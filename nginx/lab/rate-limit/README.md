# Lab: rate-limit — 驗證 limit_req burst/nodelay 行為

對應章節：ch06「限速與防濫用」

---

## 目標

用真實 Nginx 展示 `limit_req` 三種模式的差異：

| 路徑 | 設定 | 行為 |
|------|------|------|
| `/strict/` | 無 burst | 超過速率立即 429 |
| `/burst/` | `burst=5 nodelay` | 允許瞬間 5 個超量請求，不排隊，超過才 429 |

---

## 前置條件

- Docker Engine（含 Compose plugin）
- port 18082 未被佔用

---

## 快速跑

```bash
docker compose up -d
sleep 3
bash run.sh
docker compose down -v
```

---

## 預期輸出

```
=== /strict/ (無 burst) ===
狀態碼: 200 429 429 429 429 429 429 429 429 429
200 數: 1  |  429 數: 9

=== /burst/ (burst=5 nodelay) ===
狀態碼: 200 200 200 200 200 200 429 429 429 429
200 數: 6  |  429 數: 4

=== 驗證 ===
PASS: strict 200(1) < burst 200(6)，兩者都有 429
```

數字可能因機器速度略有偏差，只要 `/burst/` 的 200 數**明顯多於** `/strict/` 即為正常。

---

## 核心概念

### `limit_req_zone`

```nginx
limit_req_zone $binary_remote_addr zone=demo:10m rate=5r/s;
```

- `$binary_remote_addr`：以客戶端 IP 計數（二進位格式省空間）
- `zone=demo:10m`：共享記憶體區塊，名為 demo，10 MB 可追蹤約 160,000 個 IP
- `rate=5r/s`：令牌桶速率，每秒最多 5 個請求（= 每 200ms 一個）

### `limit_req`（無 burst）

```nginx
limit_req zone=demo;
```

嚴格模式：超過速率的請求**立即拒絕**，連隊都不排。連發 10 個請求只有第 1 個會通過。

### `limit_req burst=5 nodelay`

```nginx
limit_req zone=demo burst=5 nodelay;
```

- `burst=5`：令牌桶容量擴大 5 個，允許暫時超量
- `nodelay`：超量請求**不排隊等候**，立即處理（不加延遲）
- 效果：瞬間可放行約 6 個請求（1 正常 + 5 burst），之後的才 429

### 超限狀態碼

```nginx
limit_req_status 429;
```

預設是 503，改成 429（Too Many Requests）符合 HTTP 語義，方便客戶端做 retry。

### 為何用 `proxy_pass` 而非 `return`

Nginx 各 phase 執行順序為：**rewrite → access → content**。

`return 200` 屬於 rewrite module，在 access phase **之前**就短路返回——`limit_req` 永遠不會被執行。  
`proxy_pass` 屬於 content phase，會完整走過 access phase，`limit_req` 才能正確攔截超量請求。

本 lab 在 8080 起一個 dummy server（直接 `return 200`）作為 backend，對外的 80 port 用 `proxy_pass http://127.0.0.1:8080` 確保限速生效。

---

## 為什麼 nodelay 重要

不加 `nodelay` 時，burst 請求會被**延遲排入隊列**以符合速率，導致前幾個請求回應很慢。
加了 `nodelay` 後，burst 槽位的請求**立即回應**，但槽位用完就直接 429——
對 API 場景更友善（寧可快速失敗也不要掛起連線）。

---

## 檔案結構

```
rate-limit/
├── nginx.conf          # Nginx 設定（limit_req_zone + 兩個 location）
├── docker-compose.yml  # 單容器，port 18082:80
├── run.sh              # 連發 10 個請求並驗證行為差異
└── README.md           # 本文件
```
