# SQL 执行流程与 Explain

## 1. 核心问题

一条 SQL 从你按下回车到看到结果，经历了什么？为什么同样的 WHERE 条件，有时 1ms 出来，有时 10s 超时？本章解决三件事：
**(a)** MySQL 内部 Parser → Optimizer → Executor 三阶段各做了什么，边界在哪里；
**(b)** 怎么读懂 `EXPLAIN` 输出的每一列，5 秒内判断一条 SQL 是否有隐患；
**(c)** 当 Explain 看起来 OK 但还是慢，怎么用 `optimizer_trace` 和 `EXPLAIN ANALYZE` 深挖。

---

## 2. 直觉理解

把一条 SQL 想成一张机票预订的完整流程：

```
你（Client）输入目的地
    ↓
前台（Parser）：核验地址拼写对不对、出发地/目的地是否真实存在
    ↓
调度员（Optimizer）：查所有航班时刻表，算出最省油的路线（不一定最短）
    ↓
飞行员（Executor）：按路线真正飞，中途遇到气流（WHERE 残余条件）自己处理
    ↓
落地（返回结果集）
```

Optimizer 选的路线（执行计划）是**基于统计的估算**，不一定最优，但 99% 场景够好。当它算错了（统计过期、数据倾斜），就是你需要介入的时候。

---

## 3. 原理深入

### 3.1 三阶段总览（ASCII 图）

```
Client
  │
  │ SQL 文本
  ▼
┌─────────────────────────────────┐
│           连接器 / 缓存          │
│  (8.0 已废弃 Query Cache)        │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│          Parser（解析器）         │
│  词法分析 → Token 流              │
│  语法分析 → AST（抽象语法树）       │
│  语义分析 → 验证表/列/权限          │
└────────────────┬────────────────┘
                 │ AST
                 ▼
┌─────────────────────────────────┐
│        Optimizer（优化器）        │
│  逻辑重写（Rewriter）              │
│  成本估算（Cost-based planner）    │
│  选 JOIN 顺序 + 选索引              │
│  生成执行计划（Plan）               │
└────────────────┬────────────────┘
                 │ Plan
                 ▼
┌─────────────────────────────────┐
│        Executor（执行器）         │
│  按 Plan 驱动引擎读行               │
│  应用残余 WHERE / 聚合 / 排序       │
│  通过 Handler API 与 InnoDB 交互   │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│     InnoDB（或其他存储引擎）        │
│  Buffer Pool → B+ 树页 → 磁盘 IO  │
└─────────────────────────────────┘
```

---

### 3.2 Parser

Parser 做两件事，然后做一件常被忽略的事：

**（1）词法分析（Lexer）**

把 SQL 文本切成 Token 流，不校验逻辑：

```
SELECT name FROM users WHERE age > 18
→ [{KEYWORD: SELECT}, {IDENT: name}, {KEYWORD: FROM},
   {IDENT: users}, {KEYWORD: WHERE}, {IDENT: age},
   {OP: >}, {NUMBER: 18}]
```

**（2）语法分析（Parser）**

检查 Token 流是否符合 SQL 语法规范，生成 AST：

```
SELECT
├── Columns: [name]
├── FROM
│   └── Table: users
└── WHERE
    └── Condition
        ├── Column: age
        ├── Operator: >
        └── Value: 18
```

语法错误（`SELEC` 拼错、括号不匹配）在这里被捕获，代价极低。

**（3）语义分析（Semantic Analysis）—— 常被忽略但很重要**

- 查 information_schema：验证 `users` 表存在、`name` / `age` 列存在
- 解析别名、子查询的命名空间
- 检查当前用户对表/列的权限（`SELECT` 权限）
- 把 `*` 展开为具体列列表

> 面试陷阱：「Parser 做什么」标准答案要含「验证表/列存在 + 权限检查」，不只是词法/语法。

---

### 3.3 Optimizer：Rewriter + Cost-based Planner

Optimizer 分两步工作：

#### 逻辑重写（Rule-based Rewriter）

在进入成本估算前，优化器先做一些确定性的等价变换（无论数据分布如何都成立）：

| 重写规则 | 示例 |
|---|---|
| 常量折叠 | `WHERE 1+1=2 AND age>18` → `WHERE age>18` |
| 外连接 → 内连接 | `LEFT JOIN` 的右表 WHERE 有非 NULL 条件时自动转 INNER JOIN |
| 子查询 → JOIN | `WHERE id IN (SELECT id FROM t2 WHERE ...)` 常被改写为 semijoin |
| 条件下推 | 把 WHERE 条件尽量下推到更靠近扫描层 |
| 投影下推 | 把不需要的列尽早从流水线中去掉 |
| 等值传递 | `WHERE a.id=b.id AND a.id=5` → `b.id=5` 也能走索引 |

#### 成本估算（Cost-based Planner）

对所有候选执行计划逐一估算成本，选最小的。候选项包括：
- 对每张表：全表扫 vs 每个可用索引（range / ref / eq_ref）
- 多表 JOIN：不同的 JOIN 顺序（表少于 `optimizer_search_depth=8` 时穷举，超过时贪心）

成本计算公式（简化版）：

```
Total Cost = Σ (IO Cost + CPU Cost)
IO Cost   = 读到的页数 × io_block_read_cost
CPU Cost  = 处理的行数 × row_evaluate_cost
```

具体数字见 §3.4。

---

### 3.4 Optimizer 成本模型（具体公式 + server_cost / engine_cost 表）

MySQL 8.0 把成本参数拆成两张系统表，可以查询和修改：

#### `mysql.engine_cost`（引擎层，IO 相关）

```sql
SELECT * FROM mysql.engine_cost;
```

| cost_name | default_value | 含义 |
|---|---|---|
| io_block_read_cost | 1.0 | 从磁盘读一个数据页的代价（相对单位） |
| memory_block_read_cost | 0.25 | 从 Buffer Pool 读一个数据页的代价 |

Buffer Pool 读比磁盘读便宜 4 倍，所以热数据多的表更倾向走索引（索引页常驻内存）。

#### `mysql.server_cost`（Server 层，CPU 相关）

```sql
SELECT * FROM mysql.server_cost;
```

| cost_name | default_value | 含义 |
|---|---|---|
| row_evaluate_cost | 0.1 | 评估一行 WHERE 条件的代价 |
| key_compare_cost | 0.05 | 比较一个索引键的代价 |
| memory_temptable_create_cost | 1.0 | 创建内存临时表的代价 |
| memory_temptable_row_cost | 0.1 | 往内存临时表插一行的代价 |
| disk_temptable_create_cost | 20.0 | 创建磁盘临时表的代价（USING TEMPORARY 降级到磁盘） |
| disk_temptable_row_cost | 0.5 | 往磁盘临时表插一行的代价 |

#### 完整成本估算公式

```
-- 全表扫描代价
FullScan Cost = data_page_count × io_block_read_cost
              + row_count × row_evaluate_cost

-- 范围扫描代价
RangeScan Cost = range_page_count × io_block_read_cost
               + range_row_count × row_evaluate_cost
               + range_row_count × key_compare_cost   (索引键比较)

-- 回表代价（二级索引 + 回表）
IndexLookup Cost = RangeScan Cost
                 + range_row_count × io_block_read_cost  (每行回表一次随机 IO)
```

> 实战含义：`range_row_count`（即 Explain 里的 `rows`）如果被高估，优化器会认为「回表次数太多」，转而选全表扫。这时跑 `ANALYZE TABLE` 更新统计，或用 `FORCE INDEX` 干预。

#### 查看实际成本

`optimizer_trace` 里的 `cost_for_plan` 字段就是上述公式的输出。详见 §3.8。

---

### 3.5 Executor + 与引擎层的边界（Handler API）

Executor 拿到 Plan 后，按以下步骤逐行执行：

```
1. 调用 Handler::index_first / index_next / rnd_next
   （Handler 是 Server 层与存储引擎的统一接口）
2. 引擎返回一行数据（从 Buffer Pool 或磁盘页）
3. Executor 应用「残余 WHERE 条件」
   （不能在索引层过滤的条件，比如函数条件、跨列条件）
4. 如果有 GROUP BY / ORDER BY，写入排序缓冲区或临时表
5. 满足 LIMIT 后停止迭代
6. 汇总结果，返回给 Client
```

**Handler API 关键方法：**

| 方法 | 作用 |
|---|---|
| `index_read` | 用索引定位第一条满足条件的行 |
| `index_next` | 沿索引顺序读下一行 |
| `rnd_next` | 全表扫描读下一行 |
| `ha_mrr_fill_buffer` | MRR：批量填充主键缓冲区再排序回表 |

**Server 层 vs 引擎层的边界：**

- **引擎层做**：索引定位、页读取、MVCC 可见性判断（undo log 回溯版本）、行锁
- **Server 层做**：残余 WHERE 过滤、JOIN 拼接、GROUP BY 聚合、ORDER BY 排序、LIMIT 截断

> Explain 的 `Using where` 就表示「有一部分 WHERE 条件没法在引擎层完成，由 Server 层接手」，不是坏事，但说明索引没有完全覆盖过滤条件。

---

### 3.6 Explain 完整字段速查

先看一个完整示例，建表假设：

```sql
CREATE TABLE user_profile (
  id       BIGINT AUTO_INCREMENT PRIMARY KEY,
  city     VARCHAR(50),
  age      INT,
  username VARCHAR(100),
  INDEX idx_city_age (city, age)
);
```

```sql
EXPLAIN SELECT id, city, age FROM user_profile WHERE city='Taipei' AND age=30;
```

```
+----+-------------+--------------+------------+------+---------------+--------------+---------+-------------+------+----------+-------------+
| id | select_type | table        | partitions | type | possible_keys | key          | key_len | ref         | rows | filtered | Extra       |
+----+-------------+--------------+------------+------+---------------+--------------+---------+-------------+------+----------+-------------+
|  1 | SIMPLE      | user_profile | NULL       | ref  | idx_city_age  | idx_city_age | 208     | const,const |   42 |   100.00 | Using index |
+----+-------------+--------------+------------+------+---------------+--------------+---------+-------------+------+----------+-------------+
```

下面逐列解读：

---

#### `id` — 查询块编号

- 值含义：同一 SELECT 语句内所有行 `id` 相同；子查询 / UNION 会产生新的 `id` 值，数字越大越先执行
- 示例：
  - `id=1` 只有一个简单查询
  - `id=1` 和 `id=2`：2 先执行（内层子查询），1 用 2 的结果

---

#### `select_type` — 查询类型

| 值 | 含义 |
|---|---|
| `SIMPLE` | 没有子查询、没有 UNION 的简单查询 |
| `PRIMARY` | 最外层的 SELECT（当有子查询时） |
| `SUBQUERY` | WHERE/SELECT 中的不相关子查询 |
| `DEPENDENT SUBQUERY` | 相关子查询（每次外层行都要重新执行） |
| `DERIVED` | FROM 子句中的派生表（临时表） |
| `UNION` | UNION 中第二个及以后的 SELECT |
| `UNION RESULT` | UNION 的合并结果（对应去重临时表） |
| `MATERIALIZED` | 被物化的子查询（8.0 新增，存为临时表供外层 JOIN） |

> 看到 `DEPENDENT SUBQUERY` 要警觉：每遍历外层一行就执行一次子查询，N×M 复杂度，通常改写为 JOIN。

---

#### `table` — 当前行访问的表

- 通常是表名或别名
- `<derivedN>` 表示引用的是 id=N 的派生表
- `<unionM,N>` 表示是 M 和 N 的 UNION 结果
- `<subqueryN>` 表示引用的是物化子查询

---

#### `partitions` — 分区裁剪

- NULL：表没有分区，或分区不适用
- 非 NULL：列出实际访问的分区名，未命中的分区已被裁剪

---

#### `type` — 访问类型（最重要的一列）

**按速度从慢到快排列：**

| type | 速度 | 含义 | 何时出现 |
|---|---|---|---|
| `ALL` | 最慢 | 全表扫描，逐行读所有数据页 | 没有可用索引，或优化器认为全扫更快 |
| `index` | 很慢 | 全索引扫描（扫整棵索引 B+ 树），只比 ALL 省了回表 | `SELECT` 列都在索引里但无法走范围 |
| `range` | 中等 | 索引范围扫描（`>`, `<`, `BETWEEN`, `IN`, `LIKE 'abc%'`） | WHERE 有范围条件且走了索引 |
| `ref` | 较快 | 非唯一索引等值查找，可能返回多行 | 二级索引 = 常量，或 JOIN 用非唯一索引 |
| `fulltext` | 特殊 | 全文索引扫描 | MATCH...AGAINST |
| `ref_or_null` | 中等 | 类似 ref，但还要查 NULL 值 | `WHERE col=? OR col IS NULL` |
| `index_merge` | 中等偏快 | 合并多个索引的结果 | OR 条件且每个列各有索引 |
| `unique_subquery` | 较快 | IN 子查询被优化成唯一索引查找 | `WHERE id IN (SELECT ...)` |
| `eq_ref` | 很快 | JOIN 中用唯一索引/主键等值连接，每次最多返回 1 行 | JOIN ON 主键 / 唯一索引 |
| `const` | 极快 | 主键或唯一索引等值查询，最多 1 行，结果作常量 | `WHERE id=5`（主键等值） |
| `system` | 极快 | 表只有 1 行（系统表） | 特殊系统表 |
| `NULL` | 极快 | 不需要访问表（例如 `SELECT 1`） | 纯常量查询 |

**判断口诀：看到 `ALL` 要警觉；看到 `range` 及以上放心；看到 `const` / `eq_ref` 最优。**

---

#### `possible_keys` — 优化器考虑过的索引

- 列出所有「理论上可以用」的索引
- NULL 表示没有任何索引可用
- 重要：`possible_keys` 有值不代表真的用了（`key` 列才是最终结果）

---

#### `key` — 实际使用的索引

- NULL：没有用任何索引（全扫或 index_merge 的特殊情况）
- 非 NULL：实际走的索引名
- `possible_keys=NULL` 但 `key` 非 NULL：发生了覆盖索引强制扫（`type=index`）

---

#### `key_len` — 使用的索引字节数

`key_len` 告诉你用了联合索引的**前几列**，是诊断「最左前缀失效」的直接证据。

计算规则：
- INT：4 字节（NOT NULL），允许 NULL 则 +1（NULL 标志位）
- BIGINT：8 字节
- VARCHAR(N) 使用 utf8mb4：`N × 4 + 2`（变长前缀 2 字节） + 1（NULL 标志位，如允许 NULL）
- DATETIME：5 字节（MySQL 5.6+ 精简存储）

示例：`idx_city_age (city VARCHAR(50), age INT)` 都走了：

```
key_len = (50×4 + 2) + (4) = 202 + 4 = 206 字节（均 NOT NULL）
若 city 允许 NULL：key_len = (50×4 + 2 + 1) + (4 + 1) = 208 字节
```

> 如果 `key_len` 等于只有第一列的长度，说明联合索引只用了第一列，后续列没走到。

---

#### `ref` — 与索引比较的值

| 值 | 含义 |
|---|---|
| `const` | 与常量比较（`WHERE city='Taipei'`） |
| `db.table.column` | 与另一列比较（JOIN 条件） |
| `func` | 与函数结果比较 |
| NULL | 全扫或范围扫时不适用 |

---

#### `rows` — 优化器预估扫描行数

`rows` 是优化器基于 `mysql.innodb_index_stats` 统计信息的预估值，**不是实际行数**。预估可能偏差 10 倍乃至更多，尤其是：
- 数据分布倾斜（某个 city 占 80% 数据时，等值 rows 估算会偏小）
- 统计信息过期（大批量 INSERT/DELETE 后没有 ANALYZE）
- 新表刚导入数据

若 `rows` 与实际出入很大，跑 `ANALYZE TABLE tablename;` 更新统计，或用 `EXPLAIN ANALYZE`（§3.9）看实际值。

---

#### `filtered` — 经 WHERE 过滤后留下行的百分比

- 范围 0-100（百分比）
- `rows × filtered / 100` = 优化器预估最终返回给上层的行数
- `filtered=100` 表示引擎层已完全过滤，Server 层不需要再做额外过滤
- `filtered=10` 表示 Server 层还要过滤掉 90% 的行 → 可能有优化空间（加索引列覆盖过滤条件）

---

#### `Extra` — 执行细节标志位（完整对照表见 §3.6 末尾）

最常见的 Extra 字符串，单独列表见下一节。

---

#### Extra 完整对照表

| Extra | 含义 | 性能信号 |
|---|---|---|
| `Using where` | Server 层用 WHERE 过滤行（部分 WHERE 没在引擎层过滤） | 中性；如果 rows 很大但 filtered 很低则有优化空间 |
| `Using index` | 覆盖索引，SELECT 列全在索引里，免回表 | 好，越多越好 |
| `Using index condition` | 索引下推（ICP），引擎层用索引中的列做 WHERE 过滤，减少回表 | 好 |
| `Using temporary` | 用了临时表（GROUP BY、DISTINCT、UNION 常见） | 警觉；若是磁盘临时表代价更高 |
| `Using filesort` | 排序不走索引顺序，需要在内存/磁盘做额外排序 | 警觉；尝试让 ORDER BY 列包含在索引里 |
| `Using join buffer (Block Nested Loop)` | JOIN 没有用到被驱动表的索引，把驱动表数据放 join_buffer 批量比较 | 警觉；为被驱动表 JOIN 条件列加索引 |
| `Using join buffer (Batched Key Access)` | BKA：用 MRR 批量回表，比 BNL 好 | 较好；8.0.18+ hash join 更优 |
| `Using MRR` | Multi-Range Read：先收集主键再排序回表，把随机 IO 变顺序 | 好 |
| `LooseScan` | semijoin 优化的一种，从索引组扫描只取每组的第一行 | 较好 |
| `FirstMatch(table)` | semijoin 优化的一种，找到第一个匹配行就停止内层扫描 | 较好 |
| `Materialize` | 子查询被物化为临时表 | 中性；避免 DEPENDENT SUBQUERY 的逐行执行 |
| `Not exists` | LEFT JOIN 的 NULL 优化，找到一行匹配就停 | 好（实现 NOT EXISTS 语义时） |
| `Select tables optimized away` | 直接从统计或索引元数据取结果（如 `MIN`/`MAX` 有索引时） | 极好 |
| `Impossible WHERE` | WHERE 条件永远为假（如 `id=1 AND id=2`），不读任何行 | 特殊；说明 SQL 逻辑有问题 |
| `Zero limit` | LIMIT 0，不返回任何行 | 特殊 |
| `Distinct` | 找到第一个匹配行后对当前组停止 | 中性 |
| `Using index for group-by` | GROUP BY / DISTINCT 利用索引顺序，不需要临时表 | 好 |
| `Using index for skip scan` | 8.0 新特性：跳过索引前缀扫描范围条件 | 较好（联合索引第一列没有等值条件时的退化优化） |
| `Range checked for each record` | 在 JOIN 每次迭代时重新选择索引，通常是 JOIN 条件不确定 | 警觉；尝试固定驱动表条件 |

---

### 3.7 Explain FORMAT 三种

MySQL 8.0 支持三种 Explain 格式：

#### TRADITIONAL（默认）

```sql
EXPLAIN SELECT ...;
-- 等价于
EXPLAIN FORMAT=TRADITIONAL SELECT ...;
```

输出一张二维表，每行对应一个查询块。适合日常快速浏览。

---

#### JSON

```sql
EXPLAIN FORMAT=JSON SELECT * FROM user_profile WHERE city='Taipei';
```

```json
{
  "query_block": {
    "select_id": 1,
    "cost_info": {
      "query_cost": "5.25"
    },
    "table": {
      "table_name": "user_profile",
      "access_type": "ref",
      "possible_keys": ["idx_city_age"],
      "key": "idx_city_age",
      "key_length": "203",
      "ref": ["const"],
      "rows_examined_per_scan": 42,
      "rows_produced_per_join": 42,
      "filtered": "100.00",
      "cost_info": {
        "read_cost": "1.01",
        "eval_cost": "4.20",
        "prefix_cost": "5.21",
        "data_read_per_join": "8K"
      },
      "used_columns": ["id", "city", "age"],
      "attached_condition": "(`mydb`.`user_profile`.`age` = 30)"
    }
  }
}
```

JSON 格式额外暴露：
- `cost_info.query_cost`：总估算成本（直接和 §3.4 的公式对应）
- `cost_info.read_cost`：IO 成本部分
- `cost_info.eval_cost`：CPU 成本部分
- `attached_condition`：Server 层实际应用的 WHERE 条件（残余条件）
- 嵌套结构清晰展示 JOIN 树

**何时用 JSON**：想知道成本数字、想看残余条件被附在哪里、分析复杂 JOIN 的计划树时。

---

#### TREE

```sql
EXPLAIN FORMAT=TREE SELECT * FROM user_profile WHERE city='Taipei' AND age=30;
```

```
-> Index lookup on user_profile using idx_city_age (city='Taipei', age=30)
     (cost=5.25 rows=42)
```

对于复杂 JOIN：

```
-> Nested loop inner join  (cost=xx rows=yy)
    -> Table scan on orders  (cost=... rows=...)
    -> Single-row index lookup on user_profile using PRIMARY (id=orders.user_id)
         (cost=... rows=1)
```

TREE 格式：
- 8.0.16+ 引入，`EXPLAIN ANALYZE` 必须用 TREE 格式
- 缩进表示执行层次（最内层先执行）
- 直接显示 cost 和 rows

**何时用 TREE**：配合 `EXPLAIN ANALYZE` 查看实际 vs 估算；可视化复杂 JOIN 的执行顺序。

---

#### 三种格式对比

| 格式 | 适合场景 | 优点 | 缺点 |
|---|---|---|---|
| TRADITIONAL | 日常快速诊断 | 紧凑，一行一个块 | 没有成本数字，无法区分嵌套层次 |
| JSON | 深度成本分析、脚本解析 | 完整成本字段、残余条件、数据读量 | 太长，肉眼读累 |
| TREE | 分析执行顺序、配合 ANALYZE | 层次清晰，ANALYZE 用此格式 | 信息比 JSON 少 |

---

### 3.8 optimizer_trace 怎么用

当 Explain 无法说明「为什么没走某个索引」时，`optimizer_trace` 是你的 X 光机。

#### 开启与使用

```sql
-- 开启 trace（当前 session）
SET optimizer_trace='enabled=on';
SET optimizer_trace_max_mem_size=1048576;  -- 1MB，防止被截断

-- 跑你要分析的 SQL
SELECT * FROM user_profile WHERE city='Taipei' AND age BETWEEN 20 AND 40;

-- 读 trace 结果
SELECT * FROM information_schema.OPTIMIZER_TRACE\G

-- 读完后关掉（有性能开销）
SET optimizer_trace='enabled=off';
```

#### trace JSON 结构导航

```
{
  "steps": [
    { "join_preparation": { ... } },        -- SQL 规范化、子查询展开
    { "join_optimization": {                -- 核心
        "table_dependencies": [...],
        "rows_estimation": [...],           -- 每张表的行数/范围估算
        "considered_execution_plans": [...] -- 每个候选 plan 的成本
    }},
    { "join_execution": { ... } }           -- 实际执行（通常不关心）
  ]
}
```

#### 重点字段详解

**`rows_estimation`**：展示每个表、每个索引的范围估算

```json
{
  "table": "user_profile",
  "range_analysis": {
    "table_scan": {
      "rows": 100000,
      "cost": 20251
    },
    "potential_range_indexes": [
      {
        "index": "idx_city_age",
        "usable": true,
        "key_parts": ["city", "age"]
      }
    ],
    "analyzing_range_alternatives": {
      "range_scan_alternatives": [
        {
          "index": "idx_city_age",
          "ranges": ["Taipei <= city <= Taipei AND 20 <= age <= 40"],
          "index_dives_for_eq_ranges": true,
          "rowid_ordered": false,
          "using_mrr": false,
          "index_only": true,
          "rows": 42,
          "cost": 5.25,
          "chosen": true   -- <-- 这个 plan 被选中
        }
      ],
      "analyzing_roworder_intersect": { "usable": false }
    }
  }
}
```

**关键字段含义：**

| 字段 | 含义 |
|---|---|
| `table_scan.cost` | 全表扫的总估算成本 |
| `range_scan_alternatives[*].cost` | 该索引范围扫的总估算成本 |
| `range_scan_alternatives[*].rows` | 该索引扫描的预估行数 |
| `range_scan_alternatives[*].chosen` | `true` = 被选中；`false` = 被放弃，原因看 `cause` 字段 |
| `cause` | 放弃原因：`cost`（成本不划算）/ `uses_more_keyparts_than_ref`（有更好选择）/ `too_much_overlap` |
| `index_only` | `true` = 覆盖索引，无回表 |
| `using_mrr` | `true` = 用了 MRR 优化 |

**`considered_execution_plans`**：多表 JOIN 时列出所有被考虑的 JOIN 顺序和成本

```json
{
  "considered_execution_plans": [
    {
      "plan_prefix": [],
      "table": "orders",
      "best_access_path": {
        "considered_access_paths": [
          { "access_type": "scan", "cost": 1000, "rows": 50000, "chosen": false, "cause": "cost" },
          { "access_type": "ref", "index": "idx_user_id", "cost": 120, "rows": 10, "chosen": true }
        ]
      },
      "cost_for_plan": 120,
      "rows_for_plan": 10,
      "chosen": true
    }
  ]
}
```

**`cost_for_plan`** 是该 plan 当前累计成本，最终选择 `cost_for_plan` 最小且 `chosen=true` 的 plan。

#### 常见诊断流程

```
1. 打开 trace，跑 SQL
2. 找 range_scan_alternatives，看你期望的索引
   - 如果根本没出现 → 优化器不认为该索引可用（检查索引是否存在 / 条件是否有函数）
   - 如果出现但 chosen=false + cause=cost
     → 找 cost 数字，与 table_scan.cost 比较
     → 若差距很小但 rows 明显偏高 → ANALYZE TABLE 更新统计
     → 若 rows 准确但全扫真的更便宜（数据量小）→ 正常，不需要干预
3. 看 considered_execution_plans 的 cost_for_plan，确认 JOIN 顺序是否合理
```

---

### 3.9 8.0 新增的 Explain ANALYZE

`EXPLAIN ANALYZE` 是 MySQL 8.0.18 引入的功能，它**真正执行 SQL**，然后对比「估算值」与「实际值」。

```sql
EXPLAIN ANALYZE
SELECT u.id, u.city, COUNT(o.id)
FROM user_profile u
JOIN orders o ON o.user_id = u.id
WHERE u.city = 'Taipei'
GROUP BY u.id, u.city;
```

示例输出（TREE 格式，每行后括号是实测数据）：

```
-> Table scan on <temporary>  (actual time=5.2..5.2 rows=18 loops=1)
    -> Aggregate using temporary table  (actual time=5.1..5.1 rows=18 loops=1)
        -> Nested loop inner join  (cost=88.4 rows=50) (actual time=0.28..4.9 rows=230 loops=1)
            -> Index lookup on u using idx_city (city='Taipei')
                 (cost=12.3 rows=18) (actual time=0.15..0.22 rows=18 loops=1)
            -> Index lookup on o using idx_user_id (user_id=u.id)
                 (cost=2.1 rows=3) (actual time=0.25..0.26 rows=13 loops=18)
```

#### 关键字段解读

| 字段 | 含义 |
|---|---|
| `cost=xx` | 优化器估算成本 |
| `rows=xx`（括号外） | 优化器估算行数 |
| `actual time=A..B` | A=读到第一行的毫秒数，B=完成所有行的毫秒数 |
| `rows=xx`（括号内 `actual`） | 实际读取行数 |
| `loops=N` | 该节点被执行了 N 次（驱动表 loops=1，被驱动表 loops= 驱动表行数） |

#### 估算 vs 实际的诊断

```
estimated rows=3, actual rows=13, loops=18
→ 实际每次 JOIN 返回 13 行，优化器只估 3 行 → 统计偏低
→ 总实际行数 = 13×18 = 234，估算 = 3×18 = 54 → 差 4.3 倍
→ 可能影响 JOIN 顺序判断，跑 ANALYZE TABLE orders 更新统计
```

#### 注意事项

- `EXPLAIN ANALYZE` **真实执行 SQL**，包括写操作（DELETE/UPDATE 也真执行）。对写 SQL 要先用事务包起来再 ROLLBACK，或只在测试环境运行
- 返回的时间是**挂钟时间**（wall clock），包含锁等待、IO 等待，不是纯 CPU 时间
- 若 SQL 非常慢，`EXPLAIN ANALYZE` 也会等同样的时间

---

## 4. 日常开发应用

**「我刚写完一条 SQL，怎么 5 秒内判断它会不会慢」**

```
Step 1: EXPLAIN 一下，看这 4 列
  - type：有没有 ALL 或 index？
  - rows：数量级合理吗？
  - Extra：有没有 Using temporary / Using filesort？
  - key：走了你期望的索引吗？

Step 2: 判断规则
  - type=ALL + rows > 10000       → 大概率有问题，找索引
  - type=range/ref + rows 合理   → 暂时 OK
  - Extra 有 Using filesort       → ORDER BY 没走索引，加或调整索引
  - Extra 有 Using temporary      → GROUP BY / DISTINCT 没利用索引顺序
  - key=NULL + type=ALL           → 完全没索引，危险

Step 3: 如果有疑问但不确定
  - EXPLAIN FORMAT=JSON 看 cost_info.query_cost
  - 10 以下通常很快；1000+ 要警惕；10000+ 要优化
```

**实际操作清单：**

- 每次写完非主键点查的 SELECT，跑一次 `EXPLAIN`，养成习惯
- JOIN 两张表以上时，检查被驱动表的 JOIN 条件列是否有索引（`type=ALL` 在内层表是最贵的）
- `LIMIT 100000, 20` 这类深翻页：先看 `rows`，然后改成延迟关联（覆盖索引先拿主键 LIST，再用主键 IN 回表）
- ORM 生成的 SQL 不一定走你想要的索引——用 `make general-log-on` 或 `SET global general_log=ON` 抓实际 SQL，贴 `EXPLAIN`

---

## 5. 调优实战

### Case A：「explain 看起来 OK 但还是慢」

**症状：** `type=ref`，`rows=100`，Extra 正常，但 P99 延迟 500ms。

**排查思路：**

1. 实际行数是不是和估算差很多？

```sql
-- 先看估算
EXPLAIN FORMAT=JSON SELECT ... \G
-- 找 rows_examined_per_scan

-- 再看实际
EXPLAIN ANALYZE SELECT ...;
-- 对比 actual rows
```

2. 不是行数问题 → 看锁等待

```sql
SELECT * FROM performance_schema.events_waits_current WHERE OBJECT_NAME='your_table';
SHOW ENGINE INNODB STATUS;  -- 看 LATEST DETECTED DEADLOCK 和 TRANSACTIONS
```

3. 不是锁 → 看 IO（Buffer Pool 命中率）

```sql
SHOW STATUS LIKE 'Innodb_buffer_pool_read%';
-- Innodb_buffer_pool_reads / Innodb_buffer_pool_read_requests
-- 命中率 < 99% → 考虑增大 innodb_buffer_pool_size
```

---

### Case B：「rows 估算偏差太大」

**症状：** `rows=5000` 但实际返回 500 行；或反过来 `rows=50` 但实际扫 50000 行。

**原因：** 统计信息过期、数据分布倾斜、抽样精度不足。

**处理步骤：**

```sql
-- 1. 更新统计
ANALYZE TABLE user_profile;

-- 2. 提升索引统计精度（默认 8，可调大到 20-30）
SET GLOBAL innodb_stats_persistent_sample_pages=20;
ANALYZE TABLE user_profile;  -- 重新采样

-- 3. 验证
SELECT * FROM mysql.innodb_index_stats
WHERE table_name='user_profile' AND index_name='idx_city_age';
```

---

### Case C：「想强制走某个索引 / 禁用某个索引」

```sql
-- 强制走指定索引
SELECT * FROM user_profile FORCE INDEX (idx_city_age)
WHERE city='Taipei' AND age=30;

-- 只给优化器一个提示（优化器可能忽略）
SELECT * FROM user_profile USE INDEX (idx_city_age)
WHERE city='Taipei' AND age=30;

-- 禁用某个索引（让优化器不考虑它）
SELECT * FROM user_profile IGNORE INDEX (idx_bad)
WHERE city='Taipei';

-- 8.0 推荐：optimizer hints（不需要改 SQL 结构）
SELECT /*+ INDEX(user_profile idx_city_age) */ *
FROM user_profile WHERE city='Taipei' AND age=30;

-- 固定 JOIN 顺序
SELECT /*+ JOIN_ORDER(orders, user_profile) */ ...
FROM orders JOIN user_profile ON ...;
```

**什么时候用 hint：**
- 统计偏差导致优化器持续选错索引，ANALYZE TABLE 后仍不改善
- 特定业务 SQL 已知数据分布，需要确定性的执行计划
- **不要在所有 SQL 上撒 hint**——统计数据修复后，hint 可能反而更慢

---

### Case D：「Using filesort 怎么消掉」

Using filesort 的根本原因：ORDER BY 列不在索引里，或在索引里但前缀条件不满足有序性。

```sql
-- 原始 SQL（假设只有 idx_city_age (city, age)）
SELECT * FROM user_profile WHERE city='Taipei' ORDER BY username;
-- Extra: Using where; Using filesort  ← username 不在索引里

-- 解法 1：加联合索引覆盖 ORDER BY 列
ALTER TABLE user_profile ADD INDEX idx_city_username (city, username);
-- Extra: Using index condition  ← 消了 filesort

-- 解法 2：接受 filesort，但确保在内存里完成（不降级到磁盘）
SET SESSION sort_buffer_size=4*1024*1024;  -- 默认 256KB，太小会降级到磁盘

-- 解法 3：如果只要 TOP N，配合索引 LIMIT
SELECT * FROM user_profile WHERE city='Taipei' ORDER BY age LIMIT 10;
-- idx_city_age 正好覆盖 city= + age 排序 → 消 filesort
```

---

### Case E：「Using temporary 怎么消掉」

Using temporary 多见于 GROUP BY / DISTINCT / UNION（去重）。

```sql
-- 问题 SQL
SELECT city, COUNT(*) FROM user_profile GROUP BY city;
-- 若 city 没有索引 → Using temporary; Using filesort

-- 解法：city 加索引（或联合索引中 city 在最左）
ALTER TABLE user_profile ADD INDEX idx_city (city);
-- Extra 变为 Using index  ← 利用索引顺序分组，免临时表
```

---

## 6. 面试高频考点

### 必考对比：三阶段各做了什么

| 阶段 | 职责 | 常见面试陷阱 |
|---|---|---|
| Parser | 词法/语法分析 + 语义验证（表/列/权限） | 「Parser 只做语法？」—— 还有语义（表是否存在、权限） |
| Optimizer | 逻辑重写 + 成本估算 + 选索引/JOIN 顺序 | 「优化器选的一定是最优的？」—— 是基于统计的估算，可能错 |
| Executor | 驱动引擎读行 + 残余过滤 + 排序聚合 + 返回 | 「WHERE 条件都在引擎层处理？」—— 部分在 Server 层（Using where） |

---

### 必考：Explain type 排序

口诀：**ALL < index < range < ref < eq_ref < const < system**

- `ALL`：全表，警觉
- `index`：全索引扫描，比 ALL 只省了回表，依然慢
- `range`：索引范围，可接受
- `ref`：非唯一索引等值，较好
- `eq_ref`：唯一索引/主键 JOIN，很好
- `const`：主键/唯一索引常量等值，最优

---

### 必考：rows 为什么不准

`rows` 是基于 `mysql.innodb_index_stats` 采样统计的预估值，不是精确扫描计数。数据倾斜（某值占大比例）、统计过期（大量写入后没 ANALYZE）、抽样页数不足（`innodb_stats_persistent_sample_pages` 默认只有 8 页）都会导致偏差。

修复：`ANALYZE TABLE` 更新统计 + 必要时调大 `innodb_stats_persistent_sample_pages`。

---

### 必考：optimizer_trace 和 EXPLAIN 的区别

| | EXPLAIN | optimizer_trace |
|---|---|---|
| 显示什么 | 最终选中的执行计划 | 所有候选计划的成本对比过程 |
| 何时用 | 日常快速诊断 | 诊断「为什么没走期望的索引」 |
| 性能开销 | 极低 | 有开销，用完及时关闭 |
| 8.0 增强 | EXPLAIN ANALYZE 显示实际时间 | 无变化 |

---

### 高频追问与简答

**Q: Using index 和 Using index condition 有什么区别？**

A: `Using index` = 覆盖索引，SELECT 的所有列都在索引里，完全不需要回表。`Using index condition` = 索引下推（ICP），WHERE 中涉及索引列的条件被推到引擎层过滤，但 SELECT 列超出了索引范围，最终还是要回表，只是回表次数减少了。

**Q: EXPLAIN 为什么有时候 key=NULL 但 type=index？**

A: `type=index` 表示全索引扫描（扫整棵二级索引 B+ 树），不是等值/范围定位。这时 `key` 会是该索引名，而不是 NULL。`key=NULL` 对应的是 `type=ALL`（全表扫）。（注意：面试中这两个配合关系常被混淆）

**Q: 子查询什么时候会被改写成 JOIN？**

A: 优化器的 semijoin 优化会将 `WHERE id IN (SELECT ...)` 改写为 semijoin（在 optimizer_trace 的 `join_preparation` 步骤里能看到 `transformation`）。但以下情况不会改写：外层 SELECT 有 DISTINCT、子查询有 LIMIT/GROUP BY、子查询是相关子查询（DEPENDENT）且代价更高。

**Q: Explain ANALYZE 和 Explain 最大区别？**

A: Explain 是「计划」，基于统计估算，不执行 SQL。Explain ANALYZE 是「计划 + 执行」，真实跑一次 SQL，输出估算值和实际值的对比，能精确发现统计偏差和哪个节点最耗时。代价是：SQL 真的被执行，写操作需要额外保护。

---

## 7. 一句话总结

一条 SQL 经过 Parser 验证语法和表/列存在、Optimizer 基于统计成本模型选出执行计划、Executor 驱动 InnoDB Handler 逐行读取并在 Server 层做残余过滤。**读 Explain 先看 type（ALL = 警觉，const/eq_ref = 放心）、再看 rows（估算行数 × 1/filtered = 真实流量）、再看 Extra（Using temporary / Using filesort = 要优化，Using index = 好）**；看不懂为什么不走期望索引时，开 optimizer_trace 看 `cost_for_plan`；估算偏差大时，跑 `ANALYZE TABLE` 更新统计或用 `EXPLAIN ANALYZE` 看实际行数。
