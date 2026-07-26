import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CompleteOutageRecoveryTest(unittest.TestCase):
    def run_reboot(self, environment):
        script = ROOT / "bootstrap/reboot.js"
        self.assertTrue(script.exists(), "complete-outage reboot primitive is missing")
        runner = """
const fs = require('fs');
const vm = require('vm');
const environment = JSON.parse(process.argv[1]);
const result = {connect: [], reboot: [], status: [], printed: []};
const cluster = {status: (options) => { result.status.push(options); return {defaultReplicaSet: {status: 'OK'}}; }};
const sandbox = {
  shell: {options: {}, connect: (options) => result.connect.push(options)},
  os: {getenv: (name) => environment[name]},
  dba: {rebootClusterFromCompleteOutage: (name, options) => { result.reboot.push({name, options}); return cluster; }},
  print: (value) => result.printed.push(value),
  JSON,
};
vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), sandbox, {filename: process.argv[2]});
process.stdout.write(JSON.stringify(result));
"""
        completed = subprocess.run(
            ["node", "-e", runner, json.dumps(environment), str(script)],
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(completed.stdout)

    @unittest.skipUnless(shutil.which("node"), "requires a JavaScript runtime")
    def test_reboot_defaults_to_dry_run_and_actual_requires_explicit_opt_in(self):
        """Catches a reboot primitive that mutates a complete outage by default."""
        default = self.run_reboot({})
        actual = self.run_reboot({"MYSQL_REBOOT_DRY_RUN": "0", "MYSQL_SEED": "db2"})

        self.assertEqual(default["connect"], [{"scheme": "mysql", "user": "icadmin", "password": "ha-cluster", "host": "db1", "port": 3306}])
        self.assertEqual(default["reboot"], [{"name": "haLabCluster", "options": {"dryRun": True}}])
        self.assertEqual(default["status"], [])
        self.assertEqual(len(default["printed"]), 1)
        self.assertEqual(
            json.loads(default["printed"][0]),
            {"dryRun": True, "cluster": "haLabCluster", "seed": "db1", "ok": True},
        )
        self.assertEqual(actual["connect"][0]["host"], "db2")
        self.assertEqual(actual["reboot"], [{"name": "haLabCluster", "options": {"dryRun": False}}])
        self.assertEqual(actual["status"], [{"extended": 2}])
        self.assertEqual(len(actual["printed"]), 1)

    @unittest.skipUnless(shutil.which("node"), "requires a JavaScript runtime")
    def test_reboot_never_enables_force(self):
        """Catches a recovery primitive that force-selects an unsafe seed."""
        for environment in ({}, {"MYSQL_REBOOT_DRY_RUN": "0"}):
            with self.subTest(environment=environment):
                result = self.run_reboot(environment)
                self.assertEqual(set(result["reboot"][0]["options"]), {"dryRun"})

    def controlled_root(self, final_verify_fails=False):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name) / "ha"
        (root / "scenarios").mkdir(parents=True)
        (root / "evidence").mkdir()
        source = ROOT / "scenarios/complete-outage.sh"
        self.assertTrue(source.exists(), "complete-outage orchestration is missing")
        shutil.copy2(source, root / "scenarios/complete-outage.sh")
        (root / "compose.yml").write_text("name: mysql-ha\n", encoding="utf-8")
        bin_dir = root / "bin"
        bin_dir.mkdir()
        docker_log = root / "docker.log"
        make_log = root / "make.log"
        fake_docker = bin_dir / "docker"
        fake_docker.write_text(
            "#!/usr/bin/env bash\n"
            "set -eu\n"
            "printf '%s\\n' \"$*\" >> \"$FAKE_DOCKER_LOG\"\n"
            "case \"$*\" in\n"
            "  *\"SET PERSIST_ONLY group_replication_start_on_boot = OFF\"*) printf 'OFF' > \"$FAKE_START_ON_BOOT\" ;;\n"
            "  *\"SET PERSIST_ONLY group_replication_start_on_boot = ON\"*) printf 'ON' > \"$FAKE_START_ON_BOOT\" ;;\n"
            "  *\"SELECT VARIABLE_VALUE FROM performance_schema.persisted_variables\"*) cat \"$FAKE_START_ON_BOOT\" ;;\n"
            "  *\"MEMBER_ROLE='PRIMARY'\"*) printf 'db1\\n' ;;\n"
            "  *\"SELECT @@GLOBAL.gtid_executed\"*) printf 'uuid:1-20\\n' ;;\n"
            "  *\"WAIT_FOR_EXECUTED_GTID_SET\"*) printf '0\\n' ;;\n"
            "  *\"SELECT request_id FROM ha_lab.orders\"*) printf 'request-1\\nrequest-2\\n' ;;\n"
            "  *\"COUNT(*) FROM performance_schema.replication_group_members\"*) printf '3\\n' ;;\n"
            "  *\"MYSQL_REBOOT_DRY_RUN=1\"*\"mysqlsh --js --file=/bootstrap/reboot.js\"*) printf '{\\\"dryRun\\\":true,\\\"cluster\\\":\\\"haLabCluster\\\",\\\"seed\\\":\\\"db1\\\",\\\"ok\\\":true}\\n' ;;\n"
            "  *\"MYSQL_REBOOT_DRY_RUN=0\"*\"mysqlsh --js --file=/bootstrap/reboot.js\"*) printf '{\\\"status\\\":\\\"OK\\\"}\\n' ;;\n"
            "  *\"mysqlsh --js --file=/bootstrap/status.js\"*) printf '{\\\"online\\\":3,\\\"primary\\\":1}\\n' ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        fake_docker.chmod(0o755)
        (root / "start-on-boot").write_text("ON", encoding="utf-8")
        fake_make = bin_dir / "make"
        fake_make.write_text(
            "#!/usr/bin/env bash\n"
            "set -eu\n"
            "printf '%s\\n' \"$*\" >> \"$FAKE_MAKE_LOG\"\n"
            "case \"$*\" in\n"
            "  *' verify'*)\n"
            "    count=0; [ ! -f \"$FAKE_VERIFY_COUNT\" ] || count=\"$(cat \"$FAKE_VERIFY_COUNT\")\"\n"
            "    count=$((count + 1)); printf '%s' \"$count\" > \"$FAKE_VERIFY_COUNT\"\n"
            "    if [ \"$FAKE_FINAL_VERIFY_FAIL\" = 1 ] && [ \"$count\" -gt 1 ]; then exit 17; fi\n"
            "    ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        fake_make.chmod(0o755)
        environment = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "FAKE_DOCKER_LOG": str(docker_log),
            "FAKE_MAKE_LOG": str(make_log),
            "FAKE_VERIFY_COUNT": str(root / "verify-count"),
            "FAKE_FINAL_VERIFY_FAIL": "1" if final_verify_fails else "0",
            "FAKE_START_ON_BOOT": str(root / "start-on-boot"),
        }
        return temporary, root, docker_log, make_log, environment

    def test_complete_outage_orders_safe_recovery_gates_and_preserves_ids(self):
        """Catches outage recovery that skips Router/GTID/dry-run/data-integrity gates."""
        temporary, root, docker_log, make_log, environment = self.controlled_root()
        self.addCleanup(temporary.cleanup)

        result = subprocess.run(
            ["bash", "scenarios/complete-outage.sh"], cwd=root, env=environment,
            text=True, capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = docker_log.read_text(encoding="utf-8")
        self.assertIn("stop router-a router-b", calls)
        self.assertIn("stop db1 db2 db3", calls)
        self.assertIn("up -d db1 db2 db3", calls)
        self.assertIn("up -d router-a router-b", calls)
        self.assertEqual(calls.count("WAIT_FOR_EXECUTED_GTID_SET"), 3)
        self.assertLess(calls.index("stop router-a router-b"), calls.index("WAIT_FOR_EXECUTED_GTID_SET"))
        self.assertLess(calls.index("WAIT_FOR_EXECUTED_GTID_SET"), calls.index("stop db1 db2 db3"))
        self.assertEqual(calls.count("SET PERSIST_ONLY group_replication_start_on_boot = OFF"), 3)
        self.assertEqual(calls.count("SET PERSIST_ONLY group_replication_start_on_boot = ON"), 3)
        self.assertLess(
            calls.rindex("SET PERSIST_ONLY group_replication_start_on_boot = OFF"),
            calls.index("stop db1 db2 db3"),
        )
        self.assertLess(calls.index("MYSQL_REBOOT_DRY_RUN=1"), calls.index("MYSQL_REBOOT_DRY_RUN=0"))
        self.assertLess(calls.index("up -d db1 db2 db3"), calls.index("MYSQL_REBOOT_DRY_RUN=1"))
        self.assertIn("COUNT(*) FROM performance_schema.replication_group_members", calls)
        self.assertEqual(
            (root / "evidence/complete-outage/before-ids.txt").read_bytes(),
            (root / "evidence/complete-outage/after-ids.txt").read_bytes(),
        )
        self.assertEqual(
            [json.loads(line)["phase"] for line in (root / "evidence/complete-outage/events.jsonl").read_text().splitlines()],
            ["outage_begin", "dry_run_begin", "actual_reboot_begin", "recovery_verified"],
        )
        self.assertEqual(
            [json.loads(line) for line in (root / "evidence/complete-outage/start-on-boot-before.jsonl").read_text().splitlines()],
            [
                {"member": "db1", "persistedStartOnBoot": "ON"},
                {"member": "db2", "persistedStartOnBoot": "ON"},
                {"member": "db3", "persistedStartOnBoot": "ON"},
            ],
        )
        self.assertEqual(
            [json.loads(line) for line in (root / "evidence/complete-outage/start-on-boot-after.jsonl").read_text().splitlines()],
            [
                {"member": "db1", "persistedStartOnBoot": "ON"},
                {"member": "db2", "persistedStartOnBoot": "ON"},
                {"member": "db3", "persistedStartOnBoot": "ON"},
            ],
        )
        self.assertLess(
            calls.rindex("SET PERSIST_ONLY group_replication_start_on_boot = ON"),
            calls.rindex("mysqlsh --js --file=/bootstrap/status.js"),
        )
        self.assertIn("-C", make_log.read_text(encoding="utf-8"))
        self.assertEqual((root / "evidence/complete-outage/seed.txt").read_text(), "db1\n")
        self.assertIn('"primary":1', (root / "evidence/complete-outage/final-status.json").read_text())

    def test_complete_outage_does_not_publish_success_when_final_verifier_fails(self):
        """Catches a success event written before final topology and data gates complete."""
        temporary, root, _docker_log, _make_log, environment = self.controlled_root(final_verify_fails=True)
        self.addCleanup(temporary.cleanup)

        result = subprocess.run(
            ["bash", "scenarios/complete-outage.sh"], cwd=root, env=environment,
            text=True, capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        phases = [json.loads(line)["phase"] for line in (root / "evidence/complete-outage/events.jsonl").read_text().splitlines()]
        self.assertNotIn("recovery_verified", phases)


if __name__ == "__main__":
    unittest.main()
