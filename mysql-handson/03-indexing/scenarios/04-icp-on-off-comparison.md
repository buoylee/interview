# Scenario 04: 索引下推（ICP）开关前后对比

## 我想验证的问题

沿用 Scenario 03 建立的索引 `idx_city_name_age (city, name, age)`，SQL：
```sql
SELECT * FROM user_profile WHERE city='Taipei' AND age > 25 AND name LIKE '%a%';
```

`name LIKE '%a%'` 是范围条件，但 `name` **在索引里**——这是 ICP 起作用的前提（索引含但 WHERE 不是等值/不能定位区间的列）。
- ICP 开（默认）：Extra 会是什么？引擎层 vs Server 层各做什么？
- ICP 关：Extra 会变成什么？rows 数字会不会变？读了多少行回去 Server 层过滤？

## 预期（基于 ch03 §3.5 推算）

按 §3.5「索引下推（ICP）」：索引 `idx_city_name_age (city, name, age)` 中，city 是等值条件，age > 25 和 name LIKE '%0%' 都在索引里但不能收窄起始位置（age/name 的 WHERE 不是最左等值）。

- **ICP on（默认）**：引擎层在扫描索引页时就应用 `age > 25 AND name LIKE '%0%'` 过滤，只有满足条件的行才回表取完整行，Extra = `Using index condition`，Handler_read_next 应等于**实际命中行数**（约 80）。
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
-- (注: 数据集中 name 格式为 'uN'，含 '0' 的约 80 行；age>25 在 Taipei 中约 160 行)

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
- 关键数字：ICP on 扫 80 行（最终返回行数），ICP off 扫 200 行（city='Taipei' 全集），多读了 **2.5 倍**。`rows` 估算值没有变化（均为 200），因为 EXPLAIN 的 rows 是优化器统计估算，不反映 ICP 的实际过滤效果。
- 我学到：ICP 的作用体现在 `Handler_read_next` 而不是 EXPLAIN 的 rows；rows 不变不代表 ICP 没起作用，要看 Handler 统计才能量化"少回了多少次表"。

## 连到的面试卡

- `99-interview-cards/q-when-does-index-fail.md`
