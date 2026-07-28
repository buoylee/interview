#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
schema="${1:-product_catalog}"
[[ "$schema" =~ ^[a-zA-Z0-9_]+$ ]] || exit 2
for table in product_write_gate cdc_barrier rebuild_run rebuild_partition_offset canal_position_recovery; do
  docker compose -f infra/compose.yaml exec -T mysql mysql -uroot -prootpass -N -B -e \
    "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='$schema' AND TABLE_NAME='$table'" 2>/dev/null | grep -qx "$table"
done
docker compose -f infra/compose.yaml exec -T mysql mysql -uroot -prootpass -N -B -e \
  "SELECT CONCAT(COUNT(*),':',MIN(singleton_id),':',MIN(closed)) FROM $schema.product_write_gate" 2>/dev/null | grep -qx '1:1:0'
contracts="$(docker compose -f infra/compose.yaml exec -T mysql mysql -uroot -prootpass -N -B -e "
SELECT CONCAT(TABLE_NAME,':',CONSTRAINT_NAME,':',CONSTRAINT_TYPE) FROM information_schema.TABLE_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA='$schema' AND TABLE_NAME IN ('product_write_gate','cdc_barrier','rebuild_run','rebuild_partition_offset','canal_position_recovery')
AND CONSTRAINT_NAME IN ('chk_product_write_gate_singleton','chk_cdc_barrier_token','uk_rebuild_generation','fk_rebuild_offset_run','uk_canal_recovery_run','fk_canal_recovery_run') ORDER BY TABLE_NAME,CONSTRAINT_NAME;
" 2>/dev/null)"
[[ "$(printf '%s\n' "$contracts" | wc -l | tr -d ' ')" == 6 ]] || { echo "rebuild FK/index/check drift detected" >&2; exit 1; }
grants="$(docker compose -f infra/compose.yaml exec -T mysql mysql -uroot -prootpass -N -B -e "
SELECT COUNT(*) FROM information_schema.TABLE_PRIVILEGES WHERE GRANTEE=\"'verifier'@'%'\" AND TABLE_SCHEMA='$schema'
AND TABLE_NAME IN ('product_write_gate','cdc_barrier','rebuild_run','rebuild_partition_offset','canal_position_recovery');" 2>/dev/null)"
[[ "$grants" == 13 ]] || { echo "rebuild grant drift detected: $grants" >&2; exit 1; }
echo "rebuild control schema contract passed"
