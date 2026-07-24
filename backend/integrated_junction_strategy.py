"""Integrated shadow orchestration and promotion policy for TL-004F."""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
from collections import Counter
from typing import Any, Iterable, Mapping, Sequence

from backend.endpoint_validation import analyze_flow_candidate
from backend.geometric_events import extract_geometric_event_catalog
from backend.intersection_validation import classify_intersections
from backend.shared_trunk_reconstruction import reconstruct_shared_trunks
from backend.transitive_shortcut_validation import classify_transitive_shortcuts
from scripts.diagnose_flow_errors import required_metric_view
from scripts.evaluate_structure_benchmark import score_flows


SCHEMA_VERSION = "1.0"
STRATEGY_REVISION = "tl004f-integrated-shadow-v1"
FINAL_ACTIONS = ("keep", "redirect", "block", "decompose", "recover", "review_only")
DEFAULT_MODULE_FLAGS = {
    "endpointRedirect": True,
    "crossingBlock": True,
    "trunkRecovery": True,
    "transitiveSuppression": True,
}


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"{prefix}-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]}"


def _edge(item: Mapping[str, Any]) -> tuple[str, str]:
    return str(item.get("from") or ""), str(item.get("to") or "")


def _segments_for_flow(flow: Mapping[str, Any]) -> list[dict[str, Any]]:
    points = flow.get("pathPoints") or []
    identifiers = list(flow.get("segmentIds") or [])
    provenance = str(flow.get("provenance") or flow.get("id") or "candidate")
    return [
        {
            "id": identifiers[index] if index < len(identifiers) else f"{provenance}:segment:{index}",
            "start": copy.deepcopy(start),
            "end": copy.deepcopy(end),
            "provenance": provenance,
            "pixelSupport": flow.get("pixelSupport"),
        }
        for index, (start, end) in enumerate(zip(points, points[1:]))
        if start != end
    ]


def _terminal_ports(flows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ports = []
    for flow in flows:
        segments = _segments_for_flow(flow)
        points = flow.get("pathPoints") or []
        if not segments or len(points) < 2:
            continue
        confidence = float(flow.get("directionConfidence") or 0)
        provenance = str(flow.get("provenance") or flow.get("id") or "candidate")
        ports.extend(
            (
                {
                    "id": f"{provenance}:source-port",
                    "componentId": str(flow["from"]),
                    "coordinates": copy.deepcopy(points[0]),
                    "segmentId": segments[0]["id"],
                    "direction": "outgoing",
                    "confidence": confidence,
                    "reviewed": True,
                    "provenance": provenance,
                },
                {
                    "id": f"{provenance}:destination-port",
                    "componentId": str(flow["to"]),
                    "coordinates": copy.deepcopy(points[-1]),
                    "segmentId": segments[-1]["id"],
                    "direction": "incoming",
                    "confidence": confidence,
                    "reviewed": True,
                    "provenance": provenance,
                },
            )
        )
    return ports


def _candidate_crossing_signal(events: Sequence[Mapping[str, Any]], provenance: str) -> dict[str, Any] | None:
    matching = []
    for event in events:
        arms = [arm for arm in event["arms"] if provenance in (arm.get("provenance") or [])]
        arm_ids = sorted(arm["id"] for arm in arms)
        candidate_pairs = {tuple(sorted(pair)) for pair in itertools.combinations(arm_ids, 2)}
        blocked = {tuple(item["armIds"]) for item in event["blockedTransversePairs"]}
        if candidate_pairs & blocked:
            matching.append(event)
    if not matching:
        return None
    return {
        "module": "TL-004C",
        "proposedAction": "block",
        "confidence": "high" if all(not item["reviewOnly"] for item in matching) else "low",
        "reason": "candidate_switches_transverse_branches_at_unmarked_crossing",
        "eventIds": sorted(item["id"] for item in matching),
    }


def _endpoint_signal(analysis: Mapping[str, Any]) -> dict[str, Any]:
    action = analysis["edgeAction"]
    decisions = analysis.get("endpointDecisions") or []
    if analysis.get("firstIntermediateBarrier") and analysis.get("adjacentRelations"):
        return {
            "module": "TL-004B",
            "proposedAction": "decompose",
            "confidence": "high",
            "reason": "component_barrier_requires_adjacent_relations",
            "adjacentRelations": copy.deepcopy(analysis["adjacentRelations"]),
        }
    if action == "redirected" and analysis.get("experimentalFlow"):
        reliable = len(decisions) == 2 and all(
            item.get("classification") in {"confirmed_contact", "wrong_component_contact"}
            for item in decisions
        )
        return {
            "module": "TL-004B",
            "proposedAction": "redirect",
            "confidence": "high" if reliable else "low",
            "reason": "endpoint_contact_changes_declared_component",
            "proposedFrom": analysis["experimentalFlow"]["from"],
            "proposedTo": analysis["experimentalFlow"]["to"],
        }
    if action == "kept":
        return {
            "module": "TL-004B",
            "proposedAction": "keep",
            "confidence": "high",
            "reason": "both_endpoint_contacts_are_confirmed",
        }
    return {
        "module": "TL-004B",
        "proposedAction": "review_only",
        "confidence": "low",
        "reason": "endpoint_contact_is_not_sufficient_for_automatic_change",
    }


def _transitive_signal(decision: Mapping[str, Any]) -> dict[str, Any]:
    action = decision["shadowAction"]
    proposed = "review_only" if action == "review" else action
    return {
        "module": "TL-004E",
        "proposedAction": proposed,
        "confidence": decision["confidence"],
        "reason": decision["reasons"][0] if decision["reasons"] else "transitive_analysis",
        "classification": decision["classification"],
        "adjacentRelations": copy.deepcopy(decision["recommendedAdjacentRelations"]),
        "intermediateComponents": copy.deepcopy(decision["intermediateComponents"]),
    }


def _resolve_candidate(
    flow: Mapping[str, Any],
    signals: Sequence[Mapping[str, Any]],
    *,
    protected: bool,
    structural: bool,
    flags: Mapping[str, bool],
) -> tuple[str, dict[str, Any], list[dict[str, Any]], str, str]:
    enabled = []
    for signal in signals:
        module, action = signal["module"], signal["proposedAction"]
        if module == "TL-004B" and action == "redirect" and not flags["endpointRedirect"]:
            continue
        if module == "TL-004C" and not flags["crossingBlock"]:
            continue
        if module == "TL-004D" and not flags["trunkRecovery"]:
            continue
        if module == "TL-004E" and not flags["transitiveSuppression"]:
            continue
        enabled.append(copy.deepcopy(dict(signal)))
    competing = sorted({item["proposedAction"] for item in enabled if item["proposedAction"] not in {"keep", "review_only"}})
    conflicts = []
    if len(competing) > 1:
        conflicts.append(
            {
                "modules": sorted({item["module"] for item in enabled if item["proposedAction"] in competing}),
                "competingActions": competing,
                "rule": "transitive block outranks endpoint redirect only with high-confidence directed chain; otherwise review",
            }
        )
    if structural:
        return "review_only", {}, conflicts, "low", "structural_line_is_outside_tl004_scope"
    if protected:
        return "keep", {}, conflicts, "high", "human_or_benchmark_protection_preserves_valid_edge"

    high_transitive = next(
        (
            item
            for item in enabled
            if item["module"] == "TL-004E"
            and item["proposedAction"] == "block"
            and item["confidence"] in {"high", "medium"}
        ),
        None,
    )
    high_crossing = next(
        (
            item
            for item in enabled
            if item["module"] == "TL-004C"
            and item["proposedAction"] == "block"
            and item["confidence"] == "high"
        ),
        None,
    )
    high_decompose = next(
        (
            item
            for item in enabled
            if item["proposedAction"] == "decompose" and item["confidence"] == "high"
        ),
        None,
    )
    high_redirect = next(
        (
            item
            for item in enabled
            if item["proposedAction"] == "redirect" and item["confidence"] == "high"
        ),
        None,
    )
    if high_transitive:
        return "block", {}, conflicts, high_transitive["confidence"], "high-confidence transitive suppression"
    if high_decompose and not high_crossing:
        return (
            "decompose",
            {"adjacentRelations": copy.deepcopy(high_decompose.get("adjacentRelations") or [])},
            conflicts,
            "high",
            "component barrier preserves only adjacent relations",
        )
    if high_crossing and not high_redirect:
        return "block", {}, conflicts, "high", "unmarked crossing blocks transverse branch switch"
    if high_redirect and not high_crossing:
        return (
            "redirect",
            {"from": high_redirect["proposedFrom"], "to": high_redirect["proposedTo"]},
            conflicts,
            "high",
            "reliable endpoint contacts support redirect",
        )
    if high_redirect and high_crossing:
        return "review_only", {}, conflicts, "low", "unresolved redirect versus crossing conflict"
    if any(item["proposedAction"] == "keep" and item["confidence"] == "high" for item in enabled):
        return "keep", {}, conflicts, "high", "confirmed endpoint contacts preserve candidate"
    return "review_only", {}, conflicts, "low", "evidence is insufficient or conflicting"


def orchestrate_junction_aware(
    legacy_flows: Iterable[Mapping[str, Any]],
    components: Iterable[Mapping[str, Any]],
    *,
    segments: Iterable[Sequence[float] | Mapping[str, Any]] = (),
    terminal_ports: Iterable[Mapping[str, Any]] = (),
    explicit_junctions: Iterable[Mapping[str, Any]] = (),
    adjacent_relations: Iterable[Mapping[str, Any]] = (),
    confirmed_direct_edges: Iterable[Mapping[str, Any]] = (),
    human_confirmed_shortcuts: Iterable[Mapping[str, Any]] = (),
    protected_edges: Iterable[Sequence[str]] = (),
    protected_candidate_ids: Iterable[str] = (),
    structural_candidate_ids: Iterable[str] = (),
    recovery_candidates: Iterable[Mapping[str, Any]] = (),
    module_flags: Mapping[str, bool] | None = None,
    scale: float = 1.0,
    line_width: float = 1.0,
) -> dict[str, Any]:
    flows = copy.deepcopy(list(legacy_flows))
    component_list = copy.deepcopy(list(components))
    segment_list = copy.deepcopy(list(segments)) or [segment for flow in flows for segment in _segments_for_flow(flow)]
    port_list = copy.deepcopy(list(terminal_ports)) or _terminal_ports(flows)
    junctions = copy.deepcopy(list(explicit_junctions))
    adjacency = copy.deepcopy(list(adjacent_relations))
    direct_edges = copy.deepcopy(list(confirmed_direct_edges))
    human_shortcuts = copy.deepcopy(list(human_confirmed_shortcuts))
    recoveries = copy.deepcopy(list(recovery_candidates))
    flags = {**DEFAULT_MODULE_FLAGS, **dict(module_flags or {})}
    protected_edge_set = {tuple(str(value) for value in item) for item in protected_edges}
    protected_ids = {str(item) for item in protected_candidate_ids}
    structural_ids = {str(item) for item in structural_candidate_ids}

    geometric = extract_geometric_event_catalog(segment_list, component_list, junctions, scale=scale, line_width=line_width)
    intersections = classify_intersections(segment_list, component_list, junctions, scale=scale, line_width=line_width)
    trunks = reconstruct_shared_trunks(segment_list, component_list, port_list, junctions, scale=scale, line_width=line_width)
    transitive = classify_transitive_shortcuts(
        flows,
        component_list,
        segments=segment_list,
        terminal_ports=port_list,
        explicit_junctions=junctions,
        adjacent_relations=adjacency,
        confirmed_direct_edges=direct_edges,
        human_confirmed_shortcuts=human_shortcuts,
        scale=scale,
        line_width=line_width,
    )
    transitive_by_candidate = {item["candidateId"]: item for item in transitive["decisions"]}
    final_decisions = []
    module_conflicts = []
    for flow in sorted(flows, key=lambda item: (str(item.get("id") or ""), _edge(item))):
        candidate_id = str(flow.get("id") or "")
        provenance = str(flow.get("provenance") or candidate_id)
        endpoint = analyze_flow_candidate(flow, component_list, flow_strategy="junction_aware", scale=scale, line_width=line_width)
        related_events = [item for item in geometric["events"] if provenance in (item.get("segmentProvenance") or [])]
        related_intersections = [item for item in intersections["events"] if provenance in (item.get("segmentProvenance") or [])]
        related_trunks = [item for item in trunks["trunks"] if provenance in (item.get("segmentProvenance") or [])]
        signals = [_endpoint_signal(endpoint), _transitive_signal(transitive_by_candidate[candidate_id])]
        crossing_signal = _candidate_crossing_signal(intersections["events"], provenance)
        if crossing_signal:
            signals.append(crossing_signal)
        if related_trunks:
            signals.append(
                {
                    "module": "TL-004D",
                    "proposedAction": "keep",
                    "confidence": max((item["confidence"] for item in related_trunks), default="low"),
                    "reason": "candidate_is_representable_by_shared_trunk_evidence",
                    "trunkIds": sorted(item["id"] for item in related_trunks),
                }
            )
        protected = candidate_id in protected_ids or provenance in protected_ids or _edge(flow) in protected_edge_set
        structural = candidate_id in structural_ids or provenance in structural_ids
        action, proposal, conflicts, confidence, reason = _resolve_candidate(
            flow,
            signals,
            protected=protected,
            structural=structural,
            flags=flags,
        )
        decision_id = _stable_id("integrated", {"candidateId": candidate_id, "from": flow["from"], "to": flow["to"]})
        decision = {
            "id": decision_id,
            "candidateId": candidate_id,
            "legacyFrom": flow["from"],
            "legacyTo": flow["to"],
            "proposedFrom": proposal.get("from", flow["from"]),
            "proposedTo": proposal.get("to", flow["to"]),
            "finalAction": action,
            "confidence": confidence,
            "reason": reason,
            "segments": [item["id"] for item in _segments_for_flow(flow)],
            "ports": copy.deepcopy(endpoint.get("ports") or []),
            "barriers": copy.deepcopy(endpoint.get("barriers") or []),
            "intersectionIds": sorted(item["id"] for item in related_intersections),
            "geometricEventIds": sorted(item["id"] for item in related_events),
            "trunkIds": sorted(item["id"] for item in related_trunks),
            "adjacentRelations": copy.deepcopy(proposal.get("adjacentRelations") or transitive_by_candidate[candidate_id]["recommendedAdjacentRelations"]),
            "intermediateComponents": copy.deepcopy(transitive_by_candidate[candidate_id]["intermediateComponents"]),
            "directEdgeEvidence": copy.deepcopy(transitive_by_candidate[candidate_id]["directEdgeEvidence"]),
            "moduleSignals": signals,
            "participatingModules": sorted({item["module"] for item in signals}),
            "conflicts": conflicts,
            "protected": protected,
            "structuralLineCase": structural,
            "officialResultChanged": False,
            "officialDirectionChanged": False,
            "officialEligible": False,
        }
        final_decisions.append(decision)
        module_conflicts.extend({**item, "decisionId": decision_id, "candidateId": candidate_id, "finalAction": action} for item in conflicts)

    recovery_decisions = []
    for recovery in sorted(recoveries, key=lambda item: (_edge(item), str(item.get("id") or ""))):
        supervised = bool(recovery.get("supervised", False))
        confidence = str(recovery.get("confidence") or "low")
        barrier = bool(recovery.get("barrierConflict", False))
        if supervised:
            action, reason = "review_only", "supervised recovery cannot be applied as autonomous"
        elif barrier:
            action, reason = "review_only", "recovery conflicts with component barrier"
        elif not flags["trunkRecovery"]:
            action, reason = "review_only", "trunk recovery is disabled by ablation"
        elif confidence == "high" and recovery.get("geometricSupport") and recovery.get("topologicalSupport"):
            action, reason = "recover", "independent geometric and topological support"
        else:
            action, reason = "review_only", "recovery evidence is insufficient"
        recovery_decisions.append(
            {
                "id": _stable_id("recovery", {"id": recovery.get("id"), "from": recovery.get("from"), "to": recovery.get("to")}),
                "candidateId": None,
                "legacyFrom": None,
                "legacyTo": None,
                "proposedFrom": recovery.get("from"),
                "proposedTo": recovery.get("to"),
                "finalAction": action,
                "confidence": confidence,
                "reason": reason,
                "supervised": supervised,
                "evidence": copy.deepcopy(recovery),
                "participatingModules": ["TL-004D"],
                "officialResultChanged": False,
                "officialDirectionChanged": False,
                "officialEligible": False,
            }
        )
        if barrier and recovery.get("geometricSupport"):
            module_conflicts.append(
                {
                    "decisionId": recovery_decisions[-1]["id"],
                    "candidateId": None,
                    "modules": ["TL-004B", "TL-004D"],
                    "competingActions": ["decompose", "recover"],
                    "rule": "barrier blocks automatic recovery",
                    "finalAction": action,
                }
            )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "strategyRevision": STRATEGY_REVISION,
        "mode": "shadow",
        "officialStrategy": "legacy",
        "shadowStrategy": "junction_aware_full",
        "moduleFlags": flags,
        "executionOrder": ["TL-004A", "TL-004B", "TL-004C", "TL-004D", "TL-004E", "consolidation", "human_controls"],
        "moduleOutputs": {
            "geometricEventCount": len(geometric["events"]),
            "intersectionEventCount": intersections["eventCount"],
            "trunkCount": len(trunks["trunks"]),
            "transitiveDecisionCount": len(transitive["decisions"]),
        },
        "candidateDecisions": final_decisions,
        "recoveryDecisions": recovery_decisions,
        "moduleConflicts": module_conflicts,
        "officialFlows": copy.deepcopy(flows),
        "officialFlowsChanged": False,
        "officialDirectionChanges": 0,
        "feedsStride": "legacy_only",
        "inputMutation": False,
    }


def apply_integrated_decisions(
    legacy_flows: Iterable[Mapping[str, Any]],
    candidate_decisions: Iterable[Mapping[str, Any]],
    recovery_decisions: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    original = copy.deepcopy(list(legacy_flows))
    decisions = {str(item["candidateId"]): copy.deepcopy(dict(item)) for item in candidate_decisions}
    output = []
    applied = []
    for flow in original:
        candidate_id = str(flow.get("id") or "")
        decision = decisions[candidate_id]
        action = decision["finalAction"]
        if action in {"keep", "review_only"}:
            output.append(copy.deepcopy(flow))
        elif action == "redirect":
            output.append({**copy.deepcopy(flow), "from": decision["proposedFrom"], "to": decision["proposedTo"], "shadowDerived": True})
        elif action == "block":
            pass
        elif action == "decompose":
            for index, relation in enumerate(decision.get("adjacentRelations") or []):
                output.append({"id": f"{candidate_id}:adjacent:{index}", "from": relation["from"], "to": relation["to"], "shadowDerived": True})
        else:
            raise ValueError(f"unsupported candidate action: {action}")
        applied.append({"candidateId": candidate_id, "action": action})
    for recovery in recovery_decisions:
        if recovery["finalAction"] != "recover" or recovery.get("supervised"):
            continue
        output.append({"id": recovery["id"], "from": recovery["proposedFrom"], "to": recovery["proposedTo"], "shadowDerived": True})
        applied.append({"candidateId": None, "decisionId": recovery["id"], "action": "recover"})

    unique = []
    seen = set()
    duplicates = []
    for flow in output:
        edge = _edge(flow)
        if edge in seen:
            duplicates.append({"from": edge[0], "to": edge[1], "discardedFlowId": flow.get("id")})
            continue
        seen.add(edge)
        unique.append(flow)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "flows": unique,
        "appliedDecisions": applied,
        "deduplicatedEdges": duplicates,
        "inputMutation": False,
        "reviewOnlyAppliedCount": 0,
    }


def structural_metrics(expected: list[dict[str, Any]], predicted: list[dict[str, Any]]) -> dict[str, Any]:
    raw = score_flows(expected, predicted)
    metrics = required_metric_view(raw)
    metrics["correctAdjacencyCount"] = raw["undirectedTruePositive"]
    metrics["falsePositiveEdges"] = raw["falsePositiveEdges"]
    metrics["missedEdges"] = raw["missedEdges"]
    metrics["reversedEdges"] = raw["reversedEdges"]
    return metrics


def evaluate_promotion(
    metrics: Mapping[str, Any],
    *,
    controls_pass: bool,
    correct_directions_changed: int,
    human_true_positives_blocked: int,
    possible_false_blocks: int,
    review_only_applied: int,
    gate_status: str,
    verifier_status: str,
    v12_status: str,
    tests_pass: bool,
    evidence_sufficient: bool,
) -> dict[str, Any]:
    baseline_false_positives = 90
    reduction = baseline_false_positives - int(metrics["falsePositiveEdgeCount"])
    reduction_rate = reduction / baseline_false_positives
    checks = {
        "falsePositiveEdgeCount": int(metrics["falsePositiveEdgeCount"]) <= 81,
        "falsePositiveReductionAtLeast10Percent": reduction_rate >= 0.10,
        "correctAdjacencyCount": int(metrics["correctAdjacencyCount"]) >= 52,
        "missedEdgeCount": int(metrics["missedEdgeCount"]) <= 19,
        "edgeExistenceRecall": float(metrics["edgeExistenceRecall"]) >= 0.7324,
        "edgeExistenceF1": float(metrics["edgeExistenceF1"]) >= 0.5083,
        "directionAccuracy": float(metrics["directionAccuracy"]) >= 0.8654,
        "correctDirectionsChanged": correct_directions_changed == 0,
        "controlsC01ToC07": controls_pass,
        "humanTruePositivesBlocked": human_true_positives_blocked == 0,
        "possibleFalseBlockCount": possible_false_blocks == 0,
        "reviewOnlyAppliedCount": review_only_applied == 0,
        "v15Gate": gate_status == "PASS",
        "projectVerifier": verifier_status == "PASS",
        "prospectiveV12": v12_status == "PASS",
        "tests": tests_pass,
    }
    all_metrics_pass = all(checks.values())
    if not controls_pass or human_true_positives_blocked or possible_false_blocks or correct_directions_changed:
        recommendation = "not_eligible_regression"
    elif not all_metrics_pass:
        recommendation = "not_eligible_metrics"
    elif not evidence_sufficient:
        recommendation = "not_eligible_insufficient_evidence"
    else:
        recommendation = "eligible_for_controlled_promotion"
    return {
        "checks": checks,
        "passedCount": sum(checks.values()),
        "checkCount": len(checks),
        "allCriteriaPassed": all_metrics_pass and evidence_sufficient,
        "falsePositiveReduction": reduction,
        "falsePositiveReductionRate": reduction_rate,
        "evidenceSufficient": evidence_sufficient,
        "recommendation": recommendation,
        "defaultStrategyChanged": False,
    }
