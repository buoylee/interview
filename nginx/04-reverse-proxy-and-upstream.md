# 04 · 反向代理與 upstream:proxy_pass / header / 超時 / 連線池 🔬⭐

> 一句話:這是 Nginx 最常用、也最容易踩坑的身份。`proxy_pass` 一個尾斜線寫錯就 404、`Host` 頭忘了設後端就拿不到對的域名、`X-Forwarded-For` 照單全收就被偽造繞過 IP 白名單、三個超時分不清楚就把「後端慢」誤判成「後端掛」。這一章把這些**日常重災區**逐個講死,並把它們串成一份能直接抄上生產的反代設定。

把請求收進來、轉給後端、再把回應送出去——聽起來簡單,但「轉給後端」這一步藏著一堆**默認值會害你**的細節:`proxy_pass` 的路徑改寫規則反直覺、預設傳給後端的 `Host` 是錯的、緩衝開關決定慢客戶端會不會拖住你的後端。本章假設你已經能讀懂一個 `location` 區塊(ch01),在它之上把「反向代理」這門手藝講透。

> 引擎為什麼快(master-worker、epoll、**upstream 連線池為什麼省握手**、L4 vs L7)不在這裡——那是 `gateway/01-reverse-proxy-engine.md` 的事。本章只教「怎麼**用設定**把這台引擎配成一個可靠的反向代理」。負載均衡**演算法本身**(輪詢/最少連線/一致性哈希/P2C 的原理)也不在這裡,在 `system-design/05-服務治理設施.md`;本章只講 Nginx `upstream` 怎麼**寫**。

---

## 1. 🔬⭐ `proxy_pass` 的尾斜線陷阱:一個 `/` 決定後端收到什麼路徑

這是 Nginx 反代**最高頻的線上事故**,也是面試最愛問的一題。規則一句話講不清,但只要記住一條判據,所有情況都能推出來:

> **`proxy_pass` 的 URL 帶不帶「路徑部分」(含尾斜線 `/`),決定 Nginx 是「替換」還是「拼接」`location` 前綴。**
>
> - **`proxy_pass` 後面只有 host(沒有路徑,連尾斜線都沒有)** → Nginx 把**整個原始 URI** 原樣接到後端。
> - **`proxy_pass` 後面有路徑(哪怕只是一個 `/`)** → Nginx 把請求 URI 中**匹配掉 `location` 前綴後剩下的部分**,接到這個路徑後面。也就是「`location` 前綴被替換成 `proxy_pass` 的路徑」。

換成操作層面的口訣:**`proxy_pass` 帶 `/`(或任何路徑)= 砍掉 location 前綴再拼;不帶 = 原封不動轉。**

### 1.1 組合對照表(背這張)

設定 `location /p/ { proxy_pass <X>; }`,客戶端請求 `GET /p/api/users?id=1`:

| `proxy_pass` 寫法 | 帶路徑? | 後端實際收到的路徑 | 怎麼算出來的 |
|---|---|---|---|
| `proxy_pass http://b;` | ✗ 只有 host | `/p/api/users?id=1` | 無路徑 → **整個原始 URI 原樣轉**,`/p/` 也保留 |
| `proxy_pass http://b/;` | ✓ 路徑是 `/` | `/api/users?id=1` | 砍掉 location 前綴 `/p/`,剩 `api/users`,接到 `/` 後 → `/api/users` |
| `proxy_pass http://b/app/;` | ✓ 路徑是 `/app/` | `/app/api/users?id=1` | 砍掉 `/p/`,剩 `api/users`,接到 `/app/` 後 → `/app/api/users` |
| `proxy_pass http://b/app;` | ✓ 路徑是 `/app` | `/appapi/users?id=1` ⚠️ | 砍掉 `/p/`,剩 `api/users`,接到 `/app`(無尾斜線)後 → `/appapi/users`(**黏一起了!**) |

**這張表裡最會出事的兩格**:

- **第 1 格 vs 第 2 格**:差一個尾斜線,後端收到的路徑前面**有沒有 `/p/`** 完全不同。如果後端是個只認 `/api/users` 的服務,你用了第 1 格(不帶斜線),後端會收到 `/p/api/users` 而 404,而且你盯著 Nginx 設定看半天都覺得「沒問題啊」。
- **第 4 格**:`proxy_pass http://b/app;`(路徑不帶尾斜線)+ `location /p/`(帶尾斜線),剩餘部分 `api/users` 直接黏在 `app` 後變成 `appapi`——典型的「少寫一個斜線就路徑錯位」,和 ch01 `alias` 的尾斜線陷阱是同一類病。

### 1.2 三條附帶規則(踩坑時想得起來)

1. **`proxy_pass` 帶變數或正則 `location`,就不能用「替換」模式**。例如 `proxy_pass http://$backend;`(host 來自變數)或 `location ~ ^/p/(.*)`(正則 location),Nginx **無法自動算出要砍掉的前綴**,這時要嘛 `proxy_pass http://b;`(整段轉),要嘛自己用 `rewrite` 把路徑改好再 `proxy_pass`(細節 ↪ ch02)。
2. **`proxy_pass` 帶 `upstream` 名(`proxy_pass http://my_upstream;`)時不能帶路徑**——`upstream` 區塊只定義後端伺服器組,不是 URL,後面接 `/路徑` 是非法的。要改路徑請配 `rewrite`。
3. **日常建議**:`location` 前綴和 `proxy_pass` 路徑的尾斜線**成對寫**(`location /p/` 配 `proxy_pass http://b/;`),想「原樣轉發整個路徑」就**兩邊都不要路徑**(`location /p/` 配 `proxy_pass http://b;`)。別寫第 4 格那種一邊有一邊沒有的組合。

> ⭐ **白板答法**(被問「`proxy_pass` 帶不帶斜線差在哪」):
> 「看 `proxy_pass` 後面**有沒有路徑**。沒有路徑(只有 host)→ 整個原始 URI 原樣轉給後端,`location` 前綴**保留**。有路徑(哪怕只是一個 `/`)→ Nginx 把 URI 砍掉 `location` 前綴後的剩餘部分,接到那個路徑後面,等於**前綴被替換**。所以 `location /p/` 下,`proxy_pass http://b;` 後端收到 `/p/...`,`proxy_pass http://b/;` 後端收到 `/...`。尾斜線不對齊還會把路徑黏一起。正則或變數 `location` 不能用替換模式,得自己 `rewrite`。」

---

## 2. 🔬 必設的 `proxy_set_header`:不設,後端拿到的資訊全是錯的

Nginx 一旦做反向代理,後端看到的「客戶端」其實是 **Nginx 自己**——TCP 連線是 Nginx 發起的,源 IP 是 Nginx 的,後端對真實客戶端**一無所知**,除非你主動把資訊透過 header 傳過去。更糟的是,有幾個 header 的**默認值是錯的**,不覆蓋就會出 bug。

### 2.1 `Host`:默認值會丟掉客戶端原本的域名

這是最隱蔽的一個默認坑:

> **`proxy_pass http://backend;` 時,Nginx 默認傳給後端的 `Host` 頭是 `$proxy_host`(= `proxy_pass` 裡的那個 host,例如 `backend`),而不是客戶端原本請求的域名。**

後果:如果你的後端靠 `Host` 來做**虛擬主機路由、生成絕對 URL、或多租戶分流**,它會收到 `Host: backend`(或上游的內網名),而不是客戶端打的 `api.example.com`,於是路由到錯的站點、回傳錯的連結。

**對策:明確設成 `$host`**(ch01 講過,`$host` 比 `$http_host` 穩——做了小寫正規化、缺 `Host` 時用 `server_name` 兜底):

```nginx
proxy_set_header Host $host;   # 把客戶端原本的域名透傳給後端
```

### 2.2 `X-Forwarded-For` / `X-Real-IP` / `X-Forwarded-Proto`:讓後端知道「真實客戶端是誰、走的是不是 HTTPS」

後端看到的源 IP 是 Nginx 的,所以**真實客戶端 IP** 要靠 header 傳遞:

```nginx
proxy_set_header X-Real-IP        $remote_addr;                    # 直連 Nginx 的那個 IP(單一值)
proxy_set_header X-Forwarded-For  $proxy_add_x_forwarded_for;      # 經過的代理鏈(逗號分隔,追加)
proxy_set_header X-Forwarded-Proto $scheme;                        # 客戶端走的是 http 還是 https
```

| header | 傳什麼 | 後端拿來幹嘛 |
|---|---|---|
| **`X-Real-IP`** | 直連 Nginx 的那一跳 IP(`$remote_addr`,單一值) | 記日誌、做 IP 限制(取一個確定值最方便) |
| **`X-Forwarded-For`** | 整條代理鏈的 IP(`$proxy_add_x_forwarded_for` = 客戶端傳來的 XFF + 追加 `$remote_addr`) | 還原客戶端真實 IP(取最左、但見下節偽造防範) |
| **`X-Forwarded-Proto`** | 客戶端到 Nginx 那一段的協議(`$scheme` = `http`/`https`) | 後端判斷「外部是不是 HTTPS」,避免在 TLS 終止後生成 `http://` 連結、或誤判要不要 redirect |

`$proxy_add_x_forwarded_for` 的行為:**如果客戶端的請求裡已經有 `X-Forwarded-For`,它會在後面追加 `, $remote_addr`;沒有就直接是 `$remote_addr`。** 這正是它危險的地方——它**信任了客戶端傳來的 XFF**。

### 2.3 🔬 `X-Forwarded-For` 偽造防範:別信客戶端傳進來的那一截

面試高頻陷阱題:**「`X-Forwarded-For` 能信嗎?」答案是:不能無條件信。**

問題出在:`X-Forwarded-For` 只是一個**普通請求頭,客戶端可以隨手偽造**。攻擊者直接發:

```
GET /admin HTTP/1.1
Host: api.example.com
X-Forwarded-For: 10.0.0.1     ← 偽造成內網 IP
```

如果你的後端「取 `X-Forwarded-For` 最左邊那個值當真實 IP」來做 **IP 白名單 / 限流 / 地理判斷**,攻擊者就能把自己**偽裝成任意 IP**,繞過白名單。而且因為 `$proxy_add_x_forwarded_for` 是「在客戶端傳來的值後面追加」,這個偽造的 `10.0.0.1` 會被原封不動帶進鏈條最左邊。

**根本原因**:你只能信任**你自己控制的那幾跳代理**追加的部分,客戶端那一截是不可信的。怎麼分清哪些是可信的、哪些是客戶端偽造的?——用 **`realip` 模組**(`ngx_http_realip_module`,Nginx 標配)。

```nginx
# 宣告「哪些來源是我信得過的代理」——只有來自這些 IP 的那一跳,XFF 才採信
set_real_ip_from  10.0.0.0/8;        # 內網/上游 LB 網段
set_real_ip_from  172.16.0.0/12;
real_ip_header    X-Forwarded-For;   # 從哪個頭還原真實 IP
real_ip_recursive on;                # 從右往左剝掉可信代理,停在第一個「不可信」的 IP
```

`realip` 的工作機制(內幕):Nginx 收到請求後,看「直連我的這個 IP」是否在 `set_real_ip_from` 的可信清單裡。是的話,才去讀 `X-Forwarded-For`,**從右往左**(`real_ip_recursive on`)逐個剝掉「在可信清單裡」的 IP,**剝到第一個不在清單裡的 IP——那就是真實客戶端**,把 `$remote_addr` 重寫成它。這樣攻擊者偽造的 `10.0.0.1`(若它在可信網段裡)會被當成「中間代理」剝掉,真正的源 IP 才浮出來;反之偽造一個外部 IP 也沒用,因為它會停在攻擊者自己那一跳。

**架構結論**:
- 你的反代是**直接面向公網**的第一跳:不要無腦 `$proxy_add_x_forwarded_for`,而是用 `real_ip_header` + `set_real_ip_from` 把可信邊界框死;面向公網那層**應該主動覆蓋(而非追加)** XFF,只留你信得過的鏈。
- 你的反代在**雲 LB 後面**(LB 已經填好 XFF):把 LB 的網段加進 `set_real_ip_from`,讓 Nginx 信任 LB 填的那一截。
- **永遠不要**讓「客戶端可控的 XFF」直接流進「IP 白名單/限流」的判斷。

> 一句話面試答法:「`X-Forwarded-For` 是普通請求頭,客戶端能偽造,所以**不能無條件信任**。要用 `realip` 模組設 `set_real_ip_from` 宣告可信代理網段,Nginx 只採信來自可信代理那幾跳的 XFF,從右往左剝到第一個不可信 IP 當真實客戶端。直接對公網的那層尤其不能照單全收。」

---

## 3. 🔬 proxy buffer:為什麼要把後端「早點放掉」

緩衝是反向代理裡一個**性能 / 穩定性的關鍵開關**,但它的價值不直覺。先看默認行為:

> **`proxy_buffering on`(默認開啟)**:後端一回應,Nginx 就**盡快把回應全部讀進自己的緩衝區**(記憶體 `proxy_buffers`,放不下就落臨時檔案 `proxy_temp_path`),讀完就**讓後端連線回到連線池**,然後 Nginx 再**按客戶端的節奏**慢慢把緩衝的內容送給客戶端。

### 3.1 為什麼這對「慢客戶端」至關重要

想像一個場景:客戶端在 3G 網路、下載一個 5MB 的回應要 30 秒;後端 100ms 就生成好了這 5MB。

- **`proxy_buffering on`(默認,正確)**:後端 100ms 吐完 5MB → Nginx 收進緩衝 → **後端連線立刻釋放回池子,去服務下一個請求**。那個慢客戶端接下來 30 秒只在佔用 Nginx 的緩衝(Nginx 是事件驅動、扛海量慢連線很便宜,↪ `gateway/01`),**完全不佔後端**。
- **`proxy_buffering off`**:Nginx 收一點就轉一點,後端連線必須**陪著慢客戶端全程 30 秒**才能釋放。如果後端是「一連線一線程 / 連線池有限」的傳統服務,1000 個慢客戶端就把後端的 1000 個工作執行緒/連線全佔住了——後端**被慢客戶端拖垮**,這正是反向代理要解決的核心問題之一。

**一句話**:`proxy_buffering on` 讓 Nginx 當「**快速吸收後端回應、再慢慢喂客戶端**」的海綿,把昂貴的後端從慢客戶端手裡**早點放掉**。

### 3.2 緩衝相關參數

```nginx
proxy_buffering on;                  # 默認開;反代生產環境基本都該開
proxy_buffers        8 16k;          # 每個連線最多 8 塊、每塊 16k 的記憶體緩衝
proxy_buffer_size    16k;            # 存「回應頭 + 第一塊 body」的緩衝
proxy_busy_buffers_size 32k;         # 已可開始送客戶端的緩衝上限
proxy_max_temp_file_size 1024m;      # 緩衝放不下時落磁碟的上限(設 0 = 禁用落盤)
```

### 3.3 什麼時候反而要關掉 buffering

少數場景要 `proxy_buffering off`(或對單個 location 關):

- **SSE / 長輪詢 / 串流回應**(如 LLM token 流式輸出):你**要**Nginx 收到一點就立刻轉一點,而不是等後端吐完。這時 `proxy_buffering off`(或設較小緩衝、配 `X-Accel-Buffering: no`)。
- **gRPC**:用 `grpc_pass`,有自己的緩衝語意。

> 注意區分:`proxy_buffering` 管的是**後端 → 客戶端**方向(回應)。**請求方向**(客戶端 → 後端)的緩衝是 `proxy_request_buffering`,默認也是 on(先收完整個請求體再轉後端,避免慢上傳佔住後端),上傳大檔的串流場景才考慮關。

---

## 4. 🔬 超時三件套:`connect` / `send` / `read` 各管哪一段卡頓

反代有三個和後端互動的超時,**對應請求生命週期的三個不同階段**。分不清它們,就會把「後端慢」誤判成「後端掛」,或調錯參數。

```nginx
proxy_connect_timeout 5s;    # 階段①:和後端建 TCP 連線(+ TLS 握手)
proxy_send_timeout    60s;   # 階段②:Nginx 往後端「寫請求」期間,兩次成功寫之間的最長間隔
proxy_read_timeout    60s;   # 階段③:Nginx 等後端「回應」期間,兩次成功讀之間的最長間隔
```

| 超時 | 管哪一段 | 觸發時通常意味著 | 觸發後 Nginx 行為 |
|---|---|---|---|
| **`proxy_connect_timeout`** | 從「決定連後端」到「TCP 連線建立(含 TLS)」 | 後端**掛了 / 埠不通 / 網路不可達 / backlog 滿**——根本連不上 | 連不上 → 通常觸發 **502**(若有其他可用 upstream 會 `next_upstream` 重試) |
| **`proxy_send_timeout`** | Nginx 向後端**發送請求**期間,**相鄰兩次成功寫操作**的間隔 | 後端**讀請求極慢 / 不讀**(少見,大請求體 + 後端卡住時才會撞到) | 超時 → 通常 **504** |
| **`proxy_read_timeout`** | Nginx **等後端回應**期間,**相鄰兩次成功讀操作**的間隔 | 後端**連上了但處理太慢**(慢 SQL、死循環、下游卡住)——最常見的一個 | 超時 → **504 Gateway Timeout** |

**三個關鍵理解**:

1. **`connect` 對應「連不上」,`read` 對應「連上了但回得慢」**——這正是 502 和 504 的分水嶺(ch10 會把狀態碼診斷講全)。面試常問「502 和 504 怎麼分」,根子就在這:**502 = 後端拒連/連不上/回了非法回應**(connect 階段或協議錯);**504 = 後端連上了但沒在 `proxy_read_timeout` 內回完**(read 階段超時)。
2. **`send_timeout` / `read_timeout` 不是「整個請求的總時長上限」,而是「兩次 I/O 之間的最長靜默間隔」**。後端只要每隔幾秒吐一點數據,`read_timeout 60s` 就**不會**觸發,哪怕總共傳了 10 分鐘。所以它防的是「**卡死不動**」,不是「**總耗時太長**」。要限總時長得另想辦法(後端自己控、或在 location 層用其他手段)。
3. **`connect_timeout` 不要設太長**:後端真掛時,你希望**快速失敗**去重試下一台或回 502,而不是讓客戶端乾等。一般 `connect_timeout` 設幾秒(2~5s),`read_timeout` 按後端最慢的合理回應時間設(默認 60s,慢介面才往上調,並只在那個 location 調,別全局放大)。

> ⭐ **白板答法**(被問「三個超時分別管什麼」):
> 「`connect_timeout` 管**連後端那一步**——撞到它通常是後端掛了/連不上,回 502。`send_timeout` 管 Nginx **往後端寫請求**時相鄰兩次寫的間隔。`read_timeout` 管 Nginx **等後端回應**時相鄰兩次讀的間隔——撞到它是後端連上了但處理太慢,回 504。記住兩件事:`connect` 對應 502、`read` 對應 504,這就是 502/504 的分水嶺;而且後兩個是『兩次 I/O 之間的靜默間隔上限』,不是『總耗時上限』。」

---

## 5. `upstream` 區塊:把多台後端組成一個池子

前面 `proxy_pass http://backend;` 裡的 `backend`,通常指向一個 `upstream` 區塊——它定義「後端伺服器組」以及**怎麼在它們之間分流、怎麼處理掛掉的成員、怎麼復用連線**。

```nginx
upstream backend {
    least_conn;                                   # 負載均衡策略(見 5.1)

    server 10.0.0.11:8080 weight=3;               # 權重 3(分到 3 倍流量)
    server 10.0.0.12:8080;                        # 權重默認 1
    server 10.0.0.13:8080 max_fails=3 fail_timeout=10s;  # 被動健康檢查(見 5.3)
    server 10.0.0.14:8080 backup;                 # 備援:只有主後端全掛才啟用

    keepalive 32;                                 # 對後端的連線池(見 5.4)
}

server {
    location / {
        proxy_pass http://backend;
        proxy_http_version 1.1;                   # keepalive 需要 HTTP/1.1
        proxy_set_header Connection "";           # 清掉逐跳 Connection 頭,才能復用
    }
}
```

### 5.1 負載均衡策略(Nginx 怎麼**選**,不是演算法原理)

| 指令 | 怎麼分 | 適合 |
|---|---|---|
| **(默認)round-robin** | 加權輪詢,依 `weight` 比例輪流 | 後端同質、請求成本均勻 |
| **`least_conn`** | 分給「當前活躍連線數最少」的後端 | 請求耗時不均(有的快有的慢),避免慢請求堆在一台 |
| **`ip_hash`** | 按客戶端 IP 哈希固定到某台 | 需要**會話黏性**(session 存本機時);但一台掛了會重新分布 |
| **`hash key [consistent]`** | 按自定 key(如 `$request_uri`)哈希;加 `consistent` 用一致性哈希 | 想按 URL/自定鍵做快取親和或分片 |

> 這些是「Nginx 提供哪幾種、怎麼配」。**演算法本身的取捨**(輪詢 vs 最少連線 vs 一致性哈希 vs P2C 的數學/抖動/熱點問題)↪ `system-design/05-服務治理設施.md`,本章不重講。
>
> 另:Nginx 開源版**沒有內建主動健康檢查**(主動定期探活的 `health_check` 在商業版 Nginx Plus;開源版靠下面的「被動」健康檢查,或用 OpenResty/第三方模組補)。`hash`/`ip_hash` 的會話黏性,在容器化彈性伸縮的世界裡通常不如「把 session 外移到 Redis」乾淨——能無狀態就無狀態。

### 5.2 server 權重

`weight=N`(默認 1):流量按權重比例分配,常用於**灰度**(新版本先給 `weight=1`,老版本 `weight=9`,慢慢調)或**異構機器**(大機器給高權重)。

### 5.3 🔬 被動健康檢查:`max_fails` / `fail_timeout`

開源 Nginx 用**被動**健康檢查——不主動探活,而是**在轉發真實請求的過程中觀察失敗**:

```nginx
server 10.0.0.13:8080 max_fails=3 fail_timeout=10s;
```

機制:
- 在 `fail_timeout`(10s)的時間窗內,如果這台後端累計失敗達到 `max_fails`(3 次),Nginx 就把它**標記為不可用**,在接下來的 `fail_timeout`(10s)內**不再往它轉發**。
- `fail_timeout` 一過,Nginx 會**再試一次**這台——成功就恢復,失敗就再隔離一個 `fail_timeout`。
- 「失敗」的定義由 `proxy_next_upstream` 控制(默認把 connect 錯誤、後端拒連等算失敗;可配置是否把超時、`http_500`/`http_502`/`http_503` 等也算進去)。

**邊界與坑**:
- 這是「**事後**」隔離——要等真的失敗了 `max_fails` 次才隔離,所以**頭幾個請求會打到掛掉的後端**(被 `next_upstream` 重試到別台,客戶端通常無感,但後端錯誤日誌會有)。要「掛了立刻不打」需要**主動**健康檢查(Nginx Plus 或第三方模組)。
- `max_fails=0` 表示**永不隔離**(這台永遠在池子裡),慎用。
- 全部後端都被標記失敗時,Nginx 會回 **502/503**,並可能在下一輪重新嘗試(取決於設定)——ch10 的狀態碼診斷會接上這條。

### 5.4 🔬 `keepalive` 連線池:別對後端每請求都重握手

```nginx
upstream backend {
    server 10.0.0.11:8080;
    keepalive 32;                 # 每個 worker 對這個 upstream 保留最多 32 條空閒長連線
}
location / {
    proxy_pass http://backend;
    proxy_http_version 1.1;       # ① keepalive 需要 HTTP/1.1
    proxy_set_header Connection ""; # ② 清掉逐跳的 Connection 頭,才能復用
}
```

不配連線池時,Nginx **每個到後端的請求都新建一條 TCP 連線、用完就關**——每次都付 TCP 三次握手(+ 後端若是 HTTPS 還有 TLS 握手)的成本,高 QPS 下這是純浪費,還會把後端的 `TIME_WAIT` 撐爆。配了 `keepalive` 就維持一個**到後端的長連線池**復用。

**三個必須記住的點**:
1. **`keepalive 32` 是「每個 worker」的數,不是全局**——4 個 worker 就是 4×32 條空閒連線上限。
2. **必須配 `proxy_http_version 1.1`**:HTTP/1.0 默認短連線,不升到 1.1 就復用不了。
3. **必須清 `Connection` 頭**(`proxy_set_header Connection "";`):客戶端可能帶 `Connection: close`,而它是**逐跳(hop-by-hop)頭**——代理若原樣轉給後端,後端就會關掉連線、池子白做。清空它,代理才能維持自己到後端的長連線。

> **連線池的內幕**(為什麼能省握手、`TIME_WAIT` 怎麼回事、它如何構成隱性並發上限)↪ `gateway/01-reverse-proxy-engine.md` 第 3 節,本章不重講,只給「怎麼配」。

---

## 6. 一份能抄上生產的反代基線

把上面串起來,這是一個**生產級反向代理 location 的最小骨架**(可作為你日常的起手式):

```nginx
upstream app {
    least_conn;
    server 10.0.0.11:8080 max_fails=3 fail_timeout=10s;
    server 10.0.0.12:8080 max_fails=3 fail_timeout=10s;
    keepalive 32;
}

# 信任的代理邊界(這台在雲 LB 後面;若直面公網改成覆蓋策略)
set_real_ip_from 10.0.0.0/8;
real_ip_header   X-Forwarded-For;
real_ip_recursive on;

server {
    listen 80;
    server_name api.example.com;

    location /api/ {
        proxy_pass http://app;                 # 注意:無路徑 → /api/ 前綴保留轉給後端

        # —— header:把真實客戶端資訊透傳 ——
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # —— 連線池 ——
        proxy_http_version 1.1;
        proxy_set_header   Connection "";

        # —— 超時三件套 ——
        proxy_connect_timeout 5s;
        proxy_read_timeout    60s;
        proxy_send_timeout    60s;

        # —— 緩衝(默認 on,顯式寫出意圖)——
        proxy_buffering on;
    }
}
```

> 反向代理的**可跑 lab** 已在 `gateway/lab/nginx-reverse-proxy/`(本 track 不重做);快取(ch05)、限流(ch06)會在這個骨架上往下掛。

---

## 交叉引用

- **upstream 連線池為什麼省握手、`proxy_http_version 1.1` + 清 `Connection` 頭的引擎內幕、`TIME_WAIT`、L4 vs L7**:↪ `gateway/01-reverse-proxy-engine.md`(第 3 節「upstream 連線池」)。本章只講「怎麼配」,不重講「為什麼」。
- **負載均衡演算法本身**(輪詢 / 最少連線 / 一致性哈希 / P2C 的原理與取捨、服務發現):↪ `system-design/05-服務治理設施.md`。本章只講 Nginx `upstream` 怎麼**寫**。
- **`location` 匹配優先級、`$host` vs `$http_host`、`add_header` 繼承、`if` 替代方案**:↪ `01-config-model.md`(本章建立在它之上)。
- **正則 / 變數 `location` 下怎麼用 `rewrite` 改路徑再 `proxy_pass`**:↪ `02-rewrite-and-internal-redirect.md`。
- **狀態碼診斷(502 vs 504 vs 499)、`$upstream_response_time` 怎麼讀、連線耗盡定位**:↪ `10-observability-debugging.md`(本章只點出 connect→502 / read→504 的分水嶺)。

---

## 本章小結

- **`proxy_pass` 尾斜線**:後面**有路徑(含尾斜線)= 替換** `location` 前綴;**只有 host = 整段原樣轉**。`location /p/` 下,`http://b;` → 後端收 `/p/...`,`http://b/;` → 後端收 `/...`;尾斜線不對齊會把路徑黏一起。正則 / 變數 `location` 不能用替換模式,要 `rewrite`。
- **必設 header**:`Host $host`(默認 `$proxy_host` 會丟客戶端域名)、`X-Real-IP`、`X-Forwarded-For`、`X-Forwarded-Proto $scheme`。
- **`X-Forwarded-For` 不能無條件信**——客戶端能偽造。用 `realip` 模組 + `set_real_ip_from` 宣告可信代理網段,只採信可信那幾跳的 XFF;直面公網的那層尤其別照單全收。
- **`proxy_buffering on`(默認)** 讓 Nginx 快速吸收後端回應、把昂貴的後端**早點放掉**,再慢慢喂慢客戶端;串流(SSE/LLM)場景才關。
- **超時三件套**:`connect`(連後端,撞到 → 多半 502)/ `send`(寫請求的 I/O 間隔)/ `read`(等回應的 I/O 間隔,撞到 → 504)。`connect↔502`、`read↔504` 是 502/504 的分水嶺;後兩者是「兩次 I/O 的靜默間隔」不是「總耗時上限」。
- **`upstream`**:`weight` 權重 / `least_conn` / `ip_hash` / `hash` 選後端;`max_fails` + `fail_timeout` 被動健康檢查(事後隔離、頭幾個請求會打到掛機);`keepalive` 連線池配 `proxy_http_version 1.1` + 清 `Connection` 頭。

## 章末問答(複習自檢,答案要點都在前面正文)

1. `location /p/ { proxy_pass http://b<?>; }`,客戶端請求 `/p/api`。當 `<?>` 分別是(a)空、(b)`/`、(c)`/app/`、(d)`/app` 時,後端各收到什麼路徑?哪一個會出「路徑黏一起」的事故?

   <details><summary>對答案</summary>
   (a)`proxy_pass http://b;` → 後端收 `/p/api`(無路徑,整段原樣轉,`/p/` 保留)。
   (b)`proxy_pass http://b/;` → 後端收 `/api`(砍掉 `/p/`,剩 `api` 接到 `/` 後)。
   (c)`proxy_pass http://b/app/;` → 後端收 `/app/api`(砍掉 `/p/`,接到 `/app/` 後)。
   (d)`proxy_pass http://b/app;` → 後端收 `/appapi`(剩餘 `api` 直接黏在 `app` 後,**事故**)。
   </details>

2. 反代後不設 `proxy_set_header Host`,後端會收到什麼 `Host`?這在什麼後端架構下會出 bug?正確該設成什麼、為什麼用 `$host` 而不是 `$http_host`?

3. 攻擊者直接發一個帶 `X-Forwarded-For: 10.0.0.1` 的請求,而你的後端「取 XFF 最左值當客戶端 IP 做白名單」。會發生什麼?用 `realip` 模組要設哪兩個關鍵指令、它們各自的作用?「直面公網的那層」和「在雲 LB 後面的那層」對 XFF 的處理策略有何不同?

4. 一個慢客戶端要花 30 秒下載後端 100ms 就生成好的大回應。`proxy_buffering on` 和 `off` 兩種情況下,**後端連線**分別被佔用多久?為什麼說 buffering 能「保護後端」?什麼場景反而要關掉它?

5. **(分辨題)** 下面三種現象,分別最可能撞到哪個超時、最可能回哪個狀態碼?
   (a)後端進程被 kill 了、埠沒人聽;(b)後端連上了,但一條慢 SQL 卡了 90 秒才回;(c)Nginx 往後端傳一個大上傳體,後端卡住不讀。

   <details><summary>對答案</summary>
   (a)撞 `proxy_connect_timeout`(連不上)→ 多半 **502**(若有其他可用 upstream 會先 `next_upstream` 重試)。
   (b)撞 `proxy_read_timeout`(連上了但回得慢,超過讀間隔上限)→ **504**。
   (c)撞 `proxy_send_timeout`(寫請求時相鄰兩次寫的間隔超限)→ 多半 **504**。
   口訣:connect↔502、read↔504;send/read 管的是「兩次 I/O 之間的靜默」不是「總耗時」。
   </details>

6. `upstream` 裡 `keepalive 32` 配 4 個 worker,實際最多有多少條到後端的空閒長連線?為什麼一定要配 `proxy_http_version 1.1` 並清掉 `Connection` 頭?(連線池為什麼省握手的內幕該去哪章看?)

7. 開源 Nginx 的被動健康檢查 `max_fails=3 fail_timeout=10s` 是怎麼隔離一台掛掉的後端的?它和「主動健康檢查」的關鍵差別是什麼?為什麼說「頭幾個請求還是會打到掛掉的後端」?
