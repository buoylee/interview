# 01 · 內核環:重建 k8s 心智模型(聲明式 + 控制器 + reconcile)

> **一句話定位**:圓心這一環,把你天天用卻未必說得清的底層——「**為什麼 k8s 是聲明式 + 控制器 + reconcile**」——重新講透。這不是新知識,是把舊知識**換成正確的心智模型**,後面每一環(GitOps、Operator、mesh 控制面)都建在這個模型上。

> **本章深度層**:內環(架構師視角 + 指進)。機制細部(informer/watch、etcd、leader election、kube-proxy 包路徑)`cloud-native/03b` 已寫深,本章寫**架構師視角**(為什麼這設計、怎麼崩、極限在哪),細部指進。

---

## 🕰 變遷盒

| | 舊世界(2019-2020) | 新世界(2026) |
|---|---|---|
| 怎麼改集群 | `kubectl create/edit/scale`,命令式一條條敲 | **聲明式**:寫 YAML → `apply`,集群自己收斂;再外推成 **GitOps** |
| apply 的語義 | 客戶端 `kubectl apply` 算 diff,容易互相覆蓋 | **Server-Side Apply**(GA 1.22):字段所有權在服務端,多方協作不打架 |
| 擴展 k8s | 改源碼 / 等官方加功能 | **CRD + 控制器(Operator)**:用同一套聲明式模型擴展任何東西 |
| 「內建」的範圍 | Docker、雲廠商、存儲都編進 k8s 源碼樹 | **全部 out-of-tree**:CRI / CSI / CCM / device plugin —— k8s 內核只剩「聲明式 + 控制環」 |

**一句話**:這幾年 k8s 自己最大的演進,不是加了什麼功能,而是**把「聲明式 + 控制器」這個內核打磨成唯一的擴展範式**——你之後學的 mesh、GitOps、DRA,全是這個範式的應用。

---

## 1. 核心敘事:k8s 的本質是一台「狀態收斂機」

把 k8s 所有花哨的對象忘掉,只記一個模型:

> **你聲明「期望狀態(desired)」,k8s 不斷把「實際狀態(actual)」往期望狀態收斂。**

每個對象(Pod、Deployment、Service…)都長這樣:

```yaml
spec:     # 你寫的:我期望什麼(desired state)
  replicas: 3
status:   # k8s 寫的:現在實際怎樣(actual state)
  readyReplicas: 2
```

而所謂「控制器(controller)」,本質就是一個**死循環**:

```
for {
    desired := 讀 spec
    actual  := 觀測世界
    if desired != actual {
        採取行動讓 actual 靠近 desired   // 創建/刪除 Pod、調 API…
    }
}                                        // 這就是 reconcile（調諧）
```

整個 k8s = **一堆這樣的控制器**,各自盯著自己關心的對象,各自 reconcile。Deployment 控制器盯 Deployment→管 ReplicaSet;ReplicaSet 控制器盯 ReplicaSet→管 Pod;scheduler 盯「沒綁節點的 Pod」→綁節點;kubelet 盯「綁到我這台的 Pod」→真的把容器跑起來。**沒有總指揮,只有一群各管一攤的循環。**

### 為什麼這個設計這麼重要:level-triggered,不是 edge-triggered

這是最值錢的一個架構直覺,面試常考:

- **edge-triggered(邊沿觸發)**:對「事件」做反應——「收到 Pod 刪除事件 → 補一個」。問題:**事件丟了就永遠錯了**(消息中間件斷一下、控制器重啟漏了一個事件)。
- **level-triggered(電平觸發)**:對「當前狀態」做反應——「我看現在只有 2 個、期望 3 個 → 補 1 個」。**不管中間漏了多少事件,只要最終看到真實狀態,就能收斂。**

k8s 選 level-triggered。所以控制器**重啟、漏事件、網絡抖動都不怕**:它醒來重新 list 一遍當前狀態,該補補、該刪刪。這就是 k8s「自愈」的根。

> 記憶點:**k8s 的健壯,來自「它永遠在比對當前狀態,而不是依賴別人通知它發生了什麼」。**

### 唯一真相源:API Server + etcd

所有 spec/status 都存在 **etcd**(一致性 KV,Raft 共識),但**沒人直接碰 etcd**——一切讀寫都過 **API Server**(認證、鑑權、admission、校驗、版本轉換)。控制器之間從不互相直接調用,全靠「**讀寫 API Server 上的對象**」隔空協作。

```
   你 / 控制器 / kubelet
          │ (只跟 API Server 說話)
          ▼
   ┌──────────────┐     watch / list      ┌──────────┐
   │  API Server  │◀──────────────────────│ 控制器們  │
   │ (認證/鑑權/   │──────────────────────▶│ scheduler│
   │  admission)  │     create/update     │ kubelet  │
   └──────┬───────┘                       └──────────┘
          │ 唯一寫入者
          ▼
      ┌────────┐
      │  etcd  │  (Raft,集群唯一真相源)
      └────────┘
```

這個「**一切過 API Server、對象是唯一溝通媒介**」的設計,就是為什麼 k8s 能無限擴展控制器(加個 CRD + 控制器就多一種能力),也是 Operator 模式的地基。

---

## 🏛 架構師視角

### 🔬 黑盒內幕(概要,細部指進 03b)

控制器不是真的傻轮询。實際路徑是 **informer 機制**:

```
API Server ──watch──▶ Informer(本地 cache,鏡像一份對象)
                         │ 對象變化 → 丟 key 進
                         ▼
                     WorkQueue(去重 + 限速 + 重試)
                         │ worker 取 key
                         ▼
                     Reconcile(讀本地 cache,不打 API Server 讀)
```

- **watch** 是長連接增量推送(基於 etcd 的 watch),不是輪询;**list** 是全量兜底(重啟/重連時)。
- **本地 cache(informer)**:reconcile 時讀 cache 而非每次打 API Server,否則大集群會把 API Server 讀爆。
- **WorkQueue**:去重(同一對象多次變化合併成一次 reconcile)、限速(失敗指數退避)、重試。
- **樂觀並發**:每個對象有 `resourceVersion`(= etcd revision)。你更新時帶上它,若服務端已變過,寫入被拒(409 Conflict),控制器重試。**這就是為什麼沒有鎖也能多控制器並發改對象。**

### 💥 失敗模式 / 故障域

| 故障 | 會發生什麼 | 為什麼(架構含義) |
|---|---|---|
| **控制面全掛**(API Server/etcd down) | **已跑的 Pod 繼續跑**;但不能擴縮、調度、改配置、自愈 | 數據面(kubelet + 已調度 Pod)和控制面解耦;kubelet 按本地緩存維持現狀 |
| **etcd 故障**(失去 quorum) | 整個集群「凍結」:讀可能還行,寫全停 | etcd 是強一致 Raft,多數派不在就拒寫;**etcd 是集群的命門** |
| **API Server 重啟 / 大量重連** | watch 全斷 → 所有控制器 re-list → **驚群(thundering herd)** 把 API Server 打爆 | 所以大集群要限流(API Priority & Fairness)、控制器要做 list 分頁與限速 |
| **控制器熱循環** | 一個 reconcile bug 導致無限改→觸發→再改,CPU 飆、API Server 被刷 | level-triggered 的代價:reconcile 必須**冪等且收斂**,否則自己打自己 |
| **單個大對象 / 大量對象** | API Server 內存暴漲、watch cache 撐爆、etcd 變慢 | 見下方「規模化極限」 |

> 架構結論:**etcd 和 API Server 是控制面的 SPOF 與瓶頸**。生產上控制面要 HA(多副本 API Server + etcd 奇數節點 quorum + controller-manager/scheduler 用 **leader election** 選主,只有 leader 在 reconcile)。

### 📈 規模化極限(具體數字,架構評審要背)

| 維度 | 量級 / 上限 | 來源 / 含義 |
|---|---|---|
| 單集群節點數 | **~5,000 節點** | k8s 官方可擴展性 SLO 上限 |
| 單集群 Pod 數 | **~150,000 Pod** / ~300,000 容器 | 同上 |
| 單節點 Pod 數 | **~110 Pod**(默認上限) | kubelet 默認 `maxPods` |
| etcd 單值大小 | **默認 ~1.5 MiB** | `--max-request-bytes`;所以別把大 blob 塞進對象/ConfigMap |
| etcd DB 大小 | 默認配額 2 GiB,**建議 ≤ 8 GiB** | 超了 etcd 進入只讀告警,集群寫入停 |

**架構含義**:這些數字決定「什麼時候要拆多集群」。比如你要跑十萬級 Pod、或多租戶爆炸、或 etcd 對象太多——單集群撐不住,就進入**多集群/Fleet**(第 12 章)。也解釋了一個常見坑:**把大配置/證書/日誌塞進 ConfigMap/Secret**,會直接頂到 etcd 值上限或撐大 etcd。

### ⚖️ 選型論證

- **控制面自管 vs 託管(EKS/GKE/AKS)**:99% 的團隊該用**託管控制面**。控制面(etcd 備份、API Server HA、版本升級、證書輪換)是純運維負擔且容易出大事故(etcd 滿盤 = 集群凍結),交給雲廠商;你只管數據面。自管只在「強合規/離線/特殊內核」場景。這也呼應你「依賴 SaaS 不安心」——k8s 的逃生票是:**API 是標準的,託管和自管之間可遷移**,真要自托管控制面也跑得起來。
- **etcd vs 替代**:大集群只有 etcd 是經過考驗的後端;但邊緣/小集群(k3s)用 **kine** 把 etcd API 翻譯到 SQLite/MySQL/PG,省掉 etcd 運維——這是「規模化極限」反過來用:小場景不需要 etcd 的成本。
- **什麼時候上 CRD + Operator**:當你有「需要持續 reconcile 的領域對象」(如「一個資料庫集群該長這樣」),才寫 Operator;只是存配置,用 ConfigMap 就好。**別為了 Operator 而 Operator**——它本質是「你自己寫的一個控制循環」,維護成本不低。

### 🧭 演進路徑

1. **命令式 → 聲明式**:停用 `kubectl scale/edit` 改線上,一切走 YAML + `apply`。
2. **客戶端 apply → Server-Side Apply**:多控制器/多人協作同一對象時,SSA 的「字段所有權」避免互相覆蓋(HPA 改 replicas、你改鏡像,互不踩)。
3. **聲明式 → GitOps**:YAML 進 Git,集群從 Git 收斂(第 06 章)。**注意這在哲學上和 k8s 內核完全同構**:GitOps 就是「把 reconcile 從集群內擴展到『Git ↔ 集群』之間」——Argo CD/Flux 本身就是一個控制器。
4. **in-tree → out-of-tree**:容器運行時(CRI,第 02 章)、存儲(CSI)、雲集成(CCM)、設備(device plugin / DRA,第 09 章)全部插件化。**k8s 內核越縮越小,擴展點越來越標準**。

### 🏭 生產事故 / 教訓

- **etcd 磁盤寫滿 / 超配額** → etcd 進只讀 → 集群無法寫入 → 表現為「kubectl apply 卡住、Pod 調度不動」,但已有 Pod 還在跑(數據面解耦救了你)。教訓:**監控 etcd DB size 與磁盤,定時 compaction + defrag + 備份**。
- **超大 CRD / 海量對象**(如某控制器瘋狂建對象)→ API Server watch cache 撐爆 OOM → 控制面雪崩。教訓:**控制器要對自己創建的對象數量設界,reconcile 要冪等**。

---

## 2. 現在主流怎麼選

| 決策 | 2026 主流答案 |
|---|---|
| 控制面 | **託管**(EKS/GKE/AKS)優先;自管僅特殊場景 |
| apply 方式 | **Server-Side Apply**;線上禁命令式改動 |
| 部署集群狀態 | **GitOps**(第 06 章),Git 為唯一真相源 |
| 擴展能力 | **CRD + 控制器(Operator)**,沿用聲明式範式 |
| etcd 後端 | 大集群原生 etcd;邊緣/小集群 k3s + kine |
| 控制面 HA | 多 API Server + etcd 奇數 quorum + 控制器 leader election |

---

## 🧵 示例服務在這一環

`order-api` 你只寫了一句期望:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: order-api }
spec:
  replicas: 3            # 我要 3 個
  selector: { matchLabels: { app: order-api } }
  template:
    metadata: { labels: { app: order-api } }
    spec:
      containers:
        - name: order-api
          image: registry.internal/order-api:1.4.2
```

背後發生的 reconcile 接力:

1. **Deployment 控制器**看到要 3 個 → 建一個 ReplicaSet(期望 3)。
2. **ReplicaSet 控制器**看到 0/3 → 建 3 個 Pod 對象(還沒綁節點)。
3. **scheduler** 看到 3 個沒綁節點的 Pod → 各挑一個節點寫回 `nodeName`。
4. **kubelet**(那幾台)看到「綁到我的 Pod」→ 調 CRI 真的把容器跑起來(第 02 章),再把 `status` 寫回。

現在**殺掉一個 Pod**:ReplicaSet 控制器下次 reconcile 看到 2/3(level-triggered!),立刻補一個——你什麼都不用做。**改 `replicas: 5`**:同樣一條收斂路徑,多建 2 個。**滾動更新**(改 image):Deployment 控制器建新 ReplicaSet、按策略逐步把舊的縮到 0、新的擴到 3——這也是一次次 reconcile,不是一個「部署腳本」。

> 這就是「狀態收斂機」的威力:你**只描述終態,從不寫步驟**。

---

## 🔬 深挖出口

| 想深挖 | 去哪 |
|---|---|
| informer/watch、etcd 瓶頸、leader election、kube-proxy 包路徑(機制細部) | `cloud-native/03b-control-and-data-plane-internals` |
| 控制面/數據面、核心對象、聲明式 + reconcile(對象維度) | `cloud-native/03-k8s-architecture-and-objects` |
| 共識(Raft)/CAP——etcd 為什麼這樣設計 | `system-design/00-理論基礎-CAP與共識` |
| etcd 本身 | `etcd/` |

---

## 一句收口 + 地圖更新

> **k8s 的內核只有一句話:聲明期望狀態,一群 level-triggered 的控制器不斷把世界收斂過去;一切過 API Server,etcd 是唯一真相源。** 你之後學的每一個「現代」東西——Operator、GitOps、服務網格控制面、DRA——都是這個內核的再應用。

**🗺 地圖更新**:圓心(k8s)從「會用」升級成「**知道它為什麼這樣設計、怎麼崩、極限在哪**」。
**下一站**:`02 運行時環` —— 往外一環,看 spec 落到節點後,kubelet 到底**怎麼把容器真的跑起來**:dockershim 為什麼被移除、containerd/CRI/OCI 這條鏈現在長什麼樣。
