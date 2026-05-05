# Chunking 调参手册：科学确定 chunk_size 和 overlap

## 这篇解决什么问题

`chunk_size` 和 `overlap` 没有行业统一默认值。真实项目里，默认值只能当起点，不能当结论。

这篇解决的是：

```text
我应该如何用真实文档和真实问题，证明某组 chunk 参数更合适？
```

目标不是找到一个永远正确的数字，而是建立一套可复现的调参流程：

```text
准备问题集
-> 设计参数矩阵
-> 每组参数重建索引
-> 跑同一批问题
-> 比较 retrieval、answer、citation、成本和延迟
-> 选择最终配置
```

## 先记住结论

先用保守参数跑起来，再用数据调：

```text
普通产品文档 / FAQ / 知识库:
  500/50
  800/100

长政策 / 合同 / 技术手册:
  800/100
  1000/150

短问答 / 原子化条目:
  200/0
  300/30
```

这里的写法是：

```text
chunk_size / overlap
```

例如 `800/100` 表示每个 chunk 约 800 tokens，下一段和上一段重叠约 100 tokens。

最终选择不看感觉，而看：

- 正确证据是否进入候选：`recall@k`
- 候选里噪声是否太多：`precision@k`
- 正确证据是否靠前：first-correct-rank / `MRR`
- 最终答案是否被证据支持：faithfulness / grounding
- 引用是否真的支持答案：citation accuracy
- 成本是否可接受：chunk 数量、embedding 成本、rerank 延迟、prompt 长度

## 从保守初始值开始

第一轮不要试太多组合，先选 3 组：

| 配置 | 适合观察什么 |
|------|--------------|
| `500/50` | 小 chunk 是否能提高精确度 |
| `800/100` | 常见平衡点，适合作为基线 |
| `1000/150` | 较长 chunk 是否能保留条件、定义和例外 |

如果文档多是 FAQ、短政策、字段说明，可以加：

```text
300/30
```

如果文档多是合同条款、技术设计、长表格解释，可以加：

```text
1200/150
```

不要一开始就做十几组参数。组合太多会让你看不清问题来自 chunking、retriever、reranker 还是 prompt。

## 建一个 chunking golden set

调 chunk 参数前，先准备一批代表性问题。最小规模可以从 30 到 50 条开始，稳定后扩到 100 到 200 条。

每一条样本至少记录：

```text
question
expected_resource_id
expected_section_or_span
reference_answer
failure_risk
```

示例：

| 字段 | 示例 |
|------|------|
| question | 在职员工未休年假能提现吗？ |
| expected_resource_id | hr-leave-policy-2026 |
| expected_section_or_span | 年假折现规则，第 2 条和第 3 条 |
| reference_answer | 在职员工不得直接折现；离职结算时可按政策折现。 |
| failure_risk | 条件遗漏 / partial hit |

样本要覆盖不同失败风险：

| 类型 | 例子 | 为什么重要 |
|------|------|------------|
| 精确术语 | `ERR_PAYMENT_402` 是什么 | 测 BM25、metadata、短 chunk |
| 同义表达 | 退款多久到账 | 测 embedding 语义召回 |
| 条件问题 | 在职员工未休年假能提现吗 | 测 chunk 是否保留条件 |
| 例外问题 | 哪些情况不能退款 | 测 chunk 是否保留例外 |
| 表格问题 | 哪个套餐支持 SSO | 测表格解析和结构切分 |
| 版本问题 | 现在 SLA 是多久 | 测 metadata 和旧文档污染 |

注意：golden set 不是只写问题，还要标注“正确证据在哪里”。否则你无法判断是检索没命中，还是生成没用好证据。

## 跑参数矩阵

对每组 `chunk_size / overlap` 都跑同一套流程：

```text
1. parse documents
2. split chunks with this config
3. save chunk_id, resource_id, start_offset, end_offset, heading, text
4. rebuild embeddings and index
5. run the same golden set
6. capture retrieved chunks
7. capture reranked chunks
8. capture final prompt context
9. capture answer and citations
10. label failure type if answer is wrong
```

每组参数必须重建索引，因为 chunk 边界变了，`chunk_id`、embedding、召回结果都会变。

建议记录成这样的表：

| config | chunks | avg_chunk_tokens | recall@5 | precision@5 | first_correct_rank | citation_accuracy | avg_prompt_tokens | avg_latency_ms |
|--------|--------|------------------|----------|-------------|--------------------|-------------------|-------------------|----------------|
| 500/50 | 1800 | 492 | 0.78 | 0.61 | 2.4 | 0.70 | 3100 | 820 |
| 800/100 | 1260 | 781 | 0.86 | 0.66 | 1.8 | 0.79 | 3400 | 760 |
| 1000/150 | 1030 | 972 | 0.88 | 0.55 | 1.7 | 0.75 | 4300 | 730 |

表里的数字只是示例。真实项目要用自己的文档和问题跑。

## 看 retrieval 指标

先看检索，不要直接看最终答案。

| 指标 | 看什么 | 和 chunk 的关系 |
|------|--------|----------------|
| `recall@k` | 正确证据是否进入前 k 个候选 | 低说明正确 chunk 没进候选，可能切太碎、切断条件、metadata 错 |
| `precision@k` | 前 k 个候选有多少是真相关 | 低说明 chunk 太大、主题混杂、噪声多 |
| first-correct-rank | 第一个正确证据排第几 | 越靠前越好，影响 rerank 和 context assembly |
| duplicate rate | 候选里重复 chunk 比例 | 高说明 overlap 太大或去重不足 |

一个实用判断：

```text
正确证据完全没进候选 -> 先修 parsing、chunking、metadata、retriever
正确证据进了但排很低 -> 看 rerank、hybrid fusion、top_k
正确证据进 final context 但答案错 -> 看 prompt、grounding、citation
```

## 看 answer 指标

chunking 最终服务的是答案质量，所以还要看最终回答。

| 指标 | 看什么 |
|------|--------|
| answer correctness | 答案是否符合业务事实 |
| faithfulness / grounding | 答案每个主张是否被 final context 支持 |
| citation accuracy | 引用的 chunk 是否真的支持对应句子 |
| answer relevancy | 是否回答了用户的问题，而不是复述资料 |

重点是区分两类错误：

```text
retrieval failure:
  正确证据没有进入 final context

generation / grounding failure:
  正确证据已经进入 final context，但答案没用好、扩大解释或引用错配
```

如果问题是 generation，继续调 `chunk_size` 通常收益有限。

## 看成本和延迟

`overlap` 会制造重复，`chunk_size` 会影响候选粒度。调参时必须同时记录成本：

| 成本项 | 为什么受影响 |
|--------|--------------|
| chunk 数量 | chunk 越小、overlap 越大，数量越多 |
| embedding 成本 | 每个 chunk 都要 embedding |
| 向量索引大小 | chunk 数量越多，索引越大 |
| rerank 延迟 | 候选越多，cross-encoder 或 reranker 越慢 |
| prompt tokens | chunk 越大，final context 更容易变长 |
| duplicate context | overlap 过大时，模型会看到重复内容 |

常见取舍：

```text
小 chunk:
  召回更细，precision 可能更高
  但容易切断条件，chunk 数更多

大 chunk:
  保留上下文更完整
  但更容易混入多个主题，prompt 更长

大 overlap:
  边界信息更不容易丢
  但重复索引、重复候选、重复上下文都会增加
```

## 常见现象诊断

| 现象 | 常见原因 | 调整方向 |
|------|----------|----------|
| 答案漏掉条件或例外 | chunk 太小，条件被切到另一个 chunk | 增大 `chunk_size`，增加 `overlap`，或按标题/条款切 |
| 检索结果看似相关但答不了问题 | chunk 太大，一个 chunk 混了多个主题 | 减小 `chunk_size`，按段落/标题/表格结构切 |
| 边界处信息经常丢 | overlap 太小 | 把 overlap 提到 chunk 的 10% 到 20% |
| 候选里很多重复片段 | overlap 太大或没有去重 | 降低 overlap，增加 dedup |
| 标题和正文分离 | 只按固定长度切 | 给正文保留 heading path，或按 Markdown/HTML 结构切 |
| 表格被切坏 | 固定长度切断行列关系 | 表格单独解析，按行组或表格块切 |
| 引用对不上 | source tracking 丢失或 context assembly 改写后没保留来源 | 保留 `chunk_id`、offset、标题、页码和版本 |

## 如何选最终配置

一个务实原则：

```text
选能稳定保留语义边界的最小 chunk_size。
选能解决边界丢失的最小 overlap。
```

不要只追求最高 `recall@k`。如果 `1000/150` 的 recall 只比 `800/100` 高 1%，但 prompt 长度和噪声明显增加，通常不值得。

也不要只追求低成本。如果 `500/50` 便宜但经常漏条件，后面 reranker 和 LLM 很难补救。

最终决策可以写成：

```text
我们选择 800/100。
原因是它在 golden set 上 recall@5 明显高于 500/50，
citation accuracy 高于 1000/150，
并且 chunk 数和 prompt 长度仍在预算内。
```

## 一个完整例子

问题：

```text
在职员工未休年假能提现吗？
```

文档原文：

```text
离职结算规则：员工离职结算时，未休年假可按当地政策折现。
在职规则：仍在职员工不得直接折现未休年假，但可按流程申请休假。
```

如果 `chunk_size` 太小，可能切成：

```text
chunk A: 离职结算规则：员工离职结算时，未休年假可按当地政策折现。
chunk B: 在职规则：仍在职员工不得直接折现未休年假，但可按流程申请休假。
```

检索只命中 chunk A 时，模型可能错误回答“可以折现”。

更好的 chunk 应保留问题需要的边界：

```text
chunk: 年假折现规则
离职结算时，未休年假可按当地政策折现；仍在职员工不得直接折现未休年假，但可按流程申请休假。
```

这时答案可以基于完整证据：

```text
不可以。在职员工不能直接折现未休年假；只有离职结算时才可能按当地政策折现。
```

引用也应该指向同一个包含两条边界的 chunk。

## 面试 / 项目回答模板

可以这样说：

```text
我们没有直接拍一个 chunk_size。第一版用 500/50、800/100、1000/150 做参数矩阵，
每组都重新切 chunk、重建 embedding 和索引，然后用同一批 golden set 回放。

评估时分两层看：retrieval 层看 recall@k、precision@k、first-correct-rank；
answer 层看 correctness、grounding 和 citation accuracy。

最后还看成本和延迟，比如 chunk 数量、rerank 延迟、prompt tokens 和重复 chunk 比例。
最终选择的是能稳定保留条件和例外、同时噪声和成本可接受的一组参数。
```

如果要更短：

```text
chunk_size 和 overlap 不是默认值问题，而是 eval 问题。
我们用代表性问题集比较多组切分参数，看正确证据是否进候选、是否靠前、答案是否被引用支持，
再结合索引规模、rerank 延迟和 prompt 成本选最终配置。
```

## 自测

1. 为什么不能只看最终答案来调 `chunk_size`？
2. `recall@5` 高但 `precision@5` 很低，可能说明什么？
3. overlap 太大会带来哪些成本？
4. 什么现象说明 chunk 太小？
5. 为什么每组 chunk 参数都要重建索引？
6. 如果正确证据已经进入 final context，但答案仍然错，应该继续调 chunk 还是先看 generation / grounding？
