import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app import app, state

client = TestClient(app)


def test_fast_ok():
    assert client.get("/fast").status_code == 200


def test_healthz():
    assert client.get("/healthz").json()["status"] == "ok"


def test_stats_shape():
    body = client.get("/stats").json()
    assert {"in_flight", "max_in_flight", "rejected", "pool_size", "model"} <= body.keys()


@pytest.mark.anyio
async def test_slow_respects_pool_when_full():
    # pool_size=1 → two concurrent /slow: one served (200), one shed (503)
    state.pool_size = 1
    state.rejected = 0
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as ac:
        r1, r2 = await asyncio.gather(
            ac.get("/slow?ms=200"),
            ac.get("/slow?ms=200"),
        )
    codes = sorted([r1.status_code, r2.status_code])
    assert codes == [200, 503]
    assert state.rejected == 1
