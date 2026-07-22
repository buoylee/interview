# Agent Skills：Workflow、Code Review 與 Production Engineering

## 先給結論

這是一條從「看懂兩個 skill library」走到「建立自己的 production-grade Agent delivery system」的學習路徑。

先分清三層：

1. **上游 skills** 規範 Agent 如何工作；
2. **本地 engineering policy** 告訴 Agent 本專案什麼不能錯；
3. **evidence 與 gate** 證明變更是否可以交付。

Superpowers 更像 end-to-end methodology；Matt Pocock Skills 更像 composable engineering toolset。兩者都能提高流程品質，但都不能替代 project invariants、production acceptance、risk review 和 rollout/recovery決策。

## 這條學習路徑回答什麼

- Agent Skill 到底是 prompt、workflow、policy，還是 runtime enforcement？
- Superpowers 是否有一條規範流程，14 個 skills各自防止什麼 failure mode？
- Matt Pocock Skills太多時，哪些 8 + 2 + 2 最值得深讀，其他 skills如何定位？
- 兩個庫在 trigger、artifact、context、TDD、debug、review、verification和control上有什麼差異？
- 為什麼使用 skills後的 code仍可能缺 data consistency、fallback、encapsulation、readability、reuse、interface orientation和decoupling？
- 應該改 upstream skills、fork、寫 wrapper，還是加入自己的 project policy？
- AI Code Review如何從「兩個 Agent給意見」升級成有 evidence、severity、verification、fix/re-review和go/no-go的工程 gate？

## Descriptive、Comparative、Normative 三種文件

| 類型 | 回答的問題 | 本路徑中的例子 | 閱讀時的態度 |
|---|---|---|---|
| **Descriptive** | 上游 source目前實際寫了什麼？ | 兩庫 lifecycle、skill contracts、snapshot inventory | 回到 pinned source驗證，不把版本事實永恆化 |
| **Comparative** | 在相同軸上，兩套設計如何不同？ | methodology/toolset、control、artifacts、review topology、cost | 比責任與trade-off，不用名稱相似度代替分析 |
| **Normative** | 我們的專案應要求什麼？ | AI review protocol、Production Engineering Profile、adoption gate | 必須有owner、applicability、evidence和exception process |

文件中的「source 明示」屬 Descriptive；跨庫差異屬 Comparative；標示為「本專題判斷」或後續本地規則的內容屬 Normative。這個分層可避免把作者原意、我們的推論和專案政策混成一件事。

## 線性閱讀順序

1. **Foundation** — [00 Agent Skills 心智模型](./00-agent-skills-mental-model.md)：六層模型、trigger、hard gate、artifact與production boundary。
2. **Descriptive / Comparative** — [01 兩庫 Workflow 全景](./01-two-libraries-workflow-map.md)：主線、分支和同名不同責任。
3. **Descriptive** — [02 Superpowers](./02-superpowers/README.md)：`v6.1.1`方法論、14個skills和邊界。
4. **Descriptive** — [03 Matt Pocock Skills](./03-matt-pocock/README.md)：snapshot主流程、常用`8 + 2 + 2`和完整索引。
5. **Comparative** — [04 差異與組合](./04-comparison-and-composition.md)：primary lifecycle、最小組合與conflict rules。
6. **Descriptive + Normative** — [05 AI Code Review](./05-ai-code-review/README.md)：upstream機制、production protocol、evaluation lab。
7. **Normative** — [06 Production Engineering Profile](./06-production-profile/README.md)：四層quality model、30條Core rules、Overlay和integration。
8. **Normative** — [07 Adoption Playbook](./07-adoption-playbook.md)：risk-scaled採用、exceptions、governance與upstream refresh。

### Superpowers 章節

- [方法論與生命週期](./02-superpowers/01-methodology-and-lifecycle.md)
- [14 Skills Guide](./02-superpowers/02-all-skills-guide.md)
- [強項與邊界](./02-superpowers/03-strengths-and-boundaries.md)

### Matt Pocock 章節

- [主流程](./03-matt-pocock/01-main-flow.md)
- [8 個核心 Skills Guide](./03-matt-pocock/02-core-skills-guide.md)
- [品質基礎、條件能力與邊界](./03-matt-pocock/03-quality-foundations-and-boundaries.md)

### AI Code Review 章節

- [專題入口](./05-ai-code-review/README.md)
- [AI Code Review 心智模型](./05-ai-code-review/01-mental-model.md)
- [兩個 Skill 庫的 Code Review 機制](./05-ai-code-review/02-two-library-mechanisms.md)
- [Production Review Protocol](./05-ai-code-review/03-production-review-protocol.md)
- [Evaluation Method](./05-ai-code-review/04-evaluation-and-lab.md)
- [Executable Lab](./05-ai-code-review/lab/README.md)

### Production Engineering Profile 章節

- [Profile入口](./06-production-profile/README.md)
- [Production Quality Model](./06-production-profile/01-production-quality-model.md)
- [30條Core Rules](./06-production-profile/02-core-profile.md)
- [Project Overlay Template](./06-production-profile/03-project-overlay-template.md)
- [Skills Integration](./06-production-profile/04-integrating-with-skills.md)
- [Adoption Playbook](./07-adoption-playbook.md)

## 按任務跳讀

| 你現在要做什麼 | 先讀 | 得到什麼 |
|---|---|---|
| 對兩庫先有整體畫面 | [Workflow 全景](./01-two-libraries-workflow-map.md) | 兩條主線、分支、同名不同責任 |
| 建立嚴格 feature lifecycle | [Superpowers 方法論](./02-superpowers/01-methodology-and-lifecycle.md) | design、worktree、plan、execution、review、verification gates |
| 查某個 Superpowers skill | [14 Skills Guide](./02-superpowers/02-all-skills-guide.md) | 11 欄contract、guarantee與production gap |
| 只學 Matt最常用部分 | [Matt 8 + 2 + 2](./03-matt-pocock/README.md#8--2--2-選擇模型) | 核心workflow、quality foundations和conditional能力 |
| 改善domain words/interface/seam | [品質基礎](./03-matt-pocock/03-quality-foundations-and-boundaries.md) | domain modeling、codebase design與architecture boundary |
| 判斷兩庫怎麼搭配 | [差異與組合](./04-comparison-and-composition.md) | 四種最小組合與conflict rules |
| 建立AI review的工程模型 | [AI Code Review 心智模型](./05-ai-code-review/01-mental-model.md) | candidate truth、review claim、delivery decision與八階段loop |
| 比較兩庫review機制 | [兩庫 Code Review 機制](./05-ai-code-review/02-two-library-mechanisms.md) | task/branch gate與Standards/Spec兩軸的真實差異 |
| 新feature | [Adoption Feature Entry](./07-adoption-playbook.md#feature-entry) | 按Tier把Core/Overlay接入primary lifecycle |
| Bug/incident | [Adoption Bug Entry](./07-adoption-playbook.md#bug-entry) | diagnosis、regression、Profile回寫與review |
| Review-only | [Production Review Protocol](./05-ai-code-review/03-production-review-protocol.md) | fixed packet、axes/lenses、finding與go/no-go |
| Architecture improvement | [Architecture Entry](./07-adoption-playbook.md#architecture-entry) | bounded discovery後回正式delivery lifecycle |
| Production hardening | [Core + Overlay](./06-production-profile/README.md) | universal obligations加project facts/evidence/gate |
| Upstream refresh | [Snapshot Refresh](./07-adoption-playbook.md#upstream-snapshot-refresh) | 重讀source、重查topology與local assumptions |
| 追查舊三庫報告 | [Legacy Archive — historical only](./_archive/legacy-three-library-report/README.md) | 只作歷史背景，不作當前source of truth |

## Source Snapshots

| Library | Local source | Pinned snapshot | Verified |
|---|---|---|---|
| `obra/superpowers` | `/Users/buoy/Development/gitrepo/superpowers` | `d884ae04edebef577e82ff7c4e143debd0bbec99` (`v6.1.1`) | `2026-07-21` |
| `mattpocock/skills` | `/Users/buoy/Development/gitrepo/skills` | `ed37663cc5fbef691ddfecd080dff42f7e7e350d` (`v1.1.0-40-ged37663`) | `2026-07-21` |

Snapshot facts包括 skill數量、目錄分類、agent topology、scripts、install/distribution和prompt wording。上游更新後，應重新讀 changed source並更新 pin，不以本頁替代當前 upstream。

## 目前已完成的範圍

完整學習與規範層已完成：

- Agent Skill 的六層心智模型與 production boundary；
- Superpowers `v6.1.1` 的完整 lifecycle和14個skills；
- Matt Pocock snapshot的完整41-skill索引，深讀最常用 `8 + 2 + 2`；
- 兩庫沿十個軸的比較、四種最小充分組合與衝突優先序；
- AI Code Review的decision-system心智模型、production protocol、evaluation方法與六fixture executable lab；
- Production Quality Model、30條Core rules、Project Overlay template與skills integration；
- Tier S/M/H adoption、exception lifecycle、governance與upstream refresh；
- 舊版三庫報告的獨立archive，避免與當前source混用。

Lab delivery gate：

```bash
python3 ai/coding-agent/agent-skills/05-ai-code-review/lab/run-fixtures.py
```

這份track提供可採用baseline，不替project owner填入真實Overlay facts，也不替human承擔Critical/Important risk acceptance。
