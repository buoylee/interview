from bulkhead import simulate

# fast = cheap+frequent, slow = expensive+bursty; slow oversubscribes a shared pool.
PARAMS = dict(fast_rate=0.6, slow_rate=0.08, slow_service=40, fast_service=1,
              capacity=4, ticks=4000, seed=1)


def test_shared_pool_lets_slow_starve_fast():
    shared = simulate(shared=True, **PARAMS)
    isolated = simulate(shared=False, **PARAMS)
    # isolation protects the fast path: fewer fast rejects AND lower fast wait
    assert isolated["fast_rejected"] < shared["fast_rejected"]
    assert isolated["fast_p99_wait"] < shared["fast_p99_wait"]


def test_deterministic():
    a = simulate(shared=True, **PARAMS)
    b = simulate(shared=True, **PARAMS)
    assert a == b
