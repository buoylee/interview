# 11 Outbox Publisher

这是第 10 章真实工程原型的下一步：保留 `TransferService` 的 MySQL 本地事务边界，把已提交的 `outbox_message(PENDING)` 发布到真实 Kafka，并用消费者幂等表证明重复消息不会造成重复业务效果。

## 目标

- 使用真实 Kafka topic `funds.transfer.events`。
- 用 `OutboxPublisher` 发布已提交的 Outbox 行。
- 发布成功后把 Outbox 标记为 `PUBLISHED`。
- 用 `TransferEventConsumer` 消费事件并写入 `consumer_processed_event`。
- 用 verifier 从 MySQL 事实检查发布和消费是否闭环。

## 运行方式

从仓库根目录运行：

```bash
bash financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh
```

手工启动服务：

```bash
bash financial-consistency/11-outbox-publisher/scripts/run-service.sh
```

## 关键边界

- `TransferService` 不直接调用 Kafka。
- Publisher 只能重发 Outbox 事件，不能重做转账。
- Kafka offset 不等于业务完成证明。
- Consumer 必须先写入本地幂等处理事实，再 ack Kafka 消息。
