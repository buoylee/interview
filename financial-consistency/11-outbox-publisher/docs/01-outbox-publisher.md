# Outbox Publisher

第 11 章的发布器从 MySQL 事实出发。`TransferService` 在同一个本地事务里写入 `transfer_order`、`ledger_entry` 和 `outbox_message(PENDING)`；事务提交后，转账事实和待发布事件同时落库。这里的边界很重要：`TransferService` 只负责 MySQL 本地一致性，不调用 Kafka。

`OutboxPublisher` 只处理已经提交的 Outbox 行。每次调用 `publishBatch` 时，它生成一个本次调用专用的 `ownerToken`，把状态为 `PENDING` 或 `FAILED_RETRYABLE` 的记录 claim 成 `PUBLISHING`，同时写入 `locked_by`、`locked_at` 并增加 `attempt_count`。

后续状态迁移都带有 fencing 条件：`markPublished` 和 `markFailedRetryable` 都要求 `message_id` 匹配、当前状态仍是 `PUBLISHING`，并且 `locked_by` 等于本次调用的 `ownerToken`。如果这三个条件不成立，更新行数不是 1，发布器会报错，而不是误改其他调用或其他发布器持有的行。

成功路径是：

```text
PENDING/FAILED_RETRYABLE
-> PUBLISHING(ownerToken)
-> Kafka ack
-> PUBLISHED
```

`KafkaTemplate.send(...).get(...)` 返回成功后，发布器把 Outbox 行标记为 `PUBLISHED`，写入 `published_at`，并清空锁信息。

失败路径是：

```text
PENDING/FAILED_RETRYABLE
-> PUBLISHING(ownerToken)
-> send error
-> FAILED_RETRYABLE
```

发送异常会被记录到 `last_error`，锁信息会被清空，下一次发布调用可以重新 claim 这条 Outbox。发布器重试的是同一条 Outbox payload，不会重新执行转账，也不会调用 `TransferService`。

手工发布入口是：

```http
POST /outbox/publish-once?batchSize=10
```

`batchSize` 的合法范围是 `1..100`，默认值是 `10`。
