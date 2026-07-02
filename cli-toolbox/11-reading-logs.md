# 11 · 看日誌檔的最佳實踐

> 前面幾章給了看日誌的**零件**:`less`/`tail`(→ 00)、`grep`/`awk`/`jq`(→ 05)、`journalctl`/`dmesg`(→ 04·07)、容器日誌(→ 08)。這章不重教零件,教**把零件串成一條「讀一個日誌檔」的工作流**——出事了,怎麼從一大坨日誌收斂到根因,以及幾個前面沒教、但天天會踩的原語(輪替+壓縮、跨行堆疊、時間窗、request-id 串鏈、JSON 日誌)。

---

## 收口地圖(讀日誌是一條收斂漏斗,不是「打開來看」)

日誌動輒幾十萬行,新手的錯是「`cat` 出來從頭找」。資深的讀法是**一路收斂**:每一步把範圍砍小一個數量級,直到剩下「那一條請求 / 那一段堆疊」。

```text
① 別 cat 大檔      —— 用 less / tail / grep 按需取(cat 10G 卡爆終端 + 沖掉 scrollback)
② 先框時間窗       —— 框到「出事那幾分鐘」,別在全量裡撈(sed/awk 按時間戳切)
③ 抓錨點再擴上下文  —— grep 關鍵字定位「哪一行」,再 -C 看前後(尤其跨行堆疊)
④ 順 ID 串成一條   —— 一個 request-id / trace-id 把散在多行、多服務的同一請求串起來
⑤ 記得會輪替+壓縮  —— 剛才那條錯可能已滾進 app.log.1 / app.log.2.gz,要 zgrep 跨檔搜
```

> 心法:讀日誌的功夫不在「認命令」,在**收斂順序**:**時間窗 → 關鍵字 → 上下文 → 一條請求鏈**。命令(`less`/`grep`/`zgrep`/`jq`)只是每一步的工具。這章就是把這五步各配上工具。

---

## 1. 日誌在哪 + 別 `cat` 大檔

先知道去哪找。系統日誌在 `/var/log`,應用日誌各寫各的(看啟動參數 / 配置)。

| 路徑 | 裝什麼 |
|---|---|
| `/var/log/syslog`(Debian)/ `messages`(RHEL) | 系統綜合日誌 |
| `/var/log/auth.log` / `secure` | 登入 / sudo / SSH |
| `/var/log/nginx/{access,error}.log` | nginx(→ `nginx` track) |
| `/var/log/<app>/` 或 應用自訂路徑 | 應用日誌;不確定就看 `/proc/<pid>/fd`(→ 04)哪個 fd 指向 `.log` |
| `journalctl`(沒有檔案) | systemd 服務日誌走 journald,不落 `/var/log`(→ 07) |

> 找不到應用日誌往哪寫?`ls -l /proc/<pid>/fd | grep '\.log'`——進程開著的 log 檔一抓就現形(原語 3「一切皆檔案」,→ 04)。

**鐵律:別 `cat` 大日誌檔。** `cat app.log` 會把幾十萬行一次噴進終端:卡住、沖掉 scrollback、還可能 `cat` 一個正在寫的檔停不下來。改用按需取:

```text
看最新       tail -n 200 app.log        （不是 cat）
慢慢翻/搜    less app.log               （→ 00:/搜、F 跟隨、&只顯示匹配行)
只要含 X 的  grep X app.log | less      （先砍再看)
即時跟       tail -f app.log            （→ 第 6 節)
```

---

## 2. 輪替 + 壓縮日誌(`zgrep`/`zcat` 家族)

日誌不會無限長進一個檔——`logrotate` 每天/每到某大小就**切一份、把舊的壓縮**。所以「昨天那條錯」很可能**不在 `app.log` 裡**,而在旁邊的輪替檔:

```text
app.log         ← 當前正在寫的
app.log.1       ← 上一份(還沒壓)
app.log.2.gz    ← 更舊,已 gzip
app.log.3.gz
...
```

在**未解壓**的 `.gz` 上直接搜,用 `z` 系列(它們是「先解壓再跑對應命令」的包裝):

| 命令 | 等於 | 幹嘛 |
|---|---|---|
| `zcat f.gz` | `cat`(解壓版) | 印出壓縮檔內容,不落地解壓 |
| `zless f.gz` | `less` | 分頁看壓縮日誌 |
| `zgrep pat f.gz` | `grep` | 在壓縮檔裡搜 |
| `zegrep` / `zfgrep` | `grep -E` / `-F` | 擴展正則 / 固定字串版 |
| `zdiff a.gz b.gz` | `diff` | 比兩個壓縮檔 |

> 關鍵招:**一次跨所有輪替檔搜**(`z` 系列連沒壓縮的檔也照吃):
> ```bash
> zgrep -h 'ERROR' /var/log/app/app.log*    # app.log + app.log.1 + *.gz 全搜
> ```

**兩個真坑:**

1. **glob 排序是字典序,不是時間序**:`app.log*` 展開成 `app.log app.log.1 app.log.10 app.log.2 ...`——`.10` 排在 `.2` **前面**。要跨檔按時間看時心裡有數,別以為輸出是嚴格時間順的。
2. **`tail -f` 會在 rotate 時斷**:它跟的是舊檔的 inode,rotate 後新日誌寫進**新** inode,你就一直盯著死檔。跟「會被輪替的檔」要用 **`tail -F`**(大寫,見第 6 節)。

> 深挖 logrotate 怎麼配(`size`/`daily`/`copytruncate` 的差別、`copytruncate` 為何可能丟幾行)→ `linux-handson` / `07`。

---

## 3. 抓錯誤 + 看上下文(尤其跨行堆疊)

`grep ERROR` 定位到「哪一行」只是第一步——**錯誤的真相常在它前後幾行**,而且一個異常往往**跨很多行**(Java / Python 的 stack trace、`Caused by` 鏈)。只 grep 一行會把整個堆疊漏光。

| 寫法 | 幹嘛 | 讀日誌怎麼用 |
|---|---|---|
| `grep -C 3 ERROR` | 匹配行 + 上下各 3 行 | 看錯誤發生前後的脈絡 |
| `grep -A 20 ERROR` | 匹配行 + **後** 20 行 | 抓整段 stack trace(往下延伸) |
| `grep -B 5 ERROR` | 匹配行 + **前** 5 行 | 看「出錯前做了什麼」 |
| `grep -n ERROR` | 帶行號 | 記住行號,回 `less` 用 `<N>g` 跳過去 |
| `awk '/ERROR/{p=1} p; /^$/{p=0}'` | 從 ERROR 印到**空行** | 堆疊以空行分隔時,精準抓「一整段」 |
| `sed -n '/ERROR/,/^$/p'` | 同上(sed 區間版) | 兩個標記之間整段取出 |

> `grep` 是**逐行**工具,天生看不懂「一個異常跨 6 行」。兩條路:① 知道堆疊大概幾行 → `grep -A N`(簡單粗暴);② 堆疊以空行 / 下一條時間戳為界 → `awk`/`sed` **區間**抓整段(精準)。別試圖用 `grep` 的多行模式硬解,脆弱又難記。

**組合:先數哪種錯最多,再挑一條看整段**(回扣 05 的 top-N 套路):

```bash
# 哪類錯最多(取 ERROR 後的錯誤類型欄,統計 top-N)
grep -h ERROR app.log* | awk '{print $4}' | sort | uniq -c | sort -rn | head
# 鎖定最多那類,挑一次看完整堆疊
grep -A 20 'NullPointerException' app.log | head -30
```

---

## 4. 按時間窗切(先框到「出事那幾分鐘」)

知道「大概 10:03 出事」時,**先把日誌切到那個窗口**,再在裡面搜——比在全量裡 grep 快也乾淨得多。

| 寫法 | 幹嘛 |
|---|---|
| `sed -n '/10:03/,/10:05/p' app.log` | 印出兩個時間標記**之間**的所有行 |
| `awk '$1>="10:03:00" && $1<="10:05:00"' app.log` | 按時間戳欄位範圍過濾(第 1 欄是時間時) |
| `journalctl --since "10:03" --until "10:05"` | systemd 日誌按時間切(→ 07) |
| `journalctl --since "10 min ago" -p err` | 近 10 分鐘的 error 級(→ 04) |

> `sed` 區間 `/起/,/迄/` 靠**字串匹配**框範圍,不真懂時間;`awk` 的 `>=`/`<=` 在時間戳是**零填充、可字典序比較**(`HH:MM:SS`、ISO8601)時才對。所以 `10:03:00` 能比,`9:3:0` 這種不補零的會出錯。

**時區這個隱形坑**:容器 / 伺服器日誌時間戳常是 **UTC**,你本地是 +8——「日誌顯示 02:00 出事」對應你這邊 10:00。跨系統對時間線前先確認每份日誌的時區(看格式有沒有 `Z` / `+00:00`,或 `date -u` 對一下)。**多服務串一條請求時,時區沒對齊會把因果順序看反。**

---

## 5. 順 request-id / trace-id 串成一條請求

一個請求在日誌裡是**散開的**:進來一行、查 DB 一行、報錯一行、返回一行,中間還插著別的請求。把它們**收攏成一條**的鑰匙,是每行都帶的 **request-id / trace-id**(現代框架預設會印;沒有就該加)。

```bash
# 把某條請求的所有行,不管散在哪,全撈出來按序看
grep 'req-abc123' app.log

# 跨多個服務:同一 trace-id 在各服務日誌裡都出現 → 拼出全鏈路
grep -h 'trace-4f2a' svc-a.log svc-b.log svc-c.log | sort   # 按時間戳排(前提:時區已對齊)
```

- **從錯誤反查請求**:先 `grep -B 2 ERROR` 找到出錯行附近的 request-id,再拿那個 id 撈出整條請求,看它一路做了什麼才崩。
- **錯誤分類**:`grep ERROR | awk '{...取錯誤碼...}' | sort | uniq -c | sort -rn`——哪種錯最多、是不是集中在某個 id / 某個下游(回扣 05)。

> 這正是分散式追蹤(distributed tracing)在做的事:給每條請求一個 trace-id 貫穿所有服務。手動 `grep trace-id` 是它的「窮人版」;要系統化(自動串鏈、看每段耗時、可視化)→ `observability` track 的 trace 章。**日誌裡有沒有一以貫之的 request-id,是「能不能排查」的分水嶺。**

---

## 6. 實時跟 + 多檔

事情**正在發生**時,邊復現邊看:

| 寫法 | 幹嘛 | 底層一兩句 |
|---|---|---|
| `tail -f app.log` | 跟隨新增行 | 跟的是**inode**;rotate 後會卡在死檔 |
| `tail -F app.log` | 跟隨**檔名** | rotate / 重建後自動追新檔(跟會輪替的檔用這個) |
| `tail -f a.log b.log` | 同時跟多檔 | 切換檔時印 `==> b.log <==` 分隔頭 |
| `tail -f app.log \| grep --line-buffered ERROR` | 邊跟邊過濾 | **必加 `--line-buffered`**,否則管道緩衝住、看不到即時輸出(回扣 05) |
| `less +F app.log` | `less` 的跟隨模式 | `Ctrl+C` 退回普通瀏覽、可上下搜,再按 `F` 繼續跟(→ 00) |
| `journalctl -u svc -f` | 跟服務日誌 | → 07 |
| `docker logs -f C` / `kubectl logs -f pod` | 跟容器 / Pod 日誌 | → 08 |

> `tail -f` 跟 inode、`tail -F` 跟檔名——**排查會被 logrotate 輪替的檔,一律用 `-F`**,不然你盯著的是已被移走的舊檔,新日誌一行都看不到。`less +F` 的好處是能隨時 `Ctrl+C` 停下來往回搜,比 `tail -f` 只能一直往下滾靈活。

---

## 7. JSON / 結構化日誌

現代服務常輸出**每行一個 JSON**(JSON Lines / JSONL):`{"ts":...,"level":"error","msg":...,"trace":...}`。這種**別用 `grep` 硬撈**——用 `jq` 按欄位過濾,乾淨又能組合(回扣 05 的 jq 節):

```bash
# 只看 error 級,印出訊息
jq -r 'select(.level=="error") | .msg' app.jsonl
# 順一條 trace 把該請求所有行串起來
jq -c 'select(.trace=="4f2a")' app.jsonl
# 統計各級別數量(結構化日誌算 top-N 更準)
jq -r '.level' app.jsonl | sort | uniq -c | sort -rn
```

| 場景 | 用 | 為什麼 |
|---|---|---|
| 每行合法 JSON(JSONL) | `jq 'select(...)'` | 按欄位精準過濾,不怕欄位順序 / 內含空格 |
| 純文字日誌 | `grep` / `awk` | 沒結構,只能靠字串 / 欄位位置 |
| **混雜**(有的行 JSON、有的純文字) | `jq -R 'fromjson? // empty'` | `-R` 讀原始行,`fromjson?` 解析失敗就丟掉,避免 jq 整個報錯中止 |

> 坑:對「不是每行都合法 JSON」的檔直接 `jq '...'` 會在第一個非 JSON 行**報錯中止**。混雜日誌先用 `jq -R 'fromjson? // empty'` 濾出能解析的,或先 `grep '^{'` 只留 JSON 行。

---

## 🔧 主力命令深講 + 速驗

> 以下全部**在拋棄式沙盒裡自給自足**(只用檔案 + `gzip` + `grep`/`awk`/`sed`/`jq`,沙盒已裝)。每段先造樣本,再跑,對照 `# 預期:`。

### zgrep / zcat — 跨輪替 + 壓縮檔搜

| 寫法 | 作用 |
|---|---|
| `zcat f.gz` | 印壓縮檔內容(不落地) |
| `zgrep pat f.gz` | 在壓縮檔裡 grep |
| `zgrep -h pat app.log*` | 跨所有輪替檔搜(連沒壓的也吃)、`-h` 不印檔名 |
| `zless f.gz` | 分頁看壓縮日誌 |

**⚡ 驗證(造輪替+壓縮日誌,一次跨檔搜):**
```bash
cd /tmp && rm -f app.log*
printf 'INFO start\nERROR db timeout\nINFO ok\n' > app.log
printf 'INFO old\nERROR disk full\n'             > app.log.1
printf 'INFO older\nERROR oom killed\n' | gzip    > app.log.2.gz

zcat app.log.2.gz          # 預期:INFO older / ERROR oom killed(直接印被壓縮的內容)
zgrep ERROR app.log*       # 預期:三檔各一行 ERROR,前面帶檔名:
                           #   app.log:ERROR db timeout
                           #   app.log.1:ERROR disk full
                           #   app.log.2.gz:ERROR oom killed
```

### grep -A/-B/-C — 抓錯誤上下文(跨行堆疊)

| 寫法 | 作用 |
|---|---|
| `grep -A N pat` | 匹配行 + 後 N 行(抓 stack trace) |
| `grep -B N pat` | 匹配行 + 前 N 行(看出錯前脈絡) |
| `grep -C N pat` | 前後各 N 行 |

**⚡ 驗證(造跨行堆疊,對比單行 grep 漏掉整段):**
```bash
cd /tmp
cat > trace.log <<'EOF'
INFO  request started
ERROR unhandled exception
    at com.foo.Bar.run(Bar.java:42)
    at com.foo.App.main(App.java:10)
Caused by: java.lang.NullPointerException
INFO  request done
EOF

grep ERROR trace.log       # 預期:只有 "ERROR unhandled exception" 一行 ← 堆疊全漏!
grep -A 4 ERROR trace.log  # 預期:ERROR 那行 + 後 4 行(整段 stack trace + Caused by)
```

### sed / awk 時間窗 — 切「出事那幾分鐘」

| 寫法 | 作用 |
|---|---|
| `sed -n '/起/,/迄/p'` | 印兩個標記之間的行(字串匹配框範圍) |
| `awk '$1>="A" && $1<="B"'` | 按第 1 欄範圍過濾(時間戳零填充才對) |

**⚡ 驗證(造帶時間戳日誌,兩種切法):**
```bash
cd /tmp
cat > ts.log <<'EOF'
10:00:01 INFO boot
10:03:12 WARN slow query
10:04:55 ERROR timeout
10:07:30 INFO recovered
EOF

sed -n '/10:03/,/10:05/p' ts.log            # 預期:10:03:12 WARN / 10:04:55 ERROR 兩行
awk '$1>="10:03:00" && $1<="10:05:00"' ts.log  # 預期:同上兩行(靠零填充時間戳可比大小)
```

### jq — 過濾 JSON 日誌

| 寫法 | 作用 |
|---|---|
| `jq 'select(.level=="error")'` | 按欄位過濾 |
| `jq -r '.msg'` | raw 取欄位(去引號) |
| `jq -R 'fromjson? // empty'` | 混雜日誌:解析失敗的行丟掉,不中止 |

**⚡ 驗證(造 JSONL,按級別 / 按請求過濾):**
```bash
cd /tmp
cat > app.jsonl <<'EOF'
{"ts":"10:00:01","level":"info","msg":"start","req":"r1"}
{"ts":"10:00:02","level":"error","msg":"db timeout","req":"r1"}
{"ts":"10:00:03","level":"info","msg":"ok","req":"r2"}
EOF

jq -r 'select(.level=="error") | .msg' app.jsonl  # 預期:db timeout
jq -c 'select(.req=="r1")' app.jsonl              # 預期:r1 的兩行(start / db timeout)
```

### ⚡ 配角速驗(`grep` 串 request-id / `tail -F` 語義)

```bash
cd /tmp
printf 'req-1 start\nreq-2 start\nreq-1 db\nreq-1 done\n' > multi.log
grep 'req-1' multi.log     # 預期:req-1 的 3 行(start / db / done)——散開的請求收攏成一條

# tail -F(跟檔名,rotate 後追新檔)vs tail -f(跟 inode,rotate 後卡死檔)
# 實跑要另開 shell:mv multi.log multi.log.1 後再新建 multi.log 寫入
#   tail -f  → 卡在被 mv 走的舊檔,新的看不到
#   tail -F  → 自動追到新建的 multi.log(排查會輪替的檔用這個)
```

---

## 🎯 練習場:模擬日誌流 + 排查 drill

> 上面的 ⚡ 驗證都是**靜態檔**——能測「命令對不對」,但測不到讀日誌真正難的部分:**一堆請求交錯、噪音刷屏時,即時撈出那一條**。這節給一個**會不斷打印日誌的產生器**,讓你在沙盒裡練「活的」排查——這是讀日誌唯一練得出手感的方式,靜態檔給不了。

**① 起一個模擬服務**(貼進沙盒,建議在 `tmux` 開兩個 pane,一個跑產生器、一個排查):

```bash
cat > /tmp/loggen.sh <<'EOF'
#!/usr/bin/env bash
# 模擬服務日誌:多個 request 交錯、ERROR 偶帶多行堆疊。寫到 stdout + /tmp/app.log。
# FMT=json 改輸出 JSONL(每行一個 JSON)。Ctrl+C 停。
LOG=/tmp/app.log
reqs=(req-1a req-2b req-3c req-4d); lvls=(INFO INFO INFO INFO WARN ERROR)
msgs=("request started" "db query ok" "cache hit" "cache miss" \
      "slow query 1200ms" "db timeout" "upstream 502")
while true; do
  ts=$(date +%H:%M:%S)
  req=${reqs[$((RANDOM%${#reqs[@]}))]}; lvl=${lvls[$((RANDOM%${#lvls[@]}))]}
  msg=${msgs[$((RANDOM%${#msgs[@]}))]}
  if [ "$FMT" = json ]; then
    printf '{"ts":"%s","level":"%s","req":"%s","msg":"%s"}\n' "$ts" "$lvl" "$req" "$msg" | tee -a "$LOG"
  else
    echo "$ts $lvl [$req] $msg" | tee -a "$LOG"
    [ "$lvl" = ERROR ] && printf '    at com.foo.Svc.call(Svc.java:%d)\n    at com.foo.App.main(App.java:10)\nCaused by: java.lang.NullPointerException\n' $((RANDOM%200)) | tee -a "$LOG"
  fi
  sleep 0.3
done
EOF
bash /tmp/loggen.sh          # 純文字模式;JSON 模式改:FMT=json bash /tmp/loggen.sh
```

**② 另一個 pane 練這幾題**(先自己想命令,卡住再看答案):

| # | 任務 | 答案 |
|---|---|---|
| 1 | 即時只盯 ERROR + 它後面那段堆疊 | `tail -F /tmp/app.log \| grep -A3 --line-buffered ERROR` |
| 2 | 挑一個 request-id,串出它做過的所有事 | `grep 'req-2b' /tmp/app.log`(id 換成你看到的) |
| 3 | 哪個 level 出現最多(top-N) | `awk '{print $2}' /tmp/app.log \| sort \| uniq -c \| sort -rn` |
| 4 | 把最近某一分鐘切出來 | `sed -n '/10:03/,/10:04/p' /tmp/app.log`(時間換成你的) |
| 5 | 手動輪替 + 壓縮,再跨檔搜 ERROR | 見下 ↓ |

**③ Drill 5(輪替 + `tail -F` 的殺手鐧,最值得練)**:

```bash
# 產生器還在跑。手動 rotate:把當前檔搬走並壓縮
mv /tmp/app.log /tmp/app.log.1 && gzip /tmp/app.log.1
# 產生器的 tee -a 會自動重建 /tmp/app.log 繼續寫
zgrep -h ERROR /tmp/app.log*       # 預期:跨新 app.log + app.log.1.gz 一次搜到所有 ERROR
```

> 這一步同時把第 2 / 6 節那兩個坑**跑給你看**:rotate 後,`tail -f`(小寫)卡在被搬走的死檔、新的一行都看不到;`tail -F`(大寫)才追上重建的 `/tmp/app.log`。開兩個 pane 各跑一個 `tail -f` / `tail -F` 對照,一眼看懂差別。
>
> **JSON 模式**練 jq:`FMT=json bash /tmp/loggen.sh` 起,另一 pane 跑
> `tail -F /tmp/app.log | jq -R 'fromjson? // empty | select(.level=="error")'`——即時只挑出 error 級的 JSON 行。
>
> 玩完清掉:`rm -f /tmp/app.log* /tmp/loggen.sh`。

---

## 深挖

- `less`(`/`搜 / `F` 跟隨 / `&` 只顯示匹配行)、`tail -f`、`tee` 的機制 → **`00`**
- `grep`/`awk`/`sed`/`sort|uniq`/`jq` 完整參數 → **`05`**
- `journalctl`(系統/服務日誌)、`dmesg`(內核日誌)、OOM 三連查 → **`04`**、**`07`**
- 容器 / Pod 日誌(`docker logs`、`kubectl logs`) → **`08`**
- 結構化日誌怎麼**寫**(欄位設計、request-id 注入、log level) → **`logging`** track
- 系統化 trace / 日誌收集 / 集中查詢(ELK、Loki、OTel) → **`observability`**、**`log-collection`**
- `logrotate` 配置與 `copytruncate` 取捨 → **`linux-handson`**
