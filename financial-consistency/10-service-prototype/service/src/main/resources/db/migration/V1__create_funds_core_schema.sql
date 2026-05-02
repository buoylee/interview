create table account (
    account_id varchar(64) primary key,
    currency char(3) not null,
    available_balance decimal(19, 4) not null,
    frozen_balance decimal(19, 4) not null default 0.0000,
    version bigint not null default 0,
    created_at timestamp(6) not null default current_timestamp(6),
    updated_at timestamp(6) not null default current_timestamp(6) on update current_timestamp(6),
    constraint chk_account_available_balance_non_negative check (available_balance >= 0),
    constraint chk_account_frozen_balance_non_negative check (frozen_balance >= 0)
) engine = InnoDB default charset = utf8mb4;

create table transfer_order (
    transfer_id varchar(64) primary key,
    request_id varchar(64) not null,
    from_account_id varchar(64) not null,
    to_account_id varchar(64) not null,
    currency char(3) not null,
    amount decimal(19, 4) not null,
    status varchar(16) not null,
    failure_reason varchar(512),
    created_at timestamp(6) not null default current_timestamp(6),
    updated_at timestamp(6) not null default current_timestamp(6) on update current_timestamp(6),
    constraint chk_transfer_order_amount_positive check (amount > 0),
    constraint chk_transfer_order_status check (status in ('INITIATED', 'SUCCEEDED', 'FAILED')),
    unique key uk_transfer_order_request_id (request_id),
    key idx_transfer_order_from_account_id (from_account_id),
    key idx_transfer_order_to_account_id (to_account_id),
    key idx_transfer_order_status_created_at (status, created_at)
) engine = InnoDB default charset = utf8mb4;

create table idempotency_record (
    idempotency_key varchar(128) primary key,
    request_hash char(64) not null,
    business_type varchar(64) not null,
    business_id varchar(64),
    status varchar(16) not null,
    response_code int,
    response_body json,
    created_at timestamp(6) not null default current_timestamp(6),
    updated_at timestamp(6) not null default current_timestamp(6) on update current_timestamp(6),
    constraint chk_idempotency_record_status check (status in ('PROCESSING', 'SUCCEEDED', 'FAILED', 'REJECTED')),
    key idx_idempotency_record_business (business_type, business_id),
    key idx_idempotency_record_status_created_at (status, created_at)
) engine = InnoDB default charset = utf8mb4;

create table ledger_entry (
    entry_id varchar(64) primary key,
    transfer_id varchar(64) not null,
    account_id varchar(64) not null,
    direction varchar(8) not null,
    currency char(3) not null,
    amount decimal(19, 4) not null,
    entry_type varchar(32) not null,
    created_at timestamp(6) not null default current_timestamp(6),
    constraint chk_ledger_entry_direction check (direction in ('DEBIT', 'CREDIT')),
    constraint chk_ledger_entry_amount_positive check (amount > 0),
    unique key uk_ledger_entry_transfer_account_direction_type (transfer_id, account_id, direction, entry_type),
    key idx_ledger_entry_transfer_id (transfer_id),
    key idx_ledger_entry_account_id_created_at (account_id, created_at)
) engine = InnoDB default charset = utf8mb4;

create table outbox_message (
    message_id varchar(64) primary key,
    aggregate_type varchar(64) not null,
    aggregate_id varchar(64) not null,
    event_type varchar(64) not null,
    payload json not null,
    status varchar(32) not null,
    created_at timestamp(6) not null default current_timestamp(6),
    updated_at timestamp(6) not null default current_timestamp(6) on update current_timestamp(6),
    published_at timestamp(6) null,
    attempt_count int not null default 0,
    constraint chk_outbox_message_status check (status in ('PENDING', 'PUBLISHED', 'FAILED_RETRYABLE')),
    key idx_outbox_message_status_created_at (status, created_at),
    key idx_outbox_message_aggregate (aggregate_type, aggregate_id)
) engine = InnoDB default charset = utf8mb4;
