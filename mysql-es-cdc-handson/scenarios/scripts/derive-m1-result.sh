#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
out="${1:-evidence/m1/m1-basic}"

jq -n \
  --slurpfile input "$out/input-commands.json" \
  --slurpfile create "$out/create-response.json" \
  --slurpfile update "$out/update-response.json" \
  --slurpfile insert_source "$out/mysql-insert-snapshot.json" \
  --slurpfile insert_target "$out/es-insert-snapshot.json" \
  --slurpfile source "$out/mysql-snapshot.json" \
  --slurpfile target "$out/es-snapshot.json" \
  --slurpfile mapping_proof "$out/current-run-mapping-proof.json" '
  def allowed_fields:
    ["category_id","description","name","price_cents",
     "product_id","sku","status","updated_at"];
  def source_timestamp_non_null($doc):
    ($doc.updated_at | type) == "string" and
    ($doc.updated_at | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{6}Z$"));
  def forbidden_absent($doc):
    ($doc | has("category_name") | not) and
    ($doc | has("inventory") | not) and
    ($doc | has("searchable") | not) and
    ($doc | has("source_revision") | not);

  ($input[0]) as $commands |
  ($commands.source_products[0]) as $input_product |
  ($commands.mutations[0]) as $mutation |
  ($commands.scenario_id == "m1-basic" and
   ($commands.source_products | length) == 1 and
   $input_product == {
     id:1101,
     sku:"M1-1101",
     name:"Adapter Keyboard",
     description:"initial",
     category_id:10,
     price_cents:100,
     status:"ACTIVE"
   } and
   ($commands.mutations | length) == 1 and
   $mutation == {
     operation:"change_price",
     product_id:1101,
     price_cents:120
   }) as $input_commands_match |
  ({
    product_id:$input_product.id,
    sku:$input_product.sku,
    name:$input_product.name,
    description:$input_product.description,
    category_id:$input_product.category_id,
    price_cents:$input_product.price_cents,
    status:$input_product.status
  }) as $expected_insert |
  ($expected_insert + {price_cents:$mutation.price_cents}) as $expected_final |
  ($mapping_proof[0]) as $proof |
  ($proof.contract == "m1-adapter-baseline-continuity-v1" and
   $proof.phase == "baseline_complete" and
   $proof.baseline_continuity_verified == true and
   $proof.identity_stable_during_precheck == true and
   $proof.loader_assertions == {
     start_loading_after_cutoff:true,
     loaded_after_cutoff:true
   } and
   ($proof.container_id | test("^[0-9a-f]{64}$")) and
   ($proof.java_identity | test("^[0-9]+[|][0-9]+$")) and
   ($proof.java_cutoff_utc | test("^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{3}$")) and
   ($proof.workspace_mapping_sha256 | test("^[0-9a-f]{64}$")) and
   $proof.container_mapping_sha256 == $proof.workspace_mapping_sha256 and
   $proof.post_behavior == {
     container_id:$proof.container_id,
     java_identity:$proof.java_identity,
     container_mapping_sha256:$proof.container_mapping_sha256,
     identity_stable_during_postcheck:true
   }) as $mapping_continuity_verified |
  ($insert_source[0]) as $insert_source_doc |
  ($insert_target[0]) as $insert_target_get |
  ($insert_target_get._source) as $insert_target_doc |
  ($source[0]) as $source_doc |
  ($target[0]) as $target_get |
  ($target_get._source) as $target_doc |
  {
    input_commands_match:$input_commands_match,
    mapping_continuity_verified:$mapping_continuity_verified,
    insert_observed: (
      $input_commands_match and
      $create[0] == {productId:$input_product.id,revision:1} and
      $insert_target_get.found == true and
      ($insert_source_doc | del(.updated_at)) == $expected_insert and
      ($insert_target_doc | del(.updated_at)) == $expected_insert
    ),
    update_observed: (
      $input_commands_match and
      $update[0] == {productId:$mutation.product_id,revision:2} and
      $target_get.found == true and
      ($source_doc | del(.updated_at)) == $expected_final and
      ($target_doc | del(.updated_at)) == $expected_final
    ),
    non_computed_fields_match: (
      ($insert_source_doc | del(.updated_at)) == $expected_insert and
      ($insert_target_doc | del(.updated_at)) == $expected_insert and
      ($source_doc | del(.updated_at)) == $expected_final and
      ($target_doc | del(.updated_at)) == $expected_final
    ),
    forbidden_fields_absent: (
      forbidden_absent($insert_source_doc) and forbidden_absent($insert_target_doc) and
      forbidden_absent($source_doc) and forbidden_absent($target_doc)
    ),
    allowed_field_set_exact: (
      ($insert_source_doc | keys | sort) == allowed_fields and
      ($insert_target_doc | keys | sort) == allowed_fields and
      ($source_doc | keys | sort) == allowed_fields and
      ($target_doc | keys | sort) == allowed_fields
    ),
    source_updated_at_non_null: (
      source_timestamp_non_null($insert_source_doc) and source_timestamp_non_null($source_doc)
    ),
    target_updated_at_is_null: (
      $insert_target_doc.updated_at == null and $target_doc.updated_at == null
    ),
    updated_at_matches_source: (
      $insert_target_doc.updated_at == $insert_source_doc.updated_at and
      $target_doc.updated_at == $source_doc.updated_at
    )
  } as $observed |
  ($observed.input_commands_match and
   $observed.mapping_continuity_verified and
   $observed.insert_observed and
   $observed.update_observed and
   $observed.non_computed_fields_match and
   $observed.forbidden_fields_absent and
   $observed.allowed_field_set_exact and
   $observed.source_updated_at_non_null and
   $observed.target_updated_at_is_null and
   ($observed.updated_at_matches_source | not)) as $is_ruled_gap |
  {
    scenario_id:$commands.scenario_id,
    result:(if $is_ruled_gap
      then "OBSERVED_INSERT_UPDATE_WITH_COMPUTED_FIELD_GAP"
      else "OBSERVED_ASSERTION_MISMATCH"
    end),
    input_commands_match:$observed.input_commands_match,
    mapping_continuity_verified:$observed.mapping_continuity_verified,
    insert_observed:$observed.insert_observed,
    update_observed:$observed.update_observed,
    non_computed_fields_match:$observed.non_computed_fields_match,
    forbidden_fields_absent:$observed.forbidden_fields_absent,
    allowed_field_set_exact:$observed.allowed_field_set_exact,
    source_updated_at_non_null:$observed.source_updated_at_non_null,
    target_updated_at_is_null:$observed.target_updated_at_is_null,
    updated_at_matches_source:$observed.updated_at_matches_source,
    captured_values:{
      insert_source_updated_at:$insert_source_doc.updated_at,
      insert_target_updated_at:$insert_target_doc.updated_at,
      final_source_updated_at:$source_doc.updated_at,
      final_target_updated_at:$target_doc.updated_at
    },
    evidence_files:{
      input:"input-commands.json",
      source:"mysql-snapshot.json",
      target:"es-snapshot.json",
      adapter_log:"adapter.log",
      pre_behavior_mapping_proof:"pre-behavior-mapping-proof.json",
      mapping_proof:"current-run-mapping-proof.json"
    },
    final_consistency_claim:false
  }
'
