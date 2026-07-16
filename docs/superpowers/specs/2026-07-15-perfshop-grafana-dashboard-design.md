# PerfShop Grafana Dashboard Provisioning Design

## Goal

Make the PerfShop observability lab runnable without manually creating Grafana panels. Starting or restarting Grafana must automatically load one version-controlled dashboard. The tutorial must also provide copyable baseline and chaos-test commands.

## Scope

Included:

- Provision one Grafana dashboard from files in the repository.
- Reuse the existing Prometheus datasource.
- Cover HTTP, database, process, Redis, and downstream signals already exposed by PerfShop.
- Add README commands for baseline load, each chaos scenario, reset, and expected observations.
- Document the restart command required after dashboard changes.

Excluded:

- New application metrics.
- Alert rules and notification channels.
- Loki, tracing, Kubernetes, or external exporters.
- Grafana API-based deployment.

## File Layout

```text
performance-tuning-roadmap/labs/perfshop-p0/grafana/provisioning/
├── datasources/
│   └── datasources.yml
└── dashboards/
    ├── provider.yml
    └── perfshop-overview.json
```

The existing Compose volume already mounts the complete `provisioning` directory at `/etc/grafana/provisioning:ro`. No image rebuild or additional volume is required.

## Provisioning

`provider.yml` defines a file provider that reads dashboard JSON from `/etc/grafana/provisioning/dashboards`. Grafana reads the provider at startup. After repository files change, the documented refresh command is:

```bash
docker compose restart grafana
```

The Prometheus datasource receives a stable UID. Dashboard panels reference that UID, avoiding name-dependent datasource resolution.

The dashboard receives a stable UID and title so restart does not create duplicates.

## Dashboard

One dashboard, `PerfShop Overview`, groups panels into four rows.

### Service and HTTP

- Service availability: `up` for Prometheus, App, and Downstream.
- HTTP QPS grouped by normalized `path`.
- HTTP 5xx request rate grouped by `path`.
- HTTP P95 latency grouped by `path`.
- HTTP P99 latency grouped by `path`.

### Database

- DB query QPS grouped by `query`.
- DB average latency grouped by `query`, calculated as duration sum rate divided by count rate.
- DB P95 latency grouped by `query`.

### Process and Redis

- App process CPU usage rate.
- App resident memory.
- Redis operation P95 latency grouped by `operation`.

### Downstream

- Downstream request QPS grouped by `status` or `target` where available.
- Downstream error request rate.
- Downstream retry rate.
- Downstream request P95 latency.

Latency panels use milliseconds for display while Prometheus values remain seconds. Rate windows use one minute for responsive labs; percentile panels may use five minutes where needed for stable histogram estimates.

## Tutorial Commands

The README gains a single runbook section containing:

1. Start services and verify Prometheus targets.
2. Restart Grafana after dashboard-file changes.
3. Generate baseline load with `wrk`.
4. Run slow-DB chaos and compare DB QPS, average latency, and P95.
5. Run CPU chaos and compare CPU, HTTP QPS, and P99.
6. Run Redis slow/big-key chaos and compare Redis latency and App behavior.
7. Run downstream-delay and retry-storm chaos and compare downstream latency, errors, retries, and App P99.
8. Reset all chaos after every experiment.

Each scenario states which panels should change and what evidence to record. Commands use complete `curl` and `wrk` invocations rather than shorthand HTTP descriptions.

## Error Handling

- Missing data produces empty panels; it must not prevent Grafana startup.
- Provisioning syntax errors appear in Grafana container logs.
- Dashboard queries use only metrics already exposed by App and Downstream.
- Dashboard panels avoid high-cardinality labels beyond existing normalized `path`, `query`, `operation`, `target`, and `status` values.

## Verification

Static checks:

```bash
docker compose config
python -m json.tool grafana/provisioning/dashboards/perfshop-overview.json
```

Runtime checks:

1. Restart Grafana.
2. Confirm Grafana health endpoint succeeds.
3. Confirm `PerfShop Overview` exists through Grafana search API or UI.
4. Generate baseline traffic and confirm HTTP and DB panels receive data.
5. Trigger one chaos scenario and confirm its expected series appears.
6. Reset chaos and confirm recovery.

## Success Criteria

- Fresh `docker compose up` automatically creates the dashboard.
- Existing environments load it after `docker compose restart grafana`.
- No manual panel or datasource creation is required.
- README commands are directly executable from the `perfshop-p0` directory.
- Dashboard covers all metrics needed by the existing P0 and P1-mini exercises.
