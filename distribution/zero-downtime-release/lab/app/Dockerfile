FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .

EXPOSE 8000

# exec form(JSON 数组)→ uvicorn 直接当 PID 1,亲自收 SIGTERM 走优雅关。
# 若写成 shell form("uvicorn ..."),PID 1 会是 sh、不转发 SIGTERM → 优雅关失效
# (见 fastapi-ops/01 B′2)。
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
