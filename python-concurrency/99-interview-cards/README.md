# 99 · 面试卡 —— Python 并发高频题速查

> 把全课浓缩成面试可直接背的答案。深题拆成独立卡（链回章节做证据），其余用下面的「速答表」。

## 卡片索引

- [GIL 是什么 / 为什么 / 何时释放](q-gil.md)
- [线程 / I/O / event loop：谁是系统线程，谁在并行](q-thread-io-event-loop.md)
- [asyncio 和 goroutine 的区别](q-asyncio-vs-goroutine.md)
- [并发模型选型：CPU 密集还是 I/O 密集](q-model-selection.md)
- [为什么 Python Web 服务要多 worker](q-why-workers.md)

## 速答表（一行一条，背诵用）

| 问题 | 一句话答案 |
|---|---|
| Python 多线程能用多核吗 | CPU 密集不能（GIL 同一刻只一个线程跑字节码）；I/O 密集能（I/O 时释放 GIL）。见 [01](../01-foundations-gil/) |
| Python 线程是假线程吗 | 不是。`threading.Thread` 通常是真 OS 线程，只是执行 Python 字节码前要抢 GIL。见 [线程/I/O卡](q-thread-io-event-loop.md) |
| I/O 线程和 Python 线程是同一个吗 | 阻塞 I/O 常常就是同一个 OS 线程进入 syscall；也可能有应用层 I/O 线程、库线程或内核 worker。见 [线程/I/O卡](q-thread-io-event-loop.md) |
| 线程等 I/O 时还能并行吗 | I/O 与另一个线程执行字节码可以重叠；若线程在 kernel/native 代码里跑且已释放 GIL，也可能是真 CPU 并行。见 [线程/I/O卡](q-thread-io-event-loop.md) |
| 有 GIL 还要加锁吗 | 要。`x+=1` 是多条字节码，中间可能切走丢更新，同 Java `i++`。见 [01](../01-foundations-gil/) |
| GIL 何时释放 | 阻塞 I/O、sleep、等锁、C 扩展显式释放、纯算每约 5ms 检查一次 |
| CPU 密集怎么做 | multiprocessing 多进程绕 GIL，或 numpy 向量化（释放 GIL）。见 [03](../03-multiprocessing/) |
| `Lock` vs `RLock` | RLock 可重入（同线程可多次 acquire），Lock 不可。见 [02](../02-threading/) |
| Python 有 AtomicInteger 吗 | 标准库没有，用 `Lock` 保护读改写。见 [02](../02-threading/) |
| 怎么优雅停线程 | 不能外部杀，用 `Event` 标志位轮询；阻塞调用带 timeout。见 [02](../02-threading/) |
| `ThreadPoolExecutor` 队列满了 | 不拒绝，无界堆积；限流自己加 Semaphore。见 [02](../02-threading/) |
| fork vs spawn | fork 复制内存(Linux默认)；spawn 重启解释器重 import(mac/Win默认)，必加 `__main__` 守卫。见 [03](../03-multiprocessing/) |
| 进程间传大数据 | shared_memory 零拷贝，或各进程自读，或 numpy 向量化避免开进程。见 [03](../03-multiprocessing/) |
| 单线程 asyncio 为何高并发 | 事件循环 + 不阻塞：发 I/O 就让出，epoll 多路复用监听上万 socket。见 [04](../04-asyncio-core/) |
| coroutine / Task / event loop 怎么对应 | coroutine 是可暂停函数状态，Task 是调度包装，event loop 是跑在 OS 线程里的调度循环。见 [线程/I/O卡](q-thread-io-event-loop.md) |
| 写了 async 就并发了吗 | 不。`await a();await b()` 是串行；并发要 `gather`/`TaskGroup`/`create_task`。见 [04](../04-asyncio-core/) |
| 为什么 sleep(1) 拖垮异步服务 | 同步阻塞冻结单线程事件循环，所有连接一起卡；用 `await asyncio.sleep`。见 [05](../05-asyncio-pitfalls/) |
| 协程里必须用同步库怎么办 | `run_in_executor`：I/O 丢线程池、CPU 丢进程池。见 [05](../05-asyncio-pitfalls/) |
| 什么是函数染色 | async 传染整条调用链；Go 无此问题。应 async 到底或全同步。见 [05](../05-asyncio-pitfalls/) |
| anyio 是什么 | 架在 asyncio 上的结构化并发高层 API，FastAPI 底层用它丢同步路由进线程池。见 [06](../06-anyio/) |
| WSGI vs ASGI | WSGI 同步(Flask/Django+gunicorn)；ASGI 异步事件循环(FastAPI+uvicorn)。见 [07](../07-prod-web-workers/) |
| worker 配几个 | 同步≈2×核数+1；异步(uvicorn)≈核数；压测定。见 [07](../07-prod-web-workers/) |
| `--max-requests` 干嘛 | worker 处理 N 个请求后重启，缓解内存泄漏。见 [07](../07-prod-web-workers/) |
| 为什么要任务队列 | 把耗时/可异步/可重试的活剥离请求，接口快返回 + 重试/定时。见 [08](../08-prod-task-queues/) |
| Celery pool 怎么选 | CPU 密集 prefork、I/O 密集 threads/gevent——还是那个老问题。见 [08](../08-prod-task-queues/) |
| 任务为什么要幂等 | 重试/重投会多次执行，必须能安全重复。见 [08](../08-prod-task-queues/) |
| 多 worker 下连接池注意啥 | 总连接 = 单池×worker数×机器数，易打满 DB max_connections。见 [09](../09-patterns-tuning/) |
| 并发抓取怎么防打挂 | Semaphore 限流 + 连接池 + 超时 + 指数退避重试。见 [09](../09-patterns-tuning/) |
| 怎么定位并发瓶颈 | py-spy 看栈/热点、asyncio debug 看门狗、压测看 P99 拐点。见 [09](../09-patterns-tuning/) |
