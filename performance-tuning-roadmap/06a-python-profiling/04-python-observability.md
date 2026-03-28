# Python 可观测性

## 概述

可观测性（Observability）是生产环境性能管理的基础，包含三大支柱：指标（Metrics）、追踪（Traces）、日志（Logs）。本文介绍 Python 后端服务如何接入这三大支柱，重点是 Prometheus 指标、OpenTelemetry 追踪和 structlog 结构化日志。

## 1. prometheus_client — 指标采集

Prometheus 是云原生监控的事实标准。`prometheus_client` 是 Python 官方客户端库。

### 四种指标类型

```python
from prometheus_client import Counter, Gauge, Histogram, Summary

# Counter — 只增不减的计数器（请求数、错误数）
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

# Gauge — 可增可减的仪表盘（当前连接数、队列长度）
ACTIVE_CONNECTIONS = Gauge(
    'active_connections',
    'Number of active connections'
)

# Histogram — 分布统计（请求延迟、响应大小）
# 自动计算 bucket 分布、sum、count
REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Summary — 类似 Histogram，但计算分位数
REQUEST_SUMMARY = Summary(
    'http_request_duration_summary',
    'HTTP request latency summary'
)
```

### 在 FastAPI 中使用

```python
from fastapi import FastAPI, Request
from prometheus_client import (
    Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
)
from starlette.responses import Response
import time

app = FastAPI()

REQUEST_COUNT = Counter(
    'http_requests_total', 'Total requests', ['method', 'path', 'status']
)
REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds', 'Request latency', ['method', 'path']
)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    REQUEST_COUNT.labels(
        method=request.method,
        path=request.url.path,
        status=response.status_code
    ).inc()
    REQUEST_LATENCY.labels(
        method=request.method,
        path=request.url.path
    ).observe(duration)

    return response

@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

### 独立 HTTP 服务器暴露指标

```python
from prometheus_client import start_http_server

# 在 8000 端口暴露 /metrics
start_http_server(8000)
```

### Push Gateway（短生命周期任务）

对于 Cron Job、批处理等短生命周期任务，Prometheus 拉取模式无法在任务结束后获取指标，需要主动推送：

```python
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

registry = CollectorRegistry()
duration = Gauge('batch_job_duration_seconds', 'Duration of batch job',
                 registry=registry)

with duration.time():
    run_batch_job()

push_to_gateway('pushgateway:9091', job='batch_etl', registry=registry)
```

## 2. OpenTelemetry Python SDK — 分布式追踪

OpenTelemetry (OTel) 是 CNCF 的可观测性标准，提供统一的 API 来采集 traces、metrics 和 logs。

### 手动接入

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

# 配置 TracerProvider
resource = Resource.create({
    "service.name": "order-service",
    "service.version": "1.2.0",
    "deployment.environment": "production",
})

provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(
    OTLPSpanExporter(endpoint="http://otel-collector:4317")
)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# 使用 tracer
tracer = trace.get_tracer(__name__)

async def create_order(order_data):
    with tracer.start_as_current_span("create_order") as span:
        span.set_attribute("order.amount", order_data["amount"])
        span.set_attribute("order.items_count", len(order_data["items"]))

        with tracer.start_as_current_span("validate_order"):
            validate(order_data)

        with tracer.start_as_current_span("save_to_db"):
            order = await db.save(order_data)
            span.set_attribute("order.id", order.id)

        with tracer.start_as_current_span("send_notification"):
            await notify(order)

        return order
```

### MeterProvider — OTel 指标

```python
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(endpoint="http://otel-collector:4317"),
    export_interval_millis=10000,
)
provider = MeterProvider(metric_readers=[reader], resource=resource)
metrics.set_meter_provider(provider)

meter = metrics.get_meter(__name__)

# 创建指标
request_counter = meter.create_counter("http.requests", unit="1")
request_duration = meter.create_histogram("http.request.duration", unit="ms")
```

## 3. 自动 Instrumentation

手动埋点工作量大，OTel 提供自动 instrumentation，零代码修改即可采集常用框架的 traces。

### 安装

```bash
pip install opentelemetry-distro opentelemetry-exporter-otlp
opentelemetry-bootstrap -a install  # 自动检测已安装的库并安装对应的 instrumentation
```

常用的 instrumentation 包：

```bash
pip install opentelemetry-instrumentation-fastapi
pip install opentelemetry-instrumentation-django
pip install opentelemetry-instrumentation-requests
pip install opentelemetry-instrumentation-httpx
pip install opentelemetry-instrumentation-sqlalchemy
pip install opentelemetry-instrumentation-redis
pip install opentelemetry-instrumentation-celery
```

### 零代码启动

```bash
# 用 opentelemetry-instrument 命令包装启动
opentelemetry-instrument \
    --service_name order-service \
    --exporter_otlp_endpoint http://otel-collector:4317 \
    --exporter_otlp_protocol grpc \
    uvicorn main:app --host 0.0.0.0 --port 8000
```

这一条命令就能自动为 FastAPI 路由、SQLAlchemy 查询、HTTP 外部调用等生成 trace spans，不需要修改任何业务代码。

### 在代码中配置自动 instrumentation

```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

# 对 FastAPI 应用自动埋点
FastAPIInstrumentor.instrument_app(app)

# 对 SQLAlchemy 引擎自动埋点
SQLAlchemyInstrumentor().instrument(engine=engine)

# 对 httpx 客户端自动埋点
HTTPXClientInstrumentor().instrument()
```

## 4. structlog — 结构化日志

结构化日志输出 JSON 格式，便于日志系统（ELK、Loki）解析和查询。

### 基本配置

```python
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,        # 合并上下文变量
        structlog.stdlib.filter_by_level,               # 按级别过滤
        structlog.stdlib.add_logger_name,               # 添加 logger 名称
        structlog.stdlib.add_log_level,                 # 添加日志级别
        structlog.stdlib.PositionalArgumentsFormatter(),# 格式化位置参数
        structlog.processors.TimeStamper(fmt="iso"),    # ISO 时间戳
        structlog.processors.StackInfoRenderer(),       # 异常堆栈
        structlog.processors.format_exc_info,           # 异常信息
        structlog.processors.UnicodeDecoder(),          # Unicode 解码
        structlog.processors.JSONRenderer(),            # JSON 输出
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()

# 使用
log.info("order_created", order_id="ORD-123", amount=99.99, items=3)
```

输出：

```json
{
  "event": "order_created",
  "order_id": "ORD-123",
  "amount": 99.99,
  "items": 3,
  "level": "info",
  "timestamp": "2026-03-28T10:30:00.000000Z",
  "logger": "app.orders"
}
```

### 绑定请求上下文

```python
from starlette.middleware.base import BaseHTTPMiddleware
import structlog
import uuid

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # 绑定到 contextvars，后续所有日志自动带上这些字段
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        log = structlog.get_logger()
        log.info("request_started")

        response = await call_next(request)

        log.info("request_completed", status=response.status_code)
        return response
```

这样整个请求链路中的所有日志都会自动带上 `request_id`、`method`、`path`，方便按请求维度聚合查询。

## 5. 实操：给 FastAPI 应用接入 OTel 自动埋点

完整的接入步骤：

```bash
# 1. 安装依赖
pip install \
    opentelemetry-distro \
    opentelemetry-exporter-otlp \
    opentelemetry-instrumentation-fastapi \
    opentelemetry-instrumentation-sqlalchemy \
    opentelemetry-instrumentation-httpx

# 2. 自动检测并安装所有可用的 instrumentation
opentelemetry-bootstrap -a install

# 3. 启动应用（docker-compose 中的配置）
```

docker-compose 配置：

```yaml
services:
  app:
    build: .
    command: >
      opentelemetry-instrument
      --service_name order-service
      --exporter_otlp_endpoint http://otel-collector:4317
      uvicorn main:app --host 0.0.0.0 --port 8000
    environment:
      - OTEL_PYTHON_LOG_CORRELATION=true
      - OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true

  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    ports:
      - "4317:4317"   # gRPC
      - "4318:4318"   # HTTP

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # Jaeger UI
```

启动后，访问 `http://localhost:16686` 打开 Jaeger UI，即可看到每个请求的完整链路，包括数据库查询、外部 HTTP 调用等，每个 span 的耗时一目了然。

## 小结

可观测性的三大支柱需要协同工作：

- **Metrics**（Prometheus）告诉你"出了问题" — 如 p99 延迟突然升高
- **Traces**（OpenTelemetry → Jaeger）告诉你"问题在哪" — 链路中哪个环节慢
- **Logs**（structlog）告诉你"为什么出问题" — 具体的错误信息和上下文

接入顺序建议：先上 Metrics（最低成本、最高价值），再上 Traces（排查慢请求），最后结构化日志（提升日志可搜索性）。
