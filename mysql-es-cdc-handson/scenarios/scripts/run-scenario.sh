#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
scenario_id="${1:-}"
catalog="$root/scenarios/catalog.json"
count="$(jq --arg id "$scenario_id" '[.scenarios[]|select(.scenario_id==$id)]|length' "$catalog")"
test "$count" -eq 1 || { echo 'scenario ID must occur exactly once in locked catalog' >&2; exit 64; }
row="$(jq -cer --arg id "$scenario_id" '.scenarios[]|select(.scenario_id==$id)' "$catalog")"

die_path() { echo "unsafe evidence path: $1" >&2; exit 74; }
owned_dir() {
  local path="$1" parent="$2" physical expected
  test ! -L "$path" || die_path "$path"
  if test ! -e "$path"; then mkdir "$path" 2>/dev/null || die_path "$path"; fi
  test -d "$path" && test ! -L "$path" || die_path "$path"
  physical="$(cd "$path" && pwd -P)";expected="$parent/$(basename "$path")"
  test "$physical" = "$expected" || die_path "$path"
}

provisional_uuid() {
  local first second third fourth last
  first=$(((RANDOM << 17) ^ (RANDOM << 2) ^ ($$ & 0x1ffff)))
  second=$((RANDOM & 0xffff))
  third=$((0x4000 | (RANDOM & 0x0fff)))
  fourth=$((0x8000 | (RANDOM & 0x3fff)))
  last=$(((RANDOM << 30) | (RANDOM << 15) | RANDOM))
  printf '%08x-%04x-%04x-%04x-%012x\n' "$first" "$second" "$third" "$fourth" "$last"
}

test_hooks_allowed() {
  test "${M6_RUNNER_EXECUTION_MODE:-fixture}" = fixture &&
    test -n "${M6_RUNNER_FIXTURE:-}" && test -f "${M6_RUNNER_FIXTURE:-}"
}

setup_runner() {
  local generated_run_id
  evidence_root="${M6_EVIDENCE_ROOT:-$root/evidence}"
  test -d "$evidence_root" && test ! -L "$evidence_root" || die_path "$evidence_root"
  evidence_root="$(cd "$evidence_root" && pwd -P)"
  owned_dir "$evidence_root/.runs" "$evidence_root"
  owned_dir "$evidence_root/.locks" "$evidence_root"
  owned_dir "$evidence_root/.runs/$scenario_id" "$evidence_root/.runs"
  runs_dir="$evidence_root/.runs/$scenario_id"
  locks_dir="$evidence_root/.locks"
  canonical="$evidence_root/$scenario_id"

  if test -L "$canonical"; then
    target="$(readlink "$canonical")"
    case "$target" in .runs/"$scenario_id"/*) ;; *) die_path "$canonical" ;; esac
    resolved="$(cd "$(dirname "$canonical")" && cd "$(dirname "$target")" && pwd -P)/$(basename "$target")"
    case "$resolved" in "$runs_dir"/*) ;; *) die_path "$canonical" ;; esac
    test -d "$resolved" && test ! -L "$resolved" || die_path "$canonical"
  elif test -e "$canonical"; then
    die_path "$canonical"
  fi

  run_id="$(provisional_uuid)";token="$run_id"
  started_at=1970-01-01T00:00:00Z
  private=;bundle=;observations=;version="$runs_dir/$token"
  cleanup_done=false;finalize_state=idle;finalize_rc=1;recovery_required=false
  signal_exit_code=0;pending_signal_failure=;test_hook_forbidden=false
  lock="$locks_dir/$scenario_id"
  test ! -L "$lock" || die_path "$lock"
  mkdir "$lock" 2>/dev/null || { echo 'scenario already owned by another run' >&2; exit 75; }

  # From this point onward every signal has enough safe state to create one
  # fail-closed attempt and release this run's lock.
  trap cleanup EXIT
  trap 'handle_signal 130' INT
  trap 'handle_signal 143' TERM

  unset M6_RUNNER_INTERNAL_TEST_HOOKS
  if test_hooks_allowed; then
    export M6_RUNNER_INTERNAL_TEST_HOOKS=fixture-fail-v1
  elif test -n "${M6_RUNNER_HOLD_STAGE_DIR:-}${M6_RUNNER_FINALIZE_HOLD_DIR:-}${M6_RUNNER_PUBLISH_HOLD_DIR:-}${M6_RUNNER_GATE_HOLD_DIR:-}"; then
    test_hook_forbidden=true
  fi

  generated_run_id="$(uuidgen | tr '[:upper:]' '[:lower:]')"
  if jq -en --arg value "$generated_run_id" '$value|test("^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")' >/dev/null; then
    run_id="$generated_run_id";token="$run_id";version="$runs_dir/$token"
  else
    fail_and_finalize 64 runner_generated_run_id_invalid
  fi
  started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  ensure_private
}

ensure_private() {
  test -z "$private" || return 0
  private="$(mktemp -d "$evidence_root/.tmp.$scenario_id.XXXXXX")"
  test ! -L "$private" && test "$(cd "$private/.." && pwd -P)" = "$evidence_root" || die_path "$private"
  bundle="$private/bundle";mkdir "$bundle"
  observations="$private/observations.json"
}

cleanup() {
  local rc=$?;trap - EXIT INT TERM
  if test -n "${private:-}" && test -d "$private" && test ! -L "$private" && test "$(cd "$private/.." && pwd -P)" = "$evidence_root"; then rm -rf "$private"; fi
  if test -n "${lock:-}" && test -d "$lock" && test ! -L "$lock" && test "$(cd "$lock/.." && pwd -P)" = "$locks_dir"; then rmdir "$lock" 2>/dev/null || true; fi
  exit "$rc"
}

fallback_observations() {
  ensure_private
  jq -n --arg run "$run_id" --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '{
    consistency_preconditions:[{name:"runner-finalizer",satisfied:false,observed_at:$now}],source_watermark:0,
    target_watermarks:{mysql_revision:0,elasticsearch_revision:0,passed:false},watermark_run_id:$run,applied_offsets:{"0":0,"1":0,"2":0},
    scenario_lag_satisfied:false,product_unresolved_dlq_count:0,record_unresolved_dlq_count:0,
    verification:{run_id:$run,status:"INCONCLUSIVE",conclusive:false,stable:false,exact_managed_field_diff_count:0,version_metadata_diff_count:0,observed_at:$now},
    exact_diff_count:0,tombstone_mismatch_count:0,canal_position_recovery:null,observed_intermediate_states:["DEGRADED"],observed_pipeline_state:"DEGRADED",
    recovery_action_observed:false,rebuild_required_before_rebuild:false,commands:[],recovery_commands:[],cleanup_actions:[],runner_failures:[]
  }' >"$observations"
}

add_failure() {
  local failure="$1" tmp
  ensure_private;tmp="$private/observations.next"
  test -s "$observations" && jq -e 'type=="object"' "$observations" >/dev/null 2>&1 || fallback_observations
  jq --arg failure "$failure" '.runner_failures=((.runner_failures//[])+[$failure]|unique)' "$observations" >"$tmp" && mv "$tmp" "$observations"
}

safe_commands() {
  bash "$root/scenarios/scripts/validate-runner-json.sh" commands "$observations"
}

publish_attempt() {
  local result="$1" canonical_status gate_rc previous_token= previous_target=
  owned_dir "$runs_dir" "$evidence_root/.runs"
  python3 "$root/scenarios/scripts/publish-evidence.py" version \
    "$evidence_root" "$bundle" "$runs_dir" "$token" || return $?
  python3 "$root/scenarios/scripts/publish-evidence.py" gate \
    "$evidence_root" "$scenario_id" "$token" version \
    "$root/tests/contracts/evidence-contract.sh" \
    "$root/tests/contracts/no-evidence-secrets.sh" || return $?
  test "${M6_RUNNER_FAIL_STAGE:-}" != before-replace || return 86
  if test "$result" = PASS && test -L "$canonical"; then
    previous_target="$(readlink "$canonical")"
    previous_token="${previous_target##*/}"
    canonical_status="$(python3 "$root/scenarios/scripts/publish-evidence.py" replace \
      "$evidence_root" "$scenario_id" "$token" "$previous_token")" || return $?
  else
    canonical_status="$(python3 "$root/scenarios/scripts/publish-evidence.py" canonical \
      "$evidence_root" "$scenario_id" "$token")" || return $?
  fi
  if python3 "$root/scenarios/scripts/publish-evidence.py" gate \
    "$evidence_root" "$scenario_id" "$token" canonical \
    "$root/tests/contracts/evidence-contract.sh" \
    "$root/tests/contracts/no-evidence-secrets.sh"; then
    gate_rc=0
  else
    gate_rc=$?
  fi
  if test "$gate_rc" -ne 0; then
    if test "$canonical_status" = published; then
      python3 "$root/scenarios/scripts/publish-evidence.py" remove \
        "$evidence_root" "$scenario_id" "$token" >/dev/null 2>&1 || true
    elif test "$canonical_status" = replaced; then
      python3 "$root/scenarios/scripts/publish-evidence.py" replace \
        "$evidence_root" "$scenario_id" "$previous_token" "$token" >/dev/null 2>&1 || true
    fi
    return "$gate_rc"
  fi
}

finalize_once() {
  local terminal_rc=1 result_rc=1 recovery_rc=0 result=FAIL terminal recovery_output external_clear=false
  test -s "$observations" || fallback_observations
  jq --arg run "$run_id" '.watermark_run_id=$run | .verification.run_id=$run' "$observations" >"$private/observations.run-bound"
  mv "$private/observations.run-bound" "$observations"
  if $test_hook_forbidden; then add_failure runner_test_hook_forbidden;test_hook_forbidden=false;fi
  consume_pending_signal
  if $recovery_required; then
    recovery_output="$private/recovery-output.json"
    if bash "$root/scenarios/scripts/dispatch-recovery.sh" "$scenario_id" "$private" "$token" >"$recovery_output"; then
      recovery_rc=0
    else
      recovery_rc=$?
    fi
    test ! -e "$private/fault-status.json" && external_clear=true
    if ! bash "$root/scenarios/scripts/validate-runner-json.sh" recovery \
      "$scenario_id" "$token" "$external_clear" "$recovery_rc" "$recovery_output"; then
      recovery_rc=73
      jq -n --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '{
        recovery_action_observed:false,
        cleanup_actions:[{name:"dispatch-owned-recovery-output",success:false,finished_at:$now}],
        commands:[]
      }' >"$recovery_output"
    fi
    jq --slurpfile recovery "$recovery_output" '
      .recovery_action_observed=$recovery[0].recovery_action_observed |
      .cleanup_actions=$recovery[0].cleanup_actions |
      .recovery_commands=$recovery[0].commands
    ' "$observations" >"$private/observations.recovered" &&
      mv "$private/observations.recovered" "$observations"
    if test "$recovery_rc" -ne 0 || test "$external_clear" != true; then add_failure runner_recovery_failure;fi
  fi
  jq -n --arg scenario "$scenario_id" --arg run "$run_id" --arg head "$(git -C "$root" rev-parse HEAD)" '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,project_head:$head}' >"$bundle/manifest.json"
  if test -f "$private/command-intent.json" && jq -e '.scenario_id and (.commands|type)=="array" and (.executions|type)=="array"' "$private/command-intent.json" >/dev/null 2>&1; then
    jq -n --arg scenario "$scenario_id" --arg run "$run_id" --slurpfile intent "$private/command-intent.json" \
      '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,intents:$intent[0].commands,executions:$intent[0].executions}' >"$bundle/input-commands.json"
  else
    jq -n --arg scenario "$scenario_id" --arg run "$run_id" '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,intents:[],executions:[]}' >"$bundle/input-commands.json"
  fi
  jq -n --arg scenario "$scenario_id" --arg run "$run_id" --argjson fault "$(jq -c .fault <<<"$row")" '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,declared_fault:$fault,cleanup_registered_before_fault:true}' >"$bundle/fault.json"
  jq -n --arg scenario "$scenario_id" --arg run "$run_id" '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,consistency:"FAIL_CLOSED_CAPTURE",documents:[]}' >"$bundle/mysql-snapshot.json"
  cp "$bundle/mysql-snapshot.json" "$bundle/es-snapshot.json";cp "$bundle/mysql-snapshot.json" "$bundle/kafka-offsets.json"
  jq -n --arg scenario "$scenario_id" --arg run "$run_id" --slurpfile o "$observations" \
    '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,observations:($o[0]|.commands=[]|.canal_position_recovery=(.canal_position_recovery//null))}' >"$bundle/differences.json"
  jq -n --arg scenario "$scenario_id" --arg run "$run_id" --slurpfile o "$observations" '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,rebuild_required_observed_before_rebuild:($o[0].rebuild_required_before_rebuild//false),commands:($o[0].recovery_commands//[]),cleanup_actions:($o[0].cleanup_actions//[]),cleanup_failures:([$o[0].cleanup_actions[]?|select(.success!=true)]|length)}' >"$bundle/recovery-actions.json"
  printf '%s\n' "$row" >"$private/catalog-row.json";terminal="$private/terminal.json"
  bash "$root/scenarios/scripts/assert-terminal.sh" "$private/catalog-row.json" "$observations" "$terminal" >/dev/null 2>&1 && terminal_rc=0 || true
  bash "$root/scenarios/scripts/write-result.sh" "$scenario_id" "$run_id" "$started_at" "$observations" "$bundle/recovery-actions.json" "$bundle/result.json" >/dev/null 2>&1 && result_rc=0 || true
  test -f "$bundle/result.json" || return 76
  result="$(jq -r .result "$bundle/result.json")"
  test "$result" = FAIL || { add_failure runner_result_not_fail_closed;return 76; }
  bash "$root/tests/contracts/evidence-contract.sh" "$bundle" >/dev/null || return 76
  bash "$root/tests/contracts/no-evidence-secrets.sh" "$bundle"/*.json >/dev/null || return 77
  publish_attempt "$result" || return $?
  cleanup_done=true
  test "$terminal_rc" -eq 0 && test "$result_rc" -eq 0 && test "$recovery_rc" -eq 0
}

consume_pending_signal() {
  local failure="${pending_signal_failure:-}"
  test -n "$failure" || return 0
  pending_signal_failure=
  add_failure "$failure"
}

finalizer_hold() {
  local hold_dir="${M6_RUNNER_FINALIZE_HOLD_DIR:-}"
  test -n "$hold_dir" || return 0
  test_hooks_allowed || { test_hook_forbidden=true;return 0; }
  test -d "$hold_dir" && test ! -L "$hold_dir" || { add_failure runner_hold_path_unsafe;return 0; }
  touch "$hold_dir/finalizer-entered.ready"
  while test ! -f "$hold_dir/finalizer-entered.release"; do :; done
}

finalize() {
  local rc
  case "$finalize_state" in
    done) return "$finalize_rc" ;;
    finalizing) return 0 ;;
  esac
  finalize_state=finalizing
  ensure_private
  finalizer_hold
  consume_pending_signal
  finalize_once
  rc=$?
  consume_pending_signal
  finalize_rc="$rc"
  finalize_state=done
  return "$finalize_rc"
}

fail_and_finalize() {
  local code="$1" failure="$2"
  add_failure "$failure"
  set +e
  finalize
  set -e
  exit "$code"
}

handle_signal() {
  local code="$1"
  signal_exit_code="$code"
  pending_signal_failure="signal_$code"
  case "$finalize_state" in
    finalizing) return 0 ;;
    done) exit "$signal_exit_code" ;;
  esac
  set +e
  finalize
  set -e
  exit "$signal_exit_code"
}

hold_stage() {
  local stage="$1" hold_dir="${M6_RUNNER_HOLD_STAGE_DIR:-}"
  test -n "$hold_dir" || return 0
  test_hooks_allowed || { test_hook_forbidden=true;return 0; }
  test -d "$hold_dir" && test ! -L "$hold_dir" || fail_and_finalize 74 runner_hold_path_unsafe
  touch "$hold_dir/$stage.ready"
  while test ! -f "$hold_dir/$stage.release"; do :; done
}

setup_runner
hold_stage after-finalizer
requested_run_id="${M6_RUNNER_RUN_ID:-}"
if test -n "$requested_run_id"; then
  if jq -en --arg value "$requested_run_id" '$value|test("^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")' >/dev/null; then
    run_id="$requested_run_id";token="$run_id";version="$runs_dir/$token"
  else
    printf '%s\n' "$token" >"$private/owner-token"
    fail_and_finalize 64 runner_run_id_invalid
  fi
fi
printf '%s\n' "$token" >"$private/owner-token"
if test -e "$version" || test -L "$version"; then
  add_failure runner_version_exists
  while :; do
    run_id="$(uuidgen | tr '[:upper:]' '[:lower:]')"
    token="$run_id";version="$runs_dir/$token"
    test ! -e "$version" && test ! -L "$version" && break
  done
  printf '%s\n' "$token" >"$private/owner-token"
  fail_and_finalize 74 runner_version_exists
fi

if test "${M6_RUNNER_EXECUTION_MODE:-fixture}" = real; then
  test -z "${M6_RUNNER_FIXTURE:-}" || fail_and_finalize 64 runner_real_mode_rejects_fixture
  jq -n --arg scenario "$scenario_id" --arg token "$token" \
    '{scenario_id:$scenario,owner_token:$token,registered:true}' >"$private/cleanup-intent.json"
  if ! bash "$root/scenarios/scripts/prepare-m6-run.sh" "$private"; then fail_and_finalize 69 runner_real_setup_failure; fi
  bash "$root/scenarios/scripts/persist-m6-command-intent.sh" "$scenario_id" "$token" "$private/command-intent.json" || fail_and_finalize 71 runner_command_intent_failure
  recovery_required=true
  fault_started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  set +e
  bash "$root/scenarios/scripts/dispatch-fault.sh" "$scenario_id" "$private" "$token" >"$private/fault-dispatch-output.json"
  fault_rc=$?
  set -e
  fault_finished="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  bash "$root/scenarios/scripts/complete-m6-command-intent.sh" "$private/command-intent.json" mutate "$fault_started" "$fault_finished" "$fault_rc" || fail_and_finalize 71 runner_command_intent_failure
  if test "$fault_rc" -ne 0; then
    fail_and_finalize 73 runner_dispatch_failure
  fi
  if ! bash "$root/scenarios/scripts/execute-case.sh" "$scenario_id" intermediate "$private" "$token"; then
    fail_and_finalize 73 runner_intermediate_failure
  fi
  recovery_output="$private/recovery-output.json"
  if ! bash "$root/scenarios/scripts/dispatch-recovery.sh" "$scenario_id" "$private" "$token" >"$recovery_output"; then
    fail_and_finalize 73 runner_recovery_failure
  fi
  recovery_required=false
  if ! bash "$root/scenarios/scripts/collect-m6-observations.sh" "$scenario_id" "$run_id" "$private" "$observations"; then
    fail_and_finalize 76 runner_terminal_observation_failure
  fi
  if ! bash "$root/scenarios/scripts/build-m6-real-bundle.sh" "$scenario_id" "$run_id" "$started_at" "$private" "$observations" "$recovery_output" "$bundle"; then
    fail_and_finalize 76 runner_real_bundle_failure
  fi
  bash "$root/tests/contracts/evidence-contract.sh" "$bundle" || fail_and_finalize 76 runner_evidence_contract_failure
  bash "$root/tests/contracts/no-evidence-secrets.sh" "$bundle"/*.json >/dev/null || fail_and_finalize 77 runner_secret_gate_failure
  publish_attempt PASS || fail_and_finalize 76 runner_publication_failure
  cleanup_done=true;finalize_state=done;finalize_rc=0
  exit 0
fi

fixture="${M6_RUNNER_FIXTURE:-}"
test -n "$fixture" && test -f "$fixture" || fail_and_finalize 69 runner_fixture_missing
if test "${M6_RUNNER_FAIL_STAGE:-}" = parse || ! jq -e 'type=="object"' "$fixture" >/dev/null 2>&1; then fail_and_finalize 70 runner_parse_failure;fi
cp "$fixture" "$observations"
tmp_observations="$private/observations.fixture"
jq '.recovery_action_observed=false|.cleanup_actions=[]|.recovery_commands=[]' "$observations" >"$tmp_observations"
mv "$tmp_observations" "$observations"
add_failure fixture_mode_forbids_pass
if test "${M6_RUNNER_FAIL_STAGE:-}" = command || ! safe_commands; then fallback_observations;fail_and_finalize 71 runner_command_failure;fi
if test "${M6_RUNNER_FAIL_STAGE:-}" = manifest; then fail_and_finalize 72 runner_manifest_failure;fi
if test "${M6_RUNNER_FAIL_STAGE:-}" = dispatch; then fail_and_finalize 73 runner_dispatch_failure;fi
jq -n --arg scenario "$scenario_id" --arg token "$token" \
  '{scenario_id:$scenario,owner_token:$token,registered:true}' >"$private/cleanup-intent.json"
bash "$root/scenarios/scripts/persist-m6-command-intent.sh" "$scenario_id" "$token" "$private/command-intent.json" || fail_and_finalize 71 runner_command_intent_failure
recovery_required=true
set +e
fault_started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
bash "$root/scenarios/scripts/dispatch-fault.sh" "$scenario_id" "$private" "$token" >"$private/fault-dispatch-output.json"
dispatch_rc=$?
set -e
fault_finished="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  bash "$root/scenarios/scripts/complete-m6-command-intent.sh" "$private/command-intent.json" mutate "$fault_started" "$fault_finished" "$dispatch_rc" || fail_and_finalize 71 runner_command_intent_failure
test "$dispatch_rc" -eq 0 || fail_and_finalize 73 runner_dispatch_failure
if test -n "${M6_RUNNER_HOLD_FILE:-}";then touch "$M6_RUNNER_HOLD_FILE.ready";while test ! -f "$M6_RUNNER_HOLD_FILE.release";do :;done;fi
set +e
finalize
final_rc=$?
set -e
test "$signal_exit_code" -eq 0 || exit "$signal_exit_code"
exit "$final_rc"
