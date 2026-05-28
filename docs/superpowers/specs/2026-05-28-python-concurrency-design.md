# Python 并发系统课 — 设计 spec

> 日期：2026-05-28
> 目录：`python-concurrency/`

## 背景与目标

用户是 5 年+ Java/Go 后端工程师，并发底子（线程、线程池、锁、CAS、goroutine、channel）扎实但生疏，**Python 并发这块很薄**：基础问题答不上来，anyio/gunicorn/uvicorn 一知半解，对「生产里怎么用 Python 并发」完全没概念。

目标（用户原话「两者都要：先懂再背」）：
1. **像 `java.util.concurrent` 一样系统**地讲一遍 Python 的并发体系。
2. **先建立完整的理论认识**，再做实验（用户明确要求理论优先）。
3. 最终能**应对面试**（讲清原理 + 答高频题）。

## 核心设计决策

- **形式**：多文件 mini-course，对标仓库里已有的 `mysql-handson/`（用户认可且熟悉的形态）。
- **路线**：自底向上 + 生产专章。原理(GIL) → 三大原语(threading/multiprocessing/asyncio) → 生态(anyio) → 生产部署(gunicorn/uvicorn/celery) → 模式&调优 → 面试卡。第 1 章末尾放「生产预告」让用户先看到终点。
- **理论优先，lab 后置**：**不搭独立 lab 环境**。每章内嵌可直接 copy 运行的最小代码（stdlib + 个别 `pip install`）。理论吃透后再回头加 docker lab（仅 celery 章需要 Redis）。
- **贯穿主线 = Java/Go ↔ Python 映射**：每个 Python 原语都对标 JUC / goroutine 的对应物。GIL 是「为什么 Python 不一样」的总钥匙。
- **calibration（重要）**：用户 Python 并发起点低，narrative 要从更基础处讲起、多用类比，**不要假设他熟悉 Python 生态**。承接已有记忆 [[feedback-learning-style]]：先在正文讲透原理和具体数字，再让他应用；predict-then-observe 仅用于他 Java/Go 直觉能支撑的预测（如「4 线程能否加速 CPU 密集」）。

## 章节地图

| 章节 | 内容 | 跨语言对标 |
|---|---|---|
| `00-execution-model/` | **执行地基**（后补）：OS 视角（进程/线程/调度/上下文切换/用户态内核态/syscall/阻塞 I/O/epoll）+ 解释器内部（字节码/eval loop/GIL 实现/协程=生成器/事件循环）+ 全链路贯通图。深度=资深面试够用，不抠源码 | OS + JVM 执行模型 |
| `01-foundations-gil/` | 进程/线程/协程在 Python 里 + **GIL 深讲** + 三大武器全景 + 生产预告 | 全局地图 |
| `02-threading/` | `threading` 全家桶 = JUC 平移：Thread/Lock/RLock/Condition/Semaphore/Event/Barrier/queue.Queue/ThreadLocal/ThreadPoolExecutor/Future + GIL 限制 demo | `java/concurrent/*` |
| `03-multiprocessing/` | Process/Pool/ProcessPoolExecutor/Queue/Pipe/shared_memory、fork vs spawn、pickle 开销、真多核加速 | 多开 JVM 进程 |
| `04-asyncio-core/` | 事件循环/coroutine/await/Task/gather/TaskGroup/asyncio.Queue/取消&超时；**asyncio≠goroutine** | Go goroutine/channel |
| `05-asyncio-pitfalls/` | 阻塞事件循环、同步混进 async、run_in_executor、函数染色、调试 | — |
| `06-anyio/` | anyio + 结构化并发(trio 模型)，FastAPI 为何用 anyio | — |
| `07-prod-web-workers/` | **生产①**：WSGI vs ASGI、gunicorn(sync/gthread/gevent)、uvicorn worker、各框架线上怎么跑、worker 数怎么定、优雅重启 | Tomcat 线程池 vs 多 JVM |
| `08-prod-task-queues/` | **生产②**：Celery(prefork/threads/gevent 池)、RQ、arq、APScheduler、后台任务选型 | Spring @Async + MQ 消费者 |
| `09-patterns-tuning/` | 并发模式(生产者消费者/限流/连接池/fan-out-in/超时重试熔断) + 调优(池大小/uvloop) + py-spy 剖析 | — |
| `99-interview-cards/` | 反向产出的面试题答案卡，每张链回章节做证据 | mysql-handson 卡 |

每章固定 7 段：**核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结**。

## 已有素材的处理

- 仓库已有但分散的相关笔记，章节内**链接复用、不重复**：
  - `performance-tuning-roadmap/06b-python-debugging/01-gil-concurrency-model.md`（GIL+选型）
  - `performance-tuning-roadmap/06b-python-debugging/02-asyncio-debugging.md`（asyncio 排查）
  - `performance-tuning-roadmap/00-os-fundamentals/05-process-thread-coroutine.md`（OS 层）
  - `java/concurrent/*`（Java 侧基础，做对标锚点）
- 本次先写的鸟瞰笔记 `python/并发-进程-线程-协程.md`：内容收编进第 1 章的深化版；待课程成形后再决定是否删除标准版（避免双源漂移）。

## 交付节奏

1. 写本 spec（本文件）。
2. 搭骨架：根 `README.md`（含进度地图）+ 章节目录。
3. **先只写第 1 章**作为样例，确认深度/风格。
4. 用户反馈后按章推进，每章一交付。

## 验收标准

- 理论部分自洽完整：读完一章能讲清该章的「核心问题」和面试考点，无需先做实验。
- 每个 Python 原语都有明确的 Java/Go 对标。
- 生产部署有专章，能回答「FastAPI/Django 线上到底怎么跑、worker 怎么配」。
- 代码片段可直接运行（标注所需 `pip install`）。

## 非目标（YAGNI）

- 不搭 docker lab 环境（理论优先，后置）。
- 不覆盖 free-threaded/no-GIL 的深度实现（仅了解性提及 PEP 703）。
- 不做 asyncio 源码级剖析（事件循环用 selector 实现的原理点到为止）。
