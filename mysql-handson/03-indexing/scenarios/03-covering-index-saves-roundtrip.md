# Scenario 03: 覆盖索引省回表

## 我想验证的问题

同样一条 `SELECT name, age FROM user_profile WHERE city='Taipei'`：
- 索引 A：`(city)`
- 索引 B：`(city, name, age)`（覆盖了 SELECT 列表）

走 A 和走 B 的 explain 有什么差别？性能差多少？

## 预期

> 填空：
> - 索引 A 的 Extra 会显示 ……
> - 索引 B 的 Extra 会显示 ……
> - 回表代价大约是几次随机 IO？
> - 性能差大概几倍？

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
<两次 explain 的 Extra 行>
<计时对比>
```

## ⚠️ 预期 vs 实机落差

- ...

## 连到的面试卡

- `99-interview-cards/q-why-bplus-tree.md`
