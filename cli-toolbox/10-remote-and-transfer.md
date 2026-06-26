# 10 · 遠端與傳輸

> 連遠端連得舒服、穿透到內網服務、傳大檔案、跑幾小時的任務不怕斷線。`ssh` / `rsync` / `tmux` 三件套。

---

## 收口地圖

| 要做的事 | 工具 | 一句話 |
|---|---|---|
| 連得舒服(免密、別名、跳板) | `ssh` + `~/.ssh/config` | 一次配好,以後 `ssh prod` 就進 |
| **穿透到內網服務** | `ssh -L/-R/-D` | 把 TCP 流量套進加密隧道 |
| 傳檔案 / 同步目錄 | `scp` / `rsync` | 小檔 scp,大目錄/反覆同步 rsync |
| 跑長任務不怕斷線 | `tmux` | 伺服器端的可重連會話(回扣 **01** 第三層) |

> **原語:`ssh` 不只是「登入」,它是一條加密隧道**——能把任意 TCP 流量塞進去轉發。理解這點,`-L/-R/-D` 一次全通。

---

## 1. `ssh` 基礎 + `~/.ssh/config`(連得舒服)

| 命令 | 作用 |
|---|---|
| 🔧 `ssh user@host -p 2222 -i ~/.ssh/key` | 指定端口 / 私鑰登入 |
| `ssh-keygen -t ed25519` | 產生金鑰對 |
| `ssh-copy-id user@host` | 把公鑰裝到對端 → **免密登入** |
| `ssh -J bastion user@internal` | 經**跳板機**連內網主機(ProxyJump) |

**`~/.ssh/config`(資深必配,告別一長串參數)**:

```ssh-config
Host prod                    # 別名:以後只要 `ssh prod`
    HostName 10.0.0.5
    User deploy
    Port 2222
    IdentityFile ~/.ssh/prod_key
    ProxyJump bastion        # 自動走跳板機

Host bastion
    HostName bastion.example.com
    User jump
```

---

## 2. `ssh` 隧道 / 端口轉發(架構師高頻)

| 命令 | 方向 | 作用 |
|---|---|---|
| `ssh -L 5432:db-internal:5432 bastion` | **本地←遠端** | 本地連 `localhost:5432` = 連到內網的 `db-internal:5432` |
| `ssh -R 8080:localhost:3000 host` | **本地→遠端** | 把你本機的 3000 服務,暴露成遠端的 8080 |
| `ssh -D 1080 host` | SOCKS 代理 | 本地 `1080` 變成走遠端出口的代理 |

> 記憶:**`-L` 把「遠端能到的東西」拉到本地**(最常用:連只有跳板機能到的內網 DB / k8s Service);**`-R` 把「本地的東西」推到遠端**(臨時給外部 demo、接 webhook)。兩個方向別記反。

```bash
# 實例:本地用 GUI 連一個只有跳板機能訪問的內網 Postgres
ssh -L 5432:pg.internal:5432 bastion
# → 然後本機 psql -h localhost -p 5432 就連上了
```

---

## 3. 傳檔案:`scp` / `rsync`

| 命令 | 作用 |
|---|---|
| `scp file host:/path/` | 傳單檔到遠端(`-r` 傳目錄) |
| `scp host:/path/file ./` | 從遠端拉回 |
| 🔧 `rsync -avz src/ host:/dst/` | **增量同步**:只傳差異(`a`保留屬性 `v`詳細 `z`壓縮) |
| `rsync -avz --progress src/ host:/dst/` | 顯示進度 |
| `rsync -avz --delete src/ host:/dst/` | **鏡像**:目標多出來的也刪 ⚠️ |
| `rsync -avzn src/ host:/dst/` | `-n` = **dry-run**,先看會傳什麼 |

> 心法:**一次性小檔 → `scp`;大目錄 / 反覆同步 / 怕斷線 → `rsync`**(只傳變化、可續傳,省大量時間)。
> ⚠️ **尾斜線有意義**:`src/` = 傳「src 裡的內容」;`src`(無斜線)= 傳「src 這個目錄本身」。`--delete` 前務必先 `-n` 試跑。

---

## 4. 🔧 `tmux`(跑長任務 + 可重連)

| 操作 | 命令 / 按鍵 |
|---|---|
| 新建命名會話 | `tmux new -s train` |
| **脫離**(留著繼續跑) | `Ctrl+b` 然後 `d` |
| 列出會話 | `tmux ls` |
| **重新連回** | `tmux attach -t train` |
| 新窗口 / 分屏 | `Ctrl+b c` / `Ctrl+b %`(左右)`Ctrl+b "`(上下) |

> 為什麼比 `nohup` 適合「互動式長任務」:**會話活在伺服器端**,ssh 斷了任務照跑;重連 `tmux attach` 就**回到原來的畫面**(還能看滾動輸出、繼續敲)。跑訓練、跑遷移、盯實時日誌的首選。
>
> 回扣 **01**:這是「放後台」的**第三層——會話管理器**。`nohup` 適合「丟了不管」的批處理;`tmux` 適合「要回來看、要繼續互動」的長任務。

---

## 5. 場景速查

| 我要 | 怎麼做 |
|---|---|
| 連只有跳板機能到的內網 DB | `ssh -L 本地:db:遠端 bastion` 隧道 |
| 把本地服務臨時給外部 demo | `ssh -R` 反向隧道(或 ngrok 類工具) |
| 同步一個大目錄到伺服器 | `rsync -avz --progress src/ host:/dst/` |
| 跑幾小時的任務怕斷線 | `tmux new -s job`,`Ctrl+b d` 脫離 |
| 管多台機器、免密 + 別名 | 配好 `~/.ssh/config` + `ssh-copy-id` |

---

## 🔧 主力命令深講 + 速驗

> 隧道 / scp 需要對端;沙盒裡能自驗的是 `ssh-keygen`、`ssh -G`(解析 config)、本地 `rsync`、`tmux` 後台會話。先進 README 沙盒。

### ssh — 連線 + config

| 寫法 | 作用 |
|---|---|
| `ssh user@host -p PORT -i KEY` | 指定端口 / 私鑰 |
| `ssh -J bastion user@internal` | 經跳板機(ProxyJump) |
| `ssh -G host` | **印出對 host 生效的完整配置**(排查 config) |
| `ssh -v host` | verbose,排查連不上 |
| `ssh-keygen -t ed25519 -f KEY` | 產生金鑰對 |

`ssh -v` 排查時看常見訊號:

| 日誌片段 | 訊號 | 排查方向 |
|---|---|---|
| `Reading configuration data` | 讀 config | 是否吃到預期 `~/.ssh/config` |
| `Connecting to host port` | DNS/TCP 連線 | 主機名、端口、防火牆 |
| `kex_exchange_identification` / `SSH2_MSG_KEX` | key exchange | 協議/中間設備 |
| `Offering public key` | 嘗試私鑰 | 是否用了正確 key |
| `Authentication succeeded` | 認證成功 | 後面才是遠端 session 問題 |
| `Permission denied` | 認證失敗訊號 | key、使用者、server `authorized_keys`;不一定是固定階段 |

`ssh -G host` 印「最後生效」的 config,包含預設值與展開後結果:

| 欄位 | 意思 |
|---|---|
| `hostname` | 最終連到哪個主機 |
| `user` | 最終登入使用者 |
| `port` | 最終端口 |
| `identityfile` | 會嘗試的私鑰 |
| `proxyjump` | 是否走跳板機 |

> 小坑:`ssh -G` 不會真的連線,適合先確認 config 展開結果。

**⚡ 驗證**:
```bash
mkdir -p ~/.ssh
ssh-keygen -t ed25519 -f /tmp/testkey -N '' -q    # 產生金鑰對(無密碼)
ls /tmp/testkey*                                   # 預期:testkey(私鑰)+ testkey.pub(公鑰)
ssh-keygen -lf /tmp/testkey.pub                    # 預期:指紋 "256 SHA256:... (ED25519)"
cat >/tmp/demo-ssh-config <<'EOF'
Host demo
  HostName 1.2.3.4
  User bob
  Port 2222
EOF
ssh -F /tmp/demo-ssh-config -G demo | grep -E '^(hostname|user|port) '     # 預期:hostname 1.2.3.4 / user bob / port 2222
```

### ssh 隧道(需對端,記命令形態)

```bash
ssh -L 5432:db-internal:5432 bastion   # 本地←遠端:本機 localhost:5432 → 內網 db
ssh -R 8080:localhost:3000 host        # 本地→遠端:把本機 3000 暴露成遠端 8080
ssh -D 1080 host                       # SOCKS 代理
```

### rsync — 增量同步

| 寫法 | 作用 |
|---|---|
| `rsync -av src/ dst/` | 保留屬性 + 詳細;增量(只傳差異) |
| `rsync -avz ... host:/dst/` | 加 `z` 壓縮(走網路時) |
| `rsync -av --delete src/ dst/` | 鏡像:目標多的也刪 ⚠️ |
| `rsync -avn src/ dst/` | `-n` dry-run,先看會做什麼 |

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
| `to-chk=2/5` | 剩餘待檢查項 / 總項目 | 粗看整批同步還有多少項要掃 |

> 小坑:目錄尾斜線很重要:`src/` 傳內容,`src` 傳整個目錄名。

**⚡ 驗證**(本地目錄就能驗):
```bash
mkdir -p /tmp/src && echo a >/tmp/src/a.txt && echo b >/tmp/src/b.txt
rsync -av /tmp/src/ /tmp/dst/         # 同步(尾斜線=傳內容)
ls /tmp/dst                            # 預期:a.txt b.txt
echo c >/tmp/src/c.txt
rsync -av /tmp/src/ /tmp/dst/         # 預期:只傳 c.txt(增量,輸出只列 c.txt)
rsync -avn --delete /tmp/src/ /tmp/dst/   # 預期:dry-run 列出將同步/刪除什麼,但不真做
```

### tmux — 可重連會話

| 操作 | 命令 |
|---|---|
| 新建(後台) | `tmux new -d -s 名` |
| 列出 | `tmux ls` |
| 連回 | `tmux attach -t 名` |
| 脫離(在會話內) | `Ctrl+b` `d` |
| 殺會話 | `tmux kill-session -t 名` |

**⚡ 驗證**(非互動,後台會話):
```bash
tmux new -d -s demo                          # 後台建會話
tmux ls                                       # 預期:demo: 1 windows ...
tmux send-keys -t demo 'echo hi > /tmp/tmux-out' Enter    # 往會話發命令
sleep 1; cat /tmp/tmux-out                    # 預期:hi(會話內真的執行了)
tmux kill-session -t demo                     # 清理
```
> 互動版:`tmux new -s x` → 按 `Ctrl+b d` 脫離 → `tmux attach -t x` 回到原畫面。

### ⚡ 配角速驗(`scp` / `ssh-copy-id` —— 需對端)

```bash
# 以下需真的遠端主機,這裡只列命令形態:
# scp file user@host:/path/        傳檔上去(-r 傳目錄)
# scp user@host:/path/file ./      拉回來
# ssh-copy-id user@host            把公鑰裝到對端 → 免密
```

---

## 深挖

- 網路、TCP、為什麼隧道能穿透 → **`linux-handson/06-networking`**
- 「放後台」的完整三層(`&`/`nohup` → `setsid`/`disown` → `tmux`/systemd) → **`01 進程與作業控制`**
- 邊緣代理 / 反向暴露服務的生產做法 → **`gateway`**、**`nginx`**
