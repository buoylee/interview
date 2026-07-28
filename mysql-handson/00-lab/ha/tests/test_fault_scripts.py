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
            "  *\"exec -T db1\"*\"MEMBER_ROLE='PRIMARY'\"*) [ \"${FAKE_EMPTY_DB1_PRIMARY:-0}\" = 1 ] || printf 'db1\\n' ;;\n"
            "  *\"exec -T db2\"*\"MEMBER_ROLE='PRIMARY'\"*) [ -z \"${FAKE_PRIMARY_DB2:-}\" ] || printf '%s\\n' \"$FAKE_PRIMARY_DB2\" ;;\n"
            "  *\"exec -T db1\"*\"MEMBER_ROLE='SECONDARY'\"*) [ \"${FAKE_EMPTY_DB1_SECONDARY:-0}\" = 1 ] || { [ -z \"${FAKE_SECONDARIES:-}\" ] || printf '%s\\n' \"$FAKE_SECONDARIES\"; } ;;\n"
            "  *\"exec -T db2\"*\"MEMBER_ROLE='SECONDARY'\"*) [ -z \"${FAKE_SECONDARIES_DB2:-}\" ] || printf '%s\\n' \"$FAKE_SECONDARIES_DB2\" ;;\n"
            "  *\"HEX(@@GLOBAL.gtid_executed)\"*)\n"
            "    member=unknown\n"
            "    case \"$*\" in *\"exec -T db1\"*) member=db1 ;; *\"exec -T db2\"*) member=db2 ;; *\"exec -T db3\"*) member=db3 ;; esac\n"
            "    case \"${FAKE_MALFORMED_OUTPUT:-}\" in\n"
            "      gtid-nonhex) printf 'not-hex\\n' ;;\n"
            "      gtid-odd) printf 'abc\\n' ;;\n"
            "      gtid-empty) ;;\n"
            "      *) if [ \"${FAKE_EXTRA_GTID_MEMBER:-}\" = \"$member\" ] || { [ \"${FAKE_POST_WAIT_EXTRA:-}\" = \"$member\" ] && grep -q \"exec -T $member.*WAIT_FOR_EXECUTED_GTID_SET\" \"$FAKE_DOCKER_LOG\"; }; then printf '61616161616161612d616161612d616161612d616161612d6161616161616161616161613a312d32303a3231\\n'; else printf '61616161616161612d616161612d616161612d616161612d6161616161616161616161613a312d3230\\n'; fi ;;\n"
            "    esac\n"
            "    ;;\n"
            "  *\"WAIT_FOR_EXECUTED_GTID_SET\"*)\n"
            "    wait_member=unknown\n"
            "    case \"$*\" in *\"exec -T db1\"*) wait_member=db1 ;; *\"exec -T db2\"*) wait_member=db2 ;; *\"exec -T db3\"*) wait_member=db3 ;; esac\n"
            "    if [ \"${FAKE_WAIT_MEMBER:-}\" = \"$wait_member\" ]; then case \"${FAKE_WAIT_MODE:-value}\" in value) printf '1\\n' ;; malformed) printf 'nope\\n' ;; command) exit 24 ;; esac; else printf '0\\n'; fi\n"
            "    ;;\n"
            "  *\"GTID_SUBSET\"*)\n"
            "    if [ \"${FAKE_SUBSET_MODE:-normal}\" = command ]; then exit 25; elif [ \"${FAKE_SUBSET_MODE:-normal}\" = malformed ]; then printf 'nope\\n'; else case \"$*\" in *'3231'*) printf '0\\n' ;; *) printf '1\\n' ;; esac; fi\n"
            "    ;;\n"
            "  *\"SET GLOBAL read_only=ON; SET GLOBAL super_read_only=ON; SET GLOBAL offline_mode=ON\"*)\n"
            "    fence_member=unknown\n"
            "    case \"$*\" in *\"exec -T db1\"*) fence_member=db1 ;; *\"exec -T db2\"*) fence_member=db2 ;; *\"exec -T db3\"*) fence_member=db3 ;; esac\n"
            "    [ \"${FAKE_FENCE_APPLY_FAIL:-}\" != \"$fence_member\" ] || exit 26\n"
            "    touch \"$FAKE_DB_FENCE_DIR/$fence_member\"\n"
            "    ;;\n"
            "  *\"SET GLOBAL super_read_only=OFF; SET GLOBAL read_only=OFF; SET GLOBAL offline_mode=OFF\"*) touch \"$FAKE_POST_ACCESS_DIR/db1\" ;;\n"
            "  *\"SET GLOBAL read_only=ON; SET GLOBAL super_read_only=ON; SET GLOBAL offline_mode=OFF\"*)\n"
            "    case \"$*\" in *\"exec -T db2\"*) touch \"$FAKE_POST_ACCESS_DIR/db2\" ;; *\"exec -T db3\"*) touch \"$FAKE_POST_ACCESS_DIR/db3\" ;; esac\n"
            "    ;;\n"
            "  *\"STOP GROUP_REPLICATION\"*)\n"
            "    stop_member=unknown\n"
            "    case \"$*\" in *\"exec -T db1\"*) stop_member=db1 ;; *\"exec -T db2\"*) stop_member=db2 ;; *\"exec -T db3\"*) stop_member=db3 ;; esac\n"
            "    [ \"${FAKE_STOP_GROUP_FAIL:-}\" != \"$stop_member\" ] || exit 23\n"
            "    touch \"$FAKE_GROUP_STOP_DIR/$stop_member\"\n"
            "    ;;\n"
            "  *\"SELECT COALESCE((SELECT MEMBER_STATE\"*)\n"
            "    state_member=unknown\n"
            "    case \"$*\" in *\"exec -T db1\"*) state_member=db1 ;; *\"exec -T db2\"*) state_member=db2 ;; *\"exec -T db3\"*) state_member=db3 ;; esac\n"
            "    case \"${FAKE_GROUP_STATE_MODE:-normal}\" in\n"
            "      already-offline) printf 'OFFLINE\\n' ;;\n"
            "      malformed) printf 'OFFLINE\\textra\\n' ;;\n"
            "      normal) if [ -f \"$FAKE_GROUP_STOP_DIR/$state_member\" ]; then printf 'OFFLINE\\n'; else printf 'ERROR\\n'; fi ;;\n"
            "    esac\n"
            "    ;;\n"
            "  *\"MYSQL_REBOOT_DRY_RUN=1\"*\"mysqlsh --js --file=/bootstrap/reboot.js\"*)\n"
            "    [ \"${FAKE_DRY_RUN_FAIL:-0}\" = 0 ] || { printf 'dry-run failed\\n' >&2; exit 19; }\n"
            "    case \"${FAKE_MALFORMED_OUTPUT:-}\" in dry-run) printf 'not-json\\n' ;; *) printf '{\"dryRun\":true,\"cluster\":\"haLabCluster\",\"seed\":\"db1\",\"ok\":true}\\n' ;; esac\n"
            "    ;;\n"
            "  *\"MYSQL_REBOOT_DRY_RUN=0\"*\"mysqlsh --js --file=/bootstrap/reboot.js\"*) touch \"$FAKE_REBOOTED_PATH\"; printf '{\"status\":\"OK\"}\\n' ;;\n"
            "  *\"SUM(MEMBER_ROLE = 'PRIMARY')\"*)\n"
            "    case \"${FAKE_TOPOLOGY_MODE:-ok}\" in ok) printf '3\\t1\\n' ;; no-primary) printf '3\\t0\\n' ;; two-primary) printf '3\\t2\\n' ;; malformed) printf 'three primary\\n' ;; esac\n"
            "    ;;\n"
            "  *\"MEMBER_STATE = 'ONLINE' AND MEMBER_ROLE = 'PRIMARY'\"*) printf 'db1\\n' ;;\n"
            "  *\"SELECT MEMBER_ROLE FROM performance_schema.replication_group_members WHERE MEMBER_HOST = '\"*) case \"$*\" in *\"'db1'\"*) printf 'PRIMARY\\n' ;; *) printf 'SECONDARY\\n' ;; esac ;;\n"
            "  *\"@@GLOBAL.read_only\"*)\n"
            "    access_member=unknown\n"
            "    case \"$*\" in *\"exec -T db1\"*) access_member=db1 ;; *\"exec -T db2\"*) access_member=db2 ;; *\"exec -T db3\"*) access_member=db3 ;; esac\n"
            "    if [ ! -f \"$FAKE_REBOOTED_PATH\" ]; then\n"
            "      if [ ! -f \"$FAKE_DB_FENCE_DIR/$access_member\" ] || { [ \"${FAKE_FENCE_RESET_MEMBER:-}\" = \"$access_member\" ] && [ \"$(grep -c GTID_SUBSET \"$FAKE_DOCKER_LOG\")\" -ge 6 ]; }; then printf '0\\t0\\t0\\n'; else printf '1\\t1\\t1\\n'; fi\n"
            "    else\n"
            "      case \"${FAKE_WRITABLE_MODE:-ok}:$access_member\" in ok:db1) printf '0\\t0\\t0\\n' ;; ok:db2|ok:db3) printf '1\\t1\\t0\\n' ;; read-only:db1) printf '1\\t1\\t0\\n' ;; malformed:*) printf '0\\t0\\n' ;; secondary-writable:db2) printf '0\\t0\\t0\\n' ;; *) printf '1\\t1\\t0\\n' ;; esac\n"
            "    fi\n"
            "    ;;\n"
            "  *\"WHERE request_id = 'quorum-recovery-probe-\"*)\n"
            "    case \"${FAKE_ROUTER_PROBE_MODE:-ok}\" in ok) printf '0\\n' ;; residue) printf '1\\n' ;; malformed) printf 'nope\\n' ;; esac\n"
            "    ;;\n"
            "  *\"mysqladmin ping -hrouter-a\"*) [ \"${FAKE_ROUTER_PING_FAIL:-0}\" = 0 ] ;;\n"
            "  *\"mysqladmin ping -hrouter-b\"*) [ \"${FAKE_ROUTER_PING_FAIL:-0}\" = 0 ] ;;\n"
            "  *\"SELECT MEMBER_STATE FROM performance_schema.replication_group_members WHERE MEMBER_HOST=\"*) printf 'ONLINE\\n' ;;\n"
            "  *\"COUNT(*) FROM performance_schema.replication_group_members\"*) printf '3\\n' ;;\n"
            "  *\"@@offline_mode\"*)\n"
            "    grep -q '\"phase\":\"fault_active\"' \"$FAKE_EVENTS_PATH\" || exit 10\n"
            "    count=0\n"
            "    [ ! -f \"$FAKE_FENCE_COUNT_PATH\" ] || count=\"$(sed -n '1p' \"$FAKE_FENCE_COUNT_PATH\")\"\n"
            "    count=$((count + 1))\n"
            "    printf '%s\\n' \"$count\" > \"$FAKE_FENCE_COUNT_PATH\"\n"
            "    case \"${FAKE_FENCING_MODE:-never}\" in\n"
            "      eventually)\n"
            "        if [ \"$count\" -ge 2 ]; then printf '1\\t0\\tERROR\\n'; else printf '0\\t0\\tONLINE\\n'; fi\n"
            "        ;;\n"
            "      nonzero-match) printf '1\\t0\\tERROR\\n'; exit 7 ;;\n"
            "      empty) ;;\n"
            "      malformed-two) printf '1\\t0\\n' ;;\n"
            "      malformed-four) printf '1\\t0\\tERROR\\textra\\n' ;;\n"
            "      never) printf '0\\t0\\tONLINE\\n' ;;\n"
            "    esac\n"
            "    ;;\n"
            "  *\"update --restart=no mysql-ha-db2\"*)\n"
            "    [ -f \"$FAKE_STATE_PATH\" ] && grep -q '\"phase\":\"fault_begin\"' \"$FAKE_EVENTS_PATH\" || exit 9\n"
            "    [ \"${FAKE_FAIL_RESTART_NO_MEMBER:-}\" != db2 ] || exit 11\n"
            "    ;;\n"
            "  *\"update --restart=no mysql-ha-db3\"*)\n"
            "    [ -f \"$FAKE_STATE_PATH\" ] && grep -q '\"phase\":\"fault_begin\"' \"$FAKE_EVENTS_PATH\" || exit 9\n"
            "    [ \"${FAKE_FAIL_RESTART_NO_MEMBER:-}\" != db3 ] || exit 11\n"
            "    ;;\n"
            "  *\" kill db2 db3\"*)\n"
            "    grep -q 'update --restart=no mysql-ha-db2' \"$FAKE_DOCKER_LOG\" || exit 12\n"
            "    grep -q 'update --restart=no mysql-ha-db3' \"$FAKE_DOCKER_LOG\" || exit 12\n"
            "    [ \"${FAKE_FAIL_QUORUM_KILL:-0}\" = 0 ] || exit 13\n"
            "    ;;\n"
            "  *\"network connect\"*) [ \"${FAKE_FAIL_NETWORK_CONNECT:-0}\" = 0 ] || exit 1 ;;\n"
            "  *\" stop db2 db3\"*) [ -f \"$FAKE_STATE_PATH\" ] && grep -q '\"phase\":\"fault_begin\"' \"$FAKE_EVENTS_PATH\" || exit 9 ;;\n"
            "  *\" stop router-a router-b\"*) touch \"$FAKE_ROUTER_STOP_DIR/router-a\" \"$FAKE_ROUTER_STOP_DIR/router-b\" ;;\n"
            "  *\" up -d router-a router-b\"*) touch \"$FAKE_ROUTERS_RESTARTED\" ;;\n"
            "  *\"inspect --format {{.State.Running}} mysql-ha-router-\"*) router_name=\"${*: -1}\"; router_name=\"${router_name#mysql-ha-}\"; if [ -f \"$FAKE_ROUTER_STOP_DIR/$router_name\" ]; then printf 'false\\n'; else printf 'true\\n'; fi ;;\n"
            "  *inspect*) printf 'mysql-ha\\n' ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        fake_docker.chmod(0o755)
        group_stop_dir = root / "group-stopped"
        group_stop_dir.mkdir()
        router_stop_dir = root / "routers-stopped"
        router_stop_dir.mkdir()
        db_fence_dir = root / "db-fenced"
        db_fence_dir.mkdir()
        post_access_dir = root / "post-access"
        post_access_dir.mkdir()
        environment = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "FAKE_DOCKER_LOG": str(log),
            "FAKE_SECONDARIES": secondaries,
            "FAKE_STATE_PATH": str(root / "evidence/fault-state.env"),
            "FAKE_EVENTS_PATH": str(root / "evidence/events.jsonl"),
            "FAKE_FENCE_COUNT_PATH": str(root / "fence-count"),
            "FAKE_EXTRA_GTID_MEMBER": "",
            "FAKE_POST_WAIT_EXTRA": "",
            "FAKE_WAIT_MEMBER": "",
            "FAKE_WAIT_MODE": "value",
            "FAKE_SUBSET_MODE": "normal",
            "FAKE_DRY_RUN_FAIL": "0",
            "FAKE_MALFORMED_OUTPUT": "",
            "FAKE_STOP_GROUP_FAIL": "",
            "FAKE_GROUP_STOP_DIR": str(group_stop_dir),
            "FAKE_GROUP_STATE_MODE": "normal",
            "FAKE_ROUTER_STOP_DIR": str(router_stop_dir),
            "FAKE_ROUTERS_RESTARTED": str(root / "routers-restarted"),
            "FAKE_DB_FENCE_DIR": str(db_fence_dir),
            "FAKE_POST_ACCESS_DIR": str(post_access_dir),
            "FAKE_REBOOTED_PATH": str(root / "rebooted"),
            "FAKE_FENCE_APPLY_FAIL": "",
            "FAKE_FENCE_RESET_MEMBER": "",
            "FAKE_TOPOLOGY_MODE": "ok",
            "FAKE_WRITABLE_MODE": "ok",
            "FAKE_ROUTER_PROBE_MODE": "ok",
            "FAKE_ROUTER_PING_FAIL": "0",
            "MYSQL_HA_RESTORE_TIMEOUT_SECONDS": "1",
        }
        return temporary, root, log, environment

    def call_lib_function(self, root, environment, function):
        return subprocess.run(
            ["bash", "-c", f"source '{root}/faults/lib.sh'; {function}"],
            cwd=root, env=environment, text=True, capture_output=True,
        )

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

    def test_quorum_loss_disables_restart_then_kills_explicit_secondaries_before_polling(self):
        temporary, root, log, environment = self.controlled_root("db2\ndb3")
        self.addCleanup(temporary.cleanup)
        environment["FAKE_FENCING_MODE"] = "eventually"
        environment["MYSQL_HA_QUORUM_BLOCK_TIMEOUT_SECONDS"] = "3"

        result = subprocess.run(
            ["/bin/bash", "faults/inject.sh", "quorum-loss"], cwd=root,
            env=environment, text=True, capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = log.read_text(encoding="utf-8")
        self.assertNotIn(" stop ", calls)
        self.assertIn("update --restart=no mysql-ha-db2", calls)
        self.assertIn("update --restart=no mysql-ha-db3", calls)
        kill_calls = [line for line in calls.splitlines() if " kill " in line]
        self.assertEqual(len(kill_calls), 1)
        self.assertTrue(kill_calls[0].endswith(" kill db2 db3"), kill_calls)
        fencing_calls = [line for line in calls.splitlines() if "@@offline_mode" in line]
        self.assertGreaterEqual(len(fencing_calls), 2)
        self.assertTrue(all("exec -T db1" in line for line in fencing_calls), fencing_calls)
        self.assertLess(calls.index("update --restart=no mysql-ha-db2"), calls.index("update --restart=no mysql-ha-db3"))
        self.assertLess(calls.index("update --restart=no mysql-ha-db3"), calls.index(" kill db2 db3"))
        self.assertLess(calls.index(" kill db2 db3"), calls.index("@@offline_mode"))
        state = (root / "evidence/fault-state.env").read_text(encoding="utf-8")
        self.assertIn("TARGETS=db2,db3\n", state)
        phases = [line.split('"phase":"', 1)[1].split('"', 1)[0]
                  for line in (root / "evidence/events.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(phases, ["fault_begin", "fault_active", "quorum_blocked"])
        self.assertEqual(phases.count("quorum_blocked"), 1)

    def test_quorum_loss_timeout_retains_state_without_blocked_event(self):
        temporary, root, log, environment = self.controlled_root("db2\ndb3")
        self.addCleanup(temporary.cleanup)
        environment["FAKE_FENCING_MODE"] = "never"
        environment["MYSQL_HA_QUORUM_BLOCK_TIMEOUT_SECONDS"] = "1"

        result = subprocess.run(
            ["/bin/bash", "faults/inject.sh", "quorum-loss"], cwd=root,
            env=environment, text=True, capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((root / "evidence/fault-state.env").exists())
        self.assertIn(" kill db2 db3", log.read_text(encoding="utf-8"))
        phases = [line.split('"phase":"', 1)[1].split('"', 1)[0]
                  for line in (root / "evidence/events.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(phases, ["fault_begin", "fault_active"])
        self.assertNotIn("quorum_blocked", phases)
        self.assertNotIn("fault_end", phases)

    def test_quorum_loss_restart_policy_failure_prevents_kill_and_fault_active(self):
        temporary, root, log, environment = self.controlled_root("db2\ndb3")
        self.addCleanup(temporary.cleanup)
        environment["FAKE_FAIL_RESTART_NO_MEMBER"] = "db3"
        environment["FAKE_FENCING_MODE"] = "eventually"
        environment["MYSQL_HA_QUORUM_BLOCK_TIMEOUT_SECONDS"] = "3"

        result = subprocess.run(
            ["/bin/bash", "faults/inject.sh", "quorum-loss"], cwd=root,
            env=environment, text=True, capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((root / "evidence/fault-state.env").exists())
        calls = log.read_text(encoding="utf-8")
        self.assertIn("update --restart=no mysql-ha-db2", calls)
        self.assertIn("update --restart=no mysql-ha-db3", calls)
        self.assertNotIn(" kill ", calls)
        self.assertNotIn(" stop ", calls)
        phases = [line.split('"phase":"', 1)[1].split('"', 1)[0]
                  for line in (root / "evidence/events.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(phases, ["fault_begin"])

    def test_quorum_loss_kill_failure_prevents_fault_active(self):
        temporary, root, log, environment = self.controlled_root("db2\ndb3")
        self.addCleanup(temporary.cleanup)
        environment["FAKE_FAIL_QUORUM_KILL"] = "1"
        environment["FAKE_FENCING_MODE"] = "eventually"
        environment["MYSQL_HA_QUORUM_BLOCK_TIMEOUT_SECONDS"] = "3"

        result = subprocess.run(
            ["/bin/bash", "faults/inject.sh", "quorum-loss"], cwd=root,
            env=environment, text=True, capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((root / "evidence/fault-state.env").exists())
        calls = log.read_text(encoding="utf-8")
        self.assertIn("update --restart=no mysql-ha-db2", calls)
        self.assertIn("update --restart=no mysql-ha-db3", calls)
        self.assertIn(" kill db2 db3", calls)
        self.assertNotIn(" stop ", calls)
        phases = [line.split('"phase":"', 1)[1].split('"', 1)[0]
                  for line in (root / "evidence/events.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(phases, ["fault_begin"])

    def quorum_state(self, root):
        (root / "evidence/fault-state.env").write_text(
            "SCENARIO=quorum-loss\nTARGET=db1\nTARGETS=db2,db3\nOLD_FLOW_THRESHOLDS=\n",
            encoding="utf-8",
        )

    def test_quorum_restore_uses_safe_complete_outage_reboot_and_router_probe(self):
        temporary, root, log, environment = self.controlled_root()
        self.addCleanup(temporary.cleanup)
        self.quorum_state(root)

        result = subprocess.run(
            ["/bin/bash", "faults/restore.sh"], cwd=root,
            env=environment, text=True, capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = log.read_text(encoding="utf-8")
        router_stop = "stop router-a router-b"
        self.assertIn(router_stop, calls)
        self.assertIn("inspect --format {{.State.Running}} mysql-ha-router-a", calls)
        self.assertIn("inspect --format {{.State.Running}} mysql-ha-router-b", calls)
        for member in ("db2", "db3"):
            restart = f"update --restart=always mysql-ha-{member}"
            up = f"up -d {member}"
            self.assertIn(restart, calls)
            self.assertIn(up, calls)
            self.assertLess(calls.index(restart), calls.index(up))
            self.assertLess(calls.index(router_stop), calls.index(up))
        for member in ("db1", "db2", "db3"):
            self.assertIn(f"exec -T {member} mysqladmin ping", calls)
            fence = f"exec -T {member} mysql -uroot -pha-root -e SET GLOBAL read_only=ON; SET GLOBAL super_read_only=ON; SET GLOBAL offline_mode=ON"
            self.assertIn(fence, calls)
            stop_group = f"exec -T {member} mysql -uroot -pha-root -e STOP GROUP_REPLICATION"
            self.assertIn(stop_group, calls)
            stop_index = calls.index(stop_group)
            final_subset_index = calls.rindex("GTID_SUBSET", 0, stop_index)
            final_fence_index = calls.rindex("@@GLOBAL.read_only", 0, stop_index)
            self.assertLess(final_subset_index, final_fence_index)
            self.assertLess(final_fence_index, stop_index)
            self.assertLess(stop_index, calls.index("MYSQL_REBOOT_DRY_RUN=1"))
        self.assertEqual(calls.count("WAIT_FOR_EXECUTED_GTID_SET"), 6)
        self.assertEqual(calls.count("GTID_SUBSET"), 6)
        for member in ("db1", "db2", "db3"):
            wait = f"exec -T {member} mysql -uroot -pha-root -Nse SELECT WAIT_FOR_EXECUTED_GTID_SET(CONVERT(UNHEX('61616161616161612d616161612d616161612d616161612d6161616161616161616161613a312d3230') USING utf8mb4), 30)"
            self.assertEqual(calls.count(wait), 2)
            wait_index = calls.index(wait)
            recapture = calls.index(
                f"exec -T {member} mysql -uroot -pha-root -Nse SELECT HEX(@@GLOBAL.gtid_executed)",
                wait_index,
            )
            self.assertLess(wait_index, recapture)
        self.assertEqual(
            calls.count("SELECT GTID_SUBSET(CONVERT(UNHEX('61616161616161612d616161612d616161612d616161612d6161616161616161616161613a312d3230') USING utf8mb4), CONVERT(UNHEX('61616161616161612d616161612d616161612d616161612d6161616161616161616161613a312d3230') USING utf8mb4))"),
            6,
        )
        self.assertLess(calls.index("MYSQL_REBOOT_DRY_RUN=1"), calls.index("MYSQL_REBOOT_DRY_RUN=0"))
        self.assertNotIn("force", calls.lower())
        self.assertIn("set -euo pipefail", (root / "faults/restore.sh").read_text())
        self.assertIn("SUM(MEMBER_ROLE = 'PRIMARY')", calls)
        self.assertIn("@@GLOBAL.read_only", calls)
        self.assertIn("START TRANSACTION; INSERT INTO ha_lab.orders", calls)
        self.assertIn("ROLLBACK", calls)
        router_start = "up -d router-a router-b"
        self.assertIn(router_start, calls)
        self.assertLess(calls.index("@@GLOBAL.read_only", calls.index("MYSQL_REBOOT_DRY_RUN=0")), calls.index(router_start))
        self.assertLess(calls.index(router_start), calls.index("START TRANSACTION; INSERT"))
        self.assertIn("mysqladmin ping -hrouter-a", calls)
        self.assertIn("mysqladmin ping -hrouter-b", calls)
        events = (root / "evidence/events.jsonl").read_text(encoding="utf-8")
        self.assertIn('"phase":"quorum_restore_begin"', events)
        self.assertIn('"phase":"fault_end"', events)
        self.assertNotIn('"phase":"rejoin_begin"', events)
        self.assertNotIn('"phase":"rejoin_online"', events)
        stopped = (root / "evidence/quorum-recovery-group-stopped.jsonl").read_text()
        status_path = root / "evidence/quorum-recovery-stop-status.jsonl"
        self.assertTrue(status_path.exists())
        statuses = status_path.read_text()
        for member in ("db1", "db2", "db3"):
            self.assertIn(f'"member":"{member}"', stopped)
            self.assertIn(f'"member":"{member}","exitStatus":0', statuses)
            self.assertTrue((root / f"evidence/quorum-recovery-stop-{member}.stdout.txt").exists())
            self.assertTrue((root / f"evidence/quorum-recovery-stop-{member}.stderr.txt").exists())
        self.assertTrue((root / "evidence/quorum-recovery-fence-initial.jsonl").exists())
        self.assertTrue((root / "evidence/quorum-recovery-fence-final.jsonl").exists())
        self.assertTrue((root / "evidence/quorum-recovery-gtid-initial.jsonl").exists())
        self.assertTrue((root / "evidence/quorum-recovery-gtid-final.jsonl").exists())
        self.assertFalse((root / "evidence/fault-state.env").exists())

    def test_quorum_restore_attempt_replaces_legacy_top_level_evidence(self):
        temporary, root, _log, environment = self.controlled_root()
        self.addCleanup(temporary.cleanup)
        self.quorum_state(root)
        legacy_names = (
            "quorum-recovery-gtid-before.jsonl",
            "quorum-recovery-gtid-subset.jsonl",
            "quorum-recovery-stop-db1.txt",
            "quorum-recovery-stop-db2.txt",
            "quorum-recovery-stop-db3.txt",
        )
        for name in legacy_names:
            (root / "evidence" / name).write_text("legacy-attempt\n", encoding="utf-8")

        result = subprocess.run(
            ["/bin/bash", "faults/restore.sh"], cwd=root,
            env=environment, text=True, capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        for name in legacy_names:
            self.assertFalse((root / "evidence" / name).exists(), name)
        current_names = {
            path.name for path in (root / "evidence").glob("quorum-recovery-*")
        }
        self.assertIn("quorum-recovery-gtid-initial.jsonl", current_names)
        self.assertIn("quorum-recovery-gtid-final.jsonl", current_names)
        for member in ("db1", "db2", "db3"):
            self.assertIn(f"quorum-recovery-stop-{member}.stdout.txt", current_names)
            self.assertIn(f"quorum-recovery-stop-{member}.stderr.txt", current_names)

    def test_quorum_restore_extra_member_gtid_aborts_before_reboot(self):
        temporary, root, log, environment = self.controlled_root()
        self.addCleanup(temporary.cleanup)
        self.quorum_state(root)
        environment["FAKE_EXTRA_GTID_MEMBER"] = "db3"

        result = subprocess.run(
            ["/bin/bash", "faults/restore.sh"], cwd=root, env=environment,
            text=True, capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        calls = log.read_text(encoding="utf-8")
        self.assertEqual(calls.count("GTID_SUBSET"), 3)
        self.assertNotIn("STOP GROUP_REPLICATION", calls)
        self.assertNotIn("MYSQL_REBOOT_DRY_RUN", calls)
        self.assertTrue((root / "evidence/fault-state.env").exists())
        self.assertNotIn('"phase":"fault_end"', (root / "evidence/events.jsonl").read_text())

    def test_quorum_restore_dry_run_failure_blocks_actual_reboot(self):
        temporary, root, log, environment = self.controlled_root()
        self.addCleanup(temporary.cleanup)
        self.quorum_state(root)
        environment["FAKE_DRY_RUN_FAIL"] = "1"

        result = subprocess.run(
            ["/bin/bash", "faults/restore.sh"], cwd=root, env=environment,
            text=True, capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        calls = log.read_text(encoding="utf-8")
        self.assertIn("MYSQL_REBOOT_DRY_RUN=1", calls)
        self.assertNotIn("MYSQL_REBOOT_DRY_RUN=0", calls)
        self.assertTrue((root / "evidence/fault-state.env").exists())

    def test_quorum_restore_malformed_outputs_fail_closed(self):
        for mode in (
            "gtid-nonhex", "gtid-odd", "gtid-empty", "dry-run",
        ):
            with self.subTest(mode=mode):
                temporary, root, log, environment = self.controlled_root()
                self.addCleanup(temporary.cleanup)
                self.quorum_state(root)
                environment["FAKE_MALFORMED_OUTPUT"] = mode

                result = subprocess.run(
                    ["/bin/bash", "faults/restore.sh"], cwd=root, env=environment,
                    text=True, capture_output=True,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertTrue((root / "evidence/fault-state.env").exists())
                calls = log.read_text(encoding="utf-8")
                if mode.startswith("gtid-"):
                    self.assertNotIn("STOP GROUP_REPLICATION", calls)
                    self.assertNotIn("MYSQL_REBOOT_DRY_RUN", calls)
                else:
                    self.assertNotIn("MYSQL_REBOOT_DRY_RUN=0", calls)

    def test_quorum_restore_stop_group_failure_blocks_reboot(self):
        for variable, value in (
            ("FAKE_STOP_GROUP_FAIL", "db2"),
            ("FAKE_GROUP_STATE_MODE", "malformed"),
        ):
            with self.subTest(variable=variable, value=value):
                temporary, root, log, environment = self.controlled_root()
                self.addCleanup(temporary.cleanup)
                self.quorum_state(root)
                environment[variable] = value

                result = subprocess.run(
                    ["/bin/bash", "faults/restore.sh"], cwd=root, env=environment,
                    text=True, capture_output=True,
                )

                self.assertNotEqual(result.returncode, 0)
                calls = log.read_text(encoding="utf-8")
                self.assertIn("STOP GROUP_REPLICATION", calls)
                self.assertNotIn("MYSQL_REBOOT_DRY_RUN", calls)
                self.assertTrue((root / "evidence/fault-state.env").exists())
                status_path = root / "evidence/quorum-recovery-stop-status.jsonl"
                self.assertTrue(status_path.exists())
                statuses = status_path.read_text()
                expected = 23 if variable == "FAKE_STOP_GROUP_FAIL" else 0
                self.assertIn(f'"exitStatus":{expected}', statuses)

    def test_quorum_restore_allows_stop_nonzero_only_when_member_is_exactly_offline(self):
        temporary, root, _log, environment = self.controlled_root()
        self.addCleanup(temporary.cleanup)
        self.quorum_state(root)
        environment["FAKE_STOP_GROUP_FAIL"] = "db2"
        environment["FAKE_GROUP_STATE_MODE"] = "already-offline"

        result = subprocess.run(
            ["/bin/bash", "faults/restore.sh"], cwd=root, env=environment,
            text=True, capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        evidence = (root / "evidence/quorum-recovery-group-stopped.jsonl").read_text()
        self.assertIn('"member":"db2","stopCommandStatus":23', evidence)
        status_path = root / "evidence/quorum-recovery-stop-status.jsonl"
        self.assertTrue(status_path.exists())
        statuses = status_path.read_text()
        self.assertIn('"member":"db2","exitStatus":23', statuses)
        self.assertTrue((root / "evidence/quorum-recovery-stop-db2.stdout.txt").exists())
        self.assertTrue((root / "evidence/quorum-recovery-stop-db2.stderr.txt").exists())

    def test_quorum_restore_post_wait_gtid_race_aborts_before_stop(self):
        temporary, root, log, environment = self.controlled_root()
        self.addCleanup(temporary.cleanup)
        self.quorum_state(root)
        environment["FAKE_POST_WAIT_EXTRA"] = "db3"

        result = subprocess.run(
            ["/bin/bash", "faults/restore.sh"], cwd=root, env=environment,
            text=True, capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        calls = log.read_text(encoding="utf-8")
        self.assertIn("WAIT_FOR_EXECUTED_GTID_SET", calls)
        self.assertIn("GTID_SUBSET", calls)
        self.assertNotIn("STOP GROUP_REPLICATION", calls)
        self.assertNotIn("MYSQL_REBOOT_DRY_RUN", calls)
        self.assertTrue((root / "evidence/fault-state.env").exists())

    def test_quorum_restore_wait_and_subset_failures_abort_before_stop(self):
        cases = (
            ({"FAKE_WAIT_MEMBER": "db2", "FAKE_WAIT_MODE": "value"},),
            ({"FAKE_WAIT_MEMBER": "db2", "FAKE_WAIT_MODE": "malformed"},),
            ({"FAKE_WAIT_MEMBER": "db2", "FAKE_WAIT_MODE": "command"},),
            ({"FAKE_SUBSET_MODE": "malformed"},),
            ({"FAKE_SUBSET_MODE": "command"},),
        )
        for (overrides,) in cases:
            with self.subTest(overrides=overrides):
                temporary, root, log, environment = self.controlled_root()
                self.addCleanup(temporary.cleanup)
                self.quorum_state(root)
                environment.update(overrides)

                result = subprocess.run(
                    ["/bin/bash", "faults/restore.sh"], cwd=root, env=environment,
                    text=True, capture_output=True,
                )

                self.assertNotEqual(result.returncode, 0)
                calls = log.read_text(encoding="utf-8")
                self.assertNotIn("STOP GROUP_REPLICATION", calls)
                self.assertNotIn("MYSQL_REBOOT_DRY_RUN", calls)
                self.assertTrue((root / "evidence/fault-state.env").exists())

    def test_quorum_restore_fence_reset_aborts_before_stop(self):
        temporary, root, log, environment = self.controlled_root()
        self.addCleanup(temporary.cleanup)
        self.quorum_state(root)
        environment["FAKE_FENCE_RESET_MEMBER"] = "db3"

        result = subprocess.run(
            ["/bin/bash", "faults/restore.sh"], cwd=root, env=environment,
            text=True, capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        calls = log.read_text(encoding="utf-8")
        self.assertEqual(calls.count("GTID_SUBSET"), 6)
        self.assertNotIn("STOP GROUP_REPLICATION", calls)
        self.assertNotIn("MYSQL_REBOOT_DRY_RUN", calls)
        self.assertTrue((root / "evidence/fault-state.env").exists())

    def test_quorum_restore_requires_unique_writable_primary_and_zero_router_residue(self):
        modes = (
            ("FAKE_TOPOLOGY_MODE", "two-primary"),
            ("FAKE_TOPOLOGY_MODE", "malformed"),
            ("FAKE_WRITABLE_MODE", "read-only"),
            ("FAKE_WRITABLE_MODE", "malformed"),
            ("FAKE_WRITABLE_MODE", "secondary-writable"),
            ("FAKE_ROUTER_PROBE_MODE", "residue"),
            ("FAKE_ROUTER_PROBE_MODE", "malformed"),
            ("FAKE_ROUTER_PING_FAIL", "1"),
        )
        for variable, value in modes:
            with self.subTest(variable=variable, value=value):
                temporary, root, _log, environment = self.controlled_root()
                self.addCleanup(temporary.cleanup)
                self.quorum_state(root)
                environment[variable] = value

                result = subprocess.run(
                    ["/bin/bash", "faults/restore.sh"], cwd=root, env=environment,
                    text=True, capture_output=True,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertTrue((root / "evidence/fault-state.env").exists())
                phases = (root / "evidence/events.jsonl").read_text()
                self.assertNotIn('"phase":"fault_end"', phases)

    def test_non_quorum_restore_still_uses_ordinary_rejoin_without_reboot(self):
        temporary, root, log, environment = self.controlled_root()
        self.addCleanup(temporary.cleanup)
        (root / "evidence/fault-state.env").write_text(
            "SCENARIO=primary-crash\nTARGET=db1\nTARGETS=\nOLD_FLOW_THRESHOLDS=\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            ["/bin/bash", "faults/restore.sh"], cwd=root, env=environment,
            text=True, capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = log.read_text(encoding="utf-8")
        self.assertIn("update --restart=always mysql-ha-db1", calls)
        self.assertNotIn("MYSQL_REBOOT_DRY_RUN", calls)
        self.assertIn('"phase":"rejoin_begin"', (root / "evidence/events.jsonl").read_text())

    def test_quorum_loss_rejects_invalid_timeout_before_any_side_effect(self):
        for timeout in ("", "0", "-1", "abc"):
            with self.subTest(timeout=timeout):
                temporary, root, log, environment = self.controlled_root("db2\ndb3")
                self.addCleanup(temporary.cleanup)
                environment["MYSQL_HA_QUORUM_BLOCK_TIMEOUT_SECONDS"] = timeout
                environment["FAKE_FENCING_MODE"] = "eventually"

                result = subprocess.run(
                    ["/bin/bash", "faults/inject.sh", "quorum-loss"], cwd=root,
                    env=environment, text=True, capture_output=True,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((root / "evidence/fault-state.env").exists())
                self.assertFalse((root / "evidence/events.jsonl").exists())
                calls = log.read_text(encoding="utf-8") if log.exists() else ""
                self.assertNotIn(" stop ", calls)

    def test_quorum_loss_ignores_matching_output_from_failed_fencing_query(self):
        temporary, root, _log, environment = self.controlled_root("db2\ndb3")
        self.addCleanup(temporary.cleanup)
        environment["FAKE_FENCING_MODE"] = "nonzero-match"
        environment["MYSQL_HA_QUORUM_BLOCK_TIMEOUT_SECONDS"] = "1"

        result = subprocess.run(
            ["/bin/bash", "faults/inject.sh", "quorum-loss"], cwd=root,
            env=environment, text=True, capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        phases = [line.split('"phase":"', 1)[1].split('"', 1)[0]
                  for line in (root / "evidence/events.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(phases, ["fault_begin", "fault_active"])
        self.assertTrue((root / "evidence/fault-state.env").exists())

    def test_quorum_loss_ignores_empty_or_malformed_successful_fencing_output(self):
        for mode in ("empty", "malformed-two", "malformed-four"):
            with self.subTest(mode=mode):
                temporary, root, _log, environment = self.controlled_root("db2\ndb3")
                self.addCleanup(temporary.cleanup)
                environment["FAKE_FENCING_MODE"] = mode
                environment["MYSQL_HA_QUORUM_BLOCK_TIMEOUT_SECONDS"] = "1"

                result = subprocess.run(
                    ["/bin/bash", "faults/inject.sh", "quorum-loss"], cwd=root,
                    env=environment, text=True, capture_output=True,
                )

                self.assertNotEqual(result.returncode, 0)
                phases = [line.split('"phase":"', 1)[1].split('"', 1)[0]
                          for line in (root / "evidence/events.jsonl").read_text(encoding="utf-8").splitlines()]
                self.assertEqual(phases, ["fault_begin", "fault_active"])
                self.assertTrue((root / "evidence/fault-state.env").exists())

    def test_primary_member_skips_empty_success_and_uses_next_seed(self):
        temporary, root, _log, environment = self.controlled_root()
        self.addCleanup(temporary.cleanup)
        environment["FAKE_EMPTY_DB1_PRIMARY"] = "1"
        environment["FAKE_PRIMARY_DB2"] = "db2"

        result = self.call_lib_function(root, environment, "primary_member")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "db2")

    def test_secondary_members_skips_empty_success_and_uses_next_seed(self):
        temporary, root, _log, environment = self.controlled_root()
        self.addCleanup(temporary.cleanup)
        environment["FAKE_EMPTY_DB1_SECONDARY"] = "1"
        environment["FAKE_SECONDARIES_DB2"] = "db2\ndb3"

        result = self.call_lib_function(root, environment, "secondary_members")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["db2", "db3"])

    def test_state_and_restore_contracts_are_strict(self):
        lib = (ROOT / "faults/lib.sh").read_text(encoding="utf-8")
        inject = (ROOT / "faults/inject.sh").read_text(encoding="utf-8")
        restore = (ROOT / "faults/restore.sh").read_text(encoding="utf-8")
        self.assertIn("parse_fault_state", lib)
        self.assertNotIn('source "$STATE"', restore)
        self.assertNotIn("mapfile", inject)
        self.assertIn("while IFS= read -r member", inject)
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
