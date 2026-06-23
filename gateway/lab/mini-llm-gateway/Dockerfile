FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" "redis>=5" httpx
COPY gateway.py fake_llm.py ./
# 用環境變數 APP 決定起哪個服務(gateway 或 fake_llm)
CMD ["sh", "-c", "uvicorn ${APP}:app --host 0.0.0.0 --port 8000"]
