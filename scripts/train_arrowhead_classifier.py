"""Train the compact arrowhead endpoint classifier on reproducible visual samples."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.arrowhead_classifier import FEATURE_NAMES, extract_tip_features


def _sample(rng: np.random.Generator, positive: bool) -> tuple[np.ndarray, tuple[int, int], tuple[int, int]]:
    size = 64
    image = np.zeros((size, size), dtype=np.uint8)
    tip = (48 + int(rng.integers(-2, 3)), 32 + int(rng.integers(-3, 4)))
    other = (10, 32 + int(rng.integers(-2, 3)))
    thickness = int(rng.integers(1, 3))
    cv2.line(image, other, tip, 255, thickness, cv2.LINE_AA)
    if positive:
        length = int(rng.integers(8, 14))
        spread = int(rng.integers(4, 8))
        cv2.line(image, tip, (tip[0] - length, tip[1] - spread), 255, thickness, cv2.LINE_AA)
        cv2.line(image, tip, (tip[0] - length, tip[1] + spread), 255, thickness, cv2.LINE_AA)
    else:
        negative_kind = int(rng.integers(0, 4))
        if negative_kind == 0:
            cv2.line(image, tip, (tip[0], tip[1] - 12), 255, thickness, cv2.LINE_AA)
        elif negative_kind == 1:
            cv2.line(image, (tip[0], tip[1] - 10), (tip[0], tip[1] + 10), 255, thickness, cv2.LINE_AA)
        elif negative_kind == 2:
            cv2.rectangle(image, (tip[0] - 8, tip[1] - 8), (tip[0] + 5, tip[1] + 8), 255, thickness)
    noise_count = int(rng.integers(0, 18))
    for _ in range(noise_count):
        x, y = int(rng.integers(0, size)), int(rng.integers(0, size))
        image[y, x] = 255
    return image, tip, other


def train(output: Path, samples: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    features, labels = [], []
    for index in range(samples):
        positive = index % 2 == 0
        image, tip, other = _sample(rng, positive)
        features.append(extract_tip_features(image, tip, other))
        labels.append(int(positive))
    x_train, x_test, y_train, y_test = train_test_split(
        np.asarray(features), np.asarray(labels), test_size=0.25, random_state=seed, stratify=labels
    )
    scaler = StandardScaler().fit(x_train)
    classifier = LogisticRegression(random_state=seed, class_weight="balanced", max_iter=1000)
    classifier.fit(scaler.transform(x_train), y_train)
    probabilities = classifier.predict_proba(scaler.transform(x_test))[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    model = {
        "schemaVersion": "1.0",
        "modelType": "logistic_regression",
        "trainedAt": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "samples": samples,
        "featureNames": FEATURE_NAMES,
        "scaler": {"mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist()},
        "coefficients": classifier.coef_[0].tolist(),
        "intercept": float(classifier.intercept_[0]),
        "threshold": 0.5,
        "holdoutMetrics": {
            "accuracy": float(accuracy_score(y_test, predictions)),
            "precision": float(precision_score(y_test, predictions, zero_division=0)),
            "recall": float(recall_score(y_test, predictions, zero_division=0)),
            "f1": float(f1_score(y_test, predictions, zero_division=0)),
            "rocAuc": float(roc_auc_score(y_test, probabilities)),
            "count": int(len(y_test)),
        },
        "limitations": [
            "Training samples are programmatically rendered connectors, not a substitute for real arrowhead annotations.",
            "The model is a direction cue and low-confidence cases remain subject to human review.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(model, indent=2), encoding="utf-8")
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("models/arrowhead-logistic/model.json"))
    parser.add_argument("--samples", type=int, default=1600)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    model = train(args.output, args.samples, args.seed)
    print(json.dumps(model["holdoutMetrics"], indent=2))


if __name__ == "__main__":
    main()
