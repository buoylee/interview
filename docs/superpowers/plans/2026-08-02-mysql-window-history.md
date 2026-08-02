# MySQL Authoritative Window History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace polling-derived OLTP windows with bounded runner-authored window history, then complete the report/export S evidence in a seventh fresh runtime.

**Architecture:** The runner appends every completed nonempty one-second window to an immutable bounded `window_history` and includes the complete history in each atomic metrics snapshot and final OLTP result. The controller validates the history, preserves its canonical prefix, ingests every unseen window in sequence, evaluates every newly available rolling-five median, and exact-reconciles the final snapshot with the child result before calibration or success.

**Tech Stack:** Markdown-embedded Python 3.13, `mysql-connector-python==9.7.0` with `use_pure=True`, MySQL 8.0.36, Docker/OrbStack, canonical JSON/SHA-256 evidence, Git worktrees.

## Global Constraints

- Design source: `docs/superpowers/specs/2026-08-02-mysql-window-history-design.md` at commit `9923a0d`.
- Plan 10f is an architecture reset after the sole sixth-run calibration failed on absent control-2 sequence 37. It is not a retry, continuation, or evidence repair of that run.
- The runner is the only authoritative owner of OLTP windows. Controller polling observes snapshots and must never define window membership or silently discard an unseen history suffix.
- Every metrics snapshot and final OLTP result carries complete `window_history` from sequence 1 through the latest published nonempty window.
- History bound: `ceil(duration_seconds / window_seconds) + 1`; a 60-second/1-second trial permits at most 61 records.
- A previously observed history prefix is immutable under canonical JSON. Gap, duplicate, reorder, truncation, mutation, wrong type, latest-record mismatch, or bound overflow fails closed.
- Live rolling evaluation processes every unseen window in sequence. An intermediate rolling breach cannot be masked by a later below-budget window.
- Calibration statistic remains `R_t = median(window_p95_ms[t-4:t+1])`; budget remains `B = 1.5 * max(all current-runtime control R_t values)`.
- No raw one-second latency value may independently abort a trial.
- Error, disk, heartbeat, malformed metrics, source, connector, worker, drain, process, and artifact gates remain immediate and fail closed.
- Pure-client smoke remains excluded from calibration and performance statistics.
- The six stopped runtimes are immutable and must never be resumed or rewritten:
  - `/private/tmp/mysql-senior-scenarios.SJ38zd`
  - `/private/tmp/mysql-senior-scenarios.LxogM8`
  - `/private/tmp/mysql-senior-scenarios.UJXwDE`
  - `/private/tmp/mysql-senior-scenarios.VW9rGt`
  - `/private/tmp/mysql-senior-scenarios.rmovUN`
  - `/private/tmp/mysql-senior-scenarios.LjCY6E`
- The sixth controls and failed calibration are historical evidence only; they cannot become current calibration inputs or a reusable budget.
- Use only `mysql-senior-scenarios-mysql` at `127.0.0.1:33306`; `mysql-primary` must remain exited and untouched.
- Preserve unrelated main-worktree dirt. Stage only files named by the current task.
- Repository edits use `apply_patch`; every measured invocation runs exactly once with no silent retry.
- Do not delete the dedicated container, volume, or any raw runtime until the final whole-branch review accepts all committed evidence.

---

### Task 1: Canonical authoritative-history contract

**Files:**
- Modify: `docs/superpowers/plans/2026-07-30-mysql-senior-scenarios.md`
- Create (ignored test artifact): `.superpowers/sdd/2026-08-02-mysql-window-history/task-1-test.py`
- Create (ignored report): `.superpowers/sdd/2026-08-02-mysql-window-history/task-1-report.md`

**Interfaces:**
- Consumes: canonical runner `run_oltp`, `atomic_json`, `percentile`, bounded drain diagnostics; canonical controller `inspect_metrics`, `new_metrics_tracker`, `rolling_latency_reason`, `reconcile_oltp_result`, `build_latency_calibration`, `canonical_json_equal`.
- Produces:
  - runner `history_limit(duration_seconds: int, window_seconds: float) -> int`
  - runner `build_window_record(status: str, trial_id: str, heartbeat_at_epoch: float, window_seq: int, window_operations: int, window_errors: int, window_p95_ms: float, operations: int, errors: int, active_elapsed_seconds: float, drain_limit_hits: int, max_heartbeat_lateness_ms: float) -> dict`
  - runner `append_window_record(history: list[dict], record: dict, limit: int) -> None`
  - controller `validate_window_history(value, trial_id: str, limit: int) -> list[dict]`
  - controller `ingest_window_history(history: list[dict], tracker: dict, now_monotonic: float) -> tuple[dict, str | None]`
  - tracker fields `accepted_windows`, `rolling_evaluated_windows`, `rolling_breach_window_seq`
  - final child/controller canonical history reconciliation

- [ ] **Step 1: Materialize the canonical runner/controller and write RED tests**

Extract the current canonical runner and controller fences by semantic markers into this plan's workspace. Execute their real functions with stubbed connector/process boundaries. Do not import another plan's ignored test files.

Use exact synthetic records:

```python
def window(trial_id: str, sequence: int, p95: float = 5.0) -> dict:
    return {
        "status": "RUNNING",
        "trial_id": trial_id,
        "heartbeat_at_epoch": 1_900_000_000.0 + sequence,
        "window_seq": sequence,
        "window_operations": 100,
        "window_errors": 0,
        "window_p95_ms": p95,
        "operations": sequence * 100,
        "errors": 0,
        "active_elapsed_seconds": float(sequence),
        "drain_limit_hits": sequence,
        "max_heartbeat_lateness_ms": float(sequence),
    }


def snapshot(trial_id: str, values: list[float]) -> dict:
    history = [
        window(trial_id, sequence, value)
        for sequence, value in enumerate(values, 1)
    ]
    return {
        **history[-1],
        "window_history": history,
    }


def inspect(metrics: dict, tracker: dict) -> tuple[dict, str | None]:
    return controller.inspect_metrics(
        metrics,
        metrics["trial_id"],
        metrics["heartbeat_at_epoch"] + 0.1,
        metrics["active_elapsed_seconds"] + 0.1,
        tracker,
        2.5,
        True,
        60,
        1.0,
    )


def ingest(metrics: dict) -> dict:
    tracker, reason = inspect(metrics, controller.new_metrics_tracker())
    assert reason is None
    return tracker


def exact_pure_connector_contract() -> dict:
    return {
        **controller.connector_environment(),
        "actual_connection_class": (
            f"{controller.MySQLConnection.__module__}."
            f"{controller.MySQLConnection.__qualname__}"
        ),
        "actual_pure": True,
    }


def exact_closed_workers(contract: dict) -> list[dict]:
    return [
        {
            **contract,
            "worker": worker,
            "connection_id": 1_000 + worker,
            "closed": True,
            "close_proof": "is_connected_false",
        }
        for worker in range(1, 5)
    ]


def successful_child(trial_id: str, history: list[dict]) -> dict:
    connector_contract = exact_pure_connector_contract()
    return {
        "status": "SUCCEEDED",
        "mode": "oltp",
        "trial_id": trial_id,
        "operations": history[-1]["operations"],
        "errors": history[-1]["errors"],
        "threads": 4,
        "drain_limit_hits": history[-1]["drain_limit_hits"],
        "max_heartbeat_lateness_ms": history[-1][
            "max_heartbeat_lateness_ms"
        ],
        "connector_contract": connector_contract,
        "worker_connections": exact_closed_workers(connector_contract),
        "window_history_schema": "oltp-window-history-v1",
        "window_history": history,
}
```

The RED suite must include these behaviors:

```python
def test_polling_gap_recovers_every_runner_window():
    tracker = controller.new_metrics_tracker()
    tracker, reason = controller.inspect_metrics(
        snapshot("control-1", [5.0] * 36),
        "control-1", 1_900_000_036.1, 36.1, tracker,
        2.5, True, 60, 1.0,
    )
    assert reason is None
    tracker, reason = controller.inspect_metrics(
        snapshot("control-1", [5.0] * 38),
        "control-1", 1_900_000_038.1, 38.1, tracker,
        2.5, True, 60, 1.0,
    )
    assert reason is None
    assert [item["window_seq"] for item in tracker["accepted_windows"]] \
        == list(range(1, 39))


def test_history_prefix_cannot_change():
    tracker = ingest(snapshot("control-1", [5.0] * 5))
    changed = snapshot("control-1", [5.0] * 6)
    changed["window_history"][2]["window_p95_ms"] = 6.0
    _, reason = inspect(changed, tracker)
    assert reason == "OLTP window history prefix changed"


def test_history_gap_fails_closed():
    metrics = snapshot("control-1", [5.0] * 6)
    del metrics["window_history"][3]
    _, reason = inspect(metrics, controller.new_metrics_tracker())
    assert reason == "OLTP window history is not consecutive"


def test_intermediate_rolling_breach_cannot_be_masked():
    tracker = controller.new_metrics_tracker()
    tracker["accepted_windows"] = [
        window("buffered-1", index, value)
        for index, value in enumerate([1.0, 1.0, 100.0, 100.0], 1)
    ]
    tracker["rolling_evaluated_windows"] = 4
    tracker["accepted_windows"].extend([
        window("buffered-1", 5, 100.0),
        window("buffered-1", 6, 1.0),
        window("buffered-1", 7, 1.0),
    ])
    reason = controller.rolling_latency_reason(
        tracker, {"budget_ms": 50.0}
    )
    assert "window_seq=5" in reason
    assert tracker["rolling_breach_window_seq"] == 5


def test_final_child_history_must_equal_controller_history():
    tracker = ingest(snapshot("control-1", [5.0] * 6))
    child = successful_child("control-1", history=tracker["accepted_windows"][:-1])
    with pytest.raises(RuntimeError, match="window history"):
        controller.reconcile_oltp_result(
            0, child, "control-1", tracker, 60, 1.0
        )
```

Also cover duplicate/reordered/truncated histories, first sequence other than 1, prefix extension with multiple unseen records, top-level latest-field mismatch, cumulative operation/error mismatch, nonadvancing elapsed time, diagnostic regression, history bound 62 for a 60/1.0 contract, missing/non-list history, wrong trial ID, booleans, int/float aliases, strings, nonfinite/negative values, unchanged history within heartbeat grace, final unseen suffix ingestion, and all existing immediate non-latency gates.

- [ ] **Step 2: Run RED and preserve exact failure evidence**

Run:

```bash
uv run --with mysql-connector-python==9.7.0 python \
  .superpowers/sdd/2026-08-02-mysql-window-history/task-1-test.py
```

Expected: failures for missing `window_history` helpers, current one-observation append behavior, polling-gap loss, absent intermediate rolling evaluation, and absent child-history reconciliation. Preserve test names, counts, and representative tracebacks in `task-1-report.md`.

- [ ] **Step 3: Add bounded authoritative history to the runner**

Add exact helpers to the runner fence:

```python
WINDOW_HISTORY_SCHEMA = "oltp-window-history-v1"


def history_limit(duration_seconds: int, window_seconds: float) -> int:
    if (
        isinstance(duration_seconds, bool)
        or not isinstance(duration_seconds, int)
        or duration_seconds < 1
        or isinstance(window_seconds, bool)
        or not isinstance(window_seconds, float)
        or not math.isfinite(window_seconds)
        or window_seconds <= 0.0
    ):
        raise ValueError("window history contract is invalid")
    return math.ceil(duration_seconds / window_seconds) + 1


def build_window_record(
    status: str,
    trial_id: str,
    heartbeat_at_epoch: float,
    window_seq: int,
    window_operations: int,
    window_errors: int,
    window_p95_ms: float,
    operations: int,
    errors: int,
    active_elapsed_seconds: float,
    drain_limit_hits: int,
    max_heartbeat_lateness_ms: float,
) -> dict:
    return {
        "status": status,
        "trial_id": trial_id,
        "heartbeat_at_epoch": heartbeat_at_epoch,
        "window_seq": window_seq,
        "window_operations": window_operations,
        "window_errors": window_errors,
        "window_p95_ms": window_p95_ms,
        "operations": operations,
        "errors": errors,
        "active_elapsed_seconds": active_elapsed_seconds,
        "drain_limit_hits": drain_limit_hits,
        "max_heartbeat_lateness_ms": max_heartbeat_lateness_ms,
    }


def append_window_record(
    history: list[dict], record: dict, limit: int
) -> None:
    expected_sequence = len(history) + 1
    if record.get("window_seq") != expected_sequence:
        raise RuntimeError("runner window history is not consecutive")
    if len(history) >= limit:
        raise RuntimeError("runner window history exceeded its trial bound")
    history.append(record)
```

`build_window_record` returns all twelve fields listed by the design spec and receives already computed exact values. `run_oltp` owns one `window_history=[]` and one immutable `limit=history_limit(duration, window_seconds)`. For every periodic or final nonempty window it must:

```python
record = build_window_record(
    status=publish_status,
    trial_id=trial_id,
    heartbeat_at_epoch=time.time(),
    window_seq=len(window_history) + 1,
    window_operations=len(window_latencies),
    window_errors=window_errors,
    window_p95_ms=percentile(window_latencies, 0.95),
    operations=len(all_latencies),
    errors=all_errors,
    active_elapsed_seconds=time.perf_counter() - started,
    drain_limit_hits=diagnostics["drain_limit_hits"],
    max_heartbeat_lateness_ms=diagnostics["max_heartbeat_lateness_ms"],
)
append_window_record(window_history, record, limit)
atomic_json(metrics_file, {**record, "window_history": window_history})
```

Build the final partial record before constructing the final OLTP result. Add:

```python
"window_history_schema": WINDOW_HISTORY_SCHEMA,
"window_history": [dict(record) for record in window_history],
```

to successful and failed OLTP evidence. The shared `oltp_diagnostics` object carries the live history so an exception after publication cannot erase it. Do not add a legacy absence default.

- [ ] **Step 4: Validate and ingest complete histories in the controller**

Add the identical schema name and an exact field set:

```python
WINDOW_HISTORY_SCHEMA = "oltp-window-history-v1"
WINDOW_RECORD_FIELDS = {
    "status", "trial_id", "heartbeat_at_epoch", "window_seq",
    "window_operations", "window_errors", "window_p95_ms",
    "operations", "errors", "active_elapsed_seconds",
    "drain_limit_hits", "max_heartbeat_lateness_ms",
}
```

`validate_window_history` must validate every record independently with existing strict integer/float helpers, exact key set, status in `RUNNING/SUCCEEDED/FAILED`, matching trial ID, positive nonempty window, consecutive sequence, cumulative reconciliation, strictly advancing active elapsed time, and nonregressing diagnostics. It rejects a history longer than `math.ceil(duration_seconds / window_seconds) + 1`.

`ingest_window_history` must use canonical JSON equality for the previously accepted prefix:

```python
accepted = tracker["accepted_windows"]
if len(history) < len(accepted):
    return dict(tracker), "OLTP window history truncated"
if not canonical_json_equal(history[:len(accepted)], accepted):
    return dict(tracker), "OLTP window history prefix changed"
updated = dict(tracker)
updated["accepted_windows"] = [dict(item) for item in history]
updated["activity_windows"] = sum(
    1 for item in history if item["status"] == "RUNNING"
)
```

Update `inspect_metrics` to accept `duration_seconds` and `window_seconds`, validate top-level status/heartbeat, validate complete history, require exact canonical equality between the last record and the top-level latest-window/cumulative fields, and ingest the unseen suffix. It no longer synthesizes one accepted record from the latest snapshot. Repeated snapshots retain heartbeat/nonadvancing checks.

- [ ] **Step 5: Evaluate every newly available rolling window**

Initialize:

```python
"rolling_evaluated_windows": 0,
"rolling_breach_window_seq": None,
```

Rewrite `rolling_latency_reason` so it resumes from the tracker cursor:

```python
start = max(
    ROLLING_WINDOW_SIZE,
    int(tracker["rolling_evaluated_windows"]) + 1,
)
for end in range(start, len(accepted) + 1):
    current = rolling_five_medians(
        accepted[end - ROLLING_WINDOW_SIZE:end]
    )[-1]
    tracker["rolling_evaluated_windows"] = end
    tracker["rolling_window_p95_ms"] = current
    tracker["rolling_window_count"] = ROLLING_WINDOW_SIZE
    if current > budget:
        tracker["rolling_breach_window_seq"] = accepted[end - 1]["window_seq"]
        return (
            "OLTP rolling-five median P95 "
            f"{current} exceeded {budget} at "
            f"window_seq={accepted[end - 1]['window_seq']}"
        )
return None
```

For controls without a calibration, `ready_for_export` computes the current rolling value over the latest five authoritative records. Export modes call `rolling_latency_reason` after each history ingestion. Raw window P95 remains absent from `gate_reason`.

- [ ] **Step 6: Reconcile the terminal snapshot and child result**

Before normal-path child reconciliation, close/flush the child handles, then
perform one final snapshot ingestion:

```python
final_snapshot = load_metrics_snapshot(metrics_file)
final_metrics = (
    None if final_snapshot is None else final_snapshot.document
)
tracker, terminal_breach = inspect_metrics(
    final_metrics,
    run_id,
    time.time(),
    time.monotonic(),
    tracker,
    args.heartbeat_grace_seconds,
    True,
    args.duration_seconds,
    1.0,
)
if terminal_breach is not None:
    raise RuntimeError(
        f"terminal OLTP metrics breach: {terminal_breach}"
    )
```

This consumes a final suffix published immediately before process exit. Any
terminal metrics breach prevents success.

Extend `reconcile_oltp_result`:

```python
child_history = validate_window_history(
    child.get("window_history"),
    trial_id,
    math.ceil(duration_seconds / window_seconds) + 1,
)
if tracker is None or not canonical_json_equal(
    child_history, tracker.get("accepted_windows")
):
    raise RuntimeError(
        "OLTP child window history does not match controller history"
    )
```

Pass duration/window contract explicitly to reconciliation call sites. Validate `window_history_schema` exactly. Controls, smoke, buffered, and chunked results persist the canonical accepted history; calibration continues consuming `accepted_windows`, now authoritative and necessarily consecutive.

- [ ] **Step 7: Update canonical prose and seventh-run commands**

In Task 10 prose:

- explain the sixth failure as a latest-snapshot observation gap, not a threshold failure;
- mark all six runtimes immutable and prohibit upgrading the sixth controls;
- replace “skip sequence is covered by cumulative deltas” with full-history prefix validation;
- state that polling may skip snapshots but never runner windows;
- require the final-snapshot read before child reconciliation;
- require the seventh fresh runtime and one-shot invocation ledger;
- keep status `READY_UNRUN` until seventh-run completion;
- preserve safety/interference separation and the non-SLO boundary.

Do not edit the feature scenario or run Docker/MySQL in this task.

- [ ] **Step 8: Run GREEN and all current offline regressions**

Run the Task 1 suite, then materialize and compile all five canonical Python fences. Add current-plan regression cases for KILL active-query synchronization, pure-client identity/closure, bounded metrics drain/coherent snapshot evidence, strict calibration reconstruction/type rejection, raw-window exclusion, final metrics suffix ingestion, and existing immediate gates. Do not invoke stale tests from another SDD workspace.

```bash
uv run --with mysql-connector-python==9.7.0 python \
  .superpowers/sdd/2026-08-02-mysql-window-history/task-1-test.py
git diff --check -- \
  docs/superpowers/plans/2026-07-30-mysql-senior-scenarios.md
```

Expected: all tests and five fence compilations pass with no MySQL or Docker access.

- [ ] **Step 9: Commit the canonical correction**

```bash
git add docs/superpowers/plans/2026-07-30-mysql-senior-scenarios.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs(plan): preserve authoritative OLTP windows"
```

The staged path list must contain exactly the canonical plan file. Preserve detailed RED/GREEN, regression, scope, and self-review evidence in the ignored report.

---

### Task 2: Synchronize authoritative history into the scenario

**Files:**
- Modify: `mysql-handson/13-senior-scenarios/04-report-export-isolation.md`
- Create (ignored test artifact): `.superpowers/sdd/2026-08-02-mysql-window-history/task-2-test.py`
- Create (ignored report): `.superpowers/sdd/2026-08-02-mysql-window-history/task-2-report.md`

**Interfaces:**
- Consumes: independently reviewed Task 1 runner/controller/freeze-helper fences and canonical prose.
- Produces: byte-equal scenario programs and a `READY_UNRUN` seventh-run contract.

- [ ] **Step 1: Write semantic RED synchronization tests**

Extract runner, controller, and freeze-audit helper using semantic markers `EXPORT_SQL`, `KILL_PREFLIGHT_SQL`, and the freeze-audit entrypoint. Assert byte equality to the reviewed canonical commit. Assert scenario prose contains:

```text
window_history
ceil(duration_seconds / window_seconds) + 1
polling may skip snapshots but never runner windows
final atomic snapshot
seventh fresh runtime
LjCY6E
READY_UNRUN
```

Assert the scenario still prohibits raw-window abort, sixth evidence repair, budget reuse, and partial performance claims.

- [ ] **Step 2: Run RED**

```bash
uv run python \
  .superpowers/sdd/2026-08-02-mysql-window-history/task-2-test.py
```

Expected: runner/controller equality and authoritative-history prose assertions fail; existing freeze-helper equality and `READY_UNRUN` assertions pass.

- [ ] **Step 3: Mechanically synchronize reviewed content**

Use `apply_patch` to replace the complete runner/controller/helper fences from the reviewed canonical Task 1 commit. Update only report/export prose needed by Plan 10f. Do not edit either README and do not claim live success.

- [ ] **Step 4: Run GREEN and feature regressions**

Run Task 2 tests, the current authoritative-history Task 1 suite against scenario extraction, five canonical/scenario fence compilations, KILL/pure/drain/calibration regression cases, Markdown link checks for the changed scenario, and:

```bash
git diff --check -- \
  mysql-handson/13-senior-scenarios/04-report-export-isolation.md
git diff --name-only
```

Expected tracked scope: exactly one scenario file. Runner/controller/helper are byte-equal to the reviewed canonical commit and status remains `READY_UNRUN`.

- [ ] **Step 5: Commit scenario synchronization**

```bash
git add mysql-handson/13-senior-scenarios/04-report-export-isolation.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs(mysql): preserve authoritative OLTP windows"
```

---

### Task 3: Execute the seventh fresh S experiment

**Files:**
- Modify only after the completion contract passes: `mysql-handson/13-senior-scenarios/04-report-export-isolation.md`
- Modify only after the completion contract passes: `mysql-handson/13-senior-scenarios/README.md` (singular report/export routing row)
- Create (ignored evidence): `.superpowers/sdd/2026-08-02-mysql-window-history/task-3-report.md`

**Interfaces:**
- Consumes: clean reviewed Task 2 feature HEAD, dedicated MySQL container, six immutable stopped runtimes.
- Produces: checksummed seventh-runtime source/history/calibration/export/resume evidence, or a controlled `BLOCKED` result with no documentation commit.

- [ ] **Step 1: Verify ownership, immutability, and resources**

Record exact container name, label, mapped port `33306`, version `8.0.36`, health, restart policy `no`, durability globals, and free disk against `5,419,909,120` bytes. Require `mysql-primary` to be exited without starting or mutating it.

Record ordered tree SHA-256, file count, and byte count for all six stopped runtimes before any write. The sixth manifest must still have SHA-256 `9aa5bdf1b240d6a346056f2eb91bb1889f4a2ffa06a0e1c4634d5219b431c189` and its control-2 accepted sequences must still omit exactly 37. Never modify those files.

- [ ] **Step 2: Create exactly one seventh runtime**

```bash
mktemp -d /private/tmp/mysql-senior-scenarios.XXXXXX
```

Persist the returned path immediately. Extract only committed scenario fences, prove byte equality to the reviewed feature commit, compile under Python 3.13 with Connector/Python 9.7.0, and record program SHA-256. No handwritten wrapper may enter a measured path.

- [ ] **Step 3: Fresh seed, freeze, triggers, and negative probes**

Drop/recreate/reseed exactly 100,000 orders, 300,000 items, and 10,000 probes. Record immutable source fingerprint, high cursor, report aggregate, CRC sums, and a separate ordered probe schema/counter audit. Install exactly six freeze triggers. Run each negative probe once and require errno `1644`, SQLSTATE `45000`, and an unchanged post-probe source manifest.

- [ ] **Step 4: Run KILL and pure-client preflights once**

Run fixed `kill-preflight-1` once. Require the exact marked active query, errno `1317`, victim disappearance, discarded temporary table, and bounded polls.

Run fixed `oltp-smoke-1` once for five seconds/four threads. Require positive operations, zero errors, at least two authoritative windows, consecutive history from sequence 1, exact child/controller history equality, four distinct closed pure-Python connections, and exclusion from calibration statistics. Either failure triggers controlled teardown and `BLOCKED` without retry.

- [ ] **Step 5: Run three controls and calibration once**

Run `control-1`, `control-2`, and `control-3` once each for 60 seconds/four threads. Each must be `SUCCEEDED`, contain 55..61 authoritative windows starting at 1 without gaps, have exact snapshot/controller/child history reconciliation, zero errors, valid worker/connector/drain evidence, and unchanged source/probe checkpoints.

Run `latency-calibration-1` once. Independently reconstruct each history, every rolling-five value, combined count/min/median/P95/P99/max, input SHA-256, noise ratio, and `B=1.5*rolling_max`. Confirm all inputs and runner/controller hashes belong to the seventh runtime. Freeze the artifact and its SHA before exports.

- [ ] **Step 6: Run buffered and chunked matrices once**

Run `buffered-1..3`, then `chunked-1..3`, once per trial. Every controller validates the frozen calibration before opening files or creating `Popen`, ingests all authoritative history suffixes, evaluates each new rolling window, and applies immediate gates.

On any `ABORTED`, stop later trials in that mode and all downstream performance ranking that depends on them. Preserve the exact breach sequence and complete history. Never retry, edit the artifact, or substitute a raw-window threshold.

- [ ] **Step 7: Run interruption/resume and exact artifact audit**

Only when successful buffered and chunked artifact prerequisites exist, run the planned three-batch interruption once and the separate resume once. Audit exactly 100,000 rows, strict `(created_at,id)` order, 100,000 distinct IDs, exact high cursor, business aggregate, and identical SHA-256 across successful buffered, chunked, and resumed artifacts.

- [ ] **Step 8: Controlled teardown and independent audit**

Before documentation edits, compare immutable report source exactly; audit probe rows/schema/counter separately; remove all six explicit triggers; require no child/victim process; prove globals unchanged; prove the dedicated container remains healthy/restart=no; prove `mysql-primary` remains exited; and prove all six stopped-runtime digests unchanged.

Create a complete ordered SHA-256 manifest for every seventh-runtime regular file except the manifest itself, then reverify every entry. Record manifest SHA, file count, byte count, and tree SHA.

- [ ] **Step 9: Patch only complete honest evidence**

Only if every completion prerequisite passes, use `apply_patch` to record environment, authoritative history contract, every control/export trial, calibration formula/current budget/noise ratio, rolling safety outcome, interference outcome, artifact/resume correctness, source/probe checks, teardown, manifest, and limitations. Mark the scenario `SCALED_REPRODUCED (S=100000)` and update only its singular README routing row.

If the run stops early, do not edit either documentation file, do not commit partial performance evidence, and return `BLOCKED` with the preserved runtime/report.

- [ ] **Step 10: Verify and commit evidence**

```bash
git diff --check -- \
  mysql-handson/13-senior-scenarios/04-report-export-isolation.md \
  mysql-handson/13-senior-scenarios/README.md
git add \
  mysql-handson/13-senior-scenarios/04-report-export-isolation.md \
  mysql-handson/13-senior-scenarios/README.md
git diff --cached --name-only
git commit -m "docs(mysql): record authoritative export evidence"
```

The staged list must contain exactly the two permitted documentation files.

---

### Task 4: Final navigation, verification, and integration gate

**Files:**
- Modify only when inconsistent: `mysql-handson/13-senior-scenarios/README.md`
- Modify only when inconsistent: `mysql-handson/README.md`
- Create (ignored report): `.superpowers/sdd/2026-08-02-mysql-window-history/task-4-report.md`

**Interfaces:**
- Consumes: reviewed canonical/scenario commits and complete Task 3 evidence.
- Produces: coherent navigation/status, whole-branch review package, and an integration-ready feature branch.

- [ ] **Step 1: Inventory all status and routing occurrences**

Classify every MySQL navigation/status occurrence for bulk import, online archive, report/export, and HA as canonical routing, summary, evidence label, or historical explanation. Require report/export to say `SCALED_REPRODUCED (S=100000)` only when Task 3 committed complete evidence. Check anchors and ensure no other file claims ownership of the same scenario.

- [ ] **Step 2: Write RED assertions only for real inconsistencies**

If inventory finds a stale row, create exact assertions naming its file and expected replacement. If navigation is already consistent, record read-only proof and make no edit or empty commit.

- [ ] **Step 3: Apply the smallest navigation correction**

Use `apply_patch`, preserve established ordering, and modify only the inconsistent navigation rows. Do not rewrite scenario evidence.

- [ ] **Step 4: Run final static and read-only live verification**

Run current-plan authoritative-history tests, canonical/scenario byte equality, five fence compilations, KILL/pure/drain/calibration regressions, Markdown links, `git diff --check`, changed-file scope, and feature worktree cleanliness. Perform a read-only audit of the dedicated container, source/probes, zero triggers, stopped `mysql-primary`, all seven runtime manifests/digests, and absence of runner/controller processes.

- [ ] **Step 5: Commit navigation only when changed**

```bash
git add mysql-handson/README.md mysql-handson/13-senior-scenarios/README.md
git diff --cached --name-only
git commit -m "docs(mysql): reconcile authoritative export status"
```

Create no empty commit when no correction is necessary.

- [ ] **Step 6: Run the broad whole-branch review and finish**

Generate the required full review package from the feature branch merge base through final HEAD. The final reviewer must inspect all feature commits, task ledger deferred findings, committed evidence claims, navigation, and live manifest/digest proof.

Only after the broad review is clean may this plan's SDD workspace and the exact owned dedicated container/volume be removed. Never delete or mutate `mysql-primary` resources. Then use `superpowers:finishing-a-development-branch` to present integration options.
