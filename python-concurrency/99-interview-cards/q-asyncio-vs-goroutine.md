# asyncio 和 goroutine 的区别

## 一句话回答

写法像，本质完全不同：**goroutine 是 Go runtime 在多个 OS 线程上抢占式调度、能真并行的轻量线程；asyncio 是单线程上协作式调度的事件循环、不能并行。** goroutine 阻塞一个不影响别的，asyncio 一个阻塞操作会冻结整个循环。

## 对比表

| | Go goroutine | Python asyncio |
|---|---|---|
| 线程数 | 多个 OS 线程（M:N） | 单个（一个事件循环） |
| 调度 | 抢占式（runtime 强制切换） | 协作式（只在 `await` 处让出） |
| 并行 | 真并行，吃多核 | 并发不并行，单核 |
| 阻塞一个任务 | 别的照跑 | 整个循环冻结 |
| 阻塞调用 | runtime 透明处理 | 必须显式 `await` + 用 async 库 |
| 函数染色 | 无 | 有（async 传染调用链） |

## 三层论证

1. **调度模型**：goroutine 由 Go runtime 自动在 GOMAXPROCS 个 OS 线程上调度，自 Go 1.14 起还能异步抢占；asyncio 只有一个线程，切换点完全由你写的 `await` 决定（协作式）。
2. **并行能力**：goroutine 能真正同时在多核上跑；asyncio 单线程，要利用多核必须叠多进程/多 worker（每 worker 一个事件循环）。
3. **阻塞的后果**：goroutine 里一个慢调用只影响该 goroutine；asyncio 里一个同步阻塞调用冻结整个事件循环、拖垮所有并发连接——这是 asyncio 最大的运维风险。

## 证据链接

- 章节原理：[04-asyncio-core §2.3](../04-asyncio-core/README.md)
- 阻塞陷阱：[05-asyncio-pitfalls](../05-asyncio-pitfalls/README.md)

## 易追问的延伸

- **Q: 那 asyncio 更像什么？** → 更像 Node.js 的事件循环：单线程、协作式、靠不阻塞撑高并发。
- **Q: 为什么 Go 没有函数染色？** → goroutine 透明，你写普通同步代码、runtime 在底层切换；Python 的 async/await 是显式语法，所以会沿调用链传染。
- **Q: asyncio 怎么利用多核？** → 它自己不行，靠 `uvicorn --workers N`（多进程，每进程一个事件循环）+ GIL 隔离来吃多核。
- **Q: Python 有没有类似 goroutine 的东西？** → 最接近的是「多 worker × 每 worker 事件循环」的组合；语言层面 3.13 的 free-threaded + 协程是未来方向，但还不等价。
