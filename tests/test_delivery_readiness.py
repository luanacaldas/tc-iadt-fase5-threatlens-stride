from __future__ import annotations

import unittest
import json
from pathlib import Path
from unittest.mock import patch

from backend.config import APP_VERSION
from backend.main import app, health
from scripts.smoke_test import (
    sample_analysis_snapshot,
    validate_full_analysis,
    validate_health,
    validate_image_analysis,
)
from scripts.build_delivery_readiness import (
    MANIFEST,
    PROTECTED_TL_FILES,
    compare_manifest,
    secret_scan,
)
from scripts.generate_sample_threat_model import build as build_sample_report


class DeliveryHealthContractTests(unittest.TestCase):
    def test_version_is_sourced_from_version_file(self) -> None:
        self.assertEqual(APP_VERSION, "1.0.0-mvp")
        self.assertEqual(app.version, APP_VERSION)

    def test_health_has_minimum_delivery_contract(self) -> None:
        with patch("backend.main.FLOW_STRATEGY", "legacy"):
            payload = health()

        self.assertEqual(
            {key: payload[key] for key in ("status", "version", "flowStrategy")},
            {"status": "ok", "version": "1.0.0-mvp", "flowStrategy": "legacy"},
        )
        self.assertEqual(payload["flowStrategies"]["default"], "legacy")
        self.assertIn("junction_aware_controlled", payload["flowStrategies"]["available"])

    def test_health_does_not_load_detector_or_rag(self) -> None:
        with (
            patch("backend.main.FLOW_STRATEGY", "legacy"),
            patch("backend.detector.status", side_effect=AssertionError("detector status called")),
            patch("backend.rag.status", side_effect=AssertionError("rag status called")),
        ):
            payload = health()

        self.assertEqual(payload["status"], "ok")

    def test_controlled_strategy_is_reported_only_when_explicit(self) -> None:
        with patch("backend.main.FLOW_STRATEGY", "junction_aware_controlled"):
            payload = health()

        self.assertEqual(payload["flowStrategy"], "junction_aware_controlled")


class DeliverySmokeContractTests(unittest.TestCase):
    def test_smoke_validators_accept_complete_payloads(self) -> None:
        health_checks = validate_health(
            {"status": "ok", "version": "1.0.0-mvp", "flowStrategy": "legacy"},
            "legacy",
        )
        image_checks = validate_image_analysis(
            {"components": [{"id": "api"}], "flows": [{"id": "f1"}], "flowStrategy": "legacy"},
            "legacy",
        )
        full_checks = validate_full_analysis(
            {
                "architecture": {"components": [{"id": "api"}], "flows": [{"id": "f1"}]},
                "threats": [{"countermeasures": ["Authenticate requests"]}],
                "pipeline": {"flowStrategy": "legacy", "flowStrategyTrace": {}},
            },
            "legacy",
        )

        self.assertTrue(all(check["passed"] for check in health_checks + image_checks + full_checks))

    def test_smoke_validators_fail_closed_on_missing_fields(self) -> None:
        checks = validate_health({}, "legacy") + validate_image_analysis({}, "legacy")
        checks += validate_full_analysis({}, "legacy")

        self.assertFalse(all(check["passed"] for check in checks))

    def test_smoke_snapshot_excludes_host_local_model_metadata(self) -> None:
        snapshot = sample_analysis_snapshot(
            {
                "architecture": {"components": [], "flows": []},
                "threats": [],
                "pipeline": {
                    "detectorUsed": "yolo",
                    "flowStrategy": "legacy",
                    "modelTrace": {"ocr": {"executable": "C:/local/tesseract.exe"}},
                },
            }
        )

        self.assertNotIn("modelTrace", snapshot["pipeline"])
        self.assertNotIn("C:/local", json.dumps(snapshot))


class DeliveryArtifactTests(unittest.TestCase):
    def test_registered_weight_is_included_in_git_and_docker_contracts(self) -> None:
        gitignore = Path(".gitignore").read_text(encoding="utf-8")
        dockerignore = Path(".dockerignore").read_text(encoding="utf-8")

        self.assertIn("!models/threatlens-hybrid-v2/weights/best.pt", gitignore)
        self.assertIn("!models/threatlens-hybrid-v2/**", dockerignore)

    def test_protected_tl_files_still_match_prior_manifest(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        result = compare_manifest(PROTECTED_TL_FILES, manifest)

        self.assertEqual(result["status"], "PASS")

    def test_delivery_sources_do_not_contain_recognized_secret_literals(self) -> None:
        self.assertEqual(secret_scan(), [])

    def test_sample_report_requires_and_renders_real_analysis(self) -> None:
        smoke = json.loads(
            Path("data/results/delivery-readiness/smoke-test-report.json").read_text(encoding="utf-8")
        )

        report = build_sample_report(smoke)

        self.assertIn("23", report)
        self.assertIn("`legacy`", report)
        self.assertIn("## Ameaças STRIDE", report)


if __name__ == "__main__":
    unittest.main()
