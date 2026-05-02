# Financial Consistency Verification Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `06-verification-lab` documentation module that turns financial consistency verification into a concrete lab specification covering models, invariants, property testing, fault injection, history replay, scenario matrices, and a future Java lab roadmap.

**Architecture:** This is a documentation-first phase. Each file owns one verification surface: the shared model, invariant catalog, test generation, fault injection, replay, scenario mapping, implementation roadmap, and interview synthesis. The phase must build on `01-transfer` through `05-patterns` without modifying completed phase content beyond linking `06-verification-lab` from the root README.

**Tech Stack:** Markdown, Git, `rg`, `find`, `git diff --check`. No Java dependencies, framework APIs, Context7 research, or runnable test harness are introduced in this phase.

---

## File Structure

- Create directory: `financial-consistency/06-verification-lab/`
- Create: `financial-consistency/06-verification-lab/README.md`
- Create: `financial-consistency/06-verification-lab/01-verification-model.md`
- Create: `financial-consistency/06-verification-lab/02-invariant-catalog.md`
- Create: `financial-consistency/06-verification-lab/03-property-testing.md`
- Create: `financial-consistency/06-verification-lab/04-fault-injection.md`
- Create: `financial-consistency/06-verification-lab/05-history-replay.md`
- Create: `financial-consistency/06-verification-lab/06-scenario-lab-matrix.md`
- Create: `financial-consistency/06-verification-lab/07-code-lab-roadmap.md`
- Create: `financial-consistency/06-verification-lab/08-interview-synthesis.md`
- Modify: `financial-consistency/README.md`

Do not modify:

- `financial-consistency/01-transfer/**`
- `financial-consistency/02-payment-recharge-withdraw/**`
- `financial-consistency/03-order-payment-inventory/**`
- `financial-consistency/04-travel-booking-saga/**`
- `financial-consistency/05-patterns/**`

## Task 1: Create Verification Lab README

**Files:**
- Create: `financial-consistency/06-verification-lab/README.md`

- [ ] **Step 1: Create directory**

Run:

```bash
mkdir -p financial-consistency/06-verification-lab
```

Expected: command succeeds.

- [ ] **Step 2: Add README content**

Use `apply_patch` to create `financial-consistency/06-verification-lab/README.md`:

````markdown
# 06 验证实验室

## 目标

这一阶段把金融级一致性的验证方法整理成实验室规格。重点不是再解释 Outbox、Saga、TCC、Temporal 或 CDC 的定义，而是定义如何用不变量、异常历史、属性测试、故障注入、历史回放和对账验证，降低不可解释事实出现的风险。

本阶段先不写 Java 实现。它先把后续可运行实验室需要的模型、oracle、生成器、故障点和场景矩阵设计清楚。

## 学习顺序

1. [验证模型](./01-verification-model.md)
2. [不变量目录](./02-invariant-catalog.md)
3. [属性测试](./03-property-testing.md)
4. [故障注入](./04-fault-injection.md)
5. [历史回放](./05-history-replay.md)
6. [场景实验矩阵](./06-scenario-lab-matrix.md)
7. [代码实验室路线图](./07-code-lab-roadmap.md)
8. [面试表达](./08-interview-synthesis.md)

## 核心问题

- 金融系统里应该验证函数返回值，还是验证一段 history 结束后的事实是否可解释？
- Command、Event、Fact、History、Invariant、Oracle 分别是什么？
- 为什么属性测试的重点是生成异常历史，而不是随机字段值？
- 故障注入应该按工具组织，还是按最容易造成事实分叉的位置组织？
- 历史回放如何验证重复、乱序、迟到成功、迟到失败和人工修复？
- 为什么测试只能降低风险，不能证明所有异常历史绝对安全？

## 本阶段边界

- 本阶段是文档实验室，不创建可运行测试工程。
- 本阶段不引入 JUnit、jqwik、Testcontainers、Kafka、Temporal SDK 或数据库依赖。
- 本阶段输出后续 Java 实验室路线图，但不绑定具体版本或 API。
- 本阶段所有验证语言都必须回到事实、状态机、幂等、账本、对账和人工复核。

## 本阶段结论

金融级验证的核心不是证明 happy path 能跑通，而是用明确的不变量和异常历史检查系统是否会产生不可解释事实。真正有价值的测试必须覆盖重复、乱序、超时、宕机、外部未知、补偿失败、对账差错和人工修复。
````

- [ ] **Step 3: Verify README links**

Run:

```bash
rg -n "\./01-verification-model.md|\./02-invariant-catalog.md|\./03-property-testing.md|\./04-fault-injection.md|\./05-history-replay.md|\./06-scenario-lab-matrix.md|\./07-code-lab-roadmap.md|\./08-interview-synthesis.md" financial-consistency/06-verification-lab/README.md
```

Expected: output includes all 8 child document links.

- [ ] **Step 4: Commit**

Run:

```bash
git add financial-consistency/06-verification-lab/README.md
git commit -m "docs: add verification lab module entry"
```

Expected: commit succeeds and includes only `financial-consistency/06-verification-lab/README.md`.

## Task 2: Create Verification Model Document

**Files:**
- Create: `financial-consistency/06-verification-lab/01-verification-model.md`

- [ ] **Step 1: Add model content**

Use `apply_patch` to create `financial-consistency/06-verification-lab/01-verification-model.md`:

````markdown
# 01 验证模型

## 目标

验证实验室需要一套统一语言。金融一致性验证不是检查某个接口是否返回成功，而是检查一段 History 结束后，所有 Fact 是否能被状态机、幂等、账本、外部事实、对账和人工修复解释。

## 核心对象

| 对象 | 含义 | 示例 | 验证重点 |
| --- | --- | --- | --- |
| Command | 外部或内部发起的意图 | `CreateTransfer`、`CapturePayment`、`CancelBooking` | 是否幂等，是否有合法前置状态 |
| Event | 系统发布或接收的变化通知 | `PaymentCaptured`、`InventoryReserved`、`SupplierCallbackReceived` | 是否重复、乱序、迟到，消费者是否幂等 |
| Fact | 已经落库、可审计、不能随意删除的事实 | 账本分录、渠道流水、供应商订单、人工审批 | 是否可追溯，是否能和其他事实互相解释 |
| History | 命令、事件、事实、故障和人工动作组成的时序 | 支付请求超时后迟到成功回调 | 终态是否可解释 |
| Invariant | 系统永远不能违反的承诺 | 同一幂等键最多一个业务效果 | 是否被任意异常历史破坏 |
| Oracle | 判断 History 是否合格的检查器 | 状态机 oracle、资金 oracle、外部事实 oracle | 是否能指出具体破坏的边界 |

## Fact 优先

接口返回、日志、broker offset、workflow history 和页面状态都不是最终事实来源。它们可以帮助定位执行过程，但不能替代领域事实、渠道事实、供应商事实、账本事实、Outbox 事件、消费者处理记录、对账差错和人工审批记录。

## 三类 Oracle

| Oracle | 检查内容 | 失败示例 |
| --- | --- | --- |
| 状态机 oracle | 状态迁移是否合法，迟到事件是否被拒绝 | `PAYMENT_SUCCEEDED` 被迟到失败覆盖 |
| 资金 oracle | 余额、冻结、流水、账本分录是否可解释 | 借贷不平，重复扣款，已 capture 后 void |
| 外部事实 oracle | 渠道、供应商、人工修复和本地事实是否互相解释 | 本地成功但供应商无单且没有差错记录 |

## History 形态

```text
Command
  -> Local Fact
  -> Outbox Event
  -> Consumer Command
  -> External Fact
  -> Callback / Query Result
  -> Ledger Fact
  -> Reconciliation Fact
  -> Manual Repair Fact
```

真实 History 可以重复、乱序、丢响应、迟到、被人工修复打断，也可能长期停留在 unknown 或人工挂起状态。验证模型必须允许这些异常历史存在，并检查它们是否仍然可解释。

## 危险误用

| 误用 | 后果 | 正确做法 |
| --- | --- | --- |
| 只断言接口返回成功 | 无法发现迟到回调、重复消息和账本差异 | 断言 History 结束后的 Fact 集合 |
| 把 workflow history 当 Fact | 编排历史被误当成资金事实 | workflow history 只能解释执行过程 |
| 把 broker offset 当业务完成 | 消费者处理失败不可见 | 消费者必须有业务处理记录和幂等键 |
| Oracle 只检查最终状态 | 资金、供应商、人工修复事实可能不可解释 | 同时检查状态、资金和外部事实 |

## 输出结论

验证模型的输出不是“测试全部证明系统正确”，而是“在这组异常历史和不变量覆盖范围内，没有发现不可解释事实”。如果 oracle 能构造出不可解释事实，说明系统的状态机、幂等、账本、事件传播、补偿、对账或人工修复边界存在缺口。
````

- [ ] **Step 2: Verify model anchors**

Run:

```bash
rg -n "Command|Event|Fact|History|Invariant|Oracle|状态机 oracle|资金 oracle|外部事实 oracle|workflow history|broker offset" financial-consistency/06-verification-lab/01-verification-model.md
```

Expected: output includes all model terms and oracle types.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/06-verification-lab/01-verification-model.md
git commit -m "docs: define financial verification model"
```

Expected: commit succeeds and includes only `01-verification-model.md`.

## Task 3: Create Invariant Catalog

**Files:**
- Create: `financial-consistency/06-verification-lab/02-invariant-catalog.md`

- [ ] **Step 1: Add invariant catalog content**

Use `apply_patch` to create `financial-consistency/06-verification-lab/02-invariant-catalog.md`:

````markdown
# 02 不变量目录

## 目标

不变量是金融级系统永远不能违反的承诺。验证实验室的每个属性测试、故障注入和历史回放都必须落回不变量，而不是只检查流程是否跑完。

## 不变量总表

| 类别 | 不变量 | 典型破坏方式 | 应该检查的事实 |
| --- | --- | --- | --- |
| 幂等 | 同一业务幂等键最多产生一个业务效果 | 重复请求造成重复扣款、退款、出票或记账 | request id、业务单号、处理记录、唯一约束 |
| 状态机 | 非法状态转换必须被拒绝 | 成功事实被迟到失败覆盖 | 状态变更记录、前置状态、版本号 |
| 账本 | 借贷分录必须平衡且可追溯 | 账户余额变化但无分录，分录无业务来源 | account movement、ledger posting、流水 |
| 外部未知 | `PAYMENT_UNKNOWN`、`REFUND_UNKNOWN`、`SUPPLIER_UNKNOWN` 不能本地直接判失败 | 超时后重复扣款，供应商成功被本地失败覆盖 | 渠道流水、供应商请求号、查询和回调 |
| TCC | Confirm 和 Cancel 不能同时成功 | 同一预留资源既确认又释放 | 全局事务 ID、分支 ID、Try/Confirm/Cancel 状态 |
| 补偿 | 补偿必须追加新业务事实，不能删除历史事实 | 已出票、已 capture 后删除本地记录 | refund、void、罚金、补差、人工处理 |
| Outbox | 本地事实提交后必须有可恢复传播记录 | 业务提交后消息丢失 | Outbox 事件、publisher 状态、消费者处理记录 |
| 消费者 | 重复消息不能产生第二次业务效果 | broker 重投造成重复库存确认或重复退款 | event id、处理表、业务唯一约束 |
| 对账 | 对账不能直接修改领域事实 | 报表调平但业务事实不可解释 | 差错记录、owner、修复命令、复核结果 |
| 人工修复 | 人工结论必须可审计、可复核 | 人工直接改状态，无证据链 | 工单、审批、证据快照、修复事实 |

## 不变量写法

一个可执行的不变量应该包含：

1. 适用场景。
2. 输入 History 范围。
3. 需要读取的 Fact。
4. 判断条件。
5. 失败时说明哪类一致性边界被破坏。

示例：

```text
Invariant: 同一 payment_request_id 最多产生一次 capture 业务效果
Applies to: 支付、旅行预订、订单支付
Facts: payment_request, channel_transaction, ledger_posting
Check: capture 成功事实数量 <= 1，并且每个成功 capture 都有唯一渠道流水和账本分录
Failure meaning: 支付幂等或账本一致性边界被破坏
```

## 分层使用

- 单服务内：用状态机、唯一约束和本地事务表达不变量。
- 跨服务事件：用 Outbox、消费者处理记录和业务唯一约束表达不变量。
- 外部系统：用 request id、查询、回调、渠道账单和供应商账单表达不变量。
- 资金事实：用账户流水、冻结、借贷分录和对账表达不变量。
- 人工修复：用 maker-checker、证据快照、审批和复核表达不变量。

## 危险误用

| 误用 | 后果 | 正确做法 |
| --- | --- | --- |
| 只写“金额不能错” | 无法定位破坏边界 | 写清金额来自哪些 Fact，如何计算 |
| 只检查最终状态 | 账本或外部事实可能不可解释 | 同时检查状态、资金和外部事实 |
| 把 unknown 当失败 | 造成重复外部动作或覆盖迟到成功 | unknown 必须查询、对账或人工处理 |
| 对账脚本直接修数据 | 修复不可审计 | 生成差错、修复命令、审批和复核 |

## 输出结论

不变量目录是后续所有测试的共同词典。属性测试负责生成异常 History，故障注入负责制造事实分叉，历史回放负责改变时序，oracle 负责检查这些不变量是否被破坏。
````

- [ ] **Step 2: Verify invariant anchors**

Run:

```bash
rg -n "幂等|状态机|账本|PAYMENT_UNKNOWN|REFUND_UNKNOWN|SUPPLIER_UNKNOWN|TCC|补偿|Outbox|消费者|对账|人工修复|maker-checker" financial-consistency/06-verification-lab/02-invariant-catalog.md
```

Expected: output includes all invariant categories.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/06-verification-lab/02-invariant-catalog.md
git commit -m "docs: add financial invariant catalog"
```

Expected: commit succeeds and includes only `02-invariant-catalog.md`.

## Task 4: Create Property Testing Document

**Files:**
- Create: `financial-consistency/06-verification-lab/03-property-testing.md`

- [ ] **Step 1: Add property testing content**

Use `apply_patch` to create `financial-consistency/06-verification-lab/03-property-testing.md`:

````markdown
# 03 属性测试

## 目标

属性测试的重点不是随机生成字段值，而是随机生成异常 History。金融级属性测试要让重复、乱序、迟到、超时、宕机恢复、补偿失败、对账差错和人工修复组合出现，然后检查不变量是否仍然成立。

属性测试不能穷尽所有异常历史，也不能证明系统绝对正确。它的价值是用系统化生成器扩大异常历史覆盖范围，让不可解释事实更容易暴露。

## 生成器模型

| 生成器 | 输入 | 可能制造的风险 | 主要不变量 |
| --- | --- | --- | --- |
| Command duplication | 相同业务幂等键重复提交 | 重复扣款、重复退款、重复出票 | 幂等、账本 |
| Message duplication | 相同 event id 重复投递 | 消费者重复处理 | 消费者、状态机 |
| Callback reordering | 成功、失败、处理中回调乱序 | 成功被迟到失败覆盖 | 状态机、外部未知 |
| Timeout then success | 请求超时后外部成功 | 本地失败和外部成功分叉 | 外部事实、对账 |
| Crash after commit | 本地事务提交后进程宕机 | Outbox 事件未发布 | Outbox |
| TCC disorder | Cancel 先于 Try，Confirm/Cancel 并发 | 空回滚、悬挂、双终态 | TCC |
| Activity retry | 外部副作用成功但 Activity completion 未记录 | Temporal retry 重复外部动作 | 幂等、外部事实 |
| CDC replay | offset 回退或重复捕获 | 投影重复或倒退 | CDC、消费者 |
| Manual repair replay | 人工修复命令重复提交 | 重复冲正、重复补分录 | 人工修复、账本 |

## History 生成步骤

```text
1. 选择场景：transfer / payment / order / travel
2. 生成初始事实：账户、订单、库存、供应商请求、支付请求
3. 生成命令序列：创建、确认、取消、查询、补偿、修复
4. 插入异常：重复、乱序、超时、崩溃、迟到回调
5. 执行业务状态迁移模型
6. 用 oracle 检查不变量
7. 输出最小失败 History
```

## Shrinking 思路

失败 History 应该尽量缩小到能解释问题的最短序列。例如：

```text
CreatePayment(req-1)
ChannelTimeout(req-1)
MarkFailed(req-1)
ChannelSuccessCallback(req-1)
```

这个最小 History 暴露的问题是：系统把 `PAYMENT_UNKNOWN` 本地裁决成失败，导致迟到成功无法解释。

## 场景示例

### 内部转账

生成重复 `CreateTransfer`、重复 `PostLedger`、account movement 成功但 ledger posting 延迟、人工冲正重复提交。检查幂等、余额守恒、借贷平衡和冲正可审计。

### 充值提现

生成渠道超时、重复回调、成功失败乱序、查询结果晚到、渠道账单和本地状态不一致。检查 unknown 不能直接失败，重复回调不能重复入账或出款。

### 电商下单

生成库存预留成功后支付失败、支付成功后库存确认失败、重复 `PaymentCaptured`、重复 `InventoryReleased`。检查库存、支付、退款和订单终态可解释。

### 旅行组合预订

生成机票出票成功但酒店失败、保险已生效但附加项失败、供应商未知后迟到成功、refund unknown 后人工处理。检查核心项和附加项策略、不可逆事实、罚金、补差和人工处理。

## 危险误用

| 误用 | 后果 | 正确做法 |
| --- | --- | --- |
| 只随机金额和字符串 | 无法发现一致性问题 | 随机异常 History |
| 把失败用例看成偶发 | 无法定位设计缺口 | 输出最小失败 History |
| 只跑 happy path 属性 | 覆盖面和普通单测没有区别 | 强制生成超时、重复、乱序和崩溃 |
| 断言框架成功 | 漏掉事实不可解释 | 断言不变量和 Fact 集合 |

## 输出结论

属性测试的产物应该是一段可复现的最小失败 History，以及被破坏的不变量。它不是证明系统正确，而是持续寻找会产生不可解释事实的异常组合。
````

- [ ] **Step 2: Verify property testing anchors**

Run:

```bash
rg -n "属性测试|异常 History|Command duplication|Message duplication|Callback reordering|Timeout then success|Crash after commit|TCC disorder|Activity retry|CDC replay|Shrinking|最小失败 History" financial-consistency/06-verification-lab/03-property-testing.md
```

Expected: output includes generator types and shrinking terminology.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/06-verification-lab/03-property-testing.md
git commit -m "docs: define property testing for consistency histories"
```

Expected: commit succeeds and includes only `03-property-testing.md`.

## Task 5: Create Fault Injection Document

**Files:**
- Create: `financial-consistency/06-verification-lab/04-fault-injection.md`

- [ ] **Step 1: Add fault injection content**

Use `apply_patch` to create `financial-consistency/06-verification-lab/04-fault-injection.md`:

````markdown
# 04 故障注入

## 目标

故障注入要放在最容易产生事实分叉的位置。验证实验室不按工具命名故障，而按事实边界命名故障：本地事务、Outbox、broker、消费者、Activity、渠道、供应商、对账和人工修复。

## 注入点矩阵

| 注入点 | 故障前事实 | 故障后允许 | 绝对不能 | 合格终态 |
| --- | --- | --- | --- | --- |
| 本地事务提交前失败 | 没有业务事实提交 | 重试命令 | 发布不存在的事件 | 未创建或幂等重试成功 |
| 本地事务提交后、Outbox sent 前失败 | 业务事实和 Outbox 已提交 | publisher 重投事件 | 重做扣款、出票或退款 | 事件 eventually sent |
| broker 暂停或重复投递 | Outbox 事件存在 | 延迟投递、重复消费 | 消费者重复业务效果 | 消费者幂等完成 |
| 消费者外部副作用后、处理记录前失败 | 外部可能成功 | 用 request id 查询或幂等重试 | 第二次外部副作用 | 同一业务效果被记录 |
| Activity completion 未写入 workflow history | 外部副作用可能成功 | Activity 用同一 request id 重试或查询 | 重复扣款、退款、供应商订单 | 外部事实可解释 |
| 渠道响应超时 | 渠道请求已发出 | 查询、等待回调、对账 | 本地直接失败后重扣 | unknown 或已确认事实 |
| 供应商成功回调迟到 | 供应商可能已成功 | 状态机接收或转人工 | 覆盖已确认事实 | 成功、差错或人工挂起 |
| 对账任务中断后重跑 | 部分差错已生成 | 幂等重跑批次 | 重复修复命令 | 差错稳定分类 |
| 人工审批后修复命令重复 | 审批事实已存在 | 幂等返回同一修复结果 | 重复冲正或补分录 | 修复事实可复核 |

## 注入规则

每个故障注入用例都必须写清：

1. 故障发生前已经提交了哪些 Fact。
2. 故障发生后系统能安全重试哪些动作。
3. 哪些外部动作或资金动作绝对不能重复。
4. 终态是成功、失败、unknown、长期对账还是人工挂起。
5. 由哪个 oracle 判断合格。

## 关键边界

### Outbox

Publisher 可以重发事件，但不能重新执行业务命令。`sent` 标记只能说明事件进入发布通道，不能证明消费者业务完成。

### Consumer

消费者可能在完成外部副作用后宕机。恢复时必须用 event id、业务 request id、处理记录或下游幂等查询防止重复业务效果。

### Temporal Activity

如果外部副作用已成功但 Activity completion/result 尚未写入 workflow history，Activity 可能被重试。合格设计必须让重试携带同一个 request id，并由下游唯一约束、查询或对账解释结果。

### 外部渠道和供应商

响应超时不是失败。渠道或供应商可能稍后成功，因此本地必须进入 unknown、查询、回调、对账或人工处理，而不是直接再次发起不可关联的扣款、退款或预订。

## 危险误用

| 误用 | 后果 | 正确做法 |
| --- | --- | --- |
| 用 kill process 代替故障模型 | 不知道故障前有哪些事实 | 先定义注入点和已提交 Fact |
| 只验证服务能恢复启动 | 事实分叉仍然存在 | 检查恢复后业务事实是否可解释 |
| 故障后简单重试外部请求 | 重复扣款、重复出票、重复退款 | 使用 request id、查询和幂等重试 |
| 对账失败后直接改数据 | 修复不可审计 | 生成差错、修复命令、审批和复核 |

## 输出结论

故障注入用例的输出应该包括：注入点、故障前 Fact、恢复动作、禁止重复动作、最终终态和 oracle 检查结果。只有这些信息齐全，故障注入才是在验证一致性，而不是只是在测试系统会不会重启。
````

- [ ] **Step 2: Verify fault injection anchors**

Run:

```bash
rg -n "故障注入|本地事务|Outbox|broker|消费者|Activity completion|workflow history|渠道响应超时|供应商成功回调迟到|对账任务|人工审批|request id" financial-consistency/06-verification-lab/04-fault-injection.md
```

Expected: output includes all injection points.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/06-verification-lab/04-fault-injection.md
git commit -m "docs: define consistency fault injection points"
```

Expected: commit succeeds and includes only `04-fault-injection.md`.

## Task 6: Create History Replay Document

**Files:**
- Create: `financial-consistency/06-verification-lab/05-history-replay.md`

- [ ] **Step 1: Add history replay content**

Use `apply_patch` to create `financial-consistency/06-verification-lab/05-history-replay.md`:

````markdown
# 05 历史回放

## 目标

历史回放用同一批事实构造不同顺序，检查系统是否仍能解释状态、资金、外部系统、事件传播、对账和人工修复。它特别适合验证重复、乱序、迟到成功、迟到失败、CDC offset 回退和人工修复交错。

历史回放不能替代对账。它帮助我们验证系统如何解释已有事实和迟到事实，对账仍然负责发现生产中的事实差异。

## 回放类型

| 回放类型 | 构造方式 | 风险 | 检查重点 |
| --- | --- | --- | --- |
| 原始顺序 | 按发生时间回放 | 基线是否可解释 | 每个状态都有前置事实 |
| 回调先到 | 回调早于本地查询结果 | 本地状态未准备好 | 幂等和状态机是否接收或挂起 |
| 成功先到、失败迟到 | 成功事实之后收到失败 | 成功被覆盖 | 状态机拒绝倒退 |
| 失败先到、成功迟到 | 本地失败之后外部成功 | 外部成功不可解释 | unknown 和对账路径 |
| 消息重复 | 同一 event id 多次出现 | 重复业务效果 | 消费者幂等 |
| CDC offset 回退 | 已投影变化再次捕获 | 投影重复或倒退 | 版本号和投影幂等 |
| 人工修复交错 | 自动补偿和人工修复同时出现 | 重复修复或覆盖事实 | maker-checker 和修复幂等 |
| 对账后重放 | 差错修复后重新对账 | 报表调平但事实不解释 | 差错分类和复核结果 |

## 回放输入

每段 replay history 至少包含：

- 原始命令。
- 幂等键。
- 领域事实。
- 事件或 CDC 变化。
- 外部请求号、渠道流水或供应商请求号。
- 查询结果或回调。
- 账本分录。
- 对账差错。
- 人工修复记录。

## 检查规则

- 状态机不能倒退。
- 成功事实不能被迟到失败覆盖。
- 失败事实不能删除迟到成功。
- unknown 不能被本地直接裁决。
- 每个资金动作都有原始请求、幂等键和账本分录。
- 每个外部成功都有请求号、查询、回调或账单证据。
- 每个人工修复都有证据快照、审批、修复命令和复核结果。
- 每个传播事实都能追溯到已经落库的领域事实。

## 示例：支付迟到成功

```text
1. CreatePayment(payment_request_id=P1)
2. ChannelTimeout(P1)
3. LocalState(PAYMENT_UNKNOWN)
4. ManualReviewStarted(P1)
5. ChannelSuccessCallback(P1, channel_txn=C1)
6. LedgerPostingCreated(P1, C1)
7. ReconciliationMatched(P1, C1)
```

合格结果：本地不能在第 2 步把支付判失败并发起无关联二次扣款。第 5 步迟到成功必须能推进到成功、补账、对账匹配或人工复核完成。

## 示例：供应商迟到失败

```text
1. SupplierBookingRequested(S1)
2. SupplierSuccessCallback(S1, ticket_no=T1)
3. OrderSubItemConfirmed(S1)
4. SupplierFailureCallback(S1)
```

合格结果：第 4 步不能覆盖第 2 步已确认成功事实。系统应记录迟到失败回调、拒绝状态倒退，并在必要时进入对账或人工处理。

## 危险误用

| 误用 | 后果 | 正确做法 |
| --- | --- | --- |
| 只按原始顺序回放 | 无法发现乱序和迟到问题 | 生成多种顺序 |
| 回放只检查最终状态 | 账本和外部事实可能不可解释 | 同时检查资金、外部和人工事实 |
| 把 replay 当生产修复 | 测试动作污染真实事实 | replay 只读或在隔离环境执行 |
| 迟到事实直接丢弃 | 外部成功或失败不可解释 | 记录并由状态机、对账或人工处理解释 |

## 输出结论

历史回放的输出应该是一份 replay report：输入 History、回放顺序、状态迁移、生成事实、被拒绝事件、不变量检查结果和需要人工解释的差异。
````

- [ ] **Step 2: Verify history replay anchors**

Run:

```bash
rg -n "历史回放|回调先到|成功先到|失败迟到|消息重复|CDC offset 回退|人工修复交错|对账后重放|PAYMENT_UNKNOWN|replay report" financial-consistency/06-verification-lab/05-history-replay.md
```

Expected: output includes all replay types and report term.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/06-verification-lab/05-history-replay.md
git commit -m "docs: define consistency history replay"
```

Expected: commit succeeds and includes only `05-history-replay.md`.

## Task 7: Create Scenario Lab Matrix

**Files:**
- Create: `financial-consistency/06-verification-lab/06-scenario-lab-matrix.md`

- [ ] **Step 1: Add scenario matrix content**

Use `apply_patch` to create `financial-consistency/06-verification-lab/06-scenario-lab-matrix.md`:

````markdown
# 06 场景实验矩阵

## 目标

场景实验矩阵把验证模型落回真实业务。每个场景都必须说明事实来源、关键不变量、异常 History、故障注入点、历史回放样例和不合格判定。

## 总览

| 场景 | 重点验证 | 主要 Oracle |
| --- | --- | --- |
| 内部转账 | 幂等、冻结、扣减、入账、account movement、ledger posting、冲正/调整 | 状态机 oracle、资金 oracle |
| 充值提现 | 渠道超时、重复回调、主动查询、渠道账单、本地 unknown、退款和对账 | 状态机 oracle、外部事实 oracle、资金 oracle |
| 电商下单 | 库存预留、支付成功后取消、重复消息、退款、发货和售后 | 状态机 oracle、资金 oracle |
| 旅行组合预订 | 核心项和附加项、供应商未知、已出票、已生效保险、付款策略、罚金、补差、人工处理 | 外部事实 oracle、资金 oracle |

## 内部转账

事实来源：

- 账户余额。
- 冻结金额。
- account movement。
- ledger posting。
- 幂等请求号。
- Outbox 事件。
- 对账差错和人工处理记录。

关键不变量：

- 同一 transfer_request_id 最多产生一个转账业务效果。
- account-service 和 ledger-service 不能共享本地事务，但各自本地事实必须可解释。
- 借贷分录必须平衡。
- account movement 与 ledger posting 分叉时必须重试、补充分录、冲正/调整、对账或人工处理。

异常 History 样例：

```text
CreateTransfer(T1)
DebitAccountSucceeded(T1)
ProcessCrashBeforeLedgerPosting(T1)
RetryTransfer(T1)
LedgerPostingCreated(T1)
ReconciliationMatched(T1)
```

不合格判定：

- 重复扣款。
- 借贷不平。
- 有账户变动但无账本事实和差错记录。
- 人工冲正没有审批和复核。

## 充值提现

事实来源：

- 本地支付单、充值单或提现单。
- 渠道请求号。
- 渠道流水。
- 回调。
- 主动查询结果。
- 渠道账单。
- 账户流水和账本分录。
- 对账差错。

关键不变量：

- `PAYMENT_UNKNOWN`、`WITHDRAW_UNKNOWN`、`REFUND_UNKNOWN` 不能直接当失败。
- 同一渠道 request id 不能产生多次业务效果。
- 成功回调不能被迟到失败覆盖。
- 渠道成功但本地未推进必须进入对账或人工处理。

异常 History 样例：

```text
CreateRecharge(R1)
ChannelRequestSent(R1)
ChannelTimeout(R1)
ChannelSuccessCallback(R1)
DuplicateCallback(R1)
LedgerPostingCreated(R1)
ChannelBillMatched(R1)
```

不合格判定：

- 超时后发起无关联二次扣款。
- 重复回调重复入账。
- 渠道账单成功但本地失败且没有差错。
- 退款成功但账本无分录。

## 电商下单

事实来源：

- 订单。
- 库存预留、确认和释放记录。
- 支付请求和支付结果。
- 退款请求和退款结果。
- 发货或取消事实。
- Outbox 事件和消费者处理记录。
- 商户结算和账本依据。

关键不变量：

- 库存预留只能确认或释放一次。
- 支付成功后取消必须进入退款和账本路径。
- 重复消息不能重复确认库存、重复释放库存或重复退款。
- 已发货订单不能被普通取消流程覆盖。

异常 History 样例：

```text
CreateOrder(O1)
ReserveInventory(O1)
PaymentCaptured(O1)
InventoryConfirmMessageDuplicated(O1)
CancelOrderRequested(O1)
RefundRequested(O1)
RefundUnknown(O1)
ReconciliationPending(O1)
```

不合格判定：

- 支付成功后删除订单。
- 库存预留失败仍扣款。
- 重复消息重复扣减库存。
- refund unknown 被直接判失败且无对账路径。

## 旅行组合预订

事实来源：

- 报价快照。
- 组合订单和子订单状态。
- 供应商请求号、订单号、出票、酒店确认、保险生效。
- 支付授权、capture、void、refund。
- 罚金、补差、账本分录。
- 人工处理工单、审批和复核。
- 供应商账单和对账差错。

关键不变量：

- 核心项和附加项必须分层处理。
- 已出票机票和已生效保险不能被本地字段回滚。
- `SUPPLIER_UNKNOWN` 不能直接失败。
- 已 capture 资金不能 void，只能 refund、冲正、调整或人工处理。
- workflow history 不是供应商事实、支付事实、退款事实或账本事实。

异常 History 样例：

```text
CreateTrip(TR1)
FlightTicketed(TR1)
HotelFailed(TR1)
PaymentCaptured(TR1)
CompensationStarted(TR1)
RefundUnknown(TR1)
ManualReviewOpened(TR1)
SupplierBillReceived(TR1)
ReconciliationMismatch(TR1)
```

不合格判定：

- 附加项失败取消核心行程。
- 供应商未知直接失败。
- 已出票事实被删除。
- 退款未知无查询、对账或人工处理。
- workflow completion 被当成账平。

## 输出结论

场景实验矩阵的作用是防止验证方法脱离业务。每个实验都必须说清：事实从哪里来、什么不能违反、异常 History 如何构造、失败时说明哪条一致性边界有缺口。
````

- [ ] **Step 2: Verify scenario anchors**

Run:

```bash
rg -n "内部转账|充值提现|电商下单|旅行组合预订|account movement|ledger posting|PAYMENT_UNKNOWN|WITHDRAW_UNKNOWN|REFUND_UNKNOWN|SUPPLIER_UNKNOWN|workflow history|不合格判定" financial-consistency/06-verification-lab/06-scenario-lab-matrix.md
```

Expected: output includes all scenarios, unknown states, and disqualification term.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/06-verification-lab/06-scenario-lab-matrix.md
git commit -m "docs: map verification lab scenarios"
```

Expected: commit succeeds and includes only `06-scenario-lab-matrix.md`.

## Task 8: Create Code Lab Roadmap

**Files:**
- Create: `financial-consistency/06-verification-lab/07-code-lab-roadmap.md`

- [ ] **Step 1: Add code roadmap content**

Use `apply_patch` to create `financial-consistency/06-verification-lab/07-code-lab-roadmap.md`:

````markdown
# 07 代码实验室路线图

## 目标

本章只定义后续可运行 Java 验证实验室的工程路线，不直接创建代码、不引入依赖、不绑定版本。它回答：如果下一阶段要把文档实验室落成代码，应该如何分层。

## 推荐结构

```text
verification-lab/
  model/
    Command
    Event
    Fact
    History
    State
    InvariantViolation
  oracle/
    StateMachineOracle
    LedgerOracle
    ExternalFactOracle
    PropagationOracle
    ManualRepairOracle
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

## 模块职责

| 模块 | 职责 | 不负责 |
| --- | --- | --- |
| model | 表达 Command、Event、Fact、History、State 和 violation | 不连接数据库 |
| oracle | 检查不变量并输出 violation | 不执行业务命令 |
| generator | 生成异常 History | 不判断测试是否通过 |
| runner | 运行属性测试、故障注入和历史回放 | 不保存生产事实 |
| scenarios | 放置转账、支付、电商、旅行的领域样例 | 不复用生产服务代码 |

## 技术候选

| 技术 | 未来用途 | 当前阶段动作 |
| --- | --- | --- |
| JUnit 5 | 基础测试框架 | 只记录候选，不引入 |
| jqwik | Java 属性测试 | 只记录候选，不查 API |
| Testcontainers | 后续接入数据库、Kafka 或 Temporal test server | 只记录候选，不引入 |
| Spring Boot test slice | 验证服务边界 | 只记录候选，不创建工程 |

## 第一批可运行实验建议

未来进入代码阶段时，优先实现这些实验：

1. 内部转账幂等和账本平衡。
2. 支付超时后迟到成功回调。
3. Outbox publisher 崩溃后恢复发布。
4. 消费者重复消息不重复业务效果。
5. TCC Cancel 先于 Try 和 Confirm/Cancel 并发。
6. Temporal Activity 外部成功但 completion 未记录后的重试幂等。
7. CDC offset 回退导致投影重复。
8. 人工修复命令重复提交。

## 设计约束

- 测试模型不能依赖真实生产数据库。
- Oracle 不能调用真实外部渠道。
- Generator 只生成 History，不直接修改事实。
- Runner 输出最小失败 History 和被破坏的不变量。
- 所有未来代码都要能解释失败，而不是只输出 assertion failed。

## 危险误用

| 误用 | 后果 | 正确做法 |
| --- | --- | --- |
| 一开始接入真实 Kafka 和 Temporal | 学习者被基础设施复杂度淹没 | 先做纯模型和 oracle |
| 复用生产服务代码做 oracle | 测试重复生产 bug | oracle 用独立判定规则 |
| 只写 JUnit happy path | 无法发现异常历史问题 | 先实现异常 History 生成器 |
| 把路线图当实现完成 | 没有可运行验证能力 | 后续单独开代码实现阶段 |

## 输出结论

代码实验室应从纯模型开始，先把 Command、Event、Fact、History、InvariantViolation 和 oracle 跑通，再逐步接入属性测试、故障注入、历史回放，最后才考虑 Testcontainers、Kafka、Temporal 或数据库。
````

- [ ] **Step 2: Verify code roadmap anchors**

Run:

```bash
rg -n "verification-lab|Command|Event|Fact|History|InvariantViolation|StateMachineOracle|LedgerOracle|ExternalFactOracle|PropertyTestRunner|FaultInjectionRunner|HistoryReplayRunner|JUnit 5|jqwik|Testcontainers" financial-consistency/06-verification-lab/07-code-lab-roadmap.md
```

Expected: output includes future structure and technology candidates.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/06-verification-lab/07-code-lab-roadmap.md
git commit -m "docs: outline verification code lab roadmap"
```

Expected: commit succeeds and includes only `07-code-lab-roadmap.md`.

## Task 9: Create Interview Synthesis

**Files:**
- Create: `financial-consistency/06-verification-lab/08-interview-synthesis.md`

- [ ] **Step 1: Add interview synthesis content**

Use `apply_patch` to create `financial-consistency/06-verification-lab/08-interview-synthesis.md`:

````markdown
# 08 面试与架构评审表达

## 一句话回答

金融级一致性验证不是只证明正常流程能跑通，而是用不变量、异常 History、oracle、属性测试、故障注入、历史回放、对账和人工复核，降低系统产生不可解释事实的风险。

## 标准回答结构

1. 先说明要保护的 Fact：账户、账本、渠道、供应商、库存、人工审批。
2. 再说明不变量：幂等、状态机、借贷平衡、unknown 处理、补偿追加事实。
3. 再说明异常 History：重复、乱序、迟到、超时、宕机、人工修复。
4. 再说明验证方法：属性测试、故障注入、历史回放、对账验证。
5. 最后说明边界：测试降低风险，但不能证明所有历史绝对安全。

## 高频问题

### 为什么普通单元测试不够？

普通单元测试容易只覆盖 happy path。金融级一致性风险通常出现在重复请求、乱序消息、迟到回调、外部超时、宕机恢复、人工修复和对账差错中，所以必须验证异常 History。

### 什么是不变量？

不变量是系统永远不能违反的承诺，例如同一幂等键最多一个业务效果、借贷分录必须平衡、已 capture 资金不能 void、unknown 不能被本地直接判失败。

### 什么是 oracle？

Oracle 是测试视角的判定器。状态机 oracle 检查迁移是否合法，资金 oracle 检查余额和账本是否可解释，外部事实 oracle 检查渠道、供应商和人工修复事实是否和本地事实一致。

### 属性测试在这里测什么？

它不是随机金额和字符串，而是随机生成异常 History，例如重复命令、重复消息、乱序回调、TCC Cancel 先于 Try、Activity 重试、CDC offset 回退和人工修复重复提交。

### 故障注入应该注入什么？

应该注入最容易产生事实分叉的位置：本地事务提交后、Outbox sent 前、消费者外部副作用后、Activity completion 未写入 workflow history、渠道响应超时、供应商回调迟到、对账任务中断和人工修复重复执行。

### 历史回放有什么价值？

历史回放用同一批事实构造不同顺序，验证状态机、账本、外部事实和人工修复是否仍然可解释。它特别适合发现迟到成功覆盖、迟到失败倒退、重复投影和人工修复交错问题。

### 测试能证明系统完全正确吗？

不能。测试只能在生成器、故障注入和回放覆盖的范围内降低风险。金融系统还需要生产监控、对账、审计、人工复核和持续修复闭环。

## 评审底线

- 不接受“正常流程跑通，所以一致性没问题”。
- 不接受“用了框架，所以不用故障注入”。
- 不接受“属性测试证明系统绝对正确”。
- 不接受“unknown 可以直接当失败”。
- 不接受“对账脚本直接改领域事实”。
- 不接受“workflow history、broker offset 或日志替代账本事实”。
- 不接受“人工修复没有证据、审批和复核”。

## 面试收束

高级回答应该把验证讲成事实闭环：先定义 Fact 和不变量，再生成异常 History，用 oracle 检查状态机、资金和外部事实，最后通过对账和人工复核处理自动测试无法收敛的问题。
````

- [ ] **Step 2: Verify interview anchors**

Run:

```bash
rg -n "普通单元测试不够|什么是不变量|什么是 oracle|属性测试|故障注入|历史回放|测试能证明系统完全正确吗|评审底线|workflow history|broker offset" financial-consistency/06-verification-lab/08-interview-synthesis.md
```

Expected: output includes all high-frequency questions and boundary warnings.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/06-verification-lab/08-interview-synthesis.md
git commit -m "docs: add verification lab interview synthesis"
```

Expected: commit succeeds and includes only `08-interview-synthesis.md`.

## Task 10: Update Root README

**Files:**
- Modify: `financial-consistency/README.md`

- [ ] **Step 1: Add design spec link**

In `financial-consistency/README.md`, add this line to the formal design document list after the patterns design link:

```markdown
- [2026-05-02-financial-consistency-verification-lab-design.md](../docs/superpowers/specs/2026-05-02-financial-consistency-verification-lab-design.md)
```

- [ ] **Step 2: Link phase 06 route**

Change:

```markdown
- 06-verification-lab
  不变量、模型验证、属性测试、故障注入、历史检查、恢复演练。
```

to:

```markdown
- [06-verification-lab](./06-verification-lab/README.md)
  不变量、模型验证、属性测试、故障注入、历史检查、恢复演练。
```

- [ ] **Step 3: Verify root README links**

Run:

```bash
rg -n "2026-05-02-financial-consistency-verification-lab-design.md|\./06-verification-lab/README.md" financial-consistency/README.md
```

Expected: output includes both links.

- [ ] **Step 4: Commit**

Run:

```bash
git add financial-consistency/README.md
git commit -m "docs: link verification lab phase"
```

Expected: commit succeeds and includes only `financial-consistency/README.md`.

## Task 11: Final Documentation Verification

**Files:**
- Verify: `financial-consistency/06-verification-lab/**`
- Verify: `financial-consistency/README.md`

- [ ] **Step 1: Verify all phase files exist**

Run:

```bash
find financial-consistency/06-verification-lab -maxdepth 1 -type f | sort
```

Expected output:

```text
financial-consistency/06-verification-lab/01-verification-model.md
financial-consistency/06-verification-lab/02-invariant-catalog.md
financial-consistency/06-verification-lab/03-property-testing.md
financial-consistency/06-verification-lab/04-fault-injection.md
financial-consistency/06-verification-lab/05-history-replay.md
financial-consistency/06-verification-lab/06-scenario-lab-matrix.md
financial-consistency/06-verification-lab/07-code-lab-roadmap.md
financial-consistency/06-verification-lab/08-interview-synthesis.md
financial-consistency/06-verification-lab/README.md
```

- [ ] **Step 2: Verify README child links**

Run:

```bash
rg -n "\./01-verification-model.md|\./02-invariant-catalog.md|\./03-property-testing.md|\./04-fault-injection.md|\./05-history-replay.md|\./06-scenario-lab-matrix.md|\./07-code-lab-roadmap.md|\./08-interview-synthesis.md" financial-consistency/06-verification-lab/README.md
```

Expected: output includes all 8 child document links.

- [ ] **Step 3: Verify verification model anchors**

Run:

```bash
rg -n "Command|Event|Fact|History|Invariant|Oracle|不变量|属性测试|故障注入|历史回放|workflow history|broker offset|PAYMENT_UNKNOWN|REFUND_UNKNOWN|SUPPLIER_UNKNOWN" financial-consistency/06-verification-lab
```

Expected: output includes core verification terms across the phase docs.

- [ ] **Step 4: Verify scenario mappings**

Run:

```bash
rg -n "内部转账|充值提现|电商下单|旅行组合预订|account movement|ledger posting|渠道超时|重复回调|库存预留|已出票|已生效保险|人工处理" financial-consistency/06-verification-lab
```

Expected: output includes all mapped scenarios and scenario-specific risks.

- [ ] **Step 5: Verify code roadmap stays documentation-only**

Run:

```bash
rg -n "不直接创建代码|不引入依赖|只记录候选|不绑定版本|不查 API|不创建工程" financial-consistency/06-verification-lab/07-code-lab-roadmap.md
```

Expected: output confirms roadmap remains documentation-only.

- [ ] **Step 6: Verify root README link**

Run:

```bash
rg -n "2026-05-02-financial-consistency-verification-lab-design.md|\./06-verification-lab/README.md" financial-consistency/README.md
```

Expected: output includes both root README links.

- [ ] **Step 7: Verify previous phases were not changed in this phase**

Run:

```bash
git diff --name-only main..HEAD -- financial-consistency/01-transfer financial-consistency/02-payment-recharge-withdraw financial-consistency/03-order-payment-inventory financial-consistency/04-travel-booking-saga financial-consistency/05-patterns
```

Expected: no output when run from a feature branch based on current `main`.

- [ ] **Step 8: Scan for incomplete-document markers**

Run:

```bash
rg -n "TO[D]O|TB[D]|待[定]|占[位]|以[后]补|未[决]|大[概]|随[便]" financial-consistency/06-verification-lab financial-consistency/README.md
```

Expected: no output and exit code `1`.

- [ ] **Step 9: Check Markdown whitespace**

Run:

```bash
git diff --check
```

Expected: no output and exit code `0`.

- [ ] **Step 10: Verify only expected work remains**

Run:

```bash
git status --short
```

Expected: no tracked file modifications related to this phase. Existing unrelated untracked files outside this phase may remain and must not be added to phase commits.
