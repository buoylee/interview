# 索引优化

## 为什么索引是数据库性能的核心

没有索引的查询就是全表扫描——百万行数据每次都从头翻到尾。**索引做得好，查询从秒级降到毫秒级；索引做得差，不仅查询没快，写入还变慢**。索引优化不是"加个索引就行"，需要理解原理、选择性、失效场景，才能在读写之间找到平衡。

---

## 一、B+ Tree 原理

### 为什么数据库用 B+ Tree 而不是其他结构

| 数据结构 | 查找复杂度 | 问题 |
|---------|-----------|------|
| 哈希表 | O(1) | 不支持范围查询、不支持排序 |
| 二叉搜索树 | O(log n) | 树高太高，磁盘 IO 次数多 |
| 红黑树 | O(log n) | 同上，每个节点只存一个 key |
| B Tree | O(log n) | 数据存在所有节点，范围查询需要中序遍历 |
| **B+ Tree** | **O(log n)** | **数据只在叶子节点，叶子节点链表连接，范围查询高效** |

### B+ Tree 的关键特性

```
                    [30 | 60]                    ← 根节点（只存 key）
                   /    |    \
          [10|20]    [40|50]    [70|80]           ← 中间节点（只存 key）
          /  |  \    /  |  \    /  |  \
        [叶1]->[叶2]->[叶3]->[叶4]->[叶5]->[叶6]  ← 叶子节点（存 key + 数据/指针）
                     双向链表连接
```

**为什么适合磁盘存储**：
1. **节点大 = 矮树**：每个节点通常是一个磁盘页（16KB），能存上千个 key。百万数据只需 3-4 层，也就是 3-4 次磁盘 IO
2. **叶子节点链表**：范围查询只需找到起点，然后沿链表顺序读，不需要回到上层节点
3. **非叶子节点不存数据**：一个页能放更多 key，树更矮

### InnoDB 的 B+ Tree 实现

```
聚簇索引（Primary Key）：
  叶子节点存完整行数据
  [PK=1 | name=iPhone | price=5999 | ...]
  [PK=2 | name=iPad   | price=3999 | ...]

二级索引（Secondary Index）：
  叶子节点存索引列值 + 主键值
  [category_id=5 | PK=1]
  [category_id=5 | PK=3]
  [category_id=8 | PK=2]

  查询过程（回表）：
  1. 在二级索引中找到 category_id=5 → 得到 PK=1, PK=3
  2. 拿 PK 回聚簇索引找完整行数据
```

---

## 二、索引选择性（Cardinality）

### 什么是选择性

选择性 = 不重复值数量 / 总行数。选择性越高，索引效果越好。

```sql
-- 查看索引的 Cardinality
SHOW INDEX FROM products;

-- 手动计算选择性
SELECT
    COUNT(DISTINCT category_id) / COUNT(*) AS category_selectivity,
    COUNT(DISTINCT status) / COUNT(*) AS status_selectivity,
    COUNT(DISTINCT sku) / COUNT(*) AS sku_selectivity,
    COUNT(DISTINCT user_id) / COUNT(*) AS user_selectivity
FROM products;
```

| 字段 | 不同值数量 | 总行数 | 选择性 | 适合建索引？ |
|------|----------|--------|--------|------------|
| sku | 500,000 | 500,000 | 1.0 | 非常适合 |
| user_id | 100,000 | 500,000 | 0.2 | 适合 |
| category_id | 200 | 500,000 | 0.0004 | 单独不太适合 |
| status | 3 | 500,000 | 0.000006 | 不适合单独建 |

**经验法则**：选择性 < 10% 的字段，单独建索引意义不大。但作为联合索引的**前缀**（配合等值查询）仍然有效。

### 前缀索引

对于长字符串字段，可以只索引前 N 个字符：

```sql
-- 查看不同前缀长度的选择性
SELECT
    COUNT(DISTINCT LEFT(email, 5)) / COUNT(*) AS sel_5,
    COUNT(DISTINCT LEFT(email, 10)) / COUNT(*) AS sel_10,
    COUNT(DISTINCT LEFT(email, 15)) / COUNT(*) AS sel_15,
    COUNT(DISTINCT email) / COUNT(*) AS sel_full
FROM users;

-- sel_5=0.12, sel_10=0.85, sel_15=0.98, sel_full=1.0
-- 前缀长度 10 已经达到 85% 的选择性，性价比较高

ALTER TABLE users ADD INDEX idx_email_prefix (email(10));
```

**前缀索引的限制**：不能用于 ORDER BY 和 GROUP BY，不能做覆盖索引。

---

## 三、覆盖索引（避免回表）

### 什么是覆盖索引

当查询需要的所有列都在索引中时，不需要回表读取完整行数据。EXPLAIN 中 Extra 列显示 `Using index`。

```sql
-- 创建联合索引
ALTER TABLE orders ADD INDEX idx_user_status_amount (user_id, status, total_amount);

-- 这个查询可以走覆盖索引（所有字段都在索引中）
EXPLAIN SELECT user_id, status, total_amount
FROM orders
WHERE user_id = 100 AND status = 'paid';
-- Extra: Using index  ← 覆盖索引！

-- 这个查询不行（需要 order_no，不在索引中）
EXPLAIN SELECT user_id, status, total_amount, order_no
FROM orders
WHERE user_id = 100 AND status = 'paid';
-- Extra: NULL  ← 需要回表
```

### 覆盖索引实战

```sql
-- 场景：用户订单列表页只显示摘要信息
-- 如果查询频繁，值得建一个宽索引

ALTER TABLE orders ADD INDEX idx_cover_user_list (
    user_id, status, created_at, total_amount, order_no
);

-- 列表查询直接走覆盖索引
SELECT order_no, status, total_amount, created_at
FROM orders
WHERE user_id = 100
ORDER BY created_at DESC
LIMIT 20;
-- Extra: Using where; Using index; Backward index scan
```

**权衡**：覆盖索引越宽，占用空间越大，写入越慢。只在高频查询上使用。

---

## 四、联合索引与最左前缀匹配

### 最左前缀原则

联合索引 `(a, b, c)` 相当于创建了三个索引：`(a)`, `(a, b)`, `(a, b, c)`。

```sql
ALTER TABLE orders ADD INDEX idx_abc (user_id, status, created_at);

-- ✅ 能用索引
WHERE user_id = 100                              -- 用到 (a)
WHERE user_id = 100 AND status = 'paid'          -- 用到 (a, b)
WHERE user_id = 100 AND status = 'paid'
      AND created_at > '2024-01-01'              -- 用到 (a, b, c)

-- ✅ 优化器会调整顺序，这个也能用
WHERE status = 'paid' AND user_id = 100          -- 用到 (a, b)

-- ❌ 不能用索引（跳过了 a）
WHERE status = 'paid'                            -- 不能用
WHERE status = 'paid' AND created_at > '2024-01-01'  -- 不能用
WHERE created_at > '2024-01-01'                  -- 不能用
```

### 范围查询对后续列的影响

```sql
-- 索引 idx_abc (user_id, status, created_at)

-- status 是等值查询，created_at 也能用索引
WHERE user_id = 100 AND status = 'paid' AND created_at > '2024-01-01'
-- key_len 包含所有三个字段 ✅

-- status 是范围查询，created_at 不能用索引
WHERE user_id = 100 AND status IN ('paid', 'shipped') AND created_at > '2024-01-01'
-- MySQL 5.7: key_len 只包含 user_id + status（IN 视为范围）
-- MySQL 8.0: IN 做了优化，三个字段都能用 ✅

-- 范围条件放最后
-- 好的索引设计：等值列在前，范围列在后
ALTER TABLE orders ADD INDEX idx_optimized (user_id, status, created_at);
-- 而不是 (user_id, created_at, status)
```

### 联合索引排序优化

```sql
-- 索引 (user_id, created_at)

-- ✅ 排序能用索引
SELECT * FROM orders WHERE user_id = 100 ORDER BY created_at DESC;
-- Extra: Backward index scan（MySQL 8.0 支持反向扫描）

-- ❌ 排序不能用索引（排序方向不一致）
SELECT * FROM orders WHERE user_id = 100 ORDER BY created_at ASC, total_amount DESC;

-- MySQL 8.0 支持降序索引
ALTER TABLE orders ADD INDEX idx_user_created_desc (user_id, created_at DESC);
```

---

## 五、索引失效场景

### 1. 函数/表达式

```sql
-- ❌ 对索引列使用函数
SELECT * FROM orders WHERE YEAR(created_at) = 2024;
SELECT * FROM users WHERE UPPER(username) = 'ADMIN';

-- ✅ 改写
SELECT * FROM orders WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01';
-- MySQL 8.0 支持函数索引
ALTER TABLE users ADD INDEX idx_upper_name ((UPPER(username)));
```

### 2. 隐式类型转换

```sql
-- phone 是 VARCHAR 类型
-- ❌ 传入数字
SELECT * FROM users WHERE phone = 13800138000;
-- MySQL 会把 phone 的每个值转换为数字来比较 → 索引失效

-- ✅ 传入字符串
SELECT * FROM users WHERE phone = '13800138000';
```

### 3. OR 条件

```sql
-- ❌ OR 连接的条件，如果其中一个没索引，整个查询不走索引
SELECT * FROM products WHERE category_id = 5 OR description LIKE '%手机%';

-- ✅ 用 UNION ALL 替代
SELECT * FROM products WHERE category_id = 5
UNION ALL
SELECT * FROM products WHERE description LIKE '%手机%' AND category_id != 5;
```

### 4. LIKE 前缀通配

```sql
-- ❌ 前缀是通配符
SELECT * FROM products WHERE name LIKE '%手机%';   -- 不走索引

-- ✅ 前缀确定
SELECT * FROM products WHERE name LIKE '苹果%';    -- 走索引（range）

-- 如果必须全文搜索，用全文索引或 Elasticsearch
ALTER TABLE products ADD FULLTEXT INDEX ft_name (name) WITH PARSER ngram;
SELECT * FROM products WHERE MATCH(name) AGAINST('手机' IN BOOLEAN MODE);
```

### 5. NOT IN / NOT EXISTS / !=

```sql
-- ❌ NOT IN 可能导致索引失效（取决于优化器判断）
SELECT * FROM products WHERE category_id NOT IN (1, 2, 3);

-- ❌ != 通常不走索引（扫描范围太大）
SELECT * FROM products WHERE status != 'deleted';

-- ✅ 改为正向条件
SELECT * FROM products WHERE status IN ('active', 'draft');
```

### 6. 索引列参与计算

```sql
-- ❌ 索引列做运算
SELECT * FROM orders WHERE id + 1 = 100;

-- ✅ 移到右边
SELECT * FROM orders WHERE id = 99;
```

### 索引失效速查表

| 场景 | 示例 | 解决方案 |
|------|------|---------|
| 函数包裹 | `WHERE YEAR(dt) = 2024` | 改为范围查询或函数索引 |
| 隐式转换 | `WHERE varchar_col = 123` | 保持类型一致 |
| 前缀通配 | `WHERE col LIKE '%abc'` | 全文索引/ES |
| OR 无索引 | `WHERE a=1 OR b=2`（b无索引） | UNION ALL |
| NOT IN | `WHERE col NOT IN (...)` | 改为正向 IN |
| 列运算 | `WHERE col + 1 = 100` | 移到等号右边 |
| 最左前缀断裂 | 跳过联合索引首列 | 调整索引或查询 |

---

## 六、索引建议工具

### MySQL 内置工具

```sql
-- MySQL 8.0 优化器建议
EXPLAIN FORMAT=JSON SELECT ...;
-- 查看 JSON 中的 "possible_keys" 和 "used_key_parts"

-- sys schema 索引使用统计
SELECT * FROM sys.schema_unused_indexes;          -- 没被使用的索引
SELECT * FROM sys.schema_redundant_indexes;       -- 冗余索引

-- performance_schema 索引使用统计
SELECT
    object_schema,
    object_name,
    index_name,
    count_fetch AS reads,
    count_insert + count_update + count_delete AS writes
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE object_schema = 'perfshop'
ORDER BY reads DESC;
```

### pt-index-usage

```bash
# 根据慢查询日志分析索引使用情况
pt-index-usage /var/log/mysql/slow.log \
  --host=127.0.0.1 --user=root --password=xxx

# 输出：哪些索引被使用、哪些从未使用
# ALTER TABLE `perfshop`.`products` DROP INDEX `idx_unused`;
```

### PostgreSQL 索引分析

```sql
-- 未使用的索引
SELECT
    schemaname || '.' || relname AS table,
    indexrelname AS index,
    pg_size_pretty(pg_relation_size(i.indexrelid)) AS index_size,
    idx_scan AS index_scans
FROM pg_stat_user_indexes i
JOIN pg_index USING (indexrelid)
WHERE idx_scan = 0
  AND indisunique IS FALSE
ORDER BY pg_relation_size(i.indexrelid) DESC;

-- 索引缓存命中率
SELECT
    indexrelname,
    idx_blks_read,
    idx_blks_hit,
    CASE WHEN idx_blks_read + idx_blks_hit = 0 THEN 0
         ELSE round(100.0 * idx_blks_hit / (idx_blks_read + idx_blks_hit), 2)
    END AS hit_rate_pct
FROM pg_statio_user_indexes
ORDER BY idx_blks_read DESC
LIMIT 20;
```

---

## 七、索引设计原则总结

| 原则 | 说明 |
|------|------|
| 高选择性优先 | 选择性 > 10% 的字段更适合建索引 |
| 等值条件在前 | 联合索引中等值列放前面，范围列放最后 |
| 覆盖高频查询 | 热门查询考虑覆盖索引避免回表 |
| 避免冗余索引 | (a, b) 已存在就不需要单独的 (a) |
| 控制索引数量 | 单表索引一般不超过 5-6 个 |
| 短索引优先 | 使用前缀索引减少空间占用 |
| 不在低选择性列单独建 | status、gender 这类不要单独建索引 |
| 定期清理无用索引 | 每月检查 sys.schema_unused_indexes |

**写入代价公式（粗略）**：每增加一个索引，INSERT 大约慢 5-10%，UPDATE 涉及索引列时更明显。在 OLTP 系统中，索引不是越多越好。
