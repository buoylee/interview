# 01 · Spring Cloud 全家桶,以及它正在發生的事(Netflix OSS 2026 現況)

> 🔬 起點:把你熟的全家桶**每根支柱管什麼**先擺清楚 —— 但**別停在 2018 年的認知**。這幾年 Netflix OSS 大半已死、替代品換了名、連 Spring Cloud Gateway 都拆成兩個模塊了。面試講「我們用 Hystrix 熔斷」會立刻露出你沒跟上。這章先把「**哪些死了、哪些還活、換成了什麼**」校準對,再說清**為什麼這些能力開始往下沉** —— 那就是整個 track 的起點。
>
> 框架對照一律生態平衡;這章因為主題就是 Spring Cloud,Java 含量高是合理的,但結論指向「能力外移」這件語言無關的事。

---

## Part A · 全家桶地圖:六根支柱各管什麼

「Spring Cloud」不是一個東西,是**一組各管一件治理事的庫**拼起來的全家桶。先認清每根支柱對應哪個**橫切關注點**(這個對應關係,正是後面每一層「去哪了」的座標):

| 支柱(經典實現) | 管的橫切關注點 | 一句話 |
|---|---|---|
| **Eureka** | 服務發現 | 實例啟動向它註冊、心跳續約;調用方來查「活著的實例列表」 |
| **Ribbon** | 客戶端負載均衡 | 調用方**自己**拿到實例列表、自己挑一個(client-side LB) |
| **Feign / OpenFeign** | 聲明式 RPC | 把 HTTP 調用寫成 Java interface,底層走 Ribbon 選實例 |
| **Hystrix** | 熔斷 / 隔離 | 下游掛了就快速失敗 / 降級,不讓故障擴散(艙壁 + 斷路器) |
| **Zuul** | API 網關 | 南北向入口:路由、認證、限流 |
| **Config Server** | 配置中心 | 配置集中存、推送、灰度,不用重新發版 |
| **Sleuth + Zipkin** | 鏈路追蹤 | 跨服務串一條 trace,定位慢在哪 |

> 記住這張表的「中間欄」。它就是 `system-design/05` 講的那幾件治理事(發現 / 配置 / LB / 熔斷 / 追蹤)的 **Spring Cloud 具體實現**。`02` 會把「中間欄」逐欄搬到 k8s,看每欄落在哪。

**一個關鍵性質(後面反覆用到):這套是「胖客戶端」。** Eureka 的列表是**調用方自己拉**的、Ribbon 是**調用方自己選**的、Hystrix 的斷路器跑在**調用方進程裡**。治理邏輯**全在 app 的 JVM 裡**,每個服務、每種語言都得把這套 SDK 引一遍。這個性質是它後來被下沉的根本原因 —— 記住它。

---

## Part B · 2026 現況:哪些死了、哪些還活 🔬

這是面試最容易翻車的地方。**Spring Cloud Netflix 這套大半已經停更或從 Spring Cloud 移除了**,但很多人的認知還停在 2017。校準一下:

| 組件 | 2026 狀態 | 換成了什麼 |
|---|---|---|
| **Hystrix** | ☠️ 維護模式(2018-11)、**2020.0 從 Spring Cloud 移除** | **Spring Cloud Circuit Breaker**(抽象)+ **Resilience4j**(引擎)|
| **Ribbon** | ☠️ 維護模式、2020.0 移除 | **Spring Cloud LoadBalancer**(現在唯一的客戶端 LB)|
| **Zuul 1** | ☠️ 替換 | **Spring Cloud Gateway** |
| **Archaius** | ☠️ 移除 | **Spring Cloud Config** + 標準 `Environment` / `@ConfigurationProperties` |
| **Turbine** | ☠️ 隨 Hystrix 一起淘汰 | (Hystrix dashboard 整套都沒了)|
| **Eureka** | ✅ **仍出貨、仍維護** | 自己;但新專案常用 k8s 發現取代 |

**三個必須記對的細節(面試講錯就掉分):**

1. **別把「Spring Cloud Netflix」一竿子打翻。** 死的是 Hystrix / Ribbon / Zuul1 / Archaius / Turbine;**Eureka 是唯一倖存、仍在維護的 Netflix 模塊**(活躍線是 2.0.x 的 Jakarta build —— 別跟那個早就放棄的「Eureka 2.0 重寫」搞混)。所以「Eureka 停更了」是**錯的**,「Hystrix 停更了」才對。

2. **熔斷要點名兩層:`Spring Cloud Circuit Breaker`(抽象)+ `Resilience4j`(引擎)。** 只說 Resilience4j 不算錯,但講出「Spring 用 Circuit Breaker 這層抽象把引擎換成了 Resilience4j」更顯你跟得上。

3. **Spring Cloud Gateway 現在是兩個模塊,不是一個。** 2025.1(Oakwood)起拆成 **`gateway-server-webflux`(reactive)** 和 **`gateway-server-webmvc`(servlet)**;舊 starter 名 2025.0 棄用、2025.1 移除,配置前綴也搬到 `spring.cloud.gateway.server.webflux.*` / `.webmvc.*`。還按「單模塊 spring-cloud-starter-gateway」答就過時了。

### 🔬 黑盒內幕:為什麼**正好是這幾個**先死?

不是隨機淘汰。死掉的那幾個,**恰好都是「平台 / mesh 能接管」的層**:

- **Hystrix(熔斷)** → 熔斷 / 重試 / 超時是**網路級**橫切關注點,sidecar(Envoy)能無侵入地做 → 下沉到 mesh。
- **Ribbon(客戶端 LB)** → LB 是**連接級**的事,kube-proxy(L4)或 mesh(L7)在平台層就做了 → 下沉到平台。
- **Zuul(網關)** → 南北向入口 k8s 有 Ingress / Gateway API → 下沉到平台。

而 **Eureka(純發現)活下來**,是因為「**我有哪些活實例**」這件事:在**非 k8s 或混合(VM+k8s)**環境裡,平台沒法替你回答,registry 仍有獨立價值;而且它輕、AP、好懂。換句話說 —— **能被平台接管的先死,平台接管不了(或你還沒上平台)的活著。** 這條規律,就是下一章「每層去哪了」的內在邏輯。

---

## Part C · 為什麼這些能力開始外移(下沉命題)

把現況連起來,會看到一個方向:**治理能力正在從 app 的 library 裡,往下沉到平台和數據面。** 為什麼?

**先看它當初為什麼長成全家桶。** Spring Cloud 起於 2015 年的 Netflix OSS —— 那時**應用底下沒有 k8s**,沒有一個會調度、會探活、會轉發的平台。服務要找到彼此、要熔斷、要均衡,**只能靠 app 自己進程裡的 SDK 扛**。胖客戶端不是設計品味,是**那個時代沒有別的地方放**。

**再看現在為什麼要往下挪。** 有了 k8s 這層底座之後,把治理留在 library 裡有三個越來越痛的代價,正好對應三個下沉動機:

| library 扛的痛 | 下沉後 |
|---|---|
| **每種語言重寫一套 SDK**(Java 有、Go/Python 各自再造)| **語言無關**:平台 / sidecar 一份,誰都能用 |
| **升級治理邏輯要改代碼、重發所有服務** | **與發版解耦**:改平台 / mesh 配置,app 零侵入 |
| 治理策略散在各 app、運維看不見也改不動 | **運維可控**:策略集中在控制面,統一下發 |

> 這就是 README 那句脊柱的由來:**Spring Cloud = 胖客戶端 / 智能庫;雲原生 = 瘦客戶端 / 智能平台。** 不是 Spring Cloud 設計差,是**底座變了**,橫切關注點自然往有能力接的那一層沉。

**但「下沉」不是一句口號就能照做。** 真到了遷移現場,你會立刻撞到兩個硬問題,正是後面幾章要解的:

- **`02`**:Eureka 換 CoreDNS 聽起來很乾脆,但 CoreDNS **沒有**權重、元數據、主動推送、灰度 —— k8s-native 常常**特性更窮**。那缺的那塊去哪補?
- **`03`/`04`**:LB 下沉到 kube-proxy,結果 **gRPC 長連接全被釘在一個 pod 上**。為什麼?怎麼修?而且**東西向和南北向還得分開治**。

---

## 交叉引用

- **這套治理事的通論(發現 / 配置 / LB / mesh)→ `system-design/05-服務治理設施`**(本 track 是它的深化)
- **同步 RPC vs 異步消息的範式選擇 → `system-design/04-服務化與通信範式`**
- **熔斷 / 重試 / 超時的韌性原理 → `system-design/01-韌性`**
- **下一步:每層搬上 k8s 去哪了 → `02`**

---

## 本章小結

- **全家桶 = 一組各管一件治理事的庫**:Eureka(發現)/ Ribbon(客戶端 LB)/ Feign(RPC)/ Hystrix(熔斷)/ Zuul(網關)/ Config(配置)/ Sleuth+Zipkin(追蹤)。關鍵性質:**胖客戶端,治理全在 app 的 JVM 裡**。
- **2026 現況校準**:Hystrix / Ribbon / Zuul1 / Archaius / Turbine **已死 / 移除**(2020.0);**Eureka 是唯一倖存、仍維護的 Netflix 模塊**。替代:Spring Cloud Circuit Breaker + Resilience4j、Spring Cloud LoadBalancer、Spring Cloud Gateway(**2025.1 拆 webflux/webmvc 兩模塊**)。
- **為什麼正好這幾個死**:能被平台 / mesh 接管的(熔斷→mesh、LB→kube-proxy、網關→Ingress)先死;平台接管不了的純發現(Eureka)活著。
- **下沉命題**:全家桶是 2015「底下沒平台」逼出來的;k8s 來了之後,治理因**語言無關 / 與發版解耦 / 運維可控**三個動機往下沉。
- **下一章**:把每根支柱搬上 k8s,看它**落在哪、怎麼選、特性差怎麼補**。

---

## 章末問答(複習自檢,答案要點都在前面正文)

1. Spring Cloud 全家桶的六 / 七根支柱各管什麼橫切關注點?
2. 為什麼說這套是「胖客戶端」?這個性質和它後來被下沉有什麼關係?
3. 下面哪些**已從 Spring Cloud 移除 / 停更**,各換成了什麼:Hystrix、Ribbon、Zuul1、Archaius?
4. Eureka 現在是什麼狀態?為什麼說「Spring Cloud Netflix 全死了」是錯的?
5. 熔斷現在的正確說法要點名哪兩層(抽象 + 引擎)?
6. Spring Cloud Gateway 在 2025.1 之後有什麼結構變化?還按單模塊答為什麼會過時?
7. 🔬 為什麼**正好是** Hystrix / Ribbon / Zuul 先死,而 Eureka 活下來?背後的規律是什麼?
8. 全家桶當初為什麼會長成「胖客戶端」?(2015 年的時代背景)
9. 把治理留在 library 裡有哪三個痛?分別對應下沉後的什麼好處?
10. **綜合題**:面試官問「你們以前用 Spring Cloud,現在上 k8s 了,這套還留著嗎」——用「哪些能被平台接管所以該退、哪些(如純發現)還有獨立價值」這條規律來組織你的回答,並點出下一步要面對的「特性差」和「長連接」兩個硬問題。
