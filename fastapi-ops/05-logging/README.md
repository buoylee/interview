# 05 — 结构化日志

## 目标

日志可检索、可关联 Trace，出事时 30 秒内定位到关键日志行。

## 为什么要结构化日志

```
# 传统日志（难以机器解析）
2024-01-15 10:23:45 ERROR Failed to create order for user 123, amount=99.9

# 结构化日志（JSON，可索引）
{"timestamp":"2024-01-15T10:23:45Z","level":"error","event":"order_create_failed",
 "user_id":123,"amount":99.9,"error":"insufficient_balance","trace_id":"4bf92f35..."}
```

## structlog 配置

```python
import structlog
import logging

def configure_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,     # 合并上下文变量
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.ExceptionRenderer(),    # 异常详情
            structlog.processors.JSONRenderer(),         # 输出 JSON
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )

log = structlog.get_logger()
```

### 使用方式

```python
# 基础
log.info("order_created", order_id=order.id, user_id=user.id)

# 错误（自动捕获异常栈）
try:
    await process_payment(order)
except PaymentError as e:
    log.error("payment_failed", order_id=order.id, exc_info=True)

# 绑定上下文（在请求作用域内，后续日志自动带上）
structlog.contextvars.bind_contextvars(
    request_id=request_id,
    trace_id=get_trace_id(),
    user_id=current_user.id,
)
```

## 请求级上下文注入（中间件）

```python
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request.headers.get("X-Request-ID", str(uuid4())),
            trace_id=get_trace_id(),
            method=request.method,
            path=request.url.path,
        )
        response = await call_next(request)
        return response
```

## 日志级别策略

| 级别 | 使用场景 | 示例 |
|------|---------|------|
| DEBUG | 开发调试，生产不开 | SQL 语句、中间变量 |
| INFO | 正常业务事件 | 订单创建成功、用户登录 |
| WARNING | 可能有问题但不影响主流程 | 重试、降级、缓存未命中 |
| ERROR | 业务失败，需要关注 | 支付失败、数据库错误 |
| CRITICAL | 系统级故障，必须立即处理 | 数据库连接全断、OOM |

## 日志采样（避免日志爆炸）

```python
import random

class SamplingLogger:
    def __init__(self, sample_rate: float = 0.1):
        self.sample_rate = sample_rate
        self.log = structlog.get_logger()

    def debug(self, event, **kwargs):
        if random.random() < self.sample_rate:
            self.log.debug(event, **kwargs)
```

高频接口（如心跳检测）不要每次都记 INFO，改用采样或 DEBUG。

## Loki + Promtail 架构

```
FastAPI → stdout (JSON) → Promtail → Loki ← Grafana
```

### Promtail 配置

```yaml
# promtail-config.yml
scrape_configs:
  - job_name: fastapi
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
    relabel_configs:
      - source_labels: [__meta_docker_container_name]
        target_label: container
    pipeline_stages:
      - json:
          expressions:
            level: level
            trace_id: trace_id
      - labels:
          level:
          trace_id:
```

## LogQL 基础查询

```logql
# 查所有 ERROR 日志
{container="fastapi-app"} | json | level="error"

# 查某 trace 的所有日志
{container="fastapi-app"} | json | trace_id="4bf92f35..."

# 统计每分钟错误数
count_over_time({container="fastapi-app"} | json | level="error" [1m])

# 提取字段并过滤
{container="fastapi-app"} | json | order_id="12345" | line_format "{{.event}}: {{.error}}"
```

## 日志 + Trace 联动

在 Grafana 中配置 Loki 的 Derived Fields：
- 字段名：`trace_id`
- 链接到：Jaeger，URL 模板 `http://jaeger:16686/trace/${__value.raw}`

效果：在日志中点击 trace_id，直接跳转到 Jaeger 对应的 Trace 详情。

## 实践任务

- [ ] 配置 structlog 输出 JSON 格式
- [ ] 实现请求级上下文注入中间件
- [ ] 日志自动带 trace_id（与 04-tracing 联动）
- [ ] 搭建 Loki + Promtail，能在 Grafana 查询日志
- [ ] 配置 Derived Fields 实现日志跳转 Trace

## 关键问题

1. 为什么不直接用 Python 的 `logging` 模块，`structlog` 的优势是什么？
2. `contextvars` 和线程本地变量（`threading.local`）的区别？在 async 环境下哪个是对的？
3. 日志写到 stdout 和写到文件，各有什么优缺点？容器环境推荐哪种？
4. 高并发下日志量过大怎么处理？
