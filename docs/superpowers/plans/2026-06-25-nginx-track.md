# `nginx/` Track Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建一個資深/架構師面試向的 `nginx/` track,教「Nginx 這門手藝」(設定模型 / rewrite / 快取 / 限流 / TLS / 運維零停機 / 調優 / 除錯 playbook + OpenResty·ingress 輕外圈),坐在 `gateway/` 之上,引擎內幕一律 ↪ 指回 `gateway/01`,零重複。

**Architecture:** 倉庫根目錄新建獨立 track 資料夾 `nginx/`,13 章扁平 `.md`(英文 slug 檔名、繁體內容,00–12)+ `99-interview-cards.md` + `README.md` + `lab/`(4 個可跑範例)。每章是一個自包含、可獨立 review 的 task;`01-config-model` 是地基(02–12 都假設讀者能讀懂 `location` 區塊),故最先寫;lab 緊跟它驗證的章之後。

**Tech Stack:** Markdown(繁體中文教學);lab 用 Docker / docker-compose、Nginx(含 stub_status)、curl/wrk、後端用最小 Python(`http.server` 或 FastAPI)。對照工具:Caddy / Envoy / HAProxy / APISIX / 雲託管。

**Spec:** `docs/superpowers/specs/2026-06-25-nginx-track-design.md`(已批准)

## Global Constraints

每個 task 的要求都隱含以下全域約束(逐條來自 spec,照抄):

- **語言:繁體中文**,指令 / 設定指令名 / 變數名保留英文。
- **深度:資深/架構師級**。🔬 標記的章必含內幕層(黑盒裡發生什麼:訊號怎麼讓 worker 平滑收工、快取 key 怎麼算、reload 怎麼交接 listen socket),**不 defer**;內幕寫進**正文教學**,不是只丟問答。
- **規則先在敘事裡教全**:`location` 優先級、`rewrite` flag、訊號表這類「規則/公式」先在正文講清楚再用,不在前面挖空白讓讀者預測。
- **生態平衡**:選型不綁 Java;雲原生/語言無關為默認;對照工具(Caddy/Envoy/HAProxy/APISIX/雲託管)只在真主流處當錨點。
- **不重寫,交叉引用**:spec 第 5 節「不在範圍」清單裡的主題(引擎內幕、限流/熔斷演算法、分散式限流 Lua、LB 演算法、鑑權概念、mesh 內幕、k8s 網路、epoll/內核實現、一般可觀測性)一律 ↪ 指路(見下表),只補「Nginx 怎麼動手」的增量。
- **每章結構**:開頭一句定位 → 內幕/方法論正文(教學主體)→ 交叉引用 → 本章小結 → 章末問答(複習自檢,答案要點都在正文,**不承載新知識**)。
- **每章標面試高頻點**;⭐ 章給「白板答法」話術。
- **lab 可跑、本機可驗、自驗**;配最小可運行 `nginx.conf` + `docker-compose.yml` + `README.md`(怎麼跑 + 預期輸出)。
- **檔名英文 slug**(對齊 `gateway`/`cloud-native`)。

## 交叉引用路徑表(已驗證存在;寫每章照此指路)

| 指向 | 路徑 |
|---|---|
| 引擎內幕(epoll/master-worker/連線池/TLS 為何貴/L4-L7) | `gateway/01-reverse-proxy-engine.md` |
| 請求管線 / filter chain 抽象 | `gateway/02-request-pipeline.md` |
| 鑑權概念 / JWT / mTLS 概念 | `gateway/04-edge-authn-authz.md`、`system-design/10-安全-網路分區與認證授權.md` |
| 限流/熔斷演算法、分散式限流抽象 | `gateway/05-traffic-control.md`、`system-design/01-韌性-依賴掛了怎麼不崩.md`、`distribution/限流算法/` |
| 分散式限流 Lua 原子實作 | `redis-handson/13-rate-limiting/` |
| 負載均衡 L4/L7 演算法、服務發現 | `system-design/05-服務治理設施.md` |
| mesh / 控制面 / xDS / 熱更新抽象 | `gateway/08-gateway-as-distributed-system.md`、`gateway/09-data-plane-control-plane-and-mesh.md` |
| k8s 網路 / Ingress / Gateway API / eBPF | `cloud-native/05-networking.md`、`cloud-native-landscape/03-networking-ebpf-and-gateway-api.md` |
| epoll / 事件模型內核實現 | `performance-tuning-roadmap/00-os-fundamentals/`、`python-concurrency/00-execution-model/` |
| 內核參數 / TCP 調優 | `performance-tuning-roadmap/00-os-fundamentals/` |
| 一般可觀測性 / 日誌體系 | `observability/`、`logging/` |
| HTTP 協議 / CORS | `network/http.md`、`frontend/cross-origin/` |
| 完整網關選型 / AI 網關 | `gateway/11-selection-and-production-playbook.md`、`gateway/10-ai-llm-gateway.md` |

---

## File Structure

```
nginx/
├── README.md                              # track 索引 + 脊柱圖(gateway/01→nginx)+ 交叉引用地圖
├── 00-decision-map.md                     # Nginx 四種身份、何時別用
├── 01-config-model.md                     # 區塊/繼承/location 匹配優先級 🔬⭐
├── 02-rewrite-and-internal-redirect.md    # rewrite/return/try_files/內部跳轉
├── 03-web-server.md                       # 靜態/FastCGI/gzip/range
├── 04-reverse-proxy-and-upstream.md       # proxy_pass/header/超時/upstream 🔬⭐
├── 05-proxy-cache.md                      # proxy_cache(CDN-lite)🔬
├── 06-rate-limiting.md                    # limit_req/limit_conn/limit_rate
├── 07-tls.md                              # 憑證/SNI/OCSP/session/mTLS/certbot
├── 08-operations-zero-downtime.md         # 訊號/reload 平滑/熱升級/優雅退出 🔬⭐
├── 09-performance-tuning.md               # worker/buffer/keepalive/reuseport/內核聯動 🔬
├── 10-observability-debugging.md          # log/499-502-504/連線耗盡/stub_status 🔬⭐
├── 11-openresty-and-ingress.md            # 外圈:OpenResty + ingress-nginx(輕)
├── 12-selection-and-graduation.md         # 選型 + 何時從 Nginx 畢業
├── 99-interview-cards.md                  # 面試卡片
└── lab/
    ├── config-matching/                   # ch01/02:location/rewrite 命中
    ├── proxy-cache/                       # ch05:HIT/MISS/STALE + 擊穿
    ├── rate-limit/                        # ch06:burst/nodelay 行為
    └── zero-downtime/                     # ch08:reload + 熱升級不丟連線
```

> 反向代理基礎 lab 已在 `gateway/lab/nginx-reverse-proxy/`,本 track 不重做。

### 標準章節 Verify(下文各章 task 引用「標準章節 Verify」即指此,不重複)

```bash
cd nginx
# 1) 確認本章交叉引用到的目標路徑都存在(把本章實際引用的路徑代入)
for p in <本章引用到的相對倉庫根路徑...>; do ( cd .. && test -e "$p" && echo "OK $p" || echo "MISSING $p" ); done
# 2) 確認本章該有的結構小節都在(定位/正文/交叉引用/小結/章末問答)
grep -E "^#{1,3} " <本章>.md
```
人工自檢清單(每章都過):🔬 章內幕是否真講「黑盒裡發生什麼」而非停在貼設定;規則(優先級/flag/訊號)是否先在正文教全;面試高頻點是否標出;章末問答答案要點是否都在正文;↪ 指路是否用上表的真實路徑。

### 標準 lab Verify(各 lab task 引用「標準 lab Verify」即指此)

```bash
cd nginx/lab/<lab-name>
docker compose up -d          # 或 README 指定的啟動方式
bash run.sh                   # 腳本發請求 + 斷言預期輸出(見各 lab 的預期)
docker compose down
```
人工自檢:`run.sh` 跑完印出的觀察值與該 lab `README.md` 寫的「預期輸出」一致;設定檔最小、可讀、有註解。

---

## Task 1: README 骨架 + Ch00 決策地圖

先立 README 骨架(後續每寫完一章回填索引),再寫 00 章把「Nginx 四種身份 + 何時別用」框架定死,給 track 一個入口與心智地圖。

**Files:**
- Create: `nginx/README.md`
- Create: `nginx/00-decision-map.md`

**Interfaces:**
- Produces: 脊柱圖(`gateway/01` 引擎內幕 → `nginx/` 手藝實戰)+ 章節索引格式 + 「不在這裡學」交叉引用地圖,後續章節都回扣。

- [ ] **Step 1: 寫 `nginx/README.md` 骨架**

內容(繁體):
- 一句定位:本 track 教「Nginx 這門手藝」、為誰(資深面試 + 日常工作)、和 `gateway/` 的關係(gateway 教「為什麼快」,本 track 教「怎麼動手」)。
- 脊柱圖:取 spec 第 1 節那張「gateway/01 引擎內幕 → nginx/ 手藝實戰」ASCII 圖。
- 章節索引:00–12 + 99 + 4 lab,每行一句話 hook(先放全,內容隨各章完成校正)。
- 學習路徑:**面試衝刺線**(00→01→04→08→10→99)+ **系統通讀線**(00→12 順讀 + 4 lab)。
- 「不在這裡學什麼」小節:列 spec 第 5 節「不在範圍」+ 對應 ↪ 路徑(用交叉引用路徑表)。

- [ ] **Step 2: 寫 `nginx/00-decision-map.md`**

內容(繁體):
- 開頭一句定位:Nginx = 一台事件驅動的代理引擎,你要學的是怎麼駕馭它。
- **Nginx 四種身份**:web server(靜態/FastCGI)、反向代理、負載均衡、邊緣腳本台(OpenResty);各身份一句話 + 對應本 track 哪章。
- 心智模型:**設定即程式**(宣告式、區塊繼承、reload 才生效)。
- **何時別用 Nginx**(避免過度設計):雲託管 LB/CDN 夠用時、需要動態配置/服務發現/豐富外掛時該上 Envoy/APISIX、需要自動 TLS 想省事可選 Caddy。↪ 完整選型留到 `12`、`gateway/11`。
- 面試高頻點:「Nginx 能幹嘛、不該拿它幹嘛」。
- 章末問答 3–5 題。

- [ ] **Step 3: 標準章節 Verify**(本章引用路徑:`gateway/01-reverse-proxy-engine.md`、`gateway/11-selection-and-production-playbook.md`)

- [ ] **Step 4: Commit**

```bash
git add nginx/README.md nginx/00-decision-map.md
git commit -m "docs(nginx): README 骨架 + ch00 決策地圖(四種身份/設定即程式/何時別用)"
```

---

## Task 2: Ch01 設定模型:區塊、繼承、location 匹配 🔬⭐

地基章。02–12 都假設讀者能讀懂一個 `server`/`location` 區塊並預測請求落到哪段。這章把「設定語言」講死。

**Files:**
- Create: `nginx/01-config-model.md`

**Interfaces:**
- Produces:「設定模型」詞彙(指令繼承、`location` 優先級、內建變數),後續每章寫設定都站在其上。

- [ ] **Step 1: 寫 `nginx/01-config-model.md`**

🔬 內幕/規則正文必須講到(規則先教全):
- **區塊層級**:`main` → `events` → `http` → `server` → `location`;每層放什麼。
- **指令繼承**:outer→inner 向下繼承、inner 覆蓋;**`add_header` 的繼承陷阱**(子層出現 `add_header` 會丟掉父層的所有 `add_header`)。
- **`location` 匹配優先級(核心,先把完整規則列出再舉例)**:`=`(精確,命中即停)> `^~`(前綴,命中即停不再比正則)> 正則 `~`/`~*`(**按在設定檔出現的順序**,第一個命中即停)> 最長前綴匹配(無正則命中時回退)。配一張「請求 URI → 命中哪條」對照表。
- **`root` vs `alias`**:路徑拼接差異(`root` 拼整個 URI、`alias` 替換 `location` 前綴),最易錯的尾斜線。
- **內建變數**:`$uri`(解碼、可被內部改寫)vs `$request_uri`(原始)、`$args`/`$arg_xxx`、`$host`/`$http_xxx`;何時用哪個。
- **「`if` is evil」的真相**:`if` 在 `location` 內只對少數指令(`return`/`rewrite`)行為可預測,配 `proxy_pass`/`try_files` 等會出詭異結果;給「該用 `if` 還是 `map`/`try_files`」的取捨。
- 面試高頻點:「`location` 匹配優先級」「`root` 和 `alias` 差在哪」「為什麼說 if is evil」。給白板答法(口述優先級順序)。
- 章末問答(含一道「給定 4 條 location + 一個 URI,問命中哪條」)。

- [ ] **Step 2: 標準章節 Verify**(引用路徑:`gateway/02-request-pipeline.md`)
人工自檢:優先級五檔規則**完整列出且有對照表**;`add_header` 繼承陷阱有講;`if is evil` 給了替代方案而非只是警告。

- [ ] **Step 3: Commit**

```bash
git add nginx/01-config-model.md
git commit -m "docs(nginx): ch01 設定模型(區塊繼承/location 優先級/root-alias/if is evil)🔬"
```

---

## Task 3: Ch02 rewrite / return / 內部跳轉

接 01:把「請求落到哪段設定」的另一半——URI 改寫與內部跳轉——講清。

**Files:**
- Create: `nginx/02-rewrite-and-internal-redirect.md`

**Interfaces:**
- Consumes: ch01 的 `location` 匹配與內建變數。
- Produces:`try_files`/命名 location/`error_page` 內部跳轉詞彙,ch03(靜態回退)、ch04(反代回退)會用。

- [ ] **Step 1: 寫 `nginx/02-rewrite-and-internal-redirect.md`**

正文必須講到:
- **`rewrite` 的 flag**:`last`(改 URI 後重走 location 匹配)、`break`(改 URI 但停在本 location)、`redirect`(302)、`permanent`(301);四者行為差異與何時用哪個。
- **`return` 為何優先**:`return` 直接結束、比 `rewrite` 早;`return 301 https://...`、`return 444`(關連線)。
- **`try_files`**:回退鏈(`try_files $uri $uri/ /index.html` / `=404`),SPA 與靜態站的標準寫法。
- **命名 location**(`@name`)+ `error_page` 觸發的**內部跳轉**(internal redirect)機制:內部跳轉不回客戶端、會重走 phase。
- **重定向環**怎麼產生(rewrite 改完又匹配回自己)與怎麼避免;`X-Accel-Redirect`(交給後端決定內部跳轉)一句話帶過。
- 正則捕獲 `(...)` 與 `$1` 引用。
- 面試高頻點:「`last` 和 `break` 差在哪」「`rewrite` 和 `return` 誰先」。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**(引用路徑:`gateway/02-request-pipeline.md`)

- [ ] **Step 3: Commit**

```bash
git add nginx/02-rewrite-and-internal-redirect.md
git commit -m "docs(nginx): ch02 rewrite/return/try_files/內部跳轉(flag 差異/重定向環)"
```

---

## Task 4: lab/config-matching(驗證 ch01/02)

可跑 lab:發各種請求,觀察命中哪個 `location`、`rewrite` 怎麼改 URI,把 01/02 的抽象規則變成看得見的行為。

**Files:**
- Create: `nginx/lab/config-matching/nginx.conf`
- Create: `nginx/lab/config-matching/docker-compose.yml`
- Create: `nginx/lab/config-matching/run.sh`
- Create: `nginx/lab/config-matching/README.md`

**Interfaces:**
- Consumes: ch01 優先級規則、ch02 rewrite flag。

- [ ] **Step 1: 寫 `nginx.conf`**

設計:同一 `server` 內放會「打架」的 `location`——`= /exact`、`^~ /prefix-stop/`、`~* \.(jpg|png)$`、`~ ^/api/`、前綴 `/`;每個 `location` 用 `return 200 "matched: <name>\n"` 回自己的名字,讓命中一目了然。再加一段 `rewrite ^/old/(.*)$ /new/$1 last;` + 對應 `/new/` location 演示內部改寫。

- [ ] **Step 2: 寫 `docker-compose.yml`**

單一 `nginx:stable` 服務,掛載 `nginx.conf`,暴露 `8080:80`。

- [ ] **Step 3: 寫 `run.sh`(發請求 + 斷言)**

```bash
#!/usr/bin/env bash
set -euo pipefail
B=http://localhost:8080
check () { local path="$1" want="$2"; local got; got=$(curl -s "$B$path"); echo "$path -> $got"; [[ "$got" == *"$want"* ]] || { echo "FAIL: $path expected $want"; exit 1; }; }
check /exact            "matched: exact"
check /prefix-stop/x    "matched: prefix-stop"
check /a.JPG            "matched: regex-image"
check /api/users        "matched: regex-api"
check /whatever         "matched: longest-prefix"
check /old/thing        "matched: new"   # rewrite ... last 後重走匹配命中 /new/
echo "ALL PASS"
```

- [ ] **Step 4: 寫 `README.md`**:怎麼跑 + 每條請求的「預期命中」表 + 一句「對照 ch01 優先級規則」。

- [ ] **Step 5: 標準 lab Verify**

```bash
cd nginx/lab/config-matching && docker compose up -d && sleep 2 && bash run.sh && docker compose down
```
預期:`ALL PASS`,且每行 `-> matched: ...` 與 README 預期表一致。

- [ ] **Step 6: Commit**

```bash
git add nginx/lab/config-matching/
git commit -m "docs(nginx): lab/config-matching — location 優先級 + rewrite 命中實測"
```

---

## Task 5: Ch03 當 web server:靜態與 FastCGI

Nginx 最原始的身份。講清靜態服務與 FastCGI 怎麼配、壓縮/快取頭/range。

**Files:**
- Create: `nginx/03-web-server.md`

**Interfaces:**
- Consumes: ch01(`root`/`alias`)、ch02(`try_files`)。

- [ ] **Step 1: 寫 `nginx/03-web-server.md`**

正文必須講到:
- **靜態檔案服務**:`root`/`index`/`autoindex`、`sendfile on`(零拷貝,內幕一句:資料不過用戶態)、`aio`/`directio` 何時用、大檔案。
- **壓縮**:`gzip` 開關與 `gzip_types`/`gzip_min_length`、`gzip_static`(預壓)、`brotli`(需模組)。
- **快取頭**:`expires`、`Cache-Control`、`etag`/`last-modified`;靜態資源的標準快取策略。
- **`Range`/斷點續傳**:`206 Partial Content`,影音/大檔。
- **FastCGI 與 php-fpm**:`fastcgi_pass` + `fastcgi_param`,和反向代理的差異(FastCGI 協議 vs HTTP);一句帶到 uwsgi/scgi 同理。
- **自訂 `error_page`**:靜態錯誤頁。
- 面試高頻點:「`sendfile` 為什麼快」「動靜分離怎麼配」。
- ↪ 壓縮/快取頭與 HTTP 協議細節 → `network/http.md`。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**(引用路徑:`network/http.md`)

- [ ] **Step 3: Commit**

```bash
git add nginx/03-web-server.md
git commit -m "docs(nginx): ch03 當 web server(靜態/sendfile/gzip/range/FastCGI)"
```

---

## Task 6: Ch04 反向代理與 upstream 🔬⭐

最常用的身份,也是面試與日常踩坑重災區(尾斜線、header、超時)。

**Files:**
- Create: `nginx/04-reverse-proxy-and-upstream.md`

**Interfaces:**
- Consumes: ch01(`location`)。
- Produces: `proxy_pass`/`upstream`/超時詞彙,ch05(快取)、ch06(限流)、ch10(除錯)會用。

- [ ] **Step 1: 寫 `nginx/04-reverse-proxy-and-upstream.md`**

🔬 內幕/踩坑正文必須講到:
- **`proxy_pass` 的尾斜線陷阱**:`proxy_pass http://b;` vs `proxy_pass http://b/;` 在 `location /p/` 下對最終路徑的差異(帶 `/` 會用 `location` 後的剩餘部分替換);給一張組合對照表。
- **必設的 `proxy_set_header`**:`Host`(默認傳 `$proxy_host` 會丟原 Host)、`X-Forwarded-For`/`X-Real-IP`、`X-Forwarded-Proto`;**`X-Forwarded-For` 偽造防範**(別信客戶端傳入的、用 `realip` 模組設定可信代理)。
- **proxy buffer 機制**:`proxy_buffering on/off`、`proxy_buffers`、慢客戶端為什麼要 buffer(把後端早點放掉)。
- **超時三件套**:`proxy_connect_timeout`(連後端)/`proxy_send_timeout`/`proxy_read_timeout`(等後端回);各自對應哪種卡頓。
- **`upstream` 區塊**:server 權重、`least_conn`/`ip_hash`/(商業版 `hash`)、**被動健康檢查** `max_fails`/`fail_timeout`、`keepalive` 連線池(配 `proxy_http_version 1.1` + 清 `Connection` 頭,內幕細節 ↪ `gateway/01`)。
- 面試高頻點:「`proxy_pass` 帶不帶斜線差在哪」「`X-Forwarded-For` 能信嗎」「三個超時分別管什麼」。給白板答法。
- ↪ 連線池/keepalive 引擎內幕、L4-L7 → `gateway/01`;LB 演算法本身 → `system-design/05`。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**(引用路徑:`gateway/01-reverse-proxy-engine.md`、`system-design/05-服務治理設施.md`)
人工自檢:尾斜線**有對照表**;超時三件套各自對應的卡頓場景講清;`X-Forwarded-For` 偽造防範有講而非只列 header。

- [ ] **Step 3: Commit**

```bash
git add nginx/04-reverse-proxy-and-upstream.md
git commit -m "docs(nginx): ch04 反向代理與 upstream(尾斜線/header/超時/健康檢查/連線池)🔬"
```

---

## Task 7: Ch05 快取 proxy_cache:Nginx 當 CDN-lite 🔬

**Files:**
- Create: `nginx/05-proxy-cache.md`

**Interfaces:**
- Consumes: ch04(反代)。

- [ ] **Step 1: 寫 `nginx/05-proxy-cache.md`**

🔬 內幕正文必須講到:
- **`proxy_cache_path`** 與 cache zone(`keys_zone`、`levels` 目錄分層、`max_size`/`inactive`、磁碟 vs 記憶體 key)。
- **cache key 怎麼算**:`proxy_cache_key`(默認 `$scheme$proxy_host$request_uri`),何時要把 cookie/header 納入 key、key 設計不當的快取污染。
- **TTL**:`proxy_cache_valid 200 10m;` 按狀態碼設;`Cache-Control`/`Expires` 與 Nginx 設定誰優先。
- **`proxy_cache_use_stale`**:後端掛了/超時/更新中用舊快取(`error timeout updating`),提升可用性。
- **`proxy_cache_lock`**:防**快取擊穿**(同一 key 並發 miss 只放一個請求回源)。
- **micro-caching**:快取 1 秒擋瞬時洪峰(對動態內容也有效)的思路。
- **purge** 與 `$upstream_cache_status`(`HIT`/`MISS`/`EXPIRED`/`STALE`/`UPDATING`)調試,建議寫進 `log_format` 與回應頭。
- 面試高頻點:「快取擊穿 Nginx 怎麼擋」「micro-caching 為什麼有用」。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**(無新增外部引用;確認結構小節齊全)

- [ ] **Step 3: Commit**

```bash
git add nginx/05-proxy-cache.md
git commit -m "docs(nginx): ch05 proxy_cache(cache key/use_stale/cache_lock/micro-caching)🔬"
```

---

## Task 8: lab/proxy-cache(驗證 ch05)

可跑 lab:觀察 HIT/MISS/STALE、`proxy_cache_lock` 擋擊穿。

**Files:**
- Create: `nginx/lab/proxy-cache/nginx.conf`
- Create: `nginx/lab/proxy-cache/backend.py`
- Create: `nginx/lab/proxy-cache/docker-compose.yml`
- Create: `nginx/lab/proxy-cache/run.sh`
- Create: `nginx/lab/proxy-cache/README.md`

**Interfaces:**
- Consumes: ch05 `proxy_cache_*`。

- [ ] **Step 1: 寫 `backend.py`**:最小 HTTP 後端(Python `http.server`),每次回應遞增計數 + `sleep 1`(模擬慢回源),回 `body=count`,讓「快取命中時 count 不變」可觀測。

- [ ] **Step 2: 寫 `nginx.conf`**:`proxy_cache_path` + zone;`location /cached/` 開 `proxy_cache`、`proxy_cache_valid 200 10s`、`proxy_cache_lock on`、`add_header X-Cache-Status $upstream_cache_status;`;`location /stale/` 額外開 `proxy_cache_use_stale`。

- [ ] **Step 3: 寫 `docker-compose.yml`**:`backend`(python)+ `nginx`,nginx `8080:80`。

- [ ] **Step 4: 寫 `run.sh`(發請求 + 斷言)**

```bash
#!/usr/bin/env bash
set -euo pipefail
B=http://localhost:8080
s () { curl -s -D - "$1" -o /tmp/body | grep -i '^X-Cache-Status' | tr -d '\r'; }
echo "first  -> $(s $B/cached/x)"   # 預期 MISS
echo "second -> $(s $B/cached/x)"   # 預期 HIT
b1=$(curl -s $B/cached/x); b2=$(curl -s $B/cached/x)
[[ "$b1" == "$b2" ]] && echo "PASS: body unchanged while cached ($b1)" || { echo "FAIL: body changed"; exit 1; }
```

- [ ] **Step 5: 寫 `README.md`**:怎麼跑 + 預期(第一次 MISS、之後 HIT、命中期間 body/count 不變)+ 「對照 ch05」。

- [ ] **Step 6: 標準 lab Verify**

```bash
cd nginx/lab/proxy-cache && docker compose up -d && sleep 3 && bash run.sh && docker compose down
```
預期:首請求 `X-Cache-Status: MISS`、次請求 `HIT`、`PASS: body unchanged`。

- [ ] **Step 7: Commit**

```bash
git add nginx/lab/proxy-cache/
git commit -m "docs(nginx): lab/proxy-cache — HIT/MISS/STALE + cache_lock 實測"
```

---

## Task 9: Ch06 Nginx 層流量控制

**Files:**
- Create: `nginx/06-rate-limiting.md`

**Interfaces:**
- Consumes: ch04(反代)。

- [ ] **Step 1: 寫 `nginx/06-rate-limiting.md`**

正文必須講到(規則先教全):
- **`limit_req`(漏桶)**:`limit_req_zone` 定義 key(常用 `$binary_remote_addr`)+ rate(`10r/s`);`limit_req zone=... burst=20 nodelay;` 三種行為:**無 burst**(超速即 503)、**burst 無 nodelay**(排隊延遲放行)、**burst + nodelay**(立即放行但仍受速率約束,推薦)——把三者差異講透。
- **`limit_conn`**:`limit_conn_zone` + `limit_conn`,限同一 key 的並發連線數。
- **`limit_rate`**/`limit_rate_after`:單連線頻寬限速(下載限速)。
- **狀態碼**:`limit_req_status 429;`/`limit_conn_status`(默認 503,建議改 429)。
- **共享記憶體 zone 大小怎麼估**(`10m` 約存多少 key)。
- **邊界(關鍵)**:Nginx `limit_req` 的 zone 是**同節點所有 worker 共享的共享記憶體**(故計數是每節點的、不是每 worker),但**跨節點不共享**,所以是「單機粗粒度防護」;跨節點全域配額必須外移到 Redis/網關層。
- 面試高頻點:「`burst` 和 `nodelay` 行為差異」「Nginx 限流能不能做全域配額」。
- ↪ 演算法本身 → `distribution/限流算法/`、`system-design/01`;分散式限流 Lua → `redis-handson/13-rate-limiting/`、`gateway/05`。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**(引用路徑:`distribution/限流算法/`、`redis-handson/13-rate-limiting/`、`gateway/05-traffic-control.md`)
人工自檢:三種 burst/nodelay 行為**都講清**;「每 worker/每節點不共享」的邊界明確點出。

- [ ] **Step 3: Commit**

```bash
git add nginx/06-rate-limiting.md
git commit -m "docs(nginx): ch06 Nginx 層限流(limit_req burst/nodelay/limit_conn/單機邊界)"
```

---

## Task 10: lab/rate-limit(驗證 ch06)

可跑 lab:對比 `burst`/`nodelay` 的放行與 429 行為。

**Files:**
- Create: `nginx/lab/rate-limit/nginx.conf`
- Create: `nginx/lab/rate-limit/docker-compose.yml`
- Create: `nginx/lab/rate-limit/run.sh`
- Create: `nginx/lab/rate-limit/README.md`

**Interfaces:**
- Consumes: ch06 `limit_req`。

- [ ] **Step 1: 寫 `nginx.conf`**:`limit_req_zone $binary_remote_addr zone=z:10m rate=2r/s;`;`location /strict/`(無 burst)、`location /burst/`(`burst=5 nodelay`);都 `limit_req_status 429;`,後端用 `return 200 ok`。

- [ ] **Step 2: 寫 `docker-compose.yml`**:單 nginx,`8080:80`。

- [ ] **Step 3: 寫 `run.sh`(連發 10 個請求數狀態碼)**

```bash
#!/usr/bin/env bash
set -euo pipefail
B=http://localhost:8080
codes () { for i in $(seq 1 10); do curl -s -o /dev/null -w "%{http_code} " "$1"; done; echo; }
echo "strict (rate=2r/s, no burst):"; codes $B/strict/   # 預期:前 ~1-2 個 200,其餘大量 429
echo "burst  (burst=5 nodelay):";     codes $B/burst/    # 預期:前 ~6-7 個 200(令牌+burst),其餘 429
echo "觀察:strict 的 200 數明顯少於 burst 的 200 數即符合預期"
```

- [ ] **Step 4: 寫 `README.md`**:怎麼跑 + 預期(strict 立刻大量 429;burst 先放一批再 429)+ 「對照 ch06 三種行為」。

- [ ] **Step 5: 標準 lab Verify**

```bash
cd nginx/lab/rate-limit && docker compose up -d && sleep 2 && bash run.sh && docker compose down
```
預期:`/strict/` 的 200 數 < `/burst/` 的 200 數,且都出現 429。

- [ ] **Step 6: Commit**

```bash
git add nginx/lab/rate-limit/
git commit -m "docs(nginx): lab/rate-limit — burst/nodelay 行為實測"
```

---

## Task 11: Ch07 TLS 實戰

**Files:**
- Create: `nginx/07-tls.md`

**Interfaces:**
- Consumes: ch04(反代,TLS 終止後轉後端)。

- [ ] **Step 1: 寫 `nginx/07-tls.md`**

正文必須講到:
- **憑證設定**:`ssl_certificate`(含中間鏈順序)/`ssl_certificate_key`、`listen 443 ssl`。
- **SNI**:一 IP 多域名怎麼按 `server_name` 選憑證。
- **協議與 cipher**:`ssl_protocols TLSv1.2 TLSv1.3`、`ssl_ciphers`、`ssl_prefer_server_ciphers`。
- **HSTS**:`add_header Strict-Transport-Security`(注意 ch01 的 `add_header` 繼承陷阱)。
- **OCSP stapling**:`ssl_stapling on` 為什麼能省客戶端一次驗證往返。
- **session 復用**:`ssl_session_cache`/`ssl_session_tickets`,省重複握手(內幕「握手為何貴」↪ `gateway/01`)。
- **HTTP→HTTPS** 重導(`return 301`)。
- **mTLS**:`ssl_verify_client on` + `ssl_client_certificate`,雙向驗證。
- **Let's Encrypt/certbot**:`webroot`/`--nginx` 自動簽發與續期、`.well-known/acme-challenge`。
- 面試高頻點:「TLS 終止為什麼放邊緣」「OCSP stapling 解決什麼」。
- ↪ 握手為何貴、TLS 終止取捨 → `gateway/01`、`gateway/04`。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**(引用路徑:`gateway/01-reverse-proxy-engine.md`、`gateway/04-edge-authn-authz.md`)

- [ ] **Step 3: Commit**

```bash
git add nginx/07-tls.md
git commit -m "docs(nginx): ch07 TLS 實戰(憑證/SNI/OCSP/session 復用/mTLS/certbot)"
```

---

## Task 12: Ch08 運維與零停機 🔬⭐

架構師寶藏章:訊號、reload 為何不丟連線、熱升級二進制。

**Files:**
- Create: `nginx/08-operations-zero-downtime.md`

**Interfaces:**
- Produces: 訊號/熱升級詞彙,ch10 除錯會用。

- [ ] **Step 1: 寫 `nginx/08-operations-zero-downtime.md`**

🔬 內幕正文必須講到:
- **訊號表**:`HUP`(reload 設定)、`USR2`(熱升級二進制)、`WINCH`(優雅停 worker、保留 master)、`QUIT`(優雅退出)、`TERM`(快退)、`USR1`(重開日誌檔)。一張表 + 各自場景。
- **`reload` 為什麼平滑(內幕)**:master 收 `HUP` → 校驗新設定 → 用新設定 fork 新 worker → 對舊 worker 發停止訊號 → 舊 worker **不再接新連線、把在途請求處理完才退**(graceful);listen socket 由 master 持有不關,所以不丟連線。設定錯時新 worker 起不來、舊 worker 繼續服務(reload 安全)。
- **熱升級二進制(內幕)**:`USR2` 讓舊 master 重命名 pid、fork 出**新 master + 新 worker**(新舊同時跑、共用 listen socket fd);觀察無誤後 `WINCH` 收舊 worker、`QUIT` 收舊 master;出錯可把舊 master 拉回來回滾。畫出「舊 master/worker ↔ 新 master/worker」交接圖。
- **優雅退出與在途請求**:`worker_shutdown_timeout` 兜底。
- **日誌切割**:`mv access.log` 後 `USR1` 重開(配 logrotate `postrotate`)。
- **`nginx -t`** 校驗 + 灰度(先一台 reload 觀察)。
- 面試高頻點:「reload 為什麼不丟連線」「怎麼不停機升級 Nginx 版本」。給白板答法(口述 USR2→WINCH→QUIT 流程)。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**(引用路徑:`gateway/01-reverse-proxy-engine.md`)
人工自檢:reload 平滑機制講到「listen socket 由 master 持有 + 舊 worker 處理完在途才退」;熱升級有完整 USR2→WINCH→QUIT 交接圖與回滾路徑。

- [ ] **Step 3: Commit**

```bash
git add nginx/08-operations-zero-downtime.md
git commit -m "docs(nginx): ch08 運維與零停機(訊號表/reload 平滑/熱升級二進制)🔬"
```

---

## Task 13: lab/zero-downtime(驗證 ch08)

可跑 lab:壓測中 `reload`,證明不丟連線(回應 0 失敗)。

**Files:**
- Create: `nginx/lab/zero-downtime/nginx.conf`
- Create: `nginx/lab/zero-downtime/docker-compose.yml`
- Create: `nginx/lab/zero-downtime/run.sh`
- Create: `nginx/lab/zero-downtime/README.md`

**Interfaces:**
- Consumes: ch08 `reload` 機制。

- [ ] **Step 1: 寫 `nginx.conf`**:`location /` `return 200 ok`,`keepalive_timeout 65`,正常 worker 設定。

- [ ] **Step 2: 寫 `docker-compose.yml`**:單 `nginx:stable`,`8080:80`,容器名固定(`container_name: nginx-zdt`)方便 exec 發訊號。

- [ ] **Step 3: 寫 `run.sh`(持續壓 + 中途 reload + 統計失敗)**

```bash
#!/usr/bin/env bash
set -euo pipefail
B=http://localhost:8080
fail=0; total=0
( for i in $(seq 1 300); do
    curl -s -o /dev/null -w "%{http_code}" "$B/" | grep -q 200 || fail=$((fail+1))
    total=$((total+1)); sleep 0.02
  done; echo "TOTAL=$total FAIL=$fail" > /tmp/zdt.out ) &
LOAD=$!
sleep 1
docker exec nginx-zdt nginx -s reload   # 壓測中途熱重載
docker exec nginx-zdt nginx -t          # 順帶校驗
wait $LOAD
cat /tmp/zdt.out
grep -q "FAIL=0" /tmp/zdt.out && echo "PASS: reload 期間零失敗" || { echo "FAIL: 有請求失敗"; exit 1; }
```

- [ ] **Step 4: 寫 `README.md`**:怎麼跑 + 預期(`FAIL=0`,即 reload 不中斷在途/新請求)+ 「對照 ch08 reload 平滑」。說明熱升級(USR2)在容器內演示受限,故 lab 聚焦 reload。

- [ ] **Step 5: 標準 lab Verify**

```bash
cd nginx/lab/zero-downtime && docker compose up -d && sleep 2 && bash run.sh && docker compose down
```
預期:`TOTAL=300 FAIL=0` + `PASS: reload 期間零失敗`。

- [ ] **Step 6: Commit**

```bash
git add nginx/lab/zero-downtime/
git commit -m "docs(nginx): lab/zero-downtime — reload 期間零失敗實測"
```

---

## Task 14: Ch09 性能調優 🔬

**Files:**
- Create: `nginx/09-performance-tuning.md`

**Interfaces:**
- Consumes: ch04(連線池)、ch08(worker)。

- [ ] **Step 1: 寫 `nginx/09-performance-tuning.md`**

🔬 內幕正文必須講到(每個參數講「調它影響什麼」而非只列):
- **worker**:`worker_processes auto`(= CPU 核)、`worker_cpu_affinity`(綁核減 cache miss)。
- **連線上限**:`worker_connections` 與 `worker_rlimit_nofile`、和 OS `ulimit -n` 的關係(單 worker 可開 fd 數;反代每連線佔 2 個 fd:客戶端 + 後端)。
- **事件模型**:`use epoll`(Linux 默認)。
- **`sendfile`/`tcp_nopush`/`tcp_nodelay`**:三者協同(sendfile 零拷貝、tcp_nopush 攢滿包再發、tcp_nodelay 關 Nagle 低延遲),什麼場景開哪個。
- **keepalive 調參**:`keepalive_timeout`/`keepalive_requests`(對客戶端)、`upstream keepalive`(對後端,ch04 連結)。
- **buffer**:`client_body_buffer_size`/`proxy_buffers`/`large_client_header_buffers` 調太小/太大的後果。
- **`accept_mutex` vs `reuseport`**:`listen ... reuseport` 讓內核分發連線、消驚群、多核更均(內幕 ↪ `gateway/01`)。
- **內核聯動**:`net.core.somaxconn` 與 `listen backlog`、`tcp_max_syn_backlog`、檔案描述符上限;Nginx 設定再大也受內核參數封頂。
- 面試高頻點:「`worker_connections` 設多少」「sendfile/tcp_nopush/tcp_nodelay 各幹嘛」。
- ↪ epoll 內核實現、TCP/內核參數深挖 → `performance-tuning-roadmap/00-os-fundamentals/`。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**(引用路徑:`gateway/01-reverse-proxy-engine.md`、`performance-tuning-roadmap/00-os-fundamentals/`)
人工自檢:每個參數都講「調它影響什麼」;`worker_connections`/`rlimit_nofile`/`ulimit` 三者關係講清;內核參數封頂有點出。

- [ ] **Step 3: Commit**

```bash
git add nginx/09-performance-tuning.md
git commit -m "docs(nginx): ch09 性能調優(worker/連線上限/sendfile 三件套/reuseport/內核聯動)🔬"
```

---

## Task 15: Ch10 可觀測與除錯 playbook 🔬⭐

**Files:**
- Create: `nginx/10-observability-debugging.md`

**Interfaces:**
- Consumes: ch04(upstream 變數)、ch05(cache 變數)、ch08(訊號)。

- [ ] **Step 1: 寫 `nginx/10-observability-debugging.md`**

🔬 內幕正文必須講到:
- **`log_format` 與內建變數**:`$status`/`$request_time`(總耗時)/`$upstream_response_time`(後端耗時,兩者相減=Nginx 自身/排隊)/`$upstream_addr`/`$upstream_status`/`$upstream_cache_status`/`$bytes_sent`;建議的生產 log_format。
- **狀態碼診斷(核心,逐個講「什麼引起」)**:
  - `499` = 客戶端在 Nginx 回應前就斷開(常因客戶端超時/用戶取消)。
  - `502 Bad Gateway` = 後端拒連/連不上/回了非法回應(後端掛、埠錯、回應頭壞)。
  - `504 Gateway Timeout` = 後端連上但沒在 `proxy_read_timeout` 內回(後端慢)。
  - `503` = Nginx 自己擋(`limit_req`/`limit_conn`,或 `upstream` 全部 `max_fails` 熔斷)。
  給一張「狀態碼 → 最可能根因 → 下一步查什麼」表。
- **連線耗盡定位**:`worker_connections` 打滿 / fd 耗盡的徵兆與查法(`stub_status` 的 active/waiting、error_log 的 `worker_connections are not enough`)。
- **`stub_status`** 指標(Active/reading/writing/waiting)+ Prometheus exporter(nginx-prometheus-exporter)。
- **`error_log debug`**:開 debug 級看單請求在哪個 phase 出事(需 `--with-debug`)。
- **抓包**:`tcpdump` 看 Nginx↔後端那段。
- **症狀 → 定位 → 根因 playbook 表**(把上面串成一張可查的表)。
- 面試高頻點:「502 和 504 怎麼分」「怎麼定位 Nginx 連線耗盡」。給白板答法。
- ↪ 一般可觀測性/日誌體系 → `observability/`、`logging/`。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**(引用路徑:`observability/`、`logging/`)
人工自檢:499/502/503/504 **逐個講清成因**且有「狀態碼→根因→下一步」表;`$request_time` vs `$upstream_response_time` 的差值含義講到。

- [ ] **Step 3: Commit**

```bash
git add nginx/10-observability-debugging.md
git commit -m "docs(nginx): ch10 可觀測與除錯 playbook(log 變數/499-502-503-504/連線耗盡)🔬"
```

---

## Task 16: Ch11 外圈:OpenResty + ingress-nginx(輕)

兩個外圈主題各寫輕量「為什麼/何時/最小例」,不堆 Lua 與 annotation 細節。

**Files:**
- Create: `nginx/11-openresty-and-ingress.md`

**Interfaces:**
- Consumes: ch01(phase 觀念)、ch04(反代)。

- [ ] **Step 1: 寫 `nginx/11-openresty-and-ingress.md`**

**OpenResty/Lua(輕)** 必須講到:
- 為什麼要可程式化(純設定表達力不夠:動態鑑權、複雜路由、調用外部服務)。
- Lua 掛在哪個 phase:`set_by_lua`/`rewrite_by_lua`/`access_by_lua`/`content_by_lua`/`header_filter_by_lua`(對照 ch01 的請求處理階段)。
- `lua_shared_dict`(跨 worker 共享狀態,補 ch06「限流不跨 worker」的缺口)、`ngx.*` 常用 API(一最小 `access_by_lua` 例:讀 header 決定放行)。
- **何時升級到 OpenResty vs 直接換 Envoy/APISIX**(APISIX 本身基於 OpenResty)。

**ingress-nginx(輕)** 必須講到:
- **Ingress 資源 → Nginx config 這一跳**:ingress-nginx controller 把 `Ingress` 物件 watch 下來、渲染成 `nginx.conf`、reload(就是 ch08 的 reload)。
- 常用 annotation(`rewrite-target`、`proxy-body-size`、`ssl-redirect`)、`configuration-snippet`(直接塞 Nginx 設定)。
- 與 **Gateway API**、其他 ingress controller、雲 LB 的分層關係(一句:雲 LB → ingress-nginx → service)。
- ↪ 可程式化網關演化 → `gateway/02`、`gateway/09`;k8s 網路全景、Gateway API → `cloud-native/05-networking.md`、`cloud-native-landscape/03-networking-ebpf-and-gateway-api.md`。
- 面試高頻點:「ingress-nginx 怎麼把 Ingress 變成 Nginx 設定」「什麼時候該上 OpenResty」。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**(引用路徑:`gateway/02-request-pipeline.md`、`gateway/09-data-plane-control-plane-and-mesh.md`、`cloud-native/05-networking.md`、`cloud-native-landscape/03-networking-ebpf-and-gateway-api.md`)
人工自檢:保持「輕」——OpenResty 一個最小例即可、ingress 講到「Ingress→config→reload」這一跳即可,細節 ↪ 出去。

- [ ] **Step 3: Commit**

```bash
git add nginx/11-openresty-and-ingress.md
git commit -m "docs(nginx): ch11 外圈(OpenResty 可程式化 + ingress-nginx)輕量指路"
```

---

## Task 17: Ch12 選型與「何時從 Nginx 畢業」

**Files:**
- Create: `nginx/12-selection-and-graduation.md`

**Interfaces:**
- Consumes: 全 track。

- [ ] **Step 1: 寫 `nginx/12-selection-and-graduation.md`**

正文必須講到:
- **對照表**:Nginx vs Caddy(自動 TLS、設定簡)vs Envoy(動態 xDS、可觀測)vs HAProxy(L4/L7 LB、極穩)vs APISIX(雲原生 API 網關、OpenResty 底)vs 雲託管(ALB / API Gateway);每個「強項 / 何時用」。
- **何時該從 Nginx 畢業(關鍵)**:需要不重啟動態改路由/服務發現整合/豐富外掛生態/精細可觀測時,Nginx 的「設定檔 + reload」模型撐不住,該換 Envoy/APISIX;只想省 TLS 運維可換 Caddy。
- **生產 checklist**:設定校驗、版本升級流程(ch08)、監控接入(ch10)、限流/超時兜底(ch04/06)、TLS 自動續期(ch07)。
- **常見故障模式**速查(回扣 ch10 的狀態碼表)。
- 面試高頻點:「什麼時候不該再用 Nginx」。
- ↪ 完整網關選型與 AI 網關 → `gateway/11`、`gateway/10`(本章只切 Nginx 視角,不重複)。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**(引用路徑:`gateway/11-selection-and-production-playbook.md`、`gateway/10-ai-llm-gateway.md`)
人工自檢:選型表**不綁 Java**、雲原生/語言無關;「何時畢業」有實質判據而非套話;與 `gateway/11` 不重複(只切 Nginx 視角)。

- [ ] **Step 3: Commit**

```bash
git add nginx/12-selection-and-graduation.md
git commit -m "docs(nginx): ch12 選型與何時從 Nginx 畢業(對照表/畢業判據/生產 checklist)"
```

---

## Task 18: Ch99 面試卡片 + README 索引回填

收口:把全 track 高頻題彙整成卡片;回填 README 索引讓每行 hook 與成稿一致。

**Files:**
- Create: `nginx/99-interview-cards.md`
- Modify: `nginx/README.md`(回填最終章節索引與 hook)

**Interfaces:**
- Consumes: 全 track 章節。

- [ ] **Step 1: 寫 `nginx/99-interview-cards.md`**

內容(每張卡:問題 → 30 秒口述答法 → 指回哪章深讀):
- `location` 匹配優先級(口述五檔順序)→ ch01
- `proxy_pass` 尾斜線差異 → ch04
- `X-Forwarded-For` 能不能信 → ch04
- `limit_req` 的 `burst`/`nodelay` → ch06
- `reload` 為什麼不丟連線 → ch08
- 怎麼不停機升級 Nginx 二進制(USR2→WINCH→QUIT)→ ch08
- 502 vs 504 vs 499 怎麼分 → ch10
- Nginx 為什麼快(master-worker + epoll,↪ `gateway/01`)→ ch00/ch09
- 什麼時候該從 Nginx 畢業 → ch12
- **白板題**:「用 Nginx 搭一個生產級反代 + LB + 快取 + 限流 + TLS 接入層」答題骨架(把 ch04/05/06/07/08/10 串起來)。

- [ ] **Step 2: 回填 `nginx/README.md` 索引**:把 00–12 + 99 + 4 lab 每行 hook 校正到與成稿一致;確認學習路徑兩條線的章號正確。

- [ ] **Step 3: 標準章節 Verify**(引用路徑:`gateway/01-reverse-proxy-engine.md`)+ 全 track 結構掃描:

```bash
cd nginx && ls -1 *.md && for f in 0*.md 1*.md 99-*.md; do echo "== $f =="; grep -cE "^#{1,3} " "$f"; done
```
人工自檢:每張卡有「30 秒答法 + 指回章」;白板骨架串得起來;README 每行 hook 與成稿一致、無死連結。

- [ ] **Step 4: Commit**

```bash
git add nginx/99-interview-cards.md nginx/README.md
git commit -m "docs(nginx): ch99 面試卡片 + README 索引回填(track 收官)"
```

---

## Self-Review(寫完計畫後對 spec 的覆蓋檢查)

- **Spec 覆蓋**:spec §4 章節 00–12 + 99 + README + 4 lab,逐一對應 Task 1–18(00→T1、01→T2、02→T3、config-matching→T4、03→T5、04→T6、05→T7、proxy-cache→T8、06→T9、rate-limit→T10、07→T11、08→T12、zero-downtime→T13、09→T14、10→T15、11→T16、12→T17、99+README→T18)。無遺漏。
- **不在範圍(spec §5)**:各章 ↪ 指路用「交叉引用路徑表」的已驗證路徑,無重寫。
- **Placeholder**:各章 task 給了「必須講到」的實質 bullet,各 lab 給了 `nginx.conf` 設計 + `run.sh` + 斷言 + 預期輸出,無 TBD。
- **一致性**:lab 名 config-matching/proxy-cache/rate-limit/zero-downtime 與 spec §4 lab 清單一致;章號與檔名一致;繁體 + 英文 slug 全程一致。

---

## Execution Notes

- **隔離**:已在 worktree `/.worktrees/nginx`(分支 `worktree-nginx`,基於本地 HEAD);所有 commit 落此分支,與其他並行任務無交集。
- **並發 git add 紀律**:本倉庫常有並發 agent 跑 `git add -A`,每個 Commit 步驟都用**顯式路徑** `git add nginx/<具體檔>`,不用 `-A`。
- **lab 依賴**:需要 Docker(OrbStack/Docker Desktop);若執行時 Docker 不可用,lab task 的「標準 lab Verify」改為人工核對設定正確性並在該 lab README 標注「未在本機跑通」,不阻塞文件 task。
- **寫作風格**:對齊姊妹 track `gateway/`(已成稿)的語氣與排版;可先讀 `gateway/01`、`gateway/11` 取樣。
