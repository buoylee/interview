# 07 统一对账闭环

## 目标

这一阶段把对账从单个业务场景里的补充动作提升为金融级一致性的核心闭环。它关注的不是“写 SQL 查差异”，而是如何发现 Difference、创建 Case、执行 Repair、完成 Review，并用 Close 记录可审计的关闭原因。

对账的目标不是把报表临时调平，而是让领域事实、账本事实、渠道事实、供应商事实、清结算事实和人工事实最终互相解释。

## 学习顺序

1. [对账模型](./01-reconciliation-model.md)
2. [对账数据源](./02-reconciliation-sources.md)
3. [对账类型](./03-reconciliation-types.md)
4. [差错分类](./04-difference-classification.md)
5. [修复闭环](./05-repair-workflow.md)
6. [场景矩阵](./06-scenario-matrix.md)
7. [验证与审计](./07-verification-and-audit.md)
8. [面试表达](./08-interview-synthesis.md)

## 核心问题

- 为什么有了 Outbox、Saga、TCC、Temporal 和属性测试，仍然需要对账？
- 对账读取的是哪些事实源，哪些只是执行线索？
- 准实时对账、日终对账、T+N 对账和专项重跑分别解决什么问题？
- 差错应该如何分类、分级、分派和关闭？
- 为什么对账不能直接 update 业务状态或删除历史分录？
- 自动修复和人工修复如何保持幂等、审批、复核和审计？
- 如何验证对账系统本身不会制造新的不可解释事实？

## 本阶段边界

- 本阶段是文档设计，不创建 `reconciliation-service` 代码。
- 本阶段不创建数据库表、调度器、消息消费者、管理后台或报表服务。
- 本阶段不接入真实支付渠道、供应商、Kafka、Temporal、Flink、Spark 或数据库。
- 本阶段所有修复都必须追加事实，不能直接改平历史事实。
- 本阶段继承 06 的 Fact-first 原则：日志、workflow history、broker offset、consumer offset 和任务运行记录不能替代业务事实。

## 本阶段结论

金融级对账不是事后补丁，而是把不可避免的跨系统差异纳入可解释、可审计、可复核的事实闭环。合格对账必须能发现差异、分类差错、生成修复命令、执行审批复核，并证明关闭原因成立。
