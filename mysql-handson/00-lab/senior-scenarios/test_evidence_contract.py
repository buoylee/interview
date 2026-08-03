import hashlib
import json
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from evidence_contract import (
    EvidenceBinding,
    HISTORICAL_LOSS_STATUS,
    HISTORICAL_PATHS,
    create_phase_manifest,
    extract_programs,
    require_exact_int,
    verify_phase_manifests,
    verify_final_coverage,
    write_historical_loss,
)


SCENARIO = Path("/opt/scenario.md")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
