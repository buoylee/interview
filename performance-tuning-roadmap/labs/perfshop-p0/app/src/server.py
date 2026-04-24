import json
import os
import resource
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from urllib.parse import parse_qs, urlparse

import mysql.connector


BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]

metrics_lock = Lock()
http_requests = defaultdict(int)
http_duration_buckets = defaultdict(int)
http_duration_sum = defaultdict(float)
http_duration_count = defaultdict(int)
db_duration_buckets = defaultdict(int)
db_duration_sum = defaultdict(float)
db_duration_count = defaultdict(int)

chaos = {
    "cpu_until": 0.0,
    "slow_db": False,
    "slow_downstream_ms": 0,
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
    if path.startswith("/chaos/"):
        return "/chaos/*"
    return path


class Handler(BaseHTTPRequestHandler):
    server_version = "PerfShopP0/0.1"

    def log_message(self, fmt, *args):
        return

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        started = time.perf_counter()
        status = 200
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            burn_cpu_if_enabled()
            maybe_sleep_downstream()
            if path == "/health":
                self.send_json(200, {"status": "ok"})
            elif path == "/metrics":
                self.send_metrics()
            elif path.startswith("/api/products/search"):
                status = self.handle_search(parse_qs(parsed.query))
            elif path.startswith("/api/products/"):
                status = self.handle_product(path)
            else:
                status = 404
                self.send_json(404, {"error": "not found"})
        except Exception as exc:
            status = 500
            self.send_json(500, {"error": str(exc)})
        finally:
            observe_http("GET", normalized_path(path), status, time.perf_counter() - started)

    def do_POST(self):
        started = time.perf_counter()
        status = 200
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            if path == "/chaos/cpu":
                duration = int(query.get("duration", ["60"])[0])
                chaos["cpu_until"] = time.time() + duration
                self.send_json(200, {"cpu_hotspot_enabled_seconds": duration})
            elif path == "/chaos/slow-db":
                enabled = query.get("enabled", ["true"])[0].lower() == "true"
                chaos["slow_db"] = enabled
                self.send_json(200, {"slow_db": enabled})
            elif path == "/chaos/slow-downstream":
                delay_ms = int(query.get("delay_ms", ["1000"])[0])
                chaos["slow_downstream_ms"] = delay_ms
                self.send_json(200, {"slow_downstream_ms": delay_ms})
            elif path == "/chaos/reset":
                chaos["cpu_until"] = 0.0
                chaos["slow_db"] = False
                chaos["slow_downstream_ms"] = 0
                self.send_json(200, {"status": "reset"})
            else:
                status = 404
                self.send_json(404, {"error": "not found"})
        except Exception as exc:
            status = 500
            self.send_json(500, {"error": str(exc)})
        finally:
            observe_http("POST", normalized_path(path), status, time.perf_counter() - started)

    def handle_product(self, path):
        product_id = int(path.rsplit("/", 1)[1])
        rows = run_query(
            "product_by_id",
            "SELECT id, name, category, price, stock FROM products WHERE id = %s",
            (product_id,),
        )
        if not rows:
            self.send_json(404, {"error": "product not found"})
            return 404
        self.send_json(200, rows[0])
        return 200

    def handle_search(self, query):
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
        self.send_json(200, {"count": len(rows), "items": rows})
        return 200

    def send_metrics(self):
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


if __name__ == "__main__":
    wait_for_db()
    port = int(os.getenv("APP_PORT", "8080"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
