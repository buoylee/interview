# 09 · 性能調優:worker / 連線上限 / sendfile 三件套 / reuseport / 內核聯動 🔬

> 一句話:Nginx 開箱默認值「能跑」,但離「跑好」差一截——差的是把進程、連線、I/O 三條線都和 OS 內核對齊。這章把每個調優參數的「調它影響什麼」講清楚,讓你能看著機器規格直接做出正確決策,而不是把別人的 `nginx.conf` 原樣抄過來。

`sendfile`/`tcp_nopush`/`tcp_nodelay` 的零拷貝原理已在 `03-web-server.md §2` 細講;本章給扼要回顧 + 場景矩陣,重點補「三者協同在調優視角下意味著什麼」。upstream keepalive 連線池的引擎內幕已在 `04-reverse-proxy-and-upstream.md §4` 給了設定,本章補「調它的數字影響什麼」。引擎為什麼快(master-worker、epoll 事件迴圈)不在這裡——那是 `gateway/01-reverse-proxy-engine.md` 的事,本章只教「怎麼調它」。

---

## 1. 🔬 Worker 調優:進程數與核綁定

### 1.1 `worker_processes`:設多少個 worker

```nginx
# main context(設定檔最外層)
worker_processes auto;    # 生產建議值
```

**調它影響什麼**:`worker_processes` 決定 Nginx 啟多少個 worker 進程,每個 worker 是獨立的 OS 進程,單執行緒跑事件迴圈(↪ `gateway/01-reverse-proxy-engine.md` 有 master-worker 模型圖)。設太少——CPU 核心閒置,I/O 密集型流量跑不滿;設太多——進程切換開銷升高、L1/L2 cache miss 增加,反而降吞吐。

**`auto` 等於 CPU 核心數**(Nginx 讀 `/proc/cpuinfo` 或 sysconf `_SC_NPROCESSORS_ONLN`),對純 I/O 密集場景(反代、靜態)是最佳起點。Nginx 的事件迴圈本身不阻塞 CPU,worker 數 = 核心數剛好讓每個核同時跑一個 worker 而不互搶排程時間。

唯一例外:你在 Nginx 層做 CPU 密集的事(比如 OpenResty 跑重度 Lua 計算、大量 TLS 終止時沒有硬體加速),可以試 `worker_processes <核數 × 1.5>` 觀察——但這不是常態,大多數 Nginx 部署 `auto` 就對。

### 1.2 `worker_cpu_affinity`:綁核減 cache miss

```nginx
worker_processes  4;
worker_cpu_affinity 0001 0010 0100 1000;   # 4 個 worker 各綁一個核(每位對應一顆核)

# 或用簡化寫法(Nginx ≥ 1.9.10):
worker_cpu_affinity auto;   # 自動按 worker 數均分核心
```

**調它影響什麼**:不綁核時,OS 調度器按自己的策略把 worker 進程排到任意核心,同一個 worker 可能在不同核之間跳躍。每次跳核,這個進程的 **L1/L2 CPU cache(緩存的 fd 狀態、連線結構體、SSL 上下文)就都失效了**,下一次進核心要重新把熱數據從 L3 或記憶體搬進 L1/L2——稱作 **cache miss**,每次幾十到幾百奈秒不等。

綁核(`worker_cpu_affinity`)把每個 worker 固定在一顆核,它的 cache 不會因為跳核而失效,熱路徑(讀/寫連線緩衝、查 upstream keepalive 池、做 header 改寫)的 cache miss 率顯著下降,P99 延遲縮窄。

**什麼時候值得配**:核數 ≥ 4、QPS 高、對 P99 有要求的生產機器。2 核以下、低負載的開發環境不用配。容器環境裡 cpuset 已被 cgroup 限定,`auto` 綁的核就是 cgroup 允許的那幾個,通常直接用 `auto` 即可。

---

## 2. 🔬 連線上限:三層封頂、哪層先到哪層說了算

這是調優裡**最常踩坑**的地方:三個地方各設一個數,最終可開的連線數由**最小的那個**決定。把三者關係講清楚一次,後面就不用猜了。

### 2.1 `worker_connections`:單 worker 的事件迴圈上限

```nginx
events {
    worker_connections 10240;   # 單個 worker 最多同時處理的連線數
}
```

**調它影響什麼**:`worker_connections` 是 Nginx 事件迴圈的內部限制——epoll 等待隊列裡最多同時掛多少個 fd。設太小,連線數一超就新連線被排隊或拒絕(瀏覽器看到 `Connection reset`);設太大,但 fd 沒跟著放開,實際仍受 OS 封頂(見下)。

**整機最大並發連線數**:

```
整機最大並發連線 = worker_processes × worker_connections
```

**反代場景每連線佔 2 個 fd**:這是最重要的一個計算細節。當 Nginx 做**反向代理**時,每處理一個客戶端連線,它同時要向後端開一條連線——客戶端這邊一個 fd,後端那邊一個 fd,合計 **2 個 fd**。如果 `worker_connections = 10240`,做反代時理論上最多同時接 **5120 個客戶端**(5120 × 2 = 10240 fd)。純靜態服務才是 1:1。

**面試高頻點**:「`worker_connections` 設多少合適?」——先問場景:反代還是靜態。反代的有效客戶端並發 = `worker_connections / 2`。然後看 `worker_rlimit_nofile` 和 OS `ulimit -n`,取三者最小。生產反代通常設 `worker_connections 10240`~`65535`,搭配對應的 fd 上限。

### 2.2 `worker_rlimit_nofile`:Nginx 進程的 fd 上限

```nginx
# main context
worker_rlimit_nofile 65535;   # 單個 worker 進程最多可開的 fd 數
```

**調它影響什麼**:這個值等同於對 worker 進程執行 `setrlimit(RLIMIT_NOFILE, ...)`,即這個進程最多能同時持有多少個打開的文件描述符(連線、日誌、快取文件都消耗 fd)。設定後 master 進程在 fork worker 時傳遞給子進程。

**關係**:`worker_rlimit_nofile` 必須 **≥ `worker_connections`**(且通常要更大,因為還有日誌 fd、快取 fd、listen socket fd 佔用)。一個穩妥的設法:

```
worker_rlimit_nofile = worker_connections × 2 + 一些餘量(例如 1024)
```

**原因**:反代場景每客戶端連線 2 個 fd,`worker_connections` 個槽位全滿時就需要 `worker_connections × 2` 個 fd,再加上日誌和管理 fd,所以 `worker_rlimit_nofile` 至少設到 `worker_connections` 的 2 倍以上。

### 2.3 OS `ulimit -n`:進程級 fd 上限的系統側

```bash
# 查當前 Nginx master 進程的 fd 上限
cat /proc/$(cat /run/nginx.pid)/limits | grep 'open files'

# 臨時提升(重啟失效)
ulimit -n 65535

# 永久生效:編輯 /etc/security/limits.conf
nginx   soft   nofile   65535
nginx   hard   nofile   65535
```

**關係三角(最重要的一張圖)**:

```
OS ulimit -n
  │  Nginx 進程受這個封頂,master fork worker 前先繼承它
  ▼
worker_rlimit_nofile    ← Nginx 設定可以在 ulimit 允許範圍內再收緊或等於它
  │  這是實際傳給 worker 進程的 fd 上限
  ▼
worker_connections      ← Nginx 事件迴圈的內部計數器,不得超過 worker_rlimit_nofile
  │
  ▼
實際可用並發連線 = 三層中最小的那個決定
```

**核心結論**:Nginx 設定改再大,也不能突破 OS 的 `ulimit -n`。生產調優的順序:

1. **先開 OS 層**:在 `/etc/security/limits.conf` 或 systemd unit 的 `LimitNOFILE=` 設足夠大的 fd 上限(常見 65535 或 1048576)。
2. **再設 `worker_rlimit_nofile`**:對齊 OS 上限,或設置所需值。
3. **最後設 `worker_connections`**:根據場景和 fd 上限計算。

> 🔬 systemd 托管的 Nginx:`ulimit -n` 的繼承鏈是 `systemd default → LimitNOFILE in nginx.service → Nginx worker`。`worker_rlimit_nofile` 在 Nginx 啟動後還能覆蓋 inherited rlimit,但不能超過 OS 的 hard limit。所以 `nginx.service` 最好也加 `LimitNOFILE=65535`。

---

## 3. 事件模型:`use epoll`

```nginx
events {
    use epoll;            # Linux 默認,明確寫出來讓意圖清晰
    worker_connections 10240;
}
```

**調它影響什麼**:Nginx 的事件驅動模型選什麼 I/O 多路復用機制。Linux 上 `epoll` 是最優解——O(1) 就緒通知、支援邊緣觸發(edge-triggered),萬級並發連線監控開銷幾乎不隨連線數增長。`select`/`poll` 是 O(n) 的,連線一多性能斷崖。

Linux 新版 Nginx 默認已自動選 `epoll`,明確寫 `use epoll;` 的作用主要是**讓設定意圖可讀、防止未來被意外覆蓋**。macOS/BSD 用 `kqueue`(功能等價),Windows 用 `iocp`。

> ↪ epoll 的內核實現(紅黑樹 + 就緒鏈表、ET vs LT、`epoll_wait` 的 syscall 路徑)深挖 → `performance-tuning-roadmap/00-os-fundamentals/`

---

## 4. 🔬 sendfile / tcp_nopush / tcp_nodelay:三者協同

`03-web-server.md §2` 已把三個指令的原理講透,這裡給**調優視角的扼要回顧 + 場景矩陣**。

### 4.1 三者各管什麼

| 指令 | 開啟後做什麼 | 關掉的後果 |
|---|---|---|
| `sendfile on` | 呼叫 `sendfile(2)` 系統呼叫——資料在內核頁緩存→socket 緩衝區之間搬運,**不過用戶態**,省一次拷貝 | 靜態服務每個 response 多兩次記憶體拷貝 + 兩次 syscall;CPU 和記憶體帶寬多占,高並發時延遲升 |
| `tcp_nopush on` | 設定 socket 的 `TCP_CORK` 選項——**攢滿一個 MSS(最大報文段)再推送**,把多個小寫操作合成一個 TCP 包 | 每次 `write()` 就立刻推送,靜態服務的 HTTP 回應頭和文件正文可能分成多個小包發出,增加包數和網路 overhead |
| `tcp_nodelay on` | 設定 socket 的 `TCP_NODELAY`——**關閉 Nagle 算法**,有數據就立刻發,不等攢 | 開啟 Nagle 時,socket 緩衝區裡有未確認的小包時新數據要等最多 40ms 才發(這正是 Nagle 設計的延遲),對最後一個小包影響明顯 |

### 4.2 三者如何協同

看起來 `tcp_nopush`(攢包)和 `tcp_nodelay`(立刻發)好像衝突,實際上是**兩段接力**:

```
sendfile 把數據推進 socket 緩衝區
  │
  ├─ tcp_nopush(TCP_CORK):緩衝區未滿時攢,讓多個 HTTP 頭/body 片段
  │  合成大包一起發 ← 減少包數和網路 overhead
  │
  └─ 最後一個包(通常 < MSS,緩衝區再等也不會滿了)
      tcp_nodelay(TCP_NODELAY):立刻 flush,不被 Nagle 拖 40ms
```

**Nginx 的行為**:一個 keepalive 連線上,當 `sendfile`/`tcp_nopush` 把文件發送完、需要接著等下一個請求時,Nginx 內部會**切換連線到 `tcp_nodelay` 模式**,確保最後的數據不被 Nagle 卡住。這是 Nginx 幫你做的自動切換,不需要手動控制。

### 4.3 場景矩陣:開哪個?

| 場景 | sendfile | tcp_nopush | tcp_nodelay |
|---|---|---|---|
| **靜態服務(CDN/下載/圖片)**  | ✓ 必開 | ✓ 開(批發包) | ✓ 開(尾包不卡) |
| **反向代理(後端是動態服務)** | 一般關(代理不走磁碟)| 按需 | ✓ 開(互動流量低延遲) |
| **長連線 / WebSocket / SSE** | — | ✗ 關 | ✓ 必開(每幀立刻送) |
| **大文件下載(視頻流)**        | ✓ 開 | ✓ 開 | ✓ 開(尾包) |

**面試高頻點**:「`sendfile`/`tcp_nopush`/`tcp_nodelay` 各幹嘛?」一句話口訣:「`sendfile` 讓資料不過用戶態;`tcp_nopush` 攢滿包再發省包數;`tcp_nodelay` 關 Nagle 讓尾包不等 40ms。靜態服務三個一起開;動態代理重點是 `tcp_nodelay`。」

---

## 5. 🔬 keepalive 調參:客戶端側 + 後端側

keepalive 有**兩個方向**,常被混淆:一個對**客戶端**,一個對**後端**。

### 5.1 對客戶端:`keepalive_timeout` / `keepalive_requests`

```nginx
http {
    keepalive_timeout  65;      # 空閒 keepalive 連線保持多久(秒),超時關閉
    keepalive_requests 1000;    # 一條 keepalive 連線上最多複用多少個請求,達到後主動關閉
}
```

**`keepalive_timeout` 調它影響什麼**:客戶端和 Nginx 之間的 TCP 連線,在一個請求完成後 Nginx 等多久才主動關閉。設太大——空閒連線積累,消耗 fd 和 worker_connections 槽位,高流量時相當於「連線洩漏」;設太小——客戶端每次請求都重新握手,增加延遲和 SYN 開銷。

**`65` 秒是默認值**,對大多數場景合理。如果你的 Nginx 在 LB 後面(已有四層 keepalive),可以縮短到 `15`~`30`。靜態資源服務,瀏覽器通常會多路複用(HTTP/2),`keepalive_requests` 可以放大到 `10000`。

**`keepalive_requests` 調它影響什麼**:防止一條 TCP 連線因為一個客戶端長期複用而積累 fd/資源。到達上限後 Nginx 在回應最後一個請求時加 `Connection: close`,優雅地告知客戶端關閉連線,讓新連線均勻分佈到 worker。默認 `1000`,請求頻率很高(如 API 網關)時可以調到 `10000`。

### 5.2 對後端:`upstream keepalive`

```nginx
upstream backend {
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;

    keepalive 32;     # 每個 worker 對這個 upstream 保持的最大空閒長連線數
}

server {
    location /api/ {
        proxy_pass         http://backend;
        proxy_http_version 1.1;              # HTTP/1.1 才支援 keepalive(必設)
        proxy_set_header   Connection "";    # 清掉 Connection: close(必設)
    }
}
```

**`keepalive 32` 調它影響什麼**:Nginx worker 向後端 upstream 發完請求後,如果有空閒連線,保留在池中供下一個請求複用;如果池滿了,超出的連線才關閉。**每個 worker** 各自維護一個 `keepalive` 大小的連線池,所以整機的後端連線池大小 = `keepalive × worker_processes`。

設太小——仍頻繁建立/銷毀 TCP 連線,四次揮手 + 三次握手的開銷仍在(後端 TIME_WAIT 積累);設太大——後端的 fd 消耗增加,且空閒連線佔用後端線程池或 goroutine。**一個穩妥起點**:`keepalive = worker_connections 的 1/10 ~ 1/5`。

> ↪ upstream keepalive 連線池的引擎內幕(空閒連線怎麼存、複用時怎麼挑、TIME_WAIT 怎麼省)→ `gateway/01-reverse-proxy-engine.md`

---

## 6. 🔬 buffer 調參:太小濺磁碟、太大佔記憶體

buffer 設定控制 Nginx 在內存裡分配多大的緩衝區來暫存請求/回應正文。**調太小**——正文超出緩衝、Nginx 把溢出部分寫到磁碟臨時文件(disk spill),延遲激增;**調太大**——每個連線都分配大塊內存,高並發時 OOM 或 swap。

### 6.1 `client_body_buffer_size`:接收客戶端請求正文

```nginx
http {
    client_body_buffer_size  128k;   # 默認 8k(32位) / 16k(64位)
    client_max_body_size      50m;   # 允許的最大請求體(超過返回 413)
}
```

**調它影響什麼**:客戶端 POST/PUT 的請求正文先放在這塊緩衝。超出 `client_body_buffer_size` 但未超出 `client_max_body_size` 時,Nginx 把溢出部分**臨時寫到磁碟**(`/var/lib/nginx/body/` 之類的 `client_body_temp_path`)。磁碟寫入是同步的,會卡住 worker。

調大 `client_body_buffer_size` 讓**小/中型請求(表單、JSON API、文件上傳)完全在記憶體裡處理**,避免磁碟 spill。但不要設得比典型請求正文大太多——多數 API 請求 < 64k,設 `128k` 通常夠;文件上傳場景另行調。

### 6.2 `proxy_buffers` / `proxy_buffer_size`:緩衝後端回應

```nginx
http {
    proxy_buffer_size   8k;      # 接收後端回應「頭部」的第一個緩衝大小
    proxy_buffers      16 8k;    # 接收後端回應「正文」的緩衝塊數和每塊大小
    proxy_busy_buffers_size 16k; # 向客戶端發送時,同時可用的緩衝上限(≥ proxy_buffer_size)
}
```

**調它影響什麼**:

- **`proxy_buffer_size`**:後端回應的 HTTP 頭部先進這個緩衝。默認 `4k` 對大多數回應頭夠,但有些應用在回應頭裡塞大量 `Set-Cookie` 或自定義 header,超出時 Nginx 報 `upstream sent too big header while reading response header from upstream`(502)。遇到這個錯誤把 `proxy_buffer_size` 翻倍到 `16k` 通常解決。

- **`proxy_buffers`**:後端回應正文的緩衝。`16 8k` = 16 塊、每塊 8k = 最多 128k。Nginx 把後端回應積攢到緩衝後再送給客戶端,讓後端的連線可以早點結束(後端 worker 不用一直等慢客戶端接收)。設太小——後端回應超出緩衝時,要麼 Nginx 同步等客戶端消費(佔住後端連線),要麼同樣 spill 到磁碟;設太大——高並發時每個連線都分配大塊、記憶體壓力大。

- **`proxy_buffering off`**:關掉緩衝,Nginx 拿到後端數據立刻往客戶端發。適合 **Server-Sent Events / 流式回應 / 大文件流**場景——緩衝在這裡反而增加延遲。

### 6.3 `large_client_header_buffers`:大請求頭

```nginx
http {
    large_client_header_buffers 4 16k;  # 默認 4 8k
}
```

**調它影響什麼**:客戶端請求行或請求頭超出默認緩衝(`client_header_buffer_size`,默認 1k)時,Nginx 分配這裡定義的額外緩衝。常見於帶大量 Cookie 或 JWT Token 的請求——JWT 可能幾 KB,加上其他 header 輕易超過默認 `8k`。超出時 Nginx 返回 `414 Request-URI Too Large` 或 `400 Bad Request`。把 `large_client_header_buffers 4 16k;` 調到 `4 32k;` 或 `8 16k;` 通常解決。

---

## 7. 🔬 `accept_mutex` vs `reuseport`:誰來分發新連線

這是**驚群問題(thundering herd)**的解法演進,也是面試喜歡問「Nginx 多 worker 怎麼分配連線」的核心知識點。

### 7.1 問題:新連線到來時所有 worker 同時被喚醒

Linux 老內核上,多個進程同時 `accept()` 監聽同一個 listen socket,當有新連線到來,**所有在 `accept()` 上睡眠的 worker 都被喚醒**——但最終只有一個能搶到連線,其他的白白被喚醒、白白消耗 CPU 和上下文切換——這就是**驚群(thundering herd)**。

### 7.2 `accept_mutex`(老方案,Nginx 自己做序列化)

```nginx
events {
    accept_mutex on;    # Nginx ≥ 1.11.3 默認 off(更早版本默認 on);現代搭 reuseport 更佳
}
```

**調它影響什麼**:`accept_mutex on` 時,worker 在嘗試 `accept()` 之前先搶一把互斥鎖(存在共享記憶體裡),搶到鎖的那個才去 `accept()`,其他 worker 不會被喚醒——驚群沒了,但**鎖本身有競爭開銷**,且同一時刻只有一個 worker 在 accept,在連線建立速率很高時可能成為瓶頸。

現代 Nginx(≥ 1.11.3)的默認是 `accept_mutex off`,搭配 `reuseport` 才是推薦方案。

### 7.3 `reuseport`(新方案,讓內核分發)

```nginx
server {
    listen 80 reuseport;    # 每個 worker 各自獨立監聽同一端口
    listen 443 ssl reuseport;
}
```

**調它影響什麼**:`SO_REUSEPORT` 是 Linux 3.9+ 的 socket 選項,讓多個進程各自 `bind()` 相同的 IP:port——內核為**每個 worker 維護一個獨立的 accept 隊列**,新連線到來時內核按負載均衡策略把它分到某個 worker 的隊列,**只喚醒那一個 worker**。

效果:

- **驚群問題從內核層消除**——不再有多 worker 搶同一連線。
- **多核分發更均衡**——每個 worker 的 accept 隊列獨立,避免某個 worker 特別忙時其他 worker 的隊列卻空著。
- **省掉 `accept_mutex` 的鎖競爭**——內核做的分發沒有用戶態鎖開銷。
- **代價**:連線分發在內核完成,如果某個 worker 阻塞(例如 OpenResty Lua 的同步調用),它的隊列會積壓而不能被其他 worker 搶救。`accept_mutex` 下,搶鎖失敗的 worker 會去處理已有連線,等等再來搶。

**生產建議**:Linux 內核 ≥ 3.9 的現代環境一律用 `listen 80 reuseport;`,比 `accept_mutex` 在高 QPS 場景下吞吐更高、延遲更低。

> ↪ 驚群問題的內核機制詳解、`reuseport` 的內核實現 → `gateway/01-reverse-proxy-engine.md`

---

## 8. 🔬 內核聯動:Nginx 設定再大也受內核封頂

Nginx 的調優不是孤立的——**它的每個設定都有對應的 OS 內核參數作為上界**,Nginx 設定超過內核上界時多餘的部分被靜默截掉。一張表把關鍵聯動說清楚:

### 8.1 `net.core.somaxconn` 與 `listen backlog`

```nginx
listen 80 backlog=65535;    # Nginx 這端 listen socket 的 backlog 大小
```

```bash
# 內核參數:全局 listen backlog 上限
sysctl -w net.core.somaxconn=65535
# 永久:echo 'net.core.somaxconn = 65535' >> /etc/sysctl.d/99-nginx.conf && sysctl -p
```

**聯動關係**:

- `listen backlog` 是告訴內核「為這個 listen socket 的**半連線 + 全連線隊列**分配多大容量」。
- **內核限制**:`net.core.somaxconn` 是系統全局上限。如果 Nginx 設 `backlog=65535` 但 `net.core.somaxconn=128`(很多 Linux 發行版默認值),內核會把 backlog **悄悄截到 128**,Nginx 看不到報錯,SYN 洪峰或連線建立高峰時隊列滿 → 新 SYN 被直接丟棄 → 客戶端重傳 → 延遲。

**現象**:在 `nginx error_log` 裡看到 `connect() failed (111: Connection refused)` 或監控發現 SYN 重傳率高,很可能是 backlog 被 `somaxconn` 截斷了。

### 8.2 `tcp_max_syn_backlog`:SYN 半連線隊列

```bash
sysctl -w net.ipv4.tcp_max_syn_backlog=65535
```

**聯動關係**:`somaxconn` 控制 `listen()` 呼叫的全連線隊列;`tcp_max_syn_backlog` 控制在 SYN 收到但 ACK 尚未收到時的**半連線隊列**上限。流量洪峰或 SYN flood 攻擊時,半連線隊列滿了 → 新 SYN 丟棄 → 合法用戶看到連線超時。一般設定為 `somaxconn` 同量或更大。

### 8.3 檔案描述符上限:OS 的最後一道封頂

```bash
# 查系統全局 fd 上限
cat /proc/sys/fs/file-max

# 提升
sysctl -w fs.file-max=2097152
```

**聯動關係**:

```
fs.file-max(系統全局總 fd 數)
  └── ulimit -n(進程級 hard limit)
        └── worker_rlimit_nofile(Nginx 設定覆蓋 soft limit)
              └── worker_connections(事件迴圈內部計數)
```

`fs.file-max` 是整台機器所有進程可以持有的 fd 總數。現代 Linux 默認值通常 `1048576` 或更高(可用 `cat /proc/sys/fs/file-max` 確認),一般不是瓶頸,但在容器化或資源受限環境需確認。

### 8.4 一張表:調優前的 OS 必改項

| 內核參數 | 建議值 | 對應 Nginx 設定 | 如果沒改的症狀 |
|---|---|---|---|
| `net.core.somaxconn` | 65535 | `listen ... backlog` | 流量峰值 SYN 丟包、client 超時 |
| `net.ipv4.tcp_max_syn_backlog` | 65535 | — | SYN flood 或突發連線被截 |
| `ulimit -n` / `LimitNOFILE` | 65535+ | `worker_rlimit_nofile` | `too many open files` 錯誤,連線建立失敗 |
| `fs.file-max` | 1048576 | — | 整機 fd 耗盡(少見,但容器內要確認) |
| `net.ipv4.tcp_tw_reuse` | `1` | — | TIME_WAIT 積累佔 fd,影響 upstream 連線 |

> ↪ `net.core.somaxconn`/`tcp_max_syn_backlog`/`tcp_tw_reuse` 等 TCP 內核參數的深挖、調整方法與排查 → `performance-tuning-roadmap/00-os-fundamentals/`

---

## 9. 一份生產調優基礎模板

把上面所有點串成一份可以直接貼上機器的最小模板,每行都附「為什麼」注釋:

```nginx
# ── 進程 ──────────────────────────────────────────────────────────
worker_processes  auto;                 # = CPU 核數,epoll 不阻塞核心
worker_cpu_affinity auto;               # 綁核減 cache miss(核數 ≥ 4 時有效)
worker_rlimit_nofile 65535;             # worker 的 fd 上限,≥ worker_connections × 2

events {
    use epoll;                          # Linux 最優事件模型
    worker_connections 10240;           # 單 worker 最大並發;反代實際客戶端 ÷2
    # accept_mutex off;                 # 默認 off;用 reuseport 後更好(見 listen 行)
}

http {
    # ── 連線 ──────────────────────────────────────────────────────
    keepalive_timeout  65;              # 客戶端空閒連線保持時間
    keepalive_requests 1000;            # 防止單條連線長期獨佔

    # ── 靜態服務 I/O ──────────────────────────────────────────────
    sendfile    on;                     # 零拷貝靜態服務必開
    tcp_nopush  on;                     # 攢包減包數(配合 sendfile)
    tcp_nodelay on;                     # 關 Nagle,尾包不等 40ms

    # ── Buffer ────────────────────────────────────────────────────
    client_body_buffer_size   128k;     # 防小/中型請求 spill 到磁碟
    client_max_body_size      50m;      # 超過返回 413
    client_header_buffer_size   2k;     # 常規請求頭
    large_client_header_buffers 4 16k;  # 大 Cookie / JWT 場景

    proxy_buffer_size   8k;             # 後端回應頭緩衝(大 header 調到 16k)
    proxy_buffers      16 8k;           # 後端回應正文緩衝(共 128k)
    proxy_busy_buffers_size 16k;

    # ── upstream(在 upstream 區塊裡配) ────────────────────────────
    # upstream backend {
    #     server ...;
    #     keepalive 32;                 # 每 worker 保持的空閒後端連線數
    # }

    server {
        listen 80 reuseport;            # reuseport:內核分發連線,消驚群
        # listen 443 ssl reuseport;
        ...
    }
}
```

**OS 側調優(在機器/容器啟動前完成)**:

```bash
# /etc/sysctl.d/99-nginx.conf
net.core.somaxconn        = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_tw_reuse     = 1
fs.file-max               = 1048576

# /etc/security/limits.conf 或 systemd nginx.service 的 LimitNOFILE
nginx  soft  nofile  65535
nginx  hard  nofile  65535
```

---

## 交叉引用

- **epoll 事件模型的內核實現(就緒列表、ET vs LT、`epoll_wait` 路徑)、TCP 內核參數(`somaxconn`/`tcp_max_syn_backlog`/`tcp_tw_reuse`)的深挖與排查** → ↪ `performance-tuning-roadmap/00-os-fundamentals/`
- **驚群問題(thundering herd)的內核機制、`reuseport` 的 `SO_REUSEPORT` 實現細節、master-worker 模型與 accept 競爭** → ↪ `gateway/01-reverse-proxy-engine.md`
- **`sendfile(2)` 零拷貝的完整原理(syscall 路徑、DMA scatter-gather)** → ↪ `nginx/03-web-server.md §2`(已細講)
- **upstream keepalive 連線池的引擎內幕(空閒池管理、TIME_WAIT 消除、`proxy_http_version 1.1` 為什麼必設)** → ↪ `gateway/01-reverse-proxy-engine.md`、`nginx/04-reverse-proxy-and-upstream.md §4`
- **可觀測性:連線耗盡的徵兆(`stub_status` active/waiting)、error_log 裡的 `worker_connections are not enough`** → ↪ `nginx/10-observability-debugging.md`

---

## 本章小結

- **`worker_processes auto`** = CPU 核數,I/O 密集場景的最佳起點。**`worker_cpu_affinity auto`** 綁核減 cache miss,核數 ≥ 4 有明顯收益。
- **三層 fd 封頂**:OS `ulimit -n` → `worker_rlimit_nofile` → `worker_connections`。Nginx 設定再大也不能突破 OS 上限。反代場景每客戶端連線佔 2 fd,`worker_connections` 有效客戶端並發 = `worker_connections / 2`。
- **`use epoll`** Linux 上最優;`reuseport` 讓內核分發連線,比 `accept_mutex` 在高 QPS 下吞吐更高、不驚群。
- **sendfile + tcp_nopush + tcp_nodelay 三件套**:靜態服務三個全開。`sendfile` 零拷貝進 socket、`tcp_nopush` 攢滿包再發、`tcp_nodelay` 確保尾包不被 Nagle 卡 40ms。
- **keepalive 兩個方向**:客戶端 `keepalive_timeout`(空閒保持時間)+ `keepalive_requests`(連線請求數上限)防單連線壟佔;upstream `keepalive`(每 worker 空閒後端連線池大小)+ 必須搭 `proxy_http_version 1.1` + 清 `Connection` 頭。
- **buffer 三原則**:太小 spill 到磁碟(延遲激增);太大高並發時 OOM;遇 `413`/`400` 先看 `client_body_buffer_size`/`large_client_header_buffers`;遇後端 502「big header」先調 `proxy_buffer_size`。
- **內核封頂必改**:`net.core.somaxconn` 和 `tcp_max_syn_backlog` 決定 listen 隊列深度;`ulimit -n` 和 `fs.file-max` 決定 fd 上限——Nginx 設定超過這些值會被靜默截斷,症狀是 SYN 丟包和 `too many open files`。

---

## 章末問答(複習自檢,答案要點都在前面正文)

<details>
<summary>1. 一台 8 核機器、Nginx 做反向代理、設 <code>worker_processes auto; worker_connections 10240;</code>,這台 Nginx 最多能同時服務多少個客戶端請求?為什麼不是 8 × 10240 = 81920?</summary>

做反向代理時每個客戶端連線佔 2 個 fd(一個接客戶端、一個連後端),所以單 worker 的有效客戶端並發 = `worker_connections / 2` = 5120。8 個 worker 合計 8 × 5120 = **40960 個客戶端**。81920 是「靜態服務純 1:1 fd 場景」的上限,反代不適用。
</details>

<details>
<summary>2. <code>worker_connections = 10240</code>、<code>worker_rlimit_nofile</code> 忘了設、OS <code>ulimit -n = 1024</code>,實際上這個 worker 能開幾個連線?為什麼?</summary>

最多只能開 **1024** 個 fd(含連線 fd + 日誌 fd + listen fd)。`worker_rlimit_nofile` 沒設時繼承 OS 的 `ulimit -n = 1024`——這是進程的 fd 硬上限,Nginx 的 `worker_connections` 是內部計數器,不能突破 OS 的 rlimit。實際可開連線數遠少於 1024(日誌、socket、listen fd 都佔 fd)。
</details>

<details>
<summary>3. <code>tcp_nopush on</code> 和 <code>tcp_nodelay on</code> 看起來一個攢包、一個立刻發,豈不是互相矛盾?它們是怎麼協同工作的?</summary>

兩者針對不同階段:sendfile 把文件推進 socket 緩衝區期間,`tcp_nopush`(TCP_CORK)把多個小片段攢成大包批量發,減少包數和 overhead。當文件發送完、緩衝區剩最後一小塊(< MSS,等不到填滿了),`tcp_nodelay`(關閉 Nagle)讓這個尾包立刻 flush,不被 Nagle 算法強制等最多 40ms。Nginx 在發完文件後內部切換連線到 `tcp_nodelay` 模式自動完成這個切換。兩者時序上是「前期攢包、末尾立刻 flush」,不衝突。
</details>

<details>
<summary>4. 為什麼 <code>listen 80 reuseport;</code> 比 <code>accept_mutex on</code> 更好?各自解決驚群的方式有什麼本質差異?</summary>

`accept_mutex` 在用戶態做序列化:worker 搶鎖,搶到才 `accept()`——解決了驚群但引入鎖競爭、且同一時刻只有一個 worker 在接受連線,高 QPS 時 accept 成為瓶頸。`reuseport(SO_REUSEPORT)` 讓內核為每個 worker 建立獨立的 accept 隊列,新連線在內核分發時**只喚醒目標 worker**,既沒有驚群也沒有用戶態鎖競爭,且多核分發更均衡。本質差異:`accept_mutex` 是「大家都能搶但一次只讓一個去接」,`reuseport` 是「內核事先分好、你的隊列裡才叫你」。
</details>

<details>
<summary>5. 設了 <code>listen 80 backlog=65535;</code>,壓測時仍發現 SYN 超時。排查步驟是什麼?最可能的內核參數根因是什麼?</summary>

排查步驟:① `sysctl net.core.somaxconn` 確認是否被截斷(默認 128);② `ss -lnt sport = :80` 看 `Recv-Q`(半連線積壓);③ `netstat -s | grep SYNs` 看 SYN 丟包計數。最可能根因:`net.core.somaxconn` 太小——Nginx 設的 `backlog=65535` 被內核靜默截到 `somaxconn` 的值(如 128),導致流量峰值時 listen 隊列滿、新 SYN 被丟棄、客戶端重傳 → 超時。修復:`sysctl -w net.core.somaxconn=65535`(同時調 `tcp_max_syn_backlog`),並寫入 `/etc/sysctl.d/` 永久生效。
</details>

<details>
<summary>6. upstream 設 <code>keepalive 32;</code> 但忘了加 <code>proxy_http_version 1.1;</code> 和 <code>proxy_set_header Connection "";</code>,結果是什麼?</summary>

HTTP/1.0 默認每個請求後關閉連線(`Connection: close`),`keepalive 32` 設定的連線池形同虛設——每次請求完成後連線都被關閉,Nginx 仍要為每個請求重新三次握手,TIME_WAIT 積累。`proxy_http_version 1.1;` 升到支援 keepalive 的協議;`proxy_set_header Connection "";` 清掉客戶端可能傳來的 `Connection: close` 頭(否則這個頭會被透傳給後端,後端照樣關連線)。兩者缺一不可。
</details>
