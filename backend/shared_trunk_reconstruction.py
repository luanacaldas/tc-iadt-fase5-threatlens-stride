"""Shadow-only shared-trunk reconstruction and branch pairing for TL-004D."""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

from backend.endpoint_validation import build_component_contact_catalog
from backend.geometric_events import GeometryParameters, extract_geometric_event_catalog
from backend.intersection_validation import classify_intersections


SCHEMA_VERSION = "1.0"
STRATEGY_REVISION = "tl004d-shared-trunks-v1"
TRUNK_CLASSIFICATIONS = (
    "valid_fan_in",
    "valid_fan_out",
    "shared_trunk",
    "ambiguous_shared_trunk",
    "invalid_branch_pairing",
    "insufficient_branch_evidence",
)


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"{prefix}-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]}"


def _point_segment_distance(
    point: Sequence[float], start: Sequence[float], end: Sequence[float]
) -> float:
    px, py = float(point[0]), float(point[1])
    x1, y1, x2, y2 = float(start[0]), float(start[1]), float(end[0]), float(end[1])
    dx, dy = x2 - x1, y2 - y1
    length_squared = dx * dx + dy * dy
    ratio = ((px - x1) * dx + (py - y1) * dy) / length_squared
    ratio = min(1.0, max(0.0, ratio))
    return math.hypot(px - (x1 + ratio * dx), py - (y1 + ratio * dy))


def _normalize_terminal_ports(ports: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    allowed_directions = {"outgoing", "incoming", "unknown", "bidirectional"}
    for port in ports:
        component_id = str(port.get("componentId") or "")
        coordinates = port.get("coordinates")
        direction = str(port.get("direction") or "unknown")
        confidence = float(port.get("confidence", 0.0))
        if not component_id or not isinstance(coordinates, Sequence) or len(coordinates) != 2:
            raise ValueError("terminal ports require componentId and coordinates [x, y]")
        if direction not in allowed_directions or not 0 <= confidence <= 1:
            raise ValueError("terminal port direction or confidence is invalid")
        normalized.append(
            {
                "id": str(port.get("id") or _stable_id("tport", dict(port))),
                "componentId": component_id,
                "coordinates": [float(coordinates[0]), float(coordinates[1])],
                "direction": direction,
                "directionConfidence": confidence,
                "segmentId": str(port.get("segmentId") or ""),
                "confidence": str(port.get("contactConfidence") or "reviewed"),
                "evidence": str(port.get("evidence") or "reviewed_terminal_port"),
                "provenance": str(port.get("provenance") or "input"),
                "reviewed": bool(port.get("reviewed", False)),
            }
        )
    return sorted(normalized, key=lambda item: (item["componentId"], item["coordinates"], item["id"]))


def _union_find(segment_ids: Sequence[str]):
    parents = {segment_id: segment_id for segment_id in segment_ids}

    def find(item: str) -> str:
        while parents[item] != item:
            parents[item] = parents[parents[item]]
            item = parents[item]
        return item

    def union(first: str, second: str) -> None:
        first_root, second_root = find(first), find(second)
        if first_root != second_root:
            parents[max(first_root, second_root)] = min(first_root, second_root)

    return parents, find, union


def _relation(source: str, destination: str, trunk_id: str, reason: str) -> dict[str, Any]:
    payload = {"from": source, "to": destination, "trunkId": trunk_id}
    return {
        "id": _stable_id("rel", payload),
        "from": source,
        "to": destination,
        "trunkId": trunk_id,
        "reason": reason,
        "shadowOnly": True,
        "officialEligible": False,
    }


def _component_roles(ports: Sequence[Mapping[str, Any]], confidence_threshold: float) -> dict[str, set[str]]:
    roles: dict[str, set[str]] = defaultdict(set)
    for port in ports:
        if float(port["directionConfidence"]) < confidence_threshold:
            roles[port["componentId"]].add("unknown")
        elif port["direction"] == "bidirectional":
            roles[port["componentId"]].update(("outgoing", "incoming"))
        else:
            roles[port["componentId"]].add(port["direction"])
    return roles


def _terminal_arm(port: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "portId": port["id"],
        "componentId": port["componentId"],
        "segmentId": port["canonicalSegmentId"],
        "coordinates": copy.deepcopy(port["coordinates"]),
        "direction": port["direction"],
        "directionConfidence": port["directionConfidence"],
        "provenance": port["provenance"],
    }


def reconstruct_shared_trunks(
    segments: Iterable[Sequence[float] | Mapping[str, Any]],
    components: Iterable[Mapping[str, Any]] = (),
    terminal_ports: Iterable[Mapping[str, Any]] = (),
    explicit_junctions: Iterable[Mapping[str, Any]] = (),
    *,
    barrier_component_ids: Iterable[str] = (),
    geometry_parameters: GeometryParameters | None = None,
    scale: float = 1.0,
    line_width: float = 1.0,
    direction_confidence_threshold: float = 0.7,
    parallel_arm_tolerance_degrees: float = 20.0,
) -> dict[str, Any]:
    """Reconstruct local fan-in/out relations without changing official flows."""
    raw_segments = copy.deepcopy(list(segments))
    raw_components = copy.deepcopy(list(components))
    raw_ports = copy.deepcopy(list(terminal_ports))
    raw_markers = copy.deepcopy(list(explicit_junctions))
    snapshot = copy.deepcopy((raw_segments, raw_components, raw_ports, raw_markers))
    if not 0 <= direction_confidence_threshold <= 1:
        raise ValueError("direction_confidence_threshold must be between zero and one")
    if not 0 <= parallel_arm_tolerance_degrees < 90:
        raise ValueError("parallel_arm_tolerance_degrees must be between zero and ninety")
    normalized_ports = _normalize_terminal_ports(raw_ports)
    barriers = {str(item) for item in barrier_component_ids}

    catalog = extract_geometric_event_catalog(
        raw_segments,
        raw_components,
        raw_markers,
        parameters=geometry_parameters,
        scale=scale,
        line_width=line_width,
    )
    intersections = classify_intersections(
        raw_segments,
        raw_components,
        raw_markers,
        geometry_parameters=geometry_parameters,
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
    segment_by_id = {str(item["id"]): item for item in catalog["segments"]}
    input_to_canonical = {
        str(input_id): str(segment["id"])
        for segment in catalog["segments"]
        for input_id in segment.get("inputIds") or []
    }
    parents, find, union = _union_find(sorted(segment_by_id))
    blocked_local_events = []
    for event in intersections["events"]:
        angles = [float(arm["angle"]) for arm in event["arms"]]
        near_parallel = any(
            min(abs(first - second) % 360, 360 - (abs(first - second) % 360))
            <= parallel_arm_tolerance_degrees
            for first, second in itertools.combinations(angles, 2)
        )
        if (
            near_parallel
            and event["classification"] in {"elbow", "bifurcation"}
            and not event["visualJunctionMarker"]["qualified"]
        ):
            blocked_local_events.append(
                {
                    "eventId": event["id"],
                    "classification": "invalid_branch_pairing",
                    "reason": "near_parallel_arms_without_explicit_junction",
                    "angles": angles,
                }
            )
            continue
        arm_to_segment = {arm["id"]: arm["segmentId"] for arm in event["arms"]}
        for pair in event["allowedBranchPairs"]:
            first, second = (arm_to_segment[item] for item in pair["armIds"])
            if first != second:
                union(first, second)

    groups: dict[str, set[str]] = defaultdict(set)
    for segment_id in segment_by_id:
        groups[find(segment_id)].add(segment_id)

    effective = catalog["parameters"]["effective"]
    assignment_tolerance = float(effective["nearbyComponentDistance"])
    assigned_ports = []
    for port in normalized_ports:
        canonical_id = input_to_canonical.get(port["segmentId"])
        if not canonical_id:
            ranked = sorted(
                (
                    _point_segment_distance(port["coordinates"], segment["start"], segment["end"]),
                    str(segment["id"]),
                )
                for segment in catalog["segments"]
            )
            if ranked and (ranked[0][0] <= assignment_tolerance or port["reviewed"]):
                canonical_id = ranked[0][1]
        assigned_ports.append({**port, "canonicalSegmentId": canonical_id})

    reviewed_keys = {(item["componentId"], item["canonicalSegmentId"]) for item in assigned_ports}
    for event in contacts["events"]:
        component_id = str(event["geometricEvidence"]["componentId"])
        for segment_id in event["sourceSegments"]:
            key = component_id, str(segment_id)
            if key in reviewed_keys:
                continue
            assigned_ports.append(
                {
                    "id": _stable_id("tport", {"eventId": event["id"], "segmentId": segment_id}),
                    "componentId": component_id,
                    "coordinates": copy.deepcopy(event["coordinates"]),
                    "direction": "unknown",
                    "directionConfidence": 0.0,
                    "segmentId": "",
                    "canonicalSegmentId": str(segment_id),
                    "confidence": "high",
                    "evidence": "tl004b_component_contact",
                    "provenance": event["id"],
                    "reviewed": False,
                }
            )

    trunks = []
    experimental_relations = []
    review_relations = []
    prevented_cliques = []
    for group_id, group_segments in sorted(groups.items()):
        group_ports = [
            port for port in assigned_ports if port.get("canonicalSegmentId") in group_segments
        ]
        terminal_components = sorted({port["componentId"] for port in group_ports})
        group_events = [
            event
            for event in intersections["events"]
            if set(event["sourceSegments"]) & group_segments
        ]
        junction_events = [
            event
            for event in group_events
            if event["classification"] in {"bifurcation", "explicit_junction"}
        ]
        if len(terminal_components) < 2 and not junction_events:
            continue
        trunk_id = _stable_id(
            "trunk",
            {"segments": sorted(group_segments), "terminals": terminal_components},
        )
        roles = _component_roles(group_ports, direction_confidence_threshold)
        input_arms = [
            _terminal_arm(port)
            for port in group_ports
            if port["direction"] in {"outgoing", "bidirectional"}
            and port["directionConfidence"] >= direction_confidence_threshold
        ]
        output_arms = [
            _terminal_arm(port)
            for port in group_ports
            if port["direction"] in {"incoming", "bidirectional"}
            and port["directionConfidence"] >= direction_confidence_threshold
        ]
        unknown_arms = [
            _terminal_arm(port)
            for port in group_ports
            if port["direction"] == "unknown"
            or port["directionConfidence"] < direction_confidence_threshold
        ]
        segment_provenance = sorted(
            {
                str(provenance)
                for segment_id in group_segments
                for provenance in segment_by_id[segment_id].get("provenance", [])
            }
        )
        sources = sorted(component for component, values in roles.items() if "outgoing" in values)
        destinations = sorted(component for component, values in roles.items() if "incoming" in values)
        unknown = sorted(
            component
            for component in terminal_components
            if component not in sources and component not in destinations
        )
        group_barriers = sorted(set(terminal_components) & barriers)
        relations = []
        pairing_options = []
        classification = "insufficient_branch_evidence"
        confidence = "low"
        reasons = []

        if group_barriers:
            for barrier in group_barriers:
                relations.extend(
                    _relation(source, barrier, trunk_id, "first intermediate component barrier")
                    for source in sources
                    if source != barrier
                )
                if "outgoing" in roles.get(barrier, set()):
                    relations.extend(
                        _relation(barrier, destination, trunk_id, "adjacent relation after barrier")
                        for destination in destinations
                        if destination != barrier
                    )
            classification = "shared_trunk"
            confidence = "high"
            reasons.append("component_barrier_forces_adjacent_relations")
        elif len(sources) == 1 and len(destinations) >= 2 and not unknown:
            relations = [
                _relation(sources[0], destination, trunk_id, "one source feeds multiple branches")
                for destination in destinations
                if destination != sources[0]
            ]
            classification = "valid_fan_out"
            confidence = "high"
            reasons.append("single_outgoing_terminal_with_multiple_incoming_terminals")
        elif len(sources) >= 2 and len(destinations) == 1 and not unknown:
            relations = [
                _relation(source, destinations[0], trunk_id, "multiple branches converge on one destination")
                for source in sources
                if source != destinations[0]
            ]
            classification = "valid_fan_in"
            confidence = "high"
            reasons.append("multiple_outgoing_terminals_with_single_incoming_terminal")
        elif len(sources) == 1 and len(destinations) == 1 and not unknown:
            relations = [_relation(sources[0], destinations[0], trunk_id, "direct shared-trunk pairing")]
            classification = "shared_trunk"
            confidence = "medium"
            reasons.append("single_directionally_supported_pair")
        elif not sources and not destinations and len(terminal_components) >= 3:
            classification = "ambiguous_shared_trunk"
            reasons.append("terminal_direction_is_not_available")
        elif (sources and not destinations) or (destinations and not sources):
            classification = "invalid_branch_pairing"
            reasons.append("only_same_role_terminals_are_available")
        else:
            classification = "insufficient_branch_evidence"
            reasons.append("ports_or_direction_do_not_support_unique_pairing")

        if not relations:
            pairing_options = [
                {"from": first, "to": second}
                for first, second in itertools.permutations(terminal_components, 2)
            ]
            review_relations.extend(
                {**item, "trunkId": trunk_id, "status": "review_only"}
                for item in pairing_options
            )
        relation_pairs = {(item["from"], item["to"]) for item in relations}
        all_pairs = set(itertools.permutations(terminal_components, 2))
        prevented = [
            {"from": source, "to": destination, "trunkId": trunk_id}
            for source, destination in sorted(all_pairs - relation_pairs)
        ]
        prevented_cliques.extend(prevented)
        experimental_relations.extend(relations)
        trunks.append(
            {
                "id": trunk_id,
                "classification": classification,
                "segmentIds": sorted(group_segments),
                "segmentProvenance": segment_provenance,
                "eventIds": sorted(event["id"] for event in group_events),
                "junctionEventIds": sorted(event["id"] for event in junction_events),
                "junctionArms": [
                    arm
                    for event in junction_events
                    for arm in event["arms"]
                ],
                "inputArms": input_arms,
                "outputArms": output_arms,
                "unknownDirectionArms": unknown_arms,
                "connectedPorts": group_ports,
                "terminalComponents": terminal_components,
                "sourceComponents": sources,
                "destinationComponents": destinations,
                "unknownDirectionComponents": unknown,
                "barrierComponents": group_barriers,
                "allowedPairings": relations,
                "blockedPairings": prevented,
                "pairingOptionsConsidered": pairing_options,
                "confidence": confidence,
                "reasons": reasons,
                "parameters": {
                    "directionConfidenceThreshold": direction_confidence_threshold,
                    "parallelArmToleranceDegrees": parallel_arm_tolerance_degrees,
                    "geometry": copy.deepcopy(effective),
                },
                "evidence": {
                    "tl004aEventCount": len(group_events),
                    "tl004bPortCount": len(group_ports),
                    "tl004cJunctionCount": len(junction_events),
                },
                "shadowOnly": True,
                "officialEligible": False,
            }
        )

    trunks.sort(key=lambda item: item["id"])
    experimental_relations.sort(key=lambda item: (item["from"], item["to"], item["id"]))
    review_relations.sort(key=lambda item: (item["trunkId"], item["from"], item["to"]))
    prevented_cliques.sort(key=lambda item: (item["trunkId"], item["from"], item["to"]))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "strategyRevision": STRATEGY_REVISION,
        "mode": "shadow",
        "officialEligible": False,
        "dependencies": [
            "backend/geometric_events.py",
            "backend/endpoint_validation.py",
            "backend/intersection_validation.py",
        ],
        "trunks": trunks,
        "experimentalRelations": experimental_relations,
        "reviewOnlyRelations": review_relations,
        "preventedCliqueRelations": prevented_cliques,
        "blockedLocalEvents": sorted(blocked_local_events, key=lambda item: item["eventId"]),
        "inputMutation": snapshot != (raw_segments, raw_components, raw_ports, raw_markers),
        "parameters": {
            "directionConfidenceThreshold": direction_confidence_threshold,
            "parallelArmToleranceDegrees": parallel_arm_tolerance_degrees,
            "scale": scale,
            "lineWidth": line_width,
        },
    }


def compare_legacy_and_shadow_trunks(
    official_flows: Iterable[Mapping[str, Any]],
    segments: Iterable[Sequence[float] | Mapping[str, Any]],
    components: Iterable[Mapping[str, Any]] = (),
    terminal_ports: Iterable[Mapping[str, Any]] = (),
    explicit_junctions: Iterable[Mapping[str, Any]] = (),
    **kwargs: Any,
) -> dict[str, Any]:
    legacy = copy.deepcopy(list(official_flows))
    shadow = reconstruct_shared_trunks(
        segments,
        components,
        terminal_ports,
        explicit_junctions,
        **kwargs,
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "legacy_vs_shadow",
        "officialStrategy": "legacy",
        "shadowStrategy": "junction_aware_shared_trunks",
        "officialFlows": legacy,
        "shadow": shadow,
        "officialFlowsChanged": False,
        "officialDirectionChanges": 0,
        "feedsStride": "legacy_only",
    }
