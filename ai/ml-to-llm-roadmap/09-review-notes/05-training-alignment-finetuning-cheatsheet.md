# 训练对齐微调面试速记

> 这份笔记用于复习，不适合作为第一次学习入口。第一次学习先读 [训练、对齐与微调](../05-training-alignment-finetuning/)。

## 30 秒答案

预训练让 base model 学语言和通用模式，SFT 用“指令-好回答”样本把它塑造成 instruction model，RLHF/DPO 用偏好数据让回答更符合人类偏好。KL 约束防止对齐后偏离参考模型太远；LoRA/QLoRA 用低成本做任务适配；BERT、GPT、T5 的核心差异是 encoder-only、decoder-only、encoder-decoder 及训练目标不同。

## 2 分钟展开

预训练通常是自监督 token prediction，目标是获得通用语言能力和知识底座。SFT 不是重新训练知识库，而是在高质量 instruction data 和 chat template 上继续训练，让模型学会按用户指令、角色和格式回答。SFT 能改善 instruction following，但不能完整解决“多个答案哪个更好”的偏好问题。

偏好对齐使用 chosen/rejected pair。典型 RLHF 会训练 reward model，再用 PPO 等方式更新策略模型；DPO 直接用偏好对优化模型，省掉典型 RLHF 中单独 reward model 加 PPO 的复杂链路。KL constraint 用来限制新模型不要为了高 reward 偏离参考模型太远，避免模式化、过度拒答或语言质量退化。

微调和适配要按问题选择。LoRA 冻结 base，只训练低秩增量；QLoRA 把量化 base 和 LoRA 训练结合，主要降低训练显存；蒸馏让 student 学 teacher 的答案、过程或偏好。BERT 适合理解表示，GPT 适合自回归生成，T5 把任务统一成 text-to-text。

## 高频追问

| 追问 | 回答 |
|------|------|
| Pretraining 和 SFT 的区别是什么？ | Pretraining 学通用语言和模式；SFT 用指令样本塑造对话、任务和格式行为。 |
| 为什么 SFT 后还需要 alignment？ | SFT 模仿单个示范答案；alignment 学“两个可行答案里人更偏好哪个”。 |
| RLHF 和 DPO 的主要差异是什么？ | 典型 RLHF 先训练 reward model 再做策略优化；DPO 直接用 chosen/rejected pair 优化模型。 |
| KL constraint 解决什么问题？ | 限制新模型别离参考模型太远，降低 reward hacking、模式化和语言质量退化风险。 |
| LoRA 为什么省资源？ | 冻结原权重，只训练低秩增量矩阵，训练参数和显存需求更低。 |
| QLoRA 和推理量化一样吗？ | 不一样。QLoRA 是训练方案：量化 base model 并冻结，再训练 LoRA adapter。 |
| BERT、GPT、T5 怎么快速区分？ | BERT 是 encoder-only 做理解，GPT 是 decoder-only 做生成，T5 是 encoder-decoder 做 text-to-text 转换。 |

## 易混点

| 概念 | 容易混的点 | 正确理解 |
|------|------------|----------|
| Base model vs chat model | 以为都是会聊天的模型 | Base 更像续写器，chat model 经过 SFT/对齐更会按指令交互 |
| SFT vs alignment | 以为 SFT 就等于安全对齐 | SFT 学示范答案，alignment 学偏好和安全倾向 |
| RLHF vs DPO | 以为 DPO 不需要偏好数据 | DPO 仍需要 chosen/rejected 偏好对 |
| LoRA vs full fine-tuning | 以为都是更新全量权重 | LoRA 冻结 base，只训练 adapter 增量 |
| Alignment vs factuality | 以为对齐保证事实正确 | 对齐改善偏好和安全倾向，不保证事实永远正确 |

## 项目连接

- 模型不听格式：先看 prompt、结构化输出和 SFT 行为，不要直接说要预训练。
- 语气、安全边界或过度自信问题：可从偏好对齐、系统策略和评估闭环解释。
- 业务标签和话术稳定适配：LoRA/QLoRA 是候选方案，但要先确认 prompt、schema 和数据质量是否足够。
- 私有知识经常变化：通常不优先写进权重；RAG 是未来模块边界，这里只说明微调不是知识更新的万能方案。

## 反向链接

- [预训练与 SFT：从 base model 到 instruction model](../05-training-alignment-finetuning/01-pretraining-sft-overview.md)
- [偏好对齐：RLHF、DPO 与 KL 约束](../05-training-alignment-finetuning/02-preference-alignment-rlhf-dpo.md)
- [LoRA、QLoRA、蒸馏与模型合并](../05-training-alignment-finetuning/03-lora-qlora-distillation.md)
- [模型演进：BERT、GPT、T5 给今天留下了什么](../05-training-alignment-finetuning/04-model-evolution-bert-gpt-t5.md)
- [三种 Transformer 架构范式](../04-transformer-foundations/07-transformer-architecture-variants.md)
