# 05 · 快取 proxy_cache:Nginx 當 CDN-lite 🔬

> 一句話:Nginx 的 `proxy_cache` 把它變成一個輕量 CDN——把後端回應存在本地磁碟/記憶體 key 表,下次同樣請求直接回傳不再回源。這章教你它的存儲結構、key 怎麼算、TTL 怎麼優先、以及三個最重要的可靠性機制:`use_stale`(後端掛了還能服務)、`cache_lock`(防快取擊穿)、micro-caching(1 秒快取擋瞬時洪峰)。

快取這件事聽起來只是「貼幾行指令」,但真正讓人踩坑的全在**黑盒裡**:key 算錯會把 A 用戶的資料回給 B 用戶(快取污染);沒有擊穿保護,快取過期的瞬間幾千個請求同時打垮後端;後端掛了但快取也過期了,服務就徹底癱瘓。這一章把這些黑盒逐一打開。

> ch04 的 `proxy_pass`/`upstream` 設定是本章的前提——`proxy_cache` 掛在反代設定上。`lab/proxy-cache/` 有可跑的 Docker 環境驗證 HIT/MISS/STALE 與 `cache_lock` 行為。

---

## 1. 🔬 `proxy_cache_path`:存儲區怎麼初始化

快取用前必須先在 `http` 層(或 `server`/`location` 外)宣告儲存區:

```nginx
http {
    proxy_cache_path /var/cache/nginx
        levels=1:2
        keys_zone=my_cache:10m
        max_size=5g
        inactive=60m
        use_temp_path=off;
}
```

**每個參數黑盒裡做什麼**:

| 參數 | 黑盒裡發生什麼 |
|---|---|
| `/var/cache/nginx` | 磁碟根目錄,Nginx 在這裡建立階層目錄放快取檔 |
| `levels=1:2` | 快取 key 雜湊後按「第 1 位 / 第 2–3 位」分出兩層子目錄,避免把幾百萬個檔都丟在同一個目錄(ext4 在單目錄檔案過多時查找性能劣化) |
| `keys_zone=my_cache:10m` | 在**共享記憶體**裡建一個叫 `my_cache`、大小 10 MB 的 zone;這裡只存 **key 的雜湊 + 元資料(URL/過期時間/命中數)**,快取**內容本體**在磁碟。10 MB ≈ 可存 80,000 個 key |
| `max_size=5g` | 磁碟上快取內容的上限;超過後 Nginx 的 cache manager 進程(master 管理的後台守護)用 LRU 淘汰最久未訪問的條目 |
| `inactive=60m` | 一個 key 若 60 分鐘內沒被任何請求訪問,就視為「冷 key」從磁碟淘汰——**不管它的 TTL 還剩多少**;這是「清除磁碟上的死條目」,而非 TTL 到期邏輯 |
| `use_temp_path=off` | 寫快取時直接落到目標目錄,避免先寫 temp 目錄再 rename 的跨分區開銷(生產必開) |

**記憶體 zone vs 磁碟**:keys_zone 在共享記憶體裡,存的是 key 映射表,所有 worker 共享(worker 間讀/寫都用它做協調)。磁碟存實際回應體。worker 處理命中請求時:先查記憶體 zone 得到磁碟路徑 → 讀磁碟回應體 → 回給客戶端;全在 Nginx 進程內,後端沒被碰。

---

## 2. 開啟快取:`location` 裡怎麼掛

```nginx
location /api/ {
    proxy_pass http://backend;
    proxy_cache my_cache;              # 指定用哪個 zone
    proxy_cache_valid 200 302 10m;     # 200/302 快取 10 分鐘
    proxy_cache_valid 404       1m;    # 404 快取 1 分鐘(防快取穿透)
    proxy_cache_valid any       1m;    # 其餘狀態碼快取 1 分鐘
    add_header X-Cache-Status $upstream_cache_status;  # 讓客戶端看見命中狀態
}
```

`proxy_cache` 指向 zone 名;多個 `location` 可以共用同一個 zone,也可以各用各的。

---

## 3. 🔬 Cache Key 怎麼算:設計不當的快取污染

快取的靈魂是 **key**——兩個請求 key 相同就命中同一份快取。Nginx 的默認 key 是:

```
$scheme$proxy_host$request_uri
```

也就是 `http://backend/api/users?id=1` 這種組合。**大多數時候這沒問題;但只要你的後端「同一 URL 對不同用戶/條件回不同內容」,默認 key 就會造成快取污染**。

### 3.1 幾個必須把條件納入 key 的場景

**場景 A:按語言/地區回傳不同內容**

後端看 `Accept-Language: zh-TW` 和 `Accept-Language: en-US` 回不同的頁面,但默認 key 裡沒有這個 header——第一個 zh-TW 請求的回應被快取了,下一個 en-US 請求 key 一樣,直接命中 zh-TW 的快取,英文用戶收到繁體中文。

```nginx
proxy_cache_key "$scheme$proxy_host$request_uri$http_accept_language";
```

**場景 B:登入用戶有個人化內容**

後端按 Cookie 裡的 `session_id` 回傳個人化資料,key 必須包含 session:

```nginx
proxy_cache_key "$scheme$proxy_host$request_uri$cookie_session_id";
```

**但這裡有個陷阱**:如果 `session_id` 每個用戶都不同,等於每個用戶都是 MISS、永遠不命中。個人化頁面根本**不應該快取**——應該用 `proxy_no_cache`/`proxy_cache_bypass` 跳過快取層,或只快取「公共部分」再在前端拼接個人化片段。

**場景 C:按壓縮偏好回不同 body**

如果後端根據 `Accept-Encoding` 回壓縮或未壓縮的內容,也要把它納入:

```nginx
proxy_cache_key "$scheme$proxy_host$request_uri$http_accept_encoding";
```

### 3.2 快取污染的根因與自查清單

**快取污染**發生的根因:key 相同但後端回傳內容不同——Nginx 只存了「第一個」拿到的回應,之後所有命中的請求都拿到那份錯誤的快取。

自查清單:你的後端是否按以下任一維度回不同內容?

- 不同 Cookie(登入態、A/B 實驗組)
- 不同請求頭(`Accept-Language`、`Accept-Encoding`、自訂 `X-Device-Type`)
- 不同客戶端 IP/地理位置

是 → 把該維度納入 key,或對這類請求 bypass 快取(用 `proxy_no_cache`/`proxy_cache_bypass`)。

```nginx
# 有登入 Cookie 的請求不快取
proxy_no_cache    $cookie_session_id;
proxy_cache_bypass $cookie_session_id;
```

`proxy_no_cache`(不存快取)+ `proxy_cache_bypass`(不讀快取)通常成對設,確保這類請求完全跳開快取層。

---

## 4. 🔬 TTL:Cache-Control、Expires 與 proxy_cache_valid 誰說了算

快取條目能活多久,由三層規則決定,**優先級從高到低**:

| 層 | 來源 | 例子 |
|---|---|---|
| **最高** | 後端回應的 `X-Accel-Expires` 頭 | Nginx 專屬覆蓋頭,後端顯式告訴 Nginx 快取多久(0 = 不快取) |
| **次高** | 後端回應的 `Cache-Control` / `Expires` | `Cache-Control: max-age=3600` → 快取 1 小時 |
| **最低/兜底** | Nginx 設定的 `proxy_cache_valid` | 當後端沒帶任何快取頭時,用這個 |

**黑盒細節**:

- 後端帶了 `Cache-Control: no-cache` 或 `no-store`:Nginx **默認尊重**,不快取——除非你加 `proxy_ignore_headers Cache-Control;` 強制忽略(慎用,因為這會違反後端的語義契約)。
- 後端帶 `Cache-Control: max-age=0` 或 `Expires` 是過去的時間:等效於「不快取」。
- `proxy_cache_valid 200 10m` 意思是:狀態碼 200 的回應在後端**沒帶任何快取頭**時,Nginx 主動快取 10 分鐘。
- `proxy_cache_valid any 1m` 是兜底——任何狀態碼、後端沒指定的都快取 1 分鐘;可以防止高頻 404 打穿後端(把 404 快取起來)。

**開發陷阱**:後端 API 忘記帶 `Cache-Control: no-cache`,Nginx 的 `proxy_cache_valid` 就主動快取它了——接口返回的資料在那 10 分鐘內不管怎麼更新後端,前端都看到舊數據。碰到「為什麼改了後端但客戶端沒更新」,第一眼先查 `X-Cache-Status` 是不是 HIT。

---

## 5. 🔬 `proxy_cache_use_stale`:後端掛了也能服務

```nginx
proxy_cache_use_stale error timeout updating http_502 http_503 http_504;
```

**黑盒裡發生什麼**:正常情況下,快取條目過期(TTL 到了)後 Nginx 必須回源取新的。但若回源時後端掛了(連接錯誤、超時、回 502/503/504),**Nginx 可以把過期但還存在磁碟的舊快取直接回給客戶端**——而不是返回一個冷冰冰的 502。

各條件的含義:

| 條件 | 觸發場景 |
|---|---|
| `error` | 回源時後端連線失敗(refused/reset) |
| `timeout` | 回源等待超過 `proxy_read_timeout` |
| `updating` | 另一個 worker 正在回源更新這個 key,本請求用舊的先回 |
| `http_502/503/504` | 後端回了這些錯誤狀態碼 |

**`updating` 是性能關鍵點**:假設快取剛過期,同一時刻 100 個請求同時進來,理想情況是「只有一個去回源,其餘 99 個等新快取建好再命中」。`updating` 讓那 99 個請求先拿舊快取返回,**不等待**,相當於零延遲響應——代價是這 99 個請求在回源完成前拿到的是過期數據,通常業務上可以接受。

**`proxy_cache_use_stale` 帶來的可用性提升**:後端可以短暫宕機(幾分鐘到幾小時)而用戶無感——只要快取還在磁碟上(`inactive` 時間沒到)就能服務。這讓 Nginx 快取層成了一道**可用性緩衝**。

```nginx
location /content/ {
    proxy_pass http://backend;
    proxy_cache my_cache;
    proxy_cache_valid 200 10m;
    proxy_cache_use_stale error timeout updating http_502 http_503 http_504;
    # 後端掛時最多用舊快取多久(額外延長 stale 時間)
    proxy_cache_lock on;
    proxy_cache_lock_timeout 5s;
}
```

---

## 6. 🔬 `proxy_cache_lock`:防快取擊穿

**快取擊穿**:一個高流量的 key 快取剛過期,下一個 TTL 週期開始的瞬間,有 N 個請求同時到達——它們都 MISS,都去回源,N 個並發請求同時打後端。如果這個 key 對應的後端計算很重,這 N 個並發可以直接壓垮後端。

```nginx
proxy_cache_lock on;           # 開啟擊穿保護
proxy_cache_lock_timeout 5s;   # 後續請求最多等 5s;超時後放行讓它也去回源
proxy_cache_lock_age 5s;       # 鎖最多持有 5s;防止回源卡住導致所有請求都等死
```

**黑盒裡發生什麼**:

```
時刻 T:key 過期,3 個並發請求同時到達
                    ┌─────────────────────────────────────────┐
  請求 A  ──MISS──► │ 拿到 lock,去回源                       │
  請求 B  ──MISS──► │ 未拿到 lock,等待(最多 lock_timeout 秒)│
  請求 C  ──MISS──► │ 未拿到 lock,等待                       │
                    └─────────────────────────────────────────┘
                         │  A 回源完成,把新響應寫進快取,釋放 lock
                         ▼
  請求 B  ──命中新快取──► 直接 HIT,返回
  請求 C  ──命中新快取──► 直接 HIT,返回
```

沒有 `proxy_cache_lock` 時:A/B/C 三個都去回源,後端看到 3 個並發;有 `proxy_cache_lock` 時:後端只看到 1 個回源請求。流量越大,保護效果越顯著——100 個並發 MISS 只讓 1 個打後端。

**`proxy_cache_lock_timeout` 的設計哲學**:不能讓後續請求永遠等下去——如果回源的那個請求本身也卡死了(比如後端 hang 住),`lock_timeout` 到了就放行,讓等待的請求各自嘗試回源。這是「降級為無保護模式」,比全部等死強。

> **面試高頻點:快取擊穿 Nginx 怎麼擋?**
> 答:`proxy_cache_lock on;`——key 過期後,同一時刻多個 MISS 請求裡只有「競到鎖」的一個去回源,其餘等待。等回源完成、新快取寫好後,等待的請求直接 HIT 新快取返回,後端只被打一次。搭配 `proxy_cache_use_stale updating` 可以讓等待的請求直接拿舊快取、不等待。

---

## 7. 🔬 Micro-caching:快取 1 秒擋瞬時洪峰

```nginx
location /dynamic/ {
    proxy_pass http://backend;
    proxy_cache my_cache;
    proxy_cache_valid 200 1s;   # TTL = 1 秒
    proxy_cache_use_stale updating;
    proxy_cache_lock on;
}
```

**為什麼 1 秒快取有用?** 直覺上 1 秒快取「太短了,有意義嗎?」——但算一下:

- 你的後端某個動態接口每秒被 1,000 個請求打。
- 加了 1 秒快取後:第 1 個請求 MISS 回源,接下來 999 個請求 HIT 快取。
- 後端從每秒 1,000 次計算 → 每秒最多 1 次計算。**壓力下降 99.9%**。
- 數據陳舊度:最多 1 秒。大多數業務場景(首頁資訊流、排行榜、商品庫存概覽)完全可以接受 1 秒延遲。

**micro-caching 的適用場景**:高流量、數據允許有 1–5 秒陳舊、後端計算重或 DB 慢查詢。典型場景:秒殺頁面商品狀態、社交網絡首頁時間線、新聞列表。

**micro-caching 的邊界**:
- 有登入態、個人化的接口:配合 `proxy_cache_bypass $cookie_session_id;` 讓有 session 的請求 bypass。
- 強一致性要求(支付確認、庫存扣減):不適用,老老實實讓每個請求打後端。

搭配 `proxy_cache_lock on`:1 秒 TTL 過期後,`cache_lock` 確保擊穿時只有 1 個請求回源,讓「微快取」在高並發下也穩健。

---

## 8. 🔬 `$upstream_cache_status`:調試快取命中的眼睛

Nginx 把每個請求的快取結果存在變數 `$upstream_cache_status`,值有以下幾種:

| 值 | 含義 |
|---|---|
| `HIT` | 命中快取,直接回傳,後端沒被碰 |
| `MISS` | 未命中,去回源,回源結果已寫入快取 |
| `EXPIRED` | 快取存在但 TTL 到期,去回源更新(更新後狀態變 HIT) |
| `STALE` | 快取過期且回源失敗(後端掛/超時),用舊快取回傳(`use_stale` 生效) |
| `UPDATING` | 快取過期,另一個 worker 正在回源更新,本請求用舊快取(`use_stale updating` 生效) |
| `BYPASS` | `proxy_cache_bypass` 條件命中,跳過快取直接回源,且不把回源結果存快取 |
| `REVALIDATED` | 客戶端帶 `If-Modified-Since`/`If-None-Match`,後端回 304,快取刷新 |

### 8.1 把 `$upstream_cache_status` 寫進日誌格式(生產必做)

```nginx
http {
    log_format cache_log '$remote_addr [$time_local] "$request" '
                         '$status $body_bytes_sent '
                         '"$upstream_cache_status" '  # ← 快取命中狀態
                         '$request_time $upstream_response_time';

    access_log /var/log/nginx/access.log cache_log;
}
```

日誌裡就能看到:
```
192.168.1.1 [25/Jun/2026:12:00:01 +0000] "GET /api/list HTTP/1.1" 200 1234 "HIT" 0.001 -
192.168.1.1 [25/Jun/2026:12:00:02 +0000] "GET /api/list HTTP/1.1" 200 1234 "MISS" 0.045 0.044
```

HIT 時 `$upstream_response_time` 是 `-`(後端沒被碰);MISS 時兩者都有值。對比 `$request_time`(Nginx 總耗時)和 `$upstream_response_time`(後端回源耗時)可以量化快取帶來的延遲收益。

### 8.2 把 `$upstream_cache_status` 加進回應頭(開發 / 調試必做)

```nginx
location /api/ {
    proxy_pass http://backend;
    proxy_cache my_cache;
    proxy_cache_valid 200 10m;
    add_header X-Cache-Status $upstream_cache_status always;  # ← 讓客戶端看見
}
```

這樣 `curl -I https://your-site/api/list` 就能看到:
```
X-Cache-Status: HIT
```

**注意**:`add_header` 的繼承陷阱(ch01 講過):如果這個 `location` 裡有 `add_header`,父層的安全頭要記得重抄或用 `include`。

### 8.3 快速診斷的幾個 pattern

```bash
# 統計各快取狀態的比例
grep '"HIT"' /var/log/nginx/access.log | wc -l
grep '"MISS"' /var/log/nginx/access.log | wc -l
grep '"STALE"' /var/log/nginx/access.log | wc -l

# 找出 STALE 多的端點(說明後端有問題但快取兜住了)
grep '"STALE"' /var/log/nginx/access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head
```

命中率低(大量 MISS):可能是 key 太細(URL query 太多變體)、TTL 太短、`inactive` 清得太快。

STALE 多:後端健康有問題,快取在兜住,要同步查後端的錯誤日誌。

---

## 9. Purge:主動清除快取

Nginx 開源版**沒有內建 purge 接口**。生產上常見三種做法:

**方式 1:nginx-cache-purge 模組(第三方,需編譯)**

```nginx
location ~ /purge(/.*) {
    allow 127.0.0.1;    # 只允許內部調用
    deny all;
    proxy_cache_purge my_cache "$scheme$proxy_host$1";
}
```

調用方式:`curl -X PURGE http://nginx/purge/api/list`。

**方式 2:帶版本號的 key(最簡單,不依賴第三方)**

不做主動 purge——部署時把 URL 改成 `/api/list?v=20260625`。舊 key 因為 `inactive` 時間到自然淘汰。

**方式 3:商業版 Nginx Plus**

內建 `proxy_cache_purge` 和 purge API,按需清除。

**選型建議**:小團隊 + 靜態/半靜態資源 → 版本號方案最輕;需要精確 purge(CMS 改內容立刻生效)→ 第三方模組或換 Varnish/CDN。

---

## 10. 完整設定範例:CDN-lite 生產版

```nginx
http {
    # 快取區宣告(http 層)
    proxy_cache_path /var/cache/nginx
        levels=1:2
        keys_zone=api_cache:20m
        max_size=10g
        inactive=24h
        use_temp_path=off;

    log_format cache_log '$remote_addr [$time_local] "$request" '
                         '$status "$upstream_cache_status" '
                         '$request_time/$upstream_response_time';

    server {
        listen 80;
        access_log /var/log/nginx/access.log cache_log;

        # 公共靜態資源:積極快取
        location /static/ {
            proxy_pass http://backend;
            proxy_cache      api_cache;
            proxy_cache_key  "$scheme$proxy_host$request_uri";
            proxy_cache_valid 200 1d;     # 靜態資源快取 1 天
            proxy_cache_valid 404 1m;
            proxy_cache_use_stale error timeout updating http_502 http_503 http_504;
            proxy_cache_lock on;
            proxy_cache_lock_timeout 5s;
            add_header X-Cache-Status $upstream_cache_status always;
        }

        # 動態 API:micro-caching(1 秒)
        location /api/feed {
            proxy_pass http://backend;
            proxy_cache      api_cache;
            proxy_cache_key  "$scheme$proxy_host$request_uri";
            proxy_cache_valid 200 1s;     # micro-cache:1 秒
            proxy_cache_use_stale error timeout updating;
            proxy_cache_lock on;
            # 有登入態的請求 bypass
            proxy_cache_bypass $cookie_session_id;
            proxy_no_cache     $cookie_session_id;
            add_header X-Cache-Status $upstream_cache_status always;
        }

        # 個人化接口:完全不快取
        location /api/user/ {
            proxy_pass http://backend;
            # 不掛 proxy_cache,每次回源
        }
    }
}
```

---

## 交叉引用

- **`proxy_pass`/`upstream` 反代基礎設定、超時三件套**:↪ `nginx/04-reverse-proxy-and-upstream.md`(本章的前置)。
- **`add_header` 繼承陷阱**(`X-Cache-Status` 加頭時要注意):↪ `nginx/01-config-model.md` 第 2.2 節。
- **觀察快取狀態時 `$request_time` vs `$upstream_response_time` 的差值含義**:↪ `nginx/10-observability-debugging.md`(可觀測章節,含生產 log_format 模板與 499/502/504 診斷)。
- **快取擊穿 / 穿透 / 雪崩的系統設計層討論**:↪ `system-design/01-韌性-依賴掛了怎麼不崩.md`(本章只講 Nginx 層的 `cache_lock`/`use_stale` 手段,系統級設計在那裡)。
- **引擎內幕(master-worker/epoll/連線池)**:↪ `gateway/01-reverse-proxy-engine.md`(本章不重寫)。
- **可跑的 HIT/MISS/STALE + 擊穿實測**:↪ `lab/proxy-cache/`(Docker Compose,backend.py 模擬慢回源,觀察 X-Cache-Status 各狀態)。

---

## 本章小結

- **`proxy_cache_path`**:磁碟目錄 + `keys_zone`(共享記憶體存 key 表)+ `max_size`(磁碟上限,LRU 淘汰)+ `inactive`(冷 key 清除);`levels=1:2` 避免單目錄過多檔案。
- **Cache key**:默認 `$scheme$proxy_host$request_uri`;後端按 header/cookie 回不同內容時要把這些維度加進 key,否則快取污染——把 A 用戶的回應餵給 B 用戶。個人化接口用 `proxy_cache_bypass`/`proxy_no_cache` 完全 bypass。
- **TTL 優先級**:`X-Accel-Expires`(最高)> `Cache-Control`/`Expires`(次高)> `proxy_cache_valid`(兜底);後端帶 `Cache-Control: no-cache` 時 Nginx 默認尊重不快取。
- **`proxy_cache_use_stale`**:後端掛了/超時/回 5xx 時,把過期舊快取回給客戶端,保住可用性。`updating` 讓等待回源的請求先拿舊快取不用等。
- **`proxy_cache_lock`**:防快取擊穿——key 過期後同一時刻多個 MISS 只放一個回源,其餘等新快取建好後 HIT;`lock_timeout` 防無限等待。
- **Micro-caching**:TTL 設 1 秒,對高流量動態接口可把後端壓力降 99%+,陳舊度僅 1 秒——業務上通常可接受。
- **`$upstream_cache_status`**:HIT/MISS/EXPIRED/STALE/UPDATING/BYPASS/REVALIDATED;寫進 `log_format` + 回應頭 `X-Cache-Status`,是快取調試的第一工具。
- **Purge**:開源版靠第三方模組或版本號 URL;精確 purge 有成本,小團隊優先考慮版本號方案。

---

## 章末問答(複習自檢,答案要點都在前面正文)

1. `proxy_cache_path` 的 `keys_zone` 和 `max_size` 分別控制什麼?為什麼 keys_zone 存在記憶體而不是磁碟?`inactive` 和 TTL 到期有什麼不同?

2. 你的後端 `/api/recommendations` 接口根據請求的 `Accept-Language` 頭回繁體中文或英文版本。默認的 `proxy_cache_key` 會造成什麼問題?要怎麼修?

3. **TTL 優先級**:後端回應帶了 `Cache-Control: max-age=3600`,而 Nginx 設定了 `proxy_cache_valid 200 10m;`。Nginx 實際快取多久?如果後端帶的是 `Cache-Control: no-cache` 呢?

4. `proxy_cache_use_stale` 的 `updating` 具體解決什麼問題?它的代價是什麼(用戶看到什麼)?

5. ⭐ **面試題:快取擊穿 Nginx 怎麼擋?** 請口述 `proxy_cache_lock` 在一個 key 過期後、100 個並發請求同時 MISS 的場景下做了什麼。

6. **Micro-caching 為什麼有用?** 計算:每秒 1,000 個請求打同一個動態接口,加 1 秒 `proxy_cache_valid` 後,理論上後端每秒最多收幾次回源請求?哪類接口不適合 micro-caching?

7. 列出 `$upstream_cache_status` 的至少 5 個值,並各說一句「它表示發生了什麼」。為什麼建議把它同時寫進 `log_format` 和回應頭 `X-Cache-Status`?

   <details><summary>對答案</summary>

   1. `keys_zone` 控制共享記憶體裡的 key 映射表大小(存 URL 雜湊+元資料,不存回應體);`max_size` 控制磁碟快取內容上限,超過後 LRU 淘汰。記憶體存 key 是因為 worker 每次命中都要查 key,必須極快(磁碟隨機讀太慢)。`inactive` 是「冷 key 清除」——多久沒被訪問就從磁碟刪掉,不管 TTL;TTL 到期是「快取可用性到期」——TTL 到了要回源刷新,但條目還在磁碟(可能 STALE 回傳)。

   2. 默認 key 只含 URL 路徑,不含 `Accept-Language`——第一個 zh-TW 請求的回應被快取,後續 en-US 請求命中同一份快取拿到中文版,造成污染。修法:`proxy_cache_key "$scheme$proxy_host$request_uri$http_accept_language";`。

   3. 後端帶 `Cache-Control: max-age=3600` → Nginx 尊重後端指示,快取 3600 秒(1 小時),`proxy_cache_valid 10m` 只是兜底,在後端有明確 Cache-Control 時不起作用。後端帶 `no-cache` → Nginx 默認不快取,除非你加 `proxy_ignore_headers Cache-Control;` 強制覆蓋。

   4. `updating` 解決「TTL 剛過期 + 回源還沒完成」期間等待的請求也要等很久的問題——這些請求直接拿舊(過期)快取返回,不等回源完成。代價是這批請求看到的是最多 TTL 時間陳舊的數據(不是最新的),直到回源完成後新請求才 HIT 新快取。

   5. `cache_lock on` 讓 100 個 MISS 請求競爭一把鎖。競到鎖的 1 個請求去回源;另外 99 個等待(最多 `lock_timeout` 秒)。回源完成後,新快取寫入,99 個等待的請求直接 HIT 新快取返回。後端只被打 1 次。

   6. 理論上每秒最多 1 次——第 1 個請求 MISS 回源,往後 999 個 HIT 快取(在同一秒內)。有登入態/個人化的接口、強一致性要求(支付/庫存扣減)的接口不適合 micro-caching。

   7. HIT(命中快取,後端未被碰)、MISS(未命中,去回源且寫快取)、EXPIRED(TTL 到期去回源更新)、STALE(快取過期但回源失敗,用舊的)、UPDATING(另一個 worker 正在回源,本請求用舊的)、BYPASS(條件命中 bypass,跳過快取)、REVALIDATED(條件請求後端回 304,快取刷新)。寫日誌方便離線統計命中率/STALE 率;加回應頭方便開發者 curl 實時看到每個請求的快取命運,排查「為什麼我的改動沒生效」。

   </details>
