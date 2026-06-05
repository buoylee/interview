# 面试 Q&A — Eval 与质量保障

> 本篇聚焦本项目的 eval 闭环设计:自定义检查、golden set 回归门、ragas 四指标、非确定性测试策略。不重写概念,指向仓库已有文档。

---

## Q1: RAG eval 和 agent 轨迹 eval 有什么区别?本项目如何结合两者?

**答案要点**

- **RAG eval**:评估检索+生成质量,关注"答案是否有依据、是否相关"——输入是 query+chunks+answer,指标是 faithfulness、context_recall 等。不关心 agent 走了几步、用了什么工具。
- **Agent 轨迹 eval**:评估 agent 执行路径是否正确——supervisor 路由对不对(expected_route)、有没有按规则拒答(refusal)、引用了哪些文档(citation)、在几步内完成(step_budget)。关注控制流,不依赖 LLM judge。
- **本项目如何结合**:
  - `eval/checks.py` 的四个纯函数检查 = 轨迹 eval:`check_must_include`(答案关键词)、`check_route`(路由正确性)、`check_citations`(引用文档)、`check_refusal`(拒答行为)。这四个全 hermetic,不需要 LLM,测试完全确定性。
  - `eval/ragas_eval.py` = RAG eval:`faithfulness / answer_relevancy / context_precision / context_recall`。需要 LLM judge,放在可选 extra,仅 live 运行。
  - `eval/runner.py` 的 `run_eval` 把两者串联:跑完轨迹检查后,可选调 ragas。

**深挖追问**

- "为什么轨迹 eval 不用 LLM judge?" — 路由是否正确是二值判断(route == expected_route),不需要语言理解;用 LLM judge 反而引入随机性,变成在测 judge 而不是在测 agent。
- "agent 轨迹 eval 能替代 RAG eval 吗?" — 不能。轨迹 eval 检查"走了正确的路",RAG eval 检查"路走完后答案质量如何"。两者正交。

**常见误区**

- 误认为 eval = ragas。ragas 只是 RAG eval 的一个工具框架;本项目 hermetic 测试用的是自定义纯函数检查,ragas 是额外补充。
- 误认为轨迹 eval 能检测幻觉。check_must_include 检查答案是否包含关键词,不能检查答案是否"编造"了不在 chunks 里的内容——这要 faithfulness 指标来检。

**仓库概念文档**

- `ai/ml-to-llm-roadmap/07-evaluation-safety-production/01-llm-evaluation-judge.md` → LLM-as-judge 原理与局限
- `ai/ml-to-llm-roadmap/02-agent-tool-use/11-agent-eval-practice.md` → agent 轨迹 eval 实践

---

## Q2: ragas 四个指标分别测什么?

**答案要点**

| 指标 | 测什么 | 需要什么输入 | 本项目意义 |
|---|---|---|---|
| **faithfulness** | 答案的每个主张是否都有 chunks 支撑(接地性)。没有依据 = 幻觉。 | question, answer, contexts | 检测 generate 节点是否产生幻觉;与 grounding_check 验证一致 |
| **answer_relevancy** | 答案是否回答了 question(相关性)。答非所问得低分。 | question, answer | 检测 supervisor 路由和 generate 的语义对齐 |
| **context_precision** | retrieved contexts 中真正有用的比例。命中率低意味着噪声 chunk 多。 | question, contexts, ground_truth | 检测 rerank 的 precision 质量 |
| **context_recall** | ground_truth 中需要的信息是否都在 contexts 里。漏掉 = recall 问题。 | question, contexts, ground_truth | 检测 hybrid 检索的 recall 是否覆盖 |

- faithfulness + answer_relevancy 不需要 ground_truth,只需 question/answer/contexts,较容易跑。
- context_precision + context_recall 需要 ground_truth(参考答案),要求 golden set 中有标注答案。
- 本项目 `eval/ragas_eval.py` 默认跑前三个(faithfulness, answer_relevancy, context_precision),因为 MVP golden set 中 ground_truth 可选。

**深挖追问**

- "faithfulness 为什么不等于 grounding_check?" — grounding_check 是本项目内部的二值判断(grounded/not);faithfulness 是 ragas 的 LLM judge,给出 0-1 连续分并能识别部分幻觉。两者方向一致但精度不同。
- "context_recall 低和 context_precision 低各怎么修?" — recall 低:增大 top-N、改 hybrid 策略、调 chunk_size;precision 低:加强 rerank(更好模型/更小 top-K)、改 grade 阈值。

**常见误区**

- 误认为 faithfulness 高就意味着答案正确。答案可能"有依据地"回答了错误的东西——chunks 本身有误;faithfulness 只保证答案和 chunks 一致。
- 误认为四个指标都高就"万事大吉"。还需要看延迟、cost、用户满意度(online eval)。指标是工具,不是目标。

**仓库概念文档**

- `ai/ml-to-llm-roadmap/01-rag-retrieval-systems/04-rag-evaluation-debugging.md` → RAG eval 指标体系
- `ai/ml-to-llm-roadmap/07-evaluation-safety-production/01-llm-evaluation-judge.md` → LLM judge 评测原理

---

## Q3: 为什么 golden set 要进 git?它是怎么当回归门用的?

**答案要点**

- `eval/golden/cases.jsonl`:每行一个 case,格式固定(id/question/must_include/expected_route/expected_citation_docs/should_refuse)。进 git 的原因:
  - **版本可追溯**:每次改了什么 case、加了什么 case,和代码 diff 一起 review。
  - **PR 级回归**:CI 可以在每个 PR 上跑 `make eval`(stub runner),通过率低于阈值则 PR 挡住。
  - **防止测试腐烂**:如果 golden set 只在人脑里/文档里,时间久了没人维护;进 git 强制团队当代码看待。
- **回归门机制**:`eval/runner.py` 返回 `EvalReport.pass_rate`;`eval/cli.py` 在 `pass_rate < 0.5` 时 exit code 非 0,CI 看退出码决定 pass/fail。
- `eval/report.py` 的 `diff_reports(prev, curr)`:比较两次 eval 报告,返回"之前过、现在挂"的 case id 列表——识别具体哪个 case 回归了。

**深挖追问**

- "golden set 怎么扩充?" — 每次发现线上坏答案,把那个 query + 预期行为加进 cases.jsonl,提 PR,从此作为回归 case 永久覆盖。这是"bug 驱动 golden set 增长"模式。
- "golden set 太小(只有 4 个 case)有意义吗?" — 比没有强。4 个 case 能覆盖 4 种核心行为:kb_rag 命中、kb_rag 引用、web fallback、拒答。后续按需扩充。

**常见误区**

- 误认为 golden set 要人工标注很多才有用。10-20 个精心挑选的 case(覆盖边界情况)比 1000 个平均分布的 case 更有价值。
- 误认为 eval 回归门只能在 CI 跑。本地 `make eval`(配了 key)也可以跑;CI 门是额外保障,不是唯一入口。

**仓库概念文档**

- `ai/ml-to-llm-roadmap/02-agent-tool-use/11-agent-eval-practice.md` → golden set 设计与回归 CI 实践

---

## Q4: LLM 输出是非确定性的,怎么做 hermetic 测试?

**答案要点**

- **非确定性问题的根源**:LLM 每次推理(temperature > 0)结果可能不同;测试若依赖 LLM 输出,就无法保证重复性和 CI 稳定性。
- **本项目策略**:把逻辑检查和质量检查分开:
  - **逻辑检查(hermetic)**:`eval/checks.py` 四个纯函数,输入字符串,输出布尔——不调 LLM,可以确定性测试。测试里注入 `good_runner` / `bad_runner` stub,stub 直接返回固定字符串。
  - **质量检查(live-only)**:ragas 的 faithfulness/relevancy 等指标必须调 LLM judge,放在 `[eval]` extra 里,仅在 `make eval`(配真实 key)时运行,不进 hermetic pytest 套件。
- 等价于:**行为**用 stub 测,**质量**用 live eval 测。两者各司其职。

**深挖追问**

- "temperature=0 能解决非确定性吗?" — 部分。temperature=0 让模型更确定,但不能保证跨模型版本、跨 prompt 格式 100% 相同输出。确定性测试还是要 stub。
- "stub runner 会不会测不到真实 bug?" — 会。stub 测逻辑正确性(路由对、字段格式对);真实 bug(LLM 幻觉、prompt 退化)要靠 live eval + online monitoring 发现。两层防御。

**常见误区**

- 误认为不确定性意味着"LLM 系统没法测"。逻辑层(路由、格式、schema)完全确定性测;质量层用统计/阈值方法测。测试策略要分层。
- 误认为 CI 里跑真实 LLM 是最好的做法。CI 调真实 LLM = 有网络依赖、有费用、慢、可能 flaky。hermetic 套件应该是纯 stub。

**仓库概念文档**

- `ai/ml-to-llm-roadmap/07-evaluation-safety-production/01-llm-evaluation-judge.md` → 非确定性系统的测试策略
- `ai/ml-to-llm-roadmap/01-rag-retrieval-systems/04-rag-evaluation-debugging.md` → RAG 系统测试分层
