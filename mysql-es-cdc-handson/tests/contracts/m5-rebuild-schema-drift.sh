#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
mysql=(docker compose -f infra/compose.yaml exec -T mysql mysql -uroot -prootpass product_catalog)
cleanup() {
  "${mysql[@]}" -e "ALTER TABLE cdc_barrier ENGINE=InnoDB" >/dev/null 2>&1 || true
  "${mysql[@]}" -e "ALTER TABLE cdc_barrier MODIFY partition_token CHAR(1) NOT NULL" >/dev/null 2>&1 || true
  "${mysql[@]}" -e "ALTER TABLE rebuild_run ADD UNIQUE KEY uk_rebuild_generation(generation_name)" >/dev/null 2>&1 || true
  "${mysql[@]}" -e "ALTER TABLE rebuild_partition_offset ADD CONSTRAINT fk_rebuild_offset_run FOREIGN KEY(run_id) REFERENCES rebuild_run(run_id)" >/dev/null 2>&1 || true
  "${mysql[@]}" -e "ALTER TABLE product_write_gate DROP CHECK chk_product_write_gate_singleton" >/dev/null 2>&1 || true
  "${mysql[@]}" -e "ALTER TABLE product_write_gate ADD CONSTRAINT chk_product_write_gate_singleton CHECK(singleton_id=1)" >/dev/null 2>&1 || true
  "${mysql[@]}" -e "ALTER TABLE cdc_barrier DROP CHECK chk_cdc_barrier_token" >/dev/null 2>&1 || true
  "${mysql[@]}" -e "ALTER TABLE cdc_barrier ADD CONSTRAINT chk_cdc_barrier_token CHECK(partition_token IN ('0','1','2'))" >/dev/null 2>&1 || true
  "${mysql[@]}" -e "GRANT SELECT ON product_catalog.cdc_barrier TO 'verifier'@'%'; FLUSH PRIVILEGES" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM
reject() { if bash infra/mysql/verify-rebuild-control-schema.sh product_catalog >/dev/null 2>&1; then echo "accepted $1 drift" >&2; exit 1; fi; }

"${mysql[@]}" -e "ALTER TABLE cdc_barrier MODIFY partition_token VARCHAR(2) NOT NULL"; reject column
"${mysql[@]}" -e "ALTER TABLE cdc_barrier MODIFY partition_token CHAR(1) NOT NULL"
"${mysql[@]}" -e "ALTER TABLE rebuild_run DROP INDEX uk_rebuild_generation"; reject index
"${mysql[@]}" -e "ALTER TABLE rebuild_run ADD UNIQUE KEY uk_rebuild_generation(generation_name)"
"${mysql[@]}" -e "ALTER TABLE rebuild_partition_offset DROP FOREIGN KEY fk_rebuild_offset_run"; reject foreign-key
"${mysql[@]}" -e "ALTER TABLE rebuild_partition_offset ADD CONSTRAINT fk_rebuild_offset_run FOREIGN KEY(run_id) REFERENCES rebuild_run(run_id)";
"${mysql[@]}" -e "ALTER TABLE product_write_gate DROP CHECK chk_product_write_gate_singleton"; reject check
"${mysql[@]}" -e "ALTER TABLE product_write_gate ADD CONSTRAINT chk_product_write_gate_singleton CHECK(singleton_id=1)"
"${mysql[@]}" -e "ALTER TABLE cdc_barrier ENGINE=MyISAM"; reject engine
"${mysql[@]}" -e "ALTER TABLE cdc_barrier ENGINE=InnoDB"
"${mysql[@]}" -e "ALTER TABLE cdc_barrier DROP CHECK chk_cdc_barrier_token, ADD CONSTRAINT chk_cdc_barrier_token CHECK(partition_token IN ('0','1','2'))"
"${mysql[@]}" -e "REVOKE SELECT ON product_catalog.cdc_barrier FROM 'verifier'@'%'"; reject grant
"${mysql[@]}" -e "GRANT SELECT ON product_catalog.cdc_barrier TO 'verifier'@'%'; FLUSH PRIVILEGES"
bash infra/mysql/verify-rebuild-control-schema.sh product_catalog >/dev/null
echo "M5 rebuild live drift negatives passed"
