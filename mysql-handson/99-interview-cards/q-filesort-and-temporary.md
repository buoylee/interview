# `Using filesort` 和 `Using temporary` 什么时候出现？怎么消掉？

## 一句话回答

**`Using filesort`** = 优化器拿不到「索引天然有序」的结果，得自己排一遍（`ORDER BY`/`GROUP BY` 的列没可用索引时触发）；**`Using temporary`** = 需要中间结果汇聚，建了一张临时表（`GROUP BY`/`DISTINCT`/某些 `UNION`/派生表）。两者的统一解法都是：**给排序/分组键建合适索引**，让 MySQL 边扫索引边出结果，两个标志一起消失。

## 要点

- **`Using filesort` ≠ 落磁盘**：名字里的 "file" 是历史包袱。真落盘看 `Sort_merge_passes > 0`；装得下 `sort_buffer_size` 就是纯内存排（`Sort_merge_passes=0`）。
- 临时表超过 `tmp_table_size`/`max_heap_table_size` 会从内存落到**磁盘临时表**（`Created_tmp_disk_tables` 增长）——真正的性能悬崖。
- 实测：`GROUP BY age`（无索引）→ `Using temporary; Using filesort`；`GROUP BY city`（有索引）→ `Using index`，两者都没了。

## 证据链接

- filesort 触发 + Sort 状态确认：[ch08 Scenario 01](../08-sql-tuning/scenarios/01-filesort-trigger-and-status.md)
- Using temporary 被索引消除：[ch08 Scenario 02](../08-sql-tuning/scenarios/02-using-temporary-trigger.md)
- 章节原理：[ch08 §3.3 / §3.4](../08-sql-tuning/README.md)

## 易追问的延伸

- **Q: 看到 `Using filesort` 一定要优化吗？** → 不一定，先看 `Sort_merge_passes` 和 `Sort_rows`；小排序 + 命中内存其实很快。
- **Q: `Using index` 和 `Using index condition` 区别？** → 前者是覆盖索引（不回表）；后者是索引下推 ICP（在引擎层先过滤再回表）。
