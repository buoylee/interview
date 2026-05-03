# Failure Cases

## Publisher crashes before send

如果发布器崩溃发生在 claim 之前，Outbox 行仍是 `PENDING`，下一次发布调用可以自然重试。如果之前发送失败并被标记为 `FAILED_RETRYABLE`，下一次发布调用也会重新 claim 并重试。

如果发布器已经把行 claim 成 `PUBLISHING` 后崩溃，这条记录是卡住的 in-doubt 状态。当前发布器只自动 claim `PENDING` 和 `FAILED_RETRYABLE`，不会自动回收 stale `PUBLISHING`。这种状态必须由 verifier 或运维告警暴露，再由人工或明确的恢复流程判断是否重置为可重试状态。

## Send succeeds but mark published fails

如果 Kafka 发送成功，但发布器在把 Outbox 标记为 `PUBLISHED` 前失败，下一次发布可能重放同一条事件。这个重复由消费者幂等吸收：同一个消费者组再次处理同一个 `event_id` 时，会命中 `consumer_processed_event` 的既有事实，然后 ack，不产生第二条成功处理事实。

## Consumer processes but crashes before ack

消费者先写入 `consumer_processed_event(PROCESSED)`，再 ack Kafka。如果写库成功后进程崩溃，Kafka 会重新投递同一条消息。重新消费时，`(consumer_group,event_id)` 已经存在，消费者把它当作已处理事件并 ack，避免重复业务处理。

## Consumer acks without writing local fact

如果消费者 ack 了 Kafka，但没有写入本地消费事实，Kafka offset 可能已经前进，业务数据库却没有 `consumer_processed_event(PROCESSED)`。verifier 会对 `PUBLISHED` Outbox 报告 `CONSUMER_PROCESSED_PUBLISHED_EVENT`，因为缺少配置消费者组的业务处理证明。
