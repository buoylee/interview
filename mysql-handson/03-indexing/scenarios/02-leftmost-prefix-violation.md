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

## 预期（基于 ch03 §3.3 推算）

按 §3.3「联合索引 + 最左前缀」规则：索引 `(city, age, name)` 按 city→age→name 排序，只有从最左列开始连续命中才能缩小扫描范围。

- **Q1** `WHERE city=? AND age=? AND name=?`：三列全等值，最左前缀完整，应走三列。  
- **Q2** `WHERE city=? AND age=?`：命中 city+age 两列等值，走两列。  
- **Q3** `WHERE city=? AND name=?`：city 等值命中，但 age 跳过，name 在索引里但不形成连续前缀；只能用 city 定位区间，name 需要在引擎层或 Server 层过滤。  
- **Q4** `WHERE age=? AND name=?`：缺少最左列 city，无法走联合索引，预期全表扫描。  

|     | 走索引？ | 用到几列 | Extra |
|-----|---|---|---|
| Q1  | 是 | 3 | NULL（精准 ref） |
| Q2  | 是 | 2 | NULL |
| Q3  | 是，但仅1列 | 1 | Using index condition（name 由 ICP 下推）|
| Q4  | 否 | 0 | Using where（全表） |

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
-- Q1: WHERE city='Taipei' AND age=30 AND name='alice'
type=ref  key=idx_city_age_name  key_len=520  ref=const,const,const  rows=1  Extra=NULL

-- Q2: WHERE city='Taipei' AND age=30
type=ref  key=idx_city_age_name  key_len=262  ref=const,const  rows=20  Extra=NULL

-- Q3: WHERE city='Taipei' AND name='alice'
type=ref  key=idx_city_age_name  key_len=258  ref=const  rows=200  filtered=10.00  Extra=Using index condition

-- Q4: WHERE age=30 AND name='alice'
type=ALL  key=NULL  rows=1000  filtered=1.00  Extra=Using where
```

key_len 解码（city VARCHAR(64) utf8mb4 NOT NULL = 258B；age INT NOT NULL = 4B；name VARCHAR(64) utf8mb4 NOT NULL = 258B）：
- Q1 key_len=520 = 258+4+258 → **3 列全用**
- Q2 key_len=262 = 258+4 → **city+age 2 列**
- Q3 key_len=258 = 258 → **city 1 列**；name 由 ICP（index condition pushdown）在引擎层过滤
- Q4 key=NULL → **不走索引，全表扫**

|     | 走索引？ | 用到几列 | Extra | 备注 |
|-----|---|---|---|---|
| Q1  | 是 | 3 | NULL | type=ref，精准命中 |
| Q2  | 是 | 2 | NULL | type=ref |
| Q3  | 是 | 1 | Using index condition | name 由 ICP 在引擎层过滤 |
| Q4  | 否 | 0 | Using where | type=ALL，全表扫 |

## ⚠️ 预期 vs 实机落差

- 预期对上了，Q1/Q2/Q4 完全吻合。
- Q3 的关键是 **ICP（Index Condition Pushdown）**：虽然 name 跳过了 age 不能形成连续前缀，但 name 在索引里，MySQL 8.0 默认把 `name='alice'` 下推到引擎层（InnoDB）在扫索引页时过滤，避免了大量回表，Extra 出现 `Using index condition`。
- 我学到：「最左前缀」决定**能用几列定位区间**（key_len），而 ICP 决定**索引中剩余列的 WHERE 条件在哪里过滤**（引擎层 vs Server 层）。跳过中间列的后续列不会被索引定位用到，但会被 ICP 下推利用。

## 连到的面试卡

- `99-interview-cards/q-when-does-index-fail.md`
