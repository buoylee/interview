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
    SEVENTH_RUNTIME_FILENAME,
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
    value: object, trial_id: str, *, minimum_windows: int = 0
) -> list[dict[str, object]]:
    if type(value) is not list or len(value) < minimum_windows:
        _fail("authoritative history has too few windows")
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


def _controller_results(
    runtime_root: Path,
    programs: dict[str, str],
    ledger_terminal: dict[str, dict[str, object]],
    minimum_control_windows: int,
) -> tuple[dict[str, dict[str, object]], int]:
    results = {}
    histories = 0
    for invocation_id in INVOCATIONS:
        if invocation_id.startswith("resume-"):
            stdout_path = runtime_root / f"harness-{invocation_id}.stdout.json"
            try:
                lines = stdout_path.read_text(encoding="utf-8").splitlines()
                result = json.loads(lines[-1])
            except (OSError, IndexError, UnicodeError, json.JSONDecodeError) as error:
                raise ValueError(
                    f"invalid direct-resume stdout evidence: {stdout_path}"
                ) from error
            if type(result) is not dict:
                _fail("direct-resume stdout has the wrong exact type")
        else:
            path = runtime_root / f"controller-result-{invocation_id}.json"
            result = _read_json(path)
        detail = dict(ledger_terminal[invocation_id])
        returncode = detail.pop("returncode", 0)
        if (
            type(returncode) is not int
            or returncode != 0
            or not _canonical_equal(detail, result)
        ):
            _fail("controller result differs from authoritative invocation history")
        if not invocation_id.startswith("resume-"):
            binding = result.get("experiment_binding")
            _experiment_binding(binding, runtime_root, programs)
        if invocation_id != "latency-calibration-1":
            accepted = result.get("accepted_windows")
            child = result.get("oltp_result")
            if (
                type(accepted) is list
                and type(child) is dict
                and type(child.get("window_history")) is list
            ):
                minimum = minimum_control_windows if invocation_id in CONTROL_IDS else 0
                accepted_history = _validate_window_history(
                    accepted, invocation_id, minimum_windows=minimum
                )
                child_history = _validate_window_history(
                    child["window_history"], invocation_id, minimum_windows=minimum
                )
                if child.get("window_history_schema") != "oltp-window-history-v1":
                    _fail("authoritative history schema changed")
                if not _canonical_equal(accepted_history, child_history):
                    _fail("accepted windows differ from authoritative history")
                histories += 1
            elif invocation_id in (
                "oltp-smoke-1",
                *CONTROL_IDS,
                "buffered-1",
                "buffered-2",
                "buffered-3",
                "chunked-1",
                "chunked-2",
                "chunked-3",
            ):
                _fail("timed authoritative history is missing")
        elif invocation_id == "resume-interrupt-1":
            if result.get("status") != "ABORTED" or result.get("mode") != "chunked":
                _fail("direct resume interruption history changed")
        elif invocation_id == "resume-complete-1":
            if result.get("status") != "SUCCEEDED" or result.get("mode") != "chunked":
                _fail("direct resume completion history changed")
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
    if type(value) is not list:
        _fail("trigger audit has the wrong exact type")
    names = []
    for item in value:
        if type(item) is not dict or type(item.get("name")) is not str:
            _fail("trigger audit record is malformed")
        names.append(item["name"])
    if tuple(names) != tuple(sorted(FREEZE_TRIGGER_NAMES)):
        _fail("trigger audit names drifted")
    return tuple(names)


def _verify_source_and_teardown(
    runtime_root: Path,
    expected_seed_manifest: dict[str, object],
    expected_probe_schema: list[dict[str, object]],
) -> None:
    seed = _read_json(runtime_root / "seed-manifest.json")
    if not _canonical_equal(seed, expected_seed_manifest):
        _fail("source baseline drift")
    probe_schema = _read_json(runtime_root / "probe-schema.json", list)
    if not _canonical_equal(probe_schema, expected_probe_schema):
        _fail("source probe schema drift")
    freeze = _read_json(runtime_root / "seed-freeze-audit.json")
    _probe_audit(freeze, seed)
    triggers = _read_json(runtime_root / "freeze-triggers.json", list)
    _trigger_names(triggers)
    globals_before = _read_json(runtime_root / "global-variables.json", list)
    if not globals_before:
        _fail("global variable audit is empty")
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
    if (
        connector.get("connector_version") != "9.7.0"
        or connector.get("requested_use_pure") is not True
        or connector.get("actual_pure") is not True
        or type(connector.get("threadsafety")) is not int
        or type(connector.get("have_cext")) is not bool
    ):
        _fail("connector evidence drifted")
    for phase in PHASES[1:-1]:
        audit = _read_json(runtime_root / f"source-audit-{phase}.json")
        if set(audit) != {"freeze", "triggers"}:
            _fail("source audit fields drifted")
        _probe_audit(audit["freeze"], seed)
        _trigger_names(audit["triggers"])
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


def _artifact_signature(
    job: Path, seed: dict[str, object]
) -> dict[str, object]:
    state = _read_json(job / "state.json")
    result = _read_json(job / "result.json")
    expected_mode = "buffered" if job.name.startswith("job-buffered-") else "chunked"
    expected_job_id = job.name.removeprefix("job-")
    if (
        state.get("status") != "SUCCEEDED"
        or result.get("status") != "SUCCEEDED"
        or state.get("mode") != expected_mode
        or result.get("mode") != expected_mode
        or state.get("job_id") != expected_job_id
        or result.get("job_id") != expected_job_id
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
    return {"job": job.name, "rows": rows, "sha256": actual_sha}


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
    return len(signatures), sum(item["rows"] for item in signatures)


def verify_evidence(
    *,
    volume_root: Path,
    scenario_path: Path,
    expected_commit: str,
    mountinfo_text: str | None = None,
    expected_seed_manifest: dict[str, object] | None = None,
    expected_probe_schema: list[dict[str, object]] | None = None,
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

    seed = (
        EXPECTED_SEED_MANIFEST
        if expected_seed_manifest is None
        else expected_seed_manifest
    )
    probe_schema = (
        EXPECTED_PROBE_SCHEMA
        if expected_probe_schema is None
        else expected_probe_schema
    )
    if type(seed) is not dict or type(probe_schema) is not list:
        _fail("expected baseline contract has the wrong exact type")
    _verify_source_and_teardown(runtime_root, seed, probe_schema)
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
