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
  m3-bulk-partial)
    jq -e --slurpfile definition "$dir/definition.json" '
      .terminal_state=="HEALTHY" and .valid_item_applied_before_repair==true
      and .recovered_by_current_source_replay==true
      and (.raw_batch_record.payload.data|length)==2
      and ([.raw_batch_record.payload.data[]|{product_id:(.product_id|tonumber),revision:(.revision|tonumber)}]|sort_by(.product_id))
        == ([{product_id:$definition[0].batch.bad_product_id,revision:$definition[0].batch.revision},
             {product_id:$definition[0].batch.valid_product_id,revision:$definition[0].batch.revision}]|sort_by(.product_id))
      and (.raw_pending|length)==1
      and .raw_pending[0].productId==$definition[0].batch.bad_product_id
      and .raw_pending[0].sourceRevision==$definition[0].batch.revision
      and .raw_pending[0].eventId==("product-search-revisions:"+(.raw_batch_record.partition|tostring)+":"+(.raw_batch_record.offset|tostring)+":"+($definition[0].batch.bad_product_id|tostring))
      and ((.raw_valid_before_repair.raw_body|fromjson)._source | .product_id==$definition[0].batch.valid_product_id
        and .source_revision==$definition[0].batch.revision and .price_cents==$definition[0].batch.valid_price_cents)
      and ((.raw_bad_final.raw_body|fromjson)._source.source_revision==$definition[0].batch.revision)
      and ((.raw_valid_final.raw_body|fromjson)._source.source_revision==$definition[0].batch.revision)' "$dir/result.json" >/dev/null
    jq -e '.unresolved==0' "$dir/product-dlq-count.json" "$dir/record-dlq-count.json" >/dev/null ;;
  m3-mapping-conflict)
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
