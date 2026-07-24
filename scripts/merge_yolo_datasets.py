"""Merge compatible YOLO datasets while preserving source provenance."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from collections import Counter, defaultdict
from pathlib import Path

try:
    from kaggle_dataset_utils import parse_augmented_filename
except ImportError:
    from scripts.kaggle_dataset_utils import parse_augmented_filename


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def load_class_names(yaml_path: Path) -> list[str]:
    names: dict[int, str] = {}
    in_names = False
    for raw_line in yaml_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "names:":
            in_names = True
            continue
        if in_names and line.startswith("  ") and ":" in stripped:
            key, value = stripped.split(":", 1)
            if key.strip().isdigit():
                names[int(key.strip())] = value.strip().strip("'\"")
                continue
        if in_names and not line.startswith(" "):
            in_names = False
    return [names[index] for index in sorted(names)]


def merge_datasets(
    sources: list[tuple[str, Path]],
    output_root: Path,
    link_mode: str,
) -> dict:
    if not sources:
        raise ValueError("At least one source dataset is required.")

    expected_classes: list[str] | None = None
    source_counts: dict[str, Counter[str]] = {}
    split_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    provenance: list[dict] = []
    group_owners: dict[str, set[str]] = defaultdict(set)

    for source_name, source_root in sources:
        yaml_path = source_root / "architecture.yaml"
        if not yaml_path.exists():
            raise RuntimeError(f"Missing architecture.yaml in {source_root}")
        classes = load_class_names(yaml_path)
        if not classes:
            raise RuntimeError(f"No classes found in {yaml_path}")
        if expected_classes is None:
            expected_classes = classes
        elif classes != expected_classes:
            raise RuntimeError(
                f"Class mismatch for {source_name}. Expected {expected_classes}, found {classes}."
            )

        source_counter: Counter[str] = Counter()
        for split in ("train", "val", "test"):
            image_dir = source_root / "images" / split
            label_dir = source_root / "labels" / split
            if not image_dir.exists() or not label_dir.exists():
                raise RuntimeError(f"Missing {split} image/label directories in {source_root}")

            images = sorted(path for path in image_dir.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS)
            for image_path in images:
                label_path = label_dir / f"{image_path.stem}.txt"
                if not label_path.exists():
                    raise RuntimeError(f"Missing label for {image_path}")

                safe_source = _safe_name(source_name)
                output_stem = f"{safe_source}_{image_path.stem}"
                image_destination = output_root / "images" / split / f"{output_stem}{image_path.suffix.lower()}"
                label_destination = output_root / "labels" / split / f"{output_stem}.txt"
                _materialize(image_path, image_destination, link_mode)
                _materialize(label_path, label_destination, "copy")

                group_id = parse_augmented_filename(image_path.name).group_id
                provenance_group = f"{source_name}:{group_id}"
                group_owners[provenance_group].add(split)
                labels = _count_label_file(label_path, expected_classes)
                class_counts.update(labels)
                source_counter[split] += 1
                split_counts[split] += 1
                provenance.append(
                    {
                        "output_stem": output_stem,
                        "source": source_name,
                        "source_image": str(image_path.resolve()),
                        "source_label": str(label_path.resolve()),
                        "split": split,
                        "group_id": group_id,
                        "object_count": sum(labels.values()),
                    }
                )
        source_counts[source_name] = source_counter

    leakage_groups = sorted(group for group, splits in group_owners.items() if len(splits) > 1)
    if leakage_groups:
        raise RuntimeError(f"Group leakage detected across splits: {leakage_groups[:10]}")

    assert expected_classes is not None
    _write_yaml(output_root, expected_classes)
    _write_provenance(output_root, provenance)
    summary = {
        "output_root": str(output_root.resolve()),
        "classes": expected_classes,
        "total_images": sum(split_counts.values()),
        "split_images": dict(split_counts),
        "source_images": {
            source: dict(counts) for source, counts in source_counts.items()
        },
        "class_distribution": dict(class_counts),
        "provenance_rows": len(provenance),
        "leakage_groups": leakage_groups,
        "link_mode": link_mode,
    }
    report_dir = output_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "merge-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def _count_label_file(path: Path, classes: list[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        parts = raw_line.split()
        if len(parts) != 5:
            continue
        try:
            class_index = int(parts[0])
        except ValueError:
            continue
        if 0 <= class_index < len(classes):
            counts[classes[class_index]] += 1
    return counts


def _materialize(source: Path, destination: Path, mode: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.stat().st_size == source.stat().st_size:
            return
        destination.unlink()
    if mode == "hardlink":
        try:
            os.link(source, destination)
            return
        except OSError:
            pass
    shutil.copy2(source, destination)


def _write_yaml(output_root: Path, classes: list[str]) -> None:
    lines = [
        "# ThreatLens hybrid YOLO dataset",
        f"path: {output_root.resolve().as_posix()}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        f"nc: {len(classes)}",
        "names:",
        *[f"  {index}: {name}" for index, name in enumerate(classes)],
        "",
    ]
    (output_root / "architecture.yaml").write_text("\n".join(lines), encoding="utf-8")


def _write_provenance(output_root: Path, rows: list[dict]) -> None:
    report_dir = output_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    with (report_dir / "provenance.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "output_stem",
                "source",
                "source_image",
                "source_label",
                "split",
                "group_id",
                "object_count",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value).strip("_").lower()


def _parse_source(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Use NAME=PATH for each --source")
    name, raw_path = value.split("=", 1)
    if not name.strip() or not raw_path.strip():
        raise argparse.ArgumentTypeError("Use NAME=PATH for each --source")
    return name.strip(), Path(raw_path.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge compatible YOLO datasets")
    parser.add_argument("--source", type=_parse_source, action="append", required=True)
    parser.add_argument("--output", type=Path, default=Path("dataset/hybrid_v1"))
    parser.add_argument("--link-mode", choices=("copy", "hardlink"), default="hardlink")
    args = parser.parse_args()

    for name, path in args.source:
        if not path.exists():
            raise SystemExit(f"Source not found: {name}={path}")
    summary = merge_datasets(args.source, args.output, args.link_mode)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
