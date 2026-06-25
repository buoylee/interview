# 01 · 调度/CPU → 并发模型与容量

> **薄镜头契约**：本章不重教调度机制（那是 [`linux-handson/03`](../../linux-handson/03-process-model/) 的活），不推 Little 数学（指向 `cc`）。只教一件事：**看到 CPU/调度原语，反射出设计期决策**。

---

## 一、盲点

你现在只会**事后解释**：cs 高了？线程开太多；us 爆了？CPU 密集；被 throttle 了？limit 设小了。这是资深·反应式，对的，但不够。

架构师的差别在**事前设计**：还没写代码就知道"这套并发模型会产生多少 cs"、"这个核数 + 业务阻塞比应该推出多大线程池"、"容器 CPU limit 设多少才不拖垮 P99"。

**一句点破**：资深是被问题推着走，架构师是在设计时就把问题挡在门外。

---

## 二、原语 → 决策映射表

> 三列读法：OS 原语是约束；资深·能答是你已经会的事后读指标；架构师·能设计是事前把这个约束翻成设计文档里的决策。

| OS 原语 | 资深·能答（反应式） | 架构师·能设计（预判式） |
|---|---|---|
| **上下文切换有成本**（每次 cs 消耗 μs 级 CPU，切换频率由线程数驱动） | cs 高 → "线程开太多" | 用核数 + Little 定律反推线程池 / worker 数上限，**定容量而非拍脑袋**；目标：cs 率不随负载爆炸 |
| **CPU 密集 vs IO 密集**（us 反映纯算力，wa 反映阻塞等待） | us 高 → CPU 密集；wa 高 → IO 密集 | 据此选并发模型：CPU 密集 → 多进程（绕 GIL）或 goroutine + 核绑定；IO 密集 → 协程 / 异步 / 线程池，worker 数可远超核数 |
| **CFS CPU quota 限流**（cgroup `cpu.cfs_quota_us` 控制容器每调度周期可用 CPU 时间） | "被 throttle 了" → limit 调大 | CPU limit 是 **throttle 陷阱**：高并发 burst 会耗尽 quota 导致 P99 尖刺；设计时 request = 保底，limit 留 headroom，关注 `container_cpu_cfs_throttled_seconds_total` |
| **NUMA 跨节点内存延迟**（多路服务器上，访问远端 NUMA 节点内存延迟约本地 1.5-2×） | numastat 显示跨节点访问多 | 大内存、高并发进程**绑核绑 NUMA 节点**（`taskset` / `numactl`）；Kubernetes 用 TopologyManager + `SingleNUMANode` 策略消除跨 NUMA 开销 |
| **内核态 vs 用户态时间**（`sy` 高说明系统调用/中断/切换开销占用 CPU） | sy 高 → 系统调用太频繁 | 批量 IO（`writev` / `sendfile`）、减少 `syscall` 数、io_uring 绕同步 syscall；设计时评估调用路径的 syscall 密度 |
| **进程/线程 vs 协程的调度粒度**（OS 调度单位是线程；协程在用户态调度，无 cs 代价） | 看到协程 → "省内存" | 协程仅适合 IO 密集且**无 blocking call**的路径；混入 CPU 密集 / 同步 blocking 会饿死调度器；设计时明确**每类任务走哪条调度路径** |

---

## 三、定量锚点

两条公式，**先记反射，完整推导进深矿**：

**线程池大小（阻塞式）**

```
线程数 ≈ 核数 ÷ (1 − 阻塞占比)
```

- 纯 CPU 密集（阻塞占比 ≈ 0）→ 线程数 ≈ 核数（不超过 2×）。
- IO 密集（阻塞占比 0.9）→ 线程数 ≈ 10 × 核数。
- 协程/异步模型：等效"无阻塞"，worker 数回归核数。

**Little 定律（并发量上界）**

```
并发 = 吞吐 × 延迟     （L = λ × W）
```

- 例：吞吐 1 000 req/s，P99 延迟 200ms → 系统同时在飞的请求 ≈ **200 个**；线程池要能承住 200 并发，否则请求排队，延迟雪崩。

完整推导和 sizing 算法：[`../../concurrency-capacity/01-littles-law/`](../../concurrency-capacity/01-littles-law/) 和 [`../../concurrency-capacity/04-sizing-one-node/`](../../concurrency-capacity/04-sizing-one-node/)。本章不展开。

---

## 四、决策清单 & 反模式

**设计 CPU/并发时，该问自己的问题：**

- 这个服务是 CPU 密集、IO 密集，还是混合？比例大概几比几？
- 在目标核数和预期延迟下，Little 定律算出的并发量是多少？线程池能承住吗？
- 任务里有没有 blocking call（JDBC、同步文件 IO）？有的话协程是个陷阱，不能用异步框架糊弄过去。
- 容器 CPU request/limit 是拍脑袋还是从 profile 数据推导的？`cpu_cfs_throttled` 指标有没有监控？
- 有没有多路 NUMA 机器？大内存 / 高线程数服务有没有 NUMA 亲和配置？

**反模式（设计期常见错误）：**

1. **拍脑袋线程池 200**：没有任何性能数据支撑，线上 cs 率拉满，CPU 有效利用率反而低。正解：核数 + 阻塞比 + Little 定律三角定容量。

2. **容器只设 limit 不设 request**（或 request 远小于 limit）：调度器无法保证 CPU 资源，突发时被 throttle，P99 延迟尖刺；QoS 也降为 Burstable 甚至 BestEffort，高优 Pod 驱逐时首先遭殃。

3. **忽略 CFS throttling 对延迟的影响**：以为 limit = 1.0 CPU 就能稳定跑，实际高并发 burst 耗尽 quota 窗口，整个调度周期（默认 100ms）内进程全部冻结，P99 出现 100ms+ 尖刺。排查时看 `container_cpu_cfs_throttled_seconds_total` 而非只看 CPU 使用率均值。

4. **在协程框架里调同步阻塞 API**（asyncio + `requests`、Go + `syscall.Read` without goroutine）：阻塞调用卡住 event loop / 调度器线程，其余协程全部饿死，吞吐断崖。

5. **CPU 密集任务用多线程（Python/Ruby GIL 语言）**：线程数再多也只有一个 GIL 持有者，cs 开销 × n 线程，吞吐不升反降。正解：多进程（`multiprocessing`）或换语言/换运行时（Go / JVM）。

---

## 五、指针

**往下打地基（机制不熟时）：**

- [`../../linux-handson/03-process-model/`](../../linux-handson/03-process-model/) —— 进程/线程/上下文切换机制 + 动手实验（`pidstat`、`perf`、`stress-ng`）。
- [`../../performance-tuning-roadmap/00-os-fundamentals/01-cpu-architecture-scheduling.md`](../../performance-tuning-roadmap/00-os-fundamentals/01-cpu-architecture-scheduling.md) —— CFS 调度算法、`nice` / `cgroup` cpu.shares / quota 深度；资深性能机制层。

**往深挖决策（要完整数学/容量公式时）：**

- [`../../concurrency-capacity/01-littles-law/`](../../concurrency-capacity/01-littles-law/) —— Little 定律完整推导 + 实测校准。
- [`../../concurrency-capacity/02-concurrency-models/`](../../concurrency-capacity/02-concurrency-models/) —— 线程 / 协程 / 多进程 / 异步 IO 选型决策树。
- [`../../concurrency-capacity/04-sizing-one-node/`](../../concurrency-capacity/04-sizing-one-node/) —— 单机 CPU + 线程池 sizing 全流程。

---

## 六、面试转化

**题 1：你怎么定线程池大小？**

- **能答（事后）**：看监控，cs 高了就说"线程太多"，或者凭经验说"200 个差不多"。
- **能设计（事前）**：先问业务形态——IO 密集还是 CPU 密集？量化阻塞占比。然后用公式：`线程数 ≈ 核数 ÷ (1 − 阻塞占比)`。再用 Little 定律验算并发量上界：`并发 = 吞吐 × P99 延迟`，确认线程池能承住峰值并发。最后用压测校准，看 cs 率和 CPU 利用率是否在合理区间，再锁定数值。

**题 2：为什么线程不是越多越好？**

- **能答（事后）**：线程太多 cs 高，CPU 浪费在切换上。
- **能设计（事前）**：存在两个约束下界和上界同时夹逼。下界：线程太少，IO 阻塞期间 CPU 空转，吞吐低。上界：线程过多，cs 本身消耗 CPU（每次 μs 级，× 高并发 = 不可忽略）；内存压力上升（每线程栈 ~1-8MB）；调度延迟增加，P99 变差。最优点在公式给出的区间附近，用 Little 定律确认并发量边界，压测找到 cs 率开始抬头的拐点，那就是你的 limit。

**题 3：容器 CPU limit 设多少合适？（追问）**

- **能答**：设成峰值用量就行。
- **能设计**：先分离 request（调度保底，等于正常负载用量）和 limit（突发上限）。limit 过低会触发 CFS throttle，产生 P99 尖刺；过高会在节点 CPU 超卖时抢邻居资源。正确做法：request 从 profile 数据取 p95 用量，limit 留 2-3× headroom，部署后监控 `cpu_cfs_throttled_seconds_total`，如果 throttle 率 > 5% 就调高 limit 或拆任务。

---

> **小结**：CPU 原语的设计镜头就三个反射：① 上下文切换成本 → 线程池有上限；② 密集类型 → 并发模型选型；③ CFS quota → throttle 陷阱。数字全从 `核数 + 阻塞比 + Little` 算出来，不靠拍脑袋。
