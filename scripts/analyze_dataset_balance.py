"""Analyze dataset balance and integrity before YOLO training.

This script reports:
- split sizes
- orphan images and orphan labels
- per-class distribution
- class imbalance signals

It is intentionally lightweight so it can be used as a quick pre-train gate.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path


def _load_yaml(path: Path) -> dict:
    config: dict[str, object] = {}
    names: dict[int, str] = {}
    current_key: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue

        stripped = line.strip()
        if stripped.startswith("names:"):
            current_key = "names"
            config["names"] = names
            continue

        if current_key == "names" and stripped.startswith("-"):
            value = stripped.lstrip("- ").strip().strip("'\"")
            if value:
                names[len(names)] = value
            continue

        if current_key == "names" and line.startswith("  ") and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if key.isdigit():
                names[int(key)] = value
            continue

        current_key = None
        if ":" not in stripped:
            continue

        key, value = stripped.split(":", 1)
        config[key.strip()] = value.strip().strip("'\"")

    if names:
        config["names"] = names
    return config


def _resolve_path(dataset_yaml: Path, value: str, dataset_root: str | None = None) -> Path:
    value_path = Path(value)
    if value_path.is_absolute():
        return value_path.resolve()
    cwd_candidate = (Path.cwd() / value_path).resolve()
    if cwd_candidate.exists():
        return cwd_candidate
    root = Path(dataset_root or ".")
    if not root.is_absolute():
        root = (dataset_yaml.parent / root).resolve()
    return (root / value_path).resolve()


def _list_images(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted([*directory.glob("*.jpg"), *directory.glob("*.jpeg"), *directory.glob("*.png"), *directory.glob("*.webp")])


def _count_labels(label_dir: Path, class_names: list[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    if not label_dir.exists():
        return counts

    for label_file in label_dir.glob("*.txt"):
        for line in label_file.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split()
            if len(parts) != 5:
                continue
            try:
                class_index = int(parts[0])
            except ValueError:
                continue
            if 0 <= class_index < len(class_names):
                counts[class_names[class_index]] += 1
    return counts


def analyze(dataset_yaml: Path) -> None:
    config = _load_yaml(dataset_yaml)
    names = config.get("names", [])
    if isinstance(names, dict):
        names = [names[key] for key in sorted(names, key=lambda value: int(value) if str(value).isdigit() else str(value))]
    if not isinstance(names, list) or not names:
        raise RuntimeError("Dataset YAML does not define a valid class list.")

    print(f"Dataset: {dataset_yaml}")
    print(f"Classes: {len(names)}")

    total_images = 0
    total_labels = 0
    aggregated: Counter[str] = Counter()

    for split in ("train", "val", "test"):
        split_value = config.get(split)
        if not isinstance(split_value, str) or not split_value:
            raise RuntimeError(f"Missing '{split}' entry in dataset YAML.")

        dataset_root = config.get("path")
        image_dir = _resolve_path(
            dataset_yaml,
            split_value,
            str(dataset_root) if dataset_root is not None else None,
        )
        label_dir = image_dir.parent.parent / "labels" / split

        images = _list_images(image_dir)
        labels = list(label_dir.glob("*.txt")) if label_dir.exists() else []
        image_stems = {item.stem for item in images}
        label_stems = {item.stem for item in labels}

        orphan_images = sorted(image_stems - label_stems)
        orphan_labels = sorted(label_stems - image_stems)
        class_counts = _count_labels(label_dir, names)
        aggregated.update(class_counts)

        print(f"\n[{split}]")
        print(f"  images: {len(images)}")
        print(f"  labels: {len(labels)}")
        print(f"  orphan_images: {len(orphan_images)}")
        print(f"  orphan_labels: {len(orphan_labels)}")

        if class_counts:
            print("  class distribution:")
            for class_name in names:
                count = class_counts.get(class_name, 0)
                print(f"    - {class_name}: {count}")

        total_images += len(images)
        total_labels += len(labels)

    print("\n[summary]")
    print(f"  total_images: {total_images}")
    print(f"  total_labels: {total_labels}")
    print("  top classes:")
    for class_name, count in aggregated.most_common(10):
        print(f"    - {class_name}: {count}")

    if aggregated:
        counts = list(aggregated.values())
        max_count = max(counts)
        min_count = min(counts)
        ratio = max_count / max(min_count, 1)
        print(f"  imbalance_ratio: {ratio:.2f}")
        if ratio > 4:
            print("  warning: strong class imbalance detected")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analisa balanceamento e integridade do dataset YOLO")
    parser.add_argument("--data", default="dataset/architecture.yaml", help="Caminho do dataset YAML")
    args = parser.parse_args()

    dataset_yaml = Path(args.data)
    if not dataset_yaml.exists():
        raise SystemExit(f"Dataset YAML not found: {dataset_yaml}")

    analyze(dataset_yaml)


if __name__ == "__main__":
    main()
