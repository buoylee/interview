#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
action="${1:-}";fault="${2:-}";require_action "$action"
case "$fault" in
  kafka-timeout) proxy=kafka;stream=upstream;;
  elasticsearch-timeout) proxy=elasticsearch;stream=downstream;;
  canal-mysql-timeout) proxy=canal-mysql;stream=downstream;;
  *) echo 'unknown network fault' >&2;exit 64;;
esac
api="${TOXIPROXY_API:-http://127.0.0.1:8474}";name="scenario-timeout"
status(){ local code body;body="$(mktemp)";code="$(curl -sS --max-time 10 -o "$body" -w '%{http_code}' "$api/proxies/$proxy/toxics/$name")";if test "$code" = 200;then jq -e --arg proxy "$proxy" --arg stream "$stream" '.name=="scenario-timeout" and .type=="timeout" and .stream==$stream and .attributes.timeout==0|{active:true,proxy:$proxy,toxic:.}' "$body";elif test "$code" = 404;then jq -n --arg proxy "$proxy" '{active:false,proxy:$proxy}';else rm -f "$body";exit 1;fi;rm -f "$body";}
case "$action" in
 apply) register_cleanup "bash scenarios/scripts/fault-network.sh remove $fault";if status|jq -e '.active' >/dev/null;then status;else bounded_curl -X POST "$api/proxies/$proxy/toxics" -H 'Content-Type: application/json' -d "{\"name\":\"scenario-timeout\",\"type\":\"timeout\",\"stream\":\"$stream\",\"toxicity\":1.0,\"attributes\":{\"timeout\":0}}" >/dev/null;status;fi;;
 remove) code="$(curl -sS --max-time 10 -o /dev/null -w '%{http_code}' -X DELETE "$api/proxies/$proxy/toxics/$name")";case "$code" in 204|404) status;;*) exit 1;;esac;;
 status) status;;esac
