# 09 代码实验室设计

日期：2026-05-02

## 目标

创建 `financial-consistency/09-code-lab/`，把前面阶段的金融一致性验证方法落成第一版可运行实验室。

这一阶段的重点不是搭建完整生产系统，而是实现一个能暴露事务一致性问题的最小可运行验证环境。学习者应该能运行实验、看到失败历史、理解被破坏的不变量，并知道真实金融系统为什么需要幂等、账本、状态机、Outbox、补偿、对账和人工修复。

完成后，学习者应该能回答：

- 如何把转账、支付、订单、旅行预订表达成可验证的历史？
- 为什么测试不能只断言接口返回成功，而要检查事实是否可解释？
- 一致性判定器和数据库、业务服务、单元测试分别是什么关系？
- 重复请求、乱序消息、迟到回调、宕机恢复和人工修复会破坏哪些不变量？
- 后续接入 MySQL、Spring Boot、Kafka 或 Temporal 时，哪些验证思想可以复用？

## 背景

已有阶段已经形成完整文档路线：

- `01-transfer`：从内部转账讲清账户、冻结、流水、账本、幂等和对账。
- `02-payment-recharge-withdraw`：引入外部支付渠道、充值提现、退款、回调和渠道对账。
- `03-order-payment-inventory`：扩展到订单、支付、库存、取消、退款和消息一致性。
- `04-travel-booking-saga`：覆盖机票、酒店、保险、用车等长流程 Saga。
- `05-patterns`：整理 Outbox、Saga、TCC、Temporal、CDC、对账和修复模式。
- `06-verification-lab`：定义验证模型、不变量、属性测试、故障注入和历史回放。
- `07-reconciliation-repair`：定义对账、差错分类、人工修复和审计闭环。
- `08-interview-synthesis`：把所有内容整理成面试和架构评审表达。

`06-verification-lab/07-code-lab-roadmap.md` 已经明确下一步应从纯模型开始，不先绑定基础设施。本阶段就是把这个路线图变成可以运行的代码实验室。

## 范围

第一版覆盖：

- 纯 Java 内存模型：`Command`、`Event`、`Fact`、`History`、`BusinessState`、`InvariantViolation`。
- 一致性判定器：账本、状态机、外部事实、传播、人工修复五类检查器。
- 异常历史生成器：转账、支付、订单、旅行预订四类业务场景。
- Runner：历史回放、故障注入和属性风格实验入口。
- 报告输出：失败历史、违反的不变量、相关事实、可重放 seed 或案例编号。
- 学习文档：如何运行实验、如何读失败报告、如何把实验映射回真实系统。

## 非目标

第一版不做这些事情：

- 不接入 MySQL、PostgreSQL、Oracle Database 或其他真实数据库。
- 不引入 Spring Boot、Kafka、Temporal、Redis、Testcontainers 或真实外部渠道。
- 不实现生产级转账、支付、订单或旅行预订服务。
- 不把一致性判定器复用生产业务代码。
- 不宣称测试能证明系统覆盖所有可能历史。
- 不把实验室替代生产对账、监控、审计、风控或人工复核。

MySQL 会放到后续阶段。它适合作为真实事实存储和本地事务实验对象，但不能替代一致性判定器。

## 命名约定

为了避免和 Oracle 数据库混淆，中文文档统一使用：

- 一致性判定器
- 不变量检查器
- 验证器

英文代码优先使用：

- `ConsistencyVerifier`
- `InvariantChecker`
- `LedgerConsistencyVerifier`
- `StateMachineVerifier`
- `ExternalFactVerifier`

如果引用测试理论中的 oracle，只在解释概念时使用，并明确它不是 Oracle 数据库。

## 目录设计

新增目录：

```text
financial-consistency/09-code-lab/
```

建议结构：

```text
financial-consistency/09-code-lab/
  README.md
  docs/
    01-running-the-lab.md
    02-reading-failure-reports.md
    03-mapping-to-real-systems.md
  src/
    main/java/.../model/
      Command.java
      Event.java
      Fact.java
      History.java
      BusinessState.java
      InvariantViolation.java
    main/java/.../verifier/
      ConsistencyVerifier.java
      LedgerConsistencyVerifier.java
      StateMachineVerifier.java
      ExternalFactVerifier.java
      PropagationVerifier.java
      ManualRepairVerifier.java
    main/java/.../generator/
      TransferHistoryGenerator.java
      PaymentHistoryGenerator.java
      OrderHistoryGenerator.java
      TravelHistoryGenerator.java
    main/java/.../runner/
      HistoryReplayRunner.java
      FaultInjectionRunner.java
      PropertyStyleRunner.java
    main/java/.../report/
      FailureReport.java
      FailureReporter.java
    main/java/.../scenario/
      transfer/
      payment/
      order/
      travel/
```

如果当前仓库没有 Java 构建骨架，计划阶段再决定是创建独立 Gradle 模块，还是先用已有工程结构承载。设计层面只要求第 09 章能独立运行，且不依赖真实基础设施。

## 核心模型

### Command

`Command` 表达业务意图，例如：

- `CreateTransfer`
- `RetryTransfer`
- `CapturePayment`
- `CancelOrder`
- `BookFlight`
- `CancelHotel`
- `SubmitManualRepair`

Command 可以重复、乱序或迟到。实验室不假设外部调用天然可靠。

### Event

`Event` 表达系统发布或接收的变化通知，例如：

- `TransferCreated`
- `PaymentTimeout`
- `PaymentCallbackReceived`
- `InventoryReserved`
- `OutboxMessagePublished`
- `SupplierBookingSucceeded`

Event 不等于事实本身。事件可能重复投递、延迟投递、丢失后重放，验证时必须看最终事实是否仍然可解释。

### Fact

`Fact` 表达已经发生、可审计、不能随意删除的事实，例如：

- 账本分录
- 幂等记录
- 渠道流水
- 供应商订单号
- Outbox 记录
- 消费者处理记录
- 人工审批
- 修复分录

实验室的核心判断是：一段 history 结束后，所有 fact 是否互相解释得通。

### History

`History` 是 Command、Event、Fact、Fault 和人工动作组成的序列。验证器读取 History，不调用业务服务。

History 必须支持：

- 重复命令
- 重复消息
- 乱序回调
- 迟到成功
- 迟到失败
- 事务提交后崩溃
- 发布后未标记 sent
- 消费者副作用成功但处理记录失败
- 人工修复和自动补偿交错

### InvariantViolation

`InvariantViolation` 是实验室最重要的输出。它至少包含：

- 被破坏的不变量编号或名称。
- 违反原因。
- 相关 Command、Event、Fact。
- 最小或缩减后的失败 History。
- 可重放 seed、案例编号或固定输入名称。
- 建议排查边界，例如幂等、账本、状态机、外部事实、传播或人工修复。

## 一致性判定器设计

一致性判定器必须独立于生产业务逻辑。它只读取 History 和 Fact，不能调用生产服务，也不能复用生产状态迁移代码。

### LedgerConsistencyVerifier

检查资金事实：

- 同一业务效果不能重复入账。
- 借贷分录必须平衡。
- 冻结、解冻、扣减、入账必须能形成可解释链路。
- 冲正和调整必须追加新事实，不能删除旧事实。
- 人工修复后的账本差异必须被审批、修复命令和复核结果解释。

### StateMachineVerifier

检查状态事实：

- 同一实体不能出现互斥终态。
- 成功事实不能被迟到失败覆盖。
- unknown 不能被本地直接判定为失败。
- TCC Confirm 和 Cancel 不能同时成功。
- Saga 步骤的补偿不能越过不可逆事实。

### ExternalFactVerifier

检查外部事实：

- 本地支付状态必须能被渠道流水、回调或主动查询解释。
- 本地退款状态必须能被退款渠道事实解释。
- 旅行供应商成功、失败、未知、已出票、已入住、保险已生效等事实不能被本地随意改写。
- 外部成功但本地失败时，必须进入补偿、对账、人工处理或挂起，而不是静默丢弃。

### PropagationVerifier

检查传播事实：

- 本地事务提交后的 Outbox 记录必须最终被发布或被标记为待处理。
- 消息重复投递不能重复业务效果。
- 消费者副作用成功后，即使处理记录写入失败，重试也不能重复副作用。
- CDC offset 回退不能导致读模型倒退或重复触发外部动作。

### ManualRepairVerifier

检查人工修复事实：

- 修复必须有差错来源、审批、修复命令、修复结果和复核结果。
- 同一差错不能被重复修复。
- 人工修复不能删除历史事实。
- 自动补偿和人工修复交错时，最终状态必须可解释。

## 生成器设计

生成器只负责制造异常历史，不负责判断通过或失败。

### TransferHistoryGenerator

覆盖：

- 转账请求重复提交。
- 幂等记录成功但账本分录部分缺失。
- 扣款成功、入账失败。
- 冻结成功、扣减失败。
- 调整分录重复执行。
- 修复命令重复提交。

期望暴露：

- 幂等边界不完整。
- 借贷不平。
- 账户余额和账本事实不一致。
- 修复缺少审批或复核。

### PaymentHistoryGenerator

覆盖：

- 支付请求超时。
- 本地判失败后迟到成功回调。
- 成功回调重复到达。
- 主动查询和回调结果冲突。
- 退款请求成功但响应丢失。
- 渠道账单和本地流水不一致。

期望暴露：

- 外部 unknown 被本地过早裁决。
- 成功事实被迟到失败覆盖。
- 重复回调重复入账。
- 渠道事实无法解释本地事实。

### OrderHistoryGenerator

覆盖：

- 订单创建成功、支付成功、库存预留失败。
- 库存成功、支付失败。
- 取消订单和支付成功回调竞争。
- 发货后退款。
- 消息重复导致重复发货或重复退款。
- 售后修复和自动补偿交错。

期望暴露：

- 订单、支付、库存状态互相不可解释。
- 已发货事实被错误补偿。
- 重复消息造成重复业务效果。
- 退款和取消缺少闭环。

### TravelHistoryGenerator

覆盖：

- 机票成功、酒店失败。
- 酒店成功、机票失败。
- 保险已生效后主流程失败。
- 供应商成功但回调迟到。
- 供应商 unknown 被本地直接取消。
- 取消补偿失败。
- 人工补差或改签后自动任务继续执行。

期望暴露：

- 不可逆事实被错误补偿。
- 核心项和附加项策略混乱。
- 供应商事实、本地订单和支付事实不一致。
- 人工处理缺少证据链。

## Runner 设计

### HistoryReplayRunner

读取固定 History，按原始顺序或变体顺序回放给一致性判定器。

第一批回放模式：

- 原始顺序。
- 回调先到、命令后到。
- 成功先到、失败迟到。
- 消息重复。
- 人工修复和自动补偿交错。

### FaultInjectionRunner

在 History 中插入故障事实，例如：

- 本地事务提交前失败。
- 本地事务提交后、Outbox 标记 sent 前失败。
- broker 重复投递。
- 消费者副作用成功后、处理记录写入前失败。
- 渠道请求成功但响应超时。
- 供应商成功回调迟到。

它不模拟真实基础设施，只模拟一致性验证所需的事实后果。

### PropertyStyleRunner

按 seed 生成多组异常 History，并输出失败案例。第一版可以自实现简单随机和案例缩减，不强制引入 jqwik。

报告必须至少显示：

- seed 或案例编号。
- 使用的 generator。
- 触发的 verifier。
- 最小或缩减后的失败 History。
- `InvariantViolation` 列表。

## 第一批实验

第一版至少提供八个可运行实验：

1. 内部转账重复请求，验证幂等键不能产生重复账本效果。
2. 内部转账扣款成功但入账缺失，验证借贷不平会被发现。
3. 支付超时后迟到成功回调，验证本地失败状态不可直接覆盖外部成功事实。
4. Outbox 发布后崩溃，验证业务事实和传播事实必须最终可解释。
5. 消费者重复消息，验证重复投递不能产生重复业务效果。
6. TCC Cancel 先于 Try 或 Confirm/Cancel 竞争，验证互斥终态。
7. 旅行组合预订机票成功但酒店失败，验证不可逆供应商事实和补偿路径。
8. 人工修复重复提交，验证审批、修复分录和复核事实链路。

这些实验要同时覆盖正常历史和失败历史。正常历史用于展示不变量如何被满足，失败历史用于展示判定器如何解释问题。

## 报告设计

报告面向学习者和架构评审，而不是只面向测试框架。

示例结构：

```text
Experiment: payment-timeout-late-success
Scenario: payment
Seed: 2026050201
Result: FAILED

Violated invariant:
  External success cannot be overwritten by local timeout failure.

Relevant facts:
  - PaymentCommandSubmitted(paymentId=P1)
  - LocalPaymentMarkedFailed(reason=TIMEOUT)
  - ChannelCallbackSucceeded(channelTxn=C1)

Reduced history:
  1. CapturePayment(P1)
  2. ChannelRequestTimedOut(P1)
  3. LocalPaymentMarkedFailed(P1)
  4. ChannelCallbackSucceeded(P1)

Verifier:
  ExternalFactVerifier

Interpretation:
  The local system treated an unknown external result as final failure,
  then received a successful external fact. The correct boundary is
  PAYMENT_UNKNOWN plus query, reconciliation, compensation, or manual handling.
```

报告语言要坚持边界：它说明在当前 History 和当前不变量范围内发现了不可解释事实，不宣称证明系统覆盖所有可能异常。

## 学习顺序

第 09 章建议按以下顺序呈现：

1. 先运行一个正常转账 History，观察没有 violation。
2. 再运行重复转账失败案例，看到幂等 violation。
3. 增加账本判定器，看到借贷不平 violation。
4. 增加支付迟到成功案例，理解外部 unknown。
5. 增加 Outbox 和消费者案例，理解传播一致性。
6. 增加 TCC 和旅行案例，理解长事务和不可逆动作。
7. 增加人工修复案例，理解对账、审批、修复和复核。
8. 最后总结如何迁移到 MySQL、Spring Boot、Kafka 和 Temporal。

## 后续迁移到真实工程

第 09 章完成后，后续阶段可以把同一套验证思想迁移到真实基础设施：

- MySQL：验证本地事务、唯一约束、幂等表、账本表、Outbox 表、隔离级别和锁。
- Spring Boot：实现服务边界、事务边界、adapter 和应用层幂等。
- Kafka：验证消息发布、重复投递、消费者幂等和 offset 回退。
- Temporal：验证 workflow history、activity 重试、外部副作用幂等和补偿流程。
- Testcontainers：把真实 MySQL、Kafka 和其他组件纳入可重复测试环境。

迁移时必须保留一个原则：真实系统负责产生事实，一致性判定器负责独立检查事实。二者不能混成同一套业务逻辑。

## 成功标准

第 09 章完成时应满足：

- 有可运行入口，学习者能在本地执行实验。
- 至少八个实验能稳定运行。
- 每个失败实验都输出结构化 `InvariantViolation`。
- 报告能展示最小或缩减后的失败 History。
- 代码不依赖真实数据库、消息队列、工作流引擎或外部渠道。
- 文档能解释 `ConsistencyVerifier` 不是 Oracle 数据库。
- 文档能说明为什么第 10 章才引入 MySQL 和真实服务。

## 风险与约束

| 风险 | 后果 | 约束 |
| --- | --- | --- |
| 过早接入 MySQL、Kafka 或 Temporal | 学习重点变成环境搭建 | 第 09 章只做纯 Java 内存验证 |
| 判定器复用业务代码 | 生产 bug 和测试 bug 同源 | 判定器只读 History 和 Fact |
| 只写 happy path | 无法暴露一致性问题 | 每个场景必须有失败历史 |
| 报告只打印 assertion failed | 学习者无法定位事务边界 | 必须输出 violation、相关事实和 reduced history |
| 把测试说成绝对证明 | 误导安全边界 | 始终使用覆盖范围内的验证语言 |
| `Oracle` 命名引起误解 | 学习者误以为需要 Oracle 数据库 | 中文统一叫一致性判定器，英文优先用 verifier |

## 输出结论

第 09 章应先实现纯 Java 内存版代码实验室。它不是生产服务，也不是数据库教程，而是一个能把金融一致性问题显性化的验证工具。

它的核心产物不是一组绿色测试，而是可解释的失败报告：哪段 History 违反了哪条不变量，哪些 Fact 互相解释不通，应该把问题定位到幂等、账本、状态机、外部事实、传播还是人工修复边界。

只有当这套模型、判定器、生成器和 runner 能清楚解释失败后，再进入 MySQL、Spring Boot、Kafka、Temporal 和 Testcontainers 阶段。
