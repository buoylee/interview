"""A driveable service for the capacity experiments.

One small FastAPI app with knobs (via env) and live concurrency counters,
so you can drive it into saturation and WATCH Little's Law, pool rejection,
and the P99 hockey-stick happen for real.

Endpoints:
  GET /fast            returns immediately (cheap path)
  GET /slow?ms=100     async sleep = simulated I/O wait, gated by a pool
  GET /cpu?n=100000    busy CPU loop = blocks the event loop (CPU-bound pain)
  GET /healthz         liveness
  GET /stats           {in_flight, max_in_flight, rejected, pool_size, model}

Knobs (read at startup):
  POOL_SIZE   max concurrent /slow before 503 (default 16)
  MODEL       label only, for the model-shootout experiment (default "async")

Run:
  POOL_SIZE=8 uvicorn app:app --port 8000
"""
import asyncio
import os

from fastapi import FastAPI, Request, Response


class State:
    """Live concurrency counters — the implementation of Little's Law in the flesh."""

    def __init__(self, pool_size: int, model: str):
        self.pool_size = pool_size
        self.model = model
        self.in_flight = 0          # L: requests currently in the system
        self.max_in_flight = 0      # high-water mark
        self.rejected = 0           # /slow shed because the pool was full
        self.slow_active = 0        # /slow currently holding a pool slot


state = State(pool_size=int(os.getenv("POOL_SIZE", "16")), model=os.getenv("MODEL", "async"))
app = FastAPI(title="concurrency-capacity lab service")


@app.middleware("http")
async def track_in_flight(request: Request, call_next):
    state.in_flight += 1
    if state.in_flight > state.max_in_flight:
        state.max_in_flight = state.in_flight
    try:
        return await call_next(request)
    finally:
        state.in_flight -= 1


@app.get("/fast")
async def fast():
    return {"ok": True}


@app.get("/slow")
async def slow(ms: int = 100):
    # Check-then-increment is atomic here: no await between them, single-threaded loop.
    if state.slow_active >= state.pool_size:
        state.rejected += 1
        return Response(status_code=503, content="pool full")
    state.slow_active += 1
    try:
        await asyncio.sleep(ms / 1000)   # simulated I/O wait — yields the loop
        return {"slept_ms": ms}
    finally:
        state.slow_active -= 1


@app.get("/cpu")
async def cpu(n: int = 100_000):
    # A busy loop in an async handler blocks the WHOLE event loop — by design,
    # so 04/07 can show CPU-bound work freezing every other request.
    x = 0
    for i in range(n):
        x += i * i
    return {"sum": x}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/stats")
async def stats():
    return {
        "in_flight": state.in_flight,
        "max_in_flight": state.max_in_flight,
        "rejected": state.rejected,
        "pool_size": state.pool_size,
        "model": state.model,
    }
