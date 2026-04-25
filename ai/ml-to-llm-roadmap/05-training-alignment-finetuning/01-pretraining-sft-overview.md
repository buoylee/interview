# 预训练与 SFT：从 base model 到 instruction model

## 这篇解决什么问题

一个只做过大规模预训练的模型，已经学到语言模式和很多世界知识，但它不一定知道“用户问一句，我要按指令给出有帮助的回答”。这一篇解决的问题是：为什么要先预训练，再用 SFT 把 base model 变成 instruction model。

## 学前检查

读这篇前，最好已经理解：

- Decoder-only 如何逐 token 生成：[Decoder-only 与生成](../04-transformer-foundations/08-decoder-only-generation.md)
- CLM 和 MLM 的差异：[架构变体](../04-transformer-foundations/07-transformer-architecture-variants.md)
- loss 如何通过反向传播更新参数：[反向传播与梯度问题](../foundations/deep-learning/02-backprop-gradient-problems.md)

如果你已经有 RAG 或 Agent 使用经验，可以先把这里理解成“模型能力的底座从哪里来，以及为什么 chat 模型比 base model 更会听指令”。

## 概念为什么出现

预训练解决的是“模型没有通用语言能力”的问题。它用海量文本训练 token prediction，让模型学会语法、常识、代码模式、知识关联和长程依赖。

SFT 解决的是另一个问题：会预测文本不等于会按人类指令完成任务。互联网上的原始文本包含文章、代码、问答、广告、错误内容和噪声，但用户希望模型理解任务、遵守格式、承认不确定性，并用对话方式回答。

因此顺序通常是：

```text
先预训练: 获得通用能力和知识底座
再 SFT: 把这些能力塑造成可交互的指令跟随行为
```

## 最小心智模型

预训练像让模型读完整个图书馆，并不断猜下一个 token。SFT 像给模型看一批“用户指令 -> 好回答”的样例，让它学会在对话场景里调用已有能力。

关键概念：

- token prediction：给定前文，预测下一个 token。
- data mix：预训练数据的组成比例，例如网页、书籍、代码、数学、对话等。
- base model：主要经过预训练的模型，擅长续写，不一定擅长对话。
- instruction data：人工或模型生成的指令-回答样本。
- chat template：把 system、user、assistant 等角色消息序列化成模型训练和推理时看到的文本格式。
- SFT：supervised fine-tuning，用高质量指令数据继续训练模型。

## 最小例子

预训练阶段，模型可能看到原始文本：

```text
Paris is the capital and most populous city of France.
```

训练任务是预测下一个 token，例如看到 `Paris is the capital and most populous city of` 时预测 `France`。

SFT 阶段，同一类知识会被组织成指令样本：

```text
<user> What is the capital of France?
<assistant> The capital of France is Paris.
```

模型不只是学到“France 后面常出现 Paris”，还学到当用户提问时，应当给出直接、简洁、符合对话角色的回答。

## 原理层

预训练通常使用自监督学习，不需要人工为每段文本标注答案。对于 decoder-only LLM，常见目标是 causal language modeling：只能看左侧上下文，预测下一个 token。这个目标和生成过程一致，所以预训练后的模型天然能逐 token 续写。

Data mix 很重要，因为模型学到的能力强烈受数据分布影响。代码比例更高，代码能力通常更强；数学和高质量推理数据更多，相关能力更容易出现；低质量重复数据太多，则可能带来重复、偏见和噪声。

SFT 在同一个模型上继续优化，但数据从“任意文本”变成“指令和理想回答”。Chat template 是这里容易被低估的一层：模型并不原生知道消息对象，它看到的是被模板展开后的 token 序列。如果训练和推理的模板不一致，模型可能出现角色混乱、停止符错误或格式漂移。

SFT 能明显改善 instruction following，但它没有完全解决偏好和安全问题。原因是同一个指令可能有多个正确回答：有的更诚实，有的更啰嗦，有的更安全，有的更符合用户意图。SFT 只模仿单个示范答案，不直接学习“两个可行答案里人更喜欢哪一个”。

## 和应用/面试的连接

工程上，理解预训练和 SFT 能帮你判断问题来源：模型完全不知道某个事实，可能是知识或检索问题；模型知道但不按格式回答，可能是 instruction tuning、prompt 或结构化输出问题；模型回答有害或不符合偏好，通常还要看对齐层。

面试里常见问法是：

- 为什么 base model 不能直接当 chat model 用？
- SFT 和继续预训练有什么区别？
- 为什么训练 chat model 需要 chat template？
- SFT 为什么不能替代 RLHF 或 DPO？

## 常见误区

| 误区 | 更准确的说法 |
|------|--------------|
| 预训练就是背知识库 | 预训练是压缩语言和数据分布中的模式，不是可靠数据库 |
| SFT 会让模型获得全新底层能力 | SFT 主要塑造行为和任务格式，能力上限仍受 base model 影响 |
| instruction data 越多越好 | 质量、覆盖面、去重和模板一致性都很关键 |
| chat template 只是工程包装 | 模板会变成训练 token，直接影响模型学到的对话格式 |

## 自测

1. 为什么预训练通常要放在 SFT 之前？
2. Token prediction 解决了模型训练中的什么标注成本问题？
3. Base model 和 instruction model 的行为差异是什么？
4. 为什么 SFT 改善指令跟随，但不能完全解决偏好和安全？

## 回到主线

到这里，你已经知道 base model 如何通过 SFT 变成更会对话的 instruction model。下一篇继续看：当多个回答都“能用”时，如何让模型更接近人类偏好：[偏好对齐：RLHF、DPO 与 KL 约束](./02-preference-alignment-rlhf-dpo.md)。
