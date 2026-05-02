# 映射到真实系统

代码实验室刻意使用小型内存模型，目的是把证据、不变量和判定器的边界讲清楚。真实系统接入 MySQL、消息队列、渠道文件、日志和审计表时，概念可以按下表映射。

| Lab concept | Real system counterpart |
| --- | --- |
| `Fact` | MySQL row, channel statement row, broker delivery record, workflow history event |
| `History` | Ordered evidence collected from DB, broker, logs, channel files, and audit tables |
| `ConsistencyVerifier` | Independent reconciliation or invariant checker |
| `Generator` | Property test, replay test, or fault injection fixture |
| `InvariantViolation` | Reconciliation difference, audit finding, or test failure report |

## 工程落点

- `Fact` 不只来自业务库，也可能来自渠道账单、MQ 投递日志、工作流历史、审计表和人工修复单。
- `History` 是按时间或证据顺序整理后的观察结果，不等于某一个服务的当前状态。
- `ConsistencyVerifier` 应当独立于被验证业务流程，避免业务实现和验证逻辑共享同一个错误假设。
- `Generator` 在真实工程中可以变成属性测试、历史回放、故障注入脚本或混沌测试夹具。
- `InvariantViolation` 是可处理的差异报告，需要能指回原始证据，支持自动修复、人工复核或审计归档。

## 边界提醒

MySQL 可以存储事实、承载本地事务、暴露锁和隔离级别实验，但它不是一致性判定器本身。判定器要能跨越数据库、消息、外部渠道和人工流程收集证据，然后独立判断“不变量是否被违反”。
