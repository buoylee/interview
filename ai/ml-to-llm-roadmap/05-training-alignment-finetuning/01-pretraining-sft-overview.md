# 预训练与 SFT：从 base model 到 instruction model

## 这篇解决什么问题

一个只做过大规模预训练的模型，已经学到语言模式和很多世界知识，但它不一定知道“用户问一句，我要按指令给出有帮助的回答”。这一篇解决的问题是：为什么要先预训练，再用 SFT（supervised fine-tuning，监督微调：拿“指令 -> 理想回答”样本对模型继续做有监督训练）把 base model 变成 instruction model。本篇就是 SFT 第一次登场的章节，下面会完整展开。

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

### 追问：SFT 属于"后训练"吗？

属于，而且通常是后训练的第一步。"后训练（post-training）"是个伞状术语，指预训练之后的所有训练环节：SFT、RLHF、DPO、RLAIF 都算。整体划分是：

```text
预训练: 海量无标注文本 + token prediction -> 学会语言和世界知识，产出 base model
后训练: SFT -> 偏好对齐(RLHF/DPO 等)   -> 学会遵循指令、符合人类偏好
```

两个语境注意点：

- 早期文献（InstructGPT 时代）直接说 "fine-tuning + RLHF"，"post-training" 这个统称是 2023 年后（Llama 2/3、GPT-4 技术报告）才流行的，旧资料里看不到很正常。
- "后训练"一般指模型厂商把 base model 变成可用助手的那套流程。下游用户拿已对齐的 chat model 再微调领域数据，技术上也是 SFT，但语境上叫 fine-tuning / domain adaptation，不算厂商意义上的后训练。

一句话：预训练教模型"会说话"，后训练（从 SFT 开始）教模型"好好说话"。

### 追问：领域微调和对齐 SFT 有本质差异吗？不都是按人类希望的方式输出？

从算法机制看没有本质差异：两者都是在 `(输入 -> 期望输出)` 标注样本上做 next-token prediction + cross-entropy，梯度下降更新权重（全量或 LoRA），训练代码几乎可以原样复用。真正的差异在三个工程层面：

1. **教的东西不同**：对齐 SFT 教行为模式（什么是指令、回答长什么样、何时拒绝），数据刻意广覆盖、每个领域浅浅一层；领域微调教特定分布（术语、固定格式、某类任务的套路），数据窄而深。
2. **起点不同，风险不同**：对齐 SFT 从 base model 出发，白纸一张；领域微调从已对齐模型出发，等于在调好的权重上动刀，练狠了会**灾难性遗忘**——领域任务变强，但通用对话和安全行为退化。
3. **SFT 擅长教格式，不擅长灌知识**：LIMA 的 superficial alignment hypothesis 说对齐 SFT 主要是引出 base model 已有的能力（所以千条高质量数据就够）。很多领域微调想让模型"学会"公司的新知识，这恰恰是 SFT 弱项——小数据强灌新事实容易教出幻觉。真要注入知识，走继续预训练（continued pretraining）或 RAG 更合适。

所以业界起不同名字，是为了区分语境（厂商造助手 vs 下游做适配），不是因为底层数学不同。

### 追问：各家 LLM 的 base model 差距是不是不大，真正拉开差距的是 SFT？

这个说法对了一半，而且“对的那一半”如今也不是 SFT，而是 RL。

**对的一半：从用户体感看，确实是 post-training 拉开的差距最明显。**

- 各家 base model 在 MMLU 这类 benchmark 上分数接近，因为“怎么训 base”的三大要素都摊在桌面上：Transformer 架构公开、爬虫数据源大家重叠、scaling law 也被论文公开了。开源圈尤其明显——Llama 的配方扩散之后，Qwen、DeepSeek、Mistral 的 base 水准快速收敛。
- 同一个 base model，不同的 post-training 配方，做出来的 chat model 在风格、格式遵循、拒答行为、工具调用上差异巨大。instruction data 和偏好数据是各家**从不公开**的核心资产，侧面说明 post-training 是护城河。

这里展开一下“公开的 scaling law”是什么意思。Scaling law 不是“越大越强”这句定性口号，而是一组可预测的定量公式：loss 和参数量 N、数据量 D、算力 C 之间存在幂律关系（log-log 坐标上是直线，所以能用小模型的便宜实验外推大模型的最终 loss）。它的工程价值是三件事：开训前**预测**大模型会多强（GPT-4 用千分之一算力的小模型预测了最终 loss）、固定预算下**最优分配**模型大小和数据量、小实验偏离直线时**提前止损**。Kaplan 2020 和 Chinchilla 2022（著名结论：每 1 参数配约 20 token 数据；GPT-3 按此标准严重训练不足）把这些公式发表之后，“谁摸对了配比”就不再是差异化来源——大家都往同一条曲线上收敛。后来 Llama 系列又故意“过度训练”（8B 模型训 15T token，远超 Chinchilla 建议），赔训练成本换推理便宜，说明公开配方之上各家仍有策略分化，但那是成本权衡，不是能力代差。

**错的一半：base model 仍然决定能力上限。**

Post-training 只能**引出**（elicit）能力，不能**注入**（instill）能力——这正是上面误区表里那条“SFT 主要塑造行为，能力上限仍受 base model 影响”。两个证据：

1. DeepSeek-R1 的对照实验：对小的 base model 直接做 RL，效果远不如“从大模型蒸馏”。同样的 post-training 配方，放在弱 base 上做不出强推理——推理能力的原料来自预训练。
2. 预训练的数据工程（清洗、去重、配比、合成数据、mid-training 退火）是各家差距最大、最烧钱、最保密的部分。Benchmark 接近不代表 base 一样强——benchmark 饱和了，但长尾知识深度、代码和推理的“潜力”差距真实存在，只是要等 post-training 把它引出来才看得到。

**修正后的版本（面试说这个）**：

> 预训练决定能力上限（天花板），post-training 决定实际能用到多少、以及产品体感。头部模型的 base 差距在收敛但没消失；而 post-training 这边，2023 年的差异化主要在 SFT + RLHF，2024 之后的主战场是 RL——尤其是 RLVR（可验证奖励的强化学习，o1 / DeepSeek-R1 路线）和 agentic 训练。SFT 本身反而是 post-training 里技术含量最低、最容易被追平的一环。

辅助记忆：LIMA 论文的 superficial alignment hypothesis——对话风格、格式这些“表层行为”只要少量高质量 SFT 就能对齐（所以这部分大家都差不多）；但推理深度、知识密度不是表层的东西，SFT 给不了：要么 base 里本来就有，要么靠 RL 去放大。

## 和应用/面试的连接

工程上，理解预训练和 SFT 能帮你判断问题来源：模型完全不知道某个事实，可能是知识或检索问题；模型知道但不按格式回答，可能是 instruction tuning、prompt 或结构化输出问题；模型回答有害或不符合偏好，通常还要看对齐层。

面试里常见问法是：

- 为什么 base model 不能直接当 chat model 用？
- SFT 和继续预训练有什么区别？
- 为什么训练 chat model 需要 chat template？
- SFT 为什么不能替代 RLHF 或 DPO？
- 各家模型的差距主要来自哪个训练阶段？

## 常见误区

| 误区 | 更准确的说法 |
|------|--------------|
| 预训练就是背知识库 | 预训练是压缩语言和数据分布中的模式，不是可靠数据库 |
| SFT 会让模型获得全新底层能力 | SFT 主要塑造行为和任务格式，能力上限仍受 base model 影响 |
| instruction data 越多越好 | 质量、覆盖面、去重和模板一致性都很关键 |
| chat template 只是工程包装 | 模板会变成训练 token，直接影响模型学到的对话格式 |
| 各家 base 都差不多，差距全在 SFT | base 仍决定能力上限；post-training 的差异化主战场也已从 SFT 转向 RL |
| 领域微调和 SFT 是两种不同的技术 | 算法机制完全相同，差异在目的、数据分布、起点模型和各自的坑（如灾难性遗忘） |
| 领域微调适合给模型灌新知识 | SFT 擅长教格式不擅长灌知识，小数据强灌新事实易教出幻觉；注入知识走继续预训练或 RAG |

## 自测

1. 为什么预训练通常要放在 SFT 之前？
2. Token prediction 解决了模型训练中的什么标注成本问题？
3. Base model 和 instruction model 的行为差异是什么？
4. 为什么 SFT 改善指令跟随，但不能完全解决偏好和安全？
5. “各家 base model 都差不多，差距全在 SFT”这个说法哪里对、哪里错？scaling law 公开和这件事有什么关系？
6. 领域微调和对齐 SFT 在算法机制上有区别吗？真正的差异在哪三个层面？
7. 为什么"用领域微调给模型灌公司新知识"通常是个坏主意？更合适的路是什么？

## 回到主线

到这里，你已经知道 base model 如何通过 SFT 变成更会对话的 instruction model。下一篇继续看：当多个回答都“能用”时，如何让模型更接近人类偏好：[偏好对齐：RLHF、DPO 与 KL 约束](./02-preference-alignment-rlhf-dpo.md)。
