# 03 · 網絡環:eBPF/Cilium + Gateway API

> **一句話定位**:容器跑起來了,**Pod 之間怎麼連、外部流量怎麼進來**?這一環是 2020 後變化**最大**的——數據面從 iptables/kube-proxy 換成 **eBPF/Cilium**,入口從 Ingress 換成 **Gateway API**(而 ingress-nginx 已在 2026-03 退役)。

> **本章深度層**:混合。Pod 網絡模型/Service 機制細部在 `cloud-native/05`;本章把 **eBPF 和 Gateway API 這兩個「變了的部分」寫深**,基礎指進。

---

## 🕰 變遷盒

| | 舊世界(2019-2020) | 新世界(2026) |
|---|---|---|
| Service 負載均衡 | **kube-proxy + iptables**(規則線性膨脹) | **eBPF / Cilium**(內核直連,可換掉 kube-proxy) |
| 網絡策略 | 基於 IP 的 NetworkPolicy(L3/L4) | 基於**身份(identity)**的策略,Cilium 還能到 **L7** |
| 入口網關規範 | **Ingress** + 一堆 annotation | **Gateway API**(角色分離、強類型、L4/L7) |
| 入口實現 | **ingress-nginx**(社區裝機第一) | ingress-nginx **2026-03 退役**;主流轉 **Envoy 系 / Cilium** |
| 數據面底層 | nginx | **Envoy / eBPF**(nginx 不再是默認假設,見開篇的網關回答) |

---

## 1. 核心敘事

### 1.1 Pod 網絡模型(沒變的地基)

k8s 網絡只有幾條鐵律:**每個 Pod 一個 IP、所有 Pod 扁平互通(無 NAT)、容器共享 Pod IP**。具體怎麼實現交給 **CNI 插件**(Cilium/Calico/雲 CNI)。這部分是地基,細節指進 `cloud-native/05`。

### 1.2 Service 與 kube-proxy:為什麼 iptables 撐不住

Pod IP 會變(重建就換),所以要 **Service** 提供穩定 VIP。誰把「訪問 Service VIP」變成「轉發到某個後端 Pod」?傳統是 **kube-proxy**,它在每個節點寫 **iptables** 規則。

問題在規模:**iptables 是線性匹配的規則鏈**。Service 和 endpoint 一多,規則數爆炸:

- 每個 Service × 每個後端 → 一串規則;**幾千個 Service 就是幾萬條 iptables 規則**。
- 每次 endpoint 變化,kube-proxy 要**重刷一大片規則**,同步延遲到秒級。
- 數據面每個包要**線性走規則鏈**匹配,延遲與規則數正相關。

IPVS 模式用哈希表把匹配做到 O(1) 緩解了一部分,但仍在 netfilter 框架裡。

### 1.3 eBPF/Cilium:把網絡邏輯下沉進內核

**eBPF** 讓你把小程序**安全地掛到內核的 hook 點**(socket、tc、XDP)上,在內核裡直接決策,不走 iptables/netfilter。Cilium 用它把 Service 負載均衡、NetworkPolicy 全做進 eBPF:

```
傳統:  包 → netfilter → iptables 規則鏈(線性) → 轉發
eBPF:  包 → eBPF 程序(查 eBPF map：service→backend，O(1)) → 直接轉發
```

關鍵躍遷:

- **可完全換掉 kube-proxy**(`kube-proxy replacement`):沒有 iptables 規則膨脹,大規模下同步快、轉發穩。
- **基於身份的策略**:Cilium 給每組 Pod 一個**安全身份(identity)**,策略基於身份而非易變的 IP——這對「Pod IP 一直變」的雲原生世界天然契合。
- **L7 可見 + Hubble 可觀測**:能看到並控制到 HTTP 方法/路徑層級,Hubble 提供網絡流量地圖(接 05 章可觀測)。

### 1.4 入口:Ingress 凍結 → Gateway API

**Ingress** 表達力太弱:只有 host/path 路由,其他全靠 `nginx.ingress.kubernetes.io/...` 這類 **annotation 硬塞**——不可移植、不可校驗、實現之間語義不一致(annotation 地獄)。Ingress API 已**凍結**。

**Gateway API**(GA v1.0,2023;2026 已 v1.2/1.3+)是替代品,核心是**角色分離 + 強類型**:

```
GatewayClass   ← 平台團隊:選哪個實現(Envoy Gateway / Istio / Cilium)
   │
Gateway        ← 集群運維:開哪些監聽端口、TLS、給誰用
   │
HTTPRoute      ← 應用開發:我的 /orders 路由到 order-api（還有 GRPCRoute/TCPRoute/TLSRoute）
```

每個角色管自己那層,互不踩;路由是**強類型對象**(不是 annotation 字符串),可校驗、可移植。

**而它只是規範,不轉發流量**——要挑一個實現(數據面)。詳見開篇那段網關回答:2026 主流是 **Envoy 系**(Envoy Gateway / Istio / Contour)和 **eBPF(Cilium)**;**ingress-nginx 社區版 2026-03 退役**,遷移工具 `ingress2gateway`。

---

## 🏛 架構師視角

### 🔬 黑盒內幕

- **eBPF hook 點**:XDP(網卡驅動最早期,最快,可做 DDoS 丟包)、tc(流量控制層)、socket(連接建立時直接把目標改寫成後端 Pod,連 DNAT 都省)。Service→backend 映射存在 **eBPF map**(內核態哈希表),查找 O(1)。
- **Cilium identity**:把「一組相同 label 的 Pod」壓成一個數字身份,策略和負載均衡都基於它;身份變化通過內核 map 同步,不需要重刷規則。
- **Gateway API 實現**:控制面 watch Gateway/HTTPRoute 對象 → 翻譯成數據面(Envoy)配置 → Envoy/eBPF 真正轉發。這又是一個「控制器 reconcile」(回扣第 01 章)。

### 💥 失敗模式 / 故障域

| 故障 | 現象 | 根因 |
|---|---|---|
| iptables 規則爆炸 | Service 變更生效慢(秒級)、節點 CPU 高 | kube-proxy iptables 模式在數千 Service 下線性膨脹 |
| **Cilium 高路由 churn 脆弱** | 高連接/高路由變更下**丟流量、需重啟組件** | Cilium Gateway API 在大規模 churn 下實現偏脆(真實基準);L4 強、L7 成熟度仍在追 |
| DNS 成瓶頸/SPOF | 大量服務間調用超時、p99 抖動 | CoreDNS 過載 / `ndots:5` 導致每次查詢多輪;DNS 是隱形熱點 |
| conntrack 表打滿 | 新連接被丟、`nf_conntrack: table full` | 高並發短連接耗盡連接跟蹤表 |
| ingress-nginx 帶債運行 | 已退役,**不再有 CVE 補丁** | IngressNightmare(CVE-2025-1974)等;繼續用 = 帶已知漏洞跑 |

### 📈 規模化極限

- **iptables**:規則數 ≈ O(Service × Endpoint);**數千 Service 後**同步延遲與轉發延遲明顯劣化 → 這是「該換 eBPF」的拐點。
- **IPVS**:哈希 O(1) 匹配,比 iptables 好,但仍需逐 Service 維護虛擬服務。
- **eBPF**:map 查找 O(1),大規模 Service 下表現最穩——但要吃較新內核,且 L7/Gateway 在極端 churn 下要壓測。
- **DNS**:`ndots` + search domain 會把一次查詢放大成多次;大集群要給 CoreDNS 擴副本 + NodeLocal DNSCache。

### ⚖️ 選型論證

**CNI / 數據面**:

| 方案 | 何時選 | 取捨 |
|---|---|---|
| **Cilium(eBPF)** | 現代默認;要高性能 Service LB、身份策略、L7 可觀測 | 吃新內核;Gateway/L7 極端規模要壓測 |
| **Calico** | 成熟穩、策略強;可選 eBPF 或 iptables 模式 | 經典 iptables 模式有上面的膨脹問題 |
| **雲 CNI(如 AWS VPC CNI)** | 要 Pod 直接拿 VPC IP、和雲網絡/安全組原生整合 | 受 ENI/IP 配額限制;策略能力較弱(常配 Cilium chaining) |

**入口(Gateway API 實現)**:Envoy Gateway(中立、最成熟)/ Istio(已有網格就順手)/ Cilium(已用 Cilium CNI 就統一)。**ingress-nginx 不在新選項裡**。

### 🧭 演進路徑

1. **kube-proxy → Cilium replacement**:換 CNI 為 Cilium 並開啟 kube-proxy replacement,消除 iptables 膨脹。
2. **Ingress → Gateway API**:用 `ingress2gateway` 把現有 Ingress(含 annotation)轉成 Gateway/HTTPRoute,逐步切流。
3. **ingress-nginx 退役應對**:現在用 ingress-nginx = 帶安全債運行,**列入遷移計畫**(這是當前最緊急的一件事)。

### 🏭 生產事故 / 教訓

- **IngressNightmare(CVE-2025-1974,2025-03)**:ingress-nginx 經暴露的 admission webhook 可未授權 RCE,影響極廣 → 直接推動退役。教訓:**入口組件是攻擊面最大的一塊,安全與維護人力是選型硬指標**。
- **DNS 拖垮一切**:服務間調用全走 DNS,CoreDNS 一過載 p99 全面抖動。教訓:DNS 要當**一級依賴**做容量規劃 + NodeLocal 緩存。

---

## 2. 現在主流怎麼選

| 決策 | 2026 主流答案 |
|---|---|
| CNI / 數據面 | **Cilium(eBPF)** 默認;Calico 穩健備選;雲場景常用雲 CNI + Cilium |
| Service LB | **eBPF kube-proxy replacement**,告別 iptables 膨脹 |
| 入口規範 | **Gateway API**(不再用 Ingress 新建) |
| 入口實現 | Envoy Gateway / Istio / Cilium(**不用 ingress-nginx**) |
| DNS | CoreDNS + NodeLocal DNSCache,擴副本 |
| 網絡策略 | 基於身份(Cilium),需要時上 L7 策略 |

---

## 🧵 示例服務在這一環

外部用戶要訪問 `order-api`:流量經 **Gateway**(監聽 443 + TLS)→ **HTTPRoute**(`/orders` → order-api Service)→ Cilium eBPF 在內核把目標直接改寫成某個 order-api Pod IP(無 iptables、無多餘 DNAT)。

`order-api → inventory` 的內部調用:走 Service VIP,Cilium eBPF 在 socket 層直接定位後端;策略上用**身份**規則「只有 order-api 身份能訪問 inventory 的 8080」——Pod 重建 IP 變了也不影響,因為策略綁的是身份不是 IP。

> 注意:order→inventory 之間的**重試、超時、mTLS、細粒度可觀測**,這一環只給到 L3/L4 + 基礎 L7;要把這些做成「業務代碼不用管」,是下一環**服務網格**的事。

---

## 🔬 深挖出口

| 想深挖 | 去哪 |
|---|---|
| Pod 網絡/CNI、Service 三型、kube-proxy、Ingress、DNS、NetworkPolicy(機制細部) | `cloud-native/05-networking` |
| kube-proxy 包路徑、數據面故障域 | `cloud-native/03b-control-and-data-plane-internals` |
| 2026 網關全景(實現 / 數據面對照 / ingress-nginx 退役) | 見本對話開篇的網關回答 |
| Service 沒流量 / DNS 失敗的 debug 決策樹 | `cloud-native/09-debug-networking-and-nodes` |

---

## 一句收口 + 地圖更新

> **網絡這一環在 2020 後幾乎重寫**:數據面從「iptables 線性規則」下沉到「eBPF 內核 O(1) + 身份策略」,入口從「Ingress + annotation 地獄」升級到「Gateway API 角色分離」,而曾經的默認入口 ingress-nginx 已退役。底層也不再默認是 nginx,而是 Envoy / eBPF。

**🗺 地圖更新**:你補上了「連接」這一環的當代真相,知道 iptables 的拐點、Cilium 的強弱、Gateway API 的角色模型、入口安全的教訓。
**下一站**:`04 服務間環` —— L3/L4 通了,但服務之間的 **mTLS / 重試 / 熔斷 / 細粒度追蹤** 誰來做?這是第一個「你 2019 完全沒這格」的外環:**服務網格**(寫滿深度)。
