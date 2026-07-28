from pathlib import Path
import re
import unicodedata
import unittest
from urllib.parse import unquote


REPO = Path(__file__).resolve().parents[4]
TRACK = REPO / "mysql-handson/09-replication-and-ha"
FILES = [
    TRACK / "ha-foundations.md",
    TRACK / "innodb-cluster/README.md",
    TRACK / "innodb-cluster/production-runbook.md",
    *sorted((TRACK / "innodb-cluster/scenarios").glob("*.md")),
]


def github_slug(heading):
    heading = re.sub(r"<[^>]+>", "", heading)
    heading = re.sub(r"[`*_~\[\]]", "", heading).strip().lower()
    heading = "".join(
        char
        for char in heading
        if not unicodedata.category(char).startswith("P") or char in "-_"
    )
    return re.sub(r"\s+", "-", heading)


def heading_anchors(text):
    anchors = set()
    next_suffix = {}
    in_fence = False
    fence_marker = None
    for line in text.splitlines():
        fence = re.match(r"^\s*(```|~~~)", line)
        if fence:
            marker = fence.group(1)
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = None
            continue
        if in_fence:
            continue
        match = re.match(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        base = github_slug(match.group(1))
        if not base:
            continue
        anchor = base
        suffix = next_suffix.get(base, 1)
        while anchor in anchors:
            anchor = f"{base}-{suffix}"
            suffix += 1
        next_suffix[base] = suffix
        anchors.add(anchor)
    return anchors


def missing_relative_links(documents):
    documents_by_path = {source.resolve(): text for source, text in documents}
    missing = []
    for source, text in documents:
        for raw_target in re.findall(r"(?<!!)\[[^]]+\]\(([^)\s]+)(?:\s+[^)]*)?\)", text):
            target = unquote(raw_target)
            if "://" in target or target.startswith("mailto:"):
                continue
            path_part, separator, fragment = target.partition("#")
            resolved = (source.parent / path_part).resolve() if path_part else source.resolve()
            if not resolved.exists() and resolved not in documents_by_path:
                missing.append(f"{source.relative_to(REPO)} -> {target}")
                continue
            if separator:
                target_text = documents_by_path.get(resolved)
                if target_text is None:
                    target_text = resolved.read_text(encoding="utf-8")
                if fragment not in heading_anchors(target_text):
                    missing.append(f"{source.relative_to(REPO)} -> {target}")
    return missing


class LinkTest(unittest.TestCase):
    def test_missing_fragment_is_reported(self):
        source = TRACK / "innodb-cluster/README.md"
        missing = missing_relative_links(
            [(source, "[broken](../ha-foundations.md#not-a-real-heading)")]
        )
        self.assertEqual(
            missing,
            [
                "mysql-handson/09-replication-and-ha/innodb-cluster/README.md "
                "-> ../ha-foundations.md#not-a-real-heading"
            ],
        )

    def test_same_file_url_decoded_unicode_and_duplicate_anchors_resolve(self):
        source = TRACK / "fixture.md"
        text = """# 自测题：读／写
## 重复标题
## 重复标题

[same](#自测题读写)
[decoded](#%E8%87%AA%E6%B5%8B%E9%A2%98%E8%AF%BB%E5%86%99)
[duplicate](#重复标题-1)
"""
        self.assertEqual(missing_relative_links([(source, text)]), [])

    def test_code_fence_headings_do_not_create_anchors(self):
        source = TRACK / "fixture.md"
        text = """# Real
```markdown
## Not real
```
[bad](#not-real)
"""
        self.assertEqual(
            missing_relative_links([(source, text)]),
            ["mysql-handson/09-replication-and-ha/fixture.md -> #not-real"],
        )

    def test_relative_markdown_links_resolve(self):
        self.assertEqual(
            missing_relative_links(
                [(source, source.read_text(encoding="utf-8")) for source in FILES]
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
