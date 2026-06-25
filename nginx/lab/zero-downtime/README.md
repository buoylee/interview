# lab/zero-downtime — reload 期間零失敗實測

> 對照章節:ch08「運維與零停機」

## 目的

驗證 `nginx -s reload` 的**平滑重載**機制:在持續壓測期間發出 reload 訊號,確認**在途請求與新請求均不丟失(FAIL=0)**。

## 為何聚焦 reload 而非熱升級(USR2)

Nginx 熱升級二進制(`USR2` 訊號)的完整流程需要:
1. 替換磁碟上的 `nginx` 可執行檔
2. 向舊 master 發 `USR2`,讓它 fork 出新 master
3. 再依序發 `WINCH`(收舊 worker)、`QUIT`(收舊 master)

在容器環境中,**image 是唯讀的**,無法替換 `/usr/sbin/nginx` 二進制,加上容器不鼓勵直接修改正在執行的程序映像,故 USR2 熱升級在容器內演示受限。

實際生產中,不停機升級 Nginx 版本的容器做法是**滾動更新 Pod/容器**(Kubernetes rolling update 或 docker-compose 替換),由編排層保持連線不斷;USR2 則適用於裸機/VM 部署。

本 lab 聚焦 **`HUP`(reload)** ——它在容器內完全可行,且是日常推設定最高頻的操作。ch08 已說明 reload 的平滑機制:master 收到 `HUP` 後 fork 新 worker、舊 worker 處理完在途請求才退出,listen socket 由 master 全程持有,所以不丟連線。

## 快速開始

```bash
# 啟動
docker compose up -d
sleep 3

# 執行壓測 + 中途 reload
bash run.sh

# 清理
docker compose down -v
```

## 預期輸出

```
>>> 執行 nginx -s reload ...
>>> 執行 nginx -t (設定校驗) ...
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
>>> 等待壓測完成 ...

TOTAL=300 FAIL=0
PASS: reload 期間零失敗
```

## 關鍵觀察

| 指標 | 預期值 | 說明 |
|---|---|---|
| TOTAL | 300 | 全部 300 個請求都已發出 |
| FAIL | 0 | reload 期間無任何非 200 回應 |
| `nginx -t` | syntax ok | reload 前設定校驗通過 |

## reload 平滑機制(回扣 ch08)

```
client → [listen socket (master 持有,不關閉)]
             ↓
         舊 worker          新 worker
         (處理在途請求)   (接收新連線)
             ↓                ↓
         drain 完後退出    繼續服務
```

master 收 `HUP` → 校驗設定 → fork 新 worker(用新設定)→ 通知舊 worker 停止接新連線 → 舊 worker 把在途請求跑完後退出。因為 listen socket 從未關閉,客戶端感知不到任何中斷。
