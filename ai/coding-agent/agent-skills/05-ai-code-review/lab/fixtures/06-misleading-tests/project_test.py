import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class EmailProjectTest(unittest.TestCase):
    def test_lowercases_email(self):
        self.assertEqual(
            implementation.normalize_email("ADA@EXAMPLE.COM"),
            "ada@example.com",
        )


if __name__ == "__main__":
    unittest.main()
