from __future__ import annotations

import argparse
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from sqlalchemy import event, text
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.pool import QueuePool

from order_service.db.engine import build_engine
from order_service.db.settings import DatabaseSettings
from scenarios._evidence import Evidence, write_evidence


@dataclass(frozen=True, slots=True)
class PoolExhaustionObservation:
    waited_seconds: float
    error_message: str
    checked_out_at_timeout: int
    event_names: tuple[str, ...]
    checked_out_after_recovery: int


def observe_pool_exhaustion(settings: DatabaseSettings) -> PoolExhaustionObservation:
    engine = build_engine(
        settings,
        pool_size=2,
        max_overflow=0,
        pool_timeout=0.2,
        pool_pre_ping=False,
    )
    both_checked_out = threading.Barrier(3)
    release = threading.Event()
    holder_errors: list[Exception] = []
    pool = cast(QueuePool, engine.pool)
    event_names: list[str] = []
    event_lock = threading.Lock()

    def record_event(name: str) -> None:
        with event_lock:
            event_names.append(name)

    def record_checkout(*_args: object) -> None:
        record_event("checkout")

    def record_reset(*_args: object) -> None:
        record_event("reset")

    def record_checkin(*_args: object) -> None:
        record_event("checkin")

    event.listen(pool, "checkout", record_checkout)
    event.listen(pool, "reset", record_reset)
    event.listen(pool, "checkin", record_checkin)

    def hold_connection() -> None:
        try:
            with engine.connect() as connection:
                connection.scalar(text("SELECT 1"))
                both_checked_out.wait(timeout=2)
                if not release.wait(timeout=2):
                    raise TimeoutError("holder release timed out")
        except Exception as error:
            holder_errors.append(error)

    threads = [threading.Thread(target=hold_connection) for _ in range(2)]
    timeout_result: tuple[float, str, int] | None = None
    try:
        try:
            for thread in threads:
                thread.start()
            both_checked_out.wait(timeout=2)
            started = time.perf_counter()
            try:
                third_connection = engine.connect()
            except SQLAlchemyTimeoutError as error:
                waited = time.perf_counter() - started
                record_event("timeout")
                timeout_result = (waited, str(error), pool.checkedout())
            else:
                third_connection.close()
                raise AssertionError("third checkout unexpectedly succeeded")
        finally:
            record_event("release")
            release.set()
            for thread in threads:
                if thread.ident is not None:
                    thread.join(timeout=2)
                    if thread.is_alive():
                        holder_errors.append(
                            TimeoutError("connection holder did not stop")
                        )
        if holder_errors:
            raise ExceptionGroup("connection holders failed", holder_errors)
        if timeout_result is None:
            raise AssertionError("pool exhaustion observation was not captured")

        with engine.connect() as connection:
            connection.scalar(text("SELECT 1"))

        waited, error_message, checked_out_at_timeout = timeout_result
        return PoolExhaustionObservation(
            waited_seconds=waited,
            error_message=error_message,
            checked_out_at_timeout=checked_out_at_timeout,
            event_names=tuple(event_names),
            checked_out_after_recovery=pool.checkedout(),
        )
    finally:
        engine.dispose()


def run(settings: DatabaseSettings) -> Evidence:
    observed = observe_pool_exhaustion(settings)
    return Evidence(
        title="Chapter 06 — Pooling and capacity",
        hypothesis=(
            "pool_size=2 and max_overflow=0 allow exactly two simultaneous checkouts.",
            "A third checkout waits pool_timeout before SQLAlchemy raises TimeoutError.",
        ),
        setup=("pool_size=2", "max_overflow=0", "pool_timeout=0.2 seconds"),
        command="uv run python -m scenarios.ch06_pooling_capacity",
        observation=(
            "configured_hard_limit=2",
            f"checked_out_at_timeout={observed.checked_out_at_timeout}",
            "timeout_class=sqlalchemy.exc.TimeoutError",
            "naive_checkout_timed_out=True",
            "corrected_pool_recovered="
            f"{observed.checked_out_after_recovery == 0}",
            "timeout_within_expected_bound="
            f"{0.15 <= observed.waited_seconds < 0.8}",
            f"error_message={observed.error_message}",
        ),
        explanation=(
            "QueuePool limits concurrent checked-out connections, not request concurrency.",
            "The process-wide ceiling multiplies pool limits by workers and service instances.",
        ),
        decision=(
            "Budget database connections across all processes before changing pool_size.",
        ),
        caveat=(
            "The timeout duration is an invariant window; scheduler-level milliseconds "
            "vary by host.",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("evidence/ch06-pooling-capacity.md"),
    )
    args = parser.parse_args()
    write_evidence(args.evidence, run(DatabaseSettings.from_env()))


if __name__ == "__main__":
    main()
