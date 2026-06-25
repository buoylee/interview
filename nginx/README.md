# Nginx 這門手藝 — 資深/架構師面試 + 日常工作向

> **一句定位:**`gateway/` 已把「這台引擎為什麼快」講透;本 track 補的是另一半——**怎麼用這台引擎幹活、調它、救它**。面向資深/架構師面試與日常 Nginx 工作的完整手藝教學。

---

## 脊柱:從「引擎內幕」到「手藝實戰」

```
   gateway/01  ─────────────────────────►  nginx/  (本 track)
   引擎內幕                                  手藝實戰
   ┌──────────────┐                        ┌────────────────────────────────┐
   │ master-worker │                        │ 怎麼寫 location / rewrite        │
   │ epoll 事件迴圈 │   坐在其上               │ 怎麼配 proxy_cache / limit_req   │
   │ upstream 連線池│   ──────────────────►  │ 怎麼平滑 reload / 熱升級          │
   │ TLS 終止       │                        │ 怎麼調 worker / buffer / 內核     │
   │ L4 vs L7      │                        │ 怎麼讀 log 定位 502/504/連線耗盡 │
   └──────────────┘                        └────────────────────────────────┘
   「為什麼快」(↪ 指過來)                      「怎麼動手」(本 track 自擁)
```

---

## 章節索引

### 地基段:Nginx 是什麼 + 設定語言

| # | 章 | 一句話 |
|---|---|---|
| 00 | [決策地圖](00-decision-map.md) | Nginx 四種身份、「設定即程式」心智模型、何時**不該**用 Nginx |
| 01 | [設定模型:區塊、繼承、location 匹配](01-config-model.md) 🔬⭐ | `location` 優先級五檔規則、`add_header` 繼承陷阱、`if is evil` 的真相 |
| 02 | [rewrite / return / 內部跳轉](02-rewrite-and-internal-redirect.md) | `last`/`break`/`redirect`/`permanent` 差異、`try_files` 回退鏈、命名 location |

### 角色段:Nginx 各種幹活方式

| # | 章 | 一句話 |
|---|---|---|
| 03 | [當 web server:靜態與 FastCGI](03-web-server.md) | `sendfile` 零拷貝、`gzip`/`brotli` 壓縮、`Range` 斷點續傳、FastCGI/php-fpm |
| 04 | [反向代理與 upstream](04-reverse-proxy-and-upstream.md) 🔬⭐ | `proxy_pass` 尾斜線陷阱、必設 header、超時三件套、連線池健康檢查 |
| 05 | [快取 proxy\_cache:Nginx 當 CDN-lite](05-proxy-cache.md) 🔬 | cache key 怎麼算、`cache_lock` 防擊穿、micro-caching、HIT/MISS/STALE 調試 |
| 06 | [Nginx 層流量控制](06-rate-limiting.md) | `limit_req` 三種 burst 行為、`limit_conn`/`limit_rate`、單機邊界與何時外移 |
| 07 | [TLS 實戰](07-tls.md) | 憑證/SNI/OCSP stapling/session 復用/mTLS/Let's Encrypt 自動化 |

### 運維與性能段:怎麼調、怎麼救

| # | 章 | 一句話 |
|---|---|---|
| 08 | [運維與零停機](08-operations-zero-downtime.md) 🔬⭐ | 訊號表、reload 為什麼不丟連線、USR2→WINCH→QUIT 熱升級二進制 |
| 09 | [性能調優](09-performance-tuning.md) 🔬 | worker/連線上限/sendfile 三件套/reuseport/內核參數聯動 |
| 10 | [可觀測與除錯 playbook](10-observability-debugging.md) 🔬⭐ | 499/502/503/504 成因表、連線耗盡定位、stub\_status、症狀→根因 playbook |

### 外圈段(輕量)

| # | 章 | 一句話 |
|---|---|---|
| 11 | [外圈:OpenResty + ingress-nginx](11-openresty-and-ingress.md) | Lua 掛哪個 phase、`lua_shared_dict`、Ingress 資源→config→reload 這一跳 |
| 12 | [選型與「何時從 Nginx 畢業」](12-selection-and-graduation.md) | vs Caddy/Envoy/HAProxy/APISIX/雲託管、畢業判據、生產 checklist |
| 99 | [面試卡片](99-interview-cards.md) | 高頻題 30 秒口述答法 + 白板大題骨架 |

### Lab(可跑,本機自驗)

| lab | 對應章 | 證明什麼 |
|---|---|---|
| [`lab/config-matching/`](lab/config-matching/) | 01/02 | 發各種請求,看 `location`/`rewrite` 命中哪段 |
| [`lab/proxy-cache/`](lab/proxy-cache/) | 05 | 觀察 HIT/MISS/STALE 與 `cache_lock` 防擊穿 |
| [`lab/rate-limit/`](lab/rate-limit/) | 06 | `burst`/`nodelay` 三種行為實測,看 429 幾時出現 |
| [`lab/zero-downtime/`](lab/zero-downtime/) | 08 | 壓測中 `reload`,證明不丟一個連線 |

> 反向代理基礎 lab 已在 `gateway/lab/nginx-reverse-proxy/`,本 track 不重做。

---

## 學習路徑

### 面試衝刺線(時間緊,覆蓋高頻考點)

```
00(身份/心智模型)
  → 01(設定模型,location 優先級 ⭐)
  → 04(反向代理,proxy_pass/超時 ⭐)
  → 08(零停機 reload/熱升級 ⭐)
  → 10(502/504/連線耗盡 ⭐)
  → 99(卡片快速過)
```

這條線覆蓋「Nginx 能幹嘛/怎麼配反代/為什麼不丟連線/怎麼定位故障」這四大面試主戰場。

### 系統通讀線(日常工作 + 徹底掌握)

```
00 → 01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11 → 12 → 99
  ↑                    ↑         ↑              ↑
lab/config-matching  lab/proxy-cache  lab/rate-limit  lab/zero-downtime
```

每章末做章末問答自檢;每個 lab 跑一遍對應章的規則就從抽象變成看得見的行為。

---

## 不在這裡學什麼(去這些深礦)

本 track 只補「Nginx 怎麼動手」的增量;以下主題一律交叉引用現有深礦,不重寫:

| 主題 | 去哪裡 |
|---|---|
| 代理引擎內幕:epoll/master-worker/連線池/TLS 為何貴/L4-L7 | ↪ [`gateway/01-reverse-proxy-engine.md`](../gateway/01-reverse-proxy-engine.md) |
| 請求管線 / filter chain 抽象 | ↪ [`gateway/02-request-pipeline.md`](../gateway/02-request-pipeline.md) |
| 鑑權概念 / JWT / mTLS 概念 | ↪ [`gateway/04-edge-authn-authz.md`](../gateway/04-edge-authn-authz.md)、[`system-design/10-安全-網路分區與認證授權.md`](../system-design/10-安全-網路分區與認證授權.md) |
| 限流/熔斷/降級**演算法本身** | ↪ [`gateway/05-traffic-control.md`](../gateway/05-traffic-control.md)、[`system-design/01-韌性-依賴掛了怎麼不崩.md`](../system-design/01-韌性-依賴掛了怎麼不崩.md)、[`distribution/限流算法/`](../distribution/限流算法/) |
| 分散式限流 Redis/Lua 原子實作 | ↪ [`redis-handson/13-rate-limiting/`](../redis-handson/13-rate-limiting/)、[`gateway/05-traffic-control.md`](../gateway/05-traffic-control.md) |
| 負載均衡 L4/L7 演算法、服務發現 | ↪ [`system-design/05-服務治理設施.md`](../system-design/05-服務治理設施.md) |
| Mesh / 控制面 / xDS / 熱更新抽象 | ↪ [`gateway/08-gateway-as-distributed-system.md`](../gateway/08-gateway-as-distributed-system.md)、[`gateway/09-data-plane-control-plane-and-mesh.md`](../gateway/09-data-plane-control-plane-and-mesh.md) |
| k8s 網路 / Ingress / Gateway API / eBPF | ↪ [`cloud-native/05-networking.md`](../cloud-native/05-networking.md)、[`cloud-native-landscape/03-networking-ebpf-and-gateway-api.md`](../cloud-native-landscape/03-networking-ebpf-and-gateway-api.md) |
| epoll / 事件模型內核實現 | ↪ [`performance-tuning-roadmap/00-os-fundamentals/`](../performance-tuning-roadmap/00-os-fundamentals/) |
| 內核參數 / TCP 調優 | ↪ [`performance-tuning-roadmap/00-os-fundamentals/`](../performance-tuning-roadmap/00-os-fundamentals/) |
| 一般可觀測性 / 日誌體系 | ↪ [`observability/`](../observability/)、[`logging/`](../logging/) |
| HTTP 協議 / CORS 細節 | ↪ [`network/http.md`](../network/http.md)、[`frontend/cross-origin/`](../frontend/cross-origin/) |
| 完整網關選型 / AI 網關 | ↪ [`gateway/11-selection-and-production-playbook.md`](../gateway/11-selection-and-production-playbook.md)、[`gateway/10-ai-llm-gateway.md`](../gateway/10-ai-llm-gateway.md) |

🔬 = 本章自擁「黑盒裡發生什麼」的內幕層。
⭐ = 面試主戰場,含白板答法話術。
