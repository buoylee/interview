import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PitrScenarioTest(unittest.TestCase):
    def test_scenario_runner_executes_pitr_without_entering_fault_lifecycle(self):
        """Catches Scenario 08 being rejected or routed through the 01-07 fault runner."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ha"
            (root / "scenarios").mkdir(parents=True)
            shutil.copy2(ROOT / "scenarios/run.sh", root / "scenarios/run.sh")
            pitr = root / "scenarios/pitr.sh"
            pitr.write_text("#!/usr/bin/env bash\nprintf 'pitr-only\\n'\n", encoding="utf-8")
            pitr.chmod(0o755)

            result = subprocess.run(
                ["bash", "scenarios/run.sh", "ha-cannot-replace-pitr"],
                cwd=root, text=True, capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "pitr-only\n")

    @unittest.skipUnless(shutil.which("make"), "requires make to execute the reset recipe")
    def test_reset_includes_profile_scoped_recovery_volume(self):
        """Catches a normal reset that leaks the recovery container or volume."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ha"
            root.mkdir()
            shutil.copy2(ROOT / "Makefile", root / "Makefile")
            (root / "compose.yml").write_text("name: mysql-ha\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir()
            log = root / "docker.log"
            docker = bin_dir / "docker"
            docker.write_text(
                "#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> \"$FAKE_DOCKER_LOG\"\n",
                encoding="utf-8",
            )
            docker.chmod(0o755)
            environment = {
                **os.environ,
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
                "FAKE_DOCKER_LOG": str(log),
            }

            result = subprocess.run(
                ["make", "reset"], cwd=root, env=environment,
                text=True, capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                log.read_text(encoding="utf-8"),
                "compose --project-name mysql-ha --file compose.yml --profile recovery down --volumes --remove-orphans\n",
            )

    def controlled_root(
        self, stop_status="binlog.000002\t420\t\t\t", altered_created_at=False,
        recovery_ready_after=1,
    ):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "ha"
        (root / "scenarios").mkdir(parents=True)
        (root / "evidence").mkdir()
        source = ROOT / "scenarios/pitr.sh"
        self.assertTrue(source.exists(), "PITR orchestration is missing")
        shutil.copy2(source, root / "scenarios/pitr.sh")
        (root / "compose.yml").write_text("name: mysql-ha\n", encoding="utf-8")
        bin_dir = root / "bin"
        bin_dir.mkdir()
        docker_log = root / "docker.log"
        make_log = root / "make.log"
        fake_make = bin_dir / "make"
        fake_make.write_text(
            "#!/usr/bin/env bash\n"
            "set -eu\n"
            "printf '%s\\n' \"$*\" >> \"$FAKE_MAKE_LOG\"\n",
            encoding="utf-8",
        )
        fake_make.chmod(0o755)
        fake_docker = bin_dir / "docker"
        fake_docker.write_text(
            "#!/usr/bin/env bash\n"
            "set -eu\n"
            "printf '%s\\n' \"$*\" >> \"$FAKE_DOCKER_LOG\"\n"
            "case \"$*\" in\n"
            "  *\"MEMBER_ROLE='PRIMARY'\"*) printf 'db1\\n' ;;\n"
            "  *\"mysqldump\"*) printf '%s\\n' \"-- CHANGE REPLICATION SOURCE TO SOURCE_LOG_FILE='binlog.000002', SOURCE_LOG_POS=157;\" 'CREATE DATABASE ha_lab;' ;;\n"
            "  *\"SHOW BINARY LOG STATUS\"*) printf '%b\\n' \"$FAKE_STOP_STATUS\" ;;\n"
            "  *\"INSERT INTO ha_lab.orders\"*) touch \"$FAKE_STATE_DIR/keep\" ;;\n"
            "  *\"DELETE FROM ha_lab.orders\"*) touch \"$FAKE_STATE_DIR/deleted\" ;;\n"
            "  *\"HEX(request_id)\"*)\n"
            "    include_created=0; [[ \"$*\" = *\"created_at\"* ]] && include_created=1\n"
            "    for i in $(seq 1 10); do\n"
            "      printf 'H726F772D%s\\tH7B7D\\tH726F757465722D62\\tH646231' \"$i\"\n"
            "      if [ \"$include_created\" = 1 ]; then\n"
            "        created=H323032362D30372D32382030363A30303A30302E303030303030\n"
            "        if [[ \"$*\" = *\"exec -T recovery\"* ]] && [ \"${FAKE_ALTERED_CREATED_AT:-0}\" = 1 ] && [ \"$i\" = 2 ]; then created=H323032362D30372D32382030363A30303A30312E303030303030; fi\n"
            "        printf '\\t%s' \"$created\"\n"
            "      fi\n"
            "      printf '\\n'\n"
            "    done\n"
            "    printf 'H706974722D6B656570\\tH7B7D\\tH726F757465722D61\\tH646231'\n"
            "    [ \"$include_created\" = 0 ] || printf '\\tH323032362D30372D32382030363A30303A30302E303030303030'\n"
            "    printf '\\n' ;;\n"
            "  *\"SELECT COUNT(*) FROM ha_lab.orders\"*)\n"
            "    case \"$*\" in *\"exec -T recovery\"*) printf '11\\n' ;; *\"exec -T db\"*) if [ -f \"$FAKE_STATE_DIR/deleted\" ]; then printf '0\\n'; else printf '10\\n'; fi ;; *) printf '11\\n' ;; esac ;;\n"
            "  *\"WHERE request_id='pitr-keep'\"*) printf 'pitr-keep\\n' ;;\n"
            "  *\"SELECT 1 /* recovery-readiness */\"*)\n"
            "    attempts=0; [ ! -f \"$FAKE_READINESS_COUNT\" ] || attempts=$(cat \"$FAKE_READINESS_COUNT\")\n"
            "    attempts=$((attempts + 1)); printf '%s' \"$attempts\" > \"$FAKE_READINESS_COUNT\"\n"
            "    if [ \"$attempts\" -lt \"$FAKE_RECOVERY_READY_AFTER\" ]; then exit 1; fi\n"
            "    printf '1\\n' ;;\n"
            "  *\"replication_group_members\"*) printf 'db1\\tONLINE\\tPRIMARY\\ndb2\\tONLINE\\tSECONDARY\\ndb3\\tONLINE\\tSECONDARY\\n' ;;\n"
            "  *\"mysqladmin ping\"*) exit 0 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        fake_docker.chmod(0o755)
        environment = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "FAKE_DOCKER_LOG": str(docker_log),
            "FAKE_MAKE_LOG": str(make_log),
            "FAKE_STOP_STATUS": stop_status,
            "FAKE_STATE_DIR": str(root),
            "FAKE_ALTERED_CREATED_AT": "1" if altered_created_at else "0",
            "FAKE_READINESS_COUNT": str(root / "readiness-count"),
            "FAKE_RECOVERY_READY_AFTER": str(recovery_ready_after),
        }
        return root, docker_log, make_log, environment

    def test_pitr_waits_for_authenticated_recovery_sql_not_server_ping(self):
        """Catches mysqladmin ping accepting the temporary unauthenticated init server."""
        root, docker_log, _make_log, environment = self.controlled_root(
            recovery_ready_after=3,
        )

        result = subprocess.run(
            ["bash", "scenarios/pitr.sh"], cwd=root, env=environment,
            text=True, capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = docker_log.read_text(encoding="utf-8")
        self.assertEqual(calls.count("SELECT 1 /* recovery-readiness */"), 3)
        readiness_calls = [
            line for line in calls.splitlines()
            if "SELECT 1 /* recovery-readiness */" in line
        ]
        self.assertTrue(all("mysql -h127.0.0.1" in line for line in readiness_calls))
        self.assertNotIn("exec -T recovery mysqladmin ping", calls)

    def test_pitr_orders_isolated_recovery_and_proves_pre_delete_rows(self):
        """Catches replay that races its dump boundary, includes DELETE, or targets the Cluster."""
        root, docker_log, make_log, environment = self.controlled_root()

        result = subprocess.run(
            ["bash", "scenarios/pitr.sh"], cwd=root, env=environment,
            text=True, capture_output=True,
        )

        base = root / "evidence/pitr/base.sql"
        diagnostic = base.read_text(encoding="utf-8") if base.exists() else "<no dump>"
        self.assertEqual(result.returncode, 0, f"{result.stderr}\ndump={diagnostic!r}")
        calls = docker_log.read_text(encoding="utf-8")
        self.assertLess(calls.index("mysqldump"), calls.index("pitr-keep"))
        self.assertLess(calls.index("pitr-keep"), calls.index("DELETE FROM ha_lab.orders"))
        self.assertLess(calls.index("DELETE FROM ha_lab.orders"), calls.index("--profile recovery up -d recovery"))
        self.assertIn("--start-position=157 --stop-position=420 binlog.000002", calls)
        self.assertIn("-hrecovery", calls)
        self.assertNotIn("mysql --binary-mode=1 -hdb", calls)
        self.assertIn("reset", make_log.read_text(encoding="utf-8"))
        evidence = root / "evidence/pitr"
        self.assertEqual((evidence / "source-primary.txt").read_text(), "db1\n")
        self.assertEqual((evidence / "base-count.txt").read_text(), "10\n")
        self.assertEqual((evidence / "expected-count.txt").read_text(), "11\n")
        self.assertEqual((evidence / "recovered-count.txt").read_text(), "11\n")
        self.assertEqual((evidence / "recovery-keep-row.txt").read_text(), "pitr-keep\n")
        self.assertEqual(
            (evidence / "expected-projection.tsv").read_bytes(),
            (evidence / "recovered-projection.tsv").read_bytes(),
        )
        self.assertTrue(all(
            len(line.split(b"\t")) == 5
            for line in (evidence / "expected-projection.tsv").read_bytes().splitlines()
        ))
        self.assertEqual((evidence / "member-zero.txt").read_text(), "db1 0\ndb2 0\ndb3 0\n")
        self.assertEqual(
            (evidence / "final-member-counts.txt").read_text(),
            "db1 0\ndb2 0\ndb3 0\n",
        )
        self.assertEqual((evidence / "binlog-window.txt").read_text(), "binlog.000002 157 420\n")

    def test_pitr_rejects_same_count_and_keep_with_altered_created_at(self):
        """Catches a five-column projection that omits or normalizes created_at."""
        root, _docker_log, _make_log, environment = self.controlled_root(
            altered_created_at=True,
        )

        result = subprocess.run(
            ["bash", "scenarios/pitr.sh"], cwd=root, env=environment,
            text=True, capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        evidence = root / "evidence/pitr"
        self.assertEqual((evidence / "expected-count.txt").read_text(), "11\n")
        self.assertEqual((evidence / "recovered-count.txt").read_text(), "11\n")
        self.assertEqual((evidence / "recovery-keep-row.txt").read_text(), "pitr-keep\n")
        self.assertNotEqual(
            (evidence / "expected-projection.tsv").read_bytes(),
            (evidence / "recovered-projection.tsv").read_bytes(),
        )
        runs = root / "evidence/runs/ha-cannot-replace-pitr"
        self.assertFalse(runs.exists(), "mismatched recovery must not be archived as success")

    def test_pitr_aborts_before_delete_when_status_is_multiline(self):
        """Catches ambiguous binary-log status being accepted as a replay boundary."""
        root, docker_log, _make_log, environment = self.controlled_root(
            "binlog.000002\t420\t\t\t\\nbinlog.000002\t421\t\t\t"
        )

        result = subprocess.run(
            ["bash", "scenarios/pitr.sh"], cwd=root, env=environment,
            text=True, capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        calls = docker_log.read_text(encoding="utf-8")
        self.assertNotIn("DELETE FROM ha_lab.orders", calls)
        self.assertNotIn("--profile recovery up -d recovery", calls)

    def test_pitr_aborts_before_delete_when_binlog_file_changes(self):
        """Catches a replay window silently crossing binary-log files."""
        root, docker_log, _make_log, environment = self.controlled_root(
            "binlog.000003\t420\t\t\t"
        )

        result = subprocess.run(
            ["bash", "scenarios/pitr.sh"], cwd=root, env=environment,
            text=True, capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        calls = docker_log.read_text(encoding="utf-8")
        self.assertNotIn("DELETE FROM ha_lab.orders", calls)
        self.assertNotIn("--profile recovery up -d recovery", calls)


if __name__ == "__main__":
    unittest.main()
