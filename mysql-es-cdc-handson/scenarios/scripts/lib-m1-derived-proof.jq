def m1_sha256:
  type == "string" and test("^[0-9a-f]{64}$");

def m1_identity:
  type == "string" and test("^[0-9]+[|][0-9]+$");

def m1_mapping_continuity($pre; $final; $container; $identity):
  ($pre.contract == "m1-adapter-baseline-continuity-v1") and
  ($pre.phase == "pre_behavior") and
  ($pre.baseline_continuity_verified == false) and
  ($pre.identity_stable_during_precheck == true) and
  ($pre.loader_assertions == {
    start_loading_after_cutoff:true,
    loaded_after_cutoff:true
  }) and
  ($pre.container_id | m1_sha256) and
  ($pre.java_identity | m1_identity) and
  ($pre.java_cutoff_utc | type == "string" and
    test("^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{3}$")) and
  ($pre.workspace_mapping_sha256 | m1_sha256) and
  ($pre.container_mapping_sha256 == $pre.workspace_mapping_sha256) and
  ($pre.container_id == $container) and
  ($pre.java_identity == $identity) and
  ($final.contract == $pre.contract) and
  ($final.phase == "baseline_complete") and
  ($final.baseline_continuity_verified == true) and
  ($final.container_id == $pre.container_id) and
  ($final.java_identity == $pre.java_identity) and
  ($final.java_cutoff_utc == $pre.java_cutoff_utc) and
  ($final.workspace_mapping_sha256 == $pre.workspace_mapping_sha256) and
  ($final.container_mapping_sha256 == $pre.container_mapping_sha256) and
  ($final.loader_assertions == $pre.loader_assertions) and
  ($final.identity_stable_during_precheck == true) and
  ($final.post_behavior == {
    container_id:$pre.container_id,
    java_identity:$pre.java_identity,
    container_mapping_sha256:$pre.container_mapping_sha256,
    identity_stable_during_postcheck:true
  });

def m1_managed_target($get; $expected; $price):
  ($get.found == true) and
  ($get._source | keys | sort) == [
    "category_id","description","name","price_cents",
    "product_id","sku","status","updated_at"
  ] and
  ($get._source.updated_at == null) and
  (($get._source | del(.updated_at)) == ($expected + {price_cents:$price}));

def m1_source_timestamp:
  type == "string" and
  test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{6}Z$");
