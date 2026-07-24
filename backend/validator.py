"""Validador do relatório gerado — usa Groq (LLaMA 3.3 70B).

Verifica alucinações, cobertura e qualidade do relatório antes de
entregar ao usuário. Se reprovado, o chamador pode solicitar
regeneração ou marcar como "requires human review".
"""

from __future__ import annotations

import json
import re

from groq import Groq

from backend.config import GROQ_API_KEY, GROQ_MODEL

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


_SYSTEM_PROMPT = """You are a security report quality auditor. Your job is to validate an AI-generated STRIDE threat modeling report.

Check the following criteria and return a JSON validation result.

VALIDATION CRITERIA:
1. hallucination_check — Does the report mention components NOT present in the architecture JSON? (fail = true if yes)
2. coverage_check — Do all high-risk components (database, secrets_kms, identity_provider, api_gateway) have at least one threat? (fail = true if any is missing)
3. stride_coverage — Are at least 4 of the 6 STRIDE categories addressed? (fail = true if fewer)
4. countermeasures_check — Does every threat include at least one specific countermeasure? (fail = true if any threat lacks countermeasures)
5. no_generic_advice — Does the report avoid purely generic advice (e.g. "use encryption" without context)? (fail = true if predominantly generic)

Return ONLY valid JSON, no markdown fences:
{
  "approved": true | false,
  "score": 0.0-1.0,
  "issues": ["list of specific issues found, empty if none"],
  "criteria": {
    "hallucination_check": "pass" | "fail",
    "coverage_check": "pass" | "fail",
    "stride_coverage": "pass" | "fail",
    "countermeasures_check": "pass" | "fail",
    "no_generic_advice": "pass" | "fail"
  }
}

A report is approved (approved=true) if score >= 0.70 and hallucination_check = pass.
"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def validate_report(report: str, architecture: dict, threats: list[dict]) -> dict:
    """Valida o relatório contra a arquitetura de origem.

    Retorna dict com: approved, score, issues, criteria.
    Em caso de falha na API, retorna resultado de fallback conservador.
    """
    client = _get_client()

    component_names = [c["name"] for c in architecture.get("components", [])]
    component_types = [c["type"] for c in architecture.get("components", [])]
    threat_summary = "\n".join(f"- [{t['severity']}] {t['stride']}: {t['title']}" for t in threats[:15])

    user_prompt = f"""ARCHITECTURE COMPONENTS (names and types present in the diagram):
Names: {", ".join(component_names)}
Types: {", ".join(component_types)}

RULE-ENGINE THREATS (ground truth — must all be covered):
{threat_summary}

GENERATED REPORT TO VALIDATE:
---
{report[:4000]}
---

Validate the report against the criteria and return the JSON result."""

    try:
        completion = _get_client().chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        raw = completion.choices[0].message.content or "{}"
        result = _extract_json(raw)

        # Garante campos obrigatórios
        result.setdefault("approved", False)
        result.setdefault("score", 0.0)
        result.setdefault("issues", [])
        result.setdefault("criteria", {})
        return result

    except Exception as exc:
        return {
            "approved": False,
            "score": 0.0,
            "issues": [f"Validation service unavailable: {exc}. Report requires human review."],
            "criteria": {},
        }
