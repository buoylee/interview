# 06 · 异步数据访问:值不值,怎么用

> **为什么这章重要**:FastAPI 火了之后,「数据层要不要 async」成了高频纠结。async 不是免费的「更快」——它有 `await` 着色传染的工程成本,还有 `MissingGreenlet` 这类只在异步下出现的坑。这章给你两件事:**什么时候 async 数据访问真的值**,以及**它在底层是怎么把同步式 ORM 跑成异步的**。
>
> **一句话心智**:async 数据层只在「**海量并发 IO + 全异步栈**」才值;它靠 asyncpg + greenlet 桥让 ORM 异步化,池语义照旧但要够大,懒加载在异步下会咬人。

## 一、async engine / session 长什么样

和同步版几乎对称,多了 `async`/`await` 和 `Async*` 前缀:

```python
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from models import Author

engine = create_async_engine("postgresql+asyncpg://postgres:postgres@localhost/datalab")

async def main():
    async with AsyncSession(engine) as s:
        result = await s.scalars(select(Author).limit(3))   # await 执行
        for a in result:
            print(a.name)
    await engine.dispose()

asyncio.run(main())
```

对照同步版(第 [03](03-orm-session-uow.md) 章):`Session` → `AsyncSession`,`s.scalars(...)` → `await s.scalars(...)`,`create_engine` → `create_async_engine`,URL 前缀 `+psycopg` → `+asyncpg`。**API 形状一样,每个会发 SQL 的调用前面加 `await`**。

## 二、值不值:看并发形态,不是看「听说快」

**实测对比**(`lab/demos/async_vs_sync.py`,20 次 `SELECT pg_sleep(0.05)`,Postgres 16 / 本地,你的数字会不同):

```
sync : 20 queries x 0.05s sequential = 1.07s
async: 20 concurrent                   = 0.28s  (speedup 3.7x)
```

读这个数字要诚实:

- **async 赢在「大量并发等待」**:20 个查询各等 50ms,sync 单连接串行 = 1.07s;async 并发发出去、一起等 = 0.28s。这正是 async 的主场——**IO 密集、高并发**。
- **不是理论的 20x**:理论上 20 个并发应≈一次 50ms,但实测只有 3.7x。差距吃在哪?20 条新 async 连接的建连/握手 + 事件循环调度开销。**真实世界的 async 加速,总比理论值打折**。
- **CPU 密集、低并发、串行逻辑,async 一点不快**,反而背上 `await` 着色的复杂度。

接第 [00](00-mindset-and-selection.md) 章和 [`../python/13`](../python/13-concurrency-bridge.md) 的结论:**async 不是「更快」,是「同样的线程扛住更多并发等待」**。一旦选 async,`await` 会沿调用链向上传染(函数着色),你无法把同步代码库局部改异步——所以是**架构级决定**,在项目一开始就定,别中途切。

> 决策一句话:**你的 web 框架已经是 ASGI(FastAPI async)、且并发连接数很高 → async 数据层值;否则 sync(psycopg)更省心。**

## 三、内幕:greenlet 桥——同步式 ORM 怎么跑成异步

这是面试加分点,也是踩坑时必须懂的底。**矛盾**:SQLAlchemy 的 ORM API 是同步风格设计的(`a.books` 一访问就「同步地」去查),但异步要求所有 IO 都 `await`。怎么调和?

SQLAlchemy 用 **greenlet**(一种协程/轻量栈切换库)搭了一座桥:把同步式的 ORM 内部代码跑在一个 greenlet 里,当它需要做真正的 IO 时,greenlet **把控制权交还给 asyncio 事件循环去 `await`**,IO 完成再切回来继续。于是你在 `AsyncSession` 上 `await s.execute(...)`,底层是 greenlet 在「同步 ORM 逻辑」和「异步 IO」之间来回切。

**这解释了 `MissingGreenlet` 这个只在异步下出现的坑**:对象还绑在一个 open 的 `AsyncSession` 上,但你在协程里**同步地**(没 `await`)触发了需要 IO 的懒加载——greenlet 桥只在 `await s.execute(...)` 这类入口处搭好,直接同步访问属性没有桥可走 → 抛 `MissingGreenlet`。

```python
async with AsyncSession(engine) as s:
    a = (await s.scalars(select(Author).limit(1))).first()
    a.books   # ❌ MissingGreenlet:对象还绑在 session 上,协程里同步触发懒加载 IO,无桥可走
# 区分:若把 a 传出上面的 async with 块、session 关闭后再访问 a.books,
# 抛的是 DetachedInstanceError(对象 detached,与第 03 章同源),不是 MissingGreenlet。
```

> 实测两者确实不同:session 内同步访问 → `MissingGreenlet`;session 关后访问 → `DetachedInstanceError`。

**规避**(`MissingGreenlet` 与 detached 两种都靠它解决):

- 在 session 内就 **eager 加载**要用的关系:`select(Author).options(selectinload(Author.books))`——异步下尤其推荐 `selectinload`(它一条 `IN` 查询拿完,不依赖逐个懒加载)。
- 或显式 `await s.refresh(a, ["books"])` 在 session 内加载好。
- **异步下尽量别用懒加载**:把要用的关系一次性 eager 出来,是 async ORM 的基本纪律。

## 四、async 下的连接池

async engine 用的是 `AsyncAdaptedQueuePool`,**参数和同步 `QueuePool` 一样**(`pool_size`/`max_overflow`/`pool_timeout`…,第 [02](02-connection-pooling.md) 章)。区别在心智:

- async 的卖点是「单线程扛大量并发连接」,所以**池往往要配得比同步大**——你可能同时有几百个协程各要一条连接。
- 但池再大也有上限,且最终受 Postgres `max_connections` 约束。**async ≠ 无限并发**:协程数超过池大小时,多出来的照样排队等 `pool_timeout`。
- demo 里 `make_async_engine(pool_size=N)` special 把池开到并发数 N,就是为了让 20 个协程都能立刻拿到连接、真正并发——否则池小了就退化成排队,speedup 没了。

## 五、反向桥:同步世界里偶尔要调异步(或相反)

- **async 代码里要做一段阻塞调用 / CPU 活**:别直接在协程里干(会卡住整个事件循环),丢到线程池——`await asyncio.to_thread(blocking_fn, ...)`(接 [`../python/13`](../python/13-concurrency-bridge.md) Q5)。
- **同步代码里偶尔要调一个 async 库**:用 `asyncio.run(coro())`(仅在没有运行中的事件循环时)。但**别在同步 web 框架里硬塞 async 数据层**——那是 async 着色反向传染,得不偿失。

> 并发模型本身(事件循环、着色、`asyncio` 实操陷阱)在 [`../python/13`](../python/13-concurrency-bridge.md) 和 [`../python-concurrency/04-asyncio-core`](../python-concurrency/04-asyncio-core)。本章只管「数据访问这一段」怎么异步。

## Java/Go 对照框

| 关注点 | Java | Go | Python |
|---|---|---|---|
| 主流模型 | 同步 JDBC + 线程(/虚拟线程) | 同步驱动 + goroutine | 同步(psycopg)/ 异步(asyncpg) |
| 高并发 IO 怎么扛 | 线程池 / 虚拟线程(Loom) | goroutine(语言层屏蔽异步) | asyncio + asyncpg(显式 `await`) |
| 异步是否传染 | 虚拟线程**不传染**(同步写法) | goroutine **不传染** | **传染**(`await` 着色) |
| 异步 ORM 桥 | R2DBC(响应式) | 无需(goroutine) | greenlet 桥 |

最大对比:**Go 的 goroutine 和 Java 的虚拟线程让你「用同步写法拿到异步的并发」,没有着色传染**;Python 的 asyncio 是显式 `await`,会传染整条链路。这让「Python 要不要上 async 数据层」成为一个真实的架构取舍,而 Go/新 Java 里这几乎不是问题(直接同步写、并发交给 runtime)。

## 章末面试卡

**Q1. 什么时候该用 async 数据访问?它是「更快」吗?**
不是单纯更快。async 在「海量并发 IO + 全异步栈(ASGI/FastAPI async)」才值——它让同样的线程扛住更多并发等待。低并发、CPU 密集、或同步框架里,async 不快还徒增复杂度和 `await` 着色传染。是架构级决定,项目一开始就定。

**Q2. SQLAlchemy 的 greenlet 桥是干什么的?**
ORM API 是同步风格(访问属性就去查),异步要求 IO 都 `await`。SQLAlchemy 用 greenlet 把同步式 ORM 逻辑跑在一个可切换栈里:需要 IO 时把控制权交还事件循环去 await,完成再切回。于是你能在 AsyncSession 上 `await`,底层由 greenlet 在同步逻辑与异步 IO 间桥接。

**Q3. `MissingGreenlet` 错误怎么来?怎么避免?它和 `DetachedInstanceError` 区别?**
对象还绑在一个 open 的 AsyncSession 上,但你在协程里同步(没 await)触发了需要 IO 的懒加载——greenlet 桥只在 `await` 入口处搭好,直接同步访问属性没桥可走 → MissingGreenlet。区别:若 session 已关、对象 detached 后再访问,则是 DetachedInstanceError(与同步世界同源)。两者都靠 session 内 eager 加载(selectinload)或 `await s.refresh(obj, [...])` 规避;异步下尽量不用懒加载。

**Q4. async 的连接池和同步有什么不同?async 是无限并发吗?**
用 AsyncAdaptedQueuePool,参数与同步 QueuePool 相同。心智上池常要更大(几百协程各要连接)。但 async 不是无限并发:协程数超过池大小照样排队等 pool_timeout,且最终受 Postgres max_connections 约束。

**Q5. async 代码里要做阻塞或 CPU 密集的活怎么办?**
不能直接在协程里做(会卡住整个事件循环)。丢到线程池:`await asyncio.to_thread(fn, ...)`(或进程池做 CPU 活)。反过来同步代码偶尔调 async 用 `asyncio.run`,但别在同步框架里硬塞 async 数据层。
