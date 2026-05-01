# 06 验证路线

## 验证目标

验证目标不是证明系统没有 bug，而是用多层方法提前暴露事务设计和实现中的错误，并确保异常能被发现、定位、止损和修复。

验证必须围绕已经定义的耐久事实、状态依赖和故障矩阵展开，而不是只验证接口返回成功：

- `TransferRequested` 必须对应 transfer 创建和幂等记录。
- `RiskApproved` 才能推进到 `RISK_CHECKED`；`RiskRejected` 不能继续冻结、扣款或入账。
- `DebitReserved` 表示冻结已经持久化。
- `DEBIT_POSTED` 必须同时看到 `FreezeConsumed` 和 `DebitPosted`。
- `CREDIT_POSTED` 必须同时看到 `AccountCredited` 和 `CreditPosted`。
- `TransferSucceeded` 只能在 `CREDIT_POSTED` 之后由 orchestrator 本地最终确认产生。
- `AccountCredited` 已发生但 `CreditPosted` 缺失时，必须走贷方 ledger retry 或 manual repair/review，不能走正常金融补偿。

## 层次 1：模型验证

建模对象：

- 转账状态机。
- 幂等键。
- 借方和贷方分录。
- Outbox 事件。
- 重试、超时、宕机和重复消息。

需要检查的不变量：

- 资金守恒。
- 同一幂等键只有一次业务效果。
- 成功状态必须存在借贷两边分录。
- 终态不能非法回退。

模型需要显式表达以下事实依赖：

- `RISK_CHECKED` 依赖 `RiskApproved`，且 `RiskRejected` 与资金动作互斥。
- `DEBIT_RESERVED` 依赖 `DebitReserved`。
- `DEBIT_POSTED` 依赖 `FreezeConsumed` 和 `DebitPosted` 两个事实同时成立。
- `CREDIT_POSTED` 依赖 `AccountCredited` 和 `CreditPosted` 两个事实同时成立。
- `SUCCEEDED` 依赖 `TransferSucceeded`，且不能从 `FAILED`、`COMPENSATED` 或 `MANUAL_REVIEW` 非法推进。

模型验证要枚举 F05 子场景：

- F05a：只有 `DebitReserved`，应释放冻结或进入 `MANUAL_REVIEW`。
- F05b：只有 `FreezeConsumed`，应重试 `DebitPosted` 或进入 manual repair/review。
- F05c：已有 `FreezeConsumed` 和 `DebitPosted`，但无贷方事实，应优先正向重试贷方入账，确认贷方未发生且策略允许时才补偿。
- F05d：已有 `AccountCredited` 但无 `CreditPosted`，只能重试贷方 ledger posting 或 manual repair/review。
- F05e：已有 `FreezeConsumed`、`DebitPosted`、`AccountCredited` 和 `CreditPosted`，只能重试最终确认到 `SUCCEEDED`。

## 层次 2：属性测试

随机生成操作序列：

- 创建转账。
- 重复提交。
- 重试扣款。
- 重试入账。
- 重放消息。
- 触发补偿。
- 执行对账。

每轮执行后检查不变量。

属性测试的断言必须覆盖：

- 同一 `idempotency_key` 多次提交只产生一个 `TransferRequested` 和一次业务效果。
- 重复 `DebitReserved`、`FreezeConsumed`、`DebitPosted`、`AccountCredited`、`CreditPosted` 消息不会产生重复冻结、重复扣款、重复入账或重复分录。
- 任意操作序列后，账户余额快照可以由 account movement 解释，ledger entries 可以解释成功转账。
- `DEBIT_POSTED` 状态不存在缺少 `FreezeConsumed` 或 `DebitPosted` 的情况。
- `CREDIT_POSTED` 状态不存在缺少 `AccountCredited` 或 `CreditPosted` 的情况。
- `AccountCredited` 先于 `CreditPosted` 发生时，系统状态只能暴露为等待 ledger retry、manual repair/review 或对账差异，不能被属性测试接受为普通补偿成功。

## 层次 3：集成测试

使用真实中间件语义：

- 数据库事务。
- Kafka 至少一次投递。
- Redis 幂等缓存或锁辅助。
- Outbox 发布器。

集成测试要验证每个服务的本地事务边界：

- orchestrator 创建 transfer、幂等记录、状态变更和 outbox 必须原子提交。
- account-service 的 freeze、consume、credit、movement、dedup 和 outbox 必须原子提交。
- ledger-service 的 debit/credit entry、posting dedup 和 outbox 必须原子提交。
- reconciliation-service 的输入归档、dedup、差异记录和修复工单必须原子提交。

集成测试还要验证中间件语义不会被误当作业务事实：

- Kafka offset 不能作为业务幂等、过账或对账完成依据。
- Redis 锁或缓存丢失不能破坏数据库中的幂等约束。
- Outbox 事件重复发布时，消费者 inbox/dedup 仍保持业务效果唯一。
- 发布 `TransferSucceeded` 失败不能否定 orchestrator 本地已经提交的 `TransferSucceeded` 事实；必须由 outbox 发布器继续发布或告警。

## 层次 4：故障注入

必须覆盖：

- RPC 超时但对方成功。
- 消费成功但 ack 失败。
- Orchestrator 在任意状态宕机。
- Outbox 发布器宕机。
- Kafka 重复投递。
- DB 死锁或事务超时。

故障注入必须能停在每个关键事实提交之后、调用方观察之前：

- `TransferRequested` 已提交但响应失败。
- `RiskApproved` 或 `RiskRejected` 已提交但 orchestrator 未观察到。
- `DebitReserved` 已提交但 orchestrator 超时。
- `FreezeConsumed` 已提交但 `DebitPosted` 未提交。
- `DebitPosted` 已提交但 orchestrator 宕机。
- `AccountCredited` 已提交但 `CreditPosted` 未提交。
- `CreditPosted` 已提交但 `TransferSucceeded` 未提交。
- `TransferSucceeded` 已提交但 outbox 尚未发布到 Kafka。

故障注入的期望结果必须按 F05 子场景断言：

- 缺少借方 ledger fact 时，重试 `DebitPosted` 或转人工修复，不能只回滚状态。
- 缺少贷方 account fact 时，优先正向重试贷方入账；满足策略前不能静默补偿。
- `AccountCredited` 已经发生但 `CreditPosted` 缺失时，必须重试 `PostCreditEntry` 或进入 manual repair/review，不能扣回收款方、不能标记 `COMPENSATED`。
- 借贷双方事实都已完成但最终确认缺失时，只能重试最终确认，不能回退状态或发起资金补偿。

## 层次 5：历史检查

记录并发操作历史：

- request
- response
- event
- state transition
- ledger entry
- reconciliation result

检查历史是否违反资金守恒、幂等和状态机约束。

历史检查需要把 account-side fact、ledger-side fact 和 transfer state 关联到同一个 `transfer_id` 与 `idempotency_key`：

- 每个 `request` 必须能关联到幂等记录和最终响应或可观测异常。
- 每个 `state transition` 必须有前置事实证据，并符合允许跳转表。
- 每个 `DebitPosted` 必须能关联到 `FreezeConsumed`，否则标记 account/ledger 差异。
- 每个 `CreditPosted` 必须能关联到 `AccountCredited`，否则标记 account/ledger 差异。
- 每个 `TransferSucceeded` 必须能关联到 `FreezeConsumed`、`DebitPosted`、`AccountCredited`、`CreditPosted`。
- 已经进入 `FAILED`、`COMPENSATED` 或 `MANUAL_REVIEW` 的历史不能再出现普通状态推进，除非通过明确的人工修复交易表达。

历史检查应输出可定位证据，包括缺失的事件、重复的业务效果、非法状态边、未发布 outbox、未消费事件和需要人工修复的 transfer。

## 层次 6：对账验证

对账输入：

- transfer 表。
- account balance snapshot。
- ledger entries。
- outbox events。
- consumer processed events。

对账输出：

- 无差异。
- 单边账。
- 重复账。
- 状态悬挂。
- 分录缺失。
- 需要人工处理。

对账验证必须把状态、账户和账本分开判断：

- `transfer` 表为 `SUCCEEDED` 时，必须存在 `TransferSucceeded`，并且借贷两边 account movement 与 ledger entries 都完整。
- `DEBIT_POSTED` 时，必须存在 `FreezeConsumed` 和 `DebitPosted`；缺任一项都应输出状态悬挂或分录缺失。
- `CREDIT_POSTED` 时，必须存在 `AccountCredited` 和 `CreditPosted`；缺任一项都应输出状态悬挂或分录缺失。
- 存在 `AccountCredited` 但缺少 `CreditPosted` 时，应输出需要 ledger retry 或 manual repair/review 的差异，不能输出普通补偿完成。
- 存在 `DebitPosted` 但缺少 `CreditPosted` 时，应根据 `AccountCredited` 是否存在区分正向重试、允许补偿或人工处理。
- outbox 中存在未发布或未消费事件时，应区分业务事实已提交和异步通知未完成，不能把通知失败误判为资金事实不存在。

对账验证的成功标准不是“没有告警”，而是每类差异都有稳定分类、可重复定位、明确 owner 和可审计的修复路径。
