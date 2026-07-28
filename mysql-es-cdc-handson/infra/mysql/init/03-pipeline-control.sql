USE product_catalog;

CREATE TABLE IF NOT EXISTS sync_dlq_record (
  event_id VARCHAR(300) NOT NULL,
  topic_name VARCHAR(200) NOT NULL,
  partition_no INT NOT NULL,
  offset_no BIGINT NOT NULL,
  product_id BIGINT NOT NULL,
  source_revision BIGINT NOT NULL,
  payload JSON NOT NULL,
  failure_class VARCHAR(100) NOT NULL,
  last_error TEXT NOT NULL,
  status VARCHAR(20) NOT NULL,
  attempts INT NOT NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6),
  resolved_at TIMESTAMP(6) NULL,
  PRIMARY KEY (event_id),
  UNIQUE KEY uk_dlq_source_product
    (topic_name, partition_no, offset_no, product_id),
  KEY ix_dlq_status_created (status, created_at),
  CONSTRAINT ck_dlq_identity CHECK (
    event_id = CONCAT(topic_name, ':', partition_no, ':', offset_no, ':', product_id)
  ),
  CONSTRAINT ck_dlq_coordinates CHECK (
    partition_no >= 0 AND offset_no >= 0 AND product_id > 0 AND source_revision > 0
  ),
  CONSTRAINT ck_dlq_attempts CHECK (attempts > 0),
  CONSTRAINT ck_dlq_lifecycle CHECK (
    (status = 'PENDING' AND resolved_at IS NULL)
    OR (status = 'RESOLVED' AND resolved_at IS NOT NULL)
  )
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sync_record_dlq (
  record_id VARCHAR(300) NOT NULL,
  topic_name VARCHAR(200) NOT NULL,
  partition_no INT NOT NULL,
  offset_no BIGINT NOT NULL,
  raw_key TEXT NULL,
  raw_payload MEDIUMTEXT NOT NULL,
  failure_class VARCHAR(100) NOT NULL,
  last_error TEXT NOT NULL,
  status VARCHAR(20) NOT NULL,
  attempts INT NOT NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6),
  resolved_at TIMESTAMP(6) NULL,
  PRIMARY KEY (record_id),
  UNIQUE KEY uk_record_dlq_source (topic_name, partition_no, offset_no),
  KEY ix_record_dlq_status_created (status, created_at),
  CONSTRAINT ck_record_dlq_identity CHECK (
    record_id = CONCAT(topic_name, ':', partition_no, ':', offset_no)
  ),
  CONSTRAINT ck_record_dlq_coordinates CHECK (partition_no >= 0 AND offset_no >= 0),
  CONSTRAINT ck_record_dlq_attempts CHECK (attempts > 0),
  CONSTRAINT ck_record_dlq_lifecycle CHECK (
    (status = 'PENDING' AND resolved_at IS NULL)
    OR (status = 'RESOLVED' AND resolved_at IS NOT NULL)
  )
) ENGINE=InnoDB;
