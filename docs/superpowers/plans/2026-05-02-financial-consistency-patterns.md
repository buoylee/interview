# Financial Consistency Patterns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `05-patterns` learning module that turns Outbox, Saga, TCC, Temporal, transactional messages, CDC, state machines, idempotency, framework comparison, composition, and verification into a decision-oriented consistency handbook.

**Architecture:** This is a documentation-only phase. Each file owns one decision surface: decision map, individual patterns, framework positioning, pattern composition, verification, and interview synthesis. The module must reuse lessons from `01-transfer`, `02-payment-recharge-withdraw`, `03-order-payment-inventory`, and `04-travel-booking-saga` without modifying those existing phase files.

**Tech Stack:** Markdown, Git, `rg`, `find`, `git diff --check`, Context7 CLI for framework documentation checks during framework-specific tasks.

---

## File Structure

- Create directory: `financial-consistency/05-patterns/`
- Create: `financial-consistency/05-patterns/README.md`
- Create: `financial-consistency/05-patterns/01-decision-map.md`
- Create: `financial-consistency/05-patterns/02-outbox-local-message-table.md`
- Create: `financial-consistency/05-patterns/03-saga.md`
- Create: `financial-consistency/05-patterns/04-tcc.md`
- Create: `financial-consistency/05-patterns/05-temporal.md`
- Create: `financial-consistency/05-patterns/06-transactional-message-cdc.md`
- Create: `financial-consistency/05-patterns/07-framework-comparison.md`
- Create: `financial-consistency/05-patterns/08-pattern-composition.md`
- Create: `financial-consistency/05-patterns/09-verification.md`
- Create: `financial-consistency/05-patterns/10-interview-synthesis.md`
- Modify: `financial-consistency/README.md`

Do not modify:

- `financial-consistency/01-transfer/**`
- `financial-consistency/02-payment-recharge-withdraw/**`
- `financial-consistency/03-order-payment-inventory/**`
- `financial-consistency/04-travel-booking-saga/**`

## Task 1: Create Phase README

**Files:**
- Create: `financial-consistency/05-patterns/README.md`

- [ ] **Step 1: Create directory**

Run:

```bash
mkdir -p financial-consistency/05-patterns
```

Expected: command succeeds.

- [ ] **Step 2: Add README content**

Use `apply_patch` to create `financial-consistency/05-patterns/README.md`:

````markdown
# 05 一致性模式与框架选型

## 目标

这一阶段把前四个业务阶段沉淀成模式决策手册。重点不是背诵 Outbox、Saga、TCC、Temporal、事务消息、CDC 的定义，而是判断真实业务问题应该用哪个模式、哪个模式不能解决什么、以及如何验证模式真的保护了一致性。

## 学习顺序

1. [决策地图](./01-decision-map.md)
2. [Outbox 和本地消息表](./02-outbox-local-message-table.md)
3. [Saga](./03-saga.md)
4. [TCC](./04-tcc.md)
5. [Temporal](./05-temporal.md)
6. [事务消息和 CDC](./06-transactional-message-cdc.md)
7. [框架比较](./07-framework-comparison.md)
8. [模式组合](./08-pattern-composition.md)
9. [验证方法](./09-verification.md)
10. [面试表达](./10-interview-synthesis.md)

## 核心问题

- Outbox、Saga、TCC、Temporal、事务消息和 CDC 分别解决什么问题？
- 为什么一个框架不能替代状态机、幂等、账本和对账？
- 为什么 Saga 的补偿不是回滚？
- 为什么 TCC 的 Try 必须真实预留资源？
- 为什么 Temporal 适合长流程编排，但不能当业务事实来源？
- 为什么用了 Kafka 或事务消息仍然需要 Outbox、消费者幂等和对账？
- 为什么金融级系统必须验证模式在超时、重复、乱序、宕机和人工修复下仍然成立？

## 本阶段结论

一致性模式不是可互换的名词。真实系统通常组合使用状态机、幂等、Outbox、Saga、TCC-like 资源预留、Temporal 编排、事务消息或 CDC、对账和人工修复。每个模式都必须明确事实来源、适用边界、危险误用和验证方法。
````

- [ ] **Step 3: Verify README links**

Run:

```bash
rg -n "\./01-decision-map.md|\./02-outbox-local-message-table.md|\./03-saga.md|\./04-tcc.md|\./05-temporal.md|\./06-transactional-message-cdc.md|\./07-framework-comparison.md|\./08-pattern-composition.md|\./09-verification.md|\./10-interview-synthesis.md" financial-consistency/05-patterns/README.md
```

Expected: output includes all 10 child document links.

- [ ] **Step 4: Commit**

Run:

```bash
git add financial-consistency/05-patterns/README.md
git commit -m "docs: add consistency patterns module entry"
```

Expected: commit succeeds and includes only `financial-consistency/05-patterns/README.md`.

## Task 2: Create Decision Map

**Files:**
- Create: `financial-consistency/05-patterns/01-decision-map.md`

- [ ] **Step 1: Add decision map content**

Use `apply_patch` to create `financial-consistency/05-patterns/01-decision-map.md`:

````markdown
# 01 决策地图

## 目的

决策地图回答一个真实架构问题：面对跨服务一致性需求时，应该先识别业务事实、外部系统、资源可逆性和验证手段，再选择 Outbox、Saga、TCC、Temporal、事务消息、CDC 或组合模式。

## 决策问题

| 问题 | 如果答案是是 | 常见模式 | 不能误解成 |
| --- | --- | --- | --- |
| 只需要保证本地状态变更和事件发布一致吗 | 本地事务提交后要可靠发事件 | Outbox / 本地消息表 | 下游业务已经完成 |
| 流程跨多个服务且需要多步推进吗 | 每个服务只提交自己的本地事务 | Saga | 强原子提交 |
| 资源能预留、确认和取消吗 | Try 能锁定资源，Confirm/Cancel 有明确语义 | TCC | 任意外部接口都能 TCC |
| 流程持续很久且需要超时、重试和人工等待吗 | 需要可恢复 workflow | Temporal | 业务事实来源或账本 |
| 消息中间件提供事务发送语义吗 | 可以绑定本地事务和消息发送 | 事务消息 | 跨服务事务 |
| 需要从数据库提交日志生成事实流吗 | 下游读模型或集成要跟随数据库事实 | CDC | 领域事件建模 |
| 状态是否有非法转换风险 | 需要拒绝重复、乱序和错误推进 | 状态机 + 幂等 | 可选增强 |
| 外部事实和本地事实可能长期分叉吗 | 必须事后发现并修复差错 | 对账 + 人工修复 | 报表系统 |

## 场景映射

### 内部转账

推荐组合：

```text
状态机 + 幂等 + 账本 + Outbox + 对账
```

转账内部账户更新不能直接用 Saga 逃避账本一致性。扣减、入账、流水和会计分录必须由本地事务、唯一约束、状态机和账本规则保护。Outbox 只传播已经落库的事实，对账验证账户、流水和分录能互相解释。

### 充值、提现和支付回调

推荐组合：

```text
状态机 + 渠道幂等 + 查询/回调 + Outbox + 对账 + 人工处理
```

支付渠道超时不是失败。系统必须保留渠道请求号，等待回调、主动查询或读取渠道账单。`PAYMENT_UNKNOWN` 和 `REFUND_UNKNOWN` 不能直接触发重复扣款或重复退款。

### 电商下单、支付、库存和退款

推荐组合：

```text
库存预留/TCC-like + Saga + Outbox + 支付退款状态机 + 对账
```

库存可以预留、确认和释放，适合 TCC-like 资源模型。支付成功后取消不能回滚支付事实，只能进入退款、冲正、账本和对账路径。

### 旅行组合预订

推荐组合：

```text
Temporal Saga + 状态机 + Outbox + 付款策略 + 供应商查询 + 退款 + 对账 + 人工处理
```

机票、酒店、租车和保险来自外部供应商。核心项和附加项必须分层，供应商未知不能直接失败，不可逆动作不能删除历史事实。Temporal 可编排长流程，但供应商事实、资金事实、账本事实和对账事实必须独立持久化。

## 决策底线

- 一个框架不能解决所有一致性问题。
- 消息投递成功不代表业务完成。
- workflow 成功不代表账平。
- Saga 补偿不是删除前序事实。
- TCC 只有在 Try 能真实预留资源时才成立。
- CDC 捕获变化不代表理解业务语义。
- 对账和人工修复是金融级闭环的一部分。
````

- [ ] **Step 2: Verify decision anchors**

Run:

```bash
rg -n "Outbox|Saga|TCC|Temporal|事务消息|CDC|状态机|对账|内部转账|充值、提现|电商下单|旅行组合预订" financial-consistency/05-patterns/01-decision-map.md
```

Expected: output includes all pattern names and mapped scenarios.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/05-patterns/01-decision-map.md
git commit -m "docs: add consistency pattern decision map"
```

Expected: commit succeeds and includes only `01-decision-map.md`.

## Task 3: Create Outbox Document

**Files:**
- Create: `financial-consistency/05-patterns/02-outbox-local-message-table.md`

- [ ] **Step 1: Add Outbox content**

Use `apply_patch` to create `financial-consistency/05-patterns/02-outbox-local-message-table.md`:

````markdown
# 02 Outbox 和本地消息表

## 解决的问题

Outbox 解决的是本地事实和事件发布之间的不一致：业务表已经提交，但进程在发消息前宕机；或者消息发出后，本地事务回滚。金融级系统不能让这两种情况变成不可解释状态。

## 基本模型

```text
本地事务
  -> 写业务事实
  -> 写 Outbox 事件
提交成功
  -> publisher 异步投递 broker
  -> 消费者按业务幂等键处理
```

业务表和 Outbox 表必须在同一数据库事务中提交。Outbox 事件代表本地事实已经落库，不代表下游消费者已经成功，也不代表外部供应商、支付渠道或退款渠道已经完成。

## 保护的事实

- 订单创建后一定有 `BookingCreated`。
- 支付扣款落库后一定有 `PaymentCaptured`。
- 库存确认落库后一定有 `InventoryConfirmed`。
- 旅行供应商确认落库后一定有 `FlightTicketed` 或 `HotelConfirmed`。
- 对账差错落库后一定有 `TravelMismatchDetected`。

## 不能解决的问题

- 不能证明消费者完成业务处理。
- 不能证明供应商确认、支付到账或退款成功。
- 不能自动处理重复消息。
- 不能替代状态机、账本、对账或人工处理。
- 不能让外部不可逆动作变成可回滚。

## 危险误用

| 误用 | 后果 | 正确做法 |
| --- | --- | --- |
| 业务提交后直接发消息，不写 Outbox | 进程宕机导致事件丢失 | 业务事实和 Outbox 同事务提交 |
| 发布失败后重做外部扣款或供应商动作 | 重复扣款、重复出票或重复退款 | 只重试事件投递，不重做外部动作 |
| 消费者只依赖 broker offset | 业务重复或漏处理不可解释 | 消费者使用业务幂等键和处理表 |
| 把消息投递成功当业务完成 | 下游失败但本地误判成功 | 下游完成必须有自己的事实事件 |

## 验证方法

- 在本地事务提交后、publisher 投递前杀进程，验证恢复后事件能补发。
- 暂停 broker，验证业务事实仍能提交，Outbox 保持 pending。
- 重放同一事件，验证消费者只产生一次业务效果。
- 让消费者处理失败，验证 broker offset 不被当作业务完成证明。
- 对账业务事实和 Outbox 事件，验证每个关键事实都有对应事件。

## 面试表达

Outbox 的价值是把“本地事实”和“待发布事件”放进同一个事务。它解决消息不丢的问题，但不解决下游是否成功的问题。金融系统使用 Outbox 后仍然需要消费者幂等、状态机、对账和人工修复。
````

- [ ] **Step 2: Verify Outbox anchors**

Run:

```bash
rg -n "Outbox|本地事务|publisher|broker offset|消费者|幂等|PaymentCaptured|FlightTicketed|TravelMismatchDetected" financial-consistency/05-patterns/02-outbox-local-message-table.md
```

Expected: output includes Outbox mechanics, business examples, and verification terms.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/05-patterns/02-outbox-local-message-table.md
git commit -m "docs: define outbox local message table pattern"
```

Expected: commit succeeds and includes only `02-outbox-local-message-table.md`.

## Task 4: Create Saga Document

**Files:**
- Create: `financial-consistency/05-patterns/03-saga.md`

- [ ] **Step 1: Add Saga content**

Use `apply_patch` to create `financial-consistency/05-patterns/03-saga.md`:

````markdown
# 03 Saga

## 解决的问题

Saga 解决长流程跨服务一致性问题。它把一个大流程拆成多个本地事务，每一步提交自己的事实；当后续步骤失败时，系统执行业务补偿动作，让流程进入可解释终态。

Saga 不提供强原子提交。它的目标不是让所有参与者同时成功或同时失败，而是在部分成功、未知、不可逆和人工处理下保持事实可解释。

## 基本模型

```text
Step 1 local transaction
-> Step 2 local transaction
-> Step 3 local transaction
-> success

if Step N fails:
-> compensate Step N-1
-> compensate Step N-2
-> manual review when compensation is unsafe
```

补偿是业务动作，例如释放库存、void 授权、退款、取消供应商保留、收取罚金、补差、替代供应商或创建人工工单。补偿不是删除历史记录。

## 适用场景

- 电商下单、库存预留、支付、确认库存和退款。
- 旅行组合预订、供应商确认、扣款、附加项失败和人工处理。
- 充值提现中的渠道请求、查询、回调、对账和人工处理。
- 任何单个数据库事务无法覆盖的长流程。

## 不适用或高风险场景

- 要求强一致同步提交的内部账本更新。
- 没有补偿动作的不可逆外部动作。
- 没有子状态、幂等键和审计记录的总状态流程。
- 把供应商超时直接当失败的流程。

## 设计规则

- 每一步都必须有本地状态机。
- 每一步都必须有幂等键。
- 每一步都必须记录已知事实、未知状态和补偿状态。
- 成功事实不能被失败回调覆盖。
- 补偿失败必须进入重试、对账或人工处理。
- 总状态必须能解释每个子步骤的最终状态。

## 典型失败

| 失败 | 错误处理 | 正确处理 |
| --- | --- | --- |
| 库存确认成功但支付失败 | 删除库存记录 | 释放库存或创建人工工单 |
| 支付成功但库存失败 | 本地订单改失败 | 创建退款和账本分录 |
| 机票已出票但酒店失败 | 删除机票事实 | 替代酒店、退票、罚金、退款或人工处理 |
| 供应商超时 | 直接失败补偿 | 标记 `SUPPLIER_UNKNOWN`，查询、回调、对账或人工处理 |

## 验证方法

- 随机生成步骤成功、失败、超时、重复回调和乱序回调。
- 检查已成功步骤不会被本地删除。
- 检查每个补偿动作都有幂等键和审计记录。
- 故障注入任意步骤宕机，验证恢复后流程继续或进入人工处理。
- 对账每个终态是否能解释本地事实、外部事实、资金事实和账本事实。

## 面试表达

Saga 是长流程一致性模式，不是分布式锁，也不是跨库事务。它允许中间状态和部分成功，但要求每一步事实可审计、补偿可解释、未知状态可收敛。
````

- [ ] **Step 2: Verify Saga anchors**

Run:

```bash
rg -n "Saga|补偿|本地事务|幂等|SUPPLIER_UNKNOWN|人工处理|对账|不是删除历史" financial-consistency/05-patterns/03-saga.md
```

Expected: output includes core Saga terms and danger boundaries.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/05-patterns/03-saga.md
git commit -m "docs: define saga consistency pattern"
```

Expected: commit succeeds and includes only `03-saga.md`.

## Task 5: Create TCC Document

**Files:**
- Create: `financial-consistency/05-patterns/04-tcc.md`

- [ ] **Step 1: Add TCC content**

Use `apply_patch` to create `financial-consistency/05-patterns/04-tcc.md`:

````markdown
# 04 TCC

## 解决的问题

TCC 解决可预留资源的一致性问题。它把业务动作拆成 Try、Confirm、Cancel：

- Try：真实预留资源。
- Confirm：确认 Try 预留的资源。
- Cancel：释放 Try 预留的资源。

TCC 成立的前提是业务资源真的支持预留、确认和取消。如果 Try 没有锁住资源，TCC 只是接口命名。

## 适用场景

| 场景 | Try | Confirm | Cancel |
| --- | --- | --- | --- |
| 内部账户 | 冻结余额 | 扣减冻结并入账 | 解冻余额 |
| 库存 | 预留库存 | 扣减预留库存 | 释放预留库存 |
| 支付预授权 | 授权冻结资金 | capture 扣款 | void/release 授权 |

## 不适合场景

- 外部供应商不提供预留语义。
- 机票已经出票或保险已经生效。
- Try 阶段无法隔离资源。
- Cancel 没有可靠结果。
- Confirm 或 Cancel 不是幂等接口。

## 必须处理的问题

### 幂等

Try、Confirm、Cancel 都必须支持重复调用。重复 Confirm 只能确认一次，重复 Cancel 只能释放一次。

### 空回滚

Cancel 可能先于 Try 到达。系统必须能安全记录空回滚，避免后续 Try 又成功造成悬挂。

### 悬挂

Cancel 已经处理后，迟到 Try 不能再预留资源。必须用事务 ID、分支 ID 或业务幂等键拒绝迟到 Try。

### 防并发确认

Confirm 和 Cancel 不能同时成功。状态转换必须用版本号、条件更新或唯一约束保护。

## 危险误用

| 误用 | 后果 |
| --- | --- |
| Try 只做参数校验，没有预留资源 | Confirm 时资源可能已经不存在 |
| Cancel 不幂等 | 重复释放导致余额或库存错误 |
| Confirm 后允许 Cancel | 已完成事实被错误覆盖 |
| 对不可逆外部动作套 TCC | Cancel 无法真实撤销 |

## 验证方法

- 重复调用 Try，验证只预留一次。
- 重复调用 Confirm，验证只确认一次。
- 重复调用 Cancel，验证只释放一次。
- 先 Cancel 后 Try，验证 Try 被拒绝或进入空回滚已处理状态。
- 并发执行 Confirm 和 Cancel，验证不能同时成功。
- 对账冻结、确认、释放和账本分录。

## 面试表达

TCC 的关键不在三段式接口，而在 Try 是否真实预留资源。内部账户、库存和支付预授权适合 TCC-like 模型；已经出票、已生效保险和不支持取消的供应商动作不适合 TCC。
````

- [ ] **Step 2: Verify TCC anchors**

Run:

```bash
rg -n "TCC|Try|Confirm|Cancel|空回滚|悬挂|幂等|冻结余额|预留库存|支付预授权" financial-consistency/05-patterns/04-tcc.md
```

Expected: output includes TCC mechanics and validation anchors.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/05-patterns/04-tcc.md
git commit -m "docs: define tcc consistency pattern"
```

Expected: commit succeeds and includes only `04-tcc.md`.

## Task 6: Create Temporal Document

**Files:**
- Create: `financial-consistency/05-patterns/05-temporal.md`

- [ ] **Step 1: Check current Temporal documentation**

Run Context7 commands according to the repository instruction:

```bash
npx ctx7@latest library Temporal "Temporal Saga workflow activity retry compensation durable execution financial consistency"
```

Expected: choose the official Temporal documentation result, such as `/websites/temporal_io` or `/temporalio/documentation`.

Then run:

```bash
npx ctx7@latest docs /websites/temporal_io "Temporal Saga workflow activity retry compensation durable execution financial consistency"
```

Expected: output includes Temporal positioning for workflows, activities, retries, and Saga compensation. If the chosen library ID differs, use the ID selected from the first command.

- [ ] **Step 2: Add Temporal content**

Use `apply_patch` to create `financial-consistency/05-patterns/05-temporal.md`:

````markdown
# 05 Temporal

## 解决的问题

Temporal 适合承接长流程 Saga、定时查询、超时、重试、人工等待和 workflow 恢复。它让流程编排具备 durable execution 能力：worker 重启后可以从 workflow 历史恢复，timer 和 retry 不依赖单个进程内存。

Temporal 不替代业务事实、状态机、幂等、Outbox、账本或对账。

## 在本教程中的位置

推荐把 Temporal 用作长流程编排主线，尤其适合：

- 旅行组合预订。
- 支付渠道查询和超时轮询。
- 退款未知后的周期查询。
- 人工处理等待。
- 跨服务补偿流程。

## 与 Saga 的关系

Temporal 可以承载 Saga 编排。每个 Activity 调用一个领域服务或外部适配器，每个成功 Activity 对应一个可审计事实或后续补偿动作。失败时，workflow 可以按业务顺序触发补偿。

补偿必须按业务可逆性设计：

- 库存预留可以释放。
- 支付授权可以 void。
- 已 capture 资金只能 refund。
- 已出票机票可能只能退票、收罚金、补差或人工处理。
- 已生效保险不能通过删除本地字段回滚。

## 必须遵守的边界

- Activity 必须幂等。
- 外部请求必须有业务 request id。
- Workflow 不能直接修改多个服务数据库。
- Workflow history 不是账本。
- Workflow 成功不代表供应商账单、支付渠道、退款渠道和内部账本全部一致。
- `SUPPLIER_UNKNOWN`、`PAYMENT_UNKNOWN`、`REFUND_UNKNOWN` 不能在 workflow 中被直接裁决为失败。

## 危险误用

| 误用 | 后果 | 正确做法 |
| --- | --- | --- |
| 把 workflow history 当业务事实 | 领域服务和账本不可解释 | 业务事实落领域库，workflow 只编排 |
| Activity 没有幂等键 | worker 重试造成重复扣款或重复供应商订单 | 每个 Activity 使用业务幂等键 |
| workflow 内直接改多个库 | 绕过服务边界和审计 | 调用领域服务命令 |
| 超时直接失败 | 外部系统可能已经成功 | 查询、等待回调、对账或人工处理 |

## 验证方法

- worker 在 Activity 完成后、workflow 记录下一步前重启，验证不会重复外部动作。
- Activity 超时后重试，验证幂等键阻止重复扣款、重复退款或重复供应商预订。
- timer 恢复后继续查询支付、退款或供应商状态。
- 人工等待期间重启 worker，验证 workflow 能恢复等待状态。
- 对账 workflow 结果和领域事实、渠道事实、账本事实。

## 面试表达

Temporal 解决的是可靠长流程执行和编排，不是分布式事务数据库。它非常适合 Saga、超时、重试和人工等待，但业务事实必须由领域服务、支付服务、退款服务、账本、Outbox 和对账共同保证。
````

- [ ] **Step 3: Verify Temporal anchors**

Run:

```bash
rg -n "Temporal|durable execution|Workflow|Activity|Saga|补偿|幂等|workflow history|SUPPLIER_UNKNOWN|PAYMENT_UNKNOWN|REFUND_UNKNOWN|对账" financial-consistency/05-patterns/05-temporal.md
```

Expected: output includes Temporal mechanics and boundaries.

- [ ] **Step 4: Commit**

Run:

```bash
git add financial-consistency/05-patterns/05-temporal.md
git commit -m "docs: define temporal orchestration boundary"
```

Expected: commit succeeds and includes only `05-temporal.md`.

## Task 7: Create Transactional Message and CDC Document

**Files:**
- Create: `financial-consistency/05-patterns/06-transactional-message-cdc.md`

- [ ] **Step 1: Add transactional message and CDC content**

Use `apply_patch` to create `financial-consistency/05-patterns/06-transactional-message-cdc.md`:

````markdown
# 06 事务消息和 CDC

## 目的

事务消息、CDC 和 Outbox 都常被用来连接数据库事实和消息流，但它们解决的问题不同。本章比较三者的边界，防止把消息机制误认为业务一致性本身。

## 事务消息

事务消息通常依赖特定消息中间件语义，把本地事务和消息发送绑定起来。典型流程包含半消息、执行本地事务、提交或回滚消息、异常时 broker 回查本地事务状态。

它适合解决：

- 本地事务和消息发送之间的一致性。
- 消息发送状态未知后的回查。
- 简化部分 Outbox publisher 工作。

它不能解决：

- 消费者业务是否成功。
- 消费者幂等。
- 外部供应商事实。
- 支付、退款和账本对账。
- 跨多个服务的强原子提交。

## CDC

CDC 从数据库提交日志捕获变化，把已经提交的数据库事实流出到下游。

它适合：

- 构建读模型。
- 同步搜索索引。
- 审计和数据集成。
- 从 legacy 数据库抽取事实流。
- 减少应用内 publisher 逻辑。

它不能解决：

- 业务事件语义建模。
- 补偿规则。
- 消费者幂等。
- 乱序投影。
- schema 变化导致的下游兼容。
- 外部系统是否成功。

## Outbox、事务消息、CDC 对比

| 机制 | 事实来源 | 优点 | 主要风险 |
| --- | --- | --- | --- |
| Outbox | 应用显式写业务事实和事件 | 业务语义清楚，和领域事件天然一致 | 需要 publisher 和清理机制 |
| 事务消息 | broker 和本地事务状态协作 | 中间件支持时流程简洁 | 依赖 broker 语义和回查实现 |
| CDC | 数据库提交日志 | 对已有数据库侵入较低 | 数据变化不等于领域事件 |

## 金融级结论

金融级系统更关心事实可解释性，而不是只关心消息是否送达。不管选择 Outbox、事务消息还是 CDC，都不能省略：

- 消费者幂等。
- 状态机合法转换。
- 业务唯一约束。
- 账本分录。
- 对账。
- 人工修复审计。

## 验证方法

- 事务消息：模拟半消息提交后服务宕机，验证 broker 回查不会重复业务动作。
- 事务消息：重复投递同一消息，验证消费者只处理一次。
- CDC：重复捕获同一数据库变化，验证下游投影幂等。
- CDC：乱序到达，验证投影使用版本号或事件时间处理。
- Outbox：publisher 崩溃恢复后只补发事件，不重做外部动作。
- 三者共同验证：消息传播成功不能被当作支付成功、退款成功、供应商确认或账本已平。

## 面试表达

事务消息和 CDC 是消息传播机制，不是完整业务一致性方案。Outbox 更贴近领域事件，事务消息依赖 broker 语义，CDC 依赖数据库日志。三者都需要消费者幂等、状态机和对账。
````

- [ ] **Step 2: Verify message and CDC anchors**

Run:

```bash
rg -n "事务消息|半消息|回查|CDC|Outbox|消费者幂等|状态机|对账|领域事件" financial-consistency/05-patterns/06-transactional-message-cdc.md
```

Expected: output includes comparison and verification anchors.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/05-patterns/06-transactional-message-cdc.md
git commit -m "docs: compare transactional message and cdc"
```

Expected: commit succeeds and includes only `06-transactional-message-cdc.md`.

## Task 8: Create Framework Comparison Document

**Files:**
- Create: `financial-consistency/05-patterns/07-framework-comparison.md`

- [ ] **Step 1: Fetch official framework documentation**

Use Context7 according to repository instructions. Run at most three Context7 CLI commands in this task before writing:

```bash
npx ctx7@latest library Temporal "Temporal workflow activity saga compensation durable execution"
npx ctx7@latest library Camunda "Camunda BPMN process orchestration human task workflow"
npx ctx7@latest library Seata "Seata AT TCC Saga distributed transaction"
```

Expected: each command returns an official or high-reputation library ID. If a library result is unclear, use the official website through normal research in a separate review step before finalizing this document.

- [ ] **Step 2: Add framework comparison content**

Use `apply_patch` to create `financial-consistency/05-patterns/07-framework-comparison.md`:

````markdown
# 07 框架比较

## 目标

本章从国际视角比较 Temporal、Camunda 和 Seata。比较目的不是排名，而是判断它们分别适合解决什么问题、不能解决什么问题，以及在金融级一致性教程中的位置。

## 对比表

| 框架 | 核心定位 | 适合解决 | 不适合解决 |
| --- | --- | --- | --- |
| Temporal | durable execution 和 workflow 编排 | 长流程 Saga、超时、重试、人工等待、恢复执行 | 业务事实、账本、对账、跨服务强原子提交 |
| Camunda | BPMN 流程建模和业务流程编排 | 人工任务、审批流、流程可视化、业务流程治理 | 资金事实保护、支付幂等、账本一致性 |
| Seata | 分布式事务模式框架 | 理解 AT、TCC、Saga 等模式，部分受控服务间事务 | 外部不可控供应商、国际金融架构主线、替代对账 |

## Temporal

Temporal 推荐作为本教程的长流程编排主线。它适合把旅行组合预订、支付查询、退款轮询、人工等待和补偿动作编排成可恢复 workflow。

边界：

- Activity 必须幂等。
- workflow history 不是账本。
- Temporal 不能证明供应商、支付、退款和账本事实一致。
- 仍然需要 Outbox、状态机、账本、对账和人工修复。

## Camunda

Camunda 更偏 BPMN、流程建模、人工任务和业务流程治理。它适合表达审批流、运营处理流、人工任务和跨部门业务流程。

边界：

- BPMN 流程图不是资金事实。
- 人工任务完成不代表支付、退款或账本完成。
- Camunda 可以帮助流程治理，但不能替代幂等、唯一约束、账本和对账。

## Seata

Seata 适合理解分布式事务框架中的 AT、TCC、Saga 等模式，尤其能帮助学习者认识不同事务模式的工程取舍。

边界：

- AT 模式依赖受控数据库和代理语义，不适合不可控外部供应商。
- TCC 仍要求 Try 真实预留资源。
- Saga 仍然是补偿语义，不是强原子提交。
- 在国际金融架构表达中，不应把 Seata 当唯一主线。

## 本教程推荐位置

| 需求 | 推荐 |
| --- | --- |
| 长流程可靠执行 | Temporal |
| 人工审批和 BPMN 流程治理 | Camunda 作为对比和扩展 |
| 理解 AT/TCC/Saga 框架思想 | Seata 作为对比 |
| 本地事实和消息发布一致 | Outbox |
| 业务资源预留 | TCC-like 设计 |
| 资金事实和账本一致 | 状态机、幂等、账本、对账 |

## 评审底线

- 不接受“用了 Temporal 就不用状态机”。
- 不接受“用了 Camunda 就代表资金一致”。
- 不接受“用了 Seata 就能覆盖外部供应商不可控问题”。
- 不接受“框架成功就代表账平”。
- 不接受任何框架绕过领域服务、幂等、账本和对账。
````

- [ ] **Step 3: Verify framework anchors**

Run:

```bash
rg -n "Temporal|Camunda|Seata|durable execution|BPMN|AT|TCC|Saga|Outbox|账本|对账|国际" financial-consistency/05-patterns/07-framework-comparison.md
```

Expected: output includes all framework names and boundary terms.

- [ ] **Step 4: Commit**

Run:

```bash
git add financial-consistency/05-patterns/07-framework-comparison.md
git commit -m "docs: compare consistency orchestration frameworks"
```

Expected: commit succeeds and includes only `07-framework-comparison.md`.

## Task 9: Create Pattern Composition Document

**Files:**
- Create: `financial-consistency/05-patterns/08-pattern-composition.md`

- [ ] **Step 1: Add composition content**

Use `apply_patch` to create `financial-consistency/05-patterns/08-pattern-composition.md`:

````markdown
# 08 模式组合

## 目标

真实系统通常不是单模式。一个金融级流程会同时使用状态机、幂等、Outbox、Saga、TCC-like 资源预留、Temporal、事务消息或 CDC、账本、对账和人工修复。

## 内部转账

```text
状态机 + 幂等 + 账本 + Outbox + 对账
```

关键事实：

- 账户余额。
- 冻结金额。
- 流水。
- 会计分录。
- 转账状态。

不能做：

- 用 Saga 随意补偿账户扣减。
- 只靠消息最终一致性更新账本。
- 没有借贷平衡检查。

## 充值提现

```text
状态机 + 渠道幂等 + 查询/回调 + Outbox + 对账 + 人工处理
```

关键事实：

- 渠道请求号。
- 渠道回调。
- 主动查询结果。
- 支付或提现状态。
- 渠道账单。

不能做：

- 把渠道超时当失败。
- 重复发起无关联扣款或退款。
- 只看本地订单不看渠道账单。

## 电商下单

```text
库存预留/TCC-like + Saga + Outbox + 支付退款状态机 + 对账
```

关键事实：

- 订单。
- 库存预留。
- 支付。
- 退款。
- 发货或取消。

不能做：

- 支付成功后直接删除订单。
- 库存预留失败后继续扣款。
- 消息重复导致重复确认库存。

## 旅行组合预订

```text
Temporal Saga + 状态机 + Outbox + 付款策略 + 供应商查询 + 退款 + 对账 + 人工处理
```

关键事实：

- 报价快照。
- 机票出票。
- 酒店确认。
- 租车确认。
- 保险生效。
- 支付授权、capture、void、refund。
- 罚金、补差和账本。

不能做：

- 附加项失败取消核心行程。
- 供应商未知直接失败。
- 已出票或已生效动作被本地字段回滚。
- workflow history 替代供应商、支付、退款和账本事实。

## 组合原则

- 状态机定义合法业务推进。
- 幂等保护重复命令和重复消息。
- Outbox 保护本地事实和事件发布。
- Saga 或 Temporal 编排长流程。
- TCC-like 模型只用于可预留资源。
- 事务消息或 CDC 是事件传播选项，不是业务一致性本身。
- 对账发现事实分叉。
- 人工修复处理不可逆、未知和高风险差错。

## 验证方法

- 对每个组合场景列出事实来源。
- 对每个事实来源列出唯一约束和幂等键。
- 对每个跨服务事件验证 Outbox 或等价机制。
- 对每个外部系统结果验证查询、回调和对账路径。
- 对每个终态验证是否能解释资金、供应商和账本事实。
````

- [ ] **Step 2: Verify composition anchors**

Run:

```bash
rg -n "内部转账|充值提现|电商下单|旅行组合预订|状态机|幂等|Outbox|Saga|Temporal|TCC-like|对账|人工处理" financial-consistency/05-patterns/08-pattern-composition.md
```

Expected: output includes all mapped phases and combined patterns.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/05-patterns/08-pattern-composition.md
git commit -m "docs: define consistency pattern composition"
```

Expected: commit succeeds and includes only `08-pattern-composition.md`.

## Task 10: Create Verification Document

**Files:**
- Create: `financial-consistency/05-patterns/09-verification.md`

- [ ] **Step 1: Add verification content**

Use `apply_patch` to create `financial-consistency/05-patterns/09-verification.md`:

````markdown
# 09 验证方法

## 目标

验证方法要证明模式在异常路径下仍然保护一致性。金融级设计不能只验证正常路径，必须验证超时、重复、乱序、宕机、回调延迟、人工修复和对账差错。

## 按模式验证

| 模式 | 必须验证 |
| --- | --- |
| Outbox | 本地事务提交后 publisher 崩溃，恢复后事件补发且外部动作不重复 |
| Saga | 任意步骤失败后，已成功步骤进入合法补偿或人工处理 |
| TCC | Try / Confirm / Cancel 幂等、空回滚、悬挂、防重复确认 |
| Temporal | worker 重启、Activity 重试、timer 恢复、人工等待恢复，业务事实不重复 |
| 事务消息 | 半消息、提交、回查、重复投递和消费者幂等 |
| CDC | 重复捕获、乱序投影、schema 变化和下游幂等 |
| 状态机 | 非法状态转换被拒绝 |
| 对账 | 本地事实、外部事实、资金事实和账本事实可互相解释 |

## 不变量检查

- 同一业务幂等键最多产生一个业务效果。
- `SUPPLIER_UNKNOWN`、`PAYMENT_UNKNOWN`、`REFUND_UNKNOWN` 不能直接当失败。
- 已 capture 的资金不能 void。
- Confirm 和 Cancel 不能同时成功。
- 消息重复投递不能重复扣款、重复退款、重复出票或重复记账。
- 补偿不能删除历史事实。
- 对账服务不能直接修改领域事实。

## 属性测试

随机生成：

- 命令重复。
- 消息重复。
- 回调乱序。
- 外部请求超时。
- 本地事务提交后进程宕机。
- workflow worker 重启。
- TCC Cancel 先于 Try。
- CDC 事件重复和乱序。

检查：

- 状态机终态合法。
- 资金金额可解释。
- 账本分录可解释。
- 外部事实和本地事实冲突时进入对账或人工处理。

## 故障注入

- Outbox publisher 崩溃。
- broker 暂停。
- 消费者处理一半宕机。
- payment activity 超时后重试。
- refund request 已提交但结果未知。
- supplier request 超时后晚到成功回调。
- TCC Confirm 和 Cancel 并发。
- CDC 下游投影落后或重复。

## 历史回放

把真实或构造的历史事件按不同顺序重放，检查：

- 每个状态转换都有前置事实。
- 每个资金动作都有原始请求和幂等键。
- 每个退款都有原支付和账本分录。
- 每个人工修复都有审批和证据。
- 每个对账差错都有分类、owner、修复动作和复核结果。

## 对账验证

构造差异：

- 本地显示成功但供应商无单。
- 供应商成功但本地未推进。
- 支付成功但订单失败未退款。
- 退款成功但账本无分录。
- Outbox 事件缺失。
- CDC 投影漏数据。
- 人工修复无审计。

每个差异必须稳定分类，路由到 owner，执行修复命令或人工工单，修复后重新对账。

## 面试表达

验证一致性模式的关键不是证明正常流程能跑通，而是证明异常历史不会产生不可解释事实。模式只有能通过不变量、属性测试、故障注入、历史回放和对账验证，才适合进入金融级主线。
````

- [ ] **Step 2: Verify verification anchors**

Run:

```bash
rg -n "Outbox|Saga|TCC|Temporal|事务消息|CDC|状态机|对账|不变量|属性测试|故障注入|历史回放|SUPPLIER_UNKNOWN|PAYMENT_UNKNOWN|REFUND_UNKNOWN" financial-consistency/05-patterns/09-verification.md
```

Expected: output includes all pattern and verification method anchors.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/05-patterns/09-verification.md
git commit -m "docs: define consistency pattern verification"
```

Expected: commit succeeds and includes only `09-verification.md`.

## Task 11: Create Interview Synthesis

**Files:**
- Create: `financial-consistency/05-patterns/10-interview-synthesis.md`

- [ ] **Step 1: Add interview synthesis content**

Use `apply_patch` to create `financial-consistency/05-patterns/10-interview-synthesis.md`:

````markdown
# 10 面试与架构评审表达

## 一句话回答

金融级一致性不是选一个万能框架，而是按问题组合模式：状态机和幂等保护业务状态，Outbox 保护本地事实和事件发布，Saga 或 Temporal 编排长流程，TCC 处理可预留资源，事务消息或 CDC 传播事实，对账和人工修复收敛外部差错。

## 标准回答结构

1. 先说明要保护哪些事实：本地订单、资金、供应商、退款、账本、人工审批。
2. 再说明哪些事实在本地事务内，哪些来自外部系统。
3. 再选择模式：Outbox、Saga、TCC、Temporal、事务消息、CDC 或组合。
4. 再说明每个模式不能解决什么。
5. 最后说明如何验证：不变量、属性测试、故障注入、历史回放和对账。

## 高频问题

### Outbox 和事务消息有什么区别？

Outbox 是应用把业务事实和待发布事件写入同一个本地事务，再异步投递。事务消息依赖消息中间件的半消息、提交、回查等能力。二者都解决本地事务和消息发送一致性，但都不能证明消费者业务成功，也不能替代消费者幂等和对账。

### Saga 和 TCC 有什么区别？

Saga 是长流程补偿模式，每一步提交本地事实，失败后执行业务补偿。TCC 是资源预留模式，Try 真实预留资源，Confirm 确认资源，Cancel 释放资源。没有真实 Try 预留的业务不能叫 TCC。

### 为什么 Saga 不是回滚？

因为很多业务动作已经成为外部事实，例如支付扣款、机票出票、酒店确认、保险生效。补偿只能追加退款、取消、罚金、补差、替代供应商或人工处理事实，不能删除历史。

### Temporal 能不能保证分布式事务？

不能。Temporal 能提供可靠 workflow、timer、retry 和恢复执行，适合承接 Saga 编排。它不替代领域事实、Activity 幂等、Outbox、账本、支付退款状态机和对账。

### 为什么用了 Kafka 还需要 Outbox？

Kafka 只能投递消息，不能保证业务数据库提交和消息发送一定一致。Outbox 把业务事实和待发布事件放进同一本地事务，解决本地提交后消息丢失的问题。

### 为什么用了 Temporal 还需要状态机和对账？

Temporal 管理 workflow 执行历史，但业务状态必须由领域状态机保护。供应商、支付、退款和账本可能与本地流程分叉，必须通过查询、回调、账单、对账和人工修复收敛。

### CDC 和领域事件有什么区别？

CDC 捕获数据库变化，领域事件表达业务事实。数据库字段变化不一定等于业务事件。CDC 适合数据同步、读模型和审计，但不能替代业务语义、补偿规则和消费者幂等。

### Seata、Camunda、Temporal 怎么选？

Temporal 适合长流程可靠执行和 Saga 编排。Camunda 适合 BPMN、人工任务、审批和业务流程治理。Seata 适合理解 AT、TCC、Saga 等分布式事务框架思想。金融级主线仍然要靠事实建模、状态机、幂等、账本、Outbox、对账和人工修复。

### 金融系统里最不能省的模式是什么？

不能省的是状态机、幂等、账本和对账。Outbox、Saga、TCC、Temporal、事务消息、CDC 都是围绕这些基础能力工作的工具。如果基础事实不可解释，任何框架都会放大错误。

## 评审底线

- 不接受“一个框架解决所有一致性问题”。
- 不接受“消息发出去就代表业务成功”。
- 不接受“workflow 成功就代表账平”。
- 不接受“补偿就是删除之前的数据”。
- 不接受“对账是报表系统的事情”。
- 不接受“供应商超时就是失败”。
- 不接受“已 capture 资金可以 void”。
````

- [ ] **Step 2: Verify interview anchors**

Run:

```bash
rg -n "Outbox 和事务消息|Saga 和 TCC|Saga 不是回滚|Temporal 能不能保证分布式事务|用了 Kafka 还需要 Outbox|用了 Temporal 还需要状态机和对账|CDC 和领域事件|Seata、Camunda、Temporal|金融系统里最不能省" financial-consistency/05-patterns/10-interview-synthesis.md
```

Expected: output includes all interview questions.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/05-patterns/10-interview-synthesis.md
git commit -m "docs: add consistency patterns interview synthesis"
```

Expected: commit succeeds and includes only `10-interview-synthesis.md`.

## Task 12: Update Root README

**Files:**
- Modify: `financial-consistency/README.md`

- [ ] **Step 1: Add design spec link**

In `financial-consistency/README.md`, add this line to the formal design document list after the travel booking design link:

```markdown
- [2026-05-02-financial-consistency-patterns-design.md](../docs/superpowers/specs/2026-05-02-financial-consistency-patterns-design.md)
```

- [ ] **Step 2: Link phase 05 route**

Change:

```markdown
- 05-patterns
  Outbox、TCC、Saga、Temporal、Seata、Camunda、本地消息表、事务消息、CDC、状态机和幂等模式。
```

to:

```markdown
- [05-patterns](./05-patterns/README.md)
  Outbox、TCC、Saga、Temporal、Seata、Camunda、本地消息表、事务消息、CDC、状态机和幂等模式。
```

- [ ] **Step 3: Verify root README links**

Run:

```bash
rg -n "2026-05-02-financial-consistency-patterns-design.md|\./05-patterns/README.md" financial-consistency/README.md
```

Expected: output includes both links.

- [ ] **Step 4: Commit**

Run:

```bash
git add financial-consistency/README.md
git commit -m "docs: link consistency patterns phase"
```

Expected: commit succeeds and includes only `financial-consistency/README.md`.

## Task 13: Final Documentation Verification

**Files:**
- Verify: `financial-consistency/05-patterns/**`
- Verify: `financial-consistency/README.md`

- [ ] **Step 1: Verify all phase files exist**

Run:

```bash
find financial-consistency/05-patterns -maxdepth 1 -type f | sort
```

Expected output:

```text
financial-consistency/05-patterns/01-decision-map.md
financial-consistency/05-patterns/02-outbox-local-message-table.md
financial-consistency/05-patterns/03-saga.md
financial-consistency/05-patterns/04-tcc.md
financial-consistency/05-patterns/05-temporal.md
financial-consistency/05-patterns/06-transactional-message-cdc.md
financial-consistency/05-patterns/07-framework-comparison.md
financial-consistency/05-patterns/08-pattern-composition.md
financial-consistency/05-patterns/09-verification.md
financial-consistency/05-patterns/10-interview-synthesis.md
financial-consistency/05-patterns/README.md
```

- [ ] **Step 2: Verify README child links**

Run:

```bash
rg -n "\./01-decision-map.md|\./02-outbox-local-message-table.md|\./03-saga.md|\./04-tcc.md|\./05-temporal.md|\./06-transactional-message-cdc.md|\./07-framework-comparison.md|\./08-pattern-composition.md|\./09-verification.md|\./10-interview-synthesis.md" financial-consistency/05-patterns/README.md
```

Expected: output includes all 10 child document links.

- [ ] **Step 3: Verify main pattern anchors**

Run:

```bash
rg -n "Outbox|本地消息表|Saga|TCC|Temporal|事务消息|CDC|状态机|幂等|Seata|Camunda|对账|人工修复|补偿|broker offset|workflow history" financial-consistency/05-patterns
```

Expected: output includes the core terms across the phase docs.

- [ ] **Step 4: Verify scenario mappings**

Run:

```bash
rg -n "内部转账|充值提现|支付回调|电商下单|旅行组合预订|对账和人工修复" financial-consistency/05-patterns
```

Expected: output includes mappings back to previous phases.

- [ ] **Step 5: Verify framework comparison**

Run:

```bash
rg -n "Temporal|Camunda|Seata|durable execution|BPMN|AT|TCC|Saga|不是.*事实|不能.*账本|不能.*对账" financial-consistency/05-patterns/07-framework-comparison.md
```

Expected: output includes framework names, positioning, and boundary warnings.

- [ ] **Step 6: Verify root README link**

Run:

```bash
rg -n "2026-05-02-financial-consistency-patterns-design.md|\./05-patterns/README.md" financial-consistency/README.md
```

Expected: output includes both root README links.

- [ ] **Step 7: Verify previous phases were not changed in this phase**

Run:

```bash
git diff --name-only main..HEAD -- financial-consistency/01-transfer financial-consistency/02-payment-recharge-withdraw financial-consistency/03-order-payment-inventory financial-consistency/04-travel-booking-saga
```

Expected: no output.

- [ ] **Step 8: Scan for incomplete-document markers**

Run:

```bash
rg -n "TO[D]O|TB[D]|待[定]|占[位]|以[后]补|未[决]|大[概]|随[便]" financial-consistency/05-patterns financial-consistency/README.md
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
