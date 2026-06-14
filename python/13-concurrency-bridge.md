# 13 · 并发(桥接章)

> **为什么这章重要**:并发是 Python 最反 Java/Go 直觉的地方——有了 **GIL**,多线程**跑不满多核 CPU**。这章只解决一个问题:**面对一个任务,该选 threading、multiprocessing 还是 asyncio?** 把选型心智建立起来。每条路的实操、陷阱、生产用法不在这里展开,深度内容见仓库里的 [`../python-concurrency/`](../python-concurrency/)。

> **本章是桥接,不是全部**。需要动手写线程池、进程间通信、asyncio 事件循环、anyio、生产 worker/任务队列、并发调优——直接去 `python-concurrency/`,那是专题级 handson。

## 一、GIL:必须先懂的那道坎

**GIL(Global Interpreter Lock,全局解释器锁)** 是 CPython 的一把全局锁:**任一时刻只有一个线程能执行 Python 字节码**。后果:

- **CPU 密集型任务,多线程不会变快**——哪怕你开 8 个线程、机器有 8 核,同一时刻也只有一个线程在跑 Python 代码,其余在等锁。多线程在这里甚至可能因为切换开销更慢。
- **IO 密集型任务,多线程仍然有用**——因为线程**等待 IO(网络/磁盘)时会释放 GIL**,别的线程趁机执行。所以"一堆网络请求/文件读写"用多线程能显著提速。

记忆一句话:**GIL 让多线程能并发(concurrency,交替推进)IO,但不能并行(parallelism,同时计算)CPU。**

> 注意:GIL 是 **CPython 的实现细节**,不是 Python 语言规范(Jython 没有)。3.13 起有实验性的 **free-threaded(可关 GIL)** 构建,未来可能改变这一格局,但短期内生产仍以"有 GIL"为前提(见[第 15 章](15-cpython-internals-performance.md))。

## 二、三条路与选型决策

| 方案 | 并行能力 | 适合 | 代价 |
|------|----------|------|------|
| **threading** | 并发,不并行(受 GIL) | **IO 密集**:多请求、读写文件、调用阻塞库 | 共享内存要加锁,有竞态风险 |
| **multiprocessing** | 真并行(每进程独立解释器,各自 GIL) | **CPU 密集**:计算、压缩、图像处理 | 进程开销大,数据要序列化跨进程传 |
| **asyncio** | 并发,不并行(单线程事件循环) | **海量 IO 并发**:成千上万连接、异步框架 | 需全链路 async,会"函数着色传染" |

### 决策树

```
任务是 CPU 密集(算得多)还是 IO 密集(等得多)?
│
├── CPU 密集 ──────────────► multiprocessing(绕开 GIL,吃满多核)
│                            或 C 扩展 / numpy 向量化(在 C 层释放 GIL)
│
└── IO 密集 ── 并发量多大?
              │
              ├── 中等、且用的是阻塞库(requests、普通 DB 驱动)
              │        ► threading(或 concurrent.futures.ThreadPoolExecutor)
              │
              └── 海量连接、或本就用异步框架/异步库(httpx、asyncpg)
                       ► asyncio
```

一句话版:**算得多用进程,等得多用线程或 asyncio;并发量极大且能全异步,就 asyncio。**

## 三、`async`/`await` 一句话心智

`asyncio` 是**单线程**靠**事件循环**调度的协作式并发:

```python
import asyncio

async def fetch(name, delay):
    await asyncio.sleep(delay)        # await 处“让出”控制权,事件循环去跑别的
    return f"{name} done"

async def main():
    # 三个一起跑,总耗时≈最长的 0.3s,而不是 0.1+0.2+0.3
    results = await asyncio.gather(
        fetch("a", 0.1), fetch("b", 0.2), fetch("c", 0.3)
    )
    print(results)                    # ['a done', 'b done', 'c done']

asyncio.run(main())
```

- `async def` 定义**协程**;`await x` 表示"这里可能要等,先把控制权交还事件循环,等好了再回来"。
- 没有线程切换、没有抢占——只在 `await` 处主动让出。所以协程之间不会在语句中间被打断,竞态比多线程少;但**一个协程里写了阻塞调用(没 await 的耗时操作),会卡住整个事件循环**。
- **着色(coloring)传染**:`await` 只能在 `async` 函数里用;要 await 一个函数,它得是 async;于是 async 会沿调用链向上蔓延。这是 asyncio 最大的工程成本——不能把一个同步代码库"局部改异步"。

## 四、`concurrent.futures`:统一的高层接口

不想直接摆弄 thread/process,用 `concurrent.futures` 的执行器,换一个类名就能在"线程池/进程池"之间切:

```python
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

with ThreadPoolExecutor(max_workers=8) as ex:     # IO 密集
    results = list(ex.map(download, urls))

with ProcessPoolExecutor() as ex:                 # CPU 密集
    results = list(ex.map(heavy_compute, chunks))
```

接口一致(`submit`/`map`/`Future`),IO 用 Thread 版、CPU 用 Process 版。这是日常最常用的并发入口,类似 Java 的 `ExecutorService`。

## 五、深入:去 `python-concurrency/`

本章到此为止只够"选对方向"。每条路的细节在专题目录,按需深入:

| 主题 | 去处 |
|------|------|
| 执行模型总览 | [`../python-concurrency/00-execution-model`](../python-concurrency/00-execution-model) |
| GIL 原理 | [`../python-concurrency/01-foundations-gil`](../python-concurrency/01-foundations-gil) |
| threading 实操 | [`../python-concurrency/02-threading`](../python-concurrency/02-threading) |
| multiprocessing | [`../python-concurrency/03-multiprocessing`](../python-concurrency/03-multiprocessing) |
| asyncio 核心 | [`../python-concurrency/04-asyncio-core`](../python-concurrency/04-asyncio-core) |
| asyncio 陷阱 | [`../python-concurrency/05-asyncio-pitfalls`](../python-concurrency/05-asyncio-pitfalls) |
| anyio | [`../python-concurrency/06-anyio`](../python-concurrency/06-anyio) |
| 生产 web worker | [`../python-concurrency/07-prod-web-workers`](../python-concurrency/07-prod-web-workers) |
| 任务队列 | [`../python-concurrency/08-prod-task-queues`](../python-concurrency/08-prod-task-queues) |
| 模式与调优 | [`../python-concurrency/09-patterns-tuning`](../python-concurrency/09-patterns-tuning) |
| 并发面试卡 | [`../python-concurrency/99-interview-cards`](../python-concurrency/99-interview-cards) |

## Java/Go 对照框

| | Java | Go | Python(CPython) |
|--|------|-----|------------------|
| CPU 并行 | 多线程真并行(无 GIL) | goroutine 真并行 | 线程**不行**(GIL),要用**多进程** |
| IO 并发 | 线程池 / NIO / 虚拟线程 | goroutine + channel | threading / asyncio |
| 并发原语 | `synchronized`、`CompletableFuture`、线程池 | channel、`select`、`sync` | `threading.Lock`、`asyncio`、`concurrent.futures` |
| 异步模型 | 回调 / Future / 虚拟线程 | 同步风格(goroutine 屏蔽异步) | `async`/`await`(显式着色) |

最大震撼:**Java/Go 的多线程能吃满多核,Python 不能**。Go 的 goroutine 让你"用同步写法拿并行结果",Python 的 GIL 逼你按"CPU 用进程、IO 用线程/异步"分流。面试被问"为什么 Python 多线程跑不满 CPU",答 GIL。

## 章末面试卡

**Q1. GIL 是什么?有什么影响?**
GIL 是 CPython 的全局解释器锁,保证任一时刻只有一个线程执行 Python 字节码。影响:**CPU 密集任务多线程无法并行加速**(同时只有一个线程在算);但 IO 密集任务多线程仍有效(线程等 IO 时释放 GIL)。它是 CPython 实现细节,3.13 起有实验性 free-threaded 构建。

**Q2. threading、multiprocessing、asyncio 怎么选?**
CPU 密集 → multiprocessing(绕开 GIL 吃满多核)或 C 扩展/numpy;IO 密集且用阻塞库、并发中等 → threading(或 ThreadPoolExecutor);海量 IO 连接或全异步栈 → asyncio。一句话:算得多用进程,等得多用线程/异步。

**Q3. 既然有 GIL,多线程还有用吗?**
有用,对 **IO 密集**任务:线程在等待网络/磁盘 IO 时会释放 GIL,其他线程趁机执行,从而并发推进多个 IO。GIL 只阻止 CPU 计算的并行,不阻止 IO 等待期间的并发。

**Q4. `async`/`await` 的本质是什么?为什么会"传染"?**
asyncio 是单线程事件循环上的协作式并发:`await` 处主动让出控制权给事件循环,等就绪再恢复;协程间只在 `await` 切换,不被抢占。"传染"指 `await` 只能用在 `async` 函数中,要 await 一个调用就得让它也是 async,于是 async 沿调用链蔓延,无法把同步代码库局部改异步。

**Q5. asyncio 里写了一个 CPU 密集或阻塞调用会怎样?**
会**卡住整个事件循环**——因为是单线程,没有 `await` 让出的耗时操作会让所有协程停摆。解决:把阻塞调用丢到线程池(`loop.run_in_executor` / `asyncio.to_thread`)或进程池,别在协程里直接做重计算/阻塞 IO。

**Q6. Python 怎么做 CPU 并行计算?**
用 `multiprocessing`/`ProcessPoolExecutor` 多进程(每进程独立解释器、各自 GIL,真并行),代价是进程开销和跨进程数据序列化;或用在 C 层释放 GIL 的库(numpy 向量化、C 扩展、Cython)。
