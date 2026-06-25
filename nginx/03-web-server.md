# 03 · 當 web server:靜態與 FastCGI

> 一句話:Nginx 最原始的身份——把檔案從磁碟送到客戶端,或把動態請求丟給後端程序(php-fpm、Python uWSGI)。這章教你配靜態服務、壓縮、快取頭、斷點續傳,以及 FastCGI 是什麼、怎麼把 Nginx 接上 php-fpm——同時把「動靜分離」這個面試高頻場景做死。

`root`/`alias` 的路徑拼接邏輯、`try_files` 回退鏈已在 `01-config-model.md`/`02-rewrite-and-internal-redirect.md` 講清,本章只在用到時點一下,不重說規則。

---

## 1. 靜態檔案服務:從 `root` 到 `autoindex`

最小靜態站:

```nginx
server {
    listen 80;
    server_name static.example.com;

    root /var/www/html;          # 所有 location 的磁碟根路徑
    index index.html index.htm;  # 請求目錄時依序嘗試的預設檔案

    location / {
        try_files $uri $uri/ =404;
    }
}
```

**`root`**:把整個請求 URI 拼在 `root` 後面得到磁碟路徑。請求 `/css/app.css` → 對應 `/var/www/html/css/app.css`。路徑拼接規則與 `alias` 的差異見 ↪ `01-config-model.md §4`。

**`index`**:請求的 URI 是一個目錄(以 `/` 結尾)時,Nginx 依序試 `index` 列表裡的檔案。找到就內部重定向到那個檔案繼續處理,找不到就 404 或觸發 `autoindex`。

**`autoindex`**:

```nginx
location /files/ {
    autoindex on;           # 顯示目錄列表(預設 off)
    autoindex_exact_size off;   # 顯示人類可讀的大小(K/M/G),而非位元組數
    autoindex_localtime  on;    # 顯示伺服器本地時間
}
```

`autoindex` 只在 `index` 列表的檔案都不存在時觸發。**生產環境幾乎不開**——它會暴露目錄結構;只用在內部工具或私有下載站。

---

## 2. 🔬 `sendfile`:零拷貝讓資料不過用戶態

```nginx
http {
    sendfile on;        # 幾乎所有靜態服務場景都應開啟
}
```

**為什麼 `sendfile` 快(面試高頻)?**

不開 `sendfile` 時,Nginx 送一個靜態檔案要走四步:

```
磁碟 → 內核頁緩存(read)→ 用戶態 Nginx 緩衝區(第一次拷貝)→ 內核 socket 緩衝區(write,第二次拷貝)→ 網卡
```

開啟 `sendfile on;` 後,Nginx 呼叫 Linux `sendfile(2)` 系統呼叫:

```
磁碟 → 內核頁緩存 → 內核 socket 緩衝區(一次拷貝,或有 DMA 時零拷貝)→ 網卡
```

**資料不過用戶態**——Nginx 進程只傳遞「fd + 偏移 + 長度」給內核,內核自己在兩個緩衝區之間複製(支援 scatter-gather DMA 的網卡甚至連這次內核拷貝都省掉)。CPU 不用搬數據,延遲更低、throughput 更高。

**一句口訣**:「`sendfile` 讓靜態檔案在內核裡直飛網卡,用戶態 Nginx 只是傳票、不搬貨。」

### `tcp_nopush` 與 `tcp_nodelay`:sendfile 的好搭檔

```nginx
sendfile    on;
tcp_nopush  on;   # 搭配 sendfile 使用,把多個小寫攢成一個 TCP 包再發
tcp_nodelay on;   # 關掉 Nagle 算法,降低最後一個小包的延遲
```

三者協同:`sendfile` 負責零拷貝把數據送進 socket 緩衝區;`tcp_nopush`(等緩衝區填滿才推送)讓多個靜態資源的回應頭/正文攢在一起,減少包數;最後一包送完後 `tcp_nodelay` 關掉 Nagle 算法,確保尾包不被額外延遲 40ms。靜態服務三者通開,效果最佳。

### `aio` 與 `directio`:大檔案的特殊武器

```nginx
location /download/ {
    sendfile  on;
    aio       on;         # Linux: 用核內 AIO(io_uring/aio) 讀取,不阻塞 worker
    directio  4m;         # 超過 4 MB 的檔案 bypass 頁緩存,直接 DMA 到用戶緩衝區
}
```

**何時用 `aio`**:檔案極大(如 GB 級影片)或磁碟 I/O 慢時。`sendfile` 在內核頁緩存 miss 時仍會阻塞 worker 去讀磁碟;開 `aio` 讓讀磁碟非同步進行,worker 不被卡住。

**何時用 `directio`**:大檔案一旦進頁緩存往往不再被重複讀(視頻流、軟體包下載),卻佔用大量內核記憶體。`directio` 讓超過閾值的讀取繞過頁緩存(O_DIRECT),省記憶體壓力。注意:`directio` 和 `sendfile` 不能同時對**同一個**讀取生效——超過 `directio` 閾值的讀自動切換到 direct I/O 路徑。

**普通靜態資源(幾 KB–幾 MB 的 HTML/CSS/JS)**:`sendfile on;` 就夠,不需要 `aio`/`directio`。

---

## 3. 壓縮:gzip 與 Brotli

### 3.1 `gzip`

```nginx
http {
    gzip              on;
    gzip_types        text/plain text/css text/javascript application/javascript
                      application/json application/xml image/svg+xml;
    gzip_min_length   1024;    # 小於 1 KB 的回應不壓縮(壓縮開銷比節省的傳輸量大)
    gzip_comp_level   5;       # 1(快/壓縮率低)到 9(慢/壓縮率高),5 是常用平衡點
    gzip_vary         on;      # 回應加 Vary: Accept-Encoding,讓中間快取正確分開儲存
    gzip_proxied      any;     # 對來自代理的請求也壓縮(默認 off)
    gzip_disable      "msie6"; # 對特定 UA 關閉(IE6 已是歷史,可省略)
}
```

**`gzip_types`**:只對指定 MIME type 壓縮。**不要壓縮圖片(JPEG/PNG/GIF/WebP)和字型二進制(woff2)**——它們已是二進制壓縮格式,再壓不但沒收益還多耗 CPU。`text/html` 是內建總是壓縮的,不用另外加。

**`gzip_min_length`**:太小的回應壓縮後可能反而更大(壓縮頭本身有開銷),建議 1024 位元組起步。

**`gzip_vary on`**:告訴下游快取(CDN、瀏覽器)「這份回應因 `Accept-Encoding` 不同而有差異」,避免把壓縮版快取給不支援 gzip 的客戶端。

### 3.2 `gzip_static`:預壓縮,零 CPU

```nginx
location /assets/ {
    gzip_static on;   # 先找 /assets/app.js.gz,找到就直接送;找不到再用 gzip 動態壓
    gzip        on;
    gzip_types  application/javascript text/css;
}
```

**原理**:構建時把靜態資源預壓縮成 `.gz` 副本(webpack、Vite、Rollup 都支援)。請求 `/assets/app.js` 且客戶端支援 gzip 時,Nginx 直接送 `/assets/app.js.gz`,完全不消耗 CPU——`sendfile` 把預壓縮文件零拷貝送出去。高流量靜態站標配。

### 3.3 Brotli:需要模組

```nginx
# 需編譯 ngx_brotli 模組(https://github.com/google/ngx_brotli)
brotli            on;
brotli_comp_level 5;
brotli_types      text/plain text/css application/javascript application/json image/svg+xml;
brotli_static     on;   # 類似 gzip_static,先找 .br 預壓縮檔
```

Brotli 壓縮率比 gzip 好 15–25%,現代瀏覽器(Chrome/Firefox/Edge)均支援。**主發行版的 Nginx 不內建 Brotli**,需要在編譯時加 `--add-module=/path/to/ngx_brotli` 或用含模組的第三方包(nginx-extras、OpenResty)。生產建議:gzip 兜底 + Brotli 搶先,同時開 `brotli_static`/`gzip_static` 讓預壓縮文件直接送。

> ↪ HTTP `Accept-Encoding`/`Content-Encoding` 協商流程、壓縮格式協議細節 → `network/http.md`

---

## 4. 快取頭:告訴瀏覽器/CDN 快取多久

Nginx 在**回應**裡加的快取頭控制下游(瀏覽器、CDN)行為,和 `proxy_cache`(Nginx 自己快取後端回應)是兩個不同的概念。

### 4.1 `expires` 與 `Cache-Control`

```nginx
location /assets/ {
    # 帶指紋的靜態資源(app.abc123.js)→ 永久快取
    expires 1y;
    add_header Cache-Control "public, immutable";
}

location /api/ {
    # 動態 API → 不快取
    expires -1;                    # 等同 Expires: Thu, 01 Jan 1970 00:00:01 GMT
    add_header Cache-Control "no-store";
}

location /images/ {
    # 更新不頻繁但沒指紋的圖片 → 快取 7 天,但允許再驗證
    expires 7d;
    add_header Cache-Control "public, max-age=604800, must-revalidate";
}
```

**`expires` 指令做兩件事**:
1. 設定 `Expires:` 頭(HTTP/1.0 兼容)。
2. **自動設定 `Cache-Control: max-age=<秒數>`**(HTTP/1.1)。

`expires 1y;` = `Cache-Control: max-age=31536000` + 一年後的 `Expires:` 日期。

**靜態資源快取策略(標準做法)**:構建時在檔名嵌入 content hash(如 `app.8f3e2d.js`),設 `expires 1y; add_header Cache-Control "public, immutable";`——指紋不變快取永久有效,指紋一變 URL 就變,舊快取自動失效。

### 4.2 `ETag` 與 `Last-Modified`:協商快取

```nginx
http {
    etag          on;  # 默認 on,Nginx 自動根據 Last-Modified + Content-Length 生成 ETag
}
```

**協商快取的流程(🔬 黑盒裡發生什麼)**:

1. 首次請求:Nginx 回應帶 `ETag: "abc123"` 和 `Last-Modified: Wed, 25 Jun 2026 00:00:00 GMT`。
2. 瀏覽器第二次請求:帶 `If-None-Match: "abc123"`(或 `If-Modified-Since: ...`)。
3. Nginx 比對:若檔案未變(ETag 仍 `abc123`),回 **`304 Not Modified`**,**不送 body**——省傳輸量。若檔案已變,回 `200` 帶新 body 和新 ETag。

**`ETag` vs `Last-Modified`**:`ETag` 精確(只要位元組不同就不同),`Last-Modified` 精度到秒(1 秒內多次修改可能漏改)。兩者同時存在時,`ETag` 優先。

**關閉 ETag 的場景**:Nginx 跑在多台機器後面、同一檔案的 ETag 因 inode/時間戳不同而不一致——客戶端帶的 `If-None-Match` 落到另一台機器可能永遠 miss,造成無謂回源。解法:統一用 `Last-Modified`(時間戳一致),或關閉 `etag off;` + 在構建流程控制快取失效。

> ↪ `ETag`/`Last-Modified`/`Cache-Control` 的 HTTP 協議語義完整說明 → `network/http.md`

---

## 5. `Range` 與斷點續傳(206 Partial Content)

```nginx
location /download/ {
    root /data;
    # Nginx 靜態服務默認支援 Range 請求,不需額外指令
}
```

**Nginx 靜態服務天生支援 `Range`**,無需配置。客戶端帶 `Range: bytes=1000-1999` → Nginx 回 **`206 Partial Content`**,只送指定位元組範圍。

**場景**:
- **影片播放器**:拖進度條 → 瀏覽器發 `Range` 請求跳到對應位置,不必重新下載整個檔案。
- **斷點續傳下載器**:記錄已下載的位元組偏移,重連後從斷點繼續。
- **多線程下載**:把檔案切成多個 `Range` 並行下載,加速大檔案。

**Nginx 回應的 `Accept-Ranges: bytes` 頭**告知客戶端「這個資源支援 Range 請求」。靜態服務自動加,代理後端若後端不支援 Range,Nginx 不會自動補。

**一個需注意的邊界**:如果你的靜態目錄是動態生成的(每次重建目錄可能讓 `Content-Length`/`ETag` 改變),客戶端拿舊的偏移發 `Range` 請求可能拿到錯誤的片段——確保 Range 下載場景下的快取頭設計正確。

---

## 6. FastCGI 與 php-fpm:接上動態程序

### 6.1 FastCGI 是什麼?和反向代理有什麼差異?

| | **反向代理(`proxy_pass`)** | **FastCGI(`fastcgi_pass`)** |
|---|---|---|
| **協議** | 標準 HTTP/1.1 | FastCGI 二進制協議(多路復用,低 overhead) |
| **後端是什麼** | 任何 HTTP server(Go/Python/Java…) | FastCGI 進程管理器(php-fpm、Ruby FastCGI…) |
| **連線方式** | TCP 或 Unix socket,HTTP 握手 | TCP 或 Unix socket,FastCGI 握手 |
| **請求元數據怎麼傳** | 靠 HTTP header | 靠 FastCGI `PARAMS` 記錄(環境變數格式) |

**FastCGI 的歷史背景**:最早 web server 用 CGI——每次請求 `fork()` 一個新進程,開銷極大。FastCGI 讓「PHP 解釋器進程」**常駐**,web server 通過 FastCGI 協議重複利用這些進程——和 HTTP keepalive 連線池的思路一致,只是協議不同。

php-fpm(PHP FastCGI Process Manager)就是管理一池 PHP worker 進程、接受 FastCGI 連線的 daemon。

### 6.2 最小可用 php-fpm 設定

```nginx
server {
    listen 80;
    server_name app.example.com;
    root /var/www/app;
    index index.php index.html;

    # 靜態資源直接送
    location ~* \.(css|js|png|jpg|svg|woff2)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # PHP 請求丟給 php-fpm
    location ~ \.php$ {
        # 防止腳本注入:確保請求的 .php 文件實際存在
        try_files $uri =404;
        fastcgi_pass  unix:/run/php/php8.2-fpm.sock;  # 或 127.0.0.1:9000
        fastcgi_index index.php;
        include       fastcgi_params;                  # 內建的標準 PARAM 定義
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        fastcgi_param PATH_INFO       $fastcgi_path_info;
    }

    # 所有其他請求回退到 index.php(WordPress/Laravel 等 MVC 框架)
    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }
}
```

**關鍵指令說明**:

**`fastcgi_pass`**:指向 php-fpm 監聽的地址。Unix socket(`unix:/run/php/php8.2-fpm.sock`)比 TCP(`127.0.0.1:9000`)略快(省 TCP 握手),但只能在同一台機器用;跨主機用 TCP。

**`fastcgi_params` 和 `fastcgi_param`**:`fastcgi_params` 是 Nginx 預置的標準環境變數映射文件(定義 `REQUEST_METHOD`、`SERVER_NAME`、`HTTP_HOST` 等)。`SCRIPT_FILENAME` 是告訴 php-fpm「要執行哪個 PHP 文件」的關鍵變數,必須手動設定。

**`$document_root$fastcgi_script_name`** vs **`$request_filename`**:兩者通常等價,但 `$request_filename` 更安全(已處理 `alias` 路徑的情況)。

**`try_files $uri =404`**(腳本注入防護):不加這行,請求 `/uploads/photo.jpg/attack.php` 可能被 php-fpm 執行 `photo.jpg` 裡的 PHP 程式碼——因為 php-fpm 的 `cgi.fix_pathinfo` 默認開啟時會把 `/uploads/photo.jpg` 當成腳本、`/attack.php` 當 `PATH_INFO`。`try_files $uri =404` 確保只有真實存在的 `.php` 文件才傳給 php-fpm。

### 6.3 FastCGI 緩衝與超時

```nginx
location ~ \.php$ {
    fastcgi_pass           127.0.0.1:9000;
    fastcgi_read_timeout   60s;     # 等 php-fpm 回應的最長時間
    fastcgi_buffers        16 4k;   # 接收 php-fpm 回應的緩衝
    fastcgi_buffer_size    4k;      # 第一個緩衝的大小(通常放回應頭)
    include fastcgi_params;
    fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
}
```

緩衝機制和 `proxy_pass` 的 `proxy_buffers` 邏輯相同:Nginx 等 php-fpm 的完整回應攢在緩衝區後再送給客戶端,讓 php-fpm worker 早點釋放去服務下一個請求。

### 6.4 uwsgi / scgi:同理

Python uWSGI 用的是 `uwsgi_pass` + `uwsgi_params`(uWSGI 協議);Ruby SCGI 用 `scgi_pass`。原理和設定結構與 FastCGI 幾乎相同——Nginx 把請求用不同的二進制協議轉給對應的進程管理器。

---

## 7. 動靜分離:面試必問場景

**動靜分離**是指把靜態資源(圖片、CSS、JS、字型)和動態請求(PHP/Python/Go API)分開處理——靜態由 Nginx 直接送,動態才轉給後端進程。

**為什麼要分離?**

- 靜態資源不需要進入應用進程,讓 php-fpm/uWSGI worker 只處理真正需要計算的請求,吞吐量大幅提升。
- 靜態資源可以加 `sendfile`、長 `expires`、`gzip_static`,一台 Nginx 應付幾十萬 QPS 靜態請求不費力。
- 靜態資源可以獨立 CDN 化——把 `location /assets/` 的流量直接指向 CDN 邊緣節點。

**典型配置結構**:

```nginx
server {
    listen 80;
    root /var/www/app/public;

    # 靜態資源:Nginx 直接服務
    location ~* \.(ico|css|js|gif|jpg|jpeg|png|svg|woff2|ttf)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
        sendfile on;
        gzip_static on;
        access_log off;   # 靜態資源日誌量大,生產可關
    }

    # 動態請求:轉 php-fpm
    location ~ \.php$ {
        try_files $uri =404;
        fastcgi_pass unix:/run/php/php8.2-fpm.sock;
        include fastcgi_params;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
    }

    # SPA/MVC 框架入口
    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }
}
```

**更進一步的動靜分離架構**:靜態資源放獨立域名(`static.example.com`)+ CDN,動態請求走 API 子域(`api.example.com`)+ Nginx 反代後端集群——這樣靜態 CDN 和動態後端可以獨立擴縮容。↪ 反向代理與 upstream 的配置見 `04-reverse-proxy-and-upstream.md`。

> ⭐ **白板答法**:「動靜分離的核心是讓 Nginx 用 `location` 把 URI 分流:靜態資源(副檔名匹配)直接 `root`+`sendfile`+長快取,動態請求走 `fastcgi_pass` 或 `proxy_pass`。靜態服務的邊際成本幾乎為零,省出 app worker 只處理業務邏輯。CDN 化是動靜分離的終極形態——把靜態資源推到邊緣,動態部分才回源。」

---

## 8. 自訂 `error_page`

```nginx
server {
    root /var/www/app/public;

    # 把特定狀態碼映射到自訂頁面
    error_page 404              /404.html;
    error_page 500 502 503 504  /50x.html;

    # 錯誤頁面 location:阻止無限遞迴
    location = /404.html {
        internal;         # internal 讓這個 location 只能被 error_page 等內部跳轉觸發,
                          # 外部請求 /404.html 會得到 404(而不是遞迴地又 404)
    }
    location = /50x.html {
        internal;
        root /var/www/errors;  # 可以放在不同目錄
    }
}
```

**`internal`**:這是讓 `error_page` 安全的關鍵。不加 `internal`,外部請求直接打 `/404.html` 也能拿到這個頁面,且如果 `/404.html` 本身不存在,就會觸發另一個 404,再跳到 `/404.html`……無限遞迴。加了 `internal`,外部請求 `/404.html` 得到的是真正的 404 狀態(而非這個 location 的內容)。

**進階:把錯誤頁代理到其他服務**

```nginx
error_page 503 @maintenance;
location @maintenance {
    internal;
    proxy_pass http://maintenance-server;   # 維護期間把所有錯誤轉到維護頁服務
}
```

用命名 location(`@maintenance`)配合 `error_page` 做到「出錯時走特殊後端」——細節見 ↪ `02-rewrite-and-internal-redirect.md`。

---

## 交叉引用

- **`root` vs `alias` 路徑拼接規則、`try_files` 回退鏈語法** → ↪ `nginx/01-config-model.md`、`nginx/02-rewrite-and-internal-redirect.md`(本章直接使用,不重講規則)
- **`Accept-Encoding`/`Content-Encoding` 協商、`ETag`/`Last-Modified`/`Cache-Control` HTTP 協議語義、`Range`/`206` 規範** → ↪ `network/http.md`
- **反向代理(`proxy_pass`)與 upstream 連線池** → ↪ `nginx/04-reverse-proxy-and-upstream.md`
- **`sendfile` 使用的 `tcp_nopush`/`tcp_nodelay` 與內核參數聯動(深挖)** → ↪ `nginx/09-performance-tuning.md`
- **`error_page` 的命名 location 與內部跳轉機制** → ↪ `nginx/02-rewrite-and-internal-redirect.md`

---

## 本章小結

- **靜態服務三件套**:`root`(路徑映射)+ `index`(目錄預設檔)+ `try_files`(回退鏈)。`autoindex` 只用於內部工具。
- **`sendfile on`**:靜態服務必開。資料不過用戶態——Nginx 只傳 fd 給內核,內核直接送到網卡。搭 `tcp_nopush` + `tcp_nodelay` 效果最佳。
- **`aio`/`directio`** 是大檔案(GB 級影片、下載站)的進階選項:前者讓磁碟讀取非同步、後者繞過頁緩存省記憶體。普通靜態資源不需要。
- **壓縮**:先開 `gzip`,再用 `gzip_static` + 預壓縮零 CPU 成本送 `.gz`。Brotli 壓縮率更好但需額外模組。`gzip_types` 排除已壓縮的二進制格式。
- **快取頭**:`expires` 同時設 `Expires:` 和 `Cache-Control: max-age`;帶指紋的靜態資源設一年+`immutable`;`ETag`/`Last-Modified` 讓瀏覽器可以 `304 Not Modified` 省傳輸。
- **`Range`/206**:Nginx 靜態服務天生支援斷點續傳,無需配置。
- **FastCGI**:二進制協議,後端是常駐進程管理器(php-fpm)。`fastcgi_pass` 替代 `proxy_pass`,`SCRIPT_FILENAME` 是必設的關鍵變數,`try_files` 防腳本注入。uwsgi/scgi 同理。
- **動靜分離**:用 `location` 副檔名正則分流——靜態 Nginx 直送,動態才進 app worker。這是面試「Nginx 怎麼提升性能」的標準答案。
- **`error_page`**:靜態錯誤頁加 `internal` 防遞迴;可配合命名 location 轉到後端服務。

---

## 章末問答(複習自檢,答案要點都在前面正文)

<details>
<summary>1. `sendfile` 為什麼比不開 `sendfile` 快?說出「資料的複製路徑」的差異。</summary>

不開 `sendfile`:磁碟 → 內核頁緩存 → **用戶態 Nginx 緩衝區(拷貝 1)** → 內核 socket 緩衝區(拷貝 2)→ 網卡。

開啟 `sendfile`:磁碟 → 內核頁緩存 → 內核 socket 緩衝區(一次內核拷貝,支援 DMA 可能零拷貝)→ 網卡。**資料不過用戶態**,省掉至少一次記憶體拷貝和兩次系統呼叫(read + write → sendfile)。
</details>

<details>
<summary>2. `gzip_static` 和 `gzip` 指令有什麼不同?各自什麼場景用?</summary>

`gzip on` 是 Nginx 在請求時**動態**壓縮回應,每次請求都消耗 CPU。`gzip_static on` 是 Nginx 先找 `.gz` 預壓縮副本(構建時生成),找到就直接送,**不消耗壓縮 CPU**。高流量靜態資源兩者結合:有 `.gz` 就走 `gzip_static`,沒有則 fallback 到 `gzip` 動態壓。
</details>

<details>
<summary>3. `ETag` 和 `Last-Modified` 各自解決什麼問題?什麼場景下關掉 `ETag` 反而更好?</summary>

`ETag` 精確到位元組:只要內容不同就不同,精度高。`Last-Modified` 精度到秒,1 秒內多次修改可能漏失。二者都觸發協商快取(304)。

關閉 `ETag` 的場景:多台 Nginx 節點服務同一靜態檔案,但各節點 `ETag` 因 inode/時間戳差異而不同——客戶端帶 `If-None-Match` 落到另一台機器永遠 miss,破壞快取效果。此時統一用 `Last-Modified`(用共享構建輸出的 mtime)。
</details>

<details>
<summary>4. FastCGI 和反向代理(`proxy_pass`)的核心差異是什麼?`SCRIPT_FILENAME` 為什麼必設?</summary>

`proxy_pass` 用 HTTP/1.1 協議與後端通訊,後端是任意 HTTP server。`fastcgi_pass` 用 FastCGI 二進制協議,後端是常駐的 FastCGI 進程管理器(php-fpm),請求元數據通過 `PARAMS` 記錄傳遞(環境變數格式)。

`SCRIPT_FILENAME` 告訴 php-fpm「要執行的 PHP 腳本在哪」,沒有它 php-fpm 不知道要跑哪個文件,請求會失敗。
</details>

<details>
<summary>5. 「動靜分離」的配置思路是什麼?為什麼靜態資源的 `location` 要放在 PHP `location` 前面(或用正則)?</summary>

用 `location ~* \.(css|js|png|...)$` 匹配靜態資源副檔名,配 `root`+`sendfile`+長快取;用 `location ~ \.php$` 丟給 fastcgi_pass;兜底 `location /` 用 `try_files` 回退到 `index.php`。

靜態資源 `location` 放前面是為了讓正則能先命中靜態副檔名(正則按設定檔出現順序,第一個中即停),不需要每個圖片請求都走到 PHP 入口——見 ch01 的 `location` 優先級規則。
</details>

<details>
<summary>6. `error_page 404 /404.html;` 為什麼要配合 `location = /404.html { internal; }` 使用?不加 `internal` 會怎樣?</summary>

`internal` 限制這個 location 只能被 Nginx 內部機制觸發(如 `error_page`、`try_files` 回退),外部請求 `/404.html` 會返回真正的 404。

不加 `internal`:外部請求 `/404.html` 可以直接取得錯誤頁(資訊洩露風險);更嚴重的是,如果 `/404.html` 本身不存在,`error_page` 又觸發 404 → 再跳 `/404.html` → 無限遞迴,導致 500。
</details>
