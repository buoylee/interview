# Scenario 02: `Using temporary` 什么时候出现，索引怎么把它消掉

## 我想验证的问题

`GROUP BY` 一定会用临时表（`Using temporary`）吗？同样是 `GROUP BY`，分组列「有索引」和「没索引」的执行计划差多少？

## 预期（基于 ch08 §3.4 推算）

`GROUP BY`/`DISTINCT` 需要把数据按分组键聚到一起。

- 分组键**没索引** → MySQL 建一张**临时表**做分组累加，`Using temporary`；通常还伴随 `Using filesort`（结果再排序）。
- 分组键**有索引**（B+ 树本就有序）→ 可以**边扫索引边分组**，省掉临时表，`Extra` 变成 `Using index`（覆盖）这类。

预期：`GROUP BY age`（无索引）出现 `Using temporary; Using filesort`；`GROUP BY city`（有 `idx_city`）则不需要临时表。

## 环境

- 表 `up2`：`age` 无索引，`city` 有 `idx_city`

## 步骤

```sql
EXPLAIN SELECT age,  COUNT(*) c FROM up2 GROUP BY age  ORDER BY c DESC LIMIT 5;   -- 无索引列
EXPLAIN SELECT city, COUNT(*) c FROM up2 GROUP BY city;                            -- 有索引列
```

## 实机告诉我（本机实测，MySQL 8.0.36）

```
-- GROUP BY age（age 无索引）:
+------+------+-------+-----------------------------------+
| type | key  | rows  | Extra                             |
+------+------+-------+-----------------------------------+
| ALL  | NULL | 50261 | Using temporary; Using filesort   |   ← 临时表 + 排序
+------+------+-------+-----------------------------------+

-- GROUP BY city（city 有 idx_city）:
+-------+----------+-------+-------------+
| type  | key      | rows  | Extra       |
+-------+----------+-------+-------------+
| index | idx_city | 50261 | Using index |   ← 走索引，无临时表、无 filesort
+-------+----------+-------+-------------+
```

观察到的关键事实：

- 同样是 `GROUP BY`，**唯一的差别是分组列有没有索引**：`age` 触发 `Using temporary; Using filesort`，`city` 直接 `Using index`。
- `city` 版本 `type=index`（扫整棵 idx_city），虽然也扫 5 万行，但**有序扫 + 边扫边聚合**，省掉了「建临时表 + 最后排序」两个重活。

## ⚠️ 预期 vs 实机落差

- 预期对上。把 `Using temporary` 和「分组/去重键没索引」直接挂钩，比死记「什么时候用临时表」清楚得多。
- 优化套路（ch08 §3.4）：
  - 给 `GROUP BY`/`DISTINCT`/`ORDER BY` 的键建合适索引，把 `Using temporary; Using filesort` 同时消掉。
  - 临时表大到超过 `tmp_table_size`/`max_heap_table_size` 会从内存 `MEMORY` 引擎**落到磁盘临时表**（`Created_tmp_disk_tables` 增长），那是真正的性能悬崖——监控这个状态变量。
  - `GROUP BY` 不需要排序时，加 `ORDER BY NULL`（8.0 已默认不隐式排序，但老习惯仍值得知道）能省掉无谓的 filesort。

## 连到的面试卡

- `99-interview-cards/q-filesort-and-temporary.md`
