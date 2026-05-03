# 11 Outbox Publisher

第 11 章把第 10 章提交后的 `outbox_message(PENDING)` 连接到真实 Kafka。核心目标不是追求更多框架，而是证明一件事：转账本地事务已经提交后，事件传播、重试、重复消费和验证应该分别由哪些事实负责。

## 目标

- `TransferService` 继续只写 MySQL，不调用 Kafka。
- `OutboxPublisher` 发布 `PENDING` 或 `FAILED_RETRYABLE` 事件到 `funds.transfer.events`。
- `TransferEventConsumer` 写入 `consumer_processed_event` 后再 ack Kafka。
- verifier 从 MySQL 事实检查成功转账、Outbox 发布和消费者处理是否闭环。

## 运行方式

从仓库根目录运行：

```bash
bash financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh
bash financial-consistency/11-outbox-publisher/scripts/run-service.sh
```

脚本依赖 Docker、Java 17、Maven 和 `jq`。

服务启动后可以手工触发一次 Outbox 发布：

```bash
curl -X POST "http://localhost:8081/outbox/publish-once?batchSize=10"
```

`batchSize` 的有效范围是 `1..100`，默认值是 `10`。验证接口是：

```bash
curl "http://localhost:8081/verification/violations"
```

## 文档导航

`docs/01-domain-model.md`、`docs/02-transaction-boundary.md`、`docs/03-outbox-flow.md` 和 `docs/04-verification-from-mysql.md` 是从第 10 章继承并更新的核心模型说明，保留本地事务、Outbox 和 MySQL 事实验证的背景。`docs/01-outbox-publisher.md` 到 `docs/05-failure-cases.md` 是第 11 章新增的 Kafka 发布、消费者幂等、验证和故障边界说明。

## 发布链路

```text
transfer_order + ledger_entry + outbox_message(PENDING)
-> commit
-> OutboxPublisher
-> Kafka funds.transfer.events
-> outbox_message(PUBLISHED)
```

Publisher 重试只能重发 Outbox payload，不能重新执行转账。

## 消费者幂等

Kafka 可能重复投递消息。消费者以 `consumer_group + messageId` 写入 `consumer_processed_event`，重复消息命中主键后直接 ack，不重复产生业务处理事实。

同一个事件可以被另一个消费者组独立处理；幂等边界是 `(consumer_group,event_id)`，不是全局事件 ID。

## 验证方式

`GET /verification/violations` 会检查：

- 成功转账必须有正确 Outbox。
- 发布失败或停在发布中必须暴露为可恢复问题。
- `PUBLISHED` 事件必须有配置消费者组的 `consumer_processed_event(PROCESSED)`。
- 同一消费者组内，同一事件不能有多个成功消费事实。

## 关键边界

Kafka offset 不是业务完成证明；offset 只说明消费者组对 broker 的读取进度。业务完成证明必须来自消费者自己的数据库事实。
