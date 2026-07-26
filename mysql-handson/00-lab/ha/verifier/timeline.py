from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from verifier.verify import connect, fetch_topology


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append(path: Path, phase: str, **fields: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps({"at": now(), "phase": phase, **fields}, sort_keys=True)
            + "\n"
        )


def router_target(host: str) -> str | None:
    import mysql.connector

    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(
            host=host,
            port=6446,
            user=os.getenv("MYSQL_APP_USER", "ha_app"),
            password=os.getenv("MYSQL_APP_PASSWORD", "ha-app"),
            database="ha_lab",
            connection_timeout=1,
            read_timeout=1,
            write_timeout=1,
        )
        cursor = connection.cursor()
        cursor.execute("SELECT @@hostname")
        row = cursor.fetchone()
        return str(row[0]) if row else None
    except Exception:
        return None
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()


def member_is_writable(host: str) -> bool:
    connection = None
    cursor = None
    try:
        connection = connect(host)
        cursor = connection.cursor()
        cursor.execute("SELECT @@super_read_only, @@offline_mode")
        row = cursor.fetchone()
        if not row:
            return False
        super_read_only, offline_mode = row
        return int(super_read_only) == 0 and int(offline_mode) == 0
    except Exception:
        return False
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()


def wait_for_phase(events: Path, phase: str, deadline: float) -> None:
    while time.monotonic() < deadline:
        if events.exists():
            for line in events.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as error:
                    raise RuntimeError("events evidence is malformed") from error
                if event.get("phase") == phase:
                    return
        time.sleep(0.05)
    raise TimeoutError(f"event not observed: {phase}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-primary", required=True)
    parser.add_argument("--evidence-dir", type=Path, default=Path("/evidence"))
    parser.add_argument("--timeout-seconds", type=float, default=45.0)
    args = parser.parse_args()
    events = args.evidence_dir / "events.jsonl"
    output = args.evidence_dir / "timeline.jsonl"
    deadline = time.monotonic() + args.timeout_seconds
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    (args.evidence_dir / "timeline-ready").write_text(
        f"{args.old_primary}\n", encoding="utf-8"
    )
    try:
        wait_for_phase(events, "fault_begin", deadline)
    except Exception as error:
        raise SystemExit(str(error)) from error

    detected = False
    elected: str | None = None
    writable = False
    while time.monotonic() < deadline:
        try:
            topology = fetch_topology()
        except Exception:
            time.sleep(0.1)
            continue
        old = next((row for row in topology if row["host"] == args.old_primary), None)
        if not detected and (
            old is None or old["state"] != "ONLINE" or old["role"] != "PRIMARY"
        ):
            append(output, "failure_detected", old_primary=args.old_primary)
            detected = True
        primary = next(
            (
                row["host"]
                for row in topology
                if row["state"] == "ONLINE"
                and row["role"] == "PRIMARY"
                and row["host"] != args.old_primary
            ),
            None,
        )
        if detected and primary and elected is None:
            elected = primary
            append(output, "primary_elected", new_primary=primary)
        if elected and not writable and member_is_writable(elected):
            append(output, "primary_writable", new_primary=elected)
            writable = True
        if elected and writable:
            for router in ("router-a", "router-b"):
                if router_target(router) == elected:
                    append(output, "router_ready", router=router, new_primary=elected)
                    return
        time.sleep(0.1)
    raise SystemExit("failover timeline did not complete")


if __name__ == "__main__":
    main()
