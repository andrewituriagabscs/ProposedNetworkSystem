"""Unit tests for separated web navigation routes and modular API endpoints."""

import os
import unittest

os.environ["TESTING"] = "1"
from app import create_app


class RouteNavigationTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_root_redirects_to_dashboard(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/dashboard", response.headers["Location"])

    def test_dashboard_route_renders_dashboard_panel_active(self):
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-panel="dashboard"', html)
        self.assertIn('href="/ping"', html)
        self.assertIn('href="/dashboard"', html)

    def test_ping_route_renders_ping_panel_active(self):
        response = self.client.get("/ping")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-panel="ping"', html)
        # Verify ping nav link is marked active on /ping route
        self.assertIn('class="nav-item active" href="/ping"', html)

    def test_monitor_redirects_to_ping(self):
        response = self.client.get("/monitor")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/ping", response.headers["Location"])

    def test_alerts_route_renders_alerts_panel(self):
        response = self.client.get("/alerts")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-panel="alerts"', html)
        self.assertIn('class="nav-item active" href="/alerts"', html)

    def test_records_route_renders_records_panel(self):
        response = self.client.get("/records")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-panel="records"', html)
        self.assertIn('class="nav-item active" href="/records"', html)

    def test_reports_and_ping_records_aliases_redirect_to_records(self):
        for path in ("/reports", "/ping-records"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/records", response.headers["Location"])

    def test_ml_insights_route_renders_ml_insights_panel(self):
        response = self.client.get("/ml-insights")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-panel="ml-insights"', html)
        self.assertIn('class="nav-item active" href="/ml-insights"', html)

    def test_settings_route_renders_settings_panel(self):
        response = self.client.get("/settings")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-panel="settings"', html)
        self.assertIn('class="nav-item active" href="/settings"', html)

    def test_about_route_renders_about_panel(self):
        response = self.client.get("/about")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-panel="about"', html)
        self.assertIn('class="nav-item active" href="/about"', html)

    def test_static_assets_serve_correctly(self):
        for path in (
            "/style.css",
            "/static/css/style.css",
            "/static/js/api.js",
            "/static/js/router.js",
            "/static/js/devices.js",
            "/static/js/ping_chart.js",
            "/static/js/records_alerts.js",
            "/static/js/ml.js",
            "/static/js/settings.js",
            "/static/js/app.js",
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, f"Failed to serve {path}")

    def test_api_endpoints_are_functional(self):
        status_res = self.client.get("/api/status")
        self.assertEqual(status_res.status_code, 200)
        self.assertIn("devices", status_res.get_json())

        devices_res = self.client.get("/api/devices")
        self.assertEqual(devices_res.status_code, 200)
        self.assertIn("devices", devices_res.get_json())

        ml_res = self.client.get("/api/ml/status")
        self.assertEqual(ml_res.status_code, 200)
        self.assertIn("models", ml_res.get_json())

        bldg_res = self.client.get("/api/settings/building-name")
        self.assertEqual(bldg_res.status_code, 200)
        self.assertIn("building_name", bldg_res.get_json())


if __name__ == "__main__":
    unittest.main()
