# 大型报表与导出隔离：从一致性边界到可续跑发布

> **证据状态**
>
> - `READY_UNRUN`：本文件固定的 S 级资料集、三组并发矩阵与 interruption／resume 尚未执行；Task 10 才记录实测。
> - `REUSED`：MVCC、JOIN／filesort／temporary、keyset pagination 与 replica lag 直接复用 ch05、ch08、ch09 的 owner。
> - `REASONED`：Primary／shared replica／dedicated reporting replica／analytical store 的生产选择是架构推导，不是本机实测。

## 题目与先问的约束

> 要导出一份千万级 JOIN 报表，线上 MySQL 不能被拖慢，输出要能重试、续跑并证明完整。你会怎么定义一致性、隔离资源和发布文件？

不要先回答“加索引”或“放从库”。先把下面八个问题问清楚：

1. 调用方要同步 HTTP response，还是能接受 async job／轮询／callback？
2. 要求跨表同一个精确 as-of snapshot，还是接受固定 `(created_at,id)` high watermark？
3. watermark 内的 row 在导出期间是 immutable，还是仍会 UPDATE／DELETE？
4. 能接受多少 staleness？如果走 replica，replica lag budget 是多少？
5. 预计 row 数、byte 数和格式是什么？consumer 能多快消费，是否有 backpressure？
6. 失败后从零重跑，还是按 cursor／part resume？同一个 job 可以发布几次？
7. 放在 Primary、shared replica、dedicated reporting replica，还是 analytical store？
8. OLTP P95 budget 与 export completion SLA 各是多少？谁有优先级？

### 一致性决策树

```text
需要跨表、跨 batch 的精确 as-of value snapshot？
├─ 否：membership 是否已经 materialize／snapshot？
│  ├─ 是：async job + keyset chunks + bounded part + checkpoint + atomic publish
│  └─ 否：cursor keys 是否 immutable 且 insertion-monotone？
│     ├─ 是：固定 high watermark 可作为完整 membership boundary
│     └─ 否：backdated／in-bound INSERT 可在 resume 的新 ReadView 出现；必须换 boundary
└─ 是：必须另选真正的 version source
   ├─ versioned history / temporal model
   ├─ database 或 replica snapshot
   ├─ CDC-built versioned read model
   ├─ analytical snapshot
   └─ 有明确 undo／purge budget 的 bounded MVCC snapshot
```

**硬边界**：`(created_at,id)` 只是 query upper bound。只有 cursor keys 同时 immutable、insertion-monotone，或 job membership 已 materialize／snapshot 时，它才是完整 membership boundary。后来发生的 **backdated** 或其他 in-bound INSERT 若 tuple `<= high`，会在 resume 的新 ReadView 出现；这个 tuple 也不能冻结既有 row 的 UPDATE／DELETE。production 必须选 monotone immutable keys、materialized membership、versioned history、数据库／replica snapshot、CDC 构建的 versioned read model、analytical snapshot，或明确接受 undo／purge 成本的 bounded MVCC snapshot。

InnoDB 在 RR 下的普通 consistent read 会在同一 transaction 复用第一条一致性读建立的 snapshot；RC 则每条一致性读建立新 snapshot。长时间持有 RR ReadView 会让仍被它需要的 undo 版本不能 purge，使 `History list length` 上升。因此，“一个长 transaction 就能得到快照”是正确性工具，不是免费的隔离工具。见 [ch05 snapshot／长事务 owner](../05-mvcc-and-transaction/README.md)、[MySQL 8.0 consistent nonlocking reads](https://dev.mysql.com/doc/refman/8.0/en/innodb-consistent-read.html)、[transaction isolation levels](https://dev.mysql.com/doc/refman/8.0/en/innodb-transaction-isolation-levels.html) 与 [purge configuration](https://dev.mysql.com/doc/refman/8.0/en/innodb-purge-configuration.html)。

### Baseline 决策

本场景选择：

- async job，不让 HTTP connection 承担千万行传输；
- job 建立时捕获固定 high watermark；
- S 级资料在实验期间 freeze：`report_order`／`report_item` 不允许 INSERT／UPDATE／DELETE，因此 watermark 与 immutable source 一起固定 membership 和 values；
- chunked mode 用 `(created_at,id)` keyset，不使用 offset；
- 每批写 deterministic part，part rename 后才推进 checkpoint；
- 所有 part 完成后才生成并原子发布 `artifact.tsv`；
- OLTP probe、fingerprint、disk reserve、MySQL health 是停止条件，不是事后说明；
- buffered one-shot 只作 control，不是生产默认答案。

## 固定 S 级 schema、seed 与查询顺序

Task 10 只能按这里的顺序建立资料：先三张表，再 `seed_digit`，再 `report_order`，再 `report_item`，drop helper，最后 `oltp_probe`。资料量固定为 `100000` orders、每单恰好三项（`300000` items）与 `10000` probe rows。seed 后要 freeze `report_order` 与 `report_item`，只允许 `oltp_probe` 写入；必须实际拒绝 backdated INSERT、UPDATE、DELETE，并比较 source pre/post fingerprint。没有这个 S-only freeze，resume 的新 ReadView 不能证明固定 membership 或 values。

```sql
CREATE TABLE report_order (
  id         BIGINT UNSIGNED NOT NULL,
  tenant_id  BIGINT UNSIGNED NOT NULL,
  status     TINYINT UNSIGNED NOT NULL,
  created_at DATETIME(6) NOT NULL,
  PRIMARY KEY (id),
  KEY idx_created_id (created_at, id)
) ENGINE=InnoDB;

CREATE TABLE report_item (
  id         BIGINT UNSIGNED NOT NULL,
  order_id   BIGINT UNSIGNED NOT NULL,
  qty        INT UNSIGNED NOT NULL,
  unit_price DECIMAL(18,2) NOT NULL,
  PRIMARY KEY (id),
  KEY idx_order (order_id)
) ENGINE=InnoDB;

CREATE TABLE oltp_probe (
  id      BIGINT UNSIGNED NOT NULL,
  counter BIGINT UNSIGNED NOT NULL DEFAULT 0,
  payload VARCHAR(128) NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB;
```

```sql
DROP TABLE IF EXISTS seed_digit;
CREATE TABLE seed_digit (d TINYINT UNSIGNED PRIMARY KEY);
INSERT INTO seed_digit VALUES (0),(1),(2),(3),(4),(5),(6),(7),(8),(9);

INSERT INTO report_order (id, tenant_id, status, created_at)
SELECT n,
       MOD(n, 1000) + 1,
       MOD(n, 4),
       TIMESTAMPADD(SECOND, n, '2026-01-01 00:00:00')
FROM (
  SELECT 1 + d0.d + 10*d1.d + 100*d2.d + 1000*d3.d
           + 10000*d4.d + 100000*d5.d AS n
  FROM seed_digit AS d0
  CROSS JOIN seed_digit AS d1
  CROSS JOIN seed_digit AS d2
  CROSS JOIN seed_digit AS d3
  CROSS JOIN seed_digit AS d4
  CROSS JOIN seed_digit AS d5
  ORDER BY n
  LIMIT 100000
) AS seq;

INSERT INTO report_item (id, order_id, qty, unit_price)
SELECT o.id * 10 + d.d,
       o.id,
       d.d,
       (MOD(o.id * d.d, 100000) + 1) / 100
FROM report_order AS o
JOIN seed_digit AS d ON d.d IN (1,2,3);

DROP TABLE seed_digit;

INSERT INTO oltp_probe (id, counter, payload)
SELECT id, 0, CONCAT('probe-', id)
FROM report_order
WHERE id <= 10000;
```

先验收来源，再做 performance：

```sql
SELECT COUNT(*) AS orders,
       DATE_FORMAT(MIN(created_at),'%Y-%m-%d %H:%i:%s.%f') AS min_created_at,
       MIN(id) AS min_id,
       DATE_FORMAT(MAX(created_at),'%Y-%m-%d %H:%i:%s.%f') AS max_created_at,
       MAX(id) AS max_id
FROM report_order;

SELECT COUNT(*) AS items, COUNT(DISTINCT order_id) AS item_orders
FROM report_item;

SELECT MIN(c) AS min_items, MAX(c) AS max_items
FROM (
  SELECT order_id, COUNT(*) AS c
  FROM report_item
  GROUP BY order_id
) AS x;

SELECT COUNT(*) AS probes FROM oltp_probe;

SELECT COUNT(*) AS report_rows,
       SUM(total_amount) AS total_amount_fingerprint,
       SUM(item_count) AS item_count_fingerprint
FROM (
  SELECT o.created_at, o.id,
         SUM(i.qty * i.unit_price) AS total_amount,
         COUNT(*) AS item_count
  FROM report_order AS o
  JOIN report_item AS i ON i.order_id = o.id
  GROUP BY o.created_at, o.id
) AS report;
```

导出顺序唯一固定为 `(created_at ASC,id ASC)`。job 建立时执行 `ORDER BY created_at DESC,id DESC LIMIT 1` 捕获最大 tuple，之后每批只执行下面的 query shape：

```sql
SELECT o.created_at, o.id, o.tenant_id, o.status,
       SUM(i.qty * i.unit_price) AS total_amount,
       COUNT(*) AS item_count
FROM report_order AS o
JOIN report_item AS i ON i.order_id = o.id
WHERE (o.created_at, o.id) > (?, ?)
  AND (o.created_at, o.id) <= (?, ?)
GROUP BY o.created_at, o.id, o.tenant_id, o.status
ORDER BY o.created_at, o.id
LIMIT ?;
```

JOIN algorithm、filesort、`Using temporary` 的完整机制由 [ch08](../08-sql-tuning/README.md) 负责；从深 offset 转成 `(created_at,id) > last_cursor` 的机制由 [ch08 scenario 03](../08-sql-tuning/scenarios/03-deep-pagination-deferred-join.md) 负责。这里不重复讲一次。

这条 JOIN／GROUP BY／ORDER BY 是否产生 internal temporary table 或 filesort 必须由 `EXPLAIN ANALYZE`、optimizer trace 与前后 status delta 判断。MySQL 官方列出的 temporary table 触发条件包含 aggregation、某些 `ORDER BY`／`GROUP BY` 组合；`Created_tmp_tables` 与 `Created_tmp_disk_tables` 是累计 counter，必须比较观察窗口前后差值。[MySQL 8.0 internal temporary tables](https://dev.mysql.com/doc/refman/8.0/en/internal-temporary-tables.html)

## Job state 与 artifact 不变式

runner 的全部 runtime state 只能位于一个通过 prefix guard 的 job directory：

```text
job-<run-id>/
├── state.json
├── parts/
│   ├── part-000001.tsv
│   └── part-000002.tsv
├── artifact.tsv
└── result.json
```

`state.json` 的字段固定：

```json
{
  "job_id": "run-id",
  "mode": "chunked",
  "connection_id": 123,
  "high_created_at": "2026-01-02 03:46:40.000000",
  "high_id": 100000,
  "expected_rows": 100000,
  "last_created_at": "1970-01-01 00:00:00.000000",
  "last_id": 0,
  "next_part": 1,
  "rows_written": 0,
  "active_seconds": 0.0,
  "artifact_rows": null,
  "artifact_sha256": null,
  "parts": [],
  "status": "RUNNING",
  "abort_reason": null
}
```

路径 `job-<run-id>` 与 state 的 `job_id=<run-id>` 是同一 identity：例如 `job-trial-01` 必须写 `"job_id": "trial-01"`；abort 使用 `abort-trial-01.json`，OLTP `trial_id=trial-01` 使用 `metrics-trial-01.json`。runner、controller 与 Task 10 不得把路径前缀混进 ID，也不得让不同 runtime root 的控制文件交叉绑定。

Artifact 不变式：

1. 每个 part 先写为 `.tmp`，`flush`／`fsync` 后用 `os.replace()` 原子 rename；checkpoint 只在 rename 后推进。
2. 每次 checkpoint append 一个 ordered manifest entry：part number、name、rows、SHA-256、first cursor、last cursor。
3. resume 会重验所有 checkpointed part 的 bytes、rows、hash、cursor order 与 contiguity。只允许 deterministic `next_part` 是 rename-before-checkpoint 的 pending file；它会从 old cursor 重取并覆写。
4. missing、same-line-count corruption、stale extra、orphan、gap 都必须在 publish 前失败。
5. final publish 只依 ordered manifest 串接；重验每个 part，要求 `rows_written=expected_rows` 且 `last_cursor=high`，再写入／fsync／replace `artifact.tsv`。
6. `SUCCEEDED` fast path 必须让 state、result、artifact 的 job／mode／rows／SHA／cursors 一致；chunked 还要重验 manifest，其 exact concatenated bytes／SHA 必须等于 artifact，不能靠 coupled artifact/result rewrite 绕过。
7. `ABORTED` 保留 state 与 parts；`active_seconds` 跨 invocation 累加，所以 `rows_per_active_second` 不会拿累计 rows 除以只属于最后一次 resume 的时间。
8. reader 绝不把 `.tmp` 或单个 part 当完整报表。

这些 manifest checks 证明的是 **内部 artifact construction integrity**。Task 10 仍要独立执行 buffered／chunked／resumed exact SHA equality、distinct key 与业务 aggregate fingerprint 的 external cross-mode/business audit。文件内容在 rename 前有 `fsync`，但 code 没有对 parent directory 做 `fsync`，所以不宣称 host power-loss 后 directory entry 一定 durable。

## Canonical `export_runner.py`

CLI interface 固定：

```text
--mode buffered|chunked|oltp
--runtime-root /private/tmp/mysql-senior-scenarios.<suffix>
--job-dir /private/tmp/mysql-senior-scenarios.<suffix>/job-<run-id>
--abort-file /private/tmp/mysql-senior-scenarios.<suffix>/abort-<run-id>.json
--metrics-file /private/tmp/mysql-senior-scenarios.<suffix>/metrics-<run-id>.json
--trial-id <run-id>
--batch-size 1000
--sleep-ms 20
--max-batches 0
--min-free-bytes 5419909120
--duration-seconds 60
--threads 4
--host 127.0.0.1 --port 3306 --user root --password-env MYSQL_PASSWORD
```

Task 10 从下方 canonical Python fence 原样物化到 `$MYSQL_SCENARIO_RUN_DIR/export_runner.py`。`--runtime-root`、job、abort、metrics 和 controller evidence 必须 resolve 到同一个 immediate `/private/tmp/mysql-senior-scenarios.<nonempty-suffix>` runtime directory；job 是 immediate nonempty `job-<run-id>` child，控制文件名必须与该 ID 精确对应。export data values 全部 parameterized；buffered 与 chunked 使用相同字段次序与 canonical TSV formatting；密码只来自 `--password-env MYSQL_PASSWORD`。

Connector implementation 也是实验契约，不是隐形 default。runner／controller 每次 connection 都显式传 `use_pure=True`；四个 OLTP worker 各自建立、验证并关闭独立 connection，绝不共享。evidence 持久化 Python/platform、Connector version、`threadsafety`、`HAVE_CEXT`、requested pure mode 与 actual connection class；actual class 以 documented `mysql.connector.connection.MySQLConnection` exact type check 验证，不以 class-name substring 猜测。任何其他 actual class 都在 work 前 fail closed。Connector/Python 9.5+ 支援 Python 3.13；pure Python 与 C Extension 是不同 implementation；MySQL 8 起若 C Extension 可用，`use_pure` default 为 `False`，但可显式切换为 `True`；Connector/Python `threadsafety=1`。[Connector implementations and versions](https://dev.mysql.com/doc/connector-python/en/connector-python-versions.html) [Selecting `use_pure`](https://dev.mysql.com/doc/connector-python/en/connector-python-cext-development.html) [`threadsafety`](https://dev.mysql.com/doc/connectors/en/connector-python-api-mysql-connector-threadsafety.html) [`MySQLConnection` class](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlconnection.html)

```python
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import platform
import queue
import random
import resource
import shutil
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import mysql.connector
from mysql.connector.connection import MySQLConnection


EPOCH = "1970-01-01 00:00:00.000000"
RUNTIME_PREFIX = "mysql-senior-scenarios."
# Return to heartbeat/window publication after at most this many queued events
# or this much monotonic wall time. These are liveness bounds, not throughput
# targets, and do not relax the controller's 2.5-second heartbeat gate.
OLTP_DRAIN_MAX_EVENTS = 256
OLTP_DRAIN_MAX_SECONDS = 0.010
EXPORT_SQL = """
SELECT o.created_at, o.id, o.tenant_id, o.status,
       SUM(i.qty * i.unit_price) AS total_amount,
       COUNT(*) AS item_count
FROM report_order AS o
JOIN report_item AS i ON i.order_id = o.id
WHERE (o.created_at, o.id) > (%s, %s)
  AND (o.created_at, o.id) <= (%s, %s)
GROUP BY o.created_at, o.id, o.tenant_id, o.status
ORDER BY o.created_at, o.id
LIMIT %s
"""
BUFFERED_SQL = """
SELECT o.created_at, o.id, o.tenant_id, o.status,
       SUM(i.qty * i.unit_price) AS total_amount,
       COUNT(*) AS item_count
FROM report_order AS o
JOIN report_item AS i ON i.order_id = o.id
WHERE (o.created_at, o.id) > (%s, %s)
  AND (o.created_at, o.id) <= (%s, %s)
GROUP BY o.created_at, o.id, o.tenant_id, o.status
ORDER BY o.created_at, o.id
"""


def connector_environment() -> dict:
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "connector_version": mysql.connector.__version__,
        "threadsafety": int(mysql.connector.threadsafety),
        "have_cext": bool(mysql.connector.HAVE_CEXT),
        "requested_use_pure": True,
    }


class ConnectorContractError(RuntimeError):
    def __init__(self, message: str, connector_evidence: dict):
        super().__init__(message)
        self.connector_evidence = connector_evidence


def observe_connector(connection=None) -> dict:
    return {
        **connector_environment(),
        "actual_connection_class": (
            None
            if connection is None
            else f"{type(connection).__module__}.{type(connection).__qualname__}"
        ),
        "actual_pure": (
            None if connection is None else type(connection) is MySQLConnection
        ),
    }


def require_pure_connection(connection) -> dict:
    observed = observe_connector(connection)
    if type(connection) is not MySQLConnection:
        raise ConnectorContractError(
            "connector did not return the required pure Python MySQLConnection",
            observed,
        )
    return observed


def connector_failure_evidence(exc: Exception, fallback: dict) -> dict:
    observed = getattr(exc, "connector_evidence", fallback)
    return observed if isinstance(observed, dict) else fallback


def strict_connection_id(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RuntimeError("connection_id must be a positive integer")
    return value


class StructuredArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def timestamp_text(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S.%f")
    return str(value)


def cursor_value(value) -> tuple[str, int]:
    return str(value[0]), int(value[1])


def canonical_line(row: tuple) -> bytes:
    created_at, order_id, tenant_id, status, total_amount, item_count = row
    amount = format(total_amount, "f") if isinstance(total_amount, Decimal) else str(total_amount)
    text = "\t".join(
        (
            timestamp_text(created_at),
            str(order_id),
            str(tenant_id),
            str(status),
            amount,
            str(item_count),
        )
    )
    return (text + "\n").encode("utf-8")


def capture_high_watermark(cursor) -> tuple[str, int]:
    cursor.execute(
        "SELECT DATE_FORMAT(created_at,'%Y-%m-%d %H:%i:%s.%f'), id "
        "FROM report_order ORDER BY created_at DESC,id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("report_order is empty")
    return str(row[0]), int(row[1])


def count_boundary_rows(cursor, high: tuple[str, int]) -> int:
    cursor.execute(
        "SELECT COUNT(*) FROM report_order "
        "WHERE (created_at,id) > (%s,%s) AND (created_at,id) <= (%s,%s)",
        (EPOCH, 0, *high),
    )
    return int(cursor.fetchone()[0])


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path.name} is not a JSON object")
    return value


def fetch_batch(
    cursor,
    low: tuple[str, int],
    high: tuple[str, int],
    limit: int,
) -> list[tuple]:
    cursor.execute(EXPORT_SQL, (*low, *high, limit))
    return list(cursor.fetchall())


def write_part(path: Path, rows: list[tuple]) -> tuple[int, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    digest = hashlib.sha256()
    count = 0
    with temporary.open("wb") as handle:
        for row in rows:
            encoded = canonical_line(row)
            handle.write(encoded)
            digest.update(encoded)
            count += 1
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return count, digest.hexdigest()


def part_file_metadata(path: Path) -> dict:
    digest = hashlib.sha256()
    rows = 0
    first_cursor = None
    last_cursor = None
    with path.open("rb") as handle:
        for line in handle:
            if not line.endswith(b"\n"):
                raise RuntimeError(f"{path.name} has a noncanonical final line")
            fields = line[:-1].split(b"\t")
            if len(fields) != 6:
                raise RuntimeError(f"{path.name} has a noncanonical column count")
            current = (fields[0].decode("utf-8"), int(fields[1]))
            if last_cursor is not None and current <= last_cursor:
                raise RuntimeError(f"{path.name} cursor order is not strictly increasing")
            first_cursor = first_cursor or current
            last_cursor = current
            digest.update(line)
            rows += 1
    if rows == 0:
        raise RuntimeError(f"{path.name} is empty")
    return {
        "rows": rows,
        "sha256": digest.hexdigest(),
        "first_cursor": list(first_cursor),
        "last_cursor": list(last_cursor),
    }


def file_rows_sha(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    rows = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            rows += chunk.count(b"\n")
    return rows, digest.hexdigest()


def max_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def runtime_root(path: Path) -> Path:
    resolved = path.resolve()
    private_tmp = Path("/private/tmp").resolve()
    if (
        resolved.parent != private_tmp
        or not resolved.name.startswith(RUNTIME_PREFIX)
        or resolved.name == RUNTIME_PREFIX
    ):
        raise ValueError("runtime directory is outside the allowed nonempty prefix")
    return resolved


def validated_job_dir(path: Path) -> Path:
    resolved = path.resolve()
    root = runtime_root(resolved.parent)
    if resolved.parent != root or not resolved.name.startswith("job-") or resolved.name == "job-":
        raise ValueError("job directory must be an immediate job-<run-id> child")
    return resolved


def job_id_from_dir(job_dir: Path) -> str:
    name = validated_job_dir(job_dir).name
    return name[len("job-") :]


def validated_runtime_file(
    path: Path,
    prefix: str,
    suffix: str,
    expected_root: Path,
) -> Path:
    resolved = path.resolve()
    root = runtime_root(expected_root)
    if (
        not suffix
        or resolved.parent != root
        or resolved.name != f"{prefix}{suffix}.json"
    ):
        raise ValueError(f"runtime file must equal {prefix}<nonempty-id>.json")
    return resolved


def validate_manifest(job_dir: Path, state: dict, allow_pending: bool) -> list[dict]:
    parts = state.get("parts")
    if not isinstance(parts, list):
        raise RuntimeError("state parts is not a list")
    expected_names = set()
    total_rows = 0
    previous = (EPOCH, 0)
    validated = []
    for expected_number, entry in enumerate(parts, 1):
        expected_name = f"part-{expected_number:06d}.tsv"
        if (
            int(entry.get("number", -1)) != expected_number
            or entry.get("name") != expected_name
        ):
            raise RuntimeError("part manifest has a gap or name mismatch")
        path = job_dir / "parts" / expected_name
        if not path.is_file():
            raise RuntimeError(f"checkpointed part missing: {expected_name}")
        observed = part_file_metadata(path)
        for key in ("rows", "sha256", "first_cursor", "last_cursor"):
            if observed[key] != entry.get(key):
                raise RuntimeError(f"checkpointed part mismatch: {expected_name}:{key}")
        first = cursor_value(entry["first_cursor"])
        last = cursor_value(entry["last_cursor"])
        if first <= previous or last < first:
            raise RuntimeError("part manifest cursor order is invalid")
        previous = last
        total_rows += int(entry["rows"])
        expected_names.add(expected_name)
        validated.append(entry)

    next_part = int(state.get("next_part", -1))
    if next_part != len(parts) + 1:
        raise RuntimeError("next_part does not follow the manifest")
    actual_names = {
        path.name for path in (job_dir / "parts").glob("part-*.tsv")
    } if (job_dir / "parts").exists() else set()
    allowed_names = set(expected_names)
    pending_name = f"part-{next_part:06d}.tsv"
    if allow_pending:
        allowed_names.add(pending_name)
    if expected_names - actual_names:
        raise RuntimeError("one or more checkpointed parts are missing")
    if actual_names - allowed_names:
        raise RuntimeError("stale, orphan, or gapped part detected")
    if total_rows != int(state.get("rows_written", -1)):
        raise RuntimeError("manifest rows do not match rows_written")
    expected_rows = int(state.get("expected_rows", -1))
    if expected_rows < total_rows:
        raise RuntimeError("rows_written exceeds expected boundary rows")
    expected_last = previous if parts else (EPOCH, 0)
    if expected_last != (
        str(state.get("last_created_at")),
        int(state.get("last_id", -1)),
    ):
        raise RuntimeError("state last cursor does not match manifest")
    return validated


def manifest_artifact_signature(job_dir: Path, state: dict) -> tuple[int, str]:
    parts = validate_manifest(job_dir, state, allow_pending=False)
    digest = hashlib.sha256()
    rows = 0
    for entry in parts:
        with (job_dir / "parts" / entry["name"]).open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
                rows += chunk.count(b"\n")
    return rows, digest.hexdigest()


def publish(job_dir: Path, state: dict) -> tuple[int, str]:
    parts = validate_manifest(job_dir, state, allow_pending=False)
    expected_rows = int(state["expected_rows"])
    if int(state["rows_written"]) != expected_rows:
        raise RuntimeError("checkpoint rows do not equal expected boundary rows")
    if (
        str(state["last_created_at"]),
        int(state["last_id"]),
    ) != (
        str(state["high_created_at"]),
        int(state["high_id"]),
    ):
        raise RuntimeError("last cursor does not equal the high watermark")

    artifact = job_dir / "artifact.tsv"
    temporary = job_dir / "artifact.tsv.tmp"
    artifact_digest = hashlib.sha256()
    artifact_rows = 0
    try:
        with temporary.open("wb") as output:
            for entry in parts:
                part_digest = hashlib.sha256()
                part_rows = 0
                with (job_dir / "parts" / entry["name"]).open("rb") as source:
                    for line in source:
                        output.write(line)
                        artifact_digest.update(line)
                        part_digest.update(line)
                        part_rows += line.count(b"\n")
                if (
                    part_rows != int(entry["rows"])
                    or part_digest.hexdigest() != entry["sha256"]
                ):
                    raise RuntimeError(f"part changed during publish: {entry['name']}")
                artifact_rows += part_rows
            output.flush()
            os.fsync(output.fileno())
        if artifact_rows != expected_rows:
            raise RuntimeError("artifact rows do not equal expected boundary rows")
        os.replace(temporary, artifact)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return artifact_rows, artifact_digest.hexdigest()


def validate_success(job_dir: Path, state: dict, result: dict) -> dict:
    artifact = job_dir / "artifact.tsv"
    if state.get("status") != "SUCCEEDED" or result.get("status") != "SUCCEEDED":
        raise RuntimeError("success files do not contain SUCCEEDED")
    if not artifact.is_file():
        raise RuntimeError("SUCCEEDED artifact is missing")
    rows, sha256 = file_rows_sha(artifact)
    expected_rows = int(state["expected_rows"])
    state_high = (str(state["high_created_at"]), int(state["high_id"]))
    state_last = (str(state["last_created_at"]), int(state["last_id"]))
    state_mode = str(state.get("mode"))
    if (
        rows != expected_rows
        or int(state["rows_written"]) != expected_rows
        or int(result.get("rows", -1)) != expected_rows
        or result.get("sha256") != sha256
        or int(state.get("artifact_rows", -1)) != expected_rows
        or state.get("artifact_sha256") != sha256
        or result.get("mode") != state_mode
        or result.get("job_id") != state.get("job_id")
        or result.get("connector_contract") != state.get("connector_contract")
        or state_last != state_high
        or cursor_value(result.get("high_cursor", ("", -1))) != state_high
        or cursor_value(result.get("last_cursor", ("", -1))) != state_last
    ):
        raise RuntimeError("SUCCEEDED artifact does not match state/result")
    if state_mode == "chunked":
        manifest_rows, manifest_sha256 = manifest_artifact_signature(job_dir, state)
        if manifest_rows != rows or manifest_sha256 != sha256:
            raise RuntimeError("SUCCEEDED artifact does not match checkpoint manifest")
    elif state_mode != "buffered":
        raise RuntimeError("SUCCEEDED state mode is invalid")
    return result


def stop_reason(abort_file: Path | None, job_dir: Path, min_free_bytes: int) -> str | None:
    if abort_file is not None and abort_file.exists():
        try:
            return str(read_json(abort_file).get("reason") or "external gate")
        except Exception:
            return "unreadable external abort signal"
    if min_free_bytes and shutil.disk_usage(job_dir.parent).free < min_free_bytes:
        return f"free disk below {min_free_bytes}"
    return None


def aborted_result(state: dict, reason: str, active_seconds: float) -> dict:
    state["status"] = "ABORTED"
    state["abort_reason"] = reason
    state["active_seconds"] = active_seconds
    return {
        "status": "ABORTED",
        "mode": "chunked",
        "job_id": state["job_id"],
        "reason": reason,
        "rows": int(state["rows_written"]),
        "active_seconds": active_seconds,
        "rows_per_active_second": (
            int(state["rows_written"]) / active_seconds if active_seconds else 0.0
        ),
        "max_rss_bytes": max_rss_bytes(),
        "high_cursor": [state["high_created_at"], state["high_id"]],
        "last_cursor": [state["last_created_at"], state["last_id"]],
        "parts": len(state["parts"]),
        "connector_contract": state["connector_contract"],
    }


def run_chunked(
    connection,
    connector_contract: dict,
    job_dir: Path,
    batch_size: int,
    sleep_ms: int,
    max_batches: int,
    abort_file: Path | None,
    min_free_bytes: int,
) -> dict:
    state_path = job_dir / "state.json"
    result_path = job_dir / "result.json"
    cursor = connection.cursor()
    if state_path.exists():
        state = read_json(state_path)
        if state.get("job_id") != job_id_from_dir(job_dir):
            raise RuntimeError("state job_id does not match job directory")
        if state.get("connector_contract") != connector_contract:
            raise RuntimeError("resume connector contract changed")
        if state.get("status") == "SUCCEEDED":
            if not result_path.is_file():
                raise RuntimeError("SUCCEEDED result.json is missing")
            result = validate_success(job_dir, state, read_json(result_path))
            cursor.close()
            return result
        if state.get("status") not in ("RUNNING", "ABORTED"):
            raise RuntimeError("state status is not resumable")
        validate_manifest(job_dir, state, allow_pending=True)
        state["status"] = "RUNNING"
        state["abort_reason"] = None
        state["connection_id"] = strict_connection_id(connection.connection_id)
    else:
        high_created_at, high_id = capture_high_watermark(cursor)
        expected_rows = count_boundary_rows(cursor, (high_created_at, high_id))
        state = {
            "job_id": job_id_from_dir(job_dir),
            "mode": "chunked",
            "connection_id": strict_connection_id(connection.connection_id),
            "connector_contract": connector_contract,
            "high_created_at": high_created_at,
            "high_id": high_id,
            "expected_rows": expected_rows,
            "last_created_at": EPOCH,
            "last_id": 0,
            "next_part": 1,
            "rows_written": 0,
            "active_seconds": 0.0,
            "artifact_rows": None,
            "artifact_sha256": None,
            "parts": [],
            "status": "RUNNING",
            "abort_reason": None,
        }
    atomic_json(state_path, state)
    started = time.perf_counter()
    base_active = float(state["active_seconds"])
    batches_this_run = 0
    while True:
        reason = stop_reason(abort_file, job_dir, min_free_bytes)
        if reason is not None:
            result = aborted_result(
                state, reason, base_active + (time.perf_counter() - started)
            )
            atomic_json(state_path, state)
            cursor.close()
            return result

        rows = fetch_batch(
            cursor,
            (state["last_created_at"], int(state["last_id"])),
            (state["high_created_at"], int(state["high_id"])),
            batch_size,
        )
        if not rows:
            state["active_seconds"] = base_active + (time.perf_counter() - started)
            artifact_rows, artifact_sha256 = publish(job_dir, state)
            result = {
                "status": "SUCCEEDED",
                "mode": "chunked",
                "job_id": state["job_id"],
                "rows": artifact_rows,
                "sha256": artifact_sha256,
                "active_seconds": state["active_seconds"],
                "rows_per_active_second": (
                    artifact_rows / state["active_seconds"]
                    if state["active_seconds"] else 0.0
                ),
                "max_rss_bytes": max_rss_bytes(),
                "high_cursor": [state["high_created_at"], state["high_id"]],
                "last_cursor": [state["last_created_at"], state["last_id"]],
                "parts": len(state["parts"]),
                "connector_contract": connector_contract,
            }
            atomic_json(result_path, result)
            state["artifact_rows"] = artifact_rows
            state["artifact_sha256"] = artifact_sha256
            state["status"] = "SUCCEEDED"
            atomic_json(state_path, state)
            cursor.close()
            return validate_success(job_dir, state, result)

        part_number = int(state["next_part"])
        part_name = f"part-{part_number:06d}.tsv"
        part_path = job_dir / "parts" / part_name
        part_rows, part_sha256 = write_part(part_path, rows)
        entry = {
            "number": part_number,
            "name": part_name,
            "rows": part_rows,
            "sha256": part_sha256,
            "first_cursor": [timestamp_text(rows[0][0]), int(rows[0][1])],
            "last_cursor": [timestamp_text(rows[-1][0]), int(rows[-1][1])],
        }
        state["parts"].append(entry)
        state["last_created_at"], state["last_id"] = cursor_value(entry["last_cursor"])
        state["next_part"] = part_number + 1
        state["rows_written"] = int(state["rows_written"]) + part_rows
        state["active_seconds"] = base_active + (time.perf_counter() - started)
        atomic_json(state_path, state)
        batches_this_run += 1
        if max_batches and batches_this_run >= max_batches:
            result = aborted_result(state, "max_batches", state["active_seconds"])
            atomic_json(state_path, state)
            cursor.close()
            return result
        if sleep_ms:
            time.sleep(sleep_ms / 1000)


def run_buffered(connection, connector_contract: dict, job_dir: Path) -> dict:
    state_path = job_dir / "state.json"
    result_path = job_dir / "result.json"
    if job_dir.exists():
        if state_path.is_file() and result_path.is_file():
            state = read_json(state_path)
            if state.get("job_id") != job_id_from_dir(job_dir):
                raise RuntimeError("state job_id does not match job directory")
            if state.get("connector_contract") != connector_contract:
                raise RuntimeError("buffered connector contract changed")
            return validate_success(job_dir, state, read_json(result_path))
        raise RuntimeError("buffered mode requires a fresh job directory")
    job_dir.mkdir(parents=True)
    cursor = connection.cursor(buffered=True)
    high = capture_high_watermark(cursor)
    expected_rows = count_boundary_rows(cursor, high)
    state = {
        "job_id": job_id_from_dir(job_dir),
        "mode": "buffered",
        "connection_id": strict_connection_id(connection.connection_id),
        "connector_contract": connector_contract,
        "high_created_at": high[0],
        "high_id": high[1],
        "expected_rows": expected_rows,
        "last_created_at": EPOCH,
        "last_id": 0,
        "next_part": 1,
        "rows_written": 0,
        "active_seconds": 0.0,
        "artifact_rows": None,
        "artifact_sha256": None,
        "parts": [],
        "status": "RUNNING",
        "abort_reason": None,
    }
    atomic_json(state_path, state)
    started = time.perf_counter()
    cursor.execute(BUFFERED_SQL, (EPOCH, 0, *high))
    rows = list(cursor.fetchall())
    artifact_rows, artifact_sha256 = write_part(job_dir / "artifact.tsv", rows)
    if artifact_rows != expected_rows:
        raise RuntimeError("buffered rows do not equal expected boundary rows")
    last_cursor = [timestamp_text(rows[-1][0]), int(rows[-1][1])]
    if cursor_value(last_cursor) != cursor_value(high):
        raise RuntimeError("buffered last cursor does not equal high watermark")
    cursor.close()
    active_seconds = time.perf_counter() - started
    result = {
        "status": "SUCCEEDED",
        "mode": "buffered",
        "job_id": state["job_id"],
        "rows": artifact_rows,
        "sha256": artifact_sha256,
        "active_seconds": active_seconds,
        "rows_per_active_second": (
            artifact_rows / active_seconds if active_seconds else 0.0
        ),
        "max_rss_bytes": max_rss_bytes(),
        "high_cursor": [high[0], high[1]],
        "last_cursor": last_cursor,
        "connector_contract": connector_contract,
    }
    atomic_json(result_path, result)
    state.update(
        {
            "last_created_at": last_cursor[0],
            "last_id": last_cursor[1],
            "rows_written": artifact_rows,
            "active_seconds": active_seconds,
            "artifact_rows": artifact_rows,
            "artifact_sha256": artifact_sha256,
            "status": "SUCCEEDED",
        }
    )
    atomic_json(state_path, state)
    return validate_success(job_dir, state, result)


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def drain_oltp_event_slice(
    events,
    *,
    max_events: int,
    max_seconds: float,
    monotonic=time.perf_counter,
) -> dict:
    if max_events < 1 or max_seconds <= 0:
        raise ValueError("OLTP drain bounds must be positive")
    started = monotonic()
    drained = []
    for _index in range(max_events):
        if monotonic() - started >= max_seconds:
            return {
                "events": drained,
                "limit_hit": True,
                "limit_reason": "time",
            }
        try:
            drained.append(events.get_nowait())
        except queue.Empty:
            return {
                "events": drained,
                "limit_hit": False,
                "limit_reason": None,
            }
    return {
        "events": drained,
        "limit_hit": True,
        "limit_reason": "count",
    }


def close_oltp_resources(cursor, connection) -> dict:
    failures = []
    if cursor is not None:
        try:
            cursor.close()
        except Exception as exc:
            failures.append(f"cursor close failed: {type(exc).__name__}: {exc}")
    try:
        connection.close()
    except Exception as exc:
        failures.append(f"connection close failed: {type(exc).__name__}: {exc}")
    try:
        is_connected = getattr(connection, "is_connected")
        if not callable(is_connected) or is_connected() is not False:
            raise RuntimeError("is_connected() did not return False")
    except Exception as exc:
        failures.append(
            f"connection closure could not be verified: {type(exc).__name__}: {exc}"
        )
    if failures:
        raise RuntimeError("; ".join(failures))
    return {"closed": True, "close_proof": "is_connected_false"}


def oltp_worker(
    config: dict,
    deadline: float,
    seed: int,
    events: queue.SimpleQueue,
) -> dict:
    connection = mysql.connector.connect(**config)
    cursor = None
    identity = None
    connection_id = None
    work_error = None
    try:
        identity = require_pure_connection(connection)
        connection_id = strict_connection_id(connection.connection_id)
        connection.autocommit = True
        cursor = connection.cursor()
        randomizer = random.Random(seed)
        while time.perf_counter() < deadline:
            probe_id = randomizer.randint(1, 10000)
            started = time.perf_counter_ns()
            try:
                cursor.execute("SELECT counter FROM oltp_probe WHERE id=%s", (probe_id,))
                cursor.fetchone()
                cursor.execute(
                    "UPDATE oltp_probe SET counter=counter+1 WHERE id=%s",
                    (probe_id,),
                )
                events.put(((time.perf_counter_ns() - started) / 1_000_000, False))
            except Exception:
                events.put((0.0, True))
    except BaseException as exc:
        work_error = exc
    close_error = None
    try:
        close_evidence = close_oltp_resources(cursor, connection)
    except BaseException as exc:
        close_error = exc
    if work_error is not None:
        if identity is not None and not hasattr(work_error, "connector_evidence"):
            work_error.connector_evidence = identity
        if close_error is not None:
            work_error.add_note(f"worker cleanup also failed: {close_error}")
        raise work_error
    if close_error is not None:
        if identity is not None:
            close_error.connector_evidence = identity
        raise close_error
    return {
        **identity,
        "worker": seed,
        "connection_id": connection_id,
        **close_evidence,
    }


def run_oltp(
    config: dict,
    duration: int,
    threads: int,
    metrics_file: Path | None,
    window_seconds: float,
    trial_id: str,
    diagnostics: dict | None = None,
) -> dict:
    if diagnostics is None:
        diagnostics = {
            "drain_limit_hits": 0,
            "max_heartbeat_lateness_ms": 0.0,
        }
    started = time.perf_counter()
    deadline = started + duration
    next_window = started + window_seconds
    events: queue.SimpleQueue = queue.SimpleQueue()
    all_latencies = []
    all_errors = 0
    window_latencies = []
    window_errors = 0
    sequence = 0
    diagnostics["drain_limit_hits"] = 0
    diagnostics["max_heartbeat_lateness_ms"] = 0.0
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as pool:
        futures = [
            pool.submit(oltp_worker, config, deadline, seed, events)
            for seed in range(1, threads + 1)
        ]
        while True:
            now = time.perf_counter()
            if now >= next_window and (window_latencies or window_errors):
                diagnostics["max_heartbeat_lateness_ms"] = max(
                    diagnostics["max_heartbeat_lateness_ms"],
                    max(0.0, (now - next_window) * 1000.0),
                )
                sequence += 1
                if metrics_file is not None:
                    atomic_json(
                        metrics_file,
                        {
                            "status": "RUNNING",
                            "trial_id": trial_id,
                            "heartbeat_at_epoch": time.time(),
                            "window_seq": sequence,
                            "window_operations": len(window_latencies),
                            "window_errors": window_errors,
                            "window_p95_ms": percentile(window_latencies, 0.95),
                            "operations": len(all_latencies),
                            "errors": all_errors,
                            "active_elapsed_seconds": now - started,
                            "drain_limit_hits": diagnostics["drain_limit_hits"],
                            "max_heartbeat_lateness_ms": diagnostics[
                                "max_heartbeat_lateness_ms"
                            ],
                        },
                    )
                window_latencies = []
                window_errors = 0
                next_window = now + window_seconds

            drained = drain_oltp_event_slice(
                events,
                max_events=OLTP_DRAIN_MAX_EVENTS,
                max_seconds=OLTP_DRAIN_MAX_SECONDS,
            )
            for latency, is_error in drained["events"]:
                if is_error:
                    all_errors += 1
                    window_errors += 1
                else:
                    all_latencies.append(latency)
                    window_latencies.append(latency)
            if drained["limit_hit"]:
                diagnostics["drain_limit_hits"] += 1

            if (
                all(future.done() for future in futures)
                and not drained["limit_hit"]
                and events.empty()
            ):
                break
            if not drained["limit_hit"]:
                time.sleep(0.02)
        worker_connections = [future.result() for future in futures]
    if (
        len(worker_connections) != threads
        or len({item["connection_id"] for item in worker_connections}) != threads
        or any(
            isinstance(item.get("worker"), bool)
            or not isinstance(item.get("worker"), int)
            or item.get("worker") != expected_worker
            or isinstance(item.get("connection_id"), bool)
            or not isinstance(item.get("connection_id"), int)
            or item.get("actual_pure") is not True
            or item.get("closed") is not True
            or item.get("close_proof") != "is_connected_false"
            for expected_worker, item in enumerate(worker_connections, 1)
        )
    ):
        raise RuntimeError("OLTP workers did not own distinct closed pure connections")
    connector_contract = {
        key: value
        for key, value in worker_connections[0].items()
        if key not in ("worker", "connection_id", "closed", "close_proof")
    }
    if any(
        {
            key: value
            for key, value in item.items()
            if key not in ("worker", "connection_id", "closed", "close_proof")
        }
        != connector_contract
        for item in worker_connections
    ):
        raise RuntimeError("OLTP worker connector contracts differ")
    result = {
        "status": (
            "SUCCEEDED"
            if all_errors == 0 and len(all_latencies) > 0
            else "FAILED"
        ),
        "mode": "oltp",
        "trial_id": trial_id,
        "operations": len(all_latencies),
        "errors": all_errors,
        "p50_ms": percentile(all_latencies, 0.50),
        "p95_ms": percentile(all_latencies, 0.95),
        "p99_ms": percentile(all_latencies, 0.99),
        "threads": threads,
        "drain_limit_hits": diagnostics["drain_limit_hits"],
        "max_heartbeat_lateness_ms": diagnostics[
            "max_heartbeat_lateness_ms"
        ],
        "connector_contract": connector_contract,
        "worker_connections": worker_connections,
    }
    if metrics_file is not None and (window_latencies or window_errors):
        atomic_json(
            metrics_file,
            {
                **result,
                "trial_id": trial_id,
                "heartbeat_at_epoch": time.time(),
                "window_seq": sequence + 1,
                "window_operations": len(window_latencies),
                "window_errors": window_errors,
                "window_p95_ms": percentile(window_latencies, 0.95),
                "active_elapsed_seconds": time.perf_counter() - started,
                "drain_limit_hits": diagnostics["drain_limit_hits"],
                "max_heartbeat_lateness_ms": diagnostics[
                    "max_heartbeat_lateness_ms"
                ],
            },
        )
    return result


def require_password(env_name: str) -> str:
    value = os.environ.get(env_name)
    if value is None:
        raise ValueError(f"password environment variable is not set: {env_name}")
    return value


def main() -> int:
    connector_evidence = observe_connector()
    failure_identity = {}
    oltp_diagnostics = {
        "drain_limit_hits": 0,
        "max_heartbeat_lateness_ms": 0.0,
    }
    try:
        parser = StructuredArgumentParser()
        parser.add_argument("--mode", choices=("buffered", "chunked", "oltp"), required=True)
        parser.add_argument("--runtime-root", type=Path, required=True)
        parser.add_argument("--job-dir", type=Path)
        parser.add_argument("--abort-file", type=Path)
        parser.add_argument("--metrics-file", type=Path)
        parser.add_argument("--trial-id")
        parser.add_argument("--batch-size", type=int, default=1000)
        parser.add_argument("--sleep-ms", type=int, default=20)
        parser.add_argument("--max-batches", type=int, default=0)
        parser.add_argument("--min-free-bytes", type=int, default=0)
        parser.add_argument("--duration-seconds", type=int, default=60)
        parser.add_argument("--window-seconds", type=float, default=1.0)
        parser.add_argument("--threads", type=int, default=4)
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=3306)
        parser.add_argument("--user", default="root")
        parser.add_argument("--password-env", default="MYSQL_PASSWORD")
        args = parser.parse_args()
        failure_identity = {"mode": args.mode}
        if args.mode == "oltp" and args.trial_id:
            failure_identity["trial_id"] = args.trial_id
        expected_root = runtime_root(args.runtime_root)

        if not 1 <= args.batch_size <= 5000:
            raise ValueError("--batch-size must be in 1..5000")
        if not 0 <= args.sleep_ms <= 1000:
            raise ValueError("--sleep-ms must be in 0..1000")
        if not 1 <= args.threads <= 16:
            raise ValueError("--threads must be in 1..16")
        if (
            args.duration_seconds < 1
            or args.max_batches < 0
            or args.min_free_bytes < 0
            or not 0.1 <= args.window_seconds <= 10.0
        ):
            raise ValueError("duration/max-batches/disk/window argument is invalid")

        config = {
            "host": args.host,
            "port": args.port,
            "user": args.user,
            "password": require_password(args.password_env),
            "database": "mysql_senior_scenarios",
            "use_pure": True,
        }
        connection = None
        if args.mode == "oltp":
            if (
                not args.trial_id
                or any(not (character.isalnum() or character in "-_") for character in args.trial_id)
            ):
                raise ValueError("OLTP mode requires a safe nonempty trial-id")
            metrics_file = (
                validated_runtime_file(
                    args.metrics_file,
                    "metrics-",
                    args.trial_id,
                    expected_root,
                )
                if args.metrics_file is not None else None
            )
            result = run_oltp(
                config,
                args.duration_seconds,
                args.threads,
                metrics_file,
                args.window_seconds,
                args.trial_id,
                diagnostics=oltp_diagnostics,
            )
        else:
            if args.job_dir is None:
                raise ValueError("--job-dir is required for export modes")
            job_dir = validated_job_dir(args.job_dir)
            if job_dir.parent != expected_root:
                raise ValueError("job directory must be under --runtime-root")
            job_id = job_id_from_dir(job_dir)
            abort_file = (
                validated_runtime_file(
                    args.abort_file,
                    "abort-",
                    job_id,
                    expected_root,
                )
                if args.abort_file is not None else None
            )
            try:
                connection = mysql.connector.connect(**config)
                connector_evidence = observe_connector(connection)
                connector_contract = require_pure_connection(connection)
                if args.mode == "buffered":
                    result = run_buffered(connection, connector_contract, job_dir)
                else:
                    job_dir.mkdir(parents=True, exist_ok=True)
                    result = run_chunked(
                        connection,
                        connector_contract,
                        job_dir,
                        args.batch_size,
                        args.sleep_ms,
                        args.max_batches,
                        abort_file,
                        args.min_free_bytes,
                    )
            finally:
                if connection is not None:
                    connection.close()
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] in ("SUCCEEDED", "ABORTED") else 2
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    **failure_identity,
                    **(
                        oltp_diagnostics
                        if failure_identity.get("mode") == "oltp"
                        else {}
                    ),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "connector_evidence": connector_failure_evidence(
                        exc, connector_evidence
                    ),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

### Runner 的事务、fetch 与恢复边界

这份 code 的行为要按事实解释，不能从“chunked”误推成“数据库端没有长 transaction”：

- Connector/Python connection 的 `autocommit` 默认是 `False`。在 MySQL 默认 RR 未被改变时，第一次 consistent read 建立 ReadView，同一 invocation 的后续 batch 复用它；这会保留并发 DML 需要的 undo，可能拉长 purge。Task 10 必须记录 `@@transaction_isolation`，而 production 不能靠未验证的 server default。[Connector/Python autocommit](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlconnection-autocommit.html)
- process resume 会建立新 connection，因此也是新 transaction／ReadView。high watermark 仍是 query upper bound；只有 S freeze／immutable insertion-monotone keys／materialized membership 才让它成为完整 membership boundary。否则 backdated insert 可进入新 ReadView，mutable row 的 value 也可能跨 resume 改变。
- `cursor(buffered=True)` 在 execute 后会把整个 result set 拉到 client 并 buffer，适合这里的 one-shot control，不适合把千万级 result 当默认生产路径。nonbuffered cursor 在调用 fetch method 时取 row，而且同一 connection 发下一条 statement 前必须消费完 result；本 runner 的 `fetch_batch()` 仍会 `fetchall()`，但每次只 materialize `batch_size <= 5000`。[Connector/Python buffered cursor](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlcursorbuffered.html)
- 不要把 Connector/Python 的 nonbuffered cursor 直接称为“不会物化的 MySQL server-side cursor”。MySQL 真正的 server-side cursor 会 materialize 到 internal temporary table，大 result 仍可能慢。[MySQL server-side cursor restrictions](https://dev.mysql.com/doc/mysql-reslimits-excerpt/8.0/en/cursor-restrictions.html)
- `max_rss_bytes` 是 process lifetime 的 peak RSS，不是某个 batch 的瞬时用量；三次 trial 必须各起新 process 才可比较。
- resumed success 的 `rows`、`active_seconds` 都跨 invocation 累积，`rows_per_active_second` 因而是累计 active throughput；planned-resume correctness run 仍不参与 steady-state 排名。
- `publish()` 只消费 checkpoint manifest。fresh performance trial 必须用 fresh job directory，resume 只复用该次 `ABORTED` job；orphan／stale／gap、missing 或 same-line-count corruption 会 fail closed，不会被 glob 偷渡进 artifact。
- 正常成功写入次序是 artifact → result → state。`SUCCEEDED` fast path 会重 hash artifact、核对 state/result，并在 chunked mode 重验 manifest exact concatenation；它是内部完整性 gate，不替代 Task 10 的独立 business audit。
- buffered mode 假设来源非空；`capture_high_watermark()` 会明确拒绝 empty `report_order`。chunked publish 可以处理 `rows_written=0` 的 checkpoint，但固定 S seed 本身不是 empty-data test。
- canonical parser 把不合法 JSON／缺字段视为 `FAILED`；它不是 state migration／repair tool。production 应给 state schema version、ownership、ACL、retention 和 reconciliation 独立设计。
- runner 将 validation、connection、execution 与 cleanup 都收在 structured failure boundary 内，每次 invocation 只允许一个 structured JSON outcome。Task 10 controller 仍必须同时 reconcile child JSON、return code 与 persisted state，不能只看 exit code。

这些限制没有改变 S 级实验的安全性：Task 10 使用 fresh job directory、immutable `report_order`／`report_item`，且 interrupted resume 只作 correctness evidence，不拿 resumed throughput 作性能结论。它们也意味着不能把 S 级结果外推为 mutable production export 已经正确。

## OLTP probe 与三次矩阵

`--mode oltp` 的每个 operation 是随机 primary-key `SELECT counter` 加一个 autocommit `UPDATE counter=counter+1`。final JSON 报告 trial identity、成功 operation count、compound operation 的 p50／p95／p99、error count 与 strict drain／heartbeat-lateness diagnostics；live metrics 每约一秒 atomically replace 同 trial 的 heartbeat。probe 是干扰量尺，不是业务 workload 的替身。

每组必须跑三次，每个 export trial 使用 fresh job directory：

| Group | OLTP probe | Export |
|---|---|---|
| control | 60 s，4 threads | none |
| buffered | 60 s，4 threads | one buffered query／artifact |
| chunked | 60 s，4 threads | `batch=1000`、`sleep=20 ms` |

执行顺序固定：

1. 先独立跑三次 control，要求三次 `errors=0`。
2. 以三次 control P95 的 median 定义预算：`OLTP_P95_BUDGET = 1.50 × median(control P95)`；必须在 export 前写下数字。
3. 每个 concurrent trial 先启动 OLTP；controller 必须观察到同一 `trial_id` 至少五个 fresh、advancing、nonempty window，覆盖至少五秒 active time且 cumulative work 为正，才启动 export。只等 wall clock 五秒不算证据。
4. export 前后各 capture MySQL status；OLTP 与 export 都结束后才归档 final JSON、所有 accepted live windows、state、manifest 与 artifact audit。
5. 同组后续 trial 是否继续，由停止条件决定，不可跑完后才补一个预算。

### 每次要记录的证据

OLTP JSON：

```text
trial_id, operations, p50_ms, p95_ms, p99_ms, errors, status,
drain_limit_hits, max_heartbeat_lateness_ms,
connector_contract, worker_connections(worker, connection_id, closed, close_proof)

live: heartbeat_at_epoch, window_seq, window_operations, window_errors,
window_p95_ms, operations, errors, active_elapsed_seconds,
drain_limit_hits, max_heartbeat_lateness_ms
```

Export JSON：

```text
status, job_id, rows, sha256, active_seconds, rows_per_active_second,
max_rss_bytes, high_cursor, last_cursor, parts（chunked）, connector_contract
```

Implementation contract 不是 console-only annotation：runner 把它写进 resumable state／result，controller 对 child、persisted state／result 与 current exact-pure environment 做 reconcile；`FAILED` outcome 也保留 observed connector envelope。缺失、malformed、actual-mode mismatch 或跨 resume 改变都使 trial fail closed。

MySQL 观察窗口：

```sql
SHOW FULL PROCESSLIST;
SHOW GLOBAL STATUS
WHERE Variable_name IN (
  'Created_tmp_tables',
  'Created_tmp_disk_tables',
  'Sort_rows',
  'Sort_scan',
  'Sort_range',
  'Sort_merge_passes'
);
SHOW ENGINE INNODB STATUS;
```

这些值是 shared/global 观察量，必须保留前后值与 delta，并声明实验期间是否还有其他 workload；不能把全局增量全归因于一条 SQL。`Created_tmp_disk_tables` 也不会计入 TempTable mmap overflow 的所有情况，官方文件明确说明了这个监控缺口。[MySQL 8.0 internal temporary table monitoring](https://dev.mysql.com/doc/refman/8.0/en/internal-temporary-tables.html)

### Numeric disk gate

S 级实验在任何 group 前固定使用同一个公式，不能只写“磁盘看起来够”：

```text
EXPECTED_ARTIFACT_BYTES = expected_rows(100000) * 256 = 25,600,000
MIN_FREE_BYTES = 2 * EXPECTED_ARTIFACT_BYTES + 5 * 1024^3
               = 5,419,909,120
```

controller 在每个 group 前和 live 60 秒期间检查 `MIN_FREE_BYTES`；chunked runner 也在每次新 batch 前检查 `--min-free-bytes 5419909120`。buffered 没有 batch boundary，不能假装 abort file 能中止正在执行的单条 query。

### Artifact correctness gate

每个 buffered、chunked 与 resume 后 artifact 都必须同时满足：

```text
rows = 100000
high_cursor = ["2026-01-02 03:46:40.000000", 100000]
last_cursor = high_cursor
buffered SHA-256 = chunked SHA-256 = resumed SHA-256
100000 distinct order ids
每行恰好 6 个 TSV columns
artifact aggregate total_amount = source aggregate fingerprint
artifact item_count sum = 300000
```

只有 row count 不足以证明完整：duplicate 与 missing 可能互相抵消；只有 SHA 也不足以解释语义，所以同时保存 source manifest、high／last cursor、distinct key 与 aggregate fingerprint。

### Interruption／resume 固定步骤

第一次只允许完成三个 checkpoint：

```bash
uv run --with mysql-connector-python==9.7.0 python "$MYSQL_SCENARIO_RUN_DIR/export_runner.py" \
  --mode chunked --runtime-root "$MYSQL_SCENARIO_RUN_DIR" \
  --job-dir "$MYSQL_SCENARIO_RUN_DIR/job-resume" \
  --abort-file "$MYSQL_SCENARIO_RUN_DIR/abort-resume.json" \
  --batch-size 1000 --sleep-ms 20 --max-batches 3 \
  --min-free-bytes 5419909120 \
  --host 127.0.0.1 --port 3306 --user root --password-env MYSQL_PASSWORD
```

验收 first invocation：

```text
result.status = ABORTED
state.status = ABORTED
rows_written = 3000
next_part = 4
parts = 3
artifact.tsv 不存在
```

再以 **同一 job directory** 续跑：

```bash
uv run --with mysql-connector-python==9.7.0 python "$MYSQL_SCENARIO_RUN_DIR/export_runner.py" \
  --mode chunked --runtime-root "$MYSQL_SCENARIO_RUN_DIR" \
  --job-dir "$MYSQL_SCENARIO_RUN_DIR/job-resume" \
  --abort-file "$MYSQL_SCENARIO_RUN_DIR/abort-resume.json" \
  --batch-size 1000 --sleep-ms 20 --max-batches 0 \
  --min-free-bytes 5419909120 \
  --host 127.0.0.1 --port 3306 --user root --password-env MYSQL_PASSWORD
```

第二次必须成为 `SUCCEEDED`，final artifact 无 duplicate／missing，SHA 与 fresh buffered／chunked 相同。这个步骤验证 ABORTED → resume → SUCCEEDED 的 process-level state machine；没有注入 “rename 后、checkpoint 前” 的精确 crash point，也没有模拟 host power loss，所以不能把这两项写成 observed fact。

### Task 10 controller 的 fail-closed 契约

Task 10 把下方第二个 canonical executable fence 原样物化到 `$MYSQL_SCENARIO_RUN_DIR/scenario_controller.py`；它是 temporary controller source，不新增 repository script。CLI 固定：

```text
--runner <runtime-root>/export_runner.py
--runtime-root /private/tmp/mysql-senior-scenarios.<suffix>
--trial-id <run-id>
--job-dir <runtime-root>/job-<run-id>
--export-mode none|buffered|chunked|preflight-kill|preflight-oltp
--p95-budget-ms <predeclared-control-derived-number>
--min-free-bytes 5419909120
--duration-seconds 60
--start-delay-seconds 5
--startup-grace-seconds 12
--heartbeat-grace-seconds 2.5
--threads 4 --batch-size 1000 --sleep-ms 20
--host 127.0.0.1 --port 3306 --user root --password-env MYSQL_PASSWORD
```

`--runtime-root`、runner、job、metrics、abort、stdout/stderr 与 controller-result 全部绑定到同一个 exact runtime root；export mode 的 `job-<run-id>` suffix 必须等于 `trial-id`。

Before any timed control or buffered trial, prove that the controller identity can interrupt a different connection. This mode opens two disposable, explicitly pure connections. The victim creates connection-local temporary table `kill_preflight_probe`, inserts one row, then executes exact marked row query `SELECT /* mysql_senior_kill_preflight */ 1 FROM kill_preflight_probe WHERE SLEEP(30)=0`. The killer polls `information_schema.PROCESSLIST` for the validated positive victim ID and requires the returned ID and full SQL to equal that exact query; a fixed sleep or an event set before `execute()` is not proof that the statement is active. Only after this bounded five-second poll succeeds may it issue `KILL QUERY <validated-positive-connection-id>`, require victim Connector errno `1317`, and close both connections so the temporary table is discarded. Never-active, wrong-ID/query, actual-mode mismatch, poll/permission error or normal query return fails closed without claiming cancellation. MySQL documents that interrupted standalone `SLEEP()` returns `1` without a query error, while its row-query example with `SLEEP()` in `WHERE` produces error `1317`. [MySQL 8.0 `SLEEP()`](https://dev.mysql.com/doc/refman/8.0/en/miscellaneous-functions.html)

Require controller status `SUCCEEDED`, mode `preflight-kill`, observed errno `1317`, positive `connection_id`, exact `active_query`, `active_polls >= 1`, `victim_connection_absent=true`, `temporary_table_discarded=true` and `cleanup_polls >= 1`. Preserve these active-query and cleanup observations with the preflight result. Any connection, active-query poll, identity, permission, interruption, cleanup or structured-result failure stops the matrix; in particular, skip all buffered trials rather than discovering missing `KILL QUERY` authority only after a live breach.

Before the live preflight, injected offline contract tests must also require that an unexpected victim errno is re-raised and closes all resources, and that a victim still visible through the cleanup timeout fails closed and closes both connections. The success path must assert `cleanup_polls >= 1`. Additional injected contracts must prove every runner/controller connection receives `use_pure=True`, actual-mode mismatch fails closed with the observed envelope, each OLTP worker owns and verifiably closes a distinct connection even across cursor／connection close faults, coercible non-integer child fields are rejected, export/KILL semantics remain reconciled, and smoke acceptance/rejection cannot bypass structured child, metrics or connector evidence.

```python
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from collections import namedtuple
from pathlib import Path

import mysql.connector
from mysql.connector.connection import MySQLConnection


RUNTIME_PREFIX = "mysql-senior-scenarios."
KILL_PREFLIGHT_SQL = (
    "SELECT /* mysql_senior_kill_preflight */ 1 "
    "FROM kill_preflight_probe WHERE SLEEP(30)=0"
)
PROCESSLIST_SQL = (
    "SELECT ID, INFO FROM information_schema.PROCESSLIST "
    "WHERE ID=%s AND COMMAND='Query'"
)


MetricsSnapshot = namedtuple(
    "MetricsSnapshot",
    ("document", "mtime_ns", "device", "inode", "size_bytes"),
)


def connector_environment() -> dict:
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "connector_version": mysql.connector.__version__,
        "threadsafety": int(mysql.connector.threadsafety),
        "have_cext": bool(mysql.connector.HAVE_CEXT),
        "requested_use_pure": True,
    }


class ConnectorContractError(RuntimeError):
    def __init__(self, message: str, connector_evidence: dict):
        super().__init__(message)
        self.connector_evidence = connector_evidence


def observe_connector(connection=None) -> dict:
    return {
        **connector_environment(),
        "actual_connection_class": (
            None
            if connection is None
            else f"{type(connection).__module__}.{type(connection).__qualname__}"
        ),
        "actual_pure": (
            None if connection is None else type(connection) is MySQLConnection
        ),
    }


def require_pure_connection(connection) -> dict:
    observed = observe_connector(connection)
    if type(connection) is not MySQLConnection:
        raise ConnectorContractError(
            "connector did not return the required pure Python MySQLConnection",
            observed,
        )
    return observed


def connector_failure_evidence(exc: Exception, fallback: dict) -> dict:
    observed = getattr(exc, "connector_evidence", fallback)
    return observed if isinstance(observed, dict) else fallback


def validate_connector_evidence(value) -> dict:
    expected_environment = connector_environment()
    expected_keys = set(expected_environment) | {
        "actual_connection_class",
        "actual_pure",
    }
    valid_actual_class = value.get("actual_connection_class") if isinstance(value, dict) else None
    valid_actual_pure = value.get("actual_pure") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or set(value) != expected_keys
        or any(value.get(key) != expected for key, expected in expected_environment.items())
        or (
            valid_actual_class is not None
            and (
                not isinstance(valid_actual_class, str)
                or not valid_actual_class
            )
        )
        or (
            valid_actual_pure is not True
            and valid_actual_pure is not False
            and valid_actual_pure is not None
        )
        or ((valid_actual_class is None) != (valid_actual_pure is None))
    ):
        fallback = observe_connector()
        if isinstance(value, dict):
            fallback.update(
                {
                    "actual_connection_class": value.get("actual_connection_class"),
                    "actual_pure": value.get("actual_pure"),
                }
            )
        raise ConnectorContractError(
            "connector evidence is missing or malformed", fallback
        )
    return value


def validate_connector_contract(value: dict) -> dict:
    expected = {
        **connector_environment(),
        "actual_connection_class": (
            f"{MySQLConnection.__module__}.{MySQLConnection.__qualname__}"
        ),
        "actual_pure": True,
    }
    if value != expected:
        observed = validate_connector_evidence(value)
        raise ConnectorContractError(
            "connector contract is missing or contradictory", observed
        )
    return value


def validate_worker_connections(result: dict) -> list[dict]:
    contract = validate_connector_contract(result.get("connector_contract"))
    workers = result.get("worker_connections")
    try:
        threads = _integer_field(result, "threads")
        if threads < 1:
            raise ValueError("threads must be positive")
    except ValueError as exc:
        raise RuntimeError("OLTP worker thread count is invalid") from exc
    if not isinstance(workers, list) or len(workers) != threads:
        raise RuntimeError("OLTP worker connection evidence is incomplete")
    expected_contract_fields = set(contract)
    connection_ids = set()
    for expected_worker, worker in enumerate(workers, 1):
        if not isinstance(worker, dict):
            raise RuntimeError("OLTP worker connection evidence is malformed")
        observed_contract = {
            key: worker.get(key) for key in expected_contract_fields
        }
        try:
            worker_number = _integer_field(worker, "worker")
            connection_id = _integer_field(worker, "connection_id")
        except ValueError as exc:
            raise RuntimeError("OLTP worker integer evidence is invalid") from exc
        if (
            worker_number != expected_worker
            or worker.get("closed") is not True
            or worker.get("close_proof") != "is_connected_false"
            or connection_id <= 0
            or observed_contract != contract
        ):
            raise RuntimeError("OLTP worker connection contract is invalid")
        connection_ids.add(connection_id)
    if len(connection_ids) != threads:
        raise RuntimeError("OLTP workers shared a connection")
    return workers


class StructuredArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path.name} is not a JSON object")
    return value


def validated_runtime_root(path: Path) -> Path:
    resolved = path.resolve()
    private_tmp = Path("/private/tmp").resolve()
    if (
        resolved.parent != private_tmp
        or not resolved.name.startswith(RUNTIME_PREFIX)
        or resolved.name == RUNTIME_PREFIX
    ):
        raise ValueError("runtime root is outside the allowed nonempty prefix")
    return resolved


def validated_job_dir(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if (
        resolved.parent != root
        or not resolved.name.startswith("job-")
        or resolved.name == "job-"
    ):
        raise ValueError("job directory must be an immediate job-<run-id> child")
    return resolved


def gate_reason(
    metrics: dict | None,
    free_bytes: int,
    p95_budget_ms: float,
    min_free_bytes: int,
) -> str | None:
    if free_bytes < min_free_bytes:
        return f"disk_free_bytes={free_bytes} below {min_free_bytes}"
    if metrics is None:
        return None
    if int(metrics.get("errors", 0)) > 0:
        return "OLTP cumulative errors exceeded zero"
    if int(metrics.get("window_errors", 0)) > 0:
        return "OLTP window errors exceeded zero"
    if (
        p95_budget_ms > 0
        and int(metrics.get("window_operations", 0)) > 0
        and float(metrics.get("window_p95_ms", 0.0)) > p95_budget_ms
    ):
        return (
            f"OLTP window P95 {metrics['window_p95_ms']} "
            f"exceeded {p95_budget_ms}"
        )
    return None


def new_metrics_tracker() -> dict:
    return {
        "window_seq": 0,
        "last_advance_monotonic": None,
        "operations": 0,
        "errors": 0,
        "active_elapsed_seconds": 0.0,
        "drain_limit_hits": 0,
        "max_heartbeat_lateness_ms": 0.0,
        "activity_windows": 0,
        "last_window_operations": 0,
        "last_status": None,
        "sequence_payload": None,
        "accepted_windows": [],
    }


def _integer_field(metrics: dict, name: str) -> int:
    value = metrics.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _float_field(metrics: dict, name: str) -> float:
    value = metrics.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return parsed


def inspect_metrics(
    metrics: dict | None,
    trial_id: str,
    now_epoch: float,
    now_monotonic: float,
    tracker: dict,
    heartbeat_grace_seconds: float,
    require_present: bool,
) -> tuple[dict, str | None]:
    if metrics is None:
        return (
            dict(tracker),
            (
                "OLTP metrics missing"
                if require_present or int(tracker.get("window_seq", 0)) > 0
                else None
            ),
        )
    try:
        if metrics.get("status") not in ("RUNNING", "SUCCEEDED", "FAILED"):
            raise ValueError("status is invalid")
        if metrics.get("trial_id") != trial_id:
            return dict(tracker), "OLTP metrics trial_id mismatch"
        heartbeat = _float_field(metrics, "heartbeat_at_epoch")
        sequence = _integer_field(metrics, "window_seq")
        if sequence < 1:
            raise ValueError("window_seq must be positive")
        window_operations = _integer_field(metrics, "window_operations")
        if window_operations < 1:
            raise ValueError("window_operations must be positive")
        window_errors = _integer_field(metrics, "window_errors")
        window_p95 = _float_field(metrics, "window_p95_ms")
        operations = _integer_field(metrics, "operations")
        errors = _integer_field(metrics, "errors")
        active_elapsed = _float_field(metrics, "active_elapsed_seconds")
        drain_limit_hits = _integer_field(metrics, "drain_limit_hits")
        max_heartbeat_lateness_ms = _float_field(
            metrics, "max_heartbeat_lateness_ms"
        )
    except (TypeError, ValueError) as exc:
        return dict(tracker), f"OLTP metrics malformed: {exc}"

    if heartbeat > now_epoch + 1.0:
        return dict(tracker), "OLTP metrics heartbeat is in the future"
    if now_epoch - heartbeat > heartbeat_grace_seconds:
        return dict(tracker), "OLTP metrics heartbeat is stale"

    previous_sequence = int(tracker["window_seq"])
    if sequence < previous_sequence:
        return dict(tracker), "OLTP metrics sequence regressed"
    sequence_payload = (
        metrics["status"],
        heartbeat,
        sequence,
        window_operations,
        window_errors,
        window_p95,
        operations,
        errors,
        active_elapsed,
        drain_limit_hits,
        max_heartbeat_lateness_ms,
    )
    if sequence == previous_sequence:
        if sequence_payload != tracker.get("sequence_payload"):
            return dict(tracker), "OLTP metrics sequence payload changed"
        last_advance = tracker.get("last_advance_monotonic")
        if (
            last_advance is not None
            and now_monotonic - float(last_advance) > heartbeat_grace_seconds
        ):
            return dict(tracker), "OLTP metrics sequence is nonadvancing"
        return dict(tracker), None
    previous_operations = int(tracker["operations"])
    previous_errors = int(tracker["errors"])
    previous_active_elapsed = float(tracker["active_elapsed_seconds"])
    previous_drain_limit_hits = int(tracker["drain_limit_hits"])
    previous_max_heartbeat_lateness_ms = float(
        tracker["max_heartbeat_lateness_ms"]
    )
    if previous_sequence == 0:
        if operations < window_operations:
            return dict(tracker), (
                "OLTP metrics window operations exceed cumulative operations"
            )
        if errors < window_errors:
            return dict(tracker), (
                "OLTP metrics window errors exceed cumulative errors"
            )
        if active_elapsed <= 0.0:
            return dict(tracker), (
                "OLTP metrics active elapsed time must be positive"
            )
    else:
        if operations <= previous_operations:
            return dict(tracker), (
                "OLTP metrics cumulative operations did not advance"
            )
        if errors < previous_errors:
            return dict(tracker), "OLTP metrics cumulative errors regressed"
        if active_elapsed <= previous_active_elapsed:
            return dict(tracker), (
                "OLTP metrics active elapsed time did not advance"
            )
        if drain_limit_hits < previous_drain_limit_hits:
            return dict(tracker), "OLTP metrics drain_limit_hits regressed"
        if max_heartbeat_lateness_ms < previous_max_heartbeat_lateness_ms:
            return (
                dict(tracker),
                "OLTP metrics max_heartbeat_lateness_ms regressed",
            )
        operation_delta = operations - previous_operations
        error_delta = errors - previous_errors
        if operation_delta < window_operations:
            return dict(tracker), (
                "OLTP metrics window operations exceed cumulative delta"
            )
        if error_delta < window_errors:
            return dict(tracker), (
                "OLTP metrics window errors exceed cumulative delta"
            )
        if sequence == previous_sequence + 1:
            if operation_delta != window_operations:
                return dict(tracker), (
                    "OLTP metrics consecutive operation delta is inconsistent"
                )
            if error_delta != window_errors:
                return dict(tracker), (
                    "OLTP metrics consecutive error delta is inconsistent"
                )

    updated = dict(tracker)
    updated["window_seq"] = sequence
    updated["last_advance_monotonic"] = now_monotonic
    updated["operations"] = operations
    updated["errors"] = errors
    updated["active_elapsed_seconds"] = active_elapsed
    updated["drain_limit_hits"] = drain_limit_hits
    updated["max_heartbeat_lateness_ms"] = max_heartbeat_lateness_ms
    updated["last_window_operations"] = window_operations
    updated["last_status"] = metrics["status"]
    updated["sequence_payload"] = sequence_payload
    accepted_windows = list(updated["accepted_windows"])
    accepted_windows.append(
        {
            "status": metrics["status"],
            "trial_id": trial_id,
            "heartbeat_at_epoch": heartbeat,
            "window_seq": sequence,
            "window_operations": window_operations,
            "window_errors": window_errors,
            "window_p95_ms": window_p95,
            "operations": operations,
            "errors": errors,
            "active_elapsed_seconds": active_elapsed,
            "drain_limit_hits": drain_limit_hits,
            "max_heartbeat_lateness_ms": max_heartbeat_lateness_ms,
        }
    )
    updated["accepted_windows"] = accepted_windows
    if metrics["status"] == "RUNNING":
        updated["activity_windows"] = int(updated["activity_windows"]) + 1
    return updated, None


def build_metrics_breach_diagnostics(
    snapshot: MetricsSnapshot | None,
    now_epoch: float,
    tracker: dict,
    reason: str,
) -> dict:
    latest_metrics = None if snapshot is None else snapshot.document
    heartbeat_age_seconds = None
    if isinstance(latest_metrics, dict):
        try:
            heartbeat_age_seconds = now_epoch - _float_field(
                latest_metrics, "heartbeat_at_epoch"
            )
        except ValueError:
            heartbeat_age_seconds = None
    return {
        "reason": reason,
        "last_metrics": latest_metrics,
        "heartbeat_age_seconds": heartbeat_age_seconds,
        "metrics_file_mtime_ns": (
            None if snapshot is None else snapshot.mtime_ns
        ),
        "metrics_file_identity": (
            None
            if snapshot is None
            else {
                "device": snapshot.device,
                "inode": snapshot.inode,
                "size_bytes": snapshot.size_bytes,
            }
        ),
        "metrics_tracker": dict(tracker),
    }


def ready_for_export(tracker: dict, minimum_active_seconds: float) -> bool:
    return (
        tracker.get("last_status") == "RUNNING"
        and int(tracker.get("activity_windows", 0)) >= 5
        and float(tracker.get("active_elapsed_seconds", 0.0))
        >= max(5.0, minimum_active_seconds)
        and int(tracker.get("operations", 0)) > 0
        and int(tracker.get("last_window_operations", 0)) > 0
    )


def _parse_child_output(stdout: str, stderr: str) -> dict:
    records = []
    for stream_name, content in (("stdout", stdout), ("stderr", stderr)):
        for line in content.splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"child {stream_name} contains malformed JSON"
                ) from exc
            if not isinstance(value, dict):
                raise RuntimeError(f"child {stream_name} JSON is not an object")
            records.append(value)
    if len(records) != 1:
        raise RuntimeError("child must emit exactly one structured JSON object")
    if records[0].get("status") not in ("SUCCEEDED", "ABORTED", "FAILED"):
        raise RuntimeError("child JSON status is invalid")
    return records[0]


def read_child_result(stdout_path: Path, stderr_path: Path) -> dict:
    stdout = stdout_path.read_text(encoding="utf-8")
    stderr = stderr_path.read_text(encoding="utf-8")
    return _parse_child_output(stdout, stderr)


def _matching_result_fields(left: dict, right: dict) -> bool:
    return left == right


def reconcile_export_result(
    mode: str,
    returncode: int | None,
    child: dict,
    job_dir: Path,
    verifier_command: list[str],
    run_verifier=subprocess.run,
) -> dict:
    if returncode is None:
        raise RuntimeError("export child was never started")
    state_path = job_dir / "state.json"
    if not state_path.is_file():
        raise RuntimeError("export persisted state is missing")
    state = read_json(state_path)
    expected_job_id = job_dir.name[len("job-") :]
    if state.get("job_id") != expected_job_id or state.get("mode") != mode:
        raise RuntimeError("export persisted state identity is invalid")
    if child.get("mode") != mode or child.get("job_id") != expected_job_id:
        raise RuntimeError("export child identity contradicts persisted state")

    status = child["status"]
    if status == "ABORTED":
        validate_connector_contract(child.get("connector_contract"))
        if child.get("connector_contract") != state.get("connector_contract"):
            raise RuntimeError("ABORTED connector contract contradicts state")
        if returncode != 0 or state.get("status") != "ABORTED":
            raise RuntimeError("ABORTED child contradicts return code or persisted state")
        if int(child.get("rows", -1)) != int(state.get("rows_written", -2)):
            raise RuntimeError("ABORTED child rows contradict persisted checkpoint")
        if child.get("reason") != state.get("abort_reason"):
            raise RuntimeError("ABORTED child reason contradicts persisted checkpoint")
        if child.get("high_cursor") != [
            state.get("high_created_at"),
            state.get("high_id"),
        ]:
            raise RuntimeError("ABORTED child high cursor contradicts persisted checkpoint")
        if child.get("last_cursor") != [
            state.get("last_created_at"),
            state.get("last_id"),
        ]:
            raise RuntimeError("ABORTED child last cursor contradicts persisted checkpoint")
        if int(child.get("parts", -1)) != len(state.get("parts", [])):
            raise RuntimeError("ABORTED child part count contradicts persisted checkpoint")
        if float(child.get("active_seconds", -1.0)) != float(
            state.get("active_seconds", -2.0)
        ):
            raise RuntimeError("ABORTED child timing contradicts persisted checkpoint")
        if (job_dir / "result.json").exists():
            raise RuntimeError("ABORTED export unexpectedly has result.json")
        return child

    if status == "FAILED":
        if returncode == 0 or state.get("status") == "SUCCEEDED":
            raise RuntimeError("FAILED child contradicts return code or persisted state")
        return child

    if returncode != 0 or state.get("status") != "SUCCEEDED":
        raise RuntimeError("SUCCEEDED child contradicts return code or persisted state")
    result_path = job_dir / "result.json"
    if not result_path.is_file():
        raise RuntimeError("SUCCEEDED export result.json is missing")
    persisted = read_json(result_path)
    if persisted.get("status") != "SUCCEEDED":
        raise RuntimeError("persisted export result is not SUCCEEDED")
    if not _matching_result_fields(child, persisted):
        raise RuntimeError("child JSON contradicts persisted export result")
    validate_connector_contract(persisted.get("connector_contract"))
    if persisted.get("connector_contract") != state.get("connector_contract"):
        raise RuntimeError("SUCCEEDED connector contract contradicts state")

    verification = run_verifier(
        verifier_command,
        capture_output=True,
        text=True,
        check=False,
    )
    verified = _parse_child_output(
        verification.stdout or "",
        verification.stderr or "",
    )
    if verification.returncode != 0 or verified.get("status") != "SUCCEEDED":
        raise RuntimeError("runner fast-path integrity verification failed")
    if not _matching_result_fields(verified, persisted):
        raise RuntimeError("runner verifier contradicts persisted export result")
    return persisted


def validate_oltp_diagnostics(
    child: dict,
    tracker: dict | None = None,
) -> tuple[int, float]:
    try:
        drain_limit_hits = _integer_field(child, "drain_limit_hits")
        max_heartbeat_lateness_ms = _float_field(
            child, "max_heartbeat_lateness_ms"
        )
    except ValueError as exc:
        raise RuntimeError(
            f"OLTP child diagnostics are invalid: {exc}"
        ) from exc
    if tracker is not None:
        try:
            tracked_drain_limit_hits = _integer_field(
                tracker, "drain_limit_hits"
            )
            tracked_max_heartbeat_lateness_ms = _float_field(
                tracker, "max_heartbeat_lateness_ms"
            )
        except ValueError as exc:
            raise RuntimeError(
                f"OLTP tracker diagnostics are invalid: {exc}"
            ) from exc
        if (
            drain_limit_hits < tracked_drain_limit_hits
            or max_heartbeat_lateness_ms
            < tracked_max_heartbeat_lateness_ms
        ):
            raise RuntimeError("OLTP child diagnostics regressed")
    return drain_limit_hits, max_heartbeat_lateness_ms


def reconcile_oltp_result(
    returncode: int,
    child: dict,
    trial_id: str,
    tracker: dict | None = None,
) -> dict:
    if child.get("mode") != "oltp" or child.get("trial_id") != trial_id:
        raise RuntimeError("OLTP child identity is invalid")
    validate_oltp_diagnostics(child, tracker)
    if child.get("status") == "FAILED":
        if returncode == 0:
            raise RuntimeError("FAILED OLTP child returned exit code zero")
        validate_connector_evidence(child.get("connector_evidence"))
        return child
    try:
        operations = _integer_field(child, "operations")
        errors = _integer_field(child, "errors")
        validate_connector_contract(child.get("connector_contract"))
        validate_worker_connections(child)
    except ValueError as exc:
        raise RuntimeError(f"OLTP child counters are invalid: {exc}") from exc
    if (
        returncode == 0
        and child.get("status") == "SUCCEEDED"
        and operations > 0
        and errors == 0
    ):
        return child
    raise RuntimeError("OLTP child JSON contradicts its return code or trial identity")


def validate_oltp_smoke(
    oltp_result: dict,
    tracker: dict,
    duration_seconds: int,
    threads: int,
) -> dict:
    if duration_seconds != 5 or threads != 4:
        raise RuntimeError("OLTP smoke must run for five seconds with four threads")
    try:
        operations = _integer_field(oltp_result, "operations")
        errors = _integer_field(oltp_result, "errors")
        child_threads = _integer_field(oltp_result, "threads")
        window_seq = _integer_field(tracker, "window_seq")
        tracker_operations = _integer_field(tracker, "operations")
        tracker_errors = _integer_field(tracker, "errors")
        active_elapsed = _float_field(tracker, "active_elapsed_seconds")
        drain_limit_hits = _integer_field(oltp_result, "drain_limit_hits")
        max_heartbeat_lateness_ms = _float_field(
            oltp_result, "max_heartbeat_lateness_ms"
        )
    except ValueError as exc:
        raise RuntimeError("OLTP smoke numeric evidence is malformed") from exc
    if (
        oltp_result.get("status") != "SUCCEEDED"
        or operations <= 0
        or errors != 0
        or child_threads != 4
    ):
        raise RuntimeError("OLTP smoke child result failed its work/error contract")
    workers = validate_worker_connections(oltp_result)
    accepted = tracker.get("accepted_windows")
    if (
        window_seq < 2
        or not isinstance(accepted, list)
        or len(accepted) < 2
        or tracker_operations <= 0
        or tracker_errors != 0
        or active_elapsed <= 0.0
    ):
        raise RuntimeError("OLTP smoke metrics did not progress")
    return {
        "status": "SUCCEEDED",
        "mode": "preflight-oltp",
        "duration_seconds": duration_seconds,
        "threads": threads,
        "operations": operations,
        "errors": errors,
        "drain_limit_hits": drain_limit_hits,
        "max_heartbeat_lateness_ms": max_heartbeat_lateness_ms,
        "accepted_windows": len(accepted),
        "last_window_seq": window_seq,
        "worker_connections": len(workers),
        "connector_contract": oltp_result["connector_contract"],
        "excluded_from_control_statistics": True,
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def experiment_binding(root: Path, runner: Path, config: dict) -> dict:
    try:
        port = _integer_field(config, "port")
    except ValueError as exc:
        raise RuntimeError("experiment port binding is invalid") from exc
    if port <= 0 or config.get("use_pure") is not True:
        raise RuntimeError("experiment connector binding is invalid")
    return {
        "runtime_root": str(root.resolve()),
        "runner_sha256": file_sha256(runner),
        "host": config.get("host"),
        "port": port,
        "user": config.get("user"),
        "database": config.get("database"),
        "requested_use_pure": True,
    }


def validate_persisted_smoke(root: Path, binding: dict) -> dict:
    path = root / "controller-result-oltp-smoke-1.json"
    if not path.is_file():
        raise RuntimeError("persisted OLTP smoke artifact is missing")
    result = read_json(path)
    smoke = result.get("smoke_result")
    if (
        result.get("status") != "SUCCEEDED"
        or result.get("mode") != "preflight-oltp"
        or result.get("experiment_binding") != binding
        or not isinstance(smoke, dict)
        or smoke.get("status") != "SUCCEEDED"
        or smoke.get("mode") != "preflight-oltp"
        or smoke.get("excluded_from_control_statistics") is not True
    ):
        raise RuntimeError("persisted OLTP smoke binding or status is invalid")
    try:
        duration = _integer_field(smoke, "duration_seconds")
        threads = _integer_field(smoke, "threads")
        operations = _integer_field(smoke, "operations")
        errors = _integer_field(smoke, "errors")
        accepted = _integer_field(smoke, "accepted_windows")
        last_window = _integer_field(smoke, "last_window_seq")
        workers = _integer_field(smoke, "worker_connections")
        _integer_field(smoke, "drain_limit_hits")
        _float_field(smoke, "max_heartbeat_lateness_ms")
    except ValueError as exc:
        raise RuntimeError("persisted OLTP smoke numeric evidence is invalid") from exc
    if (
        duration != 5
        or threads != 4
        or operations <= 0
        or errors != 0
        or accepted < 2
        or last_window < 2
        or workers != 4
    ):
        raise RuntimeError("persisted OLTP smoke evidence is insufficient")
    validate_connector_contract(smoke.get("connector_contract"))
    return smoke


def build_smoke_failure(
    breach: str,
    tracker: dict,
    returncode: int | None,
    stdout_path: Path,
    stderr_path: Path,
    trial_id: str,
) -> dict:
    result = {
        "status": "FAILED",
        "mode": "preflight-oltp",
        "reason": breach,
        "accepted_windows": list(tracker.get("accepted_windows", [])),
        "oltp_returncode": returncode,
    }
    try:
        child = read_child_result(stdout_path, stderr_path)
    except Exception as exc:
        result["structured_output_error"] = f"{type(exc).__name__}: {exc}"
        return result
    result["oltp_child"] = child
    if child.get("status") != "FAILED":
        result["child_reconciliation_error"] = (
            "smoke breach cannot accept a non-FAILED child"
        )
        return result
    try:
        result["oltp_failure"] = reconcile_oltp_result(
            returncode if returncode is not None else -1,
            child,
            trial_id,
            tracker=tracker,
        )
    except Exception as exc:
        result["child_reconciliation_error"] = f"{type(exc).__name__}: {exc}"
        result["connector_evidence"] = connector_failure_evidence(
            exc, observe_connector()
        )
    return result


def terminate_process(process, grace_seconds: float) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=grace_seconds)


def wait_for_state(job_dir: Path, timeout_seconds: float) -> dict | None:
    deadline = time.monotonic() + timeout_seconds
    state_path = job_dir / "state.json"
    while time.monotonic() < deadline:
        if state_path.is_file():
            return read_json(state_path)
        time.sleep(0.05)
    return None


def kill_buffered_query(config: dict, connection_id: int) -> dict:
    try:
        validated_id = _integer_field(
            {"connection_id": connection_id}, "connection_id"
        )
    except ValueError as exc:
        raise ValueError("connection_id must be a positive integer") from exc
    if validated_id <= 0:
        raise ValueError("connection_id must be a positive integer")
    if config.get("use_pure") is not True:
        raise ValueError("admin connection must request use_pure=True")
    admin = mysql.connector.connect(**config)
    cursor = None
    try:
        connector_contract = require_pure_connection(admin)
        cursor = admin.cursor()
        cursor.execute(f"KILL QUERY {validated_id}")
        return connector_contract
    finally:
        _close_quietly(cursor)
        admin.close()


def _persist_aborted_checkpoint(job_dir: Path, reason: str) -> str:
    state = wait_for_state(job_dir, 0.2)
    if state is None:
        return "MISSING"
    if state.get("status") == "SUCCEEDED":
        return "SUCCEEDED"
    state["status"] = "ABORTED"
    state["abort_reason"] = reason
    atomic_json(job_dir / "state.json", state)
    return "ABORTED"


def abort_export(
    mode: str,
    process,
    job_dir: Path,
    abort_file: Path,
    reason: str,
    admin_config: dict,
    grace_seconds: float,
    kill_query=kill_buffered_query,
) -> dict:
    atomic_json(
        abort_file,
        {"status": "ABORT_REQUESTED", "reason": reason, "mode": mode},
    )
    evidence = {
        "status": "ABORTED",
        "mode": mode,
        "reason": reason,
        "kill_query_sent": False,
        "forced_termination": False,
    }
    if process is None:
        evidence["not_started"] = True
        return evidence
    if process.poll() is not None:
        evidence["already_exited"] = True
        evidence["persisted_state_status"] = _persist_aborted_checkpoint(
            job_dir, reason
        )
        return evidence

    if mode == "buffered":
        state = wait_for_state(job_dir, 2.0)
        if state is not None and state.get("connection_id") is not None:
            try:
                evidence["kill_query_connector"] = kill_query(
                    admin_config, state["connection_id"]
                )
                evidence["kill_query_sent"] = True
            except Exception as exc:
                evidence["kill_query_error"] = f"{type(exc).__name__}: {exc}"
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        evidence["forced_termination"] = True
        terminate_process(process, grace_seconds)
    evidence["persisted_state_status"] = _persist_aborted_checkpoint(
        job_dir, reason
    )
    return evidence


def _close_quietly(resource) -> None:
    if resource is not None:
        try:
            resource.close()
        except Exception:
            pass


def wait_for_active_victim(
    killer_cursor,
    connection_id: int,
    expected_sql: str,
    future,
    timeout_seconds: float,
    monotonic=time.monotonic,
    pause=time.sleep,
) -> dict:
    validated_id = _integer_field(
        {"connection_id": connection_id}, "connection_id"
    )
    if validated_id <= 0:
        raise ValueError("connection_id must be a positive integer")
    if not 0 < timeout_seconds <= 10.0:
        raise ValueError("active query timeout must be in (0,10]")
    deadline = monotonic() + timeout_seconds
    polls = 0
    while monotonic() < deadline:
        polls += 1
        killer_cursor.execute(PROCESSLIST_SQL, (validated_id,))
        row = killer_cursor.fetchone()
        if row is not None:
            observed_id = _integer_field({"connection_id": row[0]}, "connection_id")
            observed_sql = str(row[1])
            if observed_id != validated_id:
                raise RuntimeError("active victim identity mismatch")
            if observed_sql != expected_sql:
                raise RuntimeError("active victim query mismatch")
            return {"active_query": observed_sql, "active_polls": polls}
        if future.done():
            raise RuntimeError("victim query ended before active observation")
        pause(0.02)
    raise RuntimeError("exact victim query was never observed active")


def wait_for_victim_cleanup(
    killer_cursor,
    connection_id: int,
    timeout_seconds: float,
    monotonic=time.monotonic,
    pause=time.sleep,
) -> int:
    validated_id = _integer_field(
        {"connection_id": connection_id}, "connection_id"
    )
    if validated_id <= 0:
        raise ValueError("connection_id must be a positive integer")
    if not 0 < timeout_seconds <= 10.0:
        raise ValueError("cleanup timeout must be in (0,10]")
    deadline = monotonic() + timeout_seconds
    polls = 0
    while True:
        polls += 1
        killer_cursor.execute(
            "SELECT COUNT(*) FROM information_schema.PROCESSLIST WHERE ID=%s",
            (validated_id,),
        )
        count = _integer_field({"processlist_count": killer_cursor.fetchone()[0]}, "processlist_count")
        if count == 0:
            return polls
        if monotonic() >= deadline:
            raise RuntimeError("victim connection survived cleanup deadline")
        pause(0.02)


def run_kill_query_preflight(
    config: dict,
    connect=mysql.connector.connect,
    pause=time.sleep,
    active_timeout_seconds: float = 5.0,
    cleanup_timeout_seconds: float = 2.0,
) -> dict:
    victim = None
    killer = None
    victim_cursor = None
    killer_cursor = None
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = None
    victim_connector = None
    killer_connector = None
    try:
        if config.get("use_pure") is not True:
            raise ValueError("KILL preflight must request use_pure=True")
        victim = connect(**config)
        killer = connect(**config)
        victim_connector = require_pure_connection(victim)
        killer_connector = require_pure_connection(killer)
        victim_cursor = victim.cursor()
        killer_cursor = killer.cursor()
        connection_id = _integer_field(
            {"connection_id": victim.connection_id}, "connection_id"
        )
        if connection_id <= 0:
            raise RuntimeError("preflight victim connection_id is invalid")
        victim_cursor.execute(
            "CREATE TEMPORARY TABLE kill_preflight_probe "
            "(id TINYINT UNSIGNED NOT NULL PRIMARY KEY) ENGINE=InnoDB"
        )
        victim_cursor.execute("INSERT INTO kill_preflight_probe VALUES (1)")

        def blocking_query() -> None:
            victim_cursor.execute(KILL_PREFLIGHT_SQL)
            victim_cursor.fetchall()

        future = executor.submit(blocking_query)
        active = wait_for_active_victim(
            killer_cursor,
            connection_id,
            KILL_PREFLIGHT_SQL,
            future,
            active_timeout_seconds,
            pause=pause,
        )
        killer_cursor.execute(f"KILL QUERY {connection_id}")
        try:
            future.result(timeout=5.0)
        except concurrent.futures.TimeoutError as exc:
            raise RuntimeError("KILL QUERY did not interrupt the victim") from exc
        except Exception as exc:
            if int(getattr(exc, "errno", -1)) != 1317:
                raise
        else:
            raise RuntimeError("KILL QUERY victim completed without interruption")
        _close_quietly(victim_cursor)
        victim_cursor = None
        _close_quietly(victim)
        victim = None
        cleanup_polls = wait_for_victim_cleanup(
            killer_cursor,
            connection_id,
            cleanup_timeout_seconds,
            pause=pause,
        )
        return {
            "status": "SUCCEEDED",
            "mode": "preflight-kill",
            "connection_id": connection_id,
            "observed_errno": 1317,
            "victim_connection_absent": True,
            "temporary_table_discarded": True,
            "cleanup_polls": cleanup_polls,
            "connector_contract": victim_connector,
            "connector_connections": {
                "victim": victim_connector,
                "killer": killer_connector,
            },
            **active,
        }
    except Exception as exc:
        observed = killer_connector or victim_connector
        if observed is not None and not hasattr(exc, "connector_evidence"):
            exc.connector_evidence = observed
        raise
    finally:
        _close_quietly(killer_cursor)
        _close_quietly(killer)
        if future is not None and not future.done():
            _close_quietly(victim)
            victim = None
        _close_quietly(victim_cursor)
        _close_quietly(victim)
        if future is not None and not future.done():
            try:
                future.result(timeout=1.0)
            except Exception:
                pass
        executor.shutdown(wait=False, cancel_futures=True)


def load_metrics_snapshot(path: Path) -> MetricsSnapshot | None:
    try:
        handle = path.open("rb")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RuntimeError(f"metrics snapshot open failed: {exc}") from exc
    with handle:
        try:
            before = os.fstat(handle.fileno())
        except OSError as exc:
            raise RuntimeError(
                f"metrics snapshot metadata read failed: {exc}"
            ) from exc
        try:
            raw = handle.read()
        except OSError as exc:
            raise RuntimeError(f"metrics snapshot read failed: {exc}") from exc
        try:
            after = os.fstat(handle.fileno())
        except OSError as exc:
            raise RuntimeError(
                f"metrics snapshot metadata read failed: {exc}"
            ) from exc
    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    )
    if before_identity != after_identity or len(raw) != after.st_size:
        raise RuntimeError("metrics snapshot changed during read")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"metrics snapshot JSON is malformed: {exc}"
        ) from exc
    if not isinstance(document, dict):
        raise RuntimeError("metrics snapshot JSON is malformed: object required")
    return MetricsSnapshot(
        document=dict(document),
        mtime_ns=after.st_mtime_ns,
        device=after.st_dev,
        inode=after.st_ino,
        size_bytes=after.st_size,
    )


def _require_fresh_paths(paths: list[Path]) -> None:
    existing = [path.name for path in paths if path.exists()]
    if existing:
        raise RuntimeError(
            "trial paths must not pre-exist: " + ", ".join(sorted(existing))
        )


def main() -> int:
    result_file = None
    oltp = None
    export = None
    handles = []
    connector_evidence = observe_connector()
    try:
        parser = StructuredArgumentParser()
        parser.add_argument("--runner", type=Path, required=True)
        parser.add_argument("--runtime-root", type=Path, required=True)
        parser.add_argument("--trial-id", required=True)
        parser.add_argument("--job-dir", type=Path)
        parser.add_argument(
            "--export-mode",
            choices=(
                "none",
                "buffered",
                "chunked",
                "preflight-kill",
                "preflight-oltp",
            ),
            required=True,
        )
        parser.add_argument("--p95-budget-ms", type=float, default=0.0)
        parser.add_argument("--min-free-bytes", type=int, required=True)
        parser.add_argument("--duration-seconds", type=int, default=60)
        parser.add_argument("--start-delay-seconds", type=float, default=5.0)
        parser.add_argument("--startup-grace-seconds", type=float, default=12.0)
        parser.add_argument("--heartbeat-grace-seconds", type=float, default=2.5)
        parser.add_argument("--threads", type=int, default=4)
        parser.add_argument("--batch-size", type=int, default=1000)
        parser.add_argument("--sleep-ms", type=int, default=20)
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=3306)
        parser.add_argument("--user", default="root")
        parser.add_argument("--password-env", default="MYSQL_PASSWORD")
        args = parser.parse_args()

        root = validated_runtime_root(args.runtime_root)
        runner = args.runner.resolve()
        if runner.parent != root or runner.name != "export_runner.py":
            raise ValueError("runner must be runtime-root/export_runner.py")
        if args.export_mode in ("buffered", "chunked") and args.job_dir is None:
            raise ValueError("--job-dir is required for export trials")
        if (
            not args.trial_id
            or any(
                not (character.isalnum() or character in "-_")
                for character in args.trial_id
            )
        ):
            raise ValueError(
                "trial-id must use only letters, digits, dash, or underscore"
            )
        job_dir = (
            validated_job_dir(args.job_dir, root)
            if args.job_dir is not None
            else root / "job-unused"
        )
        if (
            args.export_mode in ("buffered", "chunked")
            and job_dir.name != f"job-{args.trial_id}"
        ):
            raise ValueError("job directory run-id must equal trial-id")
        if (
            args.min_free_bytes <= 0
            or args.duration_seconds < 1
            or not 1 <= args.threads <= 16
            or args.start_delay_seconds < 5.0
            or args.startup_grace_seconds <= args.start_delay_seconds
            or not 0.5 <= args.heartbeat_grace_seconds <= 10.0
        ):
            raise ValueError("controller numeric argument is invalid")
        if args.export_mode == "preflight-oltp" and (
            args.trial_id != "oltp-smoke-1"
            or args.duration_seconds != 5
            or args.threads != 4
            or args.p95_budget_ms != 0.0
        ):
            raise ValueError("OLTP smoke requires its fixed ID/duration/threads/budget")
        if shutil.disk_usage(root).free < args.min_free_bytes:
            raise RuntimeError("pre-group disk gate failed")
        password = os.environ.get(args.password_env)
        if password is None:
            raise ValueError(
                f"password environment variable is not set: {args.password_env}"
            )
        admin_config = {
            "host": args.host,
            "port": args.port,
            "user": args.user,
            "password": password,
            "database": "mysql_senior_scenarios",
            "use_pure": True,
        }
        current_binding = experiment_binding(root, runner, admin_config)

        run_id = args.trial_id
        metrics_file = root / f"metrics-{run_id}.json"
        abort_file = root / f"abort-{run_id}.json"
        candidate_result_file = root / f"controller-result-{run_id}.json"
        oltp_stdout_path = root / f"oltp-{run_id}.stdout.json"
        oltp_stderr_path = root / f"oltp-{run_id}.stderr.json"
        export_stdout_path = root / f"export-{run_id}.stdout.json"
        export_stderr_path = root / f"export-{run_id}.stderr.json"
        _require_fresh_paths(
            [
                metrics_file,
                abort_file,
                candidate_result_file,
                oltp_stdout_path,
                oltp_stderr_path,
                export_stdout_path,
                export_stderr_path,
            ]
        )
        result_file = candidate_result_file
        if args.export_mode in ("buffered", "chunked") and job_dir.exists():
            raise RuntimeError("each trial requires a fresh job directory")

        if args.export_mode == "preflight-kill":
            result = run_kill_query_preflight(admin_config)
            result["controller_connector_environment"] = connector_environment()
            atomic_json(result_file, result)
            print(json.dumps(result, sort_keys=True))
            return 0

        smoke_gate = None
        if args.export_mode in ("none", "buffered", "chunked"):
            smoke_gate = validate_persisted_smoke(root, current_binding)

        common = [
            sys.executable,
            str(runner),
            "--runtime-root",
            str(root),
            "--host",
            args.host,
            "--port",
            str(args.port),
            "--user",
            args.user,
            "--password-env",
            args.password_env,
        ]
        oltp_stdout = oltp_stdout_path.open("w", encoding="utf-8")
        oltp_stderr = oltp_stderr_path.open("w", encoding="utf-8")
        handles.extend((oltp_stdout, oltp_stderr))
        oltp = subprocess.Popen(
            [
                *common,
                "--mode",
                "oltp",
                "--duration-seconds",
                str(args.duration_seconds),
                "--threads",
                str(args.threads),
                "--metrics-file",
                str(metrics_file),
                "--trial-id",
                run_id,
            ],
            stdout=oltp_stdout,
            stderr=oltp_stderr,
            text=True,
        )
        export_command = None
        breach = None
        export_abort = None
        started = time.monotonic()
        tracker = new_metrics_tracker()
        latest_snapshot = None
        latest_metrics = None

        while True:
            now_monotonic = time.monotonic()
            now_epoch = time.time()
            elapsed = now_monotonic - started
            try:
                latest_snapshot = load_metrics_snapshot(metrics_file)
                latest_metrics = (
                    None
                    if latest_snapshot is None
                    else latest_snapshot.document
                )
            except Exception as exc:
                breach = f"OLTP metrics malformed: {type(exc).__name__}: {exc}"
                break
            require_metrics = (
                export is not None or elapsed >= args.startup_grace_seconds
            )
            tracker, breach = inspect_metrics(
                latest_metrics,
                run_id,
                now_epoch,
                now_monotonic,
                tracker,
                args.heartbeat_grace_seconds,
                require_metrics,
            )
            if breach is None:
                breach = gate_reason(
                    latest_metrics,
                    shutil.disk_usage(root).free,
                    args.p95_budget_ms,
                    args.min_free_bytes,
                )
            if breach is not None:
                break

            if (
                export is None
                and args.export_mode in ("buffered", "chunked")
                and ready_for_export(tracker, args.start_delay_seconds)
            ):
                export_stdout = export_stdout_path.open("w", encoding="utf-8")
                export_stderr = export_stderr_path.open("w", encoding="utf-8")
                handles.extend((export_stdout, export_stderr))
                export_command = [
                    *common,
                    "--mode",
                    args.export_mode,
                    "--job-dir",
                    str(job_dir),
                    "--abort-file",
                    str(abort_file),
                ]
                if args.export_mode == "chunked":
                    export_command.extend(
                        [
                            "--batch-size",
                            str(args.batch_size),
                            "--sleep-ms",
                            str(args.sleep_ms),
                            "--min-free-bytes",
                            str(args.min_free_bytes),
                        ]
                    )
                export = subprocess.Popen(
                    export_command,
                    stdout=export_stdout,
                    stderr=export_stderr,
                    text=True,
                )

            if (
                export is None
                and args.export_mode in ("buffered", "chunked")
                and elapsed >= args.startup_grace_seconds
            ):
                breach = (
                    "OLTP did not produce five fresh nonempty windows "
                    "within startup grace"
                )
                break
            oltp_running = oltp.poll() is None
            export_running = export is not None and export.poll() is None
            if not oltp_running and export_running:
                breach = "OLTP ended before concurrent export completed"
                break
            if not oltp_running and not export_running:
                break
            time.sleep(0.1)

        if breach is not None:
            if export is not None:
                export_abort = abort_export(
                    args.export_mode,
                    export,
                    job_dir,
                    abort_file,
                    breach,
                    admin_config,
                    5.0,
                )
            terminate_process(oltp, 2.0)
            for handle in handles:
                handle.close()
            if args.export_mode == "preflight-oltp":
                result = build_smoke_failure(
                    breach,
                    tracker,
                    oltp.poll(),
                    oltp_stdout_path,
                    oltp_stderr_path,
                    run_id,
                )
                result["export_abort"] = None
                result["export_returncode"] = None
            else:
                result = {
                    "status": "ABORTED",
                    "mode": args.export_mode,
                    "reason": breach,
                    "accepted_windows": list(tracker["accepted_windows"]),
                    "export_abort": export_abort,
                    "oltp_returncode": oltp.poll(),
                    "export_returncode": (
                        export.poll() if export is not None else None
                    ),
                }
            if breach == "OLTP metrics heartbeat is stale":
                result["metrics_diagnostics"] = build_metrics_breach_diagnostics(
                    latest_snapshot,
                    now_epoch,
                    tracker,
                    breach,
                )
            result["experiment_binding"] = current_binding
            result["smoke_gate"] = smoke_gate
            result["controller_connector_environment"] = connector_environment()
        else:
            oltp_rc = oltp.wait()
            export_rc = export.wait() if export is not None else None
            for handle in handles:
                handle.close()
            oltp_child = read_child_result(oltp_stdout_path, oltp_stderr_path)
            oltp_result = reconcile_oltp_result(
                oltp_rc,
                oltp_child,
                run_id,
                tracker=tracker,
            )
            smoke_result = None
            if args.export_mode in ("none", "preflight-oltp"):
                if export is not None:
                    raise RuntimeError("control trial unexpectedly started export")
                export_result = None
                if (
                    args.export_mode == "preflight-oltp"
                    and oltp_result["status"] == "SUCCEEDED"
                ):
                    smoke_result = validate_oltp_smoke(
                        oltp_result,
                        tracker,
                        args.duration_seconds,
                        args.threads,
                    )
                status = "SUCCEEDED" if oltp_result["status"] == "SUCCEEDED" else "FAILED"
            else:
                if export is None or export_command is None:
                    raise RuntimeError(
                        "export never started from five fresh OLTP windows"
                    )
                export_child = read_child_result(
                    export_stdout_path, export_stderr_path
                )
                export_result = reconcile_export_result(
                    args.export_mode,
                    export_rc,
                    export_child,
                    job_dir,
                    export_command,
                )
                if oltp_result["status"] != "SUCCEEDED":
                    status = "FAILED"
                else:
                    status = export_result["status"]
            result = {
                "status": status,
                "mode": args.export_mode,
                "accepted_windows": list(tracker["accepted_windows"]),
                "oltp_returncode": oltp_rc,
                "export_returncode": export_rc,
                "oltp_result": oltp_result,
                "export_result": export_result,
                "smoke_result": smoke_result,
                "experiment_binding": current_binding,
                "smoke_gate": smoke_gate,
                "controller_connector_environment": connector_environment(),
            }
        atomic_json(result_file, result)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] in ("SUCCEEDED", "ABORTED") else 2
    except Exception as exc:
        result = {
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "connector_evidence": connector_failure_evidence(
                exc, connector_evidence
            ),
        }
        if result_file is not None:
            try:
                atomic_json(result_file, result)
            except Exception:
                pass
        print(json.dumps(result, sort_keys=True), file=sys.stderr)
        return 2
    finally:
        terminate_process(export, 1.0)
        terminate_process(oltp, 1.0)
        for handle in handles:
            _close_quietly(handle)


if __name__ == "__main__":
    raise SystemExit(main())
```

The fourth fresh run observed a pause at the OLTP metrics publication/process boundary: window 26 was the last complete document, the next zero-byte atomic-write temporary file appeared only at the controller's termination boundary, and no child stack or queue-depth sample was retained. The former unbounded `get_nowait()` drain is therefore the strongest code-level hypothesis consistent with the pre-write delay, not a proven unique cause; scheduler or other pre-write stalls remain possible. This correction does not increase the `2.5 s` heartbeat grace.

The runner checks a due publication before every bounded drain slice. A slice consumes at most `256` events and at most `10 ms` monotonic wall time; hitting either bound returns immediately to the publication check and skips the idle sleep while backlog may remain. When all futures finish, slices continue until the queue is observed empty, so cumulative operation/error totals neither lose nor duplicate events. Window membership is explicitly observation-based: an event belongs to the window in which the controller thread consumes it. Thus an event completed by a worker before a publication boundary but still queued is honestly counted in the next window; cumulative totals remain exact.

Every current runner metrics/result document, including the generic OLTP `FAILED` envelope, must contain strict `drain_limit_hits` and `max_heartbeat_lateness_ms` fields. The runner updates a shared in-process diagnostics envelope as work progresses. The controller validates it before returning either `FAILED` or `SUCCEEDED` and rejects missing, coercible, malformed or tracker-regressing values; there is no legacy-absence default in the current contract. On an exact stale-heartbeat breach it retains timed-mode `ABORTED` semantics. The last raw metrics document and its mtime/device/inode/size metadata come from one immutable snapshot read through the same opened file descriptor before termination. The controller therefore persists a coherent document, heartbeat age, file identity and full tracker/accepted-window evidence even if termination triggers a later atomic replacement.

Materialized runner／controller 必须保留 explicit `use_pure=True` 与 exact-type `MySQLConnection` gate。live work 前记录 Python/platform、Connector version、`threadsafety`、`HAVE_CEXT` 与 requested pure mode；successful result 加 exact pure class，所有 `FAILED` JSON 也保留 observed implementation envelope，包括 unknown／mismatched actual class。OLTP cleanup 即使 cursor close 失败也必须继续尝试 connection close；只有 `is_connected() is False` 才能记录 `closed=true`，缺 proof 或任一 close error 都 fail closed。child thread、worker 与 connection ID 是 exact JSON integer；string／boolean 都不接受。

KILL preflight 后、`control-1` 前，必须用同一 canonical runner 跑一次固定五秒、四 worker 的 client-concurrency smoke：

```bash
uv run --with mysql-connector-python==9.7.0 python \
  "$MYSQL_SCENARIO_RUN_DIR/scenario_controller.py" \
  --runner "$MYSQL_SCENARIO_RUN_DIR/export_runner.py" \
  --runtime-root "$MYSQL_SCENARIO_RUN_DIR" \
  --trial-id oltp-smoke-1 --export-mode preflight-oltp \
  --duration-seconds 5 --threads 4 \
  --p95-budget-ms 0 --min-free-bytes 5419909120 \
  --host 127.0.0.1 --port 3306 \
  --user root --password-env MYSQL_PASSWORD
```

Require one structured controller `SUCCEEDED`, positive child operations, zero child errors, at least two accepted advancing nonempty metric sequences, four distinct verifiably closed worker connections and an exact pure connector contract. Preserve the smoke result with `excluded_from_control_statistics=true` plus a binding over the exact runtime root, runner SHA-256 and non-secret connection configuration. For this mode only, any metrics／gate breach, native exit, empty／multiple／malformed child output, shared／unclosed connection or actual-mode mismatch persists controller `FAILED` and exits `2`; it must never use timed-export `ABORTED`／exit-0 semantics. Parse and retain a structured child failure when one exists, otherwise retain the structured-output error and implementation envelope. Never retry this smoke in the same runtime. The prior Python 3.13/macOS arm64/Connector 9.7.0 evidence—canonical one-thread success, default `HAVE_CEXT=true` four-thread exit 139, and the same four-thread workload succeeding with `use_pure=True`—is an excluded client/environment boundary, not a MySQL performance sample.

Every later timed `none`／`buffered`／`chunked` invocation must validate `controller-result-oltp-smoke-1.json` as `SUCCEEDED`, excluded, sufficiently progressing, exact-pure and equal to its current runtime／runner／connection binding before starting any child. Missing, failed, malformed, stale-runtime, changed-runner or changed-config smoke evidence fails the timed invocation before `Popen`; timed export breach behavior after this gate remains the documented `ABORTED` contract.

controller 与 runner 必须绑定同一个 exact `--runtime-root`。一个 `run-id` 只能拥有 `job-<run-id>/`、`abort-<run-id>.json`、`metrics-<run-id>.json` 与 controller evidence；wrong root、wrong trial、预先存在或 identity 冲突的控制文件都在 child 启动前失败。

live metrics 不是“写过文件就算有 load”。每个 accepted document 必须来自当前 trial、heartbeat fresh、`window_seq` advancing、`window_operations > 0`、active time 与 cumulative operations 严格前进、cumulative errors 不回退；window delta 必须与 cumulative delta reconcile，consecutive sequence 精确相等，skip sequence 至少 cover 最新 window。missing／malformed／stale／wrong-trial／regressing／changed／nonadvancing metrics 只允许明确 startup／heartbeat grace，之后 fail closed。以下四个 gate 彼此独立：

- live `window_p95_ms` 超过预先写下的 budget；
- `window_errors > 0` 或 cumulative `errors > 0`；
- free bytes `< 5419909120`；
- heartbeat／progression／identity 不合法。

任一 breach 都先 atomically 写 abort signal。chunked 最多完成当下 in-flight query／part，并在下一 fetch 前持久化 `ABORTED`。buffered 没有 batch boundary：controller 必须从 state 读取 sanitized numeric `connection_id`，用独立 admin connection 发 `KILL QUERY`，需要时 terminate child，再写 external `ABORTED` evidence。Task 10 timing 前必须用两个 disposable connections 执行 KILL preflight，要求 target query 得到预期 interruption，确认权限与 cleanup 后才进入矩阵。

controller 只接受 stdout/stderr 合计 **一个** structured JSON object，并与 return code、state、result、artifact 做 reconcile。只有 child=`SUCCEEDED`、rc=`0`、runner manifest-linked fast path 再调用成功，controller 才能成功；child=`ABORTED` 即使 rc=`0` 仍是 `ABORTED`。missing／malformed／multiple／contradictory JSON、未启动 export、zero-work OLTP 都是 `FAILED`。gate breach 后，若 child 尚未完成则 persist incomplete checkpoint 为 `ABORTED`；若内部 state 已真正 atomic `SUCCEEDED`，保留它并记录 `persisted_state_status=SUCCEEDED`，但 controller evidence 仍是 `ABORTED`，绝不列入 performance sample。

此外，出现下列条件也 invalidates trial 并停止后续同组 trial：

- MySQL container／process restart 或 health 不再通过；
- artifact row、cursor、distinct key、aggregate 或 SHA fingerprint diverge。

停止不是“删掉失败数据再重跑”。要保留 run ID、job directory manifest、accepted windows、child stdout/stderr、controller evidence、status delta 与 error，先判定 query／format／snapshot／resource 哪层失败。`ABORTED` 与 planned-resume correctness runs 永远不参与 steady-state throughput 排名。

### Task 10 freeze 与 teardown boundary

Task 10 在 seed 与 source baseline fingerprint 后建立六个 freeze triggers，分别拒绝 `report_order`／`report_item` 的 INSERT、UPDATE、DELETE；先执行 backdated INSERT、UPDATE、DELETE negative probes 并确认都被拒绝，矩阵期间只写 `oltp_probe`。最后一个 resumed artifact 和 external audit 完成后，再取 post fingerprint；只有它与 baseline 相同，才能 teardown freeze triggers。中断重跑要先执行明确的 `DROP TRIGGER IF EXISTS` recovery block，再重新 seed／fingerprint／freeze；Task 9 不留下 runtime artifact，Task 10 的 verified teardown 和 Task 11 的 database drop 才拥有清理边界。

Freeze fingerprint 只包含 immutable `report_order`／`report_item` membership 与 values，绝不能把 expected-mutable `oltp_probe.counter` sum 混进 source equality。矩阵前另存 probe table 的 ordered column／index schema 与 exact row count；每组后及 trigger teardown 前后重验这两个 invariants，并独立记录 counter sum。使用以下 canonical audit split，让 advanced counter 成为负载确实执行的 evidence，而不是 false source-divergence failure：

```python
TASK10_REPORT_SOURCE_FIELDS = (
    "orders",
    "min_cursor",
    "high_cursor",
    "order_crc32_sum",
    "items",
    "item_orders",
    "item_crc32_sum",
    "min_items_per_order",
    "max_items_per_order",
    "report_rows",
    "total_amount_fingerprint",
    "item_count_fingerprint",
)


def audit_task10_freeze(
    seed_manifest: dict,
    current_manifest: dict,
    seed_probe_schema,
    current_probe_schema,
) -> dict:
    seed_source = {
        field: seed_manifest[field] for field in TASK10_REPORT_SOURCE_FIELDS
    }
    current_source = {
        field: current_manifest[field] for field in TASK10_REPORT_SOURCE_FIELDS
    }
    if current_source != seed_source:
        raise RuntimeError("report source fingerprint changed")

    seed_probe_rows = seed_manifest.get("probes")
    current_probe_rows = current_manifest.get("probes")
    if (
        isinstance(seed_probe_rows, bool)
        or not isinstance(seed_probe_rows, int)
        or seed_probe_rows != 10000
        or current_probe_rows != seed_probe_rows
    ):
        raise RuntimeError("oltp_probe row count changed")
    if (
        not isinstance(seed_probe_schema, (list, tuple))
        or not seed_probe_schema
        or current_probe_schema != seed_probe_schema
    ):
        raise RuntimeError("oltp_probe schema changed")

    counter_before = seed_manifest.get("probe_counter_sum")
    counter_after = current_manifest.get("probe_counter_sum")
    if (
        isinstance(counter_before, bool)
        or not isinstance(counter_before, int)
        or counter_before < 0
        or isinstance(counter_after, bool)
        or not isinstance(counter_after, int)
        or counter_after < counter_before
    ):
        raise RuntimeError("oltp_probe counter evidence is invalid")
    return {
        "source_matches_baseline": True,
        "oltp_probe": {
            "rows": current_probe_rows,
            "counter_sum_before": counter_before,
            "counter_sum_after": counter_after,
            "counter_advanced": counter_after > counter_before,
            "schema_matches": True,
        },
    }
```

Controlled-stop audit 在 drop exactly six freeze triggers 前后都调用该 helper。report source、probe row-count 或 probe schema divergence 均 fail closed；mutable counter sum 不与 seed zero 做 report-source equality。

## 预期，不是假装实测

Task 10 执行前只允许写下这些 hypotheses：

- buffered control 应占用一个 connection，并因 client 端保存全部 result 而有较高 max RSS；
- chunking／sleep 应把 client buffer 限定在 batch、提供 checkpoint 并降低 burst，但 completion time 可能更长；
- 两种 export 对 OLTP latency 的精确差值未知；
- shared replica 可以把部分 read CPU／I/O 从 Primary 移走，但 export 会与 replication applier 竞争 capacity；
- replica result 受 receive／apply lag 与 snapshot 时点约束，`Seconds_Behind_Source=0` 在慢 network 下也可能漏掉 receiver lag，不能单独作为 high watermark 已可见的证明。[ch09 replica lag owner](../09-replication-and-ha/README.md)、[SHOW REPLICA STATUS](https://dev.mysql.com/doc/refman/8.0/en/show-replica-status.html)
- 长 MVCC transaction 能提供 snapshot，但它会保留 undo／推高 purge 成本，不是免费方案。

Connector implementation 是 measured boundary。每个 accepted control／export observation 都包含 pinned pure-Python client 的 CPU、scheduler 与 serialization cost，不能称为 MySQL-only capacity，也不能外推成 C Extension result。曾观察到的 default C Extension 四-thread exit 139 只作为 excluded client/environment crash boundary；mandatory pure-mode smoke 只决定本 runtime 是否有资格进入 matrix，不是 performance sample。

## Production topology：放在哪里

| Tier | 何时可选 | 隔离收益 | 不能忽略的代价 |
|---|---|---|---|
| Primary | 小结果、低频、极低 staleness budget，且容量 gate 证明安全 | 没有 replica visibility gap | 与 OLTP 共用 CPU／I/O／buffer pool；最严格 P95 stop gate |
| Shared replica | 允许 lag，且 export 偶发、replica 有明确余量 | 隔离部分 Primary read load | 与 applier／线上读竞争；lag 与 high watermark visibility 必须验证 |
| Dedicated reporting replica | 报表稳定、频繁，愿意付独立容量 | 把报表与 Primary／serving replica 分开 | 仍有 replication lag、长 query、snapshot、故障与扩容成本 |
| Analytical store | 大量聚合、历史 as-of、宽表／列式扫描 | OLTP 与 analytical execution 解耦 | CDC latency、schema evolution、reconciliation 与 rebuild runbook |

Replica 不是 correctness shortcut。要先定义“watermark 在该 replica 已 apply”如何证明，再在它上面捕获 snapshot；否则只是把旧资料更快地导出。analytical store 也不是双写后自动一致，必须有 source position、reconciliation 与 rebuild。

### Backpressure、发布与 consumer contract

- producer 的 batch size／sleep 是数据库侧 pressure valve；consumer 的 download rate 不能反向让一个 DB cursor 无限期打开。
- DB read、part materialization、artifact publish、object storage upload 应是分开的 state transition。
- 发布用 immutable artifact key 或 versioned manifest；同一个 job ID 只允许一个 canonical success artifact。
- consumer 只读取 success manifest 指向的 checksum／size，不扫 job directory 猜“最大文件就是完成”。
- rollback 不是把已下载 bytes 收回，而是撤销 manifest／停止分发，再以新 job 重建并发布新 version。

## 面试回答

### 30 秒

> 我先把它定义成 async job，并确认 membership／value 的一致性要求、staleness 与 OLTP budget。只有 `(created_at,id)` immutable 且 insertion-monotone，或 membership 已 materialize／snapshot，high watermark 才是完整边界；否则 backdated insert 或 update/delete 会破坏 resume correctness。执行用 keyset chunks、bounded buffer、manifest checkpoint 与 verified atomic artifact。manifest 证明内部构造完整，Task 10 另做 buffered／chunked／resumed SHA、distinct key 和业务 aggregate audit；live OLTP P95／error／heartbeat 与 `5,419,909,120` bytes disk gate 任一失守就 fail closed／ABORTED。

### 3–5 分钟

> 我把问题拆成 consistency、placement、execution、publish 四层。consistency 先区分 membership boundary 和 value snapshot：high watermark 只是 query upper bound；若 key 不是 insertion-monotone，后来 backdated／in-bound insert 仍可能在 resume 的新 ReadView 出现。即使 membership 固定，上界内 row 的 update/delete 也不会被 tuple 冻结。production 因而要 immutable monotone keys、materialized membership、versioned history、database/replica snapshot、CDC versioned read model、warehouse snapshot，或明确承担 undo/purge 成本的 bounded RR transaction。
>
> execution 不用深 offset，而按唯一 `(created_at,id)` keyset 取 batch。每批 canonical TSV 写到 deterministic `.tmp`，fsync、rename 后才 append 含 rows／SHA／first-last cursor 的 checkpoint manifest；resume 先重验全部 part，拒绝 missing、same-line-count corruption、stale／gap／orphan。publish 只串接 ordered manifest，要求 expected rows 和 last=high；success fast path 再把 state/result/artifact/manifest exact bytes 对齐。这个内部 integrity 仍不替代独立的 distinct-key／aggregate business audit。
>
> placement 依 freshness 与 capacity 选：Primary correctness 简单但直接争用 OLTP；shared replica 隔离部分负载却与 applier 竞争且有 lag；频繁报表用 dedicated reporting replica；复杂历史聚合通常进 analytical store，但 CDC 必须能 reconcile/rebuild。consumer backpressure 不应该让 DB cursor 长时间打开，数据库读取与 artifact delivery 要解耦。
>
> recovery 要说清 ambiguity：`ABORTED` 有 checkpoint 可 resume；artifact publish 前不对外可见；success 后走 manifest-linked validation。验证上先跑三次 OLTP control，写下 `1.5 × median P95` 预算，再跑 buffered／chunked 各三次；controller 只有看见五个 advancing、nonempty、same-trial one-second windows 才启动 export，持续检查 P95、window/cumulative errors、heartbeat progression 与 `2×artifact+5GiB` disk reserve。chunked 在 batch boundary abort；buffered 以经过权限 preflight 的 `KILL QUERY` 加 child termination。任何 `ABORTED`、restart 或 fingerprint divergence 都保留现场但不排名。

## 常见追问

**为什么不直接 `LIMIT offset,n`？**

offset 越深，前面越多 row 被扫描后丢弃；这里复用 ch08 keyset，以 last unique tuple 直接定位下一批。

**chunked 是否自动得到同一个跨批 snapshot？**

不是由 “chunked” 三个字保证。本 runner 在 Connector default autocommit off + RR 时同 invocation 复用 ReadView，但 resume 会换 snapshot，而且长 transaction 有 purge 成本；非 monotone key 的 backdated insert 也能进入新 snapshot。production 必须显式选择 membership boundary 与 value version source。

**为什么不把 result stream 直接传给 HTTP client？**

client 慢或断线会把 DB resource lifetime 绑在 network backpressure 上，也没有稳定 checkpoint／publish boundary。async artifact 把数据库读取与下载解耦。

**为什么 buffered 还要跑？**

它是 one-shot control：证明相同 query boundary 与 canonical formatting，也量 client peak RSS；不是“跑得过 S 就推荐千万级 buffered”。

**replica 没有拖慢 Primary，所以一定安全？**

不一定。replica 会与 applier 争 CPU／I/O，可能扩大 lag；而 `Seconds_Behind_Source` 不是所有 network／MTS 情况下的精确 freshness proof。要有 apply position／heartbeat、capacity 与 stop gate。

**如何证明 resume 没重复？**

manifest 的 deterministic part number、hash、cursor contiguity 与 exact concatenation 先证明内部构造；Task 10 仍要以 `100000 rows + distinct order id + high/last cursor + aggregate + buffered/chunked/resumed identical SHA` 做外部 audit，不能只看 state 变绿。

**如果 crash 恰好发生在 publish 附近？**

artifact 先写 `.tmp` 后 replace，result 再写，最后 state 才 `SUCCEEDED`。process crash 前 state 未成功就按 checkpoint 重跑；若要证明 host power-loss durability，还要对 parent directory fsync 并做 fault injection，本 lab 没有这项证据。

## Task 10 待填证据

当前状态保持 `READY_UNRUN`。Task 10 必须补齐：

- environment／MySQL version／transaction isolation／durability／host resources；
- run IDs、source manifest 与 predeclared numeric P95 budget；
- control／buffered／chunked 各三次原始结果、median 与 range；
- processlist、temporary／sort、InnoDB history delta；
- freeze triggers、backdated INSERT／UPDATE／DELETE rejection、pre/post source fingerprint 与 verified teardown；
- immutable report-source equality，以及另行审计且不回退的 `oltp_probe` row count／ordered schema／counter sum；
- two-connection `KILL QUERY` privilege preflight、五个 advancing 1 秒 OLTP windows、所有 accepted live metrics 与 controller evidence；
- strict nonregressing `drain_limit_hits`／`max_heartbeat_lateness_ms`，以及 stale `ABORTED` 的 coherent raw document／age／mtime／device／inode／size／tracker evidence；
- Python/platform、Connector version、`threadsafety`、`HAVE_CEXT`、requested／actual implementation、四个 distinct verifiably closed worker connections；
- mandatory `oltp-smoke-1` 的 excluded result、exact runtime／runner SHA／non-secret connection binding，以及 C Extension native-crash excluded boundary；
- numeric disk gate：`2 * 100000 * 256 + 5 * 1024^3 = 5419909120` bytes；
- 所有 artifact equality；
- `ABORTED` 三 parts 到同 job resume 的 timeline；
- expected-vs-actual；
- observed S fact、scaled trend、mutable reasoning、topology reasoning 与 untested production capacity 的明确分层。
- 明示所有 accepted latency／capacity 含 pure-Python Connector cost，不是 MySQL-only 或 C Extension capacity。
