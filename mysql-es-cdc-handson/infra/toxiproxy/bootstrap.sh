#!/usr/bin/env bash
set -euo pipefail
api="${TOXIPROXY_API:-http://127.0.0.1:8474}"
expected='[{"name":"canal-mysql","listen":"0.0.0.0:8668","upstream":"mysql:3306"},{"name":"elasticsearch","listen":"0.0.0.0:8666","upstream":"elasticsearch:9200"},{"name":"kafka","listen":"0.0.0.0:8667","upstream":"kafka:9094"}]'
actual="$(curl -fsS --max-time 10 "$api/proxies" | jq -c '[to_entries[].value|{name,listen:(.listen|sub("^\\[::\\]:";"0.0.0.0:")),upstream}]|sort_by(.name)')"
test "$actual" = "$expected" || { echo 'Toxiproxy routing differs from locked dependency boundaries' >&2;exit 1; }
curl -fsS --max-time 10 "$api/version" >/dev/null
jq -n --argjson proxies "$actual" '{healthy:true,proxies:$proxies}'
