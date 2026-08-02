# MySQL Report Export Authoritative Window History Design

**Date:** 2026-08-02

**Status:** APPROVED_DRAFT

## 1. Problem and evidence

The sixth fresh report/export experiment used the reviewed rolling-five
calibration contract. Seed/freeze, six negative probes, the KILL preflight,
the pure-client smoke, and all three controls succeeded. The sole
`latency-calibration-1` invocation nevertheless failed because `control-2`
contained 59 controller observations spanning window sequences 1 through 60,
with sequence 37 absent.

The failure is architectural rather than a noisy threshold result:

- the runner atomically replaces one latest metrics document;
- controller polling can legitimately observe sequence 36 and then sequence
  38;
- `inspect_metrics` accepts that skip when cumulative deltas cover the latest
  window;
- the overwritten sequence-37 document, including its per-window P95, cannot
  be reconstructed from cumulative counters;
- calibration correctly rejects the resulting nonconsecutive
  `accepted_windows`.

The sixth runtime
`/private/tmp/mysql-senior-scenarios.LjCY6E` remains immutable failed evidence.
It has no calibration artifact or budget, and no export or resume trial was
started. The next live experiment is a seventh fresh runtime, not a retry or
continuation of the sixth.

## 2. Decision

The runner becomes the sole owner of authoritative per-window truth. Every
atomic metrics snapshot carries the complete ordered `window_history` from
sequence 1 through the latest published nonempty window. The final OLTP result
carries the same complete history.

Controller polling observes snapshots, not windows. When polling skips a
snapshot, the controller ingests every unseen record from the next snapshot's
history. Calibration and live rolling latency gates therefore operate on
runner-authored windows rather than controller observation timing.

This preserves the approved statistic:

```text
R_t = median(window_p95_ms[t-4:t+1])
B   = 1.5 * max(all current-runtime control R_t values)
```

No raw one-second latency value independently aborts a trial.

## 3. Alternatives rejected

### 3.1 Append-only JSONL

An append-only metrics log naturally retains every window, but introduces
partial-line recovery, concurrent tailing, flush policy, and additional write
durability questions inside the measured workload. Those mechanisms add more
complexity than this fixed 60-second experiment requires.

### 3.2 One atomic JSON file per window

Immutable per-window files provide strong auditability, but add directory
scanning, filename ordering, partial-directory completion, cleanup, and
manifest complexity. Sixty files per trial are affordable, but the extra
protocol is unnecessary when a bounded complete history fits in one atomic
snapshot.

### 3.3 Compute over observed windows only

Allowing gaps and computing rolling medians over controller observations would
make the statistic depend on scheduler and polling timing. It would no longer
represent five consecutive workload windows and is therefore rejected.

## 4. Runner contract

### 4.1 Authoritative record

Each completed nonempty window appends one immutable record to
`window_history`. A record contains the exact fields needed to validate the
window and compute rolling latency:

```text
status
trial_id
window_seq
heartbeat_at_epoch
window_operations
window_errors
window_p95_ms
operations
errors
active_elapsed_seconds
drain_limit_hits
max_heartbeat_lateness_ms
```

Field types remain strict. Booleans cannot stand in for integers or floats;
integer and floating-point aliases cannot stand in for fields with a different
declared JSON type; strings, nonfinite numbers, and negative values are
rejected according to the existing field contract.

### 4.2 Append-only prefix

Within one trial:

- the first record has `window_seq=1`;
- every later record has the preceding sequence plus one;
- a published prefix is immutable;
- records are never removed, reordered, replaced, or duplicated;
- cumulative operations and errors are nondecreasing and reconcile with
  adjacent window deltas;
- active elapsed time strictly advances;
- drain and heartbeat-lateness diagnostics never regress;
- the top-level latest-window and cumulative fields exactly equal the final
  history record.

The runner appends a record before publishing the corresponding atomic metrics
snapshot. The final OLTP result contains the exact final history and cannot
claim `SUCCEEDED` without it.

### 4.3 Explicit bound

History is bounded by the immutable trial contract:

```text
max_history = ceil(duration_seconds / window_seconds) + 1
```

For a 60-second trial with one-second windows, at most 61 records are allowed.
The extra slot permits one final nonempty partial window at the termination
boundary. Exceeding the bound is malformed evidence and fails closed.

## 5. Controller contract

### 5.1 Snapshot validation

The controller maintains its previously accepted authoritative history. For
each snapshot it validates:

1. `window_history` is a list with exact typed records.
2. Sequences begin at 1 and are completely consecutive.
3. The history does not exceed the trial-derived bound.
4. The previously accepted history is an exact canonical-JSON prefix of the
   new history.
5. Top-level snapshot fields exactly match the final history record.
6. Heartbeat, trial identity, cumulative values, errors, disk, drain, and
   worker contracts satisfy their existing fail-closed rules.

History truncation, prefix mutation, a gap, a duplicate, a changed historical
record, or a latest-field mismatch is an immediate malformed-metrics breach.
No compatibility adapter or legacy backfill is allowed.

### 5.2 Ingesting unseen windows

When a valid snapshot extends the accepted prefix by multiple records, the
controller ingests the unseen suffix in sequence order. It evaluates the
rolling-five statistic after each appended record. An intermediate breach must
produce the existing timed `ABORTED` outcome even when the final unseen record
returns below budget.

Polling can therefore skip snapshots without skipping runner windows. A
snapshot transition from latest sequence 36 to 38 must deliver and validate
records 37 and 38.

When a snapshot contains no new record, existing heartbeat freshness and
nonadvancing-grace checks still apply. Immediate non-latency gates remain
independent of rolling latency.

### 5.3 Completion reconciliation

After the child exits, the controller validates the final OLTP result and
requires its complete `window_history` to equal the accepted controller
history by canonical JSON. The final cumulative result and last history record
must also reconcile exactly. Missing history, an unseen suffix, changed
history, or type-coercing equality prevents `SUCCEEDED`.

Controller results persist the complete accepted history. Calibration consumes
only three successful current-runtime controls that passed this reconciliation.

## 6. Calibration and export behavior

Calibration continues to require exactly `control-1`, `control-2`, and
`control-3`, each with the reviewed duration, thread count, sampling interval,
pure-client evidence, binding, source checkpoints, zero errors, and at least 55
windows. The histories must start at sequence 1 and be completely consecutive.

The calibration artifact embeds all authoritative input windows, all derived
rolling values, canonical input SHA-256, reconstructed derived fields, and the
current runner/controller binding. Validation reconstructs and exact-compares
the complete artifact before any export file is opened or child process is
created.

Buffered and chunked trials ingest authoritative window histories with the
same algorithm. Rolling latency is a live safety gate. Performance
interference remains a separate post-run conclusion, and the empirical control
envelope is not a production SLO.

## 7. Failure behavior and evidence boundaries

The following remain immediate fail-closed conditions:

- malformed, missing, stale, future, wrong-trial, or rewritten metrics;
- invalid or nonconsecutive authoritative history;
- history truncation or trial-bound overflow;
- errors, disk breach, heartbeat breach, drain-contract breach;
- connector, source, worker, process, or artifact contract breach.

A rolling-five budget breach retains timed `ABORTED` semantics. A raw window
P95 cannot independently abort.

Every measured invocation runs once. A failed control, calibration, export, or
resume is preserved without retry. Downstream work whose prerequisites are
invalid is not started.

The first six runtimes are immutable. In particular, the sixth runtime may be
used only as historical evidence that latest-snapshot polling lost sequence 37;
its controls cannot be upgraded, repaired, or reused as calibration inputs.

## 8. Offline verification

RED/GREEN tests execute the extracted canonical programs and cover:

- polling sequence 36 followed by a snapshot through 38 ingests 37 and 38;
- multiple unseen records are processed in order;
- an intermediate rolling breach aborts even if the last record is below
  budget;
- gaps, duplicates, truncation, prefix mutation, and reordered history fail;
- top-level latest fields that disagree with the last record fail;
- adjacent and cumulative operation/error reconciliation failures fail;
- history-bound overflow fails;
- boolean/numeric aliases, strings, nonfinite and negative fields fail;
- final OLTP history mismatch or unseen suffix prevents success;
- strict three-control histories build and reconstruct calibration;
- raw latency alone does not abort;
- disk, error, heartbeat, KILL, pure-client, drain, source, worker, and artifact
  regressions remain green.

Canonical runner/controller/helper fences are synchronized byte-for-byte into
the scenario only after canonical review passes. Until live evidence completes,
the scenario remains `READY_UNRUN`.

## 9. Seventh fresh live experiment

Only after canonical and scenario changes pass independent review:

1. Record ownership, resources, and all six stopped-runtime digests.
2. Create exactly one seventh fresh runtime and materialize committed fences.
3. Reseed and freeze 100,000 orders, 300,000 items, and 10,000 probes.
4. Run six negative trigger probes once each.
5. Run KILL preflight and pure-client smoke once each.
6. Run three 60-second controls once each.
7. Run one calibration and independently reconstruct its histories, rolling
   values, hash, noise ratio, and budget.
8. Run buffered and chunked matrices once per planned trial.
9. Run planned interruption/resume and exact correctness audit only when its
   prerequisites exist.
10. Teardown triggers and verify source, probes, globals, processes, container,
    old-runtime digests, and the seventh-runtime manifest.
11. Update documentation only when the complete evidence contract passes.

No measured invocation is retried. The dedicated container and volume remain
owned until final whole-branch review accepts the evidence.

## 10. Documentation outcome

Successful completion records the seventh environment, authoritative history
contract, current-runtime calibration, every control/export result, rolling
safety outcome, interference outcome, artifact correctness, resume evidence,
source/probe audits, teardown, manifest, and limitations. The scenario becomes
`SCALED_REPRODUCED (S=100000)` only if its full completion contract passes.

If the seventh run stops early, no partial performance conclusion or success
label is committed. The runtime and report remain evidence for the next design
decision.

## 11. Non-goals

- No production telemetry transport or general-purpose time-series database.
- No unbounded history for arbitrary-duration workloads.
- No compatibility path for the first six runtime schemas.
- No reuse of a historical calibration budget.
- No weakening of KILL, pure-client, source, disk, heartbeat, drain, worker,
  artifact, or no-retry gates.
- No claim that the empirical envelope is a production SLO.
