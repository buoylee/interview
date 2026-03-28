# I/O 性能排查

## 概述

磁盘 I/O 是后端服务中最容易被忽视但影响最大的性能瓶颈之一。数据库慢查询、日志写入阻塞、文件上传处理缓慢——这些问题的根因常常是 I/O。本文从 I/O 等待分析开始，逐步深入到工具使用、文件系统选择和高级 I/O 机制。

---

## 一、I/O 等待分析

### iowait 的含义

```
iowait (wa%)：
  CPU 空闲，且有至少一个 I/O 请求未完成。

  本质含义：有进程在等 I/O 完成，CPU 没事可做。

  注意：iowait 高不一定意味着 I/O 有问题：
  - CPU 本身很闲 + 少量 I/O → iowait 占比可能很高（因为分母小）
  - CPU 很忙 + 同样的 I/O → iowait 占比很低（被 us%/sy% 稀释了）

  所以 iowait 需要结合 I/O 吞吐量和延迟一起看。
```

### 在 top 中观察

```bash
top
# 输出第三行：
# %Cpu(s):  5.2 us,  1.3 sy,  0.0 ni, 70.0 id, 23.0 wa,  0.0 hi,  0.5 si
#                                                  ↑
#                                        23% iowait — 偏高
#
# 正常范围：wa% < 5%
# 需要关注：wa% > 10%
# 严重问题：wa% > 30%
```

### 在 vmstat 中观察

```bash
vmstat 1 10
# procs -----memory----- ---swap-- -----io---- -system-- ------cpu-----
#  r  b  swpd   free    si   so    bi    bo   in   cs  us sy id wa st
#  1  5     0 2048000    0    0  8192  4096 1200  800  5  2 70 23  0
#     ↑                            ↑     ↑                    ↑
#     │                            │     │                    └── wa% = 23
#     │                            │     └── 每秒写入块数 (blocks out)
#     │                            └── 每秒读入块数 (blocks in)
#     └── 不可中断睡眠的进程数（通常在等 I/O）

# b 列（blocked）高 → 有很多进程在等 I/O
# bi/bo 高 → I/O 吞吐量大
# wa 高 → CPU 在等 I/O
```

---

## 二、iostat 深度分析

### 基本用法

```bash
iostat -xz 1
# -x  扩展统计（显示所有列）
# -z  不显示没活动的设备
# 1   每秒刷新

# 输出示例：
# Device  r/s    w/s   rkB/s   wkB/s  rrqm/s wrqm/s  %rrqm %wrqm  r_await w_await  aqu-sz  rareq-sz wareq-sz  svctm  %util
# sda    150.00 80.00 4800.0  2560.0   5.00   20.00   3.2  20.0    2.50    5.20    0.85   32.0     32.0     1.20   85.0
# sdb      0.00  0.00    0.0     0.0   0.00    0.00   0.0   0.0    0.00    0.00    0.00    0.0      0.0     0.00    0.0
```

### 各列详解

```
读写速率：
  r/s      — 每秒读请求数（IOPS）
  w/s      — 每秒写请求数（IOPS）
  rkB/s    — 每秒读取的数据量（KB）
  wkB/s    — 每秒写入的数据量（KB）

合并请求：
  rrqm/s   — 每秒合并的读请求数
  wrqm/s   — 每秒合并的写请求数
  → I/O 调度器会将相邻的请求合并，减少实际磁盘操作

延迟（最重要的指标）：
  r_await  — 读请求的平均响应时间（ms），包含排队时间
  w_await  — 写请求的平均响应时间（ms），包含排队时间
  → SSD 正常值：r_await < 1ms, w_await < 2ms
  → HDD 正常值：r_await < 10ms, w_await < 15ms
  → 超过正常值 5-10 倍需要关注

队列深度：
  aqu-sz   — 平均队列长度（等待 + 正在处理的 I/O 请求数）
  → 高队列深度意味着 I/O 在排队

请求大小：
  rareq-sz — 平均读请求大小（KB）
  wareq-sz — 平均写请求大小（KB）
  → 大量小请求（< 4KB）通常是随机 I/O
  → 大请求（> 128KB）通常是顺序 I/O

利用率：
  %util    — 设备繁忙时间百分比
```

### %util 的正确解读

```
%util = 100% 意味着什么？

对 HDD（单队列设备）：
  %util = 100% → 磁盘完全忙碌，每个时刻都有 I/O 在处理
  → 确实是瓶颈

对 SSD/NVMe（多队列设备）：
  %util = 100% → 只说明"至少有一个 I/O 在处理"
  → 不代表达到了设备能力上限！
  → SSD 可以同时处理几十甚至上百个并行 I/O
  → 需要结合 r_await/w_await 判断是否真的饱和

判断 SSD 是否真的饱和：
  看 await 是否明显增加
  如果 %util = 100% 但 await 很低 → 设备并没有过载
  如果 %util = 100% 且 await 持续升高 → 真正过载
```

### 常见模式识别

```bash
# 模式 1：大量随机小 I/O
# r/s=5000 rkB/s=20000 rareq-sz=4 r_await=5
# → 4KB 随机读，每秒 5000 IOPS
# → 典型数据库随机读场景

# 模式 2：大块顺序写
# w/s=100 wkB/s=102400 wareq-sz=1024 w_await=1
# → 1MB 顺序写，低 IOPS 高吞吐
# → 日志写入或备份

# 模式 3：I/O 排队严重
# r/s=200 r_await=50 aqu-sz=10
# → 200 IOPS 但每个请求平均等 50ms，队列长度 10
# → HDD 的典型过载表现
```

---

## 三、iotop 按进程排序

```bash
# 安装
sudo apt install iotop  # Debian/Ubuntu
sudo yum install iotop  # CentOS/RHEL

# 交互模式
sudo iotop -o
# -o  只显示有 I/O 活动的进程

# 输出示例：
# TID  PRIO  USER  DISK READ   DISK WRITE  SWAPIN  IO>    COMMAND
# 1234  be/4  mysql  45.00 M/s   12.00 M/s   0.00%  85.12% mysqld
# 5678  be/4  root    0.00 B/s    5.00 M/s   0.00%  12.34% rsync

# 批处理模式（适合脚本和日志）
sudo iotop -obn 5
# -b  批处理模式
# -n 5  采样 5 次

# 如果系统没有 iotop，用 pidstat 替代
pidstat -d 1
# -d  显示 I/O 统计
# 输出每个进程的 kB_rd/s（读速率）和 kB_wr/s（写速率）
```

---

## 四、NFS 性能问题

### 常见 NFS 性能问题

```
NFS 特点：I/O 请求经过网络传输，延迟 = 本地处理 + 网络 RTT

1. 网络延迟叠加
   本地 SSD 读延迟：~0.1ms
   NFS 读延迟：~1-10ms（取决于网络）
   → 大量小 I/O 时性能差距巨大

2. 默认参数不适合高性能场景
   默认 rsize/wsize 可能是 8KB 或 32KB
   每次 I/O 都是一次网络往返

3. 属性缓存问题
   NFS 客户端会缓存文件属性（如大小、修改时间）
   频繁 stat() 调用可能导致缓存失效 → 大量网络请求
```

### 调优

```bash
# 查看当前 NFS 挂载参数
mount | grep nfs
nfsstat -m

# 优化挂载参数
mount -t nfs -o rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2 \
  nfs-server:/export /mnt/data

# 参数说明：
# rsize=1048576   读块大小 1MB（减少网络往返）
# wsize=1048576   写块大小 1MB
# hard            I/O 错误时无限重试（vs soft 会超时返回错误）
# timeo=600       超时时间 60 秒（单位 0.1 秒）
# retrans=2       重试次数

# 检查 NFS 统计
nfsstat -c  # 客户端统计
nfsstat -s  # 服务端统计

# stale file handle 问题
# 现象：ls: cannot access '/mnt/data/file': Stale file handle
# 原因：NFS 服务端上文件被删除或重新创建，客户端缓存的 file handle 失效
# 解决：重新挂载
umount /mnt/data && mount /mnt/data
```

---

## 五、文件系统选择与调优

### ext4 vs xfs 性能对比

```
ext4：
  ✓ 最成熟稳定的 Linux 文件系统
  ✓ 小文件操作性能好
  ✓ 修复工具完善（fsck）
  ✗ 单文件最大 16TB
  ✗ 高并发写入性能不如 xfs
  ✗ 删除大量文件时可能卡顿

xfs：
  ✓ 大文件和高吞吐场景性能更好
  ✓ 并行 I/O 性能优秀（多线程写入）
  ✓ 在线扩容（但不能缩容）
  ✓ 单文件最大 8EB
  ✗ 不能缩小文件系统大小
  ✗ 小文件大量创建/删除性能一般

选择建议：
  数据库 → xfs（大文件、高并发 I/O）
  通用服务器 → ext4（稳定、工具链完善）
  大数据/存储 → xfs（大文件吞吐优势）
```

### 挂载选项调优

```bash
# noatime：不更新访问时间
mount -o noatime /dev/sda1 /data
# 默认每次读文件都会更新 atime → 一次读操作变成了读+写
# noatime 消除这个写操作
# 对数据库服务器效果明显

# 或使用 relatime（折中方案，Linux 默认）
# 只有在 atime 比 mtime 早时才更新

# barrier 选项
mount -o nobarrier /dev/sda1 /data
# barrier=1（默认）：确保写顺序，防止断电数据不一致
# nobarrier：关闭 barrier，提升写性能
# ⚠ 只在有 BBU（电池备份）的 RAID 控制器上才安全关闭

# /etc/fstab 永久配置
# /dev/sda1  /data  xfs  defaults,noatime,nobarrier  0  2
```

---

## 六、Direct I/O

### 什么是 Direct I/O

```
普通 I/O 路径（Buffered I/O）：
  应用 → Page Cache（内存） → 磁盘

  读：先查 Page Cache，命中直接返回，未命中从磁盘读入 Cache
  写：先写 Page Cache，内核异步刷盘（writeback）

Direct I/O（O_DIRECT）：
  应用 → 磁盘（绕过 Page Cache）

  读：直接从磁盘读，不经过 Cache
  写：直接写磁盘，不经过 Cache
```

### 数据库为什么用 O_DIRECT

```
数据库（如 MySQL InnoDB、PostgreSQL）有自己的 Buffer Pool。

如果用 Buffered I/O：
  数据被缓存了两次 → 应用 Buffer Pool + 内核 Page Cache
  双重缓存浪费内存
  内核的 Page Cache 换出策略不理解数据库的访问模式
  writeback 时机不受数据库控制 → 数据库无法保证 WAL 写入顺序

使用 O_DIRECT：
  数据只缓存一次 → 应用 Buffer Pool
  数据库自己管理缓存策略（更聪明的 LRU/Clock 算法）
  数据库自己控制何时刷盘（fsync）
  → 更高效、更可控
```

```bash
# MySQL InnoDB 配置
# innodb_flush_method = O_DIRECT
# → 数据文件使用 O_DIRECT，日志文件仍用 Buffered I/O

# 测试 Direct I/O 性能
# fio 是标准的 I/O 基准测试工具
fio --name=direct-read \
    --ioengine=libaio \
    --direct=1 \         # 使用 Direct I/O
    --rw=randread \      # 随机读
    --bs=4k \            # 块大小 4KB
    --numjobs=4 \        # 4 个并发
    --iodepth=32 \       # 队列深度 32
    --size=1G \          # 测试文件 1GB
    --runtime=30 \       # 运行 30 秒
    --filename=/data/testfile

# 对比 Buffered I/O
fio --name=buffered-read \
    --ioengine=libaio \
    --direct=0 \         # 使用 Buffered I/O
    --rw=randread \
    --bs=4k \
    --numjobs=4 \
    --iodepth=32 \
    --size=1G \
    --runtime=30 \
    --filename=/data/testfile
```

---

## 七、io_uring 简介

### 传统 I/O 接口的问题

```
传统同步 I/O（read/write）：
  每次 I/O 一次系统调用
  系统调用有上下文切换开销
  高 IOPS 场景下系统调用成为瓶颈

传统异步 I/O（Linux AIO / libaio）：
  只支持 Direct I/O
  接口设计复杂
  性能受限于内核实现
```

### io_uring 是什么

```
io_uring（Linux 5.1+）：
  - Linux 内核的高性能异步 I/O 框架
  - 使用两个 ring buffer（提交队列 SQ + 完成队列 CQ）在用户态和内核之间通信
  - 避免每次 I/O 都做系统调用
  - 支持 Buffered I/O 和 Direct I/O
  - 支持网络 I/O（不仅仅是磁盘）

性能提升：
  高 IOPS 场景下比 libaio 提升 2-3 倍
  系统调用次数大幅减少
```

```
io_uring 工作原理：

  用户空间                    内核空间
  ┌──────────┐              ┌──────────┐
  │ 提交队列  │  ─── mmap ──→ │ 提交队列  │
  │   (SQ)   │              │   (SQ)   │
  └──────────┘              └──────────┘
                                  │
                            处理 I/O 请求
                                  │
  ┌──────────┐              ┌──────────┐
  │ 完成队列  │  ←── mmap ── │ 完成队列  │
  │   (CQ)   │              │   (CQ)   │
  └──────────┘              └──────────┘

  1. 应用往 SQ 中放入 I/O 请求（无需系统调用）
  2. 批量通知内核处理（一次系统调用提交多个 I/O）
  3. 内核处理完后把结果放入 CQ
  4. 应用从 CQ 中读取结果（无需系统调用）
```

### io_uring 的应用

```
已经采用 io_uring 的项目：
  - PostgreSQL（实验性支持）
  - RocksDB
  - io_uring 版 nginx（实验性）
  - liburing（C 库封装）
  - tokio（Rust 异步运行时，io_uring 后端）

对应用开发者的意义：
  大多数情况下不需要直接使用 io_uring
  数据库和框架层面会逐步采用
  了解原理有助于理解未来 I/O 性能瓶颈的变化
```

---

## 八、I/O 排查流程

```
应用"慢"且 CPU 不高
  │
  ├── Step 1: top 看 iowait (wa%)
  │    └── wa% > 10% → 可能有 I/O 问题
  │
  ├── Step 2: iostat -xz 1 看磁盘状态
  │    ├── %util 高 + await 高 → 磁盘过载
  │    ├── %util 低 + await 高 → 可能是锁竞争（不是 I/O 问题）
  │    └── r/s 或 w/s 异常高 → 找到是谁在大量读写
  │
  ├── Step 3: iotop -o 找到 I/O 大户进程
  │    └── 确认是哪个进程在做大量 I/O
  │
  ├── Step 4: 分析 I/O 模式
  │    ├── 随机小 I/O → 考虑增加缓存/使用 SSD
  │    ├── 大量顺序写 → 检查日志级别/是否在做备份
  │    └── 读 I/O 高 → Page Cache 不够（内存不足）
  │
  └── Step 5: 调优
       ├── 硬件：HDD → SSD / 增加内存（扩大 Page Cache）
       ├── 文件系统：noatime / 选择 xfs
       ├── 应用：减少不必要的 I/O / 批量写入 / 异步 I/O
       └── 内核：调整 I/O 调度器 / dirty page 参数
```

```bash
# I/O 调度器查看和修改
cat /sys/block/sda/queue/scheduler
# [mq-deadline] kyber bfq none

# SSD 推荐 none（noop）或 mq-deadline
# HDD 推荐 mq-deadline 或 bfq
echo "none" > /sys/block/sda/queue/scheduler

# dirty page 参数（影响写回策略）
sysctl vm.dirty_ratio           # 占内存百分比，超过时同步写回（默认 20）
sysctl vm.dirty_background_ratio # 后台写回触发阈值（默认 10）
sysctl vm.dirty_expire_centisecs # 脏页过期时间（默认 3000 = 30秒）

# 数据库服务器建议降低 dirty_ratio（减少突发 I/O）
sudo sysctl -w vm.dirty_ratio=5
sudo sysctl -w vm.dirty_background_ratio=2
```

---

## 总结

I/O 性能排查的关键点：

1. **iowait 是起点但不是结论**：wa% 高说明可能有 I/O 问题，但需要 iostat 确认
2. **iostat 看 await 不只看 %util**：特别是 SSD 环境，%util 可能误导
3. **iotop 找进程**：知道了 I/O 大户才能有针对性地优化
4. **文件系统有讲究**：noatime 是最简单有效的优化，xfs 适合数据库
5. **Direct I/O 有特定适用场景**：数据库用 O_DIRECT 避免双重缓存
6. **io_uring 代表未来**：高 IOPS 场景下显著优于传统接口
