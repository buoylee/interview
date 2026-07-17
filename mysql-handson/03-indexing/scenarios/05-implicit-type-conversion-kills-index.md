# Scenario 05: 隐式类型转换让索引失效

## 我想验证的问题

`user_profile.email` 是 VARCHAR(128) 且有索引。
- Q1: `WHERE email = 'a@x.com'` — 走索引吗？
- Q2: `WHERE email = 100` — 走索引吗？type 列是什么？
- Q3: 反例：表 `t(id VARCHAR(10), idx)` 然后 `WHERE id = 100` —— 走索引吗？

## 预期（基于 ch03 §3.7 推算）

按 §3.7「隐式类型转换」：两边类型不同只表示 MySQL 需要套用比较转换规则，**不代表一定转换索引列，也不代表索引一定失效**。本实验的方向是“字符串列与数字常量比较”：MySQL 按数值进行比较，同一个数字可能对应 `'1'`、`' 1'`、`'1a'` 等多个字符串，因此无法按原始字符串索引做一次精确定位。

- **Q1** `WHERE email='u1@x.com'`：字面值是字符串，与 VARCHAR 列类型一致，直接走 idx_email，type=ref。
- **Q2** `WHERE email=100`：字面值是整数，email 是 VARCHAR；MySQL 规则是按浮点数比较字符串和数字，可概念化为逐行计算 `CONVERT(email, DOUBLE)`，字符串索引不能用于 ref/range 定位，type=ALL。
- **Q3** `WHERE id=100`（id 是 VARCHAR PRIMARY KEY）：同样是 VARCHAR=INT，VARCHAR 列被转换，连主键索引也失效，type=ALL。
- 规则一句话：关键不是“类型不同”，而是**为了比较是否必须转换索引列的每一行**。字符串索引列与数字值比较会失去原字符串的 B+ 树定位能力；反方向如 `INT` 索引列与数字字符串 `'100'` 比较，常可转换常量后继续定位，不能套用同一结论。应用层仍应按列类型绑定参数，并用 `EXPLAIN` 验证。

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
- 我学到：MySQL 8.0 的 `Warning 1739` 明确表示该字段因为类型或 collation 转换而不能使用 ref/range 访问。一旦看到它，应检查**哪一侧被转换**以及驱动/ORM 绑定的参数类型，而不是把所有异型比较都判成索引失效。

## 连到的面试卡

- `99-interview-cards/q-when-does-index-fail.md`
