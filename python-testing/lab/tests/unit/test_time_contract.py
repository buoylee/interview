from datetime import datetime, timedelta, tzinfo

import pytest

from tests.factories import make_order


class _OffsetlessTimezone(tzinfo):
    def utcoffset(self, dt: datetime | None) -> timedelta | None:
        return None


def test_order_rejects_naive_created_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        make_order(created_at=datetime(2026, 7, 15))


def test_order_rejects_timezone_without_utc_offset() -> None:
    created_at = datetime(2026, 7, 15, tzinfo=_OffsetlessTimezone())

    with pytest.raises(ValueError, match="timezone-aware"):
        make_order(created_at=created_at)
