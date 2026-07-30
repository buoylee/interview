from pathlib import Path
import tempfile
import unittest

from workload.model import JsonlLedger, LedgerRecord, Outcome
from workload.runner import run_workload


class RunnerTest(unittest.TestCase):
    def test_bounded_runner_writes_one_record_per_request(self):
        """Catches a bounded runner that omits records or reuses request IDs."""
        def fake_execute(connect, request, retries):
            return LedgerRecord(
                request.request_id, request.payload, request.router,
                "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00.001+00:00",
                Outcome.SUCCESS, 0, None,
            )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger-router-a.jsonl"
            run_workload("router-a", path, 3, 0, lambda: object(), fake_execute)
            records = JsonlLedger.load([path])
            self.assertEqual(len(records), 3)
            self.assertTrue(all(record.router == "router-a" for record in records))
            self.assertEqual(len({record.request_id for record in records}), 3)


if __name__ == "__main__":
    unittest.main()
