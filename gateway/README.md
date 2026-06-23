# 網關 Gateway — 邊緣的可程式化代理

> 以「**邊緣可程式化代理**」為主角,沿 **Nginx → API 網關 →〔Service Mesh 邊界〕→ AI 網關** 這根脊柱,把分散式系統一大半的橫切知識點(限流、熔斷、鑑權、路由、可觀測性)縫成一個元件。資深/架構師面試向。

## 為什麼單開這個 track

面試愛考網關,因為一道「**設計一個 API 網關**」其實在考你能不能把 **限流 + 熔斷 + 鑑權 + 路由 + 可觀測性** 整合進一個高吞吐的接入層——這正是資深的分水嶺題。倉庫裡這些零件早就齊全(散在 `system-design`、`concurrency-capacity`、`redis-handson`、`cloud-native*` 等),但缺一份**以網關為主角**的整合篇。這個 track 補的就是這個缺口:自己擁有「管線內幕 + 分散式網關 + AI 網關」,其餘一律交叉引用,不重寫。

## 脊柱:網關的演化

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

**核心洞察:後面每一層 = 前一層 + 更多「認識業務」的橫切能力。**

## 章節索引

| # | 章 | 一句話 |
|---|---|---|
| 00 | [決策地圖](00-decision-map.md) | 網關是什麼、南北 vs 東西、何時**不該**上網關 |
| 01 | [反向代理:網關的引擎](01-reverse-proxy-engine.md) 🔬 | master-worker / epoll / 連線池 / TLS 終止 / L4-L7 |
| 02 | [請求管線 / Filter Chain](02-request-pipeline.md) 🔬 | 整個 track 的骨架:一個請求按序流過哪些階段 |
| 03 | [路由與負載均衡](03-routing-and-load-balancing.md) 🔬 | 路由匹配 / 健康檢查 / 灰度金絲雀 / 邊緣超時重試 |
| 04 | [邊緣鑑權](04-edge-authn-authz.md) 🔬 | JWT 無狀態驗簽 / OIDC / mTLS / offload vs 委派 |
| 05 | [流量控制](05-traffic-control.md) 🔬 | 分散式限流 / 熔斷 / load shedding / 降級 |
| 06 | [協議轉換與聚合](06-protocol-translation-and-aggregation.md) 🔬 | gRPC↔HTTP / 改寫 / BFF / WebSocket-SSE 穿透 |
| 07 | [邊緣可觀測性](07-observability-at-the-edge.md) 🔬 | 統一日誌 / traceId 傳播 / RED / 取樣 |
| 08 | [網關自己是個分散式系統](08-gateway-as-distributed-system.md) 🔬 | xDS 控制面 / 熱更新 / HA 無狀態 / SPOF |
| 09 | [控制面/資料面 + Mesh 邊界](09-data-plane-control-plane-and-mesh.md) 🔬 | 南北 vs 東西 / sidecar→ambient 決策 |
| 10 | [AI / LLM 網關](10-ai-llm-gateway.md) 🔬 | token 限流 / 語義快取 / 模型路由 / 護欄 |
| 11 | [選型與生產 playbook](11-selection-and-production-playbook.md) | Nginx/Envoy/Kong/APISIX/SCG/雲託管 + debug |
| 99 | [面試卡片](99-interview-cards.md) | 白板大題骨架 + 高頻陷阱卡 |

🔬 = 本章自擁「黑盒裡發生什麼」的內幕層。

## 學習路徑

- **面試衝刺(時間緊)**:00(地圖)→ 02(管線,骨架)→ 05(限流/併發控制)→ 04(鑑權)→ 08(叢集/SPOF)→ 09(mesh 邊界)→ 99(卡片)。這條線覆蓋「設計一個 API 網關」白板題的全部高頻點。
- **系統通讀**:00 → 11 順序讀完 + 三個 lab 動手跑;每章末做章末問答自檢。
- **LLM 方向**:讀完 00–05 打底後,直奔 10(AI/LLM 網關)+ 跑 `lab/mini-llm-gateway/`。
- **骨架優先**:**02(請求管線)是樞紐**——它定義的階段序被 03/04/05/06/07 反覆引用,先讀通它,其餘章都是「往管線某一段塞一個 filter」。

### Lab(可跑,本機自驗)

| lab | 對應章 | 證明什麼 |
|---|---|---|
| [`lab/nginx-reverse-proxy/`](lab/nginx-reverse-proxy/) | 01 | nginx 反代 + L7 路由 + upstream 輪詢 |
| [`lab/distributed-rate-limit/`](lab/distributed-rate-limit/) | 05 | 2 節點 + Redis Lua,合起來才是全域配額 |
| [`lab/mini-llm-gateway/`](lab/mini-llm-gateway/) | 10 | token 預算限流 + 語義快取(離線可跑) |

## 不在這裡學什麼(去這些深礦)

本 track 只補「網關視角下的增量」,以下基礎/內幕一律指路,不重寫:

- 限流/熔斷/降級**算法本身** → `system-design/01-韌性-依賴掛了怎麼不崩.md`
- 認證 vs 授權**概念**、RBAC/ABAC → `system-design/10-安全-網路分區與認證授權.md`
- 負載均衡 L4/L7、服務發現 → `system-design/05-服務治理設施.md`
- 分散式限流 **Lua 實作** → `redis-handson/13-rate-limiting/`
- 過載/背壓/load shedding → `concurrency-capacity/07-overload-backpressure/`
- Service Mesh **內幕/性能/演化** → `cloud-native-landscape/04`、`performance-tuning-roadmap/12-container/04`、`cloud-native/03b`
- k8s 網路/Ingress/eBPF/Gateway API → `cloud-native/05-networking.md`、`cloud-native-landscape/03`
- 一般可觀測性/日誌 → `observability/`、`logging/`
