# 10 · 可觀測與除錯 playbook:log 變數 / 499-502-503-504 / 連線耗盡 🔬⭐

> 一句話:這是「Nginx 救火」這門手藝。線上一個 502 跳出來,菜鳥盯著 Nginx 設定看半天,老手三步定位:**先看狀態碼分流到 502/504/499/503 哪一桶 → 再看 `$upstream_*` 變數確認是 Nginx 自己擋的還是後端的鍋 → 最後按 playbook 表查根因**。這一章把「Nginx 自帶的眼睛」(log 變數、`stub_status`、`error_log debug`)講透,再把狀態碼診斷與連線耗盡定位串成一份能直接抄上牆的 playbook。

Nginx 站在客戶端和後端之間,它是**整條鏈路裡資訊最全的那一跳**——客戶端是誰、後端是哪台、連後端花了多久、後端回了什麼、Nginx 自己排了多久隊,全在它手上。問題是這些資訊**默認不寫出來**:默認的 `log_format combined` 連 `$upstream_response_time` 都沒有,出事時你只能看到一個光禿禿的 `502`,卻不知道是「連不上後端」還是「後端回了垃圾」。所以這章的第一件事,就是**把 Nginx 的眼睛打開**。

> 一般可觀測性的方法論(三支柱 metrics/logs/traces、OpenTelemetry、分散式追蹤怎麼串)不在這裡——那是 `observability/` 的事;「日誌等級怎麼定、該記什麼、結構化與關聯 ID」是 `logging/` 的事。本章只講**Nginx 這一跳**:它有哪些內建變數、怎麼用它們把 502/504/499/503 分開、怎麼定位連線耗盡。

---

## 1. 🔬 `log_format` 與內建變數:把 Nginx 那一跳的全部資訊寫出來

`access_log` 預設用一個叫 `combined` 的格式,它**只記客戶端那一側**(誰來的、請求什麼、回了什麼狀態碼),完全沒有「後端那一側」的資訊。出事時這份日誌幾乎沒用——它告訴你「回了 502」,但不告訴你「為什麼」。

生產上你必須自訂 `log_format`,把**和後端互動的那組變數**補進去。先把這組變數逐個講清(這是讀懂任何 Nginx 慢請求/錯誤的詞彙表):

| 變數 | 是什麼 | 怎麼用它定位 |
|---|---|---|
| **`$status`** | Nginx **最終回給客戶端**的狀態碼 | 第一層分流:502/504/499/503 各進不同的桶(見第 2 節) |
| **`$request_time`** | **整個請求的總耗時**——從收到請求第一個 byte,到把回應最後一個 byte 寫給客戶端為止(**含**讀客戶端、等後端、寫客戶端的全部時間) | 「客戶端體感的慢」。注意它**含寫回客戶端的時間**——慢客戶端會把它撐大,即使後端很快 |
| **`$upstream_response_time`** | **後端那一段的耗時**——從 Nginx 開始連後端,到收完後端回應為止 | 「後端有多慢」。HIT 快取時是 `-`(後端沒被碰) |
| **`$upstream_connect_time`** | Nginx **和後端建立 TCP 連線(含 TLS)** 花的時間 | 單獨看「連後端」這一步——它高 = 後端 backlog 滿/網路慢/後端忙到 accept 不過來 |
| **`$upstream_addr`** | 這次請求**實際打到哪台後端**(IP:port);若 `next_upstream` 重試過,會是逗號/冒號串接的多台 | 確認「打到哪台」「重試了幾台」——排查某台後端壞掉時關鍵 |
| **`$upstream_status`** | **後端回給 Nginx** 的狀態碼(可能和 `$status` 不同!) | 分清「是後端回的錯」還是「Nginx 自己加工/擋下的」(見下方關鍵對比) |
| **`$upstream_cache_status`** | 快取命中狀態(HIT/MISS/STALE…,ch05 講過) | 排查快取相關問題、量化命中率 |
| **`$bytes_sent`** | 回給客戶端的**總位元組**(含回應頭) | 配合 `$body_bytes_sent`(只 body)看回應大小;異常小可能是回應被截斷 |
| **`$request_id`** | Nginx 為每個請求生成的唯一 ID | 透傳給後端(`proxy_set_header X-Request-Id $request_id;`)做**跨 Nginx↔後端的日誌關聯**(↪ 關聯 ID 的方法論在 `logging/03-結構化與關聯ID.md`) |

### 1.1 🔬 `$request_time` 減 `$upstream_response_time` = Nginx 自身/排隊耗時(核心)

這是整章最值錢的一條內幕,面試和救火都靠它:

> **`$request_time`** 是「客戶端等了多久」(總耗時),**`$upstream_response_time`** 是「後端佔了多久」。
> **兩者相減 = 不在後端身上的時間 = Nginx 自己的處理 + 排隊 + 讀寫客戶端的時間。**

這個差值幫你把「慢」歸因到正確的一邊:

| 觀察 | 含義 | 往哪查 |
|---|---|---|
| `$request_time` ≈ `$upstream_response_time`(兩者都大) | 慢在**後端**——Nginx 一收到就轉走、後端慢慢回 | 查後端(慢 SQL/下游卡/GC),Nginx 沒問題 |
| `$request_time` ≫ `$upstream_response_time`(差值很大) | 慢在**Nginx 這一側或客戶端側**——後端早就回完了,時間花在別處 | 兩種典型:① **慢客戶端**(回應大 + 客戶端網路慢,寫回去花了很久,但 `proxy_buffering on` 下後端早被放掉,所以 upstream_time 小);② **worker 排隊**(連線耗盡/worker 忙不過來,請求在 Nginx 裡排隊,見第 4 節) |
| `$upstream_response_time` = `-` 但 `$request_time` 有值 | 後端**根本沒被碰**——快取 HIT,或請求被 Nginx 在到後端前就擋了(限流/`return`/靜態檔) | 看 `$upstream_cache_status` 和 `$status`,多半是正常的快取命中或限流 |

> ⚠️ 一個常見誤判:看到 `$request_time` 很大就罵後端。但若 `$upstream_response_time` 很小,**後端是清白的**——是「回應太大 + 慢客戶端」或「Nginx 排隊」。這個差值就是用來**避免冤枉後端**的。

### 1.2 🔬 `$status` vs `$upstream_status`:分清「誰回的錯」

這兩個常常**不一樣**,而它們的差異本身就是診斷線索:

- **`$upstream_status`**:後端**真的回給 Nginx** 的碼。
- **`$status`**:Nginx **最終回給客戶端**的碼(可能被 Nginx 加工過)。

幾個典型「不一致」的場景:

| `$upstream_status` | `$status` | 發生了什麼 |
|---|---|---|
| `-`(空) | `502` | 後端**根本沒回應**(連不上/連線被拒/回了非法協議)——Nginx 沒從後端拿到任何狀態碼,自己生成 502 |
| `-`(空) | `504` | 後端連上了但**在超時內沒回完**——Nginx 沒拿到完整回應,自己生成 504 |
| `500` | `500` | 後端**自己回了 500**(應用 bug)——這是後端的鍋,不是 Nginx |
| `502`(其一)→ `200`(最終) | `200` | 第一台後端回 502,Nginx 靠 `next_upstream` **重試到第二台成功**——`$upstream_addr` 會看到兩台、`$upstream_status` 會是 `502, 200` |
| `-` | `499` | **客戶端先斷了**,Nginx 還沒從後端拿到回應(見第 2 節) |

**一句話判據**:`$upstream_status` 為空(`-`)而 `$status` 是 5xx → **Nginx 沒從後端拿到東西**(502/504,連不上或超時);`$upstream_status` 有具體 5xx → **後端自己回的錯**(應用層 bug,不該怪 Nginx)。

### 1.3 建議的生產 `log_format`(直接抄)

```nginx
http {
    log_format main escape=json
        '{'
        '"time":"$time_iso8601",'
        '"remote_addr":"$remote_addr",'
        '"request":"$request",'
        '"status":$status,'                              # Nginx 最終回給客戶端的碼
        '"request_time":$request_time,'                  # 總耗時(客戶端體感)
        '"upstream_addr":"$upstream_addr",'              # 實際打到哪台後端
        '"upstream_status":"$upstream_status",'          # 後端回給 Nginx 的碼
        '"upstream_connect_time":"$upstream_connect_time",'  # 連後端耗時
        '"upstream_response_time":"$upstream_response_time",' # 後端那段耗時
        '"cache":"$upstream_cache_status",'              # 快取命中(ch05)
        '"bytes_sent":$bytes_sent,'
        '"request_id":"$request_id"'                     # 跨 Nginx↔後端關聯
        '}';

    access_log /var/log/nginx/access.log main;
    error_log  /var/log/nginx/error.log  warn;          # error 走另一份,等級至少 warn
}
```

幾個刻意的選擇:

- **`escape=json` + JSON 結構**:讓日誌直接能被 Loki/ES/CloudWatch 等結構化攝取、按欄位查(`upstream_status:"-" AND status:502`),不用再寫脆弱的正則切欄位。`escape=json` 確保值裡的引號/控制字元被正確轉義。(結構化日誌的方法論 ↪ `logging/03-結構化與關聯ID.md`、`logging/05-配置讓它真的吐.md`。)
- **`upstream_*` 系列全帶上**:這是 Nginx 那一跳的核心診斷欄位,缺了它們的日誌幾乎沒法救火。
- **`access_log` 和 `error_log` 分開**:access 記每個請求(含正常的),error 只記異常(連後端失敗、設定告警、`worker_connections` 不夠等)。**救火時 error_log 往往比 access_log 更直接**——它會明說「為什麼」。

> 高 QPS 下 `access_log` 是熱路徑,可開 `access_log ... buffer=64k flush=5s;` 批次落盤,或對健康檢查/靜態資源關掉 access_log 減 I/O(取捨見 `logging/06-效能與衛生.md`)。

---

## 2. 🔬⭐ 狀態碼診斷:499 / 502 / 503 / 504 各是什麼引起的(核心)

這是本章的主戰場,也是面試最愛問的一組。四個碼**長得像但根因完全不同**,把它們的成因逐個刻進腦子,線上一跳出來就能直接縮小範圍。ch04 已經點出「`connect`→502 / `read`→504」的分水嶺,這裡把四個碼講全。

### 2.1 `499` —— 客戶端在 Nginx 回應前就斷開了

**`499` 是 Nginx 的非標準碼(HTTP 標準裡沒有),意思是:客戶端在 Nginx 還沒把回應送出去之前,就主動關閉了連線。**

它**不是 Nginx 或後端出錯**,而是「客戶端不等了」:

- **客戶端自己超時**:前端設了 3 秒超時,後端 5 秒才回——客戶端在第 3 秒主動斷開,Nginx 記 499。
- **用戶取消**:用戶關了分頁、按了停止、App 切到後台。
- **上游有更短的超時**:Nginx 前面還有一層 LB/CDN,它的超時比 Nginx 短,先斷了。

**怎麼讀**:大量 499 + 對應請求的 `$upstream_response_time` 很大 → **後端慢到客戶端等不及主動放棄**。所以 499 表面是客戶端的事,**根子常常還是後端慢**——你要去查的是「為什麼後端這麼慢讓客戶端等到超時」,而不是去調 Nginx。

> 一個易混點:499 vs 504。**都是「後端慢」,差在誰先放棄**:客戶端先放棄(客戶端超時 < 後端耗時)→ **499**;Nginx 先放棄(`proxy_read_timeout` < 後端耗時,且客戶端還在等)→ **504**。看 `$status` 是 499 還是 504,就知道是「客戶端的耐心」還是「Nginx 的耐心」先耗盡。

### 2.2 `502 Bad Gateway` —— 後端拒連 / 連不上 / 回了非法回應

**`502` 意思是:Nginx 想把請求轉給後端,但後端那一側壞了——根本連不上,或連上了卻回了 Nginx 看不懂的東西。**

三類典型成因:

1. **後端進程掛了 / 埠沒人聽**:後端 crash、還沒起來、被 OOM kill,Nginx 連過去被 `Connection refused`。對應 ch04 的 `proxy_connect_timeout` 場景(連不上)。
2. **埠/地址配錯**:`upstream` 寫錯 IP/port,連到一個沒有服務的地方。
3. **後端回了非法回應**:後端進程在、也回了,但回的不是合法 HTTP——回應頭壞掉、提前關閉連線、回應頭超過 `proxy_buffer_size` 放不下、PHP-FPM/uwsgi 進程崩在半路只吐了一半。這類最隱蔽:後端「看起來活著」,但 Nginx 解析回應時出錯,照樣 502。
4. **全部後端被熔斷**:`upstream` 裡所有 server 都被 `max_fails` 標記失敗,沒有可用後端可轉(這條和 503 有重疊,見 2.4 的辨析)。

**怎麼讀**:502 時看日誌 `$upstream_status` 通常是**空(`-`)**——Nginx 沒從後端拿到任何狀態碼。error_log 裡會有更具體的線索:`connect() failed (111: Connection refused)`、`upstream prematurely closed connection`、`upstream sent invalid header`。

### 2.3 `504 Gateway Timeout` —— 後端連上了,但沒在超時內回完

**`504` 意思是:Nginx 成功連上了後端,請求也發過去了,但後端在 `proxy_read_timeout` 內沒把回應給完——Nginx 等不下去,自己回 504。**

和 502 的關鍵區別:**502 是「連不上/回了垃圾」,504 是「連上了但回得太慢」。** 成因:

- **後端處理太慢**:慢 SQL、下游依賴卡住、死循環、GC 停頓、後端自己在等它的下游超時。這是 504 最常見的成因。
- **`proxy_read_timeout` 設太短**:後端本來就需要 90 秒(大報表、批次),而你 `proxy_read_timeout` 只給 60 秒——這時不是後端的錯,是超時配得不合理,該在那個 location 單獨調大(別全局放大,ch04 講過)。

**怎麼讀**:504 時 `$upstream_status` 也是**空(`-`)**(沒收完回應拿不到碼),但 `$upstream_connect_time` **有值且不大**(連上了),`$upstream_response_time` ≈ `proxy_read_timeout`(卡在超時上限)。error_log 裡是 `upstream timed out (110: Connection timed out) while reading response header from upstream`——注意這句明說 **while reading**(讀回應階段超時),正是 504 的指紋。

### 2.4 `503 Service Unavailable` —— Nginx 自己擋下的

**`503` 和上面三個的本質不同:它通常是 Nginx 自己主動擋的,請求大多沒到後端。** 兩大來源:

1. **限流/限連(ch06)**:`limit_req`(超速)或 `limit_conn`(超並發)觸發。注意 Nginx 預設用 `503`,但**建議改成 `429 Too Many Requests`**(`limit_req_status 429;`)——語義更準確,也讓客戶端/監控能和「真的服務不可用」區分開(ch06 講過)。沒改的話,限流就混在 503 裡,容易誤判成「服務掛了」。
2. **`upstream` 全部不可用**:`upstream` 區塊裡所有 server 都被 `max_fails` 標記失敗(全熔斷),或都標了 `down`——Nginx 沒有可轉發的後端,回 503。

> **503 vs 502 的辨析(易混)**:都可能源於「後端有問題」,但路徑不同。
> - **502**:Nginx **試著連了**某台後端,連不上或拿到非法回應。
> - **503**(全熔斷那種):後端**已經被標記為不可用**,Nginx **連試都不試**,直接回 503。
> - **503**(限流那種):**請求根本沒到後端**,是 Nginx 在門口按速率/並發擋下的。
>
> 實務判別:看 `$upstream_addr`——502 通常**有**後端地址(試過了),限流型 503 通常**沒有**(沒往後端轉)。

### 2.5 狀態碼 → 最可能根因 → 下一步查什麼(背這張表)

| 狀態碼 | 最可能根因 | 看哪個變數確認 | 下一步查什麼 |
|---|---|---|---|
| **499** | 客戶端先斷(客戶端/上游超時、用戶取消)——常因**後端慢**到客戶端不等了 | `$upstream_response_time` 大?客戶端/上游的超時設定 | 查後端為何慢(同 504 的查法);核對客戶端與上游 LB 的超時是否比 Nginx 短 |
| **502** | 後端拒連/連不上/回了非法回應/全熔斷 | `$upstream_status` = `-`;`$upstream_addr` 有值(試過了) | 後端進程是否活、埠對不對;error_log 看 `connection refused` / `prematurely closed` / `invalid header`;`proxy_buffer_size` 是否放不下回應頭 |
| **503** | Nginx 自己擋:限流(`limit_req`/`limit_conn`)或 `upstream` 全掛 | `$upstream_addr` = `-`(限流型,沒往後端轉)/全熔斷型 | 限流型:看 error_log `limiting requests`、考慮改 `429`;全熔斷型:查所有後端是否都掛、`max_fails` 是否誤判 |
| **504** | 後端連上了但沒在 `proxy_read_timeout` 內回完(後端慢 / 超時配太短) | `$upstream_status` = `-`;`$upstream_connect_time` 有值且小;`$upstream_response_time` ≈ timeout | 查後端慢在哪(慢 SQL/下游/GC);判斷 `proxy_read_timeout` 是否合理(別全局放大,只調該 location) |

> ⭐ **白板答法**(被問「502 和 504 怎麼分」):
> 「都是 5xx,但 502 是**連不上或拿到垃圾**,504 是**連上了但回得太慢**。具體:`proxy_connect_timeout` 撞到(連不上後端)→ 502;後端回了非法回應(頭壞了、提前關連線)也是 502;後端連上了、請求發過去了,但沒在 `proxy_read_timeout` 內回完 → 504。日誌上的指紋:兩者 `$upstream_status` 都是空(`-`),但 502 的 error_log 是 `connect() failed / connection refused / prematurely closed`,504 的 error_log 是 `upstream timed out ... while reading response header`,而且 504 的 `$upstream_connect_time` 有值(連上了)。再補一句 499:那是**客戶端**先斷的——客戶端的超時比後端耗時短就 499,Nginx 的超時比後端短就 504,差在誰先放棄。」

---

## 3. 🔬 `stub_status`:Nginx 自己的即時體徵

`access_log` 是「每個請求的歷史」,`stub_status` 是「Nginx 此刻的活體徵象」——當前有多少連線、多少在讀、多少在寫、多少在空等。它是定位**連線耗盡**(第 4 節)的第一塊儀表盤。

`stub_status` 是內建模組(`ngx_http_stub_status_module`,標配),開法:

```nginx
server {
    listen 127.0.0.1:8080;        # 只綁本機,別暴露公網
    location /nginx_status {
        stub_status;
        allow 127.0.0.1;
        deny all;
    }
}
```

`curl http://127.0.0.1:8080/nginx_status` 輸出:

```
Active connections: 291
server accepts handled requests
 16630948 16630948 31070465
Reading: 6 Writing: 179 Waiting: 106
```

**每個數字是什麼(逐個講)**:

| 指標 | 含義 | 怎麼讀 |
|---|---|---|
| **Active connections** | 當前活躍連線總數(= Reading + Writing + Waiting) | 逼近 `worker_processes × worker_connections` 就是連線快耗盡的警報(見第 4 節) |
| **accepts** | 啟動至今**接受**的連線總數(累計) | 和 handled 對比:**accepts > handled** 表示有連線被丟棄(通常是 `worker_connections` 滿了 accept 不下) |
| **handled** | 啟動至今**處理**的連線總數(累計) | 正常時 = accepts;小於 accepts 就出事了 |
| **requests** | 啟動至今的**請求**總數(累計) | requests / handled = 每連線平均請求數,反映 keepalive 復用程度(遠大於 1 = keepalive 在起作用) |
| **Reading** | 正在**讀請求頭**的連線數 | 異常高 = 客戶端發頭很慢,或遭遇慢速攻擊(Slowloris) |
| **Writing** | 正在**讀請求體 / 處理 / 寫回應**的連線數 | 高 = 後端慢或回應大,Nginx 在等後端或在往客戶端寫 |
| **Waiting** | **keepalive 空閒**等待下一個請求的連線數 | 高很正常(keepalive 連線在等復用);但它也佔著 `worker_connections` 名額 |

**關鍵診斷信號**:

- **accepts ≠ handled**(handled 更小):有連線**被丟棄**——幾乎一定是 `worker_connections` 耗盡。這是連線耗盡最硬的證據。
- **Active connections 逼近上限**(`worker_processes × worker_connections`):快耗盡了,趕緊定位(第 4 節)。
- **Reading 異常高**:慢頭/慢速攻擊;考慮 `client_header_timeout` 收緊。
- **Waiting 很高**:keepalive 空閒連線多,本身正常,但若同時 Active 逼近上限,說明空閒連線把名額佔光了——可調 `keepalive_timeout` 縮短或加 `worker_connections`。

### 3.1 Prometheus exporter:把 `stub_status` 變成可告警的指標

`stub_status` 只有一個瞬時快照,要做監控/告警/趨勢圖,標準做法是掛 **nginx-prometheus-exporter**(官方維護):它定期抓 `stub_status`(開源版)或 `/api`(Plus 版),轉成 Prometheus 指標。

```
nginx (stub_status) ──► nginx-prometheus-exporter ──► Prometheus ──► Grafana / 告警
```

抓出來的核心指標(開源版來自 stub_status):

- `nginx_connections_active` / `nginx_connections_waiting` / `nginx_connections_reading` / `nginx_connections_writing`
- `nginx_http_requests_total`(配 `rate()` 算 QPS)
- `nginx_connections_accepted` / `nginx_connections_handled`(兩者**背離**就是連線丟棄,可直接設告警:`accepted - handled > 0`)

> 注意開源版 `stub_status` **拿不到「按 status 分類的請求數」「`$upstream_response_time` 分位數」**這類細粒度指標(那是 Nginx Plus 的 `/api` 或要靠 OpenResty/`log` 模組另外算)。要在開源版做「502 率告警」「P99 延遲」,常見做法是**從 access_log 提取**(用 `mtail` / `grok_exporter` / Vector / Promtail 把 JSON 日誌轉指標),或上 OpenResty(ch11)。
>
> 一般的 metrics/告警體系怎麼搭(指標類型、SLI/SLO、告警設計)↪ `observability/01-三支柱-metrics-logs-traces.md`;本章只講「Nginx 這一跳吐哪些指標」。

---

## 4. 🔬 連線耗盡定位:`worker_connections` 打滿 / fd 耗盡

這是 Nginx 最典型、也最容易被誤判成「Nginx 掛了」的故障——其實 Nginx 沒掛,是**連線名額用光了,新連線進不來在門口排隊或被丟棄**。先理解上限怎麼來的:

> **Nginx 能同時持有的連線上限 ≈ `worker_processes × worker_connections`**,但這個數還被**兩道閘**卡住:
> 1. **`worker_rlimit_nofile`**(單 worker 能開的 fd 數)——每個連線至少佔 1 個 fd,**反向代理場景每個請求佔 2 個**(客戶端側 1 個 + 後端側 1 個),所以 `worker_rlimit_nofile` 要 ≥ `worker_connections × 2` 才不會先撞 fd 上限(ch09 講過參數聯動)。
> 2. **OS 的 `ulimit -n` / `fs.file-max`**——`worker_rlimit_nofile` 設再大,也不能超過系統允許的 fd 上限。

### 4.1 徵兆:怎麼看出來是連線耗盡

連線耗盡時,你會**同時**看到這幾個信號(任一單獨出現可能是別的事,湊齊就八九不離十):

1. **error_log 出現明確告警**——這是最硬的證據:
   ```
   [alert] 1234#0: *567 1024 worker_connections are not enough
   ```
   或 fd 先耗盡時:
   ```
   [crit] accept4() failed (24: Too many open files)
   ```
   `24: Too many open files` 就是 fd 耗盡(`EMFILE`)——說明撞到的是 `worker_rlimit_nofile` / `ulimit` 那道閘,而不是 `worker_connections`。

2. **`stub_status` 上 Active connections 逼近 `worker_processes × worker_connections`**,且 **accepts > handled**(有連線被丟棄)。

3. **客戶端側**:新連線**連不上 / 連線超時 / 排隊很久**(請求被 OS 的 `listen backlog` 接著,但 Nginx 的 worker 拿不到名額去 accept)。

4. **`$request_time` 大但 `$upstream_response_time` 小**(第 1.1 節那個差值):請求在 **Nginx 裡排隊**等名額,後端其實很快——這個差值是連線耗盡的隱性指紋之一。

### 4.2 查法與根因

| 怎麼查 | 命令 / 看哪 | 說明 |
|---|---|---|
| 看 error_log | `grep -E "worker_connections|Too many open files" error.log` | 直接告訴你撞的是哪道閘 |
| 看當前連線數 | `curl http://127.0.0.1:8080/nginx_status`(看 Active / accepts vs handled) | Active 逼近上限 + accepts>handled = 連線丟棄 |
| 看實際 fd 用量 | `ls /proc/$(cat /var/run/nginx.pid 之子worker pid)/fd | wc -l`;或 `lsof -p <worker_pid> | wc -l` | 對比 `worker_rlimit_nofile`,看是不是 fd 先到頂 |
| 看 OS 上限 | `cat /proc/<pid>/limits | grep "open files"`(看 worker 進程**實際生效**的 fd 上限) | 確認 `worker_rlimit_nofile` 有沒有真的生效(systemd `LimitNOFILE` 可能更嚴) |
| 看 backlog 溢出 | `ss -lnt`(看 Recv-Q 是否堆積)、`netstat -s | grep -i listen`(SYN/accept queue overflow 計數) | backlog 溢出 = 連線多到 OS 隊列都滿了(↪ ch09 `somaxconn`) |

**根因通常是三類之一**:

1. **真實流量超過容量**:QPS/並發確實漲了 → 加 `worker_connections`、加機器、或上游限流。
2. **連線沒被及時釋放**:後端慢(每個連線佔著久,Active 飆高)、keepalive 空閒連線太多佔名額(`keepalive_timeout` 太長)、慢客戶端/慢速攻擊撐住連線。
3. **fd 上限沒配對**:`worker_connections` 開很大,但 `worker_rlimit_nofile` / `ulimit -n` 沒跟著放大 → 先撞 `Too many open files`,連線數還沒到 `worker_connections` 就崩了。**這是最常見的「配置型」連線故障**——治本是把 `worker_rlimit_nofile` 設到 `worker_connections × 2` 以上,並確認 systemd `LimitNOFILE` 沒在外面卡住它(ch09 的參數聯動)。

> ⭐ **白板答法**(被問「怎麼定位 Nginx 連線耗盡」):
> 「三步。① 看 **error_log**:`worker_connections are not enough` 就是連線名額用光,`Too many open files (24)` 就是 fd 先耗盡——這兩句直接告訴你撞的是哪道閘。② 看 **stub_status**:Active connections 逼近 `worker_processes × worker_connections`,而且 **accepts > handled**(有連線被丟棄)就坐實了。③ 對比 **`$request_time` 和 `$upstream_response_time`**:前者大、後者小,說明請求卡在 Nginx 裡排隊、後端其實很快。根因不外乎流量真漲、連線釋放太慢(後端慢/keepalive 空閒太多/慢客戶端),或最常見的『`worker_connections` 開大了但 `worker_rlimit_nofile`/`ulimit` 沒跟上,先撞 fd 上限』。反代別忘了**每請求佔 2 個 fd**(客戶端+後端),所以 fd 上限要至少是連線數的兩倍。」

---

## 5. 🔬 `error_log debug`:看單請求卡在哪個 phase

`access_log` 是「結果」,`error_log` 的 **debug 級**是「過程」——它能逐步打印**一個請求在 Nginx 內部走了哪些 phase**(rewrite → access → content,對應 ch01/`gateway/02` 的管線模型)、`location` 怎麼匹配的、`proxy_pass` 解析到哪台後端、buffer 怎麼分配。當「`location` 命中不如預期」「`rewrite` 改完路徑不對」「就是不知道為什麼 502」這類詭異問題用普通日誌看不出來時,debug log 是終極手段。

**前提**:debug 級需要 Nginx **編譯時帶 `--with-debug`**(很多發行版的包已經帶了,`nginx -V 2>&1 | grep -- --with-debug` 確認;沒帶就只能換包或自編)。

開法(別全局開,debug 日誌量極大會淹沒磁碟):

```nginx
error_log /var/log/nginx/debug.log debug;       # 全局 debug(慎用,只在排查時短暫開)
```

更安全的做法——**只對某個來源 IP 開 debug**(`debug_connection`,生產排查首選):

```nginx
events {
    debug_connection 203.0.113.5;     # 只有這個 IP 的請求印 debug,其餘照常
}
```

這樣你用自己的測試機 IP 發一個請求,就能在 debug.log 裡看到**只屬於這一個請求**的完整 phase 軌跡,不會被生產流量淹沒。

debug 日誌裡能看到的關鍵線索(舉幾個你會盯著找的)：

- `test location: "/api/"` / `using configuration "/api/"` —— **`location` 到底命中了哪條**(排查匹配優先級問題,呼應 ch01)。
- `rewrite phase: ...` / `"...": ... matches "..."` —— rewrite 怎麼改的 URI。
- `http upstream request: ...` / `connect to ...` —— 連的是哪台後端、connect 結果。
- `http upstream process header` / `upstream sent invalid header` —— 後端回應頭解析(502 的根因常在這裡現形)。

> 一句心法:**普通 log 告訴你「出了什麼結果」,debug log 告訴你「在哪一步出的」。** 90% 的問題用第 1-4 節的 access_log + stub_status + error_log(warn 級)就定位了;只有「設定行為和預期不符」「狀態碼成因仍不明」時才上 debug,且務必用 `debug_connection` 限定來源、查完關掉。

---

## 6. 🔬 抓包:`tcpdump` 看 Nginx ↔ 後端那一段

當 502 的 error_log 寫著 `upstream prematurely closed connection` 或 `upstream sent invalid header`,而你**懷疑是後端回了非法協議**、但後端那邊又賴帳說「我沒問題」時——抓包是最終仲裁。Nginx 站在中間,你可以**分別抓兩段**:

```bash
# 抓 Nginx ↔ 後端那一段(後端在 10.0.0.11:8080)
tcpdump -i any -nn -A 'host 10.0.0.11 and port 8080' -w upstream.pcap

# 抓客戶端 ↔ Nginx 那一段(Nginx 聽 80)
tcpdump -i any -nn 'port 80' -w client.pcap
```

抓包能看清 access_log 看不到的東西:

- **後端到底回了什麼位元組**:`-A`(ASCII)直接看到後端吐的原始 HTTP——是不是回應頭格式錯了、是不是回了一半就 `FIN`/`RST` 關連線(對應 `prematurely closed`)。
- **連線是被哪一方關的**:看 `FIN`/`RST` 是 Nginx 發的還是後端發的——分清「後端主動斷」(後端 bug)還是「Nginx 超時主動斷」(504)。
- **TLS 握手卡在哪一步**(Nginx 反代後端是 HTTPS 時):`ClientHello`/`ServerHello`/憑證交換哪一步斷的。

> 抓包是「重武器」,只在日誌定位不到、需要看**位元組級真相**(尤其「後端說自己沒問題」的扯皮場景)時才用。用 `host + port` 過濾把抓包範圍縮到那一段後端連線,別在高流量機器上裸抓全部。

---

## 7. 🔬 症狀 → 定位 → 根因 playbook(把全章串成一張可查的表)

線上出事時,別從頭翻文件——按症狀直接查這張表,它把前六節串成「看到 X → 查 Y → 多半是 Z」的條件反射:

| 症狀(你先觀察到的) | 第一步看哪 | 收斂到的根因 | 動作 |
|---|---|---|---|
| **一堆 502** | error_log:`connection refused` / `prematurely closed` / `invalid header`;`$upstream_status`=`-` | 後端掛/埠錯(refused);後端回非法回應(invalid header / prematurely closed);回應頭太大放不下(`proxy_buffer_size`) | 拉起/修後端;埠對齊;invalid header 用 tcpdump 抓後端真實回應;調大 `proxy_buffer_size` |
| **一堆 504** | error_log:`upstream timed out ... while reading response header`;`$upstream_connect_time` 小、`$upstream_response_time`≈timeout | 後端慢(慢 SQL/下游/GC);或 `proxy_read_timeout` 配太短 | 查後端慢在哪;確認 timeout 是否合理,只在該 location 調 |
| **一堆 499** | `$status`=499 + 對應 `$upstream_response_time` 大 | 後端慢到客戶端先放棄;或上游 LB 超時比 Nginx 短 | 同 504 查後端;核對客戶端/上游超時鏈 |
| **一堆 503** | `$upstream_addr` 有沒有值;error_log `limiting requests` / 後端全掛 | 有值=`upstream` 全熔斷;無值+limiting=限流觸發 | 全熔斷:查所有後端是否掛、`max_fails` 誤判;限流:看是否該調閾值/改 429 |
| **整體變慢,但後端不慢** | 比 `$request_time` vs `$upstream_response_time`;`stub_status` 的 Active/accepts-handled | 差值大 = Nginx 排隊(連線耗盡)或慢客戶端 | 連線耗盡走第 4 節;慢客戶端確認 `proxy_buffering on` |
| **新連線連不上 / 大量超時** | error_log:`worker_connections are not enough` / `Too many open files`;stub_status accepts>handled | 連線名額耗盡 / fd 耗盡 | 加 `worker_connections`;對齊 `worker_rlimit_nofile`(≥連線數×2)與 `ulimit`;查連線為何不釋放 |
| **改了後端但客戶端看到舊資料** | `$upstream_cache_status` 是不是 HIT | 快取命中,改動沒回源 | ch05:查 TTL、`proxy_cache_valid`、是否該 purge |
| **`location` 命中/`rewrite` 結果和預期不符** | `debug_connection` 開 debug,看 `test location` / `rewrite phase` | 匹配優先級或 rewrite flag 理解錯 | 對照 ch01 優先級 / ch02 flag;查完關 debug |
| **後端說自己沒問題,但 Nginx 一直 502** | `tcpdump` 抓 Nginx↔後端那段(`-A` 看原始位元組) | 後端確實回了非法回應 / 提前 RST | 拿 pcap 對質;修後端協議/連線處理 |

**這張表的用法**:左欄是你在告警/監控上**先看到的現象**,順著一行往右走就是「先看哪個變數 → 收斂到根因 → 怎麼動手」。把它貼在 runbook 裡,出事時照表走,不靠記憶。

---

## 交叉引用

- **一般可觀測性方法論**(三支柱 metrics/logs/traces、指標類型、SLI/SLO、告警設計、分散式追蹤怎麼串):↪ `observability/01-三支柱-metrics-logs-traces.md`、`observability/03-分散式追蹤內幕.md`。本章只講「Nginx 這一跳吐哪些指標/日誌」。
- **日誌怎麼寫好**(等級 rubric、該記什麼、結構化與關聯 ID、效能與衛生):↪ `logging/03-結構化與關聯ID.md`、`logging/05-配置讓它真的吐.md`、`logging/06-效能與衛生.md`。本章只講 Nginx 的 `log_format` 與 `$request_id` 怎麼配。
- **超時三件套(connect/send/read)為什麼對應 502/504**:↪ `nginx/04-reverse-proxy-and-upstream.md` 第 4 節(本章把 ch04 點出的「connect→502 / read→504 分水嶺」展開成完整狀態碼診斷)。
- **`$upstream_cache_status` 各值含義、快取相關問題**:↪ `nginx/05-proxy-cache.md` 第 8 節(本章只在 log_format 裡用到它)。
- **`worker_connections` / `worker_rlimit_nofile` / `ulimit` / `somaxconn` 怎麼調、參數聯動**:↪ `nginx/09-performance-tuning.md`(本章只講「耗盡了怎麼定位」,怎麼調在那章)。
- **請求在 Nginx 內部的 phase 模型**(rewrite/access/content,debug log 印的就是它):↪ `gateway/02-request-pipeline.md`、`nginx/01-config-model.md`(`if`/`rewrite` 為何是 rewrite 階段)。
- **訊號與 `USR1` 重開日誌**(配 logrotate 切割):↪ `nginx/08-operations-zero-downtime.md`。
- **引擎內幕**(master-worker/epoll/連線怎麼收):↪ `gateway/01-reverse-proxy-engine.md`(本章不重寫)。

---

## 本章小結

- **先把 Nginx 的眼睛打開**:默認 `combined` 沒有 `$upstream_*`,救火幾乎沒用。生產用 JSON `log_format` 帶上 `$status`/`$request_time`/`$upstream_addr`/`$upstream_status`/`$upstream_connect_time`/`$upstream_response_time`/`$upstream_cache_status`/`$request_id`。
- **`$request_time` − `$upstream_response_time` = Nginx 自身/排隊耗時**:兩者都大 = 後端慢;差值大 = 慢在 Nginx 側(慢客戶端或連線排隊),別冤枉後端。`$upstream_status`=`-` 而 `$status` 是 5xx = Nginx 沒從後端拿到東西(502/504);`$upstream_status` 有具體 5xx = 後端自己回的錯。
- **狀態碼診斷(核心)**:**499**=客戶端先斷(常因後端慢到客戶端不等);**502**=後端拒連/連不上/回非法回應/全熔斷;**504**=後端連上了但沒在 `proxy_read_timeout` 內回完(後端慢/超時配太短);**503**=Nginx 自己擋(限流 `limit_req`/`limit_conn`,或 `upstream` 全熔斷)。499 vs 504 差在「誰先放棄」;502 vs 504 差在「連不上 vs 連上但慢」;502 vs 503 差在「試了連不上 vs 連都不試直接擋」。
- **`stub_status`** 給即時體徵:Active/Reading/Writing/Waiting + accepts/handled/requests;**accepts>handled = 連線被丟棄**(連線耗盡的硬證據)。掛 **nginx-prometheus-exporter** 轉 Prometheus 指標做告警(開源版細粒度指標靠從 access_log 提取)。
- **連線耗盡**:上限 ≈ `worker_processes × worker_connections`,但被 `worker_rlimit_nofile` 和 `ulimit` 卡;反代**每請求佔 2 個 fd**。徵兆:error_log `worker_connections are not enough` / `Too many open files`、stub_status accepts>handled、`$request_time` 大但 upstream_time 小。最常見的配置型根因:`worker_connections` 開大了但 `worker_rlimit_nofile`/`ulimit` 沒跟上。
- **`error_log debug`**(需 `--with-debug`)看單請求走了哪些 phase、`location` 命中哪條;生產用 `debug_connection <IP>` 只對自己的測試 IP 開,查完關掉。
- **`tcpdump`** 抓 Nginx↔後端那段,看後端回的原始位元組(`-A`)、連線被哪方關——「後端說自己沒問題」時的最終仲裁。
- **playbook 表**:看到症狀 → 先看哪個變數 → 收斂根因 → 動手,貼進 runbook 照表走。

---

## 章末問答(複習自檢,答案要點都在前面正文)

1. 默認的 `log_format combined` 為什麼出事時「幾乎沒用」?生產 `log_format` 至少要補哪一組變數?

2. 一個請求 `$request_time=5.0`、`$upstream_response_time=0.05`。慢在哪一側?有哪兩種典型原因?如果反過來 `$request_time≈$upstream_response_time` 且都很大,又該往哪查?

3. 日誌裡 `$upstream_status` 是空(`-`)而 `$status` 是 `502`,和 `$upstream_status` 是 `500`、`$status` 也是 `500`,這兩種分別代表「誰的鍋」?

4. **(逐個說成因)** 用一句話分別說清 499 / 502 / 503 / 504 各是「什麼引起的」。其中 **499 和 504 都是後端慢**,差別在哪?**502 和 504** 差別在哪?

   <details><summary>對答案</summary>

   - **499** = 客戶端在 Nginx 回應前主動斷開(客戶端/上游超時、用戶取消);常因後端慢到客戶端不等了。
   - **502** = Nginx 連不上後端 / 後端拒連 / 後端回了非法回應 / 後端全熔斷——沒從後端拿到合法回應。
   - **503** = Nginx 自己擋:`limit_req`/`limit_conn` 限流,或 `upstream` 全部不可用。
   - **504** = 後端連上了,但沒在 `proxy_read_timeout` 內把回應給完(後端慢,或超時配太短)。
   - **499 vs 504**:都是後端慢,差在**誰先放棄**——客戶端超時 < 後端耗時 → 客戶端先斷 → 499;Nginx 的 `proxy_read_timeout` < 後端耗時(客戶端還在等)→ Nginx 先斷 → 504。
   - **502 vs 504**:502 = **連不上 / 拿到垃圾**(connect 階段失敗或協議錯);504 = **連上了但回得太慢**(read 階段超時)。日誌指紋:502 error_log 是 `connection refused`/`prematurely closed`/`invalid header`;504 是 `upstream timed out ... while reading response header`,且 `$upstream_connect_time` 有值。
   </details>

5. 線上一堆 502。你會先看哪個日誌變數、error_log 裡找哪幾句話來區分「後端掛了 / 後端回非法回應 / 回應頭太大」?

6. `stub_status` 輸出裡 **accepts 和 handled 不相等**(handled 較小)說明什麼?Reading 異常高、Waiting 異常高分別暗示什麼?

7. **(連線耗盡)** error_log 出現 `Too many open files (24)` 和 `worker_connections are not enough`,分別撞到的是哪道閘?反向代理場景「每請求佔 2 個 fd」對 `worker_rlimit_nofile` 的設定有什麼直接影響?定位連線耗盡的「三步」是什麼?

   <details><summary>對答案</summary>

   - `Too many open files (24)` = fd 耗盡,撞的是 `worker_rlimit_nofile` / `ulimit -n` 那道閘;`worker_connections are not enough` = 連線名額(`worker_processes × worker_connections`)耗盡。
   - 反代每請求佔 2 個 fd(客戶端側 + 後端側),所以 `worker_rlimit_nofile` 要 ≥ `worker_connections × 2`,否則連線數還沒到 `worker_connections` 就先撞 fd 上限。
   - 三步:① 看 error_log(哪句話 → 哪道閘);② 看 stub_status(Active 逼近上限、accepts>handled = 連線丟棄);③ 比 `$request_time` vs `$upstream_response_time`(前者大後者小 = 卡在 Nginx 排隊)。
   </details>

8. 什麼時候才該上 `error_log debug` 和 `tcpdump`?各自能看到普通 access_log 看不到的什麼?開 debug 時為什麼要用 `debug_connection`?
