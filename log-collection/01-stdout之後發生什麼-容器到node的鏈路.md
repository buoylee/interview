# 01 · stdout 之後發生什麼:從容器到 node 的鏈路

> 治的認知缺口:大家都會背「容器裡寫 stdout,交給平台收」,但**「交給平台」這四個字裡到底發生了什麼**,很少人講得清。
> 這章把 **app → 容器運行時 → node 檔案** 這條鏈打通。為什麼先講這個?因為 `02` 之後「DaemonSet 還是 sidecar」的**所有取捨,都建立在一個事實上**:那行日誌此刻就是 **node 本地磁碟上的一個檔案**。不先把這弄清,後面的架構選擇全是背口訣。

---

## 一、一張圖:從一行 `log.info` 到 node 上的檔案

```
你的程式   log.info({"level":"info","msg":"order created"})
   │  本質是 write() 到 fd 1(stdout)/ fd 2(stderr)
   ▼
stdout / stderr  ← 容器進程的兩條標準輸出流
   │  容器運行時(containerd)接住這兩條流,逐行寫到 node 磁碟
   ▼
node 磁碟:/var/log/pods/<namespace>_<pod>_<uid>/<container>/<restart-count>.log
   ▲  symlink 指過去
/var/log/containers/<pod>_<namespace>_<container>-<containerid>.log
                                    ▲
                          ★ 收集器(下一章)盯的就是這裡
```

**一個必須先釘死的認知**:你的日誌「離開應用」那一刻,**不是**直接進了 Elasticsearch / CloudWatch / Loki ——它**先落地成 node 上的一個普通檔案**。中間一定有這一跳。整個收集問題,本質就是「**誰、在哪、用什麼姿勢去讀這個檔案,再往後送**」。

**誰寫的這個檔案**:容器運行時(EKS 與多數現代集群是 **containerd**)。它把容器進程 fd1/fd2 的位元組流接住,按行寫到上面那個路徑(回扣 `cloud-native/03a`:kubelet → CRI → containerd 這條鏈)。

---

## 二、node 上的那行,長得跟你 print 的不一樣:CRI 日誌格式 🔬

你以為 node 檔案裡躺的就是你 print 的那行 JSON?不是。containerd 按 **CRI 規範**給每一行套了一層「信封」:

```
2026-06-25T08:01:09.669794202Z  stdout  F  {"level":"info","msg":"order created","order_id":123}
└────────── RFC3339Nano 時間戳 ──────────┘ └─流─┘ │  └──────────── 你真正 print 的 payload ────────────┘
                                                 tag:F=完整行 / P=被截斷的部分行
```

每行四個欄位,空格分隔:

| 欄位 | 值 | 意義 |
|---|---|---|
| 時間戳 | `2026-…669…Z` | 運行時收到這行的時刻(RFC3339Nano,奈秒) |
| stream | `stdout` / `stderr` | 來自哪條流 —— 收集器能據此把錯誤流分開 |
| tag | `F` / `P` | `F`=完整一行;`P`=這行太長被切開的前段(見第三節) |
| payload | `{...}` | **你真正寫的內容** |

**為什麼這對你重要 ——「剝信封」是收集器的第一步**:你配 Fluent Bit / Vector / OTel Collector 時,**第一個 parser 永遠是 `cri`**。它先把這四段拆開、拿到 payload,**再**把 payload 當 JSON 解。漏了這步,你的 `level`/`msg`/`order_id` 全會混在一坨被當成純文字的字串裡,後端**搜不了、聚合不了**。很多人「日誌收上去卻變成一團」的事故,根因就是 parser 沒配對。

> 🔬 **為什麼有 `cri` 和 `docker` 兩種 parser?** Docker 舊的 `json-file` driver 把每行寫成一個 JSON 物件 `{"log":"…","stream":"stdout","time":"…"}`,欄位名和分隔方式都和 CRI 純文字格式不同。k8s **1.24 移除 dockershim** 後,EKS 與多數集群走 **containerd → CRI 格式**(回扣 `cloud-native/03a`:「棄的是 Docker 運行時,不是 OCI 鏡像」)。所以選 parser 要看運行時:**現在預設選 `cri`,不是 `docker`。** 選錯,日誌一樣解不出來。

---

## 三、`P` 這個 tag 是個伏筆:長行會被切斷 🔬

運行時從容器讀輸出時有個**緩衝上限**(containerd 預設 **16 KB**)。**超過這個長度的一行,會被切成多條**:前面幾段標 `P`(partial),最後一段標 `F`(full)。

後果很實際:**一條很長的 JSON、或一個多行的 Java stacktrace,到了 node 檔案裡可能已經是好幾條記錄了。**

```
2026-…Z stderr P java.lang.NullPointerException: ...（第 1 段,被切）
2026-…Z stderr P     at com.foo.Bar.baz(Bar.java:42) ...（第 2 段）
2026-…Z stderr F     at com.foo.App.main(App.java:13)（最後一段）
```

這就是 `04` 章「**多行堆疊合併(multiline)**」那個經典坑的**物理根源** —— 一個異常在你眼裡是一件事,在 node 檔案裡是 N 行、甚至被 partial 切得更碎。收集器必須把它們**重新拼回一條**,否則後端裡你看到的是「半個堆疊」。**記住這裡,到 `04` 串起來。**

---

## 四、誰來輪轉:是 kubelet,不是你的 app 🔬

node 磁碟有限,日誌不能無限漲,總得輪轉(rotate)。關鍵:**輪轉是 kubelet 做的 —— 不是 logrotate、更不是你的 app。**

kubelet 兩個參數(可在 kubelet config 調):

| 參數 | 預設 | 意義 |
|---|---|---|
| `containerLogMaxSize` | `10Mi` | 單個日誌檔超過就輪轉 |
| `containerLogMaxFiles` | `5` | 每容器最多保留幾個輪轉檔 |

**推論(回應 `logging/06` 那條「容器裡別自己 rotation」)**:app 在容器裡**千萬別自己做 rotation**。兩個輪轉器(你的 app + kubelet)盯同一批檔案,會互相打架 —— 檔案被一方改名 / 刪除,另一方的檔案 handle 失效,結果是**日誌錯亂或直接丟**。容器裡 app 的職責只有一個:**往 stdout 寫**。輪轉是平台的事。

> 🔬 **架構師警覺:輪轉可能搶在收集器前面把日誌刪掉。** 預設 `10Mi × 5 = 50Mi/容器`。一個**高日誌量**的服務,如果收集器讀得慢(背壓、後端抖動),老檔案可能在**還沒被讀走之前**就被 kubelet 輪轉刪除 → **直接丟日誌,而且無聲無息**。這是真實的事故來源 —— `04` 章講背壓 / buffer 時會回到這條:收集速度跟不上產生速度,丟的就在這裡。

---

## 五、`kubectl logs` 讀的是什麼,以及它為什麼**靠不住** 🔬

`kubectl logs` **不連你的 app**。它的路徑是:

```
kubectl logs ─► kube-apiserver ─► 目標 node 的 kubelet ─► kubelet 讀上面那個 CRI 檔案 ─► 回吐
```

所以它讀的,就是第一節那個 node 本地檔案。正因如此,它有**三個「靠不住」**:

1. **pod 沒了,日誌就沒了**:那個檔案隨容器 / pod 刪除被清掉;node 被驅逐 / 換掉(EKS 上 node 是隨時會被回收的)一起沒。**OOMKilled、CrashLoop 之後你最想看的那段,常常已經沒了。**
2. **只看得到當前這個 pod / node**:多副本服務要一個個 pod `logs` 翻;跨 node 無法聚合搜尋。
3. **輪轉窗口外的看不到**:超過 `50Mi` 的老日誌已被 kubelet 輪轉刪掉,`kubectl logs` 也撈不回。

→ **這就是整個 track 存在的理由**:`kubectl logs` 是一個**臨時觀察窗口,不是日誌系統**。你**必須**有個東西,**在 node 檔案被刪掉之前,把它搬到集群外的持久後端**(ES / Loki / CloudWatch …)。

---

## 六、把鏈路反過來看:收集器站在哪

一句話收口整章:

```
app ──► (containerd) ──► node CRI 檔案 ──┤ 收集器從這裡往後接管 ├──► 後端
        日誌離開 app          就是一個檔案           02 章的主題         observability/
```

所以**收集架構的本質問題只有一個**:

> **「讀 node 檔案的那個進程」要放在哪、放幾個?**
> - 每個 **node** 放一個,讀這台所有容器的檔案 → **DaemonSet(node agent)**
> - 每個 **pod** 旁邊放一個 → **sidecar**
> - 乾脆讓 app **別落地檔案、直接往後端推** → **直推**

這三個答案,就是 `02` 章的三種架構。你會發現:**選哪種,幾乎都能用「它離 node 檔案有多近、要付多少份成本」來解釋。**

---

## 交叉引用

- **容器 = 被隔離的進程、kubelet → CRI → containerd → runc 鏈** → `cloud-native/03a`
- **寫 stdout、別在 app 內 rotation 的應用側紀律** → `logging/06`
- **多行堆疊合併(multiline)、背壓 / buffer / 丟失** → 本 track `04`
- **三種收集架構的取捨** → 本 track `02`
- **收集器把檔案搬到哪(後端選型 / 信號階段)** → `observability/`

---

## 本章小結

- 日誌離開 app = 變成 **node 上一個檔案**(`/var/log/pods/…`,`/var/log/containers/…` 是 symlink);寫它的是 **containerd**。不是直接進後端,中間一定先落地。
- node 檔案是 **CRI 格式**(時間戳 + stream + `F`/`P` tag + payload),收集器**第一步要剝信封**(`cri` parser);Docker 舊 `json-file` 格式不同,選錯 parser 日誌解不出。
- 長行被切成 `P`/`F` 多段 → **多行堆疊坑的物理根源**(`04`)。
- 輪轉是 **kubelet** 做(`10Mi × 5`),**app 別自己輪轉**;高量服務可能被輪轉**搶先刪 → 無聲丟日誌**。
- `kubectl logs` 讀的就是這檔案,**pod 一沒就沒** → 必須在被刪前搬到集群外 → **這是整個 track 的理由**。
- 收集架構的本質:**「讀 node 檔案的進程」放哪、幾個** → DaemonSet / sidecar / 直推(`02`)。

---

## 章末問答(複習自檢,答案要點都在前面正文)

1. 你 `print` 一行 JSON 到 stdout,到它躺在 node 磁碟上,中間經手了誰?檔案在哪個路徑?為什麼說它「不是直接進後端」?
2. node 上那行日誌和你 print 的原文差在哪?說出 CRI 格式的四個欄位。收集器為什麼**必須**先配一個 `cri` parser?配成 `docker` 會怎樣?
3. 一個 200 行、單行又超長的 Java stacktrace,到了 node 檔案可能變成什麼樣(用 `P`/`F` 解釋)?這埋了後面哪一章的什麼坑?
4. 容器裡日誌的輪轉**誰**負責?為什麼 app 自己 rotation 是錯的?在預設配置下,一個高日誌量的容器**可能怎麼無聲地丟日誌**?
5. `kubectl logs` 的資料**從哪來**?列出它三個「靠不住」,並由此論證:為什麼一個集群**必須**有一套獨立於 `kubectl logs` 的收集系統?
6. **綜合題**:用一句話說清「容器化後收集架構的本質問題」,並把它展開成三種可能的架構放法(下一章的引子)。
