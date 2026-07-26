#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
out="${1:-evidence/m1/m1-hard-delete}"

jq -L scenarios/scripts -n '
  include "lib-m1-derived-proof";

  ($input[0]) as $commands |
  ($commands.source_product) as $product |
  ({
    product_id:$product.id,sku:$product.sku,name:$product.name,
    description:$product.description,category_id:$product.category_id,
    status:$product.status
  }) as $expected_product |
  ($commands == {
    scenario_id:"m1-hard-delete",
    product_id:1301,
    fault:"delete revision, inventory, and product rows in one direct SQL transaction",
    direct_sql_fault_injection:true,
    normal_business_path:false,
    source_product:{
      id:1301,sku:"M1-1301",name:"Delete Keyboard",
      description:"hard-delete observation",category_id:10,
      price_cents:100,status:"ACTIVE"
    },
    target_deadline_seconds:60,
    expected_observation:"Adapter DELETE behavior is measured, not assumed",
    final_consistency_claim:false
  }) as $input_match |
  ($initial_source[0]) as $initial |
  ($index[0] == {
      acknowledged:true,shards_acknowledged:true,index:"products_adapter_v1"
    } and
    $create[0] == {productId:1301,revision:1} and
    $initial.product == ($expected_product + {
      price_cents:100,updated_at:$initial.product.updated_at
    }) and
    ($initial.product.updated_at | m1_source_timestamp) and
    $initial.revision == {product_id:1301,revision:1,active:true} and
    $initial.inventory == {
      product_id:1301,available_quantity:0,reserved_quantity:0
    } and
    m1_managed_target($initial_target[0];$expected_product;100)) as $setup_complete |
  ($sql[0] == {
    direct_sql_fault_injection:true,
    normal_business_path:false,
    transaction:"START TRANSACTION; DELETE FROM product_search_revision WHERE product_id = 1301; DELETE FROM inventory WHERE product_id = 1301; DELETE FROM products WHERE id = 1301; COMMIT;",
    started_at:$sql[0].started_at,
    committed_at:$sql[0].committed_at
  } and
    ($sql[0].started_at | type) == "string" and
    ($sql[0].committed_at | type) == "string" and
    $sql[0].started_at <= $sql[0].committed_at) as $direct_sql_proven |
  ($absence[0].product_id == 1301 and
    $absence[0].product_row_count == 0 and
    $absence[0].revision_row_count == 0 and
    $absence[0].inventory_row_count == 0 and
    ($absence[0].captured_at | type) == "string") as $source_rows_absent |
  (m1_mapping_continuity(
    $pre_proof[0];$mapping_proof[0];
    $pre_proof[0].container_id;$pre_proof[0].java_identity
  )) as $mapping_continuity_verified |
  ($observation[0].deadline_seconds == 60 and
    $observation[0].observation_completed == true and
    ($observation[0].deadline_reached | type) == "boolean" and
    ($observation[0].completed_at | type) == "string") as $bounded_observation_complete |
  ($sql[0].committed_at <= $absence[0].captured_at and
    $absence[0].captured_at <= $observation[0].completed_at) as $timestamps_ordered |
  ($target[0].found == false and
    $target[0]._index == "products_adapter_v1" and
    $target[0]._id == "1301") as $delete_observed |
  (m1_managed_target($target[0];$expected_product;100)) as $document_still_present |
  ($input_match and $setup_complete and $direct_sql_proven and
    $source_rows_absent and $mapping_continuity_verified and
    $bounded_observation_complete and $timestamps_ordered) as $experiment_valid |
  ($experiment_valid and $delete_observed) as $propagated |
  ($experiment_valid and $document_still_present and
    $observation[0].deadline_reached == true) as $bounded_gap |
  {
    scenario_id:"m1-hard-delete",
    result:(if $propagated then "OBSERVED_DELETE_PROPAGATION"
      elif $bounded_gap then "OBSERVED_DELETE_GAP"
      else "OBSERVED_ASSERTION_MISMATCH" end),
    input_commands_match:$input_match,
    setup_complete:$setup_complete,
    direct_sql_fault_injection:$sql[0].direct_sql_fault_injection,
    normal_business_path:$sql[0].normal_business_path,
    direct_sql_proven:$direct_sql_proven,
    source_rows_absent:$source_rows_absent,
    mapping_continuity_verified:$mapping_continuity_verified,
    bounded_observation_complete:$bounded_observation_complete,
    timestamps_ordered:$timestamps_ordered,
    target_deadline_reached:$observation[0].deadline_reached,
    delete_observed:$delete_observed,
    document_still_present:$document_still_present,
    hard_delete_experiment_valid:$experiment_valid,
    evidence_files:{
      direct_sql:"direct-sql.json",source:"mysql-absence-snapshot.json",
      target:"es-snapshot.json",adapter_log:"adapter.log",
      mapping_proof:"current-run-mapping-proof.json"
    },
    final_consistency_claim:false
  }
' \
  --slurpfile input "$out/input-commands.json" \
  --slurpfile index "$out/index-create.json" \
  --slurpfile create "$out/create-response.json" \
  --slurpfile initial_source "$out/mysql-initial-snapshot.json" \
  --slurpfile initial_target "$out/es-initial-snapshot.json" \
  --slurpfile sql "$out/direct-sql.json" \
  --slurpfile absence "$out/mysql-absence-snapshot.json" \
  --slurpfile target "$out/es-snapshot.json" \
  --slurpfile observation "$out/target-observation.json" \
  --slurpfile pre_proof "$out/pre-behavior-mapping-proof.json" \
  --slurpfile mapping_proof "$out/current-run-mapping-proof.json"
