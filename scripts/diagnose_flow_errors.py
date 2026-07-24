"""Build stratified, non-causal diagnostics for development flow errors."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.diagram_structure import detect_flows, detect_trust_boundaries
from scripts.evaluate_real_architecture_benchmark import components_in_image_coordinates
from scripts.evaluate_structure_benchmark import score_flows

DEVELOPMENT_SPLIT = "development_tuning"
MODES = {"isolated_ground_truth", "end_to_end"}
CANDIDATE_LABELS = (
    "crossing_as_connection",
    "incorrect_bifurcation",
    "excessive_hops",
    "geometric_proximity",
    "parallel_connectors",
    "connection_through_component",
    "insufficient_evidence",
    "ocr_anchor_association_error",
    "high_density_context",
    "unclassified",
)
DECISION_FIELDS = (
    "id",
    "from",
    "to",
    "protocol",
    "trustBoundary",
    "crossedBoundaryIds",
    "confidence",
    "inferred",
    "reviewStatus",
    "evidence",
    "directionEvidence",
    "directionConfidence",
    "arrowheadScores",
    "pathPoints",
    "pixelSupport",
    "maximumGap",
    "segmentHops",
    "routeEfficiency",
)


def _relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise ValueError(f"Diagnostic artifacts must stay inside the project: {resolved}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _directed(flow: dict) -> tuple[str, str]:
    return str(flow["from"]), str(flow["to"])


def _undirected(flow: dict) -> tuple[str, str]:
    return tuple(sorted(_directed(flow)))


def _safe_divide(numerator: int | float, denominator: int | float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def decision_snapshot(per_image: list[dict]) -> list[dict]:
    return [
        {
            "imageId": item["id"],
            "flows": [
                {field: copy.deepcopy(flow.get(field)) for field in DECISION_FIELDS}
                for flow in item.get("predictedFlows") or []
            ],
        }
        for item in per_image
    ]


def required_metric_view(metrics: dict) -> dict:
    return {
        "edgeExistencePrecision": metrics["undirectedPrecision"],
        "edgeExistenceRecall": metrics["undirectedRecall"],
        "edgeExistenceF1": metrics["undirectedF1"],
        "directedEdgeF1": metrics["directedF1"],
        "undirectedEdgeF1": metrics["undirectedF1"],
        "directionAccuracy": metrics["directionAccuracyOnMatchedEdges"],
        "predictedEdgeCount": metrics["predicted"],
        "expectedEdgeCount": metrics["expected"],
        "falsePositiveEdgeCount": len(metrics["falsePositiveEdges"]),
        "missedEdgeCount": len(metrics["missedEdges"]),
        "reversedEdgeCount": len(metrics["reversedEdges"]),
    }


def _point_rect_distance(point: tuple[float, float], bbox: list[float]) -> float:
    x, y = point
    x1, y1, x2, y2 = bbox
    dx = max(x1 - x, 0.0, x - x2)
    dy = max(y1 - y, 0.0, y - y2)
    return math.hypot(dx, dy)


def _orientation(first: tuple[float, float], second: tuple[float, float], third: tuple[float, float]) -> float:
    return (second[0] - first[0]) * (third[1] - first[1]) - (second[1] - first[1]) * (third[0] - first[0])


def _proper_intersection(
    first_start: tuple[float, float],
    first_end: tuple[float, float],
    second_start: tuple[float, float],
    second_end: tuple[float, float],
) -> bool:
    first_side = _orientation(first_start, first_end, second_start)
    second_side = _orientation(first_start, first_end, second_end)
    third_side = _orientation(second_start, second_end, first_start)
    fourth_side = _orientation(second_start, second_end, first_end)
    epsilon = 1e-6
    return (
        first_side * second_side < -epsilon
        and third_side * fourth_side < -epsilon
    )


def _segments(path: list[list[float]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    points = [(float(point[0]), float(point[1])) for point in path if len(point) >= 2]
    return list(zip(points, points[1:]))


def _segment_intersects_rect(
    start: tuple[float, float],
    end: tuple[float, float],
    bbox: list[float],
) -> bool:
    x1, y1, x2, y2 = (float(value) for value in bbox)
    if x1 <= start[0] <= x2 and y1 <= start[1] <= y2:
        return True
    if x1 <= end[0] <= x2 and y1 <= end[1] <= y2:
        return True
    corners = ((x1, y1), (x2, y1), (x2, y2), (x1, y2))
    return any(
        _proper_intersection(start, end, corners[index], corners[(index + 1) % 4])
        for index in range(4)
    )


def _path_crosses_component(path: list[list[float]], component: dict) -> bool:
    bbox = component.get("bbox")
    return bool(
        isinstance(bbox, list)
        and len(bbox) == 4
        and any(_segment_intersects_rect(start, end, bbox) for start, end in _segments(path))
    )


def _path_angle(path: list[list[float]]) -> float | None:
    if len(path) < 2:
        return None
    start, end = path[0], path[-1]
    if start == end:
        return None
    angle = math.atan2(float(end[1]) - float(start[1]), float(end[0]) - float(start[0]))
    return angle % math.pi


def _path_midpoint(path: list[list[float]]) -> tuple[float, float] | None:
    if len(path) < 2:
        return None
    return (
        (float(path[0][0]) + float(path[-1][0])) / 2,
        (float(path[0][1]) + float(path[-1][1])) / 2,
    )


def _flow_relations(flows: list[dict], diagonal: float) -> dict[str, dict[str, list[str]]]:
    relations = {
        str(flow.get("id")): {
            "crossingFlowIds": [],
            "sharedEndpointFlowIds": [],
            "parallelFlowIds": [],
        }
        for flow in flows
    }
    for first_index, first in enumerate(flows):
        first_id = str(first.get("id"))
        first_path = first.get("pathPoints") or []
        first_segments = _segments(first_path)
        first_angle = _path_angle(first_path)
        first_midpoint = _path_midpoint(first_path)
        for second in flows[first_index + 1:]:
            second_id = str(second.get("id"))
            second_path = second.get("pathPoints") or []
            shared_endpoint = bool(set(_directed(first)) & set(_directed(second)))
            if shared_endpoint:
                relations[first_id]["sharedEndpointFlowIds"].append(second_id)
                relations[second_id]["sharedEndpointFlowIds"].append(first_id)
            elif any(
                _proper_intersection(a, b, c, d)
                for a, b in first_segments
                for c, d in _segments(second_path)
            ):
                relations[first_id]["crossingFlowIds"].append(second_id)
                relations[second_id]["crossingFlowIds"].append(first_id)

            second_angle = _path_angle(second_path)
            second_midpoint = _path_midpoint(second_path)
            if first_angle is None or second_angle is None or first_midpoint is None or second_midpoint is None:
                continue
            angle_delta = abs(first_angle - second_angle)
            angle_delta = min(angle_delta, math.pi - angle_delta)
            midpoint_distance = math.hypot(
                first_midpoint[0] - second_midpoint[0],
                first_midpoint[1] - second_midpoint[1],
            )
            if angle_delta <= math.radians(10) and midpoint_distance <= diagonal * 0.07:
                relations[first_id]["parallelFlowIds"].append(second_id)
                relations[second_id]["parallelFlowIds"].append(first_id)
    return relations


def _endpoint_profiles(flow: dict, components: list[dict]) -> dict:
    path = flow.get("pathPoints") or []
    valid_components = [item for item in components if isinstance(item.get("bbox"), list)]
    if len(path) < 2 or not valid_components:
        return {"status": "not_available", "endpoints": {}, "minimumCandidateMargin": None}
    path_ends = [(float(path[0][0]), float(path[0][1])), (float(path[-1][0]), float(path[-1][1]))]
    endpoints = {}
    margins = []
    for component_id in _directed(flow):
        component = next((item for item in valid_components if str(item["id"]) == component_id), None)
        if component is None:
            endpoints[component_id] = {"status": "component_not_found"}
            continue
        point = min(path_ends, key=lambda item: _point_rect_distance(item, component["bbox"]))
        ranked = sorted(
            (
                (_point_rect_distance(point, candidate["bbox"]), str(candidate["id"]))
                for candidate in valid_components
            ),
            key=lambda item: (item[0], item[1]),
        )
        first_distance, first_id = ranked[0]
        second_distance, second_id = ranked[1] if len(ranked) > 1 else (None, None)
        margin = second_distance - first_distance if second_distance is not None else None
        if margin is not None:
            margins.append(margin)
        endpoints[component_id] = {
            "status": "available",
            "attachmentPoint": [round(point[0], 3), round(point[1], 3)],
            "assignedComponentDistance": round(_point_rect_distance(point, component["bbox"]), 3),
            "nearestCandidateId": first_id,
            "nearestCandidateDistance": round(first_distance, 3),
            "secondCandidateId": second_id,
            "secondCandidateDistance": round(second_distance, 3) if second_distance is not None else None,
            "candidateMargin": round(margin, 3) if margin is not None else None,
        }
    return {
        "status": "available",
        "endpoints": endpoints,
        "minimumCandidateMargin": round(min(margins), 3) if margins else None,
    }


def _diagram_density(
    component_count: int,
    predicted_edge_count: int,
    line_segment_count: int,
    image_size: tuple[int, int],
) -> dict:
    width, height = image_size
    megapixels = max(0.01, width * height / 1_000_000)
    possible_edges = component_count * (component_count - 1) / 2
    edge_density = _safe_divide(predicted_edge_count, possible_edges)
    visual_elements_per_mp = (component_count + line_segment_count / 10) / megapixels
    if component_count >= 18 or edge_density >= 0.50 or visual_elements_per_mp >= 80:
        stratum = "high"
    elif component_count >= 10 or edge_density >= 0.30 or visual_elements_per_mp >= 35:
        stratum = "medium"
    else:
        stratum = "low"
    return {
        "stratum": stratum,
        "componentCount": component_count,
        "predictedEdgeCount": predicted_edge_count,
        "lineSegmentCount": line_segment_count,
        "imageWidth": width,
        "imageHeight": height,
        "imageMegapixels": round(megapixels, 4),
        "normalizedEdgeDensity": round(edge_density, 4),
        "visualElementsPerMegapixel": round(visual_elements_per_mp, 4),
        "policy": "fixed_thresholds_v1",
    }


def _ocr_anchor_observation(flow: dict, components: list[dict], mode: str) -> dict:
    if mode == "isolated_ground_truth":
        return {
            "status": "not_observable",
            "reason": "Ground-truth components bypass detector OCR-anchor association.",
        }
    endpoint_components = [
        component
        for component in components
        if str(component.get("id")) in set(_directed(flow))
    ]
    signals = []
    for component in endpoint_components:
        evidence = component.get("ocrEvidence") or (component.get("metadata") or {}).get("ocrEvidence") or {}
        if evidence and evidence.get("accepted") is False:
            signals.append({"componentId": component["id"], "signal": "rejected_ocr_label"})
        if (component.get("metadata") or {}).get("detectionSource") == "semantic_ocr_proposal":
            signals.append({"componentId": component["id"], "signal": "semantic_ocr_proposal"})
    return {
        "status": "candidate_signal" if signals else "no_signal",
        "signals": signals,
        "causalConclusion": "not_confirmed",
    }


def _hop_bucket(value: Any) -> str:
    if value is None:
        return "not_available"
    hops = int(value)
    if hops <= 1:
        return "1"
    if hops <= 3:
        return "2-3"
    if hops <= 6:
        return "4-6"
    return "7+"


def _classify_false_positive(
    flow: dict,
    diagnostic: dict,
    density: dict,
    diagonal: float,
    ocr_observation: dict,
) -> tuple[list[str], dict[str, list[str]]]:
    signals: dict[str, list[str]] = defaultdict(list)
    relations = diagnostic["relations"]
    if relations["crossingFlowIds"]:
        signals["crossing_as_connection"].append(
            "The candidate path properly intersects another connector without a shared component endpoint."
        )
    endpoint_degrees = diagnostic["endpointGraphDegrees"]
    if max(endpoint_degrees.values(), default=0) >= 4 and len(relations["sharedEndpointFlowIds"]) >= 2:
        signals["incorrect_bifurcation"].append(
            "A high-degree endpoint participates in multiple candidate branches."
        )
    hops = flow.get("segmentHops")
    if hops is not None and int(hops) >= 6:
        signals["excessive_hops"].append(f"The segment path contains {int(hops)} hops.")
    margin = diagnostic["endpointAssociation"].get("minimumCandidateMargin")
    if margin is not None and margin <= max(8.0, diagonal * 0.01):
        signals["geometric_proximity"].append(
            f"The smallest endpoint candidate margin is {margin:.3f} pixels."
        )
    if relations["parallelFlowIds"]:
        signals["parallel_connectors"].append(
            "A nearby connector has a similar orientation."
        )
    if diagnostic["componentsTraversedByPath"]:
        signals["connection_through_component"].append(
            "The path intersects one or more non-endpoint component boxes."
        )
    path = flow.get("pathPoints") or []
    if (
        len(path) < 2
        or (
            flow.get("evidence") == "detected_line"
            and flow.get("segmentHops") is None
            and flow.get("pixelSupport") is None
            and float(flow.get("confidence") or 0) <= 0.72
        )
    ):
        signals["insufficient_evidence"].append(
            "Only limited existence evidence is retained for this accepted candidate."
        )
    if ocr_observation.get("status") == "candidate_signal":
        signals["ocr_anchor_association_error"].append(
            "An endpoint has an OCR-anchor association signal; causality is not confirmed."
        )
    if density["stratum"] == "high":
        signals["high_density_context"].append(
            "The diagram falls in the fixed high-density diagnostic stratum."
        )
    labels = [label for label in CANDIDATE_LABELS if label in signals]
    if not labels:
        labels = ["unclassified"]
        signals["unclassified"].append("No available diagnostic signal met a candidate-label rule.")
    return labels, dict(signals)


def _flow_diagnostic(
    flow: dict,
    components: list[dict],
    relations: dict[str, dict[str, list[str]]],
    degrees: Counter,
    density: dict,
    mode: str,
) -> dict:
    path = flow.get("pathPoints") or []
    endpoint_ids = set(_directed(flow))
    traversed = sorted(
        str(component["id"])
        for component in components
        if str(component.get("id")) not in endpoint_ids and _path_crosses_component(path, component)
    )
    raw_score = flow.get("rawCandidateScore")
    score_status = "available" if isinstance(raw_score, (int, float)) and not isinstance(raw_score, bool) else "not_available"
    arrowhead_scores = copy.deepcopy(flow.get("arrowheadScores") or {})
    classifier = arrowhead_scores.get("classifier") if isinstance(arrowhead_scores, dict) else None
    evidence_sources = [str(flow.get("evidence") or "not_recorded")]
    if flow.get("directionEvidence"):
        evidence_sources.append(str(flow["directionEvidence"]))
    if isinstance(classifier, dict) and classifier.get("model"):
        evidence_sources.append(str(classifier["model"]))
    if flow.get("pixelSupport") is not None:
        evidence_sources.append("pixel_support")
    flow_id = str(flow.get("id"))
    endpoint_association = _endpoint_profiles(flow, components)
    path_point_ids = [
        f"path-point-{index}@{round(float(point[0]), 3)},{round(float(point[1]), 3)}"
        for index, point in enumerate(path)
        if len(point) >= 2
    ]
    return {
        "candidateScore": {
            "raw": raw_score if score_status == "available" else None,
            "status": score_status,
            "reason": None if score_status == "available" else "The current pipeline does not retain raw candidate scores.",
            "acceptedFlowConfidence": flow.get("confidence"),
        },
        "evidenceSources": list(dict.fromkeys(evidence_sources)),
        "segmentHops": flow.get("segmentHops"),
        "hopBucket": _hop_bucket(flow.get("segmentHops")),
        "routeEfficiency": flow.get("routeEfficiency"),
        "endpointAssociation": endpoint_association,
        "endpointGraphDegrees": {endpoint: int(degrees[endpoint]) for endpoint in sorted(endpoint_ids)},
        "pathNodes": {
            "status": "partial" if path_point_ids else "not_available",
            "pathPointIds": path_point_ids,
            "segmentGraphNodeIds": None,
            "segmentGraphNodeDegrees": None,
            "reason": "Segment-graph node identities and degrees are not retained by the current pipeline.",
        },
        "componentsTraversedByPath": traversed,
        "relations": copy.deepcopy(relations.get(flow_id) or {
            "crossingFlowIds": [], "sharedEndpointFlowIds": [], "parallelFlowIds": []
        }),
        "diagramDensity": copy.deepcopy(density),
        "direction": {
            "from": flow.get("from"),
            "to": flow.get("to"),
            "evidence": flow.get("directionEvidence"),
            "confidence": flow.get("directionConfidence"),
            "arrowheadScores": arrowhead_scores,
        },
        "ocrAnchorObservation": _ocr_anchor_observation(flow, components, mode),
    }


def _scope_flows(image_id: str, flows: list[dict]) -> list[dict]:
    return [
        {
            **flow,
            "from": f"{image_id}::{flow['from']}",
            "to": f"{image_id}::{flow['to']}",
        }
        for flow in flows
    ]


def _group_metrics(per_image: list[dict], field: str) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in per_image:
        grouped[str(item[field])].append(item)
    output = {}
    for name, items in sorted(grouped.items()):
        expected = [flow for item in items for flow in _scope_flows(item["id"], item["expectedFlows"])]
        predicted = [flow for item in items for flow in _scope_flows(item["id"], item["evaluationPredictedFlows"])]
        output[name] = required_metric_view(score_flows(expected, predicted))
        output[name]["imageCount"] = len(items)
    return output


def _hop_metrics(records: list[dict]) -> dict:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        if record.get("predictedFlow") is not None:
            buckets[record["diagnostic"]["hopBucket"]].append(record)
    output = {}
    for bucket in ("1", "2-3", "4-6", "7+", "not_available"):
        items = buckets.get(bucket, [])
        adjacency_correct = sum(item["status"] in {"true_positive", "reversed"} for item in items)
        directed_correct = sum(item["status"] == "true_positive" for item in items)
        output[bucket] = {
            "predictedEdgeCount": len(items),
            "adjacencyCorrectCount": adjacency_correct,
            "correctlyDirectedEdgeCount": directed_correct,
            "falsePositiveEdgeCount": sum(item["status"] == "false_positive" for item in items),
            "reversedEdgeCount": sum(item["status"] == "reversed" for item in items),
            "edgeExistencePrecision": _safe_divide(adjacency_correct, len(items)),
            "directionAccuracy": _safe_divide(directed_correct, adjacency_correct),
            "recallStatus": "not_observable_for_predicted_hop_bucket",
        }
    return output


def build_diagnostics(
    per_image: list[dict],
    mode: str,
    baseline_result: dict | None = None,
    baseline_source: str | None = None,
) -> dict:
    if mode not in MODES:
        raise ValueError(f"Unsupported diagnostic mode: {mode}")
    input_snapshot = decision_snapshot(per_image)
    records = []
    for item in per_image:
        expected = item["expectedFlows"]
        predicted = item["predictedFlows"]
        evaluation_predicted = item["evaluationPredictedFlows"]
        expected_directed = {_directed(flow): flow for flow in expected}
        predicted_undirected = {_undirected(flow) for flow in evaluation_predicted}
        degrees = Counter(
            endpoint
            for flow in predicted
            for endpoint in _directed(flow)
        )
        width, height = item["imageSize"]
        diagonal = math.hypot(width, height)
        density = _diagram_density(
            len(item["components"]),
            len(predicted),
            int((item.get("diagnostics") or {}).get("lineSegments") or 0),
            item["imageSize"],
        )
        item["densityStratum"] = density["stratum"]
        relations = _flow_relations(predicted, diagonal)
        for index, (flow, evaluation_flow) in enumerate(zip(predicted, evaluation_predicted), start=1):
            pair = _directed(evaluation_flow)
            if pair in expected_directed:
                status = "true_positive"
                expected_flow = expected_directed[pair]
            elif tuple(reversed(pair)) in expected_directed:
                status = "reversed"
                expected_flow = expected_directed[tuple(reversed(pair))]
            else:
                status = "false_positive"
                expected_flow = None
            diagnostic = _flow_diagnostic(flow, item["components"], relations, degrees, density, mode)
            labels, signals = ([], {})
            if status == "false_positive":
                labels, signals = _classify_false_positive(
                    flow,
                    diagnostic,
                    density,
                    diagonal,
                    diagnostic["ocrAnchorObservation"],
                )
            records.append({
                "inventoryId": f"{mode}:{item['id']}:predicted:{index}",
                "imageId": item["id"],
                "provider": item["provider"],
                "image": item["image"],
                "mode": mode,
                "detectionStrategy": item["detectionStrategy"],
                "status": status,
                "predictedFlow": copy.deepcopy(flow),
                "evaluationEndpoints": {"from": evaluation_flow["from"], "to": evaluation_flow["to"]},
                "expectedFlow": copy.deepcopy(expected_flow),
                "diagnostic": diagnostic,
                "candidateLabels": labels,
                "candidateLabelSignals": signals,
                "classificationStatus": "diagnostic_hypothesis" if status == "false_positive" else "not_applicable",
                "humanCauseConfirmed": False,
                "ambiguous": len(labels) > 1,
                "requiresHumanReview": status != "true_positive",
            })
        for index, expected_flow in enumerate(expected, start=1):
            if _undirected(expected_flow) in predicted_undirected:
                continue
            records.append({
                "inventoryId": f"{mode}:{item['id']}:missed:{index}",
                "imageId": item["id"],
                "provider": item["provider"],
                "image": item["image"],
                "mode": mode,
                "detectionStrategy": item["detectionStrategy"],
                "status": "missed",
                "predictedFlow": None,
                "evaluationEndpoints": None,
                "expectedFlow": copy.deepcopy(expected_flow),
                "diagnostic": {
                    "status": "not_observable_without_candidate",
                    "ocrAnchorObservation": {
                        "status": "not_observable" if mode == "isolated_ground_truth" else "no_predicted_candidate"
                    },
                    "hopBucket": "not_available",
                    "diagramDensity": copy.deepcopy(density),
                },
                "candidateLabels": [],
                "candidateLabelSignals": {},
                "classificationStatus": "not_applicable",
                "humanCauseConfirmed": False,
                "ambiguous": False,
                "requiresHumanReview": True,
            })

    expected_all = [
        flow for item in per_image for flow in _scope_flows(item["id"], item["expectedFlows"])
    ]
    predicted_all = [
        flow
        for item in per_image
        for flow in _scope_flows(item["id"], item["evaluationPredictedFlows"])
    ]
    legacy_metrics = score_flows(expected_all, predicted_all)
    required_metrics = required_metric_view(legacy_metrics)
    false_positives = [item for item in records if item["status"] == "false_positive"]
    label_counts = Counter(label for item in false_positives for label in item["candidateLabels"])
    evidence_counts = Counter(
        str((item["predictedFlow"] or {}).get("evidence") or "not_recorded")
        for item in false_positives
    )
    status_counts = Counter(item["status"] for item in records)
    required_metrics.update({
        "falsePositiveCountByEvidence": dict(sorted(evidence_counts.items())),
        "falsePositiveCountByCandidateLabel": {
            label: int(label_counts.get(label, 0)) for label in CANDIDATE_LABELS
        },
        "metricsByProvider": _group_metrics(per_image, "provider"),
        "metricsByDensityStratum": _group_metrics(per_image, "densityStratum"),
        "metricsByHopBucket": _hop_metrics(records),
        "unclassifiedRate": _safe_divide(label_counts.get("unclassified", 0), len(false_positives)),
        "ambiguousRate": _safe_divide(sum(item["ambiguous"] for item in false_positives), len(false_positives)),
    })
    per_image_metrics = []
    for item in per_image:
        metrics = required_metric_view(score_flows(item["expectedFlows"], item["evaluationPredictedFlows"]))
        per_image_metrics.append({
            "imageId": item["id"],
            "provider": item["provider"],
            "densityStratum": item["densityStratum"],
            **metrics,
        })

    after_snapshot = decision_snapshot(per_image)
    if baseline_result is not None:
        before_snapshot = decision_snapshot(baseline_result.get("perImage") or [])
        before_metrics = baseline_result["aggregate"]["flows"]
        previous_metrics_integrity = {
            "status": "PASS" if before_metrics == legacy_metrics else "FAIL",
            "baselineSource": baseline_source,
            "before": copy.deepcopy(before_metrics),
            "after": copy.deepcopy(legacy_metrics),
        }
    else:
        before_snapshot = input_snapshot
        previous_metrics_integrity = {
            "status": "NOT_APPLICABLE",
            "reason": "No prior end-to-end flow baseline is registered.",
        }
    snapshot_integrity = {
        "status": "PASS" if before_snapshot == after_snapshot else "FAIL",
        "beforeSha256": _canonical_hash(before_snapshot),
        "afterSha256": _canonical_hash(after_snapshot),
        "equivalent": before_snapshot == after_snapshot,
        "decisionFields": list(DECISION_FIELDS),
    }
    return {
        "records": records,
        "statusCounts": dict(sorted(status_counts.items())),
        "legacyMetrics": legacy_metrics,
        "requiredMetrics": required_metrics,
        "perImageMetrics": per_image_metrics,
        "previousMetricsIntegrity": previous_metrics_integrity,
        "flowDecisionSnapshotIntegrity": snapshot_integrity,
    }


def _load_isolated_images(entries: list[dict]) -> list[dict]:
    per_image = []
    for entry in entries:
        image_path = ROOT / entry["image"]
        components = components_in_image_coordinates(entry, image_path)
        boundaries = detect_trust_boundaries(image_path, components)
        predicted, diagnostics = detect_flows(image_path, components, boundaries)
        with Image.open(image_path) as image:
            image_size = image.size
        per_image.append({
            "id": entry["id"],
            "provider": entry["provider"],
            "image": entry["image"],
            "components": components,
            "expectedFlows": copy.deepcopy(entry.get("flows") or []),
            "predictedFlows": predicted,
            "evaluationPredictedFlows": copy.deepcopy(predicted),
            "diagnostics": diagnostics,
            "imageSize": image_size,
            "detectionStrategy": "ground_truth_components_plus_current_detect_flows",
        })
    return per_image


def _load_end_to_end_images(entries: list[dict]) -> list[dict]:
    from backend.detector import detect
    from scripts.evaluate_blind_end_to_end import match_components

    per_image = []
    for entry in entries:
        image_path = ROOT / entry["image"]
        expected_components = components_in_image_coordinates(entry, image_path)
        architecture = detect(str(image_path)) or {
            "components": [], "flows": [], "trustBoundaries": [], "structureMetadata": {}
        }
        component_metrics = match_components(expected_components, architecture.get("components") or [])
        mapping = {
            match["predictedId"]: match["expectedId"]
            for match in component_metrics["matches"]
        }
        predicted = copy.deepcopy(architecture.get("flows") or [])
        evaluation_predicted = [
            {
                **copy.deepcopy(flow),
                "from": mapping.get(flow["from"], f"unmatched::{flow['from']}"),
                "to": mapping.get(flow["to"], f"unmatched::{flow['to']}"),
            }
            for flow in predicted
        ]
        with Image.open(image_path) as image:
            image_size = image.size
        per_image.append({
            "id": entry["id"],
            "provider": entry["provider"],
            "image": entry["image"],
            "components": copy.deepcopy(architecture.get("components") or []),
            "expectedFlows": copy.deepcopy(entry.get("flows") or []),
            "predictedFlows": predicted,
            "evaluationPredictedFlows": evaluation_predicted,
            "diagnostics": copy.deepcopy(architecture.get("structureMetadata") or {}),
            "imageSize": image_size,
            "detectionStrategy": str(architecture.get("detectedBy") or "supervised_detector_v15"),
            "componentMapping": mapping,
        })
    return per_image


def evaluate(
    benchmark_path: Path,
    output_dir: Path,
    mode: str = "isolated_ground_truth",
    split: str = DEVELOPMENT_SPLIT,
    baseline_path: Path | None = None,
    expected_false_positive_count: int | None = 90,
) -> dict:
    if split != DEVELOPMENT_SPLIT:
        raise ValueError("Flow diagnostics are restricted to development_tuning.")
    if mode not in MODES:
        raise ValueError(f"Unsupported diagnostic mode: {mode}")
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    entries = [entry for entry in benchmark["entries"] if entry.get("split") == split]
    if not entries:
        raise ValueError("No development_tuning entries were found.")
    if mode == "isolated_ground_truth":
        per_image = _load_isolated_images(entries)
        baseline_result = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path else None
        baseline_source = _relative(baseline_path) if baseline_path else None
    else:
        per_image = _load_end_to_end_images(entries)
        baseline_result = None
        baseline_source = None
    result = build_diagnostics(per_image, mode, baseline_result, baseline_source)
    false_positive_count = result["requiredMetrics"]["falsePositiveEdgeCount"]
    if mode == "isolated_ground_truth" and expected_false_positive_count is not None:
        if false_positive_count != expected_false_positive_count:
            raise RuntimeError(
                f"Expected {expected_false_positive_count} isolated false-positive edges, received {false_positive_count}."
            )
    if result["flowDecisionSnapshotIntegrity"]["status"] != "PASS":
        raise RuntimeError("Flow decision snapshot changed during diagnostic instrumentation.")
    if mode == "isolated_ground_truth" and result["previousMetricsIntegrity"]["status"] != "PASS":
        raise RuntimeError("Legacy flow metrics changed from the registered pre-instrumentation artifact.")

    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()
    artifact_paths = {
        "inventory": output_dir / "flow-inventory.json",
        "summary": output_dir / "flow-diagnostics-summary.json",
        "metrics": output_dir / "flow-stratified-metrics.json",
        "humanReview": output_dir / "flow-human-review.json",
    }
    relative_artifacts = {name: _relative(path) for name, path in artifact_paths.items()}
    inventory_payload = {
        "schemaVersion": "1.0",
        "generatedAt": generated_at,
        "mode": mode,
        "split": split,
        "benchmark": _relative(benchmark_path),
        "recordCount": len(result["records"]),
        "falsePositiveRecordCount": false_positive_count,
        "records": result["records"],
    }
    summary_payload = {
        "schemaVersion": "1.0",
        "generatedAt": generated_at,
        "mode": mode,
        "split": split,
        "benchmark": _relative(benchmark_path),
        "imageCount": len(entries),
        "statusCounts": result["statusCounts"],
        "falsePositiveCountByEvidence": result["requiredMetrics"]["falsePositiveCountByEvidence"],
        "falsePositiveCountByCandidateLabel": result["requiredMetrics"]["falsePositiveCountByCandidateLabel"],
        "unclassifiedRate": result["requiredMetrics"]["unclassifiedRate"],
        "ambiguousRate": result["requiredMetrics"]["ambiguousRate"],
        "classificationPolicy": {
            "type": "multilabel_candidate_signals",
            "candidateLabels": list(CANDIDATE_LABELS),
            "causalClaimsAllowed": False,
            "humanReviewRequiredForFalsePositives": True,
        },
        "previousMetricsIntegrity": result["previousMetricsIntegrity"],
        "flowDecisionSnapshotIntegrity": result["flowDecisionSnapshotIntegrity"],
        "artifacts": relative_artifacts,
    }
    metrics_payload = {
        "schemaVersion": "1.0",
        "generatedAt": generated_at,
        "mode": mode,
        "split": split,
        **result["requiredMetrics"],
        "legacyMetrics": result["legacyMetrics"],
        "metricsByImage": result["perImageMetrics"],
    }
    review_records = [
        {
            "inventoryId": item["inventoryId"],
            "imageId": item["imageId"],
            "status": item["status"],
            "candidateLabels": item["candidateLabels"],
            "ambiguous": item["ambiguous"],
            "reason": (
                "Candidate labels are diagnostic signals and require human causal review."
                if item["status"] == "false_positive"
                else "The missed or reversed relation requires architecture review."
            ),
        }
        for item in result["records"]
        if item["requiresHumanReview"]
    ]
    review_payload = {
        "schemaVersion": "1.0",
        "generatedAt": generated_at,
        "mode": mode,
        "split": split,
        "reviewCaseCount": len(review_records),
        "cases": review_records,
    }
    for path, payload in (
        (artifact_paths["inventory"], inventory_payload),
        (artifact_paths["summary"], summary_payload),
        (artifact_paths["metrics"], metrics_payload),
        (artifact_paths["humanReview"], review_payload),
    ):
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "status": "passed",
        "mode": mode,
        "split": split,
        "metrics": result["requiredMetrics"],
        "statusCounts": result["statusCounts"],
        "previousMetricsIntegrity": result["previousMetricsIntegrity"]["status"],
        "flowDecisionSnapshotIntegrity": result["flowDecisionSnapshotIntegrity"]["status"],
        "artifacts": relative_artifacts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path("data/benchmarks/real-architecture/benchmark-expanded.json"),
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("data/results/real-architecture/real-architecture-evaluation.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/results/flow-diagnostics-v1/isolated-ground-truth"),
    )
    parser.add_argument("--mode", choices=sorted(MODES), default="isolated_ground_truth")
    parser.add_argument("--split", default=DEVELOPMENT_SPLIT)
    parser.add_argument("--expected-false-positive-count", type=int, default=90)
    args = parser.parse_args()
    result = evaluate(
        args.benchmark,
        args.output,
        mode=args.mode,
        split=args.split,
        baseline_path=args.baseline if args.mode == "isolated_ground_truth" else None,
        expected_false_positive_count=(
            args.expected_false_positive_count if args.mode == "isolated_ground_truth" else None
        ),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
