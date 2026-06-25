# 应用级资源饱和监控(跨语言 capstone + 三薄落地)— 设计

日期:2026-06-25
状态:设计已与用户对齐,待 spec review

## 一、缘起与问题

用户在读 `fastapi-ops/` 时提出:生产级 FastAPI 项目到底需不需要在 app 层监控线程池,还是系统层就够?
延伸为更一般的问题:**真实生产环境该如何监控「并发与运行时资源」**,并希望覆盖 Python/Java/Go 三语言(用户自评 Java/Go 这块也不扎实)。

### 全仓审计结论(6 个并行 Explore 子代理,覆盖 ~30 个 track)

把主题拆成三层:

| 层 | 现状 | 权威归宿(不重造) |
|---|---|---|
| ① 方法论(USE/RED/黄金信号、饱和=领先指标、×worker 总账) | 🟢 很完整 | `performance-tuning-roadmap/01-methodology/02-use-method.md`(USE)、`/03-red-golden-signals.md`(RED)、`concurrency-capacity/08-monitoring-concurrency`(饱和领先 + L=λW + ×worker 总账)、`os-for-architects/01`(Little + 线程公式 + CFS throttle) |
| ② 机制(每种有界资源怎么运作) | 🟢 每语言都有 | Py:`fastapi-ops/01-foundation`(anyio 40 令牌 CapacityLimiter)、`python-concurrency/06-anyio`、`python/16`(GIL/GC);Go:`golang/concurrency/01·08·09`、`golang/stdlib/03-database-sql`(db.Stats);Java:`java/concurrent/线程池.md`、`netty/概述.md`;连接池:`mysql-handson/01+11`、`python-data/02-connection-pooling`、`linux-handson/11/scenarios/05-connection-pool-starvation` |
| ③ 落地(export 代码→指标名→PromQL→Grafana→告警→诊断案例) | 🟡 大面积缺,但有两块已完成 | ✅ 已完成:`performance-tuning-roadmap/09a-database/04-connection-pool-monitor.md`(HikariCP 全套 active/idle/pending + Prometheus + Grafana 告警)、`nginx/10-observability-debugging.md`(边缘全套 stub_status/exporter/`$request_time` vs `$upstream_response_time`) |

**核心判断:不是「整个主题都缺」,而是「落地层缺得不均匀」。** 方法论与机制都铺好了;Java 连接池、Nginx 边缘甚至已到生产级。真正的洞口是 4 个:

1. **Python 落地**(用户正在读的 fastapi-ops 就缺):`anyio.CapacityLimiter` 只讲机制、无 `borrowed_tokens`/`tasks_waiting` 的 export;事件循环延迟检测散在 `06-profiling` 与 `perf-roadmap/06b/02`,未收成标准指标;运行时指标(线程数、GC)无 Prometheus 输出;连接池只有「排查一次」无持续监控。
2. **Go 落地**:`db.Stats()` 讲得好但未接 Prometheus;无 `client_golang` go collector(`go_goroutines`/`go_sched_latencies_seconds`)示例;worker pool / semaphore / `errgroup.SetLimit` 有代码无监控;`runtime/metrics` 新 API 缺。
3. **Java 落地**:连接池 ✅ 已完整;线程池→Micrometer/Prometheus 接线只到一半(`04b/04` 有 `getActiveCount()`/`getQueue().size()` 但未接 exporter);Netty EventLoop pending-task、Reactor `boundedElastic` scheduler 监控缺。
4. **缺一篇缝合的跨层 capstone**:核心洞察「**有界逻辑资源饱和系统层看不见 = CPU 没满但 P99 爆炸**」的碎片到处都有,但没有一篇正面讲透 + 走一条端到端诊断案例。

## 二、目标与非目标

### 目标
- 写一篇**跨语言 capstone**(纯叙事文),承载缺口 ④ 的核心洞察、统一心智模型、三语言对照速查、通用 PromQL/告警范式、一条端到端诊断树。
- 在三语言各自 track 补**薄落地**:Python 深(给完整 export 代码),Go/Java 对照速查深度(够接线 + 指向现有章节)。
- 风格:面试可讲的叙事文 + 对照速查表 + 诊断树。用户自学读,不需要他在 VM 里跑。

### 非目标(YAGNI)
- **不做** lab / docker-compose / 可跑 demo(用户明确选纯叙事)。
- **不重写**已完整的 HikariCP(`perf/09a/04`)、Nginx 边缘(`nginx/10`)。
- Go/Java **不灌**三语等深的完整代码;只到「能接线 + 速查对照」。
- **不重新定义** USE/RED(在 `perf/01`)、×worker 总账与饱和领先(在 `cc/05`+`cc/08`)、指标类型理论(在 `perf/03/03-metrics-theory`)——一律引用。
- 问答/速记只作复习层,不承载新知识。

### 三个 tie-breaker 的默认取定(用户未特别指定,review 时可推翻)
- **① capstone 的家**:`performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md`。理由:速查表要引用的章节有四个在 perf-roadmap 内(`04b/04` Java 线程池、`09a/04` HikariCP、`06b/02` asyncio debug、`05a` Go pprof),PromQL/指标类型地基也在 `03-observability`。`concurrency-capacity/08` 退为被引用的方法论源头。
- **② 诊断树**:绑一个具体场景——「下游某 API 变慢 → 上游协程/线程/连接被占住不放 → 回压逐层堆积」,逐层 walk。
- **③ 指标命名**:以 **OpenTelemetry semantic conventions** 为基准(如 `db.client.connection.count{state=used|idle}`、`process.runtime.*`),没有约定的退回各语言 exporter 默认名(HikariCP Micrometer 名、client_golang `go_*` 名),自建资源给 `app_*` 名。在速查表里一并标出「OTel 约定名 / exporter 默认名」。

## 三、交付物

### 交付物 1(主):capstone
**文件**:`performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md`
**语言/风格**:匹配 `03-observability/` 现有章节(简体、与 03/04 章一致的结构)。
**章节大纲**:

1. **系统层看不见的那半张脸** — 核心洞察。有界逻辑资源饱和时 `top` 看到一台「很闲」的机器(CPU 没满、延迟爆炸);为什么:线程阻塞在 I/O 不烧 CPU(回扣 `fastapi-ops/01` A5/A6)。给出「低 CPU + 高延迟」这个会骗人的特征签名。
2. **统一心智模型:每个有界资源 = 一个队列(M/M/c)** — 不管事件循环(c=1)、线程池、连接池、accept queue,都盯三个数:利用率(in-use/容量)、**饱和/等待(队列深度,领先指标)**、拒绝/溢出。引用 `cc/05`(M/M/c)+`cc/08`(饱和领先)。
3. **跨层资源清单** — 分层列:边缘(Nginx active conns / `accepts>handled`)→ app 运行时(event-loop lag、GC、线程/goroutine 数)→ app 逻辑池(自建 worker pool/semaphore)→ 下游连接池(DB/Redis/HTTP client)→ 系统层(仅用于「确认 CPU 确实闲」)。每行:盯哪个信号、为什么。
4. **★ 三语言对照速查表** — 行=资源,列=Python / Go / Java / 建议标准指标名(OTel + exporter 默认)。必含行:
   - 事件循环 / 反应式循环延迟:Py `loop` 漂移量 + `loop.slow_callback_duration`;**Go 明写「无对应物」**(runtime 自动扩 M,只有 `go_sched_latencies_seconds`);Java Netty `SingleThreadEventExecutor.pendingTasks()`、Reactor `boundedElastic`、WebFlux「别阻塞 event loop」。
   - 线程池 / 调度饱和:Py `anyio.to_thread.current_default_thread_limiter().statistics().tasks_waiting`/`.borrowed_tokens`;Go 自建 gauge + `db.Stats().WaitCount`;Java `ThreadPoolExecutor.getActiveCount()`/`getQueue().size()` → Micrometer `executor.active`/`executor.queued`、Tomcat `tomcat.threads.busy`。
   - 连接池:Py SQLAlchemy `engine.pool.checkedout()/overflow()` 或 asyncpg `pool.get_idle_size()`;Go `db.Stats()`(InUse/Idle/WaitCount/WaitDuration);Java HikariCP `hikaricp.connections.active/idle/pending`。OTel:`db.client.connection.count{state}`、`db.client.connection.pending_requests`。
   - 运行时:Py `threading.active_count()`+`prometheus_client` 的 `python_gc_*`/`process_*`;Go `client_golang` `go_goroutines`/`go_threads`/`go_gc_duration_seconds`;Java JVM threads/GC via Micrometer/Actuator。
   - 自建 semaphore / worker pool:三语都是「自己 export gauge」。
5. **通用 PromQL + 告警范式** — 告警建在**饱和度不是利用率**:`pending>0 for 30s`、`tasks_waiting>0`、`rate(rejected[5m])>0`、等待时间 `histogram_quantile(0.99, ...)`;×worker×副本 总账作**静态配置检查**。指标类型理论连 `03/03-metrics-theory`,告警模板连 `09a/04`。
6. **★ 端到端诊断树:CPU 没满但 P99 爆炸** — 绑场景(下游 API 变慢)。逐层 walk:边缘排队?(`$request_time` vs `$upstream_response_time`,连 `nginx/10`)→ 事件循环被阻塞?→ 线程池饱和?(`tasks_waiting`)→ DB 连接池枯竭?(`Threads_running` 高 vs 低,连 `mysql-handson/11`)→ 下游慢回压?每个分支:哪个指标确认、会看到什么。
7. **(轻)面试速记 3–5 题** — 复习层:怎么监控线程池饱和?CPU 不高但延迟高怎么查?为什么告警建在饱和度而非利用率?Go 为什么没有「线程池被挤满」?

### 交付物 2:Python 落地(深)
**文件**:`fastapi-ops/03-app-metrics/README.md` 新增一节「并发资源饱和监控」。
**内容**(完整可粘的 `prometheus_client` 代码):
- anyio CapacityLimiter export:读 `.statistics()` 的 `borrowed_tokens`/`total_tokens`/`tasks_waiting` → Gauge。
- 事件循环延迟:后台 task 量漂移 → `asyncio_event_loop_lag_seconds`(Gauge 或 Histogram);提 `loop.slow_callback_duration` / debug 模式。
- 运行时指标:线程数、GC(`prometheus_client` 默认 `GCCollector`/`ProcessCollector` 已带,点明指标名)。
- 连接池**持续**监控:SQLAlchemy `engine.pool` 状态 → Gauge(对比 `python-data/02` 的「一次性排查」)。
- 配套 PromQL + 告警 3–4 条。交叉链接到 capstone。

### 交付物 3:Go 落地(对照速查深度)
**文件**:`golang/service-design/03-observability/README.md` 新增一节。
**内容**:
- `db.Stats()` → Prometheus(把 InUse/Idle/WaitCount/WaitDuration 包成 collector,提 `sql.DBStats` 各字段含义)。
- `client_golang` go collector:`collectors.NewGoCollector(WithGoCollectorRuntimeMetrics(...))` → `go_goroutines`/`go_sched_latencies_seconds`/`go_gc_duration_seconds`。
- 一个 worker-pool / semaphore 的自建 gauge 范例(channel len 或 `golang.org/x/sync/semaphore` 持有数)。
- 点明「Go runtime 自动扩 M,无固定线程池被挤满的故障模式」。交叉链接 capstone + `golang/concurrency/09`。

### 交付物 4:Java 落地(最薄,填缝 + 链接)
- `performance-tuning-roadmap/04b-java-debugging/04-concurrency-performance.md`:补「线程池 → Micrometer/Prometheus 接线」那半步(`ExecutorServiceMetrics` 绑定 → `executor.active`/`executor.queued`/`executor.rejected`;Tomcat `tomcat.threads.busy`)。
- `performance-tuning-roadmap/04b-java-debugging/06-netty-performance.md`:补一小节 Netty EventLoop `pendingTasks()` 监控。
- `performance-tuning-roadmap/11-architecture/03-async-reactive.md`:补一小节 Reactor `boundedElastic` scheduler 监控(reactor-core-micrometer)。
- HikariCP 已完整(`09a/04`),只在 capstone 速查表与诊断树里**链接**,不重写。

### 交付物 5:前向链接
- `concurrency-capacity/08-monitoring-concurrency/README.md` 末尾加一条指向 capstone 的前向链接(「落地见 …07-concurrent-resource-saturation」)。

## 四、连结地图(明确不重造)
USE/RED→`perf/01-methodology/02·03`;饱和领先 + ×worker 总账→`cc/05`+`cc/08`;指标类型理论→`perf/03/03-metrics-theory`;HikariCP 范本→`perf/09a/04`;Nginx 边缘→`nginx/10`;asyncio debug→`perf/06b/02`;Go pprof→`golang/concurrency/09`;池饥饿症状→`linux-handson/11/scenarios/05`;连接池总账/`Threads_running`→`mysql-handson/01·11`。

## 五、验收标准(纯文档)
- 所有 API/指标名**真实可用**:重点核 `anyio` `.statistics()` 字段名、`prometheus_client` 默认 collector 指标名、`client_golang` go collector 名、HikariCP/Micrometer 名、SQLAlchemy `engine.pool` 方法名、`sql.DBStats` 字段名、OTel `db.client.*` 约定名。
- 所有交叉链接路径**可解析**(指向真实存在的文件)。
- 不重复定义权威内容(USE/RED/总账/指标类型);只引用。
- 速查表四语列齐全;诊断树每个分支都有「确认指标」。
- 每个新增内容**匹配宿主文件现有语言与排版风格**。

## 六、实施顺序建议
1. capstone(交付物 1)——先立骨架,后续落地都引用它。
2. Python 落地(交付物 2)——最深,且是用户当前在读的 track。
3. Go 落地(交付物 3)。
4. Java 填缝(交付物 4)。
5. 前向链接(交付物 5)。
