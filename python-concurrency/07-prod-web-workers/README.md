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

### 3.4 深入：四种模型在回答同一个问题 + gthread vs gevent 怎么选

四种 worker 模型（sync / gthread / gevent / async）本质都在回答同一个问题——**「单个请求等 I/O 的那段时间，怎么别让 CPU/进程白闲着？」**——只是在不同层次、用不同轻重的「并发单位」去隐藏这段等待：

| 模型 | 隐藏 I/O 的单位 | 怎么让出 | 单 worker 并发 | 调度 |
|---|---|---|---|---|
| **sync** | 进程（worker 内不隐藏） | 不让出，靠多开进程跨进程顶 | 1 | 内核 |
| **gthread** | OS 线程 | 阻塞 syscall 时 CPython **放 GIL**，别的线程抢 | 几十 | 内核（抢占式） |
| **gevent** | greenlet | monkey-patch 把阻塞调用换成「注册 fd + 切 greenlet」 | 上千 | 进程内 hub（协作式） |
| **async** | 协程 | 显式 `await` 让出事件循环 | 上千 | 进程内事件循环（协作式） |

> 一条线索：**隐藏 I/O 的单位越往下越轻**（进程 → 线程 → greenlet → 协程），单 worker 能塞的并发越多，但对代码和依赖的要求也越高。sync 要 `2×核数` 个进程，正因为它在 worker 内**根本不隐藏 I/O**，只能跨进程顶（这就是第 4 节那条 `N×(1+W/C)` 公式的来历）。Go 的 goroutine 是「运行时层面把这件事做绝」，所以你在 Go 里从不手配这些数。

中间的 gthread / gevent 最容易混。它俩都是**「不想把代码重写成 async，但想让单个 worker 扛更多并发 I/O」**的方案，差别在并发单位和代价：

**gthread —— 用真 OS 线程**
- 每个 worker 开 `--threads N` 个内核线程，**抢占式**调度。
- 隐藏 I/O 靠 GIL：线程做阻塞 syscall（socket/DB）时 CPython 自动释放 GIL，别的线程拿到 GIL 接着跑；I/O 回来再抢 GIL。
- **不用改代码、不挑库**：任何阻塞库、任何 C 扩展都正常工作——这是它最大的优点，省心、不会有奇怪的坑。
- 天花板：几十个线程。线程栈占内存、切换走内核、加上 GIL 争用，撑不到上千。
- 注意：GIL 让单 worker **只有 I/O 并发、没有 CPU 并行**；CPU 并行还是靠多进程。

**gevent —— 用 greenlet + monkey-patch**
- 每个 worker 就一个 OS 线程，跑一个事件循环（hub）调度成千上万个 greenlet，**协作式**。
- 隐藏 I/O 靠 `monkey.patch_all()`：它**偷偷替换**标准库的阻塞函数（socket/ssl/`time.sleep`…），你那句「阻塞」的 `recv()` 实际会把 fd 注册到事件循环、切去别的 greenlet。
- greenlet 极轻（KB 级栈、进程内切换），所以单 worker 能扛**上千连接**。
- 代价是**脆弱**：
  - `monkey.patch_all()` 必须在所有 import 之前第一个跑，否则有模块抓到没打补丁的旧函数 → 半阻塞、卡死。
  - **C 扩展不走 Python socket，patch 不到** → 它一阻塞就卡死整个事件循环、饿死同 worker 所有连接。常见雷：C 版 DB 驱动（要换 gevent 兼容的，如 `psycopg2`+`psycogreen`、`PyMySQL`）、grpc 等。
  - **CPU 重活卡死所有连接**：协作式没抢占，一个 greenlet 算 200ms 不让出，这个 worker 上千连接全冻住。
  - 难调试：栈、profiler、debugger 跟 greenlet 配合都怪。

**怎么选（一句话）**
- **默认 gthread**：中等 I/O 并发（几十）、要稳、依赖里有 C 扩展、不想踩 monkey-patch 坑。`--threads 4~16` 覆盖绝大多数同步服务。
- **gevent**：单机要扛**上千并发慢 I/O / 长连接**（大量慢下游、SSE/长轮询、扇出爬取），且你能保证整条依赖链 gevent 兼容、worker 内没有 CPU 重活。是「为极高 I/O 并发付出脆弱性」的选择。
- **能改代码就别在这俩里纠结**：它俩都是过渡方案。真要高并发 I/O，正路是迁到 ASGI/async（FastAPI）——gevent 是「给同步代码偷装一个 asyncio」，async 是「明着用」，明着的可控、可调、可观测得多。

---

## 4. 日常开发应用：worker 数怎么定

**这是面试和实战的核心数字题。** 分两种世界：

### 同步（WSGI：Flask/Django + gunicorn）

- **sync worker 数**：经验公式 **`(2 × CPU核数) + 1`**。比如 4 核 → 9 个 worker。
  - **`2×` 不是「多备 1 个」，而是「worker 总数 ≈ 核数的两倍」**：sync worker 一次只处理 1 个请求且整段真阻塞，单个 worker 没法在内部隐藏 I/O。所以靠「进程数多于核数」跨进程隐藏——稳态下默认约**一半 worker 卡在 I/O（等 DB/读写 socket），另一半正好吃满核**。
  - 它其实就是线程池经典公式 **`N = 核数 × (1 + W/C)`**（W=等待时间，C=占 CPU 时间）在 **`W/C = 1`（I/O 时间≈CPU 时间）** 时的特解。`+1` 只是边界冗余。
  - **所以它写死了一个 50/50 的 I/O 假设，比值不对就翻车**：I/O 偏重（如 20ms CPU+80ms DB，`W/C=4`）→ 需要 `4×(1+4)=20` 个才打满 CPU，9 个严重欠配；纯 CPU（`W/C≈0`）→ 只需 ≈核数，9 个反而抢核+多占内存。I/O 占比高时正解是上 gthread/gevent/async（让单 worker 内部也能多路复用，回到 Go runtime 那种自动隐藏 I/O 的模型），而不是继续堆 sync 进程。
  - 真正的数字：用 Little 定律 `并发 L = 吞吐 λ × 单请求耗时 W` 定下限，再用 `核数×(1+W/C)` 卡 CPU 这头。`2×+1` 是没有压测数字时、针对「普通 DB-backed web 接口」的开局默认值。
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
起点：同步 sync ≈ `2×核数+1`、gthread ≈ 核数+多线程、异步（uvicorn）≈ 核数。**但直接背这个数是初级答法**——这是资历过滤题，资深要把「数字」换成「方法」：

> 「`2×核数+1` 是没数据时的配置起点。真正定数我会：① 先问 CPU-bound 还是 I/O-bound、SLO 多少；② 用 Little 定律 `并发=吞吐×延迟` 估下限，再用 `核数×(1+W/C)` 卡 CPU 这头；③ 压测（k6/locust）盯 **p99 延迟**和 **CPU 利用率**找拐点——CPU 没满但延迟烂就是 worker 不够，CPU 满了加 worker 没用得优化/横扩；④ 最后取 **CPU、内存、下游连接数**里最紧的那个约束。`worker×连接池 ≤ DB max_connections` 经常才是真天花板（Q7）。」

两个加分点：**容器里 `cpu_count()` 返回宿主机核数不是 cgroup limit**，靠 `$(nproc)` 自动检测会开爆 worker，必须显式钉死；**流量大不拧单机，交给 HPA 按 CPU/延迟横向扩 Pod**。再反问一句「I/O 重还是 CPU 重？SLO 多少？跑容器吗？」基本就过了。详见第 4 节 `N×(1+W/C)` 推导与第 09 章压测/连接池。

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
