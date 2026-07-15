# SQLAlchemy Hands-on：從正確使用到架構決策

## 這不是 API 翻譯

這份教程有三個目標：先學會正確使用 SQLAlchemy，再用可重現的證據解釋機制，
最後把機制轉成可辯護的架構決策。若你正在比較 Python 資料存取方案，請先看
[`../python-data/`](../python-data/)；這裡從選型之後開始，追到 SQL、交易、連線池與
PostgreSQL 行為。

## 執行基線

- Python 3.14
- SQLAlchemy 2.0.51
- PostgreSQL 18.4
- psycopg 3
- uv

## 四卷地圖

M1 的 00–06 是本里程碑的可執行範圍；M2–M4 只標示後續範圍，不代表內容已完成。

### M1 · 起點、Core 與執行管線（00–06）

- [00 · 起點與全景](00-overview/)
- [01 · Engine 解剖](01-engine-execution/)
- [02 · Schema 與型別系統](02-schema-types/)
- [03 · SQL Expression 與 compiler](03-expression-compiler/)
- [04 · 查詢、DML 與 Result](04-core-dml-results/)
- [05 · Connection 與交易狀態機](05-connection-transactions/)
- [06 · 連線池與容量治理](06-pooling-capacity/)

### M2 · ORM 與工作單元（07–12，後續里程碑範圍）

- 07 · Typed Declarative 與 mapping
- 08 · Instrumentation 與物件生命週期
- 09 · Session、Identity Map 與 UoW
- 10 · Relationship 與載入策略
- 11 · ORM 查詢與批量 DML
- 12 · 高階 mapping

### M3 · 生產正確性（13–18，後續里程碑範圍）

- 13 · 服務層交易邊界
- 14 · 並發控制與重試
- 15 · 多租戶隔離
- 16 · 冪等與 Transactional Outbox
- 17 · Async SQLAlchemy
- 18 · Alembic 與零停機演進

### M4 · 效能、可觀測性與架構（19–24，後續里程碑範圍）

- 19 · 讀取效能
- 20 · 寫入效能
- 21 · Events 與可觀測性
- 22 · 測試策略
- 23 · 資料層架構取捨
- 24 · 事故演練與架構面試

## 每章怎麼讀

- `production question`：先定義真實系統要回答的問題。
- `prediction`：執行前先寫下對 SQL、狀態或資源的預測。
- `failing/naive behavior`：先呈現直覺作法如何失敗，建立需要解釋的落差。
- `mechanism`：追蹤公開契約與底層機制如何產生結果。
- `corrected behavior`：用最小修正重跑案例，確認行為符合預測與契約。
- `evidence`：用測試、事件順序與 PostgreSQL 行為留下證據。
- `decision`：把觀察轉成適用條件、代價與架構選擇。
- `interview drill`：用追問檢查能否清楚解釋取捨。

## 五分鐘啟動 M1 Lab

```bash
cd lab
make sync
make db-up
make verify
```

## 與既有教程的邊界

[`python-data/`](../python-data/) 是資料存取工具的選型導讀；本目錄是 SQLAlchemy 深水
教程，聚焦可執行案例、內部機制、生產正確性與架構取捨，而不是重複選型總覽。
