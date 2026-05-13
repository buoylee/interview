# Scenario 05: 隐式类型转换让索引失效

## 我想验证的问题

`user_profile.email` 是 VARCHAR(128) 且有索引。
- Q1: `WHERE email = 'a@x.com'` — 走索引吗？
- Q2: `WHERE email = 100` — 走索引吗？type 列是什么？
- Q3: 反例：表 `t(id VARCHAR(10), idx)` 然后 `WHERE id = 100` —— 走索引吗？

## 预期（基于 ch03 §3.7 推算）

按 §3.7「隐式类型转换」：当 WHERE 条件的字面值类型与列类型不同时，MySQL 会对**列**做 CONVERT 才能比较，索引建立在原始列值上，函数/转换后的值无法利用索引。

- **Q1** `WHERE email='u1@x.com'`：字面值是字符串，与 VARCHAR 列类型一致，直接走 idx_email，type=ref。
- **Q2** `WHERE email=100`：字面值是整数，email 是 VARCHAR；MySQL 规则：比较 VARCHAR 和 INT 时，VARCHAR 列被隐式转换为浮点数（`CONVERT(email, DOUBLE)`），索引失效，type=ALL。
- **Q3** `WHERE id=100`（id 是 VARCHAR PRIMARY KEY）：同样是 VARCHAR=INT，VARCHAR 列被转换，连主键索引也失效，type=ALL。
- 规则一句话：当**传入值类型（数字）与列类型（字符串）不一致**时，MySQL 将列转换为数字类型，索引建立在原始值上而非转换后，导致无法 B+ 树定位，索引失效。

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

```
-- Q1: EXPLAIN SELECT * FROM user_profile WHERE email='u1@x.com';
type=ref  key=idx_email  key_len=514  rows=1  Extra=NULL

-- Q2: EXPLAIN SELECT * FROM user_profile WHERE email=100;
type=ALL  key=NULL  rows=1000  Extra=Using where
SHOW WARNINGS:
  Warning 1739: Cannot use ref access on index 'idx_email' due to type or collation conversion on field 'email'
  Warning 1739: Cannot use range access on index 'idx_email' due to type or collation conversion on field 'email'

-- Q3: EXPLAIN SELECT * FROM varchar_id_test WHERE id=100;
type=ALL  key=NULL  rows=3  Extra=Using where
SHOW WARNINGS:
  Warning 1739: Cannot use ref access on index 'PRIMARY' due to type or collation conversion on field 'id'
  Warning 1739: Cannot use range access on index 'PRIMARY' due to type or collation conversion on field 'id'
```

|   | type | key | rows | warnings |
|---|---|---|---|---|
| Q1 | ref | idx_email | 1 | 无 |
| Q2 | ALL | NULL | 1000 | 1739: 类型转换导致无法用 ref/range 访问 idx_email |
| Q3 | ALL | NULL | 3 | 1739: 类型转换导致无法用 ref/range 访问 PRIMARY |

## ⚠️ 预期 vs 实机落差

- 预期完全对上了：Q1 走索引，Q2/Q3 不走索引，且 MySQL 8.0 直接通过 Warning 1739 明确报告了原因。
- 特别值得注意的是 Q3：连 PRIMARY KEY 也失效了。VARCHAR 主键传入整数，主键索引照样失效，退化为全表扫（虽然只有 3 行，但机制与大表完全一样）。
- 我学到：MySQL 8.0 的 `Warning 1739` 是隐式类型转换的明确信号——一旦看到这个警告，立刻检查 WHERE 条件的值类型是否与列类型匹配；ORM 框架经常忘记加引号，导致生产慢查询。

## 连到的面试卡

- `99-interview-cards/q-when-does-index-fail.md`
