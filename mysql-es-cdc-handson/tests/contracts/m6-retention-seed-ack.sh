#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)";contract="$root/tests/contracts/m6-retention-gap.sh";assertion="$root/scenarios/scripts/assert-retention-seed.sh";tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

test -x "$assertion" || { echo 'missing runtime seed ACK/record assertion' >&2;exit 1; }
! grep -Eq '"revision":"?0"?' "$contract" || { echo 'retention seed revision must be positive' >&2;exit 1; }
grep -Fq 'seed-ack.json' "$contract";grep -Fq 'seed-record.json' "$contract"

ack="$tmp/ack.json";record="$tmp/record.json"
printf '%s\n' '{"topic":"product-search-revisions","partition":0,"offset":7}' >"$ack"
printf '%s\n' '{"database":"product_catalog","table":"product_search_revision","isDdl":false,"type":"UPDATE","data":[{"product_id":"900001","revision":"1","active":"1"}]}' >"$record"
bash "$assertion" "$ack" "$record"

reject(){ local name="$1" ack_json="$2" record_json="$3";printf '%s\n' "$ack_json" >"$tmp/$name-ack.json";printf '%s\n' "$record_json" >"$tmp/$name-record.json";if bash "$assertion" "$tmp/$name-ack.json" "$tmp/$name-record.json" >/dev/null 2>&1;then echo "seed tamper accepted: $name" >&2;exit 1;fi; }
good_record="$(cat "$record")"
reject missing-topic '{"partition":0,"offset":7}' "$good_record"
reject wrong-topic '{"topic":"other","partition":0,"offset":7}' "$good_record"
reject wrong-partition '{"topic":"product-search-revisions","partition":1,"offset":7}' "$good_record"
reject nonnumeric-offset '{"topic":"product-search-revisions","partition":0,"offset":"7"}' "$good_record"
reject wrong-payload '{"topic":"product-search-revisions","partition":0,"offset":7}' '{"database":"other","table":"product_search_revision","isDdl":false,"type":"UPDATE","data":[{"product_id":"900001","revision":"1","active":"1"}]}'
reject wrong-row '{"topic":"product-search-revisions","partition":0,"offset":7}' '{"database":"product_catalog","table":"product_search_revision","isDdl":false,"type":"UPDATE","data":[{"product_id":"900002","revision":"2","active":"1"}]}'

ack_line="$(grep -n 'assert-retention-seed.sh' "$contract"|cut -d: -f1)";apply_line="$(grep -n 'fault-retention.sh.*apply' "$contract"|head -1|cut -d: -f1)"
test -n "$ack_line";test -n "$apply_line";test "$ack_line" -lt "$apply_line" || { echo 'seed proof occurs after first destructive apply' >&2;exit 1; }

printf 'M6 retention raw ACK and consumed-record tamper contract passed\n'
