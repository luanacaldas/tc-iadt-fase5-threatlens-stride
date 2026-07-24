from __future__ import annotations

import json
import unittest
from copy import deepcopy
from io import BytesIO
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from PIL import Image

from backend.flow_strategy import (
    CONTROLLED_MODULE_FLAGS,
    DEFAULT_FLOW_STRATEGY,
    SUPPORTED_FLOW_STRATEGIES,
    apply_flow_strategy,
    resolve_flow_strategy,
)
from backend.main import analyze_full, analyze_image_endpoint, analyze_json


def _components() -> list[dict]:
    return [
        {"id": "source", "name": "Source", "type": "user", "bbox": [0, 0, 10, 10]},
        {"id": "target", "name": "Target", "type": "api_gateway", "bbox": [300, 0, 310, 10]},
    ]


def _architecture(*, structural: bool = False) -> dict:
    payload = {
        "name": "Controlled strategy fixture",
        "components": _components(),
        "flows": [
            {
                "id": "f1",
                "from": "source",
                "to": "target",
                "protocol": "HTTPS",
                "confidence": 0.8,
                "directionConfidence": 0.2,
                "pathPoints": [[100, 100], [200, 100]],
            }
        ],
        "trustBoundaries": [],
        "detectionAlternatives": [],
    }
    if structural:
        payload["flowStrategyContext"] = {
            "structuralEvidenceByCandidate": {
                "f1": {
                    "sourcePortConfirmed": False,
                    "destinationPortConfirmed": False,
                    "structuralAlignment": {
                        "aligned": True,
                        "kind": "container_border",
                        "confidence": "high",
                        "source": "human_review",
                    },
                    "connectorContinuity": {"present": False, "confidence": "low"},
                    "arrowheadPresent": False,
                    "unmarkedCrossingCount": 0,
                    "humanReview": {
                        "decision": "confirmed_false_positive",
                        "primaryCause": "structural_line",
                        "confidence": "high",
                    },
                }
            }
        }
    return payload


def _validation() -> dict:
    return {"approved": True, "score": 1.0, "issues": [], "criteria": {}}


async def _report_from_analysis(analysis: dict, _rag: list[str]) -> tuple[str, dict]:
    return analysis["reportMarkdown"], _validation()


class _MemoryUpload:
    filename = "diagram.png"
    content_type = "image/png"

    def __init__(self, content: bytes):
        self._content = content
        self._offset = 0

    async def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._content) - self._offset
        chunk = self._content[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class FlowStrategyContractTests(unittest.TestCase):
    def test_strategy_contract_defaults_to_legacy(self) -> None:
        self.assertEqual(DEFAULT_FLOW_STRATEGY, "legacy")
        self.assertEqual(resolve_flow_strategy(None), "legacy")
        self.assertEqual(
            SUPPORTED_FLOW_STRATEGIES,
            ("legacy", "junction_aware_controlled"),
        )

    def test_unknown_strategy_is_rejected_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported flow strategy"):
            apply_flow_strategy(_architecture(), "experimental")

    def test_legacy_preserves_flows_and_input(self) -> None:
        payload = _architecture(structural=True)
        before = deepcopy(payload)

        result = apply_flow_strategy(payload, "legacy")

        self.assertEqual(payload, before)
        self.assertEqual(result["flows"], before["flows"])
        self.assertEqual(result["flowStrategy"], "legacy")
        self.assertFalse(result["flowStrategyTrace"]["structuralGate"]["executed"])

    def test_controlled_strategy_uses_winning_flags_without_endpoint_redirect(self) -> None:
        result = apply_flow_strategy(_architecture(), "junction_aware_controlled")
        trace = result["flowStrategyTrace"]

        self.assertEqual(trace["baseStrategy"], "full_without_endpoint_redirect")
        self.assertEqual(trace["moduleFlags"], CONTROLLED_MODULE_FLAGS)
        self.assertFalse(trace["endpointRedirectEnabled"])
        self.assertNotIn("redirect", trace["actionCounts"])
        self.assertGreaterEqual(trace["changedFlowCount"], 0)
        self.assertEqual(
            trace["executionOrder"],
            ["TL-004A", "TL-004B", "TL-004C", "TL-004D", "TL-004E", "TL-004F", "TL-STRUCT-001A"],
        )

    def test_structural_gate_blocks_only_with_complete_evidence(self) -> None:
        result = apply_flow_strategy(_architecture(structural=True), "junction_aware_controlled")

        self.assertEqual(result["flows"], [])
        self.assertEqual(result["flowStrategyTrace"]["structuralGate"]["blockedCount"], 1)
        self.assertEqual(result["flowStrategyTrace"]["actionCounts"], {"block": 1})

    def test_incomplete_structural_evidence_remains_review_only(self) -> None:
        payload = _architecture(structural=True)
        evidence = payload["flowStrategyContext"]["structuralEvidenceByCandidate"]["f1"]
        evidence["humanReview"]["confidence"] = "medium"

        result = apply_flow_strategy(payload, "junction_aware_controlled")

        self.assertEqual(len(result["flows"]), 1)
        self.assertEqual(result["flowStrategyTrace"]["structuralGate"]["blockedCount"], 0)
        self.assertEqual(result["flowStrategyTrace"]["actionCounts"], {"review_only": 1})

    def test_protected_candidate_is_never_blocked(self) -> None:
        payload = _architecture(structural=True)
        payload["flowStrategyContext"]["protectedCandidateIds"] = ["f1"]

        result = apply_flow_strategy(payload, "junction_aware_controlled")

        self.assertEqual(len(result["flows"]), 1)
        self.assertEqual(result["flowStrategyTrace"]["structuralGate"]["blockedCount"], 0)

    def test_controlled_strategy_is_deterministic_and_does_not_mutate_input(self) -> None:
        payload = _architecture(structural=True)
        before = deepcopy(payload)

        first = apply_flow_strategy(payload, "junction_aware_controlled")
        second = apply_flow_strategy(payload, "junction_aware_controlled")

        self.assertEqual(first, second)
        self.assertEqual(payload, before)
        self.assertEqual(first["flowStrategyTrace"]["newEdgeCount"], 0)

    def test_invalid_controlled_context_is_rejected(self) -> None:
        payload = _architecture()
        payload["flowStrategyContext"] = {"protectedEdges": [["source"]]}

        with self.assertRaisesRegex(ValueError, "protectedEdges"):
            apply_flow_strategy(payload, "junction_aware_controlled")


class FlowStrategyEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_json_runs_controlled_strategy_end_to_end(self) -> None:
        with (
            patch("backend.main.FLOW_STRATEGY", "junction_aware_controlled"),
            patch("backend.main._query_rag", return_value=[]),
            patch("backend.main._generate_and_validate", new=AsyncMock(side_effect=_report_from_analysis)),
        ):
            response = await analyze_json(_architecture(structural=True))

        self.assertEqual(response["architecture"]["flows"], [])
        self.assertEqual(response["pipeline"]["flowStrategy"], "junction_aware_controlled")
        self.assertEqual(response["pipeline"]["flowStrategyTrace"]["structuralGate"]["blockedCount"], 1)

    async def test_analyze_full_runs_controlled_strategy_end_to_end(self) -> None:
        with (
            patch("backend.main.FLOW_STRATEGY", "junction_aware_controlled"),
            patch("backend.main._query_rag", return_value=[]),
            patch("backend.main._generate_and_validate", new=AsyncMock(side_effect=_report_from_analysis)),
        ):
            response = await analyze_full(
                image=None,
                architecture_json=json.dumps(_architecture(structural=True)),
            )

        self.assertEqual(response["architecture"]["flows"], [])
        self.assertEqual(response["architecture"]["flowStrategy"], "junction_aware_controlled")

    async def test_analyze_image_returns_controlled_architecture(self) -> None:
        payload = _architecture(structural=True)
        with (
            patch("backend.main.FLOW_STRATEGY", "junction_aware_controlled"),
            patch("backend.main._detect_components", new=AsyncMock(return_value=deepcopy(payload))),
        ):
            response = await analyze_image_endpoint(_MemoryUpload(_png_bytes()))

        self.assertEqual(response["flows"], [])
        self.assertEqual(response["flowStrategy"], "junction_aware_controlled")

    async def test_legacy_remains_default_end_to_end(self) -> None:
        payload = _architecture(structural=True)
        with (
            patch("backend.main.FLOW_STRATEGY", "legacy"),
            patch("backend.main._query_rag", return_value=[]),
            patch("backend.main._generate_and_validate", new=AsyncMock(side_effect=_report_from_analysis)),
        ):
            response = await analyze_json(deepcopy(payload))

        self.assertEqual(response["architecture"]["flows"][0]["from"], "source")
        self.assertEqual(response["architecture"]["flows"][0]["to"], "target")
        self.assertEqual(response["pipeline"]["flowStrategy"], "legacy")

    async def test_invalid_configured_strategy_returns_422(self) -> None:
        with patch("backend.main.FLOW_STRATEGY", "invalid"):
            with self.assertRaises(HTTPException) as context:
                await analyze_json(_architecture())

        self.assertEqual(context.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
