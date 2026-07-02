# 00 · CLI 生存包

> 這章不是 Linux 入門大全，也不是 shell 腳本手冊。它收的是資深工程師 / 架構師每天在終端裡反覆用到、但不屬於某一個排查章節的操作原語。
>
> 先會這些，再進 `CORE-SET.md` 的 6 類排查命令，整個 CLI 工作流才接得起來。

---

## 收口地圖

日常 CLI 生存層只回答 9 件事：

```text
① 怎麼裝工具        apt / dpkg
② 我到底在跑誰      type / command -v / which
③ 工作現場怎麼保留  tmux / history
④ 輸出怎麼看        less / tail / watch / tee
⑤ shell 怎麼接線    $? / > / 2>&1 / |
⑥ 腳本怎麼跑        sh / bash / ./ / source（誰解釋·開不開新進程）
⑦ 東西怎麼打包      tar / gzip / zip
⑧ 我是誰、怎麼變身份  date / id / env / sudo / su
⑨ 資訊從哪來        /etc /proc /sys /var/log
```

> 心法：先把「終端現場、輸入輸出、命令來源、工具安裝」穩住，再談排查。

---

## 1. 套件與工具安裝：apt / dpkg

| 命令 | 幹嘛 | 肌肉記憶 |
|---|---|---|
| `apt update` | 更新套件索引 | 不是升級軟體，只是刷新「有哪些包/版本」 |
| `apt install tmux` | 安裝套件 | 容器/腳本常用 `-y` 自動確認 |
| `apt search strace` | 搜套件 | 不確定包名時先搜 |
| `apt show strace` | 看套件資訊 | 描述、版本、依賴、大小 |
| `apt policy tmux` | 看版本來源 | 已裝版本 / 候選版本 / repo 來源 |
| `apt list --installed` | 列已安裝套件 | 配 `grep` 找特定包 |
| `apt remove tmux` | 移除程式 | 通常保留設定 |
| `apt purge tmux` | 移除程式與設定 | 想清乾淨才用 |
| `apt autoremove` | 清不再需要的依賴 | 大升級後或移除包後用 |
| `dpkg -L tmux` | 看包裝了哪些檔案 | 回答「這個包放了什麼」 |
| `dpkg -S /usr/bin/tmux` | 反查檔案屬於哪個包 | 回答「這個 binary 誰裝的」 |

> 坑：`apt update` ≠ `apt upgrade`。前者只更新索引；後者會真的升級已安裝套件。容器工具箱裡通常沒事，正式機器不要把 `upgrade` 當反射動作。
>
> 權限：容器裡是 root 通常可直接跑；一般 VM / 主機可能要加 `sudo`，例如 `sudo apt update`、`sudo apt install -y tmux`。

**速驗：**

```bash
apt update
apt install -y tmux procps iproute2 curl
tmux -V
dpkg -L tmux | head
dpkg -S "$(command -v tmux)"
```

---

## 2. 命令來源與存在性：type / command -v / which

| 命令 | 幹嘛 | 肌肉記憶 |
|---|---|---|
| `type cd` | 看 shell 如何解析命令 | 能看出 builtin / alias / function / binary |
| `command -v python3` | 腳本裡檢查命令是否存在 | 比 `which` 更適合腳本 |
| `which python3` | 找 binary 路徑 | 熟悉但不一定看得到 alias/function |
| `whereis nginx` | 找 binary / source / man 路徑 | 粗略定位安裝位置 |

> 收口：互動排查先用 `type`，腳本判斷用 `command -v`，只想找 binary 路徑再用 `which`。

**速驗：**

```bash
type cd
type ls
command -v bash
which bash
```

典型判讀：

```text
cd is a shell builtin       # 不是 /usr/bin/cd
ls is /usr/bin/ls           # 真正 binary
bash -> /usr/bin/bash       # command -v / which 都可能印這個
```

---

## 3. 終端工作現場：tmux / history

| 命令 / 按鍵 | 幹嘛 | 肌肉記憶 |
|---|---|---|
| `tmux new -s main` | 建一個可重連工作現場 | SSH / 容器 / 長任務先開 |
| `Ctrl+b d` | detach，離開但不停止 | 先按 `Ctrl+b`，放開，再按 `d` |
| `tmux ls` | 看有哪些 session | 找 session 名稱 |
| `tmux attach -t main` | 接回工作現場 | 回到原 shell、輸出、前台程式 |
| `history` | 看命令歷史 | 追剛剛做了什麼 |
| `Ctrl+r` | 反向搜尋歷史 | 找以前敲過的長命令 |
| `!!` | 重跑上一條命令 | 常見是 `sudo !!` |

> `tmux` 保的是「整個終端工作現場」；`nohup cmd &` 保的是「單個後台命令」。想斷線後還能回到前台互動，標準答案是先進 `tmux`。

不適合用 `tmux` 的情況：

```text
正式長期服務     -> systemd / Docker / Kubernetes
單個非互動長命令 -> nohup cmd >out.log 2>&1 &
幾秒鐘短命令     -> 直接跑
```

**速驗：**

```bash
tmux new -s demo
# 在 tmux 裡執行: sleep 300
# 按 Ctrl+b d detach
tmux ls
tmux attach -t demo
# 回到 tmux 後按 Ctrl+C 停止 sleep，再 exit 關掉 demo session
```

---

## 4. 看輸出與追蹤變化：less / tail / watch / tee

| 命令 | 幹嘛 | 肌肉記憶 |
|---|---|---|
| `less file` | 分頁看大檔 | `/關鍵詞` 搜，`n` 下一個，`q` 離開 |
| `head -n 20 file` | 看前 20 行 | 快速看格式 |
| `tail -n 50 file` | 看最後 50 行 | 看最近輸出 |
| `tail -f app.log` | 跟 log | 服務排查高頻 |
| `watch -n 1 'ss -tlnp'` | 每秒重跑命令 | 觀察狀態變化 |
| <code>cmd &#124; tee out.log</code> | 邊看輸出邊存檔 | 保留現場證據 |
| <code>cmd 2&gt;&amp;1 &#124; tee out.log</code> | stdout/stderr 都保存 | 排查失敗命令時用 |

> `less` 是「慢慢看」，`tail -f` 是「跟著看」，`watch` 是「反覆看」，`tee` 是「邊看邊留證據」。

### `less` 快速查日誌快捷鍵

`less` 適合看大 log：不會一次把整個檔案打滿螢幕，能跳、搜、追新增。

| 按鍵 / 寫法 | 幹嘛 | 查日誌怎麼用 |
|---|---|---|
| `q` | 離開 | 退出 `less` |
| `Space` / `f` | 下一頁 | 往後看 |
| `b` | 上一頁 | 往前翻 |
| `d` / `u` | 下 / 上半頁 | 比整頁更細地掃 |
| `g` | 跳到檔案開頭 | 看啟動時最早的錯誤 |
| `G` | 跳到檔案結尾 | 先看最新日誌 |
| `/pattern` | 往後搜尋 | 從目前位置往後找 `ERROR` / request id |
| `?pattern` | 往前搜尋 | 在檔尾往前找最近一次錯誤 |
| `n` | 下一個匹配 | 沿著剛才搜尋方向繼續找 |
| `N` | 反方向匹配 | 搜過頭時往回找 |
| `&pattern` | 只顯示匹配行 | 快速只看含 `ERROR` 的行；`&` 後直接 Enter 取消 |
| `F` | 跟隨檔案新增 | 類似 `tail -f`；按 `Ctrl+C` 回到普通瀏覽 |
| `h` | 幫助 | 忘快捷鍵時查 |

常用啟動方式：

```bash
less -N app.log             # 顯示行號
less -S app.log             # 長行不自動換行，左右方向鍵橫向看
less -R app.log             # 保留彩色輸出(ANSI color)
less +G app.log             # 一打開就跳到檔尾
less +F app.log             # 一打開就進入 follow 模式，像 tail -f
less -N -S +G app.log       # 查大日誌常用：行號 + 不換行 + 從最新開始
```

查日誌的肌肉記憶：

```text
先看最新：less -N -S +G app.log
從尾部往前找錯：?ERROR
繼續找上一個：n
只看錯誤行：&ERROR
跟新日誌：F
停止跟隨：Ctrl+C
離開：q
```

**速驗：**

```bash
printf 'one\ntwo\nthree\n' > /tmp/demo.log
less /tmp/demo.log                # q 離開 less
tail -f /tmp/demo.log             # Ctrl+C 停止 tail -f
# 另開一個 shell: echo four >> /tmp/demo.log
watch -n 1 'date; tail -n 3 /tmp/demo.log'  # Ctrl+C 停止 watch
```

---

## 5. Shell 基本原語：退出碼、重定向、管道、環境變數

| 寫法 | 幹嘛 | 肌肉記憶 |
|---|---|---|
| `$?` | 上一條命令退出碼 | `0` 成功，非 0 失敗 |
| `cmd > out.txt` | stdout 覆寫到檔案 | 只收標準輸出 |
| `cmd >> out.txt` | stdout 追加到檔案 | 不覆蓋舊內容 |
| `cmd 2> err.txt` | stderr 寫到檔案 | 只收錯誤輸出 |
| `cmd >out.txt 2>&1` | stdout/stderr 都進同一檔 | 順序很重要 |
| <code>cmd1 &#124; cmd2</code> | 左邊 stdout 接右邊 stdin | 管道只接 stdout |
| `VAR=value cmd` | 只給這次命令的環境變數 | 不污染當前 shell |
| `export VAR=value` | 給當前 shell 與子進程 | 後續命令都看得到 |

> 三條線要分清：stdin 是輸入，stdout 是正常輸出，stderr 是錯誤輸出。管道 `|` 預設只接 stdout，不接 stderr。

### 重定向 / tee 速記

先記 fd 編號：

```text
0 = stdin   標準輸入
1 = stdout  標準輸出
2 = stderr  標準錯誤
```

重定向是在命令啟動前，先把某條 fd 改接到別的地方：

| 寫法 | 等價理解 | 常見用途 |
|---|---|---|
| `cmd > out.log` | `cmd 1> out.log` | 只保存正常輸出，覆寫檔案 |
| `cmd >> out.log` | `cmd 1>> out.log` | 只保存正常輸出，追加到檔尾 |
| `cmd 2> err.log` | fd 2 接到錯誤檔 | 正常輸出仍在螢幕 |
| `cmd > out.log 2> err.log` | fd 1 / fd 2 分開接 | 正常與錯誤分開留 |
| `cmd > all.log 2>&1` | 先讓 fd 1 去檔案，再讓 fd 2 複製 fd 1 | 正常與錯誤都進同一檔 |
| `cmd >/dev/null 2>&1` | 正常與錯誤都丟掉 | cron / 腳本裡靜音 |

`2>&1` 最容易誤會：它不是「永遠跟著 stdout」，而是「把 stderr 接到 stdout **此刻**指向的位置」。所以順序不同，結果不同：

```bash
cmd > all.log 2>&1
# fd1 -> all.log
# fd2 -> fd1 此刻的位置，也就是 all.log
# 結果：stdout/stderr 都進 all.log

cmd 2>&1 > all.log
# fd2 -> fd1 此刻的位置，也就是螢幕
# fd1 -> all.log
# 結果：stdout 進 all.log，stderr 還在螢幕
```

管道 `|` 只接 stdout。也就是 `cmd | grep error` 只會把 fd 1 交給 `grep`，fd 2 仍然直接打到螢幕。想把錯誤也送進管道，要先合併：

```bash
cmd 2>&1 | grep error
# bash / zsh 也可寫：cmd |& grep error
```

`tee` 的意思是「T 字分流」：從 stdin 讀，一份寫到螢幕，一份寫到檔案，且 stdout 會繼續往後流。

| 寫法 | 幹嘛 |
|---|---|
| <code>cmd &#124; tee out.log</code> | 邊看 stdout，邊保存 stdout |
| <code>cmd 2&gt;&amp;1 &#124; tee all.log</code> | 邊看 stdout/stderr，邊保存兩者 |
| <code>cmd &#124; tee -a out.log</code> | 追加保存，不覆蓋 |
| <code>cmd &#124; tee raw.log &#124; grep error</code> | 中途留原始輸出，後面繼續處理 |

`sudo tee` 是另一個高頻坑：`sudo echo hi > /etc/file` 常常失敗，因為 `>` 是目前 shell 先處理，沒有 sudo 權限。要讓「寫檔」這一步也帶 sudo，用：

```bash
echo '127.0.0.1 demo.local' | sudo tee -a /etc/hosts
echo value | sudo tee /etc/some.conf >/dev/null
```

第二行最後的 `>/dev/null` 是把 `tee` 原本會印回螢幕的那份輸出丟掉；檔案仍然會寫。

**速驗：**

```bash
false
echo $?

sh -c 'echo out; echo err >&2' > /tmp/out.txt 2> /tmp/err.txt
cat /tmp/out.txt
cat /tmp/err.txt

sh -c 'echo out; echo err >&2' > /tmp/all.txt 2>&1
cat /tmp/all.txt

sh -c 'echo out; echo err >&2' 2>&1 > /tmp/order.txt
cat /tmp/order.txt

sh -c 'echo out; echo err >&2' 2>&1 | tee /tmp/tee-all.txt
cat /tmp/tee-all.txt

FOO=bar sh -c 'echo "$FOO"'
echo "$FOO"
```

預期重點：

```text
false 的退出碼是 1
out.txt 只有 out
err.txt 只有 err
all.txt 同時有 out 和 err
order.txt 只有 out，err 仍然打到螢幕
tee-all.txt 同時有 out 和 err，且剛剛螢幕也看得到
FOO=bar cmd 不會永久寫進目前 shell
```

---

## 6. 跑一個腳本：sh / bash / ./ / source

同一個 `foo.sh`，你有四種跑法，結果可能天差地別——搞混就會遇到「明明能跑，換個方式就報錯」「腳本裡 `cd` 了但我還在原地」「加了 `#!/bin/bash` 還是被擋」。抓兩個問題就全通：**① 誰來解釋這個腳本？② 開不開新進程（腳本的改動留不留在我的 shell）？**

| 跑法 | 誰解釋 | 開新進程？ | 要 exec bit + shebang？ |
|---|---|---|---|
| `./foo.sh` | **shebang 第一行**決定 | 開（fork 子 shell） | **兩個都要**：沒 `chmod +x` → `Permission denied`；沒 shebang → 用當前 shell |
| `bash foo.sh` | 你指定的 `bash` | 開（fork 子 shell） | 都不用：**忽略 shebang、不看 exec bit** |
| `sh foo.sh` | 你指定的 `sh`（常是 dash） | 開（fork 子 shell） | 都不用；但 `sh` ≠ `bash`，bashism 會炸（見下） |
| `source foo.sh` / `. foo.sh` | **當前 shell 自己** | **不開**，在你這個 shell 裡跑 | 都不用 |

**兩軸看穿：**

```text
軸一「誰解釋」：
  ./foo.sh        → 看 shebang（#!/bin/bash 就 bash，#!/bin/sh 就 sh）
  bash/sh foo.sh  → 命令列寫死的那個，shebang 被【忽略】

軸二「開不開新進程」：
  ./ 、bash 、sh  → fork 子 shell 跑，腳本裡 cd / export / 改變數，做完隨子 shell 消失
  source / .      → 在當前 shell 裡跑，cd / export / 變數改動【會留下來】
```

> **為什麼設環境的腳本要 `source`**：`./env.sh` 裡 `export FOO=bar`，跑完 `FOO` 沒了（它在子 shell 裡）。要讓 `export`/`cd`/`alias` 生效在**你當前的 shell**，必須 `source env.sh`（或 `. env.sh`）。這正是 `. ~/.bashrc`、`source venv/bin/activate` 用 `source` 的原因。

### sh ≠ bash：別把 bash 腳本用 sh 跑

`sh` 在多數 Linux（Debian/Ubuntu）其實是 **dash**——精簡的 POSIX shell，**不是 bash**。很多你以為理所當然的語法（bashism）在 `sh` 下直接報錯：

| bash 有、`sh`(dash) 沒有 | 典型報錯 |
|---|---|
| 陣列 `arr=(a b c)` / `${arr[0]}` | `Syntax error: "(" unexpected` |
| `[[ ... ]]`（而非 `[ ... ]`） | `[[: not found` |
| `$RANDOM`、`{1..5}` 序列 | 展不開、當字面字串 |
| `${var/old/new}` 字串替換 | `Bad substitution` |
| process substitution `<(cmd)` | `Syntax error` |
| `local`、`function name {}` 寫法 | 視情況報錯 |

> **第 11 章練習場的 `loggen.sh` 就是活例子**：它用了陣列 `reqs=(...)`、`$RANDOM`、`${#reqs[@]}`——全是 bashism。所以那裡叫你 `bash /tmp/loggen.sh`，不是 `sh`；用 `sh` 會當場 `Syntax error: "(" unexpected`。

**你之前踩過的相關坑**：在 `zsh` / `sh` 裡跑腳本，**word-splitting（把變數按空白拆成參數）行為和 bash 不同**——同一段迴圈拆法不一樣，結果靜默不對。**要重現「Linux 上 bash 的行為」，就顯式 `bash script.sh`**，別靠當前互動 shell（可能是 zsh / dash）去跑。

### shebang：`./` 跑法的「用誰解釋」寫在第一行

```bash
#!/usr/bin/env bash   # 推薦：去 PATH 找 bash（跨系統，mac/Linux bash 位置不同）
#!/bin/bash           # 寫死路徑，少數系統 bash 不在 /bin
#!/bin/sh             # 明示只用 POSIX 語法，別放 bashism
```

> `./foo.sh` 才看 shebang；`bash foo.sh` / `sh foo.sh` **無視 shebang**（你已在命令列指定解釋器了）。所以「加了 `#!/bin/bash` 卻還是被 dash 語法擋」的常見原因，就是你用 `sh foo.sh` 跑，把 shebang 蓋掉了。

**速驗**（在沙盒 Ubuntu 裡，`sh` = dash）：

```bash
cat > /tmp/arr.sh <<'EOF'
#!/usr/bin/env bash
a=(one two three)
echo "${a[1]}"
EOF

bash /tmp/arr.sh          # 預期：two
sh /tmp/arr.sh            # 預期：Syntax error: "(" unexpected（dash 無陣列）
chmod +x /tmp/arr.sh
/tmp/arr.sh               # 預期：two（shebang 是 env bash，已加 exec bit）

# source vs 子 shell：改動留不留在當前 shell
printf 'export FOO=bar\ncd /tmp\n' > /tmp/env.sh
bash   /tmp/env.sh; echo "FOO=[$FOO] PWD=[$PWD]"   # 預期：FOO=[] 且 PWD 沒變（子 shell 改的沒留下）
source /tmp/env.sh; echo "FOO=[$FOO] PWD=[$PWD]"   # 預期：FOO=[bar] PWD=/tmp（在當前 shell 生效）
```

預期重點：

```text
bash arr.sh   → two           bash 支援陣列
sh   arr.sh   → Syntax error   dash 不支援 bashism
./arr.sh      → two            看 shebang（env bash）+ 需先 chmod +x
bash env.sh   → 改動丟失        子 shell 跑，export/cd 隨它消失
source env.sh → 改動保留        當前 shell 跑
```

---

## 7. 壓縮與搬運：tar / gzip / zip

| 命令 | 幹嘛 | 肌肉記憶 |
|---|---|---|
| `tar -czf app.tgz app/` | 打包目錄並 gzip 壓縮 | `c` create，`z` gzip，`f` file |
| `tar -tzf app.tgz` | 只看內容不解壓 | 解壓前先看一眼 |
| `tar -xzf app.tgz` | 解包 | `x` extract |
| `gzip file` | 壓縮單檔成 `file.gz` | 原檔會被替換 |
| `gunzip file.gz` | 解 gzip 單檔 | 還原單檔 |
| `zip -r app.zip app/` | 打 zip | 跨平台傳給別人常用 |
| `unzip app.zip` | 解 zip | — |

> `tar` 是打包，`gzip` 是壓縮。`.tar.gz` / `.tgz` 通常表示「先 tar 打包，再 gzip 壓縮」。

**為什麼 tar 不自己壓縮**：gzip / xz / zstd 這類壓縮器，輸入輸出都是**單一位元組流**，不懂「目錄」「多個檔案」「符號連結」是什麼。要壓一整個目錄，得先有人把「一堆檔案 + 目錄結構 + 權限 / 屬主 / 時間戳」縫成一條流——這正是 tar 的活。所以分工是：**tar 管打包並保留檔案系統中繼資料，壓縮器管把流壓小**，合起來才是 `.tar.gz`。這也是「明明不壓縮還天天用」的原因。

### tar 能配哪些壓縮器

tar 只負責打包，壓縮是外掛一個壓縮器，換 flag 就換格式：

| 壓縮器 | 打包 flag | 副檔名 | 特點 |
|---|---|---|---|
| 無(只打包) | (無) | `.tar` | 不壓，純縫合；docker save、管道傳輸用 |
| gzip | `-z` | `.tar.gz` / `.tgz` | 最通用、快、率一般。預設選它 |
| bzip2 | `-j` | `.tar.bz2` | 比 gzip 小一點、慢，現在少用 |
| xz | `-J` | `.tar.xz` | 率高、慢、吃記憶體。發布源碼常用 |
| zstd | `--zstd` | `.tar.zst` | 現代首選：接近 xz 的率 + 接近 gzip 的速 |
| lz4 | `--lz4` | `.tar.lz4` | 極快、率低。CPU 便宜時間貴時圖快 |

> 記法：小寫 `-z -j -J` 是老三樣(gz / bz2 / xz)；新的 zstd / lz4 用長選項 `--zstd` / `--lz4`。解包不用記——現代 GNU tar 會自動偵測格式，`tar -xf app.tar.zst` 直接解。

### 日常怎麼選：tar.gz / zip / gzip

問三個問題就定了：

```text
① 給誰?
   Linux 機器 / 腳本 / 自己     -> tar.gz(保目錄+權限,到處解得開)
   Windows / Mac 人、放網站     -> zip(跨平台、能雙擊點開抽單檔)
   團隊都裝 zstd、要壓更狠       -> tar.zst

② 壓的是什麼?
   一個目錄 / 多個檔案           -> tar 系(要保目錄結構)
   就一個大檔(單一 log / dump)  -> gzip file 直接壓,不用 tar
   內容已壓過(jpg/mp4/parquet)  -> 別再壓,純 tar 打包或直接傳

③ 要常單獨抽裡面某個檔?
   要頻繁隨機取單檔             -> zip(每檔獨立壓,秒取)
   整包一起用 / 只解一次         -> tar.gz(整包一起壓,通常更小)
```

> 糾結時選 tar.gz——最不會出錯、對方一定解得開。

### 最佳實踐：壓多個指定檔案到一個包

**方式一：tar.gz(Linux 首選)**——多個檔案 / 目錄空格排在後面：

```bash
tar -czf pack.tgz file1.txt file2.log dir/
```

> 坑：`-f` 後面第一個一定是**輸出檔名**，別把要打包的檔寫到它前面。
> `tar -czf pack.tgz a.txt b.txt` ✓；`tar -czf a.txt b.txt pack.tgz` ✗ 會把 `a.txt` 當產物覆蓋掉。
>
> 注意：這樣直接列裸檔名，解開會散進當前目錄——通常要「包一層」成一個乾淨資料夾，見下面「打包的路徑學問」那節。

**方式二：zip(跨平台 / 給別人)**——注意參數順序：產物在前，來源在後；目錄要加 `-r` 才會遞迴：

```bash
zip -r pack.zip file1.txt file2.log logs/
```

兩種並排：

| | tar.gz | zip |
|---|---|---|
| 建包 | `tar -czf out.tgz f1 f2 dir/` | `zip -r out.zip f1 f2 dir/` |
| 目錄 | 自動遞迴 | 必須加 `-r`，否則跳過目錄 |
| 看內容 | `tar -tzf out.tgz` | `unzip -l out.zip` |
| 解包 | `tar -xzf out.tgz` | `unzip out.zip` |
| 保權限 / 屬主 | 會 | 不完整(Windows 相容妥協) |

### 打包的路徑學問：`-C`、包一層、tar bomb

一條鐵律先記住：**tar 存的是「你喂給它的那串路徑原樣」，解開就照那串重建。** 所以包裡長什麼樣、解開炸不炸，全看你喂進去的路徑帶不帶資料夾前綴。

**① 路徑太長 → 用 `-C` 砍前綴**

`tar -czf p.tgz /var/log/app/a.log` 包裡會存成 `var/log/app/a.log`(GNU tar 剝掉開頭的 `/`)，解開重建一長串沒用的目錄。`-C 目錄` = 打包前先切到那個目錄當基準，後面寫相對路徑，包裡就乾淨。

> `-C` 打包時 = 「從哪收」；解包時 = 「解到哪」：`tar -xzf pack.tgz -C /tmp/unpack`。

**② 包一層 vs 散在根(tar bomb)→ 看 `-C` 停在哪**

決定「解開是一個乾淨資料夾，還是一堆檔炸進當前目錄」的，是 `-C` 停在**父目錄**還是**目錄裡面**：

```bash
tar -czf app.tgz -C /var/log     app       # 包裡 app/access.log ... → 解開得到 app/   包一層 ✓
tar -czf app.tgz -C /var/log/app .         # 包裡 ./access.log ...   → 檔散進當前目錄  tar bomb ✗
```
```text
-C 停「父目錄」+ 打包資料夾名   -> 包一層,好清好認(推薦)
-C 停「目錄裡面」+ 打包 .        -> 散在根,解開撒一地、撞名、難清
```

> tar bomb = 包裡檔案沒有頂層資料夾，解開直接倒進當前目錄。給別人的包尤其要避免。頂層夾名慣例對齊檔名：`report.tgz` 解開就是 `report/`。

**③ 包一層，但只挑幾個檔(不是整包)→ 檔名帶資料夾前綴**

要「解開是 `app/`，裡面只放挑的那兩個檔」：基準停父目錄，檔名寫成 `app/xxx`，列你要的：

```bash
tar -czf app-logs.tgz -C /var/log app/access.log app/error.log
# 包裡:app/access.log、app/error.log —— 包一層 ✓ 又只挑檔 ✓
```

口訣：**包不包一層 = 路徑帶不帶資料夾前綴；挑不挑檔 = 只列你要的那幾個。**

檔案散在不同地方、或想自訂頂層夾名，改用暫存夾最可控：

```bash
mkdir release && cp /var/log/app/access.log /path/to/other.conf release/
tar -czf release.tgz release/ && rm -rf release   # 解開 release/,來源隨便湊、夾名你定
```

**④ 交互式最順：cd 到「父目錄」+ Tab 補全**

手敲時 `-C` 會讓 Tab 補全失效(補全按你當前目錄補，不知道 `-C` 去哪)。最順的做法是自己 `cd` 到**父目錄**，讓 Tab 補出來的路徑天然帶資料夾前綴：

```bash
cd /var/log                                       # ← cd 到「父目錄」,不是進 app 裡
tar -czf app-logs.tgz app/acc<Tab> app/err<Tab>   # Tab 補出 app/access.log → 包一層 + 挑檔
```

> 陷阱：別 `cd` 進資料夾裡面。進去後 Tab 補的是裸檔名(`access.log`)，包出來就散成 tar bomb。**站在父目錄外往裡指，不要站進去。**

`-C` 則留給腳本(路徑寫死、不想改 cwd)；臨時不想動當前目錄用子 shell：`(cd /var/log && tar -czf ~/app.tgz app/access.log)`。

### 解包會靜默覆蓋同名檔

`tar -xzf` 解包時，包裡每個檔按存的路徑寫到磁碟，**同名檔直接覆蓋，無提示、無確認**(不像 `cp -i` 會問)；但**不會刪除包裡沒有的檔**——是「疊加 + 覆蓋」，不是「同步」，本地舊檔可能殘留。安全動作：

```bash
tar -tzf app.tgz                    # 解壓前先看內容和路徑結構,這步最重要
mkdir -p /tmp/unpack
tar -xzf app.tgz -C /tmp/unpack     # 解到乾淨的空目錄,別原地炸
tar -xzf app.tgz --keep-old-files   # 真要防覆蓋:遇同名跳過(GNU tar)
```

> 反向操作：別人的包多包了一層你不想要的頂層資料夾，解時用 `--strip-components=N` 砍掉開頭 N 層：`tar -xzf app.tgz --strip-components=1 -C target/`。打包加一層、解包砍一層，剛好對稱。

**速驗：**

```bash
mkdir -p /tmp/pkgdemo
printf 'hello\n' > /tmp/pkgdemo/hello.txt
tar -czf /tmp/pkgdemo.tgz -C /tmp pkgdemo
tar -tzf /tmp/pkgdemo.tgz
mkdir -p /tmp/unpack
tar -xzf /tmp/pkgdemo.tgz -C /tmp/unpack
cat /tmp/unpack/pkgdemo/hello.txt
```

---

## 8. 系統、身份、位置快照

| 命令 | 幹嘛 | 肌肉記憶 |
|---|---|---|
| `date` | 現在時間 | 對 log 時間線 |
| `uptime` | 開機多久 / load | 快速看機器壓力 |
| `uname -a` | 內核與系統資訊 | 容器/VM/實機先看 |
| `hostname` | 主機名 | 確認在哪台機器 |
| `whoami` | 當前使用者名 | 權限排查第一步 |
| `id` | uid/gid/groups | 比 `whoami` 更完整 |
| `pwd` | 當前目錄 | 防止在錯目錄操作 |
| `env` | 環境變數 | 可能含 token/secret，分享前先遮蔽；只看名稱用 <code>env &#124; cut -d= -f1 &#124; sort</code> |

> 陌生 shell 先回答 6 問：我在哪台機器、哪個目錄、什麼身份、什麼系統、什麼時間、帶了哪些環境變數。
>
> 注意：`env` 可能印出 token、密鑰、代理憑證等。貼給別人前先遮蔽；只需要變數名時用 `env | cut -d= -f1 | sort`。

**速驗：**

```bash
date
hostname
pwd
whoami
id
uname -a
env | cut -d= -f1 | sort | head  # 只看變數名，避免把 secret 值印出來
```

### 臨時提權與切換身份：sudo / su

`whoami` / `id` 回答「我現在是誰」；這一節回答「怎麼臨時變成別人(通常是 root)」。用起來會慌，多半不是命令難，而是**切完身份後環境跟著變**——PATH、當前目錄、profile 都不一樣了，於是冒出「命令 not found」「怎麼在錯的目錄」。抓住這條主軸就不慌了。

**兩種思路先分清**：

- `sudo cmd`：**只借 root 跑這一條命令**，跑完立刻變回你自己。首選——最小提權、有審計紀錄，不會一直待在 root。
- `su`：**整個人切換成另一個用戶**，開一個新 shell，之後每條都是那個身份，直到 `exit`。

| 寫法 | 幹嘛 | 肌肉記憶 |
|---|---|---|
| `sudo cmd` | 只這條命令用 root | 日常首選；輸的是**你自己**的密碼 |
| `sudo !!` | 上條忘了加 sudo，補跑 | `Permission denied` 後直接 `sudo !!` |
| `sudo -i` | 開一個 root 的**登入** shell | 要連續跑多條 root 命令；環境全變 root 的 |
| `sudo -s` | 開 root shell 但**不走登入流程** | 環境半新半舊，不如 `-i` 乾淨 |
| `sudo -u www-data cmd` | 以**別的用戶**跑一條 | 排查「服務那個用戶能不能讀這檔」 |
| `sudo -E cmd` | 提權**並保留你的環境變數** | 要把 `http_proxy` 等帶進 root 時 |
| `su -` | 切成 root 並**載入 root 登入環境** | 輸的是 **root** 的密碼(不是你的) |
| `su - user` | 切成某個用戶(登入式) | 帶 `-` 才乾淨 |
| `exit` / `Ctrl-D` | 退回原本身份 | 開了 root shell 記得退出 |

**慌點就這幾個**(幾乎所有踩坑都在這)：

```text
1. 帶不帶「-」差很多(su / su -、sudo -s / sudo -i)
   帶 -  = 登入式:cd 到目標用戶家目錄 + 重載其 PATH / profile -> 乾淨可預測
   不帶  = 非登入:人變了但環境(PATH、當前目錄)半新半舊 -> 常見「命令 not found / 在錯目錄」
   結論:要變身份,優先用登入式(sudo -i / su -)

2. sudo 和 su 要的密碼不一樣
   sudo cmd -> 輸「你自己」的密碼(且你要在 sudoers 名單裡)
   su -     -> 輸「目標用戶(root)」的密碼
   一直失敗先想:是不是輸錯人的密碼

3. > 重定向不會被 sudo 提權
   sudo echo x > /etc/f       ✗  > 是你當前 shell 先做的,沒 root 權限
   echo x | sudo tee /etc/f   ✓  (見 §5「sudo tee」那段)

4. sudo 預設「洗掉」你的環境變數(安全考量)
   帶不過去 http_proxy / 自訂 PATH 時,用 sudo -E,或 sudo env VAR=... cmd
```

> 心法：**能 `sudo 單條` 就別開 root shell**——最小提權、有紀錄、不會待在沒護欄的 root 下亂敲(root 下 `rm` 一步到位，沒有「你確定嗎」)。真要連續多條，用 `sudo -i` 開乾淨的登入 shell，做完 `exit`。`su` 只在你知道對方密碼、要以其身份互動時才用。

### 容器裡沒 sudo？你多半已經是 root

容器裡「沒裝 sudo」通常不是「拿不到 root」，而是**你本來就是 root**——`docker run ubuntu bash` 直接進 root shell（提示符 `#`、`whoami` = root），`apt install` 直接跑，不需要 sudo。sudo 是**多用戶主機**用的（讓普通用戶臨時借 root + 密碼 + 審計）；容器通常單一用途、單用戶，「要不要 root」在**啟動邊界**上決定，不是進去用 sudo。

當容器**故意跑非 root**（Dockerfile `USER app`、k8s `runAsNonRoot`——這是生產最佳實踐）要拿 root：

| 場景 | 拿 root |
|---|---|
| 進正在跑的容器 | `docker exec -u 0 -it <容器> bash`（宿主 daemon 是 root，`-u 0` 一定給到 root，**無視容器預設用戶**） |
| 起容器就要 root | `docker run -u 0 ...` |
| 容器內臨時裝工具 debug | `docker exec -u 0` 進去再 `apt install` |
| k8s Pod | `kubectl exec` 跟容器用戶走；要 root 用 `kubectl debug`（ephemeral 容器）或從 node `nsenter`（→ **08**） |

> 別在生產鏡像裡加 sudo——**反模式**。要 root 就在啟動邊界給（`-u 0` / `USER` / securityContext），不是塞 sudo 進去。容器排查細節 → **08**。

**速驗**(拋棄式容器裡預設是 root，`su` 到別人不需密碼，正好看環境差異；`sudo` 常要先 `apt install -y sudo`)：

```bash
useradd -m -s /bin/bash demo 2>/dev/null || true
cd /tmp
su - demo -c 'whoami; pwd; echo "PATH=$PATH"'   # 登入式:cd 到家目錄,PATH 重載
su   demo -c 'whoami; pwd; echo "PATH=$PATH"'   # 非登入:pwd 還在 /tmp,環境沿用當前
```

預期重點：

```text
su - demo  -> whoami=demo,pwd=/home/demo(登入式會 cd 到家目錄、重載環境)
su   demo  -> whoami=demo,但 pwd 還在 /tmp(人變了卻還站在原地)
             這種「環境沒跟著換」正是「命令 not found」的來源
```

---

## 9. 常用命令背後的系統文件

> 先用命令拿摘要；命令不夠細、環境太精簡、或命令結果和應用行為不一致時，再直接看文件。

| 想知道 | 先用命令 | 背後 / 可直接看的文件 | 什麼時候直接看文件 |
|---|---|---|---|
| 什麼發行版 | `cat /etc/os-release` | `/etc/os-release` | 裝工具前判斷該用 `apt` / `dnf` / `apk` / `pacman` |
| 主機名 | `hostname` | `/etc/hostname` | 查靜態 hostname；容器裡 hostname 可能是 runtime 注入 |
| 使用者與組 | `whoami` / `id` | `/etc/passwd`、`/etc/group` | 查 uid/gid/group 對應；不要把 `/etc/passwd` 當密碼文件 |
| 命令路徑 | `type cmd` / `command -v cmd` | `$PATH`、`/usr/bin`、`/usr/local/bin` | 懷疑跑到錯版本、alias、函數、venv 裡的命令 |
| DNS 解析 | `getent hosts name` / `dig name` | `/etc/hosts`、`/etc/resolv.conf`、`/etc/nsswitch.conf` | `dig` 有結果但應用連不上；本機 hosts 或解析順序可能不同 |
| CPU 資訊 | `lscpu` / `nproc` | `/proc/cpuinfo`、`/proc/stat` | 精簡環境沒 `lscpu`；想看 CPU 原始欄位或累計時間 |
| 記憶體 | `free -h` | `/proc/meminfo` | 想看 `MemAvailable`、cache、swap 原始值；容器限制另看 `/sys/fs/cgroup` |
| load average | `uptime` | `/proc/loadavg` | 腳本採樣；注意 load 要和 CPU 核數一起看 |
| 掛載與磁碟 | `df -h` / `mount` | `/proc/mounts`、`/etc/fstab` | 分清「現在已掛載」和「開機自動掛載」；改 `/etc/fstab` 要小心 |
| 進程細節 | `ps` / `lsof` | `/proc/<pid>/cmdline`、`fd/`、`limits`、`environ`、`cwd` | 查進程真實參數、打開的 fd、生效限制、工作目錄、環境變數 |
| 服務與日誌 | `systemctl status` / `journalctl` | `/etc/systemd/system/`、`/lib/systemd/system/`、`/var/log/` | 沒有 journald、服務 unit 有覆蓋、或應用直接寫文件日誌 |
| 內核與設備 | `uname -a` / `dmesg -T` | `/proc/version`、`/sys/`、`/dev/` | 查內核版本、設備狀態、cgroup、block/net class 等低層資訊 |

三條使用原則：

```text
1. /etc  多是配置:系統怎麼被設定。
2. /proc 多是內核運行時狀態:現在正在發生什麼。
3. /sys  多是設備 / 內核子系統視圖:硬體、cgroup、block、net 等。
```

高頻判斷：

```text
命令看摘要     -> uptime / free / df / hostname / id
文件看真相     -> /etc/os-release, /proc, /sys, systemd unit, /var/log
行為不一致時   -> 對照命令輸出和背後文件,尤其 DNS、PATH、容器資源限制
```

> 這節只是入口索引。進程內部細節見 `04-observability-internals.md`；DNS 見 `03-network-triage.md`；systemd 見 `07-systemd-and-services.md`。

---

## 和 CORE-SET 的關係

`00-cli-survival-kit.md` 是每天操作層：

```text
裝工具、確認命令來源、保存終端現場、看輸出、接 stdout/stderr、跑腳本、打包、確認身份位置、知道資訊從哪來
```

`CORE-SET.md` 是工程排查層：

```text
進程、性能、網路、文本、檔案磁碟、服務容器遠端
```

先用 00 把終端站穩，再用 CORE-SET 按問題類型排查。
