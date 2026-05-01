# 04 事件流

## 正常流程

下面是逻辑顺序和事实依赖，不表示一个同步 RPC 事务链。每个服务在发布事件之前，必须先在自己的本地事务内持久化本地业务状态和 outbox 记录；箭头只表达业务进展或事实可见顺序。

```text
Client
-> transaction-orchestrator: CreateTransfer(command, idempotency_key)
-> risk-service: CheckTransferRisk(command/response)
-> durable fact: RiskApproved
-> account-service: ReserveDebit
-> durable fact: DebitReserved
-> account-service: ConsumeFreeze / durable fact: FreezeConsumed
-> ledger-service: PostDebitEntry / durable fact: DebitPosted
-> account-service: CreditReceiver / durable fact: AccountCredited
-> ledger-service: PostCreditEntry / durable fact: CreditPosted
-> transaction-orchestrator: MarkSucceeded local transaction writes TransferSucceeded outbox
-> async outbox publisher: publish TransferSucceeded to Kafka later
-> reconciliation-service: independently consumes transfer/account/ledger events
```

边界说明：

- `account-service` 拥有 operational balance、freeze 和 account movement；`ledger-service` 拥有 immutable accounting entries。
- account movement 和 ledger posting 是两类独立事实，不能互相替代。
- `DEBIT_POSTED` 状态迁移要求付款方冻结被消费，即看到 `FreezeConsumed`，并且 `ledger-service` 完成 `PostDebitEntry`。
- `CREDIT_POSTED` 状态迁移要求收款方账户入账，即看到 `AccountCredited`，并且 `ledger-service` 完成 `PostCreditEntry`。
- orchestrator 不能只因为收到 `DebitPosted` 或 `CreditPosted` 就推进状态；它还必须同时看到对应 account movement fact 和 ledger posting fact。
- Kafka 只负责 topic、partition、保留和投递语义；业务幂等由各服务自己的 inbox/dedup 记录保证。

### 风控边界

第一个 transfer module 中，`risk-service` 采用同步 command/response：orchestrator 调用 `CheckTransferRisk` 并等待结果，再决定是否进入资金冻结。`TransferRequested` 不驱动风险服务消费；它作为转账创建事实供 reconciliation/audit 等异步消费者使用。无论 approval/rejection 是由 orchestrator 根据同步响应持久化并发出，还是由后续版本中的 risk-service 直接持久化并发出，都需要形成耐久事实：`RiskApproved` 或 `RiskRejected`。状态 `RISK_CHECKED` 只表示已经看到 approval fact；rejection fact 应推进到拒绝或终止路径，而不是继续执行 account/ledger 步骤。

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
| `TransferRequested` | transaction-orchestrator | reconciliation-service, audit-service | 转账请求已创建；不作为本模块风控调用入口 |
| `RiskApproved` | risk-service 或 transaction-orchestrator | transaction-orchestrator | 风控已批准；`RISK_CHECKED` 依赖此事实 |
| `RiskRejected` | risk-service 或 transaction-orchestrator | transaction-orchestrator | 风控已拒绝；不能继续冻结或入账 |
| `DebitReserved` | account-service | transaction-orchestrator, reconciliation-service | 付款资金已冻结 |
| `FreezeConsumed` | account-service | transaction-orchestrator, reconciliation-service | 付款方冻结已被消费 |
| `DebitPosted` | ledger-service | transaction-orchestrator | 借方分录已入账 |
| `AccountCredited` | account-service | transaction-orchestrator, reconciliation-service | 收款方账户已入账 |
| `CreditPosted` | ledger-service | transaction-orchestrator | 贷方分录已入账 |
| `TransferSucceeded` | transaction-orchestrator | reconciliation-service, notification-service | 转账完成 |
| `TransferCompensationRequired` | transaction-orchestrator | account-service, ledger-service | 需要补偿 |
| `TransferManualReviewRequired` | transaction-orchestrator | operations | 需要人工介入 |

事件名表达生产者已经持久化的本地事实。`DebitPosted` 和 `CreditPosted` 表示 ledger posting 已经完成；orchestrator 推进到 `DEBIT_POSTED` 或 `CREDIT_POSTED` 时，还必须结合对应 account movement 的完成事实。

状态依赖建议：

- `RISK_CHECKED`：需要 `RiskApproved`。
- `DEBIT_RESERVED`：需要 `DebitReserved`。
- `DEBIT_POSTED`：需要 `FreezeConsumed`，并且需要 `DebitPosted`。
- `CREDIT_POSTED`：需要 `AccountCredited`，并且需要 `CreditPosted`。
- `SUCCEEDED`：orchestrator 在本地事务内完成 `MarkSucceeded` 并写入 `TransferSucceeded` outbox；Kafka 中看到 `TransferSucceeded` 只是异步发布结果，不是该本地事务的一部分。

## 消息处理原则

- 所有事件必须包含 `event_id`、`transaction_id`、`idempotency_key`、`occurred_at`、`producer`。
- 消费者必须记录已处理 `event_id`。
- 同一事件重复到达时，返回已处理结果。
- 事件迟到时，必须检查当前状态是否仍允许处理。
- 消费者处理事件时，业务更新、inbox/dedup 记录和必要的 outbox 记录应在自己的本地事务内提交。
