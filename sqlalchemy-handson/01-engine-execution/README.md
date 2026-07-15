# 01 · Engine 解剖：一次 execute 的完整旅程

本章依序走過 production question、prediction、failing/naive behavior、mechanism、
corrected behavior、evidence、decision 與 interview drill。可執行案例只使用同步
SQLAlchemy 2.0 公開 API；版本內部路徑會另外標成 `Implementation note`。

## 生產問題：Engine 應該活多久？

**Production question**：訂單服務每次收到 request 時，應該建立新的 `Engine`，還是讓
同一個 `Engine` 服務多個 request？回答前要先釐清 `Engine` 不是一條已開啟的資料庫
連線。它是連線池與 Dialect 的長生命週期協調者，而一次業務操作真正持有的是
`Connection`。

本章的 production 選擇是：每個 worker process、每個資料庫角色與連線設定建立一個
`Engine`，在 process 內重用。request 進來後才短暫取得 `Connection`，並在明確的
交易邊界結束時歸還資源。不要跨 process 分享已建立連線的 pool；worker 自己擁有並
dispose 自己的 `Engine`。

## 先預測，再執行

**Prediction**：在執行
[`ch01_engine_execution.py`](../lab/scenarios/ch01_engine_execution.py) 前，先寫下兩個
可被推翻的預測：

1. `create_engine()` 只組態 `Engine`、`Pool` 與 `Dialect`，不會立即建立或 checkout
   實體 DBAPI connection。
2. 進入第一次 `engine.connect()` context 時就會觀察到 pool `checkout`；此時尚未呼叫
   `scalar()`／`execute()`，也不會有 `before_cursor_execute`。
3. 隨後執行 SQL 才會觀察到 `before_cursor_execute`；完整事件順序仍是
   `checkout->before_cursor_execute`。

SQLAlchemy 的
[`Engine Configuration`](https://docs.sqlalchemy.org/en/20/core/engines.html) 文件把
這種行為稱為 lazy initialization：第一條實體 DBAPI connection 要等到第一次連線
需求才建立。這不是「Engine 只能用一次」，而是把昂貴的 I/O 延後到真正需要時。

## 事故模式：每請求建立 Engine

**Failing/naive behavior**：若 handler 每次都呼叫 `create_engine()`，每個 request 都會
得到獨立的 pool。原本應由 process 共享的連線重用、上限與健康檢查因此被切碎；高峰期
可能同時建立大量實體連線，request 結束後又丟棄尚可重用的 pool。

`create_engine()` 本身是 lazy，不代表它適合放在 request scope。lazy 只說明「何時
第一次連線」，沒有改變 `Engine` 應承擔 process 級資源治理的責任。

## Public contract：Engine、Connection、Pool、Dialect

**Mechanism — Public contract**：application code 應依賴 SQLAlchemy 文件化的
`Engine.connect()`、`Connection.execute()`／`scalar()`、context manager、transaction
與 event API。完整使用方式見
[`Working with Engines and Connections`](https://docs.sqlalchemy.org/en/20/core/engines_connections.html)。

| 名稱 | 是什麼 | 生命週期與責任 |
| --- | --- | --- |
| `Engine` | `Pool` 與 `Dialect` 的整合入口 | process 內長期重用；依資料庫角色或連線政策分開建立 |
| SQLAlchemy `Connection` | Core 的高階執行與交易介面 | 一次工作單元短暫持有；離開 context 後 close 並歸還資源 |
| checked-out pool resource | pool 暫借給某個 `Connection` 的連線資源 | checkout 到 checkin 之間不能被其他 borrower 同時使用 |
| 實體 DBAPI connection | psycopg 對 PostgreSQL 的實際連線 | 可跨多次 checkout 被 pool 重用；失效時由 pool 丟棄或重建 |
| `Pool` | 實體 DBAPI connection 的容量與重用管理者 | 跟著 `Engine` 存活，處理 checkout、checkin、失效與回收 |
| `Dialect` | PostgreSQL + psycopg 組合的 SQL／型別／執行適配層 | 把 SQLAlchemy construct 編譯成 driver 可執行的 SQL 與參數形式 |

`engine.connect()` 回傳的是 SQLAlchemy `Connection`，不是裸的
`psycopg.Connection`。`Connection.close()` 結束的是本次借用；正常情況下實體連線會
被 checkin 回 pool，供下一個 request 使用，而不是每次都關閉 TCP session。

## Mental model：SQL Expression 到 psycopg cursor

**Mechanism — Mental model**：把一次同步 Core 執行想成以下資料與資源路徑：

```text
engine.connect()
  → Engine（選定 Pool 與 Dialect）
  → Pool checkout（取得可用的 DBAPI connection）
  → 回傳 SQLAlchemy Connection
connection.scalar(text("SELECT :value"), {"value": 42})
  → PostgreSQL/psycopg Dialect（編譯 SQL、調整參數格式）
  → psycopg cursor.execute(statement, parameters)
  → PostgreSQL
  → Result.scalar() == 42
```

這張圖是責任模型，不是可依賴的內部類別呼叫圖。能在 production code 中承諾的是
公開 API 的輸入、輸出、交易與資源生命週期；內部 frame 在 patch release 仍可能改變。

## Implementation note：2.0.51 的執行路徑地圖

**Mechanism — Implementation note（固定 SQLAlchemy 2.0.51）**：本 lab 固定的版本中，
這個 `TextClause` 大致經過 `Connection.execute()`、clause element 執行、編譯、建立
execution context、單次 cursor execution，最後由 Dialect 呼叫 DBAPI
`cursor.execute()`。這段路徑用來解釋觀察，不是 application 可呼叫或 monkey-patch
的契約；升級版本後必須重新執行案例。

案例刻意使用兩個公開 event：pool 的 `checkout` 表示借出資源，Engine 的
`before_cursor_execute` 表示已經有 cursor 與 driver SQL、即將進入 DBAPI。它們證明
兩個邊界的相對順序，但不宣稱暴露兩者之間的每一個內部 call frame。

## 參數綁定不是字串插值

**Mechanism — bound parameters**：案例傳給 SQLAlchemy 的 statement 與 values 是兩個
通道：

```python
connection.scalar(text("SELECT :value"), {"value": 42})
```

SQLAlchemy 接受 `:value`，PostgreSQL/psycopg Dialect 將它編譯成證據中的
`SELECT %(value)s`，而整數 `42` 仍由參數 mapping 交給 psycopg。driver 依型別調整值，
所以 application 不需也不應替字串加引號、做 SQL escaping 或把值拼進 statement。
手動 quoting 會混淆 SQL 語法與資料，也可能重新引入 injection 風險。

bound parameter 只能代表「值」，不能安全地取代表名、欄名或 SQL keyword。動態
identifier 應用 SQLAlchemy 的 `Table`、`Column` 等 construct 表達，或先經過明確的
allowlist。

## Corrected behavior：讓 Engine 跟 process 走

**Corrected behavior**：在 process 啟動或 dependency container 組裝時建立
`Engine`，注入需要存取資料庫的 application service；每個工作單元用
`with engine.connect()` 或 `with engine.begin()` 取得短生命週期 `Connection`。process
關閉時再呼叫 `engine.dispose()`。

測試與 CLI 也遵守同一個邊界：pytest 的 session fixture 建立一次 `Engine`；scenario
只借用 `Connection`；CLI 自己建立的 `Engine` 則在 `finally` 中 dispose。這讓案例與
production decision 使用同一套資源模型。

scenario 會真的建立兩個 naive Engine、各執行一次查詢並確認得到兩個不同 Pool，然後以注入的
同一個 Engine 執行兩個工作單元，確認共用同一 Pool；兩個 naive Engine 都在 `finally` dispose。

## Evidence：事件順序與真實 PostgreSQL 結果

**Evidence**：
[`integration test`](../lab/tests/integration/test_engine_execution_scenario.py) 對真實
PostgreSQL 執行 scenario，要求觀察同時包含：

- `event_order=checkout->before_cursor_execute`
- `checkout_during_connect=True`
- `sql_not_executed_at_checkout=True`
- `naive_distinct_pools=True`
- `corrected_reused_pool=True`
- `result=42`
- `dialect=postgresql`
- `driver=psycopg`

CLI 會把同一個 immutable `Evidence` 寫成
[`ch01-engine-execution.md`](../lab/evidence/ch01-engine-execution.md)。該檔案是執行產物，
不是手寫範例；固定保留 Hypothesis、Setup、Command、Observation、Explanation、Decision、
Caveat 七節，其中 Command 只有一條可重跑命令。事件證據支持本案例的 checkout／execute 順序，但沒有量測整個服務的 pool
容量或 latency；那些問題不能由 `SELECT 42` 外推。

## 架構決策表

**Decision**：

| 問題 | 採用 | 不採用 | 原因／代價 |
| --- | --- | --- | --- |
| Engine lifetime | 每個 worker process、每個 DB role/config 一個長生命週期 `Engine` | 每 request 建立 `Engine` | 集中 pool 容量、重用連線；process shutdown 時要 dispose |
| Connection lifetime | 每個工作單元短暫 checkout，context 結束即歸還 | 全域共享同一個 `Connection` | 交易所有權清楚；每次工作都要正確結束交易與 close |
| SQL values | bound parameters | f-string、拼字串、手動 quoting | 讓 Dialect/driver 負責參數格式與型別適配 |
| 版本內部知識 | 標成 2.0.51 `Implementation note` 並重驗 | 讓 application 依賴私有 method | 可解釋機制，同時避免把可變內部路徑當成契約 |

若 credential、資料庫角色、隔離政策或 execution options 需要獨立治理，可以建立不同
`Engine`；「process-scoped」不是強迫整個 process 只有一個全域 Engine，而是禁止把
它誤降成 request-scoped disposable object。

## 面試追問

**Interview drill**：

1. **Engine lifetime**：為什麼 `create_engine()` 是 lazy，仍不應每個 request 呼叫一次？
   回答應區分「延後第一次 I/O」與「長期擁有 pool 容量／連線重用」兩件事。
2. **Dialect responsibility**：Dialect 在 SQLAlchemy construct 與 psycopg 之間負責什麼？
   回答應涵蓋 backend/driver SQL、參數格式與型別／執行適配，但不要把它說成業務交易
   所有者。
3. **Bound parameters**：為什麼 `:value` 不需要 application 手動加引號？回答應指出
   statement 與 values 分開傳給 DBAPI，quoting／adaptation 由 Dialect 與 driver 處理；
   同時補充 bound parameter 不能代表 identifier。
