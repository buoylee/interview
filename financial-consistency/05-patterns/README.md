# 05 一致性模式与框架选型

## 目标

这一阶段把前四个业务阶段沉淀成模式决策手册。重点不是背诵 Outbox、Saga、TCC、Temporal、事务消息、CDC 的定义，而是判断真实业务问题应该用哪个模式、哪个模式不能解决什么、以及如何验证模式真的保护了一致性。

## 学习顺序

1. [决策地图](./01-decision-map.md)
2. [Outbox 和本地消息表](./02-outbox-local-message-table.md)
3. [Saga](./03-saga.md)
4. [TCC](./04-tcc.md)
5. [Temporal](./05-temporal.md)
6. [事务消息和 CDC](./06-transactional-message-cdc.md)
7. [框架比较](./07-framework-comparison.md)
8. [模式组合](./08-pattern-composition.md)
9. [验证方法](./09-verification.md)
10. [面试表达](./10-interview-synthesis.md)

## 核心问题

- Outbox、Saga、TCC、Temporal、事务消息和 CDC 分别解决什么问题？
- 为什么一个框架不能替代状态机、幂等、账本和对账？
- 为什么 Saga 的补偿不是回滚？
- 为什么 TCC 的 Try 必须真实预留资源？
- 为什么 Temporal 适合长流程编排，但不能当业务事实来源？
- 为什么用了 Kafka 或事务消息仍然需要 Outbox、消费者幂等和对账？
- 为什么金融级系统必须验证模式在超时、重复、乱序、宕机和人工修复下仍然成立？

## 本阶段结论

一致性模式不是可互换的名词。真实系统通常组合使用状态机、幂等、Outbox、Saga、TCC-like 资源预留、Temporal 编排、事务消息或 CDC、对账和人工修复。每个模式都必须明确事实来源、适用边界、危险误用和验证方法。
