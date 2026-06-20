# 可观测性三支柱

## 一句话回答

可观测性三支柱:**Metrics**(聚合数字——QPS/错误率/P99,看整体健康 + 告警,便宜)、**Trace**(单请求完整路径——经过哪些服务、每段耗时,定位跨服务哪一环慢/错)、**Log**(离散事件细节——那个时刻具体干了什么);三者互补,靠 **trace_id 串通**。载体是 **context**:trace 上下文挂在 ctx 上一路传,跨服务经 HTTP header(W3C `traceparent`)/gRPC metadata 传播——所以「ctx 首参一路下传」是命门(**断 ctx = 断 trace**)。用 **OpenTelemetry**(厂商中立标准 + SDK,一次接入可换任意后端)在中间件/拦截器统一开 span、记 metrics(按 RED)、注入 trace_id 到 slog 日志。

## 三支柱分工

| 支柱 | 看什么 | 回答 |
|---|---|---|
| Metrics | QPS/错误率/P99(聚合) | 整体健康吗、变差没(告警) |
| Trace | 单请求 span 树 | 这一个慢/错请求卡在哪环 |
| Log | 离散事件 | 那时刻具体发生什么 |

排障链:metrics 发现错误率涨 → trace 定位哪一跳 → log 看具体报错。

## 证据链接

- 正文:[`03 可观测性接入`](../03-observability/README.md);ctx 传播 [`concurrency/07`](../../../concurrency/07-context/README.md);**深挖** → [`observability/`](../../../../observability/) track

## 易追问的延伸

- **metrics 方法论?** RED(Rate/Errors/Duration,面向请求)、USE(Utilization/Saturation/Errors,面向资源);告警基于 RED + SLO。
- **trace 采样?** 全量太贵,头部/尾部采样 + 错误强制采样(深入见 observability)。
- **断 ctx 的坑?** 某处用 `context.Background()` 重起而非传入 ctx → trace 断链。
- **metrics 基数爆炸?** 别把 user_id 当 label;用有限基数(端点/状态码)。
- **和 Java?** Micrometer + OTel/SkyWalking;OTel 是跨语言统一标准。
