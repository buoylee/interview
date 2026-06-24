# 08 · 生产② 任务队列 —— Celery 与后台/定时任务

> Web 请求-响应之外，生产的另一半是「后台任务」：发邮件、生成报表、跑批、定时清理、异步处理上传。这些不该卡在请求里，要丢给**任务队列**异步处理。Python 这块的事实标准是 Celery。本章讲它和几个轻量替代怎么跑，以及它们和前面并发模型的关系。
>
> 前置：第 03 章（多进程）、07 章（worker 概念）。

---

## 1. 核心问题

1. 为什么要任务队列？它和 Web worker 有什么区别？
2. Celery 的 broker / worker / result backend 是什么？
3. Celery worker 的 pool（prefork/threads/gevent）怎么选？——又回到 CPU vs I/O。
4. 不想上 Celery 这么重，有什么轻量替代？定时任务怎么做？

---

## 2. 直觉理解

### 2.1 为什么要任务队列

设想用户上传一张图，要生成 5 种尺寸的缩略图（耗时 3 秒）。如果在 HTTP 请求里同步做，用户要干等 3 秒、worker 被占住 3 秒。正确做法：

> **请求里只做「把任务塞进队列」（毫秒级），立刻返回；真正的活由后台 worker 异步去干。**

```
   Web 进程（生产者）          Broker（队列）          Celery worker（消费者）
   handler:                  ┌──────────┐           取任务 → 执行 do_resize()
     task.delay(img)  ──put──▶│ Redis /  │──get────▶  （在独立进程里跑，不占 Web）
     立刻返回 202            │ RabbitMQ │
                            └──────────┘
```

- **Broker（消息中间件）**：存放待处理任务的队列，通常用 **Redis** 或 **RabbitMQ**。
- **Web 进程是生产者**：`task.delay(...)` 把任务投进 broker 就返回。
- **Celery worker 是消费者**：独立进程，从 broker 取任务执行。

> 对标 Java：这就是 **Spring `@Async` + 消息队列消费者** 的组合，或 `@Scheduled`/Quartz 做定时。Celery worker ≈ 你的 MQ 消费者服务。概念你早就有，只是换工具。

### 2.2 它和 Web worker 的区别

| | Web worker（第 07 章） | 任务队列 worker（本章） |
|---|---|---|
| 触发 | HTTP 请求 | 从 broker 拉任务 |
| 时效 | 同步、要快速响应 | 异步、可慢、可重试 |
| 典型活 | 接口逻辑 | 发邮件、跑批、定时、重计算 |
| 失败处理 | 返回错误码 | 自动重试、延迟重试、死信 |

---

## 3. 原理深入

### 3.1 Celery 三件套

```python
# 需要: pip install celery redis
from celery import Celery

app = Celery("tasks",
             broker="redis://localhost:6379/0",       # 任务队列
             backend="redis://localhost:6379/1")       # 结果存储（可选）

@app.task(bind=True, max_retries=3)
def resize_image(self, path):
    try:
        do_resize(path)
    except TransientError as e:
        raise self.retry(exc=e, countdown=5)           # 5 秒后重试，最多 3 次
```

```python
# Web 进程里投递任务
resize_image.delay("/uploads/a.jpg")          # 异步投递，立刻返回一个 AsyncResult
# 或带更多控制
resize_image.apply_async(args=["/a.jpg"], countdown=10, queue="images")
```

```bash
# 起 worker 消费
celery -A tasks worker --concurrency=8 --loglevel=info
```

- **broker**：必须，存任务（Redis/RabbitMQ）。
- **result backend**：可选，存任务结果/状态（要查结果才需要）。
- **task**：用 `@app.task` 装饰的函数，支持重试、超时、路由到不同队列。

### 3.2 投递之后呢？—— 取回结果与后续处理（核心）

> 这是上面那张图没画出来的下半段：任务塞进队列、`delay()` 返回了，可结果在哪、怎么用？

`delay()` 返回的**不是结果**，是一张「取件凭证」`AsyncResult`——里面只有一个 `task_id`。真正的活在别的进程异步跑，跑完把结果写进 **result backend**，你拿凭证去查：

```python
r = resize_image.delay("/uploads/a.jpg")
r.id                # 任务 id（凭证）——可存进 DB、返回给前端
r.status            # PENDING / STARTED / SUCCESS / FAILURE / RETRY
r.ready()           # 是否已跑完（布尔，不阻塞）
r.result            # 成功 → 返回值；失败 → 异常对象
r.get(timeout=10)   # ⚠️ 阻塞等结果（拿不到就一直等）；任务失败会把异常重新抛到这里
```

- **没配 `backend` 就只能投递、查不到结果**：`status` 永远 `PENDING`、`get()` 永远卡住。要查结果/状态，result backend 必配。
- **`PENDING` 有歧义**（资深陷阱）：「任务还没被领走」和「task_id 根本不存在（你查错了 id）」返回的都是 `PENDING`——Celery 默认不记录「未知任务」，所以查不到 ≠ 报错，而是装作还在排队。

**第一陷阱：绝不在 Web 请求里 `r.get()`。** 你刚把任务丢出去就是为了不阻塞请求，紧接着 `get()` 等它跑完，等于又同步了一遍——白丢。`.get()` 只该出现在**另一个后台任务里**或**离线脚本里**，永远不在 HTTP handler 里。

那结果怎么回到用户？三种生产姿势：

**① 轮询（最常见）**：handler 返回 `task_id`（202 Accepted），前端拿着 id 轮询一个状态接口。

```python
@app.post("/resize")
def submit():
    r = resize_image.delay(path)
    return {"task_id": r.id}, 202                # 立刻返回凭证，不等结果

@app.get("/resize/{task_id}")
def status(task_id):
    r = resize_image.AsyncResult(task_id)        # 用 id 重建凭证去查
    if r.ready():
        return {"state": r.status, "result": r.result if r.successful() else str(r.result)}
    return {"state": r.status}                    # 还在跑，前端继续轮
```

**② 推送/回调**：任务跑完**主动通知**——WebSocket / SSE 推给前端，或在任务末尾回调一个 webhook URL。适合不想让前端傻轮、或结果要给第三方系统的场景。

**③ 服务端续跑（任务链）**：结果不回前端，而是「任务 A 跑完自动触发任务 B」。这正是「后续处理」的核心——别在任务里手写 `.delay()` 套娃，用下面的 Canvas 编排。

> 对标 Java：`AsyncResult` ≈ `Future`/`CompletableFuture` 的句柄，`get()` ≈ `Future.get()`（一样会阻塞），轮询接口 ≈ 拿 `requestId` 查异步结果。区别是 Celery 的结果跨进程/跨机器存在 backend 里，靠 id 取，不是进程内引用。

### 3.3 Canvas：把任务串/并起来（编排后续处理）

一个任务做完要接着干别的，用 Celery 的编排原语（叫 **Canvas**）。核心是 `.s()`——**signature**，可理解为「冻结了参数、等着被串起来的任务」（≠ 立刻执行）。

```python
from celery import group, chord

# 串行：resize 的返回值自动接力当 upload 的第一个参数，再喂给 notify
(resize.s("/a.jpg") | upload.s() | notify.s()).apply_async()

# 并行 fan-out：三个尺寸同时生成，三个 worker 一起干
group(resize.s("/a.jpg", sz) for sz in (64, 128, 256)).apply_async()

# fan-out + 汇总 fan-in：并行生成完，把结果列表 [r64, r128, r256] 交给 make_zip 打包
chord(resize.s("/a.jpg", sz) for sz in (64, 128, 256))(make_zip.s())

# 简单成功/失败回调：成功跑 notify，抛异常跑 alert
resize.apply_async(("/a.jpg",), link=notify.s(), link_error=alert.s())
```

| 原语 | 作用 | 对标 Java |
|---|---|---|
| `chain`（`\|`） | 串行，前一个结果接力给下一个 | 流水线 / `thenApply` 链 |
| `group` | 并行 fan-out（撒一批任务） | 并行提交一批 `Future` |
| `chord` | fan-out 后汇总（fan-in），回调收结果列表 | `CompletableFuture.allOf(...)` + 回调 |
| `link` / `link_error` | 成功 / 失败回调 | callback |

> 这就是第 09 章「fan-out / fan-in」模式在任务队列里的落地：`group` 撒出去、`chord` 收回来。注意 `chord` 的汇总要等 group 全部成功才触发，依赖 result backend——backend 不稳会拖住 chord。

### 3.4 Celery 的 pool —— 又是 CPU vs I/O（核心）

`--concurrency` 决定并发度，`--pool` 决定**用哪种并发模型**，本质又回到第 01 章那个根本问题：

```bash
# ① prefork（默认）：多进程池（基于第 03 章 multiprocessing）
celery -A tasks worker --pool=prefork --concurrency=8
#   → 8 个子进程，每个独立 GIL。适合 CPU 密集任务（图像处理、计算）。

# ② threads：线程池（基于第 02 章 threading）
celery -A tasks worker --pool=threads --concurrency=20
#   → 受 GIL 限制，适合 I/O 密集任务（调外部 API、读写文件）。

# ③ gevent / eventlet：协程池（第 07 章见过的 gevent）
celery -A tasks worker --pool=gevent --concurrency=1000
#   → 单进程扛上千并发 I/O 任务。适合海量 I/O 密集（大量 HTTP 回调、爬取）。

# ④ solo：单进程单任务，调试用
celery -A tasks worker --pool=solo
```

> 选型口诀和前面完全一致：**CPU 密集任务 → prefork（多进程绕 GIL）；I/O 密集任务 → threads 或 gevent。** 前六章的知识在这里直接复用。

### 3.5 定时任务：Celery Beat

```python
app.conf.beat_schedule = {
    "cleanup-every-night": {
        "task": "tasks.cleanup",
        "schedule": crontab(hour=3, minute=0),     # 每天凌晨 3 点
    },
}
```

```bash
celery -A tasks beat       # 起调度器，按时把任务投进 broker（由 worker 执行）
```

> 对标 Java 的 Quartz / Spring `@Scheduled`。注意 Beat 只负责「按时投递」，执行还是 worker 干。

### 3.6 轻量替代（不想上 Celery 这么重时）

| 工具 | 定位 | 何时选 |
|---|---|---|
| **RQ**（Redis Queue） | 极简，只基于 Redis，多进程 worker | 简单后台任务，不要 Celery 的复杂度 |
| **arq** | **asyncio 原生**的任务队列，基于 Redis | 你的代码已是 async 生态（FastAPI），任务也是 I/O 密集 |
| **APScheduler** | 进程内调度器（不需 broker） | 只要定时任务、单机、不要分布式 |
| **Dramatiq** | 比 Celery 简洁的现代替代 | 想要 Celery 的能力但更简单的 API |

> arq 值得单独记：如果你整个栈是 FastAPI（异步），用 arq 比 Celery 更自然——任务函数就是 async 的，复用第 04 章的全部知识。

---

## 4. 日常开发应用

- **凡是「不需要同步返回结果、可以慢、可能失败要重试」的活，都丢任务队列**：邮件/短信、报表生成、文件处理、数据同步、Webhook 回调。
- **任务要幂等**：任务可能因重试/重投被执行多次，逻辑必须能安全重复执行（如先查再插、用唯一键去重）。这是任务队列第一纪律。
- **按 CPU/IO 选 pool**：图像/计算类用 prefork；调 API/读写类用 threads/gevent。
- **拆队列**：把慢任务和快任务路由到不同队列、不同 worker，避免慢任务饿死快任务。

---

## 5. 生产 & 调优实战

- **`--concurrency` 按 pool 定**：prefork ≈ 核数（CPU 密集）；threads/gevent 可大（I/O 密集）。
- **prefetch（预取）**：worker 一次从 broker 预取多少任务。默认预取较多，会导致慢任务把预取的快任务也压住——长任务场景设 `worker_prefetch_multiplier=1`。
- **late ack（任务确认时机）**：默认任务一领取就 ack，worker 中途崩溃任务会丢。设 `acks_late=True` 让任务**执行成功后才 ack**，崩溃可重投（但要求幂等）。
- **任务超时**：`task_time_limit` 硬超时（超时杀进程）、`task_soft_time_limit` 软超时（抛异常可清理），防任务卡死占住 worker。
- **监控**：用 **Flower**（`celery -A tasks flower`）看队列积压、worker 状态、任务成功率。队列持续积压 = 消费能力不足，要加 worker 或优化任务。
- **broker 选型**：RabbitMQ 功能全、可靠性强；Redis 简单快但持久化/可靠性弱些。看可靠性要求。

---

## 6. 面试高频考点

**Q1：为什么要任务队列？**
把耗时、可异步、可失败重试的活从请求链路里剥离，让接口快速响应、worker 不被占住；同时获得重试、定时、削峰等能力。

**Q2：Celery 的架构？**
生产者（Web 进程）`delay` 投递任务到 broker（Redis/RabbitMQ），消费者（Celery worker）从 broker 取任务执行，结果可存 result backend。Beat 负责定时投递。

**Q3：Celery 的 prefork / threads / gevent pool 怎么选？**
和通用选型一致：CPU 密集任务用 prefork（多进程绕 GIL），I/O 密集用 threads 或 gevent（海量 I/O）。

**Q4：任务为什么要幂等？怎么保证不丢任务？**
任务可能被重试/重投多次执行，必须幂等。配 `acks_late=True`（执行成功才确认）+ 持久化 broker 可避免崩溃丢任务，但前提是幂等。

**Q5：Celery 太重，有什么替代？**
RQ（极简）、arq（asyncio 原生，配 FastAPI）、Dramatiq（简洁现代）、APScheduler（纯定时、无需 broker）。

**Q6：怎么防止慢任务拖垮整个 worker？**
设 `prefetch_multiplier=1` 避免慢任务压住预取的任务、拆分快慢队列、设任务超时（time_limit）、慢任务单独用专门 worker。

**Q7：`delay()` 返回什么？结果怎么取、怎么回到用户？**
返回 `AsyncResult`（一张只含 `task_id` 的取件凭证），不是结果本身。要查结果得配 result backend，再用 `r.status / r.ready() / r.get()` 查；`get()` 会阻塞且失败时重抛异常。**绝不能在 HTTP 请求里 `get()`**（又同步回去了，白丢任务）。结果回到用户的三种姿势：① 返回 task_id 让前端轮询状态接口；② 任务跑完用 WebSocket/SSE/webhook 主动推；③ 服务端用任务链续跑（不回前端）。另外 `PENDING` 有歧义——未知 task_id 也返回 `PENDING`。

**Q8：任务 A 跑完要接着跑 B，怎么编排？**
用 Celery Canvas，别在任务里手写 `.delay()` 套娃：`chain`（`a | b | c`，结果接力）串行；`group` 并行 fan-out；`chord`（group + 回调）fan-out 后汇总 fan-in；`link`/`link_error` 做成功/失败回调。`.s()` 是 signature（冻结参数待编排的任务）。这就是 fan-out/fan-in 在任务队列里的落地。

---

## 7. 一句话总结

任务队列 = **把异步/耗时/可重试的活从请求里剥离，交给独立 worker 后台处理**，Python 事实标准是 Celery（broker + worker + 可选 result backend，Beat 做定时）。投递只是上半段，下半段是**取结果与后续处理**：`delay()` 给你一张 `AsyncResult` 凭证，结果存 result backend 靠 id 取（别在请求里 `get()`），回前端用轮询/推送、服务端续跑用 Canvas（`chain`/`group`/`chord`）。它的 pool 选型（prefork/threads/gevent）又回到「CPU 密集还是 I/O 密集」这个老问题，前面几章的知识直接复用。生产纪律：**任务幂等、按 pool 配并发、防慢任务饿死、用 Flower 盯积压**。轻量场景用 RQ/arq/APScheduler。

---

> **下一章** `09-patterns-tuning/`：把前面所有武器拼成实战模式（限流/连接池/超时重试/fan-out-in）+ 调优与剖析。
