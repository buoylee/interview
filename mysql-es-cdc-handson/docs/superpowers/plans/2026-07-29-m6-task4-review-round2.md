# M6 Task 4 Review Round 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make M6's real 18-case evidence reproducible from a fresh checkout, prove every scenario action was intended before fault execution, strictly validate the nine-file snapshots and all scenario semantics, and eliminate raw Kafka producer bypasses.

**Architecture:** Keep volatile attempts in an ignored runtime evidence root and publish their race-safe symlink views only there. After all 18 real cases pass, copy the locked nine JSON files into ordinary canonical directories under `evidence/`, generate `evidence/index.json`, and commit those files separately. A locked per-scenario intent catalog is persisted before dispatch and the runner merges actual execution timestamps and exit codes into the final command evidence.

**Tech Stack:** Bash, jq, Python 3, JSON Schema 2020-12, Docker Compose, Maven/Java 21, Git worktrees.

## Global Constraints

- Follow red-green-refactor; every production behavior change needs a failing contract first.
- Run only against `COMPOSE_PROJECT_NAME=mysql-es-cdc-handson-m6-task4`.
- Do not prune Docker, remove global resources, or touch projects outside the dedicated M6 stack.
- Preserve the already-approved rebuild condition ownership and migration behavior.
- Commit implementation first; commit genuine materialized evidence only after a clean real 18-case matrix.
- Raw logs, `.runs`, attempts, locks, and temporary state remain ignored.

---

### Task 1: Materialized canonical evidence

**Files:**
- Modify: `.gitignore`
- Modify: `tests/end-to-end/m6-fault-matrix.sh`
- Modify: `scenarios/scripts/publish-evidence.py`
- Create: `scenarios/scripts/materialize-m6-evidence.py`
- Modify: `tests/contracts/m6-evidence-gitignore.sh`
- Modify: `tests/contracts/m6-matrix-bundle-tamper.sh`
- Create: `tests/contracts/m6-materialized-evidence.sh`

**Interfaces:**
- Consumes: race-safe runtime bundles under ignored `.attempts/.runs`.
- Produces: `materialize-m6-evidence.py RUNTIME_ROOT CANONICAL_ROOT CATALOG`, ordinary nine-file directories, and a locked index.

- [ ] Write contracts that reject symlink canonical bundles, require `evidence/index.json` and all 18 JSON directories to be unignored, and verify a fresh copied tree without `.runs`.
- [ ] Run the focused contracts and confirm they fail because current canonical entries are symlinks/index is ignored.
- [ ] Add the runtime-root/materialization boundary and exact `.gitignore` allowlist.
- [ ] Re-run focused contracts and confirm PASS.
- [ ] Commit only after Tasks 1-4 are all green.

### Task 2: Pre-dispatch command intent WAL

**Files:**
- Create: `scenarios/command-intents.json`
- Create: `scenarios/schema/command-intents.schema.json`
- Create: `scenarios/scripts/persist-m6-command-intent.sh`
- Create: `scenarios/scripts/complete-m6-command-intent.sh`
- Modify: `scenarios/scripts/run-scenario.sh`
- Modify: `scenarios/scripts/dispatch-fault.sh`
- Modify: `scenarios/scripts/build-m6-real-bundle.sh`
- Modify: `scenarios/scripts/collect-m6-observations.sh`
- Modify: `scenarios/schema/input-commands.schema.json`
- Create: `tests/contracts/m6-command-intent.sh`
- Modify: `tests/contracts/evidence-contract-tamper.sh`

**Interfaces:**
- Consumes: scenario ID, owner token, and a locked case fixture path.
- Produces: an atomic inert `command-intent.json` before dispatch, with business-mutation/fault/recovery metadata and fixture digest; final evidence contains those entries plus verifier execution with real timestamps and exit codes.

- [ ] Write a contract proving dispatch fails without a valid persisted intent and final PASS evidence requires phases `business-mutation`, `fault`, `recovery`, and `verification`.
- [ ] Run it and confirm RED because only the final verifier is currently captured.
- [ ] Persist the locked intent before `dispatch-fault.sh`, merge actual phase timing/exit status, and verify fixture hashes against checked-in files.
- [ ] Re-run the intent and tamper contracts and confirm PASS.

### Task 3: Strict nine-file shapes and 18-case semantics

**Files:**
- Modify: `scenarios/schema/fault.schema.json`
- Modify: `scenarios/schema/mysql-snapshot.schema.json`
- Modify: `scenarios/schema/es-snapshot.schema.json`
- Modify: `scenarios/schema/kafka-offsets.schema.json`
- Modify: `scenarios/schema/differences.schema.json`
- Modify: `scenarios/schema/recovery-actions.schema.json`
- Modify: `tests/contracts/evidence-contract.sh`
- Modify: `tests/contracts/evidence-contract-tamper.sh`
- Modify: `tests/fixtures/m6/evidence-valid/*.json`
- Modify: `tests/fixtures/m6/evidence-canal-valid/*.json`

**Interfaces:**
- Consumes: exact capture output and canonical-hashed case facts.
- Produces: schemas with closed nested objects and a total 18-way semantic case dispatch with no permissive default.

- [ ] Add negatives for deleted duplicate-event facts, invented MySQL documents, and critical facts in cases 3, 5, 8, 11, 15, 16, and 18.
- [ ] Run tamper tests and confirm the new mutations are accepted by the old contract (RED).
- [ ] Close all nested snapshot/fault structures, bind MySQL documents to ES documents, and implement meaningful assertions for every catalog scenario with an unknown-scenario failure branch.
- [ ] Re-run positive fixtures and all tamper negatives and confirm PASS.

### Task 4: Remove helper-level raw Kafka producer bypass

**Files:**
- Modify: `scenarios/scripts/m6-case-runtime.sh`
- Modify: `tests/contracts/m6-task4-primitive-routing.sh`

**Interfaces:**
- Consumes: the actual partition observed on the original Canal record.
- Produces: case 9/10/14 replay only through `inject-scenario-event.sh`; selection performs no probe production.

- [ ] Extend routing contract to recursively inspect sourced helpers and reject `kafka-console-producer` outside the locked Task 2 primitive.
- [ ] Run it and confirm RED at `produce_with_key`.
- [ ] Remove keyed probe production and select a product using only its real captured Canal record/partition.
- [ ] Re-run routing contract and single cases 9, 10, and 14.

### Task 5: Implementation verification and commit

**Files:**
- Append after success: `evidence/task4-implementation-report.md`
- Append after success: `evidence/task4-progress.md`

**Interfaces:**
- Produces: one clean implementation commit before any new canonical evidence is materialized.

- [ ] Run all focused contracts, positive fixtures, tamper negatives, migration repeat-apply, and condition ownership tests.
- [ ] Run single real cases 9, 10, and 14 plus critical cases as required by failures.
- [ ] Verify tracked worktree contents and commit implementation-only files.

### Task 6: Genuine matrix, evidence commit, and fresh-checkout proof

**Files:**
- Create from real runtime only: `evidence/<18-scenario>/*.json`
- Create from real runtime only: `evidence/index.json`

**Interfaces:**
- Consumes: a clean implementation commit and dedicated Compose project.
- Produces: a separate evidence commit whose manifests reference the implementation commit.

- [ ] Run the full real matrix from a clean implementation HEAD; do not reuse round1 evidence.
- [ ] Confirm `18/18/0`, complete new command phases, all semantic facts, and materialized ordinary directories.
- [ ] Stage only the 18×9 canonical JSON files plus index and commit them as evidence.
- [ ] Create a temporary fresh Git worktree at the evidence commit and run verify-only without `.runs`.
- [ ] In the fresh worktree run full `make verify`; append ignored reports/progress in the implementation worktree.
- [ ] Report both commit SHAs and exact verification results.
