# 03 服务边界

## 服务列表

| 服务 | 拥有的数据 | 本地事务边界 | 不拥有的数据 |
|---|---|---|---|
| `transaction-orchestrator` | transfer 状态、workflow 进度、补偿记录 | 单个 transfer 状态推进 | 账户余额、会计分录 |
| `account-service` | account、balance、freeze 记录 | 单账户冻结、解冻、扣减、入账 | 全局交易流程 |
| `ledger-service` | ledger entry、journal、posting batch | 分录创建和过账 | 账户可用余额 |
| `risk-service` | 风控规则、限额检查结果 | 风控决策记录 | 资金状态 |
| `reconciliation-service` | 对账批次、差错记录、修复工单 | 对账结果和差错状态 | 原始资金事实 |
| `message-broker` | Kafka topic、consumer offset | 消息投递语义 | 业务状态 |

## transaction-orchestrator

职责：

- 接收转账命令。
- 创建幂等记录和 transfer 状态。
- 调用风控、账户、账本服务。
- 推进状态机。
- 触发补偿。
- 将无法自动恢复的交易转入 `MANUAL_REVIEW`。

不直接修改：

- 账户余额。
- 会计分录。

## account-service

职责：

- 冻结付款方资金。
- 扣减冻结金额。
- 给收款方入账。
- 保证单账户内余额更新的本地事务正确性。

本地事务必须同时更新：

- account balance snapshot。
- account movement 或 freeze record。
- outbox event，如果该变化需要异步通知。

## ledger-service

职责：

- 创建借方和贷方分录。
- 保证同一 transfer 的分录可追踪。
- 支持通过分录重建资金变化。

## 服务间原则

- 禁止跨服务共享数据库。
- 禁止跨服务直接改表。
- 跨服务调用必须带 `transaction_id`、`idempotency_key`、`trace_id`。
- 跨服务调用超时不能直接等价于失败，必须查询或等待状态收敛。
