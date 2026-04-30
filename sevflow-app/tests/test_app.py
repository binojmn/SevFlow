import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app


class SevFlowAppTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_home(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["name"], "sevflow-app")
        self.assertEqual(payload["status"], "ok")

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "healthy"})

    def test_severity_endpoint(self):
        response = self.client.get("/api/severity")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("critical", payload["severityLevels"])

    def test_metrics_endpoint(self):
        self.client.get("/")
        self.client.get("/api/severity")

        response = self.client.get("/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.content_type)
        self.assertIn(b"sevflow_http_requests_total", response.data)
        self.assertIn(b"sevflow_http_requests_by_status_total", response.data)
        self.assertIn(b"sevflow_http_request_duration_seconds_bucket", response.data)
        self.assertIn(b"sevflow_domain_events_total", response.data)
        self.assertIn(b"sevflow_app_info", response.data)


if __name__ == "__main__":
    unittest.main()
