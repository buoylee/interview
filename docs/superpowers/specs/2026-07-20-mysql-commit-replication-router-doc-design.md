# MySQL 提交、複製與 Router 文檔補充設計

## 目標

用最少篇幅補齊以下容易混淆的邊界：事務提交與數據頁落盤、複製確認與副本可讀、三節點高可用的多數派原則，以及 MySQL Router 的部署與讀路由行為。

## 修改範圍

只修改以下兩份文檔：

- `mysql-handson/07-logs-and-crashsafe/README.md`
- `mysql-handson/09-replication-and-ha/README.md`

### 第 07 章：提交與可見性

新增一個緊湊表格，區分四件事：

- 最新行版本通常位於 Buffer Pool；
- 其他事務能否讀到它由事務狀態、隔離級別與 MVCC ReadView 決定；
- redo log 負責崩潰恢復與提交持久性；
- `COMMIT` 成功不代表髒數據頁已寫回表空間。

不重複展開現有 WAL、LSN、刷盤策略內容。

### 第 09 章：複製、高可用與 Router

窄幅修正並補充：

- 半同步 ACK 表示副本已接收並持久化日誌，不表示 SQL/applier 已應用，也不保證立即讀到；
- Group Replication 的多數派提交保證組內排序與高可用，不表示所有 Secondary 已追平；
- 三節點生產基線採單 Primary、`2/3` 多數派；等待全部副本會把慢節點或故障節點變成整組不可用條件；
- MySQL Router 本身不選主、不複製數據，只根據拓撲把連接路由到合適節點；需要多實例避免接入層單點；
- MySQL Router 8.4 bootstrap 的關鍵端口：`6446`（Primary 讀寫）、`6447`（Secondary 只讀）、`6450`（自動讀寫分流）；
- `wait_for_my_writes` 只覆蓋同一數據庫客戶端 session 的讀己之寫；跨 session、連接池或任意副本強一致讀仍應走 Primary，或使用 GTID 等待屏障。

同時修正現有表格與「讀己之寫」段落中把半同步 ACK 等同於副本已可讀的表述。

## 非目標

- 不新增實驗、配置教程或完整部署步驟；
- 不重寫章節結構；
- 不把相同內容複製到 `mysql-handson/12-interview-cheatsheet/README.md`；
- 不把傳統主從、半同步與 Group Replication 的保證混為一談。

## 驗證

- 檢查新增內容與原章節不重複、術語一致；
- 核對 Router 8.4 端口和 `wait_for_my_writes` 邊界；
- 執行 Markdown/鏈接相關的現有校驗（若倉庫提供）；
- 執行 `git diff --check`，確保只改動批准的文檔與本規格。
