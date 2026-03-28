# Prometheus + Grafana 实操

## Prometheus 数据模型

Prometheus 中一切皆时间序列。每个时间序列由 **metric name + labels** 唯一标识：

```
http_requests_total{method="GET", handler="/api/orders", status="200"}
      │                              │
      └── metric name                └── labels（键值对，标识维度）
```

底层存储的是一系列 `(timestamp, value)` 样本点：

```
http_requests_total{method="GET"} → [(t1, 100), (t2, 105), (t3, 112), ...]
```

**关键理解：每组唯一的 label 组合就是一条独立的时间序列。** 如果你有 10 个 method 值 x 50 个 handler 值 x 5 个 status 值 = 2500 条时间序列。这就是"高基数（high cardinality）"问题的根源。

---

## 数据采集：Pull 模型 vs Push 模型

### Pull 模型（Prometheus 默认）

```
Prometheus Server ──── 定时 HTTP GET ────▶ 应用 /metrics 端点
                   （每 15s/30s 拉一次）
```

**优点：**
- Prometheus 掌握采集节奏，不会被推爆
- 应用端无需知道 Prometheus 地址
- 容易判断目标是否存活（拉不到 = 挂了）

### Push 模型（Pushgateway）

```
短生命周期 Job ──── HTTP POST ────▶ Pushgateway ◀──── Prometheus 拉取
```

适用于 CronJob、批处理任务等短生命周期进程。不适合常驻服务。

---

## 服务发现

Prometheus 需要知道从哪里拉取指标：

```yaml
# prometheus.yml

scrape_configs:
  # 1. 静态配置（开发/测试环境）
  - job_name: 'app-server'
    static_configs:
      - targets: ['app1:8080', 'app2:8080']

  # 2. 文件发现（从文件动态加载目标）
  - job_name: 'file-sd'
    file_sd_configs:
      - files: ['/etc/prometheus/targets/*.json']
        refresh_interval: 30s

  # 3. Consul 服务发现
  - job_name: 'consul-sd'
    consul_sd_configs:
      - server: 'consul:8500'
        services: ['order-service', 'payment-service']

  # 4. Kubernetes 服务发现（最常用）
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        target_label: __address__
        regex: (.+)
        replacement: ${1}:$1
```

Kubernetes 环境下，只需在 Pod 上加注解即可被自动发现：

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8080"
    prometheus.io/path: "/metrics"
```

---

## PromQL 实操

### 基础函数

**rate() —— Counter 的每秒平均增长率**

```promql
# 过去 5 分钟每秒请求数
rate(http_requests_total[5m])

# 带维度过滤
rate(http_requests_total{service="order-service", status=~"5.."}[5m])
```

**irate() —— 基于最近两个数据点的瞬时速率**

```promql
# 适合看突刺，但不适合告警（波动大）
irate(http_requests_total[5m])
```

`rate` vs `irate`：告警和 Dashboard 总览用 `rate`（平滑），排查突发问题用 `irate`（敏感）。

**increase() —— 时间窗口内的总增量**

```promql
# 过去 1 小时总请求数
increase(http_requests_total[1h])

# 本质上 increase(x[1h]) ≈ rate(x[1h]) * 3600
```

**histogram_quantile() —— 计算分位数**

```promql
# P99 延迟
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# 按服务分组的 P99
histogram_quantile(0.99,
  sum by (service, le) (
    rate(http_request_duration_seconds_bucket[5m])
  )
)

# P50（中位数）
histogram_quantile(0.5, rate(http_request_duration_seconds_bucket[5m]))
```

### 聚合操作

**sum by() —— 按维度聚合**

```promql
# 每个服务的总 QPS
sum by (service) (rate(http_requests_total[5m]))

# 每个服务的错误 QPS
sum by (service) (rate(http_requests_total{status=~"5.."}[5m]))
```

**topk() —— 取 Top N**

```promql
# QPS 最高的 10 个接口
topk(10, sum by (handler) (rate(http_requests_total[5m])))

# 延迟最高的 5 个服务
topk(5, histogram_quantile(0.99,
  sum by (service, le) (rate(http_request_duration_seconds_bucket[5m]))
))
```

### 常用查询模板

```promql
# ===== RED 指标 =====

# Request Rate（QPS）
sum(rate(http_requests_total{service="$service"}[5m]))

# Error Rate（错误率百分比）
sum(rate(http_requests_total{service="$service", status=~"5.."}[5m]))
/
sum(rate(http_requests_total{service="$service"}[5m])) * 100

# Duration（P50 / P90 / P99）
histogram_quantile(0.99, sum by (le) (
  rate(http_request_duration_seconds_bucket{service="$service"}[5m])
))

# ===== USE 指标 =====

# CPU 使用率（每个 Pod）
rate(container_cpu_usage_seconds_total{pod=~"$service.*"}[5m]) * 100

# 内存使用率
container_memory_working_set_bytes{pod=~"$service.*"}
/ container_spec_memory_limit_bytes{pod=~"$service.*"} * 100

# ===== JVM 指标 =====

# JVM 堆内存使用
jvm_memory_used_bytes{area="heap", service="$service"}

# GC 暂停时间 P99
histogram_quantile(0.99, rate(jvm_gc_pause_seconds_bucket{service="$service"}[5m]))

# GC 频率
rate(jvm_gc_pause_seconds_count{service="$service"}[5m])

# ===== 连接池 =====

# HikariCP 活跃连接
hikaricp_connections_active{pool="$pool"}

# 等待连接的线程
hikaricp_connections_pending{pool="$pool"}

# 连接获取耗时 P99
histogram_quantile(0.99, rate(hikaricp_connections_acquire_seconds_bucket[5m]))
```

---

## Grafana Dashboard 设计

### 按 RED/USE 组织面板

一个服务的标准 Dashboard 布局：

```
┌─────────────────────────────────────────────────────────┐
│ Row 1: Overview (Stat panels)                           │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│ │ QPS      │ │ 错误率   │ │ P99 延迟 │ │ 成功率   │   │
│ │ (Stat)   │ │ (Stat)   │ │ (Stat)   │ │ (Stat)   │   │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
├─────────────────────────────────────────────────────────┤
│ Row 2: RED 指标 (Time Series)                           │
│ ┌─────────────────────┐ ┌─────────────────────────┐     │
│ │ Request Rate        │ │ Error Rate              │     │
│ │ (Time Series)       │ │ (Time Series)           │     │
│ └─────────────────────┘ └─────────────────────────┘     │
│ ┌─────────────────────────────────────────────────┐     │
│ │ Latency (P50 / P90 / P99 三条线)                │     │
│ │ (Time Series)                                    │     │
│ └─────────────────────────────────────────────────┘     │
├─────────────────────────────────────────────────────────┤
│ Row 3: USE 指标                                         │
│ ┌─────────────────────┐ ┌─────────────────────────┐     │
│ │ CPU Usage           │ │ Memory Usage            │     │
│ │ (Time Series)       │ │ (Time Series)           │     │
│ └─────────────────────┘ └─────────────────────────┘     │
├─────────────────────────────────────────────────────────┤
│ Row 4: 延迟热力图                                       │
│ ┌─────────────────────────────────────────────────┐     │
│ │ Request Duration Heatmap                         │     │
│ │ (Heatmap)                                        │     │
│ └─────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

### 常用 Panel 类型

| Panel 类型 | 用途 | 典型指标 |
|-----------|------|---------|
| **Time Series** | 展示指标随时间变化的趋势 | QPS、延迟、CPU |
| **Stat** | 单一数值 + 颜色阈值 | 当前 QPS、错误率、P99 |
| **Gauge** | 百分比仪表盘 | CPU 利用率、内存使用率 |
| **Heatmap** | 延迟分布的时间演变 | Histogram bucket 数据 |
| **Table** | 多维度列表 | Top N 慢接口、错误接口 |
| **Bar Gauge** | 横向对比 | 各服务 QPS 对比 |

### 变量与模板化

通过 Grafana 变量实现一个 Dashboard 模板适配所有服务：

```
Dashboard Settings → Variables

变量名: service
类型: Query
Query: label_values(http_requests_total, service)
Multi-value: true
Include All option: true

变量名: instance
类型: Query
Query: label_values(http_requests_total{service="$service"}, instance)
依赖于 $service 变量
```

在 Panel 的 PromQL 中使用变量：

```promql
# 单选变量
rate(http_requests_total{service="$service"}[5m])

# 多选变量（用正则）
rate(http_requests_total{service=~"$service"}[5m])
```

**Dashboard 模板化最佳实践：**
- 所有 Panel 的查询都引用 `$service` 变量，切换即可看不同服务
- 时间范围用 Grafana 内置的 `$__rate_interval` 替代硬编码的 `[5m]`
- 给每个 Panel 设置有意义的 description，告诉查看者这个图表意味着什么
- 为关键指标的 Stat Panel 设置颜色阈值（绿→黄→红）

```promql
# 使用 $__rate_interval（Grafana 根据采集间隔和时间范围自动计算）
rate(http_requests_total{service=~"$service"}[$__rate_interval])
```

---

## 实用技巧

### 避免 rate() 的陷阱

```promql
# 错误：rate 的范围窗口至少要覆盖 2 个采集周期
# 如果 scrape_interval=15s，那么 rate(x[15s]) 可能没数据
# 至少要 rate(x[30s])，推荐 rate(x[1m]) 或更长

# 正确做法：用 $__rate_interval
rate(http_requests_total[$__rate_interval])
```

### Recording Rules 预计算

高频查询建议创建 Recording Rules，减少查询时的计算开销：

```yaml
# prometheus-rules.yml
groups:
  - name: service-red
    interval: 15s
    rules:
      - record: service:http_requests:rate5m
        expr: sum by (service) (rate(http_requests_total[5m]))

      - record: service:http_errors:rate5m
        expr: sum by (service) (rate(http_requests_total{status=~"5.."}[5m]))

      - record: service:http_duration:p99
        expr: histogram_quantile(0.99,
          sum by (service, le) (rate(http_request_duration_seconds_bucket[5m])))
```

---

## 小结

```
Prometheus + Grafana 实操要点
├── 数据模型：metric name + labels = 唯一时间序列
├── PromQL 核心：rate() / histogram_quantile() / sum by()
├── Dashboard 设计：按 RED/USE 分层，变量模板化
├── 性能优化：Recording Rules 预计算热点查询
└── 注意事项：控制标签基数，rate 窗口 ≥ 2x scrape_interval
```

有了 Metrics 的实时监控能力后，我们还需要分布式链路追踪来解决"一个请求在多个服务之间到底发生了什么"的问题。下一节进入分布式链路追踪。
