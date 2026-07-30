# 04 - 如何評估 AI Code Review

## 先給結論

不要以「review寫得像資深工程師」或單次demo判斷策略。可重現evaluation應固定candidate、spec、Project Overlay和answer key，改變review condition，測量是否找到已知defects、evidence是否可重現、finding是否可行動、severity是否校準，以及fix後能否正確re-review。

這個lab評估review strategy在受控fixtures上的行為，不建立model leaderboard，也不宣稱能代表所有語言、domain或production system。

## What the Lab Measures

Lab主要測：

- reviewer能否從diff/spec/overlay發現visible project tests漏掉的expected defects；
- fresh context、fixed axes和project policy各自增加什麼signal；
- findings是否帶location、rule、impact、evidence和verification；
- reviewer能否區分Critical/Important/Minor與confidence；
- fix後re-review是否關閉原finding且不製造新false claim；
- repeated runs是否穩定重現核心finding；
- quality gain相對token/cost proxy與latency的trade-off。

## What the Lab Does Not Measure

Lab不直接測：

- 模型在所有real repositories的通用排名；
- long-context codebase理解的上限；
- production incident response、human coordination或deployment tooling；
- unknown unknowns的完整recall；
- stylistic preference或報告可讀性的所有面向；
- Python stdlib以外stack的framework-specific defects。

Fixtures的answer key已知，因此只適合比較protocol condition；不能證明沒有列入key的finding一定錯，也不能證明在toy fixture成功就可自動批准真實高風險change。

## Six Fixture Families

| Fixture | Visible project test為何會pass | Expected production defect | Primary axes/lenses |
|---|---|---|---|
| Data consistency | 只測單次happy-path更新 | 多步寫入中途失敗造成partial state | Correctness；Reliability/Fallback |
| Idempotency | 只測相同request重放 | 同key不同payload錯誤重用舊result | Correctness；Compatibility |
| Timeout/retry/fallback | dependency立即成功 | 無bounded timeout/retry semantics，fallback掩蓋unknown outcome | Reliability/Fallback；Observability |
| Interface coupling | mock內部method讓測試通過 | caller依賴concrete internals，替換adapter即破壞 | Architecture；Test Quality |
| Error handling | 只斷言回傳預設值 | swallowed exception把hard failure偽裝成success | Correctness；Observability |
| Misleading tests | test重算implementation同一公式 | oracle共享同一bug，GREEN沒有獨立證據 | Test Quality；Correctness |

每個fixture有`spec.md`、`project-overlay.md`、`before.py`、`buggy.py`、`fixed.py`、visible `project_test.py`、independent `verification_test.py`、`change.diff`和隔離的answer key。

## Experimental Matrix

至少比較四組binary dimensions；candidate、prompt budget與answer key保持固定：

| Dimension | Baseline | Treatment | 要回答的問題 |
|---|---|---|---|
| Reviewer context | Implementer self-review | Fresh-context review | separation of duties是否提高expected-defect recall？ |
| Review structure | Single generic review | Four fixed axes + applicable risk lenses | 分責任是否減少masking並改善actionability？ |
| Project policy | No Core Profile/Overlay | With Core Profile/Project Overlay | 明確invariants與risk facts是否降低猜測和漏報？ |
| Lifecycle point | Initial buggy review | Re-review after fixed candidate | 策略能否確認修復而非重複舊finding？ |

完整factorial是`2 × 2 × 2 × 2 = 16` conditions per fixture；成本有限時可先跑paired ablations，但每次只能改一個dimension，並記錄未跑conditions。不同model、temperature或tool access另作experimental factor，不與protocol effect混稱。

建議每個stochastic condition重複至少三次；若host固定deterministic，仍保存run ID和完整output以確認一致。

## Metrics

所有分母為零時記`N/A`，不可用0掩蓋沒有樣本。

```text
confirmed-defect recall = confirmed expected defects found / total expected defects
false-positive rate = disproven findings / all findings
evidence rate = findings with reproducible evidence / all findings
actionability rate = findings with location + rule + impact + verification / all findings
severity calibration = findings whose severity matches answer key / matched findings
stability = findings reproduced across repeated runs / union of repeated-run findings
```

配對規則：先由獨立evaluator把finding映射到answer-key defect ID；同root cause的duplicates只算一次recall，但各自仍計入all findings以暴露spam。部分命中要記reason，不可為提高分數隨意合併。

補充記錄：

- blocking defect miss count；
- needs-verification claims中完成查證比例；
- fix/re-review後stale finding數；
- report schema violation數；
- applicable lens coverage；
- human adjudication time。

任何單一metric都不構成總quality score，尤其不能用findings數量代替recall或用長報告代替evidence。

## Answer-Key Isolation

Reviewer不得讀`answer-key/`或`verification_test.py`。它只收到spec、overlay、before/buggy diff、visible project tests和deterministic output。

Trial完成後，由evaluator解封answer key並執行verification oracle：

1. 對buggy candidate確認visible tests pass；
2. 對buggy candidate確認verification test以具名marker fail；
3. 對fixed candidate確認visible與verification tests都pass；
4. 將findings映射expected defects，判定confirmed、disproven或unmatched；
5. 保存原始review output，不事後改寫finding以符合key。

同一人/Agent若先讀answer key再review，該run只能算calibration exercise，不能列入blind evaluation。

## Running a Review Trial

一次trial記錄：

1. fixture slug、candidate hash/file hashes與runner version；
2. model/harness、system/skill instructions、tools、context condition；
3. 是否fresh context、是否fixed axes/lenses、是否提供Core/Overlay、initial或re-review；
4. review packet和deterministic commands/output；
5. 原始findings與axis/lens verdicts；
6. verifier actions、answer-key mapping與false-positive adjudication；
7. metrics、latency、token/cost proxy和errors；
8. evaluator、timestamp與known deviations。

Review步驟必須read-only。Lab runner預設只驗證fixtures；只有明確`--write-diffs`才重新產生tracked `change.diff`，避免一次trial悄悄改candidate truth。

## Comparing Results

先做同fixture paired comparison，再跨fixtures聚合：

- 同一model下比較self vs fresh，估計context isolation effect；
- 同一packet下比較generic vs fixed axes，估計structure effect；
- 同一review structure下比較with/without Overlay，估計project-fact effect；
- 同一finding set比較initial vs re-review，估計closure correctness。

跨fixtures報micro與macro結果：micro按defect數加權，macro讓每fixture等權。Critical miss必須獨立列出，不能被大量Minor success稀釋。若conditions的prompt/token budget不同，並列報告而不是聲稱純protocol因果。

## Cost and Latency Recording

每run保存：

- input/output token count；取不到時以characters或bytes作明示proxy；
- model list、agent/reviewer calls和tool calls；
- wall-clock latency與active tool time；
- retry、timeout、failed run和human clarification次數；
- estimated monetary cost（只有provider價格與cache policy已知時）。

Cost/latency只與quality metrics並列，不組成單一quality score。較便宜但漏Critical的策略不可用平均性價比分數勝出；較昂貴策略也必須證明新增的是confirmed signal，不是更多generic comments。

## Threats to Validity

| Threat | 影響 | Mitigation |
|---|---|---|
| Toy fixtures | 真實codebase navigation與framework complexity較低 | 後續加入匿名real diffs，但保留同一finding/evidence contract |
| Answer-key incompleteness | 新的有效finding可能被誤判false positive | human adjudication + unmatched-valid category，版本化key |
| Prompt leakage | reviewer從檔名/文字猜到expected defect | 使用中性packet、隔離answer key、保存prompt |
| Model stochasticity | 單次run偶然好/壞 | repeated runs、stability metric、報distribution |
| Unequal context budget | treatment因更多tokens而非結構獲益 | 記token proxy，做budget-matched secondary run |
| Evaluator bias | finding mapping與severity對齊主觀 | blind double adjudication或明確mapping rules |
| Harness/tool differences | 能否run tests/search source影響結果 | 固定tool profile，差異另列factor |
| Fixture overfitting | strategy記住六個defects | holdout variants、改名/改surface但保留invariant |

## Promotion Criteria for a Review Strategy

策略要從experiment升級為project gate，至少滿足：

- 在所有applicable fixture families沒有Critical miss；
- confirmed-defect recall與evidence/actionability相對baseline有可重現改善；
- false-positive rate沒有高到讓human無法triage；
- severity calibration足以讓blocking gate可信；
- repeated-run stability達到project預設門檻；
- re-review能正確關閉fixed finding且不保留stale accusation；
- cost/latency落在project budget，failure與fallback path已演練；
- real-code pilot由human reviewers確認有net value；
- strategy version、prompt、model/tool profile和rollback方式可追蹤。

Promotion不是永久認證。Model、skills、Project Overlay、repository architecture或defect distribution改變後，要重新跑regression fixtures與抽樣real diffs。
