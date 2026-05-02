# 05 一致性模式与框架选型设计

日期：2026-05-02

## 目标

创建 `financial-consistency/05-patterns/`，把前四个业务阶段沉淀成可复用的模式决策手册。

这一阶段不做普通概念词典。学习者已经看过转账、充值提现、电商交易和旅行组合预订，现在需要回答真实工程问题：

- 一个跨服务流程应该用 Outbox、Saga、TCC、事务消息、CDC、Temporal，还是组合使用？
- 哪些模式解决“消息不丢”，哪些模式解决“长流程编排”，哪些模式解决“资源预留”，哪些模式只是框架能力？
- 每种模式最危险的误用是什么？
- 如何验证模式真的保护了一致性，而不是只在正常路径里看起来可用？
- 国际视角下，Temporal、Camunda、Seata 等框架分别适合什么边界？

完成后，学习者应该能把模式选择讲成工程决策，而不是背诵定义。

## 背景

已有阶段提供了模式使用场景：

- `01-transfer`：内部资金转账，需要状态机、幂等、账本和对账。
- `02-payment-recharge-withdraw`：外部支付渠道接入，需要超时处理、回调、查询、退款和渠道对账。
- `03-order-payment-inventory`：订单、支付、库存，需要库存预留、取消、退款和消息最终一致性。
- `04-travel-booking-saga`：机票、酒店、租车、保险组合预订，需要长流程 Saga、供应商未知、不可逆动作、付款策略、人工处理和对账。

`05-patterns` 的作用是反过来总结这些场景：不是“这个模式是什么”，而是“什么问题应该用它，什么问题不能指望它解决”。

## 范围

第一版覆盖这些模式和框架：

- Outbox / 本地消息表。
- Saga。
- TCC。
- Temporal。
- 事务消息。
- CDC。
- 状态机和幂等。
- Seata、Camunda、Temporal 的框架定位对比。
- 模式组合策略。
- 模式验证策略。

必须覆盖的业务映射：

- 内部转账。
- 充值、提现和支付回调。
- 电商下单、支付、库存和退款。
- 旅行组合预订。
- 对账和人工修复。

## 非目标

第一版不做这些事情：

- 不写框架 API 教程。
- 不安装或运行 Temporal、Camunda、Seata、Kafka、RocketMQ、Debezium。
- 不实现 Java 代码。
- 不比较所有工作流引擎和消息中间件。
- 不做厂商营销式排名。
- 不把单个框架包装成所有一致性问题的答案。

后续真正进入实现阶段时，可以为 Temporal、Outbox、TCC 或 CDC 单独开实验模块。

## 目录设计

新增目录：

```text
financial-consistency/05-patterns/
```

新增文件：

```text
README.md
01-decision-map.md
02-outbox-local-message-table.md
03-saga.md
04-tcc.md
05-temporal.md
06-transactional-message-cdc.md
07-framework-comparison.md
08-pattern-composition.md
09-verification.md
10-interview-synthesis.md
```

文件职责：

- `README.md`：阶段目标、学习顺序和核心问题。
- `01-decision-map.md`：按业务问题选择一致性模式。
- `02-outbox-local-message-table.md`：本地事务和事件投递一致性。
- `03-saga.md`：长流程、补偿、部分成功和人工处理。
- `04-tcc.md`：Try / Confirm / Cancel 资源预留模型。
- `05-temporal.md`：Temporal 在长流程 Saga 中的位置和边界。
- `06-transactional-message-cdc.md`：事务消息、CDC 与 Outbox 的取舍。
- `07-framework-comparison.md`：Temporal、Camunda、Seata 的国际化视角定位。
- `08-pattern-composition.md`：真实系统中多模式组合使用。
- `09-verification.md`：每种模式的可验证方法和故障注入点。
- `10-interview-synthesis.md`：面试和架构评审表达。

## 核心设计原则

### 模式解决的是不同问题

模式不能混用成口号。每个模式必须绑定它真正解决的问题：

| 问题 | 首选模式 | 关键边界 |
| --- | --- | --- |
| 本地事实已提交，事件不能丢 | Outbox / 本地消息表 | 不能证明下游业务完成 |
| 长流程跨服务，不要求原子提交 | Saga | 补偿不是数据库回滚 |
| 资源可以预留、确认、取消 | TCC | Try 阶段必须真实锁定资源 |
| 流程持续数分钟到数天，需要超时和重试 | Temporal | 不替代领域事实、幂等、账本和对账 |
| 消息系统支持事务发送 | 事务消息 | 只覆盖特定 broker 语义，不等于跨服务事务 |
| 从数据库事实生成事件流 | CDC | 捕获变化不等于知道业务语义 |
| 业务状态不能非法推进 | 状态机 + 幂等 | 所有模式都依赖它 |
| 事后发现本地、外部、资金或账本不一致 | 对账 | 对账不能直接改历史事实 |

### 任何模式都必须回答三个问题

每个模式文档都必须固定回答：

1. 它保护的事实是什么？
2. 它不能保护的边界是什么？
3. 它如何被验证？

如果一个模式只能解释正常路径，而不能解释超时、重复、乱序、宕机、人工修复和对账，就不能算金融级设计。

### 框架不是事实来源

Temporal、Camunda、Seata、Kafka、RocketMQ、Debezium 都不是业务事实来源。

业务事实必须落在领域服务、供应商事实、支付渠道事实、退款渠道事实、账本、Outbox、人工审批和对账记录中。框架可以编排流程、传递消息、捕获变化或管理重试，但不能替代状态机、幂等键、唯一约束、账本分录和对账。

## 决策地图

`01-decision-map.md` 必须提供从问题到模式的决策路径。

关键问题：

- 是否只需要保证本地状态变更和消息发布一致？
- 是否需要跨多个服务推进长流程？
- 失败后是否可以补偿？
- 资源是否支持 Try / Confirm / Cancel？
- 外部系统是否可控？
- 是否存在不可逆动作？
- 是否必须人工审批？
- 是否必须通过对账才能确认外部事实？

文档要给出结论：

- 转账内部账户更新不应直接用 Saga 逃避账本一致性。
- 充值提现不能把渠道超时当失败，必须结合查询和对账。
- 电商库存适合预留模型，但支付成功后的取消需要退款流程。
- 旅行组合预订适合 Saga + Temporal 编排，但供应商事实和资金事实必须独立持久化。
- 对账和人工修复不是模式失败后的补丁，而是金融级闭环的一部分。

## Outbox / 本地消息表

`02-outbox-local-message-table.md` 必须讲清：

- Outbox 解决本地事务和事件发布之间的不一致。
- 业务表和 Outbox 表必须在同一数据库事务中提交。
- Publisher 可以重试投递。
- 消费者必须幂等。
- broker offset 不能证明业务完成。
- Outbox 不解决下游是否成功、外部供应商是否确认、支付是否到账、退款是否成功。

必须映射的场景：

- 转账流水创建后发布 `TransferRecorded`。
- 支付成功后发布 `PaymentCaptured`。
- 库存确认后发布 `InventoryConfirmed`。
- 旅行供应商确认后发布 `FlightTicketed` 或 `HotelConfirmed`。

必须包含的危险误用：

- 状态更新和消息发送不在同一事务。
- 事件发布失败后重做外部扣款或供应商动作。
- 消费者只依赖 offset 去重。
- 把事件投递成功当作下游业务完成。

## Saga

`03-saga.md` 必须讲清：

- Saga 把大流程拆成一组本地事务和补偿动作。
- 补偿是业务动作，不是数据库回滚。
- Saga 适合长流程和外部系统参与的场景。
- Saga 不保证强原子性。
- 每一步必须有状态、幂等键、失败处理和补偿边界。

必须映射的场景：

- 电商下单：创建订单、预留库存、支付、确认库存、发货。
- 旅行预订：预授权、出票、酒店确认、附加项确认、扣款、补偿。
- 充值提现：渠道请求、查询、回调、对账、人工处理。

必须包含的危险误用：

- 以为 Saga 能保证所有参与者同时提交。
- 没有子订单状态，只靠总状态补偿。
- 供应商未知时直接走失败补偿。
- 已发生不可逆动作后试图删除本地事实。

## TCC

`04-tcc.md` 必须讲清：

- TCC 的 Try 必须真实预留业务资源。
- Confirm 必须只确认 Try 成功的资源。
- Cancel 必须释放 Try 预留的资源。
- Try / Confirm / Cancel 都必须幂等。
- Cancel 必须能处理空回滚和悬挂。

必须映射的场景：

- 内部账户冻结、扣减和释放。
- 库存预留、确认和释放。
- 支付预授权、capture 和 void。

必须说明不适合的场景：

- 外部供应商不支持资源预留。
- 机票出票或保险生效已经不可逆。
- 无法保证 Try 阶段的资源隔离。
- Cancel 没有可靠语义。

## Temporal

`05-temporal.md` 必须讲清：

- Temporal 适合长流程 Saga、定时器、超时、重试、人工等待和 workflow 恢复。
- Temporal 可以记录 workflow 历史，但业务事实仍要落在领域服务和账本中。
- Activity 必须幂等。
- Workflow 不应直接把外部超时当业务失败。
- Compensation 必须按业务可逆性设计。

Temporal 当前官方文档把 Saga 描述为把复杂流程拆成小事务，失败时执行补偿动作；也强调 Temporal 管理状态和重试逻辑。这个阶段只能使用该定位，不能把 Temporal 写成分布式事务数据库。

必须映射的场景：

- 旅行组合预订的长流程编排。
- 支付渠道查询和超时轮询。
- 人工处理等待和恢复。
- 退款未知后的周期查询。

必须包含的危险误用：

- 把 workflow history 当账本。
- Activity 没有幂等键。
- 在 workflow 内直接改多个服务数据库。
- 以为 Temporal 可以替代 Outbox、状态机和对账。

## 事务消息和 CDC

`06-transactional-message-cdc.md` 必须把事务消息和 CDC 放在同一章比较。

事务消息必须讲清：

- 它依赖特定消息中间件语义。
- 它通常解决本地事务和消息发送一致性。
- 它不能自动保证消费者业务成功。
- 它不能替代消费者幂等和对账。

CDC 必须讲清：

- CDC 从数据库提交日志捕获变化。
- CDC 适合事实流出、搜索索引、读模型、审计和集成。
- CDC 不理解业务补偿语义。
- CDC 不能替代领域事件建模。

必须比较：

- Outbox publisher。
- 事务消息。
- CDC。

结论要明确：

- 金融级系统更关心事实可解释性，而不是只关心消息是否送达。
- 不管选择哪种消息传播机制，消费者幂等、状态机、对账都不能省。

## 框架比较

`07-framework-comparison.md` 必须采用国际视角，不以国内常见方案作为唯一中心。

比较对象：

- Temporal。
- Camunda。
- Seata。

比较维度：

- 核心定位。
- 国际生态和常见使用场景。
- 适合解决的问题。
- 不适合解决的问题。
- 与 Outbox、Saga、TCC、状态机、账本和对账的关系。
- 在本教程中的推荐位置。

预期结论：

- Temporal：推荐作为长流程编排和可靠执行学习主线，尤其适合 Saga、超时、重试、人工等待。
- Camunda：更偏 BPMN、流程建模、人工任务和业务流程治理；适合理解流程编排和审批，但不是资金一致性的基础设施本身。
- Seata：适合理解 AT/TCC/Saga 等分布式事务框架思想，在国际金融级架构表达中不应作为唯一主线。

执行阶段写该文档时，必须用官方文档校准框架定位和术语。

## 模式组合

`08-pattern-composition.md` 必须说明真实系统通常不是单模式。

必须给出组合示例：

### 内部转账

```text
状态机 + 幂等 + 账本 + Outbox + 对账
```

重点：账户和账本事实不能交给 Saga 随意补偿。

### 充值提现

```text
状态机 + 渠道幂等 + Outbox + 查询/回调 + 对账 + 人工处理
```

重点：渠道超时不是失败。

### 电商下单

```text
库存预留/TCC-like + Saga + Outbox + 退款 + 对账
```

重点：库存和支付有不同事实来源。

### 旅行组合预订

```text
Temporal Saga + 状态机 + Outbox + 付款策略 + 供应商查询 + 退款 + 对账 + 人工处理
```

重点：核心项和附加项分层，不可逆动作不能回滚。

## 验证策略

`09-verification.md` 必须按模式给出验证方式。

覆盖：

- Outbox：本地事务提交后 publisher 崩溃，恢复后事件补发且外部动作不重复。
- Saga：任意步骤失败后，已成功步骤进入合法补偿或人工处理。
- TCC：Try / Confirm / Cancel 幂等、空回滚、悬挂、防重复确认。
- Temporal：worker 重启、Activity 重试、timer 恢复、人工等待恢复，业务事实不重复。
- 事务消息：半消息、提交、回查、重复投递和消费者幂等。
- CDC：重复捕获、乱序投影、schema 变化和下游幂等。
- 状态机：非法状态转换被拒绝。
- 对账：本地事实、外部事实、资金事实和账本事实可互相解释。

验证方法必须包含：

- 不变量检查。
- 属性测试。
- 故障注入。
- 历史回放。
- 对账验证。
- 人工修复审计检查。

## 面试和架构评审表达

`10-interview-synthesis.md` 必须把模式选择讲成结构化表达。

高频问题：

- Outbox 和事务消息有什么区别？
- Saga 和 TCC 有什么区别？
- 为什么 Saga 不是回滚？
- Temporal 能不能保证分布式事务？
- 为什么用了 Kafka 还需要 Outbox？
- 为什么用了 Temporal 还需要状态机和对账？
- CDC 和领域事件有什么区别？
- Seata、Camunda、Temporal 怎么选？
- 金融系统里最不能省的模式是什么？

回答底线：

- 不接受“一个框架解决所有一致性问题”。
- 不接受“消息发出去就代表业务成功”。
- 不接受“workflow 成功就代表账平”。
- 不接受“补偿就是删除之前的数据”。
- 不接受“对账是报表系统的事情”。

## 根 README 更新

完成 `05-patterns` 后，需要更新 `financial-consistency/README.md`：

- 在正式设计文档列表加入本设计文档链接。
- 将阶段路线里的 `05-patterns` 改成链接到 `./05-patterns/README.md`。

## 验收标准

文档完成后必须满足：

- `financial-consistency/05-patterns/` 包含 11 个文件。
- `README.md` 链接所有子文档。
- `01-decision-map.md` 能从业务问题推导模式选择。
- 每个模式文档都包含适用场景、不能解决的问题、危险误用和验证方法。
- `07-framework-comparison.md` 明确 Temporal、Camunda、Seata 的边界。
- `08-pattern-composition.md` 映射前四个业务阶段。
- `09-verification.md` 给出每种模式的故障注入和历史检查方法。
- `10-interview-synthesis.md` 能支撑面试和架构评审表达。
- 根 README 链接更新。
- 不修改 `01-transfer`、`02-payment-recharge-withdraw`、`03-order-payment-inventory`、`04-travel-booking-saga` 的既有内容。

## 参考资料策略

框架和中间件会更新。执行阶段写框架相关文档时，应优先用官方资料校准：

- Temporal 官方文档，用于 durable execution、workflow、activity、retry、Saga compensation 的定位。
- Camunda 官方文档，用于 BPMN、process orchestration、human task 的定位。
- Seata 官方文档，用于 AT、TCC、Saga 等分布式事务模式的定位。

第一版 spec 已用 Context7 查询 Temporal 官方资料，确认 Temporal 文档将 Saga 定位为复杂 workflow 中的小事务和补偿动作，并强调 Temporal 负责状态和重试逻辑。后续文档不得把这个定位扩大成“Temporal 替代业务事实、账本或对账”。
