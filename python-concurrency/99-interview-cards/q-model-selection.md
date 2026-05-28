# 并发模型选型：CPU 密集还是 I/O 密集

## 一句话回答

选型只问一句话：**任务是 CPU 密集还是 I/O 密集。** CPU 密集 → multiprocessing（绕 GIL 吃多核）；I/O 密集且并发不大 → ThreadPoolExecutor；I/O 密集且海量连接 → asyncio。这条原则贯穿线程池、进程池、Celery pool、gunicorn worker class 所有选型。

## 决策表

| 任务类型 | 选什么 | 理由 |
|---|---|---|
| CPU 密集（计算/图像/加解密/序列化） | multiprocessing / ProcessPoolExecutor | 每进程独立 GIL，真并行 |
| I/O 密集，并发 < 几百 | ThreadPoolExecutor | 简单够用，I/O 时放 GIL |
| I/O 密集，海量连接（上千上万） | asyncio | 单线程事件循环，开销最低 |
| 必须用同步库（无 async 版） | ThreadPoolExecutor | 同步阻塞丢线程池 |
| 混合（I/O 为主 + 偶尔 CPU 重活） | asyncio + 进程池（run_in_executor） | 循环管 I/O，CPU 外包进程池 |

## 三层论证

1. **GIL 是分水岭**：CPU 密集时线程被 GIL 串行化（多线程没用甚至更慢），必须多进程；I/O 密集时 I/O 会释放 GIL，多线程/协程都能重叠等待时间。
2. **并发量决定线程 vs 协程**：几百以内线程池简单够用；上千上万时线程的栈内存（MB级）和切换开销吃不消，asyncio 的协程（KB级、用户态切换）才扛得住。
3. **同一原则层层复用**：Celery 的 `--pool`（prefork/threads/gevent）、gunicorn 的 worker class（sync/gthread/gevent/uvicorn）本质都是这张表的不同包装。

## 证据链接

- 全景与选型树：[01-foundations-gil §4](../01-foundations-gil/README.md)
- 调优视角的选型树：[performance-tuning-roadmap/06b-python-debugging/01-gil-concurrency-model.md](../../performance-tuning-roadmap/06b-python-debugging/01-gil-concurrency-model.md)

## 易追问的延伸

- **Q: 怎么判断是 CPU 还是 I/O 密集？** → 看任务时间花在哪：等网络/磁盘/DB = I/O 密集；纯算/转换 = CPU 密集。用 py-spy 采样能直接看出 CPU 占比。
- **Q: 混合型怎么处理？** → 事件循环跑 I/O，把 CPU 重活 `run_in_executor` 丢进程池，别让它卡循环。
- **Q: CPU 密集除了多进程还有别的招吗？** → 向量化（numpy 释放 GIL）、下沉到 C/Cython、甚至换语言写热点。
