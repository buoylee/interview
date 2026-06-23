# 09 · 控制面 vs 資料面 + Service Mesh 邊界 🔬

> 一句話:把 ch08 的「控制面/資料面」從**網關**擴展到**整個服務網絡**,然後畫死一條面試最愛考的邊界——**API 網關管南北向(入口),Service Mesh 管東西向(服務間)**。本章只講**邊界與決策**;mesh 的內幕/性能/演化你倉庫裡已有深礦,深挖出口直接連過去,**不重挖**。

---

## 1. 🔬 控制面 vs 資料面(從網關放大到網絡)

ch08 講過網關自己的控制/資料面。同一個二分法是整個雲原生網絡的通用結構:

- **資料面 data plane**:真正搬運每個封包/請求的元件(網關進程、每個服務旁的 sidecar 代理)。**在請求路徑上**,性能敏感。
- **控制面 control plane**:不碰具體請求,只負責**算策略、下發配置**(路由、mTLS 證書、限流規則)給資料面。**不在請求路徑上**。

**為什麼解耦(架構師必答)**:資料面掛了影響流量,控制面掛了**通常不影響已下發配置的現有流量**(資料面用最後一份配置繼續跑),只是「暫時不能改配置/不能感知新實例」。這個**故障域隔離**是設計目標——控制面不該是請求路徑上的單點。

> 🔗 控制面/資料面在 k8s 裡的具體運轉(list-watch/informer、etcd 作真相源、kube-proxy 數據路徑、leader election)在 **`cloud-native/03b-control-and-data-plane-internals.md`** 已深講。

---

## 2. 🔬 南北向 vs 東西向:網關和 Mesh 的分工(本章核心)

回扣 ch00 那條軸,現在講透:

```
        外部 client
            │  南北向(north-south)= 入口流量
            ▼
   ┌─────────────────┐
   │   API 網關        │  ← 管南北向:外部鑑權、面向用戶的限流、協議轉換、BFF
   └─────────────────┘
            │
   ┌────────┼────────┐   東西向(east-west)= 服務間流量
   ▼        ▼        ▼   ← 管東西向:服務間 mTLS、重試、熔斷、細粒度流量切分
[svc A]══[svc B]══[svc C]
  每個服務旁一個 sidecar 代理(Envoy),這層就是 Service Mesh 的資料面
```

| | **API 網關(南北)** | **Service Mesh(東西)** |
|---|---|---|
| 管什麼流量 | 外部 ↔ 系統入口 | 服務 ↔ 服務(內網) |
| 典型職責 | 面向用戶的鑑權、限流、BFF、協議轉換 | 服務間 mTLS、重試、熔斷、可觀測、流量切分 |
| 部署形態 | 邊緣幾個集中節點 | 每個 Pod 旁一個 sidecar(或 ambient,見 §3) |
| 認識誰 | 外部用戶/租戶 | 服務身份(SPIFFE/證書) |

**🔬 有了網關為什麼還要 mesh?** 服務間調用也需要重試、熔斷、加密、追蹤,但你**不想在每個服務的業務碼裡重寫一遍**(N 個服務 × M 種語言)。mesh 把這些能力**下沉到 sidecar 代理**,業務碼**零侵入**——服務只管發普通請求,sidecar 自動加 mTLS、自動重試、自動上報 trace。一句話:**網關把橫切能力集中在入口;mesh 把同類能力下沉到每個服務旁。互補,不是二選一。**

---

## 3. 🔬 sidecar vs ambient:mesh 的代價與換代(決策級)

mesh 主流嗎?**雙峰**:大廠/大規模 k8s 基本標配,中小團隊普遍「mesh 疲勞」——因為 **sidecar 太貴**。

- **經典 sidecar 模型**:每個 Pod 注入一個 Envoy。一次服務間調用要過 **2 次 Envoy 代理 + 1 次 mTLS 加解密**,且**每個 Pod 都背一份代理的 CPU/記憶體開銷**。
  > 🔗 **成本量化在 `performance-tuning-roadmap/12-container/04-service-mesh-perf.md`**:1000 個 Pod × 每 sidecar ~80MB = 80GB 記憶體、~100 核 CPU 純開銷。這就是反對票的數字依據。
- **換代方向(現代趨勢)**:正因 sidecar 太重,主流在往「**去 sidecar**」走——
  - **Istio Ambient Mesh**(~2024 GA):用節點級的 **ztunnel**(處理 L4 + mTLS)+ 按需的 **waypoint** 代理(處理 L7),**不再每 Pod 一個 Envoy**,開銷大降。
  - **eBPF / Cilium**:把部分網絡治理下沉到內核 eBPF,繞過用戶態代理。
  > 🔗 sidecar→ambient 的完整演化敘事在 **`cloud-native-landscape/04-service-mesh-sidecar-to-ambient.md`**。

**決策一句話**:服務少、團隊小 → 先別上 mesh(用客戶端庫或網關兜著);服務多、要統一零信任 mTLS 和服務間治理 → 上 mesh,但**優先評估 ambient/eBPF** 而非經典 sidecar,省掉那筆每 Pod 開銷。

---

## 4. 🔬 收斂:Gateway API 把南北和東西統一

過去南北(Ingress/網關)和東西(mesh)是兩套不同的配置模型,割裂。現在在收斂:

- **k8s Gateway API**(Ingress 的繼任者):用一套標準的 `Gateway` / `HTTPRoute` 資源描述入口路由,比舊 Ingress 表達力強得多(多協議、流量切分、跨 namespace)。
- **GAMMA 倡議**:把同一套 Gateway API 也用來描述**東西向(mesh)**的路由——**南北和東西用同一套 API**,不再學兩套。
  > 🔗 eBPF/Cilium + Gateway API 的全景在 **`cloud-native-landscape/03-networking-ebpf-and-gateway-api.md`**;k8s 網絡模型/Ingress 基礎在 **`cloud-native/05-networking.md`**。

---

## 本章小結

- **控制面(算策略/下發,不在請求路徑)vs 資料面(搬流量,性能敏感)**;解耦是為了**故障域隔離**——控制面掛了不影響已下發配置的現有流量。
- **南北向 = API 網關(入口、面向用戶),東西向 = Service Mesh(服務間、零侵入下沉)**;互補不互斥。
- mesh 採用雙峰;經典 **sidecar 每 Pod 一個 Envoy 開銷大**(成本見深礦),主流往 **ambient / eBPF** 去 sidecar 換代。
- **Gateway API + GAMMA** 把南北和東西收斂到一套 API。
- 本章只到決策/邊界;mesh 內幕、性能、演化的深挖全在 `cloud-native*` 與 `performance-tuning-roadmap`。

## 章末問答(複習自檢,答案要點都在前面正文)

1. 控制面和資料面各自負責什麼?為什麼要解耦(從故障域角度答)?
2. 「網關和 Service Mesh 的區別」一句話怎麼答?有了網關為什麼還需要 mesh?
3. 經典 sidecar 模型的開銷來自哪裡?為什麼大規模下會被詬病?ambient/eBPF 是怎麼改善的?
4. 一個只有十幾個服務的小團隊,該不該上 service mesh?為什麼?
5. Gateway API 和 GAMMA 在收斂什麼?
