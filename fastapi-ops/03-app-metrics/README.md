# 03 — 应用级指标：Prometheus + Grafana

## 目标

让服务"说出"自己的状态。能用 PromQL 回答：当前 P99 延迟是多少？哪个接口错误率在上升？

## Prometheus 数据模型

### 四种指标类型

| 类型 | 特点 | 典型用途 |
|------|------|---------|
| **Counter** | 只增不减，重启归零 | 请求总数、错误总数 |
| **Gauge** | 可增可减 | 当前连接数、内存使用量 |
| **Histogram** | 分桶统计，可算分位数 | 请求延迟分布 |
| **Summary** | 客户端计算分位数 | 分位数（不推荐，无法聚合） |

### 关键理解
- Counter 本身没意义，要配合 `rate()` 看速率
- Histogram 的 bucket 划分影响分位数精度（`le` 标签）
- 标签（label）是高基数的坑：不要把 user_id 放进标签

## 接入 FastAPI

### 方案一：自动埋点（快速上手）

```bash
pip install prometheus-fastapi-instrumentator
```

```python
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()
Instrumentator().instrument(app).expose(app)
```

自动获得：
- `http_requests_total` — 请求计数（按 method / handler / status）
- `http_request_duration_seconds` — 延迟直方图

### 方案二：手动埋点（精细控制）

```python
from prometheus_client import Counter, Histogram, Gauge

# 业务指标
orders_created = Counter(
    "orders_created_total",
    "Total orders created",
    ["status"]  # success / failed
)

order_processing_time = Histogram(
    "order_processing_seconds",
    "Order processing duration",
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

active_connections = Gauge(
    "db_active_connections",
    "Active database connections"
)

# 使用
with order_processing_time.time():
    result = await create_order(data)
orders_created.labels(status="success").inc()
```

## PromQL 核心语法

### 必会查询

```promql
# 过去 5 分钟的请求 QPS
rate(http_requests_total[5m])

# 错误率（5xx / 总请求）
rate(http_requests_total{status=~"5.."}[5m])
/ rate(http_requests_total[5m])

# P99 延迟
histogram_quantile(0.99,
  rate(http_request_duration_seconds_bucket[5m])
)

# 按接口分组的 P99
histogram_quantile(0.99,
  sum by (handler, le) (
    rate(http_request_duration_seconds_bucket[5m])
  )
)

# 当前数据库连接数
db_active_connections
```

### `rate` vs `irate`
- `rate`：时间窗口内的平均速率，适合告警（平滑）
- `irate`：最后两个点的瞬时速率，适合图表（响应快）

## Grafana Dashboard 设计

### RED 方法（面向用户体验）

| 指标 | 含义 | Panel 类型 |
|------|------|-----------|
| **R**ate | 每秒请求数（QPS） | Time series |
| **E**rror | 错误率 | Stat + Time series |
| **D**uration | P50 / P95 / P99 延迟 | Time series |

### USE 方法（面向资源）

| 指标 | 含义 |
|------|------|
| **U**tilization | CPU / 内存 / 连接池使用率 |
| **S**aturation | 队列长度、等待数 |
| **E**rrors | 系统错误计数 |

## 告警规则设计

```yaml
# alertmanager rules
groups:
  - name: fastapi
    rules:
      - alert: HighErrorRate
        expr: |
          rate(http_requests_total{status=~"5.."}[5m])
          / rate(http_requests_total[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Error rate > 5% for 2 minutes"

      - alert: SlowP99
        expr: |
          histogram_quantile(0.99,
            rate(http_request_duration_seconds_bucket[5m])
          ) > 1.0
        for: 5m
        annotations:
          summary: "P99 latency > 1s"
```

## Docker Compose 搭建观测栈

```yaml
version: '3.8'
services:
  app:
    build: .
    ports: ["8000:8000"]

  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports: ["9090:9090"]

  grafana:
    image: grafana/grafana
    ports: ["3000:3000"]
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

## 实践任务

- [ ] 接入自动埋点，能在 Prometheus 看到 http_requests_total
- [ ] 手动添加订单创建的 Counter 和 Histogram
- [ ] 在 Grafana 做出 RED Dashboard
- [ ] 编写 P99 > 1s 的告警规则

## 关键问题

1. 为什么不推荐把 `user_id` 作为 Prometheus 标签？
2. `rate(counter[5m])` 和直接用 counter 值的区别？
3. Histogram 的精度由什么决定？如何选择 bucket 边界？
4. 为什么 Summary 无法在多实例间聚合？
