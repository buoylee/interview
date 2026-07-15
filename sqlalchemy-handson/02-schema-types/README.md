# 02 · Schema 與型別系統：讓約束成為架構的一部分

本章沿用 production question、prediction、failing/naive behavior、mechanism、corrected
behavior、evidence、decision 與 interview drill 八個階段。可執行的完整定義在
[`schema.py`](../lab/src/order_service/db/schema.py)，只使用 SQLAlchemy 2.0 Core 公開 API。

## 生產問題：哪些 invariant 必須下沉到資料庫？

**Production question**：order service 已在 application layer 驗證價格、庫存與租戶，
為什麼資料庫仍要有 `CHECK`、`UNIQUE`、`FOREIGN KEY`？因為所有寫入路徑不一定共享同一段
Python：重試、批次程式、維運 SQL，以及兩個同時通過 application 驗證的 transaction，
最後都會在資料庫交會。只靠「先查再寫」無法封閉 concurrent write 的競爭窗口。

本章把不隨單一 use case 改變的 invariant 下沉：金額非負、數量為正、狀態屬於已知集合、
同租戶 SKU 唯一，以及 child row 的 tenant 與 parent tenant 必須一致。資料庫負責拒絕不合法
state；application 仍負責把 constraint violation 翻譯成領域錯誤，不能把 PostgreSQL 訊息原樣
洩漏給 caller。

## 先預測，再執行

**Prediction**：執行
[`ch02_schema_types.py`](../lab/scenarios/ch02_schema_types.py) 前，先寫下可被真實 PostgreSQL
推翻的預測：

1. `metadata.create_all()` 會建立且只建立八張表。
2. `products(tenant_id, sku)` 的 unique constraint 名稱會是
   `uq_products_tenant_id_sku`。
3. PostgreSQL reflection 會把 `products.attributes` 報告為 `JSONB`，並看見 partial index
   `ix_outbox_events_claimable`。
4. `Money` 會以 half-even 將 `Decimal("12.345")` 量化為 `Decimal("12.34")`，float 則被
   拒絕。

這些預測分別由
[`unit contract test`](../lab/tests/unit/test_schema_contract.py) 與
[`PostgreSQL integration test`](../lab/tests/integration/test_schema.py) 固定。先預測的目的不是
猜對，而是把「schema 應該保證什麼」寫成可失敗的 contract。

## Public contract：MetaData、Table、Column、constraint

**Mechanism — Public contract**：[`MetaData`](https://docs.sqlalchemy.org/en/20/core/metadata.html)
是 schema object 的 registry；八個具名 `Table` 是可供 statement、migration 與測試共用的
Python contract。`Column` 同時描述 SQL 型別、nullability、server default 與 key membership；
`PrimaryKeyConstraint`、`ForeignKeyConstraint`、`UniqueConstraint`、`CheckConstraint` 與
`Index` 則描述跨欄位規則及存取路徑。

本 lab 輸出單一 `metadata` 以及八個 table object：`tenants`、`products`、`inventories`、
`orders`、`order_lines`、`inventory_reservations`、`idempotency_records`、
`outbox_events`。這裡刻意不用 ORM model；Core schema 已足以成為 SQL expression 與 DDL 的
共同詞彙，也避免把 schema invariant 誤認成 object lifecycle 行為。

`server_default` 是 PostgreSQL 在未提供欄位時執行的 default，不是 Python 在 statement
送出前填值。時間欄位使用 timezone-aware `DateTime` 搭配 `now()`，因此非 Python 寫入路徑
仍得到一致的 database-side default。

## 命名慣例與可操作的 IntegrityError

**Failing/naive behavior**：不命名 constraint 時，名稱可能由 database 或 migration 工具
臨時產生。application 捕捉到 `IntegrityError` 後只能比對易變的 message，migration 也難以
穩定 `DROP CONSTRAINT`。更危險的 naive 修正是捕捉所有 integrity error 後一律回覆「資料
重複」；foreign key、check 與 unique violation 的語義並不相同。

`MetaData.naming_convention` 讓 `pk_products`、`uq_products_tenant_id_sku`、
`ck_products_unit_price_nonnegative` 等名稱由 table、column 與 constraint token
決定。constraint name 因此是 error-handling contract 的一部分：之後的 translation layer
可以讀取 driver 提供的 constraint name，映射成穩定的 domain error。名稱是穩定 handle，
但 application 仍應保留未知 constraint 的 fallback，因為 schema 與應用程式可能短暫處於
不同部署版本。

partial index `ix_outbox_events_claimable` 只涵蓋 `status = 'pending'` 的 `available_at`。
它表達 worker 的 claim 查詢路徑，不等同 uniqueness 或 business invariant；明確命名則讓
execution plan、維運與 migration 討論能指向同一個 object。

## Python 型別、SQLAlchemy 型別、PostgreSQL 型別

同一欄資料經過三個型別邊界：Python value、SQLAlchemy `TypeEngine`，以及 PostgreSQL
column type。SQLAlchemy 的
[`Core type basics`](https://docs.sqlalchemy.org/en/20/core/type_basics.html) 說明 portable
型別如何選擇 bind/result behavior；Dialect 再把它編譯成 PostgreSQL 能理解的 DDL 與 driver
參數。

例如 `Uuid(as_uuid=True)` 的 Python contract 是 `uuid.UUID`，資料庫端是原生 `UUID`；
`Money` 的 Python contract 是 `Decimal`，其底層 SQL 型別是 `NUMERIC(12, 2)`。型別宣告不是
單純文件，它會參與 DDL、statement compilation、bind processing、result processing 與
reflection，所以不應在 repository 裡繞過它手動轉字串。

## Money TypeDecorator 與 cache_ok

**Corrected behavior**：`Money` 依
[`TypeDecorator`](https://docs.sqlalchemy.org/en/20/core/custom_types.html) 擴充
`Numeric(12, 2)` 的 bind boundary。它只接受 `Decimal` 或 `None`，並在送入 driver 前以
`ROUND_HALF_EVEN` 量化到兩位小數。集中處理可避免每個 use case 自己選 rounding mode。

float 被拒絕，因為它以 binary floating-point 表示；許多十進位金額不能精確表示，先建立
float 再轉成 `Decimal` 可能把近似誤差帶進 rounding 決策。要求 caller 從十進位字串或其他
精確來源建立 `Decimal`，讓 cent-level 規則的輸入可預測。這個拒絕不是說 PostgreSQL
`NUMERIC` 不精確，而是保護 Python 到 bind processor 之間的資料來源。

`cache_ok = True` 宣告此 type instance 不含會改變 SQL compilation 的 mutable state，
因此可安全參與 SQLAlchemy statement cache。若 custom type 的 constructor state 會影響
rendered SQL，便不能無條件使用這個宣告。

## UUID、timezone、JSONB、Enum 的取捨

UUID 適合由多個 process 先行產生 identifier，也避免 sequence 暴露總量；代價是 index 較大，
且完全隨機的值可能降低 locality。timezone-aware timestamp 保存時間線上的 instant；顯示用
timezone 應在 system boundary 轉換，不靠無 timezone timestamp 猜測。

`JSONB` 是明確的 PostgreSQL 決策，而非 portable JSON 抽象。本 lab 的 `attributes` 與
`payload` 需要 PostgreSQL JSONB 的儲存、operator 與 indexing 生態，因此直接 import
PostgreSQL Dialect 型別，讓 backend coupling 可見。詳細型別與 partial-index options 見
[`PostgreSQL dialect`](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)。代價是這份
metadata 不能假設在 SQLite 等 backend 原樣建立；integration test 所以必須使用真實
PostgreSQL。

狀態欄目前採 `String` 加具名 `CHECK`，因為 lab 之後會演示狀態演進與 constraint error
translation。原生 PostgreSQL `ENUM` 能提供強型別，但增加獨立 type object 的 migration
lifecycle；Python `Enum` 又是另一個 application boundary。這不是普遍否定 Enum，而是目前
選擇較容易演進、且仍由 database 封閉合法集合的策略。

## 多租戶 composite constraint

只讓 `order_lines.product_id` 指向 `products.id`，無法證明 line 與 product 屬於同一租戶。
因此 `products` 額外保證 `(tenant_id, id)` 唯一，child 再用
`(tenant_id, product_id)` composite foreign key 引用它；order、inventory 與 reservation
採同樣模式。租戶 ID 不是只有 query filter，而是 relationship key 的一部分。

這層約束防止錯誤或被繞過的 application filter 寫出 cross-tenant reference。不過它不會
自動替每個 `SELECT` 加 tenant predicate，也不取代 authorization。讀取隔離仍由 repository
API、request context 與測試負責；需要更強的 defense-in-depth 時可另外評估 PostgreSQL
Row-Level Security。

## create_all 只屬於 Lab

**Evidence**：scenario 在自己擁有的 `engine.begin()` transaction boundary 中先 drop 再
create，接著只透過 inspector 讀回結果；pytest 的 function-scoped `recreated_schema` fixture
也在 setup／teardown 各自開啟並結束 transaction，不把 transaction ownership 隱藏到
repository API。實際輸出保存在
[`ch02-schema-types.md`](../lab/evidence/ch02-schema-types.md)：目前真實 PostgreSQL 回報八張
表、`uq_products_tenant_id_sku` 與 `ix_outbox_events_claimable`。

`create_all()` 適合可丟棄 lab、測試 bootstrap 與本章的 reflection evidence；它不是生產
schema evolution 策略。它不會表達 production migration 的版本順序、data backfill、
online DDL 風險或 rollback 決策。M3 將由 Alembic 擁有這些責任。

**Decision**：採用具名 database constraint、Decimal-backed `Money`、原生 UUID、timezone
timestamp、明確的 PostgreSQL JSONB，以及 tenant-aware composite foreign key；保留
`create_all()` 給 lab。代價是 schema 更接近 PostgreSQL，且 constraint 變更必須被當成
application error contract 與 migration 的協同變更，而不是私下修改 DDL。

## 面試追問

**Interview drill**：

1. 為什麼 application 已驗證 `quantity > 0`，資料庫仍要 `CHECK`？回答應涵蓋其他寫入
   路徑、concurrency 與 invariant 的最後防線，而不是說「不信任 application」就結束。
2. 為什麼 constraint name 屬於 error-handling contract？回答應說明如何從 driver diagnostic
   映射 domain error、為何不能比對完整 message，以及如何處理未知名稱。
3. 為什麼 money 拒絕 float？回答應區分 binary floating-point 的輸入近似、Decimal 的十進位
   語義，以及 PostgreSQL `NUMERIC(12, 2)` 的 storage constraint。
4. `JSONB` 帶來什麼承諾？回答應指出 operator/indexing 能力與 PostgreSQL coupling，並解釋
   為何 SQLite 測試不能替代 dialect integration test。
5. composite foreign key 解決了哪個 tenant 問題，又沒有解決什麼？回答應同時說明
   cross-tenant write protection、read predicate 與 authorization boundary。
