from __future__ import annotations

import argparse
from collections.abc import Callable
import json
import os
from pathlib import Path
import signal
import time
import uuid

from workload.client import execute_order
from workload.model import JsonlLedger, LedgerRecord, OrderRequest


Execute = Callable[[Callable[[], object], OrderRequest, int], LedgerRecord]
running = True


def stop(_signum, _frame) -> None:
    global running
    running = False


def run_workload(
    router_label: str,
    ledger_path: Path,
    max_requests: int,
    interval_ms: int,
    connect: Callable[[], object],
    execute: Execute = execute_order,
) -> None:
    ledger = JsonlLedger(ledger_path)
    sent = 0
    while running and (max_requests == 0 or sent < max_requests):
        request = OrderRequest(
            request_id=f"{router_label}-{uuid.uuid4()}",
            payload=json.dumps({"item": "book", "sequence": sent}),
            router=router_label,
        )
        ledger.append(execute(connect, request, 2))
        sent += 1
        time.sleep(interval_ms / 1000)


def main() -> None:
    import mysql.connector

    parser = argparse.ArgumentParser()
    parser.add_argument("--router-label", required=True)
    parser.add_argument("--router-host", required=True)
    parser.add_argument("--max-requests", type=int, default=0)
    parser.add_argument("--interval-ms", type=int, default=100)
    args = parser.parse_args()

    def connect():
        return mysql.connector.connect(
            host=args.router_host,
            port=6446,
            user=os.getenv("MYSQL_APP_USER", "ha_app"),
            password=os.getenv("MYSQL_APP_PASSWORD", "ha-app"),
            database="ha_lab",
            autocommit=False,
            connection_timeout=2,
            read_timeout=3,
            write_timeout=3,
        )

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    run_workload(
        args.router_label,
        Path(f"/evidence/ledger-{args.router_label}.jsonl"),
        args.max_requests,
        args.interval_ms,
        connect,
    )


if __name__ == "__main__":
    main()
