# CLI Survival Kit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a compact senior-engineer daily CLI survival chapter and link it from the CLI core set.

**Architecture:** This is a documentation-only change. `cli-toolbox/00-cli-survival-kit.md` owns the daily terminal operating layer, while `cli-toolbox/CORE-SET.md` remains the high-level triage index and only gains a short entry point.

**Tech Stack:** Markdown documentation, existing `cli-toolbox` structure, shell verification commands.

---

## File Structure

- Create: `cli-toolbox/00-cli-survival-kit.md`
  - Responsibility: teach the daily CLI operating layer: package installation, command lookup, tmux/history, output viewing, shell primitives, compression, and machine/user context.
- Modify: `cli-toolbox/CORE-SET.md`
  - Responsibility: add a discoverable pointer to the new survival chapter without changing the existing six-category triage model.
- Do not modify: `cli-toolbox/README.md` or `skills-lock.json`
  - These files were already dirty before this implementation plan. Do not stage or commit them as part of this work unless the user explicitly asks.

## Task 1: Add The Survival Kit Chapter

**Files:**
- Create: `cli-toolbox/00-cli-survival-kit.md`

- [ ] **Step 1: Check current worktree before editing**

Run:

```bash
git status --short
```

Expected:

```text
 M cli-toolbox/README.md
 M skills-lock.json
```

The output may also include the new plan file if this plan has not been committed yet. Do not stage `cli-toolbox/README.md` or `skills-lock.json`.

- [ ] **Step 2: Create `cli-toolbox/00-cli-survival-kit.md`**

Write exactly this Markdown content:

```markdown
# 00 · CLI 生存包

> 這章不是 Linux 入門大全，也不是 shell 腳本手冊。它收的是資深工程師 / 架構師每天在終端裡反覆用到、但不屬於某一個排查章節的操作原語。
>
> 先會這些，再進 `CORE-SET.md` 的 6 類排查命令，整個 CLI 工作流才接得起來。

---

## 收口地圖

日常 CLI 生存層只回答 7 件事：

```text
① 怎麼裝工具        apt / dpkg
② 我到底在跑誰      type / command -v / which
③ 工作現場怎麼保留  tmux / history
④ 輸出怎麼看        less / tail / watch / tee
⑤ shell 怎麼接線    $? / > / 2>&1 / |
⑥ 東西怎麼打包      tar / gzip / zip
⑦ 我在哪、我是誰    date / uname / id / env
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
| `cmd | tee out.log` | 邊看輸出邊存檔 | 保留現場證據 |
| `cmd 2>&1 | tee out.log` | stdout/stderr 都保存 | 排查失敗命令時用 |

> `less` 是「慢慢看」，`tail -f` 是「跟著看」，`watch` 是「反覆看」，`tee` 是「邊看邊留證據」。

**速驗：**

```bash
printf 'one\ntwo\nthree\n' > /tmp/demo.log
less /tmp/demo.log
tail -f /tmp/demo.log
# 另開一個 shell: echo four >> /tmp/demo.log
watch -n 1 'date; tail -n 3 /tmp/demo.log'
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
| `cmd1 | cmd2` | 左邊 stdout 接右邊 stdin | 管道只接 stdout |
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
| `env` | 環境變數 | PATH、代理、語言、憑證路徑 |

> 陌生 shell 先回答 6 問：我在哪台機器、哪個目錄、什麼身份、什麼系統、什麼時間、帶了哪些環境變數。

**速驗：**

```bash
date
hostname
pwd
whoami
id
uname -a
env | sort | head
```

---

## 和 CORE-SET 的關係

`00-cli-survival-kit.md` 是每天操作層：

```text
裝工具、確認命令來源、保存終端現場、看輸出、接 stdout/stderr、打包、確認身份位置
```

`CORE-SET.md` 是工程排查層：

```text
進程、性能、網路、文本、檔案磁碟、服務容器遠端
```

先用 00 把終端站穩，再用 CORE-SET 按問題類型排查。
```

- [ ] **Step 3: Verify the new chapter contains all required sections**

Run:

```bash
rg -n "^## |apt update|command -v|tmux new|tail -f|2>&1|tar -czf|uname -a" cli-toolbox/00-cli-survival-kit.md
```

Expected: output includes section headings for all seven sections plus matching lines for `apt update`, `command -v`, `tmux new`, `tail -f`, `2>&1`, `tar -czf`, and `uname -a`.

- [ ] **Step 4: Stage and commit the new chapter**

Run:

```bash
git add cli-toolbox/00-cli-survival-kit.md
git commit -m "docs(cli-toolbox): add CLI survival kit"
```

Expected: commit succeeds and reports one created file.

## Task 2: Link The New Chapter From CORE-SET

**Files:**
- Modify: `cli-toolbox/CORE-SET.md`

- [ ] **Step 1: Insert the survival kit pointer near the top of `CORE-SET.md`**

Modify the introduction so the block after the opening quote and before `## 記憶錨：一切先落到這 6 類` becomes:

```markdown
---

## 開始前：日常 CLI survival kit  → [00](00-cli-survival-kit.md)

`CORE-SET` 收的是排查與工程場景；如果你還在補「怎麼裝工具、怎麼保留終端現場、怎麼看輸出、怎麼接 stdout/stderr」，先讀 00。

---

## 記憶錨：一切先落到這 6 類
```

Keep the rest of `CORE-SET.md` unchanged.

- [ ] **Step 2: Verify the link exists and the existing core categories remain**

Run:

```bash
rg -n "00-cli-survival-kit|## 記憶錨|## ① 進程|## ⑥ 服務" cli-toolbox/CORE-SET.md
```

Expected: output includes the `00-cli-survival-kit.md` link plus the existing `記憶錨`, `①`, and `⑥` headings.

- [ ] **Step 3: Stage and commit the CORE-SET link**

Run:

```bash
git add cli-toolbox/CORE-SET.md
git commit -m "docs(cli-toolbox): link CLI survival kit"
```

Expected: commit succeeds and reports one modified file.

## Task 3: Final Documentation Verification

**Files:**
- Inspect: `cli-toolbox/00-cli-survival-kit.md`
- Inspect: `cli-toolbox/CORE-SET.md`

- [ ] **Step 1: Verify acceptance criteria phrases**

Run:

```bash
rg -n "apt update.*apt upgrade|tmux.*nohup|type.*command -v|stdout.*stderr|tar.*gzip" cli-toolbox/00-cli-survival-kit.md
```

Expected: output includes lines distinguishing package index update vs upgrade, tmux vs nohup, command lookup tools, stdout vs stderr, and tar vs gzip.

- [ ] **Step 2: Verify no accidental staging of pre-existing dirty files**

Run:

```bash
git status --short
```

Expected: `cli-toolbox/README.md` and `skills-lock.json` may still appear as modified, but they must not be staged. No uncommitted changes to `cli-toolbox/00-cli-survival-kit.md` or `cli-toolbox/CORE-SET.md` should remain after the two task commits.

- [ ] **Step 3: Show recent commits**

Run:

```bash
git log --oneline -3
```

Expected: the output includes:

```text
docs(cli-toolbox): link CLI survival kit
docs(cli-toolbox): add CLI survival kit
docs: design CLI survival kit
```

## Self-Review

Spec coverage:

- New `cli-toolbox/00-cli-survival-kit.md`: Task 1.
- `CORE-SET.md` entry point: Task 2.
- Compact senior-engineer orientation: Task 1 content and Task 2 positioning.
- Required distinctions: Task 1 content and Task 3 acceptance verification.
- No advanced tmux or service-management expansion: Task 1 includes only session basics and explicitly redirects formal services to systemd/Docker/Kubernetes.

Placeholder scan:

- This plan contains no placeholder markers.
- Every file path is exact.
- Every verification step has an exact command and expected result.

Scope check:

- The work is one documentation slice and does not require decomposition into separate plans.
