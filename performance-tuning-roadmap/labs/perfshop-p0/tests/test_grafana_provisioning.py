import json
from pathlib import Path
import unittest


LAB_ROOT = Path(__file__).resolve().parents[1]
PROVISIONING_ROOT = LAB_ROOT / "grafana/provisioning"
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

EXPECTED_PANEL_LAYOUT = {
    "Service Up": ({"h": 8, "w": 8, "x": 0, "y": 0}, "{{job}}"),
    "HTTP QPS": ({"h": 8, "w": 8, "x": 8, "y": 0}, "{{path}}"),
    "HTTP 5xx Rate": (
        {"h": 8, "w": 8, "x": 16, "y": 0},
        "{{path}}",
    ),
    "HTTP P95 Latency": (
        {"h": 8, "w": 12, "x": 0, "y": 8},
        "{{path}}",
    ),
    "HTTP P99 Latency": (
        {"h": 8, "w": 12, "x": 12, "y": 8},
        "{{path}}",
    ),
    "DB Query QPS": (
        {"h": 8, "w": 8, "x": 0, "y": 16},
        "{{query}}",
    ),
    "DB Average Latency": (
        {"h": 8, "w": 8, "x": 8, "y": 16},
        "{{query}}",
    ),
    "DB P95 Latency": (
        {"h": 8, "w": 8, "x": 16, "y": 16},
        "{{query}}",
    ),
    "App CPU Usage": ({"h": 8, "w": 8, "x": 0, "y": 24}, "app"),
    "App Resident Memory": (
        {"h": 8, "w": 8, "x": 8, "y": 24},
        "app",
    ),
    "Redis P95 Latency": (
        {"h": 8, "w": 8, "x": 16, "y": 24},
        "{{operation}}",
    ),
    "Downstream QPS": (
        {"h": 8, "w": 8, "x": 0, "y": 32},
        "{{target}} {{status}}",
    ),
    "Downstream Error Rate": (
        {"h": 8, "w": 8, "x": 8, "y": 32},
        "{{target}}",
    ),
    "Downstream Retry Rate": (
        {"h": 8, "w": 8, "x": 16, "y": 32},
        "{{target}}",
    ),
    "Downstream P95 Latency": (
        {"h": 8, "w": 24, "x": 0, "y": 40},
        "{{target}}",
    ),
}

EXPECTED_LEGEND_OPTIONS = {
    "calcs": [],
    "displayMode": "list",
    "placement": "bottom",
    "showLegend": True,
}


class GrafanaProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
        self.panel_list = self.dashboard["panels"]
        self.panels = {panel["title"]: panel for panel in self.panel_list}

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
        self.assertIn("allowUiUpdates: true", provider)
        self.assertNotIn("editable: true", provider)

    def test_optional_provisioning_directories_exist(self):
        for directory_name in ("plugins", "notifiers", "alerting"):
            with self.subTest(directory=directory_name):
                directory = PROVISIONING_ROOT / directory_name
                self.assertTrue(directory.is_dir())
                self.assertEqual(
                    (directory / "noop.yml").read_text(encoding="utf-8").strip(),
                    "apiVersion: 1",
                )

    def test_dashboard_identity_is_stable(self):
        expected_root_fields = {
            "uid": "perfshop-overview",
            "title": "PerfShop Overview",
            "schemaVersion": 39,
            "refresh": "5s",
            "tags": ["perfshop", "performance"],
            "time": {"from": "now-15m", "to": "now"},
            "timezone": "browser",
            "editable": True,
        }
        for field, expected_value in expected_root_fields.items():
            with self.subTest(field=field):
                self.assertEqual(self.dashboard[field], expected_value)

    def test_dashboard_has_exactly_15_uniquely_titled_panels(self):
        titles = [panel["title"] for panel in self.panel_list]
        self.assertEqual(len(self.panel_list), 15)
        self.assertEqual(len(titles), len(set(titles)))

    def test_dashboard_layout_and_legends_match_plan(self):
        self.assertEqual(set(self.panels), set(EXPECTED_PANEL_LAYOUT))
        for title, (expected_grid, expected_legend) in EXPECTED_PANEL_LAYOUT.items():
            with self.subTest(panel=title):
                panel = self.panels[title]
                self.assertEqual(panel["gridPos"], expected_grid)
                self.assertEqual(panel["options"]["legend"], EXPECTED_LEGEND_OPTIONS)
                self.assertEqual(
                    panel["targets"][0]["legendFormat"],
                    expected_legend,
                )

    def test_every_panel_target_uses_prometheus_datasource(self):
        for panel in self.panel_list:
            with self.subTest(panel=panel["title"]):
                self.assertEqual(panel["datasource"]["uid"], "prometheus")
                self.assertGreater(len(panel["targets"]), 0)
                for target in panel["targets"]:
                    self.assertEqual(target["datasource"]["uid"], "prometheus")

    def test_dashboard_contains_expected_queries(self):
        self.assertEqual(set(self.panels), set(EXPECTED_QUERIES))
        for title, expected_query in EXPECTED_QUERIES.items():
            with self.subTest(panel=title):
                panel = self.panels[title]
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

    def test_readme_contains_executable_monitoring_runbook(self):
        readme = (LAB_ROOT / "README.md").read_text(encoding="utf-8")
        runbook_heading = "## 6. 可执行监控与 Chaos Runbook"
        runbook_start = readme.index(runbook_heading)
        runbook_end = readme.index("\n## 7.", runbook_start)
        runbook = readme[runbook_start:runbook_end]
        required_snippets = [
            runbook_heading,
            "### 6.1 Prometheus Targets",
            "### 6.2 Baseline",
            "### 6.3 Slow DB",
            "### 6.4 CPU Hotspot",
            "### 6.5 Redis Big Key",
            "### 6.6 Redis Slow",
            "### 6.7 Downstream Timeout",
            "### 6.8 Retry Storm",
            "### 6.9 Reset",
            "docker compose restart grafana",
            "http://localhost:9090/api/v1/query",
            'query=up{job=~"perfshop-p0|perfshop-downstream"} == 1',
            '["perfshop-downstream", "perfshop-p0"]',
            "wrk -t2 -c20 -d60s",
            "/chaos/slow-db?enabled=true",
            "/chaos/cpu?duration=60",
            "/chaos/redis-big-key?enabled=true",
            "/chaos/redis-slow?enabled=true",
            "/chaos/downstream-delay?delay_ms=1000",
            "/chaos/retry-storm?enabled=true",
            "/chaos/reset",
            "PerfShop Overview",
            "Redis P95 Latency",
            "QPS/平均值面板可能很快恢复",
            "使用 `[5m]` 窗口的 P95/P99 面板",
            "等待约 5 分钟 washout",
            "washout 之后的时间区间",
        ]
        for snippet in required_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, runbook)


if __name__ == "__main__":
    unittest.main()
