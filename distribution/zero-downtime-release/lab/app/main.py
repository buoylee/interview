"""
最小 FastAPI 实例,用于演示优雅 / 非优雅下线对在途请求的影响。

- GET /work        : 模拟一个耗时 WORK_SECONDS 的在途请求(默认 2s)
- GET /health/live : liveness,只回自身存活
- GET /health/ready: readiness,_draining=True 时回 503(演示"主动摘流量")
- POST /admin/drain: 手动把 readiness 翻成 503(演示 readiness-first,见 ch03 C2)

关键点:Dockerfile 用 exec-form CMD,uvicorn 直接当 PID 1,亲自收 SIGTERM。
- `docker stop`(SIGTERM + 宽限期)→ uvicorn 优雅关:停 accept、排空在途、再退。
- `docker kill -s SIGKILL`(立即)→ 在途被硬切,演示"非优雅"。
"""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

INSTANCE = os.getenv("INSTANCE", "app")
WORK_SECONDS = float(os.getenv("WORK_SECONDS", "2"))

_draining = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 进程启动时跑一次(uvicorn 发 lifespan.startup)
    print(f"[{INSTANCE}] startup: ready to serve", flush=True)
    yield
    # 进程优雅关闭时跑一次(uvicorn 排空完在途后,发 lifespan.shutdown 到这)
    print(f"[{INSTANCE}] shutdown: in-flight drained, closing pools — bye", flush=True)


app = FastAPI(lifespan=lifespan)


@app.get("/health/live")
async def live():
    return {"status": "ok", "instance": INSTANCE}


@app.get("/health/ready")
async def ready():
    if _draining:
        # 503 = "别再给我导流量"。注意:nginx OSS 不会主动探这个端点(见 lab/README 边界说明)
        return Response('{"status":"draining"}', status_code=503,
                        media_type="application/json")
    return {"status": "ready", "instance": INSTANCE}


@app.post("/admin/drain")
async def drain():
    global _draining
    _draining = True
    print(f"[{INSTANCE}] /admin/drain → readiness now 503", flush=True)
    return {"instance": INSTANCE, "draining": True}


@app.get("/work")
async def work():
    # 模拟在途请求:这段时间内若进程被硬杀,这个请求就被掐断
    await asyncio.sleep(WORK_SECONDS)
    return {"instance": INSTANCE, "served": True}
