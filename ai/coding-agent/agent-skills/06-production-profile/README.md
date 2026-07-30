# Production Engineering Profile

## Policy Status

本section是本repository採用的Normative engineering policy，建立在兩庫Descriptive分析與AI Review protocol之上。它不是任何upstream skill作者的原文，也不把generic best practices假裝成每個project都適用的fact。

## 先給結論

Superpowers與Matt Pocock Skills能提高process reliability，但不能推導project從未提供的business invariants、criticality、data sensitivity、consistency semantics、external dependency budgets、SLOs、compatibility commitments或recovery objectives。

Production-ready必須由四層共同成立：

```text
universal engineering baseline
  + project-specific invariants
  + executable evidence
  + delivery gate
```

## Why This Layer Exists

「請寫production-grade code」不是可執行要求。它沒有回答：哪個state不能部分提交、retry是否安全、fallback代表什麼business state、哪個interface必須相容、哪種資料敏感、允許多少latency、怎麼reconcile或rollback。

Generic skill若自行補答案會over-engineer或猜錯；若只做已明示happy path，又會看起來不夠縝密。本Profile把跨project底線與本project facts分開，使spec、plan、implementation、review和delivery都能引用同一規則。

## The Four-Layer Formula

- **Universal engineering baseline**：跨語言反覆成立的最低要求，以stable rule IDs維護。
- **Project-specific invariants**：由Project Overlay填入本系統的domain、data、dependency、SLO、compatibility和recovery facts。
- **Executable evidence**：commands、behavior/failure tests、runtime proof、migration/rollback rehearsal和authorized risk record。
- **Delivery gate**：根據applicability、severity、fresh evidence與unresolved findings做go/no-go。

## Documents in This Section

1. [Production Quality Model](./01-production-quality-model.md)：四層公式、applicability、evidence、severity與rule schema。
2. [Cross-Language Core Profile](./02-core-profile.md)：10個domains、30條stable rules與七欄contract。
3. [Project Overlay Template](./03-project-overlay-template.md)：把project-specific facts、evidence和owners填成可引用policy。
4. [把Profile接進Agent Skills](./04-integrating-with-skills.md)：stage-by-stage injection與Overlay/Core/wrapper/fork決策。
5. [Adoption Playbook](../07-adoption-playbook.md)：risk tiers、project instructions、exception與upstream refresh。

## How to Use Core and Overlay

Core回答「所有採用本Profile的project最低應考慮什麼」；Overlay回答「這個project的確切答案是什麼」。

```text
Core rule: remote calls need bounded time and failure semantics
Overlay fact: total budget 400 ms; 2 × 150 ms attempts; only read operation retries;
              timeout returns unavailable, never empty-success; metric names are fixed
```

每個change先判applicable Core rules，再從Overlay取得具體values。Overlay不能用「follow best practices」代替fact；Core也不應塞入單一stack或service的magic number。

## Relationship to AI Code Review

[AI Code Review Protocol](../05-ai-code-review/03-production-review-protocol.md)把Core rule IDs與Overlay facts放入review packet。Findings引用確切rule、impact和evidence；缺少Overlay fact時標needs-verification或阻擋相關pass claim，不由reviewer自行發明。

Profile定義「什麼才合格」；review protocol定義「如何獨立判斷、驗證、修復與放行」。

## What This Does Not Replace

本Profile不替代：

- product/domain owner對business behavior的決策；
- threat model、privacy/legal review或specialist security assessment；
- architecture decision與stack-specific standards；
- capacity test、migration rehearsal、incident runbook或on-call ownership；
- human對exception、release timing和irreversible risk的authority。

它提供共同contract，不宣稱一份checklist可以自動製造production safety。
