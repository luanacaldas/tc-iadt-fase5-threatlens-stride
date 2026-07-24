"""Build reproducible flow ground truth for the reserved generated test diagrams."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from scripts.generate_synthetic_dataset import (
        CLASS_IDX,
        IMG_H,
        IMG_W,
        generate_layout,
        structure_from_layout,
    )
except ModuleNotFoundError:
    from generate_synthetic_dataset import (  # type: ignore[no-redef]
        CLASS_IDX,
        IMG_H,
        IMG_W,
        generate_layout,
        structure_from_layout,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_component_ground_truth(image_path: Path, components: list[dict]) -> None:
    label_path = Path(str(image_path).replace("\\images\\", "\\labels\\")).with_suffix(".txt")
    if not label_path.exists():
        label_path = Path(str(image_path).replace("/images/", "/labels/")).with_suffix(".txt")
    rows = [line.split() for line in label_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    expected = []
    for component in components:
        x1, y1, x2, y2 = component["bbox"]
        expected.append(
            (
                CLASS_IDX[component["type"]],
                (x1 + x2) / 2 / IMG_W,
                (y1 + y2) / 2 / IMG_H,
                (x2 - x1) / IMG_W,
                (y2 - y1) / IMG_H,
            )
        )
    actual = [(int(row[0]), *(float(value) for value in row[1:5])) for row in rows]
    if len(actual) != len(expected) or any(
        actual_row[0] != expected_row[0]
        or any(abs(actual_row[index] - expected_row[index]) > 1e-5 for index in range(1, 5))
        for actual_row, expected_row in zip(actual, expected)
    ):
        raise ValueError(f"Seed reconstruction does not match YOLO ground truth: {image_path}")


def build_benchmark(
    image_dir: Path,
    output: Path,
    seed_base: int = 42,
    train_count: int = 210,
    validation_count: int = 60,
) -> dict:
    images = sorted(image_dir.glob("current_arch_test_*.jpg"))
    if not images:
        raise FileNotFoundError(f"No reserved generated test images found in {image_dir}")

    entries = []
    first_test_index = train_count + validation_count
    for index, image_path in enumerate(images):
        seed = seed_base * 1000 + first_test_index + index
        structure = structure_from_layout(generate_layout(seed))
        _validate_component_ground_truth(image_path, structure["components"])
        entries.append(
            {
                "id": image_path.stem,
                "image": image_path.resolve().as_posix(),
                "imageSha256": _sha256(image_path),
                "source": "generated_known_graph",
                "seed": seed,
                **structure,
            }
        )

    payload = {
        "schemaVersion": "1.0",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "purpose": "Structure-only benchmark using known generated graph ground truth.",
        "limitations": [
            "This initial slice is generated and does not replace manually annotated real diagrams.",
            "The benchmark isolates structure extraction by using ground-truth component boxes.",
            "The generated diagrams contain no trust-boundary ground truth.",
        ],
        "imageCount": len(entries),
        "flowCount": sum(len(entry["flows"]) for entry in entries),
        "entries": entries,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--images",
        type=Path,
        default=Path("dataset/hybrid_v2/images/test"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/benchmarks/structure/benchmark.json"),
    )
    args = parser.parse_args()
    result = build_benchmark(args.images, args.output)
    print(f"Structure benchmark: {result['imageCount']} images, {result['flowCount']} flows")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
