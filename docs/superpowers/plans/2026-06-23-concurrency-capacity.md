# concurrency-capacity Track Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `concurrency-capacity/` learning track — 10 architect-depth chapters + a two-tier runnable lab — that teaches turning a business number (RPS, P99 target) into defensible concurrency config, with Little's Law as the spine.

**Architecture:** Language-neutral narrative chapters (Python-lead + Go/Java callouts) hung off `L = λW`. A two-tier lab: `lab/sim/` (pure-stdlib, deterministic, pytest-backed) gives every chapter a runnable proof; `lab/service/` (FastAPI + load driver) gives real-load experiments. Lab `sim/` files land just before the chapter that cites them. Each chapter and each lab file is its own commit.

**Tech Stack:** Markdown (Simplified Chinese prose, matching repo); Python 3.11+ stdlib for `lab/sim/`; FastAPI + uvicorn + httpx for `lab/service/`; pytest for lab tests. No third-party deps in `sim/` (stdlib only).

## Global Constraints

Every task implicitly includes these (copied from spec `2026-06-23-concurrency-capacity-design.md`):

- **Depth contract is mandatory, per chapter.** Each chapter teaches the named 内部层 model from spec §3.1 (e.g. ch01 → `R = S/(1−ρ)` + Kingman + coordinated omission), **in the narrative** — not deferred to the cards. A chapter missing its model fails review.
- **Three-language callouts** (Python-lead + Go + Java) at every point where the concrete knob differs. Python is the primary; Go/Java are inline contrast, not separate sections.
- **Narrative format, NOT the 7-section template** that `python-concurrency/` uses. Single throughline per chapter.
- **指进不重写**: link into `performance-tuning-roadmap/`, `python-concurrency/`, `golang/concurrency`, `java/concurrent` rather than duplicating. Exact link targets in spec §8.
- **Every chapter ends with a 「动手:跑这个实验」box** pointing at the matching `lab/` artifact.
- **Prose language:** Simplified Chinese, same register as `system-design/` deep chapters. Code/identifiers/commit messages may be English.
- **`lab/sim/` = stdlib only, deterministic** (seedable RNG, no wall-clock dependence in assertions).
- **Commit cadence:** one commit per chapter / per lab file. Commit messages: `docs(concurrency-capacity): ...` for chapters, `feat(concurrency-capacity/lab): ...` for lab code. End every commit message with the Co-Authored-By trailer used in this repo.

---

## File Structure

```
concurrency-capacity/
  README.md                      # index: positioning, chapter map, progress, lab pointer
  00-decision-pipeline/README.md # 全景:需求→配置 的决策管线
  01-littles-law/README.md       # Little 定律 + M/M/1 + 饱和曲线
  02-concurrency-models/README.md# 三种并发模型
  03-measure-demand/README.md    # 测算 λ, W
  04-sizing-one-node/README.md    # worker/线程数 + 单机规格
  05-pools/README.md             # 池:哪些、多大、×worker 总账
  06-isolation/README.md         # 隔离 / 舱壁
  07-overload-backpressure/README.md # 过载与背压
  08-monitoring-concurrency/README.md# 在线监控并发
  09-scaling-out/README.md        # 横向扩容与成本
  99-interview-cards/README.md    # 面试卡
  lab/
    sim/
      little.py                  # Little + M/M/1 R=S/(1-ρ)
      saturate.py                # USL 扫描:平台 + 回退
      starve.py                  # 池=N → 等待时间爆炸
      bulkhead.py                # 共享 vs 隔离池
      tests/
        test_little.py
        test_saturate.py
        test_starve.py
        test_bulkhead.py
    service/
      app.py                     # FastAPI /fast /slow /cpu,旋钮走 env
      drive.py                   # 拉升 λ 记录 P50/P99/QPS
      compose.yaml               # service + 压测 + 指标
      tests/test_app.py          # smoke: 端点存在 + 旋钮生效
    experiments/
      e02-model-shootout.md
      e04-find-saturation.md
      e05-pool-starvation.md
      e06-bulkhead.md
      e07-overload-collapse.md
      e08-read-the-signals.md
```

---

### Task 1: Track scaffold + README index

**Files:**
- Create: `concurrency-capacity/README.md`

**Interfaces:**
- Produces: the chapter directory naming (`00-decision-pipeline/` … `09-scaling-out/`, `99-interview-cards/`) every later task creates files under. The progress table later tasks tick.

- [ ] **Step 1: Write `concurrency-capacity/README.md`**

Contents (write in full, Simplified Chinese):
1. **一句话定位** — copy spec §1 ("把业务数字翻译成站得住脚的配置…").
2. **这门课填的缺口** — the 3-track gap table from spec §2.
3. **怎么用** — read 00→09 in order; cards are review-only; lab `sim/` runs with zero infra.
4. **主线** — `L = λW` one-paragraph statement (spec §4 bullets).
5. **章节地图** — markdown table, 10 rows + 99, each linking to its dir + the one-line "干掉的问题" from spec §5.
6. **进度地图** — table with rows: spec✅ / 本文件 / 00…09 / 99 / lab-sim / lab-service, status column (all ⬜ except spec✅ and 本文件✅).
7. **指进已有课(复用不重复)** — the link list from spec §8.

- [ ] **Step 2: Acceptance checklist**

Verify: chapter map has 11 rows (00–09 + 99); every spec §8 link target appears; progress table present. 

- [ ] **Step 3: Commit**

```bash
git add concurrency-capacity/README.md
git commit -m "docs(concurrency-capacity): track scaffold + 章节/进度地图"
```

---

### Task 2: `lab/sim/little.py` + tests — Little's Law & M/M/1

**Files:**
- Create: `concurrency-capacity/lab/sim/little.py`
- Test: `concurrency-capacity/lab/sim/tests/test_little.py`

**Interfaces:**
- Produces:
  - `little_l(lam: float, w: float) -> float` — returns `lam * w` (in-flight count L).
  - `mm1_response(service_time: float, rho: float) -> float` — returns `service_time / (1 - rho)` for `0 <= rho < 1`; raises `ValueError` if `rho >= 1`.
  - `mm1_curve(service_time: float, rhos: list[float]) -> list[tuple[float, float]]` — `[(rho, R), ...]`.
  - `main()` — CLI (`argparse`: `--lam`, `--w` OR `--service-time` + `--rho`) printing L, ρ, R, and an ASCII R-vs-ρ curve.

- [ ] **Step 1: Write the failing tests**

```python
# concurrency-capacity/lab/sim/tests/test_little.py
import math, pytest
from concurrency_capacity.lab.sim.little import little_l, mm1_response, mm1_curve

def test_little_l_basic():
    # λ=200 req/s, W=50ms → 10 in flight
    assert little_l(200, 0.05) == pytest.approx(10.0)

def test_mm1_blows_up_near_one():
    # R = S/(1-ρ): doubling closeness to 1 ~doubles latency
    assert mm1_response(0.01, 0.5) == pytest.approx(0.02)
    assert mm1_response(0.01, 0.9) == pytest.approx(0.10)
    assert mm1_response(0.01, 0.99) == pytest.approx(1.0)

def test_mm1_rejects_saturation():
    with pytest.raises(ValueError):
        mm1_response(0.01, 1.0)

def test_curve_is_monotonic_increasing():
    pts = mm1_curve(0.01, [0.1, 0.5, 0.9, 0.95])
    rs = [r for _, r in pts]
    assert rs == sorted(rs) and rs[-1] > rs[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd concurrency-capacity && python -m pytest lab/sim/tests/test_little.py -v`
Expected: FAIL — `ModuleNotFoundError`/`ImportError` (little.py not written). (Add empty `__init__.py` files as needed so the import path resolves, or run pytest with `rootdir` at repo root; document whichever in the chapter.)

- [ ] **Step 3: Write `little.py`**

```python
"""Little's Law & M/M/1 — watch L = λW and R = S/(1-ρ)."""
import argparse

def little_l(lam: float, w: float) -> float:
    return lam * w

def mm1_response(service_time: float, rho: float) -> float:
    if not 0 <= rho < 1:
        raise ValueError(f"rho must be in [0,1); got {rho} (system saturates at ρ≥1)")
    return service_time / (1 - rho)

def mm1_curve(service_time: float, rhos: list[float]) -> list[tuple[float, float]]:
    return [(r, mm1_response(service_time, r)) for r in rhos]

def main() -> None:
    p = argparse.ArgumentParser(description="Little's Law / M/M/1 demo")
    p.add_argument("--lam", type=float, help="arrival rate λ (req/s)")
    p.add_argument("--w", type=float, help="latency W (s)")
    p.add_argument("--service-time", type=float, default=0.01)
    args = p.parse_args()
    if args.lam and args.w:
        print(f"L = λ·W = {little_l(args.lam, args.w):.2f} in flight")
    print("ρ      R=S/(1-ρ)   bar")
    for rho, r in mm1_curve(args.service_time, [0.1,0.3,0.5,0.7,0.8,0.9,0.95,0.99]):
        bar = "#" * min(60, int(r / args.service_time))
        print(f"{rho:<6} {r*1000:8.1f}ms  {bar}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd concurrency-capacity && python -m pytest lab/sim/tests/test_little.py -v`
Expected: PASS (4 passed). Also eyeball `python lab/sim/little.py --lam 200 --w 0.05` shows L=10 and the bars growing super-linearly toward ρ=0.99.

- [ ] **Step 5: Commit**

```bash
git add concurrency-capacity/lab/sim/little.py concurrency-capacity/lab/sim/tests/test_little.py
git commit -m "feat(concurrency-capacity/lab): little.py — Little's Law + M/M/1 R=S/(1-ρ)"
```

---

### Task 3: Chapter 00 — 决策管线全景

**Files:**
- Create: `concurrency-capacity/00-decision-pipeline/README.md`

**Interfaces:**
- Produces: the canonical pipeline ordering (需求→模型→单机→池→隔离→过载→监控→扩容) every later chapter's "你在管线的哪一步" breadcrumb references.

- [ ] **Step 1: Draft the chapter**

Content spec (narrative, Simplified Chinese):
- **开场痛点**: restate the user's own problem — 懂原语,不懂定容;到现实环境不知如何下手. Name the gap explicitly.
- **决策管线图**: an ASCII/numbered pipeline: ① 测需求(λ,W) → ② 选并发模型 → ③ 单机定容(worker/线程 + 规格) → ④ 池定容 → ⑤ 隔离 → ⑥ 过载/背压 → ⑦ 监控 → ⑧ 扩容. Each node = one chapter, link to it.
- **一句话主线**: 整条管线都从 `L=λW` 推导;先认这把钥匙(→01).
- **怎么读这门课 + lab 怎么配合**: read in order; `lab/sim/` zero-infra runnable proofs.
- **指进**: link `system-design/` (上一层) and `python-concurrency/` (语言原语层) so the reader places this track between them.

- [ ] **Step 2: Acceptance checklist**

Pipeline has 8 nodes each linking to a chapter dir; gap stated; main-line `L=λW` named; 指进 links to system-design + python-concurrency present. No 7-box template.

- [ ] **Step 3: Commit**

```bash
git add concurrency-capacity/00-decision-pipeline/README.md
git commit -m "docs(concurrency-capacity): 00 决策管线全景"
```

---

### Task 4: Chapter 01 — Little 定律(总钥匙)

**Files:**
- Create: `concurrency-capacity/01-littles-law/README.md`

**Interfaces:**
- Consumes: `lab/sim/little.py` (Task 2).
- Produces: the vocabulary (L, λ, W, ρ, 饱和) every later chapter reuses.

- [ ] **Step 1: Draft the chapter — depth model = M/M/1 + Kingman + coordinated omission**

Content spec:
- **直觉**: `L = λW` — 在途数 = 到达率 × 停留时间. Concrete: 200 req/s × 50ms = 10 在途. This single equation is the track's key.
- **底层①排队论**: derive the saturation blow-up. Present `R = S/(1−ρ)` (M/M/1). Show the `1/(1−ρ)` term IS the P99 hockey-stick; tabulate ρ=0.5/0.9/0.99 → R×2/×10/×100. Run `little.py` to show it.
- **底层②方差(Kingman/VUT)**: real traffic isn't Poisson-smooth — wait ∝ `(C²a+C²s)/2 · ρ/(1−ρ) · S`. Burstiness/heavy-tail (high C²) saturates you *before* the mean predicts. Why "平均 CPU 50%" can already be saturating.
- **底层③测量陷阱(coordinated omission)**: naive load tests pause their own clock while the server stalls, so they under-report the tail. One paragraph + how good tools fix it (Tene/HdrHistogram).
- **三语锚点**: where L shows up — Java thread-pool active count, Go in-flight goroutines, Python在途协程/in-flight requests.
- **动手盒子**: `python lab/sim/little.py --lam 200 --w 0.05` and read the R-vs-ρ bars.
- **指进**: `performance-tuning-roadmap/01-methodology/04-performance-laws.md` for更深推导.

- [ ] **Step 2: Acceptance checklist**

`R=S/(1−ρ)` derived + tabulated; Kingman/C² covered; coordinated omission covered; little.py 动手 box; perf-laws 指进 link; 3-lang anchor present.

- [ ] **Step 3: Commit**

```bash
git add concurrency-capacity/01-littles-law/README.md
git commit -m "docs(concurrency-capacity): 01 Little 定律 + M/M/1 + Kingman"
```

---

### Task 5: `lab/sim/saturate.py` + tests — USL saturation & retrograde

**Files:**
- Create: `concurrency-capacity/lab/sim/saturate.py`
- Test: `concurrency-capacity/lab/sim/tests/test_saturate.py`

**Interfaces:**
- Produces:
  - `usl_throughput(n: int, sigma: float, kappa: float, lam1: float = 1.0) -> float` — Universal Scalability Law: `lam1 * n / (1 + sigma*(n-1) + kappa*n*(n-1))`.
  - `usl_curve(ns: list[int], sigma: float, kappa: float) -> list[tuple[int, float]]`.
  - `peak_n(sigma: float, kappa: float) -> int` — the N maximizing throughput (`round(sqrt((1-sigma)/kappa))` for kappa>0).
  - `main()` — CLI sweeping N, printing throughput plateau then retrograde.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_saturate.py
import pytest
from concurrency_capacity.lab.sim.saturate import usl_throughput, usl_curve, peak_n

def test_linear_when_no_contention():
    # σ=0, κ=0 → perfect linear scaling
    assert usl_throughput(10, 0.0, 0.0) == pytest.approx(10.0)

def test_amdahl_plateau_with_sigma():
    # contention only (κ=0): approaches 1/σ ceiling, never retrogrades
    assert usl_throughput(1000, 0.05, 0.0) < 1/0.05
    assert usl_throughput(1000, 0.05, 0.0) > usl_throughput(100, 0.05, 0.0)

def test_kappa_causes_retrograde():
    # with κ>0 throughput peaks then DROPS — the key USL insight
    c = usl_curve(list(range(1, 64)), 0.03, 0.001)
    tputs = [t for _, t in c]
    peak = max(tputs)
    assert tputs[-1] < peak  # retrograde past the peak

def test_peak_n_matches_curve():
    sigma, kappa = 0.03, 0.001
    c = dict(usl_curve(list(range(1, 200)), sigma, kappa))
    pn = peak_n(sigma, kappa)
    assert c[pn] == pytest.approx(max(c.values()), rel=0.02)
```

- [ ] **Step 2: Run to verify fail**

Run: `cd concurrency-capacity && python -m pytest lab/sim/tests/test_saturate.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Implement `saturate.py`**

```python
"""USL — why throughput plateaus (Amdahl) and then RETROGRADES (coherency)."""
import argparse, math

def usl_throughput(n: int, sigma: float, kappa: float, lam1: float = 1.0) -> float:
    return lam1 * n / (1 + sigma * (n - 1) + kappa * n * (n - 1))

def usl_curve(ns, sigma, kappa):
    return [(n, usl_throughput(n, sigma, kappa)) for n in ns]

def peak_n(sigma: float, kappa: float) -> int:
    if kappa <= 0:
        return 10**9  # no peak; monotone toward 1/sigma
    return max(1, round(math.sqrt((1 - sigma) / kappa)))

def main() -> None:
    p = argparse.ArgumentParser(description="USL saturation sweep")
    p.add_argument("--sigma", type=float, default=0.03)
    p.add_argument("--kappa", type=float, default=0.001)
    p.add_argument("--max-n", type=int, default=64)
    args = p.parse_args()
    print(f"peak at N≈{peak_n(args.sigma, args.kappa)}")
    print("N    throughput  bar")
    for n, t in usl_curve(range(1, args.max_n + 1), args.sigma, args.kappa):
        print(f"{n:<4} {t:9.2f}  {'#'*min(60, int(t*2))}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run to verify pass**

Run: `cd concurrency-capacity && python -m pytest lab/sim/tests/test_saturate.py -v`
Expected: PASS (4 passed). Eyeball `python lab/sim/saturate.py` — bars rise, peak, then shrink.

- [ ] **Step 5: Commit**

```bash
git add concurrency-capacity/lab/sim/saturate.py concurrency-capacity/lab/sim/tests/test_saturate.py
git commit -m "feat(concurrency-capacity/lab): saturate.py — USL plateau + retrograde"
```

---

### Task 6: Chapter 02 — 三种并发模型

**Files:**
- Create: `concurrency-capacity/02-concurrency-models/README.md`

- [ ] **Step 1: Draft — depth model = per-unit cost + GIL release points + M:N**

Content spec:
- **三模型**: thread-per-request / event-loop(单线程协作) / 多进程-worker. For each: 它对 W 和 L 做了什么, 何时选它.
- **底层①每单位成本**: 线程栈(~MB,OS 调度,上下文切换 µs级) vs goroutine(~KB,运行时调度) vs 协程帧(堆上,无内核切换). The C10k lineage: why event-loop wins on memory at 10k+ idle conns.
- **底层②GIL 精确释放点**: Python 线程为何对 CPU 无并行、对阻塞 I/O 有(C 层释放 GIL);所以 Python 选型被 GIL 逼着走多进程/async.
- **底层③Go M:N**: runtime park-the-M——goroutine 阻塞 syscall 时 runtime 换 M,所以 Go 不需要 `to_thread`. Contrast: Python event-loop 单线程,阻塞调用冻结全场.
- **选型决策树**: I/O-bound 高并发 → async/event-loop; CPU-bound → 多进程/多机; 混合 → 进程内 async + 进程级并行.
- **三语**: Java(thread-pool/虚拟线程 Loom), Go(goroutine), Python(asyncio + 多进程 worker).
- **动手盒子**: forward-ref `lab/experiments/e02-model-shootout.md` (built Task 18) — same load, three models, compare in-flight & P99.
- **指进**: `python-concurrency/01-foundations-gil`, `golang/concurrency`, `java/concurrent`, `performance-tuning-roadmap/00-os-fundamentals/05`.

- [ ] **Step 2: Acceptance checklist**

Three models each with W/L impact; per-unit cost table; GIL release points; Go M:N contrast; decision tree; 3-lang; experiment box; 指进 links.

- [ ] **Step 3: Commit**

```bash
git add concurrency-capacity/02-concurrency-models/README.md
git commit -m "docs(concurrency-capacity): 02 三种并发模型 + GIL/M:N 机理"
```

---

### Task 7: `lab/service/` scaffold + smoke test

**Files:**
- Create: `concurrency-capacity/lab/service/app.py`
- Create: `concurrency-capacity/lab/service/drive.py`
- Create: `concurrency-capacity/lab/service/compose.yaml`
- Test: `concurrency-capacity/lab/service/tests/test_app.py`

**Interfaces:**
- Produces:
  - `app` (FastAPI) with `GET /fast` (returns immediately), `GET /slow?ms=` (async sleep — simulated I/O wait), `GET /cpu?n=` (busy CPU loop), `GET /healthz`.
  - Env knobs read at startup: `POOL_SIZE` (asyncio.Semaphore gating /slow), `MODEL` (label only). Exposes `GET /stats` → `{in_flight, max_in_flight, rejected}`.
  - `drive.py`: `async def ramp(base_url, rps_steps: list[int], seconds_per_step) -> list[dict]` returning per-step `{rps, p50, p99, qps, errors}`.

- [ ] **Step 1: Write smoke test**

```python
# tests/test_app.py
from fastapi.testclient import TestClient
from concurrency_capacity.lab.service.app import app

client = TestClient(app)

def test_fast_ok():
    assert client.get("/fast").status_code == 200

def test_stats_shape():
    body = client.get("/stats").json()
    assert {"in_flight", "max_in_flight", "rejected"} <= body.keys()

def test_slow_respects_pool_when_full(monkeypatch):
    # with POOL_SIZE small, an over-cap concurrent /slow gets 503 (rejected)
    # (drive concurrency in-test via threads; assert rejected counter increments)
    ...  # implement with concurrent.futures hitting /slow?ms=200, POOL_SIZE=1
```

- [ ] **Step 2: Run to verify fail**

Run: `cd concurrency-capacity && python -m pytest lab/service/tests/test_app.py -v`
Expected: FAIL — ImportError (app.py absent).

- [ ] **Step 3: Implement `app.py`, `drive.py`, `compose.yaml`**

`app.py` — FastAPI with a startup-read `POOL_SIZE` env → `asyncio.Semaphore`; `/slow` acquires with `try/except` non-blocking acquire → 503 + `rejected += 1` when full; `/stats` returns the counters; track `in_flight`/`max_in_flight` via a small middleware. (Write the full file — ~60 lines.)
`drive.py` — `httpx.AsyncClient`, for each rps step fire N coroutines/sec for `seconds_per_step`, collect latencies, compute P50/P99 with `statistics.quantiles`. (Full file.)
`compose.yaml` — service (uvicorn) + a load container note (reuse `performance-tuning-roadmap/03x-load-gen-quickstart` locust) + optional prometheus scrape of `/stats`. (Full file.)

- [ ] **Step 4: Run to verify pass**

Run: `cd concurrency-capacity && python -m pytest lab/service/tests/test_app.py -v`
Expected: PASS. Also `POOL_SIZE=1 uvicorn ...` + manual two concurrent `/slow?ms=500` → one 200, one 503.

- [ ] **Step 5: Commit**

```bash
git add concurrency-capacity/lab/service/
git commit -m "feat(concurrency-capacity/lab): driveable FastAPI service + ramp driver"
```

---

### Task 8: Chapter 03 — 测算真实并发需求

**Files:**
- Create: `concurrency-capacity/03-measure-demand/README.md`

- [ ] **Step 1: Draft — depth model = peak-to-mean + fan-out tail amplification**

Content spec:
- **从哪拿 λ 和 W**: λ from traffic logs/APM (req/s at peak, not daily avg); W from P50/P99 latency. Then `L=λW` gives needed in-flight.
- **底层①峰均比**: 日均 QPS 骗人;按峰值(+ 突发系数)定容. 给经验区间 + 怎么从历史曲线读峰均比.
- **底层②fan-out 尾部放大(tail-at-scale)**: Dean & Barroso — 1 用户请求 = N 个内部调用,整体延迟由**最慢的那个**决定;N 越大,P99 被放大得越狠(给 1-(0.99^N) 直觉:N=100 个 P99 调用 → ~63% 概率命中一次慢). 这决定下游并发需求被放大.
- **底层③重尾服务时间**: 为什么用均值估 W 会低估;看分布不看均值.
- **留余**: 别配到 100%,目标利用率 60-70%(回到 01 的 `1/(1−ρ)`:ρ=0.7 已经 R×3.3).
- **三语**: 不强语言相关,给通用 APM 信号(Java Micrometer / Go expvar+pprof / Python OTel)做锚.
- **动手盒子**: `python lab/sim/little.py` with measured λ,W; and `e04-find-saturation.md` to validate W under load.
- **指进**: `observability/` 或 `performance-tuning-roadmap/03-observability` for 怎么采这些数.

- [ ] **Step 2: Acceptance checklist**

λ/W sourcing concrete; 峰均比 covered; fan-out tail-amplification with the 1-(0.99^N) math; 重尾 covered; 目标利用率留余 tied back to 01; little.py box; observability 指进.

- [ ] **Step 3: Commit**

```bash
git add concurrency-capacity/03-measure-demand/README.md
git commit -m "docs(concurrency-capacity): 03 测算并发需求 + fan-out 尾部放大"
```

---

### Task 9: Chapter 04 — 单机配置与线程/worker 数

**Files:**
- Create: `concurrency-capacity/04-sizing-one-node/README.md`

- [ ] **Step 1: Draft — depth model = derive thread formula + USL + USE saturation**

Content spec:
- **从需求到线程数**: 所需并发 L(03) → 单 worker 容量 → worker/线程数.
- **底层①推导真公式**: from Little, at target CPU: `线程数 = 核数 × (1 + 等待时间/计算时间)`. Derive 2N+1 as the wait≈compute special case. CPU-bound → ≈核数; I/O-bound(wait≫compute) → 远大于核数. Worked example.
- **底层②USL 天花板**: 线程不是越多越好——`saturate.py`:加线程到某点吞吐**回退**(上下文切换/锁争用 = κ 项). 所以「压测找拐点」不是偷懒,是找 USL peak.
- **底层③单机规格(USE 找饱和点)**: CPU/内存/FD/带宽哪个先饱和;USE 方法(Utilization-Saturation-Errors)逐资源查. 怎么决定是 CPU 型机还是内存型机.
- **Python 特例**: GIL → worker 进程数 ≈ 核数,每进程内 async;给 gunicorn/uvicorn worker 公式(指进 `python-concurrency/07`).
- **三语**: Java(线程池 core/max + 队列), Go(GOMAXPROCS + goroutine 无需手设池), Python(进程 worker × async).
- **动手盒子**: `python lab/sim/saturate.py` (see retrograde) + `lab/experiments/e04-find-saturation.md` (ramp real service to the knee).
- **指进**: `python-concurrency/07-prod-web-workers`, `performance-tuning-roadmap/01-methodology/02-use-method.md`.

- [ ] **Step 2: Acceptance checklist**

Thread formula derived from Little (not just stated); USL retrograde tied to saturate.py; USE per-resource saturation; Python GIL worker special case with 指进; 3-lang; both lab boxes; 指进 links.

- [ ] **Step 3: Commit**

```bash
git add concurrency-capacity/04-sizing-one-node/README.md
git commit -m "docs(concurrency-capacity): 04 单机定容 + 线程公式推导 + USL/USE"
```

---

### Task 10: `lab/sim/starve.py` + tests — pool wait-time blow-up

**Files:**
- Create: `concurrency-capacity/lab/sim/starve.py`
- Test: `concurrency-capacity/lab/sim/tests/test_starve.py`

**Interfaces:**
- Produces:
  - `mmc_wait(lam: float, service_time: float, c: int) -> float` — mean wait in queue for M/M/c (Erlang-C). Raises `ValueError` if `lam*service_time >= c` (offered load ≥ servers → unstable).
  - `pool_sweep(lam, service_time, c_values: list[int]) -> list[tuple[int, float]]` — `(c, wait)`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_starve.py
import pytest
from concurrency_capacity.lab.sim.starve import mmc_wait, pool_sweep

def test_more_servers_less_wait():
    # offered load a = λS = 8 erlangs; wait drops as c grows past 8
    w9 = mmc_wait(80, 0.1, 9)
    w12 = mmc_wait(80, 0.1, 12)
    assert w9 > w12 > 0

def test_unstable_when_load_exceeds_servers():
    with pytest.raises(ValueError):
        mmc_wait(80, 0.1, 8)   # a=8, c=8 → ρ=1, unstable

def test_wait_explodes_approaching_capacity():
    # c just above load → huge wait vs comfortable c
    tight = mmc_wait(80, 0.1, 9)
    loose = mmc_wait(80, 0.1, 16)
    assert tight > 10 * loose
```

- [ ] **Step 2: Run to verify fail**

Run: `cd concurrency-capacity && python -m pytest lab/sim/tests/test_starve.py -v` → FAIL ImportError.

- [ ] **Step 3: Implement `starve.py`** (Erlang-C formula; full implementation with the factorial/summation, guard `a>=c`).

```python
"""M/M/c pool: a connection/thread pool is c servers — watch wait blow up as c→load."""
import argparse, math

def _erlang_c(a: float, c: int) -> float:
    # probability an arrival must queue
    top = (a**c / math.factorial(c)) * (c / (c - a))
    bot = sum(a**k / math.factorial(k) for k in range(c)) + top
    return top / bot

def mmc_wait(lam: float, service_time: float, c: int) -> float:
    a = lam * service_time            # offered load in erlangs
    if a >= c:
        raise ValueError(f"offered load a={a} ≥ servers c={c}: pool unstable (ρ≥1)")
    pq = _erlang_c(a, c)
    return pq * service_time / (c - a)   # mean wait in queue

def pool_sweep(lam, service_time, c_values):
    out = []
    for c in c_values:
        try:
            out.append((c, mmc_wait(lam, service_time, c)))
        except ValueError:
            out.append((c, float("inf")))
    return out

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--lam", type=float, default=80)
    p.add_argument("--service-time", type=float, default=0.1)
    args = p.parse_args()
    a = args.lam * args.service_time
    print(f"offered load a = {a} erlangs (need c > {a})")
    for c, w in pool_sweep(args.lam, args.service_time, range(int(a)+1, int(a)+12)):
        print(f"c={c:<3} wait={w*1000:8.1f}ms  {'#'*min(60,int(w*200))}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run to verify pass**

Run: `cd concurrency-capacity && python -m pytest lab/sim/tests/test_starve.py -v` → PASS (3 passed). Eyeball `python lab/sim/starve.py` — wait explodes as c approaches the offered load.

- [ ] **Step 5: Commit**

```bash
git add concurrency-capacity/lab/sim/starve.py concurrency-capacity/lab/sim/tests/test_starve.py
git commit -m "feat(concurrency-capacity/lab): starve.py — M/M/c pool wait blow-up"
```

---

### Task 11: Chapter 05 — 池:哪些、多大、×worker 总账

**Files:**
- Create: `concurrency-capacity/05-pools/README.md`

- [ ] **Step 1: Draft — depth model = pool as M/M/c + small-pool-faster + ×worker 总账**

Content spec:
- **哪些资源要池**: 建立昂贵 + 数量稀缺 + 可复用(DB 连接、HTTP 连接、线程). 不是所有东西都要池.
- **底层①池 = M/M/c 队列**: 池大小 c = 服务台数;`starve.py`:c 逼近 offered load(a=λS)时等待爆炸. 所以池大小 ≥ offered load 才稳定,留余到 wait 可接受.
- **底层②「小池更快」反直觉**: HikariCP / PostgreSQL 经典结论——连接数 > DB 实际并行度(核数/磁盘)时,更多连接只增上下文切换、不增吞吐,反而更慢. 池不是越大越好;DB 自身并行度才是真上限.
- **底层③×worker 总账(经典坑)**: DB 总连接 = 单池 max × worker 数 × 副本数. 配 20×20×3=1200,撞 `max_connections`. 必须算总账(指进 `python-concurrency/09` 的同一坑,这里给定容公式).
- **怎么定 pool 大小**: from offered load(λ×S of the dependency) + headroom, capped by 下游并行度, summed against 下游 max.
- **三语**: HikariCP(Java), pgxpool/database-sql `SetMaxOpenConns`(Go), asyncpg/SQLAlchemy pool(Python).
- **动手盒子**: `python lab/sim/starve.py --lam .. --service-time ..` + `e05-pool-starvation.md`.
- **指进**: `python-concurrency/09-patterns-tuning` (×worker 坑的语言落地).

- [ ] **Step 2: Acceptance checklist**

Pool=M/M/c with starve.py; small-pool-faster (HikariCP/PG) explained with the *why*; ×worker×replica 总账 formula vs max_connections; sizing recipe; 3-lang; lab boxes; 指进.

- [ ] **Step 3: Commit**

```bash
git add concurrency-capacity/05-pools/README.md
git commit -m "docs(concurrency-capacity): 05 池定容 + M/M/c + 小池更快 + ×worker 总账"
```

---

### Task 12: `lab/sim/bulkhead.py` + tests — shared vs isolated pools

**Files:**
- Create: `concurrency-capacity/lab/sim/bulkhead.py`
- Test: `concurrency-capacity/lab/sim/tests/test_bulkhead.py`

**Interfaces:**
- Produces:
  - `simulate(shared: bool, fast_rate, slow_rate, slow_service, fast_service, capacity, ticks, seed=0) -> dict` — discrete-event sim of fast+slow traffic sharing one pool (`shared=True`) vs split pools. Returns `{"fast_rejected": int, "fast_p99_wait": float, "slow_rejected": int}`. Deterministic via `random.Random(seed)`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_bulkhead.py
from concurrency_capacity.lab.sim.bulkhead import simulate

def test_shared_pool_lets_slow_starve_fast():
    shared = simulate(shared=True, fast_rate=50, slow_rate=10, slow_service=20,
                      fast_service=1, capacity=16, ticks=2000, seed=1)
    isolated = simulate(shared=False, fast_rate=50, slow_rate=10, slow_service=20,
                        fast_service=1, capacity=16, ticks=2000, seed=1)
    # isolation protects the fast path: far fewer fast rejects / lower fast wait
    assert isolated["fast_rejected"] < shared["fast_rejected"]
    assert isolated["fast_p99_wait"] < shared["fast_p99_wait"]

def test_deterministic():
    a = simulate(shared=True, fast_rate=50, slow_rate=10, slow_service=20,
                 fast_service=1, capacity=16, ticks=1000, seed=7)
    b = simulate(shared=True, fast_rate=50, slow_rate=10, slow_service=20,
                 fast_service=1, capacity=16, ticks=1000, seed=7)
    assert a == b
```

- [ ] **Step 2: Run to verify fail** → ImportError.

Run: `cd concurrency-capacity && python -m pytest lab/sim/tests/test_bulkhead.py -v`

- [ ] **Step 3: Implement `bulkhead.py`** — a simple tick-based discrete-event simulator: each tick, Poisson-ish arrivals (seeded RNG) for fast & slow classes; busy servers occupied for their service ticks; shared mode = one capacity pool both classes draw from, isolated mode = capacity split (e.g. proportional). Record rejects (arrival when pool full) and per-class wait. (Full ~70-line implementation.)

- [ ] **Step 4: Run to verify pass** → PASS (2 passed). Eyeball printed summary shared vs isolated.

- [ ] **Step 5: Commit**

```bash
git add concurrency-capacity/lab/sim/bulkhead.py concurrency-capacity/lab/sim/tests/test_bulkhead.py
git commit -m "feat(concurrency-capacity/lab): bulkhead.py — shared vs isolated pool sim"
```

---

### Task 13: Chapter 06 — 隔离 / 舱壁

**Files:**
- Create: `concurrency-capacity/06-isolation/README.md`

- [ ] **Step 1: Draft — depth model = HoL blocking + semaphore vs thread isolation + shuffle sharding**

Content spec:
- **何时需要隔离**: 不同工作负载共享一个池时,一类把池占满会饿死另一类.
- **底层①队头阻塞 → 级联耗尽**: 慢依赖把共享线程池/连接池占满,快请求拿不到资源 → 整服务雪崩. `bulkhead.py`:shared vs isolated 对比,看快路被慢路拖死/被保护.
- **底层②信号量隔离 vs 线程隔离(Hystrix)**: semaphore-isolation(轻,不能中断慢调用)vs thread-pool-isolation(可超时中断,有切换成本). 何时用哪个.
- **底层③shuffle sharding(进阶)**: AWS 的做法——给每个租户分一个随机子集池,单租户故障只影响少数邻居,概率上隔离. 一段直觉.
- **怎么拆**: 按 快/慢、CPU/IO、关键/非关键、租户. 每类独立池,池大小回到 05 的定容.
- **三语**: Resilience4j Bulkhead(Java), Go errgroup+独立 semaphore/池, Python 独立 `Semaphore`/`run_in_executor` 专用池.
- **动手盒子**: `python lab/sim/bulkhead.py` + `e06-bulkhead.md` (real service: 慢端点不拖死快端点).
- **指进**: `python-concurrency/09` (§3.5 隔离), `system-design/` 韧性章 if present.

- [ ] **Step 2: Acceptance checklist**

HoL→cascade with bulkhead.py; semaphore vs thread isolation tradeoff; shuffle sharding mentioned; partition axes; 3-lang; lab boxes; 指进.

- [ ] **Step 3: Commit**

```bash
git add concurrency-capacity/06-isolation/README.md
git commit -m "docs(concurrency-capacity): 06 隔离/舱壁 + HoL + 信号量vs线程隔离"
```

---

### Task 14: Chapter 07 — 过载与背压

**Files:**
- Create: `concurrency-capacity/07-overload-backpressure/README.md`

- [ ] **Step 1: Draft — depth model = shed vs block + retry-storm + deadline + metastable**

Content spec:
- **过了饱和点会怎样**: Little 定律下 ρ≥1 → 队列无界增长 → 延迟雪崩 → 全部超时. 无界队列 = 把内存当缓冲、把延迟无限累积 = 致命.
- **底层①有界队列 + shed vs block**: 满了要么拒绝(load-shedding,快速失败保护自己)要么阻塞(背压传导给上游). 给选择依据.
- **底层②重试风暴的乘性放大**: 下游抖动 → 上游重试 → 放大 2-3× 负载 → 把下游彻底打死. 给放大数学 + 缓解(退避+抖动+重试预算+断路器). 重试只在有 budget 时.
- **底层③deadline 传播**: 超时即背压;每跳带剩余 deadline,别让已超时的请求继续消耗下游(对标 gRPC deadline propagation).
- **底层④metastable failure**: 系统在触发器移除后仍卡在坏稳态(重试/缓存失效自我维持). 一段 + 怎么打破(降载到坏稳态以下).
- **过载下 LIFO**: 过载时后进先出比 FIFO 救活更多请求(老请求大概率已超时).
- **三语**: Java(Resilience4j RateLimiter/Bulkhead/CircuitBreaker), Go(`golang.org/x/time/rate`, context deadline), Python(`asyncio.Semaphore` + tenacity + `asyncio.timeout`).
- **动手盒子**: `e07-overload-collapse.md` — drive real service past the knee, watch latency collapse + rejects.
- **指进**: `python-concurrency/09` (超时/重试/熔断落地), `distribution/限流算法`.

- [ ] **Step 2: Acceptance checklist**

unbounded-queue death; shed vs block; retry-storm amplification math; deadline propagation; metastable failure; LIFO-under-load; 3-lang; experiment box; 指进 (incl. `distribution/限流算法`).

- [ ] **Step 3: Commit**

```bash
git add concurrency-capacity/07-overload-backpressure/README.md
git commit -m "docs(concurrency-capacity): 07 过载与背压 + 重试风暴 + metastable"
```

---

### Task 15: Chapter 08 — 在线监控并发

**Files:**
- Create: `concurrency-capacity/08-monitoring-concurrency/README.md`

- [ ] **Step 1: Draft — depth model = utilization deceives + saturation leading indicator + USE/RED**

Content spec:
- **监控什么**: 并发的四个实时读数 = Little 定律的实时投影——在途数 L、到达率 λ、利用率 ρ、队列深度/等待.
- **底层①利用率会骗人**: 平均利用率 50% 仍可能在尾部饱和(方差/突发,回到 01 Kingman). 利用率是滞后/平均指标.
- **底层②饱和度=队列深度才是领先指标**: 队列开始堆积是过载的第一信号,早于延迟飙升和错误. 盯队列/等待时间.
- **底层③USE vs RED**: USE(资源:利用率-饱和度-错误)给机器视角;RED(请求:Rate-Errors-Duration)给服务视角;并发定容两个都要.
- **底层④聚合陷阱**: 不能对 P99 求平均/相加;要 histogram 合并(指进 01 的 coordinated omission 同源问题).
- **该配哪些图/告警**: in-flight、pool 使用率、pool 等待、队列深度、P99、reject 率;告警在饱和度而非利用率.
- **三语**: Micrometer/Prometheus(Java), expvar+Prometheus(Go), OTel/prometheus-client(Python). 服务暴露 `/stats`(lab service 已有).
- **动手盒子**: `e08-read-the-signals.md` — drive service, read in_flight/rejected from `/stats`, watch saturation lead latency.
- **指进**: `observability/`, `performance-tuning-roadmap/03-observability`, `logging/`.

- [ ] **Step 2: Acceptance checklist**

four readings = Little projection; utilization-deceives tied to Kingman; saturation=queue leading indicator; USE vs RED; percentile aggregation pitfall; alert-on-saturation; 3-lang; experiment box; 指进 to observability stack.

- [ ] **Step 3: Commit**

```bash
git add concurrency-capacity/08-monitoring-concurrency/README.md
git commit -m "docs(concurrency-capacity): 08 在线监控并发 + USE/RED + 饱和度领先"
```

---

### Task 16: Chapter 09 — 横向扩容与成本

**Files:**
- Create: `concurrency-capacity/09-scaling-out/README.md`

- [ ] **Step 1: Draft — depth model = USL vertical ceiling + scale economics + autoscale signal**

Content spec:
- **单机到机群**: 单节点定容(04-08)做完,把它乘起来. 机群数 = 总需求 L / 单节点容量 + 冗余(N+1/N+2).
- **底层①USL 决定纵向天花板**: 加核/加线程到 USL peak 后回退(κ 项),所以纵向有上限,过了拐点必须横向. 给「先纵向到 USL peak,再横向」的判据(回到 04 saturate.py).
- **底层②纵向 vs 横向经济学**: 大机器单价非线性(贵)、有 USL 上限;小机器横向线性扩、但加协调成本(LB/状态/网络). 每 RPS 成本曲线.
- **底层③自动扩缩的信号**: 按 CPU 扩容会滞后(CPU 是滞后指标);按**并发/队列深度/RPS** 扩容才领先(回到 08). 给 HPA on custom metric 的思路.
- **冗余与峰值**: 按峰值 + 突发 + 故障域(挂一个 AZ 仍要扛)定机群,不是按均值.
- **三语/平台中立**: K8s HPA、云 ASG;指进 `cloud-native/` 弹性章.
- **动手盒子**: `python lab/sim/saturate.py` 找单机 USL peak → 推机群数(给一个算例).
- **指进**: `system-design/` 扩展性章, `cloud-native-landscape/` 弹性成本环, `cloud-native/`.

- [ ] **Step 2: Acceptance checklist**

fleet = demand/node-capacity + redundancy; USL vertical ceiling tied to saturate.py; vertical-vs-horizontal economics + cost/RPS; autoscale on concurrency-not-CPU tied to 08; peak+failure-domain sizing; 指进 to cloud-native/system-design.

- [ ] **Step 3: Commit**

```bash
git add concurrency-capacity/09-scaling-out/README.md
git commit -m "docs(concurrency-capacity): 09 横向扩容与成本 + USL 天花板 + 扩容信号"
```

---

### Task 17: Chapter 99 — 面试卡

**Files:**
- Create: `concurrency-capacity/99-interview-cards/README.md`

**Interfaces:**
- Consumes: all chapters 00–09 (cards link back as evidence).

- [ ] **Step 1: Draft the cards (review layer only — no new knowledge)**

Content spec: a 速答表 (Q→one-line answer→章节链接) covering the user's original 7 questions verbatim:
1. 怎么测算生产并发需求? → λ×W + 峰均比 + fan-out 放大 (→03)
2. 单机配多少线程/worker? → `核数×(1+等待/计算)`,USL 找拐点 (→04)
3. 单机什么规格? → USE 找先饱和的资源 (→04)
4. 哪些要 pool、pool 多大? → 稀缺可复用资源;M/M/c ≥ offered load,受下游并行度封顶,算 ×worker 总账 (→05)
5. 要不要隔离? → 共享池有队头阻塞级联风险就隔离 (→06)
6. 过载怎么办? → 有界队列 shed/block + 退避重试 + deadline,防重试风暴/metastable (→07)
7. 要不要监控、监控什么? → 要;盯饱和度(队列)领先于利用率,USE+RED (→08)
- Then 4-6 深题卡: "为什么 P99 会拐(M/M/1)", "为什么小连接池反而更快", "重试为什么会放大故障", "利用率 50% 为什么还会超时(Kingman)" — each = 问题 + 资深答法 + 链回章节做证据.

- [ ] **Step 2: Acceptance checklist**

All 7 original questions answered with chapter links; ≥4 深题卡 each linking back; no new knowledge introduced (review layer only).

- [ ] **Step 3: Commit**

```bash
git add concurrency-capacity/99-interview-cards/README.md
git commit -m "docs(concurrency-capacity): 99 面试卡(7 问速答 + 深题卡)"
```

---

### Task 18: Experiment runbooks + README progress finalize

**Files:**
- Create: `concurrency-capacity/lab/experiments/e02-model-shootout.md`, `e04-find-saturation.md`, `e05-pool-starvation.md`, `e06-bulkhead.md`, `e07-overload-collapse.md`, `e08-read-the-signals.md`
- Modify: `concurrency-capacity/README.md` (progress table → all ✅; lab section finalized)

**Interfaces:**
- Consumes: `lab/sim/*` and `lab/service/*` (Tasks 2,5,7,10,12).

- [ ] **Step 1: Write each runbook**

Each runbook (Simplified Chinese) has a fixed shape: **目的**(which chapter claim it proves) / **跑什么**(exact commands) / **你会看到什么**(expected numbers/curve) / **为什么**(tie to the depth model). E.g. `e04-find-saturation.md`: `POOL_SIZE=8 uvicorn ...` then `python lab/service/drive.py --steps 50,100,200,400,800` → P99 hockey-sticks at the knee, QPS plateaus → that knee is the USL peak from Task 5.

- [ ] **Step 2: Finalize README progress table**

Set every chapter + lab row to ✅. Verify all 11 chapter links + 6 experiment links + 4 sim links resolve.

- [ ] **Step 3: Acceptance checklist**

6 runbooks each with 目的/跑什么/你会看到/为什么; all README links resolve; progress table complete.

- [ ] **Step 4: Commit**

```bash
git add concurrency-capacity/lab/experiments/ concurrency-capacity/README.md
git commit -m "docs(concurrency-capacity): lab 实验 runbook + 进度收尾"
```

---

## Self-Review

**Spec coverage** (spec §5 chapters + §3.1 depth contract + §6 lab):
- Ch 00–09 + 99 → Tasks 3,4,6,8,9,11,13,14,15,16,17 ✅
- Depth-contract rows 01–09 → each chapter task names its required model in Step 1 ✅
- Lab sim/ (little/saturate/starve/bulkhead) → Tasks 2,5,10,12 ✅
- Lab service/ → Task 7 ✅; experiments/ → Task 18 ✅
- 指进 links (spec §8) → present in each chapter's content spec ✅
- 3-lang callouts (spec §3) → in each chapter checklist ✅
- README index + progress → Tasks 1, 18 ✅

**Placeholder scan:** Lab code tasks contain full implementations/tests. Chapter tasks intentionally carry content-specs + acceptance checklists (not pre-written prose) — the deliverable IS the prose; the checklist is its acceptance test. `app.py`/`drive.py`/`bulkhead.py` bodies are described as "full file ~N lines" rather than fully inlined to keep the plan readable — the implementer writes them against the stated interface + tests. This is the one deliberate deviation from "complete code in every step," flagged here.

**Type consistency:** `little_l`, `mm1_response`, `mm1_curve`, `usl_throughput`, `usl_curve`, `peak_n`, `mmc_wait`, `pool_sweep`, `simulate`, `app`, `ramp` — names used consistently between their defining task's Interfaces block and the tests. Import path `concurrency_capacity.lab.sim.*` assumes `__init__.py` scaffolding (noted in Task 2 Step 2) — implementer must add `__init__.py` or a `conftest.py`/`pyproject` rootdir; flagged.
