"""Ramp load against the lab service and record the saturation curve.

For each target RPS step, fires that many requests per second for a few
seconds (open-model: it does NOT wait for replies before sending the next,
so it avoids coordinated omission — see chapter 01), then reports
P50/P99/QPS/errors. Watch P99 hockey-stick at the knee.

  python drive.py --url http://127.0.0.1:8000/slow?ms=50 --steps 50,100,200,400,800

Note: use 127.0.0.1, not localhost — uvicorn binds IPv4 only, and httpx
does not fall back from IPv6 ::1 the way curl does.
"""
import argparse
import asyncio
import time

import httpx


async def _one(client: httpx.AsyncClient, url: str, out: list, errs: list):
    t0 = time.perf_counter()
    try:
        r = await client.get(url, timeout=10.0)
        dt = time.perf_counter() - t0
        (out if r.status_code < 500 else errs).append(dt)
    except Exception:
        errs.append(time.perf_counter() - t0)


async def step(url: str, rps: int, seconds: int) -> dict:
    lat: list[float] = []
    errs: list[float] = []
    async with httpx.AsyncClient() as client:
        tasks = []
        start = time.perf_counter()
        # open-model: schedule rps requests per second regardless of completion
        for i in range(rps * seconds):
            target = start + i / rps
            now = time.perf_counter()
            if target > now:
                await asyncio.sleep(target - now)
            tasks.append(asyncio.create_task(_one(client, url, lat, errs)))
        await asyncio.gather(*tasks)
    wall = time.perf_counter() - start
    done = sorted(lat)
    p = lambda q: done[min(len(done) - 1, int(q * len(done)))] * 1000 if done else 0.0
    return {
        "rps_target": rps,
        "ok": len(lat),
        "errors": len(errs),
        "qps": round(len(lat) / wall, 1),
        "p50_ms": round(p(0.50), 1),
        "p99_ms": round(p(0.99), 1),
    }


async def ramp(url: str, rps_steps: list[int], seconds_per_step: int) -> list[dict]:
    rows = []
    for rps in rps_steps:
        row = await step(url, rps, seconds_per_step)
        rows.append(row)
        print(f"rps={row['rps_target']:<5} qps={row['qps']:<7} "
              f"p50={row['p50_ms']:<7}ms p99={row['p99_ms']:<8}ms errors={row['errors']}")
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description="ramp load + record curve")
    p.add_argument("--url", default="http://127.0.0.1:8000/slow?ms=50")
    p.add_argument("--steps", default="50,100,200,400,800")
    p.add_argument("--seconds", type=int, default=5)
    args = p.parse_args()
    steps = [int(s) for s in args.steps.split(",")]
    print(f"ramping {args.url}  steps={steps}  {args.seconds}s each")
    asyncio.run(ramp(args.url, steps, args.seconds))


if __name__ == "__main__":
    main()
