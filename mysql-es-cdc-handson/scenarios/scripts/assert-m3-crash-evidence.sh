#!/usr/bin/env bash
set -euo pipefail
dir="${1:?evidence directory required}"
for file in definition.json process-before.json process-crashed.json process-restarted.json armed.json record.json group-after-crash.json source-mutation-response.json source-after-mutation.json result.json; do
  test -s "$dir/$file" || { echo "missing evidence: $file" >&2; exit 1; }
done
jq -e --slurpfile d "$dir/definition.json" '.exit_code == $d[0].exit_code and .failpoint == $d[0].failpoint' "$dir/result.json" >/dev/null
jq -e '.running == false and .exit_code == 86 and (.finished_at|length)>0' "$dir/process-crashed.json" >/dev/null
jq -e --slurpfile before "$dir/process-before.json" --slurpfile crash "$dir/process-crashed.json" \
  '.id == $before[0].id and .id == $crash[0].id and $before[0].started_at == $crash[0].started_at
   and $crash[0].finished_at > $crash[0].started_at and .started_at > $crash[0].finished_at and .running == true' \
  "$dir/process-restarted.json" >/dev/null
jq -e '.productId > 0 and .revision == 2' "$dir/source-mutation-response.json" >/dev/null
jq -e '.product_id > 0 and .revision == 2' "$dir/source-after-mutation.json" >/dev/null
jq -e --slurpfile r "$dir/record.json" '($r[0]) as $record | map(select(.partition==$record.partition)) | length==1 and .[0].committed <= $record.offset and .[0].end > $record.offset' "$dir/group-after-crash.json" >/dev/null
scenario="$(jq -r .scenario "$dir/definition.json")"
if [[ "$scenario" == m3-after-es-before-offset ]]; then
  jq -e '.durable_revision_before_restart==2 and .final_revision==2 and .before_restart_seq_no==.final_seq_no and .dlq_rows==0 and .replay_outcome=="STALE" and .final_consistency_claim==true' "$dir/result.json" >/dev/null
  jq -e 'length==3 and all(.[];.lag==0)' "$dir/final-group.json" >/dev/null
else
  jq -e '.products_v2.mappings.properties.price_cents.type=="byte"' "$dir/mapping-bad.json" >/dev/null
  jq -e '.products_v2.mappings.properties.price_cents.type=="long"' "$dir/mapping-restored.json" >/dev/null
  jq -e '.crash_pending_rows==1 and .attempts_after_crash==1 and .restart_pending_rows==1 and .attempts_after_restart==2 and .status_after_mapping_restore=="PENDING" and .terminal_boundary=="RECOVERY_DEFERRED_TO_TASK7" and .final_consistency_claim==false' "$dir/result.json" >/dev/null
fi
