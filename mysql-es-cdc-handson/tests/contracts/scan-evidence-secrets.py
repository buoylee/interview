#!/usr/bin/env python3
"""Find evidence credentials without printing matched values."""

import base64
import binascii
import re
import sys
from pathlib import Path
from urllib.parse import unquote


PATTERNS = (
    ("password-key", re.compile(r"(?i)(?:^|[\s{,;])['\"]?password['\"]?\s*[:=]")),
    ("authorization-key", re.compile(r"(?i)(?:^|[\s{,;])['\"]?authorization['\"]?\s*[:=]")),
    ("api-key", re.compile(r"(?i)(?:^|[\s{,;])['\"]?api[_-]?key['\"]?\s*[:=]")),
    ("secret-key", re.compile(r"(?i)(?:^|[\s{,;])['\"]?secret['\"]?\s*[:=]")),
    ("bearer-value", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")),
    ("canal-credential", re.compile(r"(?i)\bcanalpass\b")),
    ("root-basic-auth", re.compile(r"(?i)\broot:root\b")),
    ("root-password-literal", re.compile(r"(?i)\brootpass\b")),
)
PWD_ASSIGNMENT = re.compile(
    r"(?i)\b(?:MYSQL_PWD|[A-Z][A-Z0-9_]*_PWD)\s*=\s*(['\"]?)([^'\"\s;,]+)"
)
BASE64_TOKEN = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{16,}={0,2}(?![A-Za-z0-9+/=])")


def first_pattern(text: str):
    for match in PWD_ASSIGNMENT.finditer(text):
        if not match.group(2).startswith("$"):
            return "pwd-env-literal"
    for name, pattern in PATTERNS:
        if pattern.search(text):
            return name
    return None


def scan(text: str):
    direct = first_pattern(text)
    if direct:
        return direct
    decoded_url = unquote(text)
    if decoded_url != text:
        encoded = first_pattern(decoded_url)
        if encoded:
            return f"url-encoded-{encoded}"
    for candidate in BASE64_TOKEN.findall(text):
        try:
            decoded = base64.b64decode(candidate, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            continue
        encoded = first_pattern(decoded)
        if encoded:
            return f"base64-{encoded}"
    return None


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "--stdin":
        finding = scan(sys.stdin.read())
        if finding:
            print(f"{sys.argv[2]}: source={sys.argv[3]} rule={finding}", file=sys.stderr)
            return 1
        return 0
    failures = 0
    for name in sys.argv[1:]:
        path = Path(name)
        if not path.is_file():
            continue
        finding = scan(path.read_text(encoding="utf-8", errors="replace"))
        if finding:
            print(f"{path}: source=worktree rule={finding}", file=sys.stderr)
            failures += 1
            if failures >= 20:
                print("secret diagnostics truncated after 20 paths", file=sys.stderr)
                break
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
