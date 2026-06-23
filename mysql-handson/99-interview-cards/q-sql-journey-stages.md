# 一条 SQL 在 MySQL 内部经过哪些阶段？哪个最耗时？

## 一句话回答

连接器 → 分析器（解析 + 语义/权限检查）→ 优化器（取统计 + 估成本 + 选计划）→ 执行器（调存储引擎）。可用 `performance_schema.events_stages_history_long` 把每个 stage 的耗时量出来。**反直觉的实测结论：最耗时的常不是 `optimizing`，而是 `Opening tables`（拿元数据/MDL）和 `statistics`（取索引统计估成本）**——`optimizing` 本身只是拿统计结果挑路，很快。

## 要点

- 实测一条简单 SELECT：`Opening tables`≈70us、`statistics`≈66us，而 `optimizing` 仅 ≈4us。
- `statistics` 阶段才是优化器的真实开销（去 `mysql.innodb_index_stats` 取基数）。
- 「EXPLAIN 正常却慢」时，用 stage 耗时定位卡在哪：卡 `Opening tables`/`metadata lock` = MDL 被堵；卡 `statistics` = 统计/表数量问题。

## 证据链接

- 实测各 stage 耗时分解：[ch01 Scenario 01](../01-architecture/scenarios/01-sql-journey-stage-timing.md)
- 章节原理：[ch01 §3](../01-architecture/README.md)

## 易追问的延伸

- **Q: 为什么 8.0 去掉了 Query Cache？** → 缓存失效成本高（任何写都让整表缓存失效）、并发下是瓶颈；8.0 直接移除。
- **Q: `Opening tables` 慢怎么办？** → 调大 `table_open_cache`/`table_definition_cache`；排查是否有长事务/DDL 持 MDL（ch06 §3.2）。
