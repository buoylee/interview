#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
schema="${1:-product_catalog}"
[[ "$schema" =~ ^[a-zA-Z0-9_]+$ ]] || exit 2
canonical="m5_contract_${$}"
mysql=(docker compose -f infra/compose.yaml exec -T mysql mysql -uroot -prootpass -N -B)
trap '"${mysql[@]}" -e "DROP DATABASE IF EXISTS $canonical" >/dev/null 2>&1 || true' EXIT
"${mysql[@]}" -e "DROP DATABASE IF EXISTS $canonical; CREATE DATABASE $canonical CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
sed -e "s/USE product_catalog;/USE $canonical;/" -e '/^GRANT /d' -e '/^FLUSH PRIVILEGES/d' infra/mysql/init/05-rebuild-control.sql | "${mysql[@]}"

metadata() {
  local target="$1"
  "${mysql[@]}" -e "
SELECT CONCAT('column:',TABLE_NAME,':',ORDINAL_POSITION,':',COLUMN_NAME,':',COLUMN_TYPE,':',IS_NULLABLE,':',IFNULL(COLUMN_DEFAULT,'<NULL>'),':',EXTRA,':',IFNULL(CHARACTER_SET_NAME,'<NULL>'),':',IFNULL(COLLATION_NAME,'<NULL>'))
FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='$target';
SELECT CONCAT('index:',TABLE_NAME,':',INDEX_NAME,':',NON_UNIQUE,':',SEQ_IN_INDEX,':',IFNULL(COLUMN_NAME,'<NULL>'),':',INDEX_TYPE,':',IS_VISIBLE,':',IFNULL(NULLABLE,'<EMPTY>'),':',IFNULL(COLLATION,'<NULL>'),':',IFNULL(EXPRESSION,'<NULL>'),':',IFNULL(SUB_PART,'<NULL>'))
FROM information_schema.STATISTICS WHERE TABLE_SCHEMA='$target';
SELECT CONCAT('constraint:',TABLE_NAME,':',CONSTRAINT_NAME,':',CONSTRAINT_TYPE)
FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA='$target';
SELECT CONCAT('check:',tc.TABLE_NAME,':',tc.CONSTRAINT_NAME,':',LOWER(REPLACE(REPLACE(REPLACE(REPLACE(cc.CHECK_CLAUSE,' ',''),CHAR(96),''),'_utf8mb4',''),'_latin1','')))
FROM information_schema.TABLE_CONSTRAINTS tc JOIN information_schema.CHECK_CONSTRAINTS cc
ON cc.CONSTRAINT_SCHEMA=tc.CONSTRAINT_SCHEMA AND cc.CONSTRAINT_NAME=tc.CONSTRAINT_NAME WHERE tc.CONSTRAINT_SCHEMA='$target';
SELECT CONCAT('fk:',TABLE_NAME,':',CONSTRAINT_NAME,':',COLUMN_NAME,':',REFERENCED_TABLE_NAME,':',REFERENCED_COLUMN_NAME)
FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA='$target' AND REFERENCED_TABLE_NAME IS NOT NULL;
SELECT CONCAT('fk_rule:',TABLE_NAME,':',CONSTRAINT_NAME,':',UPDATE_RULE,':',DELETE_RULE)
FROM information_schema.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA='$target';
SELECT CONCAT('table:',TABLE_NAME,':',ENGINE,':',TABLE_COLLATION)
FROM information_schema.TABLES WHERE TABLE_SCHEMA='$target';" 2>/dev/null | LC_ALL=C sort
}
actual="$(metadata "$schema" | grep -E ':(product_write_gate|cdc_barrier|rebuild_run|rebuild_partition_offset|canal_position_recovery|canal_recovery_observation):|^(column|index|constraint|check|fk|fk_rule|table):(product_write_gate|cdc_barrier|rebuild_run|rebuild_partition_offset|canal_position_recovery|canal_recovery_observation):')"
expected="$(metadata "$canonical")"
[[ "$actual" == "$expected" ]] || { echo "rebuild exact schema drift detected" >&2; diff -u <(printf '%s\n' "$expected") <(printf '%s\n' "$actual") >&2 || true; exit 1; }

"${mysql[@]}" -e "SELECT CONCAT(COUNT(*),':',MIN(singleton_id),':',MIN(closed)) FROM $schema.product_write_gate" 2>/dev/null | grep -qx '1:1:0'
grants="$("${mysql[@]}" -e "SELECT CONCAT(TABLE_NAME,':',PRIVILEGE_TYPE,':',IS_GRANTABLE) FROM information_schema.TABLE_PRIVILEGES WHERE GRANTEE=\"'verifier'@'%'\" AND TABLE_SCHEMA='$schema' AND TABLE_NAME IN ('product_write_gate','cdc_barrier','rebuild_run','rebuild_partition_offset','canal_position_recovery','canal_recovery_observation') ORDER BY TABLE_NAME,PRIVILEGE_TYPE" 2>/dev/null)"
expected_grants=$'canal_position_recovery:INSERT:NO\ncanal_position_recovery:SELECT:NO\ncanal_position_recovery:UPDATE:NO\ncanal_recovery_observation:INSERT:NO\ncanal_recovery_observation:SELECT:NO\ncdc_barrier:INSERT:NO\ncdc_barrier:SELECT:NO\nproduct_write_gate:SELECT:NO\nproduct_write_gate:UPDATE:NO\nrebuild_partition_offset:INSERT:NO\nrebuild_partition_offset:SELECT:NO\nrebuild_partition_offset:UPDATE:NO\nrebuild_run:INSERT:NO\nrebuild_run:SELECT:NO\nrebuild_run:UPDATE:NO'
[[ "$grants" == "$expected_grants" ]] || { echo "rebuild exact grant drift detected" >&2; diff -u <(printf '%s\n' "$expected_grants") <(printf '%s\n' "$grants") >&2 || true; exit 1; }
echo "rebuild exact schema contract passed"
