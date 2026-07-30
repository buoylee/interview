# 07 - Agent Skills 與 Production Profile Adoption Playbook

## 先給結論

採用時不要一次安裝所有skills、複製30條rules後宣布完成。先選primary lifecycle，建立最小可引用Core/Overlay和review gate，再按真實risk擴展evidence。Risk tier改變review深度與角色數量，不改變applicable invariant的真假。

## First Adoption in a New Project

1. 指定一位adoption owner與production decision authority。
2. 選primary lifecycle：Superpowers end-to-end，或既有團隊流程；Matt skills按缺口加入。
3. 將[Core Profile](./06-production-profile/02-core-profile.md)複製/引用到project canonical docs，保留stable IDs與版本。
4. 複製[Project Overlay Template](./06-production-profile/03-project-overlay-template.md)，先完成system risk、domain/data、dependencies、commands與delivery/recovery最小集合。
5. 在`AGENTS.md`只放短入口與hard rules，不複製整份Profile。
6. 選一個Tier M真實feature試跑spec → plan → TDD → review → verification → gate。
7. 用[AI Review Lab](./05-ai-code-review/lab/README.md)校準review strategy，再以真實diff pilot。
8. 從escaped defects、review false positives與流程摩擦更新Overlay/Core/wrapper；不要為一個task fork。

## Referencing from AGENTS.md

以下paths只是可調整example，重點是link canonical artifacts而不是複製多份易漂移內容：

```markdown
## Production engineering

- Apply the Core Profile at `docs/engineering/production-core.md`.
- Project facts and exceptions live in `docs/engineering/project-overlay.md`.
- Specs and plans must cite applicable rule IDs.
- Code Review follows `docs/engineering/ai-code-review-protocol.md`.
- Do not approve unresolved Critical findings; Important exceptions require the Overlay exception record.
```

Project instructions另列exact commands、source paths與primary lifecycle。若host有skill discovery requirement，link對應skill入口；不要把完整Core、Overlay和review prompt全部塞進每次context。

## Choose a Primary Lifecycle

| 現況 | 建議primary lifecycle | Optional additions |
|---|---|---|
| 尚無一致工程流程 | Superpowers lifecycle | Matt domain modeling、codebase design、fixed-base review、handoff |
| 已有成熟ticket/CI/review流程 | Existing lifecycle | 只嵌Core/Overlay packet與production review gate |
| Artifact-driven多session團隊 | Existing/Superpowers execution | Matt grill → spec → tickets，但只保留一份canonical spec/plan |
| 研究/未知design | Bounded prototype/discovery | Verdict收斂後回到正式primary lifecycle |

Primary的意義是transition owner唯一。Optional helper可產生新artifact或discipline，不能建立第二套競爭的approval state。

## Risk-Scaled Workflow

| Tier | Typical scope | Required depth |
|---|---|---|
| `Tier S` | Docs、comments、mechanically verified low-risk edits | Fixed candidate、applicable deterministic checks和focused review；不必spawn每個semantic lens |
| `Tier M` | Normal feature/bug work | Primary lifecycle、applicable Core rules、completed Overlay facts、四個fixed review axes；risk lenses按change scope啟用 |
| `Tier H` | Money、identity、authorization、sensitive data、migrations、concurrency、external irreversible side effects、SLO-critical paths | 所有applicable risk lenses、explicit human risk acceptance、failure/migration/rollout/rollback/recovery evidence和whole-change review |

一個一行authorization改動仍是Tier H；一份400行純索引可能Tier S。Tier只縮放process/evidence投入，不能把`DAT-001`等applicable invariant從true改成false。

## Feature Entry

1. Brainstorm/grill change surface，指定Tier與applicable Core draft。
2. 補Overlay facts；critical missing fact不進spec approval。
3. Spec將rules轉成acceptance/failure criteria；plan/tickets映射implementation/evidence。
4. 在public seam做TDD與failure injection。
5. Fixed packet做四軸/applicable-lens review、fix/re-review、fresh verification。
6. Gate檢查findings、exceptions與rollout/recovery。

## Bug Entry

1. 用一套diagnosis loop建立可RED的最小reproduction，不同時逐字跑兩套debug skills。
2. 判斷escaped defect違反哪個Core/Overlay fact；若fact不存在，這也是root cause的一部分。
3. Regression test放在正確public seam，fix最小scope。
4. Review不只看patch，也看同類boundary與failure/observability/recovery。
5. 回寫Overlay、scenario matrix或Core（只有跨project義務才改Core）。

## Architecture Entry

先以Matt architecture report/domain-modeling/codebase-design找候選與stable seam，讓human選一個bounded outcome；再把它轉approved spec，進primary worktree/plan/execution/review gate。Architecture improvement不能以「code health」授權無界refactor；必須有可觀察leverage、migration與rollback boundary。

## Review-Only Entry

1. 固定fixed point/merge-base、HEAD和non-empty diff。
2. 收集spec、Core/Overlay、repo rules與fresh deterministic output。
3. 依Tier選fresh reviewer topology和risk lenses。
4. Finding遵守11-field contract；無evidence標needs-verification。
5. Controller驗證、去重但不mask，安排fix/re-review。
6. Reviewer不做final approval；delivery authority做go/no-go。

## When to Create a Wrapper Skill

只有以下條件同時大致成立才寫thin wrapper：

- 同一packet/schema/gate在多project或大量tasks重複；
- 手工組裝造成可觀察漏欄、錯base或stale evidence；
- input/output contract穩定且可測；
- wrapper只orchestrate upstream skills/artifacts，不複製其整份方法論；
- 有owner、version、pressure scenarios與distribution/refresh計畫。

Project threshold放Overlay，cross-project obligation放Core，一次性差異放task/spec。只有upstream trigger/hard gate/artifact/flow結構衝突且composition無法處理時才fork。

## Exception and Accepted-Risk Lifecycle

```text
proposed
  -> evidence reviewed
  -> authorized with expiry
  -> monitored
  -> removed OR renewed through a new decision
```

- **Proposed**：具名rule/finding、scope、impact、原因、controls與owner。
- **Evidence reviewed**：驗證impact與compensating controls，不用deadline壓力代替risk判斷。
- **Authorized with expiry**：只有rule允許且human有authority；Critical不可由Agent接受。
- **Monitored**：metric/alert/owner追蹤scope與controls，candidate/conditions改變重新review。
- **Removed/renewed**：修復後re-review並close；renewal是新decision，不是改expiry字串。

Expired exception自動成為open finding並阻擋下一次相關gate。Accepted-risk不是`not-applicable`，也不能從report刪除。

## Upstream Snapshot Refresh

上游pull/update後按固定procedure：

1. 記錄old/new full commit和tag/describe；
2. 檢查changed `README`、`SKILL`、prompt、script和distribution/plugin files；
3. 若使用knowledge graph/index，先re-index或以對應方式refresh source discovery；Markdown/config可用targeted file search；
4. 先更新snapshot facts，再更新interpretation/comparison，不反過來；
5. 重查lifecycle topology、artifacts、invocation、agent roles、review/fix/completion gates；
6. 執行documentation coverage/link checks與fixture runner；
7. 記錄local wrappers、Core/Overlay injection與host assumptions是否仍成立，需要migration還是無變更。

具體drift例子：Superpowers從`v5.1.0`到`v6.1.1`的task-review設計發生變化；當前`v6.1.1`是一位fresh task reviewer依序輸出Spec Compliance與Code Quality logical verdicts，再有final whole-branch review。舊版本拓撲只用來說明drift風險，不能當current fact。

Refresh record至少包含source diff範圍、受影響docs、verification output、reviewer與日期。

## Governance Cadence

| Cadence/trigger | Review |
|---|---|
| 每次upstream update | Snapshot、workflow topology、wrapper assumptions、docs/lab regression |
| 每個Tier H design | Risk classification、Core applicability、Overlay owners、evidence/rollout plan |
| 每次incident/escaped defect | Missing/incorrect fact、rule、test oracle、lens與gate，形成回寫 |
| 每月/季度依criticality | Deferred decisions、expired exceptions、stale links/owners、SLO/capacity/recovery evidence |
| 每次major architecture/platform change | Module/interface、dependency、compatibility、security、operations與tool commands |

Profile governance要有change log與approvers；不能讓每個Agent session自行改policy。

## Anti-Patterns

- 在`AGENTS.md`複製整份Core/Overlay，產生多個truth sources。
- 把所有30條rules標applicable，卻沒有fact或evidence。
- 用Tier S替一行security/data change降級。
- 讓AI填criticality、SLO、idempotency或fallback語義後自行批准。
- 同時跑兩套完整lifecycle，產生兩份spec/plan/review truth。
- 把wrapper寫成巨大fork，停止接收upstream修正。
- 用finding總數、平均score或tests green掩蓋Critical miss。
- Accepted-risk無owner/expiry，或到期後仍自動pass。
- Pull upstream後只改version number，不重查prompts/scripts/topology。

## Adoption Checklist

- [ ] Primary lifecycle與transition owner已選定。
- [ ] Core version/path與Project Overlay path可從`AGENTS.md`定位。
- [ ] Overlay最小facts有具名owners，不含blocking placeholders。
- [ ] Specs/plans引用applicable rule IDs與evidence。
- [ ] Tier S/M/H判定標準與升級authority已發布。
- [ ] AI Review protocol、finding schema與go/no-go authority已落地。
- [ ] Fixture runner與至少一個real-diff pilot已通過。
- [ ] Exception register、expiry handling與renewal authority可操作。
- [ ] Upstream snapshot refresh record/template已建立。
- [ ] Governance cadence、incident feedback loop與Profile owner已確認。
