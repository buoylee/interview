# 09 代码实验室

这是一个纯 Java 内存代码实验室，用来把金融一致性章节里的概念落到可运行的模型、异常历史、一致性判定器、runner 和失败报告上。

## 目标

- 用 `Fact`、`History`、`Command`、`Event` 描述可审计证据，而不是只描述某个服务的内部状态。
- 用 `ConsistencyVerifier` 把资金、外部渠道、消息传播、状态机和人工修复的不变量编码出来。
- 用固定实验用例复现常见一致性风险：重复请求、单边流水、渠道超时后成功、Outbox 未发布、重复消费、TCC 竞态、组合预订失败和人工修复重复提交。
- 用可解释失败报告训练排查方式：先看违反的不变量，再看相关证据，再读裁剪后的历史。

## 运行方式

从仓库根目录运行：

```bash
bash financial-consistency/09-code-lab/scripts/test-lab.sh
bash financial-consistency/09-code-lab/scripts/run-lab.sh list
bash financial-consistency/09-code-lab/scripts/run-lab.sh run --case payment-timeout-late-success
bash financial-consistency/09-code-lab/scripts/run-lab.sh run
```

更完整的运行说明见 [01-running-the-lab.md](./docs/01-running-the-lab.md)。

## 学习顺序

1. 先运行自检脚本，确认当前 runner、生成器和 verifier 的行为一致。
2. 再用 `list` 看全部实验，区分期望通过和期望失败的用例。
3. 单独运行 `payment-timeout-late-success`，练习阅读失败报告。
4. 最后运行全量实验，把报告字段映射到真实工程里的数据库、消息、渠道和审计证据。

配套阅读：

- [01-running-the-lab.md](./docs/01-running-the-lab.md)
- [02-reading-failure-reports.md](./docs/02-reading-failure-reports.md)
- [03-mapping-to-real-systems.md](./docs/03-mapping-to-real-systems.md)

## 实验列表

当前实验覆盖以下类型：

- 转账：正常平衡流水、重复请求、单边流水。
- 支付渠道：超时未知后成功、先本地失败后渠道晚成功。
- 消息传播：Outbox 已提交未发布、消费者重复业务效果。
- 电商交易：外部支付成功但库存本地失败。
- TCC：同一个参与者同时出现 confirm 和 cancel 终态。
- 旅行 Saga：供应商成功但订单失败、人工修复成功、人工修复重复提交。

用例清单以 runner 输出为准：

```bash
bash financial-consistency/09-code-lab/scripts/run-lab.sh list
```

## 关键边界

这里的 verifier 是一致性判定器，不是 Oracle 数据库。MySQL 会在后续真实工程阶段作为事实存储和事务实验对象出现，但不能替代独立判定器。

实验室只使用内存模型和固定历史，目的是把“不变量如何被证据验证”讲清楚。真实工程阶段会把这些概念接到 MySQL、消息队列、渠道文件、审计表、日志和对账任务上。
