# 07 · TLS 實戰:憑證、SNI、OCSP、session 復用、mTLS、certbot

> 一句話:這一章教你在 Nginx 上把 TLS **配對、配好、配快**——從最小可跑的憑證設定,到 SNI 多域名、OCSP stapling 省往返、session 復用省握手、mTLS 雙向驗證,再到 Let's Encrypt 自動化全流程。TLS 的「為什麼貴」與「終止放哪」已在 `gateway/01` 和 `gateway/04` 講透;本章只補「Nginx 怎麼動手」這一層的增量。

---

## 1. TLS 終止放邊緣:面試先定框架

⭐ **面試高頻點**:「TLS 終止為什麼放邊緣(Nginx / 負載均衡層),而不是讓後端自己解?」

答案框架(口述):

1. **集中管理憑證**:10 個後端 pod 各自配憑證 → 輪換地獄;Nginx 這一台集中接收外部 HTTPS、對內走明文 HTTP 或 mTLS,憑證只在邊緣換。
2. **卸載非對稱運算**:TLS 握手的 RSA/ECDH 非對稱運算 CPU 貴;邊緣硬體/實例多 core 專門跑,後端可以省著用。握手貴的原理(非對稱→協商對稱 session key→後續對稱加密)↪ `gateway/01-reverse-proxy-engine.md`。
3. **統一 TLS 策略**:cipher suite、協議版本、HSTS、OCSP stapling 一處設定,不同後端技術棧不用各自實作。

框架定完,下面全是「怎麼動手」。

---

## 2. 最小可跑的 TLS 設定:憑證、listen、中間鏈

### 2.1 基礎三行指令

```nginx
server {
    listen 443 ssl;
    server_name example.com www.example.com;

    ssl_certificate     /etc/nginx/ssl/fullchain.pem;   # 公鑰憑證(含中間鏈)
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;     # 私鑰(只 Nginx 讀)

    # … 其他設定
}
```

- **`listen 443 ssl`**:告訴 Nginx「這個 socket 收到的連線要先做 TLS 握手」。Nginx 1.15.0+ 的推薦寫法;舊版的 `ssl on;` 已廢棄。
- **`ssl_certificate`**:伺服器公鑰憑證路徑。
- **`ssl_certificate_key`**:對應私鑰路徑。

> **HTTP/2** 要在 listen 指令加 `http2` 參數:
> ```nginx
> listen 443 ssl;
> http2 on;          # Nginx 1.25.1+ 獨立指令;舊版寫 listen 443 ssl http2;
> ```

### 2.2 🔬 中間鏈順序:為什麼順序錯了瀏覽器不報錯但 curl 會炸

TLS 握手時伺服器要把「從自己的憑證一路到根 CA 的鏈」發給客戶端,讓客戶端能驗到它信任的根。

`ssl_certificate` 裡填的 `fullchain.pem` 必須**先放伺服器憑證、再放中間 CA 憑證**,從葉到根方向:

```
# fullchain.pem 的正確順序
-----BEGIN CERTIFICATE-----
[伺服器憑證 — domain.com]
-----END CERTIFICATE-----
-----BEGIN CERTIFICATE-----
[中間 CA — Let's Encrypt R3 / 你的 CA 發的中間憑證]
-----END CERTIFICATE-----
# 根 CA 不必放(瀏覽器/系統有緩存;放了也沒事)
```

**順序填反的後果**:現代瀏覽器通常有「AIA fetching」——憑證裡有個 URL 告訴客戶端去哪取中間鏈,瀏覽器會自動補抓,所以測試時沒問題。但 `curl`、後端服務、部分嵌入式客戶端**不做 AIA fetching**,握手直接失敗。生產環境最安全的做法是用 `openssl s_client -connect domain.com:443 -showcerts` 驗鏈的完整性。

```bash
# 驗鏈完整性(本機無需憑證,看輸出的 chain 段)
openssl s_client -connect example.com:443 -showcerts 2>/dev/null \
  | openssl x509 -noout -subject -issuer
```

---

## 3. SNI:一個 IP、多個域名、各自一張憑證

**SNI(Server Name Indication)**:TLS 握手時,客戶端在 ClientHello 裡就把「目標域名」告訴伺服器,讓伺服器在握手早期就能選對憑證。

**沒有 SNI 的問題**:TLS 握手發生在 HTTP 層之前,伺服器看不到 `Host` 頭,無法用「哪個域名」來選憑證——同一 IP 只能有一張憑證。

**Nginx 上 SNI 的設定方式**:每個 `server` 區塊寫自己的 `server_name` 和 `ssl_certificate`。Nginx 在握手早期讀 ClientHello 裡的 SNI extension,按 `server_name` 路由到對應的 `server` 區塊,使用它的憑證。

```nginx
# 第一個虛擬主機 — api.example.com
server {
    listen 443 ssl;
    server_name api.example.com;

    ssl_certificate     /etc/ssl/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/ssl/api.example.com/privkey.pem;
    # …
}

# 第二個虛擬主機 — shop.example.com
server {
    listen 443 ssl;
    server_name shop.example.com;

    ssl_certificate     /etc/ssl/shop.example.com/fullchain.pem;
    ssl_certificate_key /etc/ssl/shop.example.com/privkey.pem;
    # …
}
```

兩個 `server` 都監聽同一個 `443`,共享同一個 IP,各自用自己的憑證。**Nginx 在握手期間完成 SNI → server 選擇,不需要你寫額外指令**——只要 `server_name` 對得上 SNI extension 裡的主機名,Nginx 自動選對。

> **同一張憑證多域名**:如果一張 SAN 憑證(Subject Alternative Name)已包含多個域名,也可以多個 `server` 引用同一份憑證檔——Nginx 不介意。

---

## 4. 協議版本與 cipher suite:安全基線

### 4.1 協議版本

```nginx
ssl_protocols TLSv1.2 TLSv1.3;
```

- **去掉 TLSv1.0 和 TLSv1.1**:已被 RFC 8996 棄用,有已知攻擊(POODLE、BEAST)。現代環境只留 1.2 和 1.3。
- **TLSv1.3**:握手往返從 2-RTT 降到 1-RTT(甚至 0-RTT 恢復),同時只允許 AEAD cipher,去掉了所有已知弱算法,**比 1.2 更快更安全**。盡量讓客戶端優先走 1.3。

### 4.2 cipher suite

```nginx
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;
```

幾個關鍵點:

- **ECDHE 開頭**:帶 Forward Secrecy(完美前向保密)——即使私鑰將來洩露,過去的 session key 也不能被解。非 ECDHE/DHE 的 cipher 沒有 PFS,**現代設定應排除**。
- **GCM**:AEAD 模式(Authentication + Encryption combined),比 CBC 模式安全。
- **`ssl_prefer_server_ciphers off`**:TLSv1.3 的 cipher 不受此設定影響(它自己管);TLSv1.2 時設 `off` 讓客戶端優先選它更快的 cipher(如支援 CHACHA20 的行動設備),通常比 server 強制選好。傳統建議是 `on`,但 Mozilla SSL Config Generator 的現代模式已改 `off`。

> **參考基線**:用 [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)(`Modern` 模式)產生 Nginx 設定,它會隨主流瀏覽器支援度更新 cipher list——比手寫 cipher 字串更可靠。

---

## 5. HSTS:強制 HTTPS + `add_header` 繼承陷阱的連鎖

### 5.1 HSTS 是什麼

`Strict-Transport-Security`(HSTS)告訴瀏覽器:「這個域名接下來 `max-age` 秒內,不論何種情況一律走 HTTPS——即使用戶敲了 `http://`。」瀏覽器記住這條指令後,下一次根本不發 HTTP 請求,直接在本地升級到 HTTPS。

### 5.2 設定方式

```nginx
server {
    listen 443 ssl;
    server_name example.com;

    ssl_certificate     /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    #                                               ↑ 約兩年
    #                                                                ↑ 子域名一起
    #                                                                               ↑ 可申請進 Chrome 硬編碼清單
}
```

- **`max-age`**:單位秒;`63072000` = 2 年是多數瀏覽器 HSTS preload 的最低要求。
- **`includeSubDomains`**:所有子域名同樣強制 HTTPS。確認子域名都有效憑證再開,否則子域名的 HTTP 服務會被瀏覽器直接擋掉。
- **`preload`**:申請進 Chrome/Firefox 硬編碼 HSTS 清單——瀏覽器還沒訪問過你的域名也直接走 HTTPS。需要先上 [hstspreload.org](https://hstspreload.org) 申請。
- **`always`**:不加 `always` 時 `add_header` 只作用於 2xx/3xx;錯誤回應(4xx/5xx)不帶頭。HSTS 需要在**所有回應**上帶,包括錯誤頁,所以 **`always` 必填**。

### 5.3 🔬 `add_header` 繼承陷阱在 HSTS 上的連鎖(回扣 ch01)

這是 ch01 第 2.2 節講的陷阱在 TLS 配置裡最常爆的現場:

```nginx
server {
    # 在 server 層設 HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options "DENY" always;

    location /api/ {
        # 只是想多一個 API 追蹤頭
        add_header X-Request-Id $request_id always;   # ← 這一行殺死了上面兩個頭!
        proxy_pass http://backend;
    }
}
```

**結果**:訪問 `/api/` 時回應只有 `X-Request-Id`,**HSTS 和 X-Frame-Options 靜默消失**。安全掃描工具會標記這個 endpoint 缺少 HSTS。

**正確做法**:在出現 `add_header` 的 `location` 裡**重抄**或用 `include` 片段:

```nginx
# security-headers.conf
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
```

```nginx
server {
    listen 443 ssl;
    server_name example.com;
    ssl_certificate     /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    include /etc/nginx/security-headers.conf;   # server 層保底

    location /api/ {
        include /etc/nginx/security-headers.conf;  # 重新 include,同時補 server 層的
        add_header X-Request-Id $request_id always;
        proxy_pass http://backend;
    }
}
```

> **口訣(面試用)**:子層只要出現一條 `add_header`,父層所有 `add_header` 全部失效——HSTS 最常在這裡悄悄消失。對策:`include` 安全頭片段,或把所有 `add_header` 統一放在最深的那一層。

---

## 6. 🔬 OCSP Stapling:省客戶端一次驗證往返

### 6.1 問題:OCSP 查詢讓 TLS 握手多一次網路往返

瀏覽器收到伺服器憑證後,要確認「這張憑證有沒有被 CA 吊銷」。傳統做法是讓**客戶端**去 CA 的 OCSP(Online Certificate Status Protocol)端點查詢:

```
客戶端  ──握手──►  伺服器
客戶端  ──OCSP 查詢──►  CA 的 OCSP 端點  ──回應──►  客戶端
客戶端驗完,HTTPS 連線才真正建立完成
```

這多了**一次客戶端到 CA 的 RTT**,可能是跨洲際的慢速查詢。更糟的是:如果 CA 的 OCSP 服務器掛掉或超時,部分客戶端會「soft-fail」(繼續,不安全)、部分會「hard-fail」(拒絕,影響用戶)。

### 6.2 OCSP Stapling 如何解決

OCSP Stapling 讓**伺服器(Nginx)**去 CA 預取 OCSP 回應,定期快取,握手時**附帶(staple)**給客戶端:

```
Nginx  ──定期去 CA 取 OCSP 回應──►  CA OCSP 端點
                                     快取在本地(幾小時到幾天)

客戶端  ──握手──►  Nginx(TLS ServerHello + 憑證 + stapled OCSP 回應一起送回)
客戶端驗 OCSP 回應的 CA 簽章,無需自己再出去查
```

**省掉的是客戶端那一次往返**:查詢的工作從每個客戶端自己做,變成 Nginx 集中做、快取結果、分發給所有客戶端。

### 6.3 Nginx 設定

```nginx
http {
    # resolver 用來讓 Nginx 解析 CA OCSP 端點的域名(必填)
    resolver 8.8.8.8 1.1.1.1 valid=300s;
    resolver_timeout 5s;
}

server {
    listen 443 ssl;
    server_name example.com;

    ssl_certificate     /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    ssl_stapling on;                        # 開啟 OCSP stapling
    ssl_stapling_verify on;                 # Nginx 也驗 OCSP 回應的簽章(確保沒被篡改)
    ssl_trusted_certificate /etc/nginx/ssl/chain.pem;  # 用於驗 OCSP 回應的 CA 鏈
    #                         ↑ 有時與 fullchain 相同;Let's Encrypt 的 chain.pem 只含中間鏈
}
```

**指令說明**:

| 指令 | 作用 |
|---|---|
| `ssl_stapling on` | 讓 Nginx 取 OCSP 回應並 staple 到握手裡 |
| `ssl_stapling_verify on` | Nginx 在 staple 前驗 OCSP 回應的 CA 簽章(推薦打開;否則 Nginx 盲目附帶未驗證的回應) |
| `ssl_trusted_certificate` | 驗 OCSP 回應所需的 CA 鏈憑證(通常是你的中間 CA 鏈;Let's Encrypt 的 fullchain 已含) |
| `resolver` | Nginx 用來解析 OCSP 端點 URL 的 DNS;**必須配**,否則 Nginx 找不到 CA 的 OCSP 服務器 |

**驗證 stapling 有沒有生效**:

```bash
openssl s_client -connect example.com:443 -status 2>/dev/null \
  | grep -A 6 "OCSP response:"
# 有 "OCSP Response Status: successful" 表示 stapling 工作正常
```

---

## 7. Session 復用:省重複握手的 CPU + RTT

### 7.1 問題:每個新 TCP 連線都要完整 TLS 握手

TLS 握手(ClientHello → ServerHello → Certificate → key exchange → Finished)至少 1-RTT(TLS 1.3)或 2-RTT(TLS 1.2),且包含非對稱加密運算。同一用戶在頁面上打開幾十個子資源請求、每個都做完整握手——浪費。

**握手為什麼貴的原理**:非對稱 → 對稱協商過程,↪ `gateway/01-reverse-proxy-engine.md`。

### 7.2 兩種復用機制

**Session Cache(服務端存 session)**:

```nginx
ssl_session_cache   shared:SSL:10m;     # 10 MB 共享 cache,跨 worker 可用;約存 4 萬個 session
ssl_session_timeout 1d;                  # session 保留 1 天
```

Nginx 把 session 狀態存在共享記憶體 zone(跨 worker 可見)。客戶端下次連線時帶 session ID → Nginx 查到 → 跳過完整握手,直接進應用資料階段。

- **優點**:伺服器控制、可集中吊銷。
- **缺點**:多台 Nginx 需要同步(多實例場景 session 可能在別台機器上找不到)。

**Session Tickets(客戶端存加密 token)**:

```nginx
ssl_session_tickets on;      # 默認開啟;讓 Nginx 把 session 狀態加密後發給客戶端
```

Nginx 把 session 狀態用 ticket key 加密後塞進 `session ticket` TLS 擴展發給客戶端。下次客戶端直接帶這個 ticket 回來,Nginx 解密後直接恢復 session——**服務端不用存任何東西**。

- **優點**:服務端無狀態,多實例天然共享(只要 ticket key 相同)。
- **缺點**:如果 ticket key 洩露,過去的 session 可能被解;為保持 Forward Secrecy,**ticket key 要定期輪換**(推薦每 24 小時,Nginx 默認自動輪換,但多實例需要同步 key)。

**生產建議**:兩者可以同時開。session cache 作為主力(多 worker 跨 CPU 共用),tickets 作為補充(跨實例)。如果你有多台 Nginx 且不想同步 ticket key,關掉 tickets 只用 cache + sticky session。

---

## 8. HTTP → HTTPS 重導

用戶習慣直接打 `http://`,你需要把他們重導到 HTTPS:

```nginx
# 專門的 HTTP server 區塊:只做重導
server {
    listen 80;
    server_name example.com www.example.com;

    # 若有 Let's Encrypt webroot 驗證需求,先放行 .well-known
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # 其他一律 301 跳 HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}
```

幾個細節:

- **`return 301`**:永久重導,瀏覽器會記住,下次直接走 HTTPS。開發/測試期間可用 `302`(臨時),以免瀏覽器快取了錯誤的目標。
- **`$host$request_uri`**:保留原始 Host(含子域名)和完整請求路徑+query。不要直接寫死 `https://example.com$request_uri`——多域名場景 `$host` 更正確。
- **HSTS + 301 的聯動**:有了 HSTS 後,瀏覽器在 HSTS 有效期內根本不會發 HTTP 請求——這個 301 `server` 只是給「沒有 HSTS 快取的首次訪問」或「非瀏覽器工具」用的。

---

## 9. mTLS:雙向驗證

一般 TLS 只驗伺服器(客戶端確認伺服器是誰)。**mTLS(Mutual TLS)**再加上「伺服器也驗客戶端」——要求客戶端也出示客戶端憑證。

**常用場景**:服務間 API 認證(不走 API key,走憑證)、企業內部 Zero Trust 閘道、B2B 夥伴 API。mTLS 的概念與鑑權架構 ↪ `gateway/04-edge-authn-authz.md`。

```nginx
server {
    listen 443 ssl;
    server_name api.example.com;

    ssl_certificate     /etc/nginx/ssl/server-fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/server-privkey.pem;

    # mTLS:要求客戶端出示憑證,並用這個 CA 憑證驗它
    ssl_verify_client      on;                                 # 強制驗客戶端憑證
    ssl_client_certificate /etc/nginx/ssl/client-ca.pem;      # 信任的 CA 憑證(簽發客戶端憑證的那個 CA)
    ssl_verify_depth       2;                                  # 驗鏈深度(有中間 CA 就要 >= 2)

    location / {
        # 客戶端憑證驗過後,把 CN/DN 傳給後端讓後端知道是誰
        proxy_set_header X-Client-Cert-CN  $ssl_client_s_dn_cn;
        proxy_set_header X-Client-Cert-DN  $ssl_client_s_dn;
        proxy_pass http://backend;
    }
}
```

**關鍵指令**:

| 指令 | 作用 |
|---|---|
| `ssl_verify_client on` | 要求客戶端送憑證;客戶端不送或憑證無效 → `400 No required SSL certificate was sent` |
| `ssl_verify_client optional` | 客戶端可以不送憑證;後端用 `$ssl_client_verify` 判斷有無驗成功(`SUCCESS`/`FAILED`/`NONE`) |
| `ssl_client_certificate` | 信任的 CA 憑證檔(簽發**客戶端**憑證的 CA;不是伺服器憑證的 CA) |
| `ssl_verify_depth` | 驗客戶端憑證鏈的最大深度;有中間 CA 就要設 >= 2 |

**有用的 mTLS 內建變數**:

| 變數 | 含義 |
|---|---|
| `$ssl_client_verify` | `SUCCESS` / `FAILED:reason` / `NONE` |
| `$ssl_client_s_dn_cn` | 客戶端憑證的 Subject Common Name |
| `$ssl_client_s_dn` | 完整 Subject DN(Distinguished Name) |
| `$ssl_client_serial` | 序號 |
| `$ssl_client_fingerprint` | SHA-1 fingerprint |

---

## 10. Let's Encrypt / certbot:自動化簽發與續期

### 10.1 兩種驗證模式

Let's Encrypt 要先驗你「確實控制這個域名」,再簽憑證。Nginx 常用兩種模式:

**webroot 模式**:certbot 把驗證檔案放到指定目錄,Let's Encrypt CA 用 HTTP 來抓:

```bash
# 安裝 certbot(Ubuntu 示例)
sudo apt install certbot

# 簽發(--webroot:把挑戰文件放到指定目錄)
sudo certbot certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  -d example.com -d www.example.com \
  --email admin@example.com \
  --agree-tos
```

Nginx 設定要放行 `.well-known/acme-challenge/`:

```nginx
server {
    listen 80;
    server_name example.com www.example.com;

    # 驗證路徑:certbot 的文件放在 /var/www/certbot/.well-known/acme-challenge/
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}
```

**`--nginx` 自動模式**:certbot 直接修改你的 Nginx 設定自動配 TLS:

```bash
sudo certbot --nginx -d example.com -d www.example.com
```

certbot 會:自動修改 `server` 區塊加上 `ssl_certificate` 路徑、加重導規則。方便,但 Nginx 設定被自動改過後可讀性可能下降;**生產環境建議用 webroot 模式手動管設定、只讓 certbot 負責簽/續期憑證。**

### 10.2 自動續期

Let's Encrypt 憑證有效期 90 天,certbot 有個系統計時器/cron job 自動續期:

```bash
# 測試續期流程(dry-run,不真正簽)
sudo certbot renew --dry-run

# 正式設定(certbot 安裝時通常已自動加 systemd timer 或 cron)
# 檢查 systemd timer
systemctl status certbot.timer

# 或 cron(每天兩次,certbot 只有快過期才真正續)
0 0,12 * * * certbot renew --quiet && nginx -s reload
```

**續期後要 reload Nginx 才能載入新憑證**:certbot 的 `--deploy-hook` 可以在成功續期後自動觸發:

```bash
sudo certbot renew --deploy-hook "nginx -s reload"
```

### 10.3 `.well-known/acme-challenge/` 內幕

驗證流程:

```
certbot  ──在 /var/www/certbot/.well-known/acme-challenge/<token> 放一個臨時文件──►
Let's Encrypt CA  ──發 HTTP GET http://example.com/.well-known/acme-challenge/<token>──►  Nginx
Nginx  ──從 /var/www/certbot/ 找到文件──►  CA
CA 確認文件存在 → 簽發憑證
```

**注意**:DNS 必須真實解析到你的 Nginx 所在的 IP;防火牆的 80 埠必須對外開放(CA 從外部發 HTTP 請求)。

---

## 11. 完整生產設定彙整

```nginx
# /etc/nginx/conf.d/example.com.conf

# HTTP → HTTPS 重導 + ACME 驗證放行
server {
    listen 80;
    server_name example.com www.example.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS 主設定
server {
    listen 443 ssl;
    http2 on;
    server_name example.com www.example.com;

    # 憑證(含中間鏈)
    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    # 協議與 cipher
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305;
    ssl_prefer_server_ciphers off;

    # Session 復用
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;   # 關閉 tickets:多實例同步 key 麻煩;只用 cache + 確保 sticky

    # OCSP Stapling
    ssl_stapling        on;
    ssl_stapling_verify on;
    ssl_trusted_certificate /etc/letsencrypt/live/example.com/chain.pem;
    resolver            8.8.8.8 1.1.1.1 valid=300s;
    resolver_timeout    5s;

    # 安全頭(用 include 讓 location 層可以重 include 不丟頭)
    include /etc/nginx/security-headers.conf;

    location / {
        include /etc/nginx/security-headers.conf;
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

`/etc/nginx/security-headers.conf`:

```nginx
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

---

## 交叉引用

- **TLS 握手為何貴(非對稱 → 對稱協商)、TLS 終止放邊緣的取捨**:↪ `gateway/01-reverse-proxy-engine.md`(本章只講 Nginx 設定,不重推導)。
- **mTLS 鑑權架構、JWT vs mTLS 的選型**:↪ `gateway/04-edge-authn-authz.md`(本章只講 Nginx 的 `ssl_verify_client` 設定)。
- **`add_header` 繼承陷阱的原理**:↪ `nginx/01-config-model.md` §2.2。
- **HTTP → HTTPS 重導的 `return 301` 語法**:↪ `nginx/02-rewrite-and-internal-redirect.md`。
- **反向代理後端設定(`proxy_pass`、`proxy_set_header`、upstream)**:↪ `nginx/04-reverse-proxy-and-upstream.md`。

---

## 本章小結

- **最小設定三行**:`listen 443 ssl` + `ssl_certificate`(fullchain,葉→中間鏈順序)+ `ssl_certificate_key`。
- **SNI**:同一 IP 多域名,每個 `server` 區塊寫自己的 `server_name` + 憑證,Nginx 在握手期自動路由。
- **協議**:`ssl_protocols TLSv1.2 TLSv1.3`,去掉 1.0/1.1;cipher 選 ECDHE 系列(Forward Secrecy)。
- **HSTS**:`add_header Strict-Transport-Security ... always`——`always` 讓錯誤頁也帶頭;子層 `add_header` 一出現就丟掉父層所有 `add_header`,用 `include` 片段解決。
- **OCSP Stapling**:Nginx 集中去 CA 預取吊銷狀態,staple 進握手回應——省客戶端一次往返,`resolver` 必填。
- **Session 復用**:`ssl_session_cache shared:SSL:10m`(跨 worker)+ `ssl_session_timeout 1d`;tickets 在多實例場景需同步 key,否則關掉。
- **HTTP → HTTPS**:獨立 `listen 80` `server`,`return 301 https://$host$request_uri;`。
- **mTLS**:`ssl_verify_client on` + `ssl_client_certificate`(客戶端 CA);用 `$ssl_client_s_dn_cn` 傳客戶端身份給後端。
- **Let's Encrypt**:webroot 模式更可控;`--deploy-hook "nginx -s reload"` 確保續期後憑證生效。

---

## 章末問答(複習自檢,答案要點都在前面正文)

1. `ssl_certificate` 裡的 fullchain.pem 應該按什麼順序放憑證?順序填反了為什麼瀏覽器沒報錯但 `curl` 會失敗?

2. 同一台 Nginx 同一個 IP 上,如何讓 `api.example.com` 和 `shop.example.com` 各用不同的憑證?Nginx 在 TLS 握手的哪個階段做這個決定?

3. **面試高頻**:OCSP Stapling 解決了什麼問題?省掉的是哪一方的哪一次往返?設定時 `resolver` 指令的作用是什麼?

4. `ssl_session_cache shared:SSL:10m` 裡的 `shared` 是什麼意思?session tickets 在多實例場景有什麼風險?

5. `add_header Strict-Transport-Security ... always` 裡的 `always` 去掉有什麼後果?如果 `server` 層設了 HSTS,某個 `location` 又加了一條 `add_header`,HSTS 還在嗎?怎麼解?

6. `ssl_verify_client on` 和 `ssl_verify_client optional` 的行為差異?如何在後端取得客戶端憑證的 Common Name?

7. **面試高頻**:TLS 終止為什麼放邊緣(Nginx 層)而不是讓後端各自做?列出三個理由。

8. Let's Encrypt webroot 模式的驗證流程是什麼?Nginx 設定裡要放行哪個路徑?續期後為什麼還需要 `nginx -s reload`?
