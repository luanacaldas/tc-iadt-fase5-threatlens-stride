"""Local, auditable extraction of flows and trust zones from architecture images."""

from __future__ import annotations

import math
import heapq
from pathlib import Path
from typing import Iterable

from backend.arrowhead_classifier import predict_probability


EXTERNAL_NODE_TYPES = {"internet", "user"}
SOURCE_NODE_TYPES = EXTERNAL_NODE_TYPES | {"identity_provider"}
MINIMUM_FLOW_SCORE = 0.50


def _center(component: dict) -> tuple[float, float]:
    x1, y1, x2, y2 = component["bbox"]
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def _point_rect_distance(point: tuple[float, float], bbox: list[int]) -> float:
    x, y = point
    x1, y1, x2, y2 = bbox
    dx = max(x1 - x, 0, x - x2)
    dy = max(y1 - y, 0, y - y2)
    return math.hypot(dx, dy)


def _nearest_component(
    point: tuple[float, float], components: list[dict]
) -> tuple[dict | None, float]:
    if not components:
        return None, math.inf
    ranked = [(_point_rect_distance(point, component["bbox"]), component) for component in components]
    distance, component = min(ranked, key=lambda item: item[0])
    return component, distance


def _segment_intersects_rect(
    start: tuple[float, float],
    end: tuple[float, float],
    bbox: list[int],
    padding: float = 0.0,
) -> bool:
    """Return whether a finite segment crosses a rectangle (Liang-Barsky)."""
    x1, y1, x2, y2 = bbox
    left, top = x1 - padding, y1 - padding
    right, bottom = x2 + padding, y2 + padding
    start_x, start_y = start
    delta_x, delta_y = end[0] - start_x, end[1] - start_y
    lower, upper = 0.0, 1.0
    for direction, distance in (
        (-delta_x, start_x - left),
        (delta_x, right - start_x),
        (-delta_y, start_y - top),
        (delta_y, bottom - start_y),
    ):
        if abs(direction) < 1e-9:
            if distance < 0:
                return False
            continue
        ratio = distance / direction
        if direction < 0:
            lower = max(lower, ratio)
        else:
            upper = min(upper, ratio)
        if lower > upper:
            return False
    return True


def _blocked_by_component(
    start: tuple[float, float],
    end: tuple[float, float],
    components: list[dict],
    endpoint_ids: set[str],
) -> bool:
    return any(
        component["id"] not in endpoint_ids
        and _segment_intersects_rect(start, end, component["bbox"], padding=2.0)
        for component in components
    )


def _line_support(edges, start: tuple[float, float], end: tuple[float, float]) -> tuple[float, float]:
    """Measure corridor coverage and the largest unsupported gap along a line."""
    distance = math.hypot(end[0] - start[0], end[1] - start[1])
    samples = max(2, round(distance))
    height, width = edges.shape[:2]
    supported: list[bool] = []
    radius = max(2, min(5, round(min(width, height) * 0.003)))
    for index in range(samples + 1):
        ratio = index / samples
        x = round(start[0] + (end[0] - start[0]) * ratio)
        y = round(start[1] + (end[1] - start[1]) * ratio)
        x1, x2 = max(0, x - radius), min(width, x + radius + 1)
        y1, y2 = max(0, y - radius), min(height, y + radius + 1)
        supported.append(bool(edges[y1:y2, x1:x2].any()))

    longest_gap = 0
    current_gap = 0
    for has_edge in supported:
        if has_edge:
            longest_gap = max(longest_gap, current_gap)
            current_gap = 0
        else:
            current_gap += 1
    longest_gap = max(longest_gap, current_gap)
    return sum(supported) / len(supported), longest_gap / len(supported)


def _aligned_pixel_candidates(edges, components: list[dict], diagonal: float) -> list[dict]:
    """Recover straight connectors fragmented by labels, arrowheads, or Hough gaps."""
    candidates = []
    for index, first in enumerate(components):
        first_x, first_y = _center(first)
        first_width = first["bbox"][2] - first["bbox"][0]
        first_height = first["bbox"][3] - first["bbox"][1]
        for second in components[index + 1 :]:
            second_x, second_y = _center(second)
            second_width = second["bbox"][2] - second["bbox"][0]
            second_height = second["bbox"][3] - second["bbox"][1]
            horizontal_tolerance = max(14.0, min(first_height, second_height) * 0.32)
            vertical_tolerance = max(14.0, min(first_width, second_width) * 0.32)
            horizontally_aligned = abs(first_y - second_y) <= horizontal_tolerance
            vertically_aligned = abs(first_x - second_x) <= vertical_tolerance
            if not (horizontally_aligned or vertically_aligned):
                continue

            start = _attachment_point(first, second)
            end = _attachment_point(second, first)
            path_length = math.hypot(end[0] - start[0], end[1] - start[1])
            if path_length < max(12.0, diagonal * 0.012):
                continue
            endpoint_ids = {first["id"], second["id"]}
            if _blocked_by_component(start, end, components, endpoint_ids):
                continue
            support, maximum_gap = _line_support(edges, start, end)
            if support < 0.58 or maximum_gap > 0.24:
                continue
            candidates.append(
                {
                    "first": first,
                    "second": second,
                    "score": min(0.96, 0.54 + support * 0.42 - maximum_gap * 0.20),
                    "attachmentPoints": {
                        first["id"]: (round(start[0]), round(start[1])),
                        second["id"]: (round(end[0]), round(end[1])),
                    },
                    "pathPoints": [
                        [round(start[0]), round(start[1])],
                        [round(end[0]), round(end[1])],
                    ],
                    "evidence": "pixel_line_support",
                    "pixelSupport": round(support, 3),
                    "maximumGap": round(maximum_gap, 3),
                }
            )
    return candidates


def _direct_pair(first: dict, second: dict) -> tuple[dict, dict, str]:
    first_type = str(first.get("type") or "")
    second_type = str(second.get("type") or "")
    if first_type in SOURCE_NODE_TYPES and second_type not in SOURCE_NODE_TYPES:
        return first, second, "semantic_source"
    if second_type in SOURCE_NODE_TYPES and first_type not in SOURCE_NODE_TYPES:
        return second, first, "semantic_source"

    first_x, first_y = _center(first)
    second_x, second_y = _center(second)
    if abs(second_x - first_x) >= abs(second_y - first_y):
        return (first, second, "left_to_right") if first_x <= second_x else (second, first, "left_to_right")
    return (first, second, "top_to_bottom") if first_y <= second_y else (second, first, "top_to_bottom")


def _attachment_point(component: dict, other: dict) -> tuple[float, float]:
    cx, cy = _center(component)
    ox, oy = _center(other)
    dx, dy = ox - cx, oy - cy
    x1, y1, x2, y2 = component["bbox"]
    half_width = max(1.0, (x2 - x1) / 2)
    half_height = max(1.0, (y2 - y1) / 2)
    scales = []
    if abs(dx) > 1e-6:
        scales.append(half_width / abs(dx))
    if abs(dy) > 1e-6:
        scales.append(half_height / abs(dy))
    scale = min(scales) if scales else 0.0
    return cx + dx * scale, cy + dy * scale


def _arrowhead_score(
    edges,
    component: dict,
    other: dict,
    tip: tuple[float, float] | None = None,
    other_point: tuple[float, float] | None = None,
) -> float:
    """Measure support for the two short diagonal rays of an arrowhead."""
    tip_x, tip_y = tip or _attachment_point(component, other)
    other_x, other_y = other_point or _center(other)
    vector_x, vector_y = other_x - tip_x, other_y - tip_y
    vector_length = math.hypot(vector_x, vector_y)
    if vector_length <= 1:
        return 0.0
    unit_x, unit_y = vector_x / vector_length, vector_y / vector_length
    height, width = edges.shape[:2]

    def ray_support(origin_x: float, origin_y: float, angle_delta: float) -> float:
        cosine = math.cos(angle_delta)
        sine = math.sin(angle_delta)
        ray_x = unit_x * cosine - unit_y * sine
        ray_y = unit_x * sine + unit_y * cosine
        supported = 0
        samples = 0
        for distance in range(2, 12):
            sample_x = round(origin_x + ray_x * distance)
            sample_y = round(origin_y + ray_y * distance)
            if not (1 <= sample_x < width - 1 and 1 <= sample_y < height - 1):
                continue
            samples += 1
            if edges[sample_y - 1 : sample_y + 2, sample_x - 1 : sample_x + 2].any():
                supported += 1
        return supported / samples if samples else 0.0

    best = 0.0
    for offset_x in (-2, 0, 2):
        for offset_y in (-2, 0, 2):
            for angle_adjustment in (-0.08, 0.0, 0.08):
                left_support = ray_support(tip_x + offset_x, tip_y + offset_y, 0.40 + angle_adjustment)
                right_support = ray_support(tip_x + offset_x, tip_y + offset_y, -0.40 - angle_adjustment)
                score = min(left_support, right_support) * 100
                best = max(best, score)
    return best


def _direct_pair_from_arrowhead(
    first: dict,
    second: dict,
    edges,
    attachment_points: dict[str, tuple[int, int]] | None = None,
) -> tuple[dict, dict, str, float, dict]:
    attachment_points = attachment_points or {}
    first_point = attachment_points.get(first["id"])
    second_point = attachment_points.get(second["id"])
    first_score = _arrowhead_score(edges, first, second, first_point, second_point)
    second_score = _arrowhead_score(edges, second, first, second_point, first_point)
    first_probability = predict_probability(
        edges,
        first_point or _attachment_point(first, second),
        second_point or _center(second),
    )
    second_probability = predict_probability(
        edges,
        second_point or _attachment_point(second, first),
        first_point or _center(first),
    )
    strongest = max(first_score, second_score)
    margin = abs(first_score - second_score)
    evidence = {
        first["id"]: round(first_score, 2),
        second["id"]: round(second_score, 2),
        "classifier": {
            first["id"]: round(first_probability, 4) if first_probability is not None else None,
            second["id"]: round(second_probability, 4) if second_probability is not None else None,
            "model": "arrowhead-logistic" if first_probability is not None else None,
        },
    }
    fallback_source, fallback_target, fallback_evidence = _direct_pair(first, second)
    if (
        fallback_evidence != "semantic_source"
        and first_probability is not None
        and second_probability is not None
        and max(first_probability, second_probability) >= 0.60
        and abs(first_probability - second_probability) >= 0.20
    ):
        target, source = (first, second) if first_probability > second_probability else (second, first)
        confidence = min(0.97, 0.65 + abs(first_probability - second_probability) * 0.30)
        return source, target, "supervised_arrowhead", round(confidence, 3), evidence
    if fallback_evidence != "semantic_source" and strongest >= 50 and margin >= 35:
        target, source = (first, second) if first_score > second_score else (second, first)
        confidence = min(0.95, 0.62 + margin / max(1.0, strongest) * 0.33)
        return source, target, "visual_arrowhead", round(confidence, 3), evidence

    return fallback_source, fallback_target, fallback_evidence, 0.50, evidence


def _boundary_membership(component: dict, boundary: dict) -> bool:
    x, y = _center(component)
    x1, y1, x2, y2 = boundary["bbox"]
    return x1 <= x <= x2 and y1 <= y <= y2


def _crossed_boundaries(source: dict, target: dict, boundaries: list[dict]) -> list[str]:
    return [
        boundary["id"]
        for boundary in boundaries
        if _boundary_membership(source, boundary) != _boundary_membership(target, boundary)
    ]


def _rect_iou(first: list[int], second: list[int]) -> float:
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    intersection = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))
    first_area = max(1, (ax2 - ax1) * (ay2 - ay1))
    second_area = max(1, (bx2 - bx1) * (by2 - by1))
    return intersection / (first_area + second_area - intersection)


def detect_trust_boundaries(image_path: str | Path, components: list[dict]) -> list[dict]:
    """Detect large rectangular zones and return reviewable trust-boundary candidates."""
    try:
        import cv2
    except Exception:
        return []

    image = cv2.imread(str(image_path))
    if image is None:
        return []
    height, width = image.shape[:2]
    image_area = width * height
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 45, 140)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    candidates: list[dict] = []
    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(polygon) < 4 or len(polygon) > 8:
            continue
        x, y, rect_width, rect_height = cv2.boundingRect(polygon)
        area_ratio = (rect_width * rect_height) / image_area
        if area_ratio < 0.04 or area_ratio > 0.92:
            continue
        if rect_width < width * 0.18 or rect_height < height * 0.14:
            continue
        if x <= 2 and y <= 2 and x + rect_width >= width - 2 and y + rect_height >= height - 2:
            continue

        bbox = [int(x), int(y), int(x + rect_width), int(y + rect_height)]
        member_ids = [component["id"] for component in components if _boundary_membership(component, {"bbox": bbox})]
        if not member_ids or len(member_ids) == len(components):
            continue
        rectangularity = min(1.0, cv2.contourArea(contour) / max(1, rect_width * rect_height))
        confidence = round(min(0.78, 0.52 + rectangularity * 0.26), 3)
        candidates.append({"bbox": bbox, "componentIds": sorted(member_ids), "confidence": confidence})

    selected: list[dict] = []
    for candidate in sorted(candidates, key=lambda item: (-len(item["componentIds"]), -item["confidence"])):
        duplicate = any(
            candidate["componentIds"] == existing["componentIds"]
            and _rect_iou(candidate["bbox"], existing["bbox"]) >= 0.80
            for existing in selected
        )
        if not duplicate:
            selected.append(candidate)
        if len(selected) >= 6:
            break

    boundaries = []
    for index, candidate in enumerate(selected, start=1):
        boundaries.append(
            {
                "id": f"tb{index}",
                "name": f"Detected trust zone {index}",
                "bbox": candidate["bbox"],
                "componentIds": candidate["componentIds"],
                "confidence": candidate["confidence"],
                "inferred": True,
                "reviewStatus": "pending",
                "evidence": "rectangular_zone",
            }
        )
    return boundaries


def _candidate_line_segments(image_path: str | Path):
    try:
        import cv2
    except Exception:
        return [], (0, 0), None, None

    image = cv2.imread(str(image_path))
    if image is None:
        return [], (0, 0), None, None
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    raw_edges = cv2.Canny(gray, 45, 140)

    # Architecture connectors are usually black or gray. Limiting Hough input to
    # neutral pixels prevents colorful provider icons and augmentation overlays
    # from being mistaken for flows, while retaining a small dilation margin for
    # anti-aliased strokes.
    neutral_strokes = cv2.inRange(saturation, 0, 92)
    visible_strokes = cv2.inRange(value, 0, 242)
    connector_mask = cv2.bitwise_and(neutral_strokes, visible_strokes)
    connector_mask = cv2.dilate(connector_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    edges = cv2.bitwise_and(raw_edges, connector_mask)
    minimum = max(18, round(min(width, height) * 0.035))
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=math.pi / 180,
        threshold=max(18, minimum // 2),
        minLineLength=minimum,
        maxLineGap=max(10, round(min(width, height) * 0.018)),
    )
    if lines is None:
        return [], (width, height), edges, raw_edges
    return (
        [tuple(int(value) for value in line[0]) for line in lines],
        (width, height),
        edges,
        raw_edges,
    )


def _segment_graph_candidates(
    segments: list[tuple[int, int, int, int]],
    components: list[dict],
    width: int,
    height: int,
) -> tuple[list[dict], dict]:
    """Connect Hough fragments into paths before associating them with components.

    Only nearby segment endpoints are joined. Geometric crossings in the middle of
    segments therefore remain independent unless the drawing contains a junction.
    """
    if not segments or len(components) < 2:
        return [], {"nodes": 0, "edges": 0, "paths": 0}
    diagonal = math.hypot(width, height)
    join_tolerance = max(6.0, min(width, height) * 0.012)
    attachment_limit = max(24.0, diagonal * 0.055)
    nodes: list[dict] = []

    def node_for(point: tuple[int, int]) -> int:
        best_index, best_distance = -1, math.inf
        for index, node in enumerate(nodes):
            distance = math.hypot(point[0] - node["x"], point[1] - node["y"])
            if distance < best_distance:
                best_index, best_distance = index, distance
        if best_distance <= join_tolerance:
            node = nodes[best_index]
            count = node["count"] + 1
            node["x"] = (node["x"] * node["count"] + point[0]) / count
            node["y"] = (node["y"] * node["count"] + point[1]) / count
            node["count"] = count
            return best_index
        nodes.append({"x": float(point[0]), "y": float(point[1]), "count": 1})
        return len(nodes) - 1

    adjacency: dict[int, dict[int, float]] = {}
    for x1, y1, x2, y2 in segments:
        first_index = node_for((x1, y1))
        second_index = node_for((x2, y2))
        if first_index == second_index:
            continue
        distance = math.hypot(x2 - x1, y2 - y1)
        current = adjacency.setdefault(first_index, {}).get(second_index, math.inf)
        if distance < current:
            adjacency.setdefault(first_index, {})[second_index] = distance
            adjacency.setdefault(second_index, {})[first_index] = distance

    node_components: dict[int, list[tuple[dict, float]]] = {}
    component_nodes: dict[str, list[tuple[int, float]]] = {component["id"]: [] for component in components}
    for node_index, node in enumerate(nodes):
        point = (node["x"], node["y"])
        ranked = sorted(
            ((_point_rect_distance(point, component["bbox"]), component) for component in components),
            key=lambda item: item[0],
        )
        for distance, component in ranked[:2]:
            if distance > attachment_limit:
                continue
            node_components.setdefault(node_index, []).append((component, distance))
            component_nodes[component["id"]].append((node_index, distance))

    def shortest_path(source_nodes: list[tuple[int, float]], target_ids: set[int]) -> tuple[list[int], float] | None:
        queue: list[tuple[float, int]] = []
        distances: dict[int, float] = {}
        previous: dict[int, int] = {}
        for node_index, attach_distance in source_nodes:
            if attach_distance < distances.get(node_index, math.inf):
                distances[node_index] = attach_distance
                heapq.heappush(queue, (attach_distance, node_index))
        reached = None
        while queue:
            distance, node_index = heapq.heappop(queue)
            if distance != distances.get(node_index):
                continue
            if node_index in target_ids:
                reached = node_index
                break
            for neighbor, edge_length in adjacency.get(node_index, {}).items():
                candidate = distance + edge_length
                if candidate < distances.get(neighbor, math.inf):
                    distances[neighbor] = candidate
                    previous[neighbor] = node_index
                    heapq.heappush(queue, (candidate, neighbor))
        if reached is None:
            return None
        path = [reached]
        while path[-1] in previous:
            path.append(previous[path[-1]])
        path.reverse()
        return path, distances[reached]

    candidates = []
    for first_index, first in enumerate(components):
        first_nodes = component_nodes.get(first["id"], [])
        if not first_nodes:
            continue
        for second in components[first_index + 1:]:
            second_nodes = component_nodes.get(second["id"], [])
            if not second_nodes:
                continue
            found = shortest_path(first_nodes, {node_index for node_index, _ in second_nodes})
            if not found:
                continue
            path, weighted_length = found
            if len(path) < 2 or len(path) > 16 or weighted_length > diagonal * 1.55:
                continue
            intermediate_components = {
                component["id"]
                for node_index in path[1:-1]
                for component, _ in node_components.get(node_index, [])
            } - {first["id"], second["id"]}
            if intermediate_components:
                continue
            points = [[round(nodes[index]["x"]), round(nodes[index]["y"])] for index in path]
            direct_distance = math.hypot(points[-1][0] - points[0][0], points[-1][1] - points[0][1])
            route_efficiency = min(1.0, direct_distance / max(weighted_length, 1.0))
            hop_penalty = min(0.12, max(0, len(path) - 3) * 0.015)
            score = min(0.90, 0.54 + route_efficiency * 0.20 - hop_penalty)
            candidates.append(
                {
                    "first": first,
                    "second": second,
                    "score": score,
                    "attachmentPoints": {
                        first["id"]: tuple(points[0]),
                        second["id"]: tuple(points[-1]),
                    },
                    "pathPoints": points,
                    "evidence": "segment_graph",
                    "segmentHops": len(path) - 1,
                    "routeEfficiency": round(route_efficiency, 3),
                }
            )
    return candidates, {
        "nodes": len(nodes),
        "edges": sum(len(neighbors) for neighbors in adjacency.values()) // 2,
        "paths": len(candidates),
        "joinTolerance": round(join_tolerance, 2),
    }


def detect_flows(
    image_path: str | Path,
    components: list[dict],
    boundaries: list[dict] | None = None,
) -> tuple[list[dict], dict]:
    """Associate detected line endpoints with component boxes and deduplicate pairs."""
    boundaries = boundaries or []
    eligible = [component for component in components if isinstance(component.get("bbox"), list)]
    segments, (width, height), edges, arrow_edges = _candidate_line_segments(image_path)
    if len(eligible) < 2 or not segments:
        return [], {"lineSegments": len(segments), "associatedSegments": 0}

    diagonal = math.hypot(width, height)
    maximum_distance = max(28.0, diagonal * 0.065)
    pair_scores: dict[tuple[str, str], dict] = {}
    blocked_segments = 0

    for x1, y1, x2, y2 in segments:
        first, first_distance = _nearest_component((x1, y1), eligible)
        second, second_distance = _nearest_component((x2, y2), eligible)
        if first is None or second is None or first["id"] == second["id"]:
            continue
        if first_distance > maximum_distance or second_distance > maximum_distance:
            continue
        endpoint_ids = {first["id"], second["id"]}
        if _blocked_by_component((x1, y1), (x2, y2), eligible, endpoint_ids):
            blocked_segments += 1
            continue
        segment_length = math.hypot(x2 - x1, y2 - y1)
        attachment = 1 - min(1.0, (first_distance + second_distance) / (2 * maximum_distance))
        length_score = min(1.0, segment_length / max(1.0, diagonal * 0.35))
        score = 0.65 * attachment + 0.35 * length_score
        key = tuple(sorted((first["id"], second["id"])))
        if key not in pair_scores or score > pair_scores[key]["score"]:
            pair_scores[key] = {
                "first": first,
                "second": second,
                "score": score,
                "attachmentPoints": {
                    first["id"]: (x1, y1),
                    second["id"]: (x2, y2),
                },
                "pathPoints": [[x1, y1], [x2, y2]],
                "evidence": "detected_line",
            }

    recovered_candidates = _aligned_pixel_candidates(edges, eligible, diagonal) if edges is not None else []
    for candidate in recovered_candidates:
        key = tuple(sorted((candidate["first"]["id"], candidate["second"]["id"])))
        if key not in pair_scores:
            pair_scores[key] = candidate

    graph_candidates, segment_graph_diagnostics = _segment_graph_candidates(
        segments, eligible, width, height
    )
    for candidate in graph_candidates:
        key = tuple(sorted((candidate["first"]["id"], candidate["second"]["id"])))
        if key not in pair_scores or candidate["score"] > pair_scores[key]["score"]:
            pair_scores[key] = candidate

    accepted_candidates = [
        candidate for candidate in pair_scores.values() if candidate["score"] >= MINIMUM_FLOW_SCORE
    ]
    flows = []
    for candidate in sorted(accepted_candidates, key=lambda item: -item["score"]):
        if arrow_edges is not None:
            source, target, direction_evidence, direction_confidence, arrowhead_scores = _direct_pair_from_arrowhead(
                candidate["first"], candidate["second"], arrow_edges, candidate.get("attachmentPoints")
            )
        else:
            source, target, direction_evidence = _direct_pair(candidate["first"], candidate["second"])
            direction_confidence = 0.40
            arrowhead_scores = {}
        crossed = _crossed_boundaries(source, target, boundaries)
        external_crossing = (
            str(source.get("type")) in EXTERNAL_NODE_TYPES
            and str(target.get("type")) not in EXTERNAL_NODE_TYPES
        )
        confidence = round(min(0.82, 0.58 + candidate["score"] * 0.24), 3)
        flows.append(
            {
                "id": f"f{len(flows) + 1}",
                "from": source["id"],
                "to": target["id"],
                "protocol": "unknown",
                "trustBoundary": bool(crossed or external_crossing),
                "crossedBoundaryIds": crossed,
                "confidence": confidence,
                "inferred": True,
                "reviewStatus": "pending",
                "evidence": candidate.get("evidence", "detected_line"),
                "directionEvidence": direction_evidence,
                "directionConfidence": direction_confidence,
                "arrowheadScores": arrowhead_scores,
                "pathPoints": candidate.get("pathPoints") or [],
                "pixelSupport": candidate.get("pixelSupport"),
                "maximumGap": candidate.get("maximumGap"),
                "segmentHops": candidate.get("segmentHops"),
                "routeEfficiency": candidate.get("routeEfficiency"),
            }
        )

    return flows, {
        "lineSegments": len(segments),
        "candidatePairs": len(pair_scores),
        "associatedSegments": len(accepted_candidates),
        "rejectedLowConfidencePairs": len(pair_scores) - len(accepted_candidates),
        "blockedSegments": blocked_segments,
        "pixelRecoveredFlows": sum(
            candidate.get("evidence") == "pixel_line_support" for candidate in accepted_candidates
        ),
        "segmentGraph": segment_graph_diagnostics,
        "segmentGraphFlows": sum(
            candidate.get("evidence") == "segment_graph" for candidate in accepted_candidates
        ),
    }


def extract_structure(image_path: str | Path, components: list[dict]) -> dict:
    boundaries = detect_trust_boundaries(image_path, components)
    flows, diagnostics = detect_flows(image_path, components, boundaries)
    return {
        "flows": flows,
        "trustBoundaries": boundaries,
        "diagnostics": {
            **diagnostics,
            "trustBoundaryCandidates": len(boundaries),
            "flowExtraction": "detected_lines" if flows else "layout_fallback",
        },
    }


def boundary_ids_crossed(source_id: str, target_id: str, boundaries: Iterable[dict]) -> list[str]:
    """Public helper for deterministic tests and JSON-originated architectures."""
    crossed = []
    for boundary in boundaries:
        members = set(boundary.get("componentIds") or [])
        if (source_id in members) != (target_id in members):
            crossed.append(str(boundary.get("id") or boundary.get("name") or "trust-boundary"))
    return crossed
