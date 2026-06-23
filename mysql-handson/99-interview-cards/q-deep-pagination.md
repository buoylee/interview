# `LIMIT 大offset` 深翻页为什么慢？怎么优化？

## 一句话回答

`LIMIT offset, n` 要**真的走到第 offset+n 行**，前面 offset 行白读又丢；走二级索引还要 `SELECT` 索引外列时，**前面每一行都回表一次**，offset 越大浪费越大。两种解法：**① 延迟关联**（先在覆盖索引上翻页只取主键、不回表，再用这 n 个主键 JOIN 回表，只回表 n 次）；**② 游标翻页**（`WHERE id > last_id ORDER BY id LIMIT n`，把 `LIMIT offset` 彻底干掉，最优）。

## 要点

- 延迟关联的关键：子查询那一步 EXPLAIN 是 `Using index`（覆盖、不回表），最后只对 n 行做主键 `eq_ref` 回表。
- 优化是否成立要**看执行计划**（少回表 offset 次 → n 次），别被「本地全缓存下微基准差不多」骗了——行宽、冷缓存、大 offset 时差距才显现。
- 游标翻页缺点：不能跳页（只能上一页/下一页），但对「无限下拉」场景最佳。

## 证据链接

- EXPLAIN 对比延迟关联只回表 20 次 + 微基准为何骗人的诚实记录：[ch08 Scenario 03](../08-sql-tuning/scenarios/03-deep-pagination-deferred-join.md)
- 章节原理：[ch08 §3.6](../08-sql-tuning/README.md)

## 易追问的延伸

- **Q: 游标翻页遇到 ORDER BY 非唯一列怎么办？** → 用「排序列 + 主键」组合做游标（`WHERE (sort_col, id) > (?, ?)`），保证全局唯一稳定。
- **Q: 为什么不直接缓存总页？** → 深翻页本身是产品问题，第 2000 页几乎没人看；能改交互（搜索/筛选/游标）就别硬翻。
