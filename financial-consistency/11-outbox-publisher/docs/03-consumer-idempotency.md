# Consumer Idempotency

Kafka 消费者不能假设消息只会投递一次。本章的 `TransferEventConsumer` 在 ack Kafka 之前，先把消费事实写入 MySQL 表 `consumer_processed_event`。

消费事实的身份是 `(consumer_group,event_id)`。当前默认消费者组是 `funds-transfer-event-consumer`，`event_id` 来自 Outbox envelope 的 `messageId`。

正常路径是：

```text
Kafka record
-> parse envelope and payload
-> insert consumer_processed_event(PROCESSED)
-> ack Kafka
```

如果同一个消费者组再次收到同一个 `event_id`，插入会命中主键或唯一约束。仓储层确认 `(consumer_group,event_id)` 已经存在后，把它当成已处理消息返回，消费者随后 ack Kafka，不再产生第二条成功处理事实。

同一个事件可以被另一个消费者组独立处理。也就是说，`funds-transfer-event-consumer:M-1` 和 `another-consumer-group:M-1` 是两个不同的消费事实；幂等性只约束同一消费者组内的同一事件。

Kafka offset 进度不能替代本地处理事实。offset 只说明消费者组对 broker 的读取进度，不能说明业务数据库里已经留下了 `consumer_processed_event(PROCESSED)`。
