# Scenario 02: 联合索引最左前缀失效

## 我想验证的问题

表 `user_profile` 加联合索引 `(city, age, name)`。下面 4 条查询哪些走索引、走到第几列、Extra 提示什么？

```sql
-- Q1
SELECT * FROM user_profile WHERE city='Taipei' AND age=30 AND name='alice';
-- Q2
SELECT * FROM user_profile WHERE city='Taipei' AND age=30;
-- Q3
SELECT * FROM user_profile WHERE city='Taipei' AND name='alice';
-- Q4
SELECT * FROM user_profile WHERE age=30 AND name='alice';
```

## 预期（写实验前的假设）

> 填空（不要查）。对每条 Q 给出：
> - 走不走索引（看 explain.key）
> - 走到第几列（看 key_len 大致估算）
> - Extra 里有没有 `Using where` / `Using index condition` / `Using index`

|     | 走索引？ | 用到几列 | Extra |
|-----|---|---|---|
| Q1  |   |   |   |
| Q2  |   |   |   |
| Q3  |   |   |   |
| Q4  |   |   |   |

> 填完先 commit 一次。

## 环境

- `make up`
- 灌少量数据：

```sql
INSERT INTO user_profile (name,age,city,email)
SELECT CONCAT('u',n), 20+(n%50), ELT(1+(n%5),'Taipei','Tokyo','Seoul','HK','SF'), CONCAT('u',n,'@x.com')
FROM (SELECT a.n+10*b.n+100*c.n AS n FROM
      (SELECT 0 n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) a,
      (SELECT 0 n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) b,
      (SELECT 0 n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) c
     ) t;
```
  这会插入 1000 行，城市/年龄/姓名都有分布。

## 步骤

1. 建联合索引：`ALTER TABLE user_profile ADD INDEX idx_city_age_name (city, age, name);`
2. 对每条 Q 跑 `EXPLAIN FORMAT=TRADITIONAL <sql>` 和 `EXPLAIN FORMAT=TREE <sql>`
3. 记录 type / key / key_len / rows / Extra
4. 用 `make explain SQL="..."` 也跑一次看 optimizer_trace（重点看 `range_scan_alternatives`、`cost_for_plan`）

## 实机告诉我

```
<贴每条 Q 的 explain 输出>
```

|     | 走索引？ | 用到几列 | Extra | 备注 |
|-----|---|---|---|---|
| Q1  |   |   |   |   |
| Q2  |   |   |   |   |
| Q3  |   |   |   |   |
| Q4  |   |   |   |   |

## ⚠️ 预期 vs 实机落差

- 我以为 Q3 走全部三列：实际 ……
- 我以为 Q4 不走索引：实际 ……
- 我学到：「最左前缀」对 = 号查询和范围查询的行为分别是 ……

## 连到的面试卡

- `99-interview-cards/q-when-does-index-fail.md`
