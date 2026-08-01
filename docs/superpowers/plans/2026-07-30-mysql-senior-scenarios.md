# MySQL 資深場景推理層 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不重複既有 canonical 教材的前提下，新增一個能把 MySQL 原理組裝成陌生場景答案的資深推理層，補齊 schema 設計、1,000 萬行匯入、歸檔刪除回收、報表匯出隔離四個真缺口，並留下誠實、可重跑的本機證據。

**Architecture:** `mysql-handson/01–11` 繼續擁有機制事實；`13-senior-scenarios` 只負責 `約束 → 執行鏈 → 成本／風險 → 基準方案 → 取捨 → 驗證／恢復` 的跨章組裝。實驗重用既有 MySQL 8.0.36 一般 lab，但只建立 `mysql_senior_scenarios` schema 與 `/private/tmp/mysql-senior-scenarios.*` runtime artifacts；不修改 Compose、Makefile、init 或 HA lab。每個 runnable scenario 先提交問題、預期、驗收與停止條件，再執行並以另一個 commit 記錄實際結果。

**Tech Stack:** Markdown（教材正文沿用簡體中文）、MySQL 8.0.36、InnoDB、Docker Compose、MySQL Connector/Python 9.7.0、`uv`、Bash／POSIX `awk`、`rg`、Git。

**Spec:** `docs/superpowers/specs/2026-07-30-mysql-senior-scenarios-design.md`

## Global Constraints

- 先在目前 `main` 將既有 7 份 MySQL 修改獨立提交；不得把 Elasticsearch、Java、learning-log、system-design 或任何其他 dirty file 混入。
- baseline commit 完成後，必須先使用 `superpowers:using-git-worktrees` 建立 `codex/mysql-senior-scenarios` 隔離分支／worktree，再開始 Task 2。
- 只新增 `mysql-handson/13-senior-scenarios/README.md` 與四篇場景文件；只修改 root `README.md`、ch10 與 ch12。此計畫不修改 `mysql-handson/00-lab/Makefile`、`docker-compose.yml`、`init/` 或任何 `00-lab/ha/` 文件。
- 不修改 `mysql-handson/09-replication-and-ha/`、`financial-consistency/`、`system-design-scenarios/`、`system-design/` 或 `mysql-es-cdc-handson/`；它們只作 canonical link target。
- 每類問題只有一個 scenario owner；ch13 只摘要跨章連接點，不複製 ch01–11 的長篇機制正文。
- 共用解題器固定為：`約束 → 執行鏈 → 成本／瓶頸 → 正確性／風險 → 基準方案 → 替代／取捨 → 驗證 → 恢復／回滾`。
- 每篇新場景都必須提供陌生 prompt、先答再讀、澄清問題、不變式、執行鏈、成本模型、基準方案、替代方案、停止條件、實驗、恢復邊界、30 秒答案、3–5 分鐘答案與追問樹。
- 證據標籤只允許 `REPRODUCED`、`SCALED_REPRODUCED`、`READY_UNRUN`、`REASONED`、`REUSED`；不得用語氣暗示未發生的實測。
- 固定規模為 S=`100000`、M=`1000000`、L=`10000000` rows。預設只跑 S；M／L 必須在 S 完成且資源 gate 通過後顯式執行。
- S／M 要在估算 peak 之外保留至少 5 GiB；L 要保留至少 10 GiB。未通過就記錄 gate 證據並保持較低證據等級。
- 本機結果只支援機制、相對趨勢與 correctness workflow；不得外推為生產 IOPS、吞吐、RPO、RTO 或容量上限。
- performance comparison 使用同一 MySQL version、schema、資料、durability 與背景負載，至少三次 comparable run；記錄 median、range 與 cold／hot cache 狀態。
- 任何性能結論之前，row count、fingerprint、duplicate、missing、reject、retry／restart 與 invariant 必須先通過。
- 一般 lab 可能由另一個 worktree 啟動。先用 Docker labels 查清 `mysql-primary` 的 owner；健康實例可以重用，未知／不健康實例不得停止、刪除或接管。
- 禁止執行 `make reset`、`docker compose down -v`、刪除未知 volume／container，或清理不符合 `/private/tmp/mysql-senior-scenarios.*` 的目錄。
- 所有資料庫物件都限制在精確 schema `mysql_senior_scenarios`；cleanup 只可 `DROP DATABASE mysql_senior_scenarios`，且必須先查證目前 database 名稱。
- 只有 bulk load scenario 可以暫時切換本機 lab 的 `local_infile`；執行前保存原值，在送出 enable statement 前記錄 restore intent，並在結束前用全新 admin connection 恢復、回讀確認；恢復無法確認時不得回報 `SUCCEEDED`，也不修改 durability、constraint 或 global buffer 設定。
- 所有 repository 文件修改使用 `apply_patch`；每次 commit 前列出 staged paths，禁止 `git add .`、`git add -A` 或 broad path staging。
- 任何 MySQL 版本相關主張都以官方 MySQL 8.0 reference manual／Connector 文檔重新核對；不以 blog 或記憶作唯一依據。

## Execution Prelude

Task 1 在目前 dirty `main` 執行，因為七份既有修改尚未存在於任何 commit。Task 1 完成後：

1. invoke `superpowers:using-git-worktrees`；
2. 從更新後的 `main` 建立 branch `codex/mysql-senior-scenarios`；
3. 在新 worktree 執行 Task 2–11；
4. 不移除目前列出的 detached／其他使用者 worktrees；
5. feature 完成後才 invoke `superpowers:finishing-a-development-branch` 決定整合方式。

## File Map

| 路徑 | 動作 | 單一責任 |
|---|---|---|
| `mysql-handson/01-architecture/README.md` | baseline commit only | 保存既有 Server／Engine 邊界修正 |
| `mysql-handson/03-indexing/README.md` | baseline commit only | 保存既有索引／ICP 深化 |
| `mysql-handson/03-indexing/scenarios/04-icp-on-off-comparison.md` | baseline commit only | 保存既有 ICP 實驗澄清 |
| `mysql-handson/04-execution-and-explain/README.md` | baseline commit only | 保存既有 optimizer／join 修正 |
| `mysql-handson/08-sql-tuning/README.md` | baseline commit only | 保存既有 JOIN／filesort／status 深化 |
| `mysql-handson/08-sql-tuning/scenarios/01-filesort-trigger-and-status.md` | baseline commit only | 保存既有 filesort 實驗修正 |
| `mysql-handson/12-interview-cheatsheet/README.md` | baseline + later pointer | 先保存既有速查修正；之後只加 ch13 短入口 |
| `mysql-handson/README.md` | modify | 增加資深面試閱讀路徑與 ch12／ch13 地圖 |
| `mysql-handson/10-sharding-and-scaling/README.md` | modify | 移除四個重複／不存在的 scenario links，改指 canonical owner |
| `mysql-handson/13-senior-scenarios/README.md` | create | 解題器、19 類 owner routing、證據標籤與練習方法 |
| `mysql-handson/13-senior-scenarios/01-schema-from-access-patterns.md` | create | access patterns 到 physical schema 的完整推導與 S 級證據 |
| `mysql-handson/13-senior-scenarios/02-bulk-load-10m.md` | create | 可恢復的 1,000 萬行匯入決策、S／M／L evidence |
| `mysql-handson/13-senior-scenarios/03-archive-delete-reclaim.md` | create | retention、archive、delete、purge、reclaim 的完整生命週期 |
| `mysql-handson/13-senior-scenarios/04-report-export-isolation.md` | create | snapshot、chunk、backpressure、resume、publish 與 OLTP 隔離 |

---

### Task 1: 保存並獨立提交現有 7 份 MySQL 修正

**Files:**
- Commit unchanged working-copy edits: `mysql-handson/01-architecture/README.md`
- Commit unchanged working-copy edits: `mysql-handson/03-indexing/README.md`
- Commit unchanged working-copy edits: `mysql-handson/03-indexing/scenarios/04-icp-on-off-comparison.md`
- Commit unchanged working-copy edits: `mysql-handson/04-execution-and-explain/README.md`
- Commit unchanged working-copy edits: `mysql-handson/08-sql-tuning/README.md`
- Commit unchanged working-copy edits: `mysql-handson/08-sql-tuning/scenarios/01-filesort-trigger-and-status.md`
- Commit unchanged working-copy edits: `mysql-handson/12-interview-cheatsheet/README.md`

**Interfaces:**
- Consumes: 目前主工作樹中已完成且尚未提交的七份 MySQL 文件修正。
- Produces: 一個只包含上述七個 paths 的 baseline commit，供隔離 worktree 繼承。

- [ ] **Step 1: 確認分支、HEAD 與 dirty file 邊界**

Run:

```bash
git status --short --branch
git rev-parse --short HEAD
```

Expected: branch 是 `main`；HEAD 至少包含設計 commit `0ecaaf9`；七份 MySQL 文件為 unstaged modified，其他 dirty files 仍存在但不屬本 task。

- [ ] **Step 2: 重新審閱七份 diff，不做新內容修改**

Run:

```bash
git diff -- mysql-handson/01-architecture/README.md mysql-handson/03-indexing/README.md mysql-handson/03-indexing/scenarios/04-icp-on-off-comparison.md mysql-handson/04-execution-and-explain/README.md mysql-handson/08-sql-tuning/README.md mysql-handson/08-sql-tuning/scenarios/01-filesort-trigger-and-status.md mysql-handson/12-interview-cheatsheet/README.md
```

Expected: diff 只包含先前已核對的 architecture、ICP、optimizer／join、filesort／status 與 cheatsheet 澄清；沒有 HA、CDC、ch10 或新 ch13 內容。

- [ ] **Step 3: 跑 baseline 靜態 gate**

Run:

```bash
git diff --check -- mysql-handson/01-architecture/README.md mysql-handson/03-indexing/README.md mysql-handson/03-indexing/scenarios/04-icp-on-off-comparison.md mysql-handson/04-execution-and-explain/README.md mysql-handson/08-sql-tuning/README.md mysql-handson/08-sql-tuning/scenarios/01-filesort-trigger-and-status.md mysql-handson/12-interview-cheatsheet/README.md
rg -n 'additional_fields|rowid|max_length_for_sort_data|Rows_examined|Index Condition Pushdown|Hash Join' mysql-handson/03-indexing/README.md mysql-handson/04-execution-and-explain/README.md mysql-handson/08-sql-tuning/README.md mysql-handson/12-interview-cheatsheet/README.md
```

Expected: `git diff --check` exit `0`；關鍵詞命中新的精確邊界，沒有用舊的 single-pass／two-pass filesort 名稱取代 MySQL 8.0 optimizer trace 名稱。

- [ ] **Step 4: 只 stage 七個精確 paths**

```bash
git add mysql-handson/01-architecture/README.md mysql-handson/03-indexing/README.md mysql-handson/03-indexing/scenarios/04-icp-on-off-comparison.md mysql-handson/04-execution-and-explain/README.md mysql-handson/08-sql-tuning/README.md mysql-handson/08-sql-tuning/scenarios/01-filesort-trigger-and-status.md mysql-handson/12-interview-cheatsheet/README.md
git diff --cached --name-only
git diff --cached --check
```

Expected: name list 恰好七行且只含上述 paths；cached check exit `0`。

- [ ] **Step 5: Commit baseline**

```bash
git commit -m "docs(mysql): clarify ICP, joins, and sort metrics"
```

- [ ] **Step 6: 驗證 commit 與未相關 dirt 都被保留**

Run:

```bash
git diff-tree --no-commit-id --name-status -r HEAD
git status --short --branch
```

Expected: commit 只有七個 MySQL paths；Elasticsearch、Java、learning-log、system-design 等原有 dirt 仍未 staged／未提交。

---

### Task 2: 建立 ch13 路由層並清除 ch10 重複 placeholder

**Files:**
- Create: `mysql-handson/13-senior-scenarios/README.md`
- Modify: `mysql-handson/README.md`
- Modify: `mysql-handson/10-sharding-and-scaling/README.md`
- Modify: `mysql-handson/12-interview-cheatsheet/README.md`

**Interfaces:**
- Consumes: 設計規格 §5 的 canonical ownership、§9 的 evidence labels，與 Task 1 已提交的 ch12 內容。
- Produces: 穩定的資深面試入口、19 類問題 owner map、四個新場景的未執行路徑，以及不再指向不存在文件的 ch10。

- [ ] **Step 1: 建立修改前的 failing／absence assertions**

Run:

```bash
test ! -e mysql-handson/13-senior-scenarios/README.md
rg -n '\*\(待[補]\)\*|scenarios/0[1-4]-' mysql-handson/10-sharding-and-scaling/README.md
! rg -n '13-senior-scenarios' mysql-handson/README.md mysql-handson/12-interview-cheatsheet/README.md
```

Expected: ch13 README 不存在；ch10 命中四個舊 links；root 與 ch12 尚未出現 ch13。

- [ ] **Step 2: 建立 ch13 README 的固定結構**

Use `apply_patch` to create the file with these exact top-level sections:

```markdown
# MySQL 资深场景推理

## 为什么学完原理仍答不出陌生题
## 一套可迁移的场景解题器
## 两遍练习法
## 19 类问题与唯一 owner
## 四个新增场景
## 证据等级
## 面试输出标准
## 与其他目录的边界
```

Required content:

- 第一段明說缺口是 cross-chapter assembly，不是再背參數；
- 解題器固定為八步，並要求先遮住正文口述；
- 兩遍練習法固定為：第一遍 30 秒收斂假設與 baseline，第二遍 3–5 分鐘補齊成本、風險、證據與 rollback；
- owner 表完整列出 spec §5.3 的 19 rows，每列只能有一個 scenario owner；
- 四個新檔尚未建立時，以 backticked path 和 `READY_UNRUN` 顯示，不建立 broken Markdown link；
- evidence table 精確定義五種允許標籤；
- outcome table 精確定義 `SUCCEEDED`、`FAILED`、`UNKNOWN`、`ABORTED`；其中 client 在 statement／commit 後失聯必須先查 batch identity，不能把 `UNKNOWN` 當 `FAILED` 自動重跑；
- 邊界段明說 ch01–11 是 mechanism owner、ch12 是 compression、99 是 closed-book、00-lab 是 evidence environment。

- [ ] **Step 3: 更新 root 閱讀路徑與章節地圖**

Use `apply_patch`:

- 在「怎么用这个 repo」加入一條「想练资深陌生题」入口，路徑為 `[13-senior-scenarios](13-senior-scenarios/README.md)`；
- 保留現有首次上手、99 cards、按章學習與新增 scenario 紀律；
- 在章節地圖的 ch11 之後加入 ch12 與 ch13：

```markdown
- `12-interview-cheatsheet/` — 章节知识的快速压缩，不承载长场景推导
- `13-senior-scenarios/` — 跨章陌生场景推理：约束、执行链、取舍、证据、恢复与口述
```

- 將資深面試閱讀路徑寫成 `01–11 → 13 → 12 → 99`。

- [ ] **Step 4: 把 ch10 四個不存在的 links 換成 canonical routes**

Use `apply_patch` to replace the final `## Scenarios` block with:

```markdown
## 延伸场景路由

- Hash 分片热点：本章 [Case A](#case-a分片键选错了导致热点) 已覆盖诊断与迁移取舍，不再维护重复 scenario。
- Snowflake 时钟回拨：见 [`distribution/分布式id.md`](../../distribution/分布式id.md)。
- 深分页与游标：见 [ch08 深分页实机 scenario](../08-sql-tuning/scenarios/03-deep-pagination-deferred-join.md)。
- 在线分片迁移：本章 [Case C](#case-c在线迁移-100-亿行历史数据) 负责迁移决策；CDC 消费、对账与重建证据见 [`mysql-es-cdc-handson`](../../mysql-es-cdc-handson/README.md)。
```

Before committing, verify GitHub-style anchors against the actual headings. If the generated Case C anchor removes spaces differently, change only the fragment so the link points to the existing `### Case C：在线迁移 100 亿行历史数据` heading.

- [ ] **Step 5: 在 ch12 只加短 pointer**

Immediately after the two opening blockquote lines, insert:

```markdown
> 遇到需要跨章节组合的陌生场景，先用 [ch13 资深场景推理](../13-senior-scenarios/README.md) 完成约束、执行链、取舍和验证，再回到本页压缩成面试答案。
```

Do not add any of the four new scenario answers to ch12.

- [ ] **Step 6: 跑路由與格式 gate**

Run:

```bash
rg -c '^\| ([1-9]|1[0-9]) \|' mysql-handson/13-senior-scenarios/README.md
rg -n 'REPRODUCED|SCALED_REPRODUCED|READY_UNRUN|REASONED|REUSED' mysql-handson/13-senior-scenarios/README.md
! rg -n '\*\(待[補]\)\*|scenarios/0[1-4]-' mysql-handson/10-sharding-and-scaling/README.md
rg -n '01–11.*13.*12.*99|13-senior-scenarios' mysql-handson/README.md mysql-handson/12-interview-cheatsheet/README.md
git diff --check -- mysql-handson/README.md mysql-handson/10-sharding-and-scaling/README.md mysql-handson/12-interview-cheatsheet/README.md mysql-handson/13-senior-scenarios/README.md
```

Expected: owner rows=`19`；五種 evidence labels 都命中；ch10 舊 links 無輸出；兩個入口與閱讀順序命中；diff check exit `0`。

- [ ] **Step 7: Commit routing layer**

```bash
git add mysql-handson/README.md mysql-handson/10-sharding-and-scaling/README.md mysql-handson/12-interview-cheatsheet/README.md mysql-handson/13-senior-scenarios/README.md
git diff --cached --name-only
git commit -m "docs(mysql): add senior scenario routing"
```

Expected staged names: exactly four paths.

---

### Task 3: 寫 schema-from-access-patterns 的問題、預期與完整推導

**Files:**
- Create: `mysql-handson/13-senior-scenarios/01-schema-from-access-patterns.md`
- Modify: `mysql-handson/13-senior-scenarios/README.md`

**Interfaces:**
- Consumes: ch03 composite／covering index、ch04 `EXPLAIN ANALYZE`、ch07 write amplification、ch10 retention／sharding boundaries。
- Produces: 固定 `tenant_record` running case、baseline／over-indexed DDL、S 級實驗契約；Task 4 只填實際 evidence，不改原始 hypothesis。

- [ ] **Step 1: 確認場景文件尚不存在，README 仍標記未執行 path**

Run:

```bash
test ! -e mysql-handson/13-senior-scenarios/01-schema-from-access-patterns.md
rg -n '01-schema-from-access-patterns.md.*READY_UNRUN' mysql-handson/13-senior-scenarios/README.md
```

- [ ] **Step 2: 寫固定 prompt、access patterns 與 invariants**

Create the document with the 12-section contract from the spec. The prompt must ask for a multi-tenant write-heavy record table with these fixed operations:

```text
1. id 精确点查；
2. tenant_id + status + created_at + id 稳定倒序翻页；
3. tenant 内 external_request_id 唯一；
4. amount/currency/status 有数据库可执行约束；
5. payload 是冷字段，不进入主列表索引；
6. created_at 到期后可归档；
7. 峰值写入会被每个 secondary index 放大。
```

Fixed invariants:

- `id` globally unique and immutable；
- `(tenant_id, external_request_id)` unique；
- `amount >= 0`；
- `currency` exactly three ASCII characters；
- `status` only `0,1,2,3`；
- pagination order is `(created_at DESC, id DESC)`；
- retention does not delete legal-hold records；
- no index is justified without a named access pattern。

- [ ] **Step 3: 寫 baseline DDL 與 query contracts**

Include this baseline shape; names and key order are fixed so Task 4 can run it verbatim:

```sql
CREATE DATABASE IF NOT EXISTS mysql_senior_scenarios
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE mysql_senior_scenarios;

CREATE TABLE tenant_record_baseline (
  id                  BIGINT UNSIGNED NOT NULL,
  tenant_id           BIGINT UNSIGNED NOT NULL,
  external_request_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  status              TINYINT UNSIGNED NOT NULL,
  amount              DECIMAL(18,2) NOT NULL,
  currency            CHAR(3) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  created_at          DATETIME(6) NOT NULL,
  updated_at          DATETIME(6) NOT NULL,
  legal_hold          BOOLEAN NOT NULL DEFAULT FALSE,
  payload             JSON NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_tenant_request (tenant_id, external_request_id),
  KEY idx_tenant_status_created (tenant_id, status, created_at DESC, id DESC),
  CONSTRAINT chk_tenant_record_status CHECK (status IN (0,1,2,3)),
  CONSTRAINT chk_tenant_record_amount CHECK (amount >= 0),
  CONSTRAINT chk_tenant_record_currency CHECK (CHAR_LENGTH(currency) = 3)
) ENGINE=InnoDB;
```

Representative queries:

```sql
SELECT id, tenant_id, status, amount, currency, created_at
FROM tenant_record_baseline
WHERE id = ?;

SELECT id, status, amount, currency, created_at
FROM tenant_record_baseline
WHERE tenant_id = ?
  AND status = ?
  AND (created_at, id) < (?, ?)
ORDER BY created_at DESC, id DESC
LIMIT 50;
```

Explain why `payload` is not placed in the listing index, why a narrow BIGINT primary key is repeated into every secondary leaf, and why `uk_tenant_request` protects an invariant rather than merely speeding a query.

- [ ] **Step 4: 定義 over-indexed 對照與 expected inequalities**

The over-indexed table uses the same columns and required keys, plus these redundant indexes:

```sql
CREATE TABLE tenant_record_overindexed LIKE tenant_record_baseline;
ALTER TABLE tenant_record_overindexed
  ADD KEY idx_status (status),
  ADD KEY idx_created (created_at),
  ADD KEY idx_tenant_created (tenant_id, created_at, id),
  ADD KEY idx_currency (currency),
  ADD KEY idx_wide_listing
    (tenant_id, status, created_at, id, amount, currency);
```

Write hypotheses before any run:

- both tables preserve the same business invariants and return the same rows；
- the representative listing query should not need the redundant single-column indexes；
- over-indexed `INDEX_LENGTH` should be larger；
- inserting the same source rows should not write less redo or finish faster because every extra B+ tree must be maintained；
- exact ratios remain unknown until Task 4 and must not be invented。

At the top evidence table, mark the physical-design reasoning `REASONED` and the S comparison `READY_UNRUN`.

- [ ] **Step 5: 寫成本模型、替代方案與面試輸出**

Required formulas／decision points:

```text
secondary leaf entry ≈ secondary key bytes + primary-key bytes + record overhead
write work per row ≈ 1 clustered-tree change + N secondary-tree changes + undo + redo + binlog
index decision = named access pattern benefit - write/storage/cache/DDL cost
```

Cover surrogate vs natural key, `DECIMAL` vs floating point, `DATETIME(6)` vs timestamp semantics, CHECK／foreign-key boundaries, normalization vs snapshot columns, cold-column split, partitioning only when retention/query keys align, and when not to use a covering index.

The 30-second answer must include access patterns, invariants, one baseline index and verification. The 3–5-minute answer must walk through key width, query order, write amplification, alternatives, `EXPLAIN ANALYZE`, size evidence and migration／rollback.

- [ ] **Step 6: 加 canonical links 並把 README path 轉成真 link**

At minimum link to:

```markdown
[ch02 InnoDB storage](../02-innodb-storage/README.md)
[ch03 indexing](../03-indexing/README.md)
[ch04 execution and Explain](../04-execution-and-explain/README.md)
[ch07 logs and crash safety](../07-logs-and-crashsafe/README.md)
[ch10 sharding and scaling](../10-sharding-and-scaling/README.md)
```

Update the ch13 README row from a backticked path to `[从 access patterns 设计 schema](01-schema-from-access-patterns.md)` while keeping evidence status `READY_UNRUN`.

- [ ] **Step 7: Verify expectation document**

Run:

```bash
rg -n '^## (陌生题目|先停下来回答|澄清问题|业务不变式与完成标准|跨章执行链|成本与瓶颈模型|推荐基准方案|替代方案与取舍|执行计划与停止条件|缩小规模实验与证据|生产边界、恢复与回滚|面试输出)$' mysql-handson/13-senior-scenarios/01-schema-from-access-patterns.md
rg -n 'READY_UNRUN|tenant_record_baseline|uk_tenant_request|idx_tenant_status_created|idx_wide_listing|30 秒|3–5 分钟' mysql-handson/13-senior-scenarios/01-schema-from-access-patterns.md
git diff --check -- mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/01-schema-from-access-patterns.md
```

Expected: 12 headings all match；hypothesis remains unrun；DDL and both answer lengths are present；diff check exit `0`。

- [ ] **Step 8: Commit expectation before running MySQL**

```bash
git add mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/01-schema-from-access-patterns.md
git commit -m "docs(mysql): define access-pattern schema scenario"
```

---

### Task 4: 跑 schema S 級對照並記錄實際 evidence

**Files:**
- Modify: `mysql-handson/13-senior-scenarios/01-schema-from-access-patterns.md`
- Modify: `mysql-handson/13-senior-scenarios/README.md`

**Interfaces:**
- Consumes: Task 3 immutable hypothesis, healthy general `mysql-primary`, exact schema `mysql_senior_scenarios`。
- Produces: 三次 baseline／over-indexed insert comparison、plans、sizes、correctness 與 expectation gap。

- [ ] **Step 1: Preflight container ownership without mutating it**

Run:

```bash
docker ps -a --filter name=^/mysql-primary$ --format '{{.ID}} {{.Status}} {{.Labels}}'
docker inspect -f '{{.State.Health.Status}} {{index .Config.Labels "com.docker.compose.project"}} {{index .Config.Labels "com.docker.compose.project.working_dir"}}' mysql-primary
docker exec mysql-primary mysql -uroot -proot -Nse "SELECT VERSION(), @@version_comment, @@innodb_flush_log_at_trx_commit, @@sync_binlog, @@binlog_format"
df -k /private/tmp
```

Expected: `mysql-primary` is healthy, project is `mysql-handson`, MySQL is `8.0.36`, durability baseline is recorded, and free disk exceeds estimated S peak + 5 GiB. If the named container is absent, start only the base service with `make -C mysql-handson/00-lab up`; if it exists but is unhealthy or has an unexpected project label, stop this task without changing Docker state.

- [ ] **Step 2: Record host and run identity**

Run:

```bash
date -u +%Y%m%dT%H%M%SZ
uname -a
sysctl -n hw.memsize
docker stats --no-stream mysql-primary
```

Save the UTC value as the document's run ID. Record exact outputs in a compact environment table; do not commit raw secrets or unrelated container details.

- [ ] **Step 3: Create the S source and two target tables**

Use the DDL already committed in Task 3. Add a source table with the same columns but only a primary key, then seed exactly 100,000 deterministic rows through six cross-joined digit sets:

The helper is an ordinary namespaced table because MySQL cannot reopen one temporary table through multiple aliases in the same statement. It is removed before timing so it does not affect the experiment.

```sql
USE mysql_senior_scenarios;

CREATE TABLE tenant_record_source LIKE tenant_record_baseline;
ALTER TABLE tenant_record_source
  DROP INDEX uk_tenant_request,
  DROP INDEX idx_tenant_status_created;

DROP TABLE IF EXISTS seed_digit;
CREATE TABLE seed_digit (d TINYINT UNSIGNED PRIMARY KEY);
INSERT INTO seed_digit VALUES (0),(1),(2),(3),(4),(5),(6),(7),(8),(9);

INSERT INTO tenant_record_source
  (id, tenant_id, external_request_id, status, amount, currency,
   created_at, updated_at, legal_hold, payload)
SELECT n,
       MOD(n, 1000) + 1,
       CONCAT('req-', LPAD(n, 12, '0')),
       MOD(n, 4),
       MOD(n, 100000) / 100,
       ELT(MOD(n, 3) + 1, 'USD', 'TWD', 'JPY'),
       TIMESTAMPADD(SECOND, n, '2026-01-01 00:00:00'),
       TIMESTAMPADD(SECOND, n, '2026-01-01 00:00:00'),
       MOD(n, 10000) = 0,
       JSON_OBJECT('n', n, 'note', CONCAT('payload-', n))
FROM (
  SELECT 1 + d0.d + 10*d1.d + 100*d2.d + 1000*d3.d
           + 10000*d4.d + 100000*d5.d AS n
  FROM seed_digit AS d0
  CROSS JOIN seed_digit AS d1
  CROSS JOIN seed_digit AS d2
  CROSS JOIN seed_digit AS d3
  CROSS JOIN seed_digit AS d4
  CROSS JOIN seed_digit AS d5
  ORDER BY n
  LIMIT 100000
) AS seq;

DROP TABLE seed_digit;
```

The generated values are fixed:

```sql
id                  = n
tenant_id           = MOD(n, 1000) + 1
external_request_id = CONCAT('req-', LPAD(n, 12, '0'))
status              = MOD(n, 4)
amount              = MOD(n, 100000) / 100
currency            = ELT(MOD(n, 3) + 1, 'USD', 'TWD', 'JPY')
created_at           = TIMESTAMP('2026-01-01 00:00:00') + INTERVAL n SECOND
updated_at           = created_at
legal_hold           = MOD(n, 10000) = 0
payload              = JSON_OBJECT('n', n, 'note', CONCAT('payload-', n))
```

Verify:

```sql
SELECT COUNT(*), MIN(id), MAX(id), COUNT(DISTINCT id)
FROM mysql_senior_scenarios.tenant_record_source;
```

Expected: `100000, 1, 100000, 100000`.

- [ ] **Step 4: Run six alternating insert trials**

Use order `baseline, overindexed, overindexed, baseline, baseline, overindexed`. For each trial use the following block with the literal allowlisted table name. The committed scenario must show one complete block for `tenant_record_baseline` and one for `tenant_record_overindexed`; it must not leave `target_table` as executable SQL:

```sql
TRUNCATE TABLE target_table;
SET @redo_before = (
  SELECT CAST(VARIABLE_VALUE AS UNSIGNED)
  FROM performance_schema.global_status
  WHERE VARIABLE_NAME = 'Innodb_os_log_written'
);
SET @started = NOW(6);
INSERT INTO tenant_record_baseline SELECT * FROM tenant_record_source;
SET @elapsed_us = TIMESTAMPDIFF(MICROSECOND, @started, NOW(6));
SET @redo_after = (
  SELECT CAST(VARIABLE_VALUE AS UNSIGNED)
  FROM performance_schema.global_status
  WHERE VARIABLE_NAME = 'Innodb_os_log_written'
);
SELECT @elapsed_us / 1000000 AS seconds,
       @redo_after - @redo_before AS redo_bytes,
       (SELECT COUNT(*) FROM tenant_record_baseline) AS rows_loaded;
```

Do not `FLUSH STATUS`; use pre／post deltas. Record all six values, then report median and min–max for each table.

- [ ] **Step 5: Verify plans, index size and invariants**

Run `ANALYZE TABLE` on both targets, then execute:

```sql
EXPLAIN ANALYZE
SELECT id, status, amount, currency, created_at
FROM tenant_record_baseline
WHERE tenant_id = 42 AND status = 1
  AND (created_at, id) < ('2026-01-02 00:00:00.000000', 86400)
ORDER BY created_at DESC, id DESC
LIMIT 50;

SELECT TABLE_NAME, TABLE_ROWS, DATA_LENGTH, INDEX_LENGTH, DATA_FREE
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'mysql_senior_scenarios'
  AND TABLE_NAME IN ('tenant_record_baseline', 'tenant_record_overindexed');
```

For both targets also verify count, min／max id, distinct id, unique request count, legal-hold count, and a lab fingerprint using `BIT_XOR(CRC32(CONCAT_WS('#', id, tenant_id, external_request_id, status, amount, currency, created_at, legal_hold)))`. Label the CRC aggregate as a lab fingerprint, not a cryptographic proof.

- [ ] **Step 6: Patch actual evidence without rewriting the hypothesis**

Use `apply_patch` to add:

- environment／run ID；
- all six trial rows plus median／range；
- both `EXPLAIN ANALYZE` plan summaries；
- data／index size table；
- correctness outputs；
- explicit「我以为／实际／我学到」gap；
- `REPRODUCED` only for this exact S comparison；
- `REASONED` for production schema implications。

Update ch13 README's schema row to show `REPRODUCED (S=100000)` without changing other scenario statuses.

- [ ] **Step 7: Verify evidence claims and commit**

Run:

```bash
rg -n 'run ID|100000|median|min–max|REPRODUCED|REASONED|我以为|实际|我学到' mysql-handson/13-senior-scenarios/01-schema-from-access-patterns.md
! rg -n 'READY_UNRUN' mysql-handson/13-senior-scenarios/01-schema-from-access-patterns.md
git diff --check -- mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/01-schema-from-access-patterns.md
git add mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/01-schema-from-access-patterns.md
git commit -m "docs(mysql): record schema design evidence"
```

Expected: scenario file has no remaining unrun claim for its S experiment; commit only contains two ch13 files.

---
### Task 5: 寫 1,000 萬行 bulk load 的問題、預期與 runner 契約

**Files:**
- Create: `mysql-handson/13-senior-scenarios/02-bulk-load-10m.md`
- Modify: `mysql-handson/13-senior-scenarios/README.md`

**Interfaces:**
- Consumes: ch02 page／buffer pool、ch03 index maintenance、ch07 redo／binlog、ch09 replica apply、ch11 operations boundaries；`uv run --with mysql-connector-python==9.7.0`。
- Produces: immutable TSV manifest、single-row／driver batch／`LOAD DATA LOCAL` 三條可比較路徑、S／M／L gate；Task 6 只執行與填 evidence。

- [ ] **Step 1: 確認文件不存在且 route 尚未連結**

Run:

```bash
test ! -e mysql-handson/13-senior-scenarios/02-bulk-load-10m.md
rg -n '02-bulk-load-10m.md.*READY_UNRUN' mysql-handson/13-senior-scenarios/README.md
```

- [ ] **Step 2: 寫 prompt、澄清問題與完成標準**

The prompt is exactly: 「有一个 1,000 万行 TSV，要尽快导入 MySQL。你会怎么做，为什么，如何证明没有漏、重、错，失败后怎么继续？」

The clarification tree must branch on:

- empty staging table vs empty final table vs hot existing table；
- source file location／trust／immutability；
- row width、secondary indexes、unique／foreign keys、triggers、generated columns；
- allowed downtime、retry、reject handling、publish semantics；
- binlog／replica／HA and allowed lag；
- input regenerate ability、checkpoint identity、disk and completion SLA。

Completion requires an immutable manifest, exact accepted／rejected counts, duplicate／missing explanation, table fingerprint, restart rule, publish boundary and rollback source. Fast elapsed time alone is not completion.

- [ ] **Step 3: 寫 baseline decision tree 與 execution chain**

The recommended baseline is:

```text
immutable input + manifest
  → namespaced staging table
  → choose LOAD DATA or parameterized driver batches
  → increment batch size and concurrency from one worker
  → watch redo/checkpoint/binlog/replica and correctness
  → validate counts/fingerprint/rejects
  → controlled publish or merge
  → retain run ID and restart watermark
```

The execution chain must explicitly name source parse, client/server transfer or server file read, conversion, duplicate／constraint checks, clustered and secondary B+ tree changes, undo／redo／binlog, dirty pages／checkpoint／fsync, replica receive／persist／apply.

Alternatives must state:

- `LOAD DATA` is the baseline when the file shape is compatible and loading can be isolated；
- parameterized `executemany()` batches are the baseline when application validation／conversion／checkpointing is required；
- single-row autocommit is only the control, not the recommendation；
- rebuilding secondary indexes is considered only for an isolated reconstructible table with disk／publish plan；
- global durability weakening, blind foreign-key／unique-check disabling and hot-table index removal are not defaults。

- [ ] **Step 4: 定義三張相同 target tables 與 deterministic TSV**

Include exact DDL:

```sql
USE mysql_senior_scenarios;

CREATE TABLE bulk_template (
  id         BIGINT UNSIGNED NOT NULL,
  tenant_id  BIGINT UNSIGNED NOT NULL,
  status     TINYINT UNSIGNED NOT NULL,
  payload    VARCHAR(128) NOT NULL,
  created_at DATETIME(6) NOT NULL,
  PRIMARY KEY (id),
  KEY idx_tenant_created (tenant_id, created_at, id),
  CONSTRAINT chk_bulk_status CHECK (status IN (0,1,2,3))
) ENGINE=InnoDB;

CREATE TABLE bulk_single LIKE bulk_template;
CREATE TABLE bulk_batch  LIKE bulk_template;
CREATE TABLE bulk_load   LIKE bulk_template;
```

The runtime input generator is fixed and excluded from load timing:

```bash
MYSQL_SCENARIO_ROWS=100000
MYSQL_SCENARIO_RUN_DIR=$(mktemp -d /private/tmp/mysql-senior-scenarios.XXXXXX)
LC_ALL=C awk -v rows="$MYSQL_SCENARIO_ROWS" 'BEGIN {
  OFS="\t";
  for (i=1; i<=rows; i++) {
    day=(i%28)+1;
    printf "%d\t%d\t%d\tpayload-%012d\t2026-01-%02d 12:00:00.000000\n",
           i, (i%1000)+1, i%4, i, day;
  }
}' > "$MYSQL_SCENARIO_RUN_DIR/input.tsv"
wc -l -c "$MYSQL_SCENARIO_RUN_DIR/input.tsv"
shasum -a 256 "$MYSQL_SCENARIO_RUN_DIR/input.tsv"
```

The document must warn that the run directory is runtime data, not committed evidence; only its manifest and measured summary enter Markdown.

- [ ] **Step 5: 嵌入 exact `bulk_runner.py` interface and behavior**

The document contains a copyable Python block with this CLI:

```text
--mode single|batch|load
--table bulk_single|bulk_batch|bulk_load
--input /absolute/path/input.tsv
--batch-size 1000
--host 127.0.0.1
--port 3306
--user root
--password root
```

CLI/result contract: exact lone `-h` or lone `--help` is the only normal
plaintext zero-exit path. Every other invocation emits exactly one final JSON
object after cleanup: exit `0` only for
`status="SUCCEEDED", phase="VERIFIED"`, otherwise exit `2` with
`status="FAILED"` or `status="UNKNOWN"`, the operation／cleanup phase,
rollback-confirmation state and a redacted error.

Use this complete implementation in the embedded block:

```python
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import zlib
from datetime import datetime
from pathlib import Path
from typing import Iterable

import mysql.connector
from mysql.connector import Error as ConnectorError
from mysql.connector.errors import (
    InterfaceError,
    ReadTimeoutError,
    WriteTimeoutError,
)


ALLOWED_TABLES = {
    "single": "bulk_single",
    "batch": "bulk_batch",
    "load": "bulk_load",
}
INSERT_SQL = (
    "INSERT INTO `{table}` "
    "(id,tenant_id,status,payload,created_at) VALUES (%s,%s,%s,%s,%s)"
)
STATUS_NAMES = (
    "Innodb_os_log_written",
    "Innodb_data_written",
    "Bytes_received",
)
PHASES = {
    "VALIDATING",
    "BEFORE_SEND",
    "SESSION_SETTING",
    "GLOBAL_SETTING",
    "EXECUTING",
    "COMMITTING",
    "VERIFYING",
    "ROLLING_BACK",
    "RESTORING",
    "CLOSING",
    "VERIFIED",
}


class ContractError(Exception):
    pass


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ContractError(message)


def parse_row(fields: list[str]) -> tuple[int, int, int, str, str]:
    if len(fields) != 5:
        raise ValueError(f"expected 5 TSV fields, got {len(fields)}")
    row_id, tenant_id, status = map(int, fields[:3])
    payload, created_at = fields[3], fields[4]
    if row_id < 1 or tenant_id < 1 or status not in (0, 1, 2, 3):
        raise ValueError(f"invalid row values: {fields!r}")
    if "\t" in payload or "\n" in payload:
        raise ValueError("payload contains a TSV delimiter")
    try:
        parsed_created_at = datetime.strptime(
            created_at, "%Y-%m-%d %H:%M:%S.%f"
        )
    except ValueError as exc:
        raise ValueError("created_at must include microseconds") from exc
    return (
        row_id,
        tenant_id,
        status,
        payload,
        parsed_created_at.strftime("%Y-%m-%d %H:%M:%S.%f"),
    )


def iter_rows(path: Path) -> Iterable[tuple[int, int, int, str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for line_number, fields in enumerate(reader, start=1):
            try:
                yield parse_row(fields)
            except Exception as exc:
                raise ValueError(f"line {line_number}: {exc}") from exc


def source_manifest(path: Path) -> dict[str, int]:
    count = 0
    min_id = 0
    max_id = 0
    previous_id = 0
    lab_fingerprint = 0
    for row in iter_rows(path):
        row_id, tenant_id, status, payload, created_at = row
        if row_id <= previous_id:
            raise ContractError(
                "source ids must be unique and strictly increasing"
            )
        previous_id = row_id
        count += 1
        if count == 1:
            min_id = row_id
        max_id = row_id
        encoded = "#".join(
            (str(row_id), str(tenant_id), str(status), payload, created_at)
        ).encode("utf-8")
        lab_fingerprint ^= zlib.crc32(encoded) & 0xFFFFFFFF
    return {
        "count": count,
        "min_id": min_id,
        "max_id": max_id,
        "distinct_id": count,
        "lab_fingerprint": lab_fingerprint,
    }


def status_snapshot(cursor) -> dict[str, int]:
    quoted = ",".join(f"'{name}'" for name in STATUS_NAMES)
    cursor.execute(
        f"SHOW GLOBAL STATUS WHERE Variable_name IN ({quoted})"
    )
    values = {str(name): int(value) for name, value in cursor.fetchall()}
    return {name: values.get(name, 0) for name in STATUS_NAMES}


def load_single(connection, table: str, rows, phase: dict[str, str]) -> int:
    phase["value"] = "SESSION_SETTING"
    connection.autocommit = True
    phase["value"] = "BEFORE_SEND"
    cursor = connection.cursor()
    statement = INSERT_SQL.format(table=table)
    accepted = 0
    for row in rows:
        phase["value"] = "EXECUTING"
        cursor.execute(statement, row)
        accepted += 1
        phase["value"] = "BEFORE_SEND"
    phase["value"] = "CLOSING"
    cursor.close()
    phase["value"] = "BEFORE_SEND"
    return accepted


def load_batches(
    connection,
    table: str,
    rows,
    batch_size: int,
    phase: dict[str, str],
) -> int:
    phase["value"] = "SESSION_SETTING"
    connection.autocommit = False
    phase["value"] = "BEFORE_SEND"
    cursor = connection.cursor()
    statement = INSERT_SQL.format(table=table)
    accepted = 0
    batch: list[tuple[int, int, int, str, str]] = []
    for row in rows:
        batch.append(row)
        if len(batch) < batch_size:
            continue
        phase["value"] = "EXECUTING"
        cursor.executemany(statement, batch)
        phase["value"] = "COMMITTING"
        connection.commit()
        accepted += len(batch)
        batch.clear()
        phase["value"] = "BEFORE_SEND"
    if batch:
        phase["value"] = "EXECUTING"
        cursor.executemany(statement, batch)
        phase["value"] = "COMMITTING"
        connection.commit()
        accepted += len(batch)
        phase["value"] = "BEFORE_SEND"
    phase["value"] = "CLOSING"
    cursor.close()
    phase["value"] = "BEFORE_SEND"
    return accepted


def fingerprint(cursor, table: str) -> dict[str, int]:
    cursor.execute(
        "SELECT COUNT(*), COALESCE(MIN(id),0), COALESCE(MAX(id),0), "
        "COUNT(DISTINCT id), "
        "COALESCE(BIT_XOR(CRC32(CONCAT_WS('#',id,tenant_id,status,payload,created_at))),0) "
        f"FROM `{table}`"
    )
    count, min_id, max_id, distinct_id, crc = cursor.fetchone()
    return {
        "count": int(count),
        "min_id": int(min_id),
        "max_id": int(max_id),
        "distinct_id": int(distinct_id),
        "lab_fingerprint": int(crc),
    }


def require_manifest_match(
    source: dict[str, int],
    target: dict[str, int],
    accepted: int,
) -> None:
    mismatches: dict[str, object] = {}
    if accepted != source["count"]:
        mismatches["accepted"] = {
            "expected": source["count"],
            "actual": accepted,
        }
    for name in (
        "count",
        "min_id",
        "max_id",
        "distinct_id",
        "lab_fingerprint",
    ):
        if target[name] != source[name]:
            mismatches[name] = {
                "expected": source[name],
                "actual": target[name],
            }
    if mismatches:
        raise ContractError(
            f"source/target manifest mismatch: {json.dumps(mismatches, sort_keys=True)}"
        )


def load_local_file(
    connection,
    table: str,
    path: Path,
    source: dict[str, int],
    phase: dict[str, str],
) -> tuple[int, int, int]:
    if "'" in str(path):
        raise ValueError("input path may not contain a single quote")
    phase["value"] = "SESSION_SETTING"
    connection.autocommit = False
    phase["value"] = "BEFORE_SEND"
    cursor = connection.cursor()
    phase["value"] = "EXECUTING"
    cursor.execute(
        "LOAD DATA LOCAL INFILE "
        f"'{path.as_posix()}' INTO TABLE `{table}` "
        "FIELDS TERMINATED BY '\\t' LINES TERMINATED BY '\\n' "
        "(id,tenant_id,status,payload,created_at)"
    )
    warning_count = int(cursor.warning_count or 0)
    accepted = int(cursor.rowcount)
    rejected = max(source["count"] - accepted, 0)
    if warning_count != 0 or rejected != 0 or accepted != source["count"]:
        raise ContractError(
            "LOAD DATA warnings/rejects: "
            f"warnings={warning_count}, rejected={rejected}, "
            f"accepted={accepted}, expected={source['count']}"
        )
    phase["value"] = "VERIFYING"
    uncommitted_target = fingerprint(cursor, table)
    require_manifest_match(source, uncommitted_target, accepted)
    phase["value"] = "COMMITTING"
    connection.commit()
    phase["value"] = "CLOSING"
    cursor.close()
    phase["value"] = "BEFORE_SEND"
    return accepted, warning_count, rejected


def classify(
    exc: BaseException,
    failure_phase: str,
    rollback_confirmed: bool,
    cleanup_errors: list[tuple[str, BaseException]],
) -> str:
    if cleanup_errors:
        return "UNKNOWN"
    if failure_phase == "COMMITTING":
        return "UNKNOWN"
    if (
        failure_phase in {
            "SESSION_SETTING",
            "GLOBAL_SETTING",
            "EXECUTING",
            "VERIFYING",
        }
        and (
            isinstance(
                exc,
                (
                    InterfaceError,
                    ReadTimeoutError,
                    WriteTimeoutError,
                    TimeoutError,
                ),
            )
            or getattr(exc, "errno", None) in (2006, 2013, 2055)
        )
    ):
        return "UNKNOWN"
    if isinstance(exc, (ContractError, ValueError)):
        return "FAILED"
    if failure_phase in ("VALIDATING", "BEFORE_SEND"):
        return "FAILED"
    if (
        failure_phase in {
            "SESSION_SETTING",
            "GLOBAL_SETTING",
            "EXECUTING",
            "VERIFYING",
        }
        and isinstance(exc, ConnectorError)
        and rollback_confirmed
    ):
        return "FAILED"
    return "UNKNOWN"


def restore_local_infile(config: dict, original: int) -> None:
    admin_config = {
        name: config[name] for name in ("host", "port", "user", "password")
    }
    admin = None
    cursor = None
    failure: BaseException | None = None
    try:
        admin = mysql.connector.connect(
            **admin_config,
            allow_local_infile=True,
        )
        cursor = admin.cursor()
        cursor.execute(f"SET GLOBAL local_infile={int(original)}")
        cursor.execute("SELECT @@GLOBAL.local_infile")
        restored = int(cursor.fetchone()[0])
        if restored != int(original):
            raise ContractError(
                f"local_infile restoration mismatch: expected {original}, got {restored}"
            )
    except BaseException as exc:
        failure = exc
    if cursor is not None:
        try:
            cursor.close()
        except BaseException as exc:
            if failure is None:
                failure = exc
    if admin is not None:
        try:
            admin.close()
        except BaseException as exc:
            if failure is None:
                failure = exc
    if failure is not None:
        raise failure


def supplied_password(arguments: list[str]) -> str | None:
    for index, argument in enumerate(arguments):
        if argument == "--password" and index + 1 < len(arguments):
            return arguments[index + 1]
        if argument.startswith("--password="):
            return argument.split("=", 1)[1]
    return None


def redact(value: object, password: str | None) -> str:
    text = str(value)
    return text.replace(password, "***") if password else text


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    password = supplied_password(arguments)
    lone_help = arguments in (["-h"], ["--help"])
    has_help_token = any(
        argument in ("-h", "--help") for argument in arguments
    )
    malformed_short_help = any(
        argument.startswith("-h")
        and not argument.startswith("--")
        and argument != "-h"
        for argument in arguments
    )
    parser = JsonArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument(
        "-h",
        "--help",
        action="store_true",
        help="show this help message and exit",
    )
    parser.add_argument("--mode", choices=sorted(ALLOWED_TABLES), required=True)
    parser.add_argument(
        "--table", choices=sorted(ALLOWED_TABLES.values()), required=True
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", required=True)

    connection = None
    original_local_infile = None
    restore_required = False
    rollback_confirmed = False
    phase = {"value": "VALIDATING"}
    failure: tuple[BaseException, str] | None = None
    cleanup_errors: list[tuple[str, BaseException]] = []
    success_payload: dict[str, object] | None = None
    config: dict[str, object] | None = None

    try:
        if lone_help:
            parser.print_help()
            return 0
        if has_help_token and not lone_help:
            raise ContractError("-h/--help must be used alone")
        if malformed_short_help:
            raise ContractError("malformed short help option")
        args = parser.parse_args(arguments)
        expected_table = ALLOWED_TABLES[args.mode]
        if args.table != expected_table:
            raise ContractError(
                f"mode {args.mode} requires table {expected_table}"
            )
        raw_input_path = args.input
        if not raw_input_path.is_absolute():
            raise ContractError("--input must be an existing absolute file")
        input_path = raw_input_path.resolve(strict=True)
        if not input_path.is_file():
            raise ContractError("--input must be an existing regular file")
        if not 1 <= args.batch_size <= 5000:
            raise ContractError("--batch-size must be in 1..5000")
        if args.mode == "load" and "'" in str(input_path):
            raise ContractError("input path may not contain a single quote")

        expected_source = source_manifest(input_path)
        config = {
            "host": args.host,
            "port": args.port,
            "user": args.user,
            "password": args.password,
            "database": "mysql_senior_scenarios",
        }
        phase["value"] = "BEFORE_SEND"
        connection = mysql.connector.connect(
            **config,
            allow_local_infile=True,
        )
        cursor = connection.cursor()
        if args.mode == "load":
            phase["value"] = "GLOBAL_SETTING"
            cursor.execute("SELECT @@GLOBAL.local_infile")
            original_local_infile = int(cursor.fetchone()[0])
            if original_local_infile == 0:
                restore_required = True
                cursor.execute("SET GLOBAL local_infile=1")
                cursor.execute("SELECT @@GLOBAL.local_infile")
                if int(cursor.fetchone()[0]) != 1:
                    raise ContractError("local_infile enable was not confirmed")
            phase["value"] = "BEFORE_SEND"
        phase["value"] = "EXECUTING"
        cursor.execute(f"TRUNCATE TABLE `{args.table}`")
        phase["value"] = "VERIFYING"
        before = status_snapshot(cursor)
        phase["value"] = "CLOSING"
        cursor.close()
        phase["value"] = "BEFORE_SEND"
        started = time.perf_counter()

        if args.mode == "single":
            accepted = load_single(
                connection, args.table, iter_rows(input_path), phase
            )
        elif args.mode == "batch":
            accepted = load_batches(
                connection,
                args.table,
                iter_rows(input_path),
                args.batch_size,
                phase,
            )
        else:
            accepted, warning_count, rejected = load_local_file(
                connection,
                args.table,
                input_path,
                expected_source,
                phase,
            )
        if args.mode != "load":
            warning_count = 0
            rejected = 0

        phase["value"] = "VERIFYING"
        cursor = connection.cursor()
        after = status_snapshot(cursor)
        target_manifest = fingerprint(cursor, args.table)
        phase["value"] = "CLOSING"
        cursor.close()
        phase["value"] = "VERIFYING"
        seconds = time.perf_counter() - started
        require_manifest_match(expected_source, target_manifest, accepted)
        phase["value"] = "VERIFIED"
        success_payload = {
            "mode": args.mode,
            "table": args.table,
            "rows": accepted,
            "warnings": warning_count,
            "rejected": rejected,
            "seconds": seconds,
            "rows_per_second": accepted / seconds,
            "status_delta": {
                name: after[name] - before[name] for name in STATUS_NAMES
            },
            "source_manifest": expected_source,
            "target_manifest": target_manifest,
        }
    except SystemExit as exc:
        failure = (exc, phase["value"])
    except BaseException as exc:
        failure = (exc, phase["value"])
    finally:
        if failure is not None and connection is not None:
            phase["value"] = "ROLLING_BACK"
            try:
                if not connection.is_connected():
                    raise RuntimeError("rollback could not be confirmed")
                connection.rollback()
                rollback_confirmed = True
            except BaseException as exc:
                cleanup_errors.append((phase["value"], exc))
        if restore_required:
            phase["value"] = "RESTORING"
            try:
                if config is None or original_local_infile is None:
                    raise RuntimeError("local_infile restore state is incomplete")
                restore_local_infile(config, original_local_infile)
            except BaseException as exc:
                cleanup_errors.append((phase["value"], exc))
        if connection is not None:
            phase["value"] = "CLOSING"
            try:
                connection.close()
            except BaseException as exc:
                cleanup_errors.append((phase["value"], exc))

    if failure is not None or cleanup_errors:
        if failure is None:
            primary_exc, operation_phase = cleanup_errors[0][1], "VERIFIED"
        else:
            primary_exc, operation_phase = failure
        status = classify(
            primary_exc,
            operation_phase,
            rollback_confirmed,
            cleanup_errors,
        )
        result: dict[str, object] = {
            "status": status,
            "phase": (
                cleanup_errors[0][0] if cleanup_errors else operation_phase
            ),
            "operation_phase": operation_phase,
            "rollback_confirmed": rollback_confirmed,
            "error_type": type(primary_exc).__name__,
            "error": redact(primary_exc, password),
        }
        if cleanup_errors:
            result["cleanup_errors"] = [
                {
                    "phase": cleanup_phase,
                    "error_type": type(cleanup_exc).__name__,
                    "error": redact(cleanup_exc, password),
                }
                for cleanup_phase, cleanup_exc in cleanup_errors
            ]
        print(json.dumps(result, sort_keys=True), file=sys.stderr)
        return 2

    if success_payload is None:
        print(
            json.dumps(
                {
                    "status": "UNKNOWN",
                    "phase": phase["value"],
                    "operation_phase": "VERIFIED",
                    "rollback_confirmed": rollback_confirmed,
                    "error_type": "InternalOutcomeError",
                    "error": "verified payload was not finalized",
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    phase["value"] = "VERIFIED"
    success_payload["status"] = "SUCCEEDED"
    success_payload["phase"] = phase["value"]
    print(json.dumps(success_payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Required safety behavior:

- table name is checked against a three-name allowlist before interpolation；
- the raw input path must already be absolute before `resolve(strict=True)` runs, and the resolved target must be an existing regular file；
- `single` truncates only `bulk_single`, `batch` only `bulk_batch`, `load` only `bulk_load`；
- batch size must be `1..5000`；
- before load timing starts, scan the immutable TSV with `iter_rows()`／`parse_row()` and require strictly increasing unique primary IDs; the source manifest records exact row count, min／max ID, distinct ID count and the same UTF-8 CRC32／BIT_XOR lab fingerprint used by target SQL；
- success requires accepted rows, exact target count, distinct primary IDs, min／max ID and target fingerprint all to equal the source manifest；
- immediately after `LOAD DATA LOCAL` returns, capture `cursor.warning_count` and `rowcount` before issuing another SQL statement; any warning, reject, accepted-row mismatch or uncommitted target-manifest mismatch is rolled back instead of committed. Driver modes report an exception as `FAILED` or `UNKNOWN`; they never convert it into a successful run with a synthetic reject count；
- load mode connects with `allow_local_infile=True`, saves `@@GLOBAL.local_infile`, assigns `restore_required=True` before sending the enable statement, and restores plus confirms the original value through a fresh admin connection even if enable acknowledgement is lost；
- phases distinguish `VALIDATING`、`BEFORE_SEND`、`SESSION_SETTING`、`GLOBAL_SETTING`、`EXECUTING`、`COMMITTING`、`VERIFYING`、`ROLLING_BACK`、`RESTORING`、`CLOSING` and `VERIFIED`; each mode enters `SESSION_SETTING` before assigning `connection.autocommit`, so a lost acknowledgement／read timeout／write timeout from that session statement is always `UNKNOWN` even if later rollback succeeds. Parse／validation and definite local before-send failures remain `FAILED`; a definite server rejection can be `FAILED` only when the same connection remains usable and rollback is confirmed, every commit ambiguity remains `UNKNOWN`, and any mandatory cleanup uncertainty is `UNKNOWN`；failure JSON records `operation_phase` and `rollback_confirmed`, and the runner never auto-retries `UNKNOWN`；
- malformed or missing arguments use the same structured failure path. The parser disables built-in exiting help and long-option abbreviation, then advertises a non-exiting `-h`／`--help` option: exact lone `-h` or lone `--help` explicitly prints help and returns zero before parsing; an exact help token mixed with any other argument and malformed short forms such as `-hh`／`-hfoo` are rejected before `parse_args()`; abbreviations such as `--he`／`--hel`, `--help=value`, unknown options and missing arguments produce one structured nonzero JSON outcome without plaintext usage／help. A valid option such as `--host` is not treated as help. Parse, validation, execution, verification, rollback, restoration or close failure produces exactly one nonzero JSON outcome after all mandatory cleanup attempts, with the password redacted and no traceback；
- successful JSON is emitted only after rollback／restoration／close finalization and includes mode, table, rows, warnings, rejected rows, seconds, rows_per_second, status deltas, source manifest and target manifest；
- Connector/Python `executemany()` is described as a parameterized driver batch whose exact rewrite must be checked for the pinned connector; it is not mislabeled as proof of server-side prepared statements。

Execution form recorded in the document:

```bash
uv run --with mysql-connector-python==9.7.0 python "$MYSQL_SCENARIO_RUN_DIR/bulk_runner.py" \
  --mode batch \
  --table bulk_batch \
  --input "$MYSQL_SCENARIO_RUN_DIR/input.tsv" \
  --batch-size 1000 \
  --host 127.0.0.1 --port 3306 --user root --password root
```

The Markdown code block is the canonical source; during a run, extract or copy it to the exact namespaced path `$MYSQL_SCENARIO_RUN_DIR/bulk_runner.py`. Do not add a repository script.

- [ ] **Step 6: 寫 experiment matrix、resource gate 與 hypotheses**

Fixed matrix:

| Tier | Rows | single | batch | LOAD DATA |
|---|---:|---|---|---|
| S | 100,000 | 3 runs | 3 runs | 3 runs |
| M | 1,000,000 | not run after S establishes control cost | 3 runs if gate passes | 3 runs if gate passes |
| L | 10,000,000 | not run | 3 runs if gate passes | 3 runs if gate passes |

Before running, hypotheses are qualitative only:

- single autocommit should have the highest round-trip／commit overhead；
- batch should reduce round trips and commit count；
- `LOAD DATA` should avoid repeated SQL statement construction and is expected to be fastest for this compatible file；
- all three must produce identical correctness results；
- exact throughput and speedup are unknown；
- additional indexes, wider rows, binlog, replica and constrained I/O can change the result。

At top, mark experiment `READY_UNRUN`; architecture and safety boundaries `REASONED`.

- [ ] **Step 7: 核對官方 MySQL／Connector claims**

Browse and cite only primary documentation for:

- MySQL 8.0 `LOAD DATA` syntax and `LOCAL` security boundary；
- MySQL 8.0 InnoDB bulk loading recommendations；
- Connector/Python `executemany()` behavior；
- `local_infile` variable scope；
- binary logging／replication impact of bulk writes。

Paraphrase the verified behavior; do not copy long passages or state that disabling durability／constraints is universally safe.

- [ ] **Step 8: 寫 30 秒、3–5 分鐘答案與追問樹**

The short answer must begin by asking empty／hot table, file shape, indexes／constraints, binlog／replica and restartability. It then recommends staging + `LOAD DATA` or bounded batches, correctness gate and progressive scale.

The long answer must cover the full execution chain, batch／transaction cost, index write amplification, replication lag, manifest／rejects, publish／rollback and how evidence changes at S／M／L. Follow-ups include hot table, duplicate input, disk shortage, replica lag, interrupted commit, source regeneration and exact 10-million target.

- [ ] **Step 9: Link route, verify, and commit expectation**

Update ch13 README to link `[高效安全地导入 1,000 万行](02-bulk-load-10m.md)` with `READY_UNRUN`.

Run:

```bash
rg -n 'READY_UNRUN|bulk_single|bulk_batch|bulk_load|load_single|load_batches|load_local_file|SCALED_REPRODUCED|30 秒|3–5 分钟' mysql-handson/13-senior-scenarios/02-bulk-load-10m.md
git diff --check -- mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/02-bulk-load-10m.md
git add mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/02-bulk-load-10m.md
git commit -m "docs(mysql): define ten-million-row load scenario"
```

---

### Task 6: 跑 bulk load S，資源允許時逐級跑 M／L

**Files:**
- Modify: `mysql-handson/13-senior-scenarios/02-bulk-load-10m.md`
- Modify: `mysql-handson/13-senior-scenarios/README.md`

**Interfaces:**
- Consumes: Task 5 input and runner contracts, healthy `mysql-primary`, temporary directory with validated prefix。
- Produces: three-run S comparison and conditional M／L evidence; exact final label follows the completed tier。

- [ ] **Step 1: Repeat non-mutating preflight and capture original global state**

Run:

```bash
docker inspect -f '{{.State.Health.Status}} {{index .Config.Labels "com.docker.compose.project"}} {{index .Config.Labels "com.docker.compose.project.working_dir"}}' mysql-primary
docker exec mysql-primary mysql -uroot -proot -Nse "SELECT VERSION(), @@GLOBAL.local_infile, @@innodb_flush_log_at_trx_commit, @@sync_binlog, @@binlog_format"
df -k /private/tmp
docker stats --no-stream mysql-primary
```

Expected: healthy expected lab; record original `local_infile`; no durability setting differs from Task 5 assumptions.

- [ ] **Step 2: Create S manifest and materialize the embedded runner in temp only**

Run the exact Task 5 generator with S=`100000`. Copy the committed Python block to `$MYSQL_SCENARIO_RUN_DIR/bulk_runner.py`, then verify syntax before touching MySQL:

```bash
uv run --with mysql-connector-python==9.7.0 python -m py_compile "$MYSQL_SCENARIO_RUN_DIR/bulk_runner.py"
```

Expected: exit `0`; manifest records rows, bytes and SHA-256.

- [ ] **Step 3: Create clean bulk tables and verify zero rows**

Run Task 5 DDL against `mysql_senior_scenarios`, then:

```sql
SELECT 'bulk_single', COUNT(*) FROM bulk_single
UNION ALL SELECT 'bulk_batch', COUNT(*) FROM bulk_batch
UNION ALL SELECT 'bulk_load', COUNT(*) FROM bulk_load;
```

Expected: all three counts `0`.

- [ ] **Step 4: Run the nine S trials in alternating order**

Use fixed order:

```text
single, batch, load,
load, single, batch,
batch, load, single
```

Invoke the runner once per trial; it truncates only its allowlisted table. Save each JSON output under the validated runtime directory. If any correctness fingerprint differs, stop before M and preserve all S outputs.

- [ ] **Step 5: Calculate S median／range and verify equality**

For each method report all three seconds／rows-per-second／status deltas, median and min–max. Assert:

```text
count = 100000
min_id = 1
max_id = 100000
distinct_id = 100000
fingerprint(single) = fingerprint(batch) = fingerprint(load)
```

Do not select only the fastest attempt.

- [ ] **Step 6: Compute M／L disk gates from S evidence**

Use this conservative formula separately for M and L:

```text
projected_peak =
  1.5 × (S input bytes + largest S DATA_LENGTH + largest S INDEX_LENGTH
         + largest observed redo delta + runtime temp bytes)
      × (target_rows / 100000)

required_free = projected_peak + 5 GiB for M
required_free = projected_peak + 10 GiB for L
```

Record the arithmetic and current free bytes. A gate result is data, not a reason to change Docker storage or delete unrelated artifacts.

- [ ] **Step 7: Run M only when its gate passes**

Generate a new immutable 1,000,000-row manifest. Run `batch` and `load` three times each in alternating order; do not run the single-row control. Repeat exact correctness checks and record median／range. If the gate fails, skip all M mutations and write the measured reason.

- [ ] **Step 8: Run L only when its gate passes after M**

Generate a new immutable 10,000,000-row manifest. Run `batch` and `load` three times each in alternating order; validate exact `10,000,000` count, distinct IDs, min／max and matching fingerprint after every run. Stop on reserve breach, mysqld restart, I/O error, correctness mismatch or an explicit predeclared latency／checkpoint limit.

- [ ] **Step 9: Verify global restoration and capture final status**

Run:

```bash
docker exec mysql-primary mysql -uroot -proot -Nse "SELECT @@GLOBAL.local_infile, @@innodb_flush_log_at_trx_commit, @@sync_binlog, @@binlog_format"
docker inspect -f '{{.State.RestartCount}} {{.State.Health.Status}}' mysql-primary
```

Expected: `local_infile` equals the Step 1 original value; durability and binlog format unchanged; container healthy and no unexplained restart.

- [ ] **Step 10: Patch evidence and choose the exact label**

Use `apply_patch` without altering Task 5 hypotheses:

- if L completed and correctness passed, mark the 10-million claim `REPRODUCED`；
- if only S or M completed, mark it `SCALED_REPRODUCED` and name the highest tier；
- if no runnable tier completed, retain `READY_UNRUN` and record preflight／failure evidence；
- keep production throughput conclusions `REASONED`；
- include environment, run IDs, manifests, all runs, median／range, status deltas, correctness, unexpected results, restart／cleanup state。

Update only the corresponding ch13 README row.

- [ ] **Step 11: Safe temp cleanup and commit**

Before deleting runtime files, validate the exact prefix:

```bash
case "$MYSQL_SCENARIO_RUN_DIR" in
  /private/tmp/mysql-senior-scenarios.*) ;;
  *) exit 1 ;;
esac
rm -rf -- "$MYSQL_SCENARIO_RUN_DIR"
```

Then:

```bash
git diff --check -- mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/02-bulk-load-10m.md
git add mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/02-bulk-load-10m.md
git commit -m "docs(mysql): record bulk-load evidence"
```

---

### Task 7: 寫 archive／delete／purge／reclaim 的問題與預期

**Files:**
- Create: `mysql-handson/13-senior-scenarios/03-archive-delete-reclaim.md`
- Modify: `mysql-handson/13-senior-scenarios/README.md`

**Interfaces:**
- Consumes: ch02 page／tablespace、ch05 long transaction／purge、ch07 redo／binlog、ch09 replica apply、ch11 backup／PITR／disk operations。
- Produces: nonpartition big-delete、throttled batch-delete、partition-drop comparison with legal-hold and reclaim boundaries；Task 8 records evidence。

- [ ] **Step 1: Confirm absence and route status**

```bash
test ! -e mysql-handson/13-senior-scenarios/03-archive-delete-reclaim.md
rg -n '03-archive-delete-reclaim.md.*READY_UNRUN' mysql-handson/13-senior-scenarios/README.md
```

- [ ] **Step 2: Write the prompt and separate four lifecycle stages**

Prompt: 「一张持续增长的历史表要删除三个月前的数据并释放磁盘，你怎么做，如何避免拖垮线上、误删 legal hold、制造复制延迟或以为 DELETE 后文件一定变小？」

The document must define independently:

```text
retention = 哪些数据何时有资格离开热库
archive   = 冷数据放在哪里，如何验证可读和完整
delete    = 行不可见、undo/redo/binlog、purge 与 replica apply
reclaim   = InnoDB 可复用页 vs tablespace/OS 实际缩小
```

Completion requires archive manifest, eligibility cutoff, legal-hold exclusion, idempotent batch watermark, post-delete correctness, purge state, replica／P99 stop conditions and an explicit restore source before irreversible steps.

- [ ] **Step 3: Define the S dataset and four table roles**

Use exactly 100,000 deterministic rows across January–June 2026. Required tables:

```text
archive_source       immutable seed
archive_big_delete   one large transaction path
archive_batch_delete bounded 1,000-row commit path
archive_partitioned  monthly RANGE COLUMNS(created_at) path
archive_cold         verified archive copy
archive_hold         legal-hold rows removed from partition-drop eligibility
```

Nonpartition tables use `PRIMARY KEY(id)`, `KEY idx_created(created_at,id)` and `legal_hold BOOLEAN`. The partitioned table uses `PRIMARY KEY(id, created_at)` because every unique key must include the partition key, and monthly partitions `p202601` through `p202606` plus `pmax`.

Use this exact source and partition layout:

```sql
CREATE TABLE archive_source (
  id         BIGINT UNSIGNED NOT NULL,
  created_at DATETIME(6) NOT NULL,
  payload    VARCHAR(128) NOT NULL,
  legal_hold BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (id),
  KEY idx_created (created_at, id)
) ENGINE=InnoDB;

CREATE TABLE archive_big_delete LIKE archive_source;
CREATE TABLE archive_batch_delete LIKE archive_source;

CREATE TABLE archive_partitioned (
  id         BIGINT UNSIGNED NOT NULL,
  created_at DATETIME(6) NOT NULL,
  payload    VARCHAR(128) NOT NULL,
  legal_hold BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (id, created_at),
  KEY idx_created (created_at, id)
) ENGINE=InnoDB
PARTITION BY RANGE COLUMNS(created_at) (
  PARTITION p202601 VALUES LESS THAN ('2026-02-01'),
  PARTITION p202602 VALUES LESS THAN ('2026-03-01'),
  PARTITION p202603 VALUES LESS THAN ('2026-04-01'),
  PARTITION p202604 VALUES LESS THAN ('2026-05-01'),
  PARTITION p202605 VALUES LESS THAN ('2026-06-01'),
  PARTITION p202606 VALUES LESS THAN ('2026-07-01'),
  PARTITION pmax VALUES LESS THAN (MAXVALUE)
);

DROP TABLE IF EXISTS seed_digit;
CREATE TABLE seed_digit (d TINYINT UNSIGNED PRIMARY KEY);
INSERT INTO seed_digit VALUES (0),(1),(2),(3),(4),(5),(6),(7),(8),(9);

INSERT INTO archive_source (id, created_at, payload, legal_hold)
SELECT n,
       TIMESTAMPADD(
         SECOND,
         FLOOR((n - 1) / 6),
         TIMESTAMPADD(MONTH, MOD(n - 1, 6), '2026-01-01 00:00:00')
       ),
       CONCAT('archive-', LPAD(n, 12, '0')),
       n <= 55 AND MOD(n - 1, 6) = 0
FROM (
  SELECT 1 + d0.d + 10*d1.d + 100*d2.d + 1000*d3.d
           + 10000*d4.d + 100000*d5.d AS n
  FROM seed_digit AS d0
  CROSS JOIN seed_digit AS d1
  CROSS JOIN seed_digit AS d2
  CROSS JOIN seed_digit AS d3
  CROSS JOIN seed_digit AS d4
  CROSS JOIN seed_digit AS d5
  ORDER BY n
  LIMIT 100000
) AS seq;

INSERT INTO archive_big_delete SELECT * FROM archive_source;
INSERT INTO archive_batch_delete SELECT * FROM archive_source;
INSERT INTO archive_partitioned
SELECT * FROM archive_source
WHERE NOT (created_at < '2026-04-01 00:00:00' AND legal_hold = TRUE);

DROP TABLE seed_digit;
```

Archive tables use these fixed identities:

```sql
CREATE TABLE archive_cold (
  archive_run_id CHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  source_id      BIGINT UNSIGNED NOT NULL,
  created_at     DATETIME(6) NOT NULL,
  payload        VARCHAR(128) NOT NULL,
  PRIMARY KEY (archive_run_id, source_id)
) ENGINE=InnoDB;

CREATE TABLE archive_hold (
  source_id   BIGINT UNSIGNED NOT NULL,
  created_at  DATETIME(6) NOT NULL,
  payload     VARCHAR(128) NOT NULL,
  hold_reason VARCHAR(64) NOT NULL,
  PRIMARY KEY (source_id)
) ENGINE=InnoDB;
```

Old-data predicate is fixed:

```sql
created_at < '2026-04-01 00:00:00' AND legal_hold = FALSE
```

Exactly ten old rows have `legal_hold=TRUE`; they must remain queryable after batch deletion. Before partition drop, those ten rows are copied and verified in `archive_hold`, then excluded from the droppable partitioned dataset. Explain that row-level exceptions make blind partition drop unsafe unless data placement separates them first.

- [ ] **Step 4: Define archive correctness manifest**

Before delete or drop, capture for every eligible range:

```sql
SELECT COUNT(*) AS rows,
       MIN(id) AS min_id,
       MAX(id) AS max_id,
       SUM(id) AS sum_id,
       BIT_XOR(CRC32(CONCAT_WS('#', id, created_at, payload))) AS lab_fingerprint
FROM source_table
WHERE created_at < '2026-04-01 00:00:00'
  AND legal_hold = FALSE;
```

Copy to `archive_cold` with a stable `archive_run_id`, enforce uniqueness on `(archive_run_id,source_id)`, and compare the same aggregates before any destructive SQL by aliasing `source_id AS id`. State that CRC is a lab fingerprint; production archival uses stronger manifests, object versioning and restore drills.

- [ ] **Step 5: Define the three mutation paths and stop signals**

Paths:

```text
A. one transaction: DELETE all eligible rows, then COMMIT
B. batch: DELETE the fixed `created_at < cutoff AND legal_hold=FALSE` predicate with `ORDER BY id LIMIT 1000`, autocommit, 50 ms sleep, watermark each batch
C. partition: verify archive/hold separation, then `ALTER TABLE archive_partitioned DROP PARTITION p202601,p202602,p202603`
```

For each path record elapsed time, affected rows, redo delta, binlog growth, history list, table／partition file size and remaining invariants. This S lab does not run concurrent OLTP and therefore makes no P95 claim. Batch stops on disk reserve, lock wait, MySQL restart／I/O error, correctness mismatch, checkpoint pressure or a predeclared replication-lag budget when the replica profile is explicitly in use.

The reclaim section must distinguish:

- delete frees records/pages for InnoDB reuse but usually does not shrink `.ibd` immediately；
- purge catching up is different from file shrink；
- partition drop can remove partition files when layout permits；
- `OPTIMIZE TABLE`／table rebuild needs peak space, MDL planning, time and a restore path；
- no automatic `OPTIMIZE` recommendation after every delete。

- [ ] **Step 6: Write hypotheses, evidence labels and answer forms**

Pre-run hypotheses:

- one large delete should create the largest transaction and least controllable burst；
- batched delete should take longer end-to-end but bound each transaction and allow throttling／resume；
- partition drop should be much cheaper for eligible whole partitions, but only after schema and legal-hold placement were designed for it；
- nonpartition `.ibd` should not be assumed to shrink after DELETE；
- exact redo, time and size remain unknown。

Mark S experiment `READY_UNRUN`, mechanism links `REUSED`, production choices `REASONED`. Provide 30-second and 3–5-minute answers plus follow-ups for legal hold, replica lag, disk pressure, no partition key, no archive, restore SLA and already-full disk.

- [ ] **Step 7: Verify official claims**

Use official MySQL 8.0 documentation to verify partition unique-key requirements, `DROP PARTITION`, InnoDB file-per-table behavior, purge／history list, `OPTIMIZE TABLE` rebuild semantics and row-based binlog effects. Cite primary pages near the claims and keep local observations separate.

- [ ] **Step 8: Link route, verify, and commit expectation**

Update README to link `[归档、批量删除与空间回收](03-archive-delete-reclaim.md)` with `READY_UNRUN`.

Run:

```bash
rg -n 'READY_UNRUN|archive_big_delete|archive_batch_delete|archive_partitioned|archive_hold|legal_hold|DROP PARTITION|OPTIMIZE TABLE|30 秒|3–5 分钟' mysql-handson/13-senior-scenarios/03-archive-delete-reclaim.md
git diff --check -- mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/03-archive-delete-reclaim.md
git add mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/03-archive-delete-reclaim.md
git commit -m "docs(mysql): define archive and reclaim scenario"
```

---

### Task 8: 跑 archive S 級三路對照並記錄 evidence

**Files:**
- Modify: `mysql-handson/13-senior-scenarios/03-archive-delete-reclaim.md`
- Modify: `mysql-handson/13-senior-scenarios/README.md`

**Interfaces:**
- Consumes: Task 7 exact dataset／predicates／manifest, healthy base lab。
- Produces: correctness-first big-delete／batch-delete／partition-drop evidence and explicit logical-free／purge／OS-reclaim timestamps。

- [ ] **Step 1: Preflight and record run environment**

Repeat the Docker ownership, MySQL version／durability, free disk and host resource checks from Task 4. Require S peak + 5 GiB. Record a fresh UTC run ID and current `innodb_file_per_table`.

- [ ] **Step 2: Create and verify the immutable S source**

Create 100,000 deterministic rows, 16,666 or 16,667 per month depending on modulo distribution, with exactly ten old `legal_hold=TRUE` rows. Copy the complete source into both nonpartition paths. For the partition path, route those ten old hold rows into `archive_hold` and insert only non-held old rows plus all April–June rows into `archive_partitioned`; verify the union of partitioned rows and hold rows matches the source fingerprint before timing.

- [ ] **Step 3: Archive and verify before mutation**

Insert eligible rows into `archive_cold` under the run ID, copy ten hold rows into `archive_hold`, then compare counts, ranges, sums and fingerprints. If any mismatch appears, stop without running DELETE or DROP PARTITION.

- [ ] **Step 4: Run the one-transaction delete path**

Capture pre metrics, execute one explicit transaction deleting the fixed eligible predicate, commit, then capture elapsed time, affected count, redo delta, binary log file-size delta, history list and `.ibd` size. Verify ten held rows remain and no ineligible April–June row was removed.

- [ ] **Step 5: Run the throttled batch path**

Use a shell loop that executes one autocommit statement per iteration:

```sql
DELETE FROM archive_batch_delete
WHERE created_at < '2026-04-01 00:00:00'
  AND legal_hold = FALSE
ORDER BY id
LIMIT 1000;
SELECT ROW_COUNT();
```

After every batch save last completed batch number, cumulative rows, elapsed time and throttle signal, then sleep 50 ms. Stop at `ROW_COUNT()=0`. Interrupt once after at least three batches, verify current state, then resume from the same predicate without duplicate side effects.

- [ ] **Step 6: Run the partition path**

Verify `archive_hold` first, then:

```sql
ALTER TABLE archive_partitioned
  DROP PARTITION p202601, p202602, p202603;
```

Capture elapsed time, partition metadata, files before／after, redo／binlog delta and remaining April–June rows. Do not claim partition drop is safe for mixed legal-hold data; the lab is safe only because hold rows were separated and verified first.

- [ ] **Step 7: Observe purge and reclaim as separate milestones**

For big and batch tables record:

1. delete commit／rows no longer visible；
2. history list returns to its pre-run neighborhood；
3. `DATA_FREE`, `DATA_LENGTH`, `INDEX_LENGTH` and `.ibd` size；
4. whether OS file size changed without rebuild。

Run `OPTIMIZE TABLE archive_batch_delete` only after rechecking free disk for a second copy + 5 GiB reserve. Record MDL／elapsed／size outcome and label it a controlled S maintenance experiment, not a default production action.

- [ ] **Step 8: Repeat comparable trials or narrow the claim**

Recreate the three path tables from the immutable source and run each path three times when runtime remains within the predeclared budget. If only one destructive comparison is feasible, do not publish a stable performance ranking; publish correctness and mechanism observations and mark timing as a single-run result.

- [ ] **Step 9: Patch actual evidence and update status**

Use `apply_patch` to add environment, run ID, manifest, all paths, interruption／resume result, metrics, three reclaim milestones, correctness, legal-hold proof, expected-vs-actual and production boundary. Mark the S mechanics `SCALED_REPRODUCED`; keep production throughput／window recommendations `REASONED`.

Update only this README row to `SCALED_REPRODUCED (S=100000)`.

- [ ] **Step 10: Verify and commit**

```bash
rg -n 'SCALED_REPRODUCED|run ID|legal_hold|中断|恢复|history list|DATA_FREE|\.ibd|我以为|实际|我学到' mysql-handson/13-senior-scenarios/03-archive-delete-reclaim.md
! rg -n 'READY_UNRUN' mysql-handson/13-senior-scenarios/03-archive-delete-reclaim.md
git diff --check -- mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/03-archive-delete-reclaim.md
git add mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/03-archive-delete-reclaim.md
git commit -m "docs(mysql): record archive and reclaim evidence"
```

---

### Task 9: 寫 report／export isolation 的問題、預期與 resumable runner 契約

**Files:**
- Create: `mysql-handson/13-senior-scenarios/04-report-export-isolation.md`
- Modify: `mysql-handson/13-senior-scenarios/README.md`

**Interfaces:**
- Consumes: ch05 snapshot／long transaction、ch08 JOIN／filesort／temporary／keyset pagination、ch09 replica lag；`uv` and Connector/Python。
- Produces: buffered one-shot control、keyset parts／checkpoint／atomic publish baseline、background OLTP probe；Task 10 records measured interference and resume evidence。

- [ ] **Step 1: Confirm absence and route status**

```bash
test ! -e mysql-handson/13-senior-scenarios/04-report-export-isolation.md
rg -n '04-report-export-isolation.md.*READY_UNRUN' mysql-handson/13-senior-scenarios/README.md
```

- [ ] **Step 2: Write prompt and consistency decision tree**

Prompt: 「要导出一份千万级 JOIN 报表，线上 MySQL 不能被拖慢，输出要能重试、续跑并证明完整。你会怎么定义一致性、隔离资源和发布文件？」

Required questions:

- synchronous HTTP response or async job；
- exact cross-table as-of snapshot or bounded high watermark；
- rows immutable or mutable during export；
- allowed staleness／replica lag；
- output size／format／consumer backpressure；
- restart from zero or cursor／part resume；
- Primary, shared replica, dedicated reporting replica or analytical store；
- OLTP P95 budget and export completion SLA。

State the hard boundary precisely: `(created_at,id)` is only a query upper bound. It is a complete membership boundary only when those cursor keys are immutable and insertion-monotone, or when job membership was materialized／snapshotted. A later **backdated** or otherwise in-bound INSERT with tuple `<= high` can appear in a new ReadView after resume; the tuple also cannot freeze UPDATE／DELETE of existing rows. Production must require monotone immutable cursor keys, materialized membership, versioned history, a database／replica snapshot, CDC-built versioned read model, analytical snapshot, or a deliberately bounded MVCC snapshot with its undo／purge cost.

- [ ] **Step 3: Define the fixed S schema and query order**

Use exactly:

```sql
CREATE TABLE report_order (
  id         BIGINT UNSIGNED NOT NULL,
  tenant_id  BIGINT UNSIGNED NOT NULL,
  status     TINYINT UNSIGNED NOT NULL,
  created_at DATETIME(6) NOT NULL,
  PRIMARY KEY (id),
  KEY idx_created_id (created_at, id)
) ENGINE=InnoDB;

CREATE TABLE report_item (
  id         BIGINT UNSIGNED NOT NULL,
  order_id   BIGINT UNSIGNED NOT NULL,
  qty        INT UNSIGNED NOT NULL,
  unit_price DECIMAL(18,2) NOT NULL,
  PRIMARY KEY (id),
  KEY idx_order (order_id)
) ENGINE=InnoDB;

CREATE TABLE oltp_probe (
  id      BIGINT UNSIGNED NOT NULL,
  counter BIGINT UNSIGNED NOT NULL DEFAULT 0,
  payload VARCHAR(128) NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB;
```

Seed `100000` orders, exactly three items per order and `10000` probe rows. Export order is immutable `(created_at ASC,id ASC)`; high watermark is the maximum tuple captured at job creation. For Task 10, freeze `report_order` and `report_item` after seed, allow writes only to `oltp_probe`, reject an attempted backdated INSERT／UPDATE／DELETE, and compare pre/post source fingerprints. Without this S-only freeze, a resumed new ReadView does not prove fixed membership or values.

Use this complete six-digit seed mapping:

```sql
DROP TABLE IF EXISTS seed_digit;
CREATE TABLE seed_digit (d TINYINT UNSIGNED PRIMARY KEY);
INSERT INTO seed_digit VALUES (0),(1),(2),(3),(4),(5),(6),(7),(8),(9);

INSERT INTO report_order (id, tenant_id, status, created_at)
SELECT n,
       MOD(n, 1000) + 1,
       MOD(n, 4),
       TIMESTAMPADD(SECOND, n, '2026-01-01 00:00:00')
FROM (
  SELECT 1 + d0.d + 10*d1.d + 100*d2.d + 1000*d3.d
           + 10000*d4.d + 100000*d5.d AS n
  FROM seed_digit AS d0
  CROSS JOIN seed_digit AS d1
  CROSS JOIN seed_digit AS d2
  CROSS JOIN seed_digit AS d3
  CROSS JOIN seed_digit AS d4
  CROSS JOIN seed_digit AS d5
  ORDER BY n
  LIMIT 100000
) AS seq;

INSERT INTO report_item (id, order_id, qty, unit_price)
SELECT o.id * 10 + d.d,
       o.id,
       d.d,
       (MOD(o.id * d.d, 100000) + 1) / 100
FROM report_order AS o
JOIN seed_digit AS d ON d.d IN (1,2,3);

DROP TABLE seed_digit;

INSERT INTO oltp_probe (id, counter, payload)
SELECT id, 0, CONCAT('probe-', id)
FROM report_order
WHERE id <= 10000;
```

Export query shape:

```sql
SELECT o.created_at, o.id, o.tenant_id, o.status,
       SUM(i.qty * i.unit_price) AS total_amount,
       COUNT(*) AS item_count
FROM report_order AS o
JOIN report_item AS i ON i.order_id = o.id
WHERE (o.created_at, o.id) > (?, ?)
  AND (o.created_at, o.id) <= (?, ?)
GROUP BY o.created_at, o.id, o.tenant_id, o.status
ORDER BY o.created_at, o.id
LIMIT ?;
```

Link JOIN algorithms／filesort to ch08 and keyset pagination to ch08 scenario 03; do not reteach their full mechanism here.

- [ ] **Step 4: Define async job state and artifact invariants**

The embedded runner stores all runtime state under one exact job directory:

```text
job-<run-id>/
├── state.json
├── parts/
│   ├── part-000001.tsv
│   └── part-000002.tsv
├── artifact.tsv
└── result.json
```

`state.json` schema is fixed:

```json
{
  "job_id": "run-id",
  "mode": "chunked",
  "connection_id": 123,
  "high_created_at": "2026-01-02 03:46:40.000000",
  "high_id": 100000,
  "expected_rows": 100000,
  "last_created_at": "1970-01-01 00:00:00.000000",
  "last_id": 0,
  "next_part": 1,
  "rows_written": 0,
  "active_seconds": 0.0,
  "artifact_rows": null,
  "artifact_sha256": null,
  "parts": [],
  "status": "RUNNING",
  "abort_reason": null
}
```

Artifact invariants:

- each part is produced as `.tmp`, flushed／fsynced and atomically renamed；
- checkpoint advances only after the part rename；
- every checkpoint appends one ordered part manifest entry containing number, name, rows, SHA-256, first cursor and last cursor；
- resume verifies every checkpointed part's bytes, rows, hash, cursor order and contiguity; only the exact deterministic `next_part` file may exist uncheckpointed after rename-before-checkpoint, and it is rewritten from the old cursor；
- missing, same-line-count corruption, stale extra, orphan or gapped parts fail before publish；
- final publish consumes **only** the ordered checkpoint manifest, rechecks every part, requires `rows_written=expected_rows` and `last_cursor=high`, then writes／fsyncs／replaces `artifact.tsv`；
- `SUCCEEDED` fast path requires state, result and artifact to agree on job／mode／rows／SHA／cursors; chunked mode also revalidates every ordered part and requires their exact concatenated bytes／SHA to equal the artifact, so a coupled artifact／result rewrite cannot bypass the manifest；
- `ABORTED` keeps state and parts; cumulative `active_seconds` survives planned resume, so `rows_per_active_second` never divides cumulative rows by only the latest invocation；
- readers never consume `.tmp` or partial parts as a complete report。

Internal manifest checks prove artifact construction integrity. Task 10 must still perform an independent external audit: buffered／chunked／resumed exact SHA equality, distinct keys and business aggregate fingerprints. The lab does not claim power-loss durability for parent directories that were not fsynced.

- [ ] **Step 5: Embed exact runner interfaces**

The document contains one copyable `$MYSQL_SCENARIO_RUN_DIR/export_runner.py` block with CLI modes:

```text
--mode buffered|chunked|oltp
--runtime-root /private/tmp/mysql-senior-scenarios.<suffix>
--job-dir /private/tmp/mysql-senior-scenarios.<suffix>/job-<run-id>
--abort-file /private/tmp/mysql-senior-scenarios.<suffix>/abort-<run-id>.json
--metrics-file /private/tmp/mysql-senior-scenarios.<suffix>/metrics-<run-id>.json
--trial-id <run-id>
--batch-size 1000
--sleep-ms 20
--max-batches 0
--min-free-bytes 5419909120
--duration-seconds 60
--threads 4
--host 127.0.0.1 --port 3306 --user root --password-env MYSQL_PASSWORD
```

Interface migration from the earlier draft is intentional and binding: `job_dir=job-<run-id>` maps to `state.job_id=<run-id>` and the abort suffix, while OLTP `trial_id=<run-id>` maps to the metrics suffix; `--runtime-root`, job, abort, metrics and controller evidence all resolve beneath the same exact nonempty runtime directory, and empty runtime suffix／run ID are rejected. State gains mode, expected-boundary, artifact and part-manifest metadata; `seconds`／`rows_per_second` become cumulative `active_seconds`／`rows_per_active_second`; passwords come only from the named environment variable. Consumers and Task 10 must use these corrected names.

Use a complete implementation with these exact functions and types. The code below is the one canonical runner source; the scenario may improve comments, but not change state fields, query order, manifest validation or safety gates:

```python
def capture_high_watermark(cursor) -> tuple[str, int]:
    """Run ORDER BY created_at DESC,id DESC LIMIT 1 and return that tuple."""

def atomic_json(path: Path, value: dict) -> None:
    """Write, flush, fsync and os.replace a JSON document."""

def fetch_batch(cursor, low: tuple[str, int], high: tuple[str, int], limit: int) -> list[tuple]:
    """Execute the fixed keyset JOIN query and return at most limit rows."""

def write_part(path: Path, rows: list[tuple]) -> tuple[int, str]:
    """Atomically write canonical TSV and return row count plus SHA-256."""

def validate_manifest(job_dir: Path, state: dict, allow_pending: bool) -> list[dict]:
    """Recheck ordered checkpointed parts and reject missing/stale/corrupt parts."""

def manifest_artifact_signature(job_dir: Path, state: dict) -> tuple[int, str]:
    """Return exact rows/SHA of the ordered validated part concatenation."""

def publish(job_dir: Path, state: dict) -> tuple[int, str]:
    """Publish exactly the verified manifest after expected boundary completion."""

def validate_success(job_dir: Path, state: dict, result: dict) -> dict:
    """Recheck artifact rows/SHA against persisted success state and result."""

def run_chunked(connection, job_dir: Path, batch_size: int, sleep_ms: int, max_batches: int, abort_file: Path | None, min_free_bytes: int) -> dict:
    """Create or resume state, write deterministic parts and atomically publish on completion."""

def run_buffered(connection, job_dir: Path) -> dict:
    """Use one buffered full-boundary query, fetch all rows, write one artifact and report max RSS."""

def run_oltp(config: dict, duration: int, threads: int, metrics_file: Path | None, window_seconds: float, trial_id: str) -> dict:
    """Emit trial-bound heartbeat/window/cumulative metrics and final percentiles."""
```

```python
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import queue
import random
import resource
import shutil
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import mysql.connector


EPOCH = "1970-01-01 00:00:00.000000"
RUNTIME_PREFIX = "mysql-senior-scenarios."
EXPORT_SQL = """
SELECT o.created_at, o.id, o.tenant_id, o.status,
       SUM(i.qty * i.unit_price) AS total_amount,
       COUNT(*) AS item_count
FROM report_order AS o
JOIN report_item AS i ON i.order_id = o.id
WHERE (o.created_at, o.id) > (%s, %s)
  AND (o.created_at, o.id) <= (%s, %s)
GROUP BY o.created_at, o.id, o.tenant_id, o.status
ORDER BY o.created_at, o.id
LIMIT %s
"""
BUFFERED_SQL = """
SELECT o.created_at, o.id, o.tenant_id, o.status,
       SUM(i.qty * i.unit_price) AS total_amount,
       COUNT(*) AS item_count
FROM report_order AS o
JOIN report_item AS i ON i.order_id = o.id
WHERE (o.created_at, o.id) > (%s, %s)
  AND (o.created_at, o.id) <= (%s, %s)
GROUP BY o.created_at, o.id, o.tenant_id, o.status
ORDER BY o.created_at, o.id
"""


class StructuredArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def timestamp_text(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S.%f")
    return str(value)


def cursor_value(value) -> tuple[str, int]:
    return str(value[0]), int(value[1])


def canonical_line(row: tuple) -> bytes:
    created_at, order_id, tenant_id, status, total_amount, item_count = row
    amount = format(total_amount, "f") if isinstance(total_amount, Decimal) else str(total_amount)
    text = "\t".join(
        (
            timestamp_text(created_at),
            str(order_id),
            str(tenant_id),
            str(status),
            amount,
            str(item_count),
        )
    )
    return (text + "\n").encode("utf-8")


def capture_high_watermark(cursor) -> tuple[str, int]:
    cursor.execute(
        "SELECT DATE_FORMAT(created_at,'%Y-%m-%d %H:%i:%s.%f'), id "
        "FROM report_order ORDER BY created_at DESC,id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("report_order is empty")
    return str(row[0]), int(row[1])


def count_boundary_rows(cursor, high: tuple[str, int]) -> int:
    cursor.execute(
        "SELECT COUNT(*) FROM report_order "
        "WHERE (created_at,id) > (%s,%s) AND (created_at,id) <= (%s,%s)",
        (EPOCH, 0, *high),
    )
    return int(cursor.fetchone()[0])


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path.name} is not a JSON object")
    return value


def fetch_batch(
    cursor,
    low: tuple[str, int],
    high: tuple[str, int],
    limit: int,
) -> list[tuple]:
    cursor.execute(EXPORT_SQL, (*low, *high, limit))
    return list(cursor.fetchall())


def write_part(path: Path, rows: list[tuple]) -> tuple[int, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    digest = hashlib.sha256()
    count = 0
    with temporary.open("wb") as handle:
        for row in rows:
            encoded = canonical_line(row)
            handle.write(encoded)
            digest.update(encoded)
            count += 1
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return count, digest.hexdigest()


def part_file_metadata(path: Path) -> dict:
    digest = hashlib.sha256()
    rows = 0
    first_cursor = None
    last_cursor = None
    with path.open("rb") as handle:
        for line in handle:
            if not line.endswith(b"\n"):
                raise RuntimeError(f"{path.name} has a noncanonical final line")
            fields = line[:-1].split(b"\t")
            if len(fields) != 6:
                raise RuntimeError(f"{path.name} has a noncanonical column count")
            current = (fields[0].decode("utf-8"), int(fields[1]))
            if last_cursor is not None and current <= last_cursor:
                raise RuntimeError(f"{path.name} cursor order is not strictly increasing")
            first_cursor = first_cursor or current
            last_cursor = current
            digest.update(line)
            rows += 1
    if rows == 0:
        raise RuntimeError(f"{path.name} is empty")
    return {
        "rows": rows,
        "sha256": digest.hexdigest(),
        "first_cursor": list(first_cursor),
        "last_cursor": list(last_cursor),
    }


def file_rows_sha(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    rows = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            rows += chunk.count(b"\n")
    return rows, digest.hexdigest()


def max_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def runtime_root(path: Path) -> Path:
    resolved = path.resolve()
    private_tmp = Path("/private/tmp").resolve()
    if (
        resolved.parent != private_tmp
        or not resolved.name.startswith(RUNTIME_PREFIX)
        or resolved.name == RUNTIME_PREFIX
    ):
        raise ValueError("runtime directory is outside the allowed nonempty prefix")
    return resolved


def validated_job_dir(path: Path) -> Path:
    resolved = path.resolve()
    root = runtime_root(resolved.parent)
    if resolved.parent != root or not resolved.name.startswith("job-") or resolved.name == "job-":
        raise ValueError("job directory must be an immediate job-<run-id> child")
    return resolved


def job_id_from_dir(job_dir: Path) -> str:
    name = validated_job_dir(job_dir).name
    return name[len("job-") :]


def validated_runtime_file(
    path: Path,
    prefix: str,
    suffix: str,
    expected_root: Path,
) -> Path:
    resolved = path.resolve()
    root = runtime_root(expected_root)
    if (
        not suffix
        or resolved.parent != root
        or resolved.name != f"{prefix}{suffix}.json"
    ):
        raise ValueError(f"runtime file must equal {prefix}<nonempty-id>.json")
    return resolved


def validate_manifest(job_dir: Path, state: dict, allow_pending: bool) -> list[dict]:
    parts = state.get("parts")
    if not isinstance(parts, list):
        raise RuntimeError("state parts is not a list")
    expected_names = set()
    total_rows = 0
    previous = (EPOCH, 0)
    validated = []
    for expected_number, entry in enumerate(parts, 1):
        expected_name = f"part-{expected_number:06d}.tsv"
        if (
            int(entry.get("number", -1)) != expected_number
            or entry.get("name") != expected_name
        ):
            raise RuntimeError("part manifest has a gap or name mismatch")
        path = job_dir / "parts" / expected_name
        if not path.is_file():
            raise RuntimeError(f"checkpointed part missing: {expected_name}")
        observed = part_file_metadata(path)
        for key in ("rows", "sha256", "first_cursor", "last_cursor"):
            if observed[key] != entry.get(key):
                raise RuntimeError(f"checkpointed part mismatch: {expected_name}:{key}")
        first = cursor_value(entry["first_cursor"])
        last = cursor_value(entry["last_cursor"])
        if first <= previous or last < first:
            raise RuntimeError("part manifest cursor order is invalid")
        previous = last
        total_rows += int(entry["rows"])
        expected_names.add(expected_name)
        validated.append(entry)

    next_part = int(state.get("next_part", -1))
    if next_part != len(parts) + 1:
        raise RuntimeError("next_part does not follow the manifest")
    actual_names = {
        path.name for path in (job_dir / "parts").glob("part-*.tsv")
    } if (job_dir / "parts").exists() else set()
    allowed_names = set(expected_names)
    pending_name = f"part-{next_part:06d}.tsv"
    if allow_pending:
        allowed_names.add(pending_name)
    if expected_names - actual_names:
        raise RuntimeError("one or more checkpointed parts are missing")
    if actual_names - allowed_names:
        raise RuntimeError("stale, orphan, or gapped part detected")
    if total_rows != int(state.get("rows_written", -1)):
        raise RuntimeError("manifest rows do not match rows_written")
    expected_rows = int(state.get("expected_rows", -1))
    if expected_rows < total_rows:
        raise RuntimeError("rows_written exceeds expected boundary rows")
    expected_last = previous if parts else (EPOCH, 0)
    if expected_last != (
        str(state.get("last_created_at")),
        int(state.get("last_id", -1)),
    ):
        raise RuntimeError("state last cursor does not match manifest")
    return validated


def manifest_artifact_signature(job_dir: Path, state: dict) -> tuple[int, str]:
    parts = validate_manifest(job_dir, state, allow_pending=False)
    digest = hashlib.sha256()
    rows = 0
    for entry in parts:
        with (job_dir / "parts" / entry["name"]).open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
                rows += chunk.count(b"\n")
    return rows, digest.hexdigest()


def publish(job_dir: Path, state: dict) -> tuple[int, str]:
    parts = validate_manifest(job_dir, state, allow_pending=False)
    expected_rows = int(state["expected_rows"])
    if int(state["rows_written"]) != expected_rows:
        raise RuntimeError("checkpoint rows do not equal expected boundary rows")
    if (
        str(state["last_created_at"]),
        int(state["last_id"]),
    ) != (
        str(state["high_created_at"]),
        int(state["high_id"]),
    ):
        raise RuntimeError("last cursor does not equal the high watermark")

    artifact = job_dir / "artifact.tsv"
    temporary = job_dir / "artifact.tsv.tmp"
    artifact_digest = hashlib.sha256()
    artifact_rows = 0
    try:
        with temporary.open("wb") as output:
            for entry in parts:
                part_digest = hashlib.sha256()
                part_rows = 0
                with (job_dir / "parts" / entry["name"]).open("rb") as source:
                    for line in source:
                        output.write(line)
                        artifact_digest.update(line)
                        part_digest.update(line)
                        part_rows += line.count(b"\n")
                if (
                    part_rows != int(entry["rows"])
                    or part_digest.hexdigest() != entry["sha256"]
                ):
                    raise RuntimeError(f"part changed during publish: {entry['name']}")
                artifact_rows += part_rows
            output.flush()
            os.fsync(output.fileno())
        if artifact_rows != expected_rows:
            raise RuntimeError("artifact rows do not equal expected boundary rows")
        os.replace(temporary, artifact)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return artifact_rows, artifact_digest.hexdigest()


def validate_success(job_dir: Path, state: dict, result: dict) -> dict:
    artifact = job_dir / "artifact.tsv"
    if state.get("status") != "SUCCEEDED" or result.get("status") != "SUCCEEDED":
        raise RuntimeError("success files do not contain SUCCEEDED")
    if not artifact.is_file():
        raise RuntimeError("SUCCEEDED artifact is missing")
    rows, sha256 = file_rows_sha(artifact)
    expected_rows = int(state["expected_rows"])
    state_high = (str(state["high_created_at"]), int(state["high_id"]))
    state_last = (str(state["last_created_at"]), int(state["last_id"]))
    state_mode = str(state.get("mode"))
    if (
        rows != expected_rows
        or int(state["rows_written"]) != expected_rows
        or int(result.get("rows", -1)) != expected_rows
        or result.get("sha256") != sha256
        or int(state.get("artifact_rows", -1)) != expected_rows
        or state.get("artifact_sha256") != sha256
        or result.get("mode") != state_mode
        or result.get("job_id") != state.get("job_id")
        or state_last != state_high
        or cursor_value(result.get("high_cursor", ("", -1))) != state_high
        or cursor_value(result.get("last_cursor", ("", -1))) != state_last
    ):
        raise RuntimeError("SUCCEEDED artifact does not match state/result")
    if state_mode == "chunked":
        manifest_rows, manifest_sha256 = manifest_artifact_signature(job_dir, state)
        if manifest_rows != rows or manifest_sha256 != sha256:
            raise RuntimeError("SUCCEEDED artifact does not match checkpoint manifest")
    elif state_mode != "buffered":
        raise RuntimeError("SUCCEEDED state mode is invalid")
    return result


def stop_reason(abort_file: Path | None, job_dir: Path, min_free_bytes: int) -> str | None:
    if abort_file is not None and abort_file.exists():
        try:
            return str(read_json(abort_file).get("reason") or "external gate")
        except Exception:
            return "unreadable external abort signal"
    if min_free_bytes and shutil.disk_usage(job_dir.parent).free < min_free_bytes:
        return f"free disk below {min_free_bytes}"
    return None


def aborted_result(state: dict, reason: str, active_seconds: float) -> dict:
    state["status"] = "ABORTED"
    state["abort_reason"] = reason
    state["active_seconds"] = active_seconds
    return {
        "status": "ABORTED",
        "mode": "chunked",
        "job_id": state["job_id"],
        "reason": reason,
        "rows": int(state["rows_written"]),
        "active_seconds": active_seconds,
        "rows_per_active_second": (
            int(state["rows_written"]) / active_seconds if active_seconds else 0.0
        ),
        "max_rss_bytes": max_rss_bytes(),
        "high_cursor": [state["high_created_at"], state["high_id"]],
        "last_cursor": [state["last_created_at"], state["last_id"]],
        "parts": len(state["parts"]),
    }


def run_chunked(
    connection,
    job_dir: Path,
    batch_size: int,
    sleep_ms: int,
    max_batches: int,
    abort_file: Path | None,
    min_free_bytes: int,
) -> dict:
    state_path = job_dir / "state.json"
    result_path = job_dir / "result.json"
    cursor = connection.cursor()
    if state_path.exists():
        state = read_json(state_path)
        if state.get("job_id") != job_id_from_dir(job_dir):
            raise RuntimeError("state job_id does not match job directory")
        if state.get("status") == "SUCCEEDED":
            if not result_path.is_file():
                raise RuntimeError("SUCCEEDED result.json is missing")
            result = validate_success(job_dir, state, read_json(result_path))
            cursor.close()
            return result
        if state.get("status") not in ("RUNNING", "ABORTED"):
            raise RuntimeError("state status is not resumable")
        validate_manifest(job_dir, state, allow_pending=True)
        state["status"] = "RUNNING"
        state["abort_reason"] = None
        state["connection_id"] = int(connection.connection_id)
    else:
        high_created_at, high_id = capture_high_watermark(cursor)
        expected_rows = count_boundary_rows(cursor, (high_created_at, high_id))
        state = {
            "job_id": job_id_from_dir(job_dir),
            "mode": "chunked",
            "connection_id": int(connection.connection_id),
            "high_created_at": high_created_at,
            "high_id": high_id,
            "expected_rows": expected_rows,
            "last_created_at": EPOCH,
            "last_id": 0,
            "next_part": 1,
            "rows_written": 0,
            "active_seconds": 0.0,
            "artifact_rows": None,
            "artifact_sha256": None,
            "parts": [],
            "status": "RUNNING",
            "abort_reason": None,
        }
    atomic_json(state_path, state)
    started = time.perf_counter()
    base_active = float(state["active_seconds"])
    batches_this_run = 0
    while True:
        reason = stop_reason(abort_file, job_dir, min_free_bytes)
        if reason is not None:
            result = aborted_result(
                state, reason, base_active + (time.perf_counter() - started)
            )
            atomic_json(state_path, state)
            cursor.close()
            return result

        rows = fetch_batch(
            cursor,
            (state["last_created_at"], int(state["last_id"])),
            (state["high_created_at"], int(state["high_id"])),
            batch_size,
        )
        if not rows:
            state["active_seconds"] = base_active + (time.perf_counter() - started)
            artifact_rows, artifact_sha256 = publish(job_dir, state)
            result = {
                "status": "SUCCEEDED",
                "mode": "chunked",
                "job_id": state["job_id"],
                "rows": artifact_rows,
                "sha256": artifact_sha256,
                "active_seconds": state["active_seconds"],
                "rows_per_active_second": (
                    artifact_rows / state["active_seconds"]
                    if state["active_seconds"] else 0.0
                ),
                "max_rss_bytes": max_rss_bytes(),
                "high_cursor": [state["high_created_at"], state["high_id"]],
                "last_cursor": [state["last_created_at"], state["last_id"]],
                "parts": len(state["parts"]),
            }
            atomic_json(result_path, result)
            state["artifact_rows"] = artifact_rows
            state["artifact_sha256"] = artifact_sha256
            state["status"] = "SUCCEEDED"
            atomic_json(state_path, state)
            cursor.close()
            return validate_success(job_dir, state, result)

        part_number = int(state["next_part"])
        part_name = f"part-{part_number:06d}.tsv"
        part_path = job_dir / "parts" / part_name
        part_rows, part_sha256 = write_part(part_path, rows)
        entry = {
            "number": part_number,
            "name": part_name,
            "rows": part_rows,
            "sha256": part_sha256,
            "first_cursor": [timestamp_text(rows[0][0]), int(rows[0][1])],
            "last_cursor": [timestamp_text(rows[-1][0]), int(rows[-1][1])],
        }
        state["parts"].append(entry)
        state["last_created_at"], state["last_id"] = cursor_value(entry["last_cursor"])
        state["next_part"] = part_number + 1
        state["rows_written"] = int(state["rows_written"]) + part_rows
        state["active_seconds"] = base_active + (time.perf_counter() - started)
        atomic_json(state_path, state)
        batches_this_run += 1
        if max_batches and batches_this_run >= max_batches:
            result = aborted_result(state, "max_batches", state["active_seconds"])
            atomic_json(state_path, state)
            cursor.close()
            return result
        if sleep_ms:
            time.sleep(sleep_ms / 1000)


def run_buffered(connection, job_dir: Path) -> dict:
    state_path = job_dir / "state.json"
    result_path = job_dir / "result.json"
    if job_dir.exists():
        if state_path.is_file() and result_path.is_file():
            state = read_json(state_path)
            if state.get("job_id") != job_id_from_dir(job_dir):
                raise RuntimeError("state job_id does not match job directory")
            return validate_success(job_dir, state, read_json(result_path))
        raise RuntimeError("buffered mode requires a fresh job directory")
    job_dir.mkdir(parents=True)
    cursor = connection.cursor(buffered=True)
    high = capture_high_watermark(cursor)
    expected_rows = count_boundary_rows(cursor, high)
    state = {
        "job_id": job_id_from_dir(job_dir),
        "mode": "buffered",
        "connection_id": int(connection.connection_id),
        "high_created_at": high[0],
        "high_id": high[1],
        "expected_rows": expected_rows,
        "last_created_at": EPOCH,
        "last_id": 0,
        "next_part": 1,
        "rows_written": 0,
        "active_seconds": 0.0,
        "artifact_rows": None,
        "artifact_sha256": None,
        "parts": [],
        "status": "RUNNING",
        "abort_reason": None,
    }
    atomic_json(state_path, state)
    started = time.perf_counter()
    cursor.execute(BUFFERED_SQL, (EPOCH, 0, *high))
    rows = list(cursor.fetchall())
    artifact_rows, artifact_sha256 = write_part(job_dir / "artifact.tsv", rows)
    if artifact_rows != expected_rows:
        raise RuntimeError("buffered rows do not equal expected boundary rows")
    last_cursor = [timestamp_text(rows[-1][0]), int(rows[-1][1])]
    if cursor_value(last_cursor) != cursor_value(high):
        raise RuntimeError("buffered last cursor does not equal high watermark")
    cursor.close()
    active_seconds = time.perf_counter() - started
    result = {
        "status": "SUCCEEDED",
        "mode": "buffered",
        "job_id": state["job_id"],
        "rows": artifact_rows,
        "sha256": artifact_sha256,
        "active_seconds": active_seconds,
        "rows_per_active_second": (
            artifact_rows / active_seconds if active_seconds else 0.0
        ),
        "max_rss_bytes": max_rss_bytes(),
        "high_cursor": [high[0], high[1]],
        "last_cursor": last_cursor,
    }
    atomic_json(result_path, result)
    state.update(
        {
            "last_created_at": last_cursor[0],
            "last_id": last_cursor[1],
            "rows_written": artifact_rows,
            "active_seconds": active_seconds,
            "artifact_rows": artifact_rows,
            "artifact_sha256": artifact_sha256,
            "status": "SUCCEEDED",
        }
    )
    atomic_json(state_path, state)
    return validate_success(job_dir, state, result)


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def oltp_worker(
    config: dict,
    deadline: float,
    seed: int,
    events: queue.SimpleQueue,
) -> None:
    connection = mysql.connector.connect(**config)
    connection.autocommit = True
    cursor = connection.cursor()
    randomizer = random.Random(seed)
    try:
        while time.perf_counter() < deadline:
            probe_id = randomizer.randint(1, 10000)
            started = time.perf_counter_ns()
            try:
                cursor.execute("SELECT counter FROM oltp_probe WHERE id=%s", (probe_id,))
                cursor.fetchone()
                cursor.execute(
                    "UPDATE oltp_probe SET counter=counter+1 WHERE id=%s",
                    (probe_id,),
                )
                events.put(((time.perf_counter_ns() - started) / 1_000_000, False))
            except Exception:
                events.put((0.0, True))
    finally:
        cursor.close()
        connection.close()


def run_oltp(
    config: dict,
    duration: int,
    threads: int,
    metrics_file: Path | None,
    window_seconds: float,
    trial_id: str,
) -> dict:
    started = time.perf_counter()
    deadline = started + duration
    next_window = started + window_seconds
    events: queue.SimpleQueue = queue.SimpleQueue()
    all_latencies = []
    all_errors = 0
    window_latencies = []
    window_errors = 0
    sequence = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as pool:
        futures = [
            pool.submit(oltp_worker, config, deadline, seed, events)
            for seed in range(1, threads + 1)
        ]
        while True:
            while True:
                try:
                    latency, is_error = events.get_nowait()
                except queue.Empty:
                    break
                if is_error:
                    all_errors += 1
                    window_errors += 1
                else:
                    all_latencies.append(latency)
                    window_latencies.append(latency)
            now = time.perf_counter()
            if now >= next_window:
                sequence += 1
                if metrics_file is not None:
                    atomic_json(
                        metrics_file,
                        {
                            "status": "RUNNING",
                            "trial_id": trial_id,
                            "heartbeat_at_epoch": time.time(),
                            "window_seq": sequence,
                            "window_operations": len(window_latencies),
                            "window_errors": window_errors,
                            "window_p95_ms": percentile(window_latencies, 0.95),
                            "operations": len(all_latencies),
                            "errors": all_errors,
                            "active_elapsed_seconds": now - started,
                        },
                    )
                window_latencies = []
                window_errors = 0
                next_window = now + window_seconds
            if all(future.done() for future in futures) and events.empty():
                break
            time.sleep(0.02)
        for future in futures:
            future.result()
    result = {
        "status": (
            "SUCCEEDED"
            if all_errors == 0 and len(all_latencies) > 0
            else "FAILED"
        ),
        "mode": "oltp",
        "trial_id": trial_id,
        "operations": len(all_latencies),
        "errors": all_errors,
        "p50_ms": percentile(all_latencies, 0.50),
        "p95_ms": percentile(all_latencies, 0.95),
        "p99_ms": percentile(all_latencies, 0.99),
    }
    if metrics_file is not None and (window_latencies or window_errors):
        atomic_json(
            metrics_file,
            {
                **result,
                "trial_id": trial_id,
                "heartbeat_at_epoch": time.time(),
                "window_seq": sequence + 1,
                "window_operations": len(window_latencies),
                "window_errors": window_errors,
                "window_p95_ms": percentile(window_latencies, 0.95),
                "active_elapsed_seconds": time.perf_counter() - started,
            },
        )
    return result


def require_password(env_name: str) -> str:
    value = os.environ.get(env_name)
    if value is None:
        raise ValueError(f"password environment variable is not set: {env_name}")
    return value


def main() -> int:
    try:
        parser = StructuredArgumentParser()
        parser.add_argument("--mode", choices=("buffered", "chunked", "oltp"), required=True)
        parser.add_argument("--runtime-root", type=Path, required=True)
        parser.add_argument("--job-dir", type=Path)
        parser.add_argument("--abort-file", type=Path)
        parser.add_argument("--metrics-file", type=Path)
        parser.add_argument("--trial-id")
        parser.add_argument("--batch-size", type=int, default=1000)
        parser.add_argument("--sleep-ms", type=int, default=20)
        parser.add_argument("--max-batches", type=int, default=0)
        parser.add_argument("--min-free-bytes", type=int, default=0)
        parser.add_argument("--duration-seconds", type=int, default=60)
        parser.add_argument("--window-seconds", type=float, default=1.0)
        parser.add_argument("--threads", type=int, default=4)
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=3306)
        parser.add_argument("--user", default="root")
        parser.add_argument("--password-env", default="MYSQL_PASSWORD")
        args = parser.parse_args()
        expected_root = runtime_root(args.runtime_root)

        if not 1 <= args.batch_size <= 5000:
            raise ValueError("--batch-size must be in 1..5000")
        if not 0 <= args.sleep_ms <= 1000:
            raise ValueError("--sleep-ms must be in 0..1000")
        if not 1 <= args.threads <= 16:
            raise ValueError("--threads must be in 1..16")
        if (
            args.duration_seconds < 1
            or args.max_batches < 0
            or args.min_free_bytes < 0
            or not 0.1 <= args.window_seconds <= 10.0
        ):
            raise ValueError("duration/max-batches/disk/window argument is invalid")

        config = {
            "host": args.host,
            "port": args.port,
            "user": args.user,
            "password": require_password(args.password_env),
            "database": "mysql_senior_scenarios",
        }
        connection = None
        if args.mode == "oltp":
            if (
                not args.trial_id
                or any(not (character.isalnum() or character in "-_") for character in args.trial_id)
            ):
                raise ValueError("OLTP mode requires a safe nonempty trial-id")
            metrics_file = (
                validated_runtime_file(
                    args.metrics_file,
                    "metrics-",
                    args.trial_id,
                    expected_root,
                )
                if args.metrics_file is not None else None
            )
            result = run_oltp(
                config,
                args.duration_seconds,
                args.threads,
                metrics_file,
                args.window_seconds,
                args.trial_id,
            )
        else:
            if args.job_dir is None:
                raise ValueError("--job-dir is required for export modes")
            job_dir = validated_job_dir(args.job_dir)
            if job_dir.parent != expected_root:
                raise ValueError("job directory must be under --runtime-root")
            job_id = job_id_from_dir(job_dir)
            abort_file = (
                validated_runtime_file(
                    args.abort_file,
                    "abort-",
                    job_id,
                    expected_root,
                )
                if args.abort_file is not None else None
            )
            try:
                connection = mysql.connector.connect(**config)
                if args.mode == "buffered":
                    result = run_buffered(connection, job_dir)
                else:
                    job_dir.mkdir(parents=True, exist_ok=True)
                    result = run_chunked(
                        connection,
                        job_dir,
                        args.batch_size,
                        args.sleep_ms,
                        args.max_batches,
                        abort_file,
                        args.min_free_bytes,
                    )
            finally:
                if connection is not None:
                    connection.close()
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] in ("SUCCEEDED", "ABORTED") else 2
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

Safety／correctness requirements:

- `job_dir.resolve()` must be an immediate nonempty `job-<run-id>` child of an immediate `/private/tmp/mysql-senior-scenarios.<nonempty-suffix>` runtime directory；
- direct runner `--runtime-root`, job, abort and metrics paths must resolve under the exact same runtime root; abort／metrics names must equal `abort-<job-id>.json`／`metrics-<trial-id>.json`, and another otherwise-valid runtime root, a prefix-only name or an empty suffix is rejected；
- batch size `1..5000`, sleep `0..1000`, threads `1..16`；
- parameterized SQL for all data values；
- buffered and chunked artifacts use identical column order and canonical formatting；
- export runner JSON reports job ID, rows, SHA-256, cumulative active time／throughput, max RSS, high／last cursors and status; OLTP JSON reports its trial ID；
- CLI and committed snippets contain only `--password-env MYSQL_PASSWORD`, never a password value；
- interrupted chunked run is invoked with `--max-batches 3`, returns `ABORTED` with timing／cursor metrics, then the same job directory resumes with `--max-batches 0`；this proves process-level resume behavior, not host power-loss durability。

- [ ] **Step 6: Define performance matrix and stop conditions**

Run groups, each three times with a fresh job directory:

| Group | OLTP probe | Export |
|---|---|---|
| control | 60 s, 4 threads | none |
| buffered | 60 s, 4 threads | one buffered query／artifact |
| chunked | 60 s, 4 threads | batch=1000, sleep=20 ms |

Start OLTP before export, but do not use wall time alone as proof of load. OLTP atomically replaces a trial-bound heartbeat containing `trial_id`, epoch timestamp, advancing `window_seq`, positive one-second operations, window errors／P95, cumulative operations／errors and active elapsed time. Each accepted sequence must have positive operations and active time; cumulative operations and active time strictly advance, cumulative errors never decrease, and window deltas reconcile with the cumulative deltas (exactly for consecutive sequences, at least covered when observations skip sequences). The controller rejects contradictory or pre-existing trial files and launches export only after observing at least five fresh, advancing, nonempty same-trial windows covering at least five active seconds and positive cumulative work.

Before and throughout export, missing／malformed／stale／wrong-trial／regressing／changed or nonadvancing metrics fail closed after only the declared startup／heartbeat grace. Cumulative errors cannot be masked by a zero-error latest window; cumulative errors, window errors, P95 and live disk each remain independent stop gates. The final OLTP child result must also report positive cumulative operations and zero errors to be `SUCCEEDED`; a zero-work early exit cannot make a control trial pass. Record final OLTP p50／p95／p99／errors, every accepted live window, export active time／rows-per-active-second／max RSS, MySQL processlist／temporary-table／sort deltas and exact artifact correctness.

The numeric S disk gate is fixed before all groups:

```text
EXPECTED_ARTIFACT_BYTES = expected_rows(100000) * 256 = 25,600,000
MIN_FREE_BYTES = 2 * EXPECTED_ARTIFACT_BYTES + 5 * 1024^3
               = 5,419,909,120
```

The controller checks `MIN_FREE_BYTES` before each group and throughout the live 60-second window. Chunked mode also checks it itself before issuing every new batch. A P95／error／disk breach atomically writes an abort signal: chunked finishes at most its in-flight query/part and persists `ABORTED` before the next fetch; buffered has no batch boundary, so the controller reads its persisted connection ID, issues sanitized `KILL QUERY`, terminates the child if needed and writes separate external `ABORTED` evidence. After the child is known stopped, an incomplete checkpoint is persisted as `ABORTED`; if the runner had already atomically completed, its genuine `SUCCEEDED` checkpoint is preserved, but the controller's gate-breach evidence remains `ABORTED` and the trial can never become a performance success.

On normal child exit, the controller accepts exactly one structured JSON object across stdout／stderr and reconciles it with return code and persisted state. Only child `SUCCEEDED`, return code `0`, and consistent state／result／artifact integrity can produce controller success; `ABORTED` with exit code 0 remains `ABORTED`, an unstarted export is never success, and missing／malformed／multiple／contradictory child output is `FAILED`. The successful export is re-invoked through the runner's manifest-linked fast path before evidence is accepted. MySQL restart or fingerprint divergence also invalidates the trial. Never rank `ABORTED` or planned-resume correctness runs as steady-state throughput.

Pre-run hypotheses:

- buffered control should hold one connection and more client memory；
- chunking／sleep should reduce burst pressure and provide checkpoints, at the cost of longer completion；
- exact latency differences are unknown；
- a read replica can isolate some CPU／I/O but introduces lag, snapshot and capacity tradeoffs；
- a long MVCC transaction is not a free snapshot solution。

Mark S test `READY_UNRUN`, canonical mechanism links `REUSED`, production topology choices `REASONED`.

- [ ] **Step 7: Verify official claims and write answer forms**

Use official MySQL 8.0 documentation for consistent nonlocking reads／ReadView, long transaction effects, cursor／result fetching, temporary tables and replica lag boundaries; use official Connector/Python docs for buffered vs nonbuffered cursors. Cite primary sources.

The 30-second answer must choose async job + a **conditional** boundary (monotone immutable keys or materialized snapshot) + keyset chunks + bounded buffer + checkpoint + verified atomic artifact, then distinguish internal manifest integrity from the independent cross-mode SHA／business audit and name live OLTP／disk gates. It must not claim `(created_at,id)` alone excludes every later insert or that row-count-only publish proves business correctness. The 3–5-minute answer must distinguish membership boundary from value snapshot, explain backdated inserts, tier placement, backpressure, resume ambiguity, validation, replica／warehouse alternatives and rollback／rebuild.

- [ ] **Step 8: Link route, verify, and commit expectation**

Update README to link `[大型报表与导出隔离](04-report-export-isolation.md)` with `READY_UNRUN`.

Run:

```bash
rg -n 'READY_UNRUN|high watermark|backdated|insertion-monotone|更新|删除|validate_manifest|validate_success|window_p95_ms|ABORTED|artifact.tsv|5419909120|30 秒|3–5 分钟' mysql-handson/13-senior-scenarios/04-report-export-isolation.md
git diff --check -- mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/04-report-export-isolation.md
git add mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/04-report-export-isolation.md
git commit -m "docs(mysql): define report export isolation scenario"
```

---

### Task 10: 跑 report／export S 級干擾與 restart evidence

**Files:**
- Modify: `mysql-handson/13-senior-scenarios/04-report-export-isolation.md`
- Modify: `mysql-handson/13-senior-scenarios/README.md`

**Interfaces:**
- Consumes: Task 9 fixed schema, query, corrected runner, live controller, performance matrix and frozen S dataset。
- Produces: control／buffered／chunked OLTP comparison, live current-run abort evidence, identical artifacts, interrupted-resume proof and bounded claims。

- [ ] **Step 1: Preflight and materialize both canonical temp programs**

Repeat base-lab ownership／health, MySQL version／durability, transaction isolation, free disk and host resource checks. Set `MYSQL_SCENARIO_PORT=33306` for the owned dedicated container and verify that exact port/container label before use. Create the runtime directory with `MYSQL_SCENARIO_RUN_DIR=$(mktemp -d /private/tmp/mysql-senior-scenarios.XXXXXX)`. Copy the Task 9 runner block to `$MYSQL_SCENARIO_RUN_DIR/export_runner.py` and the controller block below to `$MYSQL_SCENARIO_RUN_DIR/scenario_controller.py`. Obtain the password outside committed snippets and export it only in the invoking shell as `MYSQL_PASSWORD`.

```bash
uv run --with mysql-connector-python==9.7.0 python -m py_compile \
  "$MYSQL_SCENARIO_RUN_DIR/export_runner.py" \
  "$MYSQL_SCENARIO_RUN_DIR/scenario_controller.py"
```

The second embedded block is the one canonical temporary controller source:

```python
from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import mysql.connector


RUNTIME_PREFIX = "mysql-senior-scenarios."


class StructuredArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path.name} is not a JSON object")
    return value


def validated_runtime_root(path: Path) -> Path:
    resolved = path.resolve()
    private_tmp = Path("/private/tmp").resolve()
    if (
        resolved.parent != private_tmp
        or not resolved.name.startswith(RUNTIME_PREFIX)
        or resolved.name == RUNTIME_PREFIX
    ):
        raise ValueError("runtime root is outside the allowed nonempty prefix")
    return resolved


def validated_job_dir(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if (
        resolved.parent != root
        or not resolved.name.startswith("job-")
        or resolved.name == "job-"
    ):
        raise ValueError("job directory must be an immediate job-<run-id> child")
    return resolved


def gate_reason(
    metrics: dict | None,
    free_bytes: int,
    p95_budget_ms: float,
    min_free_bytes: int,
) -> str | None:
    if free_bytes < min_free_bytes:
        return f"disk_free_bytes={free_bytes} below {min_free_bytes}"
    if metrics is None:
        return None
    if int(metrics.get("errors", 0)) > 0:
        return "OLTP cumulative errors exceeded zero"
    if int(metrics.get("window_errors", 0)) > 0:
        return "OLTP window errors exceeded zero"
    if (
        p95_budget_ms > 0
        and int(metrics.get("window_operations", 0)) > 0
        and float(metrics.get("window_p95_ms", 0.0)) > p95_budget_ms
    ):
        return (
            f"OLTP window P95 {metrics['window_p95_ms']} "
            f"exceeded {p95_budget_ms}"
        )
    return None


def new_metrics_tracker() -> dict:
    return {
        "window_seq": 0,
        "last_advance_monotonic": None,
        "operations": 0,
        "errors": 0,
        "active_elapsed_seconds": 0.0,
        "activity_windows": 0,
        "last_window_operations": 0,
        "last_status": None,
        "sequence_payload": None,
        "accepted_windows": [],
    }


def _integer_field(metrics: dict, name: str) -> int:
    value = metrics.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _float_field(metrics: dict, name: str) -> float:
    value = metrics.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return parsed


def inspect_metrics(
    metrics: dict | None,
    trial_id: str,
    now_epoch: float,
    now_monotonic: float,
    tracker: dict,
    heartbeat_grace_seconds: float,
    require_present: bool,
) -> tuple[dict, str | None]:
    if metrics is None:
        return (
            dict(tracker),
            (
                "OLTP metrics missing"
                if require_present or int(tracker.get("window_seq", 0)) > 0
                else None
            ),
        )
    try:
        if metrics.get("status") not in ("RUNNING", "SUCCEEDED", "FAILED"):
            raise ValueError("status is invalid")
        if metrics.get("trial_id") != trial_id:
            return dict(tracker), "OLTP metrics trial_id mismatch"
        heartbeat = _float_field(metrics, "heartbeat_at_epoch")
        if heartbeat > now_epoch + 1.0:
            return dict(tracker), "OLTP metrics heartbeat is in the future"
        if now_epoch - heartbeat > heartbeat_grace_seconds:
            return dict(tracker), "OLTP metrics heartbeat is stale"
        sequence = _integer_field(metrics, "window_seq")
        if sequence < 1:
            raise ValueError("window_seq must be positive")
        window_operations = _integer_field(metrics, "window_operations")
        if window_operations < 1:
            raise ValueError("window_operations must be positive")
        window_errors = _integer_field(metrics, "window_errors")
        window_p95 = _float_field(metrics, "window_p95_ms")
        operations = _integer_field(metrics, "operations")
        errors = _integer_field(metrics, "errors")
        active_elapsed = _float_field(metrics, "active_elapsed_seconds")
    except (TypeError, ValueError) as exc:
        return dict(tracker), f"OLTP metrics malformed: {exc}"

    previous_sequence = int(tracker["window_seq"])
    if sequence < previous_sequence:
        return dict(tracker), "OLTP metrics sequence regressed"
    sequence_payload = (
        metrics["status"],
        heartbeat,
        sequence,
        window_operations,
        window_errors,
        window_p95,
        operations,
        errors,
        active_elapsed,
    )
    if sequence == previous_sequence:
        if sequence_payload != tracker.get("sequence_payload"):
            return dict(tracker), "OLTP metrics sequence payload changed"
        last_advance = tracker.get("last_advance_monotonic")
        if (
            last_advance is not None
            and now_monotonic - float(last_advance) > heartbeat_grace_seconds
        ):
            return dict(tracker), "OLTP metrics sequence is nonadvancing"
        return dict(tracker), None
    previous_operations = int(tracker["operations"])
    previous_errors = int(tracker["errors"])
    previous_active_elapsed = float(tracker["active_elapsed_seconds"])
    if previous_sequence == 0:
        if operations < window_operations:
            return dict(tracker), (
                "OLTP metrics window operations exceed cumulative operations"
            )
        if errors < window_errors:
            return dict(tracker), (
                "OLTP metrics window errors exceed cumulative errors"
            )
        if active_elapsed <= 0.0:
            return dict(tracker), (
                "OLTP metrics active elapsed time must be positive"
            )
    else:
        if operations <= previous_operations:
            return dict(tracker), (
                "OLTP metrics cumulative operations did not advance"
            )
        if errors < previous_errors:
            return dict(tracker), "OLTP metrics cumulative errors regressed"
        if active_elapsed <= previous_active_elapsed:
            return dict(tracker), (
                "OLTP metrics active elapsed time did not advance"
            )
        operation_delta = operations - previous_operations
        error_delta = errors - previous_errors
        if operation_delta < window_operations:
            return dict(tracker), (
                "OLTP metrics window operations exceed cumulative delta"
            )
        if error_delta < window_errors:
            return dict(tracker), (
                "OLTP metrics window errors exceed cumulative delta"
            )
        if sequence == previous_sequence + 1:
            if operation_delta != window_operations:
                return dict(tracker), (
                    "OLTP metrics consecutive operation delta is inconsistent"
                )
            if error_delta != window_errors:
                return dict(tracker), (
                    "OLTP metrics consecutive error delta is inconsistent"
                )

    updated = dict(tracker)
    updated["window_seq"] = sequence
    updated["last_advance_monotonic"] = now_monotonic
    updated["operations"] = operations
    updated["errors"] = errors
    updated["active_elapsed_seconds"] = active_elapsed
    updated["last_window_operations"] = window_operations
    updated["last_status"] = metrics["status"]
    updated["sequence_payload"] = sequence_payload
    accepted_windows = list(updated["accepted_windows"])
    accepted_windows.append(
        {
            "status": metrics["status"],
            "trial_id": trial_id,
            "heartbeat_at_epoch": heartbeat,
            "window_seq": sequence,
            "window_operations": window_operations,
            "window_errors": window_errors,
            "window_p95_ms": window_p95,
            "operations": operations,
            "errors": errors,
            "active_elapsed_seconds": active_elapsed,
        }
    )
    updated["accepted_windows"] = accepted_windows
    if metrics["status"] == "RUNNING":
        updated["activity_windows"] = int(updated["activity_windows"]) + 1
    return updated, None


def ready_for_export(tracker: dict, minimum_active_seconds: float) -> bool:
    return (
        tracker.get("last_status") == "RUNNING"
        and int(tracker.get("activity_windows", 0)) >= 5
        and float(tracker.get("active_elapsed_seconds", 0.0))
        >= max(5.0, minimum_active_seconds)
        and int(tracker.get("operations", 0)) > 0
        and int(tracker.get("last_window_operations", 0)) > 0
    )


def _parse_child_output(stdout: str, stderr: str) -> dict:
    records = []
    for stream_name, content in (("stdout", stdout), ("stderr", stderr)):
        for line in content.splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"child {stream_name} contains malformed JSON"
                ) from exc
            if not isinstance(value, dict):
                raise RuntimeError(f"child {stream_name} JSON is not an object")
            records.append(value)
    if len(records) != 1:
        raise RuntimeError("child must emit exactly one structured JSON object")
    if records[0].get("status") not in ("SUCCEEDED", "ABORTED", "FAILED"):
        raise RuntimeError("child JSON status is invalid")
    return records[0]


def read_child_result(stdout_path: Path, stderr_path: Path) -> dict:
    stdout = stdout_path.read_text(encoding="utf-8")
    stderr = stderr_path.read_text(encoding="utf-8")
    return _parse_child_output(stdout, stderr)


def _matching_result_fields(left: dict, right: dict) -> bool:
    return left == right


def reconcile_export_result(
    mode: str,
    returncode: int | None,
    child: dict,
    job_dir: Path,
    verifier_command: list[str],
    run_verifier=subprocess.run,
) -> dict:
    if returncode is None:
        raise RuntimeError("export child was never started")
    state_path = job_dir / "state.json"
    if not state_path.is_file():
        raise RuntimeError("export persisted state is missing")
    state = read_json(state_path)
    expected_job_id = job_dir.name[len("job-") :]
    if state.get("job_id") != expected_job_id or state.get("mode") != mode:
        raise RuntimeError("export persisted state identity is invalid")
    if child.get("mode") != mode or child.get("job_id") != expected_job_id:
        raise RuntimeError("export child identity contradicts persisted state")

    status = child["status"]
    if status == "ABORTED":
        if returncode != 0 or state.get("status") != "ABORTED":
            raise RuntimeError("ABORTED child contradicts return code or persisted state")
        if int(child.get("rows", -1)) != int(state.get("rows_written", -2)):
            raise RuntimeError("ABORTED child rows contradict persisted checkpoint")
        if child.get("reason") != state.get("abort_reason"):
            raise RuntimeError("ABORTED child reason contradicts persisted checkpoint")
        if child.get("high_cursor") != [
            state.get("high_created_at"),
            state.get("high_id"),
        ]:
            raise RuntimeError("ABORTED child high cursor contradicts persisted checkpoint")
        if child.get("last_cursor") != [
            state.get("last_created_at"),
            state.get("last_id"),
        ]:
            raise RuntimeError("ABORTED child last cursor contradicts persisted checkpoint")
        if int(child.get("parts", -1)) != len(state.get("parts", [])):
            raise RuntimeError("ABORTED child part count contradicts persisted checkpoint")
        if float(child.get("active_seconds", -1.0)) != float(
            state.get("active_seconds", -2.0)
        ):
            raise RuntimeError("ABORTED child timing contradicts persisted checkpoint")
        if (job_dir / "result.json").exists():
            raise RuntimeError("ABORTED export unexpectedly has result.json")
        return child

    if status == "FAILED":
        if returncode == 0 or state.get("status") == "SUCCEEDED":
            raise RuntimeError("FAILED child contradicts return code or persisted state")
        return child

    if returncode != 0 or state.get("status") != "SUCCEEDED":
        raise RuntimeError("SUCCEEDED child contradicts return code or persisted state")
    result_path = job_dir / "result.json"
    if not result_path.is_file():
        raise RuntimeError("SUCCEEDED export result.json is missing")
    persisted = read_json(result_path)
    if persisted.get("status") != "SUCCEEDED":
        raise RuntimeError("persisted export result is not SUCCEEDED")
    if not _matching_result_fields(child, persisted):
        raise RuntimeError("child JSON contradicts persisted export result")

    verification = run_verifier(
        verifier_command,
        capture_output=True,
        text=True,
        check=False,
    )
    verified = _parse_child_output(
        verification.stdout or "",
        verification.stderr or "",
    )
    if verification.returncode != 0 or verified.get("status") != "SUCCEEDED":
        raise RuntimeError("runner fast-path integrity verification failed")
    if not _matching_result_fields(verified, persisted):
        raise RuntimeError("runner verifier contradicts persisted export result")
    return persisted


def reconcile_oltp_result(
    returncode: int,
    child: dict,
    trial_id: str,
) -> dict:
    if child.get("mode") != "oltp" or child.get("trial_id") != trial_id:
        raise RuntimeError("OLTP child identity is invalid")
    try:
        operations = _integer_field(child, "operations")
        errors = _integer_field(child, "errors")
    except ValueError as exc:
        raise RuntimeError(f"OLTP child counters are invalid: {exc}") from exc
    if (
        returncode == 0
        and child.get("status") == "SUCCEEDED"
        and operations > 0
        and errors == 0
    ):
        return child
    if returncode != 0 and child.get("status") == "FAILED":
        return child
    raise RuntimeError("OLTP child JSON contradicts its return code or trial identity")


def terminate_process(process, grace_seconds: float) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=grace_seconds)


def wait_for_state(job_dir: Path, timeout_seconds: float) -> dict | None:
    deadline = time.monotonic() + timeout_seconds
    state_path = job_dir / "state.json"
    while time.monotonic() < deadline:
        if state_path.is_file():
            return read_json(state_path)
        time.sleep(0.05)
    return None


def kill_buffered_query(config: dict, connection_id: int) -> None:
    validated_id = int(connection_id)
    if validated_id <= 0:
        raise ValueError("connection_id must be positive")
    admin = mysql.connector.connect(**config)
    cursor = admin.cursor()
    try:
        cursor.execute(f"KILL QUERY {validated_id}")
    finally:
        cursor.close()
        admin.close()


def _persist_aborted_checkpoint(job_dir: Path, reason: str) -> str:
    state = wait_for_state(job_dir, 0.2)
    if state is None:
        return "MISSING"
    if state.get("status") == "SUCCEEDED":
        return "SUCCEEDED"
    state["status"] = "ABORTED"
    state["abort_reason"] = reason
    atomic_json(job_dir / "state.json", state)
    return "ABORTED"


def abort_export(
    mode: str,
    process,
    job_dir: Path,
    abort_file: Path,
    reason: str,
    admin_config: dict,
    grace_seconds: float,
    kill_query=kill_buffered_query,
) -> dict:
    atomic_json(
        abort_file,
        {"status": "ABORT_REQUESTED", "reason": reason, "mode": mode},
    )
    evidence = {
        "status": "ABORTED",
        "mode": mode,
        "reason": reason,
        "kill_query_sent": False,
        "forced_termination": False,
    }
    if process is None:
        evidence["not_started"] = True
        return evidence
    if process.poll() is not None:
        evidence["already_exited"] = True
        evidence["persisted_state_status"] = _persist_aborted_checkpoint(
            job_dir, reason
        )
        return evidence

    if mode == "buffered":
        state = wait_for_state(job_dir, 2.0)
        if state is not None and state.get("connection_id") is not None:
            try:
                kill_query(admin_config, int(state["connection_id"]))
                evidence["kill_query_sent"] = True
            except Exception as exc:
                evidence["kill_query_error"] = f"{type(exc).__name__}: {exc}"
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        evidence["forced_termination"] = True
        terminate_process(process, grace_seconds)
    evidence["persisted_state_status"] = _persist_aborted_checkpoint(
        job_dir, reason
    )
    return evidence


def _close_quietly(resource) -> None:
    if resource is not None:
        try:
            resource.close()
        except Exception:
            pass


def run_kill_query_preflight(
    config: dict,
    connect=mysql.connector.connect,
    pause=time.sleep,
) -> dict:
    victim = None
    killer = None
    victim_cursor = None
    killer_cursor = None
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = None
    entered_execute = threading.Event()
    try:
        victim = connect(**config)
        killer = connect(**config)
        victim_cursor = victim.cursor()
        killer_cursor = killer.cursor()
        connection_id = int(victim.connection_id)
        if connection_id <= 0:
            raise RuntimeError("preflight victim connection_id is invalid")

        def blocking_query() -> None:
            entered_execute.set()
            victim_cursor.execute("SELECT SLEEP(30), 1")
            victim_cursor.fetchone()

        future = executor.submit(blocking_query)
        if not entered_execute.wait(timeout=2.0):
            raise RuntimeError("preflight victim query did not start")
        pause(0.2)
        killer_cursor.execute(f"KILL QUERY {connection_id}")
        try:
            future.result(timeout=5.0)
        except concurrent.futures.TimeoutError as exc:
            raise RuntimeError("KILL QUERY did not interrupt the victim") from exc
        except Exception as exc:
            if int(getattr(exc, "errno", -1)) != 1317:
                raise
        else:
            raise RuntimeError("KILL QUERY victim completed without interruption")
        return {
            "status": "SUCCEEDED",
            "mode": "preflight-kill",
            "connection_id": connection_id,
            "observed_errno": 1317,
        }
    finally:
        _close_quietly(killer_cursor)
        _close_quietly(killer)
        if future is not None and not future.done():
            _close_quietly(victim)
            victim = None
        _close_quietly(victim_cursor)
        _close_quietly(victim)
        if future is not None and not future.done():
            try:
                future.result(timeout=1.0)
            except Exception:
                pass
        executor.shutdown(wait=False, cancel_futures=True)


def load_metrics(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return read_json(path)


def _require_fresh_paths(paths: list[Path]) -> None:
    existing = [path.name for path in paths if path.exists()]
    if existing:
        raise RuntimeError(
            "trial paths must not pre-exist: " + ", ".join(sorted(existing))
        )


def main() -> int:
    result_file = None
    oltp = None
    export = None
    handles = []
    try:
        parser = StructuredArgumentParser()
        parser.add_argument("--runner", type=Path, required=True)
        parser.add_argument("--runtime-root", type=Path, required=True)
        parser.add_argument("--trial-id", required=True)
        parser.add_argument("--job-dir", type=Path)
        parser.add_argument(
            "--export-mode",
            choices=("none", "buffered", "chunked", "preflight-kill"),
            required=True,
        )
        parser.add_argument("--p95-budget-ms", type=float, default=0.0)
        parser.add_argument("--min-free-bytes", type=int, required=True)
        parser.add_argument("--duration-seconds", type=int, default=60)
        parser.add_argument("--start-delay-seconds", type=float, default=5.0)
        parser.add_argument("--startup-grace-seconds", type=float, default=12.0)
        parser.add_argument("--heartbeat-grace-seconds", type=float, default=2.5)
        parser.add_argument("--threads", type=int, default=4)
        parser.add_argument("--batch-size", type=int, default=1000)
        parser.add_argument("--sleep-ms", type=int, default=20)
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=3306)
        parser.add_argument("--user", default="root")
        parser.add_argument("--password-env", default="MYSQL_PASSWORD")
        args = parser.parse_args()

        root = validated_runtime_root(args.runtime_root)
        runner = args.runner.resolve()
        if runner.parent != root or runner.name != "export_runner.py":
            raise ValueError("runner must be runtime-root/export_runner.py")
        if args.export_mode in ("buffered", "chunked") and args.job_dir is None:
            raise ValueError("--job-dir is required for export trials")
        if (
            not args.trial_id
            or any(
                not (character.isalnum() or character in "-_")
                for character in args.trial_id
            )
        ):
            raise ValueError(
                "trial-id must use only letters, digits, dash, or underscore"
            )
        job_dir = (
            validated_job_dir(args.job_dir, root)
            if args.job_dir is not None
            else root / "job-unused"
        )
        if (
            args.export_mode in ("buffered", "chunked")
            and job_dir.name != f"job-{args.trial_id}"
        ):
            raise ValueError("job directory run-id must equal trial-id")
        if (
            args.min_free_bytes <= 0
            or args.duration_seconds < 1
            or not 1 <= args.threads <= 16
            or args.start_delay_seconds < 5.0
            or args.startup_grace_seconds <= args.start_delay_seconds
            or not 0.5 <= args.heartbeat_grace_seconds <= 10.0
        ):
            raise ValueError("controller numeric argument is invalid")
        if shutil.disk_usage(root).free < args.min_free_bytes:
            raise RuntimeError("pre-group disk gate failed")
        password = os.environ.get(args.password_env)
        if password is None:
            raise ValueError(
                f"password environment variable is not set: {args.password_env}"
            )
        admin_config = {
            "host": args.host,
            "port": args.port,
            "user": args.user,
            "password": password,
            "database": "mysql_senior_scenarios",
        }

        run_id = args.trial_id
        metrics_file = root / f"metrics-{run_id}.json"
        abort_file = root / f"abort-{run_id}.json"
        candidate_result_file = root / f"controller-result-{run_id}.json"
        oltp_stdout_path = root / f"oltp-{run_id}.stdout.json"
        oltp_stderr_path = root / f"oltp-{run_id}.stderr.json"
        export_stdout_path = root / f"export-{run_id}.stdout.json"
        export_stderr_path = root / f"export-{run_id}.stderr.json"
        _require_fresh_paths(
            [
                metrics_file,
                abort_file,
                candidate_result_file,
                oltp_stdout_path,
                oltp_stderr_path,
                export_stdout_path,
                export_stderr_path,
            ]
        )
        result_file = candidate_result_file
        if args.export_mode in ("buffered", "chunked") and job_dir.exists():
            raise RuntimeError("each trial requires a fresh job directory")

        if args.export_mode == "preflight-kill":
            result = run_kill_query_preflight(admin_config)
            atomic_json(result_file, result)
            print(json.dumps(result, sort_keys=True))
            return 0

        common = [
            sys.executable,
            str(runner),
            "--runtime-root",
            str(root),
            "--host",
            args.host,
            "--port",
            str(args.port),
            "--user",
            args.user,
            "--password-env",
            args.password_env,
        ]
        oltp_stdout = oltp_stdout_path.open("w", encoding="utf-8")
        oltp_stderr = oltp_stderr_path.open("w", encoding="utf-8")
        handles.extend((oltp_stdout, oltp_stderr))
        oltp = subprocess.Popen(
            [
                *common,
                "--mode",
                "oltp",
                "--duration-seconds",
                str(args.duration_seconds),
                "--threads",
                str(args.threads),
                "--metrics-file",
                str(metrics_file),
                "--trial-id",
                run_id,
            ],
            stdout=oltp_stdout,
            stderr=oltp_stderr,
            text=True,
        )
        export_command = None
        breach = None
        export_abort = None
        started = time.monotonic()
        tracker = new_metrics_tracker()
        latest_metrics = None

        while True:
            now_monotonic = time.monotonic()
            now_epoch = time.time()
            elapsed = now_monotonic - started
            try:
                latest_metrics = load_metrics(metrics_file)
            except Exception as exc:
                breach = f"OLTP metrics malformed: {type(exc).__name__}: {exc}"
                break
            require_metrics = (
                export is not None or elapsed >= args.startup_grace_seconds
            )
            tracker, breach = inspect_metrics(
                latest_metrics,
                run_id,
                now_epoch,
                now_monotonic,
                tracker,
                args.heartbeat_grace_seconds,
                require_metrics,
            )
            if breach is None:
                breach = gate_reason(
                    latest_metrics,
                    shutil.disk_usage(root).free,
                    args.p95_budget_ms,
                    args.min_free_bytes,
                )
            if breach is not None:
                break

            if (
                export is None
                and args.export_mode in ("buffered", "chunked")
                and ready_for_export(tracker, args.start_delay_seconds)
            ):
                export_stdout = export_stdout_path.open("w", encoding="utf-8")
                export_stderr = export_stderr_path.open("w", encoding="utf-8")
                handles.extend((export_stdout, export_stderr))
                export_command = [
                    *common,
                    "--mode",
                    args.export_mode,
                    "--job-dir",
                    str(job_dir),
                    "--abort-file",
                    str(abort_file),
                ]
                if args.export_mode == "chunked":
                    export_command.extend(
                        [
                            "--batch-size",
                            str(args.batch_size),
                            "--sleep-ms",
                            str(args.sleep_ms),
                            "--min-free-bytes",
                            str(args.min_free_bytes),
                        ]
                    )
                export = subprocess.Popen(
                    export_command,
                    stdout=export_stdout,
                    stderr=export_stderr,
                    text=True,
                )

            if (
                export is None
                and args.export_mode in ("buffered", "chunked")
                and elapsed >= args.startup_grace_seconds
            ):
                breach = (
                    "OLTP did not produce five fresh nonempty windows "
                    "within startup grace"
                )
                break
            oltp_running = oltp.poll() is None
            export_running = export is not None and export.poll() is None
            if not oltp_running and export_running:
                breach = "OLTP ended before concurrent export completed"
                break
            if not oltp_running and not export_running:
                break
            time.sleep(0.1)

        if breach is not None:
            if export is not None:
                export_abort = abort_export(
                    args.export_mode,
                    export,
                    job_dir,
                    abort_file,
                    breach,
                    admin_config,
                    5.0,
                )
            terminate_process(oltp, 2.0)
            result = {
                "status": "ABORTED",
                "mode": args.export_mode,
                "reason": breach,
                "accepted_windows": list(tracker["accepted_windows"]),
                "export_abort": export_abort,
                "oltp_returncode": oltp.poll(),
                "export_returncode": export.poll() if export is not None else None,
            }
        else:
            oltp_rc = oltp.wait()
            export_rc = export.wait() if export is not None else None
            for handle in handles:
                handle.close()
            oltp_child = read_child_result(oltp_stdout_path, oltp_stderr_path)
            oltp_result = reconcile_oltp_result(oltp_rc, oltp_child, run_id)
            if args.export_mode == "none":
                if export is not None:
                    raise RuntimeError("control trial unexpectedly started export")
                export_result = None
                status = (
                    "SUCCEEDED"
                    if oltp_result["status"] == "SUCCEEDED"
                    else "FAILED"
                )
            else:
                if export is None or export_command is None:
                    raise RuntimeError(
                        "export never started from five fresh OLTP windows"
                    )
                export_child = read_child_result(
                    export_stdout_path, export_stderr_path
                )
                export_result = reconcile_export_result(
                    args.export_mode,
                    export_rc,
                    export_child,
                    job_dir,
                    export_command,
                )
                if oltp_result["status"] != "SUCCEEDED":
                    status = "FAILED"
                else:
                    status = export_result["status"]
            result = {
                "status": status,
                "mode": args.export_mode,
                "accepted_windows": list(tracker["accepted_windows"]),
                "oltp_returncode": oltp_rc,
                "export_returncode": export_rc,
                "oltp_result": oltp_result,
                "export_result": export_result,
            }
        atomic_json(result_file, result)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] in ("SUCCEEDED", "ABORTED") else 2
    except Exception as exc:
        result = {
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        if result_file is not None:
            try:
                atomic_json(result_file, result)
            except Exception:
                pass
        print(json.dumps(result, sort_keys=True), file=sys.stderr)
        return 2
    finally:
        terminate_process(export, 1.0)
        terminate_process(oltp, 1.0)
        for handle in handles:
            _close_quietly(handle)


if __name__ == "__main__":
    raise SystemExit(main())
```

Expected: both syntax exits `0`; no global MySQL variable changes. The controller is temporary-only and is not added as a repository script. Every trial ID owns fresh metrics／abort／controller-result／stdout／stderr files; any pre-existing path is rejected before a child starts. Normal completion is based on the single structured child JSON plus persisted integrity, never return code alone.

- [ ] **Step 2: Seed and verify the S dataset**

Create exactly 100,000 orders, 300,000 items and 10,000 probe rows. Run `ANALYZE TABLE`. Verify counts, order min／max tuple, three items per order and exact source aggregate fingerprints before performance runs.

After seed, freeze both report source tables for the entire matrix. The dedicated S container has no other report writer. On an interrupted rerun, first run the exact trigger teardown below, drop／recreate the scenario tables, reseed, and use fresh trial paths; never continue from an unknown partially frozen dataset.

Run this teardown before trigger creation and run the same block again only after the final post-matrix source fingerprint:

```sql
DROP TRIGGER IF EXISTS freeze_report_order_insert;
DROP TRIGGER IF EXISTS freeze_report_order_update;
DROP TRIGGER IF EXISTS freeze_report_order_delete;
DROP TRIGGER IF EXISTS freeze_report_item_insert;
DROP TRIGGER IF EXISTS freeze_report_item_update;
DROP TRIGGER IF EXISTS freeze_report_item_delete;
```

Add six `BEFORE` triggers so even the experiment account cannot introduce an in-bound／backdated row or mutate an existing value:

```sql
CREATE TRIGGER freeze_report_order_insert BEFORE INSERT ON report_order
FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='report dataset frozen';
CREATE TRIGGER freeze_report_order_update BEFORE UPDATE ON report_order
FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='report dataset frozen';
CREATE TRIGGER freeze_report_order_delete BEFORE DELETE ON report_order
FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='report dataset frozen';
CREATE TRIGGER freeze_report_item_insert BEFORE INSERT ON report_item
FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='report dataset frozen';
CREATE TRIGGER freeze_report_item_update BEFORE UPDATE ON report_item
FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='report dataset frozen';
CREATE TRIGGER freeze_report_item_delete BEFORE DELETE ON report_item
FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='report dataset frozen';
```

Run negative immutability probes and require all to fail with `report dataset frozen`: a backdated `report_order` INSERT whose `(created_at,id) <= captured high`, one UPDATE, one DELETE, and one INSERT／UPDATE／DELETE against `report_item`. Re-run counts and source fingerprints after the negative probes, after every group and at the end; they must be byte/numeric identical. Only `oltp_probe` may change. This S freeze is the reason cross-invocation resume can be compared exactly; it is not evidence that a bare production high watermark freezes membership.

- [ ] **Step 3: Establish the OLTP-only control three times**

Predeclare the numeric disk formula and require the computed threshold before **each** group:

```bash
EXPECTED_ROWS=100000
EXPECTED_ROW_BYTES=256
MIN_FREE_BYTES=5419909120
```

The equality is binding: `MIN_FREE_BYTES = 2 * 100000 * 256 + 5 * 1024^3 = 5,419,909,120`.

Before any timed control or buffered trial, prove that the controller identity can interrupt a different connection. This mode opens two disposable connections, starts compound statement `SELECT SLEEP(30), 1` on the victim, issues `KILL QUERY <validated-positive-connection-id>` on the other, requires victim errno `1317`, then closes both connections. The extra select expression is intentional: MySQL documents that an interrupted standalone `SELECT SLEEP(...)` returns `1` without a query error, whereas interrupted `SLEEP()` used as only part of a query follows the query-interruption error path. [MySQL 8.0 `SLEEP()`](https://dev.mysql.com/doc/refman/8.0/en/miscellaneous-functions.html)

```bash
uv run --with mysql-connector-python==9.7.0 python \
  "$MYSQL_SCENARIO_RUN_DIR/scenario_controller.py" \
  --runner "$MYSQL_SCENARIO_RUN_DIR/export_runner.py" \
  --runtime-root "$MYSQL_SCENARIO_RUN_DIR" \
  --trial-id kill-preflight-1 --export-mode preflight-kill \
  --min-free-bytes "$MIN_FREE_BYTES" \
  --host 127.0.0.1 --port "$MYSQL_SCENARIO_PORT" \
  --user root --password-env MYSQL_PASSWORD
```

Require controller status `SUCCEEDED`, mode `preflight-kill` and observed errno `1317`. Any connection, permission, interruption, cleanup or structured-result failure stops the matrix; in particular, skip all buffered trials rather than discovering missing `KILL QUERY` authority only after a live breach.

Run the controller three times with unique trial IDs `control-1..3`, `--export-mode none`, `--duration-seconds 60`, `--threads 4`, `--p95-budget-ms 0` and `--min-free-bytes "$MIN_FREE_BYTES"`. Example for the first trial:

```bash
uv run --with mysql-connector-python==9.7.0 python \
  "$MYSQL_SCENARIO_RUN_DIR/scenario_controller.py" \
  --runner "$MYSQL_SCENARIO_RUN_DIR/export_runner.py" \
  --runtime-root "$MYSQL_SCENARIO_RUN_DIR" \
  --trial-id control-1 --export-mode none \
  --duration-seconds 60 --threads 4 \
  --p95-budget-ms 0 --min-free-bytes "$MIN_FREE_BYTES" \
  --host 127.0.0.1 --port "$MYSQL_SCENARIO_PORT" \
  --user root --password-env MYSQL_PASSWORD
```

Record operation count, final p50／p95／p99, every one-second live window and errors. Require all control errors=`0`. Before either export mode, calculate and write the numeric `OLTP_P95_BUDGET_MS = 1.50 × median(control final P95)`; once written it cannot be changed to make later trials pass.

- [ ] **Step 4: Run buffered export with concurrent OLTP three times**

For each trial:

1. choose a fresh **nonexistent** `job-buffered-N` path；
2. recheck `free >= MIN_FREE_BYTES` and the frozen source fingerprint；
3. invoke the controller with matching `--trial-id buffered-N`, the predeclared numeric P95 budget and fixed disk threshold；
4. let the controller start OLTP and launch buffered export only after five accepted fresh, advancing, nonempty same-trial windows cover at least five active seconds；
5. capture controller, OLTP, export, state, artifact and MySQL status evidence。

Example:

```bash
uv run --with mysql-connector-python==9.7.0 python \
  "$MYSQL_SCENARIO_RUN_DIR/scenario_controller.py" \
  --runner "$MYSQL_SCENARIO_RUN_DIR/export_runner.py" \
  --runtime-root "$MYSQL_SCENARIO_RUN_DIR" \
  --trial-id buffered-1 --export-mode buffered \
  --job-dir "$MYSQL_SCENARIO_RUN_DIR/job-buffered-1" \
  --duration-seconds 60 --threads 4 \
  --p95-budget-ms "$OLTP_P95_BUDGET_MS" \
  --min-free-bytes "$MIN_FREE_BYTES" \
  --host 127.0.0.1 --port "$MYSQL_SCENARIO_PORT" \
  --user root --password-env MYSQL_PASSWORD
```

On a live P95／error／disk breach, the controller writes the abort signal, reads buffered `connection_id`, issues `KILL QUERY`, terminates the process if the query does not exit within the grace period, and writes `controller-result-*.json` with external `ABORTED` evidence. An incomplete checkpoint becomes `ABORTED`; a genuinely completed internal `SUCCEEDED` state/artifact is preserved and recorded as `persisted_state_status=SUCCEEDED`, but the gate-breached controller result remains `ABORTED` and cannot become a performance sample. Stop later buffered trials and preserve both the controller evidence and checkpoint.

- [ ] **Step 5: Run chunked export with concurrent OLTP three times**

Repeat with unique `chunked-1..3` job/trial IDs, `--batch-size 1000 --sleep-ms 20`. The controller checks live window metrics/disk, and the runner independently checks disk plus abort signal **before every fetch**. On breach, the in-flight query/part may finish, but the next batch must not be issued; state becomes `ABORTED` with resumable manifest and reason.

```bash
uv run --with mysql-connector-python==9.7.0 python \
  "$MYSQL_SCENARIO_RUN_DIR/scenario_controller.py" \
  --runner "$MYSQL_SCENARIO_RUN_DIR/export_runner.py" \
  --runtime-root "$MYSQL_SCENARIO_RUN_DIR" \
  --trial-id chunked-1 --export-mode chunked \
  --job-dir "$MYSQL_SCENARIO_RUN_DIR/job-chunked-1" \
  --duration-seconds 60 --threads 4 \
  --batch-size 1000 --sleep-ms 20 \
  --p95-budget-ms "$OLTP_P95_BUDGET_MS" \
  --min-free-bytes "$MIN_FREE_BYTES" \
  --host 127.0.0.1 --port "$MYSQL_SCENARIO_PORT" \
  --user root --password-env MYSQL_PASSWORD
```

Record manifest progression, active throughput, max RSS and live abort boundary. Do not resume a gate-aborted performance trial and then rank it; diagnose the gate first.

- [ ] **Step 6: Prove interruption and idempotent resume**

Use a separate job directory:

```bash
uv run --with mysql-connector-python==9.7.0 python "$MYSQL_SCENARIO_RUN_DIR/export_runner.py" \
  --mode chunked --runtime-root "$MYSQL_SCENARIO_RUN_DIR" \
  --job-dir "$MYSQL_SCENARIO_RUN_DIR/job-resume" \
  --batch-size 1000 --sleep-ms 20 --max-batches 3 \
  --min-free-bytes "$MIN_FREE_BYTES" \
  --host 127.0.0.1 --port "$MYSQL_SCENARIO_PORT" \
  --user root --password-env MYSQL_PASSWORD

uv run --with mysql-connector-python==9.7.0 python "$MYSQL_SCENARIO_RUN_DIR/export_runner.py" \
  --mode chunked --runtime-root "$MYSQL_SCENARIO_RUN_DIR" \
  --job-dir "$MYSQL_SCENARIO_RUN_DIR/job-resume" \
  --batch-size 1000 --sleep-ms 20 --max-batches 0 \
  --min-free-bytes "$MIN_FREE_BYTES" \
  --host 127.0.0.1 --port "$MYSQL_SCENARIO_PORT" \
  --user root --password-env MYSQL_PASSWORD
```

Expected: first result=`ABORTED` after three committed parts; second validates those part hashes/cursors, resumes from saved cursor and ends `SUCCEEDED`; final bytes/SHA equal a fresh successful export with no duplicate／missing row. `active_seconds` is cumulative across both planned invocations. This is correctness evidence only, never a steady-state performance sample.

- [ ] **Step 7: Compare artifacts and correctness before latency claims**

Verify every buffered and chunked artifact has:

```text
rows = 100000
same high watermark
same canonical SHA-256
same aggregate total_amount fingerprint
no duplicate order id
last cursor = high watermark
```

First require each runner's internal state/result/artifact integrity checks. Then independently compute external file bytes/SHA, distinct keys and business aggregates and compare buffered／chunked／resumed artifacts. If hashes differ, diagnose formatting／membership／snapshot／ordering before reporting any performance comparison; a matching internal manifest alone is not cross-mode correctness.

After the last identical frozen-source fingerprint is recorded, tear down the fixed-name guards explicitly:

```sql
DROP TRIGGER IF EXISTS freeze_report_order_insert;
DROP TRIGGER IF EXISTS freeze_report_order_update;
DROP TRIGGER IF EXISTS freeze_report_order_delete;
DROP TRIGGER IF EXISTS freeze_report_item_insert;
DROP TRIGGER IF EXISTS freeze_report_item_update;
DROP TRIGGER IF EXISTS freeze_report_item_delete;
```

- [ ] **Step 8: Summarize three-run evidence and explicit limitations**

For each group report all three OLTP percentile sets, every live window, median／range and controller status; for successful fresh export modes report active time, active throughput, max RSS and status deltas. List `ABORTED` separately with trigger and stop boundary; do not include it or resume-correctness runs in steady-state median/range. Separate:

- observed S facts；
- scaled trend only；
- reasoning about mutable rows；
- reasoning about backdated/in-bound inserts and membership snapshots；
- reasoning about read replica／warehouse；
- untested production capacity。

- [ ] **Step 9: Patch status and expectation gap**

Use `apply_patch` to add environment, run IDs, frozen-source pre/post manifests, numeric disk/P95 gates, live window/controller tables, abort boundaries, successful artifact equality, interruption／resume timeline, expected-vs-actual and production boundary. Explicitly state that S used triggers plus an isolated writer set; production needs immutable insertion-monotone keys or snapshotted/materialized membership. Mark exact S behavior `SCALED_REPRODUCED`, reused ch08／ch09 mechanisms `REUSED`, and production topology conclusions `REASONED`.

Update only the report/export README row to `SCALED_REPRODUCED (S=100000)`.

- [ ] **Step 10: Validate temp prefix, cleanup, and commit**

```bash
case "$MYSQL_SCENARIO_RUN_DIR" in
  /private/tmp/mysql-senior-scenarios.?*) ;;
  *) exit 1 ;;
esac
rm -rf -- "$MYSQL_SCENARIO_RUN_DIR"

git diff --check -- mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/04-report-export-isolation.md
git add mysql-handson/13-senior-scenarios/README.md mysql-handson/13-senior-scenarios/04-report-export-isolation.md
git commit -m "docs(mysql): record report export evidence"
```

---

### Task 11: 做全 repository owner、link、evidence 與 scope 稽核

**Files:**
- Verify: `mysql-handson/README.md`
- Verify: `mysql-handson/10-sharding-and-scaling/README.md`
- Verify: `mysql-handson/12-interview-cheatsheet/README.md`
- Verify: `mysql-handson/13-senior-scenarios/README.md`
- Verify: `mysql-handson/13-senior-scenarios/01-schema-from-access-patterns.md`
- Verify: `mysql-handson/13-senior-scenarios/02-bulk-load-10m.md`
- Verify: `mysql-handson/13-senior-scenarios/03-archive-delete-reclaim.md`
- Verify: `mysql-handson/13-senior-scenarios/04-report-export-isolation.md`

**Interfaces:**
- Consumes: Task 2–10 commits and runtime evidence already summarized in Markdown。
- Produces: no broken local links／anchors, exactly one owner per 19 rows, honest evidence states, clean feature worktree and an integration-ready branch。

- [ ] **Step 1: Verify final file set and forbidden scope**

Run:

```bash
git diff --name-status main...HEAD
git diff --name-only main...HEAD | rg '^mysql-handson/(00-lab/ha|09-replication-and-ha)/|^(financial-consistency|system-design-scenarios|system-design|mysql-es-cdc-handson)/'
```

Expected: first command lists only root／ch10／ch12／ch13 implementation paths; second command has no output and exits `1`. Task 1 baseline lives on `main`, so it is not part of the feature diff.

- [ ] **Step 2: Verify owner matrix and scenario contracts**

Run:

```bash
rg -c '^\| ([1-9]|1[0-9]) \|' mysql-handson/13-senior-scenarios/README.md
for file in mysql-handson/13-senior-scenarios/0[1-4]-*.md; do
  for heading in \
    '陌生题目' \
    '先停下来回答' \
    '澄清问题' \
    '业务不变式与完成标准' \
    '跨章执行链' \
    '成本与瓶颈模型' \
    '推荐基准方案' \
    '替代方案与取舍' \
    '执行计划与停止条件' \
    '缩小规模实验与证据' \
    '生产边界、恢复与回滚' \
    '面试输出'; do
    rg -q "^## $heading$" "$file"
  done
  rg -q '30 秒' "$file"
  rg -q '3–5 分钟' "$file"
done
```

Expected: row count=`19`; all 12 contract headings and both answer lengths exist in every scenario；loop exits `0`.

- [ ] **Step 3: Run local Markdown path／anchor verifier**

Run this standard-library checker from repository root:

```bash
python3 - <<'PY'
from pathlib import Path
import re
import unicodedata

FILES = [
    Path("mysql-handson/README.md"),
    Path("mysql-handson/10-sharding-and-scaling/README.md"),
    Path("mysql-handson/12-interview-cheatsheet/README.md"),
    *sorted(Path("mysql-handson/13-senior-scenarios").glob("*.md")),
]
LINK_RE = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")

def anchor(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).strip().lower()
    text = re.sub(r"[`*_~]", "", text)
    text = re.sub(r"[^\w\-\u3400-\u9fff ]", "", text)
    return re.sub(r"[\s]+", "-", text)

errors = []
for source in FILES:
    body = source.read_text(encoding="utf-8")
    for raw in LINK_RE.findall(body):
        target = raw.split()[0]
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        path_text, _, fragment = target.partition("#")
        target_path = (source.parent / path_text).resolve() if path_text else source.resolve()
        if not target_path.exists():
            errors.append(f"{source}: missing {target}")
            continue
        if fragment and target_path.is_file():
            headings = {
                anchor(match.group(1))
                for line in target_path.read_text(encoding="utf-8").splitlines()
                if (match := re.match(r"^#{1,6}\s+(.+?)\s*$", line))
            }
            if fragment not in headings:
                errors.append(f"{source}: missing anchor {target}")
if errors:
    raise SystemExit("\n".join(errors))
print(f"PASS: {len(FILES)} Markdown files")
PY
```

Expected: `PASS` and exit `0`. Fix only actual path／fragment mistakes; do not weaken the checker to ignore failures.

- [ ] **Step 4: Verify fences, placeholders and evidence vocabulary**

Run:

```bash
for file in mysql-handson/13-senior-scenarios/*.md; do
  awk '/^```/{n++} END {if (n % 2) exit 1}' "$file"
done
! rg -n '[T]ODO|[T]BD|[F]IXME|待[补]|待[定]|假设已经通过|实测证明生产' mysql-handson/13-senior-scenarios
rg -n 'REPRODUCED|SCALED_REPRODUCED|READY_UNRUN|REASONED|REUSED' mysql-handson/13-senior-scenarios/README.md
git diff --check main...HEAD
```

Expected: all commands exit `0`; `READY_UNRUN` may remain only for a resource-gated tier with recorded evidence, never as an empty result section.

- [ ] **Step 5: Audit expectation-before-result commit order**

Run:

```bash
git log --reverse --format='%h %s' main..HEAD
```

Expected order:

```text
docs(mysql): add senior scenario routing
docs(mysql): define access-pattern schema scenario
docs(mysql): record schema design evidence
docs(mysql): define ten-million-row load scenario
docs(mysql): record bulk-load evidence
docs(mysql): define archive and reclaim scenario
docs(mysql): record archive and reclaim evidence
docs(mysql): define report export isolation scenario
docs(mysql): record report export evidence
```

Additional audit-fix commits may follow these pairs, but an evidence-recording commit may never precede its matching scenario-definition commit.

- [ ] **Step 6: Verify interview output and production boundaries by inspection**

For each scenario, read only prompt + 30-second + 3–5-minute answer and confirm the answer names constraints, execution chain, cost, correctness, baseline, alternatives, verification and recovery. Then inspect the evidence table and confirm every numeric claim identifies tier, rows, MySQL version, run count and environment.

- [ ] **Step 7: Drop only the namespaced lab schema after evidence is committed**

First prove the exact target:

```bash
docker exec mysql-primary mysql -uroot -proot -Nse "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='mysql_senior_scenarios'"
```

If and only if output is exactly `mysql_senior_scenarios`, run:

```bash
docker exec mysql-primary mysql -uroot -proot -e "DROP DATABASE mysql_senior_scenarios"
```

Do not stop the container or remove its volume. Record cleanup completion in the final handoff, not as performance evidence.

- [ ] **Step 8: Final fresh verification and audit-fix rule**

Run:

```bash
git status --short --branch
git diff --check main...HEAD
git log -1 --oneline
```

Expected: feature worktree clean; diff check exit `0`; HEAD is the last evidence or audit-fix commit.

If Steps 1–6 required Markdown fixes, stage only the exact affected docs and commit once:

```bash
git commit -m "docs(mysql): close senior scenario audit"
```

If no file changed, do not create an empty commit. Invoke `superpowers:verification-before-completion` before reporting the branch ready, then use `superpowers:finishing-a-development-branch` for the user-selected integration path.
