# cli-toolbox Output Field Decoders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add compact output-decoder blocks across `cli-toolbox` so common command outputs are readable during troubleshooting and interview prep.

**Architecture:** This is a Markdown-only documentation change. Each chapter keeps its current structure; decoder blocks are inserted inside existing "主力命令深講 + 速驗" sections, directly after the relevant command table or before the command's verification block.

**Tech Stack:** Markdown, shell verification with `rg` and `git diff --check`, existing `cli-toolbox` documentation style.

---

## File Structure

- Modify: `cli-toolbox/01-process-and-job-control.md`
  - Add `ps` output decoder and `STAT` code table.
- Modify: `cli-toolbox/02-performance-and-resource-triage.md`
  - Keep existing `vmstat` decoder.
  - Add `top`, `free`, and `iostat` decoders.
- Modify: `cli-toolbox/03-network-triage.md`
  - Add `ss`, `dig`, `curl -w`, and `tcpdump` decoders.
- Modify: `cli-toolbox/04-observability-internals.md`
  - Add `strace`, `lsof`, and `/proc/<pid>/status` decoders.
- Modify: `cli-toolbox/05-text-processing-and-pipes.md`
  - Add `awk` field-variable decoder and `sort | uniq -c` output decoder.
- Modify: `cli-toolbox/06-files-disk-permissions.md`
  - Add `ls -l`, `df`, `stat`, and `lsblk` decoders.
- Modify: `cli-toolbox/07-systemd-and-services.md`
  - Add `systemctl status` and `journalctl` decoders.
- Modify: `cli-toolbox/08-containers-and-k8s.md`
  - Add `docker ps`, `docker stats`, `kubectl get pods`, and Events decoders.
- Modify: `cli-toolbox/09-git-lifesaver.md`
  - Add `git status -sb`, `git diff`, and `git log --oneline --graph` decoders.
- Modify: `cli-toolbox/10-remote-and-transfer.md`
  - Add `ssh -v`, `ssh -G`, and `rsync --progress` decoders.

Implementation rule: keep every decoder compact. Do not rewrite chapter structure. Do not touch unrelated dirty files such as `linux-handson/04-memory-model/README.md`.

---

### Task 1: Process Decoders

**Files:**
- Modify: `cli-toolbox/01-process-and-job-control.md`

- [ ] **Step 1: Locate insertion point**

Run:

```bash
rg -n "### ps|ps -eo pid,ppid,pgid,sid,tty,stat,comm|\\*\\*⚡ 驗證\\*\\*" cli-toolbox/01-process-and-job-control.md
```

Expected: output shows `### ps — 看進程的瑞士刀`, the custom `ps -eo pid,ppid,pgid,sid,tty,stat,comm` row, and the `ps` verification block.

- [ ] **Step 2: Insert decoder after the `ps` command table and before `**⚡ 驗證**`**

Insert this exact Markdown:

````md
如果看到這種輸出,按欄位這樣讀:

```text
  PID  PPID  PGID   SID TT       STAT COMMAND
 1234  1200  1234  1200 pts/0    S+   sleep
```

| 欄位 | 意思 | 怎麼判讀 |
|---|---|---|
| `PID` | 進程自己的 ID | 後續 `kill`、`lsof -p`、`strace -p` 都靠它 |
| `PPID` | 父進程 ID | 子進程失控時,先找誰生了它 |
| `PGID` | 進程組 ID | `kill -- -PGID` 會打整組,不是單一 PID |
| `SID` | session ID | 判斷它還歸不歸某個登入會話/終端管 |
| `TTY` | 控制終端 | `?` 常見於 daemon 或脫離終端的進程 |
| `STAT` | 進程狀態碼 | 第一個字母看狀態,後綴看前台/多線程/優先級 |
| `COMMAND` | 程式名 | 只看程式名;要看完整參數用 `args` 或 `ps -ef` |

`STAT` 最常見:

| 代碼 | 意思 | 怎麼判讀 |
|---|---|---|
| `R` | running / runnable | 正在跑或等 CPU |
| `S` | sleeping | 正常睡眠,在等事件 |
| `D` | uninterruptible sleep | 常見是卡 IO;`kill -9` 也不一定立刻有用 |
| `T` | stopped | 被 `Ctrl+Z` 或信號停住 |
| `Z` | zombie | 子進程已死,等父進程 `wait()` 回收 |
| `+` | foreground process group | 前台進程組,會吃到終端的 `Ctrl+C` |
| `s` | session leader | 會話頭頭 |
| `l` | multi-threaded | 多線程進程 |

> 小坑:`ps -C name` 只認程式名,不認參數;找命令列字串用 `pgrep -af` 或 `ps -ef | grep`。
````

- [ ] **Step 3: Verify Task 1 text**

Run:

```bash
rg -n "runnable|uninterruptible sleep|ps -C name" cli-toolbox/01-process-and-job-control.md
git diff --check -- cli-toolbox/01-process-and-job-control.md
```

Expected: `rg` shows the inserted decoder lines. `git diff --check` exits 0.

---

### Task 2: Performance Decoders

**Files:**
- Modify: `cli-toolbox/02-performance-and-resource-triage.md`

- [ ] **Step 1: Locate insertion points**

Run:

```bash
rg -n "### top|### free|### iostat|### vmstat|如果看到完整表頭" cli-toolbox/02-performance-and-resource-triage.md
```

Expected: output shows all four command sections. `vmstat` already has a decoder block.

- [ ] **Step 2: Insert `top` decoder before `top` verification**

Insert this exact Markdown after the batch-mode table in the `top` section:

````md
如果看到 `top` 頂部摘要,按區塊這樣讀:

```text
top - 10:00:00 up 3 days,  2 users,  load average: 0.42, 0.60, 0.55
Tasks: 120 total,   1 running, 119 sleeping,   0 stopped,   0 zombie
%Cpu(s): 12.0 us,  3.0 sy,  0.0 ni, 80.0 id,  5.0 wa,  0.0 hi,  0.0 si,  0.0 st
MiB Mem :  16000 total,   2000 free,   9000 used,   5000 buff/cache
MiB Swap:   2048 total,   2048 free,      0 used.   6000 avail Mem
```

| 區塊 | 怎麼讀 |
|---|---|
| `load average` | 1/5/15 分鐘平均排隊量;要除以 CPU 核心數看 |
| `Tasks` | `running` 多看 CPU,`zombie` 非 0 看父進程回收問題 |
| `%Cpu(s)` | `us` 應用算,`sy` 內核忙,`id` 空閒,`wa` 等 IO,`st` 被宿主偷 CPU |
| `Mem` | `used` 含 cache 口徑,別只盯 `free` |
| `Swap` | `used` 上升不一定正在抖;要配 `vmstat si/so` 看是否持續換頁 |

> 小坑:`top` 裡單個進程 `%CPU` 在多核機可超過 100%;總 CPU 行才是全機比例。
````

- [ ] **Step 3: Insert `free` decoder before `free` verification**

Insert this exact Markdown after the `free` options table:

````md
如果看到這種輸出,重點看 `available`:

```text
              total        used        free      shared  buff/cache   available
Mem:           16Gi       9.0Gi       1.5Gi       200Mi       5.5Gi       6.0Gi
Swap:         2.0Gi          0B       2.0Gi
```

| 欄位 | 意思 | 怎麼判讀 |
|---|---|---|
| `total` | 物理記憶體總量 | 容量基準 |
| `used` | 已使用記憶體 | 包含多種口徑,別單獨當壓力證據 |
| `free` | 完全空著的記憶體 | Linux 會故意讓它低,拿去做 cache |
| `buff/cache` | buffer + page cache | 可回收,通常不是壞事 |
| `available` | 估算可立刻給應用的量 | **最該看**;低才是真緊 |
| `Swap used` | 已放到 swap 的量 | 配 `vmstat si/so` 判斷是否正在頻繁換頁 |

> 小坑:`free` 很低不等於缺記憶體;`available` 低 + `si/so` 持續非零才危險。
````

- [ ] **Step 4: Insert `iostat` decoder before `iostat` verification**

Insert this exact Markdown after the sentence `看哪幾欄:`:

````md
如果看到磁碟行,這幾欄最有用:

```text
Device            r/s     w/s   rkB/s   wkB/s  await  aqu-sz  %util
nvme0n1          5.00   80.00  640.00 9000.00   2.50    0.30  35.00
```

| 欄位 | 意思 | 怎麼判讀 |
|---|---|---|
| `r/s` `w/s` | 每秒讀/寫 IO 次數 | IOPS 壓力 |
| `rkB/s` `wkB/s` | 每秒讀/寫吞吐 | 大檔/掃描型壓力 |
| `await` | 單次 IO 平均等待 ms | **延遲核心指標**;飆高表示請求等太久 |
| `aqu-sz` | 平均隊列長度 | 長期升高 = IO 排隊 |
| `%util` | 設備忙碌比例 | HDD 接近 100% 多半飽和;NVMe 要配 `await` 看 |

> 小坑:SSD/NVMe 能並行,`%util` 高不一定壞;`await` 高才更像使用者真的在等。
````

- [ ] **Step 5: Verify Task 2 text**

Run:

```bash
rg -n "top.*頂部摘要|available|aqu-sz|第一行數字通常" cli-toolbox/02-performance-and-resource-triage.md
git diff --check -- cli-toolbox/02-performance-and-resource-triage.md
```

Expected: `rg` shows the new `top`, `free`, `iostat`, and existing `vmstat` decoder lines. `git diff --check` exits 0.

---

### Task 3: Network Decoders

**Files:**
- Modify: `cli-toolbox/03-network-triage.md`

- [ ] **Step 1: Locate insertion points**

Run:

```bash
rg -n "### ss|### dig|### curl|### tcpdump|\\*\\*⚡ 驗證" cli-toolbox/03-network-triage.md
```

Expected: output shows each network command section and verification blocks.

- [ ] **Step 2: Insert `ss` decoder after the `ss` mnemonic line**

Insert this exact Markdown:

````md
如果看到 `ss -tlnp` 輸出,按欄位這樣讀:

```text
State  Recv-Q Send-Q Local Address:Port Peer Address:Port Process
LISTEN 0      128          0.0.0.0:8080      0.0.0.0:*     users:(("nc",pid=1234,fd=3))
```

| 欄位 | 意思 | 怎麼判讀 |
|---|---|---|
| `State` | TCP 狀態 | `LISTEN` 是服務在聽;`ESTAB` 是已連上 |
| `Recv-Q` | 本端還沒被程式讀走的 bytes | 監聽 socket 上長期高,應用可能接太慢 |
| `Send-Q` | 本端還沒送出去/對端沒收完的 bytes | 長期高,可能對端慢或網路塞 |
| `Local Address:Port` | 本機地址與端口 | `0.0.0.0:8080` = 所有網卡都聽 |
| `Peer Address:Port` | 對端地址與端口 | `*` 常見於監聽 socket |
| `users:(("nc",pid=1234,fd=3))` | 佔用 socket 的進程、PID、fd | 端口被佔時直接看這欄 |

> 小坑:沒有 `-n` 時會反查域名/服務名,排查時可能變慢且干擾判讀。
````

- [ ] **Step 3: Insert `dig` decoder before `dig` verification**

Insert this exact Markdown after the `dig` options table:

````md
如果看到完整 `dig` 輸出,先看這幾段:

```text
;; ANSWER SECTION:
example.com.        300     IN      A       93.184.216.34

;; Query time: 20 msec
;; SERVER: 1.1.1.1#53(1.1.1.1)
```

| 欄位/段落 | 意思 | 怎麼判讀 |
|---|---|---|
| `ANSWER SECTION` | DNS 回答本體 | 沒這段常是沒解析到結果 |
| `300` | TTL 秒數 | 快取多久;切 DNS 時它決定舊值殘留時間 |
| `A` / `CNAME` / `MX` | 記錄類型 | `A` 是 IPv4,`CNAME` 是別名,`MX` 是郵件 |
| `Query time` | 查詢耗時 | 高了看 DNS server 或網路 |
| `SERVER` | 實際詢問的 DNS server | 確認是不是問到預期 resolver |

> 小坑:`dig` 直接問 DNS;應用實際解析還可能受 `/etc/hosts` 和 `nsswitch` 影響,要用 `getent hosts` 對照。
````

- [ ] **Step 4: Insert `curl -w` decoder before `curl` verification**

Insert this exact Markdown after the `curl` options table:

````md
排慢請把時間拆開看:

```bash
curl -s -o /dev/null -w 'dns=%{time_namelookup} tcp=%{time_connect} tls=%{time_appconnect} first=%{time_starttransfer} total=%{time_total}\n' https://example.com
```

| 欄位 | 意思 | 慢了看哪 |
|---|---|---|
| `time_namelookup` | DNS 解析完成時間 | DNS / resolver |
| `time_connect` | TCP 連線完成時間 | 網路路徑 / 防火牆 / 端口 |
| `time_appconnect` | TLS 握手完成時間 | 憑證 / TLS / 中間代理 |
| `time_starttransfer` | 首 byte 回來時間 | 後端處理慢最常看這個 |
| `time_total` | 整次請求總時間 | 使用者體感總耗時 |

> 小坑:`time_starttransfer` 包含前面的 DNS/TCP/TLS;要看後端處理時間,用它減掉連線階段。
````

- [ ] **Step 5: Insert `tcpdump` decoder before `tcpdump` verification**

Insert this exact Markdown after the `tcpdump` options table:

````md
如果看到 TCP 包,拆成這幾段:

```text
10:00:00.123456 IP 10.0.0.1.54321 > 10.0.0.2.80: Flags [S], seq 100, win 64240, length 0
```

| 片段 | 意思 | 怎麼判讀 |
|---|---|---|
| `10:00:00.123456` | 抓到包的時間 | 對齊應用日誌時間 |
| `10.0.0.1.54321 > 10.0.0.2.80` | 來源 IP/端口 到 目的 IP/端口 | 箭頭看方向 |
| `Flags [S]` | TCP flag | `S` SYN,`.` ACK,`F` FIN,`R` RST,`P` PUSH |
| `seq` / `ack` | TCP 序號/確認號 | 深查重傳/亂序時用 |
| `length` | payload 長度 | `0` 常見於握手/ACK 控制包 |

> 小坑:排查連線先加 `-nn`;不反解名字,輸出更快更準。
````

- [ ] **Step 6: Verify Task 3 text**

Run:

```bash
rg -n "Recv-Q|ANSWER SECTION|time_starttransfer|Flags \\[S\\]" cli-toolbox/03-network-triage.md
git diff --check -- cli-toolbox/03-network-triage.md
```

Expected: `rg` shows all four decoder blocks. `git diff --check` exits 0.

---

### Task 4: Observability Decoders

**Files:**
- Modify: `cli-toolbox/04-observability-internals.md`

- [ ] **Step 1: Locate insertion points**

Run:

```bash
rg -n "### strace|### lsof|### /proc|\\*\\*⚡ 驗證" cli-toolbox/04-observability-internals.md
```

Expected: output shows the three observability command sections and verification blocks.

- [ ] **Step 2: Insert `strace` decoder before `strace` verification**

Insert this exact Markdown after the `strace` options table:

````md
如果看到一行 syscall,按形狀拆:

```text
10:00:00.123456 openat(AT_FDCWD, "/etc/passwd", O_RDONLY) = 3 <0.000123>
```

| 片段 | 意思 | 怎麼判讀 |
|---|---|---|
| `10:00:00.123456` | syscall 發生時間 | `-tt` 才有,用來對齊日誌 |
| `openat(AT_FDCWD, "/etc/passwd", O_RDONLY)` | syscall 名與參數 | 看進程向內核要什麼 |
| `= 3` | 返回值 | 非負通常成功;fd 也常在這裡出現 |
| `= -1 ENOENT` | 失敗 + errno | 直接指出缺檔、權限、連線失敗等原因 |
| `<0.000123>` | syscall 耗時 | `-T` 才有;找慢 syscall |

> 小坑:`strace` 會拖慢目標進程;生產短抓即放。
````

- [ ] **Step 3: Insert `lsof` decoder before `lsof` verification**

Insert this exact Markdown after the `lsof` options table:

````md
如果看到 `lsof` 表頭,這樣讀:

```text
COMMAND PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
sleep  1234 root  cwd    DIR  0,123     4096    2 /tmp
sleep  1234 root    1w   REG  0,123      100   99 /tmp/app.log
```

| 欄位 | 意思 | 怎麼判讀 |
|---|---|---|
| `COMMAND` / `PID` / `USER` | 進程、PID、使用者 | 先定位誰開著 |
| `FD` | file descriptor | `cwd` 工作目錄,`txt` 程式本體,`1w` stdout 以寫入開啟 |
| `TYPE` | 對象類型 | `REG` 檔案,`DIR` 目錄,`IPv4/IPv6` socket |
| `SIZE/OFF` | 檔案大小或 offset | 看日誌是否還在增長 |
| `NAME` | 檔名或連線 | 看到 `(deleted)` 代表刪了但 fd 還開著 |

> 小坑:磁碟滿但 `du` 算不出來,優先找 `lsof | grep deleted`。
````

- [ ] **Step 4: Insert `/proc/<pid>/status` decoder before `/proc` verification**

Insert this exact Markdown after the `/proc/<pid>/` options table:

````md
`/proc/PID/status` 常看這幾行:

```text
State:  S (sleeping)
VmRSS:  12345 kB
Threads:  8
voluntary_ctxt_switches:  100
nonvoluntary_ctxt_switches:  20
```

| 欄位 | 意思 | 怎麼判讀 |
|---|---|---|
| `State` | 進程狀態 | `R/S/D/Z` 對應 `ps STAT` 第一字母 |
| `VmRSS` | 常駐實體記憶體 | 粗看進程真佔多少 RAM |
| `Threads` | 線程數 | 暴增可能是線程洩漏或池子失控 |
| `voluntary_ctxt_switches` | 主動讓出 CPU 次數 | 常見於等 IO/鎖/睡眠 |
| `nonvoluntary_ctxt_switches` | 被排程器搶走 CPU 次數 | CPU 競爭高時可能上升 |

> 小坑:`VmSize` 是虛擬地址空間,不等於真實佔用;看記憶體優先看 `VmRSS`。
````

- [ ] **Step 5: Verify Task 4 text**

Run:

```bash
rg -n "ENOENT|deleted\\)|VmRSS|nonvoluntary" cli-toolbox/04-observability-internals.md
git diff --check -- cli-toolbox/04-observability-internals.md
```

Expected: `rg` shows all three decoder blocks. `git diff --check` exits 0.

---

### Task 5: Text Pipeline Decoders

**Files:**
- Modify: `cli-toolbox/05-text-processing-and-pipes.md`

- [ ] **Step 1: Locate insertion points**

Run:

```bash
rg -n "### awk|### ⚡ 配角速驗|sort \\| uniq" cli-toolbox/05-text-processing-and-pipes.md
```

Expected: output shows the `awk` verification block and the companion tools verification block.

- [ ] **Step 2: Insert `awk` decoder before `awk` verification**

Insert this exact Markdown under the `### awk 速驗(補:\`-v var=值\` 傳變數、\`NF\` 欄位數、\`$NF\` 最後一欄)` heading and before its code block:

````md
`awk` 先把每行切欄位,內建變數這樣讀:

| 變數 | 意思 | 常用法 |
|---|---|---|
| `$0` | 整行 | 原樣輸出或整行匹配 |
| `$1` `$2` | 第 1/第 2 欄 | `awk '{print $1}'` 取第一欄 |
| `$NF` | 最後一欄 | 日誌欄位數不固定時很常用 |
| `NF` | 本行欄位數 | 過濾欄位不足的髒資料 |
| `NR` | 目前第幾行 | 跳過表頭:`NR>1` |
| `FS` | input separator | `-F:` 等價於設定它 |
| `OFS` | output separator | 控制 `print a,b` 中間用什麼隔開 |

> 小坑:預設按連續空白切欄;CSV 不是純文字空白表,複雜 CSV 別硬用簡單 `awk -F,`。
````

- [ ] **Step 3: Insert `sort | uniq -c` decoder before companion verification code block**

Insert this exact Markdown under the `### ⚡ 配角速驗(\`sort\`/\`uniq\`/\`cut\`/\`tr\`/\`wc\`/\`xargs\`/\`jq\`/\`tee\`)` heading and before its code block:

````md
`sort | uniq -c | sort -rn` 輸出是「次數在前」:

```text
      2 dev
      2 ops
```

| 片段 | 意思 | 怎麼判讀 |
|---|---|---|
| `2` | 這個值出現次數 | 排序後可當 top-N |
| `dev` | 被統計的值 | 可能是 IP、狀態碼、使用者、錯誤類型 |
| 第一個 `sort` | 讓相同值相鄰 | `uniq` 只合併相鄰重複行 |
| `sort -rn` | 按數字逆序排 count | 最大量排最前 |

> 小坑:漏掉第一個 `sort`,`uniq -c` 只統計連在一起的重複,結果會錯。
````

- [ ] **Step 4: Verify Task 5 text**

Run:

```bash
rg -n "\\$NF|CSV|uniq -c|漏掉第一個" cli-toolbox/05-text-processing-and-pipes.md
git diff --check -- cli-toolbox/05-text-processing-and-pipes.md
```

Expected: `rg` shows both decoder blocks. `git diff --check` exits 0.

---

### Task 6: Filesystem Decoders

**Files:**
- Modify: `cli-toolbox/06-files-disk-permissions.md`

- [ ] **Step 1: Locate insertion points**

Run:

```bash
rg -n "### du / df|### chmod|### ⚡ 配角速驗|ls -l /tmp/perm|stat /tmp/perm|lsblk" cli-toolbox/06-files-disk-permissions.md
```

Expected: output shows `du / df`, `chmod`, and companion verification sections.

- [ ] **Step 2: Insert `df` decoder before `du / df` verification**

Insert this exact Markdown after the `du / df` options table:

````md
`df -h` 看空間,`df -i` 看 inode,兩個都可能滿:

```text
Filesystem      Size  Used Avail Use% Mounted on
/dev/vda1        40G   35G  5.0G  88% /

Filesystem      Inodes IUsed  IFree IUse% Mounted on
/dev/vda1      2621440 20000 2601440    1% /
```

| 命令 | 看什麼 | 怎麼判讀 |
|---|---|---|
| `df -h` | block 空間 | `Use%` 高 = 容量快滿 |
| `df -i` | inode 數量 | 小檔太多會 inode 滿,即使 GB 還夠也寫不進 |
| `Avail` / `IFree` | 剩餘空間/剩餘 inode | 這兩欄才是還能不能寫 |
| `Mounted on` | 掛載點 | 確認滿的是哪個分區 |

> 小坑:報 `No space left on device` 不一定是 GB 滿,也可能是 inode 滿。
````

- [ ] **Step 3: Insert `ls -l` decoder before `chmod` verification**

Insert this exact Markdown after the `chmod / chown` options table:

````md
`ls -l` 第一欄拆開看:

```text
-rwxr-xr-x 1 root root 123 Jun 26 10:00 app.sh
```

| 片段 | 意思 | 怎麼判讀 |
|---|---|---|
| `-` | 檔案類型 | `-` 普通檔,`d` 目錄,`l` 軟連結 |
| `rwx` | owner 權限 | 檔案擁有者能讀/寫/執行 |
| `r-x` | group 權限 | 同組使用者能讀/執行 |
| `r-x` | others 權限 | 其他人能讀/執行 |
| `1` | hard link 數 | 目錄或硬連結場景會變大 |
| `root root` | owner / group | 權限排查要配這兩欄 |
| `123` | 大小 bytes | `ls -lh` 會變成人類可讀 |

> 小坑:目錄的 `x` 代表能進入/穿越目錄;只有 `r` 沒 `x` 很多操作仍會失敗。
````

- [ ] **Step 4: Insert `stat` and `lsblk` decoders before companion verification code block**

Insert this exact Markdown under the `### ⚡ 配角速驗(\`stat\` / \`ln\` / \`tar\` / \`file\` / \`lsblk\`)` heading and before its code block:

````md
`stat` 的三種時間不要混:

| 欄位 | 意思 | 常見用途 |
|---|---|---|
| `Access` | 上次讀取時間 | 誰最近讀過;很多系統會弱化更新 |
| `Modify` | 檔案內容上次修改 | 排查內容何時變了 |
| `Change` | metadata 上次改變 | chmod/chown/rename/link 也會更新 |

`lsblk` 看塊設備樹:

| 欄位 | 意思 | 怎麼判讀 |
|---|---|---|
| `NAME` | 設備名 | 樹狀縮排表示磁碟、分區、LVM 關係 |
| `SIZE` | 容量 | 對照 `df` 看分區是否掛上 |
| `TYPE` | 類型 | `disk` 磁碟,`part` 分區,`lvm` 邏輯卷 |
| `MOUNTPOINTS` | 掛載點 | 空白代表目前沒掛載 |

> 小坑:`Modify` 是內容變,`Change` 是 inode metadata 變;不是建立時間。
````

- [ ] **Step 5: Verify Task 6 text**

Run:

```bash
rg -n "inode 滿|第一欄拆開|Access|MOUNTPOINTS" cli-toolbox/06-files-disk-permissions.md
git diff --check -- cli-toolbox/06-files-disk-permissions.md
```

Expected: `rg` shows all filesystem decoder blocks. `git diff --check` exits 0.

---

### Task 7: systemd Decoders

**Files:**
- Modify: `cli-toolbox/07-systemd-and-services.md`

- [ ] **Step 1: Locate insertion points**

Run:

```bash
rg -n "### systemctl|### journalctl|\\*\\*⚡ 驗證" cli-toolbox/07-systemd-and-services.md
```

Expected: output shows `systemctl` and `journalctl` sections.

- [ ] **Step 2: Insert `systemctl status` decoder before `systemctl` verification**

Insert this exact Markdown after the `systemctl` options table:

````md
`systemctl status` 先看三塊:

```text
Loaded: loaded (/etc/systemd/system/app.service; enabled)
Active: failed (Result: exit-code) since Fri 2026-06-26 10:00:00 CST
Main PID: 1234 (code=exited, status=1/FAILURE)
```

| 欄位 | 意思 | 怎麼判讀 |
|---|---|---|
| `Loaded` | unit 檔是否被讀到、是否 enabled | `disabled` 不代表現在沒跑,只代表不自啟 |
| `Active` | 當前狀態 | `active` 跑著,`failed` 掛了,`activating` 卡啟動中 |
| `Result` | systemd 判定結果 | `exit-code` 看退出碼,`timeout` 看啟動超時 |
| `Main PID` | 主進程 PID | 已退出時會配 `code/status` |
| `status=1/FAILURE` | 進程退出碼 | 先看服務自己的日誌解釋這個碼 |

> 小坑:改 unit 檔後沒 `systemctl daemon-reload`,狀態裡仍可能是舊定義。
````

- [ ] **Step 3: Insert `journalctl` decoder before `journalctl` verification**

Insert this exact Markdown after the `journalctl` options table:

````md
`journalctl` 一行日誌拆法:

```text
Jun 26 10:00:00 host app[1234]: failed to bind port
```

| 片段 | 意思 | 怎麼判讀 |
|---|---|---|
| `Jun 26 10:00:00` | 時間 | 用 `--since` / `--until` 收窄 |
| `host` | 主機名 | 多機匯總時很重要 |
| `app[1234]` | unit/程序與 PID | 對上 `systemctl status` 的 Main PID |
| `failed to bind port` | 日誌正文 | 真正錯誤通常在這裡 |
| `-p err` | 優先級過濾 | 只看 error 以上,適合快速巡檢 |

> 小坑:服務剛重啟過時,加 `-b` 看本次開機,加 `-u 服務` 避免被其他日誌淹掉。
````

- [ ] **Step 4: Verify Task 7 text**

Run:

```bash
rg -n "Result: exit-code|daemon-reload|failed to bind port|優先級" cli-toolbox/07-systemd-and-services.md
git diff --check -- cli-toolbox/07-systemd-and-services.md
```

Expected: `rg` shows both systemd decoder blocks. `git diff --check` exits 0.

---

### Task 8: Container and Kubernetes Decoders

**Files:**
- Modify: `cli-toolbox/08-containers-and-k8s.md`

- [ ] **Step 1: Locate insertion points**

Run:

```bash
rg -n "### docker|### kubectl|### ⚡ 配角速驗" cli-toolbox/08-containers-and-k8s.md
```

Expected: output shows Docker, kubectl, and companion verification sections.

- [ ] **Step 2: Insert Docker decoders before Docker verification**

Insert this exact Markdown after the Docker command table:

````md
`docker ps` 先看狀態與端口:

```text
CONTAINER ID   IMAGE   COMMAND                  STATUS          PORTS                  NAMES
abc123         nginx   "nginx -g 'daemon of…"   Up 10 seconds   0.0.0.0:8080->80/tcp   demo
```

| 欄位 | 意思 | 怎麼判讀 |
|---|---|---|
| `CONTAINER ID` | 容器短 ID | 後續 `logs/exec/inspect` 可用 |
| `IMAGE` | 來源鏡像 | 先確認版本/tag 對不對 |
| `COMMAND` | 容器啟動命令 | 被截斷時用 `docker inspect` 看完整 |
| `STATUS` | 容器狀態 | `Up` 正常,`Exited` 看 exit code,`Restarting` 看崩潰循環 |
| `PORTS` | 端口映射 | `8080->80` = 宿主 8080 轉容器 80 |
| `NAMES` | 容器名 | 人類操作最常用 |

`docker stats` 看資源:

| 欄位 | 意思 | 怎麼判讀 |
|---|---|---|
| `CPU %` | CPU 使用率 | 多核下可超過 100% |
| `MEM USAGE / LIMIT` | 已用記憶體 / 限額 | 接近 limit 時看 OOM 風險 |
| `NET I/O` | 網路收/發 | 粗看流量方向 |
| `BLOCK I/O` | 磁碟讀/寫 | 找刷盤容器 |
| `PIDS` | 進程/線程數 | 暴增可能是 fork/線程失控 |

> 小坑:`docker ps` 預設不顯示已退出容器;排查崩潰要加 `-a`。
````

- [ ] **Step 3: Insert Kubernetes decoders before kubectl verification**

Insert this exact Markdown after the kubectl command table:

````md
`kubectl get pods` 先看這幾欄:

```text
NAME    READY   STATUS             RESTARTS   AGE
api-0   0/1     CrashLoopBackOff   5          3m
```

| 欄位 | 意思 | 怎麼判讀 |
|---|---|---|
| `READY` | ready containers / total containers | `0/1` 表示容器未通過 ready |
| `STATUS` | Pod 當前階段/原因 | `Running` 不等於 ready;`CrashLoopBackOff` 看上次崩潰日誌 |
| `RESTARTS` | 重啟次數 | 持續增加 = 容器反覆崩 |
| `AGE` | Pod 存活時間 | 很小且重啟多,多半正在抖 |

`describe` 的 Events 看這樣:

| 欄位 | 意思 | 怎麼判讀 |
|---|---|---|
| `Type` | `Normal` 或 `Warning` | 先看 Warning |
| `Reason` | 機器可讀原因 | `FailedScheduling`、`BackOff`、`Pulled` |
| `Age` | 發生時間/頻率 | 看是否仍在重複 |
| `From` | 哪個 controller/kubelet 報的 | 區分調度、拉鏡像、節點問題 |
| `Message` | 人類可讀原因 | 真正排查線索 |

> 小坑:Pod `Running` 只代表容器進程在跑;服務能不能接流量要看 `READY`。
````

- [ ] **Step 4: Verify Task 8 text**

Run:

```bash
rg -n "docker ps|MEM USAGE|CrashLoopBackOff|FailedScheduling|READY" cli-toolbox/08-containers-and-k8s.md
git diff --check -- cli-toolbox/08-containers-and-k8s.md
```

Expected: `rg` shows Docker and Kubernetes decoder blocks. `git diff --check` exits 0.

---

### Task 9: Git Decoders

**Files:**
- Modify: `cli-toolbox/09-git-lifesaver.md`

- [ ] **Step 1: Locate insertion point**

Run:

```bash
rg -n "## 🔧 主力命令深講|git log --oneline|### reflog" cli-toolbox/09-git-lifesaver.md
```

Expected: output shows the setup block and command sections.

- [ ] **Step 2: Insert Git output decoder section after the setup code block and before `### reflog`**

Insert this exact Markdown:

````md
### 常見輸出怎麼讀

`git status -sb` 的短狀態:

```text
## main...origin/main [ahead 1, behind 2]
 M app.py
A  new.txt
?? scratch.txt
```

| 片段 | 意思 | 怎麼判讀 |
|---|---|---|
| `## main...origin/main` | 本地分支與 upstream | 確認正在跟哪個遠端分支比 |
| `ahead 1` | 本地多 1 個提交 | 還沒 push |
| `behind 2` | 遠端多 2 個提交 | 需要 pull/rebase |
| ` M app.py` | 工作區修改 | 左欄空,右欄 `M` = 未暫存 |
| `A  new.txt` | 暫存區新增 | 左欄 `A` = 已 staged |
| `?? scratch.txt` | 未追蹤 | Git 還沒管理 |

`git diff` 看 hunk:

```text
@@ -10,2 +10,3 @@
-old line
+new line
```

| 片段 | 意思 |
|---|---|
| `-10,2` | 舊檔從第 10 行開始,共 2 行 |
| `+10,3` | 新檔從第 10 行開始,共 3 行 |
| `-old line` | 刪掉的行 |
| `+new line` | 新增的行 |

`git log --oneline --graph` 左邊符號看分支形狀:`*` 是提交,線條表示分叉/合併,括號裡是 branch/tag/HEAD 指標。

> 小坑:`git status -s` 是兩欄狀態:左欄 staged,右欄 unstaged。
````

- [ ] **Step 3: Verify Task 9 text**

Run:

```bash
rg -n "ahead 1|左欄 staged|@@ -10,2|--graph" cli-toolbox/09-git-lifesaver.md
git diff --check -- cli-toolbox/09-git-lifesaver.md
```

Expected: `rg` shows all Git decoder lines. `git diff --check` exits 0.

---

### Task 10: Remote and Transfer Decoders

**Files:**
- Modify: `cli-toolbox/10-remote-and-transfer.md`

- [ ] **Step 1: Locate insertion points**

Run:

```bash
rg -n "### ssh|### rsync|\\*\\*⚡ 驗證" cli-toolbox/10-remote-and-transfer.md
```

Expected: output shows SSH and rsync sections.

- [ ] **Step 2: Insert SSH decoder before SSH verification**

Insert this exact Markdown after the SSH command table:

````md
`ssh -v` 排查時按階段看:

| 日誌片段 | 階段 | 卡住時看哪 |
|---|---|---|
| `Reading configuration data` | 讀 config | 是否吃到預期 `~/.ssh/config` |
| `Connecting to host port` | DNS/TCP 連線 | 主機名、端口、防火牆 |
| `kex_exchange_identification` / `SSH2_MSG_KEX` | key exchange | 協議/中間設備 |
| `Offering public key` | 嘗試私鑰 | 是否用了正確 key |
| `Authentication succeeded` | 認證成功 | 後面才是遠端 session 問題 |
| `Permission denied` | 認證失敗 | key、使用者、server `authorized_keys` |

`ssh -G host` 印「最後生效」的 config:

| 欄位 | 意思 |
|---|---|
| `hostname` | 最終連到哪個主機 |
| `user` | 最終登入使用者 |
| `port` | 最終端口 |
| `identityfile` | 會嘗試的私鑰 |
| `proxyjump` | 是否走跳板機 |

> 小坑:`ssh -G` 不會真的連線,適合先確認 config 展開結果。
````

- [ ] **Step 3: Insert `rsync --progress` decoder before rsync verification**

Insert this exact Markdown after the rsync options table:

````md
`rsync --progress` 一行進度這樣讀:

```text
      1,048,576  50%   10.00MB/s    0:00:01 (xfr#1, to-chk=2/5)
```

| 片段 | 意思 | 怎麼判讀 |
|---|---|---|
| `1,048,576` | 已傳 bytes | 單檔目前進度 |
| `50%` | 單檔完成比例 | 不是整個目錄比例 |
| `10.00MB/s` | 當前傳輸速度 | 看網路/磁碟瓶頸 |
| `0:00:01` | 估算剩餘時間 | 小檔很多時波動大 |
| `xfr#1` | 第幾個實際傳輸的檔案 | 沒變代表大多檔案被跳過 |
| `to-chk=2/5` | 待檢查/總檔案數 | 目錄整體掃描進度 |

> 小坑:目錄尾斜線很重要:`src/` 傳內容,`src` 傳整個目錄名。
````

- [ ] **Step 4: Verify Task 10 text**

Run:

```bash
rg -n "Reading configuration data|ssh -G|to-chk|尾斜線" cli-toolbox/10-remote-and-transfer.md
git diff --check -- cli-toolbox/10-remote-and-transfer.md
```

Expected: `rg` shows SSH and rsync decoder blocks. `git diff --check` exits 0.

---

### Task 11: Full Documentation Verification

**Files:**
- Modify: no files in this task.

- [ ] **Step 1: Confirm decoder coverage**

Run:

```bash
rg -n "如果看到|常見輸出怎麼讀|先看三塊|一行進度" cli-toolbox
```

Expected: output includes decoder blocks across `01` through `10`, with existing `vmstat` block in `02`.

- [ ] **Step 2: Check Markdown patch hygiene**

Run:

```bash
git diff --check -- cli-toolbox docs/superpowers/plans/2026-06-26-cli-toolbox-output-field-decoders.md
```

Expected: command exits 0 with no output.

- [ ] **Step 3: Review changed files only**

Run:

```bash
git diff --stat -- cli-toolbox
git diff -- cli-toolbox/01-process-and-job-control.md cli-toolbox/02-performance-and-resource-triage.md cli-toolbox/03-network-triage.md cli-toolbox/04-observability-internals.md cli-toolbox/05-text-processing-and-pipes.md cli-toolbox/06-files-disk-permissions.md cli-toolbox/07-systemd-and-services.md cli-toolbox/08-containers-and-k8s.md cli-toolbox/09-git-lifesaver.md cli-toolbox/10-remote-and-transfer.md
```

Expected: diff shows only compact decoder additions, no unrelated chapter rewrites.

- [ ] **Step 4: Commit implementation docs only**

Run:

```bash
git status --short
git add cli-toolbox/01-process-and-job-control.md cli-toolbox/02-performance-and-resource-triage.md cli-toolbox/03-network-triage.md cli-toolbox/04-observability-internals.md cli-toolbox/05-text-processing-and-pipes.md cli-toolbox/06-files-disk-permissions.md cli-toolbox/07-systemd-and-services.md cli-toolbox/08-containers-and-k8s.md cli-toolbox/09-git-lifesaver.md cli-toolbox/10-remote-and-transfer.md
git commit -m "docs(cli-toolbox): add output field decoders"
```

Expected: commit includes only `cli-toolbox` docs. If `linux-handson/04-memory-model/README.md` remains dirty, leave it unstaged.
