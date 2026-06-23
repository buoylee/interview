"""最小 LLM 網關(對應 ch10)。實作兩個 LLM 網關特有能力:

  1. 語義快取(ch10 §3):用「字元 n-gram + 餘弦相似度」近似語義匹配。
     相似度 >= 閾值就命中歷史回答,省掉一次 LLM 調用,且不計費。
     ⚠️ 這是教學近似(純字面)。生產用真 embedding 模型(sentence-transformers /
        OpenAI embeddings)+ 向量索引(pgvector/Milvus/Redis 向量),語義更準。

  2. 按 token 預算限流(ch10 §2 = ch05 限流的 token 版):每 client 累計 token,
     超過 BUDGET 就 429。語義快取命中不計費 —— 這正是它省成本的意義。
"""
import json
import math
import os
from collections import Counter

import httpx
import redis
from fastapi import FastAPI
from fastapi.responses import JSONResponse

LLM_URL = os.environ.get("LLM_URL", "http://fake-llm:8000/v1/chat")
BUDGET = int(os.environ.get("BUDGET", "200"))        # 每 client 窗口內 token 預算
WINDOW = int(os.environ.get("WINDOW", "300"))        # 預算窗口秒數
THRESHOLD = float(os.environ.get("THRESHOLD", "0.6"))  # 語義快取命中閾值(配字元 2-gram 近似;真 embedding 用 ~0.9)
CACHE_KEY = "llmcache"

r = redis.Redis(host=os.environ.get("REDIS_HOST", "redis"), port=6379, decode_responses=True)
app = FastAPI()


def ngram_vec(text: str, n: int = 2) -> Counter:
    grams = [text[i:i + n] for i in range(max(0, len(text) - n + 1))] or [text]
    return Counter(grams)


def cosine(a: Counter, b: Counter) -> float:
    common = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


@app.post("/chat")
def chat(body: dict):
    client = body.get("client", "anon")
    prompt = body.get("prompt", "")
    qv = ngram_vec(prompt)

    # 1) 語義快取查找:掃過歷史 prompt,取最相似的(lab 用 O(N) 掃;生產用向量索引)
    best, best_sim = None, 0.0
    for raw in r.lrange(CACHE_KEY, 0, -1):
        item = json.loads(raw)
        sim = cosine(qv, Counter(item["vec"]))
        if sim > best_sim:
            best_sim, best = sim, item
    if best and best_sim >= THRESHOLD:
        return {"cached": True, "similarity": round(best_sim, 3),
                "answer": best["answer"], "tokens_charged": 0}

    # 2) token 預算檢查(快取沒命中才需要真打 LLM、才計費)
    used = int(r.get(f"tokens:{client}") or 0)
    if used >= BUDGET:
        return JSONResponse(status_code=429,
                            content={"error": "token budget exceeded", "used": used, "budget": BUDGET})

    # 3) 打後端 LLM
    resp = httpx.post(LLM_URL, json={"prompt": prompt}, timeout=10).json()
    answer, tokens = resp["answer"], resp["usage"]["total_tokens"]

    # 4) 計費(累計 token)+ 存入語義快取
    new_used = r.incrby(f"tokens:{client}", tokens)
    if new_used == tokens:                       # 首次設窗口過期
        r.expire(f"tokens:{client}", WINDOW)
    r.rpush(CACHE_KEY, json.dumps({"prompt": prompt, "answer": answer, "vec": dict(qv)}))

    return {"cached": False, "answer": answer,
            "tokens_charged": tokens, "used": new_used, "budget": BUDGET}
