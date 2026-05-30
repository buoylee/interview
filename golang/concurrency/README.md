# Go 并发系统课 —— 给 Java·Python 后端的「以调度器为核心」

> 把 Go 并发像 `java.util.concurrent` 一样系统讲一遍，但主线是**运行时调度器**。总钥匙是 **GMP + 抢占 + netpoller**——就像 Python 课的总钥匙是 GIL：GIL 解释「Python 为什么不一样」，GMP+抢占解释「Go 为什么这么省心」。
>
> 理论优先：每章正文先讲透原理，代码片段可直接 copy 运行（标注所需 Go 版本）。不搭独立 lab。
>
> 设计来源：`docs/superpowers/specs/2026-05-30-go-concurrency-design.md`

## 怎么用这个课

1. **按顺序读**：`00` 立并发地基（谁是真线程、为什么 M:N），`01–03` 是调度器内核（GMP / 抢占 / netpoller）——这是本课的「以调度器为核心」。内核吃透了，后面的原语(channel/sync/context)才落得了地。
2. **每章固定 7 段**：核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结。
3. **双向桥**：每个机制同时锚两头——从 **Java 线程/JUC/Loom** 切入（你的母语），再反链到 **Python `asyncio`**（你刚学完的那门课），尤其 goroutine vs asyncio、抢占 vs 协作、netpoller vs `to_thread`。
4. **想答面试**：去 `99-interview-cards/` 找卡，每张卡链回章节做证据。
5. **想跑代码**：片段标了 Go 版本，复制到 `main.go` 跑（`go run main.go`）。

## 容易忘时先看这里

- [抢占怎么实现：无停止点也能让出 CPU](02-preemption/README.md) — sysmon → SIGURG → asyncPreempt 这条链，面试白板题。
- （后续补）GMP 一图流、channel 底层、goroutine vs asyncio 深题卡。

## 章节地图

| 章节 | 主题 | 一句话 |
|---|---|---|
| `00-execution-model/` | **并发地基** | 进程/线程/协程、为什么 M:N、goroutine 凭什么便宜 ← **想要全局认识从这开始** |
| `01-gmp-scheduler/` | **GMP 调度器** ← 核心① | G/M/P 三件套、运行队列、work-stealing、调度循环 |
| `02-preemption/` | **抢占式调度** ← 核心② | 协作→异步抢占、sysmon/SIGURG/safe point/10ms |
| `03-netpoller-blocking/` | **阻塞与 netpoller** ← 核心③ | 网络 I/O park/unpark、syscall 时 P 交接、`time.Sleep` 怎么让出 |
| `04-goroutine/` | goroutine 实战 | 创建/栈增长/泄漏、凭什么开几十万 |
| `05-channel-select/` | channel 与 select | hchan 底层、缓冲/关闭/nil 语义、select |
| `06-sync-memory-model/` | sync 与内存模型 | Mutex/atomic、happens-before、数据竞争 + `-race` |
| `07-context/` | context 与取消传播 | 超时/取消/传值、取消树 |
| `08-patterns/` | 并发模式(实战) | worker pool / fan-in-out / pipeline / errgroup / 限流 / 优雅关闭 |
| `09-pitfalls-tuning/` | 陷阱与调优 | 泄漏/死锁、GOMAXPROCS、pprof/trace、与 GC 交互 |
| `99-interview-cards/` | 面试卡 | 速答表 + 深题卡 |

每章 7 段：**核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结**。

## 进度地图

| 章节 | 状态 | 备注 |
|---|---|---|
| 设计 spec | ✅ 完成 | `docs/superpowers/specs/2026-05-30-go-concurrency-design.md` |
| 骨架 + 进度地图 | ✅ 完成 | 本文件 |
| 00-execution-model | ✅ 完成 | 并发地基 + 三方对照(Java/asyncio/goroutine) |
| 01-gmp-scheduler | ✅ 完成 | GMP 内核(G/M/P、三队列、work-stealing、为什么要 P) |
| 02-preemption | ✅ 完成 | 抢占(样章·已认可调子) |
| 03-netpoller-blocking | ✅ 完成 | netpoller(网络不阻塞 M) + P 交接(文件/cgo) + time.Sleep 实现 |
| 04-goroutine | ✅ 完成 | 创建成本/可增长栈/泄漏排查/循环变量捕获 |
| 05-channel-select | ✅ 完成 | hchan 底层/无缓冲vs有缓冲/close 语义/select/nil channel |
| 06-sync-memory-model | ✅ 完成 | atomic/Mutex(不可重入)/happens-before/data race/-race |
| 07-context | ✅ 完成 | 取消树/超时穿透/防泄漏/传播惯例/Value 慎用 |
| 08-patterns | ⬜ 待写 | 并发模式 |
| 09-pitfalls-tuning | ⬜ 待写 | 陷阱调优 |
| 99-interview-cards | ⬜ 待写 | 面试卡 |

## 关联已有笔记（复用不重复）

- `performance-tuning-roadmap/05a-go-profiling/03-go-gc-runtime.md` — GC + GOGC/GOMEMLIMIT（第 09 章引用，本课不重讲 GC 细节）
- `performance-tuning-roadmap/05a-go-profiling/0{1,2,4}-*.md` — pprof / trace / race 工具（第 09 章引用）
- `performance-tuning-roadmap/05b-go-debugging/01-goroutine-leak.md` — 泄漏排查实操
- `performance-tuning-roadmap/00-os-fundamentals/05-process-thread-coroutine.md` — OS 层进程/线程/协程
- `python-concurrency/99-interview-cards/q-asyncio-vs-goroutine.md` — 反向对标锚点（本课会升级成深题卡）
- `java/concurrent/*` — Java 并发基础，做对标锚点
