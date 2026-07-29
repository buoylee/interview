USE product_catalog;

CREATE TABLE IF NOT EXISTS product_write_gate (
  singleton_id TINYINT UNSIGNED NOT NULL,
  closed BOOLEAN NOT NULL DEFAULT FALSE,
  owner_run_id BINARY(16) NULL,
  reason VARCHAR(255) NULL,
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (singleton_id),
  CONSTRAINT chk_product_write_gate_singleton CHECK (singleton_id = 1)
) ENGINE=InnoDB;
INSERT INTO product_write_gate(singleton_id, closed) VALUES (1, FALSE)
ON DUPLICATE KEY UPDATE singleton_id = singleton_id;

CREATE TABLE IF NOT EXISTS cdc_barrier (
  run_id BINARY(16) NOT NULL,
  partition_token CHAR(1) NOT NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (run_id, partition_token),
  CONSTRAINT chk_cdc_barrier_token CHECK (partition_token IN ('0','1','2'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS rebuild_run (
  run_id BINARY(16) NOT NULL, generation_name VARCHAR(128) NOT NULL,
  topic_name VARCHAR(128) NOT NULL DEFAULT 'product-search-revisions',
  rebuild_reason VARCHAR(64) NOT NULL DEFAULT 'NORMAL',
  page_size INT NOT NULL DEFAULT 200,
  status ENUM('CREATED','CANAL_RECOVERY_REQUIRED','CANAL_RECOVERING','SNAPSHOTTING','REPLAYING','GATING','VERIFYING','CUTTING_OVER','CUTOVER_COMMITTED','COMPLETED','FAILED') NOT NULL,
  source_watermark BIGINT UNSIGNED NULL, source_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  verification_run_id BINARY(16) NULL, canal_recovery_id BINARY(16) NULL,
  alias_swapped BOOLEAN NOT NULL DEFAULT FALSE,
  started_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), finished_at TIMESTAMP(6) NULL,
  failure_phase VARCHAR(64) NULL, failure_message VARCHAR(512) NULL,
  PRIMARY KEY (run_id), UNIQUE KEY uk_rebuild_generation (generation_name),
  CONSTRAINT chk_rebuild_page_size CHECK (page_size BETWEEN 1 AND 1000)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS rebuild_partition_offset (
  run_id BINARY(16) NOT NULL, phase ENUM('START','SHADOW','BARRIER') NOT NULL,
  topic_name VARCHAR(128) NOT NULL, partition_id INT NOT NULL, next_offset BIGINT NOT NULL,
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (run_id, phase, topic_name, partition_id),
  CONSTRAINT fk_rebuild_offset_run FOREIGN KEY (run_id) REFERENCES rebuild_run(run_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS canal_position_recovery (
  recovery_id BINARY(16) NOT NULL, rebuild_run_id BINARY(16) NOT NULL,
  status ENUM('STARTED','CURSOR_BACKED_UP','RESET_BOOTED','RESET_ANCHORS_ACKED','NORMAL_RESTART_VERIFIED','NORMAL_SENTINELS_OBSERVED','COMPLETED','FAILED') NOT NULL,
  cursor_path VARCHAR(255) NOT NULL, cursor_backup_path VARCHAR(255) NOT NULL,
  old_cursor_sha256 CHAR(64) NOT NULL, old_journal_name VARCHAR(255) NOT NULL, old_position BIGINT NOT NULL,
  retained_binlog_files_json JSON NULL,
  reset_lower_bound_journal VARCHAR(255) NULL, reset_lower_bound_file_index INT NULL, reset_lower_bound_position BIGINT NULL,
  reset_cursor_sha256 CHAR(64) NULL, reset_journal_name VARCHAR(255) NULL, reset_file_index INT NULL, reset_position BIGINT NULL,
  reset_anchor_run_id BINARY(16) NULL, reset_anchor_offsets_json JSON NULL, reset_anchor_events_json JSON NULL,
  reset_restart_offsets_before_json JSON NULL,
  normal_restart_cursor_sha256 CHAR(64) NULL, normal_restart_journal_name VARCHAR(255) NULL,
  normal_restart_file_index INT NULL, normal_restart_position BIGINT NULL, normal_restart_offsets_after_json JSON NULL,
  normal_sentinel_run_id BINARY(16) NULL, normal_sentinel_offsets_json JSON NULL, normal_sentinel_events_json JSON NULL,
  started_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), finished_at TIMESTAMP(6) NULL,
  failure_message VARCHAR(512) NULL,
  PRIMARY KEY (recovery_id), UNIQUE KEY uk_canal_recovery_run (rebuild_run_id),
  CONSTRAINT fk_canal_recovery_run FOREIGN KEY (rebuild_run_id) REFERENCES rebuild_run(run_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS canal_recovery_observation (
  rebuild_run_id BINARY(16) NOT NULL,
  kind ENUM('RESET_ANCHOR','NORMAL_SENTINEL') NOT NULL,
  marker_run_id BINARY(16) NOT NULL,
  pre_offsets_json JSON NOT NULL, observed_offsets_json JSON NOT NULL, events_json JSON NOT NULL,
  observed_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (rebuild_run_id, kind), UNIQUE KEY uk_canal_observation_marker (marker_run_id),
  CONSTRAINT fk_canal_observation_run FOREIGN KEY (rebuild_run_id) REFERENCES rebuild_run(run_id)
) ENGINE=InnoDB;

GRANT SELECT, UPDATE ON product_catalog.product_write_gate TO 'verifier'@'%';
GRANT SELECT, INSERT ON product_catalog.cdc_barrier TO 'verifier'@'%';
GRANT SELECT, INSERT, UPDATE ON product_catalog.rebuild_run TO 'verifier'@'%';
GRANT SELECT, INSERT, UPDATE ON product_catalog.rebuild_partition_offset TO 'verifier'@'%';
GRANT SELECT, INSERT, UPDATE ON product_catalog.rebuild_partition_offset TO 'product'@'%';
GRANT SELECT, INSERT, UPDATE ON product_catalog.canal_position_recovery TO 'verifier'@'%';
GRANT SELECT, INSERT ON product_catalog.canal_recovery_observation TO 'verifier'@'%';
FLUSH PRIVILEGES;
