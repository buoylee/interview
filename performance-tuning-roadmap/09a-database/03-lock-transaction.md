# 锁与事务

## 为什么要理解数据库锁

应用上线后，最棘手的性能问题往往不是慢查询，而是锁等待和死锁。**慢查询可以通过 EXPLAIN 定位，但锁问题是运行时行为——只在并发场景下出现，日志里看不到 SQL 本身有什么问题**。理解 InnoDB 锁机制，是处理线上并发问题的必备技能。

---

## 一、MySQL InnoDB 锁类型

### 锁分类总览

| 锁类型 | 锁粒度 | 说明 |
|--------|--------|------|
| 行锁（Record Lock） | 行 | 锁定索引中的一条记录 |
| 间隙锁（Gap Lock） | 行间间隙 | 锁定索引记录之间的间隙，防止插入 |
| 临键锁（Next-Key Lock） | 行+左间隙 | 行锁 + 间隙锁的组合，InnoDB 默认 |
| 意向锁（Intention Lock） | 表 | 表示事务将要加行级锁的意向 |
| 自增锁（AUTO-INC Lock） | 表 | 自增列插入时的特殊锁 |
| 元数据锁（MDL Lock） | 表 | DDL 与 DML 互斥 |

### 行锁（Record Lock）

```sql
-- 事务 A：锁定 id=1 的行
BEGIN;
SELECT * FROM products WHERE id = 1 FOR UPDATE;
-- 此时 id=1 被加了 X 锁（排他锁）

-- 事务 B：尝试更新同一行 → 阻塞
UPDATE products SET price = 100 WHERE id = 1;
-- 等待事务 A 释放锁...

-- 事务 B：更新其他行 → 不阻塞
UPDATE products SET price = 200 WHERE id = 2;
-- 立即执行 ✅
```

**关键点**：InnoDB 的行锁是加在**索引**上的，不是加在数据行上。如果查询没走索引，会升级为表锁。

```sql
-- 危险：没有索引的 WHERE 条件
BEGIN;
-- status 字段没有索引
UPDATE products SET price = 100 WHERE status = 'draft';
-- InnoDB 会锁住所有扫描到的行（可能是全表）！
```

### 间隙锁（Gap Lock）

在 REPEATABLE READ 隔离级别下，InnoDB 用间隙锁防止幻读。

```sql
-- 假设 products 表 category_id 索引中有值：10, 20, 30

-- 事务 A
BEGIN;
SELECT * FROM products WHERE category_id = 15 FOR UPDATE;
-- 15 不存在，但加了间隙锁，锁住 (10, 20) 这个间隙

-- 事务 B：在间隙中插入 → 阻塞
INSERT INTO products (category_id, name) VALUES (12, 'test');
-- 被间隙锁阻塞！

-- 事务 B：插入间隙外 → 不阻塞
INSERT INTO products (category_id, name) VALUES (25, 'test');
-- 立即执行 ✅
```

### 临键锁（Next-Key Lock）

InnoDB 默认的加锁方式。锁住记录本身 + 记录前面的间隙。

```sql
-- 索引中有值：10, 20, 30
-- Next-Key Lock 划分的区间：
-- (-∞, 10]
-- (10, 20]
-- (20, 30]
-- (30, +∞)

-- 事务 A
BEGIN;
SELECT * FROM products WHERE category_id = 20 FOR UPDATE;
-- 加 Next-Key Lock: (10, 20]
-- 同时还有间隙锁: (20, 30)

-- 事务 B
INSERT INTO products (category_id) VALUES (15);  -- 阻塞（在 (10, 20] 间隙中）
INSERT INTO products (category_id) VALUES (25);  -- 阻塞（在 (20, 30) 间隙中）
INSERT INTO products (category_id) VALUES (5);   -- 不阻塞 ✅
INSERT INTO products (category_id) VALUES (35);  -- 不阻塞 ✅
```

### 意向锁（Intention Lock）

表级别的锁，用于快速判断是否有行级锁存在。

```sql
-- 意向共享锁（IS）：事务准备给行加 S 锁前，先在表上加 IS
-- 意向排他锁（IX）：事务准备给行加 X 锁前，先在表上加 IX

-- 兼容矩阵
--        IS    IX    S     X
-- IS     ✅    ✅    ✅    ❌
-- IX     ✅    ✅    ❌    ❌
-- S      ✅    ❌    ✅    ❌
-- X      ❌    ❌    ❌    ❌

-- 为什么需要意向锁？
-- DDL 操作（ALTER TABLE）需要加表级 X 锁
-- 如果没有意向锁，需要遍历所有行检查是否有行锁
-- 有了意向锁，只需检查表级意向锁是否冲突
```

---

## 二、锁等待分析

### SHOW ENGINE INNODB STATUS

```sql
SHOW ENGINE INNODB STATUS\G

-- 关注 TRANSACTIONS 部分：
-- ---TRANSACTION 42156789, ACTIVE 30 sec
-- 2 lock struct(s), heap size 1136, 1 row lock(s)
-- MySQL thread id 15, OS thread handle 140234567890, query id 12345
-- UPDATE products SET price = 100 WHERE id = 1

-- 关注 LATEST DETECTED DEADLOCK 部分（如果有的话）
```

### performance_schema 锁监控

```sql
-- 查看当前等待锁的线程
SELECT
    r.trx_id AS waiting_trx_id,
    r.trx_mysql_thread_id AS waiting_thread,
    r.trx_query AS waiting_query,
    b.trx_id AS blocking_trx_id,
    b.trx_mysql_thread_id AS blocking_thread,
    b.trx_query AS blocking_query,
    b.trx_started AS blocking_started
FROM information_schema.innodb_lock_waits w
JOIN information_schema.innodb_trx b ON b.trx_id = w.blocking_trx_id
JOIN information_schema.innodb_trx r ON r.trx_id = w.requesting_trx_id;

-- MySQL 8.0 用 performance_schema
SELECT
    waiting_trx_id,
    waiting_pid,
    waiting_query,
    blocking_trx_id,
    blocking_pid,
    blocking_query,
    wait_started,
    TIMESTAMPDIFF(SECOND, wait_started, NOW()) AS wait_seconds
FROM sys.innodb_lock_waits;
```

### 查看当前持有的锁

```sql
-- MySQL 8.0
SELECT
    ENGINE_LOCK_ID,
    ENGINE_TRANSACTION_ID,
    THREAD_ID,
    OBJECT_SCHEMA,
    OBJECT_NAME,
    INDEX_NAME,
    LOCK_TYPE,
    LOCK_MODE,
    LOCK_STATUS,
    LOCK_DATA
FROM performance_schema.data_locks
WHERE OBJECT_SCHEMA = 'perfshop';

-- 示例输出：
-- +------------------+------+---------+--------+----------+---------+--------+
-- | LOCK_TYPE        | MODE | STATUS  | TABLE  | INDEX    | DATA   |
-- +------------------+------+---------+--------+----------+---------+--------+
-- | TABLE            | IX   | GRANTED | orders | NULL     | NULL    |
-- | RECORD           | X    | GRANTED | orders | PRIMARY  | 1       |
-- | RECORD           | X    | WAITING | orders | PRIMARY  | 1       |  ← 等待中
-- +------------------+------+---------+--------+----------+---------+--------+
```

### PostgreSQL 锁分析

```sql
-- 查看锁等待
SELECT
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocked_activity.query AS blocked_query,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocking_activity.query AS blocking_query,
    now() - blocked_activity.query_start AS blocked_duration
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity
    ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.relation = blocked_locks.relation
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity
    ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

---

## 三、死锁排查与日志解读

### 死锁原理

```
事务 A: 锁住行 1 → 等待行 2
事务 B: 锁住行 2 → 等待行 1
→ 循环等待 → 死锁！
```

### 开启死锁日志

```sql
-- 默认只保留最近一次死锁
SHOW ENGINE INNODB STATUS\G  -- 看 LATEST DETECTED DEADLOCK

-- 记录所有死锁到错误日志
SET GLOBAL innodb_print_all_deadlocks = ON;
```

### 死锁日志解读

```
*** (1) TRANSACTION:
TRANSACTION 42156789, ACTIVE 2 sec starting index read
mysql tables in use 1, locked 1
LOCK WAIT 3 lock struct(s), heap size 1136, 2 row lock(s)
MySQL thread id 15, OS thread handle 140234567890
*** (1) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 58 page no 4 n bits 72
  index PRIMARY of table `perfshop`.`orders`
  trx id 42156789 lock_mode X locks rec but not gap waiting
Record lock, heap no 3 PHYSICAL RECORD: n_fields 8; ...

*** (2) TRANSACTION:
TRANSACTION 42156790, ACTIVE 2 sec starting index read
mysql tables in use 1, locked 1
3 lock struct(s), heap size 1136, 2 row lock(s)
MySQL thread id 16, OS thread handle 140234567891
*** (2) HOLDS THE LOCK(S):
RECORD LOCKS space id 58 page no 4 n bits 72
  index PRIMARY of table `perfshop`.`orders`
  trx id 42156790 lock_mode X locks rec but not gap
*** (2) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 58 page no 3 n bits 80
  index PRIMARY of table `perfshop`.`products`
  trx id 42156790 lock_mode X locks rec but not gap waiting

*** WE ROLL BACK TRANSACTION (1)
```

**解读步骤**：
1. 看 `WAITING FOR THIS LOCK` 和 `HOLDS THE LOCK(S)` 确定循环等待关系
2. 看 `index` 和 `table` 确定锁在哪个表的哪个索引上
3. 看 `lock_mode` 确定锁类型（X=排他, S=共享, gap=间隙锁）
4. 看最后一行确定哪个事务被回滚

### 常见死锁场景及解决

```sql
-- 场景 1：不同顺序更新
-- 事务 A：UPDATE orders SET ... WHERE id = 1; UPDATE orders SET ... WHERE id = 2;
-- 事务 B：UPDATE orders SET ... WHERE id = 2; UPDATE orders SET ... WHERE id = 1;
-- 解决：统一按 id 升序更新

-- 场景 2：间隙锁死锁
-- 事务 A：SELECT * FROM t WHERE id = 5 FOR UPDATE; (id=5 不存在，加间隙锁)
-- 事务 B：SELECT * FROM t WHERE id = 6 FOR UPDATE; (id=6 不存在，加间隙锁)
-- 事务 A：INSERT INTO t (id) VALUES (5); -- 被 B 的间隙锁阻塞
-- 事务 B：INSERT INTO t (id) VALUES (6); -- 被 A 的间隙锁阻塞 → 死锁！
-- 解决：用 INSERT ... ON DUPLICATE KEY UPDATE 或降低隔离级别

-- 场景 3：二级索引与主键索引顺序不同
-- 事务 A：通过二级索引 idx_a 锁行（先锁二级索引再锁主键）
-- 事务 B：通过主键直接锁行
-- 解决：确保访问路径一致
```

---

## 四、事务隔离级别对性能的影响

### 四种隔离级别

| 隔离级别 | 脏读 | 不可重复读 | 幻读 | 性能 |
|---------|------|-----------|------|------|
| READ UNCOMMITTED | ✅ 可能 | ✅ 可能 | ✅ 可能 | 最好 |
| READ COMMITTED (RC) | ❌ 不会 | ✅ 可能 | ✅ 可能 | 好 |
| REPEATABLE READ (RR) | ❌ 不会 | ❌ 不会 | ❌ InnoDB 解决 | 默认 |
| SERIALIZABLE | ❌ 不会 | ❌ 不会 | ❌ 不会 | 最差 |

```sql
-- 查看当前隔离级别
SELECT @@transaction_isolation;  -- MySQL 8.0
SELECT @@tx_isolation;           -- MySQL 5.7

-- 修改隔离级别
SET GLOBAL transaction_isolation = 'READ-COMMITTED';
-- 或在 my.cnf 中配置
-- transaction-isolation = READ-COMMITTED
```

### RR vs RC 的性能差异

| 维度 | REPEATABLE READ | READ COMMITTED |
|------|----------------|----------------|
| 间隙锁 | **有**（锁范围大） | **没有**（锁范围小） |
| 死锁概率 | 较高 | 较低 |
| Undo 版本链 | 整个事务期间保持 | 每条语句可以释放 |
| 并发性能 | 较差 | 较好 |
| 幻读防护 | 有 | 没有 |

**生产建议**：互联网业务大多用 RC。阿里巴巴的 MySQL 规范推荐 READ COMMITTED + binlog_format=ROW。

---

## 五、MVCC 机制

### MVCC 工作原理

InnoDB 通过多版本并发控制（MVCC）实现非锁定读，避免读写互相阻塞。

```
每行数据有隐藏列：
- DB_TRX_ID: 最后修改该行的事务 ID
- DB_ROLL_PTR: 指向 undo log 的指针（回滚段指针）

版本链（通过 undo log 构建）：
[当前版本 trx_id=200] → [旧版本 trx_id=150] → [更旧版本 trx_id=100]

ReadView（读视图）：
- 创建时间：RR 级别在事务第一次 SELECT 时创建，RC 级别每次 SELECT 都创建新的
- m_ids: 创建 ReadView 时活跃的事务 ID 列表
- min_trx_id: 活跃事务中最小的 ID
- max_trx_id: 下一个将分配的事务 ID
- creator_trx_id: 创建该 ReadView 的事务 ID

可见性判断：
- trx_id == creator_trx_id → 可见（自己修改的）
- trx_id < min_trx_id → 可见（事务已提交）
- trx_id >= max_trx_id → 不可见（事务在 ReadView 之后开启）
- min_trx_id <= trx_id < max_trx_id → 检查是否在 m_ids 中
  - 在 m_ids 中 → 不可见（事务未提交）
  - 不在 m_ids 中 → 可见（事务已提交）
```

### MVCC 对性能的影响

```sql
-- 长事务导致 undo log 无法回收
-- 事务 A 在 10:00 开始，一直没提交
BEGIN;
SELECT * FROM products WHERE id = 1;  -- 创建了 ReadView
-- ... 忘了提交 ...

-- 10:00 之后所有其他事务对 products 的修改，undo log 都不能回收
-- 因为事务 A 的 ReadView 可能还需要读旧版本

-- 查看 undo log 积压
SHOW ENGINE INNODB STATUS\G
-- History list length 表示 undo log 未清理的记录数
-- 正常应该 < 1000，如果持续增长说明有长事务
```

---

## 六、长事务危害与检测

### 长事务的危害

| 危害 | 说明 |
|------|------|
| 锁持有时间长 | 其他事务等待超时或死锁增加 |
| Undo log 堆积 | 磁盘空间增长，ibdata1 文件膨胀 |
| MVCC 版本链过长 | 读取时需要遍历更多版本，查询变慢 |
| 主从延迟 | 大事务的 binlog 在从库回放时间长 |
| 回滚风险 | 长事务回滚可能需要很长时间 |

### 检测长事务

```sql
-- MySQL：查看运行超过 60 秒的事务
SELECT
    trx_id,
    trx_state,
    trx_started,
    TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS duration_sec,
    trx_mysql_thread_id,
    trx_query,
    trx_rows_locked,
    trx_rows_modified
FROM information_schema.innodb_trx
WHERE TIMESTAMPDIFF(SECOND, trx_started, NOW()) > 60
ORDER BY trx_started;

-- 杀掉长事务（谨慎使用）
-- KILL <trx_mysql_thread_id>;

-- PostgreSQL：查看长事务
SELECT
    pid,
    usename,
    state,
    query,
    now() - xact_start AS xact_duration,
    now() - query_start AS query_duration
FROM pg_stat_activity
WHERE state != 'idle'
  AND xact_start < now() - interval '60 seconds'
ORDER BY xact_start;
```

### 长事务告警

```sql
-- 设置锁等待超时（避免无限等待）
SET GLOBAL innodb_lock_wait_timeout = 10;  -- 默认 50 秒，建议调低

-- 设置空闲连接超时
SET GLOBAL wait_timeout = 300;             -- 5 分钟
SET GLOBAL interactive_timeout = 300;
```

在应用层配置事务超时：

```java
// Spring Boot
@Transactional(timeout = 10)  // 10 秒超时
public void processOrder(Long orderId) {
    // ...
}

// HikariCP 配置
spring.datasource.hikari.connection-timeout=5000    # 获取连接超时 5s
spring.datasource.hikari.max-lifetime=1800000       # 连接最大存活 30 分钟
```

---

## 七、锁监控指标

### 关键指标

```sql
-- 锁等待次数和时间
SHOW GLOBAL STATUS LIKE 'Innodb_row_lock%';
-- Innodb_row_lock_current_waits: 当前等待锁的数量
-- Innodb_row_lock_time: 锁等待总时间（ms）
-- Innodb_row_lock_time_avg: 平均等待时间（ms）
-- Innodb_row_lock_time_max: 最大等待时间（ms）
-- Innodb_row_lock_waits: 锁等待总次数

-- 死锁次数（需要通过 error log 统计或使用 performance_schema）
SELECT COUNT_STAR AS deadlocks
FROM performance_schema.events_errors_summary_global_by_error
WHERE ERROR_NAME = 'ER_LOCK_DEADLOCK';
```

### Prometheus 监控配置

```yaml
# mysqld_exporter 自带这些指标
# mysql_global_status_innodb_row_lock_current_waits
# mysql_global_status_innodb_row_lock_time
# mysql_global_status_innodb_row_lock_waits

# Grafana 告警规则
# 锁等待次数每分钟增量 > 10 告警
# rate(mysql_global_status_innodb_row_lock_waits[1m]) > 10

# 平均锁等待时间 > 1s 告警
# mysql_global_status_innodb_row_lock_time_avg > 1000
```

### 锁问题排查清单

| 步骤 | 操作 | 命令 |
|------|------|------|
| 1 | 确认是锁等待 | `SHOW PROCESSLIST` 看 State 列是否有 Waiting for lock |
| 2 | 找到阻塞源 | `sys.innodb_lock_waits` 查看谁阻塞谁 |
| 3 | 查看持锁事务 | `information_schema.innodb_trx` 查看事务详情 |
| 4 | 分析锁类型 | `performance_schema.data_locks` 看具体锁 |
| 5 | 检查死锁日志 | `SHOW ENGINE INNODB STATUS` 看 DEADLOCK 部分 |
| 6 | 检查慢查询 | 长时间运行的 SQL 可能持锁不放 |
| 7 | 检查事务提交 | 应用是否有未提交的事务 |
| 8 | 检查 DDL | `ALTER TABLE` 等 DDL 会加 MDL 锁 |
| 9 | 考虑降级隔离级别 | RR → RC 可以减少间隙锁 |
| 10 | 应用层优化 | 控制事务大小、统一加锁顺序 |
