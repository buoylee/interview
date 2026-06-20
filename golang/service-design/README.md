# Go 服务/API 设计 —— 把所有 track 收束成「一个生产级服务」

> C 层最后一条,也是综合题:**怎么搭一个生产级 Go 服务**。把前面的并发、错误、接口、stdlib 全收束到一处——**服务骨架(配置·优雅关闭·健康检查)+ 通信(gRPC/REST)+ 横切(中间件:限流/熔断/重试)+ 可观测性接入**。
>
> 总钥匙:**服务 = 骨架 + 通信 + 横切 + 可观测;优雅关闭和超时是生产命门。**
>
> 设计来源：`docs/superpowers/specs/2026-06-20-go-service-design-track-design.md`｜Go 1.22+

## 怎么用这个 track

1. **按顺序读**：`00` 服务骨架(配置/优雅关闭/健康),`01` gRPC vs REST,`02` 中间件横切,`03` 可观测性接入。
2. **每章固定 7 段**。
3. **双向桥**：对照 **Java**(Spring Boot actuator/graceful、gRPC-java、Resilience4j、Micrometer)。
4. **想答面试**：去 `99-interview-cards/`。

## 章节地图

| 章节 | 主题 | 一句话 |
|---|---|---|
| [`00-service-skeleton/`](00-service-skeleton/) | 服务骨架 | 配置 / **优雅关闭(signal.NotifyContext+Shutdown)** / 信号 / liveness·readiness / slog ← 从这开始 |
| [`01-grpc-rest/`](01-grpc-rest/) | gRPC vs REST | protobuf / gRPC 流·拦截器·status code / 选型(内部 gRPC·对外 REST)/ gRPC-gateway |
| [`02-middleware/`](02-middleware/) | 中间件与横切 | 日志/认证/**限流·重试·熔断**/超时 |
| [`03-observability/`](03-observability/) | 可观测性接入 | OTel 三支柱 / ctx 传播 / RED·USE → 链 `observability/` |
| [`99-interview-cards/`](99-interview-cards/) | 面试卡 | 速答表 + 深题卡 |

每章 7 段：**核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结**。

## 进度地图

| 章节 | 状态 |
|---|---|
| 设计 spec | ✅ |
| 骨架 + 进度地图 | ✅ |
| 00-service-skeleton | ✅ 配置/优雅关闭(NotifyContext+Shutdown)/liveness·readiness/slog |
| 01-grpc-rest | ✅ protobuf/gRPC 流·拦截器·status code/选型/gateway |
| 02-middleware | ✅ 限流(令牌桶)/重试(退避+抖动+幂等)/熔断(三态)/超时 |
| 03-observability | ✅ OTel 三支柱/ctx 传播/RED·USE/链 observability |
| 99-interview-cards | ✅ 速答表(20 条) + 4 张深题卡 |

**本 track 全部完成。C 层(工程化与架构)收官 —— 整个 master 教程完成。**

## 关联已有笔记（复用不重复）

- [`concurrency/07`](../concurrency/07-context/README.md)·[`08`](../concurrency/08-patterns/README.md) — ctx / 优雅关闭 / 限流 / 重试机制
- [`error-handling/04`](../error-handling/04-error-design/README.md)·[`05`](../error-handling/05-concurrent-errors/README.md) — 错误码 / 边界
- [`stdlib/01`](../stdlib/01-net-http/README.md) — net/http server / 超时
- [`design/03`](../design/03-concurrent-api/README.md) — 并发 API 设计
- [`observability/`](../../observability/) — 可观测性深挖(本 track `03` 链过去)
- `java/`、`spring-cloud/`、`spring-boot/` — Spring 服务对标锚点

← 回 [`golang/` master 索引](../README.md)
