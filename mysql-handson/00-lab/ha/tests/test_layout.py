from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LayoutTest(unittest.TestCase):
    def test_compose_pins_three_dynamic_role_members(self):
        text = (ROOT / "compose.yml").read_text(encoding="utf-8")
        self.assertIn("name: mysql-ha", text)
        self.assertGreaterEqual(text.count("image: mysql:8.4.10"), 1)
        for member in ("db1", "db2", "db3"):
            self.assertIn(f"  {member}:\n", text)
            self.assertNotIn(f"mysql-ha-primary-{member}", text)

    def test_common_config_pins_durability(self):
        text = (ROOT / "config/common.cnf").read_text(encoding="utf-8")
        for setting in (
            "gtid_mode=ON",
            "enforce_gtid_consistency=ON",
            "binlog_format=ROW",
            "plugin_load_add=group_replication.so",
            "innodb_flush_log_at_trx_commit=1",
            "sync_binlog=1",
            "group_replication_unreachable_majority_timeout=5",
        ):
            self.assertIn(setting, text)

    def test_init_hook_persists_super_read_only_after_account_setup(self):
        compose = (ROOT / "compose.yml").read_text(encoding="utf-8")
        hook = (ROOT / "init/01-persist-super-read-only.sql").read_text(
            encoding="utf-8"
        )
        common = (ROOT / "config/common.cnf").read_text(encoding="utf-8")
        self.assertIn("./init:/docker-entrypoint-initdb.d:ro", compose)
        self.assertIn("SET PERSIST_ONLY super_read_only=ON;", hook)
        self.assertNotIn("\nsuper_read_only=ON", common)

    def test_common_config_keeps_group_replication_stopped_until_task_two(self):
        text = (ROOT / "config/common.cnf").read_text(encoding="utf-8")
        for setting in (
            "loose-group_replication_start_on_boot=OFF",
            "loose-group_replication_consistency=BEFORE_ON_PRIMARY_FAILOVER",
            "loose-group_replication_unreachable_majority_timeout=5",
        ):
            self.assertIn(setting, text)

    def test_members_restart_after_clone_exits_cleanly(self):
        text = (ROOT / "compose.yml").read_text(encoding="utf-8")
        self.assertIn("restart: always", text)

    def test_cluster_script_pins_failover_safety(self):
        text = (ROOT / "bootstrap/cluster.js").read_text(encoding="utf-8")
        for setting in (
            "BEFORE_ON_PRIMARY_FAILOVER",
            "OFFLINE_MODE",
            "autoRejoinTries: 3",
            "expelTimeout: 5",
            "communicationStack: 'MYSQL'",
        ):
            self.assertIn(setting, text)

    def test_cluster_bootstrap_skips_members_already_in_a_cluster(self):
        text = (ROOT / "bootstrap/cluster.js").read_text(encoding="utf-8")
        self.assertIn("belongs to an InnoDB Cluster", text)
        self.assertIn("clusterAdmin option is not allowed", text)
        self.assertIn("throw error", text)

    def test_two_routers_only_expose_read_write_path(self):
        text = (ROOT / "compose.yml").read_text(encoding="utf-8")
        self.assertIn("16446:6446", text)
        self.assertIn("17446:6446", text)
        self.assertEqual(text.count("community-router:8.4.10"), 2)
        self.assertGreaterEqual(text.count("platform: linux/amd64"), 4)

    def test_mysql_shell_uses_a_separate_official_package_image(self):
        text = (ROOT / "tools/Dockerfile").read_text(encoding="utf-8")
        self.assertIn("FROM --platform=linux/amd64 oraclelinux:9-slim", text)
        self.assertIn("mysql84-community-release-el9-4.noarch.rpm", text)
        self.assertIn("ca-certificates", text)
        self.assertIn("curl --fail --location", text)
        self.assertNotIn("curl-minimal", text)
        self.assertIn("rpm -Uvh", text)
        self.assertIn("--enablerepo=mysql-8.4-lts-community", text)
        self.assertIn("--enablerepo=mysql-tools-8.4-lts-community", text)
        self.assertIn("--disablerepo=mysql-9.7-lts-community", text)
        self.assertIn("--disablerepo=mysql-tools-9.7-lts-community", text)
        self.assertIn("mysql-shell-8.4.10-1.el9", text)
        self.assertIn("mysql-community-client-8.4.10-1.el9", text)


if __name__ == "__main__":
    unittest.main()
