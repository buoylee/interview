# AI Engineer 面试导向：ML → LLM 系统学习路线

> **定位**：你做过一些 RAG / Agent / LLM 应用开发，但对 LLM 底层只有基础理解。本路线从 AI Engineer 综合面试能力出发，反向补齐 Transformer、训练、推理、评估和系统设计知识。

## 如何使用这套路线

| 你的目标 | 推荐路径 |
|---------|---------|
| 面试在 2 周内 | 先走「面试冲刺路径」，只看主线模块和 review notes |
| 想系统补底层 | 走「系统学习路径」，主线遇到不懂再回 foundations |
| 正在做 RAG / Agent 项目 | 从 RAG、Agent、生成控制三个模块开始，再补 Transformer |

## 新路线目标结构（迁移中）

下面是迁移完成后的目标结构；首批 Transformer 系统学习样板和复习笔记已创建，Deep Learning 补课已系统化，其他模块后续按这个结构继续迁移。

```text
01 RAG 与检索系统
02 Agent 与工具调用
03 生成控制与结构化输出
04 Transformer 必要基础
05 训练、对齐与微调
06 推理优化、部署与成本
07 评估、安全与生产排查
08 系统设计与项目叙事
09 面试复习笔记
foundations 按需补课
```

## 第一批迁移成果

| 模块 | 内容 | 入口 | 状态 |
|------|------|------|------|
| Transformer 系统学习样板 | 从 AI Engineer 视角系统理解 Transformer | [04-transformer-foundations](./ml-to-llm-roadmap/04-transformer-foundations/) | 已创建 |
| Deep Learning 补课 | 支撑 Transformer 的神经网络基础 | [foundations/deep-learning](./ml-to-llm-roadmap/foundations/deep-learning/) | 已系统化 |
| Transformer 面试复习 | 30 秒答案、追问、易混点和项目连接 | [03-transformer-core-cheatsheet](./ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md) | 已创建 |

## 面试冲刺路径

> 这条路径适合先冲 AI Engineer 面试：先走 Transformer 系统学习模块，再用面试路径和速记文档复盘。旧版 RAG、Agent 和系统设计材料只作为可选参考。

1. Transformer 系统学习模块：[04-transformer-foundations](./ml-to-llm-roadmap/04-transformer-foundations/)
2. Transformer 面试阅读路径：[interview-paths/ai-engineer-transformer.md](./ml-to-llm-roadmap/interview-paths/ai-engineer-transformer.md)
3. Transformer 复习笔记：[09-review-notes/03-transformer-core-cheatsheet.md](./ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md)

### 可选旧版参考

下面材料尚未迁入新路线，只作为扩展查阅，不属于默认冲刺步骤：

- 旧版 Transformer 核心材料：[04/01-transformer-core.md](./ml-to-llm-roadmap/04-transformer-architecture/01-transformer-core.md)
- 旧版 RAG 深度材料：[07/01-rag-deep-dive.md](./ml-to-llm-roadmap/07-theory-practice-bridge/01-rag-deep-dive.md)
- 旧版 Agent 架构材料：[07/02-agent-architecture.md](./ml-to-llm-roadmap/07-theory-practice-bridge/02-agent-architecture.md)
- 旧版系统设计材料：[08/02-system-design.md](./ml-to-llm-roadmap/08-interview-synthesis/02-system-design.md)

## 系统学习路径

1. 从主线模块开始，不从数学开始。
2. 每篇已迁移主线教程的「学前检查」会告诉你缺哪个基础。
3. 缺基础时进入 `foundations/`；Deep Learning 前置知识已拆成小节，补完再回主线。
4. 每个模块迁移完成后，用对应 `09-review-notes/` 做面试复盘。

## 迁移说明

旧的 `00-08` 学科式目录暂时保留，避免丢失已有材料。新路线会逐步把有价值内容迁入能力模块、foundations 和 review notes。迁移完成前，旧目录可以作为参考资料，但不再作为默认学习入口。

## 旧版目录索引

| 旧目录 | 内容 |
|--------|------|
| [00-math-foundations](./ml-to-llm-roadmap/00-math-foundations/) | 数学基础 |
| [01-ml-basics](./ml-to-llm-roadmap/01-ml-basics/) | 机器学习基础 |
| [02-deep-learning](./ml-to-llm-roadmap/02-deep-learning/) | 深度学习基础 |
| [03-nlp-embedding-retrieval](./ml-to-llm-roadmap/03-nlp-embedding-retrieval/) | NLP、Embedding 与检索 |
| [04-transformer-architecture](./ml-to-llm-roadmap/04-transformer-architecture/) | Transformer 架构 |
| [05-pretrained-models](./ml-to-llm-roadmap/05-pretrained-models/) | 预训练语言模型 |
| [06-llm-core](./ml-to-llm-roadmap/06-llm-core/) | 大模型核心 |
| [07-theory-practice-bridge](./ml-to-llm-roadmap/07-theory-practice-bridge/) | 理论与应用桥接 |
| [08-interview-synthesis](./ml-to-llm-roadmap/08-interview-synthesis/) | 面试串联 |
