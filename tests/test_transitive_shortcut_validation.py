from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from backend.transitive_shortcut_validation import (
    SHORTCUT_CLASSIFICATIONS,
    classify_transitive_shortcuts,
    compare_legacy_and_shadow_shortcuts,
)
from scripts.build_tl004e_artifacts import build_artifacts


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads(
    (ROOT / "tests/fixtures/tl004e_transitive_shortcuts.json").read_text(encoding="utf-8")
)["fixtures"]


def _fixtures() -> dict[str, dict]:
    return {item["id"]: item for item in FIXTURES}


def _analyze(fixture: dict) -> dict:
    return classify_transitive_shortcuts(
        [fixture["candidate"]],
        fixture["components"],
        adjacent_relations=fixture.get("adjacentRelations") or [],
        confirmed_direct_edges=fixture.get("confirmedDirectEdges") or [],
        human_confirmed_shortcuts=fixture.get("humanConfirmedShortcuts") or [],
        scale=float(fixture.get("scale", 1)),
        line_width=float(fixture.get("lineWidth", 1)),
    )


class TransitiveShortcutFixtureTests(unittest.TestCase):
    fixtures = _fixtures()


def _make_fixture_test(fixture_id: str):
    def test(self: TransitiveShortcutFixtureTests) -> None:
        fixture = self.fixtures[fixture_id]
        decision = _analyze(fixture)["decisions"][0]
        self.assertEqual(decision["classification"], fixture["expectedClassification"])
        self.assertEqual(decision["shadowAction"], fixture["expectedAction"])
        self.assertFalse(decision["officialResultChanged"])
        self.assertFalse(decision["officialDirectionChanged"])

    return test


for _fixture_id in sorted(_fixtures()):
    setattr(
        TransitiveShortcutFixtureTests,
        f"test_fixture_{_fixture_id}",
        _make_fixture_test(_fixture_id),
    )


class TransitiveShortcutContractTests(unittest.TestCase):
    def test_exactly_twenty_required_fixtures_exist(self) -> None:
        self.assertEqual(len(FIXTURES), 20)

    def test_every_required_classification_is_represented(self) -> None:
        observed = {
            _analyze(fixture)["decisions"][0]["classification"]
            for fixture in FIXTURES
        }
        self.assertEqual(observed, set(SHORTCUT_CLASSIFICATIONS))

    def test_false_shortcut_is_blocked_but_independent_direct_edge_is_kept(self) -> None:
        fixtures = _fixtures()
        blocked = _analyze(fixtures["false_shortcut_in_chain"])["decisions"][0]
        kept = _analyze(fixtures["valid_independent_direct_edge"])["decisions"][0]
        self.assertEqual((blocked["classification"], blocked["shadowAction"]), ("transitive_shortcut", "block"))
        self.assertEqual((kept["classification"], kept["shadowAction"]), ("direct_edge_confirmed", "keep"))
        self.assertTrue(kept["directEdgeEvidence"]["confirmed"])

    def test_adjacent_relations_and_fan_in_out_are_never_suppressed(self) -> None:
        for fixture_id in ("simple_chain_adjacent_edge", "valid_fan_in", "valid_fan_out", "shared_trunk_without_clique"):
            with self.subTest(fixture=fixture_id):
                decision = _analyze(_fixtures()[fixture_id])["decisions"][0]
                self.assertEqual(decision["classification"], "adjacent_relation")
                self.assertEqual(decision["shadowAction"], "keep")

    def test_ambiguous_and_opposite_direction_paths_remain_review_only(self) -> None:
        fixtures = _fixtures()
        ambiguous = _analyze(fixtures["multiple_indirect_paths"])["decisions"][0]
        opposite = _analyze(fixtures["opposite_direction_indirect_path"])["decisions"][0]
        self.assertEqual(ambiguous["shadowAction"], "review")
        self.assertEqual(opposite["classification"], "insufficient_evidence")
        self.assertEqual(opposite["shadowAction"], "review")

    def test_segment_and_component_order_do_not_change_decision(self) -> None:
        fixtures = _fixtures()
        original = _analyze(fixtures["false_shortcut_in_chain"])["decisions"][0]
        reordered = _analyze(fixtures["different_segment_order"])["decisions"][0]
        self.assertEqual(original["classification"], reordered["classification"])
        self.assertEqual(original["shadowAction"], reordered["shadowAction"])
        self.assertEqual(original["intermediateComponents"], reordered["intermediateComponents"])

    def test_inputs_are_immutable_and_execution_is_deterministic(self) -> None:
        fixture = copy.deepcopy(_fixtures()["immutable_input_case"])
        before = copy.deepcopy(fixture)
        first = _analyze(fixture)
        second = _analyze(fixture)
        self.assertEqual(fixture, before)
        self.assertFalse(first["inputMutation"])
        self.assertEqual(first, second)

    def test_decision_contract_has_all_traceability_fields(self) -> None:
        decision = _analyze(_fixtures()["false_shortcut_in_chain"])["decisions"][0]
        required = {
            "from",
            "to",
            "completePath",
            "intermediateComponents",
            "touchedPorts",
            "barriers",
            "adjacentRelations",
            "directEdgeEvidence",
            "arrowheadEvidence",
            "sharedSegmentEvidence",
            "trunkIds",
            "junctionEventIds",
            "confidence",
            "reasons",
            "shadowAction",
        }
        self.assertTrue(required <= set(decision))

    def test_dependencies_reuse_all_prior_tl004_modules(self) -> None:
        result = _analyze(_fixtures()["false_shortcut_in_chain"])
        self.assertEqual(
            result["dependencies"],
            [
                "backend/geometric_events.py",
                "backend/endpoint_validation.py",
                "backend/intersection_validation.py",
                "backend/shared_trunk_reconstruction.py",
            ],
        )

    def test_legacy_comparison_never_changes_edges_direction_or_stride_source(self) -> None:
        fixture = _fixtures()["false_shortcut_in_chain"]
        flow = copy.deepcopy(fixture["candidate"])
        comparison = compare_legacy_and_shadow_shortcuts(
            [flow],
            fixture["components"],
            adjacent_relations=fixture["adjacentRelations"],
        )
        self.assertEqual(comparison["officialFlows"], [flow])
        self.assertFalse(comparison["officialFlowsChanged"])
        self.assertEqual(comparison["officialDirectionChanges"], 0)
        self.assertEqual(comparison["feedsStride"], "legacy_only")


class TL004EArtifactTests(unittest.TestCase):
    def test_builder_is_development_only_and_writes_ten_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as directory:
            output = Path(directory) / "tl004e"
            result = build_artifacts(output)
            self.assertEqual(result["split"], "development_tuning")
            self.assertEqual(result["legacyCandidateCount"], 142)
            self.assertEqual(len(result["artifacts"]), 10)
            self.assertTrue(result["priorityCasesCorrected"])
            self.assertTrue(result["controlsPreserved"])
            self.assertEqual(result["possibleFalseBlockCount"], 0)
            self.assertTrue(all((ROOT / path).is_file() for path in result["artifacts"].values()))

    def test_priority_human_cases_are_blocked_and_e16_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as directory:
            output = Path(directory) / "tl004e"
            build_artifacts(output)
            human = json.loads((output / "human-cases-comparison.json").read_text(encoding="utf-8"))
            priority = {item["caseId"]: item for item in human["cases"] if item["priority"]}
            self.assertEqual(set(priority), {"E03", "E10", "E14"})
            self.assertTrue(all(item["correctedInShadow"] for item in priority.values()))
            self.assertEqual(human["excludedCases"], ["E16"])
            self.assertNotIn("E16", {item["caseId"] for item in human["cases"]})

    def test_controls_and_c04_supervised_boundary_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as directory:
            output = Path(directory) / "tl004e"
            build_artifacts(output)
            controls = json.loads((output / "control-cases-results.json").read_text(encoding="utf-8"))
            index = {item["caseId"]: item for item in controls["controls"]}
            self.assertTrue(controls["allControlsPreserved"])
            self.assertTrue(all(not item["blockedRequiredEdges"] for item in index.values()))
            self.assertFalse(index["C04"]["c04AutonomousRecoveryClaimed"])
            self.assertTrue(index["C04"]["c04SupervisedRecovery"]["reconstructedCorrectlyInSupervisedShadow"])

    def test_legacy_snapshot_direct_edges_and_directions_are_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as directory:
            output = Path(directory) / "tl004e"
            build_artifacts(output)
            legacy = json.loads((output / "legacy-shadow-comparison.json").read_text(encoding="utf-8"))
            direct = json.loads((output / "direct-edge-evidence.json").read_text(encoding="utf-8"))
            self.assertEqual(legacy["legacyCandidateCount"], 142)
            self.assertEqual(legacy["officialEdgesChanged"], 0)
            self.assertEqual(legacy["officialDirectionChanges"], 0)
            self.assertEqual(legacy["feedsStride"], "legacy_only")
            self.assertTrue(legacy["legacySnapshot"]["checks"]["snapshotEquivalent"])
            self.assertEqual(direct["possibleFalseBlockCount"], 0)

    def test_builder_refuses_to_overwrite_output(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as directory:
            output = Path(directory) / "tl004e"
            build_artifacts(output)
            with self.assertRaises(FileExistsError):
                build_artifacts(output)

    def test_builder_runs_as_direct_cli(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as directory:
            output = Path(directory) / "tl004e"
            result = subprocess.run(
                [sys.executable, "scripts/build_tl004e_artifacts.py", "--output", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["split"], "development_tuning")
            self.assertTrue((output / "tl004e-decision.json").is_file())


if __name__ == "__main__":
    unittest.main()
