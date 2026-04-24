# 阶段 9a：数据库性能学习指南

> 本阶段目标：能从慢接口中识别数据库瓶颈，读懂执行计划，优化索引、事务和连接池。

---

## 学习顺序

| 顺序 | 文件 | 学习重点 |
|------|------|----------|
| 1 | [01-slow-query-analysis.md](./01-slow-query-analysis.md) | 慢查询日志、pt-query-digest、EXPLAIN |
| 2 | [02-index-optimization.md](./02-index-optimization.md) | B+ Tree、联合索引、覆盖索引、索引失效 |
| 3 | [05-query-optimization.md](./05-query-optimization.md) | 查询重写、分页、批量、大表策略 |
| 4 | [03-lock-transaction.md](./03-lock-transaction.md) | 锁等待、死锁、隔离级别、长事务 |
| 5 | [04-connection-pool-monitor.md](./04-connection-pool-monitor.md) | HikariCP、连接泄漏、连接池指标 |

---

## 本阶段主线

数据库排查不要只看 SQL 文本，要看完整链路：

```text
接口慢
→ Trace 中 DB span 慢
→ 慢查询日志确认 SQL
→ EXPLAIN/EXPLAIN ANALYZE 看执行计划
→ 判断索引、锁、连接池或数据量问题
→ 修改后用相同压测复测
```

---

## 最小完成标准

学完后应该能做到：

- 开启并读取慢查询日志
- 对一个慢 SQL 执行 EXPLAIN
- 判断全表扫描、索引失效、filesort、回表等问题
- 设计一个联合索引并解释顺序
- 排查一次锁等待或死锁
- 看懂连接池 active、idle、pending、timeout 指标

---

## 本阶段产物

建议留下：

- 慢查询摘要
- EXPLAIN 前后对比
- 索引设计说明
- 压测前后 P99 / QPS 对比
- 锁或连接池排查记录

---

## 常见误区

| 误区 | 正确做法 |
|------|----------|
| 给每个 where 字段都加索引 | 按查询模式设计联合索引 |
| 小数据集测试正常就上线 | 用接近真实数据量验证 |
| 只优化 SQL 不看连接池 | 慢查询和连接池排队会互相放大 |
| 死锁只看应用异常 | 查看数据库死锁日志和事务语句 |

---

## 下一阶段衔接

阶段 9a 解决数据库。阶段 9b 进入 Redis 和 MQ，它们常与数据库一起构成缓存、异步和一致性问题。

