# Scenario 04: 索引下推（ICP）开关前后对比

## 我想验证的问题

沿用 Scenario 03 建立的索引 `idx_city_name_age (city, name, age)`，SQL：
```sql
SELECT * FROM user_profile WHERE city='Taipei' AND age > 25 AND name LIKE '%a%';
```

`name LIKE '%a%'` 是范围条件，但 `name` **在索引里**——这是 ICP 起作用的前提（索引含但 WHERE 不是等值/不能定位区间的列）。
- ICP 开（默认）：Extra 会是什么？引擎层 vs Server 层各做什么？
- ICP 关：Extra 会变成什么？rows 数字会不会变？读了多少行回去 Server 层过滤？

## 预期

> 填表：

|     | Extra | rows | 谁过滤 name LIKE |
|-----|---|---|---|
| ICP on  |   |   |   |
| ICP off |   |   |   |

## 环境

- 已建索引 `idx_city_name_age (city, name, age)`（来自 Scenario 03）

## 步骤

1. ICP 默认开。跑 `EXPLAIN FORMAT=TREE` + 业务 SQL，记录
2. `SET optimizer_switch='index_condition_pushdown=off';`
3. 同 SQL 再跑 explain，对比
4. 用 `SHOW SESSION STATUS LIKE 'Handler_read%';` 在两种状态下分别跑一次 SELECT，看 Handler_read_next 差几倍
5. 跑完 `SET optimizer_switch='index_condition_pushdown=on';` 还原

## 实机告诉我

|     | Extra | rows | Handler_read_next |
|-----|---|---|---|

## ⚠️ 预期 vs 实机落差

- ...

## 连到的面试卡

- `99-interview-cards/q-when-does-index-fail.md`
