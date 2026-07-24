import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.evaluate_real_architecture_benchmark import (
    components_in_image_coordinates,
    score_boundaries,
    score_protocols,
)


class RealArchitectureBenchmarkTests(unittest.TestCase):
    def test_boundary_matching_uses_member_jaccard(self):
        expected = [{"id": "zone", "componentIds": ["api", "db"]}]
        predicted = [
            {"id": "candidate", "componentIds": ["api", "db", "logs"]},
            {"id": "noise", "componentIds": ["user"]},
        ]

        metrics = score_boundaries(expected, predicted)

        self.assertEqual(metrics["truePositive"], 1)
        self.assertAlmostEqual(metrics["precision"], 0.5)
        self.assertEqual(metrics["recall"], 1.0)
        self.assertAlmostEqual(metrics["matches"][0]["memberJaccard"], 2 / 3)

    def test_protocol_score_requires_correct_flow_association(self):
        expected = [{"flowId": "f1", "value": "HTTPS"}]
        flows = [
            {"id": "f1", "protocol": "unknown"},
            {"id": "f2", "protocol": "HTTPS"},
        ]

        metrics = score_protocols(expected, flows)

        self.assertEqual(metrics["truePositive"], 0)
        self.assertEqual(metrics["falsePositive"], [["f2", "https"]])
        self.assertEqual(metrics["falseNegative"], [["f1", "https"]])

    def test_preview_coordinates_are_scaled_to_original_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "diagram.png"
            Image.new("RGB", (400, 200), "white").save(image_path)
            entry = {
                "id": "scaled-preview",
                "annotationSize": [200, 100],
                "components": [{"id": "api", "bbox": [10, 20, 50, 60]}],
            }

            components = components_in_image_coordinates(entry, image_path)

            self.assertEqual(components[0]["bbox"], [20, 40, 100, 120])
            self.assertEqual(entry["components"][0]["bbox"], [10, 20, 50, 60])


if __name__ == "__main__":
    unittest.main()
