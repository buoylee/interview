# 内存管理

> 理解虚拟内存、页表、Page Fault、Swap 和 OOM Killer，是分析内存类性能问题的基础。很多线上事故的根因都在这里。

---

## 1. 虚拟内存：为什么需要

每个进程都以为自己独占全部内存空间，这是虚拟内存机制提供的抽象。

### 没有虚拟内存的问题

- 多个进程直接操作物理内存，互相覆盖数据
- 一个进程的 bug 能搞崩整个系统
- 无法运行总内存需求超过物理内存的程序

### 虚拟内存提供的三大保障

1. **隔离**：每个进程有独立的地址空间，互不影响
2. **超额分配**：可以分配超过物理内存的虚拟空间（配合 Swap 或 demand paging）
3. **共享**：多个进程可以映射同一段物理内存（共享库、mmap）

### 进程地址空间布局（64-bit Linux）

```
高地址
┌──────────────────┐ 0x7FFF_FFFF_FFFF
│    内核空间        │ (用户不可访问)
├──────────────────┤
│       栈 ↓        │ 主线程栈，向低地址增长
│                   │ 默认 8MB (ulimit -s)
├──────────────────┤
│                   │
│   内存映射区域 ↓   │ mmap, 共享库, 线程栈
│                   │
├──────────────────┤
│       堆 ↑        │ malloc/new，向高地址增长
│                   │ brk/sbrk 管理
├──────────────────┤
│    BSS 段         │ 未初始化的全局变量
├──────────────────┤
│    数据段         │ 已初始化的全局变量
├──────────────────┤
│    代码段         │ .text（只读，可执行）
└──────────────────┘ 0x0000_0040_0000
低地址
```

```bash
# 查看进程的内存映射
cat /proc/<pid>/maps

# 或更友好的格式
pmap -x <pid>

# 查看进程的内存使用汇总
cat /proc/<pid>/status | grep -i vm
# VmPeak: 虚拟内存峰值
# VmRSS:  常驻物理内存（真正占用的物理内存）
# VmSwap: 被交换到磁盘的内存
```

---

## 2. 页表与 TLB

虚拟地址到物理地址的翻译通过**页表（Page Table）**完成。Linux 使用 4KB 页面大小。

### 多级页表

64-bit 系统使用 4 级（或 5 级）页表，避免一张巨大的单层页表浪费内存：

```
虚拟地址 (48-bit 有效)
┌────────┬────────┬────────┬────────┬──────────┐
│ PGD(9) │ PUD(9) │ PMD(9) │ PTE(9) │Offset(12)│
└───┬────┴───┬────┴───┬────┴───┬────┴─────┬────┘
    │        │        │        │          │
    ▼        ▼        ▼        ▼          │
   PGD表 → PUD表 → PMD表 → PTE表 ────→ 物理页帧 + 偏移

每次虚拟地址翻译需要 4 次内存访问（查 4 级页表）→ 非常慢！
```

### TLB（Translation Lookaside Buffer）

TLB 是 CPU 内部的页表缓存，命中 TLB 时地址翻译只需 1 个时钟周期。

| 项目 | 典型值 |
|------|-------|
| L1 TLB 容量 | 64-128 条目 |
| L2 TLB 容量 | 512-2048 条目 |
| TLB Hit 延迟 | ~1 ns |
| TLB Miss 延迟 | ~20-30 ns（Page Walk，查 4 级页表） |

**TLB Miss 代价高昂**。进程使用的内存越分散、页面数越多，TLB Miss 率越高。

### 大页（Huge Pages）

默认 4KB 页面意味着 1GB 内存需要 262144 个页表条目。使用 2MB 大页可以减少到 512 个，极大降低 TLB Miss：

```bash
# 查看当前大页配置
cat /proc/meminfo | grep Huge

# 预留 1024 个 2MB 大页（共 2GB）
echo 1024 > /proc/sys/vm/nr_hugepages

# Java 使用大页
java -XX:+UseTransparentHugePages -jar app.jar
# 或使用显式大页
java -XX:+UseLargePages -XX:LargePageSizeInBytes=2m -jar app.jar

# THP（Transparent Huge Pages）状态
cat /sys/kernel/mm/transparent_hugepage/enabled
# [always] madvise never
```

**生产注意**：THP 在某些数据库场景（Redis、MongoDB）会导致延迟抖动，这些服务通常建议关闭 THP。

---

## 3. Page Fault（缺页异常）

进程访问的虚拟页面不在物理内存中时，触发 Page Fault。CPU 暂停当前指令，切换到内核态处理。

### Minor Page Fault（次要缺页）

物理页面在内存中但未建立映射（例如新分配的匿名页面首次写入、共享库已在 Page Cache 中）。处理只需更新页表，代价约 **1-5 us**。

### Major Page Fault（主要缺页）

物理页面不在内存中，需要从磁盘读取（从 Swap 读回、或从文件系统读取 mmap 映射的文件）。涉及磁盘 I/O，代价约 **1-10 ms**（HDD）或 **0.1-1 ms**（SSD）。

```
Minor Fault:  虚拟页 → 页表无映射 → 内核分配物理页 + 建立映射 → 完成
Major Fault:  虚拟页 → 页表无映射 → 内核从磁盘读入物理页 → 建立映射 → 完成
                                           ↑ 磁盘 I/O，非常慢
```

```bash
# 查看进程的 Page Fault 统计
ps -o pid,min_flt,maj_flt,cmd -p <pid>
# min_flt: Minor Page Fault 累计次数
# maj_flt: Major Page Fault 累计次数

# 实时监控
pidstat -r 1 -p <pid>
# minflt/s: 每秒 Minor Fault
# majflt/s: 每秒 Major Fault（> 0 就需要关注）
```

**性能影响**：Java 服务启动时 Minor Fault 很多是正常的（JVM 分配堆内存）。但运行期间出现大量 Major Fault 通常意味着内存不足触发了 Swap。

---

## 4. Swap 机制

Swap 是内存不足时将不活跃的内存页面交换到磁盘的机制。

### swappiness 参数

```bash
# 查看当前值
cat /proc/sys/vm/swappiness
# 默认 60

# 含义：
# swappiness = 0   → 尽量不 Swap（OOM 前的最后手段）
# swappiness = 60  → 默认值，倾向保留 Page Cache
# swappiness = 100 → 积极 Swap

# 临时修改
sysctl vm.swappiness=10

# 永久修改
echo "vm.swappiness=10" >> /etc/sysctl.conf
sysctl -p
```

### 为什么生产环境通常关闭或极低化 Swap

1. **延迟不可预测**：一个 Major Page Fault 导致毫秒级延迟，对在线服务来说不可接受
2. **GC 灾难**：JVM GC 需要扫描整个堆，如果堆的一部分被 Swap Out，GC 触发海量 Major Fault，一次 GC 可能从几十毫秒变成几十秒
3. **级联效应**：一个进程 Swap 慢 → 上游超时 → 重试 → 负载飙升 → 更多 Swap → 系统雪崩
4. **假象**：Swap 让进程不被 OOM Kill，但其实已经无法正常提供服务，不如尽早 OOM 让监控报警并快速重启

```bash
# 查看当前 Swap 使用
free -h
swapon --show

# 查看哪些进程在用 Swap
for f in /proc/[0-9]*/status; do
  awk '/^(Name|VmSwap)/{printf "%s ", $2}' "$f" 2>/dev/null
  echo
done | sort -k2 -n -r | head -10

# 生产建议：设置 swappiness=1（不是 0，0 在某些内核版本会完全禁用）
sysctl vm.swappiness=1
```

---

## 5. OOM Killer

当内存真正耗尽（且 Swap 也不够或已关闭）时，内核的 OOM Killer 会选择一个进程杀掉以释放内存。

### 评分机制

每个进程有一个 `oom_score`（0-1000），得分越高越容易被杀：

```bash
# 查看进程的 OOM 分数
cat /proc/<pid>/oom_score

# 查看调整值
cat /proc/<pid>/oom_score_adj
# 范围 -1000 到 1000
# -1000: 永不被 OOM Kill
#     0: 默认
#  1000: 最优先被 Kill
```

### 评分计算因子

- 进程占用的 RSS 内存越大，分数越高
- 子进程的内存也计入
- `oom_score_adj` 可以人为调整

### 生产配置建议

```bash
# 保护关键服务（如数据库）不被 OOM Kill
echo -1000 > /proc/$(pidof mysqld)/oom_score_adj

# 让辅助进程优先被杀
echo 500 > /proc/$(pidof log-collector)/oom_score_adj

# 查看 OOM Kill 日志
dmesg | grep -i "oom"
journalctl -k | grep -i "oom"
```

**常见误区**：把所有服务都设为 -1000 是没有意义的。OOM 的根因是内存不够，设置 -1000 只是避免被杀，但系统仍然会因为内存不足而表现异常。正确做法是合理规划内存用量。

---

## 6. NUMA 内存策略

在 NUMA 架构下，内存分配策略对性能有显著影响：

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| local | 优先在本地节点分配 | 默认策略，适合大多数场景 |
| bind | 只在指定节点分配 | 绑定特定节点 |
| interleave | 轮流在各节点分配 | 内存带宽密集型（如大内存数据库） |
| preferred | 优先指定节点，不够则其他节点 | 软约束 |

```bash
# 查看 NUMA 拓扑
numactl --hardware

# 查看内存分配统计
numastat

# 绑定进程到 Node 0
numactl --cpunodebind=0 --membind=0 java -jar app.jar

# 交错分配（适合 Redis 等需要大内存带宽的场景）
numactl --interleave=all redis-server /etc/redis.conf
```

### Local vs Remote 访问的性能差异

```
NUMA Node 0 上的进程访问 Node 0 的内存: ~65ns
NUMA Node 0 上的进程访问 Node 1 的内存: ~120ns (慢 ~85%)
```

**真实案例**：某 Java 服务 GC 耗时不稳定，排查发现堆内存跨 NUMA 节点分配。绑定 NUMA 节点后 GC P99 从 200ms 降到 80ms。

```bash
# 监控 NUMA miss（远程访问）次数
numastat -p <pid>
# 关注 other_node 列，值越大说明跨节点访问越多
```

---

## 7. 实用诊断命令速查

```bash
# 系统内存全貌
free -h

# 详细内存信息
cat /proc/meminfo

# 进程内存详情
pmap -x <pid>

# 进程 RSS/VSZ 排行
ps aux --sort=-rss | head -20

# 内存分配追踪（glibc malloc）
MALLOC_TRACE=/tmp/mtrace.log LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libc.so.6 ./app
mtrace ./app /tmp/mtrace.log

# 持续监控内存使用变化
pidstat -r 1 -p <pid>

# 查看 slab 缓存（内核内存分配）
slabtop

# 清除 Page Cache（测试用，生产慎用）
sync && echo 3 > /proc/sys/vm/drop_caches
```

---

## 要点总结

1. **虚拟内存提供隔离和超额分配**——`VmRSS` 才是真正的物理内存占用，`VmSize` 不用太担心。
2. **TLB Miss 代价高**——大内存应用考虑大页（Huge Pages），但要注意 THP 对某些数据库的负面影响。
3. **Major Page Fault 意味着磁盘 I/O**——运行期间出现大量 Major Fault 几乎肯定是 Swap 导致，需立即关注。
4. **生产环境应极低化 Swap**——设置 `swappiness=1`，让 OOM Kill 暴露问题而不是让 Swap 拖垮整个系统。
5. **OOM Killer 保护关键进程**——但根本解决方案是合理规划内存，不是把所有进程都设 -1000。
6. **NUMA 对大内存服务影响显著**——JVM、Redis 等应绑定 NUMA 节点或使用 interleave 策略。
