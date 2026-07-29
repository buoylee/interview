#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
runner="$root/scenarios/scripts/run-scenario.sh"
fixture="$root/tests/fixtures/m6/runner-wrong-terminal.json"
tmp="$(mktemp -d)"
trap 'test -z "${runner_pid:-}" || kill -KILL "$runner_pid" 2>/dev/null || true; rm -rf "$tmp"' EXIT
export UV_CACHE_DIR="${UV_CACHE_DIR:-/private/tmp/mysql-es-cdc-uv-cache}"

assert_one_failed_attempt() {
  local evidence="$1" failure="$2" attempt
  attempt="$(find "$evidence/.runs/duplicate-event" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  test -n "$attempt"
  test "$(find "$attempt" -maxdepth 1 -type f | wc -l | tr -d ' ')" -eq 9
  jq -e --arg failure "$failure" '
    .result == "FAIL" and
    (.failed_assertions | index($failure)) != null and
    (.runner_run_id | test("^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"))
  ' "$attempt/result.json" >/dev/null
  bash "$root/tests/contracts/evidence-contract.sh" "$attempt" >/dev/null
  bash "$root/tests/contracts/no-evidence-secrets.sh" "$attempt"/*.json >/dev/null
}

only_attempt() {
  find "$1/.runs/duplicate-event" -mindepth 1 -maxdepth 1 -type d | head -n 1
}

# A validated scenario with an unsafe requested run ID still receives a safe,
# generated evidence identity and a complete FAIL attempt.
evidence="$tmp/invalid-run-id"
mkdir "$evidence"
set +e
M6_EVIDENCE_ROOT="$evidence" \
  M6_RUNNER_FIXTURE="$fixture" \
  M6_RUNNER_RUN_ID='../not-a-uuid' \
  bash "$runner" duplicate-event >/dev/null 2>&1
rc=$?
set -e
test "$rc" -ne 0
assert_one_failed_attempt "$evidence" runner_run_id_invalid
test ! -e "$tmp/not-a-uuid"
test ! -d "$evidence/.locks/duplicate-event"

# TERM immediately after the safe finalizer/traps are installed must retain a
# complete signal FAIL attempt, even before fixture parsing or fault intent.
evidence="$tmp/early-signal"
hold="$tmp/early-signal-hold"
mkdir "$evidence" "$hold"
M6_EVIDENCE_ROOT="$evidence" \
  M6_RUNNER_FIXTURE="$fixture" \
  M6_RUNNER_HOLD_STAGE_DIR="$hold" \
  bash "$runner" duplicate-event >/dev/null 2>&1 &
runner_pid=$!
"$root/scenarios/scripts/wait-condition.sh" \
  'runner installs earliest safe traps' 2 0.02 test -f "$hold/after-finalizer.ready"
kill -TERM "$runner_pid"
set +e
wait "$runner_pid"
rc=$?
set -e
runner_pid=
test "$rc" -eq 143
assert_one_failed_attempt "$evidence" signal_143
test ! -d "$evidence/.locks/duplicate-event"

# Fault ownership/cleanup intent is durable before dispatch. A dispatcher that
# applies the fixture fault and then fails still invokes idempotent recovery.
evidence="$tmp/partial-dispatch"
mkdir "$evidence"
set +e
M6_EVIDENCE_ROOT="$evidence" \
  M6_RUNNER_FIXTURE="$fixture" \
  M6_RUNNER_FAULT_MODE=partial-fail \
  bash "$runner" duplicate-event >/dev/null 2>&1
rc=$?
set -e
test "$rc" -ne 0
attempt="$(only_attempt "$evidence")"
jq -e '
  .result == "FAIL" and
  (.failed_assertions | index("runner_dispatch_failure")) != null and
  .cleanup_failures == 0 and
  (.cleanup_actions | length) == 1 and
  .cleanup_actions[0].name == "dispatch-owned-fixture-fault" and
  .cleanup_actions[0].success == true
' "$attempt/result.json" >/dev/null
jq -e '
  .cleanup_failures == 0 and
  .cleanup_actions[0].name == "dispatch-owned-fixture-fault" and
  .commands[0].target == "fixture-fault-status" and
  .commands[0].exit_code == 0
' "$attempt/recovery-actions.json" >/dev/null

# Cleanup truth comes from dispatch-recovery's structured result plus its
# external status observation, never from the scenario fixture.
forged_cleanup="$tmp/forged-cleanup.json"
jq '.cleanup_actions=[{"name":"fixture-forged-cleanup","success":false,"finished_at":"2026-07-29T06:02:00Z"}]' \
  "$fixture" >"$forged_cleanup"
evidence="$tmp/recovery-truth"
mkdir "$evidence"
set +e
M6_EVIDENCE_ROOT="$evidence" \
  M6_RUNNER_FIXTURE="$forged_cleanup" \
  bash "$runner" duplicate-event >/dev/null 2>&1
rc=$?
set -e
test "$rc" -ne 0
attempt="$(only_attempt "$evidence")"
jq -e '
  .cleanup_failures == 0 and
  (.cleanup_actions | length) == 1 and
  .cleanup_actions[0].name == "dispatch-owned-fixture-fault" and
  .cleanup_actions[0].success == true and
  ([.cleanup_actions[].name] | index("fixture-forged-cleanup")) == null
' "$attempt/result.json" >/dev/null

# A failed external cleanup observation is terminal and forces FAIL.
evidence="$tmp/recovery-failure"
mkdir "$evidence"
set +e
M6_EVIDENCE_ROOT="$evidence" \
  M6_RUNNER_FIXTURE="$fixture" \
  M6_RUNNER_RECOVERY_MODE=fail \
  bash "$runner" duplicate-event >/dev/null 2>&1
rc=$?
set -e
test "$rc" -ne 0
attempt="$(only_attempt "$evidence")"
jq -e '
  .result == "FAIL" and
  (.failed_assertions | index("runner_recovery_failure")) != null and
  (.failed_assertions | index("cleanup")) != null and
  .cleanup_failures == 1 and
  .cleanup_actions[0].success == false
' "$attempt/result.json" >/dev/null

# An existing version directory is never treated as mv's destination parent.
# The collision is represented under a fresh safe run ID.
evidence="$tmp/existing-version"
fixed_run_id=44444444-4444-4444-8444-444444444444
mkdir -p "$evidence/.runs/duplicate-event/$fixed_run_id" "$evidence/.locks"
touch "$evidence/.runs/duplicate-event/$fixed_run_id/competitor-owned"
set +e
M6_EVIDENCE_ROOT="$evidence" \
  M6_RUNNER_FIXTURE="$fixture" \
  M6_RUNNER_RUN_ID="$fixed_run_id" \
  bash "$runner" duplicate-event >/dev/null 2>&1
rc=$?
set -e
test "$rc" -ne 0
test -f "$evidence/.runs/duplicate-event/$fixed_run_id/competitor-owned"
test ! -e "$evidence/.runs/duplicate-event/$fixed_run_id/bundle"
test ! -e "$evidence/.runs/duplicate-event/$fixed_run_id/result.json"
attempt_count="$(find "$evidence/.runs/duplicate-event" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
test "$attempt_count" -eq 2
attempt="$(find "$evidence/.runs/duplicate-event" -mindepth 1 -maxdepth 1 -type d ! -name "$fixed_run_id" | head -n 1)"
jq -e '
  .result == "FAIL" and
  (.failed_assertions | index("runner_version_exists")) != null
' "$attempt/result.json" >/dev/null
bash "$root/tests/contracts/evidence-contract.sh" "$attempt" >/dev/null

# Once publication has pinned the physical scenario parent, replacing its
# pathname with a symlink must fail before any bundle bytes reach the attacker
# directory. Restoring the original parent must reveal the unchanged last-good
# canonical target.
evidence="$tmp/publish-parent-race"
hold="$tmp/publish-parent-race-hold"
outside="$tmp/publish-parent-race-outside"
mkdir "$evidence" "$hold" "$outside"
set +e
M6_EVIDENCE_ROOT="$evidence" M6_RUNNER_FIXTURE="$fixture" \
  bash "$runner" duplicate-event >/dev/null 2>&1
seed_rc=$?
set -e
test "$seed_rc" -ne 0
old_target="$(readlink "$evidence/duplicate-event")"
old_hash="$(shasum -a 256 "$evidence/duplicate-event/result.json" | awk '{print $1}')"
M6_EVIDENCE_ROOT="$evidence" \
  M6_RUNNER_FIXTURE="$fixture" \
  M6_RUNNER_PUBLISH_HOLD_DIR="$hold" \
  M6_RUNNER_PUBLISH_HOLD_STAGE=parent-opened \
  bash "$runner" duplicate-event >/dev/null 2>&1 &
runner_pid=$!
"$root/scenarios/scripts/wait-condition.sh" \
  'publisher pins scenario parent before mutation' 10 0.02 test -f "$hold/parent-opened.ready"
mv "$evidence/.runs/duplicate-event" "$evidence/.runs/duplicate-event.saved"
ln -s "$outside" "$evidence/.runs/duplicate-event"
touch "$hold/parent-opened.release"
set +e
wait "$runner_pid"
rc=$?
set -e
runner_pid=
test "$rc" -ne 0
test -z "$(find "$outside" -mindepth 1 -print -quit)"
unlink "$evidence/.runs/duplicate-event"
mv "$evidence/.runs/duplicate-event.saved" "$evidence/.runs/duplicate-event"
test "$(readlink "$evidence/duplicate-event")" = "$old_target"
test "$(shasum -a 256 "$evidence/duplicate-event/result.json" | awk '{print $1}')" = "$old_hash"

# A competitor creating the requested version after the publisher's absence
# check must win without receiving a nested bundle. The runner fails closed and
# leaves both the competitor marker and any prior canonical evidence untouched.
evidence="$tmp/publish-version-race"
hold="$tmp/publish-version-race-hold"
mkdir "$evidence" "$hold"
fixed_run_id=55555555-5555-4555-8555-555555555555
M6_EVIDENCE_ROOT="$evidence" \
  M6_RUNNER_FIXTURE="$fixture" \
  M6_RUNNER_RUN_ID="$fixed_run_id" \
  M6_RUNNER_PUBLISH_HOLD_DIR="$hold" \
  M6_RUNNER_PUBLISH_HOLD_STAGE=version-staged \
  bash "$runner" duplicate-event >/dev/null 2>&1 &
runner_pid=$!
"$root/scenarios/scripts/wait-condition.sh" \
  'publisher stages before exclusive version rename' 10 0.02 test -f "$hold/version-staged.ready"
mkdir "$evidence/.runs/duplicate-event/$fixed_run_id"
touch "$evidence/.runs/duplicate-event/$fixed_run_id/competitor-owned"
touch "$hold/version-staged.release"
set +e
wait "$runner_pid"
rc=$?
set -e
runner_pid=
test "$rc" -ne 0
test -f "$evidence/.runs/duplicate-event/$fixed_run_id/competitor-owned"
test ! -e "$evidence/.runs/duplicate-event/$fixed_run_id/bundle"
test ! -e "$evidence/.runs/duplicate-event/$fixed_run_id/result.json"
test ! -e "$evidence/duplicate-event"
test -z "$(find "$evidence/.runs/duplicate-event" -mindepth 1 -maxdepth 1 -name '.incoming.*' -print -quit)"

# Publication is not complete after validating only the private/staged bundle:
# both gates must run through the actual canonical symlink, bracketed by target
# identity verification.
test "$(grep -Fc 'publish-evidence.py" verify' "$runner")" -eq 2
grep -Fq 'evidence-contract.sh" "$canonical"' "$runner"
grep -Fq 'no-evidence-secrets.sh" "$canonical"' "$runner"

printf 'M6 Task 3 fix round 2 runner contract passed\n'
