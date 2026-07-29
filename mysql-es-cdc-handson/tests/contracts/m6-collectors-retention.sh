#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)";tmp="$(mktemp -d)";trap 'rm -rf "$tmp"' EXIT
export MYSQL_PWD="${MYSQL_PWD:?MYSQL_PWD required}" MYSQL_USER=root SCENARIO_STATE_DIR="$tmp/state" SCENARIO_CLEANUP_FILE="$tmp/cleanup"

bash "$root/scenarios/scripts/capture-mysql.sh" "$tmp/mysql.json"
jq -e '.consistency=="REPEATABLE_READ_CONSISTENT_SNAPSHOT" and (.documents|length)>0 and ([.documents[].product_id]==([.documents[].product_id]|sort)) and all(.documents[];has("revision") and has("active") and has("updated_at"))' "$tmp/mysql.json" >/dev/null
bash "$root/scenarios/scripts/capture-elasticsearch.sh" "$tmp/es.json"
jq -e '.consistency=="ELASTICSEARCH_PIT" and ([.documents[].product_id]==([.documents[].product_id]|sort)) and all(.documents[];has("version") and (.source|has("source_revision")))' "$tmp/es.json" >/dev/null
bash "$root/scenarios/scripts/capture-kafka.sh" "$tmp/kafka.json"
jq -e '([.beginning[].partition]==[0,1,2]) and ([.end[].partition]==[0,1,2]) and ([.primary[].partition]==[0,1,2]) and (.shadow_and_barrier|type)=="array"' "$tmp/kafka.json" >/dev/null
bash "$root/scenarios/scripts/capture-manifest.sh" "$tmp/manifest.json"
jq -e '.git.commit|test("^[a-f0-9]{40}$")' "$tmp/manifest.json" >/dev/null
jq -e '.checked_in_config_hashes|length==6 and .==sort_by(.path) and all(.[];.sha256|test("^[a-f0-9]{64}$"))' "$tmp/manifest.json" >/dev/null
bash "$root/tests/contracts/no-evidence-secrets.sh" "$tmp/manifest.json" >/dev/null
test -z "$(find "$tmp" -name '.tmp.*' -print -quit)"

printf 'M6 real non-destructive collectors contract passed\n'
