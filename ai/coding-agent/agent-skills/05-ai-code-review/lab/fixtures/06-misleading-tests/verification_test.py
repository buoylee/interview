import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class EmailVerificationTest(unittest.TestCase):
    def test_trims_boundary_whitespace(self):
        self.assertEqual(
            implementation.normalize_email("  ADA@EXAMPLE.COM  "),
            "ada@example.com",
            "TEST-001 visible tests prove only lowercasing, not normalization",
        )

    def test_rejects_malformed_email(self):
        with self.assertRaises(ValueError):
            implementation.normalize_email("not-an-email")


if __name__ == "__main__":
    unittest.main()
