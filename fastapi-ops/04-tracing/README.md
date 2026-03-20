# 04 — 分布式追踪：OpenTelemetry + Jaeger

## 目标

一个请求慢了，能精确定位是哪一步慢：是查数据库、调外部服务、还是业务逻辑本身。

## 核心概念

```
Trace（一次完整请求的生命周期）
  └── Span（一个操作单元）
        ├── 属性（attributes）：key-value 附加信息
        ├── 事件（events）：时间戳 + 消息
        └── 状态（status）：OK / ERROR
```

### Context Propagation（关键！）
跨服务传播 Trace 上下文，通过 HTTP Header 传递：
```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```
格式：`版本-TraceID-SpanID-Flags`

## 接入 FastAPI

```bash
pip install opentelemetry-sdk \
            opentelemetry-instrumentation-fastapi \
            opentelemetry-instrumentation-sqlalchemy \
            opentelemetry-instrumentation-redis \
            opentelemetry-instrumentation-httpx \
            opentelemetry-exporter-otlp
```

### 初始化

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

def setup_tracing(app: FastAPI, engine):
    provider = TracerProvider()
    exporter = OTLPSpanExporter(endpoint="http://jaeger:4317")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)
```

### 手动 Span

```python
tracer = trace.get_tracer(__name__)

async def create_order(data: OrderCreate):
    with tracer.start_as_current_span("create_order") as span:
        span.set_attribute("order.user_id", data.user_id)
        span.set_attribute("order.amount", float(data.amount))

        # 子操作自动成为子 Span（SQLAlchemy 已自动埋点）
        order = await db.save(data)

        span.add_event("order_saved", {"order_id": str(order.id)})
        return order
```

### 关联日志与 Trace

```python
from opentelemetry import trace

def get_trace_id() -> str:
    span = trace.get_current_span()
    if span.is_recording():
        return format(span.get_span_context().trace_id, '032x')
    return ""

# 在日志中自动注入 trace_id
import structlog
structlog.configure(
    processors=[
        lambda _, __, event_dict: {
            **event_dict,
            "trace_id": get_trace_id()
        },
        ...
    ]
)
```

## Jaeger UI 使用

### 常用分析操作
1. **搜索慢请求**：Service + Operation + Min Duration 过滤
2. **Trace 甘特图**：横轴时间，纵轴 Span 层级，一眼看出哪步慢
3. **比较两个 Trace**：找出正常 vs 慢请求的差异
4. **依赖拓扑**：自动生成服务调用图

### 识别问题模式

```
串行调用（N+1问题）：
  [          总请求          ]
    [sql] [sql] [sql] [sql]   ← 每个 sql 都等上一个完成

并行调用（正常）：
  [          总请求          ]
    [sql1]
    [sql2]                    ← 并发执行
    [http_call]

慢外部调用：
  [          总请求          ]
    [db query: 5ms]
    [external_api: 2000ms]    ← 外部依赖慢
```

## 采样策略

全量采集在高 QPS 下代价太大，需要采样：

```python
from opentelemetry.sdk.trace.sampling import (
    TraceIdRatioBased,
    ParentBased,
)

# 采样 10% 的请求
sampler = ParentBased(root=TraceIdRatioBased(0.1))

# 尾部采样（Jaeger 支持）：先全采，后端过滤只保留慢请求和错误
# 配置在 Jaeger Collector 端
```

## Docker Compose 配置

```yaml
jaeger:
  image: jaegertracing/all-in-one:latest
  ports:
    - "16686:16686"   # Jaeger UI
    - "4317:4317"     # OTLP gRPC
    - "4318:4318"     # OTLP HTTP
  environment:
    - COLLECTOR_OTLP_ENABLED=true
```

## 实践任务

- [ ] 接入 FastAPI + SQLAlchemy 自动埋点
- [ ] 添加业务级手动 Span（create_order）
- [ ] 在 Jaeger UI 找到一次完整请求的 Trace
- [ ] 模拟 N+1 查询，在 Trace 中识别它
- [ ] 实现日志中自动带上 trace_id

## 关键问题

1. `TraceID` 和 `SpanID` 的关系？一个 Trace 有几个 SpanID？
2. 如何保证跨服务的 Trace 是同一个？（Context Propagation 的机制）
3. 采样率设为 10%，慢请求会被漏掉吗？怎么解决？
4. 自动埋点的 SQLAlchemy Span 和手动 Span 的父子关系是怎么建立的？
