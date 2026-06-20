# 00 · 执行模型与并发地基

> 本课总钥匙是**调度器**。但在拆 GMP 之前，先把地基立稳：跑一个 goroutine 时，机器到底分几层？谁是真线程？Go 为什么不像 Java 那样「一个任务一根线程」，而要搞 M:N？
>
> 桥接锚点：**Java Thread ←→ Python asyncio ←→ goroutine**，外加 Java 21 虚拟线程(Loom)这面最佳镜子。

---

## 1. 核心问题

你写 `go doWork()`，一行就起一个并发任务。但底下到底发生了什么？三个必须分清的问题：

1. **goroutine 是 OS 线程吗？** —— 不是。它是用户态的轻量任务，被多路复用到少数 OS 线程上。
2. **那谁是 OS 线程？** —— Go runtime 里的 **M**。你碰不到它，它是 runtime 的内部管线。
3. **为什么要这么绕？** 直接「一个 goroutine 一根线程」不好吗？ —— 因为线程太贵（MB 级栈、内核调度、微秒级切换），开几千个就爆；而 goroutine 要能开几十万个。

这一章回答：**Go 用什么执行模型(M:N)、凭什么 goroutine 能比线程便宜几个数量级。**

---

## 2. 直觉理解

### 三层概念，先对齐

| | 是什么 | 谁调度 | 成本 |
|---|---|---|---|
| **进程** | 一份独立地址空间 | OS | 最重(GB 级隔离) |
| **线程** | 进程内一条执行流，共享地址空间 | OS 内核 | 重(MB 级栈，内核态切换) |
| **协程/goroutine** | 用户态的一条执行流 | **语言 runtime**(非内核) | 轻(KB 级栈，用户态切换) |

关键分界：**线程由内核调度，协程由 runtime 调度。** 内核不知道 goroutine 的存在——它只看到几个在跑的 OS 线程(M)，至于每根 M 上正在跑哪个 goroutine，是 Go runtime 自己说了算。

### 三方对照（你的两门母语 + Go）

你刚学完 asyncio，又有 Java 底子，正好三方对照：

| 维度 | Java 平台线程 | Python asyncio | **Go goroutine** |
|---|---|---|---|
| 并发单元 | `Thread` | coroutine | goroutine(G) |
| 是不是 OS 线程 | **是**(1:1) | 否(单线程内协作) | 否(M:N 复用) |
| 谁调度 | OS 内核 | 事件循环(你的代码 await) | Go runtime 调度器 |
| 让出方式 | 内核抢占 | 显式 `await` | runtime 抢占(隐式) |
| 真并行 | ✅ 多核 | ❌ 单线程 | ✅ 多核 |
| 启动语法 | `new Thread()` | `create_task()` | `go f()` |

一句话定位 Go：**它既有 asyncio 那样的「海量轻量任务」，又有 Java 线程那样的「真多核并行」，还不用你手写 `await`。** 这三者兼得，靠的就是 M:N 调度器(下一章 GMP)。

### Loom：给 Java 人的最佳镜子

Java 21 的**虚拟线程**(Project Loom)其实就是 Java 抄了 Go 的模型：

- Go 的 **goroutine** = Java 的 **virtual thread**
- Go 的 **M**(承载 goroutine 的 OS 线程) = Java 的 **carrier / platform thread**

所以：**你过去用 `new Thread()` 的地方，Go 用 `go f()`，新 Java 用 `Thread.ofVirtual()`——三者是同一类东西。** 把「goroutine」读成「虚拟线程」，你的 Java 直觉立刻就接上了。

---

## 3. 原理深入

### 为什么是 M:N，而不是 1:1 或 N:1

并发单元(协程)和 OS 线程的映射有三种：

- **1:1（Java 平台线程、C pthread）**：一个任务一根内核线程。简单、真并行，但**线程贵**——开几千个就吃光内存、压垮内核调度器。
- **N:1（早期 Python greenlet、老式绿色线程）**：很多协程挤在一根 OS 线程上。轻，但**没有并行**——一根线程只能用一个核，且一个阻塞调用卡死全部(这正是 asyncio 单线程的处境)。
- **M:N（Go、Erlang、Haskell、Java Loom）**：M 个 OS 线程承载 N 个协程，N ≫ M。**既轻又能并行**——用户态调度省成本，多根 M 吃满多核。

Go 选 M:N，就是为了同时拿到「轻」和「并行」。代价是 runtime 复杂(要自己写调度器)——这复杂度就是 `01–03` 三章的内容。

### goroutine 凭什么便宜几个数量级

对比一根 OS 线程，goroutine 省在三处：

**① 栈：KB 级 vs MB 级。**
- OS 线程栈通常 **1–8 MB**(Java 默认 `-Xss` 约 512KB–1MB，Linux pthread 默认 8MB)，而且是**固定**的——一开就占住。
- goroutine 初始栈只有 **2 KB**(`_StackMin`)，且是**可增长**的：不够用时 runtime 分配更大的栈、把旧栈内容**拷过去**(连续栈，Go 1.4 起；早期是分段栈)。
- 算一笔账：1 GB 内存，线程按 1MB 栈算只能开 ~1000 个；goroutine 按 2KB 算能开 **~50 万个**。这就是「goroutine 能开几十万」的物理来源。

**② 切换：用户态 vs 内核态。**
- 线程切换要陷入内核(syscall)，保存/恢复完整寄存器组、刷 TLB 等，**微秒级**。
- goroutine 切换发生在**用户态**，由 runtime 直接改几个指针、保存少量寄存器，**纳秒级**——不经过内核。

**③ 创建/销毁：runtime 池化 vs 内核 syscall。**
- 创建线程是 `clone()`/`pthread_create` syscall，重。
- 创建 goroutine 是 runtime 分配一个小结构体 + 2KB 栈，并且 M 还会被**缓存复用**(空闲不销毁)，摊销极低。

> **可增长栈的隐藏代价**：因为栈会被拷贝/移动，runtime 必须精确知道所有指针(配合 GC)，这也是为什么 Go 不能像 C 那样随便把栈指针传给外部、cgo 调用要做特殊交接。这一点在 `03`(syscall 处理)和 `06`(内存模型)还会回头碰到。

### 一张「跑起来」的全链路图

```
你的代码        go doWork()            <- 创建一个 G(goroutine)
                  │
Go runtime      调度器把 G 放进某个 P 的本地运行队列
                  │                      (P = 逻辑处理器，数量 = GOMAXPROCS)
                  │
                M 必须先拿到一个 P，才能执行 G 的代码
                  │
OS 内核         M 是真 OS 线程，被内核调度到某个 CPU 核上
                  │
硬件            CPU 核执行指令
```

- **G** = 你的任务，**M** = OS 线程，**P** = 「执行 Go 代码的许可证」+ 一个本地队列。
- 同一瞬间真正并行跑 Go 代码的 G 数 = 有 P 的 M 数 ≤ **GOMAXPROCS**(默认 = CPU 核数)。

这张图的细节(P 是什么、队列怎么偷、怎么抢占)就是接下来三章。`00` 只需要你记住：**G 不是线程，M 才是；G 靠 runtime 多路复用到 M 上。**

---

## 4. 日常开发应用

- **`go f()` 几乎零成本**：不像 Java 要珍惜线程、配线程池大小，goroutine 该开就开。一个请求里 fan-out 几十个 goroutine 去并发调下游，完全正常。
- **但「便宜」≠「免费」**：每个 goroutine 至少占 2KB + 它引用的对象。开几十万个、又都不退出(泄漏)，照样 OOM。所以**生命周期管理**(谁负责让它结束)比「数量」更重要——这是 `07 context` 和 `04 泄漏`的主题。
- **别用「线程数」直觉去管 goroutine**：Java 里你会算「线程池开多少个」；Go 里你通常不限 goroutine 数，而是用**有界的并发原语**(带缓冲 channel / 信号量 / worker pool)去限并发度。心智从「管线程」换成「管并发度」。

```go
// 一个请求里并发调 3 个下游，直接开 3 个 goroutine——在 Java 里你会犹豫，在 Go 里这是常态
func handle() (A, B, C) {
    var a A; var b B; var c C
    var wg sync.WaitGroup
    wg.Add(3)
    go func() { defer wg.Done(); a = fetchA() }()
    go func() { defer wg.Done(); b = fetchB() }()
    go func() { defer wg.Done(); c = fetchC() }()
    wg.Wait()
    return a, b, c
}
```

---

## 5. 生产&调优实战

- **GOMAXPROCS 默认 = 逻辑核数**：决定同时并行跑 Go 代码的上限。**容器里有坑**：Go 1.24 及之前默认读宿主机核数，而不是 cgroup 限额——4 核 limit 的 Pod 跑在 64 核宿主机上，GOMAXPROCS=64，导致过度调度/上下文切换抖动。老办法上 `uber-go/automaxprocs`；Go 1.25+ 起 runtime 开始感知 cgroup CPU 限额(关注版本说明)。这个点在 `09` 调优章细讲。
- **监控 goroutine 数**：`runtime.NumGoroutine()`，或 pprof 的 goroutine profile。**数量持续单调上涨 = 泄漏信号**(`04`/`09` 章)。
  ```bash
  go tool pprof http://localhost:6060/debug/pprof/goroutine   # 需 import _ "net/http/pprof"
  ```
- **栈增长不是免费的**：递归深、或栈上放大对象，会触发多次栈拷贝(`morestack`)。极端场景能在 trace 里看到。一般无需操心，知道有这回事即可。

---

## 6. 面试高频考点

- **进程 / 线程 / 协程的区别？** 隔离粒度(地址空间)→ 调度者(内核 vs runtime)→ 成本(GB/MB/KB)。落点：协程是**用户态**调度，内核不感知。
- **goroutine 和线程的区别？** goroutine 不是 OS 线程，是 M:N 复用到 OS 线程(M)上的用户态任务；栈 2KB 可增长 vs 线程 MB 固定；切换用户态纳秒级 vs 内核态微秒级；runtime 调度 vs 内核调度。
- **为什么 goroutine 能开几十万，线程几千就爆？** 栈小(2KB vs MB)+ 用户态切换便宜 + M 复用。给得出「1GB/2KB≈50万」这笔账加分。
- **M:N 是什么？为什么不用 1:1？** N 个 goroutine 复用 M 个 OS 线程；1:1 太贵(线程重)，N:1 没并行；M:N 兼得轻与并行，代价是 runtime 调度器复杂。
- **(对标题) goroutine 和 Java 线程/虚拟线程怎么对应？** goroutine ≈ 虚拟线程(Loom)，M ≈ carrier/平台线程；Java 老的 `Thread` 是 1:1 OS 线程 = Go 的 M。
- **(对标题) goroutine 和 asyncio 协程区别？** 都是轻量任务，但 asyncio 是单线程 N:1、协作式、要 `await`；goroutine 是 M:N、能真并行、抢占式、不用手写让出。深答见 `02`/`03` 和 [goroutine vs asyncio 卡](../../../python-concurrency/99-interview-cards/q-asyncio-vs-goroutine.md)。

---

## 7. 一句话总结

> **goroutine 不是线程，M 才是；Go 用 M:N 把 N 个 KB 级、用户态调度的 goroutine 复用到 M 个 OS 线程上，于是同时拿到了 asyncio 的「海量轻量」和 Java 线程的「真多核并行」——代价是一个复杂的 runtime 调度器，那就是接下来 `01 GMP`、`02 抢占`、`03 netpoller` 三章。**

下一章 → [`01 GMP 调度器`](../01-gmp-scheduler/README.md)：把上面那个 G/M/P 全链路图拆开，看 P 到底是什么、队列怎么偷。
