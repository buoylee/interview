# Matt Pocock Skills 學習入口

| Source field | Value |
|---|---|
| Library | `mattpocock/skills` |
| Local path | `/Users/buoy/Development/gitrepo/skills` |
| Snapshot | `ed37663cc5fbef691ddfecd080dff42f7e7e350d` (`v1.1.0-40-ged37663`) |
| Verified | `2026-07-21` |
| Primary sources | `README.md`, `skills/*/SKILL.md`, `.agents/adr/` where distribution matters |

## 先給結論

Matt Pocock 的庫刻意不把整個開發流程收編成單一 framework。它提供 small、adaptable、composable skills，讓使用者保留對 issue tracker、context boundary、prototype、implementation 和 review 的控制。

本學習路徑不平均深挖 41 個 snapshot skills，而是集中在最能形成日常 engineering flow、回答 code quality問題的 `8 + 2 + 2`：八個核心 workflow、兩個品質 vocabulary foundation、兩個條件式能力。

## Source Snapshot

本地快照共有 41 個 `SKILL.md`，分布在 `engineering`、`productivity`、`in-progress`、`deprecated`、`misc`、`personal`。這是 `2026-07-21` 對 commit `ed37663` 的 snapshot fact，不是永久數量。

README 將 skills 分成 user-invoked 和 model-invoked：user-invoked負責 orchestration，model-invoked可由使用者或 Agent按情境觸發並提供 reusable discipline。安裝可走 skills.sh複製到 project，或 Claude Code plugin的managed bundle；其他 harness/distribution狀態可能更新，應回 pinned source重查。

## 為什麼不深挖全部 41 個 Skills

「全都逐篇翻譯」會把成熟主線、個人工具、misc setup、in-progress experiments和deprecated skills放在同一重要度，反而看不出作者實際推薦的 flow。

本次深度選擇根據：

1. 作者在 README/`ask-matt` 明示的 main flow和on-ramp；
2. feature、bug、review、handoff等跨專案高復用場景；
3. 本專題關心的 domain invariant、interface、test seam、architecture和production gap。

它不是使用遙測、下載量或客觀 popularity ranking。

## 8 + 2 + 2 選擇模型

| Depth | Skills | 為什麼重要 |
|---|---|---|
| 8 core | `grill-with-docs`, `to-spec`, `to-tickets`, `implement`, `tdd`, `code-review`, `diagnosing-bugs`, `handoff` | 從 alignment、artifact conversion到 implementation、review、bug on-ramp和跨 session continuity |
| 2 foundations | `domain-modeling`, `codebase-design` | 提供 ubiquitous language、invariant、deep module、interface、seam、leverage、locality等品質語言 |
| 2 conditional | `prototype`, `improve-codebase-architecture` | 分別處理「紙上無法回答的 design question」與「既有 codebase entropy」 |

## Prerequisite and Router

### `setup-matt-pocock-skills`

這是每個 repository 首次使用 engineering flow 前的 user-invoked prerequisite。它探索並確認 issue tracker、triage label vocabulary、domain docs layout，然後更新現有 `CLAUDE.md` 或 `AGENTS.md` 的 `## Agent skills` block和 `docs/agents/*.md`。它是 prompt-driven setup，不是可盲跑的 deterministic installer。

### `ask-matt`

這是 user-invoked router。它解釋 main flow、bugs/triage/wayfinder on-ramps、codebase health、underlying vocabulary、handoff/compact差異和 standalone skills。它幫助選路，不是每次交付都經過的 stage。

## 建議閱讀順序

1. [主流程](./01-main-flow.md)：先看 idea如何變成 spec/tickets/implementation/review。
2. [8 個核心 Skills](./02-core-skills-guide.md)：理解 artifact和control boundary。
3. [品質基礎、條件式能力與邊界](./03-quality-foundations-and-boundaries.md)：回答 interface、decoupling、testability和production缺口。
4. 回到 [兩庫 Workflow 全景](../01-two-libraries-workflow-map.md)決定怎麼與 Superpowers 組合。

## Complete Snapshot Inventory

| Skill | Source bucket | Coverage | One-line purpose | Why this depth |
|---|---|---|---|---|
| `ask-matt` | engineering | intro-only | 路由到 main flow、on-ramp或standalone能力 | 入口重要，但不執行交付工作 |
| `code-review` | engineering | deep-core | 固定三點diff，平行做 Standards/Spec兩軸review | AI Code Review專題的主要來源 |
| `codebase-design` | engineering | deep-foundation | 用deep module/interface/seam vocabulary設計codebase | 直接回答封裝、解耦、testability |
| `diagnosing-bugs` | engineering | deep-core | 先建立tight red-capable loop，再最小化、假設、instrument、修復 | 日常bug on-ramp且evidence要求強 |
| `domain-modeling` | engineering | deep-foundation | 維護精確domain glossary和必要ADR | 提供invariant與命名基礎 |
| `grill-with-docs` | engineering | deep-core | 用grilling + domain-modeling澄清並同步docs | 作者main flow起點 |
| `implement` | engineering | deep-core | 以pre-agreed seams驅動TDD、review、commit | main flow執行器 |
| `improve-codebase-architecture` | engineering | deep-conditional | 找deepening opportunities並以visual report + grilling選案 | 回答既有architecture退化 |
| `prototype` | engineering | deep-conditional | 用throwaway logic/UI code回答一個design question | main flow重要detour，但非每task適用 |
| `research` | engineering | index-only | 背景agent讀primary sources並留下cited artifact | 有用但不屬本次主交付鏈 |
| `resolving-merge-conflicts` | engineering | index-only | 依兩邊primary intent逐hunk完成merge/rebase | 專門Git故障路徑 |
| `setup-matt-pocock-skills` | engineering | intro-only | 設定tracker、triage vocabulary和domain docs | repository prerequisite，不是日常stage |
| `tdd` | engineering | deep-core | 在已確認seam做vertical red-green slices | implementation feedback loop |
| `to-spec` | engineering | deep-core | 把既有conversation合成spec並發布 | main flow durable artifact |
| `to-tickets` | engineering | deep-core | 把工作拆成tracer-bullet tickets與blocking edges | multi-session decomposition |
| `triage` | engineering | index-only | 讓外來issue經角色state machine成為agent-ready | 是on-ramp，但本次不深挖issue governance |
| `wayfinder` | engineering | index-only | 用decision-ticket map探索超大模糊工作 | 認知成本高、非一般feature flow |
| `grill-me` | productivity | index-only | 無codebase時做stateless relentless interview | 主線使用有docs版本 |
| `grilling` | productivity | index-only | `grill-me`/`grill-with-docs`底層可重用interview loop | 由wrapper間接說明 |
| `handoff` | productivity | deep-core | 把conversation壓成temporary handoff給fresh agent | context/session bridge |
| `teach` | productivity | index-only | 用current directory做跨session教學workspace | 不屬engineering delivery主線 |
| `writing-great-skills` | productivity | index-only | 寫skill的vocabulary和principles | 本專題不建立Matt skill |
| `batch-grill-me` | in-progress | index-only | 批次化grilling實驗 | maturity尚在in-progress |
| `claude-handoff` | in-progress | index-only | Claude-specific handoff實驗 | 已選成熟`handoff`作主線 |
| `loop-me` | in-progress | index-only | 迴圈式工作實驗 | maturity尚在in-progress |
| `setup-ts-deep-modules` | in-progress | index-only | TypeScript deep-module setup實驗 | language-specific且未成熟 |
| `to-questionnaire` | in-progress | index-only | 把內容轉成questionnaire | 非核心engineering flow |
| `wizard` | in-progress | index-only | wizard式互動流程實驗 | maturity尚在in-progress |
| `writing-beats` | in-progress | index-only | writing workflow的beat拆解 | 非code delivery主線 |
| `writing-fragments` | in-progress | index-only | writing fragment workflow | 非code delivery主線 |
| `writing-shape` | in-progress | index-only | writing shape workflow | 非code delivery主線 |
| `design-an-interface` | deprecated | index-only | 舊interface design流程 | 已由`codebase-design` vocabulary取代/涵蓋 |
| `qa` | deprecated | index-only | 舊QA流程 | deprecated，不作當前建議 |
| `request-refactor-plan` | deprecated | index-only | 舊refactor planning流程 | deprecated且有新architecture能力 |
| `ubiquitous-language` | deprecated | index-only | 舊ubiquitous-language流程 | 由`domain-modeling`取代/深化 |
| `git-guardrails-claude-code` | misc | index-only | Claude Code Git guardrails setup | host-specific setup，不是主線方法 |
| `migrate-to-shoehorn` | misc | index-only | 特定migration helper | 專門工具，復用面窄 |
| `scaffold-exercises` | misc | index-only | 建立教學exercise骨架 | 教學產物，不是production workflow |
| `setup-pre-commit` | misc | index-only | 設置pre-commit feedback loop | 有用的mechanical setup但非核心流程 |
| `edit-article` | personal | index-only | 個人文章編輯workflow | personal scope |
| `obsidian-vault` | personal | index-only | 個人Obsidian工作流 | personal scope |

## Snapshot 限制

Bucket 是來源目錄，不是正式semantic version maturity保證；`in-progress`/`deprecated`的含義以當前repo為準。上游新增、搬移、改 invocation或 plugin distribution後，要重新產生 inventory，而不是只修改總數。
