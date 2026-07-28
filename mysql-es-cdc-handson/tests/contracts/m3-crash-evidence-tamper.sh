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

cp -R evidence/m3/m3-after-es-before-offset "$tmp/es-record"
sed -i.bak 's/"product_id":"2301"/"product_id":"9999"/' "$tmp/es-record/topic-records.txt"
rm "$tmp/es-record/topic-records.txt.bak"
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
