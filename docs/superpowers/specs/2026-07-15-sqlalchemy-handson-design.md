# 設計：`sqlalchemy-handson/` 資深工程師／架構師教程

> 日期：2026-07-15
>
> 狀態：已核准，待實作計畫
>
> 目標讀者：具備資深後端、Python、SQL 與交易基礎，但尚未系統掌握 SQLAlchemy 的工程師與架構師

## 1. 背景

倉庫已有 [`python-data/`](../../../python-data/) 教程，涵蓋 Python 資料存取的整體選型、DBAPI、連線池、SQLAlchemy Session／UoW、交易、N+1、async、Alembic 與資料層架構。它適合作為資料存取架構導讀，但每個 SQLAlchemy 主題的篇幅與實驗深度不足以形成一套完整的 SQLAlchemy 專著。

本設計新增獨立的 `sqlalchemy-handson/`：

- `python-data/` 保留為 Python 資料存取架構與快速決策入口。
- `sqlalchemy-handson/` 承接該入口，深入 SQLAlchemy 的公開 API、執行機制、失敗語義、生產設計、事故診斷與架構取捨。
- 兩者互相連結，但不重複維護同一篇基礎內容。

## 2. 目標與非目標

### 2.1 目標

讀者完成教程後，應具備三層能力：

1. **正確使用**：能寫出交易邊界清楚、型別安全、可測試且可觀測的 SQLAlchemy 2.0 程式碼。
2. **解釋機制**：能從 Engine、Pool、Dialect、DBAPI 一路解釋到 Session、Identity Map、Unit of Work 與 flush。
3. **作出決策**：面對 ORM／Core、sync／async、loader strategy、locking、repository、bulk API 等選擇時，能說明適用條件、成本與失敗模式。

教程必須同時服務兩種真實需要：

- 日常開發：設計、實作、測試、遷移、調優與事故排查。
- 面試答辯：能回答行為預測、底層原理、方案比較與架構追問，而不是只背 API。

### 2.2 非目標

- 不把 SQLAlchemy 官方 API 文件逐頁翻譯成中文。
- 不重新教授 SQL、關聯模型、ACID、MVCC 等完整資料庫基礎；必要處連結倉庫既有教程。
- 不擴張成完整 FastAPI、微服務、broker、Saga 或分散式交易教程。
- 不維護 PostgreSQL 與 MySQL 兩套完整實作。
- 不做 SQLAlchemy 私有源碼的逐行導讀，也不讓正式程式碼依賴 private API。
- 不承諾「exactly once」、通用的效能倍數或脫離環境的連線池魔法數字。

## 3. 已核准的技術與寫作決策

| 決策 | 結論 |
|---|---|
| 教程位置 | 新建 `sqlalchemy-handson/`，`python-data/` 作上游導讀 |
| 教學組織 | 螺旋演進＋故障驅動，搭配參考型附錄 |
| 主案例 | 單一、多租戶的訂單／庫存服務 |
| 框架邊界 | 核心框架中立；只提供薄 FastAPI adapter |
| 同步／非同步 | 先以 sync 講透機制，再演進到 async |
| 資料庫 | PostgreSQL 18 為唯一可執行基線；補充 MySQL／SQLite 關鍵差異 |
| SQLAlchemy | 公開 API 基線為穩定的 2.0 系列；lab 初始鎖定 2.0.51 |
| Python | lab 鎖定 Python 3.14；正文程式碼盡量相容 Python 3.11+ |
| 語言 | 單一繁體中文版；API、錯誤與必要術語保留英文 |
| 原理深度 | 機制級解釋＋少量固定版本的關鍵源碼路徑 |
| 系統邊界 | 單服務內一致性；含冪等、outbox 寫入與 claim，不含 broker／Saga 實作 |
| 交付形態 | 正文＋可運行服務＋PostgreSQL lab＋測試＋migration＋真實 evidence＋面試卡 |

版本選擇依據：

- SQLAlchemy 官方下載頁將 2.0.51 列為穩定 2.0 版本，而 2.1 尚處於 beta：<https://www.sqlalchemy.org/download.html>
- PostgreSQL 18 是目前正式版本，16–18 仍在官方支援期：<https://www.postgresql.org/support/versioning/>
- Python 3.14 處於 bugfix 支援階段，3.15 仍是 prerelease：<https://devguide.python.org/versions/>

小版本可以在實作時經驗證後更新，但不得未經驗證改用 prerelease API。

## 4. 教學方法與閱讀契約

每章採用相同的故障驅動結構：

1. 生產情境或面試追問。
2. 可執行的錯誤／天真实作。
3. 讀者先預測行為，再執行實驗。
4. 公開 API 與正確寫法。
5. 底層機制與必要源碼路徑。
6. PostgreSQL 證據：SQL、query count、lock、EXPLAIN 或 timing。
7. 架構取捨、常見錯誤與面試追問。

原理內容必須標明穩定性層級：

- **Public contract**：應用可以依賴的 SQLAlchemy 2.0 行為。
- **Mental model**：用於推理與除錯，但不是 API 承諾。
- **Implementation note**：針對 SQLAlchemy 2.0.51 的選擇性內部源碼說明。

章末面試題只做複習、預測與答辯，不得承載正文沒有教過的新知識。

## 5. 主案例

### 5.1 系統範圍

主案例是一個多租戶訂單與庫存服務。它限制在單一 PostgreSQL 資料庫、單一部署單元，足以重現 SQLAlchemy 的高階問題，又不滑向分散式系統教程。

核心資料模型：

- `Tenant`：租戶邊界。
- `Product`、`Inventory`：商品與可用／保留庫存；庫存包含版本欄位。
- `Order`、`OrderLine`：訂單聚合、狀態機、金額與明細。
- `InventoryReservation`：保存庫存保留的業務證據。
- `IdempotencyRecord`：防止相同請求重複建立訂單。
- `OutboxEvent`：與訂單在同一交易寫入，供批量 claim 與重試實驗使用。

schema 必須實際使用並解釋 unique、check、foreign key、partial index 與 composite index。金額使用精確數值型別，不使用 binary floating point。

### 5.2 程式邊界

```text
FastAPI adapter
    ↓ input validation、tenant/request context、error mapping
Application service
    ↓ place/cancel order；不依賴 FastAPI
Transaction boundary / Session
    ↓
Domain invariants + SQLAlchemy mappings + query objects
    ↓
Engine → Pool → Dialect → psycopg → PostgreSQL
```

主案例最終採取務實架構：mapped entity＋application service＋專用 query object。教程明確承認 `Session` 已提供 Unit of Work 能力，不額外建立只有 CRUD 的 generic repository。

第 23 章以隔離的 vertical slice 比較 direct Session、query object、repository 與獨立 domain model，不為展示模式而強行重構主案例。

### 5.3 下單資料流

1. adapter 建立 request-scoped Session，但不自行決定業務 commit 時機。
2. application service 驗證 tenant 與 idempotency key。
3. 在單一交易中檢查庫存、建立 `Order`、`OrderLine` 與 `InventoryReservation`。
4. 在同一交易寫入 `OutboxEvent`。
5. 正常完成才 commit；任何例外 rollback。
6. adapter 將 domain／data-access error 映射成 HTTP 回應。
7. outbox worker 使用獨立短交易 claim 事件；原交易內禁止呼叫 broker 或其他外部 I/O。

交易所有權固定如下：application service 的入口負責 `begin`／commit／rollback；較低層的 query／persistence function 可以 `flush`，但不得自行 `commit`。FastAPI dependency 只負責建立與關閉 Session。outbox worker 只實作資料庫 claim／狀態更新與 publisher interface；不實作真實 broker。

案例從故意不完整的版本演進，依次重現並解決跨租戶洩漏、超賣、重複下單、N+1、長交易、pool exhaustion 與 migration lock。

## 6. 章節地圖

教程共 `00–24`，分成四個可獨立驗收的里程碑。每卷完成時，案例服務都必須處於可運行、可測試狀態。

### 6.1 起點

| 章 | 主題 | 核心內容 |
|---|---|---|
| 00 | 起點與全景 | 環境、案例、成功標準；SQLAlchemy 2.0 心智地圖；ORM／Core、sync／async 決策；request 到 PostgreSQL 的完整路徑 |

### 6.2 第一卷：Core 與執行管線

| 章 | 主題 | 核心內容 |
|---|---|---|
| 01 | Engine 解剖 | Engine、Dialect、Pool、DBAPI；一次 `execute()` 的旅程 |
| 02 | Schema 與型別系統 | MetaData、constraint、naming convention、UUID、Decimal、timezone、JSONB、Enum、`TypeDecorator` |
| 03 | SQL Expression 與 compiler | generative API、bind parameter、SQL injection 邊界、compiled cache／cache key、方言編譯 |
| 04 | 查詢、DML 與 Result | join、subquery、CTE、window function、RETURNING、upsert、executemany、`Row`／mapping／scalar 語義 |
| 05 | Connection 與交易狀態機 | autobegin、begin-once、commit-as-you-go、savepoint、isolation、DBAPI autocommit、失敗後狀態 |
| 06 | 連線池與容量治理 | QueuePool、checkout/reset/invalidate、timeout、pre-ping、fork safety、PgBouncer、容量估算與耗盡事故 |

### 6.3 第二卷：ORM 與工作單元

| 章 | 主題 | 核心內容 |
|---|---|---|
| 07 | Typed Declarative 與 mapping | `Mapped`、`mapped_column`、registry、relationship、nullable 推導與型別檢查 |
| 08 | Instrumentation 與物件生命週期 | descriptor、`InstanceState`、transient／pending／persistent／deleted／detached |
| 09 | Session、Identity Map 與 UoW | autoflush、flush dependency ordering、expire／refresh／merge、cascade、rollback 後狀態 |
| 10 | Relationship 與載入策略 | lazy、selectin、joined、subquery、raiseload、write-only；N+1、row explosion、detached 問題 |
| 11 | ORM 查詢與批量 DML | entity／column selection、alias、RETURNING、bulk insert／update／delete、session synchronization |
| 12 | 高階 mapping | association object、composite value、hybrid property、self-reference、inheritance、view-only，以及不該使用的情境 |

### 6.4 第三卷：生產正確性

| 章 | 主題 | 核心內容 |
|---|---|---|
| 13 | 服務層交易邊界 | session-per-operation、application service、例外分類、savepoint、禁止交易內外部 I/O |
| 14 | 並發控制與重試 | lost update、`FOR UPDATE`、optimistic version、deadlock、serialization failure、完整交易重試 |
| 15 | 多租戶隔離 | tenant key、composite constraint、`with_loader_criteria`、Session event、PostgreSQL RLS 與 defense in depth |
| 16 | 冪等與 Transactional Outbox | 唯一性競爭、同交易寫入、`SKIP LOCKED` claim、重試與 exactly-once 迷思 |
| 17 | Async SQLAlchemy | AsyncEngine／AsyncSession、greenlet bridge、`MissingGreenlet`、task safety、取消語義、池容量 |
| 18 | Alembic 與零停機演進 | autogenerate 邊界、expand／contract、資料回填、concurrent index、lock timeout、部署順序 |

### 6.5 第四卷：效能、可觀測性與架構

| 章 | 主題 | 核心內容 |
|---|---|---|
| 19 | 讀取效能 | query budget、N+1、projection、EXPLAIN ANALYZE、keyset pagination、streaming、記憶體成本 |
| 20 | 寫入效能 | flush batching、insertmanyvalues、bulk API、COPY 邊界、長交易、lock footprint |
| 21 | Events 與可觀測性 | Engine／Session events、SQL timing、pool metrics、OpenTelemetry、參數遮罩、低基數標籤 |
| 22 | 測試策略 | 真 PostgreSQL、pytest transaction fixture、concurrency test、migration test、query-count regression |
| 23 | 資料層架構取捨 | direct Session、query object、repository、UoW、獨立 domain model、read replica／多 Engine routing |
| 24 | 事故演練與架構面試 | pool exhaustion、failed Session、detached、`MissingGreenlet`、死鎖、跨租戶洩漏、migration lock 的整合排查 |

### 6.6 附錄

- SQLAlchemy 錯誤索引與診斷決策樹。
- API／架構選型表。
- SQLAlchemy 1.4 → 2.0 遷移指南。
- PostgreSQL／MySQL／SQLite 關鍵差異。
- SQLAlchemy 2.0.51 關鍵內部源碼地圖。
- 面試卡、追問題與案例答辯題。
- SQLAlchemy 2.1 相容性雷達；主線不使用 beta API。

## 7. 產物與目錄

```text
sqlalchemy-handson/
├── README.md
├── 00-overview/
├── 01-engine-execution/
├── ...
├── 24-incident-capstone/
├── appendices/
└── lab/
    ├── pyproject.toml
    ├── uv.lock
    ├── .python-version
    ├── compose.yaml
    ├── alembic.ini
    ├── alembic/
    ├── src/order_service/
    │   ├── model/
    │   ├── application/
    │   ├── persistence/
    │   ├── web/
    │   └── workers/
    ├── tests/
    │   ├── unit/
    │   ├── integration/
    │   ├── concurrency/
    │   └── migrations/
    ├── scenarios/
    └── evidence/
```

### 7.1 程式碼演進

- `src/order_service/` 保存最終可運行的生產級參考實作。
- `scenarios/chXX_*` 保存每章可獨立執行的「錯誤版 → 修正版」實驗。
- 每章連結到對應 source、test、scenario 與 evidence。
- 不複製 25 份完整應用，也不依賴讀者切換隱藏的 git tag 才能完成章節。
- 每卷提供一個驗收命令，驗證該卷的正文、程式與資料庫行為。

## 8. Evidence 契約

每個 scenario 必須包含：

1. `Hypothesis`：執行前預測。
2. `Setup`：資料量、pool 參數、隔離級別與版本。
3. `Command`：一條可重現命令。
4. `Observation`：真實 SQL、錯誤、鎖狀態、query count 或 EXPLAIN。
5. `Explanation`：將觀察連回 SQLAlchemy／PostgreSQL 機制。
6. `Decision`：何時使用、何時不用。
7. `Caveat`：哪些數字只適用於本機環境。

`evidence/` 提交去敏後的真實輸出與環境 manifest。驗證優先使用 query count、狀態轉移、鎖行為與執行計畫形狀；timing 只作同環境下的輔助證據，不宣稱普遍倍數。

## 9. 錯誤語義

教程建立明確且可操作的錯誤分類：

| 類別 | 例子 | 策略 |
|---|---|---|
| Domain error | `OutOfStock`、`TenantMismatch` | 不重試；回傳明確業務結果 |
| Constraint／資料競爭 | `IntegrityError` | rollback；依 constraint name 區分冪等衝突、唯一性競爭與資料錯誤 |
| 暫時性並發錯誤 | SQLSTATE `40001`、`40P01`、`StaleDataError` | 在 budget 內用 backoff＋jitter 重跑完整交易 |
| 連線／資源錯誤 | pool `TimeoutError`、斷線、DB restart | 區分 pool saturation 與 DB unavailable；禁止無條件重試 |
| 程式設計錯誤 | `InvalidRequestError`、`MissingGreenlet`、跨 task 共用 Session | fail fast；修正生命週期或程式模型 |

資料庫錯誤後不得在 failed transaction／inactive Session 上繼續工作。錯誤轉譯集中於 application／adapter 邊界。結構化日誌可以保存 SQLSTATE、constraint name、operation 與 tenant／request correlation，但不得記錄敏感 SQL 參數。

## 10. 驗證策略

- `ruff`：格式與靜態問題。
- `mypy`：以 SQLAlchemy 2.0 原生 PEP 484 型別支援驗證 Typed Declarative 範例，不依賴舊版 SQLAlchemy mypy plugin。
- `pytest` unit：純領域規則與不需資料庫的 expression／mapping 行為。
- `pytest` integration：使用真 PostgreSQL 18；不用 SQLite 代替 PostgreSQL 行為測試。
- `pytest` concurrency：使用 barrier、短 timeout 與可控鎖順序降低競態測試 flake。
- `pytest` migrations：空庫升級、舊 schema 升級、資料回填及明確的 downgrade 邊界。
- query-count assertion：阻止 N+1 回歸。
- 文件中的主要程式片段由測試檔或可執行 scenario 提供，避免正文與程式碼漂移。
- 原理與版本主張優先引用 SQLAlchemy、PostgreSQL、Python 官方文件或對應版本源碼。

任何預期失敗都必須被 scenario 明確捕捉與斷言；真正的測試失敗不能被當成教學輸出忽略。

## 11. 交付里程碑

| 里程碑 | 範圍 | 驗收產物 |
|---|---|---|
| M1 | 00–06 | 教程骨架、PostgreSQL lab、Engine／Core／交易／Pool 正文、測試與 evidence |
| M2 | 07–12 | 完整 ORM、Session／UoW、載入策略與高階 mapping |
| M3 | 13–18 | 一致性、多租戶、鎖／重試、冪等、outbox、async、Alembic |
| M4 | 19–24＋附錄 | 效能、觀測、測試、架構取捨、事故 capstone、面試卡與索引 |

每個里程碑都以「正文＋程式＋測試＋實測 evidence」一起提交。禁止先完成大量無法執行的正文，再於最後補程式與證據。

## 12. 成功標準

教程完成後，讀者應能：

1. 畫出並解釋一次 SQLAlchemy 呼叫從 ORM／Core 到 DBAPI 與 PostgreSQL 的路徑。
2. 正確設計 Engine、Pool、Session 與交易生命週期，並定位 pool exhaustion、failed Session 與連線失效。
3. 解釋 object state、Identity Map、Unit of Work、flush ordering、expire 與 loader strategy 的可觀察結果。
4. 對多租戶、庫存競爭、冪等、重試、outbox 與 async cancellation 建立可測試的一致性設計。
5. 使用 query count、EXPLAIN、events、metrics 與真實錯誤證據診斷效能與可靠性問題。
6. 規劃可部署的 Alembic expand／contract migration。
7. 對 repository、獨立 domain model、Core／ORM、sync／async、bulk API 等選擇提出有條件的架構論證。
8. 完成第 24 章事故演練與案例答辯，而不是只背誦面試卡。

## 13. 風險與控制

### 範圍過大

以四個里程碑拆分，每卷都可獨立驗收。若單章超過一個主要學習目標，實作計畫可拆成同章的多篇，但不得增加新的頂層主題。

### 主案例壓過 SQLAlchemy 主題

只保留能製造真實資料層問題的業務規則。支付、broker、Saga、通知等外部系統使用 interface 或 stub 表示，不實作完整平台。

### 文件與程式漂移

主要範例來自可執行 scenario／test；章節連到具體檔案。每個里程碑同時驗證 docs、code、migrations 與 evidence。

### 私有實作被誤當契約

所有源碼內容標記為 Implementation note，固定對應 2.0.51 tag；正式程式只用 public API。2.1 變更獨立放在 compatibility radar。

### 不穩定的並發與效能實驗

並發測試使用同步屏障與短 timeout 控制順序；效能判斷以查詢數、鎖行為、狀態與 plan shape 為主，wall-clock timing 為輔。

## 14. 後續流程

本設計核准並提交後，下一步使用 `superpowers:writing-plans` 產生分里程碑的詳細實作計畫。實作計畫必須先完成 M1 的檔案、命令、測試與 evidence 介面，再決定是否將 M2–M4 拆成獨立計畫文件。
