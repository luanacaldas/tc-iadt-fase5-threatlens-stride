"""Evaluate flow, trust-boundary, and OCR extraction on manually annotated real diagrams."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.diagram_structure import detect_flows, detect_trust_boundaries
from backend.ocr import apply_protocol_evidence, extract_text_lines
from scripts.evaluate_structure_benchmark import score_flows


def _safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _member_set(boundary: dict) -> frozenset[str]:
    return frozenset(str(item) for item in boundary.get("componentIds") or [])


def score_boundaries(expected: list[dict], predicted: list[dict], threshold: float = 0.5) -> dict:
    candidates = []
    for expected_index, expected_boundary in enumerate(expected):
        expected_members = _member_set(expected_boundary)
        for predicted_index, predicted_boundary in enumerate(predicted):
            predicted_members = _member_set(predicted_boundary)
            union = expected_members | predicted_members
            jaccard = len(expected_members & predicted_members) / len(union) if union else 0.0
            if jaccard >= threshold:
                candidates.append((jaccard, expected_index, predicted_index))

    matches = []
    used_expected: set[int] = set()
    used_predicted: set[int] = set()
    for jaccard, expected_index, predicted_index in sorted(candidates, reverse=True):
        if expected_index in used_expected or predicted_index in used_predicted:
            continue
        used_expected.add(expected_index)
        used_predicted.add(predicted_index)
        matches.append(
            {
                "expectedId": expected[expected_index].get("id"),
                "predictedId": predicted[predicted_index].get("id"),
                "memberJaccard": jaccard,
            }
        )

    true_positive = len(matches)
    precision = _safe_divide(true_positive, len(predicted))
    recall = _safe_divide(true_positive, len(expected))
    if not expected and not predicted:
        precision = recall = 1.0
    return {
        "expected": len(expected),
        "predicted": len(predicted),
        "truePositive": true_positive,
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
        "meanMatchedMemberJaccard": (
            sum(match["memberJaccard"] for match in matches) / len(matches) if matches else 0.0
        ),
        "matches": matches,
    }


def score_protocols(expected: list[dict], flows: list[dict]) -> dict:
    expected_pairs = {(item["flowId"], item["value"].lower()) for item in expected}
    predicted_pairs = {
        (flow["id"], str(flow.get("protocol") or "unknown").lower())
        for flow in flows
        if str(flow.get("protocol") or "unknown").lower() != "unknown"
    }
    true_positive = expected_pairs & predicted_pairs
    false_positive = predicted_pairs - expected_pairs
    false_negative = expected_pairs - predicted_pairs
    precision = _safe_divide(len(true_positive), len(predicted_pairs))
    recall = _safe_divide(len(true_positive), len(expected_pairs))
    if not expected_pairs and not predicted_pairs:
        precision = recall = 1.0
    return {
        "expected": len(expected_pairs),
        "predicted": len(predicted_pairs),
        "truePositive": len(true_positive),
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
        "falsePositive": [list(pair) for pair in sorted(false_positive)],
        "falseNegative": [list(pair) for pair in sorted(false_negative)],
    }


def _aggregate_counts(items: list[dict]) -> dict:
    expected = sum(item["expected"] for item in items)
    predicted = sum(item["predicted"] for item in items)
    true_positive = sum(item["truePositive"] for item in items)
    precision = _safe_divide(true_positive, predicted)
    recall = _safe_divide(true_positive, expected)
    return {
        "expected": expected,
        "predicted": predicted,
        "truePositive": true_positive,
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
    }


def components_in_image_coordinates(entry: dict, image_path: Path) -> list[dict]:
    """Scale manual boxes when annotations were made against a rendered preview."""
    annotation_size = entry.get("annotationSize")
    components = copy.deepcopy(entry["components"])
    with Image.open(image_path) as image:
        image_width, image_height = image.size
    for component in components:
        if "bboxNormalized" in component:
            x1, y1, x2, y2 = component.pop("bboxNormalized")
            component["bbox"] = [
                round(x1 * image_width), round(y1 * image_height),
                round(x2 * image_width), round(y2 * image_height),
            ]
    if not annotation_size:
        return components
    annotation_width, annotation_height = annotation_size
    if annotation_width <= 0 or annotation_height <= 0:
        raise ValueError(f"Invalid annotationSize for {entry.get('id')}: {annotation_size}")
    scale_x = image_width / annotation_width
    scale_y = image_height / annotation_height
    for component in components:
        x1, y1, x2, y2 = component["bbox"]
        component["bbox"] = [
            round(x1 * scale_x),
            round(y1 * scale_y),
            round(x2 * scale_x),
            round(y2 * scale_y),
        ]
    return components


def evaluate(benchmark_path: Path, output_dir: Path, split: str | None = "development_tuning") -> dict:
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    per_image = []
    aggregate_expected_flows = []
    aggregate_predicted_flows = []

    selected_entries = [
        entry for entry in benchmark["entries"]
        if split in {None, "all"} or entry.get("split") == split
    ]
    for entry in selected_entries:
        image_path = PROJECT_ROOT / entry["image"]
        if not image_path.is_file():
            raise FileNotFoundError(f"Benchmark image not found: {image_path}")
        components = components_in_image_coordinates(entry, image_path)
        predicted_boundaries = detect_trust_boundaries(image_path, components)
        predicted_flows, diagnostics = detect_flows(image_path, components, predicted_boundaries)
        flow_metrics = score_flows(entry["flows"], predicted_flows)
        boundary_metrics = score_boundaries(entry.get("boundaries") or [], predicted_boundaries)

        ocr_lines = extract_text_lines(image_path)
        protocol_flows = [
            {**copy.deepcopy(flow), "protocol": "unknown"}
            for flow in entry["flows"]
        ]
        apply_protocol_evidence(protocol_flows, components, ocr_lines)
        protocol_metrics = score_protocols(entry.get("protocols") or [], protocol_flows)

        per_image.append(
            {
                "id": entry["id"],
                "provider": entry["provider"],
                "sourceGroup": entry["sourceGroup"],
                "image": entry["image"],
                "annotationSize": entry.get("annotationSize"),
                "flowMetrics": flow_metrics,
                "boundaryMetrics": boundary_metrics,
                "protocolMetrics": protocol_metrics,
                "diagnostics": diagnostics,
                "ocrLineCount": len(ocr_lines),
                "predictedBoundaries": predicted_boundaries,
                "predictedFlows": predicted_flows,
                "protocolFlows": protocol_flows,
            }
        )
        aggregate_expected_flows.extend(
            {**flow, "from": f"{entry['id']}::{flow['from']}", "to": f"{entry['id']}::{flow['to']}"}
            for flow in entry["flows"]
        )
        aggregate_predicted_flows.extend(
            {**flow, "from": f"{entry['id']}::{flow['from']}", "to": f"{entry['id']}::{flow['to']}"}
            for flow in predicted_flows
        )

    result = {
        "schemaVersion": "1.0",
        "evaluatedAt": datetime.now(timezone.utc).isoformat(),
        "benchmark": str(benchmark_path.resolve()),
        "imageCount": len(per_image),
        "split": split or "all",
        "aggregate": {
            "flows": score_flows(aggregate_expected_flows, aggregate_predicted_flows),
            "boundaries": _aggregate_counts([item["boundaryMetrics"] for item in per_image]),
            "protocols": _aggregate_counts([item["protocolMetrics"] for item in per_image]),
        },
        "perImage": per_image,
        "interpretation": (
            "This benchmark uses manually annotated primary architecture content from reserved real-image groups. "
            "Ground-truth component boxes isolate structure and OCR from component-detection quality."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "real-architecture-evaluation.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    _write_markdown(result, output_dir / "real-architecture-evaluation.md")
    return result


def _write_markdown(result: dict, output: Path) -> None:
    flows = result["aggregate"]["flows"]
    boundaries = result["aggregate"]["boundaries"]
    protocols = result["aggregate"]["protocols"]
    lines = [
        "# Real Architecture Extraction Evaluation",
        "",
        f"- Images: {result['imageCount']}",
        f"- Flow adjacency F1: {flows['undirectedF1']:.4f}",
        f"- Flow directed F1: {flows['directedF1']:.4f}",
        f"- Direction accuracy on matched flows: {flows['directionAccuracyOnMatchedEdges']:.4f}",
        f"- Trust-boundary membership F1: {boundaries['f1']:.4f}",
        f"- OCR protocol assignment F1: {protocols['f1']:.4f}",
        "",
        "## Per image",
        "",
    ]
    for item in result["perImage"]:
        lines.append(
            f"- **{item['id']}**: adjacency F1 {item['flowMetrics']['undirectedF1']:.4f}; "
            f"directed F1 {item['flowMetrics']['directedF1']:.4f}; "
            f"boundary F1 {item['boundaryMetrics']['f1']:.4f}; "
            f"protocol F1 {item['protocolMetrics']['f1']:.4f}."
        )
    lines += [
        "",
        "Ground-truth component boxes are supplied to isolate structure and OCR quality. "
        "The source images include dataset augmentation overlays; only visible primary-diagram content is annotated.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path("data/benchmarks/real-architecture/benchmark-expanded.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/results/real-architecture"),
    )
    parser.add_argument("--split", default="development_tuning")
    args = parser.parse_args()
    result = evaluate(args.benchmark, args.output, args.split)
    aggregate = result["aggregate"]
    print(
        "Real architecture evaluation: "
        f"adjacency F1={aggregate['flows']['undirectedF1']:.4f}, "
        f"directed F1={aggregate['flows']['directedF1']:.4f}, "
        f"boundary F1={aggregate['boundaries']['f1']:.4f}, "
        f"protocol F1={aggregate['protocols']['f1']:.4f}"
    )


if __name__ == "__main__":
    main()
