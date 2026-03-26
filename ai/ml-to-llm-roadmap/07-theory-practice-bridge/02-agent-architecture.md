# 7.2 Agent 架构理论（Day 5-7）

> **一句话定位**：用理论基础解释 ReAct、Planning、Tool Use、Multi-Agent 的设计原理。

---

## 1. Agent = LLM + 工具 + 记忆 + 规划

```
Agent 的四要素：
  Brain:   LLM（推理和决策）
  Tools:   外部工具（搜索、代码执行、API）
  Memory:  上下文/长期记忆
  Planning: 任务分解和执行策略
```

## 2. ReAct (Reasoning + Acting)

```
交替进行思考(Thought)和行动(Action)：

Question: "比较 GPT-4 和 Claude 3.5 的代码能力"

Thought 1: 我需要找到两者的代码能力评测数据
Action 1: search("GPT-4 vs Claude 3.5 coding benchmark")
Observation 1: [搜索结果...]

Thought 2: 根据搜索结果，GPT-4 在 HumanEval 上...
Action 2: search("Claude 3.5 HumanEval score")
Observation 2: [搜索结果...]

Thought 3: 综合对比后我可以回答了
Answer: GPT-4 在 HumanEval 上得分 X%，Claude 3.5 得分 Y%...

理论基础: Chain-of-Thought + In-Context Learning
  思考 = CoT 推理
  行动 = Tool Calling
  交替 = 允许中间反馈修正推理方向
```

## 3. Planning 规划

### 3.1 规划类型

| 类型 | 做法 | 特点 |
|------|------|------|
| **Sequential** | 一步步执行 | 简单但不灵活 |
| **DAG-based** | 有向图，允许并行 | 更高效 |
| **Tree Search** | 探索多条路径 | 更全面但更贵 |
| **Adaptive** | 根据反馈动态调整 | 最灵活 |

### 3.2 Plan-and-Execute

```
LLM 1 (Planner): 制定完整计划
  1. 搜索 GPT-4 的代码评测
  2. 搜索 Claude 3.5 的代码评测
  3. 对比分析两者差异
  4. 撰写比较报告

LLM 2 (Executor): 逐步执行，每步可能调用工具

优点: 规划和执行分离 -> 更可控
```

### 3.3 Planning 的具体算法

```
1. Tree-of-Thought (ToT)
   将推理建模为搜索树，用 BFS/DFS 搜索 + LLM 评估每个节点
   比线性 CoT 更全面，但计算量更大

2. Graph-of-Thought (GoT)
   允许思维节点之间有更复杂的关系（合并、循环）
   比 ToT 更灵活

3. Monte Carlo Tree Search (MCTS)
   AlphaGo 的思想用于 Agent Planning：
   Selection -> Expansion -> Simulation -> Backpropagation
   用模拟结果更新路径分数
```

## 4. Multi-Agent

### 4.1 为什么多 Agent？

```
单 Agent 问题:
  - 上下文越来越长 -> 质量下降
  - 单一角色难以处理复杂任务
  - 出错后难以恢复

Multi-Agent 解决:
  - 每个 Agent 负责子任务 -> 上下文更聚焦
  - 不同角色（Researcher、Coder、Reviewer）
  - 通过对话协作 -> 互相校验
```

### 4.2 模式

```
1. 顺序协作: Agent A -> Agent B -> Agent C
2. 对话协作: Agents 之间来回讨论
3. 层级:     Manager Agent 分配任务给 Worker Agents
4. 竞争:     多个 Agent 独立解决 -> 取最好结果
```

### 4.3 Multi-Agent 的通信协议

```
1. 共享消息队列: 所有 Agent 往同一个消息列表写入/读取
2. 点对点通信: Agent A 直接给 Agent B 发消息
3. 黑板系统 (Blackboard): 所有 Agent 读写一个共享的结构化状态

实际框架：
  LangGraph: 用图定义 Agent 间的消息流转
  CrewAI: 角色 + 任务 + 协作模式
  AutoGen: 对话式多 Agent 协作
```

## 5. 记忆系统

```
短期记忆: 对话上下文（Context Window 内）
长期记忆: 存储到外部系统（向量数据库、结构化存储）

长期记忆实现:
  回忆: 用 Embedding 检索相关历史（本质是 RAG！）
  反思: 定期总结历史对话 -> 压缩存储

理论连接: Agent 的记忆系统 = RAG 在对话历史上的应用
```

### 5.1 记忆类型细分

| 类型 | 说明 | 实现 |
|------|------|------|
| **对话记忆** | 最近 N 轮对话 / 摘要压缩 | Context Window / Summary Memory |
| **知识记忆** | 执行过程中学到的事实 | 向量数据库检索 |
| **经验记忆** | 类似任务的历史经验 | (任务, 过程, 结果) 三元组存储 |
| **工作记忆** | 当前任务的中间状态 | 结构化存储 (JSON/dict) |

## 6. Tool Use 的训练机制

### 6.1 Function Calling 的 SFT 数据

```
训练数据的核心结构：

1. System 中定义可用工具（名称、参数、描述）
2. 模型学会输出特殊格式表示"我要调用工具"
3. 工具执行结果作为 Observation 回传给模型
4. 模型根据结果继续生成

关键：模型不是"理解"工具，而是学会了输出特定格式的 token
  -> 本质是 SFT 让模型学会了一种新的输出模式
```

### 6.2 Constrained Decoding 在 Tool Use 中的作用

```
问题：模型输出的 JSON 可能格式错误（括号不匹配、类型错误）

Constrained Decoding 方案：
  在解码时用 CFG/JSON Schema 约束 token 选择
  -> 保证输出是合法的 JSON
  -> 保证函数名在允许列表中
  -> 保证参数类型正确

例：当前已生成 {"function": "get_weather", "args": {"city":
  下一个 token 只允许是字符串开头的引号
  -> 不可能生成 {"city": 123}
```

### 6.3 Parallel Tool Calling

```
进阶能力：模型一次调用多个工具

例：用户问 "北京和上海明天天气分别怎么样？"

串行：get_weather("北京") -> 等结果 -> get_weather("上海") -> 等结果
并行：同时调用 get_weather("北京") 和 get_weather("上海")

训练方式：SFT 数据中包含多工具调用的样本
输出格式：一次生成多个 tool_call 对象
```

## 7. 面试常问

### Q1: Agent 和普通 LLM 调用的区别？

**答**：普通 LLM 是一次性的输入->输出。Agent 有观察->思考->行动的循环，可以调用工具获取外部信息，根据反馈调整策略，维护记忆状态。

### Q2: ReAct 的原理？

**答**：交替进行推理(Thought)和行动(Action)。每步先思考需要什么信息，再执行动作（如搜索、计算），获取观察结果后继续思考。理论上是 CoT + Tool Calling 的结合。

### Q3: Function Calling 是怎么训练的？

**答**：通过 SFT 训练模型学会输出特定格式（包含函数名和参数的 JSON）。训练数据包含工具定义、调用示例和执行结果。模型本质上学会了一种新的输出模式，配合 Constrained Decoding 保证输出格式正确。

### Q4: Multi-Agent 系统有哪些协作模式？各适用什么场景？

**答**：四种主要模式：(1) 顺序协作——流水线任务如 Research->Coding->Review (2) 对话协作——需要讨论和辩论的决策任务 (3) 层级——Manager 分配任务给 Workers，适合可拆解的复杂任务 (4) 竞争——多个 Agent 独立解决取最优，适合有明确评估标准的任务。

### Q5: Agent 的记忆系统怎么设计？

**答**：分四层：(1) 对话记忆——Context Window 内的短期上下文 (2) 知识记忆——用向量数据库存储和检索学到的事实 (3) 经验记忆——存储历史任务的执行过程和结果 (4) 工作记忆——当前任务的中间状态。长期记忆本质是 RAG 在对话历史和知识上的应用。

---

> ⬅️ [上一节：RAG 深度](./01-rag-deep-dive.md) | [返回概览](./README.md) | ➡️ [下一节：Prompt 理论](./03-prompt-engineering.md)
