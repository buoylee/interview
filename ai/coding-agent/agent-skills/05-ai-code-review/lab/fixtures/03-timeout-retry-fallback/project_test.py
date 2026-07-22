import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class HealthyClient:
    def get(self, user_id, timeout=None):
        return {"id": user_id, "name": "Ada"}


class ProfileProjectTest(unittest.TestCase):
    def test_returns_profile_when_dependency_is_healthy(self):
        result = implementation.fetch_profile(HealthyClient(), "user-1")
        profile = result.profile if hasattr(result, "profile") else result
        self.assertEqual(profile, {"id": "user-1", "name": "Ada"})


if __name__ == "__main__":
    unittest.main()
