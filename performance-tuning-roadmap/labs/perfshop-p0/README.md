# PerfShop P0 / P1-mini 实验闭环

> 目标：在完整 PerfShop 三语言系统尚未落地前，先提供一个最低成本、可连续进阶的实验标准，让学习者完成“压测 → 观测 → 定位 → 修复 → 复测 → 面试复盘”的闭环。

---

## 1. P0 范围

P0 不追求微服务完整性，只要求具备性能训练所需的最小元素：

| 能力 | 最小要求 |
|------|----------|
| 服务 | 任意一门语言实现一个 HTTP 服务 |
| 接口 | 至少有 `/health`、`/metrics`、一个业务接口 |
| 数据库 | MySQL，至少一张有索引和可制造慢查询的表 |
| 观测 | Prometheus 能抓到请求数、错误数、延迟直方图 |
| 可视化 | Grafana 能展示 QPS、错误率、P95/P99 |
| 负载 | wrk 或 Locust 能稳定压测业务接口 |
| 问题注入 | 至少支持慢 SQL、CPU 热点、下游超时或连接池耗尽中的 3 类 |

### 1.1 P1-mini 范围

P1-mini 是 P0 之后的最小分布式扩展，用来覆盖资深工程师面试中更常见的系统性问题：缓存、下游依赖、trace 关联、重试放大和降级。

| 能力 | 最小要求 |
|------|----------|
| 缓存 | App 使用 Redis 做 cache-aside，并暴露 Redis 操作耗时 |
| 下游依赖 | 增加一个独立 downstream 服务，提供推荐接口和独立 `/metrics` |
| 链路关联 | App 和 downstream 透传 `X-Trace-Id`，结构化日志都包含 `trace_id` |
| 降级 | App 调用 downstream 使用明确 timeout，失败时返回稳定 502 |
| 重试 | 支持受控 retry storm 场景，并记录重试次数指标 |
| Chaos | 支持 Redis big key、Redis slow、downstream delay、retry storm |
| 面试产出 | 能解释瓶颈证据、影响面、修复策略、复测结果和工程权衡 |

P1-mini 的非目标：不引入 OpenTelemetry、Jaeger、Loki、Kafka、Kubernetes 或完整服务网格。这里先训练“证据链”和“故障闭环”，避免工具栈过早掩盖问题本身。

---

## 2. 快速启动

当前目录已经包含一个最小可运行骨架：

```bash
docker compose up --build
```

验证：

```bash
curl http://localhost:8080/health
curl http://localhost:8080/api/products/1
curl http://localhost:8080/api/recommendations/1
curl http://localhost:8080/metrics
curl http://localhost:8081/metrics
```

访问入口：

| 组件 | 地址 |
|------|------|
| App | http://localhost:8080 |
| Downstream | http://localhost:8081 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000，账号 `admin/admin` |
| MySQL | `localhost:3306`，root 密码 `perfshop123` |
| Redis | `localhost:6379` |

如果本机端口已被其他项目占用，可以用 Compose override 临时改端口。验证时优先使用 `127.0.0.1`，避免某些环境下 `localhost` 优先走 IPv6 造成误判。

---

## 3. 推荐目录

```text
perfshop-p0/
├── README.md
├── docker-compose.yml
├── prometheus/
│   └── prometheus.yml
├── grafana/
│   └── provisioning/
├── sql/
│   └── init.sql
├── app/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
├── downstream/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
└── load/
    ├── wrk-products.lua
    └── locustfile.py
```

当前实现刻意保持简单：HTTP 服务使用 Python 标准库实现，手动暴露 Prometheus 文本指标，只依赖 MySQL driver 和 Redis client。这样学习者可以先关注性能闭环，而不是框架细节。

---

## 4. 必备接口

| 接口 | 用途 |
|------|------|
| `GET /health` | 健康检查 |
| `GET /metrics` | Prometheus 指标 |
| `GET /api/products/{id}` | 商品详情，正常查询 |
| `GET /api/products/search?q=...` | 可制造慢查询 |
| `GET /api/recommendations/{product_id}` | App 调用 downstream 获取推荐 |
| `POST /chaos/cpu?duration=60` | 制造 CPU 热点 |
| `POST /chaos/slow-db?enabled=true` | 切换慢 SQL 场景 |
| `POST /chaos/slow-downstream?delay_ms=1000` | 制造下游超时 |
| `POST /chaos/redis-big-key?enabled=true` | 制造 Redis big key 读取 |
| `POST /chaos/redis-slow?enabled=true` | 制造 Redis 操作变慢 |
| `POST /chaos/downstream-delay?delay_ms=1000` | 在 downstream 注入延迟 |
| `POST /chaos/retry-storm?enabled=true` | 开启 App 到 downstream 的重试放大 |
| `POST /chaos/reset` | 关闭所有 chaos |

---

## 5. 必备指标

Prometheus 至少需要这些指标：

```text
http_requests_total{method,path,status}
http_request_duration_seconds_bucket{method,path}
http_request_duration_seconds_count{method,path}
http_request_duration_seconds_sum{method,path}
process_cpu_seconds_total
process_resident_memory_bytes
db_query_duration_seconds_bucket{query}
redis_operation_duration_seconds_bucket{operation}
app_downstream_requests_total{target,status}
app_downstream_request_duration_seconds_bucket{target}
app_downstream_retries_total{target}
downstream_http_requests_total{method,path,status}
downstream_http_request_duration_seconds_bucket{method,path}
```

如果暂时没有语言 SDK，可以先手动输出 Prometheus 文本格式，但最终应接入正式客户端库。

---

## 6. 三个入门场景

### 场景 1：慢 SQL

目标：让学习者完成数据库瓶颈闭环。

流程：

```text
POST /chaos/slow-db?enabled=true
→ wrk -t2 -c20 -d30s http://localhost:8080/api/products/search?q=alpha
→ Grafana/Prometheus 看到 P99 升高
→ DB 查询耗时指标确认慢查询
→ EXPLAIN 看到全表扫描
→ 加索引或改查询
→ 用同样压测复测
```

产物：

- 慢查询日志
- EXPLAIN 前后对比
- P99 前后对比

### 场景 2：CPU 热点

目标：让学习者完成 profiling 闭环。

流程：

```text
POST /chaos/cpu?duration=60
→ 压测业务接口
→ CPU 升高、QPS 下降
→ 采集 profile
→ 找到热点函数
→ 修改或关闭热点
→ 复测
```

产物：

- CPU profile
- top 3 热点说明
- 优化前后 QPS / P99

### 场景 3：下游超时

目标：让学习者完成分布式延迟闭环。

流程：

```text
POST /chaos/slow-downstream?delay_ms=1000
→ 压测业务接口
→ P99 升高或错误率升高
→ HTTP 延迟指标确认请求时间被下游等待放大
→ 调整 timeout / fallback / circuit breaker
→ 复测快速失败是否生效
```

产物：

- HTTP 延迟和错误率对比
- 超时配置表
- 修复前后错误率和 P99 对比

---

## 7. P1-mini 进阶场景

这些场景用于把 P0 的单服务闭环扩展成面试中更有区分度的分布式诊断闭环。建议按顺序完成，每个场景都保留压测命令、PromQL、日志片段、根因判断和复测结果。

### 场景 4：Redis cache-aside 与慢缓存

目标：让学习者理解缓存命中、缓存退化和数据库回退之间的边界。

流程：

```text
GET /api/products/1
→ 第二次请求命中 Redis
→ Prometheus 查看 redis_operation_duration_seconds
→ POST /chaos/redis-slow?enabled=true
→ 再次压测 /api/products/1
→ 区分 DB 慢、Redis 慢、App 等待时间
→ POST /chaos/reset
→ 用同样压测复测
```

关键观察：

- App 返回仍应稳定，不因为 Redis 慢而返回随机错误。
- `redis_operation_duration_seconds_bucket{operation="get"}` 应能反映慢缓存。
- 如果 Redis 操作失败，日志中应有 `redis_failure` 和对应 `trace_id`。

面试产出：

- 说明 cache-aside 的读路径和写入时机。
- 解释“缓存慢”和“缓存未命中导致 DB 压力升高”的差异。
- 给出 Redis timeout、TTL、big key、fallback 的工程取舍。

### 场景 5：Downstream timeout 与快速失败

目标：让学习者完成跨服务延迟定位，并能解释 timeout 和降级策略。

流程：

```text
POST /chaos/downstream-delay?delay_ms=1000
→ curl -H "X-Trace-Id: p1-timeout-demo" http://localhost:8080/api/recommendations/1
→ App 返回 502 downstream unavailable
→ App metrics 查看 app_downstream_request_duration_seconds 和 app_downstream_requests_total{status="error"}
→ Downstream metrics 查看 downstream_http_request_duration_seconds
→ App/downstream 日志用 trace_id 关联同一次请求
→ POST /chaos/reset
→ 复测恢复
```

关键观察：

- App 的 timeout 应小于 downstream delay，因此请求应快速失败。
- App 层看到的是 502，downstream 层可能看到客户端断开后的 499。
- 同一个 `trace_id` 必须能连接 App failure 日志和 downstream 请求日志。

面试产出：

- 说明为什么不能无限等待下游。
- 给出 timeout、fallback、circuit breaker、bulkhead 的适用边界。
- 解释 App 指标和 Downstream 指标看到的状态码为什么可能不同。

### 场景 6：Retry storm 与放大效应

目标：让学习者看到重试如何把一个慢下游放大成系统性故障。

流程：

```text
POST /chaos/downstream-delay?delay_ms=1000
POST /chaos/retry-storm?enabled=true
→ 压测 http://localhost:8080/api/recommendations/1
→ 查看 app_downstream_retries_total 是否增长
→ 对比 downstream_http_requests_total 的请求数量
→ 关闭 retry storm，保留下游 delay
→ 对比错误率、P99 和下游请求数
→ POST /chaos/reset
```

关键观察：

- App 侧一次用户请求可能产生多次 downstream 请求。
- `app_downstream_retries_total` 和 downstream QPS 应能证明重试放大。
- 重试不应该用于已经超时且不可快速恢复的依赖。

面试产出：

- 说明重试预算、指数退避、jitter、幂等性和限流。
- 解释什么时候应该快速失败，什么时候允许重试。
- 给出复测数据，证明修复后下游压力下降。

---

## 8. 学习顺序建议

1. 先跑通 P0：健康检查、业务接口、Prometheus target、基础 Grafana。
2. 完成慢 SQL：用 DB 指标和 EXPLAIN 给出可复现证据。
3. 完成 CPU 热点：用 profile 证明热点，而不是只看 CPU 百分比。
4. 完成 P1-mini Redis：区分缓存命中、缓存慢、DB 回退。
5. 完成 P1-mini downstream：用 trace_id 关联 App 和下游。
6. 完成 retry storm：量化重试放大，给出限流或退避策略。
7. 用模板沉淀报告：`templates/performance-investigation-record.md`、`templates/load-test-report.md`、`templates/postmortem.md`。

资深工程师面试中，答案不应停留在“加缓存、加索引、调参数”。合格复盘至少要包含：假设、证据、影响面、修复方案、风险、复测数据和长期防护。

---

## 9. P0 验收标准

- [ ] 一条命令启动依赖和服务
- [ ] `/health` 返回正常
- [ ] Prometheus target 为 UP
- [ ] Grafana 能看到 QPS、错误率、P95/P99
- [ ] wrk 或 Locust 能稳定压测业务接口
- [ ] 至少一个问题场景能被开启和关闭
- [ ] 至少一个问题能完成“发现 → 定位 → 修复 → 复测”

---

## 10. P1-mini 验收标准

- [ ] Redis、downstream、App、Prometheus、Grafana 能由 `docker compose up --build` 启动
- [ ] `/api/products/{id}` 能使用 Redis cache-aside，并暴露 Redis 操作耗时
- [ ] `/api/recommendations/{product_id}` 能调用 downstream，并在失败时稳定返回 502
- [ ] App 和 downstream 的响应头、结构化日志都包含可关联的 `X-Trace-Id` / `trace_id`
- [ ] Prometheus 能抓到 `perfshop-p0` 和 `perfshop-downstream` 两个 target
- [ ] Redis slow 和 Redis big key 场景能开启、观察、关闭
- [ ] Downstream delay 能制造 App timeout，并能用日志和指标解释 502 / 499
- [ ] Retry storm 能让 `app_downstream_retries_total` 增长，并能证明下游请求被放大
- [ ] 每个场景都有压测命令、PromQL 或指标截图、日志证据、根因判断和复测结论

---

## 11. 与路线阶段的对应关系

| P0 能力 | 对应阶段 |
|---------|----------|
| 启动服务和监控 | P、3 |
| 压测接口 | 3.5、7 |
| 慢 SQL | 9a |
| CPU profile | 4a / 5a / 6a |
| 下游超时 | 10 |
| 复盘记录 | 13、14 |

| P1-mini 能力 | 对应阶段 |
|--------------|----------|
| Redis cache-aside / big key / slow operation | 9b、11 |
| Downstream timeout / fallback | 10、11 |
| Retry storm / retry budget | 10 |
| Trace ID 关联日志 | 3、10 |
| 多服务指标对比 | 3、13 |
| 面试级复盘 | 13、14 |
