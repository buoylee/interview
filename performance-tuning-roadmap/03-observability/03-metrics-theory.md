# Metrics 理论

## 概述

Metrics（指标）是可观测性三大支柱中数据密度最高、存储成本最低的一种信号。一条日志可能有几百字节，一条 trace 可能有几 KB，但一个 metric 数据点只需要 (timestamp, value) 十几个字节。这使得指标特别适合做长时间段的趋势分析和实时告警。

---

## 指标四种类型详解

### 1. Counter（计数器）

**语义：累计计数，只增不减，进程重启归零。**

```
http_requests_total{method="GET", path="/api/orders", status="200"}

时间 T1: 1000
时间 T2: 1050    ← 50 个新请求
时间 T3: 1120    ← 70 个新请求
时间 T4: 0       ← 进程重启，归零
时间 T5: 30      ← Prometheus 自动处理 reset
```

**关键用法：**
- Counter 的原始值没有意义（只是个累积数）
- 必须用 `rate()` 或 `increase()` 计算速率
- `rate(http_requests_total[5m])` = 过去 5 分钟的每秒平均请求数

**Java（Micrometer）：**
```java
Counter requestCounter = Counter.builder("http.requests")
    .tag("method", "GET")
    .tag("path", "/api/orders")
    .register(meterRegistry);

requestCounter.increment();
```

**Go（Prometheus client）：**
```go
var requestCounter = prometheus.NewCounterVec(
    prometheus.CounterOpts{
        Name: "http_requests_total",
        Help: "Total HTTP requests",
    },
    []string{"method", "path", "status"},
)

requestCounter.WithLabelValues("GET", "/api/orders", "200").Inc()
```

### 2. Gauge（仪表盘）

**语义：瞬时值，可增可减。**

典型场景：当前活跃连接数、队列深度、内存使用量、线程池活跃线程数。

```
jvm_memory_used_bytes{area="heap"} = 524288000   # 某一时刻的堆内存使用
db_pool_active_connections{pool="main"} = 15      # 当前活跃连接数
```

**与 Counter 的区别：**
- Counter：累积的"总量"，要用 rate() 看速率
- Gauge：当前的"状态"，直接看数值就有意义

```java
// Micrometer Gauge 示例
Gauge.builder("thread.pool.active", executor, ThreadPoolExecutor::getActiveCount)
    .tag("pool", "order-processor")
    .register(meterRegistry);
```

### 3. Histogram（直方图）

**语义：将观测值分配到预定义的桶（bucket）中，记录分布。**

这是性能监控最重要的指标类型，用于衡量延迟分布。

```
# Prometheus 中一个 Histogram 实际存储为多个时间序列：
http_request_duration_seconds_bucket{le="0.005"} = 100   # ≤5ms 的请求数
http_request_duration_seconds_bucket{le="0.01"}  = 150   # ≤10ms 的请求数
http_request_duration_seconds_bucket{le="0.025"} = 200   # ≤25ms 的请求数
http_request_duration_seconds_bucket{le="0.05"}  = 280   # ≤50ms 的请求数
http_request_duration_seconds_bucket{le="0.1"}   = 350   # ≤100ms 的请求数
http_request_duration_seconds_bucket{le="0.25"}  = 400   # ≤250ms 的请求数
http_request_duration_seconds_bucket{le="0.5"}   = 420   # ≤500ms 的请求数
http_request_duration_seconds_bucket{le="1.0"}   = 430   # ≤1s 的请求数
http_request_duration_seconds_bucket{le="+Inf"}  = 435   # 所有请求（总数）
http_request_duration_seconds_sum = 23.5                  # 总耗时
http_request_duration_seconds_count = 435                 # 总请求数（等同于 +Inf bucket）
```

**计算分位数（P99 延迟）：**
```promql
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
```

**桶边界设计要点：**
- 默认桶 `.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10` 不一定适合你的业务
- 根据 SLO 设计桶：如果 P99 目标是 200ms，桶边界应该在 200ms 附近密集分布
- 桶太多增加存储成本，桶太少精度不够

```java
// Micrometer 自定义桶
Timer.builder("http.request.duration")
    .publishPercentileHistogram()
    .sla(Duration.ofMillis(50), Duration.ofMillis(100),
         Duration.ofMillis(200), Duration.ofMillis(500))
    .register(meterRegistry);
```

### 4. Summary（摘要）

**语义：在客户端计算分位数。**

```
# Summary 直接输出分位数
http_request_duration_seconds{quantile="0.5"}  = 0.023   # P50
http_request_duration_seconds{quantile="0.9"}  = 0.056   # P90
http_request_duration_seconds{quantile="0.99"} = 0.148   # P99
http_request_duration_seconds_sum = 23.5
http_request_duration_seconds_count = 435
```

**Summary vs Histogram 对比：**

| 维度 | Histogram | Summary |
|------|-----------|---------|
| 分位数计算位置 | 服务端（PromQL） | 客户端（应用内） |
| 能否跨实例聚合 | 能（合并桶后计算） | 不能（分位数不可加） |
| 精度 | 取决于桶边界 | 精确 |
| 性能开销 | 低 | 较高（需维护排序数据结构） |
| 推荐场景 | 绝大多数场景 | 单实例精确分位数 |

**实践建议：优先用 Histogram。** Summary 最大的问题是不可聚合 —— 当你有 20 个 Pod，你无法把 20 个 P99 合并成全局 P99。

---

## RED 指标实现

RED 方法是微服务监控的黄金标准：

```
R - Rate     (每秒请求数)    → Counter + rate()
E - Errors   (每秒错误数)    → Counter + rate()
D - Duration (请求耗时分布)  → Histogram + histogram_quantile()
```

### 完整实现示例

```java
// Micrometer 实现 RED
@Component
public class OrderMetrics {
    private final Counter requestCounter;
    private final Counter errorCounter;
    private final Timer requestTimer;

    public OrderMetrics(MeterRegistry registry) {
        this.requestCounter = Counter.builder("order.requests.total")
            .description("Total order requests")
            .register(registry);
        this.errorCounter = Counter.builder("order.errors.total")
            .description("Total order errors")
            .register(registry);
        this.requestTimer = Timer.builder("order.request.duration")
            .description("Order request duration")
            .publishPercentileHistogram()
            .register(registry);
    }

    public <T> T recordRequest(Supplier<T> action) {
        requestCounter.increment();
        return requestTimer.record(() -> {
            try {
                return action.get();
            } catch (Exception e) {
                errorCounter.increment();
                throw e;
            }
        });
    }
}
```

**对应的 PromQL：**
```promql
# Rate: 每秒请求数
rate(order_requests_total[5m])

# Error Rate: 错误率
rate(order_errors_total[5m]) / rate(order_requests_total[5m])

# Duration: P99 延迟
histogram_quantile(0.99, rate(order_request_duration_seconds_bucket[5m]))
```

---

## USE 指标实现

USE 方法用于基础设施/资源层面的监控：

```
U - Utilization (利用率)  → Gauge（0-100%）
S - Saturation  (饱和度)  → Gauge（队列深度、等待数）
E - Errors      (错误)    → Counter + rate()
```

| 资源 | Utilization | Saturation | Errors |
|------|------------|------------|--------|
| CPU | `node_cpu_seconds_total` | load average / runqueue | - |
| 内存 | `node_memory_MemAvailable` | swap 使用量 | OOM kill |
| 磁盘 | `node_disk_io_time_seconds` | IO 队列深度 `avgqu-sz` | 磁盘错误 |
| 网络 | 带宽利用率 | TCP retransmit / drop | 网卡错误 |
| 连接池 | active / max | 等待获取连接的线程数 | 获取超时次数 |
| 线程池 | active / max | 队列堆积量 | rejected 次数 |

---

## 指标命名规范

遵循 Prometheus 命名约定：

```
# 格式：<namespace>_<subsystem>_<name>_<unit>

# 好的命名
http_requests_total                        # Counter 以 _total 结尾
http_request_duration_seconds              # 时间单位用基础单位（秒）
process_resident_memory_bytes              # 内存用字节
node_disk_read_bytes_total                 # 磁盘读取字节总数

# 坏的命名
http_requests                              # 缺少 _total 后缀
request_latency_milliseconds              # 应该用秒
orderService_requestCount                  # 不要用驼峰
```

**标签（Label）规范：**
- 标签名用小写 + 下划线：`method`, `status_code`, `service_name`
- 标签值基数要可控：不要把 userId、orderId 当标签
- 一个指标的标签组合数 = 所有标签值的笛卡尔积，基数爆炸会压垮 Prometheus

---

## Micrometer：Java 指标门面

Micrometer 之于 Metrics，就像 SLF4J 之于 Logging —— 它是一个门面，后端可以对接 Prometheus、DataDog、CloudWatch 等。

```java
// Spring Boot Actuator 自动配置 Micrometer
// application.yml
management:
  endpoints:
    web:
      exposure:
        include: prometheus
  metrics:
    tags:
      application: order-service  # 全局标签，所有指标自动添加

// 自定义 MeterBinder
@Component
public class BusinessMetrics implements MeterBinder {
    @Override
    public void bindTo(MeterRegistry registry) {
        Gauge.builder("order.pending.count", orderRepo::countPending)
            .description("Number of pending orders")
            .register(registry);
    }
}
```

---

## 小结

```
Metrics 核心知识体系
├── 四种类型：Counter / Gauge / Histogram / Summary
│   └── 绝大多数场景用 Counter + Histogram 就够了
├── RED 方法：面向服务（Rate / Errors / Duration）
├── USE 方法：面向资源（Utilization / Saturation / Errors）
├── 命名规范：snake_case + 基础单位 + _total 后缀
└── 实现：Micrometer(Java) / prometheus/client_golang(Go) / prometheus_client(Python)
```

理解了指标理论后，下一节我们进入 Prometheus + Grafana 的实操 —— 如何写 PromQL 查询、如何设计 Dashboard。
