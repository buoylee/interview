#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
out="${1:-evidence/m1/m1-basic}"

jq -n \
  --slurpfile create "$out/create-response.json" \
  --slurpfile update "$out/update-response.json" \
  --slurpfile insert_source "$out/mysql-insert-snapshot.json" \
  --slurpfile insert_target "$out/es-insert-snapshot.json" \
  --slurpfile source "$out/mysql-snapshot.json" \
  --slurpfile target "$out/es-snapshot.json" '
  def allowed_fields:
    ["category_id","description","name","price_cents",
     "product_id","sku","status","updated_at"];
  def source_timestamp_non_null($doc):
    ($doc.updated_at | type) == "string" and
    ($doc.updated_at | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z$"));
  def forbidden_absent($doc):
    ($doc | has("category_name") | not) and
    ($doc | has("inventory") | not) and
    ($doc | has("searchable") | not) and
    ($doc | has("source_revision") | not);

  ($insert_source[0]) as $insert_source_doc |
  ($insert_target[0]) as $insert_target_get |
  ($insert_target_get._source) as $insert_target_doc |
  ($source[0]) as $source_doc |
  ($target[0]) as $target_get |
  ($target_get._source) as $target_doc |
  {
    insert_observed: (
      $create[0] == {productId:1101,revision:1} and
      $insert_target_get.found == true and
      $insert_source_doc.price_cents == 100 and
      $insert_target_doc.price_cents == 100
    ),
    update_observed: (
      $update[0] == {productId:1101,revision:2} and
      $target_get.found == true and
      $source_doc.price_cents == 120 and
      $target_doc.price_cents == 120
    ),
    non_computed_fields_match: (
      ($insert_source_doc | del(.updated_at)) == ($insert_target_doc | del(.updated_at)) and
      ($source_doc | del(.updated_at)) == ($target_doc | del(.updated_at))
    ),
    forbidden_fields_absent: (
      forbidden_absent($insert_target_doc) and forbidden_absent($target_doc)
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
  ($observed.insert_observed and
   $observed.update_observed and
   $observed.non_computed_fields_match and
   $observed.forbidden_fields_absent and
   $observed.allowed_field_set_exact and
   $observed.source_updated_at_non_null and
   $observed.target_updated_at_is_null and
   ($observed.updated_at_matches_source | not)) as $is_ruled_gap |
  {
    scenario_id:"m1-basic",
    result:(if $is_ruled_gap
      then "OBSERVED_INSERT_UPDATE_WITH_COMPUTED_FIELD_GAP"
      else "OBSERVED_ASSERTION_MISMATCH"
    end),
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
      source:"mysql-snapshot.json",
      target:"es-snapshot.json",
      adapter_log:"adapter.log",
      mapping_proof:"current-run-mapping-proof.txt"
    },
    final_consistency_claim:false
  }
'
