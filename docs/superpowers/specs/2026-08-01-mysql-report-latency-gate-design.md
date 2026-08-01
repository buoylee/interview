# MySQL Report Export Latency Gate Design

## Context

The senior report/export scenario currently calibrates an OLTP latency budget
from the median of three whole-trial final P95 values, then enforces that budget
against each one-second `window_p95_ms`. The fifth fresh Task 10 run proved that
these are different statistical units:

- all three 60-second controls succeeded;
- the old formula froze `10.706124 ms`;
- `62/179` accepted control windows already exceeded that value;
- `buffered-1` stopped before export on `17.607083 ms`, approximately the
  75th percentile of the control-window distribution.

The abort was therefore valid under the implemented contract but cannot be
attributed to export interference. This is an experiment-design defect, not a
reason to retry the same trial or raise a number ad hoc.

## Decision

Separate the live safety gate from the post-run interference comparison.

The live latency gate uses the same statistic for calibration and enforcement:

```text
R_t = median(window_p95_ms[t-4:t+1])
B   = 1.5 * max(all control R_t values)
```

`R_t` is defined only after five advancing, nonempty, same-trial one-second
windows. The median uses the existing canonical nearest-rank implementation.
Rolling windows never cross trial boundaries.

The fifth run is diagnostic evidence only. Its `B=2083.017375 ms` demonstrates
the formula, but must not be reused. A future fresh runtime must run its own
three controls, calculate its own `B`, persist it, and freeze it before any
buffered or chunked child starts.

## Why This Approach

The maximum rolling-control value is deliberately conservative. It guarantees
that the observed control envelope does not fail its own safety gate; the `1.5`
factor protects against materially worse sustained behavior. A single breach
already represents at least three elevated one-second P95 values inside a
five-window median, so no additional consecutive-breach counter is required.

This gate is not a statistical claim that export caused latency. Its only job
is to stop catastrophic degradation. Export impact is evaluated after the run
from all raw windows and the three trial-level final percentile sets.

Rejected alternatives:

- `1.5 * P95(control R_t)`: the fifth controls themselves contain six
  consecutive values above that threshold, so it can still reject baseline
  behavior.
- a per-export 30-second paired baseline: it adapts to local noise but gives
  every trial a different safety budget, weakening cross-trial comparability.
- a fixed product SLO: correct for production, but this lab has no legitimate
  business SLO to invent.

## Calibration Artifact

After `control-1..3` succeed, a separate calibration step writes an atomic JSON
artifact under the current runtime root. It contains:

- schema/formula version;
- exact runtime root and canonical runner/controller SHA-256 values;
- non-secret connection binding;
- control trial IDs, durations, thread count, window size, and accepted-window
  counts;
- every ordered control `window_p95_ms` and derived `R_t` value;
- combined rolling count, minimum, median, P95, P99, maximum;
- multiplier `1.5` and the exact frozen budget;
- SHA-256 over the canonical calibration inputs.

The artifact is written only when all three controls are `SUCCEEDED`, have zero
errors, valid pure-client/worker contracts, advancing metrics, and coherent
stale/backlog diagnostics. Missing, duplicate, malformed, nonfinite, negative,
coercible, reordered, cross-trial, or insufficient windows fail closed.

Every later timed invocation validates the calibration artifact before opening
child output files or calling `Popen`. The binding must match the current
runtime, programs, connection configuration, duration, threads, and one-second
window contract. The budget cannot be recomputed or changed after the first
export starts.

## Live Enforcement

Latency handling is changed as follows:

1. Control trials run with latency gating disabled but all error, disk,
   heartbeat, identity, connector, and metrics-integrity gates enabled.
2. Buffered and chunked trials first collect five advancing, nonempty windows.
3. Before export starts, compute `R_t`; start only when `R_t <= B`.
4. While export runs, recompute `R_t` for each new accepted window. One
   `R_t > B` produces the existing timed-trial `ABORTED` behavior.
5. Error, cumulative-error, disk, heartbeat, malformed metrics, source drift,
   and implementation-contract breaches remain immediate; they are never
   smoothed by the rolling statistic.

The existing pure-client smoke remains excluded from control calibration and
performance statistics.

## Performance Interpretation

The report must publish two separate conclusions:

- **Safety outcome:** whether the empirical rolling-envelope gate aborted a
  trial and at which rolling window.
- **Interference outcome:** control versus buffered versus chunked comparison
  using all ordered one-second windows, each trial's final P50/P95/P99,
  median/range across three successful trials, export duration/throughput/RSS,
  and artifact correctness.

The empirical budget is host- and runtime-specific. A large `max/median` ratio
must be reported as evidence that the environment is noisy and that the safety
gate is insensitive to moderate regressions. Results continue to include the
pinned pure-Python client cost and are neither a MySQL-only capacity number nor
a production SLO.

`ABORTED` trials remain outside steady-state medians. They are recorded with
their complete rolling inputs, frozen budget, trigger, controller evidence,
and checkpoint boundary.

## Source and Recovery Boundaries

This design does not change source consistency, artifact publication, KILL,
resume, disk, or teardown semantics:

- `report_order` and `report_item` remain frozen and exact;
- `oltp_probe` row count/schema are invariant while its counter is expected to
  advance and is audited separately;
- gate-aborted performance trials are never resumed and ranked;
- the planned three-part interruption/resume run remains correctness-only;
- all prior stopped runtime directories remain immutable evidence.

## Testing

Implementation follows RED/GREEN TDD and must cover:

- rolling median requires exactly five ordered windows and never crosses trial
  boundaries;
- nearest-rank calculations and `B = 1.5 * max(R_t)` use exact values;
- the old fifth-run dataset reproduces `167` rolling values and
  `B=2083.017375 ms` as a regression fixture;
- the fifth `buffered-1` raw window does not cause an abort before five windows;
- malformed, duplicate, reordered, missing, nonfinite, boolean/string, or
  cross-boundary calibration inputs fail closed;
- calibration artifact atomicity, checksum, identity binding, immutability,
  and validation-before-`Popen`;
- immediate non-latency gates remain immediate;
- rolling breach preserves timed `ABORTED`, KILL/checkpoint, and no-retry
  semantics;
- all prior Task 9/10 KILL, pure-client, bounded-drain, stale-snapshot,
  artifact, resume, and source-audit regressions remain green.

## Delivery and Execution

Plan 10e is a new architecture-reset task authorized after the Task 9 five-round
breaker. It is not Task 9 fix round 6.

Delivery order:

1. amend the canonical implementation plan;
2. independently review the plan correction;
3. synchronize the reviewed runner/controller/prose into the feature scenario
   as a new architecture-reset task with a fresh review ledger;
4. run offline regressions and an independent scoped review;
5. create a sixth fresh runtime and fresh S seed/freeze;
6. execute each gate and trial once, with no silent retry;
7. commit evidence only if the documented completion contract is satisfied.

The five existing runtime directories are never resumed or rewritten. The
dedicated MySQL container remains the only permitted server; `mysql-primary`
must remain exited and untouched.

## Acceptance Criteria

- Calibration and enforcement use the identical rolling-five statistic.
- The frozen budget is derived only from the current fresh runtime's three
  successful controls and is immutable before exports.
- No raw one-second latency window can independently abort a trial.
- Immediate integrity/safety gates retain their prior fail-closed behavior.
- Safety and interference conclusions are reported separately.
- All offline and live evidence remains attributable, checksummed, and honest
  about environment and client boundaries.

