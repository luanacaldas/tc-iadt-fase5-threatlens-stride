"""Run the sealed image-to-STRIDE benchmark and count correct, missing, and extra threats."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.detector import detect
from backend.stride_engine import analyze_architecture
from scripts.evaluate_real_architecture_benchmark import components_in_image_coordinates

EXTERNAL_COMPONENT_TYPES = {"user", "internet"}


def _iou(first: list[int], second: list[int]) -> float:
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    intersection = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))
    union = max(1, (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - intersection)
    return intersection / union


def match_components(expected: list[dict], predicted: list[dict], threshold: float = 0.25) -> dict:
    candidates = []
    for expected_index, expected_component in enumerate(expected):
        for predicted_index, predicted_component in enumerate(predicted):
            overlap = _iou(expected_component["bbox"], predicted_component["bbox"])
            same_type = expected_component["type"] == predicted_component["type"]
            if overlap >= threshold:
                candidates.append((same_type, overlap, expected_index, predicted_index))
    matches, used_expected, used_predicted = [], set(), set()
    for same_type, overlap, expected_index, predicted_index in sorted(candidates, reverse=True):
        if expected_index in used_expected or predicted_index in used_predicted:
            continue
        used_expected.add(expected_index)
        used_predicted.add(predicted_index)
        matches.append({
            "expectedId": expected[expected_index]["id"],
            "predictedId": predicted[predicted_index]["id"],
            "expectedType": expected[expected_index]["type"],
            "predictedType": predicted[predicted_index]["type"],
            "typeCorrect": same_type,
            "iou": round(overlap, 4),
        })
    type_correct = sum(match["typeCorrect"] for match in matches)
    return {
        "matches": matches,
        "expected": len(expected),
        "predicted": len(predicted),
        "localized": len(matches),
        "typeCorrect": type_correct,
        "localizationRecall": len(matches) / len(expected) if expected else 1.0,
        "typedRecall": type_correct / len(expected) if expected else 1.0,
        "precision": len(matches) / len(predicted) if predicted else (1.0 if not expected else 0.0),
    }


def apply_expected_provider(components: list[dict], entry_provider: str) -> list[dict]:
    """Attach diagram provider context without assigning cloud ownership to external actors."""
    for component in components:
        component.setdefault(
            "provider",
            "generic" if component.get("type") in EXTERNAL_COMPONENT_TYPES else entry_provider,
        )
    return components


def _threat_signature(threat: dict, component_mapping: dict[str, str] | None = None) -> str:
    component_id = threat.get("componentId") or "architecture"
    if component_mapping is not None and component_id != "architecture":
        component_id = component_mapping.get(component_id, f"unmatched::{component_id}")
    return "|".join((threat["stride"], threat["title"], component_id))


def score_threats(expected: list[dict], predicted: list[dict], component_mapping: dict[str, str]) -> dict:
    expected_signatures = {_threat_signature(threat) for threat in expected}
    predicted_signatures = {_threat_signature(threat, component_mapping) for threat in predicted}
    correct = expected_signatures & predicted_signatures
    missing = expected_signatures - predicted_signatures
    extra = predicted_signatures - expected_signatures
    precision = len(correct) / len(predicted_signatures) if predicted_signatures else 0.0
    recall = len(correct) / len(expected_signatures) if expected_signatures else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "expected": len(expected_signatures),
        "predicted": len(predicted_signatures),
        "correct": len(correct),
        "missing": len(missing),
        "extra": len(extra),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "correctSignatures": sorted(correct),
        "missingSignatures": sorted(missing),
        "extraSignatures": sorted(extra),
    }


def evaluate(
    benchmark_path: Path,
    output_dir: Path,
    split: str = "blind_holdout",
    protocol: str = "sealed_first_pass",
) -> dict:
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    entries = [entry for entry in benchmark["entries"] if entry.get("split") == split]
    per_image = []
    for entry in entries:
        image_path = PROJECT_ROOT / entry["image"]
        expected_components = apply_expected_provider(
            components_in_image_coordinates(entry, image_path),
            str(entry.get("provider") or "generic"),
        )
        expected_architecture = {
            "name": entry["id"],
            "components": expected_components,
            "flows": entry.get("flows") or [],
            "trustBoundaries": entry.get("boundaries") or [],
            "reviewedByHuman": True,
        }
        predicted_architecture = detect(str(image_path)) or {
            "name": entry["id"], "components": [], "flows": [], "trustBoundaries": []
        }
        component_metrics = match_components(expected_components, predicted_architecture["components"])
        component_mapping = {
            match["predictedId"]: match["expectedId"] for match in component_metrics["matches"]
        }
        expected_analysis = analyze_architecture(expected_architecture)
        predicted_analysis = analyze_architecture(predicted_architecture)
        threat_metrics = score_threats(
            expected_analysis["threats"], predicted_analysis["threats"], component_mapping
        )
        per_image.append({
            "id": entry["id"],
            "provider": entry["provider"],
            "image": entry["image"],
            "components": component_metrics,
            "threats": threat_metrics,
            "predictedStructure": {
                "components": len(predicted_architecture["components"]),
                "flows": len(predicted_architecture.get("flows") or []),
                "boundaries": len(predicted_architecture.get("trustBoundaries") or []),
            },
        })
    totals = {
        key: sum(item["threats"][key] for item in per_image)
        for key in ("expected", "predicted", "correct", "missing", "extra")
    }
    precision = totals["correct"] / totals["predicted"] if totals["predicted"] else 0.0
    recall = totals["correct"] / totals["expected"] if totals["expected"] else 1.0
    result = {
        "schemaVersion": "1.1",
        "evaluatedAt": datetime.now(timezone.utc).isoformat(),
        "benchmark": str(benchmark_path.resolve()),
        "split": split,
        "evaluationProtocol": protocol,
        "imageCount": len(entries),
        "aggregate": {
            **totals,
            "precision": precision,
            "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "meanComponentTypedRecall": (
                sum(item["components"]["typedRecall"] for item in per_image) / len(per_image)
                if per_image else 0.0
            ),
        },
        "perImage": per_image,
        "interpretation": (
            "Threat correctness is evaluated after the full supervised detector -> graph -> STRIDE chain. "
            "Expected STRIDE cases are generated from human-annotated architecture facts with the same "
            "versioned rule base and the benchmark's explicit provider context."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"end-to-end-{split}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=Path("data/benchmarks/real-architecture/benchmark-expanded.json"))
    parser.add_argument("--output", type=Path, default=Path("data/results/end-to-end"))
    parser.add_argument("--split", default="blind_holdout")
    parser.add_argument(
        "--protocol",
        default="sealed_first_pass",
        help="Audit label such as sealed_first_pass or posthoc_diagnostic_after_unsealing.",
    )
    args = parser.parse_args()
    result = evaluate(args.benchmark, args.output, args.split, args.protocol)
    print(json.dumps(result["aggregate"], indent=2))


if __name__ == "__main__":
    main()
