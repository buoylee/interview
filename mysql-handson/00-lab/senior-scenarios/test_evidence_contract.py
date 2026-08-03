import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from evidence_contract import (
    HISTORICAL_LOSS_STATUS,
    HISTORICAL_PATHS,
    create_historical_loss,
    create_phase_manifest,
    extract_programs,
    require_exact_int,
    verify_final_coverage,
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
            target = create_historical_loss(runtime_root)
            record = json.loads(target.read_text(encoding="utf-8"))

            self.assertEqual(tuple(record["historical_paths"]), HISTORICAL_PATHS)
            self.assertIs(type(record["status"]), str)
            self.assertEqual(record["status"], HISTORICAL_LOSS_STATUS)
            self.assertIs(type(record["verification_succeeded"]), bool)
            self.assertFalse(record["verification_succeeded"])
            with self.assertRaises(FileExistsError):
                create_historical_loss(runtime_root)


class PhaseManifestTests(unittest.TestCase):
    binding = {"scenario": "report-export-isolation", "version": 1}

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
            self.assertEqual([entry["path"] for entry in entries], ["b.txt", "nested/a.txt"])
            line_stream = "".join(
                f"{entry['path']}\0{entry['size']}\0{entry['sha256']}\n"
                for entry in entries
            )
            self.assertEqual(
                hashlib.sha256(line_stream.encode("utf-8")).hexdigest(),
                manifest["tree_hash"],
            )

    def test_second_write_of_same_phase_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            runtime_root = Path(temporary_directory)
            self._write(runtime_root, "evidence.txt", b"seed")
            create_phase_manifest(runtime_root, "00-seed-freeze", self.binding)
            with self.assertRaises(FileExistsError):
                create_phase_manifest(runtime_root, "00-seed-freeze", self.binding)

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
            self._create_through_final(runtime_root)
            verify_final_coverage(runtime_root, self.binding)

            manifest = self._manifest(runtime_root, "60-final")
            expected_paths = {
                path.relative_to(runtime_root).as_posix()
                for path in runtime_root.rglob("*")
                if path.is_file()
                and not path.is_symlink()
                and path.name != "phase-manifest-60-final.json"
            }
            self.assertEqual(
                {entry["path"] for entry in manifest["entries"]}, expected_paths
            )


if __name__ == "__main__":
    unittest.main()
