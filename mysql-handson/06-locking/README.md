# 锁机制

## 1. 核心问题

锁是「多个事务并发访问同一数据时，保证正确性的协调机制」。本章解决三件事：
**(a)** 搞清楚 InnoDB 里到底有多少种锁、各自锁的是什么；
**(b)** 理解 RR 隔离级别下 Next-Key Lock 怎么防幻读，以及为什么没走索引会让锁范围急剧扩大；
**(c)** 线上死锁怎么定位、怎么读日志、怎么从 SQL 层面彻底避免。

## 2. 直觉理解

把数据库里的数据想象成一份**共享文档**，多个人同时在线编辑。

- **表锁**：整页批注权限被一个人独占。你要改任何一行，都得等那个人批注完、放弃整页权限。粒度粗，并发低，但开销小，MyISAM 默认用这个。
- **行锁（Record Lock）**：只在某一行上夹一个「便利贴」，只有这一行被锁，其他行照常能改。粒度细，并发高，但要定位到具体那行，所以依赖索引。
- **间隙锁（Gap Lock）**：这一行和下一行之间夹了一张「禁止插入」的隔板。当前两行没有什么问题，但你不能在这俩之间再插新行。间隙本身不是一条记录，所以叫「锁间隙」。
- **Next-Key Lock**：行锁 + 它前面那段间隙锁打包在一起。「我不但锁了这条记录，还把它前面的空位也拦住了。」
- **插入意向锁（Insert Intention Lock）**：INSERT 时在间隙上打的「我要插这里」标记，多个事务可以同时声明插不同位置，互不冲突——但如果这个间隙已经有 Gap Lock，INSERT 就得等。
- **意向锁（IS / IX）**：表级别的「通知旗」。加行锁之前先在表上挂一面旗，告诉要加表锁的人「这张表某些行已经有共享/排他锁了，你别直接上表锁」，省去一行一行检查的代价。

一句话归纳结构：**意向锁挂在表层，做协调；行级锁（Record / Gap / Next-Key / Insert Intention）挂在索引行/区间上，做真正的并发控制。**

## 3. 原理深入

### 3.1 两个维度（粒度 × 类型）一图理清

```
           共享（S / IS）            排他（X / IX）
           ─────────────────────    ─────────────────────
表 级  │  表锁 S / 意向共享 IS  │  表锁 X / 意向排他 IX
行 级  │  Record Lock S          │  Record Lock X
间隙级 │  Gap Lock（S/X 都有，   │  常以 X 模式出现）
Next-K │  Next-Key Lock S        │  Next-Key Lock X
插入意 │  Insert Intention Lock  │  （GAP 的子集，等价 IX）
```

**粒度**：表 > 行 > 间隙/Next-Key。粒度越粗开销越小，并发越低。

**类型**：
- S（共享锁 / 读锁）：多个事务可以同时持有，互相兼容。`SELECT ... FOR SHARE` 加 S 锁；`LOCK IN SHARE MODE` 是兼容保留的旧语法。
- X（排他锁 / 写锁）：只能一个事务持有，和任何其他 S/X 都冲突。`SELECT ... FOR UPDATE`、`UPDATE`、`DELETE`、`INSERT` 加 X 锁。

### 3.2 表级锁三种：Table Lock / MDL / AUTO-INC

**① 表锁（Table Lock）**

最粗粒度。显式用法：
```sql
LOCK TABLES t READ;   -- 加表级 S 锁
LOCK TABLES t WRITE;  -- 加表级 X 锁
UNLOCK TABLES;
```
MyISAM 对每条 SELECT 自动加表读锁，对每条 DML 自动加表写锁。InnoDB 几乎不需要手动表锁（有行锁），但批量导入数据时手动 `LOCK TABLES ... WRITE` 可以显著提速（跳过行锁的开销）。

**② MDL（元数据锁，Metadata Lock）**

5.5 引入。任何 DQL / DML 在执行时，Server 层自动给涉及的表加 **MDL 读锁**（MDL_S）；`ALTER TABLE` 等 DDL 执行时加 **MDL 写锁**（MDL_X）。MDL 读锁之间兼容，MDL 写锁和任何 MDL 锁都冲突。

**常见线上事故**：一个长事务持有 MDL_S（哪怕只是 `SELECT`），此时有 `ALTER TABLE` 在等 MDL_X；而 `ALTER TABLE` 又挡住了后面所有的 MDL_S 请求，导致整张表的读写全部堆积——表面看起来是 DDL 挂着，实际是事务没提交。

排查命令（MySQL 8.0）：
```sql
SELECT object_name, lock_type, lock_duration, lock_status, owner_thread_id
FROM performance_schema.metadata_locks
WHERE object_type = 'TABLE';
```

**③ AUTO-INC 锁**

`AUTO_INCREMENT` 列插入时需要分配自增值。InnoDB 有三种模式（`innodb_autoinc_lock_mode`）：
- `0`（traditional）：语句级表锁，INSERT 完整语句结束才释放——并发插入时严重竞争。
- `1`（consecutive，5.7 默认）：简单 INSERT 用轻量互斥量（mutex），批量 INSERT 才用表锁。
- `2`（interleaved，8.0 默认）：全用互斥量，并发最高，但批量 INSERT 时自增值可能不连续——这也是为什么 binlog_format=ROW 才能配合使用。

### 3.3 行级锁：Record / Gap / Next-Key / Insert Intention 四种

#### Record Lock（记录锁）

锁的是**索引树上的一条具体记录**，不是行本身。这一点至关重要：InnoDB 的行锁永远加在索引上。没有索引、或者索引失效，引擎就要扫描所有匹配的行，把它们全都锁住——效果接近表锁。

```sql
-- 假设 t 表有主键 id，以及列 age
UPDATE t SET age = 20 WHERE id = 5;
-- 加的是 id=5 这条索引记录上的 X Record Lock
```

#### Gap Lock（间隙锁）

Gap Lock 锁的是**索引上两条相邻记录之间的「区间」（开区间）**，表示这个范围内不允许 INSERT。

举例：表 t 里 id 列上已有记录 `1, 5, 10`，那么索引上存在以下几个 gap：
```
(-∞, 1)  (1, 5)  (5, 10)  (10, +∞)
```
每个 gap 可以被独立加锁。Gap Lock 之间**互相兼容**（两个 Gap Lock 锁同一个间隙也不冲突），因为它们阻止的都是 INSERT，而不是互相阻塞读写。

Gap Lock 主要在 **RR（可重复读）或 Serializable** 隔离级别下用于索引搜索和扫描。RC 下普通搜索通常不加 Gap Lock，但**外键约束检查和重复键检查仍可能使用 Gap Lock**，不能简单理解成 RC 绝对没有 Gap Lock。

**什么时候加 Gap Lock？** 范围查询、或者查询条件命中不存在的行时：
```sql
-- 假设 id=7 不存在
SELECT * FROM t WHERE id = 7 FOR UPDATE;
-- 加的是 (5, 10) 这个 gap 的 Gap Lock，防止其他事务插入 id=7
```

#### Next-Key Lock（临键锁）

Next-Key Lock = Record Lock + **它前面那段 Gap Lock**，区间是**左开右闭**。

索引值是 5 → Next-Key Lock 锁的是 `(1, 5]`，即 5 这条记录本身 + 1 和 5 之间的间隙。

InnoDB 在 RR 级别下的**当前读（FOR UPDATE / FOR SHARE / UPDATE / DELETE）默认加 Next-Key Lock**，而不是 Record Lock。这是 RR 防幻读的核心机制。

```
表 t 中 id: 1, 5, 10
对应的 Next-Key Lock 区间（以 id 值命名）：
  (-∞, 1]
  (1,  5]
  (5, 10]
  (10, +∞)  ← 这个叫 supremum pseudo-record，锁到正无穷
```

**优化 1**：等值查询命中唯一索引上存在的记录时，Next-Key Lock 退化为 Record Lock（没必要锁间隙）。
**优化 2**：等值查询向右遍历到最后一条不满足条件的记录时，Next-Key Lock 退化为 Gap Lock（只需要锁间隙，不锁那条记录本身）。

#### Insert Intention Lock（插入意向锁）

INSERT 在插入之前，会先在目标位置所在的 gap 上申请一个 **Insert Intention Lock（插入意向锁）**。它是一种特殊的 gap lock 请求，表示「准备在这个 gap 的某个位置插入」，**不是表级的 IX 意向排他锁**。

关键行为：
- **多个事务的插入意向锁之间互相兼容**，只要它们插的位置不同（例如一个插 id=3，一个插 id=4，两者都在 (1,5) 这个 gap，但不冲突）。
- **插入意向锁和 Gap Lock 不兼容**：如果 (1,5) 已经有 Gap Lock，INSERT 就必须等 Gap Lock 释放。

这就是 Gap Lock 防幻读的完整机制：已有 Gap Lock → INSERT 加不上插入意向锁 → INSERT 等待 → 幻读被阻止。

**为什么 Insert Intention 会被 Gap Lock / Next-Key Lock 阻塞？**

因为它们对同一个索引间隙提出了相反要求：

```text
Gap Lock：这个 gap 内禁止出现新的索引记录
Insert Intention：我要在这个 gap 内插入新的索引记录
```

假设主键索引中已有 `5、10`：

```sql
-- 事务 A：id=7 不存在，RR 下锁住 (5,10)
BEGIN;
SELECT * FROM t WHERE id = 7 FOR UPDATE;

-- 事务 B：插入位置落在 (5,10)，Insert Intention 必须等待
BEGIN;
INSERT INTO t(id) VALUES (7);
```

如果允许事务 B 取得 Insert Intention 并完成插入，事务 A 锁住 `(5,10)` 防止幻读的承诺就会失效。因此，事务 B 必须等事务 A 释放 Gap Lock。

Next-Key Lock 也会阻塞落在其范围内的 Insert Intention，因为：

```text
Next-Key Lock = 前方 Gap Lock + 当前 Record Lock
```

真正与 Insert Intention 冲突的是其中的 **Gap Lock 部分**，不是 Record Lock 部分。只有 INSERT 的目标位置落入该 gap 时才会等待。

三种关系可以这样记：

```text
Gap + Gap：可以共存；双方都只是在表达「禁止插入」
Insert Intention + Insert Intention：插入位置不同时可以共存
已有 Gap / Next-Key + 新请求 Insert Intention：目标位置被禁止插入，必须等待
```

### 3.4 意向锁 IS / IX：为什么是「意向」+ 兼容矩阵

> **先消除一个最容易混淆的点：IS / IX 与 Insert Intention Lock 不是同一种锁。**它们都带有「Intention」，但所处层级、锁定对象和冲突对象完全不同。

| 概念 | 所在层级 | 锁定对象 | 谁会使用 | 主要作用 |
|---|---|---|---|---|
| IS（Intention Shared） | 表级 | 整张表 | 准备给索引记录加 S 锁的事务 | 通知表级锁请求：「表内存在或即将存在行级 S 锁」 |
| IX（Intention Exclusive） | 表级 | 整张表 | `FOR UPDATE`、`INSERT`、`UPDATE`、`DELETE` 等准备加行级 X 锁的事务 | 通知表级锁请求：「表内存在或即将存在行级 X 锁」 |
| Insert Intention Lock | 索引间隙级 | 目标索引 gap 中的插入位置 | `INSERT` | 通知索引锁系统：「准备在这个 gap 的某个位置插入」 |

它们解决的是两个不同问题：

```text
IS / IX：协调「表级锁」与「行级锁」
Insert Intention：协调 INSERT 与目标 gap 上已有的 Gap / Next-Key Lock
```

同一条 INSERT 会先后同时出现 IX 和 Insert Intention，并不是二选一：

```sql
INSERT INTO t(id) VALUES (7);
```

```text
t 表：加 IX
  ↓
PRIMARY 索引中 id=7 所在的 gap：申请 Insert Intention
  ↓
新插入的 id=7 索引记录：加 X Record Lock
```

因此可以这样记忆：

> **IX 挂在表门口，说明里面有人准备改行；Insert Intention 挂在索引空位上，说明有人准备往这里插入。**

**问题起源**：事务 A 持有表 t 里某几行的行锁，此时事务 B 要加表级 X 锁。没有意向锁的话，B 必须逐行扫描确认有没有行锁——O(n)。

**意向锁的解法**：加行锁之前，先在**表**上挂一面「意向旗」：
- 要加行级 S 锁 → 先给表加 **IS（意向共享锁）**
- 要加行级 X 锁（或 Gap / Next-Key / Insert Intention）→ 先给表加 **IX（意向排他锁）**

表级锁请求时只需要检查表上有没有挂旗，O(1) 完成冲突检测。

意向锁是引擎自动加的，应用层感知不到。

#### IS / IX 什么时候出现？与隔离级别有关吗？

判断规则只有两条：

```text
准备给表内索引记录加 S 锁 → 先给表加 IS
准备给表内索引记录加 X 锁 → 先给表加 IX
```

| SQL | 表级意向锁 | 后续索引锁 |
|---|---|---|
| 普通 `SELECT`（RC / RR） | 通常没有 | MVCC 快照读，不加行锁 |
| `SELECT ... FOR SHARE` | IS | S Record / Gap / Next-Key Lock，取决于隔离级别和扫描范围 |
| `SELECT ... FOR UPDATE` | IX | X Record / Gap / Next-Key Lock，取决于隔离级别和扫描范围 |
| `INSERT` | IX | Insert Intention + 新记录的 X Lock |
| `UPDATE` / `DELETE` | IX | X Record / Gap / Next-Key Lock |

IS / IX **不只在 RR 下使用**。RC、RR 甚至其他隔离级别，只要语句准备加行级 S/X 锁，就要先遵守相同的表级意向锁协议；隔离级别改变的是后续使用 Record、Gap 还是 Next-Key Lock，不是要不要使用 IS / IX。

IS / IX 也不只是「省掉逐行扫描」的性能优化，它还防止表锁和行锁并发申请时出现竞态。假如没有意向锁：

```text
事务 A：检查表内暂时没有行锁，准备取得表级 X
事务 B：恰好在检查后给 id=7 加了 X Record Lock
事务 A：取得表级 X
结果：表级 X 和行级 X 错误地同时存在
```

有了多粒度锁协议后，事务 B 必须先取得 IX：

```text
B 先取得 IX → A 的表级 X 与 IX 冲突，A 等待
A 先取得表级 X → B 的 IX 与表级 X 冲突，B 等待
```

所以 IS / IX 同时承担两件事：**O(1) 判断表级锁能否取得，以及保证表锁与行锁的申请顺序不会产生竞态**。它们不负责锁住数据，也不负责防幻读。

**兼容矩阵（表级）**：

下面所有矩阵统一使用这个方向：

```text
横向的栏（column）＝当前事务新请求的锁
纵向的行（row）   ＝其他事务已经持有、或者在锁队列中排在前面的锁
✓                 ＝新请求可以立即取得，不需要等待
✗                 ＝新请求必须等待现有锁释放
```

| 已持有的锁 ↓ / 新请求的锁 → | IS 请求 | IX 请求 | S 表锁请求 | X 表锁请求 |
|---|:---:|:---:|:---:|:---:|
| 已持有 IS | ✓ | ✓ | ✓ | ✗ |
| 已持有 IX | ✓ | ✓ | ✗ | ✗ |
| 已持有 S 表锁 | ✓ | ✗ | ✓ | ✗ |
| 已持有 X 表锁 | ✗ | ✗ | ✗ | ✗ |

规律：IS / IX 之间全部兼容（意向锁只是声明，不互相阻塞）；S 表锁和 IX 不兼容（表上有行在写，不能加读锁）；X 表锁和任何锁都不兼容。

**行级锁兼容矩阵**：

这张表继续使用相同方向：**每一行是已经存在的锁，每一栏是现在要申请的新锁**。

| 已存在或排在前面的锁 ↓ / 新请求的锁 → | Record S 请求 | Record X 请求 | Gap 请求 | Next-Key S 请求 | Next-Key X 请求 | Insert Intention 请求 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| 已有 Record S | ✓ | ✗ | ✓ | ✓ | ✗ | ✓ |
| 已有 Record X | ✗ | ✗ | ✓ | ✗ | ✗ | ✓ |
| 已有 Gap Lock | ✓ | ✓ | ✓ | ✓ | ✓ | **✗** |
| 已有 Next-Key S | ✓ | ✗ | ✓ | ✓ | ✗ | **✗** |
| 已有 Next-Key X | ✗ | ✗ | ✓ | ✗ | ✗ | **✗** |
| 已有 Insert Intention | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

读矩阵时先找「已有锁」所在的行，再找「新请求」所在的栏。例如：

```text
已有 Gap Lock 这一行
  × 新请求 Insert Intention 这一栏
  = ✗，INSERT 必须等待
```

这个等待关系是**有方向的**，因此矩阵不能沿对角线直接镜像：

- 已有 Gap / Next-Key Lock 时，新请求的 Insert Intention 必须等待，否则就能绕过「禁止向 gap 插入」的保证。
- 已有 Insert Intention 时，后来申请的普通 Gap / Next-Key Lock 不需要反过来等待它。Insert Intention 是插入过程中的短暂请求；让后来的 Gap / Next-Key 请求等待它，可能制造没有必要的循环等待。
- 两个 Insert Intention 如果准备插入不同位置，可以同时存在；真正插入同一个唯一键时，后续还会由唯一键检查和记录锁处理冲突。

因此，最需要记住的格子是：**已有 Gap / Next-Key Lock + 新请求 Insert Intention = 等待**。这正是 RR 下 Gap / Next-Key Lock 能阻止幻读插入的机制。

规则依据：[MySQL 8.4 Reference Manual — InnoDB Locking](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking.html)；矩阵的方向性来自 InnoDB 对「新锁请求是否必须等待队列中已有锁」的判断，参见 [`rec_lock_check_conflict`](https://github.com/mysql/mysql-server/blob/trunk/storage/innobase/lock/lock0lock.cc)。

### 3.5 SELECT ... FOR UPDATE / FOR SHARE：语义、阻塞与生产边界

#### 它们不是「更强一点的普通 SELECT」

普通 `SELECT` 是 MVCC 快照读；`FOR UPDATE` 和 `FOR SHARE` 是锁定读（Locking Read），会读取最新版本并为后续事务操作取得锁：

| 语句 | 主要语义 | 取得的记录锁 | 对其他事务的主要影响 |
|---|---|---|---|
| 普通 `SELECT` | 读取一致性快照 | 不加行锁 | 通常不阻塞写入，也不被未提交写入阻塞 |
| `SELECT ... FOR SHARE` | 保证读到的记录在本事务内不被修改或删除 | S Lock | 其他 `FOR SHARE` 可并发；X Lock、UPDATE、DELETE 需要等待 |
| `SELECT ... FOR UPDATE` | 读取最新记录并预留排他修改权 | X Lock | 其他 S/X locking read、UPDATE、DELETE 需要等待 |

因此，应把 `FOR UPDATE` 理解成「更新操作的前半段」，而不是普通查询附加一个选项。`FOR SHARE` 也不是无害读；它虽然允许其他共享锁定读，但会阻塞需要 X Lock 的写操作。

这些记录锁会持续到事务 `COMMIT` 或 `ROLLBACK`。在 `autocommit=1` 且没有显式事务时，锁会在语句结束后立即释放，通常无法保护后续另一条 SQL。

#### 为什么未提交 INSERT 不阻塞普通 SELECT，却会阻塞 locking read？

```sql
-- 事务 A
BEGIN;
INSERT INTO t(id) VALUES (7);
-- 尚未提交，id=7 被 A 的 X Record Lock 保护
```

此时事务 B 的不同读法结果不同：

```sql
-- 普通快照读：不等待，也看不到未提交的 id=7
SELECT * FROM t WHERE id BETWEEN 5 AND 10;

-- 锁定读：扫描到 id=7 时，需要等待 A 决定 COMMIT 或 ROLLBACK
SELECT * FROM t WHERE id BETWEEN 5 AND 10 FOR UPDATE;
SELECT * FROM t WHERE id BETWEEN 5 AND 10 FOR SHARE;
```

数据库不能让 B 直接读取 A 的未提交数据，否则会脏读；也不能让 locking read 永远把 `id=7` 当成不存在，因为 A 可能马上提交。它只能等待：

```text
A COMMIT   → B 确认 id=7 存在，再取得相应 S/X Lock
A ROLLBACK → id=7 被撤销，B 继续并返回不包含 id=7 的结果
```

这里真正阻塞 B 的是未提交记录上的 **X Record Lock**，不是 Insert Intention，也不是 RR 特有的 Gap Lock。因此改成 RC 仍然可能等待；任何可靠的隔离级别都不能让两个事务同时拥有同一条记录的排他修改权。

如果接口不允许等待，可以显式选择：

```sql
SELECT ... FOR UPDATE NOWAIT;       -- 取得不到锁就立即报错
SELECT ... FOR UPDATE SKIP LOCKED;  -- 跳过已锁记录，主要用于任务队列
```

`SKIP LOCKED` 返回的不是一致性视图，不适合普通交易判断；它适合多个 worker 从 queue-like table 并发领取任务。

#### RR 和 RC 到底改变了什么？

| 场景 | RR | RC |
|---|---|---|
| 普通 SELECT 遇到未提交记录 | MVCC，不等待、不读取未提交版本 | MVCC，不等待、不读取未提交版本 |
| locking read 遇到未提交记录的 X Lock | 等待 | **同样等待** |
| 完整唯一索引等值命中 | 通常只锁 Record | 通常只锁 Record |
| 完整唯一索引等值未命中 | 锁住目标值所在 gap | 普通搜索通常不锁 gap |
| 非唯一索引 / 范围搜索 | 通常使用 Next-Key Lock，保护记录和 gap | 主要锁命中记录，非匹配记录锁提前释放 |
| 外键 / 重复键检查 | 可能使用额外 Record / Gap Lock | **仍可能使用**额外 Record / Gap Lock |

RC 能减少 RR 的 Gap / Next-Key Lock 放大，但不能消除 Record Lock 冲突。真正危险的组合是：

```text
RR
+ FOR UPDATE / FOR SHARE
+ 非唯一索引、范围查询、记录不存在或索引失效
+ 长事务
+ 高并发
```

#### 大型高并发项目怎么使用？

大型项目通常不会禁用 locking read，但会把它限制在少数必须悲观串行化的短事务中。绝大多数请求优先使用更小的并发控制原语：

| 业务需求 | 优先选择 |
|---|---|
| 只展示数据 | 普通 `SELECT` |
| 单行条件修改 | 一条原子 `UPDATE ... WHERE ...` |
| 低冲突并发修改 | `version` 乐观锁 / Compare-And-Set |
| 唯一性判断 | UNIQUE 约束 + 直接 INSERT |
| 读多行后做复杂判断并修改多行 | 短事务内精确使用 `FOR UPDATE` |
| 只需保证依赖记录暂时不被改或删 | `FOR SHARE`，使用场景通常更少 |
| 多 worker 领取任务 | `FOR UPDATE SKIP LOCKED` |

例如扣减单行库存，通常优先使用原子 UPDATE：

```sql
UPDATE inventory
SET stock = stock - 1
WHERE product_id = ?
  AND stock >= 1;
```

只有当业务必须先读取多条记录、进行无法放进一条 SQL 的复杂校验，再修改多行或多表时，才适合使用 `FOR UPDATE`。

locking read 的生产约束：

- 必须走明确的主键、唯一索引或经过验证的窄范围索引。
- 持锁期间不调用 RPC、HTTP 或其他外部系统。
- 多行加锁使用统一顺序，避免交叉等待。
- 事务必须短，并处理 `1205 lock wait timeout` 和 `1213 deadlock` 重试。
- 不需要保护「记录不存在」或「范围内不能插入」时，可以评估让该事务使用 RC。
- `NOWAIT` 用于快速失败；`SKIP LOCKED` 主要限于任务队列，不当作一般一致性查询。

规则依据：[MySQL 8.4 Locking Reads](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html)、[Locks Set by Different SQL Statements](https://dev.mysql.com/doc/refman/8.4/en/innodb-locks-set.html) 和 [SELECT — NOWAIT / SKIP LOCKED](https://dev.mysql.com/doc/refman/8.4/en/select.html)。

### 3.6 RR 下当前读怎么防幻读（Next-Key + 插入意向锁配合）

**幻读**的定义：同一事务内，两次相同查询返回了不同的行数（通常是中间有其他事务 INSERT）。

MVCC 的快照读（普通 SELECT）通过读 undo log 快照避免幻读，但**当前读（`FOR UPDATE`、`FOR SHARE` / `LOCK IN SHARE MODE`、`UPDATE`、`DELETE`）会绕过快照，直接读最新数据**，MVCC 此时无效。

RR 用 Next-Key Lock 防当前读的幻读，完整流程：

```
事务 A：
BEGIN;
SELECT * FROM t WHERE id BETWEEN 3 AND 8 FOR UPDATE;
  -- 扫描索引，命中 id=5 → 加 Next-Key Lock (1,5]
  -- 继续扫，遇到 id=10（第一个不满足条件的）→ 退化为 Gap Lock (5,10)
  -- 整体锁住的范围：(1, 10)，即 id 在这个区间内不能 INSERT

事务 B：
INSERT INTO t VALUES (6, ...);  -- 要在 (5,10) 这个 gap 插入
  -- 先加 Insert Intention Lock on (5,10)
  -- 发现 (5,10) 已有 Gap Lock → 等待
  -- 事务 A 提交前，事务 B 一直阻塞

事务 A：
SELECT * FROM t WHERE id BETWEEN 3 AND 8 FOR UPDATE;  -- 再次执行
  -- id=6 还不存在（B 被阻塞），结果和第一次相同 → 无幻读
COMMIT;
  -- A 的 Next-Key Lock / Gap Lock 释放
  -- B 的 Insert Intention Lock 加上，INSERT 执行成功
```

**注意**：RC 下普通索引搜索和扫描通常不使用 Gap Lock，所以当前读允许其他事务在搜索范围内插入新记录；但外键约束检查和重复键检查仍可能使用 Gap Lock。这是 RC vs RR 在锁行为上的核心区别。

### 3.7 索引选择影响锁范围

InnoDB 行锁加在**索引**上，不是加在行上。这条规则有三个重要推论：

**推论 1：没走索引 → 全表扫描，RR 下可能锁住每条扫描记录**

```sql
-- age 列没有索引
UPDATE t SET status = 1 WHERE age = 25;
```
引擎无法定位，只能扫描整个聚簇索引。在 RR 下，扫描过程中对遇到的索引记录加 Next-Key Lock，并通常持有到事务结束，效果接近锁表；在 RC 下仍然必须全表扫描，但不匹配 `age=25` 的记录锁会在判断后释放，主要保留真正需要修改的记录锁。

因此，RC 只能缩小**持锁范围**，不能缩小**扫描范围**；真正的解决方法仍是在 WHERE 条件列上建立合适索引。

**推论 2：走了非唯一二级索引 → 锁范围包含索引值相同的所有行 + 间隙**

```sql
-- idx_age 是非唯一索引，age=25 有 3 行（id=10,20,30）
SELECT * FROM t WHERE age = 25 FOR UPDATE;
```
锁定：
- Record Lock on age=25, id=10
- Record Lock on age=25, id=20
- Record Lock on age=25, id=30
- Gap Lock on (age=20 行, age=25 的第一行) 之间的间隙
- Gap Lock on (age=25 最后一行, age=30 行) 之间的间隙
- 每条 Record Lock 实际是 Next-Key Lock，覆盖了整个 age=25 的区间及前后 gap

**推论 3：走了唯一索引且等值命中 → Next-Key Lock 退化为 Record Lock，Gap Lock 消失**

```sql
-- id 是主键（唯一），id=5 存在
SELECT * FROM t WHERE id = 5 FOR UPDATE;
-- 只加 id=5 的 Record Lock，不加任何 Gap Lock
```
这就是为什么主键等值查询的并发性最好。

**推论 4：索引失效 = 行锁升级**

`WHERE varchar_col = 100`（类型不匹配导致隐式转换）、`WHERE DATE(created_at) = '2026-01-01'`（函数包裹）等情况下索引失效，效果同推论 1。

### 3.8 INSERT / UPDATE / DELETE 到底怎么加锁

`INSERT`、`UPDATE`、`DELETE` 属于会修改数据的 DML（Data Manipulation Language）语句。它们不会先把整张 InnoDB 表加上排他表锁，而是遵循两层流程：

1. 在表上加 **IX（意向排他锁）**，声明本事务准备修改某些索引记录。
2. 根据实际执行计划，在聚簇索引、二级索引或索引间隙上加 Record / Gap / Next-Key / Insert Intention Lock。

锁哪些记录由**实际扫描的索引范围**决定，不是只看 SQL 文本中的 `WHERE`。普通行级锁会一直持有到事务 `COMMIT` 或 `ROLLBACK`；`AUTO-INC` 锁是单独的机制，部分模式下只持有到当前 INSERT 语句结束。

#### INSERT：先声明插入位置，再锁住新记录

```sql
INSERT INTO users(id, email, age)
VALUES (7, 'a@example.com', 25);
```

可以把主要流程理解为：

```text
表上加 IX
  ↓
在各目标索引的插入位置申请 Insert Intention Lock
  ↓
检查主键、唯一索引和外键约束
  ↓
写入聚簇索引以及相关二级索引
  ↓
给新插入的索引记录加 X Record Lock，持有到事务结束
```

关键边界：

- Insert Intention Lock 表示「准备在这个 gap 的某个位置插入」，不是把整个 gap 独占。两个事务在同一个 gap 插入不同值，通常可以并发。
- 如果目标 gap 已经被其他事务的 Gap / Next-Key Lock 覆盖，Insert Intention Lock 会等待。
- 简单 INSERT 给新记录加的是 **X Record Lock**，不是 Next-Key Lock，不会因为插入一行就禁止别人向它前面的整个 gap 插入。
- 普通 INSERT 遇到重复唯一键时，会对冲突记录申请共享锁；`INSERT ... ON DUPLICATE KEY UPDATE` 遇到冲突时则申请排他锁并更新该记录。
- 外键检查会给检查到的父表或子表索引记录加 S Record Lock，即使约束检查最终失败也可能产生锁。
- 自增值分配还可能涉及 AUTO-INC 锁或轻量互斥量，这和这里的索引记录锁是两个维度。

#### UPDATE：先按索引搜索并锁定，再修改相关索引

```sql
UPDATE users
SET age = 26
WHERE id = 7;
```

主要流程是：

```text
表上加 IX
  ↓
按照执行计划搜索 WHERE 条件
  ↓
锁住搜索过程中需要保护的索引记录或范围
  ↓
锁住对应的聚簇索引记录
  ↓
修改聚簇索引；如果索引列变化，同时修改相关二级索引
```

锁范围取决于搜索方式：

- **完整唯一索引等值查询且记录存在**：只需要该索引记录的 X Record Lock。例如主键 `id=7`。
- **完整唯一索引等值查询但记录不存在**：RR 下锁住该值所在的 gap；RC 下普通搜索通常不锁 gap。
- **非唯一索引或范围查询**：RR 下锁住实际扫描范围的 X Next-Key Lock；RC 下主要保留需要更新记录的 X Record Lock。
- **没有可用索引**：RR 下扫描聚簇索引并可能将所有扫描记录的 Next-Key Lock 持有到事务结束；RC 同样全表扫描，但不匹配记录的锁会在判断后释放。

如果 UPDATE 通过二级索引找到记录，例如：

```sql
-- idx_name(name)，idx_age(age)
UPDATE users
SET age = 26
WHERE name = 'Ada';
```

它至少涉及三部分：

1. 锁住 `idx_name` 中被扫描和命中的索引记录或范围。
2. 根据二级索引中的主键值，锁住对应的聚簇索引记录。
3. 因为 `age` 被修改，还要删除旧的 `idx_age(age=25)` 索引项并插入新的 `idx_age(age=26)` 索引项，期间执行必要的索引写入和重复键检查。

因此，UPDATE 不一定只锁 WHERE 使用的一个索引；它还必须保护真正的数据行和所有被修改的索引项。

#### DELETE：搜索阶段与 UPDATE 相同，再把记录标记删除

```sql
DELETE FROM users
WHERE id = 7;
```

DELETE 的搜索和加锁规则基本与 UPDATE 相同：

- 完整唯一索引等值命中：锁对应的 X Record Lock。
- 非唯一索引或范围扫描：RR 下通常使用 X Next-Key Lock。
- 没有可用索引：仍然要扫描整个聚簇索引，RR 下可能产生接近锁表的效果。
- 通过二级索引找到记录时，既要锁搜索使用的二级索引记录，也要锁对应的聚簇索引记录，并处理其他二级索引项。

InnoDB 执行 DELETE 时，通常先把聚簇索引和二级索引记录标记为删除；真正的物理清理由后台 purge 完成。其他事务在当前事务提交或回滚前，不能修改这些被锁住的记录。

如果存在外键：

- 删除父表记录时，需要检查是否存在引用它的子表记录，并锁住检查到的索引记录。
- 配置 `ON DELETE CASCADE` 时，还会继续删除子表记录，因此锁会沿着级联链扩散到其他表。

#### RR 与 RC 对 DML 锁范围的影响

| 场景 | RR（Repeatable Read） | RC（Read Committed） |
|---|---|---|
| 唯一索引等值命中 | X Record Lock | X Record Lock |
| 唯一索引等值未命中 | 锁住目标值所在 gap | 普通搜索通常不锁 gap |
| 非唯一索引 / 范围搜索 | X Next-Key Lock，保护记录和 gap | 主要锁需要修改的记录，不匹配记录锁提前释放 |
| 没有可用索引 | 全表扫描，扫描记录可能持续持有 Next-Key Lock | 仍然全表扫描，但不匹配记录锁会释放 |
| INSERT | Insert Intention + 新记录 X Lock | 基本相同 |
| 外键 / 重复键检查 | 可能产生额外 Record / Gap Lock | **仍可能产生**额外 Record / Gap Lock |

所以必须分清两个问题：

> **索引决定扫描多少记录；隔离级别决定扫描过程中加什么锁、哪些锁需要持有到事务结束。**

规则依据：[MySQL 8.4 Reference Manual — Locks Set by Different SQL Statements in InnoDB](https://dev.mysql.com/doc/refman/8.4/en/innodb-locks-set.html)。

### 3.9 死锁怎么产生、怎么读 INNODB STATUS 的 deadlock 日志

#### 死锁产生的三种经典模式

**模式 A：两个事务交叉更新同两行**

```
事务 1                          事务 2
UPDATE t SET v=1 WHERE id=5;    -- 锁 id=5
                                UPDATE t SET v=2 WHERE id=10; -- 锁 id=10
UPDATE t SET v=1 WHERE id=10;   -- 等待 id=10，被事务 2 持有
                                UPDATE t SET v=2 WHERE id=5;  -- 等待 id=5，被事务 1 持有
-- 循环等待 → 死锁
```

**模式 B：唯一索引重复 INSERT**

```
事务 1                               事务 2
INSERT INTO t(uk) VALUES ('foo');    -- 加 uk='foo' 的 Record Lock X
                                     INSERT INTO t(uk) VALUES ('foo');
                                     -- uk 已存在，等待事务 1 的 X 锁；
                                     -- 同时加了一个 S 锁请求（duplicate key check）
事务 1 ROLLBACK;
-- 事务 1 释放 X 锁
-- 事务 2 的 S 锁通过，但随后还要加 X 锁
-- 如果同时有事务 3 也在 ROLLBACK 后加 S 锁，
--   事务 2 和事务 3 互相等待对方的 S → X 升级 → 死锁
```

**模式 C：外键级联**

子表删除时触发父表的级联操作，父表级联又可能触发其他子表更新，形成跨表锁链。

#### 读 INNODB STATUS 死锁日志

执行：
```sql
SHOW ENGINE INNODB STATUS\G
```

找到 `LATEST DETECTED DEADLOCK` 段：

```
------------------------
LATEST DETECTED DEADLOCK
------------------------
2026-05-13 10:23:45 0x7f8b4c0f2700
*** (1) TRANSACTION:
TRANSACTION 12345, ACTIVE 5 sec starting index read
mysql tables in use 1, locked 1
LOCK WAIT 3 lock struct(s), heap size 1136, 2 row lock(s)
MySQL thread id 101, OS thread handle 139..., query id 9876 localhost root updating
UPDATE orders SET status=2 WHERE id=1001
*** (1) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 42 page no 3 n bits 72 index PRIMARY of table `shop`.`orders`
trx id 12345 lock_mode X locks rec but not gap waiting
Record lock, heap no 5 PHYSICAL RECORD: n_fields 4; compact format; info bits 0
 0: len 8; hex 00000000000003e9; asc         ;; -- id=1001

*** (2) TRANSACTION:
TRANSACTION 12346, ACTIVE 8 sec starting index read
mysql tables in use 1, locked 1
3 lock struct(s), heap size 1136, 2 row lock(s)
MySQL thread id 102, OS thread handle 139..., query id 9877 localhost root updating
UPDATE orders SET status=3 WHERE id=1002
*** (2) HOLDS THE LOCK(S):
RECORD LOCKS space id 42 page no 3 n bits 72 index PRIMARY of table `shop`.`orders`
trx id 12346 lock_mode X locks rec but not gap
Record lock, heap no 5 PHYSICAL RECORD: n_fields 4; compact format; info bits 0
 0: len 8; hex 00000000000003e9; asc         ;; -- id=1001

*** (2) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 42 page no 3 n bits 72 index PRIMARY of table `shop`.`orders`
trx id 12346 lock_mode X locks rec but not gap waiting
Record lock, heap no 6 PHYSICAL RECORD: n_fields 4; compact format; info bits 0
 0: len 8; hex 00000000000003ea; asc         ;; -- id=1002

*** WE ROLL BACK TRANSACTION (1)
```

**逐段解读**：

| 字段 | 含义 |
|------|------|
| `TRANSACTION 12345, ACTIVE 5 sec` | 事务 12345，已运行 5 秒 |
| `starting index read` | 当前状态（还有 `fetching rows`、`updating` 等） |
| `mysql tables in use 1, locked 1` | 使用了 1 张表，持有 1 张表的锁结构 |
| `2 row lock(s)` | 持有 2 个行锁 |
| `MySQL thread id 101` | 对应 `SHOW PROCESSLIST` 里的 Id=101，可以找到是哪条连接/SQL |
| `WAITING FOR THIS LOCK TO BE GRANTED` | 事务 1 在等这把锁 |
| `index PRIMARY of table shop.orders` | 锁在 `shop.orders` 表的 PRIMARY 索引上 |
| `lock_mode X locks rec but not gap` | 排他的 **Record Lock**（`but not gap` = 不是 Gap Lock） |
| `lock_mode X locks gap before rec` | **Gap Lock** |
| `lock_mode X` (无后缀) | **Next-Key Lock** |
| `hex 00000000000003e9` | 锁定的记录主键值，十六进制转十进制 = 1001 |
| `HOLDS THE LOCK(S)` | 事务 2 持有 id=1001 的 X 锁 |
| `*** WE ROLL BACK TRANSACTION (1)` | InnoDB 选择回滚事务 1（通常回滚代价小的那个）|

**快速定位步骤**：
1. 找 `TRANSACTION (1)` 的 `MySQL thread id` → 在 `SHOW PROCESSLIST` 里找那条连接的 `USER`、`HOST`、`INFO`（当前 SQL）
2. 看 `WAITING FOR` 和 `HOLDS THE LOCK` — 确认两个事务各等谁持有的什么锁
3. 把两个事务的 SQL 顺序画出来，找到「交叉等待」点
4. 调整 SQL 执行顺序或拆分事务

**lock_mode 速查**：

| 日志中显示 | 锁类型 |
|-----------|--------|
| `lock_mode S` | Next-Key S |
| `lock_mode S locks rec but not gap` | Record S |
| `lock_mode S locks gap before rec` | Gap S |
| `lock_mode X` | Next-Key X |
| `lock_mode X locks rec but not gap` | Record X |
| `lock_mode X locks gap before rec` | Gap X |
| `lock_mode X locks insert intention` | Insert Intention X |

### 3.10 8.0 推荐用 performance_schema.data_locks 排查

MySQL 5.7 的 `information_schema.innodb_trx + innodb_locks + innodb_lock_waits` 在 8.0 中被迁移到 `performance_schema`，信息更全：

```sql
-- 查看当前所有行锁
SELECT
  r.trx_id           AS waiting_trx_id,
  r.trx_mysql_thread_id AS waiting_thread,
  r.trx_query        AS waiting_query,
  b.trx_id           AS blocking_trx_id,
  b.trx_mysql_thread_id AS blocking_thread,
  b.trx_query        AS blocking_query,
  dl.object_schema,
  dl.object_name,
  dl.index_name,
  dl.lock_type,
  dl.lock_mode,
  dl.lock_status
FROM performance_schema.data_lock_waits dlw
JOIN information_schema.innodb_trx r
  ON r.trx_id = dlw.requesting_engine_transaction_id
JOIN information_schema.innodb_trx b
  ON b.trx_id = dlw.blocking_engine_transaction_id
JOIN performance_schema.data_locks dl
  ON dl.engine_transaction_id = dlw.blocking_engine_transaction_id
ORDER BY blocking_thread;
```

`data_locks` 比老的 `innodb_locks` 更完整：`innodb_locks` 只显示「有等待关系的锁」，`data_locks` 显示**所有持有中的锁**，包括没有等待方的锁。

**锁等待超时设置**：
```sql
SHOW VARIABLES LIKE 'innodb_lock_wait_timeout';  -- 默认 50 秒
SET innodb_lock_wait_timeout = 5;                -- 会话级，调小以便快速报错而不是无限等待
```

**死锁自动检测**：
```sql
SHOW VARIABLES LIKE 'innodb_deadlock_detect';  -- 默认 ON
-- 关闭后死锁依赖 innodb_lock_wait_timeout 超时解决，高并发时可能降低死锁检测开销
-- 但一般不建议关闭
```

## 4. 日常开发应用

**写 SQL 时的锁意识**

- **SELECT 能不加锁就不加锁**：普通 `SELECT` 走 MVCC 快照读，不加行锁，性能最好。只有真正需要「我读完之后要更新，且中间不允许别人改」才用 `SELECT ... FOR UPDATE`。
- **事务要短**：锁在事务提交/回滚时释放（MDL 写锁在 DDL 完成时释放）。事务越长，锁持有时间越长，并发越低。把不需要在事务里的操作（如外部调用、大计算）移到事务外面。

> **DB 短鎖的系統邊界**：DB row lock 只保護本地短事務臨界區；長任務若跨外部 I/O、進程 crash 或接管，不應持續占用 transaction。請依 invariant 選 immutable batch、logical freeze、reservation、lease/fencing 或 workflow，決策入口見[並發正確性與長任務協調](../../system-design/11-並發正確性與長任務協調.md)。

- **UPDATE/DELETE WHERE 条件列一定要有索引**：没有索引 = 锁范围无限扩大，是线上锁等待事故最常见的原因。上线前 `EXPLAIN` 确认 `type` 不是 `ALL`。
- **同一个业务流程，锁多张表时固定顺序**：比如下单先锁 `inventory` 再锁 `orders`，退款也按同样顺序，杜绝交叉死锁。
- **INSERT 的唯一键冲突要处理**：捕获 `1062 Duplicate entry` 错误后及时重试或直接 `INSERT IGNORE` / `ON DUPLICATE KEY UPDATE`，避免 S 锁升级 X 锁的死锁窗口。

**DDL 上线时防 MDL 超时**

1. 在业务低峰期执行 `ALTER TABLE`
2. 先用 `pt-online-schema-change` 或 `gh-ost` 做 online DDL（内部也有 MDL，但等待时间很短）
3. 执行 DDL 之前，检查 `performance_schema.metadata_locks` 有没有长事务持有 MDL_S
4. 如果发现 MDL 等待，找到并 `KILL` 对应的 thread id（谨慎，确认是可以终止的连接）

## 5. 调优实战

**场景 A：「线上有锁等待，怎么定位是哪条 SQL」**

1. 发现慢：监控告警 `innodb_row_lock_waits` 或 `innodb_lock_wait_timeout` 错误日志激增
2. 立刻执行：
   ```sql
   SELECT * FROM performance_schema.data_lock_waits\G
   -- 找到 waiting_engine_transaction_id 和 blocking_engine_transaction_id
   SELECT * FROM information_schema.innodb_trx
   WHERE trx_id IN (<waiting_id>, <blocking_id>)\G
   -- trx_query 就是对应的 SQL；trx_mysql_thread_id 对应 SHOW PROCESSLIST 的 Id
   ```
3. 用 `trx_mysql_thread_id` 在 `SHOW PROCESSLIST` 里找到 `HOST` 和 `INFO`，结合应用日志追溯调用链
4. 根据 SQL 的 `EXPLAIN` 判断有没有走索引；如果没走，补索引是最快的修复

**场景 B：「频繁死锁，怎么改 SQL 顺序避免」**

诊断步骤：
1. `SHOW ENGINE INNODB STATUS\G` 看 `LATEST DETECTED DEADLOCK`，把两个事务的 SQL 抄下来
2. 画出时序图：
   ```
   时间轴 →
   事务 A: 锁 row1 → 等 row2
   事务 B:          锁 row2 → 等 row1
   ```
3. 找到「两个事务加锁顺序相反」的那对行/表

修复方向：
- **统一加锁顺序**：所有涉及多行/多表的业务，按同一个固定顺序（例如主键从小到大）依次加锁
- **缩短事务**：拆成更小的事务，减少同时持有多把锁的窗口期
- **降低隔离级别到 RC**：RC 的普通搜索和扫描通常不使用 Gap Lock，可以减少相关死锁（外键和重复键检查仍可能使用；代价是当前读可能出现幻读，需要业务层容忍或处理）
- **批量操作改为逐行处理**：`WHERE id IN (1,2,3)` 批量更新时加锁顺序不确定，改为按 `id` 从小到大逐行 UPDATE
- **重试机制兜底**：死锁被 InnoDB 自动检测并回滚一个事务，应用层捕获 `Error 1213 Deadlock` 后自动重试

**场景 C：「Gap Lock 导致低并发，怎么调」**

现象：高并发 INSERT，经常出现 `lock wait timeout` 或死锁，INNODB STATUS 里看到大量 `lock_mode X locks gap before rec`。

诊断：
```sql
-- 检查是否是唯一索引重复 insert 触发 gap lock
-- 检查 WHERE 条件有没有范围查询锁了大片 gap
```

解决：
- 如果业务允许，把 RR 降到 RC：`SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;`——普通搜索不再使用 Gap Lock 时，INSERT 并发通常会改善；外键和重复键检查仍是例外
- 检查范围查询是否必要，能否改为精确等值查询
- 唯一键冲突改用 `INSERT ... ON DUPLICATE KEY UPDATE` 减少 S → X 锁升级的窗口

## 6. 面试高频考点

### 必考对比

| 维度 | Gap Lock | Next-Key Lock | Insert Intention Lock |
|------|---------|---------------|-----------------------|
| 锁的对象 | 两条记录之间的间隙（开区间） | 记录本身 + 前面的间隙（左开右闭） | 间隙内的某个插入位置 |
| 区间示例（索引有 1,5,10） | (1,5) | (1,5] | 插 id=3 时在 (1,5) 内 |
| 兼容性 | Gap Lock 之间互相兼容 | 和 Insert Intention 不兼容 | Insert Intention 之间互相兼容；但和 Gap/Next-Key 不兼容 |
| 生效条件 | RR 或 Serializable | RR 或 Serializable | 有 Gap Lock 时才会等待 |
| 目的 | 防止 INSERT 填入间隙 | 防幻读：锁记录 + 锁前方间隙 | 多个 INSERT 互不阻塞，除非遇到 Gap Lock |

### "RR 能完全解决幻读吗" — 标准答案

不能完全解决。MVCC 快照读解决了普通 `SELECT` 的幻读；Next-Key Lock 解决了**当前读（`FOR UPDATE` / `FOR SHARE` / `UPDATE` / `DELETE`）** 的幻读。但如果事务内先用快照读读了一次，再用当前读读第二次，两次结果会不一致，这种情况 RR 不能防。要彻底防幻读，用 Serializable（但并发极低）。

### "没走索引时锁会变成什么" — 两句话答法

InnoDB 行锁加在索引上，不加索引就没有「锁哪一行」的依据，引擎会全表扫描并对所有扫到的行加 Next-Key Lock，效果等同表锁。这就是生产环境中「一条 `UPDATE WHERE` 不走索引导致整表锁死」事故的原因。

### "意向锁 IS 和 IX 的意义" — 一句话答法

IS / IX 是表级「声明旗」，让需要加表级锁的操作能 O(1) 检测表上是否有行锁，而不用逐行扫描；它们本身不阻塞任何行操作，只和表级 S / X 锁产生冲突。

### "读 INNODB STATUS deadlock 日志的关键词" — 速查

- `lock_mode X locks rec but not gap` → Record X（纯行锁）
- `lock_mode X locks gap before rec` → Gap X（纯间隙锁）
- `lock_mode X` (无后缀) → Next-Key X
- `lock_mode X locks insert intention` → Insert Intention
- `HOLDS THE LOCK(S)` → 谁持有
- `WAITING FOR THIS LOCK TO BE GRANTED` → 谁在等
- `WE ROLL BACK TRANSACTION (N)` → InnoDB 回滚了哪个事务（通常是 undo 量小的）

### "什么情况下 Next-Key Lock 退化" — 两个退化规则

1. **等值查询 + 唯一索引 + 记录存在** → Next-Key Lock 退化为 Record Lock（不需要锁间隙，唯一性保证不会有相同值插入）
2. **等值查询向右遍历到第一条不满足的记录** → 该记录的 Next-Key Lock 退化为 Gap Lock（该记录本身不在查询范围内，不需要 Record Lock）

### 易错点

- **行锁是加在索引上，不是加在行数据上**：主键索引 = 聚簇索引，二级索引加行锁时还会在聚簇索引上加对应记录的 Record Lock（防止其他事务通过主键直接改这行）
- **Gap Lock 之间不冲突**：两个事务可以同时持有同一个 Gap 的 Gap Lock，它们只阻止 INSERT，不互相阻塞
- **RC 不是绝对没有 Gap Lock**：普通索引搜索和扫描通常不使用 Gap / Next-Key Lock，但外键约束检查和重复键检查仍可能使用 Gap Lock；RC 也不能避免无索引 SQL 的全表扫描
- **MDL 不是行锁**：MDL 是 Server 层的元数据保护，与 InnoDB 行锁是不同维度的锁，常被混淆
- **锁释放时机是事务提交/回滚，不是语句结束**：即使一条 `UPDATE` 执行完了，它加的行锁要等事务 `COMMIT` 或 `ROLLBACK` 才释放

## 7. 一句话总结

InnoDB 的锁是「意向锁挂表层（O(1) 冲突检测 + 多粒度锁正确性）+ 行级锁挂索引上（Record / Gap / Next-Key / Insert Intention）」的两层设计；IS / IX 与隔离级别无关，RR 的 locking read 通常用 Next-Key Lock 防幻读，等值命中唯一索引时退化为 Record Lock；不走索引就必须全表扫描，RR 下可能让扫描记录持续持锁；死锁治理要统一加锁顺序、缩短事务并缩小扫描范围，不需要保护 gap 的事务可评估使用 RC。

## Scenarios

> 本机实测（MySQL 8.0.36），每个都跑过「预期 → 实机 → 落差」。

- [01 - WHERE 列没索引，行锁退化成锁全表](scenarios/01-no-index-locks-whole-table.md) — 5 万行表的无索引 UPDATE 实测加了 50130 把 X 行锁（比行数还多，含间隙）
- [02 - 间隙锁挡住 INSERT](scenarios/02-gap-lock-blocks-insert.md) — A 锁住范围间隙，B 往间隙插入 → `ERROR 1205` 等锁超时
- [03 - 经典死锁复现 + 读懂死锁日志](scenarios/03-deadlock-reproduce-and-read-log.md) — 交叉加锁 → `ERROR 1213`，逐字解读 LATEST DETECTED DEADLOCK 的 hex 与 ROLL BACK
