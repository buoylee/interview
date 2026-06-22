"""驗證腳本:打四種請求,把產生的結構化日誌印到 stdout。

不需要起 server —— 用 FastAPI 內建 TestClient 直接驅動 app。
    python smoke_test.py
"""

from fastapi.testclient import TestClient

from app import app

client = TestClient(app, raise_server_exceptions=False)

for uid in [42, 0, 13, 99]:
    client.get(f"/users/{uid}", headers={"X-Request-ID": f"req-{uid}"})
