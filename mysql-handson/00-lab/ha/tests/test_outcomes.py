from pathlib import Path
import tempfile
import unittest

from workload.client import execute_order
from workload.model import JsonlLedger, OrderRequest, Outcome


class FakeCursor:
    def __init__(self, execute_error=None):
        self.execute_error = execute_error
        self.calls = 0

    def execute(self, sql, params):
        self.calls += 1
        if self.execute_error:
            raise self.execute_error

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor, commit_error=None):
        self._cursor = cursor
        self.commit_error = commit_error
        self.commit_calls = 0

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commit_calls += 1
        if self.commit_error:
            raise self.commit_error

    def close(self):
        pass


class ReadOnlyError(Exception):
    errno = 1290


class OutcomeTest(unittest.TestCase):
    def setUp(self):
        self.request = OrderRequest("req-1", '{"item":"book"}', "router-a")

    def test_success_requires_execute_and_commit_to_return(self):
        """Catches a client that records SUCCESS before commit returns."""
        connection = FakeConnection(FakeCursor())
        record = execute_order(lambda: connection, self.request, 2)
        self.assertEqual(record.outcome, Outcome.SUCCESS)
        self.assertEqual(connection.commit_calls, 1)

    def test_pre_send_connection_failure_can_retry(self):
        """Catches a client that fails pre-send attempts without retrying."""
        attempts = 0

        def connect():
            nonlocal attempts
            attempts += 1
            raise ConnectionError("not connected")

        record = execute_order(connect, self.request, 2)
        self.assertEqual(record.outcome, Outcome.FAILURE)
        self.assertEqual(record.retries, 2)
        self.assertEqual(attempts, 3)

    def test_post_send_disconnect_is_unknown_and_never_replayed(self):
        """Catches blind replay after SQL send loses its response."""
        cursor = FakeCursor(ConnectionResetError("response lost"))
        calls = 0

        def connect():
            nonlocal calls
            calls += 1
            return FakeConnection(cursor)

        record = execute_order(connect, self.request, 5)
        self.assertEqual(record.outcome, Outcome.UNKNOWN)
        self.assertEqual(calls, 1)
        self.assertEqual(cursor.calls, 1)

    def test_commit_disconnect_is_unknown_and_never_replayed(self):
        """Catches blind replay after commit response loss."""
        cursor = FakeCursor()
        connection = FakeConnection(cursor, ConnectionResetError("commit response lost"))
        calls = 0

        def connect():
            nonlocal calls
            calls += 1
            return connection

        record = execute_order(connect, self.request, 5)
        self.assertEqual(record.outcome, Outcome.UNKNOWN)
        self.assertEqual(calls, 1)
        self.assertEqual(cursor.calls, 1)
        self.assertEqual(connection.commit_calls, 1)

    def test_explicit_server_rejection_is_failure_and_never_replayed(self):
        """Catches read-only server rejection being mislabeled UNKNOWN."""
        cursor = FakeCursor(ReadOnlyError("server is read only"))
        record = execute_order(lambda: FakeConnection(cursor), self.request, 5)
        self.assertEqual(record.outcome, Outcome.FAILURE)
        self.assertEqual(cursor.calls, 1)

    def test_jsonl_round_trip_preserves_contract(self):
        """Catches JSONL serialization that loses a ledger record's fields or outcome."""
        record = execute_order(lambda: FakeConnection(FakeCursor()), self.request, 0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            JsonlLedger(path).append(record)
            self.assertEqual(JsonlLedger.load([path]), [record])


if __name__ == "__main__":
    unittest.main()
