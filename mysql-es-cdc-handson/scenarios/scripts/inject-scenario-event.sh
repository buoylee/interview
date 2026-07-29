#!/usr/bin/env bash
set -euo pipefail

partition="${1:?partition required}"
payload="${2:?payload required}"
case "$partition" in 0|1|2) ;; *) echo 'partition must be 0, 1, or 2' >&2; exit 64 ;; esac
normalized_payload="$(jq -c '.data |= map({product_id,revision,active})' <<<"$payload")"
jq -e '
  type=="object" and .database=="product_catalog" and
  .table=="product_search_revision" and .isDdl==false and
  (.type=="INSERT" or .type=="UPDATE" or .type=="DELETE") and
  (.data|type=="array" and length>0) and
  all(.data[]; (keys|sort)==["active","product_id","revision"])
' <<<"$normalized_payload" >/dev/null

request="$(jq -cn --argjson partition "$partition" --arg payload "$normalized_payload" \
  '{topic:"product-search-revisions",partition:$partition,payload:$payload}')"
ack="$(docker compose -f infra/compose.yaml exec -T consistency-verifier \
  curl --fail-with-body --silent --show-error --max-time 10 \
    -X POST http://127.0.0.1:8083/internal/lab/scenario-events \
    -H 'Content-Type: application/json' -d "$request")"
jq -e --argjson partition "$partition" '
  .topic=="product-search-revisions" and .partition==$partition and
  (.offset|type=="number" and .>=0)
' <<<"$ack" >/dev/null
jq -n --argjson ack "$ack" --argjson normalized_payload "$normalized_payload" \
  --arg request_sha256 "$(printf '%s' "$request" | shasum -a 256 | awk '{print $1}')" \
  --arg payload_sha256 "$(printf '%s' "$normalized_payload" | shasum -a 256 | awk '{print $1}')" \
  '{primitive:"lab-scenario-event-v1",request_sha256:$request_sha256,payload_sha256:$payload_sha256,
    normalized_payload:$normalized_payload,
    broker_ack:$ack,key_is_null:true}'
