"""Shadow-only crossing and junction classification for TL-004C."""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from backend.endpoint_validation import build_component_contact_catalog
from backend.geometric_events import GeometryParameters, extract_geometric_event_catalog


SCHEMA_VERSION = "1.0"
STRATEGY_REVISION = "tl004c-crossings-junctions-v1"
INTERSECTION_CLASSIFICATIONS = (
    "continuation",
    "elbow",
    "crossing_without_junction",
    "explicit_junction",
    "bifurcation",
    "ambiguous_intersection",
)


@dataclass(frozen=True)
class IntersectionParameters:
    marker_min_confidence: float = 0.8
    minimum_pixel_support: float = 0.35

    def to_dict(self) -> dict[str, float]:
        if not 0 <= self.marker_min_confidence <= 1:
            raise ValueError("marker_min_confidence must be between zero and one")
        if not 0 <= self.minimum_pixel_support <= 1:
            raise ValueError("minimum_pixel_support must be between zero and one")
        return {
            "markerMinConfidence": self.marker_min_confidence,
            "minimumPixelSupport": self.minimum_pixel_support,
        }


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"{prefix}-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]}"


def _distance(first: Sequence[float], second: Sequence[float]) -> float:
    return math.hypot(float(first[0]) - float(second[0]), float(first[1]) - float(second[1]))


def _angle_separation(first: float, second: float) -> float:
    difference = abs(float(first) - float(second)) % 360
    return min(difference, 360 - difference)


def _normalize_markers(markers: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for marker in markers:
        center = marker.get("center")
        if not isinstance(center, Sequence) or len(center) != 2:
            raise ValueError("junction markers require center [x, y]")
        radius = float(marker.get("radius") or 0)
        confidence = float(marker.get("confidence", 1.0))
        if radius <= 0 or not 0 <= confidence <= 1:
            raise ValueError("junction marker radius and confidence are invalid")
        normalized.append(
            {
                "center": [float(center[0]), float(center[1])],
                "radius": radius,
                "confidence": confidence,
                "complete": bool(marker.get("complete", True)),
                "provenance": str(marker.get("provenance") or "explicit_marker"),
            }
        )
    return sorted(
        normalized,
        key=lambda item: (item["center"], item["radius"], item["provenance"]),
    )


def _segment_supports(
    raw_segments: Sequence[Sequence[float] | Mapping[str, Any]],
    canonical_segments: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    by_input_id = {}
    for raw in raw_segments:
        if not isinstance(raw, Mapping) or not raw.get("id"):
            continue
        support = raw.get("pixelSupport")
        if support is not None:
            value = float(support)
            if not 0 <= value <= 1:
                raise ValueError("pixelSupport must be between zero and one")
            by_input_id[str(raw["id"])] = value
    result = {}
    for segment in canonical_segments:
        values = [by_input_id[item] for item in segment.get("inputIds", []) if item in by_input_id]
        result[str(segment["id"])] = {
            "values": values,
            "aggregate": round(sum(values) / len(values), 4) if values else None,
        }
    return result


def _arm_records(
    arms: Sequence[Mapping[str, Any]],
    segment_provenance: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    records = []
    for arm in arms:
        payload = {
            "segmentId": str(arm["segmentId"]),
            "role": str(arm["role"]),
            "angle": round(float(arm["angle"]), 3),
        }
        metadata = segment_provenance.get(payload["segmentId"], {})
        records.append(
            {
                "id": _stable_id("arm", payload),
                **payload,
                "provenance": copy.deepcopy(metadata.get("provenance") or []),
                "inputSegmentIds": copy.deepcopy(metadata.get("inputIds") or []),
            }
        )
    return sorted(records, key=lambda item: (item["angle"], item["segmentId"], item["role"]))


def _branch_pairs(
    arms: Sequence[Mapping[str, Any]], collinear_tolerance: float
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    all_pairs = []
    collinear = []
    for first, second in itertools.combinations(arms, 2):
        separation = round(_angle_separation(first["angle"], second["angle"]), 3)
        pair = {
            "armIds": sorted((str(first["id"]), str(second["id"]))),
            "angleSeparation": separation,
        }
        all_pairs.append(pair)
        if abs(180 - separation) <= collinear_tolerance:
            collinear.append(pair)
    sort_key = lambda item: (item["armIds"], item["angleSeparation"])
    return sorted(all_pairs, key=sort_key), sorted(collinear, key=sort_key)


def _matched_markers(
    coordinates: Sequence[float], markers: Sequence[Mapping[str, Any]], tolerance: float
) -> list[dict[str, Any]]:
    return [
        copy.deepcopy(marker)
        for marker in markers
        if _distance(coordinates, marker["center"]) <= float(marker["radius"]) + tolerance
    ]


def _component_context(
    coordinates: Sequence[float], contact_events: Sequence[Mapping[str, Any]], tolerance: float
) -> dict[str, Any]:
    matched = [
        event
        for event in contact_events
        if _distance(coordinates, event["coordinates"]) <= tolerance
    ]
    return {
        "contactEventIds": sorted(str(event["id"]) for event in matched),
        "nearComponentBoundary": bool(matched),
        "connectedToComponentPort": any(
            (
                event["type"] == "component_port"
                and event["geometricEvidence"].get("contactVerified")
            )
            or (
                event["type"] == "component_boundary_intersection"
                and event["geometricEvidence"].get("crossesComponentInterior")
            )
            for event in matched
        ),
        "onComponentBarrier": any(
            event["type"] == "component_boundary_intersection"
            and event["geometricEvidence"].get("crossesComponentInterior")
            for event in matched
        ),
        "componentIds": sorted(
            {
                str(event["geometricEvidence"]["componentId"])
                for event in matched
            }
        ),
    }


def _classify_event(
    event: Mapping[str, Any],
    markers: Sequence[Mapping[str, Any]],
    supports: Mapping[str, Mapping[str, Any]],
    segment_provenance: Mapping[str, Mapping[str, Any]],
    component_context: Mapping[str, Any],
    intersection_parameters: IntersectionParameters,
) -> dict[str, Any]:
    evidence = event["geometricEvidence"]
    effective = event["parameters"]
    arms = _arm_records(evidence.get("arms") or [], segment_provenance)
    all_pairs, collinear_pairs = _branch_pairs(
        arms, float(effective["collinearToleranceDegrees"])
    )
    matched = _matched_markers(
        event["coordinates"], markers, float(effective["markerTolerance"])
    )
    qualified_markers = [
        marker
        for marker in matched
        if marker["complete"]
        and marker["confidence"] >= intersection_parameters.marker_min_confidence
    ]
    support_values = [
        value
        for segment_id in event["sourceSegments"]
        for value in supports.get(str(segment_id), {}).get("values", [])
    ]
    local_support = round(sum(support_values) / len(support_values), 4) if support_values else None
    degree = len(arms)
    event_type = str(event["type"])
    reasons = []

    if matched and not qualified_markers:
        classification = "ambiguous_intersection"
        reasons.append("junction_marker_incomplete_or_below_confidence")
    elif qualified_markers and degree >= 3:
        classification = "explicit_junction"
        reasons.append("qualified_visual_junction_marker")
    elif event_type == "crossing":
        if len(collinear_pairs) >= 2:
            classification = "crossing_without_junction"
            reasons.extend(("proper_intersection_without_marker", "collinear_continuity_preserved"))
        else:
            classification = "ambiguous_intersection"
            reasons.append("crossing_lacks_two_collinear_continuities")
    elif event_type == "bifurcation":
        if degree != 3:
            classification = "ambiguous_intersection"
            reasons.append("multi_arm_event_requires_later_global_pairing")
        elif local_support is not None and local_support < intersection_parameters.minimum_pixel_support:
            classification = "ambiguous_intersection"
            reasons.append("insufficient_local_pixel_support")
        else:
            classification = "bifurcation"
            reasons.append("three_arms_converge_at_shared_contact")
    elif event_type == "continuation" and len(collinear_pairs) == 1:
        classification = "continuation"
        reasons.append("two_arms_are_collinear")
    elif event_type == "elbow" and degree == 2:
        separation = _angle_separation(arms[0]["angle"], arms[1]["angle"])
        if separation <= float(effective["collinearToleranceDegrees"]):
            classification = "ambiguous_intersection"
            reasons.append("same_direction_parallel_arms_may_only_be_proximate")
        else:
            classification = "elbow"
            reasons.append("two_connected_non_collinear_arms")
    else:
        classification = "ambiguous_intersection"
        reasons.append("insufficient_topological_evidence")

    if classification == "crossing_without_junction":
        allowed_pairs = collinear_pairs
        allowed_ids = {tuple(item["armIds"]) for item in allowed_pairs}
        blocked_pairs = [item for item in all_pairs if tuple(item["armIds"]) not in allowed_ids]
        action = "shadow_block_transverse"
        review_only = False
    elif classification in {"explicit_junction", "bifurcation"}:
        allowed_pairs = all_pairs
        blocked_pairs = []
        action = "shadow_allow_local_connectivity"
        review_only = False
    elif classification in {"continuation", "elbow"}:
        allowed_pairs = all_pairs
        blocked_pairs = []
        action = "shadow_preserve_continuity"
        review_only = False
    else:
        allowed_pairs = []
        blocked_pairs = []
        action = "review_only"
        review_only = True

    if classification == "explicit_junction":
        confidence = "high"
    elif classification == "ambiguous_intersection":
        confidence = "low"
    elif local_support is None:
        confidence = "medium"
    else:
        confidence = "high" if local_support >= 0.7 else "medium"
    payload = {
        "sourceEventId": event["id"],
        "classification": classification,
        "coordinates": event["coordinates"],
    }
    return {
        "id": _stable_id("int", payload),
        "sourceEventId": event["id"],
        "sourceEventType": event_type,
        "coordinates": copy.deepcopy(event["coordinates"]),
        "classification": classification,
        "legacyImplicitClassification": "all_incident_arms_connected",
        "geometricDegree": degree,
        "arms": arms,
        "angles": [arm["angle"] for arm in arms],
        "collinearPairs": collinear_pairs,
        "allowedBranchPairs": allowed_pairs,
        "blockedTransversePairs": blocked_pairs,
        "localPixelSupport": local_support,
        "pixelSupportBySegment": {
            str(segment_id): supports.get(str(segment_id), {}).get("aggregate")
            for segment_id in event["sourceSegments"]
        },
        "visualJunctionMarker": {
            "exists": bool(matched),
            "qualified": bool(qualified_markers),
            "markers": matched,
        },
        "segmentProvenance": copy.deepcopy(event["provenance"].get("inputs") or []),
        "sourceSegments": copy.deepcopy(event["sourceSegments"]),
        "componentContext": copy.deepcopy(dict(component_context)),
        "confidence": confidence,
        "reasons": sorted(set(reasons)),
        "parameters": {
            **copy.deepcopy(effective),
            **intersection_parameters.to_dict(),
        },
        "connectivityDecision": action,
        "reviewOnly": review_only,
        "decompositionDeferred": classification in {"explicit_junction", "bifurcation"},
        "shadowOnly": True,
        "officialEligible": False,
    }


def classify_intersections(
    segments: Iterable[Sequence[float] | Mapping[str, Any]],
    components: Iterable[Mapping[str, Any]] = (),
    explicit_junctions: Iterable[Mapping[str, Any]] = (),
    *,
    geometry_parameters: GeometryParameters | None = None,
    intersection_parameters: IntersectionParameters | None = None,
    scale: float = 1.0,
    line_width: float = 1.0,
) -> dict[str, Any]:
    """Classify local topology without changing official flows or caller inputs."""
    raw_segments = copy.deepcopy(list(segments))
    raw_components = copy.deepcopy(list(components))
    raw_markers = copy.deepcopy(list(explicit_junctions))
    input_snapshot = copy.deepcopy((raw_segments, raw_components, raw_markers))
    params = intersection_parameters or IntersectionParameters()
    params.to_dict()
    markers = _normalize_markers(raw_markers)
    qualified = [
        {
            "center": marker["center"],
            "radius": marker["radius"],
            "provenance": marker["provenance"],
        }
        for marker in markers
        if marker["complete"] and marker["confidence"] >= params.marker_min_confidence
    ]
    catalog = extract_geometric_event_catalog(
        raw_segments,
        raw_components,
        qualified,
        parameters=geometry_parameters,
        scale=scale,
        line_width=line_width,
    )
    contacts = build_component_contact_catalog(
        raw_segments,
        raw_components,
        geometry_parameters=geometry_parameters,
        scale=scale,
        line_width=line_width,
    )
    supports = _segment_supports(raw_segments, catalog["segments"])
    segment_provenance = {
        str(segment["id"]): {
            "provenance": copy.deepcopy(segment.get("provenance") or []),
            "inputIds": copy.deepcopy(segment.get("inputIds") or []),
        }
        for segment in catalog["segments"]
    }
    topology_types = {"continuation", "elbow", "crossing", "explicit_junction", "bifurcation"}
    events = []
    for event in catalog["events"]:
        if event["type"] not in topology_types:
            continue
        context = _component_context(
            event["coordinates"],
            contacts["events"],
            float(event["parameters"]["intersectionTolerance"]),
        )
        events.append(
            _classify_event(event, markers, supports, segment_provenance, context, params)
        )
    events.sort(key=lambda item: (item["coordinates"], item["classification"], item["id"]))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "strategyRevision": STRATEGY_REVISION,
        "mode": "shadow",
        "officialEligible": False,
        "dependencies": [
            "backend/geometric_events.py",
            "backend/endpoint_validation.py",
        ],
        "events": events,
        "eventCount": len(events),
        "parameters": {
            "geometry": copy.deepcopy(catalog["parameters"]),
            "intersection": params.to_dict(),
        },
        "inputMutation": input_snapshot != (raw_segments, raw_components, raw_markers),
    }


def compare_legacy_and_shadow_intersections(
    official_flows: Iterable[Mapping[str, Any]],
    segments: Iterable[Sequence[float] | Mapping[str, Any]],
    components: Iterable[Mapping[str, Any]] = (),
    explicit_junctions: Iterable[Mapping[str, Any]] = (),
    **kwargs: Any,
) -> dict[str, Any]:
    """Return shadow topology while preserving an exact copy of official legacy flows."""
    legacy = copy.deepcopy(list(official_flows))
    shadow = classify_intersections(
        segments,
        components,
        explicit_junctions,
        **kwargs,
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "legacy_vs_shadow",
        "officialStrategy": "legacy",
        "shadowStrategy": "junction_aware_intersections",
        "officialFlows": legacy,
        "shadow": shadow,
        "officialFlowsChanged": False,
        "officialDirectionChanges": 0,
        "feedsStride": "legacy_only",
    }
