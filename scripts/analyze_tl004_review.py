"""Validate and summarize a completed TL-004 human-review export."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data/reviews/tl004-junction-aware/batch-01/review-manifest.json"
DEFAULT_RESULT = ROOT / "data/reviews/tl004-junction-aware/batch-01/review-result.json"
DEFAULT_JSON_OUTPUT = ROOT / "data/reviews/tl004-junction-aware/batch-01/review-analysis.json"
DEFAULT_MARKDOWN_OUTPUT = ROOT / "data/reviews/tl004-junction-aware/batch-01/review-analysis.md"

VALID_DECISIONS = {"confirmed_false_positive", "valid_connection", "ambiguous"}
VALID_SCOPES = {"inside", "partial", "outside"}
VALID_CONFIDENCE = {"low", "medium", "high"}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _counts(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def validate_review(manifest: dict[str, Any], result: dict[str, Any]) -> None:
    if result.get("batchId") != manifest.get("batchId"):
        raise ValueError("Review result batchId does not match the source manifest.")
    if result.get("split") != "development_tuning" or manifest.get("split") != "development_tuning":
        raise ValueError("Human review is restricted to development_tuning.")

    expected = {str(case["caseId"]): case for case in manifest.get("cases") or []}
    responses = result.get("responses") or []
    response_ids = [str(response.get("caseId") or "") for response in responses]
    if len(response_ids) != len(set(response_ids)):
        raise ValueError("Review result contains duplicate case IDs.")
    if set(response_ids) != set(expected):
        missing = sorted(set(expected) - set(response_ids))
        extra = sorted(set(response_ids) - set(expected))
        raise ValueError(f"Review result case mismatch; missing={missing}, extra={extra}.")

    for response in responses:
        case_id = str(response["caseId"])
        source = expected[case_id]
        if response.get("group") != source.get("group"):
            raise ValueError(f"Review group mismatch for {case_id}.")
        source_record_ids = {
            str(record["inventoryId"]) for record in source.get("records") or []
        }
        if set(str(item) for item in response.get("recordIds") or []) != source_record_ids:
            raise ValueError(f"Review record mismatch for {case_id}.")
        review = response.get("review") or {}
        if review.get("decision") not in VALID_DECISIONS:
            raise ValueError(f"Invalid or missing decision for {case_id}.")
        if not str(review.get("primaryCause") or "").strip():
            raise ValueError(f"Missing primary cause for {case_id}.")
        if review.get("tl004Scope") not in VALID_SCOPES:
            raise ValueError(f"Invalid or missing TL-004 scope for {case_id}.")
        if review.get("confidence") not in VALID_CONFIDENCE:
            raise ValueError(f"Invalid or missing confidence for {case_id}.")

    assessment = result.get("batchAssessment") or {}
    if not str(assessment.get("reviewer") or "").strip():
        raise ValueError("Batch reviewer is required.")
    if not isinstance(assessment.get("newRelevantCategoriesFound"), bool):
        raise ValueError("Batch new-category decision is required.")
    if not isinstance(assessment.get("validInvalidDistinctionResolved"), bool):
        raise ValueError("Batch valid/invalid distinction decision is required.")


def analyze_review(
    manifest_path: Path = DEFAULT_MANIFEST,
    result_path: Path = DEFAULT_RESULT,
    json_output: Path = DEFAULT_JSON_OUTPUT,
    markdown_output: Path = DEFAULT_MARKDOWN_OUTPUT,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    result = _load_json(result_path)
    validate_review(manifest, result)

    responses = result["responses"]
    reviews = [response["review"] for response in responses]
    assessment = result["batchAssessment"]
    ambiguous_cases = sorted(
        response["caseId"]
        for response in responses
        if response["review"]["decision"] == "ambiguous"
        or response["review"]["primaryCause"] == "inconclusive"
    )
    low_confidence_cases = sorted(
        response["caseId"]
        for response in responses
        if response["review"]["confidence"] == "low"
    )
    case_new_categories = sorted(
        {
            str(review["newCategory"]).strip()
            for review in reviews
            if str(review.get("newCategory") or "").strip()
        }
    )
    categories_needing_examples = str(
        assessment.get("categoriesNeedingMoreExamples") or ""
    ).strip()
    trigger_checks = {
        "newRelevantCategoriesFound": bool(assessment["newRelevantCategoriesFound"]),
        "caseLevelNewCategoriesFound": bool(case_new_categories),
        "ambiguousCasesFound": bool(ambiguous_cases),
        "lowConfidenceCasesFound": bool(low_confidence_cases),
        "coverageGapsDeclared": bool(categories_needing_examples),
        "validInvalidDistinctionUnresolved": not bool(
            assessment["validInvalidDistinctionResolved"]
        ),
    }
    reasons = [name for name, triggered in trigger_checks.items() if triggered]
    action = "generate_batch_02" if reasons else "stop_review"

    expected_decisions = {
        "error": "confirmed_false_positive",
        "control": "valid_connection",
    }
    decision_mismatches = sorted(
        response["caseId"]
        for response in responses
        if response["review"]["decision"] != expected_decisions.get(response["group"])
    )
    analysis = {
        "schemaVersion": "1.0",
        "analysisId": "tl004-junction-review-batch-01-analysis",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "split": "development_tuning",
        "sourceManifest": _relative(manifest_path),
        "sourceReviewResult": _relative(result_path),
        "reviewer": assessment["reviewer"],
        "completion": {
            "expectedCaseCount": len(manifest["cases"]),
            "completedCaseCount": len(responses),
            "complete": len(responses) == len(manifest["cases"]),
        },
        "distributions": {
            "group": _counts([str(response["group"]) for response in responses]),
            "decision": _counts([str(review["decision"]) for review in reviews]),
            "primaryCause": _counts([str(review["primaryCause"]) for review in reviews]),
            "tl004Scope": _counts([str(review["tl004Scope"]) for review in reviews]),
            "confidence": _counts([str(review["confidence"]) for review in reviews]),
            "contributingCause": _counts(
                [
                    str(cause)
                    for review in reviews
                    for cause in review.get("contributingCauses") or []
                ]
            ),
        },
        "quality": {
            "decisionMismatchCaseIds": decision_mismatches,
            "ambiguousCaseIds": ambiguous_cases,
            "lowConfidenceCaseIds": low_confidence_cases,
            "caseLevelNewCategories": case_new_categories,
            "controlsValidated": sum(
                response["group"] == "control"
                and response["review"]["decision"] == "valid_connection"
                for response in responses
            ),
            "falsePositivesConfirmed": sum(
                response["group"] == "error"
                and response["review"]["decision"] == "confirmed_false_positive"
                for response in responses
            ),
        },
        "batchAssessment": assessment,
        "nextStepDecision": {
            "action": action,
            "triggerChecks": trigger_checks,
            "triggeredReasons": reasons,
            "requestedBatchSize": "8-10" if action == "generate_batch_02" else None,
            "noNewRelevantCauseStreak": (
                0 if assessment["newRelevantCategoriesFound"] else 1
            ),
            "stopRuleSatisfied": False,
            "stopRule": (
                "Stop after two consecutive completed batches reveal no relevant new cause."
            ),
        },
    }

    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    causes = analysis["distributions"]["primaryCause"]
    scopes = analysis["distributions"]["tl004Scope"]
    markdown_output.write_text(
        "\n".join(
            (
                "# TL-004 - Analise da revisao humana do lote 01",
                "",
                f"- Revisor(a): {assessment['reviewer']}",
                f"- Casos concluidos: {len(responses)}/{len(manifest['cases'])}",
                f"- Falsos positivos confirmados: {analysis['quality']['falsePositivesConfirmed']}",
                f"- Controles validos confirmados: {analysis['quality']['controlsValidated']}",
                f"- Confianca alta: {analysis['distributions']['confidence'].get('high', 0)}",
                f"- Confianca media: {analysis['distributions']['confidence'].get('medium', 0)}",
                "",
                "## Causas principais",
                "",
                *[f"- `{name}`: {count}" for name, count in causes.items()],
                "",
                "## Escopo da TL-004",
                "",
                *[f"- `{name}`: {count}" for name, count in scopes.items()],
                "",
                "## Decisao",
                "",
                f"Acao: `{action}`.",
                "Motivos: " + ", ".join(f"`{reason}`" for reason in reasons) + ".",
                "",
                "Nao houve nova categoria principal. O subtipo relatado permanece sob "
                "`structural_line` e nao amplia a taxonomia neste ciclo.",
                "",
                "A pipeline e os artefatos prospectivos nao foram alterados.",
            )
        ),
        encoding="utf-8",
    )
    return analysis


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    args = parser.parse_args()
    analysis = analyze_review(
        args.manifest, args.result, args.json_output, args.markdown_output
    )
    print(json.dumps(analysis, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
