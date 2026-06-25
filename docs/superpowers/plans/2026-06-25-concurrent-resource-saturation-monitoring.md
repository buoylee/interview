# 应用级资源饱和监控(跨语言 capstone + 三薄落地)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐全仓「生产级并发/运行时资源监控」的落地层缺口——一篇跨语言 capstone(核心洞察 + 统一心智模型 + 三语言对照速查 + 通用 PromQL/告警 + 端到端诊断树)+ Python(深)/Go/Java 三个薄落地。

**Architecture:** 纯叙事文(无 lab)。capstone 放 `performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md`,承载洞察与跨语言对照;三个落地各自挂在该语言已有的可观测/调优章节,提供可粘代码;已完整的内容(HikariCP、Nginx 边缘、USE/RED 方法论、指标类型理论)一律链接不重写。

**Tech Stack:** Markdown 文档;引用的库 = Python `anyio`/`prometheus_client`/`SQLAlchemy`、Go `database/sql`/`prometheus/client_golang`、Java `Micrometer`/`HikariCP`/`Netty`/`Reactor`。

## Global Constraints

- 纯叙事文档,**不做** lab / docker-compose / 可跑 demo。
- **不重新定义**:USE/RED(在 `performance-tuning-roadmap/01-methodology/02-use-method.md`、`/03-red-golden-signals.md`)、×worker 总账 + 饱和领先(在 `concurrency-capacity/05-pools`、`/08-monitoring-concurrency`)、指标类型理论 Counter/Gauge/Histogram(在 `performance-tuning-roadmap/03-observability/03-metrics-theory.md`)——一律**引用**。
- **不重写**:HikariCP 全套(`performance-tuning-roadmap/09a-database/04-connection-pool-monitor.md`)、Nginx 边缘(`nginx/10-observability-debugging.md`)——只**链接**。
- 每个新增内容**匹配宿主文件现有语言与排版风格**(perf-roadmap/golang/fastapi-ops 均为简体)。
- 指标命名:OpenTelemetry semantic conventions 为基准(`db.client.connection.count{state=used|idle}`、`db.client.connection.pending_requests`、`process.runtime.*`),无约定者退回各语言 exporter 默认名,自建资源用 `app_*`。
- **已核实的 API/指标名(权威,直接用)**:
  - anyio 4.x:`anyio.to_thread.current_default_thread_limiter()` → `CapacityLimiter`;`.statistics()` → 字段 `borrowed_tokens` / `total_tokens` / `tasks_waiting` / `borrowers`;`limiter.total_tokens` 默认 40、可写。
  - prometheus_client:默认已注册 `ProcessCollector`(`process_open_fds`/`process_resident_memory_bytes`/`process_cpu_seconds_total`)、`GCCollector`(`python_gc_collections_total`/`python_gc_objects_collected_total`)、`PlatformCollector`。
  - SQLAlchemy `QueuePool`(含 AsyncEngine 的 `engine.pool`):`.checkedout()` / `.checkedin()` / `.overflow()` / `.size()`。
  - Go `sql.DBStats`:`OpenConnections` / `InUse` / `Idle` / `WaitCount` / `WaitDuration` / `MaxOpenConnections`。
  - Go client_golang:`collectors.NewGoCollector(collectors.WithGoCollectorRuntimeMetrics(...))` → `go_goroutines` / `go_threads` / `go_sched_latencies_seconds` / `go_gc_duration_seconds`。
  - Java Micrometer `ExecutorServiceMetrics` → `executor.active` / `executor.queued` / `executor.pool.size` / `executor.completed` / `executor.rejected`;Tomcat `tomcat.threads.busy` / `tomcat.threads.current` / `tomcat.threads.config.max`;HikariCP `hikaricp.connections.active` / `.idle` / `.pending`;Netty `SingleThreadEventExecutor.pendingTasks()`;Reactor reactor-core-micrometer `Micrometer.timedScheduler(...)`。
- **canonical 自建指标名(跨任务一致,Task 2 速查表与 Task 3/4 落地必须用同名)**:
  - Python:`app_threadpool_tasks_waiting` / `app_threadpool_borrowed_tokens` / `app_threadpool_total_tokens`、`asyncio_event_loop_lag_seconds`、`app_db_pool_checked_out` / `app_db_pool_overflow`、`app_python_threads`。
  - Go:`app_db_pool_in_use`、`app_db_pool_wait_count_total`、`app_worker_inflight`。
- 提交信息用中文 conventional commit,结尾附:`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。
- 文档任务的"测试"= 验证:① 交叉链接路径 `test -f` 可解析;② 新文件含已核实 API/指标名(grep 自查);③ 不重述权威内容(人工核对只链接)。

---

### Task 1: capstone 骨架(§1–3、§5、§7)+ cc/08 前向链接

**Files:**
- Create: `performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md`
- Modify: `concurrency-capacity/08-monitoring-concurrency/README.md`(末尾加一条前向链接)
- Reference(读以对齐风格/不重述):`performance-tuning-roadmap/03-observability/03-metrics-theory.md`、`/04-prometheus-grafana.md`、`/06-alerting-oncall.md`、`concurrency-capacity/08-monitoring-concurrency/README.md`、`fastapi-ops/01-foundation/README.md`(A5/A6)

**Interfaces:**
- Produces:capstone 文件存在 + 含 §4/§6 的占位标题(Task 2 填充);§5 的告警范式;cc/08 → capstone 的前向链接。

- [ ] **Step 1: 读宿主与引用章节,对齐风格**

Run: `sed -n '1,40p' performance-tuning-roadmap/03-observability/03-metrics-theory.md` 与 `sed -n '1,30p' performance-tuning-roadmap/03-observability/README.md`
确认标题层级、术语(简体)、章节间链接写法。

- [ ] **Step 2: 写 capstone §1–3、§5、§7**

新建 `07-concurrent-resource-saturation.md`,写入以下小节(§4/§6 仅留二级标题 + 一行「见 Task 2」占位,本任务不填):

- **§1 系统层看不见的那半张脸**:核心洞察——有界逻辑资源饱和时 `top` 看到一台「很闲」的机器(CPU 没满、P99 爆炸)。为什么:阻塞 I/O 不烧 CPU(线程在 C 层释放 GIL/在等待队列里 park)。回扣 `fastapi-ops/01-foundation`(A5 阻塞循环 / A6 线程池 40 令牌)。给出「低 CPU + 高延迟」会骗人的特征签名。
- **§2 统一心智模型:每个有界资源 = 一个队列(M/M/c)**:事件循环(c=1)、线程池、连接池、accept queue 都盯三个数——利用率(in-use/容量)、**饱和/等待(队列深度=领先指标)**、拒绝/溢出。链接 `concurrency-capacity/05-pools`(M/M/c)与 `/08`(饱和领先、×worker 总账),声明本章不重推。
- **§3 跨层资源清单**:分层列(每层一段 + 该层盯什么、为什么):边缘(Nginx active conns / `accepts>handled`,链接 `nginx/10`)→ app 运行时(event-loop lag、GC、线程/goroutine 数)→ app 逻辑池(自建 worker pool / semaphore)→ 下游连接池(DB/Redis/HTTP client)→ 系统层(只用于「确认 CPU 确实闲」,链接 `linux-handson/07`、`/06`)。
- **§5 通用 PromQL + 告警范式**:核心原则——**告警建在饱和度不是利用率**。给通用 PromQL 模板(语言无关):
  ```promql
  # 饱和领先告警:任何「等待数」> 0 持续 30s
  <saturation_metric> > 0           # for: 30s
  # 拒绝/溢出出现即告警
  rate(<rejected_total>[5m]) > 0
  # 等待时间尾延迟
  histogram_quantile(0.99, rate(<wait_seconds_bucket>[5m])) > 0.05
  ```
  并说明 ×worker×副本 总账作**静态配置检查**(不是运行时告警);指标类型选型链接 `03-metrics-theory`,Grafana/告警模板链接 `09a-database/04`。
- **§7 面试速记**:4 题(只复习,不引入新知):① 怎么监控线程池饱和?② CPU 不高但延迟高怎么查?③ 为什么告警建在饱和度而非利用率?④ Go 为什么没有「线程池被挤满」?

- [ ] **Step 3: cc/08 末尾加前向链接**

在 `concurrency-capacity/08-monitoring-concurrency/README.md` 末尾(交互卡/参考链接区)加一行:
```markdown
> **落地实现(export 代码 / 三语言对照 / 诊断树)见** [`performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation`](../../performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md)。
```

- [ ] **Step 4: 验证链接可解析**

Run:
```bash
for f in nginx/10-observability-debugging.md concurrency-capacity/05-pools/README.md concurrency-capacity/08-monitoring-concurrency/README.md performance-tuning-roadmap/03-observability/03-metrics-theory.md performance-tuning-roadmap/09a-database/04-connection-pool-monitor.md linux-handson/07-troubleshooting-playbook/README.md fastapi-ops/01-foundation/README.md; do test -f "$f" && echo "OK $f" || echo "MISSING $f"; done
```
Expected: 全部 OK。

- [ ] **Step 5: Commit**

```bash
git add performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md concurrency-capacity/08-monitoring-concurrency/README.md
git commit -m "docs(perf/observability): 新增并发资源饱和监控 capstone 骨架(§1-3/5/7)+ cc/08 前向链接" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: capstone ★ 两大核心制品(§4 三语言对照速查 + §6 端到端诊断树)

**Files:**
- Modify: `performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md`(填充 §4、§6)

**Interfaces:**
- Consumes:Task 1 的 capstone 文件与占位标题;Global Constraints 的 canonical 指标名。
- Produces:§4 速查表(被读者当对照卡)、§6 诊断树(面试可讲那条线)。

- [ ] **Step 1: 填 §4 三语言对照速查表**

写入下表(行=资源,列=Python / Go / Java / 建议标准指标名),并在表后用 2-3 句解释「事件循环行 Go 为何无对应物」:

```markdown
| 资源 | Python | Go | Java | 建议标准指标名 |
|---|---|---|---|---|
| 事件循环/反应式循环延迟 | 后台 task 量 loop 漂移 → `asyncio_event_loop_lag_seconds`;`loop.slow_callback_duration` | **无对应物**(runtime 自动扩 M);只有 `go_sched_latencies_seconds` | Netty `SingleThreadEventExecutor.pendingTasks()`;Reactor `boundedElastic`;WebFlux「别阻塞 loop」 | `process.runtime.*` |
| 线程池/调度饱和 | `current_default_thread_limiter().statistics().tasks_waiting`/`.borrowed_tokens` | 自建 `app_worker_inflight` + `db.Stats().WaitCount` | `executor.queued`/`executor.active`/`executor.rejected`;Tomcat `tomcat.threads.busy` | `app_*`(无 OTel 约定) |
| 连接池 | `engine.pool.checkedout()`/`.overflow()` 或 asyncpg `pool.get_idle_size()` | `db.Stats()`:`InUse`/`Idle`/`WaitCount`/`WaitDuration` | HikariCP `hikaricp.connections.active`/`.idle`/`.pending` | `db.client.connection.count{state}`、`db.client.connection.pending_requests` |
| 运行时(GC/线程数) | `threading.active_count()`;`python_gc_collections_total`/`process_open_fds`(prometheus_client 默认) | `go_goroutines`/`go_threads`/`go_gc_duration_seconds` | JVM threads/GC via Micrometer/Actuator | `process.runtime.*` |
| 自建 semaphore/worker pool | 自建 Gauge | 自建 Gauge(channel len / semaphore 持有数) | 自建 Gauge / `ExecutorServiceMetrics` | `app_*` |
```
表后注明:Java 连接池全套落地见 `../09a-database/04-connection-pool-monitor.md`;Go 连接池字段释义见 `../../golang/stdlib/03-database-sql`;Python asyncio 慢回调调试见 `../06b-python-debugging/02-asyncio-debugging.md`。

- [ ] **Step 2: 填 §6 端到端诊断树(绑场景)**

写入诊断树。场景:**「下游某 API 变慢 → 上游协程/线程/连接被占住不放 → 回压逐层堆积」**。结构为 top-down 决策树,每个分支给「确认指标 + 会看到什么」:
```
现象:P99 爆炸,但 `top` 显示 CPU 没满
├─ ① 边缘在排队? → 看 `$request_time` ≫ `$upstream_response_time`(链接 nginx/10)
│     或 accept queue:`ss -lnt` 的 Recv-Q 接近 Send-Q(链接 linux-handson/06)
├─ ② 事件循环被阻塞?(Python/Node)→ `asyncio_event_loop_lag_seconds` 飙高
│     → 找在 async def 里跑的同步阻塞调用(回扣 fastapi-ops/01 A5)
├─ ③ 线程池饱和? → `tasks_waiting`(Py)/`executor.queued`(Java)持续 > 0
│     → 同步 def 端点过多 / 池太小(回扣 A6 的 40 令牌)
├─ ④ DB 连接池枯竭? → `pending`/`WaitCount` 涨;再看 DB 侧 `Threads_running`
│     高=真业务压力,低=连接被慢查 hang 住堆积(链接 mysql-handson/11)
└─ ⑤ 下游慢回压? → 自建 worker/semaphore 的 inflight 触顶 + 下游 P99 涨
      → 别调大池(只是把队列挪到下游),该限流/隔离/async 化(链接 concurrency-capacity/07)
```
收尾一句:**逐层都在问同一个问题——「哪个有界队列满了,而它的饱和系统层看不见」。**

- [ ] **Step 3: 验证 API/指标名与链接**

Run:
```bash
grep -c -e tasks_waiting -e borrowed_tokens -e asyncio_event_loop_lag_seconds -e 'db.Stats' -e WaitCount -e 'hikaricp.connections' -e go_sched_latencies_seconds performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md
for f in performance-tuning-roadmap/09a-database/04-connection-pool-monitor.md golang/stdlib/03-database-sql/README.md performance-tuning-roadmap/06b-python-debugging/02-asyncio-debugging.md mysql-handson/11-ops-and-troubleshooting/README.md linux-handson/06-networking/README.md concurrency-capacity/07-overload-backpressure/README.md; do test -f "$f" && echo "OK $f" || echo "MISSING $f"; done
```
Expected: grep 计数 > 0;链接全部 OK。(若 `golang/stdlib/03-database-sql/README.md` 路径不符,用 `find golang/stdlib -ipath '*database*'` 修正链接。)

- [ ] **Step 4: Commit**

```bash
git add performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md
git commit -m "docs(perf/observability): capstone 补三语言对照速查表 + 端到端诊断树" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Python 深落地(fastapi-ops/03-app-metrics)

**Files:**
- Modify: `fastapi-ops/03-app-metrics/README.md`(新增一节「并发资源饱和监控」)
- Reference:`fastapi-ops/01-foundation/README.md`(A6 线程池)、`python-data/02-connection-pooling.md`(一次性排查,本节给持续监控做对比)

**Interfaces:**
- Consumes:Global Constraints 的 canonical Python 指标名;Task 2 §4 速查表(本节是其 Python 列的展开)。
- Produces:可粘 `prometheus_client` 代码 + 配套 PromQL/告警;capstone §4 链接的目标。

- [ ] **Step 1: 读宿主章节,确认接入风格**

Run: `sed -n '40,70p' fastapi-ops/03-app-metrics/README.md`(看现有 `prometheus_client` 手动埋点风格,沿用)。

- [ ] **Step 2: 写「并发资源饱和监控」节**

在 `03-app-metrics/README.md` 适当位置(手动埋点节之后、PromQL 节之前)插入新节,含以下四段代码 + 说明:

```python
# 用一个后台采样协程统一刷新「拉取时」难取的运行期指标(避免在 /metrics 处理协程里取 loop 绑定对象)
import anyio.to_thread, asyncio, threading
from prometheus_client import Gauge

TP_BORROWED = Gauge("app_threadpool_borrowed_tokens", "anyio 线程池在用线程数")
TP_TOTAL    = Gauge("app_threadpool_total_tokens", "anyio 线程池容量上限")
TP_WAITING  = Gauge("app_threadpool_tasks_waiting", "排队等令牌的协程数(饱和领先指标)")
LOOP_LAG    = Gauge("asyncio_event_loop_lag_seconds", "事件循环单拍滞后(实际睡眠-预期)")
PY_THREADS  = Gauge("app_python_threads", "当前 Python 线程数")

async def sample_concurrency(interval: float = 0.5):
    loop = asyncio.get_running_loop()
    while True:
        t0 = loop.time()
        await asyncio.sleep(interval)
        LOOP_LAG.set(loop.time() - t0 - interval)            # 多睡的部分 = 循环被卡住的时间
        s = anyio.to_thread.current_default_thread_limiter().statistics()
        TP_BORROWED.set(s.borrowed_tokens); TP_TOTAL.set(s.total_tokens); TP_WAITING.set(s.tasks_waiting)
        PY_THREADS.set(threading.active_count())
```
```python
# 在 lifespan 里挂起采样协程
@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(sample_concurrency())
    yield
    task.cancel()
```
```python
# 连接池「持续」监控(对比 python-data/02 的一次性排查)
from prometheus_client import Gauge
DB_CHECKED_OUT = Gauge("app_db_pool_checked_out", "已借出连接数")
DB_OVERFLOW    = Gauge("app_db_pool_overflow", "溢出连接数(超过 pool_size 的临时连接)")
def collect_db_pool(engine):           # AsyncEngine 也用 engine.pool
    p = engine.pool
    DB_CHECKED_OUT.set(p.checkedout()); DB_OVERFLOW.set(p.overflow())
```
说明段点明:**运行时指标(GC/fd/RSS)无需手写**——`prometheus_client` 默认已注册 `ProcessCollector`/`GCCollector`,`/metrics` 直接有 `process_open_fds`、`process_resident_memory_bytes`、`python_gc_collections_total`。

配套 PromQL/告警(3 条):
```promql
app_threadpool_tasks_waiting > 0                 # 同步 def 端点在排队(for: 30s → P2)
asyncio_event_loop_lag_seconds > 0.1             # 事件循环被阻塞(头号坑)
app_db_pool_overflow > 0                         # pool_size 已用尽、开始借临时连接 = 连接池饱和
```
末尾链接 capstone 与 `python-data/02-connection-pooling.md`。

- [ ] **Step 3: 验证 API 名与链接**

Run:
```bash
grep -c -e 'current_default_thread_limiter().statistics()' -e 'borrowed_tokens' -e 'tasks_waiting' -e 'asyncio_event_loop_lag_seconds' -e 'p.checkedout()' -e 'p.overflow()' -e 'ProcessCollector' fastapi-ops/03-app-metrics/README.md
for f in performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md python-data/02-connection-pooling.md fastapi-ops/01-foundation/README.md; do test -f "$f" && echo OK || echo "MISSING $f"; done
```
Expected: grep > 0;链接 OK。

- [ ] **Step 4: 用已核实环境冒烟一次(可选但建议)**

Run:
```bash
cd ai/langchain/mvp-agentic-rag && ./.venv/bin/python -c "
import asyncio, anyio.to_thread, prometheus_client
async def main():
    s = anyio.to_thread.current_default_thread_limiter().statistics()
    print('OK', s.borrowed_tokens, s.total_tokens, s.tasks_waiting)
asyncio.run(main())
print('ProcessCollector/GCCollector default:', hasattr(prometheus_client,'ProcessCollector'), hasattr(prometheus_client,'GCCollector'))
"
```
Expected: 打印 `OK 0 40 0` 与 `... True True`(确认 anyio statistics 字段与 prometheus 默认 collector 在已装版本可用)。

- [ ] **Step 5: Commit**

```bash
git add fastapi-ops/03-app-metrics/README.md
git commit -m "docs(fastapi-ops/03): 新增并发资源饱和监控(anyio 线程池/事件循环延迟/连接池/运行时 export)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Go 对照落地(golang/service-design/03-observability)

**Files:**
- Modify: `golang/service-design/03-observability/README.md`(新增一节)
- Reference:`golang/stdlib/03-database-sql/README.md`(db.Stats 字段)、`golang/concurrency/09-pitfalls-tuning/README.md`(pprof)

**Interfaces:**
- Consumes:Global Constraints 的 canonical Go 指标名。
- Produces:capstone §4 Go 列的展开;`db.Stats()`→Prometheus、client_golang go collector、worker-pool gauge 代码。

- [ ] **Step 1: 读宿主章节风格**

Run: `sed -n '1,40p' golang/service-design/03-observability/README.md`

- [ ] **Step 2: 写「并发资源饱和监控落地」节**

插入以下三段代码 + 说明:
```go
// ① db.Stats() -> Prometheus(GaugeFunc/CounterFunc,拉取时实时读)
prometheus.MustRegister(
    prometheus.NewGaugeFunc(prometheus.GaugeOpts{Name: "app_db_pool_in_use", Help: "在用连接数"},
        func() float64 { return float64(db.Stats().InUse) }),
    prometheus.NewCounterFunc(prometheus.CounterOpts{Name: "app_db_pool_wait_count_total", Help: "等待连接累计次数(领先指标)"},
        func() float64 { return float64(db.Stats().WaitCount) }),
)
// sql.DBStats 还有 Idle / WaitDuration / OpenConnections / MaxOpenConnections
```
```go
// ② client_golang go collector:内建运行时指标
import "github.com/prometheus/client_golang/prometheus/collectors"
reg := prometheus.NewRegistry()
reg.MustRegister(collectors.NewGoCollector(
    collectors.WithGoCollectorRuntimeMetrics(collectors.MetricsScheduler, collectors.MetricsGC),
))
// 暴露 go_goroutines / go_threads / go_sched_latencies_seconds / go_gc_duration_seconds
```
```go
// ③ 自建 worker pool / semaphore 的 inflight gauge
inflight := prometheus.NewGauge(prometheus.GaugeOpts{Name: "app_worker_inflight", Help: "在途任务数"})
prometheus.MustRegister(inflight)
sem := make(chan struct{}, limit)
// acquire: sem <- struct{}{}; inflight.Inc()
// release: <-sem;            inflight.Dec()
```
说明段点明(回扣 capstone 洞察):**Go runtime 在 goroutine 阻塞 syscall 时自动扩 M,所以「固定线程池被挤满」这种 Python/Java 故障模式在 Go 基本不存在**——Go 侧的有界资源主要是连接池与自建 semaphore;调度压力看 `go_sched_latencies_seconds`,泄漏看 `go_goroutines` 单调上升。链接 capstone 与 `golang/concurrency/09`。

- [ ] **Step 3: 验证指标名与链接**

Run:
```bash
grep -c -e 'db.Stats()' -e 'app_db_pool_in_use' -e 'WaitCount' -e 'NewGoCollector' -e 'WithGoCollectorRuntimeMetrics' -e 'app_worker_inflight' golang/service-design/03-observability/README.md
for f in performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md golang/concurrency/09-pitfalls-tuning/README.md; do test -f "$f" && echo OK || echo "MISSING $f"; done
test -f golang/stdlib/03-database-sql/README.md && echo "OK db-sql" || find golang/stdlib -ipath '*database*' -name README.md
```
Expected: grep > 0;链接 OK(若 db-sql 路径不符,用 find 结果修正 capstone 与本节链接)。

- [ ] **Step 4: Commit**

```bash
git add golang/service-design/03-observability/README.md
git commit -m "docs(golang/service-design/03): 新增并发资源饱和落地(db.Stats→Prometheus / go collector / worker-pool gauge)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Java 填缝(线程池接线 + Netty/Reactor 监控小节)

**Files:**
- Modify: `performance-tuning-roadmap/04b-java-debugging/04-concurrency-performance.md`(补线程池→Micrometer 接线)
- Modify: `performance-tuning-roadmap/04b-java-debugging/06-netty-performance.md`(补 EventLoop 监控小节)
- Modify: `performance-tuning-roadmap/11-architecture/03-async-reactive.md`(补 Reactor boundedElastic 监控小节)

**Interfaces:**
- Consumes:Global Constraints 的 Java Micrometer/Netty/Reactor 指标名。
- Produces:capstone §4 Java 列引用的落地;连接池仍指向已完整的 `09a-database/04`。

- [ ] **Step 1: 04b/04 补线程池→Micrometer 接线**

在 `04-concurrency-performance.md` 现有 `getActiveCount()`/`getQueue().size()` 段之后,补一小段把它接到 Prometheus:
```java
// 把 ThreadPoolExecutor 接入 Micrometer(Spring Boot 下自动导出到 /actuator/prometheus)
ExecutorServiceMetrics.monitor(meterRegistry, executor, "biz-pool");
// 得到 executor.active / executor.queued / executor.pool.size / executor.completed / executor.rejected
// Web 容器线程池(Tomcat)Actuator 自动埋:tomcat.threads.busy / tomcat.threads.current / tomcat.threads.config.max
```
一句话点明:**告警建在 `executor.queued`/`executor.rejected`(饱和),不是 `executor.active`(利用率)**。链接 capstone。

- [ ] **Step 2: 04b/06 补 Netty EventLoop 监控小节**

在 `06-netty-performance.md` 末尾补:
```java
// 每个 EventLoop 是单线程,绝不能在 handler 里阻塞;监控 pending 任务堆积:
for (EventExecutor e : group) {
    if (e instanceof SingleThreadEventExecutor ste) {
        gauge("netty.eventloop.pending.tasks", ste, SingleThreadEventExecutor::pendingTasks);
    }
}
```
点明:`pendingTasks()` 持续增长 = EventLoop 被某个慢/阻塞 handler 拖住(等价 capstone §6 的「事件循环被阻塞」分支)。链接 capstone。

- [ ] **Step 3: 11/03 补 Reactor boundedElastic 监控小节**

在 `03-async-reactive.md` 末尾补:
```java
// 阻塞调用要 .subscribeOn(Schedulers.boundedElastic());监控这个有界弹性池的饱和:
// 依赖 reactor-core-micrometer
Scheduler monitored = Micrometer.timedScheduler(Schedulers.boundedElastic(), meterRegistry, "boundedElastic");
// 关注其执行/排队计时器;池满会让阻塞任务排队 → 反应式链路尾延迟上升
```
点明:WebFlux/Reactor 的纪律与 Netty 同源——**别阻塞 event loop 线程,阻塞活儿丢 boundedElastic 并监控它的饱和**。链接 capstone。

- [ ] **Step 4: 验证指标名与链接**

Run:
```bash
grep -c -e 'ExecutorServiceMetrics' -e 'executor.queued' -e 'tomcat.threads.busy' performance-tuning-roadmap/04b-java-debugging/04-concurrency-performance.md
grep -c -e 'pendingTasks' performance-tuning-roadmap/04b-java-debugging/06-netty-performance.md
grep -c -e 'boundedElastic' -e 'timedScheduler' performance-tuning-roadmap/11-architecture/03-async-reactive.md
test -f performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md && echo OK || echo MISSING
```
Expected: 各 grep > 0;capstone OK。

- [ ] **Step 5: Commit**

```bash
git add performance-tuning-roadmap/04b-java-debugging/04-concurrency-performance.md performance-tuning-roadmap/04b-java-debugging/06-netty-performance.md performance-tuning-roadmap/11-architecture/03-async-reactive.md
git commit -m "docs(perf/java): 线程池→Micrometer 接线 + Netty EventLoop / Reactor boundedElastic 饱和监控" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 验收(全部任务完成后)
- capstone 7 节齐全;§4 速查表四语列齐;§6 诊断树每分支有「确认指标」。
- Python 落地代码用已核实 API;Go/Java 落地指标名与 capstone §4 一致。
- 全部交叉链接 `test -f` 通过;cc/08 有前向链接。
- 无重述权威内容(USE/RED/总账/指标类型/HikariCP/Nginx 均为链接)。
