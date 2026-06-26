# 04 并发原语

> **这章解决什么问题**
>
> 你在 `linux-handson/03-process-model` 里看到线程竞争、锁、信号量——但「Java `synchronized` 底下到底做了什么系统调用」「Go `sync.Mutex` 为什么大部分时候不进内核」「两个线程各自的写为什么互相看不见」这些黑盒在这里揭开。本章是整个 primer 的压轴章：并发原语最抽象，多数无法用 5 行代码复现，因此以 ② 为主，但最关键的两个（futex / signal）有真实容器取证支撑。

**依赖**：

- 「上下文切换」「进程 vs 线程（task_struct / clone）」→ [`linux/02-execution-primitives/`](../02-execution-primitives/README.md)
- 「内存可见性」「每进程独立地址空间」→ [`linux/01-memory-primitives/`](../01-memory-primitives/README.md)

**三层怎么读：**

- **① 你视角** — 先用你熟悉的 Java/Go 概念搭桥，≤ 30 秒落地。
- **② 黑盒内部** — 内核/硬件真正做了什么，架构取舍在哪。这层是本章核心，每个原语必有。
- **③ 砸实** — 在真实 Linux 容器里跑出来的命令 + 输出，印在文档里作透明证据。本章多数原语为概念层，无干净 5 行复现，明确标注「② 讲透，无 ③」；只有 futex 和 signal 有真实取证。

> 注：所有 ③ 命令在 `arm64v8/ubuntu:22.04` 容器实跑（host 为 macOS aarch64，`ubuntu:24.04` 不在本机缓存中，故替换；aarch64 使用 LL/SC 原子指令，x86-64 使用 `LOCK` 前缀，内核行为与语义相同）。

---

## 原语一：原子操作 / CAS（compare-and-swap）

### ① 你视角

Java 里 `AtomicInteger.incrementAndGet()`、Go 里 `sync/atomic.AddInt64()` 都是"原子操作"——它们不用加锁却能保证并发安全。这是怎么做到的？答案在 CPU 硬件里。

### ② 黑盒内部

**原子操作的根基：硬件层保证「读-改-写」不可分割。**

普通的 `i++` 在汇编里是三步：读 `i` → 加 1 → 写回。两个线程并发执行，中间可以被抢占，结果丢失。原子操作由 CPU 用特殊指令一步完成：

- **x86-64**：`LOCK CMPXCHG`——`LOCK` 前缀靠 cache 一致性协议（MESI）保证原子性（Nehalem，2008 起;仅对极少数跨缓存行或非缓存内存才真锁内存总线），操作期间其他 CPU 无法读写该地址。
- **aarch64**：`LDXR`（Load-Exclusive）+ `STXR`（Store-Exclusive）——LL/SC（Load-Linked / Store-Conditional）模式。`LDXR` 读取并标记地址为「独占监视」；`STXR` 写入时若监视被其他 CPU 破坏则失败，调用者需要循环重试。

**compare-and-swap（CAS）是无锁算法的基石：**

```
CAS(addr, expected, new_val):
    if *addr == expected:
        *addr = new_val
        return success
    else:
        return fail（调用者决定是否重试）
```

这是一条原子指令——读比较写三步不可中断。无锁数据结构（lock-free queue、lock-free stack）全部建立在 CAS 之上。Java `AtomicInteger` 底层就是 `sun.misc.Unsafe.compareAndSwapInt()`，最终落到 CPU 的 `LOCK CMPXCHG`。

**ABA 问题**：CAS 只比较值，不比较「中间发生了什么」。假设地址值本来是 A，另一线程改成 B 又改回 A，第一个线程的 CAS 看到值还是 A，成功了——但逻辑上这个 A 已经是「改过又改回」的 A，可能不再安全。解决方案：附加版本号（version tag）或时间戳，变成 `CAS(addr, (A, version), (new_val, version+1))`。Java `AtomicStampedReference` 就是这个设计。

**重要边界**：CAS 不是「总比锁快」。无争用时 CAS 确实避免了内核开销；但高争用时 CAS 循环重试（自旋）会让 CPU 空转，锁（悲观等待）反而更省 CPU 资源。两者各有适用场景。

> 无 ③（硬件指令级，无干净 5 行容器复现）

→ **回链**：`linux-handson/03-process-model`（线程竞争 + 无锁数据结构实测）

---

## 原语二：锁底层（futex）

### ① 你视角

Java `synchronized`、`ReentrantLock`，Go `sync.Mutex`——这些锁在用户代码层就一行，但背后到底做了什么？大多数教材说「锁 = 系统调用」，但实测并非如此：Go `sync.Mutex` 在无争用时根本不进内核。

### ② 黑盒内部

**futex（Fast Userspace Mutex）= 原子 CAS + 内核睡眠/唤醒的组合。**

Linux 锁的真正实现由两层组成：

**第一层：用户态 CAS（无内核开销）**

锁用一个整数表示状态（0 = 未锁，1 = 已锁）。加锁时先用 CAS 尝试把 0 改成 1：
- 成功 → 锁到手，完全在用户态完成，**零系统调用**。
- 失败（已被别人持有）→ 进入第二层。

**第二层：内核 futex syscall（仅在争用时触发）**

第一层失败后，调用 `futex(FUTEX_WAIT, addr, expected_val, ...)` 进内核，让当前线程睡在该地址的等待队列上，不消耗 CPU。
持锁者释放锁时，把整数改回 0，然后调用 `futex(FUTEX_WAKE, addr, 1)` 唤醒一个等待者。

```
lock():
    if CAS(lock_word, 0, 1) == success:
        return             ← 无争用：纯用户态，0 syscall
    else:
        futex(FUTEX_WAIT)  ← 有争用：进内核睡眠

unlock():
    lock_word = 0
    if 有线程在等待:
        futex(FUTEX_WAKE)  ← 唤醒等待者
```

**架构取舍**：futex 的关键设计决策是「乐观先走用户态」——因为实际场景中大多数 lock/unlock 是无争用的（临界区很短），把 100% 的锁都做成 syscall 浪费巨大。futex 让高频无争用路径零内核开销，只在真正需要等待时才付出 syscall 代价。

glibc 的 `pthread_mutex_t`、Java HotSpot 的 thin lock / biased lock、Go `sync.Mutex` 全部基于此机制（Go 不走 glibc/pthreads 封装，而是自己实现 futex-like 原语、直接通过 `syscall` 调 Linux `futex(2)`）。

### ③ 砸实

两个线程各执行 100,000 次 `pthread_mutex_lock/unlock`，共 200,000 次加锁操作，用 `strace` 统计实际触发了多少次 `futex` 系统调用：

```bash
docker run --rm --cap-add=SYS_PTRACE arm64v8/ubuntu:22.04 bash -c '
apt-get update -qq && apt-get install -y -qq gcc strace >/dev/null 2>&1
cat > /tmp/f.c <<"EOF"
#include <pthread.h>
pthread_mutex_t m = PTHREAD_MUTEX_INITIALIZER;
void* w(void* a){ for(int i=0;i<100000;i++){ pthread_mutex_lock(&m); pthread_mutex_unlock(&m);} return 0; }
int main(){ pthread_t t1,t2; pthread_create(&t1,0,w,0); pthread_create(&t2,0,w,0);
  pthread_join(t1,0); pthread_join(t2,0); return 0; }
EOF
gcc /tmp/f.c -o /tmp/f -lpthread
strace -f -e trace=futex /tmp/f 2>&1 | grep -c futex
echo "futex 调用次数 ↑(上面是计数)"
'
```

真实输出（`arm64v8/ubuntu:22.04` 实跑）：

```
3
futex 调用次数 ↑(上面是计数)
```

**解读**：200,000 次加锁操作中，只有 **3 次** 触发了 `futex` 系统调用。其余 199,997 次完全在用户态以 CAS 完成，不进内核。注意这 3 次里至少 2 次来自 `pthread_join` 等待子线程退出（`FUTEX_WAIT` on tid），真正由互斥锁争用触发的可能只有 0–1 次——这反而是更强的实证:**互斥锁加锁路径在无争用时几乎零内核开销**，正是 futex「无争用不进内核」的设计。

→ **回链**：`linux-handson/03-process-model`（`/proc/<pid>/status` 看 `voluntary_ctxt_switches` 验证锁争用的上下文切换次数）

---

## 原语三：信号（signal）

### ① 你视角

Go 里你用 `signal.Notify(ch, syscall.SIGTERM)` 监听终止信号，Java 里用 `Runtime.addShutdownHook()`——这些都是对 Linux 信号机制的封装。信号是操作系统向进程异步投递「事件通知」的手段。

### ② 黑盒内部

**信号是内核向进程异步投递的软件中断。**

信号的投递流程：

1. 发送方调用 `kill(pid, sig)`（或内核自己生成，如除零产生 `SIGFPE`）。
2. 内核在目标进程的任务结构（`task_struct`）里设置信号 pending 标志位。
3. 目标进程下次从内核态返回用户态（syscall 返回、时钟中断返回等）时，内核检查 pending 标志，**打断正常控制流，跳到信号处理函数**。
4. 信号处理函数执行完后，内核恢复原来的控制流（或终止进程）。

**两类关键限制：**

**① 可重入限制（async-signal-safe）**：信号处理函数可以在任意时刻打断正常代码——包括正在执行 `malloc`、`printf` 的中间状态。如果处理函数再调 `malloc`，就可能破坏 malloc 内部的数据结构（重入）。Linux 定义了「async-signal-safe」函数白名单（`man signal-safety`），只有这些函数可以在信号处理函数里安全调用。`malloc`、`printf`、`mutex_lock` **不在**白名单内。常见安全做法：处理函数只写一个 `int` 标志位，在主循环里检查并处理。

**② 不可屏蔽信号**：`SIGKILL`（9）和 `SIGSTOP`（19）无法被捕获、忽略或阻塞，是内核强制机制的保证。这是为什么容器 `docker stop` 会发 `SIGTERM`（可被捕获→优雅退出）而 `docker kill` 发 `SIGKILL`（强制终止）。

**`SIGTERM` → 优雅退出的基础**：`SIGTERM`（15）是「请优雅退出」的标准信号。进程注册处理函数后，收到 `SIGTERM` 可以：清理资源、等待请求处理完、关闭连接，然后退出。这是 零停机下线 / rolling deployment 的操作系统基础——k8s Pod 终止先发 `SIGTERM`，等 `terminationGracePeriodSeconds`，再发 `SIGKILL`。详见 [`distribution/zero-downtime-release/`](../../distribution/zero-downtime-release/)。

**实时信号（SIGRTMIN–SIGRTMAX）**：编号 34–64，支持排队（不丢失）和优先级，是标准信号（1–31）的补充。glibc 内部用几个实时信号做线程管理，应用一般不直接用。

### ③ 砸实

`kill -l` 列出当前内核支持的全部信号及编号：

```bash
docker run --rm arm64v8/ubuntu:22.04 bash -c 'kill -l'
```

真实输出（`arm64v8/ubuntu:22.04` 实跑）：

```
 1) SIGHUP	 2) SIGINT	 3) SIGQUIT	 4) SIGILL	 5) SIGTRAP
 6) SIGABRT	 7) SIGBUS	 8) SIGFPE	 9) SIGKILL	10) SIGUSR1
11) SIGSEGV	12) SIGUSR2	13) SIGPIPE	14) SIGALRM	15) SIGTERM
16) SIGSTKFLT	17) SIGCHLD	18) SIGCONT	19) SIGSTOP	20) SIGTSTP
21) SIGTTIN	22) SIGTTOU	23) SIGURG	24) SIGXCPU	25) SIGXFSZ
26) SIGVTALRM	27) SIGPROF	28) SIGWINCH	29) SIGIO	30) SIGPWR
31) SIGSYS	34) SIGRTMIN	35) SIGRTMIN+1	36) SIGRTMIN+2	37) SIGRTMIN+3
38) SIGRTMIN+4	39) SIGRTMIN+5	40) SIGRTMIN+6	41) SIGRTMIN+7	42) SIGRTMIN+8
43) SIGRTMIN+9	44) SIGRTMIN+10	45) SIGRTMIN+11	46) SIGRTMIN+12	47) SIGRTMIN+13
48) SIGRTMIN+14	49) SIGRTMIN+15	50) SIGRTMAX-14	51) SIGRTMAX-13	52) SIGRTMAX-12
53) SIGRTMAX-11	54) SIGRTMAX-10	55) SIGRTMAX-9	56) SIGRTMAX-8	57) SIGRTMAX-7
58) SIGRTMAX-6	59) SIGRTMAX-5	60) SIGRTMAX-4	61) SIGRTMAX-3	62) SIGRTMAX-2
63) SIGRTMAX-1	64) SIGRTMAX
```

**对照看点**：
- 9) `SIGKILL`、19) `SIGSTOP`：不可捕获，直接由内核处理。
- 15) `SIGTERM`：可捕获，标准「请优雅退出」信号。
- 2) `SIGINT`：键盘 `Ctrl+C` 的信号，也可捕获。
- 32、33 号由 glibc/NPTL 线程实现占用（故用户态 `SIGRTMIN` 从 34 起）；34–64 为实时信号，支持排队不丢失。

→ **回链**：`linux-handson/03-process-model`（进程信号与 `/proc/<pid>/status` 的 `SigCgt` 字段，以及 graceful shutdown 实测）

---

## 原语四：条件变量 / 唤醒（condition variable）

### ① 你视角

Java 里的 `Object.wait()/notify()/notifyAll()`、`Condition.await()/signal()`，Go 里的 `sync.Cond.Wait()/Signal()/Broadcast()`——这些都是「条件变量」。核心场景：一个线程等待某个条件成立（如队列非空），另一个线程满足条件后唤醒它。

### ② 黑盒内部

**条件变量底层 = futex 等待队列。**

条件变量的语义：
1. `wait`：原子地「释放持有的互斥锁 + 把自己睡在等待队列上」（两步必须原子，否则会错过唤醒）。内核实现为 `futex(FUTEX_WAIT_BITSET, ...)` 睡在条件变量内部计数器上，唤醒时用 `FUTEX_CMP_REQUEUE` 把等待者原子迁移到互斥锁的等待队列（这是非 PI 锁的标准路径；`FUTEX_WAIT_REQUEUE_PI` 是优先级继承锁才走的变体）。
2. `signal`：从等待队列唤醒一个线程，该线程被唤醒后需要重新竞争互斥锁才能继续。
3. `broadcast`（`notifyAll`）：唤醒所有等待线程，但同一时刻只有一个能拿到锁继续执行。

**为什么必须用 `while` 而不是 `if` 检查条件**：

```java
// 错误写法
synchronized(lock) {
    if (queue.isEmpty())      // ← 危险！
        lock.wait();
    process(queue.poll());
}

// 正确写法
synchronized(lock) {
    while (queue.isEmpty())   // ← 必须 while
        lock.wait();
    process(queue.poll());
}
```

原因有两个：

1. **虚假唤醒（spurious wakeup）**：POSIX 规范允许 `wait` 在没有 `signal/broadcast` 的情况下自行返回。原因是内核出于性能考虑，可能在信号投递、中断等时机提前唤醒等待者。如果用 `if`，虚假唤醒后直接执行，条件可能根本没满足。`while` 循环回去重新检查条件，才是正确的防御。

2. **窗口期丢失**：即使被合法 `signal` 唤醒，从睡眠到真正拿到锁之间有窗口，其他线程可能已经消费了条件（如把队列又清空）。`while` 重新检查能捕获这种情况。

**惊群（thundering herd）**：`notifyAll`（Java）/ `Broadcast`（Go `sync.Cond`）唤醒所有等待线程，但只有一个能拿到锁，其余全部重新睡眠。在等待者很多时，这 N 次唤醒触发 N 次上下文切换，只有一次有效——是性能陷阱。解决方式：用 `Signal`（只唤醒一个）或改用信道（Go channel 的 select 语义天然避免此问题）。

> 无 ③（概念层；futex wait/wake 在 ③ 中已通过 mutex 争用间接展示，不再单独复现）

→ **回链**：`linux-handson/03-process-model`（生产者消费者模型实测）

---

## 原语五：内存屏障（memory barrier）

### ① 你视角

你在 Java 里用 `volatile` 修饰一个标志位，Go 里用 `sync/atomic.StoreInt32()`——这些不只是「用了个原子操作」，它们还在保证**内存可见性**：一个线程写的值，另一个线程一定能看到。没有这个保证，你的 `volatile` 标志可能在另一个线程眼里永远是旧值。

### ② 黑盒内部

**内存屏障解决的问题：编译器和 CPU 都会重排指令。**

两层重排：

**① 编译器重排**：编译器在优化时会对「看起来无关」的读写重排顺序以提升局部性能。例如把一个写操作推后，或把一个读操作提前。这在单线程下没问题，但多线程下可能让另一个线程看到「乱序」的操作序列。

**② CPU 乱序执行（OOO）**：现代 CPU 的执行单元是流水线，为了填满流水线，CPU 可以乱序执行指令（只要数据依赖不违反）。更关键的是：**多核 CPU 之间有 write buffer（写缓冲）**——一个核心写的值先进本核心的 write buffer，还没刷到对其他核心可见的缓存层（L3 或内存），另一个核心就读到了旧值。

```
Thread A (Core 0)       Thread B (Core 1)
x = 1;                  if (ready) {
ready = true;               print(x);   ← 可能打印 0！
                        }
```

CPU 不保证 `x = 1` 对 Core 1 可见早于 `ready = true`（write buffer 的刷出顺序不确定）。

**内存屏障（memory barrier / memory fence）是强制 CPU 和编译器的有序承诺：**

- **StoreStore Barrier**：此前所有写操作先于此后所有写操作对其他核可见。
- **LoadLoad Barrier**：此前所有读操作先于此后所有读操作。
- **Full Barrier（mfence / dmb sy）**：最强，保证两侧的读和写都有序。

**happens-before**：JMM（Java Memory Model）定义的规则，说「操作 A 先行发生于操作 B」意味着 A 的结果对 B 一定可见。`volatile` 写 happens-before 之后的 `volatile` 读——这个保证由 JVM 在底层插入内存屏障指令来实现。

**Java `volatile` 的真实语义**：

`volatile` 不只是「禁止缓存」（这是 C 语言 `volatile` 的语义，完全不同）。Java `volatile` 同时保证：
1. **原子性**：64 位值的读写原子（防止 long/double 的半字问题）。
2. **可见性**：写 `volatile` 字段会插入 StoreLoad barrier，强制刷出 write buffer；读会插入 LoadLoad barrier，强制从内存读取而不是寄存器缓存。
3. **有序性**：禁止编译器把 `volatile` 读写与前后指令重排（happens-before 保证）。

**Go `sync/atomic` 的语义**：Go 的 `sync/atomic` 操作同样带内存屏障语义（实现为 `LOCK`/`DMB` 指令），保证 happens-before。Go memory model 明确说明：`sync/atomic` 操作同步了 goroutine 间的内存视图。普通赋值不带屏障，两个 goroutine 并发读写同一变量（哪怕是 `int`）是数据竞争，结果未定义。

**架构取舍**：x86-64 是「强顺序」（TSO，Total Store Order）架构，硬件已经保证大部分读写顺序，StoreLoad 仍然可能重排，`mfence` 代价相对小。aarch64 是「弱顺序」架构，几乎所有顺序都需要显式屏障（`dmb sy`），屏障指令开销更大但架构更灵活。这是为什么跨平台并发库不能假设特定内存顺序，必须依赖语言层的 happens-before 抽象。

> 无 ③（CPU 指令级和 JVM 字节码层，无干净的 Linux 容器 5 行复现；内存可见性问题在单核容器环境难以稳定复现）

→ **回链**：`linux-handson/03-process-model`（线程数据竞争场景：用 `volatile`/atomic 修复可见性 bug）；`linux-handson/04-memory-model`（`/proc/<pid>/status` VmRSS 等内存指标，以及数据竞争排查）；`linux/01-memory-primitives/`（虚拟内存模型 + 为什么需要内存屏障的场景原点）

---

## 本章总结：五个原语的关系

```
硬件原子（CAS / LL-SC）
       │
       ├─→ futex（无争用走 CAS，争用才进内核睡眠/唤醒）
       │         │
       │         └─→ 条件变量（futex 等待队列 + 互斥锁联动）
       │
       ├─→ 内存屏障（原子操作附带屏障，保证 happens-before）
       │
       └─→ signal（内核异步投递，打断正常控制流）
```

- **CAS** 是最基础的硬件原子，是其他并发原语的基石。
- **futex** 用 CAS + 内核睡眠组合出高效互斥锁：无争用零内核开销，争用时精准睡眠/唤醒。
- **条件变量**在 futex 上构建「等条件 + 通知」语义，必须配合 `while` 循环防虚假唤醒。
- **内存屏障**解决 CAS 之外的可见性问题：保证写操作在多核间有序传播。
- **signal** 是独立的异步通知通道，不走锁机制，适用于进程级事件（优雅退出、配置热加载）。

→ 这五个原语合在一起，解释了 `linux-handson/03-process-model` 里「并发为什么难」的每一个根因。
