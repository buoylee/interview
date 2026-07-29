#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
checker=scenarios/scripts/assert-gap-precondition.sh
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

jq -n '{target:"mysql-binlog",journal:"binlog.000009",position:431,retained_files:["binlog.000010"],recorded_present:false,canal_missing_position_observed:true}' >"$tmp/mysql-pass.json"
jq -n '{target:"kafka",topic:"product-search-revisions",partition:2,committed_offset:40,beginning_offset:41}' >"$tmp/kafka-pass.json"
bash "$checker" mysql-binlog "$tmp/mysql-pass.json" >/dev/null
bash "$checker" kafka "$tmp/kafka-pass.json" >/dev/null

expect_rejected() {
  local name="$1" target="$2" fixture="$3"
  if bash "$checker" "$target" "$fixture" >"$tmp/$name.out" 2>&1; then
    echo "gap precondition accepted $name" >&2
    exit 1
  fi
}

jq '.recorded_present=true' "$tmp/mysql-pass.json" >"$tmp/mysql-present.json"
jq '.canal_missing_position_observed=false' "$tmp/mysql-pass.json" >"$tmp/mysql-no-error.json"
jq '.beginning_offset=.committed_offset' "$tmp/kafka-pass.json" >"$tmp/kafka-equal.json"
jq '.partition=null' "$tmp/kafka-pass.json" >"$tmp/kafka-no-partition.json"
expect_rejected mysql-present mysql-binlog "$tmp/mysql-present.json"
expect_rejected mysql-no-error mysql-binlog "$tmp/mysql-no-error.json"
expect_rejected kafka-equal kafka "$tmp/kafka-equal.json"
expect_rejected kafka-no-partition kafka "$tmp/kafka-no-partition.json"
expect_rejected cross-target kafka "$tmp/mysql-pass.json"

echo 'M6 gap endpoints require concrete non-replayability evidence'
