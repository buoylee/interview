# 06 · Nginx 層流量控制:`limit_req` / `limit_conn` / `limit_rate`

> 一句話:這一章教你在 Nginx 層做「單機粗粒度防護」——用 `limit_req` 擋爆量請求、用 `limit_conn` 限並發連線、用 `limit_rate` 限頻寬;同時把最重要的邊界說清楚:Nginx 限流的計數是**每節點**的(同節點多 worker 透過共享記憶體共享同一份計數),但**跨節點不共享**,跨節點全域配額必須外移到 Redis / 網關層。

Nginx 自帶的 `ngx_http_limit_req_module` 和 `ngx_http_limit_conn_module` 在絕大多數發行版裡是默認編譯進去的,不用額外裝模組。它們能擋住暴力爬蟲、防止突發流量打穿後端,是「夠用、配簡單、不依賴外部組件」的第一道防線。理解它們**能做什麼、不能做什麼**,是面試和生產都必考的功課。

---

## 1. 概念基礎:漏桶

`limit_req` 的底層實現是**漏桶(Leaky Bucket)**——請求以任意速率進來,以固定速率流出(放行)。超過流出速率的請求要麼排隊等待,要麼被直接拒絕,取決於 `burst` 和 `nodelay` 的組合。

演算法本身的推導、漏桶 vs 令牌桶的比較、更多限流模式,見 ↪ `distribution/限流算法/`、`system-design/01-韌性-依賴掛了怎麼不崩.md`。本章只講 Nginx 的配置行為。

---

## 2. 🔬 `limit_req`:請求頻率限制(漏桶)

### 2.1 第一步:在 `http` 層定義 zone

```nginx
http {
    # key = 客戶端 IP 的二進制形式(比 $remote_addr 省記憶體)
    # zone 名稱 = req_zone,共享記憶體 10MB
    # rate = 每秒最多 10 個請求
    limit_req_zone $binary_remote_addr zone=req_zone:10m rate=10r/s;

    # 也可以按 API key 或 server 整體限
    # limit_req_zone $http_x_api_key   zone=api_zone:5m  rate=100r/s;
    # limit_req_zone $server_name      zone=srv_zone:1m  rate=1000r/s;
    ...
}
```

- `$binary_remote_addr`:把 IPv4 壓成 4 字節、IPv6 壓成 16 字節,比字串形式的 `$remote_addr` 約省 30% 記憶體。
- `zone=req_zone:10m`:zone 名稱 + 共享記憶體大小。10MB 能存多少 key?見「§5 zone 大小估算」。
- `rate=10r/s`:也可以寫 `rate=60r/m`(每分鐘 60 個)。

### 2.2 第二步:在 `server` / `location` 啟用

```nginx
server {
    # 最基本:超速即 429
    location /api/strict/ {
        limit_req zone=req_zone;
        limit_req_status 429;
        proxy_pass http://backend;
    }

    # 帶排隊緩衝:burst=20
    location /api/burst-queue/ {
        limit_req zone=req_zone burst=20;
        limit_req_status 429;
        proxy_pass http://backend;
    }

    # 帶突發 + 立即放行:burst=20 nodelay(推薦)
    location /api/burst-nodelay/ {
        limit_req zone=req_zone burst=20 nodelay;
        limit_req_status 429;
        proxy_pass http://backend;
    }
}
```

### 2.3 🔬 三種行為講透:無 burst / burst / burst+nodelay

這是面試最高頻的考點,也是線上最容易配錯的地方。以 `rate=10r/s`(即每 100ms 放行 1 個)為例,連續打進 30 個請求:

---

**行為一:無 burst(`limit_req zone=req_zone;`)**

- 漏桶沒有緩衝區。
- 第 1 個請求:即時放行(桶開始以 100ms/個的速率流出)。
- 第 2–30 個請求:如果不足 100ms 就到,超速,**立即拒絕**(返回 429)。
- **結果**:30 個請求裡只有 1 個放行,29 個被拒。
- **適用場景**:嚴格限速,每個超速請求都不許等,如防 DDoS 的入口。

```
時間軸:  ──┬──┬──┬──┬── ...
請求:       1  2  3  4  ...
放行:       ✓  ✗  ✗  ✗  (429)
```

---

**行為二:burst 無 nodelay(`limit_req zone=req_zone burst=20;`)**

- 漏桶加了一個「等待隊列」,最多能排 20 個請求。
- 第 1 個:即時放行。
- 第 2–21 個:超速但進入隊列**排隊延遲放行**——Nginx 按固定速率(每 100ms)從隊列裡取出一個處理;排在第 21 位的請求要等約 2 秒才輪到。
- 第 22–30 個:隊列已滿,**立即拒絕**。
- **結果**:21 個放行(帶不同延遲),9 個被拒。
- **副作用**:隊列裡的請求響應時間被人為拉長——可能幾百毫秒到幾秒,客戶端可能因自身超時先斷開(會引起 Nginx 側的 499)。通常**不推薦**這種配置給 API 服務。

```
時間軸:  ──┬──┬──┬──┬── ...
請求:       1  2  3  ...21  22  23
放行:       ✓  (延遲100ms) (延遲200ms)...(延遲2000ms) ✗  ✗
```

---

**行為三:burst + nodelay(`limit_req zone=req_zone burst=20 nodelay;`)**⭐ 推薦

- 漏桶的等待隊列仍有 20 個槽位,但 `nodelay` 的效果是:排進隊列的請求**不等待、立即放行**。
- 第 1–21 個:全部**立即放行**——但這 21 個「槽位」被佔用了,Nginx 按固定速率(每 100ms)釋放槽位。
- 第 22–30 個:在槽位被釋放前到達,**立即拒絕**。
- **結果**:21 個立即放行,9 個被拒。放行的總數和「行為二」一樣,但**沒有人為延遲**。
- 速率約束仍然存在:槽位釋放是按 rate 走的,所以約 2 秒後(20 個槽位全部釋放)才能再接受 20 個突發。
- **推薦用法**:API 服務允許短暫突發,但不想引入人為排隊延遲。

```
時間軸:  ──┬──┬──┬──┬── ...
請求:       1  2  3  ...21  22  23
放行:       ✓  ✓  ✓  ... ✓   ✗   ✗  (全部立即放行或拒絕,無延遲)
```

**三種行為對比表**:

| 配置 | 超速第 1–21 個 | 超速第 22–30 個 | 延遲 |
|---|---|---|---|
| 無 burst | 第 2 個起立即 429 | — | 無 |
| `burst=20` | 排隊(延遲放行) | 立即 429 | 有(最長 ~2s) |
| `burst=20 nodelay` | **立即放行** | 立即 429 | **無** |

> **面試一句話**:`nodelay` 不是「跳過速率限制」,而是「把排隊等待改成立即放行,但槽位佔用仍受 rate 控制、慢慢釋放」。總通過量和帶排隊的 burst 一樣,只是消除了人為延遲。

---

## 3. `limit_conn`:並發連線數限制

`limit_req` 限的是「每秒請求頻率」;`limit_conn` 限的是「同一 key 同時持有的並發連線數」。兩者不互斥,通常一起用。

```nginx
http {
    # 定義 zone:按 IP 計並發連線
    limit_conn_zone $binary_remote_addr zone=conn_zone:10m;

    server {
        location /download/ {
            limit_conn      conn_zone 10;      # 同一 IP 最多 10 條並發連線
            limit_conn_status 429;             # 默認 503,建議改 429
            proxy_pass http://backend;
        }
    }
}
```

- 默認狀態碼是 503;**建議改成 429**(`limit_conn_status 429;`),語義更準確(「太多請求」而非「服務不可用」)。
- 對於長連線(WebSocket、SSE、大檔下載),`limit_conn` 比 `limit_req` 更合適——前者限的是同時在線的連線數,後者限的是請求發起速率。
- 同一個 location 可以同時設 `limit_req` 和 `limit_conn`,兩條都過才放行。

---

## 4. `limit_rate` / `limit_rate_after`:單連線頻寬限速

用於限制單個連線的下行速率,常見於下載服務。

```nginx
location /files/ {
    # 前 10MB 不限速,之後限制到 512KB/s
    limit_rate_after 10m;
    limit_rate        512k;
    root /data/files;
}
```

- `limit_rate`:每條連線的最大下行速率(字節/秒)。
- `limit_rate_after`:前 N 字節不限速,超過後才開始限速。適合「允許快速完成小檔案、對大檔慢速限流」的場景。
- 也可以在 `proxy_pass` 場景下用,Nginx 會控制向客戶端發送數據的速率。
- 如果想動態設定速率(按用戶等級不同),可以用 `set $limit_rate 512k;` 在 `map` 或 `if` 里賦值(這是 `limit_rate` 少數可以安全放在 `if` 裡的情境之一)。

---

## 5. 狀態碼:`limit_req_status` 和 `limit_conn_status`

```nginx
http {
    limit_req_zone  $binary_remote_addr zone=rz:10m rate=10r/s;
    limit_conn_zone $binary_remote_addr zone=cz:10m;

    # 建議在 http 層統一設定,或在各 location 按需覆蓋
    limit_req_status  429;   # 默認 503
    limit_conn_status 429;   # 默認 503
}
```

- 默認兩者都返回 **503**。503 的語義是「服務暫不可用」,適合後端全掛的場景;因流量控制被拒的請求語義上是「太多請求」,用 **429 Too Many Requests** 更準確,也讓客戶端能區分「後端掛了」和「被限流了」。
- 可以搭配自訂錯誤頁:
  ```nginx
  error_page 429 /429.html;
  location = /429.html { root /usr/share/nginx/html; internal; }
  ```

---

## 6. 🔬 共享記憶體 zone 大小怎麼估

`limit_req_zone` 和 `limit_conn_zone` 都要指定共享記憶體大小(`zone=name:SIZE`)。這塊記憶體由**所有 worker 進程共享**,用來存放每個 key(如每個 IP)的計數器和時間戳。

**估算公式(經驗值)**:

- 每條 IPv4 key 記錄約佔 **64 字節**。
- 每條 IPv6 key 記錄約佔 **128 字節**。
- 1MB 可存約 **16,000 個 IPv4 key**(= 1,048,576 / 64)。
- `10m` ≈ 160,000 個 IPv4 key。

| zone 大小 | 約可存 IPv4 key 數 |
|---|---|
| 1m | ~16,000 |
| 5m | ~80,000 |
| **10m** | **~160,000** |
| 32m | ~500,000 |

**實踐建議**:

- 面向公網的 API 入口,10m 通常夠用(同一時刻活躍的不同 IP 不會超過 16 萬)。
- 超過 zone 容量時,Nginx 會用 LRU 淘汰最久未使用的條目,通常不會 crash,但可能讓部分 IP 的計數重置。`error_log` 裡會出現 `limiting requests, excess` 或 zone 滿的警告。
- 一個 zone 可以被多個 `location` 共用(共享同一個 rate 計數),也可以為不同路徑建不同 zone(獨立計數)。

---

## 7. 🔬 關鍵邊界:Nginx 限流是「每節點」計數(節點內 worker 共享、跨節點不共享)

這是最重要也最常被忽略的邊界,面試必考。

### 7.1 多 worker 下的行為

Nginx 的 `limit_req_zone` 和 `limit_conn_zone` 使用的是**進程間共享記憶體(shared memory)**——`zone:10m` 的那塊記憶體在**同一台機器**的所有 worker 之間是**共享**的。所以在**單節點多 worker** 的場景下,計數是全節點共享的,`rate=10r/s` 就是這台機器整體每秒 10 個請求。

> 一個常見的誤解是「多 worker 下速率會翻倍」——**不對**。共享記憶體讓計數器是全節點統一的。

### 7.2 多節點(集群)下的邊界:計數**不共享**

這是真正的限制所在。如果你有 3 台 Nginx 節點:

```
客戶端 ──► LB ──► Nginx-1  (各自獨立的 limit_req 計數)
              ──► Nginx-2
              ──► Nginx-3
```

每台 Nginx 各自在本機的共享記憶體裡獨立計數。如果你設 `rate=10r/s`:
- Nginx-1 允許最多 10 r/s
- Nginx-2 允許最多 10 r/s
- Nginx-3 允許最多 10 r/s
- **整個集群實際可通過最多 30 r/s**,而不是 10 r/s。

**結論**:Nginx `limit_req` 是**單機粗粒度防護**——它能擋住單個 IP 對同一台節點的爆量攻擊,但無法做到跨節點的精確全域配額。

### 7.3 需要跨節點全域配額時怎麼辦

把限流邏輯外移到能跨節點共享狀態的地方:

1. **Redis + Lua 原子腳本**:在 Nginx(OpenResty)的 `access_by_lua` 裡呼叫 Redis INCR/EXPIRE,實現原子計數,所有節點共用同一個 Redis。↪ 具體實作見 `redis-handson/13-rate-limiting/`。
2. **API 網關層**:把限流職責前移到 Envoy / APISIX / Kong 等網關,它們原生支援分散式限流(帶 Redis 後端)。↪ `gateway/05-traffic-control.md`。
3. **服務網格(mesh)**:如果用了 Istio/Envoy,可在 sidecar 層做精細限流並共享狀態。

**何時 Nginx 本地限流夠用**:
- 防止單個 IP 的**突發流量**打穿後端(這是最典型的用法)。
- 單節點部署或可接受「per-node 粗粒度」的場景。
- 作為第一道防線配合後端更精細的限流組合使用。

**何時必須外移**:
- 需要「全局每秒 N 個請求」的嚴格配額(如 API monetization)。
- 需要跨 endpoint / 跨服務統一計算配額。
- 需要動態調整速率(Nginx 改 rate 要 reload,帶代價)。

---

## 8. 完整配置範例(生產推薦寫法)

```nginx
http {
    # zone 定義(http 層)
    limit_req_zone  $binary_remote_addr zone=api_req:10m  rate=20r/s;
    limit_conn_zone $binary_remote_addr zone=api_conn:10m;

    # 統一狀態碼
    limit_req_status  429;
    limit_conn_status 429;

    server {
        listen 80;

        # API 路徑:頻率限制 + 連線數限制組合
        location /api/ {
            limit_req  zone=api_req burst=40 nodelay;  # 允許瞬時突發 40,立即放行
            limit_conn api_conn 20;                    # 同 IP 最多 20 條並發連線
            proxy_pass http://backend;
        }

        # 下載路徑:連線數限制 + 頻寬限速
        location /download/ {
            limit_conn  api_conn 5;       # 同 IP 最多 5 條並發下載
            limit_rate_after 1m;          # 前 1MB 不限速
            limit_rate       256k;        # 之後 256KB/s
            root /data/downloads;
        }

        # 健康檢查路徑:不限流
        location /health {
            return 200 "ok\n";
        }

        # 自訂 429 頁面
        error_page 429 /429.html;
        location = /429.html {
            root /usr/share/nginx/html;
            internal;
        }
    }
}
```

**面試高頻點補充**:

- **`limit_req_log_level`**:被限流的請求默認記在 `error_log` 的 warn 級別,可以改成 `info` 降低日誌噪音:`limit_req_log_level info;`
- **`limit_req_dry_run`**(Nginx 1.17.1+):只記日誌、不真的拒絕,用於上線前評估速率設定是否合適。

---

## 交叉引用

- **限流/熔斷演算法本身(漏桶/令牌桶/滑動視窗的推導與比較)**:↪ `distribution/限流算法/`、`system-design/01-韌性-依賴掛了怎麼不崩.md`(本章不重講演算法,只講 Nginx 設定行為)。
- **分散式限流 Redis/Lua 原子實作**:↪ `redis-handson/13-rate-limiting/`(OpenResty `access_by_lua` + INCR/EXPIRE 的具體程式碼)。
- **API 網關層分散式限流(Envoy/APISIX/Kong 的限流設計)**:↪ `gateway/05-traffic-control.md`(本章只講「何時需要外移」,不重複網關層設計)。
- **本章對應 lab**:`lab/rate-limit/` — 用 `burst` / `nodelay` 各種組合對 `/strict/`、`/burst/` 路徑連發 10 個請求,觀察 200 / 429 的分布(burst 路徑的 200 數明顯多於 strict)。

---

## 本章小結

- **`limit_req`(漏桶)**:用 `limit_req_zone` 在 `http` 層定義 key + rate;在 `location` 啟用並選擇行為:
  - **無 burst**:超速即 429,最嚴格。
  - **`burst=N`**:超速進隊列排隊延遲放行,最多 N 個排隊,超過才 429。
  - **`burst=N nodelay`(推薦)**:超速立即放行但消耗槽位,槽位耗盡才 429;無人為延遲。
- **`limit_conn`**:限同一 key 的並發連線數;適合長連線/下載場景。
- **`limit_rate` / `limit_rate_after`**:限單條連線的下行頻寬;`limit_rate_after` 允許前 N 字節全速。
- **狀態碼**:默認 503,**建議改 429**(`limit_req_status 429; limit_conn_status 429;`)。
- **zone 大小**:1MB ≈ 16,000 個 IPv4 key;10m 通常夠面向公網的入口。
- **最關鍵的邊界**:`limit_req` zone 是同一節點所有 worker **共享**的,但**跨節點不共享**——多節點集群下每台各自計數,Nginx 限流是**單機粗粒度防護**;跨節點全域配額必須外移到 Redis / 網關層。

---

## 章末問答(複習自檢,答案要點都在前面正文)

1. `limit_req_zone $binary_remote_addr zone=z:10m rate=10r/s;` 這行寫在哪個 context?`$binary_remote_addr` 相比 `$remote_addr` 省了什麼?`10m` 大約能存多少個 IPv4 key?

2. **(核心題)** 給定 `rate=2r/s; burst=5 nodelay;`,連續在 0.1 秒內打進 8 個請求,請說明:幾個被放行、幾個被拒、有沒有人為延遲?如果改成 `burst=5`(去掉 nodelay),行為有何不同?

3. 為什麼說「Nginx `limit_req` 是單機粗粒度防護」?如果你有 4 台 Nginx 節點,每台 `rate=50r/s`,整個集群實際能通過多少 r/s?要做跨節點全域配額,應該用什麼方案?

4. `limit_conn` 和 `limit_req` 分別限的是什麼?對一個大檔下載服務(連線持續幾十秒),哪個更合適?為什麼?

5. 默認限流狀態碼是 503,建議改成 429。這兩個狀態碼語義上的差別是什麼?為什麼 429 更準確?

6. 一個 location 裡同時設了 `limit_req zone=z burst=10 nodelay;` 和 `limit_conn cz 5;`,兩個條件的關係是「AND」還是「OR」?如果 IP 的並發連線已有 5 條,再發請求,哪個先觸發?

   <details><summary>對答案</summary>
   AND 關係——兩個都要滿足才放行。如果並發連線已達 5 條,`limit_conn` 先觸發返回 429(`limit_conn_status`),請求不會進入 `limit_req` 階段。
   </details>
