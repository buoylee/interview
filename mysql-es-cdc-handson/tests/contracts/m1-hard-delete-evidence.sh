#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
source tests/contracts/lib-m1-task3-fixtures.sh

test -f scenarios/definitions/m1-hard-delete.json

jq -e '
  . == {
    scenario_id:"m1-hard-delete",
    product_id:1301,
    fault:"delete revision, inventory, and product rows in one direct SQL transaction",
    direct_sql_fault_injection:true,
    normal_business_path:false,
    source_product:{
      id:1301,
      sku:"M1-1301",
      name:"Delete Keyboard",
      description:"hard-delete observation",
      category_id:10,
      price_cents:100,
      status:"ACTIVE"
    },
    target_deadline_seconds:60,
    expected_observation:"Adapter DELETE behavior is measured, not assumed",
    final_consistency_claim:false
  }
' scenarios/definitions/m1-hard-delete.json >/dev/null

fixture=$(mktemp -d "${TMPDIR:-/tmp}/m1-hard-delete-evidence.XXXXXX")
trap 'rm -rf "$fixture"' EXIT

container_id="cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
java_identity="50|444444"
accepted_regressions=0

record_accepted_delete_regression() {
  local description="$1"
  bash scenarios/scripts/derive-m1-hard-delete-result.sh "$fixture" >"$fixture/result.json"
  if bash scenarios/scripts/assert-m1-hard-delete-evidence.sh "$fixture" >/dev/null 2>&1; then
    echo "hard-delete evidence accepted $description" >&2
    accepted_regressions=$((accepted_regressions + 1))
  fi
}
m1_task3_write_common_setup \
  "$fixture" m1-hard-delete 1301 M1-1301 "Delete Keyboard" "hard-delete observation"
m1_task3_write_mapping_proofs "$fixture" "$container_id" "$java_identity"

printf '%s\n' \
  '{"direct_sql_fault_injection":true,"normal_business_path":false,"transaction":"START TRANSACTION; DELETE FROM product_search_revision WHERE product_id = 1301; DELETE FROM inventory WHERE product_id = 1301; DELETE FROM products WHERE id = 1301; COMMIT;","started_at":"2026-07-26T15:00:02.000Z","committed_at":"2026-07-26T15:00:03.000Z"}' \
  >"$fixture/direct-sql.json"
printf '%s\n' \
  '{"product_id":1301,"product_row_count":0,"revision_row_count":0,"inventory_row_count":0,"captured_at":"2026-07-26T15:00:04.000Z"}' \
  >"$fixture/mysql-absence-snapshot.json"
printf '%s\n' \
  '{"_index":"products_adapter_v1","_id":"1301","found":false}' \
  >"$fixture/es-snapshot.json"
printf '%s\n' \
  '{"deadline_seconds":60,"deadline_reached":false,"observation_completed":true,"completed_at":"2026-07-26T15:00:05.000Z"}' \
  >"$fixture/target-observation.json"

bash scenarios/scripts/derive-m1-hard-delete-result.sh "$fixture" >"$fixture/result.json"
bash scenarios/scripts/assert-m1-hard-delete-evidence.sh "$fixture"
jq -e '
  .result == "OBSERVED_DELETE_PROPAGATION" and
  .direct_sql_fault_injection == true and
  .normal_business_path == false and
  .source_rows_absent == true and
  .mapping_continuity_verified == true and
  .final_consistency_claim == false
' "$fixture/result.json" >/dev/null

# Still-present target is an observed gap only after the bounded deadline.
cp "$fixture/es-initial-snapshot.json" "$fixture/es-snapshot.json"
jq '.deadline_reached = true | .completed_at = "2026-07-26T15:01:04.000Z"' \
  "$fixture/target-observation.json" >"$fixture/target-observation.tmp"
mv "$fixture/target-observation.tmp" "$fixture/target-observation.json"
bash scenarios/scripts/derive-m1-hard-delete-result.sh "$fixture" >"$fixture/result.json"
bash scenarios/scripts/assert-m1-hard-delete-evidence.sh "$fixture"
jq -e '.result == "OBSERVED_DELETE_GAP" and .final_consistency_claim == false' \
  "$fixture/result.json" >/dev/null

jq '.deadline_reached = false' "$fixture/target-observation.json" \
  >"$fixture/target-observation.tmp"
mv "$fixture/target-observation.tmp" "$fixture/target-observation.json"
bash scenarios/scripts/derive-m1-hard-delete-result.sh "$fixture" >"$fixture/result.json"
if bash scenarios/scripts/assert-m1-hard-delete-evidence.sh "$fixture" >/dev/null 2>&1; then
  echo "hard-delete evidence accepted a gap before the bounded target deadline" >&2
  exit 1
fi

test -x scenarios/scripts/run-m1-hard-delete.sh

jq '.deadline_reached = true' "$fixture/target-observation.json" \
  >"$fixture/target-observation.tmp"
mv "$fixture/target-observation.tmp" "$fixture/target-observation.json"
cp "$fixture/direct-sql.json" "$fixture/direct-sql-time.valid.json"
jq '.started_at = "2026-07-26 15:00:02.000Z"' \
  "$fixture/direct-sql-time.valid.json" >"$fixture/direct-sql.json"
record_accepted_delete_regression "a non-RFC3339 timestamp"
jq '.started_at = "2026-02-30T15:00:02.000Z"' \
  "$fixture/direct-sql-time.valid.json" >"$fixture/direct-sql.json"
record_accepted_delete_regression "an invalid calendar timestamp"
jq '.committed_at = .started_at' \
  "$fixture/direct-sql-time.valid.json" >"$fixture/direct-sql.json"
record_accepted_delete_regression "equal causal timestamps"
jq '.committed_at = "2026-07-26T14:59:59.999Z"' \
  "$fixture/direct-sql-time.valid.json" >"$fixture/direct-sql.json"
record_accepted_delete_regression "a commit timestamp before SQL start"
mv "$fixture/direct-sql-time.valid.json" "$fixture/direct-sql.json"

cp "$fixture/mysql-absence-snapshot.json" "$fixture/mysql-absence-snapshot.valid.json"
jq '.product_row_count = 1' "$fixture/mysql-absence-snapshot.valid.json" \
  >"$fixture/mysql-absence-snapshot.json"
bash scenarios/scripts/derive-m1-hard-delete-result.sh "$fixture" >"$fixture/result.json"
if bash scenarios/scripts/assert-m1-hard-delete-evidence.sh "$fixture" >/dev/null 2>&1; then
  echo "hard-delete evidence accepted source rows that were not absent" >&2
  exit 1
fi

test "$accepted_regressions" -eq 0
mv "$fixture/mysql-absence-snapshot.valid.json" "$fixture/mysql-absence-snapshot.json"

cp "$fixture/direct-sql.json" "$fixture/direct-sql.valid.json"
jq '.normal_business_path = true' "$fixture/direct-sql.valid.json" >"$fixture/direct-sql.json"
bash scenarios/scripts/derive-m1-hard-delete-result.sh "$fixture" >"$fixture/result.json"
if bash scenarios/scripts/assert-m1-hard-delete-evidence.sh "$fixture" >/dev/null 2>&1; then
  echo "hard-delete evidence accepted a mislabeled normal business path" >&2
  exit 1
fi
mv "$fixture/direct-sql.valid.json" "$fixture/direct-sql.json"

cp "$fixture/current-run-mapping-proof.json" "$fixture/current-run-mapping-proof.valid.json"
jq '.post_behavior.java_identity = "51|555555"' \
  "$fixture/current-run-mapping-proof.valid.json" >"$fixture/current-run-mapping-proof.json"
bash scenarios/scripts/derive-m1-hard-delete-result.sh "$fixture" >"$fixture/result.json"
if bash scenarios/scripts/assert-m1-hard-delete-evidence.sh "$fixture" >/dev/null 2>&1; then
  echo "hard-delete evidence accepted mapping/process discontinuity" >&2
  exit 1
fi
mv "$fixture/current-run-mapping-proof.valid.json" "$fixture/current-run-mapping-proof.json"

mv "$fixture/direct-sql.json" "$fixture/direct-sql.missing.json"
if bash scenarios/scripts/assert-m1-hard-delete-evidence.sh "$fixture" >/dev/null 2>&1; then
  echo "hard-delete evidence accepted missing direct-SQL evidence" >&2
  exit 1
fi
