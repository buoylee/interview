# eBPF 入门

## eBPF 是什么

eBPF（extended Berkeley Packet Filter）是 Linux 内核中的一个革命性技术。简单来说，它允许你在**不修改内核源码、不加载内核模块**的情况下，在内核中运行自定义程序。

```
┌───────────────────────────────────────────────┐
│                 用户空间                        │
│                                               │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐ │
│   │  bcc 工具 │   │ bpftrace │   │ 自定义程序 │ │
│   └─────┬────┘   └─────┬────┘   └─────┬────┘ │
│         │              │              │       │
├─────────┼──────────────┼──────────────┼───────┤
│         ▼              ▼              ▼       │
│   ┌─────────────────────────────────────────┐ │
│   │          eBPF 虚拟机 (内核空间)           │ │
│   │                                         │ │
│   │  ┌─────────┐  ┌──────┐  ┌───────────┐  │ │
│   │  │ 验证器   │→│ JIT  │→│ 挂载到      │  │ │
│   │  │(Verifier)│  │ 编译 │  │ 内核事件点  │  │ │
│   │  └─────────┘  └──────┘  └───────────┘  │ │
│   └─────────────────────────────────────────┘ │
│                    内核空间                     │
└───────────────────────────────────────────────┘
```

### 核心架构

1. **内核虚拟机**：eBPF 程序在内核中的一个虚拟机中执行，不直接运行在 CPU 上（编译后通过 JIT 会直接运行）
2. **安全沙箱**：每个 eBPF 程序在加载时必须通过验证器（Verifier）检查，确保不会崩溃内核、不会有死循环、不会访问非法内存
3. **JIT 编译**：通过验证后，eBPF 字节码会被 JIT 编译为原生机器码，执行效率接近内核原生代码

### 可以挂载的事件点

eBPF 程序可以挂载到内核中几乎任何位置：
- **kprobe/kretprobe**：内核函数入口/返回
- **uprobe/uretprobe**：用户态函数入口/返回
- **tracepoint**：内核预定义的追踪点
- **perf events**：硬件性能事件
- **socket/XDP**：网络数据包处理
- **cgroup**：容器资源控制

## 为什么 eBPF 比 strace/perf 更好

### 与 strace 对比

```
strace 的工作原理:
  进程 → ptrace() 拦截 → strace 处理 → 返回进程
  每个系统调用被拦截 2 次（进入 + 退出）
  开销: 5-10 倍性能下降

eBPF 的工作原理:
  系统调用 → 内核中直接执行 eBPF 程序 → 汇总数据到 map
  无 ptrace 上下文切换
  开销: < 1% 性能影响
```

| 维度 | strace | eBPF |
|------|--------|------|
| 性能开销 | 5-10 倍下降 | < 1% |
| 追踪范围 | 仅系统调用 | 任何内核/用户函数 |
| 数据聚合 | 无（逐行输出） | 内核中聚合（histogram/count） |
| 生产环境 | 高风险 | 安全可用 |
| 可编程性 | 不可编程 | 完全可编程 |

### 与 perf 对比

perf 已经很好了，但 eBPF 的优势在于**可编程性**。perf 只能按固定格式采样和输出，eBPF 可以在内核中编写任意逻辑来过滤、聚合、关联数据。

例如，"统计每个进程的 read 系统调用延迟分布"：
- perf：需要采样所有事件，用户态后处理
- eBPF：在内核中直接计算时间差并汇总到直方图，只输出最终结果

## bcc 工具集

bcc（BPF Compiler Collection）是一套基于 eBPF 的现成工具，安装即用，无需编写 eBPF 代码。

### execsnoop — 追踪进程执行

```bash
$ sudo execsnoop-bpfcc
PCOMM            PID    PPID   RET ARGS
bash             12345  3421     0 /bin/bash -c curl http://api.example.com
curl             12346  12345    0 /usr/bin/curl http://api.example.com
sh               12347  1892     0 /bin/sh -c /usr/bin/mysqldump ...
mysqldump        12348  12347    0 /usr/bin/mysqldump --databases mydb
cron             12349  1        0 /usr/sbin/cron
logrotate        12350  12349    0 /usr/sbin/logrotate /etc/logrotate.conf
```

显示系统中每个新创建的进程。用途：
- 排查"谁在偷偷执行什么"
- 发现意外的定时任务
- 排查短命进程（用 top/ps 看不到，因为执行完就退出了）

**实际案例**：某服务器 CPU 间歇性飙高，top 看不到可疑进程。用 execsnoop 发现每 5 秒会启动一个 Python 脚本做健康检查，脚本启动开销很大。

### biosnoop — 块 I/O 追踪

```bash
$ sudo biosnoop-bpfcc
TIME(s)     COMM           PID    DISK    T SECTOR     BYTES   LAT(ms)
0.000000    mysqld         1892   sda     R 12345678   4096      0.45
0.000234    mysqld         1892   sda     R 12345686   4096      0.38
0.001456    java           3421   sda     W 23456789   65536    12.34
0.002345    java           3421   sda     W 23456917   65536    15.67
0.005678    jbd2/sda1-8    456    sda     W 34567890   8192      2.34
```

每一行是一次块 I/O 操作。关键列：
- **T**：R=读、W=写
- **BYTES**：I/O 大小
- **LAT(ms)**：I/O 延迟

上面可以看到 java 进程的写 I/O 延迟 12-15ms，而 mysqld 的读 I/O 只有 0.4ms。如果 java 和 mysqld 共享一块磁盘，java 的大块写入可能影响 mysqld 的读性能。

### tcplife — TCP 连接生命周期

```bash
$ sudo tcplife-bpfcc
PID   COMM         LADDR           LPORT RADDR           RPORT TX_KB RX_KB  MS
3421  java         10.0.0.1        54321 10.0.0.4         3306     2    45  234
3421  java         10.0.0.1        54322 10.0.0.4         3306     1    12   56
3421  java         10.0.0.1        54323 10.0.0.5         6379     0     1    8
4521  python3      10.0.0.1        45678 10.0.0.6         8080    12    89  1234
4521  python3      10.0.0.1        45679 10.0.0.6         8080     8    45  2345
```

显示每个 TCP 连接的完整生命周期信息：谁连了谁、传了多少数据、存活了多久。

上面可以看到 python3 到 10.0.0.6:8080 的连接存活 1-2 秒且每次重新建立，说明没有用连接池（或连接池配置有问题）。

### opensnoop — 文件打开追踪

```bash
$ sudo opensnoop-bpfcc
PID    COMM          FD ERR PATH
3421   java           8   0 /opt/app/config/application.yml
3421   java           9   0 /tmp/app-cache/session-abc123.dat
3421   java          -1   2 /opt/app/data/missing-file.dat      ← 打开失败
1892   mysqld        12   0 /var/lib/mysql/mydb/orders.ibd
5634   logrotate      3   0 /var/log/app/app.log
```

ERR 列 = 2 对应 ENOENT（文件不存在）。如果大量文件打开失败，可能是配置错误或路径问题。

**实际案例**：一个 Java 应用每次请求都尝试打开一个不存在的配置文件（ERR=2），虽然代码有 fallback 逻辑，但大量失败的 open 系统调用浪费了 CPU。

## bpftrace — 单行脚本

bpftrace 是 eBPF 的高级追踪语言，类似 awk，可以用一行命令编写 eBPF 程序。

### 追踪 read 系统调用延迟分布

```bash
$ sudo bpftrace -e '
tracepoint:syscalls:sys_enter_read { @start[tid] = nsecs; }
tracepoint:syscalls:sys_exit_read /@start[tid]/ {
    @usecs = hist((nsecs - @start[tid]) / 1000);
    delete(@start[tid]);
}'

Attaching 2 probes...
^C

@usecs:
[0]                  12345 |@@@@@@@@@@@@@@@@@@@@@@@@@@                  |
[1]                  23456 |@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@|
[2, 4)               8901 |@@@@@@@@@@@@@@@@                            |
[4, 8)               3456 |@@@@@@                                      |
[8, 16)              1234 |@@                                          |
[16, 32)              567 |@                                           |
[32, 64)              234 |                                            |
[64, 128)              89 |                                            |
[128, 256)             45 |                                            |
[256, 512)             12 |                                            |
[512, 1K)               3 |                                            |
[1K, 2K)                1 |                                            |
```

这个直方图显示：大部分 read 调用在 0-4 微秒完成，但有少量达到毫秒级。直方图比平均值有价值得多。

### 更多 bpftrace 单行脚本

```bash
# 统计每个进程的系统调用次数
$ sudo bpftrace -e 'tracepoint:raw_syscalls:sys_enter { @[comm] = count(); }'

# 追踪 TCP 重传
$ sudo bpftrace -e 'kprobe:tcp_retransmit_skb { @retrans[comm] = count(); }'

# 统计 VFS read 延迟
$ sudo bpftrace -e '
kprobe:vfs_read { @start[tid] = nsecs; }
kretprobe:vfs_read /@start[tid]/ {
    @ns[comm] = hist(nsecs - @start[tid]);
    delete(@start[tid]);
}'

# 追踪进程的 malloc 大小分布
$ sudo bpftrace -e 'uprobe:/lib/x86_64-linux-gnu/libc.so.6:malloc {
    @malloc_size[comm] = hist(arg0);
}'
```

## 典型排查场景

### 场景一：排查短命进程导致的 CPU 飙高

```bash
# top 看不到可疑进程
$ sudo execsnoop-bpfcc -t
TIME     PCOMM        PID    PPID   RET ARGS
0.000    health.sh    12345  1234     0 /opt/scripts/health.sh
0.050    curl         12346  12345    0 /usr/bin/curl -s http://localhost:8080/health
0.100    jq           12347  12345    0 /usr/bin/jq .status
5.000    health.sh    12348  1234     0 /opt/scripts/health.sh
5.050    curl         12349  12348    0 /usr/bin/curl -s http://localhost:8080/health
```

每 5 秒启动一次 health.sh，fork+exec 开销明显。改用常驻进程或内嵌健康检查。

### 场景二：排查文件系统延迟

```bash
# 用 bpftrace 看 ext4 写入延迟
$ sudo bpftrace -e '
kprobe:ext4_file_write_iter { @start[tid] = nsecs; }
kretprobe:ext4_file_write_iter /@start[tid]/ {
    @write_latency_us = hist((nsecs - @start[tid]) / 1000);
    delete(@start[tid]);
}'
```

### 场景三：排查 DNS 查询延迟

```bash
$ sudo gethostlatency-bpfcc
TIME      PID    COMM          LATms HOST
10:45:01  3421   java           0.23 api.internal.svc
10:45:01  3421   java          45.67 unknown-host.example.com  ← DNS 查询 45ms!
10:45:02  4521   python3        0.12 redis.internal.svc
```

## 安装指南

### Ubuntu/Debian

```bash
# 安装 bcc 工具
$ sudo apt-get install bpfcc-tools linux-headers-$(uname -r)

# 安装 bpftrace
$ sudo apt-get install bpftrace

# 验证安装
$ sudo bpftrace -e 'BEGIN { printf("eBPF works!\n"); exit(); }'
Attaching 1 probe...
eBPF works!
```

### CentOS/RHEL

```bash
# 安装 bcc 工具
$ sudo yum install bcc-tools

# bcc 工具安装在 /usr/share/bcc/tools/ 下
$ ls /usr/share/bcc/tools/
biosnoop  execsnoop  opensnoop  tcplife  ...
```

### 内核版本要求

| 功能 | 最低内核版本 |
|------|-------------|
| 基本 eBPF | 4.1 |
| kprobe/uprobe | 4.4 |
| tracepoint | 4.7 |
| bpftrace | 4.9 |
| BTF（无需头文件） | 5.2 |

推荐使用 **5.4+** 内核以获得完整的 eBPF 支持。

### 容器环境

在 Kubernetes 中使用 eBPF 工具需要特权模式：
```yaml
securityContext:
  privileged: true
```

或者使用宿主机上的工具，通过 `-p <pid>` 追踪容器内的进程（容器进程在宿主机上有对应的 PID）。

## 小结

| 工具 | 用途 | 命令示例 |
|------|------|----------|
| execsnoop | 追踪进程创建 | `sudo execsnoop-bpfcc` |
| biosnoop | 块 I/O 延迟追踪 | `sudo biosnoop-bpfcc` |
| tcplife | TCP 连接生命周期 | `sudo tcplife-bpfcc` |
| opensnoop | 文件打开追踪 | `sudo opensnoop-bpfcc` |
| bpftrace | 自定义追踪脚本 | `sudo bpftrace -e '...'` |

eBPF 是现代 Linux 性能观测的基础。它的核心价值是**低开销 + 可编程**，让你可以在生产环境中安全地运行原来只能在测试环境做的深度追踪。如果你只能学一个新的性能工具，学 eBPF。
