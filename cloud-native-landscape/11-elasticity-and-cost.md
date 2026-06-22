# 11 · 彈性與成本環:autoscaling 全景 · Karpenter · FinOps

> **一句話定位**:前面把所有 workload(微服務 + AI)都講完了——**現在怎麼讓它們自動隨負載伸縮、又不把錢燒光**?這一環是橫切的「彈性 + 成本」收束:Pod 級與節點級的多維 autoscaling、Karpenter 即時供節點、以及 FinOps 成本治理。

> **本章深度層**:外環,**寫滿深度**。橫切性質,放在 workload 章之後做收束(管好前面一切的伸縮與花費);requests/limits/QoS 機制細部指進 `cloud-native/04`。

---

## 🕰 變遷盒

| | 舊世界(2019-2020) | 新世界(2026) |
|---|---|---|
| 擴縮 | 固定副本 / 手工改 replicas | **多維 autoscaling**:HPA + VPA + KEDA + scale-to-zero |
| 加節點 | 預留一堆機器「保險」/ 手工擴 | **Karpenter 即時按需供節點**,選最划算機型 |
| 成本 | 沒人算,超配當保險 | **FinOps**:Kubecost/OpenCost 可視 + right-sizing + spot |
| requests 設定 | 拍腦袋設大保平安 | **requests = 成本旋鈕**,按實際用量精調 |
| 縮容 | 幾乎不縮 | **consolidation 自動合併**、閒時縮容、spot |

**一句話**:雲原生的彈性有兩個軸——**Pod 級**(改副本/規格)和**節點級**(增減機器);而 2020 後最大變化是 **Karpenter** 把「加節點」從「擴節點組」變成「即時挑最優機型直接開」,加上 **FinOps** 把「成本」從沒人管變成一級 SLO。

---

## 1. 核心敘事

### 1.1 彈性的兩個軸

```
Pod 級彈性(改 workload 本身)        節點級彈性(改集群有多少機器)
┌─────────────────────────┐         ┌──────────────────────────┐
│ HPA  橫向:加減副本        │         │ Cluster Autoscaler        │
│ VPA  縱向:調 requests     │  觸發   │   按節點組擴(較慢)        │
│ KEDA 事件驅動 + scale-to-0│ ──────▶ │ Karpenter                 │
│ (隊列/Kafka lag/自定義)   │ Pod 調  │   即時挑最優機型直接開(快) │
└─────────────────────────┘ 不上→開機 └──────────────────────────┘
```

**先有 Pod 級擴縮產生「調度不上的 Pod」,才觸發節點級擴容**——兩軸協同。

### 1.2 Pod 級:HPA / VPA / KEDA

- **HPA(橫向)**:按 CPU / 自定義 / 外部指標自動增減**副本數**。最常用。
- **VPA(縱向)**:自動調**單 Pod 的 requests/limits**(right-sizing)。**注意**:VPA 和 HPA **不能在同一指標上同時作用**(會打架);VPA 常用 recommend 模式幫你校準 requests。
- **KEDA**:**事件驅動**擴縮——按隊列深度、Kafka lag、Prometheus 指標等擴縮,並支持 **scale-to-zero**(回扣 10/12)。微服務裡「按 MQ 積壓擴消費者」就靠它。

### 1.3 節點級:Cluster Autoscaler vs Karpenter

當 Pod 因為「沒節點放」而 Pending,要自動加機器:

- **Cluster Autoscaler(CA)**:基於**節點組(node group / ASG)**——你預定義幾種節點組,它在組內加減。受限於預設機型,擴容較慢、bin-packing 不夠優。
- **Karpenter**:**groupless**,直接看「Pending 的 Pod 需要什麼」→ **即時挑最合適的機型/大小開一台**(可混 spot、可選便宜實例),並做 **consolidation**(把零散負載合併到更少/更小節點、回收浪費)。AWS 出身、已捐 CNCF、走向多雲——**現代默認**,尤其 EKS。

> Karpenter 的精髓:**「按真實需求即時供給最划算的節點,並持續合併壓縮」**——這直接把「預留保險機器」的浪費幹掉。

### 1.4 成本 / FinOps:把花費變成一級 SLO

雲原生很容易燒錢:超配 requests、閒置節點、無上限擴容、GPU 空轉(回扣 09)。FinOps 把成本管起來:

- **可視**:**Kubecost / OpenCost** 按 namespace / 團隊 / workload 分攤成本,讓「誰花了多少」透明。
- **槓桿**:**right-sizing**(requests 貼近實際用量)、**spot/競價實例**(便宜但會被回收)、**consolidation/bin-packing**(裝得更密)、**scale-to-zero**(閒時縮沒)、**autoscaling**(不再為峰值常駐)。
- **核心旋鈕是 requests**:它同時決定**調度**(放得下放不下)和**成本**(預留多少)。requests 設太大 = 裝不密 = 燒錢;設太小 = 被驅逐/搶佔。

---

## 🏛 架構師視角

### 🔬 黑盒內幕

- **HPA 控制環**:metrics-server / 自定義指標 API 提供當前指標 → HPA 算「期望副本 = 當前副本 × 當前指標 / 目標指標」→ 改 Deployment.spec.replicas(又是 reconcile,回扣 01)。
- **Karpenter**:watch **unschedulable** Pod → 直接調雲 API 開一台「剛好裝得下」的節點(而非從預設組挑)→ 之後持續評估 consolidation,把 Pod 重新打包到更省的節點、回收空節點。
- **spot 中斷**:雲在回收前發中斷通知,Karpenter/處理器據此優雅驅逐 + 重調度。

### 💥 失敗模式 / 故障域

| 故障 | 現象 | 根因 / 架構含義 |
|---|---|---|
| **HPA / VPA 打架** | 副本和規格互相觸發、抖動 | 同指標上 HPA+VPA 同時作用;要分離指標或 VPA 只 recommend |
| **擴容滯後** | 流量突增時 Pod Pending 幾十秒(等開機) | 節點供給是分鐘級;用 **預留 headroom**(低優先級占位 Pod)或預擴 |
| **抖動 / flapping** | 反覆擴了又縮 | 閾值太敏感 / 無穩定窗口;設 stabilization window + 合理冷卻 |
| **spot 大規模回收** | 一批節點同時被收,服務抖動 | 沒配 **PodDisruptionBudget** / spot 比例過高;要分散 + PDB + 留 on-demand 底座 |
| **縮不下去** | 集群縮容卡住、長期超配 | Pod 無 PDB / 用了本地存儲 / 無 requests;CA 不敢縮 |
| **成本盲區** | 賬單爆炸沒人知道哪來的 | 沒 requests(無上限)或超配;沒 Kubecost 分攤 |

### 📈 規模化極限 / 成本

- **requests 準確度 = 集群效率**:requests 普遍超配 → bin-packing 密度低 → 節點數虛高 → 直接燒錢。**把 requests 校準到貼近真實用量,是最大的省錢槓桿**(用 VPA recommend / Kubecost 反推)。
- **spot 比例 vs 可靠性**:spot 省 60-90% 但會被回收;無狀態 + PDB + 多樣機型可大比例上 spot,有狀態/關鍵路徑留 on-demand 底座。
- **擴容延遲預算**:節點開機分鐘級,突發場景要 headroom 占位或預測式擴容,別讓彈性變成「峰值時才慢慢開機」。

### ⚖️ 選型論證

| 維度 | 選項 | 怎麼選 |
|---|---|---|
| 橫向擴縮 | **HPA**(指標)/ **KEDA**(事件 + scale-to-zero) | 按資源指標用 HPA;按隊列/事件/要縮到 0 用 KEDA |
| 縱向 right-size | **VPA**(多為 recommend 模式) | 校準 requests;別和 HPA 搶同指標 |
| 節點彈性 | **Karpenter**(現代、靈活、省)/ Cluster Autoscaler(節點組) | 新集群 / EKS 首選 Karpenter;CA 適合固定機型/簡單場景 |
| 成本可視 | **Kubecost / OpenCost** | 標配,按團隊分攤 |
| 省錢手段 | right-sizing + spot + consolidation | 組合拳,先校準 requests(收益最大) |

> **架構師判斷**:成本不是事後對賬,是**架構決策**。最大的浪費通常不是「沒用 spot」,而是 **requests 普遍超配導致節點裝不密**。先把 requests 校準(VPA/Kubecost)、再上 Karpenter consolidation、最後 spot——順序別反。且彈性要配 **PDB** 才安全,否則 spot 回收/縮容會誤傷。

### 🧭 演進路徑

1. **固定副本 → HPA / KEDA**:按負載自動橫向擴縮。
2. **拍腦袋 requests → VPA recommend + Kubecost 校準**:right-size,提 bin-packing 密度。
3. **節點組 → Karpenter**:即時供最優節點 + consolidation。
4. **on-demand → 混 spot + PDB**:無狀態大比例上 spot,關鍵留底座。
5. **成本入 SLO**:Kubecost 按團隊分攤,成本進評審與告警。

### 🏭 生產事故 / 教訓

- **失控 HPA + 無節點上限 → 成本爆炸**:一個指標 bug 讓 HPA 瘋狂擴、Karpenter 一直開機。教訓:**設副本/節點上限 + 成本告警**。
- **spot 大規模回收打掛服務**:spot 比例 100% 又沒 PDB。教訓:**留 on-demand 底座 + PDB + 機型分散**。
- **requests 全員超配 3 倍**:集群節點數虛高一倍,賬單翻倍卻沒人察覺。教訓:**requests 是成本旋鈕,要持續校準**。

---

## 2. 現在主流怎麼選

| 決策 | 2026 主流答案 |
|---|---|
| 橫向擴縮 | HPA(指標)+ KEDA(事件 / scale-to-zero) |
| right-sizing | VPA recommend + Kubecost 反推 |
| 節點彈性 | **Karpenter**(consolidation + 混 spot);CA 為簡單場景 |
| 成本可視 | Kubecost / OpenCost,按團隊分攤 |
| 省錢順序 | **先校準 requests** → consolidation → spot |
| 安全網 | PodDisruptionBudget + 副本/節點上限 + 成本告警 |

---

## 🧵 示例服務在這一環

order 系統的彈性與成本:

- **order-api**:HPA 按 RPS 擴副本;requests 用 VPA recommend 校準到貼近實際(不再超配 3 倍)。
- **inventory 的異步消費者**:KEDA 按 MQ 積壓擴縮,夜間無消息時 scale-to-zero。
- **節點**:Karpenter 看到 Pending Pod 即時開最划算機型,無狀態服務跑 spot、配 PDB,凌晨低峰自動 consolidation 把負載擠到更少節點、回收空機。
- **AI 成本(回扣 09-10)**:GPU 節點也由 Karpenter 供給,推理用 scale-to-zero 省閒置 GPU,Kubecost 把「風控模型這個月花了多少 GPU 錢」攤給算法團隊。
- **可視**:Kubecost 面板顯示 order 團隊本月花費與浪費(超配 requests)排行,進月度評審。

對比 2019:固定副本 + 預留一堆「保險」機器常駐空轉,成本沒人算,峰值還是手忙腳亂手工擴。

---

## 🔬 深挖出口

| 想深挖 | 去哪 |
|---|---|
| requests/limits、QoS、OOMKilled、HPA、親和/污點(機制) | `cloud-native/04-scheduling-and-resources` |
| GPU 成本 / 利用率 | 本線 `09-ai-infra-training`、`10-ai-infra-serving` |
| 容器/k8s 性能調優 | `performance-tuning-roadmap/12-container` |
| 容量規劃 / RPO-RTO(理論) | `system-design/08-可用性與容災-RPO-RTO` |

---

## 一句收口 + 地圖更新

> **彈性有兩軸**:Pod 級(HPA/VPA/KEDA)+ 節點級(Karpenter 即時供最優節點 + consolidation);**成本的核心旋鈕是 requests**——校準它的收益大於一切花招,再疊 consolidation 與 spot,並用 Kubecost 把花費變成一級 SLO。彈性要配 PDB 才安全。

**🗺 地圖更新**:你補上橫切的「伸縮與花費」環——知道兩軸 autoscaling、Karpenter 的精髓、以及「requests 是成本旋鈕」這個最值錢的省錢判斷。
**下一站**:`12 前沿環` —— 一章快速掃完 k8s 還在往哪長:serverless、WASM、多集群、邊緣。
