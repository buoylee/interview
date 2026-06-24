# 07 · 生产① Web Worker —— Python 服务线上到底怎么跑

> 这是你说「完全没概念」的部分，也是面试高频。前面六章讲的进程/线程/协程，到这一章会拼成你每天 `gunicorn ... --workers 4` 背后的完整图景。读完你能回答：FastAPI/Django/Flask 线上怎么部署、worker 是什么、几个 worker、每个 worker 内部怎么处理并发。
>
> 前置：第 01 章（GIL）、02（线程）、03（多进程）、04（asyncio）。

---

## 1. 核心问题

1. WSGI 和 ASGI 是什么？为什么有这个分裂？
2. gunicorn 的 master/worker 是什么？worker 又分几种？
3. Flask、Django、FastAPI 线上各自怎么跑？命令长什么样？
4. worker 配几个、每个几线程？凭什么定？

---

## 2. 直觉理解

### 2.1 一句话回顾「为什么要多 worker」

第 01 章证明过：**单个 Python 进程受 GIL 限制，吃不满多核。** 所以线上的标准做法是：

> **起多个 worker 进程**（每个一把独立 GIL，合起来吃满多核）+ **每个 worker 内部再用线程或事件循环**处理并发请求。

```
            ┌─────────── 一台 4 核机器 ───────────┐
 Nginx ───▶ │  gunicorn master（不处理请求，只管 worker）│
（负载均衡） │     ├── worker 进程 1  ┐                  │
            │     ├── worker 进程 2  ├ 各自独立 GIL，    │
            │     ├── worker 进程 3  │ 真正处理请求       │
            │     └── worker 进程 4  ┘                  │
            └────────────────────────────────────────┘
```

- **worker 数 ≈ 进程数** → 解决「吃多核」。
- **worker 内部的线程/协程** → 解决「单个 worker 内的并发」。
- **master 进程**：本身不处理请求，只负责拉起、监控、重启 worker（worker 崩了它补一个）。

> 对标 Java：gunicorn 多 worker ≈ 起多个 JVM 实例 + 前面挂 Nginx 负载均衡；单个 worker 内部的并发 ≈ 一个 Tomcat 进程里的线程池。Java 一个进程就能吃满多核，所以很少这么玩；Python 因 GIL 必须靠多进程凑。**这是 GIL 给部署架构带来的最直接差异。**

#### 2.1.1 那「单个 worker 到底用几个核」？

初学最容易卡的具体问题，一句话回答：**单个 worker（= 一个进程）会在多个核之间跳，但同一瞬间只占一个核。**

- **会跳核**：内核调度器不会把 worker 钉在固定核上，它这会儿在核 0、待会儿可能被排到核 3（线程迁移）。所以「单 worker 只能用某一个核」是错的。
- **但封顶一核**：受 GIL，这个进程同一瞬间只有一条线程能跑 Python 字节码 → 吞吐封顶在「一个核」。`--workers 4` 才是 **4 个进程、4 把 GIL、同时占 4 个核**，这才真吃满多核。

`top` 直接验证：单 worker 灌满负载，CPU% 顶到 **~100%**（一个核满，尽管它在跳核）；`--workers 4` 能到 **~400%**。

> 「跳核 ≠ 同时用多核」的机制详解见 [00 章 A.2.1](../00-execution-model/README.md)。也正因封顶一核，**异步 worker 数起手 ≈ 核数**——每个 worker 内部靠事件循环已能扛海量并发，堆 worker 数只为吃满核，不是为提单机并发。

### 2.2 WSGI vs ASGI（先分清这个，才懂 worker）

这是 Python Web 的根本分裂，决定了你能用同步还是异步：

| | WSGI | ASGI |
|---|---|---|
| 全称 | Web Server Gateway Interface | Asynchronous Server Gateway Interface |
| 模型 | **同步**：一个请求占一个 worker/线程直到处理完 | **异步**：基于 asyncio 事件循环，一个 worker 并发处理大量请求 |
| 协议 | 只支持 HTTP 请求-响应 | HTTP + WebSocket + 长连接 |
| 代表框架 | Flask、Django（传统）、旧框架 | **FastAPI**、Starlette、Django（3.0+ 异步部分） |
| 典型服务器 | **gunicorn**、uWSGI | **uvicorn**、hypercorn、daphne |

> 心智：**WSGI = 同步世界（靠多进程多线程堆并发），ASGI = 异步世界（靠事件循环堆并发）。** 你的框架属于哪边，决定了你用哪种服务器和 worker。

---

## 3. 原理深入

### 3.1 gunicorn 的 worker 类型（WSGI 世界）

gunicorn 是 WSGI 服务器，它的精髓是 **worker class**——决定「每个 worker 内部怎么处理并发」：

```bash
# ① sync worker（默认）：每个 worker 进程一次只处理一个请求
gunicorn app:wsgi --workers 4 --worker-class sync
#   → 4 个请求并发上限。简单、稳，但 worker 在等 I/O 时整个闲着。
#   → 适合：CPU 偏重、或请求很快的服务。

# ② gthread worker：每个 worker 内开一个线程池
gunicorn app:wsgi --workers 4 --worker-class gthread --threads 8
#   → 并发上限 ≈ 4 × 8 = 32。worker 等 I/O 时（放 GIL）线程能处理别的请求。
#   → 适合：I/O 偏重的同步应用。这是同步框架扛并发的常用配置。

# ③ gevent / eventlet worker：每个 worker 用协程（monkey-patch 把阻塞调用变协作式）
gunicorn app:wsgi --workers 4 --worker-class gevent --worker-connections 1000
#   → 单 worker 能扛上千并发连接。靠 gevent 把 socket 等阻塞操作偷偷换成协程让出。
#   → 适合：高并发 I/O 的同步应用（不想重写成 async，但要高并发）。
```

> gevent 是什么：一个用「绿色线程（greenlet）」+ monkey-patch 实现协程的库。它**在不改你同步代码的前提下**，把标准库的阻塞 I/O 替换成协作式让出——相当于给同步代码「偷偷加上 asyncio 的好处」。Celery、老项目里很常见（第 08 章还会见到）。

### 3.2 uvicorn（ASGI 世界）

uvicorn 是 ASGI 服务器，**每个 worker 内部就是一个 asyncio 事件循环**（第 04 章那套）：

```bash
# uvicorn 直接起，多 worker
uvicorn app:asgi --workers 4
#   → 4 个进程，每个进程一个事件循环。
#   → 每个事件循环本身就能并发处理海量连接（第 04 章），所以 worker 数 ≈ 核数即可。

# 生产常见：gunicorn 当 master（进程管理更成熟）+ uvicorn worker 干活
gunicorn app:asgi --workers 4 --worker-class uvicorn.workers.UvicornWorker
#   → 兼得 gunicorn 的进程管理 + uvicorn 的 ASGI 事件循环。经典生产组合。
```

> 注意区别：sync worker 是「1 worker = 1 并发请求」；uvicorn worker 是「1 worker = 1 事件循环 = 海量并发请求」。所以**异步服务的 worker 数远少于同步服务**。

### 3.3 三个框架线上怎么跑（直接抄）

```bash
# Flask（WSGI，同步）—— I/O 偏重用 gthread
gunicorn "myapp:app" --workers 4 --worker-class gthread --threads 8 --bind 0.0.0.0:8000

# Django（WSGI，同步）—— 同上；ASGI 模式（用了 async view/channels）则走 uvicorn
gunicorn "myproject.wsgi:application" --workers 4 --threads 4 --bind 0.0.0.0:8000

# FastAPI（ASGI，异步）—— uvicorn worker
gunicorn "myapp:app" --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
# 或直接 uvicorn（开发/简单部署）
uvicorn myapp:app --workers 4 --host 0.0.0.0 --port 8000
```

---

## 4. 日常开发应用：worker 数怎么定

**这是面试和实战的核心数字题。** 分两种世界：

### 同步（WSGI：Flask/Django + gunicorn）

- **sync worker 数**：经验公式 **`(2 × CPU核数) + 1`**。比如 4 核 → 9 个 worker。这个「2×」是为了在 worker 等 I/O 时还有别的 worker 能用 CPU。
- **gthread**：worker 数可降到接近核数，靠 `--threads` 补并发。总并发 ≈ workers × threads。
- 别无脑堆 worker：每个 worker 是独立进程、独立内存，N 个 worker ≈ N 份内存占用。

### 异步（ASGI：FastAPI + uvicorn）

- **worker 数 ≈ CPU 核数**（不用 2×）。因为单个事件循环已经能并发处理海量请求，worker 多了只为吃满多核，不是为了并发量。
- 前提：**代码真的 async 到底、不阻塞循环**（第 05 章）。否则事件循环被卡，多少 worker 都白搭。

### 一句话决策

| 框架/场景 | 服务器 + worker | worker 数起点 |
|---|---|---|
| Flask/Django，CPU 偏重 | gunicorn sync | 2×核数+1 |
| Flask/Django，I/O 偏重 | gunicorn gthread | ≈核数，threads 补 |
| Flask/Django，超高并发 I/O 不想改 async | gunicorn gevent | ≈核数，connections 调大 |
| FastAPI / 异步 | uvicorn / gunicorn+uvicorn worker | ≈核数 |

> 真正的数字要压测定（第 09 章），公式只是起点。

---

## 5. 生产 & 调优实战

几个一定要知道的生产参数和坑：

- **`--timeout`**：worker 处理一个请求超过这个秒数（默认 30s），master 会**杀掉并重启**它。CPU 重活或慢接口要调大，否则 worker 被反复杀。注意：sync worker 的 timeout 是「单请求墙钟时间」。
- **`--max-requests` + `--max-requests-jitter`**：每个 worker 处理 N 个请求后自动重启。**用来缓解内存泄漏**（Python 长跑进程内存只增不减时，定期重启 worker 回收）。jitter 加随机避免所有 worker 同时重启。
- **`--preload`**：master 先 import 应用再 fork worker，省内存（COW 共享）、加快启动；代价是改代码要重启 master，且 fork 后某些资源（DB 连接、随机种子）要小心在 worker 里重建。
- **优雅重启/热重载**：`kill -HUP <master_pid>` 让 gunicorn 滚动重启 worker（不中断服务）；`--reload` 仅开发用。
- **每个 worker 独立资源**：数据库连接池、缓存、全局状态在每个 worker 里各有一份。**「连接池大小 × worker 数」才是对数据库的总连接数**——这是压垮数据库的经典原因（第 09 章连接池）。
- **worker 内并发模型要和代码匹配**：async 框架（FastAPI）必须配 uvicorn/ASGI worker，错配成 sync worker 会让异步代码退化成串行甚至报错。

---

## 6. 面试高频考点

**Q1：WSGI 和 ASGI 区别？**
WSGI 是同步接口（一个请求占一个 worker/线程到完成，代表 Flask/Django + gunicorn）；ASGI 是异步接口（基于事件循环，一个 worker 并发处理海量请求，支持 WebSocket，代表 FastAPI + uvicorn）。

**Q2：为什么 Python Web 服务要多 worker？Java 为什么不用？**
单 Python 进程受 GIL 限制吃不满多核，多 worker（多进程）才能利用多核 + 故障隔离。Java 单进程多线程即可吃满多核，所以不需要这种多进程 worker 形态。

**Q3：gunicorn 的 worker 类型有哪些，怎么选？**
sync（1 worker 1 请求，简单/CPU 偏重）、gthread（worker 内线程池，I/O 偏重）、gevent/eventlet（协程，超高并发 I/O）、uvicorn worker（跑 ASGI 异步应用）。按 CPU/IO 比重和是否异步来选。

**Q4：worker 配几个？**
同步 sync ≈ 2×核数+1；gthread ≈ 核数 + 多线程；异步（uvicorn）≈ 核数（单事件循环已能高并发）。最终靠压测定。

**Q5：`--max-requests` 干嘛的？**
让 worker 处理 N 个请求后自动重启，缓解内存泄漏（长跑进程内存不释放）。配 jitter 避免同时重启。

**Q6：FastAPI 配 sync worker 会怎样？**
错配。异步应用需要 ASGI/uvicorn worker，配成普通 sync WSGI worker 会让事件循环跑不起来或异步代码退化，性能崩塌。

**Q7：每个 worker 都有独立的数据库连接池吗？对数据库有什么影响？**
是。总连接数 = 每 worker 连接池大小 × worker 数（× 机器数）。配置不当极易打满数据库连接上限，是常见生产事故。

---

## 7. 一句话总结

Python 服务线上 = **多 worker 进程（绕 GIL 吃多核 + 故障隔离）+ 每个 worker 内部用线程(gthread)/协程(gevent)/事件循环(uvicorn)处理并发**。先分清框架是 WSGI（同步，gunicorn）还是 ASGI（异步，uvicorn）；worker 数同步约 2×核数+1、异步约核数；再配好 timeout / max-requests / 连接池总量。这就是你每天那行启动命令背后的全部逻辑。

---

> **下一章** `08-prod-task-queues/`：请求-响应之外的另一半生产——Celery 等任务队列怎么跑后台/定时任务。
>
> **延伸**：连接池总量与压测调优见第 09 章；Web 框架调优见 `performance-tuning-roadmap/06b-python-debugging/03-web-framework-tuning.md`。
