# InnoDB 存储引擎

## 1. 核心问题

InnoDB 是 MySQL 默认存储引擎，几乎所有生产场景都在用它。但很多人只会说「它支持事务、有 Buffer Pool」，说不清机制。本章解决四件事：
**(a)** 数据在磁盘上怎么组织（页 / 区 / 段 / 表空间四层结构，每层的具体尺寸）；
**(b)** Buffer Pool 怎么工作，里面的三条链表分别管什么，改良 LRU 为什么要分 young / old；
**(c)** Change Buffer / Adaptive Hash Index / Doublewrite 三个组件解决什么问题；
**(d)** 面试和调优中，这些机制怎么对应到实际数字和 SQL。

## 2. 直觉理解

把 InnoDB 想成一个巨大的**仓库系统**：

- **磁盘** = 仓库地库（便宜但存取慢）
- **页 16KB** = 仓库里每个货架的最小装卸单元，每次搬运都以货架为单位，不会搬半个货架
- **区 1MB（64 页）** = 一排货架，InnoDB 申请空间时以整排为单位，目的是减少碎片化和随机 IO
- **段** = 按用途划分的仓区（叶子节点区、非叶子节点区、回滚段区……）
- **Buffer Pool** = 工作台（内存），工人只能在工作台上干活；从地库拿页、用完放回去，工作台装满了就按 LRU 规则决定哪个货架先还回地库
- **改良 LRU（young + old）** = 工作台上有两块区域：常驻区（young）放真正频繁用的，预热区（old）放新拿来还不确定的。全表扫描来一堆页也只会堆在预热区，冲不掉常驻热点——这是防抖设计
- **Change Buffer** = 暂存台（针对二级索引）：如果二级索引页现在不在 Buffer Pool 里，先把变更记录到 Change Buffer，等这页下次被读进来时再合并，省掉了一次随机 IO
- **Doublewrite** = 草稿纸：写 16KB 页到磁盘前先完整抄一遍到 doublewrite buffer（连续空间），再写到实际位置。即使写到一半掉电（partial write），还能从草稿恢复

## 3. 原理深入

### 3.1 页 / 区 / 段 / 表空间四层

```
表空间（Tablespace）
└── 段（Segment）           ← 逻辑概念，无固定字节大小
    └── 区（Extent）= 1MB  ← 64 个连续的页
        └── 页（Page）= 16KB ← 最小存取单元
```

**页（Page）**

InnoDB 最小 I/O 单位是页，默认 `innodb_page_size = 16384 bytes（16KB）`。可选值：4KB / 8KB / 16KB / 32KB / 64KB。一旦初始化数据目录就不可更改，生产几乎不改（32KB / 64KB 适合 BLOB 密集型，但行数会减少）。

**区（Extent）**

64 个连续页 = 1MB。InnoDB 为段申请磁盘空间时以区为单位（当段内已有 32 个碎片页时才升级到整区分配），目的：减少碎片、让顺序 IO 成立。对应到 OS 层，操作系统预读（read-ahead）也更容易命中。

**段（Segment）**

段是逻辑概念，没有固定的字节大小。每个索引会分配两个段：叶子节点段（leaf node segment）和非叶子节点段（non-leaf node segment）。另有回滚段（undo segment）和专门的 LOB 段等。段的意义是让不同用途的数据在物理上尽量相邻，减少 B+ 树叶子节点的随机 IO。

**表空间（Tablespace）**

MySQL 8.0 默认 `innodb_file_per_table=ON`，每张表一个 `.ibd` 文件，就是一个独立表空间。系统表空间 `ibdata1` 保留 undo log（部分）、double write buffer（8.0.20 之前）、change buffer 等全局数据。共享表空间可以用 `CREATE TABLESPACE` 手工管理。

```sql
-- 查看各表占用的表空间大小（单位 MB）
SELECT
  table_schema,
  table_name,
  ROUND((data_length + index_length) / 1024 / 1024, 2) AS total_mb,
  ROUND(data_length / 1024 / 1024, 2) AS data_mb,
  ROUND(index_length / 1024 / 1024, 2) AS index_mb
FROM information_schema.tables
WHERE table_schema = 'your_db'
ORDER BY total_mb DESC
LIMIT 10;
```

---

### 3.2 一页 16KB 里到底装了什么

InnoDB 数据页（`FIL_PAGE_INDEX`，类型值 `0x45BF`）的内部结构：

```
┌──────────────────────────────────────┐  ← 偏移 0
│  File Header          (38 字节)       │  checksum / 页号 / 上下页指针 / LSN / 页类型
├──────────────────────────────────────┤
│  Page Header          (56 字节)       │  槽数量 / 堆顶指针 / 记录数 / 上次修改事务 ID 等
├──────────────────────────────────────┤
│  Infimum + Supremum   (26 字节)       │  两条虚拟记录，是本页记录链表的边界哨兵
├──────────────────────────────────────┤
│  User Records         (变长)          │  实际行数据，按主键顺序的单向链表
├──────────────────────────────────────┤
│  Free Space           (变长)          │  未使用空间，从 User Records 末尾到 Page Directory 之间
├──────────────────────────────────────┤
│  Page Directory       (变长)          │  槽数组（每槽 2 字节），每 4-8 条记录一个槽，支持二分查找
├──────────────────────────────────────┤
│  File Trailer         (8 字节)        │  末尾 checksum（用于校验 File Header checksum 一致性）
└──────────────────────────────────────┘  ← 偏移 16383
```

关键细节：

- **File Header（38B）**：头 4 字节是 checksum，紧跟 4 字节页号，然后 4+4 字节上/下页号（双向链表，支持叶子层顺序扫描），8 字节 LSN，2 字节页类型，8 字节 Flush LSN（仅系统页），4 字节 space ID。
- **Page Directory**：把页内记录分组，每组 4-8 条，每组最后一条记录的偏移写入目录槽。查找时先二分槽（O(log n)），再在组内线性扫（最多 7 次比较），比纯链表扫描快得多。
- **记录头（5 字节）**：每行真实数据前有 5 字节 record header，包含 `delete_mask`（逻辑删除位）、`n_owned`（该组条数）、`next_record` 偏移（15 位），以及一个用于索引节点层次管理的 `min_rec_mask`。
- **行格式**：MySQL 8.0 默认 `DYNAMIC`（5.7 默认 `COMPACT`）。DYNAMIC 对超过页 1/2 的 BLOB/TEXT 完全存溢出页（off-page），页内只留 20 字节指针；COMPACT 则保留前 768 字节在页内。

---

### 3.3 Buffer Pool 三大链表（free / LRU / flush）

**Buffer Pool 基本参数**

```sql
SHOW VARIABLES LIKE 'innodb_buffer_pool%';
```

典型输出（8.0 默认值）：

```
+-------------------------------------+----------------+
| Variable_name                       | Value          |
+-------------------------------------+----------------+
| innodb_buffer_pool_chunk_size       | 134217728      |  ← 128MB，每个 chunk
| innodb_buffer_pool_dump_at_shutdown | ON             |
| innodb_buffer_pool_dump_pct         | 25             |  ← 关机时 dump 最热的 25%
| innodb_buffer_pool_filename         | ib_buffer_pool |
| innodb_buffer_pool_instances        | 8              |  ← 8 个实例（默认 ≥1GB 时）
| innodb_buffer_pool_load_at_startup  | ON             |
| innodb_buffer_pool_size             | 134217728      |  ← 128MB（生产要改！）
+-------------------------------------+----------------+
```

**生产建议**：`innodb_buffer_pool_size` 设为物理内存的 50-75%（OS 和连接线程也需要内存）。8GB 内存的机器设 4-6GB；32GB 设 20-24GB。

**Buffer Pool 按页管理**：128MB ÷ 16KB = 8192 个缓存帧（frame）。每个帧对应一个**控制块（control block）**，存储：所属表空间 ID、页号、当前状态（free / clean / dirty）、所在 LRU 和 flush list 的位置、latch 等，大约 800 字节/帧，总控制块区约 50MB（占实际申请内存的 5-8%，这也是为什么 `SHOW ENGINE INNODB STATUS` 里显示的 Buffer Pool size 会比配置值略少）。

**三大链表**

| 链表 | 含义 | 新增时机 | 移除时机 |
|---|---|---|---|
| **free list** | 空闲帧队列 | 初始化 / flush 完一帧后放回 | 读入新页时从这里取帧 |
| **LRU list** | 所有「已使用」帧，按冷热排序 | 页第一次被读入 | 被淘汰（写回磁盘或直接丢弃） |
| **flush list** | 所有脏页（内存已改、磁盘未改） | 页第一次被修改（DML） | 页刷到磁盘后移回 LRU clean 或 free |

**IO 路径**：

1. SQL 要读某页 → 先查 Buffer Pool hash（space_id + page_no → frame）。
2. 命中（Buffer Pool hit）：直接从内存返回，不碰磁盘。
3. 未命中（Buffer Pool miss）：
   - 从 free list 拿一个空闲帧；如果 free list 空了，从 LRU 尾部淘汰一帧（若为脏页，先异步刷盘）。
   - 从磁盘读该页填入帧，插入 LRU 特定位置（见 §3.4）。
4. 写操作（INSERT/UPDATE/DELETE）：修改 Buffer Pool 里的帧，标记为脏页，加入 flush list；redo log 保证持久化（ch07 详述）。

---

### 3.4 改良 LRU（young + old + midpoint）解决了什么

**原始问题**：纯 LRU 在全表扫描时会把所有页都读进来，依次变成「最近使用」，把原本的热点页（如小表、高频查询的索引根页）全部挤到尾部淘汰。全表扫完，Buffer Pool 里全是冷数据，热点数据要重新预热，代价极高。

**改良方案：midpoint insertion strategy**

```
        young 区（热）           old 区（冷）
 ┌──────────────────────┐  ┌─────────────────┐
 │ head ← 最近访问      │  │ 新读入页 → tail  │
 └──────────────────────┘  └─────────────────┘
        约 5/8 的 LRU          约 3/8 的 LRU
                    ↑ midpoint（5/8 处）
```

关键参数与行为：

```sql
SHOW VARIABLES LIKE 'innodb_old_blocks%';
-- innodb_old_blocks_pct  = 37  （old 区占 LRU 的 37%，约 3/8）
-- innodb_old_blocks_time = 1000（毫秒，页在 old 区停留超过 1s 才能晋升 young）
```

**全表扫描场景**：新读入的页只放 old 区头部；如果扫描速度快（远小于 1s 就扫完一页），页永远不会晋升 young，扫完后整批页被淘汰。热点页稳居 young 区，不受影响。

**正常访问场景**：某页被读入 old 区后，1 秒后又被访问，晋升 young 区头部，后续访问反复刷新到头，常驻 young 区。

**young 区内部优化**：为避免每次访问都移动指针（高并发下链表操作有 latch 竞争），young 区前 1/4 内的页被再次访问时不移动（已经够热了）。只有在 young 后 3/4 的页被访问才真正移到头部。

**查看 Buffer Pool 命中率**：

```sql
SELECT * FROM information_schema.INNODB_BUFFER_POOL_STATS\G
```

典型输出关键字段：

```
*************************** 1. row ***************************
                 POOL_ID: 0
               POOL_SIZE: 8192          ← 本实例管理的页数（128MB / 16KB）
            FREE_BUFFERS: 0             ← free list 里的空闲帧数，生产跑满时接近 0
          DATABASE_PAGES: 7942          ← LRU list 上的页数
      OLD_DATABASE_PAGES: 2929          ← old 区的页数（约 37%）
 MODIFIED_DB_PAGES: 431                 ← flush list 上的脏页数
        PENDING_READS: 0
   PENDING_FLUSH_LRU: 0
  PENDING_FLUSH_LIST: 0
       PAGES_MADE_YOUNG: 1284732        ← 从 old 晋升 young 的累计次数
   PAGES_NOT_MADE_YOUNG: 3920481        ← 未晋升（全表扫等场景）的累计次数
 PAGES_MADE_YOUNG_RATE: 12.50          ← 近期晋升速率（次/秒）
     HIT_RATE: 998                      ← 命中率 998/1000，即 99.8%（生产要 > 99%）
```

命中率公式：`HIT_RATE = (读请求 - 物理读) / 读请求 * 1000`。低于 990（99%）时需要加大 `innodb_buffer_pool_size`。

---

### 3.5 Change Buffer：写优化的精髓

**背景**：INSERT/UPDATE/DELETE 修改行时，不仅要改聚簇索引，还要改所有**二级索引**。聚簇索引页大概率已在 Buffer Pool（因为主键经常被访问），但二级索引页未必在 Buffer Pool 里，直接写需要先从磁盘随机读入再修改——这是写放大的根源。

**Change Buffer 的解法**：如果二级索引页**不在** Buffer Pool 里，把这次变更（增/删/改）暂存到 Change Buffer（位于 Buffer Pool 内的一块专用区域，也会持久化到 `ibdata1`），不立即做随机 IO。等该页**被读入 Buffer Pool**（下次有人访问），再把积压的变更合并（merge）进去，变成「批量随机 IO → 一次顺序写」。

**Change Buffer 的适用条件**（同时满足才生效）：

1. 操作是 INSERT / UPDATE / DELETE（非 SELECT）
2. 操作的是**二级索引**（不是聚簇索引）
3. 二级索引页**当前不在** Buffer Pool
4. 索引**不是唯一索引（UNIQUE）**——因为唯一索引在 INSERT 时必须立即读入页做唯一性校验，无法缓冲

```sql
SHOW VARIABLES LIKE 'innodb_change_buffer%';
-- innodb_change_buffer_max_size = 25  （Change Buffer 最大占 Buffer Pool 的 25%）
-- innodb_change_buffering = all       （buffer inserts / deletes / purges，默认 all）
```

**merge 的时机**（以下任一）：

- 该二级索引页被读入 Buffer Pool（SELECT / 范围扫描触发）
- Master thread 定期合并（每秒或每 10 秒一次，视负载调整）
- Buffer Pool 空间不足，淘汰某帧前先合并
- MySQL 正常关闭时

**什么时候 Change Buffer 帮不上忙（甚至该关）**：

- 表上几乎全是唯一索引 → 无法缓冲，占用 Buffer Pool 空间浪费
- 大量随机读后立刻查这些数据（写完马上查）→ merge 频繁，收益低
- SSD 机器上随机 IO 代价已经很低 → Change Buffer 带来的 IO 合并收益缩小；部分场景下 `innodb_change_buffering=none` 反而更快（减少 merge 开销）

**查看 Change Buffer 状态**（在 `SHOW ENGINE INNODB STATUS\G` 里找 `INSERT BUFFER AND ADAPTIVE HASH INDEX` 段）：

```
-------------------------------------
INSERT BUFFER AND ADAPTIVE HASH INDEX
-------------------------------------
Ibuf: size 1, free list len 0, seg size 2, 12 merges
merged operations:
 insert 17, delete mark 5, delete 3
discarded operations:
 insert 0, delete mark 0, delete 0
```

`size`：Change Buffer B+ 树当前占用的页数。`merges`：累计发生的 merge 次数。`merged operations insert/delete mark/delete` 对应三种操作类型的合并量。

---

### 3.6 Adaptive Hash Index：B+ 树之上的额外缓存

**问题**：B+ 树查找某行需要从根往叶子走，高度 3 就是 3 次内存比较（页已在 Buffer Pool）。如果某个等值查询极其频繁（比如主键查询某个热点 ID），每次都走 B+ 树仍然有固定开销。

**AHI 的做法**：InnoDB 自动监控 B+ 树的访问模式。当发现某个索引前缀被频繁用于**等值查询**（内部阈值约为访问同一页 17 次，且连续 100 次访问中该前缀占比达到 1/16 以上），就为该模式在内存中建一个 Hash 表：`(index_id, index_prefix_value) → 叶子页指针`，下次相同查询直接一次 Hash 命中跳到叶子页，绕过了 B+ 树所有中间节点的比较。

关键约束：

- **只支持等值查询**（`=` 或 `IN`），不支持范围（`>`、`<`、`BETWEEN`）、排序、`LIKE`
- **自动构建自动失效**：行 DELETE、页分裂/合并、索引重建时对应 AHI 条目自动失效
- **不可手动控制**哪些索引建 AHI，由 InnoDB 自己决定

```sql
SHOW VARIABLES LIKE 'innodb_adaptive_hash_index%';
-- innodb_adaptive_hash_index         = ON
-- innodb_adaptive_hash_index_parts   = 8   （8 个分区，减少 latch 竞争）
```

**什么时候该关（`innodb_adaptive_hash_index=OFF`）**：

- 负载以范围扫描、ORDER BY 为主，AHI 命中率低但占内存（可在 `SHOW ENGINE INNODB STATUS` 的 `INSERT BUFFER AND ADAPTIVE HASH INDEX` 段看 `hash searches/s` vs `non-hash searches/s`）
- 高并发下出现 `RW-latch wait` 在 AHI 的内存地址上（即使 8 分区后仍然热的场景）——可先 `SET GLOBAL innodb_adaptive_hash_index=OFF` 在线关闭，观察吞吐变化
- Hash 搜索远少于非 Hash 搜索时，说明工作负载不适合 AHI

在 `SHOW ENGINE INNODB STATUS\G` 中观察：

```
Hash table size 34679, node heap has 1 buffer(s)
Hash table size 34679, node heap has 0 buffer(s)
...（8 个分区各一行）
0.00 hash searches/s, 0.50 non-hash searches/s
```

`hash searches/s` 明显低于 `non-hash searches/s` 时，AHI 对当前工作负载收益不大。

---

### 3.7 Doublewrite：为什么 redo log 不够

**问题根源：partial write（页撕裂）**

InnoDB 页 16KB，OS 和磁盘的物理写单位通常是 512 字节（或 4KB）。写一个 16KB 的页需要多次系统调用或 DMA 传输。如果中途掉电，磁盘上可能只写了 8KB，剩下 8KB 是旧数据——这叫 partial write / page tearing。这时候该页的 checksum 一定对不上（File Header 和 File Trailer 的 checksum 不匹配），InnoDB 知道这页损坏了。

**为什么 redo log 不能直接修复**：redo log 记录的是「对某页某偏移做了什么操作」（物理逻辑日志），它需要一个**基线完整页**来 replay。如果页本身撕裂了（是个半新半旧的混合状态），就找不到正确基线，redo 无法安全应用。

**Doublewrite 的解法**：

```
写脏页流程（简化）：

1. Page Cleaner 线程把脏页收集成一批（batch，默认 120 页）
2. 先顺序写到 doublewrite buffer（在 ibdata1 或独立文件里的 2MB 连续空间）
   → 2MB 对应 128 个 16KB 页，顺序写，一次 fsync
3. 再把这批页各自写到它们在表空间中的实际位置（随机写）
   → 写到一半掉电？没事，step 2 的副本还在
4. 崩溃恢复时：找到损坏页 → 从 doublewrite buffer 复制完整页副本 → 再重放 redo log
```

**代价**：每个页实际写了两次，写吞吐理论上减少约 5-10%（实际因为 step 2 是顺序 IO，代价远小于随机写，真实性能影响通常在 1-5% 之间）。

**MySQL 8.0.20+ 的变化**：Doublewrite buffer 从 `ibdata1` 移出到独立的 `#ib_16384_0.dblwr` 文件（在数据目录），大小配置更灵活：

```sql
SHOW VARIABLES LIKE 'innodb_doublewrite%';
-- innodb_doublewrite              = ON
-- innodb_doublewrite_dir          =        （空 = 数据目录）
-- innodb_doublewrite_files        = 2      （8.0.20+，每个 BP 实例 2 个文件）
-- innodb_doublewrite_pages        = 128    （每个文件存 128 页）
-- innodb_doublewrite_batch_size   = 0      （0 = 自动）
```

**什么时候可以关**（`innodb_doublewrite=OFF`）：

- 文件系统本身支持原子写（如 ZFS、某些 NVMe 固件），可以保证 16KB 写原子性
- 使用 MySQL 8.0 的 `innodb_page_size=4KB` + 底层 4K 扇区磁盘（写单位对齐，无 partial write）
- 极端性能压测场景（临时关闭，数据非生产）

---

### 3.8 后台线程

InnoDB 有多类后台线程，各司其职：

**Master Thread**

每秒和每 10 秒各执行一轮维护：

- 每秒：刷新 redo log buffer 到磁盘（即使未满），尝试合并 Change Buffer（自适应速率），最多刷 100 个脏页（视 IO 能力动态调整），清理无用 undo 段
- 每 10 秒：合并 Change Buffer（至多 5 个），刷新 100 个脏页，删除无用 undo log

**IO Thread**

使用 AIO（异步 IO）处理 read 和 write 请求：

```sql
SHOW VARIABLES LIKE 'innodb_%io_threads';
-- innodb_read_io_threads  = 4  （异步读线程，可调 1-64）
-- innodb_write_io_threads = 4  （异步写线程，可调 1-64）
```

读写线程各默认 4 个。IO 密集型场景（大量全表扫 / 批量导入）可以增加到 8-16。

**Purge Thread**

回收已提交事务留下的 undo log 和标记为删除的记录（物理删除）。默认 4 个线程：

```sql
SHOW VARIABLES LIKE 'innodb_purge_threads';
-- innodb_purge_threads = 4
```

高 DELETE / UPDATE 负载下，如果 `SHOW ENGINE INNODB STATUS` 里看到 `History list length` 持续增长（正常应 < 1000，高负载短暂到几千可接受，若持续 > 10000 说明 purge 跟不上），考虑增加 purge_threads 或检查是否有长事务阻塞 purge。

**Page Cleaner Thread**

专门负责把 flush list 里的脏页刷到磁盘（异步后台刷，区别于被动刷：当 free list 耗尽时由用户线程同步刷）：

```sql
SHOW VARIABLES LIKE 'innodb_page_cleaners';
-- innodb_page_cleaners = 4  （8.0 默认 4，对应 BP 实例数）
```

`innodb_page_cleaners` 建议等于 `innodb_buffer_pool_instances`，让每个 BP 实例都有一个专属 page cleaner。

**在 `SHOW ENGINE INNODB STATUS\G` 观察后台线程活动**

```sql
SHOW ENGINE INNODB STATUS\G
```

关注以下段落：

```
---
BACKGROUND THREAD
---
srv_master_thread loops: 1234 srv_active, 0 srv_shutdown, 5678 srv_idle
srv_master_thread log flush and writes: 6912
```

`srv_active` 高说明 master thread 一直忙（IO 压力大）；`srv_idle` 高说明系统空闲。

```
--------
FILE I/O
--------
I/O thread 0 state: waiting for completed aio requests (insert buffer thread)
I/O thread 1 state: waiting for completed aio requests (log thread)
I/O thread 2 state: waiting for completed aio requests (read thread)
...
Pending normal aio reads: [0, 0, 0, 0] , aio writes: [0, 0, 0, 0] ,
 ibuf aio reads:, log i/o's:, sync i/o's:
Pending flushes (fsync): 0
```

`Pending normal aio reads` 持续不为零说明读 IO 压力大，考虑加 `innodb_read_io_threads` 或加 Buffer Pool。

## 4. 日常开发应用

**建表 / 迁移时**

- `innodb_file_per_table=ON`（8.0 默认），方便单表 `OPTIMIZE TABLE` / `TRUNCATE` 释放空间，也便于物理备份和迁移
- 主键选自增整数（BIGINT UNSIGNED）：有序插入 = 页只在末尾分裂，减少碎片；UUID/随机主键 = 随机页分裂，碎片率高，Buffer Pool 命中率低
- 不要在列上建太多唯一索引（UNIQUE KEY）：唯一索引写入必须立即做唯一性校验，Change Buffer 完全失效；如果业务逻辑能保证唯一，用普通索引 + 代码逻辑更快

**日常写 SQL**

- 大批量 DELETE（百万行）：拆成小批（`DELETE ... LIMIT 1000`），避免一次性把 flush list 打满脏页，也减少长事务阻塞 purge
- 大批量 INSERT：批量 `INSERT INTO ... VALUES (...),(...),...`（每批 500-1000 行），减少行锁获取次数和 redo log flush 频率
- `TRUNCATE TABLE` 比 `DELETE FROM table`（无 WHERE）快得多：TRUNCATE 直接丢弃数据文件重建，不走 purge；DELETE 逐行写 undo log 再 purge，对 Buffer Pool 和 purge thread 压力极大

**监控 Buffer Pool 健康度**

```sql
-- 快速查看命中率（每隔 30s 查一次对比）
SELECT
  pool_id,
  pool_size,
  free_buffers,
  database_pages,
  hit_rate / 1000.0 AS hit_rate_pct,
  pages_made_young,
  pages_not_made_young
FROM information_schema.INNODB_BUFFER_POOL_STATS;
```

`hit_rate_pct < 0.99` 时优先加 `innodb_buffer_pool_size`；`pages_not_made_young` 远大于 `pages_made_young` 且有大量全表扫描告警时，考虑加大 `innodb_old_blocks_time`（默认 1000ms 已经能挡住大多数全表扫）。

## 5. 调优实战

**Case A：「加了很多数据，查询变慢，Buffer Pool 命中率降到 85%」**

1. 先确认实例内存和 BP 配置：`SHOW VARIABLES LIKE 'innodb_buffer_pool_size';`
2. 看 `information_schema.INNODB_BUFFER_POOL_STATS` 的 `FREE_BUFFERS`，如果接近 0 说明 BP 已满
3. 如果 `HIT_RATE < 990`：增大 `innodb_buffer_pool_size`（8.0 支持在线动态调整，以 chunk 为单位增减）：

```sql
-- 在线扩容（chunk 为 128MB，新值必须是 chunk * instances 的整数倍）
SET GLOBAL innodb_buffer_pool_size = 4294967296;  -- 4GB
-- 进度查看
SHOW STATUS LIKE 'Innodb_buffer_pool_resize_status';
```

**Case B：「写入 QPS 高，磁盘 IO util 一直 80%+，但读很少」**

1. 检查是否有大量唯一索引（唯一索引不走 Change Buffer）：

```sql
SELECT index_name, non_unique
FROM information_schema.statistics
WHERE table_schema='your_db' AND table_name='your_table'
ORDER BY non_unique;
```

2. 确认 `innodb_change_buffering=all`
3. 考虑把非业务必要的 UNIQUE 索引降为普通索引，在应用层保证唯一性
4. 如果是纯写场景（ETL），考虑 `innodb_flush_log_at_trx_commit=2`（每秒 fsync，可能丢 1s 数据，但写吞吐提升明显）

**Case C：「SHOW ENGINE INNODB STATUS 里 History list length 持续 > 50000」**

这说明 purge 跟不上 undo log 的增速，原因通常是：

1. 存在长事务持有 consistent read view，阻止 purge 推进

```sql
SELECT trx_id, trx_started, trx_isolation_level,
       TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS seconds_running
FROM information_schema.INNODB_TRX
ORDER BY trx_started
LIMIT 5;
```

找到长事务后通知业务方 commit 或用 `KILL CONNECTION` 断开。

2. `innodb_purge_threads` 不足：`SET GLOBAL innodb_purge_threads=8;`（需重启生效）

**Case D：「innodb_buffer_pool_instances 和 innodb_buffer_pool_size 怎么配」**

规则：`innodb_buffer_pool_size` ≥ 1GB 时，建议 `innodb_buffer_pool_instances = min(BP_SIZE_GB, 64)`，不超过 64。实际生产常用 8 或 16。每个实例有独立的 free/LRU/flush list 和 mutex，多实例减少单链表的 mutex 竞争，在高并发（> 100 并发查询）下吞吐提升明显。

`innodb_buffer_pool_size` 必须是 `innodb_buffer_pool_chunk_size × innodb_buffer_pool_instances` 的整数倍，否则会自动向上取整：

```
实际大小 = ceil(配置值 / (chunk_size × instances)) × chunk_size × instances
```

## 6. 面试高频考点

### 四层结构数字

| 层级 | 尺寸 | 备注 |
|---|---|---|
| 页（Page） | 16KB（默认） | `innodb_page_size`，不可在线改 |
| 区（Extent） | 1MB = 64 页 | 段空间申请的最小单位（超 32 碎片页后） |
| 段（Segment） | 逻辑概念，无固定大小 | 每个索引有叶/非叶两个段 |
| 表空间（Tablespace） | .ibd 文件大小 | `innodb_file_per_table=ON` 时一表一文件 |

### Buffer Pool 必考三问

**Q：Buffer Pool LRU 为什么要分 young 和 old？**

纯 LRU 在全表扫描时会把所有冷页读进来依次变成「最近使用」，把热点页冲走。改良 LRU 让新读入页落在 old 区头部（midpoint insertion），在 old 区停留超过 `innodb_old_blocks_time`（默认 1000ms）才能晋升 young，全表扫通常扫完一页就不再访问，永远留在 old 区等待自然淘汰。

**Q：Buffer Pool 的 free / LRU / flush 三条链表分别存什么？**

- free list：空闲缓存帧，等待被分配给新读入的页
- LRU list：所有当前持有页的帧，按冷热排序，old 区占 3/8，用于淘汰决策
- flush list：所有脏页（已修改但未写磁盘的页），按修改时间排序，Page Cleaner 线程据此刷盘

**Q：Buffer Pool 多实例（`innodb_buffer_pool_instances`）解决什么问题？**

单 Buffer Pool 的 free/LRU/flush 链表操作需要获取 mutex，高并发下 mutex 竞争成为瓶颈。多实例把 BP 分成多个独立的区域，每个实例有独立的链表和 mutex，一个页固定属于某个实例（`hash(space_id, page_no) % instances`），并发操作打散到不同实例，mutex 竞争降低。

### Change Buffer 必考两问

**Q：为什么唯一索引不能用 Change Buffer？**

唯一索引 INSERT 时必须校验唯一性，而唯一性校验需要读入该页（看有没有重复值）；既然页已经在 Buffer Pool 了，可以直接修改，Change Buffer 没有价值。如果页不在 BP，也必须先读入做校验，不能延迟。

**Q：Change Buffer 什么时候 merge 回索引页？**

该二级索引页被读入 Buffer Pool 时（任何读触发）、Master Thread 定期合并、BP 淘汰该页前、MySQL 正常关机时。

### Doublewrite 必考一问

**Q：有了 redo log 为什么还需要 doublewrite？**

redo log 是增量日志，需要一个完整的基线页才能 replay。如果页在写入过程中发生 partial write（写了一半掉电），页 checksum 不匹配，这个页本身已经损坏，redo log 无从施展。Doublewrite 先把完整页写到连续区域（顺序写），再写到实际位置；崩溃时先用 doublewrite 中的完整页覆盖损坏页，再重放 redo log，两步恢复。

### 高频易错点

- **`innodb_buffer_pool_size` 设得越大越好**：错。OS 和 MySQL 连接线程本身也需要内存，OOM 会直接杀掉 mysqld 进程。生产上限 75% 物理内存。
- **Change Buffer 对所有写有效**：错。仅对二级索引的非唯一索引有效，聚簇索引不走 Change Buffer。
- **AHI 是永久缓存**：错。AHI 完全在内存里，实例重启后失效，需要重新预热。
- **Doublewrite 把写性能减半**：错。Step 2（写到 doublewrite 区域）是顺序 IO，代价远小于随机写，实测性能影响通常 1-5%。
- **页 16KB 是固定的**：是初始化后不可更改，但 `innodb_page_size` 可选 4/8/16/32/64KB，创建数据目录前指定。

## 7. 一句话总结

InnoDB 把磁盘按「16KB 页 → 1MB 区 → 逻辑段 → 表空间」四层组织数据，在内存里用 free / LRU / flush 三条链表管理 Buffer Pool，改良 LRU（young + old，midpoint insertion + 1s 晋升延迟）防止全表扫冲走热点；Change Buffer 把二级非唯一索引的写延迟合并，省随机 IO；Adaptive Hash Index 在热点等值查询上叠加 Hash 层；Doublewrite 用顺序写副本保证页写原子性，让 redo log 有正确基线可 replay——理解这条链路，就能读懂 `SHOW ENGINE INNODB STATUS` 里每一行数字的含义。
