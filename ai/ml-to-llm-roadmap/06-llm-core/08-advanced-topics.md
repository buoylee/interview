# 6.8 推理模型 + 多模态 + Code LLM（Day 15-17）

> **一句话定位**：三个前沿方向——o1 式推理增强、多模态理解与生成、代码模型的特殊性。

---

## 1. 推理模型 (Reasoning Models) ⭐⭐

### 1.1 核心思想

```
传统 LLM：想到什么说什么（快思维）
推理模型：先想再说，想多久取决于问题难度（慢思维）

代表：OpenAI o1/o3, DeepSeek-R1

实现方式：
1. Chain-of-Thought 训练：大量"展示思考过程"的数据
2. 强化学习：奖励正确的最终答案（过程奖励模型 PRM）
3. Test-time Compute Scaling：推理时花更多 token 思考
```

### 1.2 DeepSeek-R1 的训练

```
纯 RL 发现：只用 RL 训练（不先做 SFT）→ 模型自发学会了 CoT！

训练流程：
  Base Model → RL (GRPO) → 自发产生思维链 → 蒸馏到小模型

关键发现：RL reward 只给最终答案 → 模型自己发现"多想一步"更容易得对
```

### 1.3 Process vs Outcome Reward

```
Outcome Reward：只看最终答案对不对
  → 简单但信号稀疏

Process Reward (PRM)：评估每一步推理是否正确
  → 信号密集但标注成本高
  → OpenAI 的 o1 用到了 PRM
```

## 2. 多模态 LLM ⭐

### 2.1 架构

```
通用架构:
  [图像] → Vision Encoder (CLIP ViT) → 图像 token → 投影层 → 
                                                          → LLM → 输出
  [文本] → Tokenizer → 文本 token ────→ Embedding → 

关键：把图像转成和文本类似的"token"，让 LLM 统一处理
```

### 2.2 代表模型

| 模型 | 公司 | 特点 |
|------|------|------|
| **GPT-4V/4o** | OpenAI | 原生多模态，效果最好 |
| **LLaVA** | 开源 | 简洁架构：CLIP + LLM + 投影层 |
| **Qwen-VL** | 阿里 | 开源多模态 |
| **Claude 3.5** | Anthropic | 文档/图表理解强 |

### 2.3 训练流程

```
Phase 1: 图文对齐预训练
  冻结 Vision Encoder + LLM，只训练投影层
  数据：图文对（简单描述）
  
Phase 2: 视觉指令微调
  解冻 LLM（或 LoRA），保持 Vision Encoder 冻结
  数据：视觉问答对
```

## 3. Code LLM

### 3.1 代码模型的特殊性

```
代码不同于自然语言：
  - 语法严格（一个括号不对就报错）
  - 可执行验证（运行就知道对不对）
  - 结构化强（AST、缩进、作用域）
  - 长距离依赖（函数调用、变量引用）
```

### 3.2 训练方式

```
1. 代码预训练：在大量代码语料上继续预训练
2. Fill-in-Middle (FIM)：
   def foo():
     <PREFIX>     ← 前文
     [FILL]       ← 模型补全中间
     <SUFFIX>     ← 后文
   → 更好的代码补全

3. 执行反馈：
   生成代码 → 运行测试 → 用通过率作为奖励（RL）
```

### 3.3 代表模型

| 模型 | 特点 |
|------|------|
| **DeepSeek-Coder V2** | 开源最强代码模型之一 |
| **CodeLlama** | Meta，基于 LLaMA |
| **Qwen-Coder** | 阿里 |
| **Claude (Sonnet)** | 代码能力极强 |
| **Cursor** | 基于大模型的 IDE |

## 4. 面试常问

### Q1: o1/R1 这类推理模型和普通 LLM 区别？

**答**：推理模型在推理时生成隐式思维链（Test-time Compute Scaling），花更多 token 思考。普通 LLM 直接输出答案。DeepSeek-R1 通过纯 RL 自发学到了 CoT 推理，不需要预先设计 CoT 格式。

### Q2: 多模态 LLM 怎么处理图像？

**答**：用 Vision Encoder（通常是 CLIP 的 ViT）把图像编码成一组 token，通过投影层映射到 LLM 的嵌入空间中，和文本 token 拼接后统一由 LLM 处理。训练分两阶段：先对齐图文空间，再做视觉指令微调。

---

> ⬅️ [上一节：MoE](./07-moe.md) | [返回概览](./README.md) | ➡️ [下一节：数据工程 & 评估](./09-data-evaluation.md)
