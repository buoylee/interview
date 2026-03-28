# 磁盘观测工具

磁盘 I/O 是后端系统最常见的瓶颈之一，尤其是数据库、日志密集型服务和文件处理系统。磁盘瓶颈的表现往往不是"磁盘满了"，而是"I/O 延迟高导致应用变慢"。本文介绍 Linux 下的磁盘观测和基准测试工具。

## iostat -xz 1 — 磁盘性能核心工具

`iostat` 是磁盘性能分析的首选工具。`-x` 显示扩展统计，`-z` 隐藏无活动的设备。

```bash
$ iostat -xz 1 3
Linux 5.15.0    01/15/2024    _x86_64_

avg-cpu:  %user   %nice %system %iowait  %steal   %idle
          35.21    0.00   12.34    8.45    0.00   43.99

Device     r/s     w/s    rkB/s    wkB/s  rrqm/s  wrqm/s  r_await  w_await  await  avgqu-sz  %util
sda      250.00  800.00  8000.0  32000.0   12.00   45.00     1.20    12.50   9.85      10.3   97.6
sdb        2.00    5.00    64.0    160.0    0.00    1.00     0.50     1.20   0.95       0.01    0.7
nvme0n1  450.00  200.00 14400.0   6400.0    0.00    0.00     0.08     0.12   0.09       0.06    4.2
```

### 关键列详解

| 列 | 含义 | 关注阈值 |
|----|------|----------|
| **r/s, w/s** | 每秒读/写请求数（IOPS） | 对比磁盘规格上限 |
| **rkB/s, wkB/s** | 每秒读/写吞吐量 | 对比磁盘带宽上限 |
| **rrqm/s, wrqm/s** | 每秒合并的读/写请求 | 合并率高说明有顺序 I/O |
| **r_await** | 读请求平均等待时间（ms） | SSD < 1ms, HDD < 10ms |
| **w_await** | 写请求平均等待时间（ms） | SSD < 1ms, HDD < 10ms |
| **await** | 读写综合平均等待时间（ms） | 核心延迟指标 |
| **avgqu-sz** | 平均 I/O 队列长度 | > 1 说明有排队 |
| **%util** | 磁盘繁忙度百分比 | 接近 100% 说明满载 |

### 如何判断磁盘是否是瓶颈

分析上面的输出：

**sda（机械硬盘）**：
- %util = 97.6% → 几乎满载
- await = 9.85ms → 对 HDD 来说正常偏高
- w_await = 12.5ms → 写延迟明显高于读延迟
- avgqu-sz = 10.3 → 平均 10 个请求在排队，严重饱和
- 结论：**sda 是瓶颈**

**nvme0n1（NVMe SSD）**：
- %util = 4.2% → 非常空闲
- await = 0.09ms → 极低延迟
- avgqu-sz = 0.06 → 几乎没有排队
- 结论：NVMe 完全不是瓶颈

### %util 的误区

对于现代 SSD 和 NVMe，%util = 100% **不一定**代表瓶颈。因为这些设备支持并行处理多个 I/O 请求（队列深度 > 1），%util 只表示"有 I/O 在处理"，不代表"处理不过来"。

**正确判断**：看 await 和 avgqu-sz。如果 %util 接近 100% 但 await 很低，说明磁盘虽然一直在忙但处理得过来。

```
磁盘瓶颈判断矩阵:
┌──────────┬───────────┬──────────┬─────────────────────────┐
│ %util    │  await    │ avgqu-sz │         结论             │
├──────────┼───────────┼──────────┼─────────────────────────┤
│ < 70%    │  低       │  < 1     │ 正常                    │
│ > 90%    │  低       │  < 2     │ 繁忙但不饱和(SSD 常见)   │
│ > 90%    │  高       │  > 4     │ 磁盘饱和，是瓶颈        │
│ < 50%    │  高       │  > 1     │ 磁盘本身有问题(硬件故障) │
└──────────┴───────────┴──────────┴─────────────────────────┘
```

## iotop — 逐进程 I/O 监控

找到哪个进程在做大量 I/O。

```bash
$ sudo iotop -oP
Total DISK READ :      45.23 M/s | Total DISK WRITE :      32.56 M/s
Actual DISK READ:      45.23 M/s | Actual DISK WRITE:      38.12 M/s

  PID  PRIO  USER     DISK READ  DISK WRITE  SWAPIN     IO>    COMMAND
 3421  be/4  app      12.34 M/s   8.56 M/s   0.00 %  65.42 %  java -Xmx4g
 1892  be/4  mysql    28.45 M/s   2.34 M/s   0.00 %  34.21 %  mysqld
 5634  be/4  root      4.44 M/s  21.66 M/s   0.00 %  12.34 %  rsync --progress
```

参数说明：
- `-o`：只显示有 I/O 活动的进程（Otherwise output 太多）
- `-P`：显示进程而不是线程

**IO>** 列是进程等待 I/O 的时间占比，类似 CPU 的 iowait。65.42% 说明 java 进程有 65% 的时间在等 I/O。

```bash
# 只看磁盘写入最大的进程
$ sudo iotop -oP -a    # -a 累计模式
```

## blktrace + blkparse — 块设备级追踪

当 iostat 和 iotop 的粒度不够时，用 blktrace 做块设备级的详细追踪。

```bash
# 开始追踪（追踪 10 秒）
$ sudo blktrace -d /dev/sda -o trace -w 10

# 解析追踪结果
$ blkparse -i trace.blktrace.0 | head -20
  8,0    0        1     0.000000000  3421  Q   W 123456 + 8 [java]
  8,0    0        2     0.000001234  3421  G   W 123456 + 8 [java]
  8,0    0        3     0.000002345  3421  I   W 123456 + 8 [java]
  8,0    0        4     0.000005678  3421  D   W 123456 + 8 [java]
  8,0    0        5     0.000125678  3421  C   W 123456 + 8 [0]
```

I/O 生命周期中的事件：
```
Q (Queue)     → 请求进入块层队列
G (Get)       → 分配请求结构
I (Insert)    → 插入 I/O 调度器队列
D (Dispatch)  → 发送给磁盘驱动
C (Complete)  → I/O 完成

Q → G → I → D → C
│              │
└──── await ───┘  （iostat 中的 await 就是这段时间）
```

```bash
# 用 btt 分析延迟分布
$ btt -i trace.blktrace.0
==================== All Coverage ====================
            Q2Q        Q2G        G2I        I2D        D2C
MIN         0.0001     0.0000     0.0001     0.0001     0.0002
AVG         0.0038     0.0001     0.0003     0.0002     0.0032
MAX         0.1234     0.0012     0.0045     0.0023     0.0956
```

D2C（Dispatch to Complete）= 磁盘实际服务时间。如果 D2C 高但 I2D 正常，说明磁盘本身慢。如果 I2D 高但 D2C 正常，说明 I/O 调度器有问题。

## lsof — 打开文件列表

`lsof`（list open files）用于排查文件相关问题。

```bash
# 查看某个进程打开的所有文件
$ lsof -p 3421 | head -20
COMMAND  PID USER   FD   TYPE DEVICE  SIZE/OFF    NODE NAME
java    3421  app  cwd    DIR  253,1      4096 1234567 /opt/app
java    3421  app  txt    REG  253,1  12345678 2345678 /usr/bin/java
java    3421  app    0u   CHR  136,0       0t0       3 /dev/pts/0
java    3421  app    1w   REG  253,1 234567890 3456789 /var/log/app/app.log
java    3421  app    5u  IPv4 45678       0t0     TCP *:8080 (LISTEN)
java    3421  app    8u  IPv4 56789       0t0     TCP 10.0.0.1:8080->10.0.0.2:45678 (ESTABLISHED)
java    3421  app   12u  IPv4 67890       0t0     TCP 10.0.0.1:54321->10.0.0.3:3306 (ESTABLISHED)

# 统计进程打开的文件数
$ lsof -p 3421 | wc -l
2345
```

### 排查文件泄漏

如果进程打开文件数持续增长，可能是文件句柄泄漏：

```bash
# 查看进程的文件描述符数量
$ ls /proc/3421/fd | wc -l
2341

# 查看文件描述符限制
$ cat /proc/3421/limits | grep "open files"
Max open files            65536                65536                files

# 找出被删除但仍被持有的文件（占用磁盘空间但 ls 看不到）
$ lsof -p 3421 | grep deleted
java    3421  app   15w   REG  253,1 1234567890 4567890 /var/log/app/old.log (deleted)
```

上面最后一行：old.log 已被删除（如 logrotate 删除了旧日志），但进程仍然持有文件句柄。文件实际空间不会释放，直到进程关闭该句柄。这是"磁盘空间被占用但 du/df 对不上"的经典原因。

```bash
# 查看哪个进程在使用某个文件
$ lsof /var/log/app/app.log
COMMAND  PID USER   FD   TYPE DEVICE SIZE/OFF    NODE NAME
java    3421  app    1w   REG  253,1 234567890 3456789 /var/log/app/app.log

# 查看哪个进程在监听某个端口
$ lsof -i :8080
COMMAND  PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
java    3421  app    5u  IPv4  45678      0t0  TCP *:8080 (LISTEN)
```

## fio — 磁盘性能基准测试

`fio` 是标准的磁盘基准测试工具。当你怀疑磁盘性能有问题时，用 fio 测试磁盘的理论性能。

### 常用测试场景

```bash
# 测试顺序读吞吐量
$ fio --name=seq-read --ioengine=libaio --direct=1 --bs=128k \
      --size=1G --numjobs=1 --rw=read --runtime=30 --time_based

seq-read: (groupid=0, jobs=1): err= 0
  read: IOPS=3245, BW=405MiB/s (425MB/s)
    slat (usec): min=2, max=134, avg=4.52
    clat (usec): min=45, max=2345, avg=302.34
     lat (usec): min=48, max=2348, avg=306.86
    bw (  KiB/s): min=380000, max=425000, per=100.00%, avg=414720
```

```bash
# 测试随机读 IOPS（模拟数据库负载）
$ fio --name=rand-read --ioengine=libaio --direct=1 --bs=4k \
      --size=1G --numjobs=4 --iodepth=32 --rw=randread --runtime=30 --time_based

rand-read: (groupid=0, jobs=4): err= 0
  read: IOPS=95234, BW=372MiB/s (390MB/s)
    clat (usec): min=25, max=8234, avg=134.56
     lat (usec): min=25, max=8235, avg=134.78
    clat percentiles (usec):
     |  1.00th=[   42],  5.00th=[   56], 10.00th=[   68],
     | 50.00th=[  112], 90.00th=[  212], 95.00th=[  298],
     | 99.00th=[  578], 99.50th=[  812], 99.90th=[ 2345],
     | 99.95th=[ 4234], 99.99th=[ 6890]
```

### 关键参数说明

| 参数 | 含义 | 常用值 |
|------|------|--------|
| `--ioengine` | I/O 引擎 | `libaio`（Linux 异步 I/O） |
| `--direct=1` | 绕过 Page Cache | 测试磁盘真实性能时必须设置 |
| `--bs` | 块大小 | 4k（IOPS 测试）、128k/1M（吞吐测试） |
| `--rw` | 读写模式 | read/write/randread/randwrite/randrw |
| `--numjobs` | 并发任务数 | 模拟并发 I/O |
| `--iodepth` | 每个任务的 I/O 队列深度 | NVMe 测试时设大（32-128） |
| `--size` | 测试文件大小 | 大于内存才能避免 Cache 影响 |
| `--runtime` | 测试时长（秒） | 至少 30 秒 |

### 典型参考值

```
设备类型         顺序读带宽      4K 随机读 IOPS    4K 随机读延迟
──────────────────────────────────────────────────────────────
7200rpm HDD     ~150 MB/s       ~100              ~10ms
15000rpm HDD    ~200 MB/s       ~200              ~5ms
SATA SSD        ~550 MB/s       ~80,000           ~0.1ms
NVMe SSD        ~3,500 MB/s     ~500,000          ~0.05ms
```

如果 fio 测出来的结果远低于上表的参考值，说明磁盘可能有硬件问题，或者 I/O 调度器配置不当。

## 排查流程总结

```
iostat -xz 1 → %util 高且 await 高？
    │
    ├─ 是 → iotop -oP → 哪个进程在做大量 I/O？
    │        │
    │        ├─ 已知进程 → 应用层优化（加缓存、减少 I/O）
    │        │
    │        └─ 未知进程 → lsof -p <pid> 看在读写什么文件
    │
    ├─ await 高但 %util 不高 → 磁盘可能有硬件问题
    │                         → fio 基准测试验证
    │                         → smartctl -a 检查健康状态
    │
    └─ 否 → 磁盘不是瓶颈
```

## 小结

| 工具 | 用途 | 关键指标 | 速览命令 |
|------|------|----------|----------|
| iostat -xz | 磁盘性能统计 | await/%util/avgqu-sz | `iostat -xz 1` |
| iotop | 逐进程 I/O | DISK READ/WRITE | `sudo iotop -oP` |
| blktrace | 块设备追踪 | I/O 生命周期各阶段延迟 | `sudo blktrace -d /dev/sda -w 10` |
| lsof | 打开文件列表 | 文件描述符数量/deleted 文件 | `lsof -p <pid>` |
| fio | 基准测试 | IOPS/带宽/延迟 | `fio --name=test ...` |

核心判断：%util 高是必要条件但不充分，await 和 avgqu-sz 才是判断磁盘饱和度的关键。对 SSD/NVMe，尤其不能只看 %util。
