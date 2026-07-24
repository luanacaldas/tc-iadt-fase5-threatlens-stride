"""Convert the local Kaggle Pascal VOC dataset into a leakage-safe YOLO set."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

try:
    from cloud_class_mapping import CANONICAL_CLASSES, normalize_class_name
    from kaggle_dataset_utils import (
        IMAGE_EXTENSIONS,
        annotation_to_yolo_lines,
        deterministic_split,
        parse_augmented_filename,
        parse_voc_annotation,
    )
except ImportError:
    from scripts.cloud_class_mapping import CANONICAL_CLASSES, normalize_class_name
    from scripts.kaggle_dataset_utils import (
        IMAGE_EXTENSIONS,
        annotation_to_yolo_lines,
        deterministic_split,
        parse_augmented_filename,
        parse_voc_annotation,
    )


@dataclass(frozen=True)
class LocalPair:
    image_path: Path
    xml_path: Path
    group_id: str
    primary_class: str
    augmentation_index: int | None


def discover_pairs(source_root: Path) -> tuple[list[LocalPair], list[Path]]:
    pairs: list[LocalPair] = []
    orphan_xml: list[Path] = []
    for xml_path in sorted(source_root.rglob("*.xml")):
        image_path = _find_image(xml_path)
        if image_path is None:
            orphan_xml.append(xml_path)
            continue
        info = parse_augmented_filename(xml_path.name)
        pairs.append(
            LocalPair(
                image_path=image_path,
                xml_path=xml_path,
                group_id=info.group_id,
                primary_class=info.primary_class,
                augmentation_index=info.augmentation_index,
            )
        )
    return pairs, orphan_xml


def _find_image(xml_path: Path) -> Path | None:
    for extension in sorted(IMAGE_EXTENSIONS):
        candidate = xml_path.with_suffix(extension)
        if candidate.exists():
            return candidate
    return None


def select_group_variants(items: list[LocalPair], maximum: int) -> list[LocalPair]:
    ordered = sorted(items, key=lambda item: (item.augmentation_index is None, item.augmentation_index or -1))
    if maximum <= 0 or len(ordered) <= maximum:
        return ordered

    sizes = [item.image_path.stat().st_size for item in ordered]
    median_size = statistics.median(sizes)
    selected = sorted(
        ordered,
        key=lambda item: (
            abs(item.image_path.stat().st_size - median_size),
            item.augmentation_index if item.augmentation_index is not None else -1,
        ),
    )[:maximum]
    return sorted(selected, key=lambda item: item.augmentation_index or -1)


def prepare_dataset(
    source_root: Path,
    output_root: Path,
    train_ratio: float,
    val_ratio: float,
    seed: str,
    max_augmentations: int,
    link_mode: str,
    dry_run: bool,
) -> dict:
    pairs, orphan_xml = discover_pairs(source_root)
    grouped: dict[str, list[LocalPair]] = defaultdict(list)
    for pair in pairs:
        grouped[pair.group_id].append(pair)

    split_groups: dict[str, set[str]] = {"train": set(), "val": set(), "test": set()}
    split_images: Counter[str] = Counter()
    mapped_classes: Counter[str] = Counter()
    raw_classes: Counter[str] = Counter()
    unmapped_classes: Counter[str] = Counter()
    rejected: Counter[str] = Counter()
    selected_pair_count = 0

    if not dry_run:
        for split in ("train", "val", "test"):
            (output_root / "images" / split).mkdir(parents=True, exist_ok=True)
            (output_root / "labels" / split).mkdir(parents=True, exist_ok=True)

    for group_id, group_items in sorted(grouped.items()):
        stratum = group_items[0].primary_class
        split = deterministic_split(group_id, stratum, train_ratio, val_ratio, seed)
        split_groups[split].add(group_id)

        selected = select_group_variants(group_items, max_augmentations)
        for item in selected:
            selected_pair_count += 1
            try:
                annotation = parse_voc_annotation(item.xml_path, normalize_class_name)
            except Exception:
                rejected["invalid_xml"] += 1
                continue

            if not annotation.valid:
                rejected["invalid_image_size"] += 1
                continue

            for obj in annotation.objects:
                raw_classes[obj.raw_class] += 1
                if obj.canonical_class:
                    mapped_classes[obj.canonical_class] += 1
                else:
                    unmapped_classes[obj.raw_class] += 1

            yolo_lines, conversion_rejected = annotation_to_yolo_lines(annotation, CANONICAL_CLASSES)
            rejected.update(conversion_rejected)
            if not yolo_lines:
                rejected["empty_after_mapping"] += 1
                continue

            split_images[split] += 1
            if dry_run:
                continue

            output_stem = f"kaggle_{item.image_path.stem}"
            image_destination = output_root / "images" / split / f"{output_stem}{item.image_path.suffix.lower()}"
            label_destination = output_root / "labels" / split / f"{output_stem}.txt"
            _materialize_file(item.image_path, image_destination, link_mode)
            label_destination.write_text("\n".join(yolo_lines) + "\n", encoding="utf-8")

    leakage = _find_split_leakage(split_groups)
    summary = {
        "source_root": str(source_root.resolve()),
        "output_root": str(output_root.resolve()),
        "dry_run": dry_run,
        "discovered_pairs": len(pairs),
        "orphan_xml": len(orphan_xml),
        "augmentation_groups": len(grouped),
        "selected_pairs": selected_pair_count,
        "written_images": dict(split_images),
        "split_group_counts": {split: len(groups) for split, groups in split_groups.items()},
        "split_leakage_groups": leakage,
        "mapped_classes": dict(mapped_classes.most_common()),
        "unmapped_classes": dict(unmapped_classes.most_common()),
        "raw_class_count": len(raw_classes),
        "rejected": dict(rejected),
        "canonical_classes": CANONICAL_CLASSES,
        "settings": {
            "train_ratio": train_ratio,
            "val_ratio": val_ratio,
            "test_ratio": round(1.0 - train_ratio - val_ratio, 6),
            "seed": seed,
            "max_augmentations_per_group": max_augmentations,
            "link_mode": link_mode,
        },
    }

    if not dry_run:
        _write_dataset_yaml(output_root)
        _write_reports(output_root, summary)
    return summary


def _materialize_file(source: Path, destination: Path, link_mode: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    if link_mode == "hardlink":
        try:
            os.link(source, destination)
            return
        except OSError:
            pass
    shutil.copy2(source, destination)


def _find_split_leakage(split_groups: dict[str, set[str]]) -> list[str]:
    owners: dict[str, list[str]] = defaultdict(list)
    for split, groups in split_groups.items():
        for group in groups:
            owners[group].append(split)
    return sorted(group for group, splits in owners.items() if len(splits) > 1)


def _write_dataset_yaml(output_root: Path) -> None:
    absolute_root = output_root.resolve().as_posix()
    lines = [
        "# ThreatLens Kaggle curated dataset",
        f"path: {absolute_root}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        f"nc: {len(CANONICAL_CLASSES)}",
        "names:",
        *[f"  {index}: {name}" for index, name in enumerate(CANONICAL_CLASSES)],
        "",
    ]
    (output_root / "architecture.yaml").write_text("\n".join(lines), encoding="utf-8")


def _write_reports(output_root: Path, summary: dict) -> None:
    report_dir = output_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "preparation-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    lines = [
        "# Kaggle Dataset Preparation Summary",
        "",
        f"- Discovered pairs: {summary['discovered_pairs']}",
        f"- Augmentation groups: {summary['augmentation_groups']}",
        f"- Selected pairs: {summary['selected_pairs']}",
        f"- Split leakage groups: {len(summary['split_leakage_groups'])}",
        f"- Raw classes found: {summary['raw_class_count']}",
        "",
        "## Split images",
        "",
    ]
    for split in ("train", "val", "test"):
        lines.append(f"- {split}: {summary['written_images'].get(split, 0)}")
    lines.extend(["", "## Unmapped classes", ""])
    for raw_class, count in list(summary["unmapped_classes"].items())[:100]:
        lines.append(f"- {raw_class}: {count}")
    (report_dir / "preparation-summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _validate_ratios(train_ratio: float, val_ratio: float) -> None:
    if train_ratio <= 0 or val_ratio < 0:
        raise ValueError("Train ratio must be positive and validation ratio cannot be negative.")
    if train_ratio + val_ratio >= 1:
        raise ValueError("Train and validation ratios must leave a positive test ratio.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the local Kaggle VOC dataset for YOLO")
    parser.add_argument("--source", type=Path, required=True, help="Extracted Kaggle dataset root")
    parser.add_argument("--output", type=Path, default=Path("dataset/kaggle_curated"))
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--seed", default="threatlens-kaggle-v1")
    parser.add_argument(
        "--max-augmentations-per-group",
        type=int,
        default=4,
        help="0 keeps every augmentation; the default curates four variants near median file size",
    )
    parser.add_argument("--link-mode", choices=("copy", "hardlink"), default="copy")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _validate_ratios(args.train_ratio, args.val_ratio)
    if not args.source.exists():
        raise SystemExit(f"Source directory not found: {args.source}")

    summary = prepare_dataset(
        source_root=args.source,
        output_root=args.output,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        seed=args.seed,
        max_augmentations=args.max_augmentations_per_group,
        link_mode=args.link_mode,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if summary["split_leakage_groups"]:
        raise SystemExit("Split leakage detected. Dataset was not accepted.")


if __name__ == "__main__":
    main()
