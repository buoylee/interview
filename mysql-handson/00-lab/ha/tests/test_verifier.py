import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from verifier.verify import (
    evaluate,
    fetch_gtid_executed,
    fetch_ids,
    fetch_topology,
    main,
    wait_for_gtid,
)
from workload.model import LedgerRecord, Outcome


def record(request_id: str, outcome: Outcome) -> LedgerRecord:
    return LedgerRecord(
        request_id, "{}", "router-a",
        "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00.001+00:00",
        outcome, 0, None,
    )


class VerifierTest(unittest.TestCase):
    def test_missing_acknowledged_write_fails(self):
        report = evaluate(
            [record("ack-1", Outcome.SUCCESS)],
            {"db1": [], "db2": [], "db3": []},
            [{"host": "db1", "role": "PRIMARY", "state": "ONLINE"}],
            expected_online=1,
        )
        self.assertIn("acknowledged request missing: ack-1", report["errors"])

    def test_unknown_is_reconciled_as_committed_or_absent(self):
        report = evaluate(
            [record("u1", Outcome.UNKNOWN), record("u2", Outcome.UNKNOWN)],
            {"db1": ["u1"]},
            [{"host": "db1", "role": "PRIMARY", "state": "ONLINE"}],
            expected_online=1,
        )
        self.assertEqual(report["unknown"], {"committed": ["u1"], "absent": ["u2"]})

    def test_divergent_online_members_fail(self):
        report = evaluate(
            [],
            {"db1": ["a"], "db2": ["a", "b"]},
            [
                {"host": "db1", "role": "PRIMARY", "state": "ONLINE"},
                {"host": "db2", "role": "SECONDARY", "state": "ONLINE"},
            ],
            expected_online=2,
        )
        self.assertIn("online member data diverged", report["errors"])

    def test_two_primaries_fail(self):
        report = evaluate(
            [],
            {"db1": [], "db2": []},
            [
                {"host": "db1", "role": "PRIMARY", "state": "ONLINE"},
                {"host": "db2", "role": "PRIMARY", "state": "ONLINE"},
            ],
            expected_online=2,
        )
        self.assertIn("expected exactly one ONLINE PRIMARY, got 2", report["errors"])

    def test_duplicate_business_result_fails(self):
        report = evaluate(
            [],
            {"db1": ["dup", "dup"]},
            [{"host": "db1", "role": "PRIMARY", "state": "ONLINE"}],
            expected_online=1,
        )
        self.assertIn("duplicate business result detected", report["errors"])

    def test_gtid_convergence_timeout_fails(self):
        report = evaluate(
            [],
            {"db1": []},
            [{"host": "db1", "role": "PRIMARY", "state": "ONLINE"}],
            expected_online=1,
            convergence_errors=["db2 did not apply the Primary GTID set"],
        )
        self.assertIn("db2 did not apply the Primary GTID set", report["errors"])

    def test_expected_online_count_fails(self):
        report = evaluate(
            [],
            {"db1": []},
            [{"host": "db1", "role": "PRIMARY", "state": "ONLINE"}],
            expected_online=3,
        )
        self.assertIn("expected 3 ONLINE members, got 1", report["errors"])

    def test_duplicate_on_noncanonical_online_member_fails(self):
        report = evaluate(
            [],
            {"db1": ["a"], "db2": ["a", "b", "b"]},
            [
                {"host": "db1", "role": "PRIMARY", "state": "ONLINE"},
                {"host": "db2", "role": "SECONDARY", "state": "ONLINE"},
            ],
            expected_online=2,
        )
        self.assertIn("duplicate business result detected", report["errors"])

    def test_unknown_is_not_absent_when_online_snapshot_is_incomplete(self):
        report = evaluate(
            [record("u1", Outcome.UNKNOWN)],
            {"db1": []},
            [
                {"host": "db1", "role": "PRIMARY", "state": "ONLINE"},
                {"host": "db2", "role": "SECONDARY", "state": "ONLINE"},
            ],
            expected_online=2,
        )
        self.assertEqual(report["unknown"]["absent"], [])
        self.assertIn("missing member snapshot: db2", report["errors"])

    def test_unknown_is_not_absent_when_expected_online_is_degraded(self):
        report = evaluate(
            [record("u1", Outcome.UNKNOWN)],
            {"db1": []},
            [{"host": "db1", "role": "PRIMARY", "state": "ONLINE"}],
            expected_online=3,
        )
        self.assertEqual(report["unknown"]["absent"], [])
        self.assertIn("expected 3 ONLINE members, got 1", report["errors"])

    def test_topology_failure_writes_report_and_exits_nonzero(self):
        report, error = self.run_main_with(
            fetch_topology_side_effect=RuntimeError("network unavailable"),
        )
        self.assertIsInstance(error, SystemExit)
        self.assertNotEqual(error.code, 0)
        self.assertIn("topology collection failed: RuntimeError", report["errors"])

    def test_each_failed_topology_seed_is_reported_in_order(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(sys, "argv", ["verify", "--evidence-dir", directory]),
                patch(
                    "verifier.verify.connect",
                    side_effect=[RuntimeError(), RuntimeError(), RuntimeError()],
                ),
            ):
                try:
                    main()
                except BaseException as error:
                    result = error
                else:
                    result = None
            report = json.loads(
                (Path(directory) / "verification.json").read_text()
            )
        self.assertIsInstance(result, SystemExit)
        self.assertEqual(
            report["errors"][:3],
            [
                "topology query failed on db1: RuntimeError",
                "topology query failed on db2: RuntimeError",
                "topology query failed on db3: RuntimeError",
            ],
        )

    def test_gtid_failure_writes_report_and_exits_nonzero(self):
        topology = [{"host": "db1", "role": "PRIMARY", "state": "ONLINE"}]
        report, error = self.run_main_with(
            topology=topology,
            fetch_gtid_side_effect=RuntimeError("primary disconnected"),
            member_ids={"db1": []},
        )
        self.assertIsInstance(error, SystemExit)
        self.assertNotEqual(error.code, 0)
        self.assertIn(
            "failed to fetch Primary GTID from db1: RuntimeError",
            report["errors"],
        )

    def test_gtid_timeout_writes_report_and_exits_nonzero(self):
        topology = [{"host": "db1", "role": "PRIMARY", "state": "ONLINE"}]
        report, error = self.run_main_with(
            topology=topology,
            member_ids={"db1": []},
            wait_for_gtid_result=False,
        )
        self.assertIsInstance(error, SystemExit)
        self.assertNotEqual(error.code, 0)
        self.assertIn("db1 did not apply the Primary GTID set", report["errors"])

    def test_gtid_wait_error_writes_report_and_exits_nonzero(self):
        topology = [{"host": "db1", "role": "PRIMARY", "state": "ONLINE"}]
        report, error = self.run_main_with(
            topology=topology,
            member_ids={"db1": []},
            wait_for_gtid_side_effect=RuntimeError("wait disconnected"),
        )
        self.assertIsInstance(error, SystemExit)
        self.assertNotEqual(error.code, 0)
        self.assertIn(
            "GTID barrier check failed on db1: RuntimeError",
            report["errors"],
        )

    def test_snapshot_failure_writes_report_and_exits_nonzero(self):
        topology = [
            {"host": "db1", "role": "PRIMARY", "state": "ONLINE"},
            {"host": "db2", "role": "SECONDARY", "state": "ONLINE"},
        ]
        report, error = self.run_main_with(
            topology=topology,
            member_ids={"db1": []},
            fetch_ids_side_effect={"db2": RuntimeError("member unavailable")},
        )
        self.assertIsInstance(error, SystemExit)
        self.assertNotEqual(error.code, 0)
        self.assertIn("member snapshot failed on db2: RuntimeError", report["errors"])

    def test_failed_topology_seed_closes_cursor_and_connection(self):
        connection = FakeConnection(FailingCursor())
        with patch(
            "verifier.verify.connect",
            side_effect=[connection, RuntimeError(), RuntimeError()],
        ):
            with self.assertRaises(RuntimeError):
                fetch_topology()
        self.assertTrue(connection.cursor_value.closed)
        self.assertTrue(connection.closed)

    def test_fetch_ids_closes_cursor_and_connection_on_success_and_error(self):
        for cursor, raises in (
            (DataCursor(fetchall_result=[("request-1",)]), False),
            (FailingCursor(), True),
        ):
            with self.subTest(raises=raises):
                connection = FakeConnection(cursor)
                with patch("verifier.verify.connect", return_value=connection):
                    if raises:
                        with self.assertRaises(RuntimeError):
                            fetch_ids("db1")
                    else:
                        self.assertEqual(fetch_ids("db1"), ["request-1"])
                self.assertTrue(cursor.closed)
                self.assertTrue(connection.closed)

    def test_fetch_gtid_closes_cursor_and_connection_on_success_and_error(self):
        for cursor, raises in (
            (DataCursor(fetchone_result=("gtid-set",)), False),
            (FailingCursor(), True),
        ):
            with self.subTest(raises=raises):
                connection = FakeConnection(cursor)
                with patch("verifier.verify.connect", return_value=connection):
                    if raises:
                        with self.assertRaises(RuntimeError):
                            fetch_gtid_executed("db1")
                    else:
                        self.assertEqual(fetch_gtid_executed("db1"), "gtid-set")
                self.assertTrue(cursor.closed)
                self.assertTrue(connection.closed)

    def test_wait_for_gtid_closes_cursor_and_connection_on_success_and_error(self):
        for cursor, raises in (
            (DataCursor(fetchone_result=(0,)), False),
            (FailingCursor(), True),
        ):
            with self.subTest(raises=raises):
                connection = FakeConnection(cursor)
                with patch("verifier.verify.connect", return_value=connection):
                    if raises:
                        with self.assertRaises(RuntimeError):
                            wait_for_gtid("db1", "gtid-set")
                    else:
                        self.assertTrue(wait_for_gtid("db1", "gtid-set"))
                self.assertTrue(cursor.closed)
                self.assertTrue(connection.closed)

    def run_main_with(
        self,
        topology=None,
        fetch_topology_side_effect=None,
        fetch_gtid_side_effect=None,
        member_ids=None,
        fetch_ids_side_effect=None,
        wait_for_gtid_result=True,
        wait_for_gtid_side_effect=None,
    ):
        member_ids = member_ids or {}
        fetch_ids_side_effect = fetch_ids_side_effect or {}

        def fake_fetch_ids(host):
            result = fetch_ids_side_effect.get(host)
            if isinstance(result, BaseException):
                raise result
            return member_ids[host]

        with tempfile.TemporaryDirectory() as directory:
            evidence_dir = Path(directory)
            with (
                patch.object(sys, "argv", ["verify", "--evidence-dir", directory]),
                patch(
                    "verifier.verify.fetch_topology",
                    side_effect=fetch_topology_side_effect,
                    return_value=topology,
                ),
                patch(
                    "verifier.verify.fetch_gtid_executed",
                    side_effect=fetch_gtid_side_effect,
                    return_value="gtid-set",
                ),
                patch(
                    "verifier.verify.wait_for_gtid",
                    return_value=wait_for_gtid_result,
                    side_effect=wait_for_gtid_side_effect,
                ),
                patch("verifier.verify.fetch_ids", side_effect=fake_fetch_ids),
            ):
                try:
                    main()
                except BaseException as error:
                    result = error
                else:
                    result = None
            report_path = evidence_dir / "verification.json"
            report = json.loads(report_path.read_text()) if report_path.exists() else {}
        return report, result


class FailingCursor:
    def __init__(self):
        self.closed = False

    def execute(self, _query, _params=None):
        raise RuntimeError("query failed")

    def close(self):
        self.closed = True


class DataCursor:
    def __init__(self, fetchall_result=None, fetchone_result=None):
        self.closed = False
        self.fetchall_result = fetchall_result
        self.fetchone_result = fetchone_result

    def execute(self, _query, _params=None):
        pass

    def fetchall(self):
        return self.fetchall_result

    def fetchone(self):
        return self.fetchone_result

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor_value):
        self.cursor_value = cursor_value
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def close(self):
        self.closed = True


if __name__ == "__main__":
    unittest.main()
