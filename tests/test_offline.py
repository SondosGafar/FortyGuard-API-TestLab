"""Offline checks only; no credentials or API calls required."""
import unittest

from fortyguard_client import (
    ENDPOINTS, TOTAL_ESTIMATED_CREDITS, activity_id_from, activity_state,
    default_payload, sanitized_result,
)


class ClientContractTests(unittest.TestCase):
    def test_all_six_documented_analysis_services(self):
        self.assertEqual(len(ENDPOINTS), 6)
        self.assertEqual(TOTAL_ESTIMATED_CREDITS, 42220)
        for name in ENDPOINTS:
            self.assertTrue(default_payload(name))

    def test_temperature_units_are_endpoint_specific(self):
        self.assertAlmostEqual(default_payload("env_params")["temperature"], 27.7)
        self.assertAlmostEqual(default_payload("heat_intelligence")["temperature"], 81.86)

    def test_phoenix_polygon_is_closed(self):
        polygon = default_payload("heatmap")["polygon_aoi"]["features"][0]["geometry"]["coordinates"][0]
        self.assertEqual(polygon[0], polygon[-1])

    def test_activity_parsing(self):
        response = {"data": {"activity_id": "test-uuid", "status": "Completed"}}
        self.assertEqual(activity_id_from(response), "test-uuid")
        self.assertEqual(activity_state(response), "Completed")
        self.assertIsNone(activity_id_from({"error": True}))

    def test_sensitive_outputs_are_suppressed(self):
        response = {"data": {"result": {"download_link": "https://example.com/private?Signature=secret",
                                        "original_image": "AAAA", "map_data": {"type": "FeatureCollection", "features": [{"geometry": {"type": "Polygon"}}]},
                                        "stats_data": {"Temperature_stats": {"Mean": 20.5}}}}}
        safe = sanitized_result(response)["data"]["result"]
        self.assertEqual(safe["download_link"], "[REDACTED]")
        self.assertNotIn("AAAA", str(safe))
        self.assertEqual(safe["map_data"]["feature_count"], 1)
        self.assertEqual(safe["stats_data"]["Temperature_stats"]["Mean"], 20.5)

    def test_auth_header_or_secret_never_in_summary(self):
        body = {"api-key": "SECRET123", "details": {"password": "secret"}}
        safe = sanitized_result(body)
        self.assertEqual(safe["api-key"], "[REDACTED]")
        self.assertEqual(safe["details"]["password"], "[REDACTED]")


if __name__ == "__main__":
    unittest.main()
