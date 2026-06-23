# Lab · 分散式限流(對應 ch05 §2)

證明 ch05 的核心問題:**N 台網關怎麼合起來限流?** 兩個節點共用一個 Redis 計數 + Lua 原子腳本,`limit=10` 是**全域**的——不管請求落到哪台,合計第 11 次就被擋。

## 拓撲

```
curl ─┬─▶ node1:8001 ─┐
      └─▶ node2:8002 ─┴─▶ Redis (rate:alice 計數, Lua 原子 INCR+EXPIRE)
        各自是一個極簡網關節點,共用同一份配額
```

- `ratelimit.lua` — 固定窗口原子限流(INCR + 首次 EXPIRE + 超限判斷,單腳本原子執行)
- `app.py` — FastAPI 節點,`/ping?client=X` 對共享 Redis 跑 Lua
- 兩節點同一 image,靠 `NODE_ID` 區分

## 跑

```bash
docker compose up -d --build
bash test.sh          # 重置計數 → 交替打兩節點 12 次
docker compose down
```

## 預期輸出(實測)

```
第 1次 → node2: 200 count=1/10 (client=alice)
第 2次 → node1: 200 count=2/10 (client=alice)
 ...
第10次 → node1: 200 count=10/10 (client=alice)
第11次 → node2: 429 rate limited (client=alice)
第12次 → node1: 429 rate limited (client=alice)
```

**關鍵觀察**:`count` 跨 node1/node2 **連續遞增**(1,2,3,…,10),不是各算各的。這就是 ch05 解法 B「集中計數」:計數在 Redis,任一節點 `INCR` 的是同一個 key,所以合起來才是一份配額。

## 動手玩

- **把 Lua 換成「先 INCR 再單獨判斷+EXPIRE」兩步(非原子)**,並發壓測(`seq | xargs -P`)就可能看到計數穿透 limit——這就是 ch05 為什麼強調必須用 Lua。
- **改 `LIMIT`/`WINDOW`**(compose 的 environment)觀察窗口行為;固定窗口在窗口邊界會有「臨界突刺」(算法細節見 `system-design/01`)。
- **把 node1 停掉**(`docker compose stop node1`)再打,配額照樣全域生效——這就是「網關無狀態 + 狀態外移到 Redis」(ch08)的價值。

## 對應章節

- ch05 §2 解法 B(集中計數)、為什麼必須 Lua 原子
- Lua 實作的更多變體(滑動窗口等)見 `redis-handson/13-rate-limiting/`
- 「狀態外移讓網關無狀態」見 ch08
