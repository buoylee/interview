# 06 · anyio 与结构化并发 —— FastAPI 底层那套

> 你说 anyio「一知半解」——这章专门拆它。一句话先定性：**anyio 不是 asyncio 的竞争者，而是架在 asyncio 之上的一层更高级、更安全的并发 API**，核心卖点是「结构化并发」。FastAPI/Starlette 底层就用它。理解它，FastAPI 的并发行为你就通了。
>
> 前置：第 04、05 章（asyncio）。

---

## 1. 核心问题

1. 已经有 asyncio 了，anyio 是来干嘛的？它和 asyncio 是什么关系？
2. 「结构化并发」到底解决了什么问题？
3. FastAPI 为什么用 anyio？这对我写 FastAPI 有什么影响？
4. anyio 的几个核心工具（task group / cancel scope / to_thread）怎么用？

---

## 2. 直觉理解

### 2.1 anyio 和 asyncio 的关系

把 asyncio 想成「发动机」，anyio 是「装在发动机上的一套更好开的方向盘和变速箱」：

```
        你的代码
           │
        anyio（统一、安全的高层 API：结构化并发、取消、线程桥接）
           │
   ┌───────┴───────┐
asyncio          trio        ← anyio 能跑在两种"发动机"上
（标准库）       （第三方）
```

- anyio **不自己实现事件循环**，它运行在 asyncio（默认）或 trio 之上。
- 它提供一套**比裸 asyncio 更一致、更不容易出错**的 API，思想主要借鉴自 trio 的「结构化并发」。

> 类比：有点像 SLF4J 之于具体日志实现——anyio 是统一的上层接口，底层可换。但更重要的是它带来的**编程范式升级**（结构化并发），下面讲。

### 2.2 结构化并发解决什么问题

裸 asyncio 的痛点：`asyncio.create_task()` 创建的任务**生命周期是「游离」的**——你可能忘了 await 它、它出错了没人管、函数返回了它还在后台跑（孤儿任务）、取消时漏掉它。并发任务散落各处，难以推理。

**结构化并发**（structured concurrency）的核心原则：

> **并发任务必须有明确的作用域边界，不能比创建它的作用域活得更久。** 进了这个 `{}`，所有在里面起的并发任务，出 `}` 之前必须全部结束（正常完成 / 被取消 / 异常汇总）。

就像普通代码里函数调用有清晰的进入和返回，结构化并发让「并发」也有清晰的进入和退出。这从根上消灭了孤儿任务、漏取消、异常吞掉等一类 bug。

> 其实你在第 04 章见过它的影子：`asyncio.TaskGroup`（3.11+）就是 Python 标准库吸收了 trio/anyio 的结构化并发思想后加进去的。anyio 的 task group 是更早、更完整的版本，且在低版本 Python 上也能用。

---

## 3. 原理深入

### 3.1 Task Group：结构化地起一组任务

```python
# 需要: pip install anyio
import anyio

async def fetch(url): ...

async def main():
    async with anyio.create_task_group() as tg:   # 作用域开始
        tg.start_soon(fetch, "a")                  # 起并发任务（类似 create_task）
        tg.start_soon(fetch, "b")
        tg.start_soon(fetch, "c")
    # ← 作用域结束：保证三个任务全部完成才走到这；
    #    任一任务抛异常 → 其余自动取消，异常汇总成 ExceptionGroup 抛出

anyio.run(main)        # 启动（默认用 asyncio 后端）
```

对比裸 asyncio 的 `create_task`：**任务不会泄漏出作用域**，错误处理统一，这就是结构化的好处。

> 和 `asyncio.TaskGroup` 几乎等价。区别：anyio 版跨 Python 版本、跨后端（asyncio/trio）都能用；`asyncio.TaskGroup` 要 3.11+ 且绑定 asyncio。

### 3.2 Cancel Scope：统一的取消与超时

anyio 把「取消」做成一等公民——**取消作用域**：

```python
import anyio

# 超时：超过 5 秒就放弃里面的操作（不抛异常，静默跳出）
with anyio.move_on_after(5):
    await slow_operation()

# 超时：超过 5 秒抛 TimeoutError
with anyio.fail_after(5):
    await slow_operation()
```

> 对比 asyncio：asyncio 的取消散落在 `task.cancel()` / `asyncio.timeout()` 里，anyio 用统一的「cancel scope」抽象，且取消能干净地沿结构化作用域层层传播。对标 Go 的 `context.Context` 取消树，anyio 这套更接近那个心智。

**底层差异（资深点）：asyncio 是 edge-triggered 取消，anyio/trio 是 level-triggered。** 这是 anyio「取消更干净、更难漏」的真正原因——

- **asyncio（边沿触发）**：`task.cancel()` 只在任务的下一个 await 点**投递一次** `CancelledError`。如果你的协程不小心把它吞了（裸 `except:`、`except BaseException` 没 re-raise、或 `await` 了一个会吃掉 `CancelledError` 的东西），取消就**丢了**，任务继续跑——这是 asyncio 取消最常见的坑。
- **anyio/trio（电平触发）**：cancel scope 是在作用域上**置一个「已取消」标志**。只要执行还在这个作用域内，里面**每一个** checkpoint（await）都会持续抛 `Cancelled`，直到控制流真正离开作用域为止。你吞不掉——下一个 await 又给你抛一次。

> 一句话：asyncio 是「发一次信号赌你接得住」，anyio 是「把整个作用域钉成取消态直到你退出去」。这跟 Go `context.Context` 同一个心智——取消是**状态**（`ctx.Done()` 一直可读），不是一次性事件。

### 3.3 to_thread / from_thread：和同步世界的桥（重要）

这是 FastAPI 用 anyio 的关键之一。把同步阻塞函数丢到线程池跑（第 05 章 `run_in_executor` 的 anyio 版，但更好用）：

```python
import anyio

def blocking_io():          # 只有同步版本的库 / 阻塞 I/O
    return legacy_sdk.call()

async def handler():
    result = await anyio.to_thread.run_sync(blocking_io)   # 丢线程池，不阻塞事件循环
    return result
```

反过来，在工作线程里调度回事件循环用 `anyio.from_thread.run(...)`。anyio 还用一个**容量限制器（capacity limiter）**统一管理这个线程池的并发上限，避免线程爆炸。

这个上限默认 **40**，但不是写死的常量——它就是一个 `CapacityLimiter`，`total_tokens` 在运行期可改（绑在当前事件循环上，所以每个 worker 各一份）：

```python
# 必须在事件循环里调用（取的是当前 loop 绑定的那一份）
anyio.to_thread.current_default_thread_limiter().total_tokens = 100
```

> 这个线程池在 FastAPI 进程里到底怎么排布——同进程异线程、懒加载、和「单线程」如何共存、跨线程怎么把结果唤醒回来——见 [`fastapi-ops/01-foundation`](../../fastapi-ops/01-foundation/) 的 A6。

**三个最容易想错的点（面试也爱追问）：**

1. **这些工作线程和事件循环、和 uvicorn worker 是同一个进程、同一把 GIL。** to_thread 不是「另起一个独立运行时」，就是在当前 worker 进程里多开几条 `threading.Thread`——共享内存、共享那唯一一把 GIL（见 [00 章 B.2](../00-execution-model/README.md)）。
2. **它解决的是「阻塞」，不是「CPU 并行」。** 工作线程跑**阻塞 I/O** 时会睡进内核、**放掉 GIL**（00 章 A.5）→ 事件循环那条线程趁机接着跑别的协程，所以 loop 不被卡。但工作线程要是跑**纯 Python 的 CPU 密集运算**，它**不放 GIL**，反而和事件循环抢那唯一一把 GIL → 没有加速、还可能拖慢 loop。**CPU 活该进多进程，不是 to_thread。**
3. **为什么同步库「必须」丢线程？** 因为 `requests`/`psycopg2` 这类同步库**不会**「把 socket 注册进 epoll 再让出」——那是 `aiohttp`/`asyncpg` 这些原生异步库干的事（00 章 B.4）。同步库只会直接 `recv` 把**当前线程**睡死。你要在 `async` 路由里直接调它，睡死的就是**事件循环自己那条线程**，整个 loop 冻住；丢给 to_thread，睡死的是一条**可丢弃的工作线程**，loop 安然无恙——这就是 to_thread 的全部意义。

### 3.4 Memory Object Streams：anyio 版的 channel

```python
import anyio

async def main():
    send, receive = anyio.create_memory_object_stream(max_buffer_size=100)
    async with anyio.create_task_group() as tg:
        tg.start_soon(consumer, receive)
        async with send:
            for item in source:
                await send.send(item)     # 类似 Go channel 的 send

async def consumer(receive):
    async for item in receive:            # 类似 range over channel
        await handle(item)
```

> 对标 Go channel / asyncio.Queue，但和结构化并发、背压（buffer 满则发送方等待）配合得更自然。

---

## 4. 日常开发应用

- **你写纯 asyncio 应用**：3.11+ 直接用标准库 `asyncio.TaskGroup` + `asyncio.timeout` 即可，不一定要引入 anyio。
- **你写库、要兼容 asyncio 和 trio**，或要支持较老 Python：用 anyio，一套代码两个后端都能跑。
- **你写 FastAPI**：anyio 已经在底层了（见下），你平时不直接调它，但**理解它能解释 FastAPI 的并发行为**。

### FastAPI 与 anyio 的关系（你最关心的）

Starlette（FastAPI 的底座）用 anyio 来：
1. **把同步路由丢线程池**：你写 `def`（非 async）的路由函数时，FastAPI 通过 `anyio.to_thread.run_sync` 把它放到线程池跑，避免阻塞事件循环（呼应第 05 章那个「`def` 路由自动进线程池」的行为——背后就是 anyio）。
2. **线程池有容量上限**：anyio 默认限制这个线程池约 40 个线程（capacity limiter）。**这意味着**：如果你大量用同步 `def` 路由 + 慢同步 I/O，可能把这 40 个线程占满，新请求排队——这是个真实的生产瓶颈点。
3. **后端无关**：让 FastAPI 理论上能跑在 trio 上。

> 实务结论：写 FastAPI 时，**重 I/O 的接口尽量 async 到底（用 async 库）**，少依赖「同步 `def` 路由自动进线程池」这条捷径——因为那个线程池容量有限，扛不住高并发慢 I/O。

---

## 5. 选型决策：anyio vs asyncio，业界主流怎么选

§4 给了按场景的快速版，这里把「怎么决策」和「业界到底怎么选」讲透——这是面试常被追问的判断题。

### 5.1 先破一个误解：应用层往往不是二选一

当 anyio 跑在 asyncio 后端上时，两者的协程是**互通**的——asyncio 代码里能调 anyio 函数，反过来也行。所以多数时候你不需要在 app 里「选边站」。真正需要二选一的只有两种场景：

- 你在**写一个要被别人用的库**（要不要做到后端无关）；
- 你在**给整个项目定并发风格**（团队统一用哪套 API）。

### 5.2 决策框架（一句话版）

- **写应用 / 业务服务 → asyncio。** 生态都在上面（FastAPI、asyncpg、aiohttp、SQLAlchemy async），3.11+ 有 `TaskGroup` + `timeout` 够用，少扛一层依赖、团队心智成本低。
- **写库 / 框架，想后端中立、或要最稳的取消语义 → anyio。** HTTPX、Starlette 就是这么选的（见 §3.2 的 level-triggered 取消）。
- **想学最干净的结构化并发心智 → 读 trio/anyio 的设计，生产照样 asyncio + TaskGroup。**

### 5.3 业界主流的真实样貌（别背教条）

1. **应用层约九成直接写 asyncio。** 驱动 / ORM / Web 框架底层都是 asyncio，没理由为抽象多扛一层。
2. **框架 / 库作者越来越多选 anyio。** Starlette / FastAPI / HTTPX / 不少 MCP 实现 底层都用 anyio，好处是不绑死后端。但注意：即使你的 app 跑在 FastAPI 上（底下是 anyio），你的业务代码通常**还是写 asyncio API**，完全不冲突。
3. **真正切去用 trio 后端的团队极少。** 多数采用 anyio 的人从头到尾只跑 asyncio 后端，纯粹图它 API 更漂亮、取消更安全——后端可携性是「保险」（随时能换），不是天天用的功能。
4. **trio 本身**：设计公认最优雅、是结构化并发的发源地，但生态小，生产 app 很少选它。

> **时间线视角（理解 anyio 护城河怎么变窄）：** 3.11 之前，anyio 的 task group 是「标准库里得不到的结构化并发」，这是它最大的卖点；3.11 标准库自带 `asyncio.TaskGroup` 后，这个卖点被削弱，anyio 的护城河收窄到**更强的取消模型（§3.2 的 level-triggered）+ 后端可携性**这两点。

---

## 6. 生产 & 调优实战

- **关注 anyio 线程池容量**：FastAPI 同步路由共用 anyio 的默认线程池（~40 线程）。大量慢同步调用会耗尽它、导致请求排队。排查时看是否有大量 `def` 路由在做慢 I/O；解法是改 async，或调大限制器、或拆专用线程池。
- **结构化并发利于稳定性**：用 task group 而非游离 `create_task`，避免孤儿任务在生产里悄悄泄漏/堆积。
- **取消要传播到位**：长任务用 cancel scope 包好，请求断开/超时时能干净取消，不留僵尸协程。

---

## 7. 面试高频考点

**Q1：anyio 和 asyncio 是什么关系？**
anyio 不是替代品，是架在 asyncio（或 trio）之上的高层 API，提供结构化并发、统一取消、线程桥接，并做到后端无关。

**Q2：什么是结构化并发？解决什么问题？**
原则是「并发任务不能活得比创建它的作用域更久」。进作用域起的任务，出作用域前必须全部结束。它消灭了孤儿任务、漏取消、异常被吞等问题。`asyncio.TaskGroup` 就是标准库吸收的这套思想。

**Q3：FastAPI 为什么用 anyio？**
用它把同步 `def` 路由丢线程池执行（不阻塞事件循环）、统一管理线程池容量、并支持 asyncio/trio 双后端。

**Q4：FastAPI 里大量同步路由可能有什么坑？**
同步路由共用 anyio 的默认线程池（约 40 线程），大量慢同步 I/O 会占满线程池导致请求排队。应尽量 async 到底。

**Q5：anyio 的 task group 和 `asyncio.TaskGroup` 区别？**
功能近似（都是结构化并发）。anyio 版跨 Python 版本、跨后端可用；`asyncio.TaskGroup` 需 3.11+ 且仅 asyncio。

**Q6：实际项目里 anyio 还是 asyncio，你怎么选？**
应用层直接写 asyncio——生态都在上面，3.11+ 有 `TaskGroup` 够用；只有「写要被别人用的库（想后端中立）」或「需要 trio 级取消安全性」时才上 anyio。补一刀：在 asyncio 后端上两者互通，所以 FastAPI 底层是 anyio 并不妨碍你的业务代码写 asyncio。

**Q7：为什么说 anyio 的取消比 asyncio「更安全」？**
asyncio 取消是 edge-triggered——`cancel()` 只在下一个 await 投递一次 `CancelledError`，吞了就丢。anyio/trio 是 level-triggered——cancel scope 内每个 await 都会持续抛 `Cancelled` 直到离开作用域，吞不掉。所以 anyio 更难写出「该取消却没取消干净」的 bug。

---

## 8. 一句话总结

anyio = **架在 asyncio 之上、带「结构化并发」的高层并发 API**：task group 让并发任务有清晰作用域、cancel scope 统一取消、to_thread 桥接同步世界。你不一定直接用它，但它是 FastAPI/Starlette 的底层——理解它就理解了「为什么同步 `def` 路由会进线程池、为什么这个线程池可能成为瓶颈」。结构化并发的思想已被标准库 `asyncio.TaskGroup` 吸收，是未来方向。

---

> **下一章** `07-prod-web-workers/`：终于到生产了——gunicorn/uvicorn 的 worker 模型，FastAPI/Django/Flask 线上到底怎么跑、worker 数怎么配。这是你说「完全没概念」的部分。
