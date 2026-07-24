import unittest

from scripts.evaluate_blind_end_to_end import apply_expected_provider, match_components, score_threats


class EndToEndBenchmarkTests(unittest.TestCase):
    def test_component_matching_requires_localization_and_reports_type(self):
        expected = [{"id": "api", "type": "api_gateway", "bbox": [0, 0, 100, 100]}]
        predicted = [{"id": "p1", "type": "compute", "bbox": [10, 10, 90, 90]}]

        result = match_components(expected, predicted)

        self.assertEqual(result["localized"], 1)
        self.assertEqual(result["typeCorrect"], 0)
        self.assertEqual(result["typedRecall"], 0)

    def test_threat_scoring_maps_predicted_component_ids(self):
        expected = [{
            "stride": "Spoofing", "title": "Identity risk", "componentId": "api"
        }]
        predicted = [
            {"stride": "Spoofing", "title": "Identity risk", "componentId": "p1"},
            {"stride": "Tampering", "title": "Extra", "componentId": "p1"},
        ]

        result = score_threats(expected, predicted, {"p1": "api"})

        self.assertEqual(result["correct"], 1)
        self.assertEqual(result["missing"], 0)
        self.assertEqual(result["extra"], 1)

    def test_expected_provider_keeps_external_actors_generic(self):
        components = [
            {"id": "user", "type": "user"},
            {"id": "api", "type": "api_gateway"},
            {"id": "db", "type": "database", "provider": "generic"},
        ]

        result = apply_expected_provider(components, "aws")

        self.assertEqual(result[0]["provider"], "generic")
        self.assertEqual(result[1]["provider"], "aws")
        self.assertEqual(result[2]["provider"], "generic")


if __name__ == "__main__":
    unittest.main()
