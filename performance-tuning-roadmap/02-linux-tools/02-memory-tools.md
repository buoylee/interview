# 内存观测工具

内存问题往往不像 CPU 那样立竿见影地表现为"慢"，而是以更隐蔽的方式影响性能：OOM Kill、Swap 导致的延迟抖动、Page Cache 命中率下降导致 I/O 增加。本文介绍 Linux 下的内存观测工具链。

## free -h — 内存概况

```bash
$ free -h
              total        used        free      shared  buff/cache   available
Mem:            15G         11G        512M        234M        3.8G        3.5G
Swap:          4.0G        1.2G        2.8G
```

### 各列含义

| 列 | 含义 |
|----|------|
| **total** | 物理内存总量 |
| **used** | 已使用的内存（含被进程占用 + 内核） |
| **free** | 完全未使用的内存 |
| **shared** | 共享内存（tmpfs 等） |
| **buff/cache** | 内核缓冲区（buffer）+ 页缓存（page cache） |
| **available** | 可以给应用使用的内存（free + 可回收的 buff/cache） |

### 关键认知：看 available，不看 free

Linux 会尽量把空闲内存用于 Page Cache（文件系统缓存），所以 `free` 经常接近 0。这不代表内存不足。

```
内存真的不足的标志：
✗ free 接近 0                    ← 不能说明问题
✓ available 接近 0               ← 说明内存确实不足
✓ Swap used > 0 且持续增长        ← 说明内存压力大
✓ 出现 OOM Kill                  ← 说明内存严重不足
```

上面的例子中，free = 512M 看起来很少，但 available = 3.5G，说明还有 3.5G 可以使用（通过回收 buff/cache）。

### Swap 行

```
Swap:          4.0G        1.2G        2.8G
```

Swap used = 1.2G 说明系统在过去某个时间点内存压力大，把一部分内存页换出到了磁盘。即使当前 available 充足，Swap 中的数据在被访问时需要换回内存，会导致延迟尖刺。

## vmstat 1 — 内存活动监控

```bash
$ vmstat 1 5
procs -----------memory---------- ---swap-- -----io---- -system-- ------cpu-----
 r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st
 2  0  1228800 524340 21456 3894520  0    0     4    12  3421 5234 45  8 44  2  0
 3  1  1228800 518212 21456 3894520  0    0   256    28  3856 5890 42 10 38  8  0
 2  3  1245184 502100 21456 3878136  24  416   280   420  4102 6120 38 15 28 18  0
 4  2  1261568 489234 21456 3862520  32  512   340   540  4523 6890 35 18 22 24  0
 3  0  1261568 495456 21456 3868234   0    0     8    12  3245 4892 44  9 42  4  0
```

### 内存相关关键列

| 列 | 含义 | 关注点 |
|----|------|--------|
| **swpd** | 已使用的 Swap 大小（KB） | 持续增长 = 内存压力 |
| **free** | 空闲内存 | 参考值，不如 available |
| **buff** | 块设备缓冲区 | 通常较稳定 |
| **cache** | Page Cache | 文件系统缓存 |
| **si** | Swap In（KB/s） | 从 Swap 读回内存 |
| **so** | Swap Out（KB/s） | 从内存写到 Swap |

**si/so 是内存饱和度的直接指标。** 上面第 3-4 行出现了 si 和 so，说明系统正在进行 Swap 活动：

```
第 3 行: si=24, so=416  → 正在把 416KB/s 写入 Swap，同时从 Swap 读回 24KB/s
第 4 行: si=32, so=512  → Swap 活动加剧
第 5 行: si=0,  so=0    → Swap 活动停止
```

如果 si/so 持续 > 0，系统在频繁换页，这会严重影响性能（磁盘 I/O 比内存访问慢 10 万倍）。

## slabtop — 内核 Slab 缓存

内核自己也使用内存，Slab 分配器管理内核对象的内存（如 inode、dentry、task_struct 等）。

```bash
$ sudo slabtop --once
 Active / Total Objects (% used)    : 2543210 / 2654321 (95.8%)
 Active / Total Slabs (% used)      : 85432 / 85432 (100.0%)
 Active / Total Caches (% used)     : 112 / 152 (73.7%)
 Active / Total Size (% used)       : 845.32M / 892.15M (94.7%)

  OBJS ACTIVE  USE OBJ SIZE  SLABS OBJ/SLAB CACHE SIZE NAME
892340 890234  99%    0.19K  42492       21    169968K dentry
534120 530234  99%    0.57K  38151       14    305208K inode_cache
123456 120123  97%    1.06K   8230       15    131680K ext4_inode_cache
 85432  84521  98%    0.25K   5339       16     21356K filp
```

### 什么时候要看 slabtop

- `free` 显示大量内存被 buff/cache 占用，但 Page Cache 并不大 → 可能是 Slab 占了很多
- dentry/inode_cache 过大 → 系统有大量小文件操作（如日志目录下有百万文件）
- 某个 Slab 持续增长不释放 → 可能是内核内存泄漏

```bash
# 查看 Slab 总占用
$ cat /proc/meminfo | grep Slab
Slab:             921456 kB    ← 约 900MB 被 Slab 占用
SReclaimable:     845234 kB    ← 其中 845MB 可回收
SUnreclaim:        76222 kB    ← 76MB 不可回收
```

## pmap -x — 进程内存映射

```bash
$ pmap -x 3421 | head -20
3421:   java -Xmx4g -jar app.jar
Address           Kbytes     RSS   Dirty Mode  Mapping
0000000000400000    2048    1820       0 r-x-- java
0000000000800000      16      16      16 r---- java
0000000000804000       4       4       4 rw--- java
00000000012f0000    4352    4096    4096 rw---   [ anon ]      ← Java 堆
00007f1234000000 4194304 2148532 2148532 rw---   [ anon ]      ← Java 堆（mmap）
00007f1234500000   65536   32768   32768 rw---   [ anon ]      ← 线程栈
00007f1238000000     132     132       0 r-x-- libc-2.31.so
...
$ pmap -x 3421 | tail -1
total kB         8523456 2345678 2189432
```

各列含义：
- **Kbytes**：映射的虚拟内存大小
- **RSS**（Resident Set Size）：实际占用的物理内存
- **Dirty**：被修改过的页面（回写前不能释放）
- **Mode**：r=读、w=写、x=执行、s=共享、p=私有

**用途**：排查进程的内存都被什么占了。上面的例子中，`[ anon ]` 就是 Java 堆和线程栈。

## /proc/meminfo — 内存详细信息

```bash
$ cat /proc/meminfo
MemTotal:       16284856 kB
MemFree:          524340 kB
MemAvailable:    3612340 kB
Buffers:           21456 kB
Cached:          3894520 kB
SwapCached:        45232 kB
Active:          9234521 kB
Inactive:        5123456 kB
Active(anon):    8523456 kB
Inactive(anon):  1234567 kB
Active(file):     711065 kB
Inactive(file):  3888889 kB
SwapTotal:       4194300 kB
SwapFree:        2965500 kB
Dirty:             12340 kB
Writeback:             0 kB
AnonPages:       9234521 kB
Mapped:           345678 kB
Shmem:            234567 kB
Slab:             921456 kB
SReclaimable:     845234 kB
SUnreclaim:        76222 kB
PageTables:        45678 kB
HugePages_Total:       0
HugePages_Free:        0
```

### 关键字段

| 字段 | 含义 | 关注点 |
|------|------|--------|
| **MemAvailable** | 可用内存 | 低于总量的 10% 时需要关注 |
| **SwapCached** | 曾被换出但仍在 Page Cache 中 | > 0 说明曾经发生过换页 |
| **Active(anon)** | 活跃的匿名页（进程堆/栈） | 占大头说明进程内存使用多 |
| **Inactive(file)** | 不活跃的文件页 | 可以被回收 |
| **Dirty** | 脏页（待写回磁盘） | 突然变大可能写 I/O 积压 |
| **AnonPages** | 匿名页总量 | 没有文件背景的内存页 |
| **Slab** | 内核 Slab 总量 | 看 slabtop 细分 |

## numastat — NUMA 内存分布

在多 CPU 插槽的服务器上，NUMA（Non-Uniform Memory Access）架构下，每个 CPU 有"本地"和"远端"内存。访问远端内存比本地内存慢 1.5-3 倍。

```bash
$ numastat
                           node0           node1
numa_hit                 45234521        42345678
numa_miss                  123456          234567
numa_foreign               234567          123456
interleave_hit              12345           12345
local_node               44234521        41345678
other_node                1123456         1234567
```

| 指标 | 含义 |
|------|------|
| **numa_hit** | 在期望的节点上分配成功 |
| **numa_miss** | 在期望节点上分配失败，转到其他节点 |
| **other_node** | 进程使用了非本地节点的内存 |

**numa_miss 高或 other_node 占比大** → 大量跨节点内存访问，性能受影响。

```bash
# 查看进程的 NUMA 内存分布
$ numastat -p 3421
Per-node process memory usage (in MBs) for PID 3421 (java)
                           Node 0          Node 1           Total
                  --------------- --------------- ---------------
Huge                         0.00            0.00            0.00
Heap                       856.23         1245.67         2101.90
Stack                        8.45            4.23           12.68
Private                    234.56          312.34          546.90
```

如果一个进程的内存主要分布在非本地节点，可以用 `numactl --membind=0` 绑定内存到特定节点。

## smem — PSS（按比例共享内存）

传统的 RSS 统计对共享库内存有重复计算的问题。PSS（Proportional Set Size）按共享比例分摊。

```bash
$ smem -t -k -s pss | tail -10
  PID User     Command                         Swap      USS      PSS      RSS
 3421 app      java -Xmx4g -jar app.jar           0   2.1G     2.1G     2.2G
 1892 mysql    /usr/sbin/mysqld                    0   1.7G     1.7G     1.8G
 4521 app      python3 worker.py                   0  45.2M    48.5M    62.3M
 4522 app      python3 worker.py                   0  44.8M    48.1M    62.3M
 4523 app      python3 worker.py                   0  45.0M    48.3M    62.3M
...
                                              1.2G     4.8G     5.0G     5.4G
```

| 指标 | 含义 |
|------|------|
| **USS**（Unique Set Size） | 进程独占的物理内存 |
| **PSS**（Proportional Set Size） | USS + 按共享比例分摊的共享内存 |
| **RSS**（Resident Set Size） | USS + 全部共享内存（有重复计算） |

上面三个 Python worker 进程各自 RSS = 62.3M，加起来 = 186.9M。但实际它们共享了很多库内存，PSS 加起来 = 144.9M，更接近真实内存占用。

**什么时候用 smem**：评估一台机器能跑多少个进程实例时，用 PSS 而不是 RSS 来计算。

## 判断标准：什么时候算内存不足

不同于 CPU（看利用率就行），内存不足有多种表现：

```
┌─────────────────────────────────────────────────────────────┐
│                    内存压力等级                                │
├─────────┬───────────────────────────────────────────────────┤
│  正常    │ available > 20% total, si/so = 0                 │
├─────────┼───────────────────────────────────────────────────┤
│  轻度    │ available 10-20% total, 偶尔 si/so > 0           │
│  压力    │ Page Cache 被大量回收，文件 I/O 变慢              │
├─────────┼───────────────────────────────────────────────────┤
│  中度    │ available < 10% total, si/so 持续 > 0            │
│  压力    │ 延迟抖动明显，Swap 持续增长                       │
├─────────┼───────────────────────────────────────────────────┤
│  严重    │ available ≈ 0, Swap 接近用完                      │
│  不足    │ OOM Killer 开始杀进程                             │
└─────────┴───────────────────────────────────────────────────┘
```

检查 OOM Kill 历史：
```bash
$ dmesg | grep -i "oom"
[234567.890123] Out of memory: Killed process 3421 (java) total-vm:8523456kB,
                anon-rss:4234567kB, file-rss:34512kB, shmem-rss:0kB
```

## 排查流程总结

```
free -h → available 低？
    │
    ├─ 是 → vmstat 1 → si/so > 0？
    │         │
    │         ├─ 是 → 内存不足，谁在用内存？
    │         │       → smem -s pss 找大户
    │         │       → pmap -x <pid> 看细分
    │         │
    │         └─ 否 → 检查 Slab (slabtop)
    │                 → 内核可能在大量缓存 inode/dentry
    │
    └─ 否 → 内存不是瓶颈，查其他资源
```

## 小结

| 工具 | 用途 | 关键指标 | 速览命令 |
|------|------|----------|----------|
| free -h | 内存概况 | available | `free -h` |
| vmstat 1 | 内存活动 | si/so | `vmstat 1` |
| slabtop | 内核缓存 | dentry/inode 大小 | `sudo slabtop --once` |
| pmap -x | 进程内存映射 | RSS/Dirty | `pmap -x <pid>` |
| /proc/meminfo | 详细信息 | AnonPages/Dirty | `cat /proc/meminfo` |
| numastat | NUMA 分布 | numa_miss | `numastat -p <pid>` |
| smem | PSS 真实占用 | PSS | `smem -t -k -s pss` |

核心原则：看 available 不看 free，看 si/so 判断饱和度，用 PSS 替代 RSS 做容量评估。
