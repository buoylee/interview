"""Independent read-only verifier for containerized senior-scenario evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import stat
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from container_harness import (
    EXPECTED_MEMORY,
    EXPECTED_NETWORK,
    EXPECTED_PIDS,
    EXPECTED_PROGRAM_SHA256,
    EXPECTED_PROBE_SCHEMA,
    EXPECTED_SEED_MANIFEST,
    EXPECTED_VOLUME,
    FREEZE_TRIGGER_NAMES,
    INVOCATIONS,
    NEGATIVE_PROBE_SQL,
    PHASE_INVOCATIONS,
    RESUME_INTERRUPTION_AUDIT,
    RESUME_PART_FIELDS,
    SEVENTH_RUNTIME_FILENAME,
    canonical_tsv_part_metadata,
    validate_freeze_trigger_rows,
)
from evidence_contract import (
    EvidenceBinding,
    HISTORICAL_LOSS_FILENAME,
    HISTORICAL_LOSS_STATUS,
    HISTORICAL_PATHS,
    PHASES,
    extract_programs,
    verify_final_coverage,
    verify_phase_manifests,
)


RUNTIME_PREFIX = "mysql-senior-scenarios."
CONTROL_IDS = INVOCATIONS[2:5]
WINDOW_FIELDS = {
    "active_elapsed_seconds",
    "drain_limit_hits",
    "errors",
    "heartbeat_at_epoch",
    "max_heartbeat_lateness_ms",
    "operations",
    "status",
    "trial_id",
    "window_errors",
    "window_operations",
    "window_p95_ms",
    "window_seq",
}
JOB_NAMES = (
    "job-buffered-1",
    "job-buffered-2",
    "job-buffered-3",
    "job-chunked-1",
    "job-chunked-2",
    "job-chunked-3",
    "job-resume-1",
)
TIMED_IDS = ("oltp-smoke-1", *CONTROL_IDS, *INVOCATIONS[6:12])
COMMON_RESULT_FIELDS = {
    "accepted_windows",
    "controller_connector_environment",
    "experiment_binding",
    "export_result",
    "export_returncode",
    "latency_calibration",
    "mode",
    "oltp_result",
    "oltp_returncode",
    "smoke_gate",
    "smoke_result",
    "status",
    "trial_contract",
    "trial_id",
}


def _fail(message: str) -> None:
    raise ValueError(message)


def _exact_int(value: object, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{field} must be an exact integer >= {minimum}")
    return value


def _number(value: object, field: str) -> float:
    if type(value) not in (int, float):
        _fail(f"{field} must be an exact finite number")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        _fail(f"{field} must be an exact finite number")
    return parsed


def _connector_environment(value: object) -> dict[str, object]:
    fields = {
        "connector_version",
        "have_cext",
        "platform",
        "python_version",
        "requested_use_pure",
        "threadsafety",
    }
    if type(value) is not dict or set(value) != fields:
        _fail("controller connector environment fields drifted")
    if (
        value["connector_version"] != "9.7.0"
        or type(value["have_cext"]) is not bool
        or type(value["platform"]) is not str
        or not value["platform"]
        or type(value["python_version"]) is not str
        or not value["python_version"]
        or value["requested_use_pure"] is not True
        or _exact_int(value["threadsafety"], "connector threadsafety") != 1
    ):
        _fail("controller connector environment changed")
    return value


def _connector_contract(
    value: object, expected_environment: dict[str, object] | None = None
) -> dict[str, object]:
    fields = {
        "actual_connection_class",
        "actual_pure",
        "connector_version",
        "have_cext",
        "platform",
        "python_version",
        "requested_use_pure",
        "threadsafety",
    }
    if type(value) is not dict or set(value) != fields:
        _fail("connector contract fields drifted")
    environment = {key: value[key] for key in fields if key not in {"actual_connection_class", "actual_pure"}}
    _connector_environment(environment)
    if (
        value["actual_connection_class"]
        != "mysql.connector.connection.MySQLConnection"
        or value["actual_pure"] is not True
    ):
        _fail("connector contract changed")
    if expected_environment is not None and not _canonical_equal(
        environment, expected_environment
    ):
        _fail("connector contract differs from controller environment")
    return value


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _canonical_equal(left: object, right: object) -> bool:
    try:
        return _canonical_bytes(left) == _canonical_bytes(right)
    except (TypeError, ValueError):
        return False


def _canonical_sha(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path, expected_type: type = dict) -> Any:
    try:
        metadata = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(metadata.st_mode):
            _fail(f"evidence path is not a regular file: {path}")
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid JSON evidence: {path}") from error
    if type(value) is not expected_type:
        _fail(f"JSON evidence has the wrong exact type: {path}")
    return value


def _timestamp(value: object, field: str) -> None:
    if type(value) is not str or not re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z", value
    ):
        _fail(f"{field} is not an exact UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} is not an exact UTC timestamp") from error
    if parsed.tzinfo != timezone.utc:
        _fail(f"{field} is not an exact UTC timestamp")


def _mount_fields(line: str) -> tuple[list[str], int]:
    fields = line.split()
    try:
        separator = fields.index("-")
    except ValueError:
        return fields, -1
    return fields, separator


def _verify_process_isolation(
    volume_root: Path, mountinfo_text: str, *, production_mountinfo: bool
) -> None:
    private_tmp = []
    for line in mountinfo_text.splitlines():
        fields, separator = _mount_fields(line)
        if separator < 0 or len(fields) < 6:
            continue
        mountpoint = fields[4]
        if mountpoint == "/private/tmp":
            private_tmp.append(fields)
        if mountpoint == "/var/lib/mysql" or "mysql-senior-scenarios-data" in line:
            _fail("verifier process has a forbidden MySQL data mount")
    if len(private_tmp) != 1:
        _fail("verifier process lacks one exact /private/tmp mount")
    if "ro" not in private_tmp[0][5].split(","):
        _fail("/private/tmp evidence mount is writable")
    if production_mountinfo and volume_root.resolve() != Path("/private/tmp").resolve():
        _fail("production volume root must be /private/tmp")


def _verify_bootstrap_records(
    volume_root: Path, scenario_path: Path, expected_commit: str
) -> tuple[Path, dict[str, str], dict[str, object]]:
    historical = _read_json(volume_root / HISTORICAL_LOSS_FILENAME)
    if set(historical) != {
        "current_raw_verification",
        "historical_paths",
        "status",
    }:
        _fail("historical record fields are not exact")
    if (
        historical["current_raw_verification"] is not False
        or historical["status"] != HISTORICAL_LOSS_STATUS
        or type(historical["status"]) is not str
        or type(historical["historical_paths"]) is not list
        or historical["historical_paths"] != list(HISTORICAL_PATHS)
        or any(type(item) is not str for item in historical["historical_paths"])
    ):
        _fail("historical record is inconsistent")

    seventh = _read_json(volume_root / SEVENTH_RUNTIME_FILENAME)
    if set(seventh) != {
        "created_at",
        "internal_identity",
        "program_sha256",
        "runtime_path",
        "scenario_commit",
        "scenario_sha256",
        "suffix",
    }:
        _fail("seventh runtime record fields are not exact")
    _timestamp(seventh["created_at"], "seventh created_at")
    if (
        type(expected_commit) is not str
        or not re.fullmatch(r"[0-9a-f]{40}", expected_commit)
        or seventh["scenario_commit"] != expected_commit
        or type(seventh["suffix"]) is not str
        or not re.fullmatch(r"[A-Za-z0-9_-]+", seventh["suffix"])
    ):
        _fail("seventh runtime commit or suffix is inconsistent")
    if type(seventh["runtime_path"]) is not str:
        _fail("seventh runtime path has the wrong exact type")
    runtime_root = Path(seventh["runtime_path"])
    expected_runtime = volume_root / f"{RUNTIME_PREFIX}{seventh['suffix']}"
    if runtime_root != expected_runtime or not runtime_root.is_dir():
        _fail("seventh runtime path is inconsistent")

    scenario_text = scenario_path.read_text(encoding="utf-8")
    programs = extract_programs(scenario_text)
    hashes = {
        name: hashlib.sha256(source.encode("utf-8")).hexdigest()
        for name, source in programs.items()
    }
    scenario_sha = hashlib.sha256(scenario_text.encode("utf-8")).hexdigest()
    if (
        type(seventh["program_sha256"]) is not dict
        or seventh["program_sha256"] != hashes
        or hashes != EXPECTED_PROGRAM_SHA256
        or seventh["scenario_sha256"] != scenario_sha
    ):
        _fail("committed scenario fence hashes changed")
    for name, digest in hashes.items():
        runtime_program = runtime_root / name
        if _sha256_file(runtime_program) != digest:
            _fail(f"runtime scenario fence hash changed: {name}")
    return runtime_root, hashes, seventh


def _verify_binding(
    binding: EvidenceBinding,
    runtime_root: Path,
    programs: dict[str, str],
    seventh: dict[str, object],
) -> dict[str, object]:
    expected = {
        "scenario_commit": seventh["scenario_commit"],
        "scenario_sha256": seventh["scenario_sha256"],
        "program_sha256": programs,
        "network_name": EXPECTED_NETWORK,
        "volume_name": EXPECTED_VOLUME,
        "cpu_limit": "2",
        "memory_limit_bytes": EXPECTED_MEMORY,
        "pids_limit": EXPECTED_PIDS,
    }
    serialized = binding.serialize()
    for field, value in expected.items():
        if not _canonical_equal(serialized[field], value):
            _fail(f"evidence binding drift: {field}")
    identity = seventh["internal_identity"]
    if type(identity) is not dict or set(identity) != {
        "container_id",
        "cpu_max",
        "dns_addresses",
        "harness_image_id_process_lifetime",
        "hostname",
        "memory_max",
        "mountinfo_sha256",
        "pids_max",
        "private_tmp_mount",
    }:
        _fail("seventh internal identity has the wrong exact type")
    hostname = identity.get("hostname")
    container_id = identity.get("container_id")
    if (
        type(hostname) is not str
        or not hostname
        or type(container_id) is not str
        or not container_id.startswith(hostname)
        or identity.get("harness_image_id_process_lifetime")
        != binding.harness_image_id
        or identity.get("memory_max") != str(EXPECTED_MEMORY)
        or identity.get("pids_max") != str(EXPECTED_PIDS)
        or identity.get("cpu_max") != "200000 100000"
        or type(identity.get("private_tmp_mount")) is not str
        or "/private/tmp" not in identity["private_tmp_mount"]
        or type(identity.get("mountinfo_sha256")) is not str
        or not re.fullmatch(r"[0-9a-f]{64}", identity["mountinfo_sha256"])
        or type(identity.get("dns_addresses")) is not list
        or not identity["dns_addresses"]
        or any(
            type(address) is not str or not address
            for address in identity["dns_addresses"]
        )
    ):
        _fail("seventh internal identity or limits drifted")
    if Path(str(runtime_root)).name != f"{RUNTIME_PREFIX}{seventh['suffix']}":
        _fail("runtime binding drift")
    return serialized


def _validate_window_history(
    value: object,
    trial_id: str,
    *,
    minimum_windows: int = 0,
    maximum_windows: int | None = None,
) -> list[dict[str, object]]:
    if type(value) is not list or len(value) < minimum_windows:
        _fail("authoritative history has too few windows")
    if maximum_windows is not None and len(value) > maximum_windows:
        _fail("authoritative history has too many windows")
    previous_operations = 0
    previous_errors = 0
    previous_elapsed = 0.0
    previous_drain = 0
    previous_lateness = 0.0
    result = []
    for sequence, item in enumerate(value, 1):
        if type(item) is not dict or set(item) != WINDOW_FIELDS:
            _fail("authoritative history record fields are invalid")
        if item["trial_id"] != trial_id or item["status"] not in {
            "RUNNING",
            "SUCCEEDED",
            "FAILED",
        }:
            _fail("authoritative history trial or status changed")
        if _exact_int(item["window_seq"], "window sequence", minimum=1) != sequence:
            _fail("authoritative history window sequence regressed")
        window_operations = _exact_int(
            item["window_operations"], "window operations", minimum=1
        )
        window_errors = _exact_int(item["window_errors"], "window errors")
        operations = _exact_int(item["operations"], "operations")
        errors = _exact_int(item["errors"], "errors")
        elapsed = _number(item["active_elapsed_seconds"], "active elapsed")
        drain = _exact_int(item["drain_limit_hits"], "drain limit hits")
        lateness = _number(
            item["max_heartbeat_lateness_ms"], "max heartbeat lateness"
        )
        _number(item["heartbeat_at_epoch"], "heartbeat epoch")
        _number(item["window_p95_ms"], "window p95")
        if operations - previous_operations != window_operations:
            _fail("authoritative history operation sequence regressed")
        if errors - previous_errors != window_errors:
            _fail("authoritative history error sequence regressed")
        if elapsed <= previous_elapsed or drain < previous_drain or lateness < previous_lateness:
            _fail("authoritative history counters regressed")
        result.append(item)
        previous_operations = operations
        previous_errors = errors
        previous_elapsed = elapsed
        previous_drain = drain
        previous_lateness = lateness
    return result


def _read_ledgers(runtime_root: Path) -> dict[str, dict[str, object]]:
    terminal: dict[str, dict[str, object]] = {}
    observed_ids = []
    for phase, expected_ids in PHASE_INVOCATIONS.items():
        path = runtime_root / f"invocations-{phase}.jsonl"
        records = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                if type(record) is not dict:
                    _fail("invocation history record has the wrong exact type")
                records.append(record)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid invocation history: {path}") from error
        if len(records) != len(expected_ids) * 2:
            _fail("invocation history is incomplete")
        for index, invocation_id in enumerate(expected_ids):
            starting = records[index * 2]
            finished = records[index * 2 + 1]
            if set(starting) != {"invocation_id", "state", "timestamp"}:
                _fail("invocation STARTING history fields are not exact")
            if set(finished) != {"detail", "invocation_id", "state", "timestamp"}:
                _fail("invocation terminal history fields are not exact")
            _timestamp(starting["timestamp"], "invocation STARTING timestamp")
            _timestamp(finished["timestamp"], "invocation terminal timestamp")
            expected_terminal = "ABORTED" if invocation_id == "resume-interrupt-1" else "SUCCEEDED"
            if (
                starting["invocation_id"] != invocation_id
                or starting["state"] != "STARTING"
                or finished["invocation_id"] != invocation_id
                or finished["state"] != expected_terminal
                or type(finished["detail"]) is not dict
            ):
                _fail("invocation authoritative history order or state changed")
            observed_ids.append(invocation_id)
            terminal[invocation_id] = finished["detail"]
    if tuple(observed_ids) != INVOCATIONS:
        _fail("invocation authoritative history IDs changed")
    return terminal


def _experiment_binding(
    value: object, runtime_root: Path, programs: dict[str, str]
) -> dict[str, object]:
    fields = {
        "controller_sha256",
        "database",
        "host",
        "port",
        "requested_use_pure",
        "runner_sha256",
        "runtime_root",
        "user",
    }
    if type(value) is not dict or set(value) != fields:
        _fail("experiment binding fields drifted")
    if (
        value["runtime_root"] != str(runtime_root.resolve())
        or value["runner_sha256"] != programs["export_runner.py"]
        or value["controller_sha256"] != programs["scenario_controller.py"]
        or value["host"] != "mysql-senior-scenarios-mysql"
        or value["port"] != 3306
        or value["user"] != "root"
        or value["database"] != "mysql_senior_scenarios"
        or value["requested_use_pure"] is not True
    ):
        _fail("experiment binding drift")
    return value


def _trial_contract(value: object, mode: str, duration: int) -> int:
    expected = {
        "duration_seconds": duration,
        "export_mode": mode,
        "requested_p95_budget_ms": 0.0,
        "threads": 4,
        "window_seconds": 1.0,
    }
    if type(value) is not dict or not _canonical_equal(value, expected):
        _fail("ordinary result contract trial settings changed")
    duration_seconds = _exact_int(
        value["duration_seconds"], "trial duration seconds", minimum=1
    )
    _exact_int(value["threads"], "trial threads", minimum=1)
    window_seconds = value["window_seconds"]
    if (
        type(window_seconds) is not float
        or not math.isfinite(window_seconds)
        or window_seconds <= 0
        or type(value["requested_p95_budget_ms"]) is not float
        or not math.isfinite(value["requested_p95_budget_ms"])
        or value["requested_p95_budget_ms"] < 0
    ):
        _fail("ordinary result contract trial numeric settings changed")
    return math.ceil(duration_seconds / window_seconds) + 1


def _oltp_child(
    value: object,
    trial_id: str,
    accepted: list[dict[str, object]],
    environment: dict[str, object],
) -> None:
    fields = {
        "connector_contract",
        "drain_limit_hits",
        "errors",
        "max_heartbeat_lateness_ms",
        "mode",
        "operations",
        "p50_ms",
        "p95_ms",
        "p99_ms",
        "status",
        "threads",
        "trial_id",
        "window_history",
        "window_history_schema",
        "worker_connections",
    }
    if type(value) is not dict or set(value) != fields:
        _fail("ordinary result contract OLTP child fields changed")
    _connector_contract(value["connector_contract"], environment)
    child_history = _validate_window_history(
        value["window_history"],
        trial_id,
        minimum_windows=len(accepted),
        maximum_windows=len(accepted),
    )
    operations = _exact_int(
        value["operations"], "OLTP child operations", minimum=1
    )
    errors = _exact_int(value["errors"], "OLTP child errors")
    drain_limit_hits = _exact_int(
        value["drain_limit_hits"], "OLTP child drain hits"
    )
    max_lateness = _number(
        value["max_heartbeat_lateness_ms"], "OLTP child max heartbeat lateness"
    )
    latest = accepted[-1]
    if (
        value["mode"] != "oltp"
        or value["status"] != "SUCCEEDED"
        or value["trial_id"] != trial_id
        or _exact_int(value["threads"], "OLTP child threads", minimum=1) != 4
        or errors != 0
        or operations != latest["operations"]
        or errors != latest["errors"]
        or drain_limit_hits != latest["drain_limit_hits"]
        or max_lateness != latest["max_heartbeat_lateness_ms"]
        or value["window_history_schema"] != "oltp-window-history-v1"
        or not _canonical_equal(child_history, accepted)
    ):
        _fail("ordinary result contract OLTP summary differs from final cumulative window")
    percentiles = [
        _number(value[field], f"OLTP child {field}")
        for field in ("p50_ms", "p95_ms", "p99_ms")
    ]
    if percentiles != sorted(percentiles):
        _fail("ordinary result contract OLTP percentile ordering changed")
    workers = value["worker_connections"]
    if type(workers) is not list or len(workers) != 4:
        _fail("ordinary result contract worker connections changed")
    connection_ids = set()
    for worker_number, worker in enumerate(workers, 1):
        if type(worker) is not dict or set(worker) != {
            "actual_connection_class",
            "actual_pure",
            "close_proof",
            "closed",
            "connection_id",
            "connector_version",
            "have_cext",
            "platform",
            "python_version",
            "requested_use_pure",
            "threadsafety",
            "worker",
        }:
            _fail("ordinary result contract worker fields changed")
        contract = {
            key: worker[key]
            for key in worker
            if key not in {"close_proof", "closed", "connection_id", "worker"}
        }
        _connector_contract(contract, environment)
        connection_id = _exact_int(
            worker["connection_id"], "worker connection ID", minimum=1
        )
        if (
            worker["worker"] != worker_number
            or type(worker["worker"]) is not int
            or worker["closed"] is not True
            or worker["close_proof"] != "is_connected_false"
            or connection_id in connection_ids
        ):
            _fail("ordinary result contract worker connection changed")
        connection_ids.add(connection_id)


def _smoke_result(value: object, environment: dict[str, object]) -> dict[str, object]:
    fields = {
        "accepted_windows",
        "connector_contract",
        "drain_limit_hits",
        "duration_seconds",
        "errors",
        "excluded_from_control_statistics",
        "last_window_seq",
        "max_heartbeat_lateness_ms",
        "mode",
        "operations",
        "status",
        "threads",
        "worker_connections",
    }
    if type(value) is not dict or set(value) != fields:
        _fail("ordinary result contract smoke gate fields changed")
    _connector_contract(value["connector_contract"], environment)
    if (
        value["status"] != "SUCCEEDED"
        or value["mode"] != "preflight-oltp"
        or value["excluded_from_control_statistics"] is not True
        or _exact_int(value["duration_seconds"], "smoke duration", minimum=1) != 5
        or _exact_int(value["threads"], "smoke threads", minimum=1) != 4
        or _exact_int(value["errors"], "smoke errors") != 0
        or _exact_int(value["drain_limit_hits"], "smoke drain hits") != 0
        or _exact_int(value["accepted_windows"], "smoke accepted windows", minimum=2) < 2
        or _exact_int(value["last_window_seq"], "smoke final window", minimum=2)
        < value["accepted_windows"]
        or _exact_int(value["worker_connections"], "smoke workers", minimum=1) != 4
        or _exact_int(value["operations"], "smoke operations", minimum=1) <= 0
    ):
        _fail("ordinary result contract smoke gate changed")
    _number(value["max_heartbeat_lateness_ms"], "smoke heartbeat lateness")
    return value


def _export_result(
    value: object,
    job_id: str,
    mode: str,
    seed_rows: int | None = None,
    expected_environment: dict[str, object] | None = None,
) -> dict[str, object]:
    fields = {
        "active_seconds",
        "connector_contract",
        "high_cursor",
        "job_id",
        "last_cursor",
        "max_rss_bytes",
        "mode",
        "rows",
        "rows_per_active_second",
        "sha256",
        "status",
    }
    if mode == "chunked":
        fields.add("parts")
    if type(value) is not dict or set(value) != fields:
        _fail("ordinary result contract export fields changed")
    _connector_contract(value["connector_contract"], expected_environment)
    rows = _exact_int(value["rows"], "export rows", minimum=1)
    if (
        value["status"] != "SUCCEEDED"
        or value["mode"] != mode
        or value["job_id"] != job_id
        or (seed_rows is not None and rows != seed_rows)
        or type(value["sha256"]) is not str
        or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"])
        or type(value["high_cursor"]) is not list
        or type(value["last_cursor"]) is not list
        or value["high_cursor"] != value["last_cursor"]
    ):
        _fail("ordinary result contract export changed")
    active_seconds = _number(value["active_seconds"], "export active seconds")
    throughput = _number(value["rows_per_active_second"], "export throughput")
    if active_seconds <= 0 or not math.isclose(
        throughput, rows / active_seconds, rel_tol=1e-12, abs_tol=1e-12
    ):
        _fail("ordinary result contract export throughput changed")
    _exact_int(value["max_rss_bytes"], "export max RSS", minimum=1)
    if mode == "chunked":
        _exact_int(value["parts"], "export parts", minimum=1)
    return value


def _common_result(
    result: object,
    invocation_id: str,
    mode: str,
    duration: int,
    runtime_root: Path,
    programs: dict[str, str],
    minimum_control_windows: int,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if type(result) is not dict or set(result) != COMMON_RESULT_FIELDS:
        _fail("ordinary result contract fields changed")
    environment = _connector_environment(result["controller_connector_environment"])
    _experiment_binding(result["experiment_binding"], runtime_root, programs)
    if (
        result["status"] != "SUCCEEDED"
        or result["trial_id"] != invocation_id
        or result["mode"] != mode
        or type(result["oltp_returncode"]) is not int
        or result["oltp_returncode"] != 0
    ):
        _fail("ordinary result contract identity or status changed")
    maximum_windows = _trial_contract(result["trial_contract"], mode, duration)
    minimum = minimum_control_windows if invocation_id in CONTROL_IDS else 1
    accepted = _validate_window_history(
        result["accepted_windows"],
        invocation_id,
        minimum_windows=minimum,
        maximum_windows=maximum_windows,
    )
    _oltp_child(result["oltp_result"], invocation_id, accepted, environment)
    return accepted, environment


def _controller_results(
    runtime_root: Path,
    programs: dict[str, str],
    ledger_terminal: dict[str, dict[str, object]],
    minimum_control_windows: int,
) -> tuple[dict[str, dict[str, object]], int]:
    expected_stdout = {
        f"harness-{invocation_id}.stdout.json" for invocation_id in INVOCATIONS
    }
    expected_stderr = {
        f"harness-{invocation_id}.stderr.txt" for invocation_id in INVOCATIONS
    }
    expected_persisted = {
        f"controller-result-{invocation_id}.json"
        for invocation_id in INVOCATIONS
        if not invocation_id.startswith("resume-")
    }
    if (
        {path.name for path in runtime_root.glob("harness-*.stdout.json")}
        != expected_stdout
        or {path.name for path in runtime_root.glob("harness-*.stderr.txt")}
        != expected_stderr
        or {path.name for path in runtime_root.glob("controller-result-*.json")}
        != expected_persisted
    ):
        _fail("stdout or persisted invocation evidence set changed")

    results: dict[str, dict[str, object]] = {}
    histories = 0
    smoke_authority = None
    calibration_authority = _read_json(runtime_root / "latency-calibration.json")
    for invocation_id in INVOCATIONS:
        stdout_path = runtime_root / f"harness-{invocation_id}.stdout.json"
        try:
            lines = stdout_path.read_text(encoding="utf-8").splitlines()
            if len(lines) != 1:
                _fail("stdout invocation evidence must contain exactly one record")
            result = json.loads(lines[0])
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid stdout invocation evidence: {stdout_path}") from error
        if type(result) is not dict:
            _fail("stdout invocation evidence has the wrong exact type")
        stderr_path = runtime_root / f"harness-{invocation_id}.stderr.txt"
        try:
            if stderr_path.read_bytes() != b"":
                _fail("stdout invocation evidence has nonempty stderr")
        except OSError as error:
            raise ValueError(f"invalid stdout invocation evidence: {stderr_path}") from error
        if not invocation_id.startswith("resume-"):
            persisted = _read_json(
                runtime_root / f"controller-result-{invocation_id}.json"
            )
            if not _canonical_equal(persisted, result):
                _fail("stdout differs from persisted controller result")
        detail = dict(ledger_terminal[invocation_id])
        if set(detail) != set(result) | {"returncode"}:
            _fail("invocation returncode or result fields are not exact")
        returncode = detail.pop("returncode")
        if (
            type(returncode) is not int
            or returncode != 0
            or not _canonical_equal(detail, result)
        ):
            _fail("invocation returncode or authoritative result changed")

        # Direct resume records have no controller-result file and must be handled
        # before the generic timed-controller branch.
        if invocation_id == "resume-interrupt-1":
            fields = {
                "active_seconds", "connector_contract", "high_cursor", "job_id",
                "last_cursor", "max_rss_bytes", "mode", "parts", "reason",
                "rows", "rows_per_active_second", "status",
            }
            if type(result) is not dict or set(result) != fields:
                _fail("direct resume interruption result contract fields changed")
            _connector_contract(result["connector_contract"])
            if (
                result["status"] != "ABORTED"
                or result["mode"] != "chunked"
                or result["job_id"] != "resume-1"
                or result["reason"] != "max_batches"
                or _exact_int(result["rows"], "resume interruption rows") != 3000
                or _exact_int(result["parts"], "resume interruption parts") != 3
                or "sha256" in result
            ):
                _fail("direct resume interruption result contract changed")
            active_seconds = _number(
                result["active_seconds"], "resume interruption active seconds"
            )
            throughput = _number(
                result["rows_per_active_second"], "resume interruption throughput"
            )
            if active_seconds <= 0 or not math.isclose(
                throughput,
                result["rows"] / active_seconds,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                _fail("direct resume interruption throughput changed")
            _exact_int(result["max_rss_bytes"], "resume interruption max RSS", minimum=1)
            results[invocation_id] = result
            continue
        if invocation_id == "resume-complete-1":
            _export_result(result, "resume-1", "chunked")
            results[invocation_id] = result
            continue

        if invocation_id == "kill-preflight-1":
            fields = {
                "active_polls", "active_query", "cleanup_polls", "connection_id",
                "connector_connections", "connector_contract",
                "controller_connector_environment", "experiment_binding", "mode",
                "observed_errno", "status", "temporary_table_discarded",
                "trial_contract", "trial_id", "victim_connection_absent",
            }
            if type(result) is not dict or set(result) != fields:
                _fail("ordinary result contract kill fields changed")
            environment = _connector_environment(result["controller_connector_environment"])
            _experiment_binding(result["experiment_binding"], runtime_root, programs)
            _connector_contract(result["connector_contract"], environment)
            connections = result["connector_connections"]
            if type(connections) is not dict or set(connections) != {"killer", "victim"}:
                _fail("ordinary result contract kill connections changed")
            for connection in connections.values():
                _connector_contract(connection, environment)
            _trial_contract(result["trial_contract"], "preflight-kill", 60)
            if (
                result["status"] != "SUCCEEDED"
                or result["mode"] != "preflight-kill"
                or result["trial_id"] != invocation_id
                or result["observed_errno"] != 1317
                or type(result["observed_errno"]) is not int
                or result["temporary_table_discarded"] is not True
                or result["victim_connection_absent"] is not True
                or "mysql_senior_kill_preflight" not in result["active_query"]
            ):
                _fail("ordinary result contract kill changed")
            for field in ("active_polls", "cleanup_polls", "connection_id"):
                _exact_int(result[field], f"kill {field}", minimum=1)
        elif invocation_id == "latency-calibration-1":
            fields = {
                "calibration", "calibration_artifact",
                "controller_connector_environment", "experiment_binding", "mode",
                "smoke_gate", "status", "trial_contract", "trial_id",
            }
            if type(result) is not dict or set(result) != fields:
                _fail("ordinary result contract calibration fields changed")
            environment = _connector_environment(result["controller_connector_environment"])
            _experiment_binding(result["experiment_binding"], runtime_root, programs)
            _trial_contract(result["trial_contract"], "latency-calibration", 60)
            if (
                result["status"] != "SUCCEEDED"
                or result["mode"] != "latency-calibration"
                or result["trial_id"] != invocation_id
                or result["calibration_artifact"] != "latency-calibration.json"
                or not _canonical_equal(result["calibration"], calibration_authority)
                or not _canonical_equal(result["smoke_gate"], smoke_authority)
            ):
                _fail("ordinary result contract calibration changed")
            _smoke_result(result["smoke_gate"], environment)
        else:
            mode = (
                "preflight-oltp" if invocation_id == "oltp-smoke-1"
                else "none" if invocation_id in CONTROL_IDS
                else "buffered" if invocation_id.startswith("buffered-")
                else "chunked"
            )
            duration = 5 if invocation_id == "oltp-smoke-1" else 60
            accepted, environment = _common_result(
                result, invocation_id, mode, duration, runtime_root, programs,
                minimum_control_windows,
            )
            histories += 1
            if invocation_id == "oltp-smoke-1":
                if (
                    result["export_result"] is not None
                    or result["export_returncode"] is not None
                    or result["latency_calibration"] is not None
                    or result["smoke_gate"] is not None
                ):
                    _fail("ordinary result contract smoke outputs changed")
                smoke_authority = _smoke_result(result["smoke_result"], environment)
                child = result["oltp_result"]
                if (
                    smoke_authority["accepted_windows"] != len(accepted)
                    or smoke_authority["last_window_seq"]
                    != accepted[-1]["window_seq"]
                    or smoke_authority["operations"] != child["operations"]
                    or smoke_authority["errors"] != child["errors"]
                    or smoke_authority["drain_limit_hits"]
                    != child["drain_limit_hits"]
                    or smoke_authority["max_heartbeat_lateness_ms"]
                    != child["max_heartbeat_lateness_ms"]
                    or not _canonical_equal(
                        smoke_authority["connector_contract"],
                        child["connector_contract"],
                    )
                ):
                    _fail("ordinary result contract smoke binding changed")
            elif invocation_id in CONTROL_IDS:
                if (
                    result["export_result"] is not None
                    or result["export_returncode"] is not None
                    or result["latency_calibration"] is not None
                    or result["smoke_result"] is not None
                    or not _canonical_equal(result["smoke_gate"], smoke_authority)
                ):
                    _fail("ordinary result contract control outputs changed")
                _smoke_result(result["smoke_gate"], environment)
            else:
                job_result = _read_json(runtime_root / f"job-{invocation_id}" / "result.json")
                if (
                    type(result["export_returncode"]) is not int
                    or result["export_returncode"] != 0
                    or result["smoke_result"] is not None
                    or not _canonical_equal(result["smoke_gate"], smoke_authority)
                    or not _canonical_equal(result["latency_calibration"], calibration_authority)
                    or not _canonical_equal(result["export_result"], job_result)
                ):
                    _fail(
                        "ordinary result contract export binding or calibration changed"
                    )
                _smoke_result(result["smoke_gate"], environment)
                _export_result(
                    result["export_result"],
                    invocation_id,
                    mode,
                    expected_environment=environment,
                )
        results[invocation_id] = result
    return results, histories


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def _rolling_five(windows: list[dict[str, object]]) -> list[float]:
    values = [_number(item["window_p95_ms"], "window p95") for item in windows]
    return [
        _percentile(values[end - 5 : end], 0.50)
        for end in range(5, len(values) + 1)
    ]


def _verify_calibration(
    runtime_root: Path,
    results: dict[str, dict[str, object]],
    experiment_binding: dict[str, object],
) -> None:
    trials = []
    for control_id in CONTROL_IDS:
        source = results[control_id]
        accepted = source["accepted_windows"]
        if (
            source.get("status") != "SUCCEEDED"
            or source.get("mode") != "none"
            or source.get("trial_id") != control_id
            or type(source.get("trial_contract")) is not dict
            or source["trial_contract"]
            != {
                "duration_seconds": 60,
                "export_mode": "none",
                "requested_p95_budget_ms": 0.0,
                "threads": 4,
                "window_seconds": 1.0,
            }
        ):
            _fail("control calibration input contract changed")
        child = source["oltp_result"]
        if (
            child.get("status") != "SUCCEEDED"
            or child.get("mode") != "oltp"
            or child.get("trial_id") != control_id
            or _exact_int(child.get("threads"), "control threads", minimum=1) != 4
            or _exact_int(child.get("errors"), "control errors") != 0
        ):
            _fail("control calibration child changed")
        trials.append(
            {
                "accepted_windows": accepted,
                "experiment_binding": experiment_binding,
                "mode": "none",
                "oltp_result": child,
                "rolling_values_ms": _rolling_five(accepted),
                "status": "SUCCEEDED",
                "trial_contract": source["trial_contract"],
                "trial_id": control_id,
            }
        )
    combined = [value for trial in trials for value in trial["rolling_values_ms"]]
    rolling_max = max(combined)
    rebuilt = {
        "budget_ms": rolling_max * 1.5,
        "experiment_binding": experiment_binding,
        "formula": "1.5 * max(rolling-5 median(window_p95_ms))",
        "multiplier": 1.5,
        "rolling_count": len(combined),
        "rolling_max_ms": rolling_max,
        "rolling_median_ms": _percentile(combined, 0.50),
        "rolling_min_ms": min(combined),
        "rolling_p95_ms": _percentile(combined, 0.95),
        "rolling_p99_ms": _percentile(combined, 0.99),
        "schema": "report-latency-calibration-v1",
        "trials": trials,
        "window_size": 5,
    }
    rebuilt["inputs_sha256"] = _canonical_sha(
        {"binding": experiment_binding, "trials": trials}
    )
    persisted = _read_json(runtime_root / "latency-calibration.json")
    if not _canonical_equal(persisted, rebuilt):
        _fail("calibration derivative mismatch")
    result = results["latency-calibration-1"]
    if (
        result.get("status") != "SUCCEEDED"
        or result.get("mode") != "latency-calibration"
        or result.get("trial_id") != "latency-calibration-1"
        or not _canonical_equal(result.get("calibration"), persisted)
    ):
        _fail("calibration controller result mismatch")


def _probe_audit(value: object, seed: dict[str, object]) -> None:
    if type(value) is not dict or set(value) != {"oltp_probe", "source_matches_baseline"}:
        _fail("source probe audit fields drifted")
    probe = value["oltp_probe"]
    if type(probe) is not dict or set(probe) != {
        "counter_advanced",
        "counter_sum_after",
        "counter_sum_before",
        "rows",
        "schema_matches",
    }:
        _fail("source probe audit fields drifted")
    before = _exact_int(probe["counter_sum_before"], "source probe counter before")
    after = _exact_int(probe["counter_sum_after"], "source probe counter after")
    if (
        value["source_matches_baseline"] is not True
        or probe["rows"] != seed["probes"]
        or before != seed["probe_counter_sum"]
        or after < before
        or probe["counter_advanced"] is not (after > before)
        or probe["schema_matches"] is not True
    ):
        _fail("source probe audit drift")


def _trigger_names(value: object) -> tuple[str, ...]:
    fields = {"name", "operation", "statement", "table", "timing"}
    if type(value) is not list or len(value) != 6 or any(
        type(item) is not dict or set(item) != fields for item in value
    ):
        _fail("trigger audit fields are not exact")
    rows = [
        [item["name"], item["operation"], item["table"], item["timing"], item["statement"]]
        for item in value
    ]
    try:
        validated = validate_freeze_trigger_rows(rows)
    except RuntimeError as error:
        raise ValueError("trigger definition drifted") from error
    if not _canonical_equal(validated, value):
        _fail("trigger definition or ordering drifted")
    return tuple(item["name"] for item in value)


def _global_variables(value: object) -> list[object]:
    if type(value) is not list or len(value) != 6:
        _fail("global variable audit fields are not exact")
    for index, name in enumerate(
        ("buffer pool", "tmp table", "max heap table")
    ):
        _exact_int(value[index], f"global {name}", minimum=1)
    if (
        type(value[3]) is not str
        or value[3] != "REPEATABLE-READ"
        or type(value[4]) is not int
        or value[4] != 0
        or type(value[5]) is not int
        or value[5] != 0
    ):
        _fail("global variable audit values changed")
    return value


def _verify_source_and_teardown(
    runtime_root: Path,
    minimum_artifact_rows: int,
) -> dict[str, object]:
    seed = _read_json(runtime_root / "seed-manifest.json")
    canonical_rows = EXPECTED_SEED_MANIFEST["report_rows"]
    if minimum_artifact_rows == canonical_rows:
        if not _canonical_equal(seed, EXPECTED_SEED_MANIFEST):
            _fail("source baseline drift")
    else:
        if set(seed) != set(EXPECTED_SEED_MANIFEST):
            _fail("source baseline fields drift")
        rows = _exact_int(seed.get("report_rows"), "source baseline rows", minimum=minimum_artifact_rows)
        for field in ("orders", "item_orders"):
            if type(seed.get(field)) is not int or seed[field] != rows:
                _fail("source baseline row relationships drift")
        if (
            type(seed.get("items")) is not int
            or seed["items"] != rows * 3
            or type(seed.get("item_count_fingerprint")) is not int
            or seed["item_count_fingerprint"] != rows * 3
            or seed.get("min_items_per_order") != 3
            or seed.get("max_items_per_order") != 3
            or seed.get("probes") != 10_000
            or seed.get("probe_counter_sum") != 0
            or seed.get("min_cursor") != ["2026-01-01 00:00:01.000000", 1]
            or type(seed.get("high_cursor")) is not list
            or len(seed["high_cursor"]) != 2
            or seed["high_cursor"][1] != rows
            or seed.get("total_amount_fingerprint") != f"{rows}.00"
        ):
            _fail("source baseline aggregate relationships drift")
        for field in ("item_crc32_sum", "order_crc32_sum"):
            _exact_int(seed.get(field), f"source baseline {field}")
    probe_schema = _read_json(runtime_root / "probe-schema.json", list)
    if not _canonical_equal(probe_schema, EXPECTED_PROBE_SCHEMA):
        _fail("source probe schema drift")
    freeze = _read_json(runtime_root / "seed-freeze-audit.json")
    _probe_audit(freeze, seed)
    triggers = _read_json(runtime_root / "freeze-triggers.json", list)
    _trigger_names(triggers)
    globals_before = _read_json(runtime_root / "global-variables.json", list)
    _global_variables(globals_before)
    negative = _read_json(runtime_root / "freeze-negative-probes.json", list)
    if len(negative) != len(NEGATIVE_PROBE_SQL) or any(
        type(item) is not dict
        or item.get("rejected") is not True
        or item.get("sqlstate") != "45000"
        or item.get("message") != "report source is frozen for mysql senior scenario"
        or item.get("sql") != expected_sql
        for item, expected_sql in zip(negative, NEGATIVE_PROBE_SQL)
    ):
        _fail("source negative probe evidence drifted")
    connector = _read_json(runtime_root / "bootstrap-connector.json")
    if set(connector) != {
        "actual_connection_class", "actual_pure", "connector_version",
        "have_cext", "requested_use_pure", "threadsafety",
    } or (
        connector["connector_version"] != "9.7.0"
        or connector["requested_use_pure"] is not True
        or connector["actual_pure"] is not True
        or connector["actual_connection_class"]
        != "mysql.connector.connection.MySQLConnection"
        or type(connector["threadsafety"]) is not int
        or connector["threadsafety"] != 1
        or type(connector["have_cext"]) is not bool
    ):
        _fail("connector evidence drifted")
    for phase in PHASES[1:-1]:
        audit = _read_json(runtime_root / f"source-audit-{phase}.json")
        if set(audit) != {"freeze", "triggers"}:
            _fail("source audit fields drifted")
        _probe_audit(audit["freeze"], seed)
        _trigger_names(audit["triggers"])
        if not _canonical_equal(audit["freeze"], freeze) or not _canonical_equal(
            audit["triggers"], triggers
        ):
            _fail("source audit before/after relationship drifted")
    stop = _read_json(runtime_root / "controlled-stop.json")
    if (
        stop.get("requested_success") is not True
        or stop.get("status") != "COMPLETE"
        or stop.get("errors") != []
        or stop.get("active_processes") != []
        or stop.get("triggers_after_drop") != []
        or stop.get("triggers_dropped") != list(FREEZE_TRIGGER_NAMES)
    ):
        _fail("process cleanup or trigger teardown drifted")
    _timestamp(stop.get("timestamp"), "controlled stop timestamp")
    _trigger_names(stop.get("triggers_before_drop"))
    _probe_audit(stop.get("before_drop_audit"), seed)
    _probe_audit(stop.get("after_drop_audit"), seed)
    if (
        not _canonical_equal(stop.get("triggers_before_drop"), triggers)
        or not _canonical_equal(stop.get("before_drop_audit"), freeze)
        or not _canonical_equal(stop.get("after_drop_audit"), freeze)
    ):
        _fail("controlled stop before/after relationship drifted")
    return seed


def _artifact_signature(
    job: Path, seed: dict[str, object]
) -> dict[str, object]:
    state = _read_json(job / "state.json")
    result = _read_json(job / "result.json")
    expected_mode = "buffered" if job.name.startswith("job-buffered-") else "chunked"
    expected_job_id = job.name.removeprefix("job-")
    state_fields = {
        "abort_reason", "active_seconds", "artifact_rows", "artifact_sha256",
        "connection_id", "connector_contract", "expected_rows",
        "high_created_at", "high_id", "job_id", "last_created_at", "last_id",
        "mode", "next_part", "parts", "rows_written", "status",
    }
    if type(state) is not dict or set(state) != state_fields:
        _fail(f"artifact state fields changed: {job.name}")
    _connector_contract(state["connector_contract"])
    _export_result(result, expected_job_id, expected_mode)
    if (
        state.get("status") != "SUCCEEDED"
        or result.get("status") != "SUCCEEDED"
        or state.get("mode") != expected_mode
        or result.get("mode") != expected_mode
        or state.get("job_id") != expected_job_id
        or result.get("job_id") != expected_job_id
        or state["abort_reason"] is not None
        or _exact_int(state["connection_id"], "artifact connection ID", minimum=1) <= 0
        or _number(state["active_seconds"], "artifact active seconds") <= 0
        or not _canonical_equal(state["connector_contract"], result["connector_contract"])
    ):
        _fail(f"artifact state changed: {job.name}")
    expected_rows = _exact_int(seed["report_rows"], "expected report rows")
    high_cursor = seed["high_cursor"]
    if (
        state.get("expected_rows") != expected_rows
        or state.get("rows_written") != expected_rows
        or state.get("artifact_rows") != expected_rows
        or result.get("rows") != expected_rows
        or [state.get("high_created_at"), state.get("high_id")] != high_cursor
        or [state.get("last_created_at"), state.get("last_id")] != high_cursor
        or result.get("high_cursor") != high_cursor
        or result.get("last_cursor") != high_cursor
    ):
        _fail(f"artifact cursor or row state changed: {job.name}")

    digest = hashlib.sha256()
    rows = 0
    keys = set()
    first = None
    previous = None
    amount = Decimal("0.00")
    item_count = 0
    try:
        with (job / "artifact.tsv").open("rb") as source:
            for line in source:
                digest.update(line)
                if not line.endswith(b"\n"):
                    _fail(f"artifact row is not newline terminated: {job.name}")
                fields = line[:-1].split(b"\t")
                if len(fields) != 6:
                    _fail(f"artifact row has the wrong column count: {job.name}")
                created_at = fields[0].decode("ascii")
                order_id = int(fields[1])
                tenant_id = int(fields[2])
                status_value = int(fields[3])
                row_amount = Decimal(fields[4].decode("ascii"))
                row_item_count = int(fields[5])
                if (
                    not re.fullmatch(
                        r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{6}", created_at
                    )
                    or order_id < 0
                    or tenant_id < 0
                    or status_value < 0
                    or row_item_count < 0
                    or b"\t".join(
                        (
                            created_at.encode("ascii"),
                            str(order_id).encode("ascii"),
                            str(tenant_id).encode("ascii"),
                            str(status_value).encode("ascii"),
                            format(row_amount, ".2f").encode("ascii"),
                            str(row_item_count).encode("ascii"),
                        )
                    )
                    + b"\n"
                    != line
                ):
                    _fail(f"artifact row canonical format changed: {job.name}")
                cursor = (created_at, order_id)
                if previous is not None and cursor <= previous:
                    _fail(f"artifact row order changed: {job.name}")
                if cursor in keys:
                    _fail(f"artifact unique order key changed: {job.name}")
                keys.add(cursor)
                if first is None:
                    first = cursor
                previous = cursor
                amount += row_amount
                item_count += row_item_count
                rows += 1
    except ValueError as error:
        if str(error).startswith("artifact "):
            raise
        raise ValueError(f"artifact row parsing failed: {job.name}") from error
    except (OSError, UnicodeError, InvalidOperation) as error:
        raise ValueError(f"artifact row parsing failed: {job.name}") from error
    actual_sha = digest.hexdigest()
    if (
        rows != expected_rows
        or len(keys) != expected_rows
        or first != (seed["min_cursor"][0], seed["min_cursor"][1])
        or previous != (high_cursor[0], high_cursor[1])
        or format(amount, ".2f") != seed["total_amount_fingerprint"]
        or item_count != seed["item_count_fingerprint"]
    ):
        _fail(f"artifact business aggregate changed: {job.name}")
    if state.get("artifact_sha256") != actual_sha or result.get("sha256") != actual_sha:
        _fail(f"artifact sha mismatch: {job.name}")
    parts = state["parts"]
    if expected_mode == "buffered":
        if (
            type(parts) is not list
            or parts != []
            or _exact_int(state["next_part"], "buffered next part", minimum=1) != 1
            or "parts" in result
        ):
            _fail(f"artifact buffered part state changed: {job.name}")
    else:
        if type(parts) is not list or not parts:
            _fail(f"artifact chunked parts are missing: {job.name}")
        part_digest = hashlib.sha256()
        part_rows = 0
        previous = None
        for number, part in enumerate(parts, 1):
            if type(part) is not dict or set(part) != RESUME_PART_FIELDS:
                _fail(f"artifact part fields changed: {job.name}")
            name = f"part-{number:06d}.tsv"
            rows_in_part = _exact_int(part["rows"], "artifact part rows", minimum=1)
            if (
                type(part["number"]) is not int
                or part["number"] != number
                or part["name"] != name
                or rows_in_part > 1000
                or (number < len(parts) and rows_in_part != 1000)
                or type(part["sha256"]) is not str
                or type(part["first_cursor"]) is not list
                or len(part["first_cursor"]) != 2
                or type(part["last_cursor"]) is not list
                or len(part["last_cursor"]) != 2
                or (previous is not None and part["first_cursor"] <= previous)
            ):
                _fail(f"artifact part contract changed: {job.name}")
            path = job / "parts" / name
            try:
                observed = canonical_tsv_part_metadata(path)
            except RuntimeError as error:
                raise ValueError(
                    f"artifact part cursor or bytes changed: {job.name}"
                ) from error
            if any(observed[field] != part[field] for field in observed):
                _fail(f"artifact part cursor or bytes changed: {job.name}")
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    part_digest.update(chunk)
            part_rows += observed["rows"]
            previous = observed["last_cursor"]
        if (
            _exact_int(state["next_part"], "chunked next part", minimum=1)
            != len(parts) + 1
            or result["parts"] != len(parts)
            or type(result["parts"]) is not int
            or part_rows != rows
            or part_digest.hexdigest() != actual_sha
            or previous != [state["last_created_at"], state["last_id"]]
        ):
            _fail(f"artifact part manifest changed: {job.name}")
    return {"job": job.name, "rows": rows, "sha256": actual_sha}


def _verify_resume_interruption(
    runtime_root: Path, results: dict[str, dict[str, object]]
) -> None:
    audit = _read_json(runtime_root / RESUME_INTERRUPTION_AUDIT)
    fields = {
        "artifact_exists", "checkpoint_state", "checkpoint_state_sha256",
        "job_id", "next_part", "part_count", "parts", "recorded_at",
        "result_exists", "rows_written", "status",
    }
    if set(audit) != fields:
        _fail("resume interruption audit fields are not exact")
    _timestamp(audit["recorded_at"], "resume interruption recorded_at")
    checkpoint = audit["checkpoint_state"]
    state_fields = {
        "abort_reason", "active_seconds", "artifact_rows", "artifact_sha256",
        "connection_id", "connector_contract", "expected_rows",
        "high_created_at", "high_id", "job_id", "last_created_at", "last_id",
        "mode", "next_part", "parts", "rows_written", "status",
    }
    if type(checkpoint) is not dict or set(checkpoint) != state_fields:
        _fail("resume interruption checkpoint fields are not exact")
    expected_sha = hashlib.sha256(_canonical_bytes(checkpoint) + b"\n").hexdigest()
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
        or audit["checkpoint_state_sha256"] != expected_sha
        or checkpoint["status"] != "ABORTED"
        or checkpoint["mode"] != "chunked"
        or checkpoint["job_id"] != "resume-1"
        or checkpoint["abort_reason"] != "max_batches"
        or checkpoint["artifact_rows"] is not None
        or checkpoint["artifact_sha256"] is not None
        or _number(checkpoint["active_seconds"], "resume checkpoint active seconds")
        <= 0
        or type(checkpoint["rows_written"]) is not int
        or checkpoint["rows_written"] != 3000
        or type(checkpoint["next_part"]) is not int
        or checkpoint["next_part"] != 4
        or not _canonical_equal(audit["parts"], checkpoint["parts"])
    ):
        _fail("resume interruption audit contract changed")
    _connector_contract(checkpoint["connector_contract"])
    checkpoint_parts = checkpoint["parts"]
    if type(checkpoint_parts) is not list or len(checkpoint_parts) != 3:
        _fail("resume interruption part count changed")
    derived_rows = 0
    previous_part_cursor = None
    for number, part in enumerate(checkpoint_parts, 1):
        if (
            type(part) is not dict
            or set(part) != RESUME_PART_FIELDS
            or type(part["number"]) is not int
            or part["number"] != number
            or part["name"] != f"part-{number:06d}.tsv"
        ):
            _fail("resume interruption part fields changed")
        try:
            observed = canonical_tsv_part_metadata(
                runtime_root / "job-resume-1" / "parts" / part["name"]
            )
        except RuntimeError as error:
            raise ValueError("resume interruption part cursor or bytes changed") from error
        if any(observed[field] != part[field] for field in observed):
            _fail("resume interruption part cursor or bytes changed")
        if (
            previous_part_cursor is not None
            and observed["first_cursor"] <= previous_part_cursor
        ):
            _fail("resume interruption part cursor order changed")
        derived_rows += observed["rows"]
        previous_part_cursor = observed["last_cursor"]
    if (
        derived_rows != checkpoint["rows_written"]
        or audit["rows_written"] != derived_rows
        or checkpoint["next_part"] != len(checkpoint_parts) + 1
        or audit["next_part"] != len(checkpoint_parts) + 1
        or audit["part_count"] != len(checkpoint_parts)
        or [checkpoint["last_created_at"], checkpoint["last_id"]]
        != checkpoint_parts[-1]["last_cursor"]
    ):
        _fail("resume interruption checkpoint last cursor or rows changed")
    interrupted = results["resume-interrupt-1"]
    if (
        interrupted["rows"] != audit["rows_written"]
        or interrupted["parts"] != audit["part_count"]
        or interrupted["job_id"] != audit["job_id"]
        or interrupted["reason"] != checkpoint["abort_reason"]
        or interrupted["active_seconds"] != checkpoint["active_seconds"]
        or interrupted["high_cursor"]
        != [checkpoint["high_created_at"], checkpoint["high_id"]]
        or interrupted["last_cursor"]
        != [checkpoint["last_created_at"], checkpoint["last_id"]]
        or not _canonical_equal(
            interrupted["connector_contract"], checkpoint["connector_contract"]
        )
    ):
        _fail("resume interruption stdout and checkpoint differ")
    final_state = _read_json(runtime_root / "job-resume-1" / "state.json")
    final_parts = final_state.get("parts")
    if (
        type(final_parts) is not list
        or len(final_parts) <= 3
        or not _canonical_equal(checkpoint_parts, final_parts[:3])
        or final_state.get("expected_rows") != checkpoint["expected_rows"]
        or [final_state.get("high_created_at"), final_state.get("high_id")]
        != [checkpoint["high_created_at"], checkpoint["high_id"]]
        or [final_state.get("last_created_at"), final_state.get("last_id")]
        != final_parts[-1]["last_cursor"]
    ):
        _fail("resume interruption part prefix differs from final manifest")


def _verify_artifacts(
    runtime_root: Path,
    seed: dict[str, object],
    results: dict[str, dict[str, object]],
) -> tuple[int, int]:
    signatures = [_artifact_signature(runtime_root / name, seed) for name in JOB_NAMES]
    if len({item["sha256"] for item in signatures}) != 1:
        _fail("artifact canonical SHA equality failed")
    audit = _read_json(runtime_root / "external-artifact-audit.json")
    if (
        set(audit) != {"artifacts", "status"}
        or audit["status"] != "COMPLETE"
        or not _canonical_equal(audit["artifacts"], signatures)
    ):
        _fail("external artifact audit changed")
    resume_result = _read_json(runtime_root / "job-resume-1" / "result.json")
    if not _canonical_equal(resume_result, results["resume-complete-1"]):
        _fail("direct resume completion differs from final atomic snapshot")
    for invocation_id in INVOCATIONS[6:12]:
        persisted = _read_json(runtime_root / f"job-{invocation_id}" / "result.json")
        if not _canonical_equal(
            persisted, results[invocation_id]["export_result"]
        ):
            _fail("ordinary result contract export differs from final job result")
    _verify_resume_interruption(runtime_root, results)
    return len(signatures), sum(item["rows"] for item in signatures)


def verify_evidence(
    *,
    volume_root: Path,
    scenario_path: Path,
    expected_commit: str,
    mountinfo_text: str | None = None,
    minimum_artifact_rows: int = 100_000,
    minimum_control_windows: int = 55,
) -> dict[str, object]:
    """Verify one complete evidence volume without modifying it."""
    volume = Path(volume_root)
    mountinfo = (
        Path("/proc/self/mountinfo").read_text(encoding="utf-8")
        if mountinfo_text is None
        else mountinfo_text
    )
    _verify_process_isolation(
        volume, mountinfo, production_mountinfo=mountinfo_text is None
    )
    runtime_root, programs, seventh = _verify_bootstrap_records(
        volume, Path(scenario_path), expected_commit
    )

    final_document = _read_json(runtime_root / "phase-manifest-60-final.json")
    try:
        binding = EvidenceBinding(**final_document["binding"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("final manifest binding is invalid") from error
    _verify_binding(binding, runtime_root, programs, seventh)
    manifests = verify_phase_manifests(runtime_root, binding)
    if len(manifests) != len(PHASES):
        _fail("final phase manifest is missing")
    verify_final_coverage(runtime_root, manifests[-1])

    ledger = _read_ledgers(runtime_root)
    results, histories = _controller_results(
        runtime_root, programs, ledger, minimum_control_windows
    )
    experiment = _experiment_binding(
        results["control-1"].get("experiment_binding"), runtime_root, programs
    )
    _verify_calibration(runtime_root, results, experiment)

    minimum_rows = _exact_int(
        minimum_artifact_rows, "minimum artifact rows", minimum=1
    )
    seed = _verify_source_and_teardown(runtime_root, minimum_rows)
    artifacts, artifact_rows = _verify_artifacts(runtime_root, seed, results)
    return {
        "checked": {
            "artifact_rows": artifact_rows,
            "artifacts": artifacts,
            "histories": histories,
            "invocations": len(ledger),
            "phases": len(manifests),
        },
        "final_tree_hash": manifests[-1]["tree_hash"],
        "runtime_path": str(runtime_root),
        "status": "VERIFIED",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--volume-root", type=Path, required=True)
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = verify_evidence(
            volume_root=args.volume_root,
            scenario_path=args.scenario,
            expected_commit=args.expected_commit,
        )
    except Exception as error:
        print(
            json.dumps(
                {
                    "error": f"{type(error).__name__}: {error}",
                    "status": "FAILED",
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
