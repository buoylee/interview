#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

test -x scenarios/scripts/render-m1-boundary.sh
test -x scenarios/scripts/assert-m1-boundary-doc.sh
grep -Eq '^up-adapter:' Makefile
grep -Eq '^scenario-m1:' Makefile
grep -Eq '^verify-m1:' Makefile
grep -Eq '^\.PHONY:.*(^|[[:space:]])gate-m1([[:space:]]|$)' Makefile

gate_recipe=$(awk '
  /^gate-m1:/ { in_gate = 1; next }
  in_gate && /^[^[:space:]#][^:]*:/ { exit }
  in_gate { print }
' Makefile)

step_line() {
  local expected="$1"
  printf '%s\n' "$gate_recipe" | grep -nF "$expected" | head -n 1 | cut -d: -f1
}

verify_line=$(step_line '$(MAKE) verify-m1')
stop_line=$(step_line '$(COMPOSE_ADAPTER) stop canal-adapter canal-adapter-server')
remove_line=$(step_line '$(COMPOSE_ADAPTER) rm -f canal-adapter canal-adapter-server')
absence_line=$(step_line '$(COMPOSE_ADAPTER) ps -a -q canal-adapter canal-adapter-server')
reset_line=$(step_line '$(MAKE) reset')
smoke_line=$(step_line '$(MAKE) smoke-m0')

test "$verify_line" -lt "$stop_line"
test "$stop_line" -lt "$remove_line"
test "$remove_line" -lt "$absence_line"
test "$absence_line" -lt "$reset_line"
test "$reset_line" -lt "$smoke_line"

output=$(mktemp "${TMPDIR:-/tmp}/m1-boundary-doc.XXXXXX")
trap 'rm -f "$output"' EXIT
M1_BOUNDARY_OUTPUT="$output" bash scenarios/scripts/render-m1-boundary.sh
bash scenarios/scripts/assert-m1-boundary-doc.sh "$output"
diff -u "$output" docs/01-canal-boundary.md
