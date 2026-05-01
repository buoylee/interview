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
