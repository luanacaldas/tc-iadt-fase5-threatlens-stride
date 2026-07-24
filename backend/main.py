"""ThreatLens AI — FastAPI backend.

Pipeline: imagem → YOLO (ou Gemini Vision) → STRIDE engine → RAG → Gemini report → Groq validator
"""

from __future__ import annotations

import tempfile
import hashlib
import json
import math
import re
import time
import uuid
from copy import deepcopy
from contextvars import ContextVar
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from backend import rag as rag_module
from backend.config import (
    APP_VERSION,
    BACKEND_PORT,
    CORS_ALLOWED_ORIGINS,
    ENABLE_GENERATIVE_REPORTS,
    ENABLE_REMOTE_VALIDATION,
    ENABLE_VISION_FALLBACK,
    FLOW_STRATEGY,
    GEMINI_API_KEY,
    GROQ_API_KEY,
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_SIZE,
    MAX_COMPONENTS,
    MAX_FIELD_LENGTH,
    MAX_FLOWS,
    MAX_JSON_SIZE,
    MAX_REPORT_THREATS,
    MAX_TRUST_BOUNDARIES,
)
from backend.flow_strategy import (
    DEFAULT_FLOW_STRATEGY,
    SUPPORTED_FLOW_STRATEGIES,
    apply_flow_strategy,
    resolve_flow_strategy,
)
from backend.analysis_quality import assess_analysis_quality
from backend.stride_engine import analyze_architecture, ensure_detection_alternatives_in_report
from backend.pdf_report import generate_pdf
from backend.review_submission import ReviewSubmissionError, store_review_submission


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[main] Initializing RAG knowledge base ...")
    try:
        rag_module.initialize_rag()
    except Exception as exc:
        print(f"[main] RAG initialization warning: {exc} — continuing without RAG.")
    yield
    print("[main] Shutting down.")


app = FastAPI(
    title="ThreatLens AI",
    description="STRIDE threat modeling from architecture diagrams using supervised AI + RAG + LLM.",
    version=APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
ALLOWED_IMAGE_FORMATS = {"PNG", "JPEG", "WEBP"}
ALLOWED_COMPONENT_TYPES = {
    "user", "internet", "identity_provider", "waf", "cdn", "api_gateway",
    "load_balancer", "compute", "database", "storage", "queue", "monitoring",
    "backup", "secrets_kms",
}
REQUEST_ID: ContextVar[str | None] = ContextVar("threatlens_request_id", default=None)


@app.middleware("http")
async def audit_request(request: Request, call_next):
    supplied_id = request.headers.get("x-request-id", "")
    request_id = supplied_id if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", supplied_id) else uuid.uuid4().hex
    token = REQUEST_ID.set(request_id)
    started = time.perf_counter()
    status_code = 500
    try:
        if request.url.path in {"/analyze/json", "/report/pdf", "/reviews/tl004"}:
            content_length = request.headers.get("content-length")
            try:
                oversized = content_length is not None and int(content_length) > MAX_JSON_SIZE
            except ValueError:
                oversized = True
            if oversized:
                status_code = 413
                response = JSONResponse(
                    status_code=413,
                    content={"detail": f"JSON body too large (max {MAX_JSON_SIZE // (1024 * 1024)}MB)"},
                )
                response.headers["X-Request-ID"] = request_id
                return response
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        print(
            f"[audit] request_id={request_id} method={request.method} path={request.url.path} "
            f"status={status_code} duration_ms={duration_ms}"
        )
        REQUEST_ID.reset(token)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    selected_strategy = resolve_flow_strategy(FLOW_STRATEGY)
    return {
        "status": "ok",
        "version": APP_VERSION,
        "flowStrategy": selected_strategy,
        "flowStrategies": {
            "selected": selected_strategy,
            "default": DEFAULT_FLOW_STRATEGY,
            "available": list(SUPPORTED_FLOW_STRATEGIES),
        },
        "reportMode": "gemini" if ENABLE_GENERATIVE_REPORTS and GEMINI_API_KEY else "deterministic",
        "validatorMode": "groq" if ENABLE_REMOTE_VALIDATION and GROQ_API_KEY else "deterministic",
        "visionFallbackEnabled": ENABLE_VISION_FALLBACK and bool(GEMINI_API_KEY),
    }


def _readiness_summary(detector_info: dict, rag_info: dict) -> dict:
    reasons = []
    if not detector_info.get("available"):
        reasons.append("supervised_detector_unavailable")
    if not (detector_info.get("confidenceCalibration") or {}).get("available"):
        reasons.append("confidence_calibration_unavailable")
    if not rag_info.get("ready") or int(rag_info.get("chunks") or 0) <= 0:
        reasons.append("rag_unavailable")
    return {"ready": not reasons, "reasons": reasons}


@app.get("/ready")
def ready():
    from backend import detector
    readiness = _readiness_summary(detector.status(), rag_module.status())
    payload = {"status": "ready" if readiness["ready"] else "degraded", **readiness}
    return JSONResponse(status_code=200 if readiness["ready"] else 503, content=payload)


def _rag_count() -> int:
    try:
        return rag_module._get_collection().count()
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Analyze from JSON
# ---------------------------------------------------------------------------

@app.post("/analyze/json")
async def analyze_json(body: dict[str, Any]):
    """Recebe um JSON de arquitetura e retorna análise STRIDE completa."""
    _validate_architecture_payload(body)

    body = _apply_configured_flow_strategy(body)
    body = _reconcile_trust_boundary_crossings(body)
    body, analysis_quality = assess_analysis_quality(body)
    if analysis_quality["status"] == "rejected":
        return _build_quality_rejection_response(body, analysis_quality, body.get("detectedBy") or "json_input")
    analysis = analyze_architecture(body)
    rag_context = _query_rag(analysis)
    report, validation = await _generate_and_validate(analysis, rag_context)

    detector_used = body.get("detectedBy") or "json_input"
    return _build_response(
        analysis,
        rag_context,
        report,
        validation,
        detector_used=detector_used,
        analysis_quality=analysis_quality,
    )


@app.post("/report/pdf")
async def report_pdf(body: dict[str, Any]):
    """Render a completed analysis into an offline, deterministic PDF."""
    if not isinstance(body.get("architecture"), dict) or not isinstance(body.get("threats"), list):
        raise HTTPException(status_code=422, detail="A completed ThreatLens analysis is required.")
    if body.get("reportSuppressed") or (body.get("analysisQuality") or {}).get("status") == "rejected":
        raise HTTPException(
            status_code=422,
            detail="The report was suppressed by the structural analysis quality gate.",
        )
    _validate_architecture_payload(body["architecture"])
    if len(body["threats"]) > MAX_REPORT_THREATS:
        raise HTTPException(status_code=422, detail=f"At most {MAX_REPORT_THREATS} threats can be exported.")
    for threat in body["threats"]:
        if not isinstance(threat, dict):
            raise HTTPException(status_code=422, detail="Each report threat must be an object.")
        for field in ("title", "evidence"):
            value = threat.get(field)
            if value is not None and (not isinstance(value, str) or len(value) > MAX_FIELD_LENGTH * 4):
                raise HTTPException(status_code=422, detail=f"Threat field '{field}' is invalid or too long.")
    try:
        content = generate_pdf(body)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}") from exc
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="threatlens-stride-report.pdf"'},
    )


# ---------------------------------------------------------------------------
# Local human-review submission
# ---------------------------------------------------------------------------

@app.post("/reviews/tl004")
async def submit_tl004_review(request: Request):
    """Validate and persist a completed local TL-004 review."""
    origin = request.headers.get("origin")
    response_headers = (
        {"Access-Control-Allow-Origin": "null", "Vary": "Origin"}
        if origin == "null"
        else {}
    )
    try:
        raw = await request.body()
        if len(raw) > MAX_JSON_SIZE:
            raise ReviewSubmissionError("Review payload is too large.", 413)
        envelope = json.loads(raw.decode("utf-8"))
        result = store_review_submission(envelope)
        return JSONResponse(status_code=201, content=result, headers=response_headers)
    except UnicodeDecodeError:
        return JSONResponse(
            status_code=400,
            content={"detail": "Review payload must use UTF-8."},
            headers=response_headers,
        )
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=400,
            content={"detail": "Review payload must be valid JSON."},
            headers=response_headers,
        )
    except ReviewSubmissionError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=response_headers,
        )


# ---------------------------------------------------------------------------
# Analyze from image
# ---------------------------------------------------------------------------

@app.post("/analyze/image")
async def analyze_image_endpoint(image: UploadFile = File(...)):
    """Detecta componentes a partir de uma imagem. Retorna JSON de arquitetura (sem relatório)."""
    image_bytes = await _read_validated_image(image)

    mime_type = image.content_type or "image/png"
    arch_json = await _detect_components(image_bytes, mime_type)
    _validate_architecture_payload(arch_json)
    arch_json = _apply_configured_flow_strategy(arch_json)
    _validate_architecture_payload(arch_json)
    arch_json, analysis_quality = assess_analysis_quality(arch_json)
    arch_json["analysisQuality"] = analysis_quality
    return arch_json


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

@app.post("/analyze/full")
async def analyze_full(
    image: UploadFile | None = File(default=None),
    architecture_json: str | None = Form(default=None),
):
    """Pipeline completo: imagem → detecção → STRIDE → RAG → relatório LLM → validação."""
    arch_json: dict | None = None
    detector_used = "json_input"

    # 1. Detecta componentes da imagem, se enviada
    if image is not None:
        image_bytes = await _read_validated_image(image)

        mime_type = image.content_type or "image/png"
        try:
            arch_json = await _detect_components(image_bytes, mime_type)
            _validate_architecture_payload(arch_json)
            detector_used = arch_json.get("detectedBy", "gemini_vision")
        except Exception as exc:
            print(f"[main] Image detection failed: {exc}")
            arch_json = None

    # 2. Fallback para o JSON manual se a detecção falhou ou não veio imagem
    if arch_json is None and architecture_json:
        import json
        try:
            arch_json = json.loads(architecture_json)
            detector_used = "json_input"
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid architecture JSON: {exc}")

    if arch_json is None:
        raise HTTPException(
            status_code=422,
            detail="Provide an image and/or a valid architecture_json.",
        )

    _validate_architecture_payload(arch_json)

    # 3. Motor STRIDE
    arch_json = _apply_configured_flow_strategy(arch_json)
    _validate_architecture_payload(arch_json)
    arch_json = _reconcile_trust_boundary_crossings(arch_json)
    arch_json, analysis_quality = assess_analysis_quality(arch_json)
    if analysis_quality["status"] == "rejected":
        return _build_quality_rejection_response(arch_json, analysis_quality, detector_used)
    analysis = analyze_architecture(arch_json)

    # 4. RAG
    rag_context = _query_rag(analysis)

    # 5. Relatório LLM + validação
    report, validation = await _generate_and_validate(analysis, rag_context)

    return _build_response(
        analysis,
        rag_context,
        report,
        validation,
        detector_used=detector_used,
        analysis_quality=analysis_quality,
    )


# ---------------------------------------------------------------------------
# RAG query (debug/test)
# ---------------------------------------------------------------------------

@app.get("/rag/query")
def rag_query(components: str = "", stride: str = ""):
    """Consulta a RAG com tipos de componentes e categorias STRIDE (separados por vírgula)."""
    component_list = [c.strip() for c in components.split(",") if c.strip()]
    stride_list = [s.strip() for s in stride.split(",") if s.strip()]
    results = rag_module.query(component_list, stride_list)
    return {"results": results, "count": len(results)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _apply_configured_flow_strategy(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return apply_flow_strategy(payload, FLOW_STRATEGY)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def _detect_components(image_bytes: bytes, mime_type: str) -> dict:
    """Tenta YOLO; se indisponível ou baixa confiança, usa Gemini Vision."""
    from backend import detector

    if detector.is_available():
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name
        try:
            result = detector.detect(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        if result is not None:
            return result

    # Fallback: Gemini Vision
    from backend.vision_llm import analyze_image
    try:
        if not ENABLE_VISION_FALLBACK:
            raise RuntimeError("Vision fallback is disabled")
        result = analyze_image(image_bytes, mime_type)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "No supervised detector is available and the vision fallback is not configured. "
                "Set YOLO_MODEL_PATH to trained weights or configure GEMINI_API_KEY."
            ),
        ) from exc
    for component in result.get("components", []):
        component["reviewStatus"] = "pending"
        component.setdefault("metadata", {})["detectionSource"] = "generative_fallback"
        component["metadata"]["reviewStatus"] = "pending"
    for flow in result.get("flows", []):
        flow["reviewStatus"] = "pending"
        flow.setdefault("confidence", 0.40)
        flow["inferred"] = True
    result["reviewRequired"] = True
    result["reviewedByHuman"] = False
    result["reviewItems"] = [
        {
            "kind": "component",
            "id": component.get("id"),
            "reason": "Component came from the generative fallback and must be confirmed.",
        }
        for component in result.get("components", [])
    ]
    return result


def _validate_architecture_payload(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Architecture payload must be a JSON object.")

    components = payload.get("components")
    detection_alternatives = payload.get("detectionAlternatives", [])
    flows = payload.get("flows", [])
    trust_boundaries = payload.get("trustBoundaries", [])
    if not isinstance(components, list) or not components:
        raise HTTPException(status_code=422, detail="'components' array is required.")
    if not isinstance(flows, list):
        raise HTTPException(status_code=422, detail="'flows' must be an array.")
    if not isinstance(detection_alternatives, list):
        raise HTTPException(status_code=422, detail="'detectionAlternatives' must be an array.")
    if not isinstance(trust_boundaries, list):
        raise HTTPException(status_code=422, detail="'trustBoundaries' must be an array.")
    if len(components) > MAX_COMPONENTS:
        raise HTTPException(status_code=422, detail=f"At most {MAX_COMPONENTS} components are supported.")
    if len(detection_alternatives) > MAX_COMPONENTS:
        raise HTTPException(status_code=422, detail=f"At most {MAX_COMPONENTS} detection alternatives are supported.")
    if len(flows) > MAX_FLOWS:
        raise HTTPException(status_code=422, detail=f"At most {MAX_FLOWS} flows are supported.")
    if len(trust_boundaries) > MAX_TRUST_BOUNDARIES:
        raise HTTPException(status_code=422, detail=f"At most {MAX_TRUST_BOUNDARIES} trust boundaries are supported.")
    _validate_text_field(payload.get("name"), "Architecture name", required=False)

    for component in components:
        if not isinstance(component, dict):
            raise HTTPException(status_code=422, detail="Each component must be an object.")
        for field in ("id", "name", "type"):
            _validate_text_field(component.get(field), f"Component field '{field}'")
        if component["type"] not in ALLOWED_COMPONENT_TYPES:
            raise HTTPException(status_code=422, detail=f"Unsupported component type: {component['type']}")
        provider = component.get("provider", "generic")
        if provider not in {"generic", "aws", "azure", "gcp"}:
            raise HTTPException(status_code=422, detail=f"Unsupported provider: {provider}")

        _validate_confidence(component.get("confidence", 0.75), "Component confidence")
        if component.get("rawConfidence") is not None:
            _validate_confidence(component["rawConfidence"], "Component rawConfidence")
        bbox = component.get("bbox")
        if bbox is not None:
            _validate_bbox(bbox, "Component bbox")

    component_ids = {component["id"] for component in components}
    if len(component_ids) != len(components):
        raise HTTPException(status_code=422, detail="Component ids must be unique.")
    alternative_ids: set[str] = set()
    for alternative in detection_alternatives:
        if not isinstance(alternative, dict):
            raise HTTPException(status_code=422, detail="Each detection alternative must be an object.")
        for field in ("id", "name", "type", "provider"):
            _validate_text_field(alternative.get(field), f"Detection alternative field '{field}'")
        if alternative["type"] not in ALLOWED_COMPONENT_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported detection alternative type: {alternative['type']}",
            )
        if alternative["provider"] not in {"generic", "aws", "azure", "gcp"}:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported detection alternative provider: {alternative['provider']}",
            )
        _validate_confidence(alternative.get("confidence"), "Detection alternative confidence")
        if alternative.get("rawConfidence") is not None:
            _validate_confidence(alternative["rawConfidence"], "Detection alternative rawConfidence")
        _validate_bbox(alternative.get("bbox"), "Detection alternative bbox")
        metadata = alternative.get("metadata")
        if not isinstance(metadata, dict):
            raise HTTPException(status_code=422, detail="Detection alternative metadata must be an object.")
        _validate_text_field(metadata.get("supersededBy"), "Detection alternative metadata.supersededBy")
        _validate_text_field(
            metadata.get("supersededReason"),
            "Detection alternative metadata.supersededReason",
            required=False,
        )
        _validate_text_field(alternative.get("reviewStatus"), "Detection alternative reviewStatus", required=False)
        if alternative.get("ocrLabel") is not None:
            _validate_text_field(alternative["ocrLabel"], "Detection alternative ocrLabel")
        if alternative.get("ocrEvidence") is not None and not isinstance(alternative["ocrEvidence"], dict):
            raise HTTPException(status_code=422, detail="Detection alternative ocrEvidence must be an object.")
        alternative_id = alternative["id"]
        if alternative_id in alternative_ids:
            raise HTTPException(status_code=422, detail="Detection alternative ids must be unique.")
        if alternative_id in component_ids:
            raise HTTPException(
                status_code=422,
                detail="Detection alternative ids must not conflict with active component ids.",
            )
        if metadata["supersededBy"] not in component_ids:
            raise HTTPException(
                status_code=422,
                detail="Detection alternative supersededBy must reference an active component id.",
            )
        alternative_ids.add(alternative_id)
    flow_ids: set[str] = set()
    for flow in flows:
        if not isinstance(flow, dict):
            raise HTTPException(status_code=422, detail="Each flow must be an object.")
        _validate_text_field(flow.get("from"), "Flow field 'from'")
        _validate_text_field(flow.get("to"), "Flow field 'to'")
        if flow["from"] not in component_ids or flow["to"] not in component_ids:
            raise HTTPException(status_code=422, detail="Flow endpoints must reference detected component ids.")
        if flow["from"] == flow["to"]:
            raise HTTPException(status_code=422, detail="A flow cannot connect a component to itself.")
        _validate_confidence(flow.get("confidence", 0.5), "Flow confidence")
        _validate_text_field(flow.get("protocol", "unknown"), "Flow protocol")
        if flow.get("id"):
            _validate_text_field(flow["id"], "Flow id")
            if flow["id"] in flow_ids:
                raise HTTPException(status_code=422, detail="Flow ids must be unique.")
            flow_ids.add(flow["id"])

    boundary_ids: set[str] = set()
    for boundary in trust_boundaries:
        if not isinstance(boundary, dict):
            raise HTTPException(status_code=422, detail="Each trust boundary must be an object.")
        if not boundary.get("id") and not boundary.get("name"):
            raise HTTPException(status_code=422, detail="Each trust boundary requires an id or name.")
        if boundary.get("id"):
            _validate_text_field(boundary["id"], "Trust boundary id")
            if boundary["id"] in boundary_ids:
                raise HTTPException(status_code=422, detail="Trust boundary ids must be unique.")
            boundary_ids.add(boundary["id"])
        if boundary.get("name") is not None:
            _validate_text_field(boundary["name"], "Trust boundary name")
        members = boundary.get("componentIds", [])
        if not isinstance(members, list) or any(member not in component_ids for member in members):
            raise HTTPException(
                status_code=422,
                detail="Trust boundary componentIds must reference detected component ids.",
            )
        bbox = boundary.get("bbox")
        if bbox is not None:
            _validate_bbox(bbox, "Trust boundary bbox")


def _validate_text_field(value: Any, label: str, required: bool = True) -> None:
    if value is None and not required:
        return
    if not isinstance(value, str) or (required and not value.strip()):
        raise HTTPException(status_code=422, detail=f"{label} must be a non-empty string.")
    if len(value) > MAX_FIELD_LENGTH:
        raise HTTPException(status_code=422, detail=f"{label} exceeds {MAX_FIELD_LENGTH} characters.")


def _validate_confidence(value: Any, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise HTTPException(status_code=422, detail=f"{label} must be between 0 and 1.")


def _validate_bbox(value: Any, label: str) -> None:
    if not isinstance(value, list) or len(value) != 4 or not all(
        isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item)
        for item in value
    ):
        raise HTTPException(status_code=422, detail=f"{label} must contain four finite numeric values.")
    if value[2] <= value[0] or value[3] <= value[1]:
        raise HTTPException(status_code=422, detail=f"{label} coordinates are invalid.")


async def _read_validated_image(image: UploadFile, max_size: int = MAX_IMAGE_SIZE) -> bytes:
    if image.content_type and image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported image type: {image.content_type}")

    chunks = []
    total = 0
    while True:
        chunk = await image.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_size:
            raise HTTPException(status_code=413, detail=f"Image too large (max {max_size // (1024 * 1024)}MB)")
        chunks.append(chunk)
    image_bytes = b"".join(chunks)
    if not image_bytes:
        raise HTTPException(status_code=422, detail="Image is empty.")

    signature_format = _sniff_image_format(image_bytes)
    if signature_format is None:
        raise HTTPException(status_code=415, detail="Uploaded content is not a valid supported image.")

    try:
        from PIL import Image

        with Image.open(BytesIO(image_bytes)) as decoded:
            image_format = str(decoded.format or "").upper()
            width, height = decoded.size
            decoded.verify()
        if image_format not in ALLOWED_IMAGE_FORMATS or image_format != signature_format:
            raise HTTPException(status_code=415, detail=f"Unsupported decoded image format: {image_format}")
        if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
            raise HTTPException(status_code=413, detail="Image dimensions exceed the configured pixel limit.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=415, detail="Uploaded content is not a valid supported image.") from exc
    return image_bytes


def _sniff_image_format(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if content.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "WEBP"
    return None


def _reconcile_trust_boundary_crossings(payload: dict[str, Any]) -> dict[str, Any]:
    """Make reviewed boundary membership authoritative for flow crossing flags."""
    result = deepcopy(payload)
    boundaries = [
        boundary
        for boundary in result.get("trustBoundaries", [])
        if boundary.get("componentIds")
    ]
    if not boundaries:
        return result

    for flow in result.get("flows", []):
        crossed = []
        for boundary in boundaries:
            members = set(boundary.get("componentIds") or [])
            if (flow.get("from") in members) != (flow.get("to") in members):
                crossed.append(boundary.get("id") or boundary.get("name"))
        flow["crossedBoundaryIds"] = crossed
        flow["trustBoundary"] = bool(crossed)
    return result


def _query_rag(analysis: dict) -> list[str]:
    """Consulta a RAG com os tipos de componentes e categorias STRIDE detectados."""
    try:
        component_types = list({c["type"] for c in analysis["architecture"]["components"]})
        stride_categories = [k for k, v in analysis["coverage"].items() if v > 0]
        audit_top_k = min(18, max(8, len(component_types) + len(stride_categories) * 2))
        return rag_module.query(component_types, stride_categories, top_k=audit_top_k)
    except Exception as exc:
        print(f"[main] RAG query failed: {exc}")
        return []


def _build_evidence_catalog(rag_context: list[str]) -> list[dict]:
    catalog = []
    pattern = re.compile(r"^\*\*\[([^\]]+)\]\s*(.*?)\*\*\s*\n?(.*)$", re.DOTALL)
    for raw_document in rag_context:
        match = pattern.match(str(raw_document).strip())
        if match:
            source, section, content = match.groups()
        else:
            source, section, content = "knowledge", "", str(raw_document).strip()
        evidence_id = "rag-" + hashlib.sha256(
            f"{source}\n{section}\n{content}".encode("utf-8")
        ).hexdigest()[:12]
        catalog.append(
            {
                "id": evidence_id,
                "source": source,
                "section": section,
                "excerpt": " ".join(content.split())[:240],
            }
        )
    return catalog


def _flow_support_for_rule(rule_id: str | None, architecture: dict) -> list[dict]:
    components = {component["id"]: component for component in architecture["components"]}

    def component_type(component_id: str) -> str:
        return str((components.get(component_id) or {}).get("type") or "")

    def external(component_id: str) -> bool:
        return component_type(component_id) in {"internet", "user"}

    matches = []
    for flow in architecture["flows"]:
        source_type = component_type(flow["from"])
        target_type = component_type(flow["to"])
        protocol = str(flow.get("protocol") or "unknown").lower().replace(" ", "")
        supported = {
            "insecure-protocol-crosses-trust-boundary": bool(flow.get("trustBoundary"))
            and protocol in {"http", "ftp", "telnet", "smtp", "ldap", "tcp"},
            "unknown-protocol-crosses-trust-boundary": bool(flow.get("trustBoundary"))
            and protocol == "unknown",
            "external-entry-without-waf": external(flow["from"]) or external(flow["to"]),
            "internet-to-api": source_type == "internet" and target_type == "api_gateway",
            "compute-to-database": source_type == "compute" and target_type == "database",
        }.get(rule_id, False)
        if supported:
            matches.append(flow)
    return matches


def _trace_threat(threat: dict, architecture: dict, evidence_catalog: list[dict]) -> dict:
    component_ids = []
    if threat.get("componentId") and threat["componentId"] != "architecture":
        component_ids.append(threat["componentId"])
    supporting_flows = _flow_support_for_rule(threat.get("ruleId"), architecture)
    for flow in supporting_flows:
        component_ids.extend([flow["from"], flow["to"]])

    absence_evidence = []
    if threat.get("ruleId") == "missing-monitoring":
        absence_evidence.append("No component with canonical type 'monitoring' was present.")
    elif threat.get("ruleId") == "missing-backup-for-database":
        absence_evidence.append("A database is present and no component with canonical type 'backup' was present.")
        component_ids.extend(
            component["id"] for component in architecture["components"] if component["type"] == "database"
        )

    component_type_by_id = {
        component["id"]: component["type"].replace("_", "-")
        for component in architecture["components"]
    }
    relation_tokens = {str(threat.get("stride") or "").lower().replace(" ", "-")}
    relation_tokens.update(component_type_by_id.get(component_id, "") for component_id in component_ids)
    relation_tokens.discard("")
    rag_source_ids = []
    for evidence in evidence_catalog:
        haystack = f"{evidence['source']} {evidence['section']}".lower().replace("_", "-")
        if any(token in haystack for token in relation_tokens):
            rag_source_ids.append(evidence["id"])

    boundary_ids = sorted(
        {
            boundary_id
            for flow in supporting_flows
            for boundary_id in flow.get("crossedBoundaryIds") or []
        }
    )
    return {
        "ruleId": threat.get("ruleId"),
        "ruleSource": threat.get("source"),
        "componentIds": sorted(set(component_ids)),
        "flowIds": sorted(flow["id"] for flow in supporting_flows),
        "boundaryIds": boundary_ids,
        "absenceEvidence": absence_evidence,
        "ragSourceIds": rag_source_ids[:3],
    }


async def _generate_and_validate(analysis: dict, rag_context: list[str]) -> tuple[str, dict]:
    """Gera relatório com Gemini e valida com Groq. Até 3 tentativas com backoff."""
    import asyncio
    from backend.report import generate_report
    from backend.validator import validate_report

    architecture = analysis["architecture"]
    threats = analysis["threats"]
    score = analysis["score"]
    coverage = analysis["coverage"]

    report = analysis["reportMarkdown"]  # fallback inicial
    validation: dict = {"approved": False, "score": 0.0, "issues": ["Report not generated."], "criteria": {}}

    if not ENABLE_GENERATIVE_REPORTS or not GEMINI_API_KEY:
        return report, _validate_report_locally(report, architecture, threats)

    for attempt in range(1, 4):
        if attempt > 1:
            await asyncio.sleep(2 ** (attempt - 1))  # 2s, 4s backoff

        try:
            report = generate_report(architecture, threats, rag_context, score, coverage)
        except Exception as exc:
            print(f"[main] Report generation attempt {attempt}/3 failed: {exc}")
            if attempt == 3:
                validation = {
                    "approved": False,
                    "score": 0.3,
                    "issues": [f"LLM report generation failed after 3 attempts: {exc}. Rule-engine fallback shown."],
                    "criteria": {},
                }
            continue  # tenta novamente

        if not ENABLE_REMOTE_VALIDATION or not GROQ_API_KEY:
            validation = _validate_report_locally(report, architecture, threats)
        else:
            try:
                validation = validate_report(report, architecture, threats)
            except Exception as exc:
                print(f"[main] Validation attempt {attempt}/3 failed: {exc}")
                validation = _validate_report_locally(report, architecture, threats)
                validation["issues"].append(f"Remote validation unavailable: {exc}")

        if validation.get("approved"):
            print(f"[main] Report approved on attempt {attempt}.")
            break
        print(f"[main] Report validation attempt {attempt}/3 not approved: {validation.get('issues')}")

    return report, validation


def _validate_report_locally(report: str, architecture: dict, threats: list[dict]) -> dict:
    """Deterministic grounding gate used when a remote validator is unavailable."""
    required_sections = (
        "Executive summary",
        "STRIDE coverage",
        "Components detected",
        "Data flows and trust boundaries",
        "Prioritized threats",
        "Human review checklist",
    )
    section_coverage = all(section.lower() in report.lower() for section in required_sections)
    architecture_coverage = all(
        component["name"].lower() in report.lower() or component["type"].lower() in report.lower()
        for component in architecture["components"]
    )
    countermeasure_coverage = bool(threats) and all(
        any(measure.lower() in report.lower() for measure in threat.get("countermeasures", []))
        for threat in threats[:12]
    )
    criteria = {
        "sectionCoverage": section_coverage,
        "architectureCoverage": architecture_coverage,
        "countermeasureCoverage": countermeasure_coverage,
        "hallucinationCheck": "not_applicable_to_deterministic_template",
    }
    score = round(sum(value is True for value in criteria.values()) / 3, 2)
    issues = [
        label
        for passed, label in (
            (section_coverage, "Required report sections are incomplete."),
            (architecture_coverage, "One or more detected components are missing from the report."),
            (countermeasure_coverage, "One or more prioritized threats lack grounded countermeasures."),
        )
        if not passed
    ]
    return {
        "approved": score >= 0.67,
        "score": score,
        "issues": issues,
        "criteria": criteria,
        "validator": "deterministic_grounding_gate",
    }


def _build_response(
    analysis: dict,
    rag_context: list[str],
    report: str,
    validation: dict,
    detector_used: str,
    analysis_quality: dict[str, Any] | None = None,
) -> dict:
    evidence_catalog = _build_evidence_catalog(rag_context)
    threats = [
        {**threat, "evidenceTrace": _trace_threat(threat, analysis["architecture"], evidence_catalog)}
        for threat in analysis["threats"]
    ]
    architecture = analysis["architecture"]
    analysis_quality = analysis_quality or {
        "status": "reliable",
        "score": 1.0,
        "reasons": [],
        "recommendedAction": (
            "A estrutura passou pelo gate automático; mantenha a revisão humana antes da aprovação final."
        ),
        "gateVersion": "mvp-hardening-001",
        "blockedFlowIds": [],
    }
    report = ensure_detection_alternatives_in_report(report, architecture)
    human_review_items = [
        {
            "id": component["id"],
            "kind": "component",
            "severity": "Medium",
            "title": f"Review detected component: {component['name']}",
            "confidence": component["confidence"],
            "reason": "Component was not explicitly confirmed by a human reviewer.",
        }
        for component in architecture["components"]
        if component.get("reviewStatus") not in {"confirmed", "auto_accepted"}
    ]
    human_review_items.extend([
        {
            "id": t["id"],
            "kind": "threat",
            "stride": t["stride"],
            "severity": t["severity"],
            "title": t["title"],
            "confidence": t["confidence"],
            "reason": "Low detection confidence — manual verification recommended.",
        }
        for t in threats
        if t["confidence"] < 0.70
    ])

    human_review_items.extend(
        {
            "id": flow["id"],
            "kind": "flow",
            "severity": "Medium",
            "title": "Confirm inferred data flow",
            "confidence": flow.get("confidence", 0.5),
            "reason": (
                "A line was detected between the components; confirm its direction and protocol."
                if flow.get("evidence") == "detected_line"
                else "This flow was inferred from component layout."
            ),
        }
        for flow in architecture["flows"]
        if flow.get("inferred") and flow.get("reviewStatus") != "confirmed"
    )

    human_review_items.extend(_quality_review_items(analysis_quality))

    human_review_items.extend(
        {
            "id": f"ocr-{component['id']}",
            "kind": "ocr_label",
            "severity": "Medium",
            "title": f"Resolve OCR label conflict for {component['name']}",
            "confidence": (component.get("ocrEvidence") or {}).get("confidence", 0.5),
            "reason": (
                f"OCR read '{(component.get('ocrEvidence') or {}).get('text')}', but the supervised "
                f"detector classified the component as '{component['type']}'. The OCR label was not applied."
            ),
        }
        for component in architecture["components"]
        if component.get("ocrEvidence") and not component["ocrEvidence"].get("accepted", True)
    )

    human_review_items.extend(
        {
            "id": boundary.get("id") or f"trust-boundary-{index}",
            "kind": "trust_boundary",
            "severity": "Medium",
            "title": f"Confirm trust boundary: {boundary.get('name', 'Unnamed boundary')}",
            "confidence": boundary.get("confidence", 0.5),
            "reason": "A rectangular architecture zone was detected and its membership must be confirmed.",
        }
        for index, boundary in enumerate(architecture.get("trustBoundaries") or [], start=1)
        if boundary.get("inferred") and boundary.get("reviewStatus") != "confirmed"
    )

    # Superseded alternatives remain review-only and never enter analysis inputs.
    human_review_items.extend(
        {
            "id": alternative["id"],
            "kind": "component_alternative",
            "severity": "Info",
            "title": f"Review superseded detection: {alternative['name']}",
            "confidence": alternative["confidence"],
            "reason": (
                f"This detection was superseded by "
                f"'{(alternative.get('metadata') or {}).get('supersededBy')}' and is excluded from analysis."
            ),
        }
        for alternative in architecture.get("detectionAlternatives") or []
    )

    # Adiciona itens marcados pelo validador
    if not validation.get("approved") and validation.get("issues"):
        for index, issue in enumerate(validation["issues"], start=1):
            human_review_items.append({
                "id": f"validation-issue-{index}",
                "kind": "report",
                "stride": "N/A",
                "severity": "Medium",
                "title": "Validator flagged report quality issue",
                "confidence": validation.get("score", 0.0),
                "reason": issue,
            })

    return {
        "architecture": analysis["architecture"],
        "threats": threats,
        "score": analysis["score"],
        "riskComparison": analysis.get("riskComparison"),
        "coverage": analysis["coverage"],
        "graph": analysis["graph"],
        "reportMarkdown": report,
        "reportFallback": analysis["reportMarkdown"],
        "validation": validation,
        "humanReviewItems": human_review_items,
        "evidenceCatalog": evidence_catalog,
        "analysisQuality": analysis_quality,
        "reportSuppressed": False,
        "audit": {
            "analysisId": uuid.uuid4().hex,
            "requestId": REQUEST_ID.get(),
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "pipelineVersion": app.version,
            "humanReviewed": architecture.get("reviewedByHuman", False),
            "detectorModel": architecture.get("detectorModel"),
        },
        "pipeline": {
            "detectorUsed": detector_used,
            "detectorModel": architecture.get("detectorModel"),
            "modelTrace": architecture.get("detectorMetadata") or {},
            "structureTrace": architecture.get("structureMetadata") or {},
            "ocrTrace": architecture.get("ocrMetadata") or {},
            "alternativeTrace": architecture.get("detectionAlternativeTrace") or {
                "inputCount": 0,
                "outputCount": 0,
                "alternativeLossCount": 0,
            },
            "ragDocsRetrieved": len(rag_context),
            "ragRetrievalStrategy": "architecture-and-stride-audit",
            "reportApproved": validation.get("approved", False),
            "humanReviewed": architecture.get("reviewedByHuman", False),
            "reviewRequired": bool(human_review_items),
            "flowStrategy": architecture.get("flowStrategy") or DEFAULT_FLOW_STRATEGY,
            "flowStrategyTrace": architecture.get("flowStrategyTrace")
            or (architecture.get("structureMetadata") or {}).get("flowStrategy")
            or {},
        },
    }


def _quality_review_items(analysis_quality: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": f"analysis-quality-{index}",
            "kind": "analysis_quality",
            "severity": "High" if reason.get("severity") == "critical" else "Medium",
            "title": reason.get("message") or reason.get("code") or "Structural quality issue",
            "confidence": analysis_quality.get("score", 0.0),
            "reason": reason.get("code") or "unclassified_quality_issue",
        }
        for index, reason in enumerate(analysis_quality.get("reasons") or [], start=1)
    ]


def _build_quality_rejection_response(
    architecture: dict[str, Any],
    analysis_quality: dict[str, Any],
    detector_used: str,
) -> dict[str, Any]:
    issues = [
        reason.get("message") or reason.get("code") or "Structural quality issue"
        for reason in analysis_quality.get("reasons") or []
    ]
    return {
        "architecture": architecture,
        "threats": [],
        "score": None,
        "riskComparison": None,
        "coverage": {},
        "graph": {"nodes": [], "edges": []},
        "reportMarkdown": "",
        "reportFallback": "",
        "validation": {
            "approved": False,
            "score": 0.0,
            "issues": issues,
            "criteria": {"analysisQuality": False},
            "validator": "analysis_quality_gate",
        },
        "humanReviewItems": _quality_review_items(analysis_quality),
        "evidenceCatalog": [],
        "analysisQuality": analysis_quality,
        "reportSuppressed": True,
        "audit": {
            "analysisId": uuid.uuid4().hex,
            "requestId": REQUEST_ID.get(),
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "pipelineVersion": app.version,
            "humanReviewed": architecture.get("reviewedByHuman", False),
            "detectorModel": architecture.get("detectorModel"),
        },
        "pipeline": {
            "detectorUsed": detector_used,
            "detectorModel": architecture.get("detectorModel"),
            "modelTrace": architecture.get("detectorMetadata") or {},
            "structureTrace": architecture.get("structureMetadata") or {},
            "ocrTrace": architecture.get("ocrMetadata") or {},
            "alternativeTrace": architecture.get("detectionAlternativeTrace") or {
                "inputCount": 0,
                "outputCount": 0,
                "alternativeLossCount": 0,
            },
            "ragDocsRetrieved": 0,
            "ragRetrievalStrategy": "not_executed_quality_rejection",
            "reportApproved": False,
            "humanReviewed": architecture.get("reviewedByHuman", False),
            "reviewRequired": True,
            "flowStrategy": architecture.get("flowStrategy") or DEFAULT_FLOW_STRATEGY,
            "flowStrategyTrace": architecture.get("flowStrategyTrace")
            or (architecture.get("structureMetadata") or {}).get("flowStrategy")
            or {},
        },
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=BACKEND_PORT, reload=True)
