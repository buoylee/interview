# 設計 spec:`service-governance-on-k8s/` mini-track

> 日期:2026-06-25
> 來源:三個架構問題(Spring Cloud↔k8s 整合、長連接 LB、Go/Python 怎麼做分佈式),經兩輪 brainstorm + 生產現況調研收斂。
> 狀態:設計已批准,待寫正文。

---

## 1. 身份與目標

**一句話身份:** 橫切關注點下沉 —— 從 Spring Cloud 全家桶切入,看每一層在 k8s/mesh 時代「去哪了」,結論語言中立。

**要回答的五個子問題(全部要講透,不能停在「選一個」):**

| 子問題 | 落到 | 核心 |
|---|---|---|
| ① 整合時如何選相同定位組件 | Ch02 上半 | 同層選一 + 選型框架 |
| ② 相同定位但**特性不同**怎麼處理 | Ch02 下半 | **特性差補法矩陣**(不是選一就完) |
| ③ **服務內部**(東西向)長連接 | Ch03 + LAB | 你控兩端 → kube-proxy 釘 pod + 修法 |
| ④ 需要**和 client**(南北向)長連接 | Ch04 | 你**不控** client → 另一套工具箱 |
| ⑤ Go/Python 如何**和 k8s 整合** | Ch05 | 講契約不是講框架 |

**定位:** 坐在現有 component stub 之上;**取代** `spring-cloud/`+`nacos/` 死 stub(標註被吸收,不刪);**指向**既有深礦(不重講 k8s 基礎)。

**Level & style(沿用 house style):** 资深/架构师;🔬 黑盒內幕寫進正文;架構師視角(失敗模式 / 規模化極限 / 選型論證);章末問答**只做複習自檢、不承載新知**;生態平衡、不綁 Java。

---

## 2. 放置與命名

- 新建**頂層** mini-track:`service-governance-on-k8s/`(與 `system-design/05-服務治理設施` 詞彙一致,交叉引用自然)。
- 落地副作用:
  - 在 `system-design/05` 加 2-3 行薄指路;`system-design/04` 加一行。
  - `spring-cloud/`、`nacos/` 死 stub:在各自 README/概述頂部標註「已被 `service-governance-on-k8s/` 取代/吸收」,**不刪**(保留歷史筆記)。

---

## 3. 章節結構(5 章 + README + lab)

### README — 下沉地圖 + 導讀
- 「分佈式要哪些能力 → 三實現層(library / platform / mesh)」總圖。
- 本 track 在既有 tracks 中的位置 + 交叉引用表。
- 一句話總綱:fat-client/smart-library → thin-client/smart-platform。

### 01 — Spring Cloud 全家桶 + Netflix OSS 2026 現況
- 起點:Eureka / Ribbon / Feign / Hystrix / Zuul / Config 各管什麼。
- **事實校準**(見 §5):Hystrix/Ribbon/Zuul1/Archaius **已移除(2020.0)**;Eureka **仍活仍維護**。
- 替代:Spring Cloud Circuit Breaker + **Resilience4j**、**Spring Cloud LoadBalancer**、Spring Cloud Gateway(**2025.1 拆 webflux/webmvc 兩模塊**)。
- 引出「下沉」命題:這些 library 能力為何開始外移(語言無關、與發版解耦、運維可控)。

### 02 — 整合與選型:同層選一 + 特性差怎麼補(子問題 ①②)
- **上半「選一」:** 為什麼同層不能兩套並行(雙重真相源 / 雙重記帳故障域);選型框架(greenfield vs brownfield、混合 VM+k8s、polyglot、中國 Nacos、運維成熟度)。
- **下半「同定位、不同特性」(子問題 ② 關鍵)—— 特性差補法矩陣:**
  1. 先列你*真正用到*的特性(不是組件全部特性)。
  2. 看 k8s-native 等價物有沒有、語義同不同 → 四種處置:
     - **(a) 保留富 registry**(Nacos 留著只為它的權重 / 元數據 / 推送)。
     - **(b) 下沉到 mesh**(灰度 / 權重 / 重試 → Istio VirtualService;熔斷 → sidecar)。
     - **(c) app 層自己實現**(讀 Endpoints 自己算)。
     - **(d) 砍掉**(很多「特性」其實沒人用)。
     - 兩邊都有但語義不同 → **別並存,選一**,避免雙重真相源。
- **具體例子(逐層):**
  - 發現:CoreDNS = name→ready-pod-IP,**沒有**權重 / 實例元數據 / 主動推送 / 灰度;Nacos/Eureka 有。要按 metadata 灰度路由?→ mesh 或保留 Nacos。
  - 配置:ConfigMap = 靜態掛載 + 滾動重啟生效 vs Nacos = 動態推送 / 監聽 / 灰度。要免重啟熱更?→ spring-cloud-kubernetes 的 ConfigMap watch、或保留 Nacos。
  - LB:kube-proxy = 連接級隨機 / 輪詢,**無** zone-aware / 權重 vs Ribbon/SCLB = 客戶端可 zone-aware。→ 下沉 mesh locality LB 或客戶端 LB。
  - 熔斷:Resilience4j(app 內、業務級、細粒度)vs mesh(網路級、語言無關、粗粒度)—— **不是選一,是分工**。

### 03 — 長連接 LB ①:服務內部 / 東西向(子問題 ③)+ LAB
- 前提:你**控兩端**(自家服務調自家服務)。
- 機制:gRPC HTTP/2 單 TCP 連接多路復用 + kube-proxy **L4 連接級** → 請求釘一個 pod;scale up 不動;DB 連接池同理。
- 修法(按真實使用排序):
  - ① headless Service + 客戶端 `round_robin`(**坑:gRPC 默認 `pick_first` 不分散,設 `round_robin` 才是 load-bearing 那步**)+ `MaxConnectionAge` 逼重解析。
  - ② mesh L7(Linkerd/Istio,透明 + polyglot + mTLS)。
  - ③ proxyless gRPC / xDS —— **仍 experimental,不當主流**。
- 🔬 黑盒:kube-proxy iptables / IPVS / Cilium **都是 L4,都不解決**(只有 L7 或客戶端能)。
- → **lab**(見 §4)。

### 04 — 長連接 ②:對 client / 南北向(子問題 ④)
- 前提:你**不控** client(瀏覽器 / 手機)→ 工具箱完全不同。
- LB 層換人:雲 L4 LB(NLB,**注意默認 idle timeout 會砍長連接**)/ L7 Ingress-Gateway(Gateway API)/ 專用 WS 網關。
- **逼不動 client 重解析**:server gRPC 能 `MaxConnectionAge` 逼重連,瀏覽器不行 → 靠 client 端重連邏輯 + 指數退避 + **抖動 jitter**(避免發版後 thundering herd 同時重連)。
- sticky vs 均衡衝突:WebSocket 狀態留在某 pod → session affinity 的代價。
- 發版 / 縮容:存量長連接 → 連接排空(drain)+ preStop sleep + client reconnect;心跳 / keepalive 對抗 idle timeout。
- WebSocket vs SSE vs long-poll 差異。
- → 指向 `distribution/zero-downtime-release/05-connection-lifecycle`(排空機制深礦)。

### 05 — Go/Python ↔ k8s 整合 + polyglot 收口(子問題 ⑤)
- **核心倒轉:** Spring Cloud = app 主動向 registry 註冊(push);k8s = app 被動暴露契約、平台來探測(pull)。Go/Python「和 k8s 整合」= 講好這份契約:
  - 發現:啥都不做 → Service DNS;要實例級 → client-go / kubernetes(py) watch Endpoints/EndpointSlice。
  - 配置:env(ConfigMap/Secret 注入)/ 掛載文件 + fsnotify 熱讀 / Downward API。
  - 健康:暴露 liveness / readiness / startup 探針(HTTP `/healthz` 或 gRPC Health 協議);readiness 控流量灌入。
  - 生命週期:收 SIGTERM → 停收新請求 → drain → 退;preStop hook;配合滾動發布。
  - 選主 / 鎖:client-go leaderelection(Lease 對象)/ python kube-leader —— 是 **k8s API** 給的,不是語言給的。
- *然後才是*框架補位:
  - Go:West = stdlib-first(raw gRPC / connect-go + net/http + k8s,**無重框架**);China = Kratos(**B站,非阿里**)/ Kitex(字節)/ go-zero / Dubbo-go;**go-kit 凍結(2023)、go-micro 轉向 AI-agent harness —— 兩者剔除**。
  - Python:**無 Spring Cloud 等價**,FastAPI + 任務隊(Celery **或** Dramatiq/Arq/Temporal)+ k8s 原語;Nameko niche/declining。
- 收口:共識 / 協調(選主 / 鎖 / 強一致配置)**不分語言**都靠 etcd/ZK/Consul —— Spring Cloud 自己也沒解決。**折 folklore:mesh 採用率 CNCF 2024 = 42%,比前年 50% 下降** → 多數團隊用 k8s 原語 + 小庫,不是 mesh。fat-client vs thin-client,是時代差不是語言差。

---

## 4. Lab 規格(`lab/`,Q2 唯一實跑)

- **語言:** Go(快、又練 Go)。
- **環境:** kind(本機 k8s;kube-proxy L4 釘連接行為在純 docker-compose 重現不出來,必須真 k8s)。
- **步驟:**
  1. kind 起集群 → 部署 Go gRPC echo 服務(回傳服務 pod 的 hostname)scale 3 副本。
  2. client 迴圈打 RPC,日誌看**請求全打一個 pod**;scale up 仍不動 → 親眼看到 pinning。
  3. 換 ① headless Service + 客戶端 `round_robin`,看請求**分散到三個 pod**。
  4. (選配)② Linkerd inject,看 L7 透明分散(不改 client code)。
- **`lab/README.md`:** 給步驟 + **使用者自己跑出的數字**(不貼預設輸出);明確標 kind 前置。

---

## 5. 事實校準清單(2026 —— 寫正文時務必照這個,別寫回 folklore)

1. **Spring Cloud Gateway 現為兩模塊**(`gateway-server-webflux` / `-webmvc`);舊 starter 名 2025.1 移除。單模塊框架已過時。
2. **Eureka 仍出貨仍維護**(唯一倖存的 Netflix 模塊);只有 Hystrix/Ribbon/Zuul/Archaius/Turbine 被移除。熔斷要點名 **Spring Cloud Circuit Breaker**(不只 Resilience4j)。
3. **Service mesh 是下降中的少數派**(CNCF 2024:42%,從 50% 降)—— 不是 70%,也不是 k8s 默認發現機制。忽略引用「70%」的二手 blog。
4. **Sidecar-less(ambient)GA 且贏 greenfield,但不是已完成的取代**;brownfield 仍以 sidecar 為主。別寫「ambient/eBPF 取代了 sidecar」。Istio ambient GA = 1.24(2024-11)。
5. **Gateway API**:引 **v1.5(2026-02)**;TLSRoute/GRPCRoute/BackendTLSPolicy 現已 stable;只剩 TCPRoute/UDPRoute + Mesh/GAMMA 還 experimental。加 **ingress-nginx EOL(2026-03-31)** 信號。「Ingress 凍結、未廢除/未排程移除」。
6. **iptables 仍是 kube-proxy 默認**,即使 nftables 在 1.33 GA。
7. **Proxyless gRPC / xDS 在 Istio 仍 experimental** —— 別當主流。
8. **Go 框架**:Kratos = **B站(非阿里)**;go-micro 已轉向 AI-agent harness(剔除為微服務推薦);China 群補 **go-zero**;go-kit 凍結(2023)。
9. **Python**:任務隊軟化為「Celery **或** Dramatiq/Arq/Temporal」。
10. **gRPC 客戶端默認 `pick_first` 不做負載均衡**,設 `round_robin` 才分散 —— 這是 load-bearing 的一步。

---

## 6. 越界清單(YAGNI —— 明確不做)

- 不重講:k8s Service/kube-proxy/CoreDNS 基礎(→ `cloud-native/05-networking`)、mesh sidecar→ambient 內幕(→ `cloud-native-landscape/04`)、LB 算法細節(→ `gateway/03`)、共識 Raft/Zab(→ `distribution/`)、連接排空機制細節(→ `zero-downtime-release/05`)。**全部指路,不複製。**
- 不做 Q1(Ch02)/ Q3(Ch05)的 lab;不做多語言運行環境(lab 只 Go)。

---

## 7. 交叉引用契約(寫正文時要連的)

- `system-design/05-服務治理設施` ←→ 本 track(深化發現/LB/mesh);雙向連結 + spine 加薄指路。
- `system-design/04-服務化與通信範式`(RPC/框架)→ 本 track Ch05 polyglot。
- `cloud-native/05-networking`(Service/kube-proxy/CoreDNS 基礎)← Ch02/03 引用,不重講。
- `cloud-native-landscape/04-service-mesh`(mesh 內幕)← Ch02/03/04 指向。
- `gateway/03-routing-and-load-balancing`(LB 算法)← Ch04 指向。
- `distribution/zero-downtime-release/05-connection-lifecycle`(排空)← Ch04 指向。
- `spring-cloud/`、`nacos/`(死 stub)→ 本 track 取代/吸收。
