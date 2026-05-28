# Python 并发系统课 —— 给 Java·Go 后端的「先懂再背」

> 把 Python 的并发体系像 `java.util.concurrent` 一样系统讲一遍。主线是**用你已有的 Java/Go 心智去理解 Python**，总钥匙是 **GIL**。
>
> 理论优先：每章正文先讲透原理，代码片段可直接 copy 运行（标注所需 `pip install`），暂不搭独立 lab 环境。
>
> 设计来源：`docs/superpowers/specs/2026-05-28-python-concurrency-design.md`

## 怎么用这个课

1. **按顺序读**：00 是执行地基（机器/解释器到底怎么跑并发），01 是总钥匙（GIL）。觉得「没有全局认识、原理落不了地」就从 00 开始。
2. **每章固定 7 段**：核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结。
3. **想答面试题**：去 `99-interview-cards/` 找卡，每张卡链回章节做证据。
4. **想跑代码**：章节里的片段标了 `# 需要: pip install xxx`，直接复制到 `.py` 跑。

## 章节地图

| 章节 | 主题 | 一句话 |
|---|---|---|
| `00-execution-model/` | **执行模型**(OS+解释器+全链路) | 跑起来时机器到底在干什么 ← **想要全局认识/原理从这开始** |
| `01-foundations-gil/` | 进程/线程/协程 + **GIL** + 全景 | 为什么 Python 并发和 Java/Go 不一样 |
| `02-threading/` | `threading` 全家桶 | JUC 平移：Thread/锁/队列/线程池/Future |
| `03-multiprocessing/` | 多进程 | Python 吃满多核的正路 |
| `04-asyncio-core/` | asyncio 核心 | 事件循环/await/Task；asyncio≠goroutine |
| `05-asyncio-pitfalls/` | asyncio 陷阱 | 阻塞事件循环、同步混入、函数染色 |
| `06-anyio/` | anyio + 结构化并发 | FastAPI 底层用的那套 |
| `07-prod-web-workers/` | **生产①** Web worker | gunicorn/uvicorn 线上怎么跑、worker 怎么配 |
| `08-prod-task-queues/` | **生产②** 任务队列 | Celery/RQ/arq 后台任务 |
| `09-patterns-tuning/` | 模式 & 调优 | 限流/连接池/超时重试 + py-spy 剖析 |
| `99-interview-cards/` | 面试卡 | 反向产出的高频题答案 |

## 进度地图

| 章节 | 状态 | 备注 |
|---|---|---|
| 设计 spec | ✅ 完成 | `docs/superpowers/specs/2026-05-28-python-concurrency-design.md` |
| 骨架 + 进度地图 | ✅ 完成 | 本文件 |
| 00-execution-model | ✅ 完成 | 执行地基：OS/解释器/全链路（资深面试向） |
| 01-foundations-gil | ✅ 完成 | 样例章（已认可调子） |
| 02-threading | ✅ 完成 | JUC 平移 |
| 03-multiprocessing | ✅ 完成 | 多核正路 |
| 04-asyncio-core | ✅ 完成 | 事件循环/协程；asyncio≠goroutine |
| 05-asyncio-pitfalls | ✅ 完成 | 阻塞循环/同步混入/函数染色 |
| 06-anyio | ✅ 完成 | 结构化并发 + FastAPI 底层 |
| 07-prod-web-workers | ✅ 完成 | WSGI/ASGI + gunicorn/uvicorn worker |
| 08-prod-task-queues | ✅ 完成 | Celery/RQ/arq |
| 09-patterns-tuning | ✅ 完成 | 限流/连接池/超时重试 + 剖析 |
| 99-interview-cards | ✅ 完成 | 速答表 + 4 张深题卡 |
| (可选) docker lab | ⬜ 后置 | 理论吃透后再加，仅 celery 章需 Redis |

## 关联已有笔记（复用不重复）

- `performance-tuning-roadmap/06b-python-debugging/01-gil-concurrency-model.md` — GIL + 选型（调优视角）
- `performance-tuning-roadmap/06b-python-debugging/02-asyncio-debugging.md` — asyncio 排查手段
- `performance-tuning-roadmap/00-os-fundamentals/05-process-thread-coroutine.md` — OS 层进程/线程/协程
- `java/concurrent/*` — Java 并发基础，做对标锚点
- `python/并发-进程-线程-协程.md` — 鸟瞰桥接版（本课第 1 章的精简前身）
