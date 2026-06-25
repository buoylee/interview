# 08 · 運維與零停機:訊號、reload 平滑、熱升級二進制 🔬⭐

> 一句話:Nginx 跑在生產上,你遲早要做三件事——**改設定生效**、**升級 Nginx 版本**、**切日誌**。這三件事要是做成「`kill` 掉再重起」,在途請求就全斷了、客戶端看到一片 502。Nginx 的設計讓這三件事都能**零停機完成**,靠的是一套**訊號 + master-worker 交接**的機制。這一章把「黑盒裡發生什麼」拆開:`reload` 為什麼不丟連線、二進制怎麼不停機換掉、出錯怎麼回滾。

Nginx 不是「改完設定點個按鈕重啟」那種服務。它是 master-worker 架構(↪ `gateway/01-reverse-proxy-engine.md` 講過引擎為什麼這樣設計),而 master 進程的核心職責之一,就是**接收 Unix 訊號、優雅地調度 worker 的生死**。你日常敲的 `nginx -s reload`、`nginx -s quit`,底層都是「給 master 發一個訊號」的語法糖。

本章把四件事講死:**訊號表**(每個訊號讓 master 做什麼)、**`reload` 為什麼平滑**(核心內幕:listen socket 由 master 持有 + 舊 worker 處理完在途才退)、**熱升級二進制**(USR2→WINCH→QUIT 交接 + 回滾)、**優雅退出 / 日誌切割 / 灰度發布**的運維手法。

> 引擎為什麼快(master-worker、epoll、worker 怎麼收連線)不在這裡——那是 `gateway/01` 的事。本章只教「**怎麼用訊號駕馭這台引擎的生命週期**」。

---

## 1. 🔬 訊號表:給 master 發訊號,就是在指揮它的生命週期

Nginx 的運維操作,本質上都是**向 master 進程發一個 Unix 訊號**。`nginx -s <cmd>` 這個命令,做的事就是「找到 master 的 pid、給它發對應訊號」——所以理解了訊號表,你就理解了 Nginx 的全部運維動作,連 `nginx -s` 都不可用(比如容器裡精簡鏡像)時也能直接 `kill -SIGxxx <master_pid>` 救場。

**先把完整訊號表列死(這是本章的字典,後面每節都在用它)**:

| 訊號 | `nginx -s` 等價 | 發給誰 | master 收到後做什麼 | 用在什麼場景 |
|---|---|---|---|---|
| **`HUP`** | `reload` | master | **重讀並校驗設定** → 用新設定 fork 新 worker → 對舊 worker 發優雅停止訊號 | 改了 `nginx.conf` 要生效 |
| **`USR2`** | (無直接等價) | master | **熱升級二進制**:fork 出**新 master + 新 worker**,新舊同時跑、共用 listen socket | 不停機換 Nginx 可執行檔(升版本/打補丁) |
| **`WINCH`** | (無直接等價) | master | **優雅停掉所有 worker、保留 master**(master 還在,可隨時再拉起 worker) | 熱升級時「先收舊 worker、保留舊 master 以便回滾」 |
| **`QUIT`** | `quit` | master 或 worker | **優雅退出**:停止接新連線,把**在途請求處理完才退** | 正常下線一個進程(收舊 master、或整個優雅關停) |
| **`TERM`** / `INT` | `stop` | master | **快速退出**:立刻關所有連線、直接終止(**不等在途請求**) | 緊急停、或不在乎在途請求時 |
| **`USR1`** | `reopen` | master | **重新開啟所有日誌檔**(關掉舊 fd、按設定路徑重開) | 日誌切割(配合 `mv` + logrotate) |

> 兩個容易記混的對子:
> - **`QUIT`(優雅)vs `TERM`(快退)**:`QUIT` 會「處理完在途才退」,`TERM` 是「立刻砍」。生產下線**永遠用 `QUIT`**,`TERM` 只在「卡死了要強殺」時用。
> - **`WINCH`(只收 worker、留 master)vs `QUIT`(連 master 一起優雅退)**:`WINCH` 是熱升級流程裡的「半步」——它讓你**把 worker 收掉但 master 還活著**,這樣萬一新版本有問題,還能用這個舊 master 把 worker 拉回來。這是回滾能力的關鍵,下面第 3 節會用到。

**一個常被忽略的事實**:這些訊號絕大多數是發給 **master** 的,由 master 去**優雅地**協調 worker。你幾乎不需要直接對 worker 發訊號——master 才是生命週期的指揮中心。worker 自己也會收 `QUIT`(由 master 轉發),那是「優雅收工」的執行端。

---

## 2. 🔬⭐ `reload` 為什麼平滑:改設定不丟一個連線

這是本章、也是面試最核心的一題:**「`nginx -s reload` 為什麼不會中斷在途請求、也不會漏接新請求?」** 很多人只會答「它是熱重載」,但答不出**機制**。把下面這條鏈講清楚,就贏了。

### 2.1 reload 的完整內幕流程

你敲 `nginx -s reload`,等於給 master 發 `HUP`。master 收到後,**按順序**做這幾步:

```
你: nginx -s reload   (= kill -HUP <master_pid>)
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ master 進程(整個過程 listen socket 一直由它持有、不關)         │
│                                                              │
│  ① 重讀 nginx.conf,並「校驗」新設定                            │
│     └─ 設定有錯(語法/找不到憑證/埠衝突)？                       │
│        → 直接放棄,印錯誤到 error_log,                          │
│          舊 worker 原封不動繼續服務 → reload 失敗但「服務不受影響」│
│                                                              │
│  ② 設定 OK → 用「新設定」fork 出一批「新 worker」               │
│     └─ 新 worker 繼承 master 手上那個 listen socket 的 fd       │
│        → 新 worker 立刻能 accept 新連線(用新設定處理)           │
│                                                              │
│  ③ 對「舊 worker」發優雅停止訊號(內部等同 QUIT)                │
│     └─ 舊 worker 收到後:                                       │
│        • 立刻「停止 accept 新連線」(新連線都交給新 worker 了)     │
│        • 但「已經在處理的在途請求」continue 處理到完             │
│        • 手上的連線全部處理完 / 關閉後,舊 worker 才自己退出       │
└─────────────────────────────────────────────────────────────┘
```

時間軸上會出現一個短暫的「**新舊 worker 並存**」窗口:

```
時間 ──────────────────────────────────────────────►
舊 worker:  [服務中]──收 reload──[只處理在途、不收新]──[在途清空]──退出
新 worker:               ┌─fork─[開始 accept 新連線、用新設定]──────────► 持續服務
listen socket: ━━━━━━━━━━ 始終由 master 持有、從未關閉 ━━━━━━━━━━━━━►
```

### 2.2 為什麼這樣就「一個連線都不丟」——兩個關鍵

整套平滑的祕密就藏在兩件事上,面試把這兩句答出來就到位了:

**關鍵一:listen socket 由 master 持有、reload 全程不關。**

監聽 socket(`listen 80` 那個)是 **master 進程**在啟動時就 `bind` + `listen` 建好的,然後**透過 fork 把這個 fd 共享給每個 worker**。reload 時 master **從頭到尾沒有關掉這個 listen socket**——它只是把這個 fd**再分享給新 fork 的 worker**。

這意味著:在「舊 worker 還沒退、新 worker 剛起來」的那個窗口裡,**監聽埠一刻都沒有空檔**。新來的連線總有 worker 在 `accept`(先是舊 worker、交接後是新 worker),內核的 accept 佇列也始終掛在同一個沒被關閉的 socket 上。**沒有「埠短暫關閉→新請求被內核拒掉(connection refused)」這種事。** 這就是為什麼 reload **不會漏接新請求**。

> 對比一下「`stop` 再 `start`」:那會先 `close` 掉 listen socket(埠釋放)、再重新 `bind`,中間有個窗口埠是沒人聽的,這段時間進來的連線會被內核直接拒絕。reload 沒有這個窗口,差別就在「listen socket 從不關閉」。

**關鍵二:舊 worker 不是被砍死,而是「處理完在途請求才退」(graceful)。**

舊 worker 收到停止訊號後,**不會立刻丟掉手上正在處理的請求**。它做的是:

- 把自己的 listen socket 從事件迴圈裡摘掉 → **不再 `accept` 新連線**(新連線交給新 worker)。
- 但**已經建立的連線、正在跑的請求繼續處理到完成**(回應發完、keepalive 連線等到空閒或超時)。
- 等手上所有連線都處理完 / 關閉了,舊 worker 才**自己退出**。

所以正在被舊 worker 處理的那個請求,**不會因為 reload 而中途斷掉**——它會被舊 worker 善始善終地處理完。這就是為什麼 reload **不會中斷在途請求**。

> ⭐ **白板答法**(被問「reload 為什麼不丟連線」,口述這段就滿分):
> 「`nginx -s reload` 給 master 發 `HUP`。master **先校驗新設定**,OK 才用新設定 fork 新 worker,然後通知舊 worker 優雅退出。不丟連線靠兩件事:**第一,listen socket 是 master 持有的、reload 全程不關閉**,只是把 fd 再分享給新 worker,所以監聽埠一刻不空檔、新請求總有 worker 在 accept;**第二,舊 worker 不是被砍死,而是停止接新連線、把手上在途的請求處理完才退**。新舊 worker 短暫並存,新連線歸新 worker、在途請求歸舊 worker,兩邊都不斷。而且設定有錯時新 worker 起不來、舊 worker 繼續服務,所以 reload 是安全的。」

### 2.3 🔬 reload 的「安全網」:設定錯了也不會掛掉服務

這是 reload 機制送的一個大禮,也是面試加分點:

> **如果新設定有錯(語法錯、憑證路徑不存在、`listen` 埠衝突……),`HUP` 流程會在「校驗」這一步就失敗——master 根本不會 fork 新 worker,舊 worker 原封不動繼續服務。** 結果是:reload 失敗、error_log 裡有報錯,但**線上服務完全不受影響**(還在用舊設定跑)。

換句話說,`reload` 是一個**「成功才換、失敗則維持原狀」的原子操作**——它不會把你帶到一個「半新半舊、服務中斷」的壞狀態。

但**別把這個安全網當校驗**。`HUP` 觸發的校驗和你手動跑 `nginx -t` 是同一套檢查,**標準做法仍是先 `nginx -t` 確認設定無誤、再 reload**:

```bash
nginx -t            # 先校驗:configuration file ... syntax is ok / test is successful
nginx -s reload     # 確認 OK 後再 reload
```

為什麼還要 `nginx -t`(既然 reload 自己會校驗)?因為:
- `nginx -t` 讓你**在發 reload 之前**就看到錯誤,不用去翻 error_log 才發現 reload 沒成功。
- 有些「設定能通過語法校驗、但邏輯是錯的」(比如 `proxy_pass` 指向一個錯的 upstream),`nginx -t` 不一定能抓到——這類靠灰度(2.4)兜。
- 自動化 / CI 裡,`nginx -t` 的退出碼(0/非 0)是你判斷「要不要 reload」的閘門。

### 2.4 灰度 reload:先一台、觀察、再全量

reload 雖然安全,但「設定語法對、但行為改錯了」(比如不小心把 `proxy_read_timeout` 設成 1s)這種**邏輯錯誤**,校驗抓不到、reload 也會成功——錯的設定就上線了。生產上多台 Nginx 時的標準節奏是**灰度**:

1. 在**一台** Nginx 上 `nginx -t && nginx -s reload`。
2. **觀察這一台**:盯 error_log、`$status` 分布、`$upstream_response_time`(↪ ch10 的觀測指標)、業務監控,確認新設定行為符合預期。
3. 沒問題,再**逐台**滾動到其餘節點;有問題,這台改回舊設定 reload(舊設定還在版本控制裡)。

> 這正是「先一台、觀察、再全量」的滾動發布思路在「設定變更」上的落地——和應用發布的灰度是同一套哲學,只是粒度是「一份 `nginx.conf`」。

---

## 3. 🔬⭐ 熱升級二進制:不停機換掉 Nginx 可執行檔

`reload` 解決的是「**換設定**」。但如果你要**換掉 Nginx 的可執行檔本身**(升級到新版本、打安全補丁、換編譯參數加模組),光 reload 不夠——reload 只是讓現有的 master 重讀設定,**master 進程本身還是舊二進制**。換二進制需要**換掉 master 進程**,而這恰恰是最危險的:master 掛了,服務就沒了。

Nginx 用一套 **`USR2` → `WINCH` → `QUIT`** 的流程,讓你**在不中斷服務的前提下,把整個 master + worker 換成新二進制**,而且**全程可回滾**。這是 Nginx 運維裡最「黑魔法」、也是面試官最愛聽的一段。

### 3.1 前置:先把新二進制就位

```bash
# 1) 把新版本的 nginx 可執行檔覆蓋到原路徑(舊 master 已載入記憶體,覆蓋檔案不影響它正在跑)
#    通常是:make install,或包管理器升級,把新的 /usr/sbin/nginx 放好
# 2) 確認 master 的 pid(USR2 要發給它)
cat /run/nginx.pid     # 假設舊 master pid = 1000
```

> 關鍵前提:**舊 master 進程已經把舊二進制載進記憶體在跑了,你覆蓋磁碟上的可執行檔不會影響它**。新二進制只有在「fork 出新 master」時才會被載入。

### 3.2 完整交接流程(USR2 → 觀察 → WINCH → QUIT)

```
階段 0(升級前):只有舊的一套在跑
┌──────────────────────────────────────┐
│  舊 master (pid 1000, 舊二進制)         │
│    ├─ 舊 worker                        │
│    └─ 舊 worker                        │
│  pid 檔: /run/nginx.pid = 1000         │
└──────────────────────────────────────┘
   listen socket(fd)由舊 master 持有

─────────────────────────────────────────────────────────────────

階段 1: kill -USR2 1000   (給舊 master 發 USR2)
舊 master 收到 USR2:
  • 把現有 pid 檔改名:/run/nginx.pid → /run/nginx.pid.oldbin
  • fork 出「新 master」,新 master exec 新二進制,並 fork 新 worker
  • 新 master 寫新的 /run/nginx.pid = 2000
  • 關鍵:新 master + 新 worker 「繼承了同一個 listen socket 的 fd」

┌──────────────────────────────────────┐   ┌──────────────────────────────────────┐
│  舊 master (1000, 舊二進制)             │   │  新 master (2000, 新二進制)             │
│    ├─ 舊 worker                        │   │    ├─ 新 worker                        │
│    └─ 舊 worker                        │   │    └─ 新 worker                        │
│  pid 檔: nginx.pid.oldbin = 1000       │   │  pid 檔: nginx.pid = 2000              │
└──────────────────────────────────────┘   └──────────────────────────────────────┘
         │                                            │
         └──────────── 共用同一個 listen socket(fd)────┘
            新舊 worker「同時在 accept 同一個埠的連線」
            內核把新連線輪流分給任意一個 worker(新或舊都行)

─────────────────────────────────────────────────────────────────

階段 2: 觀察新版本(這段時間新舊並存、一起服務流量)
  • 看新 worker 有沒有報錯、回應是否正常、指標是否健康
  • 此刻你還握著「全部回滾能力」——舊 master 完好

─────────────────────────────────────────────────────────────────

階段 3a(新版本 OK,推進):
  kill -WINCH 1000   (給「舊」master 發 WINCH)
    → 舊 master 優雅停掉它的「舊 worker」(在途處理完才退),但「舊 master 自己保留」
    → 現在只有新 worker 在服務,舊 master 待命(萬一還要回滾)

  觀察一段時間,徹底確認沒問題後:
  kill -QUIT 1000    (給「舊」master 發 QUIT)
    → 舊 master 優雅退出,舞台只剩新的一套 → 升級完成 ✅

┌──────────────────────────────────────┐
│  新 master (2000, 新二進制)             │
│    ├─ 新 worker                        │
│    └─ 新 worker                        │
│  pid 檔: nginx.pid = 2000              │
└──────────────────────────────────────┘   升級完成,全程零停機
```

### 3.3 🔬 回滾路徑:新版本有問題怎麼「拉回舊的」

熱升級最值錢的地方是**任何一步出問題都能回滾**,因為**舊 master 一直活著**(直到你確認無誤、主動 `QUIT` 它為止)。

**情況 A:階段 2 觀察時就發現新版本有問題(還沒收舊 worker)。** 這時新舊 worker 都在跑,回滾最簡單——**反過來把「新的」收掉**:

```bash
kill -QUIT 2000     # 給「新」master 發 QUIT,新 master + 新 worker 優雅退出
                    # 舊 master + 舊 worker 原封不動繼續服務 → 回到升級前狀態
mv /run/nginx.pid.oldbin /run/nginx.pid   # 把 pid 檔改回去(視情況)
```

**情況 B:階段 3a 已經 `WINCH` 收了舊 worker,才發現新版本有問題(舊 master 還在、但舊 worker 沒了)。** 因為**舊 master 還活著**,可以**讓它把舊 worker 重新拉起來**——給舊 master 發 `HUP`:

```bash
kill -HUP 1000      # 舊 master 收 HUP → 用(舊)設定重新 fork 出舊 worker
                    # 舊版本恢復服務
kill -QUIT 2000     # 再把有問題的新 master + 新 worker 優雅收掉
                    # → 完全回到舊版本
```

> 這就是為什麼流程裡先用 `WINCH`(只收舊 worker、**保留舊 master**)而不是直接 `QUIT` 舊 master:`WINCH` 保留了「用舊 master 一鍵把舊 worker 拉回來」的回滾能力。只有等你**徹底確認新版本沒問題**,才對舊 master 發 `QUIT` 把它收掉、**放棄回滾能力**、完成升級。

**一旦舊 master 被 `QUIT` 收掉,就沒有便捷回滾了**——這時要「回退」只能當成一次新的升級(把舊二進制再 `USR2` 升一遍)。所以順序很重要:**先 WINCH(留後路)→ 觀察夠久 → 再 QUIT(斷後路)**。

> ⭐ **白板答法**(被問「怎麼不停機升級 Nginx 二進制」,口述 USR2→WINCH→QUIT):
> 「先把新二進制覆蓋到原路徑。然後對舊 master 發 **`USR2`**:舊 master 會把 pid 檔改名、fork 出**新 master + 新 worker**,**新舊共用同一個 listen socket**,兩套同時服務同一個埠的流量。觀察新版本沒問題後,對舊 master 發 **`WINCH`**,優雅收掉舊 worker、**但保留舊 master 待命**——這一步留著回滾能力:萬一有問題,給舊 master 發 `HUP` 就能把舊 worker 拉回來、再 `QUIT` 掉新 master 回滾。徹底確認沒問題,最後對舊 master 發 **`QUIT`** 優雅退出,升級完成。全程因為兩套並存、共用 listen socket,埠一刻不空,所以零停機。」

> 容器世界裡的現實:**在 Kubernetes / 容器化部署中,升級 Nginx 版本通常不靠 `USR2` 熱升級,而是「換鏡像、滾動更新 Pod」**(由 k8s 的滾動發布 + readiness/PreStop 保證不丟連線,↪ `distribution/zero-downtime-release/`)。`USR2` 熱升級是**裸機 / VM 上長期跑同一個 Nginx 進程**時的看家本領,也是面試高頻考點——理解它,你才真懂「master-worker + listen socket 共享」這套機制。本章的 lab(`lab/zero-downtime/`)因此聚焦在容器內好演示的 `reload`,熱升級的 `USR2` 部分以理解機制為主。

---

## 4. 優雅退出與在途請求:`worker_shutdown_timeout` 兜底

不管是 reload 收舊 worker、還是 `QUIT` 整個下線,「優雅」都意味著「**等在途請求處理完**」。但這裡有個現實問題:**萬一某個在途請求卡住了(後端不回、客戶端不收、長連線一直開著),worker 是不是就永遠退不掉?**

是的——**默認情況下,worker 會一直等到手上所有連線都結束才退**。如果有一個 SSE 長連線、WebSocket、或卡死的請求,這個舊 worker 可能**遲遲不退**,堆積成「殭屍舊 worker」。

兜底參數是 **`worker_shutdown_timeout`**:

```nginx
# http 或 events 層
worker_shutdown_timeout 30s;   # 舊 worker 優雅退出時,最多等 30s,到點還沒處理完的連線「強制關閉」
```

它的含義:**worker 進入「優雅退出」狀態後,給在途請求一個寬限期(這裡 30s);超過寬限期還沒結束的連線,直接關掉、worker 退出。** 這是「優雅」和「不能無限等」之間的平衡:

- **設太小**:正常的慢請求(大上傳、慢介面)會在 reload/退出時被中途砍斷 → 出現「reload 偶爾掉幾個請求」的詭異現象。
- **不設(默認無限等)**:長連線場景(SSE/WebSocket/gRPC 流)會讓舊 worker **永遠退不掉**,reload 後舊 worker 殭屍堆積,佔記憶體、佔 fd。
- **合理值**:取「你業務請求的合理最長處理時間」+ 一點餘量(常見 30s~60s)。有大量長連線時,要意識到 reload 會在這個超時點**主動斷掉**那些超時的長連線——對 SSE/WebSocket 客戶端要設計好重連。

> 一句話:`worker_shutdown_timeout` 是「優雅退出」的安全閥——既給在途請求善終的機會,又不讓卡住的連線把舊 worker 永久釘在那。長連線多的服務一定要顯式設它。

---

## 5. 日誌切割:`mv` + `USR1`(配 logrotate)

Nginx 把 access/error log 寫進一個**已開啟的檔案描述符(fd)**裡——它認的是 fd,不是檔名。這帶來一個切割日誌時的經典陷阱:

> **你直接 `mv access.log access.log.1` 之後,Nginx 並不知道——它手上那個 fd 還指向同一個 inode(現在叫 `access.log.1` 了),於是新日誌繼續寫進 `access.log.1`,而你期待的新 `access.log` 一直是空的。**

正確的日誌切割是**兩步**:

```bash
# 1) 把當前日誌改名(Nginx 仍持有舊 fd,繼續寫進改名後的檔案)
mv /var/log/nginx/access.log /var/log/nginx/access.log.$(date +%F)

# 2) 通知 Nginx「重新開啟所有日誌檔」——這就是 USR1 / reopen 的作用
nginx -s reopen        # = kill -USR1 <master_pid>
```

第 2 步 `USR1`(`reopen`)讓 Nginx **關掉舊的日誌 fd、按設定裡的路徑重新 `open`**——於是它重新建立 `access.log` 並把新 fd 指向它,後續日誌寫進新檔案。被 `mv` 走的舊檔案就是切割出來的歷史日誌,可以壓縮/歸檔。

**生產上交給 logrotate**,在 `postrotate` 段裡幹第 2 步:

```
# /etc/logrotate.d/nginx
/var/log/nginx/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        # logrotate 已經把日誌改好名,這裡通知 Nginx 重開 fd
        [ -f /run/nginx.pid ] && kill -USR1 $(cat /run/nginx.pid)
    endscript
}
```

> 重點就一句:**Nginx 認 fd 不認檔名,切日誌必須 `mv` 之後發 `USR1` 讓它重開 fd**,否則新日誌會繼續寫進被改名的舊檔。logrotate 的 `postrotate` 就是自動化這一步。

---

## 6. 把運維動作收成一張速查表

日常你會用到的全部操作,對應到訊號:

| 你要做的事 | 命令 | 底層訊號 | 平滑嗎 |
|---|---|---|---|
| 改設定生效 | `nginx -t && nginx -s reload` | `HUP` | ✅ 不丟連線(§2) |
| 優雅下線 | `nginx -s quit` | `QUIT` | ✅ 在途處理完才退 |
| 緊急強停 | `nginx -s stop` | `TERM` | ❌ 立刻砍、丟在途 |
| 切日誌 | `mv` 後 `nginx -s reopen` | `USR1` | ✅ 重開 fd(§5) |
| 熱升級二進制 | `USR2` → `WINCH` → `QUIT` | 三個 | ✅ 全程零停機 + 可回滾(§3) |
| 升級失敗回滾 | 給舊 master `HUP`,給新 master `QUIT` | `HUP`/`QUIT` | ✅ 舊 master 還在(§3.3) |

> 想親手看到「reload 期間零失敗」,去跑本章 lab:`lab/zero-downtime/`——它在持續壓測中途發 `reload`,統計失敗請求數,正常結果是 `FAIL=0`,把 §2 的「不丟連線」變成你機器上看得見的數字。

---

## 交叉引用

- **master-worker 架構、worker 怎麼用 epoll 事件迴圈服務海量連線、listen socket 與 worker 的關係(本章「listen socket 由 master 持有、fork 給 worker」的引擎側內幕)**:↪ `gateway/01-reverse-proxy-engine.md`(第 1 節 master-worker、第 2 節事件迴圈)。本章只講「怎麼用訊號調度這套進程的生命週期」,不重講進程模型本身。
- **「優雅上下線 / 滾動發布 / 連線生命週期」在分散式 / k8s 層的抽象**(readiness/PreStop hook、k8s 滾動更新如何保證不丟連線、為什麼容器世界用「換鏡像滾動」而非 `USR2`):↪ `distribution/zero-downtime-release/`。本章是「單個 Nginx 進程」這一層的機制,那裡是「一群實例」這一層的抽象。
- **reload 後怎麼用 log / 指標確認新設定行為正常(灰度觀察看什麼)**:↪ `10-observability-debugging.md`(`$status`/`$upstream_response_time`/`stub_status`)。
- **`nginx -t` 校驗的設定本身怎麼寫對(區塊/繼承/`location` 優先級)**:↪ `01-config-model.md`。
- **ingress-nginx 改了 `Ingress` 物件後,controller 在底層做的「渲染 nginx.conf + reload」就是本章的 reload**:↪ `11-openresty-and-ingress.md`。

---

## 本章小結

- **訊號表是 Nginx 運維的字典**:`HUP`=reload 設定、`USR2`=熱升級二進制、`WINCH`=只收 worker 留 master、`QUIT`=優雅退出、`TERM`=快退(丟在途)、`USR1`=重開日誌 fd。`nginx -s <cmd>` 就是給 master 發訊號的語法糖。
- **`reload` 平滑的兩個關鍵**:① **listen socket 由 master 持有、reload 全程不關閉**,只是把 fd 再分享給新 worker,所以監聽埠一刻不空、新請求不漏接;② **舊 worker 不被砍死,而是停止接新連線、把在途請求處理完才退**。新舊 worker 短暫並存,新連線歸新 worker、在途請求歸舊 worker,兩邊都不斷。
- **reload 是安全的**:設定有錯時校驗失敗、master 不 fork 新 worker、舊 worker 繼續服務——「成功才換、失敗維持原狀」。但標準做法仍是 `nginx -t` 先校驗 + 灰度(先一台觀察)兜邏輯錯。
- **熱升級二進制 = USR2 → WINCH → QUIT**:`USR2` fork 出新 master + 新 worker、**共用 listen socket** 與舊的並存;觀察 OK 後 `WINCH` 收舊 worker(**保留舊 master 以便回滾**);徹底確認後 `QUIT` 收舊 master 完成。回滾靠「舊 master 一直活著」——給舊 master `HUP` 把舊 worker 拉回來、給新 master `QUIT` 收掉。
- **優雅退出靠 `worker_shutdown_timeout` 兜底**:給在途請求寬限期、到點強制關閉,避免長連線把舊 worker 永久釘住。長連線服務必設。
- **切日誌**:Nginx 認 fd 不認檔名,必須 `mv` 後發 `USR1`(`reopen`)讓它重開 fd;logrotate 的 `postrotate` 自動化這一步。

## 章末問答(複習自檢,答案要點都在前面正文)

1. 把訊號表口述一遍:`HUP` / `USR2` / `WINCH` / `QUIT` / `TERM` / `USR1` 各讓 master 做什麼、對應哪個運維場景?`QUIT` 和 `TERM` 的關鍵差別是什麼?

2. **(核心)** `nginx -s reload` 為什麼不會中斷在途請求、也不會漏接新請求?把那兩個關鍵(listen socket、舊 worker 怎麼退)講清楚。

3. 你 reload 時新設定寫錯了(比如憑證路徑不存在)。線上服務會中斷嗎?master 會做什麼?既然 reload 自己會校驗,為什麼還是建議先 `nginx -t`?

4. **(熱升級流程題)** 要不停機把 Nginx 從舊版本升到新版本,`USR2` → `WINCH` → `QUIT` 三個訊號**分別**讓 Nginx 做什麼?為什麼是這個順序,而不是 `USR2` 之後直接對舊 master 發 `QUIT`?
   <details><summary>對答案</summary>
   `USR2`(發給舊 master):舊 master 把 pid 檔改名為 `.oldbin`,fork 出**新 master + 新 worker**(載入新二進制),新舊**共用同一個 listen socket**、同時服務同一個埠。
   `WINCH`(發給舊 master):優雅停掉**舊 worker**(在途處理完才退),但**保留舊 master**待命。
   `QUIT`(發給舊 master):舊 master 優雅退出,升級完成。
   順序原因:`WINCH` 只收舊 worker、**留著舊 master** 是為了**保留回滾能力**——觀察期間若新版本有問題,可給舊 master 發 `HUP` 把舊 worker 拉回來。直接 `QUIT` 舊 master 會立刻**放棄回滾能力**;必須等徹底確認沒問題,才 `QUIT` 斷後路。
   </details>

5. **(回滾題)** 你已經 `WINCH` 收掉了舊 worker(舊 master 還在、新 worker 在服務),這時發現新版本有 bug。怎麼回滾到舊版本?關鍵前提是什麼?
   <details><summary>對答案</summary>
   給**舊 master** 發 `HUP`——它用舊設定重新 fork 出舊 worker,舊版本恢復服務;再給**新 master** 發 `QUIT` 把有問題的新進程優雅收掉,完全回到舊版本。
   關鍵前提:**舊 master 一直活著**(只有在最後 `QUIT` 它之前都還在),所以能用它把舊 worker 拉回來。一旦舊 master 被 `QUIT` 收掉,就沒有便捷回滾了。
   </details>

6. 你的服務有大量 SSE 長連線。直接 `nginx -s reload` 後,舊 worker 為什麼可能遲遲退不掉?用哪個參數兜底?設太小 / 不設分別有什麼後果?

7. 你 `mv access.log access.log.1` 之後發現新的 `access.log` 一直是空的、日誌全寫進了 `access.log.1`。為什麼?正確的日誌切割少了哪一步?logrotate 在哪個段落補這一步?

8. 多台 Nginx 要上一份新設定,「先一台 reload、觀察、再全量」這個灰度節奏防的是哪一類錯誤(校驗和 reload 安全網都抓不到的那種)?
