# Redo / Undo / Binlog 与 Crash-safe

## 1. 核心问题

数据库在掉电或进程崩溃后重启，它怎么知道哪些数据写进去了、哪些没写？主库和从库的数据靠什么保持同步？同一个事务里改了 10 行，中途崩了怎么回滚？

这些问题的答案归根结底是三个日志的协作：

- **Redo Log**（重做日志）：让 InnoDB 在内存里先写、磁盘慢慢追，同时保证崩溃后能把"已提交但还没落盘"的数据恢复出来。
- **Undo Log**（回滚日志）：让事务在中途可以反悔，也为 MVCC 多版本读提供历史快照。
- **Binlog**（归档日志）：Server 层的"剧本"，所有引擎共用，主从复制和时间点恢复都靠它。

三者分工不同、写入时序严格——错一步，数据一致性就崩。

## 2. 直觉理解

**记事本比喻**

想象你是一家饭馆的收银员，顾客结账时：

- **Redo log = 收银台旁边的小本子**（"记事本"）：先在小本子上草写"桌 3 收了 188 元"，然后再把钱放进保险箱（磁盘）。如果停电了，保险箱里可能还没更新，但草稿本还在——重启时按草稿本补记，数据不丢。
- **Undo log = 草稿本上的撤销注记**："如果桌 3 反悔了，把 188 元退回去"。万一事务中途失败，按注记反向操作恢复原状。草稿本本身也是受保护的（它的修改也记 redo），不能就这么丢。
- **Binlog = 给总部的 PDF 报表**：今天所有交易的完整记录，发给连锁店（从库）对账，也存档备份。格式是"桌 3 结账 188 元"这样的业务逻辑描述，不是"内存第 X 页第 Y 字节变成 Z"。

三者核心区别一眼看出：redo/undo 是"给 InnoDB 自己用的底层记录"，binlog 是"给外部用的高层剧本"。

## 3. 原理深入

### 3.1 三个日志一图分工

```
┌──────────────────────────────────────────────────────────────────┐
│                         MySQL Server 层                           │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Binlog  (逻辑日志 · Server 层 · 所有引擎共用)              │  │
│  │  用途: 主从复制 / 时间点恢复 / 审计                         │  │
│  │  格式: STATEMENT / ROW / MIXED                              │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              InnoDB 引擎层                                │    │
│  │                                                           │    │
│  │  ┌─────────────────────────┐  ┌──────────────────────┐  │    │
│  │  │ Redo Log (物理日志)      │  │ Undo Log (逻辑日志)  │  │    │
│  │  │ 记"在哪个页哪个偏移      │  │ 记"原来是什么值"     │  │    │
│  │  │  写了什么字节"           │  │                      │  │    │
│  │  │ 用途: crash recovery    │  │ 用途: rollback/MVCC  │  │    │
│  │  │       + WAL 性能        │  │                      │  │    │
│  │  │ 生命周期: 循环覆写       │  │ 生命周期: 保留到事务  │  │    │
│  │  │                         │  │ 结束且无读者为止      │  │    │
│  │  └─────────────────────────┘  └──────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

| 维度         | Redo Log              | Undo Log                   | Binlog                          |
|--------------|-----------------------|----------------------------|---------------------------------|
| 所属层次     | InnoDB 引擎层         | InnoDB 引擎层              | MySQL Server 层                 |
| 日志类型     | 物理日志              | 逻辑日志                   | 逻辑日志                        |
| 记录内容     | 某页某偏移写了什么    | 行的旧值（怎么反向操作）   | SQL 语句或行变化                |
| 主要用途     | Crash Recovery / WAL  | Rollback / MVCC 历史版本   | 主从复制 / 时间点恢复           |
| 写入方式     | 循环写（不保留历史）  | 追加写（保留到可清除为止） | 追加写（保留到过期为止）        |
| 跨引擎       | 否（InnoDB 专属）     | 否（InnoDB 专属）          | 是（所有引擎共用）              |

### 3.2 WAL 原则

WAL = **Write-Ahead Logging**（先保证 redo 持久化，再允许对应脏页写出）。这里的「先」约束的是**落盘顺序**，不是说内存数据页必须等 redo 写完后才能修改。

核心思路不是让数据页写入消失，而是把事务提交的持久化关键路径，从「同步等待多个数据页写回」改成「先等待连续的 redo 写入；数据页稍后由后台刷回」。

**为什么 WAL 有效：**

1. **提交不等待随机数据页写回**：事务只需等待对应 redo 达到所需持久化位置；散落在不同表空间的数据页由 page cleaner 后台处理。
2. **Group Commit 摊薄 `fsync`**：多个并发事务的 redo 可以由一次 `fsync` 覆盖，减少「每事务一次设备持久化屏障」的固定成本。
3. **同一数据页的多次修改可以合并**：一个 InnoDB B+Tree 页默认是 16KB，不是一行。相邻主键、递增主键插入、热点库存行或计数器可能反复修改同一个 leaf page。只要该页尚未刷出，100 次修改会生成各自的 redo，但数据页可能只需写出包含最终状态的一次 16KB 镜像。
4. **后台 I/O 更容易并行和批量调度**：前台事务不再逐个同步等待离散 page write；后台可以维持更高 I/O queue depth，让 SSD/NVMe 并行处理。

**WAL 没有消灭什么：**

- 如果 100 次随机更新命中 100 个不同页，最终仍要刷 100 个数据页；「同页合并」几乎没有收益。
- 若持续写入速度超过刷脏能力，checkpoint age 会不断增长；redo 空间逼近上限后，InnoDB 必须强制加速刷脏，前台仍会出现 write stall。
- 所以 WAL 主要降低**提交延迟**、提高并发吞吐并吸收短期尖峰；长期稳态随机写吞吐仍受数据页刷盘 IOPS 限制。

**WAL 的约束：**
1. 数据页（脏页）在被刷回磁盘之前，对应的 redo log 必须先落盘。
2. 事务提交时，redo log 的 prepare 记录必须先 fsync，binlog 再 fsync，最后 redo log 写 commit——这就是两阶段提交的根基，下面详述。

### 3.3 Redo Log：buffer + 刷盘 + 循环写 + checkpoint + LSN

#### Redo Log Buffer

Redo Log Buffer 是 `mysqld` 进程内、由 InnoDB 管理的环形字节数组，大小由 `innodb_log_buffer_size` 控制。默认值随版本变化：MySQL 5.7/8.0 常见为 16MB，MySQL 8.4 为 64MB；应以实例查询结果为准。

事务在 mini-transaction（mtr）中修改数据页并收集 redo records；`mtr_commit()` 再为这组 records 预留一段 LSN 范围，把 bytes 复制到全局 redo log buffer。底层可理解为：

```text
atomic fetch_add 预留 LSN
    ↓
memcpy / CPU memory store
    ↓
log_buffer[LSN % log_buffer_size]
```

这一步只修改 `mysqld` 的 user-space memory：没有文件 I/O，没有进入 kernel，也没有操作 SSD。并发线程可以写不同 LSN 区间；log writer 只会写出已经连续完成、没有空洞的 log blocks。

```sql
-- 查看当前值
SHOW VARIABLES LIKE 'innodb_log_buffer_size';
```

#### Redo Log Buffer 与 OS Page Cache：实际操作什么

以 MySQL 8.x + Linux 常见 buffered I/O 路径为例，redo 从生成到持久化会经过：

```text
事务线程
  │ CPU memcpy：mtr buffer → redo log buffer
  ▼
mysqld user space
InnoDB redo log buffer（匿名内存、环形数组）
  │ write()/pwrite() 或平台等价调用
  ▼
Linux kernel space
OS page cache（按 inode + file offset 管理的 file-backed memory）
  │ fsync()/fdatasync()
  ▼
filesystem writeback → block layer → device driver
  │ DMA / NVMe write + 必要的 cache flush/FUA
  ▼
SSD/HDD 非易失介质
```

这里的 DMA（Direct Memory Access，直接内存访问）表示设备无需 CPU 逐字节搬运即可从内存取数据；FUA（Force Unit Access，强制单次写入直达非易失介质）用于避免设备只把写入留在易失缓存中。

两层虽然物理上都可能位于 DRAM，实际操作完全不同：

- **InnoDB redo log buffer**：InnoDB 分配 LSN、组织 redo group、补 log block header/footer、计算 checksum；事务线程通过普通 CPU store / `memcpy` 写入。它属于 `mysqld` 进程，进程退出后内存会被回收。
- **OS page cache**：log writer 对 redo 文件执行 `write()` / `pwrite()` 后，kernel 根据文件 inode（文件元数据对象）和 offset 找到或创建 page-cache folio（内核批量管理的一组缓存页），把 bytes 从 user space 复制进去并标记为 dirty。OS 只理解「文件某个 offset 的 bytes」，不理解 transaction、LSN 或 redo record。
- **持久介质**：`write()` 成功通常只表示 kernel 已接收数据，不等于断电安全。log flusher 执行 `fsync()` / `fdatasync()`，kernel 才把 dirty cache 交给文件系统和 block layer，并等待设备完成必要的写入与缓存刷新。

InnoDB 用不同进度表示三种事实：

| 进度 | 已完成的实际操作 | 此时失败会怎样 |
|------|------------------|----------------|
| `log_buffer_ready_for_write_lsn()` | redo 已完整复制到 InnoDB log buffer | `mysqld` crash 会丢尚未写出的部分 |
| `write_lsn` | log writer 已把 redo 写到 log file / OS system buffer | 单独的 `mysqld` crash 通常保留；OS crash 或断电仍可能丢 |
| `flushed_to_disk_lsn` | log flusher 已完成 `fsync` | 正常遵守 flush 语义的存储设备上，断电后仍可恢复 |

**为什么不能把两个 buffer 合并：**

- 若只用 OS page cache，在常规 `write()` 路径下，InnoDB 每产生小段 redo 就要进入 kernel；而且 kernel 不会替 InnoDB 分配 LSN、判断 redo group 是否完整或计算日志 checksum。MySQL 最终仍要先在 user space 组装数据，相当于重新造一个 log buffer。
- `mmap` 可以把 file-backed pages 映射进 user space，减少显式复制，但 InnoDB 仍需管理完整 redo group、LSN 和 checksum，并用 `msync`/`fsync` 建立持久化边界；它只让物理内存可能重叠，没有合并两层职责。
- 若只用 InnoDB log buffer，user-space 内存无法提供文件系统、设备调度和断电持久化语义。MySQL 仍需通过 kernel 把 bytes 送到设备，并明确执行 flush。
- 某些 `innodb_flush_method`、同步 I/O 或 direct I/O 配置可以绕过部分 OS page-cache 路径，但「redo 已在 InnoDB 中完整生成」「OS/设备已接收」「redo 已持久化」三个逻辑状态仍然存在。

现代 MySQL 由不同后台职责推进这些状态：

1. **Log writer**：把完整 redo blocks 从 log buffer 写到 OS system buffers，推进 `write_lsn`。
2. **Log flusher**：执行 `fsync`，推进 `flushed_to_disk_lsn`。
3. **事务线程**：按照 `innodb_flush_log_at_trx_commit` 等待所需 LSN；通常不是事务线程自己直接操作 redo file。
4. **空间压力或定时任务**：即使事务尚未提交，log buffer 空间不足等情况也可能触发提前写出；不要把「write」和「fsync」视为同一个动作。

底层实现参考：[MySQL Redo Log Buffer](https://dev.mysql.com/doc/dev/mysql-server/latest/PAGE_INNODB_REDO_LOG_BUF.html)、[MySQL Background Redo Log Threads](https://dev.mysql.com/doc/dev/mysql-server/latest/PAGE_INNODB_REDO_LOG_THREADS.html)、[Linux Buffered I/O](https://docs.kernel.org/filesystems/iomap/operations.html#buffered-i-o)、[Linux Volatile Write-back Cache Control](https://docs.kernel.org/block/writeback_cache_control.html)。

#### innodb_flush_log_at_trx_commit 三档对比

这是 InnoDB 最重要的性能 vs 持久性调节参数：

| 值  | commit 等待条件 | 后台行为 | 持久性 | 一般性能 |
|-----|-----------------|----------|--------|----------|
| `0` | 不等待该事务 redo 达到 `write_lsn` 或 `flushed_to_disk_lsn` | 后台按 timeout 等条件 write + flush | `mysqld`、OS crash 或断电都可能丢最近一段事务 | 最高 |
| `1` | 等待 `flushed_to_disk_lsn >= commit_lsn`（默认） | log writer 写出，log flusher 完成 `fsync` 后唤醒事务 | 完整 ACID 持久性要求的配置 | 最低 |
| `2` | 等待 `write_lsn >= commit_lsn`，不等待 `fsync` | 后台按 timeout 等条件 flush | 单独 `mysqld` crash 通常不丢；OS crash 或断电可能丢最近一段事务 | 中等 |

```sql
SHOW VARIABLES LIKE 'innodb_flush_log_at_trx_commit';
-- 生产 OLTP 推荐 1；高吞吐写入场景（可接受少量丢失）可设 2
```

`innodb_flush_log_at_timeout` 控制定时 write/flush 的间隔，默认是 1 秒。但「每秒一次」不是实时保证：线程调度可能让它更晚，DDL 或其他内部活动也可能提前触发 flush。因此准确说法是「最多可能丢失最近一个实际 flush 间隔的数据」，不是永远精确 1 秒。

> 记忆口诀：**0 不等 write/flush；1 等 fsync；2 等 write、不等 fsync**。只有 `1` 把事务成功返回绑定到持久化完成。

#### Redo Log 文件 + 循环写

**8.0.30 以前**：redo log 由 `N` 个大小相同的文件组成，循环写入。

```
innodb_log_files_in_group = 2   （默认 2 个文件）
innodb_log_file_size = 48MB     （默认每个 48MB，总 96MB）
```

文件名为 `ib_logfile0`、`ib_logfile1`，写满 1 后续写 2，写满 2 再回到 1 覆盖——循环写。

**8.0.30+**：改为 redo log files 动态管理，参数换成：

```
innodb_redo_log_capacity = 104857600   （默认约 100MB，可在线 SET GLOBAL 动态改）
```

旧参数 `innodb_log_file_size` 和 `innodb_log_files_in_group` 被弃用（deprecated），设置了会有警告。新参数支持在线 resize，不需要重启。

#### Checkpoint + LSN

**LSN（Log Sequence Number）**：单调递增的 64 位整数，代表 redo log 写入的字节总量。每写一条 redo log record，LSN 就增加对应字节数。

关键 LSN 概念：
- **current LSN**：最新写入 redo buffer 的位置
- **flushed-to-disk LSN**：已 fsync 到 redo log 文件的位置
- **checkpoint LSN**：脏页已经刷回数据文件的最小 LSN——这个位置之前的 redo log 已经"没用了"，可以被新的 redo 覆盖

循环写的本质问题：**write pos 不能追上 checkpoint**。如果追上了，说明 redo log 满了，需要先推进 checkpoint（即强制刷脏页）才能继续写。

```
         ┌──────────────────────────────────────────────────┐
redo log │░░░░░░░░░░░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░│
文件示意  └──────────────────────────────────────────────────┘
         ↑checkpoint LSN             ↑write pos

░ = 已 checkpoint（可覆盖的区域）
▓ = redo log 有效区域（checkpoint 到 write pos）
```

当 redo log 快写满时（write pos 接近 checkpoint），InnoDB 会触发"强制 checkpoint"：把脏页刷回磁盘，推进 checkpoint LSN，腾出空间。这时**写入会被卡住**，是生产常见的性能抖动点。

```sql
-- 查看 checkpoint 和 write pos 的距离
SHOW ENGINE INNODB STATUS\G
-- 找 LOG 段，看 Log sequence number / Last checkpoint at / Checkpoint age
```

#### 性能影响

redo log 太小会导致 checkpoint 频繁，造成写停顿（write stall）。经验值：redo log 总容量设为 1~4GB，对 OLTP 负载通常足够。

```sql
-- 8.0.30+：在线扩容，不需要重启
SET GLOBAL innodb_redo_log_capacity = 4294967296;  -- 4GB
```

### 3.4 Undo Log：作用 + 也是 redo-logged

Undo log 在 ch05（MVCC 与事务）已有详细分析，这里强调两点容易被忽略的细节。

**Undo log 的两个职责**：
1. **Rollback（回滚）**：事务中途失败或显式 `ROLLBACK` 时，按 undo log 的逻辑反向操作，把数据改回去。
2. **MVCC 历史版本**：其他事务读历史快照时，沿 undo log 链（版本链）往前找到符合自己 ReadView 的版本。

**关键点：Undo log 本身也受 redo log 保护。**

Undo log 是写在 `ibdata1` 或独立的 undo tablespace（5.6+ 可分离，8.0 默认两个独立 undo tablespace `undo_001`/`undo_002`）里的。修改 undo log 的操作同样产生 redo log record（类型为 `MLOG_UNDO_*`）。这意味着：

- 事务回滚所需的 undo 数据，在 crash 后可以从 redo log 恢复出来
- Crash recovery 完成后，InnoDB 能继续执行未完成事务的回滚

这个特性保证了 crash recovery 的完整性：redo 恢复数据页，undo 恢复事务中间状态，两者缺一不可。

```sql
-- 查看 undo tablespace
SELECT * FROM information_schema.INNODB_TABLESPACES WHERE NAME LIKE 'innodb_undo%';
-- 8.0+ 查看 undo 大小
SHOW STATUS LIKE 'Innodb_undo_tablespaces%';
```

### 3.5 Binlog：三格式 + sync_binlog

Binlog 在 **Server 层**，所有存储引擎共用（InnoDB、MyISAM、Memory……都写同一套 binlog）。提交事务后，binlog 写完才能给客户端返回成功。

#### 三种格式

```sql
SHOW VARIABLES LIKE 'binlog_format';
SET GLOBAL binlog_format = 'ROW';  -- 动态可改（重启失效；持久化写到 my.cnf）
```

| 格式        | 记录内容                                     | 优点                               | 缺点                                                                   | 适用场景                        |
|-------------|----------------------------------------------|------------------------------------|------------------------------------------------------------------------|---------------------------------|
| `STATEMENT` | 原始 SQL 语句                                | 日志量小，可读性强                 | `NOW()`、`UUID()`、`RAND()` 等函数在主从上执行结果不同 → 数据不一致    | 只读简单 SQL、无不确定函数       |
| `ROW`       | 每一行的变化（前镜像 + 后镜像）              | 精确可靠，复制不会有歧义           | 日志量大，ALTER TABLE 可能产生海量日志                                  | **生产默认推荐**（MySQL 8.0 默认）|
| `MIXED`     | 默认用 STATEMENT，含不确定函数时自动转 ROW   | 兼顾大小和安全                     | 不够透明，部分边界场景仍可能不一致；无法识别所有系统变量               | 旧版本兼容场景                  |

> 注意：RC（READ COMMITTED）或 RU（READ UNCOMMITTED）隔离级别下，**禁止使用 STATEMENT 格式**（MySQL 会报错拒绝写入）。这是因为 RC 下没有 gap lock，STATEMENT 格式在从库回放时可能遗漏行。

#### sync_binlog 三档对比

控制 binlog 写磁盘的策略：

| 值    | 行为                                                              | 持久性                                       | 性能   |
|-------|-------------------------------------------------------------------|----------------------------------------------|--------|
| `0`   | 由操作系统决定何时 fsync（不主动调 fsync）                        | OS crash 可能丢 binlog                       | 最高   |
| `1`   | 每次 commit 都 fsync binlog（默认值，8.0 起）                     | 最安全，与 `innodb_flush_log_at_trx_commit=1` 配合保证双重持久化 | 最低   |
| `N>1` | 每 N 次 commit 做一次 fsync                                       | 两次 fsync 之间 OS crash 最多丢 N 个事务的 binlog | 中等  |

```sql
SHOW VARIABLES LIKE 'sync_binlog';
-- 高安全生产环境：sync_binlog=1 + innodb_flush_log_at_trx_commit=1（双一配置）
-- 高性能写入（可接受少量丢失）：sync_binlog=100 + innodb_flush_log_at_trx_commit=2
```

#### Binlog 文件管理

```sql
-- 查看当前 binlog 文件列表
SHOW BINARY LOGS;

-- 查看当前写入的 binlog 文件
SHOW MASTER STATUS;

-- 手动切换到新文件（用于清理）
FLUSH BINARY LOGS;

-- 自动过期（默认 30 天）
SHOW VARIABLES LIKE 'binlog_expire_logs_seconds';
-- 8.0 以前是 expire_logs_days；8.0+ 改为 binlog_expire_logs_seconds（默认 2592000 = 30天）
```

### 3.6 两阶段提交完整时序

#### 为什么需要两阶段提交

假设没有两阶段提交，提交顺序有两种可能，两种都不对：

**情况 A：先写 redo log commit，再写 binlog**

```
redo commit ✓ → crash → binlog 未写
```
重启后：InnoDB 认为事务已提交，但从库没有这条 binlog → 主从不一致。

**情况 B：先写 binlog，再写 redo log commit**

```
binlog ✓ → crash → redo commit 未写
```
重启后：InnoDB 认为事务未提交（会回滚），但从库已执行了 binlog → 主从不一致。

**两阶段提交的解法**：在 redo log 里引入 **prepare** 状态，让 binlog 的存在与否成为判断提交与回滚的唯一依据。

#### 完整时序图

```
事务执行阶段
──────────────
  │  写 undo log（redo-logged）
  │  修改 buffer pool 页（redo-logged，写入 redo log buffer）
  │
  │  (可能多个 DML，持续写 redo buffer)
  │
提交阶段（两阶段提交）
──────────────────────
  │
  ├─── [Phase 1: Prepare]
  │     InnoDB 将 redo log buffer 写入 redo log 文件
  │     写入 prepare 标记（含事务 XID）
  │     fsync redo log 文件
  │           ↓
  ├─── [Write Binlog]
  │     Server 层将 binlog cache 写入 binlog 文件
  │     fsync binlog 文件（sync_binlog=1 时）
  │           ↓
  ├─── [Phase 2: Commit]
  │     InnoDB 在 redo log 写入 commit 标记
  │     （有 group commit 时，多个事务的 commit fsync 合并）
  │
  └─── 返回客户端 OK
```

#### XID：绑定 redo 和 binlog 的纽带

两阶段提交的判断依据是 **XID（事务 ID）**：每个事务的 redo log prepare 记录和 binlog 记录里都含同一个 XID。Crash recovery 时，扫描 redo log 找到所有 prepare 状态的事务，再去 binlog 里查找对应 XID——找到则 commit，找不到则 rollback。

#### Crash Recovery 决策表

| Redo Log 状态         | Binlog 中是否有该事务的完整记录 | 处理方式                      |
|-----------------------|---------------------------------|-------------------------------|
| 无 prepare 标记       | —                               | 丢弃（事务还未进入提交流程）  |
| prepare，binlog 不完整 | 否（写入中途崩溃）             | **回滚**                      |
| prepare，binlog 完整  | 是                              | **重做（提交）**              |
| commit 标记存在       | —                               | 正常已提交，应用 redo 即可    |

这个设计保证：以 **binlog 为最终裁判**，主库重启后的状态和 binlog 中记录的状态始终一致，从库按 binlog 回放也始终与主库一致。

### 3.7 组提交 Group Commit

#### 背景：两阶段提交的性能瓶颈

`innodb_flush_log_at_trx_commit=1 + sync_binlog=1`（双一配置）每次提交都有两次 fsync（redo + binlog），高并发下 IOPS 成为瓶颈。

#### Group Commit 的思路

把多个**并发提交**的事务，在同一次 fsync 里打包写入磁盘。

MySQL 5.6 引入了 **binlog group commit**，5.7 进一步引入 **BLGC（Binary Log Group Commit）** 和 **MTS（Multi-Threaded Slave）** 配合。

**三阶段管道**：

```
                事务 T1 ─┐
                事务 T2 ─┤─ Flush Stage ──→ Sync Stage ──→ Commit Stage
                事务 T3 ─┘

Flush Stage: 各事务将 binlog cache 写入 OS page cache，组成 queue
Sync Stage:  queue 里的事务统一做一次 fsync（组里越多，每个事务平摊的 IO 代价越低）
Commit Stage: 按顺序在 redo log 写 commit 标记
```

**关键参数（控制等待窗口）**：

```sql
-- 等多少微秒后才触发 sync（等待更多事务加入队列）
SHOW VARIABLES LIKE 'binlog_group_commit_sync_delay';
-- 默认 0（不等）；可设 100~1000 微秒在高并发下换更大的 group

-- 等到多少个事务才触发 sync（0 表示不限）
SHOW VARIABLES LIKE 'binlog_group_commit_sync_no_delay_count';
```

> 权衡：`binlog_group_commit_sync_delay` 增大会略微增加单个事务的提交延迟，但在高并发写入时能大幅减少 fsync 次数，提升总吞吐。

#### 组提交效果可量化

```sql
-- 查看 binlog fsync 次数
SHOW GLOBAL STATUS LIKE 'Binlog_commits';
SHOW GLOBAL STATUS LIKE 'Binlog_group_commits';
-- 如果 Binlog_commits >> Binlog_group_commits，说明 group 很大，每次 fsync 打包了很多事务
```

### 3.8 Crash Recovery 流程

#### 启动时自动执行

MySQL/InnoDB 重启后，crash recovery 是第一件事，完成前不接受连接。

**完整流程：**

```
1. 扫描 redo log
   └─ 从最近一次 checkpoint LSN 开始，重放所有 redo log record
      （不管事务是否提交，只要 redo 在，先应用到 buffer pool / 数据页）

2. 确认事务状态
   └─ 找到所有"prepare 但没有 commit 标记"的事务（XID 列表）

3. 对照 binlog
   └─ 用 XID 在 binlog 中查找
      ├─ binlog 里有这条事务（完整）→ 该事务应该提交 → 在 redo log 补写 commit，确认提交
      └─ binlog 里没有这条事务   → 该事务应该回滚 → 执行 undo log 回滚

4. 清理 undo log
   └─ 已确定回滚的事务，后台线程清理 undo log 和 undo tablespace

5. 恢复完成，开放连接
```

#### 重要细节

- **第 1 步是"无脑重放"**：redo log 的应用是幂等的（同一条 redo record 应用多次结果一样），所以先应用再判断状态是安全的。
- **大事务 crash 后 rollback 可能很慢**：如果有一个修改了百万行的事务崩了，undo log 回滚需要时间，期间数据库已经可接受连接，但该部分数据上有未决事务——其他事务读时会看到历史版本（MVCC 保证）。
- **purge 线程**：已提交事务的 undo log 不是立刻删的，而是等"没有任何活跃事务还在读这个版本"后，由 purge 线程清理。

### 3.9 8.0.30+ Redo Log 配置变化

#### 新旧参数对照

| 项目               | 8.0.29 及以前                                                      | 8.0.30+                                        |
|--------------------|--------------------------------------------------------------------|------------------------------------------------|
| 文件数量           | `innodb_log_files_in_group`（默认 2）                              | 自动管理（32 个小文件，每个 ~3MB，总大小受容量控制） |
| 单文件大小         | `innodb_log_file_size`（默认 48MB）                                | 弃用（设置会有警告）                           |
| 总容量             | `innodb_log_files_in_group × innodb_log_file_size`（默认 96MB）    | `innodb_redo_log_capacity`（默认 100MB）        |
| 是否支持在线 resize | 否，需重启                                                         | **是**，`SET GLOBAL` 立即生效                  |
| 文件命名           | `ib_logfile0`, `ib_logfile1`                                       | `#ib_redo0` ~ `#ib_redo31`（在 `#innodb_redo/` 目录下） |

#### 在线扩容（8.0.30+）

```sql
-- 查看当前容量
SHOW VARIABLES LIKE 'innodb_redo_log_capacity';

-- 在线扩容到 4GB（无需重启）
SET GLOBAL innodb_redo_log_capacity = 4294967296;

-- 持久化（写入 my.cnf）
-- [mysqld]
-- innodb_redo_log_capacity = 4294967296
```

#### 为什么要改

旧的 2 文件模式在高并发写入时，checkpoint 推进不均匀，容易造成 write stall。新的 32 个小文件设计让 checkpoint 可以更细粒度推进，减少停顿；同时支持在线 resize，运维操作更安全。

## 4. 日常开发应用

**写入密集型服务上线前检查清单：**

1. **确认双一配置**（高安全）或明确接受数据丢失的窗口：
   ```sql
   SHOW VARIABLES LIKE 'innodb_flush_log_at_trx_commit';  -- 期望: 1
   SHOW VARIABLES LIKE 'sync_binlog';                      -- 期望: 1
   ```

2. **评估 redo log 容量是否足够**：
   - `SHOW ENGINE INNODB STATUS\G` 看 `Checkpoint age` vs `Max checkpoint age`
   - Checkpoint age / Max checkpoint age > 75% 时，写入开始被限速；接近 100% 就会 write stall
   - 经验：OLTP 写入峰值 TPS > 5000 时，考虑把 redo log 容量调到 2~4GB

3. **binlog 格式确认**（复制环境必须）：
   ```sql
   SHOW VARIABLES LIKE 'binlog_format';  -- 期望: ROW
   ```
   用 RC 隔离级别的服务，STATEMENT 格式会直接报错，务必提前排查。

4. **大批量写入（如数据迁移）的特殊处理**：
   - 拆小事务（每批 1000 行）而不是一个大事务，避免 undo log 暴涨 + redo log 写满
   - 如果是只读迁移目标库可接受少量丢失，临时 `set session innodb_flush_log_at_trx_commit=2` 提速

5. **主从延迟排查时看 binlog 位点**：
   ```sql
   -- 主库
   SHOW MASTER STATUS;
   -- 从库
   SHOW REPLICA STATUS\G
   -- 关注 Seconds_Behind_Source / Exec_Master_Log_Pos vs Read_Master_Log_Pos
   ```

## 5. 调优实战

### Case A：「binlog 太大，磁盘快撑不住了」

**症状**：`/var/lib/mysql` 磁盘占用持续增长，`SHOW BINARY LOGS` 看到 binlog 文件越来越多。

**排查步骤**：

```sql
-- 查看 binlog 自动过期设置
SHOW VARIABLES LIKE 'binlog_expire_logs_seconds';
-- 默认 2592000（30天），如果磁盘紧张可以降低
SET GLOBAL binlog_expire_logs_seconds = 604800;  -- 改为 7 天

-- 手动清理（删除指定文件之前的所有 binlog）
PURGE BINARY LOGS TO 'binlog.000123';
-- 或按时间
PURGE BINARY LOGS BEFORE '2026-05-01 00:00:00';
```

**注意**：删 binlog 前，先确认从库的复制进度 `SHOW REPLICA STATUS\G`，不要删从库还没消费的 binlog，否则主从断开需要重新全量同步。

**根治方案**：
- binlog 挂载到单独的磁盘分区
- 如果因 ROW 格式 + `ALTER TABLE` 产生海量 binlog，考虑在从库 `binlog_row_image=MINIMAL`（只记有变化的列），但注意这会影响 Flashback 工具的使用

### Case B：「innodb_flush_log_at_trx_commit 怎么权衡」

**决策框架**：

```
是否是金融/订单类核心数据？
├─ 是 → 只考虑 1（双一配置），性能不足就加 SSD 或做 group commit 优化
└─ 否 → 能接受最多丢失多少数据？
         ├─ 一个实际 flush 间隔内的写入，且只接受 OS/断电风险 → 可评估 2
         └─ 连 mysqld crash 也允许丢最近写入 → 才评估 0（通常只适合测试或可重建数据）
```

**性能判断不能套固定倍数**：收益取决于设备 `fsync` 延迟、并发提交数、binlog 配置和工作负载。高并发下先观察 Group Commit 是否已把多个事务合并进一次 `fsync`，再用同硬件、同持久性要求压测 `0/1/2`；不要拿放松持久性的结果直接与 `1` 比较后宣称数据库优化完成。

### Case C：「怎么用 mysqlbinlog 找误删数据」

**背景**：`DELETE FROM orders WHERE status='cancelled'` 误删了 10 万条。

**步骤**：

```bash
# 1. 确认误操作发生的时间点（从慢查询日志/general log 找）
# 假设是 2026-05-13 14:30 左右

# 2. 找到对应的 binlog 文件
mysql -e "SHOW BINARY LOGS;"
# 根据大小和时间判断，假设是 binlog.000456

# 3. 解析 binlog（ROW 格式需要加 --base64-output=DECODE-ROWS -v）
mysqlbinlog --base64-output=DECODE-ROWS -v \
  --start-datetime="2026-05-13 14:00:00" \
  --stop-datetime="2026-05-13 15:00:00" \
  /var/lib/mysql/binlog.000456 > /tmp/binlog_extract.sql

# 4. 在 /tmp/binlog_extract.sql 里找 DELETE 操作
grep -A 20 "DELETE FROM \`orders\`" /tmp/binlog_extract.sql

# 5. ROW 格式的 binlog 记录了删除前的行镜像（### @1=... 等）
#    手动或用 binlog2sql 工具生成反向 INSERT
# pip install binlog2sql
binlog2sql --flashback \
  -h 127.0.0.1 -u root -p \
  --start-datetime="2026-05-13 14:25:00" \
  --stop-datetime="2026-05-13 14:35:00" \
  -d orders_db -t orders \
  > /tmp/rollback.sql

# 6. 在测试环境验证后，在生产库执行 rollback.sql
```

> 关键前提：`binlog_format=ROW` 且 binlog 文件还没被 purge。如果 binlog_format=STATEMENT，只能记录 SQL，无法自动生成反向操作，数据恢复会复杂得多——这也是 ROW 格式的重要价值之一。

### Case D：「Redo Log write stall，写入突然变慢」

**排查**：
```sql
SHOW ENGINE INNODB STATUS\G
-- 找 LOG 段：
-- Log sequence number: 2412803265
-- Log flushed up to:   2412803265
-- Last checkpoint at:  2398620351     ← checkpoint 落后了
-- Checkpoint age:      14182914       ← 距 max checkpoint age 还剩多少
```

```sql
-- 看 max checkpoint age
SHOW VARIABLES LIKE 'innodb_log%';
-- max checkpoint age ≈ redo log 总容量 × 0.9
-- 如果 checkpoint age 接近 max，说明脏页刷不过来
```

**处理**：
1. 短期：临时增大 `innodb_redo_log_capacity`（8.0.30+ 在线修改）
2. 根本：增大 `innodb_io_capacity` 和 `innodb_io_capacity_max`，让 InnoDB 更激进地刷脏页；或升级磁盘 IOPS

## 6. 面试高频考点

### 必考题 1：redo log 和 binlog 的区别

| 维度             | Redo Log                           | Binlog                                      |
|------------------|------------------------------------|---------------------------------------------|
| 属于哪一层       | InnoDB 引擎层                      | MySQL Server 层                             |
| 日志类型         | 物理日志（记页的字节变化）         | 逻辑日志（记 SQL 或行变化）                  |
| 用途             | Crash Recovery，WAL 性能优化       | 主从复制，时间点恢复，审计                   |
| 写入方式         | 循环写（固定大小，可覆盖）         | 追加写（不断增长，过期才删）                 |
| 是否所有引擎共用 | 否（InnoDB 独有）                  | 是（所有引擎）                              |
| 事务提交时机     | prepare 阶段 fsync                 | prepare 之后、commit 之前 fsync             |

**三句话答法**：

1. Redo 是 InnoDB 引擎层的物理日志，记"某页某偏移写了什么字节"，循环写，用于 crash recovery 和 WAL 性能。
2. Binlog 是 Server 层的逻辑日志，所有引擎共用，追加写，用于主从复制和备份恢复。
3. 两者通过两阶段提交协调，以 binlog 为最终裁判保证一致性。

### 必考题 2：为什么需要两阶段提交

**一句话**：为了保证 redo log 和 binlog 的状态一致，避免主库重启后的状态与从库不同步。

**展开**：如果只有一个日志，就不存在不一致问题。MySQL 既要用 redo log 做 crash recovery（InnoDB 层），又要用 binlog 做复制（Server 层），两个日志都要写，就必须有协议保证"要么都写成功，要么都没写成功"。两阶段提交借鉴了分布式事务的 2PC 思路，以 binlog 完整性为判断依据。

### 必考题 3：WAL 是什么，为什么能提升性能

Write-Ahead Logging：数据页写出前，对应 redo 必须先持久化。它没有消灭最终的数据页随机写；它把提交关键路径换成连续 redo 写，并通过 Group Commit、同页修改合并和后台并行刷脏提升吞吐。若更新命中大量不同页，最终仍要逐页刷出，稳态瓶颈仍可能回到数据页 IOPS。

### 必考题 4：Crash 后怎么恢复

1. 从最近的 checkpoint LSN 开始，重放 redo log，把所有记录的修改应用到数据页（无论事务是否提交）。
2. 找到所有 redo log 里处于 prepare 状态（有 prepare 标记，无 commit 标记）的事务 XID。
3. 对照 binlog 逐个查：binlog 里有该 XID → 提交；binlog 里没有 → 回滚。
4. 清理 undo log，开放连接。

### 必考题 5：innodb_flush_log_at_trx_commit 三档

- `0`：commit 不等待 write 或 fsync；后台按 timeout 处理，进程 crash 也可能丢最近写入。
- `1`：commit 等 `flushed_to_disk_lsn`，即等 `fsync` 完成；默认、完整持久化配置。
- `2`：commit 等 `write_lsn`，即 redo 已交给 OS，但不等 `fsync`；OS crash 或断电可能丢最近一个实际 flush 间隔。

### 易错点

- **"redo log 是追加写"（错）**：redo log 是**循环写**，满了会覆盖旧内容（前提是 checkpoint 已推进）。binlog 才是追加写（持续增长）。
- **"undo log 不受 redo 保护"（错）**：undo log 的修改同样产生 redo log record，crash 后 undo log 也能恢复，确保回滚能继续完成。
- **"两阶段提交是分布式系统才需要的"（误区）**：单机 MySQL 内部，redo log（引擎层）和 binlog（Server 层）也是两个独立组件，需要 2PC 协调。
- **"binlog_format=ROW 一定更占空间"**：通常是的，但 `binlog_row_image=MINIMAL` 可以只记有变化的列，大幅减少 ROW 格式的空间占用（代价是 Flashback 工具功能受限）。

## 7. 一句话总结

InnoDB 靠 **Redo Log（物理，循环写）** 保证 crash 后已提交数据不丢，靠 **Undo Log（逻辑，受 redo 保护）** 保证事务可回滚 + MVCC 历史版本；**Binlog（逻辑，Server 层，追加写）** 是主从复制和时间点恢复的剧本。三者通过**两阶段提交**绑定——prepare → binlog fsync → commit——以 binlog 完整性为唯一裁判，保证崩溃重启后主从状态严格一致。生产首选"双一配置"（`innodb_flush_log_at_trx_commit=1` + `sync_binlog=1`），用 Group Commit 摊薄 fsync 代价。

## Scenarios

> 本机实测（MySQL 8.0.36），每个都跑过「预期 → 实机 → 落差」。

- [01 - redo LSN 推进 + checkpoint 滞后](scenarios/01-redo-lsn-and-checkpoint-age.md) — 灌 1 万更新看 LSN 涨 5.6MB、checkpoint 纹丝不动，亲眼看到 WAL 的两条进度线分叉
- [02 - binlog ROW vs STATEMENT 体积对比](scenarios/02-binlog-row-vs-statement-size.md) — 同样改 1 万行，STATEMENT 339 字节、ROW 477940 字节（≈1409 倍）
