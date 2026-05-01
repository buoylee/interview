# 04 事件流

## 正常流程

下面是逻辑顺序。每个服务在发布事件之前，必须先在自己的本地事务内持久化本地业务状态和 outbox 记录。

```text
Client
-> transaction-orchestrator: CreateTransfer(command, idempotency_key)
-> risk-service: CheckTransferRisk
-> account-service: ReserveDebit
-> ledger-service: PostDebitEntry
-> account-service: CreditReceiver
-> ledger-service: PostCreditEntry
-> transaction-orchestrator: MarkSucceeded
-> Kafka: TransferSucceeded event
-> reconciliation-service: consume and index for reconciliation
```

边界说明：

- `account-service` 拥有 operational balance、freeze 和 account movement；`ledger-service` 拥有 immutable accounting entries。
- account movement 和 ledger posting 是两类独立事实，不能互相替代。
- `DEBIT_POSTED` 状态迁移要求付款方冻结被消费或产生等价 debit movement，并且 `ledger-service` 完成 `PostDebitEntry`。
- `CREDIT_POSTED` 状态迁移要求收款方产生 credit movement，并且 `ledger-service` 完成 `PostCreditEntry`。
- Kafka 只负责 topic、partition、保留和投递语义；业务幂等由各服务自己的 inbox/dedup 记录保证。

## Outbox 规则

每个服务只在自己的本地事务内写业务表和 outbox 表：

```text
local business update + outbox insert = one local database transaction
```

发布器异步读取 outbox 并写 Kafka。Kafka 重复投递由消费者幂等处理。

消费者必须拥有自己的 inbox/dedup 记录；Kafka offset 只是消费进度，不是业务幂等依据。

## 事件命名

| 事件 | 生产者 | 消费者 | 语义 |
|---|---|---|---|
| `TransferRequested` | transaction-orchestrator | risk-service | 转账请求已创建 |
| `DebitReserved` | account-service | transaction-orchestrator | 付款资金已冻结 |
| `DebitPosted` | ledger-service | transaction-orchestrator | 借方分录已入账 |
| `CreditPosted` | ledger-service | transaction-orchestrator | 贷方分录已入账 |
| `TransferSucceeded` | transaction-orchestrator | reconciliation-service, notification-service | 转账完成 |
| `TransferCompensationRequired` | transaction-orchestrator | account-service, ledger-service | 需要补偿 |
| `TransferManualReviewRequired` | transaction-orchestrator | operations | 需要人工介入 |

事件名表达生产者已经持久化的本地事实。`DebitPosted` 和 `CreditPosted` 表示 ledger posting 已经完成；orchestrator 推进到 `DEBIT_POSTED` 或 `CREDIT_POSTED` 时，还必须结合对应 account movement 的完成事实。

## 消息处理原则

- 所有事件必须包含 `event_id`、`transaction_id`、`idempotency_key`、`occurred_at`、`producer`。
- 消费者必须记录已处理 `event_id`。
- 同一事件重复到达时，返回已处理结果。
- 事件迟到时，必须检查当前状态是否仍允许处理。
- 消费者处理事件时，业务更新、inbox/dedup 记录和必要的 outbox 记录应在自己的本地事务内提交。
