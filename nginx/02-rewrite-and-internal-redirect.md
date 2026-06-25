# 02 · rewrite / return / 內部跳轉

> 一句話:ch01 講「請求落到哪個 `location`」,本章講「請求落進去之後 URI 怎麼被改、怎麼跳到別處」——兩章合起來才是完整的「請求落到哪段設定」圖。

---

## 0. 為什麼需要改寫與跳轉

純靜態的 `location` 只能匹配 URI,沒有「如果 URI 是 /old/* 就轉到 /new/*」這類能力。實際場景：

- **路徑規範化**:舊 URL 改版後 301 永久跳轉新路徑。
- **SPA 路由**:所有前端路由(`/dashboard/xxx`)都要交給 `index.html` 處理。
- **HTTPS 強制**:HTTP 請求統一 301 跳 HTTPS。
- **內部路由**:後端 API 告訴 Nginx「去讀另一個路徑的檔案」(X-Accel-Redirect)。
- **自訂錯誤頁**:404 → 轉到靜態頁面,不另起 HTTP 往返。

Nginx 有三個主要工具:`rewrite`、`return`、`try_files`。加上一個機制:命名 location + `error_page` 觸發的**內部跳轉**。先把每個工具的規則教全,再談組合。

---

## 1. `return`:最直接的結束請求

### 語法與用途

```nginx
return <code>;
return <code> <URL>;
return <URL>;   # 隱含 302
```

`return` **直接結束請求處理階段**,把指定狀態碼和(可選)Location 頭發給客戶端,不再往下執行任何指令。它不重走 `location` 匹配、不改寫 `$uri`。

常見用法:

```nginx
# HTTP 強制跳 HTTPS
server {
    listen 80;
    server_name example.com;
    return 301 https://$host$request_uri;
}

# 永久移走的舊路徑
location /old-page/ {
    return 301 /new-page/;
}

# 關閉連線(不回任何 HTTP 回應):常用於封鎖惡意 IP
location /admin/ {
    return 444;  # 444 是 Nginx 自訂碼,表示直接關 TCP 連線
}

# 測試用:直接回固定文字
location /health {
    return 200 "ok\n";
}
```

### `return 444`:Nginx 私有碼

`444` 不是標準 HTTP 狀態碼,Nginx 用它表示「不回任何 HTTP 回應、直接關閉 TCP 連線」。對惡意掃描、IP 封鎖非常有效——攻擊方連 RST 都得不到,節省 Nginx 資源。

### 為什麼 `return` 優先於 `rewrite`

> **⭐ 面試高頻點:「`rewrite` 和 `return` 誰先?」**

規則:**`return` 出現在 `server` 或 `location` 區塊時,在 rewrite 模組執行的 phase 裡也是直接退出的——但重點不在執行順序,而在設計哲學**:

- `rewrite` 是**模式匹配 + 替換**,底層是正則引擎,有 PCRE 開銷。
- `return` 是**無條件退出**,代碼路徑最短、零正則開銷。

**結論**:只要能用 `return` 表達的跳轉,就不要用 `rewrite redirect/permanent`。`return` 更快、更清晰、更不容易出錯。

白板答法:「如果只是要做重定向(301/302)或直接關連線(444),用 `return`,因為它比 `rewrite` 更直接,沒有正則開銷,也不會重走 location 匹配。`rewrite` 留給需要改寫 URI 後繼續往下走的場景。」

---

## 2. `rewrite`:改 URI 後繼續走

### 語法

```nginx
rewrite <正則> <替換> [flag];
```

- `<正則>`:PCRE 正則,匹配當前 `$uri`(注意是解碼後的 URI,不含 query string)。
- `<替換>`:新的 URI 或 URL。可引用正則捕獲組(`$1`、`$2`…)。
- `[flag]`:控制改完 URI 之後做什麼。

### 正則捕獲與 `$1` 引用

括號 `(...)` 捕獲子群,按出現順序編號 `$1`、`$2`…:

```nginx
rewrite ^/users/(\d+)/profile$ /api/user-profile?id=$1 last;
# 請求 /users/42/profile → 改為 /api/user-profile?id=42
```

注意:替換字串裡如果包含 `?`,Nginx 會把原有 query string 丟棄,只用新的;若想保留,用 `$is_args$args`(或替換字串末尾加 `?`):

```nginx
rewrite ^/legacy/(.*)$ /new/$1?$args last;
# 或者:
rewrite ^/legacy/(.*)$ /new/$1$is_args$args last;
```

---

## 3. `rewrite` 的四個 flag:規則先教全

> **⭐ 面試高頻點:「`last` 和 `break` 差在哪?」**

### 完整規則表

| flag | 改完 URI 後做什麼 | 重走 location 匹配? | 回客戶端? |
|---|---|---|---|
| `last` | 停止當前 rewrite 區塊,**用新 URI 重走全部 location 匹配** | **是**,從頭比 | 否(內部) |
| `break` | 停止當前 rewrite 區塊,**繼續在本 location 執行後續指令**,不重新匹配 | 否 | 否(內部) |
| `redirect` | 發 **302 臨時重定向**給客戶端 | 否(客戶端重定向) | 是 |
| `permanent` | 發 **301 永久重定向**給客戶端 | 否(客戶端重定向) | 是 |

### `last`:改完 URI → 重走 location 匹配

```nginx
server {
    location /old/ {
        rewrite ^/old/(.*)$ /new/$1 last;
        # ↑ 執行到這裡,URI 被改成 /new/xxx,然後 Nginx 從頭跑 location 匹配
        # 下面這行不會被執行到:
        proxy_pass http://backend;
    }

    location /new/ {
        proxy_pass http://backend;  # 這裡才會被命中
    }
}
```

**何時用 `last`**:需要「改 URI 後換到另一個 location 處理」。最常見:把舊路徑統一規範到新路徑、讓另一個 location 接手邏輯。

**陷阱**:`last` 會重走所有 location 匹配,有機會再次命中帶 `rewrite ... last` 的 location → 重定向環(見第 5 節)。Nginx 限制同一請求最多重寫 10 次,超過回 `500 Internal Server Error`。

### `break`:改完 URI → 停在本 location

```nginx
location /download/ {
    rewrite ^/download/(.*)$ /files/$1 break;
    # URI 改成 /files/xxx,但繼續在這個 location 執行
    root /data;
    # 結果:Nginx 會去讀 /data/files/xxx 這個實體檔
}
```

**何時用 `break`**:已經在正確的 `location` 裡,只是需要調整 URI 對應到磁碟上的路徑,不想重走匹配。反向代理場景少用,靜態檔案場景偶爾用。

**`last` vs `break` 一句話對比**:`last` 像是「拿新 URI 重新排隊進 location 選手村」,`break` 像是「就地換個號碼牌繼續在這個視窗辦」。

### `redirect` / `permanent`:回客戶端的跳轉

```nginx
location /promo/ {
    rewrite ^/promo/(.*)$ /campaign/$1 redirect;    # 302
}

location /legacy-api/ {
    rewrite ^/legacy-api/(.*)$ /v2/api/$1 permanent; # 301
}
```

**何時用 `redirect` vs `permanent`**:
- `permanent`(301):URL 真的永遠搬家,瀏覽器會快取,下次直接去新 URL,不再問 Nginx。適合 SEO、真實改版。
- `redirect`(302):臨時跳轉,瀏覽器下次還是問 Nginx。適合 A/B 測試、臨時維護頁面。

**提醒**:301 被瀏覽器積極快取,一旦發出去很難收回——確定後才用 `permanent`。開發/測試用 `redirect` 更安全。

> **優先原則再次確認**:若只是做 301/302 跳轉,`return 301 <URL>` 比 `rewrite ... permanent` 更推薦。`rewrite redirect/permanent` 的優勢只在「要用正則捕獲重組目標 URL」時。

---

## 4. `try_files`:回退鏈

### 語法

```nginx
try_files <路徑1> <路徑2> ... <最終回退>;
```

Nginx 按順序試每個路徑:
- 若為檔案(`$uri`):確認實體檔案存在、可讀。
- 若為目錄(`$uri/`):確認目錄存在。
- 若為 `=<code>`:直接回這個狀態碼。
- 若為 `@<name>`:跳到命名 location(見第 5 節)。
- 最後一個條目必定是「兜底」。

> 🔬 **內幕**:`try_files` 不做 HTTP 重定向,它是在 content phase 裡直接改 `$uri` 並繼續處理——是純內部行為,不回客戶端任何回應、不重走 `server`/`location` 匹配樹的頂層(除非最後回退到命名 location,那是內部跳轉,見下節)。

### 靜態站標準寫法

```nginx
location / {
    root /var/www/html;
    try_files $uri $uri/ =404;
    # 試 1:/var/www/html/請求URI(檔案)
    # 試 2:/var/www/html/請求URI/(目錄 + index)
    # 兜底:404
}
```

### SPA(Single Page App)標準寫法

```nginx
location / {
    root /var/www/app;
    try_files $uri $uri/ /index.html;
    # 試 1:靜態檔案(js/css/png…)
    # 試 2:目錄
    # 兜底:交給 index.html,讓前端 router 處理路徑
}
```

前兩格讓靜態資源正常回,第三格讓前端路由(`/dashboard/profile`)不 404。

### 配合後端 API 的混合寫法

```nginx
location / {
    try_files $uri $uri/ @backend;
}

location @backend {
    proxy_pass http://app_server;
}
```

靜態資源先嘗試,找不到才轉給後端。`@backend` 是命名 location,見下節。

---

## 5. 命名 location(`@name`)與內部跳轉

### 什麼是命名 location

```nginx
location @fallback {
    proxy_pass http://origin;
}
```

以 `@` 開頭的 `location` 叫**命名 location**。它**不參與請求 URI 的正常匹配**,只能被 `try_files`、`error_page` 等指令「點名跳過來」,不能被外部客戶端直接請求命中。

### `error_page` 觸發的內部跳轉

```nginx
server {
    error_page 404 @custom_404;

    location @custom_404 {
        root /var/www/errors;
        try_files /404.html =404;
    }

    location / {
        root /var/www/html;
        try_files $uri $uri/ =404;
    }
}
```

### 🔬 內部跳轉的機制(黑盒裡發生什麼)

當 `error_page 404 @custom_404` 被觸發:

1. Nginx 產生了一個 `404` 的內部錯誤結果。
2. `error_page` 指令捕獲到這個 404。
3. Nginx **不把 404 回給客戶端**,而是做一次**內部重定向(internal redirect)**:把 `$uri` 替換成 `@custom_404` 指向的 location,**重走 content phase**。
4. `@custom_404` location 的內容執行完後,才把最終回應發給客戶端。

**關鍵特性**:
- **不回客戶端**:客戶端不知道有內部跳轉,URL bar 不變。
- **重走 phase**:是真正的「重新執行」,不只是「換個設定塊」。新 location 裡的 `root`、`try_files`、`proxy_pass` 都會生效。
- **繼承外部請求頭**:原始請求的方法、頭、body 保留(對 `proxy_pass` 型命名 location 有意義)。
- **`$uri` 被改寫**:`error_page` 跳轉後,`$uri` 反映的是內部跳轉目標,不再是原始請求 URI。若需要原始 URI,用 `$request_uri`(它永遠是原始值)。

### `error_page` 帶 URL 重定向 vs 命名 location

```nginx
# 這是回客戶端的 302 重定向(客戶端看得到):
error_page 404 /404.html;        # 內部重定向到 /404.html
error_page 404 = /fallback.html; # 用 = 可把狀態碼改成 fallback 回應的狀態碼

# 保持狀態碼:
error_page 404 =404 @custom_404; # 內部跳轉到命名 location,最終狀態碼仍是 404
```

常見困惑:
- `error_page 404 /custom.html;` → 內部重定向到 `/custom.html`(再做一次正常 location 匹配)。若 `/custom.html` 不存在,可能再觸發 404 → 環(Nginx 有防護,最多一跳)。
- `error_page 404 @name;` → 直接跳到命名 location,最清晰最安全。

### `X-Accel-Redirect`:後端決定內部跳轉

```nginx
location /protected/ {
    internal;                  # 只接受內部請求
    root /secret;
}

location /api/ {
    proxy_pass http://app;
    # app 在回應頭加 X-Accel-Redirect: /protected/secret.pdf
    # Nginx 攔截這個頭,做內部跳轉到 /protected/ location
}
```

`X-Accel-Redirect` 讓後端應用決定「Nginx 去讀哪個內部路徑」,常用於鑑權後的私密檔下載。`internal` 指令把 location 標記為「只接受內部跳轉」,外部直接請求這個路徑 Nginx 回 404。

---

## 6. 重定向環:怎麼產生、怎麼避免

### 什麼是重定向環

**重定向環(redirect loop)**:改寫後的 URI 又匹配回同一個 `rewrite` 規則,導致無窮循環。

Nginx 的防護:同一請求的 `rewrite ... last` 最多執行 **10 次**,超過回 `500 Internal Server Error`(error_log 裡可見 `rewrite or internal redirection cycle`)。

### 常見產生方式

**Case 1:location 用正則 `rewrite ... last`,改完又匹配同一 location**

```nginx
location ~* \.php$ {
    rewrite ^(.*)$ /index.php last;  # ← 壞:改成 /index.php 後還是 .php,又命中本 location
}
```

`/index.php` 結尾 `.php`,再次命中 `~* \.php$`,再次 rewrite,死循環。

**修法:用 `break` 代替 `last`**

```nginx
location ~* \.php$ {
    rewrite ^(.*)$ /index.php break;  # 改完不重走,安全
}
```

**Case 2:HTTP → HTTPS 重定向設在 `https` 的 server 裡**

```nginx
# 危險:443 server 裡也有這條,HTTP 和 HTTPS 都跳
server {
    listen 443 ssl;
    return 301 https://$host$request_uri;  # 自己跳自己
}
```

**修法:把 HTTP 跳轉放在 `listen 80` 的 server**

```nginx
server {
    listen 80;
    return 301 https://$host$request_uri;  # 只有 HTTP 觸發
}

server {
    listen 443 ssl;
    # 這裡不再有跳轉
}
```

**Case 3:`try_files` 最後回退到自身**

```nginx
location / {
    try_files $uri $uri/ /;  # ← 壞:兜底是 / 又觸發本 location
}
```

**修法:回退到具體檔或命名 location**

```nginx
location / {
    try_files $uri $uri/ /index.html;  # 明確的兜底
}
```

### 避免重定向環的原則

1. **`rewrite ... last` 在可能匹配自身的 location 裡,考慮換 `break`**。
2. **HTTP→HTTPS 跳轉只寫在 `listen 80` 的 server 區塊**。
3. **`try_files` 兜底不要指向自身 URI**;用 `=404`、`/index.html` 或 `@命名 location`。
4. **測試時看 `error_log`**:環出現時 Nginx 會記錄 `rewrite cycle`。

---

## 7. 組合場景速查

### 場景 A:SPA 部署(Vue/React)

```nginx
server {
    listen 80;
    root /var/www/spa;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 請求不交給 SPA
    location /api/ {
        proxy_pass http://backend;
    }
}
```

### 場景 B:舊路徑永久遷移

```nginx
# 簡單整條:用 return
location /old-blog/ {
    return 301 /articles/;
}

# 帶正則捕獲:用 rewrite + permanent(或 return + 拼接)
location ~* ^/posts/(\d+)$ {
    return 301 /articles/$1;  # return 也能直接用 $1,需要在 location 正則匹配後
}

# 若在 server 層用 rewrite:
rewrite ^/posts/(\d+)$ /articles/$1 permanent;
```

### 場景 C:自訂錯誤頁(不暴露 URI)

```nginx
server {
    error_page 404 @not_found;
    error_page 500 502 503 504 @server_error;

    location @not_found {
        root /var/www/errors;
        try_files /404.html =404;
    }

    location @server_error {
        root /var/www/errors;
        try_files /5xx.html =500;
    }
}
```

### 場景 D:維護模式(全站臨時關)

```nginx
server {
    # 放行健康檢查
    location = /health {
        return 200 "ok\n";
    }

    # 其他全回 503 + 自訂頁
    location / {
        return 503;
    }

    error_page 503 @maintenance;
    location @maintenance {
        root /var/www;
        try_files /maintenance.html =503;
        add_header Retry-After 3600;
    }
}
```

---

## 交叉引用

- **`location` 匹配優先級、指令繼承、`$uri` vs `$request_uri` 內建變數** → `nginx/01-config-model.md`
- **請求管線 / Nginx 的處理 phase(rewrite → access → content → header filter)** → `gateway/02-request-pipeline.md`
- **靜態服務的 `root`/`alias`/`try_files` 實戰(sendfile/gzip/快取頭)** → `nginx/03-web-server.md`
- **反向代理場景的 `try_files` + `@fallback` 組合** → `nginx/04-reverse-proxy-and-upstream.md`
- **`X-Accel-Redirect` 鑑權下載場景的鑑權概念** → `gateway/04-edge-authn-authz.md`

---

## 本章小結

| 工具 | 核心行為 | 典型場景 |
|---|---|---|
| `return` | 直接結束,回狀態碼/URL | 301/302 跳轉、`444` 封鎖、健康檢查固定回應 |
| `rewrite ... last` | 改 URI → 重走 location 匹配 | 路徑規範化、換一個 location 接手 |
| `rewrite ... break` | 改 URI → 繼續在本 location | 調整路徑對應磁碟位置,不換 location |
| `rewrite ... redirect/permanent` | 回 302/301 給客戶端 | 有正則捕獲時才用;純跳轉優先 `return` |
| `try_files` | 按順序試路徑,找不到就下一個 | SPA、靜態回退、混合路由 |
| `@name` + `error_page` | 內部跳轉(不回客戶端、重走 phase) | 自訂錯誤頁、受保護檔下載(`internal`) |

**三條口訣:**
1. **能用 `return` 就不用 `rewrite`**:更快、更清晰。
2. **`last` 換 location、`break` 留原地**:flag 選錯是重定向環的頭號來源。
3. **`try_files` 兜底要明確**:不要讓兜底再次觸發自己。

---

## 章末問答(複習自檢)

以下問題的答案要點都在正文,用於自測。

**Q1. `rewrite ^/api/v1/(.*)$ /api/v2/$1 last;` 和把 `last` 改成 `break`,行為有什麼不同?**

> `last`:URI 改成 `/api/v2/...` 後,Nginx **重新做 location 匹配**,可能命中不同的 location 區塊。`break`:URI 改完後**繼續在當前 location 執行**,不重走匹配。若當前 location 後面跟著 `proxy_pass`,`last` 可能讓請求跑到別的 location 去,`break` 確保還在這裡。

**Q2. 以下設定有什麼問題?怎麼修?**

```nginx
server {
    listen 443 ssl;
    return 301 https://$host$request_uri;
}
```

> 問題:443(HTTPS)的 server 跳轉到 `https://...`,自己跳自己,無窮循環。修法:把 `return 301 https://...` 移到 `listen 80` 的 server 區塊,443 的 server 裡不再有這條。

**Q3. `try_files $uri $uri/ /index.html;` 在 SPA 中各步做什麼?最後兜底為何不該寫成 `/`?**

> 試 1:找對應的靜態實體檔(JS/CSS/PNG…);試 2:找對應目錄(加 index);兜底 `/index.html`:交給前端 router 處理。若兜底寫 `/`,會觸發 `/` 這個 location,再次 `try_files`,再次找不到,死循環。

**Q4. `error_page 404 @custom_404` 觸發後,客戶端的 URL bar 會變嗎?為什麼?**

> **不會變**。`error_page` + 命名 location 做的是**內部跳轉**:Nginx 在內部重走 content phase,但不發 3xx 給客戶端,客戶端不知道有跳轉,URL bar 保持原樣。這和 `return 301 /xxx` 的客戶端重定向本質不同。

**Q5. `return 444` 和 `return 403` 有什麼操作層面的差異?**

> `return 403` 會回完整的 HTTP 回應(包含狀態行、頭、body),客戶端收到後可以顯示錯誤頁面。`return 444` 是 Nginx 私有碼,表示直接關 TCP 連線、**不發任何 HTTP 回應**。對惡意掃描工具更有效(它甚至不知道服務存在),同時節省 Nginx 組裝回應的資源。

**Q6. ⭐ 白板題:生產環境有一個 SPA + API 的 Nginx,前端 `/`、靜態資源 `/static/`、後端 API `/api/`、另有舊路徑 `/v1/` 要 301 到 `/api/v2/`。列出設定骨架。**

```nginx
server {
    listen 80;
    return 301 https://$host$request_uri;  # 強制 HTTPS
}

server {
    listen 443 ssl;
    root /var/www/spa;

    # 舊路徑永久遷移(用 return,有捕獲可換 rewrite)
    location ~* ^/v1/(.*)$ {
        return 301 /api/v2/$1;
    }

    # 靜態資源:直接讀磁碟
    location /static/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API:轉後端
    location /api/ {
        proxy_pass http://backend;
    }

    # SPA:兜底交 index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 自訂錯誤頁
    error_page 404 @not_found;
    location @not_found {
        try_files /404.html =404;
    }
}
```
