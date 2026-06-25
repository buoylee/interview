# 05 · Go / Python ↔ k8s 整合 —— 沒有全家桶,靠講契約

> 🔬 你的問題③:Go / Python 沒有 Spring Cloud 那種分佈式全家桶,它們**怎麼和 k8s 整合、怎麼做分佈式**?核心答案一句話:**整合不是「裝一個框架」,是「講好 k8s 的契約」。** 這章先講那份契約(探針 / 信號 / DNS / env),再看框架在哪裡補位,最後收口整個 track。

---

## Part A · 核心倒轉:從「app 主動註冊」到「平台主動探測」

Spring Cloud 和 k8s 對「服務怎麼被納入治理」的模型是**反的**:

```
Spring Cloud:  app 啟動 ──主動 register──► Eureka      （app push,胖客戶端)
k8s:           平台 ──主動 probe / watch──► app          （平台 pull,瘦客戶端)
```

- Spring Cloud 裡,**app 要做事**:引 SDK、啟動時註冊、定時心跳、調用前查列表。
- k8s 裡,**app 幾乎什麼都不做**,只是**被動暴露幾個契約點**,讓平台來探、來轉發。app 不知道有 registry,也不註冊。

所以 Go / Python「和 k8s 整合」= **把這份契約實現好**。契約只有五項,而且大半是「暴露一個 HTTP endpoint」「處理一個信號」這種小事:

| 治理事 | Spring Cloud(app 主動) | Go / Python(講契約,平台來做) |
|---|---|---|
| **服務發現** | 註冊到 Eureka + 查列表 | **啥都不做** → 直接 `http://svc-name/`,CoreDNS 解析。要實例級才用 client-go / py-client watch Endpoints |
| **配置** | Config Server SDK 拉 + 監聽 | 讀 **env**(ConfigMap/Secret 注入)/ 掛載文件 + `fsnotify` 熱讀 / Downward API |
| **健康** | actuator + 心跳 | 暴露 **liveness / readiness / startup 探針**(`/healthz` 或 gRPC Health),平台來探 |
| **生命週期** | (容器外管) | 收 **SIGTERM** → 停收新請求 → drain → 退;配 `preStop` |
| **選主 / 鎖** | (靠 ZK/Redis SDK) | **client-go leaderelection(Lease 對象)** / py kube-leader |

逐項拆:

**① 服務發現 —— 默認啥都不做。** Go / Python 服務調別的服務,就是 `GET http://order-service/...`。`order-service` 是個 k8s Service 名,CoreDNS 解析成 ClusterIP,kube-proxy 轉發。**沒有 SDK、沒有註冊、沒有心跳。** 只有當你需要「實例級信息」(比如自己做客戶端 LB、要每個 pod 的 IP),才用 **client-go**(Go)或 **kubernetes**(Python)去 watch `Endpoints` / `EndpointSlice`。

**② 配置 —— env 為主。** k8s 把 ConfigMap / Secret **注入成環境變量**,app 啟動讀 env(12-factor 第三條)。要動態熱更:掛載成文件 + `fsnotify`(Go)/ `watchdog`(Python)監聽文件變化;或讀 Downward API 拿自己的 pod 元數據。**注意 `02` 講過:ConfigMap 掛載更新是 kubelet 定期 pull、不是秒級 push** —— 要真·秒級動態配置,還是得 Nacos / 配置中心。

**③ 健康 —— 暴露探針讓平台探。** 這是 k8s 整合**最核心的一個接口**。app 開三個探針端點:
- **liveness**:活著嗎?失敗 → k8s 重啟 pod。
- **readiness**:能接流量嗎?失敗 → 從 Endpoints 摘除(**這就是 k8s 的「服務發現摘除」機制**,對應 `02` 講的 readiness)。
- **startup**:啟動完成了嗎?保護慢啟動 app 不被 liveness 誤殺。

HTTP 服務暴露 `/healthz`;gRPC 服務實現標準 **gRPC Health Checking Protocol**(`grpc_health_v1`,grpc-go 自帶)。**這個契約講好了,k8s 的探活 + 流量灌入就自動工作了** —— 這就是「整合」的實質。

**④ 生命週期 —— 處理 SIGTERM。** k8s 要停 pod 時發 **SIGTERM**。app 必須**捕獲它**:停止接受新請求 → 排空存量(`03`/`04` 的長連接在這收尾)→ 退出。Go `signal.NotifyContext` / Python signal handler。配 `preStop` hook 和 `terminationGracePeriodSeconds`(細節 → `zero-downtime-release`)。不處理 SIGTERM = 每次發版都硬斷、丟請求。

**⑤ 選主 / 鎖 —— k8s API 給,不是語言給。** 多副本裡選一個 leader(跑定時任務 / 寫主),用 **client-go 的 leaderelection**,底層是搶一個 k8s **Lease 對象**(etcd 撐強一致)。Python 有對應 kube-leader 庫。**重點:這個能力是 k8s API(etcd)給的,不分語言** —— 和 Spring Cloud 沒有也得靠外部 ZK/Redis 是一回事。

---

## Part B · 框架在哪裡補位(polyglot 現況校準)

契約講完,剩下「業務框架」只補**平台不給的那一小塊**(RPC 腳手架、參數校驗、中間件)。現況(2026,別寫回老印象):

**Go —— 真實的「West / China 分裂」:**

- **西方主流 = stdlib-first,不上重框架。** raw **gRPC-go** / **connect-go** + `net/http` 標準庫 + k8s 原語,就夠了。JetBrains 2025 調查裡,Go 開發者默認就是標準庫優先,那些「微服務框架」根本排不上號。
- **中國主流 = batteries-included 治理框架**:**Kratos**(**B站**,非阿里)、**Kitex**(字節,高性能 RPC)、**go-zero**、**Dubbo-go**(橋接 Java Dubbo 生態)。
- ⚠️ **兩個別再推薦的**:**go-kit** 已凍結(末版 2023)、**go-micro** 轉型成了 AI-agent harness —— 都別當活的微服務選型答案。

**Python —— 根本沒有 Spring Cloud 等價物:**

- 沒有任何 Python 框架打包「發現 + 配置 + 熔斷 + 客戶端 LB」。Python 服務就是 **FastAPI**(#1 API 框架)做無狀態 HTTP,擺在 k8s Service + Ingress 後面。
- 服務間:普通 HTTP(httpx)或 gRPC。
- **異步 / 分佈式任務**:**Celery 或 Dramatiq / Arq / Taskiq**(別只說 Celery 了),持久化工作流可上 Temporal。
- 治理(發現 / LB / 韌性)**整個甩給 k8s + (可選)mesh**。Nameko 那種「Python 微服務框架」niche 且維護放緩,別當主流。

---

## Part C · 收口:整個 track 的最後一塊拼圖

把五章連起來,你的三個原始問題現在有了統一答案:

**共識 / 協調不分語言。** 選主、分佈式鎖、強一致配置,**Java / Go / Python 都一樣**靠 etcd / ZooKeeper / Consul(背後 Raft / Paxos)。Spring Cloud 自己也沒解決這個 —— 它一樣外包給 ZK/Consul。所以這層**沒有「語言差」**,Go/Python 不比 Java 弱。

**「人人都上 mesh」是 folklore。** CNCF 2024 調查:**service mesh 採用率 42%,比前一年的 50% 還下降**了(運維成本勸退)。所以真實世界裡,**多數團隊靠 k8s 原語 + 小庫**做分佈式,**不是靠 mesh**。別在面試裡把 mesh 說成默認標配。

**最終收口(背起來):**

> Spring Cloud 把治理塞進 **JVM library(胖客戶端)**,是因為 2015 年它底下**沒有平台**。k8s 來了之後,這些能力**下沉**到平台(發現 / 配置 / 探活 / LB)+ 數據面(熔斷 / mTLS / 路由)+ 外部協調系統(共識)。
> Go / Python **不是缺組件**,是**生在這套基礎設施之上,只需講好 k8s 的契約(DNS / env / 探針 / 信號 / Lease)就完成了整合**,框架只補平台不給的那一小塊。
> 而 Java 自己也在走同一條路(`spring-cloud-kubernetes`、棄 Netflix OSS)。
> **所以這從來不是「Go/Python 怎麼追上 Spring Cloud」,而是「大家一起把治理下沉到了平台」—— 是時代差,不是語言差。**

---

## 交叉引用

- **RPC 範式 / 跨生態框架對照(gRPC / Kitex / FastAPI)→ `system-design/04-服務化與通信範式`**
- **SIGTERM / preStop / 優雅下線細節 → `distribution/zero-downtime-release`**
- **探針 / readiness 如何驅動「發現摘除」→ `02` Part A、`cloud-native/05`**
- **mesh 把熔斷 / mTLS 下沉的內幕 → `cloud-native-landscape/04`**
- **共識 / Raft / 選主 → `distribution/raft.md`、`etcd/`、`zookeeper/`**

---

## 本章小結

- **核心倒轉**:Spring Cloud = app 主動 push 註冊;k8s = 平台主動 pull 探測。Go/Python「整合 k8s」= **實現五項契約**:DNS 發現 / env 配置 / **探針健康** / SIGTERM 生命週期 / Lease 選主。
- **健康探針是整合的核心接口**:liveness(重啟)/ readiness(摘流量 = 發現摘除)/ startup;gRPC 用標準 Health 協議。
- **框架只補一小塊**:Go 西方 stdlib-first(gRPC/connect-go)、中國 Kratos(B站)/Kitex/go-zero/Dubbo-go;**go-kit 凍、go-micro 轉型**別推。Python 無等價物,FastAPI + 任務隊(Celery/Dramatiq/Arq/Temporal)+ k8s。
- **共識不分語言**(都靠 etcd/ZK/Consul);**mesh 是下降中的少數派(42%)**,不是標配。
- **總收口**:治理能力下沉到平台,Go/Python 靠講契約整合 —— **時代差,不是語言差**。

---

## 章末問答(複習自檢,答案要點都在前面正文)

1. Spring Cloud 和 k8s 在「服務怎麼被納入治理」上的模型,根本差別是什麼?(push vs pull)
2. Go/Python 和 k8s 整合的「五項契約」分別是什麼?
3. 服務發現在 Go/Python 裡默認要做什麼?什麼時候才需要 client-go watch Endpoints?
4. 三種健康探針各自的作用?readiness 失敗對應 `02` 講的什麼機制?
5. gRPC 服務怎麼暴露健康給 k8s?
6. 不處理 SIGTERM 會有什麼後果?
7. 多副本選主靠什麼?為什麼說「這是 k8s API 給的,不分語言」?
8. Go 微服務框架的「West/China 分裂」具體是什麼?哪兩個框架別再推薦了?
9. Python 為什麼沒有 Spring Cloud 等價物?它靠什麼做分佈式?
10. 為什麼說「人人都上 mesh」是 folklore?真實數據是多少?
11. **綜合題(整個 track 的收口)**:面試官說「你只會 Java 那套 Spring Cloud,上了 k8s、又是多語言團隊,你怎麼做服務治理」——用「治理下沉到平台 + Go/Python 靠講契約整合 + 共識不分語言 + 時代差非語言差」這條主線,把五章串成一個完整回答。
