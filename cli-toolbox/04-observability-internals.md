# 04 · 觀測內幕(看進程「在幹嘛」)

> 進程卡住了、找不到檔案、端口開著卻不回應——這章教你**打開黑盒**,看一個進程到底在跟內核要什麼、開了哪些東西、系統留了什麼線索。

---

## 收口地圖(三個視角看穿一個進程)

想知道一個進程「在幹嘛」,從三個角度切:

1. **它在跟內核要什麼?** → `strace`(看系統調用)。卡住、報錯、慢,都會在某個 syscall 上現形。
2. **它開了哪些檔案 / 連接 / fd?** → `lsof` + `/proc/<pid>/`。**原語 3「一切皆檔案」的主場**:進程內部被攤成一堆 fd。
3. **系統/內核留了什麼話?** → `dmesg`(內核)、`journalctl`(服務)。進程「莫名消失/重啟」的真相常在這。

> 心法:**現象在應用層,根因常在「syscall / fd / 內核日誌」這三處之一。** 不知道往哪查,就這三個視角輪一遍。

---

## 1. `strace` —— 進程在跟內核要什麼

系統調用(syscall)是進程跟內核打交道的唯一窗口。看 syscall 就看到了「它真正在做什麼」。

| 命令 | 作用 | 底層一兩句 |
|---|---|---|
| `strace -p PID` | attach 到一個**正在跑**的進程 | 看它此刻卡/忙在哪個 syscall |
| `strace -f cmd` | 啟動並跟蹤(含 fork 出的子進程) | `-f` = follow,不然子進程的看不到 |
| `strace -c -p PID` | **統計**各 syscall 次數 / 耗時 | 找熱點:誰被狂調、誰最慢(性能排查神器) |
| `strace -T -tt -p PID` | 每個 syscall 標**耗時**+時間戳 | 揪「慢在哪一次調用」 |
| `strace -e trace=network cmd` | 只看某類 syscall | `network`/`file`/`openat,read` 等,降噪 |
| `ltrace -p PID` | 看**庫函數**調用(非 syscall) | 想看它調了哪些 libc 函數時用 |

**怎麼讀**(常見卡點對照):

| 卡在哪個 syscall | 多半在等 |
|---|---|
| `futex(...)` | **等鎖**(線程競爭、死鎖) |
| `read` / `recvfrom` | 等 IO / 等網路對端發資料 |
| `connect` / `poll` | 等建立連接 / 等事件 |
| 報 `ENOENT` | 找不到檔案(路徑錯、配置缺) |
| 報 `EACCES` | 權限不足 |

> ⚠️ **strace 會大幅拖慢**被跟蹤的進程(每個 syscall 都被 ptrace 攔截)。**生產上慎用、短抓即放**,別 attach 著不管。

---

## 2. `lsof` —— 進程開了哪些檔案 / 連接

| 命令 | 作用 | 底層一兩句 |
|---|---|---|
| `lsof -p PID` | 一個進程開的**所有 fd**(檔案、socket、pipe) | 進程內部「碰著什麼」一覽 |
| `lsof -i :8080` | 誰在用 8080 | 「端口被佔」最快查法(也見 **03**) |
| `lsof -i TCP:ESTABLISHED` | 所有已建立的 TCP 連接 | — |
| `lsof +D /var/log` | 誰在用這個**目錄**下的檔案 | 「umount 說 device busy」時揪元兇 |
| `lsof -u user` | 某使用者開的所有檔案 | — |
| `lsof \| grep deleted` | **已刪除、但仍被進程佔著**的檔案 | 見下面這個經典坑 ↓ |

> **架構師高頻坑**:`df` 顯示磁碟滿了,`du` 卻算不出那麼多空間去哪了。原因常是**「檔案被 `rm` 刪了,但有進程還開著它的 fd」**——空間不會釋放,直到那進程關閉/重啟。`lsof | grep deleted` 一抓就現形(典型:日誌被刪了但服務還寫著)。

---

## 3. `/proc/<pid>/` —— 把進程內部攤成檔案

`/proc` 是內核把**運行時狀態攤成檔案系統**——不用特殊工具,`cat` 就能讀。原語 3「一切皆檔案」的極致。

| 路徑 | 看什麼 |
|---|---|
| `/proc/<pid>/cmdline` | 完整啟動命令(含參數) |
| `/proc/<pid>/environ` | 進程的環境變數(排查「為什麼讀到舊配置」) |
| `/proc/<pid>/cwd` | 工作目錄(symlink,`ls -l` 看) |
| `/proc/<pid>/exe` | 對應的可執行檔(symlink) |
| `ls -l /proc/<pid>/fd/` | 打開的所有 fd(socket、pipe、檔案一覽) |
| `/proc/<pid>/status` | 狀態、RSS、線程數、UID | 
| `/proc/<pid>/limits` | **實際生效**的 ulimit(別只信 shell 裡的 `ulimit -a`) |
| `/proc/<pid>/stack` | 內核棧(需 root)——看卡在內核哪 |

系統級的也在 `/proc`:`/proc/meminfo`、`/proc/loadavg`、`/proc/cpuinfo`、`/proc/net/*`(很多工具其實就是讀它們)。

> 心法:看一個進程**到底用了哪個配置 / 哪個工作目錄 / 開了多少 fd**,直接 `cat /proc/<pid>/...`,比任何工具都直接。

---

## 4. 內核 / 系統日誌

| 命令 | 作用 | 底層一兩句 |
|---|---|---|
| `dmesg -T` | 內核環形緩衝(帶人類時間) | **OOM、IO error、段錯誤、網卡 up/down、丟包**都在這 |
| `dmesg -w` | 跟隨內核訊息 | 邊復現邊看 |
| `journalctl -k` | 內核訊息(**持久化**版的 dmesg) | 重啟後還查得到 |
| `journalctl -u nginx -f` | 跟某個服務的日誌 | 詳見 **07** |
| `journalctl --since "10 min ago" -p err` | 近 10 分鐘的錯誤級日誌 | `-p` 按優先級過濾 |

> 進程**莫名消失/重啟**?三連查:`dmesg -T \| grep -i oom`(被 OOM 殺)→ `journalctl -u 服務`(crash 堆疊)→ `dmesg -T \| grep -i error`(內核層 IO/驅動報錯)。

---

## 5. 「進程卡住不動了」排查組合

```
進程 hang / 不回應
│
├─ 1. ps -o pid,stat,wchan -p PID   狀態？R(在算) / D(卡IO) / S(在等)
├─ 2. strace -p PID                 卡在哪個 syscall？futex=等鎖 read=等IO connect=等連接
├─ 3. cat /proc/PID/stack           （root）內核棧:卡在內核哪個函數
├─ 4. lsof -p PID                   它開著哪些檔案/連接（卡在哪個對端？）
└─ 5. 多線程就鎖定線程：
       top -H -p PID  /  ps -T -p PID     哪條線程在燒/在卡
       strace -f -p PID                   含所有線程
```

> 一句話:**`ps` 定狀態 → `strace` 定 syscall → `/proc/stack` 定內核棧 → `lsof` 定對象。** 四步把「卡住」從「玄學」變成「具體卡在某次 `read`」。

---

## 深挖

- IO、檔案、fd、阻塞/非阻塞的原理 → **`linux-handson/05-io-and-files`**
- 系統性可觀測性(metrics/log/trace、OTel) → **`observability`**
- 進程狀態 `R/S/D`、為什麼 `D` 卡住 → **`01`**、**`02`**
