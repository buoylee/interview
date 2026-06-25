# 03 · 可观测性接入

> 服务跑起来后,怎么**看清它在干什么、出问题时怎么定位**?这就是可观测性:**三支柱(trace / metrics / log)+ context 传播**。本章讲「Go 服务怎么接入」,**可观测性原理的深挖链到 [`observability/`](../../../observability/) track**(不重复)。
>
> 桥接锚点:Java 的 Micrometer(metrics)+ OpenTelemetry/SkyWalking(trace)+ logback ←→ Go 的 OTel SDK + slog;思路一致,OTel 是跨语言统一标准。

---

## 1. 核心问题

- 一个请求跨了 5 个服务,出错/变慢了怎么定位是哪一环?
- metrics、trace、log 各看什么?怎么串起来?
- Go 服务怎么接 OpenTelemetry?context 在里面起什么作用?

---

## 2. 直觉理解

### 三支柱:各回答一类问题

- **Metrics(指标)**:**聚合数字**——QPS、错误率、P99 延迟、连接数。回答「系统**整体**健康吗、有没有变差」。便宜、适合告警和大盘。
- **Trace(链路追踪)**:**一个请求的完整路径**——它经过哪些服务、每段耗时、哪里出错。回答「**这一个**慢/错的请求,卡在哪一环」。
- **Log(日志)**:**离散事件细节**——具体某次发生了什么。回答「**那个时刻**到底干了什么」。

三者**互补**:metrics 发现「错误率涨了」→ trace 定位「是 payment 服务那一跳慢」→ log 看「那次具体报了什么」。串起来的关键是 **trace_id**(贯穿三支柱)。

### context 是可观测性的载体

回忆 [`concurrency/07`](../../concurrency/07-context/README.md):ctx 沿调用链传递。**trace 信息(trace_id、span)就挂在 ctx 上**一路传——这就是为什么「ctx 作首参、一路下传」(见 [`design/03`](../../design/03-concurrent-api/README.md))对可观测性至关重要:断了 ctx 传递,trace 就断链。

---

## 3. 原理深入

### 3.1 OpenTelemetry(OTel):跨语言统一标准

OTel 是 trace/metrics/log 的**厂商中立标准** + SDK,Go 有官方实现。一次接入,可导出到任意后端(Jaeger/Prometheus/Tempo/各家 APM)——避免绑死某厂商(呼应 [[user_saas_dependence_unease]] 的开源逃生票思路)。

```go
// 中间件/拦截器里开 span,ctx 携带 trace 上下文往下传
ctx, span := tracer.Start(ctx, "GetUser")
defer span.End()
span.SetAttributes(attribute.Int("user.id", id))
// 出错时:
span.RecordError(err); span.SetStatus(codes.Error, "...")   // 呼应 error-handling/04 边界记录
```

### 3.2 trace 传播:span 树 + 跨服务传 context

- 一个请求 = 一棵 **span 树**:每个操作一个 span(有耗时、属性、父子关系)。
- **跨服务传播**:trace context 通过 HTTP header(`traceparent`,W3C Trace Context 标准)/gRPC metadata 传递——上游把 trace_id 放 header,下游接住继续同一条 trace。OTel 的 instrumentation 自动做这件事(http/grpc 中间件)。
- 这正是「跨 5 个服务定位哪一环」的实现:同一 trace_id 把 5 段串成一条链。

### 3.3 metrics:RED / USE 方法论

- **RED**(面向请求的服务):**R**ate(QPS)、**E**rrors(错误率)、**D**uration(延迟分布)——大多数服务盯这三个。
- **USE**(面向资源):**U**tilization、**S**aturation、**E**rrors——看资源(CPU/内存/连接池)。
- Go 用 OTel metrics 或 Prometheus client 暴露 `/metrics`,按 RED 给每个端点出 QPS/错误率/P99。

### 3.4 log 与 trace 关联

结构化日志(slog,见 [`00`](../00-service-skeleton/README.md))里**带上 trace_id**:

```go
logger.InfoContext(ctx, "user fetched", "user.id", id)   // 从 ctx 取 trace_id 一起打
```

这样一条慢 trace → 拿 trace_id → 捞出该请求所有日志,三支柱打通。日志只在边界打一次(handle once,见 [`error-handling/04`](../../error-handling/04-error-design/README.md))。

### 3.5 接入点:还是中间件/拦截器

可观测性的注入点和 [`02 中间件`](../02-middleware/README.md) 同源:在 HTTP 中间件 / gRPC 拦截器里**统一**开 span、记 metrics、注入 trace_id 到 ctx 和日志——一处接入,全链覆盖。

---

## 4. 日常开发应用

- **用 OTel** 统一接 trace/metrics(中立、可换后端);自动 instrumentation 覆盖 http/grpc/db。
- **ctx 一路传**:别断 ctx,否则 trace 断链(见 [`design/03`](../../design/03-concurrent-api/README.md))。
- **metrics 按 RED**:每端点 QPS/错误率/P99,接告警。
- **日志带 trace_id**(slog + ctx),边界打一次。
- **关键操作开 span** + 出错 `RecordError`,把内部细节放 trace/log 而非返给客户端(见 [`error-handling/04`](../../error-handling/04-error-design/README.md))。
- **深挖原理**(采样、span、指标类型、OTel collector)→ [`observability/`](../../../observability/) track。

---

## 5. 生产&调优实战

- **trace 采样**:全量 trace 成本高(存储 + 性能);生产用采样(头部/尾部采样),错误请求强制采样。深入见 observability track。
- **断 ctx = 断 trace**:在某处 `context.Background()` 重新起(而非传入的 ctx),trace 就断了;后台任务要用 OTel 的方式延续 trace。
- **metrics 基数爆炸**:label 维度过多(如把 user_id 当 label)会让时序数据库爆炸;label 用有限基数(端点/状态码/方法)。
- **可观测性开销**:span/metrics 有 CPU/内存成本;高吞吐下批量导出 + 采样 + 异步,别同步阻塞请求。
- **三支柱要打通**:只有 metrics 没 trace → 知道变差但定位不到;trace 不带 log → 看到慢但不知为何。trace_id 串三支柱是落地关键。
- **告警基于 RED + SLO**:对错误率/P99 设 SLO 告警,而非对 CPU 这种间接指标(USE 辅助定位)。

## 6. 面试高频考点

- **可观测性三支柱?各看什么?** Metrics(聚合数字:QPS/错误率/P99,整体健康+告警)、Trace(单请求完整路径,定位哪一环)、Log(离散事件细节)。互补,trace_id 串起来。
- **跨服务怎么定位慢/错请求?** 分布式 trace:同一 trace_id 串起跨服务的 span 树;trace context 经 HTTP header(W3C traceparent)/gRPC metadata 传播。
- **context 和可观测性关系?** trace 上下文挂在 ctx 上一路传;断 ctx = 断 trace,所以「ctx 首参一路下传」对可观测性关键。
- **OTel 是什么?为什么用?** 厂商中立的 trace/metrics/log 标准 + SDK,一次接入可换任意后端,不绑死厂商。
- **metrics 方法论?** RED(Rate/Errors/Duration,面向请求)、USE(面向资源);告警基于 RED + SLO。
- **怎么打通三支柱?** 日志带 trace_id、出错 span.RecordError;一条 trace 能捞出对应日志。
- **怎么接入?** HTTP 中间件 / gRPC 拦截器统一开 span + 记 metrics + 注入 trace_id(同 02 横切接入点)。

## 7. 一句话总结

> **可观测性三支柱:Metrics(聚合数字 QPS/错误率/P99——整体健康+告警)、Trace(单请求完整路径——定位跨服务哪一环慢/错)、Log(离散事件细节);trace_id 把三者串通**。载体是 **context**——trace 上下文挂在 ctx 上一路传,跨服务经 HTTP header(W3C traceparent)/gRPC metadata 传播,所以「ctx 首参一路下传」是命门(断 ctx=断 trace)。用 **OpenTelemetry**(厂商中立、可换后端)在中间件/拦截器统一开 span、记 metrics(按 RED)、注入 trace_id 到 ctx 和 slog 日志。生产注意采样(全量太贵)、label 基数、异步导出。**原理深挖见 [`observability/`](../../../observability/) track。**

---

## 8. 并发资源饱和监控落地(Go 实战)

> 本节是 [并发资源饱和监控 capstone](../../../performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md) § 4 Go 列的展开。capstone 给了三语言对照速查表,这里补完代码细节。

### 8.1 连接池监控:db.Stats() → Prometheus

Go 的 `database/sql` 在 `db.Stats()` 里暴露了完整的连接池状态([字段详见 `golang/stdlib/03-database-sql`](../../stdlib/03-database-sql/README.md))。用 `GaugeFunc` / `CounterFunc` 在 Prometheus 拉取时实时读取,无需后台 goroutine 定期推:

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

`app_db_pool_wait_count_total` 单调递增——它的导数(每秒等待次数)是连接池压力的**领先指标**,比 `InUse` 更早告警。

### 8.2 Go runtime 内建指标:client_golang go collector

`prometheus/client_golang` 的 `collectors.NewGoCollector` 把 Go runtime 指标直接接入 Prometheus,无需手写采集逻辑:

```go
// ② client_golang go collector:内建运行时指标
import "github.com/prometheus/client_golang/prometheus/collectors"
reg := prometheus.NewRegistry()
reg.MustRegister(collectors.NewGoCollector(
    collectors.WithGoCollectorRuntimeMetrics(collectors.MetricsScheduler, collectors.MetricsGC),
))
// 暴露 go_goroutines / go_threads / go_sched_latencies_seconds / go_gc_duration_seconds
```

关键指标含义:

| 指标 | 看什么 |
|---|---|
| `go_goroutines` | goroutine 总数;单调上升 = 泄漏 |
| `go_threads` | 系统线程数(M 数量);Go runtime 自动管理 |
| `go_sched_latencies_seconds` | goroutine 在 run queue 等待时间;p99 升高 = 调度压力 |
| `go_gc_duration_seconds` | GC STW 时间;影响尾延迟 |

### 8.3 自建 worker pool / semaphore 的 inflight gauge

当你用 channel 实现信号量限流时,需要自己暴露 inflight 任务数——runtime 不会替你计:

```go
// ③ 自建 worker pool / semaphore 的 inflight gauge
inflight := prometheus.NewGauge(prometheus.GaugeOpts{Name: "app_worker_inflight", Help: "在途任务数"})
prometheus.MustRegister(inflight)
sem := make(chan struct{}, limit)
// acquire: sem <- struct{}{}; inflight.Inc()
// release: <-sem;            inflight.Dec()
```

### 8.4 Go 与 Python/Java 的关键差异

**Go runtime 在 goroutine 阻塞 syscall 时自动扩 M**,所以「固定线程池被挤满」这种 Python/Java 故障模式在 Go 基本不存在——Python 受 GIL 约束、线程池有上限(`ThreadPoolExecutor`);Java 在虚拟线程前也有固定线程池瓶颈。Go 侧的有界资源主要是:

- **连接池**(`db.SetMaxOpenConns` 限制,超出阻塞等待)→ 看 `app_db_pool_wait_count_total`
- **自建 semaphore/channel**(`make(chan struct{}, limit)`)→ 看 `app_worker_inflight`

调度压力看 `go_sched_latencies_seconds`,goroutine 泄漏看 `go_goroutines` 单调上升。pprof 深挖(goroutine/mutex/block profile)见 [`golang/concurrency/09-pitfalls-tuning`](../../concurrency/09-pitfalls-tuning/README.md)。

---

← 上一章 [`02 中间件与横切`](../02-middleware/README.md) ｜ 下一章 → [`99 面试卡`](../99-interview-cards/README.md):服务骨架、gRPC vs REST、中间件、可观测性速查。｜ 回 [`service-design` 索引](../README.md)
