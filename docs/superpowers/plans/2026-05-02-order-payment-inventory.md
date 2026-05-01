# Order Payment Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `03-order-payment-inventory` learning module for e-commerce order, payment, inventory, cancellation, refund, reconciliation, and verification consistency.

**Architecture:** This is a documentation-only phase that follows the structure of `01-transfer` and `02-payment-recharge-withdraw`. Each file owns one concept: scenario cards, invariants, state machines, service boundaries, event flow, failure matrix, reconciliation, verification, and interview synthesis. The root README will link the new phase and its design spec.

**Tech Stack:** Markdown, Git, `rg`, `find`, `git diff --check`.

---

## File Structure

- Create directory: `financial-consistency/03-order-payment-inventory/`
- Create: `financial-consistency/03-order-payment-inventory/README.md`
- Create: `financial-consistency/03-order-payment-inventory/01-scenario-cards.md`
- Create: `financial-consistency/03-order-payment-inventory/02-invariants.md`
- Create: `financial-consistency/03-order-payment-inventory/03-state-machine.md`
- Create: `financial-consistency/03-order-payment-inventory/04-service-boundaries.md`
- Create: `financial-consistency/03-order-payment-inventory/05-event-flow.md`
- Create: `financial-consistency/03-order-payment-inventory/06-failure-matrix.md`
- Create: `financial-consistency/03-order-payment-inventory/07-reconciliation.md`
- Create: `financial-consistency/03-order-payment-inventory/08-verification-plan.md`
- Create: `financial-consistency/03-order-payment-inventory/09-interview-synthesis.md`
- Modify: `financial-consistency/README.md`

Do not modify `financial-consistency/01-transfer/**` or `financial-consistency/02-payment-recharge-withdraw/**`.

## Task 1: Create Phase README

**Files:**
- Create: `financial-consistency/03-order-payment-inventory/README.md`

- [ ] **Step 1: Create directory**

Run:

```bash
mkdir -p financial-consistency/03-order-payment-inventory
```

Expected: command succeeds.

- [ ] **Step 2: Add README content**

Use `apply_patch` to create `financial-consistency/03-order-payment-inventory/README.md`:

````markdown
# 03 订单、支付、库存与退款一致性

## 目标

这一阶段把学习主线从外部支付渠道推进到电商交易闭环。核心不是下单后简单扣库存，而是理解订单、库存、支付、取消、退款、Outbox 和对账之间的并发关系。

## 学习顺序

1. [场景卡](./01-scenario-cards.md)
2. [正确性不变量](./02-invariants.md)
3. [状态机](./03-state-machine.md)
4. [服务边界](./04-service-boundaries.md)
5. [事件流](./05-event-flow.md)
6. [失败矩阵](./06-failure-matrix.md)
7. [对账设计](./07-reconciliation.md)
8. [验证路线](./08-verification-plan.md)
9. [面试表达](./09-interview-synthesis.md)

## 核心问题

- 为什么库存必须先预留，再确认或释放？
- 为什么支付成功不能被普通取消直接覆盖？
- 为什么取消请求和支付回调并发时必须靠状态机裁决？
- 为什么已支付订单取消后进入退款流程，而不是简单回滚订单？
- 为什么退款金额不能超过原支付金额？
- 为什么订单、支付单、库存流水、退款单、会计分录和事件必须能对账？
- 为什么 broker offset 不能证明订单、库存、支付或退款完成？

## 本阶段范围

第一版覆盖 6 个核心场景：

- 下单并预留库存。
- 支付成功后确认订单和库存。
- 支付失败、超时或未知状态。
- 订单取消与支付回调并发。
- 已支付订单取消和退款。
- 订单、支付、库存、退款对账。

第一版不覆盖优惠券、积分、余额组合支付、复杂价格引擎、物流发货、退货入库、商户分账和复杂库存分配。那些内容会在后续模块或扩展场景中处理。

## 最小闭环

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

## 本阶段结论

电商交易一致性不是一个分布式事务框架能单独解决的问题。真实实现必须把库存预留、支付渠道事实、订单状态机、退款状态机、Outbox、幂等消费者、会计分录、对账和人工修复组合起来，才能保证订单最终进入履约、取消、退款或人工处理中的可解释终态。
````

- [ ] **Step 3: Verify README links**

Run:

```bash
rg -n "\./01-scenario-cards.md|\./02-invariants.md|\./03-state-machine.md|\./04-service-boundaries.md|\./05-event-flow.md|\./06-failure-matrix.md|\./07-reconciliation.md|\./08-verification-plan.md|\./09-interview-synthesis.md" financial-consistency/03-order-payment-inventory/README.md
```

Expected: output includes all 9 linked child documents.

- [ ] **Step 4: Commit**

Run:

```bash
git add financial-consistency/03-order-payment-inventory/README.md
git commit -m "docs: add order payment inventory module entry"
```

Expected: commit succeeds and includes only `financial-consistency/03-order-payment-inventory/README.md`.

## Task 2: Create Scenario Cards

**Files:**
- Create: `financial-consistency/03-order-payment-inventory/01-scenario-cards.md`

- [ ] **Step 1: Add scenario cards content**

Use `apply_patch` to create `financial-consistency/03-order-payment-inventory/01-scenario-cards.md`:

````markdown
# 01 场景卡

## 目的

本文件先定义业务边界，再讨论一致性方案。每张场景卡都回答：链路从哪里开始，成功目标是什么，哪些事实必须持久化，哪些失败最危险。

## 下单并预留库存

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 用户提交订单；系统创建订单；库存服务按订单明细预留库存；预留成功后订单进入待支付状态。 |
| 参与方 | 用户、order-service、inventory-service、message-broker。 |
| 核心状态机 | 订单：`CREATED -> STOCK_RESERVED -> PENDING_PAYMENT`；库存预留：`RESERVED`，失败进入 `RESERVE_FAILED` 或 `MANUAL_REVIEW`。 |
| 正确性不变量 | 库存可售量不能为负；同一订单明细只能预留一次库存；库存不足时订单不能进入可支付状态。 |
| 关键命令和事件 | `OrderCreateRequested`、`OrderCreated`、`StockReserveRequested`、`StockReserved`、`StockReserveFailed`。 |
| 耐久事实 | 订单、订单明细、库存预留记录、库存流水、Outbox 事件。 |
| 最危险失败点 | 订单创建成功但库存预留失败；库存预留成功但订单状态未推进；重复下单或重复预留；库存不足但订单可支付。 |
| 补偿方式 | 预留失败时订单进入创建失败或可重试状态；订单失败但库存已预留时释放预留；重复预留按订单明细幂等返回既有结果。 |
| 对账来源 | 订单、订单明细、库存预留记录、库存流水、Outbox 消费记录。 |
| 验证方式 | 库存非负属性测试、重复预留测试、订单创建失败故障注入、库存流水对账。 |

## 支付成功后确认订单和库存

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 用户完成支付；payment-service 提供可信支付成功事实；order-service 将订单推进到已支付；inventory-service 将预留库存确认；ledger-service 追加支付分录。 |
| 参与方 | 用户、order-service、payment-service、inventory-service、ledger-service、message-broker。 |
| 核心状态机 | 订单：`PENDING_PAYMENT -> PAID -> STOCK_CONFIRMED -> FULFILLABLE`；库存：`RESERVED -> CONFIRMED`。 |
| 正确性不变量 | 支付成功订单必须有支付成功事实；同一订单只能确认一次库存；`CONFIRMED` 库存不能再释放；支付成功必须最终有订单终态和会计分录。 |
| 关键命令和事件 | `PaymentSucceeded`、`OrderPaid`、`StockConfirmRequested`、`StockConfirmed`、`PaymentLedgerPosted`、`OrderFulfillable`。 |
| 耐久事实 | 支付单、支付渠道事实、订单状态历史、库存确认流水、会计分录、Outbox 事件。 |
| 最危险失败点 | 支付成功但订单未推进；支付成功但库存未确认；库存确认失败；重复支付事件导致库存重复确认。 |
| 补偿方式 | 支付成功但订单未推进时补订单状态；库存未确认时补确认或进入人工处理；库存已释放时进入退款或人工处理。 |
| 对账来源 | 订单、支付单、库存预留和确认流水、会计分录、渠道账单、Outbox 消费记录。 |
| 验证方式 | 重复支付事件测试、支付成功后库存确认故障注入、订单库存账本交叉对账。 |

## 支付失败、超时或未知状态

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 支付请求提交后返回失败、超时或未知；可信失败事实可以释放库存或允许重新支付；未知状态必须查询、等待回调或对账。 |
| 参与方 | 用户、order-service、payment-service、inventory-service、reconciliation-service、message-broker。 |
| 核心状态机 | 支付：`CHANNEL_PENDING -> CHANNEL_UNKNOWN -> CHANNEL_SUCCEEDED` 或 `CHANNEL_FAILED`；订单：`PENDING_PAYMENT -> PAYMENT_UNKNOWN`，可信失败后进入 `PAYMENT_FAILED` 或 `CANCELLED`。 |
| 正确性不变量 | 支付超时不是失败；`PAYMENT_UNKNOWN` 不能直接释放库存或取消成终态；未知状态不能重复提交新支付动作。 |
| 关键命令和事件 | `PaymentRequested`、`PaymentUnknown`、`PaymentQueryRequested`、`PaymentSucceeded`、`PaymentFailed`、`OrderPaymentUnknown`。 |
| 耐久事实 | 支付单、渠道请求号、查询结果、回调事实、订单状态历史、库存预留记录。 |
| 最危险失败点 | 把支付超时当失败并释放库存；未知状态下重复提交新支付；失败回调覆盖成功终态；库存长期悬挂。 |
| 补偿方式 | 查询补偿、等待回调、渠道账单核验、人工复核；可信失败后释放库存；可信成功后推进订单和库存确认。 |
| 对账来源 | 支付单、渠道账单、订单状态、库存预留记录、回调记录、查询记录。 |
| 验证方式 | 支付超时故障注入、未知状态重复动作测试、失败晚于成功测试、库存悬挂扫描。 |

## 订单取消与支付回调并发

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 用户或系统发起取消；支付成功、失败或未知回调可能同时到达；状态机必须裁决订单进入取消、已支付、退款中或人工处理。 |
| 参与方 | 用户、order-service、payment-service、inventory-service、refund-service、message-broker。 |
| 核心状态机 | 取消先成功：`PENDING_PAYMENT -> CANCEL_REQUESTED -> CANCELLED`；支付先成功：`PENDING_PAYMENT -> PAID -> REFUND_REQUIRED` 或 `FULFILLABLE`；冲突进入 `MANUAL_REVIEW`。 |
| 正确性不变量 | 订单终态不能互相覆盖；取消成功必须释放未确认库存；支付成功后不能普通取消，必须履约或退款；同一库存预留不能既确认又释放。 |
| 关键命令和事件 | `OrderCancelRequested`、`OrderCancelAccepted`、`StockReleased`、`OrderCancelled`、`PaymentSucceeded`、`OrderRefundRequired`。 |
| 耐久事实 | 订单状态历史、支付事实、库存释放流水、库存确认流水、退款需求记录、Outbox 事件。 |
| 最危险失败点 | 取消成功后收到支付成功；支付成功后库存已释放；取消和支付同时推进导致终态冲突；重复取消释放库存。 |
| 补偿方式 | 版本条件更新裁决并发；取消后支付成功进入退款或人工处理；支付后取消进入退款或履约前取消；重复取消幂等返回既有结果。 |
| 对账来源 | 订单状态历史、支付单、库存流水、退款单、Outbox 消费记录。 |
| 验证方式 | 并发模型验证、支付回调和取消竞态测试、重复取消测试、库存确认释放互斥属性测试。 |

## 已支付订单取消和退款

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 已支付但未履约订单被取消；系统创建退款单；退款渠道确认成功后订单进入已退款或关闭状态，并追加退款分录。 |
| 参与方 | 用户、order-service、refund-service、payment-service、ledger-service、reconciliation-service、message-broker。 |
| 核心状态机 | 订单：`PAID -> REFUND_REQUIRED -> REFUNDING -> REFUNDED -> CLOSED`；退款：`CREATED -> REFUND_SUBMITTED -> REFUND_UNKNOWN -> REFUND_SUCCEEDED -> SUCCEEDED`。 |
| 正确性不变量 | 已支付订单不能直接回滚为未支付；同一退款单只能产生一次退款业务效果；累计退款金额不能超过原支付金额；退款成功必须有渠道事实和退款分录。 |
| 关键命令和事件 | `RefundRequired`、`RefundCreated`、`RefundSubmitted`、`RefundSucceeded`、`OrderRefunded`、`RefundLedgerPosted`。 |
| 耐久事实 | 退款单、退款渠道请求号、退款渠道事实、订单状态历史、退款分录、Outbox 事件。 |
| 最危险失败点 | 重复退款；退款金额超过原支付金额；退款成功但订单未关闭；退款未知状态下重复提交外部退款。 |
| 补偿方式 | 退款请求幂等；未知退款查询补偿；退款成功本地未推进时补订单状态和分录；冲突进入人工复核。 |
| 对账来源 | 订单、支付单、退款单、退款渠道账单、会计分录、Outbox 消费记录。 |
| 验证方式 | 重复退款测试、退款金额上限属性测试、退款未知故障注入、退款账单对账。 |

## 订单、支付、库存、退款对账

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 系统对比订单、支付单、库存流水、退款单、会计分录、Outbox 和渠道账单；识别差错并生成修复路径。 |
| 参与方 | reconciliation-service、order-service、payment-service、inventory-service、refund-service、ledger-service、运营人员。 |
| 核心状态机 | `RECONCILIATION_STARTED -> MATCHED` 或 `MISMATCH_DETECTED -> REPAIR_REQUESTED -> REPAIRED -> VERIFIED`。 |
| 正确性不变量 | 差错必须有分类、owner、状态、修复动作和审计记录；修复不能直接覆盖订单、库存、支付、退款或分录历史。 |
| 关键命令和事件 | `CommerceStatementImported`、`CommerceMismatchDetected`、`CommerceRepairRequested`、`ManualRepairCompleted`。 |
| 耐久事实 | 对账批次、匹配结果、差错单、修复命令、审批记录、复核记录。 |
| 最危险失败点 | 只对账订单状态；不检查库存流水和退款单；差错修复直接改历史；发现问题没有 owner 和审计链。 |
| 补偿方式 | 补订单状态、补库存流水、补退款状态、补分录、补事件、冲正、人工复核。 |
| 对账来源 | 订单、支付单、库存流水、退款单、会计分录、Outbox 消费记录、渠道账单。 |
| 验证方式 | 构造差异账单、分类准确性测试、修复后不变量检查、审计记录检查。 |
````

- [ ] **Step 2: Verify scenario headings**

Run:

```bash
rg -n "^## 下单并预留库存|^## 支付成功后确认订单和库存|^## 支付失败、超时或未知状态|^## 订单取消与支付回调并发|^## 已支付订单取消和退款|^## 订单、支付、库存、退款对账" financial-consistency/03-order-payment-inventory/01-scenario-cards.md
```

Expected: output includes all 6 scenario headings.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/03-order-payment-inventory/01-scenario-cards.md
git commit -m "docs: add order payment inventory scenario cards"
```

Expected: commit succeeds and includes only `01-scenario-cards.md`.

## Task 3: Create Invariants Document

**Files:**
- Create: `financial-consistency/03-order-payment-inventory/02-invariants.md`

- [ ] **Step 1: Add invariants content**

Use `apply_patch` to create `financial-consistency/03-order-payment-inventory/02-invariants.md`:

````markdown
# 02 正确性不变量

## 核心原则

电商交易一致性必须同时保护订单事实、库存事实、支付事实、退款事实和账本事实。正确性不能依赖某一次 RPC 返回值或某个消息 offset，而要由状态机、幂等键、唯一约束、库存流水、支付/退款渠道事实、会计分录、Outbox 和对账共同保证。

## 不变量

### 订单

- 同一订单幂等键只能创建一个业务订单。
- 订单必须先成功预留库存，才能进入可支付状态。
- 支付成功订单不能被普通取消直接覆盖。
- 已支付订单取消必须进入退款、履约前取消或人工处理路径。
- 订单终态不能互相覆盖，例如 `CANCELLED` 不能静默覆盖 `PAID`。

### 库存

- 库存可售量不能为负。
- 同一订单明细只能预留一次库存。
- 同一库存预留只能确认一次或释放一次。
- `CONFIRMED` 和 `RELEASED` 是互斥终态。
- 订单取消成功必须释放未确认库存。
- 库存释放后不能再确认同一预留。

### 支付

- 同一支付单只能产生一次订单支付效果。
- 支付成功必须有可信支付渠道事实。
- 支付成功必须最终推进订单、库存确认和支付分录，或者进入退款/人工处理。
- 支付超时不是失败。
- `PAYMENT_UNKNOWN` 不能直接释放库存、取消成终态或重复提交新支付动作。
- 失败回调不能覆盖已经确认的支付成功终态。

### 退款

- 已支付订单不能通过直接改订单字段完成退款。
- 已支付订单取消必须创建退款单。
- 同一退款单只能产生一次退款业务效果。
- 累计退款金额不能超过原支付金额。
- 退款成功必须有可信退款渠道事实。
- 退款成功必须有退款单终态、订单退款终态和退款分录。
- `REFUND_UNKNOWN` 不能重复提交外部退款。

### 消息和事件

- Outbox 事件必须和本地事实在同一服务事务中提交。
- 消息消费者必须按业务幂等键去重。
- broker offset 不能证明订单、库存、支付或退款完成。
- 重复事件只能产生一次业务效果。

### 对账和修复

- 订单、支付单、库存流水、退款单、会计分录和 Outbox 消费记录最终必须能解释彼此。
- 差错必须有分类、owner、状态、修复动作和审计记录。
- 修复只能通过补订单状态、补库存流水、补退款状态、补分录、补事件、冲正或人工工单完成，不能直接覆盖历史事实。

## 常见误区

- 下单时直接扣库存，不保留预留状态。
- 把支付超时当失败并释放库存。
- 取消订单时不考虑支付回调并发。
- 已支付订单取消后直接改成取消，不创建退款单。
- 只对账订单状态，不对账库存流水、退款单和会计分录。
- 用 consumer offset 代表订单、库存、支付或退款已经完成。
````

- [ ] **Step 2: Verify invariant keywords**

Run:

```bash
rg -n "库存可售量不能为负|PAYMENT_UNKNOWN|REFUND_UNKNOWN|累计退款金额不能超过|broker offset|不能直接覆盖历史事实" financial-consistency/03-order-payment-inventory/02-invariants.md
```

Expected: output includes all required invariant anchors.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/03-order-payment-inventory/02-invariants.md
git commit -m "docs: define order payment inventory invariants"
```

Expected: commit succeeds and includes only `02-invariants.md`.

## Task 4: Create State Machine Document

**Files:**
- Create: `financial-consistency/03-order-payment-inventory/03-state-machine.md`

- [ ] **Step 1: Add state machine content**

Use `apply_patch` to create `financial-consistency/03-order-payment-inventory/03-state-machine.md`:

````markdown
# 03 状态机

## 设计原则

状态机的任务是防止订单、库存、支付和退款事实互相覆盖。所有状态推进都必须基于耐久事实和合法转换，不能只基于一次 RPC 返回值、回调或消息消费结果。

## 订单状态

正常履约路径：

```text
CREATED
-> STOCK_RESERVED
-> PENDING_PAYMENT
-> PAID
-> STOCK_CONFIRMED
-> FULFILLABLE
```

取消和退款路径：

```text
CANCEL_REQUESTED
-> CANCELLED
```

```text
PAID
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
- `PAID` 不能直接取消成 `CANCELLED`，必须进入退款、履约前取消或人工处理路径。
- `PAYMENT_UNKNOWN` 不能直接释放库存或取消成终态。
- `CANCELLED` 后收到支付成功必须进入退款或人工处理。
- `FULFILLABLE` 表示本阶段可履约，第一版不展开发货和退货。

## 库存预留状态

成功确认路径：

```text
RESERVED
-> CONFIRMED
```

取消释放路径：

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
- `RELEASED` 后不能确认同一预留。
- `CONFIRMED` 后不能释放同一预留。
- 重复确认或重复释放必须幂等返回既有结果。

## 支付单状态

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

关键规则：

- `CHANNEL_UNKNOWN` 不能被当作失败。
- `CHANNEL_SUCCEEDED` 之后必须推进订单；如果订单已经取消，必须进入退款或人工处理。
- `SUCCEEDED` 不能被失败回调覆盖。
- 支付单成功不自动代表库存已确认。

## 退款单状态

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
- 退款成功不删除原支付事实，只追加退款事实和分录。

## 非法转换示例

| 非法转换 | 原因 |
| --- | --- |
| `PAYMENT_UNKNOWN -> CANCELLED` | 支付未知不是失败，不能直接取消并释放库存。 |
| `PAID -> CANCELLED` | 已支付订单取消必须进入退款或人工处理路径。 |
| `RELEASED -> CONFIRMED` | 库存已释放后不能确认同一预留。 |
| `CONFIRMED -> RELEASED` | 库存已确认后不能释放同一预留。 |
| `REFUND_UNKNOWN -> REFUND_SUBMITTED` | 退款未知不能重复提交外部退款。 |
| `SUCCEEDED -> CHANNEL_FAILED` | 失败回调不能覆盖已确认成功终态。 |
````

- [ ] **Step 2: Verify state names**

Run:

```bash
rg -n "PAYMENT_UNKNOWN|STOCK_CONFIRM_FAILED|REFUND_UNKNOWN|CONFIRMED|RELEASED|非法转换|PAID -> CANCELLED" financial-consistency/03-order-payment-inventory/03-state-machine.md
```

Expected: output includes required state names and illegal transitions.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/03-order-payment-inventory/03-state-machine.md
git commit -m "docs: define order payment inventory state machines"
```

Expected: commit succeeds and includes only `03-state-machine.md`.

## Task 5: Create Service Boundaries Document

**Files:**
- Create: `financial-consistency/03-order-payment-inventory/04-service-boundaries.md`

- [ ] **Step 1: Add service boundaries content**

Use `apply_patch` to create `financial-consistency/03-order-payment-inventory/04-service-boundaries.md`:

````markdown
# 04 服务边界

## 目标

本文件定义电商交易闭环中的服务职责。核心原则是：订单事实、库存事实、支付事实、退款事实、账本事实和对账事实分别由明确边界拥有，不能让一个服务偷偷完成所有事情。

## 服务职责

| 服务 | 拥有什么 | 不拥有什么 |
| --- | --- | --- |
| `order-service` | 订单、订单明细、订单状态机、取消请求、订单幂等键 | 不直接扣库存，不直接确认渠道支付或退款事实 |
| `inventory-service` | 库存可售量、库存预留、确认、释放、库存流水 | 不决定订单是否支付成功，不处理退款 |
| `payment-service` | 支付单、支付回调、支付查询、支付渠道事实 | 不决定库存是否确认，不直接改订单历史 |
| `refund-service` | 退款单、退款提交、退款回调、退款查询、退款状态机 | 不直接回滚订单，不删除支付事实 |
| `ledger-service` | 支付、退款、冲正和差错修复分录 | 不覆盖历史分录，不替代订单或库存服务 |
| `reconciliation-service` | 订单/支付/库存/退款/账本对账、差错分类、修复工单 | 不直接修改订单、库存、支付、退款或分录 |
| `message-broker` | Outbox 事件投递和异步解耦 | 不代表业务事实本身 |

## 关键边界

- `order-service` 是订单状态 owner，但不是库存 owner、支付事实 owner 或退款事实 owner。
- `inventory-service` 根据订单命令处理库存预留、确认和释放，并生成库存流水。
- `payment-service` 只提供支付渠道事实和支付单状态，不直接确认库存。
- `refund-service` 只提供退款渠道事实和退款单状态，不直接删除原支付事实。
- `ledger-service` 只追加分录或冲正分录，不删除历史。
- `reconciliation-service` 发现差异后生成差错单和修复命令，自动修复也必须留下审计证据。

## 典型调用关系

### 下单

```text
order-service
-> inventory-service
-> order-service
-> message-broker
```

### 支付成功

```text
payment-service
-> order-service
-> inventory-service
-> ledger-service
-> message-broker
```

### 取消和退款

```text
order-service
-> inventory-service or refund-service
-> ledger-service
-> message-broker
```

### 对账

```text
reconciliation-service
-> order-service
-> payment-service
-> inventory-service
-> refund-service
-> ledger-service
-> repair workflow
```

## 不接受的设计

- `order-service` 直接扣减库存。
- 支付回调绕过订单状态机。
- 支付超时直接取消订单并释放库存。
- 已支付订单取消时直接改订单为取消，不创建退款单。
- 对账脚本直接改订单、库存、支付、退款或分录。
- 用消息 offset 作为订单、库存、支付或退款完成事实。
````

- [ ] **Step 2: Verify service names**

Run:

```bash
rg -n "order-service|inventory-service|payment-service|refund-service|ledger-service|reconciliation-service|message-broker|不接受的设计" financial-consistency/03-order-payment-inventory/04-service-boundaries.md
```

Expected: output includes all service names and rejected design section.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/03-order-payment-inventory/04-service-boundaries.md
git commit -m "docs: define commerce service boundaries"
```

Expected: commit succeeds and includes only `04-service-boundaries.md`.

## Task 6: Create Event Flow Document

**Files:**
- Create: `financial-consistency/03-order-payment-inventory/05-event-flow.md`

- [ ] **Step 1: Add event flow content**

Use `apply_patch` to create `financial-consistency/03-order-payment-inventory/05-event-flow.md`:

````markdown
# 05 事件流

## 目标

事件流用于区分订单命令、库存事实、支付事实、退款事实、账本事实、对账事实和人工修复事实。只有明确事实来源，系统才能在取消、支付回调、库存确认、退款和重复消息交错时恢复。

## 事件分类

| 类型 | 示例 | 事实 owner |
| --- | --- | --- |
| 订单命令 | `OrderCreateRequested`、`OrderCancelRequested` | `order-service` |
| 订单事实 | `OrderCreated`、`OrderPaid`、`OrderCancelled`、`OrderRefundRequired` | `order-service` |
| 库存事实 | `StockReserved`、`StockConfirmed`、`StockReleased` | `inventory-service` |
| 支付事实 | `PaymentSucceeded`、`PaymentFailed`、`PaymentUnknown` | `payment-service` / 支付渠道 |
| 退款事实 | `RefundSubmitted`、`RefundSucceeded`、`RefundFailed`、`RefundUnknown` | `refund-service` / 支付渠道 |
| 账本事实 | `PaymentLedgerPosted`、`RefundLedgerPosted` | `ledger-service` |
| 对账事实 | `CommerceMismatchDetected`、`CommerceRepairRequested` | `reconciliation-service` |
| 修复事实 | `ManualRepairCompleted`、`RepairVerified` | `reconciliation-service` / 运营复核 |

## 下单事件流

```text
OrderCreateRequested
-> OrderCreated
-> StockReserveRequested
-> StockReserved
-> OrderPendingPayment
```

## 支付成功事件流

```text
PaymentSucceeded
-> OrderPaid
-> StockConfirmRequested
-> StockConfirmed
-> PaymentLedgerPosted
-> OrderFulfillable
```

异常分支：

```text
PaymentSucceeded
-> OrderAlreadyCancelled
-> OrderRefundRequired or ManualReviewRequired
```

## 取消事件流

```text
OrderCancelRequested
-> OrderCancelAccepted
-> StockReleaseRequested
-> StockReleased
-> OrderCancelled
```

异常分支：

```text
OrderCancelRequested
-> OrderAlreadyPaid
-> RefundRequired or ManualReviewRequired
```

## 退款事件流

```text
RefundRequired
-> RefundCreated
-> RefundSubmitted
-> RefundSucceeded
-> OrderRefunded
-> RefundLedgerPosted
-> OrderClosed
```

异常分支：

```text
RefundUnknown
-> refund query or callback
-> RefundSucceeded or RefundFailed or ManualReviewRequired
```

## 对账事件流

匹配终止：

```text
CommerceReconciliationStarted
-> order/payment/inventory/refund/ledger matched
-> Matched
```

差错修复：

```text
CommerceMismatchDetected
-> CommerceRepairRequested
-> ManualRepairCompleted
-> RepairVerified
```

## 顺序依赖

- `OrderPendingPayment` 依赖 `StockReserved`。
- `OrderPaid` 依赖可信的 `PaymentSucceeded`。
- `StockConfirmed` 依赖 `OrderPaid`。
- `PaymentLedgerPosted` 依赖 `OrderPaid`。
- `StockReleased` 依赖合法取消裁决。
- `RefundSubmitted` 依赖 `RefundRequired`。
- `OrderRefunded` 依赖可信的 `RefundSucceeded`。
- `RefundLedgerPosted` 依赖 `OrderRefunded`。

## Broker 不是事实来源

Kafka 或其他消息系统只负责投递语义。业务事实必须来自本地数据库记录、库存流水、支付渠道事实、退款渠道事实、会计分录和对账记录，不能用 consumer offset 证明订单、库存、支付或退款已经完成。
````

- [ ] **Step 2: Verify event names**

Run:

```bash
rg -n "OrderCreateRequested|StockReserved|PaymentSucceeded|OrderCancelRequested|StockReleased|RefundSubmitted|RefundSucceeded|CommerceMismatchDetected|Broker 不是事实来源" financial-consistency/03-order-payment-inventory/05-event-flow.md
```

Expected: output includes required event names and broker warning.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/03-order-payment-inventory/05-event-flow.md
git commit -m "docs: define commerce event flow"
```

Expected: commit succeeds and includes only `05-event-flow.md`.

## Task 7: Create Failure Matrix Document

**Files:**
- Create: `financial-consistency/03-order-payment-inventory/06-failure-matrix.md`

- [ ] **Step 1: Add failure matrix content**

Use `apply_patch` to create `financial-consistency/03-order-payment-inventory/06-failure-matrix.md`:

````markdown
# 06 失败矩阵

## 目标

失败矩阵把每个危险点映射到已知事实、系统状态和恢复动作。电商交易闭环的关键是：先确认订单、库存、支付和退款事实，再决定确认库存、释放库存、退款、补事件、补分录或人工处理。

| 失败点 | 已知事实 | 系统状态 | 处理策略 |
| --- | --- | --- | --- |
| 订单创建成功但库存预留失败 | 订单存在，库存未预留 | `CREATED` 或 `RESERVE_FAILED` | 标记订单不可支付；允许重新预留或取消订单；不能进入待支付。 |
| 库存预留成功但订单状态更新失败 | 库存预留存在，订单未进入待支付 | `STOCK_RESERVED` 待修复 | 补订单状态和事件；如果订单创建失败则释放预留。 |
| 支付成功但订单未推进 | 可信支付成功事实存在 | `CHANNEL_SUCCEEDED` 待应用 | 补 `OrderPaid`，再确认库存和补支付分录。 |
| 支付成功但库存确认失败 | 支付成功，库存仍 `RESERVED` | `STOCK_CONFIRM_FAILED` | 重试确认；无法确认时进入退款或人工处理，不能静默履约。 |
| 支付失败回调晚于支付成功事实 | 已有可信支付成功终态 | stale callback | 记录审计，不覆盖订单和支付终态。 |
| 支付请求超时或未知 | 有支付请求号，没有确定结果 | `PAYMENT_UNKNOWN` | 不能当失败；查询、等待回调、渠道账单或人工复核，不能直接释放库存。 |
| 支付未知状态下用户取消订单 | 支付结果未知，库存预留存在 | `PAYMENT_UNKNOWN` + `CANCEL_REQUESTED` | 记录取消意图；等待支付事实后裁决取消、退款或人工处理。 |
| 取消成功但库存释放失败 | 取消裁决成功，库存仍 `RESERVED` | `RELEASE_FAILED` | 重试释放；失败进入人工处理；不能重复释放。 |
| 库存释放成功后收到支付成功 | `StockReleased` 和可信支付成功事实同时存在 | conflict | 创建退款需求或人工处理；不能重新确认已释放预留。 |
| 重复取消请求 | 已有取消或退款裁决 | duplicate cancel | 返回既有结果，不重复释放库存或重复退款。 |
| 退款提交超时或未知 | 有退款请求号，没有确定结果 | `REFUND_UNKNOWN` | 查询、等待回调或退款账单；不能重复提交外部退款。 |
| 退款成功但订单未关闭 | 可信退款成功事实存在 | `REFUND_SUCCEEDED` 待应用 | 补 `OrderRefunded`、补退款分录和事件。 |
| 退款失败晚于退款成功事实 | 已有可信退款成功终态 | stale callback | 记录审计，不覆盖退款成功终态。 |
| Outbox 事件发布失败 | 本地事实已提交，事件未发布 | outbox pending | 重试发布，不重做订单、库存、支付或退款动作。 |
| 消费者重复消费 | 消息重复投递 | consumer dedup | 使用业务幂等键和唯一约束去重。 |
| 对账发现订单、库存、支付或退款不一致 | 对账发现差异 | `CommerceMismatchDetected` | 分类差错，进入修复工作流。 |
| 人工修复动作失败或重复提交 | 修复工单存在 | repair pending or duplicate | 使用修复幂等键，保留审批和审计记录。 |

## 决策规则

- 支付或退款已提交外部请求但结果未知时，只能查询、等待回调、对账或人工处理，不能直接失败。
- 已确认支付成功但本地订单或库存缺失事实时，优先补齐本地事实。
- 已确认退款成功但本地订单或分录缺失事实时，优先补齐本地事实。
- 库存确认和释放是互斥事实，冲突时进入退款或人工处理。
- 已经发生的订单、库存、支付、退款和分录事实不能删除，只能用补事实、冲正、退款或人工修复解释。
````

- [ ] **Step 2: Verify failure cases**

Run:

```bash
rg -n "库存预留失败|支付成功但订单未推进|支付成功但库存确认失败|PAYMENT_UNKNOWN|库存释放成功后收到支付成功|REFUND_UNKNOWN|退款成功但订单未关闭|Outbox|人工修复" financial-consistency/03-order-payment-inventory/06-failure-matrix.md
```

Expected: output includes required failure categories.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/03-order-payment-inventory/06-failure-matrix.md
git commit -m "docs: define commerce failure matrix"
```

Expected: commit succeeds and includes only `06-failure-matrix.md`.

## Task 8: Create Reconciliation Document

**Files:**
- Create: `financial-consistency/03-order-payment-inventory/07-reconciliation.md`

- [ ] **Step 1: Add reconciliation content**

Use `apply_patch` to create `financial-consistency/03-order-payment-inventory/07-reconciliation.md`:

````markdown
# 07 对账设计

## 为什么本阶段必须讲对账

电商交易闭环里，订单、支付、库存、退款和账本都可能因为异步消息、回调、取消并发或故障恢复而分叉。对账不是后期报表，而是发现订单事实、库存事实、支付事实和退款事实不一致的核心链路。

## 对账类型

| 类型 | 关注点 | 主要输入 |
| --- | --- | --- |
| 订单支付对账 | 订单状态和支付单、渠道账单是否一致 | 订单、支付单、支付回调、支付渠道账单 |
| 订单库存对账 | 订单状态和库存预留、确认、释放流水是否一致 | 订单、订单明细、库存预留记录、库存流水 |
| 订单退款对账 | 订单取消/退款状态和退款单、退款渠道账单是否一致 | 订单、退款单、退款回调、退款渠道账单 |
| 账本对账 | 支付、退款和冲正分录能否解释业务状态 | 订单、支付单、退款单、库存流水、会计分录、Outbox 消费记录 |

## 差错分类

| 差错 | 含义 | owner | 修复方向 |
| --- | --- | --- | --- |
| 支付成功，订单未支付 | 支付渠道成功，但订单仍待支付 | order-service、payment-service | 补订单支付状态，补事件 |
| 支付成功，库存未确认 | 订单已支付，但库存预留未确认 | inventory-service、order-service | 补库存确认；失败进入退款或人工处理 |
| 订单取消，库存未释放 | 订单已取消，但库存仍预留 | inventory-service | 补释放库存流水，补事件 |
| 库存释放后支付成功 | 支付成功事实和库存释放事实冲突 | order-service、refund-service、manual review | 创建退款需求或人工处理 |
| 订单已退款，渠道退款缺失 | 本地已退款，但渠道账单没有退款 | refund-service、reconciliation-service、manual review | 查询渠道，必要时冲正或人工复核 |
| 渠道退款成功，本地订单未关闭 | 渠道退款成功，但订单或退款单未终结 | order-service、refund-service、ledger-service | 补订单退款状态、补退款分录、补事件 |
| 退款金额不一致 | 退款单、渠道退款和分录金额不一致 | refund-service、ledger-service、manual review | 差额调整、冲正或人工复核 |
| 库存流水缺失 | 订单状态需要库存事实，但库存流水不存在 | inventory-service | 补库存流水或人工修复 |
| 库存流水重复 | 同一订单明细出现多次确认或释放 | inventory-service、manual review | 冲正重复流水，检查幂等缺陷 |
| 分录缺失 | 支付或退款事实存在，但会计分录缺失 | ledger-service | 补分录 |
| Outbox 事件缺失 | 本地事实存在，但下游事件缺失 | event repair | 补发缺失 Outbox 事实 |
| 长时间未知状态 | 支付、退款或库存状态长期无法收敛 | reconciliation-service、manual review | 查询、账单核验、人工复核 |

## 修复路由

`reconciliation-service` 只负责分类、记录差错状态、创建修复命令或工单，并写入审计记录；它不直接修改订单、库存、支付、退款或会计分录。

- `order-service`：通过幂等命令补订单状态或创建退款需求。
- `inventory-service`：通过幂等命令补库存确认、释放或冲正库存流水。
- `payment-service`：补支付状态、查询渠道事实或标记支付差错。
- `refund-service`：补退款状态、查询退款事实或创建退款修复任务。
- `ledger-service`：追加支付分录、退款分录或冲正分录。
- `event repair`：补发缺失的 Outbox 事实，保证下游消费记录可追溯。
- `manual review`：处理库存释放后支付成功、退款金额不一致、渠道账单缺失等高风险差错。

## 对账输入

- 订单和订单状态历史。
- 支付单、支付回调、支付查询结果和支付渠道账单。
- 库存预留记录、库存确认流水、库存释放流水。
- 退款单、退款回调、退款查询结果和退款渠道账单。
- 会计分录。
- Outbox 事件和消费记录。
- 差错单和人工处理记录。

## 修复原则

- 不直接覆盖订单、库存、支付、退款或分录历史。
- 修复动作必须有幂等键。
- 自动修复必须留下审计记录。
- 高风险修复需要 maker-checker 或人工复核。
- 修复完成后必须重新对账。

## 对账输出

- `MATCHED`：订单、支付、库存、退款和账本事实一致。
- `MISMATCH_DETECTED`：发现差错。
- `REPAIR_REQUESTED`：已生成修复动作。
- `REPAIRED`：修复动作完成。
- `VERIFIED`：修复后复核通过。
````

- [ ] **Step 2: Verify reconciliation categories**

Run:

```bash
rg -n "订单支付对账|订单库存对账|订单退款对账|支付成功，库存未确认|库存释放后支付成功|渠道退款成功，本地订单未关闭|库存流水重复|修复路由|不直接修改" financial-consistency/03-order-payment-inventory/07-reconciliation.md
```

Expected: output includes required reconciliation categories and repair routing.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/03-order-payment-inventory/07-reconciliation.md
git commit -m "docs: define commerce reconciliation"
```

Expected: commit succeeds and includes only `07-reconciliation.md`.

## Task 9: Create Verification Plan Document

**Files:**
- Create: `financial-consistency/03-order-payment-inventory/08-verification-plan.md`

- [ ] **Step 1: Add verification content**

Use `apply_patch` to create `financial-consistency/03-order-payment-inventory/08-verification-plan.md`:

````markdown
# 08 验证路线

## 目标

验证路线要证明设计能暴露电商交易闭环中最危险的问题：超卖、支付取消并发、库存重复确认或释放、支付未知状态错误释放库存、重复退款、退款未知状态重复提交、订单支付库存退款对账差错。

## 模型验证

需要建模的规则：

- `PAYMENT_UNKNOWN` 不能直接释放库存或取消成终态。
- `REFUND_UNKNOWN` 不能重复提交外部退款。
- `CONFIRMED` 和 `RELEASED` 互斥。
- 支付成功终态不能被失败回调覆盖。
- 已支付订单取消必须进入退款或人工处理路径。
- 对账差错必须进入分类和修复状态。

## 属性测试

随机生成这些序列：

- 订单创建、库存预留成功或失败。
- 支付成功、失败、超时、未知和重复回调。
- 用户取消、系统超时取消和重复取消。
- 库存确认、库存释放、确认失败和释放失败。
- 退款成功、失败、未知和重复回调。
- Outbox 重复投递和消费者重复消费。
- 人工修复重复提交。

检查属性：

- 库存可售量不能为负。
- 同一订单明细最多一个有效库存预留。
- 同一库存预留不能既确认又释放。
- 支付成功订单最终进入履约、退款或人工处理。
- 已支付订单取消必须产生退款需求。
- 累计退款金额不能超过原支付金额。
- `PAYMENT_UNKNOWN` 不能触发库存释放终态。
- `REFUND_UNKNOWN` 不能触发第二次外部退款。
- 终态不被非法覆盖。

## 集成测试

使用真实数据库语义验证：

- 订单幂等唯一约束。
- 库存预留唯一约束。
- 支付单和退款单幂等约束。
- 本地事务和 Outbox 同提交。
- consumer dedup。
- 支付回调和取消请求并发到达。
- 库存确认失败后的修复路径。
- 退款未知状态查询补偿。

## 故障注入

必须注入：

- 订单创建后库存预留失败。
- 库存预留成功后订单状态更新失败。
- 支付成功后订单更新失败。
- 支付成功后库存确认失败。
- 支付回调重复、乱序和失败晚于成功。
- 取消成功后库存释放失败。
- 库存释放成功后收到支付成功。
- 退款提交超时。
- 退款成功后订单关闭失败。
- Outbox 发布失败。
- 消费者崩溃和重复消费。
- 对账账单缺失或金额不一致。

## 历史检查

记录所有用户命令、订单状态变化、库存流水、支付事实、退款事实、会计分录、Outbox 事件和对账结果。检查最终历史是否满足：

- 每个订单状态转换合法。
- 每个库存预留最终确认、释放或人工处理。
- 每个支付成功订单有明确履约、退款或人工处理路径。
- 每个退款成功有订单终态和退款分录。
- 每个幂等键最多一个业务效果。
- 每个差错都有分类、owner、修复动作和审计记录。

## 对账验证

构造账单和本地状态覆盖：

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

每类差错都必须生成稳定差错分类、owner、修复动作和审计证据。修复不能覆盖历史事实，修复完成后必须重新对账。
````

- [ ] **Step 2: Verify verification methods**

Run:

```bash
rg -n "模型验证|属性测试|集成测试|故障注入|历史检查|对账验证|PAYMENT_UNKNOWN|REFUND_UNKNOWN|库存可售量不能为负|累计退款金额不能超过" financial-consistency/03-order-payment-inventory/08-verification-plan.md
```

Expected: output includes all verification methods and critical properties.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/03-order-payment-inventory/08-verification-plan.md
git commit -m "docs: define commerce verification"
```

Expected: commit succeeds and includes only `08-verification-plan.md`.

## Task 10: Create Interview Synthesis Document

**Files:**
- Create: `financial-consistency/03-order-payment-inventory/09-interview-synthesis.md`

- [ ] **Step 1: Add interview content**

Use `apply_patch` to create `financial-consistency/03-order-payment-inventory/09-interview-synthesis.md`:

````markdown
# 09 面试与架构评审表达

## 一句话回答

电商交易一致性不是下单扣库存这么简单。真实系统必须把订单状态机、库存预留、支付渠道事实、取消裁决、退款状态机、Outbox、幂等消费者、会计分录、对账和人工修复组合起来，才能让订单最终进入履约、取消、退款或人工处理中的可解释终态。

## 标准回答结构

1. 先说明订单、库存、支付和退款是不同事实边界。
2. 再说明库存必须用预留、确认、释放，而不是直接扣减。
3. 再说明支付回调和取消请求通过状态机裁决并发。
4. 再说明已支付订单取消必须进入退款流程。
5. 再说明跨服务事实通过 Outbox 和幂等消费者传播。
6. 最后说明如何验证：模型验证、属性测试、故障注入、历史检查和对账验证。

## 高频问题

### 电商下单为什么不能直接扣库存？

直接扣库存会让取消、支付失败、支付未知和重复消息难以解释。更稳妥的做法是先预留库存，支付成功后确认库存，取消或可信失败后释放库存。

### 支付成功和订单取消并发时怎么处理？

必须通过订单状态机和版本条件更新裁决。取消先成功时，后续支付成功进入退款或人工处理；支付先成功时，取消必须进入退款或履约前取消路径。

### 支付超时能不能释放库存？

不能。支付超时不是失败，订单应进入 `PAYMENT_UNKNOWN`，后续通过查询、回调、渠道账单或人工处理收敛。在可信失败事实出现前不能直接释放库存或取消成终态。

### 支付成功但库存释放了怎么办？

这是订单、支付和库存事实冲突。不能重新确认已释放预留，通常应创建退款需求或进入人工处理，并通过对账留下差错和修复证据。

### 已支付订单取消为什么必须走退款？

因为支付成功是已经发生的外部资金事实。不能把订单字段简单改回未支付或取消来掩盖资金事实，必须创建退款单、跟踪退款渠道事实、追加退款分录，并推进订单终态。

### 如何防止重复退款？

退款单必须有幂等键和唯一约束，退款未知状态不能重复提交外部退款。重复回调或重复消息只能返回既有处理结果，不能再次产生退款业务效果。

### 订单、支付、库存、退款如何对账？

对账需要同时比较订单状态、支付单、渠道账单、库存预留和库存流水、退款单、退款渠道账单、会计分录、Outbox 和消费记录。每个差错必须有分类、owner、修复动作和审计证据。

### Temporal 在这里解决什么？

Temporal 适合承接长流程、定时查询、重试、超时处理和人工处理入口。它不替代订单状态机、库存幂等约束、支付/退款渠道事实、Outbox、会计分录或对账。

## 评审底线

- 不接受下单直接扣库存而没有预留状态。
- 不接受支付超时直接取消订单并释放库存。
- 不接受支付成功被普通取消覆盖。
- 不接受已支付订单取消但没有退款单。
- 不接受退款未知状态下重复提交外部退款。
- 不接受只有订单状态、没有库存流水、退款单和会计分录。
- 不接受没有订单、支付、库存、退款对账和差错修复流程。
````

- [ ] **Step 2: Verify interview questions**

Run:

```bash
rg -n "下单为什么不能直接扣库存|支付成功和订单取消并发|支付超时能不能释放库存|支付成功但库存释放|为什么必须走退款|如何防止重复退款|如何对账|Temporal" financial-consistency/03-order-payment-inventory/09-interview-synthesis.md
```

Expected: output includes all interview questions.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/03-order-payment-inventory/09-interview-synthesis.md
git commit -m "docs: add commerce interview synthesis"
```

Expected: commit succeeds and includes only `09-interview-synthesis.md`.

## Task 11: Update Root README

**Files:**
- Modify: `financial-consistency/README.md`

- [ ] **Step 1: Add design spec link**

In `financial-consistency/README.md`, add this line to the formal design document list after the payment recharge withdraw design link:

```markdown
- [2026-05-02-order-payment-inventory-design.md](../docs/superpowers/specs/2026-05-02-order-payment-inventory-design.md)
```

- [ ] **Step 2: Link phase 03 route**

Change:

```markdown
- 03-order-payment-inventory
  电商下单、支付、库存、取消、退款、消息最终一致性。
```

to:

```markdown
- [03-order-payment-inventory](./03-order-payment-inventory/README.md)
  电商下单、支付、库存、取消、退款、消息最终一致性。
```

- [ ] **Step 3: Verify root README links**

Run:

```bash
rg -n "2026-05-02-order-payment-inventory-design.md|\./03-order-payment-inventory/README.md" financial-consistency/README.md
```

Expected: output includes both links.

- [ ] **Step 4: Commit**

Run:

```bash
git add financial-consistency/README.md
git commit -m "docs: link order payment inventory phase"
```

Expected: commit succeeds and includes only `financial-consistency/README.md`.

## Task 12: Final Documentation Verification

**Files:**
- Verify: `financial-consistency/03-order-payment-inventory/**`
- Verify: `financial-consistency/README.md`

- [ ] **Step 1: Verify all phase files exist**

Run:

```bash
find financial-consistency/03-order-payment-inventory -maxdepth 1 -type f | sort
```

Expected output:

```text
financial-consistency/03-order-payment-inventory/01-scenario-cards.md
financial-consistency/03-order-payment-inventory/02-invariants.md
financial-consistency/03-order-payment-inventory/03-state-machine.md
financial-consistency/03-order-payment-inventory/04-service-boundaries.md
financial-consistency/03-order-payment-inventory/05-event-flow.md
financial-consistency/03-order-payment-inventory/06-failure-matrix.md
financial-consistency/03-order-payment-inventory/07-reconciliation.md
financial-consistency/03-order-payment-inventory/08-verification-plan.md
financial-consistency/03-order-payment-inventory/09-interview-synthesis.md
financial-consistency/03-order-payment-inventory/README.md
```

- [ ] **Step 2: Verify README child links**

Run:

```bash
rg -n "\./01-scenario-cards.md|\./02-invariants.md|\./03-state-machine.md|\./04-service-boundaries.md|\./05-event-flow.md|\./06-failure-matrix.md|\./07-reconciliation.md|\./08-verification-plan.md|\./09-interview-synthesis.md" financial-consistency/03-order-payment-inventory/README.md
```

Expected: output includes all 9 child document links.

- [ ] **Step 3: Verify core scenario coverage**

Run:

```bash
rg -n "下单并预留库存|支付成功后确认订单和库存|支付失败、超时或未知状态|订单取消与支付回调并发|已支付订单取消和退款|订单、支付、库存、退款对账" financial-consistency/03-order-payment-inventory/01-scenario-cards.md
```

Expected: output includes all 6 scenario names.

- [ ] **Step 4: Verify main technical anchors**

Run:

```bash
rg -n "PAYMENT_UNKNOWN|REFUND_UNKNOWN|库存可售量不能为负|累计退款金额不能超过|Outbox|库存流水|会计分录|重复退款|Temporal|对账" financial-consistency/03-order-payment-inventory
```

Expected: output includes the core terms across the phase docs.

- [ ] **Step 5: Verify root README link**

Run:

```bash
rg -n "2026-05-02-order-payment-inventory-design.md|\./03-order-payment-inventory/README.md" financial-consistency/README.md
```

Expected: output includes both root README links.

- [ ] **Step 6: Verify previous phases were not changed in this phase**

Run:

```bash
git diff --name-only main..HEAD -- financial-consistency/01-transfer financial-consistency/02-payment-recharge-withdraw
```

Expected: no output.

- [ ] **Step 7: Scan for incomplete-document markers**

Run:

```bash
rg -n "TO[D]O|TB[D]|待[定]|占[位]|以[后]补|未[决]|大[概]|随[便]" financial-consistency/03-order-payment-inventory financial-consistency/README.md
```

Expected: no output and exit code `1`.

- [ ] **Step 8: Check Markdown whitespace**

Run:

```bash
git diff --check
```

Expected: no output and exit code `0`.

- [ ] **Step 9: Verify only expected work remains**

Run:

```bash
git status --short
```

Expected: no tracked file modifications related to this phase. Existing unrelated files outside this phase may remain and must not be added to phase commits.
