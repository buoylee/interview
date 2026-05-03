# 03 Outbox 流程

Outbox 的目标不是在本章完成消息系统，而是先把“成功转账后必须发布事件”变成 MySQL 里的可恢复事实。

## 为什么当前只写 PENDING

成功转账在本地事务里写入：

```text
outbox_message.status = PENDING
event_type = TransferSucceeded
aggregate_type = TRANSFER
aggregate_id = transfer_id
```

当前阶段不接 Kafka 或其他 broker，所以服务没有能力证明消息已经发布。把状态写成 `PUBLISHED` 会伪造外部事实；把发布动作放进事务又会把不可回滚的外部副作用混进 MySQL 本地事务。

因此这个阶段只写 `PENDING`。它表示：业务事实已提交，有一条事件等待可靠发布。

## PENDING 行为什么是可恢复事实

`PENDING` 行和转账单、账本、余额变更在同一个 MySQL commit 中落库。只要转账成功，数据库里就能查到对应 Outbox 行；如果服务在 commit 后立刻崩溃，这行仍然存在。

后续发布器可以按 `status, created_at` 扫描 `PENDING` 行，发布成功后更新为 `PUBLISHED`，发布失败则保留或标记为 `FAILED_RETRYABLE` 等待重试。恢复的依据不是内存任务队列，也不是接口日志，而是 MySQL 中已经提交的事实。

Task 6 的验证器已经要求成功转账必须有 `TRANSFER` 聚合的 `TransferSucceeded` Outbox。缺失 Outbox 会报告 `TRANSFER_OUTBOX_REQUIRED`，这说明事件事实本身也是资金一致性的一部分。

## 为什么推迟 broker 发布

broker 发布涉及网络、确认、重试、重复消息和消费者幂等，复杂度应该和本地事务分开验证。

本章先证明本地事务能同时写入业务单、账本、余额、幂等记录和 Outbox。broker 发布可以在后续阶段单独实现：发布器读取 `PENDING`，发送消息，处理确认和失败重试。这样即使发布器重复发送，消费者也可以用事件 ID 或业务 ID 做幂等；即使发布器停机，也可以从 `PENDING` 行继续恢复。
