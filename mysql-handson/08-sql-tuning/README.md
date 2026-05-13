# SQL 调优实战

## 1. 核心问题

SQL 写完能跑，不等于跑得快。本章解决四件事：
**(a)** 慢 SQL 上线后怎么发现、怎么定位；
**(b)** JOIN / ORDER BY / GROUP BY 背后发生了什么，为什么有时候奇慢；
**(c)** 什么场景会产生临时表和 filesort，怎么消除；
**(d)** 深翻页和大表 COUNT 这两个「经典坑」的根本原因和标准解法。

---

## 2. 直觉理解

想象你是一个图书管理员，有人递给你一张单子说「帮我找出 2023 年出版、按销量排名第 100000 到 100020 的书」。

**没优化前的做法**：从第一本书开始，把所有 2023 年出版的书按销量排成一排，数到第 100000 本，再取 20 本。你翻了 100020 本书，只用了最后 20 本。

**优化后**：先只看销量目录（覆盖索引），从目录里数到第 100000 条，记下书号（主键），只用书号去仓库拿 20 本实体书。目录翻了 100000 行，但仓库只跑了 20 次。

这个图书馆类比贯穿本章：
- 索引 = 各种排序目录
- 回表 = 去仓库拿实体书
- filesort = 临时把书按某种顺序重新排一遍
- 临时表 = 在地板上堆了一大摊中间结果

---

## 3. 原理深入

### 3.1 慢查日志：从开到读

#### 开启与参数

MySQL 慢查日志有三个核心参数：

```sql
-- 查看当前状态
SHOW VARIABLES LIKE 'slow_query%';
SHOW VARIABLES LIKE 'long_query_time';
SHOW VARIABLES LIKE 'log_queries_not_using_indexes';

-- 动态开启（重启失效，生产推荐写入 my.cnf）
SET GLOBAL slow_query_log = ON;
SET GLOBAL long_query_time = 1;           -- 超过 1 秒记录（默认 10s，生产通常调到 0.5 或 1）
SET GLOBAL log_queries_not_using_indexes = ON;  -- 没走索引的也记（开发环境用，生产慎重——量大）
SET GLOBAL slow_query_log_file = '/var/log/mysql/slow.log';
```

**long_query_time 的坑**：它是 wall clock 时间，包含锁等待。一条 SQL 自身逻辑只要 10ms，但等锁等了 2s，也会进慢查日志。定位时要结合 `Lock_time` 字段区分。

#### 慢查日志格式解读

```
# Time: 2026-05-13T10:23:45.123456Z
# User@Host: app[app] @ localhost []  Id: 1024
# Query_time: 3.456789  Lock_time: 0.001234  Rows_sent: 20  Rows_examined: 1024000
# Bytes_sent: 4096
SET timestamp=1747132425;
SELECT o.* FROM orders o WHERE user_id = 100 ORDER BY created_at LIMIT 100000, 20;
```

关键字段：
- `Query_time`：总耗时（含锁等待）
- `Lock_time`：锁等待时间。Lock_time 远小于 Query_time → 慢在执行，不是锁
- `Rows_examined`：引擎扫描了多少行。`1024000` 行只返回 `20` 行 → 典型的索引缺失或深翻页
- `Rows_sent`：最终返给客户端的行数

**Rows_examined / Rows_sent 的比值是第一个报警指标**。比值 > 1000 往往意味着有问题。

#### 用工具聚合

生产环境慢查日志几分钟就能产生几十 MB，手动 grep 不现实。

```bash
# mysqldumpslow — MySQL 自带，按执行次数或总耗时聚合，粗用
mysqldumpslow -s t -t 10 /var/log/mysql/slow.log
# -s t：按总耗时排序；-t 10：取 Top 10

# pt-query-digest — Percona 出品，更强，能输出 fingerprint + 百分位耗时
pt-query-digest /var/log/mysql/slow.log \
  --order-by Query_time:sum \
  --limit 10 \
  > digest.txt
```

`pt-query-digest` 输出片段示例：

```
# Rank Query ID           Response time  Calls  R/Call V/M   Item
# ==== ================== ============== ====== ====== ===== ====
#    1 0xABCD1234ABCD1234  1234.5678 38.2% 50234  0.0246 0.18  SELECT orders
```

- `Calls`：这条 fingerprint（参数化后的 SQL）被执行了多少次
- `Response time`：占总慢查耗时的比例
- 先优化 **Rank 1**（通常是高频 + 高耗时的组合，性价比最高）

---

### 3.2 performance_schema top SQL 法

不想动慢查日志（或者 `long_query_time` 调高了漏掉了中等慢查），可以用 `performance_schema`：

```sql
-- 开启（5.7+ 默认开；如关了执行）
UPDATE performance_schema.setup_consumers
SET ENABLED = 'YES'
WHERE NAME = 'events_statements_history_long';

-- 查 Top 10 按总耗时
SELECT
    SCHEMA_NAME,
    DIGEST_TEXT,
    COUNT_STAR                        AS calls,
    ROUND(SUM_TIMER_WAIT / 1e12, 3)   AS total_sec,
    ROUND(AVG_TIMER_WAIT / 1e12, 6)   AS avg_sec,
    SUM_ROWS_EXAMINED,
    SUM_ROWS_SENT,
    SUM_NO_INDEX_USED                 AS no_index_calls,
    FIRST_SEEN,
    LAST_SEEN
FROM performance_schema.events_statements_summary_by_digest
WHERE SCHEMA_NAME = 'your_db'
ORDER BY total_sec DESC
LIMIT 10;
```

关键列解读：
- `SUM_NO_INDEX_USED`：这条 SQL 有多少次执行没走索引。非零就要警惕
- `SUM_ROWS_EXAMINED / SUM_ROWS_SENT`：同慢查日志，比值大 = 扫描浪费
- `DIGEST_TEXT`：参数化后的 SQL（具体值被 `?` 替代），方便聚合

对比慢查日志的优势：
- 不需要设 `long_query_time`，所有执行过的 SQL 都有记录
- 实时更新，不依赖文件 IO
- 记录了 `SUM_CREATED_TMP_TABLES`、`SUM_SORT_MERGE_PASSES` 等细节指标

---

### 3.3 JOIN 算法演进（BNL / Hash Join）+ 驱动表

#### MySQL JOIN 的三代算法

**第一代：Simple Nested-Loop（已淘汰）**

伪代码：
```
for each row r1 in outer_table:
    for each row r2 in inner_table:
        if r1.col = r2.col: output(r1, r2)
```
内表 N 行，外表 M 行 → M × N 次比较。没有任何缓冲，是最朴素的实现。

**第二代：Block Nested-Loop（BNL，8.0.20 前的无索引 JOIN）**

MySQL 8.0.20 前，**当 JOIN 条件列没有索引时**，用 BNL：

```
for each block of rows from outer_table (join_buffer_size, default 256KB):
    load block into join_buffer
    scan inner_table once, match against entire buffer
```

关键参数：`join_buffer_size`（默认 256KB，会话级可调）。内表扫描次数 = `ceil(outer_rows / join_buffer_rows)`，远比 SNL 少，但内表依然全扫。

EXPLAIN Extra 出现 `Using join buffer (Block Nested Loop)` 即走 BNL，**说明 JOIN 列没有索引，要加**。

**第三代：Hash Join（8.0.18+，8.0.20 完全替换 BNL）**

```
-- Build phase：把小表（build side）的 JOIN 列 hash 到 hash_table（在 join_buffer 里）
-- Probe phase：扫大表（probe side），每行用 hash 函数查 hash_table
```

Hash Join 的条件：
1. 等值 JOIN（`=`，不支持 `>` / `<` / `BETWEEN`）
2. JOIN 列无索引（有索引时优化器优先选 Index Nested-Loop）
3. 8.0.18+（`optimizer_switch='block_nested_loop=on'` 被 Hash Join 替代）

EXPLAIN Extra：`Using join buffer (hash join)`

性能对比（经验数字，具体看数据分布）：
- BNL vs Hash Join：对无索引等值 JOIN，Hash Join 通常快 **2-10 倍**（把 O(M×N) 变成近似 O(M+N)）
- 内存不够时 Hash Join 会 spill 到磁盘（`open_files_limit` 相关），性能下降

#### Index Nested-Loop（INL，有索引时的正常路径）

```
for each row r1 in outer_table:
    index_lookup(inner_table, r1.join_col)  -- 走索引，O(log N)
```

只有内表 JOIN 列有索引时才走 INL。这是生产中期望的路径，EXPLAIN 里内表的 `type` 会是 `ref` 或 `eq_ref`。

#### 驱动表选择：小表驱动大表

"小表驱动大表"的具体含义是：**把行数更少（经过 WHERE 过滤后）的表放外层**。

原因：INL 中，外表每一行都要对内表做一次索引查找。外表 1000 行 = 1000 次索引查找；外表 100000 行 = 100000 次索引查找。外层越小越好。

优化器一般自动选择，但可以用 `STRAIGHT_JOIN` 强制顺序：

```sql
-- 强制 users 先扫（作为驱动表），orders 后扫
SELECT STRAIGHT_JOIN u.name, COUNT(o.id)
FROM users u
JOIN orders o ON o.user_id = u.id
WHERE u.country = 'CN'
GROUP BY u.id;
```

**使用场景**：优化器选错了驱动表（通常因为统计信息不准），且 ANALYZE TABLE 后依然如此，才用 `STRAIGHT_JOIN`。不要滥用——它绕过了优化器。

#### 诊断 JOIN 问题的检查清单

```sql
-- 1. EXPLAIN 看内表有没有走索引
EXPLAIN SELECT ...;
-- type = ALL / index on inner table → BNL/Hash Join → 要加索引

-- 2. 看 join_buffer_size
SHOW SESSION VARIABLES LIKE 'join_buffer_size';
-- 如果一定走 BNL，可调大（但是 per-connection，影响内存）

-- 3. 8.0 查是否启用 Hash Join
SELECT @@optimizer_switch\G
-- 看 block_nested_loop=on/off 和 hash_join=on/off
```

---

### 3.4 ORDER BY 优化 + filesort 两种算法 + sort_buffer

#### 何时走索引序，何时触发 filesort

ORDER BY 最好的情况是**直接沿着索引叶子节点顺序返回**，不需要额外排序。条件：
1. ORDER BY 列和 WHERE 等值列一起构成索引的最左前缀
2. ORDER BY 列方向一致（全 ASC 或全 DESC，8.0.11+ 支持混合方向的 Descending Index）

```sql
-- 表上有索引 (user_id, created_at)
SELECT * FROM orders WHERE user_id = 100 ORDER BY created_at;
-- → type=ref, Extra 无 Using filesort，直接走索引序 ✓

SELECT * FROM orders WHERE user_id > 100 ORDER BY created_at;
-- → user_id 是范围，created_at 不能走索引序，触发 filesort ✗

SELECT * FROM orders WHERE user_id = 100 ORDER BY created_at DESC, id ASC;
-- 5.7：混合方向触发 filesort。8.0.11+ 建 (user_id, created_at DESC, id ASC) 可解决
```

EXPLAIN Extra 出现 `Using filesort` = 触发了 Server 层排序，**不等于一定慢**，但意味着 CPU 和内存/磁盘消耗增加。

#### filesort 两种算法

**Algorithm 1：rowid sort（两次传递，旧版默认）**

```
1. 扫描满足 WHERE 的行，提取 (排序列值, rowid) 对放入 sort_buffer
2. 在 sort_buffer 里排序
3. 按排好的 rowid 顺序回表取其余列
```

缺点：步骤 3 的回表是按 rowid 顺序，可能是随机 IO（对 InnoDB 聚簇索引而言实际是按主键，比物理行地址略好，但依然可能随机）。

**Algorithm 2：full sort（单次传递，5.6+ 默认倾向）**

```
1. 扫描满足 WHERE 的行，提取 (排序列值, 所有需要的列值) 放入 sort_buffer
2. 在 sort_buffer 里排序
3. 直接从 sort_buffer 输出，不回表
```

优点：省去回表的随机 IO。
缺点：sort_buffer 里每行更宽，`sort_buffer_size` 容纳的行数更少。

MySQL 选择哪种算法取决于 `max_length_for_sort_data`（默认 4096 字节）：
- 需要的列总长度 ≤ `max_length_for_sort_data` → full sort（单次传递）
- 超出 → 回退到 rowid sort

#### sort_buffer 和磁盘合并

`sort_buffer_size` 默认 256KB（可以全局或会话级设置），每个排序操作独占一个 sort_buffer。

如果排序数据超过 sort_buffer_size：
1. 内存里先排一轮，写一个临时文件（run）
2. 再填充 sort_buffer，排序，写第二个 run
3. 最后做磁盘上的 merge sort（归并合并）

**诊断是否用了磁盘合并**：

```sql
-- 执行 SQL 前后对比
SHOW STATUS LIKE 'Sort_merge_passes';
-- Sort_merge_passes > 0 → 用了磁盘归并，sort_buffer_size 太小
SHOW STATUS LIKE 'Sort_rows';         -- 总排序行数
SHOW STATUS LIKE 'Sort_range';        -- 用索引范围排序次数
SHOW STATUS LIKE 'Sort_scan';         -- 全扫后排序次数
```

调整策略：

```sql
-- 会话级临时调大（仅当前连接有效，不要全局调大——per-connection 内存）
SET SESSION sort_buffer_size = 4 * 1024 * 1024;  -- 4MB

-- 如果是 SELECT * 改成 SELECT 具体列，可以减少 full sort 每行宽度
```

**最优解还是加索引**，让 ORDER BY 走索引序，彻底消除 filesort。

---

### 3.5 GROUP BY 优化 + 8.0 取消隐式排序

#### GROUP BY 的三种执行路径

**路径 1：松散索引扫描（Loose Index Scan）**

适用条件：GROUP BY 列 + 聚合函数 = 索引前缀，聚合是 MIN/MAX 类。

```sql
-- 索引 (category_id, price)
SELECT category_id, MIN(price), MAX(price)
FROM products
GROUP BY category_id;
```

EXPLAIN Extra：`Using index for group-by`

原理：B+ 树上每个 `category_id` 的最小/最大 `price` 在叶子节点链表的起止位置，只需跳跃扫描各组的边界，不需要扫描每一行。极快，扫描的行数 = 组数，不是总行数。

**路径 2：紧凑索引扫描（Tight Index Scan）**

适用条件：GROUP BY 列是索引前缀，不一定有 MIN/MAX 优化，但按索引顺序扫，省了排序/临时表。

```sql
-- 索引 (user_id, created_at)
SELECT user_id, COUNT(*) FROM orders GROUP BY user_id;
```

EXPLAIN Extra：`Using index`（覆盖）或无额外标记，无 `Using temporary` / `Using filesort`。

**路径 3：临时表 + filesort（最差）**

GROUP BY 列不是索引前缀，或者列上有函数。Server 层要先把所有行物化到临时表，再排序，再聚合。

EXPLAIN Extra：`Using temporary; Using filesort`

```sql
-- orders 没有 (status) 索引
SELECT status, COUNT(*) FROM orders GROUP BY status;
-- → Using temporary; Using filesort（如果 status 没有索引）
```

#### 8.0 取消 GROUP BY 隐式排序

MySQL 5.7 及之前，`GROUP BY col` 会**隐式 ORDER BY col**。很多人写 `GROUP BY` 后不加 `ORDER BY`，结果是排好序的，这是副作用，不是保证。

**MySQL 8.0 取消了这个行为**：`GROUP BY` 不再隐式排序。如果业务需要排序，必须显式写 `ORDER BY`。

```sql
-- 5.7：结果按 user_id 排序（隐式行为）
SELECT user_id, COUNT(*) FROM orders GROUP BY user_id;

-- 8.0：结果顺序不确定，要加 ORDER BY
SELECT user_id, COUNT(*) FROM orders GROUP BY user_id ORDER BY user_id;
```

实际影响：从 5.7 升 8.0，依赖隐式排序的业务代码可能结果顺序变了但不报错——**最难排查的 bug 之一**。

#### GROUP BY 优化技巧

```sql
-- 1. 确保 GROUP BY 列有索引（同时 WHERE + GROUP BY 能复用联合索引）
-- 例：(user_id, status) 上有联合索引
SELECT user_id, status, COUNT(*)
FROM orders
WHERE user_id IN (1,2,3)
GROUP BY user_id, status;
-- → type=range，Using index（覆盖），无 Using temporary

-- 2. 用 ORDER BY NULL 消除 5.7 的隐式排序（如果不需要排序）
SELECT status, COUNT(*) FROM orders GROUP BY status ORDER BY NULL;
-- 5.7 下可省去排序步骤

-- 3. 数据量大时考虑在应用层做二次聚合（先按 shard key GROUP BY 部分结果，再汇总）
```

---

### 3.6 Using temporary 触发条件 + 内存/磁盘临时表

#### 什么场景触发临时表

`Using temporary` 出现在 EXPLAIN Extra 里，意味着 MySQL Server 层需要一张中间临时表来暂存结果。常见触发场景：

| 场景 | 说明 |
|---|---|
| GROUP BY 列不是索引前缀 | 要把全部数据堆到临时表再聚合 |
| UNION（非 UNION ALL） | 需要临时表来做 DISTINCT 去重 |
| ORDER BY + GROUP BY 用了不同的列 | 无法用单索引同时满足 |
| SELECT DISTINCT 大数据量 | 去重需要临时表（有时走索引能避免） |
| FROM 子查询（derived table） | 子查询结果物化到临时表（5.7 有 Derived Condition Pushdown，8.0 更激进） |
| WINDOW 函数（8.0+） | 取决于窗口定义，复杂窗口需要临时表 |

#### 内存临时表 vs 磁盘临时表

临时表优先在内存里创建（使用 TempTable 引擎，8.0.13+ 默认；或旧版 MEMORY 引擎），超出大小限制后转到磁盘（InnoDB 或 MyISAM 磁盘临时表）。

控制大小的参数：

```sql
SHOW VARIABLES LIKE 'tmp_table_size';           -- 单个内存临时表上限，默认 16MB
SHOW VARIABLES LIKE 'max_heap_table_size';       -- MEMORY 引擎表上限，默认 16MB
-- 实际限制 = MIN(tmp_table_size, max_heap_table_size)

-- 8.0.13+ TempTable 引擎额外参数
SHOW VARIABLES LIKE 'temptable_max_ram';         -- 默认 1GB（所有内存临时表总量上限）
SHOW VARIABLES LIKE 'temptable_max_mmap';        -- 溢出到内存映射文件的大小上限，默认 1GB
```

**诊断是否产生了磁盘临时表**：

```sql
SHOW GLOBAL STATUS LIKE 'Created_tmp_tables';          -- 总内存临时表创建次数
SHOW GLOBAL STATUS LIKE 'Created_tmp_disk_tables';     -- 总磁盘临时表创建次数

-- 比值：Created_tmp_disk_tables / Created_tmp_tables > 0.1（10%）→ 临时表太大，要优化
```

磁盘临时表比内存临时表慢 **10-100 倍**（取决于磁盘速度），是显著的性能杀手。

#### 消除 / 缩小临时表的手段

```sql
-- 1. 给 GROUP BY / ORDER BY 列加索引，避免触发
-- 2. 精简 SELECT 列，减少单行宽度，让临时表装下更多行
-- 3. 提前用 WHERE 缩小数据集
-- 4. 调大 tmp_table_size（治标，不如加索引）
SET SESSION tmp_table_size = 64 * 1024 * 1024;  -- 64MB，仅当前会话

-- 5. UNION 改 UNION ALL（如果业务允许重复）
-- UNION 强制去重（隐式 DISTINCT），必须物化临时表
-- UNION ALL 不去重，直接合并结果集，无需临时表
```

---

### 3.7 LIMIT 深翻页：延迟关联法

#### 为什么 LIMIT 100000, 20 很慢

```sql
SELECT * FROM orders ORDER BY created_at LIMIT 100000, 20;
```

MySQL 的 LIMIT offset, count 不是「跳过 offset 行」，而是「扫描 offset+count 行，丢弃前 offset 行」。

执行流程：
1. 按 `created_at` 索引顺序扫描
2. 每行都要**回表**取 `SELECT *` 的全部列
3. 扫完 100020 行（100000 行丢弃 + 20 行返回）
4. 返回 20 行

所以 `LIMIT 100000, 20` = **100020 次回表**，随着 offset 增大线性变慢。`LIMIT 1000000, 20` = 百万次回表。

#### 方案一：延迟关联（Deferred Join）

思路：先只在覆盖索引上扫 100020 行（不回表），拿到 20 个主键，再精准回表 20 次。

```sql
-- 慢的写法：100020 次回表
SELECT * FROM orders ORDER BY created_at LIMIT 100000, 20;

-- 改写：延迟关联，先在覆盖索引上拿到主键
SELECT o.*
FROM orders o
JOIN (
    SELECT id FROM orders ORDER BY created_at LIMIT 100000, 20
) t ON o.id = t.id;
```

性能差异：
- 原写法：扫索引 100020 次 + 回表 100020 次
- 改写：扫覆盖索引 100020 次 + 回表 20 次
- offset 越大，差距越明显（offset=100000 时回表减少 99.98%）

**前提**：`(created_at, id)` 或 `(created_at)` 上有索引，子查询能走覆盖索引。

#### 方案二：主键游标分页（Cursor / Keyset Pagination）

适合从第 1 页翻到第 N 页的场景（产品上叫"加载更多"或"无限滚动"）：

```sql
-- 第一页
SELECT * FROM orders ORDER BY created_at, id LIMIT 20;

-- 记录最后一行的 (created_at, id) = ('2026-01-15 10:23:45', 98765)

-- 下一页：WHERE 替代 OFFSET
SELECT * FROM orders
WHERE (created_at, id) > ('2026-01-15 10:23:45', 98765)
ORDER BY created_at, id
LIMIT 20;
```

优点：
- 无论翻到第几页，始终只扫 20 行（O(1)，不是 O(offset)）
- 彻底解决深翻页性能问题

缺点：
- 不支持随机跳页（只能前后翻）
- 需要客户端记录游标（last seen `created_at` + `id`）
- `(created_at, id)` 必须是唯一的组合（通常加主键 id 保证）

#### UNION vs UNION ALL（附）

```sql
-- UNION：隐式 DISTINCT，需要临时表去重
SELECT id FROM table_a
UNION
SELECT id FROM table_b;

-- UNION ALL：不去重，直接合并，快很多
SELECT id FROM table_a
UNION ALL
SELECT id FROM table_b;
```

如果业务上两个子查询结果不会重叠（或不介意重复），**永远用 UNION ALL**。UNION 的代价 = 临时表 + 去重排序。

---

### 3.8 COUNT 三种写法 + 大表 count 用估值

#### count(*) vs count(1) vs count(col) 的区别

这是面试高频题，很多人答错。

**count(*)**：统计所有行，包括 NULL。InnoDB 8.0 对 `count(*)` 有专门优化：会选最小的索引扫（二级索引比聚簇索引页数少，IO 更少）。**推荐写法**。

**count(1)**：和 `count(*)` 完全等价。`1` 是非 NULL 常量表达式，每行都返回 1，不会因为 NULL 跳过。MySQL 优化器会把它当 `count(*)` 处理，执行计划相同。

**count(col)**：只统计 col 列不为 NULL 的行数。如果列有 NULL，结果 < 总行数。比 `count(*)` 多了一步 NULL 检查。

```sql
-- 三种写法结果可能不同：
SELECT COUNT(*) FROM orders;           -- 总行数（含 NULL）= 1000
SELECT COUNT(1) FROM orders;           -- 同上 = 1000
SELECT COUNT(deleted_at) FROM orders;  -- deleted_at 不为 NULL 的行数 = 50（如果 950 行 deleted_at 是 NULL）
```

**性能排名**（从官方文档和源码角度）：`count(*)` ≥ `count(1)` >> `count(非主键列)` > `count(主键列)`

注意：`count(主键)` 不比 `count(*)` 快，因为主键必须逐行取值判断（尽管主键不为 NULL，优化器不一定能提前确认）。

#### 为什么大表 COUNT 慢

InnoDB 没有像 MyISAM 那样在元数据里维护精确的行数（因为 MVCC：不同事务看到的行数不一样，无法用单一数字缓存）。每次 `COUNT(*)` 都要扫描一遍索引。

1000 万行的表，走最小二级索引扫，也需要几秒到几十秒（取决于 buffer pool 命中率）。

#### 大表 count 的四种替代方案

**方案 1：information_schema 估值（秒级，精度约 ±5%）**

```sql
SELECT TABLE_ROWS
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'your_db'
  AND TABLE_NAME = 'orders';
```

`TABLE_ROWS` 是基于采样的估算，InnoDB 表误差约 40-50%（官方文档说可能更高）。适合展示"大约有多少行"的场景，不适合需要精确值的。

更准的估值：

```sql
-- information_schema 基于 InnoDB 统计（可通过 ANALYZE TABLE 刷新）
ANALYZE TABLE orders;
SELECT TABLE_ROWS FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'your_db' AND TABLE_NAME = 'orders';
```

**方案 2：EXPLAIN 估值（毫秒级）**

```sql
EXPLAIN SELECT COUNT(*) FROM orders;
-- rows 列 = 优化器估算的总行数，比 information_schema 快，误差相当
```

可以用 EXPLAIN 的 `rows` 值作为大表 count 的快速估算。

**方案 3：专门的计数表（精确，写多读少场景）**

```sql
-- 维护一个计数表
CREATE TABLE table_counts (
    table_name VARCHAR(64) PRIMARY KEY,
    cnt BIGINT NOT NULL DEFAULT 0
);

-- 写入时同步更新（在事务里）
START TRANSACTION;
INSERT INTO orders (...) VALUES (...);
UPDATE table_counts SET cnt = cnt + 1 WHERE table_name = 'orders';
COMMIT;

-- 读 count 直接查 table_counts，O(1)
SELECT cnt FROM table_counts WHERE table_name = 'orders';
```

注意：要在同一个事务里维护，否则 count 和实际行数可能短暂不一致。

**方案 4：Redis 计数器**

写入/删除时原子 INCR/DECR Redis，读 count 查 Redis。适合高并发计数，但需要处理 Redis 和 MySQL 的一致性问题（如服务重启后从 MySQL 重新同步）。

---

## 4. 日常开发应用

### "我刚写完 SQL，5 秒判断有没有问题" checklist

写完每条 SQL 之后，对着下面 5 个问题过一遍：

```
□ 1. EXPLAIN 的 type 列有没有 ALL？
      ALL = 全表扫，几乎肯定要加索引（除非表很小）

□ 2. EXPLAIN Extra 有没有 Using filesort / Using temporary？
      有 = ORDER BY 或 GROUP BY 没走索引序，review 索引设计

□ 3. rows × filtered / 100 是不是远大于 rows_sent？
      EXPLAIN 的 rows 是估算，实际看慢查日志的 Rows_examined
      比值 > 1000 是危险信号

□ 4. JOIN 的内表（被驱动表）有没有走索引（type = ref / eq_ref）？
      内表 type = ALL → Using join buffer → 要在 JOIN 列上加索引

□ 5. 有没有 LIMIT 大 offset？（LIMIT 10000+, N）
      有 = 改延迟关联或改游标分页

□ 附加：SELECT 是否用了 *？
      SELECT * 可能让覆盖索引失效（需要回表），也让网络传输变重
```

### 索引设计原则（综合 ch03）

详细原理见 [03-indexing/README.md](../03-indexing/README.md)，本章补充调优视角的两条原则：

**联合索引列顺序两条原则**（来自 ch03 §3.3，此处强调）：
1. **等值列放最左**：WHERE 里用 `=` 的列放最前，范围列（`>`/`<`/`BETWEEN`/`LIKE 'x%'`）放最后
2. **高区分度列靠前**：区分度 = `COUNT(DISTINCT col) / COUNT(*)`，越接近 1 越好（但不要让低区分度列"卡"住后面的高区分度列）

**调优视角额外两条**：
3. **覆盖查询热路径**：最热的 2-3 条 SQL 如果能走覆盖索引（不回表），优先建这些索引
4. **索引不是越多越好**：每个二级索引写入时都要维护（INSERT/UPDATE/DELETE 都要更新索引树），写多读少的表索引要精简

---

## 5. 调优实战

### Case A：慢 SQL 上线后定位

**现象**：上线 2 小时后，慢查日志里出现大量 `Query_time: 4.5`，涉及 `orders` 表。

**定位步骤**：

```bash
# 1. 用 pt-query-digest 找 Top 耗时 SQL
pt-query-digest /var/log/mysql/slow.log --limit 5 > /tmp/digest.txt
```

发现 fingerprint：
```sql
SELECT * FROM orders WHERE user_id = ? AND status = ? ORDER BY created_at DESC LIMIT ?
```

```sql
-- 2. 拿到 EXPLAIN
EXPLAIN SELECT * FROM orders
WHERE user_id = 12345 AND status = 'pending'
ORDER BY created_at DESC LIMIT 20\G
```

```
         id: 1
select_type: SIMPLE
      table: orders
       type: ref
   key: idx_user_id          -- 走了 user_id 索引
      rows: 85000             -- 但扫了 8.5 万行！
     Extra: Using index condition; Using filesort  -- filesort！
```

**分析**：走了 `idx_user_id`，但 `status` 没有索引过滤，`created_at` 没走索引序，触发 filesort。85000 行回表 + filesort 排序。

**解法**：

```sql
-- 加联合索引（等值列 user_id/status 在前，ORDER BY 列 created_at 在后）
ALTER TABLE orders
ADD INDEX idx_user_status_created (user_id, status, created_at);
```

```sql
-- 验证
EXPLAIN SELECT * FROM orders
WHERE user_id = 12345 AND status = 'pending'
ORDER BY created_at DESC LIMIT 20\G
```

```
  type: ref
   key: idx_user_status_created
  rows: 20             -- 从 85000 降到 20
 Extra: Using index condition   -- 无 Using filesort ✓
```

Query_time 从 4.5s → 1ms。

---

### Case B：ORDER BY ... LIMIT 慢 → 索引序解决

**现象**：

```sql
-- 1.2s，EXPLAIN rows=50000，Using filesort
SELECT id, title, created_at FROM articles
WHERE category_id = 5
ORDER BY created_at DESC
LIMIT 20;
```

**分析**：`category_id` 上有索引，但 `created_at` 没有跟 `category_id` 的联合索引，ORDER BY 走 filesort。

**解法**：

```sql
-- 建联合索引，ORDER BY 列放后
ALTER TABLE articles
ADD INDEX idx_cat_created (category_id, created_at DESC);
-- 8.0.11+ 支持 Descending Index，可以精确匹配 ORDER BY created_at DESC
```

```sql
EXPLAIN SELECT id, title, created_at FROM articles
WHERE category_id = 5
ORDER BY created_at DESC
LIMIT 20\G
-- type=ref, key=idx_cat_created, rows=20, Extra=Using index ← 覆盖索引！
```

**小细节**：`SELECT id, title, created_at` 正好是索引列的超集（假设 `id` 是主键，包含在二级索引里）或者把 `title` 也加进索引做覆盖，可以彻底消除回表。

---

### Case C：GROUP BY 大字段慢 → 临时表 + filesort 双重打击

**现象**：

```sql
-- 8s，EXPLAIN: Using temporary; Using filesort
SELECT customer_city, COUNT(*) AS cnt
FROM orders
WHERE created_at >= '2026-01-01'
GROUP BY customer_city
ORDER BY cnt DESC
LIMIT 10;
```

**分析**：
- `customer_city` 没有索引，GROUP BY 无法走索引扫描 → `Using temporary`
- ORDER BY 的是聚合结果 `cnt`，不是表列，无法走索引序 → `Using filesort`
- 双重打击：临时表物化全部结果（可能有百万行），再排序

**解法 1（加索引，减少临时表行数）**：

```sql
-- 先缩小数据集：给 created_at 加索引，让 WHERE 过滤先走索引
ALTER TABLE orders ADD INDEX idx_created (created_at);

-- 可能还不够，如果过滤后仍有大量行要 GROUP BY
-- 考虑 (created_at, customer_city) 联合索引，让 GROUP BY 也走索引
ALTER TABLE orders ADD INDEX idx_created_city (created_at, customer_city);
```

```sql
-- 改写：先 WHERE 过滤用索引，GROUP BY 走 (created_at, customer_city) tight scan
EXPLAIN SELECT customer_city, COUNT(*) AS cnt
FROM orders
WHERE created_at >= '2026-01-01'
GROUP BY customer_city
ORDER BY cnt DESC
LIMIT 10\G
-- 理想：type=range，Using index，无 Using temporary
```

**解法 2（应用层缓存）**：这种"TOP 城市"聚合查询，结果可以缓存在 Redis 里（TTL 5 分钟），不需要每次实时查。

---

### Case D：COUNT(*) 大表超时 → 改估值

**现象**：

```sql
-- 管理后台展示"订单总量 xxx 单"，orders 表 5000 万行
SELECT COUNT(*) FROM orders;
-- 每次 15-20s，DBA 叫停
```

**解法**：

```sql
-- 方案 A：EXPLAIN 估值（毫秒，误差 ±10-30%，够展示用）
EXPLAIN SELECT COUNT(*) FROM orders;
-- 取 rows 列的值

-- 方案 B：information_schema（定期 ANALYZE TABLE 后误差 < 5%）
ANALYZE TABLE orders;  -- 更新统计（会锁表短暂，生产在低峰期）
SELECT TABLE_ROWS FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'orders';

-- 方案 C：维护专用计数表（精确，如果业务需要）
-- 在订单创建/删除的事务里同步 UPDATE order_count SET cnt = cnt ± 1
SELECT cnt FROM order_count WHERE id = 1;
```

**展示策略**：管理后台通常可以接受"约 5000 万单"，用估值 + 定期刷新完全够用。精确计数只在财务对账等场景才需要。

---

### Case E：大 JOIN 慢 → 改驱动表 / 加索引

**现象**：

```sql
-- 3s，分析后发现走了 BNL
SELECT u.name, SUM(o.amount) AS total
FROM orders o
JOIN users u ON u.id = o.user_id
WHERE o.created_at >= '2026-04-01'
GROUP BY u.id, u.name;
```

EXPLAIN 显示：

```
id  table  type   key           rows    Extra
1   u      ALL    NULL          500000  Using temporary; Using filesort
1   o      ref    idx_user_id   12      Using where
```

users 被选为外表，全表扫 50 万行。

**分析**：优化器把 users（50 万行）选为驱动表，orders 走 idx_user_id 作为内表。看起来合理，但 `o.created_at >= '2026-04-01'` 如果能过滤 orders 到很少的行，驱动表应该是过滤后的 orders。

**解法**：

```sql
-- 1. 给 orders.created_at 加索引，让 WHERE 先过滤
ALTER TABLE orders ADD INDEX idx_created (created_at);

-- 2. 用 STRAIGHT_JOIN 强制 orders 作为驱动表（如果优化器仍然选错）
SELECT STRAIGHT_JOIN u.name, SUM(o.amount) AS total
FROM orders o                         -- orders 在前 = 驱动表
JOIN users u ON u.id = o.user_id
WHERE o.created_at >= '2026-04-01'
GROUP BY u.id, u.name;
```

```sql
-- 3. 验证：orders 先走 idx_created，过滤后只有少量行，users 作为内表走主键
EXPLAIN SELECT STRAIGHT_JOIN u.name, SUM(o.amount) AS total
FROM orders o
JOIN users u ON u.id = o.user_id
WHERE o.created_at >= '2026-04-01'
GROUP BY u.id, u.name\G
-- orders: type=range, key=idx_created, rows=1200
-- users:  type=eq_ref, key=PRIMARY, rows=1   ← 每次用主键精确查
```

时间从 3s → 50ms。

---

## 6. 面试高频考点

### 必考对比

| 维度 | count(*) | count(1) | count(col) |
|---|---|---|---|
| 含义 | 总行数（含 NULL） | 等价于 count(*) | col 不为 NULL 的行数 |
| 性能 | InnoDB 会选最小索引扫 | 同 count(*) | 需要判断 NULL，略慢 |
| 推荐 | 是（官方推荐） | 可以，和 * 一样 | 当业务确实要排除 NULL 时 |

| 维度 | UNION | UNION ALL |
|---|---|---|
| 去重 | 是（隐式 DISTINCT） | 否 |
| 临时表 | 需要（去重用） | 不需要 |
| 性能 | 慢 | 快 |
| 何时用 | 结果集可能重叠且要去重 | 结果集不重叠或不在乎重复 |

| 维度 | BNL | Hash Join | Index Nested-Loop |
|---|---|---|---|
| 适用版本 | < 8.0.20 | 8.0.18+ | 所有版本 |
| 要求 | 无 | 等值 JOIN，无索引 | JOIN 列有索引 |
| 内存 | join_buffer_size | join_buffer_size | 不需要额外缓冲 |
| 性能 | O(M*N/join_buf) | 近似 O(M+N) | O(M*log N) |
| EXPLAIN Extra | Using join buffer (BNL) | Using join buffer (hash join) | 无额外标记 |

### filesort 两种算法快速答法

> MySQL filesort 有两种算法：**rowid sort**（两次传递）先提取排序列 + rowid 排序，再回表；**full sort**（单次传递）把排序列 + 所需列全带走，排序后直接输出不回表。选择依据是 `max_length_for_sort_data`（默认 4096 字节），行宽超过就用 rowid sort。`sort_buffer_size`（默认 256KB）不够时做磁盘 merge sort，`Sort_merge_passes` > 0 是信号。

### "GROUP BY 8.0 有什么变化" 答法

> MySQL 8.0 取消了 GROUP BY 的隐式排序（5.7 里 GROUP BY col 会隐式 ORDER BY col）。8.0 起不加 ORDER BY 的 GROUP BY 结果顺序不确定，需要显式写 ORDER BY。另外，8.0.18+ 引入 Hash Join 替代 BNL，GROUP BY 不走索引时触发临时表的行为不变，但 8.0 的 TempTable 引擎（替代 MEMORY）溢出到磁盘时用 mmap 而非 MyISAM，性能更好。

### 深翻页的经典问法

**Q：LIMIT 100000, 20 为什么慢？有几种解法？**

A：MySQL 的 LIMIT offset, count 要扫 offset+count 行才丢弃前 offset 行，每行都可能回表。offset=100000 = 100020 次回表。两种解法：

1. **延迟关联**：子查询先在覆盖索引上取 id，再精确回表 20 次（适合任意跳页）
2. **游标分页**：记录上一页最后一行的排序列值，下一页用 WHERE 替代 OFFSET（适合顺序翻页，彻底 O(1)）

### 易错点

- **Using filesort 不等于走了磁盘排序**：filesort 是 Server 层排序的统称，数据量小时完全在 sort_buffer（内存）里完成，`Sort_merge_passes=0` 就是纯内存排序
- **小表驱动大表是结果集小的表，不是原始行数小的表**：经过 WHERE 过滤后剩 10 行的大表，比没有 WHERE 的 100 行小表更适合当驱动表
- **count(*) 和 count(1) 性能一样**：面试中不要说"count(1) 比 count(*) 快"，这是误解。官方文档明确说两者等价
- **8.0 的 Hash Join 不是万能的**：只支持等值 JOIN，非等值（`>`/`<`/`!=`）还是 BNL（或 NLJ）

---

## 7. 一句话总结

调优 SQL 的入口是慢查日志（`long_query_time` + `pt-query-digest`）或 `performance_schema.events_statements_summary_by_digest`；
核心诊断工具是 `EXPLAIN`——看 `type=ALL`、`Using filesort`、`Using temporary`、`Using join buffer` 四个危险信号；
常见根因是 ORDER BY / GROUP BY / JOIN 列缺索引（分别触发 filesort、临时表、BNL/Hash Join）；
两个高频大坑是 `LIMIT 大 offset`（改延迟关联或游标分页）和 `COUNT(*) 大表`（改估值或维护计数表）；
写完 SQL 先 EXPLAIN，上线前过一遍 5 条 checklist。

---

## 相关章节

- [03-indexing/README.md](../03-indexing/README.md) — B+ 树、聚簇索引、覆盖索引、ICP、联合索引设计原则
