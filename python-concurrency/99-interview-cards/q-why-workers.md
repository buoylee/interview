# 为什么 Python Web 服务要多 worker（Java 为什么不用）

## 一句话回答

单个 Python 进程受 GIL 限制吃不满多核，所以线上靠**多 worker 进程**（每个一把独立 GIL，合起来吃满多核）+ 故障隔离来扩展。Java 单进程多线程就能吃满多核，所以很少需要这种多进程 worker 形态——这是 GIL 给部署架构带来的最直接差异。

## 三层论证

1. **GIL → 单进程吃不满多核**：一个 Python 进程同一刻只有一个线程跑字节码，4 核机器上单进程最多用满 1 核的计算能力。要用满 4 核，就得起多个进程。
2. **多 worker = 多进程**：gunicorn/uvicorn 起 N 个 worker 进程，master 只负责拉起/监控/重启它们（worker 崩了补一个，故障隔离）。每个 worker 内部再用线程（gthread）/协程（gevent）/事件循环（uvicorn）处理并发请求。
3. **对标 Java**：gunicorn 多 worker ≈ 起多个 JVM 实例 + 前面挂负载均衡；worker 内并发 ≈ 一个 Tomcat 进程的线程池。Java 一个进程吃满多核，所以一个 Tomcat 就够，不必多进程。

## 证据链接

- 章节原理：[07-prod-web-workers §2](../07-prod-web-workers/README.md)
- GIL 根因：[01-foundations-gil §3](../01-foundations-gil/README.md)

## 易追问的延伸

- **Q: worker 配几个？** → 同步（gunicorn sync）≈ 2×核数+1；异步（uvicorn）≈ 核数（单事件循环已能高并发）；最终压测定。
- **Q: worker 多了有什么代价？** → 每个 worker 是独立进程、独立内存，N 个 worker ≈ N 份内存；且每个有独立连接池，总连接 = 池大小×worker数，易打满数据库。
- **Q: 怎么缓解 worker 内存泄漏？** → `--max-requests N`（处理 N 个请求后自动重启 worker）+ jitter 错开重启。
- **Q: 异步服务为什么 worker 少？** → 单个 uvicorn worker 就是一个事件循环，能并发处理海量连接，worker 数只为吃满多核（≈核数），不是为并发量。
