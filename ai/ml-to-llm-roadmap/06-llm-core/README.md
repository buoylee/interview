# 阶段 6：大模型 LLM 核心知识（旧版参考）

> **新版路线说明**：这个旧目录覆盖很多 LLM 核心主题，但第一次学习不再建议顺序读完。训练/对齐/微调已经拆入 [训练、对齐与微调](../05-training-alignment-finetuning/)；推理部署已经拆入 [推理优化、部署与成本](../06-inference-deployment-cost/)；评估安全会在新的主线模块中继续拆分。

## 按主题查阅

| 你想查什么 | 旧版参考 |
|------------|----------|
| 预训练、SFT、RLHF 基础 | [01-training-pipeline.md](./01-training-pipeline.md) |
| RLHF、DPO、GRPO、Constitutional AI | [02-alignment.md](./02-alignment.md) |
| Scaling Law 与涌现能力 | [03-scaling-law.md](./03-scaling-law.md) |
| 分布式训练 DP/TP/PP/ZeRO | [04-distributed-training.md](./04-distributed-training.md) |
| 推理优化、KV Cache、vLLM、长上下文 | [05-inference-optimization.md](./05-inference-optimization.md) |
| LoRA、QLoRA、蒸馏、模型合并 | [06-fine-tuning-distillation.md](./06-fine-tuning-distillation.md) |
| MoE 混合专家 | [07-moe.md](./07-moe.md) |
| 推理模型、多模态、Code LLM | [08-advanced-topics.md](./08-advanced-topics.md) |
| 数据工程与 LLM 评估 | [09-data-evaluation.md](./09-data-evaluation.md) |
| AI 安全与幻觉 | [10-safety-hallucination.md](./10-safety-hallucination.md) |
| 关键模型族总览 | [11-model-families.md](./11-model-families.md) |
| Test-time Compute Scaling | [12-test-time-compute.md](./12-test-time-compute.md) |
| 长上下文技术 | [13-long-context.md](./13-long-context.md) |
| LLM-as-Judge 评估 | [14-llm-as-judge.md](./14-llm-as-judge.md) |
| 端侧/小模型部署 | [15-edge-deployment.md](./15-edge-deployment.md) |

## 新版默认入口

如果你是第一次补 LLM 底层，不要从这个目录按 Day 1 到 Day 25 顺序读。先走已经系统化的新主线：

- [训练、对齐与微调](../05-training-alignment-finetuning/)
- [推理优化、部署与成本](../06-inference-deployment-cost/)

后续评估安全模块完成后，本页会继续补充对应新版入口。
