# goroutine 和线程 / 虚拟线程的区别

## 一句话回答

goroutine **不是 OS 线程**，是用户态的轻量任务，被 Go runtime 以 **M:N** 复用到少数 OS 线程（M）上：栈 **2KB 可增长** vs 线程 MB 级固定、**用户态纳秒级**切换 vs 内核态微秒级、**runtime 调度** vs 内核调度。所以能开几十万个而线程几千就爆。它几乎等同于 **Java 21 的虚拟线程（Loom）**——M ≈ carrier/平台线程。

## 对比表

| 维度 | OS 线程（Java 平台线程） | goroutine | Java 虚拟线程 |
|---|---|---|---|
| 是不是 OS 线程 | 是（1:1） | 否（M:N 复用） | 否（M:N 复用） |
| 栈 | MB 级固定 | 2KB 起可增长（上限 1GB） | 小、可增长 |
| 切换 | 内核态，微秒级 | 用户态，纳秒级 | 用户态 |
| 调度 | OS 内核 | Go runtime | JVM（ForkJoinPool） |
| 创建 | clone syscall | runtime 分配+G 复用 | 廉价 |
| 数量级 | 几千 | 几十万 | 几十万 |
| 抢占 | 内核抢占 | runtime 抢占（信号） | 暂不抢占 CPU |

## 三层论证（为什么轻）

1. **栈**：2KB 起 + 可增长（morestack 拷贝栈），1GB 内存能开 ~50 万；线程 MB 固定，几千就吃光内存。
2. **切换**：goroutine 切换在用户态改几个指针、不陷内核；线程切换要 syscall + 完整寄存器/TLB。
3. **创建/复用**：newproc 分配小结构体且 G 可复用；线程是 clone syscall。

## 关键澄清（容易混）

- **M = OS 线程**，这个等号成立——Go 的 M、Java 平台线程、Python 线程是同一种内核对象。
- 但你**编程面对的**是 G（goroutine），不是 M。Java 把「任务」和「OS 线程」捆成一个 `Thread`，Go 把它们拆开了：**G=任务（廉价），M=线程（昂贵）**。
- 映射：Java `Thread`（作为内核对象）↔ Go 的 M；Java `Thread`（作为你 spawn 的并发单元）↔ Go 的 G。新 Java 的虚拟线程 = G。

## 证据链接

- 正文：[`00 执行模型`](../00-execution-model/README.md) / [`04 goroutine 实战`](../04-goroutine/README.md)

## 易追问的延伸

- **为什么不用 1:1 或 N:1？** 1:1 太贵（线程重），N:1 没并行；M:N 兼得轻与并行，代价是 runtime 调度器复杂。
- **栈怎么增长？** 见 [栈相关](../04-goroutine/README.md)：序言查栈不足→分配两倍新栈拷贝→调指针。
- **和 asyncio 协程区别？** 都轻，但 asyncio 单线程 N:1、协作、要 await；goroutine M:N、真并行、抢占、不用 await。
