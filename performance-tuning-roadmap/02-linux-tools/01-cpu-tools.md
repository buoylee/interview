# CPU 观测工具

CPU 是最常见的性能瓶颈之一。本文介绍 Linux 下从粗粒度到细粒度的 CPU 观测工具，帮你回答三个问题：CPU 忙不忙？谁在用 CPU？在做什么？

## uptime — 系统负载速览

`uptime` 是最简单的起手式，一条命令看系统整体负载。

```bash
$ uptime
 10:35:21 up 45 days,  3:12,  2 users,  load average: 4.52, 3.21, 1.85
```

### load average 三个数字的含义

- **4.52**：最近 1 分钟的平均负载
- **3.21**：最近 5 分钟的平均负载
- **1.85**：最近 15 分钟的平均负载

Load average 代表的是**正在运行 + 等待运行的任务数**（在 Linux 上还包括不可中断状态的 I/O 等待任务）。

### 与 CPU 核数的关系

判断标准取决于 CPU 核心数：

```bash
# 先查看 CPU 核心数
$ nproc
4
```

| 场景 | load average | 含义 |
|------|-------------|------|
| 4 核，load = 1.0 | 25% 利用率 | 很空闲 |
| 4 核，load = 4.0 | 100% 利用率 | 刚好满载 |
| 4 核，load = 8.0 | 200% 利用率 | 严重过载，有任务在排队 |

**解读趋势**：上面的例子 4.52 → 3.21 → 1.85（从右往左看），说明负载在**上升**。1 分钟负载远高于 15 分钟负载，表明最近有突发压力。

## top / htop — 实时系统概况

```bash
$ top
top - 10:36:01 up 45 days,  3:12,  2 users,  load average: 4.52, 3.21, 1.85
Tasks: 312 total,   3 running, 309 sleeping,   0 stopped,   0 zombie
%Cpu(s): 65.2 us,  12.3 sy,  0.0 ni, 15.8 id,  5.1 wa,  0.0 hi,  1.6 si,  0.0 st
MiB Mem :  15921.5 total,   1024.3 free,  12453.8 used,   2443.4 buff/cache
MiB Swap:   4096.0 total,   3584.0 free,    512.0 used.   2890.1 avail Mem

  PID USER      PR  NI    VIRT    RES    SHR S  %CPU %MEM     TIME+ COMMAND
 3421 app       20   0 8.452g 2.1g  34512 S  185.2 13.5  42:15.38 java
 1892 mysql     20   0 4.231g 1.8g  28940 S   45.3 11.6  28:42.11 mysqld
  892 root      20   0  325.4m 12.3m  8452 S    8.2  0.1   5:23.45 kubelet
```

### CPU 状态行各字段含义

```
%Cpu(s): 65.2 us, 12.3 sy, 0.0 ni, 15.8 id, 5.1 wa, 0.0 hi, 1.6 si, 0.0 st
```

| 缩写 | 全称 | 含义 | 高时说明什么 |
|------|------|------|-------------|
| **us** | user | 用户态 CPU 时间 | 应用代码在消耗 CPU（正常情况） |
| **sy** | system | 内核态 CPU 时间 | 大量系统调用、内核路径开销（sy > 20% 需要排查） |
| **ni** | nice | 低优先级用户态 | 有 nice 过的进程在运行 |
| **id** | idle | 空闲 | CPU 空闲 |
| **wa** | iowait | I/O 等待 | CPU 在等磁盘/网络 I/O（wa 高要查磁盘） |
| **hi** | hardirq | 硬中断 | 硬件中断处理 |
| **si** | softirq | 软中断 | 网络包处理、定时器等（si 高常见于高流量服务器） |
| **st** | steal | 被虚拟化偷走 | 虚拟机/容器 CPU 被宿主机抢占（云主机常见） |

### 快速判断

- **us 高**：应用代码消耗 CPU，用 profiling 工具（perf）找热点函数
- **sy 高**：内核开销大，可能是大量系统调用、锁竞争、上下文切换多
- **wa 高**：I/O 等待，去查磁盘性能
- **st 高**：换更好的云主机实例，或者联系云厂商

## mpstat -P ALL — 逐核 CPU 利用率

`top` 的 CPU 行是所有核心的汇总。如果某个核心过载而其他核心空闲，`top` 看不出来。

```bash
$ mpstat -P ALL 1 3
Linux 5.15.0    01/15/2024    _x86_64_

10:38:01 AM  CPU    %usr   %nice    %sys %iowait   %irq   %soft  %steal  %idle
10:38:02 AM  all    35.2    0.00    8.3     2.1    0.00    1.5     0.0   52.9
10:38:02 AM    0    95.0    0.00    5.0     0.0    0.00    0.0     0.0    0.0
10:38:02 AM    1     8.0    0.00    3.0     0.0    0.00    0.0     0.0   89.0
10:38:02 AM    2    22.0    0.00   12.0     4.0    0.00    5.0     0.0   57.0
10:38:02 AM    3    16.0    0.00   13.0     4.0    0.00    1.0     0.0   66.0
```

**CPU 0 利用率 100%，其他核心很空闲。** 这是典型的单线程瓶颈或中断集中在一个核心。

常见原因：
- 单线程应用（如 Node.js 单进程、Redis）
- 网络中断没有做 IRQ 亲和性分配（所有网络中断都由 CPU 0 处理）
- 软中断（`%soft` 高）集中在一个核心

**排查 IRQ 分配：**
```bash
$ cat /proc/interrupts | head -5
           CPU0       CPU1       CPU2       CPU3
  0:         42          0          0          0   IO-APIC   2-edge      timer
  8:          0          0          0          0   IO-APIC   8-edge      rtc0
 24:   12456789          0          0          0   PCI-MSI 524288-edge   eth0-0
```

如果网卡中断全在 CPU 0 上，可以用 `irqbalance` 或手动设置 SMP affinity 分散。

## pidstat -u — 逐进程 CPU 使用

```bash
$ pidstat -u 1 3
Linux 5.15.0    01/15/2024    _x86_64_

10:40:01 AM   UID       PID    %usr %system  %guest   %wait    %CPU   CPU  Command
10:40:02 AM  1000      3421   152.0    33.0    0.00    12.0   185.0     0  java
10:40:02 AM    27      1892    35.0    10.3    0.00     2.0    45.3     2  mysqld
10:40:02 AM     0       892     5.2     3.0    0.00     0.5     8.2     1  kubelet
10:40:02 AM  1000      4521     2.0     1.0    0.00     0.0     3.0     3  python3
```

各列含义：
- **%usr**：用户态 CPU 使用率
- **%system**：内核态 CPU 使用率
- **%wait**：等待 CPU 的时间比例（被调度器延迟）
- **%CPU**：总 CPU 使用率（多核时可以超过 100%）

**%wait 高**说明该进程想用 CPU 但拿不到时间片，通常是因为 CPU 过载或被其他高优先级进程抢占。

```bash
# 查看某个进程的线程级 CPU 使用
$ pidstat -u -t -p 3421 1 3
10:41:01 AM   UID      TGID       TID    %usr %system   %CPU  Command
10:41:02 AM  1000      3421         -    152.0   33.0   185.0  java
10:41:02 AM  1000         -      3422     45.0    8.0    53.0  |__java
10:41:02 AM  1000         -      3423     42.0    7.5    49.5  |__java
10:41:02 AM  1000         -      3424     38.0    9.0    47.0  |__java
10:41:02 AM  1000         -      3425     27.0    8.5    35.5  |__java
```

`-t` 参数显示线程级别的 CPU 使用，对排查 Java/Go 多线程应用非常有用。

## vmstat 1 — 系统级概况与 CPU 饱和度

```bash
$ vmstat 1 5
procs -----------memory---------- ---swap-- -----io---- -system-- ------cpu-----
 r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st
 8  0      0 512340  21456 894520    0    0     4    12  3421 5234 65 12 16  5  0
12  1      0 508212  21456 894520    0    0     0    28  3856 5890 70 14 10  5  0
15  0      0 504100  21456 894520    0    0     0     8  4102 6120 72 15  8  4  0
 9  0      0 510234  21456 894520    0    0     4    16  3245 4892 58 11 25  5  0
 6  0      0 513456  21456 894520    0    0     0    12  2890 4234 45 10 40  4  0
```

### 关键列

| 列 | 含义 | 关注点 |
|----|------|--------|
| **r** | 运行队列长度（等待 CPU 的进程数） | r > CPU 核数说明 CPU 饱和 |
| **b** | 不可中断睡眠的进程数 | b 高通常是磁盘 I/O 阻塞 |
| **in** | 每秒中断数 | 突然增高可能是网络流量暴涨 |
| **cs** | 每秒上下文切换数 | cs 高说明线程切换频繁，可能是锁竞争 |
| **us/sy/id/wa/st** | CPU 状态百分比 | 同 top |

**判断 CPU 饱和度**：r 列持续 > CPU 核心数，说明 CPU 是瓶颈。上面的例子在 4 核机器上 r 最高到 15，严重饱和。

**上下文切换（cs）分析**：
```bash
# 进一步查看自愿/非自愿上下文切换
$ pidstat -w -p 3421 1 3
10:43:01 AM   UID       PID   cswch/s nvcswch/s  Command
10:43:02 AM  1000      3421   15234.0    8921.0  java
```

- **cswch/s**（voluntary）：自愿切换，进程主动让出 CPU（如等待 I/O、sleep、锁等待）
- **nvcswch/s**（non-voluntary）：非自愿切换，被调度器强制切走（CPU 时间片用完）

nvcswch/s 高说明 CPU 竞争激烈，进程还想用 CPU 但被抢走了。

## /proc/stat — CPU 底层统计

所有上层工具的数据来源。了解它有助于理解工具输出的含义。

```bash
$ cat /proc/stat | head -6
cpu  1025438 234 542341 8234521 234521 0 85231 0 0 0
cpu0  312456 56 152342 1823451 52341 0 42321 0 0 0
cpu1  245231 78 132456 2123456 62345 0 15234 0 0 0
cpu2  234521 45 128765 2145123 58234 0 14523 0 0 0
cpu3  233230 55 128778 2142491 61601 0 13153 0 0 0
```

各列依次是：user, nice, system, idle, iowait, irq, softirq, steal, guest, guest_nice。

单位是 jiffies（时钟滴答数），工具通过对比两次采样的差值来计算百分比。

## 排查流程总结

```
                     uptime
                       │
                 load average 高？
                   ╱         ╲
                 是            否
                 │              └── 问题可能不在 CPU
                 ▼
              vmstat 1
                 │
          r 列 > CPU 核数？
            ╱         ╲
          是            否
          │              └── CPU 不饱和，wa 高则查磁盘
          ▼
       mpstat -P ALL 1
          │
    某个核心 100%，其他空闲？
         ╱           ╲
       是              否（均匀分布）
       │                └── pidstat -u 找消耗最大的进程
       │                    → perf/火焰图找热点函数
       ▼
  单线程瓶颈或 IRQ 不均
  → 检查 /proc/interrupts
  → 检查应用是否单线程
```

## 小结

| 工具 | 用途 | 粒度 | 速览命令 |
|------|------|------|----------|
| uptime | 系统负载概览 | 系统级 | `uptime` |
| top/htop | 实时进程排名 | 系统/进程 | `top -bn1` |
| mpstat | 逐核 CPU 利用率 | per-CPU | `mpstat -P ALL 1` |
| pidstat | 逐进程/线程 CPU | 进程/线程 | `pidstat -u -t 1` |
| vmstat | CPU 饱和度 + 上下文切换 | 系统级 | `vmstat 1` |
| /proc/stat | 底层原始数据 | 系统级 | `cat /proc/stat` |

排查顺序：uptime（有没有问题）→ vmstat（饱和了没有）→ mpstat（哪个核心忙）→ pidstat（哪个进程/线程忙）→ perf（在忙什么）。
