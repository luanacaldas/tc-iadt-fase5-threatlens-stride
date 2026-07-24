from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from backend.intersection_validation import (
    INTERSECTION_CLASSIFICATIONS,
    classify_intersections,
    compare_legacy_and_shadow_intersections,
)
from scripts.build_tl004c_artifacts import build_artifacts


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads(
    (ROOT / "tests/fixtures/tl004c_intersections.json").read_text(encoding="utf-8")
)["fixtures"]


def _fixtures() -> dict[str, dict]:
    return {item["id"]: item for item in FIXTURES}


def _classify(fixture: dict) -> dict:
    return classify_intersections(
        fixture["segments"],
        fixture.get("components") or [],
        fixture.get("explicitJunctions") or [],
        scale=float(fixture.get("scale", 1)),
        line_width=float(fixture.get("lineWidth", 1)),
    )


class IntersectionFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = _fixtures()

    def test_all_sixteen_required_fixtures_match_expected_classification(self) -> None:
        self.assertEqual(len(self.fixtures), 16)
        for fixture in self.fixtures.values():
            with self.subTest(fixture=fixture["id"]):
                result = _classify(fixture)
                if "expectedEventCount" in fixture:
                    self.assertEqual(result["eventCount"], fixture["expectedEventCount"])
                else:
                    self.assertIn(
                        fixture["expectedClassification"],
                        [event["classification"] for event in result["events"]],
                    )

    def test_x_without_marker_blocks_only_transverse_pairs(self) -> None:
        event = _classify(self.fixtures["x_without_marker"])["events"][0]
        self.assertEqual(event["classification"], "crossing_without_junction")
        self.assertEqual(len(event["allowedBranchPairs"]), 2)
        self.assertEqual(len(event["blockedTransversePairs"]), 4)
        self.assertFalse(event["visualJunctionMarker"]["exists"])

    def test_x_with_explicit_marker_allows_local_connectivity(self) -> None:
        event = _classify(self.fixtures["x_with_explicit_marker"])["events"][0]
        self.assertEqual(event["classification"], "explicit_junction")
        self.assertEqual(len(event["allowedBranchPairs"]), 6)
        self.assertFalse(event["blockedTransversePairs"])
        self.assertTrue(event["visualJunctionMarker"]["qualified"])

    def test_incomplete_marker_is_review_only(self) -> None:
        event = _classify(self.fixtures["x_with_ambiguous_marker"])["events"][0]
        self.assertEqual(event["classification"], "ambiguous_intersection")
        self.assertTrue(event["reviewOnly"])
        self.assertEqual(event["connectivityDecision"], "review_only")
        self.assertFalse(event["officialEligible"])

    def test_t_and_y_preserve_all_three_observed_arms(self) -> None:
        for fixture_id in ("t_bifurcation", "y_bifurcation"):
            with self.subTest(fixture=fixture_id):
                event = _classify(self.fixtures[fixture_id])["events"][0]
                self.assertEqual(event["classification"], "bifurcation")
                self.assertEqual(event["geometricDegree"], 3)
                self.assertEqual(len(event["allowedBranchPairs"]), 3)
                self.assertTrue(event["decompositionDeferred"])

    def test_continuation_and_elbow_are_distinct(self) -> None:
        continuation = _classify(self.fixtures["fragmented_continuation"])["events"][0]
        elbow = _classify(self.fixtures["elbow"])["events"][0]
        self.assertEqual(continuation["classification"], "continuation")
        self.assertEqual(elbow["classification"], "elbow")

    def test_parallel_lines_are_not_fused_and_near_non_contact_creates_no_event(self) -> None:
        parallel = _classify(self.fixtures["near_parallel_lines"])
        self.assertTrue(parallel["events"])
        self.assertTrue(
            all(event["classification"] == "ambiguous_intersection" for event in parallel["events"])
        )
        self.assertTrue(all(not event["allowedBranchPairs"] for event in parallel["events"]))
        self.assertEqual(_classify(self.fixtures["near_without_contact"])["eventCount"], 0)

    def test_non_orthogonal_crossing_preserves_collinear_continuities(self) -> None:
        event = _classify(self.fixtures["non_orthogonal_crossing"])["events"][0]
        self.assertEqual(event["classification"], "crossing_without_junction")
        self.assertEqual(len(event["collinearPairs"]), 2)

    def test_four_arms_with_one_collinear_pair_remain_ambiguous(self) -> None:
        event = _classify(self.fixtures["four_arms_one_collinear_pair"])["events"][0]
        self.assertEqual(event["classification"], "ambiguous_intersection")
        self.assertEqual(len(event["collinearPairs"]), 1)
        self.assertTrue(event["reviewOnly"])

    def test_component_boundary_port_and_barrier_context_are_reused(self) -> None:
        for fixture_id in (
            "crossing_near_component_boundary",
            "junction_connected_to_port",
            "crossing_on_component_barrier",
        ):
            fixture = self.fixtures[fixture_id]
            event = next(
                item
                for item in _classify(fixture)["events"]
                if item["classification"] == fixture["expectedClassification"]
            )
            self.assertTrue(event["componentContext"][fixture["expectedContext"]])

    def test_segment_order_is_deterministic(self) -> None:
        original = _classify(self.fixtures["x_without_marker"])
        reordered = _classify(self.fixtures["different_segment_order"])
        self.assertEqual(original["events"], reordered["events"])

    def test_scale_rotation_and_line_width_keep_unequivocal_classification(self) -> None:
        base = _classify(self.fixtures["x_without_marker"])["events"][0]
        varied = _classify(self.fixtures["scaled_rotated_thick_crossing"])["events"][0]
        self.assertEqual(base["classification"], varied["classification"])
        self.assertEqual(len(base["allowedBranchPairs"]), len(varied["allowedBranchPairs"]))


class IntersectionContractTests(unittest.TestCase):
    def test_every_classification_is_representable(self) -> None:
        observed = {
            event["classification"]
            for fixture in FIXTURES
            for event in _classify(fixture)["events"]
        }
        self.assertEqual(observed, set(INTERSECTION_CLASSIFICATIONS))

    def test_decision_contract_contains_required_traceability(self) -> None:
        event = _classify(_fixtures()["x_without_marker"])["events"][0]
        required = {
            "id",
            "coordinates",
            "arms",
            "angles",
            "collinearPairs",
            "geometricDegree",
            "localPixelSupport",
            "visualJunctionMarker",
            "segmentProvenance",
            "confidence",
            "reasons",
            "parameters",
        }
        self.assertTrue(required.issubset(event))

    def test_inputs_are_not_mutated(self) -> None:
        fixture = copy.deepcopy(_fixtures()["x_with_ambiguous_marker"])
        before = copy.deepcopy(fixture)
        result = _classify(fixture)
        self.assertEqual(fixture, before)
        self.assertFalse(result["inputMutation"])

    def test_repeated_classification_is_identical(self) -> None:
        fixture = _fixtures()["t_bifurcation"]
        self.assertEqual(_classify(fixture), _classify(fixture))

    def test_legacy_comparison_preserves_flows_and_directions(self) -> None:
        flows = [{"id": "f1", "from": "a", "to": "b", "directionEvidence": "arrow"}]
        comparison = compare_legacy_and_shadow_intersections(
            flows, _fixtures()["x_without_marker"]["segments"]
        )
        self.assertEqual(comparison["officialFlows"], flows)
        self.assertFalse(comparison["officialFlowsChanged"])
        self.assertEqual(comparison["officialDirectionChanges"], 0)
        self.assertEqual(comparison["feedsStride"], "legacy_only")

    def test_low_pixel_support_keeps_bifurcation_in_review(self) -> None:
        segments = [
            {"id": "a", "start": [-10, 0], "end": [0, 0], "pixelSupport": 0.1},
            {"id": "b", "start": [0, 0], "end": [10, 0], "pixelSupport": 0.1},
            {"id": "c", "start": [0, 0], "end": [0, 10], "pixelSupport": 0.1},
        ]
        event = classify_intersections(segments)["events"][0]
        self.assertEqual(event["classification"], "ambiguous_intersection")
        self.assertTrue(event["reviewOnly"])


class TL004CArtifactTests(unittest.TestCase):
    def test_builder_is_development_only_and_writes_nine_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as directory:
            output = Path(directory) / "tl004c"
            result = build_artifacts(output)
            self.assertEqual(result["split"], "development_tuning")
            self.assertEqual(result["legacyCandidateCount"], 142)
            self.assertTrue(result["requiredCasesEvaluated"])
            self.assertTrue(result["controlsPreserved"])
            self.assertEqual(len(result["artifacts"]), 9)
            self.assertTrue(all((ROOT / path).is_file() for path in result["artifacts"].values()))

    def test_artifacts_keep_official_flows_and_controls_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as directory:
            output = Path(directory) / "tl004c"
            build_artifacts(output)
            legacy = json.loads((output / "legacy-shadow-comparison.json").read_text(encoding="utf-8"))
            controls = json.loads((output / "control-cases-results.json").read_text(encoding="utf-8"))
            self.assertEqual(legacy["officialEdgesChanged"], 0)
            self.assertEqual(legacy["officialDirectionChanges"], 0)
            self.assertTrue(controls["allControlsPreserved"])
            self.assertTrue(all(item["preserved"] for item in controls["controls"]))

    def test_builder_refuses_to_overwrite_output(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as directory:
            output = Path(directory) / "tl004c"
            build_artifacts(output)
            with self.assertRaises(FileExistsError):
                build_artifacts(output)

    def test_builder_runs_as_direct_cli(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as directory:
            output = Path(directory) / "tl004c"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/build_tl004c_artifacts.py",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["split"], "development_tuning")
            self.assertTrue((output / "tl004c-decision.json").is_file())


if __name__ == "__main__":
    unittest.main()
