# AI Code Review Trial Result

複製本檔建立一次trial record；不要直接覆寫template。所有`<...>`都要替換，未知值寫`unknown + reason`，不留空白。

## Run Identity

記錄能重現推理環境的身份：

| Field | Value to record |
|---|---|
| Date/timezone | `<ISO-8601 timestamp + timezone>` |
| Run ID | `<stable unique ID>` |
| Fixture / candidate | `<slug, buggy|fixed, file hashes>` |
| Harness | `<Codex/Claude Code/other + version>` |
| Provider / model / version | `<provider, exact model identifier, dated version if exposed>` |
| Temperature or equivalent | `<value; deterministic/default/not exposed>` |
| Tool profile | `<read/search/shell/subagent access actually available>` |
| Strategy version | `<protocol/prompt commit or immutable identifier>` |
| Evaluator | `<person or independent agent ID>` |

## Review Mode

逐項記experimental dimension，不用「full review」代替：

| Dimension | Selected value |
|---|---|
| Context | `<implementer self-review | fresh-context review>` |
| Structure | `<single generic | four axes + applicable lenses>` |
| Project policy | `<without Core/Overlay | with Core/Overlay>` |
| Lifecycle | `<initial buggy review | fixed re-review>` |
| Repetition | `<run N of M>` |
| Contamination | `<blind | contaminated + reason>` |

## Input Packet

保存或引用immutable packet：BASE/HEAD或file hashes、commit/diff、`spec.md`、是否包含`project-overlay.md`、visible tests command/output、repo/Core rules、assigned axes/lenses與explicit omissions。列出reviewer看不到的evaluator-only files，證明boundary成立。

```text
Packet path/hash: <...>
Visible command: <...>
Visible result: <exit code + concise output>
Axes/lenses: <...>
Omissions/deviations: <...>
```

## Raw Findings

原樣保存reviewer response，包括axis/lens verdict、coverage limitation和沒有findings的明示結果。不要在此修正文句或依answer key補finding。

```text
<verbatim reviewer output>
```

## Normalized Findings

每個row必須完整使用protocol的11 fields；一個cell未知時仍寫unknown/needs-verification理由。

| `id` | `lens` | `severity` | `confidence` | `location` | `rule` | `impact` | `evidence` | `direction` | `verification` | `status` |
|---|---|---|---|---|---|---|---|---|---|---|
| `<ID>` | `<axis/lens>` | `<Critical|Important|Minor>` | `<high|medium|low>` | `<file:line/symbol>` | `<canonical rule>` | `<concrete consequence>` | `<reproducible evidence>` | `<fix goal>` | `<focused procedure>` | `<allowed status>` |

Normalization只能整理format，不能改變reviewer原意；任何evaluator inference要在Answer-Key Comparison另記。

## Answer-Key Comparison

Initial review frozen後才填。逐expected defect與finding做mapping：

| Answer-key defect ID | Matched finding IDs | Outcome | Severity match | Evidence confirmed | Adjudication note |
|---|---|---|---|---|---|
| `<AK-ID>` | `<IDs or miss>` | `<confirmed|partial|miss>` | `<yes|no|N/A>` | `<yes|no>` | `<why>` |

另列unmatched findings，逐項標`valid additional finding`、`disproven false positive`或`needs external fact`，附evidence。Duplicates映射同一defect，但recall只算一次。

## Metrics

填numerator、denominator和result，分母為零寫N/A：

| Metric | Numerator | Denominator | Result |
|---|---:|---:|---:|
| Confirmed-defect recall | `<confirmed expected defects found>` | `<total expected defects>` | `<ratio>` |
| False-positive rate | `<disproven findings>` | `<all findings>` | `<ratio>` |
| Evidence rate | `<findings with reproducible evidence>` | `<all findings>` | `<ratio>` |
| Actionability rate | `<findings with location+rule+impact+verification>` | `<all findings>` | `<ratio>` |
| Severity calibration | `<matched findings with matching severity>` | `<matched findings>` | `<ratio>` |
| Stability | `<findings reproduced across runs>` | `<union across repeated runs>` | `<ratio or pending>` |

補充記錄Critical misses、schema violations、applicable lens coverage、needs-verification closure和human adjudication time。

## Re-review

若未跑寫`not run + reason`。若已跑，記fixed candidate hash、新packet、fresh deterministic outputs，並逐initial finding記：

| Finding ID | Before status | Fix evidence | Re-review evidence | After status | Regression/new finding |
|---|---|---|---|---|---|
| `<ID>` | `<...>` | `<command/diff>` | `<review claim>` | `<fixed|verified|open>` | `<none or ID>` |

Fixed但未re-review不可記verified；stale accusation要計入re-review品質問題。

## Cost and Latency

| Field | Exact value |
|---|---|
| Input tokens or proxy | `<tokens; otherwise chars/bytes and method>` |
| Output tokens or proxy | `<tokens; otherwise chars/bytes and method>` |
| Agent/model calls | `<count + models>` |
| Tool calls | `<count by type>` |
| Wall-clock latency | `<seconds>` |
| Active tool time | `<seconds or unavailable>` |
| Estimated cost | `<currency/value + pricing assumptions, or unavailable>` |
| Retries/timeouts/errors | `<count + reason>` |
| Human clarification | `<count + elapsed time>` |

Cost與latency不得合併進quality score，只與quality metrics並列。

## Decision

記錄`Go`、`No-Go`或`Pending`，以及candidate SHA/hash、decision authority、timestamp。逐條確認deterministic checks、Critical count、Important resolution、accepted-risk authority、re-review freshness和rollout evidence。

```text
Decision: <Go|No-Go|Pending>
Candidate: <hash>
Authority: <human/role>
Blocking finding IDs: <none or IDs>
Accepted risks: <none or IDs + authority/expiry>
Reason: <evidence-based decision>
```

## Worked Example

以下是**synthetic formatting example，不是任何fixture的實驗結果**。

### Synthetic Normalized Finding

| `id` | `lens` | `severity` | `confidence` | `location` | `rule` | `impact` | `evidence` | `direction` | `verification` | `status` |
|---|---|---|---|---|---|---|---|---|---|---|
| `SYN-001` | `Reliability and Fallback` | `Important` | `high` | `example.py:42 call_remote` | `SYN-OVERLAY-01: deadline required` | request可能無限等待，耗盡worker | diff加入remote call但沒有deadline；synthetic focused test超時 | 將總budget傳入adapter並在到期時回傳明確failure | `python -m unittest synthetic_timeout_test.py`應在100ms內以`TimeoutError`結束 | `open` |

### Synthetic Decision Fragment

```text
Decision: No-Go
Candidate: synthetic-deadbeef
Authority: example release owner
Blocking finding IDs: SYN-001
Accepted risks: none
Reason: Important finding remains open; no bounded timeout evidence.
```
