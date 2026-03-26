# 6.11 关键模型族总览（Day 21）

> **一句话定位**：面试中常问「你了解哪些模型？有什么区别？」这节提供一张完整的模型地图。

---

## 1. 闭源模型

| 模型 | 公司 | 关键特点 |
|------|------|---------|
| **GPT-4/4o** | OpenAI | 最早的多模态大模型，综合最强 |
| **GPT-o1/o3** | OpenAI | 推理模型，Test-time Compute |
| **Claude 3.5 Sonnet** | Anthropic | 代码和长文档理解极强，Constitutional AI |
| **Gemini 2.0** | Google | 原生多模态，超长上下文 |

## 2. 开源模型

### 2.1 LLaMA 家族 (Meta)

```
LLaMA-1 (2023.02): 7B-65B, 首个开源强模型
LLaMA-2 (2023.07): 7B-70B, GQA, 开放商用
LLaMA-3 (2024.04): 8B-70B, 15T tokens, 效果跳跃式提升
LLaMA-3.1 (2024.07): 8B-405B, 最大开源模型

关键技术栈：RoPE + GQA + SwiGLU + RMSNorm
```

### 2.2 DeepSeek 家族 ⭐

```
DeepSeek-V2 (2024): MLA + MoE (160E, top6), 极低推理成本
DeepSeek-V3 (2024): MLA + MoE (256E, top8), 671B/$5.6M训练
DeepSeek-R1 (2025): 首个开源推理模型，纯 RL 产生 CoT

创新：MLA (多头潜在注意力)、GRPO、无辅助损失负载均衡
→ 面试常问：DeepSeek 的技术创新是什么？
```

### 2.3 Qwen 家族 (阿里)

```
Qwen-2.5: 0.5B-72B, 中文最强开源之一
Qwen-VL: 多模态
Qwen-Coder: 代码
中文+多语言支持好
```

### 2.4 Mistral

```
Mistral-7B: Sliding Window + GQA, 7B 效果超 LLaMA-2-13B
Mixtral-8x7B: MoE (8专家, top2), 47B参数/13B激活
Mistral Large: 闭源大模型

特点：精简高效，小模型做到大效果
```

## 3. 关键技术栈对比

```
模型         注意力     位置编码   FFN      归一化    对齐
LLaMA-3     GQA        RoPE      SwiGLU   RMSNorm  DPO
DeepSeek-V3  MLA        RoPE      SwiGLU   RMSNorm  GRPO
Qwen-2.5    GQA        RoPE      SwiGLU   RMSNorm  DPO
Mistral     GQA+SWA    RoPE      SwiGLU   RMSNorm  DPO
```

> 🔑 几乎所有现代开源 LLM 都用：RoPE + GQA + SwiGLU + RMSNorm

## 4. 面试常问

### Q1: 对比几个主流开源模型？

**答**：LLaMA (Meta) 奠定了开源基础；DeepSeek 在 MLA/MoE 上有独特创新，训练成本极低；Qwen 中文能力最强；Mistral 小模型做到大效果。技术栈趋同：RoPE+GQA+SwiGLU+RMSNorm。

### Q2: DeepSeek 有什么技术创新？

**答**：(1) MLA 多头潜在注意力（低秩压缩 KV-Cache）(2) 超大 MoE（256 专家）(3) GRPO 对齐 (4) DeepSeek-R1 用纯 RL 实现推理能力 (5) 训练成本极低（$5.6M for V3）。

---

> ⬅️ [上一节：AI 安全 & 幻觉](./10-safety-hallucination.md) | [返回概览](./README.md) | ➡️ [下一阶段：理论-应用桥接](../07-theory-practice-bridge/)
