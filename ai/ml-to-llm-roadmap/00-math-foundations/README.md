# 阶段 0：数学基础速通（1 周）

> **新版路线说明**：这个目录是解锁后的数学深入资料，不是默认主线。如果你是从 Transformer 主线卡在向量、矩阵、点积、logits 或 softmax，先读 [Transformer 最小数学](../foundations/math-for-transformer/)；读完再回到这里补完整数学直觉。

> **目标**：不需要精通数学，理解直觉即可。学到后面遇到不懂的公式回来查。
>
> **你的定位**：已有 AI 应用开发经验（RAG、Agent、LangChain），这里补的是「为什么是这样」的底层直觉。

---

## 📂 本阶段内容

| 文件 | 主题 | 预计时间 | 后续关联 |
|------|------|---------|---------|
| [01-linear-algebra.md](./01-linear-algebra.md) | 线性代数 | Day 1-2 | Embedding、Attention、LoRA、PCA |
| [02-probability.md](./02-probability.md) | 概率与统计 | Day 3-4 | 语言模型、贝叶斯、MLE/MAP |
| [03-calculus.md](./03-calculus.md) | 微积分 | Day 5 | 反向传播、梯度下降 |
| [04-information-theory.md](./04-information-theory.md) | 信息论 | Day 6-7 | 交叉熵损失、KL 散度(RLHF)、互信息 |

---

## 🎯 学习原则

1. **直觉优先**：每个概念先理解「它在干什么」，再看公式
2. **联系应用**：每个数学概念都标注它在 ML/LLM 中的用途
3. **不死磕推导**：能看懂公式含义即可，不需要手推
4. **按需深入**：遇到后续阶段需要的数学再回来补

## 什么时候读旧数学资料

| 你已经读懂 | 再回来看 |
| --- | --- |
| 向量、矩阵、点积的最小直觉 | [线性代数](./01-linear-algebra.md) |
| logits、softmax、概率分布的最小直觉 | [概率与统计](./02-probability.md) |
| 反向传播为什么需要梯度 | [微积分](./03-calculus.md) |
| 交叉熵、KL、信息量在训练和对齐中的意义 | [信息论](./04-information-theory.md) |

## 📖 推荐资源

| 资源 | 覆盖内容 | 特点 |
|------|---------|------|
| [3Blue1Brown《线性代数的本质》](https://www.youtube.com/playlist?list=PLZHQObOWTQDPD3MizzM2xVFitgF8hE_ab) | 线性代数 | 动画可视化，直觉极好 |
| [3Blue1Brown《微积分的本质》](https://www.youtube.com/playlist?list=PLZHQObOWTQDMsr9K-rj53DwVRMYO3t5Yr) | 微积分 | 同上 |
| [StatQuest](https://www.youtube.com/@statquest) | 概率统计 | 讲解简洁清晰 |
| Khan Academy | 全部 | 基础补漏 |
