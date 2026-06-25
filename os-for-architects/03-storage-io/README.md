# 03 · 存储 IO → 持久化与引擎选型

> **薄镜头定位**：存储 IO 的 OS 原语就这几条 —— 顺序 vs 随机、fsync 语义、page cache 回写、顺序写最快。把它们从"事后解释 await 高"翻到"事前决定引擎选型和持久化权衡"，是本章唯一的事。机制细节和容量推导进指针。

---

## 一、盲点

你现在的状态：`await` 高了就说"盘慢"，`dirty_ratio` 触发了就说"脏页回刷"。这是**事后解释**，资深能答到这层。

架构师的事前问题不是这些：

- 这个业务的写入是顺序还是随机？选 LSM 还是 B+树？
- `fsync` 每条调一次还是组提交？吞吐 vs 持久化怎么给产品讲清楚？
- page cache 命中率假设是多少？这个假设在容量规划里去哪换算？
- 这个系统该不该用 direct IO？加了之后你失去什么？

**一句点破**：资深靠指标事后解释，架构师靠原语事前设计 —— 存储的差别从选引擎那一刻就开始了。

---

## 二、原语 → 决策映射表

| OS 原语 | 资深·能答（反应式） | 架构师·能设计（预判式） |
|---|---|---|
| **顺序 IO ≫ 随机 IO**（磁盘/NVMe 均成立） | "await 高 → 盘慢，可能随机 IO 太多" | 顺序 vs 随机**决定引擎选型**：写密集选 LSM（追加顺序写）；读多写少选 B+树（原地随机写可接受）；日志结构（Kafka、WAL）强制顺序 |
| **fsync / fdatasync 语义**（落盘屏障） | "fsync 阻塞，写放大高" | 持久化 vs 吞吐**权衡设计**：DB 的 `sync=1` vs `sync=0`；MQ 的 `acks=all` vs `acks=1`；组提交（group commit）把多个 fsync 合批，吞吐×N 持久化保证不降 |
| **顺序写最快**（追加 > 原地更新） | "顺序写快" | **WAL 架构手法**：把任何随机写（B+树 node 更新、内存状态变更）前置一条顺序追加日志，崩溃恢复靠重放；这是 MySQL InnoDB redo log / PostgreSQL WAL / etcd raft log 背后共同的 OS 原语 |
| **page cache 回写**（dirty page / writeback） | "脏页比例高会触发回刷，影响延迟" | page cache **命中率是容量假设**：热数据 < 内存则命中率≈100%，IO 压力极低；超出则 IO 随命中率下跌曲线展开；容量规划时先确认"热数据集多大"；direct IO 绕过 page cache，适合自管缓存（数据库 buffer pool）的场景，代价是失去 OS 层预读和预写优化 |
| **读写放大**（Read/Write Amplification） | "写放大会缩短 SSD 寿命" | 引擎选型时**放大三角**（读放大、写放大、空间放大）必须显式取舍：LSM 写放大低、读放大高（compaction 换来的）；B+树读放大低、写放大偏高（原地更新带来的）；设计时要对齐业务访问模式 |

---

## 三、定量锚点

**反射式**：拿到业务写入需求，先估 IOPS 和带宽，对齐磁盘/NVMe 规格，再叠读写放大系数。

**一例**：

> 业务峰值写入 50 MB/s（顺序），LSM compaction 写放大系数约 10×，则底层磁盘吞吐需覆盖 **~500 MB/s**；若用随机写工作负载估容量（典型 IOPS×4KB），结论完全不同，设计会欠配。

**放大系数口袋数**（面试速答用，精确数进深矿）：

| 存储层 | 顺序写吞吐 | 随机写 IOPS | 典型写放大 |
|---|---|---|---|
| 机械盘（7200 RPM） | ~150 MB/s | ~150 IOPS | — |
| SATA SSD | ~500 MB/s | ~数万 IOPS | — |
| NVMe SSD | ~3 GB/s | ~500K IOPS | — |
| RocksDB / LevelDB | — | — | 写放大 ×10–30 |
| InnoDB B+树 | — | — | 写放大 ×2–5 |

> 完整容量推导（IOPS 预算、放大建模、磁盘规格选型）→ `../../performance-tuning-roadmap/00-os-fundamentals/03-disk-io-filesystem.md`

---

## 四、决策清单 & 反模式

### 设计期该问的问题

- 这个系统的写入模式是顺序追加还是随机原地更新？（决定 LSM vs B+树）
- 持久化级别要 per-write fsync，还是可以接受组提交 / 异步刷盘？（对齐业务的数据丢失容忍度）
- 热数据集多大？是否能放进内存 / buffer pool？（决定 page cache 假设和 IO 压力模型）
- 是否有自管缓存（buffer pool）？如果有，direct IO 是否比 page cache 更合适？
- 读写放大的取舍方向和业务访问模式对齐了吗？

### 反模式

| 反模式 | 问题 | 正确做法 |
|---|---|---|
| **每次写都 fsync** | 吞吐崩到 IOPS 级别（一次 fsync ≈ 一次磁盘转/寻道），高并发写变串行 | 用组提交（group commit）或批量 fsync，持久化保证相同，吞吐×N |
| **用随机 IO 估容量** | 高估 IOPS 需求（随机 IOPS 低），或低估顺序写吞吐（顺序带宽才是瓶颈） | 先判顺序/随机，分别用带宽（MB/s）或 IOPS 作为计量单位 |
| **忽略写放大** | LSM compaction 写放大 10×，结果磁盘吞吐不够，compaction 积压、读放大飙升 | 规划时显式建模写放大系数，留出 compaction 带宽余量 |
| **生产用 page cache + 数据库 buffer pool 双缓冲** | 内存浪费（同一份数据缓存两次），且 page cache 回写和 buffer pool flush 可能干扰 | 数据库场景通常用 direct IO + 自管 buffer pool，绕开 OS 层缓存 |
| **把 sync=0（异步刷盘）当"反正有备库"的理由** | 主库崩溃时 binlog / redo log 未落盘，备库复制点落后，切主会丢数据 | 持久化设计要覆盖"主库宕机"场景，分开考虑单机落盘和复制确认 |

---

## 五、指针

### 下指（机制 · 能答层）

- **IO 与文件系统机制、await/iowait 指标、direct IO vs buffered IO**：
  `../../linux-handson/05-io-and-files/`
- **磁盘 IO 性能机制、page cache 深度、文件系统调优**：
  `../../performance-tuning-roadmap/00-os-fundamentals/03-disk-io-filesystem.md`

### 横指（深决策层）

- **存储引擎选型全景（LSM vs B+树、WAL、compaction 策略、行存/列存）**：
  `../../system-design/06-存儲選型.md`
- **数据规模化 · 分库分表与读写分离**（IO 约束在分布式层的延伸）：
  `../../system-design/07-數據規模化-分庫分表與讀寫分離.md`
- **数据库架构深决策（buffer pool、redo log、持久化权衡、容量建模）**：
  `../../performance-tuning-roadmap/11-architecture/04-database-architecture.md`

---

## 六、面试转化

### 题 1 · 顺序写 vs 随机写怎么影响存储选型？

**能答（反应式）**：

> 顺序写吞吐高（磁盘 ~150 MB/s、NVMe ~3 GB/s），随机写 IOPS 受限（磁盘 ~150、NVMe ~500K）。await 高说明有随机 IO 压力。

**能设计（预判式）**：

> 写密集业务（日志、时序、消息）选 LSM：所有写变顺序追加，后台 compaction 归并，写放大换读放大；读多写少（事务 OLTP）选 B+树：原地更新、范围读高效，随机写是代价但可接受。WAL（Write-Ahead Log）是**持久化**手法 —— 写前先顺序追加一条日志保证可恢复，崩溃靠重放；真正把随机写整体转成顺序写的是 LSM。MySQL InnoDB redo log / Kafka log segment 都是顺序日志的实例。设计文档里要写清楚：业务访问模式→引擎类型→放大系数→磁盘吞吐预算，一条链。

---

### 题 2 · acks/fsync 怎么权衡？

**能答（反应式）**：

> `fsync` 把内核 page cache 数据强制落盘，调用一次大约一次磁盘寻道。`acks=all` 要等所有 ISR 副本落盘才返回。这两个都会拉高延迟。

**能设计（预判式）**：

> 持久化设计三维取舍：**单机落盘**（fsync per-write vs 组提交 vs sync=0）× **复制确认**（acks=0/1/all）× **业务容忍丢数据的窗口**。
>
> - 金融/订单：`sync=1` + 组提交（InnoDB 默认）+ `acks=all` —— 落盘 + 复制双保险，组提交把串行 fsync 合批，吞吐可接受。
> - 日志 / 监控写入：`sync=0`（OS 定期刷）+ `acks=1` —— 最多丢几秒数据，换百倍吞吐。
> - 关键点：`sync=0` + "反正有备库"这个组合**不安全**：主库崩溃时 redo log 未落盘，备库复制点落后，切主会丢已确认的事务。持久化和复制要分开设计，不能互相抵消。
>
> 面试加分句："我们会在设计文档里把 RPO（最多丢多少数据）量化成秒数，然后反推 fsync 策略和 acks 级别，而不是让研发自行决定。"
