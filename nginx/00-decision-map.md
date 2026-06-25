# 00 · 決策地圖:Nginx 的四種身份、何時別用

> 一句話定位:Nginx 是一台**事件驅動的代理引擎**,你要學的是怎麼駕馭它——認清它能扮演哪四種角色、什麼場景選它、什麼場景該換別的。

---

## 1. Nginx 的四種身份

Nginx 是多面手,同一個程序可以同時扮演以下角色(甚至混搭在同一份設定裡):

| 身份 | 核心能力 | 本 track 對應章 |
|---|---|---|
| **Web Server** | 提供靜態檔案服務、FastCGI(php-fpm)、壓縮/快取頭/Range 斷點續傳 | ch03 |
| **反向代理** | `proxy_pass` 把請求轉給後端、必設 header、超時三件套、upstream 連線池 | ch04 |
| **負載均衡器** | `upstream` 區塊設定多後端、權重/`least_conn`/`ip_hash`、被動健康檢查 | ch04 |
| **邊緣腳本台** | 掛 OpenResty/Lua 在 phase 做動態鑑權/複雜路由/調外部服務 | ch11 |

> **注意:四種身份不是互斥的。** 生產環境裡最常見的是「反向代理 + 負載均衡 + TLS 終止」三合一配置,靜態資源也可以直接回,再掛上限流(ch06)和快取(ch05),就是一個完整的接入層。

### 身份一:Web Server

Nginx 的起點。`listen 80; root /var/www/html;` 三行就能跑。

核心優勢:`sendfile` 系統呼叫把靜態檔案**從磁碟直接送到 socket buffer、不過用戶態記憶體**,零拷貝高效。大流量靜態站(前端 SPA、CDN 回源站)是它的主場。

FastCGI 橋:把動態請求(PHP、Python WSGI)轉給後端進程,比直接用 Apache mod_php 輕。

### 身份二:反向代理

Nginx 最常見的用法。客戶端以為在和 `api.example.com` 說話,其實 Nginx 在背後把請求轉給後端服務(Node.js / Go / FastAPI / Spring Boot 都行)。

Nginx 自己不懂業務,它只負責:接客戶端連線、轉發、傳回應、處理超時。引擎內幕(epoll 事件迴圈、upstream 連線池)已在 `gateway/01` 講透,本 track 只講怎麼配。

↪ 引擎內幕:為什麼一台 Nginx 能扛住幾萬連線 → [`gateway/01-reverse-proxy-engine.md`](../gateway/01-reverse-proxy-engine.md)

### 身份三:負載均衡器

`upstream` 區塊 + 多個 `server` 指令,Nginx 就變成 L7 LB。

```nginx
upstream backend {
    least_conn;
    server 10.0.0.1:8080 weight=2;
    server 10.0.0.2:8080;
    server 10.0.0.3:8080 backup;  # 其他全掛才上
    keepalive 32;                  # 對後端保持長連線池
}
```

常用策略:`round-robin`(默認)/ `least_conn`(活躍連線最少的先接)/ `ip_hash`(客戶端 IP 固定打到同一台,做 session 親和)。被動健康檢查:`max_fails=3 fail_timeout=30s`——連續失敗三次就暫時下線 30 秒。

↪ LB 演算法本身(一致性哈希/P2C/權重隨機)→ [`system-design/05-服務治理設施.md`](../system-design/05-服務治理設施.md)

### 身份四:邊緣腳本台(OpenResty)

純 Nginx 設定是**宣告式**的:你告訴它「`/api/` 轉到這個 upstream」,但你沒法在設定裡寫「如果 Redis 裡這個 key 不存在就 403」。

OpenResty 把 LuaJIT 嵌進 Nginx 的請求處理 phase:

```
rewrite_by_lua → access_by_lua → content_by_lua → header_filter_by_lua
```

可以在 `access_by_lua` 裡查 Redis 做動態鑑權、讀取請求體決定路由、呼叫外部 HTTP 服務——把「代理引擎」升級成「可程式化接入層」。APISIX 本身就是基於 OpenResty 的。

↪ 詳見 ch11 外圈章。

---

## 2. 心智模型:「設定即程式」

理解 Nginx 設定最重要的一句話:**它是宣告式的、靠區塊繼承的、reload 才生效的。**

### 宣告式

你不寫「處理請求的步驟」,你寫「在什麼條件下,這個請求應該怎麼被處理」。`location /api/ { proxy_pass http://backend; }` 意思是:「所有命中 `/api/` 的請求,轉給 backend。」

### 區塊繼承

設定指令從外向內繼承:

```
main → events → http → server → location
```

`http` 裡設的 `gzip on;` 對所有 `server` 和 `location` 生效,除非內層覆蓋。父層的值是默認,子層可以覆蓋。

有一個陷阱:`add_header` **不是簡單追加**——一旦子層出現任何 `add_header`,父層的 **所有** `add_header` 都被丟掉(不是合并,是替換)。這是初學者最常踩的坑之一,ch01 會詳講。

### reload 才生效

改了 `nginx.conf` 必須 `nginx -s reload`(或 `systemctl reload nginx`)才生效——Nginx 是靜態設定模型,沒有「熱更新 API」。這是它和 Envoy/APISIX 的最大區別之一。

好處:設定是版本控制友善的文件,不存在「設定與實際運行狀態不一致」的問題。

壞處:每次改路由/上下游/限流配額都要 reload(雖然 reload 很安全,見 ch08)。

---

## 3. 何時別用 Nginx(避免過度設計)

Nginx 不是萬能的,以下場景有更好的工具:

### 情況一:雲託管 LB/CDN 已經夠用

如果你在 AWS / GCP / Azure 上,ALB(Application Load Balancer)已經提供:HTTPS 終止、路徑/主機路由、健康檢查、自動擴縮、WAF 整合。**再在 EC2 上自己跑 Nginx 做同樣的事,是純粹的運維負擔。**

除非你需要 Nginx 特有的能力(複雜的 `location` 路由邏輯、`proxy_cache`、自訂 header 操作),否則雲 LB 夠了。

### 情況二:需要動態配置/服務發現/豐富外掛

Nginx 的「reload 才生效」意味着:後端服務的 IP 變了(Kubernetes Pod 重建)、要新增一條限流規則——你得改設定檔然後 reload。在容器/微服務環境裡,這很麻煩。

這時應該考慮:

- **Envoy**:設計上就是「動態配置驅動」(xDS API),適合服務 mesh 場景。Istio/Linkerd 都以 Envoy 為資料面。
- **APISIX**:基於 OpenResty,有管理 API 和控制台,路由/插件/限流配額可以在不 reload 的情況下動態修改。適合 API 網關場景。

↪ 完整網關選型(Envoy/APISIX/Kong/雲託管對照)→ [`gateway/11-selection-and-production-playbook.md`](../gateway/11-selection-and-production-playbook.md)
↪ xDS 動態配置、控制面/資料面分離 → [`gateway/08-gateway-as-distributed-system.md`](../gateway/08-gateway-as-distributed-system.md)

### 情況三:想省掉 TLS 運維,可考慮 Caddy

讓 Nginx 自動管理憑證需要配 certbot + cron + 設定更新。**Caddy** 默認就會自動從 Let's Encrypt 申請憑證、自動續期、自動 HTTPS——設定極簡。

如果你的場景就是「一台 VPS 跑幾個站、不想管憑證」,Caddy 比 Nginx + certbot 省事得多。

↪ 選型對照完整版 → ch12

### 決策速查

```
你需要什麼?                                建議
────────────────────────────────────────────────────────
靜態服務 / 反代 / LB / TLS(自己管)       → Nginx(本 track 就是教這個)
雲上 HTTPS 終止 + 路徑路由                → 雲 ALB/API Gateway
動態配置 / 服務發現 / 插件生態             → Envoy / APISIX
自動 TLS + 簡單設定                       → Caddy
L4 LB + 極致穩定性                        → HAProxy
API 網關 + 認證/限流/開發者門戶           → Kong / APISIX / 雲 API Gateway
```

---

## 4. 面試高頻點

**「Nginx 能幹嘛?」**

> 四種身份:web server(靜態/FastCGI)、反向代理、負載均衡、邊緣腳本台(OpenResty)。核心是事件驅動引擎(master-worker + epoll),設定是宣告式的區塊繼承模型,reload 才生效。

**「Nginx 不該拿來幹嘛?」**

> 三個場景:1. 雲 LB 已夠用時別疊床架屋;2. 需要動態配置/服務發現/插件生態時換 Envoy 或 APISIX;3. 只想省 TLS 運維可換 Caddy。Nginx 的「設定檔+reload」模型在容器/微服務場景下配置管理成本高是硬傷。

---

## 5. 本章小結

- Nginx 有四種身份:web server / 反向代理 / LB / 邊緣腳本台——生產環境常混搭。
- 心智模型:宣告式設定 + 區塊繼承 + reload 才生效;`add_header` 繼承不是追加而是替換。
- 何時別用:雲 LB 夠用時、需要動態配置時上 Envoy/APISIX、只想省 TLS 管理時考慮 Caddy。
- 本 track 只教「Nginx 怎麼動手」;凡「引擎為什麼這樣」一律 ↪ 指回 `gateway/` 深礦。

---

## 6. 章末問答

**Q1.** Nginx 的 master 進程和 worker 進程各負責什麼?為什麼 master 不處理請求?

<details>
<summary>答案要點</summary>

master 以 root 啟動,負責讀設定、bind/listen 特權埠、fork 管理 worker、處理訊號(reload/熱升級)。它不碰業務請求,攻擊面小。worker 是實際處理連線的進程,數量 = CPU 核數,以非特權用戶跑,靠事件迴圈單線程服務海量連線。

</details>

**Q2.** 為什麼說 Nginx 的「reload 才生效」在容器/微服務場景是缺點?有什麼替代方案?

<details>
<summary>答案要點</summary>

容器環境下 Pod IP 頻繁變動,每次後端拓撲變化都要改 nginx.conf 然後 reload,管理負擔大且有一定延遲。替代方案:Envoy(xDS API 動態推送路由)或 APISIX(管理 API 動態配置)能做到不 reload 的熱更新。

</details>

**Q3.** 同一份 Nginx 設定能同時扮演「靜態 web server + 反向代理 + 負載均衡」嗎?怎麼做到?

<details>
<summary>答案要點</summary>

可以。同一個 `server` 區塊裡:`location /static/` 用 `root`/`alias` 直接回靜態檔;`location /api/` 用 `proxy_pass` 轉到 `upstream` 區塊;`upstream` 裡配多台後端就是 LB。三種身份在一個 server 裡共存。

</details>

**Q4.** `add_header` 的繼承行為是什麼?為什麼容易踩坑?

<details>
<summary>答案要點</summary>

`add_header` 不是追加:一旦子層(`server` 或 `location`)出現任何 `add_header` 指令,父層的所有 `add_header` 都被丟棄(替換語義,非合并)。踩坑場景:在 `http {}` 設了 `add_header X-Frame-Options DENY;`,在某個 `location {}` 加了 `add_header Cache-Control "no-cache";`,結果 `X-Frame-Options` 消失了。解法:在需要的每個子層把所有 header 都寫全。

</details>

**Q5.** 面試問「Nginx 和 Envoy 各自什麼場景」你怎麼答?

<details>
<summary>答案要點</summary>

Nginx:設定穩定、手工或 CI/CD 管理、靜態服務/反代/TLS 終止是主場;適合中小規模、設定不頻繁變動的場景。Envoy:為動態配置設計,xDS API 讓控制面(Istio 等)實時推路由/限流規則,不需要 reload;適合大規模微服務/service mesh、需要精細可觀測性和插件的場景。兩者不是競爭而是定位不同:Nginx 是「手藝工具」,Envoy 是「雲原生資料面基礎設施」。

</details>
