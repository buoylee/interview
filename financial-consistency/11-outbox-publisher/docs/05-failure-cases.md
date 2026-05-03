# Failure Cases

## Publisher crashes before send

发布器如果在发送 Kafka 之前崩溃，Outbox 行会停在 `PENDING` 或 `PUBLISHING`。这条记录仍然保留在 MySQL 中，代表事件还没有可靠发布完成。恢复动作是再次运行发布器，让它重新处理可发布记录。

## Send succeeds but mark published fails

如果 Kafka 发送成功，但发布器在把 Outbox 标记为 `PUBLISHED` 前失败，下一次发布可能重放同一条事件。这个重复由消费者幂等吸收：同一个消费者组再次处理同一个 `event_id` 时，会命中 `consumer_processed_event` 的既有事实，然后 ack，不产生第二条成功处理事实。

## Consumer processes but crashes before ack

消费者先写入 `consumer_processed_event(PROCESSED)`，再 ack Kafka。如果写库成功后进程崩溃，Kafka 会重新投递同一条消息。重新消费时，`(consumer_group,event_id)` 已经存在，消费者把它当作已处理事件并 ack，避免重复业务处理。

## Consumer acks without writing local fact

如果消费者 ack 了 Kafka，但没有写入本地消费事实，Kafka offset 可能已经前进，业务数据库却没有 `consumer_processed_event(PROCESSED)`。verifier 会对 `PUBLISHED` Outbox 报告 `CONSUMER_PROCESSED_PUBLISHED_EVENT`，因为缺少配置消费者组的业务处理证明。
