# `gateway/` Track Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建一個資深/架構師面試向的 `gateway/` track,以「邊緣可程式化代理」為主角,沿 Nginx → API 網關 → [Mesh 邊界] → AI 網關 這根脊柱,自擁「管線內幕 + 分散式網關 + AI 網關」,其餘交叉引用現有深礦。

**Architecture:** 倉庫根目錄新建獨立 track 資料夾 `gateway/`,12 章扁平 `.md`(英文 slug 檔名、繁體內容)+ `99-interview-cards.md` + `README.md` + `lab/`(3 個可跑範例)。每章是一個自包含、可獨立 review 的 task,按敘事順序遞進(管線章 02 是 03/04/05 的骨架前提)。

**Tech Stack:** Markdown(繁體中文教學);lab 用 Docker / docker-compose、Nginx、Redis、Python(FastAPI/httpx)。樣例工具:Nginx、Envoy、APISIX、Kong、Spring Cloud Gateway、LiteLLM/Portkey。

**Spec:** `docs/superpowers/specs/2026-06-23-gateway-track-design.md`(已批准)

## Global Constraints

每個 task 的要求都隱含以下全域約束(逐條來自 spec,照抄):

- **語言:繁體中文**,技術名詞保留英文。
- **深度:資深/架構師級**。每章必含 🔬 內幕層(黑盒裡發生什麼:存儲/索引/底層取捨),**不 defer**。底層內幕寫進**正文教學**,不是只丟到問答。
- **生態平衡**:默認雲原生/語言無關;Java(Spring Cloud Gateway)僅在真主流處當錨點,配 Go/Python 等價物。樣例工具優先開源、透明、真生產。
- **不重寫,交叉引用**:spec 第 5 節「不在範圍」清單裡的主題(限流/熔斷/降級算法、認證授權概念、mesh 內幕/性能/演化、k8s 網路/Ingress/eBPF、一般可觀測性/日誌)一律 ↪ 指路到現有 track,只補「網關視角下的增量」。
- **每章結構**:開頭一句定位 → 🔬 內幕正文(教學主體)→ 交叉引用 → 本章小結 → 章末問答(複習自檢,答案要點都在正文,**不承載新知識**)。
- **每章標面試高頻點**;適當處給「白板答法」話術。
- **lab 可跑、本機可驗、自驗**;配最小可運行範例與預期輸出。
- **檔名英文 slug**(對齊 `cloud-native`/`concurrency-capacity`)。

## 交叉引用路徑表(寫每章時照此指路,寫前用 Verify 步驟確認路徑存在)

| 指向 | 路徑 |
|---|---|
| 韌性六件套(算法) | `system-design/01-韌性-依賴掛了怎麼不崩.md` |
| 認證 vs 授權 / RBAC-ABAC | `system-design/10-安全-網路分區與認證授權.md` |
| 負載均衡 L4/L7、服務發現、mesh 輕量 | `system-design/05-服務治理設施.md` |
| API 網關 / BFF(概念)、通信範式 | `system-design/04-服務化與通信範式.md` |
| 分散式限流 Lua 實作 | `redis-handson/13-rate-limiting/` |
| 過載/背壓/load shedding | `concurrency-capacity/07-overload-backpressure/` |
| Nginx 限流配置、重試風暴 | `performance-tuning-roadmap/10-distributed/02-retry-ratelimit.md` |
| Mesh 演化 sidecar→ambient | `cloud-native-landscape/04-service-mesh-sidecar-to-ambient.md` |
| Mesh 性能/成本量化 | `performance-tuning-roadmap/12-container/04-service-mesh-perf.md` |
| 控制面/資料面內幕、k8s Ingress | `cloud-native/03b-control-and-data-plane-internals.md`、`cloud-native/05-networking.md` |
| eBPF/Cilium + Gateway API | `cloud-native-landscape/03-networking-ebpf-and-gateway-api.md` |
| epoll / 事件模型 | `performance-tuning-roadmap/00-os-fundamentals/`、`python-concurrency/00-execution-model/` |
| 可觀測性 / 日誌 | `observability/`、`logging/` |
| AI 基建 / serving | `cloud-native-landscape/10-ai-infra-serving-and-inference.md`、`ai/` |

---

## File Structure

```
gateway/
├── README.md                                   # track 索引 + 脊柱圖 + 交叉引用地圖
├── 00-decision-map.md                          # 網關是什麼、何時不需要
├── 01-reverse-proxy-engine.md                  # 反向代理引擎內幕 🔬
├── 02-request-pipeline.md                      # filter chain(骨架)🔬
├── 03-routing-and-load-balancing.md            # 路由/LB/灰度 🔬
├── 04-edge-authn-authz.md                      # 邊緣鑑權 🔬
├── 05-traffic-control.md                       # 限流/熔斷/降級/卸載 🔬
├── 06-protocol-translation-and-aggregation.md  # BFF/轉碼/WS 🔬
├── 07-observability-at-the-edge.md             # 邊緣觀測 🔬
├── 08-gateway-as-distributed-system.md         # 網關叢集/控制面 🔬
├── 09-data-plane-control-plane-and-mesh.md     # 南北/東西 + mesh 邊界 🔬
├── 10-ai-llm-gateway.md                        # AI/LLM 網關 🔬
├── 11-selection-and-production-playbook.md     # 選型 + 生產 playbook
├── 99-interview-cards.md                       # 面試卡片
└── lab/
    ├── nginx-reverse-proxy/                    # ch01 lab
    ├── distributed-rate-limit/                 # ch05 lab(2 節點 + Redis)
    └── mini-llm-gateway/                       # ch10 lab(token 限流 + 語義快取)
```

每章「Verify」步驟通用做法(下文不再重複,各 task 引用「標準章節 Verify」即指此):

```bash
# 1) 確認本章交叉引用的目標路徑都存在(把本章用到的路徑列進來)
for p in <本章引用到的路徑...>; do test -e "$p" && echo "OK $p" || echo "MISSING $p"; done
# 2) 確認本章該有的結構小節都在
grep -E "^#{1,3} " gateway/<本章>.md
# 3) 人工自檢清單:🔬 內幕是否真講「黑盒裡發生什麼」而非停在高層;面試高頻點是否標出;章末問答答案要點是否都在正文
```

---

## Task 1: README 骨架 + Ch00 決策地圖

先立 README 骨架(後續每寫完一章回填一行索引),再寫 00 章把脊柱框架定死,給整個 track 一個入口與心智地圖。

**Files:**
- Create: `gateway/README.md`
- Create: `gateway/00-decision-map.md`

**Interfaces:**
- Produces: 脊柱 ASCII 圖(Nginx→API 網關→[Mesh]→AI 網關)+ 章節索引格式,後續章節都回扣此圖。

- [ ] **Step 1: 寫 `gateway/README.md` 骨架**

內容:
- 一句定位:本 track 教什麼、為誰(資深面試向)、和其他 track 的關係。
- 脊柱 ASCII 圖(直接取 spec 第 1 節那張表)。
- 章節索引:00–11 + 99 + lab,每行一句話 hook(先放全,內容隨各章完成校正)。
- 「不在這裡學什麼」小節:列 spec 第 5 節「不在範圍」+ 對應 ↪ 路徑,讓讀者知道去哪找。

- [ ] **Step 2: 寫 `gateway/00-decision-map.md`**

內容(全繁體):
- 開頭一句定位:網關 = 邊緣可程式化代理。
- 脊柱全圖 + 核心洞察「後面每層 = 前一層 + 更多『認識業務』的橫切能力」(Nginx 認識 host/path;API 網關認識 用戶/API/配額;mesh 下沉到 sidecar;AI 網關認識 token/模型)。
- **南北向 vs 東西向**一張圖講死(入口流量 vs 服務間流量)。
- **何時不該上網關**(避免過度設計):單體/少量服務、內網直連夠用、團隊扛不住運維時的取捨。
- 面試高頻點:「網關解決什麼問題、不解決什麼」。
- 章末問答 3–5 題(複習自檢)。

- [ ] **Step 3: 標準章節 Verify**

```bash
grep -E "^#{1,3} " gateway/00-decision-map.md
grep -E "^#{1,3} " gateway/README.md
```
人工自檢:脊柱圖在;南北/東西邊界講清;「何時不需要」有實質取捨而非套話。

- [ ] **Step 4: Commit**

```bash
git add gateway/README.md gateway/00-decision-map.md
git commit -m "docs(gateway): README 骨架 + ch00 決策地圖(脊柱/南北東西/何時不需要)"
```

---

## Task 2: Ch01 反向代理:網關的引擎 🔬

打地基:在講「網關多管什麼事」之前,先講清「代理本身這台引擎」在 socket/事件層做什麼。這是後續所有章節的物理基礎。

**Files:**
- Create: `gateway/01-reverse-proxy-engine.md`

**Interfaces:**
- Produces: 「代理引擎」的詞彙(master-worker、epoll loop、upstream 連線池、TLS 終止、L4 vs L7),ch02 管線章直接站在其上。

- [ ] **Step 1: 寫 `gateway/01-reverse-proxy-engine.md`**

🔬 內幕正文必須講到:
- **Nginx master-worker 模型**:master 載入配置/綁 socket/管 worker;worker 進程數 = CPU 核;worker 怎麼搶連線(`accept_mutex` vs `SO_REUSEPORT` 內核分發)、驚群問題。
- **事件迴圈**:單 worker 用 epoll(edge-triggered)+ 非阻塞 I/O 撐住上萬連線;一個 worker 為何能同時服務海量連線(對比 thread-per-conn)。↪ epoll 細節指 `performance-tuning-roadmap/00-os-fundamentals/`、`python-concurrency/00-execution-model/`。
- **upstream 連線池 / keepalive**:對後端復用長連線,避免每請求重建 TCP;`keepalive` 指令的意義;連線池打滿會怎樣。
- **TLS 終止**:握手在網關卸載(對稱/非對稱、握手成本),後端走明文或 re-encrypt;為什麼把 TLS 收在邊緣。
- **L4 vs L7 代理的本質**:L4 只看 IP:port(轉發快、不懂 HTTP);L7 解析 HTTP(能按 path/header 路由、能改寫,但要解包成本)。↪ LB 算法本身指 `system-design/05`。
- 跨生態對照:Nginx / HAProxy / Envoy 在這層的差異(進程 vs 線程、配置 vs 動態)。
- 面試高頻點:「Nginx 為什麼快」「L4 和 L7 差在哪、各用在哪」。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**

```bash
for p in performance-tuning-roadmap/00-os-fundamentals python-concurrency/00-execution-model system-design/05-服務治理設施.md; do test -e "$p" && echo "OK $p" || echo "MISSING $p"; done
grep -E "^#{1,3} " gateway/01-reverse-proxy-engine.md
```
人工自檢:master-worker / epoll / 連線池 / TLS 終止 / L4-L7 五塊內幕都在且講到機制層。

- [ ] **Step 3: 回填 README 該章索引行,Commit**

```bash
git add gateway/01-reverse-proxy-engine.md gateway/README.md
git commit -m "docs(gateway/01): 反向代理引擎內幕 — master-worker/epoll/連線池/TLS終止/L4-L7"
```

---

## Task 3: Lab — nginx 反向代理(ch01 配套)

**Files:**
- Create: `gateway/lab/nginx-reverse-proxy/docker-compose.yml`
- Create: `gateway/lab/nginx-reverse-proxy/nginx.conf`
- Create: `gateway/lab/nginx-reverse-proxy/README.md`

**Interfaces:**
- Consumes: ch01 的概念(worker、upstream、L7 路由)。
- Produces: 一個能起的 nginx 反代,前面一個 nginx,後面 2 個 echo 後端。

- [ ] **Step 1: 寫 compose + nginx.conf**

`docker-compose.yml`:一個 `nginx` 服務(掛載 `nginx.conf`,曝 8080)+ 兩個輕量 echo 後端(用 `hashicorp/http-echo` 或 `kennethreitz/httpbin`),同一 network。
`nginx.conf`:
- `worker_processes auto;`
- `upstream backend { server echo1:5678; server echo2:5678; keepalive 16; }`
- `server { listen 8080; location / { proxy_pass http://backend; proxy_http_version 1.1; proxy_set_header Connection ""; } location /a { proxy_pass http://echo1:5678; } }`(示範 L7 按 path 路由)

- [ ] **Step 2: 起服務並驗證(我自己跑)**

```bash
cd gateway/lab/nginx-reverse-proxy && docker compose up -d
# 多打幾次根路徑,觀察輪詢落到兩個後端
for i in $(seq 1 6); do curl -s localhost:8080/; done
# 看 worker 數
docker compose exec nginx sh -c 'ps -e | grep nginx | wc -l'
docker compose down
```
Expected:`curl /` 的回應在 echo1/echo2 之間輪替;worker 數 ≈ 容器可見核數 + 1(master)。

- [ ] **Step 3: 寫 lab README(怎麼跑 + 預期輸出 + 對應 ch01 哪段)**

- [ ] **Step 4: Commit**

```bash
git add gateway/lab/nginx-reverse-proxy
git commit -m "docs(gateway/lab): nginx 反向代理可跑範例(L7 路由 + upstream 輪詢)"
```

---

## Task 4: Ch02 請求管線 / Filter Chain 🔬

整個 track 的骨架章。確立「請求按序流過各階段」這個心智模型,後面 03/04/05 都是往這條管線的某一段塞邏輯。

**Files:**
- Create: `gateway/02-request-pipeline.md`

**Interfaces:**
- Produces: 管線階段標準序 `接收→匹配路由→認證→授權→限流→改寫→轉發 upstream→回應過濾→埋點`,後續章節引用此序定位自己。

- [ ] **Step 1: 寫 `gateway/02-request-pipeline.md`**

🔬 內幕正文必須講到:
- **標準管線階段序**(上面那串),畫成請求/回應雙向流的圖(請求向下穿過 filters,回應向上穿回)。
- **同一套抽象的四種實現對照**:Envoy HTTP filter chain、Kong plugin phases(`access`/`header_filter`/`body_filter`/`log`)、APISIX phases、Spring Cloud Gateway `GlobalFilter`/`GatewayFilter` 的 `Ordered`。指出它們是同一個模式。
- **順序為什麼要緊**:限流放鑑權**前**還**後**?(放前→省鑑權開銷但匿名也能耗配額;放後→先認出用戶才按用戶限流但鑑權自己會被打)——講清取捨,給「看你要保護什麼」的答法。
- **短路與提前返回**:某個 filter(如鑑權失敗)直接返回,後續 filter 不跑。
- **請求/回應改寫掛在哪兩段**。
- 面試高頻點:「一個請求進網關到打到後端經過哪些階段」「限流和鑑權誰先」。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**

```bash
grep -E "^#{1,3} " gateway/02-request-pipeline.md
```
人工自檢:管線序完整;四種實現對照在;「限流 vs 鑑權順序」有實質取捨論證。

- [ ] **Step 3: 回填 README,Commit**

```bash
git add gateway/02-request-pipeline.md gateway/README.md
git commit -m "docs(gateway/02): 請求管線/filter chain 骨架 — 階段序+四框架對照+順序取捨"
```

---

## Task 5: Ch03 路由與負載均衡 🔬

管線的「匹配路由 + 轉發 upstream」段展開。

**Files:**
- Create: `gateway/03-routing-and-load-balancing.md`

- [ ] **Step 1: 寫 `gateway/03-routing-and-load-balancing.md`**

🔬 內幕正文必須講到:
- **路由匹配**:按 host / path(前綴 vs 精確 vs 正則)/ header / method / 權重;匹配優先級與衝突;路由表怎麼組織(trie/radix tree 找最長前綴)。
- **upstream 選擇與健康檢查**:主動(定期探活)vs 被動(從失敗請求標記不健康)健康檢查;摘除與恢復。
- **灰度 / 金絲雀發布**:按權重切分流量、按 header/cookie 定向(內部用戶先試)、按百分比放量;和藍綠的差別。
- **邊緣的超時與重試**:對 upstream 的連線/讀寫超時;重試只對冪等請求 + 退避抖動。↪ 重試紀律/退避抖動指 `system-design/01`;LB L4/L7 算法、服務發現指 `system-design/05`。
- 跨生態對照:Envoy(動態 cluster)/ APISIX(`upstream` + 服務發現)/ Spring Cloud Gateway(`lb://`)。
- 面試高頻點:「網關怎麼做灰度」「健康檢查主動被動差異」。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**

```bash
for p in system-design/01-韌性-依賴掛了怎麼不崩.md system-design/05-服務治理設施.md; do test -e "$p" && echo OK $p || echo MISSING $p; done
grep -E "^#{1,3} " gateway/03-routing-and-load-balancing.md
```

- [ ] **Step 3: 回填 README,Commit**

```bash
git add gateway/03-routing-and-load-balancing.md gateway/README.md
git commit -m "docs(gateway/03): 路由匹配/健康檢查/灰度金絲雀/邊緣超時重試"
```

---

## Task 6: Ch04 邊緣鑑權:認證與授權 🔬

管線的「認證 + 授權」段展開。概念基礎交叉引用,本章只補「落在網關邊緣」這個增量。

**Files:**
- Create: `gateway/04-edge-authn-authz.md`

- [ ] **Step 1: 寫 `gateway/04-edge-authn-authz.md`**

🔬 內幕正文必須講到:
- **為什麼鑑權要下沉到邊緣**:後端服務不必各自實現、統一策略、減少內網信任面。
- **JWT 校驗**:結構(header.payload.signature)、網關怎麼**無狀態**驗簽(對稱 HS256 vs 非對稱 RS256/公鑰)、`exp`/`nbf`/`aud`/`iss` 檢查、JWKS 端點與公鑰輪換、為什麼能下沉(自包含、不查 DB)。
- **OAuth2 / OIDC 在網關**:authorization code flow 簡述、網關作為 resource server 校驗 access token、token introspection(不透明 token 要回 auth server 查)。
- **API Key**、**mTLS 終止**(雙向 TLS、客戶端證書驗身,常用於服務間/合作方)。
- **auth offload vs 委派**:網關驗完注入 `X-User-Id` 等可信 header 給後端 vs 把原 token 透傳。
- **授權落點**:RBAC/ABAC 粗粒度放網關、細粒度留後端。↪ 認證 vs 授權概念、RBAC/ABAC 指 `system-design/10`。
- 面試高頻點:「JWT 為什麼能在網關無狀態校驗」「不透明 token 和 JWT 差別」「鑑權放網關還是服務」。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**

```bash
test -e system-design/10-安全-網路分區與認證授權.md && echo OK || echo MISSING
grep -E "^#{1,3} " gateway/04-edge-authn-authz.md
```

- [ ] **Step 3: 回填 README,Commit**

```bash
git add gateway/04-edge-authn-authz.md gateway/README.md
git commit -m "docs(gateway/04): 邊緣鑑權 — JWT無狀態驗簽/OIDC/mTLS/offload vs 委派"
```

---

## Task 7: Ch05 流量控制:限流/熔斷/降級/卸載 🔬

管線的「限流」段 + 對 upstream 的保護。本章是用戶最初問的「併發控制」落點。算法本身交叉引用,本章補「在網關 + 在叢集」的增量。

**Files:**
- Create: `gateway/05-traffic-control.md`

**Interfaces:**
- Produces: 分散式限流的「local vs global counter」模型,ch08(網關叢集)會回扣。

- [ ] **Step 1: 寫 `gateway/05-traffic-control.md`**

🔬 內幕正文必須講到:
- **限流落在管線哪段**、按什麼維度(全域 / per-route / per-consumer(API key/用戶)/ per-IP)。
- **分散式限流(本章核心增量)**:N 個網關節點怎麼共享計數——
  - local counter(各節點各算,簡單但總量飄)vs global counter(共享存儲,準但有延遲/熱點);
  - **Redis 後端 + Lua 原子**(讀-改-寫競態為何要 Lua)↪ 實作 lab 指 `redis-handson/13-rate-limiting/`;
  - 近似方案:本地配額 + 週期同步、令牌預取(把全域配額切片發給各節點)。
- **熔斷**:網關對 upstream 的斷路器(連續失敗→快速失敗→半開探測);與 ch03 健康檢查的分工。↪ 算法指 `system-design/01`。
- **load shedding / 卸載**:過了飽和點主動丟低優先級請求、按隊列長度/延遲卸載。↪ 過載/背壓指 `concurrency-capacity/07-overload-backpressure/`。
- **降級**:返回兜底/快取/默認值,保核心棄枝節。
- 面試高頻點:「分散式限流幾台網關怎麼共享計數」「限流算法選型」「網關過載怎麼辦」。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**

```bash
for p in redis-handson/13-rate-limiting system-design/01-韌性-依賴掛了怎麼不崩.md concurrency-capacity/07-overload-backpressure; do test -e "$p" && echo OK $p || echo MISSING $p; done
grep -E "^#{1,3} " gateway/05-traffic-control.md
```
人工自檢:分散式限流的 local vs global / Redis-Lua / 預取 三條都講到。

- [ ] **Step 3: 回填 README,Commit**

```bash
git add gateway/05-traffic-control.md gateway/README.md
git commit -m "docs(gateway/05): 流量控制 — 分散式限流(local/global/Redis-Lua/預取)+熔斷+卸載+降級"
```

---

## Task 8: Lab — 分散式限流(ch05 配套,2 節點 + Redis)

**Files:**
- Create: `gateway/lab/distributed-rate-limit/docker-compose.yml`
- Create: `gateway/lab/distributed-rate-limit/app.py`
- Create: `gateway/lab/distributed-rate-limit/ratelimit.lua`
- Create: `gateway/lab/distributed-rate-limit/README.md`

**Interfaces:**
- Consumes: ch05 的 global counter + Redis-Lua 概念。
- Produces: 兩個應用節點共享一個 Redis 限流計數,證明「合起來才是全域配額」。

- [ ] **Step 1: 寫 Lua 腳本(固定窗口原子限流)**

`ratelimit.lua`:`INCR` key,首次 `EXPIRE` 設窗口;返回當前計數;超過 limit 返回拒絕。原子性由 Lua 在 Redis 單線程內保證。

- [ ] **Step 2: 寫 app.py(FastAPI 兩實例共用)**

`/ping` 端點:每請求對 `rate:{client}` 跑 Lua(limit=10/10s),超限回 429。讀環境變數 `NODE_ID` 標識自己。

- [ ] **Step 3: 寫 compose**

`redis` 一個 + `node1`/`node2` 兩個 app(同 image,不同 `NODE_ID`,各曝 8001/8002)。

- [ ] **Step 4: 起並驗證(我自己跑)**

```bash
cd gateway/lab/distributed-rate-limit && docker compose up -d
# 交替打兩個節點共 12 次(limit=10),應在第 11 次起被 429,證明計數是共享的
for i in $(seq 1 12); do
  port=$([ $((i%2)) -eq 0 ] && echo 8001 || echo 8002)
  curl -s -o /dev/null -w "%{http_code} " localhost:$port/ping
done; echo
docker compose down
```
Expected:前 10 次 `200`,第 11、12 次 `429`(兩節點合計觸頂,證明 global counter)。

- [ ] **Step 5: 寫 lab README + Commit**

```bash
git add gateway/lab/distributed-rate-limit
git commit -m "docs(gateway/lab): 分散式限流可跑範例(2 節點 + Redis Lua,證明共享計數)"
```

---

## Task 9: Ch06 協議轉換與聚合 🔬

**Files:**
- Create: `gateway/06-protocol-translation-and-aggregation.md`

- [ ] **Step 1: 寫 `gateway/06-protocol-translation-and-aggregation.md`**

🔬 內幕正文必須講到:
- **協議轉換**:gRPC-JSON transcoding(外部 REST/JSON ↔ 內部 gRPC,靠 proto 註解);HTTP/1.1 ↔ HTTP/2 ↔ HTTP/3(QUIC)在網關的轉接。
- **請求/回應改寫**:加減 header、改 path、改 body(注入/脫敏)。
- **API 聚合 / BFF 模式**:一次外部請求扇出多個後端再合併(降低行動端往返);BFF(每端一個網關)vs 通用網關的取捨。↪ BFF/通信範式指 `system-design/04`。
- **WebSocket / SSE 穿透**:長連線怎麼過網關(Upgrade、連線保持、超時設定、和限流/鑑權的衝突)。↪ 協議細節指 `network/`。
- 面試高頻點:「網關怎麼把 REST 轉 gRPC」「BFF 解決什麼」「長連線過網關注意什麼」。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**

```bash
for p in system-design/04-服務化與通信範式.md network; do test -e "$p" && echo OK $p || echo MISSING $p; done
grep -E "^#{1,3} " gateway/06-protocol-translation-and-aggregation.md
```

- [ ] **Step 3: 回填 README,Commit**

```bash
git add gateway/06-protocol-translation-and-aggregation.md gateway/README.md
git commit -m "docs(gateway/06): 協議轉換/改寫/BFF 聚合/WebSocket-SSE 穿透"
```

---

## Task 10: Ch07 可觀測性:邊緣觀測 🔬

**Files:**
- Create: `gateway/07-observability-at-the-edge.md`

- [ ] **Step 1: 寫 `gateway/07-observability-at-the-edge.md`**

🔬 內幕正文必須講到:
- **為什麼網關是天然觀測點**:所有南北向流量必經,一處埋點覆蓋全入口。
- **統一訪問日誌**:結構化欄位(latency、status、upstream、consumer、route)。
- **traceId 注入與傳播**:網關生成/接收 trace context、W3C `traceparent` 注入往後端、和 OTel 的對接。
- **邊緣 RED 指標**(Rate/Errors/Duration)按 route/consumer 維度;為什麼 golden signals 在邊緣最全。
- **取樣與成本**:全量 trace 太貴,網關做頭部/尾部取樣的取捨。
- ↪ 一般可觀測性/日誌教學指 `observability/`、`logging/`,本章只講「網關視角」。
- 面試高頻點:「分散式追蹤 traceId 從哪來、怎麼傳」「為什麼把監控放網關」。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**

```bash
for p in observability logging; do test -e "$p" && echo OK $p || echo MISSING $p; done
grep -E "^#{1,3} " gateway/07-observability-at-the-edge.md
```

- [ ] **Step 3: 回填 README,Commit**

```bash
git add gateway/07-observability-at-the-edge.md gateway/README.md
git commit -m "docs(gateway/07): 邊緣可觀測性 — 統一日誌/traceparent 傳播/RED/取樣取捨"
```

---

## Task 11: Ch08 網關自己是個分散式系統 🔬

架構師寶藏章(全倉空白)。把「網關不只是轉發器,它自己是要被治理的分散式叢集」講透。

**Files:**
- Create: `gateway/08-gateway-as-distributed-system.md`

- [ ] **Step 1: 寫 `gateway/08-gateway-as-distributed-system.md`**

🔬 內幕正文必須講到:
- **配置 / 控制面**:Envoy **xDS**(LDS/RDS/CDS/EDS,控制面動態推路由與 cluster);Kong **DB vs DB-less**(declarative config);APISIX **+ etcd**(配置存 etcd、節點 watch)。對比「靜態 reload」與「動態下發」。
- **不斷連的熱更新**:改配置怎麼不斷現有連線(Nginx `reload` 起新 worker 接新連線、老 worker 處理完舊連線再退;Envoy 熱重啟/動態下發)。
- **網關 HA**:多節點 + 前置 L4 LB / DNS / VIP(keepalived);網關無狀態化(把限流計數、session 外移到 Redis,回扣 ch05)。
- **網關自身的藍綠 / 金絲雀**:升級網關本身怎麼不斷流。
- **避免網關變 SPOF / 瓶頸**:它是全站入口,掛了全掛——容量規劃、隔離、為什麼不能把太多重邏輯堆網關。
- 面試高頻點:「網關配置怎麼動態下發」「網關會不會單點」「網關怎麼無狀態擴展」。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**

```bash
grep -E "^#{1,3} " gateway/08-gateway-as-distributed-system.md
```
人工自檢:xDS / 熱更新 / HA 無狀態 / SPOF 四塊都到機制層。

- [ ] **Step 3: 回填 README,Commit**

```bash
git add gateway/08-gateway-as-distributed-system.md gateway/README.md
git commit -m "docs(gateway/08): 網關作為分散式叢集 — xDS控制面/熱更新/HA無狀態/SPOF"
```

---

## Task 12: Ch09 控制面 vs 資料面 + Service Mesh 邊界 🔬

整合 + 指路章。mesh 深度已在現有 track,本章只把邊界與決策講死,深挖出口連過去。

**Files:**
- Create: `gateway/09-data-plane-control-plane-and-mesh.md`

- [ ] **Step 1: 寫 `gateway/09-data-plane-control-plane-and-mesh.md`**

🔬 內幕正文必須講到:
- **資料面 vs 控制面**通用區分(資料面跑流量、控制面下發策略),回扣 ch08 的 xDS。
- **南北向(網關)vs 東西向(mesh)**:邊界畫死,什麼流量歸誰管。
- **為什麼有了網關還要 mesh**:服務間的 mTLS/重試/熔斷/可觀測下沉到 sidecar,業務碼零侵入。
- **sidecar vs ambient**(決策級,不重挖內幕):sidecar 每 Pod 一個 Envoy 太貴(↪ 成本量化 `performance-tuning-roadmap/12-container/04-service-mesh-perf.md`);ambient(ztunnel + waypoint)/ eBPF(Cilium)去 sidecar 的方向。
- **Gateway API / GAMMA 收斂**:k8s 用同一套 API 收南北向 + 東西向。
- ↪ 深挖出口集中列:`cloud-native-landscape/04`、`cloud-native/03b`、`cloud-native/05`、`cloud-native-landscape/03`。
- 面試高頻點:「網關和 service mesh 區別」「sidecar 為什麼貴、ambient 解決什麼」。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**

```bash
for p in cloud-native-landscape/04-service-mesh-sidecar-to-ambient.md performance-tuning-roadmap/12-container/04-service-mesh-perf.md cloud-native/03b-control-and-data-plane-internals.md cloud-native/05-networking.md cloud-native-landscape/03-networking-ebpf-and-gateway-api.md; do test -e "$p" && echo OK $p || echo MISSING $p; done
grep -E "^#{1,3} " gateway/09-data-plane-control-plane-and-mesh.md
```
人工自檢:深挖出口路徑全部存在且在文中出現;mesh **未重挖內幕**,只到決策/邊界。

- [ ] **Step 3: 回填 README,Commit**

```bash
git add gateway/09-data-plane-control-plane-and-mesh.md gateway/README.md
git commit -m "docs(gateway/09): 控制/資料面 + 南北東西邊界 + sidecar→ambient 決策(深挖指路)"
```

---

## Task 13: Ch10 AI / LLM 網關 🔬

幾乎全新、貼合轉型方向的章。

**Files:**
- Create: `gateway/10-ai-llm-gateway.md`

**Interfaces:**
- Produces: LLM 網關的能力清單(token 限流 / 語義快取 / 模型路由 / 護欄),ch10 lab 實作其中兩項。

- [ ] **Step 1: 寫 `gateway/10-ai-llm-gateway.md`**

🔬 內幕正文必須講到:
- **為什麼 LLM 流量要專屬網關**:請求貴(秒級、按 token 計費)、流式、供應商多且會掛——通用 API 網關的「按請求數限流」不夠用。
- **按 token 限流與預算**:不是 QPS,是 tokens/min(TPM)+ requests/min(RPM);預估輸出 token、超預算降級到小模型/拒絕;按租戶/key 的成本配額。
- **語義快取**:把 prompt 向量化,用 embedding 相似度(cosine + 閾值)命中近似歷史回答,省一次 LLM 調用;和精確快取的差別、誤命中風險與閾值取捨;向量存儲(Redis/pgvector)。
- **模型路由 / 多供應商容錯**:按成本/能力/延遲選模型、供應商故障 failover、金絲雀新模型。
- **prompt / 輸出護欄**:prompt 注入偵測、PII 脫敏、輸出審核(moderation),掛在管線哪段。
- **SSE 串流穿透**:流式回應怎麼過網關(邊收邊轉、token 計數在流結束才準)。
- **成本歸因**:按 key/租戶記 token 與費用。
- 工具對照:LiteLLM、Portkey、Kong AI Gateway、Envoy AI Gateway。↪ AI 基建指 `cloud-native-landscape/10-ai-infra-serving-and-inference.md`、`ai/`。
- 面試高頻點:「LLM 網關和普通 API 網關差在哪」「語義快取怎麼做、風險」「按 token 限流怎麼算」。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**

```bash
for p in cloud-native-landscape/10-ai-infra-serving-and-inference.md ai; do test -e "$p" && echo OK $p || echo MISSING $p; done
grep -E "^#{1,3} " gateway/10-ai-llm-gateway.md
```

- [ ] **Step 3: 回填 README,Commit**

```bash
git add gateway/10-ai-llm-gateway.md gateway/README.md
git commit -m "docs(gateway/10): AI/LLM 網關 — token限流/語義快取/模型路由/護欄/SSE/成本"
```

---

## Task 14: Lab — 最小 LLM 網關(ch10 配套)

**Files:**
- Create: `gateway/lab/mini-llm-gateway/docker-compose.yml`
- Create: `gateway/lab/mini-llm-gateway/gateway.py`
- Create: `gateway/lab/mini-llm-gateway/fake_llm.py`
- Create: `gateway/lab/mini-llm-gateway/README.md`

**Interfaces:**
- Consumes: ch10 的 token 限流 + 語義快取概念。
- Produces: 一個前置 LLM 網關,實作 token 預算限流 + 語義快取,後端接一個可離線跑的 fake LLM(避免依賴真 key,符合「本機可驗」)。

- [ ] **Step 1: 寫 fake_llm.py**

一個 FastAPI 服務模擬 `/v1/chat`:回固定/回顯文本,並在回應裡帶 `usage.total_tokens`(用簡單 `len(text.split())` 估)。可離線跑,不需真 key。

- [ ] **Step 2: 寫 gateway.py**

FastAPI 網關 `/chat`:
- **語義快取**:對 prompt 算 embedding —— 為離線可跑,用輕量本地向量化(`hashlib` 不行,需相似度;用 `sentence-transformers` 的小模型,或退而求其次用字元 n-gram + 餘弦近似並在 README 註明是教學近似)。存 Redis(向量 + 回答);新 prompt 算相似度 ≥ 閾值(如 0.9)就命中返回快取,不打後端。
- **token 預算限流**:每 client 維護 Redis 計數 `tokens:{client}`,窗口內累計 token 超 `BUDGET`(如 100)就回 429。

- [ ] **Step 3: 寫 compose**

`redis` + `fake-llm` + `gateway`(曝 9000)。

- [ ] **Step 4: 起並驗證(我自己跑)**

```bash
cd gateway/lab/mini-llm-gateway && docker compose up -d
# (a) 語義快取:近義兩問,第二次應命中快取(回應標記 cached=true 且未打後端)
curl -s -X POST localhost:9000/chat -d '{"client":"u1","prompt":"什麼是 API 網關"}'
curl -s -X POST localhost:9000/chat -d '{"client":"u1","prompt":"API 網關是什麼"}'
# (b) token 預算:連打到累計 token 超 BUDGET,後續回 429
for i in $(seq 1 8); do curl -s -o /dev/null -w "%{http_code} " -X POST localhost:9000/chat -d '{"client":"u2","prompt":"講一段長文本測試 token 預算限流機制"}'; done; echo
docker compose down
```
Expected:(a) 第二次回應 `cached=true`;(b) 累計 token 觸頂後出現 `429`。

- [ ] **Step 5: 寫 lab README(含「語義快取用教學近似、生產用真 embedding」說明)+ Commit**

```bash
git add gateway/lab/mini-llm-gateway
git commit -m "docs(gateway/lab): 最小 LLM 網關(token 預算限流 + 語義快取,離線可跑)"
```

---

## Task 15: Ch11 選型與生產 playbook

**Files:**
- Create: `gateway/11-selection-and-production-playbook.md`

- [ ] **Step 1: 寫 `gateway/11-selection-and-production-playbook.md`**

內容:
- **選型對照表**:Nginx / Envoy / Kong / APISIX / Spring Cloud Gateway / 雲託管(AWS API Gateway、ALB、GCP/Azure 等價物)—— 維度:動態配置能力、插件生態、性能、運維成本、適用場景、語言生態綁定。標明「關鍵 × 好換」邏輯(逃生票:能不能自托管)。
- **何時用哪個**:小團隊/邊緣靜態 → Nginx;k8s 原生動態 → Envoy/APISIX;要插件生態 → Kong/APISIX;Java 微服務內嵌 → Spring Cloud Gateway;不想自運維 → 雲託管(但注意鎖定)。
- **遷移路徑**:Nginx → APISIX/Envoy 怎麼漸進。
- **生產清單**:超時/重試/限流默認值、健康檢查、灰度開關、可觀測接好、容量與壓測、SPOF 演練。
- **故障模式 debug playbook**:網關 5xx 飆升、延遲毛刺、限流誤殺、配置下發失敗、連線池打滿——各自怎麼定位。
- 章末問答。

- [ ] **Step 2: 標準章節 Verify**

```bash
grep -E "^#{1,3} " gateway/11-selection-and-production-playbook.md
```
人工自檢:選型表生態平衡(不綁死 Java);debug playbook 有可操作定位步驟。

- [ ] **Step 3: 回填 README,Commit**

```bash
git add gateway/11-selection-and-production-playbook.md gateway/README.md
git commit -m "docs(gateway/11): 選型對照(Nginx/Envoy/Kong/APISIX/SCG/雲託管)+ 生產 playbook"
```

---

## Task 16: Ch99 面試卡片

**Files:**
- Create: `gateway/99-interview-cards.md`

- [ ] **Step 1: 寫 `gateway/99-interview-cards.md`**

內容(複習層,不承載新知識,答案要點都已在前面正文,卡片只濃縮 + 指回章節):
- **白板大題**:「設計一個 API 網關」滿分答法骨架——先畫管線(ch02)→ 路由/LB(ch03)→ 鑑權(ch04)→ 流控(ch05)→ 觀測(ch07)→ 叢集/HA(ch08),一條龍串起來。
- **高頻陷阱卡**(每張:問題 + 一句要點 + 回扣章節):
  - 限流放鑑權前還後?(ch02)
  - 網關會不會變 SPOF、怎麼破?(ch08)
  - 有網關為何還要 service mesh?(ch09)
  - JWT 為何能在網關無狀態校驗?(ch04)
  - 分散式限流幾台網關怎麼共享計數?(ch05)
  - L4 vs L7 各用在哪?(ch01)
  - LLM 網關和普通網關差在哪?(ch10)
  - 網關配置怎麼動態熱更新?(ch08)
- 章末:面試一句話總綱(網關 = 邊緣橫切關注點的集中地)。

- [ ] **Step 2: 標準章節 Verify**

```bash
grep -E "^#{1,3} " gateway/99-interview-cards.md
```
人工自檢:每張卡都回扣到某章,無新知識。

- [ ] **Step 3: 回填 README,Commit**

```bash
git add gateway/99-interview-cards.md gateway/README.md
git commit -m "docs(gateway/99): 面試卡片 — 白板大題骨架 + 8 張高頻陷阱卡"
```

---

## Task 17: README 收尾 + 全 track 交叉引用地圖

所有章寫完後,把 README 從骨架補成完整索引。

**Files:**
- Modify: `gateway/README.md`

- [ ] **Step 1: 補完 README**

- 校正每章一句話 hook(對齊已寫內容)。
- 「學習路徑」建議:面試衝刺(00→02→05→08→09→99)vs 系統通讀(順序)。
- **交叉引用地圖**:一張表列出本 track ↪ 出去的所有現有 track 深礦(即 Global Constraints 那張路徑表),讓讀者知道延伸去哪。
- lab 索引(3 個,各一句 + 怎麼跑)。

- [ ] **Step 2: 全 track 連結自檢**

```bash
# 確認 12 章 + 99 + 3 lab 都在
ls gateway/*.md gateway/lab/*/README.md
# 確認 README 提到的交叉引用路徑都存在
for p in system-design/01-韌性-依賴掛了怎麼不崩.md system-design/04-服務化與通信範式.md system-design/05-服務治理設施.md system-design/10-安全-網路分區與認證授權.md redis-handson/13-rate-limiting concurrency-capacity/07-overload-backpressure performance-tuning-roadmap/10-distributed/02-retry-ratelimit.md cloud-native-landscape/04-service-mesh-sidecar-to-ambient.md performance-tuning-roadmap/12-container/04-service-mesh-perf.md cloud-native/03b-control-and-data-plane-internals.md cloud-native/05-networking.md cloud-native-landscape/03-networking-ebpf-and-gateway-api.md cloud-native-landscape/10-ai-infra-serving-and-inference.md; do test -e "$p" && echo OK || echo "MISSING $p"; done
```
Expected:所有檔案在;所有交叉引用路徑 OK。

- [ ] **Step 3: Commit**

```bash
git add gateway/README.md
git commit -m "docs(gateway): README 收尾 — 完整索引 + 學習路徑 + 交叉引用地圖"
```

---

## Self-Review(寫完計畫後對 spec 的覆蓋自檢)

- **Spec 覆蓋**:spec 12 章 + 99 + 3 lab + README,逐一對應 Task 1–17 ✅。spec「不在範圍」清單 → 由 Global Constraints + 各章 ↪ 步驟落實 ✅。
- **Placeholder 掃描**:各章 task 給的是**具體要講到的機制點清單**(master-worker、xDS、Lua 原子、語義快取閾值…),非「補上內幕」這種空話;lab 給了實際 compose/驗證命令與預期輸出 ✅。
- **型別/命名一致**:管線階段序在 ch02 定義,ch03/04/05 引用同一串;分散式限流 local/global counter 在 ch05 定義,ch08 回扣;LLM 能力清單在 ch10 定義,lab 實作其中兩項 —— 一致 ✅。
- **執行說明**:本 track 是文件,task cycle 改為「draft→自檢清單+路徑驗證→commit」;3 個 lab 保留真實「起服務→驗證→預期輸出」且由執行者自跑自驗(不交 VM 作業給使用者)。
```
