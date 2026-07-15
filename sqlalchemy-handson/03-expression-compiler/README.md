# 03 · SQL Expression 與 compiler：SQL 是結構，不是字串

本章沿用 production question、prediction、failing/naive behavior、mechanism、corrected
behavior、evidence、decision 與 interview drill 八個階段。可執行案例只依賴 SQLAlchemy
2.0 公開 API；涉及版本內部實作的內容會標成 `Implementation note`，並固定在本 lab 的
SQLAlchemy 2.0.51。

## 生產問題：為什麼參數化同時影響安全與效能？

**Production question**：訂單服務依租戶與 SKU 查商品時，為什麼不能把 request value
直接塞進 SQL 字串？最直接的風險是資料被誤當成 SQL 語法：像
`x'; DROP TABLE products; --` 這種值若經由字串拼接進入 statement，可能改變原查詢的
語意。另一個問題是每個值都形成不同 SQL 文字，compiler 與資料庫看到的結構也跟著漂移，
難以把「同一個查詢形狀、不同參數」視為同一類工作。

參數化不是一句「可以防 injection」就結束。它把 SQL 結構與 runtime data 分成兩個
channel：SQLAlchemy compiler 處理 expression tree，Dialect 與 DBAPI 處理 bound value。
同一個結構因此能被 statement compilation cache 辨識。不過本章只證明 cache entry 的結構
重用，沒有量測 latency，也不宣稱每個 workload 都會得到固定幅度的效能提升。

## 先預測，再執行

**Prediction**：執行
[`ch03_expression_compiler.py`](../lab/scenarios/ch03_expression_compiler.py) 前，先寫下可被
測試推翻的預測：

1. PostgreSQL Dialect 編譯後的 SQL 會包含 `tenant_id` 與 `sku` placeholder，不包含 hostile
   SKU 本身。
2. hostile SKU 仍會完整保存在 `compiled.params["sku"]`，證明它沒有被丟棄或手動 escape。
3. 對同一結構執行兩次後，顯式 `compiled_cache` dictionary 只會有一個 entry。
4. 從 factory 建立的兩個等價 `Select` 會編譯出相同 SQL 文字。

**Failing/naive behavior** 是用 f-string、`%` 或 `+` 組 SQL。scenario 只 compile 這個
anti-example、不送進 PostgreSQL，並明確觀察 hostile value 已嵌入 SQL text。手動替單引號加 escape 也不是
修正：escaping 規則屬於 driver、backend 與型別適配邊界，application 很容易漏掉非字串型別、
不同 encoding 或另一條拼接路徑。更安全且可重用的輸入，是 SQLAlchemy expression 加上獨立
parameter mapping。

## Public contract：generative expression、bindparam、compile

**Mechanism — Public contract**：本 lab 的
[`product_by_sku_statement()`](../lab/src/order_service/db/statements.py) 回傳新的 `Select`：

```python
select(
    products.c.id,
    products.c.tenant_id,
    products.c.sku,
    products.c.name,
    products.c.unit_price,
    products.c.attributes,
).where(
    products.c.tenant_id == bindparam("tenant_id"),
    products.c.sku == bindparam("sku"),
)
```

`select()`、`where()`、`bindparam()` 與 `compile()` 都是文件化 API；完整 construct vocabulary
見 [SQL Expression Language Foundational Constructs](https://docs.sqlalchemy.org/en/20/core/expression_api.html)。
SQLAlchemy expression 是 generative：像 `where()` 這類方法回傳帶有新條件的 construct，
不要求 caller 修改共用的 SQL 字串。factory 只描述查詢形狀；實際 `tenant_id`、`sku` 在
`Connection.execute(statement, parameters)` 才進入。

`bindparam("sku")` 代表一個值的位置，不代表任意 SQL token。table name、column name、排序
方向與 keyword 不能當作一般 bound parameter；動態 identifier 必須用 `Table`、`Column` 等
construct 組合，或先通過明確 allowlist。把使用者輸入直接傳給 `text()` 也不會自動把它變成
安全的 identifier。

直接呼叫 `statement.compile(dialect=postgresql.dialect())` 適合測試、說明或診斷 Dialect
輸出；正常執行時由 `Connection`／`Engine` 選擇自己的 Dialect 並完成 compilation。application
不應先自行 compile 成字串再交回 `execute()`。

## Mental model：ClauseElement tree → cache key → SQLCompiler

**Mechanism — Mental model**：一次 Core 查詢可以用下列路徑理解：

```text
Table / Column / BinaryExpression / BindParameter 組成 ClauseElement tree
  → 產生可快取的結構描述
  → Dialect 選擇對應 SQLCompiler
  → PostgreSQL SQL + parameter metadata
  → DBAPI statement channel + parameter channel
  → PostgreSQL
```

cache 關心的是 operator、column、type、label 與 expression arrangement 等會影響編譯結果的
結構，不應把每次 request 的 `tenant_id` 或 `sku` 值當成新 SQL 形狀。Dialect 仍是 cache
邊界的一部分：同一棵 tree 在不同 backend 可能需要不同 placeholder、cast 或 SQL syntax，
不能把某個 PostgreSQL compiled object 當成跨 Dialect 產物。

**Implementation note（只適用 SQLAlchemy 2.0.51）**：`_generate_cache_key()` 是私有方法，
可以在一次性的版本研究中協助觀察 cache-key 內容，但不屬於 application contract。本 lab 的
production module 沒有呼叫它，測試也不把私有 tuple 形狀鎖死；patch/minor upgrade 都可能
改變內部表示。自訂 SQL construct 的公開擴充方式應依
[Custom SQL Constructs and Compilation Extension](https://docs.sqlalchemy.org/en/20/core/compiler.html)
所描述的 `@compiles` 與 cache participation contract，而不是呼叫私有 cache-key API。

## compiled.params 與 DBAPI parameter channel

**Mechanism**：案例先用 `.params()` 附上 hostile value，再針對 PostgreSQL Dialect compile。
結果同時顯示：

```text
WHERE products.tenant_id = %(tenant_id)s::UUID AND products.sku = %(sku)s
compiled.params["sku"] == "x'; DROP TABLE products; --"
```

第一行是 SQL 文字，第二行是與它分離的 Python parameter value。`compiled.params` 很適合在
測試中驗證「值仍在 parameter channel」，但它不是 application 應自行送給 cursor 的低階
協議。真實執行時，Dialect、SQLAlchemy type 與 psycopg 還會依 backend／driver 規則處理
placeholder、bind processor 與參數格式；因此 production code 應把原 statement 與 mapping
交給 `Connection.execute()`。

**Corrected behavior**：repository 或 service 重用 expression factory 所定義的結構，每次
呼叫只傳新的 mapping：

```python
connection.execute(
    product_by_sku_statement(),
    {"tenant_id": tenant_id, "sku": requested_sku},
).one()
```

這個邊界讓 value 的 quoting 與 type adaptation 留在 Dialect／DBAPI，也讓 code review 能直接
看出哪些部分是 SQL structure、哪些是 request data。

## statement cache 的命中與失效

**Evidence**：scenario 透過公開的
`connection.execution_options(compiled_cache=cache)` 注入空 dictionary，對相同 `Select`
與參數執行兩次。真實 PostgreSQL 執行完成後，
[`ch03-expression-compiler.md`](../lab/evidence/ch03-expression-compiler.md) 記錄：
對應的行為測試見 [`test_statements.py`](../lab/tests/unit/test_statements.py) 與
[`test_statement_cache.py`](../lab/tests/integration/test_statement_cache.py)。

- `hostile_value_present_in_sql=False`
- `naive_hostile_value_present_in_sql=True`
- `corrected_hostile_value_present_in_sql=False`
- `bound_sku=x'; DROP TABLE products; --`
- `compiled_cache_entries=1`

一個 entry 是可直接檢查的 cache-cardinality 證據：第二次等價執行沒有為 bound value 再建立
另一個 compiled entry。它不證明 PostgreSQL execution plan 必然相同，也不等同 end-to-end
效能 benchmark。production `Engine` 會管理自己的 SQL compilation cache；顯式 dictionary
只用於隔離本次 lab 觀察，不建議為了讀取內部狀態而取代正常 Engine cache。

cache 會在 statement 結構、Dialect 或會影響 SQL rendering 的 construct state 不同時分開；
包含無法安全描述 cache key 的 custom type／construct 時，SQLAlchemy 會保守地放棄快取。
[SQL compilation caching errors](https://docs.sqlalchemy.org/en/20/errors.html) 說明「不產生
cache key」警告與安全性原則；[Performance FAQ](https://docs.sqlalchemy.org/en/20/faq/performance.html)
則示範如何從 Engine logging 的 cache indicators 判斷 compilation caching 是否生效。先看
結構與 log 證據，再針對真實 workload profile；不要只憑「有 cache」推測瓶頸已消失。

### 架構決策

**Decision**：application 一律以 SQLAlchemy expression 與 bound parameters 組 SQL；共享
statement factory 描述穩定結構，由 Engine 管理 production compilation cache。lab 才注入
顯式 dictionary 量測 cache entry 數量。若查詢真的需要動態 shape，就明確組合有限的
expression branch，而不是把 value 或 identifier 拼成字串。

| 問題 | 採用 | 不採用 | 邊界／代價 |
| --- | --- | --- | --- |
| request value | `bindparam` + execute mapping | f-string、手動 quoting | 只能綁 value，不能綁 identifier |
| query reuse | 穩定 expression factory | 預先 compile 成共用 SQL 字串 | 讓執行中的 Dialect 擁有 compilation |
| cache evidence | 顯式 dictionary 的 entry cardinality | 從單次案例宣稱固定加速 | 結構證據不是 latency benchmark |
| production cache | Engine 管理的 compilation cache | application 讀寫私有 cache key | 內部表示不是相容性契約 |

## TypeDecorator.cache_ok 與自訂 construct

`TypeDecorator` 可能改變 SQL rendering 或 bind behavior，所以 SQLAlchemy 不能假設每個自訂型別
都能安全共享 compiled result。本 lab 的 `Money.cache_ok = True` 表示 `Money` instance 沒有
會改變 emitted SQL 的 mutable constructor state；這是一項由型別作者負責的承諾，不是消除
warning 的快捷鍵。

若 custom type 的 constructor state 會影響 SQL，應先把該 state 正規化為 immutable、可雜湊且
完整描述 SQL 的形式，再評估 `cache_ok=True`；無法保證時維持保守設定。對自訂 ClauseElement
或 compiler extension，也必須依 extension contract 宣告 cache 行為。錯誤地標成可快取，可能
讓不同結構共享不正確的 compiled SQL；沒有標示則通常是跳過 cache 與發出警告，影響面不同但
都應由測試與 profiling 驗證。

**Implementation note（只適用 SQLAlchemy 2.0.51）**：cache-key 內部 tuple、visitor traversal
細節與 compiler class 路徑都是版本實作，不應被 repository code、監控或 business logic
解析。可依賴的是文件化的 `cache_ok`／custom construct cache contract，以及公開 execution
options 與 log 所呈現的行為。

## 方言編譯與 literal_binds 的診斷邊界

PostgreSQL Dialect 在 UUID bind 後輸出 `::UUID`，並使用 psycopg 對應的 placeholder；換成另一
Dialect，rendered SQL 可能不同。這是 Dialect 的責任，不代表 expression factory 必須為每個
backend 維護 SQL 字串分支。

`compile_kwargs={"literal_binds": True}` 可以把部分簡單值 inline，適合產生診斷片段或比較 SQL
shape，但不能當作 production execution path。它不支援所有型別，也會把敏感值放進 SQL／log，
更不能對不受信任輸入產生 SQL 後直接執行。安全證據應像本 lab 一樣檢查正常 compilation 的
SQL 與 params 分離；若為排錯使用 `literal_binds`，必須限制在受控資料並處理遮罩與保存期限。

本章的 decision 因此是：compile 用於理解與測試，execute 仍接收 expression + mapping；cache
用結構 entry、warning、logging 與 workload profile 驗證，不以私有 API 或字面化 SQL 建立
production dependency。

## 面試追問

**Interview drill**：

1. bound parameter 為何能讓 hostile SKU 留在 params、卻不進 SQL text？回答應區分 expression
   compilation 與 DBAPI parameter channel，不能只說「SQLAlchemy 會 escape」。
2. bound parameter 能不能代表 column name？為什麼？回答應指出 parameter 是 value placeholder；
   identifier 屬於 SQL grammar，應使用 construct 或 allowlist。
3. 兩次 execute 後 dictionary 只有一個 entry，證明了什麼、沒有證明什麼？回答應限定為同一
   Dialect 下的 compilation-cache 結構重用，不外推 database plan、latency 或 throughput。
4. `cache_ok=True` 是誰的承諾？錯標可能造成什麼結果？回答應提到 custom type state 是否完整
   決定 emitted SQL，以及錯誤 cache reuse 的 correctness 風險。
5. 為什麼不在 production code 呼叫 `_generate_cache_key()`？回答應指出它是 SQLAlchemy 2.0.51
   的私有實作；application 應依賴公開 cache contract、execution options、logging 與 profiling。
6. `literal_binds` 何時有用，為什麼不能拿來處理 request？回答應涵蓋診斷用途、型別限制、
   敏感資料曝光與不受信任輸入。
