#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
action="${1:-}";point="${2:-}";require_action "$action"
case "$point" in BEFORE_ES_BULK|BEFORE_KAFKA_OFFSET_COMMIT) ;;*) echo 'unsupported deterministic process failpoint' >&2;exit 64;;esac
api="${CONSUMER_API:-http://127.0.0.1:8082/internal/failpoints}"
container_id(){ "${compose[@]}" ps -a -q search-sync-consumer; }
exit_86(){ local id;id="$(container_id)";test -n "$id" && test "$(docker inspect -f '{{.State.Status}}:{{.State.ExitCode}}' "$id")" = exited:86; }
process_status(){
  local id docker_state remaining=null
  id="$(container_id)";docker_state=missing
  test -z "$id" || docker_state="$(docker inspect -f '{{.State.Status}}:{{.State.ExitCode}}' "$id")"
  if response="$(bounded_curl "$api" 2>/dev/null)";then remaining="$(jq -c --arg p "$point" '.[$p] // null' <<<"$response")";fi
  jq -n --arg failpoint "$point" --arg docker_state "$docker_state" --argjson remaining "$remaining" \
    '{failpoint:$failpoint,remaining:$remaining,consumer_state:$docker_state,exact_exit_86:($docker_state=="exited:86")}'
}
case "$action" in
 apply)
   register_cleanup "bash scenarios/scripts/fault-process.sh remove $point"
   bounded_curl -X POST "$api/$point/arm?hits=1" | jq -e --arg p "$point" '.[$p]==1' >/dev/null
   if (( $# > 2 ));then
     set +e;"${@:3}";trigger_rc=$?;set -e
     "$wait_condition" "search-sync-consumer exact failpoint exit 86" 60 0.2 bash -c \
       'id="$(docker compose -f "$1" ps -a -q search-sync-consumer)";test -n "$id" && test "$(docker inspect -f "{{.State.Status}}:{{.State.ExitCode}}" "$id")" = exited:86' _ "$project_root/infra/compose.yaml"
     process_status|jq -e --argjson trigger_exit "$trigger_rc" 'select(.exact_exit_86==true)|{failpoint,remaining,consumer_state,exact_exit_86,trigger_exit:$trigger_exit}'
   else process_status;fi;;
 remove) bounded_curl -X DELETE "$api" | jq -e 'all(.[];.==0)';;
 status) process_status;;
esac
