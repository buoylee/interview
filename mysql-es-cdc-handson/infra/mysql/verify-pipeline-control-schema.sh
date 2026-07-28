#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
control_schema="${1:-product_catalog}"
if [[ ! "$control_schema" =~ ^[a-zA-Z0-9_]+$ ]]; then
  echo "invalid control schema" >&2
  exit 1
fi

schema_shape="$({
  docker compose -f infra/compose.yaml exec -T mysql \
    mysql -uroot -prootpass -N -B -e "
      SELECT CONCAT('columns:', TABLE_NAME, ':', GROUP_CONCAT(
        CONCAT(COLUMN_NAME, ':', COLUMN_TYPE, ':', IS_NULLABLE)
        ORDER BY ORDINAL_POSITION SEPARATOR ','))
      FROM information_schema.COLUMNS
      WHERE TABLE_SCHEMA='$control_schema'
        AND TABLE_NAME IN ('sync_dlq_record', 'sync_record_dlq')
      GROUP BY TABLE_NAME
      UNION ALL
      SELECT CONCAT('indexes:', TABLE_NAME, ':', GROUP_CONCAT(
        CONCAT(INDEX_NAME, ':', NON_UNIQUE, ':', SEQ_IN_INDEX, ':', COLUMN_NAME)
        ORDER BY INDEX_NAME, SEQ_IN_INDEX SEPARATOR ','))
      FROM information_schema.STATISTICS
      WHERE TABLE_SCHEMA='$control_schema'
        AND TABLE_NAME IN ('sync_dlq_record', 'sync_record_dlq')
      GROUP BY TABLE_NAME
      UNION ALL
      SELECT CONCAT('constraints:', TABLE_NAME, ':', GROUP_CONCAT(
        CONCAT(CONSTRAINT_NAME, ':', CONSTRAINT_TYPE)
        ORDER BY CONSTRAINT_NAME SEPARATOR ','))
      FROM information_schema.TABLE_CONSTRAINTS
      WHERE TABLE_SCHEMA='$control_schema'
        AND TABLE_NAME IN ('sync_dlq_record', 'sync_record_dlq')
      GROUP BY TABLE_NAME
      UNION ALL
      SELECT CONCAT('checks:', tc.TABLE_NAME, ':', GROUP_CONCAT(
        CONCAT(tc.CONSTRAINT_NAME, ':', LOWER(
          REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
            cc.CHECK_CLAUSE, CHAR(96), ''), '_latin1', ''), CHAR(92), ''),
            ' ', ''), CHAR(9), ''), CHAR(10), ''), CHAR(13), '')))
        ORDER BY tc.CONSTRAINT_NAME SEPARATOR ','))
      FROM information_schema.TABLE_CONSTRAINTS tc
      JOIN information_schema.CHECK_CONSTRAINTS cc
        ON cc.CONSTRAINT_SCHEMA=tc.CONSTRAINT_SCHEMA
       AND cc.CONSTRAINT_NAME=tc.CONSTRAINT_NAME
      WHERE tc.CONSTRAINT_SCHEMA='$control_schema'
        AND tc.TABLE_NAME IN ('sync_dlq_record', 'sync_record_dlq')
      GROUP BY tc.TABLE_NAME;
    " 2>/dev/null
} | LC_ALL=C sort)"

expected_shape="$(printf '%s\n' \
  "checks:sync_dlq_record:ck_dlq_attempts:(attempts>0),ck_dlq_coordinates:((partition_no>=0)and(offset_no>=0)and(product_id>0)and(source_revision>0)),ck_dlq_identity:(event_id=concat(topic_name,':',partition_no,':',offset_no,':',product_id)),ck_dlq_lifecycle:(((status='pending')and(resolved_atisnull))or((status='resolved')and(resolved_atisnotnull)))" \
  "checks:sync_record_dlq:ck_record_dlq_attempts:(attempts>0),ck_record_dlq_coordinates:((partition_no>=0)and(offset_no>=0)),ck_record_dlq_identity:(record_id=concat(topic_name,':',partition_no,':',offset_no)),ck_record_dlq_lifecycle:(((status='pending')and(resolved_atisnull))or((status='resolved')and(resolved_atisnotnull)))" \
  'columns:sync_dlq_record:event_id:varchar(300):NO,topic_name:varchar(200):NO,partition_no:int:NO,offset_no:bigint:NO,product_id:bigint:NO,source_revision:bigint:NO,payload:json:NO,failure_class:varchar(100):NO,last_error:text:NO,status:varchar(20):NO,attempts:int:NO,created_at:timestamp(6):NO,updated_at:timestamp(6):NO,resolved_at:timestamp(6):YES' \
  'columns:sync_record_dlq:record_id:varchar(300):NO,topic_name:varchar(200):NO,partition_no:int:NO,offset_no:bigint:NO,raw_key:text:YES,raw_payload:mediumtext:NO,failure_class:varchar(100):NO,last_error:text:NO,status:varchar(20):NO,attempts:int:NO,created_at:timestamp(6):NO,updated_at:timestamp(6):NO,resolved_at:timestamp(6):YES' \
  'constraints:sync_dlq_record:ck_dlq_attempts:CHECK,ck_dlq_coordinates:CHECK,ck_dlq_identity:CHECK,ck_dlq_lifecycle:CHECK,PRIMARY:PRIMARY KEY,uk_dlq_source_product:UNIQUE' \
  'constraints:sync_record_dlq:ck_record_dlq_attempts:CHECK,ck_record_dlq_coordinates:CHECK,ck_record_dlq_identity:CHECK,ck_record_dlq_lifecycle:CHECK,PRIMARY:PRIMARY KEY,uk_record_dlq_source:UNIQUE' \
  'indexes:sync_dlq_record:ix_dlq_status_created:1:1:status,ix_dlq_status_created:1:2:created_at,PRIMARY:0:1:event_id,uk_dlq_source_product:0:1:topic_name,uk_dlq_source_product:0:2:partition_no,uk_dlq_source_product:0:3:offset_no,uk_dlq_source_product:0:4:product_id' \
  'indexes:sync_record_dlq:ix_record_dlq_status_created:1:1:status,ix_record_dlq_status_created:1:2:created_at,PRIMARY:0:1:record_id,uk_record_dlq_source:0:1:topic_name,uk_record_dlq_source:0:2:partition_no,uk_record_dlq_source:0:3:offset_no' \
  | LC_ALL=C sort)"

if [[ "$schema_shape" != "$expected_shape" ]]; then
  echo "pipeline control schema drift detected" >&2
  diff -u <(printf '%s\n' "$expected_shape") <(printf '%s\n' "$schema_shape") >&2 || true
  exit 1
fi
