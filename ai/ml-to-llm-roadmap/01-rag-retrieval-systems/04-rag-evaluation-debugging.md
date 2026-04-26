# RAG 评估、幻觉与生产排查

## 这篇解决什么问题

RAG 系统即使没有报错，也可能给出错误答案：没检到证据、检到了错误证据、证据只覆盖一半问题、文档过期、答案没有被上下文支持，或引用看起来存在但对不上原文。

这一篇解决的问题是：如何把 RAG 失败拆成可定位的类型，如何分别评估 retrieval 和 answer，以及线上排查时应该记录哪些 trace。

## 学前检查

读这篇前，建议先理解：

- RAG 候选如何被召回：[索引、Embedding 与召回](./02-indexing-embedding-retrieval.md)
- RAG 上下文如何被排序和组装：[Hybrid Search、Rerank 与上下文组装](./03-hybrid-search-rerank-context.md)
- LLM 评估如何使用 golden set 和 judge：[LLM 评估与 LLM-as-Judge](../07-evaluation-safety-production/01-llm-evaluation-judge.md)

如果还不熟，可以先记住一句话：RAG 评估要分开看“证据有没有找对”和“答案有没有忠实使用证据”。

## 概念为什么出现

普通日志只能告诉你请求成功或失败，但 RAG 质量问题发生在多段链路里：

```text
没检到 -> 检错了 -> 排错了 -> 上下文组装坏了 -> 生成没遵守证据 -> 引用错配
```

评估和 trace 出现，是为了把“答案不好”拆成可定位、可回归、可修复的问题。

## 最小心智模型

RAG 评估可以分成两层：

```text
retrieval metrics: 相关证据是否进入候选和靠前位置
answer metrics: 最终答案是否正确、忠实、相关、引用准确
```

常见失败类型：

- no hit：正确证据完全没被召回。
- wrong hit：召回了看似相关但实际错误的证据。
- partial hit：只召回部分证据，遗漏条件或例外。
- stale document：命中过期文档。
- unsupported answer：答案内容没有被上下文支持。
- citation mismatch：引用位置和答案主张对不上。
- context overload：上下文太多太杂，模型忽略关键证据。

## 最小例子

用户问：

```text
在职员工未休年假能提现吗？
```

一次失败 trace 可能是：

```text
Question: 在职员工未休年假能提现吗？
Retrieved chunks:
  1. 离职结算时未休年假可折现。
  2. 年假申请需提前 3 天提交。
Reranked chunks:
  1. 离职结算时未休年假可折现。
Final prompt context:
  只包含离职折现规则，缺少“在职不得折现”条款。
Answer:
  可以，未休年假可折现。
Judge/Human label:
  incorrect, not faithful to full policy boundary
Failure type:
  partial hit -> unsupported answer
```

这里不是模型完全不会回答，而是检索漏掉了关键边界，生成又把片面证据扩大成一般结论。

## 原理层

Retrieval metrics 关注候选证据：

| 指标 | 看什么 |
|------|--------|
| recall@k | 正确证据是否出现在前 k 个候选里 |
| precision@k | 前 k 个候选里有多少是真相关 |
| MRR | 第一个正确证据出现得有多早 |
| NDCG | 排名是否把更重要证据放在更前面 |

MRR 和 NDCG 是可选排名指标，适合有标注相关性等级的场景。初期更常见的是先保证 recall@k：如果正确证据没进入候选，后面生成很难补救。

Answer metrics 关注最终回答：

- answer correctness：答案是否符合事实和业务规则。
- faithfulness/grounding：答案中的主张是否被给定上下文支持。
- citation accuracy：引用是否真的支持对应句子。
- answer relevancy：是否回答了用户真正的问题，而不是只复述文档。

Correctness 和 faithfulness 不一样。一个答案可能符合真实世界，但没有被当前上下文支持；也可能忠实复述了过期文档，却和最新事实不一致。因此 RAG 要同时看证据质量、答案忠实度和文档时效。

Golden set 是精心整理的代表性问题集合，通常带期望证据和参考答案。Regression set 用来覆盖历史失败、边界政策和高风险样本。Production trace 则记录真实线上链路，帮助发现数据分布变化、文档更新问题和 prompt 回归。

一个排查 trace 至少应包含：

```text
Question -> retrieved chunks -> reranked chunks -> final prompt context -> answer -> judge/human label -> failure type
```

生产环境还应记录 query rewrite、filters、文档版本、chunk id、rank score、rerank score、prompt 版本、模型版本、引用位置、延迟和成本。

## 和应用/面试的连接

应用里，RAG 上线前应有 golden set 和 regression set；上线后抽样 production trace，按失败类型统计。修复时要先定位链路：no hit 通常改 ingestion、chunk、metadata 或 retriever；wrong hit 和 partial hit 可能改 hybrid/rerank；unsupported answer 和 citation mismatch 可能改 prompt、context assembly、grounding check 或引用生成。

面试里，好的回答不是“用 LLM-as-Judge 评估”。更完整的表达是：分开评估 retrieval 和 answer；记录完整 trace；用 human 或 judge 标注失败类型；把历史失败加入 regression set；上线监控质量、延迟、成本和文档版本。

相关内容可继续看：[LLM 评估与 LLM-as-Judge](../07-evaluation-safety-production/01-llm-evaluation-judge.md)、[幻觉、安全与 Guardrails](../07-evaluation-safety-production/02-hallucination-safety-guardrails.md)、[生产排查与监控](../07-evaluation-safety-production/03-production-debugging-monitoring.md)。

## 常见误区

| 误区 | 更准确的理解 |
|------|--------------|
| 答案错就是模型差 | 可能是检索、排序、上下文或文档版本问题 |
| recall@k 高就够了 | 候选进来了，不代表排序、组装和生成都正确 |
| faithfulness 等于 correctness | 忠实是相对上下文，正确性还要看真实业务事实 |
| 有 citation 就可信 | citation 可能不支持对应主张 |
| 只看线上用户反馈 | 还需要固定 regression set 防止改动回退 |

## 自测

1. 如何区分检索失败和生成失败？
2. Faithfulness 和 answer correctness 有什么区别？
3. Citation mismatch 可能来自哪些环节？
4. RAG 线上回归应该记录哪些 trace 字段？

## 回到主线

到这里，你已经完成 RAG 与检索系统的主线：问题边界、索引召回、混合排序、上下文组装、评估和排查。后续学习生成控制、评估安全和系统设计时，可以把 RAG 当作“外部知识接入与证据约束”的模块，而不是 Agent 或向量数据库产品清单。
