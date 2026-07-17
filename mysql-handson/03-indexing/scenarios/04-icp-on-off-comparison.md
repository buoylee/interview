# Scenario 04: 索引下推（ICP）开关前后对比

## 我想验证的问题

沿用 Scenario 03 建立的索引 `idx_city_name_age (city, name, age)`，SQL：
```sql
SELECT * FROM user_profile WHERE city='Taipei' AND age > 25 AND name LIKE '%0%';
```

`name LIKE '%0%'` 有前导通配，不能构造 B+ 树扫描区间，但 `name` **在索引里**，所以可以作为 ICP 条件在读取完整行之前过滤。
- ICP 开（默认）：Extra 会是什么？引擎层 vs Server 层各做什么？
- ICP 关：Extra 会变成什么？rows 数字会不会变？读了多少行回去 Server 层过滤？

## 预期（基于 ch03 §3.5 推算）

按 §3.5「索引下推（ICP）」：索引 `idx_city_name_age (city, name, age)` 中，city 是等值条件；紧随其后的 name 使用前导通配，不能收窄扫描区间，位于 name 后面的 age 也不能继续构造区间。因此访问路径仍要检查 city='Taipei' 的约 200 个二级索引条目，但 name、age 都可以在索引条目上由 ICP 判断。

- **ICP on（默认）**：引擎层在扫描索引页时就应用 `age > 25 AND name LIKE '%0%'` 过滤，只有满足条件的条目才回表取完整行，Extra = `Using index condition`。Handler_read_next 预期约为 Server 层最终请求到的匹配行数（80），但它不是“引擎内部检查了多少索引条目”的计数器。
- **ICP off**：引擎层只按 city='Taipei' 扫，把所有 200 行都回表给 Server 层，Server 层再过滤 age/name，Extra = `Using where`，Handler_read_next 应等于 **200**（city='Taipei' 的全部行）。

|     | Extra | rows | 谁过滤 age+name |
|-----|---|---|---|
| ICP on  | Using index condition | 200（估算） | 引擎层（InnoDB） |
| ICP off | Using where | 200 | Server 层（mysqld） |

## 环境

- 已建索引 `idx_city_name_age (city, name, age)`（来自 Scenario 03）

## 步骤

1. ICP 默认开。跑 `EXPLAIN FORMAT=TREE` + 业务 SQL，记录
2. `SET optimizer_switch='index_condition_pushdown=off';`
3. 同 SQL 再跑 explain，对比
4. 用 `SHOW SESSION STATUS LIKE 'Handler_read%';` 在两种状态下分别跑一次 SELECT，看 Handler_read_next 差几倍
5. 跑完 `SET optimizer_switch='index_condition_pushdown=on';` 还原

## 实机告诉我

```
-- SQL: SELECT * FROM user_profile WHERE city='Taipei' AND age > 25 AND name LIKE '%0%'
-- (注: Taipei 共 200 行；name 含 '0' 的 109 行，age>25 的 160 行，两者同时满足的 80 行)

-- ICP ON (default)
EXPLAIN: type=ref  key=idx_city_name_age  key_len=258  rows=200  filtered=3.70  Extra=Using index condition

FLUSH STATUS; SELECT ...; SHOW SESSION STATUS LIKE 'Handler_read%';
Handler_read_key:   1
Handler_read_next: 80

-- ICP OFF
SET optimizer_switch='index_condition_pushdown=off';
EXPLAIN: type=ref  key=idx_city_name_age  key_len=258  rows=200  filtered=3.70  Extra=Using where

FLUSH STATUS; SELECT ...; SHOW SESSION STATUS LIKE 'Handler_read%';
Handler_read_key:   1
Handler_read_next: 200
```

|     | Extra | rows（估算） | Handler_read_next（实际） |
|-----|---|---|---|
| ICP on  | Using index condition | 200 | **80** |
| ICP off | Using where | 200 | **200** |

## ⚠️ 预期 vs 实机落差

- 预期对上了：Extra 从 `Using index condition` 变 `Using where`，Handler_read_next 从 80 升到 200。
- 关键数字：两种模式都要检查 city='Taipei' 区间内约 200 个二级索引条目。ICP on 只有 80 个条目通过条件并读取完整行；ICP off 则先读取约 200 个完整行，再由 Server 层过滤。
- `Handler_read_next` 从 200 降到 80，反映的是 Handler 层返回给 Server 的行请求减少，不表示 InnoDB 只检查了 80 个索引条目。`rows` 估算值没有变化（均为 200）也符合预期，因为访问区间没变。
- 我学到：ICP 优化的是**读取完整行和跨层传递**，不是把最左前缀确定的索引区间变小；要量化收益，不能把 Handler 计数直接命名为“索引扫描行数”。

## 连到的面试卡

- `99-interview-cards/q-when-does-index-fail.md`
