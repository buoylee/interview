# Matt Pocock 8 Core Skills Guide

| Source field | Value |
|---|---|
| Library | `mattpocock/skills` |
| Local path | `/Users/buoy/Development/gitrepo/skills` |
| Snapshot | `ed37663cc5fbef691ddfecd080dff42f7e7e350d` (`v1.1.0-40-ged37663`) |
| Verified | `2026-07-21` |
| Primary sources | the eight corresponding `SKILL.md` files and their direct references |

### `grill-with-docs`

| Contract field | Explanation |
|---|---|
| Failure mode | 使用者與Agent以為已對齊，實際terms、edge cases和hard-to-reverse decisions仍模糊；討論結束後domain knowledge又消失。 |
| Trigger and preconditions | 有既有codebase、要變更plan/design且希望留下paper trail；repository setup應已指明domain docs。 |
| Inputs | 當前idea/design、`CONTEXT.md`/`CONTEXT-MAP.md`、ADRs、code與底層 `grilling` questions。 |
| Outputs | 已resolve的decision tree、更新的domain glossary、符合三條件時的ADR，以及可供spec synthesis的conversation。 |
| Internal flow | 這個wrapper只要求run `/grilling` 並使用 `/domain-modeling`；真正loop由兩者提供：持續問branching questions、挑戰terms/scenarios、即時寫docs。 |
| Composition | 作者main flow起點；紙上不能回答時handoff到`prototype`再回來；完成後direct `implement`或`to-spec`。 |
| Guarantees | 讓alignment failure更早暴露，並使canonical vocabulary/重要trade-off跨session保存。 |
| Non-guarantees | 不直接產生buildable spec、implementation plan或production acceptance；wrapper正文很薄，依賴底層skills完整載入。 |
| When not to use | 沒有codebase時使用`grill-me`；conversation已完整且只需synthesis時直接`to-spec`。 |
| Production gap | Grilling必須主動涵蓋consistency、security、failure、capacity、migration和recovery，否則docs仍只是術語更精確。 |
| Source anchors | `skills/engineering/grill-with-docs/SKILL.md`, `skills/productivity/grilling/SKILL.md`, `skills/engineering/domain-modeling/SKILL.md`。 |

### `to-spec`

| Contract field | Explanation |
|---|---|
| Failure mode | 長conversation沒有durable requirements artifact，或spec混入易漂移file/code detail、缺少test seam decision。 |
| Trigger and preconditions | 需求已經討論充分，只需synthesis；tracker/domain docs應由setup提供。此skill明確不再訪談。 |
| Inputs | current conversation、codebase state、domain glossary、ADRs、configured issue tracker。 |
| Outputs | 發布到tracker且標為`ready-for-agent`的spec，含Problem/Solution/User Stories/Implementation Decisions/Testing Decisions/Out of Scope/Notes。 |
| Internal flow | 探索現況 → 使用domain vocabulary/ADR → 優先existing/highest test seams並與使用者確認 → 依template合成 → publish。 |
| Composition | 接`grill-with-docs`或wayfinder decision map；multi-session work再接`to-tickets`，review Spec axis回讀此artifact。 |
| Guarantees | 將已討論內容結構化、固定user perspective和test seam，降低conversation loss和file-level過度承諾。 |
| Non-guarantees | 不檢查所有未討論需求；extensive user stories也不自動等於domain invariant或operational policy。 |
| When not to use | 仍有未決branch時先grill/prototype；只做一個小且明確behavior可direct implement。 |
| Production gap | Implementation/Testing Decisions應引用Project Overlay的transaction、SLO、compatibility、security、rollout和evidence。 |
| Source anchors | `skills/engineering/to-spec/SKILL.md`。 |

### `to-tickets`

| Contract field | Explanation |
|---|---|
| Failure mode | Multi-session spec被切成horizontal layers、ticket過大、dependency隱藏，導致fresh Agent無法單獨demo或保持green。 |
| Trigger and preconditions | 已有plan/spec/conversation需要拆成tracker work；tracker config和triage vocabulary已存在。 |
| Inputs | 完整source artifact及comments、codebase/domain context、可能的prefactor opportunities。 |
| Outputs | 使用者批准的tracer-bullet tickets，每張有end-to-end deliverable、acceptance criteria和blocking edges。 |
| Internal flow | gather → optional exploration/prefactor → vertical slices → wide refactor改用expand/migrate/contract → quiz granularity/edges → 按dependency order publish。 |
| Composition | 接`to-spec`；工作frontier上每個unblocked ticket交給fresh `implement`；不把自己產生的ready tickets再送`triage`。 |
| Guarantees | 每slice可demo/verifiable且fit one fresh context，dependency graph可見，避免layer-by-layer永遠半完成。 |
| Non-guarantees | Ticket graph不證明dependency/invariant完整；real tracker native blocking capability也依平台。 |
| When not to use | 單context小變更直接implement；不可vertical land的wide mechanical refactor使用skill內expand-contract例外。 |
| Production gap | 每ticket要帶適用rule IDs、failure/migration/observability/rollback evidence，不能只有user-facing happy path。 |
| Source anchors | `skills/engineering/to-tickets/SKILL.md`。 |

### `implement`

| Contract field | Explanation |
|---|---|
| Failure mode | Agent拿到spec/ticket後自由發揮、沒有feedback loop、只跑局部test、未review就commit。 |
| Trigger and preconditions | 使用者給出一個spec或ticket；test seams已pre-agreed，current branch/workspace已準備。 |
| Inputs | work description、agreed seams、repo commands/standards、domain vocabulary。 |
| Outputs | code、tests、regular typecheck/single-test evidence、final full-suite結果、code-review findings/fixes和commit。 |
| Internal flow | implement requested work → where possible use`tdd` at agreed seams → regularly typecheck/single tests → final full suite → `code-review` → commit current branch。 |
| Composition | 是main flow execution node，內部調用model-invoked `tdd`和`code-review`；每ticket建議fresh context。 |
| Guarantees | 明確要求feedback cadence和pre-commit review，防止大段盲寫後一次驗證。 |
| Non-guarantees | Skill正文只有少量orchestration；不定義worktree、finding resolution、production risk或commit granularity的完整契約。 |
| When not to use | 需求/decision未收斂時返回grill/spec；hard bug需先`diagnosing-bugs`建立loop。 |
| Production gap | 要由local wrapper/instructions加入isolation、exact review packet、risk lenses、fresh verification和merge gate。 |
| Source anchors | `skills/engineering/implement/SKILL.md`。 |

### `tdd`

| Contract field | Explanation |
|---|---|
| Failure mode | Tests耦合implementation、tautological、在錯誤seam、或先水平寫完全部tests再實作 imagined behavior。 |
| Trigger and preconditions | build/fix behavior test-first或被`implement`調用；必須先寫下并與使用者確認public test seams。 |
| Inputs | desired external behavior、confirmed seam、domain vocabulary/ADRs、independent expected value。 |
| Outputs | 一次一個vertical tracer-bullet的RED與minimal GREEN tests/code。 |
| Internal flow | 確認seam → one test at interface → watch RED → only enough code for GREEN → next slice；refactoring被明確留到code-review stage。 |
| Composition | 被`implement`使用；testability vocabulary來自`codebase-design`；bug regression由`diagnosing-bugs`先找到correct seam。 |
| Guarantees | 測試更像public behavior spec、可承受internal refactor，避免mock/private/tautology和bulk imagined tests。 |
| Non-guarantees | 使用者確認的seam仍可能漏掉critical path；GREEN不證明spec、data race、migration或runtime behavior完整。 |
| When not to use | 純prototype按其skill明確不寫tests；無法找到correct seam時先處理architecture，而非對internal硬測。 |
| Production gap | 需補failure/concurrency/replay/contract/performance tests、environment parity及required full verification。 |
| Source anchors | `skills/engineering/tdd/SKILL.md`, `tests.md`, `mocking.md`。 |

### `code-review`

| Contract field | Explanation |
|---|---|
| Failure mode | Review base不固定、repo standards和spec correctness互相掩蓋、單reviewer context把兩軸混在一起 rerank。 |
| Trigger and preconditions | review branch/PR/WIP或review since fixed point；fixed point必須可resolve且diff非空，tracker config可定位spec。 |
| Inputs | `git diff <fixed-point>...HEAD`、commit list、originating spec、repo standards、Fowler smell baseline。 |
| Outputs | 兩份side-by-side報告：`Standards`與`Spec`，以及每軸finding count/worst issue；不選跨軸總winner。 |
| Internal flow | pin fixed point/three-dot diff → find spec → find standards + baseline → parallel independent subagents → verbatim/light cleanup aggregation，不merge/rerank。 |
| Composition | `implement`完成前調用，也可standalone review；Standards消費repo policy，Spec消費`to-spec` artifact。 |
| Guarantees | 固定merge-base comparison、隔離兩種問題、repo standard覆蓋generic smell、tooling-enforced事項不重複。 |
| Non-guarantees | 缺spec時Spec軸skip；smells是judgment calls；兩軸不含完整security/reliability/operability lenses或finding verification。 |
| When not to use | 無fixed point、bad ref或empty diff時先停止；不是用來無界review整個repository。 |
| Production gap | 加入domain correctness、risk lenses、structured severity/evidence/status、fix/re-review和go/no-go authority。 |
| Source anchors | `skills/engineering/code-review/SKILL.md`。 |

### `diagnosing-bugs`

| Contract field | Explanation |
|---|---|
| Failure mode | 沒有能抓住exact symptom的loop就讀code猜理論；repro太慢/flake、test seam錯誤、debug logs殘留。 |
| Trigger and preconditions | hard bug、performance regression、intermittent flake或reported broken/failing/slow behavior。 |
| Inputs | user exact symptom、CONTEXT/ADRs、可存取repro環境/artifact，以及feedback-loop工具。 |
| Outputs | 一個已run的fast deterministic red-capable command、minimal repro、ranked falsifiable hypotheses、targeted probes、fix/regression evidence、cleanup/post-mortem。 |
| Internal flow | Phase 1 build/tighten loop → Phase 2 reproduce/minimise → Phase 3 show 3–5 hypotheses → Phase 4 one-prediction instrumentation → Phase 5 correct-seam regression/fix/original loop → Phase 6 cleanup/prevention。 |
| Composition | Correct seam使用`tdd`; 無seam是finding，修復後handoff到`improve-codebase-architecture`；不先大refactor。 |
| Guarantees | 把diagnosis鎖在user symptom和可反駁prediction，降低vibe hypothesis、log everything和wrong regression test。 |
| Non-guarantees | 無環境/artifact時會停止而非猜；feedback loop本身也可能模擬不完整production state。 |
| When not to use | straightforward new behavior不是bug diagnosis；但hard bug不可跳過Phase 1，除非明確justify。 |
| Production gap | Production incident還需mitigation、blast radius、data repair、monitoring、owner、postmortem和recovery證據。 |
| Source anchors | `skills/engineering/diagnosing-bugs/SKILL.md`。 |

### `handoff`

| Contract field | Explanation |
|---|---|
| Failure mode | Context window滿或要branch session時，next Agent拿到重複、過期、缺next-step甚至含secret的巨大summary。 |
| Trigger and preconditions | 要交給fresh agent/session繼續，或使用者指定next session focus；OS temp directory可寫。 |
| Inputs | current conversation、已存在spec/plan/ADR/issue/commit/diff references、next-session purpose。 |
| Outputs | temp directory中的redacted Markdown handoff，含suggested skills與必要references。 |
| Internal flow | 摘要current state/decisions/open work → 不複製其他artifact → reference paths/URLs → redact API key/password/PII → tailor next focus。 |
| Composition | 在prototype detour、smart-zone boundary或任何cross-session point雙向使用；new session引用檔案。 |
| Guarantees | 降低conversation loss和重複內容，讓fresh context知道canonical artifacts與建議skills。 |
| Non-guarantees | Summary必然有loss；temp file retention和host accessibility需確認；引用artifact若漂移仍會過期。 |
| When not to use | 想留在同一conversation只做phase break可用built-in compact；durable project decision應進spec/ADR而非handoff。 |
| Production gap | 交接還需owner、deadline、environment/access、risk/open finding、verification state和secret-safe retention policy。 |
| Source anchors | `skills/productivity/handoff/SKILL.md`。 |
