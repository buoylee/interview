# 慢查询与 EXPLAIN

## 为什么需要慢查询分析

数据库是大多数系统的性能瓶颈所在。当用户抱怨"页面打开慢"时，80% 的问题最终都指向一条低效的 SQL。**慢查询日志是发现问题 SQL 的第一入口，EXPLAIN 是理解它为什么慢的核心工具**。不会读 EXPLAIN，就像不会读 X 光片的医生——只能靠猜。

---

## 一、慢查询日志配置

### MySQL 慢查询日志

```sql
-- 查看当前配置
SHOW VARIABLES LIKE 'slow_query%';
SHOW VARIABLES LIKE 'long_query_time';

-- 动态开启（不需要重启）
SET GLOBAL slow_query_log = ON;
SET GLOBAL long_query_time = 1;          -- 超过 1 秒记录
SET GLOBAL log_queries_not_using_indexes = ON;  -- 未使用索引也记录
SET GLOBAL min_examined_row_limit = 100;  -- 扫描行数 < 100 的不记录（过滤噪音）
```

在 `my.cnf` 中持久化：

```ini
[mysqld]
slow_query_log = ON
slow_query_log_file = /var/log/mysql/slow.log
long_query_time = 1
log_queries_not_using_indexes = ON
min_examined_row_limit = 100
log_slow_admin_statements = ON    # DDL 也记录
log_slow_slave_statements = ON    # 从库回放慢也记录
```

**生产建议**：`long_query_time` 从 1 秒开始，逐步降到 0.5 秒甚至 0.1 秒。别一开始就设 0——日志量会爆炸。

### PostgreSQL 慢查询日志

```ini
# postgresql.conf
log_min_duration_statement = 1000       # 毫秒，超过 1 秒记录
log_statement = 'none'                  # 不要用 'all'，量太大
log_duration = off                      # 单独开 duration 没太大用
log_line_prefix = '%t [%p] %u@%d '     # 时间、PID、用户、数据库
auto_explain.log_min_duration = '1s'    # 自动记录执行计划（需要加载模块）
auto_explain.log_analyze = true         # 记录实际行数
auto_explain.log_buffers = true         # 记录 buffer 使用
```

加载 auto_explain 模块：

```ini
# postgresql.conf
shared_preload_libraries = 'auto_explain'
```

```bash
# 重新加载配置（不需要重启）
pg_ctl reload -D /var/lib/pgsql/data
# 或者
SELECT pg_reload_conf();
```

### PostgreSQL pg_stat_statements

比慢查询日志更强大的统计工具，聚合相同结构的 SQL：

```sql
-- 启用
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- 查看最耗时的 SQL（Top 10）
SELECT
    calls,
    round(total_exec_time::numeric, 2) AS total_ms,
    round(mean_exec_time::numeric, 2) AS avg_ms,
    round(stddev_exec_time::numeric, 2) AS stddev_ms,
    rows,
    query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;

-- 查看平均最慢（单次执行慢）
SELECT
    calls,
    round(mean_exec_time::numeric, 2) AS avg_ms,
    round((100 * total_exec_time / sum(total_exec_time) OVER())::numeric, 2) AS pct,
    query
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- 定期重置统计
SELECT pg_stat_statements_reset();
```

---

## 二、pt-query-digest 使用

Percona Toolkit 的 `pt-query-digest` 是分析 MySQL 慢查询日志的标准工具。

### 安装

```bash
# CentOS/RHEL
yum install -y percona-toolkit

# Ubuntu/Debian
apt-get install -y percona-toolkit

# macOS
brew install percona-toolkit
```

### 基本用法

```bash
# 分析慢查询日志
pt-query-digest /var/log/mysql/slow.log

# 只看最近 1 小时
pt-query-digest --since '1h' /var/log/mysql/slow.log

# 输出到文件
pt-query-digest /var/log/mysql/slow.log > /tmp/slow_report.txt

# 只看特定数据库
pt-query-digest --filter '$event->{db} eq "perfshop"' /var/log/mysql/slow.log
```

### 输出解读

```
# Profile
# Rank Query ID                         Response time   Calls  R/Call  V/M
# ==== ================================ =============== ====== ======= ===
#    1 0xABC123DEF456...                 125.0340 48.7%    342  0.3655  0.12
#    2 0x789GHI012JKL...                  68.1230 26.5%   1205  0.0565  0.03
#    3 0xMNO345PQR678...                  32.5670 12.7%     89  0.3660  0.45

# Query 1: 5.70 QPS, 2.08x concurrency, ID 0xABC123DEF456...
# This item is included in the report because it matches --limit.
# Scores: V/M = 0.12
# Time range: 2024-01-15T10:00:00 to 2024-01-15T11:00:00
# Attribute    pct   total     min     max     avg     95%  stddev  median
# ============ === ======= ======= ======= ======= ======= ======= =======
# Count         14     342
# Exec time     48    125s   100ms      2s   365ms   800ms   200ms   300ms
# Lock time      5    20ms    10us   500us    58us   100us    40us    40us
# Rows sent     12   2.05k       1      20    6.14       9    4.21    5.99
# Rows examine  45  12.05M   1.00k  50.00k  36.10k  49.02k  15.21k  35.00k
# Query_time distribution
#   1us
#  10us
# 100us
#   1ms
#  10ms
# 100ms  ################################################################
#    1s   ###
#  10s+
# SELECT p.*, c.name AS category_name
# FROM products p
# JOIN categories c ON p.category_id = c.id
# WHERE p.status = 1
# AND p.price BETWEEN 100 AND 500
# ORDER BY p.created_at DESC
# LIMIT 20\G
```

**关键指标**：
| 指标 | 含义 | 关注点 |
|------|------|--------|
| Response time | 总耗时占比 | 占比最高的优先优化 |
| Calls | 执行次数 | 高频低效的比单次慢更危险 |
| R/Call | 每次平均耗时 | 单次 > 1s 需要关注 |
| V/M | 方差/均值比 | > 1 说明执行时间波动大，可能有锁等待 |
| Rows examine | 扫描行数 | 远大于 Rows sent 说明索引有问题 |

---

## 三、EXPLAIN 深入解读

### 基本使用

```sql
-- MySQL
EXPLAIN SELECT * FROM products WHERE category_id = 5 AND price > 100;

-- 更详细的格式
EXPLAIN FORMAT=JSON SELECT * FROM products WHERE category_id = 5 AND price > 100;
EXPLAIN FORMAT=TREE SELECT * FROM products WHERE category_id = 5 AND price > 100;

-- 实际执行并统计（MySQL 8.0.18+）
EXPLAIN ANALYZE SELECT * FROM products WHERE category_id = 5 AND price > 100;

-- PostgreSQL
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT * FROM products WHERE category_id = 5 AND price > 100;
```

### type 列：访问类型（从好到差）

| type | 含义 | 性能 | 典型场景 |
|------|------|------|----------|
| system | 表只有一行 | 最好 | 系统表 |
| const | 主键/唯一索引等值查询 | 极好 | `WHERE id = 1` |
| eq_ref | 关联查询中主键/唯一索引 | 很好 | `JOIN ON a.id = b.a_id`（a.id 是主键） |
| ref | 非唯一索引等值查询 | 好 | `WHERE status = 1`（status 有索引） |
| range | 索引范围扫描 | 还行 | `WHERE price BETWEEN 100 AND 500` |
| index | 全索引扫描 | 差 | 遍历整个索引树 |
| ALL | 全表扫描 | 最差 | 没有可用索引 |

**生产标准**：OLTP 查询至少达到 `ref` 级别，出现 `ALL` 或 `index` 就要优化。

### key/key_len 列

```sql
EXPLAIN SELECT * FROM orders WHERE user_id = 100 AND status = 'paid';

-- 假设有联合索引 idx_user_status(user_id, status)
-- key: idx_user_status
-- key_len: 7   (int=4 + varchar(3)=3)
```

`key_len` 可以判断联合索引用了几个字段：

| 数据类型 | key_len | 说明 |
|----------|---------|------|
| INT | 4 | 允许 NULL 则 +1 |
| BIGINT | 8 | 允许 NULL 则 +1 |
| VARCHAR(N) utf8mb4 | 4*N + 2 | +2 是变长字段长度标记 |
| DATETIME | 5 | 允许 NULL 则 +1 |
| CHAR(N) utf8mb4 | 4*N | 定长 |

### rows 与 filtered 列

```sql
EXPLAIN SELECT * FROM products WHERE category_id = 5 AND price > 100;

-- rows: 5000     -- 预估扫描行数
-- filtered: 30   -- 经过 WHERE 过滤后剩余行数百分比
-- 实际返回约 5000 * 30% = 1500 行
```

**注意**：`rows` 是基于统计信息的**估算值**，不是精确值。统计信息不准时会导致优化器选错执行计划。

### Extra 列关键信息

| Extra | 含义 | 是否需要优化 |
|-------|------|-------------|
| Using index | 覆盖索引，不需要回表 | 好，不需要优化 |
| Using where | Server 层过滤 | 关注，可能索引没用好 |
| Using index condition | 索引下推（ICP） | 好，MySQL 5.6+ |
| Using temporary | 使用临时表 | 差，GROUP BY/ORDER BY 需要优化 |
| Using filesort | 额外排序 | 差，ORDER BY 没有走索引 |
| Using join buffer | 关联查询无索引 | 差，被驱动表需要加索引 |
| Impossible WHERE | WHERE 条件永远为假 | 检查 SQL 逻辑 |
| Select tables optimized away | 聚合函数直接走索引 | 好，MIN/MAX 等 |

---

## 四、执行计划陷阱

### 陷阱 1：统计信息不准

```sql
-- MySQL：查看表统计信息
SHOW TABLE STATUS LIKE 'products'\G
-- Rows: 980000  （实际可能有 1200000）

-- 手动更新统计信息
ANALYZE TABLE products;

-- InnoDB 统计信息配置
SHOW VARIABLES LIKE 'innodb_stats%';
-- innodb_stats_persistent = ON         -- 持久化统计信息
-- innodb_stats_auto_recalc = ON        -- 自动重新计算
-- innodb_stats_persistent_sample_pages = 20  -- 采样页数（调大可提高准确性）
```

```sql
-- PostgreSQL：查看统计信息
SELECT
    relname,
    reltuples AS estimated_rows,
    n_live_tup AS live_rows,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
WHERE relname = 'products';

-- 手动更新
ANALYZE products;

-- 调整采样率（默认 100 页面）
ALTER TABLE products ALTER COLUMN category_id SET STATISTICS 1000;
ANALYZE products;
```

### 陷阱 2：隐式类型转换

```sql
-- products.sku 是 VARCHAR(32) 类型
-- 错误写法：传入数字，触发隐式转换，索引失效！
EXPLAIN SELECT * FROM products WHERE sku = 12345;
-- type: ALL  （全表扫描！）

-- 正确写法：类型匹配
EXPLAIN SELECT * FROM products WHERE sku = '12345';
-- type: ref  （走索引）
```

```sql
-- 常见的隐式转换场景
-- 1. Java 中 int 参数传给 VARCHAR 字段
-- 2. 字符集不一致的 JOIN（utf8 JOIN utf8mb4）
-- 3. 关联查询字段类型不一致

-- 查看字符集
SELECT column_name, character_set_name, collation_name
FROM information_schema.columns
WHERE table_name = 'products' AND column_name = 'sku';
```

### 陷阱 3：函数导致索引失效

```sql
-- 错误：对索引列使用函数
EXPLAIN SELECT * FROM orders WHERE DATE(created_at) = '2024-01-15';
-- type: ALL  （索引失效）

-- 正确：改写为范围查询
EXPLAIN SELECT * FROM orders
WHERE created_at >= '2024-01-15 00:00:00'
  AND created_at < '2024-01-16 00:00:00';
-- type: range  （走索引）

-- 错误：字符串函数
EXPLAIN SELECT * FROM users WHERE LEFT(phone, 3) = '138';
-- type: ALL

-- 正确：使用前缀 LIKE
EXPLAIN SELECT * FROM users WHERE phone LIKE '138%';
-- type: range
```

### 陷阱 4：EXPLAIN 与实际执行不同

```sql
-- EXPLAIN 只是**估计**，不是实际执行
-- 使用 EXPLAIN ANALYZE 看真实情况（MySQL 8.0.18+）
EXPLAIN ANALYZE
SELECT p.*, c.name
FROM products p
JOIN categories c ON p.category_id = c.id
WHERE p.price > 100
ORDER BY p.created_at DESC
LIMIT 20;

-- 输出示例：
-- -> Limit: 20 row(s)  (actual time=0.8..12.5 rows=20 loops=1)
--     -> Sort: p.created_at DESC  (actual time=0.8..12.4 rows=20 loops=1)
--         -> Nested loop join  (actual time=0.3..11.2 rows=4500 loops=1)
--             -> Filter: (p.price > 100)  (actual time=0.1..5.6 rows=4500 loops=1)
--                 -> Table scan on p  (actual time=0.1..3.2 rows=10000 loops=1)
--             -> Single-row index lookup on c using PRIMARY  (actual time=0.001..0.001 rows=1 loops=4500)
```

---

## 五、实操示例：PerfShop 商品查询

### 场景：商品列表页加载慢

用户反馈商品列表页加载超过 3 秒。应用日志显示以下 SQL 耗时 2.8 秒：

```sql
SELECT p.id, p.name, p.price, p.main_image,
       c.name AS category_name,
       (SELECT COUNT(*) FROM reviews r WHERE r.product_id = p.id) AS review_count
FROM products p
LEFT JOIN categories c ON p.category_id = c.id
WHERE p.status = 1
  AND p.category_id IN (SELECT id FROM categories WHERE parent_id = 10)
  AND p.price BETWEEN 50 AND 500
ORDER BY p.sales_count DESC
LIMIT 20 OFFSET 1000;
```

### 步骤 1：EXPLAIN 分析

```sql
EXPLAIN SELECT p.id, p.name, p.price, p.main_image,
       c.name AS category_name,
       (SELECT COUNT(*) FROM reviews r WHERE r.product_id = p.id) AS review_count
FROM products p
LEFT JOIN categories c ON p.category_id = c.id
WHERE p.status = 1
  AND p.category_id IN (SELECT id FROM categories WHERE parent_id = 10)
  AND p.price BETWEEN 50 AND 500
ORDER BY p.sales_count DESC
LIMIT 20 OFFSET 1000;
```

```
+----+--------------------+-------+------+------------------+------+---------+------+--------+-------------------------------+
| id | select_type        | table | type | possible_keys    | key  | key_len | ref  | rows   | Extra                         |
+----+--------------------+-------+------+------------------+------+---------+------+--------+-------------------------------+
|  1 | PRIMARY            | p     | ALL  | idx_category     | NULL | NULL    | NULL | 500000 | Using where; Using filesort   |
|  1 | PRIMARY            | c     | eq_ref| PRIMARY         | PRI  | 4       | ...  |      1 | NULL                          |
|  2 | DEPENDENT SUBQUERY | r     | ALL  | NULL             | NULL | NULL    | NULL | 200000 | Using where                   |
|  3 | SUBQUERY           | cat   | ref  | idx_parent       | ...  | 4       | ...  |      5 | Using index                   |
+----+--------------------+-------+------+------------------+------+---------+------+--------+-------------------------------+
```

### 步骤 2：逐一分析问题

| 问题编号 | 问题 | 影响 |
|---------|------|------|
| 1 | products 全表扫描（type=ALL） | 扫描 50 万行 |
| 2 | Using filesort | 额外排序，内存/磁盘开销 |
| 3 | reviews 关联子查询是 DEPENDENT SUBQUERY，每行执行一次 | 子查询执行数万次 |
| 4 | reviews 表没有 product_id 索引（type=ALL） | 每次子查询扫描 20 万行 |
| 5 | OFFSET 1000 | 数据库需要先读 1020 行再丢弃 1000 行 |

### 步骤 3：逐步优化

```sql
-- 优化 1：添加缺失索引
ALTER TABLE reviews ADD INDEX idx_product_id (product_id);

-- 优化 2：products 添加联合索引
ALTER TABLE products ADD INDEX idx_status_category_price (status, category_id, price);

-- 优化 3：把关联子查询改为 JOIN
-- 优化 4：用 keyset pagination 替代 OFFSET

-- 优化后的 SQL
SELECT p.id, p.name, p.price, p.main_image,
       c.name AS category_name,
       COALESCE(rc.cnt, 0) AS review_count
FROM products p
LEFT JOIN categories c ON p.category_id = c.id
LEFT JOIN (
    SELECT product_id, COUNT(*) AS cnt
    FROM reviews
    GROUP BY product_id
) rc ON rc.product_id = p.id
WHERE p.status = 1
  AND p.category_id IN (5, 8, 12, 15, 20)  -- 提前查出子分类 ID
  AND p.price BETWEEN 50 AND 500
  AND p.id < 50000                           -- keyset pagination
ORDER BY p.sales_count DESC
LIMIT 20;
```

### 步骤 4：验证优化效果

```sql
EXPLAIN ANALYZE <优化后的 SQL>;

-- 对比：
-- 优化前：2.8s, rows_examined=12,000,000+
-- 优化后：0.05s, rows_examined=3,200
```

---

## 六、慢查询排查清单

| 步骤 | 操作 | 命令/工具 |
|------|------|----------|
| 1 | 开启慢查询日志 | `SET GLOBAL slow_query_log = ON` |
| 2 | 分析日志找 Top SQL | `pt-query-digest slow.log` |
| 3 | EXPLAIN 分析执行计划 | `EXPLAIN FORMAT=TREE <sql>` |
| 4 | 检查 type 列 | 目标：至少 ref，不能出现 ALL |
| 5 | 检查 Extra 列 | 避免 Using filesort + Using temporary |
| 6 | 检查 rows 列 | 扫描行 >> 返回行 = 索引有问题 |
| 7 | 检查隐式转换 | 字段类型与参数类型一致 |
| 8 | 检查函数使用 | 索引列不要套函数 |
| 9 | 验证统计信息 | `ANALYZE TABLE` 更新统计信息 |
| 10 | 用 EXPLAIN ANALYZE 验证 | 看实际执行时间和行数 |

**核心原则**：先通过日志/监控找到问题 SQL，再用 EXPLAIN 定位根因，最后通过索引/改写解决。不要盲目加索引——每个索引都有写入成本。
