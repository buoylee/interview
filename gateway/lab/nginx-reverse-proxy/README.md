# Lab · nginx 反向代理(對應 ch01)

最小可跑範例:一台 nginx 反代,後面兩個 echo 後端。證明三件 ch01 講的事——**worker 模型**、**upstream 輪詢**、**L7 按 path 路由**。

## 拓撲

```
curl ──▶ nginx:8080 ──┬─(/  輪詢)──▶ echo1:5678 "hello from echo1"
                      │              └▶ echo2:5678 "hello from echo2"
                      └─(/a 定向)───▶ echo1:5678
```

## 跑

```bash
docker compose up -d
bash test.sh          # 暖機 → 展示輪詢 + L7 路由 + worker 數
docker compose down
```

## 預期輸出(實測)

```
=== / 連打 6 次:預期 echo1/echo2 交替(輪詢)===
hello from echo1
hello from echo2
hello from echo1
hello from echo2
hello from echo1
hello from echo2

=== /a 連打 3 次:預期全 echo1(L7 按 path 定向)===
hello from echo1
hello from echo1
hello from echo1

=== nginx 進程數:1 master + N worker(= CPU 核)===
11                    # 1 master + 10 worker(機器 10 核;你的數字依核數而定)
```

## 看到什麼、對應 ch01 哪段

| 觀察 | 對應 |
|---|---|
| `/` 在 echo1/echo2 間交替 | upstream 輪詢負載均衡(ch01 §3、§5) |
| `/a` 永遠 echo1 | **L7** 代理認得 `path` 才能按路徑定向(ch01 §5);L4 做不到 |
| 進程數 = 1 + 核數 | master-worker 模型,worker 數 = CPU 核(ch01 §1) |

## 兩個刻意的設計(都是教學點)

1. **為什麼要「暖機」**:剛 `up` 時你若直接打,可能**前 ~10 秒全是 echo1**。因為啟動瞬間 echo2 還沒就緒,nginx 的**被動健康檢查**試了一次失敗,就把 echo2 標記 down 約 10s(`fail_timeout` 默認值),這段時間流量全導向健康的 echo1。等 echo2 恢復,輪詢才乾淨交替。**這正是 ch03「健康檢查」的伏筆**——網關會自動摘除不健康的後端。

2. **為什麼 demo 不開 `keepalive`**:upstream 連線池(ch01 §3)會復用一條已建立的暖連線,序列化請求時會一直黏在同一個後端,把輪詢效果蓋掉。連線池是 ch01 的正文教學點;此 lab 想「看見輪詢」,所以 `nginx.conf` 裡刻意註解掉它(見檔內說明)。
