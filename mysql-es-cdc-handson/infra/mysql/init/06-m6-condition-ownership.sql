USE product_catalog;

-- Upgrade persistent M5 volumes without resetting rebuild or condition rows.
SET @has_condition_owner = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'pipeline_condition'
    AND COLUMN_NAME = 'owner_rebuild_run_id'
);
SET @ddl = IF(@has_condition_owner = 0,
  'ALTER TABLE pipeline_condition ADD COLUMN owner_rebuild_run_id BINARY(16) NULL AFTER cleared_at',
  'DO 0');
PREPARE statement FROM @ddl;
EXECUTE statement;
DEALLOCATE PREPARE statement;

SET @has_rebuild_reason = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'rebuild_run'
    AND COLUMN_NAME = 'rebuild_reason'
);
SET @ddl = IF(@has_rebuild_reason = 0,
  'ALTER TABLE rebuild_run ADD COLUMN rebuild_reason VARCHAR(64) NOT NULL DEFAULT ''NORMAL'' AFTER topic_name',
  'DO 0');
PREPARE statement FROM @ddl;
EXECUTE statement;
DEALLOCATE PREPARE statement;
