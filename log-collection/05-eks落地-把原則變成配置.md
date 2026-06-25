# 05 · EKS 落地:把原則變成配置

> 前四章是**雲中立原則**;這章把它落到 **EKS**(你的真實場景),最後映射 GKE / AKS,證明原則是通的、只是託管程度不同。
> 一個必須先記住的分叉:**EKS 上的 node 形態(EC2 vs Fargate)直接決定收法** —— 這是 `02`「直推 / sidecar 例外」在真實世界最大的觸發點。

---

## 一、EKS 的兩種 node 形態 → 兩種收法 🔬

```
EKS 集群
├─ EC2 node group   你有 node、能跑 DaemonSet  ──►  ① 標準 Fluent Bit DaemonSet
└─ Fargate          每 pod 一個微 VM,AWS 管底層  ──►  ② 跑不了 DaemonSet → 內建 log router
                    你 ssh 不進去、沒有 node 可掛
```

- **EC2 node group**:`02` ① 的標準世界 —— DaemonSet agent。
- **Fargate**:**沒有你掌控的 node**(AWS 給每個 pod 一個獨立微 VM,底層你碰不到)→ **DaemonSet 根本調度不上去** → 這正是 `02` 說的「**Serverless 沒 node 可掛 agent**」的真實案例。AWS 用內建 router 幫你補位(第三節)。

> 🔬 **這是 EKS 日誌最常踩的坑**:照搬 EC2 的 Fluent Bit DaemonSet YAML 到純 Fargate 集群,**它永遠 Pending**(沒有 node 能放 DaemonSet),於是「日誌收不到」卻查不出原因。記住:**Fargate 走 log router,不是 DaemonSet。**

---

## 二、EC2 node group:Fluent Bit DaemonSet

**收集器**:**`aws-for-fluent-bit`**(AWS 維護的 Fluent Bit 發行鏡像,內建了 CloudWatch / Kinesis / S3 / OpenSearch 的 output 插件)。以 DaemonSet 部署,tail `/var/log/containers`(完全是 `02` ① + `04` 的那套)。

**後端選項**(按需選,呼應 `04` 別綁死):

| 後端 | 適合 | 備註 |
|---|---|---|
| **CloudWatch Logs** | 默認、和 AWS 生態最順 | 按 ingest GB + 存儲計費,**高量很貴**(第六節) |
| **OpenSearch** | 要強搜尋 / Kibana 式分析 | 自己運維或用 AWS 託管 OpenSearch |
| **S3(經 Kinesis Firehose)** | 歸檔 / 低成本長保留 / 合規 | Firehose 做緩衝 + 批量落 S3,適合 audit |
| **第三方**(Datadog / Splunk / Grafana Cloud) | 已有 SaaS 棧 | Fluent Bit 直接有 output |

> 🔬 **Container Insights** 本質就是這套:AWS 預打包的 **CloudWatch agent(metrics)+ Fluent Bit(logs)** DaemonSet。你「開 Container Insights」= 自動部署了這個收集棧。不神秘,就是 `02`+`04`。

**權限:用 IRSA,別開大 node IAM** 🔬
Fluent Bit 要寫 CloudWatch / S3,需要 AWS 權限。**最佳實踐是 IRSA(IAM Roles for Service Accounts)**:給 Fluent Bit 的 **ServiceAccount 綁一個最小權限 IAM role**(只能 `logs:PutLogEvents` 等),而**不是**把權限加到 node 的 instance role(那會讓**這台 node 上所有 pod**都繼承,違反最小權限)。這是 EKS 安全的通用模式,日誌收集是它最典型的應用之一。

---

## 三、Fargate:內建 log router 🔬

Fargate 沒 DaemonSet,AWS 在**每個 Fargate pod 裡注入一個 Fluent Bit log router**(等於 AWS 幫你管的 sidecar —— `02` 的 sidecar 模式,只是你不用自己寫進 workload)。

**配置方式**(和 EC2 完全不同,要記):在 **`aws-observability`** namespace 建一個名叫 **`aws-logging`** 的 **ConfigMap**,在裡面寫 output(去 CloudWatch / Firehose / 第三方)。沒有這個 ConfigMap,Fargate 日誌就只進 `kubectl logs`(回扣 `01` 的「臨時窗口」),不落持久後端。

```
Fargate pod ──► (AWS 注入的 Fluent Bit router) ──► 讀 aws-observability/aws-logging ConfigMap ──► CloudWatch / Firehose
```

**一句話對應**:EC2 = 你部署 DaemonSet;Fargate = AWS 部署 router,你只給它一張 ConfigMap 配置。

---

## 四、控制平面日誌:`03` 的「託管不自己收」在 EKS 落地

`03` 第六 / 七節說過:託管集群的控制平面**你 ssh 不進去,靠雲廠開關導出**。EKS 的開關叫 **control plane logging**,**5 種 log type**,逐個可開,全部送 **CloudWatch Logs**:

| type | 是什麼 | 排查什麼 |
|---|---|---|
| `api` | apiserver 請求日誌 | API 請求、誰在打 apiserver |
| **`audit`** | **審計日誌(`03` 第七節)** | 誰對什麼資源做了什麼;**合規 / 安全,獨立長保留** |
| `authenticator` | **EKS 特有**:IAM → k8s 認證 | 「為什麼我連不上集群 / 權限不對」 |
| `controllerManager` | 各 controller 的 reconcile | controller 行為異常 |
| `scheduler` | 調度決策 | **pod 為什麼一直 Pending** |

> 🔬 `authenticator` 是 EKS 獨有的一層 —— EKS 用 IAM 身份映射到 k8s RBAC,這條鏈出問題(`aws-auth` 配錯、IAM role 沒映射)就在這個日誌裡。純 k8s 沒有這類。
>
> `audit` type 就是 `03` 講的審計日誌:開了之後,**對它做和應用日誌不同的處理** —— 更長保留、限制訪問、必要時從 CloudWatch 再導去 S3 + Object Lock 做不可變存檔。

---

## 五、一張 EKS 落地全圖

```
應用日誌
 ├─ EC2 pod    ─► Fluent Bit DaemonSet ─┐
 └─ Fargate pod ─► 內建 log router      ─┼─► CloudWatch / OpenSearch / S3(Firehose)/ 第三方
                                         │
Node/系統(EC2)─► 同 DaemonSet journald input ─┘     (Fargate 無 node 系統層可收)

控制平面 + 審計 ─► EKS control plane logging(5 type 開關)─► CloudWatch(audit 再導 S3 長存)

K8s Events     ─► event-exporter(自己部署,03 第八節)─► CloudWatch / 後端
```

把這張圖畫出來,就把 `01`~`04` 的原則在 EKS 上**全部兌現**了:不同源、不同收法、不同後端 / 保留。

---

## 六、成本與保留:架構師必算的一筆 🔬

**CloudWatch Logs 按 ingest GB 計費**(寫入量),高日誌量服務的帳單能很嚇人。對策全是前面章節的回收:

- **抽樣 / 限流**(`04`):高頻 access 日誌抽樣,別全量進 CloudWatch。
- **按 `log_type` 分流 + 差異保留**(`03`):access 進 CloudWatch 短保留(7~30 天);audit 進 S3 長保留(合規);冷數據用 Firehose 落 S3(比 CloudWatch 存儲便宜得多)。
- **別把高基數 / 大 payload 全塞進去**(`04`/`logging06`):ingest 量直接等於錢。

> 🔬 一句架構師話術:**「日誌成本 = ingest 量 × 保留期 × 後端單價」,三個乘數每一個都是 `03`/`04` 的決策**(分流降量、差異保留、抽樣、選對後端)。面試問「日誌太貴怎麼辦」,答案不是「換個便宜後端」,是**從源頭分流和保留策略下手**。

---

## 七、雲中立映射:原則一樣,託管程度不同

回應「中立原則優先」—— 三家雲**原理完全一樣**(node agent 收應用日誌 + 雲廠導出控制平面日誌),差別只在**託管程度**和**默認後端**:

| | EKS(AWS) | GKE(GCP) | AKS(Azure) |
|---|---|---|---|
| 應用日誌 agent | 自己部署 Fluent Bit DaemonSet(或開 Container Insights) | **默認內建** Logging agent(Fluent Bit based),開箱即收 | Container Insights / Azure Monitor agent |
| 默認後端 | CloudWatch Logs | **Cloud Logging**(默認就進) | Azure Monitor Logs(Log Analytics) |
| 控制平面日誌 | control plane logging 開關 | 默認進 Cloud Logging | diagnostic settings 開關 |
| Serverless node | **Fargate → log router** | Autopilot(GKE 託管 node) | virtual nodes |
| 風格 | **給你最多自己配的空間** | 最「開箱即用」 | 介於兩者 |

> 一句話:**GKE 把 agent 做成默認內建、最省心;EKS 給你最多控制權、也最多要自己配**。但你只要懂了 `01`~`04` 的原理,換哪家都是「node agent + 託管控制平面日誌 + 分層後端」這同一張圖,只是按鈕位置不同。

---

## 交叉引用

- **DaemonSet / sidecar / 直推三架構** → `02`(Fargate 是「直推 / 託管 sidecar」的真實案例)
- **控制平面 / 審計 / Events 為什麼分開收** → `03`
- **收集器選型、buffer、分流** → `04`
- **零停機遷移收集方案的灰度思路** → `distribution/zero-downtime-release/`(`06` 會用)
- **PII 脫敏、別把祕密寫進日誌(進了 CloudWatch 就外流)** → `logging/06`

---

## 本章小結

- **EC2 vs Fargate 決定收法**:EC2 → Fluent Bit DaemonSet;**Fargate 沒 node → 跑不了 DaemonSet → 內建 log router(aws-observability/aws-logging ConfigMap)**。照搬 DaemonSet 到 Fargate 會永遠 Pending。
- EC2:`aws-for-fluent-bit` DaemonSet → CloudWatch / OpenSearch / S3(Firehose)/ 第三方;**Container Insights = 這套的預打包**;權限用 **IRSA 最小化**,別開大 node IAM。
- 控制平面:**control plane logging 5 type**(`api`/`audit`/`authenticator`(EKS 特有)/`controllerManager`/`scheduler`)→ CloudWatch;`audit` 獨立長保留。
- 🔬 **成本 = ingest 量 × 保留 × 單價**,靠 `03`/`04` 的分流 / 差異保留 / 抽樣下手,不是換後端。
- 雲中立:三家原理一致(agent + 託管控制平面導出),**GKE 最開箱、EKS 最多自配**。

---

## 章末問答(複習自檢,答案要點都在前面正文)

1. 為什麼把 EC2 的 Fluent Bit DaemonSet YAML 直接套到純 Fargate 集群,日誌會收不到?Fargate 正確的收法是什麼、配在哪?
2. `aws-for-fluent-bit` DaemonSet 對應前面哪一章的哪種架構?Container Insights 和它什麼關係?
3. 為什麼 Fluent Bit 的權限要用 IRSA 而不是加到 node instance role?這體現什麼安全原則?
4. EKS control plane logging 的 5 種 type 分別排查什麼?哪一種是 EKS 特有、為什麼?哪一種要獨立長保留?
5. 「我們 CloudWatch 日誌帳單太貴」——你會從哪幾個地方下手降成本(至少三個,且都回扣前面章節)?
6. EKS / GKE / AKS 在日誌收集上「原理相同、差別在哪」?用一句話概括三家的風格差異。
7. **綜合題**:畫出一個**混合 EC2 + Fargate** 的 EKS 集群的完整日誌收集落地圖(應用 / 系統 / 控制平面 / 審計 / Events 各走哪條路、進哪個後端、什麼保留)。
