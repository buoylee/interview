# Scenario 04: 索引下推（ICP）开关前后对比

## 我想验证的问题

沿用 Scenario 03 建立的索引 `idx_city_name_age (city, name, age)`，SQL：
```sql
SELECT * FROM user_profile WHERE city='Taipei' AND age > 25 AND name LIKE '%0%';
```

`name LIKE '%0%'` 有前导通配，不能构造 B+ 树扫描区间，但 `name` **在索引里**，所以可以作为 ICP 条件在读取完整行之前过滤。
- ICP 开（默认）：Extra 会是什么？引擎层 vs Server 层各做什么？
- ICP 关：Extra 会变成什么？rows 数字会不会变？读了多少行回去 Server 层过滤？

## 先把“下推”方向和条件分工对上

二级索引不是位于聚簇索引的“下层”；两种索引都归 InnoDB 管理。ICP 中的“下推”指执行位置发生了以下变化：

```text
没有 ICP：完整行返回 Server 层 → Server 判断 name/age
有 ICP：  Server 下推 name/age 条件树 → InnoDB 在二级索引扫描循环中触发判断
```

这里的“交给 InnoDB”不是把 SQL 字符串再解析一次。Server 已经把 `WHERE` 解析成内部条件表达式；InnoDB 读到一个二级索引条目后，把 `name/age` 值放入 Handler 使用的 record buffer，在尚未回表、尚未返回 Server Executor 时调用这棵下推条件。条件为假，InnoDB 就在**同一次取行请求内部**继续扫描下一条。

本查询中的条件分工：

| 内容 | 是否缩小扫描范围 | 有没有使用索引 | 具体怎样使用 |
|---|---|---|---|
| `city='Taipei'` | 能 | 有 | 利用索引顺序定位 Taipei 区间 |
| `name LIKE '%0%'` | 不能 | 有 | 读取每个索引条目中的 `name`，在回表前做 ICP 判断 |
| `age > 25` | 不能 | 有 | 前面的 `name` 没有形成可定位前缀；读取每个条目中的 `age` 做 ICP 判断 |
| `SELECT *` 所需的 `email/created_at` 等列 | 不适用 | 当前索引没有 | 通过 ICP 后，仍需用主键回表读取这些列 |

因此实验要验证的不是“`name/age` 有没有用索引”——它们确实使用了索引条目中的值；实验要验证的是“同样扫描这段二级索引时，是否能在回表前淘汰不符合条件的条目”。“利用索引定位”和“利用索引条目过滤”的完整区别见 [ch03 §3.5](../README.md)。

换成复杂度语言：`city` 先利用 B+ 树的有序性定位区间，ICP 本身不会再通过 `name/age` 做一次 `O(log N)` 跳转查找；它是在这个区间内逐条读取索引值并判断 SQL 条件。若共扫描 `M` 个条目、其中 `K` 个通过，ICP 仍检查 `M` 个条目，但可把回表从最多 `M` 次降到 `K` 次。

从 Handler 调用边界看，200 个候选项的差别是：

```text
ICP OFF：index_next() → 回表 1 条 → 返回 Server → Server 判断
         上述过程对候选项反复发生，约 200 条完整行到达 Server

ICP ON： index_next() → InnoDB 内部检查若干二级索引条目
                    ├─ 不匹配：内部 continue，不回表、不返回
                    └─ 匹配：回表并返回 1 条完整行
         最终约 80 条完整行到达 Server
```

所以“ICP ON 时 `Handler_read_next=80`，但 InnoDB 仍检查约 200 个索引条目”并不矛盾：一次 Handler 取下一行的调用，在 InnoDB 内部可以跨过多个不匹配的索引条目。

## 预期（基于 ch03 §3.5 推算）

按 §3.5「索引下推（ICP）」：索引 `idx_city_name_age (city, name, age)` 中，city 是等值条件；紧随其后的 name 使用前导通配，不能收窄扫描区间，位于 name 后面的 age 也不能继续构造区间。因此访问路径仍要检查 city='Taipei' 的约 200 个二级索引条目，但 name、age 都可以在索引条目上由 ICP 判断。

- **ICP on（默认）**：InnoDB 在扫描循环里准备 `age/name` 索引列并触发下推条件，只有满足条件的条目才回表取完整行，Extra = `Using index condition`。本实验的 Handler_read_next 预期约为返回 Handler 边界的匹配行数（80），但它不是“InnoDB 内部检查了多少索引条目”的计数器。
- **ICP off**：InnoDB 只按 city='Taipei' 扫，把所有 200 个候选项都回表成完整行并逐一返回 Server Executor；Server 再过滤 age/name，Extra = `Using where`，本实验的 Handler_read_next 应等于 **200**（city='Taipei' 的全部行）。

|     | Extra | rows | 谁过滤 age+name |
|-----|---|---|---|
| ICP on  | Using index condition | 200（估算） | InnoDB 扫描循环触发下推条件 |
| ICP off | Using where | 200 | 完整行返回后的 Server Executor |

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
