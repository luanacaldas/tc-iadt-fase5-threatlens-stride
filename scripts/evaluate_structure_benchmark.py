"""Evaluate flow extraction independently from supervised component detection."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.diagram_structure import detect_flows, detect_trust_boundaries


def _safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _directed(flow: dict) -> tuple[str, str]:
    return str(flow["from"]), str(flow["to"])


def _undirected(flow: dict) -> tuple[str, str]:
    return tuple(sorted(_directed(flow)))


def score_flows(expected: list[dict], predicted: list[dict]) -> dict:
    expected_directed = {_directed(flow) for flow in expected}
    predicted_directed = {_directed(flow) for flow in predicted}
    expected_undirected = {_undirected(flow) for flow in expected}
    predicted_undirected = {_undirected(flow) for flow in predicted}

    directed_tp = len(expected_directed & predicted_directed)
    undirected_tp = len(expected_undirected & predicted_undirected)
    directed_precision = _safe_divide(directed_tp, len(predicted_directed))
    directed_recall = _safe_divide(directed_tp, len(expected_directed))
    undirected_precision = _safe_divide(undirected_tp, len(predicted_undirected))
    undirected_recall = _safe_divide(undirected_tp, len(expected_undirected))

    return {
        "expected": len(expected_directed),
        "predicted": len(predicted_directed),
        "directedTruePositive": directed_tp,
        "directedPrecision": directed_precision,
        "directedRecall": directed_recall,
        "directedF1": _f1(directed_precision, directed_recall),
        "undirectedTruePositive": undirected_tp,
        "undirectedPrecision": undirected_precision,
        "undirectedRecall": undirected_recall,
        "undirectedF1": _f1(undirected_precision, undirected_recall),
        "directionAccuracyOnMatchedEdges": _safe_divide(directed_tp, undirected_tp),
        "falsePositiveEdges": [list(pair) for pair in sorted(predicted_undirected - expected_undirected)],
        "missedEdges": [list(pair) for pair in sorted(expected_undirected - predicted_undirected)],
        "reversedEdges": [
            list(pair)
            for pair in sorted(expected_directed)
            if tuple(reversed(pair)) in predicted_directed
        ],
    }


def evaluate(benchmark_path: Path, output_dir: Path) -> dict:
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    per_image = []
    aggregate_expected = []
    aggregate_predicted = []

    for entry in benchmark["entries"]:
        components = entry["components"]
        boundaries = detect_trust_boundaries(entry["image"], components)
        predicted, diagnostics = detect_flows(entry["image"], components, boundaries)
        metrics = score_flows(entry["flows"], predicted)
        per_image.append(
            {
                "id": entry["id"],
                "metrics": metrics,
                "diagnostics": diagnostics,
                "predictedFlows": predicted,
                "predictedBoundaryCount": len(boundaries),
            }
        )
        aggregate_expected.extend(
            {**flow, "from": f"{entry['id']}::{flow['from']}", "to": f"{entry['id']}::{flow['to']}"}
            for flow in entry["flows"]
        )
        aggregate_predicted.extend(
            {**flow, "from": f"{entry['id']}::{flow['from']}", "to": f"{entry['id']}::{flow['to']}"}
            for flow in predicted
        )

    result = {
        "schemaVersion": "1.0",
        "evaluatedAt": datetime.now(timezone.utc).isoformat(),
        "benchmark": str(benchmark_path.resolve()),
        "imageCount": len(per_image),
        "aggregate": score_flows(aggregate_expected, aggregate_predicted),
        "boundaryEvaluation": {
            "status": "not_evaluated",
            "reason": "The generated benchmark has no trust-boundary ground truth.",
        },
        "perImage": per_image,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "structure-evaluation.json"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    _write_markdown(result, output_dir / "structure-evaluation.md")
    return result


def _write_markdown(result: dict, output: Path) -> None:
    aggregate = result["aggregate"]
    lines = [
        "# Structure Extraction Evaluation",
        "",
        f"- Images: {result['imageCount']}",
        f"- Expected flows: {aggregate['expected']}",
        f"- Predicted flows: {aggregate['predicted']}",
        f"- Undirected precision: {aggregate['undirectedPrecision']:.4f}",
        f"- Undirected recall: {aggregate['undirectedRecall']:.4f}",
        f"- Undirected F1: {aggregate['undirectedF1']:.4f}",
        f"- Directed precision: {aggregate['directedPrecision']:.4f}",
        f"- Directed recall: {aggregate['directedRecall']:.4f}",
        f"- Directed F1: {aggregate['directedF1']:.4f}",
        f"- Direction accuracy on matched edges: {aggregate['directionAccuracyOnMatchedEdges']:.4f}",
        "",
        "Boundary metrics are intentionally not reported because this generated slice has no boundary ground truth.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path("data/benchmarks/structure/benchmark.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/results/structure-current"),
    )
    args = parser.parse_args()
    result = evaluate(args.benchmark, args.output)
    aggregate = result["aggregate"]
    print(
        "Structure evaluation: "
        f"undirected F1={aggregate['undirectedF1']:.4f}, "
        f"directed F1={aggregate['directedF1']:.4f}, "
        f"direction accuracy={aggregate['directionAccuracyOnMatchedEdges']:.4f}"
    )


if __name__ == "__main__":
    main()
