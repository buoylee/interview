# 01 分布式转账

## 目标

用 A 给 B 转账这个最小资金场景，学习真实金融系统中的分布式一致性、账务建模、幂等、状态机、Outbox、补偿、对账和验证方法。

转账场景不是单库事务 demo。它从第一天就按分布式服务边界分析：

- `transaction-orchestrator`
- `account-service`
- `ledger-service`
- `risk-service`
- `reconciliation-service`
- `message-broker`

## 学习顺序

1. [正确性不变量](./01-invariants.md)
2. [状态机](./02-state-machine.md)
3. [服务边界](./03-service-boundaries.md)
4. [事件流](./04-event-flow.md)
5. [失败矩阵](./05-failure-matrix.md)
6. [验证路线](./06-verification-plan.md)
7. [面试表达](./07-interview-synthesis.md)

## 核心问题

- 为什么不能只在一个数据库事务里扣 A、加 B？
- 为什么余额字段不能作为唯一事实来源？
- 为什么成功转账必须有借贷两边分录？
- 幂等键到底保护的是请求、消息还是业务结果？
- 扣款成功但入账失败时，系统如何恢复？
- 消息重复、乱序、延迟时，如何保证不重复扣款？
- 对账发现单边账后，如何定位和修复？
- 如何用不变量和故障注入验证系统正确性？
