# MySQL InnoDB Cluster 高可用學習專題設計

**日期**：2026-07-22

**狀態**：已批准

**目標位置**：mysql-handson/09-replication-and-ha/ 與 mysql-handson/00-lab/ha/

## 1. 背景

現有 mysql-handson/09-replication-and-ha/README.md 已涵蓋：

- binlog、relay log 與複製執行鏈；
- GTID 與傳統位點；
- 異步、半同步與 Group Replication 的基礎差異；
- 半同步 ACK、Secondary apply 與可讀性的邊界；
- 主從延遲、讀己之寫與 Router；
- 三個傳統複製場景：延遲、GTID 續傳、errant transaction。

目前缺少的是一套完整的端到端 HA 學習模型：

- 客戶端收到成功時，系統究竟承諾了什麼；
- 資料面、控制面、路由面與應用層如何協作；
- quorum、選主、fencing、重連與結果未知如何串成完整故障時序；
- 如何用業務證據，而不是只看 Cluster 狀態，驗證 RPO 與 RTO；
- 如何從本地行為實驗延伸到生產部署、監控、演練和恢復。

本專題不是收集所有 MySQL HA 產品，而是用最少方案建立可遷移的 HA 能力。

## 2. 學習終點

完成專題後，學習者應能獨立完成以下真實任務：

> 公司要求自建 MySQL HA 時，能完成需求分析、方案判斷、部署、故障演練與恢復，並用證據判斷已確認資料是否遺失。

具體能力包括：

- 畫出資料面、控制面、路由面與應用層；
- 說清楚一次事務從請求到 Primary commit、組內認證、Secondary apply 的完整流程；
- 預測程序崩潰、主機故障、網路分區、慢節點、Router 故障與 quorum loss 的結果；
- 執行計劃內切換和意外故障切換；
- 測量實際 RTO，而不是引用產品宣傳值；
- 證明所有明確成功的事務仍存在；
- 正確處理連線中斷造成的結果未知；
- 區分 HA、讀擴展、Backup/PITR 和跨地域 DR。

## 3. 核心決策

### 3.1 學習策略

採用「一套主方案深入，第二方案設門檻」：

1. 保留傳統複製的必要原理與失敗反例；
2. 不完整部署 MHA、舊 Orchestrator 或手工位點切主系統；
3. 完整學習一套現代 HA 主方案；
4. 主方案完成後，再檢查是否存在重要機制缺口；
5. 只有缺口足夠重要且可實驗驗證時，才加入第二方案。

這避免以歷史順序學習大量舊工具，也避免為了「全面」而搭建多套高度重複的集群。

### 3.2 主方案

主方案固定為：

- MySQL 8.4 LTS；
- InnoDB Cluster；
- 三個 Group Replication 成員；
- Single-Primary；
- MySQL Shell / AdminAPI；
- MySQL Router；
- 本地以 Docker Compose 模擬；
- 生產心智模型為三台位於獨立故障域的 Linux VM 或主機。

選擇 InnoDB Cluster 的原因不是單純「官方」，而是它能在同一套系統內展示：

- 成員管理；
- quorum 與 view change；
- write-set ordering 與 certification；
- Primary election；
- fencing；
- flow control；
- 節點 recovery 與 rejoin；
- Router metadata 與連線路由；
- 應用重連、冪等和結果未知。

### 3.3 第二方案候選

Percona XtraDB Cluster（PXC）只保留為門檻式候選，不預先承諾實作。

如果主方案完成後，仍需要觀察下列差異，才考慮加入：

- Galera virtually synchronous 語義；
- multi-primary certification conflict；
- PXC 的 SST / IST；
- 相同故障測試在 InnoDB Cluster 與 PXC 上產生的實質差異。

### 3.4 基礎設施邊界

生產心智模型：

- 三個資料庫成員位於獨立故障域；
- 同一地域內保持低延遲；
- Router 跟隨應用實例部署；
- 應用具備連線重建、超時、冪等和未知結果確認能力。

本地 Lab：

- 用不同容器和網路模擬三個成員；
- 可驗證選主、quorum、fencing、路由和恢復；
- 不宣稱能重現真實主機、交換機、磁碟控制器、檔案系統或可用區故障。

## 4. 非目標

主線不包含：

- MHA 的完整部署；
- 舊 Orchestrator 的完整部署；
- 以 binlog file/position 為核心的手工 HA 平台；
- multi-primary InnoDB Cluster；
- 自動讀寫分離；
- Kubernetes Operator；
- InnoDB ClusterSet；
- Vitess 分片；
- MySQL NDB Cluster；
- 雲廠商內部 HA 實作；
- 為展示產品數量而增加第二套集群；
- 形式化 Paxos 證明；
- 把本地 Compose 宣稱為生產級故障域。

Kubernetes、跨地域 DR、Vitess、NDB 和雲托管 HA 可以作為方案地圖中的邊界說明，但不進入主方案 Lab。

## 5. 整體學習架構

~~~text
已有複製基礎
binlog / GTID / ACK / apply
        ↓
產品無關的 HA 理論
故障模型 / quorum / fencing / RPO / RTO
        ↓
InnoDB Cluster 主方案
把通用理論映射到 MySQL 8.4
        ↓
端到端實驗
持續寫入 → 故障 → 選主 → 重連 → 恢復 → 驗證
        ↓
生產化能力
監控 / 備份 / 升級 / 演練 / runbook
        ↓
第二方案門檻
只補主方案無法覆蓋的重要機制
~~~

現有章節中的 binlog、GTID、半同步和 ACK != apply 作為前置知識引用，不重複寫成另一套複製教程。

## 6. 產品無關的 HA 理論

所有理論圍繞一個核心問題：

> 當客戶端看到成功時，系統究竟承諾了什麼？

### 6.1 請求結果三態

每次業務操作必須被分類為：

- **明確成功**：客戶端收到成功；系統必須能描述其持久性保證；
- **明確失敗**：已確認事務沒有提交，可以安全重新執行；
- **結果未知**：SQL 可能已提交，但回應在連線中斷時遺失。

結果未知不能直接重放。應用必須使用穩定 request_id、資料庫唯一約束和查詢確認來解析最終結果。

### 6.2 端到端分層

| 層次 | 責任 |
|---|---|
| 應用層 | deadline、重連、有限重試、冪等、結果未知確認 |
| 路由面 | 找到當前 Primary，避免把新連線送往不可寫節點 |
| 控制面 | 故障檢測、成員資格、選主、fencing |
| 資料面 | 執行、排序、認證、複製、apply |
| 儲存層 | redo、binlog、fsync、crash recovery |

每一層都可能單獨故障，因此「資料庫節點仍在線」不等於端到端可用。

### 6.3 故障模型

深入以下故障：

- MySQL 程序崩潰；
- 整台主機失效；
- Primary 與多數派網路分區；
- 節點仍活著但非常慢；
- 儲存故障或資料損壞；
- Router 或應用連線入口失效；
- 多數成員同時失效；
- 整個故障域失效。

每個故障都要回答：

- 哪些節點仍可讀；
- 哪個節點可寫；
- 誰必須被隔離；
- 是否仍有 quorum；
- 哪些請求變成結果未知；
- 自動恢復和人工介入的邊界。

### 6.4 Quorum、選主與 fencing

理論需覆蓋：

- 三節點為何可以容忍一個成員故障；
- 兩節點為何難以同時滿足自動切換與防腦裂；
- 多數派決策、全節點 apply 和全部磁碟落盤不是同一件事；
- 選出新 Primary 後，舊 Primary 仍必須失去寫資格；
- 恢復節點必須驗證狀態並追平，不能直接重新開放寫入。

### 6.5 提交與一致性邊界

明確分開：

1. Primary 執行事務；
2. 產生 write set；
3. 組內排序與 certification；
4. Primary 本地 commit；
5. 客戶端收到結果；
6. Secondary apply；
7. Secondary 對讀請求可見。

教材不得用模糊的「三台同步完成」壓縮上述邊界。

### 6.6 HA、DR 與恢復

- **HA**：在允許的局部故障下恢復或繼續服務；
- **Backup/PITR**：處理誤刪、邏輯損壞和歷史恢復；
- **DR**：處理整個地域或資料中心失效；
- **Read scaling**：分散讀流量，不等於提高資料安全。

### 6.7 可量化指標

至少測量：

- RPO；
- RTO；
- 故障檢測時間；
- 選主時間；
- Router 拓撲刷新時間；
- 應用重新成功寫入時間；
- 成功、失敗、未知請求數；
- certification conflict；
- applier backlog；
- flow control；
- Cluster 是否重新恢復一故障容忍能力。

## 7. InnoDB Cluster 教學模型

### 7.1 元件責任

| 元件 | 責任 | 不負責 |
|---|---|---|
| MySQL Server / InnoDB | 執行事務、本地 redo/binlog、資料持久化 | 不替應用處理重試 |
| Group Replication | 成員管理、排序、認證、quorum、選主 | 不搬遷既有客戶端連線 |
| MySQL Shell / AdminAPI | 建立、配置、檢查、修復 Cluster | 不位於正常 SQL 資料路徑 |
| MySQL Router | 依 Cluster Metadata 路由連線 | 不複製資料、不決定 Primary |
| 應用程式 | 重連、超時、冪等、未知結果確認 | 不能假設切主對 session 無感 |

### 7.2 正常提交時序

~~~text
Client
  → Router
  → Primary 執行事務
  → 產生 write set
  → Group Replication 排序與認證
  → Primary 本地提交
  → Client 收到結果
  → Secondary 繼續 apply
~~~

關鍵教學邊界：

- 多數派完成組內決策，不表示所有 Secondary 已 apply；
- Secondary 可能存在 applier backlog；
- quorum、日誌持久化、Primary commit 和 Secondary 可讀是不同邊界；
- 「明確成功不丟」必須結合 durability 配置與允許故障模型來論證。

### 7.3 Primary 故障時序

~~~text
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
~~~

MySQL 8.4 的 group_replication_consistency 預設為 BEFORE_ON_PRIMARY_FAILOVER。教材要展示它如何在 failover 後先處理 backlog、避免新 Primary 對應用呈現資料倒退，以及這項保證如何增加恢復等待時間。

Router 偵測後端關閉後會改從其他成員取得 metadata。連往失效 MySQL Server 的既有應用連線會被關閉，應用必須重新連到 Router。

### 7.4 主線配置邊界

主線固定：

- 三成員 Single-Primary；
- 僅使用 InnoDB；
- GTID；
- row-based binlog；
- 明確設定 redo/binlog durability；
- BEFORE_ON_PRIMARY_FAILOVER；
- 寫流量只使用 Router 的 Primary 讀寫入口；
- Router 跟隨應用部署；
- 不加入 multi-primary；
- 不加入自動讀寫分離。

### 7.5 必須深入的機制

- Group Replication 成員狀態與 view change；
- XCom / quorum 在交易與成員決策中的位置；
- write-set extraction、全序與 certification conflict；
- Primary election 和 memberWeight；
- expelTimeout、網路抖動與誤判取捨；
- exitStateAction、super_read_only 與 fencing；
- flow control、applier backlog 和慢節點；
- Clone、增量恢復、auto-rejoin 與人工 rejoin；
- Cluster Metadata 和 Router metadata cache。

## 8. Lab 架構

現有 mysql-handson/00-lab/docker-compose.yml 保持原本單 Primary / Replica 語義。HA Lab 使用獨立 Compose project、容器、網路和 volumes。

~~~text
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
~~~

### 8.1 元件

- **DB-1 / DB-2 / DB-3**：角色可動態變化，不以容器名固定 Primary；
- **Router A / Router B**：驗證資料庫切主與路由入口冗餘；
- **Workload Runner**：執行最小業務寫入並記錄客戶端結果；
- **Fault Controller**：注入 crash、partition、latency、pause 和 Router failure；
- **Evidence Verifier**：比對客戶端 ledger、Cluster 狀態與成員最終資料。

### 8.2 最小業務操作

使用 create_order(request_id, payload) 作為驗證操作。

資料表必須：

- 以 request_id 作為穩定業務冪等鍵；
- 使用唯一約束阻止重試產生重複業務結果；
- 能記錄提交時間與實際寫入節點；
- 支援故障後按 request_id 查詢最終狀態。

Workload Runner 對每次嘗試記錄：

- request_id；
- 開始與完成時間；
- Router 入口；
- SUCCESS、FAILURE 或 UNKNOWN；
- 重試次數；
- 錯誤類型。

### 8.3 證據契約

Verifier 必須檢查：

- 所有 SUCCESS request_id 都存在；
- 同一 request_id 只有一筆業務結果；
- 每個 UNKNOWN 最後都能解析為已提交或未提交；
- 故障期間沒有兩個可寫 Primary；
- 新 Primary 與恢復節點最終資料一致；
- RTO 有明確起點和終點；
- 實驗結束後 Cluster 恢復三成員與一故障容忍能力。

不能只以容器重新啟動、cluster.status() 顯示 ONLINE 或 Router 程序存活作為成功證據。

## 9. 核心 Scenario

| # | Scenario | 主要問題 | 必要證據 |
|---|---|---|---|
| 1 | 計劃內切換 | 正常維護的切換順序與中斷時間 | Primary 變更、client outcomes、RTO |
| 2 | Primary 突然崩潰 | 自動檢測、選主、Router 更新與重連 | view、election、ledger、最終資料 |
| 3 | Primary 與多數派分區 | 少數派是否被 fencing | 可寫節點數、雙寫檢查、ledger |
| 4 | Quorum loss | 系統是否 fail closed | 寫入拒絕、成員狀態、恢復流程 |
| 5 | 慢成員 | backlog 與 flow control 如何影響延遲 | queue、flow control、client latency |
| 6 | Router 故障 | DB 正常時入口是否仍可能成為單點 | Router 狀態、另一入口、重連時間 |
| 7 | 成員 rejoin | 節點如何追平並安全恢復服務 | recovery 狀態、資料一致性 |
| 8 | HA 不能替代 PITR | 邏輯錯誤為何會複製到所有成員 | DELETE 傳播、restore/PITR 證據 |

每個 Scenario 沿用倉庫既有格式：

~~~text
我預期什麼
→ 注入故障
→ 實際觀察
→ 客戶端證據
→ Cluster 證據
→ 資料驗證
→ 預期與實際落差
~~~

原始執行輸出保存於 Git 忽略的本地 evidence 目錄；文檔只保存足以證明結論的關鍵片段。

## 10. 生產 Runbook

### 10.1 部署前檢查

- 成員分布於獨立故障域；
- 節點間延遲、丟包和頻寬可接受；
- 版本、配置、時鐘、字符集與儲存引擎一致；
- redo、binlog、GTID 和 durability 明確；
- Router 不形成單點；
- 應用具備重連與冪等；
- 備份、binlog 保存與 PITR 已實際恢復驗證；
- 生產帳號、TLS、憑證與權限不沿用 Lab 簡化配置。

### 10.2 穩態觀測

至少觀察：

- 當前 Primary；
- 成員狀態；
- Cluster 是否仍具有故障容忍能力；
- group view；
- certification conflict；
- applier/recovery queue；
- flow control；
- Router metadata refresh；
- Router 後端連線錯誤；
- 應用成功、失敗、未知和重試比例；
- 備份 restore 驗證結果。

### 10.3 故障處置格式

每個 Runbook 固定回答：

~~~text
觸發條件
→ 現象
→ 先確認什麼
→ 是否允許自動恢復
→ 何時人工介入
→ 危險操作及前置條件
→ 恢復後驗證
~~~

需涵蓋：

- planned switchover；
- Primary 意外失效；
- auto-rejoin 失敗；
- network partition；
- quorum loss；
- 慢節點與 flow control；
- Router 故障；
- complete outage 後的重啟判斷；
- clone / rejoin；
- backup restore 與 PITR。

強制 quorum、重新 bootstrap、清除 metadata 或把舊 Primary 強行帶回等操作，必須寫出資料集確認條件和風險，不包裝成無條件一鍵命令。

### 10.4 應用錯誤處理

- 連線錯誤後丟棄原 session；
- 只對可安全重試的操作做有限重試；
- 使用 request_id 與唯一約束保證冪等；
- UNKNOWN 先查詢確認，再決定後續行為；
- 區分連線 timeout、查詢 timeout 與整體業務 deadline；
- 避免無限重試形成重試風暴。

### 10.5 變更與演練

- planned switchover；
- 單節點維護；
- rolling upgrade；
- Primary crash 演練；
- Router failure 演練；
- restore/PITR 演練；
- 版本或配置變更後重跑關鍵 Scenario；
- 演練後確認恢復三成員與故障容忍能力。

## 11. 文件與目錄設計

~~~text
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
│           └── 08-ha-cannot-replace-pitr.md
│
└── 99-interview-cards/
    ├── q-ha-vs-replication.md
    ├── q-quorum-and-fencing.md
    ├── q-transaction-outcome-unknown.md
    └── q-innodb-cluster-failover.md
~~~

組織原則：

- 現有 Primary/Replica Lab 不改語義；
- HA Lab 使用獨立 Compose project、network 與 volumes；
- 使用者仍可從 00-lab/Makefile 進入 ha-* 指令；
- ha-foundations.md 只寫產品無關理論；
- innodb-cluster/README.md 只寫 MySQL 8.4 機制映射；
- production-runbook.md 承載生產檢查與處置；
- Scenario 保存實驗方法與關鍵證據；
- 面試卡只壓縮結論並鏈回理論和 Scenario。

## 12. 完成標準

### 12.1 知識驗收

學習者能：

- 不看命令講清完整提交與 failover 時序；
- 解釋 quorum、選主與 fencing 的不同責任；
- 說清楚自動切主為何仍會斷連；
- 分辨 SUCCESS、FAILURE 和 UNKNOWN；
- 區分 HA、read scaling、Backup/PITR 與 DR；
- 根據 RPO、RTO、延遲和運維條件判斷方案適用性。

### 12.2 Lab 驗收

從乾淨 volumes 開始可重複完成：

- 建立三成員 Single-Primary Cluster；
- bootstrap Router；
- 持續執行業務 workload；
- 執行八個 Scenario；
- 產生 client、Cluster 與資料三類證據；
- 驗證 SUCCESS 不遺失、無重複業務結果、UNKNOWN 可解析；
- 驗證無雙 Primary；
- 測量 RTO；
- 恢復三節點故障容忍能力。

### 12.3 文件驗收

- 每個理論承諾鏈到 Scenario 或官方機制；
- 每個 Scenario 包含預期、實機和落差；
- 不存在模糊的「同步完成」或無條件「零丟失」宣稱；
- 所有章節均須有明確內容與驗收邊界；
- Lab 可從乾淨環境執行；
- README、理論、Runbook、Scenario 和面試卡互相鏈接；
- 不破壞現有單 Primary/Replica Lab。

## 13. 第二方案門檻

完成 InnoDB Cluster 後才評估：

1. 是否仍有重要 HA 機制無法觀察；
2. PXC 是否會產生實質不同的提交、衝突或恢復結果；
3. 差異是否與真實工作或面試需求有關；
4. 是否能重用 workload、fault controller 和 verifier。

只有出現至少兩個具體、重要且可驗證的機制缺口，才新增 PXC 實驗。

若加入 PXC，只做精簡對照：

- multi-primary 並發寫衝突；
- 節點故障下的 commit 行為；
- 網路分區與 quorum；
- SST / IST 節點恢復。

否則 PXC 只保留架構比較表，專題到 InnoDB Cluster 為止。

## 14. 風險與緩解

| 風險 | 緩解 |
|---|---|
| HA Lab 過重，影響其他章節 | 使用獨立 Compose project，按需啟動 |
| 把容器故障誤稱為生產故障域 | 文檔明示模擬邊界，生產模型使用獨立主機 |
| 只驗證 Cluster 狀態，不驗證業務 | 強制 client ledger + Cluster + 最終資料三類證據 |
| 自動重試掩蓋 UNKNOWN | 三態分類，UNKNOWN 不盲目重放 |
| Router 被誤認為無縫 session 遷移 | 故障場景強制觀察舊連線中斷與重連 |
| 無條件宣稱零資料遺失 | 每項結論綁定 durability、故障模型與實測證據 |
| 為比較產品而擴張範圍 | 使用第二方案門檻 |
| 危險恢復命令被照抄 | Runbook 寫明前置條件、dry-run 與資料風險 |
| 改壞既有 MySQL Lab | HA 目錄、資源與入口隔離，回歸驗證原 Lab |

## 15. 官方參考

- [MySQL InnoDB Cluster](https://dev.mysql.com/doc/mysql-shell/8.4/en/mysql-innodb-cluster.html)
- [MySQL 8.4 Group Replication](https://dev.mysql.com/doc/refman/8.4/en/group-replication.html)
- [Configuring InnoDB Cluster Failover Consistency](https://dev.mysql.com/doc/mysql-shell/8.4/en/mysql-innodb-cluster-failover-consistency.html)
- [MySQL Router Cluster Metadata and State](https://dev.mysql.com/doc/mysql-router/8.4/en/mysql-router-general-metadata.html)
- [MySQL 8.4 LTS and Innovation Releases](https://dev.mysql.com/doc/refman/8.4/en/mysql-releases.html)

## 16. 實作交接約束

- 本文件批准並提交後，先由使用者審閱落盤版本；
- 使用者確認後才進入 implementation plan；
- implementation plan 必須逐項對應本設計的邊界與驗收；
- 未重新取得批准，不得加入 PXC、ClusterSet、Kubernetes、multi-primary 或自動讀寫分離；
- 工作樹中的其他修改不屬於本專題，不得被暫存或提交。
