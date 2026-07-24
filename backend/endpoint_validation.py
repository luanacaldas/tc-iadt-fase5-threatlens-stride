"""Shadow-only endpoint, component-port, and barrier validation for TL-004B."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any, Iterable, Mapping, Sequence

from backend.geometric_events import GeometryParameters, extract_geometric_event_catalog


SCHEMA_VERSION = "1.0"
STRATEGY_REVISION = "tl004b-ports-barriers-v1"
FLOW_STRATEGIES = ("legacy", "junction_aware")
CONTACT_CLASSIFICATIONS = (
    "confirmed_contact",
    "ambiguous_contact",
    "proximity_only",
    "no_contact",
    "wrong_component_contact",
)


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    content = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"{prefix}-{hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]}"


def _point(value: Sequence[float]) -> tuple[float, float]:
    if len(value) != 2:
        raise ValueError("path points must contain exactly two coordinates")
    return float(value[0]), float(value[1])


def _distance(first: Sequence[float], second: Sequence[float]) -> float:
    return math.hypot(float(first[0]) - float(second[0]), float(first[1]) - float(second[1]))


def _point_rect_distance(point: Sequence[float], bbox: Sequence[float]) -> float:
    x, y = float(point[0]), float(point[1])
    x1, y1, x2, y2 = (float(value) for value in bbox)
    return math.hypot(max(x1 - x, 0.0, x - x2), max(y1 - y, 0.0, y - y2))


def _normalize_components(components: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    normalized = []
    for component in components:
        component_id = str(component.get("id") or "")
        bbox = component.get("bbox")
        if not component_id or not isinstance(bbox, Sequence) or len(bbox) != 4:
            raise ValueError("components require a non-empty id and bbox [x1, y1, x2, y2]")
        values = tuple(float(value) for value in bbox)
        if values[0] >= values[2] or values[1] >= values[3]:
            raise ValueError("component bounding boxes must have positive area")
        normalized.append({"id": component_id, "bbox": values})
    ids = [item["id"] for item in normalized]
    if len(ids) != len(set(ids)):
        raise ValueError("component ids must be unique")
    return tuple(sorted(normalized, key=lambda item: item["id"]))


def _path_segments(path: Sequence[Sequence[float]], flow_id: str) -> tuple[dict[str, Any], ...]:
    points = tuple(_point(value) for value in path)
    if len(points) < 2:
        raise ValueError("junction-aware validation requires at least two pathPoints")
    segments = []
    for index, (start, end) in enumerate(zip(points, points[1:])):
        if start == end:
            continue
        segments.append(
            {
                "id": f"path-segment-{index}",
                "start": list(start),
                "end": list(end),
                "provenance": f"flow:{flow_id or 'anonymous'}",
            }
        )
    if not segments:
        raise ValueError("junction-aware validation requires a non-zero path")
    return tuple(segments)


def _bbox_side(point: Sequence[float], bbox: Sequence[float]) -> str:
    x, y = float(point[0]), float(point[1])
    x1, y1, x2, y2 = (float(value) for value in bbox)
    ranked = sorted(
        ((abs(x - x1), "left"), (abs(x - x2), "right"), (abs(y - y1), "top"), (abs(y - y2), "bottom")),
        key=lambda item: (item[0], item[1]),
    )
    return ranked[0][1]


def _project_to_segment(
    point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]
) -> tuple[float, float, tuple[float, float]]:
    delta_x, delta_y = end[0] - start[0], end[1] - start[1]
    length_squared = delta_x * delta_x + delta_y * delta_y
    ratio = ((point[0] - start[0]) * delta_x + (point[1] - start[1]) * delta_y) / length_squared
    ratio = min(1.0, max(0.0, ratio))
    projected = start[0] + ratio * delta_x, start[1] + ratio * delta_y
    return ratio, _distance(point, projected), projected


def _path_position(
    point: tuple[float, float], path: tuple[tuple[float, float], ...]
) -> dict[str, Any]:
    lengths = [_distance(start, end) for start, end in zip(path, path[1:])]
    total = sum(lengths)
    cumulative = 0.0
    candidates = []
    for index, (start, end, length) in enumerate(zip(path, path[1:], lengths)):
        if length <= 0:
            continue
        ratio, distance, _ = _project_to_segment(point, start, end)
        absolute = cumulative + ratio * length
        candidates.append((distance, index, ratio, absolute, start, end))
        cumulative += length
    distance, index, ratio, absolute, start, end = min(candidates)
    angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0])) % 360
    return {
        "segmentIndex": index,
        "segmentRatio": round(ratio, 6),
        "distanceToPath": round(distance, 6),
        "absolutePosition": round(absolute, 6),
        "normalizedPosition": round(absolute / total, 6) if total else 0.0,
        "pathLength": round(total, 6),
        "angle": round(angle, 3),
    }


def build_component_contact_catalog(
    segments: Iterable[Sequence[float] | Mapping[str, Any]],
    components: Iterable[Mapping[str, Any]],
    *,
    geometry_parameters: GeometryParameters | None = None,
    scale: float = 1.0,
    line_width: float = 1.0,
) -> dict[str, Any]:
    """Expose the TL-004A component-contact events with a TL-004B dependency marker."""
    catalog = extract_geometric_event_catalog(
        segments,
        components,
        parameters=geometry_parameters,
        scale=scale,
        line_width=line_width,
    )
    component_events = [
        copy.deepcopy(event)
        for event in catalog["events"]
        if event["type"] in {"component_port", "component_boundary_intersection"}
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "strategyRevision": STRATEGY_REVISION,
        "dependency": {
            "extractorRevision": catalog["extractorRevision"],
            "eventTypes": ["component_port", "component_boundary_intersection"],
        },
        "parameters": copy.deepcopy(catalog["parameters"]),
        "segments": copy.deepcopy(catalog["segments"]),
        "events": component_events,
    }


def derive_ports_and_barriers(
    path_points: Sequence[Sequence[float]],
    components: Iterable[Mapping[str, Any]],
    *,
    flow_id: str = "",
    geometry_parameters: GeometryParameters | None = None,
    scale: float = 1.0,
    line_width: float = 1.0,
) -> dict[str, Any]:
    """Derive ordered component contacts while preserving the caller's path."""
    path = tuple(_point(value) for value in path_points)
    normalized_components = _normalize_components(components)
    component_by_id = {item["id"]: item for item in normalized_components}
    segments = _path_segments(path, flow_id)
    catalog = build_component_contact_catalog(
        segments,
        normalized_components,
        geometry_parameters=geometry_parameters,
        scale=scale,
        line_width=line_width,
    )
    canonical_to_inputs = {
        segment["id"]: tuple(segment.get("inputIds") or []) for segment in catalog["segments"]
    }
    grouped: dict[tuple[str, tuple[float, float]], dict[str, Any]] = {}
    for event in catalog["events"]:
        component_id = str(event["geometricEvidence"]["componentId"])
        coordinates = _point(event["coordinates"])
        position = _path_position(coordinates, path)
        key = component_id, coordinates
        entry = grouped.setdefault(
            key,
            {
                "componentId": component_id,
                "coordinates": list(coordinates),
                "eventIds": set(),
                "eventTypes": set(),
                "sourceSegments": set(),
                "crossesInterior": False,
                "contactVerified": False,
                "position": position,
            },
        )
        entry["eventIds"].add(event["id"])
        entry["eventTypes"].add(event["type"])
        entry["crossesInterior"] = bool(
            entry["crossesInterior"]
            or event["geometricEvidence"].get("crossesComponentInterior")
        )
        entry["contactVerified"] = bool(
            entry["contactVerified"] or event["geometricEvidence"].get("contactVerified")
        )
        for segment_id in event["sourceSegments"]:
            entry["sourceSegments"].update(canonical_to_inputs.get(segment_id) or (segment_id,))

    ports = []
    for entry in grouped.values():
        component = component_by_id[entry["componentId"]]
        strong = bool(entry["crossesInterior"] or entry["contactVerified"])
        coordinates = entry["coordinates"]
        position = entry["position"]
        source_segments = sorted(entry["sourceSegments"])
        payload = {
            "componentId": entry["componentId"],
            "coordinates": coordinates,
            "sourceSegments": source_segments,
        }
        ports.append(
            {
                "id": _stable_id("port", payload),
                "componentId": entry["componentId"],
                "coordinates": coordinates,
                "side": _bbox_side(coordinates, component["bbox"]),
                "distanceFromPathStart": round(position["absolutePosition"], 3),
                "distanceFromPathEnd": round(
                    position["pathLength"] - position["absolutePosition"], 3
                ),
                "normalizedPathPosition": position["normalizedPosition"],
                "arrivalOrDepartureAngle": position["angle"],
                "segmentResponsible": source_segments[0] if source_segments else None,
                "sourceSegments": source_segments,
                "confidence": "high" if strong else "low",
                "contactStrength": "verified" if strong else "tangent_only",
                "geometricEvidence": {
                    "eventIds": sorted(entry["eventIds"]),
                    "eventTypes": sorted(entry["eventTypes"]),
                    "crossesComponentInterior": bool(entry["crossesInterior"]),
                    "endpointContactVerified": bool(entry["contactVerified"]),
                    "dependency": "backend/geometric_events.py",
                },
            }
        )
    ports.sort(key=lambda item: (item["normalizedPathPosition"], item["componentId"], item["id"]))
    barriers = [
        {
            "id": _stable_id(
                "barrier",
                {
                    "componentId": port["componentId"],
                    "coordinates": port["coordinates"],
                    "portId": port["id"],
                },
            ),
            "componentId": port["componentId"],
            "firstContact": copy.deepcopy(port["coordinates"]),
            "normalizedPathPosition": port["normalizedPathPosition"],
            "portId": port["id"],
            "crossesComponentInterior": True,
            "shadowOnly": True,
        }
        for port in ports
        if port["geometricEvidence"]["crossesComponentInterior"]
    ]
    return {
        "ports": ports,
        "barriers": barriers,
        "eventCatalog": catalog,
        "pathLength": ports[0]["distanceFromPathStart"] + ports[0]["distanceFromPathEnd"] if ports else sum(
            _distance(start, end) for start, end in zip(path, path[1:])
        ),
    }


def _orientation(
    path: tuple[tuple[float, float], ...],
    source: Mapping[str, Any],
    destination: Mapping[str, Any],
    scale: float,
) -> dict[str, Any]:
    normal = _point_rect_distance(path[0], source["bbox"]) + _point_rect_distance(
        path[-1], destination["bbox"]
    )
    reversed_cost = _point_rect_distance(path[-1], source["bbox"]) + _point_rect_distance(
        path[0], destination["bbox"]
    )
    reversed_path = reversed_cost + max(0.5 * scale, 0.5) < normal
    return {
        "pathPointsReversed": reversed_path,
        "normalAssociationCost": round(normal, 3),
        "reversedAssociationCost": round(reversed_cost, 3),
        "reason": "lower_declared_endpoint_cost" if reversed_path else "original_order_retained",
    }


def _endpoint_decision(
    role: str,
    declared_component: str,
    endpoint: tuple[float, float],
    ports: list[dict[str, Any]],
    components: tuple[dict[str, Any], ...],
    proximity_tolerance: float,
) -> dict[str, Any]:
    reverse = role == "destination"
    strong = [port for port in ports if port["contactStrength"] == "verified"]
    ordered = sorted(
        strong,
        key=lambda item: (
            -item["normalizedPathPosition"] if reverse else item["normalizedPathPosition"],
            item["componentId"],
        ),
    )
    selected = ordered[0] if ordered else None
    if selected:
        extreme = selected["normalizedPathPosition"]
        equivalent = [
            port
            for port in ordered
            if abs(port["normalizedPathPosition"] - extreme) <= 1e-4
        ]
        equivalent_ids = sorted({port["componentId"] for port in equivalent})
        if len(equivalent_ids) > 1:
            classification = "ambiguous_contact"
        elif selected["componentId"] == declared_component:
            classification = "confirmed_contact"
        else:
            classification = "wrong_component_contact"
        selected_component = selected["componentId"]
        selected_port = selected["id"]
    else:
        tangent_ids = sorted(
            {
                port["componentId"]
                for port in ports
                if port["contactStrength"] == "tangent_only"
            }
        )
        declared = next(item for item in components if item["id"] == declared_component)
        declared_distance = _point_rect_distance(endpoint, declared["bbox"])
        if declared_component in tangent_ids:
            classification = "ambiguous_contact"
            selected_component = declared_component
        elif declared_distance <= proximity_tolerance:
            classification = "proximity_only"
            selected_component = declared_component
        else:
            classification = "no_contact"
            selected_component = None
        selected_port = None
        equivalent_ids = tangent_ids

    ranked = sorted(
        (
            (_point_rect_distance(endpoint, component["bbox"]), component["id"])
            for component in components
        ),
        key=lambda item: (item[0], item[1]),
    )
    return {
        "role": role,
        "declaredComponentId": declared_component,
        "endpoint": list(endpoint),
        "classification": classification,
        "selectedComponentId": selected_component,
        "selectedPortId": selected_port,
        "coherentContactCandidates": equivalent_ids,
        "nearestComponentId": ranked[0][1],
        "nearestComponentDistance": round(ranked[0][0], 3),
        "secondComponentId": ranked[1][1] if len(ranked) > 1 else None,
        "secondComponentDistance": round(ranked[1][0], 3) if len(ranked) > 1 else None,
        "proximityTolerance": round(proximity_tolerance, 3),
    }


def _contact_sequence(ports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sequence = []
    for port in sorted(ports, key=lambda item: (item["normalizedPathPosition"], item["componentId"])):
        if port["contactStrength"] != "verified":
            continue
        if sequence and sequence[-1]["componentId"] == port["componentId"]:
            sequence[-1]["lastPosition"] = port["normalizedPathPosition"]
            continue
        sequence.append(
            {
                "componentId": port["componentId"],
                "firstPosition": port["normalizedPathPosition"],
                "lastPosition": port["normalizedPathPosition"],
            }
        )
    return sequence


def _junction_aware_analysis(
    flow: Mapping[str, Any],
    components: Iterable[Mapping[str, Any]],
    *,
    geometry_parameters: GeometryParameters | None,
    scale: float,
    line_width: float,
) -> dict[str, Any]:
    original = copy.deepcopy(dict(flow))
    component_tuple = _normalize_components(components)
    component_by_id = {item["id"]: item for item in component_tuple}
    source_id, destination_id = str(flow.get("from") or ""), str(flow.get("to") or "")
    if source_id not in component_by_id or destination_id not in component_by_id:
        raise ValueError("flow endpoints must reference known components")
    path = tuple(_point(value) for value in (flow.get("pathPoints") or []))
    if len(path) < 2:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "strategy": "junction_aware",
            "strategyRevision": STRATEGY_REVISION,
            "mode": "shadow",
            "officialEligible": False,
            "legacyFlow": original,
            "experimentalFlow": None,
            "edgeAction": "review_only",
            "reasonCodes": ["path_points_not_available"],
            "pathPointsReversed": False,
            "endpointDecisions": [],
            "ports": [],
            "barriers": [],
            "adjacentRelations": [],
        }

    orientation = _orientation(
        path, component_by_id[source_id], component_by_id[destination_id], scale
    )
    internal_path = tuple(reversed(path)) if orientation["pathPointsReversed"] else path
    contact_data = derive_ports_and_barriers(
        internal_path,
        component_tuple,
        flow_id=str(flow.get("id") or ""),
        geometry_parameters=geometry_parameters,
        scale=scale,
        line_width=line_width,
    )
    proximity_tolerance = float(
        contact_data["eventCatalog"]["parameters"]["effective"]["nearbyComponentDistance"]
    )
    source_decision = _endpoint_decision(
        "source", source_id, internal_path[0], contact_data["ports"], component_tuple, proximity_tolerance
    )
    destination_decision = _endpoint_decision(
        "destination",
        destination_id,
        internal_path[-1],
        contact_data["ports"],
        component_tuple,
        proximity_tolerance,
    )
    endpoint_resolution_reason = None
    if (
        source_decision["classification"] == "wrong_component_contact"
        and destination_decision["classification"] == "wrong_component_contact"
        and source_decision["selectedComponentId"] == destination_decision["selectedComponentId"]
        and destination_decision["secondComponentId"] == destination_id
        and destination_decision["secondComponentDistance"] is not None
        and destination_decision["secondComponentDistance"] <= proximity_tolerance * 3
    ):
        destination_decision["classification"] = "proximity_only"
        destination_decision["selectedComponentId"] = destination_id
        destination_decision["selectedPortId"] = None
        endpoint_resolution_reason = "destination_approach_after_wrong_source_contact"
    sequence = _contact_sequence(contact_data["ports"])
    selected_source = source_decision["selectedComponentId"] or source_id
    selected_destination = destination_decision["selectedComponentId"] or destination_id
    endpoint_ids = {source_id, destination_id, selected_source, selected_destination}
    intermediate = [item for item in sequence[1:-1] if item["componentId"] not in endpoint_ids]
    first_barrier = intermediate[0] if intermediate else None

    adjacent_relations = [
        {"from": first["componentId"], "to": second["componentId"], "shadowOnly": True}
        for first, second in zip(sequence, sequence[1:])
        if first["componentId"] != second["componentId"]
    ]
    reason_codes = []
    if orientation["pathPointsReversed"]:
        reason_codes.append("path_points_reversed_internally")
    if endpoint_resolution_reason:
        reason_codes.append(endpoint_resolution_reason)
    for decision in (source_decision, destination_decision):
        if decision["classification"] != "confirmed_contact":
            reason_codes.append(f"{decision['role']}:{decision['classification']}")
    if first_barrier:
        reason_codes.append("component_barrier_stops_path")

    classifications = {source_decision["classification"], destination_decision["classification"]}
    experimental = copy.deepcopy(original)
    if first_barrier:
        experimental["from"] = selected_source
        experimental["to"] = first_barrier["componentId"]
        edge_action = "redirected"
    elif "wrong_component_contact" in classifications:
        experimental["from"] = selected_source
        experimental["to"] = selected_destination
        edge_action = "redirected" if experimental["from"] != experimental["to"] else "review_only"
    elif classifications == {"confirmed_contact"}:
        edge_action = "kept"
    else:
        edge_action = "review_only"
        experimental = copy.deepcopy(original)
    if edge_action == "redirected" and (
        experimental["from"] == original.get("from") and experimental["to"] == original.get("to")
    ):
        edge_action = "kept"
    if not reason_codes:
        reason_codes.append("both_endpoints_confirmed_without_intermediate_barrier")

    barriers = [
        {
            **copy.deepcopy(barrier),
            "isDeclaredEndpoint": barrier["componentId"] in {source_id, destination_id},
            "terminatesExperimentalPath": bool(
                first_barrier and barrier["componentId"] == first_barrier["componentId"]
            ),
        }
        for barrier in contact_data["barriers"]
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "strategy": "junction_aware",
        "strategyRevision": STRATEGY_REVISION,
        "mode": "shadow",
        "officialEligible": False,
        "legacyFlow": original,
        "experimentalFlow": experimental if edge_action != "review_only" else None,
        "edgeAction": edge_action,
        "reasonCodes": sorted(set(reason_codes)),
        **orientation,
        "internalPathPoints": [list(point) for point in internal_path],
        "endpointDecisions": [source_decision, destination_decision],
        "ports": contact_data["ports"],
        "barriers": barriers,
        "firstIntermediateBarrier": copy.deepcopy(first_barrier),
        "contactSequence": sequence,
        "adjacentRelations": adjacent_relations,
        "inputMutation": False,
    }


def analyze_flow_candidate(
    flow: Mapping[str, Any],
    components: Iterable[Mapping[str, Any]],
    *,
    flow_strategy: str = "legacy",
    geometry_parameters: GeometryParameters | None = None,
    scale: float = 1.0,
    line_width: float = 1.0,
) -> dict[str, Any]:
    """Run an explicit legacy or shadow junction-aware strategy."""
    if flow_strategy not in FLOW_STRATEGIES:
        raise ValueError(f"unsupported flow strategy: {flow_strategy}")
    if flow_strategy == "legacy":
        return {
            "schemaVersion": SCHEMA_VERSION,
            "strategy": "legacy",
            "mode": "official",
            "officialEligible": True,
            "legacyFlow": copy.deepcopy(dict(flow)),
            "experimentalFlow": None,
            "edgeAction": "kept",
            "reasonCodes": ["legacy_default_unchanged"],
        }
    return _junction_aware_analysis(
        flow,
        components,
        geometry_parameters=geometry_parameters,
        scale=scale,
        line_width=line_width,
    )


def compare_legacy_and_shadow(
    flow: Mapping[str, Any],
    components: Iterable[Mapping[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    """Execute both strategies while keeping the legacy flow as the only official result."""
    component_snapshot = copy.deepcopy(list(components))
    legacy = analyze_flow_candidate(flow, component_snapshot, flow_strategy="legacy")
    shadow = analyze_flow_candidate(
        flow, component_snapshot, flow_strategy="junction_aware", **kwargs
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "legacy_vs_shadow",
        "officialStrategy": "legacy",
        "officialFlow": copy.deepcopy(legacy["legacyFlow"]),
        "legacy": legacy,
        "junctionAware": shadow,
        "officialResultChanged": False,
        "feedsStride": "legacy_only",
    }
