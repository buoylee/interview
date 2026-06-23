# 02 · 三种并发模型 —— 选错了,后面怎么调都白搭

> `01` 算出了你需要多大并发 L。但「同样的 L」用不同模型扛,成本差几个数量级。这一章是定容管线的第一个**架构岔路口**:thread-per-request / event-loop / 多进程-worker,选错了,后面所有定容都建在沙子上。
>
> 前置:`01`。动手:`lab/experiments/e02-model-shootout.md`。

---

## 1. 同一个 L,三种扛法

`01` 告诉你:峰值需要 L=1000 个请求同时在途。现在的问题是——**这 1000 个「同时」,在机器里具体长什么样?** 有三种根本不同的答法,它们就是三种并发模型:

| 模型 | 1 个在途请求 = | 谁在调度 | 一句话 |
|---|---|---|---|
| **thread-per-request** | 1 个 OS 线程(阻塞式) | 操作系统内核 | 来一个请求开一个线程,线程里同步地等 I/O |
| **event-loop**(单线程协作) | 1 个协程/回调(在一个线程里) | 你的运行时(用户态) | 一个线程轮流推进上千个协程,谁等 I/O 就让出 |
| **多进程-worker** | 1 个请求占 1 个进程的一个槽 | OS 调度进程 + 进程内再用上面两种之一 | 开 N 个进程吃满多核,每进程内部再 thread 或 async |

这三者不是「谁更先进」,是**针对不同瓶颈的不同答案**。选型的全部依据,是你的负载是 **I/O 密集**还是 **CPU 密集**——这是这一章要你形成的第一直觉。

---

## 2. 底层①:一个在途请求到底占多少资源

「同样的 L=1000」为什么成本差几个数量级?因为三种模型里「一个在途请求」占的资源完全不同。这是选型的物理基础:

| 承载单位 | 内存/个 | 切换成本 | 谁切换 | L=1000 的代价 |
|---|---|---|---|---|
| **OS 线程**(Java 平台线程) | 默认栈 **~1MB**(可调) | ~1–10µs(陷内核、刷 TLB/缓存) | 内核 | ~1GB 栈内存 + 内核要调度 1000 个线程 |
| **goroutine** | 初始栈 **~2KB**(按需增长) | ~快(用户态,不陷内核) | Go runtime | ~2MB,runtime 自己调度 |
| **协程帧**(Python async / JS) | **~KB 级**(堆上一个对象) | 极快(就是个函数恢复) | event loop | ~MB 级,单线程轮转 |

**这张表就是 C10k 问题的答案。** 上世纪末,「单机扛 1 万并发连接」是难题,因为当时的做法是 thread-per-connection:1 万线程 = 10GB 栈 + 内核被 1 万个线程的调度压垮。解法不是买更大的机器,而是**换模型**——用 event-loop(epoll/kqueue + 单线程轮转)让「一个连接」从「一个线程」退化成「一个 fd + 一小块状态」。今天 Nginx、Redis、Node、Go 的网络服务,本质都在吃这个红利。

**对定容的直接影响**:

- 如果你的 L 很大(几千上万的并发连接,大多在等 I/O),thread-per-request 会先被**内存和上下文切换**压垮,而不是被 CPU 压垮。这时必须 event-loop 或 goroutine。
- 如果 L 不大(几十几百),thread-per-request 的简单性完全值得,别为了「高并发」过度设计。

> 关键转折:`01` 说「L=λW,降 W 能降 L」。这里补一刀:**L 一旦大到某个量级,承载单位的单位成本就成了主瓶颈,逼你换模型**——这是从「调参数」上升到「换架构」的临界点。

---

## 3. 底层②:Python 的 GIL —— 为什么它逼着你做选择

Python 选型绕不开 GIL(全局解释器锁)。一句话:**同一个 Python 进程里,任一时刻只有一个线程在执行 Python 字节码。** 但关键在「执行 Python 字节码」这几个字——GIL 在两种情况下会**释放**:

1. **阻塞 I/O 时**:线程进入 `read()`/`recv()` 这类系统调用前,会先释放 GIL。所以**多线程对 I/O 密集是有效的**——A 线程等网络时,B 线程能拿 GIL 干活。
2. **C 扩展主动释放时**:numpy 这类库在做密集计算时会释放 GIL,所以它们能真并行。

而**纯 Python 的 CPU 密集**(一个 for 循环算哈希)全程握着 GIL,多线程**完全无法并行**——开 8 个线程算,还是只有 1 个核在动,反而多了切换开销。

**这把 Python 的选型逼成一道明确的题:**

| 你的负载 | Python 正解 | 为什么 |
|---|---|---|
| I/O 密集(等 DB/HTTP/磁盘) | **asyncio**(event-loop)或多线程 | I/O 时释放 GIL,单线程协程就能扛上万并发 |
| CPU 密集(纯 Python 计算) | **多进程**(每进程独立 GIL)或换 C 扩展 | 唯一能吃满多核的路;线程没用 |
| 混合(典型 Web 服务) | **多进程 worker × 每进程 async** | 进程吃多核,进程内 async 扛 I/O 并发 |

最后一行就是 `gunicorn -k uvicorn.workers.UvicornWorker -w N` 的全部道理,`04` 会把 N 算出来。Java/Go 没有 GIL,所以没这道题——但你要懂它,因为**面试和定容里,「为什么 Python 要多进程」是必答题**(`python-concurrency/01` 有更细的 GIL 内幕,这里只取定容需要的)。

---

## 4. 底层③:Go 的 M:N —— 为什么 goroutine 里能放心写阻塞代码

event-loop 有个著名的坑:**单线程协作式,任何一个协程里写了阻塞调用,整个 loop 冻住**(Python `asyncio` 里直接 `time.sleep()` 或同步 DB 调用 = 全场停摆,`05/07` 细讲)。

Go 没这个坑,因为它的调度是 **M:N**:M 个 OS 线程(machine)上跑 N 个 goroutine,中间夹一个用户态调度器。当某个 goroutine 陷入阻塞 syscall 时,runtime 会**把那条 OS 线程和 goroutine 一起「停泊」(park the M),腾出调度器去别的 OS 线程上继续跑其余 goroutine**。所以:

- **Go 里你可以放心写「阻塞」代码**——`conn.Read()` 直接写,runtime 在底下把它变成非阻塞 + 调度,你看到的是同步代码、拿到的是异步性能。
- **Python asyncio 里你不能**——它是单线程 1:N,没有那个能「换条腿继续跑」的 M。阻塞调用必须手动 `run_in_executor`/`to_thread` 踢到线程池,否则冻 loop。

> 这解释了一个常见困惑:「都是协程,为什么 Go 的好写、Python 的处处是坑?」——因为 Go 的 runtime 多了一层 M:N 调度,替你扛了阻塞;Python 的 event loop 只有一条线程,阻塞了就没人接班。**模型的调度层级,决定了你写代码时要操多少心。**

---

## 5. 选型决策树(把上面收成一张图)

```
你的服务主要在干什么?
│
├─ 大量等 I/O(DB/HTTP/RPC/磁盘),CPU 占比低
│   └─ 高并发(L 上千)→ event-loop / goroutine        （内存省、切换便宜）
│       Python: asyncio   Go: 天生   Java: 虚拟线程(Loom)或 Netty
│   └─ 并发不高(L 几十)→ thread-per-request 也行,图简单
│
├─ CPU 密集(计算/序列化/压缩)
│   └─ 多核并行:多进程 / 多机                          （线程在 Python 无效;Go/Java 用线程吃核)
│       Python: multiprocessing   Go: GOMAXPROCS 自动   Java: 线程池=核数
│
└─ 混合(绝大多数 Web 服务:既等 DB 又有些计算)
    └─ 多进程 worker × 每进程内 event-loop/线程         （进程吃多核,进程内扛 I/O 并发)
        这是 gunicorn+uvicorn、Go 单进程多 goroutine、Java 线程池的共同形态
```

**三语速记**:

- **Java**:传统 thread-per-request(线程池);**虚拟线程(Loom,JDK 21+)** 让你「写阻塞代码、拿 event-loop 性能」——本质是 JVM 自己实现了类似 Go 的 M:N,是 Java 版的 goroutine。
- **Go**:不用选,goroutine + M:N runtime 一把梭;CPU 密集靠 `GOMAXPROCS`=核数自动并行。
- **Python**:被 GIL 逼着走「多进程 × async」组合拳,是三语里选型最不自由、最需要想清楚的。

---

## 6. 一句话收口

并发模型不是「谁先进」,是「针对 I/O 密集还是 CPU 密集的不同答案」:I/O 密集要 event-loop/goroutine(承载单位便宜,扛得起大 L),CPU 密集要多进程/多核(绕开 GIL、吃满核),混合负载是「多进程 × 进程内 async」。底层差异——线程 MB vs 协程 KB(决定大 L 的成败)、GIL 释放点(逼 Python 做选择)、M:N 调度(决定阻塞代码能不能随便写)——是你在面试里把「会用」讲成「懂为什么选」的关键。**这个选择定了,`04` 才能开始算具体配多少。**

> **动手:跑这个实验**
> `lab/experiments/e02-model-shootout.md`:对同一个 `/slow`(模拟 I/O)端点,分别用 `MODEL=async` 和模拟 thread 阻塞,打同样的负载,对比在途数 L 和 P99。你会看到 event-loop 用一个线程扛住了 thread 模型要几百个线程才扛得住的并发。
> ```bash
> # 先感受单进程 async 扛并发的能力:
> cd concurrency-capacity/lab/service
> POOL_SIZE=200 uvicorn app:app --port 8000 &
> python drive.py --url 'http://127.0.0.1:8000/slow?ms=50' --steps 100,500,1000 --seconds 4
> # 一个 uvicorn 进程、一个事件循环,扛住上千并发 I/O——这就是 event-loop 的红利
> ```

> **指进**:GIL 字节码级内幕 → [`python-concurrency/01-foundations-gil`](../../python-concurrency/01-foundations-gil/);goroutine 调度 → [`golang/concurrency`](../../golang/concurrency/);JUC 线程池 → [`java/concurrent`](../../java/concurrent/);OS 层进程/线程/协程 → [`performance-tuning-roadmap/00-os-fundamentals/05`](../../performance-tuning-roadmap/00-os-fundamentals/05-process-thread-coroutine.md)。
