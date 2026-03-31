# PyTorch 系统学习路线

> **前提**：你已经理解了 ML 基础概念（梯度下降、损失函数、反向传播），现在需要学会用 PyTorch 把这些概念写成代码。

---

## 学习路线概览

```
阶段 1：基础操作（2-3 天）
  → 张量（Tensor）操作 = PyTorch 的核心数据结构

阶段 2：自动求导（1-2 天）
  → Autograd = 自动反向传播，不用手算梯度

阶段 3：构建神经网络（2-3 天）
  → nn.Module = 搭积木式构建模型

阶段 4：数据处理（1-2 天）
  → Dataset + DataLoader = 高效喂数据

阶段 5：训练循环（3-4 天）
  → 完整的 前向传播 → 算损失 → 反向传播 → 更新权重 → 验证评估

阶段 6：预训练模型与迁移学习（2-3 天）
  → 加载别人训练好的模型，冻结 + 微调

阶段 7：实战项目（3-5 天）
  → 用以上知识完成递进式项目，衔接 fine-tuning
```

---

## 阶段 1：张量（Tensor）操作

### 你需要掌握的

张量就是 NumPy 数组的 GPU 版本。所有数据在 PyTorch 里都是张量。

```python
import torch

# 1.1 创建张量
x = torch.tensor([1, 2, 3])              # 从列表创建
x = torch.zeros(3, 4)                     # 3×4 的全零矩阵
x = torch.randn(3, 4)                     # 3×4 的随机矩阵（正态分布）
x = torch.ones(3, 4)                      # 3×4 的全一矩阵

# 1.2 张量属性
x.shape      # 形状，比如 torch.Size([3, 4])
x.dtype      # 数据类型，比如 torch.float32
x.device     # 在哪个设备，'cpu' 或 'cuda:0'

# 1.3 基本运算（和你学过的矩阵运算对应）
a + b        # 逐元素加
a * b        # 逐元素乘
a @ b        # 矩阵乘法 ← 你在线性代数里学过的
a.T          # 转置

# 1.4 形状操作
x.reshape(2, 6)   # 改变形状
x.squeeze()       # 去掉大小为 1 的维度
x.unsqueeze(0)    # 增加一个维度

# 1.5 设备管理
# 通用写法（在任何设备上都能跑）：
device = (
    "cuda" if torch.cuda.is_available()
    else "mps" if torch.backends.mps.is_available()
    else "cpu"
)
x = x.to(device)      # 把张量放到可用的加速设备
x = x.to("cpu")       # 放回 CPU
```

### 和你学过的知识的关系

```
线性代数里学的矩阵 → PyTorch 里就是 2D 的 Tensor
向量              → 1D 的 Tensor
标量              → 0D 的 Tensor
```

### Mac M4 适配

```python
# 你的 MacBook M4 不是 NVIDIA GPU，不能用 "cuda"
# 要用 Apple 的 MPS（Metal Performance Shaders）

# 错误写法（会报错）：
x = x.to("cuda")

# 正确写法（Mac M4）：
device = "mps" if torch.backends.mps.is_available() else "cpu"
x = x.to(device)
model = model.to(device)
```

> 从第一天起就养成用 `device` 变量的习惯，后面所有阶段都会用到。

### 练习

```
1. 创建两个 3×3 矩阵，做矩阵乘法
2. 创建一个 (batch_size=4, input_dim=3) 的张量
   和一个 (3, 5) 的权重矩阵，相乘得到 (4, 5) 的输出
   ← 这就是你学过的"批量加权求和"
3. 把上面的操作放到 MPS/GPU 上执行，确认 device 切换正常
```

---

## 阶段 2：自动求导（Autograd）

### 你需要掌握的

PyTorch 最强大的功能：自动帮你算梯度，不用手写链式法则。

```python
# 2.1 基本自动求导
x = torch.tensor(3.0, requires_grad=True)
# requires_grad=True → 告诉 PyTorch "我需要对这个变量求导"

y = x ** 2 + 2 * x + 1
# y = x² + 2x + 1

y.backward()
# ⭐ 自动反向传播！
# PyTorch 自动用链式法则算出 dy/dx

print(x.grad)
# 输出: tensor(8.0)
# 因为 dy/dx = 2x + 2 = 2(3) + 2 = 8 ✓

# 2.2 多变量求导
w = torch.tensor(2.0, requires_grad=True)
b = torch.tensor(1.0, requires_grad=True)
x = torch.tensor(3.0)

y = w * x + b      # y = 2*3 + 1 = 7
loss = (y - 5) ** 2 # loss = (7-5)² = 4

loss.backward()     # 自动算所有梯度

print(w.grad)       # dloss/dw
print(b.grad)       # dloss/db
# PyTorch 自动追踪所有计算过程，反向传播一键完成
```

### 和你学过的知识的关系

```
微积分里的链式法则 → PyTorch 用 .backward() 自动完成
反向传播          → 就是 .backward() 做的事
梯度下降          → 拿到 .grad 后手动更新权重（或用优化器）
```

### 练习

```
1. 定义 y = 3x³ + 2x² + x，在 x=2 处求导
   （手算答案：dy/dx = 9x² + 4x + 1 = 9(4) + 4(2) + 1 = 45）
2. 实现一个简单的线性回归的梯度计算
```

---

## 阶段 3：构建神经网络（nn.Module）

### 你需要掌握的

用 PyTorch 搭建模型就像搭积木：

```python
import torch.nn as nn

# 3.1 最简单的方式：Sequential（顺序堆叠）
model = nn.Sequential(
    nn.Linear(784, 256),    # 全连接层：784 → 256
    nn.ReLU(),              # 激活函数
    nn.Linear(256, 128),    # 全连接层：256 → 128
    nn.ReLU(),
    nn.Linear(128, 10),     # 输出层：128 → 10（10 个分类）
)

# 3.2 自定义模型（更灵活）
class MyModel(nn.Module):
    def __init__(self):
        super().__init__()
        # 定义层
        self.fc1 = nn.Linear(784, 256)
        self.fc2 = nn.Linear(256, 128)
        self.fc3 = nn.Linear(128, 10)
        self.relu = nn.ReLU()

    def forward(self, x):
        # 定义数据怎么流过这些层
        x = self.relu(self.fc1(x))   # 输入 → 第1层 → ReLU
        x = self.relu(self.fc2(x))   # → 第2层 → ReLU
        x = self.fc3(x)             # → 第3层（输出）
        return x

model = MyModel()

# 3.3 查看模型参数
for name, param in model.named_parameters():
    print(name, param.shape)
# fc1.weight torch.Size([256, 784])
# fc1.bias   torch.Size([256])
# ...

# 3.4 常用层
nn.Linear(in, out)       # 全连接层（矩阵乘法 + bias）
nn.Conv2d(in_ch, out_ch) # 卷积层（图像用）
nn.Embedding(vocab, dim) # 嵌入层（NLP 用）
nn.LayerNorm(dim)        # 层归一化（Transformer 用）
nn.Dropout(p)            # 随机丢弃（防过拟合）
```

### 和你学过的知识的关系

```
nn.Linear(in, out) = 就是 y = Wx + b
  - W 就是你学过的权重矩阵
  - b 就是偏置
  - 每个 Linear 层就是一次矩阵乘法

nn.ReLU() = 激活函数
  - 让网络能学非线性关系
  - ReLU(x) = max(0, x)（负数变0，正数不变）
```

### 练习

```
1. 用 nn.Sequential 搭一个 3 层网络
2. 用 nn.Module 搭同样的网络
3. 打印所有参数的名字和形状
```

---

## 阶段 4：数据处理（Dataset + DataLoader）

### 你需要掌握的

训练循环需要数据，所以先学会怎么喂数据：

```python
from torch.utils.data import Dataset, DataLoader

# 4.1 自定义数据集
class MyDataset(Dataset):
    def __init__(self, texts, labels):
        self.texts = texts
        self.labels = labels

    def __len__(self):
        return len(self.texts)     # 数据集大小

    def __getitem__(self, idx):
        return self.texts[idx], self.labels[idx]  # 取一条数据

# 4.2 DataLoader（自动分 batch + 打乱）
dataset = MyDataset(texts, labels)
dataloader = DataLoader(
    dataset,
    batch_size = 32,       # 每次取 32 条
    shuffle = True,        # 每个 epoch 打乱顺序
    num_workers = 2,       # 用 2 个子进程加载数据
)

# 4.3 使用
for batch_x, batch_y in dataloader:
    # batch_x.shape = (32, ...)
    # 自动帮你切好了 batch，直接喂给模型
    pass
```

### 数据划分：train / val / test

```python
from torch.utils.data import random_split

# 假设你有 10000 条数据
dataset = MyDataset(all_texts, all_labels)

# 按 8:1:1 划分
train_size = int(0.8 * len(dataset))
val_size = int(0.1 * len(dataset))
test_size = len(dataset) - train_size - val_size

train_dataset, val_dataset, test_dataset = random_split(
    dataset, [train_size, val_size, test_size]
)

# 分别创建 DataLoader
train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
val_loader   = DataLoader(val_dataset,   batch_size=32, shuffle=False)  # 验证不需要打乱
test_loader  = DataLoader(test_dataset,  batch_size=32, shuffle=False)
```

### 和微调 notebook 的关系

```
你在 notebook 里看到的：
  from datasets import load_dataset  ← 这是 Hugging Face 的 Dataset
  SFTTrainer(train_dataset=...)     ← Trainer 内部就是用 DataLoader 分 batch 的

Hugging Face 的 Dataset 是 PyTorch Dataset 的封装，底层逻辑一样
```

### 练习

```
1. 写一个自定义 Dataset，加载任意数据
2. 用 random_split 划分 train/val/test
3. 用 DataLoader 遍历，打印每个 batch 的形状
```

---

## 阶段 5：训练循环（最核心）⭐

### 你需要掌握的

这是 PyTorch 的核心流程，对应你之前学的完整训练过程。

### 5.1 选择损失函数

不同任务用不同的损失函数：

| 任务类型 | 损失函数 | 例子 |
|---------|---------|------|
| 多分类（N 选 1） | `nn.CrossEntropyLoss()` | 手写数字识别（0-9） |
| 二分类（是/否） | `nn.BCEWithLogitsLoss()` | 垃圾邮件检测 |
| 回归（预测数值） | `nn.MSELoss()` | 预测房价 |

> 不确定用哪个？看你的 label：是类别就用 CrossEntropy，是数值就用 MSE。

### 5.2 完整训练 + 验证循环

```python
import torch
import torch.nn as nn
import torch.optim as optim

# 准备模型、损失函数、优化器
model = MyModel().to(device)
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=0.001)

# ========== 训练循环 ==========
for epoch in range(10):

    # --- 训练阶段 ---
    model.train()    # ⭐ 开启训练模式（启用 Dropout 等）
    train_loss = 0

    for batch_x, batch_y in train_loader:
        batch_x, batch_y = batch_x.to(device), batch_y.to(device)

        # 前向传播
        predictions = model(batch_x)
        loss = criterion(predictions, batch_y)

        # 反向传播
        optimizer.zero_grad()   # ⭐ 清零上一步的梯度（必须！）
        loss.backward()         # ⭐ 自动计算所有参数的梯度
        optimizer.step()        # ⭐ 根据梯度更新权重

        train_loss += loss.item()

    train_loss /= len(train_loader)

    # --- 验证阶段 ---
    model.eval()     # ⭐ 切到评估模式（关闭 Dropout 等）
    val_loss = 0
    correct = 0
    total = 0

    with torch.no_grad():   # ⭐ 不算梯度，省显存
        for batch_x, batch_y in val_loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)

            predictions = model(batch_x)
            loss = criterion(predictions, batch_y)
            val_loss += loss.item()

            # 算准确率
            _, predicted = predictions.max(1)
            total += batch_y.size(0)
            correct += predicted.eq(batch_y).sum().item()

    val_loss /= len(val_loader)
    val_acc = correct / total

    print(f"Epoch {epoch}: train_loss={train_loss:.4f}, val_loss={val_loss:.4f}, val_acc={val_acc:.4f}")
```

### 5.3 如何判断训练状态

```
train_loss ↓  val_loss ↓  → 正常，继续训练
train_loss ↓  val_loss ↑  → ⚠️ 过拟合！模型在背答案，而不是学规律
train_loss →  val_loss →  → 学不动了，可能需要调参数或换模型
train_loss ↑              → 出问题了，检查学习率或数据
```

### 每一步对应的数学

```
predictions = model(batch_x)
  → 前向传播：输入 × 权重矩阵 → 激活函数 → 下一层 × ...

loss = criterion(predictions, batch_y)
  → 交叉熵 = -log(模型给正确类的概率)

optimizer.zero_grad()
  → 清零梯度。为什么？因为 PyTorch 默认梯度是累加的
    不清零的话这次的梯度会加到上次的上面

loss.backward()
  → 反向传播 = 链式法则
    从 loss 出发，一层层往回算每个参数的梯度

optimizer.step()
  → 梯度下降：参数 = 参数 - 学习率 × 梯度
    Adam 比基础梯度下降更智能（会自适应调整步长）
```

### 练习

```
1. 手写一个包含训练 + 验证的完整循环（不用 Hugging Face Trainer）
2. 观察 train_loss 和 val_loss 随 epoch 变化的趋势
3. 修改学习率（0.1 vs 0.001 vs 0.00001），观察 loss 变化
4. 故意让模型过拟合（用很小的数据集 + 很大的模型），观察 train/val loss 的分离
```

---

## 阶段 6：预训练模型与迁移学习

### 为什么需要这个阶段

现实中很少从零训练模型。主流做法是：

```
别人用海量数据训练好的大模型
  → 你加载它
  → 冻结大部分参数
  → 只训练最后几层（或用 LoRA 训练少量参数）
  → 用你自己的数据微调
```

这就是 fine-tuning 的核心思路。前面 5 个阶段学的是底层原理，这个阶段开始衔接实际工作流。

### 6.1 加载预训练模型（torchvision 示例）

```python
import torchvision.models as models

# 加载一个在 ImageNet 上训练好的 ResNet
model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)

# 查看最后一层
print(model.fc)  # Linear(in_features=512, out_features=1000)
# 原模型分 1000 类（ImageNet），你需要改成你的类别数
```

### 6.2 冻结参数 + 替换输出层

```python
# 冻结所有参数（不参与训练）
for param in model.parameters():
    param.requires_grad = False

# 只替换最后一层（这一层会被训练）
model.fc = nn.Linear(512, 2)  # 比如你只需要分 2 类

# 只有 model.fc 的参数会被更新
optimizer = optim.Adam(model.fc.parameters(), lr=0.001)
```

### 6.3 加载 Hugging Face 预训练模型（NLP）

```python
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# 加载预训练模型和分词器
model_name = "bert-base-uncased"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(
    model_name, num_labels=2
)

# 使用
inputs = tokenizer("Hello world", return_tensors="pt")
outputs = model(**inputs)
```

### 6.4 和 fine-tuning notebook 的关系

```
你在 notebook 里看到的：

  model = AutoModelForCausalLM.from_pretrained(...)
    → 就是 6.3 的加载预训练模型

  peft_config = LoraConfig(...)
    → 和 6.2 类似，只训练少量参数，但用了更高效的 LoRA 方法

  trainer = SFTTrainer(...)
    → 就是 5.2 的训练循环，但 Hugging Face 帮你封装好了
```

### 练习

```
1. 用 torchvision 加载一个预训练 ResNet，替换最后一层，跑通前向传播
2. 冻结所有层只训练最后一层，在小数据集上 fine-tune
3. 用 Hugging Face 加载一个 BERT，做文本分类的推理
```

---

## 阶段 7：实战项目

### 3 个递进项目

```
项目 1：手写数字识别（MNIST）← 巩固 Stage 1-5，1-2 小时完成
  - 用 nn.Linear 搭一个 3 层网络
  - 用 CrossEntropyLoss + Adam
  - 包含完整的 train/val 循环
  - 画出 train_loss 和 val_loss 曲线
  - 目标：准确率 > 95%
  - 数据集 PyTorch 自带：torchvision.datasets.MNIST

项目 2：文本情感分类 ← 衔接 NLP，用迁移学习
  - 用 Hugging Face 加载预训练 BERT
  - 冻结 BERT 参数，只训练分类头
  - 数据集：Hugging Face 上的 imdb
  - 目标：理解 tokenizer → model → loss 的完整链路

项目 3：手写一个简单的 fine-tune 流程 ← 衔接你的 fine-tuning 学习
  - 加载一个小型预训练语言模型（如 GPT-2 small）
  - 不用 SFTTrainer，自己写训练循环
  - 用 LoRA（peft 库）只训练少量参数
  - 在一个小数据集上微调
  - 目标：完全理解 fine-tuning notebook 里每一步在做什么
```

---

## 推荐学习资源

```
官方教程（最权威）：
  https://pytorch.org/tutorials/

视频教程（最直观）：
  Andrej Karpathy - "Neural Networks: Zero to Hero"（YouTube 免费）
  ← 前 Tesla AI 总监，从零手写神经网络，极其清晰

速查手册（写代码时查）：
  https://pytorch.org/docs/stable/

练习平台（动手写）：
  Google Colab（免费 GPU）
```

---

## 和你现有知识的对应关系

| 你学过的概念 | PyTorch 代码 |
|---|---|
| 矩阵乘法 | `torch.matmul(a, b)` 或 `a @ b` |
| 梯度下降 | `optimizer.step()` |
| 反向传播 / 链式法则 | `loss.backward()` |
| 交叉熵损失 | `nn.CrossEntropyLoss()` |
| 均方误差损失 | `nn.MSELoss()` |
| 学习率 | `optim.Adam(params, lr=0.001)` |
| 批量处理 (batch) | `DataLoader(batch_size=32)` |
| 过拟合判断 | 比较 train_loss vs val_loss |
| 迁移学习 | `model = models.resnet18(weights=...)` |
| LoRA 低秩矩阵 | `peft` 库自动处理 |
| 4-bit 量化 | `bitsandbytes` 库自动处理 |

---

## 学习建议

```
1. 阶段 1-5 是核心，必须亲手写代码跑通
2. 阶段 6 是衔接 fine-tuning 的桥梁，理解思路并跑通示例
3. 阶段 7 至少做项目 1（MNIST），然后尽快做项目 3 衔接你的学习目标
4. 不用背 API，写代码时查文档就行
5. 推荐 Karpathy 的视频，看完直接开悟
```

---

## 附录：常见报错和解决

```
报错 1：RuntimeError: Expected all tensors on the same device
原因：一部分数据在 CPU，一部分在 GPU
解决：确保 model 和输入数据在同一个 device 上

报错 2：RuntimeError: mat1 and mat2 shapes cannot be multiplied
原因：矩阵形状不匹配
解决：检查 nn.Linear(in, out) 的 in 是否等于上一层的 out

报错 3：梯度爆炸（loss 突然变成 nan 或 inf）
原因：学习率太大
解决：降低学习率，或加 gradient clipping：
  torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

报错 4：loss 不下降
原因：学习率太小 / 数据有问题 / 忘记 optimizer.zero_grad()
解决：逐一排查
```

---

## 附录：模型保存和加载

```python
# 保存模型参数
torch.save(model.state_dict(), "model.pth")

# 加载模型参数
model = MyModel()                         # 先创建模型结构
model.load_state_dict(torch.load("model.pth"))  # 再加载参数
model.eval()                              # 切到推理模式
```

---

> **最终目标**：能看懂微调 notebook 里每一行 PyTorch 代码在做什么，能自己修改参数和数据。阶段 6 和项目 3 完成后你就到了。
