# 01 · 進程與作業控制

> 放後台、找進程、殺進程、信號、優先級、殭屍。資深日常最高頻的一章。

---

## 收口地圖(記這三條,別背命令)

命令一多就亂——是因為你把它們當「一堆並列的招式」記。其實它們只在回答**三件事**:

1. **放後台 = 回答 2 個問題**
   - ① 我要它**別佔住終端**嗎?→ `&`(啟動時)/ `Ctrl+Z` 再 `bg`(跑到一半)
   - ② 我**斷線/登出後還要它活**嗎?→ 前面加 `nohup`(日常夠用),進階用 `setsid` / `disown`
2. **找 / 殺 = 1 個區分**:線索是**程式名**還是**命令列裡的字串**?後者一律加 `-f`(原語 2)。
3. **信號 = 沿歸屬鏈傳**:`Ctrl+C`/`Ctrl+Z`/斷線 `SIGHUP`/`kill` 整組,都是「對某一層發信號」(原語 1)。

> `&` 給你後台,`nohup` 給你「斷線免疫」,`setsid` 讓你「徹底搬離終端」。三件事,別混。

---

## 1. 放後台 & 作業控制(job control)

| 命令 | 作用 | 底層一兩句 |
|---|---|---|
| `cmd &` | 啟動即放後台 | 進後台進程組,shell 不等它;**但仍綁終端**,斷線會被 `SIGHUP` 殺 |
| `Ctrl+Z` | 把前台任務**掛起**(暫停) | 發 `SIGTSTP`;此刻它是**停住的,不是在跑** |
| `bg %1` | 讓掛起的任務在**後台繼續跑** | `Ctrl+Z` 後真正「放後台執行」的那一步 |
| `fg %1` | 把後台/掛起任務**調回前台** | — |
| `jobs -l` | 列出本 shell 的後台任務(含 PID) | 只看得到**本 shell** 的 job;`setsid`/`disown` 過的看不到 |
| `nohup cmd &` | 後台 + **斷線不死** | **忽略** `SIGHUP`;無終端時 stdout 自動倒進 `nohup.out` |
| `cmd & disown` | 事後補救:讓 shell **別管它** | 從 shell 的 job table 移除 → shell 退出時不發 `SIGHUP` |
| `disown -h %1` | 留在 job table 但標記「別發 HUP」 | 想還能 `jobs` 看到、又要保命時用 |
| `setsid cmd >log 2>&1` | **徹底脫離終端**跑 | 開新 session、無控制終端 → `SIGHUP` 根本送不到(最乾淨) |

**三招「斷線不死」的差別**:`nohup`=裝聾(忽略信號)/ `disown`=叫 shell 別當二傳手 / `setsid`=直接從歸屬鏈上消失。生產長期跑請跳過這些,用 **07 的 systemd**。

> macOS 注意:**沒有 `setsid`**(Linux 專屬)。`nohup`、`&`、`disown` 在 mac 上有。

---

## 2. 找進程

| 命令 | 作用 | 底層一兩句 |
|---|---|---|
| 🔧 `pgrep -af 字串` | 按**命令列**找,並印出完整命令列 | `-f` = 比對整條命令列;`-a` = 印出來肉眼確認 |
| `pgrep -u user 名` | 按使用者 + 程式名找 | — |
| `ps -ef \| grep '[n]ginx'` | 萬用找法(任何欄位) | `[n]ginx` 讓 grep **不匹配自己**(它命令列裡是 `[n]ginx`) |
| 🔧 `ps aux` / `ps -ef` | 列全部進程(兩種風格) | `aux`=BSD 風、`-ef`=System V 風,看慣一種即可 |
| `ps -eo pid,ppid,pgid,sid,tty,stat,comm` | 自訂欄位,看歸屬關係 | 一眼看穿原語 1 的四層:PID/PPID/PGID/SID/TTY |
| `pstree -p` | 進程樹(看父子) | 看清「誰 fork 了誰」,排查孤兒/失控子進程 |
| `top -p PID` / `lsof -p PID` | 盯單一進程的資源 / 開啟的檔案 | `lsof` 詳見 **04** |

> **`ps -C` 只認程式名**(`bash`/`sleep`),不認參數——想用命令列字串找,別用 `-C`,用上面 `grep` 那條。

---

## 3. 殺進程 & 信號

| 命令 | 作用 | 底層一兩句 |
|---|---|---|
| 🔧 `kill PID` | 禮貌終止 | 預設發 `SIGTERM`(15),**可被捕獲**做清理(關連接、flush 日誌) |
| `kill -9 PID` | 強殺 | `SIGKILL`,**不可捕獲/忽略**;但殺不掉 `D`(不可中斷睡眠)與 `Z`(已死) |
| `kill -HUP PID` | 「重載」 | 很多 daemon(nginx)用 `SIGHUP` 觸發**重讀配置**,不是殺 |
| `kill -- -PGID` | 殺**整個進程組** | 負號 = 進程組;一刀帶走「它 fork 的一串子孫」 |
| `pkill -f 字串` | 按命令列批量殺 | 同 `pgrep` 的 `-f`;小心別誤傷 |
| `killall 名` | 按**程式名**殺全部 | Linux 上按名;(注意:某些 Unix 上 `killall` 是「殺所有進程」,別在生產亂用) |
| `kill -l` | 列出所有信號 | 忘了編號就敲這個 |

**常用信號速記**(`kill -名` 或 `-編號`):

| 信號 | 觸發 | 用途 / 特性 |
|---|---|---|
| `TERM`(15) | `kill` 預設 | 禮貌終止,**可捕獲**做善後 —— **優先用這個**,別動不動 -9 |
| `KILL`(9) | `kill -9` | 強殺,內核直接幹掉,進程**來不及善後**(可能丟資料) |
| `INT`(2) | `Ctrl+C` | 中斷前台任務 |
| `QUIT`(3) | `Ctrl+\` | 退出並產生 core dump(調試用) |
| `TSTP`(20) | `Ctrl+Z` | 掛起(**可捕獲**版的暫停) |
| `STOP`(19)/`CONT`(18) | — | 暫停 / 繼續;`STOP` **不可捕獲**(比 Ctrl+Z 更硬) |
| `HUP`(1) | 斷線 | 終端掛斷 → 殺進程;daemon 拿來「重載配置」 |
| `USR1`/`USR2` | — | 程式自定義(如 nginx `USR1` 重開日誌檔) |

> 心法:**先 `TERM`,給它善後機會;真不死再 `-9`。** 直接 `-9` 是「斷電」,可能留下髒資料、半寫檔案。

---

## 4. 看狀態與優先級

`top`(人人有)/ `htop`(更好用,需裝)即時看;`ps` 的 **STAT 欄**看進程狀態:

| STAT | 意思 | 排查含義 |
|---|---|---|
| `R` | 執行中 / 可執行 | 正在用 CPU(或排隊等 CPU) |
| `S` | 可中斷睡眠 | 正常等待(等 IO、等事件),大多數進程平時是這個 |
| `D` | **不可中斷睡眠** | **卡在 IO**!`kill -9` 都殺不掉。一堆 `D` = 磁碟/NFS 出事(見 **02** 的 `wa`) |
| `Z` | 殭屍(defunct) | 已死、等父回收。見下節 |
| `T` | 停止 / 被追蹤 | 被 `Ctrl+Z` 或 debugger 停住 |
| 後綴 `+` `s` `<` `N` `l` | 前台組 / session leader / 高優先 / 低優先 / 多線程 | `s`=會話頭頭、`<`=被調高優先級 |

**優先級(nice 值,-20 最高 ~ 19 最低)**:

| 命令 | 作用 |
|---|---|
| `nice -n 10 cmd` | 用**較低**優先級啟動(對別人客氣,+10) |
| `renice -n 5 -p PID` | 改一個**正在跑**的進程的優先級 |

> `nice` 數字越大越「謙讓」(搶不過別人 CPU)。跑批量/備份任務時設高 nice 值,避免拖垮線上服務。

---

## 5. 殭屍與孤兒(經典面試題)

兩個都源自原語 1 的父子關係,別搞混:

- **孤兒(orphan)**:**父先死**。子進程被**過繼(reparent)**給 `init`(PID 1)/ subreaper。**無害**——它照常跑,只是換了個爹。
- **殭屍(zombie / `Z` / defunct)**:**子先死,但父還沒 `wait()` 回收它的退出碼**。它**已經死了**,只剩一個「PID 槽 + 退出狀態」的空殼佔著進程表。

關於殭屍的三個關鍵事實:

1. **`kill -9` 殺不掉殭屍**——它已經死了,沒有東西可殺。
2. **危害**:佔用 PID 槽。少量無害;**大量殭屍 = 父進程有 bug(沒回收子進程)**,可能耗盡 PID。
3. **怎麼清**:① 讓**父進程**去 `wait()`(通常重啟父進程);② **殺掉父進程**——殭屍被過繼給 `init`,`init` 會立刻 `wait()` 把它回收。

```bash
# 找出所有殭屍(及它們的父進程 PPID —— 真正要修的是父)
ps -eo pid,ppid,stat,comm | awk '$3 ~ /^Z/'
```

> 一句話:**孤兒換爹照樣活;殭屍是「沒人收屍」的空殼,要嘛父進程收,要嘛殺父讓 init 收。**

---

## 🔧 主力命令深講 + 速驗

> 上面是「掃一眼」;這裡把標 🔧 的主力命令展開:好用參數 + 一個能立刻跑的驗證。**先進 README 的沙盒。**

### ps — 看進程的瑞士刀

| 寫法 | 作用 |
|---|---|
| `ps aux` | 全部進程,BSD 風(帶 `%CPU`/`%MEM`/`STAT`) |
| `ps -ef` | 全部進程,SysV 風(帶 `PPID`,看父子) |
| `ps -eo pid,ppid,pgid,sid,tty,stat,comm` | **自訂欄位**,只看你要的 |
| `ps -p PID` | 只看某個 PID |
| `ps --sort=-%cpu \| head` | 按 CPU 降序揪大戶(`-%mem` 同理) |
| `ps -T -p PID` | 看某進程的**線程**(每線程一行) |
| `ps -o pid,ni,pri,comm -p PID` | 看優先級(`ni` nice / `pri`) |

如果看到這種輸出,按欄位這樣讀:

```text
  PID  PPID  PGID   SID TTY      STAT COMMAND
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

**⚡ 驗證**:
```bash
sleep 300 &
ps -o pid,ppid,stat,comm -p $!      # 預期:STAT=S(睡眠),COMMAND=sleep
ps aux --sort=-%mem | head -3       # 預期:表頭 + 記憶體前 2 名
kill $!
```

### pgrep / pkill — 按命令列找與殺

| 寫法 | 作用 |
|---|---|
| `pgrep -af 字串` | 按整條命令列找,印 PID + 命令列 |
| `pgrep -u root sshd` | 限使用者 + 程式名 |
| `pgrep -n / -o 名` | 只要**最新** / **最舊**那一個 |
| `pgrep -c 名` | 只回**數量** |
| `pkill -f 字串` | 按命令列**批量殺** |
| `pkill -TERM -f 字串` | 指定信號殺(預設就是 TERM) |

**⚡ 驗證**:
```bash
sleep 300 &
pgrep -af sleep         # 預期:印出 "<PID> sleep 300"
pkill -f 'sleep 300'    # 殺掉
pgrep -af sleep         # 預期:無輸出(已殺乾淨)
```

### kill — 發信號(不只是「殺」)

`kill` 的「參數」其實就是**信號**(信號表見上)。重點是發「對的信號」:

| 寫法 | 作用 |
|---|---|
| `kill PID` | 發 `TERM`(禮貌終止,可捕獲善後) |
| `kill -9 PID` | 發 `KILL`(強殺,不可捕獲) |
| `kill -HUP PID` | 觸發多數 daemon 的「重載配置」 |
| `kill -- -PGID` | 殺**整個進程組**(負號) |
| `kill -l` | 列出所有信號名 / 編號 |

**⚡ 驗證(親眼看「TERM 可被捕獲、KILL 不行」)**:
```bash
# 開一個「捕獲 TERM」的進程
bash -c 'trap "echo 收到TERM正在善後; exit" TERM; sleep 300' &
sleep 1
kill -TERM $!     # 預期:印出 "收到TERM正在善後" 後才退出 ← 信號被捕獲

# 對比:KILL 攔不住
bash -c 'trap "echo 這行不會印" TERM; sleep 300' &
kill -9 $!        # 預期:直接消失,trap 來不及執行
```

### job control(`&` / `jobs` / `bg` / `fg`)

**⚡ 驗證(放後台 → 查 → 調回 → 掛起 → 再放後台)**:
```bash
sleep 300 &
jobs -l            # 預期:[1]+ <PID> Running  sleep 300
fg %1              # 調回前台(畫面卡住,因 sleep 在前台跑)
#  ↑ 此時按 Ctrl+Z → 預期:[1]+ Stopped  sleep 300(掛起)
bg %1              # 預期:[1]+ sleep 300 &(回後台繼續跑)
kill %1
```
> `fg`/`bg`/`Ctrl+Z` 需**互動式終端**(沙盒裡直接敲沒問題;寫進腳本不行)。

### ⚡ 配角速驗(`nice` / `renice` / `pstree` / `setsid` / 找殭屍)

```bash
# nice / renice:看優先級數字
nice -n 10 sleep 300 &
ps -o pid,ni,comm -p $!        # 預期:NI=10
renice -n 15 -p $!             # 預期:... old priority 10, new priority 15
kill $!

# pstree:當前 shell 的進程樹
pstree -p $$ | head            # 預期:bash(<PID>)─┬─... 樹狀圖

# setsid:看它脫離終端(TTY=?、PPID=1)
setsid sleep 300
ps -o pid,ppid,sid,tty,comm -C sleep   # 預期:有一行 TTY=?、PPID=1
pkill -f 'sleep 300'

# 找殭屍(平時通常沒有;造殭屍的完整實驗見 linux-handson/03 實驗2)
ps -eo pid,ppid,stat,comm | awk '$3 ~ /^Z/'   # 預期:無輸出(沒殭屍才正常)
```

---

## 深挖

- 進程模型、fork/exec、會話/進程組/控制終端的完整原理 → **`linux-handson/03-process-model`**(本章是它的速查/反查層)
- 為什麼一堆 `D` 狀態進程 = IO 出事、`us/sy/wa` 怎麼讀 → **`02 性能與資源排查`**
- `lsof` / `/proc/<pid>` 看一個進程「在幹嘛」 → **`04 觀測內幕`**
