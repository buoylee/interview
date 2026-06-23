"""Bulkhead — one shared pool lets a slow workload starve a fast one.

A deterministic discrete-event sim of two request classes (fast + slow)
either SHARING one pool or running in ISOLATED pools. Run both with the
same seed and compare: isolation protects the fast path from the slow
path's bursts.

    python bulkhead.py
"""
import argparse
import heapq
import random
from collections import deque


class _Pool:
    """`capacity` servers + a bounded FIFO queue of length `maxq`."""

    def __init__(self, capacity: int, maxq: int):
        self.capacity = capacity
        self.maxq = maxq
        self.busy: list[int] = []          # min-heap of completion ticks
        self.queue: deque = deque()        # (arrival_tick, klass, service)

    def release(self, t: int) -> None:
        while self.busy and self.busy[0] <= t:
            heapq.heappop(self.busy)

    def admit(self, t: int, klass: str, service: int) -> bool:
        if len(self.queue) >= self.maxq:
            return False                    # queue full → rejected
        self.queue.append((t, klass, service))
        return True

    def dispatch(self, t: int):
        served = []
        while self.queue and len(self.busy) < self.capacity:
            arrival, klass, service = self.queue.popleft()
            served.append((klass, t - arrival))
            heapq.heappush(self.busy, t + service)
        return served


def _p99(xs: list[int]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    return float(s[min(len(s) - 1, int(0.99 * len(s)))])


def simulate(shared: bool, fast_rate: float, slow_rate: float, slow_service: int,
             fast_service: int, capacity: int, ticks: int, seed: int = 0) -> dict:
    """Run the sim. Rates are per-tick arrival probabilities in [0,1].

    Returns fast/slow rejected counts and fast/slow P99 queue-wait (ticks).
    Deterministic for a given seed.
    """
    rng = random.Random(seed)
    if shared:
        pools = {"both": _Pool(capacity, maxq=capacity)}
        route = {"fast": "both", "slow": "both"}
    else:
        fcap = max(1, capacity // 2)
        scap = max(1, capacity - fcap)
        pools = {"fast": _Pool(fcap, maxq=fcap), "slow": _Pool(scap, maxq=scap)}
        route = {"fast": "fast", "slow": "slow"}

    waits = {"fast": [], "slow": []}
    rejected = {"fast": 0, "slow": 0}

    for t in range(ticks):
        for pool in pools.values():
            pool.release(t)
        arrivals = []
        if rng.random() < fast_rate:
            arrivals.append(("fast", fast_service))
        if rng.random() < slow_rate:
            arrivals.append(("slow", slow_service))
        for klass, svc in arrivals:
            if not pools[route[klass]].admit(t, klass, svc):
                rejected[klass] += 1
        for pool in pools.values():
            for klass, wait in pool.dispatch(t):
                waits[klass].append(wait)

    return {
        "fast_rejected": rejected["fast"],
        "slow_rejected": rejected["slow"],
        "fast_p99_wait": _p99(waits["fast"]),
        "slow_p99_wait": _p99(waits["slow"]),
    }


def _fmt(d: dict) -> str:
    return (f"fast: rejected={d['fast_rejected']:<5} p99_wait={d['fast_p99_wait']:.0f}  |  "
            f"slow: rejected={d['slow_rejected']:<5} p99_wait={d['slow_p99_wait']:.0f}")


def main() -> None:
    p = argparse.ArgumentParser(description="bulkhead: shared vs isolated pools")
    p.add_argument("--ticks", type=int, default=4000)
    args = p.parse_args()

    def run(shared: bool) -> dict:
        return simulate(shared=shared, fast_rate=0.6, slow_rate=0.08, slow_service=40,
                        fast_service=1, capacity=4, ticks=args.ticks, seed=1)

    print("SHARED   ", _fmt(run(True)))
    print("ISOLATED ", _fmt(run(False)))
    print("\n→ isolation trades some slow rejects for a protected fast path.")


if __name__ == "__main__":
    main()
