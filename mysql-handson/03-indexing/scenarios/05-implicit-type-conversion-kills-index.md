# Scenario 05: 隐式类型转换让索引失效

## 我想验证的问题

`user_profile.email` 是 VARCHAR(128) 且有索引。
- Q1: `WHERE email = 'a@x.com'` — 走索引吗？
- Q2: `WHERE email = 100` — 走索引吗？type 列是什么？
- Q3: 反例：表 `t(id VARCHAR(10), idx)` 然后 `WHERE id = 100` —— 走索引吗？

## 预期

> 填空：
> - Q1 走索引 / type=___
> - Q2 走 / 不走？为什么？
> - Q3 走 / 不走？为什么？
> - 规则一句话：当 _________ 时索引失效，因为 ……

## 环境

- 沿用 user_profile，先建 email 索引：`ALTER TABLE user_profile ADD INDEX idx_email (email);`
- 额外建对照表：

```sql
CREATE TABLE varchar_id_test (id VARCHAR(10) PRIMARY KEY, payload VARCHAR(20));
INSERT INTO varchar_id_test VALUES ('100','a'),('200','b'),('abc','c');
```

## 步骤

1. `EXPLAIN SELECT * FROM user_profile WHERE email='a@x.com';`
2. `EXPLAIN SELECT * FROM user_profile WHERE email=100;` ← 注意类型对比方向
3. `EXPLAIN SELECT * FROM varchar_id_test WHERE id=100;`
4. `SHOW WARNINGS;` 看是否有 1739/类型转换警告

## 实机告诉我

|   | type | key | rows | warnings |
|---|---|---|---|---|
| Q1 |   |   |   |   |
| Q2 |   |   |   |   |
| Q3 |   |   |   |   |

## ⚠️ 预期 vs 实机落差

- ...

## 连到的面试卡

- `99-interview-cards/q-when-does-index-fail.md`
