# MySQL Report Export Containerized Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不執行 host Python、沒有 writable bind mount、也不把 raw evidence 寫進 macOS `/private/tmp` 或 repository 的前提下，完成第七次 MySQL report/export S 級實驗，保留 append-only named-volume 證據，並把經過唯讀驗證的結果回填教材。

**Architecture:** macOS 只執行 Git、POSIX shell 與 Docker CLI；既有 `mysql-senior-scenarios-mysql`、臨時 Python harness、臨時 verifier 透過專用 Docker network 溝通。harness 把 named evidence volume 掛到容器內 `/private/tmp`，從 committed scenario Markdown 提取既有 runner/controller/freeze helper，所有測量、manifest、artifact 與 raw evidence 都在容器內完成；最後由另一個 read-only verifier container 驗證。

**Tech Stack:** Markdown、POSIX shell、Docker Desktop、`mysql:8.0.36`、`python:3.13-slim`、MySQL Connector/Python `9.7.0`、Python 3.13 standard library、MySQL 8.0.36、InnoDB。

**Spec:** `docs/superpowers/specs/2026-08-02-mysql-containerized-evidence-design.md`

## Global Constraints

- 所有工作只在 `/Users/buoy/Development/gitrepo/interview/.worktrees/mysql-senior-scenarios`、branch `codex/mysql-senior-scenarios` 進行；不得把後續修改直接提交到 `main`。
- macOS 只允許 Git、POSIX shell、Docker inspection/management 與 `docker cp`；live work 和 raw-evidence verification 禁止 host `python`、`uv`、`pip`、`mysql` client。
- 禁止 writable bind mount；scenario 與 committed helper 必須用 `docker cp` 複製進 container，raw evidence 只能位於 named volume `mysql-senior-scenarios-evidence-v1`。
- 專用資源固定為 container `mysql-senior-scenarios-mysql`、container `mysql-senior-scenarios-harness`、network `mysql-senior-scenarios-net`、data volume `mysql-senior-scenarios-data`、evidence volume `mysql-senior-scenarios-evidence-v1`。
- 所有新建 Docker 資源固定 label `com.openai.codex.scope=mysql-senior-scenarios`；名稱存在但 label、image、mount 或 owner 不符時 fail closed。
- `mysql-primary` 不得被 start、stop、connect、disconnect、update、exec、remove 或以其他方式修改。
- MySQL 固定 `mysql:8.0.36`；harness/verifier 固定 `python:3.13-slim`；Connector 固定 `mysql-connector-python==9.7.0` 且 runner 必須是 pure Python implementation。
- MySQL 與 harness/verifier 都固定 `2 CPUs`、`2 GiB memory`、`256 PIDs`；resource failure 不得以提高 limits 後重跑掩蓋。
- harness 只透過 Docker DNS `mysql-senior-scenarios-mysql:3306` 連線；host-published `127.0.0.1:33306` 不得出現在 measured command。
- existing owned MySQL container 只允許一次 start attempt；若無法啟動或 identity contradictory，立即 BLOCKED，不刪除、不替換。
- 第七次 run 只建立一個 fresh `/private/tmp/mysql-senior-scenarios.<suffix>` runtime；任何 measured invocation 只執行一次，失敗時停止 dependent phases，不建立替代 runtime。
- S dataset 固定 `100000` orders、`300000` items、`10000` probes；保持已審核 authoritative-window、calibration、KILL、drain、heartbeat、artifact、resume 與 no-retry semantics。
- 歷史六個 runtime 只記錄為 `LOST_BY_EXTERNAL_TMP_CLEANUP`，`current_raw_verification=false`；舊 hash 只能標成 `historical_report_claim`，不能進入新 calibration/budget。
- phase 順序固定 `00-seed-freeze`、`10-kill-smoke`、`20-controls-calibration`、`30-buffered`、`40-chunked`、`50-resume-audit`、`60-final`；manifest 一旦建立不可改寫。
- 成功標籤只在 measured completion contract、七個 phase manifests 與 read-only verifier 全部通過後改為 `SCALED_REPRODUCED (S=100000)`。
- named evidence volume merge 後保留；只有使用者明確點名要求時才允許刪除。
- repository 修改全部使用 `apply_patch`；每次只 stage task 列出的 exact paths，不使用 `git add .` 或 `git add -A`。

---

## File Map

| 路徑 | 動作 | 單一責任 |
|---|---|---|
| `mysql-handson/00-lab/senior-scenarios/evidence_contract.py` | Create | fence extraction、strict JSON/type checks、historical-loss record、append-only manifest 與 final coverage |
| `mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py` | Create | 純檔案契約的 red/green tests；只在 container 內執行 |
| `mysql-handson/00-lab/senior-scenarios/container_harness.py` | Create | container bootstrap、MySQL seed/freeze、既有 controller phase sequencing、controlled teardown |
| `mysql-handson/00-lab/senior-scenarios/container_verifier.py` | Create | read-only final evidence、artifact、window history、binding 與 phase verification |
| `mysql-handson/00-lab/senior-scenarios/run-containerized.sh` | Create | macOS Docker-only ownership gate、resource creation、`docker cp`、offline/live/verify/cleanup commands |
| `mysql-handson/00-lab/senior-scenarios/README.md` | Create | 操作者入口、side-effect boundary、停止條件、保留與清理規則 |
| `mysql-handson/13-senior-scenarios/04-report-export-isolation.md` | Modify | 容器執行契約；成功時回填第七次實測與限制 |
| `mysql-handson/13-senior-scenarios/README.md` | Modify | 增加 container lab 入口；成功時只更新 report/export 狀態 |

### Shared interfaces

`evidence_contract.py` 對 harness、verifier 與 tests 公開以下精確介面：

```python
@dataclass(frozen=True)
class EvidenceBinding:
    scenario_commit: str
    scenario_sha256: str
    mysql_image_id: str
    mysql_container_id: str
    harness_image_id: str
    network_name: str
    volume_name: str
    cpu_limit: str
    memory_limit_bytes: int
    pids_limit: int
    program_sha256: dict[str, str]
```

Constants are `PHASES: tuple[str, str, str, str, str, str, str]` and
`HISTORICAL_PATHS: tuple[str, str, str, str, str, str]`. Function signatures
are `extract_programs(markdown: str) -> dict[str, str]`,
`write_historical_loss(volume_root: Path) -> Path`,
`create_phase_manifest(runtime_root: Path, phase: str, binding: EvidenceBinding) -> Path`,
`verify_phase_manifests(runtime_root: Path, binding: EvidenceBinding, require_final: bool) -> list[dict]`,
and `verify_final_coverage(runtime_root: Path, final_manifest: dict) -> None`.

`container_harness.py` 的 CLI 固定為：

```text
container_harness.py offline-check --scenario /opt/scenario.md --expected-commit <sha>
container_harness.py run-all --scenario /opt/scenario.md --expected-commit <sha>
```

`container_verifier.py` 的 CLI 固定為：

```text
container_verifier.py --volume-root /private/tmp --scenario /opt/scenario.md --expected-commit <sha>
```

`run-containerized.sh` 的 host CLI 固定為：

```text
./run-containerized.sh inspect
./run-containerized.sh offline-test
./run-containerized.sh run
./run-containerized.sh verify
./run-containerized.sh cleanup-transient
```

---

### Task 1: 建立 append-only evidence contract

**Files:**
- Create: `mysql-handson/00-lab/senior-scenarios/evidence_contract.py`
- Create: `mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py`

**Interfaces:**
- Consumes: approved spec §§7–9 and the shared interfaces above.
- Produces: deterministic extraction, exact historical-loss JSON, strict append-only phase manifests, and final-coverage verification for Tasks 2–5.

- [ ] **Step 1: 寫 extraction 與 strict-type failing tests**

Create tests that import only the standard library and assert exact marker ownership:

```python
class ExtractionTests(unittest.TestCase):
    def test_extracts_exact_three_programs(self):
        programs = extract_programs(SCENARIO.read_text(encoding="utf-8"))
        self.assertEqual(set(programs), {"export_runner.py", "scenario_controller.py", "freeze_audit.py"})
        self.assertEqual(sha256(programs["export_runner.py"]), "f774d36f3448c491668d1838075e2d18199e183fdbba415421fbcfb31e335d35")
        self.assertEqual(sha256(programs["scenario_controller.py"]), "9aa226bb5fedb48b949841fa933b00decfe80855c19bce244e9a6e4476c04148")
        self.assertEqual(sha256(programs["freeze_audit.py"]), "7461b1c0315f8b134cbe0f94d7ac6980e22034aa0703e587f853c11d3a443062")

    def test_duplicate_marker_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "exactly one Python fence"):
            extract_programs("```python\nEXPORT_SQL = 1\n```\n```python\nEXPORT_SQL = 2\n```\n")

    def test_bool_is_not_accepted_as_integer(self):
        with self.assertRaisesRegex(ValueError, "exact int"):
            require_exact_int(True, "file_count")
```

- [ ] **Step 2: 在 ephemeral container 執行 RED**

Run only Docker commands on macOS; copy files instead of mounting the worktree:

```bash
docker create --name mysql-senior-scenarios-offline-red \
  --label com.openai.codex.scope=mysql-senior-scenarios \
  --cpus 2 --memory 2g --pids-limit 256 \
  python:3.13-slim python /opt/test_evidence_contract.py
docker cp mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py mysql-senior-scenarios-offline-red:/opt/test_evidence_contract.py
docker cp mysql-handson/13-senior-scenarios/04-report-export-isolation.md mysql-senior-scenarios-offline-red:/opt/scenario.md
docker start -a mysql-senior-scenarios-offline-red
```

Expected: nonzero exit with import failure for `evidence_contract`; remove only exact transient container after recording the expected RED result.

- [ ] **Step 3: 實作 deterministic extraction 與 exact JSON primitives**

Implement marker-to-filename extraction without line-number slicing:

```python
PROGRAM_MARKERS = {
    "export_runner.py": "EXPORT_SQL",
    "scenario_controller.py": "KILL_PREFLIGHT_SQL",
    "freeze_audit.py": "def audit_task10_freeze",
}

def extract_programs(markdown: str) -> dict[str, str]:
    blocks = re.findall(r"```python\n(.*?)```", markdown, flags=re.DOTALL)
    result: dict[str, str] = {}
    for filename, marker in PROGRAM_MARKERS.items():
        matches = [block for block in blocks if marker in block]
        if len(matches) != 1:
            raise ValueError(f"expected exactly one Python fence for {marker!r}, got {len(matches)}")
        result[filename] = matches[0]
    return result

def require_exact_int(value: object, field: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{field} must be exact int")
    return value
```

All JSON writes use UTF-8, sorted keys, compact separators, trailing newline, `flush()`, `os.fsync()`, then `os.replace()` for replaceable bootstrap files. Immutable files and manifests use `os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)` and are never replaced.

- [ ] **Step 4: 寫 historical-loss 與 phase-manifest failing tests**

Tests must cover the six exact former paths:

```python
HISTORICAL_PATHS = (
    "/private/tmp/mysql-senior-scenarios.SJ38zd",
    "/private/tmp/mysql-senior-scenarios.LxogM8",
    "/private/tmp/mysql-senior-scenarios.UJXwDE",
    "/private/tmp/mysql-senior-scenarios.VW9rGt",
    "/private/tmp/mysql-senior-scenarios.rmovUN",
    "/private/tmp/mysql-senior-scenarios.LjCY6E",
)
```

Add these exact test methods and assertions:

| Test method | Required assertion |
|---|---|
| `test_historical_loss_is_truthful_and_exclusive` | parsed paths equal `HISTORICAL_PATHS`; status is exact string; verification flag has `type(value) is bool` and is false; a second write raises `FileExistsError` |
| `test_manifest_records_ordered_regular_files_and_tree_hash` | entries equal sorted regular-file paths and recomputed line-stream SHA equals `tree_hash` |
| `test_second_write_of_same_phase_is_rejected` | second `create_phase_manifest(runtime_root, "00-seed-freeze", binding)` raises `FileExistsError` |
| `test_prior_file_mutation_is_rejected_before_next_phase` | changing one recorded byte makes creation of `10-kill-smoke` raise `ValueError` |
| `test_phase_skip_or_reordering_is_rejected` | first phase `10-kill-smoke` and repeated earlier phase both raise `ValueError` |
| `test_missing_extra_corrupt_symlink_and_fifo_are_rejected` | each fixture is independently rejected; no manifest is created |
| `test_bool_float_and_numeric_string_are_rejected_for_integer_fields` | `True`, `1.0`, and `"1"` each raise `ValueError` |
| `test_final_manifest_covers_every_regular_file_except_itself` | exact scan set equals final entries and excludes only `phase-manifest-60-final.json` |

Each test creates its tree with `tempfile.TemporaryDirectory()` inside the container; no test path is a host mount.

- [ ] **Step 5: 實作 phase manifests**

Use these exact invariants:

```python
PHASES = (
    "00-seed-freeze",
    "10-kill-smoke",
    "20-controls-calibration",
    "30-buffered",
    "40-chunked",
    "50-resume-audit",
    "60-final",
)
```

`create_phase_manifest()` first verifies every existing prior manifest, rejects a phase unless it is the next exact value, walks with `os.scandir()` without following symlinks, rejects non-regular entries, excludes only its own target, and writes ordered entries `{path,size,sha256}`. `tree_hash` is SHA-256 over UTF-8 lines `path\0size\0sha256\n`. The binding is serialized in full and compared by exact type/value during verification. `60-final` additionally calls `verify_final_coverage()`.

- [ ] **Step 6: Copy implementation and rerun GREEN in a fresh container**

```bash
docker create --name mysql-senior-scenarios-offline-green \
  --label com.openai.codex.scope=mysql-senior-scenarios \
  --cpus 2 --memory 2g --pids-limit 256 \
  python:3.13-slim python -m unittest -v /opt/test_evidence_contract.py
docker cp mysql-handson/00-lab/senior-scenarios/evidence_contract.py mysql-senior-scenarios-offline-green:/opt/evidence_contract.py
docker cp mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py mysql-senior-scenarios-offline-green:/opt/test_evidence_contract.py
docker cp mysql-handson/13-senior-scenarios/04-report-export-isolation.md mysql-senior-scenarios-offline-green:/opt/scenario.md
docker start -a mysql-senior-scenarios-offline-green
```

Expected: all tests pass. Inspect both transient containers by exact name, then remove only those two containers.

- [ ] **Step 7: Static scope gate and commit**

```bash
git diff --check -- mysql-handson/00-lab/senior-scenarios/evidence_contract.py mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py
git add mysql-handson/00-lab/senior-scenarios/evidence_contract.py mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py
git diff --cached --name-only
git commit -m "test(mysql): define container evidence contract"
```

Expected staged paths: exactly the two Task 1 files.

---

### Task 2: 建立 Docker-only orchestration boundary

**Files:**
- Create: `mysql-handson/00-lab/senior-scenarios/run-containerized.sh`
- Create: `mysql-handson/00-lab/senior-scenarios/README.md`
- Modify: `mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py`

**Interfaces:**
- Consumes: Task 1 evidence functions and exact resource names from Global Constraints.
- Produces: five host commands whose only live boundary is Docker CLI; Task 3 harness and Task 4 verifier are copied into containers through this script.

- [ ] **Step 1: Add failing static-policy tests**

Add tests that read `run-containerized.sh` and require the exact constants while rejecting host execution and mounts:

```python
class ShellPolicyTests(unittest.TestCase):
    def test_exact_owned_names_and_limits(self):
        text = RUN_SCRIPT.read_text(encoding="utf-8")
        for value in (
            "mysql-senior-scenarios-mysql", "mysql-senior-scenarios-harness",
            "mysql-senior-scenarios-net", "mysql-senior-scenarios-data",
            "mysql-senior-scenarios-evidence-v1", "--cpus 2", "--memory 2g",
            "--pids-limit 256", "com.openai.codex.scope=mysql-senior-scenarios",
        ):
            self.assertIn(value, text)

    def test_no_host_runtime_or_bind_mount(self):
        text = RUN_SCRIPT.read_text(encoding="utf-8")
        for forbidden in ("127.0.0.1:33306", "--mount type=bind", "-v $", "docker compose down", "docker volume rm"):
            self.assertNotIn(forbidden, text)
        self.assertIsNone(re.search(r"(?m)^(?:uv|python|python3|pip|pip3|mysql)\s", text))
```

Run the Task 1 container test command. Expected: failure because the script does not exist.

- [ ] **Step 2: Implement exact inspection helpers**

Start the shell script with fixed constants and fail-closed functions:

```sh
#!/bin/sh
set -eu
SCOPE_LABEL='com.openai.codex.scope=mysql-senior-scenarios'
MYSQL_CONTAINER='mysql-senior-scenarios-mysql'
HARNESS_CONTAINER='mysql-senior-scenarios-harness'
VERIFIER_CONTAINER='mysql-senior-scenarios-verifier'
NETWORK='mysql-senior-scenarios-net'
DATA_VOLUME='mysql-senior-scenarios-data'
EVIDENCE_VOLUME='mysql-senior-scenarios-evidence-v1'
PYTHON_IMAGE='python:3.13-slim'

require_scope_label() {
  kind=$1
  name=$2
  actual=$(docker inspect --format "{{ index .Config.Labels \"com.openai.codex.scope\" }}" "$name")
  test "$actual" = 'mysql-senior-scenarios' || {
    printf '%s %s has unexpected scope label: %s\n' "$kind" "$name" "$actual" >&2
    exit 1
  }
}
```

`inspect` must print exact state/image/labels/mounts/network/restart/health/CPU/memory/PID data for the owned MySQL container and read-only state for `mysql-primary`. It performs no start, create, connect, update, exec or removal.

- [ ] **Step 3: Implement idempotent owned network/volume gates**

For `run`, create missing network/volume with the exact label; if present, require the label. Do not operate on resources selected by wildcard. Use exact-name inspections:

```sh
docker network create --label "$SCOPE_LABEL" "$NETWORK"
docker volume create --label "$SCOPE_LABEL" "$EVIDENCE_VOLUME"
```

Before creation, branch on `docker network inspect "$NETWORK"` and `docker volume inspect "$EVIDENCE_VOLUME"`; an existing unlabeled object is a hard failure. Never remove or recreate an existing evidence volume.

- [ ] **Step 4: Implement MySQL one-start and resource gate**

The run path must:

1. require the exact MySQL container label, `mysql:8.0.36` image reference, and only `mysql-senior-scenarios-data:/var/lib/mysql` as its data mount;
2. record pre-state of both MySQL containers;
3. apply `docker update --cpus 2 --memory 2g --pids-limit 256 mysql-senior-scenarios-mysql` once;
4. connect the owned MySQL container to the dedicated network only if absent;
5. call `docker start mysql-senior-scenarios-mysql` at most once when it is not running;
6. poll health with a bounded 60-second shell loop and fail if it is not `healthy`;
7. re-inspect limits, image ID, data volume, restart policy and `mysql-primary` unchanged state before creating harness.

No retry loop may contain `docker start`.

- [ ] **Step 5: Implement container-copy and subcommand lifecycle**

`offline-test`, `run`, and `verify` create containers with `docker create`, not bind mounts. Exact harness mount:

```sh
--mount type=volume,src=mysql-senior-scenarios-evidence-v1,dst=/private/tmp
```

Exact verifier mount:

```sh
--mount type=volume,src=mysql-senior-scenarios-evidence-v1,dst=/private/tmp,readonly
```

Use `docker cp` for scenario, `evidence_contract.py`, `container_harness.py`, `container_verifier.py`, and tests. `cleanup-transient` may remove only exact harness/verifier/offline-test containers after verifying their label; it must not remove MySQL, data volume, evidence volume, `mysql-primary`, or wildcard-selected resources.

The live harness command installs the pinned connector inside the container and
then starts the harness in the same process chain:

```sh
sh -c 'python -m pip install --no-cache-dir mysql-connector-python==9.7.0 && exec python /opt/container_harness.py run-all --scenario /opt/scenario.md --expected-commit "$1"' sh "$SCENARIO_COMMIT"
```

This command is passed as the `python:3.13-slim` container command; it is never
evaluated by the macOS shell as a host Python or pip command. Package installation
finishes before the harness creates the seventh runtime or starts measurement.

- [ ] **Step 6: Write operator README**

Document in this exact order:

```markdown
# Report/export container lab
## macOS side-effect boundary
## Exact owned Docker resources
## Read-only inspection
## Offline test
## One-shot live run
## Read-only verification
## Controlled stop
## Transient cleanup
## Retained evidence volume
```

State that `run` mutates dedicated Docker resources and MySQL schema, starts the owned MySQL container at most once, never touches `mysql-primary`, and does not imply production capacity. State that deleting `mysql-senior-scenarios-evidence-v1` is deliberately absent from the script.

- [ ] **Step 7: Run shell and policy gates inside a container**

```bash
docker run --rm -i --label com.openai.codex.scope=mysql-senior-scenarios --cpus 2 --memory 2g --pids-limit 256 python:3.13-slim sh -n /dev/stdin < mysql-handson/00-lab/senior-scenarios/run-containerized.sh
```

Because shell redirection only provides script bytes and creates no runtime, it is allowed for syntax verification. Then rerun the Task 1 copy-based unittest container with the new shell file copied to `/opt/run-containerized.sh`. Expected: all tests pass.

- [ ] **Step 8: Verify exact scope and commit**

```bash
git diff --check -- mysql-handson/00-lab/senior-scenarios/run-containerized.sh mysql-handson/00-lab/senior-scenarios/README.md mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py
git add mysql-handson/00-lab/senior-scenarios/run-containerized.sh mysql-handson/00-lab/senior-scenarios/README.md mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py
git diff --cached --name-only
git commit -m "feat(mysql): add Docker-only experiment boundary"
```

Expected staged paths: exactly the three Task 2 files.

---

### Task 3: 實作 container harness 與 controlled teardown

**Files:**
- Create: `mysql-handson/00-lab/senior-scenarios/container_harness.py`
- Modify: `mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py`
- Modify: `mysql-handson/00-lab/senior-scenarios/run-containerized.sh`

**Interfaces:**
- Consumes: `EvidenceBinding`, `extract_programs()`, `write_historical_loss()`, `create_phase_manifest()`, and scenario runner/controller/freeze-helper fences.
- Produces: one fresh seventh runtime, one-shot phase ledger, controlled teardown, and seven immutable manifests for Task 4.

- [ ] **Step 1: Add failing harness policy and state-machine tests**

Use fake subprocess and fake connector boundaries; tests must not require a live MySQL server:

Add a `HarnessStateTests` class with these exact cases:

| Test method | Required assertion |
|---|---|
| `test_phase_order_is_exact_and_no_retry` | fake call log equals `INVOCATIONS` exactly once and manifests equal `PHASES` |
| `test_failure_stops_later_phases_and_runs_teardown_once` | injected `buffered-1` failure produces no later invocation and teardown count equals one |
| `test_existing_seventh_runtime_record_fails_before_measurement` | pre-created record raises before fake connector call count changes from zero |
| `test_connection_is_docker_dns_3306_and_password_is_env_only` | captured kwargs contain exact host/port, no password CLI token, and environment supplies password |
| `test_measured_ledger_rejects_second_invocation_id` | duplicate invocation ID raises before subprocess launch |
| `test_bootstrap_rejects_wrong_connector_or_nonpure_connection` | wrong version and a connection not created with/verified as `use_pure=True` each fail; module `HAVE_CEXT` is recorded but does not decide the connection implementation |
| `test_bootstrap_rejects_wrong_cgroup_limits_mount_or_dns` | each wrong CPU/memory/PID/mount/DNS fixture fails before runtime creation |

Run the copy-based unittest container. Expected: import failure for `container_harness`.

- [ ] **Step 2: Implement bootstrap identity and program materialization**

`offline-check` and `run-all` must:

```python
EXPECTED_CONNECTOR = "9.7.0"
EXPECTED_HOST = "mysql-senior-scenarios-mysql"
EXPECTED_PORT = 3306
EXPECTED_MEMORY = 2 * 1024**3
EXPECTED_PIDS = 256
```

Read `/sys/fs/cgroup/cpu.max`, `/sys/fs/cgroup/memory.max`, and `/sys/fs/cgroup/pids.max`; verify two CPUs, `2147483648` bytes, and `256`. Verify `/private/tmp` is a mounted named-volume filesystem from container inspect evidence copied to `/opt/bootstrap-inspect.json`; verify Docker DNS resolves the exact MySQL name; verify `mysql.connector.__version__ == "9.7.0"`, record `threadsafety` and module `HAVE_CEXT`, and require every runner connection to be requested with `use_pure=True` and verified as the pure implementation.

Extract the three programs, compare their SHA-256 with the three fixed reviewed hashes from Task 1, write them into the fresh runtime with mode `0600`, and run `py_compile` before any database call.

- [ ] **Step 3: Implement immutable historical loss and seventh identity**

At volume root, create `historical-evidence-loss.json` and `seventh-runtime.json` with exclusive creation. The historical file contains all six exact paths, `status`, `current_raw_verification`, and any earlier hashes only under `historical_report_claim`. The seventh file contains one generated nonempty suffix, runtime path, UTC creation time, scenario commit/hash and program hashes. If either file already exists with contradictory content, stop; never silently create another runtime.

- [ ] **Step 4: Implement phase runner around the reviewed controller**

Represent the one-shot ledger as immutable JSON lines. Every invocation ID is appended before launch with `state=STARTING`, then reconciled to one terminal result without reusing the ID. The exact ordered invocations are:

```python
INVOCATIONS = (
    "kill-preflight-1", "oltp-smoke-1",
    "control-1", "control-2", "control-3", "latency-calibration-1",
    "buffered-1", "buffered-2", "buffered-3",
    "chunked-1", "chunked-2", "chunked-3",
    "resume-interrupt-1", "resume-complete-1",
)
```

Call the existing `scenario_controller.py` with `--host mysql-senior-scenarios-mysql --port 3306`, runtime-root-local runner, metrics, stdout and stderr paths, and password from `MYSQL_PASSWORD`. Do not alter authoritative-history/calibration/KILL/drain/heartbeat arguments already fixed in the scenario.

- [ ] **Step 5: Implement seed/freeze and phase boundaries**

`run-all` performs:

```text
bootstrap -> drop/recreate/reseed -> source fingerprint -> six freeze triggers
-> six negative probes -> 00-seed-freeze
-> KILL preflight + pure smoke -> 10-kill-smoke
-> three controls + calibration -> 20-controls-calibration
-> buffered 1..3 -> 30-buffered
-> chunked 1..3 -> 40-chunked
-> interruption/resume + external artifact audit -> 50-resume-audit
-> controlled teardown + final audits -> 60-final
```

Reuse the scenario SQL and freeze helper exactly. After each phase, verify all prior manifests before writing the next one. Any child `FAILED`, `UNKNOWN`, `ABORTED` outside the planned interruption, malformed evidence, budget breach, source change, resource failure or Docker binding drift stops dependent work.

- [ ] **Step 6: Implement controlled teardown**

In `finally`, if MySQL was reached, inspect active processes scoped to the experiment user, preserve all stdout/stderr/state, verify report-source fingerprint and probe schema/count, drop exactly six owned freeze triggers, re-check global variables and container identity, and write `controlled-stop.json`. `60-final` is written only when every required success audit passes; an earlier failure may write a `failed-phase.json` but never a success manifest for an incomplete phase.

- [ ] **Step 7: Run offline tests and compile all committed Python inside container**

Use `run-containerized.sh offline-test`. It must copy every Python file and scenario into a bounded ephemeral container, install Connector `9.7.0` there, run all unittests, extract the three scenario fences, and compile the six Python inputs. Expected: zero failures; no live MySQL connection and no named evidence volume mutation.

- [ ] **Step 8: Verify and commit**

```bash
git diff --check -- mysql-handson/00-lab/senior-scenarios/container_harness.py mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py mysql-handson/00-lab/senior-scenarios/run-containerized.sh
git add mysql-handson/00-lab/senior-scenarios/container_harness.py mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py mysql-handson/00-lab/senior-scenarios/run-containerized.sh
git diff --cached --name-only
git commit -m "feat(mysql): orchestrate containerized report evidence"
```

Expected staged paths: exactly the three Task 3 files.

---

### Task 4: 實作獨立 read-only verifier

**Files:**
- Create: `mysql-handson/00-lab/senior-scenarios/container_verifier.py`
- Modify: `mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py`
- Modify: `mysql-handson/00-lab/senior-scenarios/run-containerized.sh`

**Interfaces:**
- Consumes: complete named-volume tree, `verify_phase_manifests()`, scenario fences and seventh binding.
- Produces: stdout-only `VERIFIED` or nonzero failure; verifier has no writable evidence/MySQL path.

- [ ] **Step 1: Add failing verifier tests**

Construct a complete miniature seven-phase tree and add these exact cases:

| Test method | Required assertion |
|---|---|
| `test_verifier_accepts_complete_read_only_tree` | return status is `VERIFIED`, checked phase count is seven, and final tree hash matches |
| `test_verifier_rejects_missing_final_manifest` | removing final manifest produces nonzero verifier result |
| `test_verifier_rejects_changed_authoritative_history` | one changed window sequence is rejected |
| `test_verifier_rejects_calibration_derivative_mismatch` | one changed derived budget is rejected |
| `test_verifier_rejects_artifact_row_order_or_sha_mismatch` | order corruption and hash corruption are independently rejected |
| `test_verifier_rejects_source_probe_or_binding_drift` | each drift fixture is independently rejected |
| `test_verifier_writes_nothing_to_volume` | ordered tree digest and mtime map are identical before/after verification |

Run offline-test. Expected: import failure for `container_verifier`.

- [ ] **Step 2: Implement verifier checks**

The verifier must perform, in order:

1. confirm `/private/tmp` is not writable and the process has no MySQL data mount;
2. parse exact-type historical/seventh records;
3. re-extract scenario fences and compare committed/runtime hashes;
4. verify all seven manifests and final coverage;
5. reconstruct every control accepted window and frozen calibration derivative;
6. verify authoritative full histories, final atomic snapshots and no sequence regression;
7. stream every buffered/chunked/resumed artifact to verify rows, unique/order keys, high/last cursor, business aggregate and canonical SHA equality;
8. verify source pre/post, probe schema/count/counter, trigger teardown, globals, process cleanup, limits and container binding;
9. print one compact JSON object with `status="VERIFIED"`, runtime path, final tree hash and checked counts.

It must not import `mysql.connector`, open a network socket, or write a report file.

- [ ] **Step 3: Make `verify` prove container isolation before execution**

`run-containerized.sh verify` creates a fresh verifier with:

```sh
docker create --name mysql-senior-scenarios-verifier \
  --label com.openai.codex.scope=mysql-senior-scenarios \
  --network none --cpus 2 --memory 2g --pids-limit 256 \
  --mount type=volume,src=mysql-senior-scenarios-evidence-v1,dst=/private/tmp,readonly \
  python:3.13-slim python /opt/container_verifier.py \
  --volume-root /private/tmp --scenario /opt/scenario.md --expected-commit "$SCENARIO_COMMIT"
```

Copy committed code/scenario with `docker cp` before start. Inspect the created container and fail unless network is `none`, evidence mount is read-only, no MySQL data volume or writable host mount exists, and limits match. The ordinary container layer may contain the copied verifier and scenario; only the evidence mount is part of the evidence immutability claim.

- [ ] **Step 4: Run complete offline GREEN and commit**

Run `run-containerized.sh offline-test`; require all unit tests, miniature verifier and Python compilation to pass. Then:

```bash
git diff --check -- mysql-handson/00-lab/senior-scenarios/container_verifier.py mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py mysql-handson/00-lab/senior-scenarios/run-containerized.sh
git add mysql-handson/00-lab/senior-scenarios/container_verifier.py mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py mysql-handson/00-lab/senior-scenarios/run-containerized.sh
git diff --cached --name-only
git commit -m "test(mysql): verify report evidence read-only"
```

Expected staged paths: exactly the three Task 4 files.

---

### Task 5: 同步教材的 container execution contract

**Files:**
- Modify: `mysql-handson/13-senior-scenarios/04-report-export-isolation.md`
- Modify: `mysql-handson/13-senior-scenarios/README.md`
- Modify: `mysql-handson/00-lab/senior-scenarios/README.md`
- Modify: `mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py`

**Interfaces:**
- Consumes: Tasks 1–4 exact scripts and the existing runner/controller/freeze hashes.
- Produces: reader-visible Docker-only commands and static gates, while evidence status remains `READY_UNRUN` before Task 6.

- [ ] **Step 1: Add failing documentation-contract tests**

Require scenario/README prose for exact network, volume, Docker DNS, resource limits, host exclusions, seventh-run history, seven phases, read-only verifier, and retained-volume rule. Explicitly forbid a host live command containing `uv run`, `python`, `mysql`, `127.0.0.1:33306`, `mktemp -d /private/tmp/mysql-senior-scenarios`, or `rm -rf`.

- [ ] **Step 2: Replace host execution examples with one container lab entry**

In scenario §§runner/controller/freeze and the evidence section, preserve canonical Python fences byte-for-byte but replace operational prose/commands with:

```bash
cd mysql-handson/00-lab/senior-scenarios
./run-containerized.sh inspect
./run-containerized.sh offline-test
./run-containerized.sh run
./run-containerized.sh verify
```

Explain that `/private/tmp` in program arguments is the evidence volume inside harness, connection is `mysql-senior-scenarios-mysql:3306`, and macOS receives no runtime/artifact path. Keep status `READY_UNRUN`.

- [ ] **Step 3: Add explicit historical-loss and phase semantics**

Document the six lost paths, truthful status fields, no historical calibration reuse, seventh numbering, manifest phase order, append-only verification, one-shot/no-retry behavior, resource limits, and failure outcome. Do not copy raw evidence or S results into Markdown before live verification.

- [ ] **Step 4: Link the lab from ch13 README**

Add one link to `../00-lab/senior-scenarios/README.md` in the report/export row or adjacent paragraph. Both report/export owner rows and the four-scenario table remain `READY_UNRUN`.

- [ ] **Step 5: Run offline, fence-equality, link and diff gates**

```bash
mysql-handson/00-lab/senior-scenarios/run-containerized.sh offline-test
git diff --check -- mysql-handson/00-lab/senior-scenarios/README.md mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/04-report-export-isolation.md
rg -n 'READY_UNRUN|mysql-senior-scenarios-net|mysql-senior-scenarios-evidence-v1|mysql-senior-scenarios-mysql:3306|read-only|LOST_BY_EXTERNAL_TMP_CLEANUP' mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/04-report-export-isolation.md mysql-handson/00-lab/senior-scenarios/README.md
```

Expected: offline suite passes, three extracted program hashes remain exactly Task 1 values, local Markdown links resolve, no completed evidence status appears.

- [ ] **Step 6: Commit documentation contract**

```bash
git add mysql-handson/00-lab/senior-scenarios/README.md mysql-handson/00-lab/senior-scenarios/test_evidence_contract.py mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/04-report-export-isolation.md
git diff --cached --name-only
git commit -m "docs(mysql): document containerized report run"
```

Expected staged paths: exactly the four Task 5 files.

---

### Task 6: 執行第七次 one-shot live experiment

**Files:**
- Runtime only: Docker resources named in Global Constraints
- Evidence only: Docker volume `mysql-senior-scenarios-evidence-v1`
- Report only: `.superpowers/sdd/2026-08-02-mysql-containerized-evidence/task-6-report.md` (ignored)

**Interfaces:**
- Consumes: Tasks 1–5 committed HEAD and clean index.
- Produces: either a complete seven-phase seventh runtime, or a truthful BLOCKED/FAILED runtime with no replacement/retry.

- [ ] **Step 1: Record immutable Git and Docker preflight**

Run:

```bash
git status --short --branch
git rev-parse HEAD
mysql-handson/00-lab/senior-scenarios/run-containerized.sh inspect
```

Expected: feature worktree/index clean; exact commit recorded; `mysql-primary` state recorded read-only; no host `/private/tmp/mysql-senior-scenarios.*` path is created. If MySQL identity is contradictory, stop before `run`.

- [ ] **Step 2: Run the complete offline gate at the same HEAD**

```bash
mysql-handson/00-lab/senior-scenarios/run-containerized.sh offline-test
```

Expected: all policy/unit/miniature/compile/hash checks pass in container. Inspect and remove only the labeled offline-test container.

- [ ] **Step 3: Execute the one allowed live command once**

```bash
mysql-handson/00-lab/senior-scenarios/run-containerized.sh run
```

Do not invoke `run` a second time. If the one start attempt, bootstrap, seed, gate, measured invocation or teardown fails, record the exact last completed phase and stop this task; do not improvise replacement, retry, larger limits or alternate runtime.

- [ ] **Step 4: Inspect post-state without reading raw evidence on host**

```bash
mysql-handson/00-lab/senior-scenarios/run-containerized.sh inspect
docker inspect mysql-senior-scenarios-harness
docker volume inspect mysql-senior-scenarios-evidence-v1
git status --short --branch
```

Expected on success: harness terminal exit `0`, MySQL identity/limits unchanged from post-start binding, `mysql-primary` unchanged, repository clean, evidence volume retained. Raw files are not copied to host.

- [ ] **Step 5: Write ignored execution report**

Report exact commands, exit codes, container/image IDs, one-start count, invocation ledger, phase status, resource events and any blocker. A failed run says no performance conclusion and does not schedule Task 7 documentation.

---

### Task 7: Run independent read-only verification

**Files:**
- Runtime only: temporary `mysql-senior-scenarios-verifier`
- Read-only evidence: `mysql-senior-scenarios-evidence-v1`
- Report only: `.superpowers/sdd/2026-08-02-mysql-containerized-evidence/task-7-report.md` (ignored)

**Interfaces:**
- Consumes: Task 6 complete `60-final` runtime.
- Produces: independent stdout `VERIFIED` summary and zero evidence-volume writes.

- [ ] **Step 1: Capture evidence-volume metadata and harness terminal state**

Use `docker inspect` only. Record evidence volume name/label/mountpoint metadata and harness exit status. Do not open Docker Desktop filesystem paths from macOS.

- [ ] **Step 2: Run verifier exactly once**

```bash
mysql-handson/00-lab/senior-scenarios/run-containerized.sh verify
```

Expected: verifier container inspection proves network none, evidence mount read-only, no MySQL data mount or writable host mount and exact limits; stdout is one `status=VERIFIED` JSON object; exit `0`.

- [ ] **Step 3: Prove verifier did not mutate evidence**

The final manifest tree hash before and after verification must match the verifier-reported value. Since the verifier cannot write, any mismatch is a failure; do not rerun to obtain a passing result.

- [ ] **Step 4: Record review report**

Record checked counts, final tree hash, program/scenario/container binding, artifact equality, authoritative histories, calibration reconstruction, source/probe/teardown audits, and exact verifier isolation. If any check fails, leave docs `READY_UNRUN` and stop.

---

### Task 8: 回填 verified S evidence 並做 final repository audit

**Files:**
- Modify: `mysql-handson/13-senior-scenarios/04-report-export-isolation.md`
- Modify: `mysql-handson/13-senior-scenarios/README.md`

**Interfaces:**
- Consumes: Task 6 complete evidence plus Task 7 `VERIFIED` report.
- Produces: bounded `SCALED_REPRODUCED (S=100000)` documentation and integration-ready feature branch.

- [ ] **Step 1: Patch only verified facts**

Replace `## Task 10 待填证据` with a dated evidence section containing exact:

- Docker images/IDs, CPU/memory/PID limits, network and volume;
- seventh runtime ID and all seven manifest/tree hashes;
- historical six-runtime loss limitation;
- seed/source/freeze/negative-probe results;
- KILL smoke, three controls, frozen calibration and authoritative histories;
- buffered/chunked three-run raw sets, medians/ranges and safety/interference separation;
- artifact rows/order/distinct/aggregate/SHA equality;
- three-part interruption/resume timeline;
- source/probe/process/global/container teardown;
- read-only verifier result;
- observed S facts versus untested production capacity.

Do not transcribe secrets or claim native macOS/production capacity.

- [ ] **Step 2: Update exactly two README statuses**

Change owner rows 6 and 7 plus the four-scenario table report row from `READY_UNRUN` to `SCALED_REPRODUCED (S=100000)`. Preserve all other scenario statuses.

- [ ] **Step 3: Run final offline and documentation gates**

```bash
mysql-handson/00-lab/senior-scenarios/run-containerized.sh offline-test
git diff --check -- mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/04-report-export-isolation.md
rg -n 'SCALED_REPRODUCED \(S=100000\)|LOST_BY_EXTERNAL_TMP_CLEANUP|current_raw_verification=false|VERIFIED|2 CPUs|2 GiB|256 PIDs' mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/04-report-export-isolation.md
```

Also run the repository's existing Markdown relative-link checker and verify the three canonical fence hashes are unchanged.

- [ ] **Step 4: Commit evidence documentation**

```bash
git add mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/04-report-export-isolation.md
git diff --cached --name-only
git diff --cached --check
git commit -m "docs(mysql): record containerized report evidence"
```

Expected staged paths: exactly the two Task 8 files.

- [ ] **Step 5: Cleanup transient containers only**

```bash
mysql-handson/00-lab/senior-scenarios/run-containerized.sh cleanup-transient
```

Verify harness/verifier/offline-test containers are absent. Retain `mysql-senior-scenarios-evidence-v1`; do not delete MySQL/data. Disconnect/remove the dedicated network only if the script proves every attached endpoint has the exact experiment label and the owned MySQL lifecycle permits it; otherwise retain the network and report why.

- [ ] **Step 6: Final branch verification**

```bash
git status --short --branch
git log --oneline --decorate -8
git diff --name-status main...HEAD
git show --check --stat HEAD
docker volume inspect mysql-senior-scenarios-evidence-v1
```

Require clean feature worktree/index, only planned repository paths, retained labeled evidence volume, and no modification to `mysql-primary`. Then invoke `superpowers:finishing-a-development-branch`; do not merge, push, delete the branch, delete the worktree or delete evidence without the user's explicit choice.
