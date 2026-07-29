#!/usr/bin/env bash
set -euo pipefail

usage(){ echo 'usage: wait-condition.sh DESCRIPTION TIMEOUT_SECONDS POLL_SECONDS COMMAND [ARG...]' >&2;exit 64; }
(( $# >= 4 )) || usage
description="$1";timeout_seconds="$2";poll_seconds="$3";shift 3
[[ "$timeout_seconds" =~ ^[0-9]+$ ]] && (( timeout_seconds >= 1 && timeout_seconds <= 1800 )) || usage
[[ "$poll_seconds" =~ ^(0|[1-9][0-9]*)([.][0-9]+)?$ ]] || usage
awk -v value="$poll_seconds" 'BEGIN{exit !(value>0 && value<=10)}' || usage

tmp="$(mktemp -d)";child_pid=;child_pgid=;attempt=0;last_exit_code=0;last_stdout=;last_stderr=
now_ms(){ python3 -c 'import time;print(time.monotonic_ns()//1000000)'; }
started_ms="$(now_ms)";deadline_ms=$((started_ms + timeout_seconds*1000))
sleep_bounded(){ local requested="$1" remaining_ms="$2";awk -v req="$requested" -v remaining="$remaining_ms" 'BEGIN{remaining=remaining/1000;print (req<remaining ? req : remaining)}'; }
terminate_tree(){
  test -z "$child_pid" && return
  kill -TERM -- "-$child_pgid" 2>/dev/null || true
  local grace_deadline=$(( $(now_ms)+500 )) now pause
  while kill -0 -- "-$child_pgid" 2>/dev/null;do now="$(now_ms)";((now<grace_deadline))||break;pause="$(sleep_bounded 0.05 $((grace_deadline-now)))";sleep "$pause";done
  kill -KILL -- "-$child_pgid" 2>/dev/null || true
  wait "$child_pid" 2>/dev/null || true
  child_pid=;child_pgid=
}
cleanup(){ terminate_tree;rm -rf "$tmp"; }
on_signal(){ local signal="$1" code="$2";cleanup;jq -cn --arg status SIGNAL --arg description "$description" --arg signal "$signal" --argjson attempts "$attempt" '{status:$status,description:$description,signal:$signal,attempts:$attempts}' >&2;trap - EXIT;exit "$code"; }
trap cleanup EXIT
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM

bounded(){ tail -c 2048 "$1" 2>/dev/null || true; }
diagnostic(){
  local now duration
  now="$(now_ms)";duration=$((now-started_ms))
  jq -cn --arg status TIMEOUT --arg description "$description" --argjson attempts "$attempt" \
    --argjson duration_ms "$duration" --argjson last_exit_code "$last_exit_code" \
    --arg last_stdout "$last_stdout" --arg last_stderr "$last_stderr" \
    '{status:$status,description:$description,attempts:$attempts,duration_ms:$duration_ms,last_exit_code:$last_exit_code,last_stdout:$last_stdout,last_stderr:$last_stderr}' >&2
}

while true; do
  attempt=$((attempt+1))
  : >"$tmp/stdout";: >"$tmp/stderr"
  "$(dirname "$0")/lib/exec-process-group.py" "$@" >"$tmp/stdout" 2>"$tmp/stderr" & child_pid=$!;child_pgid=$child_pid
  while kill -0 "$child_pid" 2>/dev/null; do
    now="$(now_ms)"
    if (( now >= deadline_ms )); then
      terminate_tree
      last_exit_code=124;last_stdout="$(bounded "$tmp/stdout")";last_stderr="$(bounded "$tmp/stderr")"
      diagnostic;exit 124
    fi
    sleep "$(sleep_bounded "$poll_seconds" $((deadline_ms-now)))"
  done
  set +e;wait "$child_pid";last_exit_code=$?;set -e;child_pid=
  last_stdout="$(bounded "$tmp/stdout")";last_stderr="$(bounded "$tmp/stderr")"
  if (( last_exit_code == 0 )); then printf '%s' "$last_stdout";test -z "$last_stdout" || printf '\n';exit 0;fi
  if (( $(now_ms) >= deadline_ms )); then diagnostic;exit 124;fi
done
