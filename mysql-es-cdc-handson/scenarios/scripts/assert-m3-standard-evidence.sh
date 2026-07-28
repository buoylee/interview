#!/usr/bin/env bash
set -euo pipefail
dir="${1:?evidence directory required}"
jq -e . "$dir/definition.json" "$dir/result.json" >/dev/null
scenario="$(jq -r .scenario "$dir/definition.json")"
jq -e --arg scenario "$scenario" '.scenario==$scenario and (.final_consistency_claim==false)' "$dir/result.json" >/dev/null
case "$scenario" in
  m3-record-parse-dlq)
    jq -e '.terminal_state=="DEGRADED" and .replay_still_pending==true
      and .teardown_is_not_recovery==true and .final_recovery_claim==false
      and .raw_before[0].status=="PENDING" and .raw_after[0].status=="PENDING"
      and .raw_after[0].attempts>.raw_before[0].attempts' "$dir/result.json" >/dev/null ;;
  m3-mapping-conflict|m3-bulk-partial)
    jq -e '.terminal_state=="HEALTHY" and .recovered_by_current_source_replay==true
      and (.raw_pending|length)>=1' "$dir/result.json" >/dev/null
    jq -e '.unresolved==0' "$dir/product-dlq-count.json" "$dir/record-dlq-count.json" >/dev/null ;;
  m3-delete-then-old-replay)
    jq -e '.terminal_state=="HEALTHY" and .raw_old_record.payload.data[0].revision=="1"
      and .raw_tombstone._source.source_revision==2 and .raw_tombstone._source.searchable==false' "$dir/result.json" >/dev/null ;;
  *)
    jq -e '.terminal_state=="HEALTHY"' "$dir/result.json" >/dev/null
    jq -e '.unresolved==0' "$dir/product-dlq-count.json" "$dir/record-dlq-count.json" >/dev/null ;;
esac
