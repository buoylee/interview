# Scenario 03: 深翻页 `LIMIT 40000,20` 与延迟关联改写

## 我想验证的问题

`LIMIT 40000,20` 这种深翻页为什么慢？「延迟关联」改写到底改变了什么？用 EXPLAIN 看两种写法的执行计划差在哪。

## 预期（基于 ch08 §3.6 推算）

`LIMIT offset, n` 的代价在于：MySQL 要**真的走到第 offset+n 行**，前面 offset 行白白读出来又丢掉。如果走的是二级索引、还要 `SELECT` 索引外的列，那前面这 offset 行**每一行都要回表**一次——offset 越大，浪费的回表越多。

**延迟关联**：先在**覆盖索引**上只取主键、翻到第 offset 行（这一步 `Using index`，不回表），拿到那 20 个主键后，再用主键 JOIN 回原表取完整行——**只回表 20 次**。

预期：延迟关联版本的子查询是 `Using index`（覆盖、不回表），最后只对 20 行做主键 `eq_ref` 回表。

## 环境

- 表 `up2`，`idx_city(city)`（二级索引叶子含主键 id）

## 步骤

```sql
-- 直接深翻页
EXPLAIN SELECT id,name,age,city FROM up2 WHERE city='Taipei' ORDER BY id LIMIT 40000,20;

-- 延迟关联改写：先在覆盖索引上翻页拿主键，再 JOIN 回表
EXPLAIN
SELECT a.id,a.name,a.age,a.city
FROM up2 a
JOIN (SELECT id FROM up2 WHERE city='Taipei' ORDER BY id LIMIT 40000,20) b
  ON a.id = b.id;
```

## 实机告诉我（本机实测，MySQL 8.0.36）

```
-- 直接 LIMIT 40000,20:
+------+----------+-------+-------+
| type | key      | rows  | Extra |
+------+----------+-------+-------+
| ref  | idx_city | 18030 | NULL  |   ← 走 idx_city，但取索引外列(name,age) 要逐行回表
+------+----------+-------+-------+

-- 延迟关联:
+----+---------+------------+--------+----------+---------+-------------+
| id | table   | type   | key      | ref   | rows  | Extra       |
+----+---------+------------+--------+----------+---------+-------------+
|  1 | <derived2> | ALL  | NULL     | NULL  | 18030 | NULL        |
|  1 | a          | eq_ref | PRIMARY  | b.id  |     1 | NULL        |   ← 只对 20 行回表
|  2 | up2        | ref    | idx_city | const | 18030 | Using index |   ← 子查询覆盖索引，不回表
+----+---------+------------+--------+----------+---------+-------------+
```

观察到的关键事实：

- 延迟关联的**子查询那一行 `Extra: Using index`**——翻页过程只在 idx_city 上走，**不回表**；外层 `a` 表对最终 20 个主键做 `eq_ref` 回表，**只回 20 次**。
- 直接写法没有 `Using index`，意味着翻页过程中走到的行都要按 idx_city 里的主键**回表取 name/age**。offset 越大，这笔回表浪费越大。

诚实的计时结果：本机这张表 5 万行、且已全缓存在 Buffer Pool，两种写法跑出来都在 ~1.2ms，**差距不明显**。这恰恰是个重要提醒——

## ⚠️ 预期 vs 实机落差

- EXPLAIN 的**结构差异是真实且确定的**（子查询 `Using index` vs 直接回表），但**本机小数据 + 全缓存下，墙钟时间几乎一样**。延迟关联真正拉开差距的条件是：① 行**宽**（回表代价大）；② 数据**没全在内存**（每次回表是一次随机 IO）；③ offset **更大**。三者满足时，延迟关联能从几百 ms 降到几 ms。
- 这条 scenario 的真正价值：**别被一次微基准骗了**——要从执行计划（少回表 40000 次 vs 回表 20 次）判断优化是否成立，而不是只看本地缓存命中后的耗时。生产上深翻页的标准解法仍是：延迟关联，或更彻底的**游标翻页**（`WHERE id > last_id ORDER BY id LIMIT n`，把 `LIMIT offset` 彻底干掉）。
- 附带踩到的坑：`city='Taipei'` 只有 1 万行，`LIMIT 40000,20` 的 offset 已经超过匹配行数（结果为空），所以计时更不具代表性——你后续可以把 WHERE 去掉、或换 offset=8000 再量一次真实差距。

## 连到的面试卡

- `99-interview-cards/q-deep-pagination.md`
