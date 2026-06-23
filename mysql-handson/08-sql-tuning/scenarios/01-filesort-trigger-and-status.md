# Scenario 01: filesort 什么时候触发，怎么从 status 确认

## 我想验证的问题

`Using filesort` 到底什么时候出现？是不是「排序就一定走 filesort」？怎么从 `SHOW STATUS` 的 `Sort_*` 指标确认它真的排了、排了多少、有没有用到磁盘？

## 预期（基于 ch08 §3.3 推算）

`Using filesort` ≠ 一定写磁盘文件，它的意思是「**优化器没法靠索引顺序拿到结果，得自己排一遍**」。

- `ORDER BY` 的列**没有可用索引** → filesort。
- 排序量小、装得下 `sort_buffer_size` → 在**内存**里排，`Sort_merge_passes=0`。
- 排序量大、超过 buffer → 分块排好写临时文件再归并，`Sort_merge_passes>0`（这才是真的落磁盘，要警惕）。

预期：对无索引列 `age` 排序会出现 `Using filesort`、`type=ALL`；因为只取 20 行，内存够，`Sort_merge_passes=0`。

## 环境

- 表 `up2`，5 万行，`age` **无索引**

## 步骤

```sql
EXPLAIN SELECT id,name,age FROM up2 ORDER BY age LIMIT 20;

FLUSH STATUS;
SELECT id,name,age FROM up2 ORDER BY age LIMIT 20;
SHOW STATUS LIKE 'Sort%';
```

## 实机告诉我（本机实测，MySQL 8.0.36）

```
-- EXPLAIN:
+------+-------+------+------+-------+----------------+
| type | key   | rows | ...                          |
+------+-------+------+------+-------+----------------+
| ALL  | NULL  | 50261| ...  Extra: Using filesort    |
+------+-------+------+------+-------+----------------+

-- SHOW STATUS LIKE 'Sort%'（跑完那条 SELECT 后）:
Sort_merge_passes   0      ← 没有归并轮次 = 没落磁盘，纯内存排
Sort_range          0
Sort_rows           20     ← 排序产出 20 行
Sort_scan           1      ← 全表扫一遍喂给排序
```

观察到的关键事实：

- `type=ALL` + `Using filesort`：`age` 无索引，只能全表扫 5 万行、再排序。
- `Sort_merge_passes=0`：虽然写着 filesort，但**没碰磁盘**——sort buffer 装得下。这条很重要：**看到 `Using filesort` 先别慌，要看 `Sort_merge_passes` 是不是 >0 才判断有没有磁盘代价**。
- `Sort_scan=1`：用「全表扫 → 排序」的方式（不是走索引 range 喂排序）。

## ⚠️ 预期 vs 实机落差

- 预期对上，但纠正了一个常见误解：**`Using filesort` 不等于「写磁盘文件」**。名字里的 "file" 是历史包袱，真实是否落盘看 `Sort_merge_passes`。
- 优化方向（接 ch08 §3.3）：
  - 给 `ORDER BY` 的列建索引，让结果**直接按索引顺序出**，`Using filesort` 消失（这是首选）。
  - 改不了索引时，若 `Sort_merge_passes>0`，调大 `sort_buffer_size` 把排序留在内存（注意是 per-connection，别设太大，见 ch01）。
  - 配合 `LIMIT` + 覆盖索引，能让优化器走「单次扫描 + 优先队列」的小顶堆，避免全量排序。

## 连到的面试卡

- `99-interview-cards/q-filesort-and-temporary.md`
