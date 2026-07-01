# 資深 CLI core set（一屏總覽）

> **這頁不解釋，只收口。** 一個資深工程師 / 架構師日常真正反覆敲的命令，全塞進一屏。
> 每行只給「命令 · 幹嘛 · 肌肉記憶那 1-3 個參數」，想懂**為什麼 / 完整參數 / 驗證**——順著 `→` 翻對應章（那裡才是詳解）。
>
> 心法：**記的是「6 類 + 每類收口原語」，不是背命令。命令/參數會忘，忘了就查（見文末反射塊）。**

---

## 記憶錨：一切先落到這 6 類

```
① 進程/作業   ② 性能/資源   ③ 網路
④ 文本/管道   ⑤ 檔案/磁碟   ⑥ 服務·容器·遠端
```

排查任何「X 出事」→ 先歸到某一類 → 進那一類的幾個主力命令 → 不夠深再 `→` 翻章。

---

## ① 進程與作業控制  → [01](01-process-and-job-control.md)

| 命令 | 幹嘛 | 肌肉記憶 |
|---|---|---|
| `ps -ef` / `ps aux` | 列全部進程 | 挑一種風格看慣即可 |
| `pgrep -af 字串` | **按命令列**找進程 | `-f` 比整條命令列（必加）· `-a` 印出來 |
| `pkill -f 字串` | 按命令列殺 | 同上；殺前先用 `pgrep -af` 確認 |
| `kill -TERM PID` / `kill -9 PID` | 送信號 | 先 `-TERM`（優雅）→ 不理再 `-9`（強殺） |
| `Ctrl+Z` → `bg` / `fg` / `jobs` | 作業控制 | 掛起→後台跑→調回前台 |
| `nohup cmd &` | 後台 + 斷線不死 | 長期跑請改用 systemd（→07） |
| `pstree -p` | 進程樹（誰 fork 誰） | 抓孤兒/失控子進程 |

> 收口：**放後台答 2 問（佔終端嗎/斷線要活嗎）· 找殺看程式名 vs 命令列（後者 `-f`）· 信號沿歸屬鏈傳。**

## ② 性能與資源排查  → [02](02-performance-and-resource-triage.md) · 讀錶 → [../metrics-decoder](../metrics-decoder/)

| 命令 | 幹嘛 | 肌肉記憶 |
|---|---|---|
| `top` / `htop` | 即時總覽 | 讀頂行 `us/sy/wa` 分流是哪類瓶頸 |
| `uptime` | load 1/5/15 分鐘 | 看**趨勢**；load 要除以 `nproc` |
| `vmstat 1` | CPU/mem/swap 時序 | `si/so`（swap）非 0 = 記憶體吃緊 |
| `pidstat 1` | 按**進程**分 CPU | `-w` 看上下文切換 · `-d` 看 IO |
| `free -h` | 記憶體 | 看 `available` 不是 `free` |
| `iostat -xz 1` | 磁碟 IO | `await`（延遲）· `%util`（忙碌） |

> 收口：**資源 4 類（CPU/mem/IO/net），每類問 USE（用了多少/排隊多深/有沒有錯）· `load` ≠ CPU%（含 D 態等 IO）。**

## ③ 網路排查  → [03](03-network-triage.md)

| 命令 | 幹嘛 | 肌肉記憶 |
|---|---|---|
| `ss -tlnp` | **誰在聽哪個端口** | `t`CP `l`isten `n`umeric `p`rocess |
| `ss -tnp state established` | 看活躍連接 | 排查連接數/`TIME_WAIT` 堆積 |
| `curl -v` / `-I URL` | 打 HTTP 看細節 | `-v` 全過程 · `-I` 只看頭 |
| `ping` / `mtr host` | 連通 / 逐跳丟包 | `mtr` = ping+traceroute |
| `dig 域名` | DNS 解析 | `+short` 只看結果 |
| `tcpdump -i any port 80 -nn` | 抓包 | `-nn` 不解析名字（快）· `-w f.pcap` 存檔 |

> 收口：**先分「連不上 / 連上了慢 / 解不出名字」→ 對應 ss·curl·dig。**

## ④ 文本三劍客與管道  → [05](05-text-processing-and-pipes.md)

| 命令 | 幹嘛 | 肌肉記憶 |
|---|---|---|
| `grep -rn 'x' .` / `-E` | 找 | `-r` 遞迴 `-n` 行號 · `-E` 擴展正則 · `-v` 反選 |
| `awk '{print $2}'` | 抽某列 | `-F,` 換分隔符 · `$NF` 最後一列 |
| `sed 's/a/b/g'` | 替換 | `-i` 直接改檔（危險，先不加試） |
| `sort \| uniq -c \| sort -rn` | **統計排行**（黃金組合） | 日誌數 IP/URL Top N 就這條 |
| `cut -d: -f1` | 切列 | 結構固定用 cut，不固定用 awk |
| `xargs` | 上游輸出 → 下游參數 | `-I{}` 佔位 · `-P` 並行 |
| `jq '.a.b'` | JSON | `-r` 去引號 · `.[]` 展開陣列 |

> 收口：**一切皆檔案 · 小工具用 `\|` 拼 · `xargs` 把輸出變參數。不存在萬能命令，只有積木。**

## ⑤ 檔案・磁碟・權限  → [06](06-files-disk-permissions.md)

| 命令 | 幹嘛 | 肌肉記憶 |
|---|---|---|
| `find . -name '*.log' -mtime +7` | 按名字/時間/大小找 | `-type f` · `-size +100M` · `-delete` |
| `df -h` | **磁碟滿沒** | 看 `Use%` 和掛載點 |
| `du -sh *` / `ncdu` | **誰佔空間** | `ncdu` 可互動鑽（先裝） |
| `lsof -p PID` / `lsof -i:8080` | 進程開了啥 / 誰佔端口 | 「刪了檔磁碟沒回」→ `lsof \| grep deleted` |
| `chmod 644` / `chown u:g` | 權限/屬主 | `-R` 遞迴（小心） |
| `stat 檔` | 元數據（時間/inode/權限） | — |

> 收口：**磁碟滿先 `df` 定位掛載點 → `du`/`ncdu` 往下鑽 → 空間沒回想到 `lsof deleted`。**

## ⑥ 服務・容器・遠端

| 命令 | 幹嘛 | → |
|---|---|---|
| `systemctl status/restart svc` | 服務起停/看狀態 | [07](07-systemd-and-services.md) |
| `systemctl enable svc` | 開機自啟 | [07](07-systemd-and-services.md) |
| `journalctl -u svc -f` | 跟服務日誌 | [07](07-systemd-and-services.md) · [04](04-observability-internals.md) |
| `docker ps` / `logs -f` / `exec -it C sh` | 容器看/日誌/進去 | [08](08-containers-and-k8s.md) |
| `kubectl get/describe/logs/exec` | Pod 排查四件套 | [08](08-containers-and-k8s.md) |
| `ssh -L 本地:host:遠端 -N` | SSH 隧道 | [10](10-remote-and-transfer.md) |
| `rsync -avz src dst` | 增量同步大檔 | [10](10-remote-and-transfer.md) |
| `tmux` | 長任務可重連 | [10](10-remote-and-transfer.md) |
| `git reflog` / `bisect` / `stash` | git 救命 | [09](09-git-lifesaver.md) |

## 觀測內幕（深一層，不常用但關鍵）  → [04](04-observability-internals.md)

| 命令 | 幹嘛 | 肌肉記憶 |
|---|---|---|
| `strace -p PID -f` | 看進程狂調哪個 syscall | `-e trace=network,file` 只看某類 · 有性能開銷 |
| `dmesg -T` | 內核環形緩衝（OOM/硬體錯） | 「進程無故被殺」先看這（找 OOM） |

---

## ⚡ 忘了就查（3 秒反射，比背命令重要 10 倍）

命令/參數忘光是**正常的**——資深工程師記牢的就每工具 3-5 個，其餘每次現查。練這個反射：

| 想幹嘛 | 敲 | 說明 |
|---|---|---|
| 這個 flag 幹嘛 | `<cmd> --help` | **本機最快**，argparse/getopt 工具都印得出 |
| 完整手冊 | `man <cmd>` | `/關鍵詞` 搜、`n` 跳下一個 |
| 只想看**常用例子** | `tldr <cmd>` | 跳過長篇，直接給你能抄的例子（需 `apt install tldr`） |
| 沒網也沒裝 tldr | `curl cheat.sh/<cmd>` | 一行拿到範例（要網） |
| **忘了命令叫啥**，只記功能 | `apropos 關鍵詞` | 按描述反查命令名 |
| 這命令一句話幹嘛 | `whatis <cmd>` | 一行定位 |

> 三步循環（配 [FIRST-LOOP](../performance-tuning-roadmap/FIRST-LOOP.md) 一起用）：
> **① 這命令幹嘛** `tldr`/`whatis` → **② 這 flag 幹嘛** `--help`/`man` → **③ 輸出哪欄啥意思** [metrics-decoder](../metrics-decoder/)。

---

## 怎麼用這頁

1. **記 6 類 + 每類收口那一行**（灰底引言）——這是真正要進腦子的，~10 分鐘。
2. 命令表**掃過有印象就好**，不背。敲的時候忘了 → `--help`。
3. 想懂某命令的**為什麼 / 完整參數 / 驗證用例** → 順 `→` 翻 cli-toolbox 那章（那才是詳解，本頁不重複）。
4. 別停在讀——挑 [FIRST-LOOP](../performance-tuning-roadmap/FIRST-LOOP.md) 開兩個終端,把這頁的命令**敲**出來。手感只有敲才長。
