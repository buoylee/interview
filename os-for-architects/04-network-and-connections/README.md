# 04 · 网络/连接 → 连接模型与容量

> **本章契约**：薄镜头，不重教网络机制，不展开 TCP 状态机，不建实验。看到"连接 = fd + 缓冲 + 队列"这条原语，反射出设计期要做的决策，然后指你进深矿。

---

## 一、盲点

你在这一层的能力，几乎全是**事后解释**：CLOSE_WAIT 堆积了就重启、TIME_WAIT 多了就调 `tcp_tw_reuse`、端口耗尽了就 kill 进程。这是**被问题追着跑**。

架构师在另一头：**还没写连接逻辑时，就从"一个连接消耗多少内核资源"反推出连接池大小、长连还是短连、backlog 和超时怎么设**，让那些运维问题根本不出现。

一句点破：资深在连接坏掉之后解释，架构师在写第一行连接代码之前设计。

---

## 二、原语 → 决策映射表

| OS 原语 | 资深·能答（反应式） | 架构师·能设计（预判式） |
|---|---|---|
| 连接 = fd + 内核发/收缓冲 + TCP 状态队列 | "CLOSE_WAIT / TIME_WAIT 堆积，定位到没关连接或主动关连接方" | 设计期算好：长连 vs 短连、连接池复用、fd 上限和池大小；让 CLOSE_WAIT 根本无法堆积 |
| epoll / reactor 事件驱动 | "C10K 问题，用 epoll 能撑高并发" | 选型判断：IO 密集 + 高并发 → reactor 单线程/小线程池；CPU 密集 → 线程每连接；混合场景 → 多 reactor；**在架构阶段定下来，不是优化阶段** |
| backlog / accept queue 半连接+全连接队列 | "队列满了丢连接，`net.core.somaxconn` 调大" | 设计时量化：backlog = 峰值 QPS × RTT（秒）；不设 → 流量尖刺静默丢包；配合限流/背压让队列可见而非静默溢出 |
| 端口号 / fd 数量上限 | "端口耗尽，`ss -s` 看 TIME_WAIT；fd 超 ulimit 报 too many open files" | 客户端侧：连接池复用源端口；规划 `ulimit -n`（每连接 1 fd）、本地端口范围 `ip_local_port_range`；多实例部署时 fd 总量 = 池大小 × worker 数，提前核算 |

---

## 三、定量锚点

**连接池大小**用 Little 定律一句话反射：

```
池大小（并发连接数） = QPS × 平均响应时延（秒）
```

例：10,000 QPS，响应 P99 = 20 ms → 池大小 ≈ 10000 × 0.02 = **200 个连接**。
小于这个值 → 请求排队等连接，延迟升高；远大于这个值 → 浪费 fd 和内核缓冲。

完整推导（含候补队列、超时、连接回收节拍）→ [`../../concurrency-capacity/05-pools/`](../../concurrency-capacity/05-pools/)

**fd 上限规划**：每条 TCP 连接占 1 fd；单进程 `ulimit -n`（常见默认 1024）是容量硬墙。容量 = 连接池大小 + 监听 fd + 文件 fd，至少设为 **4 倍峰值连接数**留余量。

---

## 四、决策清单 & 反模式

### 设计时该问的问题

- 这个服务是 IO 密集还是 CPU 密集？混合？→ 决定用 reactor 还是线程每连接。
- 客户端到这个服务的 QPS + 平均延迟是多少？→ 算连接池大小。
- 连接是长连（keep-alive）还是短连（每请求新建）？→ 影响 TIME_WAIT 规模和 fd 占用。
- backlog 设了多少？有没有在流量峰值时监控 accept queue overflow？
- 超时有没有设？connect timeout / read timeout / idle timeout 三条都要有。
- fd ulimit 和本地端口范围有没有核算到峰值容量？

### 反模式（至少三条）

| 反模式 | 后果 | 正解 |
|---|---|---|
| **每请求新建连接** | 大量 TIME_WAIT 堆积，端口耗尽，连接建立延迟（TCP 三次握手 + TLS 握手）叠加到业务延迟 | 连接池 + 长连接；gRPC/HTTP/2 天然复用 |
| **连接池大小拍脑袋**（固定写 10 / 100） | 池太小 → 等连接排队；池太大 → fd 超 ulimit crash；两头都崩 | Little 定律先算，再观测调参，不要靠经验猜 |
| **不设超时，任连接堆积** | 下游慢或断开 → 上游线程/goroutine 永久阻塞持有连接 → 池耗尽 → 雪崩 | connect / read / idle 三个超时都要设；配合 circuit breaker |
| **backlog 不设 / 用默认** | 流量尖刺时半连接队列溢出，静默丢包，表现为神秘超时；开发环境从不复现 | backlog = 峰值 QPS × RTT，至少 1024；配限流保护上游 |

---

## 五、指针

### 下指（机制）

- 网络机制 + 排查 lab → [`../../linux-handson/06-networking/`](../../linux-handson/06-networking/)
- TCP 核心（状态机、TIME_WAIT、拥塞控制）→ [`../../performance-tuning-roadmap/00-os-fundamentals/04a-network-tcp-core.md`](../../performance-tuning-roadmap/00-os-fundamentals/04a-network-tcp-core.md)
- Socket 内核路径（缓冲、队列、epoll 实现）→ [`../../performance-tuning-roadmap/00-os-fundamentals/04b-network-socket-kernel.md`](../../performance-tuning-roadmap/00-os-fundamentals/04b-network-socket-kernel.md)

### 横指（深决策）

| 主题 | 深矿 |
|---|---|
| 连接池完整容量推导 + Little 定律 | [`../../concurrency-capacity/05-pools/`](../../concurrency-capacity/05-pools/) |
| 过载保护 / 背压设计 | [`../../concurrency-capacity/07-overload-backpressure/`](../../concurrency-capacity/07-overload-backpressure/) |
| 连接池架构决策（架构师深度） | [`../../performance-tuning-roadmap/11-architecture/02-connection-pooling.md`](../../performance-tuning-roadmap/11-architecture/02-connection-pooling.md) |
| 异步 / reactor 架构选型 | [`../../performance-tuning-roadmap/11-architecture/03-async-reactive.md`](../../performance-tuning-roadmap/11-architecture/03-async-reactive.md) |
| 服务化通信范式（长连、流、协议选型） | [`../../system-design/04-服務化與通信範式.md`](../../system-design/04-服務化與通信範式.md) |

---

## 六、面试转化

面试里这类题往往先问"能答"再追"能设计"。下面每题给两层：

---

**题一：连接池大小怎么定？**

- **能答（资深）**：调大或调小 `max_pool_size`，看数据库连接数告警来决定。
- **能设计（架构师）**：Little 定律：`并发连接 = QPS × 延迟（秒）`；再加 20% 余量做缓冲；用监控确认池等待队列长度（若 wait_count 持续 > 0 说明池不够）；同时算 fd ulimit 是否够用。超过数据库 max_connections 上限时，在应用侧加限流或拆分读写池。

---

**题二：为什么用长连接？TIME_WAIT 堆积怎么设计避免？**

- **能答（资深）**：TIME_WAIT 是主动关闭方等 2MSL，防止旧包干扰新连接；开 `tcp_tw_reuse` 可以复用。
- **能设计（架构师）**：根本解法是**不频繁主动关闭连接** —— 长连接 + 连接池，让 TIME_WAIT 的产生频率从"每请求"降到"池缩容时"；客户端主动关闭 → TIME_WAIT 在客户端（好的）；若服务端主动关闭（坏的），改为让客户端主动断；高 QPS 场景用 HTTP/2 或 gRPC 彻底消掉单次请求的连接创建开销。`tcp_tw_reuse` 是运维补丁，不是设计答案。

---

**题三（加分）：如何为一个高并发微服务规划网络容量？**

- 列出：峰值 QPS → 计算连接池大小（Little）→ 核算 fd ulimit → 设 backlog → 设三个超时 → 配置 circuit breaker + 背压 → 监控 accept queue overflow + 连接池 wait_count。能把这条链说完，就是在"设计"而不在"救火"。
