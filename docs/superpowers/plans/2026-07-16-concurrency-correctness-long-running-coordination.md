# Concurrency Correctness and Long-Running Coordination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立一篇以業務不變量為起點、能指導高併發長任務選型與故障恢復的通用理論章，並從既有 MySQL、Redis、金融一致性與軟體架構文件連回唯一理論源頭。

**Architecture:** `system-design/11-並發正確性與長任務協調.md` 是唯一主文，依序建立 invariant、boundary、mechanism、failure、capacity、verification 的決策鏈。其他五個文件只增加短入口與邊界提示，不複製主文；現有 hands-on 與 financial-consistency 仍負責底層機制、實機證據與領域深挖。

**Tech Stack:** Markdown、ASCII 時序／狀態圖、官方公開文件、`rg`／`test`／Git 文件驗證

## Global Constraints

- 只寫理論、狀態、時序、保證、失效點與選型；不新增 Java、Go、SQL 或框架實作代碼。
- 主文固定為 `system-design/11-並發正確性與長任務協調.md`，不得建立第二份通用理論源頭。
- 全章使用 `業務不變量 → 保護對象 → 一致性邊界 → 競爭程度 → 故障模型 → 選擇機制 → 證明與修復` 推理鏈。
- 每個核心方案必須寫：解決的 invariant、保護對象、原子邊界、保證、不保證、接管、stale owner、高併發退化、驗證與修復。
- 真實案例只引用官方公開來源；不得推測供應商未公開的內部 schema、鎖實作或資料模型。
- 明確區分 DB、進程、服務、消息與業務層，不用「通常」「理論上」掩蓋邊界。
- 主流低成本方案先寫；高成本強化方案後寫。
- 不重寫 MySQL、Redis、Kafka、Temporal、Saga、TCC、CAP、共識與容量公式；使用相對連結指向既有深礦。
- 不修改 root `README.md`，不新增 lab，不修改既有 scenario。
- 所有 Markdown 變更必須通過 `git diff --check`，不得包含任何未完成標記或占位文字。

---

## File Map

| File | Responsibility |
|---|---|
| `system-design/11-並發正確性與長任務協調.md` | 唯一主文；定義問題分類、邊界階梯、短事務、長任務、跨服務、故障、高併發、閉環與決策樹 |
| `system-design/README.md` | 把新章加入 L2/L3 跨層導航與本地章節清單 |
| `mysql-handson/06-locking/README.md` | 說明 DB 行鎖只保護短事務臨界區，長任務導向主文 |
| `redis-handson/07-distributed-locks/README.md` | 說明 distributed lock／lease 只協調 owner，資源正確性導向主文 |
| `financial-consistency/05-patterns/README.md` | 在金融 pattern 前提供通用 invariant／boundary 決策入口 |
| `software-architecture/07-EventSourcing-領域事件-Saga.md` | 從 Saga 長流程骨架連回通用協調與故障模型 |

---

### Task 1: 建立 invariant、邊界與本地短事務骨架

**Files:**
- Create: `system-design/11-並發正確性與長任務協調.md`
- Reference: `docs/superpowers/specs/2026-07-16-concurrency-correctness-long-running-coordination-design.md`
- Reference: `mysql-handson/05-mvcc-and-transaction/README.md`
- Reference: `mysql-handson/06-locking/README.md`

**Interfaces:**
- Consumes: 已批准 spec 的「核心推理模型」與 Part A–C。
- Produces: 穩定術語表、五類問題、五層一致性邊界、短事務選型順序；Task 2–4 必須沿用這些名稱與邊界。

- [ ] **Step 1: 建立章首定位與閱讀契約**

新增標題、問題背景、非目標與這條總推理鏈：

```text
業務不變量
→ 保護對象
→ 一致性邊界
→ 競爭程度
→ 故障模型
→ 選擇機制
→ 證明與修復
```

章首必須明說：本章不是 lock、Saga 或 queue 百科；它負責辨認問題、選型與解釋 failure boundary，細節交給深度專題。

- [ ] **Step 2: 寫 Part A「先從不變量出發」**

使用一張對照表定義五類問題，欄位固定為「問題類型／真正要保護的東西／典型錯誤／錯誤工具直覺」：

1. 互斥執行：有效 owner；錯誤是同一任務重複產生副作用。
2. 穩定批次：同一批輸入的成員與值；錯誤是混合不同版本。
3. 資源預留：可消耗能力；錯誤是超賣、重複扣減。
4. 有序狀態：aggregate 的合法遷移；錯誤是晚到事件覆蓋新狀態。
5. 跨服務收斂：多個本地結果；錯誤是永久部分成功且不可解釋。

以一句話收束：「鎖是機制，不是需求；先說 invariant，再談工具。」

- [ ] **Step 3: 寫 Part B「一致性邊界階梯」**

加入以下階梯，逐層說明能依賴與必須補上的能力：

```text
單條原子操作
→ 本地短事務
→ 單服務 durable state
→ 跨服務 workflow
→ 外部不可控系統
```

使用表格列出每層的原子邊界、主要失敗、恢復單位與附加機制。短／長邊界不得只用秒數；必須同時檢查外部 I/O、延遲上界、進程生命週期、接管需求與鎖住的稀缺資源。

- [ ] **Step 4: 寫 Part C「本地短邊界」**

依序解釋：

```text
唯一約束／原子條件更新
→ Optimistic CAS
→ Pessimistic Lock
→ 固定順序的短事務
```

必須包含：

- DB 鎖是 OLTP 基礎，不是大型系統不用鎖。
- 原子條件更新縮短 read-modify-write window。
- Optimistic CAS 適合低衝突，衝突高時形成 retry storm。
- Pessimistic lock 適合重算不可接受、臨界區有界且短的情況。
- 多行／多表使用一致順序與小鎖面。
- 外部 I/O、人工等待、不可預測計算或 crash 接管一旦出現，就離開 DB transaction。

引用 MySQL 官方 locking read：

`https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html`

使用相對連結指向：

- `../mysql-handson/05-mvcc-and-transaction/README.md`
- `../mysql-handson/06-locking/README.md`

- [ ] **Step 5: 驗證 Task 1 結構與邊界**

Run:

```bash
test -s system-design/11-並發正確性與長任務協調.md
rg -n '^## Part [ABC]' system-design/11-並發正確性與長任務協調.md
rg -n '互斥執行|穩定批次|資源預留|有序狀態|跨服務收斂' system-design/11-並發正確性與長任務協調.md
rg -n '原子條件更新|Optimistic CAS|Pessimistic Lock' system-design/11-並發正確性與長任務協調.md
test -e mysql-handson/05-mvcc-and-transaction/README.md
test -e mysql-handson/06-locking/README.md
git diff --check
```

Expected:

- Part A、B、C 各出現一次。
- 五類問題與三個短邊界術語全部命中。
- 兩個本地引用存在。
- `git diff --check` 無輸出、exit 0。

- [ ] **Step 6: 提交 Task 1**

```bash
git add system-design/11-並發正確性與長任務協調.md
git commit -m "docs(system-design): define concurrency boundaries"
```

---

### Task 2: 加入長任務與跨服務生產方案

**Files:**
- Modify: `system-design/11-並發正確性與長任務協調.md`（接在 Part C 後）
- Reference: `redis-handson/07-distributed-locks/README.md`
- Reference: `financial-consistency/05-patterns/README.md`
- Reference: `software-architecture/07-EventSourcing-領域事件-Saga.md`

**Interfaces:**
- Consumes: Task 1 定義的五類問題與五層邊界。
- Produces: Part D 的六類長任務方案與 Part E 的跨服務組合關係；Task 3 的故障矩陣將逐項驗證這些方案。

- [ ] **Step 1: 寫 Part D 開場與固定評估模板**

先釘死每個方案都必須回答：invariant、保護對象、原子邊界、保證、不保證、接管、stale owner、高併發退化、驗證與修復。不得只寫定義或優點。

- [ ] **Step 2: 寫 Durable State 與 Lease/Fencing**

分開說明：

- Durable State Machine 保存任務生命週期，不依賴 worker 記憶體。
- owner token 識別持有者；lease 提供有界所有權；heartbeat 延長活性判斷。
- lease expiry 不能讓舊 worker 自動停止；fencing 必須在被保護資源的寫入邊界拒絕舊 token。
- lock/lease 可避免重複工作，但沒有 resource-side validation 時不能單獨保證錢、庫存等正確性。

官方錨點只使用公開行為：

- Kubernetes Lease：`https://kubernetes.io/docs/concepts/architecture/leases/`
- Amazon SQS visibility timeout：`https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html`

- [ ] **Step 3: 寫 Immutable Batch 與 Reservation**

Immutable Batch 必須分清：

- membership 固定：保存哪些資料屬於批次。
- value 固定：保存完整輸入或 immutable version；只存 ID 不足以重算。
- cutoff/version 是捕獲邊界，不代表來源資料必須停止演進。

Reservation 必須分清：

- 保護的是可消耗能力，不是凍結整個物件。
- Hold/Confirm/Release 需要 expiry、idempotency 與恢復路徑。
- 適合庫存、資金、座位；不應被描述成 DB 長鎖。

官方錨點：

- Stripe authorization/capture/cancel：`https://docs.stripe.com/payments/place-a-hold-on-a-payment-method`

- [ ] **Step 4: 寫 Per-Key Serialization 與 Shadow Build**

Per-Key Serialization 必須說明：同一 resource key 局部串行，其他 key 仍可並行；durable queue 保存等待，不占 DB connection；代價是 backlog、延遲、公平性與 hot partition。

Shadow Build 必須說明：在線舊版本持續服務，背景建立新版本，驗證完成後做短暫原子切換；適合索引、配置、讀模型與大批資料轉換，不適合需要原地副作用的流程。

官方錨點：

- Elasticsearch alias 原子操作與 zero-downtime reindex：`https://www.elastic.co/guide/en/elasticsearch/reference/current/aliases.html`

- [ ] **Step 5: 寫 Part E「跨服務長流程」**

使用以下關係圖，不展開框架 API：

```text
本地事務
+ Outbox 解決 dual write
+ Idempotency 吸收重複
+ Saga/TCC 協調業務結果
+ Durable Workflow 保存控制狀態
+ Reconciliation 收口
```

必須釐清：

- Outbox 保存已提交事實的可靠傳播，不是 workflow engine。
- Saga 用本地事務與補償收斂跨服務流程；補償是新業務動作，不是時間倒流。
- TCC 適合具有真實 Try/Confirm/Cancel 資源語義的場景。
- Durable workflow 保存流程進度、timer、retry 與 signal，但不替代服務內 invariant、帳本與對帳。
- transport delivery、handler processing、business effect 是三層；不得直接宣稱端到端 exactly-once。
- XA/2PC 的同步原子性以阻塞、參與者耦合與可用性為代價，不作長業務流程預設。

官方來源：

- AWS idempotent APIs：`https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/`
- AWS Transactional Outbox：`https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html`
- AWS Saga：`https://docs.aws.amazon.com/prescriptive-guidance/latest/modernization-data-persistence/saga-pattern.html`
- Temporal Durable Execution：`https://temporal.io/`

- [ ] **Step 6: 驗證方案、來源與本地深度連結**

Run:

```bash
rg -n '^## Part [DE]' system-design/11-並發正確性與長任務協調.md
rg -n 'Durable State|Lease|Heartbeat|Fencing|Immutable Batch|Reservation|Per-Key Serialization|Shadow Build' system-design/11-並發正確性與長任務協調.md
rg -n 'Outbox|Idempotency|Saga|TCC|Durable Workflow|Reconciliation|exactly-once|XA|2PC' system-design/11-並發正確性與長任務協調.md
rg -n 'kubernetes.io|docs.aws.amazon.com|aws.amazon.com|docs.stripe.com|elastic.co|temporal.io' system-design/11-並發正確性與長任務協調.md
test -e redis-handson/07-distributed-locks/README.md
test -e financial-consistency/05-patterns/README.md
test -e software-architecture/07-EventSourcing-領域事件-Saga.md
git diff --check
```

Expected:

- Part D、E 各出現一次。
- 六類長任務方案、跨服務組合術語與六個官方來源域名全部命中。
- 三個本地深度文件存在。
- `git diff --check` 無輸出、exit 0。

- [ ] **Step 7: 提交 Task 2**

```bash
git add system-design/11-並發正確性與長任務協調.md
git commit -m "docs(system-design): add long-task patterns"
```

---

### Task 3: 補齊故障、容量、閉環與決策樹

**Files:**
- Modify: `system-design/11-並發正確性與長任務協調.md`（接在 Part E 後）
- Reference: `concurrency-capacity/README.md`
- Reference: `financial-consistency/07-reconciliation/README.md`

**Interfaces:**
- Consumes: Task 2 的長任務與跨服務方案。
- Produces: 可逐場景驗收的 failure matrix、capacity trade-off、correctness loop、選型決策樹、反模式與章末自檢。

- [ ] **Step 1: 寫 Part F「完整故障矩陣」**

表格欄位固定為「失敗時點／可能出現的錯誤結果／必要控制／恢復與驗證」。至少包含：

1. 認領前 crash。
2. 認領後、執行前 crash。
3. 外部操作成功但回應丟失。
4. 本地提交成功但通知未發。
5. lease 過期後舊 worker 復活。
6. 新舊 worker 同時嘗試完成。
7. 補償失敗或結果未知。
8. 人工修復與自動恢復競爭。

矩陣必須實際使用 durable state、idempotency key、lease、fencing、retry、outbox、compensation、reconciliation、manual review，不得只列名詞。

- [ ] **Step 2: 寫 Part G「高併發與容量」**

依序說明：

- 熱點 invariant 的天然串行點；增加 worker 不能突破單資源序列化上限。
- lock hold time 與 hot-key throughput 的反比關係，只作量級直覺，不捏造通用 SLA。
- Optimistic CAS 在高衝突下的 retry amplification 與 retry storm。
- Queue 的削峰價值及 backlog、延遲、公平性、starvation 代價。
- resource-key partitioning 把全域串行縮小為局部串行。
- Reservation/Escrow 把單一總量競爭拆成可獨立消耗的能力。
- Backpressure、bounded retry、jitter 防止恢復流量形成第二次事故。

加入相對連結：`../concurrency-capacity/README.md`。

- [ ] **Step 3: 寫 Part H「正確性閉環」**

使用三層模型：

```text
預防：constraint / atomic transition / short lock / fencing / idempotency
檢測：metric / immutable audit fact / history / invariant checker / aging alarm
恢復：retry / reclaim / compensation / reconciliation / manual repair
```

明確說明：lock、lease、workflow 只能降低出錯機率；對帳與可解釋修復負責最後收口。加入相對連結：`../financial-consistency/07-reconciliation/README.md`。

- [ ] **Step 4: 寫 Part I「決策樹與反模式」**

決策樹按此順序：

1. 只需要有效執行者，還是需要保護業務資料？
2. 只需穩定輸入，還是來源資料也必須禁止修改？
3. 保護完整物件，還是可預留的稀缺能力？
4. 衝突頻率與重算成本如何？
5. 是否跨服務／資料庫／外部副作用？
6. timeout 後能否查詢結果，副作用能否冪等重試？
7. 是否要求審計、重放、對帳與人工修復？

反模式至少包含：長 DB transaction、Redis lock 當完整正確性保證、`PROCESSING` 無 owner/lease/fencing、retry 無 idempotency、snapshot 只存 ID、Saga 無補償失敗處理、只存當前狀態、沒有對帳與修復。

- [ ] **Step 5: 加入四個完整場景演練與章末自檢**

不用代碼，以決策鏈跑完：

- 批次統計：stable batch → immutable inputs/version → 長計算 → 結果綁 batch。
- 庫存預留：scarce capacity → hold/confirm/release → expiry/idempotency/reconciliation。
- 單 worker 任務：effective owner → lease/heartbeat/fencing → crash 接管。
- 跨服務訂單：local transaction → outbox → saga/workflow → compensation/reconciliation。

章末至少包含 spec「讀者與完成標準」中的十個自檢問題。

- [ ] **Step 6: 驗證 Part F–I、閉環與場景覆蓋**

Run:

```bash
rg -n '^## Part [FGHI]' system-design/11-並發正確性與長任務協調.md
rg -n '認領前|外部操作成功|lease 過期|補償失敗|人工修復' system-design/11-並發正確性與長任務協調.md
rg -n 'retry storm|Backpressure|starvation|resource key|Escrow' system-design/11-並發正確性與長任務協調.md
rg -n '預防|檢測|恢復|Reconciliation|Manual' system-design/11-並發正確性與長任務協調.md
rg -n '批次統計|庫存預留|單 worker|跨服務訂單' system-design/11-並發正確性與長任務協調.md
test -e concurrency-capacity/README.md
test -e financial-consistency/07-reconciliation/README.md
git diff --check
```

Expected:

- Part F、G、H、I 各出現一次。
- 故障、高併發、閉環與四個場景關鍵字全部命中。
- 兩個本地引用存在。
- `git diff --check` 無輸出、exit 0。

- [ ] **Step 7: 提交 Task 3**

```bash
git add system-design/11-並發正確性與長任務協調.md
git commit -m "docs(system-design): add failure decision model"
```

---

### Task 4: 接入全 repo 導航並完成文件驗證

**Files:**
- Modify: `system-design/README.md:21-58`
- Modify: `mysql-handson/06-locking/README.md:406-422`
- Modify: `redis-handson/07-distributed-locks/README.md:52-78`
- Modify: `financial-consistency/05-patterns/README.md:1-32`
- Modify: `software-architecture/07-EventSourcing-領域事件-Saga.md:55-116`
- Verify: `system-design/11-並發正確性與長任務協調.md`

**Interfaces:**
- Consumes: Task 1–3 完成的唯一主文與既有深度專題。
- Produces: 從 system-design 與四個領域入口可達的雙向導航；無第二份理論內容。

- [ ] **Step 1: 更新 `system-design/README.md`**

在 L0–L9 全景中，將新章標為跨 L2/L3 的「並發正確性與長任務協調」決策層；不要新造 L10。於本地章節清單加入：

```text
11-並發正確性與長任務協調.md | L2/L3 跨層 | invariant→短事務→長任務→跨服務→故障恢復→對帳
```

保留原有 L0–L9 架構與閱讀順序說明。

- [ ] **Step 2: 更新 MySQL 鎖章入口**

在 `## 4. 日常开发应用` 的「事务要短」之後增加一個短段落，內容只包含：

- DB row lock 保護本地短事務臨界區。
- 長任務若跨外部 I/O、進程 crash 或接管，不應持續占用 transaction。
- 依 invariant 選 immutable batch、logical freeze、reservation、lease/fencing 或 workflow。
- 連到 `../../system-design/11-並發正確性與長任務協調.md`。

不得在 MySQL 章重新解釋六類長任務方案。

- [ ] **Step 3: 更新 Redis distributed lock 入口**

在 `## 4. 日常开发应用` 或一句話總結前增加短段落，內容只包含：

- Redis lock／lease 協調 owner，不等於被保護資源本身的正確性。
- 強 invariant 需要 resource-side fencing、idempotency 或狀態機。
- 連到 `../../system-design/11-並發正確性與長任務協調.md`。

不得複製主文的 failure matrix。

- [ ] **Step 4: 更新 financial-consistency 與 software-architecture 入口**

`financial-consistency/05-patterns/README.md` 在學習順序前加入一段：先讀通用章辨認 invariant、boundary 與 failure model，再進入金融領域 pattern；相對連結為 `../../system-design/11-並發正確性與長任務協調.md`。

`software-architecture/07-EventSourcing-領域事件-Saga.md` 在 Part C Saga 開場或深礦提示中加入：Saga 只是跨服務長流程的一種協調方式；通用長任務、lease/fencing、batch、reservation 與 recovery 決策連到 `../system-design/11-並發正確性與長任務協調.md`。

- [ ] **Step 5: 驗證主文章節、占位符與官方來源**

Run:

```bash
for part in A B C D E F G H I; do count=$(rg -c "^## Part ${part}" system-design/11-並發正確性與長任務協調.md); test "$count" -eq 1 || { echo "Part $part count=$count"; exit 1; }; done
if rg -n 'T[B]D|T[O]DO|FIXM[E]|待[定]|待[補]|placeholde[r]' system-design/11-並發正確性與長任務協調.md system-design/README.md mysql-handson/06-locking/README.md redis-handson/07-distributed-locks/README.md financial-consistency/05-patterns/README.md software-architecture/07-EventSourcing-領域事件-Saga.md; then exit 1; else echo 'no incomplete markers'; fi
rg -n 'dev.mysql.com|kubernetes.io|docs.aws.amazon.com|aws.amazon.com|docs.stripe.com|elastic.co|temporal.io' system-design/11-並發正確性與長任務協調.md
```

Expected:

- Part A–I 各一次。
- 輸出 `no incomplete markers`。
- 七個官方來源域名全部可在主文找到；重複 AWS 域名可出現多次。

- [ ] **Step 6: 驗證六個文件的雙向導航與相對路徑**

Run:

```bash
rg -n '11-並發正確性與長任務協調' system-design/README.md mysql-handson/06-locking/README.md redis-handson/07-distributed-locks/README.md financial-consistency/05-patterns/README.md software-architecture/07-EventSourcing-領域事件-Saga.md
test -e system-design/11-並發正確性與長任務協調.md
test -e mysql-handson/06-locking/README.md
test -e redis-handson/07-distributed-locks/README.md
test -e financial-consistency/05-patterns/README.md
test -e software-architecture/07-EventSourcing-領域事件-Saga.md
```

Expected:

- 五個入口都命中新章名稱。
- 六個檔案全部存在。

- [ ] **Step 7: 驗證變更範圍與 Markdown 清潔度**

Run:

```bash
git diff --check d1bae98..HEAD
git diff --name-only d1bae98..HEAD \
  | rg -v '^docs/superpowers/plans/2026-07-16-concurrency-correctness-long-running-coordination.md$' \
  | sort
```

Expected file list:

```text
financial-consistency/05-patterns/README.md
mysql-handson/06-locking/README.md
redis-handson/07-distributed-locks/README.md
software-architecture/07-EventSourcing-領域事件-Saga.md
system-design/11-並發正確性與長任務協調.md
system-design/README.md
```

不得出現其他產品或 lab 文件。

- [ ] **Step 8: 提交導航與最終驗證修正**

```bash
git add system-design/README.md mysql-handson/06-locking/README.md redis-handson/07-distributed-locks/README.md financial-consistency/05-patterns/README.md software-architecture/07-EventSourcing-領域事件-Saga.md
git commit -m "docs(system-design): link coordination guide"
```

提交後重跑 Step 5–7；Expected 全部通過，`git status --short` 無本計畫相關未提交檔案。
