"""Validated local persistence for TL-004 human-review submissions."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BATCH_ID_PATTERN = re.compile(r"tl004-junction-review-batch-(\d{2})")
VALID_DECISIONS = {"confirmed_false_positive", "valid_connection", "ambiguous"}
VALID_SCOPES = {"inside", "partial", "outside"}
VALID_CONFIDENCE = {"low", "medium", "high"}


class ReviewSubmissionError(ValueError):
    def __init__(self, detail: str, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewSubmissionError("Review manifest is unavailable.", 404) from exc


def _batch_directory(batch_id: str, root: Path) -> Path:
    match = BATCH_ID_PATTERN.fullmatch(batch_id)
    if not match:
        raise ReviewSubmissionError("Unsupported review batch ID.")
    directory = root / "data" / "reviews" / "tl004-junction-aware" / f"batch-{match.group(1)}"
    try:
        directory.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReviewSubmissionError("Invalid review batch path.") from exc
    return directory


def _validate_response(response: dict[str, Any], source: dict[str, Any]) -> None:
    case_id = str(source["caseId"])
    if response.get("group") != source.get("group"):
        raise ReviewSubmissionError(f"Review group mismatch for {case_id}.")
    if response.get("imageId") != source.get("imageId"):
        raise ReviewSubmissionError(f"Review image mismatch for {case_id}.")
    expected_record_ids = {
        str(record["inventoryId"]) for record in source.get("records") or []
    }
    received_record_ids = {str(item) for item in response.get("recordIds") or []}
    if received_record_ids != expected_record_ids:
        raise ReviewSubmissionError(f"Review records mismatch for {case_id}.")

    review = response.get("review") or {}
    if review.get("decision") not in VALID_DECISIONS:
        raise ReviewSubmissionError(f"Invalid or missing decision for {case_id}.")
    if not str(review.get("primaryCause") or "").strip():
        raise ReviewSubmissionError(f"Missing primary cause for {case_id}.")
    if review.get("tl004Scope") not in VALID_SCOPES:
        raise ReviewSubmissionError(f"Invalid or missing TL-004 scope for {case_id}.")
    if review.get("confidence") not in VALID_CONFIDENCE:
        raise ReviewSubmissionError(f"Invalid or missing confidence for {case_id}.")


def validate_submission(
    envelope: dict[str, Any], root: Path = PROJECT_ROOT
) -> tuple[dict[str, Any], Path]:
    if not isinstance(envelope, dict):
        raise ReviewSubmissionError("Submission envelope must be a JSON object.")
    review = envelope.get("review")
    token = envelope.get("submissionToken")
    if not isinstance(review, dict) or not isinstance(token, str):
        raise ReviewSubmissionError("Review payload and submission token are required.")
    batch_id = str(review.get("batchId") or "")
    batch_dir = _batch_directory(batch_id, root)
    manifest = _load_json(batch_dir / "review-manifest.json")
    expected_token = str(manifest.get("submissionToken") or "")
    if len(expected_token) < 32 or not hmac.compare_digest(token, expected_token):
        raise ReviewSubmissionError("Invalid review submission token.", 403)
    if review.get("schemaVersion") != "1.0":
        raise ReviewSubmissionError("Unsupported review result schema.")
    if review.get("split") != "development_tuning" or manifest.get("split") != "development_tuning":
        raise ReviewSubmissionError("Review submissions are restricted to development_tuning.")
    if review.get("sourceManifest") != "review-manifest.json":
        raise ReviewSubmissionError("Unexpected source manifest.")

    expected_cases = {
        str(case["caseId"]): case for case in manifest.get("cases") or []
    }
    responses = review.get("responses")
    if not isinstance(responses, list):
        raise ReviewSubmissionError("Review responses must be an array.")
    response_ids = [str(response.get("caseId") or "") for response in responses]
    if len(response_ids) != len(set(response_ids)):
        raise ReviewSubmissionError("Review contains duplicate case IDs.")
    if set(response_ids) != set(expected_cases):
        raise ReviewSubmissionError("Review must contain every manifest case exactly once.")
    for response in responses:
        if not isinstance(response, dict):
            raise ReviewSubmissionError("Each review response must be an object.")
        _validate_response(response, expected_cases[str(response["caseId"])])

    assessment = review.get("batchAssessment") or {}
    if not str(assessment.get("reviewer") or "").strip():
        raise ReviewSubmissionError("Batch reviewer is required.")
    if not isinstance(assessment.get("newRelevantCategoriesFound"), bool):
        raise ReviewSubmissionError("New-category assessment is required.")
    if not isinstance(assessment.get("validInvalidDistinctionResolved"), bool):
        raise ReviewSubmissionError("Valid/invalid distinction assessment is required.")
    return review, batch_dir


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def store_review_submission(
    envelope: dict[str, Any],
    root: Path = PROJECT_ROOT,
    received_at: datetime | None = None,
) -> dict[str, Any]:
    review, batch_dir = validate_submission(envelope, root)
    content = json.dumps(review, indent=2, ensure_ascii=False).encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()
    timestamp = (received_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    stamp = timestamp.strftime("%Y%m%dT%H%M%SZ")
    canonical_path = batch_dir / "review-result.json"
    submission_path = batch_dir / "submissions" / f"{stamp}-{digest[:12]}.json"
    duplicate = submission_path.exists()
    if not duplicate:
        _atomic_write(submission_path, content)
    _atomic_write(canonical_path, content)
    return {
        "status": "accepted",
        "batchId": review["batchId"],
        "completedCaseCount": len(review["responses"]),
        "sha256": digest,
        "duplicate": duplicate,
        "artifact": canonical_path.resolve().relative_to(root.resolve()).as_posix(),
        "submissionArtifact": submission_path.resolve().relative_to(root.resolve()).as_posix(),
        "receivedAt": timestamp.isoformat(),
    }
