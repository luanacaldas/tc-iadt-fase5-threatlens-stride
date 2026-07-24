import json
import unittest
from pathlib import Path

from scripts.evaluate_stride_golden_set import evaluate_scenarios, score_rule_sets


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class StrideGoldenSetTests(unittest.TestCase):
    def test_rule_set_score_reports_false_positive_and_missing_rules(self):
        metrics = score_rule_sets(
            {"expected", "missing"},
            {"expected", "unexpected"},
        )

        self.assertEqual(metrics["truePositive"], ["expected"])
        self.assertEqual(metrics["falsePositive"], ["unexpected"])
        self.assertEqual(metrics["falseNegative"], ["missing"])
        self.assertFalse(metrics["exactMatch"])

    def test_golden_set_covers_and_passes_all_architecture_rules(self):
        golden_set = json.loads(
            (PROJECT_ROOT / "data/benchmarks/stride/golden-set.json").read_text(encoding="utf-8")
        )

        result = evaluate_scenarios(golden_set)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["aggregate"]["ruleCoverage"], 1.0)
        self.assertEqual(result["aggregate"]["exactMatchRate"], 1.0)
        self.assertEqual(result["aggregate"]["f1"], 1.0)


if __name__ == "__main__":
    unittest.main()
