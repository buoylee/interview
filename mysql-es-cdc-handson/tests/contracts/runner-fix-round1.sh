#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
runner="$root/scenarios/scripts/run-scenario.sh"
fixture="$root/tests/fixtures/m6/runner-wrong-terminal.json"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

latest_attempt() {
  find -H "$1/.runs/duplicate-event" -mindepth 1 -maxdepth 1 -type d | LC_ALL=C sort | tail -n 1
}

assert_failed_attempt() {
  local evidence="$1" expected="$2" attempt
  attempt="$(latest_attempt "$evidence")"
  test -n "$attempt"
  test "$(find "$attempt" -maxdepth 1 -type f | wc -l | tr -d ' ')" -eq 9
  jq -e --arg expected "$expected" '.result=="FAIL" and (.failed_assertions|index($expected))!=null' "$attempt/result.json" >/dev/null
  bash "$root/tests/contracts/evidence-contract.sh" "$attempt" >/dev/null
}

# A fixture that requests an otherwise forgeable PASS remains FAIL. Its stale IDs
# and cleanup observations are evidence, not values the runner may rewrite.
evidence="$tmp/fixture";mkdir "$evidence"
forged="$tmp/forged.json"
jq '.observed_pipeline_state="HEALTHY"|.verification.run_id="22222222-2222-4222-8222-222222222222"|.watermark_run_id="33333333-3333-4333-8333-333333333333"|.cleanup_actions[0].name="fixture-owned-cleanup"' "$fixture" >"$forged"
set +e
M6_EVIDENCE_ROOT="$evidence" M6_RUNNER_FIXTURE="$forged" bash "$runner" duplicate-event >/dev/null 2>&1
rc=$?
set -e
test "$rc" -ne 0
assert_failed_attempt "$evidence" fixture_mode_forbids_pass
attempt="$(latest_attempt "$evidence")"
jq -e '.verification.run_id=="22222222-2222-4222-8222-222222222222" and .watermark_run_id=="33333333-3333-4333-8333-333333333333" and .cleanup_actions[0].name=="fixture-owned-cleanup"' "$attempt/result.json" >/dev/null

# Once canonical exists, a later failed attempt remains addressable but cannot
# replace the last-good target.
old_target="$(readlink "$evidence/duplicate-event")"
old_hash="$(shasum -a 256 "$evidence/duplicate-event/result.json" | awk '{print $1}')"
set +e
M6_EVIDENCE_ROOT="$evidence" M6_RUNNER_FIXTURE="$fixture" bash "$runner" duplicate-event >/dev/null 2>&1
rc=$?
set -e
test "$rc" -ne 0
test "$(readlink "$evidence/duplicate-event")" = "$old_target"
test "$(shasum -a 256 "$evidence/duplicate-event/result.json" | awk '{print $1}')" = "$old_hash"
test "$(find "$evidence/.runs/duplicate-event" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')" -eq 2

# Every post-ID-validation class reaches the failure finalizer.
for mode in parse command manifest dispatch; do
  evidence="$tmp/failure-$mode";mkdir "$evidence"
  input="$fixture"
  if test "$mode" = parse; then input="$tmp/malformed.json";printf '{' >"$input";fi
  set +e
  M6_EVIDENCE_ROOT="$evidence" M6_RUNNER_FIXTURE="$input" M6_RUNNER_FAIL_STAGE="$mode" bash "$runner" duplicate-event >/dev/null 2>&1
  rc=$?
  set -e
  test "$rc" -ne 0
  assert_failed_attempt "$evidence" "runner_${mode}_failure"
done

# Owned hierarchy must be physical directories, never symlink parents.
for level in root runs locks scenario version; do
  base="$tmp/path-$level";mkdir -p "$base/real";evidence="$base/evidence"
  case "$level" in
    root) ln -s "$base/real" "$evidence" ;;
    runs) mkdir "$evidence";ln -s "$base/real" "$evidence/.runs" ;;
    locks) mkdir "$evidence";ln -s "$base/real" "$evidence/.locks" ;;
    scenario) mkdir -p "$evidence/.runs" "$evidence/.locks";ln -s "$base/real" "$evidence/.runs/duplicate-event" ;;
    version) mkdir -p "$evidence/.runs/duplicate-event" "$evidence/.locks";ln -s "$base/real" "$evidence/.runs/duplicate-event/44444444-4444-4444-8444-444444444444" ;;
  esac
  set +e
  M6_EVIDENCE_ROOT="$evidence" M6_RUNNER_FIXTURE="$fixture" M6_RUNNER_RUN_ID=44444444-4444-4444-8444-444444444444 bash "$runner" duplicate-event >/dev/null 2>&1
  rc=$?
  set -e
  test "$rc" -eq 74
  test -z "$(find "$base/real" -name result.json -print -quit)"
done

printf 'M6 Task 3 fix round 1 runner contract passed\n'
