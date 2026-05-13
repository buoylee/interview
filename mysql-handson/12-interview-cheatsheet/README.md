# MySQL 面试速查

> 读完 ch01-11 之后用这份扫一遍。每题: 一句话答 + 90 秒展开 + 链回章节。
> 建议: 面试前一天花 30 分钟扫完，重点看自己不熟的章节链接。

---

## 目录

1. [索引](#索引--ch03)
2. [事务与 MVCC](#事务与-mvcc--ch05)
3. [锁](#锁--ch06)
4. [日志与 Crash-Safe](#日志与-crash-safe--ch07)
5. [存储与缓存](#存储与缓存--ch02)
6. [执行 + Explain](#执行--explain--ch04)
7. [架构](#架构--ch01)
8. [SQL 调优](#sql-调优--ch08)
9. [主从复制 + HA](#主从复制--ha--ch09)
10. [分库分表](#分库分表--ch10)
11. [运维](#运维--ch11)
12. [必考综合大题](#必考综合大题)
13. [易混对比表汇总](#易混对比表汇总)

---

## 索引  (→ ch03)

### Q: 为什么 InnoDB 用 B+ 树？

**一句话**: 最小化磁盘 IO、支持范围查询，是磁盘数据库的最优树结构。

**90 秒**:
- **扇出大**: BIGINT 主键时，16 KB 页内可存约 1170 条目；三层 B+ 树可索引约 **2100 万**条记录，IO 最多 3 次
- **叶子有序双向链表**: 范围查询只需找到左端点后顺序遍历叶子，无需回根
- **内部节点只存键+指针**: 比 B 树内部节点体积更小，同页扇出更大，树更矮
- **Hash 索引**: 等值查询 O(1) 但不支持范围、前缀、ORDER BY；Memory 引擎默认用 Hash

**对比表**:

| 结构 | 等值查询 | 范围查询 | 排序 | 磁盘友好 |
|------|---------|---------|------|---------|
| B+ 树 | O(log n) | 优秀 | 优秀 | 是 |
| B 树 | O(log n) | 一般（内部节点存数据）| 差 | 是 |
| Hash | O(1) | 不支持 | 不支持 | 否 |
| 红黑树 | O(log n) | 一般 | 一般 | 否（层数深）|

→ 详见 [ch03 §3.1](../03-indexing/README.md)

---

### Q: 索引什么时候失效？

**一句话**: 破坏最左前缀、对索引列做函数/运算、类型隐式转换、优化器认为全表扫更快，索引就失效。

**90 秒**:
- **最左前缀断链**: `WHERE b=1`（跳过 a）→ 联合索引 (a,b,c) 失效
- **索引列上做函数**: `WHERE YEAR(create_time)=2024` → 改为 `create_time BETWEEN '2024-01-01' AND '2024-12-31'`
- **隐式类型转换**: 字符串列用整数比较 `WHERE phone=13800138000`（phone 是 varchar）→ MySQL 对列做转换，失效
- **LIKE 前缀通配**: `LIKE '%abc'` 失效，`LIKE 'abc%'` 有效
- **OR 两侧有非索引列**: 整条条件退化全表扫
- **优化器放弃**: 选择率太低（如 status 只有 0/1）时优化器选全表扫

**口诀**: 函数、运算、类型转、OR、最左断、低选择率。

→ 详见 [ch03](../03-indexing/README.md)

---

### Q: 联合索引顺序怎么定？

**一句话**: 区分度高的列放前面；等值查询的列放前面，范围查询的列放后面。

**90 秒**:
- **区分度原则**: `cardinality / rows` 高的列前移，走索引更精准
- **等值 > 范围**: `(user_id, create_time)` 比 `(create_time, user_id)` 更适合 `WHERE user_id=? AND create_time>?`，因为等值列用完后范围列才能继续用索引
- **覆盖索引收益**: 将 SELECT 目标列加入索引，可避免回表（例：`(user_id, status, order_id)`）
- **查询频率**: 高频查询的列组合优先建联合索引

→ 详见 [ch03](../03-indexing/README.md)

---

### Q: 覆盖索引是什么？

**一句话**: 查询所需的所有列都在索引中，无需回主键表，Extra 显示 `Using index`。

**90 秒**:
- **回表代价**: 二级索引叶子存的是主键值，回表要再做一次主键 B+ 树查询；大量回表 = 大量随机 IO
- **覆盖索引**: 索引中已包含 SELECT 所有列，直接返回，Extra=`Using index`
- **典型场景**: `SELECT id, name FROM t WHERE name='x'`，索引 `(name, id)` 可覆盖；`SELECT *` 很难覆盖
- **注意**: 覆盖索引只对二级索引有意义；主键查询天然不需要回表

→ 详见 [ch03](../03-indexing/README.md)

---

### Q: 什么是 ICP（Index Condition Pushdown）？

**一句话**: 把 WHERE 过滤下推到存储引擎层，在扫索引时就过滤，减少回表次数。

**90 秒**:
- **Without ICP**: 存储引擎把符合最左前缀的所有行返回给 Server 层，Server 层再过滤其他 WHERE 条件
- **With ICP**: 存储引擎在遍历索引时，把能用索引字段的 WHERE 条件也在引擎层判断；不满足就不回表
- **Explain 标志**: Extra 显示 `Using index condition`
- **适用**: 联合索引中非最左前缀的列，仍可在引擎层过滤（例：索引 (a,b)，WHERE a>10 AND b=5）
- **默认开启**: `optimizer_switch='index_condition_pushdown=on'`（MySQL 5.6+）

→ 详见 [ch03](../03-indexing/README.md)

---

### Q: Explain type 列 `type=index` 和 `type=range` 区别？

**一句话**: `index` 是全索引扫描（慢），`range` 是按范围扫索引（好很多）。

**90 秒**:
- **`type=index`**: 遍历整棵二级索引 B+ 树，但不回表（因为需要的列都在索引里）；比 ALL 略好，但仍是全扫
- **`type=range`**: 只扫描索引的某个范围，有明确的起止点；`>, <, BETWEEN, IN, LIKE 'abc%'` 都可触发
- **`type=ref`**: 等值匹配非唯一索引，返回多行
- **`type=eq_ref`**: JOIN 时等值匹配唯一索引，返回最多一行
- **`type=const`**: 主键或唯一索引等值查询，最多一行，优化器直接替换成常量

**速记**: `ALL < index < range < ref < eq_ref < const/system`

→ 详见 [ch04 执行与 Explain](../04-execution-and-explain/README.md)

---

## 事务与 MVCC  (→ ch05)

### Q: ACID 各靠什么实现？

**一句话**: A 靠 undo log 回滚，C 是目标靠 AID 保证，I 靠锁+MVCC，D 靠 redo log+fsync。

**90 秒**:

| 特性 | 中文 | 实现机制 |
|------|------|---------|
| Atomicity | 原子性 | undo log：事务失败时按 undo log 逐步回滚 |
| Consistency | 一致性 | 由 A/I/D 共同保障，加上约束检查（FK、唯一） |
| Isolation | 隔离性 | MVCC（快照读） + 行锁/间隙锁（当前读） |
| Durability | 持久性 | redo log WAL + `innodb_flush_log_at_trx_commit=1` + fsync |

→ 详见 [ch05](../05-mvcc-and-transaction/README.md)

---

### Q: RR（Repeatable Read）能不能防幻读？

**一句话**: 快照读下 RR 可防幻读；当前读（加锁）下需要 Next-Key Lock 才能防。

**90 秒**:
- **快照读**（普通 SELECT）：事务开始时生成 ReadView，整个事务看同一快照，新插入的行不可见 → **防幻读**
- **当前读**（SELECT ... FOR UPDATE / UPDATE / DELETE）：每次读最新版本 → 需要 Next-Key Lock 配合防止幻读
- **场景举例**: 事务 A `SELECT COUNT(*) FROM t WHERE age>18` 两次结果相同（快照读），但 `SELECT ... FOR UPDATE` 需要间隙锁防止其他事务插入
- **MySQL 默认**: InnoDB 默认隔离级别 RR，且自动加 Next-Key Lock，所以实际幻读问题极少

→ 详见 [ch05](../05-mvcc-and-transaction/README.md)

---

### Q: ReadView 怎么工作？

**一句话**: ReadView 是事务开始时（RC）或第一次快照读时（RR）生成的活跃事务快照，决定哪些版本可见。

**90 秒**:
- **4 个关键字段**:
  - `m_ids`: 生成 ReadView 时所有活跃（未提交）事务的 ID 列表
  - `min_trx_id`: m_ids 最小值
  - `max_trx_id`: 下一个待分配事务 ID（即当前最大 trx_id + 1）
  - `creator_trx_id`: 当前事务自己的 trx_id
- **可见性判断**: 对 undo log 版本链上的每个版本（trx_id = X）:
  1. `X < min_trx_id` → 已提交，**可见**
  2. `X >= max_trx_id` → 比 ReadView 更新，**不可见**
  3. `X in m_ids` → 生成时未提交，**不可见**
  4. `X not in m_ids` 且 `min <= X < max` → 生成时已提交，**可见**
- **RC vs RR**: RC 每次 SELECT 重新生成 ReadView；RR 只在事务内第一次生成，之后复用

→ 详见 [ch05](../05-mvcc-and-transaction/README.md)

---

### Q: 快照读 vs 当前读

**一句话**: 快照读走 MVCC 版本链，不加锁；当前读加锁读最新数据。

**90 秒**:

| | 快照读 | 当前读 |
|--|--------|--------|
| 语法 | 普通 `SELECT` | `SELECT ... FOR UPDATE / LOCK IN SHARE MODE`; `UPDATE`; `DELETE`; `INSERT` |
| 加锁 | 不加锁 | 加行锁 / Next-Key Lock |
| 读取版本 | MVCC 历史版本 | 最新已提交版本 |
| 幻读防护 | ReadView（RR 下） | Next-Key Lock |
| 性能 | 高（无锁竞争） | 较低（需等锁） |

→ 详见 [ch05](../05-mvcc-and-transaction/README.md)

---

### Q: 长事务的危害？

**一句话**: 长事务会导致 undo log 膨胀、锁长时间占用、主从延迟加剧，是线上故障高发点。

**90 秒**:
- **undo log 堆积**: 长事务对应的 ReadView 一直存在，其之后生成的所有 undo 版本无法 purge → ibdata1 / undo 表空间膨胀
- **锁长期占用**: 若事务中包含 DML，行锁持续到事务结束，阻塞其他写操作
- **主从延迟**: binlog 只在事务提交时写入，超大事务一次性传大量 binlog → 从库延迟
- **回滚代价大**: 长事务回滚需要 apply 大量 undo log，时间可能比正向执行更长
- **监控**: `information_schema.INNODB_TRX` 查看 `trx_started`；`performance_schema.events_transactions_current`

→ 详见 [ch05](../05-mvcc-and-transaction/README.md)

---

## 锁  (→ ch06)

### Q: 行锁、表锁、间隙锁、Next-Key Lock 区别？

**一句话**: 行锁锁具体行，表锁锁整表，间隙锁锁区间防插入，Next-Key Lock = 行锁 + 左侧间隙锁。

**90 秒**:

| 锁类型 | 锁定范围 | 目的 | 触发场景 |
|--------|---------|------|---------|
| 行锁（Record Lock）| 单行 | 并发修改隔离 | UPDATE/DELETE 命中索引 |
| 表锁 | 整张表 | DDL 保护、无索引 DML | ALTER TABLE、无索引 UPDATE |
| 间隙锁（Gap Lock）| 两行之间的区间 | 防止幻读（阻止插入）| RR 级别范围查询 |
| Next-Key Lock | 行 + 左侧间隙 | 幻读防护 | RR 级别当前读 |
| Insert Intention Lock | 插入前的间隙点 | 允许多事务并发插入不同位置 | INSERT |

- **Next-Key Lock 退化规则**（面试常考）:
  - 唯一索引等值命中存在行 → 退化为行锁
  - 唯一索引等值查不到 → 退化为间隙锁
  - 非唯一索引等值 → 保留 Next-Key Lock，加访问行的行锁

→ 详见 [ch06](../06-locking/README.md)

---

### Q: 意向锁 IS/IX 是干啥的？

**一句话**: 意向锁是表级锁，让引擎快速判断表上有无行级锁，避免逐行扫描。

**90 秒**:
- **问题**: 加表锁前需要判断表内有无行锁 → 如果没有意向锁，需要全表扫描每行
- **解法**: 事务加行锁前先在表上加意向锁（IS/IX），表锁检测时只看表级意向锁
- **IS（意向共享锁）**: 事务要对某行加 S 锁时，先对表加 IS
- **IX（意向排他锁）**: 事务要对某行加 X 锁时，先对表加 IX
- **兼容矩阵（表级）**:

| | IS | IX | S（表锁） | X（表锁） |
|--|----|----|----------|----------|
| IS | 兼容 | 兼容 | 兼容 | 冲突 |
| IX | 兼容 | 兼容 | 冲突 | 冲突 |
| S | 兼容 | 冲突 | 兼容 | 冲突 |
| X | 冲突 | 冲突 | 冲突 | 冲突 |

→ 详见 [ch06](../06-locking/README.md)

---

### Q: 怎么看死锁日志？

**一句话**: `SHOW ENGINE INNODB STATUS` 看 `LATEST DETECTED DEADLOCK` 段，找两个事务互相等待的锁。

**90 秒**:
- **命令**: `SHOW ENGINE INNODB STATUS\G` → 找 `LATEST DETECTED DEADLOCK` 部分
- **关键字段**: `TRANSACTION`（事务 ID）、`WAITING FOR THIS LOCK TO BE GRANTED`（在等什么锁）、`HOLDS THE LOCK`（持有什么锁）
- **死锁原因**: 两个事务以相反顺序加锁同一组资源，例：
  - T1: 锁 row A → 等 row B
  - T2: 锁 row B → 等 row A
- **自动检测**: InnoDB 有死锁检测（`innodb_deadlock_detect=ON`），检测到自动回滚代价小的事务
- **预防**: 统一加锁顺序、缩短事务、尽量用行锁而非表锁
- **持久化日志**: `innodb_print_all_deadlocks=ON` → 将所有死锁信息写入 error log

→ 详见 [ch06](../06-locking/README.md)

---

### Q: 索引选择对锁范围的影响？

**一句话**: 走索引则锁行，走全表扫则锁全表；索引选择直接决定锁的粒度。

**90 秒**:
- **走主键索引**: 精确锁定目标行，Next-Key Lock 范围最小
- **走二级索引**: 先锁二级索引 Next-Key，再锁主键行锁（两层锁）
- **全表扫描**: UPDATE/DELETE 无法命中索引 → 表锁（实际是对全部行加行锁，等效表锁）
- **案例**: `UPDATE t SET x=1 WHERE unindexed_col=5` → 锁全表；加索引后只锁匹配行
- **结论**: DML 语句的 WHERE 条件列必须有合适索引，否则锁范围失控

→ 详见 [ch06](../06-locking/README.md)

---

## 日志与 Crash-Safe  (→ ch07)

### Q: 为什么需要两阶段提交？

**一句话**: 保证 redo log 和 binlog 在崩溃时保持一致，防止数据和日志不同步。

**90 秒**:
- **问题背景**: redo log 是 InnoDB 内部日志，binlog 是 Server 层日志，两者独立
- **不一致场景**:
  - 写完 redo 崩溃，binlog 没写 → 主库恢复了，从库没有 → 主从不一致
  - 写完 binlog 崩溃，redo 没写 → 从库执行了，主库没有 → 数据差异
- **两阶段提交**:
  1. **Prepare 阶段**: redo log 写入并 fsync，状态标记为 prepare
  2. **Commit 阶段**: binlog 写入并 fsync，然后 redo log 标记 commit
- **崩溃恢复判断**:
  - redo prepare + binlog 完整 → 提交
  - redo prepare + binlog 不完整 → 回滚
- **MySQL 8.0 优化**: 组提交（Group Commit）减少 fsync 次数，提升吞吐

→ 详见 [ch07](../07-logs-and-crashsafe/README.md)

---

### Q: redo log vs binlog 区别？

**一句话**: redo log 是 InnoDB 物理日志保证崩溃恢复，binlog 是 Server 层逻辑日志用于复制和备份。

**90 秒**:

| | redo log | binlog |
|--|---------|--------|
| 所属层 | InnoDB 引擎层 | Server 层（所有引擎共享）|
| 日志类型 | 物理日志（页级修改）| 逻辑日志（SQL 语句 / 行变更）|
| 写入方式 | 循环写（固定大小）| 顺序追加（不断增大）|
| 用途 | Crash-Safe 恢复 | 主从复制、时间点恢复（PITR）|
| 格式 | 页号+偏移+新值 | statement / row / mixed |
| 事务 | 只记录本 InnoDB 事务 | 记录所有引擎事务 |
| 是否支持 PITR | 否 | 是（配合全量备份）|

→ 详见 [ch07](../07-logs-and-crashsafe/README.md)

---

### Q: WAL 是什么？

**一句话**: Write-Ahead Logging，先写日志再修改数据页，将随机写转为顺序写，大幅提升写性能。

**90 秒**:
- **核心思想**: 数据页的修改先记入 redo log（顺序 IO），内存中的脏页异步刷盘；宕机时用 redo 重放
- **为什么快**: 磁盘顺序写比随机写快 100x+ 以上；redo log 每次写几百字节，数据页 16 KB
- **脏页刷盘时机**: checkpoint 推进时、Buffer Pool 空间不足时、后台线程定期刷
- **Crash 恢复**: 重启后从最新 checkpoint 开始 replay redo log，保证持久性
- **关键参数**: `innodb_log_file_size`（redo log 文件大小，太小会导致频繁 checkpoint）

→ 详见 [ch07](../07-logs-and-crashsafe/README.md)

---

### Q: `innodb_flush_log_at_trx_commit` 三档？

**一句话**: 0=每秒刷，1=每次提交刷（最安全），2=提交写OS缓存每秒刷盘。

**90 秒**:

| 值 | 行为 | 数据安全 | 性能 | 适用场景 |
|---|------|---------|------|---------|
| 0 | 每秒 write+fsync | 可能丢 1 秒数据 | 最高 | 测试环境 |
| 1 | 每次提交 write+fsync | **不丢数据**（默认）| 最低 | 生产（金融级）|
| 2 | 每次提交 write，每秒 fsync | OS 崩溃丢数据 | 中等 | 允许极小概率丢失 |

- 配合 `sync_binlog=1`（每次提交 fsync binlog）才能做到完全不丢
- 主库推荐 `1+1`（innodb_flush=1, sync_binlog=1）；从库可放宽到 `2+1000`

→ 详见 [ch07](../07-logs-and-crashsafe/README.md)

---

### Q: Crash 时怎么恢复？

**一句话**: 重启时 InnoDB 从最新 checkpoint replay redo log，再用 binlog 做两阶段提交一致性校验。

**90 秒**:
- **步骤**:
  1. 找到最后一个 checkpoint LSN
  2. 从 checkpoint LSN 开始顺序 replay redo log（前滚）
  3. 对 redo log 中 prepare 状态的事务，检查对应 binlog 是否完整
     - 完整 → 提交（前滚）
     - 不完整 → 回滚（undo log 回滚）
- **undo log 作用**: 回滚未提交事务，保证原子性
- **Double Write 作用**: 防止页写到一半（partial write）导致的页损坏，先写到 doublewrite buffer 再写数据文件

→ 详见 [ch07](../07-logs-and-crashsafe/README.md)

---

## 存储与缓存  (→ ch02)

### Q: Buffer Pool 怎么工作？

**一句话**: Buffer Pool 是 InnoDB 内存池，所有读写都经过它，热页缓存在内存，减少磁盘 IO。

**90 秒**:
- **基本单位**: 数据页（16 KB），与磁盘页一一对应
- **读流程**: 先查 Buffer Pool（page cache），命中直接返回；未命中从磁盘加载到 Buffer Pool 再返回
- **写流程**: 修改 Buffer Pool 中的页（脏页），记 redo log，脏页异步刷盘
- **关键参数**: `innodb_buffer_pool_size`（建议设为物理内存 70-80%）
- **多实例**: `innodb_buffer_pool_instances`（建议 CPU 核数，减少锁竞争）
- **命中率监控**: `Innodb_buffer_pool_read_requests` / `Innodb_buffer_pool_reads`，目标 > 99%

→ 详见 [ch02](../02-innodb-storage/README.md)

---

### Q: 改良 LRU 解决了什么？

**一句话**: 防止全表扫描和预读把热数据从 Buffer Pool 中刷掉（缓存污染）。

**90 秒**:
- **传统 LRU 问题**: 全表扫描读大量冷页 → 全部进入 LRU 头部 → 把真正热的页挤出去
- **InnoDB 改良**: LRU 分为 **young 区（5/8）** 和 **old 区（3/8）**
  - 新载入的页先放 old 区头部，而非 young 区
  - old 区页在 **1 秒后**（`innodb_old_blocks_time=1000ms`）再次被访问，才升入 young 区
- **效果**: 全表扫描的页在 old 区很快被淘汰，不污染 young 区热数据
- **预读**: 线性预读/随机预读的页也先进 old 区，真正被访问才升区

→ 详见 [ch02](../02-innodb-storage/README.md)

---

### Q: Change Buffer 是干啥的？

**一句话**: 对非唯一二级索引的写操作缓存在内存，合并后再写磁盘，把随机 IO 转为顺序 IO。

**90 秒**:
- **适用条件**: 非唯一二级索引（唯一索引写入时需要判断唯一性，必须读盘）
- **原理**: 目标页不在 Buffer Pool 时，将变更记录到 Change Buffer；下次读取该页时 merge
- **收益**: 减少随机 IO；适合写多读少的场景（如日志、埋点表）
- **风险**: Change Buffer 占用 Buffer Pool，`innodb_change_buffer_max_size`（默认 25%）
- **写密集读少时收益最大**; 读多场景（每次写后立即读）merge 频繁，收益有限
- **crash 安全**: Change Buffer 的变更记录在 redo log，crash 后可恢复

→ 详见 [ch02](../02-innodb-storage/README.md)

---

### Q: Doublewrite Buffer 是干啥的？

**一句话**: 防止页写到一半时宕机导致的数据页损坏，先把脏页写到 doublewrite 区再写数据文件。

**90 秒**:
- **问题**: MySQL 页 16 KB，OS 写磁盘的原子单位通常 4 KB，断电可能只写了一半（partial page write）
- **Doublewrite 流程**:
  1. 脏页刷盘前，先顺序写入 doublewrite buffer（ibdata1 中 2 MB 连续空间）
  2. 然后再写入数据文件对应位置
- **恢复时**: 发现数据文件页损坏，从 doublewrite buffer 中恢复完整页，再 replay redo log
- **MySQL 8.0.20+**: doublewrite buffer 移到独立文件（`#ib_16384_0.dblwr`）
- **性能影响**: 顺序写开销约 5-10%，可用 `innodb_doublewrite=OFF` 关闭（不推荐生产）

→ 详见 [ch02](../02-innodb-storage/README.md)

---

## 执行 + Explain  (→ ch04)

### Q: 一条 SELECT 的完整旅程？

**一句话**: 连接器 → 查询缓存（8.0 已删）→ 分析器 → 优化器 → 执行器 → 存储引擎。

**90 秒**:

```
Client
  ↓
[连接器] 认证 + 权限检查，维护长/短连接
  ↓
[分析器] 词法分析（Token）+ 语法分析（AST）→ 语法错误在此报
  ↓
[优化器] 选择索引、JOIN 顺序、等价变换 → 生成执行计划
  ↓
[执行器] 调用引擎 API，逐行/批量读取，做 Server 层过滤
  ↓
[存储引擎] InnoDB: Buffer Pool 读写、索引查找、锁、MVCC
```

- 权限检查: 连接时检查全局权限；SQL 执行时检查表/列权限
- 8.0 移除查询缓存（`query_cache_type` 已废弃）

→ 详见 [ch04](../04-execution-and-explain/README.md) | [ch01](../01-architecture/README.md)

---

### Q: Explain type 列从慢到快？

**一句话**: ALL < index < range < index_merge < ref < eq_ref < const < system。

**90 秒**:

| type | 含义 | 场景 |
|------|------|------|
| ALL | 全表扫描 | 无索引或优化器放弃索引 |
| index | 全索引扫描 | 覆盖索引但扫全部 |
| range | 索引范围扫描 | `>`, `<`, `BETWEEN`, `IN`, `LIKE 'x%'` |
| index_merge | 多索引合并 | `OR` 条件两侧各有索引 |
| ref | 非唯一索引等值 | `WHERE indexed_col = val`，多行 |
| eq_ref | 唯一索引等值，JOIN | JOIN 时主键/唯一索引匹配 |
| const | 主键/唯一索引等值 | 最多一行，优化器常量折叠 |
| system | 单行表 | 系统表或 const 的特例 |

- **目标**: 生产 SQL 至少达到 `range`；`ALL` 必须优化

→ 详见 [ch04](../04-execution-and-explain/README.md)

---

### Q: Explain Extra 关键短语？

**一句话**: Extra 列是执行细节，`Using filesort` 和 `Using temporary` 是需要优化的信号。

**90 秒**:

| Extra 短语 | 含义 | 好/坏 |
|------------|------|-------|
| Using index | 覆盖索引，无回表 | 好 |
| Using index condition | ICP 下推过滤 | 好 |
| Using where | Server 层过滤（索引后再过滤）| 中性 |
| Using filesort | 排序无法用索引，需额外排序 | 需优化 |
| Using temporary | 用临时表（GROUP BY/DISTINCT/子查询）| 需优化 |
| Using join buffer | JOIN 无索引，用 Block Nested Loop | 需优化 |
| NULL（空）| 正常，无特殊操作 | 正常 |

→ 详见 [ch04](../04-execution-and-explain/README.md)

---

### Q: optimizer_trace 怎么用？

**一句话**: 开启后执行 SQL，查询 `information_schema.OPTIMIZER_TRACE` 表，看优化器如何选择执行计划。

**90 秒**:
```sql
SET optimizer_trace = 'enabled=on';
SELECT * FROM t WHERE ...;  -- 执行目标 SQL
SELECT * FROM information_schema.OPTIMIZER_TRACE\G
SET optimizer_trace = 'enabled=off';
```
- 关键字段: `rows_estimation`（各索引代价估算）、`considered_execution_plans`（候选计划）、`best_access_path`（最终选择）
- 代价单位: 读一页磁盘 IO cost = 1.0；内存访问 cost = 0.25（可调）
- 用途: 理解为什么优化器选了某个索引（或没选）

→ 详见 [ch04](../04-execution-and-explain/README.md)

---

### Q: MySQL 8.0 `EXPLAIN ANALYZE` 新功能？

**一句话**: 真正执行 SQL 后返回实际行数和耗时，不是估算值，用于精确诊断计划与实际的差距。

**90 秒**:
- **语法**: `EXPLAIN ANALYZE SELECT ...`（8.0.18+）
- **输出新增**: `actual time=X..Y rows=Z loops=N`（实际时间、实际行数、循环次数）
- **对比 EXPLAIN**: EXPLAIN 只给优化器估算的 `rows` 和 `filtered`；ANALYZE 给真实值
- **适用**: 排查"优化器估算行数严重偏差"导致的错误执行计划
- **注意**: ANALYZE 会真正执行 SQL（包括写操作），DML 语句慎用

→ 详见 [ch04](../04-execution-and-explain/README.md)

---

## 架构  (→ ch01)

### Q: Server 层和引擎层各有什么？

**一句话**: Server 层负责 SQL 解析/优化/执行，引擎层负责数据存储/读写/事务/锁。

**90 秒**:

| 层 | 组件 | 职责 |
|----|------|------|
| Server 层 | 连接器 | 认证、权限、连接池 |
| | 分析器 | 词法+语法分析，生成 AST |
| | 优化器 | 选执行计划（索引、JOIN 顺序）|
| | 执行器 | 调用引擎 API，结果组装 |
| | binlog | 逻辑日志，复制/备份 |
| 引擎层（InnoDB）| Buffer Pool | 内存页缓存 |
| | Change Buffer | 非唯一索引写缓存 |
| | redo log | 崩溃恢复 WAL |
| | undo log | 事务回滚、MVCC 版本链 |
| | 锁管理 | 行锁/表锁/间隙锁 |

→ 详见 [ch01](../01-architecture/README.md)

---

### Q: 长连接 vs 短连接？

**一句话**: 长连接复用 TCP，减少握手开销，但连接内存不释放会导致 OOM；短连接每次重建，开销大。

**90 秒**:
- **长连接内存问题**: 执行大查询后连接占用的内存不会释放，高并发下可能 OOM
- **解法**:
  1. 定期 `mysql_reset_connection()`（MySQL 5.7+）清理内存但不断连接
  2. 按时间/请求数主动关闭长连接重建
- **连接数上限**: `max_connections`（默认 151），超出报 "Too many connections"
- **连接池**: 中间件（ProxySQL/Vitess）维护连接池，对 MySQL 保持少量长连接，对业务复用

→ 详见 [ch01](../01-architecture/README.md)

---

### Q: Query Cache 为什么被 8.0 移除？

**一句话**: 命中率低、锁粒度粗（任意写操作使整表缓存失效）、弊大于利。

**90 秒**:
- **原理**: 以 SQL 字符串为 key，缓存结果集；完全相同的 SQL 直接返回
- **问题**:
  - 缓存粒度是表级：表上任何写操作 → 该表所有缓存失效
  - SQL 必须字节完全相同（大小写、空格都算）
  - 高并发写场景：不断失效，锁争用严重，实际是负优化
  - 现代连接池/应用层缓存（Redis）已覆盖其功能
- **移除版本**: MySQL 8.0 正式删除（5.7 已建议不用）

→ 详见 [ch01](../01-architecture/README.md)

---

## SQL 调优  (→ ch08)

### Q: 慢查日志怎么用？

**一句话**: 开启 `slow_query_log`，设 `long_query_time` 阈值，用 `pt-query-digest` 汇总分析。

**90 秒**:
```sql
SET GLOBAL slow_query_log = ON;
SET GLOBAL long_query_time = 1;           -- 超过 1 秒记录
SET GLOBAL log_queries_not_using_indexes = ON;  -- 记录未用索引的查询
SHOW VARIABLES LIKE 'slow_query_log_file';      -- 日志文件路径
```
- **分析工具**: `pt-query-digest slow.log` → 按 Query_time 汇总，找 top N 慢 SQL
- **关键指标**: `Query_time`（总耗时）、`Lock_time`（等锁时间）、`Rows_examined`（扫描行数 vs `Rows_sent` 发送行数）
- **Rows_examined / Rows_sent 比值高** → 索引选择性差，需优化

→ 详见 [ch08](../08-sql-tuning/README.md)

---

### Q: filesort 什么时候触发？

**一句话**: ORDER BY 无法利用索引顺序时触发，Extra 显示 `Using filesort`。

**90 秒**:
- **触发条件**:
  - ORDER BY 的列不在索引中
  - ORDER BY 列顺序与索引列顺序不匹配
  - ORDER BY 方向与索引方向不一致（混合 ASC/DESC，8.0 前）
  - WHERE 条件索引列与 ORDER BY 索引列不同
- **filesort 两种方式**:
  - **单路排序**: 取所有需要列放 sort_buffer，一次排序（`max_length_for_sort_data` 限制）
  - **双路排序（rowid 排序）**: 只取排序键+rowid，排完再回表取数据，两次 IO
- **优化**: 建复合索引满足 WHERE + ORDER BY；增大 `sort_buffer_size`

→ 详见 [ch08](../08-sql-tuning/README.md)

---

### Q: 临时表什么时候触发？

**一句话**: GROUP BY 列无索引、DISTINCT、子查询、UNION 等场景会触发内部临时表。

**90 秒**:
- **常见触发**:
  - `GROUP BY` 的列不在索引中，需要临时表聚合
  - `ORDER BY + GROUP BY` 列不同
  - `DISTINCT` 大结果集
  - `UNION`（非 UNION ALL）需去重
  - 子查询物化
- **内存 vs 磁盘临时表**: 先用内存（TempTable 引擎，8.0）；超过 `tmp_table_size` 转磁盘（InnoDB）
- **8.0 变化**: 默认用 TempTable 引擎替代 MEMORY 引擎，支持 BLOB/TEXT
- **优化**: 为 GROUP BY 列建索引；调大 `tmp_table_size`

→ 详见 [ch08](../08-sql-tuning/README.md)

---

### Q: LIMIT 深翻页怎么优化？

**一句话**: 用"书签法"（WHERE id > last_id）替代 OFFSET，避免扫描丢弃大量行。

**90 秒**:
- **问题**: `LIMIT 100000, 10` → 扫描并丢弃 10 万行，只返回 10 行，极慢
- **方案一（书签法）**: `WHERE id > :last_seen_id ORDER BY id LIMIT 10`，每次从上次末尾继续
- **方案二（延迟关联）**: 先只查主键，再 JOIN 回原表取数据
  ```sql
  SELECT t.* FROM t
  JOIN (SELECT id FROM t ORDER BY create_time LIMIT 100000, 10) tmp
  ON t.id = tmp.id;
  ```
- **方案三**: 业务上限制最大翻页深度（如搜索引擎只展示前 1000 页）

→ 详见 [ch08](../08-sql-tuning/README.md)

---

### Q: COUNT(*) 大表怎么优化？

**一句话**: InnoDB COUNT(*) 全表扫（无法像 MyISAM 直接返回行数），可用二级索引覆盖扫或缓存计数。

**90 秒**:
- **MyISAM vs InnoDB**: MyISAM 维护精确行数，COUNT(*) O(1)；InnoDB 因 MVCC 每次需扫描
- **InnoDB 优化点**: 优化器会选择最小的二级索引（而非主键）做覆盖扫描，相对快一点
- **应用层方案**:
  - Redis 维护计数器，写操作同步 +1/-1
  - 独立计数表，行级锁比全局锁开销小
- **近似方案**: `EXPLAIN SELECT COUNT(*) FROM t` → `rows` 列是估算值（误差 5-20%）
- **`COUNT(1)` vs `COUNT(*)` vs `COUNT(col)`**: `COUNT(*)`=`COUNT(1)` 等价，性能相同；`COUNT(col)` 不计 NULL，语义不同

→ 详见 [ch08](../08-sql-tuning/README.md)

---

### Q: JOIN 怎么选驱动表？

**一句话**: 小结果集作驱动表（外层），被驱动表有索引；优化器会自动选，可用 STRAIGHT_JOIN 强制。

**90 秒**:
- **Nested Loop Join**: 驱动表每行 → 在被驱动表找匹配行；被驱动表无索引 = 内层全表扫 → O(m×n)
- **驱动表选择原则**: WHERE 过滤后**结果集最小**的表作驱动表（减少外层循环次数）
- **被驱动表必须有索引**: 否则触发 Block Nested Loop（BNL），大量内存 IO
- **Hash Join（8.0.18+）**: 被驱动表无索引时，优化器改用 Hash Join（构建 hash 表），比 BNL 快
- **强制顺序**: `SELECT STRAIGHT_JOIN ...` 按 FROM 后表顺序固定驱动表

→ 详见 [ch08](../08-sql-tuning/README.md)

---

## 主从复制 + HA  (→ ch09)

### Q: 主从复制三大线程？

**一句话**: 主库 binlog dump 线程推日志，从库 IO 线程接收写 relay log，从库 SQL 线程回放。

**90 秒**:

| 线程 | 所在节点 | 职责 |
|------|---------|------|
| binlog dump thread | 主库 | 读取 binlog，推送给从库 IO 线程 |
| IO thread | 从库 | 接收主库 binlog，写入 relay log |
| SQL thread（单线程）| 从库 | 读 relay log，顺序回放 SQL |
| coordinator + worker（并行复制）| 从库 | 多线程并行回放，减少延迟 |

- **MySQL 5.7+ 并行复制**: `slave_parallel_type=LOGICAL_CLOCK`，按提交时间戳并行
- **MySQL 8.0**: 默认 `LOGICAL_CLOCK`，`slave_parallel_workers` 建议 4-16

→ 详见 [ch09](../09-replication-and-ha/README.md)

---

### Q: 异步 / 半同步 / MGR 区别？

**一句话**: 异步最快但可能丢数据，半同步等至少一从确认，MGR 是 Paxos 多主强一致。

**90 秒**:

| 方案 | 一致性 | 性能 | 可用性 | 适用场景 |
|------|--------|------|--------|---------|
| 异步复制 | 可能丢数据 | 最高 | 主故障从可能缺数据 | 对一致性要求低 |
| 半同步（rpl_semi_sync）| 至少 1 从持久化 | 较高（网络延迟影响）| 故障转移安全 | 金融业务 |
| MGR（Group Replication）| 强一致（Paxos）| 中等（消息投票延迟）| 自动选主，多主可写 | 高可用 + 强一致 |
| InnoDB Cluster | 强一致 + 自动 HA | 中等 | 内置故障转移 | 一体化方案 |

- **半同步超时**: 等从确认超时后退化为异步（`rpl_semi_sync_master_timeout`）
- **MGR 限制**: 不支持某些 DDL 并发；事务需要有主键；网络延迟影响写性能

→ 详见 [ch09](../09-replication-and-ha/README.md)

---

### Q: 主从延迟怎么定位？

**一句话**: `SHOW SLAVE STATUS` 看 `Seconds_Behind_Master`，再结合 binlog 位点、慢 SQL、从库并行度排查。

**90 秒**:
- **`Seconds_Behind_Master`**: SQL thread 处理时间与 IO thread 接收时间的差值，不完全准确
- **精确方案**: 对比主从当前 binlog 位点差（字节数）或 GTID 差距
- **常见原因**:
  1. 从库单线程回放跑不过主库并发写（→ 开并行复制）
  2. 从库有大事务（单条 SQL 跑很久）
  3. 从库上有慢查询/大表扫（被查询拖慢）
  4. 主库写入量突增（导入数据、批量删除）
- **监控**: `performance_schema.replication_applier_status_by_worker` 查各 worker 延迟
- **应急**: 停止从库非核心查询、增加 worker 数、在从库建缺失索引

→ 详见 [ch09](../09-replication-and-ha/README.md)

---

### Q: GTID vs 位点复制？

**一句话**: 位点复制依赖 binlog 文件名+偏移，切主时需人工计算；GTID 用全局唯一事务 ID，自动定位，切主更安全。

**90 秒**:
- **传统位点**: `CHANGE MASTER TO MASTER_LOG_FILE='bin.000003', MASTER_LOG_POS=1234`
  - 故障切主时需要从备机日志反向推算位点，容易出错
- **GTID**: `server_uuid:transaction_id`，如 `3E11FA47-71CA-11E1-9E33-C80AA9429562:23`
  - 每个事务 ID 全局唯一；从库已执行的 GTID 集合 `gtid_executed` 自动去重
  - 切主：`CHANGE MASTER TO MASTER_AUTO_POSITION=1`，从库自动协商缺失事务
- **限制**: GTID 模式下不能在事务中执行非事务 DDL + DML 混用；binlog_format 建议 ROW

→ 详见 [ch09](../09-replication-and-ha/README.md)

---

### Q: 读写分离写后立即读问题？

**一句话**: 写主库后立即读从库可能读到旧数据（从库延迟），需判断延迟或强制读主库。

**90 秒**:
- **场景**: 用户注册后立即查自己的信息 → 查从库未同步 → 404
- **方案**:
  1. **强制走主库**: 写操作后的 N 秒内同一会话读主库（session 打标记）
  2. **等待从库追上**: 写完获取 binlog 位点，读时 `SELECT MASTER_POS_WAIT(file, pos, timeout)` 等从库追上
  3. **GTID 方案**: 写完拿到 GTID，读时 `WAIT_FOR_EXECUTED_GTID_SET(gtid, timeout)`
  4. **业务层缓存**: 写后更新 Redis，短期读 Redis 而非 DB
- **中间件支持**: ProxySQL 可配置 `mysql-wait_timeout_on_master_after_write` 自动处理

→ 详见 [ch09](../09-replication-and-ha/README.md)

---

## 分库分表  (→ ch10)

### Q: 何时需要分库分表？

**一句话**: 单表超过 2000 万行、单库 QPS 超过硬件极限、磁盘空间不足，才考虑分。

**90 秒**:
- **先做的事**（分库分表前必须做完）:
  1. 索引优化 + SQL 调优
  2. 读写分离（从库承接读流量）
  3. 缓存层（Redis 降低 DB 读压力）
  4. 归档历史数据（冷热分离）
- **分的阈值（经验值）**:
  - 单表 > 2000 万行，查询开始变慢
  - 单库写 QPS > 5000（受磁盘/CPU 限制）
- **分的代价**: 无法跨分片 JOIN、事务变分布式事务、全局 ID 复杂、运维成本高

→ 详见 [ch10](../10-sharding-and-scaling/README.md)

---

### Q: 全局 ID 几种方案？

**一句话**: UUID/数据库自增/雪花算法/号段模式，各有取舍，雪花算法是生产最常用。

**90 秒**:

| 方案 | 优点 | 缺点 |
|------|------|------|
| MySQL 自增（auto_increment）| 简单 | 单点、分库后重复 |
| UUID | 无中心 | 无序，索引性能差，存储大 |
| 雪花算法（Snowflake）| 趋势递增、高性能、无中心 | 时钟回拨问题，需机器 ID 分配 |
| 号段模式（美团 Leaf）| 趋势递增、批量获取减少 DB 访问 | 号段用完时短暂阻塞 |
| Redis INCR | 高性能 | Redis 持久化风险、单点 |

- **雪花算法结构**: 1 bit 符号 + 41 bit 时间戳 + 10 bit 机器 ID + 12 bit 序列号 → 69 年不重复，每毫秒 4096 个

→ 详见 [ch10](../10-sharding-and-scaling/README.md)

---

### Q: 跨库 JOIN 怎么处理？

**一句话**: 跨库 JOIN 无法原生支持，通过字段冗余、全局广播表、应用层 JOIN 或搜索引擎解决。

**90 秒**:
- **方案一（字段冗余）**: 把 JOIN 所需的列存入本表（反范式），用空间换 JOIN
- **方案二（广播表）**: 字典表/配置表在每个分片都保留全量数据，本地 JOIN
- **方案三（应用层 JOIN）**: 分别查两个分片，在应用代码里做内存 JOIN（适合小结果集）
- **方案四（数据中台/搜索引擎）**: 将需要复杂查询的数据同步到 ES/ClickHouse，由 ES 做 JOIN

→ 详见 [ch10](../10-sharding-and-scaling/README.md)

---

### Q: 在线迁移 SOP？

**一句话**: 双写 + 数据同步 + 灰度切读 + 切写 + 验证下线老库，整个过程不停服。

**90 秒**:
```
Phase 1: 全量迁移
  mysqldump / DTS 全量导入新库

Phase 2: 增量同步
  Canal / DTS 监听 binlog 实时同步增量
  直到主从延迟 < 1s

Phase 3: 双写
  应用代码同时写老库 + 新库
  新库读取比例从 0% 逐步提升

Phase 4: 灰度切读
  5% → 10% → 50% → 100% 读新库
  监控错误率和延迟

Phase 5: 切写
  停止写老库，只写新库
  确认新库数据一致

Phase 6: 验证下线
  数据对比工具验证一致性
  保留老库 N 天后下线
```

→ 详见 [ch10](../10-sharding-and-scaling/README.md)

---

## 运维  (→ ch11)

### Q: Online DDL 三算法？

**一句话**: INSTANT 不改表只改元数据（最快），INPLACE 在原表操作（可并发 DML），COPY 建临时表（阻塞写）。

**90 秒**:

| 算法 | 原理 | 阻塞写 | 速度 | 支持操作 |
|------|------|--------|------|---------|
| INSTANT（8.0+）| 只改数据字典（frm/ibd 元数据）| 否 | 毫秒级 | 加列（末尾）、修改默认值、重命名列 |
| INPLACE | 在原始 ibd 文件内操作 | 否（允许并发 DML）| 分钟级 | 加索引、改列长度（部分）|
| COPY | 创建临时表，全量复制，rename | 是（阻塞写）| 最慢 | 改列类型、改字符集 |

- **指定算法**: `ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT`
- **锁级别**: `LOCK=NONE/SHARED/EXCLUSIVE`（配合 ALGORITHM 使用）
- **INSTANT 限制**: 只能在表末尾加列（MySQL 8.0.29 之前），不支持加到任意位置

→ 详见 [ch11](../11-ops-and-troubleshooting/README.md)

---

### Q: pt-osc 原理？

**一句话**: 创建影子表，触发器同步增量，分批复制全量，原子 rename 替换，全程不锁原表。

**90 秒**:
```
1. 创建影子表 _t_new（目标结构）
2. 在原表添加 AFTER INSERT/UPDATE/DELETE 触发器，同步变更到 _t_new
3. 分批 INSERT INTO _t_new SELECT ... FROM t（chunk by chunk）
4. 等待主从延迟 < 阈值
5. RENAME TABLE t TO _t_old, _t_new TO t（原子操作）
6. 删除触发器，删除 _t_old
```
- **优点**: 全程不阻塞读写；可暂停（根据 `--max-load` 自动限速）
- **缺点**: 触发器有性能开销；需要额外磁盘空间；不适合频繁触发的表
- **替代方案**: MySQL 8.0 INSTANT 算法（能用 INSTANT 就不用 pt-osc）
- **类似工具**: `gh-ost`（GitHub），不用触发器，直接解析 binlog，开销更小

→ 详见 [ch11](../11-ops-and-troubleshooting/README.md)

---

### Q: 备份方案怎么选？

**一句话**: 物理备份（xtrabackup）适合大库，逻辑备份（mysqldump）适合小库或跨版本迁移。

**90 秒**:

| 方案 | 原理 | 备份速度 | 恢复速度 | 适用场景 |
|------|------|---------|---------|---------|
| mysqldump | 导出 SQL 文件 | 慢（逐行 SELECT）| 慢（重放 SQL）| 小库（< 10 GB）、跨版本 |
| mysqlpump | 并行 mysqldump | 较快 | 慢 | 中小库 |
| xtrabackup | 物理拷贝 ibd 文件 + binlog | 快 | 快 | 大库（> 10 GB）生产 |
| mydumper/myloader | 并行逻辑备份 | 快 | 快 | 中大库 |
| 云快照 | 存储层快照 | 秒级 | 秒级 | 云环境（RDS/Aurora）|

- **恢复流程（xtrabackup）**: `xtrabackup --backup` → `xtrabackup --prepare` → 复制数据目录 → 启动
- **PITR**: 全量备份 + binlog 重放（`mysqlbinlog`）

→ 详见 [ch11](../11-ops-and-troubleshooting/README.md)

---

### Q: 关键参数调优清单？

**一句话**: 最影响性能的 10 个参数，重点是 Buffer Pool、redo log、连接数、并行度。

**90 秒**:

| 参数 | 建议值 | 说明 |
|------|--------|------|
| `innodb_buffer_pool_size` | 物理内存 70-80% | 最重要参数，尽量大 |
| `innodb_buffer_pool_instances` | CPU 核数 | 减少锁争用 |
| `innodb_log_file_size` | 1-4 GB | 太小会频繁 checkpoint，影响写性能 |
| `innodb_flush_log_at_trx_commit` | 1（生产）| 0/2 可提升性能但有丢数据风险 |
| `sync_binlog` | 1（生产）| 配合上一参数 |
| `max_connections` | 500-1000 | 按实际连接数调，太大浪费内存 |
| `innodb_io_capacity` | SSD: 2000-4000 | 后台刷新 IO 上限 |
| `slave_parallel_workers` | 4-16 | 从库并行回放 worker 数 |
| `tmp_table_size` / `max_heap_table_size` | 256 MB | 减少磁盘临时表 |
| `join_buffer_size` | 256 KB-1 MB | BNL JOIN 缓冲，别设太大（per-session）|

→ 详见 [ch11](../11-ops-and-troubleshooting/README.md)

---

## 必考综合大题

### "聊聊 MySQL 整体架构"（10 分钟答法）

**结构化答题框架**:

```
① Server 层（2 分钟）
   连接器 → 分析器 → 优化器 → 执行器
   binlog（逻辑日志，复制+备份）

② 引擎层 InnoDB（3 分钟）
   Buffer Pool（内存核心）
   Change Buffer（非唯一索引写优化）
   redo log（WAL，crash-safe）
   undo log（回滚+MVCC版本链）

③ 一条 SQL 的旅程（2 分钟）
   连接器认证 → 分析器解析 → 优化器选计划
   → 执行器调引擎 API → Buffer Pool 读写
   → redo log WAL → 脏页异步刷盘

④ 三日志协同（2 分钟）
   redo log: 物理日志，循环写，crash恢复
   binlog: 逻辑日志，追加写，复制+PITR
   两阶段提交保证 redo/binlog 一致性
   undo log: 回滚+MVCC

⑤ 主从复制（1 分钟）
   binlog dump → relay log → SQL thread 回放
   异步/半同步/MGR 可选
```

**加分点**: 主动提 Buffer Pool 改良 LRU 防污染、ICP 减少回表、GTID 切主更安全。

---

### "怎么定位一条慢 SQL"（5 分钟答法）

**结构化答题框架**:

```
Step 1: 发现问题
  慢查日志（slow_query_log）或 APM 监控告警
  pt-query-digest 汇总 top N 慢 SQL

Step 2: 分析执行计划
  EXPLAIN → 看 type（是否 ALL/index）
           → 看 rows（估算扫描行数）
           → 看 Extra（filesort/temporary）
           → 看 key（是否用到索引）

Step 3: 深入分析
  EXPLAIN ANALYZE（8.0）对比实际 vs 估算
  optimizer_trace 看优化器决策
  SHOW PROFILE 看各阶段耗时

Step 4: 看锁等待
  SHOW ENGINE INNODB STATUS → 看锁等待
  information_schema.INNODB_TRX 看长事务
  performance_schema.events_waits_current

Step 5: 看主从延迟
  SHOW SLAVE STATUS → Seconds_Behind_Master
  确认是否查的是延迟从库

Step 6: 优化方向
  加/改索引（覆盖索引、联合索引）
  改写 SQL（避免函数、改 LIMIT 翻页）
  参数调优（sort_buffer_size、join_buffer_size）
```

---

### "MySQL 高可用方案对比"（3 分钟答法）

**从低到高成本+一致性排列**:

| 方案 | 架构 | 故障恢复 | 数据安全 | 成本 |
|------|------|---------|---------|------|
| 单机 | 无冗余 | 手动恢复 | 最低 | 最低 |
| 主从异步 | 1主N从 | 手动切主（MHA）| 可能丢数据 | 低 |
| 主从半同步 | 1主N从 | MHA/Orchestrator | 至少1从持久化 | 中 |
| MGR/InnoDB Cluster | 3+ 节点 | 自动选主（秒级）| Paxos 强一致 | 中高 |
| 分库分表 | 多分片+从库 | 分片级 HA | 高 | 高 |
| 云原生（Aurora/PolarDB）| 共享存储 | 秒级自动切换 | 多副本 | 按用量 |

**面试加分**: 说明实际选型时的决策因素：RTO（恢复时间）、RPO（允许丢多少数据）、成本、运维能力。

---

## 易混对比表汇总

### 聚簇索引 vs 二级索引

| | 聚簇索引（主键）| 二级索引 |
|--|-------------|---------|
| 叶子节点存什么 | 完整行数据 | 主键值 |
| 数量 | 每表只有 1 个 | 可有多个 |
| 回表 | 不需要 | 需要（除非覆盖索引）|
| 顺序 | 按主键物理有序 | 按索引键有序 |
| 大小 | 较大 | 较小 |

---

### 行锁 vs 表锁

| | 行锁 | 表锁 |
|--|------|------|
| 粒度 | 单行 | 整表 |
| 并发 | 高 | 低 |
| 开销 | 高（需维护锁结构）| 低 |
| 死锁 | 可能 | 不会 |
| 触发 | DML 命中索引 | DDL、无索引 DML |

---

### redo log vs binlog vs undo log

| | redo log | binlog | undo log |
|--|---------|--------|---------|
| 所属 | InnoDB 引擎 | Server 层 | InnoDB 引擎 |
| 内容 | 物理修改（页内变化）| 逻辑操作（SQL/行镜像）| 逆向操作（回滚用）|
| 用途 | Crash 恢复 | 复制 + PITR | 回滚 + MVCC |
| 写方式 | 循环覆盖写 | 顺序追加 | 按需分配，purge 回收 |
| 大小 | 固定（可配）| 持续增长 | 动态（长事务会膨胀）|
| 时机 | 事务执行中实时写 | 事务提交时写 | 事务执行中实时写 |

---

### 异步 vs 半同步 vs MGR

| | 异步 | 半同步 | MGR |
|--|------|--------|-----|
| 提交返回时机 | 写主库即返回 | 至少 1 从 ACK | Paxos 多数节点同意 |
| 数据安全 | 可能丢 | 丢数据风险极低 | 不丢（强一致）|
| 写性能 | 最高 | 受网络延迟影响 | 最低（投票延迟）|
| 自动切主 | 否（需工具）| 否（需工具）| 是（内置）|
| 复杂度 | 低 | 中 | 高 |

---

### INSTANT vs INPLACE vs COPY（DDL 算法）

| | INSTANT | INPLACE | COPY |
|--|---------|---------|------|
| 原理 | 改元数据 | 原地重建 | 复制整表 |
| 阻塞 DML | 否 | 否（大多数）| 是 |
| 磁盘空间 | 无额外 | 少量 | 需一倍空间 |
| 速度 | 毫秒 | 按表大小 | 最慢 |
| 支持范围 | 加列（末尾）等 | 加索引、部分列变更 | 所有 DDL |

---

### statement vs row vs mixed（binlog 格式）

| | statement | row | mixed |
|--|-----------|-----|-------|
| 记录内容 | SQL 原文 | 每行变更前后镜像 | 混合选择 |
| 日志大小 | 小 | 大（批量改行数多时）| 中 |
| 一致性 | 不确定（NOW()等不确定函数）| 高 | 中 |
| 主从一致 | 可能不一致 | 一致 | 基本一致 |
| PITR 精度 | 低 | 高 | 中 |
| 推荐 | 不推荐 | **生产推荐** | 过渡用 |

---

### RC vs RR（隔离级别）

| | READ COMMITTED | REPEATABLE READ |
|--|---------------|-----------------|
| 脏读 | 否 | 否 |
| 不可重复读 | 有 | 否 |
| 幻读（快照读）| 否（每次新 ReadView）| 否（ReadView 复用）|
| 幻读（当前读）| 有 | 否（Next-Key Lock）|
| ReadView 生成 | 每个 SELECT 生成 | 事务内第一个 SELECT 生成 |
| MySQL 默认 | 否 | **是** |
| 性能 | 略高（锁更少）| 略低 |

---

> **最后提示**: 面试时主动引出"我们线上遇到过类似问题"的经历，结合具体数字（表大小、QPS、延迟毫秒数）会让答案更有说服力。
