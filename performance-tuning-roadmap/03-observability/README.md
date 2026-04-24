# 阶段 3：可观测性体系建设学习指南

> 本阶段目标：让服务从“只能登录机器看命令”变成“可以持续观测”。学完后，能用日志、指标和 Trace 解释一次请求从进入到返回的关键过程。

---

## 学习顺序

| 顺序 | 文件 | 学习重点 |
|------|------|----------|
| 1 | [03-metrics-theory.md](./03-metrics-theory.md) | Counter、Gauge、Histogram、Summary，先建立指标模型 |
| 2 | [04-prometheus-grafana.md](./04-prometheus-grafana.md) | PromQL、Dashboard、RED/USE 面板 |
| 3 | [01-structured-logging.md](./01-structured-logging.md) | 结构化日志、TraceID、字段规范 |
| 4 | [02-log-infrastructure.md](./02-log-infrastructure.md) | ELK/Loki、日志采集、查询 |
| 5 | [05-distributed-tracing.md](./05-distributed-tracing.md) | Trace/Span、上下文传播、采样 |
| 6 | [06-alerting-oncall.md](./06-alerting-oncall.md) | 告警分级、Alertmanager、Runbook |

建议先学指标，因为指标最适合建立稳定的性能基线。

---

## 本阶段主线

三大支柱的分工：

| 支柱 | 回答的问题 |
|------|------------|
| Metrics | 现在是否异常？趋势如何？影响范围多大？ |
| Logs | 具体发生了什么事件？请求上下文是什么？ |
| Traces | 时间花在哪个服务、哪个依赖、哪个 Span？ |

学习时不要追求一次搭完所有平台。先让一个服务具备 RED 指标，再补日志和 Trace。

---

## 最小完成标准

学完后应该能做到：

- 服务暴露 `/metrics`
- Prometheus target 为 UP
- Grafana 有 RED 面板：QPS、错误率、P95/P99
- 日志中包含 trace_id 或 request_id
- Jaeger 中能看到一条跨组件 Trace
- 能写出一条基于用户影响的告警规则

---

## 本阶段产物

建议留下：

- 一张 RED Dashboard
- 一条 PromQL 查询 P99 延迟
- 一条结构化日志样例
- 一条 Trace 截图或 Span 列表
- 一条告警规则和对应 Runbook 草稿

---

## 常见误区

| 误区 | 正确做法 |
|------|----------|
| 指标 label 随便加 user_id | 避免高基数 label |
| 只看平均延迟 | 看 P95/P99 和错误率 |
| 日志没有 TraceID | 无法把日志和 Trace 串起来 |
| 告警按原因设计太多 | 优先按用户可感知症状告警 |
| Dashboard 面板越多越好 | 初期只保留 RED + 关键资源指标 |

---

## 下一阶段衔接

阶段 3 解决“能看见”。阶段 3.5 会解决“如何稳定制造负载”，让后续 profiling 和压测有意义。

