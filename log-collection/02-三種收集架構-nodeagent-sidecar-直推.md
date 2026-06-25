# 02 · 三種收集架構:Node Agent / Sidecar / 直推

> 接 `01` 的收口:收集架構的本質問題只有一個 —— **「讀 node 檔案(或攔截日誌)的那個進程,放在哪、放幾個?」** 這章把三個可能的答案攤開,連同它們的成本與取捨。
> 一句話先給結論:**預設 Node Agent(DaemonSet);只有特定理由才上 Sidecar;直推基本別碰。** 你前公司「全走 sidecar」對不對,讀完這章你會自己有答案(壓軸 `06` 再系統化)。

---

## 一、一張圖:三種放法並排

```
                    ┌─────────────── 一台 node ───────────────┐
                    │  Pod A        Pod B        Pod C         │
 ① Node Agent       │  [app]        [app]        [app]         │
    (DaemonSet)      │    │stdout      │stdout      │stdout      │
    每 node 一個 ───►│    ▼            ▼            ▼            │
                    │   /var/log/containers/*.log(這台全部)    │
                    │              ▲                            │
                    │        [agent ×1] ──────────────────────────► 後端
                    └──────────────────────────────────────────┘

 ② Sidecar          Pod: [ app ]──寫檔/stdout──►[ agent ]──► 後端
    每 pod 一個                     共享 emptyDir          (每個 pod 自帶一份)

 ③ 直推             Pod: [ app + SDK ]──────────────────────► 後端
                              (app 自己把日誌推出去,不落 node 檔案)
```

三種的差別,幾乎都能用一句話解釋:**這個收集進程「離 node 檔案有多近、要付幾份成本」。** Node Agent 一台一份、就近讀檔;Sidecar 一個 pod 一份;直推乾脆不落檔、由 app 扛。

---

## 二、Node Agent(DaemonSet）—— 預設正解

**怎麼運作**:用 DaemonSet 在**每台 node** 上跑**一個** agent(Fluent Bit / Vector …),透過 `hostPath` 把 node 的 `/var/log/containers` 掛進 agent 容器,agent **tail 這台所有容器的日誌檔**,往後端送。

**自動發現(關鍵優勢)**:你不用為新服務做任何配置。新 pod 一起來,它的日誌檔就出現在 `/var/log/containers/`,agent 的 tail input 用萬用字元 `*.log` **自動捡到**。下線同理自動消失。**整個集群一份配置,管所有現在和未來的服務。**

> 🔬 **agent 怎麼把「pod / namespace / label」貼到每行日誌上?** node 檔案的**檔名**本身就編碼了身份:`<pod>_<namespace>_<container>-<id>.log`。agent 先從檔名解析出 pod/ns/container,**再去 watch kube-apiserver** 拿這個 pod 的 labels / annotations,把它們 enrich 進每一條日誌。Fluent Bit 的 **`kubernetes` filter** 幹的就是這件事。這就是為什麼你能在後端「按 `namespace=payment` 或 `app=order`」搜日誌 —— 那些欄位不是你 app 打的,是 agent 在 node 上補的。(這也順帶說明:agent 需要 RBAC 讀 pod 物件。)

**資源模型**:`agent 數 = node 數`,**和 pod 數無關**。一個 Fluent Bit ~ 幾十 MB。100 個 pod 擠在 10 台 node 上,也只有 **10 個 agent**。

**為什麼是預設**:成本最低(按 node 攤)、運維最省(一個 DaemonSet 管全集群、升級只動一處)、**app 零改造**(只要寫 stdout)、自動發現。k8s 官方與雲廠(EKS Container Insights、GKE、AKS)的預設都是這個。

---

## 三、Sidecar —— 每個 pod 一個收集器

把收集器作為一個**額外容器**塞進**每個** pod。有兩種形態,別混:

**(a) Streaming sidecar(轉 stdout 型)**
app 寫**檔案**(不寫 stdout),sidecar `tail` 那個檔,把內容**re-emit 到 sidecar 自己的 stdout** —— 於是 node agent 又能收到了。本質是「**把檔案翻譯回 stdout**」,好讓 ① 那套還能用。app 和 sidecar 透過**共享 `emptyDir`** 看到同一個檔(app 寫 `/logs/app.log`,sidecar 讀同一個)。

**(b) Sidecar with agent(自帶收集器型)**
sidecar 裡直接跑一個 Fluent Bit,讀共享 volume 的檔案,**自己推後端**,繞過 node agent。

**成本**:`agent 數 = pod 數`。一個 sidecar 幾十 MB,**× pod 數**。100 個 pod = 100 份收集器記憶體 + 100 份 buffer + 100 份配置。這是和 DaemonSet 的根本差距。

**何時 Sidecar 才是對的**(這幾條請記牢,`06` 審計會逐條用):
- **app 寫檔案、改不動 stdout**(legacy、framework 硬寫檔)→ 用 (a) 轉回 stdout。
- **多租戶強隔離**:每個團隊 / 租戶用**自己的憑證、自己的後端、自己的管線**,不能共用一個 node agent。
- **per-app 差異化管線**:某個吵的服務要單獨限流 / 特殊解析 / 特殊路由,不想污染全局配置。
- **安全邊界**:不信任 node 層共享 agent(極少數高隔離場景)。

> 🔬 一句話判準:**Sidecar 是用「N 份成本」換「per-pod 的隔離與定制」。** 當你**沒有** per-pod 的隔離 / 定制需求(絕大多數寫 stdout 的普通服務就是這樣),這 N 份成本就是純浪費 —— 這正是 `06` 要審計你前公司的點。

---

## 四、直推(app 用 SDK 直接推後端)

app 內嵌一個 appender / exporter,把日誌**直接**推到 ES / Loki / OTLP,**不落 node 檔案**。

**為什麼一般別**:
- **耦合 app 與後端**:換後端(ES → Loki)要**改代碼、重發布所有服務**。收集器的全部意義就是解耦這層。
- **app 要自己扛 buffer / 重試 / 背壓**:後端抖動、慢、掛,這些**本該是收集器的專業**,現在全進了你的請求路徑 —— 後端一抖,app 延遲飆、甚至 OOM(回扣 `logging/06` 異步 appender 的丟失取捨)。
- **失去 node 元數據自動 enrich**(③ 沒有 ① 的 `kubernetes` filter)。

**何時勉強可以**:
- **OTel SDK → Collector**:app 用 OTLP 把日誌發到**集群內的 OTel Collector**(不是直發後端)。這其實是「推到 collector」,collector 再統一出口 —— 算 ③ 的形,①/gateway 的神,可接受(`04` 細講)。
- **Serverless / FaaS**:沒有你掌控的 node 可掛 DaemonSet(EKS Fargate、Lambda),只能靠平台注入的 router 或直推(`05` 細講)。

---

## 五、決策表

| 維度 | ① Node Agent(DaemonSet) | ② Sidecar | ③ 直推 |
|---|---|---|---|
| 收集進程數 | **= node 數**(少) | = pod 數(多) | 0(app 自己扛) |
| 記憶體成本 | 最低 | **最高**(× pod) | 進 app 進程 |
| app 改造 | **零**(寫 stdout 即可) | 低~中(掛 volume / sidecar) | 高(嵌 SDK) |
| 運維 | **最省**(一份 DaemonSet) | 重(每 workload 帶、升級動全部) | 重(改後端=改代碼) |
| 隔離 / per-app 定制 | 弱(全局一套) | **強**(每 pod 獨立) | 中 |
| 自動發現新服務 | **是** | 否(要改 workload) | 否 |
| 換後端成本 | 低(改 DaemonSet) | 中 | **高(重發布)** |
| 適合 | **絕大多數寫 stdout 的服務** | 寫檔 / 強隔離 / per-app 管線 | SDK→Collector、Serverless |

---

## 六、一句話決策

> **預設 Node Agent(DaemonSet)。** 只有出現「**app 寫檔改不動 / 多租戶強隔離 / per-app 差異化管線**」時,才為**那些 pod**上 Sidecar(而不是全員)。**直推基本別**,除非是 SDK→集群內 Collector,或 Serverless 沒 node 可挂。

**反模式(高頻、也可能就是你前公司)**:給一堆**寫 stdout、彼此無隔離需求**的普通服務**全員挂 sidecar 收集器**。結果是付了 `pod 數 × 收集器` 的記憶體與運維成本,卻沒換到任何 sidecar 才有的隔離 / 定制價值 —— 等於用最貴的姿勢做最普通的事。`06` 會教你怎麼審計與量化這筆浪費,以及怎麼安全遷回 DaemonSet。

---

## 交叉引用

- **node 檔案、CRI 格式、為什麼日誌先落檔** → `01`
- **不同日誌源(系統 / 控制平面 / 審計 / events)各自怎麼收** → `03`
- **agent + gateway 兩層管線、buffer / 背壓 / 丟失** → `04`
- **Fargate 沒 node → sidecar / router 例外在 EKS 的真實觸發** → `05`
- **反思「全 sidecar」對不對、怎麼算帳怎麼遷** → `06`
- **sidecar 模式的代價(service mesh 從 sidecar 走向 ambient 也是同一筆帳)** → `cloud-native-landscape/04`

---

## 本章小結

- 收集架構 = 「讀檔 / 攔截的進程放哪、幾個」:**Node Agent(每 node 一個)/ Sidecar(每 pod 一個)/ 直推(app 自己)**。
- **Node Agent 是預設**:成本按 node 攤、自動發現、app 零改造、一份配置管全集群;🔬 靠 `kubernetes` filter 從檔名 + apiserver 補 pod/ns/label 元數據。
- **Sidecar 是用 N 份成本換 per-pod 隔離 / 定制**:只在「寫檔改不動 / 多租戶強隔離 / per-app 管線」時對;否則純浪費。
- **直推基本別**(耦合後端、app 扛 buffer / 背壓),除非 SDK→Collector 或 Serverless。
- 反模式:給寫 stdout 的普通服務**全員 sidecar** —— `06` 審計與遷移的主角。

---

## 章末問答(複習自檢,答案要點都在前面正文)

1. 用一句話說清三種收集架構的本質差別(提示:離 node 檔案多近、付幾份成本)。
2. Node Agent 為什麼能「自動發現新服務、零配置」?那行日誌上的 `namespace=payment` 欄位是誰、在哪一步補上去的?
3. Streaming sidecar 和 sidecar-with-agent 差在哪?streaming sidecar 為什麼還需要 node agent 配合?
4. 列出三條「Sidecar 才是對的」的理由。如果一個服務寫 stdout、又沒有隔離需求,給它挂 sidecar 浪費了什麼、換到了什麼?
5. 直推為什麼一般不推薦?哪兩種情況算可接受的例外?「OTel SDK → Collector」為什麼不算真正的直推?
6. **綜合題**:你接手一個集群,發現 200 個服務全挂了 Fluent Bit sidecar,且都只寫 stdout。先別急著改 —— 你會問哪幾個問題來判斷該不該遷成 DaemonSet?(把你的問題列出來,`06` 會給標準 checklist 對答案。)
