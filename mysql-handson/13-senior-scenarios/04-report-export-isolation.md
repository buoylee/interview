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
├─ 否：固定 high watermark，资料 immutable 或接受期间 value 漂移
│  └─ async job + keyset chunks + bounded part + checkpoint + atomic publish
└─ 是：watermark 内是否仍会 UPDATE／DELETE？
   ├─ 否：固定 high watermark 即可定义 membership
   └─ 是：必须另选真正的 version source
      ├─ versioned history / temporal model
      ├─ database 或 replica snapshot
      ├─ CDC-built versioned read model
      ├─ analytical snapshot
      └─ 有明确 undo／purge budget 的 bounded MVCC snapshot
```

**硬边界**：`(created_at,id)` high watermark 只排除 watermark 之后的 INSERT，也就是固定 membership 的上界；它不能冻结上界内 row 的 UPDATE／DELETE。mutable row 的 as-of correctness 必须来自 versioned history、数据库／replica snapshot、CDC 构建的 versioned read model、analytical snapshot，或明确接受 undo／purge 成本的 bounded MVCC snapshot。

InnoDB 在 RR 下的普通 consistent read 会在同一 transaction 复用第一条一致性读建立的 snapshot；RC 则每条一致性读建立新 snapshot。长时间持有 RR ReadView 会让仍被它需要的 undo 版本不能 purge，使 `History list length` 上升。因此，“一个长 transaction 就能得到快照”是正确性工具，不是免费的隔离工具。见 [ch05 snapshot／长事务 owner](../05-mvcc-and-transaction/README.md)、[MySQL 8.0 consistent nonlocking reads](https://dev.mysql.com/doc/refman/8.0/en/innodb-consistent-read.html)、[transaction isolation levels](https://dev.mysql.com/doc/refman/8.0/en/innodb-transaction-isolation-levels.html) 与 [purge configuration](https://dev.mysql.com/doc/refman/8.0/en/innodb-purge-configuration.html)。

### Baseline 决策

本场景选择：

- async job，不让 HTTP connection 承担千万行传输；
- job 建立时捕获固定 high watermark；
- S 级资料在实验期间 immutable，因此 watermark 足以固定 membership；
- chunked mode 用 `(created_at,id)` keyset，不使用 offset；
- 每批写 deterministic part，part rename 后才推进 checkpoint；
- 所有 part 完成后才生成并原子发布 `artifact.tsv`；
- OLTP probe、fingerprint、disk reserve、MySQL health 是停止条件，不是事后说明；
- buffered one-shot 只作 control，不是生产默认答案。

## 固定 S 级 schema、seed 与查询顺序

Task 10 只能按这里的顺序建立资料：先三张表，再 `seed_digit`，再 `report_order`，再 `report_item`，drop helper，最后 `oltp_probe`。资料量固定为 `100000` orders、每单恰好三项（`300000` items）与 `10000` probe rows。

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
  "high_created_at": "2026-01-02 03:46:40.000000",
  "high_id": 100000,
  "last_created_at": "1970-01-01 00:00:00.000000",
  "last_id": 0,
  "next_part": 1,
  "rows_written": 0,
  "status": "RUNNING"
}
```

上面的 `"run-id"` 是语义占位值。下方 canonical code 不改字段，但以 `job_dir.name` 写值；因此 CLI 路径若为 `job-run-id`，实际 `job_id` 是 `"job-run-id"`。consumer 不得自行去掉 `job-` 前缀。

Artifact 不变式：

1. 每个 part 先写为 `.tmp`，`flush`／`fsync` 后用 `os.replace()` 原子 rename。
2. checkpoint 只在 part rename 之后推进。
3. 若 process 在 part rename 后、checkpoint 前中断，resume 会以同一 old cursor 重取同一批，并覆写同一 deterministic part number；S 级 immutable dataset 下不会把同一批 append 两次。
4. final publish 依 part number 排序串接到 `artifact.tsv.tmp`，计算 row count 与 SHA-256，row count 等于 checkpoint 后才 `os.replace()` 为 `artifact.tsv`。
5. `ABORTED` 保留 `state.json` 与 parts；`SUCCEEDED` 的正常 transition 顺序是 artifact → `result.json` → state status。
6. reader 只接受 `state.status=SUCCEEDED`、`result.json` 和 `artifact.tsv` 同时存在的 job；绝不把 `.tmp` 或单个 part 当完整报表。

这里证明的是 **process-level interruption／resume**。文件内容在 rename 前有 `fsync`，但 code 没有对 parent directory 做 `fsync`，所以不宣称 host power-loss 后 directory entry 一定 durable。fresh job directory 是矩阵前提；runner 不负责清理外部注入的 stale extra parts，也不把磁盘 corruption 自动修复成成功。

## Canonical `export_runner.py`

CLI interface 固定：

```text
--mode buffered|chunked|oltp
--job-dir /private/tmp/mysql-senior-scenarios.<suffix>/job-<run-id>
--batch-size 1000
--sleep-ms 20
--max-batches 0
--duration-seconds 60
--threads 4
--host 127.0.0.1 --port 3306 --user root --password root
```

Task 10 从下方唯一 Python fence 原样物化到 `$MYSQL_SCENARIO_RUN_DIR/export_runner.py`。`job_dir.resolve()` 必须是 `/private/tmp/mysql-senior-scenarios.*` 的 immediate `job-*` child；export data value 全部 parameterized；buffered 与 chunked 使用相同字段次序与 canonical TSV formatting。

```python
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import random
import resource
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import mysql.connector


EPOCH = "1970-01-01 00:00:00.000000"
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


def timestamp_text(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S.%f")
    return str(value)


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


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


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


def max_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def publish(job_dir: Path, expected_rows: int) -> tuple[int, str]:
    artifact = job_dir / "artifact.tsv"
    temporary = job_dir / "artifact.tsv.tmp"
    digest = hashlib.sha256()
    rows = 0
    with temporary.open("wb") as output:
        for part in sorted((job_dir / "parts").glob("part-*.tsv")):
            with part.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(chunk)
                    digest.update(chunk)
                    rows += chunk.count(b"\n")
        output.flush()
        os.fsync(output.fileno())
    if rows != expected_rows:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"artifact rows {rows} != checkpoint rows {expected_rows}")
    os.replace(temporary, artifact)
    return rows, digest.hexdigest()


def run_chunked(
    connection,
    job_dir: Path,
    batch_size: int,
    sleep_ms: int,
    max_batches: int,
) -> dict:
    state_path = job_dir / "state.json"
    result_path = job_dir / "result.json"
    cursor = connection.cursor()
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state["status"] == "SUCCEEDED":
            return json.loads(result_path.read_text(encoding="utf-8"))
        state["status"] = "RUNNING"
    else:
        high_created_at, high_id = capture_high_watermark(cursor)
        state = {
            "job_id": job_dir.name,
            "high_created_at": high_created_at,
            "high_id": high_id,
            "last_created_at": EPOCH,
            "last_id": 0,
            "next_part": 1,
            "rows_written": 0,
            "status": "RUNNING",
        }
    atomic_json(state_path, state)
    started = time.perf_counter()
    batches_this_run = 0
    while True:
        rows = fetch_batch(
            cursor,
            (state["last_created_at"], int(state["last_id"])),
            (state["high_created_at"], int(state["high_id"])),
            batch_size,
        )
        if not rows:
            artifact_rows, artifact_sha256 = publish(
                job_dir, int(state["rows_written"])
            )
            elapsed = time.perf_counter() - started
            result = {
                "status": "SUCCEEDED",
                "mode": "chunked",
                "rows": artifact_rows,
                "sha256": artifact_sha256,
                "seconds": elapsed,
                "rows_per_second": artifact_rows / elapsed,
                "max_rss_bytes": max_rss_bytes(),
                "high_cursor": [state["high_created_at"], state["high_id"]],
                "last_cursor": [state["last_created_at"], state["last_id"]],
                "parts": int(state["next_part"]) - 1,
            }
            atomic_json(result_path, result)
            state["status"] = "SUCCEEDED"
            atomic_json(state_path, state)
            cursor.close()
            return result

        part_number = int(state["next_part"])
        part_path = job_dir / "parts" / f"part-{part_number:06d}.tsv"
        part_rows, _ = write_part(part_path, rows)
        last = rows[-1]
        state["last_created_at"] = timestamp_text(last[0])
        state["last_id"] = int(last[1])
        state["next_part"] = part_number + 1
        state["rows_written"] = int(state["rows_written"]) + part_rows
        atomic_json(state_path, state)
        batches_this_run += 1
        if max_batches and batches_this_run >= max_batches:
            state["status"] = "ABORTED"
            atomic_json(state_path, state)
            elapsed = time.perf_counter() - started
            result = {
                "status": "ABORTED",
                "mode": "chunked",
                "rows": state["rows_written"],
                "seconds": elapsed,
                "rows_per_second": state["rows_written"] / elapsed,
                "max_rss_bytes": max_rss_bytes(),
                "high_cursor": [state["high_created_at"], state["high_id"]],
                "last_cursor": [state["last_created_at"], state["last_id"]],
                "parts": int(state["next_part"]) - 1,
            }
            cursor.close()
            return result
        if sleep_ms:
            time.sleep(sleep_ms / 1000)


def run_buffered(connection, job_dir: Path) -> dict:
    job_dir.mkdir(parents=True, exist_ok=False)
    cursor = connection.cursor(buffered=True)
    high = capture_high_watermark(cursor)
    started = time.perf_counter()
    cursor.execute(BUFFERED_SQL, (EPOCH, 0, *high))
    rows = list(cursor.fetchall())
    artifact_rows, artifact_sha256 = write_part(
        job_dir / "artifact.tsv", rows
    )
    cursor.close()
    elapsed = time.perf_counter() - started
    result = {
        "status": "SUCCEEDED",
        "mode": "buffered",
        "rows": artifact_rows,
        "sha256": artifact_sha256,
        "seconds": elapsed,
        "rows_per_second": artifact_rows / elapsed,
        "max_rss_bytes": max_rss_bytes(),
        "high_cursor": [high[0], high[1]],
        "last_cursor": [timestamp_text(rows[-1][0]), int(rows[-1][1])],
    }
    atomic_json(job_dir / "result.json", result)
    atomic_json(job_dir / "state.json", {
        "job_id": job_dir.name,
        "high_created_at": high[0],
        "high_id": high[1],
        "last_created_at": result["last_cursor"][0],
        "last_id": result["last_cursor"][1],
        "next_part": 1,
        "rows_written": artifact_rows,
        "status": "SUCCEEDED",
    })
    return result


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def oltp_worker(config: dict, duration: int, seed: int) -> tuple[list[float], int]:
    connection = mysql.connector.connect(**config)
    connection.autocommit = True
    cursor = connection.cursor()
    randomizer = random.Random(seed)
    deadline = time.perf_counter() + duration
    latencies: list[float] = []
    errors = 0
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
            latencies.append((time.perf_counter_ns() - started) / 1_000_000)
        except Exception:
            errors += 1
    cursor.close()
    connection.close()
    return latencies, errors


def run_oltp(config: dict, duration: int, threads: int) -> dict:
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as pool:
        results = list(
            pool.map(
                lambda seed: oltp_worker(config, duration, seed),
                range(1, threads + 1),
            )
        )
    latencies = [value for values, _ in results for value in values]
    errors = sum(error_count for _, error_count in results)
    return {
        "status": "SUCCEEDED" if errors == 0 else "FAILED",
        "mode": "oltp",
        "operations": len(latencies),
        "errors": errors,
        "p50_ms": percentile(latencies, 0.50),
        "p95_ms": percentile(latencies, 0.95),
        "p99_ms": percentile(latencies, 0.99),
    }


def validated_job_dir(path: Path) -> Path:
    resolved = path.resolve()
    private_tmp = Path("/private/tmp").resolve()
    runtime_root = resolved.parent
    if (
        runtime_root.parent != private_tmp
        or not runtime_root.name.startswith("mysql-senior-scenarios.")
        or not resolved.name.startswith("job-")
    ):
        raise ValueError("job directory is outside the allowed runtime prefix")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("buffered", "chunked", "oltp"), required=True)
    parser.add_argument("--job-dir", type=Path)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--sleep-ms", type=int, default=20)
    parser.add_argument("--max-batches", type=int, default=0)
    parser.add_argument("--duration-seconds", type=int, default=60)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    if not 1 <= args.batch_size <= 5000:
        raise SystemExit("--batch-size must be in 1..5000")
    if not 0 <= args.sleep_ms <= 1000:
        raise SystemExit("--sleep-ms must be in 0..1000")
    if not 1 <= args.threads <= 16:
        raise SystemExit("--threads must be in 1..16")
    if args.duration_seconds < 1 or args.max_batches < 0:
        raise SystemExit("duration must be positive and max-batches nonnegative")

    config = {
        "host": args.host,
        "port": args.port,
        "user": args.user,
        "password": args.password,
        "database": "mysql_senior_scenarios",
    }
    try:
        if args.mode == "oltp":
            result = run_oltp(config, args.duration_seconds, args.threads)
        else:
            if args.job_dir is None:
                raise ValueError("--job-dir is required for export modes")
            job_dir = validated_job_dir(args.job_dir)
            connection = mysql.connector.connect(**config)
            if args.mode == "buffered":
                result = run_buffered(connection, job_dir)
            else:
                job_dir.mkdir(parents=True, exist_ok=True)
                result = run_chunked(
                    connection,
                    job_dir,
                    args.batch_size,
                    args.sleep_ms,
                    args.max_batches,
                )
            connection.close()
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] in ("SUCCEEDED", "ABORTED") else 2
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
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
- process resume 会建立新 connection，因此也是新 transaction／ReadView。high watermark 仍固定 membership 上界，但 mutable row 的 value 可能跨 resume 改变；这正是前面“一致性硬边界”的原因。
- `cursor(buffered=True)` 在 execute 后会把整个 result set 拉到 client 并 buffer，适合这里的 one-shot control，不适合把千万级 result 当默认生产路径。nonbuffered cursor 在调用 fetch method 时取 row，而且同一 connection 发下一条 statement 前必须消费完 result；本 runner 的 `fetch_batch()` 仍会 `fetchall()`，但每次只 materialize `batch_size <= 5000`。[Connector/Python buffered cursor](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlcursorbuffered.html)
- 不要把 Connector/Python 的 nonbuffered cursor 直接称为“不会物化的 MySQL server-side cursor”。MySQL 真正的 server-side cursor 会 materialize 到 internal temporary table，大 result 仍可能慢。[MySQL server-side cursor restrictions](https://dev.mysql.com/doc/mysql-reslimits-excerpt/8.0/en/cursor-restrictions.html)
- `max_rss_bytes` 是 process lifetime 的 peak RSS，不是某个 batch 的瞬时用量；三次 trial 必须各起新 process 才可比较。
- resumed success 的 `rows` 是累计 artifact rows，但 `seconds` 只计算当前 invocation，故 `rows_per_second = cumulative rows / current invocation seconds`。它可验证 resume 路径有输出字段，**不可**用作 resumed job 的端到端 throughput；端到端值应以第一次启动至成功的外部 wall clock 另算。
- `publish()` 会读取 job 中所有 `part-*.tsv`。矩阵每次必须使用 fresh job directory，resume 只能复用该次 ABORTED job；runner 不自动 reconcile 人工放入的 orphan／stale part。
- 正常成功写入次序是 artifact → result → state。process crash 在 state 变成 `SUCCEEDED` 前可以按同一 checkpoint 重跑；但 `SUCCEEDED` fast path 只读取 existing `result.json`，不会重新 hash artifact，因此外部删除、bit rot 或人工篡改要由 artifact audit 发现，不能假称 runner 会自动修复。
- buffered mode 假设来源非空；`capture_high_watermark()` 会明确拒绝 empty `report_order`。chunked publish 可以处理 `rows_written=0` 的 checkpoint，但固定 S seed 本身不是 empty-data test。
- canonical parser 把不合法 JSON／缺字段视为 `FAILED`；它不是 state migration／repair tool。生产系统应给 state schema version、ownership、ACL、retention 和 reconciliation 独立设计。
- `argparse` 与 numeric range validation 位于 runner 的 structured-error `try` 之外；参数错误会以 argparse／`SystemExit` stderr 退出，不保证输出 result JSON。Task 10 只使用已验证的合法参数，production wrapper 若要求“任何失败都一个 JSON”，还要统一 error envelope。

这些限制没有改变 S 级实验的安全性：Task 10 使用 fresh job directory、immutable `report_order`／`report_item`，且 interrupted resume 只作 correctness evidence，不拿 resumed throughput 作性能结论。它们也意味着不能把 S 级结果外推为 mutable production export 已经正确。

## OLTP probe 与三次矩阵

`--mode oltp` 的每个 operation 是随机 primary-key `SELECT counter` 加一个 autocommit `UPDATE counter=counter+1`。它报告成功 operation count、compound operation 的 p50／p95／p99 与 error count。probe 是干扰量尺，不是业务 workload 的替身。

每组必须跑三次，每个 export trial 使用 fresh job directory：

| Group | OLTP probe | Export |
|---|---|---|
| control | 60 s，4 threads | none |
| buffered | 60 s，4 threads | one buffered query／artifact |
| chunked | 60 s，4 threads | `batch=1000`、`sleep=20 ms` |

执行顺序固定：

1. 先独立跑三次 control，要求三次 `errors=0`。
2. 以三次 control P95 的 median 定义预算：`OLTP_P95_BUDGET = 1.50 × median(control P95)`；必须在 export 前写下数字。
3. 每个 concurrent trial 先启动 OLTP，五秒后才启动 export。
4. export 前后各 capture MySQL status；OLTP 与 export 都结束后才归档两个 JSON、state 与 artifact manifest。
5. 同组后续 trial 是否继续，由停止条件决定，不可跑完后才补一个预算。

### 每次要记录的证据

OLTP JSON：

```text
operations, p50_ms, p95_ms, p99_ms, errors, status
```

Export JSON：

```text
status, rows, sha256, seconds, rows_per_second, max_rss_bytes,
high_cursor, last_cursor, parts（chunked）
```

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
  --mode chunked --job-dir "$MYSQL_SCENARIO_RUN_DIR/job-resume" \
  --batch-size 1000 --sleep-ms 20 --max-batches 3 \
  --host 127.0.0.1 --port 3306 --user root --password root
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
  --mode chunked --job-dir "$MYSQL_SCENARIO_RUN_DIR/job-resume" \
  --batch-size 1000 --sleep-ms 20 --max-batches 0 \
  --host 127.0.0.1 --port 3306 --user root --password root
```

第二次必须成为 `SUCCEEDED`，final artifact 无 duplicate／missing，SHA 与 fresh buffered／chunked 相同。这个步骤验证 ABORTED → resume → SUCCEEDED 的 process-level state machine；没有注入 “rename 后、checkpoint 前” 的精确 crash point，也没有模拟 host power loss，所以不能把这两项写成 observed fact。

### 停止条件

出现任一条件就停止**新的 batch／后续 trial**，保存现场：

- OLTP P95 超过预先写下的 budget；
- OLTP 或 export `errors > 0`／status=`FAILED`；
- disk free reserve 跌破 preflight gate；
- MySQL container／process restart 或 health 不再通过；
- artifact row、cursor、distinct key、aggregate 或 SHA fingerprint diverge。

停止不是“删掉失败数据再重跑”。要保留 run ID、job directory manifest、JSON、status delta 与 error，先判定是 query／format／snapshot／resource 哪一层失败。

## 预期，不是假装实测

Task 10 执行前只允许写下这些 hypotheses：

- buffered control 应占用一个 connection，并因 client 端保存全部 result 而有较高 max RSS；
- chunking／sleep 应把 client buffer 限定在 batch、提供 checkpoint 并降低 burst，但 completion time 可能更长；
- 两种 export 对 OLTP latency 的精确差值未知；
- shared replica 可以把部分 read CPU／I/O 从 Primary 移走，但 export 会与 replication applier 竞争 capacity；
- replica result 受 receive／apply lag 与 snapshot 时点约束，`Seconds_Behind_Source=0` 在慢 network 下也可能漏掉 receiver lag，不能单独作为 high watermark 已可见的证明。[ch09 replica lag owner](../09-replication-and-ha/README.md)、[SHOW REPLICA STATUS](https://dev.mysql.com/doc/refman/8.0/en/show-replica-status.html)
- 长 MVCC transaction 能提供 snapshot，但它会保留 undo／推高 purge 成本，不是免费方案。

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

> 我先确认这是 async job 还是同步响应、资料在导出期间会不会更新，以及能接受多少 replica lag。baseline 是在 job 建立时固定 `(created_at,id)` high watermark，用 keyset 分批 JOIN，每批只保留 bounded buffer，先 fsync／rename deterministic part，再推进 checkpoint；全部完成后校验 row、distinct key、aggregate 与 SHA，最后 atomic publish。watermark 只固定 membership，不冻结更新删除；mutable as-of 要版本历史或真正 snapshot。运行前写死 OLTP P95、error、disk、MySQL health 与 fingerprint gate，任何一项失败就 ABORTED／停止新 batch。

### 3–5 分钟

> 我把问题拆成 consistency、placement、execution、publish 四层。consistency 先区分 membership boundary 和 value snapshot：high watermark 能排除后来 insert，但上界内 row 若会 update/delete，它不是 as-of snapshot；这时要 versioned history、snapshot、CDC versioned read model、warehouse snapshot，或明确承担 undo/purge 成本的 bounded RR transaction。
>
> execution 不用深 offset，而按唯一 `(created_at,id)` keyset 取 batch。每批 canonical TSV 写到 deterministic `.tmp`，fsync、rename 后才 checkpoint；中断若发生在 rename 与 checkpoint 间，immutable source 下 resume 会覆写同一 part，不会 append duplicate。所有 parts 结束后串接临时 artifact，同时验 row count 与 SHA，再 atomic publish；reader 只认 success state、manifest 和 artifact 三者齐全。
>
> placement 依 freshness 与 capacity 选：Primary correctness 简单但直接争用 OLTP；shared replica 隔离部分负载却与 applier 竞争且有 lag；频繁报表用 dedicated reporting replica；复杂历史聚合通常进 analytical store，但 CDC 必须能 reconcile/rebuild。consumer backpressure 不应该让 DB cursor 长时间打开，数据库读取与 artifact delivery 要解耦。
>
> recovery 要说清 ambiguity：`ABORTED` 有 checkpoint 可 resume；artifact publish 前不对外可见；success 后靠 immutable manifest 去重。验证上先跑三次 OLTP control，写下 `1.5 × median P95` 预算，再跑 buffered／chunked 各三次；比较 P50/P95/P99/errors、elapsed、throughput、max RSS、temporary/sort delta，并要求所有 artifact 的 high/last cursor、distinct key、aggregate 与 SHA 完全一致。超预算、出错、MySQL restart、disk reserve 或 fingerprint 失败就停止，不拿错误 run 讲性能故事。

## 常见追问

**为什么不直接 `LIMIT offset,n`？**

offset 越深，前面越多 row 被扫描后丢弃；这里复用 ch08 keyset，以 last unique tuple 直接定位下一批。

**chunked 是否自动得到同一个跨批 snapshot？**

不是由 “chunked” 三个字保证。本 runner 在 Connector default autocommit off + RR 时同 invocation 复用 ReadView，但 resume 会换 snapshot，而且长 transaction 有 purge 成本。production 必须显式选择并验证 transaction／version source。

**为什么不把 result stream 直接传给 HTTP client？**

client 慢或断线会把 DB resource lifetime 绑在 network backpressure 上，也没有稳定 checkpoint／publish boundary。async artifact 把数据库读取与下载解耦。

**为什么 buffered 还要跑？**

它是 one-shot control：证明相同 query boundary 与 canonical formatting，也量 client peak RSS；不是“跑得过 S 就推荐千万级 buffered”。

**replica 没有拖慢 Primary，所以一定安全？**

不一定。replica 会与 applier 争 CPU／I/O，可能扩大 lag；而 `Seconds_Behind_Source` 不是所有 network／MTS 情况下的精确 freshness proof。要有 apply position／heartbeat、capacity 与 stop gate。

**如何证明 resume 没重复？**

deterministic part number 避免 append duplicate；最后仍要以 `100000 rows + distinct order id + high/last cursor + aggregate + identical SHA` 验证，不能只看 state 变绿。

**如果 crash 恰好发生在 publish 附近？**

artifact 先写 `.tmp` 后 replace，result 再写，最后 state 才 `SUCCEEDED`。process crash 前 state 未成功就按 checkpoint 重跑；若要证明 host power-loss durability，还要对 parent directory fsync 并做 fault injection，本 lab 没有这项证据。

## Task 10 待填证据

当前状态保持 `READY_UNRUN`。Task 10 必须补齐：

- environment／MySQL version／transaction isolation／durability／host resources；
- run IDs、source manifest 与 predeclared numeric P95 budget；
- control／buffered／chunked 各三次原始结果、median 与 range；
- processlist、temporary／sort、InnoDB history delta；
- 所有 artifact equality；
- `ABORTED` 三 parts 到同 job resume 的 timeline；
- expected-vs-actual；
- observed S fact、scaled trend、mutable reasoning、topology reasoning 与 untested production capacity 的明确分层。
