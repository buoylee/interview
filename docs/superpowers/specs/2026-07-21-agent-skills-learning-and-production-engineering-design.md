# Agent Skills Learning and Production Engineering Design

## 1. Goal

將兩個本地 Agent Skills 倉庫整理成一條可按順序閱讀、可回到原始來源驗證、最後能落成專案工程規範的學習路徑：

- `obra/superpowers`
- `mattpocock/skills`

這不只是一份功能比較報告。完成後，讀者應能回答四類問題：

1. 兩個庫各自相信什麼，又如何把信念落成 workflow？
2. 核心 skills 分別解決哪種 Agent failure mode，彼此如何銜接？
3. 為什麼遵循這些 skills，仍可能產出不夠 production-ready 的程式碼？
4. 如何在不直接魔改上游的前提下，加入自己的 Production Engineering Profile、Project Overlay 與 AI Code Review gate？

## 2. Audience and Success Boundary

主要讀者是已經使用 Coding Agent、希望建立穩定工程流程的後端工程師或技術負責人。讀者不需要先熟悉 Agent Skills 規範，但應理解一般軟體開發流程、Git、測試和 code review。

完成整條路徑後，讀者應能：

- 畫出兩個庫的主流程，而不是只記得一串 skill 名稱。
- 選出適合當前任務的 skill，說清它的輸入、輸出、gate 和停止條件。
- 區分 workflow discipline、project policy、domain invariants 與 executable evidence。
- 解釋 AI reviewer 的 context isolation、confirmation bias、review packet 與 finding contract。
- 將 Core Profile 和 Project Overlay 接到 brainstorm、spec、plan、implementation、review、verification 與 merge gate。
- 用可執行 fixtures 比較不同 AI Code Review 策略，而不是只憑主觀感覺評價。

## 3. Source Snapshots

所有來源分析以本地快照為準，不以記憶、舊報告或浮動的 GitHub `main` 為準。

| Library | Local path | Commit / tag |
|---|---|---|
| Matt Pocock Skills | `/Users/buoy/Development/gitrepo/skills` | `ed37663cc5fbef691ddfecd080dff42f7e7e350d` (`v1.1.0-40-ged37663`) |
| Superpowers | `/Users/buoy/Development/gitrepo/superpowers` | `f2cbfbefebbfef77321e4c9abc9e949826bea9d7` (`v5.1.0`) |

每個來源分析頁都要在頁首記錄：

- library 名稱；
- local path；
- commit 或 tag；
- verified date；
- 主要 source files。

數量、支援平台、觸發模式或 skill 狀態等容易漂移的事實，必須標示為 snapshot fact。設計哲學或流程判斷也要連回原始 `README.md`、`SKILL.md` 或相應 reference，而不是引用舊比較報告。

## 4. Core Decision

採用一個 umbrella learning track：

```text
ai/coding-agent/agent-skills/
```

它同時容納三種彼此有明確邊界的內容：

- **Descriptive learning docs**：忠實解釋上游庫。
- **Comparative analysis**：比較兩庫的流程、責任與 trade-off。
- **Normative project artifacts**：定義我們自己的 AI Code Review Protocol、Core Profile 與 Project Overlay。

上游內容與自訂規範不得混寫成同一個「作者主張」。凡是本專案新增的要求，都要明確標為 derived design 或 local policy。

## 5. Information Architecture

```text
ai/coding-agent/agent-skills/
├── README.md
├── 00-agent-skills-mental-model.md
├── 01-two-libraries-workflow-map.md
│
├── 02-superpowers/
│   ├── README.md
│   ├── 01-methodology-and-lifecycle.md
│   ├── 02-all-skills-guide.md
│   └── 03-strengths-and-boundaries.md
│
├── 03-matt-pocock/
│   ├── README.md
│   ├── 01-main-flow.md
│   ├── 02-core-skills-guide.md
│   └── 03-quality-foundations-and-boundaries.md
│
├── 04-comparison-and-composition.md
│
├── 05-ai-code-review/
│   ├── README.md
│   ├── 01-mental-model.md
│   ├── 02-two-library-mechanisms.md
│   ├── 03-production-review-protocol.md
│   ├── 04-evaluation-and-lab.md
│   └── lab/
│       ├── README.md
│       ├── fixtures/
│       │   ├── 01-data-consistency/
│       │   ├── 02-idempotency/
│       │   ├── 03-timeout-retry-fallback/
│       │   ├── 04-interface-coupling/
│       │   ├── 05-error-handling/
│       │   └── 06-misleading-tests/
│       ├── answer-key/
│       ├── results-template.md
│       └── run-fixtures.py
│
├── 06-production-profile/
│   ├── README.md
│   ├── 01-production-quality-model.md
│   ├── 02-core-profile.md
│   ├── 03-project-overlay-template.md
│   └── 04-integrating-with-skills.md
│
├── 07-adoption-playbook.md
└── _archive/
    └── legacy-three-library-report/
```

`ai/README.md` 要增加正式入口，將這條路徑放在 Coding Agent 學習材料下。主 `README.md` 只在現有導航慣例需要時更新，不為了本專題額外擴大範圍。

## 6. Reading Flow

```text
Agent Skill mental model
  -> two workflow maps
  -> Superpowers methodology and all skills
  -> Matt Pocock main flow and selected core skills
  -> comparison and composition
  -> AI Code Review as an engineering system
  -> why workflow discipline is not production policy
  -> Core Profile plus Project Overlay
  -> adoption and evolution playbook
```

`README.md` 必須同時提供：

- 線性閱讀順序；
- 按任務跳讀入口，例如 feature、bug、review、architecture、production hardening；
- descriptive docs 與 normative artifacts 的醒目區分。

正文使用繁體中文，skill name、frontmatter field、command、artifact name 和精確技術術語保留英文。寫法採 boundary-first：先給結論、流程或 invariant，再解釋機制、證據和限制。必要時使用 Mermaid 呈現 workflow、sequence 或 state transition，但不為裝飾增加圖。原文只取支撐判斷所需的短引文，其餘以中文重新組織。

## 7. Foundation Chapters

### 7.1 Agent Skills Mental Model

`00-agent-skills-mental-model.md` 先建立分層模型：

```text
Harness and invocation
  -> Skill workflow
  -> Project policy
  -> Domain invariants
  -> Tools and evidence
  -> Delivery gate
```

它要解釋 `SKILL.md`、frontmatter、user-invoked、model-invoked、trigger、hard gate、reference、artifact 與 skill composition，並特別說明：skill 是行為與流程封裝，不等於完整的 production requirements。

### 7.2 Two-Library Workflow Map

`01-two-libraries-workflow-map.md` 先各用一張主流程圖建立全景，再說明哪些能力是主線、分支、底層 vocabulary 或 meta skill。讀者在進入 skill 細節前，必須先知道每個 skill 位於哪一個 decision point。

## 8. Superpowers Coverage

Superpowers 的 14 個 skills 全部深入解釋，但按 lifecycle 而非字母排序：

1. `using-superpowers`
2. `brainstorming`
3. `using-git-worktrees`
4. `writing-plans`
5. `subagent-driven-development`
6. `executing-plans`
7. `dispatching-parallel-agents`
8. `test-driven-development`
9. `systematic-debugging`
10. `requesting-code-review`
11. `receiving-code-review`
12. `verification-before-completion`
13. `finishing-a-development-branch`
14. `writing-skills`

主流程要明確表達：

```text
using-superpowers
  -> brainstorming
  -> isolated workspace
  -> writing-plans
  -> execution strategy
  -> TDD / debugging
  -> review and feedback handling
  -> verification
  -> branch completion
```

`dispatching-parallel-agents` 和 `systematic-debugging` 是條件式分支；`writing-skills` 是 meta capability，不能硬塞成每次 feature 都會經過的線性步驟。

## 9. Matt Pocock Coverage

不逐一深挖本地庫中的 41 個 skills。詳細範圍按「8 個核心 + 2 個品質基礎 + 2 個條件式能力」固定。

### 9.1 Core Workflow

1. `grill-with-docs`
2. `to-spec`
3. `to-tickets`
4. `implement`
5. `tdd`
6. `code-review`
7. `diagnosing-bugs`
8. `handoff`

主流程：

```text
grill-with-docs
  -> to-spec
  -> to-tickets
  -> implement
       -> tdd
       -> code-review
```

`diagnosing-bugs` 是 bug on-ramp；`handoff` 是跨 context/session 的橋。

### 9.2 Quality Foundations

9. `domain-modeling`
10. `codebase-design`

這兩個 skill 雖不一定由使用者頻繁直接呼叫，卻直接回答本專題關心的 domain invariants、interface、seam、deep module、解耦與 testability。

### 9.3 Conditional Capabilities

11. `prototype`
12. `improve-codebase-architecture`

### 9.4 Index-Only Coverage

`setup-matt-pocock-skills` 與 `ask-matt` 在入口章說明其 prerequisite/router 角色。其餘 skills 只列出：

- name；
- maturity bucket；
- one-line purpose；
- 為何不在本次深挖主線。

「常用」是依作者自己定義的 main flow、一般 feature/debug/review 任務的復用性，以及本專題的生產品質目標選出，不宣稱是使用遙測或下載排名。

## 10. Skill Explanation Contract

每個重點 skill 使用同一模板：

1. **Failure mode**：它因哪種 Agent 或工程失敗而出現？
2. **Trigger and preconditions**：何時進入，必須先具備什麼？
3. **Inputs**：需要哪些 conversation、repo、spec、issue 或 fixed point？
4. **Outputs**：產出文件、程式碼、review finding、commit 還是決策？
5. **Internal flow**：步驟、分支、hard gate 與停止條件。
6. **Composition**：它依賴誰，完成後流向誰？
7. **Guarantees**：遵循流程後真正增加了哪些保證？
8. **Non-guarantees**：哪些結果仍不能聲稱？
9. **When not to use**：不適用或成本過高的場景。
10. **Production gap**：要達到 production-ready 還缺哪些 project facts 或 evidence？
11. **Source anchors**：本地原始文件與 snapshot commit。

章節不逐段翻譯 `SKILL.md`。它要先還原 invariant 和 control flow，再用必要的短引文作證據。

## 11. Comparison and Composition

`04-comparison-and-composition.md` 沿以下軸線比較：

- complete methodology 與 composable toolset；
- user control 與 automatic progression；
- invocation policy 與 trigger 強度；
- artifact flow；
- context hygiene 與 subagent isolation；
- TDD、debugging、review、verification 的責任邊界；
- domain language 與 codebase design；
- customization model；
- production quality coverage 與缺口；
- 成本、摩擦與適用任務規模。

最後給出 composition 建議，但不創造一條把兩庫所有 gate 疊加的巨型流程。推薦組合必須以最小充分流程為準，並清楚指出衝突時哪一套規則優先。

## 12. AI Code Review Topic

### 12.1 Mental Model

AI Code Review 被定義為 evidence-backed decision system，而不是「讓另一個模型看一下程式碼」。完整閉環：

```text
Preflight
  -> deterministic checks
  -> independent review axes
  -> finding verification
  -> aggregation without masking
  -> fix
  -> re-review
  -> go / no-go
```

### 12.2 Review Packet

進入 review 前必須固定：

- fixed point、merge-base、commit list 與完整 diff；
- originating spec、issue 與 acceptance criteria；
- repo standards、ADR、Core Profile 與 Project Overlay；
- tests、typecheck、lint、build、security scan 等實際輸出；
- 變更涉及的資料、接口和風險邊界。

缺少 spec 時不得聲稱完成 Spec Compliance；缺少 business invariants 時不得聲稱證明了 data consistency。

### 12.3 Deterministic Checks First

compiler、tests、linters、static analysis 和可重複執行的 checks 先跑。AI reviewer 專注語義、跨檔關係、隱含不變量與設計 trade-off，不重做工具更擅長的工作。

### 12.4 Independent Review Axes

固定四軸：

1. Spec Compliance
2. Correctness and Domain Invariants
3. Architecture and Maintainability
4. Test Quality

Project Overlay 按風險增加：

- Security
- Reliability and Fallback
- Performance and Capacity
- Observability and Operability
- Data Migration and Compatibility

實作者不能批准自己的變更。Reviewer 使用 fresh context，只接收明確的 review packet。不同軸的報告可以去重，但不能用總分掩蓋某軸的 Critical finding。

### 12.5 Finding Contract

每條 finding 必須包含：

| Field | Meaning |
|---|---|
| `id` | 穩定識別碼，用於 fix 和 re-review |
| `lens` | 所屬審查軸 |
| `severity` | 依實際 impact 分級，不依語氣 |
| `confidence` | reviewer 對判斷的信心 |
| `location` | `file:line` 或明確 artifact 位置 |
| `rule` | 違反的 spec、profile、overlay 或明文標準 |
| `impact` | 可觀察的失敗或風險 |
| `evidence` | 程式碼、資料流、命令輸出或反例 |
| `direction` | 修復方向，不強迫唯一實作 |
| `verification` | 如何證明已修復 |
| `status` | open、disputed、accepted-risk、fixed、verified |

沒有足夠證據的猜測只能標記為待驗證，不能直接成為 blocking finding。

### 12.6 Synthesis from Both Libraries

從 Superpowers 取：

- Spec Compliance 先於 Code Quality；
- fresh reviewer 與 fix/re-review loop；
- receiving review 時的技術驗證；
- verification before completion。

從 Matt Pocock 取：

- 固定 review base；
- Standards 與 Spec 分軸；
- repo standards 優先於通用 smell baseline；
- 不把不同軸強制重排成一個模糊總分。

本專題新增：production risk lenses、structured finding contract、Project Overlay、finding verification 與 measurable evaluation。

## 13. Executable Code Review Lab

### 13.1 Fixture Contract

每個 fixture 包含：

- `spec.md`；
- `project-overlay.md`；
- review target 或 reproducible diff；
- buggy implementation；
- fixed implementation；
- tests 或 verification command；
- 與 reviewer 輸入隔離的 answer key。

首版使用 Python 標準庫與 `unittest`，不引入網路、資料庫服務或第三方套件。需要交易語義時優先使用標準庫 `sqlite3` 或可確定重現的 in-memory model。

### 13.2 Six Initial Fixtures

1. Data consistency：錯誤 transaction boundary、lost update 或 invariant break。
2. Idempotency：重試導致 duplicate side effect。
3. Timeout/retry/fallback：無 time budget、無界 retry 或不安全 fallback。
4. Interface coupling：抽象洩漏、錯誤 dependency direction 或過大的 public surface。
5. Error handling：吞錯、錯誤分類丟失或無法恢復。
6. Misleading tests：測試通過但沒有證明需求行為。

### 13.3 Runner Semantics

`run-fixtures.py` 必須把「預期 buggy case 失敗」與「驗證工具本身失敗」分開：

- buggy case 按預期暴露缺陷；
- fixed case 全部通過；
- 預期失敗不造成整體 runner 誤報；
- 任一 fixture 無法重現、fixed case 仍失敗或 answer-key metadata 不完整時，runner 非零退出。

### 13.4 Evaluation Dimensions

比較：

- implementer self-review 與 fresh-context review；
- single reviewer 與 multi-axis review；
- 有無 Core Profile / Project Overlay；
- initial review 與 re-review。

衡量：

- confirmed-defect recall；
- false-positive rate；
- severity calibration；
- evidence quality；
- actionability；
- rerun stability；
- token/cost proxy 與 latency。

`results-template.md` 記錄 model、harness、review mode、input packet、findings、answer-key comparison、耗時和成本代理值。首版不直接整合任何模型供應商 API；AI review run 由使用者在現有 Coding Agent harness 中執行，lab runner 只負責證明 fixture 與 fixed case 本身可重現。這避免引入 API key、網路和 provider-specific code，同時保留可比較的結果格式。

## 14. Production Engineering Profile

核心公式：

```text
Production-ready
  = universal engineering baseline
  + project-specific invariants
  + executable evidence
  + delivery gate
```

### 14.1 Core Profile Domains

1. Requirements and Invariants
2. Data Consistency and Concurrency
3. Error Handling and Resilience
4. Interface and Module Design
5. Compatibility and Migration
6. Security and Privacy
7. Performance and Capacity
8. Observability and Operability
9. Testing and Verification
10. Deployment, Rollback and Recovery

每條 core rule 使用固定 schema：

- Rule ID
- Applicability
- Requirement
- Rationale
- Required Evidence
- Review Severity When Violated
- Allowed Exception Process

規則不能只寫抽象口號。例如「external calls 要有 timeout」必須進一步要求 Project Overlay 提供 time budget、retry policy、idempotency requirement、metrics 與驗證方法。

### 14.2 Project Overlay

模板要求每個專案具體填寫：

- system purpose、criticality 與 data sensitivity；
- domain vocabulary 與 invariants；
- transaction、concurrency、idempotency 與 consistency model；
- external dependencies、timeout、retry、fallback 與 backpressure；
- public interfaces、compatibility 和 migration policy；
- SLO、capacity 與 performance budgets；
- security boundaries 與 authorization model；
- logs、metrics、traces 與 alerts；
- test seams、verification commands 與 required scenarios；
- deployment、rollback 和 recovery；
- language/framework conventions。

Core Profile 定義「必須回答什麼」，Project Overlay 回答「這個專案的具體答案是什麼」。

### 14.3 Workflow Integration

```text
brainstorm / grill
  -> identify applicable rules and invariants
spec
  -> turn them into acceptance criteria
plan
  -> map each criterion to implementation and evidence
TDD / implementation
  -> prove behavior at agreed seams
AI Code Review
  -> review against spec, profile and overlay
verification
  -> collect fresh command and runtime evidence
merge gate
  -> block while unresolved Critical findings remain
```

### 14.4 Upstream Customization Policy

- Project-specific quality difference：只改 Project Overlay。
- Cross-project standard：加入 Core Profile。
- Repeated review packet、finding schema 或額外 gate：建立薄 wrapper/orchestration skill，調用上游 skills。
- 只有 upstream trigger、hard gate、artifact contract 或 flow order 根本不符合需求時，才 fork 原 skill。

預設策略是「upstream 保持可升級 + local policy layer」，不是複製後全面魔改。

## 15. Adoption Playbook

`07-adoption-playbook.md` 要回答：

- 新專案第一次如何加入 Core Profile 與 Overlay；
- 如何在 `AGENTS.md` 或既有專案指令中引用，而不複製全文；
- 如何選擇 Superpowers、Matt flow 或最小組合；
- feature、bug、architecture、review 各自從哪個 skill 進入；
- 何時升級為自訂 wrapper skill；
- 如何隨上游更新重新驗證 snapshot facts；
- 如何記錄 accepted risk 和 rule exception；
- 如何避免把所有 gate 無條件套到小改動。

## 16. Legacy Document Migration

現有：

```text
ai/coding-agent/agent-skills-comparison/
```

使用 `git mv` 移入：

```text
ai/coding-agent/agent-skills/_archive/legacy-three-library-report/
```

歸檔入口要標示：

- 它是舊的三庫比較 snapshot；
- 其中 Matt Pocock 的 skill 數量、invocation model、workflow 和 distribution 等描述已漂移；
- 新主線不再使用它作事實來源；
- 保留只為追溯歷史思考。

不在舊文檔上逐句修補，避免同時維護兩套互相競爭的知識來源。

## 17. Worktree and Delivery Workflow

所有修改在獨立 worktree 進行：

```text
branch: codex/agent-skills-learning
worktree: /Users/buoy/Development/gitrepo/interview/.worktrees/agent-skills-learning
base: main at 8b34827063f060cd2190ce60108ca49bca7ab0f2
```

主工作區目前的 MySQL 修改不帶入、不暫存、不提交。

交付分為：

1. Design spec
2. Detailed implementation plan
3. Foundation and library chapters
4. Comparison and composition
5. AI Code Review protocol and lab
6. Production Profile and adoption playbook
7. Navigation, migration and final verification

每個階段只提交相關檔案。正文實作前，design spec 與 implementation plan 需要通過各自的 review gate。

## 18. Verification

### 18.1 Source Coverage

- Superpowers 14 個 skills 全部出現在 inventory 與 lifecycle map。
- Matt Pocock 約定的 12 個重點 skills 都有完整 skill contract。
- Matt 其餘 skills 有 index-only coverage，且 maturity bucket 正確。
- 所有 snapshot claims 可追到固定 commit 的原始文件。

### 18.2 Documentation Integrity

- 所有 expected files 存在。
- `README.md` 的線性與按任務導航都能抵達有效文件。
- internal Markdown links 指向存在的目標。
- 沒有 placeholder markers、空模板或未解決問題。
- descriptive claims 與 local normative rules 不混淆。
- legacy report 有明確 archived/outdated banner。
- `git diff --check` 通過。

### 18.3 Lab Verification

- `python3 ai/coding-agent/agent-skills/05-ai-code-review/lab/run-fixtures.py` 零退出。
- 每個 buggy case 的缺陷可確定重現。
- 每個 fixed case 通過。
- answer keys 與 review inputs 分離。
- lab 不需要網路或外部服務。

### 18.4 Git Scope

- worktree 只包含本專題修改。
- 不 stage 或 commit 主工作區的既有 MySQL 變更。
- commit 按交付階段拆分，訊息說清 intent。

## 19. Acceptance Criteria

本專題完成時必須同時滿足：

- 讀者可以先講兩庫的完整畫面，再下鑽核心 skill。
- Superpowers 全 14 個 skills 有流程化解釋。
- Matt 12 個重點 skills 有深度解釋，其餘有邊界清楚的索引。
- comparison 章回答兩庫差異、可組合點與衝突處理。
- AI Code Review Protocol 可直接交給 Agent 執行。
- finding schema、review isolation、fix/re-review 與 merge gate 明確。
- 六組 review fixtures 可重複執行並支援策略比較。
- Core Profile 與 Project Overlay Template 可複製到其他專案。
- 文檔明確回答何時加規範、何時寫 wrapper skill、何時才 fork upstream。
- source snapshot、導航、連結、runner 與 Git scope 全部通過驗證。

## 20. Non-Goals

- 不深挖 Matt Pocock 全部 41 個 skills。
- 不把 archived 的第三個 skill 庫重新納入主比較。
- 不建立完整 CI/CD 平台或真實多服務 production demo。
- 不聲稱 AI review 可以取代 deterministic tools、runtime evidence 或 human risk acceptance。
- 不把通用 Core Profile 寫成某一語言或框架的 coding style guide。
- 不直接修改兩個下載下來的 upstream repositories。
