# FastAPI 日志配置

基于 `structlog` 实现结构化日志，通过环境变量在 JSON / 可读格式之间切换。

## 1. 依赖安装

```bash
pip install structlog python-json-logger uvicorn
```

## 2. 日志初始化

```python
# app/core/logging.py

import os
import sys
import logging
import socket
import structlog


SERVICE_NAME = os.getenv("SERVICE_NAME", "my-service")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_OUTPUT = os.getenv("LOG_OUTPUT", "stdout")  # stdout | file
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "/var/log/app/app.log")
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")     # json | console


def setup_logging() -> None:
    """应用启动时调用一次。"""

    # --- structlog 处理链 ---
    shared_processors = [
        structlog.contextvars.merge_contextvars,       # 自动合并 context 变量 (trace_id 等)
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_service_info,
        _add_caller_info,
        _mask_sensitive_fields,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if LOG_FORMAT == "console":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # --- stdlib logging (捕获 uvicorn、第三方库日志) ---
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            *shared_processors,
            renderer,
        ],
    )

    handler = _build_handler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(LOG_LEVEL)

    # 降低第三方库日志级别，避免噪音
    for name in ("uvicorn.access", "httpcore", "httpx"):
        logging.getLogger(name).setLevel(logging.WARNING)


def _build_handler() -> logging.Handler:
    """根据 LOG_OUTPUT 环境变量决定输出目标。"""
    if LOG_OUTPUT == "file":
        from logging.handlers import RotatingFileHandler
        os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
        return RotatingFileHandler(
            LOG_FILE_PATH,
            maxBytes=100 * 1024 * 1024,  # 100MB
            backupCount=5,
            encoding="utf-8",
        )
    return logging.StreamHandler(sys.stdout)


def _add_service_info(logger, method, event_dict):
    """注入 service 和 instance 字段。"""
    event_dict["service"] = SERVICE_NAME
    event_dict["instance"] = os.getenv("HOSTNAME", socket.gethostname())
    return event_dict


def _add_caller_info(logger, method, event_dict):
    """注入调用位置 (文件:行号)。"""
    # structlog 的 CallsiteParameterAdder 也能做，但这里精简实现
    record = event_dict.get("_record")
    if record:
        event_dict["caller"] = f"{record.pathname}:{record.lineno}"
    return event_dict


# ============================================================
# 敏感信息过滤
# ============================================================

_SENSITIVE_KEYS = {"password", "token", "secret", "authorization", "cookie"}


def _mask_sensitive_fields(logger, method, event_dict):
    """自动脱敏敏感字段。"""
    for key in event_dict:
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "***"
    # 手机号脱敏 (匹配 phone 类字段)
    for key in ("phone", "mobile", "tel"):
        if key in event_dict and isinstance(event_dict[key], str) and len(event_dict[key]) == 11:
            v = event_dict[key]
            event_dict[key] = f"{v[:3]}****{v[7:]}"
    return event_dict
```

## 3. 请求日志中间件

自动为每个请求注入 `trace_id`、记录请求耗时。

```python
# app/core/middleware.py

import time
import uuid
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


logger = structlog.stdlib.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # 从上游获取 trace_id，没有则生成
        trace_id = request.headers.get("x-trace-id", uuid.uuid4().hex)
        request_id = uuid.uuid4().hex

        # 绑定到 contextvars，后续所有日志自动携带
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            trace_id=trace_id,
            request_id=request_id,
        )

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "unhandled exception",
                method=request.method,
                path=request.url.path,
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "request completed",
                method=request.method,
                path=request.url.path,
                status_code=getattr(response, "status_code", 500),
                duration_ms=duration_ms,
                client_ip=request.client.host if request.client else None,
            )

        # 将 trace_id 传递给下游
        response.headers["x-trace-id"] = trace_id
        return response
```

## 4. 注册到 FastAPI

```python
# app/main.py

from fastapi import FastAPI
from app.core.logging import setup_logging
from app.core.middleware import RequestLoggingMiddleware

setup_logging()

app = FastAPI()
app.add_middleware(RequestLoggingMiddleware)
```

## 5. 业务代码中使用

```python
# app/services/order.py

import structlog

logger = structlog.stdlib.get_logger()


async def create_order(user_id: str, items: list) -> dict:
    logger.info("creating order", user_id=user_id, item_count=len(items))

    try:
        order = await do_create(user_id, items)
    except InsufficientInventoryError as e:
        # WARNING: 业务异常，可预期，不需要人工介入
        logger.warning("inventory insufficient", user_id=user_id, error=str(e))
        raise
    except Exception as e:
        # ERROR: 非预期异常，需要排查
        logger.error("create order failed", user_id=user_id, error=str(e))
        raise

    logger.info("order created", user_id=user_id, order_id=order["id"])
    return order
```

无需手动传 `trace_id` —— 中间件已通过 `contextvars` 绑定，所有日志自动携带。

## 6. 调用其他服务时传递 trace_id

```python
# app/core/http_client.py

import httpx
import structlog


async def call_service(url: str, **kwargs) -> httpx.Response:
    ctx = structlog.contextvars.get_contextvars()
    headers = kwargs.pop("headers", {})
    headers["x-trace-id"] = ctx.get("trace_id", "")

    async with httpx.AsyncClient() as client:
        return await client.request(url=url, headers=headers, **kwargs)
```

## 7. 动态调整日志级别

不需要重启服务，通过管理接口即可切换。**支持按模块精确控制**，避免全局开 DEBUG 导致日志刷屏。

```python
# app/api/admin.py

import logging
from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])


@router.put("/log-level")
async def set_log_level(level: str, module: str | None = None):
    """
    动态调整日志级别。

    - PUT /admin/log-level?level=debug&module=app.services.order
      只对 order 模块开启 DEBUG，其他模块不受影响

    - PUT /admin/log-level?level=info&module=app.services.order
      排查完毕，恢复该模块为 INFO

    - PUT /admin/log-level?level=debug
      不传 module 则调整全局级别（慎用）
    """
    numeric_level = getattr(logging, level.upper(), None)
    if numeric_level is None:
        return {"error": f"invalid level: {level}"}

    target = logging.getLogger(module)  # module=None 时等同于 root logger
    target.setLevel(numeric_level)
    return {
        "module": module or "root",
        "level": level.upper(),
    }


@router.get("/log-level")
async def get_log_levels():
    """查看当前所有非默认级别的 logger，方便确认哪些模块被调整过。"""
    manager = logging.Logger.manager
    result = {"root": logging.getLevelName(logging.getLogger().level)}
    for name, logger in sorted(manager.loggerDict.items()):
        if isinstance(logger, logging.Logger) and logger.level != logging.NOTSET:
            result[name] = logging.getLevelName(logger.level)
    return result
```

### 使用流程

```bash
# 1. 发现 order 接口有问题，只对 order 模块开 DEBUG
curl -X PUT "http://localhost:8000/admin/log-level?level=debug&module=app.services.order"

# 2. 查看日志，只有 app.services.order 的 DEBUG 出现，其他模块不受影响

# 3. 排查完毕，恢复
curl -X PUT "http://localhost:8000/admin/log-level?level=info&module=app.services.order"

# 4. 确认当前哪些模块被调整过
curl "http://localhost:8000/admin/log-level"
```

这依赖 Python logging 的层级机制：`app.services.order` 的 logger 设为 DEBUG 时，只有该模块及其子模块输出 DEBUG 日志，`app.services.user`、`app.api` 等仍然保持 INFO。

> 注意：这个接口应当做好鉴权，不要暴露在公网。
