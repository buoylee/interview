"""生產級結構化日誌設定(對應 logging/ 第 01/03/05/06 章)。

只用標準庫:logging + contextvars + json。重點示範:
- dictConfig 一次設定,handler 只掛 root(05:杜絕雙重發射)
- contextvars 帶 request_id,filter 注入每筆 record(03:async 安全的關聯 ID)
- JSON formatter,msg 固定、變數成欄位(03:可被機器 filter/aggregate)
"""

import contextvars
import json
import logging
from datetime import datetime, timezone

# 03:用 contextvars 而非全域變數 —— 每個請求(協程)有自己的副本,async 不串味
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """把當前 request_id 注入每筆 record(這樣每行日誌自動帶上,不用手動傳)。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """輸出一行 JSON。msg 維持固定字串,extra={...} 的欄位自動展開成 JSON 欄位。"""

    # 標準 LogRecord 屬性,輸出時要排除(只留我們關心的 + 使用者塞的 extra)
    _RESERVED = {
        "args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName",
        "levelname", "levelno", "lineno", "module", "msecs", "message", "msg", "name",
        "pathname", "process", "processName", "relativeCreated", "stack_info",
        "thread", "threadName", "taskName", "request_id",
    }

    def format(self, record: logging.LogRecord) -> str:
        out = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        # 展開使用者透過 extra={...} 塞進來的業務欄位(order_id、uid、latency_ms ...)
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                out[key] = value
        # 04:有異常就帶完整堆疊(含 cause chain 的 "Caused by" / "during handling")
        if record.exc_info:
            out["error"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False)


# 05:dictConfig 一次到位。handler 只掛 root;業務 logger 只設 level、不掛 handler,靠 propagate。
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": RequestIdFilter}},
    "formatters": {"json": {"()": JsonFormatter}},
    "handlers": {
        "stdout": {  # 06:寫 stdout,rotation/傳輸交給平台(12-factor)
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["request_id"],
            "stream": "ext://sys.stdout",
        }
    },
    "root": {"handlers": ["stdout"], "level": "INFO"},  # 唯一 handler 在 root
    "loggers": {
        "myapp": {"level": "INFO"},          # 業務 logger:只設 level,不掛 handler
        "uvicorn.access": {"level": "WARNING"},  # 馴服框架自帶 logger,避免重複/噪音
        "httpx": {"level": "WARNING"},       # 第三方 client 的 INFO 太吵,壓到 WARNING
    },
}
