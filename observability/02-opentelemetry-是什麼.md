# 第 2 章 · OpenTelemetry 是什麼、在你程式裡做什麼

> 🔬 這章是「開發者內幕」的第一塊。OpenTelemetry(常縮寫 **OTel**)是整份文件的主軸——它是「**怎麼產生信號、怎麼傳信號**」的廠商中立標準。搞懂它,後面的 Prometheus/Jaeger/Tempo 都只是「OTel 把資料送去的地方」。

---

## 它解決什麼問題(先講動機,面試先講這個)

在 OTel 之前,世界長這樣:
- 想要 trace,你引入 Zipkin 的 client;之後想換 Jaeger,得改一輪程式。
- 想要 metrics,你綁死 Prometheus 的 client library。
- 換監控廠商(Datadog→New Relic),埋點全部重寫。

**痛點:埋點(instrumentation)和後端(backend)被綁死了。** 你的業務程式不該關心資料最後存去哪。

**OTel 的主張**:把「**產生信號**」這件事標準化成一套跟廠商無關的 **API + SDK + 線格式**。你的程式只依賴 OTel;要送去 Jaeger 還是 Tempo 還是 Datadog,只是改一行設定(換 exporter),不動業務碼。

**身世**(一句話即可):2019 年由兩個前輩專案合併而成——**OpenTracing**(只定義 tracing 的 API 規範)+ **OpenCensus**(Google 出的、含 traces+metrics 的函式庫)→ 合併成 **OpenTelemetry**,進 CNCF,現在是僅次於 Kubernetes 的第二活躍 CNCF 專案。所以你會在老程式碼看到 OpenTracing/OpenCensus,它們是 OTel 的前身。

---

## OTel 的零件圖(把名詞對到位)

```
你的程式
 ├─ OTel API ──────── 你呼叫的介面(start span / 記一個 metric)
 ├─ OTel SDK ──────── 真正的實作(取樣、批次、匯出)
 ├─ Instrumentation ─ 預製整合(HTTP、DB、框架自動產生 span)
 │   library / agent
 └─ Exporter ──────── 轉成 OTLP / Jaeger / Prometheus 格式送出
            │
            ▼  (線格式:OTLP,走 gRPC 或 HTTP+protobuf)
   ┌─────────────────────┐
   │   OTel Collector    │  receiver → processor → exporter
   └─────────────────────┘
            │
            ▼
   後端(Jaeger / Tempo / Prometheus / Loki / ES / Datadog ...)
```

逐個拆(這就是你要的 SDK 內幕):

### API vs SDK——面試愛問的區分 🔬
- **API**:你在業務碼裡呼叫的那層介面,例如 `tracer.startSpan("createOrder")`。**它本身是 no-op(什麼都不做)**——只定義「形狀」。函式庫作者可以放心依賴 API 埋點,即使使用者沒裝 SDK 也不會出錯、零開銷。
- **SDK**:API 的**實際實作**。你在程式啟動時裝上並設定它,於是那些 span 才真的被建立、取樣、批次、匯出。
- **白話**:API 是插座規格,SDK 是真正接上的電。**換後端只動 SDK 設定,業務碼(只碰 API)完全不變**——這就是 OTel 解耦的精髓。

### Instrumentation:埋點怎麼來
- **手動埋點(manual)**:你自己 `startSpan` / 加屬性,通常用在業務關鍵操作。
- **函式庫埋點(library instrumentation)**:OTel 提供針對常見元件(HTTP client/server、JDBC、Redis、Kafka、Spring、Flask…)的預製套件,它們自動替你產生 span,你只要引入。
- **自動埋點(auto-instrumentation)** 🔬:**完全不改程式**就埋點。
  - Java:`-javaagent:opentelemetry-javaagent.jar`,在類別載入時用**字節碼增強**(ByteBuddy)織入追蹤邏輯。**這跟第 6 章 SkyWalking agent 是同一個機制**。
  - Python:`opentelemetry-instrument python app.py`,在 import 時 monkey-patch 已知函式庫。
  - **這是投報率最高的埋點方式**:零程式碼改動就先有一張全鏈路圖,之後再針對業務熱點補手動 span。

### Exporter 與 OTLP
- **Exporter**:把 SDK 收集到的 span/metric/log 轉成某種格式送出去。可以直接送 Jaeger/Prometheus,但**現代預設是送 OTLP**。
- **OTLP(OpenTelemetry Protocol)**:OTel 自己的線格式(gRPC 或 HTTP + protobuf)。**它是整個生態的通用語**——越來越多後端(Tempo、Jaeger、Prometheus、SkyWalking OAP、各家 SaaS)都直接收 OTLP。記住:**OTLP 是「資料在線路上長什麼樣」的統一規格**。
- **語意慣例(Semantic Conventions)**:OTel 還統一了**屬性的命名**,例如 HTTP 請求方法一律叫 `http.request.method`、DB 系統叫 `db.system`。這樣不同語言、不同服務產生的資料,後端能用同一套欄位查詢。面試可提一句:「OTel 不只統一了協定,還統一了**欄位語意**。」

---

## OTel Collector:那個中間的盒子 🔬

`Collector` 是一個**獨立的進程**(不是函式庫),長在你的應用和後端之間,**把應用跟後端徹底解耦**。它內部是一條三段管線:

```
receivers ──→ processors ──→ exporters
(收進來)      (加工)         (送出去)

receivers : OTLP / Prometheus 抓取 / Jaeger / Zipkin / Fluent / Kafka ...
processors: batch(批次)/ filter(過濾)/ attributes(改標籤)/ tail-sampling(尾取樣)/ memory_limiter
exporters : 送到 Tempo / Jaeger / Prometheus / Loki / ES / 多個後端同時送
```

**為什麼值得有這個盒子**(面試講得出這幾點就夠資深):
1. **解耦**:應用只管把資料丟給本地 Collector(OTLP),後端怎麼換、要不要同時送兩個地方,都在 Collector 改,**不動也不重啟應用**。
2. **集中加工**:打批次降低開銷、過濾敏感欄位、補上 `k8s.pod.name` 之類的環境資訊、做**尾取樣**(看完整條 trace 再決定留不留,例如「所有錯誤和慢請求都留、正常的只留 1%」——第 3 章細談)。
3. **減負**:重活從應用進程移到 Collector,應用只做最輕的匯出。

**兩種部署形態**(知道名詞即可,屬運維邊界):
- **Agent / sidecar 模式**:每台主機或每個 Pod 旁邊一個 Collector,就近收集。
- **Gateway 模式**:一個集中的 Collector 叢集,做統一加工再分發。
- 常見組合:應用 → 本地 agent Collector → 中央 gateway Collector → 各後端。

---

## 一張圖收尾:OTel 在表格裡的位置

回到 README 那張「信號 × 階段」表:**OTel 就是 ①(產生)和 ②(採集處理)的標準層**。

```
① 產生        ② 採集處理              ③ 儲存          ④ 看
─────────    ──────────────        ──────────      ──────
OTel SDK  →  OTel Collector   →   Prometheus  →   Grafana
(API+SDK)    (receiver/proc/       Tempo            Jaeger UI
 埋點         exporter,OTLP)        Loki / ES        Kibana
                                    SkyWalking OAP
```

**一句話記住 OTel**:它讓你「**寫一次埋點,信號隨便送去哪個後端**」——把易變的後端選擇,擋在業務碼之外。

---

## 本章小結

- OTel 解決的痛點:**埋點與後端綁死**。它用 **API+SDK+OTLP** 把「產生信號」標準化。
- **API 是 no-op 介面,SDK 是實作**;換後端只動 SDK/Collector 設定,業務碼不變。
- **自動埋點**靠字節碼增強/monkey-patch,零改碼先拿到全鏈路(跟 SkyWalking agent 同源)。
- **Collector** 是獨立進程,`receiver→processor→exporter`,負責解耦、加工、尾取樣。
- 下一章:把 trace 拆開,看 **span 樹與 context 跨服務傳播**的內幕。
