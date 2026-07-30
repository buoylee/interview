#!/usr/bin/env bash
set -euo pipefail

block="$(awk '
  /^verify: verify-fast$/ { capture=1 }
  capture && seen && /^[^[:space:]#].*:/ { exit }
  capture { print; seen=1 }
' Makefile)"

line_of() {
  awk -v needle="$1" 'index($0, needle) { print NR; exit }' <<<"$block"
}

reset_line="$(line_of '$(MAKE) reset')"
up_line="$(line_of '$(MAKE) up')"
m0_line="$(line_of 'tests/end-to-end/m0-smoke.sh')"
live_line="$(line_of '$(MAKE) verify-live-contracts')"
m4_line="$(line_of 'tests/end-to-end/m4-reconciliation.sh')"
m5_line="$(line_of 'tests/end-to-end/m5-rebuild.sh')"
projection_live_line="$(line_of '$(MAKE) verify-projection-live-contracts')"

test -n "$reset_line"
test -n "$up_line"
test -n "$m0_line"
test -n "$live_line"
test -n "$m4_line"
test -n "$m5_line"
test -n "$projection_live_line"
test "$reset_line" -lt "$up_line"
test "$up_line" -lt "$m0_line"
test "$m0_line" -lt "$live_line"
test "$live_line" -lt "$m4_line"
test "$m4_line" -lt "$m5_line"
test "$m5_line" -lt "$projection_live_line"

echo 'Fresh M0 verify ordering contract passed'
