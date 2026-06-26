# 03 · 網路排查

> 「連不上某服務」「端口被誰佔了」「DNS 解不出」——這章教你**沿著網路路徑一段段往下問**,而不是在某一層死磕。

---

## 收口地圖(記這條鏈,別背工具)

網路排查的本質是:**一個請求要經過好幾層,逐層確認「到這還通嗎」**,通的往下走,斷的就抓出來。

```
本機端口開了嗎 ──► DNS 解得出嗎 ──► 連得通嗎(L3/L4)──► 應用層回應嗎(L7)──► 中間誰丟包/慢
   ss / lsof          dig / getent        ping / nc           curl              tcpdump / mtr
```

**按層配工具(記這張對應就夠)**:

| 層 | 問題 | 工具 |
|---|---|---|
| 本機 | 端口開了沒?誰佔的?連去哪? | `ss` / `lsof -i` |
| L3 連通 | 主機通不通?路徑哪卡? | `ping` / `mtr` |
| L4 端口 | TCP 端口通不通?(不管應用) | `nc -zv` |
| DNS | 域名解得對嗎? | `dig` / `getent` |
| L7 應用 | 服務到底回什麼? | `curl -v` |
| 真相 | 線上到底發了什麼包? | `tcpdump` |

---

## 1. 端口與連接:`ss`(取代老 `netstat`)

| 命令 | 作用 | 底層一兩句 |
|---|---|---|
| 🔧 `ss -tlnp` | 看本機在**監聽**哪些 TCP 端口 + 哪個進程 | `t`=tcp `l`=listening `n`=數字(不反解) `p`=進程 |
| `ss -tnp` | 看**已建立**的 TCP 連接 | 排查「連去了哪、誰連我」 |
| `ss -s` | 連接狀態**摘要** | 一眼看各狀態總數(TIME_WAIT 爆了一目了然) |
| `ss -tn state time-wait` | 按**連接狀態**過濾 | `ss` 比 `netstat` 強的地方:能 filter |
| `lsof -i :8080` | **誰佔了 8080** | 「端口被佔」最快查法 |
| `netstat -tlnp` | 老機器沒 `ss` 時的等價物 | 知道即可,新機一律用 `ss` |

**連接狀態的兩個面試點**(都看 `ss -tn`):

- **大量 `TIME_WAIT`**:出現在**主動關閉**的一方,**正常現象**(等 2×MSL 確保舊包消散)。量大通常是**短連接太多** → 上連接池 / keep-alive。
- **大量 `CLOSE_WAIT`**:出現在**被動關閉**的一方,**幾乎一定是 bug** —— 對端關了,你的應用**沒呼叫 `close()`**。連接洩漏,查程式碼。

> macOS 注意:**沒有 `ss`**。mac 上用 `lsof -i -nP` 或 `netstat -an`。

---

## 2. 連通性(L3 / L4)

| 命令 | 作用 | 底層一兩句 |
|---|---|---|
| `ping host` | L3 通不通 + RTT | 走 ICMP;**通了只代表網路層通**,不代表服務在 |
| `mtr host` | `ping`+`traceroute` 合體,持續看每跳丟包 | 揪「路徑中哪一跳開始丟包/變慢」,比 traceroute 好用 |
| `traceroute host` | 看封包經過哪些跳 | 一次性版的 mtr |
| `nc -zv host 8080` | 測**TCP 端口**通不通(不依賴應用) | `z`=只掃不傳資料;**分清「端口通」vs「應用有回應」** |
| `telnet host 8080` | 老派測端口 + 手敲協議 | 沒 `nc` 時的備胎 |

> 排查心法:**`ping` 通但服務連不上**很常見——因為 `ping` 是 L3,服務是 L4/L7。用 `nc -zv` 確認 TCP 端口層,再用 `curl` 確認應用層,別停在 `ping`。

---

## 3. DNS

| 命令 | 作用 | 底層一兩句 |
|---|---|---|
| 🔧 `dig +short name` | 解析域名(乾淨輸出) | 直接問 DNS server,**不走** `/etc/hosts` |
| `dig name @8.8.8.8` | 指定**用哪個 DNS server** 解 | 排查「是不是本機 DNS 配置壞了」 |
| `dig +trace name` | 從根域一步步追解析過程 | 看到底卡在哪一級 |
| `getent hosts name` | 走**系統完整解析路徑** | 含 `/etc/hosts` + `nsswitch`——**和應用看到的一致** |
| `cat /etc/resolv.conf` | 看本機用哪些 DNS server | DNS 解不出先查它 |

> 關鍵對比:**`dig` 直接問 DNS server;`getent` 走系統完整路徑(含 hosts 檔)**。當「`dig` 解得出但程式連不上」——多半是 `/etc/hosts` 或 `nsswitch` 攔截了,用 `getent` 才復現得出應用的真實解析。

---

## 4. HTTP / 應用層(`curl`)

| 命令 | 作用 |
|---|---|
| 🔧 `curl -v https://x` | 看完整握手 + 請求/回應 header(排查首選) |
| `curl -I https://x` | **只看回應 header**(狀態碼、重定向、快取) |
| `curl -s -o /dev/null -w '%{http_code} %{time_total}\n' url` | 只要狀態碼 + 總耗時(腳本化探活) |
| `curl -w '@-' ...`(配 timing 模板) | 拆解 DNS / 連接 / TLS / 首字節各段耗時——**揪「慢在哪一段」** |
| `curl --resolve host:443:1.2.3.4 https://host` | **繞過 DNS** 強制連某 IP | 測「換了後端但 DNS 還沒切」 |

> `%{time_namelookup}` / `%{time_connect}` / `%{time_starttransfer}` / `%{time_total}` 一拆,立刻知道慢在 DNS、TCP、TLS 還是後端處理。

---

## 5. 抓包:`tcpdump`(真相裁判)

前面都查不出來時,抓包看**線上到底發了什麼**:

| 命令 | 作用 |
|---|---|
| 🔧 `tcpdump -i any -nn port 8080` | 抓所有網卡上 8080 的包,不反解 IP/端口 | 
| `tcpdump -i any host 1.2.3.4` | 只抓跟某 IP 的往來 |
| `tcpdump -i any -nn -w cap.pcap port 8080` | **存檔**,拖去 Wireshark 細看 |
| `tcpdump -i any -A port 8080` | 以 ASCII 印出內容(看明文 HTTP) |

> `-nn` = 不把 IP 反解成域名、不把端口反解成服務名(快、不卡)。心法:**`tcpdump` 是最後手段**——能用 `ss`/`curl` 判出來就別抓包;真要抓,複雜分析就 `-w` 存檔交給 Wireshark。

---

## 🔧 主力命令深講 + 速驗

> 網路驗證要有「對端」;沙盒裡用**本機監聽(`nc -lk`)+ ping 自己**就能自給自足。**先進 README 的沙盒**(部分用例需容器有外網)。

### ss — 端口與連接

| 寫法 | 作用 |
|---|---|
| `ss -tlnp` | TCP + 監聽 + 數字 + 進程 |
| `ss -tunlp` | 連 **UDP** 一起看(`u`) |
| `ss -tnp` | **已建立**的 TCP 連接 |
| `ss -s` | 各狀態**摘要**(TIME_WAIT 爆沒爆) |
| `ss -tn state established` | 按連接狀態過濾 |
| `ss -tnp 'dport = :443'` | 按端口過濾 |

助記:`t`cp · `u`dp · `l`isten · `n`umeric · `p`rocess · `a`ll。

**⚡ 驗證**:
```bash
nc -lk 8080 &                  # 起一個監聽 8080 的服務
ss -tlnp | grep 8080           # 預期:LISTEN ... :8080 ... users:(("nc",pid=...))
kill %1
```

### dig — DNS 查詢

| 寫法 | 作用 |
|---|---|
| `dig +short name` | 只要結果(乾淨) |
| `dig name @1.1.1.1` | 指定 DNS server |
| `dig name MX` / `TXT` / `NS` | 指定記錄類型 |
| `dig +trace name` | 從根域逐級追 |
| `dig -x 1.2.3.4` | 反向解析(IP → 域名) |

**⚡ 驗證**(需外網):
```bash
dig +short example.com         # 預期:一個或多個 IP
dig example.com MX +short      # 預期:MX 記錄(或空行)
```

### curl — HTTP 瑞士刀

| 寫法 | 作用 |
|---|---|
| `curl -v URL` | 看握手 + 請求/回應 header |
| `curl -I URL` | 只看回應 header |
| `curl -L URL` | 跟隨重定向 |
| `curl -s -o /dev/null -w '%{http_code}\n' URL` | 只要狀態碼 |
| `curl -H 'K: V' -d 'body' -X POST URL` | 加 header / body / 方法 |
| `curl --resolve host:443:IP URL` | 繞過 DNS 強連某 IP |

**⚡ 驗證**(需外網):
```bash
curl -s -o /dev/null -w '%{http_code} %{time_total}s\n' https://example.com
# 預期:200 0.xxxs
curl -sI https://example.com | head -1     # 預期:HTTP/... 200
```

### tcpdump — 抓包

| 寫法 | 作用 |
|---|---|
| `tcpdump -i any` | 抓所有網卡 |
| `tcpdump -nn` | 不反解 IP / 端口(快) |
| `tcpdump port 80` / `host 1.2.3.4` / `icmp` | 過濾表達式 |
| `tcpdump -c 10` | 抓 10 個包就停 |
| `tcpdump -w cap.pcap` / `-r cap.pcap` | 存檔 / 讀檔 |
| `tcpdump -A` | 以 ASCII 印內容(看明文 HTTP) |

**⚡ 驗證**:
```bash
tcpdump -i any -nn -c 3 icmp &     # 抓 3 個 ICMP 包就停(背景)
sleep 1
ping -c 3 127.0.0.1                # 製造 ICMP 流量
# 預期:tcpdump 印出 3 行 ICMP echo request/reply 後自動結束
```

### ⚡ 配角速驗(`ping` / `nc` / `getent` / `traceroute`)

```bash
ping -c 3 127.0.0.1            # 預期:3 個 reply,0% packet loss
getent hosts example.com      # 預期:IP + 主機名(走系統解析路徑,需外網)
nc -lk 9000 &                 # 起一個監聽
sleep 1
nc -zv 127.0.0.1 9000         # 預期:... port 9000 ... succeeded!
kill %1
traceroute -m 5 1.1.1.1       # 預期:逐跳列出(需外網;容器內可能受限)
```

---

## 黃金排查路徑:「連不上某服務」

```
連不上 service:port
│
├─ 在「服務端」機器:ss -tlnp │ 它真的在聽這個端口嗎？進程活著嗎？
│        └─ 沒在聽 → 服務沒起 / 綁錯網卡(127.0.0.1 vs 0.0.0.0)
│
├─ 在「客戶端」機器：
│   ├─ dig +short host    │ 域名解對 IP 嗎？（getent 復現應用解析）
│   ├─ ping IP            │ L3 通嗎？（不通：路由/安全組/防火牆）
│   ├─ nc -zv IP port     │ L4 端口通嗎？（不通：防火牆/安全組擋端口）
│   └─ curl -v http://... │ L7 應用回什麼？（連上了但 5xx → 是應用問題）
│
└─ 全都「看起來通」卻還是怪 → tcpdump 兩端對抓，看包到底走到哪
```

---

## 深挖

- TCP/IP、三次握手、TIME_WAIT/CLOSE_WAIT 的完整原理 → **`linux-handson/06-networking`**
- 反向代理 / 負載均衡 / 連接層調優 → **`nginx`**、**`gateway`**
- SSH 隧道、端口轉發 → **`10 遠端與傳輸`**
