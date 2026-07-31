# 高效安全地导入 1,000 万行 TSV

| 结论／证据 | 等级 | 当前含义 |
|---|---|---|
| scenario、DDL、runner、验收与恢复契约已定义 | `READY_UNRUN` | 未运行 S／M／L；没有吞吐、速度比或正确性结果。 |
| 架构、机制与安全边界 | `REASONED` | 由 ch02／03／07／09／11 和官方文档推导。 |

## 陌生题目

「有一个 1,000 万行 TSV，要尽快导入 MySQL。你会怎么做，为什么，如何证明没有漏、重、错，失败后怎么继续？」

不要先回答 `LOAD DATA`。先收敛目标表是否为空／是否线上热表、档案能否信任及重建、索引与复制边界；快的 elapsed time 不是完成。

## 澄清树与完成标准

```text
target
├─ empty staging table → 可隔离导入，验证后 controlled publish
├─ empty final table   → 仍要定义发布窗口、失败回滚与读者可见性
└─ hot existing table  → 先定义写入竞争、merge 语义、节流与停机窗口
input
├─ location / trust / immutable? → LOCAL client transfer 或 server file read 的权限边界
└─ can regenerate? → manifest、run ID、batch identity 与 restart watermark 的来源
shape
├─ row width / secondary indexes
├─ unique / foreign keys / triggers / generated columns
└─ conversion、reject record 与重复资料的业务语义
operations
├─ allowed downtime / retry / reject handling / publish semantics
├─ binlog / replica / HA / allowed lag
└─ disk headroom / completion SLA / checkpoint identity
```

完成条件必须同时有：immutable input manifest、exact accepted／rejected counts、duplicate／missing 的解释、target table fingerprint、restart rule、publish boundary 及 rollback source。任何一项未知都不能以「导入完成」结案。

## 基准决策与跨章执行链

推荐 baseline（先以一个 worker 取得可解释的 S 级 control，再递增 batch size 与 concurrency）：

```text
immutable input + manifest
  → namespaced staging table
  → choose LOAD DATA or parameterized driver batches
  → increment batch size and concurrency from one worker
  → watch redo/checkpoint/binlog/replica and correctness
  → validate counts/fingerprint/rejects
  → controlled publish or merge
  → retain run ID and restart watermark
```

每一行的执行链是：source parse；若 `LOCAL` 则 client 读取并传给 server，非 `LOCAL` 则 server 从自身文件系统读取；类型转换、duplicate／constraint 检查；clustered B+ tree 与每棵 secondary B+ tree 修改；undo、redo、binlog；Buffer Pool 脏页、checkpoint 与 fsync；最后 replica receive、persist、apply。机制 owner 分别是 [ch02 page／buffer pool](../02-innodb-storage/README.md)、[ch03 index maintenance](../03-indexing/README.md)、[ch07 redo／binlog](../07-logs-and-crashsafe/README.md)、[ch09 replica apply](../09-replication-and-ha/README.md) 与 [ch11 operations boundaries](../11-ops-and-troubleshooting/README.md)；本页只组装，不复制长机制正文。

`LOAD DATA` 语法允许 `LOCAL`；有 `LOCAL` 时文件在 client host，由 client 传输，且 client 与 server 都必须允许它；无 `LOCAL` 时 server 直接读 server host 文件。`LOCAL` 也会改变错误处理，所以 reject／warning 不能省略。详见 [MySQL 8.0 LOAD DATA](https://dev.mysql.com/doc/refman/8.0/en/load-data.html)。`local_infile` 是可动态设置的 Global 变量，故本 runner 记录原值、仅在需要时开启、finally 恢复；这不是生产上永久开启它的建议，见 [local_infile variable](https://dev.mysql.com/doc/refman/8.0/en/server-system-variables.html#sysvar_local_infile)。

`LOAD DATA` 是文件形状兼容、且可隔离导入时的 baseline；需要应用验证／转换／checkpoint 时，parameterized `executemany()` batches 是 baseline；single-row autocommit 只是 control，不是推荐。Connector/Python 的 `executemany()` 是 parameterized driver batch，其 exact rewrite 必须在固定的 connector `9.7.0` 上复核，不能把它写成 server-side prepared statements 的证明；见 [Connector/Python executemany()](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlcursor-executemany.html)。

仅在 isolated、可重建且已有 disk／publish plan 的 table 才考虑重建 secondary indexes。global durability weakening、盲目关闭 foreign-key／unique checks、和对 hot table 移除 index 都不是默认方案。InnoDB 的 bulk-load 建议同样把这些优化放在已隔离、已知约束的前提下；见 [InnoDB bulk loading](https://dev.mysql.com/doc/refman/8.0/en/optimizing-innodb-bulk-data-loading.html)。binary log 记录数据变更并供 replicas 重放，bulk write 会消耗 binlog／replica apply 容量，必须测 lag 与保留空间，而不是把 binlog 当可随意关闭的开关；见 [binary log](https://dev.mysql.com/doc/refman/8.0/en/binary-log.html)。

## 同源 target 与 immutable TSV

以下 DDL 是三条路径唯一可比较的 target；三张表必须从空表开始且不共享同一张 target。

```sql
USE mysql_senior_scenarios;

CREATE TABLE bulk_template (
  id         BIGINT UNSIGNED NOT NULL,
  tenant_id  BIGINT UNSIGNED NOT NULL,
  status     TINYINT UNSIGNED NOT NULL,
  payload    VARCHAR(128) NOT NULL,
  created_at DATETIME(6) NOT NULL,
  PRIMARY KEY (id),
  KEY idx_tenant_created (tenant_id, created_at, id),
  CONSTRAINT chk_bulk_status CHECK (status IN (0,1,2,3))
) ENGINE=InnoDB;

CREATE TABLE bulk_single LIKE bulk_template;
CREATE TABLE bulk_batch  LIKE bulk_template;
CREATE TABLE bulk_load   LIKE bulk_template;
```

在每个 run 先生成确定性 input。生成时间不属于 load timing；runtime run directory 是运行资料，不提交为证据。只有它的 manifest 和 measured summary 才能进入 Markdown。

```bash
MYSQL_SCENARIO_ROWS=100000
MYSQL_SCENARIO_RUN_DIR=$(mktemp -d /private/tmp/mysql-senior-scenarios.XXXXXX)
LC_ALL=C awk -v rows="$MYSQL_SCENARIO_ROWS" 'BEGIN {
  OFS="\t";
  for (i=1; i<=rows; i++) {
    day=(i%28)+1;
    printf "%d\t%d\t%d\tpayload-%012d\t2026-01-%02d 12:00:00.000000\n",
           i, (i%1000)+1, i%4, i, day;
  }
}' > "$MYSQL_SCENARIO_RUN_DIR/input.tsv"
wc -l -c "$MYSQL_SCENARIO_RUN_DIR/input.tsv"
shasum -a 256 "$MYSQL_SCENARIO_RUN_DIR/input.tsv"
```

manifest 至少记录 `run_id`、tier、input absolute path、rows、bytes、SHA-256、generator command、DDL digest、MySQL／connector version、binlog／replica config 与开始时间。对同一 tier 的每条路径，SHA-256、rows、DDL、server config 必须一致；否则停止 throughput 比较。

## Canonical `bulk_runner.py`

Markdown block 是唯一 canonical source。运行时 extract 或 copy 到准确的 namespaced path `$MYSQL_SCENARIO_RUN_DIR/bulk_runner.py`；不新增 repository script。

```python
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import zlib
from datetime import datetime
from pathlib import Path
from typing import Iterable

import mysql.connector
from mysql.connector import Error as ConnectorError
from mysql.connector.errors import (
    InterfaceError,
    ReadTimeoutError,
    WriteTimeoutError,
)


ALLOWED_TABLES = {
    "single": "bulk_single",
    "batch": "bulk_batch",
    "load": "bulk_load",
}
INSERT_SQL = (
    "INSERT INTO `{table}` "
    "(id,tenant_id,status,payload,created_at) VALUES (%s,%s,%s,%s,%s)"
)
STATUS_NAMES = (
    "Innodb_os_log_written",
    "Innodb_data_written",
    "Bytes_received",
)
PHASES = {
    "VALIDATING",
    "BEFORE_SEND",
    "SESSION_SETTING",
    "GLOBAL_SETTING",
    "EXECUTING",
    "COMMITTING",
    "VERIFYING",
    "ROLLING_BACK",
    "RESTORING",
    "CLOSING",
    "VERIFIED",
}


class ContractError(Exception):
    pass


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ContractError(message)


def parse_row(fields: list[str]) -> tuple[int, int, int, str, str]:
    if len(fields) != 5:
        raise ValueError(f"expected 5 TSV fields, got {len(fields)}")
    row_id, tenant_id, status = map(int, fields[:3])
    payload, created_at = fields[3], fields[4]
    if row_id < 1 or tenant_id < 1 or status not in (0, 1, 2, 3):
        raise ValueError(f"invalid row values: {fields!r}")
    if "\t" in payload or "\n" in payload:
        raise ValueError("payload contains a TSV delimiter")
    try:
        parsed_created_at = datetime.strptime(
            created_at, "%Y-%m-%d %H:%M:%S.%f"
        )
    except ValueError as exc:
        raise ValueError("created_at must include microseconds") from exc
    return (
        row_id,
        tenant_id,
        status,
        payload,
        parsed_created_at.strftime("%Y-%m-%d %H:%M:%S.%f"),
    )


def iter_rows(path: Path) -> Iterable[tuple[int, int, int, str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for line_number, fields in enumerate(reader, start=1):
            try:
                yield parse_row(fields)
            except Exception as exc:
                raise ValueError(f"line {line_number}: {exc}") from exc


def source_manifest(path: Path) -> dict[str, int]:
    count = 0
    min_id = 0
    max_id = 0
    previous_id = 0
    lab_fingerprint = 0
    for row in iter_rows(path):
        row_id, tenant_id, status, payload, created_at = row
        if row_id <= previous_id:
            raise ContractError(
                "source ids must be unique and strictly increasing"
            )
        previous_id = row_id
        count += 1
        if count == 1:
            min_id = row_id
        max_id = row_id
        encoded = "#".join(
            (str(row_id), str(tenant_id), str(status), payload, created_at)
        ).encode("utf-8")
        lab_fingerprint ^= zlib.crc32(encoded) & 0xFFFFFFFF
    return {
        "count": count,
        "min_id": min_id,
        "max_id": max_id,
        "distinct_id": count,
        "lab_fingerprint": lab_fingerprint,
    }


def status_snapshot(cursor) -> dict[str, int]:
    quoted = ",".join(f"'{name}'" for name in STATUS_NAMES)
    cursor.execute(
        f"SHOW GLOBAL STATUS WHERE Variable_name IN ({quoted})"
    )
    values = {str(name): int(value) for name, value in cursor.fetchall()}
    return {name: values.get(name, 0) for name in STATUS_NAMES}


def load_single(connection, table: str, rows, phase: dict[str, str]) -> int:
    phase["value"] = "SESSION_SETTING"
    connection.autocommit = True
    phase["value"] = "BEFORE_SEND"
    cursor = connection.cursor()
    statement = INSERT_SQL.format(table=table)
    accepted = 0
    for row in rows:
        phase["value"] = "EXECUTING"
        cursor.execute(statement, row)
        accepted += 1
        phase["value"] = "BEFORE_SEND"
    phase["value"] = "CLOSING"
    cursor.close()
    phase["value"] = "BEFORE_SEND"
    return accepted


def load_batches(
    connection,
    table: str,
    rows,
    batch_size: int,
    phase: dict[str, str],
) -> int:
    phase["value"] = "SESSION_SETTING"
    connection.autocommit = False
    phase["value"] = "BEFORE_SEND"
    cursor = connection.cursor()
    statement = INSERT_SQL.format(table=table)
    accepted = 0
    batch: list[tuple[int, int, int, str, str]] = []
    for row in rows:
        batch.append(row)
        if len(batch) < batch_size:
            continue
        phase["value"] = "EXECUTING"
        cursor.executemany(statement, batch)
        phase["value"] = "COMMITTING"
        connection.commit()
        accepted += len(batch)
        batch.clear()
        phase["value"] = "BEFORE_SEND"
    if batch:
        phase["value"] = "EXECUTING"
        cursor.executemany(statement, batch)
        phase["value"] = "COMMITTING"
        connection.commit()
        accepted += len(batch)
        phase["value"] = "BEFORE_SEND"
    phase["value"] = "CLOSING"
    cursor.close()
    phase["value"] = "BEFORE_SEND"
    return accepted


def fingerprint(cursor, table: str) -> dict[str, int]:
    cursor.execute(
        "SELECT COUNT(*), COALESCE(MIN(id),0), COALESCE(MAX(id),0), "
        "COUNT(DISTINCT id), "
        "COALESCE(BIT_XOR(CRC32(CONCAT_WS('#',id,tenant_id,status,payload,created_at))),0) "
        f"FROM `{table}`"
    )
    count, min_id, max_id, distinct_id, crc = cursor.fetchone()
    return {
        "count": int(count),
        "min_id": int(min_id),
        "max_id": int(max_id),
        "distinct_id": int(distinct_id),
        "lab_fingerprint": int(crc),
    }


def require_manifest_match(
    source: dict[str, int],
    target: dict[str, int],
    accepted: int,
) -> None:
    mismatches: dict[str, object] = {}
    if accepted != source["count"]:
        mismatches["accepted"] = {
            "expected": source["count"],
            "actual": accepted,
        }
    for name in (
        "count",
        "min_id",
        "max_id",
        "distinct_id",
        "lab_fingerprint",
    ):
        if target[name] != source[name]:
            mismatches[name] = {
                "expected": source[name],
                "actual": target[name],
            }
    if mismatches:
        raise ContractError(
            f"source/target manifest mismatch: {json.dumps(mismatches, sort_keys=True)}"
        )


def load_local_file(
    connection,
    table: str,
    path: Path,
    source: dict[str, int],
    phase: dict[str, str],
) -> tuple[int, int, int]:
    if "'" in str(path):
        raise ValueError("input path may not contain a single quote")
    phase["value"] = "SESSION_SETTING"
    connection.autocommit = False
    phase["value"] = "BEFORE_SEND"
    cursor = connection.cursor()
    phase["value"] = "EXECUTING"
    cursor.execute(
        "LOAD DATA LOCAL INFILE "
        f"'{path.as_posix()}' INTO TABLE `{table}` "
        "FIELDS TERMINATED BY '\\t' LINES TERMINATED BY '\\n' "
        "(id,tenant_id,status,payload,created_at)"
    )
    warning_count = int(cursor.warning_count or 0)
    accepted = int(cursor.rowcount)
    rejected = max(source["count"] - accepted, 0)
    if warning_count != 0 or rejected != 0 or accepted != source["count"]:
        raise ContractError(
            "LOAD DATA warnings/rejects: "
            f"warnings={warning_count}, rejected={rejected}, "
            f"accepted={accepted}, expected={source['count']}"
        )
    phase["value"] = "VERIFYING"
    uncommitted_target = fingerprint(cursor, table)
    require_manifest_match(source, uncommitted_target, accepted)
    phase["value"] = "COMMITTING"
    connection.commit()
    phase["value"] = "CLOSING"
    cursor.close()
    phase["value"] = "BEFORE_SEND"
    return accepted, warning_count, rejected


def classify(
    exc: BaseException,
    failure_phase: str,
    rollback_confirmed: bool,
    cleanup_errors: list[tuple[str, BaseException]],
) -> str:
    if cleanup_errors:
        return "UNKNOWN"
    if failure_phase == "COMMITTING":
        return "UNKNOWN"
    if (
        failure_phase in {
            "SESSION_SETTING",
            "GLOBAL_SETTING",
            "EXECUTING",
            "VERIFYING",
        }
        and (
            isinstance(
                exc,
                (
                    InterfaceError,
                    ReadTimeoutError,
                    WriteTimeoutError,
                    TimeoutError,
                ),
            )
            or getattr(exc, "errno", None) in (2006, 2013, 2055)
        )
    ):
        return "UNKNOWN"
    if isinstance(exc, (ContractError, ValueError)):
        return "FAILED"
    if failure_phase in ("VALIDATING", "BEFORE_SEND"):
        return "FAILED"
    if (
        failure_phase in {
            "SESSION_SETTING",
            "GLOBAL_SETTING",
            "EXECUTING",
            "VERIFYING",
        }
        and isinstance(exc, ConnectorError)
        and rollback_confirmed
    ):
        return "FAILED"
    return "UNKNOWN"


def restore_local_infile(config: dict, original: int) -> None:
    admin_config = {
        name: config[name] for name in ("host", "port", "user", "password")
    }
    admin = None
    cursor = None
    failure: BaseException | None = None
    try:
        admin = mysql.connector.connect(
            **admin_config,
            allow_local_infile=True,
        )
        cursor = admin.cursor()
        cursor.execute(f"SET GLOBAL local_infile={int(original)}")
        cursor.execute("SELECT @@GLOBAL.local_infile")
        restored = int(cursor.fetchone()[0])
        if restored != int(original):
            raise ContractError(
                f"local_infile restoration mismatch: expected {original}, got {restored}"
            )
    except BaseException as exc:
        failure = exc
    if cursor is not None:
        try:
            cursor.close()
        except BaseException as exc:
            if failure is None:
                failure = exc
    if admin is not None:
        try:
            admin.close()
        except BaseException as exc:
            if failure is None:
                failure = exc
    if failure is not None:
        raise failure


def supplied_password(arguments: list[str]) -> str | None:
    for index, argument in enumerate(arguments):
        if argument == "--password" and index + 1 < len(arguments):
            return arguments[index + 1]
        if argument.startswith("--password="):
            return argument.split("=", 1)[1]
    return None


def redact(value: object, password: str | None) -> str:
    text = str(value)
    return text.replace(password, "***") if password else text


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    password = supplied_password(arguments)
    lone_help = arguments in (["-h"], ["--help"])
    has_help_token = any(
        argument in ("-h", "--help") for argument in arguments
    )
    parser = JsonArgumentParser()
    parser.add_argument("--mode", choices=sorted(ALLOWED_TABLES), required=True)
    parser.add_argument(
        "--table", choices=sorted(ALLOWED_TABLES.values()), required=True
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", required=True)

    connection = None
    original_local_infile = None
    restore_required = False
    rollback_confirmed = False
    phase = {"value": "VALIDATING"}
    failure: tuple[BaseException, str] | None = None
    cleanup_errors: list[tuple[str, BaseException]] = []
    success_payload: dict[str, object] | None = None
    config: dict[str, object] | None = None

    try:
        if has_help_token and not lone_help:
            raise ContractError("-h/--help must be used alone")
        args = parser.parse_args(arguments)
        expected_table = ALLOWED_TABLES[args.mode]
        if args.table != expected_table:
            raise ContractError(
                f"mode {args.mode} requires table {expected_table}"
            )
        raw_input_path = args.input
        if not raw_input_path.is_absolute():
            raise ContractError("--input must be an existing absolute file")
        input_path = raw_input_path.resolve(strict=True)
        if not input_path.is_file():
            raise ContractError("--input must be an existing regular file")
        if not 1 <= args.batch_size <= 5000:
            raise ContractError("--batch-size must be in 1..5000")
        if args.mode == "load" and "'" in str(input_path):
            raise ContractError("input path may not contain a single quote")

        expected_source = source_manifest(input_path)
        config = {
            "host": args.host,
            "port": args.port,
            "user": args.user,
            "password": args.password,
            "database": "mysql_senior_scenarios",
        }
        phase["value"] = "BEFORE_SEND"
        connection = mysql.connector.connect(
            **config,
            allow_local_infile=True,
        )
        cursor = connection.cursor()
        if args.mode == "load":
            phase["value"] = "GLOBAL_SETTING"
            cursor.execute("SELECT @@GLOBAL.local_infile")
            original_local_infile = int(cursor.fetchone()[0])
            if original_local_infile == 0:
                restore_required = True
                cursor.execute("SET GLOBAL local_infile=1")
                cursor.execute("SELECT @@GLOBAL.local_infile")
                if int(cursor.fetchone()[0]) != 1:
                    raise ContractError("local_infile enable was not confirmed")
            phase["value"] = "BEFORE_SEND"
        phase["value"] = "EXECUTING"
        cursor.execute(f"TRUNCATE TABLE `{args.table}`")
        phase["value"] = "VERIFYING"
        before = status_snapshot(cursor)
        phase["value"] = "CLOSING"
        cursor.close()
        phase["value"] = "BEFORE_SEND"
        started = time.perf_counter()

        if args.mode == "single":
            accepted = load_single(
                connection, args.table, iter_rows(input_path), phase
            )
        elif args.mode == "batch":
            accepted = load_batches(
                connection,
                args.table,
                iter_rows(input_path),
                args.batch_size,
                phase,
            )
        else:
            accepted, warning_count, rejected = load_local_file(
                connection,
                args.table,
                input_path,
                expected_source,
                phase,
            )
        if args.mode != "load":
            warning_count = 0
            rejected = 0

        phase["value"] = "VERIFYING"
        cursor = connection.cursor()
        after = status_snapshot(cursor)
        target_manifest = fingerprint(cursor, args.table)
        phase["value"] = "CLOSING"
        cursor.close()
        phase["value"] = "VERIFYING"
        seconds = time.perf_counter() - started
        require_manifest_match(expected_source, target_manifest, accepted)
        phase["value"] = "VERIFIED"
        success_payload = {
            "mode": args.mode,
            "table": args.table,
            "rows": accepted,
            "warnings": warning_count,
            "rejected": rejected,
            "seconds": seconds,
            "rows_per_second": accepted / seconds,
            "status_delta": {
                name: after[name] - before[name] for name in STATUS_NAMES
            },
            "source_manifest": expected_source,
            "target_manifest": target_manifest,
        }
    except SystemExit as exc:
        if exc.code == 0 and lone_help:
            raise
        failure = (exc, phase["value"])
    except BaseException as exc:
        failure = (exc, phase["value"])
    finally:
        if failure is not None and connection is not None:
            phase["value"] = "ROLLING_BACK"
            try:
                if not connection.is_connected():
                    raise RuntimeError("rollback could not be confirmed")
                connection.rollback()
                rollback_confirmed = True
            except BaseException as exc:
                cleanup_errors.append((phase["value"], exc))
        if restore_required:
            phase["value"] = "RESTORING"
            try:
                if config is None or original_local_infile is None:
                    raise RuntimeError("local_infile restore state is incomplete")
                restore_local_infile(config, original_local_infile)
            except BaseException as exc:
                cleanup_errors.append((phase["value"], exc))
        if connection is not None:
            phase["value"] = "CLOSING"
            try:
                connection.close()
            except BaseException as exc:
                cleanup_errors.append((phase["value"], exc))

    if failure is not None or cleanup_errors:
        if failure is None:
            primary_exc, operation_phase = cleanup_errors[0][1], "VERIFIED"
        else:
            primary_exc, operation_phase = failure
        status = classify(
            primary_exc,
            operation_phase,
            rollback_confirmed,
            cleanup_errors,
        )
        result: dict[str, object] = {
            "status": status,
            "phase": (
                cleanup_errors[0][0] if cleanup_errors else operation_phase
            ),
            "operation_phase": operation_phase,
            "rollback_confirmed": rollback_confirmed,
            "error_type": type(primary_exc).__name__,
            "error": redact(primary_exc, password),
        }
        if cleanup_errors:
            result["cleanup_errors"] = [
                {
                    "phase": cleanup_phase,
                    "error_type": type(cleanup_exc).__name__,
                    "error": redact(cleanup_exc, password),
                }
                for cleanup_phase, cleanup_exc in cleanup_errors
            ]
        print(json.dumps(result, sort_keys=True), file=sys.stderr)
        return 2

    if success_payload is None:
        print(
            json.dumps(
                {
                    "status": "UNKNOWN",
                    "phase": phase["value"],
                    "operation_phase": "VERIFIED",
                    "rollback_confirmed": rollback_confirmed,
                    "error_type": "InternalOutcomeError",
                    "error": "verified payload was not finalized",
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    phase["value"] = "VERIFIED"
    success_payload["status"] = "SUCCEEDED"
    success_payload["phase"] = phase["value"]
    print(json.dumps(success_payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Runner interface：`--mode single|batch|load`，`--table bulk_single|bulk_batch|bulk_load`，`--input /absolute/path/input.tsv`，`--batch-size 1000`，`--host 127.0.0.1`，`--port 3306`，`--user root`，`--password root`。

CLI／result contract：exact lone `-h` 或 exact lone `--help` 是唯一允许 normal plaintext、zero-exit 的路径；其他 invocation 都在 mandatory cleanup 完成后输出恰一个 final JSON。help token 若与任何其他 argument 混用，会在 `parse_args()` 前拒绝，不打印 plaintext help。只有 `status="SUCCEEDED", phase="VERIFIED"` 返回 0；其他路径返回 2，并带 `FAILED`／`UNKNOWN`、operation／cleanup phase、rollback confirmation 和已遮蔽密码的 error。

安全 contract：

- table name 在 interpolation 前受三名称 allowlist 检查；`single`／`batch`／`load` 分别只 truncate `bulk_single`／`bulk_batch`／`bulk_load`；batch size 限 `1..5000`。
- raw input 必须在 `resolve(strict=True)` 前已经是 absolute；resolved target 必须是 existing regular file。load path 含 single quote 也在建立连接前拒绝。
- load timing 前以 `iter_rows()`／`parse_row()` 扫描 immutable TSV；source primary ID 必须 strictly increasing 且 unique，并计算 exact count、min／max、distinct 和与 target SQL 相同的 UTF-8 CRC32／BIT_XOR lab fingerprint。
- `SUCCEEDED` 前强制 source count、accepted rows、target count、distinct ID、min／max ID 和 target fingerprint 全部相等。driver modes 的 exception 只能成为 `FAILED` 或 `UNKNOWN`，不能以 synthetic rejects 转成成功。
- `LOAD DATA LOCAL` 返回后，在任何下一条 SQL 前保存 `cursor.warning_count` 与 `rowcount`；warning、reject、accepted mismatch 或 uncommitted target-manifest mismatch 一律 rollback，不 commit。
- load mode 以 `allow_local_infile=True` 连接；若原值为 0，先写 `restore_required=True`，才送出 enable statement。即使 enable acknowledgement 遗失，也必须经 fresh admin connection restore，并 read back 确认原值；restore／read-back／close 任一 uncertainty 都是 `UNKNOWN`。
- phase 区分 `VALIDATING`、`BEFORE_SEND`、`SESSION_SETTING`、`GLOBAL_SETTING`、`EXECUTING`、`COMMITTING`、`VERIFYING`、`ROLLING_BACK`、`RESTORING`、`CLOSING` 和 `VERIFIED`。三个 mode 都在每次 `connection.autocommit` assignment 前进入 `SESSION_SETTING`；该 session statement 的 lost ack／read timeout／write timeout 即使稍后 rollback 成功仍是 `UNKNOWN`。commit ambiguity 永远是 `UNKNOWN`；definite server rejection 只有在同一连接可用且 rollback confirmed 时才可为 `FAILED`。
- malformed／missing／mixed-help arguments、validation、execution、verification、rollback、restoration 或 close failure 共用一个 structured nonzero JSON outcome，记录 `operation_phase` 与 `rollback_confirmed`，不泄漏 password、不输出 traceback。仅 exact lone `-h`／`--help` 保留 argparse normal help；`--help --unknown`、`--unknown --help` 等 mixed form 都是单一 JSON failure。成功 JSON 也只在 restore／close finalization 后输出，并包含 mode、table、rows、warnings、rejected、seconds、rows_per_second、status deltas、source manifest 和 target manifest。

`UNKNOWN` 必须先用 run ID／batch identity、target count／fingerprint 和 binlog／replica 位置查证，绝不自动重试；不能以重跑覆盖可能已提交的资料。

## Run、正确性、发布与恢复

例如 batch execution form：

```bash
uv run --with mysql-connector-python==9.7.0 python "$MYSQL_SCENARIO_RUN_DIR/bulk_runner.py" \
  --mode batch \
  --table bulk_batch \
  --input "$MYSQL_SCENARIO_RUN_DIR/input.tsv" \
  --batch-size 1000 \
  --host 127.0.0.1 --port 3306 --user root --password root
```

每次输出另存 JSON，连同 manifest 作为 evidence。accepted 必须等于 input rows；rejected 必须为 0，或逐行有 reject identity、原因、重新计数后的 expected target；`COUNT(*)`、`MIN(id)`、`MAX(id)`、`COUNT(DISTINCT id)` 与 `lab_fingerprint` 必须三表相同且等于 source expectation。checksum／`BIT_XOR(CRC32(...))` 是 lab fingerprint，不是密码学 collision-proof audit；要满足更强生产审计须保存 immutable source SHA-256、row identity 与分片／批次对账。

publish boundary 是 staging validation 完整通过后，在已批准窗口以受控 rename／merge 让 reader 看见；hot existing table 不可以这份 `TRUNCATE` runner 直接执行。rollback source 是此前 live table／可验证 source manifest：publish 前 drop/recreate staging，publish 后按既定 cutback/restore plan 处理，不能凭空宣称 transaction rollback 会撤销所有 DDL／publish。restart watermark 是 manifest run ID 加 mode/table/input SHA-256，`FAILED` 才依规则清理并重跑；`UNKNOWN` 先查证再决定继续、回滚或手工对账。

## S／M／L matrix、resource gate 与 hypotheses

| Tier | Rows | single | batch | LOAD DATA |
|---|---:|---|---|---|
| S | 100,000 | 3 runs | 3 runs | 3 runs |
| M | 1,000,000 | not run after S establishes control cost | 3 runs if gate passes | 3 runs if gate passes |
| L | 10,000,000 | not run | 3 runs if gate passes | 3 runs if gate passes |

开始前只保留 qualitative hypotheses：single autocommit 应有最高 round-trip／commit overhead；batch 应减少 round trips 和 commits；兼容 TSV 的 `LOAD DATA` 预计避免重复 SQL statement construction 而最快；三者必须给出相同 correctness result。精确 throughput 和 speedup 未知；额外 indexes、宽 row、binlog、replica 或受限 I/O 都可能改变结果。

每个 tier 前的 gate：确认独立 namespaced database／tables、source manifest 与 DDL 已冻结；测可用 disk（包括 client input、server temporary copy for `LOCAL`、data／undo／redo／binlog／relay-log headroom）；记录 server version、durability、binlog format、replica health/lag、Buffer Pool／checkpoint 指标基线；明确允许 lag／disk／elapsed SLA 与 ABORT threshold。任一空间、replica lag、checkpoint/redo pressure、error rate 或 correctness gate 不通过，标 `ABORTED`，保留 restart point，不进入下一 tier。S 只建 control cost；M/L 仅在 gate 通过后运行，且 L 的目标为 10,000,000 rows。

evidence table 预留为 `READY_UNRUN`：

| Tier／path／run | manifest SHA-256 | accepted／rejected | fingerprint | seconds／rows_per_second | redo／data／network deltas | outcome |
|---|---|---|---|---|---|---|
| 未运行 | — | — | — | — | — | `READY_UNRUN` |

## 面试口述

### 30 秒

先问 target 是 empty staging、empty final 还是 hot table；TSV 是否可信／immutable、列形状为何；有哪些 indexes／constraints；binlog／replica 与可接受 lag；失败后 input 是否可重建、如何 restart。若能隔离且 TSV 兼容，我会先以 immutable manifest 建 staging，优先 `LOAD DATA LOCAL`；需要应用 conversion／reject checkpoint 就用 bounded parameterized batches。single autocommit 只当 control。每条路径先跑 S，再通过 count／distinct/min/max/fingerprint/reject gate 才逐级到 M、L；publish 是 validation 后的独立边界。

### 3–5 分钟

我会把资料 parse 后经 client/server transfer 或 server file read，做转换与 unique／constraint 检查，写 clustered 与 secondary B+ tree，同时产生 undo、redo、binlog，脏页要经过 checkpoint/fsync，replica 还要 receive、persist、apply。因此 batch size 与 transaction 数同时影响 round trips、commit cost、redo/checkpoint 和 replica lag；index 越多、row 越宽写放大越高。先冻结 source SHA-256／rows／DDL／run ID，在 namespaced staging 以一个 worker 找出 control，然后有 gate 地加 batch/concurrency。

`LOAD DATA` 适合兼容且隔离的档案；需 validation／conversion／batch identity 则使用 `executemany()`。我会保存 accepted/rejected、duplicate/missing explanation、target count/min/max/distinct 与 fingerprint；三条路径只在同 source／DDL／server config 下比较。观察 redo、checkpoint、binlog、disk 与 replica lag；越过 stop threshold 就 `ABORTED`。验证通过才在明确 publish boundary 受控 publish；rollback 依先前 live table 或 immutable source。timeout／断线落在 execute/commit 时是 `UNKNOWN`，先按 run/batch identity 查证，绝不盲目重试。

### 追问树

- **hot table**：改为 staging + controlled merge，定义 concurrent writers、idempotency、lock／lag budget，不使用本 runner 的 truncate 路径。
- **duplicate input**：解释业务 duplicate 与 malformed/reject；以 row identity／unique invariant 对账，不能用 `IGNORE` 隐藏它。
- **disk shortage**：先停止；估算 input、`LOCAL` server temp、data/index/undo/redo/binlog/relay-log headroom，清出或扩容后从 manifest restart。
- **replica lag**：测 receive/persist/apply；超过 budget 节流或暂停并保留 watermark，不以 source 成功为全链路完成。
- **interrupted commit**：`UNKNOWN`；查 target/batch identity、binlog/replica position 和 fingerprint 后才决定下一步。
- **source regeneration**：只允许以相同 deterministic generator、rows、bytes、SHA-256 重建；否则是新 manifest/run，不与旧 evidence 混比。
- **exact 10-million target**：L 必须是 10,000,000 rows、每条 batch/LOAD DATA 三 runs、先过 M gate；S/M evidence 不外推成 L。
