# 09 · 并发模式与调优 —— 把武器拼成实战

> 前面学了 threading / multiprocessing / asyncio / 任务队列。这章把它们拼成生产里反复出现的几个**模式**（限流、连接池、超时重试熔断、fan-out/fan-in、隔离），再讲怎么调优和剖析。这些模式你在 Java/Go 里大多见过（Resilience4j、Hystrix、连接池），这里给 Python 落地。
>
> 前置：第 02–08 章。

---

## 1. 核心问题

1. 海量并发请求怎么限流，别把自己或对端打挂？
2. 连接池为什么关键？为什么「连接池大小 × worker 数」是个坑？
3. 超时、重试、熔断在 Python 怎么落地？
4. 并发代码怎么调优、怎么定位瓶颈？

---

## 2. 直觉理解

并发的工程难点从来不是「怎么并发」，而是「**怎么有节制地并发**」：无限并发会耗尽内存、打垮下游、放大故障。本章的模式本质都在回答同一件事——**给并发装上闸门、护栏和保险丝**。

---

## 3. 原理深入：核心模式

### 3.1 限流：Semaphore 控制并发数

最常见的需求：并发抓 1 万个 URL，但同时在飞的不能超过 N 个（否则打挂对端或自己 OOM）。

```python
# asyncio 版（第 04 章）
import asyncio
sem = asyncio.Semaphore(20)               # 同时最多 20 个在飞
async def fetch(client, url):
    async with sem:
        return await client.get(url, timeout=10)

# 线程版（第 02 章）：threading.Semaphore 同理
```

> 这是 fan-out 时的标配护栏。对标 Java 的 `Semaphore` 限流、Resilience4j 的 Bulkhead。

### 3.2 连接池：复用昂贵连接（关键中的关键）

每次新建 DB/HTTP 连接都要握手，昂贵。连接池预先建好一批复用。**几乎所有 async 库都内置连接池**：

```python
# httpx：AsyncClient 本身就是连接池，复用它别每次新建
async with httpx.AsyncClient(limits=httpx.Limits(max_connections=100)) as client:
    ...   # 整个生命周期复用这个 client

# asyncpg：连接池
pool = await asyncpg.create_pool(dsn, min_size=10, max_size=20)
async with pool.acquire() as conn:
    await conn.fetch("SELECT ...")
```

> **第 07 章那个坑再强调**：每个 worker 进程有独立连接池。**对数据库的总连接数 = 单池 max_size × worker 数 ×机器数**。配 `max_size=20`、20 个 worker → 400 连接，很容易撞上数据库的 `max_connections` 上限。算总账！

### 3.3 超时 / 重试 / 熔断（对标 Resilience4j / Hystrix）

```python
# 需要: pip install tenacity
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),                          # 最多 3 次
    wait=wait_exponential(multiplier=1, max=10),          # 指数退避：1s,2s,4s...
    retry=retry_if_exception_type(httpx.TransportError),  # 只对特定异常重试
)
async def call_downstream():
    async with asyncio.timeout(5):                        # 每次都带超时（第 04/05 章）
        return await client.get(url)
```

- **超时**：每个外部调用必须带（`asyncio.timeout` 或库参数），否则一个慢下游能拖垮你。
- **重试**：用 `tenacity`（Python 的 Resilience4j），指数退避 + 抖动，只重试可恢复的错误（别重试 4xx）。
- **熔断**：下游连续失败时直接快速失败、不再打它（给它喘息）。Python 有 `purgatory`、`pybreaker` 等库；或在网关/服务网格层做。
- **幂等**：重试的前提是操作幂等（呼应第 08 章）。

### 3.4 Fan-out / Fan-in

并发发起一堆任务、再汇总结果——`gather`/`TaskGroup` 就是干这个的（第 04 章）：

```python
async def fan_out_in(ids):
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(fetch_one(i)) for i in ids]   # fan-out
    return [t.result() for t in tasks]                        # fan-in 汇总
```

> 配合 3.1 的 Semaphore 限制 fan-out 的宽度，别一次 fan 出一万个。

### 3.5 隔离（Bulkhead）

不同类型的活用**不同的池**，互不影响：慢任务一个池、快任务一个池；CPU 活进程池、I/O 活线程池。一类活把池占满了，不会饿死另一类。第 05 章 `run_in_executor` 建专用线程池、第 08 章拆队列，都是这个思想。

---

## 4. 日常开发应用

- **任何并发批处理**：`Semaphore 限流 + TaskGroup fan-out/in + 每个调用带 timeout` 是黄金三件套。
- **任何外部调用**：超时是必须，重试看幂等，熔断看重要性。
- **复用连接池对象**：别在循环里反复建 client/pool。
- **CPU 与 I/O 分离**：别在事件循环里算，别用线程池跑 CPU 密集。

---

## 5. 生产 & 调优实战

### 调优清单

- **池大小**：线程池按 I/O 等待占比估、进程池≈核数、连接池要算「× worker 数」的总账（3.2）。
- **uvloop**：asyncio 服务换 uvloop，吞吐 +2~4 倍，近乎零成本（第 04/05 章）。
- **worker 数**：同步≈2×核数+1、异步≈核数（第 07 章），最终压测定。
- **减少跨进程序列化**：multiprocessing 大数据用共享内存或向量化（第 03 章）。

### 怎么定位瓶颈（剖析）

- **py-spy**：不改代码、不停服务，直接采样看 CPU 热点和线程栈。卡住了就 `py-spy dump --pid <pid>` 看每个线程/协程停在哪。
- **事件循环阻塞检测**：debug 模式慢回调 + 看门狗（第 05 章）。
- **压测**：`wrk`/`hey`/`locust` 打压力，看 QPS、P99、错误率随并发的变化曲线，找拐点。

> 完整工具和案例见 `performance-tuning-roadmap/06a-python-profiling/` 和 `06b-python-debugging/`，本课不重复。

### 一个完整的生产级并发抓取（集大成）

```python
import asyncio, httpx
from tenacity import retry, stop_after_attempt, wait_exponential

sem = asyncio.Semaphore(20)                                   # 限流

@retry(stop=stop_after_attempt(3), wait=wait_exponential(max=10))
async def fetch(client, url):
    async with sem:                                           # 限并发
        async with asyncio.timeout(10):                       # 超时
            r = await client.get(url)
            r.raise_for_status()
            return r.json()

async def main(urls):
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=50)) as client:  # 连接池
        async with asyncio.TaskGroup() as tg:                 # 结构化 fan-out
            tasks = [tg.create_task(fetch(client, u)) for u in urls]
    return [t.result() for t in tasks]                        # fan-in
```

---

## 6. 面试高频考点

**Q1：并发抓取大量 URL 怎么防止打挂自己/对端？**
用 `Semaphore` 限制同时在飞的请求数（限流）+ 复用连接池 + 每个请求带超时 + 失败指数退避重试。别无限 fan-out。

**Q2：连接池在多 worker 部署下要注意什么？**
每个 worker 有独立连接池，对数据库总连接数 = 单池大小 × worker 数 × 机器数，极易打满数据库 `max_connections`，必须算总账。

**Q3：超时、重试、熔断分别解决什么？**
超时防被慢下游拖死；重试（指数退避，仅幂等操作）抗瞬时故障；熔断在下游持续失败时快速失败、避免雪崩和持续打击下游。

**Q4：Python 怎么实现重试？**
用 `tenacity` 库：声明式配置重试次数、退避策略、触发异常类型，类似 Java 的 Resilience4j。

**Q5：并发服务变慢了怎么定位？**
py-spy 采样看 CPU 热点和卡住的栈、asyncio debug 模式/看门狗查事件循环阻塞、压测看 QPS/P99 随并发的拐点，结合连接池/worker 配置排查。

---

## 7. 一句话总结

并发工程的核心是「**有节制地并发**」：用 Semaphore 限流、连接池复用（并算清 ×worker 的总账）、超时+重试+熔断做韧性、fan-out/in 配结构化并发、按类型隔离池子。调优靠 uvloop、合理的池/worker 大小，定位靠 py-spy 和压测。这些模式你在 Java/Go 里都见过，这章给了 Python 的落地写法。

---

> **最后** `99-interview-cards/`：把全课浓缩成面试高频题答案卡，每张链回对应章节做证据。
>
> **延伸**：剖析与压测工具见 `performance-tuning-roadmap/06a-python-profiling/`、`07-load-testing/`。
