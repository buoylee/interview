# Spring Cloud 上 k8s,治理層去哪了(Service Governance on k8s)— 一張地圖

> 面試導向 · **架構師視角** · 以 Spring Cloud 為錨、結論**語言中立** · 坐在 `system-design/05 服務治理設施` 之上深化
>
> 這個 track 只解決一件事:**你原本靠 Spring Cloud 全家桶扛的服務治理(發現 / 配置 / 負載均衡 / 熔斷),搬到 k8s / mesh 之後,每一層去哪了、該怎麼選 —— 以及 Go / Python 從一開始就沒有全家桶,它們怎麼做同一件事。**

---

## 這個 track 落在哪(先認位置)

你 repo 裡已經有「組件是什麼」和「k8s 機制怎麼運作」,這份補的是**夾在中間沒人管的那層縫:組件搬上 k8s 之後,治理層到底怎麼重組**。

```
spring-cloud/ + nacos/(舊筆記)   ★ service-governance-on-k8s/(這份)    cloud-native/ · cloud-native-landscape/
組件各是什麼            ───►       上 k8s 後每層去哪、怎麼選         ───►    k8s / mesh 機制本身怎麼運作
Eureka/Ribbon/Feign…              遷移 / 長連接 / polyglot 落地              Service/kube-proxy/CoreDNS/Istio
                                  ↑ 深化 system-design/05(那章給了骨,這份填肉)
```

`system-design/05` 把服務發現 / 配置 / 負載均衡 / 服務網格的**骨架**講了(client-side vs server-side、CP/AP、L4/L7)。但它**明確輕量帶過**,沒回答你真正卡住的三件事:**Spring Cloud 那套搬上來具體怎麼對映、長連接為什麼會壞、Go/Python 沒有全家桶又怎麼辦**。這個 track 專攻這三件。

---

## 這個 track 治的病

五個你問過、面試也遲早會問的問題:

| 你的問題 | 在哪章解 |
|---|---|
| 整合時,**相同定位**的組件(Eureka vs CoreDNS)怎麼選? | `02` 上半 |
| 相同定位但**特性不同**(CoreDNS 沒有權重 / 推送)怎麼處理? | `02` 下半(特性差補法矩陣) |
| **服務內部**(東西向)的長連接怎麼做負載均衡? | `03` + lab |
| 需要**和 client**(南北向、瀏覽器 / 手機)的長連接又怎麼處理? | `04` |
| Go / Python 沒有 Spring Cloud,怎麼**和 k8s 整合**? | `05` |

---

## 一個轉變,推出大半結論

Spring Cloud 那套「長那樣」,根子是**一個時代背景**,以及它正在被**一個轉變**推翻:

| | Spring Cloud 時代(pre-k8s) | k8s / mesh 時代 |
|---|---|---|
| 治理放哪 | **JVM library 裡**(胖客戶端) | **平台(k8s)+ 數據面(sidecar)** |
| 誰負責註冊 | app 主動 `register` 到 Eureka(**push**) | app 被動暴露探針,平台來探(**pull**) |
| 語言 | 每種語言重寫一套 SDK | **語言無關**,平台統一 |
| 升級治理邏輯 | 推動所有團隊改代碼、重發版 | 改平台 / mesh 配置,**app 零侵入** |
| 為什麼長這樣 | 2015 Netflix OSS:底下**沒有平台**,只能 library 自己扛 | 有了 k8s,**橫切關注點往下沉** |

→ 這不是誰比較先進,是**底座變了**:當應用底下多了一個會調度、會探活、會轉發的平台,那些本來要 library 扛的事,自然往下沉到平台和數據面。一旦接受這個轉變,大半結論其實是**推論**:Eureka 變 CoreDNS、Ribbon 變 kube-proxy、Hystrix 變 sidecar、Config Server 變 ConfigMap —— 應用越來越薄。

---

## 脊柱(整個 track 的 through-line)

> **Spring Cloud = 胖客戶端 / 智能庫;雲原生 = 瘦客戶端 / 智能平台。**
> 治理能力一個沒少,只是從「JVM library」**下沉**到「k8s 平台 + Envoy 數據面 + 外部協調系統(etcd/ZK/Consul)」。
> Go / Python 不是「缺組件」,是**生在這套基礎設施之上,沒必要在語言層重造一遍** —— 而 Java 自己也在走同一條路(`spring-cloud-kubernetes`、棄用 Netflix OSS)。**是時代差,不是語言差。**

但下沉**不是無腦平推**,真正考你的是兩個細節(`02`/`03`/`04` 的重點):

- **`02`:「選一個」只是上半場。** 同層不能兩套並行(雙重真相源),但 k8s-native 常常**特性更窮**(CoreDNS 沒有權重 / 元數據 / 推送 / 灰度)。真問題是:**缺的特性去哪補** —— 保留富 registry?下沉 mesh?app 自己實現?還是其實沒人用、直接砍?
- **`03`/`04`:長連接不是一種。** **東西向**(自家服務調自家服務,你**控兩端**)和**南北向**(瀏覽器 / 手機連進來,你**不控 client**)是**兩套完全不同的工具箱** —— 前者能逼 client 重連、後者逼不動。

---

## 章節地圖

每章格式固定:**機制 / ASCII 圖 → 🔬 黑盒內幕寫進正文 → 選型 / 取捨 / 反模式 → 章末問答(只複習自檢)**。

| 章 | 檔案 | 讀完你能做到 |
|---|---|---|
| `README` | 本頁 | 認清「下沉」這個轉變 + 整個 track 的地圖與脊柱 |
| `01` | Spring Cloud 全家桶 + Netflix OSS 2026 現況 | 講清每個組件管什麼、哪些已死哪些還活(別寫回 folklore),為何開始外移 |
| `02` | 整合與選型:同層選一 + 特性差怎麼補 | 一套「同定位、不同特性」的補法矩陣(保留 / 下沉 mesh / app 實現 / 砍掉) |
| `03` | 長連接 LB ①:服務內部 / 東西向 + **lab** | 講清 gRPC 為何釘一個 pod,headless+round_robin / MaxConnAge / mesh 怎麼修 |
| `04` | 長連接 ②:對 client / 南北向 | 說清你不控 client 時,sticky / 排空 / 重連抖動 / idle timeout 怎麼處理 |
| `05` | Go / Python ↔ k8s 整合 + polyglot 收口 | 講清「整合 = 講契約(探針 / 信號 / DNS)不是裝框架」,三生態怎麼落地 |
| `lab/` | kind 上的 gRPC pinning 實跑 | 親眼看到「全打一個 pod → round_robin 分散」你自己的數字 |

---

## 和鄰居的關係(別搞混)

| 目錄 | 管什麼 | 一句話 |
|---|---|---|
| `spring-cloud/` · `nacos/` | 組件**是什麼** | 舊筆記,已被本 track 吸收;當詞典查 |
| **`service-governance-on-k8s/`(這份)** | 上 k8s 後治理層**怎麼重組** | 遷移 / 長連接 / polyglot 的決策層 |
| `system-design/05-服務治理設施` | 治理的**骨架** | 發現 / 配置 / LB / mesh 的通論;本 track 是它的深化 |
| `system-design/04-服務化與通信範式` | RPC / 通信**範式** | 同步 RPC vs 異步消息;本 track `05` 接它的框架對照 |
| `cloud-native/05-networking` | k8s 網路**機制** | Service / kube-proxy / CoreDNS 怎麼運作;本 track 引用不重講 |
| `cloud-native-landscape/04-service-mesh` | mesh **內幕** | sidecar→ambient 演進;本 track `02`/`03`/`04` 指向它 |
| `gateway/03-routing-and-load-balancing` | 網關 **LB 算法** | 邊緣路由 / 健康檢查;本 track `04` 指向它 |
| `distribution/zero-downtime-release/05` | 連接**排空機制** | 優雅下線細節;本 track `04` 指向它 |

---

## 一句話總綱(背起來)

> Spring Cloud 把服務治理塞在 **JVM library** 裡,是因為 2015 年它底下**沒有平台**;k8s 來了之後,這些能力**下沉**到平台與數據面,應用越來越薄。
> 搬遷的原則是**同層選一**,但難點在 **k8s-native 特性更窮時缺的那塊去哪補**;
> 長連接會壞,是因為 **kube-proxy 是 L4、把整條 TCP 連接釘在一個 pod** —— 而**東西向(控兩端)和南北向(不控 client)要分開治**;
> Go / Python 沒有全家桶不是缺陷,它們**靠講好 k8s 的契約(探針 / 信號 / DNS / env)來整合**,框架只補平台不給的那一小塊。
> 一句話:**治理能力沒消失,只是從庫裡搬到了平台 —— 是時代差,不是語言差。**
