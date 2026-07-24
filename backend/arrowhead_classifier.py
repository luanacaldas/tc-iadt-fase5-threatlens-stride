"""Small, auditable classifier for arrowhead tips in architecture connectors."""

from __future__ import annotations

import json
import math
import os
from functools import lru_cache
from pathlib import Path

MODEL_PATH = Path(os.getenv("ARROWHEAD_MODEL_PATH", "models/arrowhead-logistic/model.json"))
FEATURE_NAMES = [
    "ray_left_032",
    "ray_right_032",
    "ray_left_045",
    "ray_right_045",
    "local_density",
    "bilateral_support",
]


def _patch_has_edge(edges, x: int, y: int, radius: int = 1) -> bool:
    height, width = edges.shape[:2]
    if not (0 <= x < width and 0 <= y < height):
        return False
    return bool(edges[max(0, y - radius):min(height, y + radius + 1), max(0, x - radius):min(width, x + radius + 1)].any())


def extract_tip_features(
    edges,
    tip: tuple[float, float],
    other_point: tuple[float, float],
) -> list[float]:
    """Extract rotation-invariant ray and density features around one endpoint."""
    tip_x, tip_y = tip
    vector_x, vector_y = other_point[0] - tip_x, other_point[1] - tip_y
    length = math.hypot(vector_x, vector_y)
    if length <= 1:
        return [0.0] * len(FEATURE_NAMES)
    unit_x, unit_y = vector_x / length, vector_y / length

    def ray_support(angle: float) -> float:
        cosine, sine = math.cos(angle), math.sin(angle)
        ray_x = unit_x * cosine - unit_y * sine
        ray_y = unit_x * sine + unit_y * cosine
        samples = [(round(tip_x + ray_x * distance), round(tip_y + ray_y * distance)) for distance in range(3, 13)]
        return sum(_patch_has_edge(edges, x, y) for x, y in samples) / max(1, len(samples))

    left_032 = ray_support(0.32)
    right_032 = ray_support(-0.32)
    left_045 = ray_support(0.45)
    right_045 = ray_support(-0.45)
    local_points = [
        (round(tip_x + dx), round(tip_y + dy))
        for dx in range(-6, 7, 2)
        for dy in range(-6, 7, 2)
    ]
    density = sum(_patch_has_edge(edges, x, y, 0) for x, y in local_points) / len(local_points)
    bilateral = max(min(left_032, right_032), min(left_045, right_045))
    return [left_032, right_032, left_045, right_045, density, bilateral]


@lru_cache(maxsize=1)
def load_model(path: str | Path | None = None) -> dict | None:
    model_path = Path(path) if path else MODEL_PATH
    if not model_path.is_file():
        return None
    try:
        model = json.loads(model_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if model.get("featureNames") != FEATURE_NAMES:
        return None
    return model


def predict_probability(
    edges,
    tip: tuple[float, float],
    other_point: tuple[float, float],
    model: dict | None = None,
) -> float | None:
    model = model or load_model()
    if not model:
        return None
    features = extract_tip_features(edges, tip, other_point)
    means = model["scaler"]["mean"]
    scales = model["scaler"]["scale"]
    normalized = [(value - mean) / max(scale, 1e-9) for value, mean, scale in zip(features, means, scales)]
    logit = model["intercept"] + sum(weight * value for weight, value in zip(model["coefficients"], normalized))
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-min(logit, 60)))
    exp_value = math.exp(max(logit, -60))
    return exp_value / (1.0 + exp_value)

