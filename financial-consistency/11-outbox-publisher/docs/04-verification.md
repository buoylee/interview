# Verification

`GET /verification/violations` 从 MySQL 表抽取事实并运行不变量检查。verifier 不读取服务内存状态，也不把 Kafka offset 当成业务完成证明。

本章新增的核心不变量包括：

- `OUTBOX_PUBLISH_REQUIRED`：`TransferSucceeded` Outbox 如果已经有发布尝试，并且仍停在 `FAILED_RETRYABLE` 或 `PUBLISHING`，必须暴露为需要恢复的发布问题。
- `TRANSFER_OUTBOX_SINGLE_SUCCEEDED_EVENT`：同一笔成功转账只能有一条 `TRANSFER` 聚合的 `TransferSucceeded` Outbox，避免多个 `message_id` 绕过消费者幂等。
- `CONSUMER_PROCESSED_PUBLISHED_EVENT`：状态为 `PUBLISHED` 的 Outbox 事件，必须存在配置消费者组的 `consumer_processed_event(PROCESSED)`。
- `CONSUMER_IDEMPOTENT_PROCESSING`：同一个消费者组内，同一个 `event_id` 不能出现多条成功消费事实。

`CONSUMER_PROCESSED_PUBLISHED_EVENT` 只接受配置的消费者组。当前默认值来自 `spring.kafka.consumer.group-id`，即 `funds-transfer-event-consumer`。如果同一个事件只被 `other-consumer-group` 处理，verifier 仍会报告缺少预期消费者组的处理事实。

`PENDING` 且 `attempt_count=0` 不是违规。它表示 Outbox 行已经随本地事务提交，但发布器还没有尝试发布。只有已经尝试发布后仍失败或卡在发布中，才会触发 `OUTBOX_PUBLISH_REQUIRED`。

这些检查共同表达一条边界：成功转账、Outbox 发布、消费者处理都必须能在 MySQL 事实里闭环；broker 读取进度不能替代业务事实。
