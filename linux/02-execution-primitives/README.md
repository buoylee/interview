# 02 执行原语

> **这章解决什么问题**
>
> 你在 `linux-handson/03-process-model` 里看到进程、线程、上下文切换——现象都在那章，但「CPU 到底怎么从用户代码跳进内核」「中断和 syscall 有什么本质区别」「Go goroutine 为什么不是内核线程」这些底层原理在这里。本章补齐六个执行原语的内部工作原理，让 lh/03 的每一句结论都有根。

**依赖**：本章多次引用「虚拟地址」「页」「缺页」——如果这些概念不熟，先看 [`linux/01-memory-primitives/`](../01-memory-primitives/README.md)。

**三层怎么读：**

- **① 你视角** — 先用你熟悉的 Java/Go 概念搭桥，≤ 30 秒落地。
- **② 黑盒内部** — 内核真正做了什么，架构取舍在哪。这层是本章核心，每个原语必有。
- **③ 砸实** — 在真实 Linux 容器里跑出来的命令 + 输出，印在文档里作透明证据。只在能跑出干净结果的原语放，不强求每个都有。

> 注：所有 ③ 命令在 `arm64v8/ubuntu:22.04` 容器实跑（host 为 macOS aarch64，`ubuntu:24.04` 不在本机缓存中，故替换；地址前缀 `aaaa`/`ffff` 为 aarch64 特征，x86-64 则以 `7f` 开头，内核行为相同）。

---

## 原语一：syscall（系统调用）

### ① 你视角

Java 里你调 `FileOutputStream.write(buf)`，Go 里你调 `os.File.Write(buf)`——底层最终都落到同一件事：**用一条特殊指令让 CPU 跳进内核**。这条路叫 syscall（系统调用）。libc 的 `write()`、`read()`、`mmap()` 函数只是入口登记台，真正的门在 `syscall` 指令这一步。

### ② 黑盒内部

**syscall 是用户态程序进入内核的唯一合法通道。**

调用链：

```
你的代码  →  libc write()  →  syscall 指令  →  内核 sys_write()  →  返回
```

每一步拆开看：

1. **libc 是薄封装**：`write()` 函数体只有几行——把参数放进寄存器（x86-64: `rdi`/`rsi`/`rdx`；aarch64: `x0`/`x1`/`x2`），把 syscall 编号放进 `rax`（x86-64）或 `x8`（aarch64），然后执行一条指令。这条指令就是真正的触发器。

2. **触发指令**：x86-64 叫 `syscall`，aarch64 叫 `svc #0`（Supervisor Call）。CPU 收到这条指令，立刻：
   - 把当前用户态指令地址（PC）和栈指针存到特定寄存器/内核栈
   - x86-64 从 `IA32_LSTAR` MSR 直接读取内核入口地址，**不经过 IDT**——IDT/异常向量表是硬件中断与 CPU 异常（缺页、除零）的入口，不是 `syscall` 指令的路径；aarch64 上 `svc #0` 跳到 `VBAR_EL1` 指向的异常向量基址
   - 把 CPU 特权级从 Ring 3（用户态）切到 Ring 0（内核态）
   - 跳到内核 `entry_SYSCALL_64`（x86-64）或 `el0_svc`（aarch64）入口函数

3. **内核里**：根据 syscall 编号查系统调用表（`sys_call_table[]`），dispatch 到真正的实现（`sys_write`、`sys_read`...），执行完后执行 `sysret`/`eret` 返回用户态。

4. **libc 不是 syscall 本身**：syscall 是那条 CPU 指令，不是 libc 函数。你完全可以绕过 libc 用汇编直接发 syscall。Go 的 `syscall` 包正是这样做的——它直接用汇编包裹 `SYSCALL` 指令，不走 glibc。

常见 syscall 编号（x86-64，`/usr/include/asm/unistd_64.h`）：

| 编号 | 名字 | 作用 |
|------|------|------|
| 0 | `read` | 从 fd 读 |
| 1 | `write` | 向 fd 写 |
| 9 | `mmap` | 建立内存映射 |
| 231 | `exit_group` | 进程退出 |

### ③ 砸实

`strace` 是拦截进程所有 syscall 的工具。下面跑 `echo hi`，把它发出的 syscall 序列完整抓出来：

```bash
docker run --rm --cap-add=SYS_PTRACE arm64v8/ubuntu:22.04 bash -c '
apt-get update -qq && apt-get install -y -qq strace >/dev/null 2>&1
strace echo hi 2>&1
'
```

真实输出（截取关键部分，省略中间动态链接过程）：

```
execve("/usr/bin/echo", ["echo", "hi"], 0xfffff4e94068 /* 6 vars */) = 0  # 进程启动
brk(NULL)                               = 0xaaab024a8000                  # 查堆顶
mmap(NULL, 8192, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0) = 0xffffab268000  # 内核数据结构
openat(AT_FDCWD, "/etc/ld.so.cache", O_RDONLY|O_CLOEXEC) = 3              # 打开动态链接缓存
close(3)                                = 0
# ... 动态链接 libc.so ...
write(1, "hi\n", 3)                     = 3                               # 真正的 write syscall
close(1)                                = 0
close(2)                                = 0
exit_group(0)                           = ?                                # 退出
+++ exited with 0 +++
```

**看点**：`write(1, "hi\n", 3) = 3`——fd=1（stdout），内容 `"hi\n"`（3字节），返回 3（实际写入字节数）。`exit_group(0)` 是进程退出 syscall（不是 C 的 `exit()` 库函数）。`echo hi` 这么简单一个命令，真正跑起来有几十个 syscall——这就是「libc 是薄封装、真实工作在内核」的体现。

→ **回链**：`linux-handson/03-process-model` §syscall 一节（进程模型里的系统调用开销分析）；`linux/03-io-primitives/`（fd 操作全都是 syscall，下一章拆开讲）

---

## 原语二：用户态↔内核态切换

### ① 你视角

你知道 Go 的 goroutine 比 Java 的 OS 线程轻——部分原因就是 goroutine 调度在用户态完成，不走 syscall。但凡涉及 I/O，无论 goroutine 还是线程，都得走一次用户→内核→用户的切换，而这个切换是有代价的。代价从哪来？

### ② 黑盒内部

**每次 syscall/中断都包含一次用户↔内核态切换，成本不可忽视。**

切换时 CPU 必须做的事：

1. **寄存器保存**：通用寄存器（x86-64 有 15 个，共 120 字节）、浮点/SIMD 寄存器（视使用情况）写入内核栈或 TSS（任务状态段）。
2. **特权级切换**：CPU 从 Ring 3 → Ring 0，涉及修改 CS 段寄存器、切换栈指针（用户栈 → 内核栈）。aarch64 等效为 EL0 → EL1。
3. **地址空间切换**（部分场景）：如果启用了 KPTI（内核页表隔离，Meltdown 缓解措施），用户态和内核态用不同 CR3（页表基址），切换时需要刷 TLB——代价极高（几百纳秒）。
4. **Cache 冷效应**：内核代码和用户代码在不同虚拟地址、不同物理页，进内核后 L1 指令缓存里全是内核代码，出内核后用户代码重新进缓存，冷了一批。

**量化参考**：一次 syscall 往返（含切换）大约 **50–500 ns**，与具体 CPU 和 KPTI 开启状态有关。相比之下，L1 缓存访问约 1 ns，内存访问约 100 ns——一次 syscall 的成本相当于若干次内存访问。

**这个代价催生了两类架构优化：**

| 优化手段 | 动机 | 原理 |
|---|---|---|
| `writev` / `sendmsg` | 合并多次 `write` 为一次 syscall | 减少切换次数，同样数据量更少 syscall |
| `io_uring`（Linux 5.1+） | 完全异步，批量提交，无 syscall | 用户态 ring buffer 共享给内核，提交/消费不走切换 |
| `vDSO`（虚拟 DSO） | 某些只读 syscall（如 `gettimeofday`）在用户态完成 | 内核把数据映射到用户空间，读时无需切换 |

> 本原语无 ③（无干净 5 行复现能直接量化单次切换成本；真正的基准测试需要 perf/BPF 等工具，超出本章边界）。

→ **回链**：`linux-handson/03-process-model`（strace 计数、进程模型里的 syscall 频率讨论）；`os-for-architects/`（io_uring 作为架构决策的完整讨论）

---

## 原语三：中断 IRQ

### ① 你视角

你的 Java/Go 代码在顺序执行——但磁盘读完了数据、网卡收到了包、定时器到期了，CPU 怎么知道？不是靠你的代码轮询，而是**硬件主动打断 CPU**。这个打断机制叫中断（Interrupt Request，IRQ）。

### ② 黑盒内部

**中断是硬件异步打断 CPU 当前执行流的机制，与 syscall（软件主动发起）有本质区别。**

**IRQ vs syscall 对比：**

| 维度 | syscall（软件陷入·同步） | IRQ（硬件中断·异步） |
|---|---|---|
| 发起方 | 用户程序主动调用 `syscall` 指令 | 硬件设备（网卡/磁盘/时钟）发 IRQ 信号线 |
| 时机 | 同步，程序执行到那一行才触发 | 异步，可能在任意指令之间插入 |
| 处理上下文 | 当前进程的内核态，有进程上下文 | 中断上下文（interrupt context），无进程归属 |

**中断上下文为什么不能睡眠？**

中断处理程序运行在「中断上下文」：没有关联的 `task_struct`（没有「当前进程」），调度器不知道该把 CPU 还给谁。如果在中断处理器里调用 `schedule()`（主动睡眠），内核会直接 panic。这个约束影响内核驱动开发的每一行代码——中断处理里只能做原子操作（加减、位操作、内存读写），不能做任何可能阻塞的事（不能加 mutex、不能 `kmalloc(GFP_KERNEL)`）。

**Top half / Bottom half（上半部/下半部）设计：**

为了最小化「关中断时间」，内核把中断处理分两段：

- **Top half（上半部）**：中断处理程序本体，越快越好——只做「确认硬件、把数据放到队列里」，立即返回。
- **Bottom half（下半部）**：用 `tasklet`、`workqueue`、`softirq` 等机制把真正的处理推迟到「中断上下文结束后、普通进程上下文里」执行——这里可以睡眠、可以申请内存。

类比：网卡中断到来 → Top half 把数据包 DMA 地址记下来就返回（微秒级）→ Bottom half 的 `NAPI`/软中断把包从网卡 buffer 取出、走协议栈（可以睡眠等锁）。

> **一句破误解:** 这里的「软中断(softirq)」**不是硬件触发的中断**,而是内核自己一套**固定几类的高优先级待办队列**(`NET_RX`/`NET_TX`/`TIMER`…)。硬中断的 top half 只是去队列上「打个标记:有活」,内核在硬中断返回时、或在专门的 `ksoftirqd` 内核线程里把这些待办跑掉。名字里的「中断」是历史包袱——读成「内核的延后处理任务」就不会和硬件中断混了。

> **本原语无 ③**：在 Docker Desktop / macOS aarch64 宿主机上，容器内 `/proc/interrupts` 为空文件（Docker 虚拟化层不向容器暴露宿主机中断表）。真实 Linux 裸机上 `cat /proc/interrupts` 会看到每个 CPU 核上各中断线的累计触发次数。若在真实 Linux 上运行，可用 `watch -n1 cat /proc/interrupts` 观察网卡 IRQ 在收包时实时递增。

→ **回链**：`linux-handson/03-process-model`（驱动模型/设备 I/O 时中断的角色）

---

## 原语四：上下文切换（context switch）

### ① 你视角

Java 的 `Thread.sleep()` 让出 CPU，JVM 底层调 `futex`，OS 把这个线程「暂停」——但 CPU 接下来要跑另一个线程，它得先把「当前线程跑到哪了」保存下来，再把「下一个线程上次暂停在哪」恢复出来。这个保存+恢复的过程就是**上下文切换**。

### ② 黑盒内部

**上下文切换保存的是 CPU「跑某个任务时的完整状态」。**

Linux 里进程和线程都是 `task_struct`（下一个原语会细说），切换时操作系统做：

1. **保存当前任务的 CPU 状态**：
   - 通用寄存器（x86-64: rax/rbx/.../r15 + rsp/rbp + rip）
   - 浮点/SIMD 状态（FPU、XMM/YMM 寄存器，若该任务用了浮点）
   - 内核栈指针（每个 task_struct 有自己的内核栈）
   - 这些信息存在 `task_struct` 的 `thread` 字段和内核栈上

2. **切换内存上下文**（进程间切换才有，同进程线程间可省略）：
   - 修改 CR3 寄存器（x86-64）→ 切换页表 → TLB 失效（极贵）
   - 线程共享进程地址空间，同进程线程间切换不换 CR3

3. **恢复下一个任务的状态**：从 `task_struct` 里取出上次保存的寄存器值，写回 CPU。

**主动切换 vs 抢占：**

| 切换类型 | 触发条件 | 典型场景 |
|---|---|---|
| 主动切换（voluntary） | 任务主动调 `schedule()`：睡眠/`yield`/等锁 | `read()` 等数据、`mutex_lock()` 被占 |
| 抢占切换（preemptive） | 时间片耗尽、高优先级任务就绪，内核强制切换 | 实时任务抢占、定时器中断触发调度 |

**切换成本主要来自 Cache 冷效应**：寄存器保存/恢复本身 < 1 µs，但切换后新任务的数据不在 L1/L2 缓存里（前一个任务的数据刚把缓存占满），重新 warm up 才是大头——这也是为什么同进程线程切换（不换页表）比跨进程切换代价小。

### ③ 砸实

`vmstat` 的 `cs`（context switch）列实时显示每秒上下文切换次数：

```bash
docker run --rm arm64v8/ubuntu:22.04 bash -c '
apt-get update -qq && apt-get install -y -qq procps >/dev/null 2>&1
vmstat 1 2
'
```

真实输出：

```
procs -----------memory---------- ---swap-- -----io---- -system-- ------cpu-----
 r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st
 2  0      0 7226676    144 467972    0    0   236    40    8   31  1  1 99  0  0
 0  0      0 7189608    144 511428    0    0 17500     0  177  829  0  1 99  0  0
```

**看点**：`cs` 列——第一行 31（`vmstat 1 2` 的第一行是自系统启动以来的均值，不是 1 秒采样，容器刚起所以低），第二行 829（第二个 1 秒采样，包含了磁盘 I/O 触发的大量上下文切换；`bi`=17500 块/秒对应）。`in` 是每秒中断次数（177）。本例中 `cs` > `in`——一次中断可触发多次切换（唤醒多个等待者）；但这并非通则（空闲系统里定时器 `in` 可能反超 `cs`）。

→ **回链**：`linux-handson/03-process-model`（`/proc/[pid]/status` 里的 `voluntary_ctxt_switches` / `nonvoluntary_ctxt_switches` 与本原语直接对应）

---

## 原语五：栈帧（stack frame）

### ① 你视角

Java 里 `StackOverflowError` 是递归太深导致的，Go 里 goroutine 的栈会自动扩容。两者都涉及「函数调用用的那块内存」——这块内存的基本单元就是**栈帧（stack frame）**。

### ② 黑盒内部

**每次函数调用在栈上分配一帧，帧里存局部变量、参数、返回地址。**

函数调用时硬件做（以 x86-64 为例）：

```
调用方执行 call 指令:
  1. 把返回地址（下一条指令地址）push 到栈上
  2. 跳到被调函数起始地址

被调函数 prologue（函数开头）:
  3. push rbp（保存调用方帧基址）
  4. mov rbp, rsp（建立本帧基址）
  5. sub rsp, N（N字节局部变量区域）← 栈向下增长，SP 往低地址移

函数执行结束 epilogue（函数结尾）:
  6. mov rsp, rbp（回收局部变量空间）
  7. pop rbp（还原调用方帧基址）
  8. ret（从栈上取返回地址，跳回调用方）
```

栈在内存里是**向低地址方向增长**的（每次 push 地址减小），与堆的增长方向相反。

**栈溢出的两种来源：**

1. **递归无终止（最常见）**：每层递归分配一帧，帧没有回收，栈指针一直往低走，越过栈底边界（`[stack]` 区域边界）→ 访问没有映射的页 → 缺页，但缺页异常处理器发现这不是合法扩展请求 → 发 SIGSEGV（段错误）。这就是 Java `StackOverflowError` / C `Segmentation fault` 的根本来源。
2. **巨大局部变量**：单个函数里 `char buf[1000000]` 这种大数组直接在栈上分配，一帧就能越界。

**每线程一个栈 → 线程数和内存的直接关系：**

每个 OS 线程（或 Go 的 M，即 OS thread）都有独立的栈空间，默认 8 MB（Linux 默认）。1000 个线程 → 8 GB 仅用于栈——这就是「线程池为什么不能无限大」的最直接原因。

Go goroutine 的初始栈只有 2–8 KB，可动态扩展（Go 运行时在堆上分配新栈段，复制旧内容），这是 goroutine 能开几十万个而不耗尽内存的关键。

### ③ 砸实

`ulimit -s` 显示当前 shell（及子进程）的栈大小软限制：

```bash
docker run --rm arm64v8/ubuntu:22.04 bash -c 'ulimit -s'
```

真实输出：

```
8192
```

单位 KB，即 **8 MB**。这是 Linux 每个线程的默认栈大小上限（软限制，`setrlimit(RLIMIT_STACK, ...)` 可调）。用 `ulimit -s unlimited` 可以去掉软限制，但物理内存和虚拟地址空间才是真正的上界。

→ **回链**：`linux-handson/03-process-model`（线程数量与内存消耗的关系；`ulimit -s` 调优建议）

---

## 原语六：进程 vs 线程（内核视角）

### ① 你视角

Java 里 `Process` 和 `Thread` 是完全不同的类，Go 里有 goroutine 和 `os/exec.Cmd`。在用户态这两者差别很大——但进到 Linux 内核，两者**底层是同一个数据结构**，区别只是「共享了多少」。

### ② 黑盒内部

**Linux 内核里进程和线程都是 `task_struct`，区别来自 `clone()` 的标志位。**

`fork()` 和 `pthread_create()` 的内核路径都经过 `clone()` 系统调用，区别在于传入的标志：

| 操作 | 关键 clone 标志 | 效果 |
|---|---|---|
| `fork()` | 无 CLONE_VM、无 CLONE_FILES | 复制地址空间（写时复制）、复制 fd 表 → 完全独立进程 |
| `pthread_create()` | `CLONE_VM \| CLONE_FILES \| CLONE_SIGHAND \| CLONE_THREAD` | 共享地址空间、共享 fd 表、共享信号处理 → 同进程线程 |

所以「线程」在内核视角就是「共享了地址空间和 fd 表的 task_struct」，没有任何专属的「线程」数据结构。

**内核线程调度看 LWP**：`ps` 显示的 PID 是进程 ID，LWP（Light Weight Process）是内核分配给每个 task_struct 的 ID。同一进程的多个线程有相同 PID 但不同 LWP。

**Go goroutine ≠ 内核线程**：goroutine 是 Go runtime 在用户态实现的 **M:N 调度**——N 个 goroutine 映射到 M 个 OS 线程（`GOMAXPROCS` 控制 M 的数量，通常等于 CPU 核数）。Go runtime 有自己的调度器（`runtime.schedule()`），goroutine 的切换不走内核 `schedule()`，不产生上下文切换的内核代价。Go goroutine 的暂停（如 channel 等待）是 Go runtime 把 goroutine 从 OS 线程上摘下来、换上另一个 goroutine 来跑，OS 层面看到的那个 OS 线程一直在跑，没有切换。

### ③ 砸实

编译一个启动 2 个工作线程的小程序，用 `ps -eLf` 看 LWP（每个 task_struct 对应一行）：

```bash
docker run --rm arm64v8/ubuntu:22.04 bash -c '
apt-get update -qq && apt-get install -y -qq gcc procps >/dev/null 2>&1
cat > /tmp/threads.c <<"EOF"
#include <pthread.h>
#include <unistd.h>
void* w(void* a){ sleep(10); return 0; }
int main(){ pthread_t t1,t2; pthread_create(&t1,0,w,0); pthread_create(&t2,0,w,0); sleep(5); }
EOF
gcc /tmp/threads.c -o /tmp/threads -lpthread
/tmp/threads &
sleep 0.3
ps -eLf | grep -E "^UID|threads" | grep -v grep
'
```

真实输出：

```
UID          PID    PPID     LWP  C NLWP STIME TTY          TIME CMD
root         770       1     770  0    3 07:23 ?        00:00:00 /tmp/threads
root         770       1     772  0    3 07:23 ?        00:00:00 /tmp/threads
root         770       1     773  0    3 07:23 ?        00:00:00 /tmp/threads
```

**看点**：同一个 PID（770），三行 LWP（770=主线程、772/773=两个工作线程）。`NLWP=3` 表示该进程共 3 个线程。内核为每个 task_struct 分配了独立的 LWP ID——这就是「Linux 线程是 clone 出来的 task_struct」的直接证据。

→ **回链**：`linux-handson/03-process-model`（`ps -eLf` 在线上排查「线程泄漏」时的用法；`/proc/[pid]/task/` 目录下每个子目录对应一个 LWP）

---

## 本章速查

| 原语 | 一句话 | 关键数字/结论 |
|---|---|---|
| syscall | 用户态进内核的唯一合法门，libc 是薄封装 | `write(1,"hi\n",3)=3`，编号 1（x86-64） |
| 用户↔内核切换 | 每次 syscall/中断都要保存寄存器+切特权级，50–500 ns | io_uring/vDSO 是消除切换代价的架构手段 |
| 中断 IRQ | 硬件异步打断 CPU；中断上下文不能睡眠 | top half 极短，bottom half 可睡 |
| 上下文切换 | 保存/恢复 task_struct 的 CPU 状态；真正代价来自 cache 冷 | `vmstat cs` 列可实时看切换率 |
| 栈帧 | 每次函数调用分配一帧（局部变量+返回地址）；每线程独立栈 | 默认 8 MB（`ulimit -s 8192`）|
| 进程 vs 线程 | 内核都是 task_struct；clone 标志位决定共享地址空间/fd 表 | goroutine = 用户态 M:N，不是内核线程 |

---

**下一章**：[`linux/03-io-primitives/`](../03-io-primitives/README.md)——fd、fd table、inode、epoll 底层（fd 操作全都是 syscall，本章打的底在那里用）
