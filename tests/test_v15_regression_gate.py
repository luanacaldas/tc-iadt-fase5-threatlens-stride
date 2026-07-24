from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_v15_regression import (
    ROOT,
    THRESHOLDS,
    build_checks,
    canonical_hash,
    load_baseline,
    metric_view,
    round_for_gate,
    run_gate,
)


def _aggregate(**overrides):
    payload = {
        "expected": 224,
        "predicted": 350,
        "correct": 152,
        "extra": 198,
        "precision": 0.4342857142857143,
        "recall": 0.6785714285714286,
        "f1": 0.5296167247386758,
    }
    payload.update(overrides)
    return payload


def _passing_inputs():
    return (
        metric_view(_aggregate()),
        {"testsRun": 85, "testFailures": 0},
        {"status": "passed", "checks": {}},
        {"status": "passed", "errors": []},
    )


class V15RegressionGateUnitTests(unittest.TestCase):
    def test_registered_baseline_is_intact_and_uses_development_split(self) -> None:
        baseline = load_baseline()

        self.assertEqual(baseline["split"], "development_tuning")
        self.assertEqual(metric_view(baseline["aggregate"])["f1Rounded"], THRESHOLDS["f1"])

    def test_gate_rounds_metrics_to_four_decimal_places(self) -> None:
        self.assertEqual(round_for_gate(0.5296167247386758), 0.5296)
        self.assertEqual(round_for_gate(0.6785714285714286), 0.6786)

    def test_canonical_hash_is_independent_from_dictionary_order(self) -> None:
        first = canonical_hash({"threshold": 0.5, "model": "best.pt"})
        second = canonical_hash({"model": "best.pt", "threshold": 0.5})

        self.assertEqual(first, second)

    def test_all_required_checks_pass_at_the_registered_limits(self) -> None:
        metrics, tests, prospective, real = _passing_inputs()

        checks = build_checks(metrics, tests, prospective, real, True, "development_tuning")

        self.assertTrue(all(check["passed"] for check in checks))

    def test_each_required_limit_fails_closed(self) -> None:
        cases = {
            "f1": (_aggregate(f1=0.52954), {"testsRun": 85, "testFailures": 0}, "f1"),
            "precision": (_aggregate(precision=0.43424), {"testsRun": 85, "testFailures": 0}, "precision"),
            "recall": (_aggregate(recall=0.67854), {"testsRun": 85, "testFailures": 0}, "recall"),
            "correctThreats": (_aggregate(correct=151), {"testsRun": 85, "testFailures": 0}, "correctThreats"),
            "falsePositives": (_aggregate(extra=199), {"testsRun": 85, "testFailures": 0}, "falsePositives"),
            "testsRun": (_aggregate(), {"testsRun": 84, "testFailures": 0}, "testsRun"),
            "testFailures": (_aggregate(), {"testsRun": 85, "testFailures": 1}, "testFailures"),
        }
        for label, (aggregate, tests, expected_failure) in cases.items():
            with self.subTest(label=label):
                checks = build_checks(
                    metric_view(aggregate),
                    tests,
                    {"status": "passed"},
                    {"status": "passed"},
                    True,
                    "development_tuning",
                )
                failed = {check["name"] for check in checks if not check["passed"]}
                self.assertIn(expected_failure, failed)

    def test_audit_and_split_failures_are_fail_closed(self) -> None:
        metrics, tests, _, _ = _passing_inputs()
        checks = build_checks(
            metrics,
            tests,
            {"status": "failed"},
            {"status": "failed"},
            True,
            "blind_holdout",
        )
        failed = {check["name"] for check in checks if not check["passed"]}

        self.assertEqual(
            failed,
            {"evaluationSplit", "prospectiveV12Integrity", "realBenchmarkIntegrity"},
        )

    def test_missing_metrics_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing"):
            metric_view({"f1": 0.6})


class V15RegressionGateIntegrationTests(unittest.TestCase):
    @staticmethod
    def _provenance(timestamp: str) -> dict:
        return {
            "pipelineRevision": "v15-semantic-arbitration",
            "datasetHash": "dataset-sha256",
            "configurationHash": "configuration-sha256",
            "modelHash": "model-sha256",
            "executionTimestamp": timestamp,
        }

    def test_gate_writes_passing_report_with_relative_artifact_paths(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as temp_dir:
            output = Path(temp_dir)

            def evaluator(output_dir: Path) -> dict:
                result = {
                    "split": "development_tuning",
                    "aggregate": _aggregate(),
                }
                (output_dir / "end-to-end-development_tuning.json").write_text(
                    json.dumps(result), encoding="utf-8"
                )
                return result

            report = run_gate(
                output,
                test_runner=lambda: {"testsRun": 85, "testFailures": 0},
                prospective_auditor=lambda: {"status": "passed", "checks": {}},
                real_auditor=lambda: {"status": "passed", "errors": []},
                evaluator=evaluator,
                provenance_collector=self._provenance,
            )

            persisted = json.loads((output / "gate-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "passed")
            self.assertEqual(persisted["status"], "passed")
            self.assertFalse(Path(persisted["candidate"]["source"]).is_absolute())
            self.assertTrue(all(check["passed"] for check in persisted["checks"]))

    def test_gate_persists_failure_when_evaluation_raises(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data/results") as temp_dir:
            output = Path(temp_dir)

            def failing_evaluator(_: Path) -> dict:
                raise RuntimeError("controlled evaluation failure")

            report = run_gate(
                output,
                test_runner=lambda: {"testsRun": 85, "testFailures": 0},
                prospective_auditor=lambda: {"status": "passed", "checks": {}},
                real_auditor=lambda: {"status": "passed", "errors": []},
                evaluator=failing_evaluator,
                provenance_collector=self._provenance,
            )

            persisted = json.loads((output / "gate-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "failed")
            self.assertEqual(persisted["status"], "failed")
            self.assertIn("developmentEvaluation", {item["stage"] for item in report["errors"]})
            self.assertFalse(next(check for check in report["checks"] if check["name"] == "f1")["passed"])


if __name__ == "__main__":
    unittest.main()
