"""Demo: async vs sync throughput for many IO-bound queries.

Each query is `SELECT pg_sleep(0.05)` to simulate 50ms of round-trip latency.
Sync runs them sequentially on one connection (~N*0.05s). Async fires N
concurrently over an N-sized pool (~one round trip). This is the case async
data access is *for* -- not CPU work, but lots of concurrent waiting.

Run: uv run python demos/async_vs_sync.py
"""
import asyncio
import pathlib
import sys
import time

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from db import make_async_engine, make_engine  # noqa: E402

N, SLEEP = 20, 0.05  # 20 queries, 50ms simulated latency each


def sync_run():
    engine = make_engine()
    t0 = time.perf_counter()
    with engine.connect() as conn:
        for _ in range(N):
            conn.execute(text("SELECT pg_sleep(:s)"), {"s": SLEEP})
    engine.dispose()
    return time.perf_counter() - t0


async def async_run():
    engine = make_async_engine(pool_size=N)

    async def one():
        async with engine.connect() as conn:
            await conn.execute(text("SELECT pg_sleep(:s)"), {"s": SLEEP})

    t0 = time.perf_counter()
    await asyncio.gather(*[one() for _ in range(N)])
    await engine.dispose()
    return time.perf_counter() - t0


s = sync_run()
a = asyncio.run(async_run())
print(f"sync : {N} queries x {SLEEP}s sequential = {s:.2f}s")
print(f"async: {N} concurrent                   = {a:.2f}s  (speedup {s / a:.1f}x)")
