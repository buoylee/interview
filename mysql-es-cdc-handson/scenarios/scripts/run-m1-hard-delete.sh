#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
source scenarios/scripts/lib-adapter.sh
source scenarios/scripts/lib-m1-log-window.sh
source scenarios/scripts/lib-m1-mapping-proof.sh
source scenarios/scripts/lib-m1-task3.sh

scenario="m1-hard-delete"
product_id=1301
out="evidence/m1/$scenario"
pre_mapping_proof="$out/pre-behavior-mapping-proof.json"
final_mapping_proof="$out/current-run-mapping-proof.json"
rm -rf "$out"
mkdir -p "$out"
cp "scenarios/definitions/$scenario.json" "$out/input-commands.json"

poll_until 60 product_api_is_ready
m1_task3_reset_fixture_and_index "$product_id" "$out/index-create.json"
M1_MAPPING_PROOF_OUTPUT="$pre_mapping_proof" \
  bash tests/contracts/m1-adapter.sh --live >"$out/current-run-topology-proof.txt"

curl -fsS --connect-timeout 2 --max-time 10 -X POST \
  http://127.0.0.1:8081/api/products \
  -H 'Content-Type: application/json' \
  -d '{"id":1301,"sku":"M1-1301","name":"Delete Keyboard","description":"hard-delete observation","categoryId":10,"priceCents":100}' \
  | jq -e 'select(. == {"productId":1301,"revision":1})' \
  >"$out/create-response.json"
m1_task3_capture_initial "$product_id" \
  "$out/mysql-initial-snapshot.json" "$out/es-initial-snapshot.json"

sql_started_at=$(m1_task3_utc_millis)
mysql_adapter <<'SQL'
START TRANSACTION;
DELETE FROM product_search_revision WHERE product_id = 1301;
DELETE FROM inventory WHERE product_id = 1301;
DELETE FROM products WHERE id = 1301;
COMMIT;
SQL
sql_committed_at=$(m1_task3_utc_millis)
jq -n --arg started "$sql_started_at" --arg committed "$sql_committed_at" '
  {
    direct_sql_fault_injection:true,
    normal_business_path:false,
    transaction:"START TRANSACTION; DELETE FROM product_search_revision WHERE product_id = 1301; DELETE FROM inventory WHERE product_id = 1301; DELETE FROM products WHERE id = 1301; COMMIT;",
    started_at:$started,
    committed_at:$committed
  }
' >"$out/direct-sql.json"

read -r product_count revision_count inventory_count < <(
  mysql_adapter -e "SELECT
    (SELECT COUNT(*) FROM products WHERE id = 1301),
    (SELECT COUNT(*) FROM product_search_revision WHERE product_id = 1301),
    (SELECT COUNT(*) FROM inventory WHERE product_id = 1301)"
)
case "$product_count$revision_count$inventory_count" in
  *[!0-9]*) exit 1 ;;
esac
jq -n \
  --argjson product "$product_count" --argjson revision "$revision_count" \
  --argjson inventory "$inventory_count" \
  --arg captured "$(m1_task3_utc_millis)" '
  {
    product_id:1301,product_row_count:$product,
    revision_row_count:$revision,inventory_row_count:$inventory,
    captured_at:$captured
  }
' >"$out/mysql-absence-snapshot.json"
jq -e '
  .product_row_count == 0 and .revision_row_count == 0 and
  .inventory_row_count == 0
' "$out/mysql-absence-snapshot.json" >/dev/null

deadline_reached=false
if ! poll_until 60 es_document_is_absent "$product_id"; then
  deadline_reached=true
fi
completed_at=$(m1_task3_utc_millis)
m1_task3_capture_es "$product_id" "$out/es-snapshot.json"
jq -n --argjson deadline_reached "$deadline_reached" --arg completed "$completed_at" '
  {
    deadline_seconds:60,deadline_reached:$deadline_reached,
    observation_completed:true,completed_at:$completed
  }
' >"$out/target-observation.json"
m1_task3_capture_adapter_log "$out/adapter.log"
scenarios/scripts/verify-m1-topology.sh \
  --mapping-continuity "$pre_mapping_proof" "$final_mapping_proof"

bash scenarios/scripts/derive-m1-hard-delete-result.sh "$out" >"$out/result.json"
bash scenarios/scripts/assert-m1-hard-delete-evidence.sh "$out"
