#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/../.." && pwd)"
contract="$project_root/tests/contracts/evidence-contract.sh"
valid="$project_root/tests/fixtures/m6/evidence-valid"
canal_valid="$project_root/tests/fixtures/m6/evidence-canal-valid"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

expect_rejected() {
  local name="$1" source="$2" filter="${3:-}" target
  target="$tmp/$name"
  cp -R "$source" "$target"
  if test -n "$filter"; then
    jq "$filter" "$target/result.json" >"$target/result.tmp"
    mv "$target/result.tmp" "$target/result.json"
  fi
  if bash "$contract" "$target" >/dev/null 2>&1; then
    echo "tampered evidence accepted: $name" >&2
    exit 1
  fi
}

expect_file_rejected() {
  local name="$1" source="$2" file="$3" filter="$4" target
  target="$tmp/$name"
  cp -R "$source" "$target"
  jq "$filter" "$target/$file" >"$target/file.tmp"
  mv "$target/file.tmp" "$target/$file"
  if bash "$contract" "$target" >/dev/null 2>&1; then
    echo "tampered evidence accepted: $name ($file)" >&2
    exit 1
  fi
}

files=(manifest.json input-commands.json fault.json mysql-snapshot.json es-snapshot.json kafka-offsets.json differences.json recovery-actions.json result.json)
bash "$contract" "$valid" >/dev/null
for file in "${files[@]}"; do
  target="$tmp/missing-${file%.json}"
  cp -R "$valid" "$target"
  rm "$target/$file"
  if bash "$contract" "$target" >/dev/null 2>&1; then
    echo "bundle accepted without $file" >&2
    exit 1
  fi
done
extra="$tmp/extra-file"
cp -R "$valid" "$extra"
printf 'not allowed\n' >"$extra/scenario-specific.txt"
if bash "$contract" "$extra" >/dev/null 2>&1; then echo 'bundle accepted an extra top-level file' >&2; exit 1; fi

expect_rejected product-dlq "$valid" '.product_unresolved_dlq_count=1 | .unresolved_dlq_count=1'
expect_rejected record-dlq "$valid" '.record_unresolved_dlq_count=1 | .unresolved_dlq_count=1'
expect_rejected hidden-dlq-component "$valid" '.record_unresolved_dlq_count=1'
expect_rejected aggregate-diff "$valid" '.exact_diff_count=1'
expect_rejected managed-field-diff "$valid" '.verification.exact_managed_field_diff_count=1'
expect_rejected version-metadata-diff "$valid" '.verification.version_metadata_diff_count=1'
expect_rejected tombstone "$valid" '.tombstone_mismatch_count=1'
expect_rejected missing-intermediate "$valid" '.observed_intermediate_states=["HEALTHY"]'
expect_rejected inconclusive "$valid" '.verification.status="INCONCLUSIVE" | .verification.conclusive=false'
expect_rejected unstable "$valid" '.verification.stable=false'
expect_rejected mismatched-result-id "$valid" '.scenario_id="duplicate-event"'
expect_rejected malformed-offset-key "$valid" '.applied_offsets={"0":10,"1":20,"3":30}'
expect_rejected malformed-offset-value "$valid" '.applied_offsets["2"]=-1'
expect_rejected watermark "$valid" '.target_watermark_passed=false | .target_watermarks.passed=false'
expect_rejected hidden-watermark-failure "$valid" '.target_watermarks.passed=false'
expect_rejected stale-target-watermark "$valid" '.target_watermarks.elasticsearch_revision=41'
expect_rejected failed-precondition "$valid" '.consistency_preconditions[0].satisfied=false'
expect_rejected rebuild-without-required-state "$valid" '.requires_rebuild=true | .rebuild_required_before_rebuild=false'
expect_rejected changed-recovery "$valid" '.recovery_action="skip evidence"'
expect_rejected extra-result-field "$valid" '.unexpected=true'
expect_rejected extra-dependency-field "$valid" '.dependency_versions.unexpected="x"'
expect_rejected extra-precondition-field "$valid" '.consistency_preconditions[0].unexpected=true'
expect_rejected extra-watermark-field "$valid" '.target_watermarks.unexpected=true'
expect_rejected extra-verification-field "$valid" '.verification.unexpected=true'
expect_rejected malformed-verification-uuid "$valid" '.verification.run_id="not-a-uuid"'
expect_rejected malformed-start-time "$valid" '.started_at="not-a-date"'
expect_file_rejected verifier-run-cross-file "$valid" differences.json '.independent_verification.runId="22222222-2222-4222-8222-222222222222"'
expect_file_rejected runner-run-cross-file "$valid" fault.json '.runner_run_id="22222222-2222-4222-8222-222222222222"'
expect_file_rejected missing-manifest-provenance "$valid" manifest.json 'del(.git)'
expect_file_rejected empty-input-command-proof "$valid" input-commands.json '.intents=[]'
expect_file_rejected impossible-command-time "$valid" input-commands.json '.executions[0].finished_at="2026-07-28T19:59:59Z"'
expect_file_rejected invented-case-fact "$valid" fault.json '.case_observations={kind:"invented"}'
expect_file_rejected invented-mysql-document "$valid" mysql-snapshot.json '.documents += [{product_id:999999,revision:1,active:1,sku:"INVENTED",name:"invented",description:"invented",category_id:10,category_name:"invented",price_cents:1,available_quantity:0,updated_at:"2026-07-28T20:00:00.000000Z"}]'
expect_file_rejected extra-kafka-offset-field "$valid" kafka-offsets.json '.primary=[{"partition":0,"offset":0,"lag":0,"invented":true}]'
expect_file_rejected duplicate-kafka-partition "$valid" kafka-offsets.json '.primary[2].partition=1'
expect_file_rejected missing-kafka-partition "$valid" kafka-offsets.json '.end|=.[0:2]'
expect_file_rejected incomplete-observations "$valid" differences.json 'del(.observations.source_watermark)'
expect_file_rejected missing-verification-count "$valid" differences.json 'del(.independent_verification.counts.MISSING)'
expect_file_rejected extra-difference-verification-field "$valid" differences.json '.observations.verification.invented=true'
expect_file_rejected extra-recovery-command-field "$valid" recovery-actions.json '.commands[0].invented=true'

unknown="$tmp/unknown-scenario"
cp -R "$valid" "$unknown"
for file in "${files[@]}"; do jq '.scenario_id="invented-scenario"' "$unknown/$file" >"$unknown/tmp"; mv "$unknown/tmp" "$unknown/$file"; done
if bash "$contract" "$unknown" >/dev/null 2>&1; then echo 'unknown all-file scenario identity accepted' >&2; exit 1; fi

cross="$tmp/rebuild-cross-evidence"
cp -R "$valid" "$cross"
jq '.rebuild_required_observed_before_rebuild=true' "$cross/recovery-actions.json" >"$cross/tmp"; mv "$cross/tmp" "$cross/recovery-actions.json"
if bash "$contract" "$cross" >/dev/null 2>&1; then echo 'mismatched rebuild-required cross evidence accepted' >&2; exit 1; fi

test -d "$canal_valid" || { echo 'missing Canal recovery positive fixture' >&2; exit 1; }
bash "$contract" "$canal_valid" >/dev/null
expect_rejected invented-event-id "$canal_valid" '.canal_position_recovery.reset_anchor_events["0"].event_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"'
expect_rejected invented-event-offset "$canal_valid" '.canal_position_recovery.reset_anchor_events["1"].offset+=7'
expect_rejected nonnull-event-key "$canal_valid" '.canal_position_recovery.normal_sentinel_events["2"].key_is_null=false'
expect_rejected wrong-event-token "$canal_valid" '.canal_position_recovery.normal_sentinel_events["1"].partition_token="2"'
expect_rejected extra-canal-field "$canal_valid" '.canal_position_recovery.unexpected=true'
expect_rejected extra-event-field "$canal_valid" '.canal_position_recovery.reset_anchor_events["0"].unexpected=true'
expect_rejected malformed-event-uuid "$canal_valid" '.canal_position_recovery.reset_anchor_events["0"].event_id="invented"'
expect_rejected reused-sentinel-run "$canal_valid" '.canal_position_recovery.normal_sentinel_run_id=.canal_position_recovery.reset_anchor_run_id | .canal_position_recovery.normal_sentinel_events[] .run_id=.canal_position_recovery.reset_anchor_run_id'
expect_rejected nonnext-sentinel "$canal_valid" '.canal_position_recovery.normal_sentinel_next_offsets["0"]+=1 | .canal_position_recovery.normal_sentinel_events["0"].next_offset+=1 | .canal_position_recovery.normal_sentinel_events["0"].offset+=1'
expect_rejected reset-identity-not-preserved "$canal_valid" '.canal_position_recovery.normal_restart_cursor_sha256=("f"*64)'
expect_rejected invalid-manifest-index "$canal_valid" '.canal_position_recovery.reset_file_index=0'
expect_rejected below-lower-bound "$canal_valid" '.canal_position_recovery.reset_file_index=0 | .canal_position_recovery.normal_restart_file_index=0 | .canal_position_recovery.reset_journal="binlog.000010" | .canal_position_recovery.normal_restart_journal="binlog.000010" | .canal_position_recovery.reset_position=4 | .canal_position_recovery.normal_restart_position=4'

bash "$project_root/tests/contracts/m6-case-semantics-tamper.sh" >/dev/null

printf 'M6 evidence tamper negatives passed\n'
