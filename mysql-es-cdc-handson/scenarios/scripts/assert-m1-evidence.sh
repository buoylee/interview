#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

out="${1:-evidence/m1/m1-basic}"
for required in \
  input-commands.json index-create.json create-response.json \
  mysql-insert-snapshot.json es-insert-snapshot.json update-response.json \
  mysql-snapshot.json es-snapshot.json adapter.log \
  current-run-mapping-proof.txt result.json
do
  test -s "$out/$required"
done

jq -e '.acknowledged == true and .index == "products_adapter_v1"' \
  "$out/index-create.json" >/dev/null
jq -e '. == {"productId":1101,"revision":1}' "$out/create-response.json" >/dev/null
jq -e '. == {"productId":1101,"revision":2}' "$out/update-response.json" >/dev/null

grep -Fq '## Start loading es mapping config ...' "$out/adapter.log"
grep -Fq '## ES mapping config loaded' "$out/adapter.log"
grep -Fxq -- \
  '- formal es8 products mapping: exact image file plus current-Java-run load evidence' \
  "$out/current-run-mapping-proof.txt"

expected_result=$(mktemp "${TMPDIR:-/tmp}/m1-derived-result.XXXXXX")
trap 'rm -f "$expected_result"' EXIT
bash scenarios/scripts/derive-m1-result.sh "$out" >"$expected_result"
diff -u <(jq -S . "$expected_result") <(jq -S . "$out/result.json")

jq -e '
  .result == "OBSERVED_INSERT_UPDATE_WITH_COMPUTED_FIELD_GAP" and
  .insert_observed == true and
  .update_observed == true and
  .non_computed_fields_match == true and
  .forbidden_fields_absent == true and
  .allowed_field_set_exact == true and
  .source_updated_at_non_null == true and
  .target_updated_at_is_null == true and
  .updated_at_matches_source == false and
  .final_consistency_claim == false
' "$out/result.json" >/dev/null
