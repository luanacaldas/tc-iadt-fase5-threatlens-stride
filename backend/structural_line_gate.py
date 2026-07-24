"""Conservative structural-line gate for TL-STRUCT-001A shadow evaluation."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Iterable, Mapping

from backend.integrated_junction_strategy import apply_integrated_decisions


SCHEMA_VERSION = "1.0"
GATE_REVISION = "tl-struct-001a-conservative-v1"
STRUCTURAL_KINDS = {
    "container_border",
    "subnet_border",
    "grid_line",
    "project_border",
    "area_border",
    "icon_internal_stroke",
}


def _stable_id(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"struct-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]}"


def _confirmed_endpoint(evidence: Mapping[str, Any], name: str) -> bool:
    value = evidence.get(name)
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be boolean")
    return value


def evaluate_structural_line_candidate(
    candidate: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a diagnostic gate decision without mutating the base decision."""

    base = copy.deepcopy(dict(candidate))
    observed = copy.deepcopy(dict(evidence))
    candidate_id = str(base.get("candidateId") or "")
    if not candidate_id:
        raise ValueError("candidateId is required")
    base_action = str(base.get("finalAction") or "")
    if base_action not in {"keep", "block", "decompose", "review_only"}:
        raise ValueError(f"unsupported base action: {base_action}")

    source_contact = _confirmed_endpoint(observed, "sourcePortConfirmed")
    destination_contact = _confirmed_endpoint(observed, "destinationPortConfirmed")
    control_protected = bool(observed.get("controlProtected") or base.get("protected"))
    alignment = observed.get("structuralAlignment") or {}
    kind = str(alignment.get("kind") or "unknown")
    alignment_confidence = str(alignment.get("confidence") or "low")
    alignment_source = str(alignment.get("source") or "not_available")
    strong_alignment = bool(alignment.get("aligned")) and kind in STRUCTURAL_KINDS and alignment_confidence == "high"
    continuity = observed.get("connectorContinuity") or {}
    own_continuity = bool(continuity.get("present")) and str(continuity.get("confidence") or "low") in {"medium", "high"}
    arrowhead_present = bool(observed.get("arrowheadPresent"))
    crossing_count = int(observed.get("unmarkedCrossingCount") or 0)
    human = observed.get("humanReview") or {}
    human_confirmed = (
        human.get("decision") == "confirmed_false_positive"
        and human.get("primaryCause") == "structural_line"
        and human.get("confidence") == "high"
    )
    no_endpoint_contacts = not source_contact and not destination_contact
    no_connector_evidence = not own_continuity
    direction_or_crossing_support = not arrowhead_present or crossing_count > 0
    autonomous_support = alignment_source == "geometric" and crossing_count > 0 and not arrowhead_present
    sufficient_support = human_confirmed or autonomous_support

    checks = {
        "baseActionIsReviewOnly": base_action == "review_only",
        "noConfirmedEndpointContacts": no_endpoint_contacts,
        "strongStructuralAlignment": strong_alignment,
        "noOwnConnectorContinuity": no_connector_evidence,
        "arrowheadAbsentOrUnmarkedCrossingPresent": direction_or_crossing_support,
        "humanOrIndependentGeometricCorroboration": sufficient_support,
        "controlNotProtected": not control_protected,
    }
    block = all(checks.values())
    if block:
        gate_action = "block"
        reason = "strong structural-line evidence with no valid endpoint contacts"
        confidence = "high"
    elif base_action == "review_only" and not control_protected:
        gate_action = "review_only"
        reason = "structural evidence is incomplete or ambiguous"
        confidence = "low"
    else:
        gate_action = "no_change"
        reason = "base decision or regression protection is preserved"
        confidence = str(base.get("confidence") or "high")

    return {
        "schemaVersion": SCHEMA_VERSION,
        "gateRevision": GATE_REVISION,
        "id": _stable_id({"candidateId": candidate_id, "from": base.get("legacyFrom"), "to": base.get("legacyTo")}),
        "candidateId": candidate_id,
        "inventoryId": base.get("inventoryId"),
        "legacyFrom": base.get("legacyFrom"),
        "legacyTo": base.get("legacyTo"),
        "baseAction": base_action,
        "gateAction": gate_action,
        "finalAction": "block" if block else base_action,
        "confidence": confidence,
        "reason": reason,
        "structuralKind": kind,
        "alignmentSource": alignment_source,
        "checks": checks,
        "evidence": observed,
        "controlProtected": control_protected,
        "humanConfirmed": human_confirmed,
        "autonomousSupport": autonomous_support,
        "officialResultChanged": False,
        "officialDirectionChanged": False,
    }


def evaluate_structural_line_gate(
    candidates: Iterable[Mapping[str, Any]],
    evidence_by_candidate: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    original = copy.deepcopy(list(candidates))
    decisions = [
        evaluate_structural_line_candidate(item, evidence_by_candidate.get(str(item.get("candidateId") or ""), {}))
        for item in sorted(original, key=lambda value: (str(value.get("candidateId") or ""), str(value.get("legacyFrom") or ""), str(value.get("legacyTo") or "")))
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "gateRevision": GATE_REVISION,
        "mode": "shadow",
        "baseStrategy": "full_without_endpoint_redirect",
        "decisionCount": len(decisions),
        "blockedCount": sum(item["gateAction"] == "block" for item in decisions),
        "reviewOnlyCount": sum(item["gateAction"] == "review_only" for item in decisions),
        "decisions": decisions,
        "inputMutation": False,
        "officialStrategy": "legacy",
        "officialResultChanged": False,
        "feedsStride": "legacy_only",
    }


def apply_structural_line_gate(
    legacy_flows: Iterable[Mapping[str, Any]],
    base_decisions: Iterable[Mapping[str, Any]],
    gate_decisions: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    original_flows = copy.deepcopy(list(legacy_flows))
    original_decisions = copy.deepcopy(list(base_decisions))
    gate_index = {str(item["candidateId"]): item for item in gate_decisions}
    updated = []
    for decision in original_decisions:
        candidate_id = str(decision["candidateId"])
        gate = gate_index[candidate_id]
        item = copy.deepcopy(decision)
        if gate["gateAction"] == "block":
            item["finalAction"] = "block"
            item["reason"] = gate["reason"]
            item["confidence"] = gate["confidence"]
            item["structuralGateDecisionId"] = gate["id"]
        updated.append(item)
    applied = apply_integrated_decisions(original_flows, updated)
    legacy_edges = {(str(item.get("from")), str(item.get("to"))) for item in original_flows}
    experimental_edges = {(str(item.get("from")), str(item.get("to"))) for item in applied["flows"]}
    new_edges = sorted(experimental_edges - legacy_edges)
    return {
        **applied,
        "baseStrategy": "full_without_endpoint_redirect",
        "structuralGateRevision": GATE_REVISION,
        "updatedDecisions": updated,
        "newEdges": [{"from": source, "to": target} for source, target in new_edges],
        "newEdgeCount": len(new_edges),
        "officialResultChanged": False,
        "feedsStride": "legacy_only",
    }
