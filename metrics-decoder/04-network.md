# 網路指標逐欄解碼 —— `ss` 的連線狀態 / `Recv-Q Send-Q` / `retrans`

> 你打 `ss -tan` 看到一排 `ESTAB` / `TIME-WAIT` / `CLOSE-WAIT` 和兩欄 `Recv-Q Send-Q`——最坑的是 **`Recv-Q`/`Send-Q` 在不同狀態下意思完全不同**,還有 **`TIME-WAIT` 一大堆你以為出事了,其實多半正常**。這份拆開網路那幾欄,核心:**看狀態分佈定位問題、`Recv-Q`/`Send-Q` 認清語境、`retrans` 才是丟包鐵證。**

---

## ① 逐欄解碼表

### TCP 連線狀態(`ss -tan` 第一欄)

| 狀態 | 意思 | 一堆代表什麼 | 原語 |
|------|------|--------------|------|
| `ESTAB` | 已建立,正在通信 | 正常 | [A](#原語-atcp-連線狀態機握手--揮手) |
| `LISTEN` | 在監聽等連入 | 正常(你的服務) | [B](#原語-bsocket-佇列recv-qsend-q-的雙重身分) |
| `TIME-WAIT` | **主動關閉方**關完的等待期 | **大量短連接**(多半正常,但見原語 D) | [A](#原語-atcp-連線狀態機握手--揮手) · [D](#原語-dtime_wait-堆積為什麼別急著調內核參數) |
| `CLOSE-WAIT` | 對端關了,**你還沒 close()** | ⚠️ **應用 bug**:忘了關 fd | [A](#原語-atcp-連線狀態機握手--揮手) |
| `SYN-SENT`/`SYN-RECV` | 握手中 | 大量 SYN-RECV = 可能 SYN flood | [A](#原語-atcp-連線狀態機握手--揮手) |
| `FIN-WAIT-1/2` | 揮手中 | 偶見正常 | [A](#原語-atcp-連線狀態機握手--揮手) |

### `Recv-Q` / `Send-Q`(⚠️ 看狀態決定含義)

| 在哪個狀態 | `Recv-Q` | `Send-Q` | 原語 |
|------------|----------|----------|------|
| `ESTAB`(已連線) | 已收到、**應用還沒 read** 的位元組 | 已送出、**對端還沒 ACK** 的位元組 | [B](#原語-bsocket-佇列recv-qsend-q-的雙重身分) |
| `LISTEN`(監聽) | **當前 accept 佇列**長度(握手完、等 accept) | **backlog 上限** | [B](#原語-bsocket-佇列recv-qsend-q-的雙重身分) |

### `ss -ti` 的傳輸細節(每連線)

| 欄 | 意思 | 看點 | 原語 |
|----|------|------|------|
| `rtt` | 往返時間(ms) | 鏈路延遲 | [C](#原語-c重傳--擁塞控制rtt-cwnd-retrans) |
| `cwnd` | 擁塞視窗(可在飛的段數) | 丟包會被砍 | [C](#原語-c重傳--擁塞控制rtt-cwnd-retrans) |
| `retrans` | 重傳次數 | **丟包鐵證** | [C](#原語-c重傳--擁塞控制rtt-cwnd-retrans) |

### 去哪看

```bash
ss -s                    # 總覽:各協議連線數、estab/timewait/closed
ss -tan                  # 所有 TCP 連線 + 狀態 + Recv-Q/Send-Q(-n 不解析域名,快)
ss -tan state time-wait | wc -l        # 數某個狀態
ss -tin                  # 加傳輸資訊(rtt/cwnd/retrans)
ss -ltn                  # 只看 LISTEN(查 backlog 用 Send-Q)
netstat -s | grep -i retrans           # 全機重傳統計
```

真機狀態分佈(本次容器,curl 打本地 server 200 次後):
```
$ ss -tan | awk 'NR>1{print $1}' | sort | uniq -c
    202 TIME-WAIT          ← 每次 curl 是新短連接、client 主動關 → 各留一個 TIME-WAIT
      1 LISTEN
```

---

## ② 原語黑盒

### 原語 A:TCP 連線狀態機(握手 + 揮手)

**① 你視角**
你 `curl` 一個網址,背後 TCP 要先**三次握手**建連、傳完數據再**四次揮手**拆連。`ss` 看到的每個狀態,都是這條狀態機上的一個停留點。

**② 黑盒內部**
- **建連(三次握手)**:`SYN →`、`← SYN-ACK`、`ACK →`。中間態 `SYN-SENT`(client)/`SYN-RECV`(server),成功後雙方 `ESTAB`。
- **拆連(四次揮手)**:**主動關閉方**發 `FIN`,經 `FIN-WAIT` → 最後進 **`TIME-WAIT`**。被動方收 `FIN` 後進 **`CLOSE-WAIT`**,等自己 `close()` 才發 `FIN`。

兩個高頻信號:
- **`TIME-WAIT`**:**主動關閉的一方**才會進。它要等 **2×MSL**(Linux 約 60s)才消失,目的:① 確保自己最後的 ACK 對端收到;② 讓這條連線的迷途舊封包過期,不污染之後同「四元組」的新連線。所以**誰主動關,誰背 TIME-WAIT**。
- **`CLOSE-WAIT`**:對端已經關了、輪到你 `close()`,但你**遲遲沒關**。一堆 `CLOSE-WAIT` = **你的應用忘了關連線 / 連線洩漏**,是程式 bug,不是網路問題。

**③ 砸實**
本次 200 個 `curl` 各開一條短連接、用完 **client 主動關** → 留下 **202 個 `TIME-WAIT`**(client 側)。這正是「大量短連接 → TIME-WAIT 堆積」的典型(見原語 D)。

---

### 原語 B:socket 佇列(`Recv-Q`/`Send-Q` 的雙重身分)

**① 你視角**
同樣兩欄 `Recv-Q`/`Send-Q`,在「已連線」和「監聽」兩種 socket 上**根本是兩回事**。看錯語境就誤判。

**② 黑盒內部**

**已連線(`ESTAB`)的 socket**——兩欄是**數據緩衝**:
- `Recv-Q` = 內核已收到、但**應用還沒 `read()` 取走**的位元組。持續很高 = **應用消費太慢**(處理不過來)。
- `Send-Q` = 應用已送出、但**對端還沒 ACK 確認**的位元組。持續很高 = 對端慢 / 網路堵。

**監聽(`LISTEN`)的 socket**——兩欄是**連線佇列**:
- `Recv-Q` = **當前 accept 佇列**裡的連線數(三次握手已完成、等你的應用 `accept()` 取走)。
- `Send-Q` = 這個監聽 socket 的 **backlog 上限**。

當 `accept` 跟不上(應用太忙),accept 佇列(LISTEN 的 Recv-Q)漲到滿(= Send-Q)→ **新連線被丟棄或拒絕**,client 看到連線超時 / 重傳。這就是「backlog 打滿」。

**③ 砸實**
本次監聽 socket:
```
State   Recv-Q  Send-Q  Local Address:Port
LISTEN  0       5       0.0.0.0:8000        ← Send-Q=5 是 backlog 上限(python http.server 預設)
                                              Recv-Q=0 = 此刻沒有積壓的待 accept 連線
```
若 `Recv-Q` 逼近 `Send-Q`,就是 accept 來不及、佇列要滿了。

---

### 原語 C:重傳 + 擁塞控制(`rtt` `cwnd` `retrans`)

**① 你視角**
網路「慢」,是延遲高(rtt)、還是在丟包(retrans)?這決定你查網路還是查對端。

**② 黑盒內部**
- `rtt` = 一個來回的時間,反映鏈路延遲(跨地域、繞路會高)。
- `cwnd`(擁塞視窗)= TCP 自己估算「現在能同時在飛多少段而不塞爆網路」。它**隨確認慢慢長大、一遇丟包就猛砍**(擁塞控制)。
- `retrans` = 重傳次數。TCP 發出去的段沒等到 ACK(超時或收到重複 ACK)就**重傳**——這是**丟包的直接證據**。

連起來:丟包 → `retrans` 升 → `cwnd` 被砍 → 能在飛的數據變少 → 吞吐掉。所以 **`retrans` 持續非零 = 網路在丟包**,該查鏈路 / 對端 / 中間設備。

**③ 砸實(誠實:本次沒抓到活連線)**
本次 `curl` 連線太短暫,`ss -tin` 執行時連線已關,抓到空。真機看一條長連接(如資料庫連線池、長輪詢):
```bash
ss -tin
# ESTAB ...  rtt:0.25/0.1 cwnd:10 ... retrans:0/3   ← retrans 後面那個數持續漲 = 在丟包
```

---

### 原語 D:TIME_WAIT 堆積(為什麼別急著調內核參數)

**① 你視角**
你看到幾萬個 `TIME-WAIT`,網上一搜全教你改 `tcp_tw_reuse`/`tcp_tw_recycle`。**先別。**

**② 黑盒內部**
`TIME-WAIT` 堆積的**根因幾乎都是「大量短連接」**:每次請求開一條新 TCP、用完就關,每條都在主動關閉方留一個 60s 的 `TIME-WAIT`。高 QPS 下瞬間幾萬個,還可能耗盡本地端口(端口範圍有限)。

正確解法的**優先級**:
1. **用連線池 / 長連接複用**(HTTP keep-alive、DB 連接池)——從源頭不再每請求一條新連線。這是治本。
2. 真有大量短連接無法避免時,才考慮調 `net.ipv4.tcp_tw_reuse=1`(安全,讓本地端口能更快複用)。
3. ⚠️ `tcp_tw_recycle` **早已被移除/不要用**(NAT 環境下會錯誤丟連線)。

**TIME_WAIT 是 TCP 的正常設計,不是病。** 把它當「短連接太多」的信號,去查為什麼不用連接池。

**③ 砸實**
本次 202 個 `TIME-WAIT` 就是「200 次獨立 `curl`(每次新連接)」造出來的——換成 `curl` 帶 keep-alive 復用一條連接,`TIME-WAIT` 會驟降。這就是連接池的價值。

---

## ③ 決策樹收口

```
連線 / 網路問題
│
├─ ss -s 看總量與狀態分佈
│   ├─ TIME-WAIT 一大堆     → 大量短連接      → 上連接池 / keep-alive(別先調內核)  [原語 D]
│   ├─ CLOSE-WAIT 一大堆    → 應用忘了 close()→ 修連線洩漏 bug                       [原語 A]
│   └─ SYN-RECV 一大堆      → 半連接堆積       → 可能 SYN flood / backlog 小          [原語 A·B]
│
├─ 連不上 / 偶爾超時
│   └─ ss -ltn 看 LISTEN 的 Recv-Q 是否逼近 Send-Q → accept 跟不上 / backlog 太小    [原語 B]
│
├─ 連上但慢
│   ├─ ESTAB 的 Recv-Q 持續高 → 應用 read 太慢(消費不過來)                          [原語 B]
│   ├─ ESTAB 的 Send-Q 持續高 → 對端慢 / 網路堵                                       [原語 B]
│   └─ ss -tin 看 retrans     → 持續漲 = 丟包,查鏈路 / 對端                          [原語 C]
```

> 一句心法:**先看狀態分佈定性,`Recv-Q`/`Send-Q` 認清是連線佇列還是數據緩衝,`retrans` 才是丟包證據。**

---

## ④ 面試複習(只自檢)

1. `TIME-WAIT` 為什麼存在?是主動關閉方還是被動方進入?幾萬個怎麼辦?
2. 一堆 `CLOSE-WAIT` 代表什麼問題?該查哪裡?
3. `LISTEN` socket 的 `Recv-Q` 和 `Send-Q` 各是什麼?`ESTAB` 的又是什麼?
4. `ESTAB` 連線的 `Recv-Q` 一直很高,問題在哪一端?
5. `ss -tin` 的 `retrans` 持續非零說明什麼?

<details>
<summary>對答案</summary>

1. 主動關閉方進入,等 2×MSL(約 60s)確保末 ACK 送達 + 舊封包過期。幾萬個的根因是大量短連接 → 上連接池/keep-alive 治本,別先調內核(`tcp_tw_recycle` 更是別碰)。
2. 對端已關、你的應用沒 `close()` → 連線/fd 洩漏,是程式 bug。查哪裡漏關 socket。
3. LISTEN:Recv-Q=當前 accept 佇列長度,Send-Q=backlog 上限。ESTAB:Recv-Q=收到但應用沒讀的位元組,Send-Q=送出但對端沒 ACK 的位元組。
4. 本端(收的一方):應用 `read()` 消費太慢,數據堆在內核接收緩衝。
5. 在丟包。TCP 沒收到 ACK 觸發重傳,cwnd 被砍、吞吐下降;該查鏈路/對端/中間設備。

</details>

---

## 回鏈

- **TCP 狀態 / 擁塞控制 / TIME_WAIT 原理** → [`../performance-tuning-roadmap/00-os-fundamentals/04a-network-tcp-core.md`](../performance-tuning-roadmap/00-os-fundamentals/04a-network-tcp-core.md)
- **Socket buffer / 內核收發包 / backlog** → [`../performance-tuning-roadmap/00-os-fundamentals/04b-network-socket-kernel.md`](../performance-tuning-roadmap/00-os-fundamentals/04b-network-socket-kernel.md)
- **動手:連線、丟包、TLS、超時** → [`../linux-handson/06-networking`](../linux-handson/06-networking/)
- **網路排查命令反查** → [`../cli-toolbox/03-network-triage.md`](../cli-toolbox/03-network-triage.md)
- 上一章 [03 磁碟 IO](./03-disk-io.md) · 回 [README](./README.md)
