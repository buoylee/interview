#!/usr/bin/env bash
set -euo pipefail

fault="${1:?fault evidence required}"
scenario="$(jq -er '.scenario_id' "$fault")"
base='def fact($p): [.case_observations.artifacts[]|select(.path==$p)][0] | if has("json") then .json else .text end | if type=="object" and (.raw_body? | type)=="string" then .raw_body|fromjson else . end; def normalized_event: .data |= map({product_id,revision,active}); '
assert_case() { jq -e "$base $1" "$fault" >/dev/null; }

case "$scenario" in
  canal-normal-restart)
    assert_case 'fact("meta-before.json")==fact("meta-after-restart.json") and fact("end-before.json")==fact("end-after-restart.json") and fact("consumer-stopped.json")==true and fact("post-restart-record.json").payload.data[0].product_id=="6101" and fact("post-restart-record.json").payload.data[0].revision=="2" and fact("es-final.json")._source.source_revision==2'
    ;;
  canal-outage-within-binlog-retention)
    assert_case 'fact("source-during.json").revision==2 and fact("es-during.json")._source.source_revision==1 and fact("es-final.json")._source.source_revision==2 and (fact("meta-before.json").journal|length)>0'
    ;;
  canal-outage-beyond-binlog-retention)
    assert_case 'fact("mysql-gap-status.json").target=="mysql" and fact("mysql-gap-status.json").recorded_present==false and fact("gap-proof.json").canal_missing_position_observed==true and fact("status-gap.json").state=="REBUILD_REQUIRED" and fact("recovery-required.json").status=="CANAL_RECOVERY_REQUIRED" and fact("recovery-started.json").status=="CANAL_RECOVERING"'
    ;;
  kafka-temporary-unavailable)
    assert_case 'fact("toxic-applied.json").active==true and fact("toxic-status.json")==true and fact("toxic-removed.json").active==false and fact("source-during.json").revision==2 and fact("end-before.json")==fact("end-during.json") and fact("es-final.json")._source.source_revision==2'
    ;;
  consumer-offset-beyond-kafka-retention)
    assert_case 'fact("kafka-gap-status.json").gap==true and fact("gap-proof.json").beginning_offset>fact("gap-proof.json").committed_offset and fact("status-gap.json").state=="REBUILD_REQUIRED" and fact("rebuild-response.json").status=="COMPLETED"'
    ;;
  consumer-crash-before-elasticsearch)
    assert_case 'fact("crashed.json").running==false and fact("crashed.json").exit_code==86 and fact("record.json").payload.data[0].product_id=="6601" and fact("record.json").payload.data[0].revision=="2" and fact("es-final.json")._source.source_revision==2'
    ;;
  consumer-crash-after-elasticsearch-before-offset)
    assert_case 'fact("crashed.json").running==false and fact("crashed.json").exit_code==86 and fact("record.json").payload.data[0].product_id=="6701" and fact("es-before-restart.json")._source.source_revision==2 and fact("es-after-restart.json")._seq_no==fact("es-before-restart.json")._seq_no and fact("es-after-restart.json")._version==2'
    ;;
  elasticsearch-bulk-partial-failure)
    assert_case '([fact("batch-record.json").payload.data[].product_id]|sort)==["6801","6804"] and ([fact("batch-record.json").payload.data[].revision]|unique)==["2"] and (fact("dlq-pending.json")|length)==1 and fact("dlq-pending.json")[0].productId==6804 and fact("replay.json").status=="RESOLVED" and fact("es-valid.json")._source.source_revision==2 and fact("es-replayed.json")._source.source_revision==2'
    ;;
  duplicate-event)
    assert_case 'fact("selected.json").record.payload.data[0].product_id==(fact("selected.json").product_id|tostring) and fact("injected-event.json").primitive=="lab-scenario-event-v1" and fact("injected-event.json").key_is_null==true and (fact("injected-event.json").payload_sha256|test("^[a-f0-9]{64}$")) and fact("injected-event.json").normalized_payload==(fact("selected.json").record.payload|normalized_event) and fact("injected-event.json").broker_ack.partition==fact("selected.json").partition and {version:fact("es-before.json")._version,source:fact("es-before.json")._source}=={version:fact("es-after.json")._version,source:fact("es-after.json")._source}'
    ;;
  late-old-revision)
    assert_case 'fact("selected.json").record.payload.data[0].revision=="1" and (fact("injected-event.json").payload_sha256|test("^[a-f0-9]{64}$")) and fact("injected-event.json").normalized_payload==(fact("selected.json").record.payload|normalized_event) and fact("injected-event.json").broker_ack.partition==fact("selected.json").partition and fact("es-after-old.json")._source.product_id==fact("selected.json").product_id and fact("es-after-old.json")._source.source_revision==3 and fact("es-after-old.json")._source.price_cents==70030 and fact("es-after-old.json")._seq_no==fact("es-before-old.json")._seq_no'
    ;;
  mapping-conflict)
    assert_case '(fact("dlq-pending.json")|length)==1 and fact("dlq-pending.json")[0].productId==7101 and fact("replay.json").status=="RESOLVED" and fact("generation-before")==fact("generation-after") and fact("es-final.json")._source.source_revision==2'
    ;;
  manual-elasticsearch-drift)
    assert_case 'fact("diff-run.json").status=="DIFF" and fact("diff-run.json").counts.MISSING==1 and fact("diff-run.json").counts.MODIFIED==1 and ([fact("differences.json")[].type]|sort)==["MISSING","MODIFIED"] and fact("repair.json").repaired==true and fact("repair.json").applied==2 and fact("fresh-pass.json").status=="PASS" and fact("fresh-pass.json").differenceCount==0'
    ;;
  category-rename-multi-product)
    assert_case '(fact("source-after.json")|length)==3 and ([fact("source-after.json")[].product_id]|sort)==[7301,7304,7307] and all(fact("source-after.json")[];.revision==2) and ([fact("source-after.json")[].updated_at]|unique|length)==1 and fact("three-row-record.json")==true and fact("consumer-stopped.json")==true'
    ;;
  delete-then-old-event-replay)
    assert_case 'fact("delete.json").revision==2 and (fact("injected-event.json").payload_sha256|test("^[a-f0-9]{64}$")) and fact("injected-event.json").normalized_payload==(fact("selected.json").record.payload|normalized_event) and fact("injected-event.json").broker_ack.partition==fact("selected.json").partition and fact("tombstone-after.json")._source.product_id==fact("selected.json").product_id and fact("tombstone-after.json")._source.searchable==false and fact("tombstone-after.json")._source.source_revision==2 and fact("search-alias-result.json").hits.total.value==0'
    ;;
  rebuild-with-concurrent-writes)
    assert_case 'fact("page-progress.json").status=="SNAPSHOTTING" and fact("page-progress.json").source_count>0 and fact("page-progress.json").source_count<fact("page-progress.json").total and fact("status-gating.json").status=="GATING" and fact("http-codes.json").gated_write==503 and fact("http-codes.json").post_gate_write>=200 and fact("http-codes.json").post_gate_write<300 and fact("rebuild-completed.json").status=="COMPLETED" and fact("rebuild-completed.json").aliasState=="NEW"'
    ;;
  rebuild-crash-and-restart)
    assert_case 'fact("before-failed.json").status=="FAILED" and fact("before-failed.json").aliasState=="OLD" and fact("rerun-response.json").status=="COMPLETED" and fact("after-cutover-status.json").status=="CUTOVER_COMMITTED" and fact("old-alias")==fact("alias-after-restart") and fact("promoted-before-restart")==fact("promoted-after-restart")'
    ;;
  consumer-systematic-mapping-bug)
    assert_case 'fact("diff-run.json").status=="DIFF" and fact("diff-run.json").counts.MODIFIED>=1 and fact("status-degraded.json").state=="DEGRADED" and fact("repair.json").repaired==true and fact("repair.json").applied==1 and fact("fresh-pass.json").status=="PASS" and fact("fresh-pass.json").differenceCount==0'
    ;;
  dlq-replay-fails-then-succeeds)
    assert_case 'fact("pending-after-failed-replay.json")[0].attempts>fact("pending-before.json")[0].attempts and fact("replay-failed.json").status=="PENDING" and fact("replay-failed.json").resolved==false and fact("replay-resolved.json").status=="RESOLVED" and fact("replay-resolved.json").resolved==true and fact("dlq-final.json")==true'
    ;;
  *) echo "scenario semantic contract is not implemented: $scenario" >&2; exit 1 ;;
esac
