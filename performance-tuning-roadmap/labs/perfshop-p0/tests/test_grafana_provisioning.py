import json
from pathlib import Path
import unittest


LAB_ROOT = Path(__file__).resolve().parents[1]
DATASOURCE_PATH = LAB_ROOT / "grafana/provisioning/datasources/datasources.yml"
PROVIDER_PATH = LAB_ROOT / "grafana/provisioning/dashboards/provider.yml"
DASHBOARD_PATH = LAB_ROOT / "grafana/provisioning/dashboards/perfshop-overview.json"


def compact(value):
    return " ".join(value.split())


EXPECTED_QUERIES = {
    "Service Up": 'up{job=~"prometheus|perfshop-p0|perfshop-downstream"}',
    "HTTP QPS": "sum by (path) (rate(http_requests_total[1m]))",
    "HTTP 5xx Rate": (
        'sum by (path) (rate(http_requests_total{status=~"5.."}[1m]))'
    ),
    "HTTP P95 Latency": (
        "histogram_quantile(0.95, "
        "sum by (le, path) (rate(http_request_duration_seconds_bucket[5m])))"
    ),
    "HTTP P99 Latency": (
        "histogram_quantile(0.99, "
        "sum by (le, path) (rate(http_request_duration_seconds_bucket[5m])))"
    ),
    "DB Query QPS": (
        "sum by (query) (rate(db_query_duration_seconds_count[1m]))"
    ),
    "DB Average Latency": (
        "sum by (query) (rate(db_query_duration_seconds_sum[1m])) / "
        "sum by (query) (rate(db_query_duration_seconds_count[1m]))"
    ),
    "DB P95 Latency": (
        "histogram_quantile(0.95, "
        "sum by (le, query) (rate(db_query_duration_seconds_bucket[5m])))"
    ),
    "App CPU Usage": (
        'rate(process_cpu_seconds_total{job="perfshop-p0"}[1m])'
    ),
    "App Resident Memory": (
        'process_resident_memory_bytes{job="perfshop-p0"}'
    ),
    "Redis P95 Latency": (
        "histogram_quantile(0.95, "
        "sum by (le, operation) "
        "(rate(redis_operation_duration_seconds_bucket[5m])))"
    ),
    "Downstream QPS": (
        "sum by (target, status) "
        "(rate(app_downstream_requests_total[1m]))"
    ),
    "Downstream Error Rate": (
        'sum by (target) '
        '(rate(app_downstream_requests_total{status="error"}[1m]))'
    ),
    "Downstream Retry Rate": (
        "sum by (target) (rate(app_downstream_retries_total[1m]))"
    ),
    "Downstream P95 Latency": (
        "histogram_quantile(0.95, "
        "sum by (le, target) "
        "(rate(app_downstream_request_duration_seconds_bucket[5m])))"
    ),
}


class GrafanaProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
        self.panels = {panel["title"]: panel for panel in self.dashboard["panels"]}

    def test_prometheus_datasource_has_stable_uid(self):
        datasource = DATASOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn("uid: prometheus", datasource)
        self.assertIn("url: http://prometheus:9090", datasource)

    def test_file_provider_points_at_dashboard_directory(self):
        provider = PROVIDER_PATH.read_text(encoding="utf-8")
        self.assertIn("name: PerfShop", provider)
        self.assertIn("folder: PerfShop", provider)
        self.assertIn("type: file", provider)
        self.assertIn("path: /etc/grafana/provisioning/dashboards", provider)

    def test_dashboard_identity_is_stable(self):
        self.assertEqual(self.dashboard["uid"], "perfshop-overview")
        self.assertEqual(self.dashboard["title"], "PerfShop Overview")
        self.assertEqual(self.dashboard["schemaVersion"], 39)

    def test_dashboard_contains_expected_queries(self):
        self.assertEqual(set(self.panels), set(EXPECTED_QUERIES))
        for title, expected_query in EXPECTED_QUERIES.items():
            with self.subTest(panel=title):
                panel = self.panels[title]
                self.assertEqual(panel["datasource"]["uid"], "prometheus")
                self.assertEqual(
                    compact(panel["targets"][0]["expr"]),
                    compact(expected_query),
                )

    def test_latency_panels_use_seconds_unit(self):
        latency_titles = {
            "HTTP P95 Latency",
            "HTTP P99 Latency",
            "DB Average Latency",
            "DB P95 Latency",
            "Redis P95 Latency",
            "Downstream P95 Latency",
        }
        for title in latency_titles:
            with self.subTest(panel=title):
                self.assertEqual(
                    self.panels[title]["fieldConfig"]["defaults"]["unit"],
                    "s",
                )


if __name__ == "__main__":
    unittest.main()
