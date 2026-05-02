# Travel Booking Saga Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `04-travel-booking-saga` learning module for realistic travel combination booking consistency across flights, hotels, rental cars, insurance, payment policy, compensation, reconciliation, and verification.

**Architecture:** This is a documentation-only phase that follows the structure of `02-payment-recharge-withdraw` and `03-order-payment-inventory`. Each file owns one concept: scenario cards, invariants, state machines, service boundaries, event flow, failure matrix, reconciliation, verification, and interview synthesis. The root README will link the new phase and its design spec.

**Tech Stack:** Markdown, Git, `rg`, `find`, `git diff --check`.

---

## File Structure

- Create directory: `financial-consistency/04-travel-booking-saga/`
- Create: `financial-consistency/04-travel-booking-saga/README.md`
- Create: `financial-consistency/04-travel-booking-saga/01-scenario-cards.md`
- Create: `financial-consistency/04-travel-booking-saga/02-invariants.md`
- Create: `financial-consistency/04-travel-booking-saga/03-state-machine.md`
- Create: `financial-consistency/04-travel-booking-saga/04-service-boundaries.md`
- Create: `financial-consistency/04-travel-booking-saga/05-event-flow.md`
- Create: `financial-consistency/04-travel-booking-saga/06-failure-matrix.md`
- Create: `financial-consistency/04-travel-booking-saga/07-reconciliation.md`
- Create: `financial-consistency/04-travel-booking-saga/08-verification-plan.md`
- Create: `financial-consistency/04-travel-booking-saga/09-interview-synthesis.md`
- Modify: `financial-consistency/README.md`

Do not modify `financial-consistency/01-transfer/**`, `financial-consistency/02-payment-recharge-withdraw/**`, or `financial-consistency/03-order-payment-inventory/**`.

## Task 1: Create Phase README

**Files:**
- Create: `financial-consistency/04-travel-booking-saga/README.md`

- [ ] **Step 1: Create directory**

Run:

```bash
mkdir -p financial-consistency/04-travel-booking-saga
```

Expected: command succeeds.

- [ ] **Step 2: Add README content**

Use `apply_patch` to create `financial-consistency/04-travel-booking-saga/README.md`:

````markdown
# 04 旅行组合预订 Saga 一致性

## 目标

这一阶段把学习主线从电商订单推进到旅行组合预订。核心不是多个供应商一起成功或一起失败，而是理解机票、酒店、租车和保险这些外部动作不可控、价格会漂移、部分动作不可逆时，系统如何进入可解释终态。

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

- 为什么旅行组合交易通常不能做严格全有全无？
- 为什么机票和酒店是核心项，租车和保险是附加项？
- 为什么补偿不是回滚，而是释放授权、取消供应商保留、退款、罚金、补差、替代供应商或人工处理？
- 为什么付款策略必须按子产品建模？
- 为什么搜索价、锁价和最终成交价必须区分？
- 为什么供应商确认、出票、保险生效和支付扣款都必须是可审计事实？
- 为什么组合订单必须支持部分成功、附加项失败和人工处理状态？

## 本阶段范围

第一版覆盖 7 个核心场景：

- 搜索报价、锁价和报价过期。
- 创建组合订单和子订单。
- 预授权、扣款、释放授权和退款。
- 机票出票和酒店确认的核心 Saga。
- 租车和保险附加项处理。
- 核心失败、附加失败、部分成功和人工处理。
- 供应商、支付、退款、罚金、补差和本地订单对账。

第一版不覆盖真实 GDS/CRS SDK、复杂退改签规则、多城市多航段、保险理赔、会员积分、供应商结算、多币种清结算和监管报送。那些内容会在后续模块或扩展场景中处理。

## 最小闭环

```text
搜索报价
-> 创建组合订单和子订单
-> 识别每个子产品的付款策略和可逆性
-> 预授权或扣款
-> 锁座/出票、酒店保留/确认、租车确认、保险投保
-> 成功、失败、未知或部分成功裁决
-> 释放授权、取消供应商保留、退款、罚金、补差、替代供应商或人工处理
-> 供应商/支付/退款/账本事件
-> 对账与差错修复
```

## 本阶段结论

旅行组合 Saga 的补偿不是数据库回滚。真实实现必须把核心项和附加项分层，用状态机记录每个子订单和供应商事实，用付款策略决定预授权、扣款、释放授权和退款，用 Outbox 传播事实，用对账和人工处理收敛不可逆或未知状态。
````

- [ ] **Step 3: Verify README links**

Run:

```bash
rg -n "\./01-scenario-cards.md|\./02-invariants.md|\./03-state-machine.md|\./04-service-boundaries.md|\./05-event-flow.md|\./06-failure-matrix.md|\./07-reconciliation.md|\./08-verification-plan.md|\./09-interview-synthesis.md" financial-consistency/04-travel-booking-saga/README.md
```

Expected: output includes all 9 linked child documents.

- [ ] **Step 4: Commit**

Run:

```bash
git add financial-consistency/04-travel-booking-saga/README.md
git commit -m "docs: add travel booking saga module entry"
```

Expected: commit succeeds and includes only `financial-consistency/04-travel-booking-saga/README.md`.

## Task 2: Create Scenario Cards

**Files:**
- Create: `financial-consistency/04-travel-booking-saga/01-scenario-cards.md`

- [ ] **Step 1: Add scenario cards content**

Use `apply_patch` to create `financial-consistency/04-travel-booking-saga/01-scenario-cards.md`:

````markdown
# 01 场景卡

## 目的

本文件先定义旅行组合预订的业务边界，再讨论 Saga 和一致性方案。每张场景卡都回答：链路从哪里开始，核心成功目标是什么，哪些事实必须持久化，哪些失败最危险。

## 搜索报价、锁价和报价过期

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 用户搜索机票、酒店、租车和保险；系统展示组合报价；用户选择后尝试锁价或生成报价快照。 |
| 参与方 | 用户、booking-service、supplier-adapter-service、flight supplier、hotel supplier、car supplier、insurance supplier。 |
| 核心状态机 | 报价：`SEARCHED -> QUOTE_SELECTED -> QUOTE_LOCKED`，过期进入 `QUOTE_EXPIRED` 或 `PRICE_CHANGED`。 |
| 正确性不变量 | 搜索价不能直接当成交价；报价过期后不能按旧价扣款；价格变动必须被记录并等待用户确认或重新报价。 |
| 关键命令和事件 | `TravelSearchRequested`、`QuoteSelected`、`QuoteLockRequested`、`QuoteLocked`、`QuoteExpired`、`PriceChanged`。 |
| 耐久事实 | 报价快照、供应商报价号、价格、币种、有效期、可退改规则、付款策略。 |
| 最危险失败点 | 报价过期后继续扣款；供应商库存消失；价格上涨但没有用户确认；报价快照和供应商事实无法对账。 |
| 补偿方式 | 重新报价、用户确认差价、取消组合订单、释放授权或人工处理。 |
| 对账来源 | 报价快照、供应商报价响应、组合订单、支付授权记录、用户确认记录。 |
| 验证方式 | 报价过期故障注入、价格变动属性测试、用户确认审计检查。 |

## 创建组合订单和子订单

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 用户确认组合报价；booking-service 创建组合订单；为机票、酒店、租车和保险创建子订单。 |
| 参与方 | 用户、booking-service、payment-service、message-broker。 |
| 核心状态机 | 组合订单：`QUOTE_SELECTED -> BOOKING_CREATED`；子订单：`CREATED`。 |
| 正确性不变量 | 同一幂等键只能创建一个组合订单；组合订单必须能解释所有子订单；每个子订单必须记录供应商、报价、付款策略和可逆性。 |
| 关键命令和事件 | `BookingCreateRequested`、`BookingCreated`、`TravelItemCreated`、`PaymentPolicyRecorded`。 |
| 耐久事实 | 组合订单、子订单、幂等键、报价快照、付款策略、可逆性快照、Outbox 事件。 |
| 最危险失败点 | 组合订单存在但子订单缺失；重复创建组合订单；子订单没有独立状态机；付款策略没有快照。 |
| 补偿方式 | 幂等返回既有组合订单；补子订单和事件；无法补齐时进入人工处理。 |
| 对账来源 | 组合订单、子订单、报价快照、Outbox 消费记录。 |
| 验证方式 | 重复创建测试、子订单完整性检查、付款策略快照检查。 |

## 预授权、扣款、释放授权和退款

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 系统按子产品付款策略执行预授权、立即扣款、到供应商支付或不可退规则；资金动作和供应商动作解耦。 |
| 参与方 | 用户、booking-service、payment-service、refund-service、ledger-service、payment channel。 |
| 核心状态机 | 付款：`PAYMENT_CREATED -> AUTHORIZED -> CAPTURED`；释放：`AUTHORIZED -> VOIDED`；退款：`CAPTURED -> REFUNDING -> REFUNDED`。 |
| 正确性不变量 | 同一授权只能 capture 或 void 一次；已 capture 资金不能 void；退款、罚金和补差必须有分录。 |
| 关键命令和事件 | `PaymentAuthorized`、`PaymentCaptured`、`AuthorizationVoided`、`RefundRequired`、`RefundSucceeded`、`PenaltyPosted`、`AdjustmentPosted`。 |
| 耐久事实 | 支付单、授权号、capture 记录、void 记录、退款单、罚金、补差、会计分录。 |
| 最危险失败点 | 供应商失败后忘记释放授权；已扣款后供应商失败但没有退款；重复 capture；重复退款；罚金没有分录。 |
| 补偿方式 | void/release 授权、退款、冲正、罚金分录、补差分录或人工处理。 |
| 对账来源 | 支付单、退款单、渠道账单、会计分录、供应商规则。 |
| 验证方式 | capture/void 互斥属性测试、退款幂等测试、罚金补差对账。 |

## 机票出票和酒店确认的核心 Saga

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 机票和酒店是核心项；系统锁座或出票、酒店保留或确认；核心项全部成功后组合订单进入核心成功。 |
| 参与方 | booking-service、supplier-adapter-service、flight supplier、hotel supplier、payment-service、refund-service、manual-review-service。 |
| 核心状态机 | 组合订单：`PAYMENT_AUTHORIZED -> CORE_BOOKING_IN_PROGRESS -> CORE_CONFIRMED`；子订单：`SUPPLIER_PENDING -> SUPPLIER_CONFIRMED`。 |
| 正确性不变量 | 核心项未全部成功时组合订单不能 `CONFIRMED`；供应商未知不是失败；供应商成功不能被失败回调覆盖。 |
| 关键命令和事件 | `FlightTicketRequested`、`FlightTicketed`、`HotelConfirmRequested`、`HotelConfirmed`、`CoreBookingConfirmed`、`CoreBookingFailed`。 |
| 耐久事实 | 机票子订单、酒店子订单、供应商请求号、PNR 或确认号、供应商状态历史、付款状态。 |
| 最危险失败点 | 机票已出票但酒店失败；酒店已确认但机票失败；一端未知；一端成功一端失败时直接把整单失败。 |
| 补偿方式 | 尝试取消或退款已成功核心项；计算罚金或补差；替代供应商；进入人工处理。 |
| 对账来源 | 组合订单、机票供应商订单、酒店供应商订单、支付单、退款单、会计分录。 |
| 验证方式 | 核心项部分成功故障注入、供应商未知测试、成功后失败回调测试。 |

## 租车和保险附加项处理

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 租车和保险是附加项；核心项成功后附加项继续确认；附加项失败不取消核心行程。 |
| 参与方 | booking-service、supplier-adapter-service、car supplier、insurance supplier、refund-service、manual-review-service。 |
| 核心状态机 | `CORE_CONFIRMED -> ADDON_BOOKING_IN_PROGRESS -> CONFIRMED` 或 `CONFIRMED_WITH_ADDON_FAILURES`。 |
| 正确性不变量 | 附加项失败不能覆盖核心成功事实；保险生效不能被本地删除掩盖；附加项退款必须能解释组合订单状态。 |
| 关键命令和事件 | `CarBookingRequested`、`CarBooked`、`InsuranceApplyRequested`、`InsuranceIssued`、`AddonFailed`、`AddonRefundRequired`。 |
| 耐久事实 | 租车子订单、保险子订单、供应商确认号、保险保单号、退款单、用户通知记录。 |
| 最危险失败点 | 租车失败却取消机票酒店；保险投保失败但订单显示已投保；保险已生效后收到失败回调；附加项退款和组合状态不一致。 |
| 补偿方式 | 保留核心成功；退款附加项；替代供应商；提示用户未投保；人工处理。 |
| 对账来源 | 组合订单、租车供应商订单、保险供应商订单、退款单、用户通知和账本。 |
| 验证方式 | 附加失败属性测试、核心保留测试、保险生效后失败回调测试。 |

## 核心失败、附加失败、部分成功和人工处理

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 组合订单可能进入部分成功、附加失败或人工处理；系统必须解释每个子订单最终状态。 |
| 参与方 | 用户、booking-service、manual-review-service、payment-service、refund-service、ledger-service。 |
| 核心状态机 | `PARTIALLY_CONFIRMED -> COMPENSATING -> REFUNDING -> MANUAL_REVIEW` 或 `CANCELLED`。 |
| 正确性不变量 | `PARTIALLY_CONFIRMED` 必须有 owner、下一步动作和审计记录；人工处理不能直接覆盖供应商或资金事实。 |
| 关键命令和事件 | `PartialBookingDetected`、`CompensationRequested`、`ManualReviewRequested`、`UserDecisionRecorded`、`ManualRepairCompleted`。 |
| 耐久事实 | 部分成功记录、补偿命令、用户决策、人工工单、审批记录、审计记录。 |
| 最危险失败点 | 只有总订单状态没有子订单事实；用户决策无审计；人工修复直接改历史；部分成功无法向客服和财务解释。 |
| 补偿方式 | 用户确认替代或补差；运营审批退款或罚金；追加修复事实；重新对账。 |
| 对账来源 | 组合订单、子订单、人工工单、用户确认记录、退款单、会计分录。 |
| 验证方式 | 人工修复重复提交测试、审计记录检查、部分成功历史检查。 |

## 供应商、支付、退款、罚金、补差和本地订单对账

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 系统对比本地组合订单、子订单、供应商订单、支付、退款、罚金、补差、会计分录和事件消费记录。 |
| 参与方 | reconciliation-service、booking-service、supplier-adapter-service、payment-service、refund-service、ledger-service、manual-review-service。 |
| 核心状态机 | `RECONCILIATION_STARTED -> MATCHED` 或 `MISMATCH_DETECTED -> REPAIR_REQUESTED -> REPAIRED -> VERIFIED`。 |
| 正确性不变量 | 差错必须有分类、owner、状态、修复动作和审计记录；对账服务不直接修改领域事实。 |
| 关键命令和事件 | `TravelStatementImported`、`SupplierMismatchDetected`、`PaymentMismatchDetected`、`TravelRepairRequested`、`TravelRepairVerified`。 |
| 耐久事实 | 对账批次、供应商账单、支付账单、退款账单、差错单、修复命令、复核记录。 |
| 最危险失败点 | 本地确认但供应商无订单；供应商确认但本地未推进；已扣款但核心失败未退款；罚金或补差无分录。 |
| 补偿方式 | 补订单状态、补供应商事实、补退款、补罚金或补差分录、补事件、冲正或人工复核。 |
| 对账来源 | 组合订单、子订单、供应商订单、支付单、退款单、罚金、补差、会计分录、Outbox 消费记录。 |
| 验证方式 | 构造差异账单、分类准确性测试、修复后不变量检查、审计记录检查。 |
````

- [ ] **Step 2: Verify scenario headings**

Run:

```bash
rg -n "^## 搜索报价、锁价和报价过期|^## 创建组合订单和子订单|^## 预授权、扣款、释放授权和退款|^## 机票出票和酒店确认的核心 Saga|^## 租车和保险附加项处理|^## 核心失败、附加失败、部分成功和人工处理|^## 供应商、支付、退款、罚金、补差和本地订单对账" financial-consistency/04-travel-booking-saga/01-scenario-cards.md
```

Expected: output includes all 7 scenario headings.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/04-travel-booking-saga/01-scenario-cards.md
git commit -m "docs: add travel booking saga scenario cards"
```

Expected: commit succeeds and includes only `01-scenario-cards.md`.

## Task 3: Create Invariants Document

**Files:**
- Create: `financial-consistency/04-travel-booking-saga/02-invariants.md`

- [ ] **Step 1: Add invariants content**

Use `apply_patch` to create `financial-consistency/04-travel-booking-saga/02-invariants.md`:

````markdown
# 02 正确性不变量

## 核心原则

旅行组合预订一致性必须同时保护组合订单事实、子订单事实、供应商事实、付款事实、退款事实和账本事实。正确性不能依赖某个供应商 RPC 返回值或某个消息 offset，而要由状态机、幂等键、唯一约束、供应商事实、资金渠道事实、会计分录、Outbox、对账和人工处理共同保证。

## 不变量

### 组合订单

- 同一幂等键只能创建一个组合订单。
- 每个组合订单必须有可解释的子订单集合。
- 组合订单 `CONFIRMED` 必须要求机票和酒店核心项成功。
- 附加项失败不能把核心成功订单改成失败。
- `CONFIRMED_WITH_ADDON_FAILURES` 必须明确失败附加项、退款或替代动作。
- `PARTIALLY_CONFIRMED` 必须有 owner、下一步动作和审计记录。

### 子订单和供应商

- 每个子订单必须记录供应商、供应商请求号、付款策略和可逆性快照。
- 搜索价不能直接当成交价。
- 报价过期后不能按旧价扣款，除非用户重新确认。
- `SUPPLIER_UNKNOWN` 不能直接当失败。
- 供应商成功事实不能被失败回调覆盖。
- 不可逆或半不可逆动作不能被数据库字段回滚掩盖。

### 核心项和附加项

- 机票和酒店是核心项，核心项未全部成功时组合订单不能 `CONFIRMED`。
- 租车和保险是附加项，附加项失败默认保留核心成功。
- 附加项退款、替代供应商或用户通知必须能解释组合订单状态。
- 保险已生效不能被本地删除掩盖，只能追加取消、退款、作废或人工处理事实。

### 付款和退款

- 付款策略必须按子产品记录，不能用全局付款策略覆盖所有子订单。
- 同一授权只能 capture 或 void 一次。
- 已 capture 的资金不能 void，只能 refund、冲正或人工处理。
- capture、void 和 refund 必须有幂等键。
- `PAYMENT_UNKNOWN` 不能直接当失败。
- `REFUND_UNKNOWN` 不能重复提交外部退款。
- 退款金额、罚金和补差必须能被原支付、供应商规则和会计分录解释。

### 消息和事件

- Outbox 事件必须和本地事实在同一服务事务中提交。
- 消息消费者必须按业务幂等键去重。
- broker offset 不能证明供应商确认、付款、退款或补偿完成。
- 重复事件只能产生一次业务效果。

### 对账和修复

- 组合订单、子订单、供应商事实、支付单、退款单、罚金、补差、会计分录和 Outbox 消费记录最终必须能解释彼此。
- 差错必须有分类、owner、状态、修复动作和审计记录。
- `reconciliation-service` 不能直接修改订单、供应商、支付、退款或分录历史。
- 修复只能通过领域服务幂等命令、冲正、退款、补差、人工工单或审批完成。

## 常见误区

- 把旅行组合预订设计成严格全有全无。
- 只有组合订单状态，没有子订单状态。
- 把搜索价当最终成交价。
- 供应商超时后直接当失败。
- 机票已出票或保险已生效后用本地字段回滚。
- 附加项失败后取消核心成功行程。
- 已扣款失败后没有退款、罚金、补差或人工处理路径。
- 只对账本地订单，不对账供应商订单、支付、退款和账本。
````

- [ ] **Step 2: Verify invariant keywords**

Run:

```bash
rg -n "CONFIRMED_WITH_ADDON_FAILURES|PARTIALLY_CONFIRMED|SUPPLIER_UNKNOWN|PAYMENT_UNKNOWN|REFUND_UNKNOWN|同一授权只能 capture 或 void 一次|broker offset|不能直接修改" financial-consistency/04-travel-booking-saga/02-invariants.md
```

Expected: output includes all required invariant anchors.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/04-travel-booking-saga/02-invariants.md
git commit -m "docs: define travel booking saga invariants"
```

Expected: commit succeeds and includes only `02-invariants.md`.

## Task 4: Create State Machine Document

**Files:**
- Create: `financial-consistency/04-travel-booking-saga/03-state-machine.md`

- [ ] **Step 1: Add state machine content**

Use `apply_patch` to create `financial-consistency/04-travel-booking-saga/03-state-machine.md`:

````markdown
# 03 状态机

## 设计原则

状态机的任务是防止组合订单、子订单、供应商事实和资金事实互相覆盖。所有状态推进都必须基于耐久事实和合法转换，不能只基于一次 RPC 返回值、回调或消息消费结果。

## 组合订单状态

正常核心成功路径：

```text
QUOTE_SELECTED
-> BOOKING_CREATED
-> PAYMENT_AUTHORIZED
-> CORE_BOOKING_IN_PROGRESS
-> CORE_CONFIRMED
-> CONFIRMED
```

附加项失败路径：

```text
CORE_CONFIRMED
-> ADDON_BOOKING_IN_PROGRESS
-> CONFIRMED_WITH_ADDON_FAILURES
```

部分成功和补偿路径：

```text
CORE_BOOKING_IN_PROGRESS
-> PARTIALLY_CONFIRMED
-> COMPENSATING
-> REFUNDING
-> MANUAL_REVIEW
```

取消路径：

```text
COMPENSATING
-> CANCELLED
```

关键规则：

- 核心项没有全部成功时，组合订单不能进入 `CONFIRMED`。
- 附加项失败不能把核心成功订单改成 `FAILED`。
- `PARTIALLY_CONFIRMED` 必须能解释每个子订单状态和资金状态。
- `MANUAL_REVIEW` 不能直接覆盖供应商事实或资金事实。

## 子订单状态

供应商成功路径：

```text
CREATED
-> QUOTE_LOCKED
-> SUPPLIER_PENDING
-> SUPPLIER_CONFIRMED
-> APPLIED_TO_BOOKING
```

失败、取消和人工状态：

```text
SUPPLIER_UNKNOWN
SUPPLIER_FAILED
CANCEL_REQUESTED
CANCELLED
CANCEL_UNKNOWN
REFUND_REQUIRED
MANUAL_REVIEW
```

关键规则：

- `SUPPLIER_UNKNOWN` 不是失败，不能直接释放资金或取消成终态。
- `SUPPLIER_CONFIRMED` 不能被失败回调覆盖。
- 半不可逆或不可逆子订单失败后只能取消、退款、罚金、补差或人工处理。
- 每个子订单必须记录付款策略和可逆性快照。

## 付款状态

预授权和扣款路径：

```text
PAYMENT_CREATED
-> AUTHORIZED
-> CAPTURE_REQUESTED
-> CAPTURED
```

释放授权路径：

```text
AUTHORIZED
-> VOID_REQUESTED
-> VOIDED
```

退款路径：

```text
CAPTURED
-> REFUND_REQUIRED
-> REFUNDING
-> REFUNDED
```

异常状态：

```text
PAYMENT_UNKNOWN
VOID_UNKNOWN
REFUND_UNKNOWN
MANUAL_REVIEW
```

关键规则：

- 预授权成功不等于扣款成功。
- `CAPTURED` 后不能 `VOIDED`，只能退款、冲正或人工处理。
- capture、void 和 refund 都必须幂等。
- `REFUND_UNKNOWN` 不能重复提交外部退款。

## 人工工单状态

```text
MANUAL_REVIEW_REQUESTED
-> ASSIGNED
-> DECISION_RECORDED
-> REPAIR_REQUESTED
-> REPAIRED
-> VERIFIED
```

关键规则：

- 人工处理不能直接改历史事实。
- 用户决策、运营审批和 maker-checker 必须有审计记录。
- 修复完成后必须重新对账。

## 非法转换示例

| 非法转换 | 原因 |
| --- | --- |
| `SUPPLIER_UNKNOWN -> SUPPLIER_FAILED` | 供应商未知不是失败，必须查询、等待回调、对账或人工处理。 |
| `CORE_BOOKING_IN_PROGRESS -> CONFIRMED` | 核心项未全部成功时不能确认组合订单。 |
| `CORE_CONFIRMED -> FAILED` | 附加项失败不能覆盖核心成功事实。 |
| `SUPPLIER_CONFIRMED -> SUPPLIER_FAILED` | 失败回调不能覆盖已经确认的供应商成功事实。 |
| `CAPTURED -> VOIDED` | 已扣款资金不能释放授权，只能退款、冲正或人工处理。 |
| `REFUND_UNKNOWN -> REFUNDING` | 退款未知不能重复提交外部退款。 |
````

- [ ] **Step 2: Verify state names**

Run:

```bash
rg -n "CONFIRMED_WITH_ADDON_FAILURES|PARTIALLY_CONFIRMED|SUPPLIER_UNKNOWN|SUPPLIER_CONFIRMED|PAYMENT_UNKNOWN|VOID_UNKNOWN|REFUND_UNKNOWN|CAPTURED -> VOIDED|非法转换" financial-consistency/04-travel-booking-saga/03-state-machine.md
```

Expected: output includes required state names and illegal transitions.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/04-travel-booking-saga/03-state-machine.md
git commit -m "docs: define travel booking saga state machines"
```

Expected: commit succeeds and includes only `03-state-machine.md`.

## Task 5: Create Service Boundaries Document

**Files:**
- Create: `financial-consistency/04-travel-booking-saga/04-service-boundaries.md`

- [ ] **Step 1: Add service boundaries content**

Use `apply_patch` to create `financial-consistency/04-travel-booking-saga/04-service-boundaries.md`:

````markdown
# 04 服务边界

## 目标

本文件定义旅行组合预订中的服务职责。核心原则是：组合订单事实、供应商事实、支付事实、退款事实、账本事实、对账事实和人工决策事实分别由明确边界拥有，不能让一个服务偷偷完成所有事情。

## 服务职责

| 服务 | 拥有什么 | 不拥有什么 |
| --- | --- | --- |
| `booking-service` | 组合订单、子订单、组合状态机、用户决策、幂等键 | 不直接确认供应商事实，不直接扣款或退款 |
| `supplier-adapter-service` | 供应商请求、回调、查询、供应商请求号、供应商事实 | 不决定资金入账，不直接改账本 |
| `payment-service` | 预授权、capture、void/release、支付单、支付渠道事实 | 不决定供应商是否确认成功 |
| `refund-service` | 退款单、部分退款、退款查询、退款渠道事实 | 不删除原支付事实，不直接改供应商订单 |
| `ledger-service` | 支付、退款、罚金、补差、冲正和差错修复分录 | 不覆盖历史分录，不替代订单或供应商服务 |
| `reconciliation-service` | 本地订单/供应商/支付/退款/账本对账、差错分类、修复工单 | 不直接修改订单、供应商、支付、退款或分录 |
| `manual-review-service` | 用户决策、运营审批、maker-checker、人工修复审计 | 不绕过状态机，不直接删除历史事实 |
| `message-broker` | Outbox 事件投递和异步解耦 | 不代表业务事实本身 |

## 关键边界

- `booking-service` 是组合订单 owner，但不是供应商事实 owner 或资金事实 owner。
- `supplier-adapter-service` 只记录供应商事实，不直接推进资金账本。
- `payment-service` 和 `refund-service` 只记录资金渠道事实，不改写供应商历史。
- `ledger-service` 只追加分录或冲正分录，不删除历史。
- `reconciliation-service` 发现差异后生成差错单和修复命令，自动修复也必须留下审计证据。
- `manual-review-service` 记录人工决策和审批，不绕过领域服务的幂等命令。

## 典型调用关系

### 创建组合订单

```text
booking-service
-> payment-service
-> message-broker
```

### 核心项预订

```text
booking-service
-> supplier-adapter-service
-> booking-service
-> payment-service
-> ledger-service
-> message-broker
```

### 附加项预订

```text
booking-service
-> supplier-adapter-service
-> refund-service or manual-review-service
-> message-broker
```

### 补偿和人工处理

```text
booking-service
-> refund-service
-> ledger-service
-> manual-review-service
-> message-broker
```

### 对账

```text
reconciliation-service
-> booking-service
-> supplier-adapter-service
-> payment-service
-> refund-service
-> ledger-service
-> manual-review-service
```

## 不接受的设计

- 一个 booking-service 直接调用供应商、扣款、退款并改账本。
- 只保存总订单状态，不保存子订单和供应商事实。
- 把搜索价当最终成交价。
- 供应商超时直接失败。
- 已出票、已确认或已生效动作被本地字段回滚。
- 附加项失败后取消核心成功行程。
- 对账脚本直接改订单、供应商、支付、退款或分录。
- 用消息 offset 作为供应商确认、付款、退款或补偿完成事实。
````

- [ ] **Step 2: Verify service names**

Run:

```bash
rg -n "booking-service|supplier-adapter-service|payment-service|refund-service|ledger-service|reconciliation-service|manual-review-service|message-broker|不接受的设计" financial-consistency/04-travel-booking-saga/04-service-boundaries.md
```

Expected: output includes all service names and rejected design section.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/04-travel-booking-saga/04-service-boundaries.md
git commit -m "docs: define travel booking saga service boundaries"
```

Expected: commit succeeds and includes only `04-service-boundaries.md`.

## Task 6: Create Event Flow Document

**Files:**
- Create: `financial-consistency/04-travel-booking-saga/05-event-flow.md`

- [ ] **Step 1: Add event flow content**

Use `apply_patch` to create `financial-consistency/04-travel-booking-saga/05-event-flow.md`:

````markdown
# 05 事件流

## 目标

事件流用于区分报价事实、组合订单事实、供应商事实、付款事实、退款事实、账本事实、对账事实和人工修复事实。只有明确事实来源，系统才能在供应商超时、核心项部分成功、附加项失败、扣款退款和人工修复交错时恢复。

## 事件分类

| 类型 | 示例 | 事实 owner |
| --- | --- | --- |
| 报价事实 | `QuoteSelected`、`QuoteLocked`、`QuoteExpired`、`PriceChanged` | `booking-service` / supplier |
| 组合订单事实 | `BookingCreated`、`CoreBookingConfirmed`、`AddonFailed`、`BookingPartiallyConfirmed` | `booking-service` |
| 供应商事实 | `FlightTicketed`、`HotelConfirmed`、`CarBooked`、`InsuranceIssued`、`SupplierUnknown` | `supplier-adapter-service` / supplier |
| 付款事实 | `PaymentAuthorized`、`PaymentCaptured`、`AuthorizationVoided`、`PaymentUnknown` | `payment-service` / payment channel |
| 退款事实 | `RefundRequired`、`RefundSubmitted`、`RefundSucceeded`、`RefundUnknown` | `refund-service` / payment channel |
| 账本事实 | `PaymentLedgerPosted`、`RefundLedgerPosted`、`PenaltyPosted`、`AdjustmentPosted` | `ledger-service` |
| 对账事实 | `TravelMismatchDetected`、`TravelRepairRequested` | `reconciliation-service` |
| 人工事实 | `ManualReviewRequested`、`UserDecisionRecorded`、`ManualRepairCompleted` | `manual-review-service` |

## 报价和下单事件流

```text
TravelSearchRequested
-> QuoteSelected
-> QuoteLockRequested
-> QuoteLocked
-> BookingCreateRequested
-> BookingCreated
```

异常分支：

```text
QuoteLockRequested
-> QuoteExpired or PriceChanged
-> UserDecisionRequired or BookingCancelled
```

## 核心项预订事件流

```text
PaymentAuthorized
-> CoreBookingStarted
-> FlightTicketRequested
-> FlightTicketed
-> HotelConfirmRequested
-> HotelConfirmed
-> CoreBookingConfirmed
-> PaymentCaptured
-> PaymentLedgerPosted
```

异常分支：

```text
FlightTicketed
-> HotelConfirmFailed
-> CompensationRequired or ManualReviewRequired
```

## 附加项事件流

```text
CoreBookingConfirmed
-> AddonBookingStarted
-> CarBookingRequested
-> CarBooked or CarBookingFailed
-> InsuranceApplyRequested
-> InsuranceIssued or InsuranceFailed
-> BookingConfirmed or BookingConfirmedWithAddonFailures
```

## 补偿事件流

```text
CompensationRequired
-> SupplierCancelRequested
-> RefundRequired
-> RefundSubmitted
-> RefundSucceeded
-> RefundLedgerPosted
-> CompensationCompleted
```

异常分支：

```text
RefundUnknown
-> refund query or callback
-> RefundSucceeded or RefundFailed or ManualReviewRequired
```

## 人工处理事件流

```text
ManualReviewRequested
-> UserDecisionRecorded
-> ManualRepairRequested
-> ManualRepairCompleted
-> RepairVerified
```

## 对账事件流

匹配终止：

```text
TravelReconciliationStarted
-> booking/supplier/payment/refund/ledger matched
-> Matched
```

差错修复：

```text
TravelMismatchDetected
-> TravelRepairRequested
-> ManualRepairCompleted or AutoRepairCompleted
-> RepairVerified
```

## 顺序依赖

- `BookingCreated` 依赖 `QuoteLocked` 或用户确认后的新报价。
- `CoreBookingConfirmed` 依赖机票和酒店核心项成功。
- `PaymentCaptured` 依赖合法 capture 条件，不能只依赖供应商单个回调。
- `BookingConfirmedWithAddonFailures` 依赖核心成功和附加项失败事实。
- `RefundSubmitted` 依赖 `RefundRequired`。
- `RefundLedgerPosted` 依赖可信的 `RefundSucceeded`。
- `PenaltyPosted` 和 `AdjustmentPosted` 依赖供应商规则、用户确认或人工审批。

## Broker 不是事实来源

Kafka 或其他消息系统只负责投递语义。业务事实必须来自本地数据库记录、供应商事实、支付渠道事实、退款渠道事实、会计分录、人工审批和对账记录，不能用 consumer offset 证明供应商确认、付款、退款或补偿已经完成。
````

- [ ] **Step 2: Verify event names**

Run:

```bash
rg -n "QuoteLocked|BookingCreated|FlightTicketed|HotelConfirmed|PaymentCaptured|CarBooked|InsuranceIssued|RefundSucceeded|ManualReviewRequested|TravelMismatchDetected|Broker 不是事实来源" financial-consistency/04-travel-booking-saga/05-event-flow.md
```

Expected: output includes required event names and broker warning.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/04-travel-booking-saga/05-event-flow.md
git commit -m "docs: define travel booking saga event flow"
```

Expected: commit succeeds and includes only `05-event-flow.md`.

## Task 7: Create Failure Matrix Document

**Files:**
- Create: `financial-consistency/04-travel-booking-saga/06-failure-matrix.md`

- [ ] **Step 1: Add failure matrix content**

Use `apply_patch` to create `financial-consistency/04-travel-booking-saga/06-failure-matrix.md`:

````markdown
# 06 失败矩阵

## 目标

失败矩阵把每个危险点映射到已知事实、系统状态和恢复动作。旅行组合 Saga 的关键是：先确认供应商事实和资金事实，再决定释放授权、取消供应商保留、退款、罚金、补差、替代供应商或人工处理。

| 失败点 | 已知事实 | 系统状态 | 处理策略 |
| --- | --- | --- | --- |
| 报价过期但用户继续提交 | 报价有效期已过 | `QUOTE_EXPIRED` | 重新报价或等待用户确认新价格，不能按旧价扣款。 |
| 预授权成功但机票锁座失败 | 授权存在，机票未锁定 | `PAYMENT_AUTHORIZED` + `SUPPLIER_FAILED` | 释放授权；允许重新选择航班或取消组合订单。 |
| 机票已出票但酒店确认失败 | 机票成功，酒店失败 | `PARTIALLY_CONFIRMED` | 尝试替代酒店；无法替代时计算退票规则、罚金和退款，进入人工处理。 |
| 酒店已确认但机票出票失败 | 酒店成功，机票失败 | `PARTIALLY_CONFIRMED` | 尝试替代航班；无法替代时取消酒店、计算罚金或人工处理。 |
| 供应商请求超时或未知 | 有供应商请求号，没有确定结果 | `SUPPLIER_UNKNOWN` | 查询、等待回调、供应商账单或人工处理，不能直接失败。 |
| capture 成功但供应商确认失败 | 已扣款，核心项未成功 | `CAPTURED` + core failed | 退款、罚金、补差或人工处理，不能只改本地订单为失败。 |
| 核心项部分成功后用户取消 | 至少一个核心项成功 | `PARTIALLY_CONFIRMED` + cancel intent | 记录取消意图，按成功子订单规则取消、退款、收罚金或人工处理。 |
| 租车失败但核心行程成功 | 机票酒店成功，租车失败 | `CONFIRMED_WITH_ADDON_FAILURES` | 保留核心成功，退款租车或替代供应商。 |
| 保险投保失败或未知 | 核心成功，保险未成功 | addon failed or unknown | 保留核心成功，退款保险、提示未投保、查询或人工处理。 |
| 保险已生效后收到失败回调 | 已有可信保险成功事实 | stale callback | 记录审计，不覆盖保险成功；必要时人工核验。 |
| void/release 授权失败 | 授权仍可能占用 | `VOID_UNKNOWN` | 查询支付渠道；不能重复创建新授权；必要时人工处理。 |
| 退款提交超时或未知 | 有退款请求号，没有确定结果 | `REFUND_UNKNOWN` | 查询、等待回调或退款账单；不能重复提交外部退款。 |
| 罚金或补差分录缺失 | 供应商规则产生罚金或补差 | ledger missing | 补罚金或补差分录，保留供应商规则和审批证据。 |
| Outbox 事件发布失败 | 本地事实已提交，事件未发布 | outbox pending | 重试发布，不重做供应商、支付或退款动作。 |
| 消费者重复消费 | 消息重复投递 | consumer dedup | 使用业务幂等键和唯一约束去重。 |
| 人工修复失败或重复提交 | 修复工单存在 | repair pending or duplicate | 使用修复幂等键，保留审批和审计记录。 |
| 对账发现供应商、支付或本地订单不一致 | 对账发现差异 | `TravelMismatchDetected` | 分类差错，进入修复工作流。 |

## 决策规则

- 供应商、付款或退款结果未知时，只能查询、等待回调、对账或人工处理，不能直接失败。
- 核心项失败时，必须检查另一核心项是否已经成功或不可逆。
- 附加项失败时，默认保留核心成功，处理附加退款、替代或人工流程。
- 已 capture 资金不能 void，只能退款、冲正或人工处理。
- 已发生的供应商、支付、退款、罚金、补差和分录事实不能删除，只能用追加事实解释。
````

- [ ] **Step 2: Verify failure cases**

Run:

```bash
rg -n "报价过期|预授权成功但机票锁座失败|机票已出票但酒店确认失败|SUPPLIER_UNKNOWN|CONFIRMED_WITH_ADDON_FAILURES|REFUND_UNKNOWN|罚金或补差|Outbox|人工修复" financial-consistency/04-travel-booking-saga/06-failure-matrix.md
```

Expected: output includes required failure categories.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/04-travel-booking-saga/06-failure-matrix.md
git commit -m "docs: define travel booking saga failure matrix"
```

Expected: commit succeeds and includes only `06-failure-matrix.md`.

## Task 8: Create Reconciliation Document

**Files:**
- Create: `financial-consistency/04-travel-booking-saga/07-reconciliation.md`

- [ ] **Step 1: Add reconciliation content**

Use `apply_patch` to create `financial-consistency/04-travel-booking-saga/07-reconciliation.md`:

````markdown
# 07 对账设计

## 为什么本阶段必须讲对账

旅行组合预订里，组合订单、子订单、供应商订单、支付、退款、罚金、补差和账本都可能因为供应商超时、回调、用户取消、人工处理或故障恢复而分叉。对账不是后期报表，而是发现旅行组合事实不一致的核心链路。

## 对账类型

| 类型 | 关注点 | 主要输入 |
| --- | --- | --- |
| 组合订单对账 | 组合状态能否解释所有子订单状态 | 组合订单、子订单、用户决策、人工工单 |
| 供应商对账 | 本地子订单和供应商出票、酒店确认、租车确认、保险生效是否一致 | 子订单、供应商请求、供应商回调、供应商账单 |
| 支付对账 | 预授权、capture、void、refund 和支付渠道账单是否一致 | 支付单、退款单、渠道账单、组合订单 |
| 账本对账 | 支付、退款、罚金、补差和冲正分录能否解释业务状态 | 支付单、退款单、供应商规则、会计分录 |
| 事件对账 | Outbox 事件和消费者处理记录是否覆盖本地事实 | Outbox、消费记录、本地事实表 |

## 差错分类

| 差错 | 含义 | owner | 修复方向 |
| --- | --- | --- | --- |
| 本地核心成功但供应商缺失 | 本地显示机票或酒店成功，供应商没有订单 | booking-service、supplier-adapter-service、manual review | 查询供应商；无法确认时补偿、退款或人工处理 |
| 供应商确认但本地未推进 | 供应商已出票或确认，本地子订单未成功 | supplier-adapter-service、booking-service | 补供应商事实和子订单状态，补事件 |
| 预授权长期未处理 | 授权存在但未 capture 或 void | payment-service、reconciliation-service | 查询支付渠道，capture、void 或人工处理 |
| 用户已扣款但核心失败未退款 | capture 成功，核心项失败 | refund-service、ledger-service、manual review | 创建退款、罚金或补差流程，补分录 |
| 附加项失败已退款但组合状态完整成功 | 附加失败事实存在，组合订单仍 `CONFIRMED` | booking-service、refund-service | 补附加失败状态和事件 |
| 保险生效状态不一致 | 本地和供应商对保险生效事实不一致 | supplier-adapter-service、manual review | 查询保险供应商，补生效、取消或人工处理事实 |
| 罚金或补差分录缺失 | 供应商规则产生费用，但账本没有解释 | ledger-service | 补罚金、补差或冲正分录 |
| Outbox 事件缺失 | 本地事实存在，但下游事件缺失 | event repair | 补发缺失 Outbox 事实 |
| 人工修复无审计 | 订单状态变化来自人工，但没有审批记录 | manual-review-service | 补审计记录，必要时重新复核 |
| 长时间未知状态 | 供应商、付款或退款状态长期无法收敛 | reconciliation-service、manual review | 查询、账单核验、人工复核 |

## 修复路由

`reconciliation-service` 只负责分类、记录差错状态、创建修复命令或工单，并写入审计记录；它不直接修改组合订单、子订单、供应商、支付、退款或会计分录。

- `booking-service`：通过幂等命令补组合订单或子订单状态。
- `supplier-adapter-service`：补供应商事实、查询供应商或标记供应商差错。
- `payment-service`：补授权、capture、void 状态或查询支付渠道。
- `refund-service`：补退款状态、查询退款事实或创建退款修复任务。
- `ledger-service`：追加支付、退款、罚金、补差或冲正分录。
- `manual-review-service`：处理不可逆动作、用户决策、罚金争议、供应商账单缺失等高风险差错。
- `event repair`：补发缺失的 Outbox 事实，保证下游消费记录可追溯。

## 对账输入

- 组合订单和子订单状态历史。
- 报价快照、价格变动和用户确认记录。
- 供应商请求、回调、查询结果和供应商账单。
- 支付单、授权、capture、void、退款单和支付渠道账单。
- 罚金、补差、冲正和会计分录。
- Outbox 事件和消费记录。
- 人工工单、审批和复核记录。

## 修复原则

- 不直接覆盖组合订单、子订单、供应商、支付、退款或分录历史。
- 修复动作必须有幂等键。
- 自动修复必须留下审计记录。
- 高风险修复需要 maker-checker 或人工复核。
- 修复完成后必须重新对账。

## 对账输出

- `MATCHED`：组合订单、供应商、支付、退款和账本事实一致。
- `MISMATCH_DETECTED`：发现差错。
- `REPAIR_REQUESTED`：已生成修复动作。
- `REPAIRED`：修复动作完成。
- `VERIFIED`：修复后复核通过。
````

- [ ] **Step 2: Verify reconciliation categories**

Run:

```bash
rg -n "组合订单对账|供应商对账|支付对账|本地核心成功但供应商缺失|供应商确认但本地未推进|用户已扣款但核心失败未退款|罚金或补差分录缺失|修复路由|不直接修改" financial-consistency/04-travel-booking-saga/07-reconciliation.md
```

Expected: output includes required reconciliation categories and repair routing.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/04-travel-booking-saga/07-reconciliation.md
git commit -m "docs: define travel booking saga reconciliation"
```

Expected: commit succeeds and includes only `07-reconciliation.md`.

## Task 9: Create Verification Plan Document

**Files:**
- Create: `financial-consistency/04-travel-booking-saga/08-verification-plan.md`

- [ ] **Step 1: Add verification content**

Use `apply_patch` to create `financial-consistency/04-travel-booking-saga/08-verification-plan.md`:

````markdown
# 08 验证路线

## 目标

验证路线要证明设计能暴露旅行组合预订中最危险的问题：报价过期扣款、核心项部分成功、供应商未知误判失败、附加项失败拖垮核心成功、重复 capture、重复退款、不可逆动作被回滚、罚金补差缺失和对账差错。

## 模型验证

需要建模的规则：

- 核心项未全部成功时，组合订单不能 `CONFIRMED`。
- 附加项失败不能取消核心成功事实。
- `SUPPLIER_UNKNOWN`、`PAYMENT_UNKNOWN`、`REFUND_UNKNOWN` 不能被直接当失败。
- `CAPTURED` 后不能 `VOIDED`。
- 供应商成功事实不能被失败回调覆盖。
- 补偿不能删除历史事实。
- 人工修复必须进入审计和复核状态。

## 属性测试

随机生成这些序列：

- 报价锁定、报价过期、价格变动和用户确认。
- 组合订单创建和重复创建。
- 机票成功、失败、超时、未知和重复回调。
- 酒店成功、失败、超时、未知和重复回调。
- 租车失败、保险失败、保险成功后失败回调。
- 预授权、capture、void、退款、罚金和补差。
- 用户取消、系统补偿和人工修复。
- Outbox 重复投递和消费者重复消费。

检查属性：

- 同一幂等键最多一个组合订单。
- 每个组合订单都有可解释的子订单集合。
- 核心项未全部成功时组合订单不能 `CONFIRMED`。
- 附加项失败不能把核心成功订单改成失败。
- 搜索价不能在报价过期后直接扣款。
- `SUPPLIER_UNKNOWN` 不能触发终态失败。
- 同一授权不能既 capture 又 void。
- 已 capture 资金不能 void。
- `REFUND_UNKNOWN` 不能触发第二次外部退款。
- 罚金、补差和退款金额必须能被供应商规则和原支付解释。
- 终态不被非法覆盖。

## 集成测试

使用真实数据库语义验证：

- 组合订单幂等唯一约束。
- 子订单幂等唯一约束。
- 供应商请求号唯一约束。
- 支付单、授权、capture、void 和退款幂等约束。
- 状态转换必须通过版本号或条件更新拒绝非法并发推进。
- 本地事务和 Outbox 同提交。
- supplier callback/query dedup。
- payment/refund callback dedup。
- 核心项部分成功后的补偿路径。
- 附加项失败后的保留核心成功路径。
- 人工修复审批和审计记录。

## 故障注入

必须注入：

- 报价过期后提交订单。
- 预授权成功后机票锁座失败。
- 机票出票成功后酒店确认失败。
- 酒店确认成功后机票出票失败。
- 供应商请求超时但稍后成功。
- capture 成功但本地订单未推进。
- capture 成功但核心项失败。
- 租车失败但核心行程成功。
- 保险投保未知。
- 保险成功后收到失败回调。
- void/release 授权失败。
- 退款提交超时。
- 罚金或补差分录缺失。
- Outbox 发布失败。
- 消费者崩溃和重复消费。
- 人工修复失败和重复提交。
- 对账账单缺失或金额不一致。

## 历史检查

记录所有用户命令、报价快照、组合订单状态、子订单状态、供应商事实、付款事实、退款事实、罚金、补差、会计分录、Outbox 事件、人工工单和对账结果。检查最终历史是否满足：

- 每个组合订单状态转换合法。
- 每个子订单最终成功、失败、取消、退款或人工处理。
- 每个供应商成功事实有本地子订单状态对应。
- 每个 capture 有明确供应商成功、退款、罚金、补差或人工处理路径。
- 每个退款成功有订单状态和退款分录。
- 每个幂等键最多一个业务效果。
- 每个差错都有分类、owner、修复动作和审计记录。

## 对账验证

构造账单和本地状态覆盖：

- 本地核心成功，但供应商缺少机票或酒店确认。
- 供应商确认成功，但本地组合订单未推进。
- 预授权长期未 capture 或 void。
- 用户已扣款，但核心项失败后未退款。
- 附加项失败已退款，但组合订单没有附加失败状态。
- 保险生效状态不一致。
- 罚金或补差分录缺失。
- Outbox 事件缺失或重复。
- 人工修复无审计。
- 长时间未知状态。

每类差错都必须生成稳定差错分类、owner、修复动作和审计证据。修复不能覆盖历史事实，修复完成后必须重新对账。
````

- [ ] **Step 2: Verify verification methods**

Run:

```bash
rg -n "模型验证|属性测试|集成测试|故障注入|历史检查|对账验证|SUPPLIER_UNKNOWN|PAYMENT_UNKNOWN|REFUND_UNKNOWN|CAPTURED|同一授权不能既 capture 又 void|罚金、补差" financial-consistency/04-travel-booking-saga/08-verification-plan.md
```

Expected: output includes all verification methods and critical properties.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/04-travel-booking-saga/08-verification-plan.md
git commit -m "docs: define travel booking saga verification"
```

Expected: commit succeeds and includes only `08-verification-plan.md`.

## Task 10: Create Interview Synthesis Document

**Files:**
- Create: `financial-consistency/04-travel-booking-saga/09-interview-synthesis.md`

- [ ] **Step 1: Add interview content**

Use `apply_patch` to create `financial-consistency/04-travel-booking-saga/09-interview-synthesis.md`:

````markdown
# 09 面试与架构评审表达

## 一句话回答

旅行组合预订不能靠一个大事务保证一致性。机票、酒店、租车、保险来自不同供应商，动作可逆性和付款策略不同。系统必须把核心项和附加项分层，用 Saga 编排供应商动作，用状态机记录每个子订单事实，用付款策略决定预授权、扣款、释放授权和退款，用对账和人工处理收敛不可逆或未知状态。

## 标准回答结构

1. 先说明旅行组合订单由多个外部供应商事实组成。
2. 再说明机票和酒店是核心项，租车和保险是附加项。
3. 再说明付款策略必须按子产品建模。
4. 再说明补偿不是回滚，而是取消、退款、罚金、补差、替代供应商或人工处理。
5. 再说明 Saga 负责长流程编排，但事实仍由状态机、幂等和对账保证。
6. 最后说明如何验证：模型验证、属性测试、故障注入、历史检查和对账验证。

## 高频问题

### 为什么旅行组合不能严格全有全无？

外部供应商不参与我们的数据库事务，而且机票出票、不可退酒店、保险生效等动作可能不可逆或有罚金。失败后不能假装回滚，只能追加取消、退款、罚金、补差或人工处理事实。

### 机票已出票但酒店失败怎么办？

这是核心项部分成功。系统应先确认机票事实和酒店失败事实，再尝试替代酒店；无法替代时按机票退改规则计算退款、罚金或补差，并进入人工处理或用户决策。

### 核心成功但租车或保险失败怎么办？

租车和保险是附加项。附加项失败不取消机票酒店，组合订单进入 `CONFIRMED_WITH_ADDON_FAILURES`，并对失败附加项退款、替代供应商、提示用户或进入人工处理。

### 预授权、capture、void 和 refund 分别解决什么？

预授权先冻结可支付能力；capture 是最终扣款；void/release 是释放未扣款授权；refund 是对已扣款资金退款。已 capture 的资金不能 void，只能 refund、冲正或人工处理。

### 供应商超时能不能当失败？

不能。供应商超时或未知必须进入 `SUPPLIER_UNKNOWN`，后续通过查询、回调、供应商账单或人工复核收敛。在可信失败事实出现前不能直接取消成终态或释放全部资金。

### 不可退酒店或已生效保险怎么补偿？

不能通过本地字段删除历史。必须记录不可退、罚金、保险生效、取消、作废、退款或人工处理事实，并让账本分录和供应商规则解释最终金额。

### Temporal 在这里解决什么？

Temporal 适合承接长流程 Saga、定时查询、超时、重试和人工处理入口。它不替代供应商事实记录、子订单状态机、付款和退款幂等、Outbox、会计分录或对账。

## 评审底线

- 不接受只用总订单成功/失败表达组合状态。
- 不接受把搜索价当最终成交价。
- 不接受供应商超时直接失败。
- 不接受不可逆动作被本地字段回滚掩盖。
- 不接受已扣款失败后没有退款、罚金、补差或人工处理路径。
- 不接受附加项失败拖垮核心成功行程。
- 不接受没有供应商、支付、退款、账本和本地订单对账。
````

- [ ] **Step 2: Verify interview questions**

Run:

```bash
rg -n "为什么旅行组合不能严格全有全无|机票已出票但酒店失败|核心成功但租车或保险失败|预授权、capture、void 和 refund|供应商超时能不能当失败|不可退酒店或已生效保险|Temporal" financial-consistency/04-travel-booking-saga/09-interview-synthesis.md
```

Expected: output includes all interview questions.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/04-travel-booking-saga/09-interview-synthesis.md
git commit -m "docs: add travel booking saga interview synthesis"
```

Expected: commit succeeds and includes only `09-interview-synthesis.md`.

## Task 11: Update Root README

**Files:**
- Modify: `financial-consistency/README.md`

- [ ] **Step 1: Add design spec link**

In `financial-consistency/README.md`, add this line to the formal design document list after the order payment inventory design link:

```markdown
- [2026-05-02-travel-booking-saga-design.md](../docs/superpowers/specs/2026-05-02-travel-booking-saga-design.md)
```

- [ ] **Step 2: Link phase 04 route**

Change:

```markdown
- 04-travel-booking-saga
  机票、酒店、租车、保险组合预订，处理外部系统不可控和不可逆动作。
```

to:

```markdown
- [04-travel-booking-saga](./04-travel-booking-saga/README.md)
  机票、酒店、租车、保险组合预订，处理外部系统不可控和不可逆动作。
```

- [ ] **Step 3: Verify root README links**

Run:

```bash
rg -n "2026-05-02-travel-booking-saga-design.md|\./04-travel-booking-saga/README.md" financial-consistency/README.md
```

Expected: output includes both links.

- [ ] **Step 4: Commit**

Run:

```bash
git add financial-consistency/README.md
git commit -m "docs: link travel booking saga phase"
```

Expected: commit succeeds and includes only `financial-consistency/README.md`.

## Task 12: Final Documentation Verification

**Files:**
- Verify: `financial-consistency/04-travel-booking-saga/**`
- Verify: `financial-consistency/README.md`

- [ ] **Step 1: Verify all phase files exist**

Run:

```bash
find financial-consistency/04-travel-booking-saga -maxdepth 1 -type f | sort
```

Expected output:

```text
financial-consistency/04-travel-booking-saga/01-scenario-cards.md
financial-consistency/04-travel-booking-saga/02-invariants.md
financial-consistency/04-travel-booking-saga/03-state-machine.md
financial-consistency/04-travel-booking-saga/04-service-boundaries.md
financial-consistency/04-travel-booking-saga/05-event-flow.md
financial-consistency/04-travel-booking-saga/06-failure-matrix.md
financial-consistency/04-travel-booking-saga/07-reconciliation.md
financial-consistency/04-travel-booking-saga/08-verification-plan.md
financial-consistency/04-travel-booking-saga/09-interview-synthesis.md
financial-consistency/04-travel-booking-saga/README.md
```

- [ ] **Step 2: Verify README child links**

Run:

```bash
rg -n "\./01-scenario-cards.md|\./02-invariants.md|\./03-state-machine.md|\./04-service-boundaries.md|\./05-event-flow.md|\./06-failure-matrix.md|\./07-reconciliation.md|\./08-verification-plan.md|\./09-interview-synthesis.md" financial-consistency/04-travel-booking-saga/README.md
```

Expected: output includes all 9 child document links.

- [ ] **Step 3: Verify core scenario coverage**

Run:

```bash
rg -n "搜索报价、锁价和报价过期|创建组合订单和子订单|预授权、扣款、释放授权和退款|机票出票和酒店确认的核心 Saga|租车和保险附加项处理|核心失败、附加失败、部分成功和人工处理|供应商、支付、退款、罚金、补差和本地订单对账" financial-consistency/04-travel-booking-saga/01-scenario-cards.md
```

Expected: output includes all 7 scenario names.

- [ ] **Step 4: Verify main technical anchors**

Run:

```bash
rg -n "核心项|附加项|PRE_AUTH_THEN_CAPTURE|IMMEDIATE_CAPTURE_REQUIRED|SUPPLIER_UNKNOWN|PAYMENT_UNKNOWN|REFUND_UNKNOWN|CONFIRMED_WITH_ADDON_FAILURES|PARTIALLY_CONFIRMED|Outbox|罚金|补差|Temporal|对账" financial-consistency/04-travel-booking-saga
```

Expected: output includes the core terms across the phase docs.

- [ ] **Step 5: Verify root README link**

Run:

```bash
rg -n "2026-05-02-travel-booking-saga-design.md|\./04-travel-booking-saga/README.md" financial-consistency/README.md
```

Expected: output includes both root README links.

- [ ] **Step 6: Verify previous phases were not changed in this phase**

Run:

```bash
git diff --name-only main..HEAD -- financial-consistency/01-transfer financial-consistency/02-payment-recharge-withdraw financial-consistency/03-order-payment-inventory
```

Expected: no output.

- [ ] **Step 7: Scan for incomplete-document markers**

Run:

```bash
rg -n "TO[D]O|TB[D]|待[定]|占[位]|以[后]补|未[决]|大[概]|随[便]" financial-consistency/04-travel-booking-saga financial-consistency/README.md
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

Expected: no tracked file modifications related to this phase. Existing unrelated untracked files outside this phase may remain and must not be added to phase commits.
