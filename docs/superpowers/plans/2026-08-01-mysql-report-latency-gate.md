# MySQL Report Export Latency Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the statistically mismatched one-second report-export latency gate with a reviewed rolling-five control envelope, complete the live S matrix in a fresh runtime, and finish the senior-scenario documentation track.

**Architecture:** The existing canonical runner/controller remain embedded in the original MySQL senior-scenarios plan and are synchronized verbatim into the report/export scenario. A new controller calibration mode derives an immutable, same-runtime latency artifact from three successful controls; buffered and chunked trials validate that artifact before `Popen` and enforce the identical rolling-five statistic. Live safety and post-run interference conclusions remain separate.

**Tech Stack:** Markdown-embedded Python 3.13, `mysql-connector-python==9.7.0` with `use_pure=True`, MySQL 8.0.36, Docker/OrbStack, JSON/SHA-256 evidence, Git worktrees.

## Global Constraints

- Design source: `docs/superpowers/specs/2026-08-01-mysql-report-latency-gate-design.md` at commit `0748058`.
- Plan 10e is a new architecture-reset task authorized after the Task 9 five-round breaker; it is not Task 9 fix round 6.
- Calibration statistic: `R_t = median(window_p95_ms[t-4:t+1])`, with five ordered same-trial windows and the existing nearest-rank percentile function.
- Frozen budget: `B = 1.5 * max(all current-runtime control R_t values)`.
- Fifth-run `B=2083.017375 ms` is a regression fixture only; never reuse it as the sixth-run budget.
- No raw one-second latency value may independently abort a trial.
- Error, disk, heartbeat, malformed metrics, source, connector, and worker-contract gates remain immediate and fail closed.
- The pure-client smoke remains excluded from calibration and performance statistics.
- The five stopped runtimes are immutable evidence and must never be resumed or rewritten.
- Use only `mysql-senior-scenarios-mysql` at `127.0.0.1:33306`; `mysql-primary` must remain exited and untouched.
- Preserve unrelated main-worktree dirt. Stage only files named by the current task.
- Repository edits use `apply_patch`; live trials run exactly once with no silent retry.
- Do not delete the dedicated container, volume, or raw runtimes until final review accepts all committed evidence.

---

### Task 1: Canonical rolling-envelope contract

**Files:**
- Modify: `docs/superpowers/plans/2026-07-30-mysql-senior-scenarios.md`
- Create (ignored test artifact): `.superpowers/sdd/2026-08-01-mysql-report-latency-gate/task-1-test.py`
- Create (ignored report): `.superpowers/sdd/2026-08-01-mysql-report-latency-gate/task-1-report.md`

**Interfaces:**
- Consumes: existing controller `percentile`, `inspect_metrics`, `gate_reason`, `ready_for_export`, `experiment_binding`, `atomic_json`, `read_json`, and current result/artifact contracts.
- Produces:
  - `rolling_five_medians(windows: list[dict]) -> list[float]`
  - `build_latency_calibration(control_results: list[dict], binding: dict) -> dict`
  - `validate_latency_calibration(root: Path, binding: dict) -> dict`
  - `trial_contract(args: argparse.Namespace) -> dict`
  - controller mode `latency-calibration` with fixed trial ID `latency-calibration-1`
  - tracker evidence `rolling_window_p95_ms` and `rolling_window_count`

- [ ] **Step 1: Materialize current canonical programs and write RED tests**

Extract the runner/controller fences from the canonical plan into the task workspace. The RED suite must execute real extracted functions and assert:

```python
from pathlib import Path


FIFTH_RUNTIME = Path("/private/tmp/mysql-senior-scenarios.rmovUN")
FIFTH_CONTROL_RESULTS = [
    read_json(FIFTH_RUNTIME / f"controller-result-control-{number}.json")
    for number in (1, 2, 3)
]
CALIBRATION = {"budget_ms": 2083.017375}
SYNTHETIC_BINDING = {
    "runtime_root": "/private/tmp/mysql-senior-scenarios.synthetic",
    "runner_sha256": "1" * 64,
    "controller_sha256": "2" * 64,
    "host": "127.0.0.1",
    "port": 33306,
    "user": "root",
    "database": "mysql_senior_scenarios",
    "requested_use_pure": True,
}
CONTROL_TRIAL_CONTRACT = {
    "duration_seconds": 60,
    "threads": 4,
    "window_seconds": 1.0,
    "export_mode": "none",
    "requested_p95_budget_ms": 0.0,
}


def tracker_with_windows(
    values: list[float], trial_id: str = "buffered-1"
) -> dict:
    return {
        "accepted_windows": [
            {
                "trial_id": trial_id,
                "window_seq": index,
                "window_operations": 1,
                "window_errors": 0,
                "window_p95_ms": value,
            }
            for index, value in enumerate(values, 1)
        ]
    }


def synthetic_pure_oltp_result(trial_id: str) -> dict:
    connector_contract = {
        **controller.connector_environment(),
        "actual_connection_class": (
            f"{controller.MySQLConnection.__module__}."
            f"{controller.MySQLConnection.__qualname__}"
        ),
        "actual_pure": True,
    }
    return {
        "status": "SUCCEEDED",
        "mode": "oltp",
        "trial_id": trial_id,
        "threads": 4,
        "errors": 0,
        "connector_contract": connector_contract,
        "worker_connections": [
            {
                **connector_contract,
                "worker": worker,
                "connection_id": 1000 + worker,
                "closed": True,
                "close_proof": "is_connected_false",
            }
            for worker in range(1, 5)
        ],
    }


def control_result(trial_id: str, values: list[float]) -> dict:
    return {
        "status": "SUCCEEDED",
        "mode": "none",
        "trial_id": trial_id,
        "experiment_binding": SYNTHETIC_BINDING,
        "trial_contract": CONTROL_TRIAL_CONTRACT,
        "accepted_windows": tracker_with_windows(
            values, trial_id
        )["accepted_windows"],
        "oltp_result": synthetic_pure_oltp_result(trial_id),
    }


def test_fifth_controls_reproduce_historical_arithmetic_only():
    per_trial = [
        rolling_five_medians(result["accepted_windows"])
        for result in FIFTH_CONTROL_RESULTS
    ]
    combined = [value for values in per_trial for value in values]
    rolling_max_ms = max(combined)
    budget_ms = rolling_max_ms * 1.5
    assert len(combined) == 167
    assert rolling_max_ms == 1388.678250
    assert budget_ms == 2083.017375


def test_one_raw_window_cannot_abort_before_five_windows():
    tracker = tracker_with_windows([17.607083])
    assert rolling_latency_reason(tracker, CALIBRATION) is None


def test_strict_new_format_controls_build_calibration():
    results = [
        control_result("control-1", [1.0] * 55),
        control_result("control-2", [2.0] * 55),
        control_result("control-3", [3.0] * 55),
    ]
    calibration = build_latency_calibration(results, SYNTHETIC_BINDING)
    assert calibration["rolling_count"] == 153
    assert calibration["rolling_max_ms"] == 3.0
    assert calibration["budget_ms"] == 4.5


def test_rolling_windows_never_cross_trials():
    results = [
        control_result("control-1", [1, 2, 3]),
        control_result("control-2", [100] * 55),
        control_result("control-3", [200] * 55),
    ]
    with pytest.raises(RuntimeError, match="five accepted windows"):
        build_latency_calibration(results, SYNTHETIC_BINDING)


def test_timed_mode_validates_calibration_before_popen():
    with mock.patch.object(controller.subprocess, "Popen") as popen:
        result = invoke_controller(
            runtime_root=empty_runtime,
            trial_id="buffered-1",
            export_mode="buffered",
        )
    assert result["status"] == "FAILED"
    assert "calibration artifact" in result["error"]
    popen.assert_not_called()
```

`invoke_controller` runs the extracted controller `main()` with patched
`sys.argv`; `empty_runtime` is a valid fresh prefixed directory containing the
reviewed runner, controller, smoke result, and no calibration artifact. It
patches only process creation and MySQL observation boundaries, not calibration
or validation functions.

The fifth stopped-runtime fixture is isolated to the historical arithmetic test
above. It directly runs `rolling_five_medians` once per trial, combines only the
three per-trial result lists, and never calls `build_latency_calibration` or
normalizes／backfills legacy fields. Every `build_latency_calibration` test uses
synthetic new-format results with exact ordered IDs, `trial_contract`, current
binding including runner/controller SHA-256, and exact pure-client evidence.
Include a successful strict-builder test, then cover missing/duplicate/reordered
trial IDs, missing trial contracts or controller hashes, fewer than five
windows, nonadvancing sequences, wrong trial IDs, boolean/string/nonfinite/
negative values, changed bindings, changed input hash, changed derived fields,
an existing calibration path, changed duration/thread/window contracts, and
immediate non-latency breaches. Legacy control results must fail strict builder
validation; they are never upgraded into current-runtime calibration inputs.

- [ ] **Step 2: Run RED and preserve the expected failures**

Run:

```bash
uv run python .superpowers/sdd/2026-08-01-mysql-report-latency-gate/task-1-test.py
```

Expected: failures for missing rolling/calibration interfaces and the old raw-window gate accepting `window_p95_ms` directly.

- [ ] **Step 3: Add exact rolling and canonical-hash helpers**

Add these interfaces to the canonical controller fence:

```python
ROLLING_WINDOW_SIZE = 5
LATENCY_MULTIPLIER = 1.5
CALIBRATION_SCHEMA = "report-latency-calibration-v1"
CONTROL_TRIAL_IDS = ("control-1", "control-2", "control-3")


def canonical_json_sha256(value: dict) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def rolling_five_medians(windows: list[dict]) -> list[float]:
    if len(windows) < ROLLING_WINDOW_SIZE:
        raise RuntimeError("control trial has fewer than five accepted windows")
    values = []
    previous_seq = None
    for window in windows:
        sequence = _integer_field(window, "window_seq")
        if previous_seq is not None and sequence != previous_seq + 1:
            raise RuntimeError("control windows are not consecutive")
        previous_seq = sequence
        if _integer_field(window, "window_operations") < 1:
            raise RuntimeError("control window is empty")
        if _integer_field(window, "window_errors") != 0:
            raise RuntimeError("control window contains errors")
        values.append(_float_field(window, "window_p95_ms"))
    return [
        percentile(values[index - ROLLING_WINDOW_SIZE:index], 0.50)
        for index in range(ROLLING_WINDOW_SIZE, len(values) + 1)
    ]
```

Extend `experiment_binding` with the SHA-256 of the canonical controller path
(`Path(__file__).resolve()`), requiring that path to equal
`runtime-root/scenario_controller.py`.

Add an exact trial contract to every controller result:

```python
def trial_contract(args: argparse.Namespace) -> dict:
    return {
        "duration_seconds": args.duration_seconds,
        "threads": args.threads,
        "window_seconds": 1.0,
        "export_mode": args.export_mode,
        "requested_p95_budget_ms": args.p95_budget_ms,
    }
```

The runner command must continue passing `--window-seconds 1.0`; control and
export controller results persist this contract so calibration can reject a
different sampling or workload shape.

- [ ] **Step 4: Build and atomically persist calibration**

Implement `build_latency_calibration` so it validates exactly three ordered
control results with IDs `control-1..3`, `status=SUCCEEDED`, `mode=none`,
matching experiment bindings, exact trial contracts (`60` seconds, `4`
threads, `1.0`-second windows, mode `none`, requested budget `0.0`), zero child
errors, exact pure-client contracts, and at least 55 accepted windows each.
Each control's first accepted sequence must be `1`. Embed all accepted input
windows and each trial's derived rolling values.

Derived fields are:

```python
combined = [value for trial in trials for value in trial["rolling_values_ms"]]
rolling_max = max(combined)
calibration = {
    "schema": CALIBRATION_SCHEMA,
    "formula": "1.5 * max(rolling-5 median(window_p95_ms))",
    "window_size": 5,
    "multiplier": 1.5,
    "experiment_binding": binding,
    "trials": trials,
    "rolling_count": len(combined),
    "rolling_min_ms": min(combined),
    "rolling_median_ms": percentile(combined, 0.50),
    "rolling_p95_ms": percentile(combined, 0.95),
    "rolling_p99_ms": percentile(combined, 0.99),
    "rolling_max_ms": rolling_max,
    "budget_ms": rolling_max * 1.5,
}
calibration["inputs_sha256"] = canonical_json_sha256(
    {"binding": binding, "trials": trials}
)
```

The fixed `latency-calibration` mode writes
`latency-calibration.json` and
`controller-result-latency-calibration-1.json` atomically and fails if either
already exists. It starts no child process.

- [ ] **Step 5: Validate calibration rather than trusting stored derivatives**

`validate_latency_calibration` must read the artifact, re-run all input and
rolling calculations, compare the complete reconstructed object and input
hash, and return it only on exact equality. It validates the current runtime,
runner/controller hashes, non-secret connection binding, `60` seconds, `4`
threads, and one-second windows.

For `buffered` and `chunked`, call it before opening stdout/stderr files or
constructing the first `Popen`. Controls and both preflights must reject a
nonzero CLI `--p95-budget-ms`; export modes also reject nonzero values so the
calibration artifact is the only latency authority.

- [ ] **Step 6: Replace raw-window gating with rolling gating**

Remove latency comparison from `gate_reason`; retain disk and cumulative/window
error checks exactly. Add:

```python
def rolling_latency_reason(tracker: dict, calibration: dict) -> str | None:
    accepted = tracker.get("accepted_windows")
    if not isinstance(accepted, list):
        raise RuntimeError("accepted windows are invalid")
    if len(accepted) < ROLLING_WINDOW_SIZE:
        return None
    current = rolling_five_medians(accepted[-ROLLING_WINDOW_SIZE:])[-1]
    tracker["rolling_window_p95_ms"] = current
    tracker["rolling_window_count"] = ROLLING_WINDOW_SIZE
    budget = _float_field(calibration, "budget_ms")
    if current > budget:
        return f"OLTP rolling-five median P95 {current} exceeded {budget}"
    return None
```

`rolling_five_medians` accepts any positive starting sequence but requires every
following sequence to be consecutive. Calibration separately requires each
control input to start at sequence `1`; a live latest-five slice therefore uses
the same function without weakening the calibration contract.

`ready_for_export` requires five accepted advancing, nonempty windows and a
computed rolling statistic at or below the frozen budget. One rolling breach
keeps the existing timed `ABORTED` behavior. Raw latency never independently
aborts. All immediate non-latency gates remain unchanged.

- [ ] **Step 7: Update canonical prose and commands**

Add the design boundaries verbatim to Task 10:

- run `latency-calibration-1` after all three controls and before any export;
- preserve the full calibration artifact and numeric current-runtime budget;
- remove the old `1.5 * median(final control P95)` command;
- omit nonzero `--p95-budget-ms` from buffered/chunked commands;
- report safety outcome separately from interference outcome;
- report `rolling_max/rolling_median` as the environment-noise ratio;
- state that the empirical envelope is not a production SLO.

- [ ] **Step 8: Run GREEN and every prior offline regression**

Run the new suite plus Task9a, Task10a, Task10b, Task10c, Task10d, all canonical
fence extraction/compile checks, and `git diff --check`. Expected: all PASS,
with no MySQL/Docker access.

- [ ] **Step 9: Commit the canonical plan correction**

```bash
git add docs/superpowers/plans/2026-07-30-mysql-senior-scenarios.md
git commit -m "docs(plan): calibrate report rolling latency"
```

Commit scope must be exactly that one plan file. Preserve the detailed RED,
GREEN, regression, and self-review output in the ignored task report.

---

### Task 2: Synchronize the reviewed architecture reset

**Files:**
- Modify: `mysql-handson/13-senior-scenarios/04-report-export-isolation.md`
- Create (ignored test artifact): `.superpowers/sdd/2026-08-01-mysql-report-latency-gate/task-2-test.py`
- Create (ignored report): `.superpowers/sdd/2026-08-01-mysql-report-latency-gate/task-2-report.md`

**Interfaces:**
- Consumes: reviewed canonical runner/controller/freeze helper and prose from Task 1.
- Produces: feature scenario with byte-equal code fences and `READY_UNRUN` Plan 10e contract.

- [ ] **Step 1: Write RED feature-sync tests**

Extract scenario fences by semantic markers (`EXPORT_SQL`,
`KILL_PREFLIGHT_SQL`, and the freeze-audit helper), never by fence count. Assert
the runner/controller/helper are byte-equal to the reviewed canonical plan and
that scenario prose includes `R_t`, `B = 1.5 * max`, calibration artifact,
safety/interference separation, and the no-reuse boundary.

- [ ] **Step 2: Run RED**

Expected: runner/controller equality and rolling-calibration assertions fail;
all pre-10e KILL/pure/drain contracts still pass.

- [ ] **Step 3: Mechanically synchronize reviewed blocks**

Use `apply_patch` to replace the complete runner/controller/helper fences and
only the report/export scenario prose required by Task 1. Do not modify the
senior-scenarios README and do not claim live evidence.

- [ ] **Step 4: Run GREEN and full feature regressions**

Run Task 1 tests against scenario extraction, all prior scenario harnesses,
five canonical plan fences, Markdown links for the changed scenario, and:

```bash
git diff --check -- mysql-handson/13-senior-scenarios/04-report-export-isolation.md
git diff --name-only
```

Expected tracked scope: one scenario file; status remains `READY_UNRUN`.

- [ ] **Step 5: Commit feature synchronization**

```bash
git add mysql-handson/13-senior-scenarios/04-report-export-isolation.md
git commit -m "docs(mysql): calibrate report rolling latency"
```

---

### Task 3: Execute the sixth fresh S experiment

**Files:**
- Modify: `mysql-handson/13-senior-scenarios/04-report-export-isolation.md`
- Modify: `mysql-handson/13-senior-scenarios/README.md` (only the singular report/export routing row)
- Create (ignored evidence): `.superpowers/sdd/2026-08-01-mysql-report-latency-gate/task-3-report.md`

**Interfaces:**
- Consumes: reviewed Task 2 scenario at a clean feature HEAD.
- Produces: checksummed sixth-runtime evidence, successful/aborted matrix facts, exact artifacts, and committed S evidence only if the completion contract passes.

- [ ] **Step 1: Preflight ownership and resources**

Verify the dedicated container name, label, port `33306`, version `8.0.36`,
restart policy `no`, disk formula `5,419,909,120` bytes, and that
`mysql-primary` is exited. Record SHA-256 tree digests for all five stopped
runtimes and never write them.

- [ ] **Step 2: Create one fresh runtime and materialize reviewed programs**

Use `mktemp -d /private/tmp/mysql-senior-scenarios.XXXXXX`. Extract only the
committed scenario fences, compile with Connector/Python `9.7.0`, and prove
byte equality to the reviewed feature commit. No handwritten wrapper may enter
the measured path.

- [ ] **Step 3: Fresh seed, freeze, and gates**

Drop/recreate/reseed exactly `100000` orders, `300000` items, and `10000`
probes. Record immutable source fingerprint and separate probe audit. Install
six triggers; require all six negative probes to return errno `1644` / SQLSTATE
`45000`.

Run KILL preflight once and pure-client smoke once. Either failure stops the
run, removes triggers, preserves evidence, and returns `BLOCKED` without retry.

- [ ] **Step 4: Run three controls and calibration once**

Run `control-1..3`, each `60` seconds and `4` threads, once. Require
`SUCCEEDED`, zero errors, valid pure/worker/metrics evidence, and source/probe
checkpoints.

Run the fixed controller `latency-calibration-1` once. Persist and independently
recompute every rolling input, all `R_t` values, input SHA, noise ratio, and
current-runtime `B`. Confirm its input SHA and embedded control windows come
from the sixth runtime rather than the fifth fixture; a coincidentally equal
numeric budget is allowed only when independently recomputed. Freeze it before
exports.

- [ ] **Step 5: Run buffered and chunked matrices**

Run `buffered-1..3` then `chunked-1..3` exactly once per trial. Each controller
must validate calibration before `Popen`, wait for five windows, and use only
rolling latency plus immediate non-latency gates.

On any `ABORTED`, stop later trials in that mode and all downstream performance
ranking that depends on them. Preserve complete evidence; never retry or alter
the frozen artifact.

- [ ] **Step 6: Run planned interruption/resume and correctness audit**

Only when the successful artifact prerequisites in the scenario are present,
run the planned three-part interruption followed by a separate resume. Audit
exactly `100000` rows, strict `(created_at,id)` order, distinct IDs, high cursor,
business aggregate, and identical SHA across successful buffered, chunked, and
resumed artifacts.

- [ ] **Step 7: Teardown and verify before documentation edits**

Compare immutable report source exactly; audit probe rows/schema/current
counter separately. Remove all six triggers. Require no child/victim process,
unchanged globals, healthy dedicated container, exited `mysql-primary`, and
unchanged five stopped-runtime digests. Produce a complete SHA-256 manifest for
the sixth runtime.

- [ ] **Step 8: Patch only honest completed evidence**

If and only if the documented completion contract is satisfied, use
`apply_patch` to add environment, calibration artifact/formula/current budget,
noise ratio, every control/export window and trial summary, safety/interference
conclusions, artifacts, resume, source/probe, teardown, and limitations. Mark
the scenario `SCALED_REPRODUCED (S=100000)` and update only the singular
report/export README row.

If the run stops before the required matrix/artifact evidence, do not invent a
success label or commit partial performance evidence; preserve the report and
return `BLOCKED` for adjudication.

- [ ] **Step 9: Verify and commit evidence**

```bash
git diff --check -- \
  mysql-handson/13-senior-scenarios/04-report-export-isolation.md \
  mysql-handson/13-senior-scenarios/README.md
git add \
  mysql-handson/13-senior-scenarios/04-report-export-isolation.md \
  mysql-handson/13-senior-scenarios/README.md
git commit -m "docs(mysql): record report export evidence"
```

---

### Task 4: Final navigation, status, and branch verification

**Files:**
- Modify only when inconsistent: `mysql-handson/13-senior-scenarios/README.md`
- Modify only when inconsistent: `mysql-handson/README.md`
- Create (ignored report): `.superpowers/sdd/2026-08-01-mysql-report-latency-gate/task-4-report.md`

**Interfaces:**
- Consumes: reviewed commits and Task 3 evidence.
- Produces: one coherent navigation/status story and a branch ready for final review/integration.

- [ ] **Step 1: Inventory every scenario status occurrence**

Search all MySQL navigation/status tables and the four senior scenario files.
Classify each occurrence as canonical routing, summary, evidence label, or
historical explanation. Ensure bulk import, online archive, report/export, and
HA labels agree with their actual evidence.

- [ ] **Step 2: Write RED assertions for any discovered inconsistency**

The assertions must name exact files/rows and fail on stale `READY_UNRUN`,
duplicate scenario ownership, wrong scale, broken anchors, or contradictory
primary/secondary tables. If inventory is already consistent, record the
read-only proof and make no edit.

- [ ] **Step 3: Apply the smallest navigation correction**

Use `apply_patch`; preserve established ordering and do not rewrite scenario
content. Stage only navigation files with proven inconsistencies.

- [ ] **Step 4: Run final static verification**

Run all scenario regression harnesses, Markdown-link checks, code-fence
extraction/compile, `git diff --check`, changed-file scope, feature worktree
status, and a read-only dedicated-container/source audit. Record exact output.

- [ ] **Step 5: Commit only if navigation changed**

```bash
git add mysql-handson/README.md mysql-handson/13-senior-scenarios/README.md
git commit -m "docs(mysql): reconcile senior scenario status"
```

If no navigation edit is required, create no empty commit.

After Task 4, run the required broad whole-branch review. Only after review is
clean may the plan workspace and exact owned dedicated container/volume be
cleaned up; all `mysql-primary` resources remain untouched. Then use
`superpowers:finishing-a-development-branch` for integration.
