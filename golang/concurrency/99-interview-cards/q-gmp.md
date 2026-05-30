# 讲一下 GMP / 为什么要 P

## 一句话回答

GMP 是 Go 的调度模型：**G** = goroutine（任务）、**M** = OS 线程、**P** = 逻辑处理器（执行 Go 代码的许可证 + 一条本地运行队列）。**M 必须占住一个 P 才能执行 G**；P 的数量 = `GOMAXPROCS`（默认核数），决定并行度。引入 P 的根本目的是：**给每个执行槽配一条本地无锁队列，打碎早期 GM 模型那把全局锁。**

## 三件套

| | 是什么 | 关键 |
|---|---|---|
| G | 带自己栈/PC/状态的任务 | 2KB 起，可增长 |
| M | 真 OS 线程 | 数量动态，可超 GOMAXPROCS |
| P | 执行许可证 + 本地队列 | 数量=GOMAXPROCS，固定 |

## 为什么要 P（核心追问）

- **Go 1.0 = GM 模型**：只有 G/M + 一个全局队列 + 一把全局锁。每个 M 找活/放活都抢锁，多核下锁竞争把吞吐压垮，且 G 在 M 间乱跳、缓存局部性差。
- **Go 1.1 引入 P**（Dmitry Vyukov 重设计）：每个 P 自带本地队列，绝大多数调度走本地、**无锁**；全局锁只在访问全局队列/工作窃取时才用。这是 Go 调度器能扩展到多核的根本一步。

记因果：**P = 把全局锁拆成 per-P 本地无锁。**

## 一个 G 怎么被选中（findRunnable 顺序）

1. 每 61 次调度先瞄一眼全局队列（防全局队列饿死）
2. 自己 P 的本地队列（含 `runnext` 单槽，新建 G 的局部性优化）
3. 本地空 → 全局队列拿一批（加锁）
4. → netpoll（网络就绪的 G）
5. → work stealing：随机偷别的 P 队列的一半
6. 都没有 → M 休眠，交还 P

## 证据链接

- 正文：[`01 GMP 调度器`](../01-gmp-scheduler/README.md)
- 抢占里的 sysmon、阻塞里的 P 交接：[`02`](../02-preemption/README.md) / [`03`](../03-netpoller-blocking/README.md)

## 易追问的延伸

- **M 能超过 GOMAXPROCS 吗？** 能——阻塞在 syscall 的 M 不占 P，runtime 另起 M 接管 P（[03](../03-netpoller-blocking/README.md)）。
- **和 Java 的关系？** P 的本地队列+工作窃取 = ForkJoinPool 骨架；Loom 虚拟线程调度器就是 ForkJoinPool，M≈carrier 线程。
- **GOMAXPROCS 决定 goroutine 上限吗？** 不，它只决定**并行度**；goroutine 数受内存限制（几十万级）。
- **g0 是什么？** 每个 M 的系统 goroutine，调度逻辑跑在它的栈上。
