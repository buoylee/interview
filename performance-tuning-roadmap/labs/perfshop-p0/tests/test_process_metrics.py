import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


LAB_ROOT = Path(__file__).resolve().parents[1]


def load_server(name, relative_path):
    mysql = types.ModuleType("mysql")
    mysql_connector = types.ModuleType("mysql.connector")
    mysql_connector.connect = lambda **kwargs: None
    mysql.connector = mysql_connector

    redis = types.ModuleType("redis")
    redis.Redis = lambda **kwargs: object()

    path = LAB_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(
        sys.modules,
        {"mysql": mysql, "mysql.connector": mysql_connector, "redis": redis},
    ):
        spec.loader.exec_module(module)
    return module


class CurrentRssBytesTests(unittest.TestCase):
    def test_reads_resident_pages_instead_of_lifetime_peak(self):
        modules = [
            load_server("perfshop_app_server", "app/src/server.py"),
            load_server("perfshop_downstream_server", "downstream/src/server.py"),
        ]

        with tempfile.TemporaryDirectory() as directory:
            statm = Path(directory) / "statm"
            statm.write_text("100 7 3 2 0 1 0\n", encoding="ascii")

            for module in modules:
                with self.subTest(module=module.__name__):
                    self.assertTrue(
                        hasattr(module, "current_rss_bytes"),
                        "server must expose current_rss_bytes",
                    )
                    self.assertEqual(
                        module.current_rss_bytes(statm_path=statm, page_size=4096),
                        7 * 4096,
                    )


if __name__ == "__main__":
    unittest.main()
