"""Detector de componentes via YOLOv8.

Quando o modelo treinado não está disponível, retorna None e o pipeline
usa o Gemini Vision como fallback automático.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import math
import re
from collections import Counter
from pathlib import Path

from backend.config import (
    YOLO_CONFIDENCE_THRESHOLD,
    YOLO_CALIBRATION_PATH,
    YOLO_MIN_DETECTION_CONFIDENCE,
    YOLO_MODEL_PATH,
)

logger = logging.getLogger(__name__)

_model = None
_model_loaded = False
_model_sha256: str | None = None
_confidence_calibration: dict | None = None
_confidence_calibration_loaded = False

EXTERNAL_NODE_TYPES = {"user", "internet"}

LABEL_TYPE_HINTS = {
    "api_gateway": ("api", "gateway", "apim", "endpoint"),
    "backup": ("backup", "recovery", "snapshot", "vault"),
    "cdn": ("cdn", "cloudfront", "content delivery", "front door"),
    "compute": ("compute", "server", "ec2", "lambda", "function", "container", "kubernetes", "cloud run", "sagemaker"),
    "database": ("database", " db", "rds", "sql", "dynamo", "cosmos", "firestore", "aurora", "postgres", "mysql", "mongo"),
    "identity_provider": ("identity", "entra", "iam", "cognito", "auth", "oauth", "openid"),
    "internet": ("internet", "public network", "web"),
    "load_balancer": ("load balancer", "elb", "alb", "nlb"),
    "monitoring": ("monitor", "cloudwatch", "logging", "logs", "observability", "insight"),
    "queue": ("queue", "sqs", "kafka", "pub/sub", "service bus", "rabbitmq"),
    "secrets_kms": ("secret", "kms", "key vault", "key management"),
    "storage": ("storage", "s3", "bucket", "blob", "object store", "file store"),
    "user": ("user", "customer", "client", "actor", "admin"),
    "waf": ("waf", "firewall", "web application firewall"),
}

OCR_PROPOSAL_PATTERNS = {
    "api_gateway": (
        r"\bapi gateway\b", r"\bapplication gateway\b", r"\bapi management\b",
        r"\bvpn gateway\b", r"^rest$", r"^soap$",
    ),
    "backup": (r"\bbackup\b", r"\brecovery vault\b"),
    "cdn": (r"\bcdn\b", r"\bcloudfront\b", r"\bfront door\b"),
    "compute": (
        r"\bcompute\b", r"\bcloud run\b", r"\blambda\b", r"\bfunctions?\b",
        r"\bhandlers?\b", r"\bworkers?\b", r"\blogic apps?\b", r"\bkubernetes\b",
        r"\bgke\b", r"\bcluster\b", r"\bapp service\b", r"\bvirtual machines?\b",
        r"\bfargate\b", r"\bsagemaker\b", r"\bfoundry (?:agent|account)\b",
        r"\bopenai model\b", r"\bbuild agents?\b", r"\bbastion\b", r"\bnotebook\b",
        r"\bmicroservices?\b", r"\bcomprehend\b", r"\bglue(?: etl)?\b",
        r"\btranscoder\b", r"\bmediaconvert\b", r"\bvpc access connector\b",
        r"\binternal resource\b", r"\bvideo uploads?\b", r"\bdeveloper portal\b",
        r"\bapi server\b", r"\b(?:azure|saas) services\b",
    ),
    "database": (
        r"\bdatabase\b", r"\bsql\b", r"\brds\b", r"\bdynamodb\b", r"\bcosmos db\b",
        r"\bdocumentdb\b", r"\baurora\b", r"\belasticache\b",
    ),
    "identity_provider": (
        r"\bmicrosoft entra\b", r"\bentra id\b", r"^entra$", r"\bcognito\b", r"\biam\b",
    ),
    "internet": (r"\binternet\b", r"\bcross-premises network\b"),
    "load_balancer": (r"\bload balancer\b", r"\bbalancer\b"),
    "monitoring": (
        r"\blogging\b", r"\bcloudwatch\b", r"\bmonitor(?:ing)?\b",
        r"\bapplication insights\b", r"\blog analytics\b", r"\bvisualization\b",
        r"\bcloudtrail\b",
    ),
    "queue": (
        r"\bsqs\b", r"\bqueue\b", r"\bpub.?sub\b", r"\bservice bus\b",
        r"\b(?:amazon )?ses\b", r"\bsimple email service\b",
    ),
    "secrets_kms": (
        r"\bkms\b", r"\bkey vault\b", r"\bsecret manager\b",
        r"\bkey management service\b",
    ),
    "storage": (
        r"\bstorage\b", r"\bamazon s3\b", r"\bbucket\b", r"\bartifact registry\b",
        r"\bsource repositories\b", r"\b(?:azure )?ai search\b", r"\bopensearch catalog\b",
        r"\braw data\b", r"\bprocessed data\b", r"\b(?:amazon )?efs\b",
        r"\belastic file system\b",
    ),
    "user": (
        r"^users?$", r"^clients?$", r"^developer$", r"\bmobile client\b",
        r"\boperations approval\b", r"\bapi consumer\b",
    ),
    "waf": (
        r"\bwaf\b", r"\bfirewall\b", r"\bcloud armor\b",
        r"\bingress and egress rules\b", r"\bshield\b",
    ),
}


def _load_model():
    global _model, _model_loaded, _model_sha256
    if _model_loaded:
        return

    model_path = Path(YOLO_MODEL_PATH)
    if not model_path.exists():
        _model_loaded = True
        _model = None
        return

    try:
        from ultralytics import YOLO
        _model = YOLO(str(model_path))
        _model_sha256 = _sha256(model_path)
        print(f"[detector] YOLOv8 model loaded from {model_path}")
    except Exception as exc:
        print(f"[detector] Failed to load YOLO model: {exc}")
        _model = None

    _model_loaded = True


def is_available() -> bool:
    _load_model()
    return _model is not None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_confidence_calibration() -> dict | None:
    global _confidence_calibration, _confidence_calibration_loaded
    if _confidence_calibration_loaded:
        return _confidence_calibration
    path = Path(YOLO_CALIBRATION_PATH)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if len(payload.get("coef") or []) != 2:
            raise ValueError("expected two calibration coefficients")
        _confidence_calibration = payload
    except Exception as exc:
        logger.warning("[detector] Confidence calibration unavailable: %s", exc)
        _confidence_calibration = None
    _confidence_calibration_loaded = True
    return _confidence_calibration


def _apply_confidence_calibration(raw_confidence: float, area_ratio: float, payload: dict) -> float:
    bounded = min(1 - 1e-6, max(1e-6, raw_confidence))
    features = [math.log(bounded / (1 - bounded)), math.log(max(area_ratio, 1e-7))]
    score = float(payload["intercept"]) + sum(
        float(weight) * feature for weight, feature in zip(payload["coef"], features)
    )
    if score >= 0:
        probability = 1 / (1 + math.exp(-score))
    else:
        exp_score = math.exp(score)
        probability = exp_score / (1 + exp_score)
    return round(probability, 3)


def _calibrate_confidence(raw_confidence: float, area_ratio: float) -> float:
    payload = _load_confidence_calibration()
    return _apply_confidence_calibration(raw_confidence, area_ratio, payload) if payload else round(raw_confidence, 3)


def _automatic_acceptance_threshold() -> float:
    payload = _load_confidence_calibration()
    return float(payload.get("automaticAcceptanceThreshold", YOLO_CONFIDENCE_THRESHOLD)) if payload else YOLO_CONFIDENCE_THRESHOLD


def status() -> dict:
    _load_model()
    from backend.ocr import status as ocr_status

    names = getattr(_model, "names", {}) if _model is not None else {}
    if isinstance(names, dict):
        classes = [names[index] for index in sorted(names)]
    else:
        classes = list(names)
    calibration = _load_confidence_calibration()
    return {
        "available": _model is not None,
        "modelPath": str(YOLO_MODEL_PATH),
        "modelSha256": _model_sha256,
        "classes": classes,
        "minimumDetectionConfidence": YOLO_MIN_DETECTION_CONFIDENCE,
        "automaticAcceptanceConfidence": _automatic_acceptance_threshold(),
        "confidenceCalibration": {
            "available": calibration is not None,
            "path": YOLO_CALIBRATION_PATH,
            "method": calibration.get("method") if calibration else None,
            "split": calibration.get("split") if calibration else None,
        },
        "structureExtraction": {
            "lineDetection": importlib.util.find_spec("cv2") is not None,
            "trustBoundaryDetection": importlib.util.find_spec("cv2") is not None,
            "ocr": ocr_status(),
        },
    }


def _calculate_confidence_threshold(bbox_area: float, image_area: float) -> float:
    """Raises the floor only for extremely small boxes, which are noisier."""
    size_ratio = bbox_area / image_area if image_area > 0 else 0.01
    if size_ratio < 0.0003:
        return 0.50
    if size_ratio < 0.001:
        return 0.40
    return YOLO_MIN_DETECTION_CONFIDENCE


def _extract_text_from_box(image_path: str, bbox: list[int], padding: int = 6) -> str:
    """Compatibility wrapper around the geometry-aware OCR adapter."""
    try:
        from backend.ocr import extract_text_lines, match_component_label

        match = match_component_label(extract_text_lines(image_path), bbox)
        return str(match.get("text") or "") if match else ""
    except Exception as exc:
        logger.debug("[detector] OCR unavailable: %s", exc)
        return ""


def _infer_provider(cls_name: str, ocr_label: str = "") -> str:
    """Infer provider only from explicit textual evidence, never from role alone."""
    evidence = f"{cls_name} {ocr_label}".lower()
    provider_hints = {
        "aws": ("aws", "amazon", "cloudfront", "cloudwatch", "lambda", "ec2", "dynamodb", "s3"),
        "azure": ("azure", "microsoft", "entra", "cosmos db", "app service"),
        "gcp": (
            "gcp", "google cloud", "bigquery", "cloud run", "cloud armor",
            "artifact registry", "serverless vpc", "vertex ai", "pub/sub",
        ),
    }
    for provider, hints in provider_hints.items():
        if any(hint in evidence for hint in hints):
            return provider
    return "generic"


def _ocr_label_is_compatible(cls_name: str, ocr_label: str) -> bool:
    normalized = f" {str(ocr_label or '').lower()} "
    hinted_types = {
        component_type
        for component_type, hints in LABEL_TYPE_HINTS.items()
        if any(hint in normalized for hint in hints)
    }
    return not hinted_types or cls_name in hinted_types


def _semantic_type_from_label(label: str) -> str | None:
    normalized = re.sub(r"\s+", " ", str(label or "").strip().lower())
    for mistaken, corrected in {
        "cateway": "gateway",
        "gloucifront": "cloudfront",
        "cloudvatch": "cloudwatch",
        "aulo scaling": "auto scaling",
    }.items():
        normalized = normalized.replace(mistaken, corrected)
    if len(normalized) < 3:
        return None
    matches = [
        component_type
        for component_type, patterns in OCR_PROPOSAL_PATTERNS.items()
        if any(re.search(pattern, normalized) for pattern in patterns)
    ]
    if len(matches) == 1:
        return matches[0]
    if "waf" in matches and re.search(r"\b(?:waf|firewall|cloud armor)\b", normalized):
        return "waf"
    return None


def _stacked_ocr_phrases(lines: list[dict]) -> list[dict]:
    """Recompose short service labels split into two or three vertical OCR lines."""
    eligible = [line for line in lines if float(line.get("confidence", 0)) >= 0.55]
    phrases = []
    for first in eligible:
        chain = [first]
        for candidate in eligible:
            previous = chain[-1]
            if candidate is first or candidate in chain:
                continue
            px1, py1, px2, py2 = previous["bbox"]
            cx1, cy1, cx2, cy2 = candidate["bbox"]
            previous_height = max(1.0, py2 - py1)
            candidate_height = max(1.0, cy2 - cy1)
            vertical_gap = cy1 - py2
            center_distance = abs((cx1 + cx2) / 2 - (px1 + px2) / 2)
            alignment_limit = max(px2 - px1, cx2 - cx1) * 0.65 + 8
            if -2 <= vertical_gap <= max(8, (previous_height + candidate_height) * 0.8) and center_distance <= alignment_limit:
                chain.append(candidate)
                if len(chain) == 3:
                    break
        if len(chain) < 2:
            continue
        merged_text = " ".join(str(item.get("text") or "") for item in chain)
        if _semantic_type_from_label(merged_text) is None:
            continue
        phrases.append({
            "text": merged_text[:96],
            "confidence": round(sum(float(item["confidence"]) for item in chain) / len(chain), 3),
            "bbox": [
                min(item["bbox"][0] for item in chain),
                min(item["bbox"][1] for item in chain),
                max(item["bbox"][2] for item in chain),
                max(item["bbox"][3] for item in chain),
            ],
            "engine": "tesseract_stacked_lines",
            "semanticStackDepth": len(chain),
        })
    unique = {}
    for phrase in phrases:
        key = (phrase["text"].lower(), tuple(round(value) for value in phrase["bbox"]))
        unique[key] = phrase
    return list(unique.values())


def _infer_diagram_provider(lines: list[dict]) -> str:
    providers = Counter(
        provider
        for line in lines
        if (provider := _infer_provider("", str(line.get("text") or ""))) != "generic"
    )
    if not providers:
        return "generic"
    ranked = providers.most_common(2)
    return ranked[0][0] if len(ranked) == 1 or ranked[0][1] > ranked[1][1] else "generic"


def _proposal_bbox_from_label(
    line_bbox: list[float],
    image_size: tuple[int, int],
    placement: str = "label_below_icon",
) -> list[int]:
    """Estimate a component box from explicit label geometry and provider style."""
    width, height = image_size
    x1, y1, x2, y2 = line_bbox
    line_width = max(1.0, x2 - x1)
    line_height = max(1.0, y2 - y1)
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    if placement == "inline_card":
        box_width = min(width * 0.20, max(width * 0.10, line_width + width * 0.04))
        box_height = min(height * 0.15, max(height * 0.11, line_height * 2.8 + height * 0.045))
        top = center_y - box_height * 0.70
        bottom = center_y + box_height * 0.30
    else:
        box_width = min(width * 0.14, max(width * 0.085, line_width * 0.75 + width * 0.025))
        box_height = min(height * 0.12, max(height * 0.075, line_height * 2.4 + height * 0.025))
        bottom = y1 + line_height * 0.35
        top = bottom - box_height
    return [
        max(0, round(center_x - box_width / 2)),
        max(0, round(top)),
        min(width, round(center_x + box_width / 2)),
        min(height, round(bottom)),
    ]


def _extract_colored_anchors(image_path: str) -> list[list[int]]:
    """Find compact colored regions that usually correspond to cloud service icons."""
    try:
        import cv2
        import numpy as np

        image = cv2.imread(image_path)
        if image is None:
            return []
        height, width = image.shape[:2]
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = ((hsv[:, :, 1] >= 42) & (hsv[:, :, 2] >= 45)).astype(np.uint8) * 255
        kernel_size = max(3, min(15, round(min(width, height) * 0.009)))
        if kernel_size % 2 == 0:
            kernel_size += 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.dilate(mask, kernel, iterations=1)
        count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        image_area = width * height
        minimum_pixels = max(18, round(image_area * 0.000008))
        anchors = []
        for index in range(1, count):
            x, y, box_width, box_height, pixels = (int(value) for value in stats[index])
            box_area = box_width * box_height
            if pixels < minimum_pixels or box_width < 7 or box_height < 7:
                continue
            if box_area > image_area * 0.09 or box_width > width * 0.38 or box_height > height * 0.38:
                continue
            anchors.append([x, y, x + box_width, y + box_height])
        return anchors
    except Exception as exc:
        logger.debug("[detector] Visual anchor extraction failed: %s", exc)
        return []


def _proposal_bbox_from_visual_anchor(
    line_bbox: list[float],
    anchors: list[list[int]],
    image_size: tuple[int, int],
    exclude_text_like: bool = False,
) -> tuple[list[int] | None, str | None]:
    """Associate a semantic OCR label with the nearest colored icon above, below, or inline."""
    width, height = image_size
    x1, y1, x2, y2 = line_bbox
    line_width = max(1.0, x2 - x1)
    line_height = max(1.0, y2 - y1)
    line_center_x = (x1 + x2) / 2
    horizontal_limit = max(width * 0.075, line_width * 1.15)
    vertical_limit = max(height * 0.17, line_height * 10)
    candidates = []
    for anchor in anchors:
        ax1, ay1, ax2, ay2 = anchor
        anchor_center_x = (ax1 + ax2) / 2
        horizontal_distance = abs(anchor_center_x - line_center_x)
        if horizontal_distance > horizontal_limit:
            continue
        vertical_gap = max(0.0, max(ay1 - y2, y1 - ay2))
        if vertical_gap > vertical_limit:
            continue
        anchor_height = max(1.0, ay2 - ay1)
        if exclude_text_like and vertical_gap <= line_height * 1.2 and anchor_height <= line_height * 2.0:
            continue
        anchor_area = max(1, (ax2 - ax1) * (ay2 - ay1))
        closeness = horizontal_distance / horizontal_limit + vertical_gap / vertical_limit
        size_bonus = min(0.22, math.log1p(anchor_area) / 55)
        candidates.append((closeness - size_bonus, -anchor_area, anchor))
    if not candidates:
        return None, None
    _, _, anchor = min(candidates)
    ax1, ay1, ax2, ay2 = anchor
    anchor_width = max(1.0, ax2 - ax1)
    anchor_height = max(1.0, ay2 - ay1)
    anchor_center_x = (ax1 + ax2) / 2
    label_left = max(x1, anchor_center_x - anchor_width)
    label_right = min(x2, anchor_center_x + anchor_width)
    pad_x = max(2, round(anchor_width * 0.06))
    pad_y = max(2, round(anchor_height * 0.06))
    bbox = [
        max(0, round(min(ax1, label_left) - pad_x)),
        max(0, round(min(ay1, y1) - pad_y)),
        min(width, round(max(ax2, label_right) + pad_x)),
        min(height, round(max(ay2, y2) + pad_y)),
    ]
    if ay2 <= y1:
        relation = "visual_anchor_above_label"
    elif ay1 >= y2:
        relation = "visual_anchor_below_label"
    else:
        relation = "visual_anchor_inline_label"
    return bbox, relation


def _cluster_repeated_ocr_proposals(
    proposals: list[dict],
    image_size: tuple[int, int],
) -> list[dict]:
    """Represent adjacent replicas with the same label as one auditable deployment group."""
    _, image_height = image_size
    grouped_ids: set[str] = set()
    merged: list[dict] = []
    buckets: dict[tuple[str, str], list[dict]] = {}
    for proposal in proposals:
        normalized_label = " ".join(
            re.findall(r"[a-z0-9]+", str(proposal.get("ocrLabel") or "").lower())
        )
        if not normalized_label:
            continue
        buckets.setdefault((str(proposal.get("type") or ""), normalized_label), []).append(proposal)

    for bucket in buckets.values():
        if len(bucket) < 2:
            continue
        ordered = sorted(bucket, key=lambda item: ((item["bbox"][1] + item["bbox"][3]) / 2, item["bbox"][0]))
        rows: list[list[dict]] = []
        for proposal in ordered:
            bbox = proposal["bbox"]
            center_y = (bbox[1] + bbox[3]) / 2
            box_height = max(1, bbox[3] - bbox[1])
            target = None
            for row in rows:
                row_center = sum((item["bbox"][1] + item["bbox"][3]) / 2 for item in row) / len(row)
                row_height = sum(item["bbox"][3] - item["bbox"][1] for item in row) / len(row)
                if abs(center_y - row_center) <= max(image_height * 0.025, (box_height + row_height) * 0.22):
                    target = row
                    break
            if target is None:
                rows.append([proposal])
            else:
                target.append(proposal)

        for row in rows:
            row = sorted(row, key=lambda item: item["bbox"][0])
            cluster = [row[0]]
            clusters = []
            for proposal in row[1:]:
                previous = cluster[-1]["bbox"]
                current = proposal["bbox"]
                average_width = ((previous[2] - previous[0]) + (current[2] - current[0])) / 2
                gap = current[0] - previous[2]
                if gap <= max(12, average_width * 0.55):
                    cluster.append(proposal)
                else:
                    clusters.append(cluster)
                    cluster = [proposal]
            clusters.append(cluster)
            for cluster in clusters:
                if len(cluster) < 2:
                    continue
                source_ids = [item["id"] for item in cluster]
                first = cluster[0]
                grouped_ids.update(source_ids)
                merged.append({
                    **first,
                    "name": f"{first['name']} group ({len(cluster)})"[:64],
                    "bbox": [
                        min(item["bbox"][0] for item in cluster),
                        min(item["bbox"][1] for item in cluster),
                        max(item["bbox"][2] for item in cluster),
                        max(item["bbox"][3] for item in cluster),
                    ],
                    "confidence": round(sum(float(item["confidence"]) for item in cluster) / len(cluster), 3),
                    "metadata": {
                        **(first.get("metadata") or {}),
                        "localizationMethod": "repeated_replica_group",
                        "instanceCount": len(cluster),
                        "groupedProposalIds": source_ids,
                    },
                })
    return [proposal for proposal in proposals if proposal["id"] not in grouped_ids] + merged


def _ocr_component_proposals(
    lines: list[dict],
    image_size: tuple[int, int],
    existing: list[dict] | None = None,
    visual_anchors: list[list[int]] | None = None,
) -> list[dict]:
    """Create review-only component proposals from explicit service labels."""
    width, height = image_size
    existing = existing or []
    counts = Counter(component["type"] for component in existing)
    stacked_lines = _stacked_ocr_phrases(lines)
    semantic_lines = sorted(
        [*stacked_lines, *lines],
        key=lambda line: int(line.get("semanticStackDepth", 1)),
        reverse=True,
    )
    diagram_provider = _infer_diagram_provider(semantic_lines)
    proposals = []
    for line in semantic_lines:
        if float(line.get("confidence", 0)) < 0.55:
            continue
        component_type = _semantic_type_from_label(str(line.get("text") or ""))
        if not component_type:
            continue
        text = str(line["text"])[:64]
        provider = _infer_provider(component_type, text)
        if provider == "generic":
            provider = diagram_provider
        placement = "inline_card" if diagram_provider == "gcp" else "label_below_icon"
        bbox = None
        localization_method = None
        use_visual_anchor = False
        if diagram_provider == "azure" and visual_anchors:
            candidate_bbox, candidate_method = _proposal_bbox_from_visual_anchor(
                line["bbox"],
                visual_anchors,
                image_size,
                exclude_text_like=min(width, height) < 800,
            )
            use_visual_anchor = bool(candidate_bbox) and (
                min(width, height) >= 800 or candidate_method == "visual_anchor_below_label"
            )
            if use_visual_anchor:
                bbox, localization_method = candidate_bbox, candidate_method
        if bbox is None:
            bbox = _proposal_bbox_from_label(line["bbox"], image_size, placement)
            localization_method = placement
        proposal_center = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
        duplicate = False
        for component in [*existing, *proposals]:
            current = component.get("bbox")
            if not current:
                continue
            current_center = ((current[0] + current[2]) / 2, (current[1] + current[3]) / 2)
            if abs(current_center[0] - proposal_center[0]) <= width * 0.055 and abs(current_center[1] - proposal_center[1]) <= height * 0.055:
                duplicate = True
                break
        if duplicate:
            continue
        counts[component_type] += 1
        proposals.append({
            "id": f"{component_type}_ocr_{counts[component_type]}",
            "name": text,
            "type": component_type,
            "provider": provider,
            "confidence": round(min(0.68, 0.45 + float(line["confidence"]) * 0.22), 3),
            "bbox": bbox,
            "ocrLabel": text,
            "ocrEvidence": {**line, "accepted": True, "relation": "semantic_component_proposal"},
            "reviewStatus": "pending",
            "metadata": {
                "detectionSource": "semantic_ocr_proposal",
                "localizationMethod": localization_method,
                "visualAnchorPolicy": "adaptive_azure" if use_visual_anchor else "disabled",
                "reviewStatus": "pending",
            },
        })
    return _cluster_repeated_ocr_proposals(proposals, image_size)


def _infer_flows(components: list[dict]) -> list[dict]:
    """Last-resort layout heuristic used when no visual line is associated."""
    if len(components) < 2:
        return []

    ordered = sorted(
        components,
        key=lambda item: ((item.get("bbox") or [0, 0, 0, 0])[0] + (item.get("bbox") or [0, 0, 0, 0])[2]) / 2,
    )

    flows: list[dict] = []
    for index in range(len(ordered) - 1):
        source = ordered[index]
        target = ordered[index + 1]
        source_type = str(source.get("type") or "")
        target_type = str(target.get("type") or "")
        trust_boundary = source_type in EXTERNAL_NODE_TYPES and target_type not in EXTERNAL_NODE_TYPES

        flows.append(
            {
                "id": f"f{index + 1}",
                "from": source["id"],
                "to": target["id"],
                "protocol": "unknown",
                "trustBoundary": trust_boundary,
                "crossedBoundaryIds": [],
                "confidence": 0.40,
                "inferred": True,
                "reviewStatus": "pending",
                "evidence": "layout_adjacency",
                "directionEvidence": "left_to_right",
            }
        )

    return flows


def detect(image_path: str) -> dict | None:
    """Detecta componentes numa imagem e retorna JSON de arquitetura.

    Retorna None somente se o modelo estiver indisponível ou não encontrar
    componentes acima do piso mínimo. Detecções incertas seguem para revisão.
    """
    _load_model()
    if _model is None:
        return None

    from PIL import Image

    try:
        results = _model(image_path, verbose=False, conf=YOLO_MIN_DETECTION_CONFIDENCE)
    except Exception as exc:
        print(f"[detector] Inference error: {exc}")
        return None

    img = Image.open(image_path)
    img_w, img_h = img.size
    image_area = img_w * img_h

    components = []
    type_counts: dict[str, int] = {}
    try:
        from backend.ocr import extract_text_lines, match_component_label

        ocr_lines = extract_text_lines(image_path)
    except Exception as exc:
        logger.debug("[detector] OCR extraction failed: %s", exc)
        ocr_lines = []

    detected_boxes = results[0].boxes if results and results[0].boxes is not None else []
    for box in detected_boxes:
        conf = float(box.conf[0])
        cls_idx = int(box.cls[0])
        cls_name = _model.names[cls_idx]

        x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
        bbox_area = max(1, (x2 - x1) * (y2 - y1))
        area_ratio = bbox_area / image_area if image_area else 0.0
        dynamic_threshold = _calculate_confidence_threshold(bbox_area, image_area)
        if conf < max(YOLO_MIN_DETECTION_CONFIDENCE, dynamic_threshold):
            continue

        type_counts[cls_name] = type_counts.get(cls_name, 0) + 1
        count = type_counts[cls_name]
        comp_id = f"{cls_name}_{count}"

        ocr_evidence = match_component_label(ocr_lines, [x1, y1, x2, y2])
        if ocr_evidence:
            compatible = _ocr_label_is_compatible(cls_name, str(ocr_evidence.get("text") or ""))
            ocr_evidence = {
                **ocr_evidence,
                "accepted": compatible,
                "rejectionReason": None if compatible else "label_conflicts_with_supervised_class",
            }
        ocr_label = (
            str(ocr_evidence.get("text") or "")
            if ocr_evidence and ocr_evidence.get("accepted")
            else ""
        )
        display_name = cls_name.replace("_", " ").title()
        if ocr_label:
            display_name = ocr_label[:64]

        calibrated_confidence = _calibrate_confidence(conf, area_ratio)
        acceptance_threshold = _automatic_acceptance_threshold()
        components.append({
            "id": comp_id,
            "name": display_name,
            "type": cls_name,
            "provider": _infer_provider(cls_name, ocr_label),
            "confidence": calibrated_confidence,
            "rawConfidence": round(conf, 3),
            "bbox": [x1, y1, x2, y2],
            "ocrLabel": ocr_label or None,
            "ocrEvidence": ocr_evidence,
            "reviewStatus": "auto_accepted" if calibrated_confidence >= acceptance_threshold else "pending",
            "metadata": {
                "ocrLabel": ocr_label or None,
                "ocrEvidence": ocr_evidence,
                "reviewStatus": "auto_accepted" if calibrated_confidence >= acceptance_threshold else "pending",
                "detectionSource": "supervised_yolo",
                "rawConfidence": round(conf, 3),
                "confidenceCalibration": "platt_logistic_with_area" if _load_confidence_calibration() else "identity",
            },
        })

    visual_anchors = _extract_colored_anchors(image_path)
    ocr_proposals = _ocr_component_proposals(
        ocr_lines,
        (img_w, img_h),
        components,
        visual_anchors=visual_anchors,
    )
    components.extend(ocr_proposals)

    if not components:
        return None

    avg_confidence = sum(c["confidence"] for c in components) / len(components)
    try:
        from backend.diagram_structure import extract_structure

        structure = extract_structure(image_path, components)
    except Exception as exc:
        logger.warning("[detector] Structure extraction failed: %s", exc)
        structure = {"flows": [], "trustBoundaries": [], "diagnostics": {"error": str(exc)}}

    flows = structure.get("flows") or _infer_flows(components)
    try:
        from backend.ocr import apply_protocol_evidence

        apply_protocol_evidence(flows, components, ocr_lines)
    except Exception as exc:
        logger.debug("[detector] Protocol OCR association failed: %s", exc)
    trust_boundaries = structure.get("trustBoundaries") or []
    if any(flow.get("trustBoundary") for flow in flows) and not trust_boundaries:
        internal_ids = [
            component["id"]
            for component in components
            if str(component.get("type")) not in EXTERNAL_NODE_TYPES
        ]
        trust_boundaries = [
            {
                "id": "tb-external",
                "name": "External to internal boundary",
                "componentIds": internal_ids,
                "confidence": 0.70,
                "inferred": True,
                "reviewStatus": "pending",
                "evidence": "external_internal_semantics",
            }
        ]
    review_items = [
        {
            "kind": "component",
            "id": component["id"],
            "reason": (
                "Component was proposed from an explicit OCR service label and requires visual confirmation."
                if (component.get("metadata") or {}).get("detectionSource") == "semantic_ocr_proposal"
                else "Detection confidence is below the automatic acceptance threshold."
            ),
        }
        for component in components
        if component["reviewStatus"] == "pending"
    ]
    review_items.extend(
        {
            "kind": "flow",
            "id": flow["id"],
            "reason": (
                "A visual line was associated with both components; direction and protocol must be confirmed."
                if flow.get("evidence") == "detected_line"
                else "Flow was inferred from diagram layout and must be confirmed."
            ),
        }
        for flow in flows
    )
    review_items.extend(
        {
            "kind": "ocr_label",
            "id": component["id"],
            "reason": (
                f"OCR text '{component['ocrEvidence']['text']}' conflicts with the supervised "
                f"class '{component['type']}' and was not applied."
            ),
        }
        for component in components
        if component.get("ocrEvidence") and not component["ocrEvidence"].get("accepted")
    )

    return {
        "name": "Detected architecture",
        "components": components,
        "flows": flows,
        "trustBoundaries": trust_boundaries,
        "detectedBy": "yolo",
        "detectorModel": str(YOLO_MODEL_PATH),
        "avgDetectionConfidence": round(avg_confidence, 3),
        "reviewRequired": bool(review_items),
        "reviewedByHuman": False,
        "reviewItems": review_items,
        "detectorMetadata": status(),
        "structureMetadata": structure.get("diagnostics") or {},
        "ocrMetadata": {
            "textRegions": len(ocr_lines),
            "matchedComponents": sum(
                bool((component.get("ocrEvidence") or {}).get("accepted")) for component in components
            ),
            "rejectedComponentLabels": sum(
                bool(component.get("ocrEvidence"))
                and not bool((component.get("ocrEvidence") or {}).get("accepted"))
                for component in components
            ),
            "matchedProtocols": sum(bool(flow.get("protocolEvidence")) for flow in flows),
        },
    }
