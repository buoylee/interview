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
- 只有 bulk load scenario 可以暫時切換本機 lab 的 `local_infile`；執行前保存原值，`finally` 恢復，不修改 durability、constraint 或 global buffer 設定。
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

```sql
USE mysql_senior_scenarios;

CREATE TABLE tenant_record_source LIKE tenant_record_baseline;
ALTER TABLE tenant_record_source
  DROP INDEX uk_tenant_request,
  DROP INDEX idx_tenant_status_created;

CREATE TEMPORARY TABLE digit (d TINYINT UNSIGNED PRIMARY KEY);
INSERT INTO digit VALUES (0),(1),(2),(3),(4),(5),(6),(7),(8),(9);

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
  FROM digit AS d0
  CROSS JOIN digit AS d1
  CROSS JOIN digit AS d2
  CROSS JOIN digit AS d3
  CROSS JOIN digit AS d4
  CROSS JOIN digit AS d5
  ORDER BY n
  LIMIT 100000
) AS seq;
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

Use this complete implementation in the embedded block:

```python
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Iterable

import mysql.connector
from mysql.connector import IntegrityError


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


def parse_row(fields: list[str]) -> tuple[int, int, int, str, str]:
    if len(fields) != 5:
        raise ValueError(f"expected 5 TSV fields, got {len(fields)}")
    row_id, tenant_id, status = map(int, fields[:3])
    payload, created_at = fields[3], fields[4]
    if row_id < 1 or tenant_id < 1 or status not in (0, 1, 2, 3):
        raise ValueError(f"invalid row values: {fields!r}")
    if "\t" in payload or "\n" in payload:
        raise ValueError("payload contains a TSV delimiter")
    return row_id, tenant_id, status, payload, created_at


def iter_rows(path: Path) -> Iterable[tuple[int, int, int, str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for line_number, fields in enumerate(reader, start=1):
            try:
                yield parse_row(fields)
            except Exception as exc:
                raise ValueError(f"line {line_number}: {exc}") from exc


def status_snapshot(cursor) -> dict[str, int]:
    quoted = ",".join(f"'{name}'" for name in STATUS_NAMES)
    cursor.execute(
        f"SHOW GLOBAL STATUS WHERE Variable_name IN ({quoted})"
    )
    values = {str(name): int(value) for name, value in cursor.fetchall()}
    return {name: values.get(name, 0) for name in STATUS_NAMES}


def load_single(connection, table: str, rows, phase: dict[str, str]) -> int:
    connection.autocommit = True
    cursor = connection.cursor()
    statement = INSERT_SQL.format(table=table)
    accepted = 0
    for row in rows:
        phase["value"] = "EXECUTING"
        cursor.execute(statement, row)
        accepted += 1
        phase["value"] = "BEFORE_SEND"
    cursor.close()
    return accepted


def load_batches(
    connection,
    table: str,
    rows,
    batch_size: int,
    phase: dict[str, str],
) -> int:
    connection.autocommit = False
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
    cursor.close()
    return accepted


def load_local_file(
    connection,
    table: str,
    path: Path,
    phase: dict[str, str],
) -> int:
    if "'" in str(path):
        raise ValueError("input path may not contain a single quote")
    connection.autocommit = False
    cursor = connection.cursor()
    phase["value"] = "EXECUTING"
    cursor.execute(
        "LOAD DATA LOCAL INFILE "
        f"'{path.as_posix()}' INTO TABLE `{table}` "
        "FIELDS TERMINATED BY '\\t' LINES TERMINATED BY '\\n' "
        "(id,tenant_id,status,payload,created_at)"
    )
    phase["value"] = "COMMITTING"
    connection.commit()
    accepted = cursor.rowcount
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


def classify(exc: Exception, phase: str) -> str:
    if phase == "BEFORE_SEND" or isinstance(exc, (ValueError, IntegrityError)):
        return "FAILED"
    return "UNKNOWN"


def restore_local_infile(config: dict, original: int) -> None:
    admin = mysql.connector.connect(**config, allow_local_infile=True)
    cursor = admin.cursor()
    cursor.execute(f"SET GLOBAL local_infile={int(original)}")
    cursor.close()
    admin.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=sorted(ALLOWED_TABLES), required=True)
    parser.add_argument("--table", choices=sorted(ALLOWED_TABLES.values()), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    expected_table = ALLOWED_TABLES[args.mode]
    input_path = args.input.resolve()
    if args.table != expected_table:
        raise SystemExit(f"mode {args.mode} requires table {expected_table}")
    if not input_path.is_file() or not input_path.is_absolute():
        raise SystemExit("--input must be an existing absolute file")
    if not 1 <= args.batch_size <= 5000:
        raise SystemExit("--batch-size must be in 1..5000")

    config = {
        "host": args.host,
        "port": args.port,
        "user": args.user,
        "password": args.password,
        "database": "mysql_senior_scenarios",
    }
    connection = None
    original_local_infile = None
    changed_local_infile = False
    phase = {"value": "BEFORE_SEND"}
    started = time.perf_counter()
    try:
        connection = mysql.connector.connect(
            **config,
            allow_local_infile=True,
        )
        cursor = connection.cursor()
        if args.mode == "load":
            cursor.execute("SELECT @@GLOBAL.local_infile")
            original_local_infile = int(cursor.fetchone()[0])
            if original_local_infile == 0:
                cursor.execute("SET GLOBAL local_infile=1")
                changed_local_infile = True
        phase["value"] = "EXECUTING"
        cursor.execute(f"TRUNCATE TABLE `{args.table}`")
        phase["value"] = "BEFORE_SEND"
        before = status_snapshot(cursor)
        cursor.close()

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
            accepted = load_local_file(
                connection, args.table, input_path, phase
            )

        cursor = connection.cursor()
        after = status_snapshot(cursor)
        result_fingerprint = fingerprint(cursor, args.table)
        cursor.close()
        seconds = time.perf_counter() - started
        phase["value"] = "VERIFIED"
        result = {
            "status": "SUCCEEDED",
            "phase": phase["value"],
            "mode": args.mode,
            "table": args.table,
            "rows": accepted,
            "seconds": seconds,
            "rows_per_second": accepted / seconds,
            "status_delta": {
                name: after[name] - before[name] for name in STATUS_NAMES
            },
            "fingerprint": result_fingerprint,
        }
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        status = classify(exc, phase["value"])
        if connection is not None and connection.is_connected():
            try:
                connection.rollback()
            except Exception:
                pass
        print(
            json.dumps(
                {
                    "status": status,
                    "phase": phase["value"],
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    finally:
        if changed_local_infile and original_local_infile is not None:
            restore_local_infile(config, original_local_infile)
        if connection is not None and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
```

Required safety behavior:

- table name is checked against a three-name allowlist before interpolation；
- input path is absolute and exists；
- `single` truncates only `bulk_single`, `batch` only `bulk_batch`, `load` only `bulk_load`；
- batch size must be `1..5000`；
- load mode connects with `allow_local_infile=True`, saves `@@GLOBAL.local_infile`, enables it only if needed, and restores it in `finally`；
- track phase as `BEFORE_SEND`、`EXECUTING`、`COMMITTING` or `VERIFIED`；an error before send is `FAILED`, a server error that proves rollback is `FAILED`, and a lost connection／timeout during execute or commit is `UNKNOWN`；never auto-retry `UNKNOWN`；
- on any exception, rollback only when the connection is still usable, print JSON with phase and `status="FAILED"` or `status="UNKNOWN"`, then exit nonzero；
- successful JSON includes mode, table, rows, seconds, rows_per_second, status deltas and fingerprint；
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

CREATE TEMPORARY TABLE digit (d TINYINT UNSIGNED PRIMARY KEY);
INSERT INTO digit VALUES (0),(1),(2),(3),(4),(5),(6),(7),(8),(9);

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
  FROM digit AS d0
  CROSS JOIN digit AS d1
  CROSS JOIN digit AS d2
  CROSS JOIN digit AS d3
  CROSS JOIN digit AS d4
  CROSS JOIN digit AS d5
  ORDER BY n
  LIMIT 100000
) AS seq;

INSERT INTO archive_big_delete SELECT * FROM archive_source;
INSERT INTO archive_batch_delete SELECT * FROM archive_source;
INSERT INTO archive_partitioned
SELECT * FROM archive_source
WHERE NOT (created_at < '2026-04-01 00:00:00' AND legal_hold = TRUE);
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

State the hard boundary: `(created_at,id)` high watermark excludes later inserts, but cannot freeze updates／deletes to rows already inside the boundary. Mutable as-of correctness requires versioned history, a database／replica snapshot, CDC-built versioned read model, analytical snapshot, or a deliberately bounded MVCC snapshot with its undo／purge cost.

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

Seed `100000` orders, exactly three items per order and `10000` probe rows. Export order is immutable `(created_at ASC,id ASC)`; high watermark is the maximum tuple captured at job creation.

Use this complete six-digit seed mapping:

```sql
CREATE TEMPORARY TABLE digit (d TINYINT UNSIGNED PRIMARY KEY);
INSERT INTO digit VALUES (0),(1),(2),(3),(4),(5),(6),(7),(8),(9);

INSERT INTO report_order (id, tenant_id, status, created_at)
SELECT n,
       MOD(n, 1000) + 1,
       MOD(n, 4),
       TIMESTAMPADD(SECOND, n, '2026-01-01 00:00:00')
FROM (
  SELECT 1 + d0.d + 10*d1.d + 100*d2.d + 1000*d3.d
           + 10000*d4.d + 100000*d5.d AS n
  FROM digit AS d0
  CROSS JOIN digit AS d1
  CROSS JOIN digit AS d2
  CROSS JOIN digit AS d3
  CROSS JOIN digit AS d4
  CROSS JOIN digit AS d5
  ORDER BY n
  LIMIT 100000
) AS seq;

INSERT INTO report_item (id, order_id, qty, unit_price)
SELECT o.id * 10 + d.d,
       o.id,
       d.d,
       (MOD(o.id * d.d, 100000) + 1) / 100
FROM report_order AS o
JOIN digit AS d ON d.d IN (1,2,3);

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
  "high_created_at": "2026-01-02 03:46:40.000000",
  "high_id": 100000,
  "last_created_at": "1970-01-01 00:00:00.000000",
  "last_id": 0,
  "next_part": 1,
  "rows_written": 0,
  "status": "RUNNING"
}
```

Artifact invariants:

- each part is produced as `.tmp`, flushed／fsynced and atomically renamed；
- checkpoint advances only after the part rename；
- a process interruption after part rename but before checkpoint rewrites the same deterministic part number on resume, so it cannot duplicate output；this lab does not claim power-loss durability for a parent directory that was not fsynced；
- final publish concatenates ordered parts into `artifact.tsv.tmp`, verifies row count and SHA-256, then `os.replace()` publishes `artifact.tsv`；
- `ABORTED` keeps state and parts; `SUCCEEDED` requires final artifact plus result manifest；
- readers never consume `.tmp` or partial parts as a complete report。

- [ ] **Step 5: Embed exact runner interfaces**

The document contains one copyable `$MYSQL_SCENARIO_RUN_DIR/export_runner.py` block with CLI modes:

```text
--mode buffered|chunked|oltp
--job-dir /private/tmp/mysql-senior-scenarios.<suffix>/job-<run-id>
--batch-size 1000
--sleep-ms 20
--max-batches 0
--duration-seconds 60
--threads 4
--host 127.0.0.1 --port 3306 --user root --password root
```

Use a complete implementation with these exact functions and types. The code below is the required behavior; the scenario may improve comments, but not change state fields, query order or safety gates:

```python
def capture_high_watermark(cursor) -> tuple[str, int]:
    """Run ORDER BY created_at DESC,id DESC LIMIT 1 and return that tuple."""

def atomic_json(path: Path, value: dict) -> None:
    """Write, flush, fsync and os.replace a JSON document."""

def fetch_batch(cursor, low: tuple[str, int], high: tuple[str, int], limit: int) -> list[tuple]:
    """Execute the fixed keyset JOIN query and return at most limit rows."""

def write_part(path: Path, rows: list[tuple]) -> tuple[int, str]:
    """Atomically write canonical TSV and return row count plus SHA-256."""

def run_chunked(connection, job_dir: Path, batch_size: int, sleep_ms: int, max_batches: int) -> dict:
    """Create or resume state, write deterministic parts and atomically publish on completion."""

def run_buffered(connection, job_dir: Path) -> dict:
    """Use one buffered full-boundary query, fetch all rows, write one artifact and report max RSS."""

def run_oltp(config: dict, duration: int, threads: int) -> dict:
    """Run random point SELECT plus autocommit UPDATE on oltp_probe and report count,p50,p95,p99,error count."""
```

```python
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import random
import resource
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import mysql.connector


EPOCH = "1970-01-01 00:00:00.000000"
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


def timestamp_text(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S.%f")
    return str(value)


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


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


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


def max_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def publish(job_dir: Path, expected_rows: int) -> tuple[int, str]:
    artifact = job_dir / "artifact.tsv"
    temporary = job_dir / "artifact.tsv.tmp"
    digest = hashlib.sha256()
    rows = 0
    with temporary.open("wb") as output:
        for part in sorted((job_dir / "parts").glob("part-*.tsv")):
            with part.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(chunk)
                    digest.update(chunk)
                    rows += chunk.count(b"\n")
        output.flush()
        os.fsync(output.fileno())
    if rows != expected_rows:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"artifact rows {rows} != checkpoint rows {expected_rows}")
    os.replace(temporary, artifact)
    return rows, digest.hexdigest()


def run_chunked(
    connection,
    job_dir: Path,
    batch_size: int,
    sleep_ms: int,
    max_batches: int,
) -> dict:
    state_path = job_dir / "state.json"
    result_path = job_dir / "result.json"
    cursor = connection.cursor()
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state["status"] == "SUCCEEDED":
            return json.loads(result_path.read_text(encoding="utf-8"))
        state["status"] = "RUNNING"
    else:
        high_created_at, high_id = capture_high_watermark(cursor)
        state = {
            "job_id": job_dir.name,
            "high_created_at": high_created_at,
            "high_id": high_id,
            "last_created_at": EPOCH,
            "last_id": 0,
            "next_part": 1,
            "rows_written": 0,
            "status": "RUNNING",
        }
    atomic_json(state_path, state)
    started = time.perf_counter()
    batches_this_run = 0
    while True:
        rows = fetch_batch(
            cursor,
            (state["last_created_at"], int(state["last_id"])),
            (state["high_created_at"], int(state["high_id"])),
            batch_size,
        )
        if not rows:
            artifact_rows, artifact_sha256 = publish(
                job_dir, int(state["rows_written"])
            )
            elapsed = time.perf_counter() - started
            result = {
                "status": "SUCCEEDED",
                "mode": "chunked",
                "rows": artifact_rows,
                "sha256": artifact_sha256,
                "seconds": elapsed,
                "rows_per_second": artifact_rows / elapsed,
                "max_rss_bytes": max_rss_bytes(),
                "high_cursor": [state["high_created_at"], state["high_id"]],
                "last_cursor": [state["last_created_at"], state["last_id"]],
                "parts": int(state["next_part"]) - 1,
            }
            atomic_json(result_path, result)
            state["status"] = "SUCCEEDED"
            atomic_json(state_path, state)
            cursor.close()
            return result

        part_number = int(state["next_part"])
        part_path = job_dir / "parts" / f"part-{part_number:06d}.tsv"
        part_rows, _ = write_part(part_path, rows)
        last = rows[-1]
        state["last_created_at"] = timestamp_text(last[0])
        state["last_id"] = int(last[1])
        state["next_part"] = part_number + 1
        state["rows_written"] = int(state["rows_written"]) + part_rows
        atomic_json(state_path, state)
        batches_this_run += 1
        if max_batches and batches_this_run >= max_batches:
            state["status"] = "ABORTED"
            atomic_json(state_path, state)
            elapsed = time.perf_counter() - started
            result = {
                "status": "ABORTED",
                "mode": "chunked",
                "rows": state["rows_written"],
                "seconds": elapsed,
                "rows_per_second": state["rows_written"] / elapsed,
                "max_rss_bytes": max_rss_bytes(),
                "high_cursor": [state["high_created_at"], state["high_id"]],
                "last_cursor": [state["last_created_at"], state["last_id"]],
                "parts": int(state["next_part"]) - 1,
            }
            cursor.close()
            return result
        if sleep_ms:
            time.sleep(sleep_ms / 1000)


def run_buffered(connection, job_dir: Path) -> dict:
    job_dir.mkdir(parents=True, exist_ok=False)
    cursor = connection.cursor(buffered=True)
    high = capture_high_watermark(cursor)
    started = time.perf_counter()
    cursor.execute(BUFFERED_SQL, (EPOCH, 0, *high))
    rows = list(cursor.fetchall())
    artifact_rows, artifact_sha256 = write_part(
        job_dir / "artifact.tsv", rows
    )
    cursor.close()
    elapsed = time.perf_counter() - started
    result = {
        "status": "SUCCEEDED",
        "mode": "buffered",
        "rows": artifact_rows,
        "sha256": artifact_sha256,
        "seconds": elapsed,
        "rows_per_second": artifact_rows / elapsed,
        "max_rss_bytes": max_rss_bytes(),
        "high_cursor": [high[0], high[1]],
        "last_cursor": [timestamp_text(rows[-1][0]), int(rows[-1][1])],
    }
    atomic_json(job_dir / "result.json", result)
    atomic_json(job_dir / "state.json", {
        "job_id": job_dir.name,
        "high_created_at": high[0],
        "high_id": high[1],
        "last_created_at": result["last_cursor"][0],
        "last_id": result["last_cursor"][1],
        "next_part": 1,
        "rows_written": artifact_rows,
        "status": "SUCCEEDED",
    })
    return result


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def oltp_worker(config: dict, duration: int, seed: int) -> tuple[list[float], int]:
    connection = mysql.connector.connect(**config)
    connection.autocommit = True
    cursor = connection.cursor()
    randomizer = random.Random(seed)
    deadline = time.perf_counter() + duration
    latencies: list[float] = []
    errors = 0
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
            latencies.append((time.perf_counter_ns() - started) / 1_000_000)
        except Exception:
            errors += 1
    cursor.close()
    connection.close()
    return latencies, errors


def run_oltp(config: dict, duration: int, threads: int) -> dict:
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as pool:
        results = list(
            pool.map(
                lambda seed: oltp_worker(config, duration, seed),
                range(1, threads + 1),
            )
        )
    latencies = [value for values, _ in results for value in values]
    errors = sum(error_count for _, error_count in results)
    return {
        "status": "SUCCEEDED" if errors == 0 else "FAILED",
        "mode": "oltp",
        "operations": len(latencies),
        "errors": errors,
        "p50_ms": percentile(latencies, 0.50),
        "p95_ms": percentile(latencies, 0.95),
        "p99_ms": percentile(latencies, 0.99),
    }


def validated_job_dir(path: Path) -> Path:
    resolved = path.resolve()
    private_tmp = Path("/private/tmp").resolve()
    runtime_root = resolved.parent
    if (
        runtime_root.parent != private_tmp
        or not runtime_root.name.startswith("mysql-senior-scenarios.")
        or not resolved.name.startswith("job-")
    ):
        raise ValueError("job directory is outside the allowed runtime prefix")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("buffered", "chunked", "oltp"), required=True)
    parser.add_argument("--job-dir", type=Path)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--sleep-ms", type=int, default=20)
    parser.add_argument("--max-batches", type=int, default=0)
    parser.add_argument("--duration-seconds", type=int, default=60)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    if not 1 <= args.batch_size <= 5000:
        raise SystemExit("--batch-size must be in 1..5000")
    if not 0 <= args.sleep_ms <= 1000:
        raise SystemExit("--sleep-ms must be in 0..1000")
    if not 1 <= args.threads <= 16:
        raise SystemExit("--threads must be in 1..16")
    if args.duration_seconds < 1 or args.max_batches < 0:
        raise SystemExit("duration must be positive and max-batches nonnegative")

    config = {
        "host": args.host,
        "port": args.port,
        "user": args.user,
        "password": args.password,
        "database": "mysql_senior_scenarios",
    }
    try:
        if args.mode == "oltp":
            result = run_oltp(config, args.duration_seconds, args.threads)
        else:
            if args.job_dir is None:
                raise ValueError("--job-dir is required for export modes")
            job_dir = validated_job_dir(args.job_dir)
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
                )
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

- `job_dir.resolve()` must be an immediate `job-*` child of an immediate `/private/tmp/mysql-senior-scenarios.*` runtime directory；
- batch size `1..5000`, sleep `0..1000`, threads `1..16`；
- parameterized SQL for all data values；
- buffered and chunked artifacts use identical column order and canonical formatting；
- runner JSON reports rows, SHA-256, seconds, throughput, max RSS, high／last cursors and status；
- no user password appears in committed result snippets；
- interrupted chunked run is invoked with `--max-batches 3`, returns `ABORTED` with timing／cursor metrics, then the same job directory resumes with `--max-batches 0`；this proves process-level resume behavior, not host power-loss durability。

- [ ] **Step 6: Define performance matrix and stop conditions**

Run groups, each three times with a fresh job directory:

| Group | OLTP probe | Export |
|---|---|---|
| control | 60 s, 4 threads | none |
| buffered | 60 s, 4 threads | one buffered query／artifact |
| chunked | 60 s, 4 threads | batch=1000, sleep=20 ms |

Start OLTP five seconds before export. Record OLTP p50／p95／p99／errors, export elapsed／rows-per-second／max RSS, MySQL processlist／temporary-table／sort deltas and exact artifact correctness. Stop new batches if OLTP P95 exceeds the pre-run budget, disk reserve is breached, MySQL restarts, errors appear or output fingerprint diverges.

Pre-run hypotheses:

- buffered control should hold one connection and more client memory；
- chunking／sleep should reduce burst pressure and provide checkpoints, at the cost of longer completion；
- exact latency differences are unknown；
- a read replica can isolate some CPU／I/O but introduces lag, snapshot and capacity tradeoffs；
- a long MVCC transaction is not a free snapshot solution。

Mark S test `READY_UNRUN`, canonical mechanism links `REUSED`, production topology choices `REASONED`.

- [ ] **Step 7: Verify official claims and write answer forms**

Use official MySQL 8.0 documentation for consistent nonlocking reads／ReadView, long transaction effects, cursor／result fetching, temporary tables and replica lag boundaries; use official Connector/Python docs for buffered vs nonbuffered cursors. Cite primary sources.

The 30-second answer must choose async job + fixed boundary + keyset chunks + bounded buffer + checkpoint + atomic artifact, then name OLTP／correctness gates. The 3–5-minute answer must distinguish membership boundary from value snapshot, explain tier placement, backpressure, resume ambiguity, validation, replica／warehouse alternatives and rollback／rebuild.

- [ ] **Step 8: Link route, verify, and commit expectation**

Update README to link `[大型报表与导出隔离](04-report-export-isolation.md)` with `READY_UNRUN`.

Run:

```bash
rg -n 'READY_UNRUN|high watermark|更新|删除|run_chunked|run_buffered|run_oltp|ABORTED|artifact.tsv|30 秒|3–5 分钟' mysql-handson/13-senior-scenarios/04-report-export-isolation.md
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
- Consumes: Task 9 fixed schema, query, runner, performance matrix and immutable S dataset。
- Produces: control／buffered／chunked OLTP comparison, identical artifacts, interrupted-resume proof and bounded claims。

- [ ] **Step 1: Preflight and materialize runner in validated temp path**

Repeat base-lab ownership／health, MySQL version／durability, free disk and host resource checks. Create the runtime directory with `MYSQL_SCENARIO_RUN_DIR=$(mktemp -d /private/tmp/mysql-senior-scenarios.XXXXXX)`, copy the committed code block to `$MYSQL_SCENARIO_RUN_DIR/export_runner.py`, and run:

```bash
uv run --with mysql-connector-python==9.7.0 python -m py_compile "$MYSQL_SCENARIO_RUN_DIR/export_runner.py"
```

Expected: syntax exit `0`; no global MySQL variable changes.

- [ ] **Step 2: Seed and verify the S dataset**

Create exactly 100,000 orders, 300,000 items and 10,000 probe rows. Run `ANALYZE TABLE`. Verify counts, order min／max tuple, three items per order and aggregate fingerprint before performance runs.

- [ ] **Step 3: Establish the OLTP-only control three times**

Run `--mode oltp --duration-seconds 60 --threads 4` three times without export. Record operation count, p50／p95／p99 and errors. Before either export mode, set the exact stop budget to `1.50 × median(control P95)` and require `errors=0`; write that numeric budget before those runs.

- [ ] **Step 4: Run buffered export with concurrent OLTP three times**

For each trial:

1. create a fresh job directory；
2. start OLTP mode and wait five seconds；
3. run buffered mode against the fixed high watermark；
4. wait for OLTP completion；
5. capture both JSON outputs, MySQL status deltas and artifact manifest。

Stop later buffered trials if the predeclared P95 or correctness gate fails; preserve the failed output.

- [ ] **Step 5: Run chunked export with concurrent OLTP three times**

Repeat the same structure with `--batch-size 1000 --sleep-ms 20 --max-batches 0`. Record part count, checkpoint progression, throughput, max RSS and final artifact manifest.

- [ ] **Step 6: Prove interruption and idempotent resume**

Use a separate job directory:

```bash
uv run --with mysql-connector-python==9.7.0 python "$MYSQL_SCENARIO_RUN_DIR/export_runner.py" \
  --mode chunked --job-dir "$MYSQL_SCENARIO_RUN_DIR/job-resume" \
  --batch-size 1000 --sleep-ms 20 --max-batches 3 \
  --host 127.0.0.1 --port 3306 --user root --password root

uv run --with mysql-connector-python==9.7.0 python "$MYSQL_SCENARIO_RUN_DIR/export_runner.py" \
  --mode chunked --job-dir "$MYSQL_SCENARIO_RUN_DIR/job-resume" \
  --batch-size 1000 --sleep-ms 20 --max-batches 0 \
  --host 127.0.0.1 --port 3306 --user root --password root
```

Expected: first result=`ABORTED` after three committed parts; second resumes from saved cursor and ends `SUCCEEDED`; final output has no duplicate／missing row.

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

If hashes differ, diagnose formatting／snapshot／ordering before reporting any performance comparison.

- [ ] **Step 8: Summarize three-run evidence and explicit limitations**

For each group report all three OLTP percentile sets and median／range; for export modes report elapsed, throughput, max RSS and status deltas. Separate:

- observed S facts；
- scaled trend only；
- reasoning about mutable rows；
- reasoning about read replica／warehouse；
- untested production capacity。

- [ ] **Step 9: Patch status and expectation gap**

Use `apply_patch` to add environment, run IDs, source manifest, run tables, stop budget, artifact equality, interruption／resume timeline, expected-vs-actual and production boundary. Mark exact S behavior `SCALED_REPRODUCED`, reused ch08／ch09 mechanisms `REUSED`, and production topology conclusions `REASONED`.

Update only the report/export README row to `SCALED_REPRODUCED (S=100000)`.

- [ ] **Step 10: Validate temp prefix, cleanup, and commit**

```bash
case "$MYSQL_SCENARIO_RUN_DIR" in
  /private/tmp/mysql-senior-scenarios.*) ;;
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
