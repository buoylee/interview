# MySQL 整体架构

## 1. 核心问题

MySQL 不是一个单体程序，而是**两层插件式架构**。本章解决三件事：
**(a)** 一条 SQL 从客户端发出到返回结果，经过哪些组件、发生了什么；
**(b)** Server 层和存储引擎层各自做什么，为什么这样分；
**(c)** 影响日常开发和性能的隐性规则：长连接内存堆积、Query Cache 为什么消失、连接池配多大。

## 2. 直觉理解

把 MySQL 想象成一家餐厅：

- **Server 层 = 前厅（服务员 + 领班 + 调度）**：负责接待客人（连接器）、听懂点单（分析器）、计划出菜顺序（优化器）、跟后厨下单（执行器）。它不碰食材，只做翻译和决策。
- **存储引擎层 = 后厨（InnoDB / MyISAM）**：真正读写数据，管理磁盘文件、缓存、事务、锁。

前厅通过**标准化接口**调后厨——这就是「插件式架构」的核心价值：你可以换后厨（`ALTER TABLE t ENGINE=InnoDB`）而前厅不变。

一个具体数字帮助定位性能：一台普通 MySQL 8.0 实例，**默认 `max_connections=151`**（生产常调到 500-2000），每个连接在 Server 层的元数据约占 **800 KB-1 MB**（thread stack 默认 `thread_stack=1MB`）。2000 个连接光内存就要 2 GB 起步，这是「连接数打满」会让系统 OOM 的根源。

## 3. 原理深入

### 3.1 两层架构总览

```
┌─────────────────────────────────────────────────────┐
│                    Client                           │
│  (jdbc / go-sql-driver / libmysqlclient / CLI)      │
└──────────────────────┬──────────────────────────────┘
                       │ TCP / Unix Socket (默认 3306)
┌──────────────────────▼──────────────────────────────┐
│                  SERVER 层                          │
│                                                     │
│  ┌────────────┐  ┌──────────┐  ┌───────────────┐   │
│  │  连接器    │  │  分析器  │  │   优化器      │   │
│  │ Connector  │  │  Parser  │  │  Optimizer    │   │
│  └─────┬──────┘  └────┬─────┘  └──────┬────────┘   │
│        │              │               │             │
│  ┌─────▼──────────────▼───────────────▼────────┐   │
│  │              执行器 Executor                 │   │
│  └─────────────────────┬────────────────────────┘   │
│                        │ 存储引擎 API (handler API)  │
└────────────────────────┼────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│                存储引擎层                            │
│                                                     │
│  ┌──────────────┐  ┌──────────┐  ┌──────────────┐  │
│  │   InnoDB     │  │ MyISAM   │  │    Memory    │  │
│  │ (默认引擎)   │  │          │  │              │  │
│  └──────┬───────┘  └──────────┘  └──────────────┘  │
│         │                                           │
│  ┌──────▼──────────────────────────────────────┐   │
│  │  Buffer Pool │ redo log buffer │ ibdata files│   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

**Server 层**和**存储引擎层**之间只通过 handler API 通信。执行器不直接操作文件，它调的是 `ha_innobase::index_read()`、`ha_innobase::rnd_next()` 这类虚函数——这正是插件式的关键。

### 3.2 Server 层组件逐一讲

#### 连接器（Connector）

连接器完成三件事：建立 TCP 连接、做身份认证（用户名/密码/SSL）、加载该用户的权限信息。

**权限是在连接建立时读取一次的**，之后 `GRANT` 修改权限对已有连接不生效，必须重连（或 `FLUSH PRIVILEGES` 后再次连接）。这是线上权限变更时的常见陷阱。

连接状态查看：

```sql
SHOW PROCESSLIST;
```

典型输出：

```
+----+---------+-----------+------+---------+------+-------+------------------+
| Id | User    | Host      | db   | Command | Time | State | Info             |
+----+---------+-----------+------+---------+------+-------+------------------+
|  5 | app     | 10.0.0.1  | prod | Query   |    0 | init  | SELECT ...       |
|  6 | app     | 10.0.0.1  | prod | Sleep   |  300 |       | NULL             |
+----+---------+-----------+------+---------+------+-------+------------------+
```

`Command=Sleep` + `Time` 很大：这是空闲的长连接，占着连接槽不干活。超过 `wait_timeout`（默认 28800 秒 = 8 小时）会被服务器自动断开；但在这之前，每条长连接积累的临时对象（排序缓冲区、join buffer、SP 上下文）不会释放，长时间跑大查询的连接会让单连接占用超过 100 MB。

#### 分析器（Parser）

分析器做两步：
1. **词法分析**：把 SQL 字符串拆成 Token 流。`SELECT name FROM users WHERE age > 18` → `[SELECT, name, FROM, users, WHERE, age, >, 18]`
2. **语法分析**：把 Token 流按语法规则组装成**抽象语法树（AST）**：

```
SELECT
├── Columns: [name]
├── FROM: users
└── WHERE: age > 18
```

在这一步，MySQL 才会报 `You have an error in your SQL syntax`。注意：分析器只检查**语法**，不查列是否存在——列存不存在是优化器 / 执行器阶段才验证的。

语法错误 vs 语义错误的区别：`SELECT abc FROM users` 语法正确，但如果 `abc` 列不存在，错误会在执行器调引擎时才抛出 `Unknown column 'abc'`。

#### 优化器（Optimizer）

优化器拿到 AST，生成**执行计划（execution plan）**。它做的关键决策包括：
- 选哪个索引（基于统计信息 `information_schema.STATISTICS` + `mysql.innodb_index_stats`）
- 多表 JOIN 的连接顺序（多表时 optimizer 会尝试 `N!` 种顺序，但受 `optimizer_search_depth` 限制，默认 62）
- 是否用覆盖索引避免回表
- 是否用 MRR（Multi-Range Read）把随机 IO 变顺序

优化器**不执行 SQL，只输出 plan**。这一步的耗时通常在微秒级，但统计信息不准确时会选错 plan（这是 `ANALYZE TABLE` 的用武之地）。

用 `EXPLAIN` 看优化器的选择：

```sql
EXPLAIN FORMAT=JSON SELECT name FROM users WHERE age = 25;
```

典型输出片段：

```json
{
  "query_block": {
    "select_id": 1,
    "cost_info": { "query_cost": "1.00" },
    "table": {
      "table_name": "users",
      "access_type": "ref",
      "key": "idx_age",
      "key_length": "4",
      "rows_examined_per_scan": 1,
      "filtered": "100.00"
    }
  }
}
```

`access_type: ref` 表示优化器选了非唯一索引等值扫描，`key: idx_age` 是选中的索引，`rows_examined_per_scan: 1` 是估算扫行数（不是精确值）。

#### 执行器（Executor）

执行器按优化器给的 plan，循环调存储引擎 API 拿数据。伪代码：

```
plan = optimizer.plan()
engine = get_handler("InnoDB")
while row = engine.next_row(plan):
    if row matches WHERE:
        send_to_client(row)
```

慢查询日志里的 `rows_examined` 就是执行器调引擎 API 的次数——每次调用可能是一次 B+ 树查找或一次链表推进。`rows_examined` 远大于 `rows_sent` 说明过滤效率低，通常是索引不对。

执行器在调引擎前还会验证权限（再确认一次，第一次在连接器，这是第二次）。

### 3.3 存储引擎层 + 插件式架构

MySQL 的存储引擎是**插件式**的：引擎实现 handler API（约 80 个虚函数，如 `write_row`、`index_read`、`rnd_next`），注册进 MySQL，就可以被任意表使用。

**三大引擎对比：**

| 维度 | InnoDB | MyISAM | Memory |
|---|---|---|---|
| 事务 | 支持（ACID） | 不支持 | 不支持 |
| 外键 | 支持 | 不支持 | 不支持 |
| 行锁 | 支持 | 表锁 | 表锁 |
| 崩溃恢复 | 支持（redo log） | 不支持（需修复） | 数据随进程消失 |
| 全文索引 | 5.6+ 支持 | 支持 | 不支持 |
| 索引结构 | B+ 树（聚簇） | B+ 树（非聚簇） | Hash（主）/ B+ 树 |
| 适用场景 | 几乎所有 OLTP | 读多写少历史遗留 | 临时表 / 字典表 |

**MySQL 8.0 起 InnoDB 是唯一推荐的通用引擎**。MyISAM 在 8.0 里系统表也迁移到了 InnoDB，实际项目已没有选 MyISAM 的理由。

**切换引擎：**

```sql
ALTER TABLE t ENGINE = InnoDB;
```

这条语句会重建整张表（全量拷贝数据），线上大表要用 `pt-online-schema-change` 或 `gh-ost`。

**查看当前表引擎：**

```sql
SELECT TABLE_NAME, ENGINE
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'mydb';
```

### 3.4 一条 SELECT 的完整旅程

以 `SELECT name, email FROM users WHERE id = 42;` 为例，逐步走：

**Step 1 — 连接器**
- client 发 TCP 握手，连接器做认证，加载 `users` 权限到线程内存
- 如果连接池复用已有连接，跳过 TCP 握手，直接到 Step 2

**Step 2 — 查询缓存（8.0 已移除，5.7 还有）**
- 5.7 及以前：以整条 SQL 文本做 key，查内存 hash table。命中 → 直接返回，后续步骤全跳过。不命中 → 继续
- 8.0：这步不存在

**Step 3 — 分析器**
- 词法分析 → token 流
- 语法分析 → AST。验证 SQL 语法（这里不检查 `id` 列是否存在）

**Step 4 — 优化器**
- 读统计信息：`id` 列是 PRIMARY KEY → 唯一等值，选 `access_type=const`
- 生成 plan：走聚簇索引，直接定位到 page，预估 cost ≈ 1 row read
- `const` 是 `EXPLAIN` 里 access_type 里最快的一档（除主键/唯一索引等值外都拿不到）

**Step 5 — 执行器**
- 调 InnoDB handler API：`ha_innobase::index_read(PRIMARY KEY, id=42, HA_READ_KEY_EXACT)`
- InnoDB 返回第一行（或"无此行"），执行器把结果发给 client

**Step 6 — InnoDB 内部（引擎层）**
1. 用 `id=42` 在 B+ 树上做二分查找，从根页开始，最多 3 次 page 读（树高 ≤ 3）
2. **Buffer Pool 先查**：目标 page 在 Buffer Pool（默认 `innodb_buffer_pool_size=128MB`，生产常设为物理内存 50-75%）→ 内存命中，不需要磁盘 IO
3. **Buffer Pool 未命中**：从 `.ibd` 文件读 16KB 数据页到 Buffer Pool，LRU 淘汰冷页
4. 找到行，通过 MVCC（见 ch05）验证当前事务可见性，返回可见版本的数据

**完整时间线：**

```
client → connector(0.1ms) → parser(0.05ms) → optimizer(0.1ms)
       → executor → InnoDB
                    ├─ Buffer Pool HIT:  约 0.1ms（内存读 16KB）
                    └─ Buffer Pool MISS: 约 1-10ms（SSD 随机读）
       → client 收到结果
```

### 3.5 一条 UPDATE 的完整旅程

以 `UPDATE users SET email='new@example.com' WHERE id = 42;` 为例。前三步（连接器→分析器→优化器）和 SELECT 相同，重点是 Step 5+6。

**Step 5 — 执行器**
- 调 InnoDB：先读出 `id=42` 的行（流程同 SELECT Step 6），获取**行锁**（InnoDB 行级锁，见 ch06）
- 修改内存中的行值

**Step 6 — InnoDB 写路径（重点）**

```
                   ┌─────────────────────────────┐
                   │  Buffer Pool（内存中的数据页）│
                   │  修改页标记为 dirty page      │
                   └──────────────┬──────────────┘
                                  │
          ┌───────────────────────▼──────────────────────┐
          │                InnoDB 写日志                  │
          │                                              │
          │  1. 写 redo log buffer（内存，顺序写，约 16MB）│
          │     记录：「page X, offset Y, 旧值→新值」      │
          │     格式：物理日志，用于崩溃恢复               │
          │                                              │
          │  2. 写 binlog cache（线程私有内存）            │
          │     记录：完整 SQL 或行变更（逻辑日志）        │
          │     用于主从复制 / 时间点恢复                  │
          └──────────────────────────────────────────────┘
                                  │
                         COMMIT 时：
          ┌───────────────────────▼──────────────────────┐
          │             两阶段提交（2PC）                  │
          │                                              │
          │  Phase 1 prepare: redo log 刷盘，标记 prepare  │
          │  Phase 2 commit:  binlog 刷盘，                │
          │                   redo log 标记 commit         │
          └──────────────────────────────────────────────┘
```

**关键数字：**
- `redo log buffer` 默认 16 MB（`innodb_log_buffer_size`）。大事务建议调大，避免提交前 buffer 满触发提前刷盘
- `innodb_flush_log_at_trx_commit=1`（默认）：每次 commit 都 `fsync` redo log → 最安全，每次 commit 约增加 1-2ms（SSD）
- `innodb_flush_log_at_trx_commit=2`：commit 写 OS page cache，每秒 `fsync` → 崩溃最多丢 1 秒数据
- `sync_binlog=1`（默认）：每次 commit 都 `fsync` binlog → 安全但有写放大
- **两阶段提交（2PC）的必要性**：如果先写 redo 再写 binlog，崩溃在中间会导致 binlog 缺这条记录，主从不一致。2PC 保证两者要么都提交要么都回滚。2PC 详细机制见 ch07。

**UPDATE 和 SELECT 的核心差别：**
- UPDATE 要写 redo log + binlog，一次提交 = 至少 2 次 `fsync`（默认配置）
- UPDATE 期间持行锁，其他事务等待（锁等待见 ch06）
- dirty page 不立即写磁盘，由 InnoDB 后台线程 checkpoint 异步刷回（Write-Ahead Logging 原则）

### 3.6 Query Cache 为什么被 8.0 移除了

Query Cache 的设计思路：以 SQL 文本为 key，缓存整个结果集到内存。

**失效粒度太粗**：任何对缓存涉及的**表**的写操作（INSERT / UPDATE / DELETE），都会让该表相关的所有缓存条目全部失效。高并发写场景下，缓存命中率趋近于 0，但每次写都要维护缓存锁（全局互斥锁 `query_cache_mutex`）。

**具体代价：**
- 每次 SQL 到来，要先对 SQL 文本做 hash（大小写、空格敏感），查 hash table，**无论缓存是否命中都要加锁**
- 高并发时，`query_cache_mutex` 成为全局串行点，吞吐量随并发线性下降

**能命中的场景极窄：**
- SQL 文本必须字节完全一致（`SELECT * from t` vs `select * from t` 是两条不同的 key）
- 不能含 `NOW()`、`RAND()`、`USER()` 等非确定函数
- 不能用在事务中（怕脏读）

**实际效果：** MySQL 官方基准测试显示，启用 Query Cache 在写多读少场景下，QPS 反而下降 20-30%。8.0 直接移除，不留 `query_cache_type` 开关。

**替代方案：** 应用层缓存（Redis / Memcached）在正确的粒度（业务对象而不是 SQL 文本）上做缓存，命中率可控、失效粒度可控。

### 3.7 长连接的内存问题

MySQL 的连接模型是 **one thread per connection**：每个连接对应一个服务线程，持有一套私有内存（排序缓冲区 `sort_buffer_size`、join 缓冲区 `join_buffer_size`、读缓冲区 `read_buffer_size` 等）。

**内存堆积机制：**
- 每次执行复杂查询，Server 层会按需分配临时内存（排序 buffer、临时表）
- 这些内存**在查询结束时释放到线程的内存池，而不是归还给 OS**（MySQL 5.7 及以前行为，8.0 有改善但依然存在）
- 长时间运行的长连接跑了大量大查询后，单连接内存占用可超过 100-300 MB

**示例：** 一个连接池 100 个长连接，每个连接因历史大查询占 50 MB，总计 5 GB，可能超过 `innodb_buffer_pool_size`，导致 Buffer Pool 被 OS 换出，IO 急剧升高。

**解决方案：**

**方案 A（推荐）：`mysql_reset_connection`**

```sql
-- 应用层在执行完大查询后调用（通过 MySQL C API / Connector/J）
-- 效果：释放线程临时内存，复位连接状态（不需要重新认证）
-- MySQL 5.7.3+ 支持
```

在 JDBC 里：`((com.mysql.cj.jdbc.JdbcConnection) conn).resetServerState()`
在 Go `database/sql` 里：`db.SetConnMaxLifetime(10 * time.Minute)` 触发定期重建连接

**方案 B：定期断连 + 重连**

```
连接池配置：
- maxLifetime = 10-30 分钟（超过后丢弃连接，重建）
- 比 mysql_reset_connection 稍重（需要重新握手认证）
- 但更彻底：连接本身的任何状态都清空
```

**方案 C：短连接（不推荐用于高并发）**

每次请求新建 + 关闭连接。TCP 三次握手 + MySQL 认证 ≈ 1-3ms，QPS 1000+ 时连接建立本身成为瓶颈。

**相关参数：**

```sql
SHOW VARIABLES LIKE 'wait_timeout';       -- 默认 28800s（8 小时），空闲连接超时
SHOW VARIABLES LIKE 'interactive_timeout'; -- 交互式连接超时
SHOW VARIABLES LIKE 'max_connections';    -- 默认 151，生产常调 500-2000
SHOW VARIABLES LIKE 'thread_stack';       -- 默认 1MB，每个连接固定占用
```

## 4. 日常开发应用

**连接池配置原则**

连接池大小 ≠ 越大越好。经验公式：`pool_size = CPU核数 × 2 + 磁盘数`（来自 HikariCP 文档，适合 OLTP）。原因：MySQL 一个查询在 InnoDB IO 等待时，CPU 是空闲的；但连接过多会导致 OS 线程切换开销超过收益。

```
# 推荐 HikariCP 配置示例（Java）
maximumPoolSize = 20        # 对于 4 核 + SSD 实例足够
minimumIdle = 5
connectionTimeout = 3000    # 3s 拿不到连接就报错（别设太大，掩盖问题）
maxLifetime = 1800000       # 30 分钟强制回收（解决长连接内存堆积）
keepaliveTime = 60000       # 每分钟发 SELECT 1 防止被防火墙 RST
```

**不要 `SELECT *`**

`SELECT *` 的代价不只是传输多余字段，而是：
1. 分析器和优化器要展开 `*`，查 `information_schema`，多一步元数据 IO
2. 覆盖索引失效：`SELECT id, name FROM t WHERE name='x'`，如果有 `(name, id)` 索引，`SELECT name, id` 可以走覆盖索引不回表；`SELECT *` 必须回表
3. 字段变更时 ORM 映射容易出错

**EXISTS vs IN**

- `IN` 子查询：优化器在 5.6+ 会自动转成 semi-join，两者 plan 通常等价，不需要手工改写
- 例外：外表小、内表大 → `EXISTS` 更快（用外表每行去探测内表索引，不用物化子查询）
- 外表大、内表小 → `IN` 更快（物化内表结果集，外表做 hash join）
- 实际项目：先 `EXPLAIN`，看 `select_type` 是否出现 `SUBQUERY` → 如果是，优化器没自动转，考虑改写为 JOIN

**写完 SQL 先 EXPLAIN**

```sql
-- 快速检查单条 SQL
EXPLAIN SELECT name FROM users WHERE age = 25;

-- 看实际执行（8.0+，会真正执行，ANALYZE 关键字）
EXPLAIN ANALYZE SELECT name FROM users WHERE age = 25;
```

`EXPLAIN ANALYZE` 会返回每步实际行数和耗时（不是估算），是定位慢查询最直接的工具。

## 5. 调优实战

### Case A：连接数被打满怎么排查

症状：新请求报 `Too many connections`，`max_connections` 是 1000，`SHOW PROCESSLIST` 有 1000 条。

**排查步骤：**

```sql
-- Step 1: 看是哪个 host / user 占的连接
SELECT user, host, COUNT(*) AS cnt
FROM information_schema.PROCESSLIST
GROUP BY user, host
ORDER BY cnt DESC;

-- Step 2: 看各 State 分布（是在等锁、等 IO、还是正常运行）
SELECT state, COUNT(*) AS cnt
FROM information_schema.PROCESSLIST
GROUP BY state
ORDER BY cnt DESC;

-- Step 3: 看空闲连接多少（Command = Sleep）
SELECT COUNT(*) FROM information_schema.PROCESSLIST WHERE command = 'Sleep';

-- Step 4: 查当前 max_connections 和已用
SHOW VARIABLES LIKE 'max_connections';
SHOW GLOBAL STATUS LIKE 'Threads_connected';
SHOW GLOBAL STATUS LIKE 'Max_used_connections';  -- 历史峰值，用于估算合理上限
```

**常见根因：**
- 连接池 `maximumPoolSize` 配过大 × N 个服务实例 > `max_connections`
- 应用代码连接泄漏（try-with-resources 没关连接）
- 慢查询导致连接长时间 hang → 反压积累

**临时止血：** `KILL CONNECTION <id>` 杀掉空闲长连接，或调大 `max_connections`（注意内存代价：+1000 连接约 +1GB 内存）。

### Case B：查询慢，先判断是哪一层慢

慢查询日志（`slow_query_log=ON`, `long_query_time=1`）的 `Query_time` 包含了从执行器调引擎到返回的完整时间，**但没区分是 Server 层慢还是引擎层慢**。

```sql
-- 打开 performance_schema（8.0 默认开）
-- 找最近的慢 SQL 事件
SELECT
    DIGEST_TEXT,
    COUNT_STAR,
    AVG_TIMER_WAIT / 1e12 AS avg_sec,
    SUM_LOCK_TIME / 1e12  AS lock_sec,
    SUM_ROWS_EXAMINED,
    SUM_ROWS_SENT
FROM performance_schema.events_statements_summary_by_digest
ORDER BY AVG_TIMER_WAIT DESC
LIMIT 10;
```

判断依据：
- `SUM_LOCK_TIME` 占 `AVG_TIMER_WAIT` 比例 > 50%：锁等待是主因，看 ch06 锁分析
- `SUM_ROWS_EXAMINED / SUM_ROWS_SENT` 比值 > 100：索引效率差，看 ch03 索引
- 两者都小但依然慢：可能是网络、client 处理慢，或 `tmp_table_size` 不够导致内存临时表溢出到磁盘

### Case C：用 performance_schema 定位瓶颈在哪一层

```sql
-- 查 InnoDB 引擎层等待事件（最近 top 10）
SELECT
    EVENT_NAME,
    COUNT_STAR,
    SUM_TIMER_WAIT / 1e12 AS total_sec
FROM performance_schema.events_waits_summary_global_by_event_name
WHERE EVENT_NAME LIKE 'wait/io/file/innodb/%'
   OR EVENT_NAME LIKE 'wait/synch/mutex/innodb/%'
ORDER BY SUM_TIMER_WAIT DESC
LIMIT 10;
```

如果 `wait/io/file/innodb/innodb_data_file` 高：Buffer Pool 不够，大量磁盘读（调大 `innodb_buffer_pool_size`）。
如果 `wait/synch/mutex/innodb/buf_pool_mutex` 高：Buffer Pool 锁竞争，考虑增加 `innodb_buffer_pool_instances`（建议每个 instance 1GB）。

## 6. 面试高频考点

### 必考对比

| 维度 | Server 层 | 存储引擎层 |
|---|---|---|
| 包含组件 | 连接器、分析器、优化器、执行器 | InnoDB、MyISAM、Memory 等 |
| 是否感知存储格式 | 否（通过 handler API 抽象） | 是 |
| 事务实现 | 无 | InnoDB 实现（redo log / undo log） |
| binlog | Server 层写（与引擎无关） | redo log 是 InnoDB 私有 |
| 锁 | MDL（元数据锁）在 Server 层 | 行锁 / 表锁在引擎层 |

| 维度 | InnoDB | MyISAM |
|---|---|---|
| 事务 | 支持 | 不支持 |
| 锁粒度 | 行锁 | 表锁 |
| 崩溃恢复 | redo log 保证 | 需 myisamchk 修复 |
| 索引与数据 | 聚簇（数据在主键 B+ 树叶子） | 非聚簇（索引文件 + 数据文件分离） |
| COUNT(*) | 需扫描（无统计缓存） | O(1)（维护了行数） |

### 易错点

- **binlog 是 Server 层的，redo log 是 InnoDB 的**。换成 MyISAM 就没有 redo log，但 binlog 还在。两者功能不重叠：redo log 用于崩溃恢复，binlog 用于主从复制和 PITR
- **Query Cache 在 8.0 已彻底移除**，不要在 8.0 的优化题里提「开启 query cache」
- **权限在连接建立时加载，GRANT 后要重连才生效**（已有连接不受影响）
- **`EXPLAIN` 里的 `rows` 是优化器估算值**，不是真实扫描行数；要看真实值用 `EXPLAIN ANALYZE`

### "一条 SQL 完整旅程" — 90 秒答法

> 以 SELECT 为例：
>
> **（连接器）** 客户端发 TCP 连接，MySQL 连接器验证用户名密码，加载该用户权限，建立会话。
>
> **（分析器）** SQL 文本做词法分析拆 token，语法分析生成 AST，这一步只检查语法，不查列是否存在。
>
> **（优化器）** 读表统计信息，决定用哪个索引、JOIN 顺序，输出执行计划（cost-based）。
>
> **（执行器）** 循环调 InnoDB handler API，每次拿一行或一批行。
>
> **（InnoDB）** 先查 Buffer Pool，命中则内存返回；未命中则从 .ibd 文件读 16KB 页到 Buffer Pool 再返回。结果经 MVCC 版本可见性过滤后，逐行发回执行器，最终到 client。
>
> UPDATE 在执行器调引擎修改行的同时，InnoDB 写 redo log buffer，Server 层写 binlog cache，commit 时两阶段提交保证两者原子性。

## 7. 一句话总结

MySQL 是 **Server 层（连接、解析、优化、执行） + 存储引擎层（InnoDB 负责数据读写、事务、锁、缓存）** 的两层插件式架构。一条 SQL 在 Server 层完成理解和决策，在引擎层完成实际的 IO 和事务保障。日常优化的核心抓手是：连接池设合理上限 + 长连接定期回收（`maxLifetime`）+ 写 SQL 先 EXPLAIN + UPDATE 路径理解 redo/binlog 两阶段提交（详见 ch07）。Query Cache 已死，缓存请上应用层。
