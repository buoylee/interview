"""對應 ch05 §2:分散式限流。一個極簡網關節點。

多個節點(node1/node2)共用同一個 Redis 計數,證明限流是「全域」的——
不管請求落到哪台節點,合起來才是一份配額。
"""
import os
import pathlib
from fastapi import FastAPI, Response
import redis

NODE_ID = os.environ.get("NODE_ID", "node?")
LIMIT = int(os.environ.get("LIMIT", "10"))      # 窗口內允許次數
WINDOW = int(os.environ.get("WINDOW", "30"))    # 窗口秒數

r = redis.Redis(host=os.environ.get("REDIS_HOST", "redis"), port=6379, decode_responses=True)
LUA = pathlib.Path(__file__).with_name("ratelimit.lua").read_text()

app = FastAPI()


@app.get("/ping")
def ping(client: str = "anon"):
    # 對共享的 Redis 計數做原子限流。allowed = 當前計數,或 -1 表示超限。
    allowed = r.eval(LUA, 1, f"rate:{client}", str(LIMIT), str(WINDOW))
    if allowed == -1:
        return Response(content=f"{NODE_ID}: 429 rate limited (client={client})\n", status_code=429)
    return Response(content=f"{NODE_ID}: 200 count={allowed}/{LIMIT} (client={client})\n", status_code=200)
