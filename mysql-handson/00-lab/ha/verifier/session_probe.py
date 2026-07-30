from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any

import mysql.connector


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(router: str):
    return mysql.connector.connect(
        host=router,
        port=6446,
        user=os.getenv("MYSQL_APP_USER", "ha_app"),
        password=os.getenv("MYSQL_APP_PASSWORD", "ha-app"),
        database="ha_lab",
        connection_timeout=1,
        read_timeout=1,
        write_timeout=1,
    )


def backend(connection) -> str:
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT @@hostname")
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("Router backend did not return a hostname")
        return str(row[0])
    finally:
        if cursor is not None:
            cursor.close()


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


def write_report(evidence_dir: Path, report: dict[str, Any]) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    (evidence_dir / "session.json").write_text(output, encoding="utf-8")
    print(output, end="")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--router", default="router-a")
    parser.add_argument("--evidence-dir", type=Path, default=Path("/evidence"))
    parser.add_argument("--timeout-seconds", type=float, default=45.0)
    args = parser.parse_args()
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + args.timeout_seconds
    old_connection = None
    report: dict[str, Any] = {
        "old_backend": None,
        "existing_session_disconnected": False,
        "disconnected_at": None,
        "new_backend": None,
        "reconnected_at": None,
    }
    error: str | None = None
    try:
        old_connection = connect(args.router)
        report["old_backend"] = backend(old_connection)
        (args.evidence_dir / "session-ready").write_text(
            f"{report['old_backend']}\n", encoding="utf-8"
        )
        wait_for_phase(args.evidence_dir / "events.jsonl", "fault_active", deadline)

        while time.monotonic() < deadline:
            try:
                backend(old_connection)
            except Exception:
                report["existing_session_disconnected"] = True
                report["disconnected_at"] = now()
                break
            time.sleep(0.1)

        while report["existing_session_disconnected"] and time.monotonic() < deadline:
            connection = None
            try:
                connection = connect(args.router)
                candidate = backend(connection)
                if candidate != report["old_backend"]:
                    report["new_backend"] = candidate
                    report["reconnected_at"] = now()
                    break
            except Exception:
                pass
            finally:
                if connection is not None:
                    try:
                        connection.close()
                    except Exception:
                        pass
            time.sleep(0.1)
    except Exception as caught:
        error = f"{type(caught).__name__}: {caught}"
    finally:
        if old_connection is not None:
            try:
                old_connection.close()
            except Exception:
                pass

    if error:
        report["error"] = error
    write_report(args.evidence_dir, report)
    raise SystemExit(
        0
        if error is None
        and report["existing_session_disconnected"]
        and report["new_backend"]
        else 1
    )


if __name__ == "__main__":
    main()
