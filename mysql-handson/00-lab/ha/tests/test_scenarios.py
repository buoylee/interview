import unittest

from verifier.scenarios import assert_scenario
from workload.model import LedgerRecord, Outcome


def result(router, at, outcome):
    return LedgerRecord(
        f"{router}-{at}", "{}", router, at, at, outcome, 0, None,
    )


class ScenarioAssertionTest(unittest.TestCase):
    def test_every_scenario_requires_one_ordered_fault_lifecycle(self):
        """Catches evidence that omits, duplicates, or reverses fault events."""
        scenarios = (
            "planned-switchover", "primary-crash", "primary-partition",
            "quorum-loss", "slow-member", "router-failure", "member-rejoin",
        )
        for scenario in scenarios:
            with self.subTest(scenario=scenario, defect="missing begin"):
                report = assert_scenario(
                    scenario,
                    [],
                    [
                        {"phase": "fault_active", "at": "2026-01-01T00:00:01+00:00"},
                        {"phase": "quorum_restore_begin", "at": "2026-01-01T00:00:02+00:00"},
                        {"phase": "fault_end", "at": "2026-01-01T00:00:03+00:00"},
                    ],
                )
                self.assertIn("expected exactly one fault_begin event", report["errors"])
            with self.subTest(scenario=scenario, defect="duplicate active"):
                report = assert_scenario(
                    scenario,
                    [],
                    [
                        {"phase": "fault_begin", "at": "2026-01-01T00:00:00+00:00"},
                        {"phase": "fault_active", "at": "2026-01-01T00:00:01+00:00"},
                        {"phase": "fault_active", "at": "2026-01-01T00:00:01.500000+00:00"},
                        {"phase": "quorum_restore_begin", "at": "2026-01-01T00:00:02+00:00"},
                        {"phase": "fault_end", "at": "2026-01-01T00:00:03+00:00"},
                    ],
                )
                self.assertIn("expected exactly one fault_active event", report["errors"])
            with self.subTest(scenario=scenario, defect="out of order"):
                report = assert_scenario(
                    scenario,
                    [],
                    [
                        {"phase": "fault_active", "at": "2026-01-01T00:00:00+00:00"},
                        {"phase": "fault_begin", "at": "2026-01-01T00:00:01+00:00"},
                        {"phase": "quorum_restore_begin", "at": "2026-01-01T00:00:02+00:00"},
                        {"phase": "fault_end", "at": "2026-01-01T00:00:03+00:00"},
                    ],
                )
                self.assertIn("scenario lifecycle events are out of order", report["errors"])

    def test_slow_member_uses_only_the_fault_target_metrics(self):
        """Catches another member's backlog being credited to the slowed member."""
        events = [
            {"phase": "fault_begin", "at": "2026-01-01T00:00:00+00:00", "target": "db3"},
            {"phase": "fault_active", "at": "2026-01-01T00:00:01+00:00", "target": "db3"},
            {"phase": "fault_end", "at": "2026-01-01T00:00:03+00:00", "target": "db3"},
        ]
        metrics = [
            {"phase": "before", "members": {
                "db2": {"applier_queue": 0, "flow_control_applier_threshold": 10, "flow_control_mode": "QUOTA"},
                "db3": {"applier_queue": 0, "flow_control_applier_threshold": 10, "flow_control_mode": "QUOTA"},
            }},
            {"phase": "active", "members": {
                "db2": {"applier_queue": 12, "flow_control_applier_threshold": 10, "flow_control_mode": "QUOTA"},
                "db3": {"applier_queue": 0, "flow_control_applier_threshold": 10, "flow_control_mode": "QUOTA"},
            }},
        ]
        report = assert_scenario("slow-member", [], events, metrics)
        self.assertIn("slow member did not grow the applier queue", report["errors"])
        self.assertIn("applier queue did not cross the active flow-control threshold", report["errors"])

    def test_slow_member_fails_closed_when_target_metrics_are_missing(self):
        """Catches an incomplete collector that has no snapshots for the slowed DB."""
        events = [
            {"phase": "fault_begin", "at": "2026-01-01T00:00:00+00:00", "target": "db3"},
            {"phase": "fault_active", "at": "2026-01-01T00:00:01+00:00", "target": "db3"},
            {"phase": "fault_end", "at": "2026-01-01T00:00:03+00:00", "target": "db3"},
        ]
        metrics = [
            {"phase": "before", "members": {"db2": {
                "applier_queue": 0,
                "flow_control_applier_threshold": 10,
                "flow_control_mode": "QUOTA",
            }}},
            {"phase": "active", "members": {"db2": {
                "applier_queue": 12,
                "flow_control_applier_threshold": 10,
                "flow_control_mode": "QUOTA",
            }}},
        ]
        report = assert_scenario("slow-member", [], events, metrics)
        self.assertIn("slow-member target metrics are missing", report["errors"])

    def test_slow_member_fails_closed_for_non_string_fault_targets(self):
        """Catches malformed JSON target values escaping the scenario report."""
        metrics = [
            {"phase": "before", "members": {"db3": {
                "applier_queue": 0,
                "flow_control_applier_threshold": 10,
                "flow_control_mode": "QUOTA",
            }}},
            {"phase": "active", "members": {"db3": {
                "applier_queue": 12,
                "flow_control_applier_threshold": 10,
                "flow_control_mode": "QUOTA",
            }}},
        ]
        for target in ([], {}, 3):
            with self.subTest(target=target):
                events = [
                    {"phase": "fault_begin", "at": "2026-01-01T00:00:00+00:00"},
                    {"phase": "fault_active", "at": "2026-01-01T00:00:01+00:00", "target": target},
                    {"phase": "fault_end", "at": "2026-01-01T00:00:03+00:00"},
                ]
                report = assert_scenario("slow-member", [], events, metrics)
                self.assertFalse(report["ok"])
                self.assertIn(
                    "slow-member fault target is missing or invalid", report["errors"]
                )

    def test_quorum_loss_allows_no_success_in_active_window(self):
        records = [
            result("router-a", "2026-01-01T00:00:02+00:00", Outcome.SUCCESS),
            result("router-a", "2026-01-01T00:00:05+00:00", Outcome.SUCCESS),
        ]
        events = [
            {"phase": "fault_begin", "at": "2026-01-01T00:00:00+00:00"},
            {"phase": "fault_active", "at": "2026-01-01T00:00:01+00:00"},
            {"phase": "quorum_restore_begin", "at": "2026-01-01T00:00:03+00:00"},
            {"phase": "fault_end", "at": "2026-01-01T00:00:04+00:00"},
        ]
        report = assert_scenario("quorum-loss", records, events)
        self.assertIn("write succeeded without quorum", report["errors"])

    def test_router_failure_requires_router_b_success(self):
        records = [result("router-b", "2026-01-01T00:00:02+00:00", Outcome.SUCCESS)]
        events = [
            {"phase": "fault_begin", "at": "2026-01-01T00:00:00+00:00"},
            {"phase": "fault_active", "at": "2026-01-01T00:00:01+00:00"},
            {"phase": "fault_end", "at": "2026-01-01T00:00:03+00:00"},
        ]
        self.assertEqual(assert_scenario("router-failure", records, events)["errors"], [])

    def test_slow_member_requires_queue_and_flow_control_growth(self):
        events = [
            {"phase": "fault_begin", "at": "2026-01-01T00:00:00+00:00", "target": "db3"},
            {"phase": "fault_active", "at": "2026-01-01T00:00:01+00:00", "target": "db3"},
            {"phase": "fault_end", "at": "2026-01-01T00:00:03+00:00"},
        ]
        metrics = [
            {"phase": "before", "members": {"db3": {
                "applier_queue": 0,
                "flow_control_applier_threshold": 10,
                "flow_control_mode": "QUOTA",
            }}},
            {"phase": "active", "members": {"db3": {
                "applier_queue": 12,
                "flow_control_applier_threshold": 10,
                "flow_control_mode": "QUOTA",
            }}},
        ]
        report = assert_scenario("slow-member", [], events, metrics)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["metrics"]["flow_control_triggered"])

    def test_primary_crash_reports_segmented_rto(self):
        records = [result("router-a", "2026-01-01T00:00:04+00:00", Outcome.SUCCESS)]
        events = [
            {"phase": "fault_begin", "at": "2026-01-01T00:00:00+00:00"},
            {"phase": "fault_active", "at": "2026-01-01T00:00:00.100000+00:00"},
            {"phase": "fault_end", "at": "2026-01-01T00:00:05+00:00"},
        ]
        timeline = [
            {"phase": "failure_detected", "at": "2026-01-01T00:00:01+00:00"},
            {"phase": "primary_elected", "at": "2026-01-01T00:00:02+00:00"},
            {"phase": "primary_writable", "at": "2026-01-01T00:00:02.500000+00:00"},
            {"phase": "router_ready", "at": "2026-01-01T00:00:03+00:00"},
        ]
        report = assert_scenario("primary-crash", records, events, timeline=timeline)
        self.assertEqual(
            report["rto_segments_ms"],
            {"detection": 1000, "election": 1000, "backlog_fence": 500,
             "router_refresh": 500,
             "application_reconnect": 1000, "total": 4000},
        )

    def test_primary_partition_requires_fencing_evidence(self):
        records = [result("router-a", "2026-01-01T00:00:04+00:00", Outcome.SUCCESS)]
        events = [
            {"phase": "fault_begin", "at": "2026-01-01T00:00:00+00:00"},
            {"phase": "fault_active", "at": "2026-01-01T00:00:01+00:00"},
            {"phase": "fault_end", "at": "2026-01-01T00:00:05+00:00"},
        ]
        timeline = [
            {"phase": "failure_detected", "at": "2026-01-01T00:00:01+00:00"},
            {"phase": "primary_elected", "at": "2026-01-01T00:00:02+00:00"},
            {"phase": "primary_writable", "at": "2026-01-01T00:00:02.500000+00:00"},
            {"phase": "router_ready", "at": "2026-01-01T00:00:03+00:00"},
        ]
        fencing = {"offline_mode": 1, "super_read_only": 1, "write_rejected": True}
        session = {
            "old_backend": "db1",
            "existing_session_disconnected": True,
            "new_backend": "db2",
        }
        self.assertEqual(
            assert_scenario(
                "primary-partition", records, events,
                timeline=timeline, fencing=fencing, session=session,
            )["errors"],
            [],
        )

    def test_member_rejoin_requires_explicit_recovery_events(self):
        events = [
            {"phase": "fault_begin", "at": "2026-01-01T00:00:00+00:00"},
            {"phase": "fault_active", "at": "2026-01-01T00:00:01+00:00"},
            {"phase": "rejoin_begin", "at": "2026-01-01T00:00:02+00:00"},
            {"phase": "rejoin_online", "at": "2026-01-01T00:00:03+00:00"},
            {"phase": "fault_end", "at": "2026-01-01T00:00:04+00:00"},
        ]
        self.assertEqual(assert_scenario("member-rejoin", [], events)["errors"], [])

    def test_failover_requires_old_session_disconnect_and_new_backend(self):
        records = [result("router-a", "2026-01-01T00:00:04+00:00", Outcome.SUCCESS)]
        events = [
            {"phase": "fault_begin", "at": "2026-01-01T00:00:00+00:00"},
            {"phase": "fault_active", "at": "2026-01-01T00:00:01+00:00"},
            {"phase": "fault_end", "at": "2026-01-01T00:00:05+00:00"},
        ]
        timeline = [
            {"phase": "failure_detected", "at": "2026-01-01T00:00:01+00:00"},
            {"phase": "primary_elected", "at": "2026-01-01T00:00:02+00:00"},
            {"phase": "primary_writable", "at": "2026-01-01T00:00:02.500000+00:00"},
            {"phase": "router_ready", "at": "2026-01-01T00:00:03+00:00"},
        ]
        session = {
            "old_backend": "db1",
            "existing_session_disconnected": True,
            "new_backend": "db2",
        }
        self.assertEqual(
            assert_scenario(
                "primary-crash", records, events, timeline=timeline, session=session,
            )["errors"],
            [],
        )


if __name__ == "__main__":
    unittest.main()
