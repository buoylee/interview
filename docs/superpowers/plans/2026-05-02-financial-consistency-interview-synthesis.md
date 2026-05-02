# Financial Consistency Interview Synthesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `08-interview-synthesis` capstone chapter that turns the whole financial consistency route into interview-ready and architecture-review-ready explanations.

**Architecture:** This is a documentation-only phase. Each document owns one synthesis concern: chapter navigation, master narrative, architecture review playbook, question bank, scenario drills, unsafe answers, seniority rubric, and final study sheet. The chapter links back conceptually to phases `01` through `07` and only modifies the root route README to link the new module.

**Tech Stack:** Markdown, Git, `rg`, `find`, `git diff --check`. No Java service, Go tooling, database schema, Kafka, Temporal, Seata, Camunda, payment-channel integration, or supplier integration is introduced in this phase.

---

## File Structure

- Create directory: `financial-consistency/08-interview-synthesis/`
- Create: `financial-consistency/08-interview-synthesis/README.md`
- Create: `financial-consistency/08-interview-synthesis/01-master-narrative.md`
- Create: `financial-consistency/08-interview-synthesis/02-architecture-review-playbook.md`
- Create: `financial-consistency/08-interview-synthesis/03-question-bank.md`
- Create: `financial-consistency/08-interview-synthesis/04-scenario-drills.md`
- Create: `financial-consistency/08-interview-synthesis/05-red-flags-and-bad-answers.md`
- Create: `financial-consistency/08-interview-synthesis/06-senior-answer-rubric.md`
- Create: `financial-consistency/08-interview-synthesis/07-final-summary.md`
- Modify: `financial-consistency/README.md`

Do not modify:

- `financial-consistency/01-transfer/**`
- `financial-consistency/02-payment-recharge-withdraw/**`
- `financial-consistency/03-order-payment-inventory/**`
- `financial-consistency/04-travel-booking-saga/**`
- `financial-consistency/05-patterns/**`
- `financial-consistency/06-verification-lab/**`
- `financial-consistency/07-reconciliation/**`

## Task 1: Create Capstone README

**Files:**
- Create: `financial-consistency/08-interview-synthesis/README.md`

- [ ] **Step 1: Create directory**

Run:

```bash
mkdir -p financial-consistency/08-interview-synthesis
```

Expected: command succeeds.

- [ ] **Step 2: Add README content**

Use `apply_patch` to create `financial-consistency/08-interview-synthesis/README.md` with:

````markdown
# 08 面试与架构评审综合表达

## 目标

这一章是整条金融级一致性路线的收束。它不再引入新的事务模式，也不重复每个场景的细节，而是把前面章节压缩成一套可以在面试、架构评审、方案答辩和事故复盘中讲清楚的表达体系。

最终目标不是背诵“分布式事务有哪些方案”，而是能回答：

- 这个业务到底要保护哪些事实？
- 哪些不变量绝对不能被破坏？
- 哪些状态是确定成功、确定失败、未知、待对账、待修复？
- 为什么选 Outbox、TCC、Saga、Temporal、2PC 或本地事务？
- 如何证明系统在重复、乱序、超时、宕机、迟到回调、供应商不可控时仍然安全？
- 对账发现差异后，如何修复、审批、复核和审计？

## 学习顺序

1. [总叙事](./01-master-narrative.md)
2. [架构评审话术](./02-architecture-review-playbook.md)
3. [常见问题题库](./03-question-bank.md)
4. [场景演练](./04-scenario-drills.md)
5. [危险回答与反例](./05-red-flags-and-bad-answers.md)
6. [高级回答评分标准](./06-senior-answer-rubric.md)
7. [最终速查表](./07-final-summary.md)

## 本章定位

前面章节分别解决局部问题：

- `01-transfer` 建立资金不变量和账本意识。
- `02-payment-recharge-withdraw` 引入外部渠道、回调、轮询和未知结果。
- `03-order-payment-inventory` 处理支付、订单、库存、取消和退款。
- `04-travel-booking-saga` 处理多个外部供应商和不可逆动作。
- `05-patterns` 比较 Outbox、TCC、Saga、Temporal、Seata、Camunda、2PC 等模式。
- `06-verification-lab` 建立不变量、故障注入和科学验证方法。
- `07-reconciliation` 建立差异发现、差错分类、修复、复核和关闭闭环。

本章把这些内容合并成一套最终表达模型：事实优先、状态显式、模式有边界、未知不乱判、修复要审批、关闭要证据。

## 合格输出

学完本章后，面对“如何设计一个金融级一致性系统”的问题，应该能按以下顺序作答：

1. 先定义业务影响和权威事实。
2. 再定义不变量和状态机。
3. 再说明事务边界、异步边界和幂等边界。
4. 再选择一致性模式，并解释为什么没有选择其他模式。
5. 再说明如何验证、压测、注入故障和检查历史。
6. 最后说明如何对账、修复、审批、复核、审计和关闭。

核心结论：金融级一致性不是某个框架的能力，而是一套从设计、执行、验证、对账到审计的事实闭环。
````

- [ ] **Step 3: Verify README links**

Run:

```bash
rg -n "\./01-master-narrative.md|\./02-architecture-review-playbook.md|\./03-question-bank.md|\./04-scenario-drills.md|\./05-red-flags-and-bad-answers.md|\./06-senior-answer-rubric.md|\./07-final-summary.md" financial-consistency/08-interview-synthesis/README.md
```

Expected: output includes all 7 child document links.

- [ ] **Step 4: Commit**

Run:

```bash
git add financial-consistency/08-interview-synthesis/README.md
git commit -m "docs: add interview synthesis module entry"
```

Expected: commit succeeds and includes only `financial-consistency/08-interview-synthesis/README.md`.

## Task 2: Create Master Narrative

**Files:**
- Create: `financial-consistency/08-interview-synthesis/01-master-narrative.md`

- [ ] **Step 1: Add master narrative**

Use `apply_patch` to create `financial-consistency/08-interview-synthesis/01-master-narrative.md` with:

````markdown
# 01 总叙事

## 一句话

金融级一致性不是神秘的分布式事务技术，而是围绕权威事实、不变量、状态机、幂等副作用、可观测未知、验证、对账、修复和审计建立的闭环。

## 为什么本地事务不够

本地数据库事务只能保证单个数据库内的 ACID。它能保证一次账户扣款和流水写入在同一个库内同时成功或同时失败，但它不能保证：

- 支付渠道一定收到请求。
- 支付渠道的回调一定送达。
- MQ 消息一定按预期时间被消费。
- 供应商一定支持取消或补偿。
- 工作流历史就等于资金事实。
- 外部账单一定和本地状态同时到达。

所以金融系统的核心问题不是“怎么把所有东西放进一个大事务”，而是承认外部系统、消息系统、工作流引擎和人工流程都不在同一个事务边界内，然后把它们纳入可解释的事实闭环。

## 成功的定义

在金融场景里，成功不能只看技术动作：

| 技术动作 | 为什么不等于业务成功 |
| --- | --- |
| API 返回成功 | 对方可能只是受理，请求结果仍未知 |
| 本地事务提交 | 外部渠道、供应商、清结算事实可能还没闭合 |
| MQ publish 成功 | 只说明消息进入传输系统，不说明业务事实完成 |
| consumer offset 提交 | 只说明消费进度推进，不说明业务状态安全 |
| workflow step 完成 | 只说明编排动作完成，不说明资金事实已经成立 |
| 报表对平 | 汇总对平可能掩盖明细错误 |

业务成功应该由权威事实闭合来定义。例如充值场景中，只有本地支付单、账本入账、渠道成功事实、结算事实和对账证据能互相解释，才能说资金事实闭合。

## 从转账到真实世界

最简单的转账只需要保护账户余额、冻结金额、流水和账本借贷平衡。这个阶段可以学习：

- 每笔资金变化都必须有来源。
- 借贷必须平衡。
- 重复请求不能重复扣款。
- 状态机不能跳过中间状态。

充值和提现引入外部渠道后，系统必须接受 unknown：

- 渠道请求超时，不代表失败。
- 回调迟到，不代表重复成功。
- 本地成功但渠道无账单，不能自动认为渠道成功。
- 渠道成功但本地缺单，需要补建或挂账处理。

订单、支付和库存把一致性扩展到用户可见履约：

- 支付成功但库存失败，不能简单退款了事，还要看商品、履约、用户承诺和补偿窗口。
- 库存释放、订单取消、退款发起必须互相解释。
- 发货后取消不能覆盖已履约事实。

旅行预订把问题推到更真实的边界：

- 航班、酒店、租车、保险来自不同供应商。
- 某些动作不可逆，某些补偿会产生罚金。
- Saga 只能编排业务补偿，不能消除真实世界的不确定性。

模式章节解决选择问题，验证章节解决“怎么证明”，对账章节解决“生产中一定会有差异时怎么闭环”。

## 最终心智模型

可以把金融级一致性表达成六层：

1. 事实层：哪些东西是权威事实，哪些只是日志、消息、视图或线索。
2. 不变量层：哪些条件永远不能被破坏。
3. 状态层：所有成功、失败、处理中、未知、待对账、待修复状态都要显式。
4. 执行层：本地事务、Outbox、TCC、Saga、Temporal、2PC 等只负责特定边界内的执行。
5. 验证层：用属性测试、故障注入、历史检查和模型推演证明系统没有破坏不变量。
6. 闭环层：用对账、差错分类、修复审批、复核和审计处理执行层无法完全消除的现实差异。

## 面试表达模板

遇到金融一致性题，可以这样开始：

> 我不会先选一个分布式事务框架，而是先定义业务事实和不变量。比如这类系统至少要保证资金不能凭空增加或消失、同一外部请求不能重复入账、状态不能从未知直接改成失败、账本分录必须可追溯。然后我会划分本地事务边界和外部系统边界。本地库内用 ACID 和唯一约束保证原子性；跨服务用 Outbox、幂等消费和状态机；外部渠道或供应商返回不确定时进入 unknown，由轮询、回调和对账共同闭环。最后用故障注入、属性测试、历史检查和对账修复机制证明生产中出现重复、乱序、超时和迟到结果时也不会破坏核心不变量。

这段回答的重点是：先讲正确性，再讲模式；先讲事实，再讲框架；先讲边界，再讲实现。
````

- [ ] **Step 2: Verify required concepts**

Run:

```bash
rg -n "权威事实|不变量|状态机|unknown|Outbox|TCC|Saga|Temporal|2PC|验证|对账|审计|业务成功|workflow step|MQ publish" financial-consistency/08-interview-synthesis/01-master-narrative.md
```

Expected: output includes the master thesis, pattern names, unknown-state handling, and completion-vs-execution distinction.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/08-interview-synthesis/01-master-narrative.md
git commit -m "docs: add financial consistency master narrative"
```

Expected: commit succeeds and includes only `01-master-narrative.md`.

## Task 3: Create Architecture Review Playbook

**Files:**
- Create: `financial-consistency/08-interview-synthesis/02-architecture-review-playbook.md`

- [ ] **Step 1: Add playbook content**

Use `apply_patch` to create `financial-consistency/08-interview-synthesis/02-architecture-review-playbook.md` with:

````markdown
# 02 架构评审话术

## 目标

架构评审不是展示用了多少中间件，而是证明这个设计在真实失败条件下仍然能保护业务事实。本文件给出一条稳定的讲解顺序，避免一上来就陷入框架名词。

## 推荐讲解顺序

### 1. 定义场景和影响

先说清楚业务是什么，错误会伤害谁。

示例：

> 这是一个提现系统。用户发起提现后，我们要从平台余额扣减资金，并通过外部渠道出款。风险是重复出款、少出款、本地成功但渠道失败、渠道成功但本地未知、以及对账时无法解释资金去向。

### 2. 定义权威事实

必须区分事实和线索。

| 类型 | 可以作为事实吗 | 说明 |
| --- | --- | --- |
| 支付单、提现单、订单、退款单 | 可以 | 领域事实 |
| 账本分录 | 可以 | 资金事实 |
| 渠道账单、供应商账单、清算文件 | 可以 | 外部事实 |
| MQ 消息 | 不能单独作为事实 | 只能说明传播意图或执行线索 |
| workflow history | 不能单独作为资金事实 | 只能说明编排动作 |
| 日志和 trace | 不能单独作为事实 | 只能辅助排查 |
| 报表 | 不能替代明细事实 | 只能作为派生视图 |

### 3. 定义不变量

不变量要具体到可以测试。

示例：

- 同一 `idempotency_key` 不能产生两次资金入账。
- 已成功的渠道流水不能没有本地解释。
- 本地账本借贷必须平衡。
- `UNKNOWN` 不能被无证据地改成 `FAILED`。
- 对账修复不能覆盖历史分录，只能追加修复事实。

### 4. 定义状态机

状态机要显式表达未知和人工闭环。

```text
INIT
  -> ACCEPTED
  -> PROCESSING
  -> SUCCESS
  -> FAILED
  -> UNKNOWN
  -> RECONCILING
  -> REPAIR_PENDING
  -> REPAIRED
  -> CLOSED
```

评审时要说明：

- 哪些状态由本地事务推进。
- 哪些状态由回调推进。
- 哪些状态由轮询推进。
- 哪些状态只能由对账或人工审批推进。
- 哪些状态不能直接跳转。

### 5. 定义事务边界

本地事务只保护本服务内的事实。例如：

- 写提现单。
- 冻结或扣减余额。
- 写账本分录。
- 写 Outbox 事件。

这些可以在一个数据库事务内完成。调用外部渠道不能放进本地数据库事务里，外部渠道也不会参与本地 rollback。

### 6. 定义异步和幂等边界

跨服务或跨系统时，要说明：

- 生产端用 Outbox 避免本地提交成功但消息丢失。
- 消费端用幂等表、唯一约束、业务状态版本避免重复处理。
- 每个外部请求都有稳定 request id。
- 重试只允许重试幂等命令，不能重试非幂等副作用。
- 回调和轮询结果必须走同一状态机收敛。

### 7. 定义未知状态

强回答必须承认未知。

示例：

> 调用渠道超时后，我不会把提现改成失败，因为渠道可能已经出款。我会把它改成 `CHANNEL_UNKNOWN`，启动查询和对账。只有渠道明确失败且没有出款证据时，才能进入失败或解冻；如果渠道账单显示成功但本地仍 unknown，要按外部成功事实补齐本地状态和账本解释。

### 8. 选择模式并解释取舍

| 模式 | 适合 | 不适合 |
| --- | --- | --- |
| 本地事务 | 单库内账户、流水、Outbox 原子写入 | 跨外部渠道原子提交 |
| Outbox | 本地事实和消息传播一致 | 保证下游一定业务成功 |
| TCC | 可 Try、Confirm、Cancel 的资源预留 | 不支持取消的外部动作 |
| Saga | 多步骤业务流程和补偿 | 把不可逆动作变回原子事务 |
| Temporal | 长流程编排、重试、超时、可观测执行 | 替代账本和业务事实 |
| 2PC | 少数强控制同构资源 | 互联网外部渠道、供应商和高可用场景 |

评审话术：

> 我选的不是一个万能模式，而是按边界组合：账户和账本用本地事务，消息传播用 Outbox，外部渠道用幂等请求加 unknown 状态，长流程用 Saga 或 Temporal 编排，对账和修复处理最终差异。

### 9. 定义验证策略

验证要覆盖正常路径和失败路径：

- 属性测试：任何操作序列都不能让余额凭空增加或账本不平。
- 故障注入：在本地提交后、消息发送前、回调前、消费后宕机。
- 历史检查：检查状态跳转是否合法。
- 重复和乱序测试：重复回调、迟到回调、重复消费、轮询和回调竞争。
- 对账演练：构造本地成功外部失败、外部成功本地缺失、金额不一致。

### 10. 定义对账、修复和审计

最后必须说明生产闭环：

- 对账读取领域事实、账本事实、渠道事实、供应商事实和清结算事实。
- 差异进入 Case，而不是直接 update。
- 修复命令必须幂等。
- 高风险修复需要 maker-checker。
- 关闭必须有证据和原因。
- 审计记录要能回答谁发现、谁审批、谁执行、执行了什么、为什么关闭。

## 常见追问

### 如果面试官问：你怎么证明不会重复扣款？

强回答：

> 我会从请求、状态和账本三层防重。入口有 idempotency key 和唯一约束；状态机要求同一业务单只能从可执行状态推进一次；账本分录有 source id 唯一约束，重复消费最多命中已有分录，不能再生成一次扣款。同时用重复请求、重复消息、重复回调的测试验证这个约束。

### 如果面试官问：为什么不用 2PC？

强回答：

> 2PC 只适合少数同构、可控、能接受阻塞和协调器风险的资源。支付渠道、供应商和清结算系统不会参与我们的 2PC。真实方案要承认边界不可控，用本地事务保护本地事实，用幂等和状态机处理外部结果，用对账处理迟到和差异。

### 如果面试官问：Temporal 能不能保证一致性？

强回答：

> Temporal 可以让长流程执行更可靠、可重试、可观察，但它的 workflow history 不是资金事实。资金状态仍然要落在业务库和账本里，外部渠道结果仍然要用渠道流水和对账证明。Temporal 是编排层，不是账本层。

## 评审收束句

一个成熟方案最后应该能这样收束：

> 这个设计的安全性不依赖单个中间件，而依赖事实闭环：本地事务保证本地事实原子写入，Outbox 保证事实向外传播，幂等和状态机吸收重复乱序，unknown 状态承接外部不确定性，验证证明不变量，对账和审计处理生产差异。
````

- [ ] **Step 2: Verify review sequence**

Run:

```bash
rg -n "定义场景|定义权威事实|定义不变量|定义状态机|定义事务边界|定义异步|定义未知状态|选择模式|定义验证策略|定义对账|Temporal 是编排层" financial-consistency/08-interview-synthesis/02-architecture-review-playbook.md
```

Expected: output includes all 10 review steps and the Temporal boundary statement.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/08-interview-synthesis/02-architecture-review-playbook.md
git commit -m "docs: add architecture review playbook"
```

Expected: commit succeeds and includes only `02-architecture-review-playbook.md`.

## Task 4: Create Question Bank

**Files:**
- Create: `financial-consistency/08-interview-synthesis/03-question-bank.md`

- [ ] **Step 1: Add question bank**

Use `apply_patch` to create `financial-consistency/08-interview-synthesis/03-question-bank.md` with:

````markdown
# 03 常见问题题库

## 使用方式

不要把这些问题当成背诵题。每个回答都要回到同一套结构：事实、不变量、状态机、边界、模式、验证、对账。

## 转账与账本

### Q1：A 给 B 转账，如何保证不会多扣或少加？

答：先定义资金不变量：A 的扣减、B 的增加、账本借贷分录必须在同一个本地事务中完成，或者在明确的冻结/确认状态机中完成。入口用 `transfer_id` 或 `idempotency_key` 做唯一约束；账本分录用 `source_id` 防重复；状态机禁止同一转账重复 confirm。验证上要构造重复请求、事务中断、重复消息和恢复重放，检查总余额、可用余额、冻结余额和借贷平衡。

### Q2：为什么账本不能只用账户余额表替代？

答：余额是当前视图，账本是资金事实。只看余额无法解释钱从哪里来、到哪里去、谁触发、是否被冲正。金融系统需要可追溯、可审计、可重放的流水和分录，余额应该由账本事实解释，而不是替代账本事实。

## 充值、提现和外部渠道

### Q3：调用支付渠道超时后怎么处理？

答：不能直接判失败。超时只说明本系统没有拿到确定结果，渠道可能已经成功。正确做法是进入 `CHANNEL_UNKNOWN` 或类似状态，使用渠道查询、回调、补偿轮询和对账收敛。只有拿到明确失败证据且没有成功流水时，才能失败关闭或解冻。

### Q4：渠道回调重复到达怎么办？

答：回调必须幂等。用 `channel_txn_id`、`channel_request_id` 或业务单号建立唯一约束；状态机只允许从待确认或 unknown 推进到成功一次；重复回调只能返回已有结果，不能重复入账。回调处理还要和主动查询共享同一状态推进逻辑，避免竞争写出两个终态。

### Q5：本地显示成功，但渠道账单没有这笔，怎么办？

答：这不是简单的展示问题，而是对账差异。应该创建差错 Case，收集本地支付单、账本分录、渠道请求记录、渠道账单窗口和结算证据。没有外部成功或结算证据时，不能继续把渠道成功当成事实。修复可能是冲正、退款、挂账、人工调查或长期挂起，必须有审批、复核和审计。

## 订单、支付和库存

### Q6：订单支付成功但库存预留失败怎么办？

答：先看业务承诺。如果支付成功发生在库存确认前，系统必须进入异常履约或退款流程，而不是让订单继续成功。库存预留、订单状态、支付状态和退款状态要有明确状态机。修复策略可能是重试预留、换仓、人工履约、取消订单并退款。关键是支付事实不能被库存失败覆盖，库存失败也不能被支付成功掩盖。

### Q7：取消订单和支付回调乱序怎么办？

答：要把订单、支付和退款拆成不同事实。取消请求到达时，如果支付仍 unknown，可以进入取消中或待退款判断；迟到支付成功回调到达时，不能忽略，必须根据订单状态触发退款或异常 Case。不能用最后到达的事件覆盖之前的事实。

## Saga 和供应商预订

### Q8：机票成功、酒店失败，Saga 补偿是否一定能恢复原状？

答：不能。Saga 补偿是业务动作，不是时间倒流。有些供应商取消会失败，有些会产生罚金，有些出票后不可退。正确设计要在状态机里显式记录 flight success、hotel failed、cancel pending、penalty charged、refund pending 等事实，并通过对账确认供应商账单和本地责任。

### Q9：什么时候用 Temporal 编排？

答：当流程长、步骤多、超时和重试复杂、需要可观察执行历史时，Temporal 很合适。但它不替代业务事实、账本和渠道事实。工作流活动要写业务库，业务库状态和账本仍是判定资金正确性的事实来源。

## 模式选择

### Q10：Outbox 解决了什么，没解决什么？

答：Outbox 解决本地事务提交和消息发布之间的不一致：业务事实和待发布事件在同一个本地事务里落库。但它不保证下游一定成功，也不保证外部渠道成功。消费者仍然要幂等，业务仍然需要状态机、重试、死信、告警和对账。

### Q11：TCC 适合什么？

答：TCC 适合资源可预留、可确认、可取消的场景，比如冻结余额、预留库存。它不适合已经不可逆的外部支付成功、出票成功、已发货等场景。Try、Confirm、Cancel 都要幂等，并且要处理空回滚、悬挂和重复 confirm。

### Q12：强一致是不是意味着不能异步？

答：不是。强一致要先说明边界。单账户账本写入可以在本地事务内强一致；跨外部渠道或供应商时，无法用一个全局事务强制所有系统同时提交。此时要用显式状态、幂等、验证和对账实现业务可解释的一致性，而不是假装没有异步。

## 验证和故障注入

### Q13：如何科学地找出事务一致性问题？

答：先写出不变量，再生成或枚举操作序列和失败点。对每个失败点做故障注入：提交前宕机、提交后消息前宕机、消息重复、回调迟到、查询超时、人工修复重复执行。然后用属性测试、历史检查和对账检查验证余额、账本、状态机和外部事实是否仍可解释。

### Q14：为什么只写正常集成测试不够？

答：一致性 bug 常出现在非正常路径：重复、乱序、超时、部分成功、迟到结果、恢复重放。正常路径只能证明 happy path 能跑通，不能证明不变量在真实故障下不被破坏。

## 对账、修复和审计

### Q15：为什么有了 Saga 和 Outbox 还需要对账？

答：因为它们不能控制外部世界。渠道账单可能迟到，供应商可能人工改状态，清结算可能有汇率、手续费或批次差异，人工操作也可能产生修复事实。对账是把执行时无法完全确定的事实在事后闭环，不是事后补丁。

### Q16：对账发现差异后为什么不能直接 update？

答：直接 update 会破坏历史可解释性。正确做法是创建 Case，分类风险，提出 Repair，审批后追加修复事实，再复核关闭。资金系统要能解释每一次变化，而不是让历史看起来像从未出错。

### Q17：如何回答审计追问？

答：要能回答：谁发起、谁审批、谁执行、依据哪些事实、改动了哪些状态或账本、是否幂等、谁复核、为什么关闭。审计看的是证据链，不是口头保证。
````

- [ ] **Step 2: Verify question coverage**

Run:

```bash
rg -n "Q1|Q5|Q8|Q10|Q13|Q15|转账|充值|提现|订单|库存|Saga|Temporal|Outbox|TCC|对账|审计" financial-consistency/08-interview-synthesis/03-question-bank.md
```

Expected: output includes questions across transfer, external channel, order inventory, Saga, patterns, verification, reconciliation, and audit.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/08-interview-synthesis/03-question-bank.md
git commit -m "docs: add financial consistency question bank"
```

Expected: commit succeeds and includes only `03-question-bank.md`.

## Task 5: Create Scenario Drills

**Files:**
- Create: `financial-consistency/08-interview-synthesis/04-scenario-drills.md`

- [ ] **Step 1: Add scenario drills**

Use `apply_patch` to create `financial-consistency/08-interview-synthesis/04-scenario-drills.md` with:

````markdown
# 04 场景演练

## 使用方式

每个演练都按同一套结构回答：问题、事实、不变量、状态、模式、验证、对账修复、面试回答。

## 演练 1：内部账户转账

### 问题

A 给 B 转账 100 元，请求可能重复，服务可能在扣款后宕机。

### 事实

- 转账单。
- A/B 账户余额和冻结金额。
- 借方和贷方账本分录。
- 幂等请求记录。

### 不变量

- 同一转账不能重复扣款。
- 借贷分录必须平衡。
- 总资金不能凭空增加或消失。

### 状态

`INIT -> DEBITED -> CREDITED -> SUCCESS`，异常时进入 `REPAIR_REQUIRED`，不能跳过账本校验直接成功。

### 模式

同库内优先本地事务；跨账户分库时要引入冻结、确认、Outbox 和对账。

### 验证

重复请求、扣款后宕机、入账前宕机、恢复重放、重复消息。

### 对账修复

检查转账单、借方分录、贷方分录和账户余额视图是否互相解释。缺贷方分录时追加补充分录，不覆盖原借方分录。

### 面试回答

> 我会先保证转账单和账本分录有唯一来源，重复请求只能命中同一转账。单库场景用本地事务保护借贷分录；跨库场景用冻结和确认状态机，并用 Outbox 推动后续动作。任何中断都通过账本对账发现，修复只能追加事实。

## 演练 2：充值渠道成功但回调延迟

### 问题

用户充值，渠道实际扣款成功，但回调 30 分钟后才到。

### 事实

- 本地充值单。
- 渠道请求号和渠道流水号。
- 账本入账分录。
- 渠道账单和结算批次。

### 不变量

- 渠道成功只能入账一次。
- 回调迟到不能导致重复入账。
- 没有渠道成功证据不能凭空给用户加钱。

### 状态

`REQUESTED -> CHANNEL_PENDING -> CHANNEL_UNKNOWN -> SUCCESS`。迟到回调从 unknown 收敛到 success。

### 模式

本地事务写充值单和 Outbox；渠道调用幂等；回调和主动查询共用状态推进；对账兜底。

### 验证

重复回调、查询和回调并发、回调迟到、渠道账单迟到、本地成功后宕机。

### 对账修复

如果渠道账单成功但本地未入账，创建 Case，审批后补记入账分录；如果本地入账但渠道无成功证据，进入风险 Case，不自动认定成功。

### 面试回答

> 渠道超时或回调延迟时，我会把状态保持在 pending 或 unknown，不会直接失败。迟到成功通过幂等状态机入账一次；如果回调一直不到，用渠道查询和对账确认事实。

## 演练 3：提现本地成功但供应商结果未知

### 问题

本地提现单已经扣减余额并提交出款请求，但渠道返回超时。

### 事实

- 提现单。
- 冻结、扣减或出款账本分录。
- 渠道出款请求。
- 渠道出款结果或账单。

### 不变量

- 不能重复出款。
- unknown 不能直接失败并解冻。
- 渠道成功必须有本地账本解释。

### 状态

`ACCEPTED -> FUNDS_LOCKED -> CHANNEL_SUBMITTED -> CHANNEL_UNKNOWN -> SUCCESS / FAILED / REPAIR_REQUIRED`。

### 模式

冻结余额用本地事务；出款请求用幂等 channel request id；unknown 由查询、回调和对账收敛。

### 验证

渠道超时后重复提交、回调迟到、查询失败、渠道成功但本地重启、人工修复重复执行。

### 对账修复

渠道成功但本地 unknown：补齐成功状态和出款事实。渠道明确失败且无出款证据：解冻或冲正。渠道无最终证据：长期挂起并人工跟进，不能自动退款或二次出款。

### 面试回答

> 提现最危险的是把超时当失败，因为可能造成重复出款。我会把超时作为 unknown，并保证后续查询、回调、对账都只能推进同一状态机。

## 演练 4：电商订单已支付但库存预留超时

### 问题

用户支付成功后，库存服务预留超时，订单不能确认履约。

### 事实

- 订单。
- 支付单和渠道流水。
- 库存预留记录。
- 退款单或履约异常单。

### 不变量

- 支付成功不能被库存失败覆盖。
- 库存不能出现预留和释放双终态。
- 已承诺履约和退款不能同时作为最终成功。

### 状态

订单：`PENDING_PAYMENT -> PAID -> FULFILLMENT_PENDING -> FULFILLMENT_FAILED / CONFIRMED / REFUNDING`。

### 模式

支付事实和订单事实分离；库存预留使用 TCC 或本地预留状态；跨服务事件用 Outbox；异常走退款或人工履约 Saga。

### 验证

支付回调和取消乱序、库存重复预留、释放后确认、退款重复发起、消息重复消费。

### 对账修复

对账订单、支付、库存、退款和发货事实。支付成功但无履约或退款解释时创建 Case。

### 面试回答

> 支付成功和库存成功是两个事实，不能互相覆盖。库存失败后要进入异常履约或退款流程，并通过对账确认最终是履约、退款还是人工处理。

## 演练 5：机票成功、酒店失败、退款延迟

### 问题

用户购买机票加酒店套餐，机票出票成功，酒店预订失败，退款需要 T+1 才能确认。

### 事实

- 组合订单。
- 航班供应商订单。
- 酒店供应商订单。
- 支付和退款流水。
- 供应商罚金或取消账单。

### 不变量

- 已出票事实不能被酒店失败删除。
- 退款 pending 不能当作退款成功。
- 供应商罚金必须有责任归属和账本解释。

### 状态

`PACKAGE_PROCESSING -> FLIGHT_CONFIRMED -> HOTEL_FAILED -> COMPENSATION_PENDING -> REFUND_UNKNOWN -> REFUNDED / MANUAL_REVIEW`。

### 模式

Saga 或 Temporal 编排业务流程；供应商请求幂等；不可逆动作进入补偿和对账闭环。

### 验证

酒店失败后机票取消失败、退款迟到、供应商账单金额不一致、Temporal activity 重试、人工补偿重复。

### 对账修复

核对供应商订单、支付退款、罚金和用户补偿。不能简单把 Saga 结束当作资金闭合。

### 面试回答

> Saga 只能表达业务补偿流程，不能保证恢复原状。机票成功就是事实，酒店失败后要处理取消、罚金、退款和用户承诺，并用供应商账单和资金账本对账。

## 演练 6：本地成功但无外部结算证据

### 问题

对账发现本地支付成功并已入账，但渠道账单和结算文件都没有这笔。

### 事实

- 本地支付单和账本。
- 渠道请求记录。
- 渠道账单窗口。
- 结算文件。
- 人工调查记录。

### 不变量

- 没有外部成功证据，不能继续把外部成功当成已闭合事实。
- 修复不能直接删除本地成功记录。
- 用户权益处理和平台损益处理要分开。

### 状态

`DIFFERENCE_DETECTED -> CASE_OPENED -> HIGH_RISK_REVIEW -> REPAIR_PROPOSED -> APPROVED -> REPAIRED -> CLOSED`。

### 模式

这是对账 Case，不是业务接口重试。需要 maker-checker 审批。

### 验证

构造本地成功、渠道无账单、结算无明细、重复修复命令，检查不会直接改平历史。

### 对账修复

可能选择冲正、挂账、平台承担、用户补偿或长期挂起。每种修复都必须追加事实并说明证据。

### 面试回答

> 本地成功但无外部结算证据是高风险差异。我不会直接改订单状态，而是创建 Case，收集账单窗口和结算证据，审批后追加修复事实，并在复核通过后关闭。

## 演练 7：外部成功但本地没有业务单

### 问题

渠道账单显示扣款成功，但本地找不到对应支付单。

### 事实

- 渠道账单成功流水。
- 渠道请求号或商户订单号。
- 本地支付单索引。
- 用户账户或商户映射。
- 清结算记录。

### 不变量

- 外部成功必须被本地解释。
- 不能因为本地缺单就忽略外部扣款。
- 补单、退款或挂账必须幂等。

### 状态

`EXTERNAL_SUCCESS_LOCAL_MISSING -> CASE_OPENED -> OWNER_IDENTIFIED / OWNER_UNKNOWN -> REPAIR_PENDING -> REPAIRED -> CLOSED`。

### 模式

对账驱动补单或挂账；高风险资金操作需要审批。

### 验证

重复账单导入、补单重复执行、用户映射错误、账单迟到、人工关闭无证据。

### 对账修复

能定位用户和业务意图时补建本地支付事实并入账；不能定位时挂账并继续调查；应退款时发起退款并跟踪退款对账。

### 面试回答

> 外部成功本地缺单不能丢弃。渠道成功是事实，系统必须通过补单、挂账或退款让它被本地解释，并留下审批和审计证据。
````

- [ ] **Step 2: Verify all required drills**

Run:

```bash
rg -n "演练 1|演练 2|演练 3|演练 4|演练 5|演练 6|演练 7|内部账户转账|充值渠道成功|提现本地成功|库存预留超时|机票成功|本地成功但无外部结算证据|外部成功但本地没有业务单" financial-consistency/08-interview-synthesis/04-scenario-drills.md
```

Expected: output includes all seven required drills.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/08-interview-synthesis/04-scenario-drills.md
git commit -m "docs: add financial consistency scenario drills"
```

Expected: commit succeeds and includes only `04-scenario-drills.md`.

## Task 6: Create Red Flags and Bad Answers

**Files:**
- Create: `financial-consistency/08-interview-synthesis/05-red-flags-and-bad-answers.md`

- [ ] **Step 1: Add red flag content**

Use `apply_patch` to create `financial-consistency/08-interview-synthesis/05-red-flags-and-bad-answers.md` with:

````markdown
# 05 危险回答与反例

## 目标

高级回答不仅要知道该说什么，还要知道哪些话在金融场景里很危险。本文件列出常见危险回答、错误原因和更安全的表达。

## 1. "Use 2PC everywhere."

错误说法：所有服务都接入 2PC，就能保证强一致。

为什么错：2PC 要求参与者可控、协议兼容，并且能接受阻塞和协调器风险。支付渠道、银行、供应商、清结算机构不会参与我们的 2PC。

安全说法：本地可控资源可以用本地事务或有限 2PC；外部不可控资源要用幂等请求、显式状态、查询、回调、对账和修复闭环。

## 2. "Use Saga and compensate, so consistency is solved."

错误说法：每个步骤失败时执行补偿，整个系统最终一致。

为什么错：补偿可能失败，可能迟到，可能有罚金，也可能无法恢复原状。Saga 是业务流程，不是原子事务。

安全说法：Saga 适合编排可补偿流程，但必须把补偿本身建模成事实，并用状态机、对账、人工处理和审计处理不可逆动作。

## 3. "MQ delivered means the business succeeded."

错误说法：消息投递成功，下游最终会处理，所以业务成功。

为什么错：消息投递只说明传播发生，不说明消费成功、业务状态安全或外部事实成立。

安全说法：MQ 只能传递事实或命令。消费者必须幂等，处理结果必须落业务事实，对账要能检查消息传播后业务是否真的闭合。

## 4. "Workflow history is the source of financial truth."

错误说法：Temporal 或 Camunda 的 history 记录了流程，所以它就是事实源。

为什么错：workflow history 是编排执行历史，不是账本、支付单、渠道流水或供应商账单。它不能替代业务事实。

安全说法：workflow history 用来恢复和观察流程，资金事实必须落在业务库、账本和外部事实源中。

## 5. "Callback success means the channel definitely settled."

错误说法：收到成功回调就说明钱已经结算完成。

为什么错：回调可能只是支付成功，不一定完成清结算；也可能需要和账单、结算文件、手续费明细核对。

安全说法：回调可以推进业务状态，但结算闭合还需要渠道账单、清算文件和对账证据。

## 6. "Unknown can be treated as failure."

错误说法：超时就失败，避免流程卡住。

为什么错：超时时外部动作可能已经成功。把 unknown 当失败可能造成重复扣款、重复出款、重复退款或错误解冻。

安全说法：unknown 是一等状态，必须通过查询、回调、对账或人工调查收敛。

## 7. "Reconciliation can directly update balances."

错误说法：对账发现差异，直接 update 余额表调平。

为什么错：直接 update 会破坏历史可解释性，审计无法知道钱为什么变化。

安全说法：对账只能生成 Difference 和 Case，修复要追加账本或修复事实，并经过审批、复核和关闭。

## 8. "Retry until success is safe."

错误说法：所有失败都重试，最终就成功。

为什么错：非幂等副作用被重复执行会造成重复扣款、重复出款或重复预订。

安全说法：只能重试幂等命令。每次重试必须带稳定 request id，并且状态机要能识别已执行结果。

## 9. "Idempotency key alone prevents all duplicates."

错误说法：接口有幂等键，所以不会重复。

为什么错：重复可能发生在入口、消息消费、回调、查询、人工修复、对账导入等多个层面。单一入口幂等不能覆盖全链路。

安全说法：幂等要分层：请求幂等、状态推进幂等、账本 source id 幂等、外部 request id 幂等、修复命令幂等。

## 10. "Strong consistency means no asynchronous process is allowed."

错误说法：只要异步就不强一致，所以金融系统不能异步。

为什么错：真实金融系统大量依赖异步回调、清结算、对账和人工流程。关键是说明一致性的边界和闭环，不是假装所有系统同一时刻提交。

安全说法：单个权威边界内要强约束；跨外部系统时要用显式状态、幂等、验证、对账和审计实现业务可解释的一致性。

## 反例识别口诀

遇到下面几类说法，要立刻追问：

- 把工具当成正确性证明。
- 把日志、消息、offset、history 当成资金事实。
- 把 unknown 当 failure。
- 把补偿当 rollback。
- 把重试当安全。
- 把对账当 SQL update。
- 把报表对平当明细正确。
````

- [ ] **Step 2: Verify required red flags**

Run:

```bash
rg -n "2PC everywhere|Saga and compensate|MQ delivered|Workflow history|Callback success|Unknown can be treated as failure|Reconciliation can directly update balances|Retry until success|Idempotency key alone|Strong consistency means no asynchronous process" financial-consistency/08-interview-synthesis/05-red-flags-and-bad-answers.md
```

Expected: output includes all 10 required red flags.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/08-interview-synthesis/05-red-flags-and-bad-answers.md
git commit -m "docs: document dangerous consistency answers"
```

Expected: commit succeeds and includes only `05-red-flags-and-bad-answers.md`.

## Task 7: Create Senior Answer Rubric

**Files:**
- Create: `financial-consistency/08-interview-synthesis/06-senior-answer-rubric.md`

- [ ] **Step 1: Add rubric content**

Use `apply_patch` to create `financial-consistency/08-interview-synthesis/06-senior-answer-rubric.md` with:

````markdown
# 06 高级回答评分标准

## 目标

同一个金融一致性问题，不同水平的人会给出完全不同的答案。本文件用评分标准帮助学习者判断自己的回答是否已经从“知道名词”走向“能设计真实系统”。

## 四个层级

### Junior

特征：

- 能说出事务、MQ、幂等、分布式锁等词。
- 容易把框架名当成答案。
- 很少主动定义不变量。
- 容易把超时当失败。
- 对对账、审计和人工修复缺少概念。

典型回答：

> 用事务保证扣款和加款，用 MQ 保证最终一致，如果失败就重试。

问题：没有说明事务边界、重复消息、外部不确定性和对账闭环。

### Mid-level

特征：

- 能区分本地事务、Outbox、TCC、Saga。
- 知道幂等和重试的重要性。
- 能处理一部分异常路径。
- 但回答经常停在技术流程，缺少事实闭环和验证。

典型回答：

> 本地先落库和 Outbox，然后异步通知下游。消费者幂等处理，失败进入重试和死信。

问题：还需要说明业务事实是否闭合、unknown 怎么处理、死信后如何修复、如何验证不变量。

### Senior

特征：

- 先定义事实和不变量，再选择模式。
- 明确本地事务边界和外部系统边界。
- 把 unknown 作为一等状态。
- 能解释重复、乱序、迟到回调、恢复重放。
- 能说明验证、对账、修复和审计。

典型回答：

> 我会先定义支付单、账本、渠道流水和结算文件分别是什么事实，再定义不能重复入账、账本必须平衡、unknown 不能直接失败等不变量。本地事务只保护本地事实和 Outbox；外部渠道通过幂等请求、回调、查询和对账收敛。验证上会做重复回调、乱序、宕机恢复和账单差异注入。

### Staff / Principal

特征：

- 能把技术正确性和业务风险、合规、组织流程连接起来。
- 能识别系统边界、团队边界、责任边界和运营边界。
- 能设计可观测性、审计、审批、权限、风险分级和事故响应。
- 能解释为什么某些差异不能自动修复。
- 能把方案拆成可演进路线，而不是一次性大而全。

典型回答：

> 我会把这个系统分成执行闭环和事实闭环。执行闭环处理请求、状态和消息；事实闭环通过账本、渠道账单、供应商账单、清结算和对账 Case 证明每一笔钱可解释。高风险修复进入 maker-checker，所有修复追加事实并可复核。系统上线前用故障注入和历史检查验证不变量，上线后用准实时和日终对账监控差异率、修复时效和长期挂起风险。

## 评分维度

| 维度 | 低分表现 | 高分表现 |
| --- | --- | --- |
| 事实所有权 | 混淆日志、消息、报表和事实 | 明确领域事实、账本事实、外部事实和派生视图 |
| 不变量 | 只说不能出错 | 给出可测试的不变量 |
| 失败模式 | 只覆盖正常失败 | 覆盖重复、乱序、超时、宕机、迟到、人工修复 |
| 模式选择 | 背框架名 | 按边界组合本地事务、Outbox、TCC、Saga、Temporal、对账 |
| 幂等和重试 | 简单说加幂等 | 分入口、消息、回调、账本、外部请求和修复幂等 |
| unknown 处理 | 超时直接失败 | unknown 显式建模并由查询、回调、对账收敛 |
| 验证 | 只说写测试 | 用属性测试、故障注入、历史检查和对账演练 |
| 对账修复 | 直接 update 调平 | Difference、Case、Repair、Review、Close 闭环 |
| 审计 | 只保留日志 | 能追踪证据、审批、执行、复核和关闭原因 |
| 表达清晰度 | 堆名词 | 按事实、不变量、状态、边界、模式、验证、闭环作答 |

## 自评问题

回答完一个题后，问自己：

- 我有没有定义谁是权威事实？
- 我有没有说出至少三个可测试不变量？
- 我有没有说明 unknown 状态？
- 我有没有区分业务成功和技术成功？
- 我有没有说明为什么选择这个模式而不是另一个？
- 我有没有覆盖重复、乱序、超时和迟到结果？
- 我有没有说明如何验证？
- 我有没有说明生产对账和修复？
- 我有没有留下审计证据链？

如果这些问题答不上来，说明答案还没有达到 Senior 水平。
````

- [ ] **Step 2: Verify rubric dimensions**

Run:

```bash
rg -n "Junior|Mid-level|Senior|Staff / Principal|事实所有权|不变量|失败模式|模式选择|幂等和重试|unknown 处理|验证|对账修复|审计|表达清晰度" financial-consistency/08-interview-synthesis/06-senior-answer-rubric.md
```

Expected: output includes all levels and scoring dimensions.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/08-interview-synthesis/06-senior-answer-rubric.md
git commit -m "docs: add senior consistency answer rubric"
```

Expected: commit succeeds and includes only `06-senior-answer-rubric.md`.

## Task 8: Create Final Summary

**Files:**
- Create: `financial-consistency/08-interview-synthesis/07-final-summary.md`

- [ ] **Step 1: Add final summary**

Use `apply_patch` to create `financial-consistency/08-interview-synthesis/07-final-summary.md` with:

````markdown
# 07 最终速查表

## 一句话 thesis

金融级一致性不是靠某个分布式事务框架保证的，而是靠权威事实、不变量、状态机、幂等、验证、对账、修复和审计共同形成闭环。

## 架构评审检查表

- 业务场景和错误影响是否说清楚？
- 权威事实和派生线索是否区分？
- 不变量是否可以测试？
- 状态机是否包含 unknown、reconciling、repair pending？
- 本地事务边界是否明确？
- 外部系统边界是否明确？
- MQ、workflow、日志是否没有被当成资金事实？
- 模式选择是否解释了取舍？
- 验证是否覆盖重复、乱序、超时、宕机、迟到？
- 对账、修复、审批、复核和审计是否闭环？

## 模式选择检查表

| 问题 | 倾向选择 |
| --- | --- |
| 单库内多个事实要原子写入 | 本地事务 |
| 本地事实和消息发布要一致 | Outbox |
| 资源可以预留、确认、取消 | TCC |
| 多步骤业务流程需要补偿 | Saga |
| 长流程需要重试、超时、可观测编排 | Temporal |
| 少数同构可控资源要全局提交 | 有限制地考虑 2PC |
| 外部渠道或供应商不可控 | 幂等请求、unknown、查询、回调、对账 |

## 验证检查表

- 是否写出资金守恒、借贷平衡、不可重复入账等不变量？
- 是否测试重复请求？
- 是否测试重复消息？
- 是否测试重复回调？
- 是否测试回调和查询乱序？
- 是否测试本地事务提交后宕机？
- 是否测试消息发布前后宕机？
- 是否测试外部成功本地 unknown？
- 是否测试本地成功外部无账单？
- 是否测试修复命令重复执行？

## 对账检查表

- 对账读取的是领域事实、账本事实、渠道事实、供应商事实和清结算事实吗？
- 是否区分日志、消息、workflow history、offset 和报表这些非权威事实？
- Difference 是否进入 Case？
- Case 是否分类、分级、分派？
- Repair 是否幂等且追加事实？
- 高风险 Repair 是否 maker-checker？
- Close 是否有证据和原因？
- Reopen 是否被允许并可审计？

## 面试中不要说

- “用 2PC 就能解决。”
- “Saga 会自动保证一致性。”
- “MQ 成功就等于业务成功。”
- “工作流 history 就是事实源。”
- “超时就当失败。”
- “重试直到成功。”
- “有 idempotency key 就不会重复。”
- “对账直接 update 调平。”
- “报表平了就说明明细正确。”
- “强一致就是不能有异步。”

## 最终回答模板

可以用下面模板回答大多数金融一致性设计题：

> 我会先定义这个业务的权威事实和不变量，而不是直接选框架。比如资金场景里，支付单、账本分录、渠道流水、结算文件分别承担不同事实；核心不变量包括不能重复扣款或入账、账本借贷平衡、unknown 不能无证据失败、外部成功必须有本地解释。
>
> 然后我会划分边界。本地库内用数据库事务保证业务单、账本和 Outbox 原子写入；跨服务用 Outbox、幂等消费和状态机；外部渠道或供应商不参与本地事务，所以用稳定 request id、回调、查询和 unknown 状态处理不确定性。
>
> 模式选择上，我会按边界组合：资源可预留时考虑 TCC，长流程用 Saga 或 Temporal 编排，本地事实传播用 Outbox，少数同构可控资源才考虑 2PC。Temporal 或 MQ 只是执行机制，不是资金事实源。
>
> 验证上，我会先写不变量，再做重复、乱序、超时、宕机恢复、迟到回调和差异注入。生产上通过准实时和日终对账发现本地事实、账本事实、渠道事实、供应商事实和清结算事实之间的差异。差异进入 Case，修复必须幂等、审批、复核、追加事实，并留下审计证据。

## 最终判断

如果一个方案不能回答“这笔钱为什么变化、由谁证明、错了怎么发现、怎么修复、谁审批、为什么能关闭”，它就还不是金融级一致性方案。
````

- [ ] **Step 2: Verify final summary**

Run:

```bash
rg -n "一句话 thesis|架构评审检查表|模式选择检查表|验证检查表|对账检查表|面试中不要说|最终回答模板|最终判断" financial-consistency/08-interview-synthesis/07-final-summary.md
```

Expected: output includes every final-summary section.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/08-interview-synthesis/07-final-summary.md
git commit -m "docs: add final consistency interview summary"
```

Expected: commit succeeds and includes only `07-final-summary.md`.

## Task 9: Link Chapter From Root README

**Files:**
- Modify: `financial-consistency/README.md`

- [ ] **Step 1: Replace plain 08 entry with link**

Use `apply_patch` to change the root README section from:

```markdown
- 08-interview-synthesis
  面试表达、架构评审话术、常见追问。
```

to:

```markdown
- [08-interview-synthesis](./08-interview-synthesis/README.md)
  面试表达、架构评审话术、常见追问。
```

- [ ] **Step 2: Add spec link**

Use `apply_patch` to add this bullet to the "正式设计文档" list after the reconciliation design link:

```markdown
- [2026-05-02-financial-consistency-interview-synthesis-design.md](../docs/superpowers/specs/2026-05-02-financial-consistency-interview-synthesis-design.md)
```

- [ ] **Step 3: Verify root README links**

Run:

```bash
rg -n "financial-consistency-interview-synthesis-design.md|08-interview-synthesis" financial-consistency/README.md
```

Expected: output includes the spec link and the chapter link.

- [ ] **Step 4: Commit**

Run:

```bash
git add financial-consistency/README.md
git commit -m "docs: link interview synthesis phase"
```

Expected: commit succeeds and includes only `financial-consistency/README.md`.

## Task 10: Final Verification

**Files:**
- Verify all created and modified files.

- [ ] **Step 1: Check expected file list**

Run:

```bash
find financial-consistency/08-interview-synthesis -maxdepth 1 -type f | sort
```

Expected output includes exactly:

```text
financial-consistency/08-interview-synthesis/01-master-narrative.md
financial-consistency/08-interview-synthesis/02-architecture-review-playbook.md
financial-consistency/08-interview-synthesis/03-question-bank.md
financial-consistency/08-interview-synthesis/04-scenario-drills.md
financial-consistency/08-interview-synthesis/05-red-flags-and-bad-answers.md
financial-consistency/08-interview-synthesis/06-senior-answer-rubric.md
financial-consistency/08-interview-synthesis/07-final-summary.md
financial-consistency/08-interview-synthesis/README.md
```

- [ ] **Step 2: Check required concepts**

Run:

```bash
rg -n "权威事实|不变量|状态机|unknown|Outbox|TCC|Saga|Temporal|2PC|验证|对账|修复|审计|maker-checker|workflow history|MQ" financial-consistency/08-interview-synthesis financial-consistency/README.md
```

Expected: output appears across the chapter files and root README.

- [ ] **Step 3: Check scenario coverage**

Run:

```bash
rg -n "内部账户转账|充值渠道成功|提现本地成功|库存预留超时|机票成功|本地成功但无外部结算证据|外部成功但本地没有业务单" financial-consistency/08-interview-synthesis/04-scenario-drills.md
```

Expected: output includes all seven scenario drills.

- [ ] **Step 4: Check required red flags**

Run:

```bash
rg -n "Use 2PC everywhere|Use Saga and compensate|MQ delivered means the business succeeded|Workflow history is the source of financial truth|Callback success means the channel definitely settled|Unknown can be treated as failure|Reconciliation can directly update balances|Retry until success is safe|Idempotency key alone prevents all duplicates|Strong consistency means no asynchronous process is allowed" financial-consistency/08-interview-synthesis/05-red-flags-and-bad-answers.md
```

Expected: output includes all ten red flags from the design spec.

- [ ] **Step 5: Check for placeholder language**

Run:

```bash
rg -n "TB[D]|TO[D]O|待[定]|占[位]|以后[补]|后续[补]" financial-consistency/08-interview-synthesis docs/superpowers/plans/2026-05-02-financial-consistency-interview-synthesis.md
```

Expected: no output.

- [ ] **Step 6: Check Markdown whitespace**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 7: Confirm worktree status**

Run:

```bash
git status --short
```

Expected: no output.

## Self-Review Checklist

- Spec coverage: Tasks 1-9 implement every file and root README link required by `2026-05-02-financial-consistency-interview-synthesis-design.md`.
- Required drills: Task 5 covers internal transfer, recharge callback delay, withdraw unknown, ecommerce inventory timeout, travel booking partial failure, local success without external settlement, and external success without local order.
- Required red flags: Task 6 covers all ten unsafe claims from the design spec.
- No code scope creep: The plan does not create Java, Go, database, Kafka, Temporal, Seata, Camunda, or supplier integration code.
- Verification: Task 10 checks file list, key concepts, scenario coverage, red flags, placeholders, Markdown whitespace, and clean git status.

## Execution Options

After this plan is reviewed, execute it with one of:

1. Subagent-Driven: dispatch a fresh subagent per task, review between tasks, faster iteration.
2. Inline Execution: execute tasks in this session using the executing-plans skill, with checkpoints.
