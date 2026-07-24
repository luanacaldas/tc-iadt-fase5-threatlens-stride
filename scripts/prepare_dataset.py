"""Prepare and normalize an architecture-diagram dataset for YOLO training.

This script consolidates mixed sources into the canonical ThreatLens format:

- Images under dataset/images/{train,val,test}
- Labels under dataset/labels/{train,val,test}
- dataset/architecture.yaml updated with the final class list

Supported input formats:
- YOLO label files (.txt)
- Pascal VOC annotation files (.xml)

The goal is not to preserve every source class. Instead, it maps each source
class into the canonical ThreatLens taxonomy so the detector stays stable
across AWS, Azure, and GCP style diagrams.
"""

from __future__ import annotations

import argparse
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


try:
    from cloud_class_mapping import CANONICAL_CLASSES as SHARED_CANONICAL_CLASSES
    from cloud_class_mapping import normalize_class_name as shared_normalize_class_name
except Exception:
    SHARED_CANONICAL_CLASSES = []
    shared_normalize_class_name = None

CANONICAL_CLASSES = SHARED_CANONICAL_CLASSES or [
    "api_gateway",
    "backup",
    "cdn",
    "compute",
    "database",
    "identity_provider",
    "internet",
    "load_balancer",
    "monitoring",
    "queue",
    "secrets_kms",
    "storage",
    "user",
    "waf",
]


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class SourceItem:
    image_path: Path
    label_path: Path | None
    split: str


def _normalize_class_name(value: str) -> str | None:
    if shared_normalize_class_name is not None:
        return shared_normalize_class_name(value)
    key = value.strip().lower().replace("-", " ").replace("_", " ")
    key = " ".join(key.split())
    if key.replace(" ", "_") in CANONICAL_CLASSES:
        return key.replace(" ", "_")
    if key in CANONICAL_CLASSES:
        return key
    return None


def _load_yaml_like_text(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        pass

    result: dict[str, object] = {}
    current_key: str | None = None
    current_list: list[str] | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith(" ") and current_key == "names" and current_list is not None:
            item = line.strip()
            if item.startswith("-"):
                current_list.append(item.lstrip("- ").strip().strip("'\"") )
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            if key == "names":
                current_list = []
                result[key] = current_list
                if value:
                    value = value.lstrip("[").rstrip("]")
                    for item in value.split(","):
                        cleaned = item.strip().strip("'\"")
                        if cleaned:
                            current_list.append(cleaned)
            else:
                current_list = None
                if value.startswith("[") and value.endswith("]"):
                    items = [item.strip().strip("'\"") for item in value.strip("[]").split(",") if item.strip()]
                    result[key] = items
                elif value.lower() in {"true", "false"}:
                    result[key] = value.lower() == "true"
                elif value.isdigit():
                    result[key] = int(value)
                else:
                    result[key] = value.strip("'\"")
    return result


def _load_source_classes(source_root: Path, class_file: Path | None) -> list[str]:
    if class_file is not None and class_file.exists():
        text = class_file.read_text(encoding="utf-8")
        if class_file.suffix.lower() in {".yaml", ".yml"}:
            data = _load_yaml_like_text(class_file)
            names = data.get("names")
            if isinstance(names, dict):
                ordered = [names[key] for key in sorted(names, key=lambda value: int(value) if str(value).isdigit() else str(value))]
                return [str(item) for item in ordered]
            if isinstance(names, list):
                return [str(item) for item in names]
        return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]

    for candidate in (source_root / "data.yaml", source_root / "dataset.yaml", source_root / "classes.txt"):
        if candidate.exists():
            return _load_source_classes(source_root, candidate)

    return []


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _find_image_pair(path: Path) -> Path | None:
    stem = path.stem
    for ext in IMAGE_EXTENSIONS:
        candidate = path.with_suffix(ext)
        if candidate.exists():
            return candidate
        candidate = path.parent / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return None


def _discover_yolo_pairs(source_dir: Path, split: str) -> list[SourceItem]:
    items: list[SourceItem] = []
    for label_path in source_dir.rglob("*.txt"):
        image_path = _find_image_pair(label_path)
        if image_path is None:
            continue
        items.append(SourceItem(image_path=image_path, label_path=label_path, split=split))
    return items


def _discover_voc_pairs(source_dir: Path, split: str) -> list[SourceItem]:
    items: list[SourceItem] = []
    for xml_path in source_dir.rglob("*.xml"):
        stem = xml_path.stem
        image_path = None
        for ext in IMAGE_EXTENSIONS:
            candidate = xml_path.with_suffix(ext)
            if candidate.exists():
                image_path = candidate
                break
            candidate = xml_path.parent / f"{stem}{ext}"
            if candidate.exists():
                image_path = candidate
                break
        if image_path is None:
            continue
        items.append(SourceItem(image_path=image_path, label_path=xml_path, split=split))
    return items


def _parse_voc(xml_path: Path) -> tuple[int, int, list[dict]]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    width = int(float(root.findtext("size/width", default="0")))
    height = int(float(root.findtext("size/height", default="0")))

    objects: list[dict] = []
    for obj in root.findall("object"):
        raw_name = obj.findtext("name", default="")
        canonical = _normalize_class_name(raw_name)
        if canonical is None:
            continue

        bbox = obj.find("bndbox")
        if bbox is None:
            continue

        xmin = float(bbox.findtext("xmin", default="0"))
        ymin = float(bbox.findtext("ymin", default="0"))
        xmax = float(bbox.findtext("xmax", default="0"))
        ymax = float(bbox.findtext("ymax", default="0"))

        objects.append(
            {
                "class": canonical,
                "bbox": [xmin, ymin, xmax, ymax],
            }
        )

    return width, height, objects


def _voc_to_yolo(xml_path: Path) -> list[str]:
    width, height, objects = _parse_voc(xml_path)
    if width <= 0 or height <= 0:
        return []

    lines: list[str] = []
    for obj in objects:
        class_name = obj["class"]
        if class_name not in CANONICAL_CLASSES:
            continue

        xmin, ymin, xmax, ymax = obj["bbox"]
        x_center = ((xmin + xmax) / 2.0) / width
        y_center = ((ymin + ymax) / 2.0) / height
        box_w = (xmax - xmin) / width
        box_h = (ymax - ymin) / height

        x_center = _clamp(x_center, 0.0, 1.0)
        y_center = _clamp(y_center, 0.0, 1.0)
        box_w = _clamp(box_w, 0.0, 1.0)
        box_h = _clamp(box_h, 0.0, 1.0)

        class_index = CANONICAL_CLASSES.index(class_name)
        lines.append(f"{class_index} {x_center:.6f} {y_center:.6f} {box_w:.6f} {box_h:.6f}")

    return lines


def _copy_image(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _write_label(destination: Path, lines: Iterable[str]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines), encoding="utf-8")


def _discover_items(source_dir: Path, split: str) -> list[SourceItem]:
    yolo_items = _discover_yolo_pairs(source_dir, split)
    voc_items = _discover_voc_pairs(source_dir, split)
    seen = {item.image_path.resolve() for item in yolo_items}
    for item in voc_items:
        if item.image_path.resolve() not in seen:
            yolo_items.append(item)
    return yolo_items


def _read_yolo_labels(label_path: Path, source_classes: list[str]) -> list[str]:
    lines: list[str] = []
    for raw_line in label_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) != 5:
            continue

        try:
            class_index = int(parts[0])
        except ValueError:
            continue

        if source_classes:
            if class_index < 0 or class_index >= len(source_classes):
                continue
            source_class_name = source_classes[class_index]
            canonical_name = _normalize_class_name(source_class_name)
            if canonical_name is None:
                continue
            canonical_index = CANONICAL_CLASSES.index(canonical_name)
        else:
            if class_index < 0 or class_index >= len(CANONICAL_CLASSES):
                continue
            canonical_index = class_index

        lines.append(" ".join([str(canonical_index), *parts[1:]]))

    return lines


def _count_yolo_labels(lines: Iterable[str]) -> dict[str, int]:
    counts = {name: 0 for name in CANONICAL_CLASSES}
    for line in lines:
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            class_index = int(parts[0])
        except ValueError:
            continue
        if 0 <= class_index < len(CANONICAL_CLASSES):
            counts[CANONICAL_CLASSES[class_index]] += 1
    return counts


def _write_architecture_yaml(dataset_root: Path) -> None:
    yaml_path = dataset_root / "architecture.yaml"
    yaml_text = "\n".join(
        [
            "# ThreatLens AI — YOLOv8 Dataset Configuration",
            "# Auto-generated by scripts/prepare_dataset.py",
            "path: .",
            "train: dataset/images/train",
            "val: dataset/images/val",
            "test: dataset/images/test",
            f"nc: {len(CANONICAL_CLASSES)}",
            "names:",
        ]
        + [f"  {index}: {name}" for index, name in enumerate(CANONICAL_CLASSES)]
        + [""]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")


def _ensure_split_dirs(dataset_root: Path) -> None:
    for split in ("train", "val", "test"):
        (dataset_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (dataset_root / "labels" / split).mkdir(parents=True, exist_ok=True)


def build_dataset(
    source_dirs: list[Path],
    dataset_root: Path,
    dry_run: bool = False,
    source_class_files: list[Path | None] | None = None,
) -> dict[str, int]:
    _ensure_split_dirs(dataset_root)

    split_counts = {"train": 0, "val": 0, "test": 0}
    label_counts = {name: 0 for name in CANONICAL_CLASSES}

    resolved_class_files = source_class_files or [None] * len(source_dirs)

    for index, source_dir in enumerate(source_dirs):
        if not source_dir.exists():
            continue

        source_classes = _load_source_classes(source_dir, resolved_class_files[index] if index < len(resolved_class_files) else None)

        for split in ("train", "val", "test", "valid"):
            split_dir = source_dir / split
            if not split_dir.exists():
                continue

            normalized_split = "val" if split == "valid" else split
            items = _discover_items(split_dir, normalized_split)

            for item in items:
                image_name = f"{source_dir.name}_{item.split}_{item.image_path.stem}{item.image_path.suffix.lower()}"
                label_name = f"{source_dir.name}_{item.split}_{item.image_path.stem}.txt"

                image_dest = dataset_root / "images" / item.split / image_name
                label_dest = dataset_root / "labels" / item.split / label_name

                if item.label_path is None:
                    continue

                if item.label_path.suffix.lower() == ".txt":
                    label_lines = _read_yolo_labels(item.label_path, source_classes)
                    if not label_lines:
                        continue
                    _copy_image(item.image_path, image_dest)
                    if not dry_run:
                        _write_label(label_dest, label_lines)
                    split_counts[item.split] += 1
                    for name, count in _count_yolo_labels(label_lines).items():
                        label_counts[name] += count
                    continue

                if item.label_path.suffix.lower() == ".xml":
                    yolo_lines = _voc_to_yolo(item.label_path)
                    if not yolo_lines:
                        continue

                    _copy_image(item.image_path, image_dest)
                    if not dry_run:
                        _write_label(label_dest, yolo_lines)
                    split_counts[item.split] += 1

                    for line in yolo_lines:
                        cls_index = int(line.split()[0])
                        if 0 <= cls_index < len(CANONICAL_CLASSES):
                            label_counts[CANONICAL_CLASSES[cls_index]] += 1

    if not dry_run:
        _write_architecture_yaml(dataset_root)

    return {**split_counts, **{f"class_{name}": count for name, count in label_counts.items()}}


def main() -> None:
    parser = argparse.ArgumentParser(description="Consolida datasets de diagramas em formato YOLO canônico")
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Diretório de origem. Pode ser repetido. Ex.: dataset/raw_hf, dataset/raw_kaggle, dataset/gcp_synthetic",
    )
    parser.add_argument(
        "--class-file",
        action="append",
        default=[],
        help="Arquivo opcional de classes para cada --source, como data.yaml, dataset.yaml ou classes.txt.",
    )
    parser.add_argument("--output", default="dataset", help="Diretório de saída consolidado (default: dataset)")
    parser.add_argument("--dry-run", action="store_true", help="Apenas calcula o que seria consolidado")
    args = parser.parse_args()

    source_dirs = [Path(item) for item in args.source]
    if not source_dirs:
        print("[prepare] Nenhuma origem informada. Use --source ao menos uma vez.")
        return

    if args.class_file and len(args.class_file) not in (0, len(source_dirs)):
        print("[prepare] Quando usar --class-file, forneça um arquivo por --source na mesma ordem.")
        return

    dataset_root = Path(args.output)
    class_files = [Path(item) for item in args.class_file] if args.class_file else None
    stats = build_dataset(source_dirs, dataset_root, dry_run=args.dry_run, source_class_files=class_files)

    print("[prepare] Consolidação concluída")
    print(f"[prepare] output: {dataset_root}")
    print(f"[prepare] dry_run: {args.dry_run}")
    print(f"[prepare] train: {stats['train']}")
    print(f"[prepare] val:   {stats['val']}")
    print(f"[prepare] test:  {stats['test']}")
    print("[prepare] classes:")
    for name in CANONICAL_CLASSES:
        print(f"  - {name}: {stats.get(f'class_{name}', 0)}")


if __name__ == "__main__":
    main()