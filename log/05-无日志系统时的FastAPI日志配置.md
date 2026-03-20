# 无日志系统时的 FastAPI 日志配置

> 适用场景：没有 ELK/Loki 等集中式日志系统，日志直接写到服务器本地文件，通过 SSH 上去查看。

## 1. 目录规划

```
/var/log/
└── myapp/                      # 每个服务一个目录
    ├── app.log                 # 当前日志文件
    ├── app.log.1               # 轮转后的历史文件
    ├── app.log.2.gz            # 压缩的历史文件
    └── ...
```

所有服务统一放在 `/var/log/` 下，按服务名建子目录。不要散落在各个项目目录里，否则排查时要到处找。

## 2. 依赖安装

```bash
pip install structlog
```

只需要 structlog 一个包，不需要额外依赖。

## 3. 完整配置

```python
# app/core/logging.py

import os
import sys
import logging
import socket
from logging.handlers import RotatingFileHandler

import structlog


# ---- 通过环境变量控制，方便不同环境切换 ----
SERVICE_NAME = os.getenv("SERVICE_NAME", "my-service")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")         # json | console
LOG_OUTPUT = os.getenv("LOG_OUTPUT", "file")          # file | stdout
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", f"/var/log/{SERVICE_NAME}/app.log")

# ---- 轮转配置 ----
LOG_MAX_BYTES = 100 * 1024 * 1024   # 单文件 100MB
LOG_BACKUP_COUNT = 10               # 保留 10 个历史文件（共 ~1GB）


def setup_logging() -> None:
    """应用启动时调用一次。"""

    shared_processors = [
        structlog.contextvars.merge_contextvars,
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

    # 降低第三方库噪音
    for name in ("uvicorn.access", "httpcore", "httpx"):
        logging.getLogger(name).setLevel(logging.WARNING)


def _build_handler() -> logging.Handler:
    if LOG_OUTPUT == "file":
        log_dir = os.path.dirname(LOG_FILE_PATH)
        os.makedirs(log_dir, exist_ok=True)
        return RotatingFileHandler(
            LOG_FILE_PATH,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
    return logging.StreamHandler(sys.stdout)


def _add_service_info(logger, method, event_dict):
    event_dict["service"] = SERVICE_NAME
    event_dict["instance"] = os.getenv("HOSTNAME", socket.gethostname())
    return event_dict


def _add_caller_info(logger, method, event_dict):
    record = event_dict.get("_record")
    if record:
        event_dict["caller"] = f"{record.pathname}:{record.lineno}"
    return event_dict


_SENSITIVE_KEYS = {"password", "token", "secret", "authorization", "cookie"}


def _mask_sensitive_fields(logger, method, event_dict):
    for key in event_dict:
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "***"
    for key in ("phone", "mobile", "tel"):
        if key in event_dict and isinstance(event_dict[key], str) and len(event_dict[key]) == 11:
            v = event_dict[key]
            event_dict[key] = f"{v[:3]}****{v[7:]}"
    return event_dict
```

## 4. 请求中间件

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
        trace_id = request.headers.get("x-trace-id", uuid.uuid4().hex)
        request_id = uuid.uuid4().hex

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

        response.headers["x-trace-id"] = trace_id
        return response
```

## 5. 动态调整日志级别

```python
# app/api/admin.py

import logging
from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])


@router.put("/log-level")
async def set_log_level(level: str, module: str | None = None):
    """
    按模块调整日志级别，避免全局开 DEBUG 导致刷屏。

    示例：
      PUT /admin/log-level?level=debug&module=app.services.order
      PUT /admin/log-level?level=info&module=app.services.order
    """
    numeric_level = getattr(logging, level.upper(), None)
    if numeric_level is None:
        return {"error": f"invalid level: {level}"}
    logging.getLogger(module).setLevel(numeric_level)
    return {"module": module or "root", "level": level.upper()}


@router.get("/log-level")
async def get_log_levels():
    """查看当前哪些模块被调整过级别。"""
    manager = logging.Logger.manager
    result = {"root": logging.getLevelName(logging.getLogger().level)}
    for name, lg in sorted(manager.loggerDict.items()):
        if isinstance(lg, logging.Logger) and lg.level != logging.NOTSET:
            result[name] = logging.getLevelName(lg.level)
    return result
```

## 6. 注册到 FastAPI

```python
# app/main.py

from fastapi import FastAPI
from app.core.logging import setup_logging
from app.core.middleware import RequestLoggingMiddleware
from app.api.admin import router as admin_router

setup_logging()

app = FastAPI()
app.add_middleware(RequestLoggingMiddleware)
app.include_router(admin_router)  # 生产环境务必加鉴权
```

## 7. systemd 服务配置

```ini
# /etc/systemd/system/myapp.service

[Unit]
Description=My FastAPI App
After=network.target

[Service]
User=app
EnvironmentFile=/etc/myapp/env
WorkingDirectory=/opt/myapp
ExecStart=/opt/myapp/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# /etc/myapp/env

SERVICE_NAME=order-service
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_OUTPUT=file
LOG_FILE_PATH=/var/log/order-service/app.log
```

```bash
# 启动
sudo systemctl enable myapp
sudo systemctl start myapp

# 查看 stderr 输出（启动失败等）
sudo journalctl -u myapp -f
```

## 8. 日常排查命令

日志是结构化 JSON，直接 grep 就很好用：

```bash
# 实时查看日志
tail -f /var/log/order-service/app.log

# 只看 ERROR
tail -f /var/log/order-service/app.log | grep '"level": "error"'

# 按 trace_id 追踪完整请求链路
grep "abc123def456" /var/log/order-service/app.log

# 按 trace_id 跨服务查（所有服务日志都在 /var/log/ 下）
grep -r "abc123def456" /var/log/*/app.log

# 查最近 10 分钟的 ERROR（需要日志按时间排序，JSON 格式天然满足）
grep '"level": "error"' /var/log/order-service/app.log | tail -20

# 用 jq 格式化查看（可选安装：apt install jq）
tail -1 /var/log/order-service/app.log | jq .
```

`jq` 是查看 JSON 日志的利器，建议在所有服务器上安装：

```bash
# 只看 ERROR 日志并格式化
cat /var/log/order-service/app.log | jq 'select(.level == "error")'

# 只看某个用户的日志
cat /var/log/order-service/app.log | jq 'select(.user_id == "u_10086")'

# 查看耗时超过 1 秒的请求
cat /var/log/order-service/app.log | jq 'select(.duration_ms > 1000)'
```

## 9. 日志轮转说明

应用内通过 `RotatingFileHandler` 自动轮转：

| 配置 | 值 | 说明 |
|------|-----|------|
| 单文件大小 | 100MB | 超过后自动轮转到 app.log.1 |
| 保留文件数 | 10 | 最多保留 10 个历史文件 |
| 最大磁盘占用 | ~1GB / 服务 | 5 个服务约 5GB，可控 |

轮转后的文件命名：

```
app.log        ← 当前写入
app.log.1      ← 上一个
app.log.2      ← 更早
...
app.log.10     ← 最旧，再轮转时被删除
```

> **注意**：`RotatingFileHandler` 不支持自动压缩历史文件。如果磁盘紧张，可以加一个 cron 定期压缩：
>
> ```bash
> # /etc/cron.daily/compress-logs
> find /var/log/*/app.log.[2-9]* -not -name "*.gz" -exec gzip {} \;
> ```

## 10. 未来迁移到日志系统

当前方案写的是结构化 JSON 文件，未来接入 Loki 时**应用代码不需要任何改动**，只需要在服务器上部署 Promtail 指向日志文件目录即可：

```
现在：  应用 → JSON 文件 → SSH + grep 查看
未来：  应用 → JSON 文件 → Promtail 采集 → Loki → Grafana 查看
                 ↑
           这一步不变
```

这也是为什么从一开始就要写结构化 JSON 而不是纯文本——为将来的无缝迁移做好准备。
