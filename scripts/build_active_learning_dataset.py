"""Build a real-image YOLO correction set from development benchmark errors only."""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.detector import detect, status
from scripts.evaluate_blind_end_to_end import match_components
from scripts.evaluate_real_architecture_benchmark import components_in_image_coordinates

CLASS_NAMES = [
    "api_gateway", "backup", "cdn", "compute", "database", "identity_provider", "internet",
    "load_balancer", "monitoring", "queue", "secrets_kms", "storage", "user", "waf",
]


def _write_yolo_label(path: Path, components: list[dict], width: int, height: int) -> None:
    lines = []
    for item in components:
        if item["type"] not in CLASS_NAMES:
            continue
        x1, y1, x2, y2 = item["bbox"]
        center_x = ((x1 + x2) / 2) / width
        center_y = ((y1 + y2) / 2) / height
        box_width = (x2 - x1) / width
        box_height = (y2 - y1) / height
        lines.append(
            f"{CLASS_NAMES.index(item['type'])} {center_x:.8f} {center_y:.8f} {box_width:.8f} {box_height:.8f}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(benchmark_path: Path, output: Path, seed: int) -> dict:
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    entries = [entry for entry in benchmark["entries"] if entry.get("split") == "development_tuning"]
    rng = random.Random(seed)
    rng.shuffle(entries)
    val_count = max(2, round(len(entries) * 0.22))
    val_ids = {entry["id"] for entry in entries[:val_count]}
    records, class_counts = [], Counter()
    for split in ("train", "val", "test"):
        (output / "images" / split).mkdir(parents=True, exist_ok=True)
        (output / "labels" / split).mkdir(parents=True, exist_ok=True)
    for entry in entries:
        image_path = ROOT / entry["image"]
        expected = components_in_image_coordinates(entry, image_path)
        predicted_architecture = detect(str(image_path)) or {"components": []}
        metrics = match_components(expected, predicted_architecture["components"])
        matched_expected = {match["expectedId"] for match in metrics["matches"] if match["typeCorrect"]}
        missed = [item["id"] for item in expected if item["id"] not in matched_expected]
        wrong_type = [match for match in metrics["matches"] if not match["typeCorrect"]]
        split = "val" if entry["id"] in val_ids else "train"
        suffix = image_path.suffix.lower() if image_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} else ".png"
        target_image = output / "images" / split / f"{entry['id']}{suffix}"
        shutil.copy2(image_path, target_image)
        with Image.open(image_path) as image:
            width, height = image.size
        _write_yolo_label(output / "labels" / split / f"{entry['id']}.txt", expected, width, height)
        class_counts.update(item["type"] for item in expected if item["type"] in CLASS_NAMES)
        records.append({
            "id": entry["id"],
            "split": split,
            "sourceImage": entry["image"],
            "expectedComponents": len(expected),
            "predictedComponents": len(predicted_architecture["components"]),
            "typedRecallBefore": metrics["typedRecall"],
            "missedComponentIds": missed,
            "wrongTypeMatches": wrong_type,
        })
    yaml_lines = [
        f"path: {output.resolve().as_posix()}", "train: images/train", "val: images/val", "test: images/test",
        f"nc: {len(CLASS_NAMES)}", "names:",
        *[f"  {index}: {name}" for index, name in enumerate(CLASS_NAMES)], "",
    ]
    (output / "architecture.yaml").write_text("\n".join(yaml_lines), encoding="utf-8")
    detector_status = status()
    manifest = {
        "schemaVersion": "1.0",
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "sourceBenchmark": str(benchmark_path.resolve()),
        "sourceSplit": "development_tuning",
        "blindHoldoutIncluded": False,
        "modelBefore": {
            "path": detector_status.get("modelPath"),
            "sha256": detector_status.get("modelSha256"),
        },
        "imageCount": len(records),
        "classCounts": dict(sorted(class_counts.items())),
        "meanTypedRecallBefore": sum(record["typedRecallBefore"] for record in records) / len(records),
        "records": records,
        "annotationPolicy": "All labels originate from the human-verified benchmark; Kaggle XML augmentation boxes are excluded.",
    }
    (output / "active-learning-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=Path("data/benchmarks/real-architecture/benchmark-expanded.json"))
    parser.add_argument("--output", type=Path, default=Path("dataset/active_learning_real_v1"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    manifest = build(args.benchmark, args.output, args.seed)
    print(json.dumps({
        "images": manifest["imageCount"],
        "meanTypedRecallBefore": manifest["meanTypedRecallBefore"],
        "blindHoldoutIncluded": manifest["blindHoldoutIncluded"],
    }, indent=2))


if __name__ == "__main__":
    main()
