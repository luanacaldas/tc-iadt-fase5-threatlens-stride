from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_structure_benchmark import build_benchmark
from scripts.evaluate_structure_benchmark import score_flows


class StructureBenchmarkTests(unittest.TestCase):
    def test_reversed_edge_keeps_adjacency_but_fails_direction(self) -> None:
        expected = [{"from": "internet", "to": "api"}]
        predicted = [{"from": "api", "to": "internet"}]

        metrics = score_flows(expected, predicted)

        self.assertEqual(metrics["undirectedF1"], 1.0)
        self.assertEqual(metrics["directedF1"], 0.0)
        self.assertEqual(metrics["directionAccuracyOnMatchedEdges"], 0.0)
        self.assertEqual(metrics["reversedEdges"], [["internet", "api"]])

    def test_false_and_missing_edges_are_reported(self) -> None:
        expected = [
            {"from": "user", "to": "api"},
            {"from": "api", "to": "db"},
        ]
        predicted = [
            {"from": "user", "to": "api"},
            {"from": "api", "to": "queue"},
        ]

        metrics = score_flows(expected, predicted)

        self.assertEqual(metrics["undirectedPrecision"], 0.5)
        self.assertEqual(metrics["undirectedRecall"], 0.5)
        self.assertEqual(metrics["falsePositiveEdges"], [["api", "queue"]])
        self.assertEqual(metrics["missedEdges"], [["api", "db"]])

    def test_reserved_images_match_reconstructed_seed_ground_truth(self) -> None:
        image_dir = Path("dataset/hybrid_v2/images/test")
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "benchmark.json"

            benchmark = build_benchmark(image_dir, output)

        self.assertEqual(benchmark["imageCount"], 30)
        self.assertGreater(benchmark["flowCount"], 100)
        self.assertTrue(all(entry["flows"] for entry in benchmark["entries"]))


if __name__ == "__main__":
    unittest.main()
