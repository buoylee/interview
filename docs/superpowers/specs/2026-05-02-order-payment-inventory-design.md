# 03 订单、支付、库存与退款一致性设计

日期：2026-05-02

## 目标

创建 `financial-consistency/03-order-payment-inventory/`，把学习主线从外部支付渠道推进到电商交易闭环。

这个阶段的核心不是“下单后扣库存”这么简单，而是理解订单、库存、支付、取消、退款、Outbox 和对账之间的并发关系。学习者完成后应该能解释：

- 为什么库存必须先预留，再确认或释放。
- 为什么支付成功不能被普通取消直接覆盖。
- 为什么取消请求和支付回调并发时必须靠状态机裁决。
- 为什么已支付订单取消后进入退款流程，而不是简单回滚订单。
- 为什么退款金额不能超过原支付金额。
- 为什么订单、支付单、库存流水、退款单、会计分录和事件必须能对账。

## 背景

`01-transfer` 建立了内部资金事实的基础：

- 账户、余额、冻结、流水和会计分录。
- 幂等、状态机、Outbox、补偿和对账。
- 不变量、故障注入、历史检查和对账验证。

`02-payment-recharge-withdraw` 引入了外部渠道：

- 外部渠道不参与本地事务。
- 超时不是失败。
- 回调需要验签、幂等和状态机推进。
- 渠道账单和本地资金事实必须能对账。

`03-order-payment-inventory` 在此基础上新增业务资源：库存。库存不是资金，但它和订单、支付、退款共同决定履约结果。真实系统最危险的问题通常发生在并发边界：

- 订单取消和支付成功回调同时到达。
- 库存已释放后又收到支付成功。
- 支付成功后库存确认失败。
- 退款成功但本地订单或分录未推进。
- 重复消息导致库存重复确认、重复释放或重复退款。

## 范围

第一版采用方案 A：订单、库存预留、支付、取消、退款和对账的最小真实闭环。

覆盖 6 个核心场景：

1. 下单并预留库存。
2. 支付成功后确认订单和库存。
3. 支付失败、超时或未知状态。
4. 订单取消与支付回调并发。
5. 已支付订单取消和退款。
6. 订单、支付、库存、退款对账。

这个阶段构成的闭环是：

```text
创建订单
-> 预留库存
-> 发起支付
-> 支付回调或查询补偿
-> 确认库存或释放库存
-> 必要时发起退款
-> 订单/支付/库存/退款/账本事件
-> 对账与差错修复
```

## 非目标

第一版不覆盖：

- 优惠券、积分、余额组合支付。
- 购物车促销计算和复杂价格引擎。
- 物流发货、签收、退货入库。
- 商户分账、佣金、平台补贴和日终结算。
- 预售、秒杀、跨仓调拨和复杂库存分配。
- 真实支付渠道 SDK、真实库存中间件或真实仓储系统集成。

这些场景保留在后续扩展中。第一版先把“订单、支付、库存、取消、退款”这条主链路讲清楚。

## 目录设计

新增目录：

```text
financial-consistency/03-order-payment-inventory/
```

新增文件：

```text
README.md
01-scenario-cards.md
02-invariants.md
03-state-machine.md
04-service-boundaries.md
05-event-flow.md
06-failure-matrix.md
07-reconciliation.md
08-verification-plan.md
09-interview-synthesis.md
```

文件职责：

- `README.md`：模块入口、学习目标、学习顺序和核心问题。
- `01-scenario-cards.md`：6 个电商交易场景卡。
- `02-invariants.md`：订单、库存、支付和退款必须满足的不变量。
- `03-state-machine.md`：订单、库存预留、支付单、退款单和差错单状态机。
- `04-service-boundaries.md`：order、inventory、payment、refund、ledger、reconciliation 的职责边界。
- `05-event-flow.md`：命令、事实事件、Outbox 发布和消费依赖。
- `06-failure-matrix.md`：取消/支付并发、库存确认失败、退款未知、重复消息等恢复路径。
- `07-reconciliation.md`：订单、支付、库存流水、退款单、会计分录和事件如何对账。
- `08-verification-plan.md`：模型验证、属性测试、集成测试、故障注入、历史检查和对账验证。
- `09-interview-synthesis.md`：面试和架构评审表达。

## 场景卡

第一版必须包含 6 张场景卡。

### 下单并预留库存

场景边界：

- 用户提交订单。
- `order-service` 创建订单。
- `inventory-service` 按订单明细预留库存。
- 预留成功后订单进入待支付状态。

核心风险：

- 库存预留重复。
- 库存不足但订单进入可支付状态。
- 订单创建成功但库存预留失败。
- 订单取消后库存未释放。

### 支付成功后确认订单和库存

场景边界：

- 用户完成支付。
- `payment-service` 接收可信支付成功事实。
- `order-service` 将订单推进到已支付。
- `inventory-service` 将库存预留确认成已占用或已售出。
- `ledger-service` 追加支付相关分录。

核心风险：

- 支付成功但订单仍待支付。
- 支付成功但库存未确认。
- 库存确认失败导致已支付订单无法履约。
- 支付成功事件重复导致库存重复确认。

### 支付失败、超时或未知状态

场景边界：

- 支付请求提交后返回失败、超时或未知。
- 失败事实可信时订单可回到可重试或取消路径。
- 未知状态必须查询、等待回调或对账，不得直接释放库存或取消订单。

核心风险：

- 把支付超时当失败并释放库存。
- 支付未知状态下重复提交新支付动作。
- 支付失败晚于支付成功事实，覆盖已支付终态。
- 长时间未知导致库存长期悬挂。

### 订单取消与支付回调并发

场景边界：

- 用户或系统发起取消。
- 支付成功、失败或未知回调可能同时到达。
- 状态机必须决定订单进入取消、已支付、退款中或人工处理。

核心风险：

- 取消成功后又收到支付成功。
- 支付成功后库存已释放。
- 取消和支付同时推进导致订单终态冲突。
- 重复取消导致库存重复释放。

### 已支付订单取消和退款

场景边界：

- 已支付但未履约订单被取消。
- 订单不能直接回滚为未支付。
- 系统创建退款单，调用支付渠道退款。
- 退款成功后订单进入已退款或已关闭状态，并追加退款分录。

核心风险：

- 重复退款。
- 退款金额超过原支付金额。
- 退款成功但订单状态未推进。
- 退款未知状态下重复提交外部退款请求。

### 订单、支付、库存、退款对账

场景边界：

- 对比订单、支付单、库存流水、退款单、会计分录、Outbox 和渠道账单。
- 识别支付成功订单未确认库存、订单取消库存未释放、退款成功本地未关闭等差错。
- 每个差错必须有 owner、状态、修复动作和审计记录。

核心风险：

- 只对账订单状态，不对账库存流水和退款单。
- 差错修复直接改库存或订单历史。
- 发现差异但没有 owner 和修复状态。

## 服务边界

第一版采用这些逻辑服务：

- `order-service`：订单、订单状态机、取消请求、订单幂等键。
- `inventory-service`：库存可售量、库存预留、预留确认、预留释放、库存流水。
- `payment-service`：支付单、支付回调、支付查询、支付渠道事实。
- `refund-service`：退款单、退款提交、退款回调、退款查询和退款状态机。
- `ledger-service`：支付、退款、冲正和差错修复分录。
- `reconciliation-service`：订单/支付/库存/退款/账本对账、差错分类、修复工单。
- `message-broker`：Outbox 事件投递和异步消费，不代表业务事实本身。

关键边界：

- `order-service` 不直接扣减库存，也不直接确认支付渠道事实。
- `inventory-service` 不决定订单是否支付成功，只根据订单命令确认或释放预留。
- `payment-service` 不决定库存是否确认，只提供支付事实。
- `refund-service` 不直接改订单历史，只提供退款事实并触发订单状态推进。
- `ledger-service` 不覆盖历史分录，只追加支付、退款或冲正分录。
- `reconciliation-service` 不直接修订单、库存或资金，只创建差错和修复命令。

## 正确性不变量

第一版至少定义这些不变量：

- 库存可售量不能为负。
- 同一订单明细只能预留一次库存。
- 同一库存预留只能确认一次或释放一次。
- 订单取消成功必须释放未确认库存。
- 支付成功订单不能被普通取消直接覆盖。
- 支付成功但订单已经取消时，必须进入退款或人工处理路径。
- 已支付订单取消必须创建退款单。
- 同一支付单只能产生一次订单支付效果。
- 同一退款单只能产生一次退款业务效果。
- 累计退款金额不能超过原支付金额。
- 退款成功必须有退款渠道事实、退款单终态和会计分录。
- broker offset 不能证明订单、库存、支付或退款完成。
- 对账差异必须有分类、owner、状态、修复动作和审计记录。

## 状态模型

### 订单状态

核心状态：

```text
CREATED
-> STOCK_RESERVED
-> PENDING_PAYMENT
-> PAID
-> STOCK_CONFIRMED
-> FULFILLABLE
```

取消和退款状态：

```text
CANCEL_REQUESTED
-> CANCELLED
-> REFUND_REQUIRED
-> REFUNDING
-> REFUNDED
-> CLOSED
```

异常和人工状态：

```text
PAYMENT_UNKNOWN
STOCK_CONFIRM_FAILED
RECONCILIATION_REQUIRED
MANUAL_REVIEW
```

关键规则：

- `PENDING_PAYMENT` 可以取消并释放库存。
- `PAID` 不能直接取消为 `CANCELLED`，必须走退款或履约路径。
- `PAYMENT_UNKNOWN` 不能直接释放库存，必须查询、等待回调、对账或人工处理。
- `STOCK_CONFIRMED` 后取消需要检查是否已经履约；第一版不覆盖发货后退货。

### 库存预留状态

```text
RESERVED
-> CONFIRMED
```

或：

```text
RESERVED
-> RELEASED
```

异常状态：

```text
RESERVE_FAILED
CONFIRM_FAILED
RELEASE_FAILED
MANUAL_REVIEW
```

关键规则：

- `CONFIRMED` 和 `RELEASED` 是互斥终态。
- `RELEASED` 之后不能确认库存。
- 重复确认或重复释放必须幂等返回既有结果。

### 支付单状态

沿用 `02-payment-recharge-withdraw` 的外部渠道原则：

```text
CREATED
-> CHANNEL_PENDING
-> CHANNEL_UNKNOWN
-> CHANNEL_SUCCEEDED
-> APPLIED_TO_ORDER
-> SUCCEEDED
```

失败和人工状态：

```text
CHANNEL_FAILED
FAILED
RECONCILIATION_REQUIRED
MANUAL_REVIEW
```

### 退款单状态

```text
CREATED
-> REFUND_SUBMITTED
-> REFUND_UNKNOWN
-> REFUND_SUCCEEDED
-> ORDER_REFUNDED
-> LEDGER_POSTED
-> SUCCEEDED
```

失败和人工状态：

```text
REFUND_FAILED
RECONCILIATION_REQUIRED
MANUAL_REVIEW
```

关键规则：

- `REFUND_UNKNOWN` 不能重复提交外部退款。
- `REFUND_SUCCEEDED` 后必须推进订单和分录。
- `REFUND_FAILED` 不能覆盖已经确认的退款成功事实。

## 事件流

关键事件分类：

- 订单命令：`OrderCreateRequested`、`OrderCancelRequested`。
- 库存事实：`StockReserved`、`StockConfirmed`、`StockReleased`。
- 支付事实：`PaymentSucceeded`、`PaymentFailed`、`PaymentUnknown`。
- 订单事实：`OrderPaid`、`OrderCancelled`、`OrderRefundRequired`。
- 退款事实：`RefundSubmitted`、`RefundSucceeded`、`RefundFailed`、`RefundUnknown`。
- 账本事实：`PaymentLedgerPosted`、`RefundLedgerPosted`。
- 对账事实：`CommerceMismatchDetected`、`CommerceRepairRequested`。

典型成功流：

```text
OrderCreateRequested
-> OrderCreated
-> StockReserved
-> PaymentRequested
-> PaymentSucceeded
-> OrderPaid
-> StockConfirmed
-> PaymentLedgerPosted
-> OrderFulfillable
```

取消流：

```text
OrderCancelRequested
-> OrderCancelAccepted
-> StockReleased
-> OrderCancelled
```

已支付取消退款流：

```text
OrderCancelRequested
-> RefundRequired
-> RefundSubmitted
-> RefundSucceeded
-> OrderRefunded
-> RefundLedgerPosted
-> OrderClosed
```

并发裁决：

- 支付成功和取消同时到达时，以持久化状态机和版本条件更新裁决。
- 如果取消先成功且库存释放，后续支付成功必须进入退款或人工处理。
- 如果支付先成功，取消必须进入退款或履约前取消路径。
- 重复事件只允许一次业务效果。

## 失败矩阵重点

第一版至少覆盖这些失败点：

- 订单创建成功但库存预留失败。
- 库存预留成功但订单状态更新失败。
- 支付成功但订单未推进。
- 支付成功但库存确认失败。
- 支付失败回调晚于支付成功事实。
- 支付未知状态下用户取消订单。
- 取消成功但库存释放失败。
- 库存释放成功后收到支付成功。
- 退款提交超时或未知。
- 退款成功但订单未关闭。
- Outbox 发布失败。
- 消费者重复消费。
- 对账发现订单、库存、支付或退款不一致。

## 对账设计

对账输入：

- 订单表和订单状态历史。
- 支付单、支付回调、支付查询结果和渠道账单。
- 库存预留记录、库存流水、确认/释放流水。
- 退款单、退款回调、退款查询结果和渠道退款账单。
- 会计分录。
- Outbox 事件和消费记录。

差错分类：

- 支付成功，订单未支付。
- 支付成功，库存未确认。
- 订单取消，库存未释放。
- 库存释放后支付成功。
- 订单已退款，渠道退款缺失。
- 渠道退款成功，本地订单未关闭。
- 退款金额不一致。
- 库存流水缺失或重复。
- 分录缺失。
- Outbox 事件缺失或重复。
- 长时间未知状态。

修复原则：

- 不直接覆盖订单、库存、支付、退款或分录历史。
- 通过幂等修复命令、补事件、补分录、冲正、退款或人工工单处理。
- 高风险修复必须有 maker-checker 或人工复核。
- 修复后必须重新对账。

## 验证路线

模型验证：

- 订单取消、支付回调、库存确认和退款状态组合。
- `PAYMENT_UNKNOWN` 不能直接释放库存或取消成终态。
- `REFUND_UNKNOWN` 不能重复提交外部退款。
- `StockReserved` 只能确认一次或释放一次。
- 支付成功终态不能被失败回调覆盖。

属性测试：

- 随机生成订单创建、库存预留、取消、支付成功/失败/未知、退款成功/失败/未知和重复消息序列。
- 检查库存不为负。
- 检查同一订单库存确认和释放互斥。
- 检查退款金额不超过支付金额。
- 检查每个订单最终进入履约、取消、退款或人工处理。

集成测试：

- 唯一约束和幂等键。
- 本地事务和 Outbox 同提交。
- 支付回调和取消请求并发。
- 库存确认失败后的修复路径。
- 退款未知状态查询补偿。

故障注入：

- DB 写入失败。
- Outbox 发布失败。
- 消费者崩溃和重复消费。
- 支付成功后订单更新失败。
- 支付成功后库存确认失败。
- 退款提交超时。
- 对账账单缺失或金额不一致。

历史检查：

- 每个订单状态转换合法。
- 每个库存预留最终确认、释放或人工处理。
- 每个支付成功订单有明确履约或退款路径。
- 每个退款成功有订单终态和退款分录。
- 每个差错都有分类、owner、修复动作和审计记录。

## 面试和架构评审表达

这个阶段最终要能回答：

- 电商下单为什么不能直接扣库存？
- 支付成功和订单取消并发时怎么处理？
- 支付超时能不能释放库存？
- 支付成功但库存释放了怎么办？
- 退款为什么必须是独立状态机？
- 如何防止重复退款？
- 订单、支付、库存、退款如何对账？
- Temporal 在这里解决什么，不能解决什么？

标准回答结构：

1. 先说明订单、库存、支付、退款属于不同事实边界。
2. 再说明库存用预留、确认、释放，而不是直接扣减。
3. 再说明支付回调和取消请求通过状态机裁决并发。
4. 再说明已支付订单取消进入退款流程。
5. 再说明所有跨服务事实通过 Outbox 和幂等消费者传播。
6. 最后说明用模型验证、属性测试、故障注入、历史检查和对账验证正确性。

## 根 README 更新

实现阶段需要更新 `financial-consistency/README.md`：

- 在正式设计文档列表中加入本设计文档链接。
- 将 `03-order-payment-inventory` 从纯文本改成指向 `./03-order-payment-inventory/README.md` 的链接。

## 成功标准

完成 `03-order-payment-inventory` 后，学习者应该能：

- 画出订单、库存、支付、退款的状态机。
- 解释取消和支付回调并发时的合法裁决。
- 解释为什么支付未知不能直接释放库存。
- 解释为什么退款不能只是订单字段更新。
- 定义库存、支付、退款相关不变量。
- 设计能发现超卖、重复退款、库存悬挂和订单支付不一致的验证方案。
- 用面试语言说明为什么电商交易一致性需要 Saga/Temporal、Outbox、幂等、状态机和对账组合，而不是单个分布式事务框架。
