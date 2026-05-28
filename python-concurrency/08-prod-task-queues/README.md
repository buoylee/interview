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

### 3.2 Celery 的 pool —— 又是 CPU vs I/O（核心）

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

### 3.3 定时任务：Celery Beat

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

### 3.4 轻量替代（不想上 Celery 这么重时）

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

---

## 7. 一句话总结

任务队列 = **把异步/耗时/可重试的活从请求里剥离，交给独立 worker 后台处理**，Python 事实标准是 Celery（broker + worker + 可选 result backend，Beat 做定时）。它的 pool 选型（prefork/threads/gevent）又回到「CPU 密集还是 I/O 密集」这个老问题，前面几章的知识直接复用。生产纪律：**任务幂等、按 pool 配并发、防慢任务饿死、用 Flower 盯积压**。轻量场景用 RQ/arq/APScheduler。

---

> **下一章** `09-patterns-tuning/`：把前面所有武器拼成实战模式（限流/连接池/超时重试/fan-out-in）+ 调优与剖析。
