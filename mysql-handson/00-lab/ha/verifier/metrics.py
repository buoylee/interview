from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from verifier.verify import connect


def collect(phase: str) -> dict:
    members = {}
    for host in ("db1", "db2", "db3"):
        connection = None
        cursor = None
        try:
            connection = connect(host)
            cursor = connection.cursor()
            cursor.execute(
                "SELECT COUNT_TRANSACTIONS_REMOTE_IN_APPLIER_QUEUE "
                "FROM performance_schema.replication_group_member_stats "
                "WHERE MEMBER_ID=@@server_uuid"
            )
            row = cursor.fetchone()
            cursor.execute(
                "SELECT @@GLOBAL.group_replication_flow_control_applier_threshold, "
                "@@GLOBAL.group_replication_flow_control_mode"
            )
            threshold, mode = cursor.fetchone()
            members[host] = {
                "applier_queue": int(row[0]) if row else 0,
                "flow_control_applier_threshold": int(threshold),
                "flow_control_mode": str(mode),
            }
        finally:
            try:
                if cursor is not None:
                    cursor.close()
            finally:
                if connection is not None:
                    connection.close()
    return {
        "phase": phase,
        "at": datetime.now(timezone.utc).isoformat(),
        "members": members,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=("before", "active"))
    parser.add_argument("--output", type=Path, default=Path("/evidence/metrics.jsonl"))
    args = parser.parse_args()
    snapshot = collect(args.phase)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(snapshot, sort_keys=True) + "\n")
    print(json.dumps(snapshot, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
