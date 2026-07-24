from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from backend.shared_trunk_reconstruction import (
    TRUNK_CLASSIFICATIONS,
    compare_legacy_and_shadow_trunks,
    reconstruct_shared_trunks,
)
from scripts.build_tl004d_artifacts import build_artifacts


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads(
    (ROOT / "tests/fixtures/tl004d_shared_trunks.json").read_text(encoding="utf-8")
)["fixtures"]
C04 = json.loads(
    (ROOT / "data/fixtures/tl004d_c04_shared_trunk.json").read_text(encoding="utf-8")
)


def _fixtures() -> dict[str, dict]:
    return {item["id"]: item for item in FIXTURES}


def _analyze(fixture: dict) -> dict:
    return reconstruct_shared_trunks(
        fixture["segments"],
        fixture.get("components") or [],
        fixture.get("ports") or [],
        fixture.get("explicitJunctions") or [],
        barrier_component_ids=fixture.get("barrierComponentIds") or [],
        scale=float(fixture.get("scale", 1)),
        line_width=float(fixture.get("lineWidth", 1)),
    )


def _pairs(result: dict) -> set[tuple[str, str]]:
    return {(item["from"], item["to"]) for item in result["experimentalRelations"]}


class SharedTrunkFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = _fixtures()

    def test_all_twenty_required_fixtures_match_expected_relations(self) -> None:
        self.assertEqual(len(self.fixtures), 20)
        for fixture in self.fixtures.values():
            with self.subTest(fixture=fixture["id"]):
                result = _analyze(fixture)
                observed = _pairs(result)
                expected = {tuple(item) for item in fixture.get("expectedRelations") or []}
                forbidden = {tuple(item) for item in fixture.get("forbiddenRelations") or []}
                classifications = {item["classification"] for item in result["trunks"]}
                self.assertTrue(expected <= observed)
                self.assertFalse(observed & forbidden)
                self.assertTrue(
                    set(fixture.get("expectedClassifications") or []) <= classifications
                )

    def test_fan_out_preserves_all_destinations_without_peer_clique(self) -> None:
        result = _analyze(self.fixtures["fan_out_three_destinations"])
        self.assertEqual(_pairs(result), {("A", "B"), ("A", "C"), ("A", "D")})
        self.assertTrue({("B", "C"), ("C", "D"), ("D", "B")} <= {
            (item["from"], item["to"]) for item in result["preventedCliqueRelations"]
        })

    def test_fan_in_preserves_all_origins_without_peer_edges(self) -> None:
        result = _analyze(self.fixtures["simple_fan_in"])
        self.assertEqual(_pairs(result), {("A", "C"), ("B", "C")})
        self.assertNotIn(("A", "B"), _pairs(result))
        self.assertNotIn(("B", "A"), _pairs(result))

    def test_crossing_without_junction_never_switches_branch(self) -> None:
        self.assertEqual(
            _pairs(_analyze(self.fixtures["crossing_without_junction"])),
            {("A", "B"), ("C", "D")},
        )

    def test_near_disconnected_and_parallel_arms_are_not_paired(self) -> None:
        self.assertFalse(_pairs(_analyze(self.fixtures["near_without_contact"])))
        parallel = _analyze(self.fixtures["almost_parallel_arms"])
        self.assertFalse(_pairs(parallel))
        self.assertTrue(parallel["blockedLocalEvents"])
        self.assertTrue(
            all(item["classification"] == "invalid_branch_pairing" for item in parallel["blockedLocalEvents"])
        )

    def test_component_barrier_forces_adjacent_edges_and_blocks_shortcut(self) -> None:
        result = _analyze(self.fixtures["intermediate_component_barrier"])
        self.assertEqual(_pairs(result), {("A", "B"), ("B", "C")})
        self.assertNotIn(("A", "C"), _pairs(result))

    def test_ambiguous_direction_is_review_only(self) -> None:
        result = _analyze(self.fixtures["junction_without_direction"])
        self.assertFalse(result["experimentalRelations"])
        self.assertEqual(len(result["reviewOnlyRelations"]), 6)
        self.assertEqual(result["trunks"][0]["classification"], "ambiguous_shared_trunk")

    def test_order_scale_rotation_and_width_preserve_unequivocal_relations(self) -> None:
        base = _pairs(_analyze(self.fixtures["simple_fan_out"]))
        reordered = _pairs(_analyze(self.fixtures["different_segment_order"]))
        varied = _pairs(_analyze(self.fixtures["scaled_rotated_thick_fan_out"]))
        self.assertEqual(base, reordered)
        self.assertEqual(base, varied)

    def test_simultaneous_fan_in_and_fan_out_stay_separate(self) -> None:
        self.assertEqual(
            _pairs(_analyze(self.fixtures["simultaneous_fan_in_and_fan_out"])),
            {("A", "B"), ("A", "C"), ("D", "F"), ("E", "F")},
        )


class SharedTrunkContractTests(unittest.TestCase):
    def test_all_required_classifications_are_supported(self) -> None:
        self.assertEqual(
            set(TRUNK_CLASSIFICATIONS),
            {
                "valid_fan_in",
                "valid_fan_out",
                "shared_trunk",
                "ambiguous_shared_trunk",
                "invalid_branch_pairing",
                "insufficient_branch_evidence",
            },
        )
        insufficient = reconstruct_shared_trunks(
            [
                {"id": "s0", "start": [0, 0], "end": [10, 0]},
                {"id": "s1", "start": [10, 0], "end": [20, 0]},
            ],
            terminal_ports=[
                {"componentId": "A", "coordinates": [0, 0], "segmentId": "s0", "direction": "outgoing", "confidence": 1, "reviewed": True},
                {"componentId": "B", "coordinates": [20, 0], "segmentId": "s1", "direction": "incoming", "confidence": 1, "reviewed": True},
                {"componentId": "C", "coordinates": [10, 0], "segmentId": "s0", "direction": "unknown", "confidence": 0, "reviewed": True},
            ],
        )
        self.assertEqual(insufficient["trunks"][0]["classification"], "insufficient_branch_evidence")

    def test_trunk_contract_contains_traceability_and_directional_arms(self) -> None:
        trunk = _analyze(_fixtures()["simple_fan_out"])["trunks"][0]
        required = {
            "id",
            "segmentIds",
            "segmentProvenance",
            "eventIds",
            "junctionEventIds",
            "junctionArms",
            "inputArms",
            "outputArms",
            "unknownDirectionArms",
            "connectedPorts",
            "terminalComponents",
            "confidence",
            "evidence",
            "parameters",
            "allowedPairings",
            "blockedPairings",
        }
        self.assertTrue(required <= set(trunk))
        self.assertEqual({item["componentId"] for item in trunk["inputArms"]}, {"A"})
        self.assertEqual({item["componentId"] for item in trunk["outputArms"]}, {"B", "C"})

    def test_dependencies_reuse_tl004a_b_and_c(self) -> None:
        result = _analyze(_fixtures()["simple_fan_out"])
        self.assertEqual(
            result["dependencies"],
            [
                "backend/geometric_events.py",
                "backend/endpoint_validation.py",
                "backend/intersection_validation.py",
            ],
        )

    def test_inputs_are_not_mutated_and_repeated_output_is_identical(self) -> None:
        fixture = copy.deepcopy(_fixtures()["explicit_clique_prevention"])
        before = copy.deepcopy(fixture)
        first = _analyze(fixture)
        second = _analyze(fixture)
        self.assertEqual(fixture, before)
        self.assertFalse(first["inputMutation"])
        self.assertEqual(first, second)

    def test_legacy_comparison_preserves_edges_directions_and_stride_source(self) -> None:
        flows = [{"id": "f1", "from": "A", "to": "B", "directionEvidence": "arrow"}]
        fixture = _fixtures()["simple_fan_out"]
        comparison = compare_legacy_and_shadow_trunks(
            flows, fixture["segments"], terminal_ports=fixture["ports"]
        )
        self.assertEqual(comparison["officialFlows"], flows)
        self.assertFalse(comparison["officialFlowsChanged"])
        self.assertEqual(comparison["officialDirectionChanges"], 0)
        self.assertEqual(comparison["feedsStride"], "legacy_only")

    def test_c04_reviewed_trace_recovers_only_the_two_expected_shadow_edges(self) -> None:
        result = reconstruct_shared_trunks(C04["segments"], terminal_ports=C04["ports"])
        self.assertEqual(
            _pairs(result),
            {("app_service", "key_vault"), ("app_service", "storage")},
        )
        self.assertNotIn(("key_vault", "storage"), _pairs(result))
        self.assertNotIn(("storage", "key_vault"), _pairs(result))


class TL004DArtifactTests(unittest.TestCase):
    def test_builder_is_development_only_and_writes_eleven_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as directory:
            output = Path(directory) / "tl004d"
            result = build_artifacts(output)
            self.assertEqual(result["split"], "development_tuning")
            self.assertEqual(result["legacyCandidateCount"], 142)
            self.assertEqual(len(result["artifacts"]), 11)
            self.assertTrue(result["controlsPreserved"])
            self.assertTrue(result["c04Recovered"])
            self.assertTrue(result["requiredHumanCasesEvaluated"])
            self.assertTrue(all((ROOT / path).is_file() for path in result["artifacts"].values()))

    def test_artifacts_preserve_legacy_and_forbid_control_cliques(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as directory:
            output = Path(directory) / "tl004d"
            build_artifacts(output)
            legacy = json.loads((output / "legacy-shadow-comparison.json").read_text(encoding="utf-8"))
            controls = json.loads((output / "control-cases-results.json").read_text(encoding="utf-8"))
            clique = json.loads((output / "clique-prevention-report.json").read_text(encoding="utf-8"))
            self.assertEqual(legacy["legacyCandidateCount"], 142)
            self.assertEqual(legacy["officialEdgesChanged"], 0)
            self.assertEqual(legacy["officialDirectionChanges"], 0)
            self.assertEqual(legacy["feedsStride"], "legacy_only")
            self.assertTrue(legacy["legacySnapshot"]["checks"]["snapshotEquivalent"])
            self.assertTrue(controls["allControlsPreserved"])
            self.assertEqual(clique["controlCliqueViolationCount"], 0)
            self.assertEqual(clique["status"], "PASS")

    def test_human_cases_and_c04_are_explicitly_evaluated(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as directory:
            output = Path(directory) / "tl004d"
            build_artifacts(output)
            human = json.loads((output / "human-cases-comparison.json").read_text(encoding="utf-8"))
            fan = json.loads((output / "fan-in-fan-out-results.json").read_text(encoding="utf-8"))
            self.assertEqual({item["caseId"] for item in human["cases"]}, {"E06", "E13", "E15", "E16"})
            self.assertTrue(human["allRequiredCasesEvaluated"])
            self.assertTrue(fan["c04"]["reconstructedCorrectlyInSupervisedShadow"])
            self.assertFalse(fan["c04"]["autonomousRecoveryClaimed"])
            self.assertFalse(fan["c04"]["officialResultChanged"])

    def test_builder_refuses_to_overwrite_output(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as directory:
            output = Path(directory) / "tl004d"
            build_artifacts(output)
            with self.assertRaises(FileExistsError):
                build_artifacts(output)

    def test_builder_runs_as_direct_cli(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as directory:
            output = Path(directory) / "tl004d"
            result = subprocess.run(
                [sys.executable, "scripts/build_tl004d_artifacts.py", "--output", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["split"], "development_tuning")
            self.assertTrue((output / "tl004d-decision.json").is_file())


if __name__ == "__main__":
    unittest.main()
