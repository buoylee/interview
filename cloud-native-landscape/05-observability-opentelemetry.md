# 05 · 可觀測環:OpenTelemetry 統一三支柱

> **一句話定位**:前面幾環(網絡、網格)產生了海量遙測,但**指標/日誌/追蹤**若各用各的 SDK、各自的格式、各自的後端,你出事時還是拼不出全貌。這一環講 **OpenTelemetry(OTel)** 怎麼把「採集」這層統一,讓你真能「看見」分布式系統內部。

> **本章深度層**:外環。三支柱的**深度落地**(指標設計、日誌、追蹤實戰)在 `observability/` track 已寫;本章寫 **OTel 在全景裡的角色、架構、失敗模式、選型**,細部指進。

---

## 🕰 變遷盒

| | 舊世界(2019-2020) | 新世界(2026) |
|---|---|---|
| 指標 | Prometheus + 自家 client 庫 | OTel SDK 產生,OTLP 輸出(後端仍可 Prometheus) |
| 日誌 | ELK / Fluentd,各自格式 | OTel logs + 結構化 + 關聯 trace |
| 追蹤 | Jaeger / Zipkin,各自 SDK | OTel traces,W3C trace context 標準 |
| 採集 | 每種信號一套 agent / SDK / 協議 | **一個 SDK + 一個協議(OTLP)+ 一個 Collector** |
| 廠商鎖定 | 換後端 = 重新埋點 | **埋點與後端解耦**:換後端不動代碼 |

**一句話**:OTel 的價值不是「又一個監控工具」,而是**把「怎麼採集和傳輸遙測」標準化**——一次埋點,任意後端;這也是你「依賴 SaaS 不安心」的解法(逃生票:隨時換自托管後端,不用重埋)。

---

## 1. 核心敘事

### 1.1 三支柱 + 把它們縫起來的線

- **Metrics(指標)**:聚合數字,便宜、適合告警和趨勢(QPS、p99、錯誤率)。
- **Logs(日誌)**:離散事件,適合事後細查。
- **Traces(追蹤)**:一個請求跨服務的完整路徑,**分布式系統的命根**——沒有它,微服務出問題你只能猜。
- (新興第四支柱:**Profiles 持續性能剖析**,OTel 已納入。)

關鍵不是三個各自存在,而是**用同一個 trace context 把它們縫起來**:一條指標的毛刺能跳到對應的 trace(exemplar),一條 trace 能拉出該 span 期間的日誌。**「縫合」才是可觀測,單看三個孤島不是。**

### 1.2 OTel 是什麼、不是什麼

```
你的服務
  │  OTel SDK / 自動埋點 / eBPF 零代碼埋點
  ▼  OTLP(統一協議)
┌─────────────────┐   receivers → processors → exporters
│ OTel Collector  │   (收)        (批/採樣/脫敏) (發)
└────────┬────────┘
         │ OTLP / 各後端協議
   ┌─────┼───────────────┐
   ▼     ▼               ▼
Prometheus  Loki/ELK   Tempo/Jaeger   ← 後端(存儲+查詢),OTel 不管這層
   └──────── Grafana 統一展示 ────────┘
```

**OTel 管的是**:埋點(SDK/自動/eBPF)、數據模型(語義約定)、傳輸協議(**OTLP**)、採集管道(**Collector**)。
**OTel 不管的是**:存儲和查詢——你仍需後端(Prometheus/Loki/Tempo/Jaeger 或某商業平台)。

**這個分層就是「逃生票」**:埋點和後端解耦,後端隨時可換(自托管 ↔ 商業),代碼不動。

### 1.3 Collector:廠商中立的管道

Collector 是一個獨立進程,`receivers`(收 OTLP/Prometheus/各種)→ `processors`(批處理、採樣、脫敏、加 k8s 元數據)→ `exporters`(發給任意後端)。它讓你:

- **集中治理**:採樣率、脫敏、限流在一處配,不散落各服務。
- **解耦後端**:今天發 Jaeger,明天加發 Datadog,改 Collector 配置即可。
- **兩種拓撲**:**agent**(每節點 DaemonSet,就近收)+ **gateway**(集中集群,做聚合/尾採樣)。

---

## 🏛 架構師視角

### 🔬 黑盒內幕

- **OTLP**:基於 gRPC/HTTP 的統一遙測協議,三支柱共用一套 wire format。
- **Context propagation**:W3C `traceparent` header 隨請求在服務間傳遞,讓跨服務的 span 串成一棵樹。**這是分布式追蹤能成立的根**——每個服務都得透傳這個 header(網格/框架自動做)。
- **採樣**:**head sampling**(請求一進來就決定採不採,便宜但可能丟掉後來才出錯的請求)vs **tail sampling**(等整條 trace 完成再決定,能「只留出錯/慢的」,但要 Collector 緩存全 trace、更貴)。
- **Exemplars**:指標數據點上掛一個 trace ID,讓「p99 毛刺」一鍵跳到「那一條慢請求的 trace」。

### 💥 失敗模式 / 故障域

| 故障 | 現象 | 根因 / 架構含義 |
|---|---|---|
| **基數爆炸(cardinality explosion)** | Prometheus 內存暴漲 / 成本失控 / 查詢變慢 | 把高基數值(user_id、request_id)塞進 metric label;**指標的頭號殺手** |
| Collector 成瓶頸/SPOF | 遙測丟失、背壓 | 單點 gateway 沒擴容;要水平擴 + agent/gateway 分層 + 隊列 |
| 採樣丟掉關鍵 trace | 出事時「正好沒採到那條」 | head sampling 配太低;改用 tail sampling 保「錯誤/慢」全採 |
| 日誌量 = 成本黑洞 | 賬單爆炸 | 全量 DEBUG 進後端;要分級 + 採樣 + 結構化 |
| span 時鐘錯亂 | trace 時間軸詭異 | 節點時鐘漂移;span 跨機器比較要小心(回扣 system-design 時鐘章) |

### 📈 規模化極限

- **基數 = 指標的規模天花板**:時序數量 ≈ 指標數 × 各 label 取值的笛卡爾積。一個帶 `user_id` 的指標在百萬用戶下 = 百萬條時序,直接撐爆。**鐵律:label 只放低基數維度(service/route/status_code),高基數的東西放 trace/log。**
- **trace 數據量**:全採 100% 在高 QPS 下存儲爆炸;典型做 1-10% head + tail 補全錯誤/慢請求。
- **Collector 擴展**:agent(就近、輕)+ gateway(集中、做尾採樣與聚合),gateway 要按吞吐水平擴。

### ⚖️ 選型論證

| 層 | 選項 | 怎麼選 |
|---|---|---|
| 埋點 | **OTel SDK / 自動埋點 / eBPF 零代碼** | OTel 已是事實標準,無腦選;新語言優先自動埋點/eBPF |
| 管道 | **OTel Collector** | 廠商中立、集中治理,標配 |
| 指標後端 | Prometheus / Mimir / Thanos | 自托管默認 Prometheus 系 |
| 日誌後端 | Loki / ELK / ClickHouse | 成本與查詢需求權衡 |
| 追蹤後端 | Tempo / Jaeger | 與 Grafana 整合選 Tempo |
| 展示 | Grafana | 三支柱統一面板 |
| 商業平台 | Datadog / Grafana Cloud / 各雲 | **因為 OTel,隨時可切回自托管(逃生票)** |

> **架構師判斷**:用商業平台省心沒問題,但**埋點一定用 OTel 而非廠商私有 SDK**——否則被鎖死,換家就得重埋。OTel 把「用不用 SaaS」變成可逆決策。

### 🧭 演進路徑

1. **私有 SDK → OTel SDK**:統一埋點,先保證 trace context 全鏈透傳。
2. **直連後端 → 過 Collector**:把採樣/脫敏/路由收斂到 Collector。
3. **手工埋點 → 自動 / eBPF**:減少代碼侵入,新服務零代碼起步。
4. **head → tail 採樣**:規模上來後切尾採樣,保住「錯誤和慢請求」這些你真正要看的。

### 🏭 生產事故 / 教訓

- **一個 `user_id` label 打爆 Prometheus**:某指標加了用戶維度,時序數百萬,Prometheus OOM、告警全瞎。教訓:**label 基數是設計約束,不是隨手加**。
- **尾採樣配錯,出事時沒 trace**:以為在採,實際關鍵錯誤被采樣丟了。教訓:**tail sampling 必須「錯誤/慢請求 100% 保留」**。

---

## 2. 現在主流怎麼選

| 決策 | 2026 主流答案 |
|---|---|
| 埋點 | **OpenTelemetry**(SDK + 自動 + eBPF),不用廠商私有 SDK |
| 採集管道 | **OTel Collector**(agent + gateway) |
| 自托管後端 | Prometheus(指標)+ Loki(日誌)+ Tempo/Jaeger(追蹤)+ Grafana |
| 採樣 | tail sampling,錯誤/慢請求全留 |
| 指標基數 | 嚴控 label,高基數放 trace/log |

---

## 🧵 示例服務在這一環

一筆「下單慢」的排查:用戶請求帶 `traceparent` 進入 **order-api**(網格自動注入/透傳)→ 調 **inventory** → inventory 讀 **Redis**。OTel 把這條鏈串成**一條 trace**:你一眼看到 95% 時間花在 inventory→Redis 的某次調用上。

怎麼發現的?指標面板上 `order-api` 的 p99 突刺,點開**exemplar** 直接跳到那條慢 trace;再從 trace 的 span 拉出該時段 inventory 的**日誌**——三支柱用一個 trace ID 縫合。而這些 span 大部分是**第 04 章的網格自動產生的**,業務代碼幾乎沒埋點。

對比 2019:當年指標在 Prometheus、日誌在 ELK、追蹤可能根本沒有,你得在三個系統間靠時間戳手工對齊——慢且常常對不上。

---

## 🔬 深挖出口

| 想深挖 | 去哪 |
|---|---|
| 三支柱深度落地(指標設計、SLO、日誌、追蹤實戰、OTel 細節) | `observability/` track(本線的深挖目的地) |
| 網格如何自動產生遙測 | 本線 `04-service-mesh` |
| 時鐘漂移為何影響 span 對齊 | `system-design/02-一致性模型與時鐘` |
| 性能維度的指標 | `performance-tuning-roadmap/` |

---

## 一句收口 + 地圖更新

> **OpenTelemetry 統一的是「採集與傳輸」這一層**:一個 SDK、一個協議(OTLP)、一個 Collector,把指標/日誌/追蹤用 trace context 縫成一張可導航的圖;後端可隨意更換(逃生票)。可觀測的關鍵不是有三支柱,而是**它們被縫起來、且你控制住了基數與採樣**。

**🗺 地圖更新**:你補上「看見」這一環,知道 OTel 的角色邊界、基數這個頭號陷阱、以及它怎麼讓 SaaS 決策可逆。
**下一站**:`06 交付環` —— 系統能跑、能看見了,但**怎麼把變更安全地推上去**?這一環是另一個 2019 沒有的格子:**GitOps + 漸進發布**。
