# MySQL 提交、复制与 Router 文档补充 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用两个紧凑的文档提交，准确区分事务提交、数据可见、日志持久化、副本应用、多数派可用性与 Router 路由边界。

**Architecture:** 纯 Markdown 改动。先在第 07 章补一张提交边界表，再在第 09 章修正半同步与 Group Replication 的过强表述，并把 MySQL Router 8.4 作为 InnoDB Cluster 的连接路由方案加入现有读写分离小节。

**Tech Stack:** Markdown（简体中文）、MySQL/InnoDB、MySQL Group Replication、MySQL Router 8.4。

**Spec:** `docs/superpowers/specs/2026-07-20-mysql-commit-replication-router-doc-design.md`

## Global Constraints

- 只修改 `mysql-handson/07-logs-and-crashsafe/README.md` 与 `mysql-handson/09-replication-and-ha/README.md`。
- 不新增实验、配置教程或完整部署步骤，不重写章节结构。
- 不把相同内容复制到 `mysql-handson/12-interview-cheatsheet/README.md`。
- 半同步 ACK 只表示副本 receiver 已接收并持久化日志，不表示 SQL/applier 已应用。
- Group Replication 的多数派保证组内决策与事务全序，不表示所有 Secondary 已追平。
- MySQL Router 8.4 的经典协议端口写作 `6446`（Primary 读写）、`6447`（Secondary 只读）、`6450`（自动读写分流）。
- `wait_for_my_writes` 的读己之写边界限定为同一数据库客户端 session；跨 session 强一致读走 Primary 或显式使用 GTID 等待屏障。
- 仓库没有统一 Markdown/link lint 命令；每个任务使用精确文本断言、人工 diff 审阅与 `git diff --check` 验证。

---

### Task 1: 补齐提交、可见性与数据页落盘边界

**Files:**
- Modify: `mysql-handson/07-logs-and-crashsafe/README.md:373-384`

**Interfaces:**
- Consumes: §3.6 现有两阶段提交时序与 Crash Recovery 决策表。
- Produces: 正文锚点「COMMIT、可见性与数据页落盘不是一件事」，供读者把 Buffer Pool、MVCC、redo 与 page cleaner 放回各自职责。

- [ ] **Step 1: 确认新小节尚不存在**

Run:

```bash
rg -n '^#### COMMIT、可见性与数据页落盘不是一件事$' mysql-handson/07-logs-and-crashsafe/README.md
```

Expected: exit code `1`，无输出。

- [ ] **Step 2: 在 §3.6 的 Crash Recovery 决策表后插入边界表**

在「从库按 binlog 回放也始终与主库一致。」之后、`### 3.7 组提交 Group Commit` 之前插入：

```markdown
#### COMMIT、可见性与数据页落盘不是一件事

一次 DML 会先修改 Buffer Pool 中的数据页并产生 undo/redo；`COMMIT` 确认的是事务状态与日志持久化边界，不要求立刻把整张脏页写回表空间。

| 问题 | 由什么决定 | 正确边界 |
|---|---|---|
| 最新行版本在哪里 | Buffer Pool 中的数据页 | 写入先发生在内存页；该页此时通常是脏页 |
| 其他事务能否读到 | 事务是否提交、隔离级别、MVCC ReadView | 未提交版本通常不可见（`READ UNCOMMITTED` 除外）；已提交也不代表旧 ReadView 会改看新版本 |
| 提交后 crash 能否恢复 | redo log 的提交 LSN 与刷盘策略 | redo 先于数据页落盘，重启时可重放已提交修改；持久性强度仍取决于 `innodb_flush_log_at_trx_commit` 等配置 |
| 数据页何时写回表空间 | page cleaner、checkpoint 与脏页淘汰 | `COMMIT` 成功不等于数据页已经落盘；脏页可以稍后异步写回 |

一句话收口：**可见性看事务/MVCC，崩溃持久性看 redo，数据页落盘看 checkpoint/page cleaner。**
```

- [ ] **Step 3: 验证四个职责边界都已出现**

Run:

```bash
rg -n '^#### COMMIT、可见性与数据页落盘不是一件事$|Buffer Pool 中的数据页|MVCC ReadView|提交 LSN|checkpoint/page cleaner' mysql-handson/07-logs-and-crashsafe/README.md
```

Expected: 命中新标题、表格的四个机制和收口句；新标题只出现一次。

- [ ] **Step 4: 审阅格式与范围**

Run:

```bash
git diff --check
git diff -- mysql-handson/07-logs-and-crashsafe/README.md
```

Expected: `git diff --check` 无输出；diff 只在 §3.6 与 §3.7 之间增加上述小节，没有改写现有 WAL、LSN 或刷盘策略。

- [ ] **Step 5: Commit**

```bash
git add mysql-handson/07-logs-and-crashsafe/README.md && git commit -m "docs(mysql): clarify commit visibility and page flush"
```

---

### Task 2: 修正复制保证并补 MySQL Router 8.4

**Files:**
- Modify: `mysql-handson/09-replication-and-ha/README.md:140-287`
- Modify: `mysql-handson/09-replication-and-ha/README.md:389-402`

**Interfaces:**
- Consumes: §3.4 的复制模式对比、§3.5 的 lossless 时序、§3.6 的 MGR 简述、§3.7 的读写分离方案与 §3.9 的读己之写策略。
- Produces: 明确的 `ACK != apply`、三节点 `2/3` 多数派、Router 职责/端口/HA 部署与 session 级 `wait_for_my_writes` 边界。

- [ ] **Step 1: 锁定现有过强表述**

Run:

```bash
rg -n '强（单主单写模式）|如果读请求路由到的就是这个从库，则读到写|半同步保证 \| 近强' mysql-handson/09-replication-and-ha/README.md
```

Expected: 三处都命中，分别位于 §3.4 与 §3.9。

- [ ] **Step 2: 替换 §3.4 的复制模式对比表**

把 §3.4 现有表格替换为：

```markdown
| 维度 | 异步复制 | 半同步复制 | MGR |
|---|---|---|---|
| **数据持久性（Primary crash）** | 事务可能尚未到达副本 | lossless 模式下，返回前至少 1 个副本已持久化 relay log；不代表已 apply | 多数派维持组内决策与事务全序，可容忍少数成员故障 |
| **写延迟** | 最低（不等 ACK） | +1 RTT（等 ACK，通常 1-5ms） | +1 RTT + 组通信/认证开销 |
| **读一致性** | 弱（副本可能落后） | 弱（`ACK != apply`，副本仍可能读旧值） | 默认最终一致；Secondary 可能有 applier backlog |
| **故障切换** | 手动或 MHA | 手动或 MHA | **自动**（原生选主）|
| **部署复杂度** | 低 | 低 | 高（至少 3 节点，需要 group_replication 插件）|
| **适用场景** | 允许复制延迟和一定 RPO 的读扩展 | 希望缩小 Primary 故障丢数窗口 | 需要自动 HA 与组内多数派决策的核心业务 |
| **MySQL 版本** | 所有版本 | 5.5+ 插件，5.7+ 内置 lossless | 5.7.17+ |
```

- [ ] **Step 3: 在 §3.5 明确半同步 ACK 的边界**

在 lossless 时序后的「关键差异」段落之后插入：

```markdown
> **ACK 边界**：副本的 receiver 已接收事务并把它持久化到 relay log，才向 Primary ACK；这时 SQL/applier 可能还没有执行该事务。因此 **`ACK != apply != 副本已经可读`**。半同步主要缩小故障切换时的 RPO，不提供读己之写保证。
```

- [ ] **Step 4: 收紧 §3.6 的 MGR 多数派语义并给出三节点基线**

把 §3.6 第一段替换为：

```markdown
**MGR 的一致性协议**：基于 **Paxos 变种（MySQL 内部叫 XCom）**，组成员对事务建立全序并做冲突认证；组要继续作出决策，必须保持多数派（`(N/2)+1`）。事务进入组内有序队列，不等于每个 Secondary 的 applier 都已执行完成——默认一致性仍可能读到短暂旧值。
```

把「MGR 最小部署」一段替换为：

```markdown
**三节点生产基线**：采用 Single-Primary，3 个成员以 `2/3` 形成多数派，可容忍 1 个成员故障。不要把「全部 Secondary 已 apply」设成默认可用条件，否则一个慢节点或故障节点就会拖住整组；确实需要更强读一致性时，再通过 `group_replication_consistency` 选择等待点并接受额外延迟。

推荐用 MySQL Shell 的 `dba.createCluster()` 配置 InnoDB Cluster。
```

- [ ] **Step 5: 把 MySQL Router 加入 §3.7 的读写分离方案**

先把标题和开场句改为：

```markdown
### 3.7 读写分离四种方案对比

读写分离核心：写 → Primary，读 → Secondary。四种实现方式各有取舍：
```

在 Connector/J 方案之后、总结表之前插入：

```markdown
#### 方案 D：MySQL Router（InnoDB Cluster）

MySQL Router 是轻量连接路由层：**不选主、不复制数据，也不执行 binlog**。Primary 选举与成员状态由 Group Replication/InnoDB Cluster 管理；Router 读取 Cluster Metadata 与实时拓扑，为新连接选择合适的在线节点。

MySQL Router 8.4 bootstrap 后，经典协议常用端口是：

| 端口 | 路由目标 | 应用方式 |
|---|---|---|
| `6446` | 当前 Primary | 明确要求读写或强一致读 |
| `6447` | Secondary | 明确接受副本延迟的只读流量 |
| `6450` | Primary + Secondary | Router 按事务/语句访问模式自动读写分流 |

`6450` 默认启用 `wait_for_my_writes=1`：同一数据库客户端 session 先写后读时，Router 会等待目标 Secondary 应用该 session 的最后一次写入；超时后回退到读写节点。它不跨 session 传递因果关系——重连、连接池换了物理连接或另一服务发起读取时，仍应走 `6446`，或把 GTID 传给读取方并执行 `WAIT_FOR_EXECUTED_GTID_SET()`。

生产环境至少部署两个 Router 实例，并让应用使用多个端点或前置负载均衡，避免 Router 自身成为接入层单点。Router 实例之间不选主，都是根据同一份 Cluster Metadata 独立路由。

参考：[MySQL Router 8.4 Cluster Metadata and State](https://dev.mysql.com/doc/mysql-router/8.4/en/mysql-router-general-metadata.html)、[Read/Write Splitting Configuration](https://dev.mysql.com/doc/mysql-router/8.4/en/router-read-write-splitting-configuration.html)。
```

把总结标题和表格替换为：

```markdown
#### 四方案对比总结

| 维度 | 应用层（ShardingSphere 等）| ProxySQL | JDBC Replication Driver | MySQL Router |
|---|---|---|---|---|
| 应用侵入 | 高 | **无** | 低 | **无** |
| 运维复杂度 | 低 | 中（需额外 HA）| 低 | 中（需多实例）|
| 连接数管理 | 差（每实例独立池）| **好**（统一代理池）| 中 | 中 |
| SQL 粒度控制 | 高 | 高 | 低 | 8.4 的 `6450` 支持自动分流 |
| 适用规模 | 中小 | **中大型生产** | 小型 / 原型 | InnoDB Cluster |
```

- [ ] **Step 6: 修正 §3.9 把半同步等同于可读的策略**

把策略 3 的标题和正文替换为：

```markdown
#### 策略 3：半同步只能缩小 RPO，不能代替读屏障

lossless 半同步只保证写操作返回前至少一个副本已持久化 relay log，SQL/applier 仍可能落后。即使读请求恰好路由到 ACK 的副本，也不能据此断言新版本已经可读。读己之写仍使用策略 1、策略 2，或 §3.7 Router `6450` 的同 session `wait_for_my_writes`。
```

把对比表中的半同步一行替换为：

```markdown
| 半同步 ACK | 不保证（`ACK != apply`）| 不增加 | 低（但必须另配读屏障）|
```

- [ ] **Step 7: 验证所有保证与 Router 边界**

Run:

```bash
rg -n 'ACK != apply|2/3|6446|6447|6450|wait_for_my_writes|Router 自身成为接入层单点|WAIT_FOR_EXECUTED_GTID_SET' mysql-handson/09-replication-and-ha/README.md
! rg -n '强（单主单写模式）|如果读请求路由到的就是这个从库，则读到写|半同步保证 \| 近强' mysql-handson/09-replication-and-ha/README.md
```

Expected: 第一条命令覆盖 ACK、多数派、三个端口、session 等待、Router HA 与 GTID 屏障；第二条命令无输出并返回成功。

- [ ] **Step 8: 审阅格式、链接与范围**

Run:

```bash
git diff --check
git diff -- mysql-handson/09-replication-and-ha/README.md
```

Expected: `git diff --check` 无输出；diff 只修正 §3.4-§3.7 和 §3.9，不新增部署教程，不改场景实验。

- [ ] **Step 9: Commit**

```bash
git add mysql-handson/09-replication-and-ha/README.md && git commit -m "docs(mysql): clarify replication guarantees and Router routing"
```

---

### Task 3: 全局范围与回归校验

**Files:**
- Verify: `mysql-handson/07-logs-and-crashsafe/README.md`
- Verify: `mysql-handson/09-replication-and-ha/README.md`
- Verify unchanged: `mysql-handson/12-interview-cheatsheet/README.md`

**Interfaces:**
- Consumes: Task 1 与 Task 2 的两个文档提交。
- Produces: 干净工作树，以及只改两章、没有遗漏设计要求的最终证据。

- [ ] **Step 1: 检查最近两个实现提交的文件范围**

Run:

```bash
git diff --name-only HEAD~2..HEAD
```

Expected: 只输出：

```text
mysql-handson/07-logs-and-crashsafe/README.md
mysql-handson/09-replication-and-ha/README.md
```

- [ ] **Step 2: 确认面试速查表没有被同步改写**

Run:

```bash
git diff --quiet HEAD~2..HEAD -- mysql-handson/12-interview-cheatsheet/README.md
```

Expected: exit code `0`，无输出。

- [ ] **Step 3: 运行最终文本断言与空白校验**

Run:

```bash
rg -n '^#### COMMIT、可见性与数据页落盘不是一件事$|可见性看事务/MVCC' mysql-handson/07-logs-and-crashsafe/README.md
rg -n 'ACK != apply != 副本已经可读|2/3|`6446`|`6447`|`6450`|同一数据库客户端 session' mysql-handson/09-replication-and-ha/README.md
git diff HEAD~2..HEAD --check
```

Expected: 两个章节的所有关键短语都命中；`git diff --check` 无输出。

- [ ] **Step 4: 确认工作树干净**

Run:

```bash
git status --short
```

Expected: 无输出；无需额外提交。
