"""Shadow-only transitive-shortcut classification for TL-004E."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import defaultdict, deque
from typing import Any, Iterable, Mapping, Sequence

from backend.endpoint_validation import analyze_flow_candidate
from backend.shared_trunk_reconstruction import reconstruct_shared_trunks


SCHEMA_VERSION = "1.0"
STRATEGY_REVISION = "tl004e-transitive-shortcuts-v1"
SHORTCUT_CLASSIFICATIONS = (
    "direct_edge_confirmed",
    "transitive_shortcut",
    "intermediate_component_barrier",
    "adjacent_relation",
    "ambiguous_path",
    "insufficient_evidence",
    "review_only",
)


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"{prefix}-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]}"


def _edge(item: Mapping[str, Any]) -> tuple[str, str]:
    return str(item.get("from") or ""), str(item.get("to") or "")


def _path_segments(flow: Mapping[str, Any]) -> list[dict[str, Any]]:
    points = flow.get("pathPoints") or []
    identifiers = list(flow.get("segmentIds") or [])
    return [
        {
            "id": identifiers[index] if index < len(identifiers) else f"{flow.get('id', 'flow')}:segment:{index}",
            "start": list(start),
            "end": list(end),
            "provenance": str(flow.get("provenance") or flow.get("id") or "candidate"),
        }
        for index, (start, end) in enumerate(zip(points, points[1:]))
        if start != end
    ]


def _ports_for_flow(flow: Mapping[str, Any]) -> list[dict[str, Any]]:
    points = flow.get("pathPoints") or []
    segments = _path_segments(flow)
    if len(points) < 2 or not segments:
        return []
    confidence = float(flow.get("directionConfidence") or 0)
    provenance = str(flow.get("provenance") or flow.get("id") or "candidate")
    return [
        {
            "id": f"{flow.get('id', 'flow')}:source-port",
            "componentId": str(flow["from"]),
            "coordinates": list(points[0]),
            "segmentId": segments[0]["id"],
            "direction": "outgoing",
            "confidence": confidence,
            "reviewed": True,
            "evidence": str(flow.get("directionEvidence") or "candidate_direction"),
            "provenance": provenance,
        },
        {
            "id": f"{flow.get('id', 'flow')}:destination-port",
            "componentId": str(flow["to"]),
            "coordinates": list(points[-1]),
            "segmentId": segments[-1]["id"],
            "direction": "incoming",
            "confidence": confidence,
            "reviewed": True,
            "evidence": str(flow.get("directionEvidence") or "candidate_direction"),
            "provenance": provenance,
        },
    ]


def _shortest_indirect_path(
    source: str,
    destination: str,
    relations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    adjacency: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for index, relation in enumerate(relations):
        start, end = _edge(relation)
        if not start or not end or (start, end) == (source, destination):
            continue
        adjacency[start].append((end, index))
    for values in adjacency.values():
        values.sort(key=lambda item: (item[0], item[1]))
    queue = deque([(source, [])])
    visited = {source}
    while queue:
        node, path = queue.popleft()
        for next_node, relation_index in adjacency.get(node, []):
            next_path = [*path, relation_index]
            if next_node == destination and len(next_path) >= 2:
                return [copy.deepcopy(dict(relations[item])) for item in next_path]
            if next_node not in visited:
                visited.add(next_node)
                queue.append((next_node, next_path))
    return []


def _point_line_distance(point: Sequence[float], start: Sequence[float], end: Sequence[float]) -> float:
    px, py = float(point[0]), float(point[1])
    x1, y1, x2, y2 = float(start[0]), float(start[1]), float(end[0]), float(end[1])
    dx, dy = x2 - x1, y2 - y1
    length = dx * dx + dy * dy
    if length == 0:
        return math.hypot(px - x1, py - y1)
    ratio = ((px - x1) * dx + (py - y1) * dy) / length
    projected = x1 + ratio * dx, y1 + ratio * dy
    return math.hypot(px - projected[0], py - projected[1])


def _segments_overlap(first: Mapping[str, Any], second: Mapping[str, Any], tolerance: float) -> bool:
    first_start, first_end = first["start"], first["end"]
    second_start, second_end = second["start"], second["end"]
    first_vector = float(first_end[0]) - float(first_start[0]), float(first_end[1]) - float(first_start[1])
    second_vector = float(second_end[0]) - float(second_start[0]), float(second_end[1]) - float(second_start[1])
    first_length = math.hypot(*first_vector)
    second_length = math.hypot(*second_vector)
    if first_length == 0 or second_length == 0:
        return False
    cosine = abs(
        (first_vector[0] * second_vector[0] + first_vector[1] * second_vector[1])
        / (first_length * second_length)
    )
    if cosine < math.cos(math.radians(10)):
        return False
    if max(
        _point_line_distance(second_start, first_start, first_end),
        _point_line_distance(second_end, first_start, first_end),
    ) > tolerance:
        return False
    axis = 0 if abs(first_vector[0]) >= abs(first_vector[1]) else 1
    first_range = sorted((float(first_start[axis]), float(first_end[axis])))
    second_range = sorted((float(second_start[axis]), float(second_end[axis])))
    overlap = min(first_range[1], second_range[1]) - max(first_range[0], second_range[0])
    return overlap > tolerance


def _shared_segment_evidence(
    candidate: Mapping[str, Any], indirect: Sequence[Mapping[str, Any]], tolerance: float
) -> list[dict[str, Any]]:
    candidate_segments = _path_segments(candidate)
    evidence = []
    for relation in indirect:
        relation_segments = _path_segments(relation)
        shared_ids = sorted(
            {item["id"] for item in candidate_segments}
            & {item["id"] for item in relation_segments}
        )
        geometric_pairs = sorted(
            [
                [first["id"], second["id"]]
                for first in candidate_segments
                for second in relation_segments
                if _segments_overlap(first, second, tolerance)
            ]
        )
        if shared_ids or geometric_pairs:
            evidence.append(
                {
                    "relation": {"from": relation["from"], "to": relation["to"]},
                    "sharedSegmentIds": shared_ids,
                    "geometricallyOverlappingSegments": geometric_pairs,
                }
            )
    return evidence


def _direct_evidence(
    candidate: Mapping[str, Any],
    confirmed: Mapping[tuple[str, str], Mapping[str, Any]],
    endpoint_analysis: Mapping[str, Any],
    shared_segments: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    edge = _edge(candidate)
    declared = copy.deepcopy(dict(confirmed.get(edge) or candidate.get("directEvidence") or {}))
    endpoint_decisions = endpoint_analysis.get("endpointDecisions") or []
    own_ports = len(endpoint_decisions) == 2 and all(
        item.get("classification") == "confirmed_contact" for item in endpoint_decisions
    )
    own_segments = bool(_path_segments(candidate)) and not bool(shared_segments)
    benchmark_or_human = str(declared.get("source") or "") in {
        "benchmark",
        "human_review",
        "reviewed_fixture",
    }
    independent = bool(
        declared.get("independent")
        or benchmark_or_human
        or (
            own_ports
            and own_segments
            and declared.get("independentGeometry", False)
        )
    )
    return {
        "confirmed": independent,
        "source": declared.get("source"),
        "ownSegments": own_segments,
        "ownSourceAndDestinationPorts": own_ports,
        "independentGeometry": bool(declared.get("independentGeometry", False)),
        "ownArrowhead": bool(declared.get("ownArrowhead", False)),
        "benchmarkOrHumanConfirmed": benchmark_or_human,
        "details": declared,
    }


def classify_transitive_shortcuts(
    candidates: Iterable[Mapping[str, Any]],
    components: Iterable[Mapping[str, Any]],
    *,
    segments: Iterable[Sequence[float] | Mapping[str, Any]] = (),
    terminal_ports: Iterable[Mapping[str, Any]] = (),
    explicit_junctions: Iterable[Mapping[str, Any]] = (),
    adjacent_relations: Iterable[Mapping[str, Any]] = (),
    confirmed_direct_edges: Iterable[Mapping[str, Any]] = (),
    human_confirmed_shortcuts: Iterable[Mapping[str, Any]] = (),
    scale: float = 1.0,
    line_width: float = 1.0,
    overlap_tolerance: float = 3.0,
) -> dict[str, Any]:
    """Classify candidate shortcuts without changing or removing official flows."""
    raw_candidates = copy.deepcopy(list(candidates))
    raw_components = copy.deepcopy(list(components))
    raw_segments = copy.deepcopy(list(segments))
    raw_ports = copy.deepcopy(list(terminal_ports))
    raw_junctions = copy.deepcopy(list(explicit_junctions))
    raw_adjacency = copy.deepcopy(list(adjacent_relations))
    raw_confirmed = copy.deepcopy(list(confirmed_direct_edges))
    raw_human = copy.deepcopy(list(human_confirmed_shortcuts))
    if overlap_tolerance < 0:
        raise ValueError("overlap_tolerance must be non-negative")
    if not raw_segments:
        raw_segments = [segment for candidate in raw_candidates for segment in _path_segments(candidate)]
    if not raw_ports:
        raw_ports = [port for candidate in raw_candidates for port in _ports_for_flow(candidate)]
    trunk_analysis = reconstruct_shared_trunks(
        raw_segments,
        raw_components,
        raw_ports,
        raw_junctions,
        scale=scale,
        line_width=line_width,
    )
    confirmed_index = {_edge(item): item for item in raw_confirmed}
    human_index = {_edge(item): item for item in raw_human}
    adjacency_edges = {_edge(item) for item in raw_adjacency}
    decisions = []
    for candidate in sorted(raw_candidates, key=lambda item: (str(item.get("id") or ""), _edge(item))):
        source, destination = _edge(candidate)
        if not source or not destination:
            raise ValueError("candidates require non-empty from and to component IDs")
        endpoint_analysis = analyze_flow_candidate(
            candidate,
            raw_components,
            flow_strategy="junction_aware",
            scale=scale,
            line_width=line_width,
        )
        indirect = _shortest_indirect_path(source, destination, raw_adjacency)
        intermediate_components = [item["to"] for item in indirect[:-1]]
        shared_segments = _shared_segment_evidence(candidate, indirect, overlap_tolerance)
        direct = _direct_evidence(candidate, confirmed_index, endpoint_analysis, shared_segments)
        first_barrier = endpoint_analysis.get("firstIntermediateBarrier")
        endpoint_redirect = any(
            item.get("classification") == "wrong_component_contact"
            for item in endpoint_analysis.get("endpointDecisions") or []
        )
        provenance = str(candidate.get("provenance") or candidate.get("id") or "")
        related_trunks = [
            item
            for item in trunk_analysis["trunks"]
            if provenance and provenance in (item.get("segmentProvenance") or [])
        ]
        reasons = []
        classification = "insufficient_evidence"
        action = "review"
        confidence = "low"

        if direct["confirmed"]:
            classification, action, confidence = "direct_edge_confirmed", "keep", "high"
            reasons.append("independent_direct_connector_is_confirmed")
        elif (source, destination) in adjacency_edges and not indirect:
            classification, action, confidence = "adjacent_relation", "keep", "high"
            reasons.append("candidate_is_an_evidenced_adjacent_relation")
        elif indirect and (source, destination) in human_index:
            classification, action, confidence = "transitive_shortcut", "block", "high"
            reasons.extend(("human_review_confirms_shortcut", "adjacent_chain_is_available"))
        elif indirect and (first_barrier or endpoint_redirect) and not direct["confirmed"]:
            classification, action, confidence = "transitive_shortcut", "block", "high"
            reasons.extend(("endpoint_or_barrier_stops_direct_path", "adjacent_chain_is_available"))
        elif indirect and shared_segments and not candidate.get("ambiguous", False):
            classification, action, confidence = "transitive_shortcut", "block", "medium"
            reasons.extend(("candidate_reuses_indirect_path_segments", "adjacent_chain_is_available"))
        elif first_barrier:
            classification, action, confidence = "intermediate_component_barrier", "decompose", "high"
            reasons.append("component_barrier_interrupts_candidate_path")
        elif candidate.get("forceReview", False):
            classification, action, confidence = "review_only", "review", "low"
            reasons.append("candidate_is_explicitly_reserved_for_review")
        elif indirect:
            classification, action, confidence = "ambiguous_path", "review", "low"
            reasons.append("indirect_path_exists_without_safe_suppression_evidence")
        elif candidate.get("ambiguous", False):
            classification, action, confidence = "ambiguous_path", "review", "low"
            reasons.append("path_geometry_is_ambiguous")
        else:
            reasons.append("direct_or_indirect_support_is_insufficient")

        decision_payload = {
            "candidateId": str(candidate.get("id") or ""),
            "from": source,
            "to": destination,
        }
        decisions.append(
            {
                "id": _stable_id("shortcut", decision_payload),
                **decision_payload,
                "legacyEdge": copy.deepcopy(candidate),
                "classification": classification,
                "shadowAction": action,
                "confidence": confidence,
                "reasons": reasons,
                "completePath": copy.deepcopy(candidate.get("pathPoints") or []),
                "intermediateComponents": intermediate_components,
                "touchedPorts": copy.deepcopy(endpoint_analysis.get("ports") or []),
                "barriers": copy.deepcopy(endpoint_analysis.get("barriers") or []),
                "firstIntermediateBarrier": copy.deepcopy(first_barrier),
                "endpointDecisions": copy.deepcopy(endpoint_analysis.get("endpointDecisions") or []),
                "adjacentRelations": copy.deepcopy(indirect),
                "directEdgeEvidence": direct,
                "arrowheadEvidence": {
                    "directionEvidence": candidate.get("directionEvidence"),
                    "directionConfidence": candidate.get("directionConfidence"),
                    "arrowheadScores": copy.deepcopy(candidate.get("arrowheadScores")),
                },
                "sharedSegmentEvidence": shared_segments,
                "trunkIds": sorted(item["id"] for item in related_trunks),
                "junctionEventIds": sorted(
                    {event_id for item in related_trunks for event_id in item["junctionEventIds"]}
                ),
                "recommendedAdjacentRelations": copy.deepcopy(indirect) if action in {"block", "decompose"} else [],
                "officialResultChanged": False,
                "officialDirectionChanged": False,
                "officialEligible": False,
            }
        )

    classification_counts = defaultdict(int)
    action_counts = defaultdict(int)
    for decision in decisions:
        classification_counts[decision["classification"]] += 1
        action_counts[decision["shadowAction"]] += 1
    return {
        "schemaVersion": SCHEMA_VERSION,
        "strategyRevision": STRATEGY_REVISION,
        "mode": "shadow",
        "officialEligible": False,
        "dependencies": [
            "backend/geometric_events.py",
            "backend/endpoint_validation.py",
            "backend/intersection_validation.py",
            "backend/shared_trunk_reconstruction.py",
        ],
        "decisions": decisions,
        "classificationCounts": dict(sorted(classification_counts.items())),
        "actionCounts": dict(sorted(action_counts.items())),
        "trunkEvidence": trunk_analysis,
        "officialEdgesChanged": 0,
        "officialDirectionChanges": 0,
        "feedsStride": "legacy_only",
        "inputMutation": False,
        "parameters": {
            "scale": scale,
            "lineWidth": line_width,
            "overlapTolerance": overlap_tolerance,
        },
    }


def compare_legacy_and_shadow_shortcuts(
    official_flows: Iterable[Mapping[str, Any]],
    components: Iterable[Mapping[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    legacy = copy.deepcopy(list(official_flows))
    shadow = classify_transitive_shortcuts(legacy, components, **kwargs)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "legacy_vs_shadow",
        "officialStrategy": "legacy",
        "shadowStrategy": "junction_aware_transitive_shortcuts",
        "officialFlows": legacy,
        "shadow": shadow,
        "officialFlowsChanged": False,
        "officialDirectionChanges": 0,
        "feedsStride": "legacy_only",
    }
