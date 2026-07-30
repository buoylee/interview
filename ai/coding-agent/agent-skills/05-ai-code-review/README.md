# AI Code Review：從第二雙眼睛到工程決策系統

## 先給結論

AI reviewer既不是 linter，也不是 oracle。它的價值不是「再看一次 code」，而是把固定 candidate、獨立 semantic lenses、可重現 evidence、明確 severity、fix/re-review 和 delivery decision接成一個可稽核的控制迴路。

有用的 AI Code Review 至少要分清：

- reviewer看的是哪個固定 diff和repository state；
- 每個 finding根據哪條rule、哪段evidence提出；
- finding是已證實 defect，還是需要額外verification的claim；
- 哪些問題已修、已重審、被駁回或由有權者接受風險；
- 最後是誰、根據什麼 evidence做 go/no-go。

## 這個專題解決什麼

- 為什麼「請另一個 Agent review」仍容易漏掉 data consistency、fallback、compatibility和operability問題？
- Superpowers `v6.1.1` 的 task review、whole-branch review與receiving feedback實際怎麼運作？
- Matt Pocock `code-review` 的 fixed base、Standards/Spec兩軸解決什麼，又沒有解決什麼？
- 如何防止 reviewer把 spec pass、style smell、critical correctness混成一個模糊總分？
- 如何把 finding從意見變成可驗證、可追蹤、可阻擋交付的工程claim？
- 如何用故意藏有production defect的fixtures測試 review protocol，而不是只相信prompt看起來嚴謹？

## 閱讀順序

1. [AI Code Review 心智模型](./01-mental-model.md)：先理解candidate truth、review claim與delivery decision。
2. [兩個 Skill 庫的 Code Review 機制](./02-two-library-mechanisms.md)：分開重建兩套upstream設計，不混成一條想像流程。
3. [Production AI Code Review Protocol](./03-production-review-protocol.md)：使用packet、axes/lenses、11-field finding與go/no-go gate。
4. [如何評估 AI Code Review](./04-evaluation-and-lab.md)：固定實驗矩陣、metrics和promotion criteria。
5. [Evaluation Lab](./lab/README.md)：執行六組fixtures並記錄blind review trial。
6. [Trial Result Template](./lab/results-template.md)：保存raw/normalized findings、answer-key mapping、成本與決策。

## 按角色跳讀

| 角色 | 先讀 | 核心責任 |
|---|---|---|
| Implementer | [心智模型](./01-mental-model.md#context-isolation-and-confirmation-bias) | self-review作preflight，提供完整report/evidence，但不能批准自己 |
| Reviewer | [Review packet](./01-mental-model.md#review-packet-as-an-interface) | 對固定candidate、明確axis和rules提出可驗證claims |
| Controller | [兩庫機制](./02-two-library-mechanisms.md) | 固定base/head、隔離context、處理finding lifecycle與re-review |
| Project owner | [Human responsibility](./01-mental-model.md#human-responsibility) | 提供project invariants、決定exception和不可自動化的go/no-go |
| Review operator | [Evaluation Lab](./lab/README.md) | 保持reviewer/evaluator隔離，執行deterministic gate並保存trial |

## Descriptive and Normative Boundary

本專題把兩種內容明確分開：

- **Descriptive**：只描述 pinned upstream source的review topology、artifacts、prompts和rules。
- **Normative**：由本專題定義的 production review protocol、finding contract、risk lenses和delivery gate。

上游使用「Critical」或「review」等詞，不代表已自動採用本專題的severity、evidence或approval semantics；同名概念必須看完整contract。

## Lab Entry

[Evaluation Lab](./lab/README.md)提供六個Python stdlib fixtures：data consistency、idempotency、timeout/retry/fallback、interface coupling、error handling和misleading tests。每個buggy版本都能通過可見project tests，但會被獨立verification oracle揭露；reviewer必須先從spec、overlay和diff提出finding，freeze初審後才由evaluator解封oracle與[answer key](./lab/answer-key/)。

Default delivery gate：

```bash
python3 ai/coding-agent/agent-skills/05-ai-code-review/lab/run-fixtures.py
```

Runner不呼叫provider；AI trial在現有Coding Agent harness中執行並複製[結果模板](./lab/results-template.md)。

## Success Boundary

成功不是「AI提出很多建議」，也不是「所有findings都接受」。成功邊界是：

1. candidate固定且可重建；
2. applicable requirements和risk lenses已提供；
3. findings有location、rule、impact與evidence；
4. 無法從diff證實的claim被標為needs-verification，不假裝確定；
5. blocking findings已修復並re-review，或由明確authority接受風險；
6. go/no-go只根據當前evidence，不由implementer自我宣告。

AI Code Review的產物是可審計的交付決策，不是字數很多的review report。
