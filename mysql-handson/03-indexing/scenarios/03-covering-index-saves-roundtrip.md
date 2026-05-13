# Scenario 03: 覆盖索引省回表

## 我想验证的问题

同样一条 `SELECT name, age FROM user_profile WHERE city='Taipei'`：
- 索引 A：`(city)`
- 索引 B：`(city, name, age)`（覆盖了 SELECT 列表）

走 A 和走 B 的 explain 有什么差别？性能差多少？

## 预期（基于 ch03 §3.4 推算）

按 §3.4「覆盖索引」：SELECT 列表只有 name, age，如果这两列都在索引里，就不需要回表。

- 索引 A `(city)` 不含 name 和 age：引擎按 city 找到主键后，必须去聚簇索引再查 name 和 age，Extra 显示 `NULL`（无 Using index），需要回表约 200 次随机 IO（Taipei 占 200 行）。
- 索引 B `(city, name, age)` 覆盖了 SELECT 列表：引擎在二级索引叶子节点上直接拿到 name 和 age，不需要回表，Extra 显示 `Using index`。
- 性能差距：回表是随机 IO，预计索引 B 比索引 A 快 **5-20 倍**（具体取决于 buffer pool 命中率；热数据在内存里差距会缩小）。

## 环境

- 接 Scenario 02 的数据（1000+ 行）。若全新环境，先 `make up` + 插入数据。

## 步骤

1. 仅保留单列索引：`ALTER TABLE user_profile DROP INDEX idx_city_age_name, ADD INDEX idx_city (city);`
2. 跑 `EXPLAIN FORMAT=TREE SELECT name, age FROM user_profile WHERE city='Taipei';`，记录 Extra
3. 换成覆盖索引：`ALTER TABLE user_profile DROP INDEX idx_city, ADD INDEX idx_city_name_age (city, name, age);`
4. 同样的 SQL 再跑 explain，对比 Extra
5. 对两个版本各跑 `BENCHMARK(1000, ...)` 或 `SELECT SQL_NO_CACHE ...` 多次取平均

## 实机告诉我

```
-- 索引 A：idx_city (city)
EXPLAIN SELECT name, age FROM user_profile WHERE city='Taipei';
type=ref  key=idx_city  key_len=258  rows=200  Extra=NULL

-- 索引 B：idx_city_name_age (city, name, age)
EXPLAIN SELECT name, age FROM user_profile WHERE city='Taipei';
type=ref  key=idx_city_name_age  key_len=258  rows=200  Extra=Using index

-- 计时（SQL_NO_CACHE，FORCE INDEX，SHOW PROFILES）
Query_ID  Duration    Query
1         0.00189025  SELECT SQL_NO_CACHE name, age FROM user_profile FORCE INDEX(idx_city) WHERE city='Taipei'
2         0.00016450  SELECT SQL_NO_CACHE name, age FROM user_profile FORCE INDEX(idx_city_name_age) WHERE city='Taipei'
```

观察：
- 索引 A Extra=`NULL`：走了 idx_city 定位到 city='Taipei'，但 name/age 不在索引里，需要回表 200 次。
- 索引 B Extra=`Using index`：二级索引叶子节点已包含 city+name+age，无需回表。
- 耗时：索引 A 约 1.89ms，索引 B 约 0.16ms，**覆盖索引快约 11.5 倍**。

## ⚠️ 预期 vs 实机落差

- 预期对上了：Extra=NULL 对应有回表，Extra=Using index 对应无回表。
- 性能差距实测 ~11.5 倍，落在预期 5-20 倍区间内。关键是即使 200 行在 buffer pool 里（热数据），回表的代价仍然显著——每次回表都要通过聚簇索引再查一次，增加了额外的 B+ 树遍历。
- 我学到：`Using index` 是覆盖索引起作用的标志，是消除回表最直接的方式；SELECT 列多一个不在索引里的列就会出现回表，**SELECT \* 是覆盖索引的天敌**。

## 连到的面试卡

- `99-interview-cards/q-why-bplus-tree.md`
