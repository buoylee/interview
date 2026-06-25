# 99 · 面試卡片:Nginx 高頻題 30 秒口述答法

> 每張卡的結構:**問題 → 30 秒口述答法 → 指回哪章深讀**。
>
> 用法:面試前「快速過」——先蓋住答法自己說一遍,對完再翻下一張。所有答法都和正文保持一致(正文才是知識主體,卡片只是快速復習介面)。

---

## 卡 1:location 匹配優先級怎麼口述?(五檔順序)

**問題**:Nginx 的 `location` 有好幾種寫法,當多條 `location` 都能匹配同一個 URI 時,到底哪條贏?

**30 秒口述答法**:

「先掃所有『前綴型』location。**精確 `=` 命中就立即用**——最高優先、立即停。否則記住『最長前綴』——如果它帶 `^~`,直接用、**不再比正則**。否則進正則階段:**按設定檔出現順序**,`~`(區分大小寫)和 `~*`(不分大小寫)逐個試、**第一個命中的正則勝出**。都沒有正則命中,才回退到剛才那個最長前綴。

口訣:**`=` 精確命中即停 > `^~` 最長前綴命中即停(短路正則) > 正則按出現序第一個即停 > 最長前綴回退。**

最容易坑人的兩格:一、`^~ /static/` 命中後圖片正則 `~* \.(jpg|png)$` **沒有機會**跑;二、`= /login` 精確匹配要求完全相等,`/login/` 尾斜線多了就掉到兜底。」

**深讀** → [`01-config-model.md`](01-config-model.md) §3「location 匹配優先級」

---

## 卡 2:proxy_pass 帶不帶尾斜線,後端收到的路徑有何不同?

**問題**:`location /p/ { proxy_pass http://b; }` 和 `location /p/ { proxy_pass http://b/; }` 有什麼差別?

**30 秒口述答法**:

「看 `proxy_pass` 後面**有沒有路徑部分**(含尾斜線)。

- **沒有路徑(只有 host)**:`proxy_pass http://b;` → 整個原始 URI **原樣**轉給後端,`/p/` 前綴**保留**。客戶端請求 `/p/api` → 後端收到 `/p/api`。
- **有路徑(哪怕只是 `/`)**:`proxy_pass http://b/;` → Nginx 砍掉 `location` 前綴 `/p/` 後的剩餘部分,接到那個路徑後面,前綴**被替換**。客戶端請求 `/p/api` → 後端收到 `/api`。

最容易出事的是『路徑不帶尾斜線』:`proxy_pass http://b/app;`(無尾斜線)+ `location /p/`(有尾斜線),剩餘 `api` 會直接黏在 `app` 後變成 `/appapi`——路徑錯位。成對原則:location 帶尾斜線、proxy_pass 的路徑也帶尾斜線;想原樣轉則兩邊都不帶路徑。」

**深讀** → [`04-reverse-proxy-and-upstream.md`](04-reverse-proxy-and-upstream.md) §1「proxy_pass 的尾斜線陷阱」

---

## 卡 3:X-Forwarded-For 能不能信?

**問題**:後端從 `X-Forwarded-For` 取客戶端 IP 做限流/白名單,安全嗎?

**30 秒口述答法**:

「不能無條件信。`X-Forwarded-For` 是**普通請求頭,客戶端可以隨手偽造**。攻擊者直接帶 `X-Forwarded-For: 10.0.0.1`,後端如果直接取最左邊的值當真實 IP,就被偽裝成任意 IP 繞過白名單。

根本原因:你只能信**你自己控制的那幾跳代理**追加的部分,客戶端那截不可信。

解法:用 **`realip` 模組**(`ngx_http_realip_module`)。設 `set_real_ip_from` 宣告可信代理網段(比如你的雲 LB 網段),`real_ip_recursive on` 讓 Nginx 從 XFF 右邊往左剝掉可信代理 IP,停在第一個『不在可信清單』的 IP——那才是真實客戶端。直接面向公網的那層尤其不能照單全收。」

**深讀** → [`04-reverse-proxy-and-upstream.md`](04-reverse-proxy-and-upstream.md) §2.3「X-Forwarded-For 偽造防範」

---

## 卡 4:limit_req 的 burst 和 nodelay 有什麼行為差異?

**問題**:`limit_req zone=z burst=20;` 和 `limit_req zone=z burst=20 nodelay;` 行為分別是什麼?

**30 秒口述答法**:

「以 `rate=10r/s`(每 100ms 一個)為例,連續打進 30 個請求:

- **無 burst**:第 1 個放行,第 2–30 個超速**立即 429**。
- **burst=20(無 nodelay)**:第 1 個立即放行;第 2–21 個超速進**等待隊列**,Nginx 按固定速率(每 100ms)從隊列裡取一個——排到第 21 位的請求要等約 2 秒才輪到。第 22–30 個隊列已滿,立即 429。放行了 21 個,但**有人為排隊延遲(最長約 2 秒)**。
- **burst=20 nodelay(推薦)**:第 1–21 個**立即放行**,槽位被消耗;按 rate 慢慢釋放槽位,在釋放完前到達的第 22–30 個**立即 429**。放行總數和帶排隊的 burst 一樣,但**沒有人為延遲**。

口訣:nodelay 不是跳過速率限制,是把『排隊延遲放行』改成『立即放行但消耗槽位』。推薦 API 服務用 `burst+nodelay`。」

**深讀** → [`06-rate-limiting.md`](06-rate-limiting.md) §2.3「三種行為講透」

---

## 卡 5:nginx -s reload 為什麼不丟連線?

**問題**:`nginx -s reload` 改設定生效時,為什麼在途請求不會中斷、新請求也不會漏接?

**30 秒口述答法**:

「`reload` 給 master 發 `HUP`。master 先**校驗新設定**,OK 才用新設定 fork 新 worker,然後通知舊 worker 優雅退出。不丟連線靠兩件事:

**第一:listen socket 由 master 持有、reload 全程不關閉。** 監聽 socket 是 master 持有的,fork 給 worker 用。reload 時 master 把同一個 fd 再分享給新 worker,所以監聽埠一刻不空檔——新請求總有 worker 在 accept,不存在『埠短暫關閉被內核拒掉』。

**第二:舊 worker 不是被砍死,而是停止接新連線、把在途請求處理完才退(graceful)。** 舊 worker 把自己從事件迴圈裡摘掉、不再 accept,但手上正在處理的請求繼續跑到完成。

兩邊不斷:新連線歸新 worker、在途請求歸舊 worker。設定有錯時新 worker 起不來、舊 worker 繼續服務——reload 是安全的(成功才換、失敗維持原狀)。」

**深讀** → [`08-operations-zero-downtime.md`](08-operations-zero-downtime.md) §2「reload 為什麼平滑」

---

## 卡 6:怎麼不停機升級 Nginx 二進制?(USR2 → WINCH → QUIT)

**問題**:生產上 Nginx 要升版本,但不能停機。怎麼做?

**30 秒口述答法**:

「三步:

**1. USR2(給舊 master)**:舊 master 把 pid 檔改名為 `.oldbin`,fork 出**新 master + 新 worker**(載入新二進制)。新舊**共用同一個 listen socket**,同時服務同一個埠的流量。

**2. 觀察**(新舊並存):確認新版本回應正常、error_log 無異常。這段時間你握著完整的回滾能力——舊 master 完好。

**3a. WINCH(給舊 master)**:優雅停掉舊 worker(在途處理完才退),但**保留舊 master 待命**。留著回滾路徑:若有問題,給舊 master 發 `HUP` 把舊 worker 拉回來、再 `QUIT` 掉新 master。

**3b. QUIT(給舊 master,徹底確認沒問題後)**:舊 master 優雅退出,升級完成。

關鍵:先 WINCH 留後路,等確認再 QUIT 斷後路——一旦舊 master 被 QUIT,便捷回滾就沒了。」

**深讀** → [`08-operations-zero-downtime.md`](08-operations-zero-downtime.md) §3「熱升級二進制」

---

## 卡 7:502 vs 504 vs 499 怎麼分?

**問題**:線上出現 502、504、499,各是什麼引起的?怎麼快速區分?

**30 秒口述答法**:

「**三個碼的成因**:

- **502 Bad Gateway**:後端**連不上或拿到垃圾**——後端進程掛了/埠不通被 `Connection refused`、後端回了非法 HTTP 回應(頭格式錯/提前關連線)。日誌指紋:error_log 出現 `connect() failed`/`prematurely closed connection`/`upstream sent invalid header`。
- **504 Gateway Timeout**:後端**連上了但回得太慢**——後端在 `proxy_read_timeout` 內沒回完(慢 SQL/下游卡住)。日誌指紋:error_log 出現 `upstream timed out ... while reading response header`。
- **499**:不是後端的錯——**客戶端先斷開**了(客戶端自己超時比後端短、用戶取消)。常因後端慢到客戶端等不及。

**關鍵區分**:
- 502 vs 504:`$upstream_connect_time` 有值(連上了)→ 504;無值/連接失敗 → 502。
- 499 vs 504:都是後端慢,差在**誰先放棄**——客戶端先放棄 → 499;Nginx 的 `proxy_read_timeout` 先到期(客戶端還在等)→ 504。
- 日誌看 `$upstream_status` 為空(`-`)+ `$status` 是 5xx → Nginx 沒從後端拿到合法回應(502/504)。」

**深讀** → [`10-observability-debugging.md`](10-observability-debugging.md) §2「狀態碼診斷」/ [`04-reverse-proxy-and-upstream.md`](04-reverse-proxy-and-upstream.md) §4「超時三件套」

---

## 卡 8:Nginx 為什麼快?(master-worker + epoll)

**問題**:Nginx 為什麼能以少量進程服務大量並發連線?

**30 秒口述答法**:

「兩個設計結合:

**master-worker 架構**:一個 master 進程負責管理生命週期(接收訊號、fork/回收 worker),多個 worker 進程負責實際服務連線。worker 數通常等於 CPU 核數,充分利用多核且沒有進程切換開銷。

**epoll 事件驅動(I/O 多路複用)**:每個 worker 不是「一連線一執行緒」,而是用 Linux `epoll` 系統呼叫同時監聽海量連線的事件——只有『有事做』(有數據到/可寫/有新連線)的 fd 才被喚醒處理。大量空閒的 keepalive 連線靜靜等著,**不佔執行緒/進程**。

所以:傳統 Apache(一請求一執行緒)1000 並發 = 1000 個執行緒、上下文切換劇烈;Nginx 1000 並發 = 幾個 worker 各自事件迴圈,性能線性擴展。」

引擎機制深度在 ↪ [`gateway/01-reverse-proxy-engine.md`](../gateway/01-reverse-proxy-engine.md);本 track 的落地調參在 [`09-performance-tuning.md`](09-performance-tuning.md)。

**深讀** → [`gateway/01-reverse-proxy-engine.md`](../gateway/01-reverse-proxy-engine.md) + [`00-decision-map.md`](00-decision-map.md)

---

## 卡 9:什麼時候該從 Nginx 畢業?

**問題**:面試官問「什麼情況下你會把 Nginx 換成別的東西?」

**30 秒口述答法**:

「Nginx 的根本模型是『靜態設定檔 + reload 才生效』,穩定場景是優點,但有四個硬邊界:

1. **需要動態路由/限流不重啟生效**:路由規則每天改多次、後端拓撲頻繁變動要秒級生效 → 換 **Envoy**(xDS API push)或 **APISIX**(管理 API)。
2. **需要服務發現無縫整合**:容器環境後端 IP 頻繁變、不想配膠水層(consul-template/ingress) → 換 **Envoy/APISIX**。
3. **需要開箱即用插件**:鑑權/熔斷/請求轉換不想自己寫 Lua → 換 **APISIX/Kong**。
4. **需要精細可觀測**:OTel trace 要在網關層零配置注入 → 換 **Envoy**。

如果只是想省 TLS 運維(certbot 太麻煩)→ 換 **Caddy** 就夠了,不用動全棧。沒到邊界就別換——遷移有成本。」

**深讀** → [`12-selection-and-graduation.md`](12-selection-and-graduation.md) §2「何時該從 Nginx 畢業」

---

## ⭐ 白板大題:用 Nginx 搭一個生產級接入層

**題目**:「請你設計並口述,如何用 Nginx 搭建一個生產級的反向代理 + 負載均衡 + 快取 + 限流 + TLS 接入層?給出關鍵設定骨架和口述順序。」

**答題骨架(7 段串接,口述這個順序即可)**:

---

### 第一段:upstream 定義後端池(ch04)

```nginx
upstream app {
    least_conn;                                            # 最少連線,避免慢請求堆積
    server 10.0.0.11:8080 max_fails=3 fail_timeout=10s;
    server 10.0.0.12:8080 max_fails=3 fail_timeout=10s;
    keepalive 32;                                          # 每 worker 對後端保留長連線池
}
```

**口述**:「先定 upstream 池:least_conn 防慢請求堆積;被動健康檢查用 max_fails + fail_timeout;keepalive 復用連線省握手成本(需配 proxy_http_version 1.1 + 清 Connection 頭)。」

---

### 第二段:TLS 終止(ch07)

```nginx
server {
    listen 443 ssl;
    server_name api.example.com;

    ssl_certificate     /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_tickets off;
    ssl_stapling on;
    ssl_stapling_verify on;
    add_header Strict-Transport-Security "max-age=63072000" always;
}
```

**口述**:「邊緣做 TLS 終止:憑證路徑指向 certbot/acme.sh 自動管理的位置;session cache 省重複握手;OCSP stapling 省客戶端一次 CA 查詢往返;HSTS 加 `always` 確保錯誤頁也帶安全頭(注意 add_header 繼承陷阱——ch01)。HTTP 統一 301 跳 HTTPS。」

---

### 第三段:realip + 必要 proxy header(ch04)

```nginx
# 宣告可信代理網段(上游雲 LB)
set_real_ip_from 10.0.0.0/8;
real_ip_header   X-Forwarded-For;
real_ip_recursive on;
```

**口述**:「realip 模組框住可信邊界,只採信來自可信代理那幾跳的 XFF——防止客戶端偽造 IP 繞過限流/白名單。location 裡再透傳 Host/$real_ip/X-Forwarded-Proto 給後端。」

---

### 第四段:限流閘門(ch06)

```nginx
http {
    limit_req_zone  $binary_remote_addr zone=api:10m rate=20r/s;
    limit_conn_zone $binary_remote_addr zone=api_conn:10m;
    limit_req_status  429;
    limit_conn_status 429;
}
```

在 location 內:

```nginx
limit_req  zone=api burst=40 nodelay;   # 允許短暫突發,立即放行,無人為延遲
limit_conn api_conn 20;                 # 同 IP 並發連線上限
```

**口述**:「限流放在反代前:burst+nodelay 吸收瞬時突發同時不引入排隊延遲;狀態碼改 429 讓客戶端/監控能區分限流和服務不可用;zone 是節點內 worker 共享的——跨節點全域配額需外移 Redis/網關層(ch06 的邊界)。」

---

### 第五段:快取層(ch05)

```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=api_cache:10m
                 max_size=1g inactive=10m use_temp_path=off;

location /api/public/ {
    proxy_cache            api_cache;
    proxy_cache_valid      200 5m;
    proxy_cache_lock       on;               # 防快取擊穿
    proxy_cache_use_stale  error timeout updating;  # 後端掛了先回舊快取
    add_header X-Cache-Status $upstream_cache_status always;
    proxy_pass http://app;
}
```

**口述**:「公開只讀介面才開快取;cache_lock 防同一 key 並發 miss 同時打後端;use_stale 讓後端掛了時先回舊資料提升可用性;把 cache_status 寫進回應頭和日誌,方便即時觀察命中率。」

---

### 第六段:反代核心超時 + buffer(ch04)

```nginx
location /api/ {
    proxy_pass http://app;

    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_http_version 1.1;
    proxy_set_header   Connection "";

    proxy_connect_timeout 5s;       # 連後端:幾秒連不上就 502
    proxy_read_timeout    60s;      # 等後端回:超時就 504
    proxy_send_timeout    60s;
    proxy_buffering on;             # 快速吸收後端回應,把後端早點放掉
}
```

**口述**:「超時三件套都要設:connect 幾秒連不上就快速失敗;read 等後端的間隔上限(注意是兩次 I/O 間的靜默,不是總耗時);buffering on 讓 Nginx 當海綿吸走後端回應,保護後端不被慢客戶端拖垮。」

---

### 第七段:可觀測 + 零停機運維(ch10/ch08)

```nginx
log_format main escape=json
    '{"time":"$time_iso8601","status":$status,'
    '"request_time":$request_time,'
    '"upstream_response_time":"$upstream_response_time",'
    '"upstream_status":"$upstream_status",'
    '"upstream_addr":"$upstream_addr",'
    '"cache":"$upstream_cache_status"}';
access_log /var/log/nginx/access.log main;

location /nginx_status {
    stub_status;
    allow 127.0.0.1;
    deny all;
}
```

**口述**:「JSON log_format 帶 upstream_* 系列——出事時 `$request_time - $upstream_response_time` 就能定位慢在 Nginx 側還是後端側;stub_status 接 Prometheus exporter 做 Active/accepts>handled 告警。改設定前 `nginx -t` 校驗、先單台 reload 觀察無 5xx 再全量推(灰度 reload)。版本升級用 USR2→WINCH→QUIT 全程零停機。」

---

**面試收口一句話**:「這七段依次是:upstream 池 → TLS 終止 → IP 信任邊界 → 限流閘門 → 快取層 → 反代超時/buffer → 可觀測+運維——每一段都在 ch04/05/06/07/08/10 有詳細展開。」

---

## 快速索引:卡片 → 章號

| 卡 | 核心考點 | 深讀章 |
|---|---|---|
| 1 | location 匹配五檔優先級 | ch01 |
| 2 | proxy_pass 尾斜線路徑差異 | ch04 |
| 3 | X-Forwarded-For 偽造防範 | ch04 |
| 4 | limit_req burst/nodelay 三種行為 | ch06 |
| 5 | reload 為何不丟連線(兩個關鍵) | ch08 |
| 6 | 不停機升級二進制(USR2→WINCH→QUIT) | ch08 |
| 7 | 502/504/499 成因區分 | ch10/ch04 |
| 8 | Nginx 為何快(master-worker+epoll) | gateway/01, ch09 |
| 9 | 何時從 Nginx 畢業(四個邊界) | ch12 |
| ⭐ | 白板大題:生產級接入層骨架 | ch04/05/06/07/08/10 |
