# 05 失败矩阵

## 失败场景

| 编号 | 失败点 | 可能结果 | 恢复策略 | 必须保持的不变量 |
|---|---|---|---|---|
| F01 | 请求重复提交 | 多次进入 orchestrator | 幂等键返回同一结果 | 同一幂等键只产生一次业务效果 |
| F02 | 风控服务超时 | 不知道风控是否通过 | 查询风控结果或重试 | 未通过风控不能扣款 |
| F03 | 冻结资金成功但响应超时 | orchestrator 以为失败 | 查询 account freeze 状态 | 不能重复冻结 |
| F04 | 借方分录成功但 orchestrator 宕机 | workflow 停在旧状态 | 恢复后同时检查 account-side `FreezeConsumed` 与 ledger-side `DebitPosted`；缺哪个事实就重试哪个事实，无法自动补齐则进入 manual repair/review | 借方分录不能重复，`DEBIT_POSTED` 必须同时具备 `FreezeConsumed` 与 `DebitPosted` |
| F05 | 借方成功，贷方失败 | 单边资金影响 | 按已持久化事实选择正向重试、允许场景下的补偿，或 manual repair/review | 不能静默丢失单边账 |
| F06 | Kafka 重复投递 | 消费者重复收到事件 | event_id 去重 | 不能重复扣款或入账 |
| F07 | Kafka 消息乱序 | 后置事件先到 | 状态机拒绝非法推进 | 状态不能倒退或跳跃 |
| F08 | Outbox 写入成功但发布器宕机 | 事件未发布 | 发布器重启继续扫描 | 状态变更对应事件最终发布或异常告警 |
| F09 | 补偿失败 | 资金状态悬挂 | 进入 `MANUAL_REVIEW` | 异常必须可见、可追踪 |
| F10 | 对账发现余额不一致 | account movement、balance snapshot 与 ledger posting 之间出现差异 | 生成差错记录和修复工单 | 账务差异不能被忽略 |

## F05 拆分说明

F05 不能只按“借方成功，贷方失败”粗略处理。恢复策略取决于已经持久化的 account movement fact 和 ledger posting fact。

| 子场景 | 已发生事实 | 未发生事实 | 允许的恢复策略 | 不允许的处理 | 必须保持的不变量 |
|---|---|---|---|---|---|
| F05a | `DebitReserved` | `FreezeConsumed`, `DebitPosted`, `AccountCredited`, `CreditPosted` | 释放冻结资金，进入 `COMPENSATING -> COMPENSATED`；释放失败则进入 `MANUAL_REVIEW` | 重复冻结或直接标记成功 | 资金不能被重复冻结，未完成转账不能消耗冻结 |
| F05b | `FreezeConsumed` | `DebitPosted`, `AccountCredited`, `CreditPosted` | 重试 `DebitPosted`；如果 ledger 永久不可恢复，生成人工修复工单并进入 `MANUAL_REVIEW` | 只按状态回滚而忽略已消耗冻结 | account movement 与 ledger posting 差异必须可见、可追踪 |
| F05c | `FreezeConsumed`, `DebitPosted` | `AccountCredited`, `CreditPosted` | 优先重试收款方入账；若确认贷方不会发生，可按补偿策略执行反向处理或人工处理 | 在未确认贷方缺失前静默补偿或静默失败 | 借方分录不能重复，单边资金影响不能被隐藏 |
| F05d | `FreezeConsumed`, `DebitPosted`, `AccountCredited` | `CreditPosted` | 重试贷方 ledger posting；自动重试耗尽后进入 manual repair/review | 走正常金融补偿、扣回收款方或标记 `COMPENSATED` | `AccountCredited` 已发生时必须补齐或修复 `CreditPosted`，不能制造新的单边账 |
| F05e | `FreezeConsumed`, `DebitPosted`, `AccountCredited`, `CreditPosted` | `TransferSucceeded` | 重试 orchestrator 最终确认，直到进入 `SUCCEEDED` 或暴露异常 | 执行资金补偿或回退到处理中早期状态 | 借贷双方已入账时只能完成最终确认，状态不能倒退 |

补偿只适用于贷方账户入账尚未发生、且继续正向完成已经不可行或策略明确要求终止的场景。只要 `AccountCredited` 已经持久化，就不能把它当作普通可补偿失败处理；如果 `CreditPosted` 缺失，必须重试 `PostCreditEntry`，或通过人工修复流程补齐 ledger 事实并保留审计记录。

## 故障注入原则

- 每个失败点都要能被测试主动触发。
- 每个失败点都要绑定至少一个不变量。
- 每个恢复策略都要有可观测证据：状态、分录、outbox、日志、trace 或对账记录。
- 故障注入应覆盖 `DebitReserved`、`FreezeConsumed`、`AccountCredited`、`DebitPosted`、`CreditPosted` 任意一个事实已经提交但响应、事件或状态推进失败的情况。
- 对于 `AccountCredited` 已经提交但 `CreditPosted` 未提交的情况，测试必须断言系统选择 ledger retry 或 manual repair/review，而不是普通补偿路径。
