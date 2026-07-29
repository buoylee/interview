#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)";runner="$root/scenarios/scripts/run-scenario.sh";fixture="$root/tests/fixtures/m6/runner-wrong-terminal.json";tmp="$(mktemp -d)";evidence="$tmp/evidence"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$evidence"
set +e;M6_EVIDENCE_ROOT="$evidence" M6_RUNNER_FIXTURE="$fixture" bash "$runner" duplicate-event >/dev/null 2>&1;first_rc=$?;set -e;test "$first_rc" -ne 0
old_target="$(readlink "$evidence/duplicate-event")";old_hash="$(shasum -a 256 "$evidence/duplicate-event/result.json"|awk '{print $1}')"
good="$tmp/good.json";jq '.observed_pipeline_state="HEALTHY"' "$fixture" >"$good"
set +e;M6_EVIDENCE_ROOT="$evidence" M6_RUNNER_FIXTURE="$good" bash "$runner" duplicate-event >/dev/null 2>&1;fixture_pass_rc=$?;set -e
test "$fixture_pass_rc" -ne 0;test "$(readlink "$evidence/duplicate-event")" = "$old_target"
test "$(shasum -a 256 "$evidence/duplicate-event/result.json"|awk '{print $1}')" = "$old_hash"
test "$(find "$evidence/.runs/duplicate-event" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')" -eq 2
while IFS= read -r result_file;do jq -e '.result=="FAIL" and (.failed_assertions|index("fixture_mode_forbids_pass"))!=null' "$result_file" >/dev/null;done < <(find "$evidence/.runs/duplicate-event" -mindepth 2 -maxdepth 2 -name result.json)

interrupted="$tmp/interrupted";mkdir "$interrupted"
set +e;M6_EVIDENCE_ROOT="$interrupted" M6_RUNNER_FIXTURE="$fixture" M6_RUNNER_FAIL_STAGE=before-replace bash "$runner" duplicate-event >/dev/null 2>&1;replace_rc=$?;set -e
test "$replace_rc" -ne 0;test ! -e "$interrupted/duplicate-event"
test "$(find "$interrupted/.runs/duplicate-event" -mindepth 1 -maxdepth 1 -type d|wc -l|tr -d ' ')" -eq 1

ln -s "$tmp" "$evidence/manual-elasticsearch-drift"
set +e;M6_EVIDENCE_ROOT="$evidence" M6_RUNNER_FIXTURE="$fixture" bash "$runner" manual-elasticsearch-drift >/dev/null 2>&1;escape_rc=$?;set -e;test "$escape_rc" -eq 74;test -z "$(find "$tmp" -maxdepth 1 -name result.json -print -quit)"

mkdir -p "$evidence/.locks/duplicate-event"
set +e;M6_EVIDENCE_ROOT="$evidence" M6_RUNNER_FIXTURE="$fixture" bash "$runner" duplicate-event >/dev/null 2>&1;owner_rc=$?;set -e;test "$owner_rc" -eq 75
test "$(readlink "$evidence/duplicate-event")" = "$old_target";rmdir "$evidence/.locks/duplicate-event"

bad="$tmp/bad-command.json";jq '.commands[0].shell="rm -rf /"' "$fixture" >"$bad"
set +e;M6_EVIDENCE_ROOT="$evidence" M6_RUNNER_FIXTURE="$bad" bash "$runner" duplicate-event >/dev/null 2>&1;command_rc=$?;set -e;test "$command_rc" -ne 0;test "$(readlink "$evidence/duplicate-event")" = "$old_target"
bad_recovery="$tmp/bad-recovery.json";jq '.recovery_commands[0].authorization="value-do-not-echo"' "$fixture" >"$bad_recovery"
set +e;M6_EVIDENCE_ROOT="$evidence" M6_RUNNER_FIXTURE="$bad_recovery" bash "$runner" duplicate-event >/dev/null 2>&1;recovery_rc=$?;set -e;test "$recovery_rc" -ne 0;test "$(readlink "$evidence/duplicate-event")" = "$old_target"
secret="$tmp/secret.json";jq '.commands[0].target="rootpass"' "$fixture" >"$secret"
set +e;M6_EVIDENCE_ROOT="$evidence" M6_RUNNER_FIXTURE="$secret" bash "$runner" duplicate-event >/dev/null 2>&1;secret_rc=$?;set -e;test "$secret_rc" -ne 0;test "$(readlink "$evidence/duplicate-event")" = "$old_target";test "$(shasum -a 256 "$evidence/duplicate-event/result.json"|awk '{print $1}')" = "$old_hash"

printf 'M6 atomic replacement, ownership, path, and inert-command contract passed\n'
