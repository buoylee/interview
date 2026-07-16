# 並發正確性與長任務協調：設計規格

**日期**：2026-07-16
**狀態**：已完成 brainstorming，待使用者審閱
**主文件位置**：`system-design/11-並發正確性與長任務協調.md`

## 背景

這次討論從一個 MySQL 問題開始：一批資料在長任務執行期間需要保持一致，是否應長時間持有 `FOR UPDATE`。沿著這個問題繼續推演後，發現真正缺少的不是另一篇「鎖的用法」，而是一個跨層的生產決策模型：如何在高併發、長時間執行、進程崩潰、網路分區、重複請求與部分成功下維持業務不變量。

現有 repo 已有多個深度專題：

- `mysql-handson/05–06`：本地事務、MVCC、InnoDB 鎖與長事務危害。
- `redis-handson/07-distributed-locks`：Redis lock、watchdog、failover 與 fencing。
- `financial-consistency/05-patterns`：Outbox、Saga、TCC、Temporal、CDC、狀態機與驗證。
- `software-architecture/07-EventSourcing-領域事件-Saga.md`：領域事件、Event Sourcing 與 Saga 的架構邊界。
- `concurrency-capacity/`：併發容量、排隊、隔離、背壓與 scale-out。
- `system-design/`：生產級分布式系統的通用零件庫與總索引。

缺口在於：這些內容各自講清了特定機制，但尚未提供一條從「業務不變量」走到「一致性邊界、協調方案、失敗恢復、容量代價與驗證閉環」的統一推理路線。

## 核心決策

新增單一通用理論章：

`system-design/11-並發正確性與長任務協調.md`

它是這個主題的唯一理論源頭。MySQL、Redis、金融一致性與軟體架構目錄只增加短入口與交叉引用，不各自重寫一份。

主題定位不是「長任務如何取代鎖」，而是：

> 如何在並發、長時間與部分失敗下維持業務不變量。

## 目標

1. 從 invariant 出發，而不是從 MySQL、Redis、Saga 等工具名稱出發。
2. 分清互斥執行、穩定批次、資源預留、有序狀態與跨服務收斂五類問題。
3. 建立從單條原子操作、本地短事務，到 durable state、跨服務 workflow、外部不可控系統的一致性邊界階梯。
4. 解釋生產中真正使用的方案，以及每個方案保證什麼、不保證什麼。
5. 把 crash、timeout、duplicate、late worker、partial success、unknown outcome 與補償失敗納入主流程，而不是放在附錄。
6. 補上高併發代價：熱點串行、retry storm、排隊、分區、背壓、公平性與 starvation。
7. 以審計、對帳、回放與人工修復完成「預防、檢測、恢復」閉環。
8. 透過官方公開案例證明方案是真實生產模型，不推測公司內部實作。

## 非目標

- 不提供 Java、Go、SQL 或框架實作代碼。
- 不重寫 InnoDB、Redis、Kafka、Temporal、Saga 或 TCC 的底層教程。
- 不把每個 pattern 寫成獨立百科。
- 不宣稱某家公司使用未公開的內部 schema 或協調算法。
- 不深入共識算法、CAP、邏輯時鐘、MQ broker 或容量公式；只引用既有專題。
- 不承諾一套方案適用所有業務；重點是選型條件與失敗邊界。

## 讀者與完成標準

目標讀者是資深後端工程師與架構師候選人。讀完後應能回答：

1. 目前問題是互斥、批次一致、資源預留、有序狀態，還是跨服務流程？
2. 業務 invariant 是什麼，哪種錯誤絕不能發生？
3. 正確性邊界位於單條操作、本地事務、單服務、多服務，還是外部系統？
4. 為何 DB 鎖適合短臨界區，卻不適合跨越長任務？
5. lease 為何不能單獨保證正確，fencing 解決哪個 stale-owner 問題？
6. immutable batch、logical freeze、reservation 與 workflow 如何選？
7. crash、timeout、duplicate、late worker、部分成功後，系統如何收斂？
8. 高併發下哪裡會成為天然串行點或熱點？
9. 線上保護仍然失敗時，如何靠審計、對帳與修復閉環？
10. 為何 transport 的 delivery guarantee 不等於端到端 business effect exactly-once？

## 核心推理模型

全章使用同一條推理鏈：

```text
業務不變量
→ 保護對象
→ 一致性邊界
→ 競爭程度
→ 故障模型
→ 選擇機制
→ 證明與修復
```

每個方案都固定回答八個問題：

1. 它解決哪個 invariant？
2. 它保護的是資料、資源、任務所有權，還是流程狀態？
3. 它的原子邊界在哪？
4. 它不保證什麼？
5. owner crash 後誰接管？
6. stale owner 如何被拒絕？
7. 高併發下瓶頸與退化方式是什麼？
8. 如何觀測、驗證、對帳與修復？

## 內容結構

### Part A：先從不變量出發

先區分五種經常被統稱為「鎖」的需求：

- **互斥執行**：同一任務只能有一個有效 owner。
- **穩定批次**：任務輸入的成員與值必須屬於同一業務版本。
- **資源預留**：庫存、資金、座位等稀缺能力不能被重複消耗。
- **有序狀態**：同一 aggregate 的命令與狀態遷移必須遵守合法順序。
- **跨服務收斂**：多個本地成功或失敗最終必須收斂到可解釋結果。

本節釘死「鎖只是機制，不是需求」，並用錯誤示例展示只問「該用哪種鎖」為何會選錯方案。

### Part B：一致性邊界階梯

建立五層邊界：

```text
單條原子操作
→ 本地短事務
→ 單服務 durable state
→ 跨服務 workflow
→ 外部不可控系統
```

每升一層，能依賴的同步 ACID 保證減少；需要增加 durable state、idempotency、compensation、reconciliation 與人工介入。

同時定義短事務與長任務：不以固定秒數作唯一標準，而看是否持有稀缺資源、延遲是否有界、是否包含外部 I/O、是否跨越進程生命週期，以及是否需要 crash 後接管。

### Part C：本地短邊界

建立選型優先序：

```text
唯一約束／原子條件更新
→ Optimistic CAS
→ Pessimistic Lock
→ 固定順序的短事務
```

本節只講決策原理：

- DB 鎖為何是 OLTP 正確性的基礎，而不是「大型項目不用鎖」。
- 為何能用原子條件更新時，通常比 read-modify-write 更短、更穩。
- Optimistic control 適合低衝突；高衝突會產生 retry storm。
- Pessimistic lock 適合不可接受重算、臨界區很短的競爭。
- 多行、多表操作要縮小鎖面並統一順序。
- 一旦外部 I/O、等待或 crash 接管進入流程，就要離開 DB transaction。

底層細節連到 `mysql-handson/05-mvcc-and-transaction` 與 `mysql-handson/06-locking`。

### Part D：長任務協調

覆蓋六類真實方案：

1. **Durable State Machine**：把任務生命週期寫成可恢復狀態，而非依賴進程記憶體。
2. **Ownership + Lease + Heartbeat + Fencing**：管理誰能執行、所有權何時過期，以及如何拒絕舊 owner。
3. **Immutable Batch + Version + Cutoff**：固定一批輸入的成員和值，允許來源資料繼續演進。
4. **Reservation / Hold-Confirm-Release**：保留稀缺能力，而非凍結整個業務物件。
5. **Per-Key Serialization / Durable Queue**：同一 resource key 局部串行，不占用長 DB connection。
6. **Shadow Build + Atomic Switch**：在新版本完成長處理，最後短暫切換線上指標。

每類方案使用統一模板：問題、invariant、基本原理、保證、不保證、故障行為、併發代價、選型邊界與公開案例。

### Part E：跨服務長流程

建立以下關係：

```text
本地事務
+ Outbox 解決 dual write
+ Idempotency 吸收重複
+ Saga/TCC 協調業務結果
+ Durable Workflow 保存控制狀態
+ Reconciliation 收口
```

本節釐清：

- Saga 與 TCC 解決的資源語義不同。
- Outbox 保證已提交事實可被可靠傳播，但不替代跨服務流程狀態機。
- Durable workflow 保存控制流程與重試狀態，但不替代服務內 invariant、帳本或對帳。
- Queue delivery guarantee 不等於 business side effect exactly-once。
- XA/2PC 能提供更強同步原子性，但阻塞、可用性與參與者邊界使它不適合作為長業務流程的預設方案。

細節連到 `financial-consistency/05-patterns` 與 `software-architecture/07-EventSourcing-領域事件-Saga.md`。

### Part F：完整故障矩陣

以時間點分析至少八種失敗：

1. 認領前 crash。
2. 認領後、執行前 crash。
3. 外部操作成功但回應丟失。
4. 本地提交成功但通知未發。
5. lease 過期後舊 worker 復活。
6. 新舊 worker 同時嘗試完成。
7. 補償失敗或補償結果未知。
8. 人工修復與自動恢復競爭。

矩陣把每種失敗映射到 durable state、idempotency key、lease、fencing、retry、outbox、compensation、reconciliation 與 manual review。

### Part G：高併發與容量

補上正確性方案的性能代價：

- 熱點資源天然串行，無法靠增加 worker 無限擴展。
- 鎖持有時間如何限制單熱點吞吐。
- Optimistic CAS 在高衝突下如何退化成 retry storm。
- Queue 如何削峰，但換來等待時間、backlog 與公平性問題。
- 按 resource key 分區，將全域串行縮小為局部串行。
- Reservation/Escrow 如何減少對單一總量行的競爭。
- Backpressure 如何防止失敗重試與積壓拖垮整個系統。
- 公平性與 starvation 為何也是正確性之外的生產要求。

容量公式與實驗連到 `concurrency-capacity/`。

### Part H：正確性閉環

建立「預防、檢測、恢復」三層：

```text
Invariant
→ State Machine
→ Immutable Facts
→ Metrics/Alert
→ Reconciliation
→ Replay/Repair
→ Manual Review
```

- **預防**：約束、原子狀態遷移、短鎖、fencing、idempotency。
- **檢測**：metrics、audit facts、history、invariant checker、aging task alarm。
- **恢復**：retry、reclaim、compensation、reconciliation、人工修復。

本節強調：lock、lease、workflow 只能減少錯誤；對帳與可解釋修復負責最後收口。

### Part I：決策樹與反模式

決策樹依序詢問：

1. 只需要一個有效執行者，還是需要保護業務資料？
2. 任務只需要穩定輸入，還是來源資料必須禁止修改？
3. 保護的是完整物件，還是某種可預留的稀缺能力？
4. 衝突頻率高不高，重算成本能否接受？
5. 是否跨服務、跨資料庫或包含外部副作用？
6. timeout 後能否查詢結果，副作用是否可冪等重試？
7. 是否要求審計、重放、對帳與人工修復？

反模式至少包含：

- 長時間持有 DB transaction。
- 把 Redis lock 當成資料正確性的完整保證。
- 只有 `PROCESSING`，沒有 owner、lease 與 fencing。
- retry 沒有 idempotency。
- snapshot 只保存 ID，不保存值或 immutable version。
- Saga 沒有補償失敗與 unknown outcome 處理。
- 只保存當前狀態，不保存可審計事實。
- 只設計正常流程，不做告警、對帳與修復。

## 圖示計畫

正式章節使用文字圖與表格，不依賴程式碼：

1. 一致性邊界階梯。
2. 問題類型與方案對照表。
3. owner/lease/fencing 的新舊 worker 時序。
4. immutable batch 的 capture/process/publish 流程。
5. Hold/Confirm/Release 狀態機。
6. Saga 部分成功與補償時序。
7. 故障矩陣。
8. 最終選型決策樹。

圖示只表達狀態、事件、保證與失效點，不畫具體 SDK 或基礎設施配置。

## 證據與來源策略

每種核心方案至少使用一個官方公開來源作錨點：

- MySQL：本地短事務與 locking read。
- Kubernetes：Lease、heartbeat、leader election、optimistic resource version。
- Amazon SQS：visibility timeout、重新投遞、heartbeat 式續期。
- AWS Builders' Library：idempotent API 與安全重試。
- AWS Prescriptive Guidance：Transactional Outbox 與 Saga。
- Stripe：authorization、capture、cancel 的長時間資源預留語義。
- Elasticsearch：新 index 建立與 alias 原子切換。
- Temporal：durable workflow、retry、replay 與長流程恢復。

主要官方來源：

- <https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html>
- <https://kubernetes.io/docs/concepts/architecture/leases/>
- <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html>
- <https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/>
- <https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html>
- <https://docs.aws.amazon.com/prescriptive-guidance/latest/modernization-data-persistence/saga-pattern.html>
- <https://docs.stripe.com/payments/place-a-hold-on-a-payment-method>
- <https://www.elastic.co/guide/en/elasticsearch/reference/current/aliases.html>
- <https://temporal.io/>

來源只能證明公開行為與官方建議。正文不得將公開 API 語義推斷成供應商未公開的內部資料模型。

## 文件改動範圍

正式實作階段預計修改：

1. 新增 `system-design/11-並發正確性與長任務協調.md`。
2. 更新 `system-design/README.md`，把新章標為跨 L2/L3 的正確性決策層。
3. 更新 `mysql-handson/06-locking/README.md`，新增「DB 短鎖的系統邊界」短入口。
4. 更新 `redis-handson/07-distributed-locks/README.md`，新增「lease 不等於資源正確性」短入口。
5. 更新 `financial-consistency/05-patterns/README.md`，新增通用理論入口。
6. 更新 `software-architecture/07-EventSourcing-領域事件-Saga.md`，從 Saga 邊界連回通用決策章。

不修改 root `README.md`；它已指向 `system-design/`。不新增獨立 track，不新增 lab，不修改既有 scenario。

## 寫作規則

每節使用固定順序：

```text
問題
→ invariant
→ 為何直覺方案失敗
→ 生產方案原理
→ 保證與不保證
→ 故障時行為
→ 高併發代價
→ 選型邊界
→ 官方公開案例
```

- 主流、低成本方案先講；高成本強化方案後講。
- 技術名詞保留英文，第一次出現時給精確中文解釋。
- 不用「通常」「理論上」掩蓋邊界；明確標出 DB、進程、服務、消息與業務層。
- 不把 framework capability 寫成 end-to-end business guarantee。
- 每個方案同時寫適用條件與不適用條件。
- 交叉引用負責深入，不在主文複製既有專題。

## 驗證與審閱

本次是理論文件，不新增可執行測試。驗證方式：

1. **結構檢查**：所有 Part A–I 完整，無占位符。
2. **術語檢查**：lock、lease、fencing、snapshot、reservation、idempotency、Outbox、Saga、TCC、workflow、reconciliation 邊界一致。
3. **故障檢查**：每個核心方案至少覆蓋 crash、duplicate、timeout 或 stale owner 中相關失效。
4. **選型檢查**：每個方案都寫保證、不保證、適用與不適用。
5. **來源檢查**：真實案例只引用官方來源，且不超出來源公開內容。
6. **導航檢查**：主章與五個入口互相可達，無死鏈。
7. **重複檢查**：MySQL、Redis、financial-consistency、software-architecture 的深度內容不被整段複製。
8. **讀者驗收**：用「批次統計」「庫存預留」「單 worker 任務」「跨服務訂單」四個場景走一遍決策樹，能得到可辯護的不同答案。

## 風險與控制

| 風險 | 控制 |
|---|---|
| 範圍膨脹成分布式系統百科 | 主章只做決策模型；機制細節一律交叉引用 |
| 方案清單化，缺少推理主線 | 全章強制使用 invariant → boundary → failure → mechanism → evidence |
| 廠商案例變成背產品 | 每個案例只作原理錨點，正文先講通用模型 |
| 把 lease 說成絕對互斥 | 明確加入 pause、expiry、stale worker 與 fencing 時序 |
| 把 exactly-once 當完整保證 | 分開 delivery、processing 與 business effect 三層 |
| 只講正確性，不講容量 | 每個方案寫高衝突退化、排隊與熱點代價 |
| 只講預防，不講線上恢復 | 故障矩陣與 reconciliation 放入主體，不放附錄 |
| 與既有文件重複或矛盾 | 主章定義共同語言；其他文件只加短入口 |

## 驗收條件

- 新章定位、內容結構、交叉引用範圍與本規格一致。
- 全文不包含實作代碼，但原理、狀態、時序、保證與失效點足夠清楚。
- 至少覆蓋本地短邊界、長任務協調、批次一致性、資源預留、跨服務流程、故障矩陣、高併發代價與正確性閉環。
- 所有公開案例具有官方來源，且無未證實的公司內部實作聲稱。
- 既有五個入口只做導航與邊界提示，不形成第二份理論源頭。
- 讀者能用決策樹分析不同場景，而不是背誦固定答案。
