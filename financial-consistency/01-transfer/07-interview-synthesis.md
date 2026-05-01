# 07 面试与架构评审表达

## 一句话回答

金融级转账不能只靠一个余额字段或一个跨服务事务。我们需要账户、分录、幂等、状态机、Outbox、补偿、对账和验证体系共同保证资金正确性。

更完整地说，Java/Spring + Kafka + Outbox + Temporal 可以作为国际化团队常见的主线技术组合，但真正保证资金正确性的不是某个框架，而是清晰的不变量、服务边界、耐久事实、分录、幂等、恢复策略、对账和验证闭环。

## 标准回答结构

1. 先定义资金不变量：钱不能多、不能少、不能重复扣。
2. 再定义服务边界：账户服务管余额，账本服务管分录，编排服务管流程。
3. 单服务内部使用本地事务。
4. 跨服务使用 Saga/TCC、Outbox 和消息最终一致性。
5. 所有写操作和消息消费都必须幂等。
6. 所有状态变化必须可追踪、可审计、可恢复。
7. 对账用于发现实现、消息和外部系统造成的差错。
8. 使用模型验证、属性测试和故障注入提前暴露事务问题。

展开时要把职责说清楚：

- `account-service` 拥有 operational balance、freeze 和 account movement，负责实时授权、冻结、扣减和入账。
- `ledger-service` 拥有 immutable accounting entries 和 posting batch，负责会计分录和审计事实。
- `transaction-orchestrator` 拥有 transfer 状态机、幂等命令记录、workflow 进度和补偿/人工处理标记。
- `reconciliation-service` 不声明新的资金事实，而是检测 account movement、balance snapshot 与 ledger posting 之间的 divergence。
- Kafka 负责投递语义，不能把 consumer offset 当作业务幂等、过账或对账完成的事实来源。

## 推荐表达顺序

面试或架构评审里不要从“我们用了分布式事务框架”开始，而要从资金事实开始：

1. 先说不变量：同一笔转账只能产生一次业务效果；成功转账必须同时存在借方 account movement、借方 ledger entry、贷方 account movement 和贷方 ledger entry；终态不能非法回退。
2. 再说本地事务：每个服务只在自己拥有的数据上做原子提交，例如 account-service 把 balance、freeze/movement、dedup 和 outbox 放在同一个本地事务里。
3. 再说跨服务恢复：跨服务不共享数据库，通过命令幂等、Outbox、Kafka 至少一次投递、consumer inbox/dedup 和状态机重试收敛。
4. 再说异常策略：超时不是失败，先查询事实；缺少哪一侧事实就重试或修复哪一侧事实；只有满足策略的场景才进入补偿。
5. 最后说验证闭环：用模型验证先检查状态机和事实依赖，再用属性测试、集成测试、故障注入、历史检查和对账验证持续暴露问题。

Temporal 可以作为 workflow orchestration：负责长流程、重试、定时器、补偿任务和人工处理入口。但 Temporal 不能替代资金不变量、账本分录、服务内本地事务、幂等约束、Outbox 或对账；它只是让编排更可靠、更可观测。

## 关键状态表达

状态名必须绑定已经持久化的耐久事实，不能只绑定“调用成功”或“消息收到了”：

- `DEBIT_POSTED` 必须同时具备 account-side `FreezeConsumed` 和 ledger-side `DebitPosted`。
- `CREDIT_POSTED` 必须同时具备 account-side `AccountCredited` 和 ledger-side `CreditPosted`。
- `SUCCEEDED` 只能在 `CREDIT_POSTED` 之后由 orchestrator 本地最终确认产生。
- `AccountCredited` 已发生但 `CreditPosted` 缺失时，应重试贷方 ledger posting，或进入 manual repair/review；这不是普通补偿路径，不能扣回收款方或直接标记 `COMPENSATED`。

## 常见追问

### 为什么不用一个分布式事务框架直接解决？

因为金融系统的很多动作不是数据库行更新，而是业务状态变化、外部系统调用、消息投递、不可逆动作和人工处理。框架可以帮助编排，但不能替代业务不变量、分录、幂等、补偿和对账。

如果使用 Temporal，它解决的是 workflow 持久化、重试、定时器和长流程可观测性问题；如果使用 Kafka 和 Outbox，它们解决的是事件可靠发布和最终一致性问题。这些工具都不能自动证明余额正确、分录完整或重复消息不会产生重复扣款。

### 扣款成功但入账失败怎么办？

系统不能静默结束。交易必须停留在可恢复、可观测的状态，并根据已经持久化的事实选择正向重试、允许场景下的补偿，或人工修复。

需要先区分事实：

- 只有冻结成功：可以释放冻结，失败则进入 `MANUAL_REVIEW`。
- `FreezeConsumed` 已发生但 `DebitPosted` 缺失：重试借方 ledger posting，或进入 manual repair/review。
- `FreezeConsumed` 和 `DebitPosted` 已发生，但 `AccountCredited` 未发生：优先正向重试贷方入账；确认贷方不会发生且策略允许时，才执行反向处理或人工处理。
- `AccountCredited` 已发生但 `CreditPosted` 缺失：重试 `CreditPosted`，自动重试耗尽后进入 manual repair/review；不能作为普通补偿扣回收款方。
- `AccountCredited` 和 `CreditPosted` 都已发生：只能重试最终确认到 `SUCCEEDED`，不能资金补偿或状态倒退。

通过分录、状态机、Outbox 和对账记录定位单边账，并执行解冻、冲正、补入账、补分录或人工修复。

### 如何证明不会重复扣款？

不能只说“代码判断了”。需要幂等键、数据库唯一约束、消费者去重、状态机防重、属性测试、重复消息故障注入和对账验证共同证明。

具体证据包括：

- 同一 `idempotency_key` 只能创建一个 transfer 和一次业务效果。
- `ReserveDebit`、`ConsumeFreeze`、`CreditReceiver`、`PostDebitEntry`、`PostCreditEntry` 都有命令或事件级 dedup。
- 数据库唯一约束防止同一 transfer 重复创建 movement 或 ledger entry。
- Kafka 重复投递时，consumer inbox/dedup 保证业务效果唯一。
- 状态机拒绝非法跳转和终态回退。
- 对账能发现重复账、单边账、分录缺失和状态悬挂。

### 对账是不是事后兜底，平时可以先不做？

不是。对账是资金系统的一部分，不是上线后的临时脚本。它负责发现 account movement、balance snapshot、ledger posting、outbox 事件和消费记录之间的 divergence，并生成差错记录、修复工单或人工审核输入。

没有对账，就无法证明系统在消息重复、乱序、超时、外部系统异常和人工修复之后仍然能发现并定位资金差异。

### 验证为什么要前置？

金融转账的错误通常出现在“某个事实已经提交，但调用方还没观察到”的缝隙里。只靠正常路径测试很难覆盖这些状态。

验证要先于实现形成学习闭环：

- 用模型验证检查状态机、事实依赖和非法跳转。
- 用属性测试随机生成重复提交、重试、重放消息和补偿序列。
- 用集成测试验证真实数据库事务、Kafka 至少一次投递、Outbox 发布器和 consumer dedup。
- 用故障注入停在 `FreezeConsumed`、`DebitPosted`、`AccountCredited`、`CreditPosted` 等关键事实提交之后。
- 用历史检查和对账验证证明每类差异都有稳定分类、明确 owner 和可审计修复路径。

## 评审时的底线

- 不接受“一个余额字段就是事实来源”的设计。
- 不接受跨服务共享数据库或直接改表。
- 不接受只用 broker offset 作为业务幂等、过账或对账事实。
- 不接受只凭单个服务响应推进需要双事实支撑的状态。
- 不接受 `AccountCredited` 后缺少 `CreditPosted` 时走普通补偿。
- 不接受没有模型验证、故障注入和对账验证的金融级转账方案。
