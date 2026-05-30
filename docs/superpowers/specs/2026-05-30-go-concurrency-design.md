# Go 并发系统课 — 设计 spec

> 日期：2026-05-30
> 目录：`golang/concurrency/`

## 背景与目标

用户是 5 年+ Java/Go 后端工程师，并发基础（线程、线程池、锁、CAS、goroutine、channel）有底子但生疏。刚系统学完一门 Python 并发课（`python-concurrency/`），并在一轮深入对话里把 **协作式 vs 抢占式** 这条主线摸透了——入口正是好奇「Go 凭什么让 `time.Sleep` 让出 CPU、凭什么无停止点也能抢占」。现在想把这套理解沉淀成一份**够面试、也够实践**的 Go 并发笔记。

仓库现状：关于 Go 调度/抢占的专门文档**不存在**。`golang/` 下是 ~20 行的 stub；`performance-tuning-roadmap/05a-go-profiling/03-go-gc-runtime.md` 只讲 GC 不讲调度器；`q-asyncio-vs-goroutine.md` 是 34 行小卡。GMP / 抢占 / netpoller / sysmon 这套一篇都没有——这正是要补的空白。

目标（用户三选确认：完整并发·以调度器为核心 / 仿 python-concurrency 课 / 原理·实践·面试三合一）：
1. **完整覆盖** Go 并发体系：并发原语 + 运行时调度 + 陷阱与模式。
2. **以调度器为核心**：GMP + 抢占 + netpoller 当总钥匙，所有原语最后落回「在调度器上怎么跑」。
3. 最终能**应对面试**（讲清原理 + 答高频题）**且指导实践**（怎么用、怎么避坑、并发模式）。

## 核心设计决策

- **形式**：多文件 mini-course，对标用户已认可的 `python-concurrency/`（同款 7 段章节 + 面试卡 + 进度地图）。
- **路线 = 方案 A·调度器优先**：地基 → **GMP → 抢占 → netpoller**（运行时内核，前置）→ 再讲原语（goroutine/channel/sync/context）→ 并发模式 → 陷阱调优 → 面试卡。顺序刻意贴合用户「从抢占切入、往外摸到整张图」的真实学习路径。
- **总钥匙 = GMP 调度器 + 抢占 + netpoller**：对应 Python 课里 GIL 的地位。GIL 解释「Python 为什么不一样」，GMP+抢占解释「Go 为什么这么省心」。
- **理论优先，lab 后置**：不搭独立 lab 环境。每章内嵌可直接 copy 运行的最小代码（标注所需 Go 版本/`go get`）。
- **双向桥接**：每个 Go 机制同时锚两头——① 从 Java 线程/JUC 切入（用户母语）；② 反向链回刚学完的 `python-concurrency`，尤其 **goroutine vs asyncio**、**抢占 vs 协作**、**netpoller vs `to_thread`**。
- **calibration（重要）**：与 Python 课不同，用户 Go 起点**不低**（goroutine/channel 基本会用），所以**深度压在 runtime 内核与「为什么」**，原语章节快速过 API、重点放底层与陷阱。承接 [[feedback_learning_style]]：先在正文把原理和具体数字（10ms 抢占阈值、reduction、2KB 栈等）讲透，再让他应用；predict-then-observe 仅用在他直觉够得着的地方（如「GOMAXPROCS=1 时一个死循环会不会饿死别人」）。承接 [[feedback_learning_delivery]]：逐章交付，不一次性灌长文。
- **Go 版本基线**：Go 1.22+。版本敏感点显式标注（异步抢占 1.14+、泛型 1.18+、`errgroup`/`slog` 等）。

## 章节地图

| 章节 | 内容 | 跨语言对标 |
|---|---|---|
| `00-execution-model/` | **并发地基**：进程/线程/协程、为什么 M:N、goroutine 凭什么便宜。**双向桥**：Java Thread ←→ Python asyncio ←→ goroutine；Java 虚拟线程(Loom) = goroutine 的最佳镜像 | OS 执行模型 + JVM 线程 + Loom |
| `01-gmp-scheduler/` | **GMP 调度器 ← 核心①**：G/M/P 三件套、本地/全局运行队列、work-stealing、调度循环、GOMAXPROCS | OS 线程调度 |
| `02-preemption/` | **抢占式调度 ← 核心②（用户入口）**：协作式→异步抢占演进、函数调用安全点的旧坑、sysmon、SIGURG、async-safe point、10ms 阈值 | Java 抢占式线程调度 / BEAM reduction |
| `03-netpoller-blocking/` | **阻塞与 netpoller ← 核心③**：网络 I/O 的 park/unpark、epoll/kqueue、阻塞 syscall 时的 P 交接(handoff)与自动加 M、`time.Sleep` 的 timer 实现 | Python asyncio 事件循环 / `to_thread` / `run_in_executor` |
| `04-goroutine/` | goroutine 实战：`go` 关键字、可增长栈(2KB 起/拷贝栈)、生命周期、泄漏、凭什么开几十万 | Java Thread vs 虚拟线程 |
| `05-channel-select/` | channel 与 select：hchan 底层、无/有缓冲、关闭语义、nil channel、select、`for range ch` | Java BlockingQueue + CSP |
| `06-sync-memory-model/` | sync 包与内存模型：Mutex/RWMutex/WaitGroup/Once/Cond/atomic、happens-before、Go 内存模型、数据竞争 + `-race` 检测器 | JUC 锁 + JMM + CAS |
| `07-context/` | context 与取消传播：超时/取消/传值、取消树、与 goroutine 泄漏的关系 | 线程中断 + ThreadLocal |
| `08-patterns/` | **并发模式（实战）**：worker pool、fan-in/fan-out、pipeline、`errgroup`、限流(令牌桶/信号量)、超时重试、优雅关闭 | 线程池模式 + CompletableFuture 编排 |
| `09-pitfalls-tuning/` | 陷阱与调优：goroutine 泄漏排查、channel 死锁、GOMAXPROCS 与容器、`pprof`/`go tool trace`、调度与 GC 的交互 | JVM 调优类比 |
| `99-interview-cards/` | 面试卡：速答表 + 深题卡（讲一下 GMP / 抢占怎么实现 / channel 底层 / goroutine vs thread / goroutine vs asyncio / 数据竞争 / context 取消），每张链回章节做证据 | python-concurrency 卡片格式 |

`01–03` 是调度器内核，**前置**，这就是「以调度器为核心」的落地。每章固定 7 段：**核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结**。

## 已有素材的处理

仓库已有但分散的相关内容，章节内**链接复用、不重复**：

- `performance-tuning-roadmap/05a-go-profiling/03-go-gc-runtime.md`（GC + GOGC/GOMEMLIMIT，第 09 章调优引用，本课不重讲 GC 细节）
- `performance-tuning-roadmap/05a-go-profiling/01-go-pprof.md` / `02-go-trace.md` / `04-go-race-concurrency.md`（pprof/trace/race 工具，第 09 章引用）
- `performance-tuning-roadmap/05b-go-debugging/01-goroutine-leak.md`（泄漏排查实操，第 04/09 章引用）
- `performance-tuning-roadmap/00-os-fundamentals/05-process-thread-coroutine.md`（OS 层进程/线程/协程，第 00 章引用）
- `python-concurrency/99-interview-cards/q-asyncio-vs-goroutine.md`（反向对标锚点；本课第 03/04 章会把它从 34 行小卡升级为有证据链的深题）
- `java/concurrent/*`（Java 侧基础，做对标锚点）
- `golang/` 下的 stub（base/GC/collections 等）：**不动**，本课自成体系；后续若有重叠再决定是否收编。

## 交付节奏

1. 写本 spec（本文件）。
2. 用户 review spec。
3. 搭骨架：`golang/concurrency/README.md`（含进度地图、怎么用、章节地图）+ 章节目录。
4. **先只写第 00 + 02 章**——00 立地基、02 是用户最有热度的抢占（直接复用本轮对话已讲透的内容），用来确认深度/风格。
5. 用户反馈后按章推进，每章一交付。

## 验收标准

- 理论部分自洽完整：读完一章能讲清该章的「核心问题」和面试考点，无需先做实验。
- 每个 Go 机制都有明确的 Java/Go(asyncio) 对标，且抢占/netpoller 等核心机制讲到「能在面试白板上画出 sysmon→SIGURG→asyncPreempt 这条链」。
- 面试卡每张都能链回正文证据。

## 非目标（YAGNI）

- **不是 Go 语法教程**：不讲基础语法、错误处理惯例、泛型、模块管理（除非与并发直接相关）。
- **不逐行抠 runtime 源码**：深到「机制 + 关键函数名 + 为什么」即可（资深面试够用），不做 `runtime/proc.go` 全文走读。
- **不覆盖 GC 内部**：GC 只在第 09 章「与调度的交互」层面提，细节链到已有的 go-gc-runtime 笔记。
- **不搭 docker/lab 环境**：理论吃透后若需要再后置。
- **不做分布式并发**（分布式锁/一致性等）：那是另一条线，repo 已有 `distr-tx/` 等。
