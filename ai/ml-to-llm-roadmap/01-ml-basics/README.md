# 阶段 1：机器学习基础（旧版参考）

> **新版路线说明**：这个目录是解锁后的传统 ML 深入资料，不是进入 LLM 主线的硬性前置。第一次读 Transformer 时不需要先完整学习本目录；当你想补“模型如何学习、评估、泛化”时再回来。

> **目标**：掌握 ML 的核心概念和经典算法，理解「模型是怎么学习的」。这些概念是后续深度学习和大模型的根基。
>
> **你的定位**：你已经用过 ML 的成果（Embedding、分类模型），现在补齐「为什么这么做」的理论。

---

## 📂 本阶段内容

| 文件 | 主题 | 预计时间 | 后续关联 |
|------|------|---------|---------|
| [01-core-concepts.md](./01-core-concepts.md) | 核心框架 | Day 1-3 | 贯穿所有 ML/DL/LLM |
| [02-classic-algorithms.md](./02-classic-algorithms.md) | 经典算法 | Day 4-7 | 理解模型演进脉络 |
| [03-evaluation-tuning.md](./03-evaluation-tuning.md) | 模型评估 & 调优 | Day 8-10 | 模型选择、正则化 |

---

## 🎯 本阶段核心思想

```
数据 → 特征 → 模型 → 损失函数 → 优化 → 评估 → 迭代

这个流程从传统 ML 到 LLM 都没变过，变的只是规模和自动化程度。
```

## 什么时候回来看 ML 基础

| 你想补强 | 再回来看 |
| --- | --- |
| 模型、特征、损失、优化、训练/测试划分这些共同语言 | [核心框架](./01-core-concepts.md) |
| 传统模型如何从人工特征走向学习表示 | [经典算法](./02-classic-algorithms.md) |
| 评估、调参、过拟合、泛化这些工程判断 | [模型评估 & 调优](./03-evaluation-tuning.md) |

## 📖 推荐资源

| 资源 | 覆盖内容 | 特点 |
|------|---------|------|
| [StatQuest](https://www.youtube.com/@statquest) | 几乎所有经典算法 | 讲解极其清晰 |
| 吴恩达 ML Coursera | 核心概念 + 经典算法 | 体系化 |
| 《百面机器学习》 | 面试题 | 刷题用 |
| scikit-learn 文档 | 算法实现 | 代码参考 |

> 回到新版主线：[Transformer 必要基础](../04-transformer-foundations/) | 按卡点解锁：[Foundations 解锁层](../foundations/) | 旧版参考：[数学基础](../00-math-foundations/) / [深度学习基础](../02-deep-learning/)
