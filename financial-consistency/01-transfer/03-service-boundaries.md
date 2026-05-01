# 03 服务边界

## 服务列表

| 服务 | 拥有的数据 | 本地事务边界 | 不拥有的数据 |
|---|---|---|---|
| `transaction-orchestrator` | transfer 状态、workflow 进度、补偿记录、命令幂等记录、processed command 记录、orchestrator outbox | 单个 transfer 的创建、状态推进、版本更新、审计/补偿标记和 outbox 写入 | 账户余额、冻结、账户流水、会计分录 |
| `account-service` | operational balance、freeze 记录、account movement、账户命令/事件 inbox 与 dedup 记录、account outbox | 单账户冻结、解冻、扣减、入账及对应 movement/outbox 写入 | 全局交易流程、不可变会计账本 |
| `ledger-service` | immutable ledger entry、journal、posting batch、posting 命令/事件 inbox 与 dedup 记录、ledger outbox | 分录创建、过账、posting dedup 和 ledger-posted outbox 写入 | 实时授权余额、账户冻结 |
| `risk-service` | 风控规则、限额检查结果 | 风控决策记录 | 资金状态 |
| `reconciliation-service` | 对账输入、对账结果、差错记录、修复工单、consumed event dedup | 对账输入归档、差异检测结果和差错状态 | 原始资金事实、账户或账本写模型 |
| `message-broker` | topic、partition、投递保证和保留策略 | 消息追加、分区顺序和投递语义 | 业务状态、consumer offset 作为业务事实、服务 inbox/dedup |

资金事实的边界：

- `account-service` 是实时授权使用的 operational balance、freeze 和 account movement 的所有者。
- `ledger-service` 是用于独立重建和审计的不可变 accounting/audit journal entry 的所有者。
- `reconciliation-service` 负责发现 account movement、balance snapshot 与 ledger posting 之间的偏差。
- account balance snapshot 不是任意真相；它必须能被 account movement 解释，并且能与 ledger entry 对账。

## transaction-orchestrator

职责：

- 接收转账命令。
- 创建幂等记录和 transfer 状态。
- 调用风控、账户、账本服务。
- 推进状态机。
- 触发补偿。
- 将无法自动恢复的交易转入 `MANUAL_REVIEW`。

拥有的数据：

- transfer 聚合、状态机状态、版本号和 workflow 进度。
- `idempotency_key` 对应的命令幂等记录和 processed command 记录。
- 补偿记录、人工处理标记、审计标记。
- orchestrator outbox 中的 transfer-state events。

本地事务边界：

- 在适用的状态推进中，idempotency record 创建、transfer 创建或状态迁移、版本更新、审计/补偿 marker、orchestrator outbox event 必须在同一个本地事务内提交。
- 如果外部服务响应已经收到但本地事务提交失败，必须通过 `idempotency_key` 和状态查询恢复，不能重复推进状态。

emits/consumes：

- emits: transfer created/state changed/finalized events。
- consumes: 客户端或上游 transfer command，以及下游服务回调/事件。
- owns: consumed command 的 processed/idempotency 记录；这些记录不属于 message-broker。

不直接修改：

- 账户余额。
- 会计分录。

must not do：

- 不基于本地缓存余额授权扣款。
- 不绕过 `account-service` 修改 freeze、movement 或 balance snapshot。
- 不绕过 `ledger-service` 创建或修正 ledger entry。

## account-service

职责：

- 冻结付款方资金。
- 扣减冻结金额。
- 给收款方入账。
- 保证单账户内余额更新的本地事务正确性。

拥有的数据：

- 实时授权使用的 operational balance 和 balance snapshot。
- freeze record，包括 reserve、consume、release 的生命周期。
- account movement，包括借记、贷记、冻结消耗和释放等账户侧资金变化。
- account-service inbox/dedup 记录，用于它消费的命令或事件。
- account-service outbox 中的 account movement/freeze events。

本地事务必须同时更新：

- account balance snapshot。
- account movement 或 freeze record。
- outbox event，如果该变化需要异步通知。

本地事务边界：

- `ReserveDebit` 成功时，freeze record、balance snapshot、account movement、命令 dedup/inbox 和 outbox event 必须原子提交。
- `ConsumeFreeze` 或等价扣减动作成功时，freeze 状态、借记 movement、balance snapshot、dedup/inbox 和 outbox event 必须原子提交。
- `CreditReceiver` 成功时，贷记 movement、balance snapshot、dedup/inbox 和 outbox event 必须原子提交。

emits/consumes：

- emits: freeze reserved/released/consumed events、account debited/credited movement events。
- consumes: orchestrator 发出的 reserve、consume/release freeze、credit 命令，或等价事件。
- owns: 对所消费命令/事件的 inbox 与 dedup 状态；consumer group offset 只是 broker 消费进度，不是业务幂等状态。

不拥有的数据：

- transfer 全局状态机。
- ledger journal、posting batch 和 audit journal entry。

must not do：

- 不直接写 transfer 状态。
- 不创建 ledger entry 作为会计真相。
- 不把 balance snapshot 当作不可解释的最终真相；snapshot 必须能回溯到 account movement，并参与 ledger reconciliation。

## ledger-service

职责：

- 创建借方和贷方分录。
- 保证同一 transfer 的分录可追踪。
- 支持通过分录重建资金变化。

拥有的数据：

- 不可变 accounting/audit journal entry。
- ledger posting batch、posting 状态和 transfer 到 posting 的关联。
- ledger-service inbox/dedup 记录，用于它消费的 posting command 或事件。
- ledger-service outbox 中的 ledger-posted events。

本地事务边界：

- `PostDebitEntry` 成功时，借方 ledger entry、posting batch 状态、posting dedup/inbox 和 ledger-posted outbox event 必须原子提交。
- `PostCreditEntry` 成功时，贷方 ledger entry、posting batch 状态、posting dedup/inbox 和 ledger-posted outbox event 必须原子提交。
- ledger entry 一旦过账不可变；修正必须通过反向分录或调整分录表达。

emits/consumes：

- emits: debit ledger-posted events、credit ledger-posted events。
- consumes: orchestrator 或 account 资金动作后触发的 posting command/event。
- owns: posting command/event 的 inbox 与 dedup 状态；不依赖 consumer offset 判断是否已过账。

不拥有的数据：

- account-service 的 operational balance、freeze record 和 account movement 写模型。
- transaction-orchestrator 的 transfer 状态机。

must not do：

- 不为实时授权返回账户可用余额。
- 不覆盖或删除已过账 journal entry。

## risk-service

拥有的数据：

- 风控规则、限额配置、风险决策和决策审计记录。

本地事务边界：

- 风控输入快照、决策结果和审计记录在同一个本地事务内提交。

emits/consumes：

- emits: risk approved/rejected events 或同步响应。
- consumes: transfer risk check command。

must not do：

- 不冻结、扣减、入账或过账资金。

## reconciliation-service

职责：

- 比较 account movement、balance snapshot 和 ledger posting。
- 记录差异、生成修复工单或人工审核输入。
- 验证 account balance snapshot 是否可由 account movement 和 ledger entry 独立解释。

拥有的数据：

- 对账输入归档、对账批次、对账结果、差错记录、修复工单。
- reconciliation-service consumed event dedup。

本地事务边界：

- 对账输入归档、差异检测结果、dedup 状态和修复工单状态必须在同一个本地事务内提交。

emits/consumes：

- consumes: transfer-state events、account movement/freeze events、ledger-posted events、balance snapshot feed。
- emits: reconciliation matched/diverged/manual-review-required events。
- owns: 对所消费事件的 dedup；不把 message-broker offset 当作对账结果。

must not do：

- 不直接修正 account balance、freeze、movement 或 ledger entry。
- 不声明新的资金事实，只声明 account 与 ledger 之间是否一致。

## message-broker

拥有的数据：

- topic、partition、消息保留策略、分区内顺序和投递保证。

本地事务边界：

- broker 的边界是消息追加、复制、确认和投递语义，不是业务状态提交。

emits/consumes：

- broker 传递事件；事件语义由生产服务定义，处理语义由消费服务的 inbox/dedup 定义。

must not do：

- 不拥有 consumer offset 作为业务状态。
- 不拥有任何服务的 inbox、outbox 或 dedup 记录。

## 状态迁移授权

后续详细 event-flow 文档会展开完整消息、重试和补偿流程；本边界文档必须先固定哪个服务响应授权哪一次状态迁移：

| 授权响应 | orchestrator 状态迁移 |
|---|---|
| 创建 transfer 聚合并写入 `idempotency_key` 记录成功 | `REQUESTED` |
| `risk-service` approval | `RISK_CHECKED` |
| `account-service` `ReserveDebit` success | `DEBIT_RESERVED` |
| `account-service` `ConsumeFreeze` 或等价 debit movement success，且 `ledger-service` `PostDebitEntry` success | `DEBIT_POSTED` |
| `account-service` `CreditReceiver` success，且 `ledger-service` `PostCreditEntry` success | `CREDIT_POSTED` |
| orchestrator finalization event 本地提交成功 | `SUCCEEDED` |

状态推进规则：

- orchestrator 只能在对应服务响应或已持久化事件满足条件后推进状态。
- 需要两个服务响应的迁移必须同时观察到账户侧 movement 成功和 ledger posting 成功，不能只凭其中一个服务推进。
- 所有状态推进都必须通过 orchestrator 本地事务写入版本、审计/补偿 marker 和 outbox event。

## 服务间原则

- 禁止跨服务共享数据库。
- 禁止跨服务直接改表。
- 跨服务调用必须带 `transaction_id`、`idempotency_key`、`trace_id`。
- 跨服务调用超时不能直接等价于失败，必须查询或等待状态收敛。
- 生产服务拥有自己的 outbox；消费服务拥有自己的 inbox/dedup 和 consumer group offset 处理进度。
- `message-broker` 只拥有 topic、partition、保留策略和投递保证；consumer offset 不可作为业务幂等、过账或对账完成的事实来源。
