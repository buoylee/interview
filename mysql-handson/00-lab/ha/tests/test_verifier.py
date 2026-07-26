import unittest

from verifier.verify import evaluate
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


if __name__ == "__main__":
    unittest.main()
