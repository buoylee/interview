# Financial Scenario Matrix Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the financial scenario matrix with high-value real-world scenarios and define the minimum depth for future scenario cards.

**Architecture:** This is a documentation-only change. `financial-consistency/00-scenario-matrix.md` remains the scenario navigation layer; it gains one forward-looking scenario section and one reusable scenario-card standard. `financial-consistency/README.md` remains the top-level entry point and gains a link to the expansion design spec.

**Tech Stack:** Markdown, Git, `rg`, `git diff --check`.

---

## File Structure

- Modify: `financial-consistency/00-scenario-matrix.md`
  - Adds `待补充高价值场景` after the current scenario matrix table and before `模式选择规则`.
  - Adds `场景卡最小深度` after `模式选择规则` and before `进入具体模块的顺序`.
  - Does not change existing matrix rows.

- Modify: `financial-consistency/README.md`
  - Adds the expansion design spec to the formal design document list.

- Reference only: `docs/superpowers/specs/2026-05-01-financial-scenario-matrix-expansion-design.md`
  - Approved design source for scope and acceptance criteria.

- Do not modify: `financial-consistency/01-transfer/**`
  - Existing transfer deep-dive docs must remain untouched.

## Task 1: Add High-Value Scenario Expansion Section

**Files:**
- Modify: `financial-consistency/00-scenario-matrix.md`

- [ ] **Step 1: Confirm insertion point exists**

Run:

```bash
rg -n "^## 模式选择规则" financial-consistency/00-scenario-matrix.md
```

Expected output:

```text
47:## 模式选择规则
```

Line number may shift if prior content has changed, but the heading must exist exactly once.

- [ ] **Step 2: Insert this section before `## 模式选择规则`**

Use `apply_patch` to insert this exact Markdown between the current scenario matrix table and the `## 模式选择规则` heading:

```markdown
## 待补充高价值场景

下面这些场景暂时不进入第一学习顺序，但它们在金融、支付、清结算、平台交易和国际业务中非常常见。后续扩展具体模块时，需要逐步把它们纳入正式场景卡和深挖模块。

### 预授权、授权占用、Capture、Void

代表业务：

- 酒店押金。
- 租车押金。
- 信用卡担保交易。
- 先授权占用额度，后确认扣款或撤销授权。

为什么重要：

- 它不是普通扣款。
- 授权占用、确认扣款和撤销授权是不同事实。
- 授权可能过期，Capture 可能部分成功，Void 可能晚到或失败。

后续归属：

- `02-payment-recharge-withdraw`
- `04-travel-booking-saga`

### 商户结算、分账、平台佣金

代表业务：

- 电商平台把订单收入拆给商户、平台佣金、服务费、税费和渠道手续费。
- 支付平台按日或按周期给商户结算。

为什么重要：

- 钱不是简单从 A 到 B。
- 一笔交易会产生多方应收应付。
- 退款、拒付、补贴、手续费退还会影响后续结算。

后续归属：

- `03-order-payment-inventory`
- `07-reconciliation`

### 拒付、争议、Chargeback

代表业务：

- 持卡人对已成功交易发起争议。
- 卡组织或银行把款项从商户侧冲回。
- 商户提交举证材料后可能胜诉或败诉。

为什么重要：

- 成功交易很久以后仍可能反向变化。
- 它不是普通退款，因为发起方和裁决方不完全由平台控制。
- 需要证据链、冻结准备金、商户账务调整和对账。

后续归属：

- `07-reconciliation`
- `08-interview-synthesis`

### 订阅扣费、自动续费、失败重试

代表业务：

- 月度会员。
- SaaS 订阅。
- 自动续费扣款失败后的重试、宽限期和权益暂停。

为什么重要：

- 它是长期状态机，不是单次交易。
- 扣款失败不一定立即终止服务。
- 重试策略、权益状态和账单状态必须一致。

后续归属：

- `02-payment-recharge-withdraw`
- `03-order-payment-inventory`

### ACH、Direct Debit、银行代扣

代表业务：

- 用户授权从银行账户扣款。
- 扣款请求提交后，几天后才知道最终成功或失败。
- 成功后仍可能退回。

为什么重要：

- 这类系统不是实时支付。
- “提交成功”不等于“资金成功”。
- 需要 pending 状态、退回处理、账期和渠道对账。

后续归属：

- `02-payment-recharge-withdraw`
- `07-reconciliation`

### 商户日终清算、批量出款

代表业务：

- 平台按日汇总商户可结算金额。
- 生成清算批次和出款文件。
- 银行返回部分成功、部分失败。

为什么重要：

- 从在线单笔交易进入批处理。
- 批次、明细、出款结果和账本必须能互相核对。
- 部分失败不能影响已成功明细，也不能重复出款。

后续归属：

- `07-reconciliation`

### 贷款还款、分期、利息计提

代表业务：

- 贷款分期还款。
- 逾期罚息。
- 提前还款。
- 自动扣款失败后的补扣。

为什么重要：

- 引入账期、应收、利息、罚息和摊销。
- 还款顺序会影响本金、利息和费用。
- 冲正和调整必须保留历史证据。

后续归属：

- `07-reconciliation`
- 远期可能模块 `09-credit-and-loan`
```

- [ ] **Step 3: Verify the 7 scenario headings exist**

Run:

```bash
rg -n "预授权、授权占用|商户结算、分账|拒付、争议|订阅扣费|ACH、Direct Debit|商户日终清算|贷款还款" financial-consistency/00-scenario-matrix.md
```

Expected output includes all 7 headings.

- [ ] **Step 4: Commit the scenario expansion section**

Run:

```bash
git add financial-consistency/00-scenario-matrix.md
git commit -m "docs: add high-value financial scenarios"
```

Expected: commit succeeds and includes only `financial-consistency/00-scenario-matrix.md`.

## Task 2: Add Scenario Card Depth Standard

**Files:**
- Modify: `financial-consistency/00-scenario-matrix.md`

- [ ] **Step 1: Confirm insertion point exists**

Run:

```bash
rg -n "^## 进入具体模块的顺序" financial-consistency/00-scenario-matrix.md
```

Expected output includes exactly one `## 进入具体模块的顺序` heading.

- [ ] **Step 2: Insert this section before `## 进入具体模块的顺序`**

Use `apply_patch` to insert this exact Markdown between the current `模式选择规则` list and the `## 进入具体模块的顺序` heading:

```markdown
## 场景卡最小深度

后续任何场景从矩阵进入完整模块时，至少要有一张“场景卡”。场景卡不是代码设计，而是正式建模前的业务和一致性边界说明。

每张场景卡必须包含：

| 字段 | 说明 |
| --- | --- |
| 参与方 | 用户、平台、账户服务、账本服务、支付渠道、银行、商户、供应商、运营人员等 |
| 核心状态机 | 关键业务状态，以及哪些状态不能回退 |
| 耐久事实 | 哪些记录、事件、分录或渠道结果一旦写入就代表业务事实 |
| 最危险失败点 | 超时、重复、乱序、部分成功、外部未知、人工误操作等 |
| 补偿方式 | 释放、冲正、退款、退汇、赔付、补事件、人工处理等 |
| 对账来源 | 本地订单、账户流水、会计分录、Outbox、消费记录、渠道账单、供应商账单 |
| 验证方式 | 不变量、属性测试、集成测试、故障注入、历史检查、对账规则 |

这个标准用于控制后续教程深度：不允许只讲框架，也不允许只讲 happy path。
```

- [ ] **Step 3: Verify scenario-card fields exist**

Run:

```bash
rg -n "参与方|核心状态机|耐久事实|最危险失败点|补偿方式|对账来源|验证方式" financial-consistency/00-scenario-matrix.md
```

Expected output includes all 7 field names.

- [ ] **Step 4: Commit the scenario-card standard**

Run:

```bash
git add financial-consistency/00-scenario-matrix.md
git commit -m "docs: define financial scenario card depth"
```

Expected: commit succeeds and includes only `financial-consistency/00-scenario-matrix.md`.

## Task 3: Link Expansion Spec From README

**Files:**
- Modify: `financial-consistency/README.md`

- [ ] **Step 1: Add the expansion design spec link**

In `financial-consistency/README.md`, change this block:

```markdown
正式设计文档：

- [2026-05-01-financial-consistency-design.md](../docs/superpowers/specs/2026-05-01-financial-consistency-design.md)
- [2026-05-01-financial-scenario-matrix-design.md](../docs/superpowers/specs/2026-05-01-financial-scenario-matrix-design.md)
- [旧笔记索引](./references.md)
```

to:

```markdown
正式设计文档：

- [2026-05-01-financial-consistency-design.md](../docs/superpowers/specs/2026-05-01-financial-consistency-design.md)
- [2026-05-01-financial-scenario-matrix-design.md](../docs/superpowers/specs/2026-05-01-financial-scenario-matrix-design.md)
- [2026-05-01-financial-scenario-matrix-expansion-design.md](../docs/superpowers/specs/2026-05-01-financial-scenario-matrix-expansion-design.md)
- [旧笔记索引](./references.md)
```

- [ ] **Step 2: Verify README link**

Run:

```bash
rg -n "2026-05-01-financial-scenario-matrix-expansion-design.md" financial-consistency/README.md
```

Expected output:

```text
9:- [2026-05-01-financial-scenario-matrix-expansion-design.md](../docs/superpowers/specs/2026-05-01-financial-scenario-matrix-expansion-design.md)
```

Line number may shift by one line if surrounding design links change.

- [ ] **Step 3: Commit README link update**

Run:

```bash
git add financial-consistency/README.md
git commit -m "docs: link financial scenario expansion design"
```

Expected: commit succeeds and includes only `financial-consistency/README.md`.

## Task 4: Final Verification

**Files:**
- Verify: `financial-consistency/00-scenario-matrix.md`
- Verify: `financial-consistency/README.md`

- [ ] **Step 1: Verify all high-value scenarios are searchable**

Run:

```bash
rg -n "预授权|商户结算|拒付|订阅|ACH|Direct Debit|商户日终清算|贷款还款" financial-consistency/00-scenario-matrix.md
```

Expected: output includes all high-value scenario names.

- [ ] **Step 2: Verify all scenario-card fields are searchable**

Run:

```bash
rg -n "参与方|核心状态机|耐久事实|最危险失败点|补偿方式|对账来源|验证方式" financial-consistency/00-scenario-matrix.md
```

Expected: output includes all scenario-card field names.

- [ ] **Step 3: Verify README links the expansion design spec**

Run:

```bash
rg -n "2026-05-01-financial-scenario-matrix-expansion-design.md" financial-consistency/README.md
```

Expected: output includes the expansion spec link.

- [ ] **Step 4: Verify `01-transfer` was not modified in this feature**

Run:

```bash
git diff --name-only HEAD~3..HEAD -- financial-consistency/01-transfer
```

Expected: no output.

- [ ] **Step 5: Scan for incomplete-document markers**

Run:

```bash
rg -n "TO[D]O|TB[D]|待[定]|占[位]|以[后]补|未[决]|大[概]|随[便]" financial-consistency/00-scenario-matrix.md financial-consistency/README.md
```

Expected: no output and exit code `1`.

- [ ] **Step 6: Check Markdown whitespace**

Run:

```bash
git diff --check
```

Expected: no output and exit code `0`.

- [ ] **Step 7: Verify working tree is clean**

Run:

```bash
git status --short
```

Expected: no output.

