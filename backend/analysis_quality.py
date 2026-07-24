"""Conservative structural quality gate for reconstructed architectures."""

from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from typing import Any


QUALITY_GATE_VERSION = "mvp-hardening-001"

_GROUPING_TERMS = (
    "account",
    "accounts",
    "availability zone",
    "organization",
    "organizations",
    "region",
    "resource group",
    "subnet",
    "tenant",
    "virtual network",
    "vnet",
    "vpc",
)
_PROVIDER_PATTERNS = {
    "aws": re.compile(
        r"\b(?:aws|amazon|cloudfront|cloudwatch|lambda|ec2|dynamodb|s3|kms)\b",
        re.IGNORECASE,
    ),
    "azure": re.compile(
        r"\b(?:azure|microsoft|entra|cosmos\s+db|app\s+service)\b",
        re.IGNORECASE,
    ),
    "gcp": re.compile(
        r"\b(?:gcp|google\s+cloud|bigquery|cloud\s+run|cloud\s+armor|"
        r"artifact\s+registry|vertex\s+ai|pub\s*/?\s*sub)\b",
        re.IGNORECASE,
    ),
}
_EXPLICIT_LOOP_EVIDENCE = {
    "explicit_arrow",
    "human_confirmed",
    "manual_review",
    "reviewed_json",
}
_PENALTIES = {
    "multiple_diagrams_suspected": 0.45,
    "grouping_labels_as_components": 0.18,
    "provider_inconsistency": 0.20,
    "suspicious_duplicate_components": 0.15,
    "semantic_self_loop_blocked": 0.18,
    "duplicate_flow_blocked": 0.08,
}


def assess_analysis_quality(architecture: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a sanitized copy and a deterministic structural quality assessment."""
    sanitized = deepcopy(architecture)
    components = sanitized.get("components") or []
    component_by_id = {
        component.get("id"): component
        for component in components
        if isinstance(component, dict) and component.get("id")
    }
    reasons: list[dict[str, Any]] = []

    duplicate_groups = _duplicate_component_groups(components)
    if duplicate_groups:
        reasons.append(_reason(
            "suspicious_duplicate_components",
            "warning",
            "Componentes com o mesmo nome e tipo aparecem mais de uma vez.",
            {"groups": duplicate_groups},
        ))

    repeated_panel_evidence = _repeated_panel_evidence(duplicate_groups, component_by_id)
    if repeated_panel_evidence:
        reasons.append(_reason(
            "multiple_diagrams_suspected",
            "critical",
            "A imagem parece conter dois ou mais diagramas comparativos.",
            repeated_panel_evidence,
        ))

    grouping_ids = [
        component["id"]
        for component in components
        if isinstance(component, dict)
        and component.get("id")
        and _looks_like_grouping(component.get("name") or component.get("ocrLabel") or "")
    ]
    if grouping_ids:
        reasons.append(_reason(
            "grouping_labels_as_components",
            "warning",
            "Limites ou agrupamentos podem ter sido classificados como componentes ativos.",
            {"componentIds": grouping_ids},
        ))

    provider_evidence = _provider_inconsistency(components, sanitized)
    if provider_evidence:
        reasons.append(_reason(
            "provider_inconsistency",
            "warning",
            "Foram encontrados providers incompatíveis com as evidências textuais do diagrama.",
            provider_evidence,
        ))

    kept_flows: list[dict[str, Any]] = []
    blocked_self_loops: list[str] = []
    blocked_duplicates: list[str] = []
    seen_edges: set[tuple[str, str]] = set()
    for index, flow in enumerate(sanitized.get("flows") or [], start=1):
        if not isinstance(flow, dict):
            kept_flows.append(flow)
            continue
        flow_id = str(flow.get("id") or f"flow-{index}")
        source = component_by_id.get(flow.get("from"))
        target = component_by_id.get(flow.get("to"))
        if _is_unconfirmed_semantic_self_loop(flow, source, target):
            blocked_self_loops.append(flow_id)
            continue
        edge = (str(flow.get("from") or ""), str(flow.get("to") or ""))
        if edge in seen_edges:
            blocked_duplicates.append(flow_id)
            continue
        seen_edges.add(edge)
        kept_flows.append(flow)
    sanitized["flows"] = kept_flows

    if blocked_self_loops:
        reasons.append(_reason(
            "semantic_self_loop_blocked",
            "warning",
            "Fluxos entre detecções semanticamente idênticas foram bloqueados por falta de confirmação explícita.",
            {"flowIds": blocked_self_loops},
        ))
    if blocked_duplicates:
        reasons.append(_reason(
            "duplicate_flow_blocked",
            "warning",
            "Fluxos direcionados duplicados foram removidos antes da análise de ameaças.",
            {"flowIds": blocked_duplicates},
        ))

    score = round(max(0.0, 1.0 - sum(_PENALTIES[reason["code"]] for reason in reasons)), 4)
    codes = {reason["code"] for reason in reasons}
    if "multiple_diagrams_suspected" in codes or score < 0.45:
        status = "rejected"
        action = (
            "Envie um único diagrama por imagem. Recorte painéis comparativos, cabeçalhos e legendas, "
            "depois revise componentes e conexões antes de gerar o relatório."
        )
    elif reasons or score < 0.85:
        status = "review_required"
        action = "Revise os itens sinalizados e confirme a arquitetura antes de aceitar o relatório."
    else:
        status = "reliable"
        action = "A estrutura passou pelo gate automático; mantenha a revisão humana antes da aprovação final."

    quality = {
        "status": status,
        "score": score,
        "reasons": reasons,
        "recommendedAction": action,
        "gateVersion": QUALITY_GATE_VERSION,
        "blockedFlowIds": blocked_self_loops + blocked_duplicates,
    }
    sanitized["analysisQualityTrace"] = {
        "gateVersion": QUALITY_GATE_VERSION,
        "inputFlowCount": len(architecture.get("flows") or []),
        "outputFlowCount": len(kept_flows),
        "blockedFlowIds": quality["blockedFlowIds"],
    }
    return sanitized, quality


def _reason(code: str, severity: str, message: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"code": code, "severity": severity, "message": message, "evidence": evidence}


def _normalize_label(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_value).split())


def _duplicate_component_groups(components: list[Any]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[str]] = {}
    for component in components:
        if not isinstance(component, dict) or not component.get("id"):
            continue
        key = (_normalize_label(component.get("name")), str(component.get("type") or ""))
        if not key[0]:
            continue
        groups.setdefault(key, []).append(str(component["id"]))
    return [
        {"normalizedName": name, "type": component_type, "componentIds": ids}
        for (name, component_type), ids in sorted(groups.items())
        if len(ids) > 1
    ]


def _center(component: dict[str, Any] | None) -> tuple[float, float] | None:
    bbox = (component or {}).get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    try:
        x1, y1, x2, y2 = (float(value) for value in bbox)
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def _repeated_panel_evidence(
    duplicate_groups: list[dict[str, Any]],
    component_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    displacements: list[dict[str, Any]] = []
    for group in duplicate_groups:
        centers = [
            (component_id, _center(component_by_id.get(component_id)))
            for component_id in group["componentIds"]
        ]
        centers = [(component_id, center) for component_id, center in centers if center is not None]
        if len(centers) != 2:
            continue
        (first_id, first), (second_id, second) = centers
        dx = abs(second[0] - first[0])
        dy = abs(second[1] - first[1])
        distance = max(dx, dy)
        if distance < 80:
            continue
        axis = "vertical" if dy >= dx else "horizontal"
        off_axis = dx if axis == "vertical" else dy
        if off_axis > max(40, distance * 0.30):
            continue
        displacements.append({
            "componentIds": [first_id, second_id],
            "axis": axis,
            "distance": round(distance, 2),
            "offAxisDistance": round(off_axis, 2),
        })
    if len(displacements) < 2:
        return None
    axes = {item["axis"] for item in displacements}
    if len(axes) != 1:
        return None
    distances = [item["distance"] for item in displacements]
    if max(distances) - min(distances) > max(distances) * 0.35:
        return None
    return {"axis": next(iter(axes)), "alignedDuplicateGroups": displacements}


def _looks_like_grouping(value: Any) -> bool:
    label = _normalize_label(value)
    return any(re.search(rf"\b{re.escape(term)}\b", label) for term in _GROUPING_TERMS)


def _provider_mentions(text: str) -> dict[str, int]:
    return {provider: len(pattern.findall(text)) for provider, pattern in _PROVIDER_PATTERNS.items()}


def _provider_inconsistency(
    components: list[Any],
    architecture: dict[str, Any],
) -> dict[str, Any] | None:
    ocr_metadata = architecture.get("ocrMetadata")
    text_regions = ocr_metadata.get("textRegions") if isinstance(ocr_metadata, dict) else []
    if not isinstance(text_regions, list):
        text_regions = []
    global_text = " ".join(
        [str(architecture.get("name") or "")]
        + [str(component.get("name") or "") for component in components if isinstance(component, dict)]
        + [str(region.get("text") or "") for region in text_regions if isinstance(region, dict)]
    )
    mentions = _provider_mentions(global_text)
    ranked = sorted(mentions.items(), key=lambda item: (-item[1], item[0]))
    dominant, dominant_count = ranked[0]
    second_count = ranked[1][1]
    if dominant_count < 2 or (second_count and dominant_count < second_count * 2):
        return None

    inconsistent: list[dict[str, str]] = []
    for component in components:
        if not isinstance(component, dict):
            continue
        assigned = component.get("provider") or "generic"
        if assigned in {"generic", dominant}:
            continue
        local_text = " ".join([
            str(component.get("name") or ""),
            str(component.get("ocrLabel") or ""),
            str((component.get("ocrEvidence") or {}).get("text") or ""),
        ])
        if _provider_mentions(local_text).get(assigned, 0) == 0:
            inconsistent.append({"componentId": str(component.get("id")), "assignedProvider": str(assigned)})
    if not inconsistent:
        return None
    return {
        "dominantProvider": dominant,
        "providerMentions": mentions,
        "inconsistentComponents": inconsistent,
    }


def _is_unconfirmed_semantic_self_loop(
    flow: dict[str, Any],
    source: dict[str, Any] | None,
    target: dict[str, Any] | None,
) -> bool:
    if not source or not target or source.get("id") == target.get("id"):
        return False
    if _normalize_label(source.get("name")) != _normalize_label(target.get("name")):
        return False
    explicitly_confirmed = (
        flow.get("reviewStatus") == "confirmed"
        and not flow.get("inferred", False)
        and flow.get("evidence") in _EXPLICIT_LOOP_EVIDENCE
    )
    return not explicitly_confirmed
