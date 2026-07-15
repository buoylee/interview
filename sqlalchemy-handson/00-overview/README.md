# 00 · 起點與全景：先建立可驗證的心智模型

本章先界定 M1 的學習範圍與案例，不急著背 API。實作環境與啟動方式請見
[`lab/README.md`](../lab/README.md)；下一步從
[`01 · Engine 解剖`](../01-engine-execution/) 追蹤第一次執行。

## Production question：production request 經過了什麼

多租戶訂單服務收到 request 後，application service、SQLAlchemy 與 psycopg 各自
負責什麼，最後如何抵達 PostgreSQL？在還沒引入 ORM 或 async API 前，我們需要一套
能預測 SQL、交易與連線資源的共同語言。

## Prediction：先畫出責任邊界

- request 不會直接「交給資料庫」；application service、Connection、Engine、Pool、
  Dialect 與 psycopg 各有不同責任。
- Core／ORM 與 sync／async 是兩條獨立決策軸，不應綁成同一個偏好選擇。
- tenant、product、inventory 與 order 的邊界，之後應由可執行 schema、查詢與交易
  證據驗證，而不是只靠文件約定。

## Failing/naive behavior：把 SQLAlchemy 當成黑盒

直覺作法是看到資料存取需求便直接挑 Core 或 ORM，再把 async 當成效能開關。這會把
SQL 形狀、交易所有權、連線容量與 tenant 隔離混在一起；事故發生時，只剩「查詢有
送出去」的模糊描述，無法指出責任在哪一層，也無法提出可重現的證據。

## Mechanism：從 request 追到 PostgreSQL

### 一次請求如何抵達 PostgreSQL

**Mental model**：先用下列路徑定位責任邊界，而不是把 SQLAlchemy 想成單一黑盒：

```text
request
  → application service
  → Connection
  → Engine
  → Pool
  → Dialect
  → psycopg
  → PostgreSQL
```

`application service` 決定一個業務操作的交易邊界；`Connection` 是同步 Core 執行
SQL 與控制交易的公開介面；`Engine` 組合連線取得、方言與執行能力；`Pool` 管理可
重用的 DBAPI 連線；`Dialect` 把 SQLAlchemy 結構轉成 PostgreSQL 與 psycopg 能處理
的形式；psycopg 最後依 DBAPI 職責與 PostgreSQL 溝通。

**Public contract**：應用程式依賴 SQLAlchemy 2.0 的公開 Core 介面與明確交易範圍，
不要把 pool 內部物件或未文件化屬性當成服務契約。

**Implementation note**：上述箭頭是用來追蹤責任的教學路徑，不是每一層都直接
呼叫下一層的類別圖。需要觀察 SQLAlchemy 2.0.51 內部細節時，案例會明確標示版本，
而架構決策仍以公開介面為準。

### Core／ORM 與 sync／async 的決策邊界

M1 固定使用同步 SQLAlchemy Core，因為此階段要直接觀察 SQL 結構、Result、
Connection 交易狀態與 Pool 容量。這不是宣稱 Core 永遠優於 ORM，而是先隔離執行
管線，避免物件生命週期與 UoW 同時增加變因。

- 選 Core 或 ORM，取決於工作主要是在組合 SQL 與批次資料流，還是在維護物件關係、
  Identity Map 與工作單元。ORM 的教學屬於 M2，本章只保留這條決策界線。
- 選 sync 或 async，取決於整條呼叫鏈與並發模型，不是用 `async` 關鍵字判斷快慢。
  M1 保持同步；Async SQLAlchemy 的 API、取消語義與池容量屬於後續里程碑。

**Public contract**：M1 的可執行案例只暴露同步 Core 路徑。

**Mental model**：Core／ORM 決定資料操作的抽象層次，sync／async 決定呼叫與等待
模型；這是兩條不同的決策軸。

### 多租戶商品、庫存與訂單案例

案例以 SaaS 訂單服務為背景。每個 tenant 有自己的商品目錄與庫存，客戶下單時，
application service 必須在正確的 tenant 範圍內讀取商品、保留庫存並建立訂單。

- `tenant`：所有商業資料的隔離邊界。
- `product`：tenant 內可販售的商品與定價識別。
- `inventory`：某商品可用、已保留與已扣減的數量。
- `order`：一次下單的交易主體，包含一或多個 `order line`。

後續章節會逐步讓 schema constraint、型別、DML、交易與連線池承擔可驗證的責任。
M1 先建立 Core 基線；多租戶 RLS、冪等、outbox、ORM 與 async 都不在 00–06 的實作
範圍。

### 三種穩定性標籤

- **Public contract**：SQLAlchemy 文件化、應用程式可以長期依賴的行為。
- **Mental model**：協助預測行為的簡化模型；遇到反例時要回到證據修正。
- **Implementation note**：特定版本的觀察或內部細節；升級 SQLAlchemy 時必須重驗。

看到 `Implementation note` 不代表可以把內部細節變成 production dependency；它的
用途是解釋證據，而不是建立新的耦合。

## Corrected behavior：先固定 M1 的可執行基線

M1 把案例固定在同步 Core：application service 擁有業務交易邊界，應用程式只依賴
公開 API，並用 `Public contract`、`Mental model`、`Implementation note` 區分穩定
程度。Core／ORM 或 sync／async 的其他選擇保留到對應里程碑，不在同一次實驗增加
變因。

## Evidence：只主張目前能驗證的事

- [`test_package_contract.py`](../lab/tests/unit/test_package_contract.py) 驗證案例 package
  版本為 0.1.0，SQLAlchemy 版本固定為 2.0.51。
- [`pyproject.toml`](../lab/pyproject.toml) 與 `uv.lock` 固定 Python 相容範圍、直接依賴
  與可重現的開發工具鏈。
- PostgreSQL 行為、事件順序、交易狀態與 pool 狀態的證據由 01–06 各章產生；chapter
  00 不預先宣稱尚未執行的結果。

## Decision：M1 的選擇與延後項目

M1 採用 Python 3.14、SQLAlchemy 2.0.51、psycopg 3、PostgreSQL 18.4 與同步 Core，
以最少變因建立執行、schema、compiler、DML、交易與 pool 的共同基線。ORM、async、
RLS、冪等與 outbox 保留到後續里程碑；觀察到內部實作時，也不得把它升格成應用程式
契約。

## Interview drill：能否把機制轉成判斷

1. 為什麼 Core／ORM 與 sync／async 是兩條決策軸？
2. Engine、Connection、Pool、Dialect 與 psycopg 各自負責什麼？
3. `Mental model` 與 `Public contract` 衝突時，production code 應依賴哪一個？
4. 為什麼 chapter 00 不把尚未執行的 PostgreSQL 行為寫成 evidence？

### 讀完 M1 能做什麼

- [ ] 00：畫出 request 到 PostgreSQL 的責任路徑，說明兩條技術決策軸。
- [ ] 01：區分 Engine、Connection、Pool、Dialect 與 psycopg 的角色。
- [ ] 02：用 MetaData、型別與 constraint 表達 schema 契約。
- [ ] 03：預測 expression、bind parameter、compiler 與 cache key 如何影響 SQL。
- [ ] 04：用 Core 建立查詢與 DML，並選擇正確的 Result 形狀。
- [ ] 05：解釋 autobegin、commit、rollback、savepoint 與失敗後交易狀態。
- [ ] 06：把 QueuePool 參數換算成服務與 PostgreSQL 的連線容量預算。
