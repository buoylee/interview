# MySQL Hands-on Lab + 系統筆記 設計文件

**日期**: 2026-05-13
**作者**: jimmylee
**目標倉庫位置**: `interview/mysql-handson/`
**參考設計**: `docs/superpowers/specs/2026-05-08-kafka-handson-design.md` (kafka-handson 同款骨架)

---

## 背景與動機

使用者已對 MySQL 有零散筆記（`interview/mysql/` 下含「索引.md」「事務-隔離級別-鎖.md」「執行原理-binlog.md」「MVCC-BufferPool.md」「死鎖.md」「分庫分表-遷移.md」「高可用.md」等共 ~717 行），但自評**「一知半解」**：

- 知道索引是 B+ 樹，但說不清三層能放多少行、為什麼不用 B 樹/紅黑樹、聯合索引順序怎麼定
- 知道排序「可能用臨時文件」，但不知道什麼時候會走、怎麼避免
- 寫 SQL 時不知道有沒有性能問題、能不能優化、底層怎麼執行
- 不清楚 Buffer Pool / Change Buffer / AHI 在整體執行流程中各管什麼
- 對 Redo / Undo / Binlog 的三日誌協作、兩階段提交、crash-safe 機制只記得名詞

**目標**：建立一份**系統的、流暢的、底層到上層串得通**的 MySQL 完整筆記，配可重跑的實驗環境。覆蓋兩條使用路徑——**面試衝刺**與**日常開發調優**——但**不拆成兩本書**，而是同一章內以段落分工服務兩類讀者。

## 非目標

- 不寫 MyISAM / Memory / Archive 等過時引擎的細節（InnoDB 為唯一深入引擎）
- 不寫 NDB Cluster、PolarDB、TiDB 等分散式變體（本項目是「原生 MySQL」）
- 不做完整的 BI / 報表類 SQL 優化（聚焦 OLTP 場景的調優）
- 不為 5.6 及更早版本特別寫章節（**MySQL 8.0 主線**，5.7 重大差異點在章內標註）
- 不追求生產級 chaos engineering（用 toxiproxy 即可，足以模擬主從延遲與網路抖動）
- 不為了完美 lab 而拖延寫第一個 scenario（Day 2 能跑通 explain 對照 scenario 就動手）

## 核心方法

**分層骨架（top-down）+ 場景單元（bottom-up）的混合式**，與 kafka-handson 一致：

- 章節按 MySQL 從底層到上層展開（存儲 → 索引 → 執行 → 並發 → 日誌 → 調優 → 複製 → 分庫 → 運維），確保最後筆記能講系統圖
- 每章內部由獨立可跑的 scenario 單元組成，每個 scenario 強制 **「預期 → 跑 → 實機告訴我」** 三段紀律
- 面試卡作為**反向產出**：章節寫完後再翻譯成面試題答案卡，每張卡都有實機 scenario 背書

### 為什麼不單拆「面試版 / 調優版」

兩條路徑共享 80% 的底層知識（B+ 樹、MVCC、鎖、explain 解讀）。拆開會嚴重重複，而且讓「為什麼」和「怎麼用」斷成兩本書，反而學不通。改用**章內分段**：每章固定有「日常開發應用」「調優實戰」「面試高頻考點」三個段落，讀者按需取用即可。

## 目錄結構

```
interview/mysql-handson/
├── README.md                       ← 入口：怎麼用 + 雙路徑導航 + lab 啟動方式
├── 00-lab/                         ← 實驗環境
│   ├── docker-compose.yml          ← MySQL 8.0 primary + replica + sysbench + Prom + Grafana + toxiproxy
│   ├── my.cnf/                     ← 預配好 slow log / general log / performance_schema / innodb 觀測參數
│   ├── init/                       ← 初始化 sql：建測試 schema + 灌數據腳本
│   ├── prometheus.yml
│   ├── grafana/dashboards/         ← mysqld_exporter 對應的 InnoDB / replication / query 三張板
│   └── Makefile                    ← up / down / reset / mysql / explain / slow / chaos-*
├── 01-architecture/                ← MySQL 整體架構（Server 層 + 引擎層 + 一條 SQL 的旅程）
│   ├── README.md
│   └── scenarios/
├── 02-innodb-storage/              ← 頁/區/段 + Buffer Pool + Change Buffer + AHI + Doublewrite
├── 03-indexing/                    ← B+樹 / 聚簇 vs 二級 / 聯合索引 / 覆蓋 / ICP / MRR
├── 04-execution-and-explain/       ← Parser → Optimizer（成本估算）→ Executor + Explain 完整解讀
├── 05-mvcc-and-transaction/        ← 事務 ACID + MVCC + Undo Log + RR 真相 + 幻讀
├── 06-locking/                     ← 行/表/間隙/Next-Key/插入意向 + 死鎖案例
├── 07-logs-and-crashsafe/          ← Redo / Undo / Binlog + WAL + 兩階段提交 + 組提交
├── 08-sql-tuning/                  ← 慢查日誌 / 索引設計 / JOIN / ORDER BY / GROUP BY / filesort / 臨時表
├── 09-replication-and-ha/          ← 主從複製 + 半同步 + MGR + 讀寫分離 + 延遲定位
├── 10-sharding-and-scaling/        ← 分庫分表 + 全局 ID + 跨庫事務 + 在線遷移
├── 11-ops-and-troubleshooting/     ← Online DDL / pt-osc / 備份恢復 / 參數調優 / 常見線上故障
├── 99-interview-cards/             ← 反向產物：把章節打包成面試題答案卡
│   ├── q-why-bplus-tree.md
│   ├── q-rr-can-prevent-phantom-or-not.md
│   ├── q-two-phase-commit.md
│   └── ...
└── templates/
    └── scenario-template.md
```

### 兩個關鍵架構決定

1. **lab 跟筆記分開但同 repo**：lab 在 `00-lab/`，scenario 引用 lab 腳本（`make explain SQL="..."`、`make chaos-replica-lag MS=1000`），而不是把 docker-compose 抄進每個 scenario。改 lab 一次，全部 scenario 受益。
2. **`99-interview-cards/` 是反向產物，不是源頭**：跑完 scenario、寫完章節筆記之後，再把它**翻譯**成面試卡。每張卡格式固定：問題 → 一句話回答 → 證據鏈接到 scenario / 章節段落。這保證每個答案背後都有實機支撐，不是背書。

### 與舊 `interview/mysql/` 的關係

- 舊筆記**保留不刪**，作為原始素材。
- 新章節在寫作時會**吸收**舊筆記中有價值的片段（例如「索引.md」裡的 B+ 樹三層估算、「事務-隔離級別-鎖.md」裡的隔離級別表、「MVCC-BufferPool.md」的 Buffer Pool 流程圖），不重新發明輪子。
- 全部 11 章寫完後，做一次 cleanup：把舊筆記裡仍未被吸收且仍有效的內容遷入，剩下作廢的封存到 `interview/mysql/_archive/`。

## 章節骨架（11 層）

每章固定三件事：**「我以為」→ 跑 N 個 scenario → 「實機告訴我」**。

每章 README 內部統一七段結構：

```markdown
1. 核心問題         本章解決什麼（一句話）
2. 直覺理解         用一個具體場景/比喻打開（避免術語堆疊）
3. 原理深入         圖示 + 數據結構 + 完整流程（面試底子）
4. 日常開發應用     寫代碼/建表/寫 SQL 時怎麼用    ← 日常路徑主菜
5. 調優實戰         具體 case：怎麼定位 + 怎麼改   ← 日常路徑主菜
6. 面試高頻考點     常見問題 + 易混淆對比表        ← 面試路徑主菜
7. 一句話總結       全章壓縮成 3-5 行帶回家
```

### 章節與規劃中的 scenarios

| # | 章節 | 對應舊筆記 | 規劃中的 scenarios（每章 3-6 個） |
|---|---|---|---|
| **01 架構** | `base.md` | 一條 SELECT 從連接到返回完整鏈路（連接器→解析→優化→執行→引擎）；query cache 為什麼被 8.0 移除（用 5.7 對照） |
| **02 InnoDB 存儲** | `MVCC-BufferPool.md` | Buffer Pool 命中率觀察；Change Buffer 對非唯一二級索引的寫加速；AHI 命中前後對比；Doublewrite 在 crash 後的恢復 |
| **03 索引** | `索引.md` | B+ 樹三層估算 + 實測；聯合索引最左前綴失效 case；覆蓋索引省回表；索引下推（ICP）開關前後 explain 對比；隱式類型轉換導致索引失效 |
| **04 執行 + Explain** | `執行計劃.md`, `執行原理-binlog.md` | Explain 每個欄位逐字段解讀（type/key/rows/Extra）；optimizer_trace 看成本估算；force index vs use index；同一 SQL 不同數據量下走不同計劃 |
| **05 MVCC + 事務** | `事務-隔離級別-鎖.md`, `MVCC-BufferPool.md` | RC vs RR 的 ReadView 時機差異；RR 下的快照讀 vs 當前讀；RR 能否避免幻讀（兩種情況：快照讀可以、當前讀靠 Gap Lock）；長事務對 undo 的影響 |
| **06 鎖** | `事務-隔離級別-鎖.md`, `死鎖.md` | 行鎖升級到表鎖（無索引時）；Gap Lock + Next-Key Lock 邊界；插入意向鎖；經典死鎖復現（兩個事務交叉更新）；`SHOW ENGINE INNODB STATUS` 解讀死鎖日誌 |
| **07 日誌 + Crash-safe** | `binlog.md`, `執行原理-binlog.md` | Redo Log 循環寫 + WAL；Undo Log 與 MVCC 的關係；Binlog 三種格式（statement/row/mixed）；**兩階段提交**完整時序；組提交（group commit）對吞吐的影響 |
| **08 SQL 調優** | （新，部分散在「索引.md」） | 慢查日誌定位 top SQL；filesort 觸發條件 + 觀察 `Sort_merge_passes`；臨時表（Using temporary）觸發條件；JOIN 順序與 BNL/HJ；LIMIT + OFFSET 深翻頁優化 |
| **09 複製 + 高可用** | `高可用.md`, `部署-架構.md` | 主從異步複製延遲觀察；半同步退化為異步的觸發條件；GTID 切換 vs 位點切換；**toxiproxy 注入網路延遲看主從滯後**；MGR 三節點選舉（如資源允許） |
| **10 分庫分表** | `分庫分表-迁移.md` | 分庫分表後跨庫 JOIN 怎麼辦；全局 ID 三種方案對比（雪花/號段/UUID）；在線遷移雙寫 + 校驗腳本；冷熱分離 |
| **11 運維** | （新） | Online DDL 三種演算法（INPLACE/COPY/INSTANT）；pt-online-schema-change 原理；mysqldump vs xtrabackup；常見線上故障：CPU 100% / 連接耗盡 / 主從斷裂 |

### 章節順序的理由

「底層先、上層後」是刻意的，**因為上層的詭異現象往往要靠底層解釋**：

- 第 3 章「索引」必須先有第 2 章「Buffer Pool / 頁」做地基，否則「為什麼三層 B+ 樹只要 3 次 IO」講不通
- 第 5 章「MVCC」必須先有第 7 章 Undo Log 的鋪墊（所以 05 章開頭會先提 undo，正式深入在 07）
- 第 8 章「SQL 調優」是前 7 章的**綜合應用**，所以放在中段
- 第 9-11 章是「外圍主題」——複製、分庫、運維——獨立可學，但需要前面 8 章的底子才能讀懂故障日誌

### 不單獨開的章節

- **JSON / 全文索引 / 空間索引**：面試問到的機率低，遇到時在 03-indexing 末尾用一小節掃過即可
- **PolarDB / Aurora 等雲託管變體**：超出原生 MySQL 範圍
- **數據倉庫類查詢優化**：聚焦 OLTP

## Scenario 單元模板

存在 `templates/scenario-template.md`，每個 scenario 都長一樣：

```markdown
# Scenario: <一句話描述>

## 我想驗證的問題
<一句話。例如：「同樣的 SQL，在 1k 行和 100w 行時 explain 是否會走不同計劃？」>

## 預期（寫實驗前的假設）
<一段話。把「以為」的行為寫下來。寫完才能跑，跑完才能對照。>

## 環境
- compose: `00-lab/docker-compose.yml`
- schema: `make init-schema NAME=sbtest`
- 灌數據: `make load ROWS=1000000`

## 步驟
1. ...
2. ...

## 實機告訴我（跑完當天填）
- 觀察到的 explain / status / log 截圖或片段
- 跟「預期」的差異

## ⚠️ 預期 vs 實機落差
<這是核心輸出。如果這段是空的或「完全一致」，scenario 太簡單或預期太模糊。>

## 連到的面試卡
- 99-interview-cards/q-xxx.md
```

### 紀律（與 kafka-handson 同款，不要省）

1. **「預期」必須在跑之前寫**，且要單獨 commit 一次。預期被實機污染就學不到東西了。
2. **「實機告訴我」當天填**。隔天就忘了當下的驚訝點。
3. **「⚠️ 預期 vs 實機落差」是這個方法的核心輸出**。每個 scenario 都「完全對應預期」說明 scenario 太簡單或預期太模糊。

## Lab 環境設計（00-lab）

### Docker compose 組件

| 服務 | 用途 | 端口 |
|---|---|---|
| `mysql-primary` (8.0) | 主庫 | 3306 |
| `mysql-replica` (8.0) | 從庫，用於 09-replication 章節 | 3307 |
| `mysql-5.7` (可選，懶啟動) | 5.7 對照，用於版本差異 scenario | 3357 |
| `sysbench` | 壓測 / 灌數據 | — |
| `mysqld_exporter` | Prometheus 抓 MySQL 指標 | 9104 |
| `prometheus` | 指標儲存 | 9090 |
| `grafana` | 觀察面板 | 3000 |
| `toxiproxy` | 在 primary→replica 之間注入延遲 / 斷網 | 8474 |
| `adminer` | 可選 web UI（profile，預設不啟動），方便看 schema | 8080 |

### 預配的 my.cnf 關鍵項

- `slow_query_log=ON`、`long_query_time=0.1`、`log_queries_not_using_indexes=ON`
- `general_log` 可隨需開關（Makefile 提供 `make general-log-on/off`）
- `performance_schema=ON` 並啟用 `events_statements_history_long`、`events_waits_history_long`
- `innodb_buffer_pool_size` 設小（256M）以便 scenario 觀察淘汰
- `innodb_print_all_deadlocks=ON`、`innodb_status_output=ON`
- `binlog_format=ROW`（同時保留切換 statement/mixed 的 scenario）
- `gtid_mode=ON`、`enforce_gtid_consistency=ON`

### Makefile 速查（規劃）

```bash
make up                                       # 起整套
make down                                     # 停掉
make reset                                    # 連 volume 一起清

make mysql                                    # 進 primary 的 mysql cli
make mysql-replica                            # 進 replica
make load ROWS=1000000                        # sysbench 灌數據

make explain SQL="select ..."                 # 自動跑 explain + optimizer_trace
make slow                                     # tail 慢查日誌
make general-log-on / make general-log-off
make innodb-status                            # SHOW ENGINE INNODB STATUS
make pfs-top                                  # performance_schema top SQL

make chaos-replica-lag MS=500                 # toxiproxy 給主→從加延遲
make chaos-replica-cut                        # 切斷主從網路
make chaos-restore                            # 還原
```

## 工作流程

### 寫一章的 SOP

1. **章節 README 骨架先寫**（七段結構），可以先放占位，但段落順序固定
2. **挑 3-6 個 scenario**，每個 scenario 先寫「預期」並 commit
3. **跑 lab 驗證**，填「實機告訴我」+「預期 vs 實機落差」並 commit
4. **回頭補 README 的「原理深入」「調優實戰」「面試高頻考點」**，引用本章的 scenario
5. **章末產出 1-3 張面試卡** 到 `99-interview-cards/`，每張卡引用本章 scenario 作為證據

### 寫一個 scenario 的 SOP

1. 複製 `templates/scenario-template.md` 到 `0X-xxx/scenarios/`
2. 填「我想驗證的問題」+「預期」→ commit 一次
3. 跑 lab，填「實機告訴我」+「⚠️ 預期 vs 實機落差」→ commit 第二次
4. 在對應章節 README 加一行引用

### 何時可以略過 scenario

某些章節內容（例如 11-ops 的「mysqldump vs xtrabackup 對比」）是純概念對比，沒有實機可驗的部分，README 內直接寫即可，不強行湊 scenario。但**任何牽涉「行為觀察」「性能差異」「故障恢復」的點都必須有 scenario**。

## 落地里程碑（建議節奏）

> 不寫死週數，由 writing-plans 階段拆成具體 tasks。

- **Phase 0**：lab 起得來（`make up` 能跑、Grafana 看到 InnoDB 指標）
- **Phase 1**：03-indexing 章節完整跑通（**第一個有完整 scenario 的章節**，因為使用者最在意這塊）
- **Phase 2**：02 / 04 / 05 / 06 補齊（底層核心四章）
- **Phase 3**：01 / 07 / 08（架構總覽 + 日誌 + 調優實戰）
- **Phase 4**：09 / 10 / 11（外圍三章）
- **Phase 5**：99-interview-cards 全量產出 + 舊 `mysql/` 目錄 cleanup

## 風險與緩解

| 風險 | 緩解 |
|---|---|
| Lab 環境太重，啟動慢勸退 | mysqld_exporter / grafana / toxiproxy 設為 profile，`make up` 默認只起 mysql primary，按需 `make up-full` |
| 章節寫到一半變成抄書 | 強制「scenario 先行 + 預期 vs 實機」紀律；空洞的「原理深入」段要被 scenario 帶出問題 |
| 5.7 / 8.0 差異散落各章難維護 | 統一在每章末加 **「8.0 vs 5.7 差異」小節**（如果有的話），不在章內穿插 |
| 面試卡和 scenario 重複維護 | 卡片**只寫一句話結論 + 連結**，不重述 scenario 內容 |
| 舊 `mysql/` 目錄越積越亂 | Phase 5 強制 cleanup，舊文件遷入 `_archive/` 或合併 |

## 成功標準

寫完之後，使用者能做到：

1. **任意一條 SELECT/UPDATE/INSERT**：能口述它在 MySQL 內部走的完整路徑（連接器 → 解析 → 優化 → 執行 → 引擎 → 頁/Buffer Pool → 索引 → 日誌）
2. **任意一個慢 SQL**：能用 explain + optimizer_trace + slow log 三件套定位瓶頸，並給出至少一個優化方向
3. **面試常見題**：「為什麼用 B+ 樹」「RR 能不能避免幻讀」「兩階段提交為什麼」「主從延遲怎麼定位」——能在不看筆記的情況下講 90 秒並指向自己跑過的 scenario
4. **遇到生產故障**：CPU 100% / 鎖等待 / 主從斷裂 等場景能在 5 分鐘內列出排查順序

---

**下一步**：本 spec 落庫後進入 writing-plans，把 11 章 + 00-lab + 99-cards 拆成具體可執行的 task 序列。
