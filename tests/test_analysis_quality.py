from __future__ import annotations

import base64
import json
import unittest
from copy import deepcopy
from unittest.mock import AsyncMock, patch

from backend.analysis_quality import assess_analysis_quality
from backend.main import analyze_full, analyze_image_endpoint, analyze_json, report_pdf
from fastapi import HTTPException


def _component(
    component_id: str,
    name: str,
    component_type: str = "compute",
    provider: str = "generic",
    bbox: list[int] | None = None,
) -> dict:
    value = {
        "id": component_id,
        "name": name,
        "type": component_type,
        "provider": provider,
        "confidence": 0.9,
        "reviewStatus": "auto_accepted",
    }
    if bbox is not None:
        value["bbox"] = bbox
    return value


def _clean_architecture() -> dict:
    return {
        "name": "Simple architecture",
        "components": [
            _component("client", "Client", "user"),
            _component("api", "Public API", "api_gateway"),
        ],
        "flows": [
            {
                "id": "f1",
                "from": "client",
                "to": "api",
                "protocol": "HTTPS",
                "confidence": 0.9,
                "reviewStatus": "auto_accepted",
            }
        ],
    }


def _comparative_architecture() -> dict:
    return {
        "name": "AWS comparative diagram",
        "detectedBy": "yolo",
        "components": [
            _component("kms-top", "Amazon Managed KMS key", "secrets_kms", "aws", [20, 40, 90, 100]),
            _component("kms-bottom", "Amazon Managed KMS key", "secrets_kms", "aws", [22, 310, 92, 370]),
            _component("account-top", "B. Central Backup account", "backup", "azure", [510, 30, 650, 90]),
            _component("account-bottom", "B. Central Backup account", "backup", "azure", [512, 300, 652, 360]),
        ],
        "flows": [
            {
                "id": "semantic-loop",
                "from": "account-top",
                "to": "account-bottom",
                "protocol": "unknown",
                "confidence": 0.5,
                "inferred": True,
                "reviewStatus": "pending",
            }
        ],
        "ocrMetadata": {
            "textRegions": [
                {"text": "AWS Organizations"},
                {"text": "Amazon Managed KMS key"},
            ]
        },
    }


class _MemoryUpload:
    filename = "diagram.png"
    content_type = "image/png"

    def __init__(self, content: bytes) -> None:
        self._content = content
        self._offset = 0

    async def read(self, size: int = -1) -> bytes:
        if self._offset >= len(self._content):
            return b""
        if size < 0:
            chunk = self._content[self._offset:]
            self._offset = len(self._content)
            return chunk
        chunk = self._content[self._offset:self._offset + size]
        self._offset += len(chunk)
        return chunk


_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class AnalysisQualityUnitTests(unittest.TestCase):
    def test_clean_architecture_is_reliable_and_input_is_immutable(self) -> None:
        source = _clean_architecture()
        before = deepcopy(source)

        sanitized, quality = assess_analysis_quality(source)

        self.assertEqual(source, before)
        self.assertEqual(sanitized["flows"], source["flows"])
        self.assertEqual(quality["status"], "reliable")
        self.assertEqual(quality["score"], 1.0)
        self.assertEqual(quality["reasons"], [])

    def test_comparative_panels_are_rejected_with_structured_evidence(self) -> None:
        sanitized, quality = assess_analysis_quality(_comparative_architecture())
        codes = {reason["code"] for reason in quality["reasons"]}

        self.assertEqual(quality["status"], "rejected")
        self.assertIn("multiple_diagrams_suspected", codes)
        self.assertIn("suspicious_duplicate_components", codes)
        self.assertIn("grouping_labels_as_components", codes)
        self.assertIn("provider_inconsistency", codes)
        self.assertIn("semantic_self_loop_blocked", codes)
        self.assertEqual(sanitized["flows"], [])
        self.assertEqual(quality["blockedFlowIds"], ["semantic-loop"])

    def test_confirmed_semantic_loop_with_explicit_evidence_is_preserved(self) -> None:
        source = _comparative_architecture()
        source["components"] = source["components"][:2]
        source["flows"] = [{
            "id": "confirmed-loop",
            "from": "kms-top",
            "to": "kms-bottom",
            "protocol": "HTTPS",
            "confidence": 0.9,
            "inferred": False,
            "reviewStatus": "confirmed",
            "evidence": "manual_review",
        }]

        sanitized, quality = assess_analysis_quality(source)

        self.assertEqual([flow["id"] for flow in sanitized["flows"]], ["confirmed-loop"])
        self.assertNotIn("semantic_self_loop_blocked", {item["code"] for item in quality["reasons"]})

    def test_duplicate_directed_flow_is_blocked_deterministically(self) -> None:
        source = _clean_architecture()
        source["flows"].append({**source["flows"][0], "id": "f2", "confidence": 0.99})

        first, first_quality = assess_analysis_quality(source)
        second, second_quality = assess_analysis_quality(source)

        self.assertEqual(first, second)
        self.assertEqual(first_quality, second_quality)
        self.assertEqual([flow["id"] for flow in first["flows"]], ["f1"])
        self.assertEqual(first_quality["blockedFlowIds"], ["f2"])

    def test_explicit_multicloud_labels_do_not_trigger_provider_inconsistency(self) -> None:
        source = {
            "components": [
                _component("lambda", "AWS Lambda", "compute", "aws"),
                _component("kms", "Amazon KMS", "secrets_kms", "aws"),
                _component("app", "Azure App Service", "compute", "azure"),
            ],
            "flows": [],
        }

        _, quality = assess_analysis_quality(source)

        self.assertNotIn("provider_inconsistency", {item["code"] for item in quality["reasons"]})

    def test_numeric_ocr_region_count_is_accepted(self) -> None:
        source = _clean_architecture()
        source["ocrMetadata"] = {"textRegions": 14}

        _, quality = assess_analysis_quality(source)

        self.assertEqual(quality["status"], "reliable")


class AnalysisQualityEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejected_json_skips_stride_rag_and_report_generation(self) -> None:
        with (
            patch("backend.main.analyze_architecture") as stride,
            patch("backend.main._query_rag") as rag,
            patch("backend.main._generate_and_validate", new=AsyncMock()) as report,
        ):
            response = await analyze_json(_comparative_architecture())

        stride.assert_not_called()
        rag.assert_not_called()
        report.assert_not_awaited()
        self.assertEqual(response["analysisQuality"]["status"], "rejected")
        self.assertTrue(response["reportSuppressed"])
        self.assertEqual(response["threats"], [])
        self.assertIsNone(response["score"])
        self.assertEqual(response["graph"], {"nodes": [], "edges": []})

    async def test_rejected_full_pipeline_skips_report_generation(self) -> None:
        with (
            patch("backend.main._query_rag") as rag,
            patch("backend.main._generate_and_validate", new=AsyncMock()) as report,
        ):
            response = await analyze_full(
                image=None,
                architecture_json=json.dumps(_comparative_architecture()),
            )

        rag.assert_not_called()
        report.assert_not_awaited()
        self.assertEqual(response["validation"]["validator"], "analysis_quality_gate")
        self.assertEqual(response["pipeline"]["ragDocsRetrieved"], 0)

    async def test_image_endpoint_exposes_quality_and_sanitized_flows(self) -> None:
        with patch(
            "backend.main._detect_components",
            new=AsyncMock(return_value=deepcopy(_comparative_architecture())),
        ):
            response = await analyze_image_endpoint(_MemoryUpload(_ONE_PIXEL_PNG))

        self.assertEqual(response["analysisQuality"]["status"], "rejected")
        self.assertEqual(response["flows"], [])

    async def test_reliable_json_continues_through_the_existing_pipeline(self) -> None:
        validation = {"approved": True, "score": 1.0, "issues": [], "criteria": {}}

        async def report_from_analysis(analysis: dict, _context: list[str]) -> tuple[str, dict]:
            return analysis["reportMarkdown"], validation

        with (
            patch("backend.main._query_rag", return_value=[]),
            patch("backend.main._generate_and_validate", new=AsyncMock(side_effect=report_from_analysis)),
        ):
            response = await analyze_json(_clean_architecture())

        self.assertEqual(response["analysisQuality"]["status"], "reliable")
        self.assertFalse(response["reportSuppressed"])
        self.assertGreater(len(response["threats"]), 0)
        self.assertIsNotNone(response["score"])

    async def test_pdf_export_rejects_a_suppressed_analysis(self) -> None:
        body = {
            "architecture": _comparative_architecture(),
            "threats": [],
            "analysisQuality": {
                "status": "rejected",
                "score": 0.1,
                "reasons": [],
                "recommendedAction": "Send one diagram.",
            },
            "reportSuppressed": True,
        }

        with self.assertRaises(HTTPException) as context:
            await report_pdf(body)

        self.assertEqual(context.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
