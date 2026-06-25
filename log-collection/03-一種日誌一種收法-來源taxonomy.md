# 03 · 一種日誌一種收法:來源 taxonomy

> 這是整個 track 的核心章,正面回答你那句:**「是不是不同的日誌需要不同的收集方式?」**
> `02` 的三種架構,預設解的只是**應用容器 stdout** 這一類。但一個 k8s 集群裡的日誌**不只這一種** —— 它們分布在不同的層,**產生方式、存放位置、生命週期、敏感度全都不同**,所以沒有單一收法。這章把 6 類源攤開,每類給「**機制 + 為什麼 + 反模式**」。

---

## 一、一張圖:一個集群裡的日誌源,是分層的

```
┌─ 控制平面層(master)─────────────────────────────┐
│  apiserver / scheduler / controller-manager / etcd │  ← 託管集群:你 ssh 不進去
│  + 審計日誌(audit:誰對什麼資源做了什麼)           │     靠雲廠開關導出(⑥⑦)
└────────────────────────────────────────────────────┘
┌─ K8s API 物件層 ───────────────────────────────────┐
│  Events(Scheduled / Pulled / FailedScheduling …)   │  ← 不是日誌檔,是 etcd 裡有 TTL 的物件(⑧)
└────────────────────────────────────────────────────┘
┌─ 每台 node ────────────────────────────────────────┐
│  系統層:kubelet / containerd / kernel / journald   │  ← 在 journald,不在 /var/log/containers(⑤)
│  ┌─ 應用容器層 ─────────────────────────────────┐  │
│  │  stdout/stderr ──► /var/log/containers(②主力) │  │
│  │  寫檔案的 app   ──► 容器內檔(要特別處理)(③④)│  │
│  └──────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────┘
```

**一句話**:`01/02` 講的「node agent 讀 `/var/log/containers`」只覆蓋了最內那層(應用 stdout)。往外每一層,收法都不一樣。

---

## 二、應用 stdout / stderr —— node agent(主力)

`01`+`02` 已講透:app 寫 stdout → containerd 落 node 檔 → **DaemonSet agent** tail `/var/log/containers` → 後端。**這是預設、是大頭、是「最佳實踐」那句話覆蓋的部分。** 後面五類,都是這條覆蓋不到的。

---

## 三、應用寫**檔案**(不寫 stdout)

**場景**:legacy app、framework 硬寫檔(Tomcat 的 `catalina.out`、某些 Java 服務寫 `app.log`)、或一個容器產出**多個**日誌檔(`access.log` + `error.log` + `app.log`)。

**三種收法,按優先級**:

1. **改成寫 stdout(最佳,治本)** —— 回到 `02` ① 的主力路徑,零額外成本。多個檔 → 改成多條結構化記錄、用欄位區分(見第四節)。
2. **改不動 → Streaming sidecar 轉回 stdout**(`02` 的 (a) 型):sidecar `tail` 檔案 re-emit 到自己 stdout,讓 node agent 收。
3. **共享 `emptyDir` + node agent 也讀那路徑**,或 **sidecar-with-agent** 直接讀檔推後端。

**反模式**:app 把日誌寫進**容器可寫層**(沒掛 volume 的容器內路徑)。後果:① pod 一刪日誌全沒(回扣 `01` 的「pod 沒了就沒了」);② 撐大容器可寫層、可能觸發 node 磁碟壓力。**容器裡要寫檔,至少寫到 `emptyDir`,且最好乾脆改 stdout。**

---

## 四、多流分離(一個容器多種日誌)

一個容器常有**性質不同**的多條日誌混在一起:nginx 的 `access` + `error`、應用的 `business log` + `audit log`、API 的 `request log` + `app log`。

**怎麼分**:
- 結構化日誌加一個 **`log_type`**(或 `stream`)欄位,管線按欄位**路由到不同後端 / 索引**;
- 或不同檔 → 不同 tag → 不同 pipeline。

**為什麼非分不可**(這條直接連到成本與合規):**不同流的處理策略天差地別** ——

| 流 | 量 | 抽樣 | 保留 | 索引 |
|---|---|---|---|---|
| access / request | 高頻 | 可抽樣 | 短(7~30 天) | 輕 |
| business / app | 中 | 否 | 中 | 中 |
| audit / 安全 | 低 | **絕不抽樣** | **長(數月~數年)** | 嚴格、不可變 |

混在一起,你就**沒法分別對待** —— 要嘛把 access 也長期保留(燒錢),要嘛把 audit 也抽樣丟掉(合規出事)。**分流是省錢 + 合規的前提。**(`05` 的 EKS 成本、`06` 的審計都會回到這。)

---

## 五、Node / 系統日誌(kubelet · containerd · kernel · journald)🔬

node 本身的日誌:**kubelet**、**containerd**、**kernel(dmesg / OOM)**、**systemd journald**、sshd。

**關鍵**:這些**不在** `/var/log/containers`,在 **journald** 或 `/var/log/messages`。所以 `02` ① 那套 tail `*.log` **收不到它們**。

**收法**:**同一個 DaemonSet agent 多配一個 input** —— 一個讀 `/var/log/containers`(容器日誌),另一個讀 **systemd / journald**(系統日誌)。兩個 input、兩種 parser,匯到同一個 agent 出口。

> 🔬 **journald 是二進制的**,不能像文字檔那樣 `tail`,要用收集器的 **systemd input**(Fluent Bit `systemd` plugin / Vector `journald` source)去讀。這是「不同源不同收法」最具體的一個例子:連讀取機制都不同。

**為什麼非收不可**:**node NotReady、磁碟滿、kernel OOMKill、網路異常**的根因,常常**只在系統日誌裡**,應用日誌完全看不到(回扣 `cloud-native/09` debug node)。你只收應用日誌,等於 node 出事時瞎了。

---

## 六、K8s 控制平面日誌(apiserver / scheduler / controller-manager / etcd)

**自建集群**:這些是跑在 master 上的 static pod / 進程,日誌在 master node,你能自己收。

**託管集群(EKS / GKE / AKS)—— 這是重點**:master 由**雲廠託管,你 ssh 不進去、也沒有 DaemonSet 能跑在 master 上**。所以:

> **你不自己收控制平面日誌 —— 你用雲廠的開關把它導出。** EKS 叫 **control plane logging**,一開就送 CloudWatch(`05` 細講)。

**為什麼要它**:apiserver 的請求審計、**為什麼 pod 一直 Pending** 的調度器深層原因、controller 的 reconcile 失敗 —— 這些應用日誌和 `kubectl logs` 都看不到,只在控制平面日誌裡。

---

## 七、K8s 審計日誌(audit)

**是什麼**:apiserver 的 **audit log** —— **「誰、在什麼時候、對什麼資源、做了什麼操作」**(who did what to which resource when)。注意它**不是應用日誌、也不是普通容器日誌**,是 API 層的安全記錄。

**收法 / 處理(和普通日誌不同)**:
- 屬於控制平面日誌的一種(EKS 是 control plane logging 的 `audit` 類型);
- **安全 / 合規關鍵** → **獨立管道、更長保留、限制訪問、不可變存儲**(如 S3 + Object Lock,寫入後不可改不可刪)。

**為什麼單列**:它的**敏感度和保留要求**和應用日誌完全不同(回扣第四節的分流表)。把 audit 和 access 丟同一個索引、同樣 7 天保留,就是合規事故。

---

## 八、K8s Events(物件事件)🔬

`kubectl get events` 看到的那些:`Scheduled`、`Pulled`、`FailedScheduling`、`OOMKilling`、`BackOff`、`Unhealthy`。

> 🔬 **它們不是日誌、不在 `/var/log`** —— 是 **etcd 裡的 API 物件**,而且**有 TTL,預設約 1 小時後就被 GC 掉**。所以 node agent tail 檔案那套**根本碰不到它們**,而且你晚一小時去看就消失了。

**收法**:用 **event-exporter**(watch Events API,把事件轉成日誌推後端)/ **OTel 的 k8s events receiver** / 或 kube-state-metrics(轉成 metrics)。本質是「**watch API 物件**」,不是「讀檔」。

**為什麼要它**:很多「**pod 為什麼起不來**」的答案**只在 Events 裡**(`FailedScheduling: insufficient memory`、`Failed: ImagePullBackOff`),而且 **1 小時後消失**(回扣 `cloud-native/08` debug pod)。事後復盤時 Events 早沒了 —— 所以要持續導出留存。

---

## 九、總表:6 類源 × 怎麼收

| 日誌源 | 在哪 | 怎麼收 | 為什麼非收不可 | 反模式 |
|---|---|---|---|---|
| **應用 stdout/stderr** | `/var/log/containers` | DaemonSet agent tail(`02`①) | 主力業務日誌 | 全員 sidecar(`02`/`06`) |
| **應用寫檔** | 容器內檔 | 改 stdout > streaming sidecar > emptyDir | 否則收不到 | 寫容器可寫層,pod 刪即沒 |
| **多流(access/audit…)** | 同上 | 加 `log_type` 欄位分流路由 | 不同流保留 / 抽樣 / 合規不同 | 混一個索引,沒法分別對待 |
| **Node / 系統** | journald / messages | agent 另配 **journald input** | node 故障根因在這 | 只收應用日誌,node 出事瞎 |
| **控制平面** | master(託管不可達) | **雲廠開關導出**(EKS control plane logging) | pod Pending / 調度 / 審計 | 以為能自己收 |
| **審計(audit)** | 控制平面的一種 | 獨立管道 + 不可變 + 長保留 | 合規 / 安全 | 和應用日誌同索引同保留 |
| **Events** | etcd 物件(TTL ~1h) | **event-exporter**(watch API) | pod 起不來的真因、1h 後消失 | 當成能 tail 的日誌、不導出 |

---

## 十、收口:為什麼「一種日誌一種收法」

回到你的問題 —— **是的,而且這不是麻煩,是必然**:

> 日誌源分布在**不同的層**(應用進程 / node 系統 / 控制平面 / API 物件),它們的**產生方式**(寫 fd / 寫 journald / etcd 物件)、**存放位置**、**生命週期**(隨 pod / 隨 node / TTL 1h)、**敏感度**(業務 / 審計)全都不同 —— 所以**不可能有單一收法**。

**成熟方案 = 分層組合**,不是一招打天下:

```
DaemonSet agent(一個 pod,多個 input)
  ├─ input 1: tail /var/log/containers   ← 應用 stdout(主力)
  └─ input 2: systemd journald            ← node / 系統
+ 雲廠 control plane logging                ← 控制平面 + 審計(獨立保留)
+ event-exporter                            ← K8s Events
+ 少數 sidecar                              ← 寫檔 / 強隔離的特例(02)
```

面試裡能把這張分層圖畫出來、說清每層**為什麼不能用同一種收法**,就是資深和「只會背 stdout+Fluent Bit」的分水嶺。

---

## 交叉引用

- **應用 stdout 主力路徑、node agent 怎麼運作** → `02`
- **node 檔案 / pod 沒了就沒了 / TTL 的物理原因** → `01`
- **多 input、parser、分流路由怎麼配** → `04`
- **EKS 上控制平面 / 審計日誌具體怎麼開** → `05`
- **node 系統日誌排 node 故障、Events 排 pod 起不來** → `cloud-native/08`、`09`
- **審計 / 安全日誌的不漏 PII、不可變** → `logging/06`

---

## 本章小結

- 「不同日誌不同收法」**是的,而且必然** —— 源分布在不同層,產生方式 / 位置 / 生命週期 / 敏感度都不同。
- 6 類:**應用 stdout(主力 DaemonSet)/ 應用寫檔(改 stdout 或 sidecar)/ 多流(欄位分流)/ node 系統(journald input)/ 控制平面(雲廠導出)/ 審計(獨立不可變)/ Events(event-exporter watch)**。
- 🔬 三個「碰不到 `/var/log/containers`」的源:**journald(二進制,要 systemd input)、控制平面(託管不可達)、Events(etcd 物件 + TTL 1h)**。
- 成熟方案 = **一個 DaemonSet 多 input + 雲廠控制平面日誌 + event-exporter + 少數 sidecar** 的分層組合。

---

## 章末問答(複習自檢,答案要點都在前面正文)

1. 用「層」的概念畫出一個集群裡的日誌源分布,並說明 `02` 的 node agent 預設只覆蓋哪一層。
2. 應用寫檔(不寫 stdout)的三種收法,優先級怎麼排?為什麼「寫容器可寫層」是反模式?
3. 為什麼 access 和 audit 日誌**非分流不可**?混在一個索引、同樣保留期,會出什麼事(一個省錢角度、一個合規角度)?
4. node 的系統日誌為什麼 `tail /var/log/containers` 收不到?要怎麼收?journald 和文字檔在「讀取機制」上差在哪?
5. 託管集群(EKS)的控制平面日誌,你為什麼**不能自己用 DaemonSet 收**?那要怎麼拿到?
6. K8s Events 為什麼不能當普通日誌 `tail`?它有什麼致命的「時間性」問題?該用什麼收?
7. **綜合題**:面試官問「你們 k8s 日誌收集怎麼設計的」,請畫出一個**分層組合**方案,並對每一層說一句「為什麼這層不能用上一層的收法」。
