# 阶段 5：预训练语言模型时代（旧版参考）

> **新版路线说明**：这个目录保留 BERT、GPT、T5 等历史材料。默认学习路径中，模型演进已经压缩进 [训练、对齐与微调](../05-training-alignment-finetuning/)，这里只作为深入参考。

## 旧版参考索引（非默认学习路径）

| 文件 | 主题 | 什么时候查 |
|------|------|------------|
| [01-bert-family.md](./01-bert-family.md) | BERT 家族 | 想深入看 MLM、RoBERTa、DeBERTa、DistilBERT 时 |
| [02-gpt-evolution.md](./02-gpt-evolution.md) | GPT 演进 | 想补 GPT-1/2/3、In-Context Learning 的历史细节时 |
| [03-milestones.md](./03-milestones.md) | 里程碑 & 范式转换 | 想补 T5、CLIP、自监督学习方法时 |

## 这批材料怎么使用

第一次学习不建议在这里按顺序读一周。新版主线已经把面试和工程决策最需要的模型历史压缩到：

- [模型演进：BERT、GPT、T5 给今天留下了什么](../05-training-alignment-finetuning/04-model-evolution-bert-gpt-t5.md)

读完新版主线后，如果你还想知道某个模型家族的具体改进，再回到本目录查旧版长文。

## 旧版核心脉络

```text
2018: BERT + GPT-1 → 预训练+微调范式成型
2019: GPT-2 → Zero-shot，不用微调也能做任务
      RoBERTa → "BERT 没训练够" → Scaling 的早期信号
2020: GPT-3 (175B) → In-Context Learning，Few-shot 能力涌现
2019/2020: T5 → 统一 text-to-text
2021: CLIP → 图文对齐，多模态开端

范式转换:
  特征工程+浅层模型 → 预训练+微调(BERT) → 预训练+Prompt(GPT-3) → 预训练+SFT+RLHF(ChatGPT)
```

> ⬅️ 回到新版主线：[训练、对齐与微调](../05-training-alignment-finetuning/)
