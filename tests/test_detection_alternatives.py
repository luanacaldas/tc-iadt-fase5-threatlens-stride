from __future__ import annotations

import json
import unittest
from copy import deepcopy
from io import BytesIO
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from PIL import Image

from backend.main import (
    _build_response,
    _validate_architecture_payload,
    analyze_full,
    analyze_image_endpoint,
    analyze_json,
)
from backend.pdf_report import _detection_alternative_rows, generate_pdf
from backend.stride_engine import analyze_architecture, normalize_architecture


def _architecture(with_alternatives: bool = True) -> dict:
    payload = {
        "name": "Alternative round-trip",
        "components": [
            {
                "id": "api",
                "name": "API Gateway",
                "type": "api_gateway",
                "provider": "aws",
                "confidence": 0.91,
                "bbox": [100, 40, 180, 120],
                "reviewStatus": "confirmed",
            },
            {
                "id": "db",
                "name": "Database",
                "type": "database",
                "provider": "aws",
                "confidence": 0.88,
                "bbox": [280, 40, 360, 120],
                "reviewStatus": "confirmed",
            },
        ],
        "flows": [
            {
                "id": "flow_api_db",
                "from": "api",
                "to": "db",
                "protocol": "TLS",
                "confidence": 0.84,
                "reviewStatus": "confirmed",
            }
        ],
        "trustBoundaries": [],
        "reviewedByHuman": True,
    }
    if with_alternatives:
        payload["detectionAlternatives"] = [
            {
                "id": "compute_superseded",
                "name": "Compute hypothesis",
                "type": "compute",
                "provider": "aws",
                "confidence": 0.62,
                "rawConfidence": 0.71,
                "bbox": [102, 42, 178, 118],
                "reviewStatus": "superseded_pending_review",
                "ocrLabel": "API Gateway",
                "ocrEvidence": {"text": "API Gateway", "confidence": 0.94},
                "metadata": {
                    "supersededBy": "api",
                    "supersededReason": "explicit_semantic_ocr_conflict",
                    "customEvidence": {"source": "detector-v15"},
                },
            },
            {
                "id": "storage_superseded",
                "name": "Storage hypothesis",
                "type": "storage",
                "provider": "azure",
                "confidence": 0.57,
                "bbox": [282, 42, 358, 118],
                "reviewStatus": "superseded_pending_review",
                "metadata": {
                    "supersededBy": "db",
                    "supersededReason": "shared_visual_anchor_semantic_conflict",
                },
            },
        ]
    return payload


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class _MemoryUpload:
    def __init__(self, content: bytes, content_type: str = "image/png"):
        self._content = BytesIO(content)
        self.content_type = content_type

    async def read(self, size: int = -1) -> bytes:
        return self._content.read(size)


def _validation() -> dict:
    return {
        "approved": True,
        "score": 1.0,
        "issues": [],
        "criteria": {},
        "validator": "test",
    }


async def _report_from_analysis(analysis: dict, _rag_context: list[str]) -> tuple[str, dict]:
    return analysis["reportMarkdown"], _validation()


class DetectionAlternativeContractTests(unittest.TestCase):
    def test_normalization_preserves_every_valid_alternative_and_metadata(self) -> None:
        source = _architecture()

        normalized = normalize_architecture(source)

        self.assertEqual(len(normalized["detectionAlternatives"]), len(source["detectionAlternatives"]))
        self.assertEqual(normalized["detectionAlternativeTrace"]["alternativeLossCount"], 0)
        self.assertEqual(
            normalized["detectionAlternatives"][0]["metadata"]["customEvidence"],
            {"source": "detector-v15"},
        )

    def test_alternatives_do_not_change_stride_risk_or_graph(self) -> None:
        with_alternatives = analyze_architecture(_architecture())
        without_alternatives = analyze_architecture(_architecture(with_alternatives=False))

        for field in ("threats", "score", "riskComparison", "coverage", "graph"):
            self.assertEqual(with_alternatives[field], without_alternatives[field])

        alternative_ids = {
            item["id"] for item in with_alternatives["architecture"]["detectionAlternatives"]
        }
        self.assertTrue(alternative_ids)
        self.assertTrue(all(threat.get("componentId") not in alternative_ids for threat in with_alternatives["threats"]))
        self.assertTrue(all(node["id"] not in alternative_ids for node in with_alternatives["graph"]["nodes"]))
        self.assertTrue(
            all(
                edge.get("from") not in alternative_ids and edge.get("to") not in alternative_ids
                for edge in with_alternatives["graph"]["edges"]
            )
        )

    def test_response_exposes_trace_review_items_and_markdown(self) -> None:
        analysis = analyze_architecture(_architecture())

        response = _build_response(analysis, [], "External report without alternatives.", _validation(), "test")

        self.assertEqual(response["pipeline"]["alternativeTrace"]["alternativeLossCount"], 0)
        self.assertEqual(
            len(response["architecture"]["detectionAlternatives"]),
            len(_architecture()["detectionAlternatives"]),
        )
        self.assertEqual(
            len([item for item in response["humanReviewItems"] if item["kind"] == "component_alternative"]),
            2,
        )
        self.assertIn("## Detection alternatives pending review", response["reportMarkdown"])
        for alternative in response["architecture"]["detectionAlternatives"]:
            self.assertIn(alternative["id"], response["reportMarkdown"])

    def test_old_analysis_without_alternatives_remains_compatible(self) -> None:
        analysis = analyze_architecture(_architecture(with_alternatives=False))

        self.assertEqual(analysis["architecture"]["detectionAlternatives"], [])
        self.assertEqual(
            analysis["architecture"]["detectionAlternativeTrace"],
            {"inputCount": 0, "outputCount": 0, "alternativeLossCount": 0},
        )

    def test_pdf_rows_and_document_preserve_alternative_count(self) -> None:
        analysis = analyze_architecture(_architecture())

        rows = _detection_alternative_rows(analysis["architecture"])
        content = generate_pdf(analysis)

        self.assertEqual(len(rows), len(_architecture()["detectionAlternatives"]))
        self.assertEqual({row[0] for row in rows}, {"compute_superseded", "storage_superseded"})
        self.assertTrue(content.startswith(b"%PDF"))
        self.assertGreater(len(content), 3000)


class DetectionAlternativeValidationTests(unittest.TestCase):
    def test_invalid_alternative_payloads_are_rejected(self) -> None:
        valid = _architecture()
        invalid_payloads = []

        not_an_array = deepcopy(valid)
        not_an_array["detectionAlternatives"] = {}
        invalid_payloads.append(not_an_array)

        not_an_object = deepcopy(valid)
        not_an_object["detectionAlternatives"] = ["alternative"]
        invalid_payloads.append(not_an_object)

        for field in ("id", "name", "type", "provider", "confidence", "bbox", "metadata"):
            missing = deepcopy(valid)
            missing["detectionAlternatives"][0].pop(field)
            invalid_payloads.append(missing)

        invalid_type = deepcopy(valid)
        invalid_type["detectionAlternatives"][0]["type"] = "not_supported"
        invalid_payloads.append(invalid_type)

        invalid_provider = deepcopy(valid)
        invalid_provider["detectionAlternatives"][0]["provider"] = "oracle"
        invalid_payloads.append(invalid_provider)

        invalid_confidence = deepcopy(valid)
        invalid_confidence["detectionAlternatives"][0]["confidence"] = 1.1
        invalid_payloads.append(invalid_confidence)

        invalid_bbox = deepcopy(valid)
        invalid_bbox["detectionAlternatives"][0]["bbox"] = [10, 20, 5, 30]
        invalid_payloads.append(invalid_bbox)

        invalid_metadata = deepcopy(valid)
        invalid_metadata["detectionAlternatives"][0]["metadata"] = []
        invalid_payloads.append(invalid_metadata)

        missing_superseded_by = deepcopy(valid)
        missing_superseded_by["detectionAlternatives"][0]["metadata"].pop("supersededBy")
        invalid_payloads.append(missing_superseded_by)

        unknown_superseded_by = deepcopy(valid)
        unknown_superseded_by["detectionAlternatives"][0]["metadata"]["supersededBy"] = "missing"
        invalid_payloads.append(unknown_superseded_by)

        duplicate_ids = deepcopy(valid)
        duplicate_ids["detectionAlternatives"][1]["id"] = duplicate_ids["detectionAlternatives"][0]["id"]
        invalid_payloads.append(duplicate_ids)

        active_id_conflict = deepcopy(valid)
        active_id_conflict["detectionAlternatives"][0]["id"] = "api"
        invalid_payloads.append(active_id_conflict)

        invalid_ocr_evidence = deepcopy(valid)
        invalid_ocr_evidence["detectionAlternatives"][0]["ocrEvidence"] = "text"
        invalid_payloads.append(invalid_ocr_evidence)

        for index, payload in enumerate(invalid_payloads):
            with self.subTest(case=index):
                with self.assertRaises(HTTPException) as context:
                    _validate_architecture_payload(payload)
                self.assertEqual(context.exception.status_code, 422)


class DetectionAlternativeEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_image_preserves_detector_alternatives(self) -> None:
        payload = _architecture()
        with patch("backend.main._detect_components", new=AsyncMock(return_value=deepcopy(payload))):
            response = await analyze_image_endpoint(_MemoryUpload(_png_bytes()))

        self.assertEqual(len(response["detectionAlternatives"]), len(payload["detectionAlternatives"]))

    async def test_analyze_json_preserves_alternatives(self) -> None:
        payload = _architecture()
        with (
            patch("backend.main._query_rag", return_value=[]),
            patch("backend.main._generate_and_validate", new=AsyncMock(side_effect=_report_from_analysis)),
        ):
            response = await analyze_json(deepcopy(payload))

        self.assertEqual(len(response["architecture"]["detectionAlternatives"]), 2)
        self.assertEqual(response["pipeline"]["alternativeTrace"]["alternativeLossCount"], 0)

    async def test_analyze_full_preserves_alternatives(self) -> None:
        payload = _architecture()
        with (
            patch("backend.main._query_rag", return_value=[]),
            patch("backend.main._generate_and_validate", new=AsyncMock(side_effect=_report_from_analysis)),
        ):
            response = await analyze_full(image=None, architecture_json=json.dumps(payload))

        self.assertEqual(len(response["architecture"]["detectionAlternatives"]), 2)
        self.assertEqual(response["pipeline"]["alternativeTrace"]["inputCount"], 2)

    async def test_analyze_json_rejects_invalid_alternative(self) -> None:
        payload = _architecture()
        payload["detectionAlternatives"][0]["id"] = "api"

        with self.assertRaises(HTTPException) as context:
            await analyze_json(payload)

        self.assertEqual(context.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
