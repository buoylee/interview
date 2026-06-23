# EXPLAIN 的计划是固定的吗？「高选择性就走全表扫」对吗？

## 一句话回答

不固定。优化器是**基于成本**选计划，同一条 SQL 的 `type`/`key` 由「**这一刻的数据分布 + 统计信息**」决定——数据涨了、分布变了，原本走索引的 SQL 可能突然全表扫。但「命中超过 20-30% 就走全表扫」是**迷思**：实测 MySQL 8.0 对窄行、假设页已缓存的表**极其黏索引**，命中 96% 仍走 `ref`，因为成本模型算出来「索引 + 回表」还是比全表扫便宜。

## 要点

- 实测 up2：`city='Rare'`(10 行) 和 `city='Big'`(48000 行,96%) **都走 `ref idx_city`**，从没翻 `ALL`。
- optimizer_trace：全表扫 cost=17589 vs 索引 cost=2633——成本模型默认回表廉价（页在 BP），所以索引一直赢。
- 真翻全表扫的条件不是「命中百分比阈值」，而是**回表真的变贵**（行宽 / 缓存冷 / 随机 IO）。

## 证据链接

- 实测「选择性到 96% 计划仍没翻」+ trace 成本：[ch04 Scenario 01](../04-execution-and-explain/scenarios/01-plan-flips-by-selectivity.md)
- 章节原理：[ch04 §3.4](../04-execution-and-explain/README.md)

## 易追问的延伸

- **Q: 计划怎么会选错？** → 统计过期（`mysql.innodb_index_stats` 采样旧）→ `rows` 估歪 → 选错；`ANALYZE TABLE` 刷新。实测 48000 行被估成 25090，说明估算可以很不准。
- **Q: 怎么判断该不该 FORCE INDEX？** → 先 `optimizer_trace` 看两条路真实 cost，搞清楚它为什么这么选，再决定，别无脑加 hint。
