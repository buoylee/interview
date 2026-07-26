# MySQL ES CDC Hands-on M6 Fault Matrix and Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox - [ ] syntax for tracking.

**Goal:** Turn every consistency claim into a deterministic, repeatable fault scenario with machine-readable evidence, then use those results to answer exactly what Canal provides, what it does not guarantee, and which additional capabilities make MySQL-to-Elasticsearch current-state eventual consistency defensible.

**Architecture:** One scenario catalog drives a condition-based shell runner. The runner resets deterministic data, records inputs, injects one named fault, observes the declared intermediate state, performs only the declared recovery action, waits for exact offsets and watermarks, runs the independent verifier, and writes a fixed nine-file evidence bundle. Contract tests reject missing evidence, false PASS states, unresolved DLQ, nonzero exact differences, stale tombstones, secret leakage, and fixed-sleep success checks. The final README conclusions link each guarantee and limitation to scenario IDs.

**Tech Stack:** Docker Compose v2, Bash 3.2-compatible scripts, `curl`, `jq`, SHA-256 tools, Java 21, Spring Boot 4.1.0, JUnit 5, MySQL 8.4.8, Canal 1.1.8, Kafka 4.1.2, Elasticsearch 8.17.0, Toxiproxy 2.12.0.

## Global Constraints

- Execute only after the M5 completion gate passes.
- Work only in branch `codex/mysql-es-cdc-handson` and its isolated worktree.
- The catalog contains exactly the 18 design scenarios. A scenario may not be removed or weakened to obtain a green run.
- Every scenario starts from a declared seed and records every business or fault command before execution.
- Network failures use Toxiproxy; crash windows use named one-shot failpoints; log gaps use observed beginning/end/binlog positions. Do not use random process killing.
- `sleep` is allowed only as the polling interval inside a bounded wait loop. A fixed delay is never a success condition.
- A scenario PASS means the expected failure was observed and the declared terminal invariant was proved. It does not mean no failure occurred.
- Recovered scenarios finish only after target watermarks pass, Kafka lag meets the scenario contract, unresolved DLQ is zero, a conclusive independent verification has zero exact differences, and all inactive products have latest-revision tombstones.
- Scenarios whose required recovery is rebuild must first prove `REBUILD_REQUIRED`; direct repair or offset skipping is a test failure.
- Evidence captures command intent and bounded outputs but never stores passwords, authorization headers, environment secrets, or full Compose environment dumps.
- Runtime JSON evidence under `evidence/{scenario-id}` is committed after the final clean run. Raw logs go under ignored `evidence/.raw/`.
- Two full matrix runs from reset must produce identical normalized outcomes; timestamps, UUIDs, offsets, image digests, and durations are compared by invariant rather than byte identity.
- Final documentation must distinguish observed lab evidence from a production availability or SLO claim.

## Locked Evidence Bundle

~~~text
evidence/{scenario-id}/
├── manifest.json
├── input-commands.json
├── fault.json
├── mysql-snapshot.json
├── es-snapshot.json
├── kafka-offsets.json
├── differences.json
├── recovery-actions.json
└── result.json
~~~

No scenario-specific file may replace these names. Additional raw logs belong in `evidence/.raw/{scenario-id}/` and are not committed.

---

### Task 1: Lock the scenario and evidence schemas before running faults

**Files:**

- Create: `mysql-es-cdc-handson/scenarios/schema/scenario.schema.json`
- Create: `mysql-es-cdc-handson/scenarios/schema/result.schema.json`
- Create: `mysql-es-cdc-handson/scenarios/catalog.json`
- Create: `mysql-es-cdc-handson/tests/contracts/scenario-catalog.sh`
- Create: `mysql-es-cdc-handson/tests/contracts/evidence-contract.sh`
- Create: `mysql-es-cdc-handson/tests/contracts/no-fixed-sleep.sh`
- Create: `mysql-es-cdc-handson/tests/contracts/no-evidence-secrets.sh`
- Modify: `mysql-es-cdc-handson/.gitignore`

**Interfaces:**

- Scenario IDs are stable kebab-case identifiers.
- Terminal scenario results are `PASS` or `FAIL`; pipeline states use the five-state application enum.

- [ ] **Step 1: Write the failing catalog contract**

`scenario-catalog.sh`:

~~~bash
#!/usr/bin/env bash
set -euo pipefail

catalog="scenarios/catalog.json"
test -f "$catalog"

jq -e '
  .schema_version == 1 and
  (.scenarios | length) == 18 and
  ([.scenarios[].scenario_id] | length == (unique | length)) and
  all(.scenarios[];
    (.scenario_id | test("^[a-z0-9]+(-[a-z0-9]+)*$")) and
    (.milestone | IN("M3","M4","M5","M6")) and
    (.expected_intermediate_states | length >= 1) and
    (.expected_terminal_state | IN("HEALTHY","DEGRADED","REBUILD_REQUIRED")) and
    (.recovery_action | length > 0) and
    (.timeout_seconds >= 30 and .timeout_seconds <= 1800)
  )
' "$catalog" >/dev/null

jq -r '.scenarios[].design_case' "$catalog" | sort -n | \
  diff -u <(seq 1 18) -
~~~

- [ ] **Step 2: Run the contract and verify the red state**

~~~bash
bash tests/contracts/scenario-catalog.sh
~~~

Expected: FAIL because the catalog and schemas do not exist.

- [ ] **Step 3: Create the exact scenario schema**

`scenario.schema.json` uses JSON Schema draft 2020-12 and requires:

~~~json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "design_case", "scenario_id", "milestone", "seed", "fault",
    "expected_intermediate_states", "expected_terminal_state",
    "recovery_action", "requires_rebuild", "timeout_seconds"
  ],
  "properties": {
    "design_case": {"type":"integer", "minimum":1, "maximum":18},
    "scenario_id": {"type":"string", "pattern":"^[a-z0-9]+(-[a-z0-9]+)*$"},
    "milestone": {"enum":["M3","M4","M5","M6"]},
    "seed": {"type":"string", "minLength":1},
    "fault": {
      "type":"object",
      "additionalProperties":false,
      "required":["type","target","action"],
      "properties": {
        "type":{"enum":["PROCESS","NETWORK","RETENTION","DATA","MAPPING","REBUILD"]},
        "target":{"type":"string", "minLength":1},
        "action":{"type":"string", "minLength":1}
      }
    },
    "expected_intermediate_states": {
      "type":"array", "minItems":1,
      "items":{"enum":["HEALTHY","CATCHING_UP","DEGRADED","REBUILD_REQUIRED","REBUILDING"]}
    },
    "expected_terminal_state": {"enum":["HEALTHY","DEGRADED","REBUILD_REQUIRED"]},
    "recovery_action":{"type":"string", "minLength":1},
    "requires_rebuild":{"type":"boolean"},
    "timeout_seconds":{"type":"integer", "minimum":30, "maximum":1800}
  }
}
~~~

- [ ] **Step 4: Create the result schema and PASS invariants**

`result.schema.json` requires:

~~~json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version", "scenario_id", "dependency_versions",
    "consistency_preconditions", "source_watermark", "applied_offsets",
    "unresolved_dlq_count", "exact_diff_count", "tombstone_mismatch_count",
    "canal_position_recovery",
    "expected_intermediate_states", "observed_intermediate_states",
    "expected_pipeline_state", "observed_pipeline_state", "recovery_action",
    "target_watermark_passed", "result", "started_at", "finished_at"
  ],
  "properties": {
    "schema_version":{"const":1},
    "scenario_id":{"type":"string"},
    "dependency_versions":{"type":"object"},
    "consistency_preconditions":{"type":"array"},
    "source_watermark":{"type":"integer", "minimum":0},
    "applied_offsets":{"type":"object"},
    "unresolved_dlq_count":{"type":"integer", "minimum":0},
    "exact_diff_count":{"type":"integer", "minimum":0},
    "tombstone_mismatch_count":{"type":"integer", "minimum":0},
    "expected_intermediate_states":{"type":"array"},
    "observed_intermediate_states":{"type":"array"},
    "expected_pipeline_state":{"type":"string"},
    "observed_pipeline_state":{"type":"string"},
    "recovery_action":{"type":"string"},
    "target_watermark_passed":{"type":"boolean"},
    "canal_position_recovery":{
      "oneOf":[
        {"type":"null"},
        {
          "type":"object",
          "additionalProperties":false,
          "required":[
            "old_cursor_sha256","old_missing_journal","old_missing_position",
            "reset_journal","reset_position","normal_restart_preserved",
            "anchor_next_offsets","first_post_reset_event"
          ],
          "properties":{
            "old_cursor_sha256":{"type":"string","pattern":"^[a-f0-9]{64}$"},
            "old_missing_journal":{"type":"string","minLength":1},
            "old_missing_position":{"type":"integer","minimum":4},
            "reset_journal":{"type":"string","minLength":1},
            "reset_position":{"type":"integer","minimum":4},
            "normal_restart_preserved":{"const":true},
            "anchor_next_offsets":{"type":"object","minProperties":3,"maxProperties":3},
            "first_post_reset_event":{"type":"object"}
          }
        }
      ]
    },
    "result":{"enum":["PASS","FAIL"]},
    "started_at":{"type":"string", "format":"date-time"},
    "finished_at":{"type":"string", "format":"date-time"}
  }
}
~~~

`evidence-contract.sh` first checks all nine files, then enforces:

~~~bash
jq -e '
  if .result == "PASS" then
    .target_watermark_passed == true and
    .unresolved_dlq_count == 0 and
    .exact_diff_count == 0 and
    .tombstone_mismatch_count == 0 and
    .observed_pipeline_state == .expected_pipeline_state and
    ([.expected_intermediate_states[]] - [.observed_intermediate_states[]] | length) == 0
  else true end
' "$bundle/result.json" >/dev/null

if test "$(jq -r '.scenario_id' "$bundle/result.json")" = canal-outage-beyond-binlog-retention; then
  jq -e '.canal_position_recovery != null and .canal_position_recovery.normal_restart_preserved == true and (.canal_position_recovery.anchor_next_offsets | length) == 3' "$bundle/result.json" >/dev/null
fi
~~~

`unresolved_dlq_count` is the sum of unresolved product-level and record-level DLQ rows; neither class may be hidden from PASS.

- [ ] **Step 5: Forbid fixed-sleep success and secret leakage**

`no-fixed-sleep.sh` fails if a scenario script contains `sleep` outside `wait-condition.sh`. `wait-condition.sh` is allowed only `sleep "$poll_seconds"` inside its loop.

`no-evidence-secrets.sh` recursively rejects case-insensitive keys or values matching:

~~~text
password
authorization
api_key
secret
Bearer
canalpass
root:root
~~~

Raw logs are not exempt from the repository scan because `.raw` must be ignored and untracked.

- [ ] **Step 6: Create the exact 18-row catalog**

The catalog must encode this table without merging cases:

| Case | Scenario ID | Intermediate state | Recovery | Rebuild | Terminal |
|---:|---|---|---|---:|---|
| 1 | canal-normal-restart | CATCHING_UP | restart Canal, automatic resume | no | HEALTHY |
| 2 | canal-outage-within-binlog-retention | CATCHING_UP | restore Canal before purge | no | HEALTHY |
| 3 | canal-outage-beyond-binlog-retention | REBUILD_REQUIRED | evidenced Canal cursor rebootstrap, then M5 full rebuild | yes | HEALTHY |
| 4 | kafka-temporary-unavailable | CATCHING_UP | remove Kafka toxic | no | HEALTHY |
| 5 | consumer-offset-beyond-kafka-retention | REBUILD_REQUIRED | M5 full rebuild | yes | HEALTHY |
| 6 | consumer-crash-before-elasticsearch | CATCHING_UP | restart consumer | no | HEALTHY |
| 7 | consumer-crash-after-elasticsearch-before-offset | CATCHING_UP | restart and idempotent replay | no | HEALTHY |
| 8 | elasticsearch-bulk-partial-failure | DEGRADED | disarm one-item invalid-type fault and replay DLQ | no | HEALTHY |
| 9 | duplicate-event | HEALTHY | external-version settlement | no | HEALTHY |
| 10 | late-old-revision | HEALTHY | current-state rehydrate and version fence | no | HEALTHY |
| 11 | mapping-conflict | DEGRADED | fix the lab-only invalid projection and replay DLQ | no | HEALTHY |
| 12 | manual-elasticsearch-drift | DEGRADED | M4 bounded repair | no | HEALTHY |
| 13 | category-rename-multi-product | CATCHING_UP | automatic fan-out revisions | no | HEALTHY |
| 14 | delete-then-old-event-replay | HEALTHY | latest tombstone and version fence | no | HEALTHY |
| 15 | rebuild-with-concurrent-writes | REBUILDING | M5 barrier cutover | yes | HEALTHY |
| 16 | rebuild-crash-and-restart | REBUILDING, DEGRADED | persisted-state recovery then rebuild | yes | HEALTHY |
| 17 | consumer-systematic-mapping-bug | DEGRADED | M4 detection and repair | no | HEALTHY |
| 18 | dlq-replay-fails-then-succeeds | DEGRADED | failed replay retained, fix, replay | no | HEALTHY |

- [ ] **Step 7: Verify schemas and commit**

~~~bash
bash tests/contracts/scenario-catalog.sh
bash tests/contracts/no-fixed-sleep.sh
bash tests/contracts/no-evidence-secrets.sh
git add scenarios tests/contracts .gitignore
git commit -m "test(cdc-lab): lock fault and evidence contracts"
~~~

---

### Task 2: Build deterministic wait, fault, and snapshot primitives

**Files:**

- Create: `mysql-es-cdc-handson/infra/toxiproxy/bootstrap.sh`
- Modify: `mysql-es-cdc-handson/infra/compose.yaml`
- Create: `mysql-es-cdc-handson/scenarios/scripts/lib/common.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/wait-condition.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/fault-network.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/fault-process.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/fault-retention.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/capture-mysql.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/capture-elasticsearch.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/capture-kafka.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/capture-manifest.sh`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/lab/ScenarioEventRequest.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/lab/ScenarioEventProducer.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/lab/ScenarioEventController.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/test/java/com/interview/mysqlescdc/verifier/lab/ScenarioEventProducerIT.java`

**Interfaces:**

- Fault script action is one of `apply`, `remove`, or `status` and is idempotent.
- All collectors emit deterministic JSON ordering by product ID or partition ID.

- [ ] **Step 1: Write primitive contract tests**

Tests must prove:

- wait succeeds immediately when its command returns zero;
- wait times out nonzero and records the last command output;
- applying/removing the same toxic twice is safe;
- collectors return valid JSON with sorted IDs;
- injected Kafka payload goes to the explicitly requested partition with a null key;
- manifest redacts all credential values.

- [ ] **Step 2: Implement one bounded condition loop**

`wait-condition.sh`:

~~~bash
#!/usr/bin/env bash
set -euo pipefail

description=$1
timeout_seconds=$2
poll_seconds=$3
shift 3

started=$(date +%s)
last_output=""
while true; do
  if last_output=$("$@" 2>&1); then
    printf '%s\n' "$last_output"
    exit 0
  fi
  now=$(date +%s)
  if (( now - started >= timeout_seconds )); then
    printf 'timeout waiting for %s\n%s\n' "$description" "$last_output" >&2
    exit 1
  fi
  sleep "$poll_seconds"
done
~~~

All scenario scripts call this helper rather than implementing their own loop.

- [ ] **Step 3: Route dependency traffic through named proxies**

Create these Toxiproxy proxies:

~~~json
[
  {"name":"elasticsearch","listen":"0.0.0.0:8666","upstream":"elasticsearch:9200"},
  {"name":"kafka","listen":"0.0.0.0:8667","upstream":"kafka:9092"},
  {"name":"canal-mysql","listen":"0.0.0.0:8668","upstream":"mysql:3306"}
]
~~~

Canal uses `toxiproxy:8668`; consumer and Canal Kafka configuration use `toxiproxy:8667`; application Elasticsearch writes use `toxiproxy:8666`. Product-service and verifier source reads remain direct to MySQL so a Canal-only outage does not stop business writes.

Kafka advertises an internal client listener at `toxiproxy:8667` and a host test listener at `localhost:29092`. Topic bootstrap may use direct broker port inside Compose.

- [ ] **Step 4: Implement exact network fault actions**

`fault-network.sh apply kafka-down` posts a `timeout` toxic named `scenario-timeout` with `timeout=0` to proxy `kafka`. `remove` deletes that named toxic and accepts HTTP 204 or 404. Equivalent actions exist for `elasticsearch-timeout` and `canal-mysql-timeout`.

Every apply response is written to `fault.json`; cleanup is registered before the fault is applied.

- [ ] **Step 5: Implement deterministic process failpoints**

Extend consumer `Failpoint` with `BEFORE_ES_BULK`. Invoke it immediately before the first ES request. Ensure `BEFORE_KAFKA_OFFSET_COMMIT` is invoked immediately before `Acknowledgment.acknowledge()`.

`fault-process.sh` arms through the internal API and then polls `docker inspect` until exit code 86. It never runs `docker kill` for a crash-window scenario.

- [ ] **Step 6: Implement exact retention evidence**

MySQL helper records `SHOW MASTER STATUS` and `SHOW BINARY LOGS`, changes `binlog_expire_logs_seconds` only for the scenario, rotates logs, and polls until the recorded file is absent. It restores the configured retention in `trap` cleanup.

Kafka helper records committed and beginning offsets, changes topic `retention.ms`, writes bounded events, and polls until `beginningOffset > committedOffset` for at least one partition. It restores topic retention before rebuild.

- [ ] **Step 7: Implement lab-only explicit Kafka injection**

Guard the controller with `lab.failpoints.enabled=true`. Request:

~~~json
{
  "topic":"product-search-revisions",
  "partition":1,
  "payload":"{\"id\":91,\"database\":\"product_catalog\",\"table\":\"product_search_revision\",\"isDdl\":false,\"type\":\"UPDATE\",\"data\":[{\"product_id\":\"1001\",\"revision\":\"1\",\"active\":\"1\"}]}"
}
~~~

`ScenarioEventProducer` validates the topic constant, partition range 0..2, and flat-message table before sending `new ProducerRecord<>(topic, partition, null, payload)`. Return the acknowledged partition and offset.

- [ ] **Step 8: Implement canonical collectors**

- MySQL snapshot: one JSON object per revision row with all expected fields, ordered by product ID.
- Elasticsearch snapshot: PIT/search_after all documents, including `_version`, ordered by product ID.
- Kafka snapshot: beginning, end, primary committed, lag, shadow offsets, and barrier offsets ordered by partition.
- Manifest: Git commit, dirty flag, OS/architecture, image tags/digests, Maven/Java/Compose versions, schema version, index generation, and SHA-256 of checked-in configs.

- [ ] **Step 9: Verify primitives and commit**

~~~bash
./mvnw -pl consistency-verifier -Dtest=ScenarioEventProducerIT test
bash tests/contracts/no-fixed-sleep.sh
bash tests/contracts/no-evidence-secrets.sh
git add .
git commit -m "test(cdc-lab): add deterministic fault primitives"
~~~

---

### Task 3: Implement one transactional evidence runner

**Files:**

- Create: `mysql-es-cdc-handson/scenarios/scripts/run-scenario.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/dispatch-fault.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/dispatch-recovery.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/assert-terminal.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/write-result.sh`
- Create: `mysql-es-cdc-handson/tests/contracts/runner-failure-evidence.sh`

**Interfaces:**

- Entry: `bash scenarios/scripts/run-scenario.sh {scenario-id}`.
- A failed assertion still produces all possible evidence and `result.json` with `FAIL`.

- [ ] **Step 1: Write a failing-run evidence test**

Use a fixture scenario whose expected state is deliberately wrong. Assert the runner exits nonzero but creates `result.json` with `result=FAIL`, the failed assertion, timestamps, observed state, and cleanup actions.

- [ ] **Step 2: Implement strict lifecycle and cleanup**

`run-scenario.sh` performs this order:

~~~text
validate scenario ID against catalog
create a private temporary working directory with mktemp -d
register cleanup trap
make reset && make up
load declared deterministic seed
wait for MySQL, Kafka, Canal, Elasticsearch, consumer, verifier
wait for initial lag zero and independent PASS
capture manifest and precondition evidence
record input commands before execution
dispatch fault
execute declared mutations
wait for every expected intermediate state
dispatch declared recovery
wait for target watermark and offsets
run independent verification
capture MySQL, ES, Kafka, differences, recovery actions
assert terminal contract
write PASS or FAIL result
atomically replace evidence/{scenario-id} from the temporary bundle
run evidence-contract.sh and no-evidence-secrets.sh
~~~

The runner's cleanup removes toxics, restores retention, disarms failpoints, resumes paused consumers, and reopens only a gate owned by the current run.

- [ ] **Step 3: Make result derivation non-forgeable by scenario scripts**

Only `write-result.sh` writes `result.json`. It derives PASS from assertion files and observed values; scenario definitions cannot set result directly.

The exact PASS expression is:

~~~text
all expected intermediate states observed
AND declared recovery action observed
AND target watermark passed
AND scenario lag contract satisfied
AND unresolved DLQ = 0
AND conclusive verification status = PASS
AND exact diff count = 0
AND tombstone mismatch count = 0
AND observed terminal pipeline state = expected terminal state
AND cleanup failures = 0
~~~

- [ ] **Step 4: Record commands as data, not executable strings**

`input-commands.json` and `recovery-actions.json` are arrays of:

~~~json
{
  "sequence": 1,
  "kind": "HTTP",
  "target": "product-service",
  "method": "PUT",
  "path": "/api/products/1001/price",
  "body_sha256": "f6f4c32f74288b3ef1e189714b6b06b62944390cb9bc079a0e0566f7a37f1af1",
  "started_at": "2026-07-22T12:00:00Z",
  "finished_at": "2026-07-22T12:00:01Z",
  "exit_code": 0
}
~~~

Store body hashes and checked-in fixture paths, not credentials or authorization headers.

- [ ] **Step 5: Verify failure evidence and commit**

~~~bash
bash tests/contracts/runner-failure-evidence.sh
bash tests/contracts/no-fixed-sleep.sh
bash tests/contracts/no-evidence-secrets.sh
git add scenarios tests/contracts
git commit -m "test(cdc-lab): make scenario evidence transactional"
~~~

---

### Task 4: Wire all 18 scenario executors and exact assertions

**Files:**

- Create: `mysql-es-cdc-handson/scenarios/scripts/cases/01-canal-normal-restart.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/cases/02-canal-outage-within-binlog-retention.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/cases/03-canal-outage-beyond-binlog-retention.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/cases/04-kafka-temporary-unavailable.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/cases/05-consumer-offset-beyond-kafka-retention.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/cases/06-consumer-crash-before-elasticsearch.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/cases/07-consumer-crash-after-elasticsearch-before-offset.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/cases/08-elasticsearch-bulk-partial-failure.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/cases/09-duplicate-event.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/cases/10-late-old-revision.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/cases/11-mapping-conflict.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/cases/12-manual-elasticsearch-drift.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/cases/13-category-rename-multi-product.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/cases/14-delete-then-old-event-replay.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/cases/15-rebuild-with-concurrent-writes.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/cases/16-rebuild-crash-and-restart.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/cases/17-consumer-systematic-mapping-bug.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/cases/18-dlq-replay-fails-then-succeeds.sh`
- Create: `mysql-es-cdc-handson/tests/end-to-end/m6-fault-matrix.sh`

**Interfaces:**

- Each case exports only `scenario_mutate`, `scenario_assert_intermediate`, and `scenario_recover`; the common runner owns setup, final verification, evidence, and cleanup.

- [ ] **Step 1: Implement cases 1-5 for capture and retention gaps**

Exact assertions:

1. Normal restart: before stopping Canal, prove the acknowledged `/home/admin/canal-data/products/meta.dat` cursor is persisted and record its hash/decoded position plus Kafka end offsets. After restart require the same hash/position, startup from that exact cursor, unchanged offsets caused by restart itself, and exactly one post-restart mutation at the next offset before it reaches ES. Record the known 1.1.8 static-destination `future == null` stop NPE if observed, without treating one successful restart as a universal shutdown guarantee.
2. Within retention: mutate while Canal is stopped, prove the recorded binlog file still exists, start Canal, prove all revisions catch up without repair/rebuild.
3. Beyond retention: prove the required binlog file is absent and Canal reports the missing position, activate `LOG_GAP`, require `REBUILD_REQUIRED`, restore retention, run M5's write-gated cursor rebootstrap and full rebuild, then require HEALTHY. Evidence must contain the old `meta.dat` SHA-256, old missing file/position, gate-stable reset file/position, normal-mode restart hash/position and offset result, and first post-reset event in all three partitions. Rebuild-only recovery is a failure.
4. Kafka unavailable: apply Kafka timeout toxic, mutate, prove Canal/consumer cannot advance and state is CATCHING_UP, remove toxic, require automatic convergence.
5. Consumer offset expired: prove committed offset is below beginning offset, require automatic `LOG_GAP` detection and REBUILD_REQUIRED, restore retention and run M5.

No case may call the gap endpoint unless its evidence first proves the concrete missing file or offset.

- [ ] **Step 2: Implement cases 6-11 for settlement and version behavior**

Exact assertions:

6. Arm `BEFORE_ES_BULK`, mutate, observe exit 86, prove target revision is still old and offset has not passed, restart, converge.
7. Arm `AFTER_ES_BULK_SUCCESS`, mutate, observe target new revision but old committed offset, restart, observe safe duplicate settlement.
8. Send one two-row Canal record whose first item is valid and whose second is transformed by a lab-only item fault into an invalid field type against the unchanged correct mapping; prove first item applied, second durable DLQ, offset settled only after DLQ, then disarm the item fault and replay current MySQL state.
9. Capture a real flat payload and inject it again into the same partition; prove no field or revision regresses and stale/duplicate metric increments.
10. Advance a product to revision 3, inject its recorded revision-1 signal into the same partition, prove consumer rehydrates current revision 3 and ES remains revision 3.
11. Arm a lab-only consumer projection mode that emits an invalid type for exactly one product against the unchanged correct index mapping. Require DEGRADED and one PENDING DLQ; disarm/fix the projector, replay current MySQL state into the same generation, and require RESOLVED. This scenario must not create a new generation; a real mapping-schema change belongs to M5 and would set rebuild=true.

- [ ] **Step 3: Implement cases 12-14 for drift and multi-row semantics**

Exact assertions:

12. Delete one ES document and corrupt a second at the same revision; M4 must classify `MISSING` and `MODIFIED`, bounded repair must use its two version modes, fresh verification passes.
13. Seed at least three active products in one category, rename it once, prove all affected revision rows increment in the same source transaction and every ES category name/revision converges.
14. Deactivate a product, record its tombstone revision, inject an older active signal, prove `searchable=false`, latest revision, no active fields, and search alias exclusion remain unchanged.

- [ ] **Step 4: Implement cases 15-18 for rebuild and independent recovery**

Exact assertions:

15. Use M5 page size ten, mutate active/inventory/delete/create while scan pages advance, prove 503 occurs only under GATING, then exact new generation PASS.
16. Arm `BEFORE_ALIAS_SWITCH`, prove old alias remains after crash/restart; rerun without failpoint and complete. Also capture the M5 unit/integration evidence for post-alias recovery so both sides of the atomic boundary stay covered.
17. Arm `CATEGORY_NAME_FROM_ID`, produce wrong same-revision target fields, disarm, require independent M4 detection, controlled equal-revision repair, and fresh PASS.
18. Produce mapping poison, attempt DLQ replay while mapping remains broken and prove status stays PENDING with attempts incremented; fix mapping, replay again, prove RESOLVED and exact PASS.

- [ ] **Step 5: Run each case alone before the full matrix**

~~~bash
for scenario in $(jq -r '.scenarios[].scenario_id' scenarios/catalog.json); do
  bash scenarios/scripts/run-scenario.sh "$scenario"
  bash tests/contracts/evidence-contract.sh "evidence/$scenario"
done
~~~

Expected: 18 PASS bundles. If any scenario fails, keep its FAIL bundle and fix the mechanism; do not edit expected state to match a defect.

- [ ] **Step 6: Add the full matrix wrapper and commit**

`m6-fault-matrix.sh` runs catalog order, writes `evidence/index.json`, and exits nonzero if any result is not PASS. Index shape:

~~~json
{
  "schema_version": 1,
  "scenario_count": 18,
  "pass_count": 18,
  "fail_count": 0,
  "scenarios": [
    {"design_case":1,"scenario_id":"canal-normal-restart","result":"PASS"}
  ]
}
~~~

The production index contains all 18 rows.

~~~bash
bash tests/end-to-end/m6-fault-matrix.sh
git add scenarios tests/end-to-end evidence
git commit -m "test(cdc-lab): prove the full consistency fault matrix"
~~~

---

### Task 5: Replace overclaims with evidence-linked conclusions

**Files:**

- Modify: `mysql-es-cdc-handson/README.md`
- Modify: `mysql-es-cdc-handson/docs/00-goals-and-invariants.md`
- Modify: `mysql-es-cdc-handson/docs/01-canal-boundary.md`
- Modify: `mysql-es-cdc-handson/docs/02-reliable-pipeline.md`
- Modify: `mysql-es-cdc-handson/docs/03-failure-model.md`
- Modify: `mysql-es-cdc-handson/docs/04-reconciliation.md`
- Modify: `mysql-es-cdc-handson/docs/05-rebuild-runbook.md`
- Modify: `elasticsearch/roadmap/09-data-sync/09-data-sync.md`
- Modify: `financial-consistency/05-patterns/06-transactional-message-cdc.md`
- Modify: `mysql-es-cdc-handson/Makefile`
- Create: `mysql-es-cdc-handson/tests/contracts/document-evidence-links.sh`

**Interfaces:**

- Every final capability or limitation claim contains at least one evidence scenario ID or an explicit `not tested / non-goal` label.

- [ ] **Step 1: Write the failing document-link contract**

The contract extracts `evidence:<scenario-id>` tokens from README and docs, validates every token against the catalog and PASS result, and requires all 18 scenario IDs to appear in the matrix section.

- [ ] **Step 2: Write the README verdict first**

The top section must say, in Chinese:

~~~markdown
# MySQL → Canal → Elasticsearch 最终一致性实战

## 先给结论

Canal 是 MySQL binlog CDC（变更数据捕获）/增量订阅组件，不是端到端最终一致性方案。

它提供的是：读取并解析已提交 binlog、保存和恢复消费位点、把行级变更交给下游或 MQ。它改善了“如何捕获 MySQL 已提交变化”这一段，但不负责 Elasticsearch Bulk item 成败、Kafka offset 与 ES 写入的确认顺序、幂等和乱序、DLQ、独立对账、日志缺口判断、全量重建与 alias 切换。

本项目在明确前提下实现 MySQL 与 Elasticsearch 当前状态的最终一致：MySQL 事实完整；binlog/Kafka 增量日志未出现不可回放缺口，或缺口后成功完成全量重建；消费者使用 at-least-once、当前状态重读、严格 revision 防倒退、逐 Bulk item 判定、持久 DLQ；独立对账能够发现并修复漂移；重建使用一致性快照、重叠增量回放、跨 partition barrier、短暂写闸门和原子 alias 切换。

它不承诺强一致、exactly-once、零写入暂停、MySQL 历史恢复或生产可用性 SLO。
~~~

- [ ] **Step 3: Add one responsibility matrix**

README includes:

| Ability | Canal | Additional component/capability | Evidence |
|---|---|---|---|
| Capture committed MySQL row changes | yes | binlog retention and position monitoring | cases 1-3 |
| Buffer and replay downstream work | no | Kafka with retained offsets | cases 4-5 |
| Prevent old writes from overwriting new | no | per-product revision + ES external version | cases 7, 9, 10, 14 |
| Settle partial Bulk results | no | item inspection + retry classification + durable DLQ | cases 8, 11, 18 |
| Detect projection bugs or manual drift | no | independent reconciliation | cases 12, 17 |
| Recover an unreplayable log gap | no | full rebuild + shadow replay + barrier + atomic aliases | cases 3, 5, 15, 16 |
| Prove HEALTHY | no | lag + DLQ + gap + recent exact verification state machine | all cases |

Use `evidence:<scenario-id>` links in the actual table cells.

- [ ] **Step 4: Correct the existing Elasticsearch chapter precisely**

Replace each absolute form of `基于 Binlog，不会漏数据` with:

~~~text
基于 binlog 自动捕获已提交行变化，能减少应用双写遗漏；但只有在 binlog 位点与保留期有效、下游确认和重试正确、无不可回放日志缺口时，增量链路才可恢复。出现缺口必须靠独立检测和全量重建，Canal 本身不保证 MySQL 到 ES 端到端不丢。
~~~

Replace the answer that says document `_id` alone guarantees idempotence with the exact revision, Bulk-item, DLQ, reconciliation, and rebuild boundary. Add a link to `mysql-es-cdc-handson/README.md`.

- [ ] **Step 5: Link the CDC and reconciliation knowledge tracks**

In `financial-consistency/05-patterns/06-transactional-message-cdc.md`, add a short non-financial read-model example linking the lab and stating that CDC propagation is one segment of a consistency system.

In the lab reconciliation doc, link `financial-consistency/07-reconciliation/README.md` as the general reconciliation theory source. Do not duplicate its domain-level design.

- [ ] **Step 6: Add final command contracts**

~~~make
.PHONY: scenario evidence verify verify-fast

scenario:
	test -n "$(SCENARIO)"
	bash scenarios/scripts/run-scenario.sh "$(SCENARIO)"

evidence:
	bash tests/end-to-end/m6-fault-matrix.sh

verify-fast:
	./mvnw -q test
	for test_script in tests/contracts/*.sh; do bash "$$test_script"; done

verify: verify-fast
	bash tests/end-to-end/m0-smoke.sh
	bash tests/end-to-end/m4-reconciliation.sh
	bash tests/end-to-end/m5-rebuild.sh
~~~

`make evidence` is the expensive 18-scenario gate; `make verify` is the normal component and representative end-to-end gate. README must state the distinction.

- [ ] **Step 7: Verify links and commit documentation**

~~~bash
bash tests/contracts/document-evidence-links.sh
bash tests/contracts/no-evidence-secrets.sh
git diff --check
git add . ../elasticsearch/roadmap/09-data-sync/09-data-sync.md \
  ../financial-consistency/05-patterns/06-transactional-message-cdc.md
git commit -m "docs(cdc-lab): tie consistency claims to fault evidence"
~~~

---

### Task 6: Prove clean-checkout reproducibility twice and publish final evidence

**Files:**

- Create: `mysql-es-cdc-handson/tests/contracts/normalized-evidence.sh`
- Create: `mysql-es-cdc-handson/evidence/README.md`
- Modify: `mysql-es-cdc-handson/evidence/index.json`
- Modify: `mysql-es-cdc-handson/README.md`

**Interfaces:**

- Normalization removes only run-specific identity and timing fields. It may not remove result, states, recovery action, counts, preconditions, or version identities.

- [ ] **Step 1: Implement normalized comparison**

For every result file, normalize with:

~~~bash
jq -S '
  del(
    .started_at,
    .finished_at,
    .source_watermark,
    .applied_offsets,
    .dependency_versions.image_digests,
    .consistency_preconditions[].observed_at
  )
' "$result"
~~~

Do not delete scenario ID, expected/observed states, recovery action, target-watermark boolean, DLQ/diff/tombstone counts, or PASS/FAIL.

- [ ] **Step 2: Run the first complete clean-reset pass**

~~~bash
make reset
make verify-fast
make evidence
first_evidence=$(mktemp -d)
cp -R evidence/. "$first_evidence/"
~~~

Expected: 18/18 PASS and no untracked raw logs outside ignored `.raw`.

- [ ] **Step 3: Run the second complete clean-reset pass**

~~~bash
make reset
make verify-fast
make evidence
bash tests/contracts/normalized-evidence.sh "$first_evidence" evidence
~~~

Expected: normalized outcome equality for all 18 scenarios.

- [ ] **Step 4: Run the full repository-facing gate**

~~~bash
make verify
bash tests/contracts/scenario-catalog.sh
for bundle in evidence/*; do
  test -d "$bundle" || continue
  bash tests/contracts/evidence-contract.sh "$bundle"
done
bash tests/contracts/document-evidence-links.sh
bash tests/contracts/no-fixed-sleep.sh
bash tests/contracts/no-evidence-secrets.sh
git diff --check
git status --short
~~~

Expected:

- all Maven and contract tests pass;
- representative M0/M4/M5 end-to-end tests pass;
- all committed evidence bundles validate;
- no absolute Canal guarantee remains in the linked Elasticsearch chapter;
- only intended project, plan, cross-link, and evidence files are changed.

- [ ] **Step 5: Explain evidence retention**

`evidence/README.md` states:

~~~markdown
# Evidence bundles

Each named directory is produced by one deterministic scenario and must satisfy the nine-file contract. JSON evidence is committed so documentation claims can be audited. Raw service logs are excluded because they may contain unstable or sensitive environment data; the result bundle records hashes, bounded diagnostics, and exact assertions instead.

A PASS means the expected fault and recovery path were both observed under the recorded dependency versions and preconditions. It is lab evidence, not a production SLO or universal proof for every deployment.
~~~

- [ ] **Step 6: Commit the final reproducible result**

~~~bash
git add .
git commit -m "test(cdc-lab): publish reproducible consistency evidence"
git status --short
git log --oneline --decorate -12
~~~

Expected: clean worktree after the commit.

## M6 Completion Gate

The practical project is complete only when:

- all 18 design cases exist as distinct catalog entries and PASS bundles;
- every bundle has the fixed nine-file shape and passes the secret scan;
- crash windows, network outages, replay, poison data, drift, and log gaps use deterministic mechanisms;
- a PASS requires watermarks, offsets, DLQ, independent exact diff, tombstone, and pipeline-state assertions together;
- unreplayable MySQL or Kafka gaps first enter REBUILD_REQUIRED and recover only through M5;
- two full reset runs have identical normalized outcomes;
- README directly answers the two original questions and links each capability boundary to evidence;
- existing CDC documentation no longer says binlog alone means end-to-end no-loss;
- final verification is fresh and the isolated worktree is clean.
