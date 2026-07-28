from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[4]
TRACK = REPO / "mysql-handson/09-replication-and-ha"
FILES = [
    TRACK / "ha-foundations.md",
    TRACK / "innodb-cluster/README.md",
    TRACK / "innodb-cluster/production-runbook.md",
    *sorted((TRACK / "innodb-cluster/scenarios").glob("*.md")),
]


class LinkTest(unittest.TestCase):
    def test_relative_markdown_links_resolve(self):
        missing = []
        for source in FILES:
            text = source.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^]]+\]\(([^)#]+)(?:#[^)]+)?\)", text):
                if "://" in target or target.startswith("mailto:"):
                    continue
                resolved = (source.parent / target).resolve()
                if not resolved.exists():
                    missing.append(f"{source.relative_to(REPO)} -> {target}")
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
