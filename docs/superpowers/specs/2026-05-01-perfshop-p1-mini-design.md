# PerfShop P1-mini Design

## Context

The current PerfShop P0 lab lives at `performance-tuning-roadmap/labs/perfshop-p0/`.

P0 already provides:

- A Python standard-library HTTP app.
- MySQL with product data and slow-query scenarios.
- Prometheus text-format metrics.
- Grafana provisioning.
- wrk and Locust load scripts.
- Chaos toggles for CPU hotspot, slow DB, and downstream waiting.

The new roadmap documentation now defines:

- P0 as the currently runnable minimum loop.
- P1 as the next multi-component debugging loop.
- P2 as the full Java / Go / Python symmetric PerfShop target state.

P1-mini should make the next learning step real without turning the lab into a full microservice platform.

## Goal

Extend the existing Python P0 lab into a runnable P1-mini environment that teaches cross-component performance debugging:

```text
single-service issue -> Redis latency -> downstream latency -> retry amplification
```

The learner should be able to run the lab, trigger a problem, observe it in metrics and logs, disable it, and compare before/after behavior.

## Non-Goals

- Do not migrate the app to FastAPI or another web framework.
- Do not add Java / Go / Python three-language services.
- Do not add Kafka.
- Do not add OpenTelemetry SDK or Jaeger.
- Do not add Loki.
- Do not build a production-grade tracing platform.
- Do not turn Redis client pooling into a full production design lesson.

## Chosen Approach

Use the existing Python standard-library P0 service and add only the minimum P1-mini components:

- Redis container.
- Mock downstream container.
- Lightweight trace ID propagation through request headers, response headers, and JSON logs.
- Redis cache-aside path and Redis chaos toggles.
- Downstream call path and retry-storm toggle.
- Metrics for Redis operations, downstream calls, and downstream retries.
- README scenarios for the three new P1-mini exercises.

This keeps the lab runnable and focused while giving learners the cross-component evidence needed for senior backend and SRE interviews.

## File Changes

### Modify `performance-tuning-roadmap/labs/perfshop-p0/docker-compose.yml`

Add:

- `redis` service.
- `downstream` service.
- App environment variables for Redis and downstream URL.
- Prometheus scrape support for downstream if it exposes `/metrics`.

Keep existing MySQL, app, Prometheus, and Grafana services.

### Modify `performance-tuning-roadmap/labs/perfshop-p0/app/requirements.txt`

Add Redis client dependency.

### Modify `performance-tuning-roadmap/labs/perfshop-p0/app/src/server.py`

Add:

- Trace ID extraction/generation:
  - Read `X-Trace-Id` if present.
  - Generate a new trace ID if absent.
  - Return `X-Trace-Id` on responses.
  - Log one JSON line per request.
- Redis helpers:
  - Connect to Redis.
  - Cache product lookup results.
  - Observe Redis operation duration.
  - Support Redis big-key and slow-path chaos.
- Downstream helpers:
  - Call downstream recommendation endpoint.
  - Apply timeout.
  - Optionally retry without backoff when retry-storm mode is enabled.
  - Observe downstream duration, count, and retries.
- New routes:
  - `GET /api/recommendations/{product_id}`
  - `POST /chaos/redis-big-key?enabled=true`
  - `POST /chaos/redis-slow?enabled=true`
  - `POST /chaos/downstream-delay?delay_ms=1000`
  - `POST /chaos/retry-storm?enabled=true`
- Extend `POST /chaos/reset` to clear all new chaos flags.

### Create `performance-tuning-roadmap/labs/perfshop-p0/downstream/`

Files:

- `downstream/Dockerfile`
- `downstream/requirements.txt`
- `downstream/src/server.py`

The downstream service should remain minimal:

- Python standard-library HTTP server.
- `GET /health`
- `GET /metrics`
- `GET /api/recommendations/{product_id}`
- `POST /chaos/delay?delay_ms=1000`
- `POST /chaos/reset`

It should emit simple metrics for request count and duration so learners can compare app entrance QPS with downstream QPS during retry storm.

### Modify `performance-tuning-roadmap/labs/perfshop-p0/prometheus/prometheus.yml`

Add downstream scrape target if downstream exposes `/metrics`.

### Modify `performance-tuning-roadmap/labs/perfshop-p0/README.md`

Add:

- P1-mini scope statement.
- New service list including Redis and downstream.
- New endpoints.
- New metrics.
- Three P1-mini exercises.
- Explicit note that P1-mini still excludes Kafka, Jaeger, OpenTelemetry, Loki, and P2 three-language symmetry.

## Interface Design

### App Routes

```text
GET  /health
GET  /metrics
GET  /api/products/{id}
GET  /api/products/search?q=...
GET  /api/recommendations/{product_id}
POST /chaos/cpu?duration=60
POST /chaos/slow-db?enabled=true
POST /chaos/slow-downstream?delay_ms=1000
POST /chaos/redis-big-key?enabled=true
POST /chaos/redis-slow?enabled=true
POST /chaos/downstream-delay?delay_ms=1000
POST /chaos/retry-storm?enabled=true
POST /chaos/reset
```

Existing P0 routes remain valid.

`/chaos/slow-downstream` may be retained for backward compatibility, but new P1-mini docs should prefer `/chaos/downstream-delay`.

### Downstream Routes

```text
GET  /health
GET  /metrics
GET  /api/recommendations/{product_id}
POST /chaos/delay?delay_ms=1000
POST /chaos/reset
```

### Trace ID Behavior

For every app request:

- If request has `X-Trace-Id`, use it.
- Otherwise generate a short unique ID.
- Include the trace ID in response header `X-Trace-Id`.
- Forward the same trace ID to downstream via `X-Trace-Id`.
- Include the trace ID in app JSON logs.
- Include the trace ID in downstream JSON logs.

This is not full distributed tracing. It is a lightweight correlation mechanism suitable for P1-mini.

## Metrics

Keep existing P0 metrics and add:

```text
redis_operation_duration_seconds_bucket{operation}
redis_operation_duration_seconds_count{operation}
redis_operation_duration_seconds_sum{operation}

app_downstream_request_duration_seconds_bucket{target}
app_downstream_request_duration_seconds_count{target}
app_downstream_request_duration_seconds_sum{target}
app_downstream_requests_total{target,status}
app_downstream_retries_total{target}

downstream_http_requests_total{method,path,status}
downstream_http_request_duration_seconds_bucket{method,path}
downstream_http_request_duration_seconds_count{method,path}
downstream_http_request_duration_seconds_sum{method,path}
```

App-level downstream metrics describe outbound dependency calls. Downstream service metrics describe traffic received by the downstream service. Keeping these names separate lets learners compare entrance traffic with dependency traffic during retry-storm scenarios without overloading one metric name.

## Chaos Behavior

### Redis Big Key

`POST /chaos/redis-big-key?enabled=true`

Expected behavior:

- Enable a mode where product lookup reads or writes a large Redis value.
- This should be large enough to make latency visible in metrics but not large enough to destabilize the developer machine.
- Disabling the flag or calling `/chaos/reset` returns to normal behavior.

### Redis Slow Path

`POST /chaos/redis-slow?enabled=true`

Expected behavior:

- Simulate a Redis slow path through controlled delay or intentionally inefficient scan-like work.
- Avoid dangerous unbounded commands.
- Emit higher `redis_operation_duration_seconds` values while enabled.

### Downstream Delay

`POST /chaos/downstream-delay?delay_ms=1000`

Expected behavior:

- The app configures the downstream service by calling downstream `POST /chaos/delay?delay_ms=...` through `DOWNSTREAM_URL`.
- Calling app `/chaos/reset` also calls downstream `/chaos/reset`.
- `/api/recommendations/{product_id}` becomes slower.
- App and downstream logs share the same trace ID.

### Retry Storm

`POST /chaos/retry-storm?enabled=true`

Expected behavior:

- App retries downstream calls without backoff while enabled.
- Retry count is deliberately small and bounded to protect the local environment.
- `app_downstream_retries_total` grows.
- `downstream_http_requests_total` grows faster than app entrance request count for `/api/recommendations/{product_id}`.

## P1-mini Exercises

### Exercise 1: Redis Slow Path / Big Key

```text
POST /chaos/redis-big-key?enabled=true
wrk /api/products/1
Prometheus shows redis_operation_duration_seconds rising
App logs show trace_id for slow requests
POST /chaos/reset
Repeat load and compare
```

Learning goals:

- Distinguish app latency, DB latency, and Redis latency.
- Explain cache-aside as a trade-off, not free performance.
- Use metrics and trace-id logs to prove Redis involvement.

### Exercise 2: Downstream Timeout

```text
POST /chaos/downstream-delay?delay_ms=1000
wrk /api/recommendations/1
Prometheus shows app_downstream_request_duration_seconds rising
App P99 rises
Use trace_id in app and downstream logs to connect the call
```

Learning goals:

- Explain how downstream waiting inflates upstream latency.
- Distinguish entrance latency from dependency latency.
- Motivate timeout and fallback.

### Exercise 3: Retry Storm

```text
POST /chaos/downstream-delay?delay_ms=1000
POST /chaos/retry-storm?enabled=true
wrk /api/recommendations/1
Prometheus shows app_downstream_retries_total rising
Downstream QPS exceeds entrance QPS
POST /chaos/reset
Repeat load and compare
```

Learning goals:

- Explain how retries amplify traffic.
- Prove amplification with entrance and downstream request counts.
- Motivate exponential backoff, jitter, rate limiting, and circuit breakers.

## Acceptance Criteria

- `docker compose up --build` from `performance-tuning-roadmap/labs/perfshop-p0/` starts app, MySQL, Redis, downstream, Prometheus, and Grafana.
- `GET /health` returns OK for app and downstream.
- `GET /metrics` returns existing P0 metrics plus Redis/downstream metrics after relevant calls.
- `GET /api/products/1` works with Redis cache-aside.
- `GET /api/recommendations/1` calls downstream and returns a response.
- App response includes `X-Trace-Id`.
- App logs include JSON lines containing `trace_id`, method, path, status, and duration.
- Downstream logs include the same propagated `trace_id`.
- Redis big-key or slow-path chaos can be enabled, observed, reset, and retested.
- Downstream delay chaos can be enabled, observed, reset, and retested.
- Retry-storm chaos can be enabled, observed, reset, and retested.
- README documents the P1-mini scope and clearly states excluded P2 features.

## Risks And Controls

| Risk | Control |
| --- | --- |
| P1-mini grows into P2 | Exclude Kafka, Jaeger, OTel, Loki, and three-language services |
| Retry storm overwhelms local machine | Bound retry count and document the setting as intentionally unsafe for production |
| Redis big key destabilizes memory | Use a moderate fixed payload size and reset path |
| Hand-written metrics become messy | Reuse existing histogram helper patterns and keep metric names limited |
| Trace ID is confused with full tracing | README explicitly states this is log correlation, not OpenTelemetry |

## Verification Strategy

Verification should include:

- Static checks:
  - `docker compose config`
  - file existence checks for downstream files
  - grep for required endpoints and metrics
- Runtime checks:
  - `docker compose up --build`
  - app `/health`
  - downstream `/health`
  - app `/api/products/1`
  - app `/api/recommendations/1`
  - app `/metrics` after Redis/downstream calls
  - chaos enable/reset calls
- Documentation checks:
  - README includes P1-mini scope, scenarios, and non-goals.
  - LAB-CONTRACT remains accurate.
