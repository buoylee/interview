alter table outbox_message
  drop check chk_outbox_status;

alter table outbox_message
  add column locked_at timestamp(6) null,
  add column locked_by varchar(128) null,
  add column last_error varchar(1024) null,
  add constraint chk_outbox_status check (status in ('PENDING', 'PUBLISHING', 'PUBLISHED', 'FAILED_RETRYABLE'));

create table consumer_processed_event (
  event_id varchar(64) not null,
  transfer_id varchar(64) not null,
  topic varchar(255) not null,
  partition_id int not null,
  offset_value bigint not null,
  consumer_group varchar(128) not null,
  status varchar(32) not null,
  processed_at timestamp(6) null,
  failure_reason varchar(1024) null,
  created_at timestamp(6) not null default current_timestamp(6),
  updated_at timestamp(6) not null default current_timestamp(6) on update current_timestamp(6),
  primary key (consumer_group, event_id),
  constraint chk_consumer_processed_status check (status in ('PROCESSED', 'FAILED_RETRYABLE', 'FAILED_TERMINAL')),
  unique key uk_consumer_group_topic_partition_offset (consumer_group, topic, partition_id, offset_value),
  index idx_consumer_event_id (event_id),
  index idx_consumer_transfer_id (transfer_id),
  index idx_consumer_status_created (status, created_at)
);
