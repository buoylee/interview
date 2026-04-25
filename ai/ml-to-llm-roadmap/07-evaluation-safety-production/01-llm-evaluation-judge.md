# LLM 评估与 LLM-as-Judge

## 这篇解决什么问题

传统机器学习里，很多任务可以用 accuracy、F1 或 exact match 判断对错。但 LLM 输出经常是开放文本：同一个问题可能有多个正确表达，答案还可能在有用性、引用证据、安全边界和语气上同时有好坏差异。

这篇解决的问题是：当“完全匹配标准答案”不够用时，如何系统评估 LLM 输出，为什么需要 offline eval、online eval、human eval 和 LLM-as-Judge，以及如何用 rubric 把主观判断变成可复用的评估流程。

## 学前检查

读这篇前，建议先理解：

- LLM 输出来自逐 token 生成：[Decoder-only 与生成](../04-transformer-foundations/08-decoder-only-generation.md)
- 解码参数会改变输出稳定性：[解码参数](../03-generation-control/01-decoding-parameters.md)
- SFT 和偏好对齐解决的是训练阶段行为塑形，不等于上线质量保证：[偏好对齐](../05-training-alignment-finetuning/02-preference-alignment-rlhf-dpo.md)

如果你已经做过 RAG 或 Agent，可以先把这里理解成“如何判断一次模型回答是否真的满足业务目标”，而不是只看日志里有没有报错。

## 概念为什么出现

Exact match 适合答案形式固定的任务，例如分类标签或数学题最终数字。但开放式回答有三个问题：

```text
表达多样: "可以退款" 和 "符合退款条件" 可能同义
质量多维: 正确但不完整、完整但不安全、礼貌但无证据，都不能只用一个字符串匹配判断
上线会变: 模型版本、prompt、解码参数、用户分布变化后，需要知道质量有没有回退
```

评估体系出现，是为了把“看起来不错”拆成可重复执行、可比较、可追踪的质量判断。

## 最小心智模型

LLM 评估可以分成四层：

```text
样本: golden set 和 regression set
执行: offline eval 和 online eval
标注: human eval 和 LLM-as-Judge
标准: rubric 把质量拆成可评分维度
```

关键概念：

- offline eval：上线前或发布前在固定样本集上批量测试，用来比较模型、prompt 或配置。
- online eval：上线后基于真实流量、用户反馈、抽样标注或 A/B 实验观察质量。
- human eval：由人类按标准判断输出质量，成本高但更适合高风险和校准样本。
- LLM-as-Judge：用另一个 LLM 按 rubric 给输出评分或分类，提高评估吞吐，但必须校准。
- rubric：评分规则，说明每个维度看什么、几分代表什么。
- golden set：经过认真整理、代表核心任务的高质量样本集，通常带参考答案或评分要点。
- regression set：专门覆盖历史 bug、边界案例和高风险场景，用来防止改动后旧问题复发。

## 最小例子

假设用户问：

```text
我的会员能不能退款？我昨天刚续费。
```

候选回答：

```text
可以退款。你昨天刚续费，应该符合条件。
```

一个最小 LLM-as-Judge rubric 可以写成：

```text
请按 1-5 分评价回答，并给出简短理由。

correctness: 是否符合退款政策和已知事实
helpfulness: 是否说明下一步行动
citation/grounding: 是否引用或明确依赖可验证依据
safety: 是否避免编造承诺、误导用户或泄露隐私
```

如果系统没有提供退款政策，这个回答可能 helpfulness 尚可，但 correctness 和 citation/grounding 应该低分，因为它把“不知道政策”说成了确定承诺。

## 原理层

Offline eval 的价值在于可重复。你可以在同一批 golden set 上比较模型 A、模型 B、prompt v1、prompt v2，避免只凭少数人工试用判断。但 offline eval 容易覆盖不足：如果样本不代表真实用户，分数再高也可能上线后失败。

Online eval 的价值在于真实。它能观察真实流量、用户反馈、延迟、拒答率和投诉，但噪声更大，也更难知道变化来自模型、prompt、用户分布还是产品入口。

Human eval 常用于建立标准和校准 judge。人类标注不一定完美，但在高风险场景、模糊偏好和安全判断上，仍然是重要参照。为了减少标注漂移，需要给标注员明确 rubric、示例和冲突处理规则。

LLM-as-Judge 解决的是规模问题：人工无法每天评审大量输出，judge 可以用统一 rubric 批量打分。但 judge 也有偏差，例如偏爱更长回答、被候选答案措辞影响、对自己同系列模型更宽容、忽略细小事实错误，或在安全问题上过度保守。

校准的意思是：不要直接相信 judge 分数。你需要抽样让人类复核，检查 judge 与人类一致率；用简单基线和已知好坏样本测试它是否能分开质量；必要时调整 rubric、加入反例、限制输出格式，并把 judge 分数当作趋势信号而不是绝对真理。

## 和应用/面试的连接

应用里，评估通常先从一个小但高质量的 golden set 开始，覆盖最常见任务、最重要用户、历史失败案例和安全边界。每次改模型、prompt、解码参数或输出 schema 前，都先跑 offline eval；上线后再用 online eval 和监控确认真实表现。

面试里，好的回答不是只说“我会用 LLM-as-Judge”。更完整的表达是：先定义任务目标和失败类型，再构造 golden/regression set，用 rubric 拆维度；高风险样本用 human eval，低风险大批量样本用 judge；最后用人类复核校准 judge 偏差，并把评估接入发布流程。

## 常见误区

| 误区 | 更准确的说法 |
|------|--------------|
| LLM 输出开放，所以没法评估 | 可以用 rubric、样本集和多维指标评估，只是不能只靠 exact match |
| LLM-as-Judge 等于自动真相 | Judge 是可扩展评估器，需要人类校准和偏差监控 |
| Golden set 越大越好 | 先保证代表性、标注质量和可维护性，再扩大规模 |
| Online 指标好就不需要 offline eval | Online 反映真实流量，offline 帮助发布前定位回归，二者互补 |
| 一个总分足够判断质量 | 质量通常要拆 correctness、helpfulness、grounding、safety 等维度 |

## 自测

1. 为什么 exact match 不适合大多数开放式 LLM 回答？
2. Offline eval 和 online eval 分别解决什么问题？
3. Golden set 和 regression set 的区别是什么？
4. LLM-as-Judge 的 rubric 为什么要拆成多个维度？
5. Judge bias 可能有哪些表现？你会如何校准？

## 回到主线

到这里，你已经知道如何判断“回答好不好”。下一篇进入“回答是否可靠、安全”：为什么模型会生成看似合理但无依据的内容，以及 Guardrails 如何降低幻觉、安全和输出格式风险：[幻觉、安全与 Guardrails](./02-hallucination-safety-guardrails.md)。
