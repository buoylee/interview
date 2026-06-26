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
| `ssh user@host -p 2222 -i ~/.ssh/key` | 指定端口 / 私鑰登入 |
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
| `rsync -avz src/ host:/dst/` | **增量同步**:只傳差異(`a`保留屬性 `v`詳細 `z`壓縮) |
| `rsync -avz --progress src/ host:/dst/` | 顯示進度 |
| `rsync -avz --delete src/ host:/dst/` | **鏡像**:目標多出來的也刪 ⚠️ |
| `rsync -avzn src/ host:/dst/` | `-n` = **dry-run**,先看會傳什麼 |

> 心法:**一次性小檔 → `scp`;大目錄 / 反覆同步 / 怕斷線 → `rsync`**(只傳變化、可續傳,省大量時間)。
> ⚠️ **尾斜線有意義**:`src/` = 傳「src 裡的內容」;`src`(無斜線)= 傳「src 這個目錄本身」。`--delete` 前務必先 `-n` 試跑。

---

## 4. `tmux`(跑長任務 + 可重連)

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

## 深挖

- 網路、TCP、為什麼隧道能穿透 → **`linux-handson/06-networking`**
- 「放後台」的完整三層(`&`/`nohup` → `setsid`/`disown` → `tmux`/systemd) → **`01 進程與作業控制`**
- 邊緣代理 / 反向暴露服務的生產做法 → **`gateway`**、**`nginx`**
