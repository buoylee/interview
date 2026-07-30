import importlib
import json
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class ConfigVerificationTest(unittest.TestCase):
    def test_invalid_json_is_classified_and_preserves_cause(self):
        error_type = getattr(implementation, "ConfigError", None)
        if error_type is None:
            self.fail("ERR-001 invalid input is silently replaced by a default")

        with self.assertRaises(error_type) as captured:
            implementation.load_config("{")
        self.assertIsInstance(captured.exception.__cause__, json.JSONDecodeError)

    def test_missing_timeout_is_not_silently_defaulted(self):
        error_type = getattr(implementation, "ConfigError", None)
        if error_type is None:
            self.fail("ERR-001 missing input is silently replaced by a default")
        with self.assertRaises(error_type):
            implementation.load_config("{}")


if __name__ == "__main__":
    unittest.main()
