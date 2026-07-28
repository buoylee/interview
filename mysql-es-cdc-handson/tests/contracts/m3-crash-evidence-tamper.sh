#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
validator=scenarios/scripts/assert-m3-crash-evidence.sh
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

expect_rejected() {
  local name="$1" dir="$2"
  if bash "$validator" "$dir" >/dev/null 2>&1; then
    echo "validator accepted tamper: $name" >&2
    exit 1
  fi
}

copy_fixture() {
  local scenario="$1" name="$2"
  cp -R "evidence/m3/$scenario" "$tmp/$name"
}

mutate_json() {
  local file="$1" filter="$2" replacement
  replacement="$(mktemp)"
  jq "$filter" "$file" >"$replacement"
  mv "$replacement" "$file"
}

mutate_topic_product_id() {
  local dir="$1" partition offset prefix replacement line payload
  partition="$(jq -r .partition "$dir/record.json")"
  offset="$(jq -r .offset "$dir/record.json")"
  prefix="Partition:${partition}"$'\t'"Offset:${offset}"$'\t'
  replacement="$(mktemp)"
  while IFS= read -r line; do
    if [[ "$line" == "$prefix"* ]]; then
      payload="${line#"$prefix"}"
      printf '%s%s\n' "$prefix" "$(jq -c '.data[0].product_id="9999"' <<<"$payload")" >>"$replacement"
    else
      printf '%s\n' "$line" >>"$replacement"
    fi
  done <"$dir/topic-records.txt"
  mv "$replacement" "$dir/topic-records.txt"
}

cp -R evidence/m3/m3-after-es-before-offset "$tmp/es-record"
mutate_topic_product_id "$tmp/es-record"
expect_rejected mismatched-record-payload "$tmp/es-record"

cp -R evidence/m3/m3-after-dlq-before-offset "$tmp/dlq-id"
jq '.[0].event_id="forged"' "$tmp/dlq-id/dlq-after-crash.json" >"$tmp/row"
mv "$tmp/row" "$tmp/dlq-id/dlq-after-crash.json"
expect_rejected mismatched-dlq-event-id "$tmp/dlq-id"

cp -R evidence/m3/m3-after-es-before-offset "$tmp/forged-result"
rm "$tmp/forged-result/es-before-restart.json"
expect_rejected missing-raw-with-forged-result "$tmp/forged-result"

cp -R evidence/m3/m3-after-es-before-offset "$tmp/bad-time"
jq '.finished_at="not-a-timestamp"' "$tmp/bad-time/process-crashed.json" >"$tmp/row"
mv "$tmp/row" "$tmp/bad-time/process-crashed.json"
expect_rejected malformed-timestamp "$tmp/bad-time"

cp -R evidence/m3/m3-after-es-before-offset "$tmp/bad-http"
printf '%s\n' '{"transport_exit":0,"http_status":500,"json_valid":true,"body":{"status":"UP"}}' >"$tmp/bad-http/consumer-ready.json"
expect_rejected terminal-http-500 "$tmp/bad-http"

cp -R evidence/m3/m3-after-es-before-offset "$tmp/unknown"
jq '.scenario="unknown"' "$tmp/unknown/definition.json" >"$tmp/row"
mv "$tmp/row" "$tmp/unknown/definition.json"
expect_rejected unknown-scenario "$tmp/unknown"

# A derived result must be bound to raw evidence, not merely internally consistent.
copy_fixture m3-after-es-before-offset result-seqno
mutate_json "$tmp/result-seqno/result.json" '.es_before_price_cents += 1'
expect_rejected result-price-not-bound-to-raw "$tmp/result-seqno"

copy_fixture m3-after-dlq-before-offset result-attempts
mutate_json "$tmp/result-attempts/result.json" '.event_id="forged"'
expect_rejected result-event-id-not-bound-to-raw "$tmp/result-attempts"

# Scenario semantics are fixed even if definition, armed observation, and result agree.
copy_fixture m3-after-es-before-offset semantic-point
mutate_json "$tmp/semantic-point/definition.json" '.failpoint="AFTER_DLQ_PUBLISH"'
mutate_json "$tmp/semantic-point/armed.json" 'with_entries(.key="AFTER_DLQ_PUBLISH")'
mutate_json "$tmp/semantic-point/result.json" '.failpoint="AFTER_DLQ_PUBLISH"'
expect_rejected scenario-semantic-failpoint-lock "$tmp/semantic-point"

copy_fixture m3-after-es-before-offset semantic-hits
mutate_json "$tmp/semantic-hits/definition.json" '.hits=2'
mutate_json "$tmp/semantic-hits/armed.json" '.AFTER_ES_BULK_SUCCESS=2'
expect_rejected scenario-semantic-hits-lock "$tmp/semantic-hits"

# Every readiness checkpoint is mandatory and must be a valid current-run health response.
copy_fixture m3-after-es-before-offset restarted-readiness-500
mutate_json "$tmp/restarted-readiness-500/consumer-restarted-ready.json" '.http_status=500'
expect_rejected restarted-readiness-http-500 "$tmp/restarted-readiness-500"

copy_fixture m3-after-dlq-before-offset bad-mapping-readiness-malformed
mutate_json "$tmp/bad-mapping-readiness-malformed/consumer-bad-mapping-ready.json" '.json_valid=false | .raw_body="{"'
expect_rejected bad-mapping-readiness-malformed "$tmp/bad-mapping-readiness-malformed"

copy_fixture m3-after-dlq-before-offset restarted-readiness-missing
rm "$tmp/restarted-readiness-missing/consumer-restarted-ready.json"
expect_rejected restarted-readiness-missing "$tmp/restarted-readiness-missing"

# A permanent ES document 404 never satisfies readiness; only its exact target
# document shape is retryable, while index-not-found is terminal.
if (
  source scenarios/scripts/lib-m3-crash.sh
  observation="$(mktemp)"
  trap 'rm -f "$observation"' EXIT
  jq -n '{transport_exit:0,http_status:404,json_valid:true,raw_body:(
    {"_index":"products_v2","_id":"2301","found":false}|tojson)}' >"$observation"
  is_es_revision_ready_observation 2301 2 "$observation"
); then
  echo "validator accepted permanent Elasticsearch document 404 as ready" >&2
  exit 1
fi
(
  source scenarios/scripts/lib-m3-crash.sh
  observation="$(mktemp)"
  trap 'rm -f "$observation"' EXIT
  jq -n '{transport_exit:0,http_status:404,json_valid:true,raw_body:(
    {error:{type:"index_not_found_exception"},status:404}|tojson)}' >"$observation"
  if is_es_revision_pending_observation 2301 "$observation"; then
    echo "validator accepted index-not-found as retryable" >&2
    exit 1
  fi
)

(
  source scenarios/scripts/lib-m3-crash.sh
  observation="$(mktemp)"
  trap 'rm -f "$observation"' EXIT
  jq -n '{transport_exit:0,http_status:404,json_valid:true,raw_body:(
    {"_index":"other_index","_id":"2301","found":false}|tojson)}' >"$observation"
  if is_es_revision_pending_observation 2301 "$observation"; then
    echo "validator accepted wrong-index document 404 as retryable" >&2
    exit 1
  fi
)
