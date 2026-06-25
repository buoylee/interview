# lab/proxy-cache — HIT/MISS/STALE + cache_lock 實測

對照：`nginx/05-proxy-cache.md`（ch05）。

## 目標

| 觀察點 | 預期結果 |
|--------|----------|
| 首次請求 `X-Cache-Status` | `MISS`（後端計數 +1，sleep 1 秒） |
| 再次請求 `X-Cache-Status` | `HIT`（從快取回，不碰後端） |
| 命中期間 body/count | 不變（`PASS: body unchanged`） |
| `/stale/` | 快取過期後回源途中可能回 `STALE`/`UPDATING` |

## 元件

```
client → nginx:80 (port 18081) → backend:5000 (python http.server)
```

- **backend.py**：每次被呼叫就計數 +1 並 `sleep 1`，body 是 `count=N`。
- **nginx.conf**：
  - `proxy_cache_path` 定義 zone `my_cache`
  - `/cached/`：`proxy_cache_valid 200 10s` + `proxy_cache_lock on`（防止多個並發請求同時打穿後端）
  - `/stale/`：額外 `proxy_cache_use_stale error timeout updating`
  - `add_header X-Cache-Status $upstream_cache_status` 讓 client 看到命中狀態

## 怎麼跑

```bash
# 啟動（detached）
docker compose up -d

# 等服務就緒後執行斷言腳本
sleep 4 && bash run.sh

# 清理
docker compose down -v
```

一鍵跑完（含清理）：

```bash
docker compose up -d && sleep 4 && bash run.sh; rc=$?; docker compose down -v; echo "EXIT=$rc"
```

## 預期輸出

```
=== proxy-cache lab ===
first  -> X-Cache-Status: MISS
PASS: first request MISS
second -> X-Cache-Status: HIT
PASS: second request HIT
PASS: body unchanged while cached (count=1)
=== ALL PASS ===
```

## 對照 ch05 概念

| 概念 | 本 lab 驗證方式 |
|------|----------------|
| `proxy_cache_path` / zone | `my_cache:1m` |
| `proxy_cache_valid` | 10 秒 TTL — 10 秒後再請求應回 MISS |
| `proxy_cache_lock` | 啟動後連發多個請求，後端 sleep 1 秒，`lock on` 確保只有一個去回源 |
| `X-Cache-Status` | 直接看 header：MISS/HIT/EXPIRED/STALE/UPDATING |
| `proxy_cache_use_stale` | `/stale/` 路徑：快取過期期間回源失敗可回舊快取 |
