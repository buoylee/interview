# MySQL InnoDB Cluster 高可用學習專題設計

**日期**：2026-07-22
**目標位置**：`mysql-handson/09-replication-and-ha/`、`mysql-handson/00-lab/ha/`
**主方案**：MySQL 8.4 LTS InnoDB Cluster（3 成員、Single-Primary、MySQL Router）

## 1. 背景

現有 `mysql-handson/09-replication-and-ha/README.md` 已經覆蓋：

- binlog dump／receiver／applier；
- GTID 與位點複製；
- 異步、半同步與 Group Replication；
- `ACK != apply != 副本已可讀`；
- 主從延遲、讀己之寫、手動切主與 MGR 基礎；
- 3 個傳統複製 scenario：延遲、斷線後 GTID 續傳、errant transaction。

目前缺少的不是另一份產品清單，而是：

1. 產品無關、端到端的 HA 理論模型；
2. 一套當代完整 HA 方案的深度學習；
3. 能證明業務結果、選主、fencing、路由與恢復的可重跑實驗；
4. 可帶到真實公司的部署檢查與故障 Runbook。

## 2. 核心決策

### 2.1 學習策略

採用「先完整學一套，再由機制缺口決定第二套」：

```text
已有複製基礎
binlog / GTID / ACK / apply
        ↓
產品無關的 HA 理論
故障模型 / quorum / fencing / RPO / RTO
        ↓
一個主方案
把通用理論映射到具體元件與事務流程
        ↓
端到端實驗
持續寫入 → 故障 → 選主 → 重連 → 恢復 → 驗證
        ↓
生產化能力
監控 / 備份 / 升級 / 演練 / runbook
        ↓
第二方案門檻
只補主方案無法覆蓋的重要機制
```

不從 MHA、舊 Orchestrator 或手工位點切主的完整部署開始。舊方案只保留必要機制與失敗反例。

### 2.2 主方案

主方案固定為：

- MySQL Server 8.4 LTS；
- 3 個 InnoDB Cluster 成員；
- Single-Primary；
- MySQL Shell／AdminAPI；
- MySQL Router；
- 低延遲、同一地域內的獨立故障域；
- 本地以 Docker Compose 模擬，生產心智模型為三台獨立 Linux VM／主機。

選擇 InnoDB Cluster 的原因不是單純「官方」，而是它能在同一方案內覆蓋 Group Replication、成員管理、quorum、選主、fencing、flow control、節點恢復、Router 與應用重連。

### 2.3 第二方案

Percona XtraDB Cluster（PXC）只保留為門檻式候選，不預先承諾實作。主方案完成後，只有在 Galera virtually synchronous、multi-primary certification conflict、SST／IST 等差異具有足夠學習價值時，才進入下一輪獨立設計。

## 3. 目標

完成專題後，學習者能獨立完成一個自建 MySQL HA 系統的：

- 需求與故障模型分析；
- 方案選擇與限制說明；
- 三節點部署與 Router 整合；
- 計劃內切換與非計劃故障處置；
- RPO／RTO 測量；
- 已確認、明確失敗、結果未知三類請求的判定；
- split-brain 防護與 fencing 驗證；
- 節點恢復、重新加入與日常 Runbook；
- HA、備份、PITR、DR、讀擴展之間的邊界說明。

## 4. 非目標

- 不完整部署 MHA、舊 Orchestrator 或其他歷史控制面。
- 不從 binlog file／position 手工搭建舊式自動切主系統。
- 不在主線使用 multi-primary。
- 不在主線加入讀寫分離；先把 HA 與 read scaling 分開。
- 不把 Kubernetes Operator 當成新的複製／一致性方案。
- 不實作跨地域 InnoDB ClusterSet。
- 不引入 Vitess 分片或 NDB 儲存引擎。
- 不宣稱單機 Compose 具備真實主機、磁碟、交換機或可用區級 HA。
- 不為展示產品數量而增加第二套集群。

## 5. 產品無關的 HA 理論

理論以一個問題為主線：

> 當客戶端看到「成功」時，系統究竟承諾了什麼？

### 5.1 請求結果模型

每個寫請求必須被分類為：

- **明確成功**：客戶端已收到成功，必須能說明它跨過了哪個持久性邊界；
- **明確失敗**：確認事務未提交，可以安全重新執行；
- **結果未知**：資料庫可能已提交，但回應在連線中斷時遺失，必須用 `request_id` 查明並保持重試冪等。

### 5.2 端到端分層

```text
應用層       重連、重試、冪等、結果未知
路由面       找到當前 Primary，移除故障節點
控制面       故障檢測、成員資格、選主、fencing
資料面       執行、排序／認證、持久化、複製、apply
儲存層       redo、binlog、fsync、crash recovery
```

任何可用性結論都要指出它位於哪一層，不能用「集群自動處理」模糊帶過。

### 5.3 故障模型

主線深入以下故障：

- MySQL 程序崩潰；
- 整台主機失效；
- Primary 與多數派網路分區；
- 節點仍在線但非常慢；
- 儲存故障或資料損壞；
- Router／應用連線入口失效；
- 整個故障域失效。

每種故障都要回答：誰仍可寫、誰必須被隔離、哪些請求結果會變成未知、如何恢復正常拓撲。

本地 lab 只模擬成員資料卷遺失等可控情況，不宣稱能重現真實磁碟控制器、檔案系統或媒體損壞；物理儲存故障保留在理論、備份恢復與生產 Runbook 中。

### 5.4 Quorum、選主與 fencing

理論需要說清楚：

- 三節點如何容忍一個成員故障；
- 為什麼兩節點無法同時安全滿足自動切換與防腦裂；
- 多數派確認、全節點 apply、日誌落盤不是同一件事；
- 選出新 Primary 後，舊 Primary 仍必須失去寫入資格；
- 恢復的舊節點必須先追平與驗證，不能直接重新提供寫服務。

只講足以預測實際行為的 quorum／consensus，不做形式化 Paxos 證明。

### 5.5 一致性與持久性邊界

明確區分：

1. Primary 執行事務；
2. 產生並傳播 write set；
3. 成員完成排序／認證；
4. Primary 本地提交；
5. 客戶端收到成功；
6. Secondary apply；
7. Secondary 對讀請求可見。

不能用「三台同步完成」描述整條鏈路。

### 5.6 HA、DR 與恢復

- HA：允許的局部故障下繼續服務；
- Backup／PITR：處理誤刪、邏輯損壞與歷史恢復；
- DR：處理整個地域或資料中心失效；
- Read scaling：分散讀流量，不等於提高資料安全性。

### 5.7 可度量結果

理論最終落到：

- RPO；
- RTO；
- 故障檢測、選主、路由刷新、應用重連的分段時間；
- 明確成功、明確失敗、結果未知的請求數；
- 是否存在雙 Primary 或分叉交易。

## 6. InnoDB Cluster 教學模型

### 6.1 元件責任

| 元件 | 責任 | 不負責 |
|---|---|---|
| MySQL Server／InnoDB | 執行事務、本地 redo／binlog、資料持久化 | 不替應用處理重試 |
| Group Replication | 成員管理、交易排序／認證、選主、quorum | 不搬遷現有客戶端連線 |
| MySQL Shell／AdminAPI | 建立、配置、檢查、修復 Cluster | 不在正常 SQL 資料路徑上 |
| MySQL Router | 根據 Cluster Metadata 路由新連線 | 不複製資料、不決定 Primary |
| 應用程式 | 連線重建、超時、冪等、未知結果確認 | 不能假設切主完全無感 |

### 6.2 正常提交時序

```text
Client
  → Router
  → Primary 執行事務
  → 產生 write set
  → Group Replication 排序與認證
  → Primary 本地提交
  → Client 收到成功
  → Secondary 繼續 apply
```

課程必須強調：

- 多數派完成組內決策不代表所有 Secondary 已 apply；
- Secondary apply 可能落後；
- quorum、日誌落盤、Primary commit、Secondary 可讀是不同邊界；
- durability 仍取決於明確配置與具體故障模型。

### 6.3 Failover 時序

```text
舊 Primary 無法聯絡
  → Group 更新成員視圖
  → 多數派排除故障成員
  → 選出新 Primary
  → 新 Primary 處理必要 backlog
  → 開放寫入
  → Router 更新拓撲
  → 舊連線斷開
  → 應用重新連線
  → 新連線到達新 Primary
```

MySQL 8.4 基線保留 `group_replication_consistency=BEFORE_ON_PRIMARY_FAILOVER`，讓新 Primary 在 failover 後先處理 backlog，避免應用看到資料倒退。既有應用連線仍會中斷，必須重新連到 Router。

### 6.4 固定基線

- 3 成員、Single-Primary；
- 僅使用 InnoDB；
- GTID 與 row-based binlog；
- 明確配置 `innodb_flush_log_at_trx_commit=1` 與 `sync_binlog=1`；
- 保留 `BEFORE_ON_PRIMARY_FAILOVER`；
- 寫流量走 Router 的 Primary 讀寫入口；
- Router 跟隨應用部署，本地 lab 用兩個 Router 模擬入口冗餘；
- 不啟用 multi-primary 或自動讀寫分離。

### 6.5 必須深入的機制

- Group Replication 成員狀態與 view change；
- XCom／quorum 在交易與成員決策中的位置；
- write-set extraction、全序與 certification conflict；
- Primary election 與 `memberWeight`；
- `expelTimeout` 與網路抖動取捨；
- `exitStateAction`、`super_read_only` 與 fencing；
- flow control、applier backlog 與慢節點；
- Clone／增量恢復、auto-rejoin 與人工 rejoin；
- Cluster Metadata 與 Router metadata cache。

## 7. HA Lab 架構

現有 `00-lab/docker-compose.yml` 的 MySQL 8.0.36 Primary／Replica 繼續服務其他章節。新的 HA lab 使用獨立 Compose project、容器、網路與 volumes。

```text
                         ┌──────────────┐
                         │ Evidence     │
                         │ Verifier     │
                         └──────▲───────┘
                                │
Workload Runner ──→ Router A ───┼──→ DB-1
        │          Router B ────┼──→ DB-2
        │                       └──→ DB-3
        │
        └── client outcome ledger

Fault Controller
  ├── kill / pause DB
  ├── network partition / latency
  └── stop Router
```

### 7.1 元件

- **DB-1／DB-2／DB-3**：角色動態變化，不使用固定 `primary` 命名；
- **Router A／Router B**：驗證資料庫與入口兩層可用性；
- **Workload Runner**：啟動兩個 worker，分別固定連接 Router A 與 Router B，持續送出具備 `request_id` 的業務寫入並共用結果 ledger；
- **Fault Controller**：注入崩潰、分區、延遲、pause 與 Router 故障；
- **Evidence Verifier**：比較客戶端 ledger、Cluster 狀態與資料庫最終結果。

### 7.2 業務操作與證據

使用一個最小業務操作：

```text
create_order(request_id, payload)
```

資料表以 `request_id` 建立唯一約束。Workload Runner 記錄：

- `request_id`；
- 發送與完成時間；
- 明確成功、明確失敗或結果未知；
- 經過哪個 Router；
- 重試次數；
- 錯誤類型。

結果分類規則固定為：

- 收到資料庫成功回應才記為明確成功；
- 在尚未送出 SQL 前即連線失敗才記為明確失敗；
- SQL 已送出但未收到確定回應，一律記為結果未知，不能直接自動重放為新的業務操作。

Verifier 必須檢查：

- 所有明確成功的 `request_id` 都存在；
- 同一請求沒有產生兩筆業務結果；
- 結果未知的請求最後可被查明；
- 新 Primary 與恢復成員最終一致。

原始輸出保存在被忽略的本地 evidence 目錄；scenario 只提交足以證明結論的關鍵片段。

## 8. 核心 Scenario

1. **計劃內切換**：驗證維護切換、連線中斷與 RTO。
2. **Primary 程序突然崩潰**：驗證故障檢測、選主、Router 更新與重連。
3. **Primary 與多數派網路分區**：驗證少數派被 fencing、多數派繼續服務。
4. **失去 quorum**：驗證系統停止寫入，不允許兩邊獨立提交。
5. **Secondary 極慢**：觀察 backlog、flow control 與寫入延遲。
6. **Router 故障**：驗證另一入口與應用重連接手。
7. **故障成員重新加入**：驗證追平、恢復讀服務與重新開放資格。
8. **全 Cluster 關閉後恢復**：驗證安全 reboot、Primary 唯一性與恢復後資料結果。
9. **HA 不能替代 PITR**：錯誤 `DELETE` 被複製到全部成員後，必須走資料恢復。

每個 scenario 沿用：

```text
我預期什麼
→ 注入故障
→ 實際觀察
→ 客戶端證據
→ 集群證據
→ 資料一致性驗證
→ 預期與實際落差
```

「容器重新啟動」或「Cluster 顯示 ONLINE」不能單獨作為成功證據。

## 9. 文件與目錄結構

```text
mysql-handson/
├── 00-lab/
│   ├── docker-compose.yml
│   ├── Makefile
│   └── ha/
│       ├── compose.yml
│       ├── Makefile
│       ├── config/
│       ├── bootstrap/
│       ├── init/
│       ├── workload/
│       ├── faults/
│       └── verifier/
│
├── 09-replication-and-ha/
│   ├── README.md
│   ├── ha-foundations.md
│   ├── scenarios/
│   └── innodb-cluster/
│       ├── README.md
│       ├── production-runbook.md
│       └── scenarios/
│           ├── 01-planned-switchover.md
│           ├── 02-primary-crash.md
│           ├── 03-primary-partition.md
│           ├── 04-quorum-loss.md
│           ├── 05-slow-member.md
│           ├── 06-router-failure.md
│           ├── 07-member-rejoin.md
│           ├── 08-cluster-reboot.md
│           └── 09-ha-cannot-replace-pitr.md
│
└── 99-interview-cards/
    ├── q-ha-vs-replication.md
    ├── q-quorum-and-fencing.md
    ├── q-transaction-outcome-unknown.md
    └── q-innodb-cluster-failover.md
```

### 9.1 組織原則

- `09-replication-and-ha/README.md` 保留現有複製主線，只增加導航與邊界。
- `ha-foundations.md` 只放產品無關理論。
- `innodb-cluster/README.md` 把通用理論映射到 MySQL 8.4。
- `production-runbook.md` 放部署檢查、監控、演練與處置。
- 現有 3 個傳統複製 scenario 保持原路徑與語義。
- HA lab 由 `00-lab/Makefile` 提供 `ha-*` 統一入口，內部轉發到 `00-lab/ha/Makefile`。
- 面試卡只壓縮結論並鏈回理論與 scenario，不複製正文。

## 10. 生產 Runbook

### 10.1 部署前檢查

- 三個獨立故障域與低延遲網路；
- MySQL 版本、server UUID、主機名稱與連線位址；
- InnoDB、GTID、binlog、redo／binlog durability；
- 時鐘同步、TLS、管理帳號與最小權限；
- Router 與應用的部署位置；
- 備份、PITR 與容量基線。

### 10.2 建立與驗收

- 檢查並配置三個 instance；
- 建立 Single-Primary Cluster；
- 加入成員並確認狀態；
- Bootstrap Router；
- 驗證只有一個寫入成員；
- 建立初始備份並記錄恢復點。

### 10.3 日常觀測

- Cluster／成員狀態與 Primary 身份；
- view change；
- certification conflict；
- applier queue 與 flow control；
- 交易延遲、錯誤率與連線重建；
- Router metadata 與後端可達性；
- 備份成功率與可恢復性。

### 10.4 計劃內操作

- controlled switchover；
- 滾動維護與重新加入；
- 版本升級前檢查；
- Router 更新；
- 定期 failover drill。

### 10.5 故障處置

- Primary 故障但仍有 quorum；
- 成員反覆離群或網路抖動；
- 失去 quorum；
- 慢成員拖累集群；
- Router 全部不可用；
- 成員無法自動 rejoin；
- 全 Cluster 關閉後的安全 reboot；
- 誤刪／邏輯損壞後的 PITR。

每個處置條目使用：

```text
現象
→ 先判斷什麼
→ 哪些操作安全
→ 哪些操作可能造成 split-brain／資料分叉
→ 執行命令
→ 成功證據
→ 回復正常拓撲
```

## 11. 完成標準

主方案只有同時滿足以下條件才算完成：

- 從乾淨環境可重複建立三節點 Cluster；
- 所有 scenario 都能獨立 reset、執行與驗證；
- Primary crash 後能測出完整 RTO 分段；
- 所有明確成功請求都能在恢復後找到；
- 結果未知請求能被查明並安全重試；
- 網路分區時少數派不能寫；
- 失去 quorum 時系統停止寫入；
- Router 故障不會造成永久入口中斷；
- 故障成員能安全追平並重新加入；
- 全 Cluster 關閉後能按 Runbook 安全恢復，且只有一個可寫 Primary；
- 誤刪場景證明 HA 不能替代 PITR；
- Runbook 不依賴未記錄的人工步驟；
- 學習者能不看答案解釋提交與 failover 時序；
- 本地文檔明確列出生產環境仍需驗證的物理故障域與儲存邊界。

## 12. 第二方案門檻

主方案完成後才評估：

1. 是否仍有影響實際選型的重要機制未覆蓋；
2. 第二方案能否沿用同一 workload、故障模型與 verifier 公平比較；
3. 學習收益是否足以抵消另一套配置、恢復與維護成本。

只有上述評估支持時，才另行為 PXC 建立設計與實作計畫；否則只保留架構比較。

## 13. 驗證策略

規格落地後的驗證至少包括：

- Compose 與腳本靜態檢查；
- 從空 volumes 建立 Cluster；
- 每個 scenario 的獨立重跑；
- Workload ledger 與資料庫結果自動比對；
- 明確成功／失敗／未知三類結果的斷言；
- quorum、fencing、Primary 唯一性與 rejoin 狀態斷言；
- Router 入口故障與重連驗證；
- 全 Cluster reboot 後的拓撲與業務資料驗證；
- 章節導航、相對連結與命令可執行性檢查；
- `git diff --check` 與相關 repo 驗證命令。

## 14. 主要風險與控制

| 風險 | 控制方式 |
|---|---|
| 三節點 lab 太重，影響其他章節 | 獨立 Compose project，按需啟動，不修改現有 volumes |
| 把 Compose 說成生產 HA | 文檔明確區分軟體行為驗證與物理故障域 |
| 只看 Cluster 狀態，不驗證業務結果 | 強制 workload ledger + verifier |
| 重試造成重複訂單 | `request_id` 唯一約束與冪等寫入 |
| 把未知結果算成資料丟失或成功 | 三態結果模型，故障後查明 |
| 網路故障腳本破壞宿主環境 | 所有 fault 僅作用於隔離的 Compose 網路／容器 |
| 章節繼續膨脹 | 通用理論、產品專題、Runbook、scenario 分檔 |
| 過早擴張到 PXC／Vitess／ClusterSet | 第二方案門檻與獨立設計 gate |
| 版本與官方預設變化 | 固定 MySQL 8.4 LTS，文檔記錄鏡像版本與配置快照 |

## 15. 官方參考

- [MySQL InnoDB Cluster](https://dev.mysql.com/doc/mysql-shell/8.4/en/mysql-innodb-cluster.html)
- [Group Replication](https://dev.mysql.com/doc/refman/8.4/en/group-replication.html)
- [InnoDB Cluster failover consistency](https://dev.mysql.com/doc/mysql-shell/8.4/en/mysql-innodb-cluster-failover-consistency.html)
- [MySQL Router 8.4](https://dev.mysql.com/doc/mysql-router/8.4/en/)
- [MySQL Router cluster metadata and state](https://dev.mysql.com/doc/mysql-router/8.4/en/mysql-router-general-metadata.html)
- [MySQL 8.4 LTS release model](https://dev.mysql.com/doc/refman/8.4/en/mysql-releases.html)
