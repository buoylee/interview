# 13 · 并发(桥接章)

> **为什么这章重要**:并发是 Python 最反 Java/Go 直觉的地方——有了 **GIL**,多线程**跑不满多核 CPU**。这章只解决一个问题:**面对一个任务,该选 threading、multiprocessing 还是 asyncio?** 把选型心智建立起来。每条路的实操、陷阱、生产用法不在这里展开,深度内容见仓库里的 [`../python-concurrency/`](../python-concurrency/)。

> **本章是桥接,不是全部**。需要动手写线程池、进程间通信、asyncio 事件循环、anyio、生产 worker/任务队列、并发调优——直接去 `python-concurrency/`,那是专题级 handson。

## 一、GIL:必须先懂的那道坎

**GIL(Global Interpreter Lock,全局解释器锁)** 是 CPython 的一把全局锁:**任一时刻只有一个线程能执行 Python 字节码**。后果:

- **CPU 密集型任务,多线程不会变快**——哪怕你开 8 个线程、机器有 8 核,同一时刻也只有一个线程在跑 Python 代码,其余在等锁。多线程在这里甚至可能因为切换开销更慢。
- **IO 密集型任务,多线程仍然有用**——因为线程**等待 IO(网络/磁盘)时会释放 GIL**,别的线程趁机执行。所以"一堆网络请求/文件读写"用多线程能显著提速。

记忆一句话:**GIL 让多线程能并发(concurrency,交替推进)IO,但不能并行(parallelism,同时计算)CPU。**

> 注意:GIL 是 **CPython 的实现细节**,不是 Python 语言规范(Jython 没有)。3.13 起有**实验性**的 free-threaded(可关 GIL)构建;**3.14(2025-10)经 PEP 779 转为官方支持**,不再是实验性,真去 GIL、线程真并行。代价:它仍是**可选构建**(默认发行版照旧带 GIL),单线程约有 5–10% 开销,C 扩展也需适配后才在该模式下安全。「Python 多线程跑不满多核」这条老结论正被改写(详见[第 16 章](16-objects-memory-gc-gil.md))。

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

### 3.13+:两条新并行路径

除了上面「线程 / 进程 / asyncio」老三样,3.13–3.14 又多出两条**进程内真并行**的路:

- **free-threaded 构建(PEP 703 → PEP 779)**:去掉 GIL,多线程真正并行跑 CPU。3.13 实验性,**3.14 转为官方支持的可选构建**(默认发行版仍带 GIL)。代价:单线程约 5–10% 变慢,C 扩展需适配。适合 CPU 密集且依赖纯 Python / 已适配扩展的场景。
- **子解释器(PEP 734,3.14 起标准库 `concurrent.interpreters`)**:一个进程内开多个互相隔离的解释器,**每个有自己的 GIL**,因此能并行跑 CPU 任务。比多进程轻(共享进程、启动快),但对象不共享,跨解释器要用它提供的 `Queue` / 可共享对象传数据。

```python
# 3.14+,子解释器(PEP 734),示意不实测
from concurrent import interpreters

interp = interpreters.create()
interp.exec("print('hello from subinterpreter')")
```

选型(接上面的决策树):CPU 密集 + 能用 free-threaded → 直接上线程;要隔离又嫌多进程重 → 子解释器;否则仍用 `multiprocessing`;IO 密集照旧 asyncio。以上都需 3.13/3.14,属**概念 / 面试向**,3.11 基线跑不了。

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

> **`contextvars`**:协程里没有"线程局部变量"(`threading.local` 不适用),要传递请求级上下文(如 request-id、trace-id)用 `contextvars.ContextVar`——它在 asyncio 任务间正确隔离/传播。
> ```python
> import contextvars
> req_id = contextvars.ContextVar("req_id", default="none")
> req_id.set("abc123"); req_id.get()   # 'abc123',各任务各自一份
> ```

## 四、async 里的异常:`await` 传播,脱钩任务自负盈亏

新 async 用户常以为"异步函数抓不到异常"。其实分两种写法,天差地别:

```python
async def foo():
    raise ValueError("boom")

async def bar():
    try:
        await foo()          # ① await:异常顺着 await 往上抛
    except ValueError as e:
        print("caught", e)   # ✅ 抓得到,和同步 try/except 一模一样
```

`await foo()` 语义上是"在**同一个 Task** 里把 `foo` 的栈接上来继续跑",异常 unwind 回来时你的 `try` 正好罩在那条栈上。**这就是"Python async 不存在抓不到异常的问题"的来源——但只对 `await` 这条「耦合」路径成立。** 一旦改成 fire-and-forget(丢出去自己跑),异常就脱钩了:

```python
async def bar():
    try:
        asyncio.create_task(foo())   # ❌ 不 await:异常归 Task 对象,不回这里
    except ValueError:
        print("caught")              # 永远进不来,try 早就执行完了
    await asyncio.sleep(1)
    # 程序退出时只剩一行日志:Task exception was never retrieved
```

`create_task` 起的是**独立 Task**(最接近 Go 的 `go func()`),异常被存进 Task 对象;没人 `await` / `.result()` 去取、又被 GC,异常就丢了。`asyncio.gather(..., return_exceptions=True)` 也是同类——异常被当成返回值塞进 list,不抛。

**最佳实践:用 `TaskGroup`(3.11+)把任务收回作用域**,异常就能像同步一样传播到一个统一边界:

```python
async def handle_order(order):
    async with asyncio.TaskGroup() as tg:        # 结构化并发
        tg.create_task(charge_payment(order))
        tg.create_task(reserve_stock(order))
    # 离开 with:任一子任务失败 → 自动取消其余 + 异常打包成 ExceptionGroup 抛出

try:
    await handle_order(order)
except* PaymentError as eg:      # except*(3.11+)按类型解包异常组
    ...
```

`TaskGroup` 取代裸 `create_task`/`gather`:**任一失败就 fail-fast 取消兄弟任务**,异常汇成 `ExceptionGroup` 抛到 `with` 外,`except*` 分类处理。真要 fire-and-forget(背景任务),两条铁律:**存住引用防 GC + 挂 `add_done_callback` 把异常打到日志/Sentry**,别让它变一行 "never retrieved"。(handson 见 [`../python-concurrency/04-asyncio-core`](../python-concurrency/04-asyncio-core) 与 [`05-asyncio-pitfalls`](../python-concurrency/05-asyncio-pitfalls))

### 三语言一张表:异步异常的产线最佳实践

这本质是同一道题——**异步任务跑在不在你 try/catch 罩的那条栈上**:耦合(同一逻辑栈的挂起点)就能传播,脱钩(独立执行单元)就归那个单元自己。三语言都在朝**结构化并发**收敛:把任务绑回作用域,让异常传播到统一边界。

| | Python | Java | Go |
|--|--------|------|-----|
| **异常自动回到调用方 try?** | `await` ✅ / `create_task` ❌ | `Thread.start`/`submit` ❌(存进 Future) | `go func` ❌(还会 crash 全进程) |
| **结构化并发**(收回作用域) | `TaskGroup` / anyio nursery | `StructuredTaskScope`(新)/ `CompletableFuture` 链(存量) | `errgroup` |
| **取消传播**(一个败其余停) | TaskGroup 自动取消 | scope 自动 / Reactor cancel | `context` + errgroup |
| **异常打包/解包** | `ExceptionGroup` + `except*` | 解 `CompletionException.getCause()` | `%w` + `errors.Is`/`As` |
| **fire-and-forget 安全网** | `add_done_callback` 上报 + 存引用 | 线程池 `UncaughtExceptionHandler` | safe-go `recover` 包装 |
| **边界统一处理** | 框架 exception_handler | `@ControllerAdvice` | HTTP/gRPC middleware |

一句话面试结论:**三语言产线都在朝结构化并发收敛——把并发任务绑回调用栈,让异常像同步代码一样传播到一个统一边界,中间任何脱钩点都必须接上可观测性。** Python(`TaskGroup`)和 Go(`errgroup`)已是默认这么写;Java 存量靠 Spring 全局 `@ControllerAdvice` + `CompletableFuture` 必接 `.handle`/`.exceptionally`,增量往虚拟线程 + 结构化并发(`StructuredTaskScope`)走,让并发异常回归 try/catch。论凶险:Go 最毒(脱钩 panic 直接炸全进程,见 [`../golang/error-handling/05-concurrent-errors`](../golang/error-handling/05-concurrent-errors/README.md)),Java 次之(静默吞进 Future 要主动取),Python 最温和(默认耦合,至少还印 "never retrieved")。

## 五、`concurrent.futures`:统一的高层接口

不想直接摆弄 thread/process,用 `concurrent.futures` 的执行器,换一个类名就能在"线程池/进程池"之间切:

```python
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

with ThreadPoolExecutor(max_workers=8) as ex:     # IO 密集
    results = list(ex.map(download, urls))

with ProcessPoolExecutor() as ex:                 # CPU 密集
    results = list(ex.map(heavy_compute, chunks))
```

接口一致(`submit`/`map`/`Future`),IO 用 Thread 版、CPU 用 Process 版。这是日常最常用的并发入口,类似 Java 的 `ExecutorService`。

## 六、深入:去 `python-concurrency/`

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
| CPU 并行 | 多线程真并行(无 GIL) | goroutine 真并行 | 线程**不行**(GIL),要用**多进程**;3.14 free-threaded 构建 / 子解释器可进程内真并行(≈ Java 线程 / Go goroutine) |
| IO 并发 | 线程池 / NIO / 虚拟线程 | goroutine + channel | threading / asyncio |
| 并发原语 | `synchronized`、`CompletableFuture`、线程池 | channel、`select`、`sync` | `threading.Lock`、`asyncio`、`concurrent.futures` |
| 异步模型 | 回调 / Future / 虚拟线程 | 同步风格(goroutine 屏蔽异步) | `async`/`await`(显式着色) |

最大震撼:**Java/Go 的多线程能吃满多核,默认构建的 Python 不能**(3.14 free-threaded 构建与子解释器正在改写这条结论,但默认发行版照旧带 GIL,见上表)。Go 的 goroutine 让你"用同步写法拿并行结果",Python 的 GIL 逼你按"CPU 用进程、IO 用线程/异步"分流。面试被问"为什么 Python 多线程跑不满 CPU",答 GIL。

## 章末面试卡

**Q1. GIL 是什么?有什么影响?**
GIL 是 CPython 的全局解释器锁,保证任一时刻只有一个线程执行 Python 字节码。影响:**CPU 密集任务多线程无法并行加速**(同时只有一个线程在算);但 IO 密集任务多线程仍有效(线程等 IO 时释放 GIL)。它是 CPython 实现细节;3.13 起有实验性 free-threaded 构建,**3.14 经 PEP 779 转为官方支持**(可选,默认仍带 GIL),另有子解释器(PEP 734,`concurrent.interpreters`)提供进程内真并行的第二条路。

**Q2. threading、multiprocessing、asyncio 怎么选?**
CPU 密集 → multiprocessing(绕开 GIL 吃满多核)或 C 扩展/numpy;IO 密集且用阻塞库、并发中等 → threading(或 ThreadPoolExecutor);海量 IO 连接或全异步栈 → asyncio。一句话:算得多用进程,等得多用线程/异步。

**Q3. 既然有 GIL,多线程还有用吗?**
有用,对 **IO 密集**任务:线程在等待网络/磁盘 IO 时会释放 GIL,其他线程趁机执行,从而并发推进多个 IO。GIL 只阻止 CPU 计算的并行,不阻止 IO 等待期间的并发。

**Q4. `async`/`await` 的本质是什么?为什么会"传染"?**
asyncio 是单线程事件循环上的协作式并发:`await` 处主动让出控制权给事件循环,等就绪再恢复;协程间只在 `await` 切换,不被抢占。"传染"指 `await` 只能用在 `async` 函数中,要 await 一个调用就得让它也是 async,于是 async 沿调用链蔓延,无法把同步代码库局部改异步。

**Q5. asyncio 里写了一个 CPU 密集或阻塞调用会怎样?**
会**卡住整个事件循环**——因为是单线程,没有 `await` 让出的耗时操作会让所有协程停摆。解决:把阻塞调用丢到线程池(`loop.run_in_executor` / `asyncio.to_thread`)或进程池,别在协程里直接做重计算/阻塞 IO。

**Q6. Python 怎么做 CPU 并行计算?**
用 `multiprocessing`/`ProcessPoolExecutor` 多进程(每进程独立解释器、各自 GIL,真并行),代价是进程开销和跨进程数据序列化;或用在 C 层释放 GIL 的库(numpy 向量化、C 扩展、Cython)。3.14 起另有两条进程内路径:free-threaded 构建(PEP 779,关 GIL 后多线程真并行)和子解释器(PEP 734,`concurrent.interpreters`,每解释器独立 GIL);均需 3.14、属可选 / 早期,当前默认仍首选多进程。

**Q7. 异步函数能 try/except 抓到异常吗?Python/Java/Go 有区别吗?**
看任务**耦合还是脱钩**于调用栈。Python 的 `await foo()` 是耦合的(同一 Task 的挂起点),异常顺着 await 抛回,`try/except` 抓得到,和同步一样——这是 Python async 的默认写法,所以"感觉不到问题"。但 `create_task` 脱钩成独立 Task,异常存进 Task 对象,不会回到 `try`(没人取还会变 "Task exception was never retrieved")。Java 的 `Thread.start`/`submit`、Go 的 `go func` 默认就是脱钩的:Java 异常存进 Future(要 `get()`/`.handle` 取),Go 的 goroutine panic 父协程 recover 不到、还会 **crash 整个进程**。结论:不是"Python 没这问题",而是 Python 默认写法耦合、Java/Go 默认写法脱钩;切到对方写法坑一样。

**Q8. 三语言异步异常处理的产线最佳实践?**
都朝**结构化并发**收敛——把并发任务绑回作用域,让异常传播到一个统一边界,中间脱钩点必接可观测性。Python:`TaskGroup`(任一失败取消其余 + `ExceptionGroup`/`except*`),fire-and-forget 用 `add_done_callback` 上报 + 存引用防 GC。Go:`errgroup.WithContext`(首错取消)+ 每个 goroutine 自带 `recover`。Java:存量靠 Spring `@ControllerAdvice` 全局兜底 + `CompletableFuture` 必接 `.handle`/`.exceptionally`,增量往虚拟线程 + `StructuredTaskScope` 走让异常回归 try/catch。
