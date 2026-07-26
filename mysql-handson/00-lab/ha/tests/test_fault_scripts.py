from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FaultScriptTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
