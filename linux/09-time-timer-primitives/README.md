# 09 时间与定时器原语

> **这章解决什么问题**
>
> 业务代码里到处都有时间：日志时间、超时时间、定时任务、sleep、TTL、重试、分布式锁租约。最常见的坑是把「墙上时钟」和「单调时间」混用：NTP 调时后 timeout 变长/变短，系统时间回拨导致任务重复，跨机器日志时间对不上。本章补齐 Linux 里时间和定时器的底层语义。

**依赖**：

- syscall、用户态/内核态切换 → [`linux/02-execution-primitives`](../02-execution-primitives/README.md)
- epoll、fd、阻塞等待 → [`linux/03-io-primitives`](../03-io-primitives/README.md)
- futex、线程等待/唤醒 → [`linux/04-concurrency-primitives`](../04-concurrency-primitives/README.md)

**三层怎么读：**

- **① 你视角** — 从 Java `System.currentTimeMillis()` / `System.nanoTime()`，Go `time.Now()` / timeout 搭桥。
- **② 黑盒内部** — 看 realtime clock、monotonic clock、NTP、hrtimer、timerfd。
- **③ 砸实** — 用 `date`、`uptime`、`clock_gettime`、`timerfd` 相关工具观察语义。

---

## 原语一：wall clock 是「现在几点」，monotonic 是「过了多久」

### ① 你视角

Java 里：

```text
System.currentTimeMillis()  → 现在日期时间
System.nanoTime()           → 测量时间间隔
```

Go 里 `time.Now()` 打印出来是日期时间，但 Go 的 `time.Time` 内部也可能携带 monotonic component，用于 `Sub` 这种间隔计算。

这背后的核心区别是：

| 时间 | 问题 | 能不能被调时影响 |
|---|---|---|
| wall clock / realtime | 现在是几月几号几点几分 | 会 |
| monotonic clock | 从某个固定点开始过了多久 | 不会倒退 |

### ② 黑盒内部

Linux 常见 clock：

| clock | 用途 |
|---|---|
| `CLOCK_REALTIME` | 系统实时时钟，表示日历时间 |
| `CLOCK_MONOTONIC` | 单调递增时间，适合测 elapsed duration |
| `CLOCK_MONOTONIC_RAW` | 更接近硬件计数，不受 NTP 频率校正影响 |
| `CLOCK_BOOTTIME` | 类似 monotonic，但包含 suspend 时间 |

`CLOCK_REALTIME` 可以被管理员、NTP、虚拟化平台调节。它可能跳 forward，也可能跳 backward。

`CLOCK_MONOTONIC` 不会倒退，适合做 timeout/deadline，但它不是跨机器可比较的绝对时间。

### ③ 砸实

```bash
date
python3 -c 'import time; print("time", time.time()); print("monotonic", time.monotonic())'
```

看点：

- `time.time()` 近似 wall clock 秒数。
- `time.monotonic()` 只能用于比较间隔，数值本身没有业务日期含义。

---

## 原语二：NTP 调时会影响 wall clock，但不应该破坏 timeout

### ① 你视角

假设你这样写 timeout：

```text
expire_at = currentTimeMillis() + 30_000
while currentTimeMillis() < expire_at:
  wait
```

如果系统时间被往回调，等待可能超过 30 秒；如果被往前调，可能提前超时。

### ② 黑盒内部

NTP 的目标是让机器的 wall clock 接近真实世界时间。它可能通过两类方式调整：

| 方式 | 行为 |
|---|---|
| step | 直接跳到新时间，可能前跳/后跳 |
| slew | 逐渐调快/调慢时钟频率 |

这就是为什么 timeout 应该基于 monotonic：

```text
start = monotonic()
deadline = start + timeout

while monotonic() < deadline:
  wait remaining time
```

wall clock 用来打日志、展示时间、和外部协议交换时间戳；monotonic 用来测耗时、做超时、调度本地定时器。

### ③ 砸实

```bash
timedatectl 2>/dev/null || true
date
```

看点：

- `timedatectl` 可以看到 NTP 是否启用，但容器/精简系统不一定有这个命令。
- 线上遇到「timeout 诡异」时，要查代码用的是 wall clock 还是 monotonic。

---

## 原语三：clock_gettime 可能通过 vDSO 读时间，不一定每次 syscall

### ① 你视角

高频调用当前时间看似很轻，但如果每次都陷入内核，成本会很高。Linux 为常见时间读取提供了 vDSO 优化。

### ② 黑盒内部

vDSO（virtual dynamic shared object）是内核映射到用户态地址空间的一小段只读/可执行代码。它让用户态在某些场景下不用 syscall 就能读取内核维护的时间数据。

```text
application clock_gettime()
  → libc
    → vDSO fast path if available
      → read mapped time data
    → fallback syscall if needed
```

这解释了两个现象：

- `clock_gettime` 很常用，但不一定在 `strace` 中每次都出现。
- 不同 clock、不同架构、不同内核配置下，是否走 vDSO 可能不同。

### ③ 砸实

```bash
cat /proc/self/maps | grep vdso
ldd /bin/ls | grep vdso || true
```

看点：

- `/proc/<pid>/maps` 中常能看到 `[vdso]`。
- vDSO 是进程地址空间里的特殊映射，不是普通磁盘上的 `.so`。

---

## 原语四：sleep 和 timeout 最终是让线程进入等待，等定时器唤醒

### ① 你视角

`sleep(1)` 看起来像线程「暂停一秒」。实际上线程不是忙等 CPU 一秒，而是进入睡眠状态，CPU 可以去运行其他任务。

### ② 黑盒内部

一次 sleep 大致是：

```text
thread calls nanosleep(timeout)
  → syscall enters kernel
  → kernel creates/arms timer
  → task state becomes sleeping
  → scheduler picks another runnable task
  → timer expires
  → wake up sleeping task
  → task becomes runnable
  → scheduler later runs it
```

关键点：

- 定时器到期只表示「线程可被唤醒」，不保证它立刻获得 CPU。
- 系统负载高、CPU quota throttling、调度延迟都会让实际醒来时间晚于目标时间。
- 所以 sleep/timeout 的精度不是只由定时器决定，也受调度影响。

### ③ 砸实

```bash
strace -e trace=nanosleep,clock_nanosleep sleep 1
```

看点：

- `sleep` 背后通常会调用 `nanosleep` 或 `clock_nanosleep`。
- 如果系统很忙，命令实际耗时可能略大于 1 秒。

---

## 原语五：timerfd 把定时器变成 fd，方便和 epoll 合并

### ① 你视角

事件循环里常见需求：同时等 socket 可读、进程信号、定时任务到期。Linux 可以把定时器也做成 fd，这样统一交给 `epoll`。

### ② 黑盒内部

`timerfd_create` 创建一个 timer fd。定时器到期时，这个 fd 变成可读；应用 `read` 它可以拿到到期次数。

```text
timerfd_create()
timerfd_settime()
epoll_ctl(timerfd)

epoll_wait()
  socket fd readable
  or timerfd readable
```

这就是 Linux 「一切皆 fd」在事件循环里的好处：网络、定时器、eventfd、signalfd 都可以统一进入 epoll 模型。

### ③ 砸实

```bash
man timerfd_create
```

如果系统没有 man page，可以记住接口语义：

| API | 作用 |
|---|---|
| `timerfd_create` | 创建 timer fd，指定使用哪个 clock |
| `timerfd_settime` | 设置超时时间/周期 |
| `read(timerfd)` | 读取超时次数，清除可读状态 |

---

## 原语六：deadline 比 duration 更不容易写错

### ① 你视角

复杂调用链里经常出现多个步骤共享一个总 timeout：

```text
HTTP request total timeout = 200ms
  parse
  cache
  DB
  RPC
```

如果每层都重新给自己 200ms，整体请求可能远超 200ms。

### ② 黑盒内部

更稳的做法是入口处计算一个 monotonic deadline，后续每层传 deadline 或剩余时间：

```text
deadline = monotonic_now + 200ms

before each blocking call:
  remaining = deadline - monotonic_now
  if remaining <= 0:
    timeout
  else:
    wait up to remaining
```

这有两个好处：

- 不受 wall clock 回拨影响。
- 多层调用共享同一个时间预算。

这也是很多语言/框架里 context deadline、request deadline、cancellation token 的底层语义。

### ③ 砸实

这类问题更适合代码审查而不是单条命令复现。检查点：

- 用于耗时统计的是 monotonic 还是 wall clock。
- timeout 是否按调用链传递 deadline。
- 重试是否消耗同一个总预算，而不是每次重置完整 timeout。

---

## 原语七：分布式系统里的时间不能只靠本机 clock

### ① 你视角

你在两台机器日志里看到：

```text
service A 10:00:00.100 send request
service B 10:00:00.050 receive request
```

看起来 B 在 A 发送前就收到了请求。通常不是时间旅行，而是两台机器的 wall clock 有偏差。

### ② 黑盒内部

本机 clock 有两个限制：

| clock | 限制 |
|---|---|
| wall clock | 可跨机器比较，但存在同步误差、跳变 |
| monotonic | 本机间隔可靠，但不能跨机器比较 |

因此分布式排查不能只靠日志时间排序。更可靠的组合是：

```text
wall clock timestamp
  + trace id / span id
  + causal relation
  + monotonic duration inside each process
```

在协议层做租约、锁、选主时，还要明确时钟偏差假设。不要把「本机时间到了」直接等同于「全局事实成立」。

### ③ 砸实

这类问题通常通过观测系统验证：

- 看 NTP/chrony 同步状态。
- 看 trace span 的 parent/child 关系，而不是只按日志时间排序。
- 在单进程内用 monotonic duration 看耗时，在跨机器上用 trace 因果关系看顺序。

---

## 本章速查

| 问题 | 应该用什么时间 |
|---|---|
| 打日志、展示日期 | wall clock / realtime |
| 计算函数耗时 | monotonic |
| timeout/deadline | monotonic |
| 本机定时器 | monotonic 或 boottime，取决于是否包含 suspend |
| 跨机器日志对齐 | wall clock + trace id，接受同步误差 |
| 分布式租约/锁 | 明确 clock drift 假设，不只依赖单机时间 |

**最小心智模型**：

```text
wall clock:
  answers "what time is it?"
  can jump because humans/NTP/VM adjust it

monotonic clock:
  answers "how much time has elapsed?"
  should be used for timeout and duration

timer:
  expires in kernel
  wakes task to runnable
  actual execution still depends on scheduler
```

下一章：[`10 观测与内核 tracing 原语`](../10-observability-kernel-primitives/README.md)
