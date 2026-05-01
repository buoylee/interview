# PerfShop P1-mini Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the runnable PerfShop P0 lab into a P1-mini lab with Redis latency, downstream latency, retry amplification, and trace-id log correlation.

**Architecture:** Keep the existing Python standard-library app and add only two dependencies: Redis as a cache/dependency and a minimal Python downstream service. The app owns entrance traffic, Redis cache-aside behavior, outbound downstream calls, chaos toggles, and app-level dependency metrics. The downstream service owns recommendation responses, downstream delay chaos, JSON logs, and downstream-side request metrics.

**Tech Stack:** Python 3.12 stdlib HTTP server, `mysql-connector-python==9.0.0`, `redis==7.4.0`, Docker Compose, MySQL 8.0, Redis 7.4, Prometheus, Grafana.

---

## References

- Spec: `docs/superpowers/specs/2026-05-01-perfshop-p1-mini-design.md`
- Existing lab: `performance-tuning-roadmap/labs/perfshop-p0/`
- Redis client docs checked with ctx7: `/redis/redis-py`, focused on `redis.Redis(...)`, `decode_responses=True`, `socket_timeout`, `get`, and `set`.
- Redis package version checked with `python3 -m pip index versions redis` on 2026-05-01: latest reported version is `7.4.0`.

## File Structure

- Modify `performance-tuning-roadmap/labs/perfshop-p0/docker-compose.yml`
  - Add `redis` service.
  - Add `downstream` service.
  - Add app environment variables for Redis/downstream.
  - Make app wait for MySQL, Redis, and downstream health.
- Modify `performance-tuning-roadmap/labs/perfshop-p0/app/requirements.txt`
  - Add `redis==7.4.0`.
- Modify `performance-tuning-roadmap/labs/perfshop-p0/app/src/server.py`
  - Add trace ID extraction, response propagation, and JSON logs.
  - Add Redis cache-aside behavior and Redis metrics.
  - Add downstream call behavior, outbound dependency metrics, and retry-storm behavior.
  - Add P1-mini chaos routes.
- Create `performance-tuning-roadmap/labs/perfshop-p0/downstream/Dockerfile`
  - Build a minimal Python service image.
- Create `performance-tuning-roadmap/labs/perfshop-p0/downstream/requirements.txt`
  - Keep the file present and empty because downstream uses only the standard library.
- Create `performance-tuning-roadmap/labs/perfshop-p0/downstream/src/server.py`
  - Implement recommendation endpoint, delay chaos, metrics, and trace-id JSON logs.
- Modify `performance-tuning-roadmap/labs/perfshop-p0/prometheus/prometheus.yml`
  - Add downstream scrape target.
- Modify `performance-tuning-roadmap/labs/perfshop-p0/README.md`
  - Document P1-mini scope, services, endpoints, metrics, exercises, and non-goals.

---

### Task 1: Compose, Dependencies, And Prometheus Targets

**Files:**
- Modify: `performance-tuning-roadmap/labs/perfshop-p0/app/requirements.txt`
- Create: `performance-tuning-roadmap/labs/perfshop-p0/downstream/Dockerfile`
- Create: `performance-tuning-roadmap/labs/perfshop-p0/downstream/requirements.txt`
- Modify: `performance-tuning-roadmap/labs/perfshop-p0/docker-compose.yml`
- Modify: `performance-tuning-roadmap/labs/perfshop-p0/prometheus/prometheus.yml`

- [ ] **Step 1: Update app Python dependencies**

Replace `performance-tuning-roadmap/labs/perfshop-p0/app/requirements.txt` with:

```text
mysql-connector-python==9.0.0
redis==7.4.0
```

- [ ] **Step 2: Add downstream Dockerfile**

Create `performance-tuning-roadmap/labs/perfshop-p0/downstream/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

EXPOSE 8081
CMD ["python", "src/server.py"]
```

- [ ] **Step 3: Add downstream requirements file**

Create `performance-tuning-roadmap/labs/perfshop-p0/downstream/requirements.txt` as an empty file:

```text
```

- [ ] **Step 4: Update Docker Compose**

Replace `performance-tuning-roadmap/labs/perfshop-p0/docker-compose.yml` with:

```yaml
services:
  mysql:
    image: mysql:8.0
    container_name: perfshop-p0-mysql
    environment:
      MYSQL_ROOT_PASSWORD: perfshop123
      MYSQL_DATABASE: perfshop
    ports:
      - "3306:3306"
    volumes:
      - ./sql/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-pperfshop123"]
      interval: 5s
      timeout: 3s
      retries: 20

  redis:
    image: redis:7.4-alpine
    container_name: perfshop-p0-redis
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 20

  downstream:
    build: ./downstream
    container_name: perfshop-p0-downstream
    environment:
      DOWNSTREAM_PORT: "8081"
    ports:
      - "8081:8081"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/health', timeout=2)"]
      interval: 5s
      timeout: 3s
      retries: 20

  app:
    build: ./app
    container_name: perfshop-p0-app
    environment:
      DB_HOST: mysql
      DB_PORT: "3306"
      DB_USER: root
      DB_PASSWORD: perfshop123
      DB_NAME: perfshop
      APP_PORT: "8080"
      REDIS_HOST: redis
      REDIS_PORT: "6379"
      REDIS_DB: "0"
      REDIS_SOCKET_TIMEOUT_SECONDS: "0.25"
      DOWNSTREAM_URL: http://downstream:8081
      DOWNSTREAM_TIMEOUT_SECONDS: "0.35"
      DOWNSTREAM_RETRY_ATTEMPTS: "2"
    ports:
      - "8080:8080"
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
      downstream:
        condition: service_healthy

  prometheus:
    image: prom/prometheus:v2.51.0
    container_name: perfshop-p0-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    depends_on:
      - app
      - downstream

  grafana:
    image: grafana/grafana:10.4.0
    container_name: perfshop-p0-grafana
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_USERS_ALLOW_SIGN_UP: "false"
    ports:
      - "3000:3000"
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
    depends_on:
      - prometheus
```

- [ ] **Step 5: Update Prometheus scrape config**

Replace `performance-tuning-roadmap/labs/perfshop-p0/prometheus/prometheus.yml` with:

```yaml
global:
  scrape_interval: 5s
  evaluation_interval: 5s

scrape_configs:
  - job_name: "prometheus"
    static_configs:
      - targets: ["localhost:9090"]

  - job_name: "perfshop-p0"
    metrics_path: /metrics
    static_configs:
      - targets: ["app:8080"]

  - job_name: "perfshop-downstream"
    metrics_path: /metrics
    static_configs:
      - targets: ["downstream:8081"]
```

- [ ] **Step 6: Verify Compose renders**

Run:

```bash
cd performance-tuning-roadmap/labs/perfshop-p0
docker compose config >/tmp/perfshop-p1-mini-compose.yml
rg -n "redis:|downstream:|perfshop-downstream|REDIS_HOST|DOWNSTREAM_URL" /tmp/perfshop-p1-mini-compose.yml
```

Expected output contains `redis:`, `downstream:`, `perfshop-downstream`, `REDIS_HOST`, and `DOWNSTREAM_URL`.

- [ ] **Step 7: Commit infra changes**

Run:

```bash
git add performance-tuning-roadmap/labs/perfshop-p0/app/requirements.txt \
  performance-tuning-roadmap/labs/perfshop-p0/downstream/Dockerfile \
  performance-tuning-roadmap/labs/perfshop-p0/downstream/requirements.txt \
  performance-tuning-roadmap/labs/perfshop-p0/docker-compose.yml \
  performance-tuning-roadmap/labs/perfshop-p0/prometheus/prometheus.yml
git commit -m "feat: add perfshop p1 mini services"
```

---

### Task 2: Downstream Service

**Files:**
- Create: `performance-tuning-roadmap/labs/perfshop-p0/downstream/src/server.py`

- [ ] **Step 1: Implement downstream server**

Create `performance-tuning-roadmap/labs/perfshop-p0/downstream/src/server.py`:

```python
import json
import os
import resource
import sys
import time
import uuid
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from urllib.parse import parse_qs, urlparse


BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]

metrics_lock = Lock()
http_requests = defaultdict(int)
http_duration_buckets = defaultdict(int)
http_duration_sum = defaultdict(float)
http_duration_count = defaultdict(int)

chaos = {
    "delay_ms": 0,
}


def trace_id_from(headers):
    incoming = headers.get("X-Trace-Id", "").strip()
    return incoming or uuid.uuid4().hex[:16]


def json_log(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


def observe_http(method, path, status, seconds):
    labels = (method, path, str(status))
    hist_labels = (method, path)
    with metrics_lock:
        http_requests[labels] += 1
        http_duration_sum[hist_labels] += seconds
        http_duration_count[hist_labels] += 1
        for bucket in BUCKETS:
            if seconds <= bucket:
                http_duration_buckets[(method, path, bucket)] += 1
        http_duration_buckets[(method, path, "+Inf")] += 1


def normalized_path(path):
    if path.startswith("/api/recommendations/"):
        return "/api/recommendations/{product_id}"
    if path.startswith("/chaos/"):
        return "/chaos/*"
    return path


def maybe_delay():
    delay_ms = chaos["delay_ms"]
    if delay_ms > 0:
        time.sleep(delay_ms / 1000)


class Handler(BaseHTTPRequestHandler):
    server_version = "PerfShopDownstream/0.1"

    def log_message(self, fmt, *args):
        return

    def send_json(self, status, payload, trace_id):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Trace-Id", trace_id)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        started = time.perf_counter()
        status = 200
        trace_id = trace_id_from(self.headers)
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/health":
                self.send_json(200, {"status": "ok"}, trace_id)
            elif path == "/metrics":
                self.send_metrics(trace_id)
            elif path.startswith("/api/recommendations/"):
                maybe_delay()
                status = self.handle_recommendations(path, trace_id)
            else:
                status = 404
                self.send_json(404, {"error": "not found"}, trace_id)
        except Exception as exc:
            status = 500
            self.send_json(500, {"error": str(exc)}, trace_id)
        finally:
            duration = time.perf_counter() - started
            observe_http("GET", normalized_path(path), status, duration)
            json_log({
                "service": "downstream",
                "trace_id": trace_id,
                "method": "GET",
                "path": normalized_path(path),
                "status": status,
                "duration_ms": round(duration * 1000, 3),
            })

    def do_POST(self):
        started = time.perf_counter()
        status = 200
        trace_id = trace_id_from(self.headers)
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            if path == "/chaos/delay":
                delay_ms = int(query.get("delay_ms", ["1000"])[0])
                chaos["delay_ms"] = max(0, delay_ms)
                self.send_json(200, {"delay_ms": chaos["delay_ms"]}, trace_id)
            elif path == "/chaos/reset":
                chaos["delay_ms"] = 0
                self.send_json(200, {"status": "reset"}, trace_id)
            else:
                status = 404
                self.send_json(404, {"error": "not found"}, trace_id)
        except Exception as exc:
            status = 500
            self.send_json(500, {"error": str(exc)}, trace_id)
        finally:
            duration = time.perf_counter() - started
            observe_http("POST", normalized_path(path), status, duration)
            json_log({
                "service": "downstream",
                "trace_id": trace_id,
                "method": "POST",
                "path": normalized_path(path),
                "status": status,
                "duration_ms": round(duration * 1000, 3),
            })

    def handle_recommendations(self, path, trace_id):
        product_id = int(path.rsplit("/", 1)[1])
        recommendations = [
            {"product_id": product_id + 1, "score": 0.93},
            {"product_id": product_id + 2, "score": 0.87},
            {"product_id": product_id + 3, "score": 0.81},
        ]
        self.send_json(200, {"product_id": product_id, "items": recommendations}, trace_id)
        return 200

    def send_metrics(self, trace_id):
        lines = [
            "# HELP downstream_http_requests_total Total downstream HTTP requests.",
            "# TYPE downstream_http_requests_total counter",
        ]
        with metrics_lock:
            for (method, path, status), value in sorted(http_requests.items()):
                lines.append(f'downstream_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {value}')

            lines.extend([
                "# HELP downstream_http_request_duration_seconds Downstream HTTP request duration.",
                "# TYPE downstream_http_request_duration_seconds histogram",
            ])
            for (method, path, bucket), value in sorted(http_duration_buckets.items(), key=lambda x: str(x[0])):
                lines.append(f'downstream_http_request_duration_seconds_bucket{{method="{method}",path="{path}",le="{bucket}"}} {value}')
            for (method, path), value in sorted(http_duration_sum.items()):
                lines.append(f'downstream_http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {value}')
                lines.append(f'downstream_http_request_duration_seconds_count{{method="{method}",path="{path}"}} {http_duration_count[(method, path)]}')

        rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        lines.extend([
            "# HELP process_cpu_seconds_total Total user and system CPU time spent in seconds.",
            "# TYPE process_cpu_seconds_total counter",
            f"process_cpu_seconds_total {time.process_time()}",
            "# HELP process_resident_memory_bytes Resident memory size in bytes.",
            "# TYPE process_resident_memory_bytes gauge",
            f"process_resident_memory_bytes {rss_kb * 1024}",
            "",
        ])
        body = "\n".join(lines).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Trace-Id", trace_id)
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = int(os.getenv("DOWNSTREAM_PORT", "8081"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
```

- [ ] **Step 2: Verify downstream syntax**

Run:

```bash
python3 -m py_compile performance-tuning-roadmap/labs/perfshop-p0/downstream/src/server.py
```

Expected: exit code `0` with no output.

- [ ] **Step 3: Commit downstream service**

Run:

```bash
git add performance-tuning-roadmap/labs/perfshop-p0/downstream/src/server.py
git commit -m "feat: add perfshop downstream service"
```

---

### Task 3: App P1-mini Behavior

**Files:**
- Modify: `performance-tuning-roadmap/labs/perfshop-p0/app/src/server.py`

- [ ] **Step 1: Replace app server with P1-mini implementation**

Replace `performance-tuning-roadmap/labs/perfshop-p0/app/src/server.py` with:

```python
import json
import os
import resource
import sys
import time
import uuid
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from urllib import error as url_error
from urllib import request as url_request
from urllib.parse import parse_qs, urlparse

import mysql.connector
import redis


BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
BIG_KEY_BYTES = 512 * 1024

metrics_lock = Lock()
http_requests = defaultdict(int)
http_duration_buckets = defaultdict(int)
http_duration_sum = defaultdict(float)
http_duration_count = defaultdict(int)
db_duration_buckets = defaultdict(int)
db_duration_sum = defaultdict(float)
db_duration_count = defaultdict(int)
redis_duration_buckets = defaultdict(int)
redis_duration_sum = defaultdict(float)
redis_duration_count = defaultdict(int)
app_downstream_duration_buckets = defaultdict(int)
app_downstream_duration_sum = defaultdict(float)
app_downstream_duration_count = defaultdict(int)
app_downstream_requests = defaultdict(int)
app_downstream_retries = defaultdict(int)

chaos = {
    "cpu_until": 0.0,
    "slow_db": False,
    "slow_downstream_ms": 0,
    "redis_big_key": False,
    "redis_slow": False,
    "retry_storm": False,
}


def db_config():
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", "perfshop123"),
        "database": os.getenv("DB_NAME", "perfshop"),
    }


def connect_db():
    return mysql.connector.connect(**db_config())


def redis_client():
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "127.0.0.1"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        decode_responses=True,
        socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT_SECONDS", "0.25")),
        socket_connect_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT_SECONDS", "0.25")),
    )


def downstream_url():
    return os.getenv("DOWNSTREAM_URL", "http://127.0.0.1:8081").rstrip("/")


def downstream_timeout():
    return float(os.getenv("DOWNSTREAM_TIMEOUT_SECONDS", "0.35"))


def downstream_retry_attempts():
    return int(os.getenv("DOWNSTREAM_RETRY_ATTEMPTS", "2"))


def trace_id_from(headers):
    incoming = headers.get("X-Trace-Id", "").strip()
    return incoming or uuid.uuid4().hex[:16]


def json_log(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


def observe_http(method, path, status, seconds):
    labels = (method, path, str(status))
    hist_labels = (method, path)
    with metrics_lock:
        http_requests[labels] += 1
        http_duration_sum[hist_labels] += seconds
        http_duration_count[hist_labels] += 1
        for bucket in BUCKETS:
            if seconds <= bucket:
                http_duration_buckets[(method, path, bucket)] += 1
        http_duration_buckets[(method, path, "+Inf")] += 1


def observe_db(query_name, seconds):
    with metrics_lock:
        db_duration_sum[query_name] += seconds
        db_duration_count[query_name] += 1
        for bucket in BUCKETS:
            if seconds <= bucket:
                db_duration_buckets[(query_name, bucket)] += 1
        db_duration_buckets[(query_name, "+Inf")] += 1


def observe_redis(operation, seconds):
    with metrics_lock:
        redis_duration_sum[operation] += seconds
        redis_duration_count[operation] += 1
        for bucket in BUCKETS:
            if seconds <= bucket:
                redis_duration_buckets[(operation, bucket)] += 1
        redis_duration_buckets[(operation, "+Inf")] += 1


def observe_app_downstream(target, status, seconds):
    with metrics_lock:
        app_downstream_requests[(target, str(status))] += 1
        app_downstream_duration_sum[target] += seconds
        app_downstream_duration_count[target] += 1
        for bucket in BUCKETS:
            if seconds <= bucket:
                app_downstream_duration_buckets[(target, bucket)] += 1
        app_downstream_duration_buckets[(target, "+Inf")] += 1


def observe_app_downstream_retry(target):
    with metrics_lock:
        app_downstream_retries[target] += 1


def run_query(query_name, sql, params=()):
    started = time.perf_counter()
    conn = connect_db()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        conn.close()
        observe_db(query_name, time.perf_counter() - started)


def redis_execute(operation, command):
    started = time.perf_counter()
    try:
        if chaos["redis_slow"]:
            time.sleep(0.08)
        return command(redis_client())
    finally:
        observe_redis(operation, time.perf_counter() - started)


def burn_cpu_if_enabled():
    if time.time() >= chaos["cpu_until"]:
        return
    deadline = time.perf_counter() + 0.05
    value = 0
    while time.perf_counter() < deadline:
        value = (value * 31 + 7) % 1_000_003


def maybe_sleep_downstream():
    delay_ms = chaos["slow_downstream_ms"]
    if delay_ms > 0:
        time.sleep(delay_ms / 1000)


def normalized_path(path):
    if path.startswith("/api/products/search"):
        return "/api/products/search"
    if path.startswith("/api/products/"):
        return "/api/products/{id}"
    if path.startswith("/api/recommendations/"):
        return "/api/recommendations/{product_id}"
    if path.startswith("/chaos/"):
        return "/chaos/*"
    return path


def bool_query(query, name, default=True):
    raw = query.get(name, ["true" if default else "false"])[0].lower()
    return raw in {"1", "true", "yes", "on"}


def post_downstream(path, trace_id):
    req = url_request.Request(
        f"{downstream_url()}{path}",
        method="POST",
        headers={"X-Trace-Id": trace_id},
    )
    with url_request.urlopen(req, timeout=downstream_timeout()) as response:
        return response.status


class Handler(BaseHTTPRequestHandler):
    server_version = "PerfShopP1Mini/0.1"

    def log_message(self, fmt, *args):
        return

    def send_json(self, status, payload, trace_id):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Trace-Id", trace_id)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        started = time.perf_counter()
        status = 200
        trace_id = trace_id_from(self.headers)
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            burn_cpu_if_enabled()
            maybe_sleep_downstream()
            if path == "/health":
                self.send_json(200, {"status": "ok"}, trace_id)
            elif path == "/metrics":
                self.send_metrics(trace_id)
            elif path.startswith("/api/products/search"):
                status = self.handle_search(parse_qs(parsed.query), trace_id)
            elif path.startswith("/api/products/"):
                status = self.handle_product(path, trace_id)
            elif path.startswith("/api/recommendations/"):
                status = self.handle_recommendations(path, trace_id)
            else:
                status = 404
                self.send_json(404, {"error": "not found"}, trace_id)
        except Exception as exc:
            status = 500
            self.send_json(500, {"error": str(exc)}, trace_id)
        finally:
            duration = time.perf_counter() - started
            observe_http("GET", normalized_path(path), status, duration)
            json_log({
                "service": "app",
                "trace_id": trace_id,
                "method": "GET",
                "path": normalized_path(path),
                "status": status,
                "duration_ms": round(duration * 1000, 3),
            })

    def do_POST(self):
        started = time.perf_counter()
        status = 200
        trace_id = trace_id_from(self.headers)
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            if path == "/chaos/cpu":
                duration = int(query.get("duration", ["60"])[0])
                chaos["cpu_until"] = time.time() + duration
                self.send_json(200, {"cpu_hotspot_enabled_seconds": duration}, trace_id)
            elif path == "/chaos/slow-db":
                enabled = bool_query(query, "enabled")
                chaos["slow_db"] = enabled
                self.send_json(200, {"slow_db": enabled}, trace_id)
            elif path == "/chaos/slow-downstream":
                delay_ms = int(query.get("delay_ms", ["1000"])[0])
                chaos["slow_downstream_ms"] = delay_ms
                self.send_json(200, {"slow_downstream_ms": delay_ms}, trace_id)
            elif path == "/chaos/redis-big-key":
                enabled = bool_query(query, "enabled")
                chaos["redis_big_key"] = enabled
                if enabled:
                    redis_execute("bigkey_set", lambda client: client.set("chaos:big-product-payload", "x" * BIG_KEY_BYTES))
                self.send_json(200, {"redis_big_key": enabled}, trace_id)
            elif path == "/chaos/redis-slow":
                enabled = bool_query(query, "enabled")
                chaos["redis_slow"] = enabled
                self.send_json(200, {"redis_slow": enabled}, trace_id)
            elif path == "/chaos/downstream-delay":
                delay_ms = int(query.get("delay_ms", ["1000"])[0])
                post_downstream(f"/chaos/delay?delay_ms={max(0, delay_ms)}", trace_id)
                self.send_json(200, {"downstream_delay_ms": max(0, delay_ms)}, trace_id)
            elif path == "/chaos/retry-storm":
                enabled = bool_query(query, "enabled")
                chaos["retry_storm"] = enabled
                self.send_json(200, {"retry_storm": enabled}, trace_id)
            elif path == "/chaos/reset":
                chaos["cpu_until"] = 0.0
                chaos["slow_db"] = False
                chaos["slow_downstream_ms"] = 0
                chaos["redis_big_key"] = False
                chaos["redis_slow"] = False
                chaos["retry_storm"] = False
                try:
                    post_downstream("/chaos/reset", trace_id)
                except Exception as exc:
                    json_log({"service": "app", "trace_id": trace_id, "event": "downstream_reset_failed", "error": str(exc)})
                self.send_json(200, {"status": "reset"}, trace_id)
            else:
                status = 404
                self.send_json(404, {"error": "not found"}, trace_id)
        except Exception as exc:
            status = 500
            self.send_json(500, {"error": str(exc)}, trace_id)
        finally:
            duration = time.perf_counter() - started
            observe_http("POST", normalized_path(path), status, duration)
            json_log({
                "service": "app",
                "trace_id": trace_id,
                "method": "POST",
                "path": normalized_path(path),
                "status": status,
                "duration_ms": round(duration * 1000, 3),
            })

    def handle_product(self, path, trace_id):
        product_id = int(path.rsplit("/", 1)[1])
        key = f"product:{product_id}"
        try:
            cached = redis_execute("get", lambda client: client.get(key))
            if chaos["redis_big_key"]:
                redis_execute("bigkey_get", lambda client: client.get("chaos:big-product-payload"))
            if cached:
                self.send_json(200, json.loads(cached), trace_id)
                return 200
        except redis.RedisError as exc:
            json_log({"service": "app", "trace_id": trace_id, "event": "redis_get_failed", "error": str(exc)})

        rows = run_query(
            "product_by_id",
            "SELECT id, name, category, price, stock FROM products WHERE id = %s",
            (product_id,),
        )
        if not rows:
            self.send_json(404, {"error": "product not found"}, trace_id)
            return 404

        product = rows[0]
        try:
            redis_execute("setex", lambda client: client.setex(key, 60, json.dumps(product, ensure_ascii=False, default=str)))
        except redis.RedisError as exc:
            json_log({"service": "app", "trace_id": trace_id, "event": "redis_set_failed", "error": str(exc)})
        self.send_json(200, product, trace_id)
        return 200

    def handle_search(self, query, trace_id):
        keyword = query.get("q", ["alpha"])[0]
        if chaos["slow_db"]:
            rows = run_query(
                "slow_product_search",
                "SELECT id, name, category, price FROM products WHERE description LIKE %s LIMIT 20",
                (f"%{keyword}%",),
            )
        else:
            rows = run_query(
                "product_search",
                "SELECT id, name, category, price FROM products WHERE category = %s LIMIT 20",
                (keyword if keyword in {"electronics", "books", "food", "sports", "clothing"} else "electronics",),
            )
        self.send_json(200, {"count": len(rows), "items": rows}, trace_id)
        return 200

    def handle_recommendations(self, path, trace_id):
        product_id = int(path.rsplit("/", 1)[1])
        try:
            payload = self.call_downstream_recommendations(product_id, trace_id)
            self.send_json(200, payload, trace_id)
            return 200
        except Exception as exc:
            self.send_json(502, {"error": "downstream request failed", "detail": str(exc)}, trace_id)
            return 502

    def call_downstream_recommendations(self, product_id, trace_id):
        attempts = 1 + (downstream_retry_attempts() if chaos["retry_storm"] else 0)
        last_error = None
        for attempt in range(1, attempts + 1):
            if attempt > 1:
                observe_app_downstream_retry("recommendations")
            started = time.perf_counter()
            status = "error"
            try:
                req = url_request.Request(
                    f"{downstream_url()}/api/recommendations/{product_id}",
                    headers={"X-Trace-Id": trace_id},
                )
                with url_request.urlopen(req, timeout=downstream_timeout()) as response:
                    status = response.status
                    body = response.read().decode("utf-8")
                    observe_app_downstream("recommendations", status, time.perf_counter() - started)
                    return json.loads(body)
            except url_error.HTTPError as exc:
                status = exc.code
                last_error = exc
            except Exception as exc:
                last_error = exc
            finally:
                if status == "error" or int(status) >= 400:
                    observe_app_downstream("recommendations", status, time.perf_counter() - started)
        raise RuntimeError(last_error)

    def send_metrics(self, trace_id):
        lines = [
            "# HELP http_requests_total Total HTTP requests.",
            "# TYPE http_requests_total counter",
        ]
        with metrics_lock:
            for (method, path, status), value in sorted(http_requests.items()):
                lines.append(f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {value}')

            lines.extend([
                "# HELP http_request_duration_seconds HTTP request duration.",
                "# TYPE http_request_duration_seconds histogram",
            ])
            for (method, path, bucket), value in sorted(http_duration_buckets.items(), key=lambda x: str(x[0])):
                lines.append(f'http_request_duration_seconds_bucket{{method="{method}",path="{path}",le="{bucket}"}} {value}')
            for (method, path), value in sorted(http_duration_sum.items()):
                lines.append(f'http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {value}')
                lines.append(f'http_request_duration_seconds_count{{method="{method}",path="{path}"}} {http_duration_count[(method, path)]}')

            lines.extend([
                "# HELP db_query_duration_seconds Database query duration.",
                "# TYPE db_query_duration_seconds histogram",
            ])
            for (query_name, bucket), value in sorted(db_duration_buckets.items(), key=lambda x: str(x[0])):
                lines.append(f'db_query_duration_seconds_bucket{{query="{query_name}",le="{bucket}"}} {value}')
            for query_name, value in sorted(db_duration_sum.items()):
                lines.append(f'db_query_duration_seconds_sum{{query="{query_name}"}} {value}')
                lines.append(f'db_query_duration_seconds_count{{query="{query_name}"}} {db_duration_count[query_name]}')

            lines.extend([
                "# HELP redis_operation_duration_seconds Redis operation duration.",
                "# TYPE redis_operation_duration_seconds histogram",
            ])
            for (operation, bucket), value in sorted(redis_duration_buckets.items(), key=lambda x: str(x[0])):
                lines.append(f'redis_operation_duration_seconds_bucket{{operation="{operation}",le="{bucket}"}} {value}')
            for operation, value in sorted(redis_duration_sum.items()):
                lines.append(f'redis_operation_duration_seconds_sum{{operation="{operation}"}} {value}')
                lines.append(f'redis_operation_duration_seconds_count{{operation="{operation}"}} {redis_duration_count[operation]}')

            lines.extend([
                "# HELP app_downstream_requests_total App outbound downstream requests.",
                "# TYPE app_downstream_requests_total counter",
            ])
            for (target, status), value in sorted(app_downstream_requests.items()):
                lines.append(f'app_downstream_requests_total{{target="{target}",status="{status}"}} {value}')

            lines.extend([
                "# HELP app_downstream_request_duration_seconds App outbound downstream request duration.",
                "# TYPE app_downstream_request_duration_seconds histogram",
            ])
            for (target, bucket), value in sorted(app_downstream_duration_buckets.items(), key=lambda x: str(x[0])):
                lines.append(f'app_downstream_request_duration_seconds_bucket{{target="{target}",le="{bucket}"}} {value}')
            for target, value in sorted(app_downstream_duration_sum.items()):
                lines.append(f'app_downstream_request_duration_seconds_sum{{target="{target}"}} {value}')
                lines.append(f'app_downstream_request_duration_seconds_count{{target="{target}"}} {app_downstream_duration_count[target]}')

            lines.extend([
                "# HELP app_downstream_retries_total App outbound downstream retries.",
                "# TYPE app_downstream_retries_total counter",
            ])
            for target, value in sorted(app_downstream_retries.items()):
                lines.append(f'app_downstream_retries_total{{target="{target}"}} {value}')

        rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        lines.extend([
            "# HELP process_cpu_seconds_total Total user and system CPU time spent in seconds.",
            "# TYPE process_cpu_seconds_total counter",
            f"process_cpu_seconds_total {time.process_time()}",
            "# HELP process_resident_memory_bytes Resident memory size in bytes.",
            "# TYPE process_resident_memory_bytes gauge",
            f"process_resident_memory_bytes {rss_kb * 1024}",
            "",
        ])
        body = "\n".join(lines).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Trace-Id", trace_id)
        self.end_headers()
        self.wfile.write(body)


def wait_for_db():
    for _ in range(60):
        try:
            conn = connect_db()
            conn.close()
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("database did not become ready")


def wait_for_redis():
    for _ in range(60):
        try:
            redis_execute("ping", lambda client: client.ping())
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("redis did not become ready")


if __name__ == "__main__":
    wait_for_db()
    wait_for_redis()
    port = int(os.getenv("APP_PORT", "8080"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
```

- [ ] **Step 2: Verify app syntax**

Run:

```bash
python3 -m py_compile performance-tuning-roadmap/labs/perfshop-p0/app/src/server.py
```

Expected: exit code `0` with no output.

- [ ] **Step 3: Verify required endpoints and metric names exist**

Run:

```bash
rg -n "/api/recommendations|/chaos/redis-big-key|/chaos/redis-slow|/chaos/downstream-delay|/chaos/retry-storm|redis_operation_duration_seconds|app_downstream_request_duration_seconds|app_downstream_retries_total|X-Trace-Id|trace_id" performance-tuning-roadmap/labs/perfshop-p0/app/src/server.py
```

Expected: every pattern appears at least once.

- [ ] **Step 4: Commit app behavior**

Run:

```bash
git add performance-tuning-roadmap/labs/perfshop-p0/app/src/server.py
git commit -m "feat: add perfshop p1 mini app behavior"
```

---

### Task 4: Runtime Smoke Verification

**Files:**
- Verify only.

- [ ] **Step 1: Build and start the P1-mini stack**

Run:

```bash
cd performance-tuning-roadmap/labs/perfshop-p0
docker compose up --build -d
```

Expected: exit code `0`.

- [ ] **Step 2: Verify container health**

Run:

```bash
cd performance-tuning-roadmap/labs/perfshop-p0
docker compose ps
```

Expected: `perfshop-p0-app`, `perfshop-p0-downstream`, `perfshop-p0-redis`, `perfshop-p0-mysql`, `perfshop-p0-prometheus`, and `perfshop-p0-grafana` are running. Healthcheck-backed services show healthy status after startup.

- [ ] **Step 3: Verify app and downstream health**

Run:

```bash
curl -fsS -D /tmp/perfshop-app-health-headers.txt http://localhost:8080/health
curl -fsS -D /tmp/perfshop-downstream-health-headers.txt http://localhost:8081/health
rg -n "X-Trace-Id" /tmp/perfshop-app-health-headers.txt /tmp/perfshop-downstream-health-headers.txt
```

Expected: both `curl` calls return JSON with `"status": "ok"`, and both response header files contain `X-Trace-Id`.

- [ ] **Step 4: Verify product cache path**

Run:

```bash
curl -fsS -H "X-Trace-Id: p1-product-smoke" http://localhost:8080/api/products/1
curl -fsS -H "X-Trace-Id: p1-product-smoke" http://localhost:8080/api/products/1
curl -fsS http://localhost:8080/metrics | rg -n "redis_operation_duration_seconds_(bucket|count|sum)"
```

Expected: both product requests return a product JSON object, and metrics include Redis operation duration samples.

- [ ] **Step 5: Verify downstream call path**

Run:

```bash
curl -fsS -H "X-Trace-Id: p1-downstream-smoke" http://localhost:8080/api/recommendations/1
curl -fsS http://localhost:8080/metrics | rg -n "app_downstream_requests_total|app_downstream_request_duration_seconds"
curl -fsS http://localhost:8081/metrics | rg -n "downstream_http_requests_total|downstream_http_request_duration_seconds"
```

Expected: recommendation request returns a JSON object with `items`; app metrics include app downstream metrics; downstream metrics include downstream HTTP metrics.

- [ ] **Step 6: Verify chaos toggles**

Run:

```bash
curl -fsS -X POST "http://localhost:8080/chaos/redis-big-key?enabled=true"
curl -fsS http://localhost:8080/api/products/1 >/tmp/perfshop-product-after-bigkey.json
curl -fsS -X POST "http://localhost:8080/chaos/redis-slow?enabled=true"
curl -fsS http://localhost:8080/api/products/1 >/tmp/perfshop-product-after-redis-slow.json
curl -fsS -X POST "http://localhost:8080/chaos/downstream-delay?delay_ms=1000"
curl -sS -o /tmp/perfshop-recommendation-after-delay.json -w "%{http_code}\n" http://localhost:8080/api/recommendations/1
curl -fsS -X POST "http://localhost:8080/chaos/retry-storm?enabled=true"
curl -sS -o /tmp/perfshop-recommendation-after-retry.json -w "%{http_code}\n" http://localhost:8080/api/recommendations/1
curl -fsS -X POST "http://localhost:8080/chaos/reset"
```

Expected: Redis chaos calls return JSON status. Recommendation calls may return `200` when downstream responds before timeout or `502` when app timeout is hit; both are acceptable for delay/retry scenarios because the metrics and logs prove dependency behavior. Reset returns `{"status": "reset"}`.

- [ ] **Step 7: Verify retry metrics and log correlation**

Run:

```bash
curl -fsS http://localhost:8080/metrics | rg -n "app_downstream_retries_total|app_downstream_requests_total"
curl -fsS http://localhost:8081/metrics | rg -n "downstream_http_requests_total"
cd performance-tuning-roadmap/labs/perfshop-p0
docker compose logs app downstream | rg -n "p1-downstream-smoke|trace_id|downstream_reset_failed"
```

Expected: app metrics include retry/downstream request counters after retry storm. Downstream metrics include downstream request counters. Logs contain JSON lines with `trace_id`.

- [ ] **Step 8: Stop stack after verification**

Run:

```bash
cd performance-tuning-roadmap/labs/perfshop-p0
docker compose down
```

Expected: exit code `0`.

---

### Task 5: README P1-mini Documentation

**Files:**
- Modify: `performance-tuning-roadmap/labs/perfshop-p0/README.md`

- [ ] **Step 1: Update title and scope**

Change the title from:

```markdown
# PerfShop P0 最小实验闭环
```

to:

```markdown
# PerfShop P0 / P1-mini 实验闭环
```

Replace the opening goal block with:

```markdown
> 目标：先提供 P0 的“压测 → 观测 → 定位 → 修复 → 复测”最小闭环，再在同一个可运行 lab 内加入 P1-mini 的 Redis、下游服务、重试放大和 trace-id 日志关联训练。
```

- [ ] **Step 2: Add P1-mini scope section after current P0 scope**

Insert this section after the P0 scope table:

```markdown
## 1.1 P1-mini 范围

P1-mini 不是完整微服务系统，它只把 P0 扩展到足够训练跨组件性能定位：

| 能力 | P1-mini 要求 |
|------|--------------|
| Redis | 商品详情接口走 cache-aside，并能制造 Redis slow path / big key |
| 下游服务 | `/api/recommendations/{product_id}` 调用 mock downstream |
| 重试放大 | 可开启小规模、有限次数的 retry storm |
| 关联线索 | app 和 downstream 日志都输出同一个 `trace_id` |
| 指标 | app 暴露 Redis / downstream 出站指标，downstream 暴露自身入站指标 |

P1-mini 明确不包含 Kafka、OpenTelemetry、Jaeger、Loki，也不包含 Java / Go / Python 三语言对称服务。那些属于 P2。
```

- [ ] **Step 3: Update access table**

Add these rows to the access table:

```markdown
| Redis | `localhost:6379` |
| Downstream | http://localhost:8081 |
```

- [ ] **Step 4: Update recommended directory tree**

Replace the current tree with:

```text
perfshop-p0/
├── README.md
├── docker-compose.yml
├── prometheus/
│   └── prometheus.yml
├── grafana/
│   └── provisioning/
├── sql/
│   └── init.sql
├── app/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       └── server.py
├── downstream/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       └── server.py
└── load/
    ├── wrk-products.lua
    └── locustfile.py
```

- [ ] **Step 5: Add new endpoint rows**

Add these rows to the endpoint table:

```markdown
| `GET /api/recommendations/{product_id}` | 调用 downstream，训练跨组件延迟定位 |
| `POST /chaos/redis-big-key?enabled=true` | 制造 Redis big key 读写 |
| `POST /chaos/redis-slow?enabled=true` | 制造 Redis slow path |
| `POST /chaos/downstream-delay?delay_ms=1000` | 让 app 配置 downstream 延迟 |
| `POST /chaos/retry-storm?enabled=true` | 开启有限次数、无 backoff 的重试放大 |
```

- [ ] **Step 6: Add new metric names**

Append these metric names to the metric block:

```text
redis_operation_duration_seconds_bucket{operation}
app_downstream_requests_total{target,status}
app_downstream_request_duration_seconds_bucket{target}
app_downstream_retries_total{target}
downstream_http_requests_total{method,path,status}
downstream_http_request_duration_seconds_bucket{method,path}
```

- [ ] **Step 7: Add P1-mini exercises**

Insert this section before the P0 acceptance checklist:

````markdown
## 6.1 三个 P1-mini 场景

### 场景 4：Redis slow path / big key

目标：让学习者区分 app、DB、Redis 三类延迟来源。

流程：

```text
POST /chaos/redis-big-key?enabled=true
→ wrk -t2 -c20 -d30s http://localhost:8080/api/products/1
→ Prometheus 看到 redis_operation_duration_seconds 上升
→ app JSON log 中用 trace_id 找到慢请求
→ POST /chaos/reset
→ 同样压测复测
```

产物：

- Redis 操作延迟前后对比
- 慢请求 trace_id 日志样例
- cache-aside trade-off 说明

### 场景 5：downstream timeout

目标：让学习者解释下游等待如何放大上游 P99。

流程：

```text
POST /chaos/downstream-delay?delay_ms=1000
→ wrk -t2 -c20 -d30s http://localhost:8080/api/recommendations/1
→ Prometheus 看到 app_downstream_request_duration_seconds 上升
→ app 和 downstream 日志中用同一个 trace_id 关联调用
→ POST /chaos/reset
→ 同样压测复测
```

产物：

- app 入口 P99 和 downstream 出站耗时对比
- trace_id 关联证据
- timeout / fallback 取舍说明

### 场景 6：retry storm

目标：让学习者证明重试会把下游流量放大。

流程：

```text
POST /chaos/downstream-delay?delay_ms=1000
POST /chaos/retry-storm?enabled=true
→ wrk -t2 -c20 -d30s http://localhost:8080/api/recommendations/1
→ Prometheus 看到 app_downstream_retries_total 上升
→ downstream_http_requests_total 增速高于 app 入口请求数
→ POST /chaos/reset
→ 同样压测复测
```

产物：

- 入口 QPS 与 downstream QPS 对比
- retry 次数指标
- backoff、jitter、限流、熔断的面试解释
````

- [ ] **Step 8: Add P1-mini acceptance criteria**

Append this checklist after the P0 checklist:

```markdown
## 7.1 P1-mini 验收标准

- [ ] `docker compose up --build` 启动 app、MySQL、Redis、downstream、Prometheus、Grafana
- [ ] app 和 downstream `/health` 正常
- [ ] app 响应包含 `X-Trace-Id`
- [ ] app 与 downstream JSON log 包含同一个 `trace_id`
- [ ] `/api/products/1` 能通过 Redis cache-aside 返回商品
- [ ] `/api/recommendations/1` 能调用 downstream
- [ ] `/metrics` 包含 Redis、app downstream、downstream HTTP 指标
- [ ] Redis big-key 或 slow-path 能开启、观测、reset、复测
- [ ] downstream delay 能开启、观测、reset、复测
- [ ] retry storm 能开启、观测、reset、复测
```

- [ ] **Step 9: Verify README mentions required P1-mini terms**

Run:

```bash
rg -n "P1-mini|Redis|Downstream|trace_id|retry storm|app_downstream_retries_total|downstream_http_requests_total|OpenTelemetry|Jaeger|Loki|Kafka" performance-tuning-roadmap/labs/perfshop-p0/README.md
```

Expected: every term appears at least once.

- [ ] **Step 10: Commit README changes**

Run:

```bash
git add performance-tuning-roadmap/labs/perfshop-p0/README.md
git commit -m "docs: document perfshop p1 mini lab"
```

---

### Task 6: Final Verification And Cleanup

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run static verification**

Run:

```bash
git diff --check HEAD~4..HEAD
python3 -m py_compile performance-tuning-roadmap/labs/perfshop-p0/app/src/server.py
python3 -m py_compile performance-tuning-roadmap/labs/perfshop-p0/downstream/src/server.py
cd performance-tuning-roadmap/labs/perfshop-p0
docker compose config >/tmp/perfshop-p1-mini-compose-final.yml
```

Expected: all commands exit `0`.

- [ ] **Step 2: Run runtime verification**

Run:

```bash
cd performance-tuning-roadmap/labs/perfshop-p0
docker compose up --build -d
curl -fsS http://localhost:8080/health
curl -fsS http://localhost:8081/health
curl -fsS -H "X-Trace-Id: final-product" http://localhost:8080/api/products/1
curl -fsS -H "X-Trace-Id: final-rec" http://localhost:8080/api/recommendations/1
curl -fsS http://localhost:8080/metrics | rg -n "redis_operation_duration_seconds|app_downstream_requests_total|app_downstream_request_duration_seconds"
curl -fsS http://localhost:8081/metrics | rg -n "downstream_http_requests_total|downstream_http_request_duration_seconds"
curl -fsS -X POST "http://localhost:8080/chaos/redis-big-key?enabled=true"
curl -fsS -X POST "http://localhost:8080/chaos/redis-slow?enabled=true"
curl -fsS http://localhost:8080/api/products/1 >/tmp/perfshop-final-product.json
curl -fsS -X POST "http://localhost:8080/chaos/downstream-delay?delay_ms=1000"
curl -sS -o /tmp/perfshop-final-rec-delay.json -w "%{http_code}\n" http://localhost:8080/api/recommendations/1
curl -fsS -X POST "http://localhost:8080/chaos/retry-storm?enabled=true"
curl -sS -o /tmp/perfshop-final-rec-retry.json -w "%{http_code}\n" http://localhost:8080/api/recommendations/1
curl -fsS -X POST "http://localhost:8080/chaos/reset"
docker compose logs app downstream | rg -n "final-product|final-rec|trace_id"
docker compose down
```

Expected:

- Health checks return JSON `{"status": "ok"}`.
- Product request returns product JSON.
- Recommendation request returns recommendation JSON before chaos.
- App metrics include Redis and app downstream metrics.
- Downstream metrics include downstream HTTP metrics.
- Chaos calls return JSON responses.
- Delay/retry recommendation calls may return `200` or `502`; either status is acceptable when timeout is the behavior under test.
- Logs contain JSON entries with the supplied trace IDs.
- `docker compose down` exits `0`.

- [ ] **Step 3: Confirm README and lab contract alignment**

Run:

```bash
rg -n "P1-mini|perfshop-p0|Redis|downstream|retry storm|trace_id" performance-tuning-roadmap/LAB-CONTRACT.md performance-tuning-roadmap/labs/perfshop-p0/README.md
```

Expected: both roadmap contract and lab README refer to P1-mini concepts consistently.

- [ ] **Step 4: Inspect final status**

Run:

```bash
git status --short
git log --oneline -5
```

Expected: status is clean after commits; the recent log includes the P1-mini infra, downstream, app behavior, and README commits.
