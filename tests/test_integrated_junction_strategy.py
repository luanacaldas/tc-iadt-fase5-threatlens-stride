from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from backend.integrated_junction_strategy import (
    FINAL_ACTIONS,
    apply_integrated_decisions,
    evaluate_promotion,
    orchestrate_junction_aware,
    structural_metrics,
)
from scripts.build_tl004f_artifacts import STRATEGIES, build_artifacts


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads(
    (ROOT / "tests/fixtures/tl004f_integration.json").read_text(encoding="utf-8")
)["fixtures"]


def _run_fixture(fixture: dict) -> dict:
    return orchestrate_junction_aware(
        fixture.get("legacyFlows") or [],
        fixture.get("components") or [],
        adjacent_relations=fixture.get("adjacentRelations") or [],
        confirmed_direct_edges=fixture.get("confirmedDirectEdges") or [],
        human_confirmed_shortcuts=fixture.get("humanConfirmedShortcuts") or [],
        protected_edges=fixture.get("protectedEdges") or [],
        protected_candidate_ids=fixture.get("protectedCandidateIds") or [],
        structural_candidate_ids=fixture.get("structuralCandidateIds") or [],
        recovery_candidates=fixture.get("recoveryCandidates") or [],
    )


class IntegratedFixtureTests(unittest.TestCase):
    pass


def _make_fixture_test(fixture: dict):
    def test(self: IntegratedFixtureTests) -> None:
        result = _run_fixture(fixture)
        if "expectedAction" in fixture:
            self.assertEqual(result["candidateDecisions"][0]["finalAction"], fixture["expectedAction"])
        if "expectedRecoveryAction" in fixture:
            self.assertEqual(result["recoveryDecisions"][0]["finalAction"], fixture["expectedRecoveryAction"])
        if "expectedFrom" in fixture:
            self.assertEqual(result["candidateDecisions"][0]["proposedFrom"], fixture["expectedFrom"])
            self.assertEqual(result["candidateDecisions"][0]["proposedTo"], fixture["expectedTo"])
        if "expectedConflict" in fixture:
            self.assertEqual(bool(result["moduleConflicts"]), fixture["expectedConflict"])
        self.assertFalse(result["officialFlowsChanged"])
        self.assertEqual(result["feedsStride"], "legacy_only")

    return test


for _fixture in FIXTURES:
    setattr(IntegratedFixtureTests, f"test_fixture_{_fixture['id']}", _make_fixture_test(_fixture))


class IntegratedStrategyContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.flow = {"id": "f1", "from": "A", "to": "B", "pathPoints": [[2, 0], [18, 0]], "directionConfidence": 1}
        self.components = [{"id": "A", "bbox": [0, -2, 2, 2]}, {"id": "B", "bbox": [18, -2, 22, 2]}]

    def _decision(self, action: str, **updates) -> dict:
        decision = {
            "candidateId": "f1",
            "finalAction": action,
            "proposedFrom": "A",
            "proposedTo": "B",
            "adjacentRelations": [],
        }
        decision.update(updates)
        return decision

    def test_precedence_and_execution_order_are_deterministic(self) -> None:
        fixture = next(item for item in FIXTURES if item["id"] == "transitive_block_precedes_redirect")
        result = _run_fixture(fixture)
        self.assertEqual(result["executionOrder"], ["TL-004A", "TL-004B", "TL-004C", "TL-004D", "TL-004E", "consolidation", "human_controls"])
        self.assertEqual(result["candidateDecisions"][0]["finalAction"], "block")

    def test_every_candidate_has_exactly_one_supported_final_action(self) -> None:
        result = orchestrate_junction_aware([self.flow], self.components)
        self.assertEqual(len(result["candidateDecisions"]), 1)
        self.assertIn(result["candidateDecisions"][0]["finalAction"], FINAL_ACTIONS)

    def test_inputs_are_not_mutated(self) -> None:
        flows, components = copy.deepcopy([self.flow]), copy.deepcopy(self.components)
        before = copy.deepcopy((flows, components))
        result = orchestrate_junction_aware(flows, components)
        self.assertEqual((flows, components), before)
        self.assertFalse(result["inputMutation"])

    def test_execution_is_deterministic(self) -> None:
        first = orchestrate_junction_aware([self.flow], self.components)
        second = orchestrate_junction_aware([self.flow], self.components)
        self.assertEqual(first, second)

    def test_input_order_does_not_change_decisions(self) -> None:
        other = {"id": "f2", "from": "B", "to": "A", "pathPoints": [[18, 1], [2, 1]], "directionConfidence": 1}
        first = orchestrate_junction_aware([self.flow, other], self.components)
        second = orchestrate_junction_aware([other, self.flow], list(reversed(self.components)))
        self.assertEqual(first["candidateDecisions"], second["candidateDecisions"])

    def test_keep_preserves_edge_and_direction(self) -> None:
        result = apply_integrated_decisions([self.flow], [self._decision("keep")])
        self.assertEqual([(item["from"], item["to"]) for item in result["flows"]], [("A", "B")])

    def test_redirect_replaces_both_endpoints(self) -> None:
        result = apply_integrated_decisions([self.flow], [self._decision("redirect", proposedFrom="C", proposedTo="D")])
        self.assertEqual((result["flows"][0]["from"], result["flows"][0]["to"]), ("C", "D"))

    def test_block_removes_edge(self) -> None:
        result = apply_integrated_decisions([self.flow], [self._decision("block")])
        self.assertEqual(result["flows"], [])

    def test_decompose_emits_only_adjacent_relations(self) -> None:
        decision = self._decision("decompose", adjacentRelations=[{"from": "A", "to": "X"}, {"from": "X", "to": "B"}])
        result = apply_integrated_decisions([self.flow], [decision])
        self.assertEqual([(item["from"], item["to"]) for item in result["flows"]], [("A", "X"), ("X", "B")])
        self.assertNotIn(("A", "B"), [(item["from"], item["to"]) for item in result["flows"]])

    def test_autonomous_recover_adds_only_supported_edge(self) -> None:
        recovery = {"id": "r1", "finalAction": "recover", "proposedFrom": "C", "proposedTo": "D", "supervised": False}
        result = apply_integrated_decisions([self.flow], [self._decision("keep")], [recovery])
        self.assertEqual({(item["from"], item["to"]) for item in result["flows"]}, {("A", "B"), ("C", "D")})

    def test_review_only_does_not_change_experimental_edge(self) -> None:
        result = apply_integrated_decisions([self.flow], [self._decision("review_only", proposedFrom="C", proposedTo="D")])
        self.assertEqual((result["flows"][0]["from"], result["flows"][0]["to"]), ("A", "B"))
        self.assertEqual(result["reviewOnlyAppliedCount"], 0)

    def test_supervised_recovery_is_not_applied(self) -> None:
        recovery = {"id": "r1", "finalAction": "recover", "proposedFrom": "C", "proposedTo": "D", "supervised": True}
        result = apply_integrated_decisions([self.flow], [self._decision("keep")], [recovery])
        self.assertEqual(len(result["flows"]), 1)

    def test_duplicate_edges_are_removed_without_creating_a_clique(self) -> None:
        recovery = {"id": "r1", "finalAction": "recover", "proposedFrom": "A", "proposedTo": "B", "supervised": False}
        result = apply_integrated_decisions([self.flow], [self._decision("keep")], [recovery])
        self.assertEqual(len(result["flows"]), 1)
        self.assertEqual(len(result["deduplicatedEdges"]), 1)

    def test_protected_fan_in_is_preserved(self) -> None:
        flows = [{"id": "f1", "from": "A", "to": "X"}, {"id": "f2", "from": "B", "to": "X"}]
        decisions = [self._decision("keep", candidateId="f1"), self._decision("keep", candidateId="f2")]
        result = apply_integrated_decisions(flows, decisions)
        self.assertEqual({(item["from"], item["to"]) for item in result["flows"]}, {("A", "X"), ("B", "X")})

    def test_protected_fan_out_is_preserved(self) -> None:
        flows = [{"id": "f1", "from": "X", "to": "A"}, {"id": "f2", "from": "X", "to": "B"}]
        decisions = [self._decision("keep", candidateId="f1"), self._decision("keep", candidateId="f2")]
        result = apply_integrated_decisions(flows, decisions)
        self.assertEqual({(item["from"], item["to"]) for item in result["flows"]}, {("X", "A"), ("X", "B")})

    def test_structural_provenance_forces_review_only(self) -> None:
        flow = {**self.flow, "provenance": "inventory:E16"}
        result = orchestrate_junction_aware([flow], self.components, structural_candidate_ids=["inventory:E16"])
        self.assertEqual(result["candidateDecisions"][0]["finalAction"], "review_only")
        self.assertTrue(result["candidateDecisions"][0]["structuralLineCase"])

    def test_metric_calculation_matches_known_graph(self) -> None:
        expected = [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}]
        predicted = [{"from": "A", "to": "B"}, {"from": "A", "to": "C"}]
        metrics = structural_metrics(expected, predicted)
        self.assertEqual(metrics["predictedEdgeCount"], 2)
        self.assertEqual(metrics["correctAdjacencyCount"], 1)
        self.assertEqual(metrics["falsePositiveEdgeCount"], 1)
        self.assertEqual(metrics["missedEdgeCount"], 1)
        self.assertEqual(metrics["edgeExistenceF1"], 0.5)

    def test_promotion_passes_only_when_every_check_and_evidence_pass(self) -> None:
        metrics = {"falsePositiveEdgeCount": 81, "correctAdjacencyCount": 52, "missedEdgeCount": 19, "edgeExistenceRecall": 0.74, "edgeExistenceF1": 0.51, "directionAccuracy": 0.87}
        result = evaluate_promotion(metrics, controls_pass=True, correct_directions_changed=0, human_true_positives_blocked=0, possible_false_blocks=0, review_only_applied=0, gate_status="PASS", verifier_status="PASS", v12_status="PASS", tests_pass=True, evidence_sufficient=True)
        self.assertTrue(result["allCriteriaPassed"])
        self.assertEqual(result["recommendation"], "eligible_for_controlled_promotion")

    def test_partial_promotion_criteria_are_rejected(self) -> None:
        metrics = {"falsePositiveEdgeCount": 89, "correctAdjacencyCount": 52, "missedEdgeCount": 19, "edgeExistenceRecall": 0.74, "edgeExistenceF1": 0.51, "directionAccuracy": 0.87}
        result = evaluate_promotion(metrics, controls_pass=True, correct_directions_changed=0, human_true_positives_blocked=0, possible_false_blocks=0, review_only_applied=0, gate_status="PASS", verifier_status="PASS", v12_status="PASS", tests_pass=True, evidence_sufficient=True)
        self.assertFalse(result["allCriteriaPassed"])
        self.assertEqual(result["recommendation"], "not_eligible_metrics")


class TL004FArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(dir=ROOT / "data/results")
        cls.output = Path(cls._temporary.name) / "tl004f"
        cls.result = build_artifacts(cls.output)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def _load(self, name: str) -> dict:
        return json.loads((self.output / name).read_text(encoding="utf-8"))

    def test_builder_is_development_only_and_writes_seventeen_artifacts(self) -> None:
        self.assertEqual(self.result["split"], "development_tuning")
        self.assertEqual(len(self.result["artifacts"]), 17)
        self.assertTrue(all((ROOT / path).is_file() for path in self.result["artifacts"].values()))

    def test_baseline_snapshot_is_exact_and_official_strategy_is_legacy(self) -> None:
        legacy = self._load("legacy-shadow-comparison.json")
        metrics = self.result["legacyMetrics"]
        self.assertEqual((metrics["predictedEdgeCount"], metrics["correctAdjacencyCount"], metrics["falsePositiveEdgeCount"], metrics["missedEdgeCount"], metrics["reversedEdgeCount"]), (142, 52, 90, 19, 7))
        self.assertEqual(legacy["officialStrategy"], "legacy")
        self.assertEqual(legacy["officialEdgesChanged"], 0)
        self.assertEqual(legacy["feedsStride"], "legacy_only")

    def test_all_required_ablations_are_compared(self) -> None:
        report = self._load("ablation-results.json")
        self.assertEqual(report["ablationCount"], 8)
        self.assertEqual({item["strategy"] for item in report["ablations"]}, set(STRATEGIES))

    def test_all_twenty_seven_human_cases_are_present(self) -> None:
        report = self._load("human-cases-comparison.json")
        self.assertEqual(report["caseCount"], 27)
        self.assertEqual({item["caseId"] for item in report["cases"]}, {f"E{index:02d}" for index in range(1, 21)} | {f"C{index:02d}" for index in range(1, 8)})

    def test_controls_c01_to_c07_pass_and_c04_stays_supervised(self) -> None:
        report = self._load("control-cases-results.json")
        index = {item["caseId"]: item for item in report["controls"]}
        self.assertTrue(report["allControlsPass"])
        self.assertEqual(set(index), {f"C{value:02d}" for value in range(1, 8)})
        self.assertEqual(index["C04"]["experimentalResult"], "supervised_shadow_recovery")

    def test_experimental_metrics_are_computed_but_not_promoted(self) -> None:
        metrics = self._load("structural-metrics-comparison.json")
        decision = self._load("promotion-decision.json")
        self.assertIn("junctionAwareFull", metrics["official"])
        self.assertFalse(decision["defaultStrategyChanged"])
        self.assertEqual(decision["defaultStrategy"], "legacy")

    def test_holdouts_and_structural_task_are_forbidden(self) -> None:
        decision = self._load("tl004f-decision.json")
        tests = self._load("test-report.json")
        self.assertEqual(decision["criteria"]["holdoutExecutions"], 0)
        self.assertFalse(decision["structuralTaskStarted"])
        self.assertEqual(tests["validation"]["holdoutExecutions"], 0)

    def test_builder_refuses_to_overwrite_output(self) -> None:
        with self.assertRaises(FileExistsError):
            build_artifacts(self.output)


if __name__ == "__main__":
    unittest.main()
