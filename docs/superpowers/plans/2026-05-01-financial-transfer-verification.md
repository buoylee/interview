# Financial Transfer Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first `financial-consistency/01-transfer/` tutorial module, centered on distributed transfer correctness, invariants, state machines, failure analysis, and verification.

**Architecture:** This phase creates documentation and executable learning scaffolding before Java implementation. The module starts from A-to-B transfer, but treats it as a distributed financial workflow with explicit services, ledger entries, outbox events, idempotency, compensation, verification, and reconciliation.

**Tech Stack:** Markdown documentation, Java/Spring Boot target architecture, Kafka/Outbox target eventing, Temporal target workflow orchestration, TLA+/PlusCal target modeling, Testcontainers target integration testing.

---

## File Structure

- Create: `financial-consistency/01-transfer/README.md`
  - Module entry point, learning goals, reading order, and transfer scenario overview.
- Create: `financial-consistency/01-transfer/01-invariants.md`
  - Correctness invariants for transfer, ledger, idempotency, state transitions, outbox, and reconciliation.
- Create: `financial-consistency/01-transfer/02-state-machine.md`
  - Transfer state machine, allowed transitions, terminal states, and illegal transitions.
- Create: `financial-consistency/01-transfer/03-service-boundaries.md`
  - Services, ownership boundaries, local transaction boundaries, APIs, and data ownership.
- Create: `financial-consistency/01-transfer/04-event-flow.md`
  - Command/event flow from transfer request through debit, credit, ledger, outbox, and reconciliation.
- Create: `financial-consistency/01-transfer/05-failure-matrix.md`
  - Failure cases and expected recovery behavior.
- Create: `financial-consistency/01-transfer/06-verification-plan.md`
  - Model verification, property testing, integration testing, fault injection, history checking, and reconciliation checks.
- Create: `financial-consistency/01-transfer/07-interview-synthesis.md`
  - Interview and architecture-review synthesis for the transfer module.
- Modify: `financial-consistency/README.md`
  - Link the new `01-transfer/` module.
- Modify: `financial-consistency/references.md`
  - Add verification and transfer-specific references if missing.

---

### Task 1: Create Transfer Module Entry Point

**Files:**
- Create: `financial-consistency/01-transfer/README.md`
- Modify: `financial-consistency/README.md`

- [ ] **Step 1: Create the module directory**

Run:

```bash
mkdir -p financial-consistency/01-transfer
```

Expected: `financial-consistency/01-transfer/` exists.

- [ ] **Step 2: Create `financial-consistency/01-transfer/README.md`**

Write this file with the following sections:

```markdown
# 01 分布式转账

## 目标

用 A 给 B 转账这个最小资金场景，学习真实金融系统中的分布式一致性、账务建模、幂等、状态机、Outbox、补偿、对账和验证方法。

转账场景不是单库事务 demo。它从第一天就按分布式服务边界分析：

- `transaction-orchestrator`
- `account-service`
- `ledger-service`
- `risk-service`
- `reconciliation-service`
- `message-broker`

## 学习顺序

1. [正确性不变量](./01-invariants.md)
2. [状态机](./02-state-machine.md)
3. [服务边界](./03-service-boundaries.md)
4. [事件流](./04-event-flow.md)
5. [失败矩阵](./05-failure-matrix.md)
6. [验证路线](./06-verification-plan.md)
7. [面试表达](./07-interview-synthesis.md)

## 核心问题

- 为什么不能只在一个数据库事务里扣 A、加 B？
- 为什么余额字段不能作为唯一事实来源？
- 为什么成功转账必须有借贷两边分录？
- 幂等键到底保护的是请求、消息还是业务结果？
- 扣款成功但入账失败时，系统如何恢复？
- 消息重复、乱序、延迟时，如何保证不重复扣款？
- 对账发现单边账后，如何定位和修复？
- 如何用不变量和故障注入验证系统正确性？
```

- [ ] **Step 3: Link the module from `financial-consistency/README.md`**

Add this bullet under the `01-transfer` stage:

```markdown
  入口：[01-transfer](./01-transfer/README.md)
```

- [ ] **Step 4: Verify links and headings**

Run:

```bash
rg -n "01-transfer|正确性不变量|状态机|验证路线" financial-consistency/README.md financial-consistency/01-transfer/README.md
```

Expected: output includes the new module link and all seven learning-order entries.

- [ ] **Step 5: Commit**

Run:

```bash
git add financial-consistency/README.md financial-consistency/01-transfer/README.md
git commit -m "docs: add transfer module entry"
```

Expected: commit succeeds.

---

### Task 2: Define Transfer Correctness Invariants

**Files:**
- Create: `financial-consistency/01-transfer/01-invariants.md`

- [ ] **Step 1: Create invariant document**

Write `financial-consistency/01-transfer/01-invariants.md` with these sections:

```markdown
# 01 正确性不变量

## 为什么先写不变量

金融系统的第一步不是选框架，也不是写接口，而是定义系统永远不能违反的事实。不变量用于指导表结构、状态机、事务边界、测试、故障注入和对账。

## 资金守恒

在不考虑手续费、汇率和外部清结算的第一阶段中：

```text
所有账户总余额 + 所有冻结金额 = 初始总金额
```

如果 A 给 B 转账 100：

- A 的可用余额减少 100，或 A 的冻结金额先增加 100 后扣减。
- B 的可用余额增加 100。
- 系统总金额不变。
- 不允许出现只扣 A 不加 B 且没有异常记录的终态。

## 借贷分录成对

成功转账必须至少产生两条分录：

- 付款方借记分录：`DEBIT`
- 收款方贷记分录：`CREDIT`

两条分录必须满足：

- `transfer_id` 相同。
- `amount` 相同。
- `currency` 相同。
- 借贷方向相反。
- 都处于 `POSTED` 或等价成功状态。

## 幂等

同一个 `idempotency_key` 对同一个业务动作只能产生一次业务效果。

必须防止：

- 重复扣款。
- 重复入账。
- 重复生成成功分录。
- 重复发布不可幂等业务事件。

允许：

- 重复返回同一个成功结果。
- 重复消费同一条消息。
- 重复执行幂等查询。

## 状态机合法性

交易状态只能沿明确路径推进：

```text
REQUESTED
-> RISK_CHECKED
-> DEBIT_RESERVED
-> DEBIT_POSTED
-> CREDIT_POSTED
-> SUCCEEDED
```

失败路径必须进入可解释状态：

```text
FAILED
COMPENSATING
COMPENSATED
MANUAL_REVIEW
```

终态不能非法回到处理中状态。

## Outbox 一致性

如果本地事务改变了核心业务状态，并且该状态需要通知其他服务，则同一个本地事务必须写入 outbox 事件。

```text
业务状态变更成功 => outbox 事件存在
outbox 事件存在 => 最终被发布或进入异常处理
```

## 对账可重建

账户余额必须能通过分录或流水重建：

```text
account.balance = initial_balance + posted_credits - posted_debits
```

如果重建结果和账户快照不一致，系统必须能定位到差异分录、交易和消息。
```

- [ ] **Step 2: Verify no vague invariant language**

Run:

```bash
rg -n "应[该]|大[概]|可[能]|TO[D]O|TB[D]|待[定]" financial-consistency/01-transfer/01-invariants.md
```

Expected: no output.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/01-transfer/01-invariants.md
git commit -m "docs: define transfer invariants"
```

Expected: commit succeeds.

---

### Task 3: Define Transfer State Machine

**Files:**
- Create: `financial-consistency/01-transfer/02-state-machine.md`

- [ ] **Step 1: Create state machine document**

Write `financial-consistency/01-transfer/02-state-machine.md` with these sections:

```markdown
# 02 状态机

## 主状态

| 状态 | 含义 | 是否终态 |
|---|---|---|
| `REQUESTED` | 接收到转账请求，幂等记录已创建 | 否 |
| `RISK_CHECKED` | 风控检查通过 | 否 |
| `DEBIT_RESERVED` | 付款方资金已冻结 | 否 |
| `DEBIT_POSTED` | 付款方借记分录已入账 | 否 |
| `CREDIT_POSTED` | 收款方贷记分录已入账 | 否 |
| `SUCCEEDED` | 转账完成 | 是 |
| `FAILED` | 转账失败，未产生需要补偿的资金影响 | 是 |
| `COMPENSATING` | 正在执行补偿 | 否 |
| `COMPENSATED` | 补偿完成 | 是 |
| `MANUAL_REVIEW` | 自动恢复失败，需要人工处理 | 是 |

## 正常路径

```text
REQUESTED
-> RISK_CHECKED
-> DEBIT_RESERVED
-> DEBIT_POSTED
-> CREDIT_POSTED
-> SUCCEEDED
```

## 失败路径

```text
REQUESTED -> FAILED
RISK_CHECKED -> FAILED
DEBIT_RESERVED -> COMPENSATING -> COMPENSATED
DEBIT_POSTED -> COMPENSATING -> COMPENSATED
DEBIT_POSTED -> CREDIT_POSTED -> SUCCEEDED
COMPENSATING -> MANUAL_REVIEW
```

## 非法跳转

- `SUCCEEDED -> FAILED`
- `FAILED -> SUCCEEDED`
- `COMPENSATED -> SUCCEEDED`
- `MANUAL_REVIEW -> SUCCEEDED`，除非通过人工修复流程产生新的修复交易。
- `REQUESTED -> CREDIT_POSTED`
- `DEBIT_RESERVED -> CREDIT_POSTED`

## 状态更新规则

- 状态更新必须带 `version` 或等价乐观锁。
- 重复消息只能重放当前状态允许的幂等结果。
- 迟到消息如果对应状态已经终结，必须被记录为 ignored 或 duplicate，不能推动状态倒退。
```

- [ ] **Step 2: Verify terminal state rules exist**

Run:

```bash
rg -n "SUCCEEDED|FAILED|COMPENSATED|MANUAL_REVIEW|非法跳转|version" financial-consistency/01-transfer/02-state-machine.md
```

Expected: output includes terminal states, illegal transitions, and version rule.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/01-transfer/02-state-machine.md
git commit -m "docs: define transfer state machine"
```

Expected: commit succeeds.

---

### Task 4: Define Service Boundaries

**Files:**
- Create: `financial-consistency/01-transfer/03-service-boundaries.md`

- [ ] **Step 1: Create service boundary document**

Write `financial-consistency/01-transfer/03-service-boundaries.md` with these sections:

```markdown
# 03 服务边界

## 服务列表

| 服务 | 拥有的数据 | 本地事务边界 | 不拥有的数据 |
|---|---|---|---|
| `transaction-orchestrator` | transfer 状态、workflow 进度、补偿记录 | 单个 transfer 状态推进 | 账户余额、会计分录 |
| `account-service` | account、balance、freeze 记录 | 单账户冻结、解冻、扣减、入账 | 全局交易流程 |
| `ledger-service` | ledger entry、journal、posting batch | 分录创建和过账 | 账户可用余额 |
| `risk-service` | 风控规则、限额检查结果 | 风控决策记录 | 资金状态 |
| `reconciliation-service` | 对账批次、差错记录、修复工单 | 对账结果和差错状态 | 原始资金事实 |
| `message-broker` | Kafka topic、consumer offset | 消息投递语义 | 业务状态 |

## transaction-orchestrator

职责：

- 接收转账命令。
- 创建幂等记录和 transfer 状态。
- 调用风控、账户、账本服务。
- 推进状态机。
- 触发补偿。
- 将无法自动恢复的交易转入 `MANUAL_REVIEW`。

不直接修改：

- 账户余额。
- 会计分录。

## account-service

职责：

- 冻结付款方资金。
- 扣减冻结金额。
- 给收款方入账。
- 保证单账户内余额更新的本地事务正确性。

本地事务必须同时更新：

- account balance snapshot。
- account movement 或 freeze record。
- outbox event，如果该变化需要异步通知。

## ledger-service

职责：

- 创建借方和贷方分录。
- 保证同一 transfer 的分录可追踪。
- 支持通过分录重建资金变化。

## 服务间原则

- 禁止跨服务共享数据库。
- 禁止跨服务直接改表。
- 跨服务调用必须带 `transaction_id`、`idempotency_key`、`trace_id`。
- 跨服务调用超时不能直接等价于失败，必须查询或等待状态收敛。
```

- [ ] **Step 2: Verify each service has ownership boundaries**

Run:

```bash
rg -n "拥有的数据|本地事务边界|不拥有的数据|禁止跨服务|idempotency_key" financial-consistency/01-transfer/03-service-boundaries.md
```

Expected: output includes the ownership table and cross-service rules.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/01-transfer/03-service-boundaries.md
git commit -m "docs: define transfer service boundaries"
```

Expected: commit succeeds.

---

### Task 5: Define Event Flow

**Files:**
- Create: `financial-consistency/01-transfer/04-event-flow.md`

- [ ] **Step 1: Create event flow document**

Write `financial-consistency/01-transfer/04-event-flow.md` with these sections:

```markdown
# 04 事件流

## 正常流程

```text
Client
-> transaction-orchestrator: CreateTransfer(command, idempotency_key)
-> risk-service: CheckTransferRisk
-> account-service: ReserveDebit
-> ledger-service: PostDebitEntry
-> account-service: CreditReceiver
-> ledger-service: PostCreditEntry
-> transaction-orchestrator: MarkSucceeded
-> Kafka: TransferSucceeded event
-> reconciliation-service: consume and index for reconciliation
```

## Outbox 规则

每个服务只在自己的本地事务内写业务表和 outbox 表：

```text
local business update + outbox insert = one local database transaction
```

发布器异步读取 outbox 并写 Kafka。Kafka 重复投递由消费者幂等处理。

## 事件命名

| 事件 | 生产者 | 消费者 | 语义 |
|---|---|---|---|
| `TransferRequested` | transaction-orchestrator | risk-service | 转账请求已创建 |
| `DebitReserved` | account-service | transaction-orchestrator | 付款资金已冻结 |
| `DebitPosted` | ledger-service | transaction-orchestrator | 借方分录已入账 |
| `CreditPosted` | ledger-service | transaction-orchestrator | 贷方分录已入账 |
| `TransferSucceeded` | transaction-orchestrator | reconciliation-service, notification-service | 转账完成 |
| `TransferCompensationRequired` | transaction-orchestrator | account-service, ledger-service | 需要补偿 |
| `TransferManualReviewRequired` | transaction-orchestrator | operations | 需要人工介入 |

## 消息处理原则

- 所有事件必须包含 `event_id`、`transaction_id`、`idempotency_key`、`occurred_at`、`producer`。
- 消费者必须记录已处理 `event_id`。
- 同一事件重复到达时，返回已处理结果。
- 事件迟到时，必须检查当前状态是否仍允许处理。
```

- [ ] **Step 2: Verify event coverage**

Run:

```bash
rg -n "TransferRequested|DebitReserved|DebitPosted|CreditPosted|TransferSucceeded|event_id|outbox" financial-consistency/01-transfer/04-event-flow.md
```

Expected: output includes normal events and required metadata.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/01-transfer/04-event-flow.md
git commit -m "docs: define transfer event flow"
```

Expected: commit succeeds.

---

### Task 6: Define Failure Matrix

**Files:**
- Create: `financial-consistency/01-transfer/05-failure-matrix.md`

- [ ] **Step 1: Create failure matrix document**

Write `financial-consistency/01-transfer/05-failure-matrix.md` with these sections:

```markdown
# 05 失败矩阵

## 失败场景

| 编号 | 失败点 | 可能结果 | 恢复策略 | 必须保持的不变量 |
|---|---|---|---|---|
| F01 | 请求重复提交 | 多次进入 orchestrator | 幂等键返回同一结果 | 同一幂等键只产生一次业务效果 |
| F02 | 风控服务超时 | 不知道风控是否通过 | 查询风控结果或重试 | 未通过风控不能扣款 |
| F03 | 冻结资金成功但响应超时 | orchestrator 以为失败 | 查询 account freeze 状态 | 不能重复冻结 |
| F04 | 借方分录成功但 orchestrator 宕机 | workflow 停在旧状态 | 恢复后按 transaction_id 查询 ledger | 借方分录不能重复 |
| F05 | 借方成功，贷方失败 | 单边资金影响 | 进入补偿或人工处理 | 不能静默丢失单边账 |
| F06 | Kafka 重复投递 | 消费者重复收到事件 | event_id 去重 | 不能重复扣款或入账 |
| F07 | Kafka 消息乱序 | 后置事件先到 | 状态机拒绝非法推进 | 状态不能倒退或跳跃 |
| F08 | Outbox 写入成功但发布器宕机 | 事件未发布 | 发布器重启继续扫描 | 状态变更对应事件最终发布或异常告警 |
| F09 | 补偿失败 | 资金状态悬挂 | 进入 `MANUAL_REVIEW` | 异常必须可见、可追踪 |
| F10 | 对账发现余额不一致 | 快照和分录不一致 | 生成差错记录和修复工单 | 账务差异不能被忽略 |

## 故障注入原则

- 每个失败点都要能被测试主动触发。
- 每个失败点都要绑定至少一个不变量。
- 每个恢复策略都要有可观测证据：状态、分录、outbox、日志、trace 或对账记录。
```

- [ ] **Step 2: Verify matrix coverage**

Run:

```bash
rg -n "F01|F02|F03|F04|F05|F06|F07|F08|F09|F10|MANUAL_REVIEW|不变量" financial-consistency/01-transfer/05-failure-matrix.md
```

Expected: output includes all ten failure rows and manual review fallback.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/01-transfer/05-failure-matrix.md
git commit -m "docs: define transfer failure matrix"
```

Expected: commit succeeds.

---

### Task 7: Define Verification Plan

**Files:**
- Create: `financial-consistency/01-transfer/06-verification-plan.md`

- [ ] **Step 1: Create verification plan document**

Write `financial-consistency/01-transfer/06-verification-plan.md` with these sections:

```markdown
# 06 验证路线

## 验证目标

验证目标不是证明系统没有 bug，而是用多层方法提前暴露事务设计和实现中的错误，并确保异常能被发现、定位、止损和修复。

## 层次 1：模型验证

建模对象：

- 转账状态机。
- 幂等键。
- 借方和贷方分录。
- Outbox 事件。
- 重试、超时、宕机和重复消息。

需要检查的不变量：

- 资金守恒。
- 同一幂等键只有一次业务效果。
- 成功状态必须存在借贷两边分录。
- 终态不能非法回退。

## 层次 2：属性测试

随机生成操作序列：

- 创建转账。
- 重复提交。
- 重试扣款。
- 重试入账。
- 重放消息。
- 触发补偿。
- 执行对账。

每轮执行后检查不变量。

## 层次 3：集成测试

使用真实中间件语义：

- 数据库事务。
- Kafka 至少一次投递。
- Redis 幂等缓存或锁辅助。
- Outbox 发布器。

## 层次 4：故障注入

必须覆盖：

- RPC 超时但对方成功。
- 消费成功但 ack 失败。
- Orchestrator 在任意状态宕机。
- Outbox 发布器宕机。
- Kafka 重复投递。
- DB 死锁或事务超时。

## 层次 5：历史检查

记录并发操作历史：

- request
- response
- event
- state transition
- ledger entry
- reconciliation result

检查历史是否违反资金守恒、幂等和状态机约束。

## 层次 6：对账验证

对账输入：

- transfer 表。
- account balance snapshot。
- ledger entries。
- outbox events。
- consumer processed events。

对账输出：

- 无差异。
- 单边账。
- 重复账。
- 状态悬挂。
- 分录缺失。
- 需要人工处理。
```

- [ ] **Step 2: Verify verification layers**

Run:

```bash
rg -n "模型验证|属性测试|集成测试|故障注入|历史检查|对账验证|资金守恒" financial-consistency/01-transfer/06-verification-plan.md
```

Expected: output includes all six verification layers.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/01-transfer/06-verification-plan.md
git commit -m "docs: define transfer verification plan"
```

Expected: commit succeeds.

---

### Task 8: Add Interview and Review Synthesis

**Files:**
- Create: `financial-consistency/01-transfer/07-interview-synthesis.md`

- [ ] **Step 1: Create synthesis document**

Write `financial-consistency/01-transfer/07-interview-synthesis.md` with these sections:

```markdown
# 07 面试与架构评审表达

## 一句话回答

金融级转账不能只靠一个余额字段或一个跨服务事务。我们需要账户、分录、幂等、状态机、Outbox、补偿、对账和验证体系共同保证资金正确性。

## 标准回答结构

1. 先定义资金不变量：钱不能多、不能少、不能重复扣。
2. 再定义服务边界：账户服务管余额，账本服务管分录，编排服务管流程。
3. 单服务内部使用本地事务。
4. 跨服务使用 Saga/TCC、Outbox 和消息最终一致性。
5. 所有写操作和消息消费都必须幂等。
6. 所有状态变化必须可追踪、可审计、可恢复。
7. 对账用于发现实现、消息和外部系统造成的差错。
8. 使用模型验证、属性测试和故障注入提前暴露事务问题。

## 常见追问

### 为什么不用一个分布式事务框架直接解决？

因为金融系统的很多动作不是数据库行更新，而是业务状态变化、外部系统调用、消息投递、不可逆动作和人工处理。框架可以帮助编排，但不能替代业务不变量、分录、幂等、补偿和对账。

### 扣款成功但入账失败怎么办？

系统不能静默结束。交易进入补偿或人工处理状态。通过分录、状态机、outbox 和对账记录定位单边账，并执行解冻、冲正、补入账或人工修复。

### 如何证明不会重复扣款？

不能只说“代码判断了”。需要幂等键、数据库唯一约束、消费者去重、状态机防重、属性测试、重复消息故障注入和对账验证共同证明。
```

- [ ] **Step 2: Verify synthesis covers core talking points**

Run:

```bash
rg -n "不变量|服务边界|本地事务|Saga|Outbox|幂等|对账|模型验证|故障注入" financial-consistency/01-transfer/07-interview-synthesis.md
```

Expected: output includes all core talking points.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-consistency/01-transfer/07-interview-synthesis.md
git commit -m "docs: add transfer interview synthesis"
```

Expected: commit succeeds.

---

### Task 9: Final Documentation Verification

**Files:**
- Verify: `financial-consistency/01-transfer/*.md`
- Verify: `financial-consistency/README.md`

- [ ] **Step 1: Run placeholder scan**

Run:

```bash
rg -n "TO[D]O|TB[D]|待[定]|占[位]|以[后]补|大[概]|随[便]" financial-consistency/01-transfer financial-consistency/README.md
```

Expected: no output.

- [ ] **Step 2: Verify all module files exist**

Run:

```bash
find financial-consistency/01-transfer -maxdepth 1 -type f | sort
```

Expected output:

```text
financial-consistency/01-transfer/01-invariants.md
financial-consistency/01-transfer/02-state-machine.md
financial-consistency/01-transfer/03-service-boundaries.md
financial-consistency/01-transfer/04-event-flow.md
financial-consistency/01-transfer/05-failure-matrix.md
financial-consistency/01-transfer/06-verification-plan.md
financial-consistency/01-transfer/07-interview-synthesis.md
financial-consistency/01-transfer/README.md
```

- [ ] **Step 3: Verify references from module README**

Run:

```bash
rg -n "\./01-invariants.md|\./02-state-machine.md|\./03-service-boundaries.md|\./04-event-flow.md|\./05-failure-matrix.md|\./06-verification-plan.md|\./07-interview-synthesis.md" financial-consistency/01-transfer/README.md
```

Expected: output includes seven module links.

- [ ] **Step 4: Run git diff check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 5: Commit final README/reference updates if any remain**

Run:

```bash
git status --short
```

Expected: no unstaged changes. If `financial-consistency/README.md` or `financial-consistency/references.md` remains modified, commit with:

```bash
git add financial-consistency/README.md financial-consistency/references.md
git commit -m "docs: finalize transfer module links"
```

Expected: commit succeeds or no commit is needed.
