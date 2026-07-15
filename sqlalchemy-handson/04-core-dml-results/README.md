# 04 · Core 查詢、DML 與 Result：控制 SQL，也控制回傳形狀

本章沿用前面章節的八階段教學流程，但仍保持 brief 指定的主題順序。案例使用公開 API
與真實 PostgreSQL；production function 接受 caller 提供的 `Connection`，可以 `execute()`，
但不會自行 `begin()` 或 `commit()`。application-service entry point 才擁有交易邊界。
本章驗證環境固定為 SQLAlchemy 2.0.51、psycopg 3.3.4 與 PostgreSQL 18.4；任何依賴方言、
driver 或版本的觀察都會另外標示。

先釐清定位：SQLAlchemy Core 與 ORM 共用同一個 `Engine`、`Connection`、Dialect 與 SQL
expression system。Core 不是較低品質的 fallback；當問題的主要抽象是明確 SQL shape、批次
DML、dialect-specific upsert 或 set-oriented report 時，Core 往往是較直接的介面。ORM 則在
identity map、relationship 與 unit of work 是主要問題時更合適，兩者也可以存在同一個服務中。

**Public contract**：本章的 production contract 全部位於
[`catalog.py`](../lab/src/order_service/core/catalog.py)：

- [`create_tenant()`](../lab/src/order_service/core/catalog.py) 只執行 tenant INSERT。
- [`upsert_product()`](../lab/src/order_service/core/catalog.py) 以租戶與 SKU 衝突鍵 upsert，回傳
  [`ProductRecord`](../lab/src/order_service/core/catalog.py)。
- [`replenish_inventory()`](../lab/src/order_service/core/catalog.py) 原子累加庫存與版本，回傳
  [`InventoryRecord`](../lab/src/order_service/core/catalog.py)。
- [`inventory_report()`](../lab/src/order_service/core/catalog.py) 以 JOIN、CTE 與 window aggregate
  建立租戶庫存報表。

兩個 record 都是 `frozen=True, slots=True` 的 dataclass。不可變的是 application 看見的欄位
綁定；`ProductRecord.attributes` 的型別是唯讀介面 `Mapping`，caller 不應把它視為可持久化的
mutable entity。

## 生產問題：何時 Core 比 ORM 更直接？

**production question**：商品目錄要同時處理租戶隔離、相同 tenant/SKU 的 upsert、庫存原子
累加，以及每租戶總庫存價值，應該先建立 ORM object graph，還是直接描述 SQL？

這裡的 correctness rule 都落在 statement shape：product conflict target 必須是
`(tenant_id, sku)`；inventory conflict target 必須是 `(tenant_id, product_id)`；既有 product
的 identity 不能被第二次請求帶來的新 UUID 改掉；可用量與 `version` 必須由資料庫在同一個
statement 中累加；報表也必須在 JOIN 與 filter 的每個路徑保留 tenant key。這些規則用 Core
expression 可以直接 review，而不必先經過物件生命週期。

Core 不會自動賦予租戶安全。漏掉 `tenant_id` 條件仍然會洩漏資料；把 tenant filter 只放在
application 的後處理也太晚。租戶欄位必須出現在 conflict target、JOIN predicate 與 report
filter。本章的 PostgreSQL integration test 會建立兩個租戶與相同 SKU，證明資料沒有互相覆蓋。

## 先預測，再執行

**prediction**：執行
[`ch04_core_dml_results.py`](../lab/scenarios/ch04_core_dml_results.py) 前，先寫下可被 PostgreSQL
結果推翻的預測：

1. 把兩個 parameter mapping 交給同一個 tenant `Insert`，會走一次 executemany statement
   shape，觀察到兩筆受影響資料。
2. 同租戶、同 SKU 第二次 upsert 會更新 name、unit price 與 attributes，但 `RETURNING id`
   仍是第一次提供的 product UUID。
3. 庫存先補 3、再補 5 後，`available=8`，且兩次成功寫入使 `version=2`。
4. 第一個 product 的庫存值是 `8 × 12.50 = 100.00`，第二個是 `6 × 5.00 = 30.00`；
   report 保留兩列，而且兩列的 tenant window total 都是 `130.00`。
5. 另一個 tenant 不會出現在本租戶 report，也不會因相同 SKU 成為 product upsert conflict。
6. caller rollback 後 tenant、product 與 inventory 都是零筆，證明 lower-level catalog function
   沒有偷走交易 ownership。

測試入口是 [`test_catalog.py`](../lab/tests/integration/test_catalog.py)，其中每個測試都使用真實
PostgreSQL：

- [`test_product_upsert_returns_existing_identity_and_updated_values`](../lab/tests/integration/test_catalog.py)
  驗證 conflict update、`RETURNING` shape 與 frozen product record。
- [`test_product_upsert_conflict_key_is_scoped_by_tenant`](../lab/tests/integration/test_catalog.py)
  驗證相同 SKU 在兩個 tenant 下仍是兩個 identity。
- [`test_inventory_upsert_and_report_are_tenant_scoped`](../lab/tests/integration/test_catalog.py)
  驗證累加、版本、window total 與跨租戶隔離。
- [`test_catalog_operations_leave_transaction_ownership_to_caller`](../lab/tests/integration/test_catalog.py)
  明確 rollback caller transaction，驗證 catalog 沒有 commit。
- [`test_core_dml_scenario_records_expected_result_shapes`](../lab/tests/integration/test_catalog.py)
  鎖定原始六行加上 window proof 的八行 observation contract。

## SELECT、JOIN、subquery、CTE、window function

**failing/naive behavior**：若 target tenant 只有一個 product，`window sum == row stock value`；
即使實作誤把逐列 `stock_value` 當成 window total，測試仍會通過。另一個錯誤是先把跨租戶資料
全部查回 Python，再做 JOIN、filter 與加總；這讓資料隔離與 aggregation semantics 離開 SQL
review 邊界，也增加不必要的資料傳輸。

**mechanism** — **Public contract**：`inventory_report()` 先以 `select()` 將 inventory 與 product
JOIN。JOIN 不只比對
`product_id`，也比對 `tenant_id`；這與 schema 的 composite foreign key 相同，避免把一個租戶
的庫存接到另一租戶的商品。每列先計算：

```text
stock_value = (available - reserved) * unit_price
```

**Mental model**：inventory/product JOIN 產生逐商品值，CTE 命名這個 relation，tenant filter
限制可見 partition，window aggregate 在不壓縮列數的前提下把 combined total 附到每一列，
最後才轉成 immutable records。

接著 `.cte("stock")` 把 tenant、product、SKU、數量、版本與列價值命名成可再次 SELECT 的
relation。CTE 與 subquery 都能包住一個 selectable；subquery 通常出現在 `FROM (...) AS name`，
CTE 則通常出現在 `WITH name AS (...)`。本例選 CTE 是為了讓「先建立逐商品 stock，再做租戶
window total」的兩層意圖可讀，不是宣稱 PostgreSQL 一定會 materialize 或一定更快。SQLAlchemy
的 selectable、subquery 與 CTE 公開契約見
[SELECT and Related Constructs](https://docs.sqlalchemy.org/en/20/core/selectable.html)。

外層使用：

```python
func.sum(stock.c.stock_value).over(
    partition_by=stock.c.tenant_id
).label("tenant_stock_value")
```

一般 `GROUP BY tenant_id` 會把多個商品壓成一列；window aggregate 保留每一個 product row，
同時把該 tenant 的總值附在每列。外層 `.where(stock.c.tenant_id == tenant_id)` 是不可省略的
租戶邊界，`.order_by(stock.c.sku)` 則讓 report 的列順序可預測。若要同時服務多租戶的 admin
報表，應建立另一個有明確授權語意的 function，而不是令 tenant parameter 可選。

## INSERT／UPDATE／DELETE 與 executemany

同一類 naive DML 是把 Python list 逐列迴圈，每列各呼叫一次 `execute()`；或先 SELECT 目前
庫存、在 Python 加 quantity，再 UPDATE。前者把一個 set-oriented 意圖拆成多次 round trip；
後者在兩個 writer 同時讀到舊值時可能 lost update。lower-level function 自行 commit 也會令
application service 無法把 tenant、product、inventory 與後續工作放在同一個原子交易。

依前述 public contract，`create_tenant()` 示範單筆 `INSERT`。scenario 則把同一個
`tenants.insert()` 與兩個同 shape 的 mapping 一次傳給 `Connection.execute()`；parameter
sequence 表達 executemany，而不是兩次 application-level execute。DML constructors、
execution-time parameter set 與 `RETURNING` 的契約見
[Insert, Updates, Deletes](https://docs.sqlalchemy.org/en/20/core/dml.html)，執行與
`preserve_rowcount` 見
[Working with Engines and Connections](https://docs.sqlalchemy.org/en/20/core/connections.html)。

**Implementation note（SQLAlchemy 2.0.51／psycopg 3.3.4）**：本 lab 的 scenario 設定
`preserve_rowcount=True`，讓 SQLAlchemy 在 non-row-returning INSERT cursor 關閉前保存本次
driver 提供的 rowcount，因而留下可重現的 `2`。execution option 本身是 public API，但
executemany 是否提供可加總 rowcount、RETURNING 是否回傳 `-1`，都依 DBAPI、statement shape
與版本而異；這不是跨 driver 或跨版本的 business contract。

本 slice 沒有 product UPDATE 或 DELETE function，但 Core 的 `update(table).where(...).values(...)`
與 `delete(table).where(...)` 仍遵守相同原則：每個 tenant-owned table 的 WHERE 都必須帶
`tenant_id`；應先決定 0 row、1 row 或多 row 各代表什麼，再選 `rowcount`、`RETURNING` 或後續
Result cardinality assertion。不要因 API 可以執行無條件 UPDATE/DELETE，就讓租戶條件成為
caller 可忘記的選項。

## PostgreSQL RETURNING 與 ON CONFLICT

**corrected behavior**：`upsert_product()` 使用 PostgreSQL-specific dialect `insert()`，並指定 named
constraint `uq_products_tenant_id_sku`。第一次沒有 conflict 時插入 caller 提供的 `product_id`；
第二次同 tenant/SKU conflict 時，`set_` 只從 `excluded` row 更新 `name`、`unit_price` 與
`attributes`，刻意不更新 `id`、`tenant_id` 或 `sku`。所以第二次請求即使帶新 UUID，既有
identity 仍被保留。

`RETURNING` 在同一個 DML statement 回傳寫入後的 id、tenant、SKU、name、price 與 attributes；
conflict update 分支回傳的是更新後既有 row，不需要再用 SKU 做一次 SELECT。這同時減少一個
round trip，也避免「寫入後 lookup 的條件或交易時點不同」造成 shape 漂移。SQLAlchemy 的
PostgreSQL `Insert.on_conflict_do_update()`、constraint/index inference 與 `excluded` namespace
見 [PostgreSQL dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)。

`replenish_inventory()` 的 conflict target 是 `(tenant_id, product_id)`，update expression 是
資料庫內目前值加上 excluded quantity：

```text
available = inventories.available + excluded.available
version   = inventories.version + 1
```

這是一個 atomic upsert，不是 SELECT-then-UPDATE。它確保單一 statement 不會因 application
read/modify/write 覆寫另一個已提交的累加；更高階的 contention、isolation level 與 retry policy
仍應由後續交易章節處理。upsert 只定義 conflict 發生時怎麼寫，不等於所有跨 statement invariant
都自動安全。

## Result、Row、mappings、scalars、one 的語義

**evidence**：真實 PostgreSQL integration test 讓同一個 target tenant 擁有兩個 product，
逐列庫存值分別是 `40.00` 與 `15.00`；兩個回傳 record 都帶 `55.00`，另一個 tenant 的
`700.00` 不會進入 partition。scenario 也要求兩個 report row 都帶 combined `130.00`，因此
測試能區分真正的 window aggregate 與單純逐列值。

每個 statement 先明確選擇回傳欄位，再立刻選擇 Result consumption shape。catalog 的單列
DML 使用：

```python
row = connection.execute(statement).mappings().one()
```

`Result` 是 execution 的可消耗結果；`Row` 預設同時有 positional/tuple-like 行為與 mapping
view。`.mappings()` 讓後續每列直接成為 `RowMapping`，因此轉換成 `ProductRecord` 或
`InventoryRecord` 時可用欄位名稱，reviewer 也能把 `RETURNING`／SELECT 欄位與 record constructor
逐一對照。

`.one()` 不是「拿第一筆」：它要求恰好一列，零列會拋 `NoResultFound`，多列會拋
`MultipleResultsFound`。這正符合 upsert 的 cardinality invariant。`.first()` 只取第一列，會
隱藏意外重複；`.one_or_none()` 適合 0 或 1 都合法的 lookup。`.scalars()` 則把每列投影成第一個
column 的 scalar stream；例如只 select product id 時很好用，但拿它消費多欄 product row 會
丟失其餘 shape。Result、Row、mappings、scalars 與 one 的公開語義都在
[Working with Engines and Connections](https://docs.sqlalchemy.org/en/20/core/connections.html)。

`inventory_report()` 需要多列，所以迭代 `connection.execute(statement).mappings()` 並在
connection/transaction scope 內 materialize 成 `list[InventoryRecord]`。catalog 不把尚未消耗
的 cursor-bearing Result 傳出 boundary，也不讓 application service 依賴 column position。
若結果很大，應另外設計 streaming、partition size 與 connection lifetime；不能只是把 list
改成 iterator，卻在 caller 讀取前關閉 connection。

交易 ownership 也屬於 Result correctness。scenario 的 `with engine.begin()` 是 application
entry point，catalog function 只使用傳入的 connection。rollback integration test 先完成三次
lower-level 寫入，再由 caller rollback，最後查到三張表都是零筆；這是「沒有 commit」的可執行
證據，而不只是一條 coding convention。

## 批量不是逐列迴圈

[`ch04-core-dml-results.md`](../lab/evidence/ch04-core-dml-results.md) 是 scenario
寫出的固定 observation contract：

```text
executemany_tenant_rows=2
upsert_preserved_product_id=True
returned_product_name=Updated
inventory_available=8
inventory_version=2
tenant_stock_value=100.00
tenant_report_rows=2
tenant_stock_values=130.00,130.00
```

在本章固定環境中，第一行表示保存 rowcount 後看見兩筆 tenant insert；它不證明 network
packet 數、server plan 或其他 DBAPI 都會回傳 `2`。`tenant_stock_value=100.00` 保留 brief
要求的原始單商品觀察；最後兩行再提供較強的 window proof：report 有兩列，而兩列都帶
`100.00 + 30.00 = 130.00`；若只是逐列 stock value，會得到 `100.00,30.00`。

「批量」的核心是把 parameter sets 或 set operation 交給資料庫邊界，不是在 Python loop 中
重複單列 statement。真正的大批量仍要量測 parameter/page size、driver strategy、transaction
長度、lock footprint、錯誤定位與 retry granularity。單次塞入無上限資料也不是正確答案；應依
workload 設定 chunk，並讓整批是否需要原子性由 application use case 決定。

## 方言能力與可攜性成本

**decision**：本服務明確採 PostgreSQL，因此 catalog 可以使用 `postgresql.insert()`、
`ON CONFLICT`、constraint name、`excluded`、`RETURNING` 與 schema 中的 JSONB。這些能力讓
identity-preserving product upsert 與 atomic inventory increment 直接且可 review，收益高於
假裝所有 backend 完全相同。

代價是 migration constraint name 與 application statement 已形成契約；若 constraint 改名，
upsert 必須一起改。換資料庫時也不能只改 URL：要重新設計 conflict syntax、RETURNING support、
JSON type、rowcount 與 batch behavior，並用該 backend 的 integration test 重建證據。通用 Core
expression 能提高共用程度，但不會消除 backend semantics。

| 問題 | 採用 | 不採用 | 邊界／代價 |
| --- | --- | --- | --- |
| product upsert | tenant/SKU named constraint + `excluded` | application 先查再決定 INSERT/UPDATE | PostgreSQL-specific；constraint name 是契約 |
| inventory replenish | composite conflict target 的原子加法 | Python read/modify/write | 仍需交易與 retry policy |
| DML return shape | 明確 `RETURNING` + `mappings().one()` | 寫完後再做模糊 lookup | backend support 不一致 |
| report | tenant JOIN + CTE + window aggregate | 全租戶查出後由 Python filter | window total 會重複在每個 product row |
| transaction | application service 擁有 begin/commit/rollback | catalog function 自行 commit | caller 必須提供有效 Connection scope |
| batch evidence | parameter sequence + bounded chunks | application 逐列 round trip | rowcount 不是跨 DBAPI business invariant |

## 面試追問

**interview drill**：

1. 為什麼 product upsert 第二次傳入新 UUID，`RETURNING` 還是原 UUID？回答應指出 conflict
   target 是 tenant/SKU，且 `set_` 沒有更新 id。
2. 若 conflict target 只有 SKU，會發生什麼租戶問題？回答應說明跨 tenant 相同 SKU 可能互相
   conflict；租戶 key 必須存在於 uniqueness 與 statement semantics。
3. 為什麼 `available = current + excluded` 比 SELECT 後在 Python 加總安全？回答應區分單一
   atomic DML 與有 race window 的 read/modify/write，也要承認 retry/isolation 仍是另一層問題。
4. window `sum()` 與 `GROUP BY` 的輸出 shape 有何不同？回答應指出 window 保留逐 product row，
   group aggregate 會改變 cardinality。
5. `.mappings().one()` 各解決什麼問題？回答應分別說明 name-based row shape 與 exactly-one
   cardinality assertion，不能只說「比較方便」。
6. executemany 的 `rowcount=2` 能否當作可攜 business invariant？為什麼？回答應提到 DBAPI、
   cursor memoization、RETURNING 與 multi-parameter 差異。
7. 為什麼 catalog function 不 commit？回答應從 application use case 的原子交易邊界、rollback
   測試與 composability 解釋，而不是只背「repository 不該 commit」。
8. Core 是否比 ORM 更底層、所以品質較差？回答應指出兩者共用 Engine 與 expression system；
   選擇依據是主要抽象與生命週期需求，不是品質等級。
