# Scenario 01: filesort 什么时候触发，怎么从 status 确认

## 我想验证的问题

`Using filesort` 到底什么时候出现？是不是「排序就一定走 filesort」？怎么从 `SHOW STATUS` 的 `Sort_*` 指标确认它真的排了、排了多少、有没有用到磁盘？

## 预期（基于 ch08 §3.4 推算）

`Using filesort` ≠ 一定写磁盘文件，它的意思是「**优化器没法靠索引顺序拿到结果，得自己排一遍**」。

- `ORDER BY` 的列**没有可用索引** → filesort。
- 排序量小、装得下 `sort_buffer_size` → 预期在**内存**里排，`Sort_merge_passes` 增量为 0。
- 排序量大、超过 buffer → 分块排好写临时文件再归并，`Sort_merge_passes` 增量大于 0（说明发生了外部归并，要警惕）。

预期：对无索引列 `age` 排序会出现 `Using filesort`、`type=ALL`；因为只取 20 行，预期内存足够，`Sort_merge_passes` 增量为 0。

## 环境

- 表 `up2`，5 万行，`age` **无索引**

## 先分清 `SHOW STATUS` 的统计范围

`SHOW STATUS LIKE 'Sort%'` 默认等价于 `SHOW SESSION STATUS LIKE 'Sort%'`，返回的是 **当前物理连接的累计值**，不是上一条 SQL 的指标：

```text
连接建立
├─ SQL A 产生 2 次 merge pass
├─ SQL B 产生 0 次 merge pass
└─ SQL C 产生 1 次 merge pass

SHOW SESSION STATUS → Sort_merge_passes = 3
```

`LIKE 'Sort%'` 只匹配状态变量名称，不会筛选 SQL。要把增量归因到目标 SQL，需要满足：

1. 前后检查使用同一个物理连接。
2. 两次检查之间只执行目标 SQL。
3. 计算 `after - before`，或者像本实验一样先用 `FLUSH STATUS` 清零当前 session。

`SHOW GLOBAL STATUS` 是整个实例所有连接的汇总，只适合看整体趋势，不能直接证明某条 SQL 发生了磁盘归并。

## 步骤

```sql
EXPLAIN SELECT id,name,age FROM up2 ORDER BY age LIMIT 20;

-- 个人实验环境：清零当前连接的 session status
-- 生产环境更适合记录前后值并计算差值
FLUSH STATUS;
SELECT id,name,age FROM up2 ORDER BY age LIMIT 20;
SHOW SESSION STATUS LIKE 'Sort%';
```

`FLUSH STATUS` 需要 `FLUSH_STATUS` 或 `RELOAD` 权限，并会写入 binary log；不要为了测一条生产 SQL 随意执行。连接池或 GUI 若在三条语句之间切换物理连接，本实验结果也无效。

## 实机告诉我（本机实测，MySQL 8.0.36）

```
-- EXPLAIN:
+------+-------+------+------+-------+----------------+
| type | key   | rows | ...                          |
+------+-------+------+------+-------+----------------+
| ALL  | NULL  | 50261| ...  Extra: Using filesort    |
+------+-------+------+------+-------+----------------+

-- SHOW SESSION STATUS LIKE 'Sort%'（FLUSH STATUS 后只跑了目标 SELECT）:
Sort_merge_passes   0      ← 这个观察窗口没有发生归并轮次
Sort_range          0
Sort_rows           20     ← 排序产出 20 行
Sort_scan           1      ← 全表扫一遍喂给排序
```

观察到的关键事实：

- `type=ALL` + `Using filesort`：`age` 无索引，只能全表扫 5 万行、再排序。
- `Sort_merge_passes=0`：由于前面已经清零，而且中间只执行了目标 SELECT，所以可以把这个 0 归因到目标 SQL；它表示没有发生临时文件归并轮次。若要严格确认 filesort 创建了多少临时文件，应查看 optimizer trace 的 `filesort_summary.number_of_tmp_files`。
- `Sort_scan=1`：用「全表扫 → 排序」的方式（不是走索引 range 喂排序）。

## ⚠️ 预期 vs 实机落差

- 预期对上，但纠正了两个常见误解：**`Using filesort` 不等于「写磁盘文件」；`Sort_merge_passes` 也不代表上一条 SQL，它默认是当前 session 的累计计数器**。
- 优化方向（接 ch08 §3.4）：
  - 给 `ORDER BY` 的列建索引，让结果**直接按索引顺序出**，`Using filesort` 消失（这是首选）。
  - 改不了索引时，若同一连接里的 `Sort_merge_passes` 增量持续大于 0，再结合并发量评估 `sort_buffer_size`；它是 per-session buffer，不能只为一条 SQL 全局调大。
  - 配合 `LIMIT` + 覆盖索引，能让优化器走「单次扫描 + 优先队列」的小顶堆，避免全量排序。

如果不能执行 `FLUSH STATUS`，用前后快照代替：

```sql
-- before，例如 Sort_merge_passes = 3
SHOW SESSION STATUS LIKE 'Sort_merge_passes';

SELECT id,name,age FROM up2 ORDER BY age LIMIT 20;

-- after，例如仍为 3；目标 SQL 增量为 0
SHOW SESSION STATUS LIKE 'Sort_merge_passes';
```

要直接定位最近哪些 SQL 产生了 merge pass，可以查询逐语句指标（前提是 consumer 已启用）：

```sql
SELECT
    THREAD_ID,
    EVENT_ID,
    LEFT(SQL_TEXT, 200) AS sql_text,
    SORT_MERGE_PASSES,
    SORT_ROWS
FROM performance_schema.events_statements_history_long
WHERE SORT_MERGE_PASSES > 0
ORDER BY TIMER_START DESC
LIMIT 20;
```

## 连到的面试卡

- `99-interview-cards/q-filesort-and-temporary.md`
