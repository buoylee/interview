# 6.2 对齐技术 RLHF→DPO→GRPO（Day 5-6）⭐⭐⭐

> **一句话定位**：对齐技术从 RLHF(PPO) 到 DPO 到 GRPO 不断简化，核心目标不变——让模型生成人类偏好的回答。

---

## 目录

- [1. RLHF (PPO)](#1-rlhf-ppo)
- [2. DPO](#2-dpo)
- [3. 其他对齐方法](#3-其他对齐方法)
- [4. 对比总结](#4-对比总结)
- [5. 面试常问](#5-面试常问)

---

## 1. RLHF (PPO)

### 1.1 完整流程

```
Step 1: 收集偏好数据
  同一 prompt → 生成多个回答 → 人类标注排序
  例: prompt "什么是AI?"
  回答 A > 回答 B > 回答 C（人类排序）

Step 2: 训练 Reward Model (RM)
  RM 学习预测人类偏好：RM(好回答) > RM(差回答)
  损失: L = -log σ(RM(y_w) - RM(y_l))  (Bradley-Terry 模型)
  y_w = 更好的回答, y_l = 更差的回答

Step 3: PPO 优化
  目标 = max E[RM(y)] - β × D_KL(π_θ || π_ref)
  用 PPO 算法更新 LLM 参数
```

### 1.2 RLHF 的问题

```
1. 训练复杂：需要同时维护 4 个模型
   - Policy Model (正在训练的 LLM)
   - Reference Model (SFT 后的 LLM, 冻结)
   - Reward Model
   - Value Model (PPO 需要)
   → 显存消耗巨大

2. 训练不稳定：RL 训练本身就不稳定 + PPO 超参数敏感
3. Reward Hacking：模型可能学会欺骗 RM
```

---

## 2. DPO ⭐⭐

### 2.1 核心思想

```
DPO = Direct Preference Optimization (2023)

关键洞察：RLHF 的最优解有闭式形式！
  不需要训练 Reward Model + 不需要 PPO
  直接从偏好数据优化 LLM

RLHF: 偏好数据 → 训 RM → PPO 优化 LLM
DPO:  偏好数据 → 直接优化 LLM ← 跳过 RM 和 PPO！
```

### 2.2 损失函数

```
L_DPO = -log σ(β × [log π_θ(y_w|x)/π_ref(y_w|x) - log π_θ(y_l|x)/π_ref(y_l|x)])

直觉：
  增大好回答 y_w 的概率（相对于参考模型）
  减小差回答 y_l 的概率（相对于参考模型）
  β 控制约束强度
```

### 2.3 DPO 的优势

| | RLHF (PPO) | DPO |
|--|-----------|-----|
| 需要 RM | ✅ | ❌ |
| 需要 RL | ✅ (PPO) | ❌ (纯监督学习) |
| 模型数量 | 4 个 | 2 个 (π_θ + π_ref) |
| 训练稳定性 | 差 | ⭐ 好 |
| 实现复杂度 | 高 | ⭐ 低（和 SFT 一样简单）|
| 效果 | 好 | 接近 RLHF |

---

## 3. 其他对齐方法

| 方法 | 年份 | 核心思想 | 特点 |
|------|------|---------|------|
| **KTO** | 2024 | 只需要 👍/👎，不需要配对 | 数据要求最低 |
| **ORPO** | 2024 | 统一 SFT + 偏好优化 | 一步完成 |
| **SimPO** | 2024 | 简化 DPO，不需要参考模型 | 更简单 |
| **GRPO** ⭐ | 2024 | 组内相对排序 | DeepSeek 使用 |
| **Constitutional AI** | 2023 | AI 自我监督修正 | Anthropic/Claude |

### 3.1 GRPO (Group Relative Policy Optimization)

```
DeepSeek 使用的方法：

1. 同一个 prompt 生成 G 个回答
2. 每个回答用 RM 打分
3. 组内相对排序：高分 - 均值 → 正优势，低分 - 均值 → 负优势
4. 用优势值加权更新策略

无需 Value Model → 比 PPO 少一个模型 → 更高效

优势函数：Â = (r_i - mean(r)) / std(r)  (标准化)
```

### 3.2 Constitutional AI (Anthropic)

```
让 AI 自我改进：

1. 模型生成回答
2. 模型自己评判回答是否符合"宪法"（一组原则）
3. 模型修改不符合原则的回答
4. 用修改后的数据做 RLHF

"宪法"例：
  - "回答应该是有帮助的"
  - "回答不应该包含有害信息"
  - "如果不确定，应该说明不确定"

减少对人类标注的依赖
```

---

## 4. 对比总结

```
复杂度递减：
  RLHF(PPO) → DPO → SimPO → KTO
  4模型+RL    2模型    1模型    不需要配对

效果趋势：
  RLHF ≈ DPO > SimPO ≈ KTO（但差距越来越小）

工业实践：
  OpenAI: RLHF(PPO)
  Meta (LLaMA): DPO
  DeepSeek: GRPO
  Anthropic: Constitutional AI + RLHF
```

---

## 5. 面试常问

### Q1: RLHF 和 DPO 的区别？

**答**：RLHF 需要先训练 Reward Model 再用 PPO 做 RL 优化（4 个模型），DPO 跳过 RM 和 RL，直接从偏好数据优化模型（2 个模型）。DPO 更简单稳定，效果接近 RLHF。

### Q2: DPO 的损失函数直觉是什么？

**答**：增大好回答的概率、减小差回答的概率，同时通过参考模型的比率隐式地加入 KL 约束。本质上是在做一个相对的二分类：让模型更偏好好回答而不是差回答。

### Q3: DeepSeek 用什么对齐方法？

**答**：GRPO（Group Relative Policy Optimization）。对同一个 prompt 生成一组回答，用 RM 打分后只看组内相对排名（而不是绝对分数），消除了对 Value Model 的需求。

---

> ⬅️ [上一节：训练三阶段](./01-training-pipeline.md) | [返回概览](./README.md) | ➡️ [下一节：Scaling Law](./03-scaling-law.md)
