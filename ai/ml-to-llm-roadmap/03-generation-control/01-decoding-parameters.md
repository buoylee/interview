# 解码参数：Temperature、Top-k、Top-p

## 这篇解决什么问题

同一个 prompt 为什么有时输出稳定，有时输出发散？因为 Decoder-only 模型每一步不是直接给出一句完整答案，而是给出“下一个 token 的概率分布”，再由解码策略决定实际选哪个 token。

这一篇解决的问题是：当你调 Temperature、Top-k、Top-p 或 repetition penalty 时，你到底在控制什么，以及这些参数为什么会影响稳定性、多样性和重复。

## 学前检查

读这篇前，最好已经理解：

- Decoder-only 模型如何逐 token 生成：[Decoder-only 与生成](../04-transformer-foundations/08-decoder-only-generation.md)
- Softmax 如何把分数变成概率分布：[Self-Attention QKV](../04-transformer-foundations/04-self-attention-qkv.md)

如果你还不熟，也可以先记住一句话：模型先给每个候选 token 打分，softmax 后得到概率，解码策略再从这些概率里选一个 token。

## 概念为什么出现

自由文本生成有一个天然矛盾：

- 如果每次都选概率最高的 token，输出稳定，但容易机械、重复、早早走进局部最优。
- 如果允许随机采样，输出更丰富，但格式、事实和语气可能不稳定。

解码参数出现，就是为了在“稳定”和“多样”之间调节。它们不改变模型学到的知识，只改变从概率分布中选择 token 的方式。

## 最小心智模型

生成一步可以拆成三件事：

```text
上下文 -> 模型输出 logits -> 转成概率分布 -> 解码策略选下一个 token
```

常见策略：

- Greedy：永远选概率最高的 token，确定性最强。
- Temperature：改变概率分布的尖锐程度。
- Top-k：只保留概率最高的 k 个候选。
- Top-p：只保留累计概率达到 p 的最小候选集合。
- Repetition penalty：降低已经出现过的 token 再次被选中的倾向。

## 最小例子

假设 prompt 是：

```text
The capital of France is
```

模型给出的下一个 token 候选大致是：

| token | 原始概率 |
|-------|----------|
| Paris | 0.70 |
| London | 0.12 |
| Berlin | 0.08 |
| a | 0.04 |
| beautiful | 0.03 |
| unknown | 0.03 |

Greedy 会直接选 `Paris`。低 Temperature 会让 `Paris` 更占优势，高 Temperature 会让 `London`、`Berlin` 这类低概率候选更有机会被采到。

如果设置 `Top-k = 3`，候选只剩 `Paris`、`London`、`Berlin`。如果设置 `Top-p = 0.90`，会保留累计概率达到 0.90 的候选，这里可能也是前三个，因为 `0.70 + 0.12 + 0.08 = 0.90`。

## 原理层

模型输出的是 logits，也就是每个候选 token 的未归一化分数。Softmax 把 logits 转成概率分布。Temperature 通常作用在 softmax 前：

```text
probability = softmax(logits / temperature)
```

当 Temperature 小于 1，最高分 token 的优势被放大，分布更尖锐；当 Temperature 大于 1，分布更平，低概率 token 更容易被采样。Temperature 改的是分布形状，不是候选 token 本身。

Top-k 和 Top-p 则是在采样前截断候选集合。Top-k 的规则是固定数量，只看排名；Top-p 的规则是累计概率，候选数量会随分布形状变化。分布很尖时，Top-p 可能只保留很少 token；分布很平时，它会保留更多 token。

Repetition penalty 用来处理另一个问题：自回归生成会把已经生成的内容继续作为上下文，如果某些 token 在当前上下文里越来越容易被预测，模型可能陷入重复。惩罚重复 token 可以减少循环，但过强会让正常术语、字段名或必要重复也被破坏。

## 和应用/面试的连接

在应用里，参数选择应该跟任务目标绑定：

| 任务 | 常见设置倾向 | 原因 |
|------|--------------|------|
| JSON 字段抽取 | 低 Temperature | 格式和字段稳定更重要 |
| 代码补全 | 低到中 Temperature | 要兼顾正确性和可替代写法 |
| 头脑风暴 | 中到高 Temperature | 多样性更重要 |
| 客服标准回复 | 低 Temperature + 结构化约束 | 一致性和可控性更重要 |

面试里不要只说“Temperature 越高越随机”。更完整的回答是：模型先给出下一个 token 的概率分布，Temperature 调整分布尖锐程度，Top-k/Top-p 截断采样候选，最终共同影响稳定性、多样性和错误率。

## 常见误区

| 误区 | 更准确的理解 |
|------|--------------|
| Temperature 改变模型知识 | 它只改变解码时的概率分布形状 |
| Top-k 和 Top-p 是同一个东西 | Top-k 按固定数量截断，Top-p 按累计概率截断 |
| Greedy 总是最准确 | 对事实短答可能稳定，对开放生成容易重复或僵硬 |
| 低 Temperature 能保证 JSON 正确 | 它只能降低随机性，不能保证结构合法 |
| Repetition penalty 越高越好 | 过高会破坏必要重复和专业术语 |

## 自测

1. Temperature changes what part of decoding?
2. Top-k and Top-p both remove candidates, but their cutoff rules differ how?
3. Why can low temperature improve stability but reduce diversity?
4. Why is greedy decoding often bad for open-ended generation?

## 回到主线

解码参数解决的是“如何从概率分布中选 token”。下一篇会进一步看：如果我们不仅想要稳定，还想要输出必须是合法 JSON 或符合某个 Schema，仅靠低 Temperature 为什么还不够。

下一篇：[结构化输出与约束解码](./02-structured-output-constrained-decoding.md)
