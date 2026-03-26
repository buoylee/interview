# 2.4 CNN 卷积神经网络（Day 8-9）

> **一句话定位**：CNN 引入了「局部连接 + 权值共享」的思想来处理空间数据。虽然 NLP 主要用 Transformer，但 **Residual Connection 是 CNN 送给 Transformer 的最重要礼物**。

---

## 目录

- [1. 卷积的直觉](#1-卷积的直觉)
- [2. CNN 核心组件](#2-cnn-核心组件)
- [3. 经典 CNN 演进](#3-经典-cnn-演进)
- [4. ResNet 与 Residual Connection](#4-resnet-与-residual-connection)
- [5. CNN 与 Transformer 的关系](#5-cnn-与-transformer-的关系)
- [6. 面试常问](#6-面试常问)

---

## 1. 卷积的直觉

### 1.1 MLP 处理图像的问题

```
一张 224×224×3 的图像 → 展平成 150528 维向量
第一层隐藏层 1024 个神经元 → 需要 150528 × 1024 ≈ 1.5 亿参数！

问题：
1. 参数太多 → 容易过拟合
2. 忽略了空间结构 → 相邻像素的关系丢失
3. 不具有平移不变性 → 猫在左上角和右下角是不同的输入
```

### 1.2 卷积的解决方案

```
不是每个神经元连接所有输入，而是：
  - 局部连接：每个神经元只看一小块区域（卷积核/滤波器）
  - 权值共享：同一个滤波器在整张图上滑动，用同一组权重
  - 平移不变性：猫在哪里都用同一个检测器
```

**直觉**：卷积核 = 特征检测器（检测边缘、纹理、形状等）。

---

## 2. CNN 核心组件

### 2.1 卷积层 (Convolution Layer)

```
输入: (H × W × C_in)
卷积核: (k × k × C_in)，有 C_out 个
输出: (H' × W' × C_out)

参数量: k × k × C_in × C_out

例：3×3 卷积核，64 输入通道，128 输出通道
    → 3×3×64×128 = 73728 参数（比全连接少得多！）
```

### 2.2 池化层 (Pooling Layer)

```
Max Pooling: 取区域内最大值 → 提取最显著特征
Avg Pooling: 取区域内平均值 → 光滑

作用：下采样（降低分辨率）→ 减少计算量 + 增大感受野
```

### 2.3 特征图 (Feature Map)

```
低层特征图：边缘、角点（所有图像通用）
中层特征图：纹理、局部模式
高层特征图：物体部件、完整物体（任务相关）

这就是迁移学习的基础：底层特征可以迁移到不同任务
```

---

## 3. 经典 CNN 演进

| 模型 | 年份 | 关键创新 | 深度(层) |
|------|------|---------|---------|
| **LeNet** | 1998 | CNN 开山之作 | 5 |
| **AlexNet** | 2012 | ReLU + GPU + Dropout | 8 |
| **VGG** | 2014 | 统一 3x3 卷积核，加深 | 16/19 |
| **GoogLeNet/Inception** | 2014 | 多尺度卷积模块 | 22 |
| **ResNet** ⭐ | 2015 | **Residual Connection** | 50/101/152 |

### 关键趋势

```
越来越深：5层 → 19层 → 152层
但更深不一定更好（梯度消失/退化）
ResNet 解决了这个问题 → 允许训练极深的网络
```

---

## 4. ResNet 与 Residual Connection ⭐⭐⭐

### 4.1 退化问题 (Degradation)

```
理论上：更深的网络应该至少不会比浅网络差
         （最差情况，多出来的层学成恒等映射就行）
现实中：更深的网络训练误差反而更高！
         → 不是过拟合（训练集就差），是优化困难
```

### 4.2 Residual Connection 的设计

```
普通模块:   y = F(x)              (直接学目标映射)
残差模块:   y = F(x) + x          (学残差：F(x) = 目标 - 输入)
                   ↑
            shortcut / skip connection

如果最优解是恒等映射：
  普通模块需要学 F(x) = x → 困难
  残差模块只需学 F(x) = 0 → 容易（权重接近 0 就行）
```

### 4.3 为什么有效？

| 角度 | 解释 |
|------|------|
| **梯度流** | ∂y/∂x = ∂F/∂x + 1，梯度至少是 1，不消失 |
| **信息流** | 输入可以跳过层直通 → 底层能获得原始信息 |
| **集成** | 可以看作指数多条路径的集成 |
| **易学性** | 学残差（偏差）比学完整映射更容易 |

### 4.4 在 Transformer 中的应用

```
Transformer 的每个子层都有 Residual Connection：

  x → LayerNorm → Multi-Head Attention → Add(x) → ...
  x → LayerNorm → FFN → Add(x) → ...

没有 Residual Connection，几十层的 Transformer 根本无法训练！
```

> 🔑 **核心理解**：ResNet 的 Residual Connection 是深度学习最重要的设计之一，Transformer 直接继承了它。

---

## 5. CNN 与 Transformer 的关系

### 5.1 CNN 给 Transformer 的遗产

| CNN 的贡献 | 在 Transformer 中 |
|-----------|------------------|
| **Residual Connection** ⭐ | 每个子层都有 |
| 层次化特征学习 | 底层学语法 → 高层学语义 |
| 深度的价值 | 更深 = 更好（有了 Residual） |

### 5.2 CNN vs Transformer

| | CNN | Transformer |
|--|-----|-------------|
| 擅长 | 空间局部特征 | 全局关系（任意距离）|
| 感受野 | 局部（堆叠多层才能全局）| 全局（一层就能看到全部）|
| 并行性 | ✅ 高 | ✅ 高 |
| 应用 | 图像为主 | 文本为主（现在也做图像：ViT）|

### 5.3 Vision Transformer (ViT)

```
ViT 的思路：把图像切成 patches → 每个 patch 当作一个 "token" → 用 Transformer 处理

这说明：Transformer 足够通用，可以替代 CNN 处理图像
→ 多模态模型（GPT-4V、LLaVA）就是这个思路
```

---

## 6. 面试常问

### Q1: 卷积比全连接好在哪里？

**答**：
1. **参数少**：局部连接 + 权值共享 → 参数量大幅减少
2. **保留空间结构**：知道像素之间的位置关系
3. **平移不变性**：同一个物体在不同位置都能识别
4. **层次化特征**：底层→高层，简单→复杂

### Q2: 什么是 Residual Connection？为什么重要？

**答**：
- y = F(x) + x，输出 = 变换 + 原始输入
- 解决了深度网络的退化问题（更深但训练误差更高）
- 梯度可以通过 skip connection 直接传回底层 → 缓解梯度消失
- Transformer 的每个子层都使用 → 是训练深层网络的关键

### Q3: CNN 和 Transformer 的关系？

**答**：
- CNN 引入局部连接和权值共享，Transformer 用 Self-Attention 实现全局连接
- Transformer 继承了 CNN 的 Residual Connection
- ViT 证明 Transformer 可以替代 CNN 处理图像
- 现代多模态模型（GPT-4V）：Vision Encoder (CNN/ViT) + LLM (Transformer)

---

## 📖 推荐学习路径

1. 理解卷积的直觉（局部连接 + 权值共享）
2. **重点掌握 Residual Connection** → 这是对后续最重要的知识
3. CNN 的具体架构细节了解即可，面试不会深问

> ⬅️ [上一节：迁移学习](./03-transfer-learning.md) | [返回概览](./README.md) | ➡️ [下一节：RNN → LSTM → Attention](./05-rnn-lstm-attention.md)
