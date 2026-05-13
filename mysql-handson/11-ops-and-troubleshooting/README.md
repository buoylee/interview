# 运维与排障

## 1. 核心问题

线上 MySQL 出问题时，工程师最怕的不是「不知道怎么修」，而是「不知道从哪里看、看什么」。本章解决三件事：
**(a)** 大表加列、改索引——怎样做到不锁表、不影响业务；
**(b)** 备份怎么做才能在 RTO/RPO 要求内恢复；
**(c)** CPU 100%、连接数耗尽、主从断裂——每种故障的排查 SOP（命令 → 根因 → 解决）。

---

## 2. 直觉理解

**Online DDL** 想象成：你要给一本已经在运营的图书馆加新书架（加列）。三种做法：
- 只在纸质目录上加一行标注"以后的书默认放 3 楼"（INSTANT：改元数据，秒级完成）
- 把书搬到临时区域、把书架从内部扩建好，再搬回来，期间读者还能进（INPLACE：引擎内操作，读不阻塞，写短暂阻塞）
- 关门重建整栋楼，门口挂牌"施工中"（COPY：建临时表全量拷贝，长时间锁表）

**备份 + PITR** 想象成银行的录像带机制：每周全量备份是"周存档"，binlog 是"全天实时录像"。恢复到任意时间点 = 找到最近一盘存档 + 快进录像到目标时间。

**参数调优**：MySQL 出厂时很多参数按「最小内存占用」设的（`innodb_buffer_pool_size=128M` 根本不够用）。调优的本质是「告诉 MySQL 它实际拥有多少资源、应该在哪里多花」。

**故障排查**：每一类故障都有且仅有几个「元凶变量」（CPU 100% 几乎必然是慢查询 / 全扫；连接耗尽几乎必然是连接泄漏或慢查积压），命令清单的作用是精准定位是哪一个。

---

## 3. 原理深入

### 3.1 Online DDL 三算法（INSTANT / INPLACE / COPY）+ 8.0 INSTANT 增强

MySQL 的 `ALTER TABLE` 在内部有三种执行算法，优先级按你指定的降序尝试。

**INSTANT（8.0.12+）**

原理：只修改 InnoDB 数据字典（行格式里的 metadata），不触及任何实际数据页。秒级完成，不管表有多大。

限制（8.0.29 之前）：只支持在表的**最后**追加列，且不能与其他类型的变更混用。
8.0.29+ 增强：
- 支持加列到任意位置（包括中间列）
- 支持删列（`DROP COLUMN`）
- 支持改列默认值（`ALTER COLUMN ... SET DEFAULT`）
- 支持改 ENUM / SET 在列表末尾追加成员

显式指定方式：
```sql
ALTER TABLE orders ADD COLUMN remark VARCHAR(500) DEFAULT NULL,
  ALGORITHM=INSTANT;
```
如果 INSTANT 不支持当前操作，会立即报错而不是降级，这是防止你误以为操作秒级完成实际却走了慢路径的保护。

**INPLACE**

原理：在 InnoDB 存储引擎层完成操作，读操作（SELECT）在整个过程中不阻塞，写操作（INSERT/UPDATE/DELETE）只在 prepare 阶段和最终 commit 阶段各有一次短暂的 MDL（Metadata Lock）写锁，通常毫秒级。变更期间的 DML 写入到一个「在线 DDL 日志缓冲区」中，最后一并回放。

典型操作：
- 加二级索引（在后台 sorted build，比旧版快得多）
- 修改列的 NOT NULL 约束（同时扫描全表验证）
- ROW_FORMAT 转换

关键参数：`innodb_sort_buffer_size`（控制 DDL 期间排序缓冲，默认 1M，大表可调到 64M 加速）和 `innodb_online_alter_log_max_size`（DDL 日志缓冲上限，默认 128M，DML 并发量大时要调大，否则报 `DB_ONLINE_LOG_TOO_BIG`）。

```sql
ALTER TABLE orders ADD INDEX idx_user_created(user_id, created_at),
  ALGORITHM=INPLACE, LOCK=NONE;
```
`LOCK=NONE` 表示拒绝降级到有锁模式；`LOCK=SHARED` 允许读不允许写；`LOCK=EXCLUSIVE` 等同 COPY。

**COPY**

原理：建一张与原表结构相同但加了新定义的临时表，把所有数据全量拷贝过去，然后 rename。整个过程持有 MDL 写锁，所有并发 DML 都阻塞，持续时间与表大小线性相关。

```sql
ALTER TABLE orders MODIFY COLUMN amount DECIMAL(14,4),
  ALGORITHM=COPY;   -- 迫不得已时显式指定
```

**三算法对比**

| 维度 | INSTANT | INPLACE | COPY |
|---|---|---|---|
| 读阻塞 | 无（微秒级 MDL） | 无 | 全程阻塞 |
| 写阻塞 | 无（微秒级 MDL） | 短暂（prepare + commit 各一次） | 全程阻塞 |
| 额外磁盘 | 无 | 约等于索引大小 | 全表数据的副本 |
| 适用操作举例 | 加列（8.0+）、改默认值、加/删 ENUM 末尾 | 加二级索引、改 NOT NULL | 改列数据类型、改字符集 |
| 8.0 默认选哪个 | 最优先尝试（若支持） | INSTANT 不支持时尝试 | 最后兜底 |

**实际建议**：上线前用 `ALTER TABLE ... ALGORITHM=INSTANT, LOCK=NONE` 或 `ALGORITHM=INPLACE, LOCK=NONE` 跑一次 `dry-run`（MySQL 会报错告诉你是否支持），而不是直接上生产。几百 GB 的表必须配合 pt-osc 或 gh-ost。

---

### 3.2 pt-online-schema-change 原理 + gh-ost 对比

**pt-online-schema-change（pt-osc）原理**

pt-osc 是 Percona Toolkit 的一部分，底层思路是「旁路复制 + 触发器同步 + 原子 rename」：

1. **建影子表**：`CREATE TABLE _orders_new LIKE orders`，然后在影子表上执行 DDL 变更。
2. **建三个触发器**：在原表 `orders` 上装 `AFTER INSERT / AFTER UPDATE / AFTER DELETE` 触发器，所有新 DML 同步写入影子表，保证变更期间增量数据不丢。
3. **Chunked 拷贝旧数据**：按主键范围分批（默认 `--chunk-size=1000`），把旧表数据 `INSERT IGNORE INTO _orders_new ... SELECT ...`，每批之间有 `sleep`（`--sleep=0.05`s 可调）防止对主库造成太大负载。
4. **Rename 切换**：旧数据拷贝完毕后，`RENAME TABLE orders TO _orders_old, _orders_new TO orders`，这个操作是原子的，业务几乎无感知（几毫秒）。
5. **清理**：删除旧表 `_orders_old`、删除触发器。

使用约束：
- 必须有主键或唯一索引（用于分块）
- 触发器有写入开销，高写入场景下影子表落后可能导致 rename 延迟
- 不支持在没有 `ON DELETE CASCADE` 的外键关系上操作（会先 drop FK）
- 磁盘需要约 2x 原表空间

典型调用：
```bash
pt-online-schema-change \
  --host=127.0.0.1 --user=root --password=secret \
  --alter "ADD COLUMN remark VARCHAR(500) DEFAULT NULL" \
  --execute \
  D=mydb,t=orders
```
加 `--dry-run` 先验证，加 `--print` 打印 SQL，加 `--chunk-size=500 --sleep=0.1` 降低主库压力。

**gh-ost（GitHub's Ghost）原理**

gh-ost 由 GitHub 于 2016 年开源，核心差别：**不用触发器，改从 binlog 消费增量**。

流程：
1. 建影子表 `_orders_gho`，在影子表上执行 DDL。
2. 伪装成 MySQL replica，直接连到主库（或从库）订阅 binlog stream。
3. Chunked 拷贝历史数据，同时从 binlog 解析出对原表的所有 DML，在影子表上回放。
4. 当历史数据拷贝追上 binlog 位点，执行原子 rename 切换。

对比 pt-osc 的优缺点：

| 维度 | pt-osc | gh-ost |
|---|---|---|
| 增量同步方式 | 触发器（同步写） | binlog 消费（异步） |
| 触发器开销 | 有，影响原表写入性能约 5-10% | 无 |
| 对主库并发写入的影响 | 较大（触发器在事务内） | 较小（binlog 消费独立） |
| 是否需要 SUPER 权限 | 建触发器需要 | 需要 REPLICATION SLAVE 权限 |
| 是否支持外键 | 部分支持 | 不推荐（需要额外配置） |
| 支持暂停 / 限速 | 需要手动 kill，不优雅 | 支持运行时动态调速（HTTP API / flag 文件） |
| 复杂度 | 较低，工具成熟 | 略高，binlog position 管理 |

实际选择原则：写入 QPS > 5000 或 binlog 并发大的场景优先 gh-ost；pt-osc 在普通 OLTP 场景够用，部署更简单。

```bash
gh-ost \
  --host=127.0.0.1 --port=3306 \
  --user=root --password=secret \
  --database=mydb --table=orders \
  --alter "ADD COLUMN remark VARCHAR(500) DEFAULT NULL" \
  --allow-on-master \
  --execute
```

---

### 3.3 备份方案：逻辑 vs 物理，全量 vs 增量

**逻辑备份**

工具：`mysqldump`（单线程）/ `mysqlpump`（多线程，8.0 推荐）/ `mydumper`（第三方，并行度更高）

原理：把数据转化为可执行的 SQL 语句（`CREATE TABLE` + `INSERT`）输出文件，恢复时重新执行 SQL。

特点：
- 备份文件是纯文本，可以跨 MySQL 版本、甚至跨数据库迁移
- 可以细粒度选择库 / 表
- 备份和恢复速度慢：备份需要全表扫描，恢复需要逐行 INSERT（大表恢复可能要数小时）
- 备份期间对主库有读 IO 压力

典型用法：
```bash
# 全量备份，单一事务读（InnoDB 快照读，不锁表）
mysqldump --single-transaction --set-gtid-purged=OFF \
  -h 127.0.0.1 -u root -p mydb > mydb_$(date +%F).sql

# 恢复
mysql -h 127.0.0.1 -u root -p mydb < mydb_2026-05-13.sql
```
`--single-transaction` 是关键：它在 RR 隔离级别下开事务，配合 InnoDB MVCC 保证一致性快照，不锁表（MyISAM 不适用）。

**物理备份（xtrabackup）**

工具：Percona XtraBackup（开源，支持 MySQL 5.6-8.0）/ MySQL Enterprise Backup（官方商业版）

原理：直接拷贝 InnoDB 数据文件（`.ibd`）+ redo log，在拷贝过程中持续追踪 LSN（Log Sequence Number），拷贝期间发生的变更通过 redo log 补齐，最终得到一个一致性的物理快照。

特点：
- 备份速度快（文件级拷贝，比逻辑备份快 5-10x）
- 恢复速度快（直接覆盖数据文件，不需要重新执行 SQL）
- 支持增量备份（基于 LSN）
- 备份文件只能恢复到相同或更高版本的 MySQL
- 需要在 `prepare` 阶段用 redo log 做前滚（apply-log）才能得到一致状态

全量备份流程：
```bash
# 1. 备份
xtrabackup --backup \
  --host=127.0.0.1 --user=root --password=secret \
  --target-dir=/backup/full-2026-05-13

# 2. Prepare（apply redo log，使备份一致）
xtrabackup --prepare --target-dir=/backup/full-2026-05-13

# 3. 恢复（停 mysqld 后）
xtrabackup --copy-back --target-dir=/backup/full-2026-05-13
chown -R mysql:mysql /var/lib/mysql
systemctl start mysqld
```

增量备份流程：
```bash
# 第一次全量
xtrabackup --backup --target-dir=/backup/base

# 增量备份（基于 base 的 LSN）
xtrabackup --backup \
  --target-dir=/backup/inc-day2 \
  --incremental-basedir=/backup/base

# Prepare 时按顺序合并增量
xtrabackup --prepare --apply-log-only --target-dir=/backup/base
xtrabackup --prepare --apply-log-only \
  --target-dir=/backup/base \
  --incremental-dir=/backup/inc-day2
xtrabackup --prepare --target-dir=/backup/base   # 最后一次不加 --apply-log-only
```

**三种粒度对比**

| 粒度 | 含义 | 典型工具 | 恢复时间 |
|---|---|---|---|
| 全量（Full） | 完整备份所有数据 | xtrabackup / mysqldump | 最长 |
| 增量（Incremental） | 自上次备份（全量或增量）以来变化的 pages | xtrabackup（基于 LSN） | 中等（需合并） |
| 差异（Differential） | 自上次**全量**备份以来所有变化 | xtrabackup（每次都基于 base） | 较短（只需合并一次） |

实际备份策略：周日全量 + 周一到周六每天增量 + 实时 binlog（PITR 保底）。

---

### 3.4 PITR（binlog + 全备结合）

PITR = Point-In-Time Recovery，恢复到任意时间点。原理：

```
[全备（T0）] ──── binlog ────→ [目标时间点 T1]
```

全备给你一个一致性起点，binlog 记录了从 T0 到现在所有的 DML/DDL 事件，重放 binlog 就能还原任意时刻的状态。

**前提条件**

- `binlog_format=ROW`（行格式，包含完整前后镜像，重放准确）或 `MIXED`
- `expire_logs_days` 或 `binlog_expire_logs_seconds` 要足够长（建议 7 天以上）
- 每次全备时记录备份结束时的 binlog position（xtrabackup 会自动写到 `xtrabackup_binlog_info`）

**PITR 恢复步骤**

```bash
# 1. 恢复全备到一个临时实例（不要直接在生产操作）
xtrabackup --copy-back --target-dir=/backup/full-2026-05-13

# 2. 查看全备的 binlog position
cat /backup/full-2026-05-13/xtrabackup_binlog_info
# 输出示例：mysql-bin.000042  15834729   (GTID 模式下还有 gtid_executed)

# 3. 从 binlog 提取目标时间段之前的事件
mysqlbinlog \
  --start-position=15834729 \
  --stop-datetime="2026-05-13 14:32:00" \
  /var/log/mysql/mysql-bin.000042 \
  /var/log/mysql/mysql-bin.000043 \
  > /tmp/recover.sql

# 4. 在恢复实例上重放
mysql -u root -p < /tmp/recover.sql
```

**GTID 模式下的 PITR**

如果开启了 GTID（`gtid_mode=ON`），全备包含 `gtid_executed`，重放 binlog 时 MySQL 会自动跳过已执行的事务，更安全。恢复时加 `--skip-gtids` 参数给 `mysqlbinlog`（否则重放时会因 GTID 冲突报错）：

```bash
mysqlbinlog --skip-gtids \
  --start-position=... --stop-datetime="..." \
  mysql-bin.000042 > /tmp/recover.sql
```

---

### 3.5 关键参数调优清单

以下参数针对 8GB RAM + 普通 OLTP 生产实例给出起点值，实际要根据工作负载监控后调整。

| 参数 | 默认值 | 推荐起点 | 调整原则 |
|---|---|---|---|
| `innodb_buffer_pool_size` | 128M | RAM × 0.5~0.75（如 4-6G） | 最重要的参数。InnoDB 热数据/索引都缓存在这里，越大越好，但要给 OS 和连接栈留 1-2GB |
| `innodb_buffer_pool_instances` | 1（<1G时）/ 8 | CPU 核数，最大 64 | buffer pool 分成多个实例减少竞争，建议与 buffer pool 大小联动（≥1G 时开多实例） |
| `innodb_log_file_size` | 48M | 1-2G | redo log 太小会导致频繁 checkpoint（写入停顿），太大崩溃恢复慢。大写入场景调大 |
| `innodb_flush_log_at_trx_commit` | 1 | 保持 1（金融级）/ 2（允许 1s 丢失） | 1=每次 commit 刷盘（ACID 完整），2=每秒刷盘（性能提升 2-3x，崩溃最多丢 1s 数据），0=不保证 |
| `sync_binlog` | 1（8.0）/ 0（5.7） | 1 | 1=每次 commit sync binlog，主从一致性最强；0=OS 决定，性能好但崩溃可能丢 binlog |
| `max_connections` | 151 | 500-1000 | 每条连接占 ~1MB 内存（线程栈 + 缓存），不是越大越好。连接池收敛后实际需求通常 < 300 |
| `thread_cache_size` | auto（= 8+max_connections/100，最大 100） | 100-200 | 线程复用池，减少频繁 connect/disconnect 的线程创建开销 |
| `table_open_cache` | 4000 | 4000-8000 | 每个打开的表文件描述符的缓存，高并发多表场景要调大，注意对应 `open_files_limit` |
| `innodb_read_io_threads` / `innodb_write_io_threads` | 4 / 4 | 8 / 8（SSD 可更高） | 控制 InnoDB 后台 IO 线程数，SSD 场景可调到 16 |
| `innodb_io_capacity` | 200 | SSD: 2000-5000，HDD: 200-400 | 告知 InnoDB 存储 IO 吞吐能力，影响 flush 速度和 insert buffer merge 速度 |
| `tmp_table_size` / `max_heap_table_size` | 16M / 16M | 64-128M | 内存临时表上限（GROUP BY / DISTINCT 等），超出后转磁盘临时表（MyISAM/TempTable 引擎），慢很多 |
| `join_buffer_size` | 256K | 256K~1M（不要太大） | Block NL Join 时每个 join 分配的缓冲，过大导致内存碎片，优化根本还是加索引 |
| `innodb_flush_method` | `fsync` | `O_DIRECT`（Linux + SSD） | `O_DIRECT` 绕过 OS page cache 直接 IO，避免 double buffer（InnoDB buffer pool 已缓存，OS 再缓存一遍是浪费） |
| `innodb_deadlock_detect` | ON | ON | 8.0 提供，关闭可在极高并发下提升性能，但需要应用层处理死锁重试，通常保持 ON |
| `slow_query_log` | OFF | ON | 生产必开，`long_query_time=1`（秒），`log_queries_not_using_indexes=ON` 辅助 |
| `performance_schema` | ON | ON | 性能开销约 5%，但监控收益远大于此，不要关 |

**修改参数的注意事项**：
- `innodb_buffer_pool_size` 在 8.0 支持在线动态修改（`SET GLOBAL`），无需重启；但实际内存分配是渐进式调整的。
- `innodb_log_file_size` 5.7 需要停库后删旧 redo log 文件再启动；8.0.30+ 支持在线动态调整（`innodb_redo_log_capacity` 替代了这一参数）。
- 改完参数一定同步写到 `my.cnf`，否则重启后失效。

---

### 3.6 性能监控关键指标

**通过 SHOW STATUS 采集**

```sql
-- 每 N 秒采一次差值，除以 N 得到每秒值
SHOW GLOBAL STATUS LIKE 'Queries';
SHOW GLOBAL STATUS LIKE 'Com_commit';
SHOW GLOBAL STATUS LIKE 'Com_rollback';
SHOW GLOBAL STATUS LIKE 'Threads_%';
SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_%';
SHOW GLOBAL STATUS LIKE 'Slow_queries';
```

| 指标 | 含义 | 告警阈值参考 |
|---|---|---|
| `Queries` / s（QPS） | 每秒总查询数（含 SELECT/DML） | 业务基线的 2x |
| `Com_commit` / s（TPS） | 每秒提交事务数 | 业务基线的 2x |
| `Threads_running` | 当前活跃执行线程数（不含等待） | > 核心数 * 2 时告警 |
| `Threads_connected` | 当前连接数 | > `max_connections` * 0.8 |
| `Innodb_buffer_pool_read_requests` vs `Innodb_buffer_pool_reads` | 命中率 = 1 - reads/read_requests | 命中率 < 99% 要关注 |
| `Innodb_row_lock_waits` | 行锁等待次数 | 持续增长说明有锁竞争 |
| `Innodb_row_lock_time_avg` | 平均行锁等待时间（ms） | > 100ms 要排查锁 |
| `Slow_queries` | 慢查询累计数 | 增速突变时告警 |
| `Created_tmp_disk_tables` | 落盘的临时表数 | > 0 就要关注，持续增长要查 GROUP BY / DISTINCT |
| `Handler_read_rnd_next` | 全表扫描行数 | 持续增大说明有无索引查询 |
| `Binlog_cache_disk_use` | binlog cache 溢出到磁盘次数 | 调大 `binlog_cache_size` |

**计算 buffer pool 命中率**

```sql
SELECT
  (1 - Innodb_buffer_pool_reads / Innodb_buffer_pool_read_requests) * 100
  AS hit_rate_pct
FROM (
  SELECT
    VARIABLE_VALUE AS Innodb_buffer_pool_reads
  FROM performance_schema.global_status
  WHERE VARIABLE_NAME = 'Innodb_buffer_pool_reads'
) r,
(
  SELECT
    VARIABLE_VALUE AS Innodb_buffer_pool_read_requests
  FROM performance_schema.global_status
  WHERE VARIABLE_NAME = 'Innodb_buffer_pool_read_requests'
) rr;
```

**通过 performance_schema 采集 Top SQL**

```sql
-- 找到累计执行时间最长的 SQL（需要 events_statements_summary_by_digest 打开）
SELECT
  DIGEST_TEXT,
  COUNT_STAR,
  SUM_TIMER_WAIT / 1e12 AS total_latency_s,
  AVG_TIMER_WAIT / 1e9 AS avg_latency_ms,
  SUM_ROWS_EXAMINED,
  SUM_ROWS_SENT
FROM performance_schema.events_statements_summary_by_digest
ORDER BY SUM_TIMER_WAIT DESC
LIMIT 10;
```

**主从监控**

```sql
SHOW REPLICA STATUS\G  -- 8.0 用法，5.7 用 SHOW SLAVE STATUS
-- 关注：
-- Seconds_Behind_Source（主从延迟秒数）
-- Replica_IO_Running / Replica_SQL_Running（均应为 Yes）
-- Last_Error（不应有内容）
```

---

### 3.7 常见故障 SOP 索引

| 故障类型 | 核心判断变量 | 详见 |
|---|---|---|
| CPU 100% | 慢查询 / 全扫 / 锁等待 | Case A |
| 连接数耗尽 | 连接泄漏 / 慢查积压 / 连接池配置 | Case B |
| 慢查询雪崩 | 索引缺失 / 统计信息过期 / 参数分布偏斜 | Case C |
| 主从断裂 | Replica_IO/SQL 线程异常 / 数据冲突 / 网络 | Case D |
| 磁盘满 | binlog 累积 / 临时表 / 数据增长 / undo log | Case E |
| 锁等待 / 死锁 | 长事务 / 热点行 / 索引缺失 | Case F |
| OOM 被 kill | buffer pool 过大 / 连接过多 / 内存表 | Case G |

---

## 4. 日常开发应用

**上线 DDL 前的清单**

1. **评估表大小**：`SELECT table_rows, data_length/1024/1024 AS data_mb FROM information_schema.tables WHERE table_name='orders' AND table_schema='mydb';` 超过 100M rows 一定用 pt-osc 或 gh-ost，不要用裸 ALTER。
2. **测试算法可行性**：`ALTER TABLE orders ADD COLUMN x VARCHAR(100), ALGORITHM=INSTANT, LOCK=NONE;` 不加 `--execute`（MySQL 会直接执行，用 dry-run 场景才是先看报错）。实际上做法是先在从库测试一遍，观察时间和负载。
3. **选择低峰窗口**：即使是 INPLACE，prepare/commit 阶段的短暂 MDL 锁也会阻塞所有 DDL；如果此时有慢查询持有 MDL 读锁，会导致队列堆积。
4. **检查触发器和外键**：pt-osc 碰到外键会警告，gh-ost 默认拒绝有外键的表，需要额外参数。
5. **保留旧表一段时间**：pt-osc rename 后的 `_orders_old` 不要立刻 DROP，留 24h 以防回滚需要。

**备份策略核对**

- 确认 binlog 开启：`SHOW VARIABLES LIKE 'log_bin';`
- 确认 binlog 保留足够长：`SHOW VARIABLES LIKE 'binlog_expire_logs_seconds';`（推荐 604800 = 7 天）
- 定期做恢复演练：备份有效性只有通过实际恢复来验证，每季度做一次 PITR 演练

**写代码时**

- 任何 ALTER 语句不要直接在 ORM migration 里不加限制地跑，要有 `IF NOT EXISTS` 等幂等保护，且要经过上面的清单评估。
- 长事务是所有锁问题和主从延迟的根源：事务里不要有用户交互等待，不要在事务里执行 HTTP 调用，事务尽可能短。
- 连接池配置要合理：最大连接数一般设为 `max_connections * 0.8 / 实例数`，并且要有连接超时和健康检测。

---

## 5. 调优实战（7 大线上故障 SOP）

---

### Case A: CPU 100%

**现象**：监控告警 CPU 持续 > 95%，响应时间从 50ms 飙到 5s，`top` 显示 mysqld 进程吃满所有核。

**排查步骤**

```sql
-- Step 1: 找到当前正在跑的查询（排查热查询）
SHOW PROCESSLIST;
-- 或者更详细（含 trx info）：
SELECT
  p.ID, p.USER, p.HOST, p.DB,
  p.COMMAND, p.TIME, p.STATE,
  LEFT(p.INFO, 200) AS sql_snippet,
  t.trx_id, t.trx_started
FROM information_schema.PROCESSLIST p
LEFT JOIN information_schema.INNODB_TRX t ON p.ID = t.trx_mysql_thread_id
WHERE p.COMMAND != 'Sleep'
ORDER BY p.TIME DESC
LIMIT 20;

-- Step 2: 找 top SQL（按累计 CPU/扫描行排序）
SELECT DIGEST_TEXT, COUNT_STAR,
  SUM_TIMER_WAIT/1e12 AS total_s,
  SUM_ROWS_EXAMINED / COUNT_STAR AS avg_rows_examined
FROM performance_schema.events_statements_summary_by_digest
ORDER BY SUM_TIMER_WAIT DESC LIMIT 10;

-- Step 3: 确认是否全扫（Handler_read_rnd_next 增速）
SHOW GLOBAL STATUS LIKE 'Handler_read_rnd_next';
-- 如果每秒增加数百万说明有大量全扫在跑
```

**常见根因**

| 根因 | 特征 | 应对 |
|---|---|---|
| 大量全表扫描 | `Handler_read_rnd_next` 飙升，processlist 有长时间 `Sending data` | `EXPLAIN` 找缺失索引，紧急加索引（INPLACE 或 pt-osc） |
| 批量大查询 | 单条 SQL rows_examined 百万级 | 找调用方，拆分查询，分页，加 LIMIT |
| 并发连接暴增 + 锁等待 | `Threads_running` >> CPU 核数，processlist 有大量 `waiting for lock` | 见 Case F，先 kill 长事务 |
| 统计信息失效导致全扫 | `EXPLAIN` 看到 rows 估算严重偏低但实际全扫 | `ANALYZE TABLE tablename;` 更新统计 |

**应急处理**：找到罪魁祸首查询后，`KILL QUERY <thread_id>;`（只 kill 查询不断连接）。如果是批量脚本在跑，先暂停脚本；如果是前端流量导致，考虑降级（切只读副本 / 限流）。

**恢复后**：打开慢查询日志（如果没开），`pt-query-digest /var/log/mysql/slow.log` 分析 Top 10 慢 SQL，逐个优化。

---

### Case B: 连接数耗尽（Too many connections）

**现象**：应用报 `ERROR 1040 (HY000): Too many connections`，新请求全部失败，现有请求可能还在正常跑。

**排查步骤**

```sql
-- Step 1: 确认当前连接状态
SHOW GLOBAL STATUS LIKE 'Threads_connected';
SHOW VARIABLES LIKE 'max_connections';

-- Step 2: 看连接分布（找泄漏来源）
SELECT USER, HOST, DB, COMMAND, COUNT(*) AS cnt
FROM information_schema.PROCESSLIST
GROUP BY USER, HOST, DB, COMMAND
ORDER BY cnt DESC;

-- Step 3: 找 Sleep 连接（连接池没有释放）
SELECT COUNT(*) FROM information_schema.PROCESSLIST
WHERE COMMAND = 'Sleep' AND TIME > 60;

-- Step 4: 找长时间 Sleep 的连接（可能泄漏）
SELECT ID, USER, HOST, DB, TIME, INFO
FROM information_schema.PROCESSLIST
WHERE COMMAND = 'Sleep' AND TIME > 300
ORDER BY TIME DESC;
```

**常见根因**

| 根因 | 判断方式 | 应对 |
|---|---|---|
| 连接泄漏（应用没有正确关连接） | `Sleep` 连接数量大且 TIME 很长 | 应用层修复连接管理；短期 kill Sleep 连接 |
| 连接池配置不合理（最大连接数过大） | 连接数 = 实例数 × 池大小 > max_connections | 压缩连接池 max size；引入 ProxySQL / MySQL Router 连接复用 |
| 慢查询积压（每条查询很慢，连接堆积） | `Threads_running` 高，`Sleep` 少 | 见 Case A/C，解决慢查询根因 |
| 流量突增 | 连接数短时暴增，没有 Sleep | 应急：临时调大 `max_connections`；长期：加只读副本分流 |

**应急处理**：
```sql
-- 临时调大（重启失效，须同步改 my.cnf）
SET GLOBAL max_connections = 1000;

-- 批量 kill Sleep 超过 300s 的连接
SELECT CONCAT('KILL ', ID, ';') 
FROM information_schema.PROCESSLIST 
WHERE COMMAND='Sleep' AND TIME > 300;
-- 把输出复制出来执行，或用 pt-kill 工具

-- 使用 pt-kill 自动处理（更安全）
pt-kill --host=127.0.0.1 --user=root --password=secret \
  --match-command Sleep --busy-time 300 --kill --print --daemonize
```

**根本解决**：连接问题 99% 可以通过 ProxySQL 或 MySQL Router 做连接复用来解决，业务层连接数大但实际到 MySQL 的连接数可以收敛到 200 以内。

---

### Case C: 慢查询雪崩

**现象**：数据库平时正常，某次发布后或某时间点（如整点定时任务触发）后，响应时间从正常突然升到 10s+，CPU 随之升高，形成正反馈（慢 → 连接积压 → 更慢）。

**排查步骤**

```sql
-- Step 1: 查慢查询日志（确认是什么 SQL）
-- tail -f /var/log/mysql/slow.log
-- 或通过 pt-query-digest 分析：
-- pt-query-digest /var/log/mysql/slow.log --limit 10

-- Step 2: 在库上实时看
SELECT * FROM performance_schema.events_statements_summary_by_digest
ORDER BY SUM_TIMER_WAIT DESC LIMIT 5;

-- Step 3: EXPLAIN 找问题（type=ALL, Using filesort, rows 很大）
EXPLAIN SELECT ...;

-- Step 4: 看是否是统计信息问题（rows 估算严重不准）
ANALYZE TABLE tablename;
-- 然后重新 EXPLAIN 对比

-- Step 5: 看是否是数据分布问题（某列值偏斜）
SELECT city, COUNT(*) FROM users GROUP BY city ORDER BY COUNT(*) DESC LIMIT 10;
-- 如果某个值占 80%，走了这列的索引反而不如全扫，优化器可能在两者间抖动
```

**常见根因**

| 根因 | 识别方式 | 应对 |
|---|---|---|
| 新发布引入了没索引的查询 | 慢日志里有新 SQL pattern | `EXPLAIN` → 加索引 |
| 定时任务大查询 | 固定时间点触发 | 把定时任务改到低峰期；加 LIMIT 分批 |
| 统计信息过期（大量写入后） | rows 估算偏差 10x+ | `ANALYZE TABLE` 更新统计 |
| 数据量增长触发执行计划变更 | 以前走索引，最近全扫 | `optimizer_trace` 看成本估算；必要时 `FORCE INDEX` |
| 缓存击穿（Redis 失效后所有流量打到 DB） | 连接数暴增，查询模式是大量重复 SELECT | 缓存层加互斥锁（只让一个线程重建缓存），DB 端暂时限流 |

**雪崩应急流程**：
1. 先降级：把读流量切到只读副本，主库只保留写
2. Kill 积压的慢查询（`KILL QUERY <id>`）
3. 临时 `SET GLOBAL max_connections` 控制新连接
4. 找到根因 SQL，评估是否可以立即加索引（INPLACE/INSTANT），或者先加 `FORCE INDEX` hint

---

### Case D: 主从断裂

**现象**：监控告警 `Replica_IO_Running=No` 或 `Replica_SQL_Running=No`，或 `Seconds_Behind_Source` 持续增大（延迟超过阈值）。

**排查步骤**

```sql
-- Step 1: 在从库上执行
SHOW REPLICA STATUS\G   -- 8.0；5.7 用 SHOW SLAVE STATUS\G

-- 关键字段：
-- Replica_IO_Running: Yes/No
-- Replica_SQL_Running: Yes/No
-- Last_IO_Error: ...
-- Last_SQL_Error: ...
-- Seconds_Behind_Source: N
-- Exec_Master_Log_Pos vs Read_Master_Log_Pos（判断是 IO 线程慢还是 SQL 线程慢）
```

**常见根因及处理**

**场景 1：IO 线程断（`Replica_IO_Running=No`）**

通常是网络问题或主库 binlog 被清理。

```sql
-- 查看 Last_IO_Error
-- 常见: "Got fatal error 1236 from master ... log does not exist"
-- 说明从库 relay log 位点对应的 binlog 在主库被清理（expire 太短或 PURGE BINARY LOGS）

-- 如果只是网络抖动，重启 IO 线程通常能恢复：
STOP REPLICA IO_THREAD;
START REPLICA IO_THREAD;
```

如果 binlog 已被清理，从库需要重建（从全备 + 新 binlog 起点重新搭）。

**场景 2：SQL 线程断（`Replica_SQL_Running=No`）**

通常是主从数据不一致（主库有，从库没有）或表结构不同。

```sql
-- 查看 Last_SQL_Error
-- 常见: "Error 'Duplicate entry' on query" 或 "Error 'Row doesn't exist'"

-- 方法一：跳过这条错误事件（有数据丢失风险！）
-- 非 GTID 模式：
STOP REPLICA SQL_THREAD;
SET GLOBAL SQL_SLAVE_SKIP_COUNTER = 1;
START REPLICA SQL_THREAD;

-- GTID 模式：注入空事务跳过
SET GTID_NEXT='uuid:N';  -- 填 Last_SQL_Error 里的 GTID
BEGIN; COMMIT;
SET GTID_NEXT='AUTOMATIC';
START REPLICA;
```

**注意**：跳过只是应急，根本原因是有写入绕过了从库（直接写从库，或 `sql_log_bin=0` 的操作）。应当用 pt-table-checksum + pt-table-sync 做数据一致性校验，找出差异后修复。

**场景 3：延迟持续增大（`Seconds_Behind_Source` 增加）**

```sql
-- 看 SQL 线程在做什么
SELECT * FROM performance_schema.replication_applier_status_by_worker\G
-- 找到当前正在回放的事务和 SQL

-- 常见原因：
-- 1. 主库上的大事务（e.g. 批量 UPDATE 百万行一个事务），从库 SQL 线程串行回放
-- 2. 从库 CPU/IO 跟不上主库
-- 3. 没有开并行回放
```

开启并行回放（8.0 推荐 LOGICAL_CLOCK）：
```sql
-- 在从库上
STOP REPLICA;
SET GLOBAL replica_parallel_workers = 8;
SET GLOBAL replica_parallel_type = 'LOGICAL_CLOCK';  -- 8.0 默认
START REPLICA;
```

主库端配合：`binlog_transaction_dependency_tracking = WRITESET`（8.0.1+），让 binlog 记录事务依赖信息，从库并行回放更积极。

---

### Case E: 磁盘满

**现象**：写入报错 `ERROR 1028 (HY000): Sort aborted: No space left on device` 或 `ERROR 3 (HY000): Error writing file '/tmp/xxx'`。监控磁盘 > 95%。

**排查步骤**

```bash
# Step 1: 看哪个目录占用最大
df -h
du -sh /var/lib/mysql/* | sort -rh | head -20

# Step 2: 确认 binlog 占用
ls -lh /var/lib/mysql/mysql-bin.* | tail -20
# 或
SHOW BINARY LOGS;  -- 在 MySQL 里看 binlog 列表和大小
```

**常见根因及应对**

| 根因 | 判断 | 应对 |
|---|---|---|
| binlog 堆积 | `SHOW BINARY LOGS` 看到大量旧 binlog | 确认从库已消费后：`PURGE BINARY LOGS TO 'mysql-bin.000100'` 或 `PURGE BINARY LOGS BEFORE NOW() - INTERVAL 3 DAY` |
| 数据文件增长 | `tablename.ibd` 过大 | 归档冷数据；分区表；只能加磁盘 |
| undo log 膨胀 | `ibdata1` 或 undo tablespace 过大（因长事务） | 找到长事务 `SELECT * FROM information_schema.INNODB_TRX ORDER BY trx_started;` → kill 长事务 |
| 临时文件 | `/tmp` 下有大量 `.MYD` 文件 | 大 GROUP BY / filesort 产生的临时表；杀掉查询后清理；调大 `tmp_table_size` |
| 慢查询 relay log | 从库延迟大时 relay log 积累 | 解决延迟（见 Case D）|

**紧急释放空间**：
```sql
-- 安全删除旧 binlog（先确认从库位点在哪里）
SHOW REPLICA STATUS\G  -- 从库上查 Master_Log_File / Read_Master_Log_Pos
-- 主库上：只删从库已消费的 binlog 之前的
PURGE BINARY LOGS TO 'mysql-bin.000095';
```

磁盘满时 MySQL 可能无法写入，但通常可以读。紧急情况下先腾出空间（删临时文件 / 清理旧 binlog），再做根因修复。

---

### Case F: 锁等待

**现象**：应用日志出现 `Lock wait timeout exceeded`（`innodb_lock_wait_timeout` 默认 50s）或死锁日志 `DEADLOCK`。慢查询里出现 `waiting for lock`。

**排查步骤**

```sql
-- Step 1: 找当前锁等待关系
SELECT
  r.trx_id AS waiting_trx_id,
  r.trx_mysql_thread_id AS waiting_thread,
  r.trx_query AS waiting_query,
  b.trx_id AS blocking_trx_id,
  b.trx_mysql_thread_id AS blocking_thread,
  b.trx_query AS blocking_query,
  b.trx_started AS blocking_started,
  TIMESTAMPDIFF(SECOND, b.trx_started, NOW()) AS blocking_seconds
FROM information_schema.INNODB_LOCK_WAITS w
JOIN information_schema.INNODB_TRX r ON r.trx_id = w.requesting_trx_id
JOIN information_schema.INNODB_TRX b ON b.trx_id = w.blocking_trx_id;

-- 8.0.1+ 改用 performance_schema（information_schema 里的旧视图被移除）
SELECT
  r.THREAD_ID AS waiting_thread,
  r.SQL_TEXT AS waiting_sql,
  b.THREAD_ID AS blocking_thread,
  b.SQL_TEXT AS blocking_sql
FROM performance_schema.data_lock_waits w
JOIN performance_schema.events_statements_current r
  ON r.THREAD_ID = w.REQUESTING_THREAD_ID
JOIN performance_schema.events_statements_current b
  ON b.THREAD_ID = w.BLOCKING_THREAD_ID;

-- Step 2: 看死锁日志（最近一次死锁的详情）
SHOW ENGINE INNODB STATUS\G
-- 在输出里找 LATEST DETECTED DEADLOCK 段

-- Step 3: 找长事务（锁源头）
SELECT trx_id, trx_started, trx_query,
  TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS duration_s
FROM information_schema.INNODB_TRX
ORDER BY trx_started
LIMIT 10;
```

**常见根因**

| 根因 | 特征 | 解决 |
|---|---|---|
| 长事务持有行锁 | `INNODB_TRX` 里有老事务，持锁时间长 | Kill 长事务；应用层缩短事务生命周期 |
| 热点行争用 | 同一行被大量并发更新（如库存扣减） | 拆分热点行（分段锁）；队列化；乐观锁（SELECT ... FOR UPDATE 改 CAS） |
| 范围锁 / gap lock | RR 隔离级别下范围查询加 gap lock | 降隔离级别为 RC（`transaction_isolation=READ-COMMITTED`）；或改查询避免 gap lock |
| 索引缺失导致全表锁 | UPDATE/DELETE 无索引条件，锁住大量行甚至全表 | 为 WHERE 条件加索引 |
| 死锁（两个事务互相等待） | INNODB STATUS 显示 DEADLOCK | 应用层检测 deadlock 错误码（1213）并重试；根本是操作顺序不一致，改为统一顺序访问行 |

**紧急应对**：`KILL <blocking_thread_id>` kill 掉阻塞源头的连接（整个连接，不只是查询），会回滚其事务并释放锁。

---

### Case G: OOM 被 kill

**现象**：mysqld 进程突然消失，系统日志 `/var/log/syslog` 或 `dmesg` 里出现 `Out of memory: Kill process ... mysqld`（Linux OOM Killer）。

**排查步骤**

```bash
# Step 1: 确认是 OOM 还是 mysqld crash
dmesg | grep -i "oom\|kill process\|mysqld" | tail -20
# 或
grep -i "oom\|killed\|mysqld" /var/log/syslog | tail -50

# Step 2: 查 MySQL 的内存使用明细（需要 8.0+ performance_schema）
```

```sql
-- 各组件内存用量
SELECT EVENT_NAME, CURRENT_NUMBER_OF_BYTES_USED/1024/1024 AS current_mb
FROM performance_schema.memory_summary_global_by_event_name
WHERE CURRENT_NUMBER_OF_BYTES_USED > 1024*1024
ORDER BY CURRENT_NUMBER_OF_BYTES_USED DESC
LIMIT 20;
```

**常见根因**

| 根因 | 判断 | 应对 |
|---|---|---|
| `innodb_buffer_pool_size` 设置太大 | 总 MySQL 内存预估 > 物理内存 80% | 减小 buffer pool，给 OS 留 20%+ |
| 连接数太多（每个连接消耗内存） | `max_connections` 大，`Threads_connected` 高 | 降低 max_connections；引入连接代理；降低 `sort_buffer_size` / `read_buffer_size`（每个连接独立分配） |
| 大查询内存临时表 | 复杂 GROUP BY / DISTINCT 生成巨大内存临时表 | 限制 `tmp_table_size` / `max_heap_table_size`；优化查询 |
| Performance Schema 内存 | PS 配置过多 instrument | 减少 instruments（关闭不需要的 consumers） |

**内存估算公式**（粗算）：
```
总内存 ≈ innodb_buffer_pool_size
       + max_connections × (sort_buffer_size + read_buffer_size + join_buffer_size + thread_stack)
       + key_buffer_size  (MyISAM)
       + OS 和其他进程 (留 1-2G)
```
以 8G 机器为例：buffer pool 4G + 500 连接 × (1M+256K+256K+192K) ≈ 4 + 0.85 = 4.85G，加 OS 约 2G，合计 6.85G，安全。

**预防**：
```bash
# 限制 mysqld OOM score（让内核优先 kill 其他进程）
echo -1000 > /proc/$(pgrep mysqld)/oom_score_adj
# 或在 systemd unit 里加 OOMScoreAdjust=-1000
```
但更好的预防是不让 OOM 发生：监控内存使用率，>80% 告警；定期 review `innodb_buffer_pool_size` 是否合适。

---

## 6. 面试高频考点

### Online DDL 三连问

**Q: INSTANT / INPLACE / COPY 区别？**

答题框架：从「原理」→「阻塞时间」→「适用场景」：
- INSTANT：只改元数据，不动数据页，几乎不阻塞，但支持的操作有限（8.0.29+ 支持加删列、改默认值）
- INPLACE：引擎内操作，读不阻塞，写只在 prepare/commit 阶段短暂阻塞（毫秒级），覆盖大多数 ALTER 操作
- COPY：建临时表全量拷贝，全程锁表，大表几小时不可写，已基本被淘汰（除非必须 COPY）

**Q: 大表加列不能用裸 ALTER，你们怎么做？**

1. 先评估能否 INSTANT（8.0.29+，加列基本都能 INSTANT，秒级）
2. 不能 INSTANT 的用 pt-osc 或 gh-ost（影子表 + 增量同步 + rename）
3. 写 QPS 高 / 触发器有风险时用 gh-ost（binlog 消费，无触发器）
4. 操作前在从库先演练一遍

**Q: pt-osc 和 gh-ost 怎么选？**

- pt-osc：成熟稳定，部署简单，适合中低写入场景
- gh-ost：无触发器，写入开销低，支持运行时动态限速暂停，高写入 / 需要精细控制时首选
- 两者都需要主键，都需要约 2x 磁盘空间

### 备份与恢复

**Q: mysqldump 和 xtrabackup 各自适用什么场景？**

- mysqldump：小表（< 10GB）、跨版本迁移、只备份部分表，可读 SQL 方便检查
- xtrabackup：大表（> 10GB）、生产主从快速搭建、需要增量备份、RTO 要求短

**Q: PITR 原理？**

全备（一致性起点）+ binlog 重放（从全备时间点到目标时间点的所有 DML/DDL 事件）。需要 binlog_format=ROW 保证行级准确性，且 binlog 保留足够长。

**Q: xtrabackup 为什么要 prepare 阶段？**

备份时 InnoDB 还在运行，拷贝 ibd 文件的过程中有新的 redo log 产生，数据文件处于"物理不一致"状态。prepare 阶段把备份后产生的 redo log 前滚（apply）到数据文件，让整个备份达到一致性检查点状态。

### 故障排查

**Q: CPU 100% 第一步看什么？**

`SHOW PROCESSLIST` + `SHOW GLOBAL STATUS LIKE 'Handler_read_rnd_next'`，找正在跑的查询，看是否有大量全扫，然后 `EXPLAIN` 找缺失索引。

**Q: Too many connections 怎么处理？**

先 `SET GLOBAL max_connections` 临时调大让新连接进来（如果彻底满了只能从 OS 层 kill），然后查 `PROCESSLIST` 找 Sleep 连接来源（连接泄漏 / 连接池配置错误），kill 超时 Sleep 连接，最终引入 ProxySQL 做连接复用。

**Q: 主从延迟排查思路？**

`SHOW REPLICA STATUS` 看 `Seconds_Behind_Source` 和两个线程状态：
- IO 线程断 → 网络或 binlog 被清
- SQL 线程断 → 数据冲突或表结构不一致，看 `Last_SQL_Error`
- 延迟大但线程都 running → 大事务串行回放，开启并行回放（`replica_parallel_workers > 1`）

### 参数类

**Q: `innodb_flush_log_at_trx_commit` 设成 2 会丢数据吗？**

最多丢最近 1 秒的数据（OS crash 时，buffer 里未 flush 到磁盘的 redo log）。MySQL 进程 crash 不丢（redo log 写到了 OS buffer，只是没 fsync）。金融级数据要求保持 1；允许少量丢失的高写入场景可以设 2 提升 2-3x 写入性能。

**Q: `innodb_buffer_pool_size` 调多大合适？**

RAM × 0.5~0.75，给 OS、连接内存、其他进程留余量。专用数据库服务器可以到 0.75，共享机器 0.5。超过 1G 时同时调整 `innodb_buffer_pool_instances`（建议等于 CPU 核数，最大 64）减少并发竞争。

---

## 7. 一句话总结

MySQL 运维的三大支柱是：**DDL 不锁表**（INSTANT 8.0+ 秒级加列，大表用 pt-osc/gh-ost）、**备份能恢复**（xtrabackup 物理备份 + binlog PITR，定期演练）、**故障有 SOP**（CPU 100% 查全扫、连接耗尽查泄漏、主从断裂看线程状态、磁盘满清 binlog、锁等待找长事务）。参数调优的第一步是把 `innodb_buffer_pool_size` 从 128M 调到 RAM × 0.5~0.75，其余参数在监控指标（命中率、`Threads_running`、慢查增速）的反馈下迭代调整。
