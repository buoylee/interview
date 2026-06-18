# 可觀測性(Observability)一張地圖

> 面試導向 · 開發者視角(不是運維)· 以 OpenTelemetry 為主軸串起整個體系
>
> 這份文件要解決一件事:**為什麼有這麼多看起來在做同一件事的工具?** Prometheus、Loki、Tempo、Grafana、Elasticsearch、Logstash、Kibana、Jaeger、Zipkin、SkyWalking……名字一堆,其實每一個都只是「**某個信號**」在「**某個階段**」的工具。看懂下面這張表,soup 就變成格子。

---

## 核心框架:信號 × 階段

任何一個工具名,先問兩個問題就能歸位:**它處理哪種信號?它在管線的哪一段?**

| 階段 ＼ 信號 | **Metrics**(數字/趨勢) | **Logs**(事件/細節) | **Traces**(一個請求的全鏈路) |
|---|---|---|---|
| ① 產生(你的程式) | OTel Metrics SDK / Micrometer | 結構化日誌 + `trace_id` | OTel Trace SDK / **自動注入 agent** |
| ② 採集 · 處理 | Prometheus 抓取 / **OTel Collector** | Logstash · Fluentbit · Promtail / Collector | OTel Collector / **SkyWalking Agent→OAP** |
| ③ 儲存 | Prometheus TSDB / Mimir | **Elasticsearch** / **Loki** | **Tempo** / **Jaeger** / **Zipkin** |
| ④ 查詢 · 視覺化 | **Grafana** | **Kibana** / Grafana | Jaeger UI / Zipkin UI / **Grafana** / SkyWalking UI |
| ⑤ 告警 | Alertmanager / Grafana | (從 logs 衍生指標再告警) | (從 traces 衍生指標再告警) |

兩句話把這張表的「主軸」講完:

- **OpenTelemetry = ①②的廠商中立標準**。它統一了「在程式裡怎麼產生信號」(SDK)和「資料長什麼樣、怎麼傳」(OTLP 線格式)。因為有它,③ 的後端可以隨便換、不用改程式。
- **APM(SkyWalking 是代表)= 把 ②③④ 打包成一個產品,外加一個會自動抓資料的 agent**。它用「省事、開箱即用」換掉「自由組裝的彈性」。

---

## 三大生態系,各一句話定位

很多名字其實是「同一個哲學流派的套裝」。你只要記住三套:

| 生態系 | 組成 | 一句話哲學 |
|---|---|---|
| **Grafana LGTM** | **L**oki(logs)+ **G**rafana(viz)+ **T**empo(traces)+ **M**imir/Prometheus(metrics) | 每種信號各用最省成本的專用後端,統一在 Grafana 一個畫面裡關聯 |
| **ELK / Elastic Stack** | **E**lasticsearch(存+搜)+ **L**ogstash(收集轉換)+ **K**ibana(UI)+ Beats | 以一個強大的搜尋引擎為核心,日誌/全文搜尋優先,三種信號都能塞進去 |
| **SkyWalking** | Agent + OAP + Storage + UI | 開箱即用的 APM,Java/微服務首選,幾乎不改程式就有調用拓撲與鏈路 |

它們**看似重疊**,是因為三種信號每一種都需要「產生→採集→存→看」這同一條管線,於是每套都得有自己對應的工具。它們**競爭**,是因為哲學不同(專用後端 vs 全文搜尋 vs 一體化 APM)。第 6 章把這三套擺在一起對比。

---

## 怎麼讀這份文件

建議順序就是章節順序;每一章都會在「能白板畫出來」和「講得出選型理由」之間取平衡。標 🔬 的段落是你要的**開發者內幕**(可以在面試多撐 5 分鐘的地方)。

| 章 | 檔案 | 你讀完能做到 |
|---|---|---|
| 1 | `01-三支柱-metrics-logs-traces.md` | 講清三種信號各回答什麼問題、為何缺一不可 |
| 2 | `02-opentelemetry-是什麼.md` | 講 OTel 是什麼、API/SDK/Collector 在你程式裡實際做什麼 🔬 |
| 3 | `03-分散式追蹤內幕.md` | 白板畫出 span 樹、講清 trace context 怎麼跨服務傳 🔬 |
| 4 | `04-後端選型.md` | 講出 Jaeger/Tempo、Prometheus pull/push、Loki/ES 的取捨 |
| 5 | `05-三大生態系對比.md` | 把 LGTM / ELK / SkyWalking 擺一起,講何時選哪套 |
| 6 | `06-apm-與-skywalking.md` | 講 APM 是什麼類別、SkyWalking agent 怎麼字節碼注入 🔬 |
| 7 | `07-開發者實際要做什麼.md` | 知道身為 SWE 你真正要動手的那幾件事 |
| 8 | `08-面試自檢問答.md` | 對著白板題自我抽考(內幕都在前面,這裡只複習) |

---

## 一句話總綱(背起來)

> **三種信號**(metrics 知道「有沒有事」、logs 知道「發生什麼事」、traces 知道「事在哪一段」),
> **OpenTelemetry** 統一了它們怎麼產生與傳輸,
> 然後你**挑後端**存起來(Prometheus/Loki/Tempo 或 ES,或交給 SkyWalking 一體化),
> 最後用 `trace_id` 把三種信號**串成一個畫面**,從告警一路點到出問題的那一行程式。
