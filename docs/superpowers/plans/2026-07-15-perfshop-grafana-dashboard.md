# PerfShop Grafana Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provision a version-controlled PerfShop Grafana dashboard automatically and document copyable baseline and chaos-test commands.

**Architecture:** Grafana's file provider loads one static dashboard JSON from the already-mounted provisioning directory. A stable Prometheus datasource UID connects every panel without UI setup. Standard-library unit tests validate provider wiring, dashboard identity, panel queries, and README runbook commands without requiring running containers.

**Tech Stack:** Grafana 10.4 provisioning, Prometheus/PromQL, Docker Compose, JSON, YAML, Python `unittest`, Markdown

## Global Constraints

- Reuse the existing `./grafana/provisioning:/etc/grafana/provisioning:ro` Compose volume.
- Do not add application metrics, alert rules, Loki, tracing, Kubernetes, exporters, or Grafana API deployment.
- Use stable datasource UID `prometheus` and dashboard UID `perfshop-overview`.
- Use only metrics already exposed by PerfShop App and Downstream.
- Display latency using Grafana's seconds unit so sub-second values render as milliseconds without changing Prometheus values.
- Keep Dashboard editable in Grafana, but repository JSON remains source of truth after restart.
- Preserve unrelated working-tree changes.

---

## File Structure

- Create `performance-tuning-roadmap/labs/perfshop-p0/tests/test_grafana_provisioning.py`: standard-library contract tests for provisioning, dashboard panels, and README commands.
- Modify `performance-tuning-roadmap/labs/perfshop-p0/grafana/provisioning/datasources/datasources.yml`: assign stable Prometheus UID.
- Create `performance-tuning-roadmap/labs/perfshop-p0/grafana/provisioning/dashboards/provider.yml`: file-provider configuration.
- Create `performance-tuning-roadmap/labs/perfshop-p0/grafana/provisioning/dashboards/perfshop-overview.json`: provisioned dashboard.
- Modify `performance-tuning-roadmap/labs/perfshop-p0/README.md`: runnable monitoring and chaos runbook.

---

### Task 1: Provision and Contract-Test the Grafana Dashboard

**Files:**

- Create: `performance-tuning-roadmap/labs/perfshop-p0/tests/test_grafana_provisioning.py`
- Modify: `performance-tuning-roadmap/labs/perfshop-p0/grafana/provisioning/datasources/datasources.yml`
- Create: `performance-tuning-roadmap/labs/perfshop-p0/grafana/provisioning/dashboards/provider.yml`
- Create: `performance-tuning-roadmap/labs/perfshop-p0/grafana/provisioning/dashboards/perfshop-overview.json`

**Interfaces:**

- Consumes: existing Prometheus URL `http://prometheus:9090` and existing metrics from App and Downstream `/metrics` endpoints.
- Produces: datasource UID `prometheus`, dashboard UID `perfshop-overview`, Grafana folder `PerfShop`, and named panels validated by tests.

- [ ] **Step 1: Write the failing provisioning contract test**

Create `tests/test_grafana_provisioning.py`:

```python
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
```

- [ ] **Step 2: Run test and verify it fails because dashboard files do not exist**

Run from `performance-tuning-roadmap/labs/perfshop-p0`:

```bash
python -m unittest discover -s tests -p 'test_grafana_provisioning.py' -v
```

Expected: `ERROR` with `FileNotFoundError` for `perfshop-overview.json`.

- [ ] **Step 3: Add stable datasource UID and dashboard provider**

Modify `grafana/provisioning/datasources/datasources.yml` to:

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    uid: prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

Create `grafana/provisioning/dashboards/provider.yml`:

```yaml
apiVersion: 1

providers:
  - name: PerfShop
    orgId: 1
    folder: PerfShop
    type: file
    disableDeletion: false
    editable: true
    updateIntervalSeconds: 10
    options:
      path: /etc/grafana/provisioning/dashboards
```

- [ ] **Step 4: Create dashboard JSON with exact panel contracts**

Create `grafana/provisioning/dashboards/perfshop-overview.json`. Every panel must contain these fixed fields:

- `datasource`: `{"type": "prometheus", "uid": "prometheus"}`
- `fieldConfig.overrides`: `[]`
- `fieldConfig.defaults.unit`: the unit from the matrix below
- `gridPos`: the exact `x`, `y`, `w`, and `h` values from the matrix
- `id`: the numeric ID from the matrix
- `options.legend`: `{"calcs": [], "displayMode": "list", "placement": "bottom", "showLegend": true}`
- `options.tooltip`: `{"mode": "multi", "sort": "desc"}`
- one target with datasource UID `prometheus`, `editorMode` `code`, the exact matrix PromQL, the exact matrix legend, `range` `true`, and `refId` `A`
- `title`: the exact matrix title
- `type`: `timeseries`

The first panel is fully represented as:

```json
{
  "datasource": {"type": "prometheus", "uid": "prometheus"},
  "fieldConfig": {
    "defaults": {"unit": "short"},
    "overrides": []
  },
  "gridPos": {"h": 8, "w": 8, "x": 0, "y": 0},
  "id": 1,
  "options": {
    "legend": {
      "calcs": [],
      "displayMode": "list",
      "placement": "bottom",
      "showLegend": true
    },
    "tooltip": {"mode": "multi", "sort": "desc"}
  },
  "targets": [
    {
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "editorMode": "code",
      "expr": "up{job=~\"prometheus|perfshop-p0|perfshop-downstream\"}",
      "legendFormat": "{{job}}",
      "range": true,
      "refId": "A"
    }
  ],
  "title": "Service Up",
  "type": "timeseries"
}
```

Create exactly these 15 panels. IDs and grid positions are fixed so layout stays deterministic:

| ID | Title | Unit | Legend | Grid `(x,y,w,h)` | PromQL |
|---:|---|---|---|---|---|
| 1 | Service Up | `short` | `{{job}}` | `0,0,8,8` | `up{job=~"prometheus\|perfshop-p0\|perfshop-downstream"}` |
| 2 | HTTP QPS | `reqps` | `{{path}}` | `8,0,8,8` | `sum by (path) (rate(http_requests_total[1m]))` |
| 3 | HTTP 5xx Rate | `reqps` | `{{path}}` | `16,0,8,8` | `sum by (path) (rate(http_requests_total{status=~"5.."}[1m]))` |
| 4 | HTTP P95 Latency | `s` | `{{path}}` | `0,8,12,8` | `histogram_quantile(0.95, sum by (le, path) (rate(http_request_duration_seconds_bucket[5m])))` |
| 5 | HTTP P99 Latency | `s` | `{{path}}` | `12,8,12,8` | `histogram_quantile(0.99, sum by (le, path) (rate(http_request_duration_seconds_bucket[5m])))` |
| 6 | DB Query QPS | `ops` | `{{query}}` | `0,16,8,8` | `sum by (query) (rate(db_query_duration_seconds_count[1m]))` |
| 7 | DB Average Latency | `s` | `{{query}}` | `8,16,8,8` | `sum by (query) (rate(db_query_duration_seconds_sum[1m])) / sum by (query) (rate(db_query_duration_seconds_count[1m]))` |
| 8 | DB P95 Latency | `s` | `{{query}}` | `16,16,8,8` | `histogram_quantile(0.95, sum by (le, query) (rate(db_query_duration_seconds_bucket[5m])))` |
| 9 | App CPU Usage | `cores` | `app` | `0,24,8,8` | `rate(process_cpu_seconds_total{job="perfshop-p0"}[1m])` |
| 10 | App Resident Memory | `bytes` | `app` | `8,24,8,8` | `process_resident_memory_bytes{job="perfshop-p0"}` |
| 11 | Redis P95 Latency | `s` | `{{operation}}` | `16,24,8,8` | `histogram_quantile(0.95, sum by (le, operation) (rate(redis_operation_duration_seconds_bucket[5m])))` |
| 12 | Downstream QPS | `reqps` | `{{target}} {{status}}` | `0,32,8,8` | `sum by (target, status) (rate(app_downstream_requests_total[1m]))` |
| 13 | Downstream Error Rate | `reqps` | `{{target}}` | `8,32,8,8` | `sum by (target) (rate(app_downstream_requests_total{status="error"}[1m]))` |
| 14 | Downstream Retry Rate | `reqps` | `{{target}}` | `16,32,8,8` | `sum by (target) (rate(app_downstream_retries_total[1m]))` |
| 15 | Downstream P95 Latency | `s` | `{{target}}` | `0,40,24,8` | `histogram_quantile(0.95, sum by (le, target) (rate(app_downstream_request_duration_seconds_bucket[5m])))` |

The root object must contain the 15 panel objects plus these exact fields:

```text
annotations = {"list": []}
editable = true
fiscalYearStartMonth = 0
graphTooltip = 1
id = null
links = []
liveNow = false
refresh = "5s"
schemaVersion = 39
tags = ["perfshop", "performance"]
templating = {"list": []}
time = {"from": "now-15m", "to": "now"}
timepicker = {}
timezone = "browser"
title = "PerfShop Overview"
uid = "perfshop-overview"
version = 1
weekStart = ""
```

- [ ] **Step 5: Validate JSON and run the provisioning contract test**

Run:

```bash
python -m json.tool grafana/provisioning/dashboards/perfshop-overview.json >/dev/null
python -m unittest discover -s tests -p 'test_grafana_provisioning.py' -v
```

Expected: JSON command exits `0`; five tests pass.

- [ ] **Step 6: Run existing lab unit tests**

Run:

```bash
python -m unittest discover -s tests -v
```

Expected: all existing and new tests pass.

- [ ] **Step 7: Commit dashboard provisioning**

```bash
git add \
  performance-tuning-roadmap/labs/perfshop-p0/tests/test_grafana_provisioning.py \
  performance-tuning-roadmap/labs/perfshop-p0/grafana/provisioning/datasources/datasources.yml \
  performance-tuning-roadmap/labs/perfshop-p0/grafana/provisioning/dashboards/provider.yml \
  performance-tuning-roadmap/labs/perfshop-p0/grafana/provisioning/dashboards/perfshop-overview.json
git commit -m "feat(perfshop): provision Grafana dashboard"
```

---

### Task 2: Add an Executable Monitoring and Chaos Runbook

**Files:**

- Modify: `performance-tuning-roadmap/labs/perfshop-p0/tests/test_grafana_provisioning.py`
- Modify: `performance-tuning-roadmap/labs/perfshop-p0/README.md`

**Interfaces:**

- Consumes: dashboard panel titles and chaos endpoints from Task 1 and existing App routes.
- Produces: README section `## 6. 可执行监控与 Chaos Runbook` containing commands runnable from the `perfshop-p0` directory.

- [ ] **Step 1: Add failing README runbook contract test**

Append to `GrafanaProvisioningTests` in `tests/test_grafana_provisioning.py`:

```python
    def test_readme_contains_executable_monitoring_runbook(self):
        readme = (LAB_ROOT / "README.md").read_text(encoding="utf-8")
        required_snippets = [
            "## 6. 可执行监控与 Chaos Runbook",
            "docker compose restart grafana",
            "wrk -t2 -c20 -d60s",
            "/chaos/slow-db?enabled=true",
            "/chaos/cpu?duration=60",
            "/chaos/redis-slow?enabled=true",
            "/chaos/downstream-delay?delay_ms=1000",
            "/chaos/retry-storm?enabled=true",
            "/chaos/reset",
            "PerfShop Overview",
        ]
        for snippet in required_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, readme)
```

- [ ] **Step 2: Run focused test and verify it fails**

Run:

```bash
python -m unittest \
  tests.test_grafana_provisioning.GrafanaProvisioningTests.test_readme_contains_executable_monitoring_runbook \
  -v
```

Expected: `FAIL` because README lacks the new heading and executable commands.

- [ ] **Step 3: Add the runbook before current `## 6. 三个入门场景`**

Insert this content into `README.md`, then renumber existing sections 6–11 to 7–12 and update internal section references if any:

````markdown
## 6. 可执行监控与 Chaos Runbook

Grafana 会在启动时自动导入 `PerfShop Overview`。首次启动使用：

```bash
docker compose up --build
```

只修改 Dashboard provisioning 文件时不需要重建镜像，重启 Grafana 即可：

```bash
docker compose restart grafana
```

打开 http://localhost:3000，使用 `admin/admin` 登录，在 `Dashboards → PerfShop → PerfShop Overview` 查看面板。每次实验先执行 baseline，再开启一个 chaos；实验完成后立即 reset。

### 6.1 Baseline

商品搜索：

```bash
wrk -t2 -c20 -d60s "http://localhost:8080/api/products/search?q=alpha"
```

商品详情与 Redis：

```bash
wrk -t2 -c20 -d60s http://localhost:8080/api/products/1
```

Downstream 推荐：

```bash
wrk -t2 -c20 -d60s http://localhost:8080/api/recommendations/1
```

记录 `HTTP QPS`、`HTTP P95 Latency`、`HTTP P99 Latency`，以及对应依赖面板的稳定区间。

### 6.2 Slow DB

```bash
curl -X POST "http://localhost:8080/chaos/slow-db?enabled=true"
wrk -t2 -c20 -d60s "http://localhost:8080/api/products/search?q=alpha"
```

观察 `DB Query QPS`、`DB Average Latency`、`DB P95 Latency`。确认 `slow_product_search` 序列出现；用 `EXPLAIN` 验证 `description LIKE '%alpha%'` 的全表扫描。小数据集下延迟差异可能不大，查询计划仍是扩展性证据。

### 6.3 CPU Hotspot

先在一个终端启动热点：

```bash
curl -X POST "http://localhost:8080/chaos/cpu?duration=60"
```

立即在另一个终端压测：

```bash
wrk -t2 -c20 -d60s http://localhost:8080/api/products/1
```

观察 `App CPU Usage`、`HTTP QPS`、`HTTP P99 Latency`。

### 6.4 Redis Slow

```bash
curl -X POST "http://localhost:8080/chaos/redis-slow?enabled=true"
wrk -t2 -c20 -d60s http://localhost:8080/api/products/1
```

观察 `Redis P95 Latency`、`HTTP P95 Latency`、`HTTP P99 Latency`。

### 6.5 Downstream Timeout

```bash
curl -X POST "http://localhost:8080/chaos/downstream-delay?delay_ms=1000"
wrk -t2 -c20 -d60s http://localhost:8080/api/recommendations/1
```

观察 `Downstream QPS`、`Downstream Error Rate`、`Downstream P95 Latency`、`HTTP 5xx Rate`。

### 6.6 Retry Storm

```bash
curl -X POST "http://localhost:8080/chaos/downstream-delay?delay_ms=1000"
curl -X POST "http://localhost:8080/chaos/retry-storm?enabled=true"
wrk -t2 -c20 -d60s http://localhost:8080/api/recommendations/1
```

观察 `Downstream Retry Rate`、`Downstream QPS`、`Downstream Error Rate`，确认单次用户请求被放大成多次下游请求。

### 6.7 Reset

每个案例结束后执行：

```bash
curl -X POST http://localhost:8080/chaos/reset
```

使用相同 `wrk` 参数复测，确认 CPU、延迟、错误率和重试率恢复 baseline。

````

- [ ] **Step 4: Run focused test and verify it passes**

Run:

```bash
python -m unittest \
  tests.test_grafana_provisioning.GrafanaProvisioningTests.test_readme_contains_executable_monitoring_runbook \
  -v
```

Expected: one test passes.

- [ ] **Step 5: Run all lab tests and Markdown checks**

Run:

```bash
python -m unittest discover -s tests -v
rg -n '^## ' README.md
git diff --check
```

Expected: all tests pass; headings increment monotonically; `git diff --check` emits no errors.

- [ ] **Step 6: Commit runbook**

```bash
git add \
  performance-tuning-roadmap/labs/perfshop-p0/tests/test_grafana_provisioning.py \
  performance-tuning-roadmap/labs/perfshop-p0/README.md
git commit -m "docs(perfshop): add monitoring chaos runbook"
```

---

### Task 3: Verify Compose and Runtime Provisioning

**Files:**

- Verify only; no planned file changes.

**Interfaces:**

- Consumes: Task 1 provisioning files and Task 2 runbook.
- Produces: evidence that Compose configuration is valid and Grafana loads dashboard UID `perfshop-overview`.

- [ ] **Step 1: Validate Compose configuration**

Run from `performance-tuning-roadmap/labs/perfshop-p0`:

```bash
docker compose config --quiet
```

Expected: exit code `0`, no output.

- [ ] **Step 2: Start or restart Grafana without rebuilding images**

If stack is already running:

```bash
docker compose restart grafana
```

If stack is not running:

```bash
docker compose up -d grafana
```

Expected: Grafana container reaches running state.

- [ ] **Step 3: Check Grafana provisioning logs**

Run:

```bash
docker compose logs --tail=100 grafana
```

Expected: no `failed to provision`, `error`, or dashboard JSON parse messages.

- [ ] **Step 4: Verify health and dashboard API**

Run:

```bash
curl --fail --silent http://localhost:3000/api/health
curl --fail --silent \
  --user admin:admin \
  http://localhost:3000/api/dashboards/uid/perfshop-overview
```

Expected: health JSON reports database `ok`; dashboard response contains `"uid":"perfshop-overview"` and title `PerfShop Overview`.

- [ ] **Step 5: Generate smoke traffic and verify Prometheus expressions**

Run:

```bash
curl --fail --silent http://localhost:8080/api/products/1 >/dev/null
curl --fail --silent --get \
  --data-urlencode 'query=sum(rate(http_requests_total[1m]))' \
  http://localhost:9090/api/v1/query
```

Expected: Prometheus response has `"status":"success"` and a non-empty result after the next scrape interval.

- [ ] **Step 6: Run final repository checks**

Run:

```bash
python -m json.tool grafana/provisioning/dashboards/perfshop-overview.json >/dev/null
python -m unittest discover -s tests -v
docker compose config --quiet
git status --short
```

Expected: validation and tests pass; status shows only intended changes or pre-existing unrelated user changes.
