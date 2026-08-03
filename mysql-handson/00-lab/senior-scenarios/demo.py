"""Small, retryable Docker-only report/export demonstration."""

from __future__ import annotations

import argparse
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from typing import Callable, Iterable, Sequence


DATABASE = "senior_demo"
ORDER_ROWS = 10_000
ITEM_ROWS = 30_000
PROBE_ROWS = 1_000
EXPORT_SQL = """
SELECT o.id, i.id, o.created_at, o.status, i.qty, i.unit_price
FROM report_order AS o
JOIN report_item AS i ON i.order_id = o.id
ORDER BY o.created_at, o.id, i.id
"""


def _field(value: object) -> str:
    if value is None:
        return r"\N"
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="microseconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    text = str(value)
    if "\t" in text or "\r" in text or "\n" in text:
        raise ValueError("TSV values may not contain tabs or newlines")
    return text


def canonical_row(values: Sequence[object]) -> bytes:
    return ("\t".join(_field(value) for value in values) + "\n").encode("utf-8")


def _write_rows(rows: Iterable[Sequence[object]], output_path: Path) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    count = 0
    first_key = None
    last_key = None
    started = time.perf_counter()
    with output_path.open("wb") as output:
        for row in rows:
            data = canonical_row(row)
            output.write(data)
            digest.update(data)
            key = [int(row[0]), int(row[1])]
            if first_key is None:
                first_key = key
            last_key = key
            count += 1
    return {
        "rows": count,
        "first_key": first_key,
        "last_key": last_key,
        "sha256": digest.hexdigest(),
        "elapsed_seconds": round(time.perf_counter() - started, 6),
    }


def _begin_snapshot(cursor) -> None:
    cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT")


def _finish_snapshot(connection) -> None:
    commit = getattr(connection, "commit", None)
    if callable(commit):
        commit()


def export_buffered(connection, output_path: Path) -> dict:
    cursor = connection.cursor()
    try:
        _begin_snapshot(cursor)
        cursor.execute(EXPORT_SQL)
        result = _write_rows(cursor.fetchall(), output_path)
        _finish_snapshot(connection)
        return result
    finally:
        cursor.close()


def export_chunked(connection, output_path: Path, batch_size: int = 1000) -> dict:
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError("batch_size must be a positive integer")
    cursor = connection.cursor()

    def batches():
        while True:
            batch = cursor.fetchmany(batch_size)
            if not batch:
                return
            yield from batch

    try:
        _begin_snapshot(cursor)
        cursor.execute(EXPORT_SQL)
        result = _write_rows(batches(), output_path)
        _finish_snapshot(connection)
        return result
    finally:
        cursor.close()


def _execute_all(cursor, statements: Sequence[str]) -> None:
    for statement in statements:
        cursor.execute(statement)


def prepare_database(connection_factory: Callable[..., object]) -> None:
    admin = connection_factory(database=None)
    cursor = admin.cursor()
    try:
        _execute_all(
            cursor,
            (
                "DROP DATABASE IF EXISTS senior_demo",
                "CREATE DATABASE senior_demo CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci",
            ),
        )
    finally:
        cursor.close()
        admin.close()

    connection = connection_factory(database=DATABASE)
    cursor = connection.cursor()
    try:
        _execute_all(
            cursor,
            (
                """CREATE TABLE report_order (
                       id BIGINT PRIMARY KEY,
                       created_at DATETIME(6) NOT NULL,
                       status VARCHAR(16) NOT NULL,
                       KEY idx_created_id (created_at, id)
                   ) ENGINE=InnoDB""",
                """CREATE TABLE report_item (
                       id BIGINT PRIMARY KEY,
                       order_id BIGINT NOT NULL,
                       qty INT NOT NULL,
                       unit_price DECIMAL(10,2) NOT NULL,
                       KEY idx_order_id (order_id, id),
                       CONSTRAINT fk_demo_item_order FOREIGN KEY (order_id)
                           REFERENCES report_order(id)
                   ) ENGINE=InnoDB""",
                """CREATE TABLE oltp_probe (
                       id INT PRIMARY KEY,
                       counter BIGINT NOT NULL DEFAULT 0
                   ) ENGINE=InnoDB""",
                "CREATE TEMPORARY TABLE seed_digit (n INT PRIMARY KEY)",
                "INSERT INTO seed_digit VALUES (0),(1),(2),(3),(4),(5),(6),(7),(8),(9)",
                """INSERT INTO report_order (id, created_at, status)
                   SELECT n + 1,
                          TIMESTAMP('2025-01-01 00:00:00') + INTERVAL n SECOND,
                          ELT((n MOD 3) + 1, 'paid', 'shipped', 'refunded')
                   FROM (
                       SELECT a.n + 10*b.n + 100*c.n + 1000*d.n AS n
                       FROM seed_digit a CROSS JOIN seed_digit b
                       CROSS JOIN seed_digit c CROSS JOIN seed_digit d
                   ) numbers
                   ORDER BY n""",
                """INSERT INTO report_item (id, order_id, qty, unit_price)
                   SELECT (o.id - 1) * 3 + item_no.n + 1,
                          o.id,
                          (o.id + item_no.n) MOD 5 + 1,
                          CAST(((o.id + item_no.n) MOD 10000 + 100) / 100 AS DECIMAL(10,2))
                   FROM report_order o
                   JOIN (SELECT 0 AS n UNION ALL SELECT 1 UNION ALL SELECT 2) item_no
                   ORDER BY o.id, item_no.n""",
                """INSERT INTO oltp_probe (id, counter)
                   SELECT n + 1, 0
                   FROM (
                       SELECT a.n + 10*b.n + 100*c.n AS n
                       FROM seed_digit a CROSS JOIN seed_digit b CROSS JOIN seed_digit c
                   ) numbers
                   ORDER BY n""",
            ),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def probe_total(connection_factory: Callable[..., object]) -> int:
    connection = connection_factory(database=DATABASE)
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT COALESCE(SUM(counter), 0) FROM oltp_probe")
        row = cursor.fetchone()
        return int(row[0])
    finally:
        cursor.close()
        connection.close()


class OltpWorker:
    def __init__(self, connection_factory: Callable[..., object]):
        self.connection_factory = connection_factory
        self.stop_event = threading.Event()
        self.ready_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="demo-oltp", daemon=True)
        self.error: BaseException | None = None

    def _run(self) -> None:
        connection = None
        cursor = None
        try:
            connection = self.connection_factory(database=DATABASE)
            connection.autocommit = True
            cursor = connection.cursor()
            sequence = 0
            self.ready_event.set()
            while not self.stop_event.is_set():
                probe_id = sequence % PROBE_ROWS + 1
                cursor.execute(
                    "UPDATE oltp_probe SET counter=counter+1 WHERE id=%s",
                    (probe_id,),
                )
                sequence += 1
        except BaseException as error:
            self.error = error
            self.ready_event.set()
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def start(self) -> None:
        self.thread.start()
        if not self.ready_event.wait(timeout=5):
            raise RuntimeError("OLTP worker did not start")
        if self.error is not None:
            raise RuntimeError(f"OLTP worker failed to start: {self.error}")

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=10)
        if self.thread.is_alive():
            raise RuntimeError("OLTP worker did not stop")
        if self.error is not None:
            raise RuntimeError(f"OLTP worker failed: {self.error}")


def _close(connection) -> None:
    close = getattr(connection, "close", None)
    if callable(close):
        close()


def run_demo(connection_factory: Callable[..., object], output_root: Path) -> dict:
    prepare_database(connection_factory)
    worker = OltpWorker(connection_factory)
    worker.start()
    try:
        before_buffered = probe_total(connection_factory)
        buffered_connection = connection_factory(database=DATABASE)
        try:
            buffered = export_buffered(
                buffered_connection, output_root / "buffered.tsv"
            )
        finally:
            _close(buffered_connection)
        after_buffered = probe_total(connection_factory)

        before_chunked = probe_total(connection_factory)
        chunked_connection = connection_factory(database=DATABASE)
        try:
            chunked = export_chunked(
                chunked_connection, output_root / "chunked.tsv", batch_size=1000
            )
        finally:
            _close(chunked_connection)
        after_chunked = probe_total(connection_factory)
    finally:
        worker.stop()

    equality = {
        "rows": buffered["rows"] == chunked["rows"] == ITEM_ROWS,
        "order": (
            buffered["first_key"] == chunked["first_key"]
            and buffered["last_key"] == chunked["last_key"]
        ),
        "sha256": buffered["sha256"] == chunked["sha256"],
    }
    oltp = {
        "buffered_delta": after_buffered - before_buffered,
        "chunked_delta": after_chunked - before_chunked,
    }
    reproduced = all(equality.values()) and all(value > 0 for value in oltp.values())
    return {
        "status": "SCALED_REPRODUCED" if reproduced else "FAILED",
        "scale": {
            "orders": ORDER_ROWS,
            "items": ITEM_ROWS,
            "oltp_probe_rows": PROBE_ROWS,
        },
        "buffered": buffered,
        "chunked": chunked,
        "equality": equality,
        "oltp": oltp,
        "boundaries": {
            "environment": "Docker-only local demonstration",
            "production_capacity_claim": False,
            "snapshot": "one REPEATABLE READ consistent snapshot per export",
        },
    }


def _connection_factory():
    import mysql.connector

    base = {
        "host": os.environ.get("MYSQL_HOST", "mysql-senior-demo-mysql"),
        "port": 3306,
        "user": "root",
        "password": os.environ["MYSQL_PASSWORD"],
        "use_pure": True,
    }

    def connect(*, database=None):
        options = dict(base)
        if database is not None:
            options["database"] = database
        return mysql.connector.connect(**options)

    return connect


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run",))
    args = parser.parse_args()
    if args.command == "run":
        summary = run_demo(_connection_factory(), Path("/work/output"))
        print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
        return 0 if summary["status"] == "SCALED_REPRODUCED" else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
