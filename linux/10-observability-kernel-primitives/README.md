# 10 观测与内核 tracing 原语

> **这章解决什么问题**
>
> `top`、`ss`、`strace`、`perf`、`bpftrace`、火焰图看起来是不同工具，但底层都在读 Linux 暴露出来的状态或事件。本章不做工具手册，而是解释这些工具背后的观测原语：`/proc`、`/sys`、perf event、tracepoint、kprobe/uprobe、eBPF。理解这一层，才能知道每个工具看到的到底是什么、代价是什么、盲区在哪里。

**依赖**：

- syscall、上下文切换、软中断 → [`linux/02-execution-primitives`](../02-execution-primitives/README.md)
- fd、procfs/sysfs、一切皆文件 → [`linux/03-io-primitives`](../03-io-primitives/README.md)
- 网络软中断与 socket 路径 → [`linux/06-network-kernel-primitives`](../06-network-kernel-primitives/README.md)
- 性能工具与 eBPF 动手 → [`performance-tuning-roadmap/02-linux-tools/06-ebpf-bcc-bpftrace`](../../performance-tuning-roadmap/02-linux-tools/06-ebpf-bcc-bpftrace.md)

**三层怎么读：**

- **① 你视角** — 从平时用的 `top` / `strace` / `perf` / `bpftrace` 搭桥。
- **② 黑盒内部** — 看工具读的是状态快照、计数器、采样，还是内核事件流。
- **③ 砸实** — 用 `/proc`、`/sys`、`perf stat`、`bpftrace` 验证。

---

## 原语一：/proc 是内核生成的进程和系统状态视图

### ① 你视角

你执行：

```bash
cat /proc/<pid>/status
cat /proc/meminfo
cat /proc/cpuinfo
```

看起来像读普通文件。实际上这些内容不是磁盘上的真实文本文件，而是内核按需生成的状态视图。

### ② 黑盒内部

procfs 是伪文件系统。读 `/proc` 文件时，内核把当前状态格式化成文本返回：

```text
application read("/proc/<pid>/status")
  → VFS
  → procfs handler
  → kernel reads task_struct/mm_struct/etc.
  → format text
  → copy to user buffer
```

常见路径：

| 路径 | 看什么 |
|---|---|
| `/proc/<pid>/status` | 进程身份、内存、线程数、capability、seccomp |
| `/proc/<pid>/maps` | 进程虚拟地址空间映射 |
| `/proc/<pid>/fd` | fd 表 |
| `/proc/stat` | CPU、进程、上下文切换等全局计数 |
| `/proc/softirqs` | 每 CPU 软中断计数 |
| `/proc/net/*` | 网络栈状态 |

关键限制：`/proc` 多数是 **当前快照或累计计数**，不是完整事件历史。

### ③ 砸实

```bash
cat /proc/self/status
cat /proc/self/maps | head
ls -l /proc/self/fd
cat /proc/softirqs
```

看点：

- `/proc/self` 指当前进程。
- `maps` 能对应内存原语和链接装载原语。
- `fd` 能对应 IO 原语。
- `softirqs` 能对应网络和中断排查。

---

## 原语二：/sys 是内核对象、设备和配置的结构化视图

### ① 你视角

你可能在 `/sys` 里看 CPU、block device、network interface、cgroup：

```bash
ls /sys/class/net
ls /sys/fs/cgroup
```

这些也不是普通业务文件，而是内核对象模型暴露出来的控制面和状态面。

### ② 黑盒内部

sysfs 以目录树形式暴露 kernel object：

```text
kernel object model
  device
  driver
  bus
  class
  subsystem
    → sysfs files
```

常见路径：

| 路径 | 看什么 |
|---|---|
| `/sys/class/net/<iface>` | 网络接口设备属性 |
| `/sys/block/<dev>` | 块设备队列、调度、统计 |
| `/sys/devices/system/cpu` | CPU 拓扑、online/offline 状态 |
| `/sys/fs/cgroup` | cgroup v2 控制和统计文件 |

和 `/proc` 相比，`/sys` 更偏「设备/内核对象/配置」。很多文件可写，写入会改变内核配置，因此生产上要非常谨慎。

### ③ 砸实

```bash
ls /sys/class/net
cat /sys/devices/system/cpu/online
ls /sys/fs/cgroup
```

看点：

- `/sys` 里很多文件内容很短，因为一个文件通常代表一个属性。
- cgroup v2 就挂在 `/sys/fs/cgroup`，它既是资源控制面，也是观测面。

---

## 原语三：strace 看 syscall 边界，但代价很高

### ① 你视角

`strace` 很适合回答：

- 进程卡在哪个 syscall？
- 打开了哪个文件？
- 为什么返回 `EACCES` / `ENOENT` / `ECONNREFUSED`？

但它不适合长期挂在线上高 QPS 服务上。

### ② 黑盒内部

`strace` 基于 `ptrace`。被跟踪进程每次 syscall 进入/退出都可能停下来，让 tracer 读取寄存器和参数：

```text
tracee enters syscall
  → kernel stops tracee
  → tracer wakes, reads syscall number/args
  → tracer resumes tracee
  → syscall exits
  → kernel stops tracee again
  → tracer reads return value
  → tracer resumes tracee
```

这会引入大量上下文切换和停顿。因此：

- 短时间排查单进程问题很好。
- 高频 syscall 服务上代价明显。
- 线上使用要加范围：`-p <pid>`、`-e trace=...`、短时间采样。

### ③ 砸实

```bash
strace -e trace=openat,read,write -p <pid>
```

看点：

- `strace` 看的是用户态和内核态的 syscall 边界。
- 它看不到所有内核内部事件，例如 TCP 重传、调度器决策、软中断内部细节。

---

## 原语四：perf event 提供计数器和采样

### ① 你视角

`perf stat` 可以告诉你 context switch、CPU cycles、cache miss 等计数；`perf record` 可以采样 call stack，生成火焰图。

### ② 黑盒内部

perf event 抽象了多种事件源：

| 类型 | 例子 |
|---|---|
| 硬件计数器 | cycles、instructions、cache-misses |
| 软件事件 | context-switches、cpu-clock、page-faults |
| tracepoint | sched:sched_switch、syscalls:* |
| PMU | CPU/uncore 相关性能监控单元 |

两种典型模式：

```text
counting:
  run workload
  count events
  print totals

sampling:
  every N events or time interval
  interrupt
  capture instruction pointer / call stack
  aggregate hot paths
```

采样不是记录每一次调用，而是按频率抽样。因此火焰图回答的是「大概率时间花在哪」，不是精确调用次数。

### ③ 砸实

```bash
perf stat -e cycles,instructions,context-switches,page-faults -p <pid>
perf record -F 99 -g -p <pid>
```

看点：

- `perf stat` 是计数视角。
- `perf record -g` 是采样 call stack。
- 采样频率越高，开销越大；频率太低，细节可能不稳定。

---

## 原语五：tracepoint 是内核预埋的稳定事件点

### ① 你视角

你想知道系统发生了多少次调度切换、某类 syscall、TCP 事件。相比随便 hook 内核函数，tracepoint 更适合作为稳定观测入口。

### ② 黑盒内部

tracepoint 是内核源码里预先定义的事件点，带有稳定的事件名和字段。

```text
kernel code:
  do something
  trace_sched_switch(prev, next)
  continue
```

常见 tracepoint：

| tracepoint | 看什么 |
|---|---|
| `sched:sched_switch` | 线程上下文切换 |
| `sched:sched_wakeup` | 线程被唤醒 |
| `syscalls:sys_enter_*` | syscall 进入 |
| `syscalls:sys_exit_*` | syscall 返回 |
| `net:*` / `tcp:*` | 网络栈事件，取决于内核版本 |

tracepoint 的优点是字段结构比较明确，跨内核版本相对稳定；缺点是只能看内核预埋的位置。

### ③ 砸实

```bash
perf list 'sched:*'
perf stat -e sched:sched_switch -p <pid>
```

如果有 bpftrace：

```bash
bpftrace -e 'tracepoint:sched:sched_switch { @[comm] = count(); }'
```

看点：

- tracepoint 适合从稳定事件开始排查。
- 需要 root 或相应权限，具体取决于系统配置。

---

## 原语六：kprobe/uprobe 是动态插桩

### ① 你视角

tracepoint 不够时，你可能想临时观察某个内核函数或用户态函数有没有被调用。kprobe/uprobe 就是动态插桩机制。

### ② 黑盒内部

| probe | 插在哪里 |
|---|---|
| kprobe | 内核函数入口/偏移 |
| kretprobe | 内核函数返回 |
| uprobe | 用户态程序/共享库函数入口/偏移 |
| uretprobe | 用户态函数返回 |

```text
kprobe:
  hook kernel function
  when function executes
    run handler / BPF program

uprobe:
  hook user binary or .so offset
  when process executes that instruction
    trap into kernel
    run handler / BPF program
```

kprobe/uprobe 很灵活，但稳定性取决于函数名、编译优化、内核版本、二进制符号是否存在。生产排查优先 tracepoint，必要时再用 probe。

### ③ 砸实

```bash
bpftrace -l 'kprobe:tcp_*' | head
bpftrace -l 'uprobe:/lib*/libc.so.6:malloc' 2>/dev/null | head
```

看点：

- kprobe 函数名受内核版本影响。
- uprobe 路径和符号受发行版、libc 版本、是否 strip 影响。

---

## 原语七：eBPF 是受验证的内核内小程序

### ① 你视角

很多现代观测工具说自己基于 eBPF：网络观测、性能剖析、安全审计、Kubernetes 可观测性。eBPF 的本质不是一个工具，而是一套在内核事件点运行小程序的机制。

### ② 黑盒内部

eBPF 大致工作流：

```text
user program
  → compile/load BPF bytecode
  → kernel verifier checks safety
  → attach to hook
      tracepoint / kprobe / uprobe / perf event / socket / XDP ...
  → event happens
  → BPF program runs in kernel context
  → write data to map/ring buffer
  → user program reads results
```

关键组件：

| 组件 | 作用 |
|---|---|
| verifier | 检查程序是否安全、是否可能无限循环、是否越界访问 |
| map | 内核态和用户态共享数据结构 |
| helper | BPF 程序能调用的受限内核辅助函数 |
| ring buffer/perf buffer | 把事件流传回用户态 |

eBPF 的优势是低开销、可编程、能在内核事件点就地聚合。限制是需要权限、受 verifier 限制、程序复杂度受限，且内核版本差异会影响可用能力。

### ③ 砸实

```bash
bpftrace -e 'tracepoint:raw_syscalls:sys_enter { @[comm] = count(); }'
```

看点：

- 这条命令按进程名统计 syscall 进入次数。
- 它不是 ptrace 每次停住进程，而是在 tracepoint 上运行 BPF 程序聚合计数。
- 需要 root 或足够的 BPF/perf 权限。

---

## 原语八：观测有成本，要先判断自己在看状态、事件还是采样

### ① 你视角

同一个问题可以用很多工具看。例如「线程切换频繁」：

- `vmstat` 看全局 `cs` 计数变化。
- `pidstat -w` 看进程上下文切换。
- `perf stat -e context-switches` 看事件计数。
- tracepoint/eBPF 看谁切给谁、为什么切。

选错工具不是不能看，而是容易误读。

### ② 黑盒内部

观测方式大致分三类：

| 类型 | 例子 | 回答什么 | 代价 |
|---|---|---|---|
| 状态快照 | `/proc/<pid>/status`、`ss` | 现在是什么状态 | 低 |
| 累计计数 | `/proc/stat`、`perf stat` | 一段时间发生多少次 | 低到中 |
| 事件 tracing | tracepoint、kprobe、strace | 每次事件发生时记录细节 | 中到高 |
| 采样 | `perf record`、profilers | 时间大概率花在哪里 | 可控 |

排查顺序通常是：

```text
先快照/计数确认方向
  → 再采样找热点
    → 最后 tracing 解释具体机制
```

### ③ 砸实

```bash
cat /proc/stat | grep ctxt
perf stat -e context-switches -p <pid>
bpftrace -e 'tracepoint:sched:sched_switch { @[comm] = count(); }'
```

看点：

- `/proc/stat` 的 `ctxt` 是全局累计上下文切换，不区分进程。
- `perf stat -p` 可以限制到进程。
- `sched_switch` tracepoint 可以进一步看调度事件细节，但开销和权限要求更高。

---

## 本章速查

| 想回答的问题 | 优先工具/原语 |
|---|---|
| 进程当前 fd、内存映射、权限状态 | `/proc/<pid>/fd`、`maps`、`status` |
| 内核对象/设备/cgroup 状态 | `/sys` |
| 程序卡在哪个 syscall | `strace`，短时间、窄范围 |
| CPU 时间花在哪 | `perf record -g` / 火焰图 |
| context switch/page fault 等计数 | `perf stat`、`pidstat`、`vmstat` |
| 稳定内核事件 | tracepoint |
| 没有 tracepoint 的函数级观测 | kprobe/uprobe |
| 低开销可编程观测 | eBPF |

**最小心智模型**：

```text
observability source:
  /proc / /sys          → state snapshots and counters
  perf event            → counters and sampling
  tracepoint            → stable kernel events
  kprobe/uprobe         → dynamic function instrumentation
  eBPF                  → verified programs attached to hooks
  strace/ptrace         → syscall boundary tracing with high overhead
```

到这里，`linux/` track 的底层原语已经覆盖：

```text
memory → execution → IO → concurrency → link/load
  → network → container/cgroup → permission/security
  → time/timer → observability/tracing
```
