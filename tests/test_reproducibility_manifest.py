from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.audit_real_benchmark_integrity import audit
from scripts.build_reproducibility_manifest import TRACKED, build
from scripts.verify_project import verify_hashes


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "data/benchmarks/real-architecture/benchmark-expanded.json"
ACTIVE_MANIFEST = ROOT / "dataset/active_learning_real_v1/active-learning-manifest.json"


def _json_hash(payload: dict) -> str:
    content = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


class ReproducibilityManifestTests(unittest.TestCase):
    def test_real_audit_is_deterministic_and_contains_only_relative_paths(self) -> None:
        first = audit(BENCHMARK, ACTIVE_MANIFEST)
        second = audit(BENCHMARK, ACTIVE_MANIFEST)

        self.assertEqual(first, second)
        self.assertEqual(_json_hash(first), _json_hash(second))
        self.assertNotIn("auditedAt", first)
        self.assertEqual(
            first["benchmark"],
            "data/benchmarks/real-architecture/benchmark-expanded.json",
        )
        self.assertFalse(Path(first["benchmark"]).is_absolute())

    def test_semantic_audit_change_still_changes_hash(self) -> None:
        original = audit(BENCHMARK, ACTIVE_MANIFEST)
        changed = deepcopy(original)
        changed["imageCount"] += 1

        self.assertNotEqual(_json_hash(original), _json_hash(changed))

    def test_manifest_build_is_deterministic_and_does_not_lose_coverage(self) -> None:
        first = build()
        second = build()

        self.assertEqual(first, second)
        self.assertEqual(_json_hash(first), _json_hash(second))
        self.assertNotIn("generatedAt", first)
        self.assertGreaterEqual(len(TRACKED), 108)
        self.assertEqual(first["offlineFlags"]["FLOW_STRATEGY"], "legacy")
        for relative in (
            "scripts/audit_real_benchmark_integrity.py",
            "scripts/build_reproducibility_manifest.py",
            "scripts/verify_project.py",
            "tests/test_reproducibility_manifest.py",
            "backend/geometric_events.py",
            "backend/endpoint_validation.py",
            "backend/intersection_validation.py",
            "backend/shared_trunk_reconstruction.py",
            "backend/transitive_shortcut_validation.py",
            "backend/integrated_junction_strategy.py",
            "backend/structural_line_gate.py",
            "backend/flow_strategy.py",
            "scripts/build_tl004b_artifacts.py",
            "scripts/build_tl004c_artifacts.py",
            "scripts/build_tl004d_artifacts.py",
            "scripts/build_tl004e_artifacts.py",
            "scripts/build_tl004f_artifacts.py",
            "scripts/build_tl_struct_001a_artifacts.py",
            "tests/test_endpoint_validation.py",
            "tests/test_intersection_validation.py",
            "tests/test_shared_trunk_reconstruction.py",
            "tests/test_transitive_shortcut_validation.py",
            "tests/test_integrated_junction_strategy.py",
            "tests/test_structural_line_gate.py",
            "tests/test_flow_strategy_promotion.py",
            "tests/fixtures/tl004a_geometric_events.json",
            "tests/fixtures/tl004c_intersections.json",
            "tests/fixtures/tl004d_shared_trunks.json",
            "tests/fixtures/tl004e_transitive_shortcuts.json",
            "tests/fixtures/tl004f_integration.json",
            "tests/fixtures/tl_struct_001a.json",
            "data/fixtures/tl004d_c04_shared_trunk.json",
        ):
            self.assertIn(relative, TRACKED)
            self.assertIn(relative, first["files"])

    def test_verifier_detects_missing_semantic_and_unexpected_hash_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tracked = root / "tracked.json"
            tracked.write_text('{"status":"passed"}', encoding="utf-8")
            expected = {
                "sha256": hashlib.sha256(tracked.read_bytes()).hexdigest(),
                "bytes": tracked.stat().st_size,
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps({"files": {"tracked.json": expected}}),
                encoding="utf-8",
            )

            verify_hashes(manifest_path, root)

            tracked.write_text('{"status":"failed"}', encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "tracked.json"):
                verify_hashes(manifest_path, root)

            tracked.unlink()
            with self.assertRaisesRegex(RuntimeError, "tracked.json"):
                verify_hashes(manifest_path, root)

            tracked.write_text('{"status":"passed"}', encoding="utf-8")
            unexpected = deepcopy(expected)
            unexpected["sha256"] = "0" * 64
            manifest_path.write_text(
                json.dumps({"files": {"tracked.json": unexpected}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "tracked.json"):
                verify_hashes(manifest_path, root)


if __name__ == "__main__":
    unittest.main()
