# AI Engineer 面试路径：训练、对齐与微调

## 适用场景

- 需要解释大模型从预训练到上线前能力塑形的主流程。
- 面试中会被追问 SFT、RLHF、DPO、LoRA、QLoRA、蒸馏和模型架构演进。
- RAG 与 Agent 有独立面试路径；本路径聚焦模型本身如何被训练、对齐和适配。

## 90 分钟冲刺

| 顺序 | 阅读 | 目标 |
|------|------|------|
| 1 | [Pretraining and SFT Overview](../05-training-alignment-finetuning/01-pretraining-sft-overview.md) | 区分预训练能力来源和 SFT 行为格式化 |
| 2 | [Preference Alignment, RLHF and DPO](../05-training-alignment-finetuning/02-preference-alignment-rlhf-dpo.md) | 说清偏好对齐解决的问题 |
| 3 | [LoRA, QLoRA and Distillation](../05-training-alignment-finetuning/03-lora-qlora-distillation.md) | 理解低成本适配和压缩 |
| 4 | [Model Evolution: BERT, GPT, T5](../05-training-alignment-finetuning/04-model-evolution-bert-gpt-t5.md) | 准备架构和训练目标对比 |
| 5 | [Training Alignment Cheatsheet](../09-review-notes/05-training-alignment-finetuning-cheatsheet.md) | 压缩成面试答案 |

## 半天复盘

1. 先按阶段复述：pretraining 学通用分布，SFT 学指令格式，RLHF/DPO 学偏好取舍。
2. 再按成本复述：全参微调、LoRA/QLoRA、蒸馏分别适合什么约束。
3. 用 BERT、GPT、T5 对比 encoder-only、decoder-only、encoder-decoder 的训练目标和应用边界。
4. 最后读 [Training Alignment Cheatsheet](../09-review-notes/05-training-alignment-finetuning-cheatsheet.md)，检查是否能用自己的项目语言回答。

## 必答问题

- Pretraining、SFT、RLHF/DPO 各解决什么问题？
- 为什么 SFT 不等于对齐？
- RLHF 和 DPO 的核心差异？
- LoRA/QLoRA 为什么省显存？
- BERT、GPT、T5 的架构和训练目标差异？
- 什么时候选择微调，什么时候优先 prompt、RAG 或规则？
- 蒸馏和量化分别在优化什么？

## 可跳过内容

- 不推导 PPO、DPO 损失函数细节。
- 不展开训练集构建的全部数据工程流程。
- 不把微调当成所有业务问题的默认答案；RAG 与 Agent 仍按各自面试路径处理。

## 复习笔记

从系统学习页开始，最后用 [Training Alignment Cheatsheet](../09-review-notes/05-training-alignment-finetuning-cheatsheet.md) 收口。
