# MySQL 資深場景推理層設計

- **日期**：2026-07-30
- **目標位置**：`mysql-handson/13-senior-scenarios/`
- **狀態**：設計已確認，尚未實作

## 1. 結論

這次補強的核心不是繼續擴寫 MySQL 原理，也不是為每一道面試題新增一篇答案，而是補上目前教程缺少的「跨章組裝能力」：

```text
既有原理
  → 陌生問題的約束辨識
  → 跨章執行鏈
  → 成本與正確性分析
  → 基準方案與取捨
  → 驗證、停止、恢復、回滾
  → 30 秒與 3–5 分鐘口述答案
```

`mysql-handson/01–11` 繼續擔任機制與事實的 canonical owner；新增的 `13-senior-scenarios` 只負責把既有知識組裝成資深工程師／架構師等級的場景答案。經全 repository 去重後，只新增四個真正缺少的場景文件，其餘問題全部路由到既有 owner。

## 2. 背景與問題診斷

學習者已接近讀完 `mysql-handson`，仍然難以回答「如何高效且安全地匯入 1,000 萬行」之類的陌生問題。這不等於前面內容完全沒學會，也不代表答案只是少背幾個參數。

目前 repository 已有大量材料：

- `01–11` 已覆蓋架構、InnoDB、索引、執行計畫、交易、鎖、日誌、SQL 調優、複製／HA、分片與運維；
- `12-interview-cheatsheet` 已有大量問答式濃縮內容；
- `99-interview-cards` 已有多張反向練習卡；
- `00-lab` 已能支援一般 MySQL、複製、觀測與獨立 InnoDB Cluster HA 實驗。

真正的缺口是：既有內容多以「單章機制」或「已知題目的答案」組織，學習者遇到新場景時，不知道如何從約束開始，跨章拼出可執行、可驗證、可恢復的方案。

因此本設計解決的是「輸出與組裝層」缺失，而不是再建一套更長的 MySQL 百科。

## 3. 目標與成功標準

### 3.1 目標讀者

- 已讀過一輪 MySQL 基礎與 `mysql-handson`；
- 準備資深後端工程師、Tech Lead 或架構師面試；
- 能理解單一概念，但尚未穩定地把多個概念組成場景方案。

### 3.2 能力目標

面對未見過的 MySQL 場景，學習者必須能依序回答：

```text
約束
  → 執行鏈
  → 成本／瓶頸
  → 正確性／風險
  → 基準方案
  → 替代方案／取捨
  → 驗證
  → 恢復／回滾
```

這條順序是所有新場景的共同解題器，不要求背出唯一答案。

### 3.3 面試輸出標準

每個新增場景都要產出兩種答案：

- **30 秒答案**：先問最關鍵的約束，再給基準方案、最大風險與驗證方式；
- **3–5 分鐘答案**：完整走過執行鏈、成本模型、正確性、方案取捨、停止條件與恢復／回滾。

每篇還要提供追問樹，讓學習者能處理面試官改變條件，例如「表正在承載線上寫入」、「不能停機」、「有主從」、「磁碟不夠」、「允許重跑」或「必須精確快照」。

### 3.4 文件成功標準

- 原先盤點的 19 類問題，每類只有一個場景 owner；
- 既有內容只連結，不在 `13` 重寫完整原理；
- 四個缺口都有可操作的決策流程、證據狀態與面試輸出；
- 可執行場景至少完成 S 級驗證，若資源不足則誠實保留較低證據等級；
- 任一實驗結果都能追溯環境、資料量、命令、run ID、預期與實際差異；
- 縮小規模實驗不被表述成生產容量結論。

## 4. 非目標

- 不重寫 `01–11` 的完整 MySQL 機制內容；
- 不新增 19 篇彼此重複的場景文章；
- 不把 `12-interview-cheatsheet` 擴成第二本長教程；
- 不重新實作或重跑 InnoDB Cluster HA 專題；
- 不重寫 `financial-consistency`、`system-design-scenarios`、`system-design` 或 `mysql-es-cdc-handson`；
- 不把本機 Docker 結果當成雲端、裸機、正式硬體或生產流量證據；
- 不為了跑到 1,000 萬行而停止、刪除或重設其他 worktree／Compose project 的容器與資料；
- 不預設「更改 durability、停用約束、刪除索引」一定安全；這些只能作為有前提、有恢復方案的取捨。

## 5. 資訊架構與責任邊界

### 5.1 五層學習結構

```text
00-lab
  共用、可重跑的實驗環境與證據來源

01–11
  canonical mechanism truth
  定義 MySQL 為什麼這樣執行

13-senior-scenarios
  cross-chapter reasoning layer
  定義如何把多章知識組成陌生場景方案

12-interview-cheatsheet
  compression layer
  快速複習，不承載長篇推導

99-interview-cards
  closed-book layer
  蓋住答案後練習提問、口述與追問
```

`13` 的編號晚於 `12`，但學習路徑不是單純按號碼讀。第一次學習依然讀 `01–11`；準備資深面試時先使用 `13` 組裝，再回 `12` 壓縮，最後以 `99` 閉卷練習。

### 5.2 Canonical ownership 規則

每個知識點分成兩種 owner：

- **mechanism owner**：定義 MySQL 機制與事實，通常位於 `01–11`；
- **scenario owner**：定義某類陌生問題的完整分析與輸出流程。

`13/README.md` 只是路由器，不成為第三份正文。每個問題族只指定一個 scenario owner；該 owner 可以連到多個 mechanism owner，但不能複製它們的完整解釋。

### 5.3 19 類問題的去重路由

| # | 問題族 | 唯一 scenario owner | `13` 的處理 |
|---|---|---|---|
| 1 | 從 access pattern 設計表、主鍵、型別、約束與索引 | `mysql-handson/13-senior-scenarios/01-schema-from-access-patterns.md` | 新增缺口 |
| 2 | 高效且安全地匯入 1,000 萬行 | `mysql-handson/13-senior-scenarios/02-bulk-load-10m.md` | 新增缺口 |
| 3 | 線上 schema 變更與資料 backfill | `python-data/07-migrations.md` | 路由；MySQL DDL 機制連到 ch11 |
| 4 | 歷史資料歸檔、大量刪除與空間回收 | `mysql-handson/13-senior-scenarios/03-archive-delete-reclaim.md` | 新增缺口 |
| 5 | 資料分布改變造成執行計畫退化 | `mysql-handson/04-execution-and-explain/scenarios/01-plan-flips-by-selectivity.md` | 路由 |
| 6 | 大型 JOIN、報表與全量匯出如何隔離 OLTP | `mysql-handson/13-senior-scenarios/04-report-export-isolation.md` | 新增缺口；JOIN 機制連到 ch08 |
| 7 | 深分頁到大批量匯出的完整處理 | `mysql-handson/13-senior-scenarios/04-report-export-isolation.md` | 場景組裝；分頁機制連到 ch08 scenario 03 |
| 8 | 高併發扣庫存與防超賣 | `system-design-scenarios/16-秒殺與票務.md` | 路由 |
| 9 | 訂單／支付／庫存的 UNKNOWN、冪等與對帳 | `financial-consistency/03-order-payment-inventory/README.md` | 路由；面試卡作閉卷入口 |
| 10 | 熱點庫存行、鎖競爭與死鎖取捨 | `system-design-scenarios/16-秒殺與票務.md` | 路由；鎖機制連到 ch06 |
| 11 | MySQL CPU 100% 排查 | `mysql-handson/11-ops-and-troubleshooting/README.md` Case A | 路由 |
| 12 | 連接數耗盡與慢查堆積 | `mysql-handson/11-ops-and-troubleshooting/README.md` Case B | 路由 |
| 13 | 寫風暴、checkpoint 與吞吐崩塌 | `mysql-handson/11-ops-and-troubleshooting/scenarios/01-write-storm-checkpoint-throttle.md` | 路由 |
| 14 | replica lag 與 Read Your Writes | `mysql-handson/09-replication-and-ha/README.md` | 路由 |
| 15 | Primary 故障、fencing、Router 與 failover | `mysql-handson/09-replication-and-ha/innodb-cluster/README.md` | 路由到既有實測 scenario |
| 16 | 誤刪後 PITR，以及 HA 為何不能取代備份 | `mysql-handson/09-replication-and-ha/innodb-cluster/scenarios/08-ha-cannot-replace-pitr.md` | 路由 |
| 17 | 是否該分庫分表 | `mysql-handson/10-sharding-and-scaling/README.md` | 路由 |
| 18 | 分片鍵、熱點、擴容與 reshard | `mysql-handson/10-sharding-and-scaling/README.md` | 路由 |
| 19 | 線上分片遷移、雙寫與 CDC 校驗 | `mysql-handson/10-sharding-and-scaling/README.md` Case C | 路由；CDC 故障閉環連到 `mysql-es-cdc-handson` |

這張表管理的是「哪裡回答完整場景」。被連結的 mechanism owner 仍保有自己的原理責任，因此不構成重複 owner。

## 6. 文件變更範圍

### 6.1 新增文件

```text
mysql-handson/13-senior-scenarios/
├── README.md
├── 01-schema-from-access-patterns.md
├── 02-bulk-load-10m.md
├── 03-archive-delete-reclaim.md
└── 04-report-export-isolation.md
```

責任如下：

- `README.md`：解題器、使用方式、19 類問題路由、證據標籤與練習順序；
- `01`：從需求與不變式推導 MySQL physical schema；
- `02`：安全、高吞吐、可續跑的 1,000 萬行匯入；
- `03`：retention、archive、delete、purge 與 reclaim 的完整生命週期；
- `04`：把大型報表／匯出工作從 OLTP 的延遲與資源預算中隔離。

### 6.2 更新既有文件

- `mysql-handson/README.md`
  - 加入 `13-senior-scenarios` 章節地圖；
  - 增加「資深面試」閱讀路徑：`01–11 → 13 → 12 → 99`；
  - 保留既有首次上手與 lab 指令。
- `mysql-handson/10-sharding-and-scaling/README.md`
  - 移除四個不存在的「待補 scenario」連結；
  - Hash 熱點改鏈回同章 Case A；
  - Snowflake 時鐘回撥改鏈到 `distribution/分布式id.md`；
  - 深分頁改鏈到 ch08 scenario 03；
  - 線上遷移改鏈到同章 Case C，CDC 深入證據再鏈到 `mysql-es-cdc-handson`。
- `mysql-handson/12-interview-cheatsheet/README.md`
  - 只加短入口，說明長場景推導由 ch13 負責；
  - 不複製四篇新文章的答案。
- `mysql-handson/00-lab/Makefile` 與 `init/`
  - 預設不修改；
  - 只有在「copyable SQL + 既有 make target」不能穩定重現時，才加入 namespaced 的最小 target／fixture；
  - 不新增 HA 服務、不改 `00-lab/ha/`、不重設其他 Compose project。

### 6.3 明確不改的區域

- `mysql-handson/00-lab/ha/`；
- `mysql-handson/09-replication-and-ha/` 的 HA 事實與既有證據；
- `financial-consistency/`；
- `system-design-scenarios/`；
- `system-design/`；
- `mysql-es-cdc-handson/`；
- 工作樹中與本任務無關的既有修改。

這些區域可以被連結，但不在本批次重寫。

## 7. 共用場景文件契約

四篇新文件都使用相同骨架，讓學習者把注意力放在推理，而不是猜文章結構。

### 7.1 固定章節

1. **陌生題目**：只給 prompt，不先洩漏答案；
2. **先停下來回答**：要求學習者先口述，再往下讀；
3. **澄清問題**：列出會改變方案的必要約束；
4. **業務不變式與完成標準**：先定義什麼不能錯、何時算完成；
5. **跨章執行鏈**：從 client／SQL 到 Server、InnoDB、日誌、複製與外部輸出；
6. **成本與瓶頸模型**：資料量、網路、CPU、記憶體、I/O、索引寫放大、鎖與 backlog；
7. **推薦基準方案**：在明示假設下給一個可落地起點；
8. **替代方案與取捨**：說明條件改變時為何換方案；
9. **執行計畫與停止條件**：批次、節流、監控、失敗邊界與何時中止；
10. **縮小規模實驗與證據**：命令、環境、資料量、實測結果與差異；
11. **生產邊界、恢復與回滾**：本機不能證明什麼，出錯後如何收斂；
12. **面試輸出**：30 秒答案、3–5 分鐘答案、追問樹與 red flags。

### 7.2 澄清問題的最低集合

每個場景至少確認：

- 是空表／新表，還是承載線上流量的既有表；
- 資料量、單行大小、索引數量與成長率；
- 允許停機多久，允許多舊，允許重跑嗎；
- 是否有唯一鍵、外鍵、trigger、generated column 或 side effect；
- 是否有 binlog、replica、HA、備份與 PITR；
- 正確性怎麼驗證，失敗後從哪裡續跑；
- latency、throughput、replication lag、磁碟與恢復時間的預算。

問題必須能改變決策；不增加不影響方案的制式問句。

### 7.3 解題器與輸出對應

| 解題步驟 | 文件回答 | 面試官能聽到的訊號 |
|---|---|---|
| 約束 | 澄清問題、假設、SLO | 不急著背參數 |
| 執行鏈 | 跨章資料與控制流 | 知道成本在哪一層產生 |
| 成本／瓶頸 | 數量級、資源與放大因子 | 能做容量推理 |
| 正確性／風險 | 不變式、未知結果、資料校驗 | 不以快換錯而不自知 |
| 基準方案 | 最小可行流程 | 能做決策 |
| 替代／取捨 | 條件分支 | 沒把一招當萬能答案 |
| 驗證 | 指標、實驗與驗收 | 結論有證據 |
| 恢復／回滾 | checkpoint、retry、restore、abort | 能承擔生產後果 |

## 8. 四個新增場景

### 8.1 `01-schema-from-access-patterns.md`

#### 核心問題

給定一組讀寫 access patterns、不變式、資料規模與 retention，如何推導 MySQL physical schema，而不是從「要建哪些表」憑直覺開始。

#### 固定案例

使用一個多租戶、寫入持續成長的業務記錄表。需求至少包含：

- 以全域 ID 精確查一筆；
- 以 `tenant_id + status + created_at` 做穩定分頁；
- 以外部請求號保證租戶內唯一；
- 金額、時間、狀態等欄位有明確不變式；
- 保留期到期後可歸檔；
- 讀多個欄位，但避免為每個查詢建立寬 covering index。

案例只用來承載 MySQL physical design；訂單／支付的跨服務一致性仍由 `financial-consistency` 擁有。

#### 必須推導的決策

- natural key、surrogate key 與業務唯一鍵的責任；
- `BIGINT`、`DECIMAL`、字串、時間與狀態型別的取捨；
- `NOT NULL`、`UNIQUE`、`CHECK` 與外鍵是否能守住不變式；
- 主鍵寬度如何放大所有 secondary index；
- composite index 的欄位順序如何對應定位、過濾、排序與分頁；
- 多一個索引如何增加插入、更新、redo、binlog、buffer pool 與磁碟成本；
- 何時正規化、何時保留快照欄位、何時拆冷欄位。

#### 證據

以窄索引基線和過度索引版本做 S 級對照，至少比較代表性 `EXPLAIN ANALYZE`、索引大小與相同資料量的寫入成本。結論只能說明該 schema、資料分布與本機環境下的差異。

### 8.2 `02-bulk-load-10m.md`

#### 核心問題

如何把 1,000 萬行資料高效、安全且可恢復地匯入 MySQL，並能解釋為什麼快、可能在哪裡失敗，以及線上表與空表為何不能使用同一套做法。

#### 基準決策樹

先區分：

- 檔案是否已在 server 可安全讀取；
- 目標是空 staging table、空正式表，還是承載線上讀寫的既有表；
- 是否需要逐行轉換、去重、錯誤隔離與重跑；
- 是否允許重建 secondary indexes；
- binlog／replica 是否必須跟隨，能容忍多少 lag；
- 來源是否可重新生成，是否已有不可變 input manifest。

推薦基線是「不可變輸入 + staging + 驗證 + 受控 publish／merge」：

1. 先保存 input manifest、行數、大小與 checksum；
2. 以 staging table 隔離未驗證資料；
3. 能直接載入檔案時優先評估 `LOAD DATA`；需要轉換或 checkpoint 時採 prepared multi-row batch；
4. 對 batch 大小與並行度逐級壓測，不直接把 thread 數拉滿；
5. 驗證 row count、主鍵／唯一鍵、rejects、checksum 與抽樣不變式；
6. publish／merge 前設停止條件與回滾點；
7. 保留 run ID、batch watermark 與可安全重跑策略。

#### 必須解釋的執行鏈

```text
來源讀取／解析
  → client-server 傳輸或 server-side file read
  → SQL parse／row conversion
  → constraint 與 duplicate check
  → clustered／secondary B+ tree 維護
  → undo／redo／binlog
  → buffer pool dirty pages／checkpoint／fsync
  → replica receive／persist／apply
```

#### 實驗

在相同 schema、相同資料與相同 durability 基線下，至少比較：

- single-row autocommit，僅作慢速對照；
- prepared multi-row batch；
- `LOAD DATA`。

每種方法使用乾淨目標表重複執行，記錄 elapsed time、rows/s、資料與索引大小、redo／binlog／I/O 差值、錯誤數與正確性結果。S 與 M 用於看趨勢；只有 L 的 10,000,000 行真的完成，才能把「1,000 萬行已重現」標為 `REPRODUCED`。

不把全域降低 durability、盲目停用 constraint、在熱表任意刪索引列為預設操作。這些只能在資料可重建、故障邊界與恢復方案明確時作為替代方案討論。

### 8.3 `03-archive-delete-reclaim.md`

#### 核心問題

如何讓過期資料先被正確歸檔，再從 OLTP 安全移除，最後在真的需要時把 tablespace 空間交還檔案系統。

#### 必須先拆開的四件事

- **retention**：哪些資料何時才允許離開熱庫；
- **archive**：冷資料放哪裡，如何證明完整、可讀、可追溯；
- **delete／purge**：邏輯刪除、undo、purge、redo／binlog 與 replica apply 的成本；
- **reclaim**：頁面可被 InnoDB 重用，不等於 `.ibd` 已縮小或空間已還給 OS。

#### 基準方案

- 若查詢與 retention 天然按時間切分，優先評估預先設計的 partition lifecycle；
- 既有非分區表採「固定主鍵／時間水位 + 小批次 archive-copy + 校驗 + 小批次 delete + throttle」；
- 以 history list、redo／checkpoint、鎖等待、replication lag、磁碟與 P99 作節流訊號；
- 空間回收是另一個有額外磁碟、MDL、時間與回滾風險的維護動作，不跟 delete 自動綁定；
- `OPTIMIZE TABLE`／重建只在收益、額外空間與維護窗口都成立時執行。

#### 正確性與恢復

- archive 有 manifest、range、row count、checksum 與 schema version；
- 同一批次可重跑，不會重複歸檔或越過 hold records；
- delete 只處理已驗證批次；
- 每批有 watermark，失敗從最後完成批次續跑；
- partition drop 或 tablespace rebuild 前，必須明確指出可恢復來源與 RTO；
- 沒有可驗證 archive／backup 時，不能把不可逆刪除寫成推薦步驟。

#### 實驗

以相同資料比較單一大交易 delete、小批次 delete，以及時間分區 drop 的影響；分開量測「資料已不可見」、「purge 已追上」與「檔案空間已回收」。記錄 binlog／redo、history list、執行時間、檔案大小與重跑結果。

### 8.4 `04-report-export-isolation.md`

#### 核心問題

大型 JOIN、報表或全量匯出不是只靠加索引就能解決。場景要回答如何定義一致性、限制資源、避免拖垮 OLTP、支援 backpressure／續跑，並交付一份可驗證的輸出。

#### 先確認的一致性語義

- 必須是跨整份輸出的精確 snapshot，還是允許固定 high watermark；
- 報表可以多舊，replica lag 是否可接受；
- 匯出期間資料會不會更新或刪除；
- 是否需要跨表一致版本；
- 失敗後要從頭重跑，還是可以從 cursor 續跑；
- 輸出是否直接回 HTTP，還是由 async job 產生版本化 artifact。

#### 推薦基線

- 將大型匯出建模成 async job，而不是長時間佔住同步 request；
- 先以 immutable job parameters、schema version 與 high watermark 固定成員邊界；high watermark 只能排除後續新增，不能凍結既有 row 的更新／刪除；
- 用 keyset／cursor 分塊，不用深 offset；
- 使用 streaming fetch 與 bounded buffer，把 consumer backpressure 傳回 producer；
- 每批保存 cursor、row count、checksum 與輸出位置，artifact 完成後再原子 publish；
- 以 workload 大小與一致性要求選擇 Primary、read replica、專用 reporting replica 或 analytical store；
- 若 mutable rows 也要 as-of 一致，必須選擇 versioned history、資料庫／replica snapshot、CDC 建出的版本化讀模型，或有界 MVCC snapshot；
- 若真的要求跨長時間、跨多表的精確 snapshot，必須明說長交易、undo／purge、replica 資源與失敗重跑成本，不能把 `START TRANSACTION WITH CONSISTENT SNAPSHOT` 當免費方案。

#### 與既有內容的邊界

- JOIN algorithm、驅動行、filesort、temporary table：ch08 擁有；
- 深 offset、deferred join、keyset pagination：ch08 scenario 03 擁有；
- replica lag 與 Read Your Writes：ch09 擁有；
- ch13/04 只組裝「隔離、快照、串流、backpressure、續跑與 artifact 發布」。

#### 實驗

在背景 OLTP workload 下比較同步大查詢／單次全量讀，與 cursor 分塊、節流匯出。至少記錄 OLTP latency、export throughput、連接持有時間、temporary table／sort、replica lag（若使用）、完成 row count、checksum、restart 與重複執行結果。

## 9. 實驗級別與證據契約

### 9.1 固定資料級別

| 級別 | 預設資料量 | 用途 |
|---|---:|---|
| S | 100,000 rows | 快速驗證機制、命令與正確性 |
| M | 1,000,000 rows | 驗證趨勢、批次與資源曲線 |
| L | 10,000,000 rows | 驗證目標規模；必須顯式 opt-in |

資料量可因案例語義而補充欄位大小或關聯表倍數，但不能默默改變同一比較中的 schema、durability、cache 狀態或資料分布。

### 9.2 證據標籤

| 標籤 | 精確含義 |
|---|---|
| `REPRODUCED` | 文件宣稱的目標條件已實際執行，且正確性與完成條件通過 |
| `SCALED_REPRODUCED` | 只在縮小資料量或簡化故障域實跑；不能外推為目標規模已完成 |
| `READY_UNRUN` | 命令、預期、驗收與停止條件已準備，但尚未執行 |
| `REASONED` | 由機制或架構推導，沒有宣稱本機實測 |
| `REUSED` | 結論直接引用 repository 內既有、可追溯的實驗證據 |

證據狀態不能靠文字語氣暗示，必須在每篇文件的 evidence summary 明列。

### 9.3 每次 run 的最低記錄

- scenario、run ID、開始／結束時間與結果；
- MySQL image／server version、重要 session／global variables；
- CPU、記憶體、磁碟、Docker 資源與當時運行中的相關容器；
- schema version、資料量、平均／代表性 row size、資料分布；
- 完整命令、batch size、parallelism、commit cadence；
- cold／hot cache 狀態，以及至少三次可比較 run 的分布；
- pre／post 指標與相同時間窗；
- row count、checksum、duplicate、missing、reject 與 invariant 結果；
- 預期、實際、落差與下一個假設；
- cleanup、restart point、rollback／recovery 結果。

單次最好成績不能代表結果；報告 median 與範圍，並保留失敗嘗試。

### 9.4 預期與實際分離

所有 runnable scenario 延續 repository 既有紀律：

```text
commit A：問題、假設、預期、步驟、驗收與停止條件
commit B：實際執行、原始摘要、預期落差、修正與證據狀態
```

不得先跑完，再回填一個看似命中的「預期」。

## 10. 本機資源與隔離策略

### 10.1 預設行為

- 所有新實驗預設只跑 S；
- M、L 必須由明確參數 opt-in；
- 先使用現有一般 MySQL lab，不啟動 HA lab；
- 使用專屬 schema、table prefix、輸入與 evidence path；
- 不停止、刪除、重建未知容器、volume、network 或其他 worktree 的資料；
- cleanup 只作用於本 scenario 建立且已解析成明確名稱的資源。

### 10.2 Preflight

每次執行前至少檢查：

- Docker daemon 與 MySQL 健康狀態；
- CPU、可用記憶體、Docker memory limit；
- filesystem 可用空間；
- 既有容器、Compose projects 與 port 衝突；
- 目標 schema／table 是否已存在；
- binlog、replica 與觀測服務是否在本次範圍內；
- 上次未完成 run 是否有 watermark／artifact 需要保留。

S 執行前先依 source file、schema、索引與 transaction log 做保守靜態估算；S 完成後，再以實測 bytes-per-row、data/index、redo/binlog 與 transient space 校準 M／L peak。S／M 開始前至少保留估算峰值以外 5 GiB；L 至少保留估算峰值以外 10 GiB。未通過就降級或保持 `READY_UNRUN`，不能繞過 gate。

### 10.3 停止條件

每篇在執行前寫出具體閾值。最低共同條件是：

- 可用磁碟即將低於本次 preflight 的 reserve；
- mysqld／container restart、error log 出現資料完整性或 I/O 錯誤；
- correctness check 失敗；
- replication lag、OLTP latency、lock wait 或 checkpoint pressure 超過該 run 預先設定的安全預算；
- 無法證明 cleanup 只會影響專屬資源。

觸發後停止新的 batch，保存當前 run、watermark 與診斷資訊，再做有界 cleanup。不能為了拿到漂亮數字刪除失敗證據。

## 11. 錯誤處理、續跑與回滾

### 11.1 結果分類

每個 batch／job 的結果至少分為：

- `SUCCEEDED`：完成且通過不變式；
- `FAILED`：已確認沒有完成，可依既定規則修正或重跑；
- `UNKNOWN`：client 失聯或 timeout，資料庫可能已提交，必須先按 run ID／batch ID 查證；
- `ABORTED`：因停止條件主動中止，保留 restart point。

`UNKNOWN` 不能直接當失敗重跑；匯入、歸檔與匯出都要有穩定 batch identity 或 watermark。

### 11.2 Correctness gate

性能數字只有在以下條件通過後才有效：

- 來源與目標 row count 能解釋；
- checksum／aggregate 與抽樣比對通過；
- duplicate、missing、reject 都有數量與處置；
- 重跑不會產生額外 side effect；
- rollback／restart 後的狀態能被辨識；
- publish 前後的讀者可見性邊界清楚。

### 11.3 生產外推邊界

本機 Compose 可以驗證機制、相對趨勢、命令與 correctness workflow；不能直接證明：

- 生產硬體的 IOPS、fsync latency 或網路吞吐；
- 多 AZ／多主機故障域；
- 正式資料分布、row width、cache hit ratio 或併發；
- 生產 RPO、RTO、最大安全 parallelism 或 1,000 萬行 SLA。

文件必須把 observed fact、scaled observation、architecture reasoning 與 production requirement 分開。

## 12. 驗證與驗收

### 12.1 靜態文件驗證

- 所有 Markdown 相對連結與 anchor 可解析；
- code fence 成對；
- `git diff --check` 通過；
- 沒有 `TODO`、`TBD`、假 success、空白證據段；
- 19 類問題的路由矩陣恰好各有一個 scenario owner；
- ch10 不再連到四個不存在的 scenario；
- root、ch12、ch13、99 的閱讀順序互相一致；
- 新文章沒有複製 canonical mechanism owner 的長篇正文。

### 12.2 實驗驗收

- runnable case 至少完成 S，或明列阻止執行的 preflight 證據並保持 `READY_UNRUN`；
- M／L 只在資源 gate 通過後執行；
- 每個 performance 比較使用相同 schema、資料與設定，至少三次 run；
- cold／hot cache、warm-up 與背景 workload 被明列；
- 所有性能表先通過 correctness gate；
- row count、checksum、duplicate、missing、retry、restart、recovery 都有結果；
- 縮小實驗不宣稱生產容量；
- 預期 commit 早於實際結果 commit。

### 12.3 學習成果驗收

對四篇新場景，讀者不看正文時仍能：

- 先問出會改變設計的關鍵限制；
- 畫出跨章執行鏈；
- 指出主要成本與 correctness failure mode；
- 給出一個有假設的基準方案，而不是參數清單；
- 解釋至少兩個替代方案何時更好；
- 提出可觀測的驗證、停止、恢復與回滾方式；
- 完成 30 秒與 3–5 分鐘回答。

## 13. 交付與 commit 順序

為避免目前工作樹中的既有修改、HA 內容與新場景互相污染，交付順序固定為：

1. 只提交本設計規格；
2. 將目前 7 份既有 MySQL 教程修正獨立提交，不混入新場景；
3. 新增 ch13 路由骨架、root 導航、ch12 pointer，並清理 ch10 四個重複 placeholder；
4. 完成 schema-from-access-patterns 場景及其 S 級索引／寫入對照；
5. 對其餘三個 workflow scenario（bulk load、archive/delete/reclaim、report/export），逐篇先提交預期，再執行並提交實際結果；
6. 做全 repository owner、連結、證據狀態與輸出格式稽核。

每次 stage 前都列出精確檔名；不得使用會帶入無關 dirty files 的全量 staging。HA、CDC、financial consistency 與 system design 文件只作連結目標，不進入這批 commit。

## 14. 最終完成定義

本設計完成後，repository 應呈現以下結果：

- 原理仍只有一個 canonical owner；
- 19 類資深問題都有明確去向，不再以「全部新增」解決焦慮；
- 四個真缺口有完整的跨章推理、執行與證據契約；
- 「1,000 萬行匯入」只是解題方法的一個示範，不是整個教程唯一黃金題；
- 學習者能把同一解題器遷移到未見過的 MySQL 場景；
- 文件誠實區分已實跑、縮小實跑、已準備未跑、架構推理與重用證據；
- 本機資源不足時會安全降級，而不是冒險干擾其他 worktree；
- 最終輸出符合資深工程師／架構師面試所需的決策、取捨、證據與恢復能力。
