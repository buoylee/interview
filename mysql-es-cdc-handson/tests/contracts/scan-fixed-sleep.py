#!/usr/bin/env python3
"""Reject fixed sleep commands without treating comments or output text as commands."""

import re
import sys
from pathlib import Path


COMMAND_SLEEP = re.compile(
    r"(?:^|[;&|({}`]|\$\()\s*"
    r"(?:(?:command|builtin|env)\s+(?:[A-Za-z_][A-Za-z0-9_]*=\S+\s+)*)?"
    r"sleep(?:\s|$)"
)
ALIAS_DEF = re.compile(r"^\s*alias\s+([A-Za-z_][A-Za-z0-9_]*)=(['\"])(.*?)\2\s*$")
SLEEP_VAR = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)=(['\"]?)sleep\2\s*;?")


def without_comment(line: str) -> str:
    quote = None
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
        elif char == "\\" and quote != "'":
            escaped = True
        elif quote:
            if char == quote:
                quote = None
        elif char in "'\"":
            quote = char
        elif char == "#" and (index == 0 or line[index - 1].isspace()):
            return line[:index]
    return line


def scan(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    aliases: set[str] = set()
    variables: set[str] = set()
    findings: list[tuple[int, str]] = []
    active_sleep_lines: list[tuple[int, str]] = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = without_comment(raw)
        alias = ALIAS_DEF.match(line)
        if alias and COMMAND_SLEEP.search(alias.group(3)):
            aliases.add(alias.group(1))
            continue
        variable = SLEEP_VAR.match(line)
        if variable:
            variables.add(variable.group(1))
        direct = COMMAND_SLEEP.search(line)
        wrapped_code = re.search(r"\b(?:ba|z|k)?sh\s+-c\s+(['\"])(.*?)\1", line)
        alias_call = any(re.search(rf"(?:^|[;&|()]\s*){re.escape(name)}(?:\s|$)", line) for name in aliases)
        variable_call = any(re.search(rf"(?:^|[;&|()]\s*)\$\{{?{re.escape(name)}\}}?(?:\s|$)", line) for name in variables)
        if direct or (wrapped_code and COMMAND_SLEEP.search(wrapped_code.group(2))) or alias_call or variable_call:
            active_sleep_lines.append((number, line.strip()))

    if not active_sleep_lines:
        return findings
    if path.name != "wait-condition.sh":
        return [(number, "fixed sleep command") for number, _ in active_sleep_lines]
    if "deadline_epoch" not in text or "attempt" not in text or not re.search(r"\bwhile\b", text):
        findings.append((1, "wait primitive lacks deadline/attempt evidence"))
    for number, line in active_sleep_lines:
        if line.rstrip(";") != 'sleep "$poll_seconds"':
            findings.append((number, "wait primitive sleep is not the bounded poll interval"))
    return findings


def main() -> int:
    failed = False
    for name in sys.argv[1:]:
        path = Path(name)
        for line, reason in scan(path):
            print(f"{path}:{line}: {reason}", file=sys.stderr)
            failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
