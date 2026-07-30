from collections.abc import Callable
import time
from typing import Protocol

from workload.model import LedgerRecord, OrderRequest, Outcome, utc_now


INSERT_ORDER = """
INSERT INTO ha_lab.orders(request_id, payload, via_router, written_by)
VALUES (%s, CAST(%s AS JSON), %s, @@hostname)
ON DUPLICATE KEY UPDATE request_id = VALUES(request_id)
"""

AMBIGUOUS_TRANSPORT_ERRNOS = {2006, 2013, 2055}


class Cursor(Protocol):
    def execute(self, sql: str, params: tuple[str, str, str]) -> None: ...

    def close(self) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...

    def commit(self) -> None: ...

    def close(self) -> None: ...


def execute_order(
    connect: Callable[[], Connection],
    request: OrderRequest,
    max_connect_retries: int,
) -> LedgerRecord:
    started_at = utc_now()
    retries = 0
    connection: Connection | None = None
    cursor: Cursor | None = None

    while True:
        try:
            connection = connect()
            cursor = connection.cursor()
            break
        except Exception as error:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
            if retries >= max_connect_retries:
                return LedgerRecord(
                    request.request_id,
                    request.payload,
                    request.router,
                    started_at,
                    utc_now(),
                    Outcome.FAILURE,
                    retries,
                    type(error).__name__,
                )
            retries += 1
            time.sleep(min(0.1 * (2**retries), 1.0))

    try:
        cursor.execute(
            INSERT_ORDER,
            (request.request_id, request.payload, request.router),
        )
        connection.commit()
        return LedgerRecord(
            request.request_id,
            request.payload,
            request.router,
            started_at,
            utc_now(),
            Outcome.SUCCESS,
            retries,
            None,
        )
    except Exception as error:
        errno = getattr(error, "errno", None)
        outcome = (
            Outcome.FAILURE
            if errno is not None and errno not in AMBIGUOUS_TRANSPORT_ERRNOS
            else Outcome.UNKNOWN
        )
        return LedgerRecord(
            request.request_id,
            request.payload,
            request.router,
            started_at,
            utc_now(),
            outcome,
            retries,
            type(error).__name__,
        )
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            connection.close()
        except Exception:
            pass
