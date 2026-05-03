# 11 Outbox Publisher 设计

日期：2026-05-03

## 目标

创建 `financial-consistency/11-outbox-publisher/`，在第 10 章 `10-service-prototype` 的基础上实现真实 Kafka 事件传播链路。

第 10 章已经证明：转账服务可以在一个 MySQL 本地事务里同时写入 `transfer_order`、`ledger_entry`、`account`、`idempotency_record` 和 `outbox_message(PENDING)`。第 11 章要继续证明：本地事务提交后的 `PENDING` Outbox 事实如何被可靠发布到 Kafka，下游消费者如何用本地幂等事实处理重复消息，以及 verifier 如何从 MySQL 和消费事实中发现事件传播问题。

完成后，学习者应该能回答：

- 为什么 `TransferService` 不能在本地事务里直接调用 Kafka？
- Outbox publisher 重试时为什么只能重发事件，不能重做转账？
- Kafka ack、producer idempotence、consumer offset 分别能证明什么，不能证明什么？
- 为什么消费者必须有自己的幂等表，而不能只依赖 broker offset？
- 如何验证成功转账事件从 `PENDING` 到 `PUBLISHED`，再到消费者处理事实？
- 如何识别事件已发布但未消费、重复发布、重复消费、消费失败等问题？

## 文档依据

设计前使用 Context7 查询了 Spring Kafka 当前文档。

采用 `/spring-projects/spring-kafka` 文档要点：

- Spring Boot 可通过 `spring.kafka.bootstrap-servers`、producer/consumer serializer、consumer group、listener ack-mode 等配置 Kafka。
- Producer 可配置 `acks=all`、`retries` 和 `enable.idempotence=true`。
- Listener 可配置 manual ack，业务处理成功后再确认消息。
- Spring Kafka 提供 `DefaultErrorHandler`、DLT、retry topic 等机制，但本章第一版只实现教学所需的本地幂等处理和显式失败事实，不把 DLT 作为主线。

## 背景

第 10 章的关键边界是：

```text
TransferService 本地事务
-> outbox_message(PENDING)
-> commit
```

它没有接 Kafka。这样是正确的，因为 broker publish 是不可被 MySQL 回滚的外部副作用。第 11 章从提交后的 `PENDING` 行开始，补上异步发布和消费幂等。

这一章仍然不是完整微服务平台。它只围绕 `TransferSucceeded` 事件做一个可运行、可测试、可验证的 Kafka Outbox 原型。

## 方案选择

采用方案 A：真实 Kafka + Outbox Publisher + 消费者幂等表。

整体链路：

```text
TransferService
  -> MySQL local transaction
  -> outbox_message(PENDING)
  -> OutboxPublisher claims rows
  -> Kafka topic: funds.transfer.events
  -> TransferEventConsumer
  -> consumer_processed_event
  -> verifier
```

选择真实 Kafka 的原因：

- 教学目标是贴近真实工程，而不是只停留在内存 broker。
- Kafka 会引入真实的 ack、重复消息、consumer group、offset 和网络失败语义。
- 只有接入消费者幂等表，才能讲清楚“消息被消费”和“业务效果已落库”之间的差别。

## 范围

第一版覆盖：

- 复用第 10 章的 Spring Boot + MySQL 资金内核服务。
- Docker Compose 增加 Kafka。
- Spring Kafka producer/consumer 配置。
- Kafka topic：`funds.transfer.events`。
- Outbox publisher 扫描并 claim `PENDING` 或 `FAILED_RETRYABLE` 行。
- 发布成功后把 Outbox 标记为 `PUBLISHED`，记录 `published_at` 和 `attempt_count`。
- 发布失败后把 Outbox 标记为 `FAILED_RETRYABLE`，增加 `attempt_count` 并记录错误。
- Consumer 接收 `TransferSucceeded` 事件。
- Consumer 使用 `consumer_processed_event` 幂等表，重复消息不重复产生业务处理事实。
- Verification API 扩展，能检查 Outbox 发布和消费者处理事实。
- 脚本或测试 fixture 模拟发布失败、重复发布、消费失败和重复消费。
- 文档解释 Kafka ack、offset、Outbox、消费者幂等和 verifier 的边界。

## 非目标

第一版不做这些事情：

- 不引入 Temporal、Saga、Camunda、Seata。
- 不拆成多个 Maven module 或多个独立服务进程。
- 不实现真实支付渠道、通知服务、清结算系统或下游账户系统。
- 不把 Kafka 事务作为主线方案。
- 不实现 CDC/Debezium。
- 不把 DLT 作为主要恢复机制。
- 不实现生产级监控、告警、Schema Registry 或 Avro。
- 不声明 Kafka producer idempotence 可以替代业务幂等。

## 目录设计

新增目录：

```text
financial-consistency/11-outbox-publisher/
```

建议结构：

```text
financial-consistency/11-outbox-publisher/
  README.md
  docker-compose.yml
  scripts/
    test-outbox-publisher.sh
    run-service.sh
    replay-transfer-event.sh
    mark-outbox-pending.sh
  docs/
    01-outbox-publisher.md
    02-kafka-boundaries.md
    03-consumer-idempotency.md
    04-verification.md
    05-failure-cases.md
  service/
    pom.xml
    src/main/java/.../ServicePrototypeApplication.java
    src/main/java/.../outbox/
    src/main/java/.../kafka/
    src/main/java/.../consumer/
    src/main/java/.../verification/
    src/main/resources/db/migration/
    src/test/java/.../
```

实现阶段可以从第 10 章复制服务目录作为第 11 章起点。第 11 章必须保持自包含，方便学习者单独运行，不依赖第 10 章目录里的编译产物。

## 组件设计

### TransferService

继续保持第 10 章边界：只写 MySQL 本地事务，不调用 Kafka。

成功转账仍写：

```text
outbox_message.status = PENDING
event_type = TransferSucceeded
aggregate_type = TRANSFER
aggregate_id = transfer_id
```

这一点不能改变。第 11 章新增的是提交后发布，不是把 Kafka publish 塞回转账事务。

### OutboxPublisher

`OutboxPublisher` 是一个应用内组件，负责从 MySQL claim 可发布事件并发送到 Kafka。

建议方法：

```java
int publishBatch(int batchSize)
```

处理流程：

```text
select PENDING / FAILED_RETRYABLE rows
-> claim rows
-> KafkaTemplate.send(topic, key, payload)
-> broker ack success
-> mark PUBLISHED
```

失败流程：

```text
send throws / future fails
-> mark FAILED_RETRYABLE
-> attempt_count + 1
-> last_error
```

并发要求：

- Publisher 必须避免多个线程同时发布同一行。
- 可以用 `status=PUBLISHING` 或 `locked_at/locked_by` 做 claim。
- 第一版优先使用 MySQL 行状态 claim，不引入分布式锁。

关键边界：

- Publisher 重试只能重发 Outbox payload。
- Publisher 不能重新调用 `TransferService.transfer()`。
- Publisher 不能根据内存状态推断业务是否成功，必须以 Outbox 行为准。

### Kafka Topic

第一版只需要一个 topic：

```text
funds.transfer.events
```

消息 key：

```text
transfer_id
```

消息 value 使用 JSON，来自 Outbox payload。

事件示例：

```json
{
  "transferId": "T-...",
  "fromAccountId": "A-001",
  "toAccountId": "B-001",
  "currency": "USD",
  "amount": "25.0000"
}
```

Producer 配置目标：

- `acks=all`
- `enable.idempotence=true`
- String key serializer
- String or JSON value serializer

Producer idempotence 只减少 producer 重试造成的 broker 侧重复，不能替代业务消费幂等。

### TransferEventConsumer

Consumer 订阅：

```text
funds.transfer.events
```

处理步骤：

```text
receive Kafka record
-> parse TransferSucceeded event
-> insert consumer_processed_event(event_id/message_id/transfer_id)
-> if insert succeeds: record business processing fact, ack
-> if duplicate key: treat as already processed, ack
-> if processing fails: do not ack, or record failure according to configured test path
```

第一版消费者不调用真实下游服务，只写本地处理事实。这样能专注讲清楚消费者幂等。

### consumer_processed_event

新增消费者幂等表：

```text
consumer_processed_event
```

关键字段：

- `event_id` 或 `message_id`
- `transfer_id`
- `topic`
- `partition_id`
- `offset_value`
- `consumer_group`
- `status`
- `processed_at`
- `failure_reason`
- `created_at`
- `updated_at`

状态：

```text
PROCESSED
FAILED_RETRYABLE
FAILED_TERMINAL
```

唯一约束：

- `event_id` 或 `message_id` 唯一。
- 可额外保留 `topic + partition + offset` 作为 broker 位置证据，但它不是业务幂等主键。

## 数据模型变更

### outbox_message 扩展

第 10 章已有：

- `message_id`
- `aggregate_type`
- `aggregate_id`
- `event_type`
- `payload`
- `status`
- `published_at`
- `attempt_count`

第 11 章建议补充：

- `last_error`
- `locked_at`
- `locked_by`

状态扩展：

```text
PENDING
PUBLISHING
PUBLISHED
FAILED_RETRYABLE
```

是否保留第 10 章 `FAILED_RETRYABLE` 名称：保留，避免文档概念断裂。

### published_event 或 outbox_publish_attempt

可选引入发布尝试表：

```text
outbox_publish_attempt
```

关键字段：

- `attempt_id`
- `message_id`
- `topic`
- `status`
- `error_message`
- `created_at`

建议第一版暂不引入独立 attempt 表，先用 `attempt_count` 和 `last_error`，保持实现聚焦。后续如果需要更强审计，再扩展 attempt 表。

### consumer_processed_event

消费者处理事实必须独立于 broker offset。

这张表回答的是：

```text
这个业务事件是否已经被本消费者组处理过？
```

而不是：

```text
Kafka 客户端是否移动过 offset？
```

## 核心流程

### 正常路径

```text
POST /transfers
-> MySQL commit with outbox_message(PENDING)
-> OutboxPublisher publishes Kafka record
-> outbox_message(PUBLISHED)
-> TransferEventConsumer receives record
-> consumer_processed_event(PROCESSED)
-> ack Kafka record
-> verifier reports no violations
```

### Publisher 重试

```text
outbox_message(PENDING)
-> publish fails
-> outbox_message(FAILED_RETRYABLE, attempt_count + 1, last_error)
-> next publishBatch
-> publish succeeds
-> outbox_message(PUBLISHED)
```

这个流程证明：业务事实不需要重做，事件投递可以恢复。

### 重复发布

重复发布同一个 Kafka event 是允许发生的。系统正确性不依赖“绝不重复”，而依赖消费者幂等。

预期结果：

- Kafka 中可能有重复事件。
- `consumer_processed_event` 只保留一次 `PROCESSED` 业务事实。
- verifier 不应把重复 Kafka 记录本身当成资金不一致，但应能发现重复消费是否产生多次业务效果。

### 消费失败

消费失败不能被 offset 掩盖。

预期设计：

- 如果消费者本地处理失败，不应 ack。
- 如果写入失败事实，则 verifier 可以看到 `FAILED_RETRYABLE`。
- 只有消费者幂等事实写入成功后，才 ack Kafka record。

## 验证设计

第 11 章 verifier 在第 10 章基础上增加事件传播不变量。

输入事实：

- `transfer_order`
- `ledger_entry`
- `outbox_message`
- `consumer_processed_event`

新增不变量：

### OUTBOX_PUBLISHED_FOR_SUCCESSFUL_TRANSFER

成功转账必须最终有对应 `outbox_message.status=PUBLISHED`，否则说明事件还没进入 broker 发布通道。

这个不变量和第 10 章不同：

- 第 10 章只要求成功转账有 `PENDING` Outbox。
- 第 11 章在 publisher 运行后要求它变成 `PUBLISHED`。

测试需要区分：

- publisher 未运行时，`PENDING` 是可恢复状态。
- publisher 运行后仍未发布，才是传播失败。

### CONSUMER_PROCESSED_PUBLISHED_EVENT

已发布的 `TransferSucceeded` 事件必须有对应 `consumer_processed_event(PROCESSED)`。

这证明“事件进入 broker 后，下游消费者处理事实也已落库”。

### CONSUMER_IDEMPOTENT_PROCESSING

同一个 event/message id 不能产生多条成功处理事实。

即使 Kafka 重复投递，消费者也只能记录一次业务处理成功。

### CONSUMER_OFFSET_IS_NOT_BUSINESS_PROOF

这个不变量可以通过文档和测试 fixture 表达：即使构造 broker offset 证据，如果没有 `consumer_processed_event(PROCESSED)`，verifier 仍应报告未处理。

第一版不需要真实读取 broker offset；可以用测试文档和 consumer 表设计说明这个边界。

## API 和脚本

保留第 10 章 API：

- `POST /transfers`
- `GET /verification/violations`

新增教学 API 或脚本：

- `POST /outbox/publish-once`：触发一次 publisher batch，方便测试和演示。
- `GET /outbox/messages`：可选，只用于教学观察。
- `scripts/replay-transfer-event.sh <message-id>`：手动重放某个事件到 Kafka。
- `scripts/mark-outbox-pending.sh <message-id>`：把已发布消息改回可发布状态，用于重复发布 fixture。

是否新增管理 API 在实现计划中再控制范围。推荐先实现 `publish-once`，避免后台 scheduler 造成测试不可控。

## 测试策略

使用真实 Docker Compose MySQL + Kafka。

核心测试：

1. 成功转账后有 `PENDING` Outbox。
2. 调用 publisher 后 Outbox 变成 `PUBLISHED`。
3. Kafka consumer 写入 `consumer_processed_event(PROCESSED)`。
4. 重复发布同一事件，consumer 只处理一次。
5. 模拟 Kafka 不可用或发送异常，Outbox 变成 `FAILED_RETRYABLE`。
6. 构造 `PUBLISHED` 但无 consumer 处理事实，verifier 报告未消费。
7. 构造重复 consumer success 事实，verifier 报告幂等违例。
8. 全链路 smoke：转账 -> publish -> consume -> verify `[]`。

测试原则：

- 不用 mock Kafka 替代真实 broker 语义。
- 可用直接数据库 fixture 构造坏历史，但正常路径必须跑真实 publisher/consumer。
- 每个测试重置 MySQL 表和 Kafka topic，避免消息残留影响断言。

## 文档要求

`11-outbox-publisher` 文档至少覆盖：

- Outbox publisher 为什么在事务后运行。
- Kafka producer ack 和 idempotence 能证明什么。
- Consumer offset 为什么不能证明业务完成。
- Consumer 幂等表如何设计。
- Publisher 失败、重复发布、重复消费、消费失败分别如何处理。
- Verifier 如何检查事件传播事实。

根 README 要增加第 11 章入口和设计文档链接。

## 风险和取舍

### Kafka 增加运行复杂度

真实 Kafka 会让 Docker Compose、测试等待、topic 清理更复杂。这个复杂度是本章学习目标的一部分，但实现计划必须限制范围：只一个 topic、一个 consumer group、一个事件类型。

### 后台 scheduler 会让测试不稳定

如果 publisher 自动轮询，测试可能出现竞争。第一版推荐显式 `publishBatch()` 和 `POST /outbox/publish-once`，scheduler 放到后续章节或可关闭配置中。

### Kafka 事务不是第一版主线

Kafka transaction 可以解决部分 producer 端原子性问题，但会转移学习重点。当前主线是数据库 Outbox 和消费者幂等；Kafka transaction 可在文档中提及，但不实现。

### DLT 不是业务完成证明

DLT 可以帮助错误消息隔离，但不能证明业务处理成功。第一版不把 DLT 当作一致性闭环，而是要求消费者处理事实和 verifier 检查。

## 成功标准

本章完成时应满足：

- 从仓库根目录可以启动 MySQL + Kafka 并跑完整测试。
- 转账成功后生成 `PENDING` Outbox。
- Publisher 能把 Outbox 发布到 Kafka 并标记 `PUBLISHED`。
- Consumer 能写入幂等处理事实。
- 重复发布或重复投递不会产生重复业务处理事实。
- Verifier 能发现已发布未消费、重复消费、缺失发布等坏历史。
- 文档清楚说明：Outbox 解决消息不丢，Kafka offset 不等于业务完成，消费者幂等和对账验证仍然必需。
