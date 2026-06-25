# 07 · 应用级资源饱和监控 —— 系统层看不见的那半张脸

> **问题意识**:一台 CPU 才 30%、内存正常的机器,P99 为什么会在 200ms 突然跳到 3s?`top` 显示「很闲」,但用户已经在超时了。这就是「系统层看不见」的那半张脸——有界逻辑资源的饱和。本章是整个 `03-observability` 路径的综合收口,不重复推导已有内容,只把应用层资源监控的体系串联起来。

---

## §1 系统层看不见的那半张脸

`top` 和 `vmstat` 给你看的是硬件层和内核层:CPU 核、内存页、网络带宽。这些指标是必要的,但对应用级并发资源来说**完全不够**。

### 「低 CPU + 高延迟」的特征签名

当你看到这套组合时,几乎可以直接断定:某个有界逻辑资源正在饱和,而不是物理硬件在瓶颈。

| 信号 | 表现 |
|---|---|
| CPU 用率 | 稳定在 20–60%,没有飙升迹象 |
| P99 延迟 | 突然或渐进爬升,甚至断崖式跳变 |
| 错误率 | 开始出现 503 / 429 / timeout |
| `top` 显示 | idle 百分比高,`wa` 通常不高(等待发生在用户态,不是内核 I/O) |

**为什么 CPU 不高?** 核心在于:阻塞 I/O 不烧 CPU。

一个线程在等数据库返回结果时,它被 OS 调度器放进等待队列,不占 CPU 时间片。在 Python 这层,`async/await` 协程在 `await` 处让出事件循环,同样不占 GIL,不消耗 CPU cycle。等待中的协程或线程是**静默**的——它们在 C 层释放了 GIL(Python 的 I/O 系统调用会在进入内核前释放 GIL)、在 OS 的等待队列里 park。`top` 看到的 CPU 反映的是「谁在真正做计算」,而「谁在等资源」是另一张账。

### fastapi-ops 的两个经典案例

这一现象在 [`fastapi-ops/01-foundation`](../../fastapi-ops/01-foundation/README.md) 里已经用真实可运行代码解剖过:

- **A5 阻塞循环**:在 `async def` 路由里直接写 `requests.get()`(同步 HTTP),事件循环被这一个请求占住——其他所有并发连接一起冻住。QPS 上不去、P99 爆炸,但 CPU 还没满,因为大家在排队等那条被占住的线程。

- **A6 线程池 40 令牌**:即使把同步调用正确地丢进 `run_in_threadpool`,线程池也有上限(`anyio.CapacityLimiter`,默认 40 tokens/worker)。第 41 个同步任务来了没令牌——**排队**。饱和就此发生,表现依然是「CPU 不高但延迟高」。

这两个案例共同说明:导致延迟爆炸的不是计算量,而是**有界资源的队列堆积**。

---

## §2 统一心智模型:每个有界资源 = 一个队列(M/M/c)

应用层里所有需要「排队等待」的资源,结构上都是同一件事:一个有容量上限(`c`)的服务系统 + 一条等待队列。

```
事件循环          c=1(单线程)   等待队列 = 未被 await 的协程
线程池            c=N(线程数)   等待队列 = 超出令牌的同步任务
连接池            c=pool_size   等待队列 = 等待借出连接的请求
OS accept queue   c=backlog     等待队列 = 未被 accept() 的连接
```

每个有界资源都值得盯**三个数**:

| 维度 | 含义 | 为什么要盯 |
|---|---|---|
| **利用率**(`in-use / 容量`) | 资源被用了多少比例 | 看总体负载水位;但它是**滞后指标**,且到 100% 就封顶——看不出「过载了多少」 |
| **饱和度/等待**(队列深度) | 当前有多少工作在排队 | **领先指标**——队列一开始堆积就在延迟飙升之前发出信号;可以无上限增长,直接量出过载程度 |
| **拒绝/溢出** | 因为满了被丢掉多少 | 不可逆的损失;出现即告警 |

> **核心推论:告警要建在饱和度上,不是利用率上。** 利用率 80% 不一定有问题,但等待数 > 0 持续几十秒就说明系统承受了超出容量的负载。

M/M/c 排队模型的推导——为什么小池子在利用率高时等待时间会非线性爆炸——在 [`concurrency-capacity/05-pools`](../../concurrency-capacity/05-pools/README.md) 里有完整解析,以及那个著名的「×worker 总账」坑(`单池大小 × worker 数 × 副本数`)。饱和度作为领先指标的底层原理和监控清单在 [`concurrency-capacity/08-monitoring-concurrency`](../../concurrency-capacity/08-monitoring-concurrency/README.md) 里。本章不重推,只在这个框架上做应用层的跨层资源梳理与告警范式。

---

## §3 跨层资源清单:从边缘到内核每层盯什么

应用请求路径上的有界资源并不在同一层。故障可能在任何一层首先发生,因此每层都要有对应的监控探头。

### 层 0 · 边缘(Nginx / 负载均衡)

**盯什么:** `active connections`(当前并发连接数)、`accepts` 与 `handled` 的差值(accept 了但没处理完 = 连接积压)、upstream 失败率。

**为什么:** Nginx 的 worker_connections 上限是配置项,一旦打满,新连接进不来,用户端直接超时——但机器本身 CPU 和内存完全正常。`accepts > handled` 的差是 backlog 溢出的早期信号。

Nginx 这层的完整可观测性方法——`stub_status`、upstream health、错误日志——见 [`nginx/10-observability-debugging.md`](../../nginx/10-observability-debugging.md),本章只引用结论。

---

### 层 1 · 应用运行时(Event Loop / GC / Goroutine)

**盯什么:** 因语言不同而异,但关注的是**运行时自身的有界资源**。

**Python / asyncio:**
- **Event-loop lag(事件循环滞后)**:循环处理一批事件的实际耗时与预期间隔之差。正常应在 1–5ms 以内;飙升到几十 ms 说明循环被某个回调占住了(即 A5 的阻塞场景)。可用 `loop.slow_callback_duration` 或定时埋点来测量。
- **线程池等待**:`anyio.CapacityLimiter` 的当前 borrowed / total_tokens 比率,以及 waiting 计数(等待令牌的协程数)。

**Java(JVM):**
- **GC 停顿时间和频率**:Full GC 时 Stop-the-World,所有线程 park,表现为周期性延迟尖峰——CPU 正常但 P99 每分钟一次脉冲。
- **线程池队列长度**:`ThreadPoolExecutor.getQueue().size()`;Micrometer 的 `executor.queued` 指标。

**Go:**
- **Goroutine 总数**:`runtime.NumGoroutine()`;goroutine 泄漏的特征是这个数只涨不降。
- **GC Pause** 和 **调度延迟**:`runtime/metrics` 暴露的 `/sched/latencies:seconds` 直方图。
- Go 没有「线程池被挤满」的概念——goroutine 由运行时调度,不绑定 OS 线程数量,但 goroutine 数量本身就是资源消耗的替代指标。

**为什么归为一层:** 这些都是运行时自己管理的资源,不是你显式创建的池——但它们同样有隐性上限,且饱和时同样导致「CPU 不高但延迟高」。

---

### 层 2 · 应用逻辑池(自建 Worker Pool / Semaphore)

**盯什么:** 池内 active workers / 总 worker 数、等待队列深度、任务拒绝数。

**为什么:** 你自己用信号量或 goroutine 池限制并发的地方,是第一道「主动保护」边界。一旦请求速率超过 `capacity / avg_task_time`,等待队列就开始堆积。**这里的等待队列深度是 §2 心智模型里最纯粹的体现**——没有其他层的干扰,直接反映你业务逻辑的并发能力。

---

### 层 3 · 下游连接池(DB / Redis / HTTP Client)

**盯什么:** 借出数(`active`)、池大小(`max`)、等待借连接的请求数(`pending_acquires`)、等待耗时尾延迟、超时次数。

**为什么:** 这是实战中最容易被忽视、但最致命的一层。单个实例看起来连接数正常,但 `单池大小 × worker 数 × 副本数` 的总量可能早就超过数据库的 `max_connections`。连接池满了,新请求在这里等——这正是「CPU 不高但数据库查询慢」的根因。

HikariCP 的完整监控指标与告警配置见 [`performance-tuning-roadmap/09a-database/04-connection-pool-monitor.md`](../09a-database/04-connection-pool-monitor.md),本章只给定位框架。

---

### 层 4 · 系统层(CPU / 内存 / 网络 / FD)

**盯什么:** CPU idle、内存使用、网络带宽、file descriptor 数。

**角色:用于「确认 CPU 确实闲」,而非作为主要告警来源。**

这一层的数字应该与上面的应用层指标**交叉验证**:应用层饱和但 CPU 低 → 确认是 I/O 等待或资源竞争,不是计算瓶颈。如果 CPU 真的高,再往计算路径找原因。

Linux 层的 `us/sy/wa` 分解和 `netstat backlog` 分析见 [`linux-handson/07-troubleshooting-playbook`](../../linux-handson/07-troubleshooting-playbook/README.md) 和 [`linux-handson/06-networking`](../../linux-handson/06-networking/README.md)。

---

## §4 三语言对照速查表(Python / Go / Java)

| 资源 | Python | Go | Java | 建议标准指标名 |
|---|---|---|---|---|
| 事件循环/反应式循环延迟 | 后台 task 量 loop 漂移 → `asyncio_event_loop_lag_seconds`;`loop.slow_callback_duration` | **无对应物**(runtime 自动扩 M);只有 `go_sched_latencies_seconds` | Netty `SingleThreadEventExecutor.pendingTasks()`;Reactor `boundedElastic`;WebFlux「别阻塞 loop」 | `process.runtime.*` |
| 线程池/调度饱和 | `anyio.to_thread.current_default_thread_limiter().statistics().tasks_waiting`/`.borrowed_tokens` | 自建 `app_worker_inflight` + `db.Stats().WaitCount` | `executor.queued`/`executor.active`/`executor.rejected`;Tomcat `tomcat.threads.busy` | `app_*`(无 OTel 约定);Python:`app_threadpool_tasks_waiting`/`app_threadpool_borrowed_tokens`/`app_threadpool_total_tokens`;Go:`app_worker_inflight`/`app_db_pool_wait_count_total` |
| 连接池 | `engine.pool.checkedout()`/`.overflow()` 或 asyncpg `pool.get_idle_size()`;自建:`app_db_pool_checked_out`/`app_db_pool_overflow` | `db.Stats()`:`InUse`/`Idle`/`WaitCount`/`WaitDuration`;自建:`app_db_pool_in_use` | HikariCP `hikaricp.connections.active`/`.idle`/`.pending` | `db.client.connection.count{state}`、`db.client.connection.pending_requests` |
| 运行时(GC/线程数) | `threading.active_count()`;`python_gc_collections_total`/`process_open_fds`(prometheus_client 默认) | `go_goroutines`/`go_threads`/`go_gc_duration_seconds` | JVM threads/GC via Micrometer/Actuator | `process.runtime.*` |
| 自建 semaphore/worker pool | 自建 Gauge | 自建 Gauge(channel len / semaphore 持有数) | 自建 Gauge / `ExecutorServiceMetrics` | `app_*` |

> **Go 为何「事件循环行」无对应物**:Go 运行时采用 G-M-P 调度模型,M(OS 线程)由运行时按需动态创建和销毁,不存在固定容量的「事件循环线程」可被占满。阻塞型系统调用会触发运行时自动增派 M,使其他 goroutine 继续并行执行。因此 Go 的饱和信号不在「循环延迟」,而在调度延迟(`go_sched_latencies_seconds`)和 goroutine 数量异常增长——与 Python asyncio 的单线程事件循环模型根本不同。

落地参考:Java 连接池全套监控见 [`../09a-database/04-connection-pool-monitor.md`](../09a-database/04-connection-pool-monitor.md);Go 连接池字段释义(`InUse`/`Idle`/`WaitCount`/`WaitDuration`)见 [`../../golang/stdlib/03-database-sql/README.md`](../../golang/stdlib/03-database-sql/README.md);Python asyncio 慢回调调试见 [`../06b-python-debugging/02-asyncio-debugging.md`](../06b-python-debugging/02-asyncio-debugging.md)。

---

## §5 通用 PromQL + 告警范式

### 核心原则:告警建在饱和度,不是利用率

这不是品味问题,而是时序上的必然。利用率是**同步**指标——资源满了才 100%;饱和度(等待数)是**领先**指标——过载一开始队列就动了,可能在用户感知到慢之前几十秒就触发。

USE 方法论和 RED 方法论对饱和度的定义见 [`performance-tuning-roadmap/01-methodology/02-use-method.md`](../01-methodology/02-use-method.md) 与 [`performance-tuning-roadmap/01-methodology/03-red-golden-signals.md`](../01-methodology/03-red-golden-signals.md)。

### 通用 PromQL 模板(语言无关)

以下占位指标名是**故意的**——真实指标名在后续落地章节里按语言给出,这里给出的是告警逻辑的通用结构:

```promql
# 告警 1:饱和领先告警 —— 任何「等待数」> 0 持续 30s
# 原理:等待数从 0 变为正数,就是过载的第一声警报
<saturation_metric> > 0
# for: 30s

# 告警 2:拒绝/溢出出现即告警
# 原理:拒绝是不可逆损失,等待可以消化但拒绝不行
rate(<rejected_total>[5m]) > 0

# 告警 3:等待时间尾延迟
# 原理:P99 等待 > 50ms 意味着部分请求在资源上就已经损失了大量时间
histogram_quantile(0.99, rate(<wait_seconds_bucket>[5m])) > 0.05
```

### ×worker×副本 总账:静态配置检查,而非运行时告警

`单池大小 × worker 数 × 副本数` 的总账是一个**部署时/变更时**的检查项,不是运行时告警。它告诉你理论上峰值连接需求是否超过下游容量。这个分析框架在 [`concurrency-capacity/05-pools`](../../concurrency-capacity/05-pools/README.md) 里有完整推导;实际监控依赖上面的等待数/拒绝数来感知运行时是否真的饱和。

### 指标类型选型

- **等待数、在途数、Gauge**:用 Gauge。数值直接反映当前状态,不需要 `rate()`。
- **拒绝/超时计数,Counter**:用 Counter,配合 `rate()` 看每秒拒绝速率。
- **等待耗时,Histogram**:用 Histogram,配合 `histogram_quantile()` 看尾延迟分布。

指标四种类型的理论基础(Counter/Gauge/Histogram/Summary 的内幕和用法)见 [`03-metrics-theory.md`](./03-metrics-theory.md)。Grafana Dashboard 配置与 Alertmanager 路由写法见 [`04-prometheus-grafana.md`](./04-prometheus-grafana.md) 和 [`06-alerting-oncall.md`](./06-alerting-oncall.md);HikariCP 告警模板见 [`performance-tuning-roadmap/09a-database/04-connection-pool-monitor.md`](../09a-database/04-connection-pool-monitor.md)。

---

## §6 端到端诊断树

**场景**:下游某 API 变慢 → 上游协程/线程/连接被占住不放 → 回压逐层堆积。以下决策树从现象出发,每个分支给出「确认指标 + 会看到什么」,帮助你快速定位饱和层。

```
现象:P99 爆炸,但 `top` 显示 CPU 没满
├─ ① 边缘在排队? → 看 `$request_time` ≫ `$upstream_response_time`(见 nginx/10-observability-debugging.md)
│     或 accept queue:`ss -lnt` 的 Recv-Q 接近 Send-Q(见 linux-handson/06-networking)
├─ ② 事件循环被阻塞?(Python/Node)→ `asyncio_event_loop_lag_seconds` 飙高
│     → 找在 async def 里跑的同步阻塞调用(回扣 fastapi-ops/01 A5)
├─ ③ 线程池饱和? → `tasks_waiting`(Py)/`executor.queued`(Java)持续 > 0
│     → 同步 def 端点过多 / 池太小(回扣 A6 的 40 令牌)
├─ ④ DB 连接池枯竭? → `pending`/`WaitCount` 涨;再看 DB 侧 `Threads_running`
│     高=真业务压力,低=连接被慢查 hang 住堆积(见 mysql-handson/11-ops-and-troubleshooting)
└─ ⑤ 下游慢回压? → 自建 worker/semaphore 的 inflight 触顶 + 下游 P99 涨
      → 别调大池(只是把队列挪到下游),该限流/隔离/async 化(见 concurrency-capacity/07-overload-backpressure)
```

参考链接:
- ① [nginx/10-observability-debugging.md](../../nginx/10-observability-debugging.md) · [linux-handson/06-networking](../../linux-handson/06-networking/README.md)
- ④ [mysql-handson/11-ops-and-troubleshooting](../../mysql-handson/11-ops-and-troubleshooting/README.md)
- ⑤ [concurrency-capacity/07-overload-backpressure](../../concurrency-capacity/07-overload-backpressure/README.md)

**逐层都在问同一个问题——「哪个有界队列满了,而它的饱和系统层看不见」。**

---

## §7 面试速记

以下四题是对前面所有章节核心结论的纯复习,不引入新知识。

---

**Q1:怎么监控线程池的饱和?**

看三个数,优先级从高到低:
1. **等待队列深度**(饱和度,领先):Java 是 `executor.queued`(Micrometer);Python 是 `anyio.CapacityLimiter` 的 `waiting`;这个数 > 0 持续几十秒就应该告警。
2. **活跃线程数 / 池大小**（利用率,滞后但要看）:接近 100% 时说明快到顶了。
3. **拒绝/超时次数**（溢出):出现就告警,不可恢复。

不要只看 CPU。线程在等 I/O 时不烧 CPU,池满了 CPU 照样正常。

---

**Q2:CPU 不高但延迟高,怎么查?**

这是「有界逻辑资源饱和」的特征签名。排查路径:

1. **先确认 CPU 确实闲**:看 `us/sy/wa`,wa 高说明 I/O 等待,不是计算问题。
2. **从外到内逐层看等待数**:边缘(Nginx active conns)→ 运行时(event-loop lag / goroutine 数)→ 逻辑池(semaphore/worker pool 等待)→ 连接池(DB/Redis pending_acquires)。
3. **哪层等待数 > 0 或增长,那层就是瓶颈**。
4. 工具:Prometheus 饱和度指标、`netstat -s` 看 accept 溢出、数据库 `SHOW STATUS` 看连接等待。

---

**Q3:为什么告警要建在饱和度上,而不是利用率上?**

两个原因:

**时序领先**:利用率是同步读数——资源填满才到 100%;队列深度在利用率还没到顶时就开始增长,给你几十秒到几分钟的预警窗口。

**表达能力**:利用率到 100% 就封顶,不能告诉你「过载了多少倍」;饱和度(等待数)可以继续增长,直接量化过载程度。「等待数 > 阈值」的告警比「利用率 > 80%」的告警更早、噪声更少。

> 延伸:这也是为什么 Google SRE 的 USE 方法论把 Saturation 单独拎出来、与 Utilization 并列——它们是两件不同的事。

---

**Q4:Go 为什么没有「线程池被挤满」?**

Go 没有显式的线程池。Goroutine 由 Go 运行时的调度器(G-M-P 模型)管理:

- **M**(OS 线程)数量由运行时动态调整,`GOMAXPROCS` 控制并行度,但 M 可以超过这个数(比如有 goroutine 在系统调用里阻塞时,运行时会创建新 M 来维持并行度)。
- **Goroutine** 本身极轻量(初始 2–8KB 栈,动态增长),启动成本接近函数调用。你可以同时运行几十万个。

所以 Go 里饱和的形式不是「池被挤满」,而是:
- **Goroutine 数量只涨不降**(泄漏)
- **Channel 积压**(`len(ch)` 趋近 `cap(ch)`)
- **`sync.Mutex`/`sync.WaitGroup` 的等待时长**
- **调度延迟**(`/sched/latencies:seconds`)

监控这些,而不是等一个不存在的线程池告警。
