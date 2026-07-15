# 05 · Connection 與交易狀態機：沒有「不在交易裡」的寫入

本章把「application service 擁有交易」從口頭慣例變成可執行契約。案例使用 SQLAlchemy
2.0.51、psycopg 3.3.4 與 PostgreSQL 18.4；production code 只使用 SQLAlchemy 2.0 公開 API。
driver 與 PostgreSQL 特有的觀察會標成 **Implementation note**，不冒充跨資料庫保證。

核心案例是
[`register_product_with_stock()`](../lab/src/order_service/application/catalog_service.py)：一次 use
case 要建立 tenant、upsert product、補入 inventory。application-service entry point 接受長生命週期
`Engine`，在單一 `with engine.begin()` 中取得短生命週期 `Connection`，所有 lower-level Core
function 都只接受這個 connection，不得自行結束 caller 的交易。

本章的公開參考是 SQLAlchemy 官方
[Working with Transactions and the DBAPI](https://docs.sqlalchemy.org/en/20/tutorial/dbapi_transactions.html)
與
[Engine and Connection Use](https://docs.sqlalchemy.org/en/20/core/engines_connections.html)。前者建立
DBAPI implicit transaction、commit-as-you-go 與 begin-once 的入門模型；後者是 Engine、Connection、
Transaction 與 isolation/autocommit 的完整 API 索引。

## 生產問題：commit 到底應該由誰呼叫？

**production question**：註冊商品庫存需要依序寫入 tenant、product、inventory。若第三步失敗，
前兩步應留在資料庫，還是三步一起消失？誰有足夠資訊做這個決定？

只有 application service 知道「三個 lower-level operation 合起來是一個業務操作」。
`create_tenant()` 不知道後面還要建立 product；`upsert_product()` 也不知道 inventory 是不是同一個
成功條件。因此交易邊界不能由最先完成的 lower-level function 決定。正確 ownership 是：

```text
application service
  └─ Engine.begin()：一個 use case 的 commit／rollback 邊界
       ├─ create_tenant(Connection)
       ├─ upsert_product(Connection)
       └─ replenish_inventory(Connection)
```

成功離開 block 時，context manager commit 三筆寫入；任何一步把例外傳出 block，context manager
rollback 整個 root transaction。這不是「service layer 通常這樣寫」的偏好，而是由
[`test_application_service_commits_the_complete_operation`](../lab/tests/integration/test_transactions.py)
與
[`test_application_service_rolls_back_every_prior_write`](../lab/tests/integration/test_transactions.py)
在真實 PostgreSQL 上鎖定的行為。

## 先預測，再執行

**prediction**：執行
[`ch05_connection_transactions.py`](../lab/scenarios/ch05_connection_transactions.py) 前，先寫下能被
結果推翻的預測：

1. fresh `Connection` 尚未執行 SQL 時，`in_transaction()` 是 `False`；第一次 `SELECT` 後是
   `True`，因為 execute 觸發 autobegin。
2. `with engine.begin()` 內先 INSERT、再拋出 exception，離開 block 後該 row 數量是零。
3. PostgreSQL root transaction 發生 unique violation 後仍有 transaction object，但後續
   `SELECT 1` 會失敗；只有 rollback 後，同一個 `Connection` 才能再次執行。
4. duplicate INSERT 若被 `begin_nested()` 的 savepoint 包住，只 rollback 該 savepoint；outer
   transaction 先前寫入的 row 仍可 commit。
5. application service 正常回傳後 product 與 inventory 都可由另一個 connection 看見；在
   product 後注入失敗時 tenant 與 product 都不可見。

scenario test 是
[`test_transaction_scenario_records_autobegin_and_savepoint`](../lab/tests/integration/test_transactions.py)，
它鎖定八個 observation key，而不是比對 echo log。`Connection.in_transaction()`、
`rollback()`、`begin_nested()` 與 `Engine.begin()` 都是公開 API；log wording 不是本 lab 的 contract。

## Public contract：autobegin、commit-as-you-go、begin-once

**failing/naive behavior**：最危險的寫法是 lower-level function 自行 commit：

```python
def create_product(connection: Connection, values: dict[str, object]) -> None:
    connection.execute(products.insert().values(**values))
    connection.commit()  # anti-example：偷走 caller 的交易所有權
```

假設 application service 先建立 tenant，再呼叫這個 function，最後補 inventory。上面的
`commit()` 不只 commit product，也會 commit 同一個 root transaction 中更早的 tenant INSERT。
若 inventory 接著失敗，caller 的 rollback 只能撤銷 commit 之後的新 transaction，已提交的
tenant/product 無法收回；原本「三步全成或全敗」被 lower layer 靜默切成兩段。這就是破壞 caller
atomicity，而不只是分層風格不一致。

SQLAlchemy 2.0 提供兩種公開使用模式：

- commit-as-you-go：`with engine.connect()` 取得 connection；第一次 execute autobegin，caller
  在需要的時點呼叫 `connection.commit()` 或 `connection.rollback()`。結束後下一次 execute 又
  autobegin 新交易。適合交易切點本來就是明確流程資料的低階 orchestration。
- begin-once：`with engine.begin()` 一開始宣告整個 block 是一個交易；正常離開 commit，例外離開
  rollback。它讓 use-case 意圖與 Python scope 對齊，本章 application service 採用此模式。

`RegisterStockCommand` 是 frozen、slotted input DTO；`quantity <= 0` 在取得 connection 前就拒絕，
避免為確定無效的命令建立交易。公開 entry point 是：

```python
register_product_with_stock(
    engine: Engine,
    command: RegisterStockCommand,
) -> InventoryRecord
```

它是這個 use case 唯一的 transaction owner。`Engine` 本身不是一筆交易；它是 connection factory
與 pool facade，可以跨 request 共用。每次 service call 才從 engine 取得一個 scoped connection。

## Connection、Transaction、NestedTransaction 的狀態

**mechanism**：把三個物件分清楚，交易 state machine 才不會只剩 `try/except` 印象：

| 物件 | 代表什麼 | 何時結束 |
| --- | --- | --- |
| `Connection` | 對一個 checked-out DBAPI connection 的 SQLAlchemy facade | `close()` 或 context manager 離開；未結束交易會 rollback |
| root `Transaction` | connection 上目前的 DBAPI transaction 範圍 | root commit 或 root rollback |
| `NestedTransaction` | root transaction 內的一個 SAVEPOINT handle | release savepoint 或 rollback to savepoint |

fresh connection 的簡化狀態如下：

```text
no root transaction
  -- execute / begin --> root transaction active
  -- commit ---------> no root transaction
  -- rollback -------> no root transaction

root transaction active
  -- begin_nested ---> root active + savepoint active
  -- nested commit --> root active（release savepoint）
  -- nested rollback -> root active（rollback to savepoint）
```

`connection.in_transaction()` 回答 SQLAlchemy connection 是否有 active root transaction；
`in_nested_transaction()` 回答是否有 active savepoint。需要 handle 時，可用 `get_transaction()` 與
`get_nested_transaction()`。這些是觀察與控制 SQLAlchemy state 的公開 API，但不能把 Python object
存在等同於「資料庫仍可接受下一個 statement」：PostgreSQL transaction 可能已因 SQL error 進入
failed state，下一節與後面的 scenario 會直接證明這個差異。

`Transaction` 與 `NestedTransaction` 不是兩條獨立 connection。nested rollback 只回到 savepoint；
root rollback 才結束整筆 DBAPI transaction。對 root connection 呼叫 `commit()` 也不是在 commit
目前 savepoint；savepoint 應由 `NestedTransaction` handle 或其 context manager 控制。

## DBAPI implicit transaction 與 DBAPI AUTOCOMMIT

**corrected behavior**：預設 DBAPI 模式下，不要把「我沒有寫 `BEGIN`」理解成「SQL 不在交易裡」。
SQLAlchemy `Connection` 第一次 execute 會建立 root transaction 狀態；DBAPI 依其規格與 driver
行為隱式開始資料庫交易。echo 中的 `BEGIN (implicit)` 表示 SQLAlchemy 認定 DBAPI implicit
transaction 開始，官方文件特別說明這不必然代表當下送出一條 literal `BEGIN`。

所以 plain `SELECT` 也會讓 `in_transaction()` 從 `False` 變成 `True`。離開 connection context
前若未 commit，close/reset 會 rollback；不能假設唯讀 statement 不需要資源生命週期，也不能讓
不必要的 transaction 長時間佔著 pool connection。

DBAPI `AUTOCOMMIT` 是 isolation-level mode，不是「SQLAlchemy 不再追蹤 transaction」的開關。
在該模式下，DBAPI/database 對 commit、rollback 的實際效果不同，但 SQLAlchemy 的 Python-side
`begin()`、autobegin 與 context-manager state machine 仍存在。若某個 statement 確實要求
autocommit，應建立清楚分離的 engine/connection policy，不能把主交易 engine 全域切換後仍假設
use-case atomicity 相同。

本 lab 的 production path 不使用 DBAPI AUTOCOMMIT；tenant、product、inventory 必須在預設交易
語意下共同 commit 或 rollback。

## savepoint 是局部回滾，不是獨立交易

`connection.begin_nested()` 建立 `NestedTransaction`，在 PostgreSQL 對應 SAVEPOINT。scenario
先在 outer transaction INSERT `Savepoint Tenant`，再於 nested block 嘗試相同 primary key；
unique violation 使 nested context rollback 到 savepoint。例外在 savepoint 外被處理後，outer
transaction 仍能正常離開 `engine.begin()` 並 commit 第一筆 row。

這證明 savepoint 的價值是「在同一個 root transaction 內，允許一個可預期的小單元失敗並局部
回滾」。它不是另一筆獨立交易：

- outer rollback 仍會撤銷 savepoint 之前與之後的所有資料庫寫入。
- outer transaction 的 isolation level、connection 與 lifetime 沒有縮短。
- savepoint 不能回滾已送出的 HTTP request、message、檔案寫入或 email。
- 未先開始 root transaction 時，SQLAlchemy 2.0 的 `begin_nested()` 也會先 autobegin outer
  transaction；它不會創造一條「只存在 savepoint」的 transaction。

不要把每個 exception 都用 savepoint 吞掉。只有 caller 能明確定義「這一小段失敗仍允許整體
成功」時才使用；如果 inventory 失敗代表 register-stock use case 失敗，就應讓 exception 穿出
application-service root boundary，觸發整體 rollback。

## 失敗後先 rollback，再重用資源

**evidence**：scenario 故意在 root transaction 內插入重複 tenant id。SQLAlchemy 捕捉並包裝
`IntegrityError`，但 catch exception 不會替應用程式決定 root transaction 邊界。
`connection.in_transaction()` 此時仍是 `True`；對同一 connection 立即執行 `SELECT 1`，PostgreSQL
拒絕 statement。呼叫 public `connection.rollback()` 後，`in_transaction()` 變成 `False`；再用
同一 connection 執行 `SELECT 1` 成功，且新 execute 重新 autobegin。

**Implementation note（PostgreSQL 18.4／psycopg 3.3.4）**：本 scenario 只以 SQLAlchemy 公開
`IntegrityError`／`DBAPIError` 類別與 Connection API 做 assertion。根交易發生 SQL error 後拒絕
後續 statement、直到 rollback 的行為是本固定 PostgreSQL stack 的可執行觀察；不同 database 的
failed-transaction recovery 規則可能不同，不應把 PostgreSQL error code 寫成跨 dialect contract。

生成的
[`ch05-connection-transactions.md`](../lab/evidence/ch05-connection-transactions.md) 固定八行：

```text
in_transaction_before_execute=False
in_transaction_after_execute=True
exception_block_rolled_back=True
savepoint_preserved_outer=True
failed_transaction_active=True
failed_transaction_rejected_statement=True
in_transaction_after_rollback=False
connection_reusable_after_rollback=True
```

前兩行證明 autobegin；第三行證明 exception block rollback；第四行證明 savepoint rollback 後 outer
commit；後四行共同證明「catch 不等於 recovery，rollback 才結束 failed root transaction，之後同一
Connection 才能重用」。scenario 每次先重建 schema，因此 observation 不依賴前一次執行殘留資料。

## 交易所有權：application service 擁有邊界

**decision**：每個 application-service operation 擁有且只擁有一個明確 root transaction；
lower-level Core function 接受 caller 提供的 `Connection`，可以 execute，但不能 commit 或 rollback。

本章用三層證據落實：

1. production code：
   [`catalog_service.py`](../lab/src/order_service/application/catalog_service.py) 的 entry point 只有一個
   `with engine.begin()`；三個 catalog call 共用其 connection。
2. failure injection：transaction test monkeypatch service module 使用的 `replenish_inventory`，讓
   tenant/product 已寫入後拋例外；另一個 connection 查到兩張表都是零筆，證明 root rollback。
3. architecture guard：
   [`test_lower_layers_never_commit_their_callers_transaction`](../lab/tests/unit/test_package_contract.py)
   掃描 `order_service` production package，任何 `.commit(` 都列為 offender。它是簡單 guard，不取代
   integration rollback proof；若未來有合法獨立 transaction use case，應把 owner 放在 application
   boundary，而不是放寬 lower layer。

這個 ownership 也決定 retry 位置。若整筆 transaction 因 serialization/deadlock 類錯誤必須 retry，
應重新執行完整 application operation，取得新 transaction state；不能只重跑最後一個 repository
statement，否則 earlier reads/writes 的一致性前提已經改變。retry policy 不在 Task 7 scope，但 owner
必須能看見整個 replayable use case。

## 事故模式：長交易與交易內外部 I/O

交易越長，connection checkout、row/version lock、MVCC snapshot 與失敗後重做成本通常越久。
常見事故不是忘了 `commit()`，而是 boundary 看似正確，block 內卻混入無界工作：

- 在 transaction 中呼叫支付、物流或第三方 HTTP，等待 timeout 時仍持有 connection/lock。
- 在 transaction 中等待 message broker acknowledgement，卻又要求 consumer 讀到尚未 commit 的資料。
- 把大型檔案上傳、模型推論或使用者互動放在 transaction block。
- catch database error 後不 rollback，繼續用 failed connection 做更多查詢，造成連鎖例外。
- lower layer 提早 commit，之後用補償邏輯假裝仍有資料庫 atomicity。

外部 side effect 不能由資料庫 rollback。設計時先把可在交易外完成的純計算、validation 與遠端讀取
移出去；需要「資料 commit 後可靠發布事件」時，使用 transactional outbox 等另外設計的協調機制，
而不是在 root transaction 裡直接 call broker。也不要盲目把所有外部 I/O 移到 commit 前或後：
先寫出 failure matrix，決定哪一方失敗時如何重試、去重或補償。

Connection pool reuse 也要求乾淨 state。正常 `Connection.close()` 會在歸還 pool 時清理 transaction；
但應用程式仍應在 owner boundary 明確處理成功與失敗，不要把 pool reset 當業務 rollback policy。
scenario 的「同一 Connection rollback 後可重用」證明 recovery sequence；不代表發生 disconnect、
connection invalidation 或未知 driver state 時一定應保留同一 DBAPI connection。

## 面試追問

**interview drill**：

1. 為什麼 transaction owner 應是 application service？回答要從完整 use-case invariant 與 failure
   boundary 說明，不只背「repository 不應 commit」。
2. lower-level `commit()` 如何破壞 caller atomicity？回答要指出它會 commit 同一 root transaction
   中 caller 更早的寫入，而且後續 rollback 無法撤銷已提交資料。
3. `Engine`、`Connection`、`Transaction` 的 lifetime 有何不同？回答要區分長生命週期 factory/pool、
   scoped checked-out resource 與單一 DBAPI transaction。
4. 為何第一次 `SELECT` 後 `in_transaction()` 會是 `True`？回答要說明 Connection autobegin 與 DBAPI
   implicit transaction，且 `BEGIN (implicit)` 不保證當下送出 literal SQL。
5. commit-as-you-go 與 begin-once 怎麼選？回答要比較顯式多段切點與一個 block 對應一個 use case，
   不能說其中一個永遠正確。
6. catch `IntegrityError` 後為何不能直接繼續查詢？回答要區分 SQLAlchemy transaction handle 仍存在、
   PostgreSQL root transaction 已 failed，以及 rollback 才完成 recovery。
7. savepoint 為何不是獨立交易？回答要指出它共用 outer connection/isolation/lifetime，outer rollback
   仍撤銷全部資料，且不能回滾外部 side effect。
8. DBAPI AUTOCOMMIT 是否關掉 SQLAlchemy 的 state machine？回答要說明 database effect 與
   Python-side `Connection.begin()`／autobegin semantics 是兩層。
9. 為何 pool reset 不能取代 application rollback policy？回答要區分資源清理與業務原子性；owner
   仍必須讓成功/失敗 boundary 可 review、可測試。
10. 交易內要送 message 怎麼辦？回答要先辨識 dual-write，說明 outbox／idempotency／retry 等設計
    方向，而不是宣稱 savepoint 或更長 transaction 可以涵蓋外部系統。
