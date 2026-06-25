# 性能 · 容量 · 可靠性 —— 領域地圖

> 你大概有過這種感覺:**P99、QPS、SLO 這些東西,整個職涯好像都缺,學校也沒教,不知道在哪學的。**
>
> 這不是你的問題。這是一門**有名字的學科**——性能工程 / SRE / 容量規劃——而且它**刻意不在學校教**。這頁是它的地圖:它是什麼、人們在哪學的、骨架只有哪幾條原語、你 repo 裡哪個 track 對應哪一塊。

---

## 你在這裡 —— 三條入口

| 你現在想要 | 去哪 | 花多久 |
|---|---|---|
| **知道這門學科的全貌** | 繼續往下讀這張地圖 | 15 分鐘 |
| **知道我到底缺哪一格** | [`SELF-DIAGNOSTIC.md`](./SELF-DIAGNOSTIC.md) — 6 原語 × 3 層自測 | 15 分鐘 |
| **真的會做(不只看懂)** | [`FIRST-LOOP.md`](./FIRST-LOOP.md) — 親手跑出你自己的 P99 曲線 | 30–45 分鐘 |

> 建議順序:**診斷 → 跑一次閉環 → 回來讀地圖**。先量出座標,再親手做一次,最後把那次經驗掛回整門學科的框架。光讀地圖治不好「我是不是真的懂系統」的焦慮——只有**做過一次**能。

---

## 1. 這是什麼學科,為什麼學校不教

學校教的是 backend 的**算法那一半**:Big-O、資料結構、OS 原理、編譯。它**刻意不碰**運維那一半:百分位、吞吐單位、SLO、排隊論的實際應用、容量定容。原因很現實——

- 這半門課的知識**只在「真有流量、真會痛」時才成立**。沒有生產系統、沒有 oncall、沒被半夜的 P99 叫醒,這些概念是懸空的,課堂上考不出來。
- 它不是「定理」,是**工程判斷 + 經驗數字**,沒有標準答案。

所以「我缺這個」不是個人缺陷,是**全世界 CS 教育的結構性缺口**。你身邊「會這個」的人,沒有一個是學校學的。

## 2. 人們到底在哪學的

「在職、被資深帶」是真的,但有個常被忽略的前提:**得在「規模逼著你算這些數字」的公司**。小流量公司待 5 年一樣不會——因為從沒痛過。所以這層空白多半不是能力差,是**過去的系統規模沒逼出這層需求**。

好消息是:它有一套**公開的正典**,不必靠運氣遇到好師父。

| 來源 | 解決你哪個困惑 |
|---|---|
| **Gil Tene — “How NOT to Measure Latency”**(演講) | 為什麼平均值在騙你、為什麼要看 P99/P99.9、什麼是 coordinated omission。**看這一個最回本。** |
| **DDIA《Designing Data-Intensive Applications》Ch.1** | 延遲 / 百分位 / 尾延遲的教材級講法;「最慢的請求往往是最有價值的客戶」 |
| **Google SRE Book**(免費 sre.google/books) | SLI / SLO / SLA / error budget——把數字變成業務承諾 |
| **Brendan Gregg《Systems Performance》+ USE method** | 資源層性能聖經;本 roadmap 的 [`01-methodology/02-use-method`](./01-methodology/02-use-method.md) 就源於它 |

> 一句話:人們是在「**會痛的公司 × 這套正典 × 自己的 oncall 復盤**」三者交叉處學會的。你用文檔把第二項(正典)補得比多數人都齊,缺的是第一、三項——本 roadmap 的 lab 就是用來人造第三項的。

## 3. 收口地圖 —— 整門學科只有 6 條核心原語

覺得「散、缺」,是因為它在 repo 裡攤成了上百個 `.md`。但**骨架只有 6 樣東西**,其他全是掛在上面的工具 / 語言細節。記住這 6 條,散文檔立刻變成一張網:

> **分組**:① + ② 是「**測什麼**」 · ③ + ④ 是「**怎麼系統地看**」 · ⑤ 是「**為什麼會爆**」 · ⑥ 是「**爆到多少算違約**」。

### ① 延遲 = 百分位(P50 / P99 / P99.9)

- **心智模型**:把一段時間所有請求耗時從小到大排,取第 99% 那個值。「P99=200ms」= 99% 的請求比 200ms 快,最慢的 1% 比它慢。
- **為什麼**:平均值會被掩蓋。avg=50ms 可能藏著 P99=800ms——高 QPS 下那「1%」是巨量的人,而且常是 GC、鎖、慢 SQL 等**尾部問題**。
- **最常見的坑**:把多台機器的 P99 求平均、或把 A、B 服務的 P99 相加。**百分位不可加**;要把原始樣本 / histogram bucket 匯總後重算(Prometheus 用 `histogram_quantile()` 的原因)。
- **深礦** → [`03-observability/03-metrics-theory`](./03-observability/03-metrics-theory.md)

### ② 吞吐 = 工作單位 / 時間(QPS / TPS / RPM)

- **心智模型**:每秒/每分只是換算(`QPS×60=QPM`);真正的差別在**數的是什麼工作單位**——Query(查詢)/ Request(請求)/ Transaction(事務),以及你站在哪一層數。一個用戶「下單」可能 = 1 TPS = 4 RPS = 24 QPS。
- **最常見的坑**:TPS 有兩種義(DB 的 ACID commit vs 壓測自定義事務),不講邊界就沒意義;LLM 圈的 TPM 是 **Tokens** Per Minute,不是 Transactions。
- **深礦** → [`03x-load-gen-quickstart`](./03x-load-gen-quickstart/) · [`07-load-testing`](./07-load-testing/)

### ③ RED —— 對「流量」的三個體溫計

- **Rate(吞吐)· Errors(錯誤率)· Duration(延遲)**。任何一個對外服務,先看這三個就知道它健不健康。
- **心智模型**:RED 是「從用戶視角看這個服務」。延遲變慢?錯誤變多?量變了?三問定位一半。
- **深礦** → [`01-methodology/03-red-golden-signals`](./01-methodology/03-red-golden-signals.md)

### ④ USE —— 對「資源」的三個體溫計

- 每個資源(CPU / 記憶體 / 磁碟 / 網卡 / 連接池)看三樣:**Utilization(利用率)· Saturation(飽和度=排隊)· Errors**。
- **心智模型**:RED 說「服務病了」,USE 說「哪個器官病了」。**飽和度往往領先於利用率**——隊列開始堆,比 CPU 衝到 100% 更早預警。
- **最常見的坑**:只盯利用率。利用率 80% 可能已經在排隊爆炸的邊緣(見 ⑤)。
- **深礦** → [`01-methodology/02-use-method`](./01-methodology/02-use-method.md)

### ⑤ Little 定律 + 飽和曲線 —— 為什麼 P99 會「拐彎」

- **一條方程**:`L = λ × W`(在途數 = 到達率 × 停留時間)。吞吐 × 延遲 = 併發。例:QPS 2000、延遲 50ms → 系統內同時約 100 個在途,這是你定線程 / 連接池大小的起點。
- **心智模型(最重要)**:利用率 ρ 越逼近 100%,延遲不是線性上升而是**曲棍球桿式暴漲**。`FIRST-LOOP` 第一幕讓你親眼看它:ρ 從 0.9→0.99,延遲 100ms→1000ms。
- **最常見的坑**:把目標利用率定到 90%+「省成本」,結果落在曲線拐點上,一點抖動就雪崩。
- **深礦** → [`01-methodology/04-performance-laws`](./01-methodology/04-performance-laws.md) · [`../concurrency-capacity/01-littles-law`](../concurrency-capacity/01-littles-law/)

### ⑥ SLI / SLO + error budget —— 把數字變成業務承諾

- **SLI** 是你測的指標(如 P99 延遲、成功率),**SLO** 是給它定的目標(「P99 < 200ms、可用 99.9%」),**SLA** 是違約要賠錢的對外合約。
- **心智模型**:`error budget = 1 − SLO`。99.9% 可用 = 每月可以壞 ~43 分鐘。這份預算花得起,就能拿去換發版速度;花超了,就凍結上線專心穩定。**它把「要多穩」從拍腦袋變成可量化的取捨。**
- **深礦** → [`13-sre/01-sli-slo-sla`](./13-sre/01-sli-slo-sla.md) · 容量規劃 [`13-sre/02-capacity-planning`](./13-sre/02-capacity-planning.md)

> 規律:任何性能 / 容量 / 可靠性問題,都落在這六格裡。下次覺得「我是不是漏了什麼」,對著這 6 條過一遍就知道自己站哪。

## 4. 四個 track 怎麼分工

這門學科橫跨你 repo 的 4 個 track。別一次全讀,按需要去:

| Track | 它在地圖的哪塊 | 何時去 |
|---|---|---|
| **`performance-tuning-roadmap/`**(本 track) | 全部 6 條 + 工具 + 排查閉環 | 想系統地「會排查」——主線 |
| [**`../concurrency-capacity/`**](../concurrency-capacity/) | 重壓 ⑤(Little + 飽和)→ 定容 | 想「事前算出該配多大」——這個服務開幾個線程 / 池多大 |
| [**`../observability/`**](../observability/) | 深化 ①②③④ 的「怎麼採集 / 存 / 查」 | 想把指標 / 日誌 / Trace 真正搭起來(OTel 主軸) |
| [**`../fastapi-ops/`**](../fastapi-ops/) | 把 6 條落到一個 Python / FastAPI 服務上 | 你主力是 Python 服務,要端到端可觀測 |

> 三者的關係:`performance-tuning-roadmap` 是**反應式**(出事怎麼查)、`concurrency-capacity` 是**事前**(怎麼定容)、`observability` / `fastapi-ops` 是**地基**(怎麼看得見)。

## 5. 怎麼用本 roadmap

這頁是**門面**,回答「這整門學科是什麼」。要實際走這條 roadmap,還有幾份既有導航檔(各司其職,不重複):

- [`LEARNING-GUIDE.md`](./LEARNING-GUIDE.md) —— **怎麼學**這條路線(先閉環、控制認知負擔、每階段留產物)。
- [`TRACKS.md`](./TRACKS.md) —— 按目標(資深後端 / SRE / Staff)選路線。
- [`SENIOR-RUBRIC.md`](./SENIOR-RUBRIC.md) —— 自檢回答是否到資深水平。
- [`INTERVIEW-MATRIX.md`](./INTERVIEW-MATRIX.md) —— 面試題對應章節。

**但別從讀開始。** 你已經有比多數工程師都多的文檔,卻還是覺得缺——說明瓶頸從不是缺文檔,是這些從沒變成**親手做過一次**。所以:

1. 先做 [`SELF-DIAGNOSTIC.md`](./SELF-DIAGNOSTIC.md),把焦慮變成座標。
2. 再跑 [`FIRST-LOOP.md`](./FIRST-LOOP.md),親手畫出第一條 P99 曲線。
3. 然後才按 `LEARNING-GUIDE` / `TRACKS` 系統推進。
