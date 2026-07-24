"""Pure, deterministic geometric events for the TL-004A shadow foundation."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "1.0"
EXTRACTOR_REVISION = "tl004a-geometric-events-v1"
EVENT_TYPES = (
    "endpoint",
    "continuation",
    "elbow",
    "crossing",
    "explicit_junction",
    "bifurcation",
    "component_port",
    "component_boundary_intersection",
)


@dataclass(frozen=True)
class GeometryParameters:
    """Configurable tolerances expressed in reference-image pixels."""

    endpoint_cluster_tolerance: float = 2.5
    intersection_tolerance: float = 1.25
    component_contact_tolerance: float = 1.0
    nearby_component_distance: float = 8.0
    collinear_tolerance_degrees: float = 12.0
    marker_tolerance: float = 1.0
    line_width_tolerance_factor: float = 0.5
    coordinate_precision: int = 3

    def effective(self, scale: float, line_width: float) -> dict[str, float | int]:
        if scale <= 0 or line_width <= 0:
            raise ValueError("scale and line_width must be positive")
        thickness_margin = line_width * self.line_width_tolerance_factor
        return {
            "endpointClusterTolerance": self.endpoint_cluster_tolerance * scale + thickness_margin,
            "intersectionTolerance": self.intersection_tolerance * scale + thickness_margin * 0.5,
            "componentContactTolerance": self.component_contact_tolerance * scale + thickness_margin * 0.5,
            "nearbyComponentDistance": self.nearby_component_distance * scale + thickness_margin,
            "collinearToleranceDegrees": self.collinear_tolerance_degrees,
            "markerTolerance": self.marker_tolerance * scale + thickness_margin * 0.5,
            "coordinatePrecision": self.coordinate_precision,
            "scale": scale,
            "lineWidth": line_width,
        }


@dataclass(frozen=True)
class CanonicalSegment:
    id: str
    start: tuple[float, float]
    end: tuple[float, float]
    provenance: tuple[str, ...]
    input_ids: tuple[str, ...]
    duplicate_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "start": list(self.start),
            "end": list(self.end),
            "provenance": list(self.provenance),
            "inputIds": list(self.input_ids),
            "duplicateCount": self.duplicate_count,
        }


@dataclass(frozen=True)
class GeometricEvent:
    id: str
    type: str
    coordinates: tuple[float, float]
    source_segments: tuple[str, ...]
    arm_angles: tuple[float, ...]
    provenance: Mapping[str, Any]
    nearby_components: tuple[str, ...]
    classification: str
    confidence: str
    parameters: Mapping[str, Any]
    geometric_evidence: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "coordinates": list(self.coordinates),
            "sourceSegments": list(self.source_segments),
            "armAngles": list(self.arm_angles),
            "provenance": dict(self.provenance),
            "nearbyComponents": list(self.nearby_components),
            "classification": self.classification,
            "confidence": self.confidence,
            "parameters": dict(self.parameters),
            "geometricEvidence": dict(self.geometric_evidence),
        }


def _rounded(value: float, precision: int) -> float:
    rounded = round(float(value), precision)
    return 0.0 if rounded == -0.0 else rounded


def _point(value: Sequence[float], precision: int) -> tuple[float, float]:
    if len(value) != 2:
        raise ValueError("points must contain exactly two coordinates")
    return (_rounded(value[0], precision), _rounded(value[1], precision))


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"{prefix}-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]}"


def _canonical_segment_endpoints(
    start: tuple[float, float], end: tuple[float, float]
) -> tuple[tuple[float, float], tuple[float, float]]:
    return (start, end) if start <= end else (end, start)


def _read_segment(
    raw: Sequence[float] | Mapping[str, Any], precision: int
) -> tuple[tuple[float, float], tuple[float, float], str, str]:
    if isinstance(raw, Mapping):
        if "start" in raw and "end" in raw:
            start = _point(raw["start"], precision)
            end = _point(raw["end"], precision)
        elif "points" in raw and len(raw["points"]) == 2:
            start = _point(raw["points"][0], precision)
            end = _point(raw["points"][1], precision)
        else:
            raise ValueError("segment mappings require start/end or two points")
        provenance = str(raw.get("provenance") or "input")
        input_id = str(raw.get("id") or "")
    else:
        if len(raw) != 4:
            raise ValueError("segment sequences must be [x1, y1, x2, y2]")
        start = _point(raw[:2], precision)
        end = _point(raw[2:], precision)
        provenance = "input"
        input_id = ""
    if start == end:
        raise ValueError("zero-length segments are not supported")
    return (*_canonical_segment_endpoints(start, end), provenance, input_id)


def canonicalize_segments(
    segments: Iterable[Sequence[float] | Mapping[str, Any]],
    parameters: GeometryParameters | None = None,
) -> tuple[CanonicalSegment, ...]:
    """Normalize orientation, deduplicate geometry, and assign stable IDs."""
    params = parameters or GeometryParameters()
    grouped: dict[
        tuple[tuple[float, float], tuple[float, float]], dict[str, list[str] | int]
    ] = {}
    for raw in segments:
        start, end, provenance, input_id = _read_segment(raw, params.coordinate_precision)
        entry = grouped.setdefault(
            (start, end), {"provenance": [], "inputIds": [], "count": 0}
        )
        entry["count"] = int(entry["count"]) + 1
        cast_provenance = entry["provenance"]
        cast_ids = entry["inputIds"]
        assert isinstance(cast_provenance, list) and isinstance(cast_ids, list)
        cast_provenance.append(provenance)
        if input_id:
            cast_ids.append(input_id)

    normalized = []
    for (start, end), metadata in grouped.items():
        segment_id = _stable_id("seg", {"start": start, "end": end})
        normalized.append(
            CanonicalSegment(
                id=segment_id,
                start=start,
                end=end,
                provenance=tuple(sorted(set(metadata["provenance"]))),
                input_ids=tuple(sorted(set(metadata["inputIds"]))),
                duplicate_count=int(metadata["count"]),
            )
        )
    return tuple(sorted(normalized, key=lambda item: item.id))


def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return math.hypot(first[0] - second[0], first[1] - second[1])


def _cross(first: tuple[float, float], second: tuple[float, float]) -> float:
    return first[0] * second[1] - first[1] * second[0]


def _segment_intersection(
    first: CanonicalSegment,
    second: CanonicalSegment,
    tolerance: float,
) -> dict[str, Any] | None:
    p = first.start
    q = second.start
    r = (first.end[0] - first.start[0], first.end[1] - first.start[1])
    s = (second.end[0] - second.start[0], second.end[1] - second.start[1])
    denominator = _cross(r, s)
    if abs(denominator) <= 1e-9:
        return None
    q_minus_p = (q[0] - p[0], q[1] - p[1])
    first_ratio = _cross(q_minus_p, s) / denominator
    second_ratio = _cross(q_minus_p, r) / denominator
    first_length = max(_distance(first.start, first.end), 1e-9)
    second_length = max(_distance(second.start, second.end), 1e-9)
    first_margin = tolerance / first_length
    second_margin = tolerance / second_length
    if not (-first_margin <= first_ratio <= 1 + first_margin):
        return None
    if not (-second_margin <= second_ratio <= 1 + second_margin):
        return None
    point = (p[0] + first_ratio * r[0], p[1] + first_ratio * r[1])
    return {
        "point": point,
        "firstInterior": first_margin < first_ratio < 1 - first_margin,
        "secondInterior": second_margin < second_ratio < 1 - second_margin,
        "segmentIds": tuple(sorted((first.id, second.id))),
    }


def _cluster_points(
    points: Iterable[tuple[float, float]], tolerance: float, precision: int
) -> tuple[tuple[float, float], ...]:
    ordered = sorted(set(points))
    if not ordered:
        return ()
    parents = list(range(len(ordered)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(first: int, second: int) -> None:
        first_root, second_root = find(first), find(second)
        if first_root != second_root:
            parents[max(first_root, second_root)] = min(first_root, second_root)

    for first in range(len(ordered)):
        for second in range(first + 1, len(ordered)):
            if _distance(ordered[first], ordered[second]) <= tolerance:
                union(first, second)

    groups: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for index, point in enumerate(ordered):
        groups[find(index)].append(point)
    centers = []
    for group in groups.values():
        centers.append(
            (
                _rounded(sum(point[0] for point in group) / len(group), precision),
                _rounded(sum(point[1] for point in group) / len(group), precision),
            )
        )
    return tuple(sorted(centers))


def _projection(
    point: tuple[float, float], segment: CanonicalSegment
) -> tuple[float, float, tuple[float, float]]:
    delta = (segment.end[0] - segment.start[0], segment.end[1] - segment.start[1])
    length_squared = delta[0] ** 2 + delta[1] ** 2
    ratio = (
        (point[0] - segment.start[0]) * delta[0]
        + (point[1] - segment.start[1]) * delta[1]
    ) / length_squared
    clamped = min(1.0, max(0.0, ratio))
    projected = (
        segment.start[0] + clamped * delta[0],
        segment.start[1] + clamped * delta[1],
    )
    return clamped, _distance(point, projected), projected


def _arm_angle(origin: tuple[float, float], target: tuple[float, float]) -> float:
    angle = math.degrees(math.atan2(target[1] - origin[1], target[0] - origin[0])) % 360
    return round(angle, 3)


def _incident_arms(
    point: tuple[float, float],
    segments: tuple[CanonicalSegment, ...],
    endpoint_tolerance: float,
    intersection_tolerance: float,
) -> list[dict[str, Any]]:
    arms = []
    for segment in segments:
        ratio, distance, _ = _projection(point, segment)
        if distance > intersection_tolerance:
            continue
        length = _distance(segment.start, segment.end)
        endpoint_ratio = min(0.49, endpoint_tolerance / max(length, 1e-9))
        if ratio <= endpoint_ratio:
            targets = (("start", segment.end),)
        elif ratio >= 1 - endpoint_ratio:
            targets = (("end", segment.start),)
        else:
            targets = (("interior_start", segment.start), ("interior_end", segment.end))
        for role, target in targets:
            arms.append(
                {
                    "segmentId": segment.id,
                    "role": role,
                    "angle": _arm_angle(point, target),
                }
            )
    return sorted(arms, key=lambda item: (item["angle"], item["segmentId"], item["role"]))


def _point_rect_distance(point: tuple[float, float], bbox: Sequence[float]) -> float:
    x, y = point
    x1, y1, x2, y2 = bbox
    return math.hypot(max(x1 - x, 0, x - x2), max(y1 - y, 0, y - y2))


def _point_rect_boundary_distance(point: tuple[float, float], bbox: Sequence[float]) -> float:
    x, y = point
    x1, y1, x2, y2 = bbox
    if x1 <= x <= x2 and y1 <= y <= y2:
        return min(x - x1, x2 - x, y - y1, y2 - y)
    return _point_rect_distance(point, bbox)


def _normalize_components(
    components: Iterable[Mapping[str, Any]], precision: int
) -> tuple[dict[str, Any], ...]:
    normalized = []
    for component in components:
        component_id = str(component.get("id") or "")
        bbox = component.get("bbox")
        if not component_id or not isinstance(bbox, Sequence) or len(bbox) != 4:
            raise ValueError("components require a non-empty id and bbox [x1, y1, x2, y2]")
        values = tuple(_rounded(value, precision) for value in bbox)
        if values[0] >= values[2] or values[1] >= values[3]:
            raise ValueError("component bounding boxes must have positive area")
        normalized.append({"id": component_id, "bbox": values})
    ids = [item["id"] for item in normalized]
    if len(ids) != len(set(ids)):
        raise ValueError("component ids must be unique")
    return tuple(sorted(normalized, key=lambda item: item["id"]))


def _nearby_components(
    point: tuple[float, float], components: tuple[dict[str, Any], ...], distance: float
) -> tuple[str, ...]:
    return tuple(
        component["id"]
        for component in components
        if _point_rect_distance(point, component["bbox"]) <= distance
    )


def _normalize_markers(
    markers: Iterable[Mapping[str, Any]], precision: int
) -> tuple[dict[str, Any], ...]:
    normalized = []
    for marker in markers:
        center = _point(marker.get("center") or (), precision)
        radius = float(marker.get("radius") or 0)
        if radius <= 0:
            raise ValueError("explicit junction markers require a positive radius")
        normalized.append(
            {
                "center": center,
                "radius": radius,
                "provenance": str(marker.get("provenance") or "explicit_marker"),
            }
        )
    return tuple(sorted(normalized, key=lambda item: (item["center"], item["radius"])))


def _event(
    event_type: str,
    coordinates: tuple[float, float],
    source_segments: Iterable[str],
    arm_angles: Iterable[float],
    nearby_components: Iterable[str],
    classification: str,
    parameters: Mapping[str, Any],
    evidence: Mapping[str, Any],
    input_provenance: Iterable[str],
) -> GeometricEvent:
    segment_ids = tuple(sorted(set(source_segments)))
    component_ids = tuple(sorted(set(nearby_components)))
    angles = tuple(sorted(round(float(angle), 3) for angle in arm_angles))
    payload = {
        "type": event_type,
        "coordinates": coordinates,
        "sourceSegments": segment_ids,
        "nearbyComponents": component_ids,
        "classification": classification,
    }
    return GeometricEvent(
        id=_stable_id("gev", payload),
        type=event_type,
        coordinates=coordinates,
        source_segments=segment_ids,
        arm_angles=angles,
        provenance={
            "extractor": EXTRACTOR_REVISION,
            "shadowOnly": True,
            "inputs": sorted(set(input_provenance)),
        },
        nearby_components=component_ids,
        classification=classification,
        confidence="high",
        parameters=dict(parameters),
        geometric_evidence=dict(evidence),
    )


def _topology_events(
    segments: tuple[CanonicalSegment, ...],
    components: tuple[dict[str, Any], ...],
    markers: tuple[dict[str, Any], ...],
    effective: Mapping[str, Any],
    precision: int,
) -> list[GeometricEvent]:
    endpoint_tolerance = float(effective["endpointClusterTolerance"])
    intersection_tolerance = float(effective["intersectionTolerance"])
    candidate_points = [point for segment in segments for point in (segment.start, segment.end)]
    intersections = []
    for first_index, first in enumerate(segments):
        for second in segments[first_index + 1 :]:
            intersection = _segment_intersection(first, second, intersection_tolerance)
            if intersection:
                intersections.append(intersection)
                candidate_points.append(intersection["point"])

    clustered = _cluster_points(candidate_points, endpoint_tolerance, precision)
    events = []
    classifications = {
        "endpoint": "terminal",
        "continuation": "collinear",
        "elbow": "direction_change",
        "crossing": "non_connecting_crossing",
        "explicit_junction": "connecting_junction",
        "bifurcation": "connecting_bifurcation",
    }
    for point in clustered:
        arms = _incident_arms(point, segments, endpoint_tolerance, intersection_tolerance)
        if not arms:
            continue
        source_ids = sorted({arm["segmentId"] for arm in arms})
        source_provenance = [
            provenance
            for segment in segments
            if segment.id in source_ids
            for provenance in segment.provenance
        ]
        proper_intersection = any(
            item["firstInterior"]
            and item["secondInterior"]
            and _distance(point, item["point"]) <= endpoint_tolerance
            for item in intersections
        )
        matched_markers = [
            marker
            for marker in markers
            if _distance(point, marker["center"])
            <= marker["radius"] + float(effective["markerTolerance"])
        ]
        arm_count = len(arms)
        if matched_markers and arm_count >= 3:
            event_type = "explicit_junction"
        elif arm_count >= 4 and proper_intersection:
            event_type = "crossing"
        elif arm_count >= 3:
            event_type = "bifurcation"
        elif arm_count == 2:
            first_angle, second_angle = sorted(arm["angle"] for arm in arms)
            separation = min(second_angle - first_angle, 360 - (second_angle - first_angle))
            event_type = (
                "continuation"
                if abs(180 - separation) <= float(effective["collinearToleranceDegrees"])
                else "elbow"
            )
        else:
            event_type = "endpoint"
        events.append(
            _event(
                event_type,
                point,
                source_ids,
                [arm["angle"] for arm in arms],
                _nearby_components(
                    point, components, float(effective["nearbyComponentDistance"])
                ),
                classifications[event_type],
                effective,
                {
                    "armCount": arm_count,
                    "arms": arms,
                    "properIntersection": proper_intersection,
                    "explicitMarker": bool(matched_markers),
                    "markerProvenance": sorted(
                        {marker["provenance"] for marker in matched_markers}
                    ),
                    "transverseConnectivityAllowed": event_type == "explicit_junction",
                },
                source_provenance,
            )
        )
    return events


def _clip_segment_to_rect(
    segment: CanonicalSegment, bbox: Sequence[float]
) -> tuple[float, float] | None:
    x1, y1, x2, y2 = bbox
    start_x, start_y = segment.start
    delta_x = segment.end[0] - start_x
    delta_y = segment.end[1] - start_y
    lower, upper = 0.0, 1.0
    for direction, distance in (
        (-delta_x, start_x - x1),
        (delta_x, x2 - start_x),
        (-delta_y, start_y - y1),
        (delta_y, y2 - start_y),
    ):
        if abs(direction) < 1e-12:
            if distance < 0:
                return None
            continue
        ratio = distance / direction
        if direction < 0:
            lower = max(lower, ratio)
        else:
            upper = min(upper, ratio)
        if lower > upper:
            return None
    return lower, upper


def _component_events(
    segments: tuple[CanonicalSegment, ...],
    components: tuple[dict[str, Any], ...],
    effective: Mapping[str, Any],
    precision: int,
) -> list[GeometricEvent]:
    contact_tolerance = float(effective["componentContactTolerance"])
    events = []
    for segment in segments:
        for endpoint, other in ((segment.start, segment.end), (segment.end, segment.start)):
            for component in components:
                boundary_distance = _point_rect_boundary_distance(endpoint, component["bbox"])
                if boundary_distance > contact_tolerance:
                    continue
                events.append(
                    _event(
                        "component_port",
                        endpoint,
                        (segment.id,),
                        (_arm_angle(endpoint, other),),
                        (component["id"],),
                        "boundary_contact",
                        effective,
                        {
                            "componentId": component["id"],
                            "boundaryDistance": round(boundary_distance, precision),
                            "contactVerified": True,
                        },
                        segment.provenance,
                    )
                )

        for component in components:
            clipped = _clip_segment_to_rect(segment, component["bbox"])
            if clipped is None:
                continue
            lower, upper = clipped
            middle = (lower + upper) / 2
            midpoint = (
                segment.start[0] + middle * (segment.end[0] - segment.start[0]),
                segment.start[1] + middle * (segment.end[1] - segment.start[1]),
            )
            x1, y1, x2, y2 = component["bbox"]
            crosses_interior = (
                upper - lower > 1e-9 and x1 < midpoint[0] < x2 and y1 < midpoint[1] < y2
            )
            ratios = []
            for ratio in (lower, upper):
                point = (
                    segment.start[0] + ratio * (segment.end[0] - segment.start[0]),
                    segment.start[1] + ratio * (segment.end[1] - segment.start[1]),
                )
                if _point_rect_boundary_distance(point, component["bbox"]) <= contact_tolerance:
                    ratios.append(ratio)
            for ratio in sorted(set(round(value, 12) for value in ratios)):
                point = (
                    _rounded(
                        segment.start[0] + ratio * (segment.end[0] - segment.start[0]),
                        precision,
                    ),
                    _rounded(
                        segment.start[1] + ratio * (segment.end[1] - segment.start[1]),
                        precision,
                    ),
                )
                events.append(
                    _event(
                        "component_boundary_intersection",
                        point,
                        (segment.id,),
                        (),
                        (component["id"],),
                        "barrier" if crosses_interior else "boundary_contact",
                        effective,
                        {
                            "componentId": component["id"],
                            "crossesComponentInterior": crosses_interior,
                            "normalizedPathPosition": round(ratio, 6),
                        },
                        segment.provenance,
                    )
                )
    return events


def extract_geometric_event_catalog(
    segments: Iterable[Sequence[float] | Mapping[str, Any]],
    components: Iterable[Mapping[str, Any]] = (),
    explicit_junctions: Iterable[Mapping[str, Any]] = (),
    *,
    parameters: GeometryParameters | None = None,
    scale: float = 1.0,
    line_width: float = 1.0,
) -> dict[str, Any]:
    """Build a canonical shadow-only event catalog without producing flow edges."""
    params = parameters or GeometryParameters()
    canonical_segments = canonicalize_segments(segments, params)
    normalized_components = _normalize_components(components, params.coordinate_precision)
    normalized_markers = _normalize_markers(explicit_junctions, params.coordinate_precision)
    effective = params.effective(scale, line_width)
    events = _topology_events(
        canonical_segments,
        normalized_components,
        normalized_markers,
        effective,
        params.coordinate_precision,
    )
    events.extend(
        _component_events(
            canonical_segments,
            normalized_components,
            effective,
            params.coordinate_precision,
        )
    )
    unique_events = {event.id: event for event in events}
    ordered_events = sorted(
        unique_events.values(),
        key=lambda event: (event.coordinates, event.type, event.id),
    )
    counts = Counter(event.type for event in ordered_events)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "extractorRevision": EXTRACTOR_REVISION,
        "mode": "shadow_only",
        "strategyDependency": "none",
        "producesFlows": False,
        "parameters": {
            "configured": asdict(params),
            "effective": effective,
        },
        "segments": [segment.to_dict() for segment in canonical_segments],
        "events": [event.to_dict() for event in ordered_events],
        "summary": {
            "inputSegmentCount": sum(item.duplicate_count for item in canonical_segments),
            "canonicalSegmentCount": len(canonical_segments),
            "eventCount": len(ordered_events),
            "eventCountByType": {event_type: counts.get(event_type, 0) for event_type in EVENT_TYPES},
        },
        "invariants": {
            "deterministicIds": True,
            "segmentOrderIndependent": True,
            "inputMutation": False,
            "flowDecisionInfluence": False,
        },
    }

