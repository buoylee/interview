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
    parser.add_argument("paths", nargs="+", help="SCHEMA INSTANCE pairs")
    parser.add_argument("--array-property")
    args = parser.parse_args()

    errors = []
    if len(args.paths) % 2:
        parser.error("expected SCHEMA INSTANCE pairs")
    for schema_path, instance_path in zip(args.paths[::2], args.paths[1::2]):
        schema = load(schema_path)
        instance = load(instance_path)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        instances = instance[args.array_property] if args.array_property else [instance]
        for index, item in enumerate(instances):
            for error in validator.iter_errors(item):
                location = "/".join(str(part) for part in error.absolute_path)
                prefix = f"{args.array_property}/{index}" if args.array_property else "instance"
                errors.append(f"{instance_path}:{prefix}/{location}: {error.message}".rstrip("/"))
    if errors:
        for error in sorted(errors):
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
