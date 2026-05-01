# PerfShop 实验契约

> 目标：明确哪些实验当前可以直接运行，哪些需要手工补环境，哪些属于目标态示例，避免学习者把路线图中的完整 PerfShop 设想误解为当前仓库已经全部实现。

## 1. 为什么需要实验契约

这套路线上有两类内容：

- 当前仓库已经提供的最小可运行实验。
- 用来说明目标能力的完整生产级场景。

两者都重要，但用途不同。学习者应该先用当前可运行的 P0 完成单服务闭环，再用 P1-mini 完成缓存和下游依赖闭环，最后逐步扩展到 P1 后续能力和 P2。

## 2. 实验成熟度

| 层级 | 状态 | 目标 | 当前说明 |
|------|------|------|----------|
| P0 | 当前可运行 | 单服务、MySQL、Prometheus、Grafana、wrk/Locust、3 类故障注入 | 已在 `labs/perfshop-p0/` 提供 |
| P1-mini | 当前可运行 | Redis cache-aside、downstream、trace_id 关联、timeout、retry storm | 已在 `labs/perfshop-p0/` 提供 |
| P1 | 后续扩展 | Kafka、OpenTelemetry/Jaeger、日志聚合、连接池耗尽、更多故障注入 | 文档可先描述目标，练习需标注环境要求 |
| P2 | 目标态 | Java / Go / Python 三语言同构 PerfShop，多服务链路和完整 runtime 对比 | 用于路线终局设计，不应写成当前 P 阶段必需 |

## 3. 练习状态标签

后续新增或修订练习时，建议在练习标题或说明中标注：

| 标签 | 含义 | 学习者动作 |
|------|------|------------|
| `Runnable now` | 当前仓库可直接运行 | 按文档命令执行并记录结果 |
| `Runnable with manual setup` | 需要学习者先安装工具、改配置或准备服务 | 先完成前置条件，再执行练习 |
| `Target-state example` | 用于展示完整生产场景或未来 PerfShop 形态 | 重点学习排查思路，不假设当前仓库可直接运行 |

## 4. 当前 P0 能力

当前 `labs/perfshop-p0/` 提供：

- Python 标准库 HTTP 服务。
- MySQL 商品表和可制造慢查询的数据。
- Prometheus 指标暴露。
- Grafana datasource provisioning。
- wrk 和 Locust 压测脚本。
- 慢 SQL、CPU 热点、下游等待三类故障开关。

P0 的完成标准是学习者能走完：

```text
压测 -> 观测 -> 假设 -> 证据 -> 定位 -> 修复或关闭故障 -> 复测 -> 记录
```

## 5. 当前 P1-mini 能力

当前 `labs/perfshop-p0/` 还提供 P1-mini：

- Redis 服务和 App cache-aside。
- Redis slow 和 big key chaos。
- 独立 downstream 推荐服务。
- App 到 downstream 的 timeout 和失败返回 502。
- App/downstream 响应头与结构化日志中的 `X-Trace-Id` / `trace_id` 关联。
- Downstream delay 和 retry storm。
- Redis、App downstream、downstream 服务三类 Prometheus 指标。

P1-mini 的完成标准是学习者可以证明单点问题如何放大成跨组件延迟或错误率上升。

## 6. 后续 P1 扩展目标

P1-mini 之后，P1 应优先补齐会显著提高排查训练价值、但当前还不属于一键可运行的组件：

- OpenTelemetry Trace 和 Jaeger。
- 日志聚合。
- 连接池耗尽。
- Kafka consumer lag 或等价消息积压场景。
- 更完整的限流、熔断、降级和隔离策略。

后续 P1 的完成标准是学习者可以把 P1-mini 的 trace_id / metrics 证据升级为更完整的 Trace、日志平台和容量治理证据。

## 7. P2 扩展目标

P2 才承担完整三语言 PerfShop：

- Java 服务覆盖 JVM、GC、线程、连接池、Netty 或 Web 框架调优。
- Go 服务覆盖 pprof、goroutine、runtime、net/http 或 gRPC 调优。
- Python 服务覆盖 GIL、asyncio、FastAPI/Django、py-spy、tracemalloc。
- 三语言提供同构业务接口，便于同一问题在不同 runtime 下对比。

P2 的完成标准是学习者能解释同一性能问题在不同语言 runtime 下的诊断差异。

## 8. 写作规则

- 不把 P2 目标态写成阶段 P 的硬性前置。
- 所有新练习都要说明运行状态标签。
- 目标态示例可以保留，但要明确它训练的是思路、机制和面试表达。
- 当前可运行命令必须指向仓库真实存在的目录或文件。
