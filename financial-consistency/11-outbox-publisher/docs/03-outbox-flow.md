# 03 Outbox 流程

Outbox 的第一步是把“成功转账后必须发布事件”变成 MySQL 里的可恢复事实。第 11 章在这个基础上接入真实 Kafka：发布器读取已提交的 Outbox 行，发送到 `funds.transfer.events`，再根据发送结果更新发布状态。

## 为什么本地事务只写 PENDING

成功转账在本地事务里写入：

```text
outbox_message.status = PENDING
event_type = TransferSucceeded
aggregate_type = TRANSFER
aggregate_id = transfer_id
```

本地事务阶段只写 `PENDING`，因为 `TransferService` 不能在 MySQL 事务里调用 Kafka。把发布动作放进转账事务会把不可回滚的外部副作用混进 MySQL 本地事务；把状态提前写成 `PUBLISHED` 则会伪造 broker 已确认的事实。

因此转账提交时只写 `PENDING`。它表示：业务事实已提交，有一条事件等待可靠发布。

## PENDING 行为什么是可恢复事实

`PENDING` 行和转账单、账本、余额变更在同一个 MySQL commit 中落库。只要转账成功，数据库里就能查到对应 Outbox 行；如果服务在 commit 后立刻崩溃，这行仍然存在。

本章发布器会 claim `PENDING` 或 `FAILED_RETRYABLE` 行为 `PUBLISHING`，发送 Kafka 成功后更新为 `PUBLISHED`，发送失败后标记为 `FAILED_RETRYABLE` 等待重试。恢复的依据不是内存任务队列，也不是接口日志，而是 MySQL 中已经提交的事实。

验证器要求成功转账必须有 `TRANSFER` 聚合的 `TransferSucceeded` Outbox。缺失 Outbox 会报告 `TRANSFER_OUTBOX_REQUIRED`，这说明事件事实本身也是资金一致性的一部分。

## 为什么 broker 发布仍然独立

broker 发布涉及网络、确认、重试、重复消息和消费者幂等，复杂度应该和本地事务分开验证。

本章的主线是：本地事务先写入业务单、账本、余额、幂等记录和 Outbox；发布器再读取 `PENDING` 或 `FAILED_RETRYABLE`，发送 Kafka，处理确认和失败重试。这样即使发布器重复发送，消费者也可以用 `(consumer_group,event_id)` 做幂等；即使发布器停机，也可以从数据库事实判断哪些事件仍需恢复。
