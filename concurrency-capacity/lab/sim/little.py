"""Little's Law & M/M/1 — watch L = λW, and watch R = S/(1-ρ) blow up.

Zero infra, pure stdlib, deterministic. The first runnable proof of the
whole track: concurrency is just arrival-rate × latency, and latency
explodes as utilization approaches 1.

    python little.py --lam 200 --w 0.05      # L = 10 in flight
    python little.py --service-time 0.01     # print the R-vs-ρ hockey stick
"""
import argparse


def little_l(lam: float, w: float) -> float:
    """Little's Law: in-flight count L = arrival-rate λ × time-in-system W."""
    return lam * w


def mm1_response(service_time: float, rho: float) -> float:
    """M/M/1 mean response time R = S / (1 - ρ).

    The 1/(1-ρ) factor IS the P99 hockey-stick: it is finite-but-growing
    for ρ<1 and diverges as ρ→1. Saturation (ρ≥1) has no steady state.
    """
    if not 0 <= rho < 1:
        raise ValueError(f"rho must be in [0,1); got {rho} (system saturates at ρ≥1)")
    return service_time / (1 - rho)


def mm1_curve(service_time: float, rhos: list[float]) -> list[tuple[float, float]]:
    """[(ρ, R), ...] across utilizations — the saturation curve."""
    return [(r, mm1_response(service_time, r)) for r in rhos]


def main() -> None:
    p = argparse.ArgumentParser(description="Little's Law / M/M/1 demo")
    p.add_argument("--lam", type=float, help="arrival rate λ (req/s)")
    p.add_argument("--w", type=float, help="time in system W (s)")
    p.add_argument("--service-time", type=float, default=0.01, help="M/M/1 service time S (s)")
    args = p.parse_args()

    if args.lam and args.w:
        print(f"L = λ·W = {args.lam} × {args.w} = {little_l(args.lam, args.w):.2f} in flight\n")

    print("ρ      R=S/(1-ρ)   (bar ∝ R) — watch it explode toward ρ=1")
    for rho, r in mm1_curve(args.service_time, [0.1, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 0.99]):
        bar = "#" * min(60, int(r / args.service_time))
        print(f"{rho:<6} {r * 1000:8.1f}ms  {bar}")


if __name__ == "__main__":
    main()
