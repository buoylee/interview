import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FaultScriptTest(unittest.TestCase):
    def controlled_root(self, secondaries=""):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name) / "ha"
        (root / "evidence").mkdir(parents=True)
        shutil.copytree(ROOT / "faults", root / "faults")
        (root / "compose.yml").write_text("name: mysql-ha\n", encoding="utf-8")
        bin_dir = root / "bin"
        bin_dir.mkdir()
        log = root / "docker.log"
        fake_docker = bin_dir / "docker"
        fake_docker.write_text(
            "#!/usr/bin/env bash\n"
            "set -eu\n"
            "printf '%s\\n' \"$*\" >> \"$FAKE_DOCKER_LOG\"\n"
            "case \"$*\" in\n"
            "  *\"MEMBER_ROLE='PRIMARY'\"*) printf 'db1\\n' ;;\n"
            "  *\"MEMBER_ROLE='SECONDARY'\"*) [ -z \"${FAKE_SECONDARIES:-}\" ] || printf '%s\\n' \"$FAKE_SECONDARIES\" ;;\n"
            "  *\"COUNT(*) FROM performance_schema.replication_group_members\"*) printf '3\\n' ;;\n"
            "  *\"network connect\"*) [ \"${FAKE_FAIL_NETWORK_CONNECT:-0}\" = 0 ] || exit 1 ;;\n"
            "  *inspect*) printf 'mysql-ha\\n' ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        fake_docker.chmod(0o755)
        environment = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "FAKE_DOCKER_LOG": str(log),
            "FAKE_SECONDARIES": secondaries,
        }
        return temporary, root, log, environment

    def test_faults_are_scoped_to_project_and_network(self):
        text = (ROOT / "faults/lib.sh").read_text(encoding="utf-8")
        self.assertIn("--project-name mysql-ha", text)
        self.assertIn("mysql-ha-net", text)

    def test_injector_has_all_first_seven_fault_modes(self):
        text = (ROOT / "faults/inject.sh").read_text(encoding="utf-8")
        for name in (
            "planned-switchover", "primary-crash", "primary-partition",
            "quorum-loss", "slow-member", "router-failure", "member-rejoin",
        ):
            self.assertIn(f"{name})", text)

    def test_fault_scripts_do_not_use_host_wide_cleanup(self):
        text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "faults").glob("*.sh"))
        for forbidden in ("docker system prune", "docker network prune", "pkill", "killall"):
            self.assertNotIn(forbidden, text)

    def test_recovery_state_precedes_reversible_partition_mutation(self):
        text = (ROOT / "faults/inject.sh").read_text(encoding="utf-8")
        self.assertIn(
            'write_state\n    docker network disconnect --force "$NETWORK" "mysql-ha-$target"',
            text,
        )

    def test_bootstrap_waits_for_all_members_before_routers(self):
        text = (ROOT / "Makefile").read_text(encoding="utf-8")
        bootstrap = text.split("bootstrap: up-db\n", 1)[1].split("\nrouters: bootstrap", 1)[0]
        bootstrap_command = "$(DC) run --rm cluster-bootstrap"
        readiness_command = "source ./faults/lib.sh; wait_for_online 3"
        self.assertIn(readiness_command, bootstrap)
        self.assertLess(bootstrap.index(bootstrap_command), bootstrap.index(readiness_command))

    def test_tampered_state_is_not_executed_or_mutated(self):
        temporary, root, log, environment = self.controlled_root()
        self.addCleanup(temporary.cleanup)
        marker = root / "executed"
        (root / "evidence/fault-state.env").write_text(
            "SCENARIO=router-failure\n"
            f"TARGET=$(touch {marker})\n"
            "TARGETS=\n"
            "OLD_FLOW_THRESHOLDS=\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            ["bash", "faults/restore.sh"], cwd=root, env=environment,
            text=True, capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists(), result.stderr)
        self.assertFalse(log.exists() and log.read_text(encoding="utf-8"))

    def test_quorum_loss_rejects_less_than_two_secondaries_without_event_or_stop(self):
        for secondaries in ("", "db2"):
            with self.subTest(secondaries=secondaries):
                temporary, root, log, environment = self.controlled_root(secondaries)
                self.addCleanup(temporary.cleanup)
                result = subprocess.run(
                    ["bash", "faults/inject.sh", "quorum-loss"], cwd=root,
                    env=environment, text=True, capture_output=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((root / "evidence/events.jsonl").exists())
                calls = log.read_text(encoding="utf-8") if log.exists() else ""
                self.assertNotIn(" stop ", calls)

    def test_state_and_restore_contracts_are_strict(self):
        lib = (ROOT / "faults/lib.sh").read_text(encoding="utf-8")
        inject = (ROOT / "faults/inject.sh").read_text(encoding="utf-8")
        restore = (ROOT / "faults/restore.sh").read_text(encoding="utf-8")
        self.assertIn("parse_fault_state", lib)
        self.assertNotIn('source "$STATE"', restore)
        self.assertIn("mapfile -t quorum_targets", inject)
        self.assertIn('"${quorum_targets[@]}"', inject)
        self.assertIn("OLD_FLOW_THRESHOLDS", inject)
        self.assertIn("--restart=always", restore)
        self.assertIn("network_connected", restore)
        self.assertIn("wait_for_router", restore)

    def test_parser_rejects_duplicate_missing_and_unknown_state_keys_without_docker(self):
        invalid_states = (
            "SCENARIO=router-failure\nTARGET=router-a\nTARGET=router-a\nTARGETS=\nOLD_FLOW_THRESHOLDS=\n",
            "SCENARIO=router-failure\nTARGET=router-a\nTARGETS=\n",
            "SCENARIO=router-failure\nTARGET=router-a\nTARGETS=\nOLD_FLOW_THRESHOLDS=\nEXTRA=value\n",
        )
        for state in invalid_states:
            with self.subTest(state=state):
                temporary, root, log, environment = self.controlled_root()
                self.addCleanup(temporary.cleanup)
                (root / "evidence/fault-state.env").write_text(state, encoding="utf-8")
                result = subprocess.run(
                    ["bash", "faults/restore.sh"], cwd=root, env=environment,
                    text=True, capture_output=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(log.exists() and log.read_text(encoding="utf-8"))

    def test_slow_restore_uses_each_saved_threshold(self):
        temporary, root, log, environment = self.controlled_root()
        self.addCleanup(temporary.cleanup)
        (root / "evidence/fault-state.env").write_text(
            "SCENARIO=slow-member\nTARGET=db3\nTARGETS=\n"
            "OLD_FLOW_THRESHOLDS=db1:11,db2:22,db3:33\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            ["bash", "faults/restore.sh"], cwd=root, env=environment,
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = log.read_text(encoding="utf-8")
        for threshold in (11, 22, 33):
            self.assertIn(f"group_replication_flow_control_applier_threshold={threshold}", calls)

    def test_router_restore_waits_for_acceptance_before_fault_end(self):
        temporary, root, log, environment = self.controlled_root()
        self.addCleanup(temporary.cleanup)
        (root / "evidence/fault-state.env").write_text(
            "SCENARIO=router-failure\nTARGET=router-a\nTARGETS=\nOLD_FLOW_THRESHOLDS=\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            ["bash", "faults/restore.sh"], cwd=root, env=environment,
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = log.read_text(encoding="utf-8")
        self.assertLess(calls.index("up -d router-a"), calls.index("mysqladmin ping -hrouter-a"))
        events = (root / "evidence/events.jsonl").read_text(encoding="utf-8")
        self.assertIn('"phase":"fault_end"', events)

    def test_partition_restore_propagates_network_connect_failure(self):
        temporary, root, log, environment = self.controlled_root()
        self.addCleanup(temporary.cleanup)
        environment["FAKE_FAIL_NETWORK_CONNECT"] = "1"
        (root / "evidence/fault-state.env").write_text(
            "SCENARIO=primary-partition\nTARGET=db1\nTARGETS=\nOLD_FLOW_THRESHOLDS=\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            ["bash", "faults/restore.sh"], cwd=root, env=environment,
            text=True, capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        calls = log.read_text(encoding="utf-8")
        self.assertIn("network connect", calls)
        self.assertNotIn("rejoin_begin", (root / "evidence/events.jsonl").read_text(encoding="utf-8") if (root / "evidence/events.jsonl").exists() else "")


if __name__ == "__main__":
    unittest.main()
