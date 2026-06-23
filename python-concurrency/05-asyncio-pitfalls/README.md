# 05 · asyncio 陷阱 —— 翻车的全部姿势和救法

> asyncio 的坑高度集中、且都源于同一句话：**单线程协作式，一旦某行代码不让出，整个循环就冻结。** 本章把翻车姿势讲全：阻塞事件循环、忘记 await、同步库混入、函数染色，以及对应的救法（async 库 / `run_in_executor`）。
>
> 前置：第 04 章。深度排查手段（debug 模式、看门狗、py-spy）见 `performance-tuning-roadmap/06b-python-debugging/02-asyncio-debugging.md`，本章不重复，只讲「为什么」和「怎么写对」。

---

## 1. 核心问题

1. 为什么一个 `time.sleep(1)` 能让整个高并发服务卡住？
2. 哪些代码会「阻塞事件循环」？怎么识别？
3. 没有 async 版本的库（或 CPU 密集活）怎么办？
4. 什么是「函数染色」？为什么 Go 没这个问题、Python 有？

---

## 2. 直觉理解

回到第 04 章的「一个厨师」比喻。事件循环只有一个厨师。如果他**站在一口锅前发呆 1 秒**（`time.sleep(1)`），这 1 秒里**其他所有锅都没人管**——哪怕别的锅已经响了。

这就是 asyncio 最反直觉的地方：在多线程世界里，一个线程卡住，别的线程照跑；但在 asyncio 里，**单线程卡住 = 全部并发连接一起卡住**。一个本该处理上千并发的服务，可能被一行同步代码拖成串行。

> 第 04 章那句铁律再强调一遍：**async 函数里不是 `await` 的每一行，都在独占事件循环。** 任何耗时 >1ms 又不是 await 的操作，都值得警惕。

---

## 3. 原理深入

### 3.1 头号杀手：在协程里调用同步阻塞

```python
import time, requests

async def handler():
    time.sleep(1)              # ❌ 同步 sleep，冻结整个循环 1 秒
    requests.get(url)          # ❌ 同步 HTTP，冻结直到返回
    data = open("f").read()    # ❌ 同步文件 I/O，冻结
    rows = cursor.execute(sql) # ❌ 同步 DB 驱动（psycopg2/pymysql），冻结
    result = heavy_compute()   # ❌ CPU 密集死算，冻结（没有 await 点，连取消都取消不了）
```

这些在开发时（低并发）往往看不出问题，**一上生产、并发一高就集体雪崩**——因为本该并发的请求被串行化了。

### 3.2 救法一：换成 async 版本的库

asyncio 要求**全链路 async**。每个同步阻塞库都有 async 替代：

| 同步库（会冻结循环） | async 替代 |
|---|---|
| `time.sleep` | `asyncio.sleep` |
| `requests` | `httpx` / `aiohttp` |
| `open()` 文件 I/O | `aiofiles` |
| `psycopg2`（PostgreSQL） | `asyncpg` |
| `PyMySQL`（MySQL） | `aiomysql` |
| `redis-py`（同步） | `redis.asyncio` |
| `subprocess.run` | `asyncio.create_subprocess_exec` |
| `smtplib`（邮件） | `aiosmtplib` |

```python
# 需要: pip install httpx aiofiles
import asyncio, httpx, aiofiles

async def handler():
    await asyncio.sleep(1)                          # ✅ 让出而非冻结
    async with httpx.AsyncClient() as client:
        await client.get(url)                       # ✅ 异步 HTTP
    async with aiofiles.open("f") as f:
        data = await f.read()                       # ✅ 异步文件 I/O
```

### 3.3 救法二：run_in_executor 桥接（同步库没 async 版 / CPU 密集）

有些库就是没有 async 版本，或是 CPU 密集活。这时把它**丢到线程池/进程池**里跑，用 `run_in_executor` 包成可 await 的形式，就不会卡住循环：

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

def cpu_heavy(data):           # CPU 密集
    return expensive(data)

def sync_lib_call(arg):        # 只有同步版本的库
    return legacy_sdk.do(arg)

async def handler(data, arg):
    loop = asyncio.get_running_loop()

    # 同步阻塞 I/O → 丢默认线程池（传 None）
    r1 = await loop.run_in_executor(None, sync_lib_call, arg)

    # CPU 密集 → 丢进程池（线程池对 CPU 密集没用，GIL！）
    with ProcessPoolExecutor() as pool:
        r2 = await loop.run_in_executor(pool, cpu_heavy, data)

    return r1, r2
```

> 心法：**I/O 阻塞 → 线程池（I/O 时放 GIL）；CPU 密集 → 进程池（绕 GIL）。** 这把第 02、03 章的武器接回了 asyncio。

### 3.4 坑：忘记 await

```python
async def get_user(uid): ...

async def handler(uid):
    user = get_user(uid)       # ❌ 忘了 await！user 是个协程对象，不是结果
    print(user.name)           # AttributeError: 'coroutine' object has no attribute 'name'
    user = await get_user(uid) # ✅
```

忘 await 的协程**根本没执行**。开 debug 模式（`asyncio.run(main(), debug=True)` 或 `PYTHONASYNCIODEBUG=1`）时，未 await 的协程被回收会警告 `coroutine 'xxx' was never awaited`。**开发期务必开 debug 模式。**

### 3.5 函数染色（function color，Go 开发会很不适应）

规则：`async` 函数只能被 `await`，而 `await` 只能写在 `async` 函数里。后果：**一个底层函数改成 async，所有调用它的上层都得跟着变 async**，async 沿调用链一路传染。

```python
async def db_query(): ...          # 把它改成 async
async def get_user():              # → 调用方被迫也变 async
    return await db_query()
async def handler():               # → 再上层也被迫 async
    return await get_user()
# ……一直传染到最顶层
```

> 对比 Go：goroutine 是透明的，你写普通同步代码，runtime 在底层帮你切换，**不存在染色**。Python 的 async/await 是显式的，所以会染色——这是 asyncio 在工程上最被诟病的点。
>
> **实务取舍**：要么一条链路 **async 到底**，要么干脆**整条用同步 + 线程池**。最忌讳在两个世界之间反复横跳（一会 async 一会同步，到处 `run_in_executor` 或 `asyncio.run`），既复杂又容易出错。

### 3.6 坑：阻塞调用没超时

异步代码里若 `await` 一个永不返回的 I/O（对端挂了、网络黑洞），这个协程会永远挂着。**所有网络 await 都要带 timeout**：

```python
async with asyncio.timeout(10):      # 3.11+
    await client.get(url)
# 或库自带的：await client.get(url, timeout=10)
```

### 3.7 坑：fire-and-forget 任务吞掉异常

`await foo()` 的异常会顺着 await 抛回来，`try/except` 抓得到（和同步一样）。但 `create_task` 把任务**脱钩**丢到后台跑——异常归 Task 对象，**不会回到你的 `try`**：

```python
async def worker():
    raise ValueError("boom")

async def main():
    try:
        asyncio.create_task(worker())   # ❌ 异常存进 Task，不抛到这里
    except ValueError:
        pass                            # 永远进不来，try 早执行完了
    await asyncio.sleep(1)
# 程序退出时只剩一行日志：Task exception was never retrieved
```

没人 `await`/`.result()` 去取，task 又被 GC，异常就只剩那行警告（最接近 Go 里没 recover 的 goroutine，区别是 Python 不会 crash 进程，只是「静默」）。两条救法：

1. **优先 `TaskGroup`（3.11+）**：任务收回作用域，任一失败自动取消其余并把异常打包成 `ExceptionGroup` 抛出（见第 04 章 3.3），根本不需要手动兜。
2. **真要 fire-and-forget（背景常驻任务）**：① 存住引用防 GC；② 挂 `add_done_callback` 把异常打到日志/Sentry：

```python
_bg: set[asyncio.Task] = set()

def spawn_bg(coro):
    t = asyncio.create_task(coro)
    _bg.add(t)                              # 存引用，否则可能被 GC
    t.add_done_callback(_bg.discard)
    t.add_done_callback(                    # 异常上报，别让它静默
        lambda f: f.cancelled() or (f.exception() and
                  log.error("bg task failed", exc_info=f.exception())))
```

> `gather(*coros, return_exceptions=True)` 是另一种「吞」：异常被当成返回值塞进结果 list，不抛。要 fail-fast 用默认 `return_exceptions=False` 或直接上 `TaskGroup`。

### 3.8 坑：以为「单线程」就不用锁

最容易翻车的一句话：「asyncio 单线程，共享状态不用加锁。」——只对一半。协程只在 `await` 处让出，所以：

- **临界区内没有 `await`** → 中间没人能插队，`counter += 1`、`d[k] = v` 这种**就是原子的，真不用锁**（同样的 `counter += 1` 在 `threading` 里反而是经典 race，因为 GIL 可能在 `LOAD/ADD/STORE` 之间切线程）。
- **临界区跨了 `await`** → 让出期间别的协程照样跑、能改你刚读过的状态，竞态立刻回来：

```python
balance = 100

async def withdraw(amount):
    global balance
    if balance >= amount:        # ① read
        await settle()           # ② 让出！另一个 withdraw 在这里也过了 ①
        balance -= amount        # ③ write，基于过期的 read
# 两个 withdraw(100) 并发 → 都过了检查 → 都减 → balance 变负
```

救法是 `asyncio.Lock`（协程级锁，不是线程锁），把**跨 await 的临界区**整段锁起来：

```python
lock = asyncio.Lock()

async def withdraw(amount):
    global balance
    async with lock:             # 持锁期间别的协程想进这段就挂起等待
        if balance >= amount:
            await settle()
            balance -= amount
```

> 真正的区别不是「不用锁」，而是**插队点可见**：threading 里别人能在任意字节码边界插进来（到处都得防）；asyncio 里只能在 `await` 处插进来——竞态全明写成 `await`，肉眼可查、能局部化。所以 asyncio 消灭的是「不可预期的抢占」，**没**消灭「跨 await 的逻辑竞态」。

---

## 4. 日常开发应用

- **选型先问：我的全链路能不能 async 到底？** 能 → 用 asyncio；中途必须调一堆只有同步版的老库 → 重新考虑是否值得，可能直接用线程池更省心。
- **开发期一律开 debug 模式**，自动抓「忘记 await」和「慢回调」。
- **CPU 活一律外包进程池**，别在协程里直接算。
- **FastAPI 的一个贴心设计要知道**（第 07 章细讲）：

```python
# FastAPI：同步路由（def）会被自动放到线程池跑，不阻塞循环
@app.get("/sync")
def sync_route():
    time.sleep(1)          # ✅ 不会阻塞别的请求（FastAPI 自动丢线程池）
    return {"ok": True}

# 但 async 路由（async def）里的同步阻塞会冻结循环！
@app.get("/async")
async def async_route():
    time.sleep(1)          # ❌ 冻结整个事件循环，所有请求一起卡
    return {"ok": True}
```

> 记住这条反直觉的事实：在 FastAPI 里，**写 `async def` 反而要更小心**——因为你接管了「不阻塞」的责任。拿不准时，纯同步逻辑写 `def`（交给框架的线程池）往往更安全。

---

## 5. 生产 & 调优实战

- **检测事件循环阻塞**：debug 模式的慢回调警告（`loop.slow_callback_duration`）、阻塞看门狗（`asyncio.sleep(1)` 实际睡了 2 秒就说明被阻塞了 1 秒）、py-spy dump 看卡在哪个同步调用栈。**完整可复制的检测中间件/看门狗代码见** `performance-tuning-roadmap/06b-python-debugging/02-asyncio-debugging.md`。
- **uvloop**：`pip install uvloop`，几乎零成本换上高性能事件循环，吞吐提升 2–4 倍（uvicorn 装了会自动用）。
- **`to_thread` / `run_in_executor(None, …)` 用的是默认线程池，坑位有限**：它复用事件循环的默认 executor——一个 `ThreadPoolExecutor`，默认大小 **`min(32, CPU核数 + 4)`**（≈32，见第 02 章）。这 ≈32 个坑位占满后，后续调用会在执行器的**无界 FIFO 队列里排队**等线程空出来，**并不会真正「无限并发」**。所以 `to_thread` 是「把同步库桥进 async」的工具，**不是高并发引擎**：重 I/O 桥接要建专用 `ThreadPoolExecutor(max_workers=N)` 控制规模，要真高并发就走全 async（第 04 章）。

---

## 6. 面试高频考点

**Q1：为什么 `time.sleep(1)` 会拖垮异步服务？**
asyncio 单线程，`time.sleep` 是同步阻塞、不让出，会冻结整个事件循环 1 秒，期间所有并发连接都没法推进。应该用 `await asyncio.sleep(1)`。

**Q2：协程里必须调用同步库怎么办？**
用 `loop.run_in_executor` 丢线程池（I/O 阻塞）或进程池（CPU 密集），包成可 await，避免阻塞循环。

**Q3：什么是函数染色？**
async 只能被 await、await 只能在 async 函数里，导致一个函数变 async 后调用链一路被迫变 async。Go 的 goroutine 透明、无此问题。实务上应 async 到底或全同步，别混。

**Q4：怎么发现事件循环被阻塞了？**
开 debug 模式看慢回调警告、加阻塞看门狗、用 py-spy dump 看是否卡在同步调用栈（如 `requests`、`socket.recv`）。

**Q5：FastAPI 里 `def` 和 `async def` 路由有什么区别？**
`def` 路由被自动丢线程池执行（同步阻塞不影响别人）；`async def` 路由跑在事件循环上，里面的同步阻塞会冻结整个循环。所以 async 路由里更要小心、必须全程 async。

**Q6：异步代码里 try/except 抓不到异常，可能是什么原因？**
多半是把任务 fire-and-forget 了。`await foo()` 异常会顺着 await 抛回、`try` 抓得到；但 `asyncio.create_task(foo())` 把任务脱钩到后台，异常存进 Task 对象，不会回到 `try`，没人取还会变 "Task exception was never retrieved"。`gather(return_exceptions=True)` 也会把异常塞进返回值不抛。救法：优先用 `TaskGroup`（任一失败取消其余 + `ExceptionGroup`），真要后台任务就存引用防 GC + `add_done_callback` 上报异常。

**Q7：asyncio 单线程，到底要不要加锁？**（经典陷阱题）
看临界区里有没有 `await`。没有（如 `counter += 1`）→ 中间没人插队，原子操作，**不用锁**（同样代码在 `threading` 里却是 race）。临界区**跨了 `await`**（`read; await; write`）→ **必须 `asyncio.Lock`**，因为让出期间别的协程会改你读过的状态。一句话：asyncio 消灭了「不可预期的抢占」，没消灭「跨 await 的逻辑竞态」。直接答「单线程不用锁」会被追问翻车。

---

## 7. 一句话总结

asyncio 的所有坑都来自「单线程协作式」这一个根：**任何不让出的耗时操作都会冻结全场。** 救法只有两条——**换 async 库**或 **`run_in_executor` 丢池子**（I/O→线程池、CPU→进程池）。再加上「开发开 debug 模式、调用带超时、警惕函数染色、拿不准就写同步 `def` 交给框架线程池」，asyncio 就稳了。

---

> **下一章** `06-anyio/`：anyio 与结构化并发——FastAPI 底层用的那套，解决你「anyio 一知半解」。
