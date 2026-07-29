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

lock="$locks_dir/$scenario_id"
test ! -L "$lock" || die_path "$lock"
mkdir "$lock" 2>/dev/null || { echo 'scenario already owned by another run' >&2; exit 75; }
run_id="${M6_RUNNER_RUN_ID:-$(uuidgen | tr '[:upper:]' '[:lower:]')}"
jq -en --arg value "$run_id" '$value|test("^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")' >/dev/null || { rmdir "$lock"; exit 64; }
token="$run_id";started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
version="$runs_dir/$token"
test ! -L "$version" && test ! -e "$version" || { rmdir "$lock"; die_path "$version"; }
private="$(mktemp -d "$evidence_root/.tmp.$scenario_id.XXXXXX")"
test ! -L "$private" && test "$(cd "$private/.." && pwd -P)" = "$evidence_root" || { rmdir "$lock"; die_path "$private"; }
bundle="$private/bundle";mkdir "$bundle";printf '%s\n' "$token" >"$private/owner-token"
observations="$private/observations.json";cleanup_done=false;finalized=false;fault_dispatched=false

cleanup() {
  local rc=$?;trap - EXIT INT TERM
  if test -d "$private" && test ! -L "$private" && test "$(cd "$private/.." && pwd -P)" = "$evidence_root"; then rm -rf "$private"; fi
  if test -d "$lock" && test ! -L "$lock" && test "$(cd "$lock/.." && pwd -P)" = "$locks_dir"; then rmdir "$lock" 2>/dev/null || true; fi
  exit "$rc"
}
trap cleanup EXIT

fallback_observations() {
  jq -n --arg run "$run_id" --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '{
    consistency_preconditions:[{name:"runner-finalizer",satisfied:false,observed_at:$now}],source_watermark:0,
    target_watermarks:{mysql_revision:0,elasticsearch_revision:0,passed:false},watermark_run_id:$run,applied_offsets:{"0":0,"1":0,"2":0},
    scenario_lag_satisfied:false,product_unresolved_dlq_count:0,record_unresolved_dlq_count:0,
    verification:{run_id:$run,status:"INCONCLUSIVE",conclusive:false,stable:false,exact_managed_field_diff_count:0,version_metadata_diff_count:0,observed_at:$now},
    exact_diff_count:0,tombstone_mismatch_count:0,observed_intermediate_states:["DEGRADED"],observed_pipeline_state:"DEGRADED",
    recovery_action_observed:false,rebuild_required_before_rebuild:false,commands:[],recovery_commands:[],cleanup_actions:[],runner_failures:[]
  }' >"$observations"
}

add_failure() {
  local failure="$1" tmp="$private/observations.next"
  test -s "$observations" && jq -e 'type=="object"' "$observations" >/dev/null 2>&1 || fallback_observations
  jq --arg failure "$failure" '.runner_failures=((.runner_failures//[])+[$failure]|unique)' "$observations" >"$tmp" && mv "$tmp" "$observations"
}

safe_commands() {
  jq -e 'def safe:
    type=="array" and all(.[];
      (keys_unsorted|all(.=="sequence" or .=="kind" or .=="target" or .=="method" or .=="path" or .=="body_sha256" or .=="fixture_path" or .=="fixture_sha256" or .=="started_at" or .=="finished_at" or .=="exit_code")) and
      (.sequence|type)=="number" and (.kind|IN("HTTP","SQL_FIXTURE","CONTROL")) and (.target|type)=="string" and
      (.method|type)=="string" and (.path|type)=="string" and (.path|startswith("/")) and (.path|contains("..")|not) and
      (.exit_code|type)=="number" and ((has("body_sha256")|not) or (.body_sha256|test("^[a-f0-9]{64}$"))) and
      ((has("fixture_path")|not) or (((.fixture_path|startswith("/"))|not) and (.fixture_path|contains("..")|not))) and
      ((has("fixture_sha256")|not) or (.fixture_sha256|test("^[a-f0-9]{64}$"))));
    type=="object" and (.commands|safe) and (.recovery_commands|safe)' "$observations" >/dev/null
}

publish_attempt() {
  local result="$1" link
  owned_dir "$runs_dir" "$evidence_root/.runs"
  test ! -L "$version" && test ! -e "$version" || die_path "$version"
  mv "$bundle" "$version"
  if test "$result" = FAIL && test -e "$canonical"; then return 0; fi
  if test "$result" = FAIL && test -L "$canonical"; then return 0; fi
  link="$evidence_root/.link.$scenario_id.$token";test ! -e "$link" && test ! -L "$link" || die_path "$link"
  ln -s ".runs/$scenario_id/$token" "$link"
  test "${M6_RUNNER_FAIL_STAGE:-}" != before-replace || { rm "$link"; return 86; }
  mv -fh "$link" "$canonical"
}

finalize() {
  local terminal_rc=1 result_rc=1 recovery_rc=0 result=FAIL terminal
  $finalized && return 1;finalized=true
  test -s "$observations" || fallback_observations
  if $fault_dispatched; then
    if ! bash "$root/scenarios/scripts/dispatch-recovery.sh" "$scenario_id" "$private" "$token" >/dev/null; then recovery_rc=$?;add_failure runner_recovery_failure;fi
  fi
  jq -n --arg scenario "$scenario_id" --arg run "$run_id" --arg head "$(git -C "$root" rev-parse HEAD)" '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,project_head:$head}' >"$bundle/manifest.json"
  jq -n --arg scenario "$scenario_id" --arg run "$run_id" --slurpfile o "$observations" '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,commands:($o[0].commands//[])}' >"$bundle/input-commands.json"
  jq -n --arg scenario "$scenario_id" --arg run "$run_id" --argjson fault "$(jq -c .fault <<<"$row")" '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,declared_fault:$fault,cleanup_registered_before_fault:true}' >"$bundle/fault.json"
  jq -n --arg scenario "$scenario_id" --arg run "$run_id" '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,consistency:"FAIL_CLOSED_CAPTURE",documents:[]}' >"$bundle/mysql-snapshot.json"
  cp "$bundle/mysql-snapshot.json" "$bundle/es-snapshot.json";cp "$bundle/mysql-snapshot.json" "$bundle/kafka-offsets.json"
  jq -n --arg scenario "$scenario_id" --arg run "$run_id" --slurpfile o "$observations" '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,observations:$o[0]}' >"$bundle/differences.json"
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

fail_and_finalize() { local code="$1" failure="$2";add_failure "$failure";set +e;finalize;set -e;exit "$code"; }
handle_signal() { local code="$1";trap - INT TERM;fail_and_finalize "$code" "signal_$code"; }
trap 'handle_signal 130' INT;trap 'handle_signal 143' TERM

fixture="${M6_RUNNER_FIXTURE:-}"
test -n "$fixture" && test -f "$fixture" || fail_and_finalize 69 runner_fixture_missing
if test "${M6_RUNNER_FAIL_STAGE:-}" = parse || ! jq -e 'type=="object"' "$fixture" >/dev/null 2>&1; then fail_and_finalize 70 runner_parse_failure;fi
cp "$fixture" "$observations"
add_failure fixture_mode_forbids_pass
if test "${M6_RUNNER_FAIL_STAGE:-}" = command || ! safe_commands; then fallback_observations;fail_and_finalize 71 runner_command_failure;fi
if test "${M6_RUNNER_FAIL_STAGE:-}" = manifest; then fail_and_finalize 72 runner_manifest_failure;fi
if test "${M6_RUNNER_FAIL_STAGE:-}" = dispatch; then fail_and_finalize 73 runner_dispatch_failure;fi
if ! bash "$root/scenarios/scripts/dispatch-fault.sh" "$scenario_id" "$private" "$token" >/dev/null; then fail_and_finalize 73 runner_dispatch_failure;fi
fault_dispatched=true
if test -n "${M6_RUNNER_HOLD_FILE:-}";then touch "$M6_RUNNER_HOLD_FILE.ready";while test ! -f "$M6_RUNNER_HOLD_FILE.release";do :;done;fi
finalize
