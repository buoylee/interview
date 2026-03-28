# 磁盘 I/O 与文件系统

> 磁盘 I/O 是大多数后端系统最慢的一环。理解块设备模型、Page Cache、I/O 调度器以及顺序与随机 I/O 的差异，是排查 I/O 瓶颈的基础。

---

## 1. 块设备模型

Linux 将磁盘抽象为**块设备**，所有 I/O 操作都以块为单位。从应用到磁盘的 I/O 路径：

```
应用程序
  │  read()/write() 系统调用
  ▼
VFS (Virtual File System)
  │  统一文件操作接口
  ▼
具体文件系统 (ext4/xfs/btrfs)
  │  管理文件到块的映射
  ▼
Page Cache
  │  读写缓存层
  ▼
通用块层 (Block Layer)
  │  合并/排序 I/O 请求，生成 bio 结构
  ▼
I/O 调度器
  │  决定请求提交顺序
  ▼
块设备驱动
  │  发送 SCSI/NVMe 命令
  ▼
物理磁盘 (HDD/SSD/NVMe)
```

### 关键概念

| 概念 | 大小 | 说明 |
|------|------|------|
| 扇区 (Sector) | 512 字节（传统）/ 4KB（AF） | 磁盘硬件的最小读写单位 |
| 块 (Block) | 通常 4KB | 文件系统的最小分配单位 |
| bio | 可变 | 内核对一次 I/O 操作的描述，包含多个 segment |
| I/O 请求 (request) | 可变 | 多个连续 bio 合并后的请求 |

```bash
# 查看块设备信息
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,SCHED,ROTA

# 查看扇区大小
fdisk -l /dev/sda | grep "Sector size"

# 查看文件系统块大小
tune2fs -l /dev/sda1 | grep "Block size"
```

---

## 2. 文件系统：ext4 vs xfs

### ext4

- Linux 默认文件系统，成熟稳定
- 最大文件大小 16TB，最大文件系统 1EB
- 支持延迟分配（delayed allocation）、extent-based 分配
- 适合通用场景，中小文件表现良好

### xfs

- 高性能文件系统，特别擅长大文件和大目录
- 最大文件大小 8EB，最大文件系统 8EB
- 并行 I/O 优秀（多 AG 架构）
- 不支持缩容（只能扩容）
- 适合大数据、数据库等大文件场景

### 选型建议

| 场景 | 推荐 | 原因 |
|------|------|------|
| 通用 Linux 服务器 | ext4 | 稳定、工具链完善、默认就好 |
| 数据库（MySQL/PG） | xfs | 大文件随机写性能好，并行 I/O 强 |
| 大数据 (HDFS/Kafka) | xfs | 大文件顺序写性能好 |
| 容器 overlay fs | ext4 或 xfs | 两者都可，注意 d_type 支持 |

```bash
# 查看当前文件系统类型
df -Th

# 创建 ext4 文件系统
mkfs.ext4 -T largefile /dev/sdb1

# 创建 xfs 文件系统
mkfs.xfs /dev/sdb1

# 查看 ext4 详细参数
tune2fs -l /dev/sda1

# 查看 xfs 详细参数
xfs_info /dev/sdb1
```

---

## 3. Page Cache

Page Cache 是 Linux 最重要的 I/O 优化机制，它在内存中缓存磁盘数据：

```
应用层 read()
    │
    ├──→ Page Cache 命中 → 直接返回内存数据 (us 级)
    │
    └──→ Page Cache 未命中 → 从磁盘读取 → 存入 Page Cache → 返回
                                          (ms 级)
```

### 读缓存

- 首次读取文件时，数据从磁盘加载到 Page Cache
- 后续读取相同数据直接从 Page Cache 返回（内存速度）
- 内核会预读（readahead），把后续的页面提前加载

### 写缓存（脏页回写）

- `write()` 只是把数据写到 Page Cache 就返回（非常快）
- Page Cache 中被修改但未写回磁盘的页面称为**脏页（Dirty Page）**
- 内核后台线程定期将脏页写回磁盘

```
write() → Page Cache (脏页) → 后台回写线程 → 磁盘
         应用立即返回           异步，不阻塞应用
```

### 脏页回写参数

```bash
# 查看当前脏页参数
sysctl -a | grep dirty

# vm.dirty_ratio = 20
#   脏页占可用内存 20% 时，进程的 write() 开始同步阻塞写回
# vm.dirty_background_ratio = 10
#   脏页占可用内存 10% 时，后台线程开始异步写回
# vm.dirty_expire_centisecs = 3000
#   脏页超过 30 秒必须写回
# vm.dirty_writeback_centisecs = 500
#   后台回写线程每 5 秒检查一次

# 查看当前脏页大小
cat /proc/meminfo | grep Dirty

# 查看 Page Cache 使用情况
free -h
# buffers/cache 行就是 Page Cache
```

**生产经验**：如果 `dirty_ratio` 设置过大，突然大量脏页回写时会导致 I/O 风暴，影响在线服务。数据库服务器通常降低 `dirty_ratio` 到 5-10%。

---

## 4. I/O 调度器

I/O 调度器决定了 I/O 请求提交给磁盘的顺序，对性能有直接影响。

### 传统调度器（单队列，Linux < 5.0 / HDD）

| 调度器 | 特点 | 适用场景 |
|--------|------|----------|
| CFQ (Completely Fair Queuing) | 为每个进程分配时间片和 I/O 带宽 | HDD + 多进程混合负载 |
| Deadline | 为每个请求设置截止时间，防止饥饿 | 数据库（保证延迟） |
| NOOP | 简单 FIFO，不做排序合并 | SSD / 虚拟机 |

### 多队列调度器（Multi-Queue，Linux >= 5.0）

| 调度器 | 特点 | 适用场景 |
|--------|------|----------|
| mq-deadline | deadline 的多队列版本 | 数据库 + SSD |
| BFQ (Budget Fair Queuing) | CFQ 的多队列继任者，注重公平 | 桌面、多用户共享 |
| kyber | 轻量级，基于令牌桶 | 高速 NVMe |
| none | 无调度，直接下发 | NVMe（设备自带调度） |

```bash
# 查看当前调度器
cat /sys/block/sda/queue/scheduler
# [mq-deadline] kyber bfq none

# 切换调度器
echo "none" > /sys/block/nvme0n1/queue/scheduler

# 永久配置（通过 udev 规则）
# /etc/udev/rules.d/60-scheduler.rules
# ACTION=="add|change", KERNEL=="sd*", ATTR{queue/scheduler}="mq-deadline"
# ACTION=="add|change", KERNEL=="nvme*", ATTR{queue/scheduler}="none"
```

**实践建议**：
- HDD：使用 `mq-deadline`（保证延迟，适合数据库）
- SATA SSD：使用 `mq-deadline` 或 `none`
- NVMe SSD：使用 `none`（NVMe 有硬件队列，无需软件调度）

---

## 5. 顺序 I/O vs 随机 I/O

这是理解 I/O 性能最关键的概念之一：

### HDD（机械硬盘）

```
顺序读: ~200 MB/s
随机读: ~0.5-2 MB/s  (IOPS ~100-200)
差距: 100-400 倍

原因：机械寻道
┌──────────────────────────┐
│          磁盘盘片          │
│    ┌─────────────────┐    │
│    │  磁道 0 → 寻道    │    │
│    │     ↓  (ms 级)   │    │
│    │  磁道 1000       │    │
│    └─────────────────┘    │
│    机械臂移动 + 旋转等待    │
└──────────────────────────┘
平均寻道: ~5ms，旋转延迟: ~4ms (7200rpm)
一次随机 I/O ≈ 9ms → IOPS ≈ 111
```

### SSD（固态硬盘）

```
顺序读: ~500 MB/s (SATA) / ~3500 MB/s (NVMe)
随机读: ~50-100 MB/s (IOPS ~50K-100K SATA / ~500K NVMe)
差距: 5-10 倍（比 HDD 好很多，但差距仍然存在）

原因：即使 SSD 无寻道，随机 I/O 导致更多的 FTL 查表和 Page 级读取
```

| 操作 | HDD | SATA SSD | NVMe SSD |
|------|-----|----------|----------|
| 顺序读 (MB/s) | ~200 | ~550 | ~3500 |
| 随机读 IOPS (4KB) | ~150 | ~80K | ~500K |
| 顺序写 (MB/s) | ~180 | ~520 | ~3000 |
| 随机写 IOPS (4KB) | ~150 | ~30K | ~200K |

**性能启示**：
- 数据库日志（WAL/Redo Log）是顺序写，性能好
- 数据库页面读取是随机读，IOPS 才是瓶颈
- Kafka 之所以快，核心原因之一是**纯顺序 I/O**

---

## 6. fsync 与 fdatasync

`write()` 只保证数据到达 Page Cache，不保证到达磁盘。要保证数据持久化，需要显式刷盘：

| 函数 | 刷什么 | 代价 |
|------|--------|------|
| `fsync(fd)` | 文件数据 + 文件元数据（大小、修改时间等） | 高 |
| `fdatasync(fd)` | 文件数据 + 必要的元数据（大小变更等） | 略低于 fsync |
| `sync()` | 所有文件系统的所有脏页 | 最高 |
| `O_SYNC` flag | 每次 write 都同步刷盘 | 最慢，相当于每次 write + fsync |

```
write() 调用链:
数据 → 用户缓冲区 → 内核 Page Cache → [fsync] → 磁盘控制器 → [磁盘缓存] → 磁盘介质

注意：即使 fsync 成功，如果磁盘控制器有写缓存且未启用 FUA 或 Battery Backup，
掉电仍可能丢数据。
```

**数据库通常的做法**：
- MySQL InnoDB：`innodb_flush_method = O_DIRECT`（绕过 Page Cache）+ `innodb_flush_log_at_trx_commit = 1`（每次提交 fsync redo log）
- PostgreSQL：`wal_sync_method = fdatasync`（WAL 使用 fdatasync）
- 这是数据安全与性能的平衡点

---

## 7. Direct I/O 与 Buffered I/O

| 模式 | 特点 | 适用场景 |
|------|------|----------|
| Buffered I/O（默认） | 经过 Page Cache | 大多数场景 |
| Direct I/O (O_DIRECT) | 绕过 Page Cache，直达磁盘 | 数据库（自己管理缓存） |

```
Buffered I/O:
App → Page Cache → 磁盘
优点：利用 Page Cache 加速，对小文件/重复读取友好
缺点：双重缓存（数据库有自己的 Buffer Pool + OS Page Cache），浪费内存

Direct I/O:
App → 磁盘 (绕过 Page Cache)
优点：避免双重缓存，减少内存占用和 CPU 开销
缺点：每次 I/O 必须对齐（通常 512 字节或 4KB），编程更复杂
```

```bash
# 测试 Buffered I/O 性能
dd if=/dev/zero of=testfile bs=1M count=1024

# 测试 Direct I/O 性能
dd if=/dev/zero of=testfile bs=1M count=1024 oflag=direct

# 用 fio 测试
fio --name=seqwrite --ioengine=libaio --direct=1 --rw=write \
    --bs=4k --size=1G --numjobs=4 --runtime=30 --group_reporting
```

---

## 8. 实用诊断命令速查

```bash
# I/O 整体概览
iostat -xz 1
# 重点关注：
#   %util  - 设备利用率（>80% 说明 I/O 饱和）
#   await  - 平均 I/O 等待时间（ms）
#   r/s, w/s - 每秒读写请求数（IOPS）
#   rkB/s, wkB/s - 每秒读写带宽

# 查看哪些进程在做 I/O
iotop -oP

# 跟踪进程的 I/O 系统调用
strace -e trace=read,write,fsync -c -p <pid>

# 查看 I/O 延迟分布（需要 bcc-tools）
biolatency -D 10

# 查看 Page Cache 命中率（需要 bcc-tools）
cachestat 1

# 清除 Page Cache（测试用）
sync && echo 3 > /proc/sys/vm/drop_caches

# 查看文件是否在 Page Cache 中
vmtouch testfile
# 或
fincore testfile
```

---

## 要点总结

1. **I/O 路径很长**——从应用到磁盘经过 VFS、文件系统、Page Cache、块层、调度器、驱动，任何一层都可能成为瓶颈。
2. **Page Cache 是性能的关键**——绝大多数读 I/O 应该命中 Page Cache。如果 cache hit ratio 低，通常是内存不够或访问模式太随机。
3. **顺序 vs 随机 I/O 差距巨大**——HDD 上差 100 倍以上，SSD 上也差 5-10 倍。设计存储模型时应优先考虑顺序 I/O。
4. **I/O 调度器要匹配硬件**——NVMe 用 `none`，HDD 用 `mq-deadline`。
5. **fsync 是数据安全的代价**——不调用 fsync 性能好但可能丢数据，调用太频繁则 I/O 压力大。数据库会在这里做精心权衡。
6. **数据库用 Direct I/O 有道理**——避免和 OS Page Cache 的双重缓存，自己管理 Buffer Pool 更高效。
