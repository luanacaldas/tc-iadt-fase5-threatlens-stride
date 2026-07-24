from __future__ import annotations

import copy
import json
import math
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from backend.geometric_events import (
    EVENT_TYPES,
    GeometryParameters,
    extract_geometric_event_catalog,
)
from scripts.build_tl004a_artifacts import build_artifacts


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/tl004a_geometric_events.json"


def _load_fixtures() -> dict:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def _catalog(fixture: dict, **overrides) -> dict:
    return extract_geometric_event_catalog(
        fixture["segments"],
        fixture.get("components") or [],
        fixture.get("explicitJunctions") or [],
        scale=overrides.get("scale", 1.0),
        line_width=overrides.get("line_width", 1.0),
        parameters=overrides.get("parameters"),
    )


def _event_counts(catalog: dict) -> Counter:
    return Counter(event["type"] for event in catalog["events"])


def _classification_signature(catalog: dict) -> tuple:
    return tuple(sorted(_event_counts(catalog).items()))


def _scale_fixture(fixture: dict, factor: float) -> dict:
    scaled = copy.deepcopy(fixture)

    def point(values: list[float]) -> list[float]:
        return [value * factor for value in values]

    segments = []
    for segment in scaled["segments"]:
        if isinstance(segment, dict):
            segment["start"] = point(segment["start"])
            segment["end"] = point(segment["end"])
            segments.append(segment)
        else:
            segments.append(point(segment))
    scaled["segments"] = segments
    for component in scaled.get("components") or []:
        component["bbox"] = point(component["bbox"])
    for marker in scaled.get("explicitJunctions") or []:
        marker["center"] = point(marker["center"])
        marker["radius"] *= factor
    return scaled


def _rotate_segments(segments: list, degrees: float, center: tuple[float, float]) -> list:
    radians = math.radians(degrees)
    cosine, sine = math.cos(radians), math.sin(radians)

    def rotate(point: list[float]) -> list[float]:
        x, y = point[0] - center[0], point[1] - center[1]
        return [
            center[0] + x * cosine - y * sine,
            center[1] + x * sine + y * cosine,
        ]

    rotated = []
    for segment in copy.deepcopy(segments):
        if isinstance(segment, dict):
            segment["start"] = rotate(segment["start"])
            segment["end"] = rotate(segment["end"])
            rotated.append(segment)
        else:
            rotated.append(rotate(segment[:2]) + rotate(segment[2:]))
    return rotated


class GeometricEventFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        payload = _load_fixtures()
        cls.fixtures = {fixture["id"]: fixture for fixture in payload["fixtures"]}

    def test_all_fifteen_required_fixtures_exist_and_match_contract(self) -> None:
        self.assertEqual(len(self.fixtures), 15)
        for fixture_id, fixture in self.fixtures.items():
            with self.subTest(fixture=fixture_id):
                catalog = _catalog(fixture)
                counts = _event_counts(catalog)
                for event_type, minimum in (fixture.get("expected", {}).get("required") or {}).items():
                    self.assertGreaterEqual(counts[event_type], minimum)
                for event_type in fixture.get("expected", {}).get("forbidden") or []:
                    self.assertEqual(counts[event_type], 0)
                expected = fixture.get("expected") or {}
                if "canonicalSegmentCount" in expected:
                    self.assertEqual(catalog["summary"]["canonicalSegmentCount"], expected["canonicalSegmentCount"])
                if "inputSegmentCount" in expected:
                    self.assertEqual(catalog["summary"]["inputSegmentCount"], expected["inputSegmentCount"])

    def test_x_without_marker_does_not_create_transverse_junction(self) -> None:
        catalog = _catalog(self.fixtures["x_without_junction"])
        crossing = next(event for event in catalog["events"] if event["type"] == "crossing")

        self.assertFalse(crossing["geometricEvidence"]["transverseConnectivityAllowed"])
        self.assertFalse(crossing["geometricEvidence"]["explicitMarker"])
        self.assertEqual(crossing["geometricEvidence"]["armCount"], 4)

    def test_explicit_x_marker_allows_junction(self) -> None:
        catalog = _catalog(self.fixtures["x_with_explicit_junction"])
        junction = next(
            event for event in catalog["events"] if event["type"] == "explicit_junction"
        )

        self.assertTrue(junction["geometricEvidence"]["transverseConnectivityAllowed"])
        self.assertEqual(junction["geometricEvidence"]["markerProvenance"], ["fixture_dot"])

    def test_t_and_y_preserve_three_arms(self) -> None:
        for fixture_id in ("t_bifurcation", "y_bifurcation"):
            with self.subTest(fixture=fixture_id):
                catalog = _catalog(self.fixtures[fixture_id])
                branch = next(
                    event for event in catalog["events"] if event["type"] == "bifurcation"
                )
                self.assertEqual(branch["geometricEvidence"]["armCount"], 3)
                self.assertEqual(len(branch["armAngles"]), 3)

    def test_parallel_lines_are_never_combined(self) -> None:
        catalog = _catalog(self.fixtures["parallel_lines"])

        self.assertEqual(_event_counts(catalog), Counter({"endpoint": 4}))
        self.assertTrue(all(len(event["sourceSegments"]) == 1 for event in catalog["events"]))

    def test_component_contact_nearby_and_barrier_are_distinct(self) -> None:
        touching = _catalog(self.fixtures["endpoint_touching_component"])
        nearby = _catalog(self.fixtures["endpoint_near_component"])
        crossing = _catalog(self.fixtures["path_through_component"])

        self.assertEqual(_event_counts(touching)["component_port"], 1)
        self.assertEqual(_event_counts(nearby)["component_port"], 0)
        barriers = [
            event
            for event in crossing["events"]
            if event["type"] == "component_boundary_intersection"
        ]
        self.assertEqual(len(barriers), 2)
        self.assertTrue(
            all(event["geometricEvidence"]["crossesComponentInterior"] for event in barriers)
        )

    def test_fan_in_and_fan_out_remain_representable(self) -> None:
        for fixture_id in ("shared_trunk_fan_in", "shared_trunk_fan_out"):
            with self.subTest(fixture=fixture_id):
                catalog = _catalog(self.fixtures[fixture_id])
                branch = next(
                    event for event in catalog["events"] if event["type"] == "bifurcation"
                )
                self.assertEqual(branch["geometricEvidence"]["armCount"], 3)

    def test_chain_does_not_emit_a_to_c_or_any_flow_edge(self) -> None:
        catalog = _catalog(self.fixtures["chain_a_b_c"])

        self.assertFalse(catalog["producesFlows"])
        self.assertFalse(any("from" in event or "to" in event for event in catalog["events"]))
        self.assertFalse(
            any({"A", "C"}.issubset(set(event["nearbyComponents"])) for event in catalog["events"])
        )

    def test_order_variation_produces_identical_catalog(self) -> None:
        original = _catalog(self.fixtures["t_bifurcation"])
        reordered = _catalog(self.fixtures["different_segment_order"])

        self.assertEqual(original, reordered)


class GeometricEventInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        payload = _load_fixtures()
        cls.fixtures = {fixture["id"]: fixture for fixture in payload["fixtures"]}

    def test_contract_contains_every_required_event_field(self) -> None:
        required = {
            "id",
            "type",
            "coordinates",
            "sourceSegments",
            "armAngles",
            "provenance",
            "nearbyComponents",
            "classification",
            "confidence",
            "parameters",
            "geometricEvidence",
        }
        observed_types = set()
        for fixture in self.fixtures.values():
            for event in _catalog(fixture)["events"]:
                self.assertEqual(set(event), required)
                self.assertTrue(event["id"].startswith("gev-"))
                observed_types.add(event["type"])
        self.assertEqual(observed_types, set(EVENT_TYPES))

    def test_repeated_extraction_is_deterministic(self) -> None:
        fixture = self.fixtures["duplicate_and_fragmented"]
        self.assertEqual(_catalog(fixture), _catalog(copy.deepcopy(fixture)))

    def test_small_coordinate_variations_keep_classification(self) -> None:
        fixture = copy.deepcopy(self.fixtures["t_bifurcation"])
        fixture["segments"][0]["end"] = [9.8, 10.2]
        fixture["segments"][1]["start"] = [10.3, 9.9]
        fixture["segments"][2]["start"] = [9.9, 10.1]

        self.assertEqual(
            _classification_signature(_catalog(self.fixtures["t_bifurcation"])),
            _classification_signature(_catalog(fixture)),
        )

    def test_scale_compatibility(self) -> None:
        fixture = self.fixtures["x_with_explicit_junction"]
        scaled = _scale_fixture(fixture, 2.0)

        self.assertEqual(
            _classification_signature(_catalog(fixture, scale=1.0, line_width=1.0)),
            _classification_signature(_catalog(scaled, scale=2.0, line_width=2.0)),
        )

    def test_line_width_compatibility(self) -> None:
        fixture = self.fixtures["t_bifurcation"]
        self.assertEqual(
            _classification_signature(_catalog(fixture, line_width=1.0)),
            _classification_signature(_catalog(fixture, line_width=3.0)),
        )

    def test_moderate_rotation_keeps_classification(self) -> None:
        fixture = copy.deepcopy(self.fixtures["t_bifurcation"])
        fixture["segments"] = _rotate_segments(fixture["segments"], 17.0, (10.0, 10.0))

        self.assertEqual(
            _classification_signature(_catalog(self.fixtures["t_bifurcation"])),
            _classification_signature(_catalog(fixture)),
        )

    def test_extraction_does_not_mutate_inputs(self) -> None:
        fixture = copy.deepcopy(self.fixtures["x_with_explicit_junction"])
        before = copy.deepcopy(fixture)

        _catalog(fixture)

        self.assertEqual(fixture, before)

    def test_tolerances_are_configurable_and_reported(self) -> None:
        parameters = GeometryParameters(component_contact_tolerance=0.5)
        catalog = _catalog(
            self.fixtures["endpoint_touching_component"], parameters=parameters
        )

        self.assertEqual(
            catalog["parameters"]["configured"]["component_contact_tolerance"], 0.5
        )
        self.assertEqual(
            catalog["events"][0]["provenance"]["extractor"],
            "tl004a-geometric-events-v1",
        )

    def test_artifact_builder_writes_four_relative_contract_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as temp_dir:
            output = Path(temp_dir) / "tl004a"
            result = build_artifacts(
                output,
                generated_at="2026-07-21T00:00:00+00:00",
            )

            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["fixtureCount"], 15)
            self.assertEqual(len(result["artifacts"]), 4)
            for relative in result["artifacts"].values():
                self.assertFalse(Path(relative).is_absolute())
                self.assertTrue((ROOT / relative).is_file())


if __name__ == "__main__":
    unittest.main()
