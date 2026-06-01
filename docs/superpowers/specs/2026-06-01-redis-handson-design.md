# Redis Hands-on Lab + 系統筆記 設計文件

**日期**: 2026-06-01
**作者**: jimmylee
**目標倉庫位置**: `interview/redis-handson/`
**參考設計**: `docs/superpowers/specs/2026-05-13-mysql-handson-design.md`（mysql-handson 同款骨架）

---

## 背景與動機

使用者已對 Redis 有零散筆記（`interview/redis/` 下含「概述.md」「數據結構.md」「持久化.md」「淘汰策略.md」「部署模式.md」「緩存.md」「緩存穿透.md」「事務-lua.md」「分布式鎖-redlock.md」「redisson-rlock.md」「redis-QA.md」等共 ~1600 行），**面試理論背得不錯，但自評「實際工作中用起來無從下手」**：

- 知道有 5 種數據類型 + 底層編碼，但寫業務時不知道**什麼場景該掏哪個結構**
- 緩存穿透/擊穿/雪崩、緩存一致性背過名詞，但**沒在並發下親手復現過髒讀**，落地時心裡沒底
- 分布式鎖知道 Redisson / RedLock，但說不清看門狗續期、主從切換丟鎖的真實時序
- 生產問題（大 key / 熱 key / 延遲毛刺 / 連接池）幾乎沒有定位經驗，**屬於完全真空區**
- cluster / 主從 / 哨兵的故障轉移只記得流程文字，沒看過實機選舉與客戶端重連

**目標**：建立一份**系統的、能落地的、原理到應用串得通**的 Redis 完整筆記，配可重跑的實驗環境。一套 lab + scenario + 面試卡同時服務三條路徑——**實戰會用 / 用實機盤活背過的理論 / 衝資深面試深度**——但**不拆成多本書**，而是同一章內以段落分工。

目標版本：**Redis 7.x（7.4 主線）**——listpack、FUNCTION、RESP3 客戶端緩存、multi-part AOF、`--hotkeys` 等新特性在章內標註。

## 非目標

- 不深入 Redis C 源碼逐行（資料結構講到「編碼 + 觸發轉換的參數閾值 + 實機 `OBJECT ENCODING` 觀察」即止，不讀 `t_zset.c`）
- 不寫 Redis Stack 全家桶模塊（RediSearch / RedisJSON / RedisTimeSeries / RedisGraph）——聚焦原生 Redis；布隆過濾器以 bitmap 自實現 + 提一句 RedisBloom 對照
- 不寫 KeyDB / Dragonfly / Garnet 等兼容變體
- 不追求生產級 chaos（toxiproxy 注入延遲/斷網即可，足以模擬主從滯後與哨兵切換）
- 不為 6.0 以前版本特別寫章節（重大差異點如 io-threads(6.0)、listpack(7.0)、FUNCTION(7.0) 在章內標註）
- 不為了完美 lab 而拖延寫第一個 scenario（lab 起得來就先跑 02-data-structures 的編碼轉換 scenario）

## 核心方法

**分層骨架（top-down）+ 場景單元（bottom-up）的混合式**，與 mysql-handson 一致：

- 章節按 Redis 從「為什麼快 → 用什麼存 → 怎麼不丟/不爆 → 怎麼用對 → 怎麼擴 → 怎麼救」展開，確保最後筆記能講系統圖
- 每章內部由獨立可跑的 scenario 單元組成，每個 scenario 強制 **「預期 → 跑 → 實機告訴我」** 三段紀律
- 面試卡作為**反向產出**：章節寫完後再翻譯成面試題答案卡，每張卡都有實機 scenario 背書

### 客戶端語言：cli 主幹 + Java/Redisson 應用模式 + Python 對照

使用者瓶頸是「Redis 本身不會用」，不是客戶端語言，所以客戶端語言要選**最不佔腦力**的，把認知預算留給 Redis。資深 Redis 內容裡 ~70% 是語言無關的（資料結構、持久化、淘汰、cluster、大key/熱key、延遲排查），全在服務端用 `redis-cli` + `redis.conf` 發生。客戶端語言只在少數**應用模式**上才真正分叉。因此分層：

- **主幹（原理 / 資料結構 / 運維 / 排查）= `redis-cli` + `redis.conf` + Lua**：語言無關，最貼 Redis 本體，也最對面試胃口
- **應用模式章節（鎖 / 限流 / 緩存重建）= Java/Redisson 為主**：Redisson 把 RLock / RedLock / RRateLimiter / RBloomFilter / 延遲隊列 一整套模式現成實現，是絕佳「應用模式教具」，也是使用者最熟的生態（學習成本最低）
- **每個應用模式補一段 redis-py 的「對照鏡像」**（幾行）：順手搭 Python 遷移的橋，不雙倍工作量

### 為什麼不單拆「面試版 / 實戰版」

三條路徑共享 ~80% 的底層知識（編碼轉換、持久化邊界、cluster 路由、鎖時序）。拆開會嚴重重複，而且讓「為什麼」和「怎麼用」斷成幾本書，反而學不通。改用**章內分段**：每章固定有「日常開發應用」「調優實戰」「面試高頻考點」三個段落，讀者按需取用。

## 目錄結構

```
interview/redis-handson/
├── README.md                       ← 入口：怎麼用 + 三路徑導航 + lab 啟動方式
├── 00-lab/                         ← 實驗環境
│   ├── docker-compose.yml          ← redis 7.4 single + cluster(3主3從) + sentinel + redis_exporter + Prom + Grafana + toxiproxy + RedisInsight
│   ├── conf/                       ← 預配好 maxmemory / appendonly / slowlog / latency-monitor / *-max-listpack-* 等觀測參數
│   ├── init/                       ← 灌數據腳本（造大量 key / 大 key / 熱 key）
│   ├── cluster/                    ← cluster create 腳本 + sentinel.conf
│   ├── prometheus.yml
│   ├── grafana/dashboards/         ← redis_exporter 對應的 memory / commands / persistence / replication 面板
│   └── Makefile                    ← up / down / reset / cli / cluster-init / chaos-* / bigkeys / slowlog / latency
├── 01-execution-model/             ← 單線程 + epoll/IO 多路復用 + 6.x io-threads + 命令生命週期 + 什麼命令會卡
│   ├── README.md
│   └── scenarios/
├── 02-data-structures/             ← 5 類型 + 底層編碼(SDS/listpack/quicklist/intset/skiplist) + OBJECT ENCODING 實測 + 選型決策表
├── 03-advanced-types/              ← bitmap / HyperLogLog / GEO / Stream / bitfield + 每個配「什麼業務才掏它」
├── 04-expiry-eviction/             ← 惰性+定期刪除 + maxmemory + 8 策略 + LRU近似 vs LFU + 灌滿實測
├── 05-persistence/                 ← RDB(fork/COW) + AOF(fsync/rewrite) + 混合 + 丟數據邊界 + kill -9 恢復對比
├── 06-caching-patterns/            ← Cache-Aside/讀寫穿透/回寫 + 一致性(延遲雙刪/binlog) + 穿透擊穿雪崩 + 布隆/邏輯過期/互斥重建  ★真空區①
├── 07-distributed-locks/           ← SETNX+Lua / Redisson 看門狗 / RedLock 爭議 / fencing token / redis-py 對照
├── 08-transactions-scripting/      ← MULTI/WATCH 樂觀鎖 / Lua 原子性與限制 / pipeline≠事務 / 7.x FUNCTION
├── 09-pubsub-streams-mq/           ← pub/sub vs List vs Stream 當 MQ（消費組/ack/PEL/死信/trim）取捨
├── 10-replication-sentinel/        ← psync 全量/部分 + 複製積壓緩衝 + 異步丟數據邊界 + 哨兵故障轉移 + 腦裂
├── 11-cluster/                     ← 16384 槽/CRC16/MOVED&ASK/客戶端路由/reshard/gossip/投票/hash tag
├── 12-production-ops/              ← 大key定位拆分 / 熱key打散 / SLOWLOG / 延遲毛刺歸因 / 連接池 / RESP3 客戶端緩存 / ACL 安全  ★真空區②
├── 13-rate-limiting/               ← 固定/滑動窗口(ZSet)/令牌桶(Lua) / Redisson RRateLimiter / redis-py 對照
├── 99-interview-cards/             ← 反向產物：把章節打包成面試題答案卡
│   ├── q-why-redis-single-thread-fast.md
│   ├── q-cache-consistency-delete-vs-write.md
│   ├── q-redlock-controversy.md
│   └── ...
└── templates/
    └── scenario-template.md
```

### 兩個關鍵架構決定

1. **lab 跟筆記分開但同 repo**：lab 在 `00-lab/`，scenario 引用 lab 腳本（`make cli`、`make bigkeys`、`make chaos-lag MS=1000`、`make cluster-init`），而不是把 docker-compose 抄進每個 scenario。改 lab 一次，全部 scenario 受益。
2. **`99-interview-cards/` 是反向產物，不是源頭**：跑完 scenario、寫完章節筆記之後，再把它**翻譯**成面試卡。每張卡格式固定：問題 → 一句話回答 → 典型場景表 → 排查 SOP → 證據鏈接到 scenario / 章節段落 → 易追問延伸。保證每個答案背後都有實機支撐。

### 與舊 `interview/redis/` 的關係

- 舊筆記**保留不刪**，作為原始素材與遷移來源。
- 新章節寫作時**吸收並用實機重新驗證**舊筆記中有價值的片段（「數據結構.md」463 行 → 02 章；「持久化.md」→ 05；「部署模式.md」主從/哨兵/cluster → 10/11；「緩存.md」「緩存穿透.md」→ 06；「redisson-rlock.md」「redlock.md」「分布式鎖-redlock.md」「事務-lua.md」→ 07/08；「redis-QA.md」477 行 → 拆進 99-cards）。**不重新發明輪子，但每條結論都要有一個 scenario 背書，把「背過的」變成「驗過的」。**
- 全部 13 章寫完後做一次 cleanup：仿照倉庫既有先例（`linux → linux-handson 舊目錄歸檔並重定向`），把 `interview/redis/` 歸檔 + 留一個重定向 README 指向 `redis-handson/`。

## 章節骨架（13 層）

每章固定三件事：**「我以為」→ 跑 N 個 scenario → 「實機告訴我」**。

每章 README 內部統一七段結構：

```markdown
1. 核心問題         本章解決什麼（一句話）
2. 直覺理解         用一個具體場景/比喻打開（避免術語堆疊）
3. 原理深入         圖示 + 數據結構 + 完整流程（面試底子）
4. 日常開發應用     寫代碼/選型/落地時怎麼用      ← 實戰路徑主菜
5. 調優實戰         具體 case：怎麼定位 + 怎麼改   ← 實戰路徑主菜
6. 面試高頻考點     常見問題 + 易混淆對比表        ← 面試路徑主菜
7. 一句話總結       全章壓縮成 3-5 行帶回家
```

### 章節與規劃中的 scenarios

| # | 章節 | 對應舊筆記 | 規劃中的 scenarios（每章 3-6 個） |
|---|---|---|---|
| **01 執行模型** | 概述、單線程-網絡IO | KEYS vs SCAN 在 100w key 下阻塞實測（`--latency` 期間跑 KEYS）；io-threads 開關對吞吐影響（redis-benchmark）；大 `LRANGE 0 -1` / 大 Lua 卡住其他命令 |
| **02 數據結構** | 數據結構 | hash listpack→hashtable 觸發閾值實測（改 `hash-max-listpack-entries`）；zset listpack→skiplist 轉換 + 內存對比；String int/embstr/raw 三態與 44 字節邊界；intset→hashtable |
| **03 高級類型** | redis-steam、redis-channel | bitmap 簽到 vs Set 內存對比；HyperLogLog 1000w UV 誤差 + 12KB 內存；Stream 消費組 `XREADGROUP`/`XACK`/`XPENDING`/`XAUTOCLAIM` 死信；GEO `GEOSEARCH` 附近的人 |
| **04 過期淘汰** | 淘汰策略 | maxmemory 撐滿看 `allkeys-lru` vs `noeviction` 報錯；LRU 近似 vs LFU 在熱點訪問下命中差異；大量 key 同秒過期看定期刪除 CPU 抖動 |
| **05 持久化** | 持久化 | `bgsave` fork 期間 latency 毛刺（`--latency-history`）；`appendfsync always` vs `everysec` 吞吐對比；`kill -9` 後 RDB-only / AOF / 混合 恢復數據量對比；AOF rewrite 期間觀測 |
| **06 緩存模式** ★ | 緩存、緩存穿透 | 穿透：布隆過濾器（bitmap 自實現）擋不存在 key；擊穿：邏輯過期 vs 互斥鎖（`SET NX`）重建對比；雪崩：TTL 加隨機抖動；一致性：先刪緩存 vs 先更庫 在並發下髒讀復現 + 延遲雙刪 |
| **07 分布式鎖** | redisson-rlock、redlock、分布式鎖-redlock、事務-lua | `SET NX PX` + Lua 釋放（防誤刪他人鎖）；Redisson RLock 看門狗自動續期觀察；主從切換導致鎖丟失復現（RedLock 動機）；redis-py 對照實現 |
| **08 事務與腳本** | 事務-lua | `MULTI/EXEC`+`WATCH` 樂觀鎖 CAS（並發改同 key 觸發 abort）；Lua 原子扣庫存 vs 非原子競態；pipeline 吞吐 vs 單條 RTT（證明 pipeline≠事務）；`FUNCTION` vs `EVAL` |
| **09 pub/sub 與 Stream** | （新） | pub/sub 消費者掉線丟消息 vs Stream 消費組重連補消費；List `BRPOP` 當隊列 vs Stream PEL；`XAUTOCLAIM` 死信 + `MAXLEN` trim |
| **10 複製與哨兵** | 部署模式 | psync 全量(`FULLRESYNC`) vs 部分(`CONTINUE`) 觸發條件（repl-backlog 溢出）；toxiproxy 注入主從延遲看 offset 滯後；哨兵故障轉移（kill 主，觀察選舉 + 客戶端重連）；腦裂 `min-replicas-to-write` 阻止主寫 |
| **11 cluster** | 部署模式 | CRC16 槽計算 + `MOVED` 重定向（cli 非 `-c` 觸發）；hash tag `{}` 讓 multi-key 落同槽；reshard 遷移槽期間 `ASK` 重定向；kill 一個 master 看 failover 投票 + slave 升主 |
| **12 生產運維** ★ | （新） | `--bigkeys`/`--memkeys` 定位大 key + 拆分前後對比；`--hotkeys`（需 LFU）+ 本地緩存緩解熱 key；`SLOWLOG` 抓慢命令；延遲毛刺歸因（`LATENCY DOCTOR`/`LATENCY HISTORY`）；連接池打滿 + RESP3 `CLIENT TRACKING` 客戶端緩存命中 |
| **13 限流** | （新） | 固定窗口 `INCR`+`EXPIRE` 臨界突刺問題復現；滑動窗口 ZSet 實現；令牌桶 Lua 原子；Redisson `RRateLimiter` 對照 + redis-py 對照 |

### 章節順序的理由

「為什麼快 → 存什麼 → 不丟不爆 → 用對 → 擴 → 救」是刻意的：

- 01 執行模型先講「單線程為什麼快、什麼會卡」，是後面所有「不要用 KEYS / 大 key 為什麼危險」的地基
- 02 數據結構是一切應用的詞彙表，必須在 06/13（緩存/限流要選結構）之前
- 06 緩存模式、07 鎖、08 事務 是「用對」的核心三章，也是使用者最痛的真空區之一
- 10/11 複製/cluster 是「擴」，需要 05 持久化（psync 用到 RDB）做鋪墊
- 12 生產運維是前面全部的**綜合應用**，放在擴展之後，因為大 key/熱 key/延遲歸因要懂編碼、持久化、複製才能解釋

### 不單獨開的章節

- **Redis Stack 模塊（RediSearch/RedisJSON/...）**：超出原生 Redis，06 章布隆用 bitmap 自實現時提一句 RedisBloom 對照即可
- **客戶端各語言 SDK 細節**：只在應用模式章帶 Java/Redisson + redis-py 對照，不為每種語言開章
- **Redis 7.x 新數據類型細節（如 listpack 的 entry 編碼）**：在 02 章末用一小節掃過，不逐字節拆

## Scenario 單元模板

存在 `templates/scenario-template.md`，每個 scenario 都長一樣（沿用 mysql-handson 同款）：

```markdown
# Scenario: <一句話描述>

## 我想驗證的問題
<一句話。例：「同一個 hash，entry 從 127 漲到 128 時 OBJECT ENCODING 會不會從 listpack 變 hashtable？」>

## 預期（寫實驗前的假設）
<把「以為」的行為寫下來，越具體越好。寫完才能跑，跑完才能對照。>

> 紀律：本節填完後請單獨 commit 一次，再開始跑 lab。

## 環境
- compose: `00-lab/docker-compose.yml`
- 起 lab：`make up`（cluster scenario 用 `make up-cluster && make cluster-init`）
- 造數據：`make load`（如適用）

## 步驟
1. ...
2. ...

## 實機告訴我（跑完當天填）
```
<貼 redis-cli 輸出 / INFO 片段 / SLOWLOG / LATENCY 報告>
```
觀察到的關鍵事實：
- ...

## ⚠️ 預期 vs 實機落差
<這是核心輸出。完全對應預期 = scenario 太簡單或預期太模糊。>
- 我以為：……
- 實際：……
- 我學到：……

## 連到的面試卡
- 99-interview-cards/q-xxx.md
```

### 紀律（與 mysql-handson 同款，不要省）

1. **「預期」必須在跑之前寫**，且要單獨 commit 一次。預期被實機污染就學不到東西了。
2. **「實機告訴我」當天填**。隔天就忘了當下的驚訝點。
3. **「⚠️ 預期 vs 實機落差」是這個方法的核心輸出**。每個 scenario 都「完全對應預期」說明 scenario 太簡單或預期太模糊。

## Lab 環境設計（00-lab）

### Docker compose 組件

| 服務 | 用途 | 端口 | profile |
|---|---|---|---|
| `redis` (7.4) | 單機，默認啟動 | 6379 | （默認） |
| `redis-node-1..6` | cluster 3 主 3 從 | 7001-7006 | `cluster` |
| `redis-sentinel-1..3` + 主從 | 哨兵故障轉移 | 26379+ | `sentinel` |
| `redis_exporter` | Prometheus 抓 Redis 指標 | 9121 | `obs` |
| `prometheus` | 指標儲存 | 9090 | `obs` |
| `grafana` | 觀察面板 | 3000 | `obs` |
| `toxiproxy` | 主從/cluster 之間注入延遲 / 斷網 | 8474 | `cluster`/`sentinel` |
| `redisinsight` | 官方 Web GUI，看 key/編碼/內存直覺 | 5540 | `ui` |

默認 `make up` 只起單機 redis；cluster / sentinel / obs / ui 各為獨立 profile，按需起，避免 lab 太重勸退。

### 預配的 conf 關鍵項（`conf/redis.conf`）

- `maxmemory 256mb`、`maxmemory-policy noeviction`（scenario 內切換觀察淘汰）
- `appendonly yes`、`appendfsync everysec`、`save 60 1000`（混合持久化；scenario 內切 `always` 對比）
- `slowlog-log-slower-than 10000`（10ms）、`slowlog-max-len 128`
- `latency-monitor-threshold 100`（開啟 LATENCY 監控）
- `hash-max-listpack-entries`/`hash-max-listpack-value`/`list-max-listpack-size`/`set-max-intset-entries`/`set-max-listpack-entries`/`zset-max-listpack-entries`/`zset-max-listpack-value`（02 章編碼轉換 scenario 直接調）
- `io-threads`（01 章 io-threads scenario 切換）
- `notify-keyspace-events`（鍵空間通知 scenario 開）
- cluster profile：`cluster-enabled yes`、`cluster-node-timeout 5000`
- 12 章安全：`protected-mode`、`requirepass` / ACL `user` 規則

### Makefile 速查（規劃）

```bash
make up / down / reset / ps                   # 單機 lab 生命週期

make cli                                       # redis-cli 進單機
make cli-cluster                               # redis-cli -c 進 cluster
make up-cluster && make cluster-init           # 起 6 節點 + 建 3主3從
make up-sentinel                               # 起 1主2從 + 3 哨兵
make up-obs                                     # redis_exporter + Prom + Grafana
make up-ui                                      # RedisInsight (http://localhost:5540)

make load [N=1000000]                          # 造大量 key（編碼/淘汰/bigkeys 用）
make bench [ARGS=...]                           # redis-benchmark
make slowlog                                    # SLOWLOG GET
make latency                                    # redis-cli --latency-history
make bigkeys                                    # --bigkeys / --memkeys / --hotkeys
make encoding K=mykey                           # OBJECT ENCODING
make mem K=mykey                                # MEMORY USAGE
make info S=memory                              # INFO <section>

make chaos-lag MS=500                           # toxiproxy 給複製鏈路加延遲
make chaos-cut                                  # 切斷主從 / 節點
make chaos-restore                              # 還原
```

## 工作流程

### 寫一章的 SOP

1. **章節 README 骨架先寫**（七段結構），可先放占位，但段落順序固定
2. **挑 3-6 個 scenario**，每個先寫「預期」並 commit
3. **跑 lab 驗證**，填「實機告訴我」+「⚠️ 預期 vs 實機落差」並 commit
4. **回頭補 README 的「原理深入」「調優實戰」「面試高頻考點」**，引用本章 scenario
5. **章末產出 1-3 張面試卡** 到 `99-interview-cards/`，每張引用本章 scenario 作為證據

### 寫一個 scenario 的 SOP

1. 複製 `templates/scenario-template.md` 到 `0X-xxx/scenarios/`
2. 填「我想驗證的問題」+「預期」→ commit 一次
3. 跑 lab，填「實機告訴我」+「⚠️ 預期 vs 實機落差」→ commit 第二次
4. 在對應章節 README 加一行引用

### 何時可以略過 scenario

純概念對比（如 06 章「Cache-Aside vs Read-Through 的職責劃分」）沒有實機可驗的部分，README 內直接寫即可，不強行湊 scenario。但**任何牽涉「行為觀察」「性能差異」「故障恢復」「編碼/內存變化」的點都必須有 scenario**。

## 落地里程碑（建議節奏）

> 不寫死週數，由 writing-plans 階段拆成具體 tasks。按使用者痛點前置——**先建「最小可用流暢度」，直擊「無從下手」**。

- **Phase 0**：lab 起得來（`make up` + `make cli` 能跑；`make up-ui` RedisInsight 看到 key）
- **Phase 1（最小可用流暢度）**：`02 數據結構` → `06 緩存模式` → `07 分布式鎖` → `12 生產運維`（四章直擊真空區與選型痛點）
- **Phase 2（深度與廣度）**：`01 執行模型` / `04 過期淘汰` / `05 持久化` / `08 事務腳本` / `13 限流`
- **Phase 3（擴展與外圍）**：`03 高級類型` / `09 pub/sub & Stream` / `10 複製哨兵` / `11 cluster`
- **Phase 4**：`99-interview-cards` 全量產出（含拆解舊 `redis-QA.md` 477 行）+ 舊 `redis/` 目錄歸檔重定向

面試卡隨章產出，不單列階段；Phase 4 只做「補齊 + 把舊 QA 拆卡」。

## 風險與緩解

| 風險 | 緩解 |
|---|---|
| Lab 太重（cluster 6 節點 + 監控）啟動慢勸退 | cluster/sentinel/obs/ui 全設 profile，`make up` 默認只起單機 redis，按需起 |
| 章節寫到一半變成抄書 | 強制「scenario 先行 + 預期 vs 實機」紀律；空洞的「原理深入」要被 scenario 帶出問題 |
| Java/Redisson 與 cli 主幹混雜，讀者迷路 | 應用模式章固定結構：先 cli/Lua 講原理 → Redisson 落地 → redis-py 對照鏡像，三段分明 |
| 6.x/7.x 版本差異散落 | 統一在涉及的章末加「版本差異」小節（io-threads/listpack/FUNCTION/RESP3），不穿插 |
| 面試卡和 scenario 重複維護 | 卡片只寫一句話結論 + 場景表 + 鏈接，不重述 scenario 內容 |
| 舊 `redis/` 目錄越積越亂 | Phase 4 強制歸檔重定向，仿 linux-handson 先例 |

## 成功標準

寫完之後，使用者能做到：

1. **拿到一個業務需求**（簽到 / 排行榜 / 附近的人 / 限流 / 去重計數 / 分布式鎖）：能在 30 秒內說出該用哪個數據結構或模式，並指向自己跑過的 scenario
2. **緩存三件套**：能在並發下親手復現過穿透/擊穿/雪崩 + 一致性髒讀，講清每種的成因與自己驗過的解法（布隆 / 互斥重建 / 邏輯過期 / 延遲雙刪）
3. **生產故障**：大 key / 熱 key / 延遲毛刺 / 連接耗盡 場景，能用 `--bigkeys`/`--hotkeys`/`SLOWLOG`/`LATENCY DOCTOR` 在 5 分鐘內列出排查順序
4. **面試常見題**：「單線程為什麼快」「RedLock 爭議」「主從切換會不會丟鎖/丟數據」「cluster 怎麼路由 + 故障轉移」——能在不看筆記下講 90 秒並指向自己跑過的 scenario
5. **理論盤活**：舊筆記裡背過的每個結論（持久化丟數據邊界、淘汰策略、psync 全量/部分）都有一個實機 scenario 背書，從「記得名詞」升級到「驗過、講得出所以然」

---

**下一步**：本 spec 落庫後進入 writing-plans，把 13 章 + 00-lab + 99-cards 按上述 Phase 拆成具體可執行的 task 序列。
