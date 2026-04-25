# 05 训练、对齐与微调

> **定位**：这个模块解释一个 LLM 从 base model 到 chat model，再到你的业务适配模型，中间经历了什么。它不要求你会训练大模型，但要让你能在面试和工程决策中说清训练阶段、对齐方法和微调边界。

## 默认学习顺序

1. [预训练与 SFT：从 base model 到 instruction model](./01-pretraining-sft-overview.md)
2. [偏好对齐：RLHF、DPO 与 KL 约束](./02-preference-alignment-rlhf-dpo.md)
3. [LoRA、QLoRA、蒸馏与模型合并](./03-lora-qlora-distillation.md)
4. [模型演进：BERT、GPT、T5 给今天留下了什么](./04-model-evolution-bert-gpt-t5.md)

## 学前检查

| 如果你不懂 | 先补 |
|------------|------|
| Decoder-only 为什么适合生成 | [架构变体](../04-transformer-foundations/07-transformer-architecture-variants.md) |
| CLM/MLM 的差异 | [架构变体的训练目标](../04-transformer-foundations/07-transformer-architecture-variants.md) |
| loss 和反向传播 | [反向传播与梯度问题](../foundations/deep-learning/02-backprop-gradient-problems.md) |

## 这个模块的主线

```text
预训练: 学语言和世界知识
SFT: 学会按指令回答
偏好对齐: 学会更符合人类偏好
微调/蒸馏: 适配任务、压缩模型或迁移能力
```

## 深入参考

- [旧版 LLM 训练三阶段](../06-llm-core/01-training-pipeline.md)
- [旧版对齐技术](../06-llm-core/02-alignment.md)
- [旧版微调与蒸馏](../06-llm-core/06-fine-tuning-distillation.md)
- [旧版预训练模型历史](../05-pretrained-models/)
