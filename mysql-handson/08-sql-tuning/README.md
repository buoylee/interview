# SQL 调优实战

## 1. 核心问题

SQL 写完能跑，不等于跑得快。本章解决四件事：
**(a)** 慢 SQL 上线后怎么发现、怎么定位；
**(b)** JOIN / ORDER BY / GROUP BY 背后发生了什么，为什么有时候奇慢；
**(c)** 什么场景会产生临时表和 filesort，怎么消除；
**(d)** 深翻页和大表 COUNT 这两个「经典坑」的根本原因和标准解法。

---

## 2. 直觉理解

想象你是一个图书管理员，有人递给你一张单子说「帮我找出 2023 年出版、按销量排名第 100000 到 100020 的书」。

**没优化前的做法**：从第一本书开始，把所有 2023 年出版的书按销量排成一排，数到第 100000 本，再取 20 本。你翻了 100020 本书，只用了最后 20 本。

**优化后**：先只看销量目录（覆盖索引），从目录里数到第 100000 条，记下书号（主键），只用书号去仓库拿 20 本实体书。目录翻了 100000 行，但仓库只跑了 20 次。

这个图书馆类比贯穿本章：
- 索引 = 各种排序目录
- 回表 = 去仓库拿实体书
- filesort = 临时把书按某种顺序重新排一遍
- 临时表 = 在地板上堆了一大摊中间结果

---

## 3. 原理深入

### 3.1 慢查日志：从开到读

#### 开启与参数

MySQL 慢查日志有三个核心参数：

```sql
-- 查看当前状态
SHOW VARIABLES LIKE 'slow_query%';
SHOW VARIABLES LIKE 'long_query_time';
SHOW VARIABLES LIKE 'log_queries_not_using_indexes';

-- 动态开启（重启失效，生产推荐写入 my.cnf）
SET GLOBAL slow_query_log = ON;
SET GLOBAL long_query_time = 1;           -- 超过 1 秒记录（默认 10s，生产通常调到 0.5 或 1）
SET GLOBAL log_queries_not_using_indexes = ON;  -- 没走索引的也记（开发环境用，生产慎重——量大）
SET GLOBAL slow_query_log_file = '/var/log/mysql/slow.log';
```

**long_query_time 的坑**：它是 wall clock 时间，包含锁等待。一条 SQL 自身逻辑只要 10ms，但等锁等了 2s，也会进慢查日志。定位时要结合 `Lock_time` 字段区分。

#### 慢查日志格式解读

```
# Time: 2026-05-13T10:23:45.123456Z
# User@Host: app[app] @ localhost []  Id: 1024
# Query_time: 3.456789  Lock_time: 0.001234  Rows_sent: 20  Rows_examined: 1024000
# Bytes_sent: 4096
SET timestamp=1747132425;
SELECT o.* FROM orders o WHERE user_id = 100 ORDER BY created_at LIMIT 100000, 20;
```

关键字段：
- `Query_time`：总耗时（含锁等待）
- `Lock_time`：锁等待时间。Lock_time 远小于 Query_time → 慢在执行，不是锁
- `Rows_examined`：引擎扫描了多少行。`1024000` 行只返回 `20` 行 → 典型的索引缺失或深翻页
- `Rows_sent`：最终返给客户端的行数

**Rows_examined / Rows_sent 的比值是第一个报警指标**。比值 > 1000 往往意味着有问题。

#### 用工具聚合

生产环境慢查日志几分钟就能产生几十 MB，手动 grep 不现实。
聚合工具会先生成 fingerprint（SQL 指纹）：把 SQL 中的具体参数替换成占位符，将结构相同的查询归为同一类，再统计这类查询的次数和耗时。

```bash
# mysqldumpslow — MySQL 自带，按执行次数或总耗时聚合，粗用
mysqldumpslow -s t -t 10 /var/log/mysql/slow.log
# -s t：按总耗时排序；-t 10：取 Top 10

# pt-query-digest — Percona 出品，更强，能输出 fingerprint + 百分位耗时
pt-query-digest /var/log/mysql/slow.log \
  --order-by Query_time:sum \
  --limit 10 \
  > digest.txt
```

`pt-query-digest` 输出片段示例：

```
# Rank Query ID           Response time  Calls  R/Call V/M   Item
# ==== ================== ============== ====== ====== ===== ====
#    1 0xABCD1234ABCD1234  1234.5678 38.2% 50234  0.0246 0.18  SELECT orders
```

- `Calls`：这条 fingerprint（参数化后的 SQL）被执行了多少次
- `Response time`：占总慢查耗时的比例
- 先优化 **Rank 1**（通常是高频 + 高耗时的组合，性价比最高）

---

### 3.2 performance_schema top SQL 法

不想动慢查日志（或者 `long_query_time` 调高了漏掉了中等慢查），可以用 `performance_schema`：

```sql
-- 开启（5.7+ 默认开；如关了执行）
UPDATE performance_schema.setup_consumers
SET ENABLED = 'YES'
WHERE NAME = 'events_statements_history_long';

-- 查 Top 10 按总耗时
SELECT
    SCHEMA_NAME,
    DIGEST_TEXT,
    COUNT_STAR                        AS calls,
    ROUND(SUM_TIMER_WAIT / 1e12, 3)   AS total_sec,
    ROUND(AVG_TIMER_WAIT / 1e12, 6)   AS avg_sec,
    SUM_ROWS_EXAMINED,
    SUM_ROWS_SENT,
    SUM_NO_INDEX_USED                 AS no_index_calls,
    FIRST_SEEN,
    LAST_SEEN
FROM performance_schema.events_statements_summary_by_digest
WHERE SCHEMA_NAME = 'your_db'
ORDER BY total_sec DESC
LIMIT 10;
```

关键列解读：
- `SUM_NO_INDEX_USED`：这条 SQL 有多少次执行没走索引。非零就要警惕
- `SUM_ROWS_EXAMINED / SUM_ROWS_SENT`：同慢查日志，比值大 = 扫描浪费
- `DIGEST_TEXT`：参数化后的 SQL（具体值被 `?` 替代），方便聚合

对比慢查日志的优势：
- 不需要设 `long_query_time`，所有执行过的 SQL 都有记录
- 实时更新，不依赖文件 IO
- 记录了 `SUM_CREATED_TMP_TABLES`、`SUM_SORT_MERGE_PASSES` 等细节指标

---

### 3.3 JOIN 怎么找到匹配行：NLJ / BNL / INL / Hash Join

先不要背“第一代、第二代、第三代”。JOIN 从头到尾只是在解决一个问题：

> 已经拿到一边的一行后，怎样从另一边找到 JOIN 条件匹配的行？

旧版把 SNL → BNL → Hash Join 写成“三代”，容易让人误以为后者会依次淘汰前者。更准确的地图是：

```text
JOIN 找匹配行
├─ Nested Loop：从外表取行，再去内表找
│  ├─ 内表全表扫描：SNL（用于理解成本的基础模型）
│  ├─ 外表攒成一批、内表全扫：BNL（MySQL 8.0.20 前）
│  └─ 内表走索引：INL（有可用索引时的常见方案）
└─ Hash Join：一边建哈希表，另一边扫描并探测
```

这里其实有两个互相独立的问题：

1. **先处理哪一边**：Nested Loop 里叫外表/驱动表，Hash Join 里叫 build side。
2. **怎样找匹配行**：全表扫描、索引查找，还是哈希查找。

#### 用同一组数据理解所有算法

假设 `WHERE` 过滤后只剩两个用户：

| users.id | users.name |
|---:|---|
| 2 | Alice |
| 4 | Bob |

订单表有 5 行：

| orders.id | orders.user_id |
|---:|---:|
| 101 | 1 |
| 102 | 2 |
| 103 | 2 |
| 104 | 3 |
| 105 | 4 |

执行：

```sql
SELECT u.name, o.id
FROM users u
JOIN orders o ON o.user_id = u.id
WHERE u.id IN (2, 4);
```

结果是：

```text
Alice  102
Alice  103
Bob    105
```

下面只改变“怎样找到这 3 个匹配”，SQL 语义和结果都不变。

#### SNL：外表一行，内表完整扫描一次

Simple Nested-Loop（SNL）的思路最直接：

```text
拿 users.id = 2
  扫完整个 orders：[1, 2, 2, 3, 4] → 找到 102、103

拿 users.id = 4
  再扫完整个 orders：[1, 2, 2, 3, 4] → 找到 105
```

伪代码：

```text
for each user in filtered_users:          -- 外表 M 行
    for each order in all_orders:         -- 内表 N 行
        if order.user_id = user.id:
            output(user, order)
```

例子中 `orders` 被完整扫描 2 次，进行 `2 × 5 = 10` 次条件比较。一般情况下是：

```text
内表扫描次数：M 次
条件比较次数：M × N
```

SNL 在这里是帮助理解成本的基础模型，不要把“Simple Nested-Loop 已淘汰”理解成 Nested Loop 已经消失。MySQL 现在仍大量使用 Nested Loop，尤其是下面的 INL；问题只是“每个外表行都让内表全扫”通常太贵。

#### BNL：外表攒一批，内表再完整扫描

Block Nested-Loop（BNL）改进的是“内表被反复读取”，不是彻底消除 `M × N` 次比较。

如果 `join_buffer` 能一次装下用户 2 和用户 4：

```text
join_buffer = [users.id=2, users.id=4]

orders 只扫描一次：
  order.user_id=1 → 和 buffer 中的 2、4 比
  order.user_id=2 → 和 buffer 中的 2、4 比，匹配 2
  order.user_id=2 → 和 buffer 中的 2、4 比，匹配 2
  order.user_id=3 → 和 buffer 中的 2、4 比
  order.user_id=4 → 和 buffer 中的 2、4 比，匹配 4
```

假设 buffer 一次能装 K 个外表行：

```text
内表扫描次数：ceil(M / K)
条件比较次数：仍接近 M × N
```

所以 BNL 的核心是：

> 从“一行带着内表全扫”，改成“一批行带着内表全扫”，主要减少重复读表和 I/O。

MySQL 8.0.20 已移除 BNL；旧版本执行 BNL 时，传统 `EXPLAIN` 的 `Extra` 会显示 `Using join buffer (Block Nested Loop)`。

#### Hash Join：一边建字典，另一边查字典

对这个等值 JOIN，可以先把过滤后的 `users` 建成哈希表，这一步叫 build：

```text
hash_table = {
    2 → Alice,
    4 → Bob
}
```

再扫描 `orders`，每行根据 `user_id` 查哈希表，这一步叫 probe：

```text
order 101, user_id=1 → hash_table[1] → 没有
order 102, user_id=2 → hash_table[2] → Alice
order 103, user_id=2 → hash_table[2] → Alice
order 104, user_id=3 → hash_table[3] → 没有
order 105, user_id=4 → hash_table[4] → Bob
```

它不再让每个订单和所有用户逐个比较。等值 JOIN 的平均成本可以理解为：

```text
建立哈希表：M
扫描并探测：N
输出结果：R
总成本：接近 O(M + N + R)
```

`R` 是最终匹配行数；如果 JOIN 本身会产生海量结果，任何算法都无法省掉输出这些结果的成本。

版本边界要分清：

- MySQL 8.0.18 引入 Hash Join，当时只支持包含等值条件的 JOIN。
- MySQL 8.0.20 移除 BNL，原本会用 BNL 的位置改用 Hash Join，并开始支持纯非等值 JOIN、半连接、反连接和外连接。
- 对 `a.x < b.x` 这类纯非等值条件，执行树可能是 `Inner hash join (no condition)` 后再做 `Filter`。它不能像等值 key 那样直接定位，仍可能检查大量组合，不能套用 `O(M+N)`。

Hash Join 使用 `join_buffer_size` 控制内存上限；放不下时会使用磁盘文件，性能会下降。详细版本行为见 [MySQL 8.0 Hash Join Optimization](https://dev.mysql.com/doc/refman/8.0/en/hash-joins.html)。

#### INL：外表一行，内表走一次索引

如果给 `orders.user_id` 建索引：

```sql
CREATE INDEX idx_orders_user_id ON orders(user_id);
```

Index Nested-Loop（INL）可以这样执行：

```text
拿 users.id=2 → 用 idx_orders_user_id 直接定位订单 102、103
拿 users.id=4 → 用 idx_orders_user_id 直接定位订单 105
```

伪代码：

```text
for each user in filtered_users:
    index_lookup(orders.user_id, user.id)
```

它仍然是 Nested Loop，只是内层动作从“全表扫描”变成“索引查找”。简化后的成本是 `O(M × log N + R)`，实际还取决于索引高度、缓存命中、回表次数和数据是否集中。

这也是为什么“让过滤后较小的结果集做驱动表”经常有用：外表 M 越小，内表索引查找次数越少。但不能推导成“有索引一定走 INL”或“INL 永远比 Hash Join 快”；优化器会根据行数、选择性和 I/O 成本选择计划。大量数据需要 JOIN 时，一次顺序扫描加 Hash Join 可能比大量随机索引查找更便宜。

#### 驱动表只适合解释 Nested Loop

Nested Loop 中：

```text
for each row in outer_table:     -- 外表，也叫驱动表
    find matches in inner_table  -- 内表，也叫被驱动表
```

“小表驱动大表”里的小，指的是 **经过 `WHERE` 过滤后预计进入 JOIN 的行数少**，不是磁盘上的原始表行数少：

```text
users  原表 100 行，过滤后仍是 100 行
orders 原表 1,000 万行，过滤后只剩 10 行

如果走 INL：
orders 做驱动表 → 只需对 users 做 10 次索引查找
users 做驱动表  → 需要对 orders 做 100 次索引查找
```

对于 `INNER JOIN`，SQL 中谁写在前面不保证谁先执行，优化器可以重排。对于 Hash Join，也不要硬套“驱动表”。下表只是对照两套算法各自如何称呼两边，不是一对一的术语翻译：

| Nested Loop 术语 | Hash Join 术语 | 含义 |
|---|---|---|
| outer / 驱动表 | build side | 先提供行；Hash Join 通常希望 build 结果较小、能放入内存 |
| inner / 被驱动表 | probe side | Nested Loop 被重复查找；Hash Join 扫描后查询哈希表 |

实际哪一边是 build、哪一边是 probe，要看执行计划，不要只看 SQL 书写顺序。

#### 不要一上来就用 STRAIGHT_JOIN

`STRAIGHT_JOIN` 会强制优化器按 SQL 中的表顺序执行：

```sql
-- 强制 users 先处理，作为 Nested Loop 的外表
SELECT STRAIGHT_JOIN u.name, COUNT(o.id)
FROM users u
JOIN orders o ON o.user_id = u.id
WHERE u.country = 'CN'
GROUP BY u.id;
```

它适合“`EXPLAIN ANALYZE` 已证明优化器选错顺序，更新统计信息和调整索引后仍然选错”的场景。不要仅凭“小表驱动大表”就强制顺序；数据分布变化后，今天正确的提示可能变成明天的坏计划。

#### 怎样看执行计划

优先使用树形计划，它能直接显示 JOIN 算法和两边的动作：

```sql
EXPLAIN FORMAT=TREE
SELECT ...;

-- 会真正执行 SELECT，并显示 actual rows / loops / time
EXPLAIN ANALYZE
SELECT ...;
```

重点识别：

```text
Index lookup on orders ...       → INL 的内表正在做索引查找
Inner hash join (...)            → Hash Join
  -> Table scan ...              → probe side
  -> Hash
      -> Table scan ...          → build side

Using join buffer (Block Nested Loop) → 8.0.20 前的 BNL
Using join buffer (hash join)         → Hash Join
```

不要把 `type=ALL` 直接翻译成“必须加索引”。要继续问：

1. 过滤后实际进入 JOIN 的行数是多少？
2. JOIN 条件有没有可用、选择性合适的索引？
3. `EXPLAIN ANALYZE` 的 `actual rows` 和 `loops` 是否导致大量重复工作？
4. Hash Join 是否只需顺序扫描两边，反而比大量随机索引查找便宜？

在本实验使用的 MySQL 8.0.36 中：

```sql
SHOW SESSION VARIABLES LIKE 'join_buffer_size';
SELECT @@optimizer_switch\G
```

`block_nested_loop=on/off` 控制的是 Hash Join，尽管名字仍然保留 BNL。`hash_join=on/off` 只在 8.0.18 有效，从 8.0.19 起已经不再起作用。

最后用四句话记忆：

```text
SNL  = 一行 + 内表全扫
BNL  = 一批 + 内表全扫
INL  = 一行 + 内表索引查找
Hash = 一边建哈希表 + 另一边扫描探测
```

---

### 3.4 ORDER BY 优化 + filesort 两种算法 + sort_buffer

#### 何时走索引序，何时触发 filesort

ORDER BY 最好的情况是**直接沿着索引叶子节点顺序返回**，不需要额外排序。条件：
1. ORDER BY 列和 WHERE 等值列一起构成索引的最左前缀
2. ORDER BY 列方向一致（全 ASC 或全 DESC，8.0.11+ 支持混合方向的 Descending Index）

```sql
-- 表上有索引 (user_id, created_at)
SELECT * FROM orders WHERE user_id = 100 ORDER BY created_at;
-- → type=ref, Extra 无 Using filesort，直接走索引序 ✓

SELECT * FROM orders WHERE user_id > 100 ORDER BY created_at;
-- → user_id 是范围，created_at 不能走索引序，触发 filesort ✗

SELECT * FROM orders WHERE user_id = 100 ORDER BY created_at DESC, id ASC;
-- 5.7：混合方向触发 filesort。8.0.11+ 建 (user_id, created_at DESC, id ASC) 可解决
```

EXPLAIN Extra 出现 `Using filesort` = 触发了 Server 层排序，**不等于一定慢**，但意味着 CPU 和内存/磁盘消耗增加。

#### filesort 两种算法

**Algorithm 1：rowid sort（两次传递，旧版默认）**

```
1. 扫描满足 WHERE 的行，提取 (排序列值, rowid) 对放入 sort_buffer
2. 在 sort_buffer 里排序
3. 按排好的 rowid 顺序回表取其余列
```

缺点：步骤 3 的回表是按 rowid 顺序，可能是随机 IO（对 InnoDB 聚簇索引而言实际是按主键，比物理行地址略好，但依然可能随机）。

**Algorithm 2：full sort（单次传递，5.6+ 默认倾向）**

```
1. 扫描满足 WHERE 的行，提取 (排序列值, 所有需要的列值) 放入 sort_buffer
2. 在 sort_buffer 里排序
3. 直接从 sort_buffer 输出，不回表
```

优点：省去回表的随机 IO。
缺点：sort_buffer 里每行更宽，`sort_buffer_size` 容纳的行数更少。

旧版本中，`max_length_for_sort_data` 曾用于影响是否把额外列放进 sort buffer。但本实验使用 MySQL 8.0.36，而该变量从 8.0.20 起已经 deprecated 且不再生效，不能再用“行宽是否超过 4096 字节”判断算法。

MySQL 8.0.20+ 应通过 optimizer trace 的 `filesort_summary.sort_mode` 看实际模式：

```text
<sort_key, rowid>                     → sort buffer 保存排序键 + rowid，排序后回表
<sort_key, additional_fields>         → 保存排序键 + 查询需要的列
<sort_key, packed_additional_fields>  → 同上，但额外列使用紧凑格式
```

版本依据见 [MySQL 8.0 ORDER BY Optimization](https://dev.mysql.com/doc/refman/8.0/en/order-by-optimization.html)。

#### sort_buffer 和磁盘合并

`sort_buffer_size` 默认 256KB（可以全局或会话级设置），每个排序操作独占一个 sort_buffer。

如果排序数据超过 sort_buffer_size：
1. 内存里先排一轮，写一个临时文件（run）
2. 再填充 sort_buffer，排序，写第二个 run
3. 最后做磁盘上的 merge sort（归并合并）

#### `SHOW STATUS` 到底统计哪些 SQL

`SHOW STATUS` 不是“上一条 SQL 的执行结果”，而是状态计数器。没有写 `GLOBAL` 或 `SESSION` 时，默认等价于 `SHOW SESSION STATUS`：

| 写法 | 统计范围 | 适合做什么 |
|---|---|---|
| `SHOW SESSION STATUS` / `SHOW STATUS` | 当前物理连接建立以来，或当前连接上次 `FLUSH STATUS` 以来的累计值 | 在同一连接中比较单条 SQL 前后增量 |
| `SHOW GLOBAL STATUS` | 整个 MySQL 实例所有连接的汇总值 | 观察实例级趋势，不能直接归因到某条 SQL |

`LIKE 'Sort_merge_passes'` 只是在返回结果中匹配状态变量名称，不是在筛选 SQL 文本或 SQL 历史。

`Sort_merge_passes` 的含义是“排序算法执行了多少次临时文件归并轮次”，不是 SQL 数量，也不是 filesort 次数。一条 SQL 可能包含多个排序操作，一次大排序也可能产生多轮 merge pass。

要判断目标 SQL 造成了多少 merge pass，应该在 **同一个物理连接** 中比较前后差值：

```sql
-- 1. 记录 before，例如 Sort_merge_passes = 3
SHOW SESSION STATUS LIKE 'Sort_merge_passes';

-- 2. 只执行目标 SQL
SELECT ...
ORDER BY ...;

-- 3. 记录 after，例如 Sort_merge_passes = 5
SHOW SESSION STATUS LIKE 'Sort_merge_passes';

-- 目标 SQL 的增量 = after - before = 2
```

如果两次查询之间还执行了别的 SQL，差值就属于这些 SQL 的合计。连接池或 GUI 如果中途更换物理连接，前后值也不能比较。

实验环境还可以先清零当前连接：

```sql
-- 仅建议在个人实验环境使用
FLUSH STATUS;

SELECT ...
ORDER BY ...;

SHOW SESSION STATUS LIKE 'Sort%';
```

`FLUSH STATUS` 会把当前线程的 session status 加入 global status，然后把当前 session 计数清零；它需要 `FLUSH_STATUS` 或 `RELOAD` 权限，并会写入 binary log，不要为了测一条生产 SQL 随意执行。生产环境更适合比较前后差值。

常用 `Sort_*` 指标：

```text
Sort_merge_passes  → 临时文件归并轮次
Sort_rows          → 被排序的累计行数
Sort_range         → 使用 range 访问后执行的排序次数
Sort_scan          → 扫描表后执行的排序次数
```

`Sort_merge_passes` 的增量大于 0，证明观察窗口内发生了外部归并；等于 0 只表示没有 merge pass，不能在没有“清零或前后快照”的情况下推断上一条 SQL。若要确认某次 filesort 创建了多少临时文件，可查看 optimizer trace 的 `filesort_summary.number_of_tmp_files`。

要直接定位具体 SQL，可查 Performance Schema 的逐语句字段：

```sql
SELECT
    THREAD_ID,
    EVENT_ID,
    LEFT(SQL_TEXT, 200) AS sql_text,
    SORT_MERGE_PASSES,
    SORT_ROWS,
    SORT_SCAN,
    SORT_RANGE
FROM performance_schema.events_statements_history_long
WHERE SORT_MERGE_PASSES > 0
ORDER BY TIMER_START DESC
LIMIT 20;
```

`events_statements_history_long` 保存全实例最近结束的有限条语句，并非持久日志；需要 `events_statements_history_long` consumer 已启用，开启方式见上文“3.2 performance_schema top SQL 法”。其中 `SORT_MERGE_PASSES` 是具体到单条语句的值。

调整策略：

```sql
-- 会话级临时调大（仅当前连接有效，不要全局调大——per-connection 内存）
SET SESSION sort_buffer_size = 4 * 1024 * 1024;  -- 4MB

-- 如果是 SELECT * 改成 SELECT 具体列，可以减少 full sort 每行宽度
```

**最优解还是加索引**，让 ORDER BY 走索引序，彻底消除 filesort。

---

### 3.5 GROUP BY 优化 + 8.0 取消隐式排序

#### GROUP BY 的三种执行路径

**路径 1：松散索引扫描（Loose Index Scan）**

适用条件：GROUP BY 列 + 聚合函数 = 索引前缀，聚合是 MIN/MAX 类。

```sql
-- 索引 (category_id, price)
SELECT category_id, MIN(price), MAX(price)
FROM products
GROUP BY category_id;
```

EXPLAIN Extra：`Using index for group-by`

原理：B+ 树上每个 `category_id` 的最小/最大 `price` 在叶子节点链表的起止位置，只需跳跃扫描各组的边界，不需要扫描每一行。极快，扫描的行数 = 组数，不是总行数。

**路径 2：紧凑索引扫描（Tight Index Scan）**

适用条件：GROUP BY 列是索引前缀，不一定有 MIN/MAX 优化，但按索引顺序扫，省了排序/临时表。

```sql
-- 索引 (user_id, created_at)
SELECT user_id, COUNT(*) FROM orders GROUP BY user_id;
```

EXPLAIN Extra：`Using index`（覆盖）或无额外标记，无 `Using temporary` / `Using filesort`。

**路径 3：临时表 + filesort（最差）**

GROUP BY 列不是索引前缀，或者列上有函数。Server 层要先把所有行物化到临时表，再排序，再聚合。

EXPLAIN Extra：`Using temporary; Using filesort`

```sql
-- orders 没有 (status) 索引
SELECT status, COUNT(*) FROM orders GROUP BY status;
-- → Using temporary; Using filesort（如果 status 没有索引）
```

#### 8.0 取消 GROUP BY 隐式排序

MySQL 5.7 及之前，`GROUP BY col` 会**隐式 ORDER BY col**。很多人写 `GROUP BY` 后不加 `ORDER BY`，结果是排好序的，这是副作用，不是保证。

**MySQL 8.0 取消了这个行为**：`GROUP BY` 不再隐式排序。如果业务需要排序，必须显式写 `ORDER BY`。

```sql
-- 5.7：结果按 user_id 排序（隐式行为）
SELECT user_id, COUNT(*) FROM orders GROUP BY user_id;

-- 8.0：结果顺序不确定，要加 ORDER BY
SELECT user_id, COUNT(*) FROM orders GROUP BY user_id ORDER BY user_id;
```

实际影响：从 5.7 升 8.0，依赖隐式排序的业务代码可能结果顺序变了但不报错——**最难排查的 bug 之一**。

#### GROUP BY 优化技巧

```sql
-- 1. 确保 GROUP BY 列有索引（同时 WHERE + GROUP BY 能复用联合索引）
-- 例：(user_id, status) 上有联合索引
SELECT user_id, status, COUNT(*)
FROM orders
WHERE user_id IN (1,2,3)
GROUP BY user_id, status;
-- → type=range，Using index（覆盖），无 Using temporary

-- 2. 用 ORDER BY NULL 消除 5.7 的隐式排序（如果不需要排序）
SELECT status, COUNT(*) FROM orders GROUP BY status ORDER BY NULL;
-- 5.7 下可省去排序步骤

-- 3. 数据量大时考虑在应用层做二次聚合（先按 shard key GROUP BY 部分结果，再汇总）
```

---

### 3.6 Using temporary 触发条件 + 内存/磁盘临时表

#### 什么场景触发临时表

`Using temporary` 出现在 EXPLAIN Extra 里，意味着 MySQL Server 层需要一张中间临时表来暂存结果。常见触发场景：

| 场景 | 说明 |
|---|---|
| GROUP BY 列不是索引前缀 | 要把全部数据堆到临时表再聚合 |
| UNION（非 UNION ALL） | 需要临时表来做 DISTINCT 去重 |
| ORDER BY + GROUP BY 用了不同的列 | 无法用单索引同时满足 |
| SELECT DISTINCT 大数据量 | 去重需要临时表（有时走索引能避免） |
| FROM 子查询（derived table） | 子查询结果物化到临时表（5.7 有 Derived Condition Pushdown，8.0 更激进） |
| WINDOW 函数（8.0+） | 取决于窗口定义，复杂窗口需要临时表 |

#### 内存临时表 vs 磁盘临时表

临时表优先在内存里创建（使用 TempTable 引擎，8.0.13+ 默认；或旧版 MEMORY 引擎），超出大小限制后转到磁盘（InnoDB 或 MyISAM 磁盘临时表）。

控制大小的参数：

```sql
SHOW VARIABLES LIKE 'tmp_table_size';           -- 单个内存临时表上限，默认 16MB
SHOW VARIABLES LIKE 'max_heap_table_size';       -- MEMORY 引擎表上限，默认 16MB
-- 实际限制 = MIN(tmp_table_size, max_heap_table_size)

-- 8.0.13+ TempTable 引擎额外参数
SHOW VARIABLES LIKE 'temptable_max_ram';         -- 默认 1GB（所有内存临时表总量上限）
SHOW VARIABLES LIKE 'temptable_max_mmap';        -- 溢出到内存映射文件的大小上限，默认 1GB
```

**诊断是否产生了磁盘临时表**：

```sql
SHOW GLOBAL STATUS LIKE 'Created_tmp_tables';          -- 总内存临时表创建次数
SHOW GLOBAL STATUS LIKE 'Created_tmp_disk_tables';     -- 总磁盘临时表创建次数

-- 比值：Created_tmp_disk_tables / Created_tmp_tables > 0.1（10%）→ 临时表太大，要优化
```

磁盘临时表比内存临时表慢 **10-100 倍**（取决于磁盘速度），是显著的性能杀手。

#### 消除 / 缩小临时表的手段

```sql
-- 1. 给 GROUP BY / ORDER BY 列加索引，避免触发
-- 2. 精简 SELECT 列，减少单行宽度，让临时表装下更多行
-- 3. 提前用 WHERE 缩小数据集
-- 4. 调大 tmp_table_size（治标，不如加索引）
SET SESSION tmp_table_size = 64 * 1024 * 1024;  -- 64MB，仅当前会话

-- 5. UNION 改 UNION ALL（如果业务允许重复）
-- UNION 强制去重（隐式 DISTINCT），必须物化临时表
-- UNION ALL 不去重，直接合并结果集，无需临时表
```

---

### 3.7 LIMIT 深翻页：延迟关联法

#### 为什么 LIMIT 100000, 20 很慢

```sql
SELECT * FROM orders ORDER BY created_at LIMIT 100000, 20;
```

MySQL 的 LIMIT offset, count 不是「跳过 offset 行」，而是「扫描 offset+count 行，丢弃前 offset 行」。

执行流程：
1. 按 `created_at` 索引顺序扫描
2. 每行都要**回表**取 `SELECT *` 的全部列
3. 扫完 100020 行（100000 行丢弃 + 20 行返回）
4. 返回 20 行

所以 `LIMIT 100000, 20` = **100020 次回表**，随着 offset 增大线性变慢。`LIMIT 1000000, 20` = 百万次回表。

#### 方案一：延迟关联（Deferred Join）

思路：先只在覆盖索引上扫 100020 行（不回表），拿到 20 个主键，再精准回表 20 次。

```sql
-- 慢的写法：100020 次回表
SELECT * FROM orders ORDER BY created_at LIMIT 100000, 20;

-- 改写：延迟关联，先在覆盖索引上拿到主键
SELECT o.*
FROM orders o
JOIN (
    SELECT id FROM orders ORDER BY created_at LIMIT 100000, 20
) t ON o.id = t.id;
```

性能差异：
- 原写法：扫索引 100020 次 + 回表 100020 次
- 改写：扫覆盖索引 100020 次 + 回表 20 次
- offset 越大，差距越明显（offset=100000 时回表减少 99.98%）

**前提**：`(created_at, id)` 或 `(created_at)` 上有索引，子查询能走覆盖索引。

#### 方案二：主键游标分页（Cursor / Keyset Pagination）

适合从第 1 页翻到第 N 页的场景（产品上叫"加载更多"或"无限滚动"）：

```sql
-- 第一页
SELECT * FROM orders ORDER BY created_at, id LIMIT 20;

-- 记录最后一行的 (created_at, id) = ('2026-01-15 10:23:45', 98765)

-- 下一页：WHERE 替代 OFFSET
SELECT * FROM orders
WHERE (created_at, id) > ('2026-01-15 10:23:45', 98765)
ORDER BY created_at, id
LIMIT 20;
```

优点：
- 无论翻到第几页，始终只扫 20 行（O(1)，不是 O(offset)）
- 彻底解决深翻页性能问题

缺点：
- 不支持随机跳页（只能前后翻）
- 需要客户端记录游标（last seen `created_at` + `id`）
- `(created_at, id)` 必须是唯一的组合（通常加主键 id 保证）

#### UNION vs UNION ALL（附）

```sql
-- UNION：隐式 DISTINCT，需要临时表去重
SELECT id FROM table_a
UNION
SELECT id FROM table_b;

-- UNION ALL：不去重，直接合并，快很多
SELECT id FROM table_a
UNION ALL
SELECT id FROM table_b;
```

如果业务上两个子查询结果不会重叠（或不介意重复），**永远用 UNION ALL**。UNION 的代价 = 临时表 + 去重排序。

---

### 3.8 COUNT 三种写法 + 大表 count 用估值

#### count(*) vs count(1) vs count(col) 的区别

这是面试高频题，很多人答错。

**count(*)**：统计所有行，包括 NULL。InnoDB 8.0 对 `count(*)` 有专门优化：会选最小的索引扫（二级索引比聚簇索引页数少，IO 更少）。**推荐写法**。

**count(1)**：和 `count(*)` 完全等价。`1` 是非 NULL 常量表达式，每行都返回 1，不会因为 NULL 跳过。MySQL 优化器会把它当 `count(*)` 处理，执行计划相同。

**count(col)**：只统计 col 列不为 NULL 的行数。如果列有 NULL，结果 < 总行数。比 `count(*)` 多了一步 NULL 检查。

```sql
-- 三种写法结果可能不同：
SELECT COUNT(*) FROM orders;           -- 总行数（含 NULL）= 1000
SELECT COUNT(1) FROM orders;           -- 同上 = 1000
SELECT COUNT(deleted_at) FROM orders;  -- deleted_at 不为 NULL 的行数 = 50（如果 950 行 deleted_at 是 NULL）
```

**性能排名**（从官方文档和源码角度）：`count(*)` ≥ `count(1)` >> `count(非主键列)` > `count(主键列)`

注意：`count(主键)` 不比 `count(*)` 快，因为主键必须逐行取值判断（尽管主键不为 NULL，优化器不一定能提前确认）。

#### 为什么大表 COUNT 慢

InnoDB 没有像 MyISAM 那样在元数据里维护精确的行数（因为 MVCC：不同事务看到的行数不一样，无法用单一数字缓存）。每次 `COUNT(*)` 都要扫描一遍索引。

1000 万行的表，走最小二级索引扫，也需要几秒到几十秒（取决于 buffer pool 命中率）。

#### 大表 count 的四种替代方案

**方案 1：information_schema 估值（秒级，精度约 ±5%）**

```sql
SELECT TABLE_ROWS
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'your_db'
  AND TABLE_NAME = 'orders';
```

`TABLE_ROWS` 是基于采样的估算，InnoDB 表误差约 40-50%（官方文档说可能更高）。适合展示"大约有多少行"的场景，不适合需要精确值的。

更准的估值：

```sql
-- information_schema 基于 InnoDB 统计（可通过 ANALYZE TABLE 刷新）
ANALYZE TABLE orders;
SELECT TABLE_ROWS FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'your_db' AND TABLE_NAME = 'orders';
```

**方案 2：EXPLAIN 估值（毫秒级）**

```sql
EXPLAIN SELECT COUNT(*) FROM orders;
-- rows 列 = 优化器估算的总行数，比 information_schema 快，误差相当
```

可以用 EXPLAIN 的 `rows` 值作为大表 count 的快速估算。

**方案 3：专门的计数表（精确，写多读少场景）**

```sql
-- 维护一个计数表
CREATE TABLE table_counts (
    table_name VARCHAR(64) PRIMARY KEY,
    cnt BIGINT NOT NULL DEFAULT 0
);

-- 写入时同步更新（在事务里）
START TRANSACTION;
INSERT INTO orders (...) VALUES (...);
UPDATE table_counts SET cnt = cnt + 1 WHERE table_name = 'orders';
COMMIT;

-- 读 count 直接查 table_counts，O(1)
SELECT cnt FROM table_counts WHERE table_name = 'orders';
```

注意：要在同一个事务里维护，否则 count 和实际行数可能短暂不一致。

**方案 4：Redis 计数器**

写入/删除时原子 INCR/DECR Redis，读 count 查 Redis。适合高并发计数，但需要处理 Redis 和 MySQL 的一致性问题（如服务重启后从 MySQL 重新同步）。

---

## 4. 日常开发应用

### "我刚写完 SQL，5 秒判断有没有问题" checklist

写完每条 SQL 之后，对着下面 5 个问题过一遍：

```
□ 1. EXPLAIN 的 type 列有没有 ALL？
      ALL = 全表扫，是继续分析的信号，不是“必须加索引”的结论
      小表、低选择性查询或 Hash Join 中，全表扫可能就是更便宜的计划

□ 2. EXPLAIN Extra 有没有 Using filesort / Using temporary？
      有 = ORDER BY 或 GROUP BY 没走索引序，review 索引设计

□ 3. rows × filtered / 100 是不是远大于 rows_sent？
      EXPLAIN 的 rows 是估算，实际看慢查日志的 Rows_examined
      比值 > 1000 是危险信号

□ 4. JOIN 采用哪种算法，actual rows × loops 是否过大？
      INL：看内表索引查找次数；Hash Join：看 build/probe 两边实际扫描行数
      不能仅凭 type = ALL 判断要加索引，要比较重复查找和一次顺序扫描的成本

□ 5. 有没有 LIMIT 大 offset？（LIMIT 10000+, N）
      有 = 改延迟关联或改游标分页

□ 附加：SELECT 是否用了 *？
      SELECT * 可能让覆盖索引失效（需要回表），也让网络传输变重
```

### 索引设计原则（综合 ch03）

详细原理见 [03-indexing/README.md](../03-indexing/README.md)，本章补充调优视角的两条原则：

**联合索引列顺序三条原则**（来自 ch03 §3.3，此处强调）：
1. **查询模式优先**：先确定高频 SQL 需要复用哪些最左前缀，以及 `ORDER BY` / `GROUP BY` 是否也要使用索引顺序
2. **等值列通常放在范围列前**：让更多 key part 参与区间定位；这说的是索引定义顺序，不是 WHERE 条件的书写顺序
3. **区分度只作同等候选间的参考**：若查询总是同时对两列做等值过滤，交换两列不会改变最终命中行数；还要看其他查询的前缀复用和排序需求

**调优视角额外两条**：
4. **覆盖查询热路径**：最热的 2-3 条 SQL 如果能走覆盖索引（不回表），优先建这些索引
5. **索引不是越多越好**：每个二级索引写入时都要维护（INSERT/UPDATE/DELETE 都要更新索引树），写多读少的表索引要精简

---

## 5. 调优实战

### Case A：慢 SQL 上线后定位

**现象**：上线 2 小时后，慢查日志里出现大量 `Query_time: 4.5`，涉及 `orders` 表。

**定位步骤**：

```bash
# 1. 用 pt-query-digest 找 Top 耗时 SQL
pt-query-digest /var/log/mysql/slow.log --limit 5 > /tmp/digest.txt
```

发现 fingerprint：
```sql
SELECT * FROM orders WHERE user_id = ? AND status = ? ORDER BY created_at DESC LIMIT ?
```

```sql
-- 2. 拿到 EXPLAIN
EXPLAIN SELECT * FROM orders
WHERE user_id = 12345 AND status = 'pending'
ORDER BY created_at DESC LIMIT 20\G
```

```
         id: 1
select_type: SIMPLE
      table: orders
       type: ref
   key: idx_user_id          -- 走了 user_id 索引
      rows: 85000             -- 但扫了 8.5 万行！
     Extra: Using index condition; Using filesort  -- filesort！
```

**分析**：走了 `idx_user_id`，但 `status` 没有索引过滤，`created_at` 没走索引序，触发 filesort。85000 行回表 + filesort 排序。

**解法**：

```sql
-- 加联合索引（等值列 user_id/status 在前，ORDER BY 列 created_at 在后）
ALTER TABLE orders
ADD INDEX idx_user_status_created (user_id, status, created_at);
```

```sql
-- 验证
EXPLAIN SELECT * FROM orders
WHERE user_id = 12345 AND status = 'pending'
ORDER BY created_at DESC LIMIT 20\G
```

```
  type: ref
   key: idx_user_status_created
  rows: 20             -- 从 85000 降到 20
 Extra: Using index condition   -- 无 Using filesort ✓
```

Query_time 从 4.5s → 1ms。

---

### Case B：ORDER BY ... LIMIT 慢 → 索引序解决

**现象**：

```sql
-- 1.2s，EXPLAIN rows=50000，Using filesort
SELECT id, title, created_at FROM articles
WHERE category_id = 5
ORDER BY created_at DESC
LIMIT 20;
```

**分析**：`category_id` 上有索引，但 `created_at` 没有跟 `category_id` 的联合索引，ORDER BY 走 filesort。

**解法**：

```sql
-- 建联合索引，ORDER BY 列放后
ALTER TABLE articles
ADD INDEX idx_cat_created (category_id, created_at DESC);
-- 8.0.11+ 支持 Descending Index，可以精确匹配 ORDER BY created_at DESC
```

```sql
EXPLAIN SELECT id, title, created_at FROM articles
WHERE category_id = 5
ORDER BY created_at DESC
LIMIT 20\G
-- type=ref, key=idx_cat_created, rows=20, Extra=Using index ← 覆盖索引！
```

**小细节**：`SELECT id, title, created_at` 正好是索引列的超集（假设 `id` 是主键，包含在二级索引里）或者把 `title` 也加进索引做覆盖，可以彻底消除回表。

---

### Case C：GROUP BY 大字段慢 → 临时表 + filesort 双重打击

**现象**：

```sql
-- 8s，EXPLAIN: Using temporary; Using filesort
SELECT customer_city, COUNT(*) AS cnt
FROM orders
WHERE created_at >= '2026-01-01'
GROUP BY customer_city
ORDER BY cnt DESC
LIMIT 10;
```

**分析**：
- `customer_city` 没有索引，GROUP BY 无法走索引扫描 → `Using temporary`
- ORDER BY 的是聚合结果 `cnt`，不是表列，无法走索引序 → `Using filesort`
- 双重打击：临时表物化全部结果（可能有百万行），再排序

**解法 1（加索引，减少临时表行数）**：

```sql
-- 先缩小数据集：给 created_at 加索引，让 WHERE 过滤先走索引
ALTER TABLE orders ADD INDEX idx_created (created_at);

-- 可能还不够，如果过滤后仍有大量行要 GROUP BY
-- 考虑 (created_at, customer_city) 联合索引，让 GROUP BY 也走索引
ALTER TABLE orders ADD INDEX idx_created_city (created_at, customer_city);
```

```sql
-- 改写：先 WHERE 过滤用索引，GROUP BY 走 (created_at, customer_city) tight scan
EXPLAIN SELECT customer_city, COUNT(*) AS cnt
FROM orders
WHERE created_at >= '2026-01-01'
GROUP BY customer_city
ORDER BY cnt DESC
LIMIT 10\G
-- 理想：type=range，Using index，无 Using temporary
```

**解法 2（应用层缓存）**：这种"TOP 城市"聚合查询，结果可以缓存在 Redis 里（TTL 5 分钟），不需要每次实时查。

---

### Case D：COUNT(*) 大表超时 → 改估值

**现象**：

```sql
-- 管理后台展示"订单总量 xxx 单"，orders 表 5000 万行
SELECT COUNT(*) FROM orders;
-- 每次 15-20s，DBA 叫停
```

**解法**：

```sql
-- 方案 A：EXPLAIN 估值（毫秒，误差 ±10-30%，够展示用）
EXPLAIN SELECT COUNT(*) FROM orders;
-- 取 rows 列的值

-- 方案 B：information_schema（定期 ANALYZE TABLE 后误差 < 5%）
ANALYZE TABLE orders;  -- 更新统计（会锁表短暂，生产在低峰期）
SELECT TABLE_ROWS FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'orders';

-- 方案 C：维护专用计数表（精确，如果业务需要）
-- 在订单创建/删除的事务里同步 UPDATE order_count SET cnt = cnt ± 1
SELECT cnt FROM order_count WHERE id = 1;
```

**展示策略**：管理后台通常可以接受"约 5000 万单"，用估值 + 定期刷新完全够用。精确计数只在财务对账等场景才需要。

---

### Case E：大 JOIN 慢 → 减少驱动行 / 加过滤索引

**现象**：

```sql
-- 3s，分析后发现 users 做外表，触发大量 orders 索引查找
SELECT u.name, SUM(o.amount) AS total
FROM orders o
JOIN users u ON u.id = o.user_id
WHERE o.created_at >= '2026-04-01'
GROUP BY u.id, u.name;
```

EXPLAIN 显示：

```
id  table  type   key           rows    Extra
1   u      ALL    NULL          500000  Using temporary; Using filesort
1   o      ref    idx_user_id   12      Using where
```

users 被选为外表，全表扫 50 万行；随后每个用户都通过 `idx_user_id` 查一次 orders，形成约 50 万次索引查找。

**分析**：这是 INL，不是 BNL。优化器把 users（50 万行）选为驱动表，orders 走 `idx_user_id` 作为内表。看起来有索引，但 `o.created_at >= '2026-04-01'` 如果能把 orders 过滤到很少的行，更便宜的路径是先读过滤后的 orders，再按 users 主键查用户。

**解法**：

```sql
-- 1. 给 orders.created_at 加索引，让 WHERE 先过滤
ALTER TABLE orders ADD INDEX idx_created (created_at);

-- 2. 用 STRAIGHT_JOIN 强制 orders 作为驱动表（如果优化器仍然选错）
SELECT STRAIGHT_JOIN u.name, SUM(o.amount) AS total
FROM orders o                         -- orders 在前 = 驱动表
JOIN users u ON u.id = o.user_id
WHERE o.created_at >= '2026-04-01'
GROUP BY u.id, u.name;
```

```sql
-- 3. 验证：orders 先走 idx_created，过滤后只有少量行，users 作为内表走主键
EXPLAIN SELECT STRAIGHT_JOIN u.name, SUM(o.amount) AS total
FROM orders o
JOIN users u ON u.id = o.user_id
WHERE o.created_at >= '2026-04-01'
GROUP BY u.id, u.name\G
-- orders: type=range, key=idx_created, rows=1200
-- users:  type=eq_ref, key=PRIMARY, rows=1   ← 每次用主键精确查
```

时间从 3s → 50ms。

---

## 6. 面试高频考点

### 必考对比

| 维度 | count(*) | count(1) | count(col) |
|---|---|---|---|
| 含义 | 总行数（含 NULL） | 等价于 count(*) | col 不为 NULL 的行数 |
| 性能 | InnoDB 会选最小索引扫 | 同 count(*) | 需要判断 NULL，略慢 |
| 推荐 | 是（官方推荐） | 可以，和 * 一样 | 当业务确实要排除 NULL 时 |

| 维度 | UNION | UNION ALL |
|---|---|---|
| 去重 | 是（隐式 DISTINCT） | 否 |
| 临时表 | 需要（去重用） | 不需要 |
| 性能 | 慢 | 快 |
| 何时用 | 结果集可能重叠且要去重 | 结果集不重叠或不在乎重复 |

| 方式 | 核心动作 | 典型场景 | 版本边界 | 简化成本 |
|---|---|---|---|---|
| SNL | 外表一行 + 内表全扫 | 用于理解最朴素成本 | 基础模型，不用于判断版本 | `O(M×N)` |
| BNL | 外表一批 + 内表全扫 | 无可用 JOIN 索引的旧路径 | MySQL 8.0.20 起移除 | 比较仍近似 `O(M×N)`，但减少内表重复扫描 |
| INL | 外表一行 + 内表索引查找 | 有可用且成本合适的 JOIN 索引 | 所有版本 | `O(M×log N+R)` |
| Hash Join | build side 建哈希表 + probe side 扫描探测 | 常见于无可用 JOIN 索引 | 8.0.18 引入；8.0.20 完全替代 BNL | 等值 JOIN 平均接近 `O(M+N+R)` |

`EXPLAIN` 识别信号：BNL 是 `Using join buffer (Block Nested Loop)`，Hash Join 是 `Using join buffer (hash join)` 或树形计划中的 `Hash`，INL 通常在树形计划中显示 `Index lookup`，传统 `EXPLAIN` 的内表常见 `type=ref/eq_ref`。

### filesort 两种算法快速答法

> MySQL filesort 的 sort buffer 可能保存 `<sort_key,rowid>`，排序后按 rowid 回表；也可能保存 `<sort_key,additional_fields>`，排序后直接输出额外列。`max_length_for_sort_data` 只适用于旧版本，MySQL 8.0.20+ 已 deprecated 且无效，实际模式看 optimizer trace 的 `filesort_summary.sort_mode`。`Sort_merge_passes` 是 SESSION/GLOBAL 累计计数器；判断单条 SQL 要在同一连接中比较前后增量。

### "GROUP BY 8.0 有什么变化" 答法

> MySQL 8.0 取消了 GROUP BY 的隐式排序（5.7 里 GROUP BY col 会隐式 ORDER BY col）。8.0 起不加 ORDER BY 的 GROUP BY 结果顺序不确定，需要显式写 ORDER BY。另外，8.0.18 引入 Hash Join，8.0.20 移除 BNL 并在原本使用 BNL 的位置改用 Hash Join；GROUP BY 不走索引时触发临时表的行为不变，但 8.0 的 TempTable 引擎（替代 MEMORY）溢出到磁盘时用 mmap 而非 MyISAM，性能更好。

### 深翻页的经典问法

**Q：LIMIT 100000, 20 为什么慢？有几种解法？**

A：MySQL 的 LIMIT offset, count 要扫 offset+count 行才丢弃前 offset 行，每行都可能回表。offset=100000 = 100020 次回表。两种解法：

1. **延迟关联**：子查询先在覆盖索引上取 id，再精确回表 20 次（适合任意跳页）
2. **游标分页**：记录上一页最后一行的排序列值，下一页用 WHERE 替代 OFFSET（适合顺序翻页，彻底 O(1)）

### 易错点

- **Using filesort 不等于走了磁盘排序，`Sort_merge_passes` 也不代表上一条 SQL**：它默认是当前 SESSION 累计值；同一连接中的增量大于 0 才能说明观察窗口发生了磁盘归并，具体临时文件数看 optimizer trace 的 `number_of_tmp_files`
- **“小表驱动大表”只是 Nested Loop 的经验规则，不是所有 JOIN 的定律**：这里的小指过滤后进入 JOIN 的行数少；Hash Join 应该讨论较小的 build side 和被扫描的 probe side，而不是驱动表
- **count(*) 和 count(1) 性能一样**：面试中不要说"count(1) 比 count(*) 快"，这是误解。官方文档明确说两者等价
- **MySQL 8.0.20+ 的 Hash Join 也能执行非等值 JOIN，但不代表非等值条件变成 `O(M+N)`**：纯 `>`/`<` 条件可能显示 `Inner hash join (no condition)` 后再过滤，仍可能检查大量行组合

---

## 7. 一句话总结

调优 SQL 的入口是慢查日志（`long_query_time` + `pt-query-digest`）或 `performance_schema.events_statements_summary_by_digest`；
核心诊断工具是 `EXPLAIN` / `EXPLAIN ANALYZE`——把 `type=ALL`、`Using filesort`、`Using temporary`、`Using join buffer` 当作继续分析的信号，而不是直接判错；
常见根因是 ORDER BY / GROUP BY 的访问顺序不合适，或 JOIN 两边过滤行数、索引查找次数、Hash/full scan 成本失衡；
两个高频大坑是 `LIMIT 大 offset`（改延迟关联或游标分页）和 `COUNT(*) 大表`（改估值或维护计数表）；
写完 SQL 先 EXPLAIN，上线前过一遍 5 条 checklist。

---

## Scenarios

> 本机实测（MySQL 8.0.36），每个都跑过「预期 → 实机 → 落差」。

- [01 - filesort 触发与从 status 确认](scenarios/01-filesort-trigger-and-status.md) — `SHOW STATUS` 默认是当前 SESSION 累计值；用清零或前后差值把 `Sort_merge_passes` 归因到目标 SQL
- [02 - `Using temporary` 触发与索引消除](scenarios/02-using-temporary-trigger.md) — 同样 GROUP BY，无索引列 → 临时表+filesort，有索引列 → `Using index`
- [03 - 深翻页 `LIMIT 40000,20` 与延迟关联](scenarios/03-deep-pagination-deferred-join.md) — EXPLAIN 看延迟关联只回表 20 次（含「微基准为何骗人」的诚实记录）

## 相关章节

- [03-indexing/README.md](../03-indexing/README.md) — B+ 树、聚簇索引、覆盖索引、ICP、联合索引设计原则
