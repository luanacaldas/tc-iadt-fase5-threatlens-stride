from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from backend.structural_line_gate import (
    apply_structural_line_gate,
    evaluate_structural_line_candidate,
    evaluate_structural_line_gate,
)
from scripts.build_tl_struct_001a_artifacts import build_artifacts


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads((ROOT / "tests/fixtures/tl_struct_001a.json").read_text(encoding="utf-8"))["fixtures"]


def _candidate(fixture: dict, candidate_id: str | None = None) -> dict:
    return {
        "candidateId": candidate_id or fixture["id"],
        "legacyFrom": "A",
        "legacyTo": "B",
        "finalAction": fixture.get("baseAction", "review_only"),
        "confidence": "low",
        "protected": fixture.get("protected", False),
        "adjacentRelations": [],
    }


class StructuralLineFixtureTests(unittest.TestCase):
    pass


def _make_fixture_test(fixture: dict):
    def test(self: StructuralLineFixtureTests) -> None:
        decision = evaluate_structural_line_candidate(_candidate(fixture), fixture["evidence"])
        self.assertEqual(decision["gateAction"], fixture["expectedAction"])
        self.assertFalse(decision["officialResultChanged"])
        self.assertFalse(decision["officialDirectionChanged"])

    return test


for _fixture in FIXTURES:
    setattr(StructuralLineFixtureTests, f"test_fixture_{_fixture['id']}", _make_fixture_test(_fixture))


class StructuralLineContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.block_fixture = next(item for item in FIXTURES if item["id"] == "container_border_without_ports")
        self.review_fixture = next(item for item in FIXTURES if item["id"] == "low_confidence_structural_signal")
        self.flow = {"id": "f1", "from": "A", "to": "B", "directionConfidence": 1}

    def test_invalid_endpoint_evidence_is_rejected(self) -> None:
        evidence = copy.deepcopy(self.block_fixture["evidence"])
        evidence["sourcePortConfirmed"] = "false"
        with self.assertRaisesRegex(ValueError, "sourcePortConfirmed"):
            evaluate_structural_line_candidate(_candidate(self.block_fixture), evidence)

    def test_inputs_are_immutable(self) -> None:
        candidate = _candidate(self.block_fixture)
        evidence = copy.deepcopy(self.block_fixture["evidence"])
        before = copy.deepcopy((candidate, evidence))
        evaluate_structural_line_candidate(candidate, evidence)
        self.assertEqual((candidate, evidence), before)

    def test_batch_execution_is_deterministic_and_order_independent(self) -> None:
        first_candidate = _candidate(self.block_fixture, "f1")
        second_candidate = _candidate(self.review_fixture, "f2")
        evidence = {"f1": self.block_fixture["evidence"], "f2": self.review_fixture["evidence"]}
        first = evaluate_structural_line_gate([first_candidate, second_candidate], evidence)
        second = evaluate_structural_line_gate([second_candidate, first_candidate], evidence)
        self.assertEqual(first, second)
        self.assertEqual(first["decisionCount"], 2)

    def test_block_removes_only_the_selected_edge(self) -> None:
        base = _candidate(self.block_fixture, "f1")
        gate = evaluate_structural_line_candidate(base, self.block_fixture["evidence"])
        result = apply_structural_line_gate([self.flow], [base], [gate])
        self.assertEqual(result["flows"], [])
        self.assertEqual(result["newEdgeCount"], 0)

    def test_review_only_does_not_change_edge(self) -> None:
        base = _candidate(self.review_fixture, "f1")
        gate = evaluate_structural_line_candidate(base, self.review_fixture["evidence"])
        result = apply_structural_line_gate([self.flow], [base], [gate])
        self.assertEqual([(item["from"], item["to"]) for item in result["flows"]], [("A", "B")])
        self.assertEqual(result["reviewOnlyAppliedCount"], 0)

    def test_existing_transitive_block_is_preserved(self) -> None:
        fixture = copy.deepcopy(self.block_fixture)
        fixture["baseAction"] = "block"
        base = _candidate(fixture, "f1")
        gate = evaluate_structural_line_candidate(base, fixture["evidence"])
        self.assertEqual(gate["gateAction"], "no_change")
        self.assertEqual(gate["finalAction"], "block")

    def test_gate_never_creates_edges(self) -> None:
        keep = {**_candidate(self.block_fixture, "f1"), "finalAction": "keep"}
        evidence = copy.deepcopy(self.block_fixture["evidence"])
        evidence["sourcePortConfirmed"] = True
        gate = evaluate_structural_line_candidate(keep, evidence)
        result = apply_structural_line_gate([self.flow], [keep], [gate])
        self.assertEqual(result["newEdges"], [])
        self.assertEqual(len(result["flows"]), 1)

    def test_official_strategy_and_stride_source_remain_legacy(self) -> None:
        result = evaluate_structural_line_gate([_candidate(self.block_fixture)], {self.block_fixture["id"]: self.block_fixture["evidence"]})
        self.assertEqual(result["officialStrategy"], "legacy")
        self.assertEqual(result["feedsStride"], "legacy_only")
        self.assertFalse(result["officialResultChanged"])


class StructuralLineArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(dir=ROOT / "data/results")
        cls.output = Path(cls._temporary.name) / "tl-struct-001a"
        cls.result = build_artifacts(cls.output)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def _load(self, name: str) -> dict:
        return json.loads((self.output / name).read_text(encoding="utf-8"))

    def test_builder_is_development_only_and_writes_seven_artifacts(self) -> None:
        self.assertEqual(self.result["split"], "development_tuning")
        self.assertEqual(len(self.result["artifacts"]), 7)
        self.assertTrue(all((ROOT / path).is_file() for path in self.result["artifacts"].values()))

    def test_base_ablation_matches_frozen_tl004f_metrics(self) -> None:
        metrics = self.result["baseMetrics"]
        self.assertEqual((metrics["predictedEdgeCount"], metrics["correctAdjacencyCount"], metrics["falsePositiveEdgeCount"], metrics["missedEdgeCount"]), (136, 52, 84, 19))
        self.assertAlmostEqual(metrics["edgeExistenceF1"], 0.5024154589371981)

    def test_final_metrics_preserve_all_correct_edges_and_exceed_f1_gate(self) -> None:
        metrics = self.result["finalMetrics"]
        self.assertEqual((metrics["predictedEdgeCount"], metrics["correctAdjacencyCount"], metrics["falsePositiveEdgeCount"], metrics["missedEdgeCount"]), (127, 52, 75, 19))
        self.assertGreaterEqual(round(metrics["edgeExistenceRecall"], 4), 0.7324)
        self.assertGreaterEqual(round(metrics["edgeExistenceF1"], 4), 0.5083)
        self.assertGreaterEqual(round(metrics["directionAccuracy"], 4), 0.8654)

    def test_nine_blocks_are_false_positives_and_no_false_block_exists(self) -> None:
        decisions = self._load("structural-line-decisions.json")
        blocked = [item for item in decisions["decisions"] if item["gateAction"] == "block"]
        self.assertEqual(len(blocked), 9)
        self.assertTrue(all(item["benchmarkStatus"] == "false_positive" for item in blocked))
        self.assertEqual(self.result["possibleFalseBlockCount"], 0)

    def test_all_ten_structural_cases_are_evaluated_without_id_rules(self) -> None:
        human = self._load("human-cases-comparison.json")
        structural = [item for item in human["cases"] if item["humanPrimaryCause"] == "structural_line"]
        self.assertEqual(len(structural), 10)
        self.assertEqual(sum(item["structuralGateActions"] == ["block"] for item in structural), 9)
        self.assertEqual(next(item for item in structural if item["caseId"] == "E07")["structuralGateActions"], ["review_only"])

    def test_priority_shortcuts_and_ambiguous_cases_are_preserved(self) -> None:
        human = self._load("human-cases-comparison.json")
        self.assertTrue(human["priorityShortcutsBlocked"])
        self.assertTrue(human["ambiguousCasesRemainReviewOnly"])

    def test_controls_pass_and_c04_is_not_autonomous(self) -> None:
        controls = self._load("control-cases-results.json")
        self.assertTrue(controls["allControlsPass"])
        self.assertFalse(controls["c04AutonomousRecoveryApplied"])
        self.assertEqual({item["caseId"] for item in controls["controls"]}, {f"C{index:02d}" for index in range(1, 8)})
        self.assertTrue(all(item["status"] == "PASS" for item in controls["controls"]))

    def test_default_remains_legacy_and_holdouts_are_not_executed(self) -> None:
        promotion = self._load("promotion-decision.json")
        report = self._load("test-report.json")
        self.assertEqual(promotion["defaultStrategy"], "legacy")
        self.assertFalse(promotion["defaultStrategyChanged"])
        self.assertTrue(promotion["shadowOnly"])
        self.assertEqual(promotion["holdoutExecutions"], 0)
        self.assertEqual(report["holdoutExecutions"], 0)

    def test_tl004a_to_f_integrity_passes(self) -> None:
        report = self._load("test-report.json")
        self.assertEqual(set(report["dependencyIntegrity"]), {f"TL-004{suffix}" for suffix in "ABCDEF"})
        self.assertTrue(all(item["status"] == "PASS" for item in report["dependencyIntegrity"].values()))

    def test_builder_refuses_to_overwrite_output(self) -> None:
        with self.assertRaises(FileExistsError):
            build_artifacts(self.output)


if __name__ == "__main__":
    unittest.main()
