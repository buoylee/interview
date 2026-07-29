#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib/common.sh";target="${1:-}";base="${ELASTICSEARCH_URL:-http://127.0.0.1:9200}";index="${ELASTICSEARCH_INDEX:-products_write}";tmp="$(mktemp -d)";trap 'rm -rf "$tmp"' EXIT
pit="$(curl -fsS -X POST "$base/$index/_pit?keep_alive=1m"|jq -er .id)";search_after=null;printf '[]' >"$tmp/hits"
while true;do body="$(jq -cn --arg pit "$pit" --argjson after "$search_after" '{size:500,pit:{id:$pit,keep_alive:"1m"},sort:[{"product_id":"asc"},{"_shard_doc":"asc"}],query:{match_all:{}}}+if ($after==null) then {} else {search_after:$after} end')";response="$(curl -fsS -H 'Content-Type: application/json' -d "$body" "$base/_search")";count="$(jq '.hits.hits|length'<<<"$response")";jq -s '.[0]+.[1]' "$tmp/hits" <(jq '[.hits.hits[]|{product_id:._source.product_id,version:._version,source:._source}]'<<<"$response") >"$tmp/next";mv "$tmp/next" "$tmp/hits";((count>0))||break;search_after="$(jq -c '.hits.hits[-1].sort'<<<"$response")";done
curl -fsS -X DELETE -H 'Content-Type: application/json' -d "{\"id\":\"$pit\"}" "$base/_pit" >/dev/null
output="$(jq -n --arg index "$index" --slurpfile docs "$tmp/hits" '{schema_version:1,consistency:"ELASTICSEARCH_PIT",index:$index,documents:($docs[0]|sort_by(.product_id))}')";if test -n "$target";then printf '%s\n' "$output"|atomic_json "$target";else jq -S .<<<"$output";fi
