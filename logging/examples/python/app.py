"""FastAPI 生產級日誌範例 —— 把 logging/ 六章紀律組裝在一個服務裡。

端點:GET /users/{id}
- id <= 0        → 參數非法,記 INFO(正常業務,不是 ERROR),回 400
- id == 13       → 查無此人,記 INFO(正常業務),回 404
- id == 99       → 模擬下游故障,repo 包裝往上拋 → 頂層記一次完整堆疊,回 500
- 其他           → 成功,記 INFO,回 200

跑法:
    pip install -r requirements.txt
    uvicorn app:app --port 8080 --no-access-log
    curl -H 'X-Request-ID: demo-1' localhost:8080/users/42
驗證:python smoke_test.py
"""

import logging
import logging.config
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from log_config import LOGGING_CONFIG, request_id_var

logging.config.dictConfig(LOGGING_CONFIG)
log = logging.getLogger("myapp")  # 03:用具名 logger,靠 propagate 到 root 的單一 handler

app = FastAPI()


# --- 模擬資料層(04:中間層只「包裝 + 往上拋」,不在這裡記 log)---
class UserNotFound(Exception):
    """可預期的業務狀況 —— 不是 ERROR(01)。"""


class RepositoryError(Exception):
    """不可預期的基礎設施失敗 —— 會冒泡到頂層被記成 ERROR。"""


def fetch_user(uid: int) -> dict:
    if uid == 99:
        try:
            raise ConnectionError("connection reset by peer")  # 模擬下游/DB 故障
        except ConnectionError as e:
            # 04:包裝成業務異常,from e 保留 cause chain,但「不在這裡記」
            raise RepositoryError(f"load user failed, uid={uid}") from e
    if uid == 13:
        raise UserNotFound(uid)
    return {"id": uid, "name": f"user{uid}"}


# --- 02/03:請求邊界中介層 —— 設定 request_id、記進出 ---
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request_id_var.set(rid)  # 03:之後這個請求的每一行日誌都自動帶 request_id
    start = time.monotonic()
    log.info("request started", extra={"method": request.method, "path": request.url.path})
    try:
        response = await call_next(request)
    except Exception:
        # 邊界一定要記「請求結束」(即使是錯)。堆疊由下面的 exception handler 記,這裡不重複記堆疊。
        latency = round((time.monotonic() - start) * 1000, 1)
        log.info("request finished", extra={"status": 500, "latency_ms": latency})
        raise
    latency = round((time.monotonic() - start) * 1000, 1)
    log.info("request finished", extra={"status": response.status_code, "latency_ms": latency})
    response.headers["x-request-id"] = rid
    return response


# --- 端點 ---
@app.get("/users/{uid}")
async def get_user(uid: int):
    if uid <= 0:
        log.info("invalid user id, rejecting", extra={"uid": uid})  # 01:正常業務,INFO 不是 ERROR
        return JSONResponse(status_code=400, content={"error": "invalid id"})
    try:
        user = fetch_user(uid)
    except UserNotFound:
        log.info("user not found", extra={"uid": uid})  # 01:正常業務,INFO
        return JSONResponse(status_code=404, content={"error": "not found"})
    log.info("user fetched", extra={"uid": uid})  # 02:業務里程碑
    return user


# --- 04:全域異常處理器 —— 唯一記「未捕獲異常」完整堆疊的地方 ---
@app.exception_handler(Exception)
async def on_unhandled(request: Request, exc: Exception):
    # log.exception 自帶 exc_info=True,印出完整堆疊 + cause chain(RepositoryError ← ConnectionError)
    log.exception("unhandled error", extra={"path": request.url.path})
    return JSONResponse(status_code=500, content={"error": "internal"})
