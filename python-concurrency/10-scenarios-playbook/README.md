# 10 · 实战场景手册 —— 从「需求」反查「该抽哪把武器」

> 前面 00–09 是按**工具**组织的（threading / multiprocessing / asyncio / anyio / 任务队列 / 模式）。问题是：学完一堆武器，真遇到需求时，你常常「好像懂了，但不知道该用哪个」。
>
> 这一章把方向反过来：**从你真实会遇到的后端场景出发**——先一张决策树 30 秒选出武器，再 9 个高频场景，每个都走「需求 → 选型 → 标准 pattern → 骨架代码 → 坑」。落点一律连回前面章节的原语，不重抄。
>
> 前置：第 03（多进程）、04（asyncio）、06（anyio）、08（队列）、09（模式）章——这章是它们的「用在哪」索引。

---

## 1. 怎么用这一章

- **不确定该用 thread / process / asyncio / 队列**：先看 §2 决策树，这是整章脊柱。
- **手上有具体需求**：去 §3 找最像的场景，照「选型 + 骨架」抄。
- **想背面试结论**：每个场景末尾的「**一句话**」就是可直接复述的选型答案。

---

## 2. 总决策树：30 秒选出武器

并发选型在 Python 里只有一条主轴——**这活儿卡在 CPU 还是卡在 I/O**（因为 GIL：CPU 活线程并行不了，必须多进程；I/O 活线程/协程在等待时会释放 GIL，能高并发）。沿着这棵树走：

```
这个任务 CPU 密集 还是 I/O 密集?
│
├─ CPU 密集(计算 / 编解码 / 图像 / 大数据处理 / 加密)
│   │   ← 线程没用(GIL 锁死并行)，必须多进程吃多核
│   ├─ 要在请求内同步出结果? → loop.run_in_executor(进程池)                       【场景 4】
│   └─ 批量 / 可后台?         → ProcessPool 批处理 · 或 Celery prefork(多进程)    【场景 3】
│
└─ I/O 密集(调 API / 查库 / 读写文件 / 等网络)
    │
    ├─ 必须在请求内拿到结果(聚合 / 串联)?
    │   ├─ 有 async 库(httpx/asyncpg/aioredis) → asyncio(gather / TaskGroup)      【场景 1、2】
    │   └─ 只有同步老 SDK(boto3 老接口/某些厂商 SDK) → 线程池(ThreadPoolExecutor / anyio.to_thread)
    │
    └─ 可延迟 / 可后台?
        ├─ 进程内 · 不阻塞主流程 · 结束后要处理(写日志/埋点/通知,丢了不影响对错) → create_task + 监工协程   【场景 9】
        └─ 要可靠 / 崩了重试 / 跨重启不丢(发邮件 / 报表) → 任务队列(Celery threads/gevent · arq)  【场景 5、6】

★ 横切铁律:不管落到哪一支，只要在「打外部依赖」，一律套上
  「超时 + 限流 + 重试」三件套(见 §3 场景 7，原语在 ch09)。
  无节制的并发不是能力，是事故。
```

**两个最常被搞错的点（先记住）：**

1. **「我要快」≠「用多线程」。** Python 里线程只对 I/O 有用；CPU 活上线程，被 GIL 锁死，比单线程还慢（多了切换开销）。CPU 要快 → 多进程。
2. **「请求内拿结果」vs「可以晚点做」是另一条岔路。** 能晚点做的（发券、发邮件、生成报表）都该丢任务队列、先把请求返回掉——这跟 CPU/IO 正交，但对响应延迟影响最大。

> 这棵树就是把 ch01（GIL）+ ch03/04（进程 vs 协程）+ ch08（队列）三章的结论压成一张图。后面每个场景都是这棵树的一条具体路径。

---

## 3. 场景手册

> 每个场景固定 6 格：**场景**（真实需求）→ **错法**（新手怎么写错）→ **选型**（决策树落点 + 为什么）→ **Pattern**（骨架，copy 能跑）→ **坑**（生产真实坑）→ **一句话**（面试结论）。

---

### 场景 1 · 并发调多个下游服务（API 聚合 / BFF）

**场景**：一个接口要同时调用「用户服务 + 订单服务 + 推荐服务」，把三份结果拼成一个响应返回。典型的 BFF / 聚合层。你在微服务后端几乎天天遇到。

**错法**：在 `for` 里挨个 `await`——三个下游变成**串行**，总延迟 = 三次往返之和。

```python
# ❌ 串行:user(300ms) + orders(300ms) + rec(300ms) = 900ms
user   = await get_user(client, uid)
orders = await get_orders(client, uid)
rec    = await get_recommend(client, uid)
```

**选型**：I/O 密集 + 必须请求内拿结果 + 有 async 库 → **asyncio 并发**（决策树右上支）。这是协程最闪光的场景：三个请求在等网络时互相让出 GIL，三次往返**重叠**成一次。

**Pattern**：`asyncio.gather` 把三个协程一起跑，套一个整体超时预算，并用 `return_exceptions=True` 让**部分失败不连累其他**。

```python
# 需要: pip install httpx
import asyncio, httpx

async def get_user(client, uid):
    r = await client.get(f"https://svc-user/users/{uid}")
    r.raise_for_status(); return r.json()

async def get_orders(client, uid):
    r = await client.get(f"https://svc-order/users/{uid}/orders")
    r.raise_for_status(); return r.json()

async def get_recommend(client, uid):
    r = await client.get(f"https://svc-rec/users/{uid}")
    r.raise_for_status(); return r.json()

async def aggregate(uid):
    # 复用同一个 client = 复用连接池(ch09 §3.2)，别在每个请求里 new
    async with httpx.AsyncClient(timeout=2.0) as client:
        async with asyncio.timeout(3.0):                 # 整体预算 3s(Py3.11+)
            user, orders, rec = await asyncio.gather(     # 三个并发，900ms → ~300ms
                get_user(client, uid),
                get_orders(client, uid),
                get_recommend(client, uid),
                return_exceptions=True,                   # 任一失败返回异常对象，不中断其余
            )
    return {
        "user":      None if isinstance(user, Exception)   else user,
        "orders":    []   if isinstance(orders, Exception) else orders,
        "recommend": []   if isinstance(rec, Exception)    else rec,   # 推荐挂了给空，不整单失败
    }
```

> **要么全成、要么全取消**（比如「转账的扣款 + 入账」必须同生死）→ 改用 `asyncio.TaskGroup`（ch06）：一个子任务抛异常，其余**自动取消**，异常汇成 `ExceptionGroup`。聚合场景通常要「部分成功」，所以用 `gather + return_exceptions`；强一致场景才用 TaskGroup。这是面试高频追问。

**坑**：
- **别每个请求新建 `AsyncClient`**——等于丢掉连接池，每次重新 TCP/TLS 握手。client 要复用（应用级单例或依赖注入）。
- `gather` 默认（不带 `return_exceptions`）：某个协程抛异常，`gather` 立刻把这个异常抛给你，但**其余协程不会被取消**，仍在后台跑完——容易留下「没人 await 的悬挂任务」。要么 `return_exceptions=True` 自己处理，要么用 TaskGroup 的「自动取消」语义。
- 整体超时用 `asyncio.timeout(3.0)`（3.11+）；老版本用 `asyncio.wait_for(aggregate_inner(), 3.0)`。

**一句话**：聚合多下游 = `httpx.AsyncClient`（复用连接池）+ `asyncio.gather(return_exceptions=True)` + 整体 `asyncio.timeout`；要「同生死」才换 `TaskGroup`。

---

### 场景 2 · 大量外部 HTTP 调用 / 爬取

**场景**：要抓 1 万个 URL、或给 5000 个第三方端点批量推送。和场景 1 的区别是**量级**：不是 3 个并发，是上万个。

**错法**：把一万个协程一次性 `gather`——同时在飞一万个连接，瞬间打挂对端、耗尽文件描述符、自己 OOM。「能并发」不等于「该全部并发」。

```python
# ❌ 一万个请求同时起飞 → 打垮对端 + 自己 OOM + FD 耗尽
await asyncio.gather(*(fetch(client, u) for u in one_million_urls))
```

**选型**：I/O 密集 + 海量 → asyncio（决策树右上支），但**必须装闸门**：决策树底下那条「横切铁律」在这里是主角——**限并发 + 连接池 + 重试**缺一不可。

**Pattern**：`Semaphore` 把「同时在飞」压到 N 个（ch09 §3.1），`httpx.Limits` 让连接池和它对齐，`tenacity` 处理瞬时失败重试。

```python
# 需要: pip install httpx tenacity
import asyncio, httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

CONCURRENCY = 20
sem = asyncio.Semaphore(CONCURRENCY)         # 同时最多 20 个在飞——保护对端，也保护自己

@retry(                                       # 瞬时失败自动重试(ch09 §3.3)
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=8),     # 退避:0.5→1→2…，别雪上加霜
    retry=retry_if_exception_type(httpx.HTTPStatusError),
)
async def fetch_one(client, url):
    async with sem:                           # 闸门:拿不到令牌就排队等
        r = await client.get(url, timeout=5.0)
        r.raise_for_status()
        return r.text

async def crawl(urls):
    limits = httpx.Limits(max_connections=CONCURRENCY,    # 连接池上限和 Semaphore 对齐
                          max_keepalive_connections=CONCURRENCY)
    async with httpx.AsyncClient(limits=limits) as client:
        results = await asyncio.gather(
            *(fetch_one(client, u) for u in urls),
            return_exceptions=True,           # 单个 URL 永久失败不拖垮整批
        )
    ok   = [r for r in results if not isinstance(r, Exception)]
    fail = [r for r in results if isinstance(r, Exception)]
    return ok, fail
```

**坑**：
- **Semaphore 限的是「在途并发数」，不是「QPS」。** 如果对端要求「每秒不超过 50 次」，并发数限流不够——要真正的**令牌桶**限速（如 `aiolimiter` 的 `AsyncLimiter(50, 1)`）。两者常要叠加。
- **`gather` 一次性把 N 个协程对象全建出来**：百万级 URL 光协程对象就吃光内存。海量时改用「**有界队列 + 固定 worker 数**」流式消费（ch06 memory object stream / `asyncio.Queue` + N 个 worker），别一把梭。
- **连接池 `max_connections` 要 ≥ Semaphore**，否则协程拿到信号量却卡在等连接，闸门形同虚设。
- 重试要**只重试瞬时错误**（超时、5xx、连接重置），别把 4xx（参数错）也重试——那是白重试还放大压力。

**一句话**：海量 I/O = `AsyncClient`（连接池）+ `Semaphore`（限并发）+ `tenacity`（退避重试）+ `return_exceptions`（隔离单点失败）；要限 QPS 另加令牌桶；百万级改队列流式，别裸 `gather`。

---

### 场景 3 · 批量 CPU 处理（图像 / 文件 / 数据）

**场景**：一批图片要批量压缩/打水印、一堆文件要解析、一大坨数据要算特征。纯 CPU 活，几千上万个。

**错法**：用多线程——GIL 锁死，N 个线程轮流用**一个核**，比单线程还慢（多了切换和争锁）。

```python
# ❌ 线程跑 CPU:GIL 让它们排队用一个核，8 线程 ≈ 1 核速度，反而更慢
with ThreadPoolExecutor(max_workers=8) as ex:
    ex.map(cpu_heavy, items)
```

**选型**：CPU 密集 + 批量 → **多进程**（决策树左支）。每个进程有独立解释器、独立 GIL，真正并行吃满多核（ch03）。

**Pattern**：`ProcessPoolExecutor`，worker 数 ≈ CPU 核数；任务函数和参数要可 pickle（跨进程传）。

```python
# 标准库，无需安装
from concurrent.futures import ProcessPoolExecutor
import os

def process_one(path):           # 顶层函数(可 pickle)，纯 CPU 活
    img = load(path)
    return compress_and_watermark(img)

def run_batch(paths):
    # worker 数 = 核数;CPU 活再多 worker 也没用(核就那么多)
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        # chunksize 把多个任务打包一次发给子进程，省 IPC 开销(任务多且短时关键)
        return list(ex.map(process_one, paths, chunksize=16))
```

**坑**：
- **进程间传参/返回值要 pickle**：传大对象（几百 MB 的 ndarray）开销巨大，有时序列化比计算还慢。大数据用共享内存（`multiprocessing.shared_memory`），或只传路径、让子进程自己读盘。
- **worker 数别超核数**：CPU 活给 16 核开 64 进程，只增加切换和内存，不会更快。（I/O 活才需要超配。）
- **任务函数必须可 pickle**：lambda、闭包、实例方法常 pickle 失败 → 用顶层函数。
- **fork vs spawn**：macOS/Windows 默认 spawn（子进程重新 import 你的模块），启动代码要放在 `if __name__ == "__main__":` 里，否则递归起进程。

**一句话**：批量 CPU = `ProcessPoolExecutor(max_workers=cpu_count())` + `chunksize`；别上线程（GIL），别传大对象（pickle 贵），worker 对齐核数。

---

### 场景 4 · Web 请求里混入 CPU 重活

**场景**：一个 async 接口大部分是 I/O，但中间夹一段 CPU 重活——生成缩略图、算一段加密、解析大 JSON、跑个小推理。

**错法**：直接在 async 函数里同步算——**CPU 活不让出 GIL，整个事件循环被卡死**，这个 worker 上所有并发请求一起冻住（ch05 头号坑）。

```python
# ❌ async 里同步算 CPU:事件循环被独占，本 worker 所有请求全卡
@app.get("/thumbnail")
async def thumbnail(url: str):
    img = await download(url)         # I/O，没问题
    thumb = make_thumbnail(img)       # CPU 重活，阻塞事件循环 200ms！
    return thumb
```

**选型**：I/O 流程里的 CPU 段 → 把它**踢出事件循环**。决策树：CPU + 请求内出结果 → 进程池（经 `run_in_executor`）。

**Pattern**：`loop.run_in_executor` 把 CPU 函数丢进**进程池**并 `await`——事件循环在等期间继续服务别的请求。

```python
import asyncio, functools
from concurrent.futures import ProcessPoolExecutor

pool = ProcessPoolExecutor()         # 进程级单例，别每请求新建

@app.get("/thumbnail")
async def thumbnail(url: str):
    img = await download(url)                          # I/O：协程
    loop = asyncio.get_running_loop()
    thumb = await loop.run_in_executor(               # CPU：丢进程池，不阻塞 loop
        pool, functools.partial(make_thumbnail, img),
    )
    return thumb
```

**坑**：
- **进程池 vs 线程池**：CPU 重活用**进程池**（绕开 GIL）；若那段是「只有同步库的 I/O」（老 SDK 阻塞调用），用**线程池**就够（线程等 I/O 时会放 GIL）。选错（CPU 丢线程池）= 白忙，照样卡。
- **进程池有 pickle + 启动成本**：几毫秒的小 CPU 活丢进程池，IPC 开销比省下的还多——别折腾，或攒批。
- **秒级重活别占着请求等**：直接走场景 5 丢队列、先返回。`run_in_executor` 适合「几十~几百毫秒、又必须当场返回」的中量级。

**一句话**：async 里的 CPU 段 = `run_in_executor(进程池)` 踢出事件循环；CPU 用进程池、同步 I/O 用线程池；秒级重活改丢队列（场景 5）。

---

### 场景 5 · 请求里的慢操作异步化（先返回，后台做）

**场景**：用户点「导出报表 / 下单 / 发起转码」，这活儿要几秒甚至几分钟。不能让 HTTP 干等——**先秒回「已受理」，活儿丢后台慢慢做**。

**错法**：在请求里同步做完——用户转圈 30 秒，网关超时（常 30/60s）直接 504，连接还被白占。

**选型**：可延迟、不必请求内出结果 → **任务队列**（决策树「可后台」支，ch08）。Web 进程只管投递 + 秒回 task_id；worker 进程异步消费。

**Pattern**：Celery 投递任务，接口立刻返回 `task_id`；前端拿 id 轮询状态 / 任务完回调通知。

```python
# 需要: pip install celery redis
from celery import Celery
app = Celery("tasks", broker="redis://localhost:6379/0",
             backend="redis://localhost:6379/1")    # backend 存结果/状态

@app.task(bind=True)
def export_report(self, user_id, params):
    data = heavy_query(user_id, params)              # 这段在 worker 进程跑，不占 Web 请求
    url  = render_and_upload(data)
    return {"download_url": url}

# —— Web 接口里(FastAPI/Django) ——
@route.post("/reports")
def create_report(user_id, params):
    task = export_report.delay(user_id, params)      # 投递，立即返回，不等执行
    return {"task_id": task.id, "status": "accepted"}    # 202 秒回

@route.get("/reports/{task_id}")
def report_status(task_id):
    res = export_report.AsyncResult(task_id)
    return {"status": res.status,                    # PENDING/STARTED/SUCCESS/FAILURE
            "result": res.result if res.ready() else None}
```

**坑**：
- **pool 选型**（ch08 §3.2）：报表这种「查库+渲染」偏 I/O → `threads`/`gevent`；「转码/压缩」偏 CPU → `prefork`。又回到 CPU/IO 那条主轴。
- **任务要幂等 + 可重试**：worker 可能崩、消息可能重投（见场景 6）。
- **结果别塞 broker 当数据库**：大结果（文件）传对象存储，任务只返回 URL；backend 只放小状态。
- **能轮询就别同步等**：能「先返回、前端轮询/推送」就别 `task.get()` 阻塞等——那等于把异步又退化成同步。

**一句话**：慢操作异步化 = 队列投递 + 秒回 202+task_id + 前端轮询；pool 按 CPU/IO 选（ch08），任务务必幂等。

---

### 场景 6 · 批量发通知 / 邮件（扇出 + 幂等）

**场景**：一个活动要给 10 万用户发 push/短信/邮件；或一个事件要扇出通知一批订阅者。

**错法**：① 在请求里 `for user: send()` 同步发十万次——必爆超时。② 把「发给十万人」做成**一个**大任务——中途崩了不知发到第几个，重跑就重复轰炸用户。

**选型**：可后台 + 海量 → 任务队列（ch08），且**拆成一人一任务（扇出）**：粒度细 → 失败只影响一个、能单独重试、worker 并行消费。

**Pattern**：一个「分发任务」把大列表炸成 N 个「单发任务」，每个带**幂等键**防重复发。

```python
# 需要: pip install celery redis
@app.task
def fanout_campaign(campaign_id, user_ids):
    for uid in user_ids:                       # 分发任务只做「炸开」，不真发
        send_one.delay(campaign_id, uid)       # 扇出成 N 个独立小任务

@app.task(bind=True, max_retries=5, default_retry_delay=10)
def send_one(self, campaign_id, uid):
    key = f"sent:{campaign_id}:{uid}"
    # 幂等闸门:SET NX，发过就不再发(防 worker 重试/消息重投造成重复轰炸)
    if not redis.set(key, "1", nx=True, ex=86400):
        return "duplicate-skip"
    try:
        notify(uid, campaign_id)
    except TransientError as e:
        redis.delete(key)                      # 没发成功，放开闸门让后续重试
        raise self.retry(exc=e)                # 指数退避重试
```

**坑**：
- **幂等是底线**：队列是「at-least-once」，同一任务可能投递多次；不去重 = 用户收到 5 条一样的短信。用 `SET NX` / 业务唯一约束兜底。
- **占键与发送的顺序**：先占幂等键再发；发失败要把键删掉（或用「发成功才占键」的变体），否则一次瞬时失败就把这人永久挡住。
- **下游限流**：十万任务瞬间涌向短信网关会被限/封——worker 并发数要和网关 QPS 对齐（叠加场景 7）。
- **别用一个巨任务**：粒度细才有「单点失败单点重试 + 水平扩 worker」的好处。

**一句话**：批量通知 = 队列扇出（一人一任务）+ 幂等键（`SET NX`）+ 单任务退避重试 + 对齐下游 QPS；绝不一个巨任务硬发。

---

### 场景 7 · 保护下游不被打爆（限流 + 隔离）

**场景**：你的服务要调一个脆弱下游（老系统、第三方、限了 QPS 的 API）。并发一上来就可能把它打挂；它一慢又会把你的线程/连接全拖住，**故障反向传染**。

**错法**：① 无限并发打下游。② 所有下游共用一个池——某个慢下游把池占满，**不相干的请求也一起饿死**（级联故障）。

**选型**：这是横切关注点，叠在任何场景之上。两件武器：**限流**（Semaphore/令牌桶，控制打出去的量）+ **隔离**（bulkhead，把不同下游的资源分舱，ch09 §3.1/3.5）。

**Pattern**：每个下游一个独立 Semaphore（分舱）+ 整体超时；脆弱的再加熔断。

```python
import asyncio

# 给每个下游单独分舱:A 慢/挂，不会吃掉 B 的并发额度(bulkhead)
limits = {
    "payment":   asyncio.Semaphore(10),     # 支付:脆弱，给小额度
    "inventory": asyncio.Semaphore(50),     # 库存:健壮，给大额度
}

async def call_downstream(name, coro_factory):
    async with limits[name]:                # 各自的舱，互不挤占
        async with asyncio.timeout(2.0):    # 超时:别让一个慢调用拖死整条链
            return await coro_factory()
```

> 真要「失败到一定比例就快速失败、给下游喘息」→ 上**熔断器**（`pybreaker`/`aiobreaker`，对标 Resilience4j CircuitBreaker）。限流防「打太多」，熔断防「明知挂了还硬打」，互补。

**坑**：
- **限流 ≠ 限速**：Semaphore 管「同时几个」，令牌桶管「每秒几个」。下游按 QPS 限时要令牌桶（`aiolimiter`），按并发扛不住时要 Semaphore——常两者叠。
- **隔离的本质是「别共用一个池」**：线程池、连接池、信号量按下游/业务分舱，才不会一损俱损。这就是 Hystrix/Resilience4j 的 Bulkhead。
- **超时是隔离的前提**：没有超时，慢下游会一直占着舱位，分舱也救不了——超时让占用「有上限」。

**一句话**：保护下游 = 每下游独立 Semaphore 分舱（bulkhead）+ 超时（占用有上限）+ 脆弱的加熔断；限并发用 Semaphore、限 QPS 用令牌桶，按需叠。

---

### 场景 8 · 共享状态的并发安全

**场景**：多个线程/协程/进程读写同一份状态——计数器、缓存、累加统计。并发改同一个东西，不小心就数据错乱（竞态）。

**错法 1（线程）**：以为「Python 有 GIL 所以线程安全」——**大错**。GIL 只保证单条字节码原子，`counter += 1` 是「读-改-写」三步，中间会被切走，丢更新。

```python
# ❌ 多线程下 counter += 1 会丢更新(读-改-写非原子)
counter = 0
def worker():
    global counter
    for _ in range(100000):
        counter += 1          # 不是原子！最终 counter < 预期
```

**错法 2（asyncio）**：以为「单线程协程所以不用锁」——**多数对，但有例外**：只要临界区中间有 `await`，就可能被切走，一样竞态。

```python
# ❌ 看似单线程不用锁，但中间 await 处会被切走 → 竞态
async def transfer(amount):
    bal = await read_balance()          # ← 在这 await 让出，另一个协程也读到旧值
    await write_balance(bal - amount)   # 两个协程都基于旧值写 → 钱算错
```

**选型 / Pattern**：按「跑在什么模型上」选锁，或干脆**消灭共享**：

```python
# 线程:threading.Lock(ch02)
import threading
lock = threading.Lock()
def worker():
    global counter
    with lock:                 # 临界区串行化
        counter += 1

# asyncio:asyncio.Lock —— 只在「临界区跨 await」时才需要
import asyncio
balance_lock = asyncio.Lock()
async def transfer(amount):
    async with balance_lock:   # 把「读-改-写」整段锁成原子
        bal = await read_balance()
        await write_balance(bal - amount)

# 进程:不共享内存 → 用外部权威(Redis 原子操作 / DB 事务)
redis.incr("counter")          # 多进程/多机的唯一正解:把原子性下推到 Redis/DB
```

**三条出路（优先级从高到低）**：
1. **消灭共享**：每个 worker 自己累加，最后汇总（map-reduce）；或把状态收敛到**单消费者**串行处理（actor / `asyncio.Queue` 单消费者）。没有共享就没有锁。
2. **不可变 + 消息传递**：用队列传数据而非共享变量（ch06 stream / Go channel 思路）——「不要用共享内存通信，用通信共享内存」。
3. **真要共享**：按模型上锁（线程 `Lock`、协程 `asyncio.Lock`）；**跨进程/跨机**别用本地锁，下推到 Redis/DB 原子操作或分布式锁。

**坑**：
- **GIL ≠ 线程安全**——Java/Go 转 Python 最易踩的认知坑，面试高频。
- **asyncio 要不要锁，看「临界区里有没有 await」**：纯同步段在单线程事件循环里天然原子；一旦中间 await，就要 `asyncio.Lock`。
- **进程间锁要外部化**：`multiprocessing.Lock` 只在同机有效；多机部署只有 Redis/DB 能当权威。
- **锁粒度**：太大伤并发，太小漏保护；能消灭共享就别上锁。

**一句话**：并发安全先想「能不能不共享」（汇总/单消费者/消息传递）；非共享不可才按模型上锁——线程 `Lock`、协程 `asyncio.Lock`（仅临界区跨 await 时）、跨进程下推 Redis/DB 原子操作。GIL ≠ 线程安全。

---

### 场景 9 · 后台异步任务:不阻塞主流程,但结束后要处理

**场景**:主流程要快(秒回用户),但有个**附带动作**——写审计日志、上报埋点、发条通知、刷下缓存。做不做不影响主流程对错,可它跑完后你还想拿结果 / 异常做点事(记日志、告警)。你不想 `await` 它拖慢主流程,也不想它「放飞自我」连死活都不知道。

**错法**:

```python
# ❌ await 附带动作:把它绑进主流程,白白拖慢响应
await write_audit_log(...)

# ❌ 裸 create_task 一行了事:
#   ① 不持引用 → 任务可能被 GC 中途杀掉(Task was destroyed but it is pending)
#   ② 异常被静默吞 → 只在任务被 GC 时打一条 Task exception was never retrieved
asyncio.create_task(write_audit_log(...))
```

**选型**:I/O + 可后台 + **进程内** + best-effort(丢了不影响业务正确性)→ asyncio fire-and-forget(决策树「可后台」支的进程内分叉)。和场景 5 的分界线:**要「可靠 / 崩了重试 / 重启不丢」就升级任务队列**;只是「不想阻塞 + 想观测结果」才落这里。

**Pattern**:用一个「监工协程」把**任务 + 结束后处理**缝成一体,主流程只管 `create_task` 起飞;再用一个集合**持引用防 GC**。纯标准库,无需安装。

```python
import asyncio, logging
log = logging.getLogger(__name__)

async def run_then_handle(coro, name=""):
    """监工:把任务和『结束后处理』缝在一起,异常关在里面绝不外溢"""
    try:
        result = await coro                        # 等的是任务自己,不是主流程
    except asyncio.CancelledError:
        raise                                      # 取消要放行,别吞
    except Exception as e:
        log.error("后台任务 %s 失败: %r", name, e)     # 失败后处理(这里可以 await 告警/补偿)
    else:
        log.info("后台任务 %s 完成: %r", name, result)  # 成功后处理

_bg: set[asyncio.Task] = set()                     # 强引用池:事件循环只持弱引用,不存会被 GC 杀掉
def spawn(coro, name=""):
    t = asyncio.create_task(run_then_handle(coro, name))
    _bg.add(t); t.add_done_callback(_bg.discard)   # 持引用,跑完自动移除
    return t

# —— 主流程:起了就走,不阻塞 ——
async def handle_request(...):
    result = do_main_thing()
    spawn(write_audit_log(result), name="audit")   # 不 await,主流程立即返回
    return result
```

> **升级阶梯**(按可靠性选**最低**一档,别一上来就 Celery):
> - **请求内一次性、响应后做** → FastAPI/Starlette `BackgroundTasks`(框架托管,标准库之上,最省心)。
> - **长命应用、要统一监督 + 优雅关闭** → 活整个 app 生命周期的 `asyncio.TaskGroup`(标准库 3.11+,放 lifespan)或 `aiojobs.Scheduler`(**三方包**,aio-libs/aiohttp 那个组织出品,把上面这套 `_bg` 集合 + 监工 + 收尾打包好了)。
> - **崩了要重试 / 重启不能丢** → 任务队列(场景 5)。

**坑**:
- **不持引用 = 任务可能被 GC 中途杀掉**:事件循环只持弱引用,必须 `_bg.add` 存住(官方文档明确的坑)。
- **不接异常 = 异常被静默吞**:监工里 `try/except` 兜住;裸 `create_task` 的异常只会在 GC 时打条警告,等于丢了。
- **普通 `TaskGroup` 不是 fire-and-forget**:`async with` 退出时会**等所有子任务跑完**——请求里开个短 group 会卡住主流程,正好抵消「不阻塞」。要「结构化又不阻塞」必须用**活整个 app** 的长命 group。
- **关闭会丢**:loop / 进程关闭时这些任务被直接**取消**,结束处理可能没跑完。要保证执行,shutdown 时 `await asyncio.gather(*_bg, return_exceptions=True)`;要更硬就上队列。
- **别无限 spawn**:没有上限的后台任务 = 隐形并发炸弹(打爆对端、自己 OOM)。叠场景 7 的 `Semaphore`,或用 `aiojobs` 的 `limit` 限住。

**一句话**:后台 fire-and-forget = `create_task(监工协程)` + 集合**持引用防 GC** + 监工里 `try/except` 收结果/异常;长命应用升级长命 `TaskGroup` / `aiojobs`,要可靠就上队列;记住普通 `TaskGroup` 会等子任务、**不能**当 fire-and-forget。

---

## 4. 一页速查表（场景 → 落点 → 关键 pattern）

| 需求 | 落点（决策树） | 关键 pattern |
|---|---|---|
| 聚合多下游 | asyncio | `gather(return_exceptions)` + 整体 `timeout` + client 复用 |
| 海量 HTTP / 爬取 | asyncio | `Semaphore` + 连接池 + `tenacity` 退避 + 分批 |
| 批量 CPU 处理 | 多进程 | `ProcessPool(cpu_count)` + `chunksize`，别上线程 |
| 请求内 CPU 段 | 进程池 | `run_in_executor` 踢出事件循环；CPU→进程池/同步IO→线程池 |
| 慢操作不能等 | 任务队列 | 投递秒回 `task_id` + 前端轮询；pool 按 CPU/IO 选 |
| 批量通知 | 任务队列 | 扇出一人一任务 + 幂等键 `SET NX` + 退避重试 |
| 保护下游 | 限流 + 隔离 | 每下游 `Semaphore` 分舱 + 超时 + 熔断 |
| 共享状态 | 消灭共享 / 锁 | 汇总/单消费者；线程 `Lock`、协程 `asyncio.Lock`、跨进程 Redis 原子 |
| 后台 fire-and-forget | asyncio | `create_task(监工协程)` + 集合持引用防 GC + try/except 收尾;长命用 `TaskGroup`/`aiojobs`,要可靠上队列 |

---

## 5. 一句话总结

这一章把前九章的武器按「**你会遇到的问题**」重新索引了一遍。记住整章就记一句话：**先问「CPU 还是 I/O」（决定进程还是协程/线程），再问「请求内要结果，还是可以丢后台」（决定同步并发还是任务队列），最后不管落到哪，打外部依赖一律套「超时 + 限流 + 重试」。** 这三问就是 §2 那张决策树，剩下 9 个场景都是它的具体落地。下次再「好像懂了但不知道用哪个」，回来翻这张表。

---

> **回链**：每个场景的「一句话」可直接进 [`99-interview-cards/`](../99-interview-cards/) 当选型速答；原语实现见 [`09-patterns-tuning/`](../09-patterns-tuning/)。
