import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class ConfigProjectTest(unittest.TestCase):
    def test_loads_valid_timeout(self):
        config = implementation.load_config('{"timeout_ms": 250}')
        self.assertEqual(config.timeout_ms, 250)


if __name__ == "__main__":
    unittest.main()
