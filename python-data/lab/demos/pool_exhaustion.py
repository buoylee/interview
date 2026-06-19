"""Demo: connection-pool exhaustion.

pool_size=2, max_overflow=0 => only 2 connections ever exist. Two threads
hold them for 3s; a third checkout waits pool_timeout=1s and then raises
QueuePool TimeoutError. This is what "pool exhausted" looks like in prod.

Run: uv run python demos/pool_exhaustion.py
"""
import pathlib
import sys
import threading
import time

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import TimeoutError as SATimeoutError  # noqa: E402

from db import make_engine  # noqa: E402

engine = make_engine(pool_size=2, max_overflow=0, pool_timeout=1)


def hold(i, secs):
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        print(f"conn {i}: acquired")
        time.sleep(secs)
    print(f"conn {i}: released")


for i in range(2):  # occupy the whole pool (size 2)
    threading.Thread(target=hold, args=(i, 3), daemon=True).start()
time.sleep(0.5)  # let both threads check out their connection

t0 = time.perf_counter()
try:
    with engine.connect() as conn:  # third checkout: nothing available
        conn.execute(text("SELECT 1"))
except SATimeoutError as e:
    print(f"conn 2: TimeoutError after {time.perf_counter() - t0:.2f}s -> {e}")
