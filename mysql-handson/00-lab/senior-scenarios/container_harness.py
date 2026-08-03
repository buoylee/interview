"""Fail-closed container harness for the senior report-export experiment.

The module keeps Docker inspection, DNS, Connector, process launch, and database
work behind explicit boundaries so its policy can be tested without reaching a
live MySQL server.  Live execution is entered only through the ``run-all`` CLI.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import py_compile
import re
import socket
import subprocess
import sys
import tempfile
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping

from evidence_contract import (
    EvidenceBinding,
    PHASES,
    create_phase_manifest,
    extract_programs,
    write_historical_loss,
    write_immutable_json,
)


EXPECTED_CONNECTOR = "9.7.0"
EXPECTED_HOST = "mysql-senior-scenarios-mysql"
EXPECTED_PORT = 3306
EXPECTED_MEMORY = 2 * 1024**3
EXPECTED_PIDS = 256
EXPECTED_NETWORK = "mysql-senior-scenarios-net"
EXPECTED_VOLUME = "mysql-senior-scenarios-evidence-v1"
EXPECTED_SCOPE = "mysql-senior-scenarios"
EXPECTED_CPU = "2"
MIN_FREE_BYTES = 5_419_909_120
RUNTIME_PREFIX = "mysql-senior-scenarios."
SEVENTH_RUNTIME_FILENAME = "seventh-runtime.json"
BOOTSTRAP_INSPECT_PATH = Path("/opt/bootstrap-inspect.json")

EXPECTED_PROGRAM_SHA256 = {
    "export_runner.py": "f774d36f3448c491668d1838075e2d18199e183fdbba415421fbcfb31e335d35",
    "scenario_controller.py": "9aa226bb5fedb48b949841fa933b00decfe80855c19bce244e9a6e4476c04148",
    "freeze_audit.py": "7461b1c0315f8b134cbe0f94d7ac6980e22034aa0703e587f853c11d3a443062",
}

INVOCATIONS = (
    "kill-preflight-1",
    "oltp-smoke-1",
    "control-1",
    "control-2",
    "control-3",
    "latency-calibration-1",
    "buffered-1",
    "buffered-2",
    "buffered-3",
    "chunked-1",
    "chunked-2",
    "chunked-3",
    "resume-interrupt-1",
    "resume-complete-1",
)

PHASE_INVOCATIONS = {
    "10-kill-smoke": INVOCATIONS[0:2],
    "20-controls-calibration": INVOCATIONS[2:6],
    "30-buffered": INVOCATIONS[6:9],
    "40-chunked": INVOCATIONS[9:12],
    "50-resume-audit": INVOCATIONS[12:14],
}

FREEZE_TRIGGER_NAMES = (
    "freeze_report_order_insert",
    "freeze_report_order_update",
    "freeze_report_order_delete",
    "freeze_report_item_insert",
    "freeze_report_item_update",
    "freeze_report_item_delete",
)
FREEZE_TRIGGER_SQL = tuple(
    "CREATE TRIGGER "
    f"{name} BEFORE {operation} ON {table} FOR EACH ROW "
    "SIGNAL SQLSTATE '45000' SET "
    "MESSAGE_TEXT='report source is frozen for mysql senior scenario'"
    for name, table, operation in (
        (FREEZE_TRIGGER_NAMES[0], "report_order", "INSERT"),
        (FREEZE_TRIGGER_NAMES[1], "report_order", "UPDATE"),
        (FREEZE_TRIGGER_NAMES[2], "report_order", "DELETE"),
        (FREEZE_TRIGGER_NAMES[3], "report_item", "INSERT"),
        (FREEZE_TRIGGER_NAMES[4], "report_item", "UPDATE"),
        (FREEZE_TRIGGER_NAMES[5], "report_item", "DELETE"),
    )
)
RECOVERY_DROP_FREEZE_TRIGGER_SQL = tuple(
    f"DROP TRIGGER IF EXISTS mysql_senior_scenarios.{name}"
    for name in FREEZE_TRIGGER_NAMES
)
DROP_FREEZE_TRIGGER_SQL = tuple(
    f"DROP TRIGGER mysql_senior_scenarios.{name}" for name in FREEZE_TRIGGER_NAMES
)

SOURCE_MANIFEST_FIELDS = {
    "orders",
    "min_cursor",
    "high_cursor",
    "order_crc32_sum",
    "items",
    "item_orders",
    "item_crc32_sum",
    "min_items_per_order",
    "max_items_per_order",
    "probes",
    "probe_counter_sum",
    "report_rows",
    "total_amount_fingerprint",
    "item_count_fingerprint",
}

ORDER_CRC32_SQL = """SELECT COALESCE(SUM(CAST(CRC32(CONCAT_WS('#',
  CAST(id AS CHAR),
  CAST(tenant_id AS CHAR),
  CAST(status AS CHAR),
  DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s.%f')
)) AS UNSIGNED)), 0) AS order_crc32_sum
FROM report_order"""
ITEM_CRC32_SQL = """SELECT COALESCE(SUM(CAST(CRC32(CONCAT_WS('#',
  CAST(id AS CHAR),
  CAST(order_id AS CHAR),
  CAST(qty AS CHAR),
  CAST(unit_price AS CHAR)
)) AS UNSIGNED)), 0) AS item_crc32_sum
FROM report_item"""

CREATE_TABLE_SQL = (
    """CREATE TABLE report_order (
  id BIGINT UNSIGNED NOT NULL, tenant_id BIGINT UNSIGNED NOT NULL,
  status TINYINT UNSIGNED NOT NULL, created_at DATETIME(6) NOT NULL,
  PRIMARY KEY (id), KEY idx_created_id (created_at, id)
) ENGINE=InnoDB""",
    """CREATE TABLE report_item (
  id BIGINT UNSIGNED NOT NULL, order_id BIGINT UNSIGNED NOT NULL,
  qty INT UNSIGNED NOT NULL, unit_price DECIMAL(18,2) NOT NULL,
  PRIMARY KEY (id), KEY idx_order (order_id)
) ENGINE=InnoDB""",
    """CREATE TABLE oltp_probe (
  id BIGINT UNSIGNED NOT NULL, counter BIGINT UNSIGNED NOT NULL DEFAULT 0,
  payload VARCHAR(128) NOT NULL, PRIMARY KEY (id)
) ENGINE=InnoDB""",
)

SEED_SQL = (
    "DROP TABLE IF EXISTS seed_digit",
    "CREATE TABLE seed_digit (d TINYINT UNSIGNED PRIMARY KEY)",
    "INSERT INTO seed_digit VALUES (0),(1),(2),(3),(4),(5),(6),(7),(8),(9)",
    """INSERT INTO report_order (id, tenant_id, status, created_at)
SELECT n, MOD(n, 1000) + 1, MOD(n, 4),
       TIMESTAMPADD(SECOND, n, '2026-01-01 00:00:00')
FROM (
  SELECT 1 + d0.d + 10*d1.d + 100*d2.d + 1000*d3.d
           + 10000*d4.d + 100000*d5.d AS n
  FROM seed_digit AS d0 CROSS JOIN seed_digit AS d1
  CROSS JOIN seed_digit AS d2 CROSS JOIN seed_digit AS d3
  CROSS JOIN seed_digit AS d4 CROSS JOIN seed_digit AS d5
  ORDER BY n LIMIT 100000
) AS seq""",
    """INSERT INTO report_item (id, order_id, qty, unit_price)
SELECT o.id * 10 + d.d, o.id, d.d, (MOD(o.id * d.d, 100000) + 1) / 100
FROM report_order AS o JOIN seed_digit AS d ON d.d IN (1,2,3)""",
    "DROP TABLE seed_digit",
    """INSERT INTO oltp_probe (id, counter, payload)
SELECT id, 0, CONCAT('probe-', id) FROM report_order WHERE id <= 10000""",
)

NEGATIVE_PROBE_SQL = (
    "INSERT INTO report_order VALUES (200001,1,0,'2026-01-01 00:00:00.000000')",
    "UPDATE report_order SET status=status WHERE id=1",
    "DELETE FROM report_order WHERE id=1",
    "INSERT INTO report_item VALUES (2000011,1,1,1.00)",
    "UPDATE report_item SET qty=qty WHERE id=11",
    "DELETE FROM report_item WHERE id=11",
)

FREEZE_MESSAGE = "report source is frozen for mysql senior scenario"
EXPECTED_PROBE_SCHEMA = [
    {"values": ["COLUMN", "id", 1, "bigint unsigned", "NO", None, ""]},
    {"values": ["COLUMN", "counter", 2, "bigint unsigned", "NO", "0", ""]},
    {"values": ["COLUMN", "payload", 3, "varchar(128)", "NO", None, ""]},
    {"values": ["INDEX", "PRIMARY", 1, "id", 0, "BTREE", None]},
]


def canonical_seed_reference() -> dict[str, object]:
    """Independently calculate the fixed seed's complete business fingerprint."""
    order_crc32_sum = 0
    item_crc32_sum = 0
    total_cents = 0
    for order_id in range(1, 100_001):
        day_offset, day_second = divmod(order_id, 86_400)
        hour, day_second = divmod(day_second, 3_600)
        minute, second = divmod(day_second, 60)
        created_at = (
            f"2026-01-{day_offset + 1:02d} "
            f"{hour:02d}:{minute:02d}:{second:02d}.000000"
        )
        order_value = "#".join(
            (
                str(order_id),
                str(order_id % 1000 + 1),
                str(order_id % 4),
                created_at,
            )
        )
        order_crc32_sum += zlib.crc32(order_value.encode("utf-8"))
        for quantity in (1, 2, 3):
            price_cents = (order_id * quantity) % 100_000 + 1
            price = f"{price_cents // 100}.{price_cents % 100:02d}"
            item_value = "#".join(
                (
                    str(order_id * 10 + quantity),
                    str(order_id),
                    str(quantity),
                    price,
                )
            )
            item_crc32_sum += zlib.crc32(item_value.encode("utf-8"))
            total_cents += quantity * price_cents
    return {
        "orders": 100_000,
        "min_cursor": ["2026-01-01 00:00:01.000000", 1],
        "high_cursor": ["2026-01-02 03:46:40.000000", 100_000],
        "order_crc32_sum": order_crc32_sum,
        "items": 300_000,
        "item_orders": 100_000,
        "item_crc32_sum": item_crc32_sum,
        "min_items_per_order": 3,
        "max_items_per_order": 3,
        "probes": 10_000,
        "probe_counter_sum": 0,
        "report_rows": 100_000,
        "total_amount_fingerprint": f"{total_cents // 100}.{total_cents % 100:02d}",
        "item_count_fingerprint": 300_000,
    }


EXPECTED_SEED_MANIFEST = canonical_seed_reference()


def _utc_text() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _require_exact_nonnegative(value: object, field: str) -> int:
    if type(value) is not int or value < 0:
        raise RuntimeError(f"{field} must be an exact nonnegative integer")
    return value


def validate_source_manifest(manifest: object) -> dict[str, object]:
    """Validate the canonical seed/freeze fields and fixed S-level counts."""
    if type(manifest) is not dict or set(manifest) != SOURCE_MANIFEST_FIELDS:
        raise RuntimeError("source manifest fields are incomplete or unexpected")
    expected_counts = {
        "orders": 100_000,
        "items": 300_000,
        "item_orders": 100_000,
        "min_items_per_order": 3,
        "max_items_per_order": 3,
        "probes": 10_000,
        "report_rows": 100_000,
        "item_count_fingerprint": 300_000,
    }
    for field, expected in expected_counts.items():
        if _require_exact_nonnegative(manifest[field], field) != expected:
            raise RuntimeError(f"canonical source count changed: {field}")
    for field in ("order_crc32_sum", "item_crc32_sum", "probe_counter_sum"):
        _require_exact_nonnegative(manifest[field], field)
    min_cursor = strict_canonical_cursor(manifest["min_cursor"], "source minimum")
    high_cursor = strict_canonical_cursor(manifest["high_cursor"], "source high")
    if not _canonical_json_equal(
        min_cursor, ["2026-01-01 00:00:01.000000", 1]
    ):
        raise RuntimeError("canonical source minimum cursor changed")
    if not _canonical_json_equal(
        high_cursor, ["2026-01-02 03:46:40.000000", 100000]
    ):
        raise RuntimeError("canonical source high cursor changed")
    total = manifest["total_amount_fingerprint"]
    if type(total) is not str or not re.fullmatch(r"[0-9]+\.[0-9]{2}", total):
        raise RuntimeError("source total amount fingerprint is noncanonical")
    return manifest


def validate_seed_baseline(
    manifest: object, probe_schema: object
) -> dict[str, object]:
    validated = validate_source_manifest(manifest)
    if validated != EXPECTED_SEED_MANIFEST:
        raise RuntimeError("live seed fingerprint differs from canonical Python reference")
    if probe_schema != EXPECTED_PROBE_SCHEMA:
        raise RuntimeError("live oltp_probe schema differs from canonical reference")
    return validated


def require_nonempty_password(environ: Mapping[str, str]) -> str:
    password = environ.get("MYSQL_PASSWORD")
    if type(password) is not str or not password:
        raise RuntimeError("MYSQL_PASSWORD must be a nonempty environment string")
    return password


def validate_negative_probe_error(error: BaseException) -> dict[str, str]:
    sqlstate = getattr(error, "sqlstate", None)
    message = getattr(error, "msg", None)
    if sqlstate != "45000" or message != FREEZE_MESSAGE:
        raise RuntimeError("freeze probe did not observe the exact SQLSTATE/message")
    return {"message": message, "sqlstate": sqlstate}


def exact_db_int(value: object, field: str) -> int:
    """Normalize only exact integral Connector int/Decimal values."""
    if type(value) is int:
        return value
    if type(value) is Decimal and value.is_finite() and value == value.to_integral_value():
        return int(value)
    raise RuntimeError(f"{field} is not an exact Connector integer")


def _cursor_text(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S.%f")
    if type(value) is str and re.fullmatch(
        r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{6}", value
    ):
        return value
    raise RuntimeError("source cursor is not a canonical microsecond timestamp")


def collect_source_manifest(cursor: object) -> dict[str, object]:
    """Execute the canonical count, cursor, CRC-sum, and aggregate queries."""
    cursor.execute(
        "SELECT COUNT(*), DATE_FORMAT(MIN(created_at),'%Y-%m-%d %H:%i:%s.%f'), "
        "MIN(id), DATE_FORMAT(MAX(created_at),'%Y-%m-%d %H:%i:%s.%f'), MAX(id) "
        "FROM report_order"
    )
    order = cursor.fetchone()
    cursor.execute(ORDER_CRC32_SQL)
    order_crc32_sum = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*), COUNT(DISTINCT order_id) FROM report_item"
    )
    items = cursor.fetchone()
    cursor.execute(ITEM_CRC32_SQL)
    item_crc32_sum = cursor.fetchone()[0]
    cursor.execute(
        "SELECT MIN(c), MAX(c) FROM (SELECT order_id, COUNT(*) AS c "
        "FROM report_item GROUP BY order_id) AS x"
    )
    item_range = cursor.fetchone()
    cursor.execute(
        "SELECT COUNT(*), COALESCE(SUM(counter),0) FROM oltp_probe"
    )
    probes = cursor.fetchone()
    cursor.execute(
        "SELECT COUNT(*), SUM(total_amount), SUM(item_count) FROM ("
        "SELECT o.created_at, o.id, SUM(i.qty * i.unit_price) AS total_amount, "
        "COUNT(*) AS item_count FROM report_order AS o JOIN report_item AS i "
        "ON i.order_id=o.id GROUP BY o.created_at,o.id) AS report"
    )
    report = cursor.fetchone()
    total = report[1]
    if type(total) is not Decimal or not total.is_finite():
        raise RuntimeError("source total amount is not a Connector Decimal")
    manifest = {
        "orders": exact_db_int(order[0], "orders"),
        "min_cursor": [_cursor_text(order[1]), exact_db_int(order[2], "min_id")],
        "high_cursor": [_cursor_text(order[3]), exact_db_int(order[4], "high_id")],
        "order_crc32_sum": exact_db_int(order_crc32_sum, "order_crc32_sum"),
        "items": exact_db_int(items[0], "items"),
        "item_orders": exact_db_int(items[1], "item_orders"),
        "item_crc32_sum": exact_db_int(item_crc32_sum, "item_crc32_sum"),
        "min_items_per_order": exact_db_int(item_range[0], "min_items_per_order"),
        "max_items_per_order": exact_db_int(item_range[1], "max_items_per_order"),
        "probes": exact_db_int(probes[0], "probes"),
        "probe_counter_sum": exact_db_int(probes[1], "probe_counter_sum"),
        "report_rows": exact_db_int(report[0], "report_rows"),
        "total_amount_fingerprint": format(total, ".2f"),
        "item_count_fingerprint": exact_db_int(report[2], "item_count_fingerprint"),
    }
    return validate_source_manifest(manifest)


def collect_probe_schema(cursor: object) -> list[dict[str, object]]:
    cursor.execute(
        "SELECT 'COLUMN', COLUMN_NAME, ORDINAL_POSITION, COLUMN_TYPE, "
        "IS_NULLABLE, COLUMN_DEFAULT, EXTRA FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA='mysql_senior_scenarios' AND TABLE_NAME='oltp_probe' "
        "ORDER BY ORDINAL_POSITION"
    )
    columns = cursor.fetchall()
    cursor.execute(
        "SELECT 'INDEX', INDEX_NAME, SEQ_IN_INDEX, COLUMN_NAME, NON_UNIQUE, "
        "INDEX_TYPE, NULL FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA='mysql_senior_scenarios' AND TABLE_NAME='oltp_probe' "
        "ORDER BY INDEX_NAME,SEQ_IN_INDEX"
    )
    indexes = cursor.fetchall()
    rows = [list(row) for row in (*columns, *indexes)]
    if not rows:
        raise RuntimeError("oltp_probe schema evidence is empty")
    return [
        {"values": [value if value is None or type(value) in (str, int) else str(value) for value in row]}
        for row in rows
    ]


def _normalized_trigger_statement(value: object) -> str:
    if type(value) is not str:
        raise RuntimeError("trigger action statement is not an exact string")
    return re.sub(r"\s*=\s*", "=", re.sub(r"\s+", " ", value.strip()))


def validate_freeze_trigger_rows(rows: object) -> list[dict[str, str]]:
    if type(rows) is not list or len(rows) != 6:
        raise RuntimeError("schema must contain exactly six owned freeze triggers")
    expected = {
        name: (operation, table)
        for name, table, operation in (
            (FREEZE_TRIGGER_NAMES[0], "report_order", "INSERT"),
            (FREEZE_TRIGGER_NAMES[1], "report_order", "UPDATE"),
            (FREEZE_TRIGGER_NAMES[2], "report_order", "DELETE"),
            (FREEZE_TRIGGER_NAMES[3], "report_item", "INSERT"),
            (FREEZE_TRIGGER_NAMES[4], "report_item", "UPDATE"),
            (FREEZE_TRIGGER_NAMES[5], "report_item", "DELETE"),
        )
    }
    action = _normalized_trigger_statement(
        "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='" + FREEZE_MESSAGE + "'"
    )
    observed: list[dict[str, str]] = []
    names = set()
    for row in rows:
        if type(row) not in (tuple, list) or len(row) != 5:
            raise RuntimeError("freeze trigger metadata row is malformed")
        name, operation, table, timing, statement = row
        if (
            type(name) is not str
            or name in names
            or name not in expected
            or (operation, table) != expected[name]
            or timing != "BEFORE"
            or _normalized_trigger_statement(statement) != action
        ):
            raise RuntimeError("freeze trigger name or definition drifted")
        names.add(name)
        observed.append(
            {
                "name": name,
                "operation": operation,
                "table": table,
                "timing": timing,
                "statement": action,
            }
        )
    if names != set(FREEZE_TRIGGER_NAMES):
        raise RuntimeError("freeze trigger set is incomplete")
    return sorted(observed, key=lambda item: item["name"])


def snapshot_freeze_triggers(cursor: object) -> list[dict[str, str]]:
    cursor.execute(
        "SELECT TRIGGER_NAME,EVENT_MANIPULATION,EVENT_OBJECT_TABLE,ACTION_TIMING,"
        "ACTION_STATEMENT FROM information_schema.TRIGGERS "
        "WHERE TRIGGER_SCHEMA='mysql_senior_scenarios' ORDER BY TRIGGER_NAME"
    )
    return validate_freeze_trigger_rows(list(cursor.fetchall()))


def _load_freeze_audit(path: Path) -> Callable[..., dict]:
    spec = importlib.util.spec_from_file_location("seventh_freeze_audit", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("freeze audit program cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    audit = getattr(module, "audit_task10_freeze", None)
    if not callable(audit):
        raise RuntimeError("freeze audit helper is missing")
    return audit


class ExperimentDatabase:
    """Canonical seed/freeze/audit/teardown adapter for live ``run-all``."""

    def __init__(
        self,
        context: "BootstrapContext",
        boundary: "BootstrapBoundary",
        identity_check: Callable[[], object],
    ):
        self.context = context
        self.boundary = boundary
        self.identity_check = identity_check
        self.audit_freeze = _load_freeze_audit(context.runtime_root / "freeze_audit.py")
        self.seed_manifest: dict[str, object] | None = None
        self.seed_probe_schema: list[dict[str, object]] | None = None
        self.global_variables: list[object] | None = None

    def _connect(self, database: str = "mysql_senior_scenarios") -> object:
        password = require_nonempty_password(self.boundary.environ)
        connection = self.boundary.connect(
            host=EXPECTED_HOST,
            port=EXPECTED_PORT,
            user="root",
            password=password,
            database=database,
            use_pure=True,
        )
        if type(connection) is not self.boundary.pure_connection_type:
            close = getattr(connection, "close", None)
            if callable(close):
                close()
            raise RuntimeError("database boundary received nonpure connection")
        return connection

    @staticmethod
    def _close(resource: object | None) -> None:
        close = getattr(resource, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _globals(cursor: object) -> list[object]:
        cursor.execute(
            "SELECT @@GLOBAL.innodb_buffer_pool_size,@@GLOBAL.tmp_table_size,"
            "@@GLOBAL.max_heap_table_size,@@GLOBAL.transaction_isolation,"
            "@@GLOBAL.read_only,@@GLOBAL.super_read_only"
        )
        return [value if type(value) in (str, int) else str(value) for value in cursor.fetchone()]

    def prepare(self) -> None:
        connection = self._connect("mysql")
        cursor = None
        try:
            connection.autocommit = True
            cursor = connection.cursor()
            cursor.execute("DROP DATABASE IF EXISTS mysql_senior_scenarios")
            cursor.execute("CREATE DATABASE mysql_senior_scenarios")
            cursor.execute("USE mysql_senior_scenarios")
            for statement in CREATE_TABLE_SQL:
                cursor.execute(statement)
            for statement in SEED_SQL:
                cursor.execute(statement)
            self.seed_manifest = collect_source_manifest(cursor)
            self.seed_probe_schema = collect_probe_schema(cursor)
            validate_seed_baseline(self.seed_manifest, self.seed_probe_schema)
            self.global_variables = self._globals(cursor)
            for statement in RECOVERY_DROP_FREEZE_TRIGGER_SQL:
                cursor.execute(statement)
            for statement in FREEZE_TRIGGER_SQL:
                cursor.execute(statement)
            installed_triggers = snapshot_freeze_triggers(cursor)
            negative_results = []
            for statement in NEGATIVE_PROBE_SQL:
                try:
                    cursor.execute(statement)
                except Exception as error:
                    observed = validate_negative_probe_error(error)
                    negative_results.append(
                        {"sql": statement, **observed, "rejected": True}
                    )
                else:
                    raise RuntimeError("freeze negative probe unexpectedly succeeded")
            current = collect_source_manifest(cursor)
            current_schema = collect_probe_schema(cursor)
            freeze_audit = self.audit_freeze(
                self.seed_manifest,
                current,
                self.seed_probe_schema,
                current_schema,
            )
            write_immutable_json(self.context.runtime_root / "seed-manifest.json", self.seed_manifest)
            write_immutable_json(self.context.runtime_root / "probe-schema.json", self.seed_probe_schema)
            write_immutable_json(self.context.runtime_root / "freeze-negative-probes.json", negative_results)
            write_immutable_json(self.context.runtime_root / "seed-freeze-audit.json", freeze_audit)
            write_immutable_json(self.context.runtime_root / "global-variables.json", self.global_variables)
            write_immutable_json(self.context.runtime_root / "freeze-triggers.json", installed_triggers)
        finally:
            self._close(cursor)
            self._close(connection)

    def phase_audit(self, phase: str) -> None:
        if self.seed_manifest is None or self.seed_probe_schema is None:
            raise RuntimeError("seed/freeze baseline is missing")
        connection = self._connect()
        cursor = None
        try:
            cursor = connection.cursor()
            triggers = snapshot_freeze_triggers(cursor)
            current = collect_source_manifest(cursor)
            schema = collect_probe_schema(cursor)
            result = self.audit_freeze(
                self.seed_manifest, current, self.seed_probe_schema, schema
            )
            self.identity_check()
            write_immutable_json(
                self.context.runtime_root / f"source-audit-{phase}.json",
                {"freeze": result, "triggers": triggers},
            )
        finally:
            self._close(cursor)
            self._close(connection)

    def external_audit(self) -> None:
        if self.seed_manifest is None:
            raise RuntimeError("source baseline is missing")
        jobs = [
            *(self.context.runtime_root / f"job-buffered-{index}" for index in range(1, 4)),
            *(self.context.runtime_root / f"job-chunked-{index}" for index in range(1, 4)),
            self.context.runtime_root / "job-resume-1",
        ]
        signatures = []
        for job in jobs:
            artifact = job / "artifact.tsv"
            state_path = job / "state.json"
            if not artifact.is_file() or not state_path.is_file():
                raise RuntimeError(f"external audit artifact is missing: {job.name}")
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state_high_cursor = strict_canonical_cursor(
                [state.get("high_created_at"), state.get("high_id")],
                f"external audit high: {job.name}",
            )
            state_last_cursor = strict_canonical_cursor(
                [state.get("last_created_at"), state.get("last_id")],
                f"external audit last: {job.name}",
            )
            source_high_cursor = strict_canonical_cursor(
                self.seed_manifest["high_cursor"], "external audit source high"
            )
            if (
                state.get("status") != "SUCCEEDED"
                or not _canonical_json_equal(state_high_cursor, source_high_cursor)
                or not _canonical_json_equal(state_last_cursor, source_high_cursor)
            ):
                raise RuntimeError(f"external audit state is invalid: {job.name}")
            digest = hashlib.sha256()
            rows = 0
            order_ids = set()
            amount = Decimal("0.00")
            item_count = 0
            with artifact.open("rb") as source:
                for line in source:
                    digest.update(line)
                    fields = line.rstrip(b"\n").split(b"\t")
                    if len(fields) != 6:
                        raise RuntimeError("artifact row does not have six columns")
                    rows += 1
                    order_ids.add(int(fields[1]))
                    amount += Decimal(fields[4].decode("ascii"))
                    item_count += int(fields[5])
            if (
                rows != 100_000
                or len(order_ids) != 100_000
                or format(amount, ".2f") != self.seed_manifest["total_amount_fingerprint"]
                or item_count != 300_000
            ):
                raise RuntimeError(f"artifact business audit failed: {job.name}")
            signatures.append({"job": job.name, "rows": rows, "sha256": digest.hexdigest()})
        if len({item["sha256"] for item in signatures}) != 1:
            raise RuntimeError("buffered, chunked, and resumed SHA-256 differ")
        write_immutable_json(
            self.context.runtime_root / "external-artifact-audit.json",
            {"artifacts": signatures, "status": "COMPLETE"},
        )

    def teardown(self, succeeded: bool) -> None:
        errors = []
        evidence: dict[str, object] = {
            "requested_success": succeeded,
            "timestamp": _utc_text(),
            "triggers_dropped": [],
        }
        connection = None
        cursor = None
        try:
            connection = self._connect()
            cursor = connection.cursor()
            cursor.execute(
                "SELECT ID,USER,DB,COMMAND,INFO FROM information_schema.PROCESSLIST "
                "WHERE USER='root' AND DB='mysql_senior_scenarios' "
                "AND ID<>CONNECTION_ID() ORDER BY ID"
            )
            active = [list(row) for row in cursor.fetchall()]
            evidence["active_processes"] = active
            if active:
                errors.append("experiment user still has active processes")
            try:
                evidence["triggers_before_drop"] = snapshot_freeze_triggers(cursor)
            except Exception as error:
                errors.append(f"before-drop trigger audit: {error}")
            if self.seed_manifest is not None and self.seed_probe_schema is not None:
                try:
                    before = collect_source_manifest(cursor)
                    before_schema = collect_probe_schema(cursor)
                    evidence["before_drop_audit"] = self.audit_freeze(
                        self.seed_manifest, before, self.seed_probe_schema, before_schema
                    )
                except Exception as error:
                    errors.append(f"before-drop audit: {error}")
            for name, statement in zip(FREEZE_TRIGGER_NAMES, DROP_FREEZE_TRIGGER_SQL):
                try:
                    cursor.execute(statement)
                    evidence["triggers_dropped"].append(name)
                except Exception as error:
                    errors.append(f"drop {name}: {error}")
            try:
                cursor.execute(
                    "SELECT TRIGGER_NAME FROM information_schema.TRIGGERS WHERE "
                    "TRIGGER_SCHEMA='mysql_senior_scenarios' ORDER BY TRIGGER_NAME"
                )
                remaining = list(cursor.fetchall())
                evidence["triggers_after_drop"] = remaining
                if remaining:
                    errors.append("schema triggers remain after controlled drop")
            except Exception as error:
                errors.append(f"trigger absence audit: {error}")
            if self.seed_manifest is not None and self.seed_probe_schema is not None:
                try:
                    after = collect_source_manifest(cursor)
                    after_schema = collect_probe_schema(cursor)
                    evidence["after_drop_audit"] = self.audit_freeze(
                        self.seed_manifest, after, self.seed_probe_schema, after_schema
                    )
                except Exception as error:
                    errors.append(f"after-drop audit: {error}")
            try:
                if self.global_variables is None or self._globals(cursor) != self.global_variables:
                    errors.append("global variables changed")
            except Exception as error:
                errors.append(f"global-variable audit: {error}")
        except Exception as error:
            errors.append(f"teardown connection/audit: {error}")
            if cursor is not None:
                for name, statement in zip(FREEZE_TRIGGER_NAMES, DROP_FREEZE_TRIGGER_SQL):
                    if name in evidence["triggers_dropped"]:
                        continue
                    try:
                        cursor.execute(statement)
                        evidence["triggers_dropped"].append(name)
                    except Exception as drop_error:
                        errors.append(f"drop {name}: {drop_error}")
        finally:
            self._close(cursor)
            self._close(connection)
        try:
            self.identity_check()
        except Exception as error:
            errors.append(f"identity audit: {error}")
        evidence["errors"] = errors
        evidence["status"] = (
            "COMPLETE" if succeeded and not errors else "FAILED_PHASE_TEARDOWN_COMPLETE"
        )
        write_immutable_json(self.context.runtime_root / "controlled-stop.json", evidence)
        if errors:
            raise RuntimeError("; ".join(errors))


class ControlledTeardownOnce:
    """Share one teardown attempt between the state machine and outer lifecycle."""

    def __init__(self, teardown: Callable[[bool], object]):
        self.teardown = teardown
        self.attempted = False

    def __call__(self, succeeded: bool) -> object:
        if self.attempted:
            raise RuntimeError("controlled teardown was attempted more than once")
        self.attempted = True
        return self.teardown(succeeded)


def _combined_error(primary: BaseException, secondary: BaseException, label: str) -> RuntimeError:
    return RuntimeError(f"{primary}; {label}: {secondary}")


def run_all_lifecycle(
    *,
    context: "BootstrapContext",
    boundary: "BootstrapBoundary",
    database_factory: Callable[..., object],
    connector_verifier: Callable[..., dict[str, object]],
    connector_writer: Callable[[Path, object], object],
    machine_runner: Callable[["BootstrapContext", object, ControlledTeardownOnce], object],
) -> object:
    database = database_factory(
        context,
        boundary,
        lambda: verify_internal_identity(
            boundary,
            {
                "harness_container_id": context.internal_identity["container_id"],
                "harness_image_id": context.binding.harness_image_id,
            },
            context.internal_identity,
        ),
    )
    teardown = ControlledTeardownOnce(database.teardown)
    try:
        connector_evidence = connector_verifier(
            boundary.connector_module,
            boundary.pure_connection_type,
            boundary.connect,
            boundary.environ,
        )
        connector_writer(
            context.runtime_root / "bootstrap-connector.json", connector_evidence
        )
        return machine_runner(context, database, teardown)
    except BaseException as primary:
        if not teardown.attempted:
            try:
                teardown(False)
            except BaseException as teardown_error:
                raise _combined_error(primary, teardown_error, "controlled teardown failed")
        raise


def _default_connector_boundary() -> tuple[object, type, Callable[..., object]]:
    import mysql.connector
    from mysql.connector.connection import MySQLConnection

    return mysql.connector, MySQLConnection, mysql.connector.connect


@dataclass(frozen=True)
class BootstrapBoundary:
    """Injected external effects used by bootstrap validation."""

    connector_module: object
    pure_connection_type: type
    connect: Callable[..., object]
    read_text: Callable[[Path], str]
    read_inspect: Callable[[Path], object]
    resolve_dns: Callable[[str, int], object]
    environ: Mapping[str, str]
    suffix_factory: Callable[[], str]

    @classmethod
    def live(cls) -> "BootstrapBoundary":
        connector_module, pure_connection_type, connect = _default_connector_boundary()
        return cls(
            connector_module=connector_module,
            pure_connection_type=pure_connection_type,
            connect=connect,
            read_text=lambda path: path.read_text(encoding="utf-8"),
            read_inspect=lambda path: json.loads(path.read_text(encoding="utf-8")),
            resolve_dns=lambda host, port: socket.getaddrinfo(host, port),
            environ=os.environ,
            suffix_factory=lambda: os.urandom(8).hex(),
        )


@dataclass(frozen=True)
class BootstrapContext:
    runtime_root: Path
    binding: EvidenceBinding
    connector_evidence: dict[str, object]
    internal_identity: dict[str, object]


def _connector_environment(connector_module: object) -> dict[str, object]:
    version = getattr(connector_module, "__version__", None)
    if version != EXPECTED_CONNECTOR:
        raise RuntimeError(
            f"Connector/Python {EXPECTED_CONNECTOR} required, observed {version!r}"
        )
    threadsafety = getattr(connector_module, "threadsafety", None)
    if type(threadsafety) is not int:
        raise RuntimeError("Connector/Python threadsafety must be an exact integer")
    have_cext = getattr(connector_module, "HAVE_CEXT", None)
    if type(have_cext) is not bool:
        raise RuntimeError("Connector/Python HAVE_CEXT must be an exact boolean")
    return {
        "connector_version": version,
        "threadsafety": threadsafety,
        "have_cext": have_cext,
        "requested_use_pure": True,
    }


def verify_connector_contract(
    connector_module: object,
    pure_connection_type: type,
    connect: Callable[..., object],
    environ: Mapping[str, str],
) -> dict[str, object]:
    """Open and verify one exact pure-Python connection using env-only secret."""
    evidence = _connector_environment(connector_module)
    password = require_nonempty_password(environ)
    connection = connect(
        host=EXPECTED_HOST,
        port=EXPECTED_PORT,
        user="root",
        password=password,
        database="mysql",
        use_pure=True,
    )
    try:
        evidence["actual_connection_class"] = (
            f"{type(connection).__module__}.{type(connection).__qualname__}"
        )
        evidence["actual_pure"] = type(connection) is pure_connection_type
        if not evidence["actual_pure"]:
            raise RuntimeError("Connector/Python connection is not exact pure implementation")
        return evidence
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            close()


def _exact_int_text(value: str, field: str) -> int:
    stripped = value.strip()
    if not re.fullmatch(r"[0-9]+", stripped):
        raise RuntimeError(f"{field} is not a finite exact integer")
    return int(stripped)


def _container_by_name(document: object, name: str) -> dict[str, Any]:
    if type(document) is not list:
        raise RuntimeError("bootstrap inspect evidence must be a JSON list")
    matches = [
        item
        for item in document
        if type(item) is dict and item.get("Name") == f"/{name}"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"bootstrap inspect evidence missing exact container {name}")
    return matches[0]


def _require_scope(container: dict[str, Any]) -> None:
    labels = container.get("Config", {}).get("Labels", {})
    if labels.get("com.openai.codex.scope") != EXPECTED_SCOPE:
        raise RuntimeError("container scope label drifted")


def verify_resource_contract(boundary: BootstrapBoundary) -> dict[str, str]:
    """Verify cgroups, named mount, Docker network identity, and DNS."""
    cpu_fields = boundary.read_text(Path("/sys/fs/cgroup/cpu.max")).split()
    if len(cpu_fields) != 2 or not all(re.fullmatch(r"[0-9]+", item) for item in cpu_fields):
        raise RuntimeError("cpu.max must contain finite quota and period")
    quota, period = (int(item) for item in cpu_fields)
    if period <= 0 or quota != 2 * period:
        raise RuntimeError("cpu.max is not exactly two CPUs")
    if _exact_int_text(
        boundary.read_text(Path("/sys/fs/cgroup/memory.max")), "memory.max"
    ) != EXPECTED_MEMORY:
        raise RuntimeError("memory.max is not exactly 2147483648")
    if _exact_int_text(
        boundary.read_text(Path("/sys/fs/cgroup/pids.max")), "pids.max"
    ) != EXPECTED_PIDS:
        raise RuntimeError("pids.max is not exactly 256")

    document = boundary.read_inspect(BOOTSTRAP_INSPECT_PATH)
    harness = _container_by_name(document, "mysql-senior-scenarios-harness")
    mysql = _container_by_name(document, EXPECTED_HOST)
    _require_scope(harness)
    _require_scope(mysql)
    for container in (harness, mysql):
        if any(
            type(mount) is dict and mount.get("Type") == "bind"
            for mount in container.get("Mounts", [])
        ):
            raise RuntimeError("bootstrap inspect contains a forbidden bind mount")
    limits = harness.get("HostConfig", {})
    if (
        limits.get("NanoCpus") != 2_000_000_000
        or limits.get("Memory") != EXPECTED_MEMORY
        or limits.get("PidsLimit") != EXPECTED_PIDS
    ):
        raise RuntimeError("harness inspect limits drifted")
    private_tmp_mounts = [
        mount
        for mount in harness.get("Mounts", [])
        if type(mount) is dict and mount.get("Destination") == "/private/tmp"
    ]
    if (
        len(private_tmp_mounts) != 1
        or private_tmp_mounts[0].get("Type") != "volume"
        or private_tmp_mounts[0].get("Name") != EXPECTED_VOLUME
        or private_tmp_mounts[0].get("Destination") != "/private/tmp"
    ):
        raise RuntimeError("/private/tmp is not the exact named evidence volume")
    for container in (harness, mysql):
        networks = container.get("NetworkSettings", {}).get("Networks", {})
        if type(networks) is not dict or EXPECTED_NETWORK not in networks:
            raise RuntimeError("Docker network binding drifted")
    if not boundary.resolve_dns(EXPECTED_HOST, EXPECTED_PORT):
        raise RuntimeError("Docker DNS did not resolve the exact MySQL hostname")
    for field, container in (("harness", harness), ("mysql", mysql)):
        if type(container.get("Id")) is not str or not container["Id"]:
            raise RuntimeError(f"{field} container ID is missing")
        if type(container.get("Image")) is not str or not container["Image"]:
            raise RuntimeError(f"{field} image ID is missing")
    return {
        "harness_container_id": harness["Id"],
        "harness_image_id": harness["Image"],
        "mysql_image_id": mysql["Image"],
        "mysql_container_id": mysql["Id"],
    }


def _dns_addresses(result: object) -> list[str]:
    if type(result) not in (tuple, list):
        raise RuntimeError("Docker DNS result is malformed")
    addresses = set()
    for item in result:
        if type(item) not in (tuple, list) or len(item) < 5:
            raise RuntimeError("Docker DNS result entry is malformed")
        sockaddr = item[4]
        if (
            type(sockaddr) not in (tuple, list)
            or not sockaddr
            or type(sockaddr[0]) is not str
        ):
            raise RuntimeError("Docker DNS sockaddr is malformed")
        addresses.add(sockaddr[0])
    if not addresses:
        raise RuntimeError("Docker DNS did not resolve the exact MySQL hostname")
    return sorted(addresses)


def _private_tmp_mount_line(mountinfo: str) -> str:
    matches = []
    for line in mountinfo.splitlines():
        fields = line.split()
        if len(fields) >= 10 and fields[4] == "/private/tmp" and "-" in fields:
            matches.append(" ".join(fields))
    if len(matches) != 1:
        raise RuntimeError("internal mountinfo lacks one exact /private/tmp mount")
    return matches[0]


def capture_internal_identity(
    boundary: BootstrapBoundary, bootstrap: Mapping[str, str]
) -> dict[str, object]:
    hostname = boundary.read_text(Path("/etc/hostname")).strip()
    container_id = bootstrap.get("harness_container_id")
    image_id = bootstrap.get("harness_image_id")
    if (
        type(hostname) is not str
        or not hostname
        or type(container_id) is not str
        or not container_id.startswith(hostname)
        or type(image_id) is not str
        or not image_id
    ):
        raise RuntimeError("internal hostname is not bound to bootstrap container ID")
    mountinfo = boundary.read_text(Path("/proc/self/mountinfo"))
    return {
        "hostname": hostname,
        "container_id": container_id,
        "cpu_max": boundary.read_text(Path("/sys/fs/cgroup/cpu.max")).strip(),
        "memory_max": boundary.read_text(Path("/sys/fs/cgroup/memory.max")).strip(),
        "pids_max": boundary.read_text(Path("/sys/fs/cgroup/pids.max")).strip(),
        "private_tmp_mount": _private_tmp_mount_line(mountinfo),
        "mountinfo_sha256": hashlib.sha256(mountinfo.encode("utf-8")).hexdigest(),
        "dns_addresses": _dns_addresses(
            boundary.resolve_dns(EXPECTED_HOST, EXPECTED_PORT)
        ),
        # A running container cannot change image ID without process replacement;
        # the fresh hostname check binds this process to the inspected container.
        "harness_image_id_process_lifetime": image_id,
    }


def verify_internal_identity(
    boundary: BootstrapBoundary,
    bootstrap: Mapping[str, str],
    expected: Mapping[str, object],
) -> dict[str, object]:
    observed = capture_internal_identity(boundary, bootstrap)
    if observed != expected:
        raise RuntimeError("live internal container identity drifted from bootstrap")
    return observed


def _reviewed_programs(scenario_text: str) -> tuple[dict[str, str], dict[str, str]]:
    programs = extract_programs(scenario_text)
    hashes = {name: _sha256_text(source) for name, source in programs.items()}
    if hashes != EXPECTED_PROGRAM_SHA256:
        raise RuntimeError("canonical scenario program hashes changed")
    return programs, hashes


def _materialize_programs(runtime_root: Path, programs: dict[str, str]) -> None:
    for name, source in programs.items():
        target = runtime_root / name
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(source)
            output.flush()
            os.fsync(output.fileno())
        py_compile.compile(str(target), doraise=True)
        if target.stat().st_mode & 0o777 != 0o600:
            raise RuntimeError(f"materialized program mode drifted: {name}")


def prepare_bootstrap(
    volume_root: Path,
    scenario_path: Path,
    expected_commit: str,
    boundary: BootstrapBoundary,
) -> BootstrapContext:
    """Validate identity, materialize a unique runtime, then touch MySQL once."""
    volume = Path(volume_root)
    seventh_path = volume / SEVENTH_RUNTIME_FILENAME
    historical_path = volume / "historical-evidence-loss.json"
    if seventh_path.exists() or seventh_path.is_symlink():
        raise FileExistsError(seventh_path)
    if historical_path.exists() or historical_path.is_symlink():
        raise FileExistsError(historical_path)
    require_nonempty_password(boundary.environ)
    if type(expected_commit) is not str or not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        raise RuntimeError("expected scenario commit must be a lowercase 40-byte Git ID")

    connector_evidence = _connector_environment(boundary.connector_module)
    identities = verify_resource_contract(boundary)
    internal_identity = capture_internal_identity(boundary, identities)
    scenario_text = scenario_path.read_text(encoding="utf-8")
    programs, program_hashes = _reviewed_programs(scenario_text)

    suffix = boundary.suffix_factory()
    if type(suffix) is not str or not re.fullmatch(r"[A-Za-z0-9_-]+", suffix):
        raise RuntimeError("runtime suffix must be nonempty and path-safe")
    runtime_root = volume / f"{RUNTIME_PREFIX}{suffix}"
    runtime_root.mkdir(mode=0o700)
    _materialize_programs(runtime_root, programs)

    write_historical_loss(volume)
    scenario_sha256 = _sha256_text(scenario_text)
    write_immutable_json(
        seventh_path,
        {
            "created_at": _utc_text(),
            "program_sha256": program_hashes,
            "runtime_path": str(runtime_root),
            "scenario_commit": expected_commit,
            "scenario_sha256": scenario_sha256,
            "suffix": suffix,
            "internal_identity": internal_identity,
        },
    )
    binding = EvidenceBinding(
        scenario_commit=expected_commit,
        scenario_sha256=scenario_sha256,
        mysql_image_id=identities["mysql_image_id"],
        mysql_container_id=identities["mysql_container_id"],
        harness_image_id=identities["harness_image_id"],
        network_name=EXPECTED_NETWORK,
        volume_name=EXPECTED_VOLUME,
        cpu_limit=EXPECTED_CPU,
        memory_limit_bytes=EXPECTED_MEMORY,
        pids_limit=EXPECTED_PIDS,
        program_sha256=program_hashes,
    )
    return BootstrapContext(runtime_root, binding, connector_evidence, internal_identity)


def _controller_mode(invocation_id: str) -> str:
    if invocation_id == "kill-preflight-1":
        return "preflight-kill"
    if invocation_id == "oltp-smoke-1":
        return "preflight-oltp"
    if invocation_id.startswith("control-"):
        return "none"
    if invocation_id == "latency-calibration-1":
        return "latency-calibration"
    if invocation_id.startswith("buffered-"):
        return "buffered"
    if invocation_id.startswith("chunked-"):
        return "chunked"
    raise ValueError(f"controller has no mode for {invocation_id}")


def build_invocation_command(invocation_id: str, runtime_root: Path) -> tuple[str, ...]:
    """Build a password-free command from the reviewed controller/runner CLIs."""
    if invocation_id not in INVOCATIONS:
        raise ValueError("unknown invocation ID")
    root = Path(runtime_root)
    common_connection = (
        "--host",
        EXPECTED_HOST,
        "--port",
        str(EXPECTED_PORT),
        "--user",
        "root",
        "--password-env",
        "MYSQL_PASSWORD",
    )
    if invocation_id.startswith("resume-"):
        maximum = "3" if invocation_id == "resume-interrupt-1" else "0"
        return (
            sys.executable,
            str(root / "export_runner.py"),
            "--mode",
            "chunked",
            "--runtime-root",
            str(root),
            "--job-dir",
            str(root / "job-resume-1"),
            "--abort-file",
            str(root / "abort-resume-1.json"),
            "--batch-size",
            "1000",
            "--sleep-ms",
            "20",
            "--max-batches",
            maximum,
            "--min-free-bytes",
            str(MIN_FREE_BYTES),
            *common_connection,
        )
    mode = _controller_mode(invocation_id)
    command = [
        sys.executable,
        str(root / "scenario_controller.py"),
        "--runner",
        str(root / "export_runner.py"),
        "--runtime-root",
        str(root),
        "--trial-id",
        invocation_id,
        "--export-mode",
        mode,
        "--p95-budget-ms",
        "0",
        "--min-free-bytes",
        str(MIN_FREE_BYTES),
        "--duration-seconds",
        "5" if invocation_id == "oltp-smoke-1" else "60",
        "--start-delay-seconds",
        "5",
        "--startup-grace-seconds",
        "12",
        "--heartbeat-grace-seconds",
        "2.5",
        "--threads",
        "4",
        "--batch-size",
        "1000",
        "--sleep-ms",
        "20",
    ]
    if mode in ("buffered", "chunked"):
        command.extend(("--job-dir", str(root / f"job-{invocation_id}")))
    command.extend(common_connection)
    return tuple(command)


class InvocationLedger:
    """Phase-rotated immutable JSONL ledger with globally one-shot IDs."""

    def __init__(self, active_path: Path):
        self.active_path = Path(active_path)
        self.active_path.parent.mkdir(parents=True, exist_ok=True)
        self._records: dict[str, list[str]] = {}
        for path in sorted(self.active_path.parent.glob("invocations-*.jsonl")):
            self._load(path)
        if self.active_path.exists():
            self._load(self.active_path)

    def _load(self, path: Path) -> None:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"malformed invocation ledger: {path}") from error
            if type(record) is not dict:
                raise ValueError(f"malformed invocation ledger: {path}")
            invocation_id = record.get("invocation_id")
            state = record.get("state")
            if type(invocation_id) is not str or type(state) is not str:
                raise ValueError(f"malformed invocation ledger: {path}")
            self._records.setdefault(invocation_id, []).append(state)

    def _append(self, record: dict[str, object]) -> None:
        encoded = (
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        descriptor = os.open(
            self.active_path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600
        )
        with os.fdopen(descriptor, "ab") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())

    def start(self, invocation_id: str) -> None:
        if invocation_id not in INVOCATIONS or invocation_id in self._records:
            raise ValueError(f"invocation ID is unknown or already measured: {invocation_id}")
        self._append(
            {
                "invocation_id": invocation_id,
                "state": "STARTING",
                "timestamp": _utc_text(),
            }
        )
        self._records[invocation_id] = ["STARTING"]

    def finish(self, invocation_id: str, state: str, detail: object) -> None:
        states = self._records.get(invocation_id)
        if states != ["STARTING"]:
            raise ValueError(f"invocation ID cannot be reconciled: {invocation_id}")
        if state not in {"SUCCEEDED", "FAILED", "UNKNOWN", "ABORTED"}:
            raise ValueError("invocation terminal state is invalid")
        self._append(
            {
                "detail": detail,
                "invocation_id": invocation_id,
                "state": state,
                "timestamp": _utc_text(),
            }
        )
        states.append(state)

    def checkpoint(self, phase: str) -> None:
        if not self.active_path.exists():
            raise RuntimeError("cannot checkpoint an empty invocation ledger")
        target = self.active_path.parent / f"invocations-{phase}.jsonl"
        if target.exists() or target.is_symlink():
            raise FileExistsError(target)
        os.rename(self.active_path, target)


Launch = Callable[[str, tuple[str, ...], Mapping[str, str], Path, Path], dict[str, object]]
ManifestWriter = Callable[[Path, str, EvidenceBinding], object]
Teardown = Callable[[bool], object]

RESUME_INTERRUPTION_AUDIT = "resume-interruption-audit.json"
RESUME_PART_FIELDS = {
    "first_cursor",
    "last_cursor",
    "name",
    "number",
    "rows",
    "sha256",
}


def _checkpoint_state_sha256(state: object) -> str:
    encoded = (
        json.dumps(
            state, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def strict_canonical_cursor(value: object, field: str) -> list[object]:
    """Require the runner's exact JSON cursor representation without aliases."""
    if (
        type(value) is not list
        or len(value) != 2
        or type(value[0]) is not str
        or not value[0]
        or not re.fullmatch(
            r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{6}", value[0]
        )
        or type(value[1]) is not int
        or value[1] < 0
    ):
        raise RuntimeError(f"{field} cursor exact type or format changed")
    try:
        datetime.strptime(value[0], "%Y-%m-%d %H:%M:%S.%f")
    except ValueError as error:
        raise RuntimeError(f"{field} cursor exact type or format changed") from error
    return [value[0], value[1]]


def _canonical_json_equal(left: object, right: object) -> bool:
    return json.dumps(
        left, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) == json.dumps(
        right, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def canonical_tsv_part_metadata(path: Path) -> dict[str, object]:
    """Derive the runner's immutable part metadata from canonical TSV bytes."""
    digest = hashlib.sha256()
    rows = 0
    first_cursor = None
    last_cursor = None
    try:
        with Path(path).open("rb") as source:
            for line in source:
                if not line.endswith(b"\n"):
                    raise RuntimeError(f"{Path(path).name} has a noncanonical final line")
                fields = line[:-1].split(b"\t")
                if len(fields) != 6:
                    raise RuntimeError(
                        f"{Path(path).name} has a noncanonical column count"
                    )
                try:
                    created_at = fields[0].decode("ascii")
                    order_id = int(fields[1])
                    tenant_id = int(fields[2])
                    status_value = int(fields[3])
                    amount = Decimal(fields[4].decode("ascii"))
                    item_count = int(fields[5])
                except (UnicodeError, ValueError, InvalidOperation) as error:
                    raise RuntimeError(
                        f"{Path(path).name} has a noncanonical TSV value"
                    ) from error
                if not amount.is_finite() or amount < 0:
                    raise RuntimeError(
                        f"{Path(path).name} has a noncanonical TSV amount"
                    )
                canonical = b"\t".join(
                    (
                        created_at.encode("ascii"),
                        str(order_id).encode("ascii"),
                        str(tenant_id).encode("ascii"),
                        str(status_value).encode("ascii"),
                        format(amount, ".2f").encode("ascii"),
                        str(item_count).encode("ascii"),
                    )
                ) + b"\n"
                cursor_list = strict_canonical_cursor(
                    [created_at, order_id], f"{Path(path).name} row"
                )
                cursor = (cursor_list[0], cursor_list[1])
                if (
                    canonical != line
                    or not re.fullmatch(
                        r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{6}",
                        created_at,
                    )
                    or order_id < 0
                    or tenant_id < 0
                    or status_value < 0
                    or item_count < 0
                    or (last_cursor is not None and cursor <= last_cursor)
                ):
                    raise RuntimeError(
                        f"{Path(path).name} has noncanonical cursor or row bytes"
                    )
                if first_cursor is None:
                    first_cursor = cursor
                last_cursor = cursor
                digest.update(line)
                rows += 1
    except OSError as error:
        raise RuntimeError(f"{Path(path).name} is unreadable") from error
    if rows == 0:
        raise RuntimeError(f"{Path(path).name} is empty")
    return {
        "first_cursor": list(first_cursor),
        "last_cursor": list(last_cursor),
        "rows": rows,
        "sha256": digest.hexdigest(),
    }


def _validated_resume_parts(job: Path, value: object) -> list[dict[str, object]]:
    if type(value) is not list or len(value) != 3:
        raise RuntimeError("resume interruption parts are not exact")
    validated = []
    previous_last = None
    for number, part in enumerate(value, 1):
        if type(part) is not dict or set(part) != RESUME_PART_FIELDS:
            raise RuntimeError("resume interruption part fields are not exact")
        name = f"part-{number:06d}.tsv"
        if (
            part["name"] != name
            or type(part["number"]) is not int
            or part["number"] != number
            or type(part["rows"]) is not int
            or part["rows"] != 1000
            or type(part["sha256"]) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", part["sha256"])
        ):
            raise RuntimeError("resume interruption part contract changed")
        first_cursor = strict_canonical_cursor(
            part["first_cursor"], "resume interruption part first"
        )
        last_cursor = strict_canonical_cursor(
            part["last_cursor"], "resume interruption part last"
        )
        path = job / "parts" / name
        try:
            observed = canonical_tsv_part_metadata(path)
        except RuntimeError as error:
            raise RuntimeError(
                "resume interruption part cursor or bytes changed"
            ) from error
        if (
            not _canonical_json_equal(observed["first_cursor"], first_cursor)
            or not _canonical_json_equal(observed["last_cursor"], last_cursor)
            or observed["rows"] != part["rows"]
            or observed["sha256"] != part["sha256"]
        ):
            raise RuntimeError("resume interruption part cursor or bytes changed")
        if previous_last is not None and first_cursor <= previous_last:
            raise RuntimeError("resume interruption part cursor order changed")
        validated.append(dict(part))
        previous_last = last_cursor
    return validated


def validate_resume_interruption_audit(runtime_root: Path) -> dict[str, object]:
    """Re-read the immutable pre-resume checkpoint and bind it to part bytes."""
    root = Path(runtime_root)
    job = root / "job-resume-1"
    try:
        audit = json.loads(
            (root / RESUME_INTERRUPTION_AUDIT).read_text(encoding="utf-8")
        )
        state = json.loads((job / "state.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError("resume interruption audit is unreadable") from error
    fields = {
        "artifact_exists",
        "checkpoint_state",
        "checkpoint_state_sha256",
        "job_id",
        "next_part",
        "part_count",
        "parts",
        "recorded_at",
        "result_exists",
        "rows_written",
        "status",
    }
    if type(audit) is not dict or set(audit) != fields:
        raise RuntimeError("resume interruption audit fields are not exact")
    try:
        recorded_at = datetime.fromisoformat(
            str(audit["recorded_at"]).replace("Z", "+00:00")
        )
    except ValueError as error:
        raise RuntimeError("resume interruption timestamp is invalid") from error
    if (
        audit["status"] != "ABORTED"
        or audit["job_id"] != "resume-1"
        or type(audit["rows_written"]) is not int
        or audit["rows_written"] != 3000
        or type(audit["part_count"]) is not int
        or audit["part_count"] != 3
        or type(audit["next_part"]) is not int
        or audit["next_part"] != 4
        or audit["artifact_exists"] is not False
        or audit["result_exists"] is not False
        or type(audit["recorded_at"]) is not str
        or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z", audit["recorded_at"])
        or recorded_at.tzinfo != timezone.utc
        or type(audit["checkpoint_state"]) is not dict
        or not _canonical_json_equal(audit["checkpoint_state"], state)
        or audit["checkpoint_state_sha256"] != _checkpoint_state_sha256(state)
        or state.get("status") != "ABORTED"
        or state.get("job_id") != "resume-1"
        or type(state.get("rows_written")) is not int
        or state["rows_written"] != 3000
        or type(state.get("next_part")) is not int
        or state["next_part"] != 4
        or job.joinpath("artifact.tsv").exists()
        or job.joinpath("result.json").exists()
    ):
        raise RuntimeError("resume interruption audit contract changed")
    state_high = strict_canonical_cursor(
        [state.get("high_created_at"), state.get("high_id")],
        "resume interruption checkpoint high",
    )
    state_last = strict_canonical_cursor(
        [state.get("last_created_at"), state.get("last_id")],
        "resume interruption checkpoint last",
    )
    parts = _validated_resume_parts(job, state.get("parts"))
    audit_parts = _validated_resume_parts(job, audit.get("parts"))
    derived_rows = sum(part["rows"] for part in parts)
    if (
        not _canonical_json_equal(audit_parts, parts)
        or audit["part_count"] != len(parts)
        or audit["next_part"] != len(parts) + 1
        or state["rows_written"] != derived_rows
        or state["next_part"] != len(parts) + 1
    ):
        raise RuntimeError("resume interruption audit part prefix changed")
    if not _canonical_json_equal(state_last, parts[-1]["last_cursor"]):
        raise RuntimeError("resume interruption checkpoint last cursor changed")
    if state_high < state_last:
        raise RuntimeError("resume interruption checkpoint high cursor changed")
    return audit


def write_resume_interruption_audit(
    runtime_root: Path, state: dict[str, object]
) -> dict[str, object]:
    """Atomically retain the state that will otherwise be overwritten by resume."""
    root = Path(runtime_root)
    job = root / "job-resume-1"
    parts = _validated_resume_parts(job, state.get("parts"))
    audit = {
        "artifact_exists": False,
        "checkpoint_state": state,
        "checkpoint_state_sha256": _checkpoint_state_sha256(state),
        "job_id": "resume-1",
        "next_part": 4,
        "part_count": 3,
        "parts": parts,
        "recorded_at": _utc_text(),
        "result_exists": False,
        "rows_written": 3000,
        "status": "ABORTED",
    }
    write_immutable_json(root / RESUME_INTERRUPTION_AUDIT, audit)
    validate_resume_interruption_audit(root)
    return audit


class HarnessStateMachine:
    """Execute the reviewed phase order exactly once, with no retry path."""

    def __init__(
        self,
        *,
        runtime_root: Path,
        binding: EvidenceBinding,
        ledger: InvocationLedger,
        environment: Mapping[str, str],
        launch: Launch,
        create_manifest: ManifestWriter,
        teardown: Teardown,
        prepare: Callable[[], object] | None = None,
        phase_audit: Callable[[str], object] | None = None,
        external_audit: Callable[[], object] | None = None,
    ):
        self.runtime_root = Path(runtime_root)
        self.binding = binding
        self.ledger = ledger
        self.environment = environment
        self.launch = launch
        self.create_manifest = create_manifest
        self.teardown = teardown
        self.prepare = prepare or (lambda: None)
        self.phase_audit = phase_audit or (lambda phase: None)
        self.external_audit = external_audit or (lambda: None)

    def execute(self, invocation_id: str) -> dict[str, object]:
        command = build_invocation_command(invocation_id, self.runtime_root)
        stdout_path = self.runtime_root / f"harness-{invocation_id}.stdout.json"
        stderr_path = self.runtime_root / f"harness-{invocation_id}.stderr.txt"
        if invocation_id == "resume-complete-1":
            validate_resume_interruption_audit(self.runtime_root)
        self.ledger.start(invocation_id)
        try:
            result = self.launch(
                invocation_id, command, self.environment, stdout_path, stderr_path
            )
        except BaseException as error:
            self.ledger.finish(
                invocation_id,
                "UNKNOWN",
                {"error": f"{type(error).__name__}: {error}"},
            )
            raise
        if type(result) is not dict:
            self.ledger.finish(invocation_id, "FAILED", {"error": "non-object result"})
            raise RuntimeError(f"{invocation_id} returned malformed evidence")
        try:
            returncode = result.get("returncode")
            status = result.get("status")
            expected_status = (
                "ABORTED" if invocation_id == "resume-interrupt-1" else "SUCCEEDED"
            )
            if type(returncode) is not int or returncode != 0 or status != expected_status:
                raise RuntimeError(
                    f"{invocation_id} stopped with returncode={returncode!r} "
                    f"status={status!r}"
                )
            if invocation_id == "resume-interrupt-1":
                state = json.loads(
                    (self.runtime_root / "job-resume-1" / "state.json").read_text(
                        encoding="utf-8"
                    )
                )
                if (
                    state.get("status") != "ABORTED"
                    or state.get("rows_written") != 3000
                    or state.get("next_part") != 4
                    or len(state.get("parts", [])) != 3
                    or result.get("rows") != 3000
                    or result.get("parts") != 3
                    or (self.runtime_root / "job-resume-1" / "artifact.tsv").exists()
                    or (self.runtime_root / "job-resume-1" / "result.json").exists()
                ):
                    raise RuntimeError("resume interruption checkpoint is invalid")
                write_resume_interruption_audit(self.runtime_root, state)
            if invocation_id == "resume-complete-1":
                job = self.runtime_root / "job-resume-1"
                state = json.loads((job / "state.json").read_text(encoding="utf-8"))
                persisted = json.loads(
                    (job / "result.json").read_text(encoding="utf-8")
                )
                if (
                    state.get("status") != "SUCCEEDED"
                    or persisted.get("status") != "SUCCEEDED"
                    or not (job / "artifact.tsv").is_file()
                    or persisted
                    != {
                        key: value
                        for key, value in result.items()
                        if key != "returncode"
                    }
                ):
                    raise RuntimeError("resume completion evidence is invalid")
        except BaseException as error:
            self.ledger.finish(
                invocation_id,
                "FAILED",
                {
                    "error": f"{type(error).__name__}: {error}",
                    "outcome": result,
                },
            )
            raise
        self.ledger.finish(invocation_id, expected_status, result)
        return result

    def _failure_record(self, error: BaseException) -> None:
        target = self.runtime_root / "failed-phase.json"
        if target.exists() or target.is_symlink():
            return
        write_immutable_json(
            target,
            {
                "error": f"{type(error).__name__}: {error}",
                "status": "FAILED",
                "timestamp": _utc_text(),
            },
        )

    def run(self) -> None:
        succeeded = False
        primary_error: BaseException | None = None
        failure_record_error: BaseException | None = None
        teardown_error: BaseException | None = None
        try:
            self.prepare()
            self.create_manifest(self.runtime_root, PHASES[0], self.binding)
            for phase in PHASES[1:-1]:
                for invocation_id in PHASE_INVOCATIONS[phase]:
                    self.execute(invocation_id)
                if phase == "50-resume-audit":
                    self.external_audit()
                self.phase_audit(phase)
                self.ledger.checkpoint(phase)
                self.create_manifest(self.runtime_root, phase, self.binding)
            succeeded = True
        except BaseException as error:
            primary_error = error
        try:
            if primary_error is not None:
                try:
                    self._failure_record(primary_error)
                except BaseException as error:
                    failure_record_error = error
        finally:
            try:
                self.teardown(succeeded)
            except BaseException as error:
                teardown_error = error
        if primary_error is not None:
            if failure_record_error is not None:
                primary_error = _combined_error(
                    primary_error, failure_record_error, "failure record failed"
                )
            if teardown_error is not None:
                primary_error = _combined_error(
                    primary_error, teardown_error, "controlled teardown failed"
                )
            raise primary_error
        if teardown_error is not None:
            raise teardown_error
        self.create_manifest(self.runtime_root, PHASES[-1], self.binding)


def default_launch(
    invocation_id: str,
    command: tuple[str, ...],
    environment: Mapping[str, str],
    stdout_path: Path,
    stderr_path: Path,
) -> dict[str, object]:
    """Launch once, preserving both streams and parsing the final JSON object."""
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        completed = subprocess.run(
            command,
            env=dict(environment),
            stdout=stdout,
            stderr=stderr,
            check=False,
        )
    document: dict[str, object] = {}
    lines = stdout_path.read_text(encoding="utf-8").splitlines()
    if lines:
        try:
            candidate = json.loads(lines[-1])
        except json.JSONDecodeError:
            candidate = None
        if type(candidate) is dict:
            document = candidate
    document["returncode"] = completed.returncode
    return document


def offline_check(scenario_path: Path, python_inputs: list[Path]) -> dict[str, object]:
    """Extract and compile all six Python inputs without Docker/MySQL effects."""
    connector_module, _, _ = _default_connector_boundary()
    connector = _connector_environment(connector_module)
    scenario_text = scenario_path.read_text(encoding="utf-8")
    programs, hashes = _reviewed_programs(scenario_text)
    with tempfile.TemporaryDirectory(prefix="mysql-senior-offline-") as temporary:
        root = Path(temporary)
        _materialize_programs(root, programs)
        for source in python_inputs:
            py_compile.compile(str(source), doraise=True)
    return {
        "connector": connector,
        "program_sha256": hashes,
        "python_inputs": [str(path) for path in python_inputs],
        "status": "OFFLINE_CHECK_COMPLETE",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    offline = subparsers.add_parser("offline-check")
    offline.add_argument("--scenario", type=Path, required=True)
    offline.add_argument("--python-input", type=Path, action="append", required=True)
    live = subparsers.add_parser("run-all")
    live.add_argument("--scenario", type=Path, required=True)
    live.add_argument("--expected-commit", required=True)
    live.add_argument("--volume-root", type=Path, default=Path("/private/tmp"))
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "offline-check":
        print(
            json.dumps(
                offline_check(args.scenario, args.python_input), sort_keys=True
            )
        )
        return 0
    boundary = BootstrapBoundary.live()
    context = prepare_bootstrap(
        args.volume_root, args.scenario, args.expected_commit, boundary
    )
    def run_machine(
        live_context: BootstrapContext,
        database: ExperimentDatabase,
        teardown: ControlledTeardownOnce,
    ) -> None:
        machine = HarnessStateMachine(
            runtime_root=live_context.runtime_root,
            binding=live_context.binding,
            ledger=InvocationLedger(live_context.runtime_root / "invocations.jsonl"),
            environment=dict(boundary.environ),
            launch=default_launch,
            create_manifest=create_phase_manifest,
            prepare=database.prepare,
            phase_audit=database.phase_audit,
            external_audit=database.external_audit,
            teardown=teardown,
        )
        machine.run()

    run_all_lifecycle(
        context=context,
        boundary=boundary,
        database_factory=ExperimentDatabase,
        connector_verifier=verify_connector_contract,
        connector_writer=write_immutable_json,
        machine_runner=run_machine,
    )
    print(
        json.dumps(
            {
                "runtime_root": str(context.runtime_root),
                "status": "COMPLETE",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
