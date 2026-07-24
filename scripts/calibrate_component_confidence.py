"""Calibrate YOLO component confidence against human-reviewed real diagrams."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_real_architecture_benchmark import components_in_image_coordinates


def _iou(first: list[int], second: list[int]) -> float:
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    intersection = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))
    union = max(1, (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - intersection)
    return intersection / union


def _features(confidence: float, area_ratio: float) -> list[float]:
    bounded = min(1 - 1e-6, max(1e-6, confidence))
    return [math.log(bounded / (1 - bounded)), math.log(max(area_ratio, 1e-7))]


def _collect(model: YOLO, benchmark: dict, confidence: float) -> list[dict]:
    records: list[dict] = []
    entries = [entry for entry in benchmark["entries"] if entry.get("split") == "development_tuning"]
    for entry in entries:
        image_path = ROOT / entry["image"]
        expected = components_in_image_coordinates(entry, image_path)
        result = model.predict(str(image_path), conf=confidence, verbose=False)[0]
        height, width = result.orig_shape
        predictions = []
        for box in result.boxes or []:
            bbox = [int(value) for value in box.xyxy[0]]
            predictions.append({
                "type": model.names[int(box.cls[0])],
                "bbox": bbox,
                "confidence": float(box.conf[0]),
                "areaRatio": ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / max(1, width * height),
            })

        candidates = []
        for predicted_index, predicted in enumerate(predictions):
            for expected_index, expected_component in enumerate(expected):
                if predicted["type"] != expected_component["type"]:
                    continue
                overlap = _iou(predicted["bbox"], expected_component["bbox"])
                if overlap >= 0.25:
                    candidates.append((overlap, predicted_index, expected_index))
        positives, used_expected = set(), set()
        for _, predicted_index, expected_index in sorted(candidates, reverse=True):
            if predicted_index in positives or expected_index in used_expected:
                continue
            positives.add(predicted_index)
            used_expected.add(expected_index)

        for index, predicted in enumerate(predictions):
            records.append({
                "diagramId": entry["id"],
                **predicted,
                "correct": int(index in positives),
                "features": _features(predicted["confidence"], predicted["areaRatio"]),
            })
    return records


def _ece(labels: np.ndarray, probabilities: np.ndarray, bins: int = 5) -> float:
    score = 0.0
    for lower in np.linspace(0, 1, bins, endpoint=False):
        upper = lower + 1 / bins
        mask = (probabilities >= lower) & (probabilities < upper if upper < 1 else probabilities <= upper)
        if mask.any():
            score += mask.mean() * abs(labels[mask].mean() - probabilities[mask].mean())
    return float(score)


def calibrate(benchmark_path: Path, model_path: Path, output_model: Path, output_result: Path) -> dict:
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    model = YOLO(str(model_path))
    records = _collect(model, benchmark, confidence=0.15)
    features = np.asarray([record["features"] for record in records], dtype=float)
    labels = np.asarray([record["correct"] for record in records], dtype=int)
    groups = np.asarray([record["diagramId"] for record in records])
    if len(np.unique(labels)) < 2:
        raise RuntimeError("Calibration requires both correct and incorrect real-diagram detections")

    oof = np.zeros(len(records), dtype=float)
    for diagram_id in sorted(set(groups)):
        validation = groups == diagram_id
        training = ~validation
        if len(np.unique(labels[training])) < 2:
            oof[validation] = labels[training].mean()
            continue
        fold = LogisticRegression(C=1.0, random_state=42, max_iter=1000)
        fold.fit(features[training], labels[training])
        oof[validation] = fold.predict_proba(features[validation])[:, 1]

    final = LogisticRegression(C=1.0, random_state=42, max_iter=1000)
    final.fit(features, labels)
    raw = np.asarray([record["confidence"] for record in records])
    threshold_rows = []
    for threshold in (0.5, 0.6, 0.7, 0.8, 0.9):
        selected = oof >= threshold
        threshold_rows.append({
            "threshold": threshold,
            "coverage": float(selected.mean()),
            "precision": float(labels[selected].mean()) if selected.any() else None,
            "count": int(selected.sum()),
        })
    deploy_threshold = next(
        (row["threshold"] for row in threshold_rows if row["count"] >= 3 and row["precision"] >= 0.8),
        0.9,
    )

    model_payload = {
        "schemaVersion": "1.0",
        "method": "platt_logistic_with_area",
        "trainedAt": datetime.now(timezone.utc).isoformat(),
        "seed": 42,
        "modelPath": str(model_path).replace("\\", "/"),
        "benchmarkPath": str(benchmark_path).replace("\\", "/"),
        "split": "development_tuning",
        "featureNames": ["confidence_logit", "log_bbox_area_ratio"],
        "coef": final.coef_[0].tolist(),
        "intercept": float(final.intercept_[0]),
        "automaticAcceptanceThreshold": deploy_threshold,
        "trainingRecords": len(records),
        "positiveRecords": int(labels.sum()),
    }
    result = {
        "schemaVersion": "1.0",
        "evaluatedAt": datetime.now(timezone.utc).isoformat(),
        "protocol": "leave_one_diagram_out_on_development_only",
        "diagramCount": len(set(groups)),
        "predictionCount": len(records),
        "correctPredictionCount": int(labels.sum()),
        "metrics": {
            "rawBrier": float(brier_score_loss(labels, raw)),
            "calibratedBrier": float(brier_score_loss(labels, oof)),
            "rawEce": _ece(labels, raw),
            "calibratedEce": _ece(labels, oof),
        },
        "automaticAcceptance": threshold_rows,
        "selectedThreshold": deploy_threshold,
        "blindHoldoutUsed": False,
        "model": model_payload,
    }
    output_model.parent.mkdir(parents=True, exist_ok=True)
    output_result.parent.mkdir(parents=True, exist_ok=True)
    output_model.write_text(json.dumps(model_payload, indent=2), encoding="utf-8")
    output_result.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=Path("data/benchmarks/real-architecture/benchmark-expanded.json"))
    parser.add_argument("--model", type=Path, default=Path("models/threatlens-hybrid-v2/weights/best.pt"))
    parser.add_argument("--output-model", type=Path, default=Path("models/component-confidence-calibration.json"))
    parser.add_argument("--output-result", type=Path, default=Path("data/results/calibration/component-confidence.json"))
    args = parser.parse_args()
    result = calibrate(args.benchmark, args.model, args.output_model, args.output_result)
    print(json.dumps(result["metrics"] | {"selectedThreshold": result["selectedThreshold"]}, indent=2))


if __name__ == "__main__":
    main()
