USE product_catalog;

CREATE TABLE IF NOT EXISTS source_change_watermark (
  singleton_id TINYINT UNSIGNED NOT NULL,
  value BIGINT UNSIGNED NOT NULL,
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (singleton_id),
  CONSTRAINT chk_source_watermark_singleton CHECK (singleton_id = 1)
) ENGINE=InnoDB COMMENT='Change epoch counted from reconciliation control-plane installation';

-- Existing facts predate this change epoch. Re-applying preserves any installed epoch.
INSERT INTO source_change_watermark(singleton_id, value)
VALUES (1, 0)
ON DUPLICATE KEY UPDATE value = value;

CREATE TABLE IF NOT EXISTS verification_run (
  run_id BINARY(16) NOT NULL,
  target_name VARCHAR(128) NOT NULL,
  status ENUM('RUNNING','PASS','DIFF','INCONCLUSIVE','REPAIRED','FAILED') NOT NULL,
  source_watermark_start BIGINT UNSIGNED NOT NULL,
  source_watermark_end BIGINT UNSIGNED NULL,
  expected_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  actual_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  difference_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  started_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  finished_at TIMESTAMP(6) NULL,
  failure_class VARCHAR(64) NULL,
  failure_message VARCHAR(512) NULL,
  PRIMARY KEY (run_id),
  KEY idx_verification_run_finished (finished_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS verification_difference (
  run_id BINARY(16) NOT NULL,
  product_id BIGINT UNSIGNED NOT NULL,
  difference_type ENUM('MISSING','EXTRA','MODIFIED','STALE','FUTURE_REVISION','TOMBSTONE_MISMATCH','VERSION_METADATA_MISMATCH') NOT NULL,
  expected_revision BIGINT UNSIGNED NULL,
  actual_revision BIGINT UNSIGNED NULL,
  expected_json JSON NULL,
  actual_json JSON NULL,
  fields_json JSON NOT NULL,
  repaired_at TIMESTAMP(6) NULL,
  repair_outcome VARCHAR(64) NULL,
  PRIMARY KEY (run_id, product_id, difference_type),
  CONSTRAINT fk_verification_difference_run
    FOREIGN KEY (run_id) REFERENCES verification_run(run_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS pipeline_condition (
  condition_key VARCHAR(64) NOT NULL,
  active BOOLEAN NOT NULL,
  details_json JSON NOT NULL,
  observed_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  cleared_at TIMESTAMP(6) NULL,
  PRIMARY KEY (condition_key)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS repair_action (
  action_id BINARY(16) NOT NULL,
  run_id BINARY(16) NOT NULL,
  product_id BIGINT UNSIGNED NOT NULL,
  action_type ENUM('WRITE_EXTERNAL','WRITE_EXTERNAL_GTE','DELETE_EXTRA') NOT NULL,
  source_watermark BIGINT UNSIGNED NOT NULL,
  source_revision BIGINT UNSIGNED NULL,
  outcome ENUM('STARTED','APPLIED','STALE','FAILED') NOT NULL,
  started_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  finished_at TIMESTAMP(6) NULL,
  error_message VARCHAR(512) NULL,
  PRIMARY KEY (action_id),
  UNIQUE KEY uk_repair_action_run_product (run_id, product_id),
  CONSTRAINT fk_repair_action_run FOREIGN KEY (run_id) REFERENCES verification_run(run_id)
) ENGINE=InnoDB;

GRANT INSERT, UPDATE, DELETE, SELECT
ON product_catalog.verification_run TO 'verifier'@'%';
GRANT INSERT, UPDATE, DELETE, SELECT
ON product_catalog.verification_difference TO 'verifier'@'%';
GRANT INSERT, UPDATE, DELETE, SELECT
ON product_catalog.pipeline_condition TO 'verifier'@'%';
GRANT INSERT, UPDATE, DELETE, SELECT
ON product_catalog.repair_action TO 'verifier'@'%';
FLUSH PRIVILEGES;
