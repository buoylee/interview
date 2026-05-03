# 生产排查、监控与回归定位

## 这篇解决什么问题

LLM 应用上线后，问题经常不是简单的“服务挂了”。更常见的是：回答质量下降、延迟升高、成本暴涨、拒答变多、JSON 解析失败、用户投诉某类问题答错，或者安全过滤突然拦不住。

这篇解决的问题是：如何把一个模糊症状拆到具体组件，如何设计监控维度，以及如何在模型、prompt、版本或配置变更后定位质量回归。

## 学前检查

读这篇前，建议先理解：

- 评估样本和 LLM-as-Judge 如何帮助判断质量：[LLM 评估与 LLM-as-Judge](./01-llm-evaluation-judge.md)
- 幻觉、安全和 Guardrails 为什么要拆维度：[幻觉、安全与 Guardrails](./02-hallucination-safety-guardrails.md)
- 推理延迟和成本如何拆解：[推理优化、部署与成本](../06-inference-deployment-cost/README.md)

如果你已经有 RAG 或 Agent 经验，可以把检索、工具和输出解析器看作链路里的可选节点。当前主线仍然是通用 LLM 应用排查。

## 概念为什么出现

传统后端排查常从错误码、日志和资源指标开始。LLM 系统多了一类“语义故障”：HTTP 200，但答案错了；结构合法，但业务含义不对；安全策略没有报错，但输出越界。

生产排查出现，是为了把这些语义故障拆成可观察、可复现、可回归验证的问题：

```text
症状: 用户看到什么坏结果
组件: 哪一段链路可能造成它
证据: 用日志、样本、指标和 eval 证明
修复: 改 prompt、模型、解码、guardrail、infra 或产品流程
回归: 用 regression set 防止再次发生
```

## 最小心智模型

从症状到组件，可以按这条链路排查：

```text
input -> optional retrieval/context -> prompt -> model -> decoding -> optional tool/output parser -> evaluator/guardrail -> infra
```

每个组件问一个问题：

- input：用户输入是否分布变化、过长、恶意、缺关键字段？
- retrieval/context（可选）：如果系统用了外部上下文，召回、排序、摘要或拼接是否错了？
- prompt：系统指令、示例、格式要求或上下文顺序是否改变？
- model：模型版本、供应商、微调权重或安全策略是否改变？
- decoding：temperature、top-p、max tokens、stop sequences 是否改变？
- tool/output parser（可选）：如果系统用了工具或结构化解析，schema、字段名、重试逻辑是否改变？
- evaluator/guardrail：评估、过滤、拒答、引用检查是否误杀或漏检？
- infra：排队、限流、超时、缓存、网络、GPU 或服务降级是否影响结果？

## 最小例子

一次发布后，客服摘要系统的用户投诉增加：摘要更短，但漏掉退款原因。

排查可以这样做：

```text
1. 取发布前后同一批 conversation，构造 regression set。
2. 跑 offline eval，rubric 包含 completeness、correctness、safety。
3. 对比变更记录：模型从 v1 换到 v2，同时 max tokens 从 300 降到 120。
4. 查看失败样本：模型仍理解对话，但输出被截短，关键原因常在末尾丢失。
5. 修复：提高 max tokens，调整摘要 prompt，加入“必须包含退款原因”检查。
6. 回归：把这些失败样本加入 regression set，后续发布自动测试。
```

这里问题不是“模型坏了”一个笼统结论，而是输出预算和任务要求冲突，导致质量指标下降。

## 排查与修复 Playbook

线上问题不要先猜“是不是模型不行”。按下面顺序处理：

```text
1. 定义症状: 哪个指标变差，影响哪些用户/任务/时间段
2. 固定样本: 抽取失败请求，脱敏后形成 replay set
3. 对比版本: 找出 prompt、模型、参数、schema、guardrail、路由、检索或工具变更
4. 拆链路: input -> context -> prompt -> model -> decoding -> parser/tool -> guardrail -> infra
5. 定位根因: 用 trace 证明坏在哪一层
6. 小修复: 只改一个主要变量，避免同时改 prompt、模型和参数
7. 回归验证: replay set + regression set 通过后再灰度发布
```

常见症状可以这样处理：

| 症状 | 先查什么 | 常见修复 |
|------|----------|----------|
| 回答变短、漏关键点 | `max_tokens`、摘要 prompt、输出截断、stop sequence | 提高输出预算；在 rubric/prompt 中列必填信息；加 completeness 检查 |
| factuality 下降 | 是否缺上下文、模型版本变化、用户分布变化、是否要求模型猜测 | 补充可靠上下文；低依据时拒答；加入事实核查或人工复核 |
| grounding 下降 | 检索片段、引用是否支持结论、context 顺序是否变化 | 调整 retrieval/rerank；减少噪声 chunk；加引用支持检查 |
| JSON/schema 失败 | schema 是否变更、示例是否冲突、temperature、输出是否被截断 | 使用结构化输出；降低随机性；加 validation retry；简化 schema |
| 拒答率升高 | safety policy、拒答 prompt、分类器阈值、误拒样本 | 降低误拒阈值；拆分安全拒答和缺信息拒答；补安全替代回答 |
| 危险输出漏检 | safety classifier 覆盖范围、输出过滤、red team 样本 | 增加高风险分类；加后置验证；把漏检加入 regression set |
| 延迟升高 | TTFT、总 tokens、排队、检索/工具耗时、重试次数 | 缩短上下文；缓存检索；并行只读工具；设置超时和降级 |
| 成本暴涨 | 输入 token、输出 token、重试、模型路由、异常用户 | context trimming；限制 top-k；降级小模型；加成本预算和速率限制 |
| 工具调用错误 | tool schema、参数抽取、权限、超时、幂等、外部 API 变化 | 强校验参数；分类重试；补权限检查；记录 tool observation |
| RAG 答错 | selected resources、metadata filter、retrieved chunks、rerank、context assembly | 修 resource resolver；修 filter；调 chunk/top-k/rerank；去重压缩上下文 |

修复要尽量绑定到对应层：

```text
input 问题:
  加输入分类、长度限制、缺字段追问、恶意输入检测

context/RAG 问题:
  修 resource scope、metadata filter、chunking、hybrid retrieval、rerank、context order

prompt 问题:
  明确任务边界、必填项、拒答条件、引用规则，删除冲突示例

model/decoding 问题:
  固定模型版本，调整 temperature/top_p/max_tokens/stop sequences

parser/schema 问题:
  使用结构化输出、schema validation、字段级重试和降级路径

guardrail 问题:
  拆分类别、调整阈值、增加后置验证，把误杀/漏检都加入样本集

infra 问题:
  查超时、限流、缓存、队列、供应商状态、重试风暴和降级策略
```

最后用同一批样本验证修复：

```text
before: 旧版本输出 + 指标
after: 新版本输出 + 指标
diff: 哪些样本修好，哪些变差
release: 小流量灰度，监控同一组指标
```

没有 replay set 和 trace 的“修复”只能算猜测。

## 原理层

监控 LLM 应用要同时覆盖工程指标和语义指标。只看 p95 latency 和 error rate，会漏掉大量 HTTP 200 的坏回答；只看人工抽样质量，又会错过成本、拒答率和 schema failure 的系统性变化。

常见监控维度包括：

| 维度 | 看什么 | 常见信号 |
|------|--------|----------|
| quality | 正确性、完整性、有用性、grounding | judge 分数、人工抽样、任务成功率 |
| latency | TTFT、总耗时、排队时间、tokens/sec | p50/p95/p99、超时率 |
| cost | 输入 token、输出 token、重试、模型单价 | 单请求成本、总账单、异常用户 |
| safety | 违规输出、敏感信息、危险建议 | safety 分类、拦截率、人工升级 |
| refusal rate | 拒答比例和误拒比例 | 拒答率突增、用户重试 |
| schema failure | JSON 解析失败、字段缺失、类型错误 | parser error、validation retry |
| drift | 用户分布、问题类型、模型行为变化 | topic shift、eval 分数趋势 |
| user feedback | 点赞点踩、投诉、人工纠错 | feedback rate、negative feedback |

质量回归定位要有变更意识。模型版本、prompt、系统消息、few-shot 示例、解码参数、输出 schema、安全策略、供应商默认行为、路由规则和超时设置都可能改变输出。排查时先固定样本，再逐项对比，避免在真实流量噪声里猜原因。

可复现性也很重要。记录 request id、模型和版本、prompt 模板版本、输入摘要、上下文片段 id、解码参数、输出、解析结果、评估结果、延迟和成本。对于隐私敏感系统，日志要脱敏或只保存可审计摘要，但不能完全没有定位依据。

Optional retrieval/context 和 optional tool/output parser 之所以标成可选，是因为不是每个 LLM 应用都需要 RAG 或 Agent。简单分类、摘要、改写、结构化抽取也会遇到质量和安全问题。等系统确实引入检索或工具，再把召回率、工具成功率、工具权限、外部内容注入和工具结果验证纳入排查。

## 和应用/面试的连接

应用里，生产排查最好和发布流程绑定：每次改动先跑 golden set 和 regression set，再小流量上线，观察质量、延迟、成本、安全、拒答率、schema failure、drift 和用户反馈。出现问题时，用固定样本重放并对比版本，而不是只读几条聊天记录下结论。

面试里，如果被问“LLM 应用线上质量下降怎么办”，可以按症状到组件回答：先定义下降指标，抽样失败案例，固定可复现输入；检查 input、prompt、model、decoding、parser/schema（如果系统有结构化输出）、guardrail、infra；如有检索或工具，再检查这些可选组件；最后用 eval 和 regression set 验证修复。

## 常见误区

| 误区 | 更准确的说法 |
|------|--------------|
| HTTP 200 就说明系统正常 | LLM 可能返回流畅但错误、无依据或不安全的答案 |
| 质量下降一定是模型退化 | Prompt、解码、输出长度、上下文、解析和安全策略都可能造成回归 |
| 线上排查只看日志 | 还需要固定样本、eval、用户反馈和变更记录 |
| 监控成本只看 token 单价 | 重试、长输入、长输出、超时和人工复核都会放大成本 |
| 所有问题都先加 RAG 或工具 | 检索和工具是可选组件，先定位问题来源再决定是否引入 |

## 自测

1. LLM 应用里的语义故障为什么可能不会表现为 HTTP 错误？
2. 如果 schema failure 突然上升，你会检查哪些组件？
3. 为什么质量监控要同时看 offline eval 和 online feedback？
4. 输出质量下降后，为什么要先固定样本再对比版本？
5. 检索和工具在生产排查里为什么应该作为可选组件处理？

## 回到主线

到这里，你已经能把评估、安全和生产排查连起来：用 eval 判断质量，用 Guardrails 控制风险，用监控和 regression set 定位并防止回归。后续系统设计和项目叙事会继续使用这些概念，把“不确定的模型行为”纳入可解释的工程方案。
