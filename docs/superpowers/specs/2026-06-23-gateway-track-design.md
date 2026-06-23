# `gateway/` Track 設計 Spec — 邊緣可程式化代理(Nginx → API 網關 → [Mesh 邊界] → AI 網關)

- 日期:2026-06-23
- 狀態:設計已批准,待寫 implementation plan
- 語言:**繁體中文**(技術名詞保留英文)
- 落點:倉庫根目錄新建獨立 track `gateway/`,與 `concurrency-capacity/`、`cloud-native/` 平級

---

## 1. 動機與定位

面試對「網關」非常看重,因為它是**橫切關注點(cross-cutting concerns)的集中地**:一道「設計一個 API 網關」的題,實際在考能不能把 **限流 + 熔斷 + 鑑權 + 路由 + 可觀測性** 整合進一個高吞吐的接入層。這是資深/架構師面試的分水嶺題。

倉庫現況:**零件齊全,但缺「以網關為主角」的整合篇**。限流、熔斷、認證授權、負載均衡、過載背壓、Service Mesh 都已散落在多個 track,但沒有一份把「邊緣接入層」當主角、講清請求進來到打到後端之間網關按序做了什麼、每件事的內部實現與取捨。

本 track 補的就是這個缺口。

### 核心心智模型(整個 track 的脊柱)

> **網關 = 站在邊緣的「可程式化代理 programmable proxy」。後面每一層 = 前一層 + 更多「認識業務」的橫切能力。**

```
                     認識的東西越來越「懂業務」 →
┌─────────────┬──────────────────┬───────────────────┬─────────────────┐
│ 反向代理      │   API 網關         │  Service Mesh      │  AI / LLM 網關    │
│ Nginx/HAProxy│  Kong/APISIX/      │  Istio+Envoy/      │  LiteLLM/Portkey/ │
│              │  Envoy/SC Gateway  │  Linkerd (sidecar) │  Envoy AI Gateway │
│ host/path 路由│ +認證/授權/限流     │ 治理下沉到 sidecar  │ +模型路由/token   │
│ TLS/LB/靜態  │ +熔斷/協議轉換/聚合 │ 管東西向(服務間)   │ +語義快取/護欄    │
│ (config 驅動) │ 認識用戶/API/配額   │ (網關管南北向)      │ 認識 token/模型   │
└─────────────┴──────────────────┴───────────────────┴─────────────────┘
```

- **Nginx** 認識 `host / path / IP` → 路由與限流只能到 IP 粒度。
- **API 網關** 認識 `用戶 / API / 配額` → 能做「此用戶每秒只能調 10 次此 API」「token 過期打回」。
- **Service Mesh** 同樣治理能力但**下沉**到 sidecar,管東西向;網關管南北向。
- **AI 網關** 認識 `token / 模型 / prompt / 成本` → 是 API 網關針對 LLM 流量的特化版。

## 2. 目標讀者與深度

- 讀者:本人(5 年+ Java/Go 後端,正轉 Python/LLM,面試導向自學)。
- 深度:**資深/架構師級**。每章必含 🔬 內幕層(黑盒裡發生什麼:存儲/索引/底層取捨),不 defer。
- 生態:**生態平衡**,默認雲原生/語言無關;Java(Spring Cloud Gateway)僅在真主流處當錨點,配 Go/Python 等價物。樣例工具優先開源、透明且真生產(Nginx/Envoy/APISIX/Kong/LiteLLM)。
- 教法:底層內幕寫進正文教學,章末問答只做複習自檢,不承載新知識。

## 3. 整合策略(查重結果 + 如何融入現有內容)

**本 track 自己擁有(新寫,深度所在):**
1. 反向代理引擎內幕(proxy 在 socket/事件層做什麼)
2. 請求管線 / filter chain(整個 track 的組織骨架)
3. 網關作為分散式叢集的治理(配置/控制面、熱更新、HA、SPOF)
4. AI / LLM 網關(全倉幾乎空白)

**其餘一律交叉引用現有深礦,不重寫**(與 `system-design` 當 master 索引「指进深矿不重写」同一玩法):

| 主題 | 現有位置 | 本 track 態度 |
|---|---|---|
| 韌性六件套(限流/熔斷/降級算法) | `system-design/01-韌性-依賴掛了怎麼不崩.md` | ↪ 交叉引用,只補「在網關管線哪段跑、叢集怎麼共享計數」 |
| 認證 vs 授權 / RBAC-ABAC | `system-design/10-安全-網路分區與認證授權.md` | ↪ 交叉引用,只補「邊緣鑑權、JWT 下沉、mTLS 終止」 |
| 負載均衡 L4/L7 | `system-design/05-服務治理設施.md` | ↪ 交叉引用,只補「網關側 upstream 選擇/連線池」 |
| API 網關 / BFF(概念,輕) | `system-design/04-服務化與通信範式.md` Part D | 吸收並升級成主角 |
| 分散式限流(Lua 原子實作) | `redis-handson/13-rate-limiting/` | ↪ 當實作 lab 指過去 |
| 過載/背壓/load shedding | `concurrency-capacity/07-overload-backpressure/` | ↪ 交叉引用 |
| Nginx 限流配置 / 重試風暴 | `performance-tuning-roadmap/10-distributed/02-retry-ratelimit.md` | ↪ 交叉引用,補「Nginx 作為代理的引擎內幕」 |
| Service Mesh 演化(sidecar→ambient) | `cloud-native-landscape/04-service-mesh-sidecar-to-ambient.md` | ↪ 深挖出口,不重挖 |
| Service Mesh 性能/成本量化 | `performance-tuning-roadmap/12-container/04-service-mesh-perf.md` | ↪ 深挖出口 |
| 控制面/資料面內幕、k8s Ingress | `cloud-native/03b-control-and-data-plane-internals.md`、`cloud-native/05-networking.md` | ↪ 深挖出口 |
| eBPF/Cilium + Gateway API | `cloud-native-landscape/03-networking-ebpf-and-gateway-api.md` | ↪ 深挖出口 |
| epoll / 事件模型 | `performance-tuning-roadmap/00-os-fundamentals/`、`python-concurrency/00` | ↪ 交叉引用 |
| 可觀測性 / 日誌 | `observability/`、`logging/` | ↪ 交叉引用 |
| AI 基建 / serving | `cloud-native-landscape/10-ai-infra-serving-and-inference.md`、`ai/` | ↪ 交叉引用 |

**mesh 決策結論**:mesh 夠主流(大廠標配,中小團隊有「mesh 疲勞」因 sidecar 太貴;架構正從 sidecar→ambient/eBPF 換代),但深度倉庫已有(見上三處)。故本 track 對 mesh = 一章「整合 + 指路」(南北/東西邊界、sidecar vs ambient 決策),不從零重挖。

## 4. 章節目錄(12 章 + 卡 + lab)

檔名用英文 slug(可移植,對齊 `cloud-native`/`concurrency-capacity`),內容繁體。標記:🔬=本章自擁內幕,↪=交叉引用,🧪=lab,⭐=面試主戰場。

### 地基段(代理是什麼)

**`00-decision-map.md` · 決策地圖:網關是什麼、何時不需要**
脊柱全圖、南北向 vs 東西向、什麼場景**不該**上網關(避免過度設計)。對標 `concurrency-capacity/00` 決策管線風格。

**`01-reverse-proxy-engine.md` · 反向代理:網關的引擎** 🔬⭐
🔬 代理在 socket 層做什麼:Nginx master-worker + epoll 事件模型、upstream 連線池/keepalive、TLS 終止(握手卸載)、L4 vs L7 代理的本質差異。
↪ epoll/事件模型 → `perf-roadmap/00-os-fundamentals`、`python-concurrency/00`;限流配置語法 → `perf-roadmap/10-distributed/02`。
🧪 跑 nginx 反代,觀察 worker/連線復用。

### 主戰場段(代理 → API 網關)

**`02-request-pipeline.md` · 請求管線 / Filter Chain:網關的靈魂** 🔬⭐
🔬 **整個 track 的骨架**:請求按序流過 `接收→匹配路由→認證→授權→限流→改寫→轉發 upstream→回應過濾→埋點`。Envoy filter chain / Kong plugin phases / APISIX / Spring Cloud Gateway GlobalFilter 都是這套。順序為什麼要緊(限流放鑑權前還後)。

**`03-routing-and-load-balancing.md` · 路由與負載均衡:送對地方** 🔬⭐
🔬 路由匹配(host/path/header/權重)、upstream 健康檢查、灰度/金絲雀發布(流量切分)、邊緣的超時/重試。
↪ LB L4/L7 算法 → `system-design/05`;重試紀律/退避抖動 → `system-design/01`。

**`04-edge-authn-authz.md` · 邊緣鑑權:認證與授權落在網關** 🔬⭐
🔬 為什麼鑑權下沉到邊緣、JWT 校驗(簽名/exp/aud)、OAuth2/OIDC 在網關、API Key、mTLS 終止、auth offload vs 委派、token introspection、authz(RBAC/ABAC)落點。
↪ 認證 vs 授權概念 → `system-design/10`。

**`05-traffic-control.md` · 流量控制:限流/熔斷/降級/卸載** 🔬⭐
🔬 限流算法在管線哪段跑、per-route/per-consumer 配額、**分散式限流(網關叢集共享計數:local vs global、Redis 後端、同步難題)**、邊緣 load shedding、對 upstream 熔斷。
↪ 算法本身 → `system-design/01`;Lua 原子實作 → `redis-handson/13`;過載/背壓 → `concurrency-capacity/07`。
🧪 兩個網關節點 + Redis 做全域限流。

**`06-protocol-translation-and-aggregation.md` · 協議轉換與聚合:BFF / gRPC↔HTTP / WebSocket** 🔬
🔬 gRPC-JSON 轉碼、HTTP/1↔2↔3、請求/回應改寫、API 聚合(BFF 模式)、WebSocket/SSE 穿透網關。
↪ BFF/通信範式 → `system-design/04`;協議 → `network/`。

**`07-observability-at-the-edge.md` · 可觀測性:網關是天然觀測點** 🔬
🔬 統一訪問日誌、traceId 注入與傳播(W3C traceparent)、邊緣 RED 指標、為什麼網關是 golden signals 最佳採集點。
↪ → `observability/`、`logging/`。

**`08-gateway-as-distributed-system.md` · 網關自己是個分散式系統** 🔬⭐
🔬(架構師寶藏章,全倉空白)配置/控制面(Envoy xDS、Kong DB vs DB-less、APISIX+etcd)、不斷連的熱更新、網關 HA、網關自身的藍綠/金絲雀、避免網關變 SPOF/瓶頸。

### 邊界段(東西向 + 現代化)

**`09-data-plane-control-plane-and-mesh.md` · 控制面 vs 資料面 + Service Mesh 邊界** 🔬
🔬 南北向 vs 東西向講死、為什麼有網關還要 mesh、sidecar vs ambient(決策級)、Gateway API / GAMMA 收斂。
↪ 深挖全部指路:`cloud-native-landscape/04`、`perf-roadmap/12-container/04`、`cloud-native/03b`、`cloud-native/05`、`cloud-native-landscape/03`。

### 特化段(轉型方向)

**`10-ai-llm-gateway.md` · AI / LLM 網關** 🔬⭐
🔬(幾乎全新)為什麼 LLM 流量要專屬網關:按 token 限流與預算、語義快取(embedding 相似度命中)、模型路由/多供應商容錯、prompt/輸出護欄(注入/PII/審核)、成本歸因、SSE 串流穿透。工具:LiteLLM、Portkey、Kong AI Gateway、Envoy AI Gateway。
↪ → `cloud-native-landscape/10-ai-infra`、`ai/`。
🧪 最小 LLM 網關(token 限流 + 語義快取)。

### 收口

**`11-selection-and-production-playbook.md` · 選型與生產 playbook**
Nginx vs Envoy vs Kong vs APISIX vs Spring Cloud Gateway vs 雲託管(ALB / API Gateway);各自何時用、遷移、生產清單、故障模式 debug playbook。

**`99-interview-cards.md` · 面試卡片**
白板題「設計一個 API 網關」滿分答法;高頻陷阱:限流放鑑權前後?網關會不會變 SPOF?有網關為何還要 mesh?JWT 為何能下沉?

**`lab/`** 三個可跑:`nginx-reverse-proxy/`、`distributed-rate-limit/`(2 節點 + Redis)、`mini-llm-gateway/`(token 限流 + 語義快取)。

**`README.md`** track 索引 + 脊柱圖 + 章節導覽 + 與其他 track 的交叉引用地圖。

## 5. 不在範圍(明確不重寫)

- 限流/熔斷/降級**算法本身**的推導(在 `system-design/01`)。
- 認證 vs 授權的**概念基礎**(在 `system-design/10`)。
- Service Mesh 的**內幕/性能/演化深挖**(在 `cloud-native*` 與 `perf-roadmap`)。
- k8s 網路模型、Ingress、CNI、eBPF(在 `cloud-native/05`、`cloud-native-landscape/03`)。
- 一般可觀測性/日誌教學(在 `observability/`、`logging/`)。
本 track 對以上一律 ↪ 指路,只補「網關視角下的增量」。

## 6. 一致性慣例

- 每章結構:開頭一句定位 → 🔬 內幕正文(教學主體)→ 交叉引用 → 本章小結 → 章末問答(複習自檢,答案要點在正文)。
- 每章標注面試高頻點;適當處給「白板答法」話術。
- 樣例可跑、本機可驗;lab 配最小可運行範例與預期輸出。
- 跨生態對照表(Java/Go/雲託管等價物),不綁死單一棧。

## 7. 成功標準

- 讀完能在白板上完整答「設計一個 API 網關」,並串起限流+熔斷+鑑權+路由+可觀測性。
- 能說清反向代理 → API 網關 → mesh → AI 網關的演化與邊界,且不與現有 track 重複。
- 三個 lab 能在本機跑出預期結果。
- 每章 🔬 內幕層真的講「黑盒裡發生什麼」,而非停在高層概念。
