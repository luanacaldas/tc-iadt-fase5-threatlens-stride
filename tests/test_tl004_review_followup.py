from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.analyze_tl004_review import (
    DEFAULT_MANIFEST,
    DEFAULT_RESULT,
    analyze_review,
    validate_review,
)
from scripts.build_tl004_review_batch import DEFAULT_BENCHMARK, DEFAULT_INVENTORY, ROOT, load_sources
from scripts.build_tl004_review_followup import (
    CONTROL_CASES,
    DEFAULT_PREVIOUS_ANALYSIS,
    DEFAULT_PREVIOUS_MANIFEST,
    DEFAULT_PREVIOUS_RESULT,
    ERROR_CASES,
    build_batch,
    validate_selection,
)


class TL004CompletedReviewTests(unittest.TestCase):
    def test_completed_review_is_valid_and_requires_confirmation_batch(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as temp_dir:
            output = Path(temp_dir)
            analysis = analyze_review(
                DEFAULT_MANIFEST,
                DEFAULT_RESULT,
                output / "analysis.json",
                output / "analysis.md",
            )

            self.assertEqual(analysis["completion"]["completedCaseCount"], 18)
            self.assertEqual(analysis["quality"]["falsePositivesConfirmed"], 14)
            self.assertEqual(analysis["quality"]["controlsValidated"], 4)
            self.assertEqual(analysis["quality"]["decisionMismatchCaseIds"], [])
            self.assertEqual(analysis["quality"]["ambiguousCaseIds"], [])
            self.assertEqual(analysis["quality"]["caseLevelNewCategories"], [])
            self.assertEqual(
                analysis["nextStepDecision"]["action"], "generate_batch_02"
            )
            self.assertTrue(
                analysis["nextStepDecision"]["triggerChecks"]["coverageGapsDeclared"]
            )
            self.assertTrue((output / "analysis.json").is_file())
            self.assertTrue((output / "analysis.md").is_file())

    def test_incomplete_review_fails_closed(self) -> None:
        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        result = json.loads(DEFAULT_RESULT.read_text(encoding="utf-8"))
        incomplete = copy.deepcopy(result)
        incomplete["responses"] = incomplete["responses"][:-1]

        with self.assertRaises(ValueError):
            validate_review(manifest, incomplete)


class TL004FollowupSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.records, cls.entries = load_sources(DEFAULT_INVENTORY, DEFAULT_BENCHMARK)
        cls.previous_manifest = json.loads(
            DEFAULT_PREVIOUS_MANIFEST.read_text(encoding="utf-8")
        )
        cls.previous_result = json.loads(
            DEFAULT_PREVIOUS_RESULT.read_text(encoding="utf-8")
        )
        cls.previous_analysis = json.loads(
            DEFAULT_PREVIOUS_ANALYSIS.read_text(encoding="utf-8")
        )

    def test_followup_has_nine_cases_and_required_focus(self) -> None:
        coverage = validate_selection(
            self.records,
            self.entries,
            self.previous_manifest,
            self.previous_result,
            self.previous_analysis,
        )

        self.assertEqual(coverage["errorCaseCount"], 6)
        self.assertEqual(coverage["controlCaseCount"], 3)
        self.assertEqual(coverage["totalCaseCount"], 9)
        self.assertGreaterEqual(coverage["highDensityCaseCount"], 5)
        self.assertEqual(coverage["previousRecordOverlapCount"], 0)

    def test_errors_are_segment_graph_false_positives_and_controls_are_valid(self) -> None:
        for spec in ERROR_CASES:
            record = self.records[spec["recordIds"][0]]
            self.assertEqual(record["status"], "false_positive")
            self.assertEqual(record["predictedFlow"]["evidence"], "segment_graph")
        for spec in CONTROL_CASES:
            for record_id in spec["recordIds"]:
                self.assertEqual(self.records[record_id]["status"], "true_positive")

    def test_followup_does_not_reuse_batch_01_records(self) -> None:
        previous_ids = {
            record["inventoryId"]
            for case in self.previous_manifest["cases"]
            for record in case["records"]
        }
        followup_ids = {
            record_id
            for spec in (*ERROR_CASES, *CONTROL_CASES)
            for record_id in spec["recordIds"]
        }
        self.assertFalse(previous_ids.intersection(followup_ids))


class TL004FollowupIntegrationTests(unittest.TestCase):
    def test_followup_builds_offline_review_with_blank_answers(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as temp_dir:
            output = Path(temp_dir) / "batch-02"
            result = build_batch(output)
            manifest = json.loads(
                (output / "review-manifest.json").read_text(encoding="utf-8")
            )

            self.assertEqual(result["status"], "passed")
            self.assertEqual(manifest["split"], "development_tuning")
            self.assertEqual(len(manifest["cases"]), 9)
            self.assertEqual(
                manifest["selectionPolicy"]["type"], "stratified_confirmation_batch"
            )
            for case in manifest["cases"]:
                self.assertIsNone(case["humanReview"]["decision"])
                crop = output / case["visualization"]
                self.assertTrue(crop.is_file())
                with Image.open(crop) as image:
                    self.assertGreater(image.width, 100)
                    self.assertGreater(image.height, 100)


if __name__ == "__main__":
    unittest.main()
