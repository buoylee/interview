# Scenario 01: 一条 SELECT 的旅程——用 performance_schema 看各阶段耗时

## 我想验证的问题

ch01 讲「一条 SQL 从连接器 → 分析器 → 优化器 → 执行器」。这条旅程能不能**真的量出来**？每个阶段各花多少时间？是不是「优化」最耗时？

## 预期（基于 ch01 §3 推算）

`performance_schema` 的 `events_stages_*` 表记录了语句执行经过的每个内部阶段（stage）。预期能看到：打开表、检查权限、统计信息、优化、执行、清理等阶段，且**优化（optimizing）应该占不小比例**（毕竟它要选索引、估成本）。

## 环境

- 表 `up2`，开启 stage 级 instrument 和 consumer

## 步骤

```sql
-- 打开 stage 采集
UPDATE performance_schema.setup_instruments
   SET ENABLED='YES', TIMED='YES' WHERE NAME LIKE 'stage/sql/%';
UPDATE performance_schema.setup_consumers
   SET ENABLED='YES' WHERE NAME LIKE 'events_stages%';

-- 跑一条查询
SELECT COUNT(*) FROM up2 WHERE city='Big' AND age>20;

-- 看它经过的各阶段耗时
SELECT EVENT_NAME, TRUNCATE(TIMER_WAIT/1000000,1) AS us
FROM performance_schema.events_stages_history_long
ORDER BY TIMER_START DESC LIMIT 15;
```

## 实机告诉我（本机实测，MySQL 8.0.36）

```
EVENT_NAME                        us
stage/sql/starting               47.7    ← 连接器交接、语句初始化
stage/sql/checking permissions    2.5    ← 权限检查(语义分析的一部分)
stage/sql/Opening tables         69.8    ← 打开表、拿元数据/MDL
stage/sql/init                    1.0
stage/sql/System lock             1.6
stage/sql/optimizing              4.0    ← 优化器选计划
stage/sql/statistics             66.1    ← 优化器取索引统计估成本 ★
stage/sql/preparing              14.4    ← 生成执行计划
stage/sql/executing               4.5    ← 真正执行(本例 COUNT 很快)
stage/sql/end                     0.3
stage/sql/query end               2.4
stage/sql/freeing items          12.2
stage/sql/cleaning up             0.1
```

观察到的关键事实：

- 这条旅程的耗时大头是 **`Opening tables`（70us）和 `statistics`（66us）**，**不是** `optimizing`（仅 4us）。
- `statistics` 阶段才是优化器真正的开销——它要去 `mysql.innodb_index_stats` 取索引基数来估成本（对应 [ch04 Scenario 01](../../04-execution-and-explain/scenarios/01-plan-flips-by-selectivity.md) 里那套 cost 估算）。`optimizing` 只是拿统计结果挑路，反而很快。
- `Opening tables` 含拿元数据锁（MDL）和表定义缓存——表多、表定义缓存（`table_open_cache`）不够时这步会更慢。
- `executing` 在本例只有 4.5us，因为 `COUNT` 走得快；复杂查询这里才是大头。

## ⚠️ 预期 vs 实机落差

- 落差明显：原以为「优化」最耗时，实测 **`optimizing` 只占 4us，真正的成本在「取统计（statistics）」和「打开表（Opening tables）」**。把「优化器慢」简单等同于「optimizing 阶段慢」是误区。
- 直接可用：线上某条简单 SQL 莫名慢，但 `EXPLAIN` 又很正常时，用 `events_stages_history_long` 看它**卡在哪个 stage**——卡 `Opening tables`/`Waiting for table metadata lock` = MDL 被长事务/DDL 堵（ch06 §3.2）；卡 `statistics` = 统计信息有问题或表太多。这是「EXPLAIN 正常却慢」的定位入口。

## 连到的面试卡

- `99-interview-cards/q-sql-journey-stages.md`
