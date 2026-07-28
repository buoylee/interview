#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
mysql=(docker compose -f infra/compose.yaml exec -T mysql mysql -uroot -prootpass product_catalog)
run="00000000-0000-0000-0000-00000000a551"
cleanup() {
  "${mysql[@]}" -e "DELETE FROM cdc_barrier WHERE run_id=UUID_TO_BIN('$run'); DELETE FROM rebuild_run WHERE run_id=UUID_TO_BIN('$run'); UPDATE product_write_gate SET reason=NULL WHERE singleton_id=1" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM
cleanup
"${mysql[@]}" -e "UPDATE product_write_gate SET reason='repeat-apply-sentinel' WHERE singleton_id=1; INSERT INTO rebuild_run(run_id,generation_name,status,source_count) VALUES(UUID_TO_BIN('$run'),'repeat-apply-sentinel','CREATED',17); INSERT INTO cdc_barrier(run_id,partition_token) VALUES(UUID_TO_BIN('$run'),'0')"
before="$("${mysql[@]}" -N -B -e "SELECT CONCAT(reason,':',closed) FROM product_write_gate WHERE singleton_id=1; SELECT CONCAT(generation_name,':',status,':',source_count) FROM rebuild_run WHERE run_id=UUID_TO_BIN('$run'); SELECT partition_token FROM cdc_barrier WHERE run_id=UUID_TO_BIN('$run')")"
for round in 1 2; do
  bash infra/mysql/apply-reconciliation-control.sh >/dev/null
  bash infra/mysql/verify-rebuild-control-schema.sh product_catalog >/dev/null
  after="$("${mysql[@]}" -N -B -e "SELECT CONCAT(reason,':',closed) FROM product_write_gate WHERE singleton_id=1; SELECT CONCAT(generation_name,':',status,':',source_count) FROM rebuild_run WHERE run_id=UUID_TO_BIN('$run'); SELECT partition_token FROM cdc_barrier WHERE run_id=UUID_TO_BIN('$run')")"
  [[ "$after" == "$before" ]] || { echo "repeat apply reset persisted data in round $round" >&2; exit 1; }
done
echo "M5 rebuild repeat-apply contract passed"
