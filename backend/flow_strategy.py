"""Selectable, reversible flow strategies for the production pipeline."""

from __future__ import annotations

import copy
from collections import Counter
from typing import Any, Mapping

from backend.integrated_junction_strategy import orchestrate_junction_aware
from backend.structural_line_gate import (
    GATE_REVISION,
    apply_structural_line_gate,
    evaluate_structural_line_gate,
)


DEFAULT_FLOW_STRATEGY = "legacy"
SUPPORTED_FLOW_STRATEGIES = ("legacy", "junction_aware_controlled")
CONTROLLED_MODULE_FLAGS = {
    "endpointRedirect": False,
    "crossingBlock": True,
    "trunkRecovery": True,
    "transitiveSuppression": True,
}
STRATEGY_REVISION = "tl-promotion-001-controlled-v1"


def resolve_flow_strategy(value: str | None) -> str:
    strategy = str(value or DEFAULT_FLOW_STRATEGY).strip().lower()
    if strategy not in SUPPORTED_FLOW_STRATEGIES:
        supported = ", ".join(SUPPORTED_FLOW_STRATEGIES)
        raise ValueError(f"unsupported flow strategy '{strategy}'; expected one of: {supported}")
    return strategy


def _context(architecture: Mapping[str, Any]) -> dict[str, Any]:
    value = architecture.get("flowStrategyContext") or {}
    if not isinstance(value, Mapping):
        raise ValueError("flowStrategyContext must be an object")
    return copy.deepcopy(dict(value))


def _flows_with_ids(flows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for index, flow in enumerate(flows, start=1):
        item = copy.deepcopy(flow)
        candidate_id = str(item.get("id") or f"flow_{index}")
        if candidate_id in seen:
            raise ValueError("flow ids must be unique for junction_aware_controlled")
        seen.add(candidate_id)
        item["id"] = candidate_id
        result.append(item)
    return result


def _mapping_list(context: Mapping[str, Any], name: str) -> list[dict[str, Any]]:
    value = context.get(name) or []
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"flowStrategyContext.{name} must be an array of objects")
    return copy.deepcopy(value)


def _string_list(context: Mapping[str, Any], name: str) -> list[str]:
    value = context.get(name) or []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"flowStrategyContext.{name} must be an array of strings")
    return list(value)


def _edge_list(context: Mapping[str, Any], name: str) -> list[list[str]]:
    value = context.get(name) or []
    valid = isinstance(value, list) and all(
        isinstance(item, (list, tuple))
        and len(item) == 2
        and all(isinstance(endpoint, str) for endpoint in item)
        for item in value
    )
    if not valid:
        raise ValueError(f"flowStrategyContext.{name} must contain two-item string arrays")
    return [list(item) for item in value]


def _structural_evidence(
    flow: Mapping[str, Any],
    decision: Mapping[str, Any],
    supplied: Mapping[str, Any] | None,
) -> dict[str, Any]:
    explicit = copy.deepcopy(dict(supplied or {}))
    ports = decision.get("ports") or []
    verified = [
        item
        for item in ports
        if isinstance(item, Mapping)
        and bool((item.get("geometricEvidence") or {}).get("endpointContactVerified"))
    ]
    source_contact = any(item.get("componentId") == decision.get("legacyFrom") for item in verified)
    destination_contact = any(item.get("componentId") == decision.get("legacyTo") for item in verified)
    direction = str(flow.get("directionEvidence") or "")
    direction_confidence = float(flow.get("directionConfidence") or 0)
    direct = decision.get("directEdgeEvidence") or {}

    alignment = explicit.get("structuralAlignment") or {}
    continuity = explicit.get("connectorContinuity") or {
        "present": bool(direct.get("confirmed")),
        "confidence": "high" if direct.get("confirmed") else "low",
        "source": "direct_edge_evidence",
    }
    return {
        "sourcePortConfirmed": bool(explicit.get("sourcePortConfirmed", source_contact)),
        "destinationPortConfirmed": bool(explicit.get("destinationPortConfirmed", destination_contact)),
        "structuralAlignment": copy.deepcopy(alignment),
        "connectorContinuity": copy.deepcopy(continuity),
        "arrowheadPresent": bool(
            explicit.get(
                "arrowheadPresent",
                direction in {"visual_arrowhead", "supervised_arrowhead"}
                and direction_confidence >= 0.75,
            )
        ),
        "arrowheadEvidence": copy.deepcopy(
            explicit.get("arrowheadEvidence")
            or {"type": direction or "not_available", "confidence": direction_confidence}
        ),
        "unmarkedCrossingCount": int(
            explicit.get("unmarkedCrossingCount", len(decision.get("intersectionIds") or []))
        ),
        "humanReview": copy.deepcopy(explicit.get("humanReview") or {}),
        "controlProtected": bool(explicit.get("controlProtected", decision.get("protected"))),
    }


def _legacy_trace(flow_count: int) -> dict[str, Any]:
    return {
        "strategy": "legacy",
        "strategyRevision": STRATEGY_REVISION,
        "defaultStrategy": DEFAULT_FLOW_STRATEGY,
        "selectableStrategies": list(SUPPORTED_FLOW_STRATEGIES),
        "reversible": True,
        "endpointRedirectEnabled": False,
        "inputFlowCount": flow_count,
        "outputFlowCount": flow_count,
        "changedFlowCount": 0,
        "actionCounts": {"keep": flow_count},
        "structuralGate": {"executed": False, "blockedCount": 0},
    }


def apply_flow_strategy(
    architecture: Mapping[str, Any],
    strategy: str | None = None,
) -> dict[str, Any]:
    """Apply the selected strategy to a copy of an architecture payload."""

    selected = resolve_flow_strategy(strategy)
    result = copy.deepcopy(dict(architecture))
    raw_flows = result.get("flows") or []
    components = result.get("components") or []
    if not isinstance(raw_flows, list) or any(not isinstance(item, Mapping) for item in raw_flows):
        raise ValueError("flows must be an array of objects")
    if not isinstance(components, list) or any(not isinstance(item, Mapping) for item in components):
        raise ValueError("components must be an array of objects")

    if selected == "legacy":
        trace = _legacy_trace(len(raw_flows))
    else:
        context = _context(result)
        flows = _flows_with_ids(copy.deepcopy(raw_flows))
        evidence_by_candidate = context.get("structuralEvidenceByCandidate") or {}
        if not isinstance(evidence_by_candidate, Mapping) or any(
            not isinstance(value, Mapping) for value in evidence_by_candidate.values()
        ):
            raise ValueError("flowStrategyContext.structuralEvidenceByCandidate must be an object of objects")

        structural_ids = set(_string_list(context, "structuralCandidateIds"))
        structural_ids.update(str(key) for key in evidence_by_candidate)
        integrated = orchestrate_junction_aware(
            flows,
            components,
            segments=_mapping_list(context, "segments"),
            terminal_ports=_mapping_list(context, "terminalPorts"),
            explicit_junctions=_mapping_list(context, "explicitJunctions"),
            adjacent_relations=_mapping_list(context, "adjacentRelations"),
            confirmed_direct_edges=_mapping_list(context, "confirmedDirectEdges"),
            human_confirmed_shortcuts=_mapping_list(context, "humanConfirmedShortcuts"),
            protected_edges=_edge_list(context, "protectedEdges"),
            protected_candidate_ids=_string_list(context, "protectedCandidateIds"),
            structural_candidate_ids=sorted(structural_ids),
            recovery_candidates=_mapping_list(context, "recoveryCandidates"),
            module_flags=CONTROLLED_MODULE_FLAGS,
        )
        decisions = integrated["candidateDecisions"]
        flow_by_id = {str(item["id"]): item for item in flows}
        gate_evidence = {
            str(item["candidateId"]): _structural_evidence(
                flow_by_id[str(item["candidateId"])],
                item,
                evidence_by_candidate.get(str(item["candidateId"])),
            )
            for item in decisions
        }
        gate = evaluate_structural_line_gate(decisions, gate_evidence)
        applied = apply_structural_line_gate(flows, decisions, gate["decisions"])
        result["flows"] = applied["flows"]
        action_counts = Counter(item["action"] for item in applied["appliedDecisions"])
        changed_flow_count = sum(
            count for action, count in action_counts.items() if action not in {"keep", "review_only"}
        )
        trace = {
            "strategy": selected,
            "strategyRevision": STRATEGY_REVISION,
            "defaultStrategy": DEFAULT_FLOW_STRATEGY,
            "selectableStrategies": list(SUPPORTED_FLOW_STRATEGIES),
            "reversible": True,
            "baseStrategy": "full_without_endpoint_redirect",
            "moduleFlags": copy.deepcopy(CONTROLLED_MODULE_FLAGS),
            "executionOrder": [
                "TL-004A",
                "TL-004B",
                "TL-004C",
                "TL-004D",
                "TL-004E",
                "TL-004F",
                "TL-STRUCT-001A",
            ],
            "endpointRedirectEnabled": False,
            "inputFlowCount": len(flows),
            "outputFlowCount": len(result["flows"]),
            "changedFlowCount": changed_flow_count,
            "actionCounts": dict(sorted(action_counts.items())),
            "moduleOutputs": copy.deepcopy(integrated["moduleOutputs"]),
            "structuralGate": {
                "executed": True,
                "revision": GATE_REVISION,
                "blockedCount": gate["blockedCount"],
                "reviewOnlyCount": gate["reviewOnlyCount"],
            },
            "candidateDecisions": copy.deepcopy(applied["updatedDecisions"]),
            "structuralGateDecisions": copy.deepcopy(gate["decisions"]),
            "newEdgeCount": applied["newEdgeCount"],
            "reviewOnlyAppliedCount": applied["reviewOnlyAppliedCount"],
        }

    metadata = copy.deepcopy(result.get("structureMetadata") or {})
    metadata["flowStrategy"] = copy.deepcopy(trace)
    result["structureMetadata"] = metadata
    result["flowStrategy"] = selected
    result["flowStrategyTrace"] = trace
    return result
