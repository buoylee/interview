# Capstone 样例报告：P1-mini 下游超时与重试放大

> 目标：给学习者一份“资深工程师级别的成品样例”。本文使用 `labs/perfshop-p0/` 当前可运行的 P1-mini 场景，示范如何从现象、指标、日志、假设、根因、修复、复测到面试表达。

> 说明：报告中的数值是样例写法。实际练习时必须替换成自己机器上的压测输出、PromQL 结果和日志片段。

---

## 1. 场景摘要

| 项目 | 内容 |
|------|------|
| 场景 | 推荐接口 P99 升高并出现 502 |
| 系统 | PerfShop P1-mini |
| 入口接口 | `GET /api/recommendations/1` |
| 相关组件 | App、downstream recommendations service、Prometheus、结构化日志 |
| 注入故障 | `POST /chaos/downstream-delay?delay_ms=1000`，随后开启 `POST /chaos/retry-storm?enabled=true` |
| 主要结论 | downstream 延迟超过 App timeout，App 快速失败返回 502；开启 retry storm 后，一次用户请求产生多次下游请求，放大 downstream 压力 |

---

## 2. 环境和复现命令

```bash
cd performance-tuning-roadmap/labs/perfshop-p0
docker compose up --build
```

验证服务：

```bash
curl http://localhost:8080/health
curl http://localhost:8081/health
curl http://localhost:8080/api/recommendations/1
curl http://localhost:8080/metrics
curl http://localhost:8081/metrics
```

如果本机端口冲突，可以使用 Compose override 改端口。排查报告中必须写清最终访问地址，避免复测时环境不一致。

---

## 3. 基线

基线命令：

```bash
wrk -t2 -c20 -d30s http://localhost:8080/api/recommendations/1
```

样例基线：

```text
QPS: 820 req/s
P50: 18ms
P95: 42ms
P99: 70ms
Error rate: 0%
```

基线观察：

- App `app_downstream_requests_total{target="recommendations",status="200"}` 持续增长。
- Downstream `downstream_http_requests_total{path="/api/recommendations/{product_id}",status="200"}` 持续增长。
- 日志中同一个 `trace_id` 能在 App 和 downstream 两侧找到。

---

## 4. 故障注入

先注入下游延迟：

```bash
curl -X POST "http://localhost:8080/chaos/downstream-delay?delay_ms=1000"
curl -H "X-Trace-Id: capstone-delay-001" \
  http://localhost:8080/api/recommendations/1
```

预期：

```text
HTTP 502
{"error": "downstream unavailable"}
```

再开启重试放大：

```bash
curl -X POST "http://localhost:8080/chaos/retry-storm?enabled=true"
curl -H "X-Trace-Id: capstone-retry-001" \
  http://localhost:8080/api/recommendations/1
```

最后复位：

```bash
curl -X POST http://localhost:8080/chaos/reset
```

---

## 5. 假设与证据

| 假设 | 需要的证据 | 实际观察 | 结论 |
|------|------------|----------|------|
| 数据库慢导致推荐接口慢 | `db_query_duration_seconds` 同步升高 | 推荐接口不访问 DB，DB 指标无明显变化 | 排除 |
| Redis 慢导致推荐接口慢 | `redis_operation_duration_seconds` 在推荐请求窗口升高 | 推荐接口路径没有 Redis 访问；Redis 指标无异常 | 排除 |
| Downstream 延迟导致 App timeout | App downstream duration 接近 timeout；App 返回 502；downstream duration 接近 1000ms | App 记录 downstream failure，downstream 记录同 trace_id 的长耗时请求 | 成立 |
| Retry storm 放大下游压力 | `app_downstream_retries_total` 增长；downstream 请求数高于入口请求数 | 开启 retry 后 retry counter 增长，下游请求数增加 | 成立 |

---

## 6. 关键指标

App 侧 PromQL：

```promql
rate(app_downstream_requests_total{target="recommendations"}[1m])
```

```promql
histogram_quantile(
  0.99,
  rate(app_downstream_request_duration_seconds_bucket{target="recommendations"}[5m])
)
```

```promql
increase(app_downstream_retries_total{target="recommendations"}[5m])
```

Downstream 侧 PromQL：

```promql
rate(downstream_http_requests_total{path="/api/recommendations/{product_id}"}[1m])
```

```promql
histogram_quantile(
  0.99,
  rate(downstream_http_request_duration_seconds_bucket{path="/api/recommendations/{product_id}"}[5m])
)
```

样例观察：

```text
故障前：
App downstream error rate: 0%
Retry count increase: 0
Downstream P99: 45ms

downstream delay 后：
App downstream error rate: 100%
App response: 502
Downstream P99: ~1000ms

retry storm 后：
Retry count increase: > 0
Downstream request rate 高于入口 request rate
```

---

## 7. 日志证据

App 日志样例：

```json
{"service":"app","event":"downstream_failure","trace_id":"capstone-delay-001","target":"recommendations","method":"GET","path":"/api/recommendations/1","error":"TimeoutError"}
```

Downstream 日志样例：

```json
{"service":"downstream","trace_id":"capstone-delay-001","method":"GET","path":"/api/recommendations/{product_id}","status":499,"duration_ms":1001.2}
```

状态码解释：

- App 返回 502：上游对用户表达“下游不可用”。
- Downstream 记录 499：App 已经 timeout 并断开连接，downstream 后续写响应时发现客户端已离开。
- 这不是状态码矛盾，而是同一次请求在不同组件视角下的结果。

---

## 8. 根因机制

根因不是“App 代码慢”，而是下游依赖超过了 App 的 timeout budget。

机制链路：

```text
downstream delay = 1000ms
App downstream timeout < 1000ms
App 等待到 timeout 后快速失败
用户看到 502
downstream 继续处理，写回时客户端已经断开
downstream 记录 499
```

开启 retry storm 后：

```text
一次用户请求
→ App 第一次调用 downstream timeout
→ App 重试
→ 每次重试都命中同一个慢下游
→ 下游请求数被放大
→ 下游更忙，恢复更慢
```

这说明重试不是无条件收益。对已经超时且短时间不可恢复的依赖，重试会把局部延迟放大成系统压力。

---

## 9. 修复与缓解方案

短期缓解：

- 关闭 retry storm：`POST /chaos/retry-storm?enabled=false` 或 `POST /chaos/reset`。
- 保持 App timeout 小于用户可接受延迟，避免无限等待。
- 对推荐接口使用 fallback，例如返回空推荐或缓存推荐。

中期修复：

- 引入 retry budget：只对少量、幂等、可能瞬时恢复的错误重试。
- 使用指数退避和 jitter，避免同时重试。
- 对 downstream 设置并发隔离或 bulkhead，避免拖垮 App 主业务。

长期治理：

- 建立 timeout budget：入口 SLA、App timeout、downstream timeout、DB timeout 必须有层级关系。
- 为 `app_downstream_retries_total`、downstream error rate、P99 建告警。
- 在发布前用 P1-mini retry storm 场景做性能回归。
- 把推荐服务降级策略写入 runbook。

---

## 10. 复测验证

复位：

```bash
curl -X POST http://localhost:8080/chaos/reset
wrk -t2 -c20 -d30s http://localhost:8080/api/recommendations/1
```

样例复测：

```text
QPS: 810 req/s
P50: 19ms
P95: 45ms
P99: 73ms
Error rate: 0%
Retry count increase: 0
```

验证结论：

- 关闭 downstream delay 和 retry storm 后，推荐接口恢复到基线附近。
- App downstream error rate 回到 0。
- `app_downstream_retries_total` 不再增长。
- Downstream P99 回到正常区间。

---

## 11. 3 分钟面试回答

“我用 PerfShop P1-mini 做过一次下游超时和重试放大的排查。现象是推荐接口出现 502，P99 明显升高。我先看入口 RED，确认错误集中在 `/api/recommendations/{id}`，再看 App 的 downstream 指标，发现 `app_downstream_requests_total{status="error"}` 增长，同时 downstream 的请求耗时接近 1 秒。

我用 `trace_id` 关联 App 和 downstream 日志：App 记录 downstream timeout 并返回 502，downstream 记录同一个 trace_id 的 499，说明 App 已经超时断开。然后我开启 retry storm，观察到 `app_downstream_retries_total` 增长，downstream 请求数高于入口请求数，证明重试把慢下游问题放大了。

修复上我会先关闭重试和故障注入，用 fallback 快速恢复；长期会设计 timeout budget、retry budget、指数退避和 jitter，并对 downstream error、retry count、P99 建告警。复测时用同样压测确认 P99、错误率和 retry count 回到基线。”

---

## 12. 8 分钟深挖要点

如果面试官继续追问，可以展开：

- 为什么先排除 DB 和 Redis：推荐接口路径不访问 DB，Redis 指标没有同步升高。
- 为什么 502 和 499 可以同时出现：上游用户视角和下游服务视角不同。
- 为什么 timeout 不能越长越好：长 timeout 会占用 worker、连接和内存，把等待变成排队。
- 什么请求适合重试：幂等、短暂错误、低成本、有限预算。
- 什么请求不适合重试：已经超过 timeout budget、不可幂等、下游处于饱和、请求成本高。
- 如何防止重试风暴：retry budget、退避、jitter、限流、熔断、隔离池。
- Staff 视角如何治理：统一客户端配置、依赖分级、SLO、dashboard、runbook、发布前性能门禁。

---

## 13. 自评分

| Rubric 维度 | 是否覆盖 | 证据 |
|-------------|----------|------|
| 现象和影响面 | 覆盖 | 推荐接口 502、P99 升高 |
| 分层排查路径 | 覆盖 | 入口 RED -> App downstream -> downstream metrics -> logs |
| 可证伪假设 | 覆盖 | DB、Redis、downstream、retry 四个假设 |
| 根因机制 | 覆盖 | timeout budget 和 retry amplification |
| 修复方案 | 覆盖 | reset、fallback、retry budget、bulkhead |
| 验证复盘 | 覆盖 | 复测 QPS/P99/error/retry count |

按 `SENIOR-RUBRIC.md`，这份报告达到资深回答标准；如果补充容量模型、发布门禁和跨团队 owner，可以扩展到 Staff 版本。
