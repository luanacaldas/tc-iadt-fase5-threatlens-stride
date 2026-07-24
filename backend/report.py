"""Geração do relatório executivo STRIDE com Gemini.

Recebe a análise do motor de regras + contexto da RAG e gera um relatório
estruturado e legível. Aplica a regra de não-alucinação: o LLM não pode
inventar componentes ausentes no JSON de entrada.
"""

from __future__ import annotations

from google import genai
from google.genai import types

from backend.config import GEMINI_API_KEY, GEMINI_MODEL

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


_SYSTEM_PROMPT = """You are a senior application security engineer writing a formal STRIDE threat modeling report.

CRITICAL RULES — follow these without exception:
1. Only reference components explicitly listed in the PROVIDED_ARCHITECTURE JSON.
2. If a component was not detected, say "No [component] was detected. Confirm if one exists outside the diagram." — never assert it is absent.
3. Base every threat on the DETECTED_THREATS list. You may expand with RAG_CONTEXT, but do not contradict or omit rule-engine findings.
4. Every threat must include: STRIDE category, severity, evidence, and at least two countermeasures.
5. Write in formal but accessible English. No generic advice — be specific to the detected architecture.
6. Structure the report exactly as requested in the OUTPUT_FORMAT.
7. DETECTION_ALTERNATIVES are superseded hypotheses for review only. Never treat them as active components, threat evidence, graph nodes, or risk inputs.

OUTPUT_FORMAT (use these exact section headings):
## Executive Summary
## Architecture Overview
## Detected Components
## Detection Alternatives Pending Review
## STRIDE Threat Coverage
## Prioritized Threats
## Recommended Remediation Plan
## Human Review Checklist
## Limitations and Assumptions
"""


def _build_user_prompt(architecture: dict, threats: list[dict], rag_context: list[str], score: dict, coverage: dict) -> str:
    components_text = "\n".join(
        f"- {c['name']} (type={c['type']}, provider={c.get('provider','generic')}, confidence={round(c['confidence']*100)}%)"
        for c in architecture.get("components", [])
    )
    flows_text = "\n".join(
        f"- {f['from']} → {f['to']} [{f.get('protocol','?')}]{'  ⚠ trust boundary' if f.get('trustBoundary') else ''}"
        for f in architecture.get("flows", [])
    )
    alternatives = architecture.get("detectionAlternatives") or []
    alternatives_text = "\n".join(
        (
            f"- {item['id']} (name={item['name']}, type={item['type']}, provider={item['provider']}, "
            f"confidence={round(item['confidence'] * 100)}%, "
            f"supersededBy={(item.get('metadata') or {}).get('supersededBy')})"
        )
        for item in alternatives
    ) or "No superseded detection alternatives were retained."
    threats_text = "\n".join(
        f"[{t['severity']}] {t['stride']}: {t['title']}\n  Evidence: {t['evidence']}\n  Countermeasures: {'; '.join(t['countermeasures'])}"
        for t in threats[:15]
    )
    rag_text = "\n\n---\n\n".join(rag_context) if rag_context else "No additional context retrieved."
    coverage_text = "\n".join(f"- {k}: {v} threats" for k, v in coverage.items())

    return f"""PROVIDED_ARCHITECTURE:
Name: {architecture.get('name', 'Unknown')}
Risk Score: {score['label']} ({score['value']}/10)
Summary: {score['summary']}

COMPONENTS:
{components_text}

FLOWS:
{flows_text}

DETECTION_ALTERNATIVES (review-only; excluded from threats, graph, and risk):
{alternatives_text}

DETECTED_THREATS (from rule engine — do not omit any):
{threats_text}

STRIDE_COVERAGE:
{coverage_text}

RAG_CONTEXT (additional security knowledge — use to enrich, not contradict):
{rag_text}

Now write the full STRIDE threat modeling report following the OUTPUT_FORMAT.
"""


def generate_report(
    architecture: dict,
    threats: list[dict],
    rag_context: list[str],
    score: dict,
    coverage: dict,
) -> str:
    """Gera o relatório STRIDE completo. Retorna texto Markdown."""
    client = _get_client()
    user_prompt = _build_user_prompt(architecture, threats, rag_context, score, coverage)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_text(text=_SYSTEM_PROMPT + "\n\n" + user_prompt),
        ],
    )
    return response.text
