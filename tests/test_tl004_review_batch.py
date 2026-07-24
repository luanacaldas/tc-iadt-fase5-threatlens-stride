from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.build_tl004_review_batch import (
    CONTROL_CASES,
    DEFAULT_BENCHMARK,
    DEFAULT_INVENTORY,
    DEFAULT_TEMPLATE,
    ERROR_CASES,
    ROOT,
    build_batch,
    load_sources,
    validate_selection,
)


class TL004ReviewSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.records, cls.entries = load_sources(DEFAULT_INVENTORY, DEFAULT_BENCHMARK)

    def test_initial_batch_has_required_error_and_control_counts(self) -> None:
        coverage = validate_selection(self.records, self.entries)

        self.assertEqual(coverage["errorCaseCount"], 14)
        self.assertEqual(coverage["controlCaseCount"], 4)
        self.assertEqual(coverage["totalCaseCount"], 18)
        self.assertGreaterEqual(coverage["topImageErrorCaseCount"], 7)

    def test_error_sample_contains_only_segment_graph_false_positives(self) -> None:
        for case in ERROR_CASES:
            with self.subTest(case=case["caseId"]):
                record = self.records[case["recordIds"][0]]
                self.assertEqual(record["status"], "false_positive")
                self.assertEqual(record["predictedFlow"]["evidence"], "segment_graph")

    def test_selection_is_unique_and_restricted_to_development_tuning(self) -> None:
        record_ids = [
            record_id
            for case in (*ERROR_CASES, *CONTROL_CASES)
            for record_id in case["recordIds"]
        ]

        self.assertEqual(len(record_ids), len(set(record_ids)))
        self.assertTrue(
            all(self.records[record_id]["imageId"] in self.entries for record_id in record_ids)
        )

    def test_selection_covers_required_junction_hypotheses_and_controls(self) -> None:
        coverage = validate_selection(self.records, self.entries)
        required = {
            "crossing",
            "component_passthrough",
            "transitive_shortcut",
            "incorrect_bifurcation",
            "parallel_connectors",
            "ambiguous_endpoint",
            "valid_fan_in",
            "valid_fan_out",
            "valid_junction",
        }

        self.assertTrue(required.issubset(set(coverage["coveredFocus"])))


class TL004ReviewBatchIntegrationTests(unittest.TestCase):
    def test_batch_builds_offline_review_with_blank_human_answers(self) -> None:
        temp_parent = ROOT / "data/results"
        with tempfile.TemporaryDirectory(dir=temp_parent) as temp_dir:
            output = Path(temp_dir) / "review-batch"

            result = build_batch(
                output,
                DEFAULT_INVENTORY,
                DEFAULT_BENCHMARK,
                DEFAULT_TEMPLATE,
            )

            manifest = json.loads((output / "review-manifest.json").read_text(encoding="utf-8"))
            page = (output / "index.html").read_text(encoding="utf-8")
            self.assertEqual(result["status"], "passed")
            self.assertEqual(manifest["split"], "development_tuning")
            self.assertEqual(len(manifest["cases"]), 18)
            self.assertNotIn("__BATCH_DATA__", page)
            self.assertIn("Exportar JSON", page)
            for case in manifest["cases"]:
                with self.subTest(case=case["caseId"]):
                    review = case["humanReview"]
                    self.assertIsNone(review["decision"])
                    self.assertIsNone(review["primaryCause"])
                    self.assertEqual(review["contributingCauses"], [])
                    crop = output / case["visualization"]
                    self.assertTrue(crop.is_file())
                    with Image.open(crop) as image:
                        self.assertGreater(image.width, 100)
                        self.assertGreater(image.height, 100)

    def test_review_page_has_download_feedback_and_copy_fallback(self) -> None:
        template = DEFAULT_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("Copiar JSON", template)
        self.assertIn("Enviar ao projeto", template)
        self.assertIn("Enviar revisao ao projeto", template)
        self.assertIn("assessment-submit-status", template)
        self.assertIn("Arquivo enviado para Downloads", template)
        self.assertIn("json-recovery-text", template)
        self.assertIn("navigator.clipboard.writeText", template)
        self.assertIn("/reviews/tl004", template)


if __name__ == "__main__":
    unittest.main()
