# Scenario 01: 选择性变了，计划却没翻——8.0 优化器有多「黏」索引

## 我想验证的问题

`SELECT * FROM up2 WHERE city = ?`，`city` 上有索引。教科书常说「命中行数超过 20~30% 优化器就会放弃索引走全表扫」。真的吗？把命中比例从 10 行一路推到 96%，看 `type` 到底什么时候从 `ref` 翻成 `ALL`。

## 预期（基于 ch04 §3.4 + 常见说法）

走二级索引要逐行**回表**（随机 IO）；命中行数太多时「索引 + 大量回表」比「全表顺序扫」还贵，优化器应该弃用索引走全扫。

预期：

- `city='Rare'`（10 行）→ `type=ref`。
- 命中 ~20-30% → 翻成 `type=ALL`。
- 命中 96% → 铁定 `type=ALL`。

## 环境

- 表 `up2`，5 万行，`idx_city(city)`，窄行（id/name/age/city）
- 用 `UPDATE` 改变 `city` 分布制造不同选择性，每次 `ANALYZE TABLE` 刷新统计

## 步骤

```sql
-- 制造偏斜：96% 行是 'Big'，10 行是 'Rare'
UPDATE up2 SET city='Big'  WHERE id > 2000;
UPDATE up2 SET city='Rare' WHERE id <= 10;
ANALYZE TABLE up2;

EXPLAIN SELECT * FROM up2 WHERE city='Big';    -- 命中 ~96%
EXPLAIN SELECT * FROM up2 WHERE city='Rare';   -- 命中 10 行

-- 看成本估算
SET optimizer_trace='enabled=on';
SELECT * FROM up2 WHERE city='Big' LIMIT 1;
SELECT TRACE FROM information_schema.OPTIMIZER_TRACE\G
```

## 实机告诉我（本机实测，MySQL 8.0.36）

```
-- 分布：Big=48000(96%), 其余 5 城各 ~398, Rare=10

-- city='Big'（命中 48000，96%）:
type=ref  key=idx_city  rows=25090  Extra=NULL      ← 居然还是 ref！没翻 ALL
-- city='Rare'（命中 10）:
type=ref  key=idx_city  rows=10     Extra=NULL

-- optimizer_trace（city='Big'）:
table_scan:  rows=50251, cost=17589.8        chosen=false
range/ref :  rows=25090, cost=2633.25        chosen=true     ← 索引成本只有全扫的 1/6.7
```

观察到的关键事实：

- **从 10 行到 48000 行（96%），`type` 始终是 `ref`，一次都没翻成 `ALL`。** 教科书的「20-30% 就全扫」在这张表上根本不成立。
- optimizer_trace 给了原因：全表扫成本 17589，走索引（含回表）成本只算 2633——**优化器的成本模型默认「页都在 Buffer Pool 里、回表是廉价随机访问」**，于是窄行小表回表 4.8 万次仍比全扫便宜，索引一直赢。
- 有意思的细节：命中 48000 行，`rows` 却估成 25090（统计采样 + 索引统计的粗估），但**这不影响它选 ref**——两条路成本差太远，估歪了也不改结论。

## ⚠️ 预期 vs 实机落差

- **最大的落差**：预期会翻 ALL，实机一路守着索引。结论要改写：**「高选择性必走全表扫」是个迷思**；8.0 优化器对窄行、且假设页已缓存的表，**极其「黏」索引**。
- 那它什么时候才真翻 ALL？当**回表真的变贵**时——行很宽（回表搬的数据多）、或工作集冷（每次回表是真·磁盘随机 IO）。这俩条件下全表顺序扫才会反超。换句话说，会不会翻表取决于**回表的真实代价**，而不是一个固定的「命中百分比阈值」。
- 真正可带走的工程判断：
  - 别背「超过 X% 就全扫」这种硬阈值——用 `optimizer_trace` 看**两条路的真实 cost** 才靠谱。
  - `rows` 是统计采样的估算，可能离真值很远（这里 48000 估成 25090）；怀疑计划选错先 `ANALYZE TABLE` 刷新统计（ch04 §6）。
  - 计划确实不对时再用 `FORCE INDEX`/`IGNORE INDEX`，但先用 trace 搞清楚「优化器为什么这么算」。

## 连到的面试卡

- `99-interview-cards/q-optimizer-cost-plan.md`
