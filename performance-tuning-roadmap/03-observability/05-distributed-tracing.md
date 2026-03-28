# 分布式链路追踪

## 为什么需要分布式追踪

在单体应用中，一个请求从入口到出口都在同一个进程内，看日志和堆栈就能排查问题。但在微服务架构下：

```
用户请求 → API Gateway → Order Service → Payment Service → Notification Service
                              │                │
                              ▼                ▼
                         Inventory Service   Bank API
                              │
                              ▼
                          Redis Cache
```

一个"下单"请求可能经过 6+ 个服务。当用户反馈"下单慢"时：
- 哪个服务慢？
- 是网络延迟还是服务处理慢？
- 是每次都慢还是偶尔慢？
- 某个下游服务超时重试了几次？

没有链路追踪，这些问题只能靠 traceId grep 日志 + 人脑拼接时间线。分布式追踪将整个调用链自动串联起来，用可视化的方式展示每一跳的耗时。

---

## 核心概念

### Trace

一个 Trace 代表一个完整的请求链路，由一组 Span 组成。

### Span

一个 Span 代表链路中的一个操作单元（一次 RPC 调用、一次数据库查询、一个函数执行）。

```
Trace: abc123
│
├── Span A: API Gateway (0-350ms)
│   ├── Span B: Order Service (10-300ms)
│   │   ├── Span C: Redis GET (15-20ms)
│   │   ├── Span D: Inventory Service (25-150ms)
│   │   │   └── Span E: MySQL Query (30-140ms)
│   │   └── Span F: Payment Service (155-290ms)
│   │       └── Span G: Bank API Call (160-280ms)
│   └── Span H: Notification Service (305-340ms)
```

每个 Span 包含：
- **TraceId**：全局唯一，贯穿整个链路
- **SpanId**：当前操作的唯一标识
- **ParentSpanId**：父 Span 的 ID，构成树状结构
- **OperationName**：操作名（如 `POST /api/orders`）
- **StartTime / Duration**：开始时间和持续时间
- **Tags/Attributes**：键值对元数据（`http.method=POST`, `db.type=mysql`）
- **Events/Logs**：时间点事件（如 `exception thrown at T+50ms`）
- **Status**：OK / ERROR

### SpanContext

SpanContext 是跨进程传播的核心数据结构，包含 TraceId、SpanId、TraceFlags（如采样标记）等。它通过 HTTP Header 或 gRPC Metadata 在服务间传递。

### Baggage

Baggage 是附加在 SpanContext 上的业务键值对，会沿着调用链传播到所有下游服务。例如把 `userId` 放在 Baggage 中，所有下游服务都可以读取，无需通过 API 参数传递。

**注意：Baggage 会增加每次跨进程调用的网络开销，只放必要的少量数据。**

---

## OpenTelemetry 架构

OpenTelemetry（OTel）是 CNCF 项目，统一了 OpenTracing 和 OpenCensus，现在是可观测性的事实标准。

```
┌───────────────────────────────────────────────────┐
│                  应用进程                           │
│                                                     │
│  ┌─────────┐    ┌──────────┐    ┌───────────────┐  │
│  │ OTel API │───▶│ OTel SDK │───▶│   Exporter    │  │
│  │ (接口)   │    │ (实现)    │    │ (OTLP/Jaeger) │  │
│  └─────────┘    └──────────┘    └───────┬───────┘  │
│       ▲                                  │          │
│       │ 自动/手动埋点                     │          │
│  ┌────┴─────┐                            │          │
│  │ 业务代码  │                            │          │
│  └──────────┘                            │          │
└──────────────────────────────────────────┼──────────┘
                                           │ OTLP (gRPC/HTTP)
                                           ▼
                                  ┌────────────────┐
                                  │ OTel Collector  │
                                  │ ┌────────────┐ │
                                  │ │ Receivers   │ │  ← 接收数据
                                  │ │ Processors  │ │  ← 过滤/采样/转换
                                  │ │ Exporters   │ │  ← 输出到后端
                                  │ └────────────┘ │
                                  └───────┬────────┘
                                          │
                          ┌───────────────┼───────────────┐
                          ▼               ▼               ▼
                     ┌─────────┐   ┌───────────┐   ┌──────────┐
                     │  Jaeger  │   │   Tempo   │   │ 自建存储  │
                     └─────────┘   └───────────┘   └──────────┘
```

**四层架构的分工：**

| 层 | 职责 | 说明 |
|----|------|------|
| API | 定义接口 | 只有接口定义，无实现，零依赖 |
| SDK | 实现采集逻辑 | 采样器、SpanProcessor、资源检测 |
| Collector | 独立的数据管道 | 接收、处理、转发，支持多后端 |
| Exporter | 输出适配 | OTLP、Jaeger、Zipkin 等格式 |

---

## 采样策略

生产环境不可能 100% 采集所有 Trace（数据量太大），需要采样。

### Head-based Sampling（头部采样）

在请求入口就决定是否采集这条 Trace。

```
请求进入 → 随机数 < 采样率？→ 是 → 标记采集，全链路采集
                              → 否 → 标记不采集，全链路跳过
```

```yaml
# OTel SDK 配置
otel:
  traces:
    sampler:
      type: parentbased_traceidratio
      arg: 0.1   # 10% 采样率
```

**优点：** 简单，开销小。
**缺点：** 采样是随机的，可能漏掉真正有问题的请求。

### Tail-based Sampling（尾部采样）

先采集所有 Trace，在 Collector 层根据完整 Trace 的特征决定保留哪些。

```yaml
# OTel Collector 配置
processors:
  tail_sampling:
    decision_wait: 10s
    policies:
      - name: errors
        type: status_code
        status_code: {status_codes: [ERROR]}  # 保留所有错误请求
      - name: slow-requests
        type: latency
        latency: {threshold_ms: 1000}          # 保留所有慢请求（>1s）
      - name: default
        type: probabilistic
        probabilistic: {sampling_percentage: 5} # 正常请求采 5%
```

**优点：** 能保证错误请求和慢请求 100% 被采集。
**缺点：** Collector 需要缓存完整 Trace 等待所有 Span 到达，内存和 CPU 开销大。

### 实践建议

| 场景 | 推荐策略 |
|------|---------|
| 开发/测试环境 | 100% 采集（AlwaysOn） |
| 低流量生产服务 | Head-based 50-100% |
| 高流量生产服务 | Tail-based（错误+慢请求 100%，正常 1-5%） |
| 极高流量（>10w QPS） | Head-based 1% + 错误强制采集 |

---

## Jaeger vs SkyWalking vs Zipkin 对比

| 特性 | Jaeger | SkyWalking | Zipkin |
|------|--------|-----------|--------|
| 语言 | Go | Java | Java |
| CNCF 阶段 | 毕业项目 | 顶级项目 | 非 CNCF |
| 协议支持 | OTLP, Jaeger, Zipkin | 自有 + OTLP | Zipkin, OTLP |
| 存储后端 | ES, Cassandra, Kafka | ES, MySQL, BanyanDB | ES, MySQL, Cassandra |
| 自动埋点 | 依赖 OTel SDK | 自带 Java Agent（字节码增强） | 依赖 OTel SDK |
| 服务拓扑 | 需要额外组件 | 内置，开箱即用 | 无 |
| 运维复杂度 | 中 | 较高（组件多） | 低 |
| 适用场景 | 云原生，OTLP 标准化 | Java 为主，需要完整 APM | 轻量级，快速上手 |

**选型建议：**
- 标准化、多语言 → Jaeger + OTel
- Java 为主、需要开箱即用的 APM → SkyWalking
- 简单场景、快速验证 → Zipkin

---

## 上下文传播机制

链路追踪的核心难题是：如何将 SpanContext 从一个进程传递到另一个进程？

### W3C TraceContext（推荐标准）

```http
GET /api/orders HTTP/1.1
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
tracestate: congo=t61rcWkgMzE
```

`traceparent` 格式：`{version}-{trace-id}-{parent-id}-{trace-flags}`

### B3（Zipkin 传统格式）

```http
GET /api/orders HTTP/1.1
X-B3-TraceId: 4bf92f3577b34da6a3ce929d0e0e4736
X-B3-SpanId: 00f067aa0ba902b7
X-B3-ParentSpanId: ...
X-B3-Sampled: 1
```

### 传播流程

```
Service A                          Service B
┌──────────────┐                  ┌──────────────┐
│ 创建 Span A   │                  │ 提取 Context  │
│ 注入 Context  │ ── HTTP/gRPC ──▶│ 创建 Span B   │
│ 到 Header    │                  │ parent = A    │
└──────────────┘                  └──────────────┘
   Inject(context, carrier)          Extract(carrier)
```

---

## 实操：接入 OTel SDK

### Java（Spring Boot）

```xml
<!-- pom.xml -->
<dependency>
    <groupId>io.opentelemetry.instrumentation</groupId>
    <artifactId>opentelemetry-spring-boot-starter</artifactId>
    <version>2.4.0</version>
</dependency>
```

```yaml
# application.yml
otel:
  service:
    name: order-service
  exporter:
    otlp:
      endpoint: http://otel-collector:4317
  traces:
    sampler:
      type: parentbased_traceidratio
      arg: "0.1"
```

或者使用 Java Agent（零代码修改）：

```bash
java -javaagent:opentelemetry-javaagent.jar \
     -Dotel.service.name=order-service \
     -Dotel.exporter.otlp.endpoint=http://collector:4317 \
     -Dotel.traces.sampler=parentbased_traceidratio \
     -Dotel.traces.sampler.arg=0.1 \
     -jar app.jar
```

### Go

```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/sdk/trace"
    "go.opentelemetry.io/otel/sdk/resource"
    semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
)

func initTracer() (*trace.TracerProvider, error) {
    exporter, err := otlptracegrpc.New(context.Background(),
        otlptracegrpc.WithEndpoint("otel-collector:4317"),
        otlptracegrpc.WithInsecure(),
    )
    if err != nil {
        return nil, err
    }

    tp := trace.NewTracerProvider(
        trace.WithBatcher(exporter),
        trace.WithSampler(trace.ParentBased(trace.TraceIDRatioBased(0.1))),
        trace.WithResource(resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceName("order-service"),
        )),
    )
    otel.SetTracerProvider(tp)
    return tp, nil
}

// 手动创建 Span
func ProcessOrder(ctx context.Context, orderId string) error {
    tracer := otel.Tracer("order-processor")
    ctx, span := tracer.Start(ctx, "ProcessOrder")
    defer span.End()

    span.SetAttributes(attribute.String("order.id", orderId))
    // ... 业务逻辑
    return nil
}
```

### Python

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "order-service"})
provider = TracerProvider(resource=resource)
exporter = OTLPSpanExporter(endpoint="otel-collector:4317", insecure=True)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

# 使用
tracer = trace.get_tracer("order-processor")

def process_order(order_id: str):
    with tracer.start_as_current_span("ProcessOrder") as span:
        span.set_attribute("order.id", order_id)
        # ... 业务逻辑
```

---

## 小结

```
分布式链路追踪要点
├── 核心概念：Trace → Span 树 → SpanContext 跨进程传播
├── 标准：OpenTelemetry（统一 API/SDK/Collector）
├── 采样：Head-based（简单）vs Tail-based（智能，保留异常）
├── 后端：Jaeger（标准化）/ SkyWalking（Java APM）/ Zipkin（轻量）
└── 传播协议：W3C TraceContext（推荐）/ B3（兼容）
```

Logs + Metrics + Traces 构成了完整的可观测性体系。下一节我们讨论如何基于这些数据建立有效的告警和 On-call 机制。
