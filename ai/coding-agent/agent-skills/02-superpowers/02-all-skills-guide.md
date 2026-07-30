# Superpowers 14 Skills Guide

| Source field | Value |
|---|---|
| Library | `obra/superpowers` |
| Local path | `/Users/buoy/Development/gitrepo/superpowers` |
| Snapshot | `d884ae04edebef577e82ff7c4e143debd0bbec99` (`v6.1.1`) |
| Verified | `2026-07-21` |
| Primary sources | the corresponding `skills/<name>/SKILL.md` plus directly referenced prompts/scripts |

本章按 lifecycle 排序，不按字母排序。每個 skill 都用同一份 contract，讓「它做了什麼」和「它仍不能保證什麼」同時可見。

### `using-superpowers`

| Contract field | Explanation |
|---|---|
| Failure mode | Agent 先回覆、問問題或操作，之後才想起適用 skill；或只憑 `description` 猜 workflow。 |
| Trigger and preconditions | 每次 conversation/task 開始、任何 response/action 前；host 必須能列出或載入可用 skills。 |
| Inputs | 使用者請求、available-skills catalog、host/system instructions。 |
| Outputs | 已選定並完整讀取的 skill、對使用者的使用公告，以及受該 skill 約束的下一步。 |
| Internal flow | 判斷是否有哪怕小機率適用的 skill → 先載入 → 建 checklist/todos → 才回覆或操作；process skills 通常先於 implementation skills。 |
| Composition | 是整套 methodology 的 dispatcher；會導向 `brainstorming`、`systematic-debugging`、`writing-skills` 等情境 skill。 |
| Guarantees | 降低漏用流程、先做後補理由、只讀摘要不讀正文的機率。 |
| Non-guarantees | 不能保證 discovery metadata 正確、host 真的 enforce、或被選 skill 具有 project facts。 |
| When not to use | 它是入口 discipline，不是一個可選的 feature implementation technique；不應拿來替代實際 domain skill。 |
| Production gap | 仍需 repository instructions、risk classification、domain invariants、tool permissions 和 delivery policy。 |
| Source anchors | `skills/using-superpowers/SKILL.md` at snapshot `d884ae0`。 |

### `brainstorming`

| Contract field | Explanation |
|---|---|
| Failure mode | 在需求、成功邊界和 trade-off 未決時直接 code，導致返工或把假設固化成 implementation。 |
| Trigger and preconditions | 任何 creative work、feature、component、behavior change 前；需要能讀 project context 並與使用者互動。 |
| Inputs | 使用者目的、repo/docs/recent changes、constraints、success criteria。 |
| Outputs | 經分段確認、自檢、使用者 review 且 committed 的 design spec。 |
| Internal flow | 探索 context → 在真的有視覺決策時才 offer visual companion → 一次一問 → 提 2–3 approaches → 分段批准 design → 寫 spec → placeholder/contradiction/scope/ambiguity self-review → user review。 |
| Composition | 唯一 terminal transition 是 `writing-plans`；不是直接轉到 code generation。 |
| Guarantees | 固定需求決策、non-goals、architecture和 approval boundary；降低邊做邊猜。 |
| Non-guarantees | Approval 不等於完整 production requirements，也不證明方案可運行或可恢復。 |
| When not to use | 已有明確 approved spec 時不必重新發明需求；但 scope 變更要返回本流程。 |
| Production gap | Spec 還需注入 consistency、security、capacity、compatibility、observability、rollback/recovery 等 project facts。 |
| Source anchors | `skills/brainstorming/SKILL.md`；必要時 `skills/brainstorming/visual-companion.md`。 |

### `using-git-worktrees`

| Contract field | Explanation |
|---|---|
| Failure mode | 在使用者 dirty checkout 上混入變更、建立 nested/phantom worktree、或無法區分 baseline failure 和新 regression。 |
| Trigger and preconditions | 開始需要隔離的 feature work 或執行 implementation plan 前；必須位於 Git repository。 |
| Inputs | current `git-dir`/`git-common-dir`、branch/detached state、submodule state、host native worktree capability、ignore rules。 |
| Outputs | 已存在或新建的 isolated workspace、project setup 結果和 clean baseline evidence。 |
| Internal flow | 先偵測 linked worktree並排除 submodule → 優先 native tool → fallback 到 ignored `.worktrees/` → setup → baseline tests。 |
| Composition | 位於 `brainstorming`/approved spec 後、`writing-plans` execution 前；`finishing-a-development-branch` 使用 provenance 決定 cleanup。 |
| Guarantees | 隔離 scope、保護主 checkout、固定 review base，並揭露 pre-existing failure。 |
| Non-guarantees | 不保證 test suite 完整、branch base 是使用者真正想要的 lineage、或 worktree 外 external state 隔離。 |
| When not to use | 已在 harness-managed linked worktree 時不得再建 nested worktree；使用者明確拒絕時在原地但仍驗證 baseline。 |
| Production gap | 還需 CI/environment parity、secrets/data isolation、deployment sandbox 和 branch protection policy。 |
| Source anchors | `skills/using-git-worktrees/SKILL.md`。 |

### `writing-plans`

| Contract field | Explanation |
|---|---|
| Failure mode | Plan 只有高階口號，fresh implementer 要猜檔案、interfaces、test、commands 或 task dependency。 |
| Trigger and preconditions | 已有 approved spec/requirements、尚未 implementation；大型多 subsystem spec 應先拆 plan。 |
| Inputs | committed spec、repo structure/patterns、global constraints、verification commands。 |
| Outputs | `docs/superpowers/plans/YYYY-MM-DD-*.md`，含 file structure、Global Constraints、task Interfaces、checkbox steps、expected output 和 commits。 |
| Internal flow | 鎖定 file boundaries → 以可獨立 review/test 的 task 拆分 → 每一步 2–5 分鐘單一 action → exact code/command → spec coverage/placeholder/type self-review。 |
| Composition | 接收 `brainstorming` spec；交給 `subagent-driven-development`（推薦）或 `executing-plans`。 |
| Guarantees | 降低 fresh agent 猜測、跨 task naming drift、沒有驗證就 commit 和 task scope 模糊。 |
| Non-guarantees | 精確 plan 仍可能精確地實作錯 spec；command 也可能因環境漂移失效。 |
| When not to use | 一步即可回答的 read-only解釋不需要大型 plan；需求未批准時應回到 design。 |
| Production gap | Global Constraints 必須引用 Core/Overlay 的實際 invariants、budgets、compatibility 和 evidence，不能只寫 coding steps。 |
| Source anchors | `skills/writing-plans/SKILL.md`。 |

### `subagent-driven-development`

| Contract field | Explanation |
|---|---|
| Failure mode | 長 session context 污染、同一 Agent 實作又自批、task diff 被截斷、跨 task Minor finding 遺失。 |
| Trigger and preconditions | 當前 session 有可拆的 implementation plan、host 有 subagents、tasks 可序列化執行；先完成 worktree isolation。 |
| Inputs | plan、Global Constraints、task number、per-task BASE、task brief、implementer report、review package。 |
| Outputs | 每 task commits/report、ordered spec/quality verdicts、fix/re-review結果、durable progress ledger、final whole-branch review。 |
| Internal flow | plan pre-flight → `task-brief` → fresh implementer → record HEAD/report → `review-package BASE HEAD` → one fresh task reviewer Part 1/Part 2 → fix/re-review Critical/Important → ledger Minor → next task → final branch review。 |
| Composition | 執行 `writing-plans`；task 內依賴 TDD/debugging，使用 review prompt；最後轉 `finishing-a-development-branch`。 |
| Guarantees | 強化 role/context isolation、固定 task scope、保留多 commit diff、讓 claims 與 code evidence 分離。 |
| Non-guarantees | Reviewer 不重跑完整 suite，也不應 crawl 整庫；brief 未提供的跨 task invariant仍可能漏掉，final review 也不是 oracle。 |
| When not to use | tasks 高度共享 state、需要同時改同一檔案，或 host 無 subagent；這時用 `executing-plans`。 |
| Production gap | Review packet 需額外含 project standards、domain invariants、risk lenses、migration/runtime evidence，才能判斷 production readiness。 |
| Source anchors | `skills/subagent-driven-development/SKILL.md`, `implementer-prompt.md`, `task-reviewer-prompt.md`, `scripts/task-brief`, `scripts/review-package`, `scripts/sdd-workspace`。 |

### `executing-plans`

| Contract field | Explanation |
|---|---|
| Failure mode | 有 plan 卻自由發揮、跳過 task verification，或遇到 blocker仍硬做。 |
| Trigger and preconditions | 在 separate/inline session 執行既有 written plan，尤其未採用 per-task subagent flow時；不得在未授權 main/master 上開始。 |
| Inputs | 完整 plan、clean isolated workspace、task checklist。 |
| Outputs | 按順序完成且逐項驗證的 tasks、checkpoint status，最後進 branch finishing。 |
| Internal flow | load/critical review plan → 有 concern 先停問 → 建 todos → 每 task in-progress/steps/verification/completed → 全部完成後 invoke branch finishing。 |
| Composition | 是 SDD 的替代 execution strategy；仍會按 task 觸發 TDD、debugging、verification。 |
| Guarantees | 保持 plan traceability、一次只進行一 task、遇到 ambiguity/failure停止而非猜測。 |
| Non-guarantees | 同一 controller 持續累積 context，缺少 fresh implementer/reviewer separation。 |
| When not to use | host 支援且使用者選擇 SDD、tasks適合 fresh agents時優先 SDD；沒有 plan時先寫 plan。 |
| Production gap | Inline self-review需額外 independent approval；仍需 project-specific quality gates。 |
| Source anchors | `skills/executing-plans/SKILL.md`。 |

### `dispatching-parallel-agents`

| Contract field | Explanation |
|---|---|
| Failure mode | 多個無關 failure/investigation 被單一 context 串行處理；或反過來把共享 state 的工作錯誤並行造成衝突。 |
| Trigger and preconditions | 至少兩個能在不共享 state、無順序依賴下獨立解決的 domain；host 支援 parallel agents。 |
| Inputs | 對每個 domain 清楚的 scope、symptom、constraints、expected report，並保留 controller integration responsibility。 |
| Outputs | 各自獨立的 diagnosis/changes/reports，之後由 controller驗證並整合。 |
| Internal flow | 分組 independent domains → 每 domain 一 agent → parallel run → 逐一 review outputs/diffs → combined verification。 |
| Composition | 可由 plan/execution在真正獨立時選用；bug agent仍應遵循 systematic debugging。 |
| Guarantees | 降低無關 context互相污染與等待時間，讓每個 agent聚焦一個問題。 |
| Non-guarantees | 不自動解決 merge conflict、shared resource race、跨 domain invariant或錯誤拆分。 |
| When not to use | 同檔修改、同一 root cause、需要前一步結果、或需要全局 design decision時不要並行。 |
| Production gap | Controller仍需 integration test、system-level review、capacity/cost控制和一致 delivery gate。 |
| Source anchors | `skills/dispatching-parallel-agents/SKILL.md`。 |

### `test-driven-development`

| Contract field | Explanation |
|---|---|
| Failure mode | 先寫 implementation再補會立即通過的 test，導致 test只驗證既有實作而非需求。 |
| Trigger and preconditions | feature、bugfix、refactor、behavior change；prototype/generated/config例外需 human同意。 |
| Inputs | 單一 desired behavior、可執行 test harness、理解目前 failure boundary。 |
| Outputs | 正確原因失敗的 RED、最小 GREEN implementation、保持全綠的 REFACTOR和測試證據。 |
| Internal flow | 寫一個 behavior test → 執行並確認 expected failure非 syntax/setup error → minimal code → fresh pass + full relevant suite → refactor → repeat。 |
| Composition | implementation task 的核心 loop；bugfix先由 systematic debugging定位，再用 failing regression test證明。 |
| Guarantees | 證明新增 test有抓住缺少 behavior的能力，降低 tests-after confirmation bias，提供可重跑 regression。 |
| Non-guarantees | 不保證需求完整、test oracle正確、integration/production環境等價或所有 edge cases被想到。 |
| When not to use | 只有 human批准的 throwaway prototype、generated code或純 configuration例外；不能由 Agent自行合理化。 |
| Production gap | 還需 invariant/contract/failure/concurrency/migration/performance tests和真實 runtime evidence。 |
| Source anchors | `skills/test-driven-development/SKILL.md`, `skills/test-driven-development/testing-anti-patterns.md`。 |

### `systematic-debugging`

| Contract field | Explanation |
|---|---|
| Failure mode | 看見 symptom就猜修、同時改多個變數、quick patch掩蓋 root cause，導致反覆失敗與新 regression。 |
| Trigger and preconditions | 任意 bug、test/build failure、unexpected behavior、performance或integration issue，尤其已嘗試過修復時。 |
| Inputs | 完整 error/stack、reproduction steps、recent diff、component-boundary evidence、working reference。 |
| Outputs | root-cause chain、single hypothesis/minimal experiment、failing regression test、single fix和verified outcome。 |
| Internal flow | Phase 1 read/reproduce/change/evidence/data flow → Phase 2 working pattern/full reference/differences → Phase 3 one hypothesis/one variable → Phase 4 regression test/fix/verify；三次失敗停下討論 architecture。 |
| Composition | Phase 4 使用 TDD；完成主張使用 verification-before-completion；支援 root-cause-tracing、defense-in-depth、condition-based-waiting。 |
| Guarantees | 把 fix 和 evidence/root cause連接，降低 symptom patch和無法歸因的多變量變更。 |
| Non-guarantees | 有些外部/timing/environment issue仍需 monitoring與防護；「95%」等效果數字不是本專案實測保證。 |
| When not to use | 沒有 failure、只是新 feature design時不用；但不能因 bug看似簡單而跳過 root cause。 |
| Production gap | Root cause後仍需 blast radius、data repair、rollback、incident response、observability和postmortem。 |
| Source anchors | `skills/systematic-debugging/SKILL.md` 及同目錄 supporting techniques。 |

### `requesting-code-review`

| Contract field | Explanation |
|---|---|
| Failure mode | 只說「幫我看一下」、review range飄動、reviewer不知道 requirements，或實作者直接自批通過。 |
| Trigger and preconditions | task/major feature完成、merge前、或需要 independent review；implementation已在可識別 base/head。 |
| Inputs | WHAT_WAS_IMPLEMENTED、PLAN_OR_REQUIREMENTS、BASE_SHA、HEAD_SHA和適用 standards/evidence。 |
| Outputs | 按 severity 的 strengths/issues/assessment，包含 file:line、impact和fix direction。 |
| Internal flow | 取得 base/head → dispatch reviewer template → reviewer讀 requirements與 diff → 檢查 correctness、design、tests、production readiness → controller處理 findings。 |
| Composition | SDD用自己的 task reviewer做窄 gate；全部 task後可用此 broad reviewer做 whole-branch review；feedback交給 `receiving-code-review`。 |
| Guarantees | 固定 review object和requirements，增加 independent eyes並按 impact校準 finding。 |
| Non-guarantees | Generic rubric不知道完整 domain policy；reviewer可能誤報、漏報，且不能替代 tests/build/runtime checks。 |
| When not to use | 沒有固定 diff或requirements時先補 packet；不要把 reviewer當成任意 codebase探索代理。 |
| Production gap | 應加入 Core/Overlay、risk lenses、migration/compatibility evidence、finding verification和explicit go/no-go。 |
| Source anchors | `skills/requesting-code-review/SKILL.md`, `skills/requesting-code-review/code-reviewer.md`。 |

### `receiving-code-review`

| Contract field | Explanation |
|---|---|
| Failure mode | 對 feedback performative agreement、盲目照改、一次實作模糊多項、或因 reviewer權威而忽略技術錯誤。 |
| Trigger and preconditions | 收到任何 code review feedback，尤其模糊、與 codebase不符或多項一起出現時。 |
| Inputs | 原 finding、實際 code/diff、project constraints、可重現 test或doc evidence。 |
| Outputs | 經驗證的 accepted/disputed/clarification decision、逐項 fix和re-verification。 |
| Internal flow | 讀完整 feedback → restate technical requirement → 對 repo驗證 → 不清楚先問 → 按項實作 → tests/re-review；不做空洞道歉/讚美。 |
| Composition | 接在 task/branch review後；若修復引發 failure，轉 systematic debugging/TDD；完成後再 review。 |
| Guarantees | 把 reviewer comment視為待驗證 technical claim，降低錯誤建議和群組誤解被直接寫入 code。 |
| Non-guarantees | Disagree本身不代表正確；最後仍需 evidence和必要的人類 risk decision。 |
| When not to use | 不適用於單純社交回覆；但任何會改 code的 feedback都應先經技術判斷。 |
| Production gap | 需要 structured finding status、owner、accepted-risk authority、expiry和verification contract。 |
| Source anchors | `skills/receiving-code-review/SKILL.md`。 |

### `verification-before-completion`

| Contract field | Explanation |
|---|---|
| Failure mode | 用「應該可以」、先前 run、partial check、agent report或自信替代 exact completion evidence。 |
| Trigger and preconditions | 任何成功/完成/修復/通過主張前，以及 commit、PR、task transition前。 |
| Inputs | 要聲稱的精確命題、能證明該命題的完整 command、目前 workspace/state。 |
| Outputs | fresh command output、exit/failure count和只與 evidence相符的 status statement。 |
| Internal flow | IDENTIFY proof command → RUN full/fresh → READ complete output → VERIFY是否支持 claim → 只在支持時陳述。Regression test還需 red-green proof。 |
| Composition | 所有 implementation/review/debug task的最後 gate；完成後才可進 branch finishing。 |
| Guarantees | 將語言主張與當下 evidence綁定，阻止 partial/old/second-hand結果被冒充完成。 |
| Non-guarantees | Command可能選錯、test suite可能不完整、environment可能與production不同。 |
| When not to use | 沒有 completion claim的探索中不需假裝完成；但任何正面 status implication都受約束。 |
| Production gap | Proof set要由 Project Overlay定義，包含 migration、runtime、security、rollback/recovery而非只跑 unit tests。 |
| Source anchors | `skills/verification-before-completion/SKILL.md`。 |

### `finishing-a-development-branch`

| Contract field | Explanation |
|---|---|
| Failure mode | tests未過就 merge/PR、誤刪 worktree、detached state仍提供錯誤選項、discard未確認。 |
| Trigger and preconditions | implementation完整、所有適用 tests通過、準備決定 branch disposition。 |
| Inputs | fresh test result、git-dir/common-dir、branch/detached state、base branch、worktree provenance。 |
| Outputs | local merge、push/PR、保留 branch，或經確認的 discard；必要時安全 cleanup。 |
| Internal flow | verify tests → detect environment → determine base → 依 state呈現固定選項 → 執行選擇 → 只在 merge/discard且 owned worktree時 cleanup。 |
| Composition | 接在 execution + verification後；merge後再次跑 tests。 |
| Guarantees | 降低錯誤 workspace cleanup、未確認刪除、PR後失去 iteration worktree和merge後未驗證。 |
| Non-guarantees | 不包含 production deployment、release approval、database rollback或incident readiness。 |
| When not to use | tests失敗時停止；harness-owned/detached workspace不可擅自移除。 |
| Production gap | 還需 CI/branch protection、release strategy、deploy/rollback/recovery和change management。 |
| Source anchors | `skills/finishing-a-development-branch/SKILL.md`。 |

### `writing-skills`

| Contract field | Explanation |
|---|---|
| Failure mode | 只憑作者覺得清楚就部署 skill；description洩漏 workflow造成跳讀；規則在壓力下被 Agent合理化。 |
| Trigger and preconditions | 建立、修改或部署任何 skill；須先理解 TDD，並能用 fresh-context/pressure scenarios測試行為。 |
| Inputs | baseline failure scenario、Agent rationalizations、skill type、discovery keywords、agentskills.io frontmatter constraints。 |
| Outputs | 經 RED-GREEN-REFACTOR驗證的 `SKILL.md`、必要 supporting references/tools、deployment evidence。 |
| Internal flow | 無 skill跑 baseline RED → 分類 failure shape → 寫最小 guidance GREEN → micro-test wording + pressure scenarios → 收集新 loopholes → refactor/retest → 每個 skill獨立部署。 |
| Composition | REQUIRED BACKGROUND 是 TDD；產出的 skill由 `using-superpowers` discovery；可引用其他 skill但避免 force-load重內容。 |
| Guarantees | 證明 guidance相對 no-guidance control改變了可觀察行為，並針對真實 rationalization收緊規則。 |
| Non-guarantees | 少量 model samples不是永久可靠性證明；不同 model/harness/version仍會漂移。 |
| When not to use | one-off project convention放 instructions；可用機械 validator enforce的規則優先自動化；普通已充分文件化知識不必再包 skill。 |
| Production gap | Skill本身也需要版本、owner、eval corpus、regression cadence、distribution和安全審查。 |
| Source anchors | `skills/writing-skills/SKILL.md` 及 `testing-skills-with-subagents.md`, `anthropic-best-practices.md`。 |
