"""Compare baseline and refined detectors on real development and sealed holdout boxes."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_blind_end_to_end import match_components
from scripts.evaluate_real_architecture_benchmark import components_in_image_coordinates


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _predict(model: YOLO, image: Path, confidence: float) -> list[dict]:
    result = model.predict(str(image), conf=confidence, verbose=False)[0]
    components = []
    if result.boxes is None:
        return components
    counts = {}
    for box in result.boxes:
        component_type = model.names[int(box.cls[0])]
        counts[component_type] = counts.get(component_type, 0) + 1
        components.append({
            "id": f"{component_type}_{counts[component_type]}",
            "type": component_type,
            "bbox": [int(value) for value in box.xyxy[0]],
            "confidence": float(box.conf[0]),
        })
    return components


def _evaluate_model(model_path: Path, entries: list[dict], confidence: float) -> dict:
    model = YOLO(str(model_path))
    per_image = []
    for entry in entries:
        image = ROOT / entry["image"]
        expected = components_in_image_coordinates(entry, image)
        predicted = _predict(model, image, confidence)
        per_image.append({"id": entry["id"], **match_components(expected, predicted)})
    return {
        "path": str(model_path.resolve()),
        "sha256": _sha256(model_path),
        "imageCount": len(entries),
        "meanLocalizationRecall": sum(item["localizationRecall"] for item in per_image) / len(per_image),
        "meanTypedRecall": sum(item["typedRecall"] for item in per_image) / len(per_image),
        "meanPrecision": sum(item["precision"] for item in per_image) / len(per_image),
        "perImage": per_image,
    }


def compare(benchmark: Path, baseline: Path, refined: Path, output: Path, confidence: float) -> dict:
    data = json.loads(benchmark.read_text(encoding="utf-8"))
    splits = {}
    for split in ("development_tuning", "blind_holdout"):
        entries = [entry for entry in data["entries"] if entry.get("split") == split]
        before = _evaluate_model(baseline, entries, confidence)
        after = _evaluate_model(refined, entries, confidence)
        splits[split] = {
            "baseline": before,
            "refined": after,
            "delta": {
                "meanLocalizationRecall": after["meanLocalizationRecall"] - before["meanLocalizationRecall"],
                "meanTypedRecall": after["meanTypedRecall"] - before["meanTypedRecall"],
                "meanPrecision": after["meanPrecision"] - before["meanPrecision"],
            },
        }
    result = {
        "schemaVersion": "1.0",
        "evaluatedAt": datetime.now(timezone.utc).isoformat(),
        "benchmark": str(benchmark.resolve()),
        "confidence": confidence,
        "selectionRule": "Register refined model only if development typed recall improves without a material sealed-holdout precision regression.",
        "splits": splits,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=Path("data/benchmarks/real-architecture/benchmark-expanded.json"))
    parser.add_argument("--baseline", type=Path, default=Path("models/threatlens-hybrid-v2/weights/best.pt"))
    parser.add_argument(
        "--refined",
        type=Path,
        default=Path("runs/detect/models/threatlens-active-v3/weights/best.pt"),
    )
    parser.add_argument("--output", type=Path, default=Path("data/results/active-learning/model-comparison.json"))
    parser.add_argument("--confidence", type=float, default=0.35)
    args = parser.parse_args()
    result = compare(args.benchmark, args.baseline, args.refined, args.output, args.confidence)
    print(json.dumps({split: value["delta"] for split, value in result["splits"].items()}, indent=2))


if __name__ == "__main__":
    main()
