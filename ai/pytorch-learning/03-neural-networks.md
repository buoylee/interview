# 阶段 3：构建神经网络（nn.Module）

> **目标**：用 PyTorch 的积木式 API 构建、理解神经网络结构。
> **预计时间**：2-3 天
> **前置知识**：阶段 1-2（张量 + 自动求导）

---

## 1. 从手写到框架

```
阶段 2，你手写了 y = w*x + b 做线性回归
问题：如果网络有 100 层，每层 1000 个参数，手写就不现实了

nn.Module 解决了这个问题：
  - 每一层是一个"积木块"
  - 把积木块堆起来就是神经网络
  - PyTorch 自动管理所有参数
```

---

## 2. nn.Linear：最基本的积木块

```python
import torch
import torch.nn as nn

# 创建一个全连接层
layer = nn.Linear(in_features=3, out_features=5)
# in_features=3  → 输入维度（每条数据有 3 个特征）
# out_features=5 → 输出维度（输出 5 个值）

# 查看参数
print(layer.weight.shape)  # (5, 3) → 权重矩阵
print(layer.bias.shape)    # (5,) → 偏置向量

# 使用
x = torch.randn(4, 3)     # 4 条数据，每条 3 个特征
y = layer(x)               # 前向传播
print(y.shape)             # (4, 5) → 4 条数据，每条 5 个输出
```

### nn.Linear 做了什么？

```
y = x @ W^T + b

用你线性代数的知识：
  x:   (4, 3)   → 4 条数据
  W^T: (3, 5)   → 权重矩阵的转置
  b:   (5,)     → 偏置，广播到每一行
  y:   (4, 5)   → 结果

一个 nn.Linear 就是一次矩阵乘法 + 加偏置
```

---

## 3. 激活函数：让网络能学非线性

```python
# 问题：多个 Linear 堆起来还是线性的
# y = W2(W1 x + b1) + b2 = W2·W1·x + W2·b1 + b2 = W'x + b'
# 等效于一个 Linear！加深层数没用！

# 解决：在每层之间加激活函数（非线性变换）

# ReLU：最常用的激活函数
relu = nn.ReLU()
x = torch.tensor([-2.0, -1.0, 0.0, 1.0, 2.0])
print(relu(x))   # tensor([0., 0., 0., 1., 2.])
# 负数 → 0，正数 → 不变

# 其他常用激活函数
nn.Sigmoid()     # 输出 (0, 1)，用于二分类概率
nn.Tanh()        # 输出 (-1, 1)
nn.GELU()        # Transformer 常用（比 ReLU 更平滑）
nn.SiLU()        # 也叫 Swish，现代模型常用

# Softmax：把一组数变成概率分布
softmax = nn.Softmax(dim=-1)
logits = torch.tensor([2.0, 1.0, 0.1])
probs = softmax(logits)
print(probs)      # tensor([0.6590, 0.2424, 0.0986])  → 相加 = 1
# 分类任务最后一步：logits → Softmax → 概率
```

---

## 4. 两种搭建方式

### 方式 1：nn.Sequential（简单顺序堆叠）

```python
model = nn.Sequential(
    nn.Linear(784, 256),    # 第 1 层：784 → 256
    nn.ReLU(),              # 激活
    nn.Linear(256, 128),    # 第 2 层：256 → 128
    nn.ReLU(),              # 激活
    nn.Linear(128, 10),     # 输出层：128 → 10（10 个分类）
)

# 使用
x = torch.randn(32, 784)   # 32 张 28×28 的图片（展平成 784）
y = model(x)                # 前向传播
print(y.shape)              # (32, 10) → 32 张图片各自的 10 类得分
```

```
数据流：
  x(32,784) → Linear → (32,256) → ReLU → (32,256) → Linear → (32,128) → ReLU → (32,128) → Linear → (32,10)

什么时候用 Sequential？
  ✅ 网络是简单的线性堆叠（A→B→C→D）
  ❌ 网络有分支、跳跃连接等复杂结构
```

### 方式 2：自定义 nn.Module（灵活控制）

```python
class MyModel(nn.Module):        # 继承 nn.Module
    def __init__(self):
        super().__init__()       # ⭐ 必须调用父类初始化
        # 在这里定义所有的层
        self.fc1 = nn.Linear(784, 256)
        self.fc2 = nn.Linear(256, 128)
        self.fc3 = nn.Linear(128, 10)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.2)  # 20% 的概率随机丢弃

    def forward(self, x):
        # 在这里定义数据怎么流过这些层
        x = self.relu(self.fc1(x))      # 第 1 层 + 激活
        x = self.dropout(x)             # Dropout（只在训练时生效）
        x = self.relu(self.fc2(x))      # 第 2 层 + 激活
        x = self.dropout(x)
        x = self.fc3(x)                 # 输出层（不加激活）
        return x                        # ⭐ 最后一层不加 ReLU/Sigmoid！
        # CrossEntropyLoss 内部自带 Softmax
```

```
为什么输出层不加激活函数？
  因为 CrossEntropyLoss 自带 Softmax
  如果你加了，等于做了两次 Softmax，结果会错

  输出 → Softmax → CrossEntropy  ← 分开做
  输出 → CrossEntropyLoss        ← PyTorch 合在一起做（更快更稳定）
```

### 使用自定义模型

```python
model = MyModel()

# 前向传播
x = torch.randn(32, 784)
y = model(x)          # 等同于 model.forward(x)，但不要直接调用 forward
print(y.shape)        # (32, 10)
```

---

## 5. 查看和管理模型参数

```python
model = MyModel()

# 查看所有参数
for name, param in model.named_parameters():
    print(f"{name:15} shape={param.shape}  trainable={param.requires_grad}")

# 输出：
# fc1.weight      shape=torch.Size([256, 784])  trainable=True
# fc1.bias        shape=torch.Size([256])        trainable=True
# fc2.weight      shape=torch.Size([128, 256])  trainable=True
# fc2.bias        shape=torch.Size([128])        trainable=True
# fc3.weight      shape=torch.Size([10, 128])   trainable=True
# fc3.bias        shape=torch.Size([10])         trainable=True

# 总参数量
total = sum(p.numel() for p in model.parameters())
print(f"总参数量: {total:,}")  # 235,146

# 可训练参数量
trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f"可训练参数量: {trainable:,}")  # 235,146

# ⭐ 和 notebook 的关系：
# Trainable parameters = 128,450,560 of 14,896,757,760 (0.86%)
# 就是用上面的方法算出来的
```

### 冻结参数

```python
# 冻结某些层的参数（不参与训练）
for param in model.fc1.parameters():
    param.requires_grad = False

# 冻结所有参数
for param in model.parameters():
    param.requires_grad = False

# 只解冻最后一层
for param in model.fc3.parameters():
    param.requires_grad = True

# ⭐ 这就是迁移学习/微调的核心思路：
# 冻结预训练好的大部分参数，只训练最后几层
```

---

## 6. 常用层速查

| 层 | 用途 | 典型场景 |
|---|---|---|
| `nn.Linear(in, out)` | 全连接 | 几乎所有网络 |
| `nn.Conv2d(in_ch, out_ch, kernel)` | 2D 卷积 | 图像处理 |
| `nn.Embedding(vocab_size, dim)` | 词嵌入 | NLP，把 token ID 变成向量 |
| `nn.LSTM(input, hidden)` | 长短期记忆 | 序列建模（已被 Transformer 取代） |
| `nn.LayerNorm(dim)` | 层归一化 | Transformer 每层后面都有 |
| `nn.Dropout(p)` | 随机丢弃 | 防过拟合 |
| `nn.BatchNorm1d(dim)` | 批归一化 | 加速训练收敛 |

### nn.Embedding 详解（NLP 关键）

```python
# 假设词表有 1000 个词，每个词用 64 维向量表示
embed = nn.Embedding(num_embeddings=1000, embedding_dim=64)

# 输入是 token ID
token_ids = torch.tensor([42, 7, 256, 0])   # 4 个词的 ID
vectors = embed(token_ids)                    # (4, 64) → 每个 ID 变成 64 维向量

# Embedding 本质：一个查找表
# ID=42 → 查找表第 42 行 → 返回一个 64 维向量
# 这些向量是可训练的参数！
```

### nn.LayerNorm 详解（Transformer 关键）

```python
# 对每条数据的特征做归一化（均值=0，方差=1）
norm = nn.LayerNorm(64)

x = torch.randn(32, 10, 64)   # batch=32, seq_len=10, dim=64
y = norm(x)                    # 对最后一维做归一化
# 每个位置的 64 维向量被归一化

# 为什么需要？
# 防止数值越来越大或越来越小（稳定训练）
```

---

## 7. 模型的嵌套组合

```python
# 复杂模型可以嵌套 nn.Module

class ResidualBlock(nn.Module):
    """残差块：输出 = 输入 + 变换(输入)"""
    def __init__(self, dim):
        super().__init__()
        self.fc = nn.Linear(dim, dim)
        self.relu = nn.ReLU()
        self.norm = nn.LayerNorm(dim)

    def forward(self, x):
        residual = x                    # 保存原始输入
        x = self.relu(self.fc(x))       # 做一次变换
        x = self.norm(x + residual)     # 加回原始输入（残差连接）
        return x


class DeepModel(nn.Module):
    def __init__(self, input_dim, hidden_dim, num_blocks, output_dim):
        super().__init__()
        self.input_layer = nn.Linear(input_dim, hidden_dim)
        # 用 nn.ModuleList 管理多个子模块
        self.blocks = nn.ModuleList([
            ResidualBlock(hidden_dim) for _ in range(num_blocks)
        ])
        self.output_layer = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        x = self.input_layer(x)
        for block in self.blocks:
            x = block(x)               # 逐层通过残差块
        return self.output_layer(x)


model = DeepModel(input_dim=784, hidden_dim=128, num_blocks=3, output_dim=10)
print(model)
# 会打印出完整的模型结构，包括 3 个 ResidualBlock
```

```
⚠️ 注意：用 nn.ModuleList 而不是 Python list
  nn.ModuleList → PyTorch 能追踪里面的参数（可训练）
  Python list   → PyTorch 看不到里面的参数（不可训练，bug！）

残差连接（Residual Connection）：
  Transformer 每一层都有残差连接
  核心思想：让梯度能直接"穿过"这一层 → 深层网络也能训练
  你在后续学 Transformer 架构时会深入理解
```

---

## 练习

```
1. 用 nn.Sequential 搭一个 3 层网络（784→256→128→10），跑通前向传播
2. 把同样的网络用自定义 nn.Module 重写，加上 Dropout
3. 打印所有参数的名字和形状，计算总参数量
4. 冻结前两层参数，确认只有最后一层 requires_grad=True
5. 创建一个 Embedding 层（vocab=100, dim=32），输入 token ID 得到向量
```

---

## 本阶段小结

```
学到了什么：
  ✅ nn.Linear 就是矩阵乘法 + bias
  ✅ 激活函数让网络能学非线性
  ✅ Sequential（简单堆叠）vs Module（灵活控制）
  ✅ 查看和冻结参数
  ✅ Embedding、LayerNorm 等常用层

和 notebook 的关系：
  model = FastLanguageModel.from_pretrained(...)
  → 加载了一个巨大的 nn.Module（Qwen3-14B）

  model = FastLanguageModel.get_peft_model(model, r=32, ...)
  → 冻结原始参数 + 添加 LoRA adapter（新的小型 nn.Linear）

  target_modules = ["q_proj", "k_proj", ...]
  → 指定在哪些 nn.Linear 上添加 LoRA

下一阶段预告：
  模型有了，但还需要数据。下一阶段学 Dataset 和 DataLoader，
  学会怎么高效地把数据喂给模型。
```
