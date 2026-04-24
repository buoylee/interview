# PerfShop P0 最小实验闭环

> 目标：在完整 PerfShop 三语言系统尚未落地前，先提供一个最低成本的实验标准，让学习者能完成“压测 → 观测 → 定位 → 修复 → 复测”的闭环。

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
curl http://localhost:8080/metrics
```

访问入口：

| 组件 | 地址 |
|------|------|
| App | http://localhost:8080 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000，账号 `admin/admin` |
| MySQL | `localhost:3306`，root 密码 `perfshop123` |

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
│   └── src/
└── load/
    ├── wrk-products.lua
    └── locustfile.py
```

当前实现刻意保持简单：HTTP 服务使用 Python 标准库实现，手动暴露 Prometheus 文本指标，只依赖 MySQL driver。这样学习者可以先关注性能闭环，而不是框架细节。

---

## 4. 必备接口

| 接口 | 用途 |
|------|------|
| `GET /health` | 健康检查 |
| `GET /metrics` | Prometheus 指标 |
| `GET /api/products/{id}` | 商品详情，正常查询 |
| `GET /api/products/search?q=...` | 可制造慢查询 |
| `POST /chaos/cpu?duration=60` | 制造 CPU 热点 |
| `POST /chaos/slow-db?enabled=true` | 切换慢 SQL 场景 |
| `POST /chaos/slow-downstream?delay_ms=1000` | 制造下游超时 |
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

## 7. P0 验收标准

- [ ] 一条命令启动依赖和服务
- [ ] `/health` 返回正常
- [ ] Prometheus target 为 UP
- [ ] Grafana 能看到 QPS、错误率、P95/P99
- [ ] wrk 或 Locust 能稳定压测业务接口
- [ ] 至少一个问题场景能被开启和关闭
- [ ] 至少一个问题能完成“发现 → 定位 → 修复 → 复测”

---

## 8. 与路线阶段的对应关系

| P0 能力 | 对应阶段 |
|---------|----------|
| 启动服务和监控 | P、3 |
| 压测接口 | 3.5、7 |
| 慢 SQL | 9a |
| CPU profile | 4a / 5a / 6a |
| 下游超时 | 10 |
| 复盘记录 | 13、14 |
