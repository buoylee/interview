# 3.5 受控生成 & 结构化输出（Day 9-10）

> **一句话定位**：LLM 怎么输出 JSON？Function Calling 怎么训练的？JSON Mode 底层是什么？这节回答这些你在 Agent 开发中天天使用的问题。

---

## 工程师导读

> **面试优先级：⭐⭐** — Agent 开发岗位的加分项
>
> **为什么 LLM 工程师要懂这些？**
> - 你每天用 Function Calling 和 JSON Mode — 这里讲它们背后的原理
> - 面试区分度话题："JSON Mode 底层是怎么实现的？" — 大部分候选人答不好
> - 理解 Logit Processor 统一框架能帮你理解推理引擎（vLLM）的工作方式
>
> **本节核心要点**：
> 1. JSON Mode = Constrained Decoding = 每步只允许选"合法"的 token
> 2. Function Calling = 通过 SFT 数据教会模型输出结构化工具调用
> 3. Temperature/Top-p/重复惩罚 都是 Logit Processor — 统一框架处理 logits
>
> **先修**：[04-语言模型 & 解码](./04-language-model-decoding.md)

---

## 目录

- [1. 为什么需要受控生成](#1-为什么需要受控生成)
- [2. Constrained Decoding 约束解码](#2-constrained-decoding-约束解码)
- [3. Grammar-guided Generation](#3-grammar-guided-generation)
- [4. Function Calling 训练机制](#4-function-calling-训练机制)
- [5. Logit Processor 统一框架](#5-logit-processor-统一框架)
- [6. 结构化输出的演进](#6-结构化输出的演进)
- [7. 面试常问](#7-面试常问)

---

## 1. 为什么需要受控生成

### 1.1 LLM 的自由文本问题

```
你让 LLM 返回 JSON：
  "请以 JSON 格式返回 name 和 age"

LLM 可能回答：
  ❌ 当然！这是结果：{"name": "张三", "age": 25}
  ❌ {"name": "张三", "age": "二十五"}  ← age 应该是数字
  ❌ {"name": "张三",\n"age": 25       ← 格式不完整
  ✅ {"name": "张三", "age": 25}
```

### 1.2 三个层次的控制

```
1. Prompt 约束：在提示词中说明输出格式 → 不保证遵循
2. 解码约束：在生成过程中限制 token 选择 → 保证格式正确 ⭐
3. 微调约束：训练模型学会输出特定格式 → 最自然
```

---

## 2. Constrained Decoding 约束解码

### 2.1 核心思想

```
正常解码：从全部词表中选 token
约束解码：在每一步，只允许选择 "合法" 的 token

例：输出 JSON 时
  已生成 '{"name": '
  下一个 token 必须是 '"'（JSON 字符串必须用引号）
  → 把所有非 '"' 的 token 概率设为 -∞（mask 掉）
  → softmax 后概率为 0
  → 保证只会选 '"'
```

### 2.2 工作方式

```
Step 1: 模型输出 logits（所有 token 的分数）
Step 2: 约束处理器检查当前状态，确定哪些 token 合法
Step 3: 把不合法的 token 的 logit 设为 -∞
Step 4: softmax 后只有合法 token 有概率
Step 5: 从合法 token 中采样/选最大的

logits: [2.1, 0.5, -1.0, 3.2, ...]
mask:   [  1,   0,    0,   1, ...]     ← 只有位置 0 和 3 合法
result: [2.1, -∞,   -∞,  3.2, ...]
→ softmax → 只从位置 0 和 3 中选
```

---

## 3. Grammar-guided Generation

### 3.1 用 CFG/正则约束

```
定义一个语法（如 JSON Schema）：
  object → "{" pairs "}"
  pairs → pair ("," pair)*
  pair → string ":" value
  value → string | number | object | array | "true" | "false" | "null"

在每个解码步骤，用语法状态机确定哪些 token 合法
```

### 3.2 实际工具

| 工具 | 方法 | 适用 |
|------|------|------|
| **Outlines** | 正则表达式 → 有限状态机 | 通用结构化输出 |
| **llama.cpp** grammar | BNF 语法 | C++ 推理引擎 |
| **Guidance** (Microsoft) | 模板 + 约束 | Python SDK |
| **vLLM** structured output | JSON Schema | 推理服务 |
| **OpenAI JSON Mode** | 内置 | API 调用 |

### 3.3 Outlines 示例原理

```
正则表达式: \d{4}-\d{2}-\d{2}  (日期格式 YYYY-MM-DD)

1. 编译正则 → 有限状态自动机 (FSA)
2. 每个状态对应一组合法的 token
3. 解码时根据当前 FSA 状态 mask 不合法 token

状态 0: 只允许 '0'-'9'
状态 1: 只允许 '0'-'9'
...
状态 4: 只允许 '-'
...

保证输出一定匹配正则表达式！100% 可靠
```

---

## 4. Function Calling 训练机制

### 4.1 Function Calling 是什么？

```
让 LLM 在需要时输出结构化的函数调用而不是自然语言：

用户: "北京今天天气怎么样？"
LLM 输出:
  {
    "function": "get_weather",
    "arguments": {"city": "北京", "date": "今天"}
  }

系统调用 get_weather("北京", "今天") → "晴天, 25°C"
LLM 再用结果回答: "北京今天晴天，25 度。"
```

### 4.2 怎么训练的？⭐

```
关键：SFT 数据格式

训练样本：

<system>
你有以下工具可用：
[{"name": "get_weather", "parameters": {"city": "string", "date": "string"}}]
</system>

<user>北京今天天气怎么样？</user>

<assistant>
<tool_call>
{"name": "get_weather", "arguments": {"city": "北京", "date": "今天"}}
</tool_call>
</assistant>

<tool_result>晴天, 25°C</tool_result>

<assistant>北京今天晴天，气温 25℃。</assistant>
```

### 4.3 训练要素

| 要素 | 说明 |
|------|------|
| **特殊 token** | `<tool_call>`, `<tool_result>` 等标记开始/结束 |
| **SFT 数据** | 大量的 (query, tool_call, result, answer) 四元组 |
| **Schema 注入** | System prompt 中放工具定义（JSON Schema） |
| **多工具选择** | 模型学会根据 query 选择正确的工具 |
| **决定是否需要工具** | 模型学会判断：直接回答 vs 调用工具 |

### 4.4 Parallel Function Calling

```
一次输出多个函数调用：

用户: "北京和上海今天天气怎么样？"
LLM:
  <tool_call>
  [
    {"name": "get_weather", "arguments": {"city": "北京"}},
    {"name": "get_weather", "arguments": {"city": "上海"}}
  ]
  </tool_call>

这也是通过 SFT 数据教会的
```

---

## 5. Logit Processor 统一框架

### 5.1 概念

```
所有影响 token 选择的操作都可以看作 Logit Processor：

原始 logits → [处理器1] → [处理器2] → [处理器3] → 修改后的 logits → softmax

常见处理器：
  - Temperature: logits = logits / T
  - Top-k: 只保留 top-k 的 logit
  - Top-p: 只保留累积概率 ≥ p 的 logit
  - Repetition Penalty: 降低已出现 token 的 logit
  - JSON Constraint: mask 不合法的 token
```

### 5.2 处理链

```
推理框架（如 vLLM）中的实现：

logits = model.forward(input_ids)

for processor in logit_processors:
    logits = processor(logits, context)

# 处理器列表可能包含：
# 1. TemperatureProcessor(T=0.7)
# 2. TopPProcessor(p=0.9)
# 3. RepetitionPenaltyProcessor(penalty=1.1)
# 4. JSONConstraintProcessor(schema=...)
```

---

## 6. 结构化输出的演进

```
2022: Prompt 约束 → "请用 JSON 格式回答" → 不可靠

2023: 解码约束 → JSON Mode、Outlines → 格式可靠但内容不一定
      同时: Function Calling SFT → 模型学会输出工具调用

2024: Structured Outputs → JSON Schema 级别的保证
      OpenAI structured_output 参数
      → 同时用微调(知道格式) + 约束解码(保证格式)

趋势：
  Prompt约束（不可靠） → 解码约束（可靠但笨） → 微调+解码（又聪明又可靠）
```

---

## 7. 面试常问

### Q1: JSON Mode 底层是怎么实现的？

**答**：通过 Constrained Decoding。在每个解码步骤，根据 JSON 语法的当前状态确定哪些 token 合法，把不合法的 token 的 logit 设为 -∞，保证输出一定是合法 JSON。可以用 CFG（上下文无关文法）或正则表达式对应的有限状态机来跟踪状态。

### Q2: Function Calling 模型怎么训练的？

**答**：通过 SFT（监督微调）。训练数据包含特殊格式的 (用户输入, 工具定义, 工具调用, 工具结果, 最终回答) 序列。模型学会：(1) 判断是否需要调用工具 (2) 选择正确的工具 (3) 输出正确格式的参数 (4) 用工具结果生成最终回答。

### Q3: Prompt 约束和 Constrained Decoding 的区别？

**答**：
- **Prompt 约束**：在提示词中要求格式 → 模型可能忽略 → 不可靠
- **Constrained Decoding**：在解码过程中强制约束 → 100% 保证格式 → 可靠
- 但 Constrained Decoding 只保证格式，不保证内容正确
- 最佳方案：微调让模型理解格式 + 约束解码保证格式正确

### Q4: Temperature、Top-k、Top-p、Repetition Penalty 的关系？

**答**：它们都是 Logit Processor，按顺序处理 logits：
1. Temperature 调整分布平坦度
2. Top-k 截掉低概率的 token
3. Top-p 自适应截掉
4. Repetition Penalty 降低已出现 token
- 最终修改后的 logits 做 softmax → 采样

---

## 📖 推荐学习路径

1. 理解 JSON Mode = Constrained Decoding 的本质
2. Function Calling 的 SFT 数据格式是面试区分度话题
3. 对 Logit Processor 统一框架有全局理解

## ⏭️ 下一节预告

本阶段最后一节：**Tokenization 算法深度解析**。BPE 是面试常问的算法题，经常要求你讲清楚训练和推理的完整流程。同时 Tokenization 直接影响 LLM 的多语言能力和成本 — 知道为什么中文比英文贵吗？答案就在分词。

> ⬅️ [上一节：语言模型 & 解码](./04-language-model-decoding.md) | [返回概览](./README.md) | ➡️ [下一节：Tokenization 算法](./06-tokenization-deep-dive.md)
