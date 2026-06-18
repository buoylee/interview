# 第 6 章 · APM 與 SkyWalking 深入

> 🔬 你 repo 裡有 SkyWalking 的截圖,代表你工作上碰過。這章把 **APM 是什麼類別**、**SkyWalking 的架構**、以及你最想懂的 **agent 怎麼字節碼注入** 講透。這也是 Java 背景的人在面試最容易拿分的一塊。

---

## 先定義:APM 是什麼類別

**APM = Application Performance Monitoring / Management(應用性能監控)**。它**不是一個工具,是一個產品類別**:把 **traces + metrics(常常 + logs)打包成一個產品**,配上**有主見的 agent + 現成儀表板 + 服務拓撲圖 + 告警**,目標是「掛上就能用」。

| | **DIY:OTel + 後端**(LGTM 那種) | **APM 產品**(SkyWalking 那種) |
|---|---|---|
| 組裝 | 自己挑埋點、Collector、各信號後端、UI | **一體化**,一個產品全包 |
| 埋點 | OTel SDK / 自動埋點(中立) | **自家 agent 自動埋點**(有主見) |
| 彈性 | 高,後端隨便換 | 低,綁這個產品 |
| 上手 | 要懂較多概念 | **開箱即用,拓撲圖直接出來** |
| 適合 | 雲原生、要彈性、避免鎖定 | 想快速上線、少操心 |

**開源 APM**:**SkyWalking**(Apache,Java 主場)、**Pinpoint**(韓國 Naver,Java)、Elastic APM。
**商用 APM**:**Datadog、New Relic、Dynatrace、AppDynamics**——功能更全但按量收費、會鎖定(這對你「不放心依賴 SaaS」的偏好正是要警惕的點:埋點用 OTel 就能保留逃生票,日後換得掉)。

**面試一句話**:「**APM 用『開箱即用、有主見』換掉『自由組裝的彈性』**。OTel + LGTM 是另一端;兩者可結合——用 OTel 埋點餵給 APM 後端,兼得中立與省事。」

---

## SkyWalking 架構:Agent → OAP → Storage → UI

```
   ┌──────────────┐  你的 Java 服務們(每個掛一個 agent)
   │  App + Agent │ ── 自動產生 trace + metrics
   └──────┬───────┘
          │  gRPC(SkyWalking 自家協定 / 也收 OTLP、Zipkin、Jaeger 格式)
          ▼
   ┌──────────────┐  OAP(Observability Analysis Platform)= 大腦
   │     OAP      │  接收 → 用 OAL 流式聚合 → 算拓撲/SLA/指標 → 寫儲存
   └──────┬───────┘
          ▼
   ┌──────────────┐  Storage:ElasticSearch / BanyanDB(自研)/ H2(demo)/ MySQL
   │   Storage    │
   └──────┬───────┘
          ▼
   ┌──────────────┐  UI:服務拓撲圖、鏈路、端點指標、告警
   │      UI      │
   └──────────────┘
```

逐層拆(面試能講出每層職責就很完整):

### Agent(資料來源)
掛在每個應用上,**自動**收集 trace 與 metrics,透過 gRPC 送給 OAP。Java 用 `-javaagent` 掛載(下一節細講)。其他語言(Go、Python、Node…)也有對應 agent / SDK,但 **Java 最成熟**。

### OAP(大腦,最該懂的一層)🔬
**O**bservability **A**nalysis **P**latform——SkyWalking 的伺服器端。它做四件事:
1. **接收(receiver)**:收 agent 資料;也能收 **OTLP**、Zipkin、Jaeger、Telegraf 等格式(這是它與 OTel 的接點)。
2. **分析(analysis)**:用 **OAL(Observability Analysis Language)**——一種類 SQL 的串流聚合語言——把原始 span 即時算成「服務每分鐘的 p99、錯誤率、吞吐」等指標。
3. **拓撲(topology)**:從 span 的「誰呼叫誰」自動畫出**服務調用拓撲圖**(SkyWalking 的招牌畫面)。
4. **儲存(persistence)**:把算好的指標與鏈路寫進 storage。
> 一句話:**OAP 是「邊收邊算」的串流分析引擎**,不是單純的儲存——這跟 Jaeger/Tempo「先存原始 trace、查時才算」是不同取向。

### Storage(存)
可插拔:**ElasticSearch**(生產最常見)、**BanyanDB**(SkyWalking 自研、為可觀測性最佳化的資料庫,新版主推)、H2(只給 demo)、MySQL/TiDB 等。

### UI(看)
自帶 Web UI:**服務拓撲圖、鏈路追蹤、各服務/端點指標、告警、慢查詢**。你截圖裡看到的就是這層。

---

## 🔬 重頭戲:Agent 怎麼「字節碼注入」做到零改碼

這是你指定要懂的內幕。問題:**SkyWalking(和 OTel Java agent)怎麼在你完全不改程式的情況下,自動替每個 HTTP 請求、每次 DB 查詢生 span?**

答案:**Java Agent + 字節碼增強(bytecode instrumentation)**,在類別被載入 JVM 的那一刻**改寫它的字節碼**,織入「開始/結束 span」的攔截邏輯。

### 一步步看(面試能講到這個層次就很突出)

```
1. 啟動加參數:  java -javaagent:skywalking-agent.jar -jar app.jar
                              │
2. JVM 載入 agent,呼叫它的 premain(...) 方法
   (premain 在你的 main() 之前執行——這是 java.lang.instrument 機制)
                              │
3. agent 透過 Instrumentation API 註冊一個 ClassFileTransformer
   (SkyWalking/OTel 底層用 ByteBuddy 這個函式庫來操作字節碼)
                              │
4. 之後每當一個「目標類別」被類別載入器載入時 ──┐
   (例如 Spring 的 DispatcherServlet、JDBC 的    │  transformer 被觸發
    PreparedStatement、Tomcat 的處理器…)         │
                              ▼
5. transformer 改寫該類別的字節碼:在目標方法的「進入」與「離開」
   插入攔截器(interceptor)呼叫:
     - 進入時:startSpan(...)、把當前 context 取出
     - 離開時:stopSpan(...)、記錄耗時/狀態/例外
     - 對「出站呼叫」(HTTP client、RPC):把 trace context inject 進 header
                              │
6. 被改寫後的類別正常執行;你的業務碼一個字沒動,
   span 卻自動產生並串接了 ── 這就是「零改碼全鏈路」的真相
```

幾個關鍵點:
- **`premain` / `java.lang.instrument`**:JDK 內建的「在 main 之前介入、可改寫類別」的官方機制。`-javaagent` 就是用它。
- **ByteBuddy**:實際做字節碼改寫的函式庫(SkyWalking 與 OTel Java agent 都用它)。你不用懂它的細節,但要知道「改寫是在類別載入時、針對**已知框架的特定類別/方法**做的」。
- **為什麼只對「已知框架」有效**:agent 內建一堆**外掛(plugin)**,每個外掛知道「Spring MVC 的入口方法是哪個」「JDBC 執行查詢的方法是哪個」,才知道往哪織入。**你自寫的業務方法不會自動有 span**——那要靠手動埋點(`@Trace` 註解或 OTel API)。這常是面試追問點。

### 對照:OTel Java agent 是同一招
`-javaagent:opentelemetry-javaagent.jar` 用**完全相同的機制**(premain + ByteBuddy)。差別只在:**SkyWalking agent 把資料送進 SkyWalking 自家協定/OAP;OTel agent 送的是 OTLP,可進任何 OTLP 後端**。所以你可以說:「兩者埋點原理一樣,差在**送去哪、被誰鎖定**。」

---

## SkyWalking 與 OTel 的關係(收束)

- **重疊**:兩者都能做「自動埋點 + 分散式追蹤」,agent 機制同源。
- **不同層次**:**OTel 只是「產生+傳輸」層(沒有儲存/UI);SkyWalking 是「agent + 後端 + UI」的完整產品**。
- **可協作**:SkyWalking OAP 能**接收 OTLP**,所以你能用 OTel 埋點、把資料餵進 SkyWalking 看拓撲圖。
- **選擇**:要拓撲圖與開箱即用 → SkyWalking;要中立、可換後端、避免鎖定 → OTel + LGTM。**埋點層用 OTel 最保險**(留逃生票)。

---

## 本章小結

- **APM 是產品類別**:把 traces/metrics(/logs)打包 + 有主見的 agent + 拓撲圖 + 告警,用「開箱即用」換「彈性」。
- **SkyWalking 架構**:Agent(自動採集)→ **OAP**(串流聚合 + 算拓撲的大腦,OAL)→ Storage(ES/BanyanDB)→ UI。
- **Agent 內幕**:`-javaagent` 走 `premain` + **ByteBuddy 字節碼改寫**,在類別載入時對**已知框架的方法**織入 start/stop span,所以零改碼;自寫業務方法要手動埋點。**OTel Java agent 同源,差在送去哪。**
- 下一章:把鏡頭拉回你自己——身為 SWE(不是運維),你**實際要動手**的是哪幾件事。
