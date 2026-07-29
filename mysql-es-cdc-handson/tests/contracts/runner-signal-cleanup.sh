#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)";runner="$root/scenarios/scripts/run-scenario.sh";fixture="$root/tests/fixtures/m6/runner-wrong-terminal.json";tmp="$(mktemp -d)";evidence="$tmp/evidence";hold="$tmp/hold"
trap 'test -z "${pid:-}"||kill -KILL "$pid" 2>/dev/null||true;rm -rf "$tmp"' EXIT
mkdir -p "$evidence"
M6_EVIDENCE_ROOT="$evidence" M6_RUNNER_FIXTURE="$fixture" M6_RUNNER_HOLD_FILE="$hold" bash "$runner" duplicate-event >"$tmp/out" 2>"$tmp/err" &pid=$!
"$root/scenarios/scripts/wait-condition.sh" 'runner reaches post-fault hold' 10 0.05 test -f "$hold.ready"
kill -TERM "$pid";set +e;wait "$pid";rc=$?;set -e;pid=
test "$rc" -eq 143
bundle="$evidence/duplicate-event";test -d "$bundle"
jq -e '.result=="FAIL" and (.failed_assertions|index("signal_143"))!=null and .cleanup_failures==0 and all(.cleanup_actions[];.success==true)' "$bundle/result.json" >/dev/null
test ! -d "$evidence/.locks/duplicate-event"
test -z "$(find "$evidence" -maxdepth 1 -name '.tmp.duplicate-event.*' -print -quit)"

printf 'M6 signal failure evidence and owned cleanup contract passed\n'
