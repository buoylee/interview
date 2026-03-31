# 阶段 1：张量（Tensor）操作

> **目标**：掌握 PyTorch 的核心数据结构，能熟练创建、操作、变换张量。
> **预计时间**：2-3 天
> **前置知识**：线性代数基础（向量、矩阵、矩阵乘法）

---

## 1. 什么是张量？

```
张量 = 多维数组 = NumPy 数组的 GPU 加速版

维度     名称       例子
0D      标量       一个数字：3.14
1D      向量       一行数字：[1, 2, 3]
2D      矩阵       表格：[[1,2], [3,4]]
3D      3阶张量    一批表格（如一批图片）
4D+     高阶张量    更复杂的数据结构
```

为什么不直接用 NumPy？

```
NumPy：  只能在 CPU 上计算
PyTorch：可以在 GPU/MPS 上计算 → 速度快几十倍
         而且支持自动求导（下一阶段学）
```

---

## 2. 创建张量

```python
import torch

# ===== 从数据创建 =====
x = torch.tensor([1, 2, 3])              # 从 Python 列表创建
x = torch.tensor([[1, 2], [3, 4]])        # 2D 矩阵

# ===== 用函数创建 =====
x = torch.zeros(3, 4)        # 3×4 全零矩阵
x = torch.ones(3, 4)         # 3×4 全一矩阵
x = torch.randn(3, 4)        # 3×4 随机矩阵（标准正态分布 N(0,1)）
x = torch.rand(3, 4)         # 3×4 随机矩阵（均匀分布 [0,1)）
x = torch.arange(0, 10, 2)   # [0, 2, 4, 6, 8]
x = torch.linspace(0, 1, 5)  # [0, 0.25, 0.5, 0.75, 1.0]
x = torch.eye(3)             # 3×3 单位矩阵

# ===== 创建和已有张量形状一样的张量 =====
y = torch.zeros_like(x)      # 和 x 同形状的全零张量
y = torch.randn_like(x)      # 和 x 同形状的随机张量

# ===== 指定数据类型 =====
x = torch.tensor([1, 2, 3], dtype=torch.float32)   # 浮点数
x = torch.tensor([1, 2, 3], dtype=torch.int64)      # 整数
x = torch.tensor([1, 2, 3], dtype=torch.bool)       # 布尔值
```

### 为什么 randn 用正态分布？

```
因为神经网络的权重初始化通常用正态分布（均值 0，方差较小）
  → 太大的初始权重会导致梯度爆炸
  → 太小的初始权重会导致梯度消失
  → 正态分布在 0 附近集中，是个好的起点
```

---

## 3. 张量的属性

```python
x = torch.randn(3, 4)

x.shape         # torch.Size([3, 4]) → 3 行 4 列
x.size()        # 同上，另一种写法
x.dtype         # torch.float32 → 数据类型
x.device        # cpu → 在哪个设备上
x.ndim          # 2 → 几维张量
x.numel()       # 12 → 总共有多少个元素（3×4=12）
x.requires_grad # False → 是否需要计算梯度（阶段 2 详解）
```

### 数据类型转换（训练时常用）

```python
x = torch.tensor([1, 2, 3])       # 默认 int64
x = x.float()                     # → float32（模型输入通常要求 float）
x = x.long()                      # → int64（标签通常是 long）
x = x.half()                      # → float16（省显存）
x = x.bool()                      # → bool
x = x.to(torch.bfloat16)          # → bfloat16（训练常用）

# 常见场景：
# 图片读进来是 uint8 (0-255)，模型需要 float32 (0-1)
# labels 是 float，但 CrossEntropyLoss 要求 long
```

---

## 4. 基本运算

### 4.1 逐元素运算

```python
a = torch.tensor([1.0, 2.0, 3.0])
b = torch.tensor([4.0, 5.0, 6.0])

a + b    # tensor([5., 7., 9.])   每个位置分别相加
a - b    # tensor([-3., -3., -3.])
a * b    # tensor([4., 10., 18.]) 每个位置分别相乘（不是矩阵乘法！）
a / b    # tensor([0.25, 0.4, 0.5])
a ** 2   # tensor([1., 4., 9.])   每个元素平方
```

> ⚠️ `a * b` 是**逐元素乘**，不是矩阵乘法！矩阵乘法用 `@` 或 `torch.matmul`

### 4.2 矩阵乘法

```python
A = torch.randn(3, 4)   # 3×4 矩阵
B = torch.randn(4, 5)   # 4×5 矩阵

C = A @ B                # 3×5 矩阵 ← 推荐写法
C = torch.matmul(A, B)   # 同上
C = A.mm(B)              # 同上（只能用于 2D）

# 记住维度规则（你在线性代数里学过的）：
# (m × n) @ (n × p) = (m × p)
# 内层维度 n 必须相同！
```

### 4.3 常用数学函数

```python
x = torch.tensor([-2.0, -1.0, 0.0, 1.0, 2.0])

torch.abs(x)    # [2, 1, 0, 1, 2]    绝对值
torch.exp(x)    # e 的 x 次方
torch.log(x)    # 自然对数（x 必须 > 0）
torch.sqrt(x)   # 平方根（x 必须 >= 0）
torch.clamp(x, min=0)  # 小于 0 的变成 0 → 这就是 ReLU！

torch.sum(x)    # 求和
torch.mean(x)   # 平均值
torch.max(x)    # 最大值
torch.min(x)    # 最小值
torch.argmax(x) # 最大值的索引 → 分类任务用这个找预测类别
```

### 4.4 广播机制（Broadcasting）

```python
# 当两个张量形状不同但兼容时，PyTorch 自动扩展
a = torch.randn(3, 4)     # 3×4
b = torch.tensor([1.0])   # 标量

c = a + b    # b 自动扩展成 3×4，每个元素都加 1

# 常见的广播场景
a = torch.randn(3, 4)     # 3×4
b = torch.randn(1, 4)     # 1×4 → 自动扩展成 3×4（每行加同一个向量）
c = a + b                 # 结果是 3×4

# 广播规则：从最后一个维度开始对齐
# 每个维度要么相同，要么其中一个是 1
```

---

## 5. 形状操作（⭐ 非常重要）

在深度学习中经常需要调整张量形状，这是最常用也最容易出错的操作。

### 5.1 reshape / view

```python
x = torch.arange(12)       # tensor([0, 1, 2, ..., 11])，形状 (12,)

x.reshape(3, 4)             # 变成 3×4 矩阵
x.reshape(4, 3)             # 变成 4×3 矩阵
x.reshape(2, 2, 3)          # 变成 2×2×3 的 3D 张量
x.reshape(-1, 4)            # -1 表示自动计算：12/4=3，变成 3×4

# view 和 reshape 类似，但要求内存连续
x.view(3, 4)                # 和 reshape 结果一样
# 建议：不确定就用 reshape，更安全
```

### 5.2 squeeze / unsqueeze

```python
x = torch.randn(1, 3, 1, 4)

x.squeeze()        # 去掉所有大小为 1 的维度 → (3, 4)
x.squeeze(0)       # 只去掉第 0 维 → (3, 1, 4)
x.squeeze(2)       # 只去掉第 2 维 → (1, 3, 4)

y = torch.randn(3, 4)
y.unsqueeze(0)     # 在第 0 维加一个 → (1, 3, 4)  常用于加 batch 维度
y.unsqueeze(-1)    # 在最后加一个 → (3, 4, 1)
```

```
为什么需要 squeeze/unsqueeze？

模型输入通常需要 batch 维度：
  模型期望 (batch_size, features) = (32, 784)
  但你只有一条数据 (784,)
  所以需要 unsqueeze(0) 变成 (1, 784) → 假装是 batch_size=1
```

### 5.3 转置和维度交换

```python
x = torch.randn(3, 4)

x.T             # 转置 → (4, 3)，只能用于 2D
x.t()           # 同上

# 多维张量用 permute
x = torch.randn(2, 3, 4)
x.permute(0, 2, 1)   # 交换第 1 和第 2 维 → (2, 4, 3)
# 在 Transformer 中经常用到（调整 batch/seq/feature 的顺序）
```

### 5.4 拼接

```python
a = torch.randn(2, 3)
b = torch.randn(2, 3)

torch.cat([a, b], dim=0)    # 沿第 0 维拼接 → (4, 3)
torch.cat([a, b], dim=1)    # 沿第 1 维拼接 → (2, 6)

torch.stack([a, b], dim=0)  # 新增一个维度来堆叠 → (2, 2, 3)
# cat = 续接（不加维度），stack = 堆叠（加一个新维度）
```

---

## 6. 索引和切片

```python
x = torch.tensor([[1, 2, 3], [4, 5, 6], [7, 8, 9]])

# 基本索引（和 Python 列表一样）
x[0]          # tensor([1, 2, 3]) → 第 0 行
x[0, 1]       # tensor(2) → 第 0 行第 1 列
x[:, 1]       # tensor([2, 5, 8]) → 所有行的第 1 列
x[0:2, :]     # 前 2 行

# 布尔索引
mask = x > 5
x[mask]       # tensor([6, 7, 8, 9]) → 所有大于 5 的元素

# fancy indexing
indices = torch.tensor([0, 2])
x[indices]    # 取第 0 行和第 2 行
```

---

## 7. 设备管理（CPU / GPU / MPS）

```python
# 检测可用设备
device = (
    "cuda" if torch.cuda.is_available()       # NVIDIA GPU
    else "mps" if torch.backends.mps.is_available()  # Mac M 系列
    else "cpu"
)
print(f"Using device: {device}")

# 创建时指定设备
x = torch.randn(3, 4, device=device)

# 或者创建后移动
x = torch.randn(3, 4)
x = x.to(device)          # 移到加速设备
x = x.to("cpu")           # 移回 CPU

# ⚠️ 重要：两个张量运算时必须在同一个设备上！
a = torch.randn(3, device="cpu")
b = torch.randn(3, device=device)
# a + b  → 如果 device 不是 cpu，会报错！
# 解决：a.to(device) + b
```

### Mac M4 注意事项

```
- 你的 M4 用 "mps" 设备，不是 "cuda"
- MPS 不支持所有 PyTorch 操作，极少数操作会报错
  报错时加 .to("cpu") 在 CPU 上算即可
- 从阶段 1 就养成用 device 变量的习惯
```

---

## 8. 张量和 NumPy 的互转

```python
import numpy as np

# Tensor → NumPy
x = torch.tensor([1.0, 2.0, 3.0])
n = x.numpy()            # 共享内存！修改一个另一个也会变
n = x.detach().numpy()   # 安全版本（断开梯度追踪）

# NumPy → Tensor
n = np.array([1.0, 2.0, 3.0])
x = torch.from_numpy(n)  # 共享内存
x = torch.tensor(n)      # 不共享，创建副本（更安全）
```

---

## 练习

```
1. 创建两个 3×3 矩阵，分别做逐元素乘法和矩阵乘法，对比结果
2. 创建一个 (batch_size=4, input_dim=3) 的输入张量
   和一个 (3, 5) 的权重矩阵，相乘得到 (4, 5) 的输出
   → 理解"批量处理"的含义
3. 创建一个 (12,) 的向量，reshape 成 (2, 2, 3)，再用 permute 交换后两个维度
4. 把以上操作都放到 MPS/GPU 上执行，确认 device 切换正常
5. 尝试在不同 device 的张量之间做运算，观察报错信息
```

---

## 本阶段小结

```
学到了什么：
  ✅ 创建各种张量（zeros, randn, eye...）
  ✅ 基本运算（逐元素 vs 矩阵乘法）
  ✅ 形状操作（reshape, squeeze, permute, cat）
  ✅ 设备管理（CPU/GPU/MPS）

和 notebook 的关系：
  tokenizer(text, return_tensors="pt")
  → "pt" 就是 PyTorch tensor
  → Hugging Face 把文字转成了张量，然后喂给模型

下一阶段预告：
  张量只是数据容器。下一阶段学习 Autograd（自动求导），
  让 PyTorch 能自动帮你算梯度，不用手写链式法则。
```
