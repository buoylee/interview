# Financial Consistency Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `07-reconciliation` documentation module that turns reconciliation into a unified financial-grade fact closure covering statements, differences, cases, repairs, reviews, audits, and scenario-specific reconciliation.

**Architecture:** This is a documentation-first phase. Each file owns one reconciliation concern: the shared model, data sources, reconciliation types, difference classification, repair workflow, scenario matrix, verification/audit, and interview synthesis. The phase builds on `01-transfer` through `06-verification-lab` and only modifies the root README to link the new module.

**Tech Stack:** Markdown, Git, `rg`, `find`, `git diff --check`. No Java service, database schema, scheduler, Kafka, Temporal, payment-channel integration, supplier integration, or framework API is introduced in this phase.

---

## File Structure

- Create directory: `financial-consistency/07-reconciliation/`
- Create: `financial-consistency/07-reconciliation/README.md`
- Create: `financial-consistency/07-reconciliation/01-reconciliation-model.md`
- Create: `financial-consistency/07-reconciliation/02-reconciliation-sources.md`
- Create: `financial-consistency/07-reconciliation/03-reconciliation-types.md`
- Create: `financial-consistency/07-reconciliation/04-difference-classification.md`
- Create: `financial-consistency/07-reconciliation/05-repair-workflow.md`
- Create: `financial-consistency/07-reconciliation/06-scenario-matrix.md`
- Create: `financial-consistency/07-reconciliation/07-verification-and-audit.md`
- Create: `financial-consistency/07-reconciliation/08-interview-synthesis.md`
- Modify: `financial-consistency/README.md`

Do not modify:

- `financial-consistency/01-transfer/**`
- `financial-consistency/02-payment-recharge-withdraw/**`
- `financial-consistency/03-order-payment-inventory/**`
- `financial-consistency/04-travel-booking-saga/**`
- `financial-consistency/05-patterns/**`
- `financial-consistency/06-verification-lab/**`

## Task 1: Create Reconciliation README

**Files:**
- Create: `financial-consistency/07-reconciliation/README.md`

- [ ] **Step 1: Create directory**

Run:

```bash
mkdir -p financial-consistency/07-reconciliation
```

Expected: command succeeds.

- [ ] **Step 2: Add README content**

Use `apply_patch` to create `financial-consistency/07-reconciliation/README.md` with:

````markdown
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
````

- [ ] **Step 3: Verify README links**

Run:

```bash
rg -n "\./01-reconciliation-model.md|\./02-reconciliation-sources.md|\./03-reconciliation-types.md|\./04-difference-classification.md|\./05-repair-workflow.md|\./06-scenario-matrix.md|\./07-verification-and-audit.md|\./08-interview-synthesis.md" financial-consistency/07-reconciliation/README.md
```

Expected: output includes all 8 child document links.

- [ ] **Step 4: Commit**

Run:

```bash
git add financial-consistency/07-reconciliation/README.md
git commit -m "docs: add reconciliation module entry"
```

Expected: commit succeeds and includes only `financial-consistency/07-reconciliation/README.md`.

## Task 2: Create Reconciliation Model Document

**Files:**
- Create: `financial-consistency/07-reconciliation/01-reconciliation-model.md`

- [ ] **Step 1: Add model content**

Use `apply_patch` to create `financial-consistency/07-reconciliation/01-reconciliation-model.md` with:

````markdown
# 01 对账模型

## 目标

统一对账语言。对账不是两张表相减，也不是发现差异后直接改数据；对账是一组从 Difference 到 Case、Repair、Review、Close 的事实闭环。

## 核心对象

| 对象 | 含义 | 示例 | 验证重点 |
| --- | --- | --- | --- |
| Fact | 已经持久化、可审计的业务或资金事实 | 支付单、账本分录、供应商订单、库存流水、人工审批 | 是否可信、可追溯、不可随意删除 |
| Statement | 外部或内部对账来源给出的陈述 | 渠道账单、供应商账单、清算文件、库存快照 | 是否有来源、批次、时间窗口和签名或校验 |
| Difference | Fact 与 Statement 或 Fact 之间的差异 | 渠道成功但本地 unknown、账本借贷不平 | 是否能定位业务单、金额、状态和责任边界 |
| Case | 差错工单 | `CASE_PAYMENT_LOCAL_MISSING` | 是否有分类、证据、风险等级和状态机 |
| Repair | 修复命令和修复事实 | 补记账本、退款、冲正、调整、补差、罚金 | 是否幂等，是否追加事实 |
| Review | 审批和复核 | maker-checker 审批、复核失败、重新打开 | 是否有人、时间、证据和意见 |
| Close | 关闭事实 | 已修复关闭、无需修复关闭、长期挂起 | 是否有关闭原因和可审计证据 |

## 状态流

```text
DifferenceDetected
  -> CaseOpened
  -> Classified
  -> RepairProposed
  -> ReviewRequired / AutoRepairAllowed
  -> RepairExecuted
  -> Reviewed
  -> Closed / Reopened / LongTermSuspended
```

## 不可变边界

- 对账不能删除或覆盖历史 Fact。
- 对账不能用 Statement 直接覆盖本地事实，也不能用本地状态覆盖外部事实。
- 对账不能把 `PAYMENT_UNKNOWN`、`WITHDRAW_UNKNOWN`、`REFUND_UNKNOWN` 或 `SUPPLIER_UNKNOWN` 直接判失败。
- 对账不能用日志、workflow history、broker offset、consumer offset 或任务运行记录替代业务事实。
- Repair 必须追加 Repair Fact，并能被 Review 和 Close 解释。
- 高风险资金修复必须经过 maker-checker。

## 合格输出

一次合格对账输出的不是“数据已改平”，而是：差异是什么、证据是什么、分类是什么、谁审批、执行了什么修复、生成了哪些新事实、复核结果是什么、为什么可以关闭。
````

- [ ] **Step 2: Verify model anchors**

Run:

```bash
rg -n "Fact|Statement|Difference|Case|Repair|Review|Close|DifferenceDetected|CaseOpened|RepairExecuted|LongTermSuspended|maker-checker|workflow history|broker offset|consumer offset" financial-consistency/07-reconciliation/01-reconciliation-model.md
```

Expected: output includes model objects, state flow, and unsafe fact-source boundaries.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/07-reconciliation/01-reconciliation-model.md
git commit -m "docs: define reconciliation model"
```

Expected: commit succeeds and includes only `01-reconciliation-model.md`.

## Task 3: Create Reconciliation Sources Document

**Files:**
- Create: `financial-consistency/07-reconciliation/02-reconciliation-sources.md`

- [ ] **Step 1: Add source content**

Use `apply_patch` to create `financial-consistency/07-reconciliation/02-reconciliation-sources.md` with sections:

````markdown
# 02 对账数据源

## 目标

对账首先要回答哪些东西可以作为事实源，哪些只能作为执行线索。事实源可以参与判定 Difference；执行线索只能帮助定位问题。

## 可判定事实源

| 来源 | 典型事实 | 关键字段 | 常见风险 |
| --- | --- | --- | --- |
| 领域事实 | 订单、支付请求、退款请求、提现请求、供应商请求、售后单 | business_id、request_id、idempotency_key、state、version | 状态推进但账本或外部事实缺失 |
| 账本事实 | account movement、ledger posting、冲正分录、调整分录、日切批次 | ledger_id、account_id、debit、credit、posting_date、source_id | 借贷不平、缺业务来源、重复分录 |
| 渠道事实 | 支付流水、退款流水、提现结果、渠道账单、手续费 | channel_request_id、channel_txn_id、amount、currency、status、settle_date | 回调成功本地 unknown，账单迟到 |
| 供应商事实 | 供应商订单、出票、酒店确认、保险生效、供应商账单 | supplier_request_id、supplier_order_id、confirmation_no、bill_id | 迟到成功、迟到失败、罚金不可解释 |
| 库存和订单事实 | 预留、确认、释放、发货、取消、售后 | order_id、reservation_id、shipment_id、sku_id、quantity | 库存双终态，已发货被取消覆盖 |
| 清结算事实 | 商户结算、平台手续费、供应商结算、资金划拨 | settlement_id、merchant_id、supplier_id、fee、net_amount | 汇总平但明细不可解释 |
| 人工事实 | Case、证据快照、审批、修复命令、复核、关闭原因 | case_id、operator、reviewer、evidence_id、reason | 人工修复缺审批或复核 |

## 辅助线索

日志、trace、workflow history、broker offset、consumer offset、任务实例和报表生成记录只能说明系统执行过某些动作。它们不能单独证明支付成功、退款成功、供应商确认、库存释放、ledger posting 完成或人工修复完成。

## 匹配键

- 业务单号：`transfer_id`、`payment_request_id`、`refund_request_id`、`order_id`、`trip_id`。
- 幂等键：`idempotency_key`、`channel_request_id`、`supplier_request_id`、`repair_command_id`。
- 外部流水：`channel_txn_id`、`supplier_order_id`、`settlement_id`。
- 账本来源：`source_type`、`source_id`、`ledger_batch_id`。
- 时间窗口：业务发生时间、外部账单时间、入账时间、日切批次、清算日期。

## 数据质量要求

- 每个事实源必须有来源系统、批次或版本。
- 每条外部 Statement 必须保留原始证据或可追溯文件。
- 汇总对账不能替代明细对账。
- 报表只能读取事实和 Case 状态，不能反向修改事实。
- 任何缺字段导致无法匹配的记录必须进入 Difference 或数据质量 Case。

## 输出结论

对账数据源的底线是 Fact-first。真正能关闭差错的是可审计事实、修复事实、审批复核和关闭原因，不是日志、offset、workflow history 或报表展示。
````

- [ ] **Step 2: Verify source anchors**

Run:

```bash
rg -n "领域事实|账本事实|渠道事实|供应商事实|库存|清结算|人工事实|workflow history|broker offset|consumer offset|匹配键|汇总对账|明细对账" financial-consistency/07-reconciliation/02-reconciliation-sources.md
```

Expected: output includes all source categories and auxiliary clue boundaries.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/07-reconciliation/02-reconciliation-sources.md
git commit -m "docs: map reconciliation data sources"
```

Expected: commit succeeds and includes only `02-reconciliation-sources.md`.

## Task 4: Create Reconciliation Types Document

**Files:**
- Create: `financial-consistency/07-reconciliation/03-reconciliation-types.md`

- [ ] **Step 1: Add type content**

Use `apply_patch` to create `financial-consistency/07-reconciliation/03-reconciliation-types.md` with:

````markdown
# 03 对账类型

## 目标

不同对账类型解决不同时间尺度的问题。准实时对账适合尽早暴露分叉；日终对账适合批量账单和账本汇总；T+N 对账适合迟到账单、手续费、供应商和清算差异；专项重跑适合事故修复和版本修复后的再解释；人工复核负责自动规则无法关闭的高风险差异。

## 类型矩阵

| 类型 | 触发 | 输入 | 输出 | 不合格做法 |
| --- | --- | --- | --- | --- |
| 准实时对账 | 回调、查询、事件流、短周期任务 | 本地状态、渠道查询、供应商查询、消费者处理记录 | 初步 Difference、查询任务、人工挂起 | 把短暂延迟直接判失败 |
| 日终对账 | 日切后账单、账本、清算文件到齐 | 明细账单、账本批次、领域事实、汇总文件 | 日终 Case、金额差异、笔数差异 | 只看汇总不看明细 |
| T+N 对账 | 延迟账单、供应商账单、手续费、清算文件 | T 日事实、N 日外部 Statement、结算文件 | 迟到成功、迟到失败、手续费和结算差异 | 本地提前关闭 unknown |
| 专项重跑 | 修复后、事故后、版本修复后 | 历史 Fact、历史 Statement、已有 Case、修复事实 | 重新分类、重新打开、关闭确认 | 重跑重复执行修复 |
| 人工复核 | 自动规则无法收敛或金额风险较高 | 证据快照、分类结果、修复建议、审批记录 | 审批通过、拒绝、补证、长期挂起 | 人工直接 update 数据 |

## 时间窗口

- 准实时对账需要容忍渠道、供应商和消息系统的短暂延迟。
- 日终对账以日切批次和账单批次为边界。
- T+N 对账必须允许供应商账单、清算文件、手续费和汇率差异迟到。
- 专项重跑必须固定输入批次，保证可重放。
- 人工复核必须记录提交时间、审批时间、执行时间和关闭时间。

## 关闭条件

| 类型 | 允许关闭 |
| --- | --- |
| 准实时对账 | 后续事实到达并能解释，或升级为 Case |
| 日终对账 | 明细差异解释完成，修复事实和复核完成 |
| T+N 对账 | 迟到事实被记录，手续费、罚金、补差或清算差异被解释 |
| 专项重跑 | 重跑结果与已有 Case、Repair、Close 一致，或重新打开不一致 Case |
| 人工复核 | maker-checker 审批、修复事实、复核结果和关闭原因完整 |

## 输出结论

对账类型不能混成一个批处理任务。每种类型都必须说明输入事实、匹配键、时间窗口、容忍延迟、输出 Difference、Case 升级规则和关闭条件。
````

- [ ] **Step 2: Verify type anchors**

Run:

```bash
rg -n "准实时对账|日终对账|T\\+N|专项重跑|人工复核|时间窗口|关闭条件|短暂延迟|只看汇总|重跑重复执行修复|maker-checker" financial-consistency/07-reconciliation/03-reconciliation-types.md
```

Expected: output includes all reconciliation types and closing rules.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/07-reconciliation/03-reconciliation-types.md
git commit -m "docs: define reconciliation types"
```

Expected: commit succeeds and includes only `03-reconciliation-types.md`.

## Task 5: Create Difference Classification Document

**Files:**
- Create: `financial-consistency/07-reconciliation/04-difference-classification.md`

- [ ] **Step 1: Add classification content**

Use `apply_patch` to create `financial-consistency/07-reconciliation/04-difference-classification.md` with:

````markdown
# 04 差错分类

## 目标

差错分类要让系统知道差异属于什么边界、风险有多高、能不能自动修复、是否必须人工审批、怎样关闭。只写“金额不一致”无法指导修复。

## 分类矩阵

| 分类 | 判定依据 | 允许路径 | 禁止行为 |
| --- | --- | --- | --- |
| 本地少记 | 外部 Statement 成功，本地领域事实或账本事实缺失 | 补记领域事实、补记账本、创建人工 Case | 删除外部成功，重新发起扣款 |
| 本地多记 | 本地成功，外部账单不存在或明确失败 | 查询确认、冲正、退款、人工复核 | 直接把外部失败改成本地成功 |
| 外部多扣 | 渠道或供应商多扣、多结算、重复收费 | 退款、索赔、供应商调整、人工 Case | 靠本地账本分录掩盖外部多扣 |
| 外部少扣 | 本地认为成功，外部无资金或无供应商确认 | 补扣、取消、冲正、人工复核 | 已发货或已出票事实被删除 |
| 账本不平 | ledger posting 借贷不平、缺来源、与 account movement 冲突 | 追加调整分录、冲正分录、复核 | 删除原始账本分录 |
| 状态不一致 | 业务状态、渠道状态、供应商状态和账本状态冲突 | 状态机修复命令、人工审批、对账关闭 | 迟到失败覆盖外部成功 |
| unknown 未收敛 | `PAYMENT_UNKNOWN`、`WITHDRAW_UNKNOWN`、`REFUND_UNKNOWN`、`SUPPLIER_UNKNOWN` 长期无解释 | 查询、账单、T+N、人工挂起 | 直接判失败并重试外部副作用 |
| 重复业务效果 | 重复回调、消息重投、修复重放造成第二次效果 | 幂等拦截、冲正、差错 Case | 用 offset 证明业务完成 |
| 清结算差异 | 手续费、罚金、补差、汇率、商户或供应商结算不可解释 | 结算调整、补差、罚金、人工复核 | 只调汇总报表 |
| 人工修复缺证据 | 修复缺证据快照、审批、复核或关闭原因 | 重新打开 Case、补证、复核失败 | 用人工备注替代审批 |

## 风险等级

- P0：可能造成资金损失、重复扣款、重复退款、账本不平或不可逆外部动作丢失。
- P1：影响用户、商户、供应商或清结算准确性，但有明确冻结或挂起路径。
- P2：数据质量、报表展示或延迟到达导致的可解释差异。
- P3：无需修复但必须记录关闭原因的差异。

## 处理规则

- 能自动修复的分类必须有幂等 Repair Command。
- 高风险资金修复必须进入 maker-checker。
- 不可逆外部事实必须保留，例如已出票、已生效保险、已确认供应商订单。
- 关闭 Case 前必须验证领域事实、账本事实、外部事实和人工事实互相解释。
- 长期 unknown 允许进入长期挂起，但必须有周期性复核和暴露金额。

## 输出结论

差错分类的价值是把 Difference 变成可执行处理路径。每个分类都必须绑定读取事实、判断规则、允许路径、禁止行为、风险等级和关闭条件。
````

- [ ] **Step 2: Verify classification anchors**

Run:

```bash
rg -n "本地少记|本地多记|外部多扣|外部少扣|账本不平|状态不一致|unknown 未收敛|重复业务效果|清结算差异|人工修复缺证据|P0|P1|P2|P3|maker-checker|长期挂起" financial-consistency/07-reconciliation/04-difference-classification.md
```

Expected: output includes all classifications and risk levels.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/07-reconciliation/04-difference-classification.md
git commit -m "docs: classify reconciliation differences"
```

Expected: commit succeeds and includes only `04-difference-classification.md`.

## Task 6: Create Repair Workflow Document

**Files:**
- Create: `financial-consistency/07-reconciliation/05-repair-workflow.md`

- [ ] **Step 1: Add repair workflow content**

Use `apply_patch` to create `financial-consistency/07-reconciliation/05-repair-workflow.md` with:

````markdown
# 05 修复闭环

## 目标

修复闭环的核心原则是：对账不能直接改平数据。所有修复都必须通过 Case、Repair Command、Repair Fact、Review 和 Close 留下证据。

## 标准流程

```text
DifferenceDetected
  -> CaseOpened
  -> EvidenceCaptured
  -> Classified
  -> RepairCommandCreated
  -> MakerApproved
  -> CheckerReviewed
  -> RepairExecuted
  -> RepairFactRecorded
  -> ReviewCompleted
  -> CaseClosed
```

## 自动修复

自动修复只适用于低风险、规则明确、幂等键完整的差异：

- 补记缺失的传播记录。
- 对重复 Case 做幂等合并。
- 对已确认重复消息生成重复处理记录。
- 对汇总报表缺失重新生成报表事实。

自动修复必须输出 `repair_command_id`、幂等键、输入证据、执行结果和 Repair Fact。

## 人工修复

人工修复适用于资金、账本、供应商不可逆事实、清结算和高风险状态差异：

- maker 提交修复建议和证据快照。
- checker 审核金额、事实来源、风险等级和修复命令。
- 执行修复后必须复核领域事实、账本事实、外部事实和人工事实。
- 复核失败必须重新打开 Case，不能关闭后再私下修数据。

## 禁止行为

- 对账 SQL 直接 update 业务状态。
- 删除原始账本分录来让报表平衡。
- 对已 capture 资金执行 void。
- 删除已出票、已确认供应商订单或已生效保险。
- 用人工备注替代 maker-checker、证据快照和复核结果。
- 修复命令没有幂等键，重复执行产生第二次资金效果。
- 关闭 Case 但没有关闭原因。

## 关闭原因

| 关闭原因 | 含义 | 必备证据 |
| --- | --- | --- |
| repaired | 已执行修复且复核通过 | Repair Fact、审批、复核结果 |
| external_late_fact_matched | 迟到外部事实到达并解释差异 | 外部 Statement、匹配记录 |
| no_repair_needed | 差异被证明为可解释时间差或数据质量噪声 | 判定规则、证据快照 |
| long_term_suspended | 自动和人工都无法短期收敛 | 暴露金额、责任人、复核周期 |
| reopened | 关闭后被新事实推翻 | 新事实、重新打开原因 |

## 输出结论

合格修复不是“状态改好了”，而是每个差异都能追溯到证据、命令、审批、执行、复核和关闭原因。对账系统本身必须比业务系统更重视可审计性。
````

- [ ] **Step 2: Verify repair workflow anchors**

Run:

```bash
rg -n "DifferenceDetected|CaseOpened|EvidenceCaptured|RepairCommandCreated|MakerApproved|CheckerReviewed|RepairFactRecorded|CaseClosed|自动修复|人工修复|禁止行为|关闭原因|repaired|long_term_suspended|reopened" financial-consistency/07-reconciliation/05-repair-workflow.md
```

Expected: output includes state flow, repair categories, forbidden actions, and close reasons.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/07-reconciliation/05-repair-workflow.md
git commit -m "docs: define reconciliation repair workflow"
```

Expected: commit succeeds and includes only `05-repair-workflow.md`.

## Task 7: Create Scenario Matrix Document

**Files:**
- Create: `financial-consistency/07-reconciliation/06-scenario-matrix.md`

- [ ] **Step 1: Add scenario matrix content**

Use `apply_patch` to create `financial-consistency/07-reconciliation/06-scenario-matrix.md` with sections for each scenario:

````markdown
# 06 场景矩阵

## 目标

场景矩阵把统一对账模型落回真实业务。每个场景都必须说明事实源、匹配键、差错分类、自动修复路径、人工处理边界和不合格修复。

## 总览

| 场景 | 对账重点 | 典型差错 |
| --- | --- | --- |
| 内部转账 | account movement、ledger posting、冻结、扣减、入账、冲正、调整 | 借贷不平、入账缺失、重复冲正、账本与账户流水不一致 |
| 充值提现 | 渠道流水、回调、查询、账单、退款、提现、手续费 | 渠道成功本地 unknown、重复回调、退款 unknown、提现受理后本地释放资金 |
| 电商下单 | 订单、支付、库存、退款、发货、售后、商户结算 | 已支付未发货、库存释放重复、退款缺账本、结算金额不一致 |
| 旅行组合预订 | 供应商订单、出票、酒店确认、保险生效、罚金、补差、退款 | 供应商迟到成功、已出票后本地失败、已生效保险被取消覆盖 |

## 内部转账

- 事实源：账户流水、account movement、ledger posting、Outbox 事件、消费者处理记录、冲正和调整分录、人工审批。
- 匹配键：transfer_id、ledger_source_id、account_id、idempotency_key。
- 差错分类：账本不平、本地少记、重复业务效果、人工修复缺证据。
- 自动修复：重投 Outbox、补消费者处理记录、生成对账 Case。
- 人工边界：补账、冲正、调整和关闭 Case 必须 maker-checker。
- 不合格修复：删除原始账本分录、用 broker offset 证明入账完成、重复执行冲正。

## 充值提现

- 事实源：支付请求、提现请求、退款请求、渠道流水、渠道查询结果、渠道账单、手续费、ledger posting、人工 Case。
- 匹配键：payment_request_id、withdraw_request_id、refund_request_id、channel_request_id、channel_txn_id。
- 差错分类：本地少记、本地多记、外部多扣、外部少扣、unknown 未收敛、清结算差异。
- 自动修复：渠道成功本地少记时补记可审计事实和账本；重复回调只生成幂等处理记录。
- 人工边界：退款 unknown、提现受理后本地释放资金、手续费差异和大额资金差异。
- 不合格修复：把 `PAYMENT_UNKNOWN` 直接判失败、重复退款、已 capture 资金 void。

## 电商下单

- 事实源：订单、支付、退款、库存预留、库存确认、库存释放、发货、售后、商户结算、账本分录。
- 匹配键：order_id、payment_request_id、refund_request_id、reservation_id、shipment_id、settlement_id。
- 差错分类：状态不一致、外部少扣、退款缺账本、库存与订单不一致、清结算差异。
- 自动修复：幂等合并重复消息、重建读模型、生成退款或结算差异 Case。
- 人工边界：已发货后取消、商户结算差异、库存与资金双边不一致。
- 不合格修复：删除已发货事实、重复释放库存、用汇总报表覆盖明细差异。

## 旅行组合预订

- 事实源：组合订单、子订单、供应商 request id、出票、酒店确认、保险生效、供应商账单、支付 capture、refund、罚金、补差、人工审批。
- 匹配键：trip_id、sub_item_id、supplier_request_id、supplier_order_id、payment_request_id、refund_request_id。
- 差错分类：供应商迟到、unknown 未收敛、外部多扣、外部少扣、状态不一致、清结算差异、人工修复缺证据。
- 自动修复：记录迟到供应商事实、生成 Case、关联供应商账单和本地子订单。
- 人工边界：已出票后酒店失败、保险已生效后取消、罚金补差、供应商账单与本地策略冲突。
- 不合格修复：删除已出票事实、删除已生效保险、用 workflow history completion 证明供应商确认。

## 输出结论

统一对账矩阵的价值是让每个业务场景都能回答同一组问题：事实从哪里来、用什么键匹配、差错属于哪类、能否自动修复、何时必须人工审批、哪些修复方式绝对不允许。
````

- [ ] **Step 2: Verify scenario anchors**

Run:

```bash
rg -n "内部转账|充值提现|电商下单|旅行组合预订|account movement|ledger posting|渠道成功本地 unknown|退款 unknown|库存释放重复|已出票|已生效保险|maker-checker|broker offset|workflow history" financial-consistency/07-reconciliation/06-scenario-matrix.md
```

Expected: output includes all scenarios, reconciliation facts, and unsafe repair boundaries.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/07-reconciliation/06-scenario-matrix.md
git commit -m "docs: map reconciliation scenarios"
```

Expected: commit succeeds and includes only `06-scenario-matrix.md`.

## Task 8: Create Verification and Audit Document

**Files:**
- Create: `financial-consistency/07-reconciliation/07-verification-and-audit.md`

- [ ] **Step 1: Add verification and audit content**

Use `apply_patch` to create `financial-consistency/07-reconciliation/07-verification-and-audit.md` with:

````markdown
# 07 验证与审计

## 目标

对账系统也会产生风险。它可能重复生成 Case、重复执行 Repair、错误关闭差错、遗漏审批、让报表反向修改事实，或者在重跑时制造第二次资金效果。因此，对账系统本身也必须被验证和审计。

## 核心不变量

| 不变量 | 失败示例 | 验证方式 |
| --- | --- | --- |
| Difference 幂等 | 同一差异无限生成重复 Case | 固定匹配键和差异指纹 |
| Repair 幂等 | 重复补账、重复退款、重复冲正 | repair_command_id 和业务唯一约束 |
| Close 可解释 | Case 关闭但无证据、修复或挂起原因 | Close 必须引用证据和 Review |
| 重跑安全 | 日终重跑或 T+N 重跑重复修复 | 重跑只能重新分类或重新打开 |
| 审计完整 | 人工修复缺操作者、审批或复核 | 审计链检查 |
| 报表只读 | 报表任务修改业务事实 | 报表权限和数据流验证 |

## 异常 History

需要验证这些 History：

- 同一渠道账单重复导入。
- 同一 Difference 被准实时对账和日终对账同时发现。
- Repair Command 提交后进程宕机，然后重试。
- maker 审批通过后 checker 拒绝。
- Case 关闭后 T+N 迟到事实到达。
- 日终重跑覆盖已有 Case 状态。
- 报表生成任务读到未关闭 Case。
- 人工修复和自动修复并发。

## 审计字段

每个 Case 至少要能追踪：

- case_id、difference_fingerprint、classification、risk_level。
- evidence_snapshot、source_batch、statement_id、fact_ids。
- maker、checker、operator、review_result。
- repair_command_id、repair_fact_ids、idempotency_key。
- close_reason、closed_by、closed_at、reopen_reason。

## 监控指标

- 新增 Case 数量和金额。
- P0/P1 暴露金额。
- unknown 年龄和长期挂起金额。
- 自动修复率、人工处理时长、复核失败率。
- 重开率、重复 Case 合并率、重跑差异数量。
- 渠道账单、供应商账单、清算文件延迟。
- 日终对账完成时间和失败批次。

## 与 06 验证实验室的连接

对账验证必须复用 06 的语言：History、Invariant、Oracle、Fault Injection 和 Replay。一次合格验证只能说明在已生成的对账 History 和不变量范围内没有发现不可解释事实，不能证明所有生产差异绝对安全。

## 输出结论

对账系统本身必须像资金系统一样被验证。它的成功标准不是 Case 数量归零，而是每个差异都能被事实、修复、审批、复核和关闭原因解释。
````

- [ ] **Step 2: Verify verification anchors**

Run:

```bash
rg -n "Difference 幂等|Repair 幂等|Close 可解释|重跑安全|审计完整|报表只读|异常 History|maker|checker|unknown 年龄|History|Invariant|Oracle|Fault Injection|Replay" financial-consistency/07-reconciliation/07-verification-and-audit.md
```

Expected: output includes invariants, audit fields, monitoring metrics, and 06 verification links.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/07-reconciliation/07-verification-and-audit.md
git commit -m "docs: define reconciliation verification and audit"
```

Expected: commit succeeds and includes only `07-verification-and-audit.md`.

## Task 9: Create Interview Synthesis Document

**Files:**
- Create: `financial-consistency/07-reconciliation/08-interview-synthesis.md`

- [ ] **Step 1: Add interview synthesis content**

Use `apply_patch` to create `financial-consistency/07-reconciliation/08-interview-synthesis.md` with:

````markdown
# 08 面试与架构评审表达

## 一句话回答

对账不是事后补丁，而是金融一致性的事实闭环：它读取业务、账本、外部、清结算和人工事实，发现 Difference，创建 Case，通过 Repair、Review 和 Close 把差异收敛成可解释、可审计、可复核的结果。

## 标准回答结构

1. 先说明为什么需要对账：外部系统不可控，消息会重复乱序，账单会迟到，人工修复也会出错。
2. 再说明事实源：领域事实、账本事实、渠道事实、供应商事实、清结算事实和人工事实。
3. 再说明差错模型：Difference、Case、Repair、Review、Close。
4. 再说明对账类型：准实时、日终、T+N、专项重跑、人工复核。
5. 再说明修复边界：不能直接改平数据，必须追加事实和审批复核。
6. 最后说明验证：对账系统本身也要验证幂等、重跑安全、审计完整和关闭条件。

## 高频问题

### 为什么有了分布式事务还需要对账？

分布式事务和一致性模式只能降低部分执行窗口的风险，不能控制外部渠道、供应商账单、清算文件、迟到回调、人工修复和报表差异。真实金融系统必须用对账发现剩余差异，并把差异收敛成可审计事实。

### 渠道回调成功但本地失败怎么办？

不能直接把本地改成功，也不能重新扣款。应该用渠道 request id 和 channel transaction id 关联本地请求，创建 Difference 和 Case，补记可审计领域事实或账本事实，必要时进入 maker-checker。

### 本地成功但渠道账单没有怎么办？

先查询和等待账单窗口。如果 T+N 后仍然无外部事实，应分类为本地多记或外部少扣，根据业务风险走冲正、补扣、取消、人工复核或长期挂起。

### 对账能不能直接把状态改成成功？

不能。对账只能生成 Difference、Case、Repair Command、Repair Fact、Review 和 Close。直接 update 状态会破坏审计链，也会让历史回放无法解释。

### 日终对账和准实时对账有什么区别？

准实时对账尽早暴露分叉，必须容忍短暂延迟。日终对账用账单、账本和清算批次做完整性检查，必须同时看明细和汇总。

### 人工修复如何避免变成不可审计后门？

人工修复必须有证据快照、maker-checker、幂等 Repair Command、Repair Fact、复核结果和关闭原因。人工备注不能替代审批和复核。

### 如何验证对账系统本身？

用异常 History 检查 Difference 幂等、Repair 幂等、重跑安全、Close 可解释、审计完整和报表只读。对账系统不能因为重跑、并发或人工操作制造新的不可解释事实。

## 评审底线

- 不接受“用了 Outbox/Saga/Temporal，所以不用对账”。
- 不接受“对账 SQL 直接 update 状态”。
- 不接受“只看汇总金额平，不看明细事实”。
- 不接受“workflow history、broker offset、日志或报表替代业务事实”。
- 不接受“unknown 直接判失败并重新外部扣款或退款”。
- 不接受“人工修复没有 maker-checker、证据和复核”。
- 不接受“Case 关闭没有关闭原因”。

## 面试收束

高级回答应该把对账讲成事实闭环：跨系统差异一定会发生，关键是系统能不能发现 Difference、创建 Case、执行幂等 Repair、完成 Review，并用 Close 证明差异已经被解释或进入可审计挂起。
````

- [ ] **Step 2: Verify interview anchors**

Run:

```bash
rg -n "为什么有了分布式事务还需要对账|渠道回调成功但本地失败怎么办|本地成功但渠道账单没有怎么办|对账能不能直接把状态改成成功|日终对账和准实时对账有什么区别|人工修复如何避免变成不可审计后门|如何验证对账系统本身|评审底线|workflow history|broker offset|maker-checker" financial-consistency/07-reconciliation/08-interview-synthesis.md
```

Expected: output includes all high-frequency questions and review bottom lines.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/07-reconciliation/08-interview-synthesis.md
git commit -m "docs: add reconciliation interview synthesis"
```

Expected: commit succeeds and includes only `08-interview-synthesis.md`.

## Task 10: Update Root README

**Files:**
- Modify: `financial-consistency/README.md`

- [ ] **Step 1: Add design spec link**

In `financial-consistency/README.md`, add this line to the formal design document list after the verification lab design link:

```markdown
- [2026-05-02-financial-consistency-reconciliation-design.md](../docs/superpowers/specs/2026-05-02-financial-consistency-reconciliation-design.md)
```

- [ ] **Step 2: Link phase 07 route**

Change:

```markdown
- 07-reconciliation
  准实时对账、日终对账、差错处理、人工补偿。
```

to:

```markdown
- [07-reconciliation](./07-reconciliation/README.md)
  准实时对账、日终对账、差错处理、人工补偿。
```

- [ ] **Step 3: Verify root README links**

Run:

```bash
rg -n "2026-05-02-financial-consistency-reconciliation-design.md|\./07-reconciliation/README.md" financial-consistency/README.md
```

Expected: output includes both links.

- [ ] **Step 4: Commit**

Run:

```bash
git add financial-consistency/README.md
git commit -m "docs: link reconciliation phase"
```

Expected: commit succeeds and includes only `financial-consistency/README.md`.

## Task 11: Final Documentation Verification

**Files:**
- Verify: `financial-consistency/07-reconciliation/**`
- Verify: `financial-consistency/README.md`

- [ ] **Step 1: Verify file list**

Run:

```bash
find financial-consistency/07-reconciliation -maxdepth 1 -type f | sort
```

Expected output:

```text
financial-consistency/07-reconciliation/01-reconciliation-model.md
financial-consistency/07-reconciliation/02-reconciliation-sources.md
financial-consistency/07-reconciliation/03-reconciliation-types.md
financial-consistency/07-reconciliation/04-difference-classification.md
financial-consistency/07-reconciliation/05-repair-workflow.md
financial-consistency/07-reconciliation/06-scenario-matrix.md
financial-consistency/07-reconciliation/07-verification-and-audit.md
financial-consistency/07-reconciliation/08-interview-synthesis.md
financial-consistency/07-reconciliation/README.md
```

- [ ] **Step 2: Verify README child links**

Run:

```bash
rg -n "\./01-reconciliation-model.md|\./02-reconciliation-sources.md|\./03-reconciliation-types.md|\./04-difference-classification.md|\./05-repair-workflow.md|\./06-scenario-matrix.md|\./07-verification-and-audit.md|\./08-interview-synthesis.md" financial-consistency/07-reconciliation/README.md
```

Expected: output includes all 8 child document links.

- [ ] **Step 3: Verify core reconciliation terms**

Run:

```bash
rg -n "Fact|Statement|Difference|Case|Repair|Review|Close|准实时对账|日终对账|T\\+N|专项重跑|maker-checker|审计|复核|关闭原因|不能直接改平数据" financial-consistency/07-reconciliation
```

Expected: output includes model, types, repair, audit, and boundary terms.

- [ ] **Step 4: Verify scenario coverage**

Run:

```bash
rg -n "内部转账|充值提现|电商下单|旅行组合预订|account movement|ledger posting|渠道成功本地 unknown|退款 unknown|库存释放重复|已出票|已生效保险|供应商迟到" financial-consistency/07-reconciliation
```

Expected: output includes all four scenario families and key reconciliation hazards.

- [ ] **Step 5: Verify fact-source boundaries**

Run:

```bash
rg -n "workflow history|broker offset|consumer offset|日志|报表|不能替代|不能单独证明|只读" financial-consistency/07-reconciliation
```

Expected: output confirms execution clues and reports are not business facts.

- [ ] **Step 6: Verify root README links**

Run:

```bash
rg -n "2026-05-02-financial-consistency-reconciliation-design.md|\./07-reconciliation/README.md" financial-consistency/README.md
```

Expected: output includes both links.

- [ ] **Step 7: Verify previous phases unchanged**

Run:

```bash
git diff --name-only main..HEAD -- financial-consistency/01-transfer financial-consistency/02-payment-recharge-withdraw financial-consistency/03-order-payment-inventory financial-consistency/04-travel-booking-saga financial-consistency/05-patterns financial-consistency/06-verification-lab
```

Expected: no output.

- [ ] **Step 8: Scan placeholders**

Run:

```bash
rg -n "TO[D]O|TB[D]|待[定]|占[位]|以[后]补|未[决]|大[概]|随[便]" financial-consistency/07-reconciliation financial-consistency/README.md
```

Expected: no output and exit code 1.

- [ ] **Step 9: Check whitespace**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 10: Check worktree**

Run:

```bash
git status --short
```

Expected: only unrelated pre-existing user changes may appear. No unstaged changes from `financial-consistency/07-reconciliation` or `financial-consistency/README.md`.

## Execution Notes

- Use an isolated worktree for implementation.
- Commit after each task.
- If a reviewer flags a transient README broken-link issue before all child files exist, fix it only if the final state would still be broken; otherwise verify it in Task 11.
- Preserve unrelated working tree changes such as `.obsidian/`, `Untitled.base`, or non-financial-consistency files.
- Do not introduce runnable services, dependencies, schemas, schedulers, or framework API details in this phase.
