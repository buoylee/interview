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
| `systemctl status nginx` | 看狀態 + 最近幾行日誌 | **最高頻**;一眼看 active/failed + PID + 退出碼 |
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
| `journalctl -u nginx` | 某服務的全部日誌 |
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

## 深挖

- systemd 架構、unit 類型、依賴/目標、cgroup 整合 → **`linux-handson/08-systemd-and-services`**
- reload/優雅重啟、不中斷連接 → **`distribution/zero-downtime-release`**
- 日誌歸集到 ELK/Loki(不只看本機 journal) → **`log-collection`**、**`logging`**
