# 99 · 面试卡 —— Go 服务/API 设计高频题速查

> 速答表(背诵)+ 深题卡(讲清,链回正文做证据)。
>
> 总钥匙:**服务 = 骨架 + 通信 + 横切 + 可观测;优雅关闭和超时是生产命门。**

## 卡片索引(深题卡)

- [优雅关闭 + liveness/readiness](q-graceful-shutdown.md)
- [gRPC vs REST 选型](q-grpc-rest.md)
- [限流·重试·熔断(韧性三件套)](q-resilience.md)
- [可观测性三支柱](q-observability.md)

## 速答表(一行一条,背诵用)

| 问题 | 速答 | 详 |
|---|---|---|
| 怎么优雅关闭 | signal.NotifyContext(SIGTERM)→摘 readiness→srv.Shutdown(超时ctx)→cancel 后台→flush | [00](../00-service-skeleton/README.md) |
| K8s 滚动为什么掉请求 | 收 SIGTERM 立即退掐断存量;优雅关闭+先摘流量再 Shutdown | [00](../00-service-skeleton/README.md) |
| liveness vs readiness | liveness=进程活着吗(死了重启,只查自身);readiness=能收流量吗(依赖没好/关闭中摘流量) | [00](../00-service-skeleton/README.md) |
| 配置怎么管 | 12-factor 走 env、secret 注入、启动校验缺项 Fatal | [00](../00-service-skeleton/README.md) |
| 日志 | slog(1.21)结构化键值+JSON+trace_id;别裸 log.Printf | [00](../00-service-skeleton/README.md) |
| gRPC vs REST 选型 | 内部服务间 gRPC(性能+强契约+流);对外/浏览器 REST;兼得 gRPC-gateway | [01](../01-grpc-rest/README.md) |
| gRPC 为什么快 | protobuf 二进制 + HTTP/2 多路复用 + 生成代码无反射 | [01](../01-grpc-rest/README.md) |
| gRPC 横切 | 拦截器(≈HTTP 中间件):日志/认证/recover/metrics | [01](../01-grpc-rest/README.md) |
| gRPC 错误 | status code(codes.NotFound…);边界翻译不泄漏;客户端按 code 判断 | [01](../01-grpc-rest/README.md) |
| protobuf 兼容规则 | 字段编号不可复用/不可改类型;加用新编号、删 reserved | [01](../01-grpc-rest/README.md) |
| 横切关注点怎么处理 | 中间件/拦截器洋葱包装(recover/日志/trace/认证/限流/超时) | [02](../02-middleware/README.md) |
| 限流 | 令牌桶(x/time/rate)超限 429;按 key 用 map;多实例用 Redis | [02](../02-middleware/README.md) |
| 重试坑 | 只重可重试错误+指数退避+抖动+幂等+响应 ctx;无脑重试 retry storm | [02](../02-middleware/README.md) |
| 熔断 | 三态 Closed→Open→Half-Open;下游持续失败快速失败防级联;配合重试 | [02](../02-middleware/README.md) |
| 中间件顺序 | recover 最外、trace 早、限流按需在认证前后 | [02](../02-middleware/README.md) |
| 可观测性三支柱 | Metrics(聚合数字/告警)/Trace(单请求路径/定位)/Log(细节);trace_id 串通 | [03](../03-observability/README.md) |
| 跨服务定位 | 分布式 trace:同 trace_id 串 span 树;header(traceparent)/grpc metadata 传播 | [03](../03-observability/README.md) |
| ctx 与可观测性 | trace 挂 ctx 一路传;断 ctx=断 trace | [03](../03-observability/README.md) |
| OTel | 厂商中立 trace/metrics/log 标准+SDK,一次接入换任意后端 | [03](../03-observability/README.md) |
| metrics 方法论 | RED(Rate/Errors/Duration,面向请求)/USE(面向资源) | [03](../03-observability/README.md) |

← 回 [`service-design` 索引](../README.md)
