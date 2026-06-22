# 09 · AI 基建環 I:訓練/批處理(GPU 調度 · gang scheduling · 批編排)

> **一句話定位**:k8s 從「跑微服務」變成「**一切 workload 的底座**」,最大的新住戶就是 AI。但 AI workload 和微服務**根本不同**:要 GPU、是批處理而非常駐、多機要「全有或全無」地一起調度。這一環講**訓練/批處理側**的基建。

> **本章深度層**:外環,**寫滿深度**(AI 工程師/架構師向)。

---

## 🕰 變遷盒

| | 舊世界(2019-2020) | 新世界(2026) |
|---|---|---|
| AI 跑哪 | VM / 裸機,**手工 SSH 排 GPU** | **k8s 成 AI 底座**,聲明式調度 GPU |
| GPU 分配 | 一人一卡、靜態綁定 | **device plugin / MIG / 分時 / DRA** 靈活共享 |
| 多機訓練調度 | 手工協調幾台機器一起跑 | **gang scheduling**(全有或全無)+ 批隊列 |
| 資源治理 | 誰先登錄誰用,搶不到乾等 | **Kueue 配額 + 公平共享**,多團隊排隊 |
| GPU 利用率 | 沒人量,經常 20% 空燒 | **利用率 = 頭號成本指標**,被嚴格盯 |

**一句話**:把 AI 訓練搬上 k8s,不是「再起幾個 Pod」那麼簡單——GPU 昂貴稀缺、訓練是長批處理、多機要協同,這逼出了一整套**GPU 調度 + gang scheduling + 批隊列**的新基建。

---

## 1. 核心敘事

### 1.1 為什麼 AI workload 和微服務根本不同

| 維度 | 微服務(前 8 環) | AI 訓練 workload |
|---|---|---|
| 形態 | 常駐服務,always-on | **批處理任務**,跑完就退 |
| 資源 | CPU/內存,便宜可超賣 | **GPU,昂貴、稀缺、不可超賣** |
| 調度 | 一個個 Pod 獨立調度 | **多 Pod 必須一起調度**(gang) |
| 狀態 | 多為無狀態 | **有狀態**:checkpoint、數據集、模型 |
| 失敗 | 重啟一個 Pod | 一個 worker 掛可能**整個訓練作廢** |

這些差異意味著:默認的 k8s 調度器和「一 Pod 一資源」模型**不夠用**。

### 1.2 GPU 怎麼上 k8s:從整卡到細分

k8s 默認不認識 GPU。靠 **device plugin** 把 GPU 暴露成「擴展資源」:

```yaml
resources:
  limits:
    nvidia.com/gpu: 1     # 申請 1 張整卡
```

但「一 Pod 獨佔整卡」太粗——小實驗/推理用不滿一張 H100。於是有了 **GPU 共享/細分**:

| 方式 | 機制 | 隔離 | 適用 |
|---|---|---|---|
| **time-slicing(分時)** | 多 Pod 輪流用一張卡 | **無**(互相影響) | 開發/小實驗,容忍干擾 |
| **MPS** | 多進程共享 GPU 上下文 | 弱 | 已知協作的多任務 |
| **MIG(Multi-Instance GPU)** | A100/H100 **硬件切**成多個隔離實例 | **強(硬件級)** | 多租戶、要隔離 |
| **DRA(Dynamic Resource Allocation)** | 聲明式靈活申請設備(beta,2026 的方向) | 取決於後端 | **未來主流**,取代僵硬的 device plugin 模型 |

**DRA 是關鍵演進**:device plugin 模型只能「要 N 張卡」,表達不了「要 2 張用 NVLink 互連的卡」「要一個 MIG 切片」「多 Pod 共享這張卡」這類豐富約束。DRA 用 `ResourceClaim`/`ResourceSlice` 把設備申請變成**結構化、可組合**的聲明——這是 k8s 設備調度的戰略方向(回扣 01 章「in-tree → out-of-tree 設備插件化」的延伸)。

**NVIDIA GPU Operator** 則負責在節點上自動裝驅動、device plugin、監控——別手裝。

### 1.3 gang scheduling:為什麼「全有或全無」是命根

分布式訓練(數據並行/模型並行)需要 **N 個 worker 同時在線**用 NCCL 互相通信。如果調度器**先給了 6 個 GPU、剩 2 個排隊**——這 6 張卡會**乾等另外 2 個,誰都跑不了,還佔著卡**。整個集群陷入「人人持有一半、人人等另一半」的死鎖,GPU 全空燒。

**gang scheduling(成組調度)**:把一個作業的所有 Pod 當一個整體——**要麼全部能調度上、要麼一個都不上**,避免部分分配的死鎖。默認 kube-scheduler **不會** gang,要靠:

- **Volcano**:CNCF 批調度器,內建 gang(`PodGroup`)、隊列、優先級,HPC/AI 經典選擇。
- **Kueue**:k8s SIG 的**作業隊列 + 配額**層,管「哪個作業何時能進場」「各團隊配額與公平共享」,常和 gang 調度配合。
- coscheduling 插件:輕量 gang。

### 1.4 批編排框架

- **Kubeflow Training Operator**:`PyTorchJob`/`TFJob` 等 CRD,描述「N 個 worker 的分布式訓練」。
- **KubeRay**:把 **Ray** 跑上 k8s,做分布式訓練/調參/數據處理(也能服務,接 ch10)。
- 都是「CRD + 控制器」(回扣 01)——平台把高層「訓練作業」reconcile 成一組協同的 Pod。

### 1.5 數據與 checkpoint

訓練要喂大數據集、定期存 checkpoint(便於搶占後恢復)、產出模型工件。需要**快速共享存儲**(高吞吐),checkpoint 頻率是「容錯 vs 開銷」的權衡。

---

## 🏛 架構師視角

### 🔬 黑盒內幕

- **device plugin**:DaemonSet 在每節點向 kubelet 註冊 `nvidia.com/gpu` 資源與健康;調度器據此把 Pod 放到有空卡的節點。
- **MIG**:在 A100/H100 上把一張卡硬件切成如 7 個實例,每個有獨立顯存與算力分區——**真隔離**,不是分時。
- **DRA**:`ResourceClaim`(我要什麼設備)+ `ResourceSlice`(節點有什麼設備)+ 結構化參數,調度器據此匹配;比 `limits: gpu: N` 表達力強得多。
- **gang**:Volcano 的 `PodGroup` 標記「這組 Pod 是一個 gang」,調度器計算「能否一次性放下全組」,否則整組不調度。
- **多機通信**:GPU 間用 **NCCL**,跨節點走 **RDMA(InfiniBand/RoCE)**——普通 TCP 網絡會成為分布式訓練的瓶頸。

### 💥 失敗模式 / 故障域

| 故障 | 現象 | 根因 / 架構含義 |
|---|---|---|
| **gang 死鎖** | 多個作業各佔一半 GPU,全卡住、全空燒 | 沒用 gang scheduling;部分分配的經典災難 |
| **GPU 碎片** | 集群有 8 張空卡但分散在不同節點,需 8 卡同機的作業調不上 | 拓撲碎片;要 bin-packing / 拓撲感知調度 |
| **搶占丟 checkpoint** | spot 實例被回收,3 天訓練從頭來 | 沒勤存 checkpoint;長訓練 + spot 的致命組合 |
| **GPU 顯存 OOM** | 訓練進程崩 | batch size / 模型太大;OOM 不像 CPU 可超賣 |
| **低利用率空燒** | H100 利用率 20%,賬單爆炸 | 沒量利用率、配額不公、數據喂不滿 GPU |

### 📈 規模化極限

- **GPU 利用率 = 頭號成本指標**:一張閒置 H100 每小時都在燒錢。架構目標是**把利用率拉滿**(MIG 細分小任務、Kueue 排隊填空、數據管道別讓 GPU 餓著)。
- **多機訓練的網絡牆**:分布式訓練的擴展性受**節點間帶寬**限制;沒有 RDMA/InfiniBand,加機器邊際收益迅速遞減(通信開銷吃掉算力)。
- **配額與公平**:多團隊共享一個 GPU 池,要用 Kueue 做配額 + 公平共享 + 借用,否則一個團隊能餓死所有人。
- **千卡級調度**:大規模訓練要拓撲感知(同機/同機架/NVLink 域),調度器要理解硬件拓撲。

### ⚖️ 選型論證

| 維度 | 選項 | 怎麼選 |
|---|---|---|
| GPU 分配 | **DRA(新)** vs device plugin + MIG/分時 | 新集群往 DRA 走;現有用 device plugin + MIG(要隔離)/分時(開發) |
| 批調度 | **Volcano**(gang)+ **Kueue**(配額隊列) | 多機訓練必須 gang(Volcano);多團隊配額用 Kueue;常一起用 |
| 訓練框架 | Kubeflow Training Operator / **KubeRay** | 用 Ray 生態選 KubeRay;PyTorch 原生選 Training Operator |
| 自管 vs 託管 | k8s 自管 vs SageMaker/Vertex | 要可控/混合雲/逃生用 k8s;要省心用託管(但被鎖定) |
| 節點網絡 | RDMA(InfiniBand/RoCE) | 多機訓練**必須**,否則擴展不動 |

> **架構師判斷**:AI 訓練上 k8s 的核心不是「能不能跑」,而是「**GPU 這種昂貴稀缺資源,怎麼調度得既不死鎖、又高利用率、又對多團隊公平**」。gang scheduling 防死鎖、MIG/DRA 提利用率、Kueue 管公平——三件事缺一不可。

### 🧭 演進路徑

1. **裸機手工 → device plugin**:GPU 上 k8s,聲明式申請整卡。
2. **整卡 → 細分(MIG/分時/DRA)**:提利用率;小任務別獨佔整卡。
3. **默認調度 → gang(Volcano)**:多機訓練防死鎖。
4. **加配額層(Kueue)**:多團隊公平共享 GPU 池。
5. **加 RDMA + 拓撲感知**:讓多機訓練真的擴展得動。

### 🏭 生產事故 / 教訓

- **gang 死鎖燒掉整個 GPU 集群一下午**:兩個訓練作業各搶到一半卡,互等。教訓:**多 Pod 作業必須 gang scheduling**。
- **spot 搶占 + 無 checkpoint = 3 天白跑**:省了 spot 的錢,賠了整輪訓練。教訓:**長訓練要勤 checkpoint + 容忍搶占的恢復機制**。
- **H100 利用率長期 20%**:數據管道喂不滿、無人盯利用率。教訓:**把 GPU 利用率當第一成本 SLO**。

---

## 2. 現在主流怎麼選

| 決策 | 2026 主流答案 |
|---|---|
| GPU 分配 | DRA(方向)/ device plugin + MIG(隔離)+ 分時(開發);GPU Operator 管驅動 |
| 批調度 | Volcano(gang)+ Kueue(配額/隊列) |
| 訓練框架 | KubeRay / Kubeflow Training Operator |
| 多機網絡 | RDMA(InfiniBand / RoCE)+ NCCL |
| 核心 SLO | **GPU 利用率** + 隊列公平 |
| 容錯 | 勤 checkpoint，容忍搶占 |

---

## 🧵 示例服務在這一環

`order-api` 要一個**風控/推薦模型**,先得訓練它:

- 提交一個 **PyTorchJob**:8 個 worker,各 1 張 GPU,跨 2 節點。
- **Kueue** 按團隊配額決定它何時進場(別讓它餓死別人);**Volcano** gang 調度——8 個 worker **一次性全調度上**,絕不部分分配。
- 節點間走 **RDMA**,NCCL 做梯度同步;每 N 步存 checkpoint 到共享存儲(spot 被回收也能恢復)。
- 小規模超參實驗則用 **MIG** 把一張 H100 切成多片並行跑,把利用率榨滿。
- 訓練產出的模型工件進模型倉庫 → 交給 **ch10** 做推理服務。

對比 2019:當年是 SSH 上某台 GPU 機、`CUDA_VISIBLE_DEVICES` 手排、幾台機器手工協調、掛了重來——沒有調度、沒有配額、沒有 gang。

---

## 🔬 深挖出口

| 想深挖 | 去哪 |
|---|---|
| 調度器 / DRA 作為設備調度擴展(機制根) | 本線 `01-kernel`、`cloud-native/04-scheduling-and-resources` |
| 模型訓練本身(算法/動手) | `ai/ml-labs/`(你的 ML 動手 labs) |
| 推理/服務側 | 本線 `10-ai-infra-serving` |
| 平台怎麼把訓練作業自助化 | 本線 `08-platform-engineering` |

---

## 一句收口 + 地圖更新

> **AI 訓練上 k8s 的本質,是「昂貴稀缺的 GPU 怎麼調度得不死鎖、高利用率、多團隊公平」**:device plugin/MIG/DRA 解決「怎麼分卡」、gang scheduling(Volcano)解決「多機全有或全無」、Kueue 解決「配額與排隊」、RDMA 解決「多機擴展得動」。GPU 利用率是頭號成本指標。

**🗺 地圖更新**:你補上 AI 底座的「訓練側」,知道它為何不同於微服務、GPU 調度的幾種細分、gang 的命根地位。
**下一站**:`10 AI 基建環 II` —— 模型訓好了,**怎麼把它服務化**?推理和訓練又很不同:它是在線、突發、要 scale-to-zero、還有 LLM 特有的麻煩。
