import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from verifier import timeline


ROOT = Path(__file__).resolve().parents[1]


class ScenarioRunnerTest(unittest.TestCase):
    def controlled_runner(self, fail_verifier_build=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "ha"
        (root / "scenarios").mkdir(parents=True)
        shutil.copy(ROOT / "scenarios/run.sh", root / "scenarios/run.sh")
        (root / "evidence").mkdir()
        bin_dir = root / "bin"
        bin_dir.mkdir()
        make_log = root / "make.log"
        docker_log = root / "docker.log"
        (bin_dir / "make").write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s\\n' \"$*\" >> \"$FAKE_MAKE_LOG\"\n"
            "exit 0\n",
            encoding="utf-8",
        )
        (bin_dir / "docker").write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s\\n' \"$*\" >> \"$FAKE_DOCKER_LOG\"\n"
            "case \"$*\" in\n"
            "  *' build verifier'*) [ \"${FAKE_BUILD_FAIL:-0}\" = 0 ] || exit 73 ;;\n"
            "  *'exec -T db1 mysql'*) printf 'db1\\n' ;;\n"
            "  *'verifier.timeline'*) touch \"$FAKE_ROOT/evidence/timeline-ready\"; sleep 0.2 ;;\n"
            "  *'verifier.session_probe'*) touch \"$FAKE_ROOT/evidence/session-ready\"; sleep 0.2 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        for command in (bin_dir / "make", bin_dir / "docker", root / "scenarios/run.sh"):
            command.chmod(0o755)
        environment = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "FAKE_MAKE_LOG": str(make_log),
            "FAKE_DOCKER_LOG": str(docker_log),
            "FAKE_ROOT": str(root),
            "FAKE_BUILD_FAIL": "1" if fail_verifier_build else "0",
            "WARMUP_SECONDS": "0",
            "FAULT_SECONDS": "0",
            "RECOVERY_SECONDS": "0",
        }
        return root, make_log, docker_log, environment

    def test_runner_builds_verifier_before_launching_observers(self):
        """Catches observers running from the stale service image."""
        root, _make_log, docker_log, environment = self.controlled_runner()

        result = subprocess.run(
            ["bash", "scenarios/run.sh", "primary-crash"],
            cwd=root,
            env=environment,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = docker_log.read_text(encoding="utf-8")
        self.assertLess(calls.index("build verifier"), calls.index("verifier.timeline"))
        self.assertLess(calls.index("build verifier"), calls.index("verifier.session_probe"))

    def test_verifier_build_failure_stops_before_observers_and_fault(self):
        """Catches a failed verifier build being ignored before fault injection."""
        root, make_log, docker_log, environment = self.controlled_runner(
            fail_verifier_build=True
        )

        result = subprocess.run(
            ["bash", "scenarios/run.sh", "primary-crash"],
            cwd=root,
            env=environment,
            text=True,
            capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        docker_calls = docker_log.read_text(encoding="utf-8")
        make_calls = make_log.read_text(encoding="utf-8")
        self.assertIn("build verifier", docker_calls)
        self.assertNotIn("verifier.timeline", docker_calls)
        self.assertNotIn("verifier.session_probe", docker_calls)
        self.assertNotIn("fault SCENARIO=primary-crash", make_calls)

    def test_timeline_marks_ready_before_waiting_for_fault_begin(self):
        """Catches an observer that the runner cannot prove was ready."""
        with tempfile.TemporaryDirectory() as directory:
            evidence_dir = Path(directory)
            observed = []

            def wait_for_fault_begin(_events, _phase, _deadline):
                observed.append((evidence_dir / "timeline-ready").exists())
                raise TimeoutError("stop after readiness check")

            with (
                patch("sys.argv", [
                    "timeline", "--old-primary", "db1", "--evidence-dir", str(evidence_dir),
                ]),
                patch("verifier.timeline.wait_for_phase", side_effect=wait_for_fault_begin),
            ):
                with self.assertRaises(SystemExit):
                    timeline.main()

            self.assertEqual(observed, [True])

    def test_runner_stops_before_fault_when_timeline_exits_early(self):
        """Catches a runner that faults the cluster after its observer already died."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "ha"
        (root / "scenarios").mkdir(parents=True)
        shutil.copy(ROOT / "scenarios/run.sh", root / "scenarios/run.sh")
        (root / "evidence").mkdir()
        bin_dir = root / "bin"
        bin_dir.mkdir()
        log = root / "make.log"
        (bin_dir / "make").write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s\\n' \"$*\" >> \"$FAKE_MAKE_LOG\"\n"
            "exit 0\n",
            encoding="utf-8",
        )
        (bin_dir / "docker").write_text(
            "#!/usr/bin/env bash\n"
            "case \"$*\" in\n"
            "  *'exec -T db1 mysql'*) printf 'db1\\n' ;;\n"
            "  *'verifier.timeline'*) exit 1 ;;\n"
            "  *'verifier.session_probe'*) touch \"$FAKE_ROOT/evidence/session-ready\"; sleep 5 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        for command in (bin_dir / "make", bin_dir / "docker", root / "scenarios/run.sh"):
            command.chmod(0o755)
        environment = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "FAKE_MAKE_LOG": str(log),
            "FAKE_ROOT": str(root),
            "WARMUP_SECONDS": "0",
        }

        result = subprocess.run(
            ["bash", "scenarios/run.sh", "primary-crash"],
            cwd=root,
            env=environment,
            text=True,
            capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        calls = log.read_text(encoding="utf-8") if log.exists() else ""
        self.assertNotIn("fault SCENARIO=primary-crash", calls)


if __name__ == "__main__":
    unittest.main()
