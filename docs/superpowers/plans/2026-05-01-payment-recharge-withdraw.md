# Payment Recharge Withdraw Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `02-payment-recharge-withdraw` learning module for external payment channels, covering recharge, withdraw, callbacks, unknown channel states, reconciliation, and verification.

**Architecture:** This is a documentation-only phase that mirrors the structure of `01-transfer` while adding external-channel uncertainty. Each file owns one concept: scenario cards, invariants, state machines, service boundaries, event flow, failure matrix, reconciliation, verification, and interview synthesis. The root README will link the new phase and its design spec.

**Tech Stack:** Markdown, Git, `rg`, `find`, `git diff --check`.

---

## File Structure

- Create directory: `financial-consistency/02-payment-recharge-withdraw/`
- Create: `financial-consistency/02-payment-recharge-withdraw/README.md`
- Create: `financial-consistency/02-payment-recharge-withdraw/01-scenario-cards.md`
- Create: `financial-consistency/02-payment-recharge-withdraw/02-invariants.md`
- Create: `financial-consistency/02-payment-recharge-withdraw/03-state-machine.md`
- Create: `financial-consistency/02-payment-recharge-withdraw/04-service-boundaries.md`
- Create: `financial-consistency/02-payment-recharge-withdraw/05-event-flow.md`
- Create: `financial-consistency/02-payment-recharge-withdraw/06-failure-matrix.md`
- Create: `financial-consistency/02-payment-recharge-withdraw/07-reconciliation.md`
- Create: `financial-consistency/02-payment-recharge-withdraw/08-verification-plan.md`
- Create: `financial-consistency/02-payment-recharge-withdraw/09-interview-synthesis.md`
- Modify: `financial-consistency/README.md`

Do not modify `financial-consistency/01-transfer/**`.

## Task 1: Create Phase README

**Files:**
- Create: `financial-consistency/02-payment-recharge-withdraw/README.md`

- [ ] **Step 1: Create directory**

Run:

```bash
mkdir -p financial-consistency/02-payment-recharge-withdraw
```

Expected: command succeeds.

- [ ] **Step 2: Add README content**

Use `apply_patch` to create `financial-consistency/02-payment-recharge-withdraw/README.md`:

````markdown
# 02 支付、充值、提现与外部渠道一致性

## 目标

这一阶段把学习主线从内部转账推进到外部支付渠道。核心不是接一个支付 API，而是理解外部系统不参与我们的数据库事务时，如何处理充值、提现、支付回调、渠道超时、未知状态、查询补偿、渠道对账和人工修复。

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

- 为什么接口超时不能直接当失败？
- 为什么回调不是唯一事实来源？
- 为什么查询补偿和渠道对账是状态收敛手段？
- 为什么充值成功必须最终落到账户流水和会计分录？
- 为什么提现必须先冻结资金，再等待外部出款事实？
- 渠道成功、本地失败如何补账？
- 本地成功、渠道失败如何冲正或人工处理？
- 为什么不能只靠接口返回值判断资金状态？
- 渠道对账和账本对账分别解决什么问题？

## 本阶段范围

第一版覆盖 5 个核心场景：

- 充值。
- 提现。
- 支付回调。
- 外部渠道超时或未知状态。
- 渠道对账。

这个范围故意不包含预授权、ACH、订阅扣费、商户分账、日终批量出款和贷款还款。那些场景已经放入 `00-scenario-matrix.md` 的高价值扩展区，后续可单独展开。

## 最小闭环

```text
本地订单
-> 外部渠道请求
-> 回调或查询补偿
-> 账户流水
-> 会计分录
-> Outbox 事件
-> 渠道对账
-> 差错修复
```

## 本阶段结论

外部渠道不参与我们的事务，因此系统不能把 RPC 返回值当作最终事实。金融级实现必须把本地状态机、渠道事实、账户流水、会计分录、Outbox 事件、查询补偿、对账和人工修复组合起来，才能把未知状态收敛到可解释、可审计、可修复的终态。
````

- [ ] **Step 3: Verify README links**

Run:

```bash
rg -n "\./01-scenario-cards.md|\./02-invariants.md|\./03-state-machine.md|\./04-service-boundaries.md|\./05-event-flow.md|\./06-failure-matrix.md|\./07-reconciliation.md|\./08-verification-plan.md|\./09-interview-synthesis.md" financial-consistency/02-payment-recharge-withdraw/README.md
```

Expected: output includes all 9 linked child documents.

- [ ] **Step 4: Commit**

Run:

```bash
git add financial-consistency/02-payment-recharge-withdraw/README.md
git commit -m "docs: add payment channel module entry"
```

Expected: commit succeeds and includes only `financial-consistency/02-payment-recharge-withdraw/README.md`.

## Task 2: Create Scenario Cards

**Files:**
- Create: `financial-consistency/02-payment-recharge-withdraw/01-scenario-cards.md`

- [ ] **Step 1: Add scenario cards content**

Use `apply_patch` to create `financial-consistency/02-payment-recharge-withdraw/01-scenario-cards.md`:

````markdown
# 01 场景卡

## 目的

本文件先定义业务边界，再讨论一致性方案。每张场景卡都回答：链路从哪里开始，成功目标是什么，哪些事实必须持久化，哪些失败最危险。

## 充值

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 用户发起充值；系统创建充值单并调用支付渠道；渠道确认成功后，本地给账户入账并生成会计分录；充值最终进入成功、失败、未知或人工处理状态。 |
| 参与方 | 用户、payment-service、channel-adapter、account-service、ledger-service、reconciliation-service、message-broker。 |
| 核心状态机 | `CREATED -> CHANNEL_PENDING -> CHANNEL_UNKNOWN -> CHANNEL_SUCCEEDED -> ACCOUNT_CREDITED -> LEDGER_POSTED -> SUCCEEDED`。 |
| 正确性不变量 | 同一充值单不能重复入账；成功充值必须同时有渠道成功事实、账户入账流水和贷记分录。 |
| 关键命令和事件 | `RechargeRequested`、`ChannelPaymentInitiated`、`ChannelPaymentSucceeded`、`RechargeAccountCredited`、`RechargeLedgerPosted`。 |
| 耐久事实 | 充值单、渠道请求号、渠道交易号、账户流水、会计分录、Outbox 事件。 |
| 最危险失败点 | 渠道成功但本地入账失败；回调重复导致重复入账；查询成功和回调成功同时到达；本地状态成功但渠道账单不存在。 |
| 补偿方式 | 未入账时补入账；已重复入账时冲正；渠道缺失时进入差错处理；无法自动判断时进入人工复核。 |
| 对账来源 | 渠道账单、本地充值单、账户流水、会计分录、Outbox 消费记录。 |
| 验证方式 | 幂等测试、重复回调测试、渠道超时故障注入、渠道账单差错构造、账户和账本交叉对账。 |

## 提现

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 用户发起提现；系统冻结用户可用余额；系统提交出款请求到银行或出款渠道；渠道成功后消耗冻结并记账；渠道失败后释放冻结。 |
| 参与方 | 用户、payment-service、risk-service、channel-adapter、account-service、ledger-service、reconciliation-service。 |
| 核心状态机 | `CREATED -> RISK_APPROVED -> FUNDS_RESERVED -> PAYOUT_SUBMITTED -> PAYOUT_UNKNOWN -> PAYOUT_SUCCEEDED -> FREEZE_CONSUMED -> LEDGER_POSTED -> SUCCEEDED`。 |
| 正确性不变量 | 同一提现单不能重复出款；提现成功必须消耗冻结；提现失败必须释放冻结；不能既释放冻结又确认出款成功。 |
| 关键命令和事件 | `WithdrawRequested`、`WithdrawRiskApproved`、`WithdrawFundsReserved`、`PayoutSubmitted`、`PayoutSucceeded`、`WithdrawFreezeConsumed`、`WithdrawLedgerPosted`。 |
| 耐久事实 | 提现单、风控结果、冻结记录、渠道出款请求号、渠道出款流水、冻结消耗流水、借记分录。 |
| 最危险失败点 | 出款请求超时但渠道实际成功；重试造成重复出款；冻结金额长期悬挂；银行成功但本地状态未推进。 |
| 补偿方式 | 渠道失败释放冻结；渠道成功但本地未推进时补消耗冻结和分录；重复出款进入人工追回或反向入账；长期未知进入人工复核。 |
| 对账来源 | 银行出款文件、提现单、冻结流水、账户流水、会计分录、差错单。 |
| 验证方式 | 重复提交测试、渠道未知状态模型检查、冻结最终态扫描、出款账单对账。 |

## 支付回调

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 渠道异步通知支付、充值或提现结果；系统验签、幂等识别、状态推进和事件发布；回调只能推进到合法状态，不能覆盖更可信的终态。 |
| 参与方 | channel-adapter、payment-service、account-service、ledger-service、message-broker。 |
| 核心状态机 | `RECEIVED -> VERIFIED -> DEDUPED -> APPLIED`，异常进入 `SIGNATURE_INVALID`、`DUPLICATE`、`STALE`、`CONFLICT`、`IGNORED` 或 `MANUAL_REVIEW`。 |
| 正确性不变量 | 重复回调只有一次业务效果；验签失败不能改变业务状态；失败回调不能覆盖已经确认的成功终态。 |
| 关键命令和事件 | `PaymentCallbackReceived`、`PaymentCallbackVerified`、`PaymentCallbackApplied`。 |
| 耐久事实 | 回调原文、验签结果、回调幂等记录、状态推进记录、Outbox 事件。 |
| 最危险失败点 | 回调重复、乱序、伪造、延迟；查询结果和回调结果冲突。 |
| 补偿方式 | 重复回调直接返回已处理结果；乱序回调按状态机忽略或进入冲突处理；伪造回调拒绝并审计；冲突事实进入人工复核。 |
| 对账来源 | 回调记录、渠道查询结果、渠道账单、本地订单状态、账户流水、会计分录。 |
| 验证方式 | 重复回调故障注入、乱序回调模型测试、验签失败测试、终态覆盖保护测试。 |

## 外部渠道超时或未知状态

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 本地向渠道发起请求；请求没有返回确定结果；系统进入 `UNKNOWN` 或等价状态；后续通过查询、回调、渠道账单或人工处理收敛。 |
| 参与方 | payment-service、channel-adapter、reconciliation-service、运营人员。 |
| 核心状态机 | `CHANNEL_PENDING -> CHANNEL_UNKNOWN -> CHANNEL_SUCCEEDED` 或 `CHANNEL_FAILED`，长时间无法收敛进入 `MANUAL_REVIEW`。 |
| 正确性不变量 | `UNKNOWN` 不是失败；未知状态不能直接释放、退款或重复提交外部动作；重复查询不能产生新的渠道交易。 |
| 关键命令和事件 | `ChannelPaymentUnknown`、`PayoutUnknown`、渠道查询命令、查询结果事实、人工复核事件。 |
| 耐久事实 | 渠道请求号、本地请求状态、查询请求、查询结果、回调事实、人工处理记录。 |
| 最危险失败点 | 把超时当失败；未知状态下重复提交外部请求；未知状态长期悬挂；查询结果和回调结果冲突。 |
| 补偿方式 | 定时查询补偿；根据渠道事实推进状态；长期未知升级人工复核；冲突事实进入差错单。 |
| 对账来源 | 渠道查询结果、渠道账单、本地订单、回调记录、差错单。 |
| 验证方式 | 超时故障注入、重复查询测试、未知状态 aging 扫描、查询回调冲突测试。 |

## 渠道对账

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 系统导入渠道账单；对比本地订单、账户流水、会计分录和渠道流水；识别本地多记、本地少记、渠道多记、渠道少记、金额不一致和状态不一致；生成差错单和修复路径。 |
| 参与方 | reconciliation-service、payment-service、account-service、ledger-service、channel-adapter、运营人员。 |
| 核心状态机 | `STATEMENT_IMPORTED -> MATCHED` 或 `MISMATCH_DETECTED -> REPAIR_REQUESTED -> REPAIRED -> VERIFIED`。 |
| 正确性不变量 | 对账差异必须有分类、owner、修复动作和审计记录；修复不能直接覆盖历史事实。 |
| 关键命令和事件 | `ChannelStatementImported`、`ChannelMismatchDetected`、`ChannelRepairRequested`、`ManualRepairCompleted`。 |
| 耐久事实 | 渠道账单、匹配结果、差错单、修复动作、复核记录。 |
| 最危险失败点 | 只比较订单状态，不比较账户流水和分录；差错修复直接改历史记录；发现问题但没有 owner、状态和审计链。 |
| 补偿方式 | 补流水、补分录、冲正、补事件、人工复核和客户赔付。 |
| 对账来源 | 渠道账单、本地订单、账户流水、会计分录、Outbox 消费记录。 |
| 验证方式 | 构造差异账单、分类准确性测试、修复后不变量检查、审计记录检查。 |
````

- [ ] **Step 2: Verify scenario headings**

Run:

```bash
rg -n "^## 充值|^## 提现|^## 支付回调|^## 外部渠道超时或未知状态|^## 渠道对账" financial-consistency/02-payment-recharge-withdraw/01-scenario-cards.md
```

Expected: output includes all 5 scenario headings.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/02-payment-recharge-withdraw/01-scenario-cards.md
git commit -m "docs: add payment channel scenario cards"
```

Expected: commit succeeds and includes only `01-scenario-cards.md`.

## Task 3: Create Invariants Document

**Files:**
- Create: `financial-consistency/02-payment-recharge-withdraw/02-invariants.md`

- [ ] **Step 1: Add invariants content**

Use `apply_patch` to create `financial-consistency/02-payment-recharge-withdraw/02-invariants.md`:

````markdown
# 02 正确性不变量

## 核心原则

外部渠道不参与我们的数据库事务，所以正确性不能依赖接口返回值。正确性必须由本地状态机、渠道事实、账户流水、会计分录、Outbox 事件、对账和修复记录共同保证。

## 不变量

### 幂等

- 同一业务幂等键只能产生一次充值入账。
- 同一提现单只能提交一次有效出款结果。
- 同一渠道回调只能产生一次业务效果。
- 同一渠道交易号不能绑定多个互相冲突的本地订单。

### 充值

- 充值成功必须有渠道成功事实。
- 充值成功必须有账户入账流水。
- 充值成功必须有贷记分录。
- 渠道成功但本地缺少入账或分录时，交易不能静默成功，必须进入补账或差错处理。
- 本地入账不能早于可信渠道成功事实，除非业务明确采用垫资模型；第一版不采用垫资。

### 提现

- 提现提交出款前必须先冻结资金。
- 提现成功必须消耗冻结。
- 提现失败必须释放冻结。
- 同一笔提现不能既释放冻结又确认出款成功。
- 出款成功但本地未消耗冻结时，必须补消耗冻结和分录，不能再次出款。

### 未知状态

- `UNKNOWN` 不是失败。
- 未知状态不能直接触发释放、退款或重复提交外部动作。
- 未知状态必须通过查询、回调、渠道账单或人工处理收敛。
- 长时间未知必须可观测，并进入升级流程。

### 回调

- 验签失败的回调不能改变业务状态。
- 重复回调不能重复入账、重复释放冻结或重复消耗冻结。
- 失败回调不能覆盖已经确认的成功终态。
- 回调只能基于状态机推进，不允许任意改状态。

### 对账和修复

- 渠道账单、本地支付单、账户流水和会计分录最终必须能解释彼此。
- 差错必须有分类、owner、状态、修复动作和审计记录。
- 修复只能通过补流水、补分录、冲正、补事件或人工工单完成，不能直接覆盖历史事实。

## 常见误区

- 把接口超时当失败。
- 把回调当唯一事实来源。
- 只对账订单状态，不对账账户流水和会计分录。
- 用更新历史记录代替冲正和补账。
- 用 broker offset 代表业务处理完成。
````

- [ ] **Step 2: Verify required invariant keywords**

Run:

```bash
rg -n "幂等|充值|提现|UNKNOWN|回调|对账和修复|不能直接覆盖历史事实" financial-consistency/02-payment-recharge-withdraw/02-invariants.md
```

Expected: output includes all required invariant groups.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/02-payment-recharge-withdraw/02-invariants.md
git commit -m "docs: define payment channel invariants"
```

Expected: commit succeeds and includes only `02-invariants.md`.

## Task 4: Create State Machine Document

**Files:**
- Create: `financial-consistency/02-payment-recharge-withdraw/03-state-machine.md`

- [ ] **Step 1: Add state machine content**

Use `apply_patch` to create `financial-consistency/02-payment-recharge-withdraw/03-state-machine.md`:

````markdown
# 03 状态机

## 设计原则

状态机的任务是防止外部渠道的不确定性污染本地资金事实。所有状态推进都必须基于耐久事实，不能只基于一次 RPC 返回值。

## 充值单状态

```text
CREATED
-> CHANNEL_PENDING
-> CHANNEL_UNKNOWN
-> CHANNEL_SUCCEEDED
-> ACCOUNT_CREDITED
-> LEDGER_POSTED
-> SUCCEEDED
```

失败和人工状态：

```text
CHANNEL_FAILED
RECONCILIATION_REQUIRED
MANUAL_REVIEW
```

关键规则：

- `CHANNEL_UNKNOWN` 只能通过查询、回调、账单或人工处理继续推进。
- `CHANNEL_SUCCEEDED` 之后必须补齐账户入账和分录。
- `SUCCEEDED` 不能被失败回调覆盖。
- `ACCOUNT_CREDITED` 但缺少 `LEDGER_POSTED` 时，修复方向是补分录，不是回滚入账。

## 提现单状态

```text
CREATED
-> RISK_APPROVED
-> FUNDS_RESERVED
-> PAYOUT_SUBMITTED
-> PAYOUT_UNKNOWN
-> PAYOUT_SUCCEEDED
-> FREEZE_CONSUMED
-> LEDGER_POSTED
-> SUCCEEDED
```

失败和人工状态：

```text
RISK_REJECTED
PAYOUT_FAILED
FUNDS_RELEASED
FAILED
RECONCILIATION_REQUIRED
MANUAL_REVIEW
```

关键规则：

- `PAYOUT_SUBMITTED` 之后出现超时必须进入 `PAYOUT_UNKNOWN`，不能直接进入失败。
- `PAYOUT_UNKNOWN` 不能再次提交新的出款动作，只能查询、等待回调或人工处理。
- `PAYOUT_FAILED` 后必须释放冻结，进入 `FUNDS_RELEASED` 后才能失败终结。
- `PAYOUT_SUCCEEDED` 后必须消耗冻结和记分录。

## 回调处理状态

```text
RECEIVED
-> VERIFIED
-> DEDUPED
-> APPLIED
```

异常状态：

```text
SIGNATURE_INVALID
DUPLICATE
STALE
CONFLICT
IGNORED
MANUAL_REVIEW
```

关键规则：

- `SIGNATURE_INVALID` 不能推进业务状态。
- `DUPLICATE` 返回既有处理结果，不重复执行业务动作。
- `STALE` 表示回调事实落后于本地更可信终态。
- `CONFLICT` 表示回调和本地或查询事实冲突，必须进入差错处理。

## 非法转换示例

| 非法转换 | 原因 |
| --- | --- |
| `CHANNEL_UNKNOWN -> CHANNEL_FAILED` | 超时不是失败，必须查询事实或等待回调。 |
| `PAYOUT_UNKNOWN -> FUNDS_RELEASED` | 未知出款不能释放冻结，否则可能造成用户拿到钱且余额恢复。 |
| `SUCCEEDED -> CHANNEL_FAILED` | 失败回调不能覆盖已确认成功终态。 |
| `PAYOUT_SUCCEEDED -> PAYOUT_SUBMITTED` | 出款成功后不能重新提交出款。 |
| `ACCOUNT_CREDITED -> CHANNEL_FAILED` | 已入账后发现冲突必须走差错或冲正，不允许简单改失败。 |
````

- [ ] **Step 2: Verify state names**

Run:

```bash
rg -n "CHANNEL_UNKNOWN|PAYOUT_UNKNOWN|ACCOUNT_CREDITED|FREEZE_CONSUMED|SIGNATURE_INVALID|CONFLICT|非法转换" financial-consistency/02-payment-recharge-withdraw/03-state-machine.md
```

Expected: output includes all required state names and illegal-transition section.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/02-payment-recharge-withdraw/03-state-machine.md
git commit -m "docs: define payment channel state machines"
```

Expected: commit succeeds and includes only `03-state-machine.md`.

## Task 5: Create Service Boundaries Document

**Files:**
- Create: `financial-consistency/02-payment-recharge-withdraw/04-service-boundaries.md`

- [ ] **Step 1: Add service boundaries content**

Use `apply_patch` to create `financial-consistency/02-payment-recharge-withdraw/04-service-boundaries.md`:

````markdown
# 04 服务边界

## 目标

本文件定义外部渠道场景下的服务职责。核心原则是：渠道事实、账户事实、账本事实和对账事实分别由不同边界拥有，不能让一个服务偷偷完成所有事情。

## 服务职责

| 服务 | 拥有什么 | 不拥有什么 |
| --- | --- | --- |
| `payment-service` | 充值单、提现单、支付单、渠道请求、回调幂等、业务状态机 | 不直接改账户余额，不直接写会计分录 |
| `channel-adapter` | 渠道调用、验签、查询、账单导入、渠道幂等号映射 | 不拥有业务终态，不决定用户余额 |
| `account-service` | 入账、冻结、释放冻结、消耗冻结、账户流水 | 不决定渠道是否成功 |
| `ledger-service` | 充值、提现、冲正和差错修复分录 | 不覆盖历史分录，不替代账户服务 |
| `reconciliation-service` | 渠道对账、账本对账、差错分类、修复工单 | 不静默修改资金 |
| `risk-service` | 提现风控、限额、风险拒绝 | 不处理渠道回调和出款结果 |
| `message-broker` | Outbox 事件投递和异步解耦 | 不代表业务事实本身 |

## 关键边界

- `payment-service` 是流程状态 owner，但不是资金 owner。
- `channel-adapter` 只提供渠道事实，不把渠道返回值直接变成本地成功。
- `account-service` 根据已确认命令修改账户，并生成账户流水。
- `ledger-service` 只追加分录或冲正分录，不删除历史。
- `reconciliation-service` 发现差异后生成差错单，自动修复也必须留下审计证据。

## 典型调用关系

### 充值

```text
payment-service
-> channel-adapter
-> payment-service
-> account-service
-> ledger-service
-> message-broker
```

### 提现

```text
payment-service
-> risk-service
-> account-service
-> channel-adapter
-> account-service
-> ledger-service
-> message-broker
```

### 渠道对账

```text
reconciliation-service
-> channel-adapter
-> payment-service
-> account-service
-> ledger-service
-> repair workflow
```

## 不接受的设计

- `payment-service` 直接更新余额。
- 回调处理绕过状态机。
- `channel-adapter` 决定本地成功或失败终态。
- 对账脚本直接改余额或改分录。
- 用消息 offset 作为入账、出款或对账完成事实。
````

- [ ] **Step 2: Verify service names**

Run:

```bash
rg -n "payment-service|channel-adapter|account-service|ledger-service|reconciliation-service|risk-service|message-broker|不接受的设计" financial-consistency/02-payment-recharge-withdraw/04-service-boundaries.md
```

Expected: output includes all service names.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/02-payment-recharge-withdraw/04-service-boundaries.md
git commit -m "docs: define payment channel service boundaries"
```

Expected: commit succeeds and includes only `04-service-boundaries.md`.

## Task 6: Create Event Flow Document

**Files:**
- Create: `financial-consistency/02-payment-recharge-withdraw/05-event-flow.md`

- [ ] **Step 1: Add event flow content**

Use `apply_patch` to create `financial-consistency/02-payment-recharge-withdraw/05-event-flow.md`:

````markdown
# 05 事件流

## 目标

事件流用于区分本地命令、渠道事实、账户事实、账本事实、对账事实和人工修复事实。只有明确事实来源，系统才能在超时、重复、乱序和部分成功之后恢复。

## 事件分类

| 类型 | 示例 | 事实 owner |
| --- | --- | --- |
| 本地命令 | `RechargeRequested`、`WithdrawRequested` | `payment-service` |
| 渠道事实 | `ChannelPaymentSucceeded`、`PayoutSucceeded` | `channel-adapter` / 渠道账单 |
| 账户事实 | `RechargeAccountCredited`、`WithdrawFreezeConsumed` | `account-service` |
| 账本事实 | `RechargeLedgerPosted`、`WithdrawLedgerPosted` | `ledger-service` |
| 回调事实 | `PaymentCallbackReceived`、`PaymentCallbackVerified`、`PaymentCallbackApplied` | `payment-service` |
| 对账事实 | `ChannelStatementImported`、`ChannelMismatchDetected` | `reconciliation-service` |
| 修复事实 | `ChannelRepairRequested`、`ManualRepairCompleted` | `reconciliation-service` / 运营复核 |

## 充值事件流

```text
RechargeRequested
-> ChannelPaymentInitiated
-> ChannelPaymentSucceeded
-> RechargeAccountCredited
-> RechargeLedgerPosted
-> RechargeSucceeded
```

异常分支：

```text
ChannelPaymentUnknown
-> channel query or callback
-> ChannelPaymentSucceeded or ChannelPaymentFailed or ManualReviewRequired
```

## 提现事件流

```text
WithdrawRequested
-> WithdrawRiskApproved
-> WithdrawFundsReserved
-> PayoutSubmitted
-> PayoutSucceeded
-> WithdrawFreezeConsumed
-> WithdrawLedgerPosted
-> WithdrawSucceeded
```

异常分支：

```text
PayoutUnknown
-> channel query or callback
-> PayoutSucceeded or PayoutFailed or ManualReviewRequired
```

## 回调事件流

```text
PaymentCallbackReceived
-> PaymentCallbackVerified
-> callback dedup check
-> PaymentCallbackApplied
-> downstream state transition
```

回调不能直接代表业务成功。它只是一个外部事实输入，必须经过验签、幂等和状态机判断。

## 对账事件流

```text
ChannelStatementImported
-> local order matched
-> account movement matched
-> ledger posting matched
-> matched or ChannelMismatchDetected
-> ChannelRepairRequested
-> ManualRepairCompleted
```

## 顺序依赖

- `RechargeAccountCredited` 依赖可信的 `ChannelPaymentSucceeded`。
- `RechargeLedgerPosted` 依赖 `RechargeAccountCredited`。
- `PayoutSubmitted` 依赖 `WithdrawFundsReserved`。
- `WithdrawFreezeConsumed` 依赖可信的 `PayoutSucceeded`。
- `WithdrawLedgerPosted` 依赖 `WithdrawFreezeConsumed`。
- `ManualRepairCompleted` 依赖差错分类和审批证据。

## Broker 不是事实来源

Kafka 或其他消息系统只负责投递语义。业务事实必须来自本地数据库记录、渠道事实、账户流水、会计分录和对账记录，不能用 consumer offset 证明入账、出款或对账已经完成。
````

- [ ] **Step 2: Verify event names**

Run:

```bash
rg -n "RechargeRequested|ChannelPaymentSucceeded|WithdrawRequested|PayoutSucceeded|PaymentCallbackReceived|ChannelStatementImported|ChannelMismatchDetected|ManualRepairCompleted|Broker 不是事实来源" financial-consistency/02-payment-recharge-withdraw/05-event-flow.md
```

Expected: output includes all required event names and broker warning.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/02-payment-recharge-withdraw/05-event-flow.md
git commit -m "docs: define payment channel event flow"
```

Expected: commit succeeds and includes only `05-event-flow.md`.

## Task 7: Create Failure Matrix Document

**Files:**
- Create: `financial-consistency/02-payment-recharge-withdraw/06-failure-matrix.md`

- [ ] **Step 1: Add failure matrix content**

Use `apply_patch` to create `financial-consistency/02-payment-recharge-withdraw/06-failure-matrix.md`:

````markdown
# 06 失败矩阵

## 目标

失败矩阵把每个危险点映射到状态、事实来源和恢复动作。外部渠道场景的关键是：先确认事实，再决定重试、补偿、冲正或人工处理。

| 失败点 | 已知事实 | 系统状态 | 处理策略 |
| --- | --- | --- | --- |
| 调用渠道前本地事务失败 | 没有渠道请求号 | 本地请求未成立 | 回滚本地事务或重试创建本地单，不调用渠道补偿。 |
| 调用渠道成功但响应超时 | 有渠道请求号，没有确定结果 | `CHANNEL_UNKNOWN` 或 `PAYOUT_UNKNOWN` | 不能当失败；定时查询、等待回调或渠道账单收敛。 |
| 调用渠道失败但稍后收到成功回调 | 有成功回调或查询成功事实 | 渠道成功、本地可能失败 | 以可信渠道事实推进，补账户流水和分录。 |
| 回调重复 | 回调幂等键或渠道交易号已处理 | `DUPLICATE` | 返回既有处理结果，不重复执行业务动作。 |
| 回调乱序 | 回调事实落后于本地终态 | `STALE` 或 `IGNORED` | 记录审计，不覆盖更可信终态。 |
| 回调验签失败 | 签名无效 | `SIGNATURE_INVALID` | 拒绝处理，记录安全审计。 |
| 查询结果和回调结果冲突 | 两个外部事实不一致 | `CONFLICT` | 进入差错处理和人工复核。 |
| 充值渠道成功但账户入账失败 | 渠道成功，无账户流水 | `RECONCILIATION_REQUIRED` | 补入账流水，再补分录和事件。 |
| 充值账户入账成功但分录失败 | 账户流水存在，分录缺失 | `ACCOUNT_CREDITED` | 补贷记分录，不回滚账户流水。 |
| 提现冻结成功但出款提交失败 | 冻结存在，无渠道请求成功事实 | `FUNDS_RESERVED` | 释放冻结，标记失败或允许重新发起。 |
| 提现出款成功但本地状态未推进 | 渠道出款成功，冻结仍存在 | `PAYOUT_SUCCEEDED` 待修复 | 补消耗冻结、补借记分录、补事件。 |
| 提现出款失败但冻结未释放 | 渠道失败，冻结仍存在 | `PAYOUT_FAILED` | 释放冻结，记录失败原因。 |
| Outbox 事件发布失败 | 本地事实已提交，事件未发布 | outbox pending | 重试发布，不重做资金动作。 |
| 消费者重复消费 | 消息重复投递 | consumer dedup | 使用业务幂等键和唯一约束去重。 |
| 渠道账单和本地订单不一致 | 对账发现差异 | `ChannelMismatchDetected` | 分类差错，进入修复工作流。 |
| 人工修复动作失败或重复提交 | 修复工单存在 | repair pending or duplicate | 使用修复幂等键，保留审批和审计记录。 |

## 决策规则

- 已提交外部请求但结果未知时，只能查询、等待回调或对账，不能直接失败。
- 已确认渠道成功但本地缺失事实时，优先补齐本地事实。
- 已确认本地成功但渠道缺失时，进入差错处理，不能静默成功。
- 已经发生的资金事实不能删除，只能用冲正、补账或人工修复解释。
````

- [ ] **Step 2: Verify failure cases**

Run:

```bash
rg -n "响应超时|回调重复|回调乱序|验签失败|充值渠道成功|提现出款成功|Outbox|渠道账单|人工修复" financial-consistency/02-payment-recharge-withdraw/06-failure-matrix.md
```

Expected: output includes all required failure categories.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/02-payment-recharge-withdraw/06-failure-matrix.md
git commit -m "docs: define payment channel failure matrix"
```

Expected: commit succeeds and includes only `06-failure-matrix.md`.

## Task 8: Create Reconciliation Document

**Files:**
- Create: `financial-consistency/02-payment-recharge-withdraw/07-reconciliation.md`

- [ ] **Step 1: Add reconciliation content**

Use `apply_patch` to create `financial-consistency/02-payment-recharge-withdraw/07-reconciliation.md`:

````markdown
# 07 对账设计

## 为什么本阶段必须讲对账

外部渠道场景里，接口返回、回调、查询结果和账单可能互相不一致。对账不是后期补丁，而是发现渠道事实和本地事实分叉的核心链路。

## 渠道对账和账本对账

| 类型 | 关注点 | 主要输入 |
| --- | --- | --- |
| 渠道对账 | 渠道有没有这笔交易，状态、金额、币种、手续费和时间是否一致 | 渠道账单、本地支付单、渠道请求号、渠道交易号 |
| 账本对账 | 本地资金事实是否完整，账户流水和会计分录能否解释业务状态 | 本地支付单、账户流水、会计分录、Outbox 消费记录 |

## 差错分类

| 差错 | 含义 | 修复方向 |
| --- | --- | --- |
| 渠道成功，本地失败 | 渠道账单成功，本地未成功或缺少流水 | 补状态、补账户流水、补分录、补事件 |
| 本地成功，渠道缺失 | 本地成功但渠道账单没有交易 | 进入人工复核，必要时冲正或客户沟通 |
| 渠道失败，本地成功 | 渠道失败但本地已入账或确认出款 | 冲正、释放或人工修复 |
| 金额不一致 | 渠道金额、手续费、币种和本地不一致 | 差额分录、手续费调整、人工复核 |
| 重复入账 | 同一渠道事实产生多次账户入账 | 冲正重复流水，检查幂等缺陷 |
| 重复出款 | 同一提现产生多次渠道出款 | 人工追回、反向入账、风险升级 |
| 分录缺失 | 账户流水存在但会计分录缺失 | 补分录 |
| 长时间未知状态 | 本地状态无法自动收敛 | 查询、账单核验、人工复核 |

## 对账输入

- 渠道账单。
- 本地支付单、充值单、提现单。
- 渠道请求号和渠道交易号。
- 账户流水。
- 会计分录。
- Outbox 事件和消费记录。
- 回调记录和查询记录。

## 修复原则

- 不直接覆盖历史事实。
- 修复动作必须有幂等键。
- 自动修复必须留下审计记录。
- 高风险修复需要 maker-checker 或人工复核。
- 修复完成后必须重新对账。

## 对账输出

- `MATCHED`：渠道和本地事实一致。
- `MISMATCH_DETECTED`：发现差错。
- `REPAIR_REQUESTED`：已生成修复动作。
- `REPAIRED`：修复动作完成。
- `VERIFIED`：修复后复核通过。
````

- [ ] **Step 2: Verify reconciliation categories**

Run:

```bash
rg -n "渠道对账|账本对账|渠道成功，本地失败|本地成功，渠道缺失|渠道失败，本地成功|金额不一致|重复入账|重复出款|分录缺失|长时间未知状态" financial-consistency/02-payment-recharge-withdraw/07-reconciliation.md
```

Expected: output includes all required reconciliation categories.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/02-payment-recharge-withdraw/07-reconciliation.md
git commit -m "docs: define payment channel reconciliation"
```

Expected: commit succeeds and includes only `07-reconciliation.md`.

## Task 9: Create Verification Plan Document

**Files:**
- Create: `financial-consistency/02-payment-recharge-withdraw/08-verification-plan.md`

- [ ] **Step 1: Add verification content**

Use `apply_patch` to create `financial-consistency/02-payment-recharge-withdraw/08-verification-plan.md`:

````markdown
# 08 验证路线

## 目标

验证路线要证明设计能暴露外部渠道场景中最危险的问题：重复回调、未知状态、重复出款、渠道成功本地失败、本地成功渠道失败，以及对账差错修复。

## 模型验证

需要建模的规则：

- `UNKNOWN` 不能直接变成失败补偿。
- 成功终态不能被失败回调覆盖。
- 提现出款未知时不能释放冻结。
- 同一渠道事实只能产生一次业务效果。
- 对账差错必须进入分类和修复状态。

## 属性测试

随机生成这些序列：

- 回调重复、乱序、延迟。
- 查询补偿先于回调或晚于回调。
- 提现提交后超时，再收到成功或失败事实。
- Outbox 重复投递。
- 人工修复重复提交。

检查属性：

- 不重复入账。
- 不重复出款。
- 冻结最终释放或消耗。
- 成功充值有账户流水和贷记分录。
- 成功提现有冻结消耗和借记分录。
- 终态不被非法覆盖。

## 集成测试

使用真实数据库语义验证：

- 幂等唯一约束。
- 本地事务和 Outbox 同提交。
- consumer dedup。
- channel-adapter fake 返回成功、失败、超时和冲突。
- 回调处理和查询补偿并发到达。

## 故障注入

必须注入：

- 渠道超时。
- 回调重复。
- 回调乱序。
- DB 写入失败。
- Outbox 发布失败。
- 消费者崩溃。
- 对账账单缺失或金额不一致。

## 历史检查

记录所有用户命令、渠道事实、本地状态变化、账户流水、会计分录和对账结果。检查最终历史是否满足：

- 每个幂等键最多一个业务效果。
- 每个成功充值有完整资金事实。
- 每个成功提现有完整资金事实。
- 每个未知状态最终进入成功、失败或人工处理。
- 每个差错都有分类和修复路径。

## 对账验证

构造账单覆盖：

- 渠道成功，本地失败。
- 本地成功，渠道缺失。
- 渠道失败，本地成功。
- 金额不一致。
- 重复入账。
- 重复出款。
- 分录缺失。
- 长时间未知状态。

每类账单都必须生成稳定差错分类、owner、修复动作和审计证据。
````

- [ ] **Step 2: Verify verification methods**

Run:

```bash
rg -n "模型验证|属性测试|集成测试|故障注入|历史检查|对账验证|UNKNOWN|重复出款" financial-consistency/02-payment-recharge-withdraw/08-verification-plan.md
```

Expected: output includes all verification methods.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/02-payment-recharge-withdraw/08-verification-plan.md
git commit -m "docs: define payment channel verification"
```

Expected: commit succeeds and includes only `08-verification-plan.md`.

## Task 10: Create Interview Synthesis Document

**Files:**
- Create: `financial-consistency/02-payment-recharge-withdraw/09-interview-synthesis.md`

- [ ] **Step 1: Add interview content**

Use `apply_patch` to create `financial-consistency/02-payment-recharge-withdraw/09-interview-synthesis.md`:

````markdown
# 09 面试与架构评审表达

## 一句话回答

外部支付渠道不参与我们的事务，所以支付、充值和提现不能只靠接口返回值保证正确性。金融级实现必须用本地状态机、渠道事实、幂等、查询补偿、账户流水、会计分录、Outbox、渠道对账和人工修复共同收敛。

## 标准回答结构

1. 先说明外部渠道不可控，不参与本地事务。
2. 再说明超时不是失败，必须进入未知状态。
3. 再说明回调必须验签、幂等和状态机推进。
4. 再说明资金变化必须落到账户流水和会计分录。
5. 再说明渠道账单、本地订单、账户流水和分录必须对账。
6. 最后说明如何验证：模型、属性测试、故障注入、历史检查和对账验证。

## 高频问题

### 支付回调重复怎么办？

回调必须有幂等键或渠道交易号唯一约束。重复回调只能返回既有处理结果，不能重复入账、重复释放冻结或重复消耗冻结。

### 支付接口超时怎么办？

超时不能当失败。已经提交渠道请求时，本地应进入 `UNKNOWN`，后续通过查询补偿、回调、渠道账单或人工处理收敛。

### 充值成功但本地没入账怎么办？

如果渠道成功事实可信，本地应该补入账、补分录、补事件，并记录修复审计。不能让交易静默停在成功或失败之外。

### 提现请求超时能不能重试？

不能盲目重试新的出款动作。必须使用渠道幂等请求号查询原请求结果。未知状态下重复提交可能造成重复出款。

### 渠道成功、本地失败如何处理？

以渠道成功事实为基础补齐本地状态、账户流水和分录，再通过对账复核。

### 本地成功、渠道失败如何处理？

这属于差错。根据场景进行冲正、释放、退款、人工复核或客户沟通，不能直接改历史记录掩盖问题。

### 为什么不能只看回调？

回调可能重复、乱序、伪造、延迟或丢失。必须结合验签、查询补偿、渠道账单和本地状态机判断。

### 为什么对账不是补丁？

因为外部渠道和本地系统天然可能分叉。没有对账，就无法发现渠道成功本地失败、本地成功渠道缺失、金额不一致和分录缺失。

### Temporal 在这里解决什么？

Temporal 适合承接长流程、重试、定时查询、超时处理和人工处理入口。它不替代账户流水、会计分录、幂等约束、Outbox 或对账。

## 评审底线

- 不接受把 RPC 超时当失败。
- 不接受回调直接改终态而不走状态机。
- 不接受提现未知状态下重复提交出款。
- 不接受只有订单状态、没有账户流水和会计分录。
- 不接受没有渠道对账和差错修复流程。
````

- [ ] **Step 2: Verify interview questions**

Run:

```bash
rg -n "支付回调重复|支付接口超时|充值成功但本地没入账|提现请求超时|渠道成功、本地失败|本地成功、渠道失败|为什么不能只看回调|Temporal" financial-consistency/02-payment-recharge-withdraw/09-interview-synthesis.md
```

Expected: output includes all interview questions.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/02-payment-recharge-withdraw/09-interview-synthesis.md
git commit -m "docs: add payment channel interview synthesis"
```

Expected: commit succeeds and includes only `09-interview-synthesis.md`.

## Task 11: Update Root README

**Files:**
- Modify: `financial-consistency/README.md`

- [ ] **Step 1: Add design spec link**

In `financial-consistency/README.md`, add this line to the formal design document list after the existing financial scenario matrix expansion design link:

```markdown
- [2026-05-01-payment-recharge-withdraw-design.md](../docs/superpowers/specs/2026-05-01-payment-recharge-withdraw-design.md)
```

- [ ] **Step 2: Link phase 02 route**

Change:

```markdown
- 02-payment-recharge-withdraw
  充值、提现、支付回调、渠道超时、渠道对账。
```

to:

```markdown
- [02-payment-recharge-withdraw](./02-payment-recharge-withdraw/README.md)
  充值、提现、支付回调、渠道超时、渠道对账。
```

- [ ] **Step 3: Verify root README links**

Run:

```bash
rg -n "2026-05-01-payment-recharge-withdraw-design.md|\./02-payment-recharge-withdraw/README.md" financial-consistency/README.md
```

Expected: output includes both links.

- [ ] **Step 4: Commit**

Run:

```bash
git add financial-consistency/README.md
git commit -m "docs: link payment recharge withdraw phase"
```

Expected: commit succeeds and includes only `financial-consistency/README.md`.

## Task 12: Final Documentation Verification

**Files:**
- Verify: `financial-consistency/02-payment-recharge-withdraw/**`
- Verify: `financial-consistency/README.md`

- [ ] **Step 1: Verify all phase files exist**

Run:

```bash
find financial-consistency/02-payment-recharge-withdraw -maxdepth 1 -type f | sort
```

Expected output:

```text
financial-consistency/02-payment-recharge-withdraw/01-scenario-cards.md
financial-consistency/02-payment-recharge-withdraw/02-invariants.md
financial-consistency/02-payment-recharge-withdraw/03-state-machine.md
financial-consistency/02-payment-recharge-withdraw/04-service-boundaries.md
financial-consistency/02-payment-recharge-withdraw/05-event-flow.md
financial-consistency/02-payment-recharge-withdraw/06-failure-matrix.md
financial-consistency/02-payment-recharge-withdraw/07-reconciliation.md
financial-consistency/02-payment-recharge-withdraw/08-verification-plan.md
financial-consistency/02-payment-recharge-withdraw/09-interview-synthesis.md
financial-consistency/02-payment-recharge-withdraw/README.md
```

- [ ] **Step 2: Verify README child links**

Run:

```bash
rg -n "\./01-scenario-cards.md|\./02-invariants.md|\./03-state-machine.md|\./04-service-boundaries.md|\./05-event-flow.md|\./06-failure-matrix.md|\./07-reconciliation.md|\./08-verification-plan.md|\./09-interview-synthesis.md" financial-consistency/02-payment-recharge-withdraw/README.md
```

Expected: output includes all 9 child document links.

- [ ] **Step 3: Verify core scenario coverage**

Run:

```bash
rg -n "充值|提现|支付回调|外部渠道超时|渠道对账" financial-consistency/02-payment-recharge-withdraw/01-scenario-cards.md
```

Expected: output includes all 5 scenario names.

- [ ] **Step 4: Verify main technical anchors**

Run:

```bash
rg -n "UNKNOWN|幂等|Outbox|渠道账单|会计分录|查询补偿|人工修复|Temporal" financial-consistency/02-payment-recharge-withdraw
```

Expected: output includes the core terms across the phase docs.

- [ ] **Step 5: Verify root README link**

Run:

```bash
rg -n "2026-05-01-payment-recharge-withdraw-design.md|\./02-payment-recharge-withdraw/README.md" financial-consistency/README.md
```

Expected: output includes both root README links.

- [ ] **Step 6: Verify `01-transfer` was not changed in this phase**

Run:

```bash
git diff --name-only main..HEAD -- financial-consistency/01-transfer
```

Expected: no output.

- [ ] **Step 7: Scan for incomplete-document markers**

Run:

```bash
rg -n "TO[D]O|TB[D]|待[定]|占[位]|以[后]补|未[决]|大[概]|随[便]" financial-consistency/02-payment-recharge-withdraw financial-consistency/README.md
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
