# 追踪与 Profiling 工具

前面介绍的工具（top、iostat、ss 等）告诉你"是什么资源有瓶颈"。追踪和 Profiling 工具则回答下一层问题："具体在执行什么代码/系统调用时产生了瓶颈"。

## strace — 系统调用追踪

strace 是最常用的诊断工具之一，它追踪进程发出的每一个系统调用（open/read/write/connect 等）。

### strace -c — 系统调用统计

```bash
$ sudo strace -c -p 3421
strace: Process 3421 attached
^C
strace: Process 3421 detached
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 42.31    2.345678        1234      1901           epoll_wait
 25.12    1.392345          45     30941           read
 15.67    0.868901          38     22856           write
  8.45    0.468234         234      2001        45 futex
  4.23    0.234567          23     10198           clock_gettime
  2.12    0.117456          58      2025           sendto
  1.05    0.058234          28      2080           recvfrom
  0.56    0.031023          15      2068           close
  0.49    0.027189          13      2089           openat
------ ----------- ----------- --------- --------- ----------------
100.00    5.543627                 76159        45 total
```

这是最安全的 strace 用法（统计模式），开销相对较小。

解读：
- `epoll_wait` 占 42% 时间 → 进程大部分时间在等待事件（正常，说明 I/O 多路复用）
- `futex` 有 45 个错误 → 锁竞争或条件变量超时
- `read`/`write` 次数多 → 可以看看是否可以合并 I/O

### strace -e — 过滤特定类型

```bash
# 只追踪网络相关系统调用
$ sudo strace -e trace=network -p 3421 -T
connect(15, {sa_family=AF_INET, sin_port=htons(3306), sin_addr=inet_addr("10.0.0.4")}, 16) = 0 <0.001234>
sendto(15, "SELECT * FROM orders WHERE id = 12345", 37, 0, NULL, 0) = 37 <0.000045>
recvfrom(15, "...", 16384, 0, NULL, NULL) = 1234 <0.012345>
```

`-T` 显示每个系统调用的耗时（尖括号中的秒数）。上面 recvfrom 耗时 12ms，说明数据库查询响应时间约 12ms。

```bash
# 只追踪文件操作
$ sudo strace -e trace=file -p 3421

# 只追踪进程/线程操作
$ sudo strace -e trace=process -p 3421

# 追踪特定系统调用
$ sudo strace -e trace=openat,read,write -p 3421
```

### strace 性能影响警告

strace 使用 ptrace 机制，**每个系统调用都会被拦截两次**（进入和退出）。性能影响非常大：

```
正常运行: 10000 req/s
strace 附加后: 可能降到 1000-2000 req/s (下降 5-10 倍)
```

**在生产环境中慎用 strace**。如果必须用：
- 用 `-c` 统计模式（开销较小）
- 用 `-p <pid>` 只追踪特定进程
- 短时间附加，尽快 detach
- 优先考虑用 eBPF 工具替代（开销小 100 倍以上）

## ltrace — 库函数追踪

类似 strace，但追踪的是共享库函数调用（如 malloc、free、strlen 等）。

```bash
$ ltrace -c -p 3421
% time     seconds  usecs/call     calls      function
------ ----------- ----------- --------- --------------------
 35.23    1.234567          12    102880 malloc
 28.45    0.998765          10     99876 free
 15.67    0.549876           8     68734 memcpy
 10.23    0.358901          45      7975 pthread_mutex_lock
  5.12    0.179654          22      8166 pthread_mutex_unlock
  3.45    0.121023          15      8068 strlen
  1.85    0.064890          32      2028 fwrite
------ ----------- ----------- --------- --------------------
100.00    3.507676                297727 total
```

malloc/free 调用频率极高，可能导致内存分配器成为瓶颈。可以考虑用对象池或 jemalloc/tcmalloc 替代。

**注意**：ltrace 的性能影响和 strace 类似，生产环境慎用。

## perf — Linux 性能分析神器

perf 是 Linux 内核自带的性能分析工具，基于硬件性能计数器（PMU），开销极小。

### perf stat — 硬件计数器

```bash
$ sudo perf stat -p 3421 -- sleep 10
 Performance counter stats for process id '3421':

      45,234.56 msec  task-clock                #    4.523 CPUs utilized
        892,345        context-switches          #   19.725 K/sec
         12,345        cpu-migrations            #    0.273 K/sec
        234,567        page-faults               #    5.185 K/sec
 98,765,432,109        cycles                    #    2.183 GHz
 45,678,901,234        instructions              #    0.46  insn per cycle   ← IPC 低!
  8,901,234,567        branches                  #  196.793 M/sec
    234,567,890        branch-misses             #    2.64% of all branches

      10.003456 seconds time elapsed
```

关键指标解读：

| 指标 | 含义 | 关注点 |
|------|------|--------|
| **task-clock** | CPU 时间 | 4.523 CPUs = 用了约 4.5 个核 |
| **context-switches** | 上下文切换次数 | 19K/s 偏高，可能有锁竞争 |
| **instructions/cycles (IPC)** | 每周期指令数 | < 1.0 说明 CPU 流水线效率低（cache miss 多） |
| **branch-misses** | 分支预测失败率 | > 5% 需要关注 |

**IPC = 0.46** 非常低（现代 CPU 理论 IPC 可达 4+），说明 CPU 在等待数据（可能是 cache miss 严重）。

### perf record + perf report — CPU Profiling

```bash
# 采样 30 秒
$ sudo perf record -g -p 3421 -- sleep 30
[ perf record: Woken up 12 times to write data ]
[ perf record: Captured and wrote 45.234 MB perf.data (234567 samples) ]

# 查看报告
$ sudo perf report
Overhead  Command  Shared Object       Symbol
  25.34%  java     libjvm.so           [.] G1ParScanThreadState::copy_to_survivor_space
  12.56%  java     libjvm.so           [.] G1ParEvacuateFollowersClosure::do_void
   8.45%  java     libc-2.31.so        [.] __memmove_avx_unaligned_erms
   6.78%  java     app.jar             [.] com.example.OrderService.processOrder
   5.23%  java     app.jar             [.] com.example.JsonSerializer.serialize
   4.12%  java     libjvm.so           [.] JavaThread::check_safepoint_and_suspend
   3.45%  java     libc-2.31.so        [.] malloc
```

解读：前三名都是 JVM GC 相关函数，占了 46% 的 CPU。应用代码只占约 12%。GC 是主要的 CPU 消耗者。

`-g` 参数开启调用栈采集，可以看到完整的调用链。

### perf top — 实时热点

```bash
$ sudo perf top -p 3421
Overhead  Shared Object       Symbol
  18.34%  libjvm.so           [.] G1ParScanThreadState::copy_to_survivor_space
  10.23%  libjvm.so           [.] G1ParEvacuateFollowersClosure::do_void
   7.89%  libc-2.31.so        [.] __memmove_avx_unaligned_erms
   5.67%  app.jar             [.] com.example.OrderService.processOrder
```

类似 `top`，但显示的是 CPU 热点函数而不是进程。实时刷新，适合交互式排查。

## 火焰图生成流程

火焰图（Flame Graph）是 Brendan Gregg 发明的可视化工具，把调用栈采样数据转化为直观的图形。

```bash
# 第 1 步：采样
$ sudo perf record -F 99 -g -p 3421 -- sleep 30

# 第 2 步：导出采样数据
$ sudo perf script > perf.script

# 第 3 步：折叠调用栈
$ ./stackcollapse-perf.pl perf.script > perf.folded

# 第 4 步：生成火焰图 SVG
$ ./flamegraph.pl perf.folded > flamegraph.svg
```

火焰图的阅读方法：

```
                ┌──────────────────────────────┐
                │      main()                  │  ← 底部是入口函数
                ├────────────┬─────────────────┤
                │ handleReq()│  gcWorker()     │  ← 上层是被调用的函数
                ├──────┬─────┼────────┬────────┤
                │parse │proc │  mark  │  sweep │  ← 宽度 = CPU 时间占比
                └──────┴─────┴────────┴────────┘
```

- **纵轴**：调用栈深度（底部是最外层函数）
- **横轴宽度**：该函数在采样中出现的比例（≈ CPU 时间占比）
- **看平顶**：顶部宽且平的函数就是 CPU 热点

## ftrace — 内核函数追踪

ftrace 是 Linux 内核内置的追踪框架。

```bash
# 启用 function_graph tracer
$ echo function_graph > /sys/kernel/debug/tracing/current_tracer

# 只追踪特定函数
$ echo 'vfs_read' > /sys/kernel/debug/tracing/set_graph_function

# 查看追踪结果
$ cat /sys/kernel/debug/tracing/trace | head -20
# tracer: function_graph
#
# CPU  DURATION            FUNCTION CALLS
# |     |   |              |   |   |   |
  0)               |  vfs_read() {
  0)               |    rw_verify_area() {
  0)   0.234 us    |      security_file_permission();
  0)   0.567 us    |    }
  0)               |    __vfs_read() {
  0)               |      new_sync_read() {
  0)               |        ext4_file_read_iter() {
  0)  12.345 us    |          generic_file_read_iter();
  0)  12.678 us    |        }
  0)  13.012 us    |      }
  0)  13.345 us    |    }
  0)  14.234 us    |  }
```

function_graph tracer 显示函数调用树和每个函数的执行时间。适合排查内核路径的性能问题。

```bash
# 关闭追踪
$ echo nop > /sys/kernel/debug/tracing/current_tracer
```

## /proc/[pid]/* — 进程信息宝库

`/proc` 文件系统是 Linux 内核暴露进程信息的接口，很多工具的数据都来源于此。

```bash
# 进程状态（内存、线程数、上下文切换等）
$ cat /proc/3421/status
Name:   java
State:  S (sleeping)
Threads:    234
VmSize:  8523456 kB
VmRSS:   2345678 kB
voluntary_ctxt_switches:    45234567
nonvoluntary_ctxt_switches: 8901234

# 进程的内存映射（类似 pmap）
$ cat /proc/3421/maps | head -5
00400000-00600000 r-xp 00000000 fd:01 1234567  /usr/bin/java
7f1234000000-7f1244000000 rw-p 00000000 00:00 0

# 进程打开的文件描述符
$ ls -la /proc/3421/fd | head -10
lrwx------ 1 app app 64 Jan 15 10:45 0 -> /dev/pts/0
l-wx------ 1 app app 64 Jan 15 10:45 1 -> /var/log/app/app.log
lrwx------ 1 app app 64 Jan 15 10:45 5 -> socket:[45678]

# 进程 I/O 统计
$ cat /proc/3421/io
rchar: 89234567890
wchar: 45678901234
syscr: 12345678
syscw: 8901234
read_bytes: 5678901234
write_bytes: 3456789012

# 进程的详细内存映射（含 PSS/RSS 等）
$ cat /proc/3421/smaps | head -20
00400000-00600000 r-xp 00000000 fd:01 1234567  /usr/bin/java
Size:               2048 kB
Rss:                1820 kB
Pss:                1820 kB
Shared_Clean:          0 kB
Shared_Dirty:          0 kB
Private_Clean:      1820 kB
Private_Dirty:         0 kB
```

### 常用文件速查

| 文件 | 内容 | 等价工具 |
|------|------|----------|
| `/proc/<pid>/status` | 进程状态摘要 | `ps` |
| `/proc/<pid>/maps` | 内存映射 | `pmap` |
| `/proc/<pid>/fd/` | 打开的文件描述符 | `lsof` |
| `/proc/<pid>/io` | I/O 统计 | `iotop` |
| `/proc/<pid>/smaps` | 详细内存映射（含 PSS） | `smem` |
| `/proc/<pid>/stat` | CPU 时间等原始数据 | `pidstat` |
| `/proc/<pid>/net/tcp` | TCP 连接列表 | `ss` |

## 小结

| 工具 | 用途 | 开销 | 生产环境 |
|------|------|------|----------|
| strace -c | 系统调用统计 | 高 | 短时间可用 |
| strace -e | 系统调用过滤追踪 | 非常高 | 谨慎使用 |
| ltrace | 库函数追踪 | 非常高 | 避免使用 |
| perf stat | 硬件计数器 | 极低 | 安全 |
| perf record/report | CPU Profiling | 低 | 安全 |
| perf top | 实时 CPU 热点 | 低 | 安全 |
| 火焰图 | 可视化调用栈 | 低 | 安全 |
| ftrace | 内核函数追踪 | 中等 | 按需使用 |

排查路径：先用 `perf stat` 看整体（IPC、cache miss），再用 `perf record` + 火焰图找热点函数，必要时用 `strace -c` 看系统调用分布。生产环境优先用 perf 和 eBPF，尽量避免 strace。
