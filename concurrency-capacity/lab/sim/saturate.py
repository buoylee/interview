"""USL — why adding workers stops helping (Amdahl) and then HURTS (coherency).

The Universal Scalability Law:

    throughput(N) = λ1·N / (1 + σ·(N−1) + κ·N·(N−1))

- σ (sigma)  = contention   — serial fraction; caps you at 1/σ (Amdahl)
- κ (kappa)  = coherency    — crosstalk cost; makes throughput RETROGRADE

The κ term is the one people forget: past a peak N, more workers/threads
make total throughput go DOWN, not just plateau. That peak is the number
you're hunting when you "load-test to find the knee".

    python saturate.py --sigma 0.03 --kappa 0.001
"""
import argparse
import math


def usl_throughput(n: int, sigma: float, kappa: float, lam1: float = 1.0) -> float:
    """Relative throughput at concurrency N (lam1 = throughput of one worker)."""
    return lam1 * n / (1 + sigma * (n - 1) + kappa * n * (n - 1))


def usl_curve(ns, sigma: float, kappa: float):
    """[(N, throughput), ...] — the scalability curve."""
    return [(n, usl_throughput(n, sigma, kappa)) for n in ns]


def peak_n(sigma: float, kappa: float) -> int:
    """The N that maximizes throughput. With κ>0 this is finite — the knee.

    Derivative of USL gives N* = sqrt((1−σ)/κ). With κ=0 there is no peak
    (monotone toward the 1/σ Amdahl ceiling), reported as a huge sentinel.
    """
    if kappa <= 0:
        return 10**9
    return max(1, round(math.sqrt((1 - sigma) / kappa)))


def main() -> None:
    p = argparse.ArgumentParser(description="USL saturation sweep")
    p.add_argument("--sigma", type=float, default=0.03, help="contention σ")
    p.add_argument("--kappa", type=float, default=0.001, help="coherency κ")
    p.add_argument("--max-n", type=int, default=64)
    args = p.parse_args()

    pn = peak_n(args.sigma, args.kappa)
    print(f"peak throughput at N ≈ {pn}  (σ={args.sigma}, κ={args.kappa})")
    print("N    throughput  bar")
    for n, t in usl_curve(range(1, args.max_n + 1), args.sigma, args.kappa):
        mark = "  <- peak" if n == pn else ""
        print(f"{n:<4} {t:9.2f}  {'#' * min(60, int(t * 2))}{mark}")


if __name__ == "__main__":
    main()
