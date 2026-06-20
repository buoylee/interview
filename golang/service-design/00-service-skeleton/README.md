# 00 · 服务骨架:配置、优雅关闭、健康检查

> 一个生产级服务的「地基」:配置怎么读、怎么**优雅关闭**(K8s 滚动更新不丢请求)、健康检查 liveness/readiness 的区别、结构化日志。其中**优雅关闭是生产命门**——做不好滚动发布就掉请求(502)。
>
> 桥接锚点:Spring Boot 的 actuator(`/health`)、graceful shutdown、`application.yml` ←→ Go 手搓但更透明:signal + `srv.Shutdown(ctx)` + `/healthz`。

---

## 1. 核心问题

- 配置从哪来(文件/环境变量/flag)?生产怎么管?
- K8s 发新版本时,正在处理的请求会被掐断吗?怎么**优雅关闭**?
- liveness 和 readiness 健康检查有什么区别?为什么要两个?

---

## 2. 直觉理解

### 优雅关闭:收到停止信号 → 停止收新请求 → 等存量做完 → 退出

K8s 滚动更新时给容器发 **SIGTERM**。如果进程立刻 `os.Exit`,正在处理的请求**全被掐断**(客户端看到 502/连接重置)。优雅关闭的正确姿势:

```go
ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
defer stop()

go func() { srv.ListenAndServe() }()      // 起服务

<-ctx.Done()                               // 阻塞,等信号
stop()                                     // 恢复默认信号行为(再按一次能强杀)

shutdownCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()
srv.Shutdown(shutdownCtx)                  // 停止收新请求,等存量请求完成(或超时)
```

`signal.NotifyContext`(1.16)把信号变成一个会被取消的 ctx;`srv.Shutdown(ctx)`(见 [`stdlib/01`](../../stdlib/01-net-http/README.md))停止接新连接、等存量请求处理完。这套是**滚动发布不丢请求**的关键。

### liveness vs readiness:两个问题

- **liveness(存活)**:进程**还活着吗**?死了(死锁/卡死)就**重启**容器。`/healthz`,轻量、永远快速返回。
- **readiness(就绪)**:能**接收流量吗**?依赖(DB/缓存)没就绪、或正在优雅关闭时,返回 not ready → 从负载均衡**摘除**(但不重启)。`/readyz`,检查关键依赖。

为什么两个:**还活着 ≠ 能服务**。启动中、依赖抖动、优雅关闭期间,进程活着但不该收流量——这时 readiness 失败摘流量、liveness 仍通过(别重启)。

---

## 3. 原理深入

### 3.1 配置:12-factor,优先环境变量

```go
type Config struct {
    Addr     string        // 来自 env / flag / 文件
    DBDsn    string
    Timeout  time.Duration
}
```

- **12-factor 原则**:配置走**环境变量**(容器友好、不入代码库),敏感信息(密码/密钥)走 secret 注入。
- 来源优先级常是 flag > env > 配置文件 > 默认值。
- 工具:标准库 `flag`/`os.Getenv` 够用;复杂用 `viper`(多源合并)、`envconfig`(结构体绑定 env)。
- **启动时校验配置**,缺关键项直接 `log.Fatal`(快速失败,见 [`error-handling/00`](../../error-handling/00-philosophy/README.md):启动前置不满足该 panic/Fatal)。

### 3.2 优雅关闭的完整链条

```
SIGTERM → readiness 转 not ready(从 LB 摘流量)→ srv.Shutdown(停收新请求、等存量)
        → 关闭后台 worker(cancel 它们的 ctx,见 design/03)→ 关 DB 池/flush 日志 → 退出
```

关键点:

- **Shutdown 要有超时**(`WithTimeout(30s)`):存量请求超时还没完就强退,别无限等。
- **关闭顺序**:先摘流量(readiness)、再停 HTTP、再停后台 goroutine(cancel ctx)、最后关连接池/flush。
- **后台 goroutine 也要优雅停**:用 ctx 通知它们退出(见 [`design/03`](../../design/03-concurrent-api/README.md) 库别偷开 goroutine、[`concurrency/08`](../../concurrency/08-patterns/README.md) 优雅关闭模式)。

### 3.3 结构化日志:slog(1.21 标准库)

```go
logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
logger.Info("request handled", "method", r.Method, "status", 200, "trace_id", tid)
```

`log/slog`(1.21)是标准库的**结构化日志**:键值对、JSON 输出、级别、可挂 handler。生产日志要结构化(可被日志系统检索),带 `trace_id` 串联(见 [`03 可观测性`](../03-observability/README.md))。别用裸 `log.Printf` 拼字符串。

---

## 4. 日常开发应用

- **配置走 env**(12-factor)+ 启动校验 + 缺关键项 Fatal。
- **优雅关闭**:`signal.NotifyContext` + `srv.Shutdown(超时ctx)` + 关后台 goroutine + flush。
- **两个健康端点**:`/healthz`(liveness,轻量)+ `/readyz`(readiness,查依赖,优雅关闭期间转失败)。
- **slog 结构化日志**,带 trace_id;别裸 log.Printf。
- **main 薄**:配置 → 装配依赖(见 [`design/01`](../../design/01-composition-di/README.md))→ 起服务 → 等信号 → 优雅关闭。

---

## 5. 生产&调优实战

- **不做优雅关闭 = 滚动发布掉请求**:每次部署都有一批 502;K8s 默认 SIGTERM 后等 `terminationGracePeriodSeconds`(默认 30s)再 SIGKILL,你的 Shutdown 超时要小于它。
- **摘流量要早于停服务**:K8s 摘 endpoint 和发 SIGTERM 几乎同时但不保证顺序,常见做法:收到 SIGTERM 后先把 readiness 转失败、`sleep` 几秒等 LB 摘干净,再 Shutdown,避免「还在路上的请求」打到正在关的实例。
- **liveness 别查重依赖**:liveness 探针若查 DB,DB 抖一下就被误杀重启(雪上加霜);liveness 只查进程本身,依赖检查放 readiness。
- **配置热加载谨慎**:多数配置启动定死最简单;真要热加载(日志级别/限流阈值)用原子值 + 信号(SIGHUP)或配置中心。
- **日志别同步阻塞**:高吞吐下同步写日志会拖慢请求;slog handler 选异步/缓冲,或写 stdout 让采集器处理。

---

## 6. 面试高频考点

- **怎么优雅关闭?** `signal.NotifyContext(SIGTERM/SIGINT)` 得到 ctx,`<-ctx.Done()` 后 `srv.Shutdown(超时ctx)` 停收新请求、等存量完成,再关后台 goroutine(cancel ctx)+ flush。Shutdown 必须带超时。
- **K8s 滚动更新为什么会掉请求?怎么防?** 进程收 SIGTERM 立即退会掐断存量请求;优雅关闭 + 先摘 readiness 流量再 Shutdown。
- **liveness vs readiness?** liveness=进程还活着吗(死了重启,只查自身);readiness=能收流量吗(依赖没好/关闭中摘流量但不重启)。还活着≠能服务,所以要两个。
- **配置怎么管?** 12-factor 走环境变量、敏感信息 secret 注入、启动校验缺项 Fatal;flag>env>文件>默认。
- **日志怎么打?** slog(1.21)结构化键值 + JSON + trace_id;别裸 log.Printf 拼串。
- **liveness 探针能查 DB 吗?** 不该——DB 抖动会误杀重启;依赖检查放 readiness。

---

## 7. 一句话总结

> **生产级服务骨架四件事:① 配置走环境变量(12-factor)+ 启动校验缺项 Fatal;② 优雅关闭(生产命门)——`signal.NotifyContext(SIGTERM)` → 先把 readiness 转失败摘流量 → `srv.Shutdown(超时ctx)` 停收新请求等存量完成 → cancel 后台 goroutine → 关池/flush,Shutdown 必须带超时(< K8s 的 graceperiod),否则滚动发布掉请求(502);③ 两个健康端点——liveness(进程活着吗,死了重启、只查自身别查 DB)vs readiness(能收流量吗,依赖没好/关闭中摘流量不重启);④ slog 结构化日志带 trace_id**。≈ Spring Boot actuator + graceful shutdown,但 Go 手搓更透明。

下一章 → [`01 gRPC vs REST`](../01-grpc-rest/README.md):服务间怎么通信?protobuf/gRPC 和 REST/JSON 怎么选、gRPC 的拦截器和错误码映射。｜ 回 [`service-design` 索引](../README.md)
