# 06 · 综合：一道设计题，五条资源决策线

> 前五章是五个分开的镜头。这一章把它们装回一台机器：拿一道真实的设计题，**从 OS 约束一路推到部署决策**，让你看见"能设计"长什么样。

---

## 题面（固定假设）

> **设计一个订单查询服务，支撑 5000 QPS、P99 < 100ms。**

先把架构师该先问出来的数字假设钉死（没有数字就没有设计）：

| 维度 | 假设 |
|------|------|
| 吞吐 | 5000 QPS（读为主，写另算） |
| 延迟目标 | P99 < 100ms |
| 单请求耗时 | ~50ms（其中 ~45ms 在等 DB/缓存 I/O，~5ms 计算）→ **IO 密集** |
| 数据规模 | 1 亿订单，单行 ~1KB |
| 访问形态 | 按 order_id 点查为主 + 按 user_id 近期范围查 |
| 部署 | 容器 / K8s，和别的服务混部 |

这张表就是后面五条决策线的输入。**注意"单请求 45ms 在等 I/O"这一条** —— 它会一路决定并发模型、连接池、容量。

---

## 线 ①：调度/CPU → 并发模型与容量 → [`../01`](../01-cpu-and-scheduling/)

- **Little 反推在途请求**：并发 = 吞吐 × 延迟 = 5000 × 0.05s = **250 个在途请求**。
- **IO 密集 → 选模型**：45/50 的时间在等 I/O，CPU 大部分时间闲着。所以**不是按核数堆线程**，而是用能用少量线程扛住 250 个等待的模型：协程 / async（Go goroutine、Python asyncio、Java 虚拟线程），或一个偏大的线程池。
- **CPU 核数**：计算只占 5ms/请求 → CPU 需求 ≈ 5000 × 0.005s = 25 核·秒/秒 → **约 25 核的纯计算**，留余量给 GC/毛刺，定 ~32 核（或多副本分摊）。
- 完整容量推导 → [`cc/01-littles-law`](../../concurrency-capacity/01-littles-law/)、[`cc/04-sizing-one-node`](../../concurrency-capacity/04-sizing-one-node/)。

## 线 ②：虚存/内存 → 内存预算与缓存层 → [`../02`](../02-memory-and-paging/)

- **读密集 → page cache 是免费缓存层**：1 亿 × 1KB ≈ 100GB 数据，热点（近期订单）可能就几 GB。让这几 GB 常驻 page cache / 应用层缓存，点查基本不落盘。
- **内存预算**：容器内存 = 堆 + 堆外 + 栈 × 线程数 + page cache 余量。别把 limit 设成刚好等于堆 —— 留出堆外和 cache 的空间，否则一定被 OOMKill。
- 深挖缓存策略 → [`perf-11/01-caching-strategy`](../../performance-tuning-roadmap/11-architecture/01-caching-strategy.md)。

## 线 ③：存储 IO → 持久化与引擎选型 → [`../03`](../03-storage-io/)

- **点查为主 + 范围查 → B+ 树系**：order_id 点查、user_id 近期范围查，都吃**有序索引**，选 B+ 树（MySQL/PG）而非 LSM（LSM 利于写密集，本题读多写少）。
- **覆盖索引**：把查询要的列做进 `(user_id, created_at)` 联合/覆盖索引，避免回表随机 IO。
- **读写放大**：1 亿行的二级索引 + 回表是随机 IO 大头 → 用覆盖索引 + 缓存把随机 IO 压到最低。
- 存储选型深矿 → [`sd/06-存儲選型`](../../system-design/06-存儲選型.md)、规模化 → [`sd/07`](../../system-design/07-數據規模化-分庫分表與讀寫分離.md)。

## 线 ④：网络/连接 → 连接模型与容量 → [`../04`](../04-network-and-connections/)

- **入站**：5000 QPS 用 **HTTP keep-alive 长连接**，别每请求新建（否则 TIME_WAIT/端口耗尽）。
- **出站连接池**：到 DB/缓存的连接池大小同样用 Little —— 到 DB 的并发 = DB QPS × DB 单次延迟。比如缓存未命中 1000 QPS × 8ms ≈ 8 个 DB 连接在途 → 池子 ~16（留余量），**不是越大越好**（连接也是 DB 的内存/CPU）。
- **背压**：accept queue/超时设好，过载时快速失败而非堆积。
- 连接池深矿 → [`cc/05-pools`](../../concurrency-capacity/05-pools/)、背压 → [`cc/07`](../../concurrency-capacity/07-overload-backpressure/)。

## 线 ⑤：隔离/cgroup → 多租户与隔离设计 → [`../05`](../05-isolation-and-cgroups/)

- **request = 稳态、limit = 峰值 + 余量**：按线①算出的 ~25 核稳态设 request，峰值留头设 limit；CPU limit 设太低会被 CFS throttle，直接拉爆 P99。
- **隔离**：这个延迟敏感的查询服务，别和批处理/离线任务混部抢 CPU（noisy neighbor）；关键路径给 Guaranteed QoS。
- 深矿 → [`perf-12/01-cgroup-resource`](../../performance-tuning-roadmap/12-container/01-cgroup-resource.md)、隔离 → [`cc/06-isolation`](../../concurrency-capacity/06-isolation/)。

---

## 五条线汇成一张设计决策表

| 资源 | 关键数字 | 决策 |
|------|---------|------|
| CPU/并发 | 250 在途、25 核计算 | async/协程模型 + ~32 核（或多副本） |
| 内存 | 热点几 GB | page cache/应用缓存当缓存层；limit 留堆外+cache 余量 |
| 存储 | 1 亿行、读多写少 | B+ 树 + 覆盖索引；缓存挡随机 IO |
| 网络 | 5000 QPS、DB 8 在途 | 入站 keep-alive；出站连接池 ~16 + 背压 |
| 隔离 | 稳态 25 核 | request=25/limit 留余；延迟敏感独占、Guaranteed |

**这就是"能设计"**：从 5000 QPS / P99<100ms 这两个数字，沿五条 OS 约束线，推出一套可写进设计文档的决策 —— 在写第一行代码之前。

---

## 接着练

这一章是单机视角的资源决策。要把它放大到**完整系统设计场景题**（容量估算 → 架构 → 取舍 → 演进），去 [`system-design-scenarios/`](../../system-design-scenarios/) 的"整机装配线"，那里有固定模板和成套场景题。本课负责的，是让你在那些场景题里，每碰到一个资源约束都能反射出对应的设计决策。
