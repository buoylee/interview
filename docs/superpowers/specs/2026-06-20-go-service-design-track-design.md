# Go 服务/API 设计 track —— 设计 spec

> 日期：2026-06-20｜目录：`golang/service-design/`｜上级：umbrella spec。C 层第五条(最后一条)。

## 背景与目标

把前面所有 track 收束到「写一个生产级 Go 服务」:**服务骨架(配置/优雅关闭/信号/健康检查)**、**gRPC vs REST(选型 + protobuf + 拦截器 + 错误码)**、**中间件横切(日志/认证/限流/重试/熔断)**、**可观测性接入(OTel,链 observability/)**。架构师面试的「你怎么搭一个服务」综合题。

## 核心设计决策

- 形式:4 章,照搬模板(7 段 + 面试卡)。
- 主线钥匙:**「服务 = 骨架(配置·优雅关闭·健康)+ 通信(gRPC/REST)+ 横切(中间件)+ 可观测;优雅关闭和超时是生产命门」**。
- 双向桥:Spring Boot(actuator/graceful shutdown)、gRPC-java、Resilience4j(熔断/限流/重试)、Micrometer/OTel。
- 实战进正文:signal.NotifyContext + srv.Shutdown 优雅关闭、liveness/readiness、slog 结构化日志、protobuf/gRPC 四种流/拦截器/status code 映射、gRPC vs REST 选型、限流(rate.Limiter 令牌桶)/熔断(gobreaker)/重试(退避+抖动+幂等)、OTel 三支柱 + ctx 传播。
- 互链:[`concurrency/07·08`](ctx/优雅关闭/限流/重试)、[`error-handling/04·05`](错误码/边界)、[`stdlib/01`](net/http server)、[`design/03`](并发 API)、[`observability/`](可观测性深度)。

## 章节地图

| 章节 | 主题 | 一句话 |
|---|---|---|
| `00-service-skeleton/` | 服务骨架 | 配置(env/12-factor)/ 启动·优雅关闭(signal.NotifyContext+Shutdown)/ 信号 / liveness·readiness 健康检查 / slog |
| `01-grpc-rest/` | gRPC vs REST | protobuf / gRPC 四种流·拦截器·status code 映射 / REST / 选型(内部 gRPC·对外 REST)/ gRPC-gateway |
| `02-middleware/` | 中间件与横切 | 日志/认证/限流(令牌桶)/重试(退避+抖动+幂等)/熔断(gobreaker)/超时 |
| `03-observability/` | 可观测性接入 | OTel 三支柱(trace/metrics/log)/ ctx 传播 / RED·USE / 链 observability track |
| `99-interview-cards/` | 面试卡 | 速答表 + 深题卡 |

## 交付节奏
1 spec → 2 骨架 → 3 四章 + 面试卡。

## 验收
- 00 能写优雅关闭(signal.NotifyContext + Shutdown)、讲 liveness vs readiness。
- 01 能讲 gRPC vs REST 选型、protobuf、拦截器、错误码映射。
- 02 能讲限流/熔断/重试的实现与坑(幂等/退避抖动)。
- 03 能讲 OTel 三支柱 + ctx 传播,且链到 observability track。

## 非目标
- 不重讲可观测性原理(链 observability/ track 深挖)。
- 不重讲限流/重试/优雅关闭的并发机制(链 concurrency/08)。
- 不绑定具体框架(gin/kratos 等只点到)。
