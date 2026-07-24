"""Audit Pascal VOC annotations and ThreatLens canonical-class coverage."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

try:
    from cloud_class_mapping import CANONICAL_CLASSES, normalize_class_name
    from kaggle_dataset_utils import parse_voc_annotation
except ImportError:
    from scripts.cloud_class_mapping import CANONICAL_CLASSES, normalize_class_name
    from scripts.kaggle_dataset_utils import parse_voc_annotation


def audit_annotations(source_root: Path) -> dict:
    raw_classes: Counter[str] = Counter()
    canonical_classes: Counter[str] = Counter()
    unmapped_classes: Counter[str] = Counter()
    invalid_files: list[str] = []
    invalid_boxes = 0
    object_count = 0
    valid_file_count = 0

    xml_files = sorted(source_root.rglob("*.xml"))
    for xml_path in xml_files:
        try:
            annotation = parse_voc_annotation(xml_path, normalize_class_name)
        except Exception as exc:
            invalid_files.append(f"{xml_path}: {exc}")
            continue
        if not annotation.valid:
            invalid_files.append(f"{xml_path}: invalid image dimensions")
            continue

        valid_file_count += 1
        for item in annotation.objects:
            object_count += 1
            raw_classes[item.raw_class] += 1
            if not item.valid:
                invalid_boxes += 1
            if item.canonical_class:
                canonical_classes[item.canonical_class] += 1
            else:
                unmapped_classes[item.raw_class] += 1

    mapped_object_count = sum(canonical_classes.values())
    mapping_rate = mapped_object_count / object_count if object_count else 0.0
    missing_canonical_classes = [
        name for name in CANONICAL_CLASSES if canonical_classes.get(name, 0) == 0
    ]
    return {
        "source_root": str(source_root.resolve()),
        "xml_files": len(xml_files),
        "valid_xml_files": valid_file_count,
        "invalid_xml_files": len(invalid_files),
        "objects": object_count,
        "mapped_objects": mapped_object_count,
        "unmapped_objects": sum(unmapped_classes.values()),
        "mapping_rate": round(mapping_rate, 6),
        "invalid_boxes": invalid_boxes,
        "unique_raw_classes": len(raw_classes),
        "unique_mapped_raw_classes": len(raw_classes) - len(unmapped_classes),
        "canonical_class_distribution": dict(canonical_classes.most_common()),
        "unmapped_class_distribution": dict(unmapped_classes.most_common()),
        "missing_canonical_classes": missing_canonical_classes,
        "invalid_file_examples": invalid_files[:50],
    }


def write_report(result: dict, output_base: Path) -> None:
    output_base.parent.mkdir(parents=True, exist_ok=True)
    output_base.with_suffix(".json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    lines = [
        "# Pascal VOC Annotation Audit",
        "",
        f"- XML files: {result['xml_files']}",
        f"- Valid XML files: {result['valid_xml_files']}",
        f"- Objects: {result['objects']}",
        f"- Mapped objects: {result['mapped_objects']}",
        f"- Unmapped objects: {result['unmapped_objects']}",
        f"- Mapping rate: {result['mapping_rate']:.2%}",
        f"- Invalid boxes: {result['invalid_boxes']}",
        "",
        "## Canonical distribution",
        "",
    ]
    for class_name in CANONICAL_CLASSES:
        lines.append(f"- {class_name}: {result['canonical_class_distribution'].get(class_name, 0)}")
    lines.extend(["", "## Unmapped classes", ""])
    for raw_class, count in result["unmapped_class_distribution"].items():
        lines.append(f"- {raw_class}: {count}")
    output_base.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Pascal VOC annotations")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/manifests/kaggle_annotation_sample_audit"),
    )
    args = parser.parse_args()
    if not args.source.exists():
        raise SystemExit(f"Source directory not found: {args.source}")

    result = audit_annotations(args.source)
    write_report(result, args.output)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
