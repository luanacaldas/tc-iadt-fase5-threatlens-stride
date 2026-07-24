from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.diagnose_flow_errors import (
    ROOT,
    build_diagnostics,
    decision_snapshot,
    evaluate,
    required_metric_view,
)
from scripts.evaluate_structure_benchmark import score_flows


def _flow(
    flow_id: str,
    source: str,
    target: str,
    path: list[list[int]],
    **overrides,
) -> dict:
    payload = {
        "id": flow_id,
        "from": source,
        "to": target,
        "protocol": "HTTPS",
        "trustBoundary": False,
        "crossedBoundaryIds": [],
        "confidence": 0.75,
        "inferred": True,
        "reviewStatus": "pending",
        "evidence": "detected_line",
        "directionEvidence": "visual_arrowhead",
        "directionConfidence": 0.8,
        "arrowheadScores": {"classifier": {"model": "arrowhead-logistic"}},
        "pathPoints": path,
        "pixelSupport": 0.8,
        "maximumGap": 2,
        "segmentHops": 2,
        "routeEfficiency": 0.9,
    }
    payload.update(overrides)
    return payload


def _fixture() -> list[dict]:
    components = [
        {"id": "a", "type": "user", "bbox": [0, 0, 10, 10]},
        {"id": "b", "type": "api", "bbox": [20, 0, 30, 10]},
        {"id": "c", "type": "service", "bbox": [40, 0, 50, 10]},
        {"id": "d", "type": "database", "bbox": [60, 0, 70, 10]},
    ]
    expected = [
        {"id": "e1", "from": "a", "to": "b"},
        {"id": "e2", "from": "b", "to": "c"},
        {"id": "e3", "from": "c", "to": "d"},
    ]
    predicted = [
        _flow("p1", "a", "b", [[10, 5], [20, 5]]),
        _flow("p2", "c", "b", [[40, 5], [30, 5]]),
        _flow(
            "p3",
            "a",
            "d",
            [[10, 5], [25, 5], [45, 5], [60, 5]],
            segmentHops=7,
        ),
    ]
    return [{
        "id": "synthetic-development",
        "provider": "generic",
        "image": "data/benchmarks/synthetic.png",
        "components": components,
        "expectedFlows": expected,
        "predictedFlows": predicted,
        "evaluationPredictedFlows": copy.deepcopy(predicted),
        "diagnostics": {"lineSegments": 8},
        "imageSize": (100, 100),
        "detectionStrategy": "test_fixture",
    }]


def _baseline(per_image: list[dict]) -> dict:
    expected = [
        {**flow, "from": f"{item['id']}::{flow['from']}", "to": f"{item['id']}::{flow['to']}"}
        for item in per_image
        for flow in item["expectedFlows"]
    ]
    predicted = [
        {**flow, "from": f"{item['id']}::{flow['from']}", "to": f"{item['id']}::{flow['to']}"}
        for item in per_image
        for flow in item["evaluationPredictedFlows"]
    ]
    return {
        "aggregate": {"flows": score_flows(expected, predicted)},
        "perImage": [
            {"id": item["id"], "predictedFlows": copy.deepcopy(item["predictedFlows"])}
            for item in per_image
        ],
    }


class FlowDiagnosticsUnitTests(unittest.TestCase):
    def test_inventory_partitions_predictions_and_missing_edges_once(self) -> None:
        per_image = _fixture()
        result = build_diagnostics(
            per_image,
            "isolated_ground_truth",
            _baseline(per_image),
            "data/results/test-baseline.json",
        )

        self.assertEqual(
            result["statusCounts"],
            {"false_positive": 1, "missed": 1, "reversed": 1, "true_positive": 1},
        )
        self.assertEqual(len({item["inventoryId"] for item in result["records"]}), 4)
        self.assertEqual(result["requiredMetrics"]["falsePositiveEdgeCount"], 1)
        self.assertEqual(result["requiredMetrics"]["missedEdgeCount"], 1)
        self.assertEqual(result["requiredMetrics"]["reversedEdgeCount"], 1)

    def test_false_positive_labels_are_multilabel_candidate_signals(self) -> None:
        result = build_diagnostics(_fixture(), "isolated_ground_truth")
        false_positive = next(
            item for item in result["records"] if item["status"] == "false_positive"
        )

        self.assertIn("excessive_hops", false_positive["candidateLabels"])
        self.assertIn("connection_through_component", false_positive["candidateLabels"])
        self.assertEqual(false_positive["classificationStatus"], "diagnostic_hypothesis")
        self.assertFalse(false_positive["humanCauseConfirmed"])
        self.assertTrue(false_positive["requiresHumanReview"])
        self.assertEqual(
            false_positive["diagnostic"]["ocrAnchorObservation"]["status"],
            "not_observable",
        )

    def test_instrumentation_preserves_flow_decisions_and_previous_metrics(self) -> None:
        per_image = _fixture()
        baseline = _baseline(per_image)
        before = decision_snapshot(copy.deepcopy(per_image))

        result = build_diagnostics(
            per_image,
            "isolated_ground_truth",
            baseline,
            "data/results/test-baseline.json",
        )

        self.assertEqual(before, decision_snapshot(per_image))
        self.assertEqual(result["flowDecisionSnapshotIntegrity"]["status"], "PASS")
        self.assertEqual(result["previousMetricsIntegrity"]["status"], "PASS")

    def test_required_metric_names_map_to_existing_connectivity_metrics(self) -> None:
        expected = _fixture()[0]["expectedFlows"]
        predicted = _fixture()[0]["evaluationPredictedFlows"]
        legacy = score_flows(expected, predicted)

        metrics = required_metric_view(legacy)

        self.assertEqual(metrics["edgeExistenceF1"], legacy["undirectedF1"])
        self.assertEqual(metrics["directedEdgeF1"], legacy["directedF1"])
        self.assertEqual(metrics["directionAccuracy"], legacy["directionAccuracyOnMatchedEdges"])

    def test_protected_splits_are_rejected_before_loading_benchmark(self) -> None:
        for split in ("blind_holdout", "prospective_holdout"):
            with self.subTest(split=split):
                with self.assertRaisesRegex(ValueError, "development_tuning"):
                    evaluate(Path("missing.json"), Path("missing-output"), split=split)


class FlowDiagnosticsIntegrationTests(unittest.TestCase):
    def test_development_run_writes_four_relative_json_artifacts(self) -> None:
        fixture = _fixture()
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as temp_dir:
            root = Path(temp_dir)
            benchmark_path = root / "benchmark.json"
            baseline_path = root / "baseline.json"
            output_dir = root / "output"
            benchmark_path.write_text(
                json.dumps({
                    "entries": [{
                        "id": "synthetic-development",
                        "provider": "generic",
                        "image": "data/benchmarks/synthetic.png",
                        "split": "development_tuning",
                    }]
                }),
                encoding="utf-8",
            )
            baseline_path.write_text(json.dumps(_baseline(fixture)), encoding="utf-8")

            with patch(
                "scripts.diagnose_flow_errors._load_isolated_images",
                return_value=fixture,
            ):
                result = evaluate(
                    benchmark_path,
                    output_dir,
                    baseline_path=baseline_path,
                    expected_false_positive_count=1,
                )

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["previousMetricsIntegrity"], "PASS")
            self.assertEqual(result["flowDecisionSnapshotIntegrity"], "PASS")
            self.assertEqual(len(result["artifacts"]), 4)
            for relative in result["artifacts"].values():
                self.assertFalse(Path(relative).is_absolute())
                self.assertTrue((ROOT / relative).is_file())

            inventory = json.loads((output_dir / "flow-inventory.json").read_text(encoding="utf-8"))
            self.assertEqual(inventory["split"], "development_tuning")
            self.assertEqual(inventory["falsePositiveRecordCount"], 1)


if __name__ == "__main__":
    unittest.main()
