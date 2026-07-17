# Scenario 03: 覆盖索引省回表

## 我想验证的问题

同样一条 `SELECT name, age FROM user_profile WHERE city='Taipei'`：
- 索引 A：`(city)`
- 索引 B：`(city, name, age)`（覆盖了 SELECT 列表）

走 A 和走 B 的 explain 有什么差别？性能差多少？

## 预期（基于 ch03 §3.4 推算）

按 §3.4「覆盖索引」：SELECT 列表只有 name, age，如果这两列都在索引里，就不需要回表。

- 索引 A `(city)` 不含 name 和 age：引擎按 city 找到主键后，必须去聚簇索引再查 name 和 age，Extra 显示 `NULL`（无 Using index），需要约 200 次聚簇索引查找（Taipei 占 200 行）。一次回表不等于一次物理磁盘 IO：命中 Buffer Pool 时是逻辑读，未命中才可能产生磁盘读取。
- 索引 B `(city, name, age)` 覆盖了 SELECT 列表：引擎在二级索引叶子节点上直接拿到 name 和 age，不需要回表，Extra 显示 `Using index`。
- 性能差距没有固定倍数：返回行数越多、行越宽、工作集越冷，覆盖索引的收益通常越大；小数据且全部命中 Buffer Pool 时，差距可能很小。

## 环境

- 接 Scenario 02 的数据（1000+ 行）。若全新环境，先 `make up` + 插入数据。

## 步骤

1. 仅保留单列索引：`ALTER TABLE user_profile DROP INDEX idx_city_age_name, ADD INDEX idx_city (city);`
2. 跑 `EXPLAIN FORMAT=TREE SELECT name, age FROM user_profile WHERE city='Taipei';`，记录 Extra
3. 换成覆盖索引：`ALTER TABLE user_profile DROP INDEX idx_city, ADD INDEX idx_city_name_age (city, name, age);`
4. 同样的 SQL 再跑 explain，对比 Extra
5. 对两个版本预热后交替执行多轮并取分位数，或用 `EXPLAIN ANALYZE` / Performance Schema 比较。MySQL 8.0 已移除 Query Cache，`SQL_NO_CACHE` 没有实际效果；`SHOW PROFILES` 也已废弃，不应用作新的基准方案

## 实机告诉我

```
-- 索引 A：idx_city (city)
EXPLAIN SELECT name, age FROM user_profile WHERE city='Taipei';
type=ref  key=idx_city  key_len=258  rows=200  Extra=NULL

-- 索引 B：idx_city_name_age (city, name, age)
EXPLAIN SELECT name, age FROM user_profile WHERE city='Taipei';
type=ref  key=idx_city_name_age  key_len=258  rows=200  Extra=Using index

-- 当时的单次计时（FORCE INDEX，SHOW PROFILES；仅保留为历史记录）
Query_ID  Duration    Query
1         0.00189025  SELECT SQL_NO_CACHE name, age FROM user_profile FORCE INDEX(idx_city) WHERE city='Taipei'
2         0.00016450  SELECT SQL_NO_CACHE name, age FROM user_profile FORCE INDEX(idx_city_name_age) WHERE city='Taipei'
```

注意：MySQL 8.0 中 `SQL_NO_CACHE` 没有效果，`SHOW PROFILES` 已废弃；上面的 11.5 倍来自微秒级单次样本，只能说明这一次运行，不能作为覆盖索引的通用倍率。

观察：
- 索引 A Extra=`NULL`：走了 idx_city 定位到 city='Taipei'，但 name/age 不在索引里，需要回表 200 次。
- 索引 B Extra=`Using index`：二级索引叶子节点已包含 city+name+age，无需回表。
- 这次单次耗时记录为索引 A 约 1.89ms、索引 B 约 0.16ms；需要多轮、交替、报告分位数后才能形成可靠的性能结论。

## ⚠️ 预期 vs 实机落差

- 执行计划证据对上了：Extra=NULL 对应需要回表，Extra=Using index 对应覆盖索引、无需回表。
- 单次墙钟时间不能证明固定加速倍率。即使数据都在 Buffer Pool，回表仍增加聚簇索引查找和 CPU/锁存开销；只有页未命中时，才进一步体现为随机磁盘 IO。
- 我学到：`Using index` 是覆盖索引起作用的标志，是消除回表最直接的方式；SELECT 列多一个不在索引里的列就会出现回表，**SELECT \* 是覆盖索引的天敌**。

## 连到的面试卡

- `99-interview-cards/q-why-bplus-tree.md`
