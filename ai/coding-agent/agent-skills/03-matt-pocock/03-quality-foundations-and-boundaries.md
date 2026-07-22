# Matt Pocock 品質基礎、條件能力與邊界

| Source field | Value |
|---|---|
| Library | `mattpocock/skills` |
| Local path | `/Users/buoy/Development/gitrepo/skills` |
| Snapshot | `ed37663cc5fbef691ddfecd080dff42f7e7e350d` (`v1.1.0-40-ged37663`) |
| Verified | `2026-07-21` |
| Primary sources | `domain-modeling`, `codebase-design`, `prototype`, `improve-codebase-architecture` and direct references |

### `domain-modeling`

| Contract field | Explanation |
|---|---|
| Failure mode | Domain expert、developer、Agent使用模糊/重載詞，code/docs各自發明語言，hard-to-reverse decision沒有理由。 |
| Trigger and preconditions | 使用者要釐清domain terminology/ubiquitous language、record architecture decision，或其他skill需要主動維護model。只讀glossary不算觸發。 |
| Inputs | root/per-context `CONTEXT.md`、`CONTEXT-MAP.md`、ADRs、conversation terms、concrete edge scenarios、現有code behavior。 |
| Outputs | 即時更新的純glossary `CONTEXT.md`；符合hard-to-reverse + surprising + real-trade-off三條件時的ADR。 |
| Internal flow | challenge glossary conflict → sharpen fuzzy/overloaded words → invent edge scenarios → cross-check code contradiction → inline glossary update → sparingly offer ADR。Files lazy-create。 |
| Composition | `grill-with-docs`和architecture grilling主動使用；其他skills讀其vocabulary但不一定修改。 |
| Guarantees | 建立canonical terms、暴露概念boundary矛盾，讓code/test/file names與conversation更一致。 |
| Non-guarantees | `CONTEXT.md`明確不是spec、scratch pad或implementation decision store；language model不等於完整behavior model。 |
| When not to use | 只是消費已穩定vocabulary時直接讀檔；可逆/明顯/無trade-off決定不寫ADR。 |
| Production gap | Glossary還需把關鍵terms連到state machine、ownership、invariants、consistency、authorization和evidence。 |
| Source anchors | `skills/engineering/domain-modeling/SKILL.md`, `CONTEXT-FORMAT.md`, `ADR-FORMAT.md`。 |

### `codebase-design`

| Contract field | Explanation |
|---|---|
| Failure mode | Agent抽出大量shallow wrappers/“interfaces”只為mock，caller仍需知道內部細節，修改散落且test不代表真實seam。 |
| Trigger and preconditions | 設計/改善module interface、找deepening、決定seam、提高testability/AI-navigability，或其他skill需要共享design vocabulary。 |
| Inputs | domain concepts、caller needs、現有module/interface/adapter、variation evidence、tests和dependency graph。 |
| Outputs | 用Module/Interface/Depth/Seam/Adapter/Leverage/Locality描述的design，以及small interface上的test surface。 |
| Internal flow | 定義caller必須知道的完整interface → 比較hidden behavior與surface → deletion test → 檢查test seam/dependency injection/result return → 只有真variation才引入seam；需要時design-it-twice。 |
| Composition | `tdd`用interface作test surface；`improve-codebase-architecture`用它評估candidate；domain-modeling為seam命名。 |
| Guarantees | 使encapsulation、interface、decoupling不只是主觀“clean code”，而能用leverage/locality/test surface討論。 |
| Non-guarantees | “Deep”不是越大越好；一個adapter通常只是hypothetical seam；vocabulary不會自動選對domain/transaction boundary。 |
| When not to use | 沒有實際variation/caller leverage時不要為抽象而抽象；單純type keyword不是此處的Interface概念。 |
| Production gap | Interface還要明文包含invariant、ordering、error、configuration、performance、compatibility和security obligations。 |
| Source anchors | `skills/engineering/codebase-design/SKILL.md`, `DEEPENING.md`, `DESIGN-IT-TWICE.md`。 |

### `prototype`

| Contract field | Explanation |
|---|---|
| Failure mode | 紙上討論無法判斷state/logic/UI，卻直接把第一個production implementation當答案；或prototype被誤認為可merge code。 |
| Trigger and preconditions | 一個明確design question需要runnable/visual feedback；能判定logic branch或UI branch。 |
| Inputs | 要回答的單一問題、surrounding backend/page context、project task runner/routing convention。 |
| Outputs | 明確標示throwaway、one-command runnable、state可見的terminal app或多variation UI；throwaway branch primary source與captured verdict。 |
| Internal flow | 判定logic/UI（user不在時依context並聲明assumption）→ near-real-use位置但清楚命名 → in-memory/low polish → surface full state → capture question/verdict/branch → 真實implementation只帶回validated decision。 |
| Composition | Main flow grilling的detour，通常用`handoff`出去/回來；結果進spec/issue，不把prototype直接當production。 |
| Guarantees | 快速把抽象design question轉成可操作feedback，並保持question和throwaway status可見。 |
| Non-guarantees | 規則刻意skip tests、production error handling、abstraction和persistence；完全不提供production readiness。 |
| When not to use | 問題可由conversation/primary research回答、或使用者其實要求production implementation時不用。 |
| Production gap | 真實實作必須重新走spec/TDD/review，補data、security、resilience、observability、performance、deploy/recovery。 |
| Source anchors | `skills/engineering/prototype/SKILL.md`, `LOGIC.md`, `UI.md`。 |

### `improve-codebase-architecture`

| Contract field | Explanation |
|---|---|
| Failure mode | Agent加速code entropy，shallow modules、coupling、low locality和錯誤test seams累積；又以全庫heuristic大refactor回應。 |
| Trigger and preconditions | 使用者要掃描codebase deepening opportunities；需要domain docs、ADRs、codebase-design vocabulary和探索能力。 |
| Inputs | user scope或recent commit hot spots、`CONTEXT.md`、ADRs、files/modules/tests、exploration friction。 |
| Outputs | OS temp中的visual HTML candidate report（files/problem/solution/benefits/before-after/recommendation），以及使用者選案後的grilled design decisions。 |
| Internal flow | scope/YAGNI → read domain/ADR → organic Explore找shallow/locality/coupling/test friction + deletion test → visual report（先不提interfaces）→ user picks → grilling + domain updates + optional design-it-twice。 |
| Composition | 建立candidate idea後回到`grill-with-docs`/main flow；使用`codebase-design` vocabulary和`domain-modeling` side effects。Bug diagnosis無seam時可提供具體handoff。 |
| Guarantees | 把architecture改善聚焦recent/real friction，先讓人比較candidate再承諾interface，並把benefit連到locality/leverage/tests。 |
| Non-guarantees | HTML使用Tailwind/Mermaid CDN且需要可開browser；candidate只是proposal，不證明refactor value或production safety。 |
| When not to use | 當前feature不受architecture阻礙時不要“順手”全庫掃描；沒有evidence的theoretical ADR conflict不重開。 |
| Production gap | Approved candidate仍需migration/compatibility、incremental rollout、performance、ownership、rollback和full regression plan。 |
| Source anchors | `skills/engineering/improve-codebase-architecture/SKILL.md`, `HTML-REPORT.md`, plus `codebase-design` references。 |

## Why These Four Matter to Production Quality

這四個skill分別回答production code常被泛化成一句“clean architecture”的四個問題：

| Question | Skill contribution |
|---|---|
| 我們說的domain object/state到底是什麼？ | `domain-modeling` 固定canonical terms並用edge scenario測boundary |
| 哪些behavior應藏在同一module，caller應知道多少？ | `codebase-design` 用depth/leverage/locality設計interface |
| 哪個未知design decision值得先用code學習？ | `prototype` 把單一問題變成throwaway feedback |
| 已有codebase哪裡因shallow/coupling難理解、難測？ | `improve-codebase-architecture` 從real friction找deepening candidate |

它們讓可讀性、封裝、複用、面向interface和解耦變成有boundary的判斷：

- **可讀性**來自canonical vocabulary和locality，不只是命名格式。
- **封裝**是caller不用知道implementation complexity；Interface包含behavior contract，不只method list。
- **複用**來自一個deep module對多callers提供leverage，不是先抽generic helper。
- **面向interface**要有real seam/variation；一個adapter時通常不急著抽象。
- **解耦**是stable dependency direction和change locality，不是module數量越多越好。

## What They Still Cannot Infer

即使domain words和module shape都很好，skills仍不能從generic principle推導：

- balance是否strongly consistent或eventually reconciled；
- concurrent writes用lock、optimistic version或single writer；
- idempotency跨process/crash的store和retention；
- external call的time budget、safe retry和fallback；
- interface consumer compatibility/deprecation；
- authorization、privacy、SLO、capacity、telemetry、rollout、rollback、RPO/RTO。

這些要進spec/Core Profile/Project Overlay，並用tests、rehearsals、runtime signals或human decision證明。

## Intro-Only Skills

`setup-matt-pocock-skills` 解決repository prerequisites；`ask-matt` 解決路由。兩者需要理解，但不使用11-field deep contract，因為它們不直接處理feature correctness或production quality。

Setup產物是engineering skills的依賴：issue tracker、triage label mapping、domain docs layout和instructions block。若缺少，`to-spec`/`to-tickets`/review可能無法找到正確artifact destination。

## Index-Only Boundary

其餘27個skills保留在 [Complete Snapshot Inventory](./README.md#complete-snapshot-inventory)。Index-only不代表“不好”，而是本次學習目標不需要同等深度：有些是on-ramp/governance、host setup、writing/teaching、個人workflow，有些仍在in-progress或已deprecated。

## When to Add Project Policy

一旦requirements含money、identity、authorization、sensitive data、migration、concurrency、external side effect或SLO-critical path，就不能只依賴design vocabulary。至少補：

1. applicable business invariants和forbidden states；
2. consistency/idempotency/failure semantics；
3. interface compatibility和migration；
4. security/performance/observability budgets；
5. tests/runtime/deploy/recovery evidence；
6. review severity和go/no-go authority。

預設將這些放Project Overlay；跨專案都成立的義務提升到Core Profile；反覆使用相同packet/gate才寫thin wrapper；只有上游structural contract衝突才fork。

## 一句話總結

Matt 的品質foundation能讓Agent更準確地談domain與code shape，但production-grade仍需要專案自己把不可違反的facts和可執行evidence接進main flow。
