#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)";scenario_id="${1:-}";catalog="$root/scenarios/catalog.json"
count="$(jq --arg id "$scenario_id" '[.scenarios[]|select(.scenario_id==$id)]|length' "$catalog")"
test "$count" -eq 1||{ echo 'scenario ID must occur exactly once in locked catalog' >&2;exit 64;}
row="$(jq -cer --arg id "$scenario_id" '.scenarios[]|select(.scenario_id==$id)' "$catalog")"
evidence_root="${M6_EVIDENCE_ROOT:-$root/evidence}";mkdir -p "$evidence_root/.locks" "$evidence_root/.runs/$scenario_id"
evidence_root="$(cd "$evidence_root"&&pwd -P)";canonical="$evidence_root/$scenario_id"
test ! -L "$canonical"||case "$(readlink "$canonical")" in .runs/"$scenario_id"/*) ;;*) echo 'canonical evidence symlink escapes owned versions' >&2;exit 74;;esac
lock="$evidence_root/.locks/$scenario_id";mkdir "$lock" 2>/dev/null||{ echo 'scenario already owned by another run' >&2;exit 75;}
run_id="$(uuidgen|tr '[:upper:]' '[:lower:]')";token="$run_id";started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)";private="$(mktemp -d "$evidence_root/.tmp.$scenario_id.XXXXXX")";bundle="$private/bundle";mkdir "$bundle";printf '%s\n' "$token" >"$private/owner-token";published=false;cleanup_done=false
cleanup(){
  rc=$?;trap - EXIT INT TERM
  if ! $cleanup_done;then cleanup_done=true;fi
  rm -rf "$private";rmdir "$lock" 2>/dev/null||true
  exit "$rc"
}
trap cleanup EXIT
fixture="${M6_RUNNER_FIXTURE:-}";test -n "$fixture"&&test -f "$fixture"||{ echo 'Task 3 requires a controlled fixture until scenario executors exist' >&2;exit 69;}
observations="$private/observations.json";jq --arg run "$run_id" '.verification.run_id=$run|.watermark_run_id=$run' "$fixture" >"$observations"
jq -e 'def safe_commands:
  type=="array" and all(.[];
    (keys_unsorted|all(.=="sequence" or .=="kind" or .=="target" or .=="method" or .=="path" or .=="body_sha256" or .=="fixture_path" or .=="fixture_sha256" or .=="started_at" or .=="finished_at" or .=="exit_code")) and
    (.sequence|type)=="number" and (.kind|IN("HTTP","SQL_FIXTURE","CONTROL")) and (.target|type)=="string" and (.method|type)=="string" and (.path|type)=="string" and (.path|startswith("/")) and (.path|contains("..")|not) and (.exit_code|type)=="number" and
    ((has("body_sha256")|not) or (.body_sha256|test("^[a-f0-9]{64}$"))) and
    ((has("fixture_path")|not) or ((.fixture_path|startswith("/"))|not) and (.fixture_path|contains("..")|not)) and
    ((has("fixture_sha256")|not) or (.fixture_sha256|test("^[a-f0-9]{64}$"))));
  type=="object" and (.commands|safe_commands) and (.recovery_commands|safe_commands)' "$observations" >/dev/null
jq -n --arg scenario "$scenario_id" --arg run "$run_id" --arg head "$(git -C "$root" rev-parse HEAD)" '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,project_head:$head}' >"$bundle/manifest.json"
jq -n --arg scenario "$scenario_id" --arg run "$run_id" --slurpfile o "$observations" '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,commands:$o[0].commands}' >"$bundle/input-commands.json"
jq -n --arg scenario "$scenario_id" --arg run "$run_id" --argjson fault "$(jq -c .fault <<<"$row")" '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,declared_fault:$fault,cleanup_registered_before_fault:true}' >"$bundle/fault.json"
cleanup_plan="$private/cleanup-plan.json";jq -n --arg scenario "$scenario_id" --arg run "$run_id" '{scenario_id:$scenario,runner_run_id:$run,registered:true}' >"$cleanup_plan"
finish_run(){
 local recovery_rc terminal_rc result_rc version link
 if bash "$root/scenarios/scripts/dispatch-recovery.sh" "$scenario_id" "$private" "$token" >/dev/null;then recovery_rc=0;else recovery_rc=$?;fi
 if test "$recovery_rc" -ne 0;then jq '.cleanup_actions += [{name:"dispatch-owned-recovery",success:false,finished_at:(now|todateiso8601)}]' "$observations" >"$private/o";mv "$private/o" "$observations";fi
 jq -n --arg scenario "$scenario_id" --arg run "$run_id" '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,consistency:"FIXTURE_TRANSACTIONAL_CAPTURE",documents:[]}' >"$bundle/mysql-snapshot.json"
 cp "$bundle/mysql-snapshot.json" "$bundle/es-snapshot.json";cp "$bundle/mysql-snapshot.json" "$bundle/kafka-offsets.json"
 jq -n --arg scenario "$scenario_id" --arg run "$run_id" --slurpfile o "$observations" '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,observations:$o[0]}' >"$bundle/differences.json"
 jq -n --arg scenario "$scenario_id" --arg run "$run_id" --slurpfile o "$observations" '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,rebuild_required_observed_before_rebuild:$o[0].rebuild_required_before_rebuild,commands:$o[0].recovery_commands,cleanup_actions:$o[0].cleanup_actions,cleanup_failures:([$o[0].cleanup_actions[]|select(.success!=true)]|length)}' >"$bundle/recovery-actions.json"
 terminal="$private/terminal.json";printf '%s\n' "$row" >"$private/catalog-row.json";if bash "$root/scenarios/scripts/assert-terminal.sh" "$private/catalog-row.json" "$observations" "$terminal";then terminal_rc=0;else terminal_rc=$?;fi
 if bash "$root/scenarios/scripts/write-result.sh" "$scenario_id" "$run_id" "$started_at" "$observations" "$bundle/recovery-actions.json" "$bundle/result.json";then result_rc=0;else result_rc=$?;fi
 if ! bash "$root/tests/contracts/evidence-contract.sh" "$bundle" >/dev/null;then return 76;fi
 if ! bash "$root/tests/contracts/no-evidence-secrets.sh" "$bundle"/*.json >/dev/null;then return 77;fi
 version="$evidence_root/.runs/$scenario_id/$token";mv "$bundle" "$version";link="$evidence_root/.link.$scenario_id.$token";ln -s ".runs/$scenario_id/$token" "$link"
 test ! -d "$canonical"||test -L "$canonical"||{ echo 'refusing non-atomic replacement of canonical directory' >&2;return 74;}
 test "${M6_RUNNER_FAIL_STAGE:-}" != before-replace||return 86
 mv -fh "$link" "$canonical";published=true;if ! bash "$root/tests/contracts/evidence-contract.sh" "$canonical" >/dev/null;then return 78;fi;cleanup_done=true
 test "$terminal_rc" -eq 0&&test "$result_rc" -eq 0&&test "$recovery_rc" -eq 0
}
handle_signal(){ local code="$1";trap - INT TERM;jq --arg failure "signal_$code" '.runner_failures=((.runner_failures//[])+[$failure])|.recovery_action_observed=false' "$observations" >"$private/signal-observations";mv "$private/signal-observations" "$observations";set +e;finish_run;exit "$code"; }
trap 'handle_signal 130' INT;trap 'handle_signal 143' TERM
bash "$root/scenarios/scripts/dispatch-fault.sh" "$scenario_id" "$private" "$token" >/dev/null
if test -n "${M6_RUNNER_HOLD_FILE:-}";then touch "$M6_RUNNER_HOLD_FILE.ready";while test ! -f "$M6_RUNNER_HOLD_FILE.release";do :;done;fi
finish_run
