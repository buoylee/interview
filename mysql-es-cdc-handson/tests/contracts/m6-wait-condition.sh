#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
waiter="$root/scenarios/scripts/wait-condition.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
test -x "$waiter" || { echo 'missing wait-condition primitive' >&2; exit 1; }

literal='$(touch should-not-exist)'
output="$("$waiter" immediate 2 0.05 sh -c 'printf "%s|%s\n" "$1" "$2"' sh 'a b' "$literal")"
test "$output" = "a b|$literal"
test ! -e "$root/should-not-exist"

set +e
"$waiter" timeout 1 0.05 sh -c 'printf "last-stdout"; printf "last-stderr" >&2; exit 7' >"$tmp/out" 2>"$tmp/error"
rc=$?
set -e
test "$rc" -eq 124
test ! -s "$tmp/out"
jq -e '.status=="TIMEOUT" and .description=="timeout" and .last_exit_code==7 and .attempts>=2 and .duration_ms>=900 and .duration_ms<3000 and .last_stdout=="last-stdout" and .last_stderr=="last-stderr"' "$tmp/error" >/dev/null
test "$(wc -c <"$tmp/error" | tr -d ' ')" -le 8192

set +e
"$waiter" invalid nope 1 sh -c 'touch "$1"' sh "$tmp/ran" >/dev/null 2>&1
rc=$?
set -e
test "$rc" -eq 64
test ! -e "$tmp/ran"

printf 'M6 wait-condition contract passed\n'
