# 00 · CLI 生存包

> 這章不是 Linux 入門大全，也不是 shell 腳本手冊。它收的是資深工程師 / 架構師每天在終端裡反覆用到、但不屬於某一個排查章節的操作原語。
>
> 先會這些，再進 `CORE-SET.md` 的 6 類排查命令，整個 CLI 工作流才接得起來。

---

## 收口地圖

日常 CLI 生存層只回答 8 件事：

```text
① 怎麼裝工具        apt / dpkg
② 我到底在跑誰      type / command -v / which
③ 工作現場怎麼保留  tmux / history
④ 輸出怎麼看        less / tail / watch / tee
⑤ shell 怎麼接線    $? / > / 2>&1 / |
⑥ 東西怎麼打包      tar / gzip / zip
⑦ 我在哪、我是誰    date / uname / id / env
⑧ 資訊從哪來        /etc /proc /sys /var/log
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

**速驗：**

```bash
false
echo $?

sh -c 'echo out; echo err >&2' > /tmp/out.txt 2> /tmp/err.txt
cat /tmp/out.txt
cat /tmp/err.txt

sh -c 'echo out; echo err >&2' > /tmp/all.txt 2>&1
cat /tmp/all.txt

FOO=bar sh -c 'echo "$FOO"'
echo "$FOO"
```

預期重點：

```text
false 的退出碼是 1
out.txt 只有 out
err.txt 只有 err
all.txt 同時有 out 和 err
FOO=bar cmd 不會永久寫進目前 shell
```

---

## 6. 壓縮與搬運：tar / gzip / zip

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

## 7. 系統、身份、位置快照

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

---

## 8. 常用命令背後的系統文件

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
裝工具、確認命令來源、保存終端現場、看輸出、接 stdout/stderr、打包、確認身份位置、知道資訊從哪來
```

`CORE-SET.md` 是工程排查層：

```text
進程、性能、網路、文本、檔案磁碟、服務容器遠端
```

先用 00 把終端站穩，再用 CORE-SET 按問題類型排查。
