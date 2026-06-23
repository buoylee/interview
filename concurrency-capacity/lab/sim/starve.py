"""M/M/c — a connection/thread pool is c servers. Watch wait blow up as c→load.

A pool of size c is a c-server queue. Offered load a = λ·S (in "erlangs" =
how many servers' worth of work arrives). The pool is stable only if c > a;
as c approaches a, the mean wait explodes (same 1/(1−ρ) family as M/M/1).

This is the engine behind "how big should the pool be": big enough that
c comfortably exceeds the offered load a — not bigger (see 05 on why).

    python starve.py --lam 80 --service-time 0.1     # a = 8 erlangs
"""
import argparse
import math


def _erlang_c(a: float, c: int) -> float:
    """Erlang-C: probability an arriving request must queue (all servers busy)."""
    top = (a ** c / math.factorial(c)) * (c / (c - a))
    bot = sum(a ** k / math.factorial(k) for k in range(c)) + top
    return top / bot


def mmc_wait(lam: float, service_time: float, c: int) -> float:
    """Mean time waiting in queue for an M/M/c pool of c servers.

    Raises ValueError if offered load a = λ·S ≥ c (pool unstable, ρ ≥ 1).
    """
    a = lam * service_time  # offered load in erlangs
    if a >= c:
        raise ValueError(f"offered load a={a} ≥ servers c={c}: pool unstable (ρ≥1)")
    pq = _erlang_c(a, c)
    return pq * service_time / (c - a)


def pool_sweep(lam: float, service_time: float, c_values):
    """[(c, mean_wait), ...]; unstable sizes report inf."""
    out = []
    for c in c_values:
        try:
            out.append((c, mmc_wait(lam, service_time, c)))
        except ValueError:
            out.append((c, float("inf")))
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="M/M/c pool wait sweep")
    p.add_argument("--lam", type=float, default=80)
    p.add_argument("--service-time", type=float, default=0.1)
    args = p.parse_args()
    a = args.lam * args.service_time
    print(f"offered load a = λ·S = {a:.1f} erlangs  →  need pool size c > {a:.1f}")
    print("c    mean wait   bar")
    for c, w in pool_sweep(args.lam, args.service_time, range(int(a) + 1, int(a) + 13)):
        shown = "  ∞ (unstable)" if math.isinf(w) else f"{w * 1000:8.1f}ms"
        bar = "" if math.isinf(w) else "#" * min(60, int(w * 200))
        print(f"{c:<4} {shown}  {bar}")


if __name__ == "__main__":
    main()
