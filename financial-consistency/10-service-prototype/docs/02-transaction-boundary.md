# 02 事务边界

本章只有一个资金内核服务，事务边界就是这个服务内的一次 MySQL 本地事务。它不跨服务，也不包住 broker、支付渠道或任何外部调用。

## 成功转账顺序

成功路径必须按这个顺序形成事实：

```text
idempotency -> account locks -> transfer_order -> ledger_entry -> account update -> outbox_message -> idempotency completion -> commit
```

含义如下：

- `idempotency`：先插入 `PROCESSING` 幂等记录，抢占幂等键。
- `account locks`：按稳定顺序锁定转出和转入账户，减少死锁风险。
- `transfer_order`：写入 `SUCCEEDED` 转账单，确定业务结果。
- `ledger_entry`：写入一借一贷两条 `TRANSFER` 分录。
- `account update`：扣减转出账户余额，增加转入账户余额。
- `outbox_message`：写入 `PENDING` 的 `TransferSucceeded` 事件。
- `idempotency completion`：把幂等记录更新为最终状态和响应体。
- `commit`：一次性提交以上事实。

只要 commit 没有发生，以上事实都不能作为已完成转账对外承诺。发生异常时，MySQL 回滚这批写入，避免只扣款、不入账、只写账本、不写 Outbox 之类的半成品状态。

## 失败路径

余额不足不是系统异常，而是可解释业务失败。服务会写 `FAILED` 的 `transfer_order` 和 `FAILED` 的 `idempotency_record`，但不会写 `ledger_entry`，也不会写成功事件 Outbox。

校验失败和同幂等键不同 payload 属于拒绝请求，不应创建成功转账事实。重复请求命中已完成幂等记录时，返回已保存响应，不重复执行业务写入。

## 为什么事务内没有外部调用

外部调用不可被 MySQL 回滚。假设事务中先发 broker 消息再回滚数据库，外部消费者可能已经看到一笔不存在的成功转账；假设先调用支付渠道再数据库超时，渠道结果也不会因为 MySQL 回滚而消失。

因此本阶段事务内只写本地事实，不做 broker publish、HTTP 调用、Temporal 调度或支付渠道调用。需要对外传播的事实先写入 `outbox_message` 的 `PENDING` 行，后续由独立发布流程读取并重试。这样本地原子性由 MySQL 保证，外部传播由 Outbox 的可恢复事实保证。
