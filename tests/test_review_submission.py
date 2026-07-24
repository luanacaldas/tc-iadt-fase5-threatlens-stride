from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from backend.main import submit_tl004_review
from backend.review_submission import ReviewSubmissionError, store_review_submission


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFEST = ROOT / "data/reviews/tl004-junction-aware/batch-01/review-manifest.json"
SOURCE_RESULT = ROOT / "data/reviews/tl004-junction-aware/batch-01/review-result.json"


class ReviewSubmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
        self.result = json.loads(SOURCE_RESULT.read_text(encoding="utf-8"))
        self.token = "test-token-" + "a" * 40
        self.manifest["submissionToken"] = self.token

    def _root_with_manifest(self, parent: str) -> Path:
        root = Path(parent)
        batch_dir = root / "data/reviews/tl004-junction-aware/batch-01"
        batch_dir.mkdir(parents=True)
        (batch_dir / "review-manifest.json").write_text(
            json.dumps(self.manifest), encoding="utf-8"
        )
        return root

    def test_valid_submission_is_saved_canonically_and_in_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._root_with_manifest(directory)
            received_at = datetime(2026, 7, 21, 15, 0, tzinfo=timezone.utc)
            result = store_review_submission(
                {"submissionToken": self.token, "review": self.result},
                root=root,
                received_at=received_at,
            )

            self.assertEqual(result["status"], "accepted")
            self.assertEqual(result["completedCaseCount"], 18)
            self.assertEqual(len(result["sha256"]), 64)
            self.assertTrue((root / result["artifact"]).is_file())
            self.assertTrue((root / result["submissionArtifact"]).is_file())
            persisted = json.loads((root / result["artifact"]).read_text(encoding="utf-8"))
            self.assertEqual(persisted, self.result)
            self.assertNotIn("submissionToken", persisted)

    def test_invalid_token_is_rejected_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._root_with_manifest(directory)
            with self.assertRaises(ReviewSubmissionError) as context:
                store_review_submission(
                    {"submissionToken": "wrong", "review": self.result}, root=root
                )

            self.assertEqual(context.exception.status_code, 403)
            self.assertFalse(
                (root / "data/reviews/tl004-junction-aware/batch-01/review-result.json").exists()
            )

    def test_incomplete_or_conflicting_review_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._root_with_manifest(directory)
            incomplete = copy.deepcopy(self.result)
            incomplete["responses"] = incomplete["responses"][:-1]
            with self.assertRaises(ReviewSubmissionError):
                store_review_submission(
                    {"submissionToken": self.token, "review": incomplete}, root=root
                )

            conflicting = copy.deepcopy(self.result)
            conflicting["responses"][0]["recordIds"] = ["unexpected"]
            with self.assertRaises(ReviewSubmissionError):
                store_review_submission(
                    {"submissionToken": self.token, "review": conflicting}, root=root
                )


class ReviewSubmissionEndpointTests(unittest.IsolatedAsyncioTestCase):
    class RequestStub:
        def __init__(self, body: bytes, origin: str = "null") -> None:
            self._body = body
            self.headers = {"origin": origin}

        async def body(self) -> bytes:
            return self._body

    async def test_file_origin_receives_confirmation_and_cors_header(self) -> None:
        accepted = {
            "status": "accepted",
            "batchId": "tl004-junction-review-batch-01",
            "completedCaseCount": 18,
            "sha256": "a" * 64,
            "duplicate": False,
            "artifact": "data/reviews/tl004-junction-aware/batch-01/review-result.json",
            "submissionArtifact": "data/reviews/tl004-junction-aware/batch-01/submissions/example.json",
            "receivedAt": "2026-07-21T15:00:00+00:00",
        }
        request = self.RequestStub(b'{"submissionToken":"token","review":{}}')
        with patch("backend.main.store_review_submission", return_value=accepted):
            response = await submit_tl004_review(request)  # type: ignore[arg-type]

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["access-control-allow-origin"], "null")
        self.assertIn(b'"status":"accepted"', response.body)

    async def test_invalid_json_returns_readable_file_origin_error(self) -> None:
        response = await submit_tl004_review(  # type: ignore[arg-type]
            self.RequestStub(b"not-json")
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.headers["access-control-allow-origin"], "null")
        self.assertIn(b"valid JSON", response.body)


if __name__ == "__main__":
    unittest.main()
