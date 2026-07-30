# 00 - Agent Skills 心智模型

## 先給結論

Agent Skill 最適合被理解為「給 Coding Agent 使用的流程控制模組」：它把觸發條件、工作步驟、產物、gate、停止條件和工具使用方式寫成可重複載入的指令。它能顯著降低 Agent 跳步、猜測、無證據完成和上下文污染，但它不是專案需求、domain model、資料一致性設計或 production acceptance criteria 的替代品。

> **本專題判斷**：評價 skill library 時，應把 workflow discipline 與 production policy 分層，而不是用「有沒有一份很長的 checklist」判斷它是否 production-ready。

所以評估一個 skill 時，不應只問「它會不會寫程式」，而要問：

1. 它在防止哪種 failure mode？
2. 它要求什麼輸入，產出什麼 artifact？
3. 哪個 transition 被 hard gate 阻擋？
4. 它增加了什麼保證，又有哪些事實根本不知道？
5. 最後由什麼 evidence 支撐 delivery claim？

## 六層工程模型

```text
Harness and invocation
  -> Skill workflow
  -> Project policy
  -> Domain invariants
  -> Tools and evidence
  -> Delivery gate
```

| 層 | 核心問題 | 典型內容 | 缺少時會發生什麼 |
|---|---|---|---|
| Harness and invocation | skill 如何被發現、載入與執行？ | user/model trigger、plugin、command、tool permission、context | 文件存在但 Agent 沒讀，或讀了卻無法操作 |
| Skill workflow | Agent 應按什麼順序工作？ | brainstorm、spec、plan、TDD、debug、review、verify | 跳步、邊做邊猜、完成邊界不清 |
| Project policy | 這個 repository 認為什麼是合格變更？ | AGENTS.md、ADR、coding rules、review gate、SLO | Agent 只能套用泛化的工程直覺 |
| Domain invariants | 哪些業務事實永遠不能被破壞？ | 餘額守恆、狀態機、唯一性、授權邊界、事件順序 | 程式碼可讀且測試通過，仍可能做錯業務 |
| Tools and evidence | 如何證明主張？ | tests、typecheck、lint、build、migration rehearsal、runtime signals | reviewer 只有意見，沒有可重現證據 |
| Delivery gate | 誰根據哪些 evidence 決定 go/no-go？ | unresolved findings、accepted risk、rollback、human approval | 「完成」只是 Agent 的主觀敘述 |

這六層不是六個必然分開的檔案，而是六種責任。上游 skill library 通常主要覆蓋前兩層和部分 evidence discipline；production-ready 專案必須補齊後四層的具體答案。

## Skill 的檔案與載入機制

一個常見的 skill 入口是 `SKILL.md`：YAML frontmatter 提供 `name`、`description` 等 discovery metadata，正文才定義完整流程。Supporting references、prompt templates、scripts 和 examples 可以按需載入，避免所有細節永遠佔用 context。

需要分清三件事：

- **檔案規格**：skill 如何被描述和打包。
- **discovery policy**：host 何時根據 `description` 或明確指令選中它。
- **execution capability**：host 是否真的提供 shell、worktree、subagent、browser 或其他工具。

Markdown 寫了「MUST」不代表所有 harness 都會自動攔截違規行為；真正的強制力來自 system instruction、host integration、tool boundary，以及 Agent 是否正確讀取並遵循正文。因此 `description` 應回答「何時讀」，不能濃縮成一份讓 Agent 跳過正文的迷你 workflow。

常見 invocation 模式：

| 模式 | 誰決定使用 | 優點 | 風險 |
|---|---|---|---|
| User-invoked | 使用者明確點名 skill/command | 控制清楚，成本可預測 | 使用者必須知道 skill 存在 |
| Model-invoked | Agent 根據 trigger 自行載入 | 能在 failure mode 出現時及時介入 | discovery 描述不精確會漏載或過度載入 |
| Workflow-required | 上一個 skill 明確指定下一個 skill | transition 清楚、可形成 methodology | host 若不支援或 Agent 跳讀，鏈條會斷 |
| Wrapper/orchestrated | 本地流程組合上游 skills 與專案 artifacts | 能加入 project policy，又保留 upstream 更新 | wrapper 過厚會變成難維護的 fork |

## Trigger、Hard Gate 與停止條件

**Trigger** 是進入條件，例如「開始 creative work」、「出現 test failure」、「準備聲稱完成」。好的 trigger 描述可觀察情境，而不是只重述 skill 名稱。

**Hard gate** 是 transition rule：條件未滿足就不得進到下一階段。例如：

- design 未獲批准，不得 implementation；
- test 沒有先以正確原因失敗，不得聲稱完成 TDD 的 RED；
- 沒有 fresh verification output，不得聲稱完成；
- destructive discard 未取得明確確認，不得刪除 branch/worktree。

**停止條件** 同樣重要。Skill 若只描述 happy path，Agent 容易在資訊不足時自行補完。可靠流程會在以下情況停下：

- plan 有矛盾或缺少決定；
- bug 無法重現，沒有足夠 evidence；
- reviewer finding 無法從 diff 判定；
- tests 失敗且原因不在本 task；
- action 需要超出既有授權的外部變更。

Hard gate 增加的是「流程上不得越過的邊界」，不是自動證明 gate 前的內容正確。得到 spec approval，只代表人與 Agent 對文字達成一致，不代表該 spec 已包含所有 domain invariants。

## Reference、Artifact 與 Composition

三者解決不同的 context 問題：

- **Reference**：按需提供較重的知識，例如 review rubric、debug technique、平台差異。
- **Artifact**：把一次決策固定下來，例如 spec、plan、task brief、diff package、finding、test output。
- **Composition**：定義 artifact 如何從一個 skill 流向下一個 skill。

可以把 composition 看成 typed pipeline：

```text
conversation
  -> approved spec
  -> implementation plan
  -> task brief + code diff + implementer report
  -> review findings
  -> fixes + verification evidence
  -> delivery decision
```

如果只寫「接著做 review」，沒有固定 review base、requirements、project standards 和 evidence，那個 transition 就沒有穩定 interface。Fresh reviewer 的 context 再乾淨，也只能對不完整輸入做猜測。

## Skill 能保證什麼

遵循設計良好的 skill，通常可以提高以下保證：

- **順序保證**：先釐清、再規劃、再實作，而不是直接猜 code。
- **行為保證**：要求 RED-GREEN-REFACTOR、root-cause investigation 或 fresh verification。
- **artifact 保證**：關鍵決策不只留在對話裡。
- **context hygiene**：implementer、reviewer 和 controller 接收 bounded context。
- **separation of duties**：實作者不能單獨批准自己的變更。
- **failure visibility**：遇到不確定、test failure 或 disputed feedback 時有停止/回退路徑。

這些是 workflow guarantees，不是業務正確性的充分條件。

## Skill 不能保證什麼

Generic skill 不知道以下專案事實，除非輸入明確提供：

- 哪些寫入必須在同一 transaction；
- 哪個 consistency model 或 isolation level 才正確；
- idempotency key 的 scope、retention 和 payload-conflict policy；
- external dependency 的總 time budget、retry 前提和 fallback 語義；
- API/event/schema 必須相容多久；
- 哪些資料敏感、誰有授權、保留多久；
- latency、throughput、capacity、RPO、RTO 和 SLO；
- 如何 deploy、rollback、forward-recover 和 reconcile。

同樣地，TDD 只證明「被寫下來的測試」驅動了實作，不能證明測試代表完整需求；code review 只對收到的 diff、spec 和 rules 負責，不能從空白推導真實業務。

## 為什麼 Workflow Discipline 不等於 Production Policy

使用 skill 後的程式碼有時看起來「不夠 production-grade」，通常有三類原因：

1. **YAGNI 的刻意約束**：workflow 鼓勵先完成已批准的最小需求，不主動加入未要求的抽象、fallback 或 framework。
2. **資訊邊界**：project 沒提供 consistency、capacity、compatibility 或 recovery 事實，Agent 不應假裝知道。
3. **驗收邊界過窄**：spec 和 tests 只覆蓋 happy path，reviewer 就缺少判斷 edge cases 的規則和 evidence。

所以正確補法不是把所有 upstream skill 全面魔改成一份巨大 checklist，而是分層：

```text
upstream workflow
  + cross-project Core Profile
  + project-specific Overlay
  + executable evidence
  + review/delivery gate
```

當差異只是本專案的 timeout、invariant 或 module convention，寫進 Project Overlay；跨專案反覆成立的要求放進 Core Profile；只有重複的 artifact/gate 編排才值得寫薄 wrapper；upstream 的 trigger、hard gate、artifact contract 或 flow order 根本衝突時才考慮 fork。

## 如何閱讀後續章節

閱讀每個重點 skill 時，固定追蹤 11 個問題：Failure mode、trigger/preconditions、inputs、outputs、internal flow、composition、guarantees、non-guarantees、when not to use、production gap、source anchors。

先讀兩庫 workflow map，再讀個別 skill。這能避免把同名 skill 當成同一責任，也能看出哪些是主線、條件分支、quality foundation 或 meta capability。

## 一句話總結

Agent Skill 管的是「Agent 應如何可靠地工作」；production engineering 還必須明確告訴它「本專案什麼絕對不能錯，以及要用什麼證據證明沒有錯」。
