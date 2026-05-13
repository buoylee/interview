# 事务与 MVCC

## 1. 核心问题

并发数据库面临两种竞争：**读-写**和**写-写**。锁解决写-写，但如果读也加锁，并发就垮掉了。MVCC（Multi-Version Concurrency Control）的核心价值是：**让读不阻塞写、写不阻塞读**——方法是给每行存历史版本，读时按一致性快照挑合适的版本，而不是锁住当前值。

本章解决三件事：
**(a)** ACID 四特性各自靠什么机制保证，背后的 log 是谁；
**(b)** 四种隔离级别在 MySQL 中的实际行为（特别是 RR 和 SQL 标准的偏差）；
**(c)** ReadView 的四个字段 + 可见性算法 + RR 能不能防幻读的完整答案。

---

## 2. 直觉理解

**事务 = 银行转账打包**

A 转 1000 给 B：先扣 A，再加 B。如果扣了 A 之后宕机，B 没加到——钱凭空消失了。事务就是把这两步打包成"要么都成功，要么都回滚"的原子操作。

**MVCC = 给每行建历史版本链，读时按快照挑版本**

不加锁，普通 SELECT 看到的是一张"历史照片"。每次修改不是覆盖原数据，而是在 undo log 里追加一个旧版本，用指针串成链。读操作拿到一个 ReadView（记录快照建立时的活跃事务集合），沿链往回找"在这个快照角度里应该看到的最新版本"。

形象类比：图书馆里每本书都有历史修订记录，你借阅某一天的版本，别人正在修第三章，但你看到的仍然是借阅当时的那个版本。两件事互不干扰。

---

## 3. 原理深入

### 3.1 事务 ACID 各靠什么实现

| 特性 | 中文 | 保证机制 | 关键组件 |
|---|---|---|---|
| **A**tomicity | 原子性 | 要么全做，要么全回滚 | **Undo Log**（记录回滚的逆操作；事务中断时 InnoDB 按 undo log 撤销所有修改） |
| **C**onsistency | 一致性 | 数据始终满足约束 | 约束（PK/FK/UNIQUE/CHECK）+ 其余三个特性共同保证；AID 是手段，C 是目标 |
| **I**solation | 隔离性 | 并发事务互不干扰 | **MVCC**（快照读）+ **锁**（当前读 + 写-写） |
| **D**urability | 持久性 | 提交后即使宕机也不丢 | **Redo Log**（WAL：先写 redo log，再刷脏页到磁盘；崩溃恢复时重放 redo log） |

**一个常考的追问**：Undo Log 和 Redo Log 分别在什么时候写？

- **Undo Log** 在事务执行期间每条 DML 之前写（记录"如何撤销"）。支持原子性回滚，也支持 MVCC 旧版本读。
- **Redo Log** 在事务执行中持续追加（记录"如何重做"），`fsync` 时机由 `innodb_flush_log_at_trx_commit` 控制（1 = 每次提交 fsync，最安全；0 = 每秒 fsync；2 = 写 OS 缓存每秒 fsync）。
- 两者配合：宕机重启后，先用 redo log 前滚（恢复已提交但未刷盘的页），再用 undo log 回滚（回滚未提交的事务）——这就是"先前滚后回滚"的原因。

---

### 3.2 四种隔离级别 + 异常对照表

SQL 标准定义了三种异常：

- **脏读（Dirty Read）**：读到另一个未提交事务的修改
- **不可重复读（Non-Repeatable Read）**：同一事务内两次读同一行，值不同（因为另一事务在中间提交了 UPDATE）
- **幻读（Phantom Read）**：同一事务内两次相同范围查询，行数不同（因为另一事务在中间提交了 INSERT/DELETE）

| 隔离级别 | 脏读 | 不可重复读 | 幻读 | MySQL 实现 |
|---|---|---|---|---|
| READ UNCOMMITTED (RU) | 可能 | 可能 | 可能 | 直接读最新版本，无保护 |
| READ COMMITTED (RC) | 不可能 | 可能 | 可能 | MVCC，每次查询建新 ReadView |
| REPEATABLE READ (RR) | 不可能 | 不可能 | **MySQL 中大部分场景不可能** | MVCC，第一次查询建 ReadView；+ Gap/Next-Key Lock 防当前读幻读 |
| SERIALIZABLE | 不可能 | 不可能 | 不可能 | 所有读都加共享锁，完全串行 |

**MySQL 默认隔离级别是 RR**，查看方式：

```sql
SELECT @@transaction_isolation;
-- 或
SHOW VARIABLES LIKE 'transaction_isolation';
```

**MySQL RR 和 SQL 标准 RR 的重要差别**：SQL 标准说 RR 允许幻读；MySQL 的 RR 通过 MVCC（快照读）+ Gap Lock/Next-Key Lock（当前读）大幅抑制了幻读，但不是完全等价于 SERIALIZABLE。细节见 §3.6。

---

### 3.3 行的隐藏列 + Undo Log 链

InnoDB 每行有三个隐藏列（用户看不到，但引擎内部用）：

| 隐藏列 | 大小 | 含义 |
|---|---|---|
| `DB_TRX_ID` | 6 字节 | 最后一次修改该行的事务 ID |
| `DB_ROLL_PTR` | 7 字节 | 指向 undo log 中该行上一个版本的指针（"回滚指针"） |
| `DB_ROW_ID` | 6 字节 | 无显式主键时 InnoDB 自动生成的行 ID（有显式主键时不存在） |

**Undo Log 的两种类型**：

- **Insert Undo**：INSERT 产生，只记录被插入行的主键（回滚时用来删除该行）。事务提交后可以**立即丢弃**，没有 MVCC 场景需要它（因为 INSERT 之前这行不存在，任何早于它的 ReadView 都看不到它）。
- **Update Undo**：UPDATE / DELETE 产生，记录修改前的完整行数据（包含所有列的旧值 + 旧 DB_TRX_ID）。事务提交后**不能立即丢弃**——只要存在仍然活跃的事务持有比这条 undo log 更早的 ReadView，就必须保留。由 InnoDB 的 **purge 线程**延迟清理。

**Undo Log 版本链（链表）**：

```
当前行（最新版本）
  DB_TRX_ID = 300
  DB_ROLL_PTR ──→ undo log (trx=300, 旧值: name='Alice')
                      DB_ROLL_PTR ──→ undo log (trx=150, 旧值: name='Adam')
                                          DB_ROLL_PTR ──→ undo log (trx=50, 旧值: name='A')
                                                              DB_ROLL_PTR = NULL（最初插入）
```

链是"头插"的：最新修改在链头（即行本身），最早版本在链尾。MVCC 读时从链头往尾走，找到第一个对当前 ReadView 可见的版本就停止。

**示例**：表 `accounts` 里 `id=1` 这行，经历了三次修改：

| 事务 ID | 操作 | name |
|---|---|---|
| trx=50 | INSERT | 'A' |
| trx=150 | UPDATE | 'Adam' |
| trx=300 | UPDATE | 'Alice' |

当前行 DB_TRX_ID=300，name='Alice'。undo log 链保存了 'Adam'（trx=150）和 'A'（trx=50）两个旧版本。

---

### 3.4 ReadView 四字段 + 可见性算法（伪代码）

**ReadView 是"MVCC 一致性视图"，本质是一个快照时刻的活跃事务集合 + 边界信息**。

四个字段：

| 字段 | 含义 |
|---|---|
| `m_ids` | 快照建立时所有**活跃（已开始但未提交）**的事务 ID 列表 |
| `min_trx_id` | `m_ids` 中最小的事务 ID（= 最早还未提交的事务） |
| `max_trx_id` | 快照建立时**下一个将分配的**事务 ID（即当前已分配的最大 ID + 1）。注意：不是 m_ids 中最大的，是全局计数器的下一个值 |
| `creator_trx_id` | 创建这个 ReadView 的事务自身的 ID |

**可见性判断算法**：给定一行的 `DB_TRX_ID`（记为 `record_trx_id`），判断当前事务能不能看到这个版本：

```python
def is_visible(record_trx_id, view):
    # 1. 自己写的，永远看得到
    if record_trx_id == view.creator_trx_id:
        return True

    # 2. 在快照之前就已提交（比所有活跃事务还早）
    if record_trx_id < view.min_trx_id:
        return True

    # 3. 在快照之后才开始的事务——肯定没提交
    if record_trx_id >= view.max_trx_id:
        return False

    # 4. 在 min 和 max 之间：看是否还在活跃列表里
    if record_trx_id in view.m_ids:
        return False  # 快照时还未提交，看不到

    return True  # 在范围内但已提交（快照建立前刚提交的），看得到
```

**MVCC 读取流程**：

1. 从当前行（链头，`DB_TRX_ID` 最新）开始
2. 调用 `is_visible(record_trx_id, view)`
3. 如果可见，返回这个版本
4. 如果不可见，沿 `DB_ROLL_PTR` 走到 undo log 中的上一个版本，重复步骤 2
5. 走到链尾（`DB_ROLL_PTR = NULL`）仍不可见，说明这行对当前事务不存在（比如 INSERT 在快照后发生）

---

### 3.5 快照读 vs 当前读

这是 RR 防幻读问题的根本分歧点，必须先搞清楚。

| 类型 | 触发语句 | 读取方式 | 加锁？ |
|---|---|---|---|
| **快照读（Snapshot Read）** | 普通 `SELECT` | 通过 ReadView + undo log 链读历史版本 | 不加锁 |
| **当前读（Current Read）** | `SELECT ... FOR UPDATE` / `SELECT ... FOR SHARE` / `UPDATE` / `DELETE` / `INSERT` | 直接读最新版本（binlog 和锁的语义要求看最新） | 加锁（行锁 / Gap Lock / Next-Key Lock） |

**快照读是 MVCC 的核心**，让读完全无锁，吞吐量高。当前读绕过 MVCC，直接操作最新数据，需要锁来保证一致性。

**一个直觉**：`UPDATE t SET x=x+1 WHERE id=5` 必须是当前读——如果读的是历史版本，算出来的结果是错的。所以 DML 都是当前读。

---

### 3.6 RR 能否防幻读：分快照读和当前读两种回答

这是面试最高频的考点，答案不是简单的"能"或"不能"，要分两条路：

#### 场景设置

```
accounts 表：id=1(Alice), id=2(Bob)
```

| 时间 | 事务 T1 | 事务 T2 |
|---|---|---|
| t1 | BEGIN | |
| t2 | SELECT * FROM accounts WHERE id > 0; — 看到 2 行 | |
| t3 | | BEGIN |
| t4 | | INSERT INTO accounts(id,name) VALUES(3,'Charlie'); |
| t5 | | COMMIT; |
| t6 | SELECT * FROM accounts WHERE id > 0; — **？** | |
| t7 | SELECT * FROM accounts WHERE id > 0 FOR UPDATE; — **？** | |

#### 快照读（普通 SELECT）：RR 能防幻读

- t2 时 T1 建立 ReadView，`m_ids` 记录了此刻活跃事务
- t5 时 T2 提交，trx_id=T2 的记录进入数据库，`id=3` 这行 `DB_TRX_ID=T2`
- t6 时 T1 再次执行普通 SELECT，**复用 t2 建立的同一个 ReadView**
- 可见性检查：`DB_TRX_ID(T2) >= view.max_trx_id`（T2 在快照之后开始）→ `return False` → 新行不可见
- **结论**：t6 仍然只看到 2 行，幻读被阻止

#### 当前读（SELECT ... FOR UPDATE / DML）：RR 靠锁防幻读，有漏洞

- t7 时 T1 执行 `SELECT ... FOR UPDATE`，读最新版本，**看到 3 行**（包括 T2 刚插入的 Charlie）
- 这就是幻读出现了

**Gap Lock + Next-Key Lock 的作用**：

如果 T1 在 t2 时就执行的是 `SELECT ... FOR UPDATE`（而不是普通 SELECT），InnoDB 会在相关范围加 **Next-Key Lock**（锁住 `(-∞, 1], (1, 2], (2, +∞)`）。T2 尝试插入 `id=3` 时，`(2, +∞)` 间隙锁阻塞 T2，直到 T1 提交——这样就防住了当前读的幻读。

详细锁范围和加锁规则见第 06 章（locking）。

#### 一句话总结

- **快照读（普通 SELECT）+ RR = 靠 ReadView 防幻读，同一事务复用同一 ReadView**
- **当前读（SELECT FOR UPDATE / DML）+ RR = 靠 Gap Lock / Next-Key Lock 防幻读**，如果没有加锁（比如先快照读后当前读），可能看到新行

#### 一个特殊漏洞场景

```sql
-- T1：
BEGIN;
SELECT * FROM accounts WHERE id > 0;        -- 快照读，看到 2 行，建立 ReadView
-- T2 此时 INSERT id=3 并提交
UPDATE accounts SET name = CONCAT(name, '!') WHERE id > 0; -- 当前读，更新了 3 行
SELECT * FROM accounts WHERE id > 0;        -- 快照读，但自己刚 UPDATE 了 id=3，
                                             -- creator_trx_id 匹配，**现在看到 3 行了**
```

这就是 RR 下快照读也能出现幻读的边角场景：用当前读"激活"了本不应该看到的新行，让它进入了自己的可见范围。

---

### 3.7 RC vs RR：ReadView 创建时机的差别

这是可见性行为差异的根本原因，一句话：

> **RC：每条 SELECT 语句建一个新的 ReadView**
> **RR：整个事务内第一条一致性读建 ReadView，之后复用**

| 事务行为 | RC | RR |
|---|---|---|
| T1 第一次 SELECT（ReadView 建立）| 建 ReadView-1 | 建 ReadView-1 |
| T2 提交（UPDATE id=1 的 name） | | |
| T1 第二次 SELECT | 建新 ReadView-2（能看到 T2 的提交） | 复用 ReadView-1（看不到 T2 的提交） |

**RC 下"每次查询建新 ReadView"的细节**：

ReadView 的 `m_ids` 是快照建立那一刻的活跃事务列表。RC 每次 SELECT 重新采样，如果 T2 在两次 SELECT 之间提交，第二次的 ReadView 的 `m_ids` 就不包含 T2 了，`is_visible(T2_trx_id)` 就返回 True——于是 RC 能看到其他事务已提交的修改，这正是"不可重复读"的由来。

**RR 的第一次一致性读触发时机**：

- 不是 BEGIN 的那一刻（BEGIN 不建 ReadView）
- 是**第一条快照读（普通 SELECT）执行时**才建 ReadView
- 所以如果你 `BEGIN` 之后先执行了 `UPDATE`，再执行 `SELECT`，ReadView 建立时间仍然是那条 `SELECT`

```sql
-- 演示 RR 下 ReadView 建立时机
BEGIN;
-- 此时还没有 ReadView
SELECT SLEEP(5);  -- 等待 5 秒（T2 在这期间修改了数据）
SELECT * FROM accounts;  -- 第一条一致性读，NOW 才建 ReadView
-- ReadView 建立时 T2 已提交，T2 的修改对 T1 可见
```

这个细节很重要：如果你的"事务"只是 `BEGIN; ... ; COMMIT;`，中间有个很长的 `SLEEP`，则 ReadView 建立在第一条 SELECT 时，之后该事务内的一致性读始终基于那个快照。

---

### 3.8 长事务的代价

**核心危害**：Update Undo Log 无法被 purge。

purge 线程负责清理 undo log，但有个约束：**只有当所有活跃事务的 ReadView 的 `min_trx_id` 都大于某个 undo log 的 `DB_TRX_ID` 时，那条 undo log 才能被清理**。

换句话说：有一个长事务持有非常早的 ReadView，整条 undo log 链就不能被截断。

**后果**：

| 问题 | 原因 |
|---|---|
| Undo Log 空间持续膨胀 | purge 被长事务阻塞，历史版本越堆越多 |
| 每行的版本链越来越长 | MVCC 读需要遍历更多版本，查询变慢 |
| Undo Tablespace 磁盘撑满 | 生产事故，严重时导致写入失败 |
| 持有锁时间长 | 如果长事务还持有行锁，阻塞其他事务 |

**量化感知**：生产中一个跑了 1 小时的事务，如果期间有高频 UPDATE，undo log 可能累积数百 MB 到 GB 级别，且完全无法释放，直到这个事务结束。

---

## 4. 日常开发应用

**事务边界控制**

- 事务越短越好。把业务逻辑（调 HTTP API、发 MQ、计算复杂逻辑）移到事务外面，事务内只保留最必要的 DML
- 避免在事务里等待用户输入或网络响应
- 使用 `SET innodb_lock_wait_timeout = 5`（秒）防止长时间等锁无法退出

**隔离级别选择**

- 大部分业务用默认 RR，够用
- 报表类只读查询可以切到 RC（`SET TRANSACTION ISOLATION LEVEL READ COMMITTED`），减少锁争用
- 金融/账务核心场景需要 SERIALIZABLE，或者在 RR 下显式 `SELECT ... FOR UPDATE`

**正确使用快照读和当前读**

- 需要"读后写"的场景（先查余额再扣减）**必须用当前读**，否则两个事务并发读同一快照，都看到充足余额，都扣成功，形成超卖
- `SELECT ... FOR UPDATE` 之后的操作才是安全的读-改-写

```sql
-- 正确：当前读保证看最新，同时加行锁
BEGIN;
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;
-- 此时其他事务的 SELECT FOR UPDATE 会阻塞
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
COMMIT;

-- 危险：快照读 + UPDATE 之间有并发窗口
BEGIN;
SELECT balance FROM accounts WHERE id = 1;  -- 快照读，可能读到旧值
UPDATE accounts SET balance = balance - 100 WHERE id = 1;  -- 但 UPDATE 是当前读，没问题
COMMIT;
-- 注意：上面的模式在单列 UPDATE 时实际安全（因为 UPDATE 是当前读）
-- 但如果 SELECT 的值用于业务判断（if balance > 100），则有问题
```

**显式 START TRANSACTION 而不是依赖 autocommit**

- 在代码里显式 `BEGIN` / `COMMIT` / `ROLLBACK`，比依赖 ORM 的自动提交更可控
- Spring 的 `@Transactional` 背后原理就是 `SET autocommit=0; ... COMMIT/ROLLBACK`，了解底层帮助排查事务不生效问题（比如在同一个 Bean 内部调用没有走代理）

---

## 5. 调优实战

### Case A：「用 information_schema 定位长事务」

```sql
-- 找所有运行时间超过 60 秒的活跃事务
SELECT
    trx_id,
    trx_state,
    trx_started,
    TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS duration_sec,
    trx_rows_locked,
    trx_rows_modified,
    trx_query,
    trx_mysql_thread_id
FROM information_schema.innodb_trx
WHERE TIMESTAMPDIFF(SECOND, trx_started, NOW()) > 60
ORDER BY trx_started ASC;
```

字段解读：
- `trx_rows_locked`：这个事务持有的行锁数量，高值说明可能是阻塞源头
- `trx_rows_modified`：修改了多少行，高值 + 事务时间长 = undo log 很大
- `trx_query`：当前正在执行的 SQL（可能是 NULL，说明事务没在执行查询，只是持有锁）

找到 `trx_mysql_thread_id` 后，可以 `KILL [thread_id]` 终止该事务。

### Case B：「undo log 膨胀监控」

```sql
-- 查看 undo log 占用的 tablespace 大小
SELECT
    space,
    name,
    ROW_FORMAT,
    FILE_SIZE / 1024 / 1024 AS size_mb
FROM information_schema.innodb_tablespaces
WHERE name LIKE 'innodb_undo%';

-- 查看当前 undo log purge 延迟（history list length）
SHOW ENGINE INNODB STATUS\G
-- 找 "History list length"：正常应该 < 1000，超过几万说明有长事务阻塞 purge
```

`History list length` 是 undo log 记录数量的指标，如果这个数字一直增长，说明 purge 被某个活跃 ReadView 阻塞了——找到对应的长事务并处理。

### Case C：「我以为是死锁但其实是 undo 链太长」

症状：某条 `SELECT` 越来越慢，`EXPLAIN` 显示 `rows` 很小、走了索引，但执行时间从 ms 级变成了秒级。

定位步骤：

1. 检查 `information_schema.innodb_trx`，看是否有长事务
2. 运行 `SHOW ENGINE INNODB STATUS\G`，检查 `History list length`
3. 如果 undo 链长，MVCC 读要遍历链上大量版本——每次 `SELECT` 都要从链头往尾走，找到符合 ReadView 的版本

```sql
-- 查看 MVCC 相关的 innodb metrics
SELECT
    name,
    count,
    status
FROM information_schema.innodb_metrics
WHERE name IN (
    'trx_undo_slots_used',
    'trx_undo_slots_cached',
    'purge_del_mark_records',
    'purge_upd_exist_or_extern_records'
);
```

解决方案：找到并终止长事务，让 purge 追上来；之后 undo 链会缩短，MVCC 读速度恢复正常。

### Case D：「RR 下的幻读陷阱」

场景：库存扣减，先读后扣：

```sql
-- 事务 T1（RR 隔离级别）：
BEGIN;
SELECT COUNT(*) FROM inventory WHERE product_id = 42 AND quantity > 0;  -- 快照读，返回 1
-- T2 同时 DELETE FROM inventory WHERE product_id = 42 AND quantity > 0; COMMIT;
UPDATE inventory SET quantity = quantity - 1 WHERE product_id = 42;     -- 当前读，影响 0 行
-- 数量没变，但业务以为扣成功了
COMMIT;
```

问题：SELECT 用快照读（看到库存存在），UPDATE 用当前读（库存已被删，影响 0 行），两种读模式不一致导致逻辑错误。

修复：把 SELECT 改成 `SELECT ... FOR UPDATE`，让它也是当前读，并持有锁，阻止 T2 的 DELETE。

---

## 6. 面试高频考点

### 必考：ACID 各靠什么保证

| 考题形式 | 要点 |
|---|---|
| "原子性靠什么？" | Undo Log，事务中断时逐条逆操作 |
| "持久性靠什么？" | Redo Log（WAL），fsync 后宕机数据不丢 |
| "隔离性靠什么？" | MVCC（快照读）+ 锁（当前读） |
| "一致性靠什么？" | 约束 + 其余三个特性；C 是目标，AID 是手段 |

### 必考：ReadView 创建时机（RC vs RR）

标准答案：**RC 每条 SQL 建新 ReadView；RR 第一条快照读时建 ReadView，之后整个事务复用**。这是不可重复读在 RC 中出现、在 RR 中不出现的根本原因。

注意：RR 的 ReadView 是在第一条**快照读**（普通 SELECT）时建立，不是 BEGIN 时。

### 必考：RR 能不能防幻读

分两种情况回答，缺一不可：

1. **快照读（普通 SELECT）**：能防幻读。原理是同一事务复用同一 ReadView，后来插入的行 `DB_TRX_ID >= view.max_trx_id`，`is_visible` 返回 False。
2. **当前读（SELECT FOR UPDATE / DML）**：靠 Gap Lock + Next-Key Lock，只要加锁范围覆盖了间隙，新插入就会阻塞。但如果锁范围设计不当，或者先快照读后当前读，仍可能看到新行。

### 必考：MVCC 怎么读到旧版本

完整流程：
1. 每行有 `DB_TRX_ID`（最后改它的事务 ID）和 `DB_ROLL_PTR`（指向 undo log 链）
2. 读操作持有一个 ReadView（`m_ids + min_trx_id + max_trx_id + creator_trx_id`）
3. 从当前行开始，用可见性算法判断 `DB_TRX_ID` 是否可见
4. 不可见则沿 `DB_ROLL_PTR` 回溯到 undo log 中的上一个版本，再判断
5. 找到第一个可见版本返回

### 必考：快照读 vs 当前读

| 维度 | 快照读 | 当前读 |
|---|---|---|
| 触发 | 普通 SELECT | SELECT FOR UPDATE/SHARE, UPDATE, DELETE, INSERT |
| 读哪个版本 | ReadView + undo log 决定的历史版本 | 最新版本 |
| 加锁 | 不加 | 行锁 / Gap Lock / Next-Key Lock |
| 能看到其他事务未提交的修改 | 不能 | 不能（已提交的才可见） |

### 易错点

- **`max_trx_id` 不是 m_ids 中最大的**：是全局事务 ID 计数器的下一个值（"快照建立时还没分配出去的最小 ID"）。m_ids 中的事务 ID 是已分配但未提交的，`max_trx_id` 比它们都大（或相等）。

- **BEGIN 不触发 ReadView**：RR 下 `BEGIN` 之后还没有 ReadView，第一条普通 SELECT 才建。这意味着你可以 BEGIN 之后 sleep 一段时间再 SELECT，ReadView 建立时看到的是 sleep 结束后的世界。

- **Update Undo 不能随便清**：Insert Undo 提交即清；Update Undo 需要等所有活跃 ReadView 的 `min_trx_id` 都超过它的 `DB_TRX_ID`，这是长事务危害的机制根源。

- **RR + 先快照读后当前读的陷阱**：先普通 SELECT（建 ReadView，看到 N 行）→ 其他事务 INSERT 新行并提交 → 自己 UPDATE 新行（当前读，命中了）→ 自己再普通 SELECT（ReadView 里看到自己改过的行，幻读发生）。

---

## 7. 一句话总结

MVCC 的本质是：**每行保存一条 `(DB_TRX_ID, DB_ROLL_PTR)` 的隐藏字段，修改时在 undo log 里追加旧版本；读操作用 ReadView（`m_ids + min_trx_id + max_trx_id + creator_trx_id`）的四字段可见性算法沿链回溯，找到第一个可见版本——让快照读完全无锁、写不阻塞读**。RC 每条 SELECT 建新 ReadView（所以能看到已提交修改），RR 第一条 SELECT 建一次之后复用（所以同一事务内多次读一致）。RR 防幻读：快照读靠 ReadView，当前读靠 Gap/Next-Key Lock；两者混用时有漏洞，留意先快照读后当前读的激活场景。
