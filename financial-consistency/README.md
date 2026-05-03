# 金融级分布式事务与一致性

这是一个独立学习与实现目录，用来系统化整理金融级事务、一致性、幂等、补偿、对账和可扩展架构。

正式设计文档：

- [2026-05-01-financial-consistency-design.md](../docs/superpowers/specs/2026-05-01-financial-consistency-design.md)
- [2026-05-01-financial-scenario-matrix-design.md](../docs/superpowers/specs/2026-05-01-financial-scenario-matrix-design.md)
- [2026-05-01-financial-scenario-matrix-expansion-design.md](../docs/superpowers/specs/2026-05-01-financial-scenario-matrix-expansion-design.md)
- [2026-05-01-payment-recharge-withdraw-design.md](../docs/superpowers/specs/2026-05-01-payment-recharge-withdraw-design.md)
- [2026-05-02-order-payment-inventory-design.md](../docs/superpowers/specs/2026-05-02-order-payment-inventory-design.md)
- [2026-05-02-travel-booking-saga-design.md](../docs/superpowers/specs/2026-05-02-travel-booking-saga-design.md)
- [2026-05-02-financial-consistency-patterns-design.md](../docs/superpowers/specs/2026-05-02-financial-consistency-patterns-design.md)
- [2026-05-02-financial-consistency-verification-lab-design.md](../docs/superpowers/specs/2026-05-02-financial-consistency-verification-lab-design.md)
- [2026-05-02-financial-consistency-reconciliation-design.md](../docs/superpowers/specs/2026-05-02-financial-consistency-reconciliation-design.md)
- [2026-05-02-financial-consistency-interview-synthesis-design.md](../docs/superpowers/specs/2026-05-02-financial-consistency-interview-synthesis-design.md)
- [2026-05-02-financial-consistency-code-lab-design.md](../docs/superpowers/specs/2026-05-02-financial-consistency-code-lab-design.md)
- [2026-05-03-financial-consistency-service-prototype-design.md](../docs/superpowers/specs/2026-05-03-financial-consistency-service-prototype-design.md)
- [旧笔记索引](./references.md)

## 当前决策

- 主线语言：Java。
- 辅助语言：Go，用于后续压测、故障注入或基础设施工具。
- 主框架路线：Spring Boot + Kafka + Outbox + Temporal。
- 对比框架：Seata、Camunda；用于理解取舍，不作为主实现路线。
- 架构形态：从第一阶段开始就是分布式服务边界，不用单体服务作为主实现。
- 起点场景：A 给 B 转账。
- 最终目标：从转账扩展到充值、提现、支付回调、电商交易、机票酒店组合预订、退款、跨境和多币种结算。

## 目标

从最简单的交易场景开始，逐步建立真实金融系统需要的能力：

- 资金模型：账户、余额、冻结、流水、会计分录。
- 分布式一致性：Saga、TCC、Temporal、Outbox、事务消息、补偿、对账。
- 科学验证：不变量、模型验证、属性测试、故障注入、历史检查。
- 可靠性：幂等、重试、消息重复、乱序、超时、宕机恢复。
- 可观测性：trace、审计日志、状态机、事件流、对账报告。
- 可扩展性：服务边界清晰，后续能自然演进到 Kubernetes 和真实中间件部署。

## 学习循环

每个场景都按同一套顺序推进：

```text
业务场景
-> 正确性不变量
-> 状态机和事件模型
-> 形式化/半形式化推演
-> 真实代码实现
-> 属性测试和集成测试
-> 故障注入和历史检查
-> 对账闭环
-> 面试和架构评审表达
```

核心原则：先知道系统永远不能违反什么，再讨论用什么事务模式和框架。

## 阶段路线

- [00-scenario-matrix](./00-scenario-matrix.md)
  真实分布式事务场景地图：资金内核、外部渠道、组合交易、清结算和人工修复。

- [01-transfer](./01-transfer/README.md)
  分布式转账：账户、冻结、扣减、入账、流水、幂等、补偿、对账。

- [02-payment-recharge-withdraw](./02-payment-recharge-withdraw/README.md)
  充值、提现、支付回调、渠道超时、渠道对账。

- [03-order-payment-inventory](./03-order-payment-inventory/README.md)
  电商下单、支付、库存、取消、退款、消息最终一致性。

- [04-travel-booking-saga](./04-travel-booking-saga/README.md)
  机票、酒店、租车、保险组合预订，处理外部系统不可控和不可逆动作。

- [05-patterns](./05-patterns/README.md)
  Outbox、TCC、Saga、Temporal、Seata、Camunda、本地消息表、事务消息、CDC、状态机和幂等模式。

- [06-verification-lab](./06-verification-lab/README.md)
  不变量、模型验证、属性测试、故障注入、历史检查、恢复演练。

- [07-reconciliation](./07-reconciliation/README.md)
  准实时对账、日终对账、差错处理、人工补偿。

- [08-interview-synthesis](./08-interview-synthesis/README.md)
  面试表达、架构评审话术、常见追问。

- [09-code-lab](./09-code-lab/README.md)
  纯 Java 内存代码实验室：模型、异常历史、一致性判定器、runner 和可解释失败报告。

- [10-service-prototype](./10-service-prototype/README.md)
  Spring Boot + MySQL 内部转账服务原型：本地事务、幂等、双分录账本、Outbox 和数据库事实验证。

## 真实工程约束

- 所有写接口必须支持幂等。
- 所有消息消费者必须能处理重复消息。
- 所有跨服务流程必须有明确状态机。
- 本地事务只保护单服务内的数据一致性。
- 外部系统默认不可控，不参与我们的数据库事务。
- 对账是核心链路，不是后期补丁。
- 验证是主线，不是实现完成后的补充测试。
- 任何资金变化都必须可审计、可追踪、可恢复。

## 旧笔记归档策略

旧文档不移动，后续通过 `references.md` 按主题链接：

- MySQL 事务、锁、隔离级别。
- MQ 消息幂等、防丢、本地消息表、事务消息。
- Seata、TCC、AT、Saga。
- Redis Lua、分布式锁。
- 支付轮询、回调、异步等待。
- CAP、ZooKeeper、etcd、一致性协议。
