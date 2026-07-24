"""Gemini Vision — extrai componentes arquiteturais de uma imagem de diagrama.

Retorna um dict no mesmo formato do sample-architecture.json.
Usado como fallback quando o YOLO não está disponível ou tem baixa confiança.
"""

from __future__ import annotations

import json
import re

from google import genai
from google.genai import types

from backend.config import GEMINI_API_KEY, GEMINI_MODEL

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


_SYSTEM_PROMPT = """You are an expert software architecture analyst and security engineer.
Your task is to analyze a software architecture diagram image and identify all architectural components.

Return ONLY a valid JSON object — no markdown fences, no explanation, just raw JSON.

The JSON must follow this exact schema:
{
  "name": "string — inferred architecture name",
  "components": [
    {
      "id": "short_snake_case_id",
      "name": "Human readable name",
      "type": "one of the allowed types below",
      "provider": "aws | azure | gcp | generic",
      "confidence": 0.0-1.0,
      "bbox": [x1, y1, x2, y2]
    }
  ],
  "flows": [
    {
      "id": "f1",
      "from": "component_id",
      "to": "component_id",
      "protocol": "HTTPS | HTTP | TCP | gRPC | AMQP | unknown",
      "trustBoundary": true | false
    }
  ]
}

Allowed component types (use only these exact strings):
user, internet, identity_provider, waf, cdn, api_gateway, load_balancer,
compute, database, storage, queue, monitoring, backup, secrets_kms

Rules:
- Assign bounding box [x1, y1, x2, y2] relative to the image dimensions (pixels).
- If you cannot determine the exact position, use an approximate estimate.
- Set trustBoundary to true for flows that cross a security boundary (e.g. internet to internal network).
- If an arrow or flow line is not clear, infer it from component position (left-to-right, top-to-bottom).
- Do NOT include components you are not confident about (confidence < 0.5).
- Generate sequential IDs: user_1, api_gateway_1, database_1, etc.
"""


def _extract_json(text: str) -> dict:
    """Extrai JSON do texto — ignora markdown fences se o modelo insistir."""
    text = text.strip()
    # Remove ```json ... ``` ou ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def analyze_image(image_bytes: bytes, mime_type: str = "image/png") -> dict:
    """Envia a imagem para o Gemini e retorna o JSON de arquitetura detectada."""
    client = _get_client()

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            types.Part.from_text(text=_SYSTEM_PROMPT),
        ],
    )

    raw_text = response.text
    result = _extract_json(raw_text)

    # Garante campo obrigatório
    if "components" not in result:
        result["components"] = []
    if "flows" not in result:
        result["flows"] = []

    # Marca que a detecção veio do Gemini Vision
    result["detectedBy"] = "gemini_vision"
    result["detectorModel"] = GEMINI_MODEL

    return result
