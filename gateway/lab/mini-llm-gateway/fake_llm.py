"""離線 fake LLM(對應 ch10)。模擬一個 LLM 供應商:回固定文本,
並在 usage 裡回報 token 用量(用字元數粗估),好讓網關做計費。
不需要任何真實 API key —— 整個 lab 離線可跑。
"""
from fastapi import FastAPI

app = FastAPI()


@app.post("/v1/chat")
def chat(body: dict):
    prompt = body.get("prompt", "")
    answer = f"(模擬回答)關於「{prompt[:24]}」:這是離線 fake LLM 的固定回應,用於 lab。"
    total_tokens = len(prompt) + len(answer)   # 用字元數當 token 粗估(真實供應商按真 token 計)
    return {"answer": answer, "usage": {"total_tokens": total_tokens}}
