#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

test -x scenarios/scripts/render-m1-boundary.sh
test -x scenarios/scripts/assert-m1-boundary-doc.sh
grep -Eq '^up-adapter:' Makefile
grep -Eq '^scenario-m1:' Makefile
grep -Eq '^verify-m1:' Makefile

output=$(mktemp "${TMPDIR:-/tmp}/m1-boundary-doc.XXXXXX")
trap 'rm -f "$output"' EXIT
M1_BOUNDARY_OUTPUT="$output" bash scenarios/scripts/render-m1-boundary.sh
bash scenarios/scripts/assert-m1-boundary-doc.sh "$output"
diff -u "$output" docs/01-canal-boundary.md
