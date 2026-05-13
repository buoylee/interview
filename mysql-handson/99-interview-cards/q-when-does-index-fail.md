# 索引什么时候会失效？

## 一句话回答

**核心规则**：当 WHERE 条件让索引列发生**变换**（类型转换、函数调用、表达式运算）或破坏**索引顺序**（前导通配 `LIKE '%x'`、最左前缀缺失、OR 跨非索引列）时，索引失效。

## 6 种典型场景

| 场景 | 例子 | 失效原因 |
|---|---|---|
| 隐式类型转换 | `WHERE varchar_col = 100` | MySQL 把列做 CAST，索引列被包装 → Scenario 05 |
| 函数 / 表达式 | `WHERE DATE(t)='2026-01-01'` | 5.7 失效；8.0 可建函数索引补救 |
| 前导通配 | `LIKE '%abc'` | B+ 树无法定位起始页 |
| 最左前缀缺失 | 索引 `(a,b,c)`，`WHERE b=?` | 索引按 a 排序，跳 a 就找不到入口（8.0 有 skip scan 例外） → Scenario 02 |
| OR 跨列 | `WHERE a=? OR x=?`（x 无索引） | 整体退化为全扫；改 UNION ALL |
| 优化器估算不划算 | 小表 / 选择性低 | type=ALL；用 optimizer_trace 看 cost → Scenario 04 末段 |

## 排查 SOP

1. `EXPLAIN` 看 type 和 key
2. type 是 ALL/index？key 是 NULL？→ 索引没走
3. 看 WHERE 是否中招上表 6 种
4. 看 Extra 是否 `Using filesort` / `Using temporary`（不一定是索引问题，但常伴随）
5. `optimizer_trace` 看是不是优化器主动放弃了索引

## 证据链接

- 联合索引最左前缀实测：[Scenario 02](../03-indexing/scenarios/02-leftmost-prefix-violation.md)
- ICP 开关对比（间接影响索引使用率）：[Scenario 04](../03-indexing/scenarios/04-icp-on-off-comparison.md)
- 隐式类型转换实测：[Scenario 05](../03-indexing/scenarios/05-implicit-type-conversion-kills-index.md)
- 章节原理：[03-indexing §3.7](../03-indexing/README.md)

## 易追问的延伸

- **Q: 8.0 的 skip scan 是什么？** → 联合索引 `(a,b)` 上的 `WHERE b=?` 在某些条件下，优化器会枚举 a 的不同值分别扫，比全扫快但比直接走索引慢。看 explain Extra 里的 `Using index for skip scan`。
- **Q: 怎么强制走 / 不走索引？** → `FORCE INDEX(idx)` / `IGNORE INDEX(idx)`；8.0 推荐用 optimizer hint `/*+ INDEX(tbl idx) */`。
- **Q: ANALYZE TABLE 多久跑一次？** → 数据量稳定时不用主动跑，大变化（批量导入 / 删除）后必须跑，让优化器拿到最新统计。
