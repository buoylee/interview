# 07 · systemd 與服務

> 服務起不來、要看服務日誌、要設開機自啟/崩潰自動重拉——這些都歸 systemd。記 `systemctl` + `journalctl` 兩個命令就覆蓋 80%。

---

## 收口地圖

- **systemd 管「服務的生命週期」**:起 / 停 / 查狀態 / 看日誌 / 開機自啟 / 崩潰重拉。
- 你要記的就**兩個命令**:`systemctl`(控制)+ `journalctl`(看日誌)。
- 一個概念:**unit** = systemd 管理的單位(`.service` 是其中一種),用一個描述檔定義「怎麼起、依賴誰、崩了怎麼辦」。

> 回扣 **01**:`nohup`/`setsid` 是臨時手段;**生產服務要開機自啟、崩潰重拉、日誌歸集,正路是寫成 systemd service**。

---

## 1. `systemctl` —— 服務生命週期

| 命令 | 作用 | 底層一兩句 |
|---|---|---|
| 🔧 `systemctl status nginx` | 看狀態 + 最近幾行日誌 | **最高頻**;一眼看 active/failed + PID + 退出碼 |
| `systemctl start/stop/restart nginx` | 起 / 停 / 重啟 | restart = 真的停再起 |
| `systemctl reload nginx` | **重讀配置但不中斷服務** | 服務需支援(底層常是發 `SIGHUP`);比 restart 溫和 |
| `systemctl enable --now nginx` | 設開機自啟**並立即啟動** | `enable` 只設自啟;`--now` 順便 start |
| `systemctl disable nginx` | 取消開機自啟 | — |
| `systemctl is-active / is-enabled nginx` | 腳本化探測 | 回單詞,好判斷 |
| `systemctl list-units --state=failed` | 列**掛掉**的服務 | 巡檢第一條 |
| `systemctl daemon-reload` | **改完 unit 檔後重載** | 忘了它 → 你的修改不生效 |

> **reload vs restart**:`reload` 在不斷服務的前提下重讀配置(連接不掉),`restart` 會真的停一下。**能 reload 就別 restart**(尤其線上)。詳見 `distribution/zero-downtime-release`。

---

## 2. `journalctl` —— 服務日誌

| 命令 | 作用 |
|---|---|
| 🔧 `journalctl -u nginx` | 某服務的全部日誌 |
| `journalctl -u nginx -f` | **跟隨**(實時) |
| `journalctl -u nginx -e` | 直接跳到**最尾部**(看最新錯誤) |
| `journalctl -u nginx --since "1 hour ago"` | 按時間窗 |
| `journalctl -u nginx -p err` | 只看 error 級以上 |
| `journalctl -b` / `-b -1` | **本次開機** / 上一次開機 |
| `journalctl -k` | 內核訊息(= 持久化的 `dmesg`,見 **04**) |
| `journalctl --disk-usage` | 日誌佔了多少磁碟 |

> 「服務莫名重啟」三連:`systemctl status`(退出碼/狀態)→ `journalctl -u 服務 -e`(崩潰堆疊)→ `journalctl -k | grep -i oom`(是不是被 OOM 殺,見 **02/04**)。

---

## 3. 寫一個 unit(架構師該會)

`/etc/systemd/system/myapp.service`:

```ini
[Unit]
Description=My App
After=network.target          # 等網路就緒再起

[Service]
ExecStart=/usr/bin/myapp --port 8080
WorkingDirectory=/opt/myapp
Environment=ENV=prod          # 環境變數(或 EnvironmentFile=)
User=myapp                    # 用非 root 身份跑(安全)
Restart=on-failure            # 崩潰自動重拉 ← 這就是你要的
RestartSec=3

[Install]
WantedBy=multi-user.target    # enable 時掛到「多用戶」開機目標
```

啟用:

```bash
sudo systemctl daemon-reload          # 讓 systemd 看到新檔
sudo systemctl enable --now myapp     # 開機自啟 + 立即啟動
systemctl status myapp                # 確認
```

> 三個欄位對應你 **01** 學的痛點:`Restart=on-failure`=崩潰重拉、`WantedBy=...`=開機自啟、`User=`=不用 root。**這一套取代了 `nohup &` + 自己寫看門狗。**

---

## 4. 臨時托管:`systemd-run`

不想寫 unit 檔,但要「比 shell 活得久」:

| 命令 | 作用 |
|---|---|
| `systemd-run --unit=job1 /path/cmd` | 臨時把命令交給 systemd 跑(脫離當前 session) |
| `systemd-run --scope --user cmd` | 用戶級臨時 scope |
| `systemctl --user status` | 管理**用戶級**服務(不需 root) |

---

## 5. 排查「服務起不來」

```
systemctl start myapp  →  失敗
│
├─ systemctl status myapp     active 狀態？退出碼?Main PID 的結束原因?
├─ journalctl -u myapp -e      尾部錯誤堆疊(最直接)
├─ systemctl cat myapp         看「完整生效」的 unit(改對地方了嗎)
├─ 一直 Restart 循環？         journal 裡看每次崩的原因;先 stop 止血
└─ systemd-analyze blame       開機很慢?看哪個服務拖的
```

---

## 🔧 主力命令深講 + 速驗

> ⚠️ **這章驗證需要「有 systemd 的環境」**:plain `docker run ubuntu` 沒跑 systemd(PID 1 是 bash 不是 systemd)。請在**你的 linux-handson VM / WSL / 雲主機**裡跑(這些本來就是 systemd)。下面凡是 `start/stop` 的請用 root。

### systemctl — 服務生命週期

| 寫法 | 作用 |
|---|---|
| `systemctl status 服務` | 狀態 + 最近日誌 |
| `systemctl start/stop/restart 服務` | 起/停/重啟 |
| `systemctl reload 服務` | 不斷服務重讀配置 |
| `systemctl enable --now 服務` | 開機自啟 + 立即啟動 |
| `systemctl is-active / is-enabled 服務` | 腳本化探測 |
| `systemctl list-units --type=service` | 列服務(`--state=failed` 只看掛的) |
| `systemctl cat / show 服務` | 看生效的 unit / 所有屬性 |
| `systemctl daemon-reload` | 改完 unit 檔重載 |

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

**⚡ 驗證 A(唯讀,安全)**:
```bash
systemctl is-system-running             # 預期:running(或 degraded)
systemctl list-units --type=service --state=running | head   # 預期:跑著的服務列表
systemctl is-active cron 2>/dev/null || echo inactive        # 預期:active 或 inactive
```

**⚡ 驗證 B(端到端:造臨時服務 → 啟動 → 看日誌 → 清掉)**:
```bash
cat >/etc/systemd/system/hello.service <<'EOF'
[Unit]
Description=hello test
[Service]
ExecStart=/bin/sh -c 'echo hello from systemd; sleep 2'
EOF
systemctl daemon-reload
systemctl start hello
journalctl -u hello --no-pager | tail -3     # 預期:看到 "hello from systemd"
# 清理:
systemctl stop hello; rm /etc/systemd/system/hello.service; systemctl daemon-reload
```

### journalctl — 服務日誌

| 寫法 | 作用 |
|---|---|
| `journalctl -u 服務` | 某服務全部日誌 |
| `journalctl -u 服務 -f` / `-e` | 跟隨 / 跳到尾部 |
| `journalctl -u 服務 --since "1 hour ago"` | 按時間窗 |
| `journalctl -p err -b` | 本次開機的 error 級以上 |
| `journalctl -k` | 內核訊息 |
| `journalctl -n 50 --no-pager` | 最近 50 條 |
| `journalctl --disk-usage` | 佔用磁碟 |

`journalctl` 一行日誌拆法:

```text
Jun 26 10:00:00 host app[1234]: failed to bind port
```

| 片段 | 意思 | 怎麼判讀 |
|---|---|---|
| `Jun 26 10:00:00` | 時間 | 用 `--since` / `--until` 收窄 |
| `host` | 主機名 | 多機匯總時很重要 |
| `app[1234]` | journal 顯示的來源標記/PID | 可輔助比對來源進程,但不保證等於 `Main PID` |
| `failed to bind port` | 日誌正文 | 真正錯誤通常在這裡 |
| `-p err` | 查詢時的優先級過濾 | 不是日誌片段本身;只看 error 以上時用 |

> 小坑:服務剛重啟過時,加 `-b` 看本次開機,加 `-u 服務` 避免被其他日誌淹掉。

**⚡ 驗證**:
```bash
journalctl -n 10 --no-pager       # 預期:最近 10 條日誌
journalctl -p err -b --no-pager | tail   # 預期:本次開機的錯誤(可能為空)
journalctl --disk-usage           # 預期:Archived and active journals take up XXM
```

### ⚡ 配角速驗(`systemd-run` / `systemd-analyze`)

```bash
systemd-run --on-active=2 /bin/touch /tmp/sd-done   # 2 秒後執行一次(需 root)
sleep 3; ls -l /tmp/sd-done                          # 預期:檔案存在(transient timer 跑過了)
systemd-analyze 2>/dev/null                          # 預期:Startup finished in ... 開機耗時
systemd-analyze blame 2>/dev/null | head             # 預期:各服務啟動耗時降序
```

---

## 深挖

- systemd 架構、unit 類型、依賴/目標、cgroup 整合 → **`linux-handson/08-systemd-and-services`**
- reload/優雅重啟、不中斷連接 → **`distribution/zero-downtime-release`**
- 日誌歸集到 ELK/Loki(不只看本機 journal) → **`log-collection`**、**`logging`**
