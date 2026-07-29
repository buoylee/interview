#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
runner="$root/scenarios/scripts/run-scenario.sh"
fixture="$root/tests/fixtures/m6/runner-wrong-terminal.json"
tmp="$(mktemp -d)"
runner_pid=
trap 'test -z "${runner_pid:-}" || kill -KILL "$runner_pid" 2>/dev/null || true; rm -rf "$tmp"' EXIT
export UV_CACHE_DIR="${UV_CACHE_DIR:-/private/tmp/mysql-es-cdc-uv-cache}"

only_attempt() {
  find "$1/.runs/duplicate-event" -mindepth 1 -maxdepth 1 -type d | head -n 1
}

assert_single_signal_attempt() {
  local evidence="$1" attempt
  test "$(find "$evidence/.runs/duplicate-event" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')" -eq 1
  attempt="$(only_attempt "$evidence")"
  test "$(find "$attempt" -maxdepth 1 -type f | wc -l | tr -d ' ')" -eq 9
  jq -e '
    .result=="FAIL" and
    ([.failed_assertions[]|select(.=="signal_130" or .=="signal_143")]|length)>=1
  ' "$attempt/result.json" >/dev/null
  bash "$root/tests/contracts/evidence-contract.sh" "$attempt" >/dev/null
  bash "$root/tests/contracts/no-evidence-secrets.sh" "$attempt"/*.json >/dev/null
  test ! -d "$evidence/.locks/duplicate-event"
}

pre_uuid_signal() {
  local evidence="$tmp/pre-uuid" fakebin="$tmp/pre-uuid-bin" control="$tmp/pre-uuid-control" rc
  mkdir "$evidence" "$fakebin" "$control"
  apply_fake_uuidgen="$fakebin/uuidgen"
  printf '%s\n' '#!/usr/bin/env bash' >"$apply_fake_uuidgen"
  printf '%s\n' 'set -euo pipefail' >>"$apply_fake_uuidgen"
  printf '%s\n' 'touch "$M6_UUIDGEN_CONTROL/ready"' >>"$apply_fake_uuidgen"
  printf '%s\n' 'while test ! -f "$M6_UUIDGEN_CONTROL/release"; do :; done' >>"$apply_fake_uuidgen"
  printf '%s\n' 'printf "%s\n" 66666666-6666-4666-8666-666666666666' >>"$apply_fake_uuidgen"
  chmod +x "$apply_fake_uuidgen"
  PATH="$fakebin:$PATH" \
    M6_UUIDGEN_CONTROL="$control" \
    M6_EVIDENCE_ROOT="$evidence" \
    M6_RUNNER_FIXTURE="$fixture" \
    bash "$runner" duplicate-event >/dev/null 2>&1 &
  runner_pid=$!
  "$root/scenarios/scripts/wait-condition.sh" \
    'runner blocks inside uuid generation' 5 0.02 test -f "$control/ready"
  kill -TERM "$runner_pid"
  touch "$control/release"
  set +e
  wait "$runner_pid"
  rc=$?
  set -e
  runner_pid=
  test "$rc" -eq 143
  assert_single_signal_attempt "$evidence"
}

reentrant_signal() {
  local evidence="$tmp/reentrant" hold="$tmp/reentrant-hold" rc
  mkdir "$evidence" "$hold"
  M6_EVIDENCE_ROOT="$evidence" \
    M6_RUNNER_FIXTURE="$fixture" \
    M6_RUNNER_FINALIZE_HOLD_DIR="$hold" \
    bash "$runner" duplicate-event >/dev/null 2>&1 &
  runner_pid=$!
  "$root/scenarios/scripts/wait-condition.sh" \
    'single finalizer enters controlled fixture hold' 10 0.02 test -f "$hold/finalizer-entered.ready"
  kill -TERM "$runner_pid"
  kill -INT "$runner_pid" 2>/dev/null || true
  touch "$hold/finalizer-entered.release"
  set +e
  wait "$runner_pid"
  rc=$?
  set -e
  runner_pid=
  test "$rc" -eq 130 || test "$rc" -eq 143
  assert_single_signal_attempt "$evidence"
}

canonical_target_swap() {
  local evidence="$tmp/canonical-swap" hold="$tmp/canonical-swap-hold" target version saved rc
  mkdir "$evidence" "$hold"
  M6_EVIDENCE_ROOT="$evidence" \
    M6_RUNNER_FIXTURE="$fixture" \
    M6_RUNNER_GATE_HOLD_DIR="$hold" \
    M6_RUNNER_GATE_HOLD_STAGE=canonical-between-gates \
    bash "$runner" duplicate-event >/dev/null 2>&1 &
  runner_pid=$!
  "$root/scenarios/scripts/wait-condition.sh" \
    'canonical gate pins target between schema and secret scans' 15 0.02 test -f "$hold/canonical-between-gates.ready"
  target="$(readlink "$evidence/duplicate-event")"
  version="$evidence/$target"
  saved="$version.saved"
  mv "$version" "$saved"
  mkdir "$version"
  touch "$version/unverified-competitor"
  touch "$hold/canonical-between-gates.release"
  set +e
  wait "$runner_pid"
  rc=$?
  set -e
  runner_pid=
  test "$rc" -ne 0
  test ! -e "$evidence/duplicate-event"
  test -f "$version/unverified-competitor"
  rm -rf "$version"
  mv "$saved" "$version"
  test "$(find "$version" -maxdepth 1 -type f | wc -l | tr -d ' ')" -eq 9
}

real_mode_ignores_hooks() {
  local evidence="$tmp/real-mode" hold="$tmp/real-mode-hold" rc
  mkdir "$evidence" "$hold"
  M6_EVIDENCE_ROOT="$evidence" \
    M6_RUNNER_FIXTURE="$fixture" \
    M6_RUNNER_EXECUTION_MODE=real \
    M6_RUNNER_HOLD_STAGE_DIR="$hold" \
    M6_RUNNER_FINALIZE_HOLD_DIR="$hold" \
    M6_RUNNER_PUBLISH_HOLD_DIR="$hold" \
    M6_RUNNER_PUBLISH_HOLD_STAGE=parent-opened \
    M6_RUNNER_GATE_HOLD_DIR="$hold" \
    M6_RUNNER_GATE_HOLD_STAGE=canonical-between-gates \
    M6_RUNNER_RECOVERY_OUTPUT_MODE=top-extra \
    bash "$runner" duplicate-event >/dev/null 2>&1 &
  runner_pid=$!
  "$root/scenarios/scripts/wait-condition.sh" \
    'real mode rejects inherited test holds and exits' 15 0.02 bash -c '! kill -0 "$1" 2>/dev/null' _ "$runner_pid"
  set +e
  wait "$runner_pid"
  rc=$?
  set -e
  runner_pid=
  test "$rc" -ne 0
  test ! -e "$hold/after-finalizer.ready"
  test ! -e "$hold/finalizer-entered.ready"
  test ! -e "$hold/parent-opened.ready"
  test ! -e "$hold/canonical-between-gates.ready"
  attempt="$(only_attempt "$evidence")"
  jq -e '
    .result=="FAIL" and
    (.failed_assertions|index("runner_test_hook_forbidden"))!=null
  ' "$attempt/result.json" >/dev/null
}

nonfixture_ignores_hooks() {
  local evidence="$tmp/nonfixture" hold="$tmp/nonfixture-hold" attempt rc
  mkdir "$evidence" "$hold"
  M6_EVIDENCE_ROOT="$evidence" \
    M6_RUNNER_HOLD_STAGE_DIR="$hold" \
    M6_RUNNER_FINALIZE_HOLD_DIR="$hold" \
    M6_RUNNER_PUBLISH_HOLD_DIR="$hold" \
    M6_RUNNER_PUBLISH_HOLD_STAGE=parent-opened \
    M6_RUNNER_GATE_HOLD_DIR="$hold" \
    M6_RUNNER_GATE_HOLD_STAGE=canonical-between-gates \
    bash "$runner" duplicate-event >/dev/null 2>&1 &
  runner_pid=$!
  "$root/scenarios/scripts/wait-condition.sh" \
    'nonfixture runner rejects inherited test holds and exits' 15 0.02 \
    bash -c '! kill -0 "$1" 2>/dev/null' _ "$runner_pid"
  set +e
  wait "$runner_pid"
  rc=$?
  set -e
  runner_pid=
  test "$rc" -ne 0
  test -z "$(find "$hold" -mindepth 1 -print -quit)"
  attempt="$(only_attempt "$evidence")"
  jq -e '
    .result=="FAIL" and
    (.failed_assertions|index("runner_test_hook_forbidden"))!=null and
    (.failed_assertions|index("runner_fixture_missing"))!=null
  ' "$attempt/result.json" >/dev/null
}

recovery_tamper() {
  local mode evidence attempt rc
  for mode in \
    top-extra external-extra command-shell command-auth command-path \
    success-exit-mismatch status-mismatch cleanup-mismatch
  do
    evidence="$tmp/recovery-$mode"
    mkdir "$evidence"
    set +e
    M6_EVIDENCE_ROOT="$evidence" \
      M6_RUNNER_FIXTURE="$fixture" \
      M6_RUNNER_RECOVERY_OUTPUT_MODE="$mode" \
      bash "$runner" duplicate-event >/dev/null 2>&1
    rc=$?
    set -e
    test "$rc" -ne 0
    attempt="$(only_attempt "$evidence")"
    jq -e '
      .result=="FAIL" and
      (.failed_assertions|index("runner_recovery_failure"))!=null and
      (.failed_assertions|index("cleanup"))!=null and
      .cleanup_failures==1 and
      .cleanup_actions==[{"name":"dispatch-owned-recovery-output","success":false,"finished_at":.cleanup_actions[0].finished_at}]
    ' "$attempt/result.json" >/dev/null
    jq -e '
      .cleanup_failures==1 and .commands==[] and
      .cleanup_actions[0].name=="dispatch-owned-recovery-output" and
      .cleanup_actions[0].success==false
    ' "$attempt/recovery-actions.json" >/dev/null
    bash "$root/tests/contracts/evidence-contract.sh" "$attempt" >/dev/null
  done
}

case "${1:-all}" in
  pre-uuid) pre_uuid_signal ;;
  reentrant) reentrant_signal ;;
  canonical-swap) canonical_target_swap ;;
  real-mode) real_mode_ignores_hooks ;;
  nonfixture) nonfixture_ignores_hooks ;;
  recovery-tamper) recovery_tamper ;;
  all)
    pre_uuid_signal
    reentrant_signal
    canonical_target_swap
    real_mode_ignores_hooks
    nonfixture_ignores_hooks
    recovery_tamper
    ;;
  *) echo 'unknown round3 contract selection' >&2;exit 64 ;;
esac

printf 'M6 Task 3 fix round 3 runner contract passed: %s\n' "${1:-all}"
