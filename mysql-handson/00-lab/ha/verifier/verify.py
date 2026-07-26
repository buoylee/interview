from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
from typing import Any

from workload.model import JsonlLedger, LedgerRecord, Outcome


class TopologyCollectionError(RuntimeError):
    def __init__(self, failures: list[tuple[str, str]]):
        self.failures = failures
        super().__init__("; ".join(f"{host}: {error_type}" for host, error_type in failures))


def evaluate(
    records: list[LedgerRecord],
    member_ids: dict[str, list[str]],
    topology: list[dict[str, str]],
    expected_online: int,
    convergence_errors: list[str] | None = None,
) -> dict[str, Any]:
    errors: list[str] = list(convergence_errors or [])
    online = [member for member in topology if member.get("state") == "ONLINE"]
    online_hosts = sorted(member["host"] for member in online)
    primaries = [member for member in online if member.get("role") == "PRIMARY"]
    primary_hosts = sorted(member["host"] for member in primaries)
    missing_snapshots = [host for host in online_hosts if host not in member_ids]
    for host in missing_snapshots:
        errors.append(f"missing member snapshot: {host}")

    canonical_rows = member_ids.get(primary_hosts[0], []) if len(primary_hosts) == 1 else []
    canonical = set(canonical_rows)
    acknowledged = sorted({r.request_id for r in records if r.outcome is Outcome.SUCCESS})
    unknown_ids = sorted({r.request_id for r in records if r.outcome is Outcome.UNKNOWN})

    snapshots = {
        host: Counter(member_ids[host])
        for host in online_hosts
        if host in member_ids
    }
    if any(any(count != 1 for count in rows.values()) for rows in snapshots.values()):
        errors.append("duplicate business result detected")
    snapshots_complete = not missing_snapshots and len(primary_hosts) == 1
    snapshots_converged = (
        snapshots_complete
        and all(
            snapshot == snapshots[primary_hosts[0]]
            for snapshot in snapshots.values()
        )
    )
    if snapshots_complete and not snapshots_converged:
        errors.append("online member data diverged")

    if len(online) != expected_online:
        errors.append(f"expected {expected_online} ONLINE members, got {len(online)}")
    if len(primaries) != 1:
        errors.append(f"expected exactly one ONLINE PRIMARY, got {len(primaries)}")

    reconciliation_complete = (
        snapshots_converged
        and len(online) == expected_online
        and not convergence_errors
    )
    if reconciliation_complete:
        for request_id in acknowledged:
            if request_id not in canonical:
                errors.append(f"acknowledged request missing: {request_id}")

    return {
        "ok": not errors,
        "errors": errors,
        "outcomes": dict(Counter(record.outcome.value for record in records)),
        "acknowledged": len(acknowledged),
        "unknown": {
            "committed": (
                [value for value in unknown_ids if value in canonical]
                if reconciliation_complete else []
            ),
            "absent": (
                [value for value in unknown_ids if value not in canonical]
                if reconciliation_complete else []
            ),
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
    connection = None
    cursor = None
    try:
        connection = connect(
            host,
            os.getenv("MYSQL_APP_USER", "ha_app"),
            os.getenv("MYSQL_APP_PASSWORD", "ha-app"),
        )
        cursor = connection.cursor()
        cursor.execute("SELECT request_id FROM ha_lab.orders ORDER BY request_id")
        return [row[0] for row in cursor.fetchall()]
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()


def fetch_topology() -> list[dict[str, str]]:
    failures: list[tuple[str, str]] = []
    for seed in ("db1", "db2", "db3"):
        connection = None
        cursor = None
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
            return rows
        except Exception as error:
            failures.append((seed, type(error).__name__))
        finally:
            try:
                if cursor is not None:
                    cursor.close()
            finally:
                if connection is not None:
                    connection.close()
    raise TopologyCollectionError(failures)


def fetch_gtid_executed(host: str) -> str:
    connection = None
    cursor = None
    try:
        connection = connect(host)
        cursor = connection.cursor()
        cursor.execute("SELECT @@GLOBAL.gtid_executed")
        return str(cursor.fetchone()[0])
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()


def wait_for_gtid(host: str, gtid_set: str, timeout_seconds: int = 30) -> bool:
    connection = None
    cursor = None
    try:
        connection = connect(host)
        cursor = connection.cursor()
        cursor.execute(
            "SELECT WAIT_FOR_EXECUTED_GTID_SET(%s, %s)",
            (gtid_set, timeout_seconds),
        )
        return int(cursor.fetchone()[0]) == 0
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()


def write_report(evidence_dir: Path, report: dict[str, Any]) -> None:
    output = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "verification.json").write_text(output + "\n", encoding="utf-8")
    print(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, default=Path("/evidence"))
    parser.add_argument("--expected-online", type=int, default=3)
    args = parser.parse_args()

    records: list[LedgerRecord] = []
    collection_errors: list[str] = []
    try:
        records = JsonlLedger.load(args.evidence_dir.glob("ledger-*.jsonl"))
    except Exception as error:
        collection_errors.append(f"ledger collection failed: {type(error).__name__}")
    try:
        topology = fetch_topology()
    except TopologyCollectionError as error:
        topology = []
        collection_errors.extend(
            f"topology query failed on {host}: {error_type}"
            for host, error_type in error.failures
        )
    except Exception as error:
        topology = []
        collection_errors.append(f"topology collection failed: {type(error).__name__}")

    online_hosts = sorted(
        row["host"] for row in topology if row.get("state") == "ONLINE"
    )
    primary_hosts = [
        row["host"] for row in topology
        if row.get("state") == "ONLINE" and row.get("role") == "PRIMARY"
    ]
    convergence_errors: list[str] = collection_errors
    if len(primary_hosts) == 1:
        primary_host = primary_hosts[0]
        try:
            primary_gtid = fetch_gtid_executed(primary_host)
        except Exception as error:
            convergence_errors.append(
                f"failed to fetch Primary GTID from {primary_host}: {type(error).__name__}"
            )
        else:
            for host in online_hosts:
                try:
                    caught_up = wait_for_gtid(host, primary_gtid)
                except Exception as error:
                    convergence_errors.append(
                        f"GTID barrier check failed on {host}: {type(error).__name__}"
                    )
                else:
                    if not caught_up:
                        convergence_errors.append(
                            f"{host} did not apply the Primary GTID set"
                        )
    else:
        convergence_errors.append(
            f"GTID barrier requires exactly one ONLINE PRIMARY, got {len(primary_hosts)}"
        )
    member_ids: dict[str, list[str]] = {}
    for host in online_hosts:
        try:
            member_ids[host] = fetch_ids(host)
        except Exception as error:
            convergence_errors.append(
                f"member snapshot failed on {host}: {type(error).__name__}"
            )
    report = evaluate(
        records,
        member_ids,
        topology,
        args.expected_online,
        convergence_errors,
    )
    write_report(args.evidence_dir, report)
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
