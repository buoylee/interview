#!/usr/bin/env python3
"""Validate JSON instances with the real jsonschema Draft 2020-12 engine."""

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


def load(path: str):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("schema")
    parser.add_argument("instance")
    parser.add_argument("--array-property")
    args = parser.parse_args()

    schema = load(args.schema)
    instance = load(args.instance)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    instances = instance[args.array_property] if args.array_property else [instance]
    errors = []
    for index, item in enumerate(instances):
        for error in validator.iter_errors(item):
            location = "/".join(str(part) for part in error.absolute_path)
            prefix = f"{args.array_property}/{index}" if args.array_property else "instance"
            errors.append(f"{prefix}/{location}: {error.message}".rstrip("/"))
    if errors:
        for error in sorted(errors):
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
