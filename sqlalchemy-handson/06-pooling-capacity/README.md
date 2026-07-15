# 06 · 連線池與容量治理：Pool 是並發閘門，不是加速按鈕

本章把「pool timeout」拆成可重現的資源狀態，而不是用一句「把 pool 調大」結案。案例固定在
SQLAlchemy 2.0.51、psycopg 3.3.4 與 PostgreSQL 18.4；production code 與測試只依賴 SQLAlchemy
公開 API。SQLAlchemy 的完整公開契約見 [Connection Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)，
斷線偵測與 `pool_pre_ping` 見
[Disconnect Handling — Pessimistic](https://docs.sqlalchemy.org/en/20/core/pooling.html#disconnect-handling-pessimistic)。

可執行案例是
[`ch06_pooling_capacity.py`](../lab/scenarios/ch06_pooling_capacity.py)，結果寫入
[`ch06-pooling-capacity.md`](../lab/evidence/ch06-pooling-capacity.md)。測試
[`test_pooling.py`](../lab/tests/integration/test_pooling.py) 用 barrier 先確認兩條 connection 都已
checkout，再由第三個 checkout 等待 0.2 秒 timeout；它不靠 `sleep()` 猜兩個 holder 是否準備完成。

## 生產問題：pool timeout 是池太小，還是連線拿太久？

相同的 `sqlalchemy.exc.TimeoutError` 可以來自不同負載形狀。先區分四種事故，才知道該改容量、
縮短 transaction，還是修生命週期：

| 事故 | 資源狀態 | 典型訊號 | 優先行動 |
| --- | --- | --- | --- |
| application pool saturation | 單一 process 的 `checkedout()` 達 `pool_size + max_overflow` | checkout wait 上升；資料庫可能仍有餘裕 | 找持有時間與 process 內並發，先不要盲目放大 pool |
| database max-connections exhaustion | 全部 client 合計逼近 PostgreSQL connection 上限 | 新 DBAPI connect 被 database 拒絕 | 盤點所有 service、worker、migration 與維運連線的總預算 |
| slow transactions | connection 合法 checkout，但被 query、lock wait 或 transaction 內 I/O 長時間占用 | transaction age、query latency、lock wait 同時上升 | 找慢 SQL、鎖與 transaction boundary |
| leaked `Connection` | owner 沒有 close／context manager，資源不回 pool | checkout 累積且缺少對應 checkin | 修所有權與 `with` scope，不能靠增大 pool 掩蓋 leak |

因此「pool 太小」不是 timeout message 自動給出的結論。容量不足與持有時間過長也會互相放大：同樣
十個 slot，平均持有 20 ms 與 2 s 能承受的吞吐完全不同。

## 先預測，再執行

執行 scenario 前先寫下可被推翻的預測：

1. `pool_size=2, max_overflow=0` 時，兩個 holder 成功 checkout 後，`checkedout()` 是 2。
2. 第三次 `engine.connect()` 不產生 checkout event；它等待 `pool_timeout=0.2` 後拋出
   `sqlalchemy.exc.TimeoutError`。
3. holder 被明確 release 後，每個歸還流程先 reset、再 checkin。
4. pool timeout 不會破壞 pool；下一次 checkout 可執行 `SELECT 1`，離開 context 後
   `checkedout()` 回到 0。

[`test_third_checkout_times_out_when_two_slots_are_held`](../lab/tests/integration/test_pooling.py) 對等待時間只鎖定
`0.15 <= waited_seconds < 0.8` 的寬窗口。0.2 秒是設定值，不是 universal latency promise；host
scheduler、CI contention 與 clock granularity 都會讓實測毫秒數浮動。真正不變的證據是兩個 slot
已持有、第三次 checkout timeout，以及 release 後 pool 可恢復。因此 committed evidence 只寫
`timeout_within_expected_bound=True`，不提交 wall-clock millisecond；寬窗口仍由測試直接檢查。

## Public contract：QueuePool checkout、checkin、reset、invalidate

`QueuePool` 管理可重用的 DBAPI connection。公開 event 與狀態 API 足以描述本案例：

- `checkout`：成功從 pool 取得 DBAPI connection；排隊等待但最後 timeout 的 attempt 沒有 checkout。
- `reset`：connection 歸還前清理 transaction state；預設 reset-on-return 通常會 rollback。
- `checkin`：DBAPI connection 回到 pool，可以被下一個 caller 再次 checkout。
- `invalidate`：標記某條 connection 不再可用；下一次使用時由 pool 建立替代連線。
- `QueuePool.checkedout()`：目前由 caller 持有的連線數，是公開的當下狀態觀察。

本 scenario 用 `sqlalchemy.event.listen()` 監聽 pool 的公開事件，並用 lock 保護跨 thread 的 observation
list。測試只要求 deterministic 的 phase order：最初兩個 checkout、接著 timeout；release 完成後，
最後一個 recovery connection 是 checkout → reset → checkin。兩個 holder 彼此的 reset/checkin 交錯順序
由 scheduler 決定，不被寫成 contract。

**Implementation note（固定 stack）**：目前 SQLAlchemy timeout message 包含
`QueuePool limit of size 2 overflow 0 reached`，integration test 把它當本 lab 固定版本的診斷證據；
message wording 不是跨 SQLAlchemy 版本的 public API。reset 對此 PostgreSQL/psycopg 組合會清理
DBAPI transaction，但應用程式仍必須由 transaction owner 明確 commit/rollback，不能把 pool reset
當業務交易 policy。

## pool_size、max_overflow、pool_timeout、pool_recycle、pre_ping

- `pool_size` 是每個 `Engine` 長期保留的連線數上限，不是整個 service 或整個 cluster 的上限。
- `max_overflow` 是 pool 已滿時可臨時新增的連線數；每個 process 的硬 checkout 上限是
  `pool_size + max_overflow`。overflow connection 歸還後通常不留在 persistent pool。
- `pool_timeout` 是等待可用 slot 的最長時間；縮短它是更快 fail，不會創造容量。
- `pool_recycle` 讓超過 age 的連線在下一次 checkout 時被替換，適合對齊 proxy/server idle policy；
  它不會中止正在使用的 connection。
- `pool_pre_ping=True` 在 checkout 時先測試連線，降低 stale connection 進入 request 的機率，但每次
  checkout 多一次健康檢查成本，也不能救回已開始 transaction 中途發生的斷線。

本 lab 的 `build_engine(settings, **overrides)` 保留預設 production policy，同時讓 scenario 明確覆寫
四個 pool 參數。這是測試建立獨立 Engine 的配置 seam，不改變既有 transaction ownership。

## 全服務連線預算：instance × worker × process pool

[`PoolBudget`](../lab/src/order_service/db/pool_budget.py) 定義保守 hard ceiling：

```text
connection_ceiling = instances × workers × (pool_size + max_overflow)
```

例如 3 個 instance、每個 4 個 worker、`pool_size=5`、`max_overflow=2`，上限是
`3 × 4 × 7 = 84`。這還不是 PostgreSQL 可全部分給本服務的數字；database budget 要先扣除管理保留、
migration、background job、其他服務與故障切換所需餘裕。`assert_fits(database_budget)` 只做
deployment arithmetic guard，不宣稱 runtime 一定同時打滿，也不取代 database 端監控。

worker model 必須算對。Gunicorn 每個 process 通常各有自己的 Engine/pool；多個 service instance
也不共享 process memory。若同一 process 建立讀寫兩個 Engine，兩個 pool 應分別列入。不能只看一個
worker 的 `pool_size=5` 就向 DBA 宣稱服務最多五條連線。

## Little's Law 只提供估算，不提供魔法數字

穩態下可以用 `L = λW` 思考：平均同時被占用的 connection 數，約等於需要 database connection 的
完成率乘以平均持有時間。若每秒 100 個 database operation，每次平均持有 40 ms，平均占用約 4；
但平均值不描述 burst、長尾、lock convoy 或 retry storm。

所以 Little's Law 適合做起始容量與敏感度分析，不適合直接產生「pool_size 必須等於 4」的魔法數字。
實際決策仍要看 checkout wait percentile、checked-out utilization、transaction/query latency、timeout
rate 與 database headroom，並在代表性 burst 下驗證。

## PgBouncer 與應用池的雙層關係

PgBouncer 不會讓應用層 pool budget 消失。application pool 管理 process 內的 caller 排隊與 DBAPI
connection reuse；PgBouncer 管理更多 client connection 如何 multiplex 到較少 server connection。
兩層都設很大，可能只把排隊位置從 application 移到 proxy，並增加 client socket、memory 與 timeout
組合的複雜度。

transaction pooling 模式下，server connection 在 transaction 結束後可換手；依賴 session state、
temporary table、session-level advisory lock 或 prepared-statement 行為前，必須依固定 driver、PgBouncer
版本與配置驗證。不要把 session pooling 與 transaction pooling 的語意混為一談。

容量規劃應同時列出 application hard ceiling、PgBouncer client limit、server pool size、PostgreSQL
可用 connection budget 與每層 timeout，明確知道哪一層先 backpressure。

## fork safety、DB restart、disconnect handling

`Engine` 持有 pool 與既有 DBAPI socket，不能把 parent process 已建立的 connection 直接當成 fork 後
可安全共享的資源。pre-fork server 應在 child process 建立 Engine，或依 SQLAlchemy 官方策略在 child
初始化時 dispose 舊 pool；同一個 file descriptor 被多個 process 使用會造成不可預期的 protocol
interleaving。

database restart 會讓 pool 內 idle socket stale。pessimistic `pre_ping` 可在 checkout 時偵測並替換；
optimistic handling 則在實際 operation 收到 disconnect 時 invalidate pool generation。無論哪種策略，
已進行中的 transaction 都已失敗，應由 application boundary 決定整個 use case 是否可安全 retry；
pool 自動重連不能恢復 transaction 中已完成一半的工作。

## 排查順序與觀測指標

建議依因果順序排查，而不是先改 pool size：

1. 確認 exception class、發生層與 pool 配置；分清 application checkout timeout 與 database connect
   rejection。
2. 同看 `checkedout()`、checkout wait histogram、timeout rate、checkout/checkin/reset/invalidate event
   count，確認是 burst、持續 saturation 或疑似 leak。
3. 按 endpoint/job 量測 connection hold time，對照 query latency、transaction age、lock wait 與外部
   I/O；慢 transaction 先縮短 critical section。
4. 盤點 instance、worker、每 process Engine、overflow 與其他 client，計算 cluster hard ceiling，
   對照 PostgreSQL 與 PgBouncer headroom。
5. 修好 ownership/leak 或 slow path 後再做 load test；只有 database 有餘裕且 checkout wait 仍是瓶頸，
   才調整 pool。調大後要重跑 budget guard 與 failure test。

alert 不應只看單一瞬間 utilization。較有用的組合是：checkout wait p95/p99、timeout rate、checked-out
比例、connection hold p95/p99、active/idle-in-transaction 數、oldest transaction age、database
connection headroom 與 lock wait。它們能把「slot 不夠」連回「誰持有、持有多久、下游是否還能承受」。

## 面試追問

1. `pool_size=5, max_overflow=10` 是一個 process 還是整個 deployment 的 15？多 worker 時如何算？
2. 第三次 checkout timeout 時，為什麼不應出現 checkout event？timeout 後如何證明 pool 沒壞？
3. pool saturation、PostgreSQL max-connections、slow transaction 與 leaked `Connection` 的證據各是什麼？
4. 為什麼把 `pool_timeout` 從一秒改成十秒可能只會讓 request 更慢，而不會增加吞吐？
5. `pool_pre_ping` 能處理 DB restart 的哪一段？為什麼不能透明恢復 in-flight transaction？
6. PgBouncer transaction pooling 下，哪些 session-level assumption 必須重新驗證？
7. Little's Law 如何協助估算平均占用？為什麼仍要保留 burst 與 database headroom？
