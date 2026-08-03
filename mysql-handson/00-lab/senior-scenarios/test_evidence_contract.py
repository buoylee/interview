import hashlib
import json
import os
import re
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

from evidence_contract import (
    EvidenceBinding,
    HISTORICAL_LOSS_STATUS,
    HISTORICAL_PATHS,
    PHASES,
    create_phase_manifest,
    extract_programs,
    require_exact_int,
    verify_phase_manifests,
    verify_final_coverage,
    write_historical_loss,
)
from container_harness import (
    EXPECTED_HOST,
    EXPECTED_MEMORY,
    EXPECTED_NETWORK,
    EXPECTED_PIDS,
    EXPECTED_PORT,
    EXPECTED_PROBE_SCHEMA,
    EXPECTED_SEED_MANIFEST,
    EXPECTED_VOLUME,
    FREEZE_TRIGGER_NAMES,
    FREEZE_TRIGGER_SQL,
    ITEM_CRC32_SQL,
    INVOCATIONS,
    NEGATIVE_PROBE_SQL,
    ORDER_CRC32_SQL,
    SEVENTH_RUNTIME_FILENAME,
    BootstrapBoundary,
    BootstrapContext,
    ControlledTeardownOnce,
    HarnessStateMachine,
    InvocationLedger,
    build_invocation_command,
    capture_internal_identity,
    canonical_seed_reference,
    exact_db_int,
    run_all_lifecycle,
    snapshot_freeze_triggers,
    prepare_bootstrap,
    verify_connector_contract,
    validate_source_manifest,
    validate_freeze_trigger_rows,
    validate_negative_probe_error,
    validate_seed_baseline,
    verify_internal_identity,
)
from container_verifier import verify_evidence


SCENARIO = Path("/opt/scenario.md")
RUN_SCRIPT = Path("/opt/run-containerized.sh")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ShellPolicyTests(unittest.TestCase):
    def test_exact_owned_names_and_limits(self):
        text = RUN_SCRIPT.read_text(encoding="utf-8")
        for value in (
            "mysql-senior-scenarios-mysql",
            "mysql-senior-scenarios-harness",
            "mysql-senior-scenarios-net",
            "mysql-senior-scenarios-data",
            "mysql-senior-scenarios-evidence-v1",
            "--cpus 2",
            "--memory 2g",
            "--pids-limit 256",
            "com.openai.codex.scope=mysql-senior-scenarios",
        ):
            self.assertIn(value, text)

    def test_no_host_runtime_or_bind_mount(self):
        text = RUN_SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            "127.0.0.1:33306",
            "--mount type=bind",
            "-v $",
            "docker compose down",
            "docker volume rm",
        ):
            self.assertNotIn(forbidden, text)
        self.assertIsNone(
            re.search(r"(?m)^(?:uv|python|python3|pip|pip3|mysql)\s", text)
        )

    def test_host_runtime_regex_rejects_python_command_line(self):
        self.assertIsNotNone(
            re.search(
                r"(?m)^(?:uv|python|python3|pip|pip3|mysql)\s",
                "python command.py\n",
            )
        )

    def test_verify_requires_existing_evidence_volume(self):
        text = RUN_SCRIPT.read_text(encoding="utf-8")
        verify = text.split("verify_evidence() {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("require_existing_owned_evidence_volume", verify)
        self.assertNotIn("require_owned_evidence_volume", verify)

    def test_offline_suite_is_networkless_copy_only_and_compiles_verifier(self):
        text = RUN_SCRIPT.read_text(encoding="utf-8")
        offline = text.split("offline_test() {", 1)[1].split("\n}\n", 1)[0]
        create_line = next(
            line for line in offline.splitlines() if "docker create" in line
        )
        self.assertIn("--network none", create_line)
        self.assertNotIn("pip install", offline)
        self.assertIn("/opt/container_verifier.py", offline)
        self.assertIn("python -m py_compile", offline)

    def test_verify_inspects_network_mounts_and_limits_before_start(self):
        text = RUN_SCRIPT.read_text(encoding="utf-8")
        verify = text.split("verify_evidence() {", 1)[1].split("\n}\n", 1)[0]
        create_line = next(
            line for line in verify.splitlines() if "docker create" in line
        )
        self.assertIn("--network none", create_line)
        self.assertIn(
            "--mount type=volume,src=mysql-senior-scenarios-evidence-v1,dst=/private/tmp,readonly",
            create_line,
        )
        self.assertIn("--volume-root /private/tmp", create_line)
        self.assertIn('--expected-commit "$SCENARIO_COMMIT"', create_line)
        self.assertLess(
            verify.index("require_verifier_isolation"),
            verify.index('docker start -a "$VERIFIER_CONTAINER"'),
        )

    def test_live_paths_preflight_inputs_before_docker_mutation(self):
        text = RUN_SCRIPT.read_text(encoding="utf-8")
        run = text.split("run_live_harness() {", 1)[1].split("\n}\n", 1)[0]
        verify = text.split("verify_evidence() {", 1)[1].split("\n}\n", 1)[0]
        self.assertLess(
            run.index("preflight_harness_inputs"), run.index("require_owned_network")
        )
        self.assertLess(
            verify.index("preflight_verifier_inputs"),
            verify.index("remove_owned_transient"),
        )

    def test_owned_mysql_requires_data_volume_scope_label(self):
        text = RUN_SCRIPT.read_text(encoding="utf-8")
        mysql_gate = text.split("require_owned_mysql() {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn(
            'require_resource_scope_label volume "$DATA_VOLUME"', mysql_gate
        )

    def test_live_password_is_preflighted_and_forwarded_without_cli_value(self):
        text = RUN_SCRIPT.read_text(encoding="utf-8")
        run = text.split("run_live_harness() {", 1)[1].split("\n}\n", 1)[0]
        self.assertLess(
            run.index("preflight_harness_inputs"), run.index("require_owned_network")
        )
        preflight = text.split("preflight_harness_inputs() {", 1)[1].split(
            "\n}\n", 1
        )[0]
        self.assertIn("require_nonempty_mysql_password", preflight)
        create_line = next(
            line for line in run.splitlines() if "docker create" in line
        )
        self.assertIn("--env MYSQL_PASSWORD", create_line)
        self.assertNotIn("MYSQL_PASSWORD=", create_line)


class ContainerVerifierTests(unittest.TestCase):
    read_only_mountinfo = (
        "36 25 0:32 / /private/tmp ro,nosuid,nodev - local /dev rw\n"
    )

    def _write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n",
            encoding="utf-8",
        )

    def _canonical_sha(self, value: object) -> str:
        return hashlib.sha256(
            json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()

    def _window(self, trial_id: str, sequence: int, p95: float) -> dict:
        return {
            "active_elapsed_seconds": float(sequence),
            "drain_limit_hits": 0,
            "errors": 0,
            "heartbeat_at_epoch": 1_700_000_000.0 + sequence,
            "max_heartbeat_lateness_ms": float(sequence),
            "operations": sequence * 10,
            "status": "SUCCEEDED" if sequence == 5 else "RUNNING",
            "trial_id": trial_id,
            "window_errors": 0,
            "window_operations": 10,
            "window_p95_ms": p95,
            "window_seq": sequence,
        }

    def _experiment_binding(self, runtime_root: Path, programs: dict[str, str]) -> dict:
        return {
            "controller_sha256": sha256(programs["scenario_controller.py"]),
            "database": "mysql_senior_scenarios",
            "host": EXPECTED_HOST,
            "port": EXPECTED_PORT,
            "requested_use_pure": True,
            "runner_sha256": sha256(programs["export_runner.py"]),
            "runtime_root": str(runtime_root),
            "user": "root",
        }

    def _controller_result(
        self,
        trial_id: str,
        mode: str,
        binding: dict,
        windows: list[dict],
    ) -> dict:
        child = {
            "errors": 0,
            "mode": "oltp",
            "status": "SUCCEEDED",
            "threads": 4,
            "trial_id": trial_id,
            "window_history": windows,
            "window_history_schema": "oltp-window-history-v1",
        }
        return {
            "accepted_windows": windows,
            "experiment_binding": binding,
            "export_result": None,
            "mode": mode,
            "oltp_result": child,
            "status": "SUCCEEDED",
            "trial_contract": {
                "duration_seconds": 60,
                "export_mode": mode,
                "requested_p95_budget_ms": 0.0,
                "threads": 4,
                "window_seconds": 1.0,
            },
            "trial_id": trial_id,
        }

    def _refresh_manifests(self, runtime_root: Path, binding: EvidenceBinding) -> None:
        for phase in PHASES:
            path = runtime_root / f"phase-manifest-{phase}.json"
            if path.exists():
                path.unlink()
        for phase in PHASES:
            create_phase_manifest(runtime_root, phase, binding)

    def _build_tree(self, volume_root: Path) -> dict[str, object]:
        scenario_text = SCENARIO.read_text(encoding="utf-8")
        programs = extract_programs(scenario_text)
        program_hashes = {name: sha256(source) for name, source in programs.items()}
        runtime_root = volume_root / "mysql-senior-scenarios.miniature"
        runtime_root.mkdir()
        for name, source in programs.items():
            (runtime_root / name).write_text(source, encoding="utf-8")

        expected_commit = "1" * 40
        binding = EvidenceBinding(
            scenario_commit=expected_commit,
            scenario_sha256=sha256(scenario_text),
            mysql_image_id="sha256:mysql-image",
            mysql_container_id="mysql-container-id",
            harness_image_id="sha256:harness-image",
            network_name=EXPECTED_NETWORK,
            volume_name=EXPECTED_VOLUME,
            cpu_limit="2",
            memory_limit_bytes=EXPECTED_MEMORY,
            pids_limit=EXPECTED_PIDS,
            program_sha256=program_hashes,
        )
        self._write_json(
            volume_root / "historical-evidence-loss.json",
            {
                "current_raw_verification": False,
                "historical_paths": list(HISTORICAL_PATHS),
                "status": HISTORICAL_LOSS_STATUS,
            },
        )
        internal_identity = {
            "container_id": "harness-container-id",
            "cpu_max": "200000 100000",
            "dns_addresses": ["172.20.0.3"],
            "harness_image_id_process_lifetime": binding.harness_image_id,
            "hostname": "harness-container",
            "memory_max": str(EXPECTED_MEMORY),
            "mountinfo_sha256": "a" * 64,
            "pids_max": str(EXPECTED_PIDS),
            "private_tmp_mount": "volume /private/tmp rw",
        }
        self._write_json(
            volume_root / SEVENTH_RUNTIME_FILENAME,
            {
                "created_at": "2026-08-02T12:00:00Z",
                "internal_identity": internal_identity,
                "program_sha256": program_hashes,
                "runtime_path": str(runtime_root),
                "scenario_commit": expected_commit,
                "scenario_sha256": binding.scenario_sha256,
                "suffix": "miniature",
            },
        )

        seed = {
            "high_cursor": ["2026-01-01 00:00:03.000000", 3],
            "item_count_fingerprint": 6,
            "item_crc32_sum": 222,
            "item_orders": 3,
            "items": 6,
            "max_items_per_order": 2,
            "min_cursor": ["2026-01-01 00:00:01.000000", 1],
            "min_items_per_order": 2,
            "order_crc32_sum": 111,
            "orders": 3,
            "probe_counter_sum": 0,
            "probes": 2,
            "report_rows": 3,
            "total_amount_fingerprint": "60.00",
        }
        probe_schema = [
            {"values": ["COLUMN", "id", 1, "bigint unsigned", "NO", None, ""]},
            {"values": ["COLUMN", "counter", 2, "bigint unsigned", "NO", "0", ""]},
        ]
        freeze = {
            "oltp_probe": {
                "counter_advanced": True,
                "counter_sum_after": 30,
                "counter_sum_before": 0,
                "rows": 2,
                "schema_matches": True,
            },
            "source_matches_baseline": True,
        }
        triggers = [
            {"name": name, "statement": f"CREATE TRIGGER {name}"}
            for name in sorted(FREEZE_TRIGGER_NAMES)
        ]
        self._write_json(runtime_root / "seed-manifest.json", seed)
        self._write_json(runtime_root / "probe-schema.json", probe_schema)
        self._write_json(runtime_root / "seed-freeze-audit.json", freeze)
        self._write_json(runtime_root / "freeze-triggers.json", triggers)
        self._write_json(runtime_root / "global-variables.json", [1, 2, 3, "RR", 0, 0])
        self._write_json(
            runtime_root / "freeze-negative-probes.json",
            [
                {"message": "report source is frozen for mysql senior scenario", "rejected": True, "sql": statement, "sqlstate": "45000"}
                for statement in NEGATIVE_PROBE_SQL
            ],
        )
        self._write_json(
            runtime_root / "bootstrap-connector.json",
            {
                "actual_connection_class": "mysql.connector.connection.MySQLConnection",
                "actual_pure": True,
                "connector_version": "9.7.0",
                "have_cext": False,
                "requested_use_pure": True,
                "threadsafety": 1,
            },
        )
        for phase in PHASES[1:-1]:
            self._write_json(
                runtime_root / f"source-audit-{phase}.json",
                {"freeze": freeze, "triggers": triggers},
            )

        experiment_binding = self._experiment_binding(runtime_root, programs)
        result_by_id: dict[str, dict] = {}
        artifact_bytes = (
            b"2026-01-01 00:00:01.000000\t1\t1\t0\t10.00\t2\n"
            b"2026-01-01 00:00:02.000000\t2\t1\t0\t20.00\t2\n"
            b"2026-01-01 00:00:03.000000\t3\t1\t0\t30.00\t2\n"
        )
        artifact_sha = hashlib.sha256(artifact_bytes).hexdigest()
        control_p95 = {
            "control-1": [1.0, 2.0, 3.0, 4.0, 5.0],
            "control-2": [2.0, 3.0, 4.0, 5.0, 6.0],
            "control-3": [3.0, 4.0, 5.0, 6.0, 7.0],
        }
        for invocation_id in INVOCATIONS:
            if invocation_id == "latency-calibration-1":
                continue
            if invocation_id.startswith("resume-"):
                result = (
                    {
                        "high_cursor": seed["high_cursor"],
                        "job_id": "resume-1",
                        "last_cursor": [seed["min_cursor"][0], seed["min_cursor"][1]],
                        "mode": "chunked",
                        "parts": 1,
                        "rows": 1,
                        "status": "ABORTED",
                    }
                    if invocation_id == "resume-interrupt-1"
                    else {
                        "high_cursor": seed["high_cursor"],
                        "job_id": "resume-1",
                        "last_cursor": seed["high_cursor"],
                        "mode": "chunked",
                        "rows": 3,
                        "sha256": artifact_sha,
                        "status": "SUCCEEDED",
                    }
                )
                result_by_id[invocation_id] = result
                (runtime_root / f"harness-{invocation_id}.stdout.json").write_text(
                    json.dumps(result, sort_keys=True) + "\n", encoding="utf-8"
                )
                continue
            mode = (
                "none"
                if invocation_id.startswith("control-")
                else "chunked"
                if invocation_id.startswith(("chunked-", "resume-"))
                else "buffered"
                if invocation_id.startswith("buffered-")
                else "preflight"
            )
            values = control_p95.get(invocation_id, [1.0, 1.0, 1.0, 1.0, 1.0])
            windows = [
                self._window(invocation_id, sequence, value)
                for sequence, value in enumerate(values, 1)
            ]
            result = self._controller_result(
                invocation_id, mode, experiment_binding, windows
            )
            result_by_id[invocation_id] = result
            self._write_json(
                runtime_root / f"controller-result-{invocation_id}.json", result
            )

        trials = []
        for trial_id, rolling_value in (
            ("control-1", 3.0),
            ("control-2", 4.0),
            ("control-3", 5.0),
        ):
            source = result_by_id[trial_id]
            trial = {
                "accepted_windows": source["accepted_windows"],
                "experiment_binding": source["experiment_binding"],
                "mode": source["mode"],
                "oltp_result": source["oltp_result"],
                "status": source["status"],
                "trial_contract": source["trial_contract"],
                "trial_id": source["trial_id"],
            }
            trial["rolling_values_ms"] = [rolling_value]
            trials.append(trial)
        calibration = {
            "budget_ms": 7.5,
            "experiment_binding": experiment_binding,
            "formula": "1.5 * max(rolling-5 median(window_p95_ms))",
            "multiplier": 1.5,
            "rolling_count": 3,
            "rolling_max_ms": 5.0,
            "rolling_median_ms": 4.0,
            "rolling_min_ms": 3.0,
            "rolling_p95_ms": 5.0,
            "rolling_p99_ms": 5.0,
            "schema": "report-latency-calibration-v1",
            "trials": trials,
            "window_size": 5,
        }
        calibration["inputs_sha256"] = self._canonical_sha(
            {"binding": experiment_binding, "trials": trials}
        )
        self._write_json(runtime_root / "latency-calibration.json", calibration)
        calibration_result = {
            "calibration": calibration,
            "experiment_binding": experiment_binding,
            "mode": "latency-calibration",
            "status": "SUCCEEDED",
            "trial_id": "latency-calibration-1",
        }
        result_by_id["latency-calibration-1"] = calibration_result
        self._write_json(
            runtime_root / "controller-result-latency-calibration-1.json",
            calibration_result,
        )

        phase_invocations = {
            "10-kill-smoke": INVOCATIONS[0:2],
            "20-controls-calibration": INVOCATIONS[2:6],
            "30-buffered": INVOCATIONS[6:9],
            "40-chunked": INVOCATIONS[9:12],
            "50-resume-audit": INVOCATIONS[12:14],
        }
        ledger_for: dict[str, Path] = {}
        for phase, invocation_ids in phase_invocations.items():
            ledger_path = runtime_root / f"invocations-{phase}.jsonl"
            with ledger_path.open("w", encoding="utf-8") as output:
                for invocation_id in invocation_ids:
                    ledger_for[invocation_id] = ledger_path
                    output.write(
                        json.dumps(
                            {
                                "invocation_id": invocation_id,
                                "state": "STARTING",
                                "timestamp": "2026-08-02T12:00:00Z",
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
                    output.write(
                        json.dumps(
                            {
                                "detail": result_by_id[invocation_id],
                                "invocation_id": invocation_id,
                                "state": (
                                    "ABORTED"
                                    if invocation_id == "resume-interrupt-1"
                                    else "SUCCEEDED"
                                ),
                                "timestamp": "2026-08-02T12:01:00Z",
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        + "\n"
                    )

        job_names = [
            *(f"job-buffered-{index}" for index in range(1, 4)),
            *(f"job-chunked-{index}" for index in range(1, 4)),
            "job-resume-1",
        ]
        audit_signatures = []
        for job_name in job_names:
            job = runtime_root / job_name
            job.mkdir()
            (job / "artifact.tsv").write_bytes(artifact_bytes)
            mode = "buffered" if job_name.startswith("job-buffered") else "chunked"
            state = {
                "artifact_rows": 3,
                "artifact_sha256": artifact_sha,
                "expected_rows": 3,
                "high_created_at": seed["high_cursor"][0],
                "high_id": seed["high_cursor"][1],
                "job_id": job_name.removeprefix("job-"),
                "last_created_at": seed["high_cursor"][0],
                "last_id": seed["high_cursor"][1],
                "mode": mode,
                "rows_written": 3,
                "status": "SUCCEEDED",
            }
            result = {
                "high_cursor": seed["high_cursor"],
                "job_id": state["job_id"],
                "last_cursor": seed["high_cursor"],
                "mode": mode,
                "rows": 3,
                "sha256": artifact_sha,
                "status": "SUCCEEDED",
            }
            self._write_json(job / "state.json", state)
            self._write_json(job / "result.json", result)
            audit_signatures.append(
                {"job": job_name, "rows": 3, "sha256": artifact_sha}
            )
        self._write_json(
            runtime_root / "external-artifact-audit.json",
            {"artifacts": audit_signatures, "status": "COMPLETE"},
        )
        self._write_json(
            runtime_root / "controlled-stop.json",
            {
                "active_processes": [],
                "after_drop_audit": freeze,
                "before_drop_audit": freeze,
                "errors": [],
                "requested_success": True,
                "status": "COMPLETE",
                "timestamp": "2026-08-02T12:02:00Z",
                "triggers_after_drop": [],
                "triggers_before_drop": triggers,
                "triggers_dropped": list(FREEZE_TRIGGER_NAMES),
            },
        )
        self._refresh_manifests(runtime_root, binding)
        return {
            "binding": binding,
            "expected_commit": expected_commit,
            "ledger_for": ledger_for,
            "probe_schema": probe_schema,
            "runtime_root": runtime_root,
            "seed": seed,
        }

    def _verify(self, volume_root: Path, fixture: dict[str, object]) -> dict:
        return verify_evidence(
            volume_root=volume_root,
            scenario_path=SCENARIO,
            expected_commit=fixture["expected_commit"],
            mountinfo_text=self.read_only_mountinfo,
            expected_seed_manifest=fixture["seed"],
            expected_probe_schema=fixture["probe_schema"],
            minimum_control_windows=5,
        )

    def _snapshot(self, root: Path) -> tuple[list[tuple[str, str]], dict[str, int]]:
        files = sorted(path for path in root.rglob("*") if path.is_file())
        digests = [
            (path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
            for path in files
        ]
        mtimes = {
            path.relative_to(root).as_posix(): path.stat().st_mtime_ns for path in files
        }
        return digests, mtimes

    def test_verifier_accepts_complete_read_only_tree(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            fixture = self._build_tree(root)
            result = self._verify(root, fixture)
            final_manifest = json.loads(
                (fixture["runtime_root"] / "phase-manifest-60-final.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(result["status"], "VERIFIED")
            self.assertEqual(result["checked"]["phases"], 7)
            self.assertEqual(result["final_tree_hash"], final_manifest["tree_hash"])

    def test_verifier_rejects_missing_final_manifest(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            fixture = self._build_tree(root)
            (fixture["runtime_root"] / "phase-manifest-60-final.json").unlink()
            with self.assertRaises(ValueError):
                self._verify(root, fixture)

    def test_verifier_rejects_changed_authoritative_history(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            fixture = self._build_tree(root)
            runtime_root = fixture["runtime_root"]
            path = runtime_root / "controller-result-control-1.json"
            result = json.loads(path.read_text(encoding="utf-8"))
            result["oltp_result"]["window_history"][2]["window_seq"] = 99
            self._write_json(path, result)
            ledger_path = fixture["ledger_for"]["control-1"]
            records = [json.loads(line) for line in ledger_path.read_text().splitlines()]
            next(
                record
                for record in records
                if record["invocation_id"] == "control-1" and "detail" in record
            )["detail"] = result
            ledger_path.write_text(
                "".join(
                    json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n"
                    for item in records
                ),
                encoding="utf-8",
            )
            self._refresh_manifests(runtime_root, fixture["binding"])
            with self.assertRaisesRegex(ValueError, "sequence"):
                self._verify(root, fixture)

    def test_verifier_rejects_calibration_derivative_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            fixture = self._build_tree(root)
            runtime_root = fixture["runtime_root"]
            calibration_path = runtime_root / "latency-calibration.json"
            calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
            calibration["budget_ms"] = 999.0
            self._write_json(calibration_path, calibration)
            result_path = runtime_root / "controller-result-latency-calibration-1.json"
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result["calibration"] = calibration
            self._write_json(result_path, result)
            ledger_path = fixture["ledger_for"]["latency-calibration-1"]
            records = [json.loads(line) for line in ledger_path.read_text().splitlines()]
            next(
                record
                for record in records
                if record["invocation_id"] == "latency-calibration-1"
                and "detail" in record
            )["detail"] = result
            ledger_path.write_text(
                "".join(
                    json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n"
                    for item in records
                ),
                encoding="utf-8",
            )
            self._refresh_manifests(runtime_root, fixture["binding"])
            with self.assertRaisesRegex(ValueError, "calibration"):
                self._verify(root, fixture)

    def test_verifier_rejects_artifact_row_order_or_sha_mismatch(self):
        for corruption in ("order", "sha"):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory)
                fixture = self._build_tree(root)
                runtime_root = fixture["runtime_root"]
                job = runtime_root / "job-buffered-1"
                if corruption == "order":
                    lines = (job / "artifact.tsv").read_bytes().splitlines(keepends=True)
                    (job / "artifact.tsv").write_bytes(lines[1] + lines[0] + lines[2])
                else:
                    state_path = job / "state.json"
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                    state["artifact_sha256"] = "0" * 64
                    self._write_json(state_path, state)
                self._refresh_manifests(runtime_root, fixture["binding"])
                with self.assertRaisesRegex(ValueError, corruption):
                    self._verify(root, fixture)

    def test_verifier_rejects_source_probe_or_binding_drift(self):
        for corruption in ("source_probe", "binding"):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory)
                fixture = self._build_tree(root)
                runtime_root = fixture["runtime_root"]
                if corruption == "source_probe":
                    path = runtime_root / "source-audit-10-kill-smoke.json"
                    audit = json.loads(path.read_text(encoding="utf-8"))
                    audit["freeze"]["oltp_probe"]["rows"] = 99
                    self._write_json(path, audit)
                else:
                    path = runtime_root / "controller-result-buffered-1.json"
                    result = json.loads(path.read_text(encoding="utf-8"))
                    result["experiment_binding"]["runtime_root"] = "/private/tmp/drift"
                    self._write_json(path, result)
                    ledger_path = fixture["ledger_for"]["buffered-1"]
                    records = [
                        json.loads(line)
                        for line in ledger_path.read_text(encoding="utf-8").splitlines()
                    ]
                    next(
                        record
                        for record in records
                        if record["invocation_id"] == "buffered-1"
                        and "detail" in record
                    )["detail"] = result
                    ledger_path.write_text(
                        "".join(
                            json.dumps(item, sort_keys=True, separators=(",", ":"))
                            + "\n"
                            for item in records
                        ),
                        encoding="utf-8",
                    )
                self._refresh_manifests(runtime_root, fixture["binding"])
                with self.assertRaisesRegex(ValueError, corruption.replace("_", " ")):
                    self._verify(root, fixture)

    def test_verifier_writes_nothing_to_volume(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            fixture = self._build_tree(root)
            before = self._snapshot(root)
            self._verify(root, fixture)
            after = self._snapshot(root)
            self.assertEqual(after, before)


class ExtractionTests(unittest.TestCase):
    def test_extracts_exact_three_programs(self):
        programs = extract_programs(SCENARIO.read_text(encoding="utf-8"))
        self.assertEqual(
            set(programs),
            {"export_runner.py", "scenario_controller.py", "freeze_audit.py"},
        )
        self.assertEqual(
            sha256(programs["export_runner.py"]),
            "f774d36f3448c491668d1838075e2d18199e183fdbba415421fbcfb31e335d35",
        )
        self.assertEqual(
            sha256(programs["scenario_controller.py"]),
            "9aa226bb5fedb48b949841fa933b00decfe80855c19bce244e9a6e4476c04148",
        )
        self.assertEqual(
            sha256(programs["freeze_audit.py"]),
            "7461b1c0315f8b134cbe0f94d7ac6980e22034aa0703e587f853c11d3a443062",
        )

    def test_duplicate_marker_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "exactly one Python fence"):
            extract_programs("```python\nEXPORT_SQL = 1\n```\n```python\nEXPORT_SQL = 2\n```\n")

    def test_bool_is_not_accepted_as_integer(self):
        with self.assertRaisesRegex(ValueError, "exact int"):
            require_exact_int(True, "file_count")


class HistoricalLossTests(unittest.TestCase):
    def test_historical_loss_is_truthful_and_exclusive(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            runtime_root = Path(temporary_directory)
            target = write_historical_loss(runtime_root)
            record = json.loads(target.read_text(encoding="utf-8"))

            self.assertEqual(target.name, "historical-evidence-loss.json")
            self.assertEqual(tuple(record["historical_paths"]), HISTORICAL_PATHS)
            self.assertIs(type(record["status"]), str)
            self.assertEqual(record["status"], "LOST_BY_EXTERNAL_TMP_CLEANUP")
            self.assertEqual(HISTORICAL_LOSS_STATUS, record["status"])
            self.assertIs(type(record["current_raw_verification"]), bool)
            self.assertFalse(record["current_raw_verification"])
            with self.assertRaises(FileExistsError):
                write_historical_loss(runtime_root)


class HarnessStateTests(unittest.TestCase):
    binding = EvidenceBinding(
        scenario_commit="11d04a64716624f55860a32e68dc8c0ba71fd65c",
        scenario_sha256="a" * 64,
        mysql_image_id="sha256:mysql-image",
        mysql_container_id="mysql-container-id",
        harness_image_id="sha256:harness-image",
        network_name=EXPECTED_NETWORK,
        volume_name=EXPECTED_VOLUME,
        cpu_limit="2",
        memory_limit_bytes=EXPECTED_MEMORY,
        pids_limit=EXPECTED_PIDS,
        program_sha256={
            "export_runner.py": "b" * 64,
            "scenario_controller.py": "c" * 64,
            "freeze_audit.py": "d" * 64,
        },
    )

    class PureConnection:
        def close(self):
            pass

    class OtherConnection:
        def close(self):
            pass

    def _module(self, have_cext=True, version="9.7.0"):
        return SimpleNamespace(
            __version__=version,
            threadsafety=1,
            HAVE_CEXT=have_cext,
        )

    def _inspect(self):
        return [
            {
                "Name": "/mysql-senior-scenarios-harness",
                "Id": "harness-container-id",
                "Image": "sha256:harness-image",
                "Config": {
                    "Labels": {
                        "com.openai.codex.scope": "mysql-senior-scenarios"
                    }
                },
                "HostConfig": {
                    "NanoCpus": 2_000_000_000,
                    "Memory": EXPECTED_MEMORY,
                    "PidsLimit": EXPECTED_PIDS,
                },
                "Mounts": [
                    {
                        "Type": "volume",
                        "Name": EXPECTED_VOLUME,
                        "Destination": "/private/tmp",
                    }
                ],
                "NetworkSettings": {"Networks": {EXPECTED_NETWORK: {}}},
            },
            {
                "Name": f"/{EXPECTED_HOST}",
                "Id": "mysql-container-id",
                "Image": "sha256:mysql-image",
                "Config": {
                    "Labels": {
                        "com.openai.codex.scope": "mysql-senior-scenarios"
                    }
                },
                "NetworkSettings": {"Networks": {EXPECTED_NETWORK: {}}},
            },
        ]

    def _boundary(
        self,
        *,
        connect=None,
        connector_module=None,
        inspect_document=None,
        cgroups=None,
        resolve_dns=None,
        suffix_factory=None,
        hostname="harness-container-id\n",
        mountinfo=None,
        environ=None,
    ):
        cgroup_values = cgroups or {
            "/sys/fs/cgroup/cpu.max": "200000 100000\n",
            "/sys/fs/cgroup/memory.max": f"{EXPECTED_MEMORY}\n",
            "/sys/fs/cgroup/pids.max": f"{EXPECTED_PIDS}\n",
            "/etc/hostname": hostname,
            "/proc/self/mountinfo": mountinfo
            or (
                "100 1 0:1 / / rw - overlay overlay rw\n"
                "101 100 0:2 / /private/tmp rw - ext4 /dev/vda rw\n"
            ),
        }
        return BootstrapBoundary(
            connector_module=connector_module or self._module(),
            pure_connection_type=self.PureConnection,
            connect=connect or (lambda **kwargs: self.PureConnection()),
            read_text=lambda path: cgroup_values[str(path)],
            read_inspect=lambda path: inspect_document or self._inspect(),
            resolve_dns=resolve_dns
            or (
                lambda host, port: (
                    (2, 1, 6, "", ("172.18.0.2", port)),
                )
            ),
            environ=environ or {"MYSQL_PASSWORD": "not-on-command-line"},
            suffix_factory=suffix_factory or (lambda: "seventh"),
        )

    def _machine(self, root, call_log, manifest_log, teardown_log, fail=None):
        def launch(invocation_id, command, environment, stdout_path, stderr_path):
            call_log.append(invocation_id)
            if invocation_id == fail:
                raise RuntimeError(f"injected failure: {invocation_id}")
            if invocation_id == "resume-interrupt-1":
                job = root / "job-resume-1"
                job.mkdir()
                (job / "state.json").write_text(
                    json.dumps(
                        {
                            "status": "ABORTED",
                            "rows_written": 3000,
                            "next_part": 4,
                            "parts": [{}, {}, {}],
                        }
                    ),
                    encoding="utf-8",
                )
            if invocation_id == "resume-complete-1":
                job = root / "job-resume-1"
                (job / "state.json").write_text(
                    json.dumps({"status": "SUCCEEDED"}), encoding="utf-8"
                )
                (job / "result.json").write_text(
                    json.dumps({"status": "SUCCEEDED"}), encoding="utf-8"
                )
                (job / "artifact.tsv").write_bytes(b"evidence\n")
            result = {
                "returncode": 0,
                "status": (
                    "ABORTED"
                    if invocation_id == "resume-interrupt-1"
                    else "SUCCEEDED"
                ),
            }
            if invocation_id == "resume-interrupt-1":
                result.update({"rows": 3000, "parts": 3})
            return result

        def manifest(runtime_root, phase, binding):
            self.assertEqual(runtime_root, root)
            self.assertIs(binding, self.binding)
            manifest_log.append(phase)

        return HarnessStateMachine(
            runtime_root=root,
            binding=self.binding,
            ledger=InvocationLedger(root / "invocations.jsonl"),
            environment={"MYSQL_PASSWORD": "not-on-command-line"},
            launch=launch,
            create_manifest=manifest,
            teardown=lambda succeeded: teardown_log.append(succeeded),
        )

    def test_phase_order_is_exact_and_no_retry(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            calls = []
            manifests = []
            teardowns = []

            self._machine(root, calls, manifests, teardowns).run()

            self.assertEqual(tuple(calls), INVOCATIONS)
            self.assertEqual(tuple(manifests), PHASES)
            self.assertEqual(teardowns, [True])

    def test_failure_stops_later_phases_and_runs_teardown_once(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            calls = []
            manifests = []
            teardowns = []

            with self.assertRaisesRegex(RuntimeError, "buffered-1"):
                self._machine(
                    root, calls, manifests, teardowns, fail="buffered-1"
                ).run()

            failed_index = INVOCATIONS.index("buffered-1")
            self.assertEqual(tuple(calls), INVOCATIONS[: failed_index + 1])
            self.assertEqual(
                manifests,
                ["00-seed-freeze", "10-kill-smoke", "20-controls-calibration"],
            )
            self.assertEqual(teardowns, [False])

    def test_existing_seventh_runtime_record_fails_before_measurement(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            volume_root = Path(temporary_directory)
            (volume_root / SEVENTH_RUNTIME_FILENAME).write_text(
                "{}\n", encoding="utf-8"
            )
            connector_calls = []
            boundary = self._boundary(
                connect=lambda **kwargs: connector_calls.append(kwargs)
            )

            with self.assertRaises(FileExistsError):
                prepare_bootstrap(
                    volume_root,
                    Path("/does/not/reach/scenario.md"),
                    self.binding.scenario_commit,
                    boundary,
                )

            self.assertEqual(connector_calls, [])

    def test_connection_is_docker_dns_3306_and_password_is_env_only(self):
        captured = []

        def connect(**kwargs):
            captured.append(kwargs)
            return self.PureConnection()

        environment = {"MYSQL_PASSWORD": "secret-from-environment"}
        evidence = verify_connector_contract(
            self._module(have_cext=True),
            self.PureConnection,
            connect,
            environment,
        )
        command = build_invocation_command(
            "control-1", Path("/private/tmp/mysql-senior-scenarios.seventh")
        )

        self.assertEqual(captured[0]["host"], EXPECTED_HOST)
        self.assertEqual(captured[0]["port"], EXPECTED_PORT)
        self.assertEqual(captured[0]["password"], environment["MYSQL_PASSWORD"])
        self.assertIs(captured[0]["use_pure"], True)
        self.assertNotIn(environment["MYSQL_PASSWORD"], command)
        self.assertIn("--password-env", command)
        self.assertIn("MYSQL_PASSWORD", command)
        self.assertTrue(evidence["have_cext"])
        self.assertTrue(evidence["actual_pure"])

    def test_measured_ledger_rejects_second_invocation_id(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            ledger = InvocationLedger(root / "invocations.jsonl")
            ledger.start("kill-preflight-1")
            launches = []
            machine = HarnessStateMachine(
                runtime_root=root,
                binding=self.binding,
                ledger=ledger,
                environment={"MYSQL_PASSWORD": "secret"},
                launch=lambda *args: launches.append(args),
                create_manifest=lambda *args: None,
                teardown=lambda succeeded: None,
            )

            with self.assertRaisesRegex(ValueError, "invocation ID"):
                machine.execute("kill-preflight-1")

            self.assertEqual(launches, [])

    def test_bootstrap_rejects_wrong_connector_or_nonpure_connection(self):
        calls = []
        with self.assertRaisesRegex(RuntimeError, "9.7.0"):
            verify_connector_contract(
                self._module(version="9.6.0"),
                self.PureConnection,
                lambda **kwargs: calls.append(kwargs),
                {"MYSQL_PASSWORD": "secret"},
            )
        self.assertEqual(calls, [])

        with self.assertRaisesRegex(RuntimeError, "pure"):
            verify_connector_contract(
                self._module(have_cext=False),
                self.PureConnection,
                lambda **kwargs: self.OtherConnection(),
                {"MYSQL_PASSWORD": "secret"},
            )

    def test_bootstrap_rejects_wrong_cgroup_limits_mount_or_dns(self):
        cases = []
        wrong_cpu = {
            "/sys/fs/cgroup/cpu.max": "100000 100000\n",
            "/sys/fs/cgroup/memory.max": f"{EXPECTED_MEMORY}\n",
            "/sys/fs/cgroup/pids.max": f"{EXPECTED_PIDS}\n",
        }
        cases.append(("cpu", {"cgroups": wrong_cpu}))
        wrong_memory = dict(wrong_cpu)
        wrong_memory["/sys/fs/cgroup/cpu.max"] = "200000 100000\n"
        wrong_memory["/sys/fs/cgroup/memory.max"] = "1073741824\n"
        cases.append(("memory", {"cgroups": wrong_memory}))
        wrong_pids = dict(wrong_cpu)
        wrong_pids["/sys/fs/cgroup/cpu.max"] = "200000 100000\n"
        wrong_pids["/sys/fs/cgroup/pids.max"] = "128\n"
        cases.append(("pids", {"cgroups": wrong_pids}))
        wrong_mount = self._inspect()
        wrong_mount[0]["Mounts"][0]["Type"] = "bind"
        cases.append(("mount", {"inspect_document": wrong_mount}))
        cases.append(("dns", {"resolve_dns": lambda host, port: ()}))

        for label, changes in cases:
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    volume_root = Path(temporary_directory)
                    suffix_calls = []
                    boundary = self._boundary(
                        suffix_factory=lambda: suffix_calls.append("called"),
                        **changes,
                    )
                    with self.assertRaises(RuntimeError):
                        prepare_bootstrap(
                            volume_root,
                            Path("/does/not/reach/scenario.md"),
                            self.binding.scenario_commit,
                            boundary,
                        )
                    self.assertEqual(suffix_calls, [])
                    self.assertEqual(
                        list(volume_root.glob("mysql-senior-scenarios.*")), []
                    )

    def test_empty_password_fails_before_immutable_runtime_records(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            volume_root = Path(temporary_directory)
            boundary = self._boundary(environ={"IGNORED": "value"})
            with self.assertRaisesRegex(RuntimeError, "MYSQL_PASSWORD"):
                prepare_bootstrap(
                    volume_root, SCENARIO, self.binding.scenario_commit, boundary
                )
            self.assertFalse((volume_root / SEVENTH_RUNTIME_FILENAME).exists())
            self.assertFalse((volume_root / "historical-evidence-loss.json").exists())
            self.assertEqual(
                list(volume_root.glob("mysql-senior-scenarios.*")), []
            )

    def test_bootstrap_rejects_any_additional_bind_mount(self):
        for container_index in (0, 1):
            inspect_document = self._inspect()
            inspect_document[container_index].setdefault("Mounts", []).append(
                {
                    "Type": "bind",
                    "Source": "/host/other",
                    "Destination": "/opt/other",
                }
            )
            with self.subTest(container_index=container_index):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    with self.assertRaisesRegex(RuntimeError, "bind"):
                        prepare_bootstrap(
                            Path(temporary_directory),
                            Path("/does/not/reach/scenario.md"),
                            self.binding.scenario_commit,
                            self._boundary(inspect_document=inspect_document),
                        )

    def test_internal_identity_is_fresh_and_bound_to_bootstrap_container(self):
        boundary = self._boundary()
        bootstrap = {
            "harness_container_id": "harness-container-id",
            "harness_image_id": "sha256:harness-image",
        }
        expected = capture_internal_identity(boundary, bootstrap)
        observed = verify_internal_identity(boundary, bootstrap, expected)
        self.assertEqual(observed["hostname"], "harness-container-id")
        self.assertEqual(
            observed["harness_image_id_process_lifetime"], "sha256:harness-image"
        )
        for changed in (
            self._boundary(hostname="different-container\n"),
            self._boundary(resolve_dns=lambda host, port: ()),
            self._boundary(
                mountinfo=(
                    "100 1 0:1 / / rw - overlay overlay rw\n"
                    "102 100 0:3 / /private/tmp rw - ext4 /dev/changed rw\n"
                )
            ),
        ):
            with self.assertRaises(RuntimeError):
                verify_internal_identity(changed, bootstrap, expected)

    def test_outer_db_reach_failure_attempts_controlled_stop_once(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            context = BootstrapContext(
                root, self.binding, {}, {"hostname": "harness-container-id"}
            )
            calls = []

            class Database:
                def teardown(self, succeeded):
                    calls.append(succeeded)
                    (root / "controlled-stop.json").write_text(
                        "{}\n", encoding="utf-8"
                    )

            with self.assertRaisesRegex(RuntimeError, "bootstrap connection"):
                run_all_lifecycle(
                    context=context,
                    boundary=self._boundary(),
                    database_factory=lambda *args: Database(),
                    connector_verifier=lambda *args: (_ for _ in ()).throw(
                        RuntimeError("bootstrap connection failed")
                    ),
                    connector_writer=lambda *args: None,
                    machine_runner=lambda *args: self.fail("machine must not start"),
                )
            self.assertEqual(calls, [False])
            self.assertTrue((root / "controlled-stop.json").is_file())

    def test_failure_record_error_cannot_suppress_teardown(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            teardowns = []
            machine = HarnessStateMachine(
                runtime_root=root,
                binding=self.binding,
                ledger=InvocationLedger(root / "invocations.jsonl"),
                environment={"MYSQL_PASSWORD": "secret"},
                launch=lambda *args: {},
                create_manifest=lambda *args: None,
                prepare=lambda: (_ for _ in ()).throw(RuntimeError("primary failure")),
                teardown=lambda succeeded: teardowns.append(succeeded),
            )
            machine._failure_record = lambda error: (_ for _ in ()).throw(
                RuntimeError("failure record failed")
            )
            with self.assertRaisesRegex(
                RuntimeError, "primary failure.*failure record failed"
            ):
                machine.run()
            self.assertEqual(teardowns, [False])

    def test_failure_record_baseexception_runs_teardown_once_and_preserves_errors(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            teardowns = []

            class FailureRecordAbort(BaseException):
                def __str__(self):
                    if not teardowns:
                        raise RuntimeError("failure error combined before teardown")
                    return "failure record baseexception"

            def controlled_teardown(succeeded):
                teardowns.append(succeeded)
                (root / "controlled-stop.json").write_text(
                    "{}\n", encoding="utf-8"
                )

            machine = HarnessStateMachine(
                runtime_root=root,
                binding=self.binding,
                ledger=InvocationLedger(root / "invocations.jsonl"),
                environment={"MYSQL_PASSWORD": "secret"},
                launch=lambda *args: {},
                create_manifest=lambda *args: None,
                prepare=lambda: (_ for _ in ()).throw(RuntimeError("primary failure")),
                teardown=controlled_teardown,
            )
            machine._failure_record = lambda error: (_ for _ in ()).throw(
                FailureRecordAbort()
            )
            with self.assertRaises(RuntimeError) as captured:
                machine.run()
            self.assertIn("primary failure", str(captured.exception))
            self.assertIn("failure record baseexception", str(captured.exception))
            self.assertEqual(teardowns, [False])
            self.assertTrue((root / "controlled-stop.json").is_file())

    def test_reconciliation_failure_records_failed_terminal_only(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            job = root / "job-resume-1"
            job.mkdir()
            (job / "state.json").write_text(
                json.dumps(
                    {
                        "status": "ABORTED",
                        "rows_written": 2,
                        "next_part": 2,
                        "parts": [{}],
                    }
                ),
                encoding="utf-8",
            )
            ledger = InvocationLedger(root / "invocations.jsonl")
            machine = HarnessStateMachine(
                runtime_root=root,
                binding=self.binding,
                ledger=ledger,
                environment={"MYSQL_PASSWORD": "secret"},
                launch=lambda *args: {
                    "returncode": 0,
                    "status": "ABORTED",
                    "rows": 2,
                    "parts": 1,
                },
                create_manifest=lambda *args: None,
                teardown=lambda succeeded: None,
            )
            with self.assertRaisesRegex(RuntimeError, "checkpoint"):
                machine.execute("resume-interrupt-1")
            records = [
                json.loads(line)
                for line in (root / "invocations.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual([record["state"] for record in records], ["STARTING", "FAILED"])

    def test_controller_and_direct_resume_routing_is_exact(self):
        root = Path("/private/tmp/mysql-senior-scenarios.seventh")
        for invocation_id in INVOCATIONS[:-2]:
            command = build_invocation_command(invocation_id, root)
            self.assertEqual(command[1], str(root / "scenario_controller.py"))
            self.assertIn("--trial-id", command)
        for invocation_id, maximum in (
            ("resume-interrupt-1", "3"),
            ("resume-complete-1", "0"),
        ):
            command = build_invocation_command(invocation_id, root)
            self.assertEqual(command[1], str(root / "export_runner.py"))
            self.assertNotIn("scenario_controller.py", command)
            self.assertEqual(
                command[command.index("--job-dir") + 1], str(root / "job-resume-1")
            )
            self.assertEqual(command[command.index("--max-batches") + 1], maximum)

    def test_six_owned_freeze_triggers_have_exact_signal_contract(self):
        self.assertEqual(
            FREEZE_TRIGGER_NAMES,
            (
                "freeze_report_order_insert",
                "freeze_report_order_update",
                "freeze_report_order_delete",
                "freeze_report_item_insert",
                "freeze_report_item_update",
                "freeze_report_item_delete",
            ),
        )
        self.assertEqual(len(FREEZE_TRIGGER_SQL), 6)
        for name, sql in zip(FREEZE_TRIGGER_NAMES, FREEZE_TRIGGER_SQL):
            self.assertIn(f"CREATE TRIGGER {name}", sql)
            self.assertIn("FOR EACH ROW", sql)
            self.assertIn("SIGNAL SQLSTATE '45000'", sql)
            self.assertIn(
                "MESSAGE_TEXT='report source is frozen for mysql senior scenario'",
                sql,
            )

    def test_negative_probe_requires_exact_sqlstate_and_message(self):
        class ProbeError(Exception):
            def __init__(self, sqlstate, msg):
                super().__init__(msg)
                self.sqlstate = sqlstate
                self.msg = msg

        expected = "report source is frozen for mysql senior scenario"
        self.assertEqual(
            validate_negative_probe_error(ProbeError("45000", expected)),
            {"message": expected, "sqlstate": "45000"},
        )
        for error in (
            ProbeError("42000", expected),
            ProbeError("45000", "wrong freeze message"),
        ):
            with self.assertRaises(RuntimeError):
                validate_negative_probe_error(error)

    def test_trigger_snapshot_requires_exact_six_definitions(self):
        message = "report source is frozen for mysql senior scenario"
        rows = [
            (
                name,
                operation,
                table,
                "BEFORE",
                f"SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '{message}'",
            )
            for name, table, operation in (
                ("freeze_report_order_insert", "report_order", "INSERT"),
                ("freeze_report_order_update", "report_order", "UPDATE"),
                ("freeze_report_order_delete", "report_order", "DELETE"),
                ("freeze_report_item_insert", "report_item", "INSERT"),
                ("freeze_report_item_update", "report_item", "UPDATE"),
                ("freeze_report_item_delete", "report_item", "DELETE"),
            )
        ]
        self.assertEqual(len(validate_freeze_trigger_rows(rows)), 6)
        for changed in (rows[:-1], rows + [rows[0]], [(*rows[0][:-1], "SET @x=1"), *rows[1:]]):
            with self.assertRaises(RuntimeError):
                validate_freeze_trigger_rows(changed)

        class Cursor:
            def __init__(self):
                self.calls = []

            def execute(self, sql):
                self.calls.append(sql)

            def fetchall(self):
                return rows

        cursor = Cursor()
        self.assertEqual(len(snapshot_freeze_triggers(cursor)), 6)
        self.assertIn("information_schema.TRIGGERS", cursor.calls[0])

    def test_canonical_source_counts_and_probe_audit_are_strict(self):
        manifest = {
            "orders": 100000,
            "min_cursor": ["2026-01-01 00:00:01.000000", 1],
            "high_cursor": ["2026-01-02 03:46:40.000000", 100000],
            "order_crc32_sum": 123,
            "items": 300000,
            "item_orders": 100000,
            "item_crc32_sum": 456,
            "min_items_per_order": 3,
            "max_items_per_order": 3,
            "probes": 10000,
            "probe_counter_sum": 0,
            "report_rows": 100000,
            "total_amount_fingerprint": "150003000.00",
            "item_count_fingerprint": 300000,
        }
        self.assertEqual(validate_source_manifest(manifest), manifest)
        for field, invalid in (
            ("orders", 99999),
            ("items", 299999),
            ("probes", True),
            ("item_count_fingerprint", 299999),
        ):
            with self.subTest(field=field):
                changed = dict(manifest)
                changed[field] = invalid
                with self.assertRaises(RuntimeError):
                    validate_source_manifest(changed)

    def test_seed_reference_pins_crc_amount_and_probe_schema(self):
        expected = canonical_seed_reference()
        self.assertEqual(expected, EXPECTED_SEED_MANIFEST)
        self.assertEqual(expected["order_crc32_sum"], 214876779439655)
        self.assertEqual(expected["item_crc32_sum"], 644951398284901)
        self.assertEqual(expected["total_amount_fingerprint"], "300002000.00")
        self.assertEqual(expected["item_count_fingerprint"], 300000)
        self.assertEqual(
            EXPECTED_PROBE_SCHEMA,
            [
                {"values": ["COLUMN", "id", 1, "bigint unsigned", "NO", None, ""]},
                {"values": ["COLUMN", "counter", 2, "bigint unsigned", "NO", "0", ""]},
                {"values": ["COLUMN", "payload", 3, "varchar(128)", "NO", None, ""]},
                {"values": ["INDEX", "PRIMARY", 1, "id", 0, "BTREE", None]},
            ],
        )
        self.assertEqual(
            validate_seed_baseline(dict(expected), list(EXPECTED_PROBE_SCHEMA)),
            expected,
        )
        wrong_crc = dict(expected)
        wrong_crc["order_crc32_sum"] += 1
        wrong_amount = dict(expected)
        wrong_amount["total_amount_fingerprint"] = "300002001.00"
        wrong_schema = [dict(row) for row in EXPECTED_PROBE_SCHEMA]
        wrong_schema[1] = {"values": list(wrong_schema[1]["values"])}
        wrong_schema[1]["values"][5] = "1"
        for manifest, schema in (
            (wrong_crc, EXPECTED_PROBE_SCHEMA),
            (wrong_amount, EXPECTED_PROBE_SCHEMA),
            (expected, wrong_schema),
        ):
            with self.assertRaises(RuntimeError):
                validate_seed_baseline(manifest, schema)

    def test_crc_queries_and_connector_integer_normalization_are_exact(self):
        self.assertIn("AS order_crc32_sum", ORDER_CRC32_SQL)
        self.assertIn("DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s.%f')", ORDER_CRC32_SQL)
        self.assertEqual(ORDER_CRC32_SQL.count("CAST(id AS CHAR)"), 1)
        self.assertIn("AS item_crc32_sum", ITEM_CRC32_SQL)
        self.assertIn("CAST(unit_price AS CHAR)", ITEM_CRC32_SQL)
        self.assertIn("CONCAT_WS('#'", ITEM_CRC32_SQL)
        self.assertEqual(exact_db_int(Decimal("123"), "crc"), 123)
        self.assertEqual(exact_db_int(123, "crc"), 123)
        for invalid in (True, "123", Decimal("1.5")):
            with self.assertRaises(RuntimeError):
                exact_db_int(invalid, "crc")

    def test_teardown_failure_never_writes_final_manifest(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            calls = []
            manifests = []

            machine = self._machine(root, calls, manifests, [], fail=None)
            machine.teardown = lambda succeeded: (_ for _ in ()).throw(
                RuntimeError("teardown audit failed")
            )
            with self.assertRaisesRegex(RuntimeError, "teardown audit failed"):
                machine.run()
            self.assertEqual(tuple(calls), INVOCATIONS)
            self.assertEqual(tuple(manifests), PHASES[:-1])


class PhaseManifestTests(unittest.TestCase):
    binding = EvidenceBinding(
        scenario_commit="0e927a9534cb214641885d110b4e98ef7a313a54",
        scenario_sha256="a" * 64,
        mysql_image_id="sha256:mysql-image",
        mysql_container_id="mysql-senior-scenarios-primary",
        harness_image_id="sha256:harness-image",
        network_name="mysql-senior-scenarios-network",
        volume_name="mysql-senior-scenarios-evidence",
        cpu_limit="2",
        memory_limit_bytes=2 * 1024 * 1024 * 1024,
        pids_limit=256,
        program_sha256={
            "export_runner.py": "b" * 64,
            "scenario_controller.py": "c" * 64,
            "freeze_audit.py": "d" * 64,
        },
    )

    def _write(self, root: Path, relative_path: str, content: bytes) -> None:
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def _manifest(self, root: Path, phase: str) -> dict:
        return json.loads(
            (root / f"phase-manifest-{phase}.json").read_text(encoding="utf-8")
        )

    def _create_through_final(self, root: Path) -> None:
        for phase in (
            "00-seed-freeze",
            "10-kill-smoke",
            "20-controls-calibration",
            "30-buffered",
            "40-chunked",
            "50-resume-audit",
            "60-final",
        ):
            create_phase_manifest(root, phase, self.binding)

    def test_manifest_records_ordered_regular_files_and_tree_hash(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            runtime_root = Path(temporary_directory)
            self._write(runtime_root, "nested/a.txt", b"a")
            self._write(runtime_root, "b.txt", b"bb")

            create_phase_manifest(runtime_root, "00-seed-freeze", self.binding)
            manifest = self._manifest(runtime_root, "00-seed-freeze")
            entries = manifest["entries"]
            self.assertEqual(
                set(manifest),
                {
                    "binding",
                    "byte_count",
                    "entries",
                    "file_count",
                    "phase",
                    "status",
                    "timestamp",
                    "tree_hash",
                },
            )
            self.assertEqual(manifest["binding"], self.binding.serialize())
            self.assertEqual(
                set(manifest["binding"]),
                {
                    "scenario_commit",
                    "scenario_sha256",
                    "mysql_image_id",
                    "mysql_container_id",
                    "harness_image_id",
                    "network_name",
                    "volume_name",
                    "cpu_limit",
                    "memory_limit_bytes",
                    "pids_limit",
                    "program_sha256",
                },
            )
            self.assertEqual(manifest["status"], "COMPLETE")
            self.assertIs(type(manifest["timestamp"]), str)
            self.assertRegex(
                manifest["timestamp"],
                r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z$",
            )
            self.assertEqual(
                datetime.fromisoformat(manifest["timestamp"].replace("Z", "+00:00")).tzinfo,
                timezone.utc,
            )
            self.assertEqual(manifest["file_count"], len(entries))
            self.assertEqual(manifest["byte_count"], sum(entry["size"] for entry in entries))
            self.assertEqual([entry["path"] for entry in entries], ["b.txt", "nested/a.txt"])
            line_stream = "".join(
                f"{entry['path']}\0{entry['size']}\0{entry['sha256']}\n"
                for entry in entries
            )
            self.assertEqual(
                hashlib.sha256(line_stream.encode("utf-8")).hexdigest(),
                manifest["tree_hash"],
            )
            self.assertEqual(
                verify_phase_manifests(runtime_root, self.binding)[0], manifest
            )

    def test_second_write_of_same_phase_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            runtime_root = Path(temporary_directory)
            self._write(runtime_root, "evidence.txt", b"seed")
            create_phase_manifest(runtime_root, "00-seed-freeze", self.binding)
            with self.assertRaises(FileExistsError):
                create_phase_manifest(runtime_root, "00-seed-freeze", self.binding)

    def test_phase_manifest_requires_evidence_binding(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            runtime_root = Path(temporary_directory)
            self._write(runtime_root, "evidence.txt", b"seed")
            with self.assertRaisesRegex(ValueError, "EvidenceBinding"):
                create_phase_manifest(
                    runtime_root,
                    "00-seed-freeze",
                    {"scenario_commit": "not-a-binding"},
                )

    def test_evidence_binding_requires_exact_fields_and_types(self):
        self.assertEqual(
            self.binding.serialize(),
            {
                "scenario_commit": "0e927a9534cb214641885d110b4e98ef7a313a54",
                "scenario_sha256": "a" * 64,
                "mysql_image_id": "sha256:mysql-image",
                "mysql_container_id": "mysql-senior-scenarios-primary",
                "harness_image_id": "sha256:harness-image",
                "network_name": "mysql-senior-scenarios-network",
                "volume_name": "mysql-senior-scenarios-evidence",
                "cpu_limit": "2",
                "memory_limit_bytes": 2 * 1024 * 1024 * 1024,
                "pids_limit": 256,
                "program_sha256": {
                    "export_runner.py": "b" * 64,
                    "scenario_controller.py": "c" * 64,
                    "freeze_audit.py": "d" * 64,
                },
            },
        )
        with self.assertRaisesRegex(ValueError, "memory_limit_bytes"):
            replace(self.binding, memory_limit_bytes=True)
        with self.assertRaisesRegex(ValueError, "scenario_commit"):
            replace(self.binding, scenario_commit="")
        with self.assertRaisesRegex(ValueError, "lowercase SHA-256"):
            replace(
                self.binding,
                program_sha256={"export_runner.py": "A" * 64},
            )

    def test_manifest_rejects_bool_count_and_non_utc_timestamp(self):
        def assert_rejected(mutate) -> None:
            with tempfile.TemporaryDirectory() as temporary_directory:
                runtime_root = Path(temporary_directory)
                self._write(runtime_root, "evidence.txt", b"seed")
                create_phase_manifest(runtime_root, "00-seed-freeze", self.binding)
                manifest_path = runtime_root / "phase-manifest-00-seed-freeze.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                mutate(manifest)
                manifest_path.write_text(
                    json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
                    encoding="utf-8",
                )
                with self.assertRaises(ValueError):
                    verify_phase_manifests(runtime_root, self.binding)

        assert_rejected(lambda manifest: manifest.__setitem__("file_count", True))
        assert_rejected(
            lambda manifest: manifest.__setitem__(
                "timestamp", "2026-08-02T12:00:00+00:00"
            )
        )

    def test_prior_file_mutation_is_rejected_before_next_phase(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            runtime_root = Path(temporary_directory)
            self._write(runtime_root, "evidence.txt", b"seed")
            create_phase_manifest(runtime_root, "00-seed-freeze", self.binding)
            self._write(runtime_root, "evidence.txt", b"changed")

            with self.assertRaises(ValueError):
                create_phase_manifest(runtime_root, "10-kill-smoke", self.binding)

    def test_phase_skip_or_reordering_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            runtime_root = Path(temporary_directory)
            self._write(runtime_root, "evidence.txt", b"seed")
            with self.assertRaises(ValueError):
                create_phase_manifest(runtime_root, "10-kill-smoke", self.binding)
            create_phase_manifest(runtime_root, "00-seed-freeze", self.binding)
            create_phase_manifest(runtime_root, "10-kill-smoke", self.binding)
            (runtime_root / "phase-manifest-00-seed-freeze.json").unlink()
            with self.assertRaises(ValueError):
                create_phase_manifest(runtime_root, "00-seed-freeze", self.binding)

    def test_missing_extra_corrupt_symlink_and_fifo_are_rejected(self):
        def assert_rejected(mutate) -> None:
            with tempfile.TemporaryDirectory() as temporary_directory:
                runtime_root = Path(temporary_directory)
                self._write(runtime_root, "evidence.txt", b"seed")
                create_phase_manifest(runtime_root, "00-seed-freeze", self.binding)
                mutate(runtime_root)
                with self.assertRaises(ValueError):
                    create_phase_manifest(runtime_root, "10-kill-smoke", self.binding)
                self.assertFalse(
                    (runtime_root / "phase-manifest-10-kill-smoke.json").exists()
                )

        assert_rejected(lambda root: (root / "evidence.txt").unlink())
        assert_rejected(
            lambda root: (root / "phase-manifest-20-controls-calibration.json").write_text(
                "{}\n", encoding="utf-8"
            )
        )

        def corrupt(root: Path) -> None:
            manifest = root / "phase-manifest-00-seed-freeze.json"
            manifest.write_text("not-json\n", encoding="utf-8")

        assert_rejected(corrupt)

        def symlink(root: Path) -> None:
            os.symlink(root / "evidence.txt", root / "link.txt")

        assert_rejected(symlink)

        def fifo(root: Path) -> None:
            os.mkfifo(root / "stream")

        assert_rejected(fifo)

    def test_bool_float_and_numeric_string_are_rejected_for_integer_fields(self):
        for invalid in (True, 1.0, "1"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    require_exact_int(invalid, "file_count")

    def test_final_manifest_covers_every_regular_file_except_itself(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            runtime_root = Path(temporary_directory)
            self._write(runtime_root, "nested/evidence.txt", b"seed")
            self._write(
                runtime_root,
                "nested/phase-manifest-60-final.json",
                b"legitimate nested evidence",
            )
            self._create_through_final(runtime_root)

            manifest = self._manifest(runtime_root, "60-final")
            verify_final_coverage(runtime_root, manifest)
            expected_paths = {
                path.relative_to(runtime_root).as_posix()
                for path in runtime_root.rglob("*")
                if path.is_file()
                and not path.is_symlink()
                and path.relative_to(runtime_root).as_posix()
                != "phase-manifest-60-final.json"
            }
            self.assertEqual(
                {entry["path"] for entry in manifest["entries"]}, expected_paths
            )
            self.assertIn(
                "nested/phase-manifest-60-final.json",
                {entry["path"] for entry in manifest["entries"]},
            )


if __name__ == "__main__":
    unittest.main()
