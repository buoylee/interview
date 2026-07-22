import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class TimingOutClient:
    def __init__(self):
        self.timeouts = []

    def get(self, user_id, timeout=None):
        self.timeouts.append(timeout)
        raise TimeoutError(user_id)


class ProfileVerificationTest(unittest.TestCase):
    def test_timeout_budget_retry_cap_and_fallback_are_explicit(self):
        client = TimingOutClient()
        result = implementation.fetch_profile(client, "user-1")

        self.assertEqual(
            client.timeouts,
            [0.05, 0.05],
            "RES-001 calls must carry a bounded timeout and retry cap",
        )
        self.assertEqual(result.status, "degraded")
        self.assertIsNone(result.profile)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(result.error, "upstream-timeout")


if __name__ == "__main__":
    unittest.main()
