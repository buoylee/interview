# MySQL Senior Scenarios Scope Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the report/export audit platform with a small, retryable Docker demonstration and rewrite the reader path as a fluent senior-engineer tutorial.

**Architecture:** One Python program inside a scoped container seeds exactly 10,000 orders, 30,000 items, and 1,000 OLTP probe rows in a dedicated disposable MySQL container. It runs buffered and chunked exports while a small OLTP worker advances, compares deterministic rows and SHA-256, and prints one bounded JSON summary; no append-only evidence protocol, one-shot state machine, calibration matrix, or independent verifier remains reader-facing.

**Tech Stack:** POSIX shell, Docker CLI, MySQL 8.0.36, Python 3.13, mysql-connector-python 9.7.0, Python unittest, Markdown.

## Global Constraints

- Default dataset is exactly 10,000 orders, 30,000 items, and 1,000 OLTP probe rows.
- Host executes Git and Docker CLI only: no host Python, `uv`, `pip`, MySQL, runtime directory, artifact directory, or writable bind mount.
- Use only Docker resources labeled `com.openai.codex.scope=mysql-senior-demo` and names prefixed `mysql-senior-demo-`.
- Limit MySQL and demo containers to `--cpus 2`, `--memory 2g`, and `--pids-limit 256`.
- The lab is retryable educational evidence, not a benchmark or production-capacity certification.
- Do not touch or delete `mysql-primary`, `mysql-senior-scenarios-mysql`, either existing data/evidence volume, or the failed seventh-run harness.
- Do not implement an eighth-runtime heartbeat pipe, manifest chain, calibration reconstruction, or production-style verifier.
- Keep report/export reader status `READY_UNRUN` until the simple live demo passes; only then use `SCALED_REPRODUCED (S=10000 orders, 30000 items)`.
- Preserve the other three senior-scenario documents and their established evidence.

---

### Task 1: Replace the audit harness with one small Docker demo

**Files:**
- Delete: `mysql-handson/00-lab/senior-scenarios/container_harness.py`
- Delete: `mysql-handson/00-lab/senior-scenarios/container_verifier.py`
- Delete: `mysql-handson/00-lab/senior-scenarios/evidence_contract.py`
- Rename: `mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py` → `mysql-handson/00-lab/senior-scenarios/test_demo.py`
- Rename: `mysql-handson/00-lab/senior-scenarios/run-containerized.sh` → `mysql-handson/00-lab/senior-scenarios/run-demo.sh`
- Create: `mysql-handson/00-lab/senior-scenarios/demo.py`
- Modify: `mysql-handson/00-lab/senior-scenarios/README.md`

**Interfaces:**
- `demo.py run`: connects through Docker DNS, recreates only database `senior_demo`, seeds fixed data, runs two exports, and prints one JSON object.
- `run_demo(connection_factory, output_root: Path) -> dict`: returns the summary used by CLI and tests.
- `canonical_row(values: Sequence[object]) -> bytes`: returns one UTF-8 TSV row with `\n` terminator and rejects tab/newline-bearing strings.
- `run-demo.sh test|run|cleanup|inspect`: the only operator interface.
- Summary fields: `status`, `scale`, `buffered`, `chunked`, `equality`, `oltp`, and `boundaries`.

- [ ] **Step 1: Replace the old test suite with focused failing tests**

Use `git mv` for the two retained entry files, then replace the renamed test file with focused tests. The first test must derive expected bytes independently:

```python
def test_canonical_row_is_stable_and_rejects_tsv_breakers(self):
    self.assertEqual(
        b"7\tpaid\t12.30\n",
        canonical_row((7, "paid", Decimal("12.30"))),
    )
    with self.assertRaises(ValueError):
        canonical_row((7, "bad\tvalue"))
```

Add tests that exercise real file output with literal rows:

```python
class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.offset = 0

    def execute(self, statement):
        self.offset = 0

    def fetchall(self):
        return list(self.rows)

    def fetchmany(self, size):
        batch = self.rows[self.offset : self.offset + size]
        self.offset += len(batch)
        return batch

    def close(self):
        pass


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows

    def cursor(self):
        return FakeCursor(self.rows)


def test_buffered_and_chunked_exports_have_identical_count_order_and_sha(self):
    rows = [(1, 10, "paid"), (2, 20, "shipped"), (3, 30, "paid")]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        buffered = export_buffered(FakeConnection(rows), root / "buffered.tsv")
        chunked = export_chunked(
            FakeConnection(rows), root / "chunked.tsv", batch_size=2
        )
    self.assertEqual(3, buffered["rows"])
    self.assertEqual(buffered["rows"], chunked["rows"])
    self.assertEqual([1, 10], buffered["first_key"])
    self.assertEqual(buffered["first_key"], chunked["first_key"])
    self.assertEqual([3, 30], buffered["last_key"])
    self.assertEqual(buffered["last_key"], chunked["last_key"])
    self.assertEqual(buffered["sha256"], chunked["sha256"])
```

Add a coordinator test whose fake OLTP worker increments before and during each export and assert:

```python
self.assertEqual("SCALED_REPRODUCED", summary["status"])
self.assertEqual(
    {"rows": True, "order": True, "sha256": True}, summary["equality"]
)
self.assertGreater(summary["oltp"]["buffered_delta"], 0)
self.assertGreater(summary["oltp"]["chunked_delta"], 0)
```

Add a shell-policy test using a fake `docker` executable. It must run the real `run-demo.sh run` and assert that calls contain exact scoped names/labels/limits, contain no bind mount, and contain none of `python`, `uv`, `pip`, `mysql`, or `/private/tmp` as host commands/paths outside the container command.

- [ ] **Step 2: Run the new tests in the existing networkless test container and verify RED**

Temporarily adapt `run-demo.sh test` only enough to create a `python:3.13-slim` container with `--network none`, copy `demo.py`, `test_demo.py`, and `run-demo.sh`, and execute:

```text
python -m unittest -v /opt/test_demo.py
python -m py_compile /opt/demo.py /opt/test_demo.py
sh -n /opt/run-demo.sh
```

Run:

```bash
./run-demo.sh test
```

Expected: tests fail because `canonical_row`, `export_buffered`, `export_chunked`, and `run_demo` do not yet exist. Record the exact failing names; do not run host Python.

- [ ] **Step 3: Implement the minimal demo program**

Implement `demo.py` with these exact behaviors:

```python
EXPORT_SQL = """
SELECT o.id, i.id, o.created_at, o.status, i.qty, i.unit_price
FROM report_order AS o
JOIN report_item AS i ON i.order_id = o.id
ORDER BY o.created_at, o.id, i.id
"""
```

- Recreate only `senior_demo`.
- Create `report_order`, `report_item`, and `oltp_probe` with primary/foreign keys plus index `(created_at, id)` on orders and `(order_id, id)` on items.
- Seed through SQL set generation, not 40,000 individual client inserts.
- Derive three items per order and deterministic values.
- Start one dedicated OLTP connection/thread that repeatedly executes a parameterized `UPDATE oltp_probe SET counter=counter+1 WHERE id=%s` with autocommit.
- For each export, capture the OLTP counter immediately before and after the export operation.
- Buffered mode uses `fetchall()`; chunked mode uses `fetchmany(1000)` and writes each batch immediately.
- Write artifacts only below `/work/output` in the demo container.
- Each export returns row count, first/last `(order_id,item_id)`, SHA-256, and elapsed seconds.
- Stop/join the OLTP thread in `finally`; close every cursor/connection.
- Return `SCALED_REPRODUCED` only for exactly 30,000 equal ordered rows, equal SHA-256, and positive OLTP deltas for both modes.
- Print no password or connection environment.

- [ ] **Step 4: Implement the minimal Docker runner**

`run-demo.sh` must use exact resources:

```text
mysql-senior-demo-mysql
mysql-senior-demo-runner
mysql-senior-demo-test
mysql-senior-demo-net
mysql-senior-demo-data
```

`run` must fail if scoped resources already exist and instruct `cleanup`; it must not silently delete them. It creates the labeled network/volume/MySQL container, waits for health, creates a labeled Python container, copies `demo.py`, and starts it with an in-container command that installs exactly `mysql-connector-python==9.7.0` before executing `python /opt/demo.py run`. The fixed password is demo-only and passed through container environment, never written to a host file or printed.

`cleanup` may remove only those exact names after checking the scope label. It must not use globs or touch resources named `mysql-senior-scenarios-*` or `mysql-primary`.

- [ ] **Step 5: Run GREEN and static boundaries**

Run only:

```bash
./run-demo.sh test
git diff --check -- mysql-handson/00-lab/senior-scenarios
```

Expected: focused networkless container suite passes; compile and shell syntax pass; no host Python/cache/artifact exists.

- [ ] **Step 6: Rewrite the lab README**

Document only:

```bash
cd mysql-handson/00-lab/senior-scenarios
./run-demo.sh test
./run-demo.sh run
./run-demo.sh cleanup
```

Explain the exact scale, buffered/chunked difference, OLTP counter meaning, Docker-only macOS boundary, retryability, cleanup scope, and non-production limitation. Remove all references to seventh/eighth runtime, one-shot, manifests, historical loss, retained verifier, and `READY_UNRUN` evidence machinery from this lab README.

- [ ] **Step 7: Commit Task 1**

Stage exactly the lab-directory changes, verify the staged deletion/rename list, and commit:

```bash
git commit -m "refactor(mysql): simplify report export lab"
```

---

### Task 2: Rewrite the report/export chapter as a fluent senior tutorial

**Files:**
- Replace: `mysql-handson/13-senior-scenarios/04-report-export-isolation.md`
- Modify: `mysql-handson/13-senior-scenarios/README.md`

**Interfaces:**
- Consumes the four-command lab contract from Task 1.
- Produces a reader path with one decision model, one execution model, one runnable lab link, and one interview answer.

- [ ] **Step 1: Write documentation contract tests before rewriting**

Add tests to `test_demo.py` that read the chapter and routing README and require:

- the decision order `definition → snapshot → query shape → execution strategy → isolation → observability → recovery`;
- exact lab commands `test`, `run`, and `cleanup`;
- explicit boundaries for `fetchall`, `fetchmany(1000)`, keyset ordering, MVCC/undo retention, OLTP counter, local scale, and non-production inference;
- absence of reader-facing `Task 10`, seventh/eighth runtime, one-shot, calibration matrix, manifest chain, and verifier instructions.

- [ ] **Step 2: Run container tests and verify documentation RED**

Run `./run-demo.sh test` and require only the new documentation contract tests to fail against the old 4,021-line chapter.

- [ ] **Step 3: Replace the chapter**

Write a concise chapter with these sections in order:

1. `先给结论` — reports should use replicas/read models when freshness permits; otherwise use a bounded snapshot plus streaming/keyset export.
2. `先定义问题` — scale, freshness, consistency, output, OLTP budget, retry/recovery.
3. `数据与索引` — access path, covering trade-off, deterministic `(created_at,id,item_id)` order.
4. `一致性边界` — RR ReadView, current read distinction, undo retention, backdated mutations and high-watermark limits.
5. `执行策略` — why `fetchall` grows memory; why `fetchmany(1000)` bounds client memory but does not by itself shorten the database snapshot.
6. `隔离 OLTP` — replica/read model, resource governance, scheduling, chunk/resume, cancellation.
7. `如何观测` — rows, SHA/order correctness, elapsed time, OLTP progression, latency/error metrics required in production.
8. `Docker 缩小实验` — exact commands and truthful 10k/30k boundary.
9. `失败与恢复` — idempotent job ID, checkpoint, atomic publish, cleanup.
10. `面试回答模板` — a concise answer plus follow-up questions.

Do not embed executable Python fences or reproduce the removed audit platform. Link to the simple lab for code.

- [ ] **Step 4: Update routing text without changing other scenario evidence**

In `13-senior-scenarios/README.md`, preserve rows for scenarios 1–3. Keep report/export `READY_UNRUN` before Task 3, link to the simple lab, and replace “等待 Task 10” with “等待 Docker 缩小实验”. Correct the stale prose that currently says bulk-load/archive are `READY_UNRUN` while their table rows already show reproduced status.

- [ ] **Step 5: Run documentation gates and commit**

Run:

```bash
./run-demo.sh test
git diff --check -- mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/04-report-export-isolation.md
```

Run the repository's existing Markdown relative-link checker. Commit exactly the chapter, routing README, and documentation-test change:

```bash
git commit -m "docs(mysql): streamline report export scenario"
```

---

### Task 3: Execute the small demo and record only observed facts

**Files:**
- Modify on success: `mysql-handson/00-lab/senior-scenarios/README.md`
- Modify on success: `mysql-handson/13-senior-scenarios/04-report-export-isolation.md`
- Modify on success: `mysql-handson/13-senior-scenarios/README.md`
- Runtime only: exact `mysql-senior-demo-*` Docker resources

**Interfaces:**
- Consumes Task 1 runner and Task 2 truthful `READY_UNRUN` documentation.
- Produces either a bounded observed summary or an unchanged status plus direct failure diagnosis.

- [ ] **Step 1: Run preflight and the container-only suite**

```bash
git status --short --branch
./run-demo.sh inspect
./run-demo.sh test
```

Require clean Git state, no conflicting scoped demo resources, and passing tests.

- [ ] **Step 2: Execute the retryable simple demo**

```bash
./run-demo.sh run
```

Capture the single JSON summary. Success requires exact scale `10000/30000/1000`, both exports at 30,000 rows, equal order/SHA-256, positive buffered/chunked OLTP deltas, and status `SCALED_REPRODUCED`.

If it fails, diagnose the direct simple-lab failure; do not restore the audit platform. Because this is an educational retryable lab, a code/configuration bug may be fixed through TDD and rerun after review. Do not hide or overwrite the failed output.

- [ ] **Step 3: Patch only observed facts**

On success, update the three files with the run date, image versions, fixed scale, row count, both SHA values, elapsed seconds, OLTP deltas, and explicit “local demonstration, not production capacity” wording. Change only the report/export statuses to:

```text
SCALED_REPRODUCED (S=10000 orders, 30000 items)
```

Never copy a password, Docker environment, raw artifact, or unobserved latency/capacity claim into Markdown.

- [ ] **Step 4: Verify, clean demo resources, and commit**

Run the container suite, Markdown links, `git diff --check`, and status-scope gates. Then:

```bash
./run-demo.sh cleanup
```

Verify only `mysql-senior-demo-*` resources are absent and all pre-existing `mysql-senior-scenarios-*`/`mysql-primary` resources are unchanged. Commit the three observed-document paths only:

```bash
git commit -m "docs(mysql): record simple report export demo"
```

---

## Final verification

Run at final HEAD:

```bash
git status --short --branch
git diff --check main...HEAD
git log --oneline --decorate -12
```

Run `./run-demo.sh test` once more, the Markdown relative-link checker, and a read-only Docker name/label inventory. Require a clean worktree, no reader-facing abandoned audit instructions, no host Python/cache/artifacts, and no changes to pre-existing MySQL/evidence resources. Request final code review before merge; do not merge, push, delete the worktree, or clean the failed seventh-run resources without explicit user approval.
