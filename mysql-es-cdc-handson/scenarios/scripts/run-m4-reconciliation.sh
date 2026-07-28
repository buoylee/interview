#!/usr/bin/env bash
set -euo pipefail

compose=(docker compose -f infra/compose.yaml)
evidence_root="${M4_EVIDENCE_DIR:-evidence/m4/manual}"
case_dir=
mkdir -p "$evidence_root"

die() { echo "ERROR: $*" >&2; [[ -n "$case_dir" ]] && collect_diagnostics; exit 1; }

poll() {
  local description="$1" timeout="$2" command="$3" start=$SECONDS
  until eval "$command"; do
    if (( SECONDS - start >= timeout )); then
      echo "timeout waiting for $description; last command: $command" >&2
      return 1
    fi
    sleep 1
  done
}

collect_diagnostics() {
  curl -sS http://127.0.0.1:8083/internal/pipeline/status >"$case_dir/failure-status.json" 2>/dev/null || true
  curl -sS http://127.0.0.1:8082/internal/dlq/count >"$case_dir/failure-product-dlq.json" 2>/dev/null || true
  curl -sS http://127.0.0.1:8082/internal/record-dlq/count >"$case_dir/failure-record-dlq.json" 2>/dev/null || true
  curl -sS http://127.0.0.1:9200/products_write/_search?pretty >"$case_dir/failure-es.json" 2>/dev/null || true
  "${compose[@]}" logs --no-color --tail=80 search-sync-consumer consistency-verifier >"$case_dir/failure-services.log" 2>&1 || true
}

cleanup_faults() {
  curl -sS -X DELETE http://127.0.0.1:8082/internal/lab/projection-fault >/dev/null 2>&1 || true
  curl -sS -X DELETE http://127.0.0.1:8474/proxies/elasticsearch/toxics/m4-latency >/dev/null 2>&1 || true
}
trap cleanup_faults EXIT

wait_http() {
  local name="$1" url="$2"
  poll "$name" 120 "curl -fsS '$url' >/dev/null"
}

group_json() {
  "${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-consumer-groups.sh \
    --bootstrap-server kafka:9092 --group product-search-sync-v1 --describe 2>/dev/null |
    awk '
      $2=="product-search-revisions" && $3~/^[0-9]+$/ {
        committed=$4; lag=$6
        if (committed=="-" && $5==0 && lag=="-") { committed=0; lag=0 }
        if (committed!~/^[0-9]+$/ || $5!~/^[0-9]+$/ || lag!~/^[0-9]+$/) exit 42
        printf "%s{\"partition\":%s,\"committed\":%s,\"end\":%s,\"lag\":%s}", separator,$3,committed,$5,lag
        separator="," }
      END { print "" }' | sed '1s/^/[/' | sed '$s/$/]/' | jq 'sort_by(.partition)'
}

wait_lag_zero() {
  poll "three consumer partitions at lag zero" 120 \
    "group_json | jq -e 'length==3 and all(.[];.lag==0)' >/dev/null"
  group_json >"$case_dir/final-group.json"
}

reset_and_seed() {
  local name="$1"
  case_dir="$evidence_root/$name"
  mkdir -p "$case_dir"
  cleanup_faults
  "${compose[@]}" --profile m0-tools down --volumes --remove-orphans
  make up
  bash infra/mysql/apply-pipeline-control.sh
  bash infra/mysql/apply-reconciliation-control.sh
  make bootstrap-index
  "${compose[@]}" --profile m0-tools up -d --build search-sync-consumer consistency-verifier
  wait_http "consumer health" http://127.0.0.1:8082/actuator/health
  wait_http "verifier health" http://127.0.0.1:8083/actuator/health
  curl -fsS -X POST http://127.0.0.1:8081/api/products \
    -H 'Content-Type: application/json' \
    -d '{"id":1001,"sku":"SKU-1001","name":"Monitor","description":"4K display","categoryId":10,"priceCents":39999}' \
    >"$case_dir/seed.json"
  poll "baseline product revision 1" 120 \
    "curl -fsS http://127.0.0.1:9200/products_write/_doc/1001 | jq -e '._source.source_revision==1' >/dev/null"
  wait_lag_zero
  curl -fsS http://127.0.0.1:9200/products_write/_doc/1001 >"$case_dir/baseline-es.json"
}

run_verification() {
  local output="$1"
  curl -fsS -X POST http://127.0.0.1:9200/products_v2/_refresh >/dev/null
  curl -fsS -X POST http://127.0.0.1:8083/internal/reconciliation/runs \
    -H 'Content-Type: application/json' \
    -d '{"target":"products_write","pageSize":200}' >"$output"
}

assert_one_difference() {
  local report="$1" type="$2" field="${3:-}" run result
  run="$(jq -r '.runId' "$report")"
  jq -e --arg type "$type" '.status=="DIFF" and .differenceCount==1 and .counts[$type]==1' "$report" >/dev/null || {
    cat "$report" >&2; die "unexpected verification classification; wanted $type";
  }
  result="$("${compose[@]}" exec -T mysql mysql -N -B -uroot -prootpass product_catalog -e \
    "SELECT COUNT(*), SUM(product_id=1001 AND difference_type='${type}'$([[ -n "$field" ]] && printf " AND JSON_CONTAINS(fields_json, JSON_OBJECT('field','%s'), '$')" "$field")) FROM verification_difference WHERE run_id=UUID_TO_BIN('${run}');")"
  [[ "$result" == $'1\t1' ]] || { echo "difference rows: $result" >&2; die "persisted difference mismatch"; }
  "${compose[@]}" exec -T mysql mysql -N -B -uroot -prootpass product_catalog -e \
    "SELECT JSON_OBJECT('productId',product_id,'type',difference_type,'fields',fields_json) FROM verification_difference WHERE run_id=UUID_TO_BIN('${run}');" \
    | jq . >"$case_dir/difference.json"
}

repair_and_pass() {
  local report="$1" run
  run="$(jq -r '.runId' "$report")"
  curl -fsS -X POST "http://127.0.0.1:8083/internal/reconciliation/runs/${run}/repair" >"$case_dir/repair.json"
  jq -e '.repaired==true and .failed==0' "$case_dir/repair.json" >/dev/null || die "repair was not conclusive"
  curl -fsS -X POST http://127.0.0.1:9200/products_v2/_refresh >"$case_dir/post-repair-refresh.json"
  run_verification "$case_dir/fresh-pass.json"
  jq -e '.status=="PASS" and .differenceCount==0' "$case_dir/fresh-pass.json" >/dev/null || die "fresh verification did not PASS"
  wait_lag_zero
  curl -fsS http://127.0.0.1:8083/internal/pipeline/status >"$case_dir/final-status.json"
  jq -e '.state=="HEALTHY" and .kafkaLag==0 and .unresolvedDlq==0 and
    .latestRunStatus=="PASS" and .latestDifferenceCount==0 and (.activeConditions|length)==0' \
    "$case_dir/final-status.json" >/dev/null || die "pipeline did not become HEALTHY"
}

put_source() {
  local source_file="$1" url="$2"
  jq -c '._source' "$source_file" | curl -fsS -X PUT "$url" -H 'Content-Type: application/json' --data-binary @- >/dev/null
}

case_missing() {
  reset_and_seed m4-missing-document
  "${compose[@]}" stop search-sync-consumer
  curl -fsS -X DELETE http://127.0.0.1:9200/products_v2 >"$case_dir/corruption.json"
  make bootstrap-index
  "${compose[@]}" --profile m0-tools start search-sync-consumer
  wait_http "consumer restart" http://127.0.0.1:8082/actuator/health
  run_verification "$case_dir/diff-run.json"; assert_one_difference "$case_dir/diff-run.json" MISSING
  repair_and_pass "$case_dir/diff-run.json"
  jq -n --slurpfile run "$case_dir/diff-run.json" --slurpfile pass "$case_dir/fresh-pass.json" \
    '{scenario:"m4-missing-document",classification:$run[0].status,difference:"MISSING",fresh_pass:$pass[0].status}' >"$case_dir/result.json"
}

case_extra() {
  reset_and_seed m4-extra-document
  jq '._source | .product_id=9001 | .sku="EXTRA-9001"' "$case_dir/baseline-es.json" |
    curl -fsS -X PUT 'http://127.0.0.1:9200/products_v2/_doc/9001?version=1&version_type=external' \
      -H 'Content-Type: application/json' --data-binary @- >"$case_dir/corruption.json"
  run_verification "$case_dir/diff-run.json"
  local run; run="$(jq -r '.runId' "$case_dir/diff-run.json")"
  jq -e '.status=="DIFF" and .differenceCount==1 and .counts.EXTRA==1' "$case_dir/diff-run.json" >/dev/null || die "extra classification mismatch"
  "${compose[@]}" exec -T mysql mysql -N -B -uroot -prootpass product_catalog -e \
    "SELECT COUNT(*) FROM verification_difference WHERE run_id=UUID_TO_BIN('${run}') AND product_id=9001 AND difference_type='EXTRA';" |
    grep -qx 1 || die "extra persisted difference mismatch"
  repair_and_pass "$case_dir/diff-run.json"
  jq -n '{scenario:"m4-extra-document",classification:"DIFF",difference:"EXTRA",fresh_pass:"PASS"}' >"$case_dir/result.json"
}

case_modified() {
  reset_and_seed m4-modified-field-same-revision
  jq '._source | .name="corrupted"' "$case_dir/baseline-es.json" |
    curl -fsS -X PUT 'http://127.0.0.1:9200/products_v2/_doc/1001?version=1&version_type=external_gte' \
      -H 'Content-Type: application/json' --data-binary @- >"$case_dir/corruption.json"
  run_verification "$case_dir/diff-run.json"; assert_one_difference "$case_dir/diff-run.json" MODIFIED name
  repair_and_pass "$case_dir/diff-run.json"
  jq -n '{scenario:"m4-modified-field-same-revision",classification:"DIFF",difference:"MODIFIED/name",fresh_pass:"PASS"}' >"$case_dir/result.json"
}

case_stale() {
  reset_and_seed m4-stale-document
  curl -fsS -X PUT http://127.0.0.1:8081/api/products/1001/price -H 'Content-Type: application/json' -d '{"priceCents":40000}' >"$case_dir/mutation.json"
  poll "source revision 2 in Elasticsearch" 120 "curl -fsS http://127.0.0.1:9200/products_write/_doc/1001 | jq -e '._source.source_revision==2' >/dev/null"
  wait_lag_zero
  "${compose[@]}" stop search-sync-consumer
  curl -fsS -X DELETE http://127.0.0.1:9200/products_v2 >/dev/null
  make bootstrap-index
  put_source "$case_dir/baseline-es.json" 'http://127.0.0.1:9200/products_v2/_doc/1001?version=1&version_type=external'
  "${compose[@]}" --profile m0-tools start search-sync-consumer
  wait_http "consumer restart" http://127.0.0.1:8082/actuator/health
  run_verification "$case_dir/diff-run.json"; assert_one_difference "$case_dir/diff-run.json" STALE
  repair_and_pass "$case_dir/diff-run.json"
  jq -n '{scenario:"m4-stale-document",classification:"DIFF",difference:"STALE",fresh_pass:"PASS"}' >"$case_dir/result.json"
}

case_tombstone() {
  reset_and_seed m4-tombstone-mismatch
  curl -fsS -X DELETE http://127.0.0.1:8081/api/products/1001 >"$case_dir/delete.json"
  poll "revision 2 tombstone" 120 "curl -fsS http://127.0.0.1:9200/products_write/_doc/1001 | jq -e '._source.source_revision==2 and ._source.searchable==false' >/dev/null"
  curl -fsS http://127.0.0.1:9200/products_write/_doc/1001 >"$case_dir/tombstone-es.json"
  jq --slurpfile tomb "$case_dir/tombstone-es.json" '._source | .source_revision=2 | .source_updated_at=$tomb[0]._source.source_updated_at | .searchable=true' "$case_dir/baseline-es.json" |
    curl -fsS -X PUT 'http://127.0.0.1:9200/products_v2/_doc/1001?version=2&version_type=external_gte' \
      -H 'Content-Type: application/json' --data-binary @- >"$case_dir/corruption.json"
  run_verification "$case_dir/diff-run.json"; assert_one_difference "$case_dir/diff-run.json" TOMBSTONE_MISMATCH
  repair_and_pass "$case_dir/diff-run.json"
  jq -n '{scenario:"m4-tombstone-mismatch",classification:"DIFF",difference:"TOMBSTONE_MISMATCH",fresh_pass:"PASS"}' >"$case_dir/result.json"
}

case_moving_source() {
  reset_and_seed m4-source-moves-during-scan
  curl -fsS -X POST http://127.0.0.1:8474/proxies/elasticsearch/toxics \
    -H 'Content-Type: application/json' -d '{"name":"m4-latency","type":"latency","stream":"downstream","attributes":{"latency":1500,"jitter":0}}' >"$case_dir/toxic.json"
  curl -fsS -X POST http://127.0.0.1:8083/internal/reconciliation/runs \
    -H 'Content-Type: application/json' -d '{"target":"products_write","pageSize":200}' >"$case_dir/moving-run.json" &
  local request_pid=$!
  poll "RUNNING verification" 30 "${compose[*]} exec -T mysql mysql -N -B -uroot -prootpass product_catalog -e \"SELECT COUNT(*) FROM verification_run WHERE status='RUNNING';\" | grep -Eq '^[1-9]'"
  curl -fsS -X PUT http://127.0.0.1:8081/api/products/1001/price -H 'Content-Type: application/json' -d '{"priceCents":40001}' >"$case_dir/mutation.json"
  wait "$request_pid"
  cleanup_faults
  jq -e '.status=="INCONCLUSIVE"' "$case_dir/moving-run.json" >/dev/null || { cat "$case_dir/moving-run.json" >&2; die "moving source was not inconclusive"; }
  local run status
  run="$(jq -r '.runId' "$case_dir/moving-run.json")"
  status="$(curl -sS -o "$case_dir/repair-rejected.json" -w '%{http_code}' -X POST "http://127.0.0.1:8083/internal/reconciliation/runs/${run}/repair")"
  [[ "$status" == 409 ]] || die "moving-source repair was not rejected"
  jq -e '.message|contains("only a conclusive DIFF")' "$case_dir/repair-rejected.json" >/dev/null || die "unexpected repair rejection"
  jq -n '{scenario:"m4-source-moves-during-scan",classification:"INCONCLUSIVE",repair:"REJECTED"}' >"$case_dir/result.json"
}

case_consumer_bug() {
  reset_and_seed m4-consumer-projection-bug
  curl -fsS -X PUT http://127.0.0.1:8082/internal/lab/projection-fault/CATEGORY_NAME_FROM_ID >"$case_dir/fault-armed.json"
  jq -e '.fault=="CATEGORY_NAME_FROM_ID"' "$case_dir/fault-armed.json" >/dev/null
  curl -fsS -X PUT http://127.0.0.1:8081/api/categories/10 -H 'Content-Type: application/json' -d '{"name":"Computer Accessories"}' >"$case_dir/mutation.json"
  poll "faulted category projection" 120 "curl -fsS http://127.0.0.1:9200/products_write/_doc/1001 | jq -e '._source.source_revision==2 and ._source.category_name==\"10\"' >/dev/null"
  wait_lag_zero
  cleanup_faults
  run_verification "$case_dir/diff-run.json"; assert_one_difference "$case_dir/diff-run.json" MODIFIED category_name
  curl -fsS http://127.0.0.1:8083/internal/pipeline/status >"$case_dir/status-before-repair.json"
  jq -e '.state=="DEGRADED" and .latestRunStatus=="DIFF" and .latestDifferenceCount==1' "$case_dir/status-before-repair.json" >/dev/null || die "pre-repair state was not DEGRADED"
  repair_and_pass "$case_dir/diff-run.json"
  jq -n '{scenario:"m4-consumer-projection-bug",classification:"DIFF",difference:"MODIFIED/category_name",state_before:"DEGRADED",fresh_pass:"PASS",state_after:"HEALTHY"}' >"$case_dir/result.json"
}

default_cases="case_missing case_extra case_modified case_stale case_tombstone case_moving_source case_consumer_bug"
read -r -a cases <<<"${M4_CASES:-$default_cases}"
for scenario_case in "${cases[@]}"; do
  echo "==> ${scenario_case#case_}"
  "$scenario_case"
done

jq -s 'sort_by(.scenario)' "$evidence_root"/*/result.json >"$evidence_root/terminal-classifications.json"
echo "M4 reconciliation matrix passed: $evidence_root"
