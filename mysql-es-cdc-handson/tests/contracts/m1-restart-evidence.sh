#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
source tests/contracts/lib-m1-task3-fixtures.sh

test -f scenarios/definitions/m1-restart.json

jq -e '
  . == {
    scenario_id:"m1-restart",
    product_id:1201,
    fault:"stop only canal-adapter while source revisions advance",
    recovery:"start the same container without deleting its state",
    source_product:{
      id:1201,
      sku:"M1-1201",
      name:"Restart Keyboard",
      description:"restart observation",
      category_id:10,
      price_cents:100,
      status:"ACTIVE"
    },
    mutations:[
      {operation:"change_price",price_cents:200,expected_revision:2},
      {operation:"replace_inventory",available_quantity:7,reserved_quantity:2,expected_revision:3}
    ],
    target_deadline_seconds:60,
    expected_observation:"document reaches the latest source value or evidence records the gap",
    final_consistency_claim:false
  }
' scenarios/definitions/m1-restart.json >/dev/null

fixture=$(mktemp -d "${TMPDIR:-/tmp}/m1-restart-evidence.XXXXXX")
trap 'rm -rf "$fixture"' EXIT

container_id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
before_identity="40|111111"
after_identity="41|222222"
m1_task3_write_common_setup \
  "$fixture" m1-restart 1201 M1-1201 "Restart Keyboard" "restart observation"
m1_task3_write_mapping_proofs "$fixture" "$container_id" "$after_identity"

jq -n --arg container "$container_id" --arg identity "$before_identity" '
  {container_id:$container,java_identity:$identity,captured_at:"2026-07-26T14:00:02Z"}
' >"$fixture/adapter-before-stop.json"
jq -n --arg container "$container_id" --arg identity "$before_identity" '
  {
    container_id:$container,stopped_java_identity:$identity,
    java_process_absent:true,captured_at:"2026-07-26T14:00:03Z"
  }
' >"$fixture/adapter-stopped.json"
printf '%s\n' '{"productId":1201,"revision":2}' >"$fixture/price-response.json"
printf '%s\n' '{"productId":1201,"revision":3}' >"$fixture/inventory-response.json"
jq '.product.price_cents = 200 |
    .product.updated_at = "2026-07-26T14:00:04.000000Z" |
    .revision.revision = 3 |
    .inventory.available_quantity = 7 |
    .inventory.reserved_quantity = 2' \
  "$fixture/mysql-initial-snapshot.json" >"$fixture/mysql-while-down-snapshot.json"
cp "$fixture/es-initial-snapshot.json" "$fixture/es-while-down-snapshot.json"
jq -n --arg container "$container_id" --arg identity "$after_identity" '
  {container_id:$container,java_identity:$identity,captured_at:"2026-07-26T14:00:05Z"}
' >"$fixture/adapter-after-start.json"
cp "$fixture/mysql-while-down-snapshot.json" "$fixture/mysql-snapshot.json"
jq '._source.price_cents = 200' \
  "$fixture/es-initial-snapshot.json" >"$fixture/es-snapshot.json"
printf '%s\n' \
  '{"deadline_seconds":60,"deadline_reached":false,"observation_completed":true,"completed_at":"2026-07-26T14:00:06Z"}' \
  >"$fixture/target-observation.json"
printf '%s\n' \
  '{"started_at":"2026-07-26T14:00:00Z","stopped_at":"2026-07-26T14:00:03Z","source_mutated_at":"2026-07-26T14:00:04Z","restarted_at":"2026-07-26T14:00:05Z","completed_at":"2026-07-26T14:00:06Z"}' \
  >"$fixture/timestamps.json"

bash scenarios/scripts/derive-m1-restart-result.sh "$fixture" >"$fixture/result.json"
bash scenarios/scripts/assert-m1-restart-evidence.sh "$fixture"
jq -e '
  .result == "OBSERVED_RESTART_RECOVERY" and
  .restart_experiment_valid == true and
  .mapping_continuity_verified == true and
  .final_consistency_claim == false
' "$fixture/result.json" >/dev/null

# A complete bounded deadline may record the observed gap without failing the runner.
cp "$fixture/es-initial-snapshot.json" "$fixture/es-snapshot.json"
jq '.deadline_reached = true | .completed_at = "2026-07-26T14:01:05Z"' \
  "$fixture/target-observation.json" >"$fixture/target-observation.tmp"
mv "$fixture/target-observation.tmp" "$fixture/target-observation.json"
jq '.completed_at = "2026-07-26T14:01:05Z"' "$fixture/timestamps.json" \
  >"$fixture/timestamps.tmp"
mv "$fixture/timestamps.tmp" "$fixture/timestamps.json"
bash scenarios/scripts/derive-m1-restart-result.sh "$fixture" >"$fixture/result.json"
bash scenarios/scripts/assert-m1-restart-evidence.sh "$fixture"
jq -e '.result == "OBSERVED_RESTART_GAP" and .final_consistency_claim == false' \
  "$fixture/result.json" >/dev/null

# A gap without the bounded deadline is not an observation.
jq '.deadline_reached = false' "$fixture/target-observation.json" \
  >"$fixture/target-observation.tmp"
mv "$fixture/target-observation.tmp" "$fixture/target-observation.json"
bash scenarios/scripts/derive-m1-restart-result.sh "$fixture" >"$fixture/result.json"
if bash scenarios/scripts/assert-m1-restart-evidence.sh "$fixture" >/dev/null 2>&1; then
  echo "restart evidence accepted a gap before the bounded target deadline" >&2
  exit 1
fi

test -x scenarios/scripts/run-m1-restart.sh

# A recreated container, silent Java restart, changed-while-down target, or incomplete source fails closed.
jq '.deadline_reached = true' "$fixture/target-observation.json" \
  >"$fixture/target-observation.tmp"
mv "$fixture/target-observation.tmp" "$fixture/target-observation.json"
cp "$fixture/timestamps.json" "$fixture/timestamps.valid.json"
jq '.completed_at = "2026-07-26T13:59:59Z"' \
  "$fixture/timestamps.valid.json" >"$fixture/timestamps.json"
bash scenarios/scripts/derive-m1-restart-result.sh "$fixture" >"$fixture/result.json"
if bash scenarios/scripts/assert-m1-restart-evidence.sh "$fixture" >/dev/null 2>&1; then
  echo "restart evidence accepted timestamps that contradict the state order" >&2
  exit 1
fi
mv "$fixture/timestamps.valid.json" "$fixture/timestamps.json"

cp "$fixture/adapter-after-start.json" "$fixture/adapter-after-start.valid.json"
jq '.container_id = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"' \
  "$fixture/adapter-after-start.valid.json" >"$fixture/adapter-after-start.json"
bash scenarios/scripts/derive-m1-restart-result.sh "$fixture" >"$fixture/result.json"
if bash scenarios/scripts/assert-m1-restart-evidence.sh "$fixture" >/dev/null 2>&1; then
  echo "restart evidence accepted a recreated Adapter container" >&2
  exit 1
fi
mv "$fixture/adapter-after-start.valid.json" "$fixture/adapter-after-start.json"

cp "$fixture/current-run-mapping-proof.json" "$fixture/current-run-mapping-proof.valid.json"
jq '.post_behavior.java_identity = "42|333333"' \
  "$fixture/current-run-mapping-proof.valid.json" >"$fixture/current-run-mapping-proof.json"
bash scenarios/scripts/derive-m1-restart-result.sh "$fixture" >"$fixture/result.json"
if bash scenarios/scripts/assert-m1-restart-evidence.sh "$fixture" >/dev/null 2>&1; then
  echo "restart evidence accepted a silent Java restart" >&2
  exit 1
fi
mv "$fixture/current-run-mapping-proof.valid.json" "$fixture/current-run-mapping-proof.json"

cp "$fixture/es-while-down-snapshot.json" "$fixture/es-while-down-snapshot.valid.json"
jq '._source.price_cents = 200' "$fixture/es-while-down-snapshot.valid.json" \
  >"$fixture/es-while-down-snapshot.json"
bash scenarios/scripts/derive-m1-restart-result.sh "$fixture" >"$fixture/result.json"
if bash scenarios/scripts/assert-m1-restart-evidence.sh "$fixture" >/dev/null 2>&1; then
  echo "restart evidence accepted a target that changed while Adapter was down" >&2
  exit 1
fi
mv "$fixture/es-while-down-snapshot.valid.json" "$fixture/es-while-down-snapshot.json"

mv "$fixture/mysql-snapshot.json" "$fixture/mysql-snapshot.missing.json"
if bash scenarios/scripts/assert-m1-restart-evidence.sh "$fixture" >/dev/null 2>&1; then
  echo "restart evidence accepted an incomplete source snapshot" >&2
  exit 1
fi
