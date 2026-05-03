create table account (
  account_id varchar(64) not null primary key,
  currency varchar(3) not null,
  available_balance decimal(19, 4) not null,
  frozen_balance decimal(19, 4) not null default 0.0000,
  version bigint not null default 0,
  created_at timestamp(6) not null default current_timestamp(6),
  updated_at timestamp(6) not null default current_timestamp(6) on update current_timestamp(6),
  constraint chk_account_available_non_negative check (available_balance >= 0),
  constraint chk_account_frozen_non_negative check (frozen_balance >= 0)
);

create table transfer_order (
  transfer_id varchar(64) not null primary key,
  request_id varchar(128) not null,
  from_account_id varchar(64) not null,
  to_account_id varchar(64) not null,
  currency varchar(3) not null,
  amount decimal(19, 4) not null,
  status varchar(32) not null,
  failure_reason varchar(255),
  created_at timestamp(6) not null default current_timestamp(6),
  updated_at timestamp(6) not null default current_timestamp(6) on update current_timestamp(6),
  constraint chk_transfer_amount_positive check (amount > 0),
  constraint chk_transfer_status check (status in ('INITIATED', 'SUCCEEDED', 'FAILED')),
  index idx_transfer_request_id (request_id),
  index idx_transfer_from_account (from_account_id),
  index idx_transfer_to_account (to_account_id)
);

create table idempotency_record (
  idempotency_key varchar(128) not null primary key,
  request_hash char(64) not null,
  business_type varchar(64) not null,
  business_id varchar(64),
  status varchar(32) not null,
  response_code int,
  response_body text,
  created_at timestamp(6) not null default current_timestamp(6),
  updated_at timestamp(6) not null default current_timestamp(6) on update current_timestamp(6),
  constraint chk_idempotency_status check (status in ('PROCESSING', 'SUCCEEDED', 'FAILED', 'REJECTED'))
);

create table ledger_entry (
  entry_id varchar(64) not null primary key,
  transfer_id varchar(64) not null,
  account_id varchar(64) not null,
  direction varchar(16) not null,
  currency varchar(3) not null,
  amount decimal(19, 4) not null,
  entry_type varchar(32) not null,
  created_at timestamp(6) not null default current_timestamp(6),
  constraint chk_ledger_direction check (direction in ('DEBIT', 'CREDIT')),
  constraint chk_ledger_amount_positive check (amount > 0),
  unique key uk_ledger_transfer_account_direction_type (transfer_id, account_id, direction, entry_type),
  index idx_ledger_transfer_id (transfer_id),
  index idx_ledger_account_id (account_id)
);

create table outbox_message (
  message_id varchar(64) not null primary key,
  aggregate_type varchar(64) not null,
  aggregate_id varchar(64) not null,
  event_type varchar(64) not null,
  payload json not null,
  status varchar(32) not null,
  created_at timestamp(6) not null default current_timestamp(6),
  updated_at timestamp(6) not null default current_timestamp(6) on update current_timestamp(6),
  published_at timestamp(6) null,
  attempt_count int not null default 0,
  constraint chk_outbox_status check (status in ('PENDING', 'PUBLISHED', 'FAILED_RETRYABLE')),
  index idx_outbox_status_created (status, created_at),
  index idx_outbox_aggregate (aggregate_type, aggregate_id)
);
