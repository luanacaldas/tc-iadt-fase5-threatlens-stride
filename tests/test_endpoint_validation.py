from __future__ import annotations

import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from backend.endpoint_validation import (
    analyze_flow_candidate,
    build_component_contact_catalog,
    compare_legacy_and_shadow,
)
from scripts.build_tl004b_artifacts import _normalize_validation_status, build_artifacts


ROOT = Path(__file__).resolve().parents[1]


def _components() -> list[dict]:
    return [
        {"id": "a", "bbox": [0, 40, 20, 60]},
        {"id": "b", "bbox": [40, 40, 60, 60]},
        {"id": "c", "bbox": [80, 40, 100, 60]},
    ]


def _flow(source: str = "a", destination: str = "c", points=None) -> dict:
    return {
        "id": "flow-test",
        "from": source,
        "to": destination,
        "protocol": "TLS",
        "pathPoints": points or [[10, 50], [90, 50]],
        "directionEvidence": "test",
    }


def _endpoint(result: dict, role: str) -> dict:
    return next(item for item in result["endpointDecisions"] if item["role"] == role)


class EndpointValidationTests(unittest.TestCase):
    def test_source_endpoint_contact_is_confirmed(self) -> None:
        result = analyze_flow_candidate(_flow(points=[[10, 50], [30, 50]]), _components(), flow_strategy="junction_aware")
        self.assertEqual(_endpoint(result, "source")["classification"], "confirmed_contact")

    def test_destination_endpoint_contact_is_confirmed(self) -> None:
        result = analyze_flow_candidate(_flow(points=[[70, 50], [90, 50]]), _components(), flow_strategy="junction_aware")
        self.assertEqual(_endpoint(result, "destination")["classification"], "confirmed_contact")

    def test_nearby_endpoint_without_contact_is_proximity_only(self) -> None:
        result = analyze_flow_candidate(
            _flow(points=[[22, 38], [78, 38]]), _components(), flow_strategy="junction_aware"
        )
        self.assertEqual(_endpoint(result, "source")["classification"], "proximity_only")

    def test_endpoint_contacting_wrong_component_is_redirected(self) -> None:
        result = analyze_flow_candidate(
            _flow(points=[[50, 50], [90, 50]]), _components(), flow_strategy="junction_aware"
        )
        self.assertEqual(_endpoint(result, "source")["classification"], "wrong_component_contact")
        self.assertEqual(result["experimentalFlow"]["from"], "b")

    def test_collapsed_contact_can_keep_nearby_declared_destination(self) -> None:
        components = [
            {"id": "declared_source", "bbox": [0, 40, 20, 60]},
            {"id": "touched_source", "bbox": [40, 40, 80, 60]},
            {"id": "declared_destination", "bbox": [100, 40, 120, 60]},
        ]
        flow = _flow(
            source="declared_source",
            destination="declared_destination",
            points=[[50, 50], [82, 50]],
        )
        result = analyze_flow_candidate(flow, components, flow_strategy="junction_aware")

        self.assertEqual(result["edgeAction"], "redirected")
        self.assertEqual(
            (result["experimentalFlow"]["from"], result["experimentalFlow"]["to"]),
            ("touched_source", "declared_destination"),
        )
        self.assertIn("destination_approach_after_wrong_source_contact", result["reasonCodes"])

    def test_reversed_path_points_are_only_reversed_internally(self) -> None:
        flow = _flow(points=[[90, 50], [10, 50]])
        result = analyze_flow_candidate(flow, _components(), flow_strategy="junction_aware")
        self.assertTrue(result["pathPointsReversed"])
        self.assertEqual(flow["pathPoints"], [[90, 50], [10, 50]])
        self.assertEqual(_endpoint(result, "source")["classification"], "confirmed_contact")

    def test_intermediate_component_is_recorded_as_first_barrier(self) -> None:
        result = analyze_flow_candidate(_flow(), _components(), flow_strategy="junction_aware")
        self.assertEqual(result["firstIntermediateBarrier"]["componentId"], "b")
        self.assertIn("component_barrier_stops_path", result["reasonCodes"])

    def test_path_crossing_component_is_redirected_to_first_barrier(self) -> None:
        result = analyze_flow_candidate(_flow(), _components(), flow_strategy="junction_aware")
        self.assertEqual(result["edgeAction"], "redirected")
        self.assertEqual(
            (result["experimentalFlow"]["from"], result["experimentalFlow"]["to"]),
            ("a", "b"),
        )

    def test_chain_never_keeps_direct_a_to_c_edge(self) -> None:
        result = analyze_flow_candidate(_flow(), _components(), flow_strategy="junction_aware")
        self.assertNotEqual(
            (result["experimentalFlow"]["from"], result["experimentalFlow"]["to"]),
            ("a", "c"),
        )
        self.assertEqual(
            [(item["from"], item["to"]) for item in result["adjacentRelations"]],
            [("a", "b"), ("b", "c")],
        )

    def test_only_geometrically_touched_nearby_component_is_selected(self) -> None:
        components = _components() + [{"id": "near_b", "bbox": [40, 62, 60, 82]}]
        result = analyze_flow_candidate(
            _flow(source="b", points=[[50, 50], [90, 50]]), components, flow_strategy="junction_aware"
        )
        self.assertEqual(_endpoint(result, "source")["selectedComponentId"], "b")
        self.assertNotIn("near_b", _endpoint(result, "source")["coherentContactCandidates"])

    def test_tangent_component_is_not_a_barrier(self) -> None:
        result = analyze_flow_candidate(
            _flow(points=[[10, 40], [90, 40]]), _components(), flow_strategy="junction_aware"
        )
        self.assertIsNone(result["firstIntermediateBarrier"])
        tangent = [port for port in result["ports"] if port["componentId"] == "b"]
        self.assertTrue(tangent)
        self.assertTrue(all(port["contactStrength"] == "tangent_only" for port in tangent))

    def test_declared_source_and_destination_are_not_barriers(self) -> None:
        components = [_components()[0], _components()[2]]
        result = analyze_flow_candidate(_flow(), components, flow_strategy="junction_aware")
        self.assertIsNone(result["firstIntermediateBarrier"])
        self.assertEqual(result["edgeAction"], "kept")

    def test_inputs_remain_immutable_after_both_strategies(self) -> None:
        flow, components = _flow(), _components()
        before_flow, before_components = copy.deepcopy(flow), copy.deepcopy(components)
        comparison = compare_legacy_and_shadow(flow, components)
        self.assertEqual(flow, before_flow)
        self.assertEqual(components, before_components)
        self.assertFalse(comparison["officialResultChanged"])
        self.assertEqual(comparison["officialFlow"], flow)

    def test_segment_input_order_does_not_change_contact_catalog(self) -> None:
        segments = [
            {"id": "s1", "start": [10, 50], "end": [50, 50]},
            {"id": "s2", "start": [50, 50], "end": [90, 50]},
        ]
        first = build_component_contact_catalog(segments, _components())
        second = build_component_contact_catalog(list(reversed(segments)), _components())
        self.assertEqual(first, second)

    def test_small_coordinate_variation_and_scale_keep_classification(self) -> None:
        base = analyze_flow_candidate(_flow(), _components(), flow_strategy="junction_aware")
        varied = analyze_flow_candidate(
            _flow(points=[[10.2, 50.1], [89.8, 49.9]]),
            _components(),
            flow_strategy="junction_aware",
        )
        scaled_components = [
            {"id": item["id"], "bbox": [value * 2 for value in item["bbox"]]}
            for item in _components()
        ]
        scaled = analyze_flow_candidate(
            _flow(points=[[20, 100], [180, 100]]),
            scaled_components,
            flow_strategy="junction_aware",
            scale=2.0,
            line_width=2.0,
        )
        self.assertEqual(base["edgeAction"], varied["edgeAction"])
        self.assertEqual(base["edgeAction"], scaled["edgeAction"])
        self.assertEqual(
            base["firstIntermediateBarrier"]["componentId"],
            scaled["firstIntermediateBarrier"]["componentId"],
        )

    def test_legacy_is_the_default_and_rejects_unknown_strategy(self) -> None:
        flow = _flow()
        result = analyze_flow_candidate(flow, _components())
        self.assertEqual(result["strategy"], "legacy")
        self.assertEqual(result["legacyFlow"], flow)
        with self.assertRaises(ValueError):
            analyze_flow_candidate(flow, _components(), flow_strategy="tl004c")


class TL004BArtifactTests(unittest.TestCase):
    def test_external_validation_status_is_canonical_and_fail_closed(self) -> None:
        self.assertEqual(_normalize_validation_status("PASS"), "PASS")
        self.assertEqual(_normalize_validation_status("passed"), "PASS")
        self.assertEqual(_normalize_validation_status("FAIL"), "FAIL")
        self.assertEqual(_normalize_validation_status("pending"), "FAIL")
        self.assertEqual(_normalize_validation_status(None), "FAIL")

    def test_artifact_builder_is_development_only_and_covers_human_cases(self) -> None:
        results_root = ROOT / "data/results"
        with tempfile.TemporaryDirectory(dir=results_root) as directory:
            output = Path(directory) / "tl004b"
            result = build_artifacts(output)

            self.assertEqual(result["split"], "development_tuning")
            self.assertTrue(result["requiredCasesEvaluated"])
            self.assertTrue(result["controlsPreserved"])
            self.assertEqual(len(result["artifacts"]), 8)
            self.assertTrue(all((ROOT / path).is_file() for path in result["artifacts"].values()))

    def test_artifact_builder_refuses_to_overwrite_existing_output(self) -> None:
        results_root = ROOT / "data/results"
        with tempfile.TemporaryDirectory(dir=results_root) as directory:
            output = Path(directory) / "tl004b"
            build_artifacts(output)
            with self.assertRaises(FileExistsError):
                build_artifacts(output)

    def test_artifact_builder_runs_as_a_direct_cli(self) -> None:
        results_root = ROOT / "data/results"
        with tempfile.TemporaryDirectory(dir=results_root) as directory:
            output = Path(directory) / "tl004b"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/build_tl004b_artifacts.py",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((output / "tl004b-decision.json").is_file())


if __name__ == "__main__":
    unittest.main()
