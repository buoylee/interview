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
| **Normative** | 我們的專案應要求什麼？ | 後續 AI review protocol、Production Engineering Profile、adoption gate | 必須有owner、applicability、evidence和exception process |

文件中的「source 明示」屬 Descriptive；跨庫差異屬 Comparative；標示為「本專題判斷」或後續本地規則的內容屬 Normative。這個分層可避免把作者原意、我們的推論和專案政策混成一件事。

## 線性閱讀順序

1. [Agent Skills 心智模型](./00-agent-skills-mental-model.md)：先建立六層模型、trigger、hard gate、artifact與production boundary。
2. [兩個 Skill 庫的 Workflow 全景](./01-two-libraries-workflow-map.md)：先看主線與分支，不逐篇迷失。
3. [Superpowers 學習入口](./02-superpowers/README.md)：讀方法論、14 個 skills和邊界。
4. [Matt Pocock Skills 學習入口](./03-matt-pocock/README.md)：讀主流程、常用 8 + 2 + 2和完整索引。
5. [兩庫差異與組合](./04-comparison-and-composition.md)：決定 primary lifecycle和最小充分組合。

### Superpowers 章節

- [方法論與生命週期](./02-superpowers/01-methodology-and-lifecycle.md)
- [14 Skills Guide](./02-superpowers/02-all-skills-guide.md)
- [強項與邊界](./02-superpowers/03-strengths-and-boundaries.md)

### Matt Pocock 章節

- [主流程](./03-matt-pocock/01-main-flow.md)
- [8 個核心 Skills Guide](./03-matt-pocock/02-core-skills-guide.md)
- [品質基礎、條件能力與邊界](./03-matt-pocock/03-quality-foundations-and-boundaries.md)

## 按任務跳讀

| 你現在要做什麼 | 先讀 | 得到什麼 |
|---|---|---|
| 對兩庫先有整體畫面 | [Workflow 全景](./01-two-libraries-workflow-map.md) | 兩條主線、分支、同名不同責任 |
| 建立嚴格 feature lifecycle | [Superpowers 方法論](./02-superpowers/01-methodology-and-lifecycle.md) | design、worktree、plan、execution、review、verification gates |
| 查某個 Superpowers skill | [14 Skills Guide](./02-superpowers/02-all-skills-guide.md) | 11 欄contract、guarantee與production gap |
| 只學 Matt最常用部分 | [Matt 8 + 2 + 2](./03-matt-pocock/README.md#8--2--2-選擇模型) | 核心workflow、quality foundations和conditional能力 |
| 改善domain words/interface/seam | [品質基礎](./03-matt-pocock/03-quality-foundations-and-boundaries.md) | domain modeling、codebase design與architecture boundary |
| 判斷兩庫怎麼搭配 | [差異與組合](./04-comparison-and-composition.md) | 四種最小組合與conflict rules |
| 追查舊三庫報告 | [Legacy Archive](./_archive/legacy-three-library-report/README.md) | 只作歷史背景，不作當前source of truth |

## Source Snapshots

| Library | Local source | Pinned snapshot | Verified |
|---|---|---|---|
| `obra/superpowers` | `/Users/buoy/Development/gitrepo/superpowers` | `d884ae04edebef577e82ff7c4e143debd0bbec99` (`v6.1.1`) | `2026-07-21` |
| `mattpocock/skills` | `/Users/buoy/Development/gitrepo/skills` | `ed37663cc5fbef691ddfecd080dff42f7e7e350d` (`v1.1.0-40-ged37663`) | `2026-07-21` |

Snapshot facts包括 skill數量、目錄分類、agent topology、scripts、install/distribution和prompt wording。上游更新後，應重新讀 changed source並更新 pin，不以本頁替代當前 upstream。

## 目前已完成的範圍

目前 foundation layer 已完成：

- Agent Skill 的六層心智模型與 production boundary；
- Superpowers `v6.1.1` 的完整 lifecycle和14個skills；
- Matt Pocock snapshot的完整41-skill索引，深讀最常用 `8 + 2 + 2`；
- 兩庫沿十個軸的比較、四種最小充分組合與衝突優先序；
- 舊版三庫報告的獨立archive，避免與當前source混用。

本層刻意先回答「上游提供什麼、差在哪裡、如何組合」，不假裝已經定義本專案的production gate。

## 後續規範層

下一階段會在此 foundation上加入兩個 Normative 層，目前先不建立尚不存在的導航連結：

1. **AI Code Review 專題**：定義 review inputs、independent axes、risk lenses、finding schema、evidence verification、aggregation、fix/re-review與go/no-go，並以六組可執行 Python fixtures驗證 reviewer是否真的找得到production defects。
2. **Production Engineering Profile**：建立跨語言 Core Profile加Project Overlay，覆蓋data consistency、resilience、module/interface、compatibility、security、performance、observability、testing和delivery/recovery，再說明何時加規範、寫薄wrapper或fork upstream。

它們完成後，這個入口會改成可直接跳讀的live navigation；在那之前，以本頁列出的foundation文件為已完成source of truth。
