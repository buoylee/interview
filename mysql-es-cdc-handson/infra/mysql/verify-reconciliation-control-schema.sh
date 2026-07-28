#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
control_schema="${1:-product_catalog}"
if [[ ! "$control_schema" =~ ^[a-zA-Z0-9_]+$ ]]; then
  echo "invalid control schema" >&2
  exit 1
fi

tables="'source_change_watermark','verification_run','verification_difference','pipeline_condition','repair_action'"
actual="$({
  docker compose -f infra/compose.yaml exec -T mysql mysql -uroot -prootpass -N -B -e "
    SELECT CONCAT('column:', TABLE_NAME, ':', ORDINAL_POSITION, ':', COLUMN_NAME, ':', COLUMN_TYPE,
      ':', IS_NULLABLE, ':', IFNULL(COLUMN_DEFAULT, '<NULL>'), ':', EXTRA)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA='$control_schema' AND TABLE_NAME IN ($tables)
    UNION ALL
    SELECT CONCAT('index:', TABLE_NAME, ':', INDEX_NAME, ':', NON_UNIQUE, ':', SEQ_IN_INDEX, ':', COLUMN_NAME)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA='$control_schema' AND TABLE_NAME IN ($tables)
    UNION ALL
    SELECT CONCAT('constraint:', TABLE_NAME, ':', CONSTRAINT_NAME, ':', CONSTRAINT_TYPE)
    FROM information_schema.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA='$control_schema' AND TABLE_NAME IN ($tables)
    UNION ALL
    SELECT CONCAT('check:', tc.TABLE_NAME, ':', tc.CONSTRAINT_NAME, ':', LOWER(
      REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
        cc.CHECK_CLAUSE, CHAR(96), ''), '_latin1', ''), CHAR(92), ''),
        ' ', ''), CHAR(9), ''), CHAR(10), ''), CHAR(13), '')))
    FROM information_schema.TABLE_CONSTRAINTS tc
    JOIN information_schema.CHECK_CONSTRAINTS cc
      ON cc.CONSTRAINT_SCHEMA=tc.CONSTRAINT_SCHEMA AND cc.CONSTRAINT_NAME=tc.CONSTRAINT_NAME
    WHERE tc.CONSTRAINT_SCHEMA='$control_schema' AND tc.TABLE_NAME IN ($tables)
    UNION ALL
    SELECT CONCAT('fk:', TABLE_NAME, ':', CONSTRAINT_NAME, ':', COLUMN_NAME, ':',
      REFERENCED_TABLE_NAME, ':', REFERENCED_COLUMN_NAME)
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA='$control_schema' AND TABLE_NAME IN ($tables)
      AND REFERENCED_TABLE_NAME IS NOT NULL
    UNION ALL
    SELECT CONCAT('table:', TABLE_NAME, ':', ENGINE, ':', TABLE_COLLATION, ':', TABLE_COMMENT)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA='$control_schema' AND TABLE_NAME IN ($tables);
  " 2>/dev/null
} | LC_ALL=C sort)"

expected="$(printf '%s\n' \
  'check:source_change_watermark:chk_source_watermark_singleton:(singleton_id=1)' \
  'column:pipeline_condition:1:condition_key:varchar(64):NO:<NULL>:' \
  'column:pipeline_condition:2:active:tinyint(1):NO:<NULL>:' \
  'column:pipeline_condition:3:details_json:json:NO:<NULL>:' \
  'column:pipeline_condition:4:observed_at:timestamp(6):NO:CURRENT_TIMESTAMP(6):DEFAULT_GENERATED' \
  'column:pipeline_condition:5:cleared_at:timestamp(6):YES:<NULL>:' \
  'column:repair_action:1:action_id:binary(16):NO:<NULL>:' \
  'column:repair_action:2:run_id:binary(16):NO:<NULL>:' \
  'column:repair_action:3:product_id:bigint unsigned:NO:<NULL>:' \
  "column:repair_action:4:action_type:enum('WRITE_EXTERNAL','WRITE_EXTERNAL_GTE','DELETE_EXTRA'):NO:<NULL>:" \
  'column:repair_action:5:source_watermark:bigint unsigned:NO:<NULL>:' \
  'column:repair_action:6:source_revision:bigint unsigned:YES:<NULL>:' \
  "column:repair_action:7:outcome:enum('STARTED','APPLIED','STALE','FAILED'):NO:<NULL>:" \
  'column:repair_action:8:started_at:timestamp(6):NO:CURRENT_TIMESTAMP(6):DEFAULT_GENERATED' \
  'column:repair_action:9:finished_at:timestamp(6):YES:<NULL>:' \
  'column:repair_action:10:error_message:varchar(512):YES:<NULL>:' \
  'column:source_change_watermark:1:singleton_id:tinyint unsigned:NO:<NULL>:' \
  'column:source_change_watermark:2:value:bigint unsigned:NO:<NULL>:' \
  'column:source_change_watermark:3:updated_at:timestamp(6):NO:CURRENT_TIMESTAMP(6):DEFAULT_GENERATED on update CURRENT_TIMESTAMP(6)' \
  'column:verification_difference:1:run_id:binary(16):NO:<NULL>:' \
  'column:verification_difference:2:product_id:bigint unsigned:NO:<NULL>:' \
  "column:verification_difference:3:difference_type:enum('MISSING','EXTRA','MODIFIED','STALE','FUTURE_REVISION','TOMBSTONE_MISMATCH','VERSION_METADATA_MISMATCH'):NO:<NULL>:" \
  'column:verification_difference:4:expected_revision:bigint unsigned:YES:<NULL>:' \
  'column:verification_difference:5:actual_revision:bigint unsigned:YES:<NULL>:' \
  'column:verification_difference:6:expected_json:json:YES:<NULL>:' \
  'column:verification_difference:7:actual_json:json:YES:<NULL>:' \
  'column:verification_difference:8:fields_json:json:NO:<NULL>:' \
  'column:verification_difference:9:repaired_at:timestamp(6):YES:<NULL>:' \
  'column:verification_difference:10:repair_outcome:varchar(64):YES:<NULL>:' \
  'column:verification_run:1:run_id:binary(16):NO:<NULL>:' \
  'column:verification_run:2:target_name:varchar(128):NO:<NULL>:' \
  "column:verification_run:3:status:enum('RUNNING','PASS','DIFF','INCONCLUSIVE','REPAIRED','FAILED'):NO:<NULL>:" \
  'column:verification_run:4:source_watermark_start:bigint unsigned:NO:<NULL>:' \
  'column:verification_run:5:source_watermark_end:bigint unsigned:YES:<NULL>:' \
  'column:verification_run:6:expected_count:bigint unsigned:NO:0:' \
  'column:verification_run:7:actual_count:bigint unsigned:NO:0:' \
  'column:verification_run:8:difference_count:bigint unsigned:NO:0:' \
  'column:verification_run:9:started_at:timestamp(6):NO:CURRENT_TIMESTAMP(6):DEFAULT_GENERATED' \
  'column:verification_run:10:finished_at:timestamp(6):YES:<NULL>:' \
  'column:verification_run:11:failure_class:varchar(64):YES:<NULL>:' \
  'column:verification_run:12:failure_message:varchar(512):YES:<NULL>:' \
  'constraint:pipeline_condition:PRIMARY:PRIMARY KEY' \
  'constraint:repair_action:fk_repair_action_run:FOREIGN KEY' \
  'constraint:repair_action:PRIMARY:PRIMARY KEY' \
  'constraint:repair_action:uk_repair_action_run_product:UNIQUE' \
  'constraint:source_change_watermark:chk_source_watermark_singleton:CHECK' \
  'constraint:source_change_watermark:PRIMARY:PRIMARY KEY' \
  'constraint:verification_difference:fk_verification_difference_run:FOREIGN KEY' \
  'constraint:verification_difference:PRIMARY:PRIMARY KEY' \
  'constraint:verification_run:PRIMARY:PRIMARY KEY' \
  'fk:repair_action:fk_repair_action_run:run_id:verification_run:run_id' \
  'fk:verification_difference:fk_verification_difference_run:run_id:verification_run:run_id' \
  'index:pipeline_condition:PRIMARY:0:1:condition_key' \
  'index:repair_action:PRIMARY:0:1:action_id' \
  'index:repair_action:uk_repair_action_run_product:0:1:run_id' \
  'index:repair_action:uk_repair_action_run_product:0:2:product_id' \
  'index:source_change_watermark:PRIMARY:0:1:singleton_id' \
  'index:verification_difference:PRIMARY:0:1:run_id' \
  'index:verification_difference:PRIMARY:0:2:product_id' \
  'index:verification_difference:PRIMARY:0:3:difference_type' \
  'index:verification_run:idx_verification_run_finished:1:1:finished_at' \
  'index:verification_run:PRIMARY:0:1:run_id' \
  'table:pipeline_condition:InnoDB:utf8mb4_0900_ai_ci:' \
  'table:repair_action:InnoDB:utf8mb4_0900_ai_ci:' \
  'table:source_change_watermark:InnoDB:utf8mb4_0900_ai_ci:Change epoch counted from reconciliation control-plane installation' \
  'table:verification_difference:InnoDB:utf8mb4_0900_ai_ci:' \
  'table:verification_run:InnoDB:utf8mb4_0900_ai_ci:' \
  | LC_ALL=C sort)"

if [[ "$actual" != "$expected" ]]; then
  echo "reconciliation control schema drift detected" >&2
  diff -u <(printf '%s\n' "$expected") <(printf '%s\n' "$actual") >&2 || true
  exit 1
fi

singleton="$(docker compose -f infra/compose.yaml exec -T mysql mysql -uroot -prootpass -N -B \
  -e "SELECT CONCAT(COUNT(*), ':', MIN(singleton_id), ':', MIN(value)) FROM $control_schema.source_change_watermark" 2>/dev/null)"
if [[ ! "$singleton" =~ ^1:1:[0-9]+$ ]]; then
  echo "source watermark singleton seed drift detected: $singleton" >&2
  exit 1
fi

schema_grants="$(docker compose -f infra/compose.yaml exec -T mysql mysql -uroot -prootpass -N -B -e "
  SELECT CONCAT(PRIVILEGE_TYPE, ':', IS_GRANTABLE)
  FROM information_schema.SCHEMA_PRIVILEGES
  WHERE GRANTEE=\"'verifier'@'%'\" AND TABLE_SCHEMA='$control_schema';
" 2>/dev/null | LC_ALL=C sort)"
[[ "$schema_grants" == 'SELECT:NO' ]] || { echo "verifier schema grants drift detected" >&2; exit 1; }

table_grants="$(docker compose -f infra/compose.yaml exec -T mysql mysql -uroot -prootpass -N -B -e "
  SELECT CONCAT(TABLE_NAME, ':', PRIVILEGE_TYPE, ':', IS_GRANTABLE)
  FROM information_schema.TABLE_PRIVILEGES
  WHERE GRANTEE=\"'verifier'@'%'\" AND TABLE_SCHEMA='$control_schema'
    AND TABLE_NAME IN ('verification_run','verification_difference','pipeline_condition','repair_action');
" 2>/dev/null | LC_ALL=C sort)"
expected_grants="$(for table in pipeline_condition repair_action verification_difference verification_run; do
  for privilege in DELETE INSERT SELECT UPDATE; do printf '%s:%s:NO\n' "$table" "$privilege"; done
done)"
[[ "$table_grants" == "$expected_grants" ]] || {
  echo "verifier table grants drift detected" >&2
  diff -u <(printf '%s\n' "$expected_grants") <(printf '%s\n' "$table_grants") >&2 || true
  exit 1
}
