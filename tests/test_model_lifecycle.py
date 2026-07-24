from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_model import CRITICAL_CLASSES, build_quality_gate
from scripts.register_model import build_source_gate, register_model


class QualityGateTests(unittest.TestCase):
    def test_gate_requires_aggregate_and_critical_classes(self) -> None:
        aggregate = {"map50": 0.60, "recall": 0.55}
        per_class = [{"name": name, "map50": 0.40} for name in CRITICAL_CLASSES]

        gate = build_quality_gate(aggregate, per_class, 0.25, 0.25, 0.10)

        self.assertTrue(gate["passed"])
        self.assertTrue(all(check["passed"] for check in gate["checks"]))

    def test_gate_fails_when_critical_class_is_missing(self) -> None:
        aggregate = {"map50": 0.60, "recall": 0.55}
        per_class = [
            {"name": name, "map50": 0.40}
            for name in CRITICAL_CLASSES
            if name != "internet"
        ]

        gate = build_quality_gate(aggregate, per_class, 0.25, 0.25, 0.10)

        self.assertFalse(gate["passed"])

    def test_source_gate_requires_real_domain_performance(self) -> None:
        comparison = {
            "sources": [
                {
                    "source": "kaggle_unique",
                    "aggregate": {"map50": 0.42, "recall": 0.31},
                }
            ]
        }

        gate = build_source_gate(comparison)

        self.assertTrue(gate["passed"])

    def test_source_gate_rejects_weak_real_domain_recall(self) -> None:
        comparison = {
            "sources": [
                {
                    "source": "kaggle_unique",
                    "aggregate": {"map50": 0.42, "recall": 0.10},
                }
            ]
        }

        gate = build_source_gate(comparison)

        self.assertFalse(gate["passed"])


class ModelRegistrationTests(unittest.TestCase):
    @staticmethod
    def _evaluation(root: Path, passed: bool) -> Path:
        model = root / "candidate.pt"
        model.write_bytes(b"qualified-model")
        digest = hashlib.sha256(model.read_bytes()).hexdigest()
        evaluation = {
            "model": {"path": str(model), "sha256": digest},
            "dataset": {"yaml": "dataset.yaml", "split": "test"},
            "settings": {"imgsz": 416},
            "aggregate": {"map50": 0.5, "recall": 0.5},
            "qualityGate": {"passed": passed, "checks": []},
        }
        path = root / "evaluation.json"
        path.write_text(json.dumps(evaluation), encoding="utf-8")
        return path

    def test_registration_verifies_and_copies_qualified_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            evaluation = self._evaluation(root, True)
            target = root / "registry" / "weights" / "best.pt"

            card = register_model(evaluation, target)

            self.assertEqual(card["status"], "qualified")
            self.assertTrue(target.exists())
            self.assertTrue((root / "registry" / "model-card.json").exists())

    def test_registration_refuses_failed_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            evaluation = self._evaluation(root, False)

            with self.assertRaisesRegex(RuntimeError, "Quality gate failed"):
                register_model(evaluation, root / "registry" / "weights" / "best.pt")


if __name__ == "__main__":
    unittest.main()
