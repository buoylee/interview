# 04 · asyncio 核心 —— 单线程事件循环 + 协程

> 换一套完全不同的思路：不靠多线程/多进程，而靠**一个线程 + 一个事件循环**，在海量 I/O 等待之间快速切换。这是 Python 扛上万并发连接的首选，也是 FastAPI 的根基。
>
> **给 Go 开发的预先警告**：asyncio 写出来很像 goroutine，但**本质不同**（单线程协作式 vs 多线程抢占式）。这章会把这个差异钉死，别用 goroutine 的直觉去想 asyncio。
>
> 前置：第 01 章（GIL）。

---

## 1. 核心问题

1. 单线程怎么可能「并发」处理上万连接？事件循环到底在干嘛？
2. `async` / `await` / coroutine / Task 分别是什么？`await` 的本质是什么？
3. asyncio 和 Go 的 goroutine 到底差在哪？为什么说它「更弱」？
4. 怎么并发跑一堆协程、怎么取消、怎么超时？channel 对应什么？

---

## 2. 直觉理解

### 2.1 一个厨师的故事（事件循环）

回到第 01 章那个比喻：一个厨师（单线程）照看 3 口锅。他不会站在第 1 口锅前干等水烧开——他**把水烧上（发起 I/O），转身去切第 2 口锅的菜，再去搅第 3 口锅**。哪口锅响了（I/O 就绪）就回去处理哪口。

这就是**事件循环（event loop）**：一个线程，手里一堆「在等 I/O 的任务」，谁的 I/O 好了就去推进谁。CPU 几乎从不空转在等待上。

- **关键①：只有一个厨师（单线程）。** 所以 GIL 在 asyncio 里**根本不是问题**——压根只有一个线程在跑。
- **关键②：厨师只在「把活交出去等待」时才切换。** 他切菜切到一半不会突然跑去别的锅——**切换只发生在他主动停下等待的点**。这就是「协作式」。

### 2.2 await 的本质：主动让出

```python
async def fetch(url):
    r = await client.get(url)    # ← 这里：发起网络请求，然后"我要等了，事件循环你先忙别的"
    return r.json()
```

**`await` 就是那个「把活交出去、让出执行权」的标记。** 协程跑到 `await 某个IO()` 时说：「我要等 I/O 了，事件循环你去伺候别的协程吧，等我 I/O 好了再叫我回来。」

> **核心心智**：在一个 `async` 函数里，**不是 `await` 的每一行代码，都在独占整个事件循环**（厨师在专心做这一件事，没法切走）。所以一旦某行代码很慢又不是 `await`，整个循环就卡住——这是第 05 章的头号陷阱。

### 2.3 ⚠️ asyncio ≠ goroutine（Go 开发必看）

写法像，本质完全不同：

| | Go goroutine | Python asyncio |
|---|---|---|
| 线程数 | **多个** OS 线程（M:N 调度） | **单个**线程（一个事件循环） |
| 调度 | **抢占式**（runtime 强制切换，你无感） | **协作式**（只在你写的 `await` 处切） |
| 并行 | **真并行**（吃多核） | 并发不并行（一个核） |
| 一个任务死算 | 别的 goroutine 照跑 | **整个循环卡死** |
| 阻塞调用 | runtime 透明处理，你写同步代码就行 | 必须显式 `await`，且必须用 async 版本的库 |
| 函数染色 | 无（goroutine 透明） | **有**（async 会传染，见第 05 章） |

> 一句话：goroutine 更像「Go 帮你管理的轻量线程，能吃多核」；asyncio 更像 **Node.js 的事件循环**——单线程、协作式、靠不阻塞来撑高并发。**别指望 asyncio 利用多核**（要多核还得叠多进程/多 worker，见第 07 章）。

那 asyncio 凭什么值得用？因为对**海量 I/O 等待**场景它开销最低：单线程无线程切换、无锁、一个协程才几百字节~KB（对比线程栈 MB 级），轻松上万并发连接。

---

## 3. 原理深入

### 3.1 最小骨架

```python
# 需要: pip install httpx
import asyncio, httpx

async def fetch(client, url):          # async def 定义"协程函数"
    r = await client.get(url)          # await 让出，等响应
    return r.status_code

async def main():
    async with httpx.AsyncClient() as client:
        codes = await asyncio.gather(  # 并发跑一组协程，等全部完成
            fetch(client, "https://example.com"),
            fetch(client, "https://httpbin.org/get"),
        )
    print(codes)

asyncio.run(main())                    # 启动事件循环，跑到 main 结束（程序唯一入口）
```

几个概念分清：

- **协程函数**：`async def` 定义的函数。
- **协程对象**：调用协程函数得到的东西。注意：`fetch(...)` **只是创建协程对象，并不执行**——必须 `await` 它或交给事件循环才会跑。（Go 里 `go f()` 直接就跑了，这里不会，常见坑。）
- **`asyncio.run(coro)`**：创建事件循环、跑这个协程直到结束、关闭循环。一个程序通常只调一次。

### 3.2 并发的三种姿势：await / create_task / gather

```python
import asyncio

# ① 顺序 await —— 串行，没有并发！（新手常误以为 async 就自动并发）
async def serial():
    a = await step1()      # 等 step1 完全做完
    b = await step2()      # 才开始 step2
    # 总耗时 = step1 + step2

# ② create_task —— 把协程丢进事件循环后台跑（最接近 Go 的 go func()）
async def concurrent_tasks():
    t1 = asyncio.create_task(step1())   # 立刻开始在后台推进
    t2 = asyncio.create_task(step2())
    a = await t1                        # 这时再去取结果
    b = await t2
    # 总耗时 ≈ max(step1, step2)

# ③ gather —— 一把并发跑一组并收集结果（最常用，≈ Go WaitGroup / Java allOf）
async def concurrent_gather():
    a, b = await asyncio.gather(step1(), step2())
    # 总耗时 ≈ max(step1, step2)；任一抛异常默认会传播出来
```

> **重点提醒**：写了 `async`/`await` **不等于**自动并发。`await a(); await b()` 是串行。要并发必须用 `create_task` 或 `gather` 把它们同时"挂"到循环上。这是从同步思维转过来最容易错的点。

### 3.3 结构化并发：TaskGroup（3.11+，推荐）

裸 `create_task` 有个问题：任务的生命周期散落各处，一个失败了其他的容易变成「孤儿任务」。`TaskGroup` 把一组任务的生命周期绑在一个作用域里——**任一任务失败，同组其他任务自动取消**，作用域退出时保证全部结束：

```python
import asyncio

async def main():
    async with asyncio.TaskGroup() as tg:    # Python 3.11+
        tg.create_task(fetch("a"))
        tg.create_task(fetch("b"))
        tg.create_task(fetch("c"))
    # 退出 with 时：等全部完成；若有异常，其余自动取消并汇总抛出
```

> 这就是「结构化并发」思想（第 06 章 anyio 会深入）——并发任务有清晰的作用域边界，不会泄漏。新代码优先用 `TaskGroup` 而非裸 `gather`/`create_task`。

### 3.4 协程间的同步与通信

asyncio 有自己的一套锁/队列，**注意它们是「协程级」的，不是线程锁**（单线程内用来协调协程，不能跨线程）：

```python
import asyncio

lock = asyncio.Lock()           # 协程级锁
sem = asyncio.Semaphore(10)     # 限制同时进行的协程数（最常用于限并发，比如限制并发请求数）

async def limited_fetch(url):
    async with sem:             # 最多 10 个协程同时在这段里
        return await client.get(url)

# asyncio.Queue —— 协程间队列，相当于 Go 的 channel
q = asyncio.Queue(maxsize=100)
async def producer():
    await q.put(item)           # 满了会"让出并等待"，不阻塞线程
async def consumer():
    item = await q.get()        # 空了会让出并等待
```

| asyncio | Go | 说明 |
|---|---|---|
| `create_task(coro)` | `go func()` | 后台并发跑 |
| `asyncio.Queue` | `channel` | 协程间传数据 |
| `asyncio.gather` / `TaskGroup` | `sync.WaitGroup` | 等一组任务 |
| `asyncio.Semaphore` | 带缓冲 channel 做信号量 | 限并发 |
| `task.cancel()` / `asyncio.timeout()` | `context.Context` 取消/超时 | 取消传播 |

### 3.5 取消与超时（对应 Go 的 context）

```python
import asyncio

# 超时：超过 5 秒自动取消里面的协程并抛 TimeoutError（3.11+ 的写法）
async def main():
    try:
        async with asyncio.timeout(5):
            await slow_operation()
    except TimeoutError:
        print("超时了")

# 手动取消一个 task
task = asyncio.create_task(work())
task.cancel()                      # 在 work 的下一个 await 点抛 CancelledError
```

> 取消是**协作式**的：`task.cancel()` 不会立刻杀死协程，而是在它下一次 `await` 时抛 `CancelledError`。如果协程在死算（没有 await 点），取消也不会生效——又一次印证「协作式」的本质。

### 3.6 事件循环到底怎么实现的（点到为止）

事件循环底层用操作系统的 **I/O 多路复用**（Linux 的 `epoll`、macOS 的 `kqueue`，通过 `selectors` 模块）：把成百上千个 socket 注册进去，一次系统调用就能拿到「哪些 socket 现在可读/可写」，然后去推进对应的协程。这正是单线程能管上万连接的底层魔法（C10k 问题的解法）。

> 想看清楚「epoll 在内核里到底怎么回事 + 协程怎么被事件循环恢复 + 为什么协程切换比线程快百倍」的完整机制，见 [00-execution-model](../00-execution-model/README.md) 的 A.6 / B.3 / B.4。

> 对标：这和 Java 的 NIO `Selector`、Netty 的 EventLoop 是同一套思想。你要是用过 Netty，asyncio 的事件循环对你不陌生。

---

### 3.7 coroutine / Task / event loop 和 Java 的类比边界

可以用 Java 类比，但别把 `Task` 当成 `Thread`：

```text
Java:
  Runnable / Callable  -> Thread / ExecutorService -> OS thread

asyncio:
  coroutine            -> Task + event loop         -> OS thread
```

- `coroutine`：可暂停/可恢复的函数执行状态，粗略像一个「能 `await` 的 Runnable/Callable」。
- `Task`：把 coroutine 注册到 event loop 的调度包装，更像 `Future` + 调度句柄。
- `event loop`：真正运行在某个 OS 线程里的调度循环，负责恢复 Task、等待 I/O/timer。

事件循环恢复协程的简化过程：

```text
Task 恢复 coroutine
  -> coroutine 一直跑到下一个 await / return / exception
  -> 遇到 await 时挂起，等待某个 Future/I/O/timer
  -> Future 完成后 Task 回到 ready queue
  -> event loop 下次再恢复它
```

所以 `asyncio.Task` 默认不是系统线程，也不会被 OS 单独调度；多个 Task 通常在同一个 event loop 线程里协作式切换。完整复习见：[线程 / I/O / event loop 面试卡](../99-interview-cards/q-thread-io-event-loop.md)。

## 4. 日常开发应用

- **什么时候用 asyncio**：I/O 密集 + 高并发（大量网络请求、高并发 Web 服务、爬虫、代理、WebSocket 长连接）。
- **铁律：全链路 async**。要用 asyncio，I/O 就必须用 async 版本的库（`httpx`/`aiohttp`、`asyncpg`、`aiomysql`、`redis.asyncio`、`aiofiles`）。混入一个同步阻塞调用就会卡死整个循环（第 05 章详解）。
- **限并发用 `Semaphore`**：别一次性 `gather` 一万个请求把对端打挂，用 `asyncio.Semaphore(N)` 控制同时在飞的数量。
- **新代码用 `TaskGroup` + `asyncio.timeout`**：结构化、好维护。
- **CPU 密集别放进协程**：会卡死循环，丢给进程池（`run_in_executor`，第 05 章）。

```python
# 典型：受控并发抓取一批 URL
import asyncio, httpx

async def fetch(client, sem, url):
    async with sem:                          # 限制并发数
        r = await client.get(url, timeout=10)
        return r.status_code

async def main(urls):
    sem = asyncio.Semaphore(20)
    async with httpx.AsyncClient() as client:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(fetch(client, sem, u)) for u in urls]
    return [t.result() for t in tasks]

asyncio.run(main(urls))
```

---

## 5. 生产 & 调优实战

- **asyncio 不吃多核**（单线程）。生产里要利用多核 = **多开 worker 进程**，每个 worker 内跑一个事件循环：`uvicorn app:asgi --workers 4`（第 07 章）。即「多进程绕 GIL + 每进程一个事件循环扛高并发」。
- **换 uvloop 提速 2–4 倍**：uvloop 是基于 libuv 的高性能事件循环，几乎零成本替换默认循环（`uvicorn --loop uvloop` 自动启用）。
- **每个协程要轻**：协程多但都很轻才划算；别在协程里放重计算或同步阻塞。
- **监控事件循环是否被阻塞**：开 debug 模式、加看门狗、用 py-spy dump 看卡在哪——详见 `performance-tuning-roadmap/06b-python-debugging/02-asyncio-debugging.md`（第 05 章也会引用）。

---

## 6. 面试高频考点

**Q1：单线程的 asyncio 怎么做到高并发？**
靠事件循环 + 不阻塞：发起 I/O 后立即 `await` 让出，去推进别的协程，I/O 就绪再回来。底层用 epoll/kqueue 多路复用一次性监听上万 socket。CPU 几乎不空转在等待上。

**Q2：asyncio 和 goroutine 的区别？**
goroutine 是多 OS 线程上抢占式调度、能真并行；asyncio 是单线程协作式、不并行。goroutine 阻塞一个不影响别的，asyncio 一个阻塞操作冻结整个循环。asyncio 还有函数染色问题，goroutine 没有。

**Q3：`await` 是什么意思？**
标记一个「让出执行权、等待某个异步操作完成」的点。不是 await 的代码都在独占事件循环。

**Q4：写了 async 就并发了吗？**
不是。`await a(); await b()` 是串行。要并发得用 `create_task` 或 `gather`/`TaskGroup` 把协程同时挂到循环上。

**Q5：协程里能放 CPU 密集计算或同步阻塞吗？**
不能，会冻结整个事件循环、拖垮所有并发连接。CPU 密集丢进程池、同步阻塞用 async 库或 `run_in_executor` 桥接（第 05 章）。

**Q6：asyncio 能利用多核吗？**
不能，单线程。要多核得叠多进程/多 worker（每个 worker 一个事件循环）。

**Q7：怎么实现超时和取消？**
`asyncio.timeout(秒)` 上下文管理器做超时；`task.cancel()` 取消。取消是协作式的，在下一个 await 点抛 `CancelledError`，死算的协程取消不掉。

---

## 7. 一句话总结

asyncio = **单线程 + 事件循环 + 协程协作式调度**，靠「发起 I/O 就让出」在海量等待间高速切换，是 Python 扛高并发 I/O 的首选，GIL 对它无影响。它写着像 goroutine，但**单线程、协作式、不并行、有函数染色**——别用 Go 直觉硬套。用它的铁律是**全链路 async、绝不在协程里阻塞**，这正是下一章的主题。

---

> **下一章** `05-asyncio-pitfalls/`：阻塞事件循环、同步混进 async、`run_in_executor` 桥接、函数染色——asyncio 翻车的全部姿势和救法。
>
> **延伸**：排查手段见 `performance-tuning-roadmap/06b-python-debugging/02-asyncio-debugging.md`。
