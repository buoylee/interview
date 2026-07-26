from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
from typing import Any

from workload.model import JsonlLedger, LedgerRecord, Outcome


def evaluate(
    records: list[LedgerRecord],
    member_ids: dict[str, list[str]],
    topology: list[dict[str, str]],
    expected_online: int,
    convergence_errors: list[str] | None = None,
) -> dict[str, Any]:
    errors: list[str] = list(convergence_errors or [])
    canonical_rows = next(iter(member_ids.values()), [])
    canonical = set(canonical_rows)
    acknowledged = sorted({r.request_id for r in records if r.outcome is Outcome.SUCCESS})
    unknown_ids = sorted({r.request_id for r in records if r.outcome is Outcome.UNKNOWN})

    for request_id in acknowledged:
        if request_id not in canonical:
            errors.append(f"acknowledged request missing: {request_id}")

    counts = Counter(canonical_rows)
    if any(count != 1 for count in counts.values()):
        errors.append("duplicate business result detected")

    snapshots = [set(rows) for rows in member_ids.values()]
    if snapshots and any(snapshot != snapshots[0] for snapshot in snapshots[1:]):
        errors.append("online member data diverged")

    online = [member for member in topology if member["state"] == "ONLINE"]
    primaries = [member for member in online if member["role"] == "PRIMARY"]
    if len(online) != expected_online:
        errors.append(f"expected {expected_online} ONLINE members, got {len(online)}")
    if len(primaries) != 1:
        errors.append(f"expected exactly one ONLINE PRIMARY, got {len(primaries)}")

    return {
        "ok": not errors,
        "errors": errors,
        "outcomes": dict(Counter(record.outcome.value for record in records)),
        "acknowledged": len(acknowledged),
        "unknown": {
            "committed": [value for value in unknown_ids if value in canonical],
            "absent": [value for value in unknown_ids if value not in canonical],
        },
        "members": {host: len(ids) for host, ids in member_ids.items()},
        "topology": topology,
    }


def connect(host: str, user: str | None = None, password: str | None = None):
    import mysql.connector

    return mysql.connector.connect(
        host=host,
        port=3306,
        user=user or os.getenv("MYSQL_CLUSTER_ADMIN", "icadmin"),
        password=password or os.getenv("MYSQL_CLUSTER_ADMIN_PASSWORD", "ha-cluster"),
        connection_timeout=3,
    )


def fetch_ids(host: str) -> list[str]:
    connection = connect(
        host,
        os.getenv("MYSQL_APP_USER", "ha_app"),
        os.getenv("MYSQL_APP_PASSWORD", "ha-app"),
    )
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT request_id FROM ha_lab.orders ORDER BY request_id")
        return [row[0] for row in cursor.fetchall()]
    finally:
        connection.close()


def fetch_topology() -> list[dict[str, str]]:
    for seed in ("db1", "db2", "db3"):
        try:
            connection = connect(seed)
            cursor = connection.cursor()
            cursor.execute(
                "SELECT MEMBER_HOST, MEMBER_ROLE, MEMBER_STATE "
                "FROM performance_schema.replication_group_members ORDER BY MEMBER_HOST"
            )
            rows = [
                {"host": host, "role": role, "state": state}
                for host, role, state in cursor.fetchall()
            ]
            connection.close()
            return rows
        except Exception:
            continue
    return []


def fetch_gtid_executed(host: str) -> str:
    connection = connect(host)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT @@GLOBAL.gtid_executed")
        return str(cursor.fetchone()[0])
    finally:
        connection.close()


def wait_for_gtid(host: str, gtid_set: str, timeout_seconds: int = 30) -> bool:
    connection = connect(host)
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT WAIT_FOR_EXECUTED_GTID_SET(%s, %s)",
            (gtid_set, timeout_seconds),
        )
        return int(cursor.fetchone()[0]) == 0
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, default=Path("/evidence"))
    parser.add_argument("--expected-online", type=int, default=3)
    args = parser.parse_args()

    records = JsonlLedger.load(args.evidence_dir.glob("ledger-*.jsonl"))
    topology = fetch_topology()
    online_hosts = [row["host"] for row in topology if row["state"] == "ONLINE"]
    primary_hosts = [
        row["host"] for row in topology
        if row["state"] == "ONLINE" and row["role"] == "PRIMARY"
    ]
    convergence_errors: list[str] = []
    if len(primary_hosts) == 1:
        primary_gtid = fetch_gtid_executed(primary_hosts[0])
        for host in online_hosts:
            if not wait_for_gtid(host, primary_gtid):
                convergence_errors.append(
                    f"{host} did not apply the Primary GTID set"
                )
    else:
        convergence_errors.append(
            f"GTID barrier requires exactly one ONLINE PRIMARY, got {len(primary_hosts)}"
        )
    member_ids = {host: fetch_ids(host) for host in online_hosts}
    report = evaluate(
        records,
        member_ids,
        topology,
        args.expected_online,
        convergence_errors,
    )
    output = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    (args.evidence_dir / "verification.json").write_text(output + "\n", encoding="utf-8")
    print(output)
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
