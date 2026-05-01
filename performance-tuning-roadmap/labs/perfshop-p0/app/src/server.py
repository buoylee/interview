import json
import os
import resource
import sys
import time
import uuid
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlparse

import mysql.connector
import redis


BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
BIG_KEY_BYTES = 512 * 1024
CACHE_TTL_SECONDS = 60
DOWNSTREAM_TARGET = "recommendations"
REDIS_BIG_KEY = "chaos:big-product-payload"
REDIS_SLOW_SECONDS = 0.1

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
downstream_requests = defaultdict(int)
downstream_duration_buckets = defaultdict(int)
downstream_duration_sum = defaultdict(float)
downstream_duration_count = defaultdict(int)
downstream_retries = defaultdict(int)

chaos_lock = Lock()
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


def redis_config():
    return {
        "host": os.getenv("REDIS_HOST", "127.0.0.1"),
        "port": int(os.getenv("REDIS_PORT", "6379")),
        "db": int(os.getenv("REDIS_DB", "0")),
        "socket_timeout": float(os.getenv("REDIS_SOCKET_TIMEOUT_SECONDS", "0.25")),
        "decode_responses": True,
    }


def connect_db():
    return mysql.connector.connect(**db_config())


redis_client = redis.Redis(**redis_config())


def downstream_base_url():
    return os.getenv("DOWNSTREAM_URL", "http://127.0.0.1:8081").rstrip("/")


def downstream_timeout_seconds():
    return float(os.getenv("DOWNSTREAM_TIMEOUT_SECONDS", "0.35"))


def downstream_retry_attempts():
    try:
        attempts = int(os.getenv("DOWNSTREAM_RETRY_ATTEMPTS", "2"))
    except ValueError:
        attempts = 2
    return min(3, max(0, attempts))


def trace_id_from(headers):
    incoming = headers.get("X-Trace-Id", "").strip()
    return incoming or uuid.uuid4().hex[:16]


def json_log(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


def chaos_snapshot():
    with chaos_lock:
        return dict(chaos)


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


def observe_downstream(target, status, seconds):
    with metrics_lock:
        downstream_requests[(target, str(status))] += 1
        downstream_duration_sum[target] += seconds
        downstream_duration_count[target] += 1
        for bucket in BUCKETS:
            if seconds <= bucket:
                downstream_duration_buckets[(target, bucket)] += 1
        downstream_duration_buckets[(target, "+Inf")] += 1


def observe_downstream_retry(target):
    with metrics_lock:
        downstream_retries[target] += 1


def histogram_sort_key(item):
    labels = item[0]
    bucket = labels[-1]
    bucket_key = (1, float("inf")) if bucket == "+Inf" else (0, float(bucket))
    return labels[:-1] + (bucket_key,)


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


def redis_call(operation, trace_id, func, *args):
    started = time.perf_counter()
    if chaos_snapshot()["redis_slow"]:
        time.sleep(REDIS_SLOW_SECONDS)
    try:
        return func(*args)
    except Exception as exc:
        json_log({
            "service": "app",
            "event": "redis_failure",
            "trace_id": trace_id,
            "operation": operation,
            "error": exc.__class__.__name__,
        })
        raise
    finally:
        observe_redis(operation, time.perf_counter() - started)


def maybe_touch_big_key(trace_id):
    if not chaos_snapshot()["redis_big_key"]:
        return
    try:
        redis_call("get_big_key", trace_id, redis_client.get, REDIS_BIG_KEY)
    except Exception:
        pass


def set_redis_big_key(enabled, trace_id):
    if enabled:
        redis_call("setex_big_key", trace_id, redis_client.setex, REDIS_BIG_KEY, CACHE_TTL_SECONDS, "x" * BIG_KEY_BYTES)
    else:
        redis_call("delete_big_key", trace_id, redis_client.delete, REDIS_BIG_KEY)


class DownstreamRequestError(Exception):
    pass


def downstream_request_json(method, path, trace_id):
    attempts = 1 + (downstream_retry_attempts() if chaos_snapshot()["retry_storm"] else 0)
    last_error = None
    url = downstream_base_url() + path
    for attempt in range(attempts):
        if attempt > 0:
            observe_downstream_retry(DOWNSTREAM_TARGET)
        started = time.perf_counter()
        status_label = "error"
        try:
            data = b"" if method == "POST" else None
            request = urllib.request.Request(url, data=data, method=method, headers={"X-Trace-Id": trace_id})
            with urllib.request.urlopen(request, timeout=downstream_timeout_seconds()) as response:
                status_label = str(response.getcode())
                body = response.read()
            try:
                return json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                status_label = "invalid_json"
                last_error = exc
        except urllib.error.HTTPError as exc:
            status_label = str(exc.code)
            last_error = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            status_label = "error"
            last_error = exc
        finally:
            observe_downstream(DOWNSTREAM_TARGET, status_label, time.perf_counter() - started)

    json_log({
        "service": "app",
        "event": "downstream_failure",
        "trace_id": trace_id,
        "target": DOWNSTREAM_TARGET,
        "method": method,
        "path": path,
        "error": last_error.__class__.__name__ if last_error else "unknown",
    })
    raise DownstreamRequestError()


def parse_int_value(value):
    if value is None or value == "":
        raise ValueError
    return int(value)


def parse_int_param(query, name, default):
    values = query.get(name)
    value = default if values is None else values[0]
    return parse_int_value(value)


def parse_enabled_param(query):
    values = query.get("enabled")
    if values is None:
        return True
    value = values[0].strip().lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError


def parse_path_id(path, prefix):
    value = path[len(prefix):] if path.startswith(prefix) else ""
    if not value or "/" in value:
        raise ValueError
    item_id = parse_int_value(value)
    if item_id <= 0:
        raise ValueError
    return item_id


def burn_cpu_if_enabled():
    with chaos_lock:
        cpu_until = chaos["cpu_until"]
    if time.time() >= cpu_until:
        return
    deadline = time.perf_counter() + 0.05
    value = 0
    while time.perf_counter() < deadline:
        value = (value * 31 + 7) % 1_000_003


def maybe_sleep_downstream():
    with chaos_lock:
        delay_ms = chaos["slow_downstream_ms"]
    if delay_ms > 0:
        time.sleep(delay_ms / 1000)


def normalized_path(path):
    if path in ("/health", "/metrics"):
        return path
    if path == "/api/products/search":
        return "/api/products/search"
    if path.startswith("/api/products/"):
        return "/api/products/{id}"
    if path.startswith("/api/recommendations/"):
        return "/api/recommendations/{product_id}"
    if path.startswith("/chaos/"):
        return "/chaos/*"
    return "/unknown"


class Handler(BaseHTTPRequestHandler):
    server_version = "PerfShopP0/0.1"

    def log_message(self, fmt, *args):
        return

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Trace-Id", self.trace_id)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        started = time.perf_counter()
        status = 200
        self.trace_id = trace_id_from(self.headers)
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            burn_cpu_if_enabled()
            maybe_sleep_downstream()
            if path == "/health":
                self.send_json(200, {"status": "ok"})
            elif path == "/metrics":
                self.send_metrics()
            elif path == "/api/products/search":
                status = self.handle_search(parse_qs(parsed.query))
            elif path.startswith("/api/products/"):
                status = self.handle_product(path)
            elif path.startswith("/api/recommendations/"):
                status = self.handle_recommendations(path)
            else:
                status = 404
                self.send_json(404, {"error": "not found"})
        except Exception:
            status = 500
            self.send_json(500, {"error": "internal server error"})
        finally:
            duration = time.perf_counter() - started
            norm_path = normalized_path(path)
            observe_http("GET", norm_path, status, duration)
            json_log({
                "service": "app",
                "trace_id": self.trace_id,
                "method": "GET",
                "path": norm_path,
                "status": status,
                "duration_ms": round(duration * 1000, 3),
            })

    def do_POST(self):
        started = time.perf_counter()
        status = 200
        self.trace_id = trace_id_from(self.headers)
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query, keep_blank_values=True)
        try:
            if path == "/chaos/cpu":
                status = self.handle_cpu_chaos(query)
            elif path == "/chaos/slow-db":
                status = self.handle_boolean_chaos(query, "slow_db")
            elif path == "/chaos/slow-downstream":
                status = self.handle_slow_downstream_chaos(query)
            elif path == "/chaos/redis-big-key":
                status = self.handle_redis_big_key_chaos(query)
            elif path == "/chaos/redis-slow":
                status = self.handle_boolean_chaos(query, "redis_slow")
            elif path == "/chaos/downstream-delay":
                status = self.handle_downstream_delay_chaos(query)
            elif path == "/chaos/retry-storm":
                status = self.handle_boolean_chaos(query, "retry_storm")
            elif path == "/chaos/reset":
                status = self.handle_reset_chaos()
            else:
                status = 404
                self.send_json(404, {"error": "not found"})
        except Exception:
            status = 500
            self.send_json(500, {"error": "internal server error"})
        finally:
            duration = time.perf_counter() - started
            norm_path = normalized_path(path)
            observe_http("POST", norm_path, status, duration)
            json_log({
                "service": "app",
                "trace_id": self.trace_id,
                "method": "POST",
                "path": norm_path,
                "status": status,
                "duration_ms": round(duration * 1000, 3),
            })

    def handle_product(self, path):
        try:
            product_id = parse_path_id(path, "/api/products/")
        except ValueError:
            self.send_json(400, {"error": "invalid product_id"})
            return 400
        maybe_touch_big_key(self.trace_id)
        cache_key = f"product:{product_id}"
        try:
            cached = redis_call("get", self.trace_id, redis_client.get, cache_key)
        except Exception:
            cached = None
        if cached is not None:
            try:
                self.send_json(200, json.loads(cached))
                return 200
            except json.JSONDecodeError:
                json_log({
                    "service": "app",
                    "event": "redis_decode_failure",
                    "trace_id": self.trace_id,
                    "operation": "get",
                })
        rows = run_query(
            "product_by_id",
            "SELECT id, name, category, price, stock FROM products WHERE id = %s",
            (product_id,),
        )
        if not rows:
            self.send_json(404, {"error": "product not found"})
            return 404
        try:
            redis_call(
                "setex",
                self.trace_id,
                redis_client.setex,
                cache_key,
                CACHE_TTL_SECONDS,
                json.dumps(rows[0], ensure_ascii=False, default=str),
            )
        except Exception:
            pass
        self.send_json(200, rows[0])
        return 200

    def handle_search(self, query):
        keyword = query.get("q", ["alpha"])[0]
        with chaos_lock:
            slow_db = chaos["slow_db"]
        if slow_db:
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

    def handle_recommendations(self, path):
        try:
            product_id = parse_path_id(path, "/api/recommendations/")
        except ValueError:
            self.send_json(400, {"error": "invalid product_id"})
            return 400
        try:
            payload = downstream_request_json("GET", f"/api/recommendations/{product_id}", self.trace_id)
        except DownstreamRequestError:
            self.send_json(502, {"error": "downstream unavailable"})
            return 502
        self.send_json(200, payload)
        return 200

    def handle_cpu_chaos(self, query):
        try:
            duration = parse_int_param(query, "duration", "60")
        except ValueError:
            self.send_json(400, {"error": "invalid duration"})
            return 400
        if duration < 0:
            self.send_json(400, {"error": "invalid duration"})
            return 400
        with chaos_lock:
            chaos["cpu_until"] = time.time() + duration
        self.send_json(200, {"cpu_hotspot_enabled_seconds": duration})
        return 200

    def handle_slow_downstream_chaos(self, query):
        try:
            delay_ms = parse_int_param(query, "delay_ms", "1000")
        except ValueError:
            self.send_json(400, {"error": "invalid delay_ms"})
            return 400
        if delay_ms < 0:
            self.send_json(400, {"error": "invalid delay_ms"})
            return 400
        with chaos_lock:
            chaos["slow_downstream_ms"] = delay_ms
        self.send_json(200, {"slow_downstream_ms": delay_ms})
        return 200

    def handle_boolean_chaos(self, query, key):
        try:
            enabled = parse_enabled_param(query)
        except ValueError:
            self.send_json(400, {"error": "invalid enabled"})
            return 400
        with chaos_lock:
            chaos[key] = enabled
        self.send_json(200, {key: enabled})
        return 200

    def handle_redis_big_key_chaos(self, query):
        try:
            enabled = parse_enabled_param(query)
        except ValueError:
            self.send_json(400, {"error": "invalid enabled"})
            return 400
        with chaos_lock:
            chaos["redis_big_key"] = enabled
        try:
            set_redis_big_key(enabled, self.trace_id)
        except Exception:
            pass
        self.send_json(200, {"redis_big_key": enabled})
        return 200

    def handle_downstream_delay_chaos(self, query):
        try:
            delay_ms = parse_int_param(query, "delay_ms", "1000")
        except ValueError:
            self.send_json(400, {"error": "invalid delay_ms"})
            return 400
        if delay_ms < 0:
            self.send_json(400, {"error": "invalid delay_ms"})
            return 400
        try:
            payload = downstream_request_json("POST", f"/chaos/delay?delay_ms={delay_ms}", self.trace_id)
        except DownstreamRequestError:
            self.send_json(502, {"error": "downstream unavailable"})
            return 502
        self.send_json(200, payload)
        return 200

    def handle_reset_chaos(self):
        with chaos_lock:
            chaos["cpu_until"] = 0.0
            chaos["slow_db"] = False
            chaos["slow_downstream_ms"] = 0
            chaos["redis_big_key"] = False
            chaos["redis_slow"] = False
            chaos["retry_storm"] = False
        try:
            set_redis_big_key(False, self.trace_id)
        except Exception:
            pass
        downstream_reset = True
        try:
            downstream_request_json("POST", "/chaos/reset", self.trace_id)
        except DownstreamRequestError:
            downstream_reset = False
        self.send_json(200, {"status": "reset", "downstream_reset": downstream_reset})
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
            for (method, path, bucket), value in sorted(http_duration_buckets.items(), key=histogram_sort_key):
                lines.append(f'http_request_duration_seconds_bucket{{method="{method}",path="{path}",le="{bucket}"}} {value}')
            for (method, path), value in sorted(http_duration_sum.items()):
                lines.append(f'http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {value}')
                lines.append(f'http_request_duration_seconds_count{{method="{method}",path="{path}"}} {http_duration_count[(method, path)]}')

            lines.extend([
                "# HELP db_query_duration_seconds Database query duration.",
                "# TYPE db_query_duration_seconds histogram",
            ])
            for (query_name, bucket), value in sorted(db_duration_buckets.items(), key=histogram_sort_key):
                lines.append(f'db_query_duration_seconds_bucket{{query="{query_name}",le="{bucket}"}} {value}')
            for query_name, value in sorted(db_duration_sum.items()):
                lines.append(f'db_query_duration_seconds_sum{{query="{query_name}"}} {value}')
                lines.append(f'db_query_duration_seconds_count{{query="{query_name}"}} {db_duration_count[query_name]}')

            lines.extend([
                "# HELP redis_operation_duration_seconds Redis operation duration.",
                "# TYPE redis_operation_duration_seconds histogram",
            ])
            for (operation, bucket), value in sorted(redis_duration_buckets.items(), key=histogram_sort_key):
                lines.append(f'redis_operation_duration_seconds_bucket{{operation="{operation}",le="{bucket}"}} {value}')
            for operation, value in sorted(redis_duration_sum.items()):
                lines.append(f'redis_operation_duration_seconds_sum{{operation="{operation}"}} {value}')
                lines.append(f'redis_operation_duration_seconds_count{{operation="{operation}"}} {redis_duration_count[operation]}')

            lines.extend([
                "# HELP app_downstream_requests_total Total app downstream requests.",
                "# TYPE app_downstream_requests_total counter",
            ])
            for (target, status), value in sorted(downstream_requests.items()):
                lines.append(f'app_downstream_requests_total{{target="{target}",status="{status}"}} {value}')

            lines.extend([
                "# HELP app_downstream_request_duration_seconds App downstream request duration.",
                "# TYPE app_downstream_request_duration_seconds histogram",
            ])
            for (target, bucket), value in sorted(downstream_duration_buckets.items(), key=histogram_sort_key):
                lines.append(f'app_downstream_request_duration_seconds_bucket{{target="{target}",le="{bucket}"}} {value}')
            for target, value in sorted(downstream_duration_sum.items()):
                lines.append(f'app_downstream_request_duration_seconds_sum{{target="{target}"}} {value}')
                lines.append(f'app_downstream_request_duration_seconds_count{{target="{target}"}} {downstream_duration_count[target]}')

            lines.extend([
                "# HELP app_downstream_retries_total Total app downstream retries.",
                "# TYPE app_downstream_retries_total counter",
            ])
            for target, value in sorted(downstream_retries.items()):
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
        self.send_header("X-Trace-Id", self.trace_id)
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
            redis_call("ping", "startup", redis_client.ping)
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("redis did not become ready")


if __name__ == "__main__":
    wait_for_db()
    wait_for_redis()
    port = int(os.getenv("APP_PORT", "8080"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
