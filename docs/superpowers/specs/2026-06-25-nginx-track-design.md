# `nginx/` Track 設計 Spec — Nginx 這門手藝(配置 / 運維 / 調優 / 救火)

- 日期:2026-06-25
- 狀態:設計已批准,待寫 implementation plan
- 語言:**繁體中文**(技術名詞、指令、設定保留英文)
- 落點:倉庫根目錄新建獨立 track `nginx/`,與 `gateway/`、`cloud-native/`、`concurrency-capacity/` 平級
- 姊妹 track:`gateway/`(2026-06-23 完成)。本 track **坐在 `gateway/` 之上**,引擎內幕一律 ↪ 指過去,不重寫。

---

## 1. 動機與定位

倉庫現況:**`gateway/` 已把「代理引擎為什麼快」講透了**(master-worker、epoll 事件迴圈、upstream 連線池、TLS 終止、L4-vs-L7,見 `gateway/01`),它用 Nginx 當解剖標本,但它的視角是**網關抽象**——Nginx 只是舉例,它**故意不教 Nginx 這個工具本身**。

於是有一塊真空:**Nginx 作為「日常要動手用的一門手藝」完全沒有系統文件**。散落的提及只有 `network/http.md`、`frontend/cross-origin/`(CORS 配 Nginx)、`performance-tuning-roadmap`(零星調優),都不成體系。

具體缺什麼(資深/架構師面試 + 日常工作都要,`gateway/` 都沒覆蓋):

- **設定模型本身** — `server`/`location` 區塊、指令繼承、`location` 匹配優先級(`=` / `^~` / 正則 / 前綴的順序)、`rewrite`/`return`、內建變數、`if` 的坑。
- **Nginx 各角色** — 靜態 web server、FastCGI/php-fpm、`proxy_cache` 快取、`limit_req`/`limit_conn` 在 Nginx 層限流的真實寫法。
- **運維** — `reload` 訊號機制、零停機二進制熱升級、優雅退出、日誌切割。
- **調優** — `worker_connections`、`sendfile`/`tcp_nopush`、buffer/timeout、keepalive、`reuseport` 到底調哪個、和內核參數怎麼聯動。
- **除錯 playbook** — 502/504/499 各是什麼、連線耗盡怎麼定位。
- **外圈** — OpenResty/Lua、ingress-nginx(k8s)。

本 track 補的就是這塊「Nginx 手藝」缺口。

### 核心心智模型(整個 track 的脊柱)

> **`gateway/` 教你「這台引擎為什麼快」;`nginx/` 教你「怎麼用這台引擎幹活、調它、救它」。**

```
   gateway/01  ─────────────►  nginx/  (本 track)
   引擎內幕                      手藝實戰
   ┌──────────────┐            ┌────────────────────────────────┐
   │ master-worker │            │ 怎麼寫 location / rewrite        │
   │ epoll 事件迴圈 │   坐在     │ 怎麼配 proxy_cache / limit_req   │
   │ upstream 連線池│   ──上──►  │ 怎麼平滑 reload / 熱升級          │
   │ TLS 終止       │            │ 怎麼調 worker / buffer / 內核     │
   │ L4 vs L7      │            │ 怎麼讀 log 定位 502/504/連線耗盡 │
   └──────────────┘            └────────────────────────────────┘
   「為什麼快」(↪ 指過來)        「怎麼動手」(本 track 自擁)
```

## 2. 目標讀者與深度

- 讀者:本人(5 年+ Java/Go 後端,正轉 Python/LLM,面試導向自學;Nginx 用過但不系統)。
- 深度:**資深/架構師級**。🔬 標記的章自帶「黑盒裡發生什麼」內幕層(訊號怎麼讓 worker 平滑收工、快取 key 怎麼算、reload 為什麼不丟連線),不停在「貼一段設定」。
- 廣度:覆蓋 Nginx 四種身份(web server / 反向代理 / 負載均衡 / 邊緣腳本台)的日常工作面 + 高頻面試點。
- 生態:**生態平衡**,選型章不綁 Java;雲原生/語言無關為默認;對照工具(Caddy/Envoy/HAProxy/APISIX/雲託管)只在真主流處當錨點。
- 教法:底層內幕寫進正文教學;公式/規則先在敘事裡教全(不在前面挖空);章末問答只做複習自檢,不承載新知識。
- 雙層:每章先講方法論/內幕 → 再轉成面試話術(白板答法);`99` 卡片做最後彙整。

## 3. 整合策略(查重結果 + 與現有內容的邊界)

**本 track 自己擁有(新寫,深度所在,全倉空白):**

1. **Nginx 設定語言模型** — 區塊/繼承、`location` 匹配優先級、`rewrite`/`return`/內部跳轉。
2. **Nginx 各角色實戰** — 靜態服務、FastCGI、`proxy_cache`、`limit_req`、TLS 設定。
3. **Nginx 運維內幕** — 訊號表、`reload` 平滑機制、熱升級二進制(USR2+WINCH)、優雅退出、日誌切割。
4. **Nginx 調優與除錯 playbook** — 參數聯動、`reuseport`、499/502/504 診斷、連線耗盡定位。

**其餘一律交叉引用現有深礦,不重寫**(與 `gateway/`、`system-design` 當 master 索引「指進深礦不重寫」同一玩法):

| 主題 | 現有位置 | 本 track 態度 |
|---|---|---|
| 引擎內幕(epoll/master-worker/事件迴圈/連線池/TLS 為何貴/L4-L7) | `gateway/01` | ↪ 指路,**不重寫**;本 track 只講「怎麼配/調這些」 |
| 請求管線 / filter chain 抽象 | `gateway/02` | ↪ 指路;Nginx 的 phase(rewrite/access/content)在 `01`/`02` 落地成具體設定 |
| 限流/熔斷/降級**演算法本身** | `system-design/01`、`distribution/限流算法/` | ↪ 指路;`06` 只講 Nginx `limit_req`/`limit_conn` 的配置與行為 |
| 分散式限流(Redis/Lua 原子) | `redis-handson/13-rate-limiting/`、`gateway/05` | ↪ 指路;`06` 講「Nginx 本地限流的邊界、何時要外移到分散式」 |
| 負載均衡 L4/L7 **演算法**(輪詢/最少連線/一致性哈希) | `system-design/05-服務治理設施.md` | ↪ 指路;`04` 只講 Nginx `upstream` 配置/權重/健康檢查 |
| 認證 vs 授權概念 / JWT / mTLS 概念 | `system-design/10`、`gateway/04` | ↪ 指路;`07` 只講 Nginx TLS 設定實戰(憑證/SNI/OCSP/session) |
| mesh / 控制面 / xDS / 熱更新抽象 | `gateway/08`、`gateway/09`、`cloud-native-landscape/04` | ↪ 指路;`11` 只講 ingress-nginx 落地 |
| k8s 網路 / Ingress / Gateway API / eBPF | `cloud-native/05-networking.md`、`cloud-native-landscape/03` | ↪ 指路;`11` 只補「Ingress 資源 → Nginx config」這一跳 |
| epoll / 事件模型**內核實現** | `performance-tuning-roadmap/00-os-fundamentals/`、`python-concurrency/00` | ↪ 指路 |
| 內核參數 / ulimit / TCP 調優 | `performance-tuning-roadmap/00-os-fundamentals/04*` | ↪ 指路;`09` 補「Nginx 參數與內核參數怎麼聯動」 |
| 一般可觀測性 / 日誌教學 | `observability/`、`logging/` | ↪ 指路;`10` 只講 Nginx access/error log、`stub_status`、debug log |
| HTTP 協議 / CORS 細節 | `network/http.md`、`frontend/cross-origin/` | ↪ 指路 |
| 網關抽象 / 選型(Envoy/Kong/APISIX)/ AI 網關 | `gateway/00`–`gateway/11` | ↪ 指路;`12` 只從「Nginx 視角:何時該從 Nginx 畢業」切入 |

**與 `gateway/` 的關係結論**:`gateway/` 是「網關抽象」主角、Nginx 是其配角;`nginx/` 反過來,Nginx 是主角、抽象指回 `gateway/`。兩者互補不重疊:凡是「為什麼」「抽象演化」「演算法」歸 `gateway/` 與深礦,凡是「Nginx 怎麼動手」歸本 track。

## 4. 章節目錄(00–12 + 卡 + 4 lab + README)

檔名用英文 slug(可移植,對齊 `gateway`/`cloud-native`),內容繁體。標記:🔬=本章自擁內幕,↪=交叉引用,🧪=lab,⭐=面試主戰場。

### 地基段(Nginx 是什麼 + 設定語言)

**`00-decision-map.md` · 決策地圖:Nginx 的四種身份、何時別用**
Nginx 四種身份(web server / 反向代理 / 負載均衡 / 邊緣腳本台)、心智模型(設定即程式)、什麼場景**不該**上 Nginx(雲託管 LB 夠用、要動態配置該上 Envoy/APISIX)。
↪ 網關抽象與演化 → `gateway/00`。

**`01-config-model.md` · 設定模型:區塊、繼承、location 匹配** 🔬⭐
🔬 `main`/`http`/`server`/`location` 層級與**指令繼承**(outer→inner、`add_header` 的繼承陷阱)、**`location` 匹配優先級**(`=` 精確 > `^~` 前綴停止 > 正則 `~`/`~*` 按出現序 > 最長前綴)、`root` vs `alias`、內建變數(`$uri`/`$request_uri`/`$args`…)、**「`if` is evil」的真相**(`if` 在 `location` 內只安全用於少數指令)。
🧪 `config-matching`:發各種請求看命中哪個 `location`。

**`02-rewrite-and-internal-redirect.md` · rewrite / return / 內部跳轉**
`rewrite` 的 flag(`last`/`break`/`redirect`/`permanent`)、`return` 為何優先於 `rewrite`、`try_files` 的回退鏈、命名 `location`(`@name`)、`error_page` 的內部跳轉、重定向環怎麼產生與避免、正則捕獲與 `$1`。
↪ 與 `01` 的 `location` 匹配合起來才是完整「請求落到哪段設定」。

### 角色段(Nginx 各種幹活方式)

**`03-web-server.md` · 當 web server:靜態與 FastCGI**
靜態檔案服務(`sendfile`/`aio`/`directio`、`index`/`autoindex`)、`gzip`/`brotli` 壓縮、`Range`/斷點續傳、`expires`/快取頭、FastCGI 與 php-fpm(`fastcgi_pass`)、自訂 `error_page`。
↪ 壓縮/快取頭與 HTTP 協議 → `network/http.md`。

**`04-reverse-proxy-and-upstream.md` · 反向代理與 upstream** 🔬⭐
🔬 `proxy_pass` 的**尾斜線陷阱**(帶不帶 `/` 的路徑改寫差異)、必設的 `proxy_set_header`(`Host`/`X-Forwarded-For`/`X-Forwarded-Proto`/`X-Real-IP`)、proxy buffer 機制、**超時三件套**(`proxy_connect_timeout`/`proxy_send_timeout`/`proxy_read_timeout`)、`upstream` 區塊(權重、`least_conn`/`ip_hash`、`max_fails`/`fail_timeout` 被動健康檢查、`keepalive` 連線池)。
↪ 連線池/keepalive 引擎內幕、L4-L7 → `gateway/01`;LB 演算法本身 → `system-design/05`。

**`05-proxy-cache.md` · 快取 proxy_cache:Nginx 當 CDN-lite** 🔬
🔬 `proxy_cache_path` 與 cache zone、**cache key 怎麼算**(`proxy_cache_key`)、TTL(`proxy_cache_valid`)、**`proxy_cache_use_stale`**(後端掛了用舊快取)、`proxy_cache_lock`(防快取擊穿)、micro-caching(快取 1 秒擋洪峰)、purge、用 `$upstream_cache_status` 調試命中。
🧪 `proxy-cache`:觀察 HIT/MISS/STALE 與擊穿。

**`06-rate-limiting.md` · Nginx 層流量控制**
`limit_req`(漏桶 + `burst` + `nodelay` 三者行為差異)、`limit_conn`(並發連線數)、`limit_rate`(頻寬限速)、`limit_req_status`/`limit_conn_status`、共享記憶體 zone 大小怎麼估;**邊界**:Nginx 本地限流是「每 worker / 每節點」,跨節點全域配額要外移。
↪ 演算法本身 → `distribution/限流算法/`、`system-design/01`;分散式 Lua 實作 → `redis-handson/13`、`gateway/05`。
🧪 `rate-limit`:`burst`/`nodelay` 行為實測。

**`07-tls.md` · TLS 實戰**
憑證設定(`ssl_certificate`/`ssl_certificate_key`)、SNI(一 IP 多域名)、`ssl_protocols`/`ssl_ciphers`、HSTS、**OCSP stapling**、session 復用(session cache / tickets)、HTTP→HTTPS 重導、mTLS(`ssl_verify_client`)、Let's Encrypt/certbot 自動化與續期。
↪ 握手為何貴(非對稱→對稱)、TLS 終止取捨 → `gateway/01`、`gateway/04`。

### 運維與性能段(怎麼調、怎麼救)

**`08-operations-zero-downtime.md` · 運維與零停機** 🔬⭐
🔬 **訊號表**(`HUP` reload / `USR2` 熱升級 / `WINCH` 優雅停 worker / `QUIT` 優雅退出 / `USR1` 重開日誌)、**`reload` 為什麼平滑**(master 重讀設定→啟新 worker→舊 worker 處理完在途請求才退)、**熱升級二進制**(USR2 啟新 master + 新 worker,WINCH 收舊 worker,出錯可回滾)、優雅退出與在途請求、`logrotate` + USR1 日誌切割、`nginx -t` 校驗與灰度。
🧪 `zero-downtime`:壓測中 `reload` + 熱升級,證明不丟連線。

**`09-performance-tuning.md` · 性能調優** 🔬
🔬 `worker_processes auto` 與 `worker_cpu_affinity`、`worker_connections` 與 `worker_rlimit_nofile`(和 `ulimit` 的關係)、事件模型(`epoll`)、`sendfile`/`tcp_nopush`/`tcp_nodelay` 三者協同、keepalive 調參(`keepalive_timeout`/`keepalive_requests`)、buffer 調參、`accept_mutex` vs `reuseport`、與內核參數(`somaxconn`/`tcp_max_syn_backlog`/檔案描述符)聯動。
↪ epoll 內核實現、TCP/內核參數深挖 → `performance-tuning-roadmap/00-os-fundamentals/`。

**`10-observability-debugging.md` · 可觀測與除錯 playbook** 🔬⭐
🔬 `log_format` 與內建變數($status/$request_time/$upstream_response_time/$upstream_cache_status…)、**499/502/504/503 各是什麼**(499=客戶端先斷、502=後端拒連或協議錯、504=後端超時、503=限流/`upstream` 全掛)、連線耗盡定位、`stub_status` 與 Prometheus exporter、`error_log debug`、抓包;一張「**症狀 → 定位 → 根因**」表。
↪ 一般可觀測性/日誌體系 → `observability/`、`logging/`。

### 外圈段(輕量,看崗位)

**`11-openresty-and-ingress.md` · 外圈:可程式化(OpenResty)與 k8s(ingress-nginx)** ↪
**OpenResty/Lua(輕)**:為什麼要可程式化、`access_by_lua`/`content_by_lua` 在哪個 phase 跑、`lua_shared_dict`、`ngx.*` API、何時升級到 OpenResty vs 換 Envoy/APISIX(最小例,不堆 Lua 細節)。
**ingress-nginx(輕)**:Ingress 資源 → Nginx config 這一跳、常用 annotation、snippet、與 Gateway API / 其他 ingress controller 的關係、和雲 LB 的分層。
↪ 網關可程式化演化 → `gateway/02`、`gateway/09`;k8s 網路全景 → `cloud-native/05`、`cloud-native-landscape/03`。

### 收口

**`12-selection-and-graduation.md` · 選型與「何時從 Nginx 畢業」**
Nginx vs Caddy(自動 TLS)vs Envoy(動態 xDS)vs HAProxy(L4/L7 LB)vs APISIX(雲原生 API 網關)vs 雲託管(ALB / API Gateway);各自何時用、**何時該從 Nginx 畢業**(需要動態配置/服務發現/豐富外掛時)、生產 checklist、常見故障模式。
↪ 完整網關選型與 AI 網關 → `gateway/11`、`gateway/10`(不重複,本章只切 Nginx 視角)。

**`99-interview-cards.md` · 面試卡片**
高頻題滿分答法:`location` 匹配優先級、`reload` 為什麼不丟連線、熱升級二進制原理、502 vs 504 怎麼分、`limit_req` 的 `burst`/`nodelay`、Nginx 為什麼快(↪ `gateway/01`)、`proxy_pass` 尾斜線、`X-Forwarded-For` 偽造防範。白板題「用 Nginx 搭一個生產級反代/LB/快取層」骨架。

**`lab/`** 四個可跑、本機自驗:
- `config-matching/`(對應 `01`/`02`):發請求看 `location`/`rewrite` 命中哪段。
- `proxy-cache/`(對應 `05`):觀察 HIT/MISS/STALE、快取擊穿與 `cache_lock`。
- `rate-limit/`(對應 `06`):`limit_req` 的 `burst`/`nodelay` 行為實測。
- `zero-downtime/`(對應 `08`):壓測中 `reload` + 熱升級,證明不丟連線。
> 反向代理基礎 lab 已在 `gateway/lab/nginx-reverse-proxy/`,本 track 不重做。

**`README.md`** track 索引 + 脊柱圖(`gateway/01` → `nginx/`)+ 章節導覽 + 學習路徑(面試衝刺線 / 系統通讀線)+ 「不在這裡學」交叉引用地圖。

## 5. 不在範圍(明確不重寫)

- 代理引擎內幕(epoll/master-worker/事件迴圈/連線池/TLS 為何貴/L4-L7)的**推導**(在 `gateway/01`)。
- 限流/熔斷/降級**演算法本身**(在 `system-design/01`、`distribution/限流算法/`)。
- 分散式限流的 **Redis/Lua 原子實作**(在 `redis-handson/13`、`gateway/05`)。
- 負載均衡 L4/L7 **演算法**、服務發現(在 `system-design/05`)。
- 認證/授權**概念基礎**、JWT/OIDC 原理(在 `system-design/10`、`gateway/04`)。
- Service Mesh、控制面/資料面、xDS 的**內幕與演化**(在 `gateway/08-09`、`cloud-native*`)。
- k8s 網路模型、Ingress 控制器內幕、CNI、eBPF、Gateway API(在 `cloud-native/05`、`cloud-native-landscape/03`)。
- epoll/TCP/內核參數的**內核實現**(在 `performance-tuning-roadmap/00-os-fundamentals/`)。
- 一般可觀測性/日誌體系(在 `observability/`、`logging/`)。
本 track 對以上一律 ↪ 指路,只補「Nginx 怎麼動手」的增量。

## 6. 一致性慣例

- 每章結構:開頭一句定位 → 內幕/方法論正文(教學主體,🔬 章含「黑盒裡發生什麼」)→ 交叉引用 → 本章小結 → 章末問答(複習自檢,答案要點在正文)。
- 每章標注面試高頻點;⭐ 章給「白板答法」話術。
- 設定範例可跑、本機可驗;lab 配最小可運行 `nginx.conf` + `docker compose` + 預期輸出。
- 跨生態對照(Caddy/Envoy/HAProxy/APISIX/雲託管),不綁死 Java,雲原生/語言無關為默認。
- 繁體中文;指令、設定指令名、變數名保留英文。

## 7. 成功標準

- 讀完能獨立寫/讀/除錯生產級 Nginx 設定:看懂 `location` 命中、寫對 `proxy_pass`/`upstream`、配 `proxy_cache`/`limit_req`/TLS、平滑 `reload` 與熱升級、用 log 定位 502/504/連線耗盡。
- 高頻面試題能當場答透:`location` 優先級、`reload` 為何不丟連線、熱升級原理、502 vs 504、`burst`/`nodelay`、Nginx 為什麼快。
- 四個 lab 能在本機跑出預期結果(命中表 / HIT-MISS-STALE / burst 行為 / reload 不丟連線)。
- 與 `gateway/` 零重複:凡「為什麼/抽象/演算法」都 ↪ 指過去,本 track 只講「Nginx 怎麼動手」。
- 🔬 章真的講「黑盒裡發生什麼」(訊號怎麼讓 worker 收工、快取 key 怎麼算、reload 怎麼交接 listen socket),而非停在貼設定。
