# examples — 三語言生產級日誌可跑範例

對應 `logging/08-生產級完整範例-三語言.md`。同一個服務(`GET /users/{id}`,四種情境)三語言各一份,把六章紀律組裝在一起。**三份都已在本機實跑驗證過。**

| 情境 | 觸發 | 等級 | 回應 |
|---|---|---|---|
| 成功 | `id=42` | INFO | 200 |
| 參數非法 | `id=0` | INFO(非 ERROR) | 400 |
| 查無此人 | `id=13` | INFO(非 ERROR) | 404 |
| 下游故障 | `id=99` | ERROR(完整堆疊+cause) | 500 |

## Python(FastAPI + dictConfig + contextvars)

```bash
cd python
pip install -r requirements.txt
python smoke_test.py                 # 免起 server,直接打四種請求看輸出
# 或起 server:
uvicorn app:app --port 8080 --no-access-log
curl -H 'X-Request-ID: demo-1' localhost:8080/users/99
```

## Go(gin + slog)

```bash
cd go
go mod tidy
go test -v                           # httptest 驗證 + 看 JSON 輸出
# 或起 server:
go run .
curl -H 'X-Request-ID: demo-1' localhost:8080/users/99
```

## Java(Spring Boot + Logback JSON + MDC)

```bash
cd java
mvn test                             # MockMvc 驗證 + 看 JSON 輸出
# 或起 server:
mvn spring-boot:run
curl -H 'X-Request-ID: demo-1' localhost:8080/users/99
```

## 看什麼

每份輸出都驗收這五件事(逐條對照 `08` 第五節):

1. `request_id` 出現在該請求的每一行。
2. 故障只記一次 ERROR + 完整 cause 鏈(無 cascade 重複)。
3. 400 / 404 是 INFO 不是 ERROR。
4. 每行是結構化 JSON、寫 stdout。
5. 請求進/出各一條、帶 latency。
