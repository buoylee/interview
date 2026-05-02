# 06 验证实验室设计

日期：2026-05-02

## 目标

创建 `financial-consistency/06-verification-lab/`，把前面阶段反复提到的金融级验证方法整理成一个可落地的实验室规格。

这一阶段先不写 Java 实现。它的目标是把后续可运行实验室需要的测试模型、异常历史、断言方式和场景矩阵定义清楚，让学习者知道金融一致性问题应该如何被科学验证，而不是只靠正常路径测试或人工推理。

完成后，学习者应该能回答：

- 要验证金融级一致性，系统里哪些东西必须被建模？
- 不变量、oracle、属性测试、故障注入、历史回放分别解决什么问题？
- 转账、充值提现、电商下单、旅行组合预订各自应该生成哪些异常历史？
- 什么时候测试只能降低风险，不能证明系统绝对正确？
- 后续如果进入 Java 实现，测试工程应该如何组织？

## 背景

已有阶段已经覆盖业务和模式：

- `01-transfer`：内部转账，需要账户、冻结、流水、账本、幂等和对账。
- `02-payment-recharge-withdraw`：外部渠道接入，需要处理超时、回调、查询、退款和渠道对账。
- `03-order-payment-inventory`：订单、支付、库存、取消和退款，需要库存预留、消息重复和退款闭环。
- `04-travel-booking-saga`：旅行组合预订，需要长流程 Saga、供应商未知、不可逆动作和人工处理。
- `05-patterns/09-verification.md`：已经总结了验证方法的概念边界。

`06-verification-lab` 的作用是从“概念说明”前进到“实验室规格”：把验证对象、输入历史、状态演化和失败判定统一起来，为后续代码实现打基础。

## 范围

第一版覆盖：

- 验证模型：命令、事件、事实、历史、不变量、oracle。
- 不变量目录：幂等、状态机、账本、外部未知、补偿、Outbox、消费者、人工修复。
- 属性测试设计：如何随机生成重复、乱序、迟到、超时、宕机恢复和人工修复。
- 故障注入设计：注入点、期望恢复路径和失败判定。
- 历史回放设计：如何重放真实或构造历史，检查状态机和账本事实。
- 场景实验矩阵：转账、充值提现、电商下单、旅行组合预订分别怎么测。
- 代码实验室路线图：后续 Java 测试工程应该如何分层。
- 面试和架构评审表达。

## 非目标

第一版不做这些事情：

- 不创建 Java、Go 或其他可运行测试工程。
- 不引入 JUnit、jqwik、Testcontainers、Temporal SDK、Kafka 或数据库依赖。
- 不实现真实服务、真实 broker、真实数据库或真实工作流引擎。
- 不宣称测试可以证明所有异常历史绝对安全。
- 不把验证实验室替代生产对账、监控、审计或人工复核。
- 不重新讲解 Outbox、Saga、TCC、Temporal、CDC 的定义，除非它们影响验证方法。

## 目录设计

新增目录：

```text
financial-consistency/06-verification-lab/
```

新增文件：

```text
README.md
01-verification-model.md
02-invariant-catalog.md
03-property-testing.md
04-fault-injection.md
05-history-replay.md
06-scenario-lab-matrix.md
07-code-lab-roadmap.md
08-interview-synthesis.md
```

文件职责：

- `README.md`：阶段目标、学习顺序、实验室边界。
- `01-verification-model.md`：统一命令、事件、事实、历史、不变量和 oracle 的含义。
- `02-invariant-catalog.md`：金融一致性不变量目录。
- `03-property-testing.md`：属性测试如何生成异常历史并检查不变量。
- `04-fault-injection.md`：故障注入点、恢复路径和失败判定。
- `05-history-replay.md`：历史回放、乱序回放、重复回放和迟到事实验证。
- `06-scenario-lab-matrix.md`：四类业务场景的实验矩阵。
- `07-code-lab-roadmap.md`：后续 Java 可运行实验室的工程路线图。
- `08-interview-synthesis.md`：验证实验室的面试和架构评审表达。

## 核心模型

### 命令、事件、事实、历史

实验室需要把业务系统拆成四类可验证对象：

| 对象 | 含义 | 示例 |
| --- | --- | --- |
| Command | 外部或内部发起的意图 | `CreateTransfer`、`CapturePayment`、`CancelBooking` |
| Event | 系统发布或接收的变化通知 | `PaymentCaptured`、`SupplierCallbackReceived` |
| Fact | 已经落库、可审计、不能随意删除的事实 | 账本分录、渠道流水、供应商订单、人工审批 |
| History | 命令、事件、事实、故障和人工动作组成的时序 | 重复扣款请求后迟到成功回调 |

验证不是检查某个函数返回成功，而是检查一段 history 结束后，所有 fact 是否可解释。

### 不变量

不变量是系统永远不能违反的承诺。它们应该独立于具体实现框架存在。

示例：

- 同一业务幂等键最多产生一个业务效果。
- 借贷分录必须平衡。
- 已 capture 的资金不能 void。
- `PAYMENT_UNKNOWN`、`REFUND_UNKNOWN`、`SUPPLIER_UNKNOWN` 不能被本地直接判失败。
- TCC 的 Confirm 和 Cancel 不能同时成功。
- 补偿必须追加新事实，不能删除历史事实。
- workflow history、broker offset、接口返回和日志不能替代账本分录。

### Oracle

Oracle 是判断一段 history 是否合格的检查器。

第一版文档要把 oracle 分成三类：

- 状态机 oracle：检查状态迁移是否合法。
- 资金 oracle：检查余额、冻结、流水和账本分录是否可解释。
- 外部事实 oracle：检查支付渠道、退款渠道、供应商和人工修复事实是否和本地事实能互相解释。

Oracle 不代表生产系统里的单个服务。它是测试视角的判定模型，用来帮助学习者知道应该断言什么。

## 属性测试设计

属性测试文档必须讲清：重点不是随机数据本身，而是随机生成异常历史。

生成器需要覆盖：

- 命令重复。
- 消息重复。
- 回调乱序。
- 迟到成功和迟到失败。
- 外部请求超时。
- 本地事务提交后进程宕机。
- Outbox publisher 崩溃。
- 消费者处理一半宕机。
- TCC Cancel 先于 Try。
- TCC Confirm 和 Cancel 并发。
- Temporal Activity 重试。
- CDC 重复捕获、乱序投影和 schema 变化。
- 人工修复命令重复提交。
- 对账批次重复执行。

每类生成器都必须说明：

1. 生成什么输入。
2. 会制造什么风险。
3. 应该用哪个不变量检查。
4. 失败时说明系统哪条一致性边界没有守住。

## 故障注入设计

故障注入文档必须按注入点组织，而不是按工具组织。

关键注入点：

- 本地事务提交前失败。
- 本地事务提交后、Outbox 标记 sent 前失败。
- broker 暂停、延迟、重复投递。
- 消费者完成外部副作用后、写处理记录前失败。
- Activity 外部副作用已成功，但 completion/result 尚未写入 workflow history。
- 渠道请求成功但响应超时。
- 供应商成功回调迟到。
- 对账任务处理中断后重跑。
- 人工审批通过后修复命令重复执行。

每个注入点必须写清：

- 故障前已经有哪些事实。
- 故障后允许重试什么。
- 故障后绝对不能重复什么。
- 最终应该进入成功、失败、unknown、长期对账或人工挂起中的哪类终态。

## 历史回放设计

历史回放文档要说明如何用同一批事实构造不同顺序：

- 原始顺序。
- 回调先到、命令后到。
- 成功先到、失败迟到。
- 消息重复。
- CDC offset 回退。
- 人工修复和自动补偿交错。
- 对账差错修复后重新对账。

回放检查重点：

- 状态机不能倒退。
- 成功事实不能被迟到失败覆盖。
- 资金事实必须能解释。
- 外部未知不能被本地直接裁决。
- 人工修复必须有证据、审批、修复命令和复核结果。

## 场景实验矩阵

`06-scenario-lab-matrix.md` 必须把实验映射回四类业务：

| 场景 | 重点验证 |
| --- | --- |
| 内部转账 | 幂等、冻结、扣减、入账、account movement、ledger posting、冲正/调整 |
| 充值提现 | 渠道超时、重复回调、主动查询、渠道账单、本地 unknown、退款和对账 |
| 电商下单 | 库存预留、支付成功后取消、重复消息、退款、发货和售后 |
| 旅行组合预订 | 核心项和附加项、供应商未知、已出票、已生效保险、付款策略、罚金、补差、人工处理 |

每个场景都要给出：

- 事实来源。
- 关键不变量。
- 异常历史样例。
- 故障注入点。
- 历史回放样例。
- 不合格判定。

## 代码实验室路线图

`07-code-lab-roadmap.md` 只描述后续实现路线，不直接实现。

推荐未来 Java 结构：

```text
verification-lab/
  model/
    Command
    Event
    Fact
    History
    State
  oracle/
    StateMachineOracle
    LedgerOracle
    ExternalFactOracle
  generator/
    TransferHistoryGenerator
    PaymentHistoryGenerator
    OrderHistoryGenerator
    TravelHistoryGenerator
  runner/
    PropertyTestRunner
    FaultInjectionRunner
    HistoryReplayRunner
  scenarios/
    transfer/
    payment/
    order/
    travel/
```

未来技术选型可在实现阶段再确认。候选方向：

- JUnit 5：基础测试框架。
- jqwik：Java 属性测试。
- Testcontainers：后续接入真实数据库、Kafka 或 Temporal test server 时使用。
- Spring Boot test slice：后续验证服务边界时使用。

第一版文档只写路线图，不查 API、不绑定版本、不引入依赖。

## 验证边界

必须避免过度表述：

- 不能说“属性测试证明系统正确”。
- 只能说“在生成器覆盖的异常历史范围内，检查不变量是否被破坏”。
- 不能说“故障注入覆盖所有生产故障”。
- 只能说“优先覆盖最容易产生不可解释事实的故障点”。
- 不能说“历史回放可以替代对账”。
- 只能说“历史回放帮助验证系统如何解释已有事实和迟到事实”。

## 完成标准

这一阶段完成时必须满足：

- `06-verification-lab/` 下 9 个文档全部存在。
- 每个文档都说明验证对象、危险误用和输出结论。
- 至少覆盖内部转账、充值提现、电商下单、旅行组合预订四类场景。
- 明确区分文档实验室和后续可运行 Java 实验室。
- 明确说明测试降低风险但不证明所有历史绝对安全。
- 根 `financial-consistency/README.md` 链接到 `06-verification-lab/README.md`。
- 不修改 `01` 到 `05` 已完成阶段的内容，除非只是总 README 增加链接。

## 后续阶段关系

`06-verification-lab` 会给 `07-reconciliation` 提供验证语言：

- 对账差异可以作为 history replay 的输入。
- 修复命令必须满足不变量。
- 人工修复必须能被 oracle 解释。
- 重新对账是验证闭环的一部分。

`08-interview-synthesis` 会吸收 `06` 的表达：

- 金融级系统不是只问“用了什么框架”，还要问“怎么验证异常历史不会产生不可解释事实”。
- 高级回答必须包含不变量、异常历史、故障注入、历史回放、对账和人工复核。
