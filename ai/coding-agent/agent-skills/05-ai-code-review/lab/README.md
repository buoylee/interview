# AI Code Review Evaluation Lab

## Purpose

本lab用小型、可執行、故意含production defect的Python stdlib fixtures，測試review strategy能否在visible project tests通過時，仍從spec、Project Overlay和diff提出正確finding。

它是protocol evaluation harness，不是provider client：deterministic runner只檢查fixture truth table、files、diff freshness和answer-key structure；AI review在現有Coding Agent harness中人工啟動，再把結果複製到`results-template.md`。

## Directory Contract

```text
lab/
├── README.md
├── run_lab.py
├── results-template.md
├── fixtures/
│   └── <NN-slug>/
│       ├── spec.md
│       ├── project-overlay.md
│       ├── before.py
│       ├── buggy.py
│       ├── fixed.py
│       ├── project_test.py
│       ├── verification_test.py
│       └── change.diff
└── answer-key/
    └── <NN-slug>.md
```

每個fixture必須self-contained，只使用Python standard library，不import其他fixture。`before.py`是change前candidate；`buggy.py`是initial review target；`fixed.py`是re-review target；兩個test files透過runner指定candidate module，不靠修改tracked files。

`change.diff`必須等於runner以`before.py`與`buggy.py`產生的unified diff。它是review packet的一部分，不是答案。

## Reviewer Input Boundary

Initial reviewer只可收到：

- `spec.md`；
- `project-overlay.md`；
- `change.diff`；
- `buggy.py`；
- visible `project_test.py`的command與passing output。

Reviewer可以依protocol產生四軸與applicable lens findings，但不得自行探索evaluator-only files。若review condition是without Overlay，evaluator從packet拿掉`project-overlay.md`並在result record註明；不是讓reviewer知道被隱藏內容。

## Evaluator-Only Boundary

以下內容在initial review frozen前只由evaluator/runner存取：

- `fixed.py`；
- `verification_test.py`；
- `answer-key/`下對應文件。

Initial findings、verdict與cost/latency先原樣保存，才解封answer key。Reviewer若提前讀取任何evaluator-only內容，該run標為contaminated，只能作calibration，不能計入blind metrics。

Re-review階段可向reviewer提供`fixed.py`及新的before-to-fixed diff，但仍不提供verification oracle或answer key，直到re-review frozen。

## Candidate Variants

| Variant | Role | Expected visible result | Expected hidden result |
|---|---|---|---|
| `before.py` | change base，只用於生成diff | 不要求獨立gate | 不要求獨立gate |
| `buggy.py` | initial review candidate | `project_test.py` pass | `verification_test.py`以fixture指定marker fail |
| `fixed.py` | fix/re-review candidate | `project_test.py` pass | `verification_test.py` pass |

Buggy hidden failure是有效fixture的expected result，不是runner失敗。它證明oracle能揭露visible suite漏掉的defect。

## Deterministic Runner Semantics

Runner預設read-only，逐fixture驗證：

1. 所有required files存在；
2. answer key有required headings；
3. tracked `change.diff`與freshly generated before-to-buggy diff完全一致；
4. buggy visible project tests pass；
5. buggy hidden verification fails，且output包含該fixture宣告的named marker；
6. fixed visible project tests pass；
7. fixed hidden verification tests pass。

只有第5項的具名expected failure算pass。Import error、syntax error、missing file、stale diff、wrong failure marker、project test failure、fixed candidate任何failure或runner exception都屬harness failure並以nonzero exit結束。

Runner設定`PYTHONDONTWRITEBYTECODE=1`，不在fixtures留下`__pycache__`。`--write-diffs`是唯一允許寫入的mode，用於刻意修改`before.py`/`buggy.py`後重新生成diff；一般trial不得使用它修飾candidate。

## Manual AI Review Procedure

1. 先執行runner，確認lab baseline有效。
2. 選定fixture與experimental condition，建立fresh Coding Agent context（self-review condition除外）。
3. 只組裝Reviewer Input Boundary允許的packet，記錄visible test command/output。
4. 給reviewer [Production Protocol](../03-production-review-protocol.md)的assigned axes/lenses與11-field contract。
5. 保存完整prompt/context condition、raw response、normalized findings和initial decision；此時freeze initial review。
6. 解封answer key與verification oracle，由evaluator映射findings、計算metrics。
7. 若測re-review，提供fixed candidate與new diff，重複review並在再次解封前freeze。
8. 把完整run複製到`results-template.md`的副本，原template保持可重用。

AI trial在既有Coding Agent harness中執行。`run_lab.py`永遠不呼叫OpenAI、Anthropic或任何provider API，也不需要API key。

## Result Recording

每個run使用一份results template副本，保留fixture slug、candidate hashes、model/harness、experimental dimensions、packet、raw/normalized findings、answer-key mapping、metrics、re-review、cost/latency與go/no-go。

不要只保存摘要。Raw output使未來能重新判定false positive、schema compliance和prompt effects；normalized table則使跨conditions可比較。

## Adding a Fixture

新增fixture時：

1. 使用下一個兩位數slug並建立完整8-file fixture contract；
2. `spec.md`只寫requested behavior，`project-overlay.md`只寫project facts/rules；
3. 讓buggy candidate在visible suite pass，但hidden oracle以唯一marker揭露一個主要production defect；
4. fixed candidate同時通過兩套tests；
5. answer key解釋expected finding、severity/evidence、project_test為何漏掉、fixed evidence和scope boundary；
6. 用`--write-diffs`建立diff，然後回到default read-only runner驗證；
7. 確認reviewer不需答案檔也能從packet合理推導finding。

一個fixture可有多個related symptoms，但answer key應固定主要root cause，避免recall分母任意漂移。

## Limitations

- Fixtures小且刻意聚焦，不能代表real codebase navigation成本。
- Python stdlib避開framework noise，也因此不涵蓋ORM、message broker、cloud SDK等stack behavior。
- Hidden oracle本身可能不完整，需要human review與版本控制。
- Reviewer看到固定六個families後可能overfit；正式promotion需holdout variants和real-diff pilot。
- Runner驗證fixture mechanics，不驗證AI output品質；quality metrics由evaluator從保存的trial record計算。
