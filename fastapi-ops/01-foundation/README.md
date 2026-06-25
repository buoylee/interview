# 01 — FastAPI 生产化部署(裸机 + 容器)+ uvicorn 内脏

> 核心问题:一个「能跑」的 `uvicorn app:app` 和一个「能上生产」的 FastAPI,差在哪?
> 本章讲清三件事:**uvicorn 内部到底怎么工作**、**怎么在一台 Linux 上把它跑成开机自启/崩溃自愈/优雅关机的正经服务(裸机,Part B)**,以及**怎么把同一套装进容器(主流那条路,Part B′)**。
> 顺序是故意的:**先把裸机的部署原语(进程模型、守护、信号、优雅关机)讲透,再容器化**——因为容器只是把「守护层」从 systemd 换成 runtime/编排,跑你代码的内核(gunicorn+worker)一个字都没变。理解了裸机,容器就是「换壳不换芯」。
> 这是后续所有章节(监控、追踪、压测、调优)共用的载体项目。

---

## 开篇 · 一个你大概率踩过的盲点

你改了一行代码,刷新页面——没生效。重启服务,生效了。为什么?

很多人以为是「`.pyc` 缓存旧了」。**不是。** Python 的 `.pyc`(`__pycache__/` 里的字节码缓存)靠源文件的 mtime+size 自动失效,你一改它就重编,基本不会 stale。

真正的原因是:**一个正在跑的 Python 进程,把所有 import 过的模块以对象形式持在内存里(`sys.modules`),它不会因为你改了硬盘上的 `.py` 就重新加载。** 就跟一个正在跑的 JVM 不会自动换掉已加载的 `.class` 一样——要么重启进程,要么有热重载机制(`uvicorn --reload` / Spring DevTools / JRebel)。

这件小事其实是整章的引子:**线上服务 = 一个长期驻留、持有状态(连接池、缓存)的进程。** 你怎么把它启动、守护、优雅关闭、改了代码怎么不中断地换掉——这就是「部署」。在讲怎么部署之前,得先看清这个进程内部长什么样:**uvicorn 到底在干什么。**

---

## Part A · uvicorn 到底如何工作

### A1 一句话定位:uvicorn 是个「翻译官」

> **uvicorn 是一个 ASGI 服务器。它的工作就是:在 socket 上讲 HTTP,把 HTTP 翻译成对你 app 的函数调用。**

对标 Java,一秒就懂:

| Python | Java 对应 | 干什么 |
|---|---|---|
| **uvicorn** | Tomcat / Netty | 处理 socket、解析 HTTP 协议的那层 |
| **FastAPI**(你写的) | Servlet / Controller | 业务逻辑 |
| **ASGI** | Servlet API | 上面两者之间的「接口契约」 |

Java 里 Tomcat 和你的 Controller 之间靠 Servlet API 解耦;Python 里 uvicorn 和你的 FastAPI 之间靠 **ASGI** 解耦。搞懂 ASGI,就搞懂了 uvicorn 和 FastAPI 的分工。

### A2 ASGI 契约:你的整个 app 其实是一个函数

这是最反直觉、但点破就通的事。你的 FastAPI app,在 uvicorn 眼里就是**一个 async 函数**,签名固定:

```python
async def app(scope, receive, send):
    ...
```

- `scope`:一个 dict,描述这次连接是什么——`type`(`http` / `websocket` / `lifespan`)、method、path、headers……≈ Java 的 `HttpServletRequest` 元数据。
- `receive`:一个 async 函数,`await receive()` 拿到下一个事件(比如请求 body 的一块)。
- `send`:一个 async 函数,`await send({...})` 把响应写回去(先发 `http.response.start` 带状态码+headers,再发 `http.response.body`)。

`FastAPI()` 这个对象本身**就是**这个 callable(底层是 Starlette 实现的)。uvicorn 启动时把它 import 进来、捏在手里,每来一个请求就 `await app(scope, receive, send)` 调一次。**你写的 `@app.get(...)` 路由,只是这个大函数内部的一次分发。**

> 心智模型:你不是在「写接口给 uvicorn 调」,你是把**整个应用打包成了一个异步函数**交给 uvicorn。这就是 ASGI 的全部。

### A3 uvicorn 内部的四个零件

```
       ┌──────────────────── 一个 uvicorn worker 进程 ──────────────────┐
socket │  ① 事件循环 (asyncio / uvloop)   ← 整个进程的心脏,单线程       │
─────▶ │  ② HTTP 解析器 (httptools / h11) ← 把 socket 字节流→请求对象    │
       │  ③ Server/Protocol:accept 连接、建 scope、调你的 app          │
       │  ④ 你的 ASGI app (FastAPI):async def app(scope, receive, send)│
       └────────────────────────────────────────────────────────────────┘
```

1. **事件循环**:`pip install "uvicorn[standard]"` 会带上 **uvloop**(基于 libuv——跟 Node.js 同一个底层 C 库,比标准 `asyncio` 事件循环快不少),装了默认就用它。这就是「每个 worker 内部一个事件循环」的那个循环。
2. **HTTP 解析器**:`[standard]` 还带 **httptools**(C 写的高速 HTTP 解析器),没装就退化到纯 Python 的 **h11**。负责把 socket 进来的原始字节 `GET /x HTTP/1.1\r\n...` 解析成结构化请求。
3. **Server/Protocol 层**:bind 一个 socket、跑 accept 循环;每个连接建一个 protocol 实例,解析完组出 `scope` dict,然后 `await app(...)`。
4. **你的 app**:跑业务,期间 `await` 任何 I/O(查 DB、调外部 API)时,事件循环就转去服务别的连接。

> 所以 `uvicorn[standard]` 不是可有可无——它把「纯 Python 的慢解析 + 慢循环」换成「C 的快解析 + libuv 的快循环」。生产一律装 `[standard]`。

### A4 一个请求在一个 worker 里的完整生命

```
socket 可读 → 事件循环醒 → httptools 解析字节 → 组出 scope
   → await app(scope, receive, send)   ← 进你的 FastAPI 路由
       → 路由里 await db.query(...)     ← 让出!循环转去服务别的请求
       ← DB 回来,循环把控制权调度回这里继续
   → 你 return 响应 → uvicorn 用 send() 把字节写回 socket
```

关键记忆点:**这一切跑在单线程上。** 一个 worker 进程 = 一个事件循环 = 一条线程,靠「谁 await 了就让出」实现并发,而不是靠多线程。这就是为什么单个 worker 能同时扛上千个连接:大家大部分时间都在等 I/O,轮流用这条线程的那一小段 CPU。

### A5 资深分水岭题 ⭐:在路由里写阻塞调用会怎样?

> **面试高频,80% 的人栽在这。**

既然整个 worker 就一条线程、靠 `await` 让出,那如果你在 `async def` 路由里写了一个**不让出**的调用——比如 `requests.get(...)`(同步 HTTP 库)、`time.sleep(5)`、或一段纯 CPU 的重计算——会发生什么?

**事件循环被这一个请求卡死。** 在它返回之前,这条线程没法去服务任何其他连接。这个 worker 上所有并发请求**一起冻住**。你压测会看到:QPS 上不去、P99 爆炸,但 CPU 还没满——因为大家在排队等那条被占住的线程。

正确做法:
- 异步 I/O 用异步库:`httpx`(替 `requests`)、`asyncpg`/SQLAlchemy async(替同步驱动)、`redis.asyncio`。
- 实在要调同步阻塞代码:`await run_in_threadpool(fn, ...)`(Starlette 提供)丢到线程池,别堵循环。
- 重 CPU 计算:丢进程池 / 任务队列(Celery,见 `python-concurrency/08`),别在请求线程里算。

> 这是 FastAPI 最大的坑,详见 [`python-concurrency/05-asyncio-pitfalls`](../../python-concurrency/05-asyncio-pitfalls/)。能讲清这题,面试官就知道你真懂事件循环,而不是只会调 API。

### A6 那个「线程池」到底是什么 —— 单线程怎么又冒出 40 条线程?

> A5 给的解药是「阻塞就丢 `run_in_threadpool`」。但这立刻戳出一个矛盾:不是说一个 worker 就**一条线程**吗,哪来的「线程池」?这一节把这个盒子打开——它是面试里能立刻分出层次的点,也是很多人嘴上会说「丢线程池」却讲不清的地方。

**先把结论钉死,消除矛盾:**

> **基本盘永远是 1 条线程**(事件循环,跑你所有 `async def`)。那个线程池是个**按需、懒加载的「逃生艇」**:你不写同步阻塞代码,它一条线程都不会建。「单线程」讲的是常态,「40 条」讲的是你主动引入阻塞时的可选溢出池。两件事不矛盾。

#### 谁会触发线程池?只有一个开关:函数加没加 `async`

```python
@app.get("/a")
async def a():          # async def → 就在事件循环那条线程上跑,0 条额外线程
    await db.fetch(...)

@app.get("/b")
def b():                # 注意没 async → Starlette 自动把它丢进线程池的某条 worker thread
    requests.get(...)   # 阻塞调用,但有自己的线程兜着,不会堵死循环
```

FastAPI 会检查你的端点是不是协程函数:

- `async def` → 在事件循环上 `await`,**不碰线程池**;
- 光 `def` → 自动走 `run_in_threadpool`(= `anyio.to_thread.run_sync`),**这时才借/建一条 worker thread**;
- 同理,同步的依赖项 `Depends` 和同步的 `BackgroundTasks` 也走这个池。

**所以一个全 `async def` 的 app,那个池从头到尾是空的。** 它不是 uvicorn 的标配,而是「你写了同步阻塞代码时,系统帮你兜底的隔离区」。这正解释了 A5 那条解药的代价:它有个容量上限,见下。

#### 这些线程在哪?同一个进程,不同的线程(不是新进程)

```
       ┌──────────────── 一个 uvicorn worker 进程 ────────────────┐
       │  主线程:asyncio 事件循环   ← 跑你所有 async def           │
socket │       │                                                  │
─────▶ │       │  await run_in_threadpool(同步函数)                 │
       │       ▼                                                  │
       │  anyio 线程池(同进程内的 OS 线程,懒加载 / 闲置复用)        │
       │   ├─ worker thread #1   ← 同步函数在这跑                  │
       │   ├─ worker thread #2                                    │
       │   └─ … 最多 40(可调)                                     │
       └──────────────────────────────────────────────────────────┘
```

定性一句话:**同进程、异线程。** 它们和事件循环线程共享同一块内存、同一把 GIL,只是不同的 OS 线程——不是子进程。这些线程**懒加载 + 闲置复用**:第一次有同步活儿才建,跑完留着给下一个用,长期闲置才回收。而且**每个 worker 进程各有自己的一套**(各自的事件循环 + 各自的线程池),进程间内存不通。

#### 那「40」是什么?是个令牌桶,而且能动态调

线程池的并发上限不是写死的常量,而是 anyio 的一个 **CapacityLimiter(容量限制器,本质是信号量 / 令牌桶)**,默认 `total_tokens = 40`:

- 第 41 个同步活儿来了没令牌 → **排队**等,直到前面有人还令牌(这就是 A5 里「同步路由扛不住高并发慢 I/O」的物理原因)。
- 它**绑在事件循环上**(每个 worker 各一份),所以**有效阻塞并发 = workers × 40**。
- `total_tokens` 是个**可写属性**,运行期随时能改。这就直接回答了「线程数是启动时定死还是动态调」:**默认 40,但完全是动态可调的。**

```python
from contextlib import asynccontextmanager
import anyio
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时把上限从 40 抬到 100(必须在事件循环里调)
    anyio.to_thread.current_default_thread_limiter().total_tokens = 100
    yield

app = FastAPI(lifespan=lifespan)

# 运行期也能改 —— total_tokens 只是个可写属性,从任意 async 上下文都能动:
@app.post("/admin/threadpool/{n}")
async def resize(n: int):
    anyio.to_thread.current_default_thread_limiter().total_tokens = n
    return {"total_tokens": n}
```

> 注意 `current_default_thread_limiter()` 必须在事件循环跑起来**之后**调用(它取的是当前 loop 绑定的那一份),所以放 lifespan 里,别放模块顶层。

#### 事件循环线程和 worker thread 怎么对话(跨线程不出事的机制)

这是「单线程模型里凭空多出一条线程,数据怎么安全传回来」的关键,也是面试爱追的细节:

1. 协程 `await run_in_threadpool(fn)` → anyio 先向 CapacityLimiter **领一个令牌**(没令牌就排队)。
2. 挑一条闲置 worker thread(没有就新建),把 `fn` 丢过去。
3. **协程在此 park,让出事件循环**,循环继续服务别的请求——这一步是它没堵死循环的根本。
4. worker thread 同步跑完 `fn`,用 `loop.call_soon_threadsafe(...)` 把结果塞回事件循环、唤醒那个 park 住的协程。
5. 还回令牌。

对你写的协程来说,它只看到一个普通的 `await`;底下其实是「跨线程把活儿甩出去、再唤醒回来」。

#### 必问的反问:同进程同 GIL,丢到另一条线程到底有啥用?

这是从 Java/Go 过来最容易卡住的点。同一把 GIL,worker thread 跑的时候不也占着 GIL、堵住循环吗?答案在 **GIL 什么时候被放开**:

- worker thread 跑到**阻塞 I/O**(socket、文件、C 扩展写的 DB 驱动)→ 进 C 层那一刻**主动释放 GIL** → 事件循环线程立刻抢到 GIL 继续干活。**这就是丢线程的全部价值。**
- worker thread 跑**纯 Python CPU**(算 hash、跑大循环)→ 它**死抱 GIL**,只靠 GIL 每几毫秒一次的强制切换勉强让一点 → 循环被严重拖慢。**所以 CPU 重活丢这个池几乎没用**,要丢进程池 / 任务队列(A5 已说)。

#### 一句话心智 + 怎么亲眼验证

> **异步并发** = 同一条线程靠 `await` 切换;**阻塞隔离** = 同进程内甩到别的线程,赌它做 I/O 时放开 GIL;**吃多核** = 开多进程(A7)。三件事,三个机制,别混成一锅。

验证也很简单,埋一个端点看线程数:

```python
import threading

@app.get("/threads")
async def how_many():
    return {"active_threads": threading.active_count()}
```

全 `async def` 的 app 打它,数字就一两条;把一堆端点改成同步 `def` 再压测,你会看到线程数往上爬、到 **40 封顶**不再涨——那就是 CapacityLimiter 在挡。

#### 怎么给这 40 定大小(把池定容公式套到 anyio 上)

默认 40 既可能**太小**(同步活儿排队、P99 抬头),也可能**太大**(把下游打挂)。别凭感觉调,套通用定容公式——把线程池当一个 M/M/c 队列,`c = total_tokens`:

1. **下限:`total_tokens > offered load a = λ × S`**
   - `λ` = 这个 worker 上**进线程池的同步调用**速率(req/s);
   - `S` = 每个同步调用**占住线程的时长**(≈ 它背后那个阻塞 I/O 的响应时间)。
   - 例:某 sync `def` 路由调一个遗留 SDK,`S = 0.2s`;这个 worker 每秒来 50 个这类请求 → `a = 50 × 0.2 = 10`。`total_tokens` 至少要 >10,留余量配 ~16。默认 40 在这绰绰有余。

2. **上限 + 总账:`total_tokens × workers × 副本数 ≤ 下游能扛的并发`**
   - 接上例:`16 × 4 worker × 8 副本 = 512` 个并发打向那个遗留后端——它扛得住 512 吗?若它限流在 100 并发,你别说 40,连 16 都过头,得**往下压**并配隔离/限流。
   - **这就是不能无脑信默认 40 的原因**:`40 × worker × 副本` 轻松冲到几百上千,把下游(或它的连接池)打挂——和 connection pool 那个 `单池 × worker × 副本` 总账是同一个雷。

3. **若 `a` 已经 > 下游并行度** → 别调大池(只是把排队从这儿挪到下游、还更慢),该 async 化 / 加缓存 / 给下游扩容 / 上限流 + 专用 `CapacityLimiter` 隔离。

> 一句话:**给 anyio 这池定大小 = 下限喂饱 `λ×S`、上限卡在下游并行度之下、再用 ×worker×副本 总账封顶。** 默认 40 只是「零星同步活儿够用」的起点,不是免算金牌。

> 关联:这个池的**工具视角**(anyio `to_thread` / capacity limiter / 结构化并发)见 [`python-concurrency/06-anyio`](../../python-concurrency/06-anyio/);**池/线程数定容的通用方法论**(Little 定律、M/M/c、×worker 总账、bulkhead 隔离、饱和度监控)见 [`concurrency-capacity`](../../concurrency-capacity/)(尤其 `01`/`05`/`06`/`08`,带可跑 lab);**worker 数怎么配**见 [`python-concurrency/07-prod-web-workers`](../../python-concurrency/07-prod-web-workers/)。

### A7 `--workers N`:用多进程绕开 GIL

单个 uvicorn worker 就一条线程,受 **GIL** 限制吃不满多核。所以线上要起多个 worker:

```
uvicorn app:app --workers 4
   主进程:bind 一个监听 socket → fork 4 个子进程(继承同一个 socket fd)
   ├── worker 1(自己一个事件循环)┐
   ├── worker 2                    ├ 4 个都 accept 同一个 socket,
   ├── worker 3                    │ 内核在它们之间分发新连接
   └── worker 4 ┘                  ┘
   主进程:只当监工,worker 死了重新 fork 一个,自己不处理请求
```

- **worker 数 ≈ 进程数** → 解决「吃多核」。
- **每个 worker 内部的事件循环** → 解决「单 worker 内的高并发」。
- **worker 配几个**:FastAPI 这种异步服务,worker 数 ≈ **CPU 核数**(不用同步框架那个 `2×核数+1`,因为单个事件循环已经能高并发,worker 多了只为吃满多核)。**前提是代码真 async 到底、不阻塞循环(A5)。** 详细的数字题(同步 vs 异步、gthread/gevent)见 [`python-concurrency/07-prod-web-workers`](../../python-concurrency/07-prod-web-workers/),本章不重复。

**三种起法,生产怎么选:**

```bash
# ① uvicorn 自己起多 worker —— 最简单
uvicorn app:app --workers 4 --host 0.0.0.0 --port 8000

# ② gunicorn 当监工 + UvicornWorker 干活 —— 老牌生产组合
gunicorn app:app -k uvicorn.workers.UvicornWorker -w 4 --bind 0.0.0.0:8000
#   gunicorn 的进程管理更成熟:优雅滚动重启(HUP)、--max-requests 防内存泄漏、
#   --preload 省内存。生产想要这些就用它。

# ③ FastAPI 官方 CLI —— 其实就是包了一层 uvicorn --workers
fastapi run app.py --workers 4
```

> 历史背景(面试会问):早年 uvicorn 自己的多进程管理较弱,大家用 **gunicorn + UvicornWorker**。现在 uvicorn 的 `--workers` 和 `fastapi run` 已经够用,但 gunicorn 那套生产参数(见下)仍然更全。两条路都对。

### A8 lifespan 协议:startup/shutdown 是怎么触发的

uvicorn 启动时,会先用一个 `scope["type"] == "lifespan"` 调你的 app:发 `lifespan.startup` 事件、等你回 `startup.complete`——**这一刻就是你的 FastAPI `lifespan` / `@app.on_event("startup")` 被执行的时刻**,建数据库连接池、预热缓存都在这。关机时发 `lifespan.shutdown`,你在这里优雅关闭连接池。

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await create_pool()   # 启动:建连接池(uvicorn 发 lifespan.startup 时跑到这)
    yield                                  # ← 服务运行期
    await app.state.pool.close()           # 关机:优雅关池(收到 SIGTERM 时跑到这)

app = FastAPI(lifespan=lifespan)
```

记住这个 `yield` 上下两半:**上半在进程启动时跑一次,下半在进程优雅关闭时跑一次。** 这正好对接 Part B 的 systemd——`systemctl stop` 发 SIGTERM,你的 `yield` 下半就有机会排空连接、关池,而不是被硬杀。

> **再往下一层:`lifespan.shutdown` 这个事件,是谁、在什么时候发出来的?** 不是信号处理器直接发的。链路是:进程收到 SIGTERM(systemd/docker stop,或 gunicorn master graceful stop 发给 worker;裸跑时 Ctrl+C 是 SIGINT)→ uvicorn 在 `serve()` 启动时早已 `loop.add_signal_handler(SIGTERM/SIGINT, handle_exit)` 装好处理器 → `handle_exit` **只把 `should_exit` 翻成 True**(信号处理器里不做异步清理,只拨一个标志位,因为 `shutdown()` 是协程、要 `await`)→ uvicorn 主循环 `main_loop` 每 ~0.1s tick 一次,发现 `should_exit` 就跳出 → 紧接着 `await Server.shutdown()`:**先关监听 socket(B2 那段)→ 排空在途 → 最后才发 `lifespan.shutdown` 触发这个 `yield` 下半。** 所以「优雅关机」不是同步打断,而是「拨标志 → 事件循环下一拍自己收摊」。**这也正好回扣 A5:若循环被阻塞调用卡死,`main_loop` 这一拍都 tick 不动,连 `should_exit` 都没人看 → shutdown 触发不了 → 等满 `--graceful-timeout` 被 SIGKILL 硬杀。循环被堵,连关机都关不干净。**(连按两次 Ctrl+C 会把 `force_exit` 置 True,跳过排空直接退。)

---

## Part B · 不用 Docker,在 Linux 上正经部署

「正经生产级」= 下面这四层,缺一层都算不上正经:

```
公网 ──▶ ① nginx (443/TLS、静态文件、限流、缓冲慢客户端)
            │  反代到本机
            ▼  unix socket 或 127.0.0.1:8000
         ② gunicorn master + 4×UvicornWorker   ← 真正跑你的代码(Part A)
            ▲
         ③ systemd 守着它(开机自启 / 崩溃自愈 / SIGTERM 优雅关 / cgroup 限资源 / 日志进 journald)
         ④ venv 隔离依赖(绝不用系统 python)
```

对标你熟的栈,骨架完全一样:

| | Java | Go | Python(本章) |
|---|---|---|---|
| 跑代码 | Spring Boot fat jar | 单个二进制 | gunicorn + N×UvicornWorker |
| 守护 | systemd | systemd | systemd |
| 入口 | nginx | nginx | nginx |

唯一的区别:Python 因 GIL 多出 ②那层**多 worker**(Java/Go 单进程就吃满多核,不需要)。这是 GIL 给部署架构带来的最直接差异。

### B1 venv:依赖隔离

```bash
python3 -m venv /opt/myapp/venv
/opt/myapp/venv/bin/pip install "uvicorn[standard]" gunicorn fastapi
```

绝不用系统 Python 装依赖(会污染系统、版本打架)。后面 systemd 的 `ExecStart` 直接指 venv 里的可执行文件,**不需要 `source activate`**——指对路径就行。

### B2 进程管理器层

就是 A7 那套。命令二选一(gunicorn 生产参数更全,推荐):

```bash
/opt/myapp/venv/bin/gunicorn app:app \
    -k uvicorn.workers.UvicornWorker \
    -w 4 \
    --bind unix:/run/myapp/gunicorn.sock \
    --timeout 30 \
    --max-requests 2000 --max-requests-jitter 200 \
    --graceful-timeout 30
```

几个一定要懂的生产参数:

- `--timeout 30`:一个 worker 处理单个请求超过 30s,master 杀掉重启它。慢接口/重活要调大,否则 worker 被反复杀。
- `--max-requests 2000` + `--max-requests-jitter`:每个 worker 处理 2000 个请求后自动重启——**缓解内存泄漏**(Python 长跑进程内存只增不减时定期回收)。jitter 加随机,避免所有 worker 同时重启造成抖动。
- `--preload`:master 先 import 应用再 fork worker,省内存(写时复制共享)、加快启动;代价是改代码要重启 master,且 fork 后某些资源(DB 连接、随机种子)要在 worker 里重建。
- `--graceful-timeout 30`:收到停止信号后,给 worker 30s 排空在途请求再杀。

> **底层:graceful 关机第一步是「关监听 socket」,不是「慢慢接完再关」。** 收到 SIGTERM,gunicorn master 先 `close()` 掉监听 socket、再给 worker 发 SIGTERM(源码 `arbiter.stop()` 顺序:关 LISTENERS → kill_workers(SIGTERM) → 等 graceful_timeout → SIGKILL);uvicorn 的 `Server.shutdown()` 随即 `server.close()` 把监听 fd 从事件循环摘掉——**这一刻起就不再 `accept()` 新连接**,内核 accept 队列里没取走的连接被 RST、新 SYN 打来直接 connection refused。所以 `--graceful-timeout` 那 30s **只用来排空「已经进门的在途请求」**:已建立的 keep-alive 连接会被打上 `Connection: close`(这发响应完即关、不再服务下一个请求),真正在处理的请求给它跑完。换句话说——**它管的是「进了门的请求等多久」,不是「还接不接新请求」:新请求在关 socket 那一刻就被挡在门外了。** 现实里还要前面的 nginx/LB 先停止导流(readiness 转 fail),否则关 socket 瞬间在路上的 SYN 会吃 RST。

### B3 systemd:把它变成一个正经服务(本章重点)

**这才是「不用 Docker 但要正经」的灵魂。** 没有 Docker,靠谁做开机自启、崩溃自愈、优雅关机、限资源、收日志?答案是 systemd——现代 Linux 的 PID 1。

`/etc/systemd/system/myapp.service`:

```ini
[Unit]
Description=My FastAPI App
After=network.target                 # 网络就绪后再启动
Requires=postgresql.service          # 强依赖(可选)

[Service]
User=appuser                         # 非 root 跑(最小权限)
Group=appuser
WorkingDirectory=/opt/myapp
RuntimeDirectory=myapp               # 自动建 /run/myapp(放 unix socket)
EnvironmentFile=/etc/myapp/env       # 密钥/配置从这读,绝不硬编码进代码
ExecStart=/opt/myapp/venv/bin/gunicorn app:app \
          -k uvicorn.workers.UvicornWorker -w 4 \
          --bind unix:/run/myapp/gunicorn.sock \
          --timeout 30 --max-requests 2000 --max-requests-jitter 200

Restart=on-failure                   # 崩了自动拉起 —— 这就是「生产怎么守护」的答案
RestartSec=3
TimeoutStopSec=30                    # 停止宽限期:先 SIGTERM,30s 不退再 SIGKILL
MemoryMax=1G                         # cgroup 内存上限,超了 OOMKilled
LimitNOFILE=65536                    # fd 上限,高并发(大量连接)必调大

[Install]
WantedBy=multi-user.target           # enable 时挂到这,决定开机自启
```

上线三条命令:

```bash
sudo systemctl daemon-reload         # 改了 .service 必须 reload(90% 的「不生效」是忘了这步)
sudo systemctl enable --now myapp    # 既设开机自启,又立即启动
journalctl -u myapp -f               # 看日志(stdout/stderr 自动进 journald,你不用做日志重定向)
```

这套下来你白嫖了 Docker/K8s 帮你做的大半事情:**开机自启 ✅、崩溃自愈(`Restart`)✅、优雅关机(SIGTERM → 触发 A8 的 lifespan 关池)✅、资源限制(cgroup)✅、统一日志(journald)✅。**

> systemd 的机制细节(`enable` vs `start`、`Type=simple` vs `forking`、cgroup、journald vs 文件日志、timer 替代 cron)在 [`linux-handson/08-systemd-and-services`](../../linux-handson/08-systemd-and-services/) 讲透了,本章不重复——那一章的「四语言桥接表」里 Python 那行就是这里的 uvicorn。

### B4 nginx 反代:为什么 uvicorn 不该裸奔公网

uvicorn 技术上能 `--host 0.0.0.0` 直接对公网,但生产不该这么干。前面必须有一层 nginx(或 Caddy/其他反代),原因:

1. **缓冲慢客户端(最重要的技术理由)**:回顾 A4——uvicorn 是单线程事件循环。一个**慢连接**(慢慢发请求 / 慢慢收响应,典型攻击叫 slowloris)如果直连 uvicorn,会占住一个协程、拖慢整个循环。nginx 先把整个请求**完整收齐**再一次性喂给 uvicorn,把慢客户端挡在外面。
2. **TLS 终止**:HTTPS 证书在 nginx 卸载,uvicorn 只跑明文 HTTP(本机回环,安全)。
3. **静态资源**:JS/CSS/图片交给 nginx 发,别浪费 Python 进程。
4. **限流 / 路由 / 多服务**:`limit_req`、按 path 分流到不同后端。

`/etc/nginx/conf.d/myapp.conf`:

```nginx
upstream myapp {
    server unix:/run/myapp/gunicorn.sock;   # 本机走 unix socket,免走 TCP 栈,最快
}

server {
    listen 443 ssl;
    server_name myapp.example.com;
    # ssl_certificate ... (certbot 拿 Let's Encrypt 证书)

    location / {
        proxy_pass http://myapp;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;   # 让 app 知道原始是 https
    }

    location /static/ { alias /opt/myapp/static/; }   # 静态交给 nginx
}
```

> 配套:让 uvicorn/gunicorn 信任 nginx 转发的真实 IP,要加 `--proxy-headers --forwarded-allow-ips='*'`(或具体 nginx IP),否则 `request.client.host` 拿到的是 nginx 的回环地址而不是真实客户端 IP。WebSocket 还需 nginx 转发 `Upgrade`/`Connection` 头。

### B5 零停机:改了代码怎么不中断地换掉

回到开篇——进程持有内存中的旧代码,要换就得重启。但生产不能「停了再起」造成中断。做法:

- **gunicorn 滚动重启**:`kill -HUP <master_pid>`(或 `systemctl reload myapp`,见下)让 gunicorn **逐个**用新代码替换 worker,旧 worker 处理完手头请求再退——服务不断。
- 在 unit 里加一行就能 `systemctl reload`:`ExecReload=/bin/kill -s HUP $MAINPID`。
- `uvicorn --reload` **只配开发用**(它是文件监听热重载,有性能开销、不适合生产)。

### B6 配置与密钥:别硬编码

用 `pydantic-settings` 从环境变量/`.env` 读配置,密钥(DB 密码、API key)走 systemd 的 `EnvironmentFile=/etc/myapp/env`(文件权限设 `600`、属主 `appuser`):

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    log_level: str = "INFO"
    class Config:
        env_file = ".env"   # 本地开发读 .env;生产由 systemd EnvironmentFile 注入

settings = Settings()       # 启动时校验:少了必填项直接报错,不让你带病上线
```

> 好处:配置集中、类型校验、缺失即报错;密钥不进 git、不进镜像、不进代码。

### B7 健康检查:裸机上谁来探活?

```python
@app.get("/health/live")    # liveness:进程还活着吗?(只回 200,不查依赖)
async def live(): return {"status": "ok"}

@app.get("/health/ready")   # readiness:依赖就绪吗?(轻量 ping 一下 DB/Redis)
async def ready():
    await app.state.pool.execute("SELECT 1")
    return {"status": "ready"}
```

两个原则:**liveness 绝不查业务依赖**(否则 DB 抖一下你的进程就被误判杀掉);**健康检查不做重型操作**(别 `SELECT count(*)` 整张表)。

裸机没有 K8s,这俩给谁用?诚实地说:
- **外部监控/Uptime 探测**(Prometheus blackbox exporter、Uptime Kuma 等)定时打 `/health/ready`,挂了告警。
- **nginx upstream**:开源版 nginx 只做**被动**健康检查(某 upstream 连续失败 N 次就暂时摘掉),**主动**定时探测要 nginx Plus 或第三方模块。所以裸机下「探活+告警」主要靠外部监控,不像 K8s 有 kubelet 自动重启。这也正是 Part E 要讲的「systemd ≈ 单机 K8s,但探活这块弱一些」。

---

## Part B′ · 主流那条路:把同一套装进容器

> Part B 是「不上 Docker 的正经做法」。但 2026 年更主流的是**容器化 + 编排**。好消息是:容器化**不是另起炉灶**。

**一句话定调:换壳不换芯。** 跑你代码的内核(`gunicorn + N×UvicornWorker`,Part A/B7 那套)一个字都不变;变的只有外面两层——**守护层**从 systemd 换成容器 runtime(docker/containerd)+ 编排器(K8s),**入口层**从本机 nginx 换成 Ingress / 云 LB。把这句记牢,下面全是细节。(完整的「裸机层 ↔ 容器层」对应表见 Part E,这里只讲**怎么把它装进镜像**。)

### B′1 Dockerfile 多阶段构建:为什么非要两段

最容易写错的是「一段到底」:一个镜像里又装编译器、又装依赖、又跑代码。问题是**编译器和 build 缓存全被打进了生产镜像**——又大、攻击面又广、还可能把构建期的东西泄漏出去。

正解是**多阶段(multi-stage)**:builder 段有编译器、负责把依赖装好;runtime 段只把「装好的依赖 + 你的代码」搬过来,基于 `slim` 基础镜像,**不带编译器**。

> 对标 Java 你秒懂:这跟 fat jar 用 jib / distroless 做多阶段、把 JDK 留在构建期、运行期只带 JRE 是同一个思路。

```dockerfile
# ---------- ① builder 段:有编译器,在独立 venv 里装依赖 ----------
FROM python:3.12-slim AS builder

# asyncpg / uvloop / httptools 这些都带 C 扩展,装的时候要编译
RUN apt-get update && apt-get install -y --no-install-recommends build-essential

RUN python -m venv /opt/venv            # 装进一个独立目录,等下整个搬走
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt   # "uvicorn[standard]" gunicorn fastapi ...

# ---------- ② runtime 段:只带运行期要的,不带编译器 ----------
FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 1000 appuser     # 非 root 跑(对标 B3 的 User=appuser)

COPY --from=builder /opt/venv /opt/venv          # 只搬装好的依赖,编译器留在 builder 段
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY --chown=appuser:appuser . .

USER appuser                                     # 切非 root(见 B′3)
EXPOSE 8000

# exec form(JSON 数组)→ gunicorn 直接当 PID 1,亲自收 SIGTERM(关键,见 B′2)
CMD ["gunicorn", "app:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "4", "--bind", "0.0.0.0:8000", \
     "--timeout", "30", \
     "--max-requests", "2000", "--max-requests-jitter", "200", \
     "--graceful-timeout", "30"]
```

两个跟裸机不一样的细节:

- **bind 从 unix socket 改成 `0.0.0.0:8000` 的 TCP**:裸机时 nginx 和 gunicorn 同机,走 unix socket 最快;容器里入口(Ingress / 另一个容器)在网络的另一头,得 bind TCP 端口暴露出去。
- **没有 systemd 那一坨**:守护交给容器 runtime,镜像里只管「把进程跑起来」。

> **镜像里还要 venv 吗?** 容器本身就隔离了系统 Python,所以 venv **不是为了隔离**——它是为了让 builder 段把全部依赖塞进**一个目录**,runtime 段一行 `COPY` 整个搬走,干净可控。这是多阶段的常用手法,不是多此一举。

### B′2 容器里的头号深坑:PID 1 与信号 ⭐

> **资深分水岭。这题能讲清,面试官就知道你真容器化过、而不是抄了个 Dockerfile。** 它直接接 A8 的 lifespan、B3 的优雅关机。

回顾 A8/B3:优雅关机靠 `SIGTERM` → 触发 lifespan 的 `yield` 下半 → 排空连接、关池。在容器里,`docker stop`(以及 K8s 删 Pod)同样是**先发 SIGTERM、宽限期(默认 10s)后再 SIGKILL**——机制和 systemd 一模一样。

但容器里有个 systemd 没有的陷阱:**你 CMD 启动的进程就是容器里的 PID 1,而 Linux 的 PID 1 有特殊信号语义**——

> 内核对普通进程「没装 handler 的信号就执行默认动作(SIGTERM→终止)」;但**对 PID 1 不走这套**:PID 1 只响应它**显式注册了 handler** 的信号,没注册的直接被忽略。

这就分出两种写法,生死攸关:

- ✅ **`CMD ["gunicorn", ...]`(exec form,JSON 数组)** → gunicorn master **直接当 PID 1**。它是个正经 master,显式处理 SIGTERM(优雅停 worker)→ lifespan shutdown 正常触发 → 连接池排空。对了。
- ❌ **`CMD gunicorn ...`(shell form,字符串)** → Docker 实际跑的是 `/bin/sh -c "gunicorn ..."`,**PID 1 是 sh**。sh 不转发 SIGTERM 给子进程 gunicorn → gunicorn 永远收不到停止信号 → **lifespan 的 `yield` 下半永远不跑** → 等满 10s 宽限期被 SIGKILL 硬杀,连接被粗暴掐断。

**这就是「容器优雅关机失效」最常见的根因**:不是 lifespan 写错了,是信号根本没传到。现象很好认:`docker stop` 每次都卡满 10 秒才退、日志里看不到 shutdown 段执行。

两个解法:

1. **CMD 一律用 exec form**(上面 Dockerfile 那样),让 gunicorn 亲自当 PID 1。
2. 进程树更复杂(你的进程还 fork 别的子进程)时,加一个 **init 进程当 PID 1** 帮你转发信号 + 回收僵尸:`docker run --init`(用内置 tini),或镜像里 `ENTRYPOINT ["tini", "--"]`。gunicorn 自己会 reap 它的 worker,所以单纯 gunicorn 不强制要 tini,但加了更稳。

> 一句话:**exec form 让真正干活的 master 当 PID 1,SIGTERM 才能直达,A8 的优雅关机在容器里才成立。**

### B′3 非 root + .dockerignore + 层缓存:三个必做的小事

- **非 root 跑**(上面 `USER appuser`):默认 root 跑容器,一旦逃逸权限被放大。对标 B3 systemd 的 `User=appuser`,容器里同理——给个 uid 跑业务,别用 root。
- **`.dockerignore`**:把 `.venv/ .git/ __pycache__/ tests/ *.md` 排掉,否则它们被塞进 build context——既拖慢构建,又可能把本地 `.env`、密钥泄漏进镜像。
- **层缓存顺序**(上面 Dockerfile 已体现):先 `COPY requirements.txt` + 装依赖,**再** `COPY . .` 你的代码。这样改业务代码时,依赖层命中缓存不重装——和 Maven 先拉 dependency 层、再 copy 源码一个道理。

### B′4 健康检查:裸机弱的那块,容器补上了

B7 末尾说过:裸机下「主动探活」弱,要靠外部监控打 `/health/ready`。**容器编排正好补上这块**——K8s 的 `readinessProbe` / `livenessProbe`(或 Dockerfile 的 `HEALTHCHECK`)由 runtime/kubelet **主动定时探**你 B7 写的那两个端点:

- `livenessProbe` 打 `/health/live` 挂了 → 重启容器(对标 systemd `Restart=on-failure`,但更智能)。
- `readinessProbe` 打 `/health/ready` 没就绪 → 把这个 Pod 从 Service 摘掉、不给它导流量(开源版 nginx 做不到主动探,这里白拿)。

所以你 B7 那两个端点不是白写——**裸机给外部监控用,容器给 kubelet 用,接口同一个,探的人换了**。

### B′5 编排不在本章 —— 指过去

到这里「**把 FastAPI 装进一个能优雅起停、非 root、瘦身**的镜像」就齐了。再往上的**编排**(K8s Pod/Deployment/Service/滚动更新/HPA 扩缩)是另一个大题,你已有专门 track,本章不重复:

- 容器编排、K8s 对象模型、滚动更新 → [`cloud-native`](../../cloud-native/) / [`cloud-native-landscape`](../../cloud-native-landscape/)
- **分布式/容器优雅停机的完整机制**(本章只讲单实例;摘流量 vs SIGTERM 竞态、`preStop`、滚动不掉容量、长连接排空)→ [`distribution/zero-downtime-release`](../../distribution/zero-downtime-release/)
- **容器 cgroup CPU 限制对 Python/Java 的影响**(`os.cpu_count()` 读到的是宿主机核数不是 cgroup 配额,worker 数别照宿主机核数配)→ [`fastapi-ops/09-system-tuning`](../09-system-tuning/)

> 收口:**容器化 = 换壳(systemd→runtime、nginx→Ingress)不换芯(gunicorn+UvicornWorker 原样);多阶段瘦身、exec-form 保信号、非 root、探活交给编排。** 把芯看住,容器只是把 Part B 那套搬进了一个可移植的盒子。

---

## Part C · 生产踩坑框 ⚠️

> **在路由里写了阻塞调用** → 卡死整个事件循环,这 worker 所有并发一起凉(A5)。FastAPI 头号坑。

> **改了 `.service` 不生效** → 90% 是忘了 `sudo systemctl daemon-reload`。改完 unit 必须 reload 再 restart。

> **`Type` 用错** → 现代程序保持**前台运行**(systemd 默认 `Type=simple`),别给 gunicorn 加 `--daemon`。程序自己 daemonize 会让 systemd 误判主进程退出 = 失败。

> **`LimitNOFILE` 默认不够** → 高并发 = 大量连接 = 大量 fd,不调大就 `Too many open files`。

> **worker 数 × 连接池大小 = 对数据库的总连接数** → 4 worker × pool 10 = 40 条连接,再 × 机器数。配不好直接打满 DB 连接上限,经典生产事故。

> **日志写文件不配 logrotate** → 直接写 `/var/log/app.log` 又不切割,迟早写满磁盘。要么交给 journald,要么配 logrotate。

> **FastAPI 配成同步 worker** → 异步应用必须用 ASGI/uvicorn worker,错配成普通同步 WSGI worker 会让异步代码退化甚至报错。

> **整片用同步 `def` 端点** → 它们全挤 anyio 默认线程池(40 封顶,见 A6),高并发慢同步 I/O 会占满线程池、新请求排队:典型现象是 CPU 没满但 QPS 上不去、P99 爆。解法:重 I/O 端点 async 到底,或按需调大 `total_tokens`。

> **容器 CMD 用 shell form** → PID 1 变成 `sh`,不转发 SIGTERM,gunicorn 收不到停止信号,lifespan 优雅关机失效,`docker stop` 每次等满 10s 被 SIGKILL 硬杀(B′2)。CMD 一律用 exec form 数组,或加 `--init`/tini。

> **在容器里再塞 systemd / 还 bind unix socket** → 容器世界里守护和入口交给 runtime/编排,镜像里重复一套 systemd 是经典反模式(systemd-in-container);unix socket 也没了「同机 nginx」这个邻居,改 bind TCP `0.0.0.0:8000`。

> **root 跑容器 / 没写 `.dockerignore`** → 逃逸放大权限;build context 把 `.env`/`.git` 带进镜像泄漏密钥。给 `USER appuser` + 写 `.dockerignore`(B′3)。

---

## Part D · 面试速记卡(只做复习自检)

**人人会的(不加分)**

- WSGI vs ASGI?→ WSGI 同步(一请求占一 worker/线程到完成,Flask/Django+gunicorn);ASGI 异步(基于事件循环,一 worker 并发海量请求,支持 WebSocket,FastAPI+uvicorn)。
- 为什么 Python 要多 worker,Java 不用?→ 单 Python 进程受 GIL 吃不满多核,多进程才能利用多核+故障隔离;Java 单进程多线程即可。

**资深分水岭** ⭐

- uvicorn 是什么?→ ASGI 服务器,在 socket 上讲 HTTP,把它翻成 `await app(scope, receive, send)` 调你的 FastAPI,跑在单线程事件循环上。
- 一个请求从 socket 到你的函数经过什么?→ socket 可读 → httptools 解析 → 建 scope → `await app(...)` → 路由 await I/O 让出 → send 写回。
- 路由里写 `requests.get()` 会怎样?→ 阻塞调用卡死单线程事件循环,这 worker 所有并发请求一起冻住;改用 `httpx` 异步库或丢线程池。
- 一个 worker 就一条线程,哪来的「线程池」?→ 基本盘是 1 条事件循环线程;只有同步 `def` 端点 / `run_in_threadpool` 才**按需**把活儿丢进 anyio 线程池(同进程异线程、懒加载、闲置复用)。全 async 的 app 这池是空的。
- 那线程池的「40」是启动时定死的吗?→ 不是。是 anyio CapacityLimiter 的 `total_tokens`,默认 40、运行期可改(`current_default_thread_limiter()`);每个 worker 各一份,有效阻塞并发 = workers × 40。丢线程为什么有用?——线程做阻塞 I/O 时会放开 GIL,让事件循环继续跑;纯 CPU 重活则不放 GIL,丢了也白丢。
- 不用 Docker 怎么做开机自启+崩溃自愈?→ 写 systemd `.service`(`Restart=on-failure` + `enable --now`)。
- 为什么前面要放 nginx?→ 缓冲慢客户端(防 slowloris 占住事件循环)、TLS 终止、发静态、限流。
- `--max-requests` 干嘛?→ worker 处理 N 个请求后自动重启,缓解内存泄漏;配 jitter 避免同时重启。
- uvloop / httptools 为什么快?→ uvloop 基于 libuv(C),httptools 是 C 写的 HTTP 解析,替掉纯 Python 的慢实现。
- 优雅关机怎么做?→ systemd `stop` 发 SIGTERM → **先关监听 socket(不再 `accept()` 新连接)** → uvicorn 触发 lifespan 的 shutdown 段排空在途/关池 → `TimeoutStopSec`(对应 gunicorn `--graceful-timeout`)内不退才 SIGKILL。注意:graceful-timeout 只排空「已进门的在途请求」,不是「还接新请求」。
- 容器化和裸机比,跑代码那层变了吗?→ **没变**,还是 gunicorn+UvicornWorker(芯)。变的是守护层 systemd→容器 runtime/编排、入口 nginx→Ingress。换壳不换芯。
- Dockerfile 为什么要多阶段?→ builder 段带编译器装依赖,runtime 段只 `COPY` 装好的依赖、基于 slim,镜像小、攻击面小(对标 Java distroless/jib)。
- 容器里 `docker stop` 优雅关机有时失效,为什么?→ CMD 用了 shell form,PID 1 是 `sh` 不转发 SIGTERM,真正的 gunicorn 收不到,lifespan shutdown 不触发,等满宽限期被 SIGKILL。改 exec form 数组(或 `--init`/tini)。

**架构师**

- worker 数 × 连接池 = DB 总连接数,怎么避免打满?→ 算总量、压测定、必要时上连接池中间件(pgbouncer)。
- 这套裸机栈和 K8s 什么关系?→ 见 Part E,systemd ≈ 单机版 K8s。

---

## Part E · 小结 + 裸机 ↔ 容器对应

**一句话记忆点**

> uvicorn = ASGI 服务器,在 socket 上讲 HTTP、翻成 `await app(scope,receive,send)` 调你的 FastAPI,跑在单线程事件循环上,`--workers` 靠多进程绕 GIL。
> 裸机正经部署 = **venv(隔离)→ gunicorn+UvicornWorker(跑代码绕 GIL)→ systemd(自启/自愈/优雅关/限资源/日志)→ nginx(TLS/缓冲/静态)**。
> 容器化部署 = **多阶段瘦身镜像 → exec-form CMD 让 gunicorn 当 PID 1 保信号 → 非 root → 守护/探活交给 runtime/编排(systemd→runtime、nginx→Ingress)**;换壳不换芯,芯还是 gunicorn+UvicornWorker。

**裸机 ↔ Docker/K8s 对应**(你说不用 Docker,但这个对应是架构师考点)

| 裸机这一层 | Docker/K8s 对应物 | 干的事 |
|---|---|---|
| venv | 镜像里打包的依赖层 | 依赖隔离 |
| systemd `.service` | kubelet + Deployment | 拉起、守护、重启、限资源 |
| `Restart=on-failure` | `restartPolicy` / ReplicaSet 补 Pod | 崩溃自愈 |
| `MemoryMax` / `LimitNOFILE` | Pod `resources.limits` / cgroup | 资源限制 |
| 多 worker 进程 | 多 replica Pod | 绕 GIL 吃多核 + 容量 |
| nginx 反代 | Ingress / Service | 入口、TLS、路由 |
| `/health/ready` + 外部监控 | readinessProbe(kubelet 主动探) | 探活 |
| `systemctl reload`(HUP 滚动) | 滚动更新(rolling update) | 零停机部署 |

> 点题:**systemd 在很多方面就是「单机版的 K8s」**——拉起、守护、健康、限资源、滚动。理解了这套裸机栈,K8s 的 Pod 生命周期会非常好懂。区别主要在:K8s 是**分布式**调度 + **主动**健康探测 + 自动扩缩,裸机这些要靠外部监控和人工补。

**桥接指针**

- worker 模型、worker 数怎么定、WSGI/ASGI 完整对比 → [`python-concurrency/07-prod-web-workers`](../../python-concurrency/07-prod-web-workers/)
- 别在事件循环里阻塞(A5 的坑) → [`python-concurrency/05-asyncio-pitfalls`](../../python-concurrency/05-asyncio-pitfalls/)
- systemd 机制全解 / journald / cgroup → [`linux-handson/08-systemd-and-services`](../../linux-handson/08-systemd-and-services/)
- 从 QPS/P99 反推 worker 数与单机容量 → [`concurrency-capacity`](../../concurrency-capacity/)

---

## 参考

- [Uvicorn Deployment](https://www.uvicorn.org/deployment/)
- [FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/)
- [ASGI 规范](https://asgi.readthedocs.io/)
- [Gunicorn Settings](https://docs.gunicorn.org/en/stable/settings.html)
- [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Docker 多阶段构建](https://docs.docker.com/build/building/multi-stage/)
- [Docker 与 PID 1 / `--init`(tini)](https://docs.docker.com/engine/reference/run/#specify-an-init-process)

➡️ 下一章:[`02-system-metrics`](../02-system-metrics/) — 服务慢/挂,第一时间看什么系统指标。
