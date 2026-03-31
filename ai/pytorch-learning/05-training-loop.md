# 阶段 5：训练循环（最核心）⭐

> **目标**：掌握完整的训练 + 验证 + 测试流程，能独立写出可用的训练代码。
> **预计时间**：3-4 天
> **前置知识**：阶段 1-4（张量 + 自动求导 + 神经网络 + 数据处理）

---

## 1. 训练循环的全貌

```
每一个 epoch（把所有数据看一遍）：

  训练阶段：
    for 每个 batch:
      1. 前向传播：input → model → prediction
      2. 算损失：prediction vs label → loss
      3. 反向传播：loss.backward() → 算梯度
      4. 更新权重：optimizer.step()
      5. 清零梯度：optimizer.zero_grad()

  验证阶段：
    for 每个 batch:
      1. 前向传播（不算梯度）
      2. 算损失 + 准确率
    
    判断：是否过拟合？是否该停？

最终测试：
  用 test_loader 评估最终性能
```

---

## 2. 损失函数的选择

```python
import torch.nn as nn

# 多分类（N 选 1）← 最常用
criterion = nn.CrossEntropyLoss()
# 输入：模型输出 (batch, num_classes)，标签 (batch,)
# 内部自带 Softmax，你不需要手动加

# 二分类（是/否）
criterion = nn.BCEWithLogitsLoss()
# 输入：模型输出 (batch,)，标签 (batch,)
# 内部自带 Sigmoid

# 回归（预测数值）
criterion = nn.MSELoss()
# 均方误差：(prediction - label)² 的平均值

# 回归（对异常值更鲁棒）
criterion = nn.L1Loss()
# 绝对值误差：|prediction - label| 的平均值
```

### 怎么选？

```
你的 label 是整数类别 → CrossEntropyLoss
你的 label 是 0/1    → BCEWithLogitsLoss
你的 label 是浮点数   → MSELoss 或 L1Loss
```

---

## 3. 优化器的选择

```python
import torch.optim as optim

# SGD：最基础
optimizer = optim.SGD(model.parameters(), lr=0.01, momentum=0.9)
# momentum = 动量，帮助跳出局部最优

# Adam：最常用 ⭐
optimizer = optim.Adam(model.parameters(), lr=0.001)
# 自适应学习率，几乎不用调

# AdamW：Adam + 权重衰减（微调常用）⭐
optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.01)
# weight_decay = 正则化，防过拟合

# 8-bit Adam（省显存，微调用）
# 需要 bitsandbytes 库
# 你在 notebook 里看到的 optim="adamw_8bit" 就是这个
```

### 怎么选？

```
新手 / 日常训练   → Adam（lr=0.001）
微调预训练模型    → AdamW（lr=2e-5 ~ 2e-4）
显存不够         → adamw_8bit
想精调          → SGD + momentum（收敛更慢但有时更好）
```

---

## 4. 完整训练循环（核心代码）⭐

```python
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

# ===== 准备工作 =====
device = (
    "cuda" if torch.cuda.is_available()
    else "mps" if torch.backends.mps.is_available()
    else "cpu"
)

model = MyModel().to(device)
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=0.001)

# ===== 训练循环 =====
num_epochs = 10
best_val_loss = float('inf')

for epoch in range(num_epochs):

    # ────────── 训练阶段 ──────────
    model.train()                        # ⭐ 开启训练模式
    train_loss = 0
    train_correct = 0
    train_total = 0

    for batch_x, batch_y in train_loader:
        batch_x = batch_x.to(device)     # 数据放到 GPU/MPS
        batch_y = batch_y.to(device)

        # 1. 前向传播
        outputs = model(batch_x)

        # 2. 算损失
        loss = criterion(outputs, batch_y)

        # 3. 反向传播 + 更新
        optimizer.zero_grad()            # ⭐ 清零梯度
        loss.backward()                  # ⭐ 算梯度
        optimizer.step()                 # ⭐ 更新权重

        # 统计
        train_loss += loss.item()
        _, predicted = outputs.max(1)    # 取概率最高的类别
        train_total += batch_y.size(0)
        train_correct += predicted.eq(batch_y).sum().item()

    train_loss /= len(train_loader)
    train_acc = train_correct / train_total

    # ────────── 验证阶段 ──────────
    model.eval()                         # ⭐ 切到评估模式
    val_loss = 0
    val_correct = 0
    val_total = 0

    with torch.no_grad():               # ⭐ 不计算梯度
        for batch_x, batch_y in val_loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)

            outputs = model(batch_x)
            loss = criterion(outputs, batch_y)

            val_loss += loss.item()
            _, predicted = outputs.max(1)
            val_total += batch_y.size(0)
            val_correct += predicted.eq(batch_y).sum().item()

    val_loss /= len(val_loader)
    val_acc = val_correct / val_total

    # ────────── 打印结果 ──────────
    print(f"Epoch {epoch+1}/{num_epochs}: "
          f"train_loss={train_loss:.4f} train_acc={train_acc:.4f} | "
          f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}")

    # ────────── 保存最佳模型 ──────────
    if val_loss < best_val_loss:
        best_val_loss = val_loss
        torch.save(model.state_dict(), "best_model.pth")
        print(f"  → 保存最佳模型 (val_loss={val_loss:.4f})")
```

### 每一行的意义

```
model.train()
  → 开启 Dropout、BatchNorm 的训练行为

model.eval()
  → 关闭 Dropout（每次输出一致）
  → BatchNorm 用全局统计量（不用当前 batch 的）

with torch.no_grad()
  → 不构建计算图 → 省显存
  → 验证时不需要梯度

optimizer.zero_grad()
  → 必须在 backward() 前调用
  → 否则梯度会和上一步的累加

loss.backward()
  → 链式法则计算所有参数的梯度

optimizer.step()
  → 用梯度更新参数：param = param - lr * grad
```

---

## 6. 判断训练状态

```
场景                        诊断          怎么办
────────────────────────   ─────────    ──────────
train_loss ↓  val_loss ↓   正常           继续训练
train_loss ↓  val_loss ↑   ⚠️ 过拟合     加 Dropout / 减小模型 / 加数据 / 早停
train_loss →  val_loss →   学不动了       增大 lr / 换更大的模型
train_loss ↑              出 bug 了      检查 lr 是否太大 / 数据是否正确
```

### 过拟合的解决方案

```python
# 方法 1：Dropout（随机丢弃部分神经元）
self.dropout = nn.Dropout(0.3)   # 30% 概率丢弃

# 方法 2：权重衰减（weight decay）
optimizer = optim.AdamW(model.parameters(), weight_decay=0.01)

# 方法 3：早停（Early Stopping）
patience = 5           # 容忍 val_loss 不降的轮数
no_improve_count = 0

for epoch in range(100):
    # ... 训练和验证 ...
    if val_loss < best_val_loss:
        best_val_loss = val_loss
        no_improve_count = 0
        torch.save(model.state_dict(), "best_model.pth")
    else:
        no_improve_count += 1
        if no_improve_count >= patience:
            print("早停！验证集 loss 不再下降")
            break

# 方法 4：数据增强（增加数据多样性）
# 图像：翻转、旋转、裁剪
# 文本：同义词替换、随机删除
```

---

## 6. 学习率调度器

> 掌握了完整训练循环后，再来学如何动态调整学习率。

```python
from torch.optim.lr_scheduler import (
    StepLR,
    CosineAnnealingLR,
    LinearLR,
    ReduceLROnPlateau,
)

# 线性衰减：学习率从初始值线性降到 0（notebook 里用的）
scheduler = LinearLR(optimizer, start_factor=1.0, end_factor=0.0, total_iters=100)

# 余弦退火：学习率按余弦曲线下降（常用）
scheduler = CosineAnnealingLR(optimizer, T_max=100)

# 阶梯下降：每 30 步 lr 乘以 0.1
scheduler = StepLR(optimizer, step_size=30, gamma=0.1)

# 自适应：val_loss 不降时自动降 lr
scheduler = ReduceLROnPlateau(optimizer, mode='min', patience=5)

# 在训练循环中使用（加在 epoch 循环的末尾）
for epoch in range(100):
    train_one_epoch()
    validate()
    scheduler.step()       # 每个 epoch 调用一次
    # scheduler.step(val_loss)  # ReduceLROnPlateau 需要传入 val_loss
```

### 为什么要调学习率？

```
前期：大学习率 → 快速找到大致方向
后期：小学习率 → 精细调整，不会跳过最优解

类比：
  找停车位 → 先快速开到停车场附近（大 lr）
           → 再慢慢倒车入位（小 lr）
```

---

## 7. 梯度裁剪

```python
# 防止梯度爆炸（loss 变成 nan/inf）

# 方法 1：按范数裁剪（更常用）
torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
# 如果所有梯度的 L2 范数 > 1.0，等比例缩小

# 方法 2：按值裁剪
torch.nn.utils.clip_grad_value_(model.parameters(), clip_value=0.5)
# 把所有梯度限制在 [-0.5, 0.5]

# 在训练循环中使用（backward 之后，step 之前）
loss.backward()
torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)  # ← 加在这里
optimizer.step()
```

---

## 8. 梯度累积

```python
# 当显存不够用大 batch_size 时，用梯度累积模拟

accumulation_steps = 4  # 累积 4 步
optimizer.zero_grad()   # 开始前清零

for i, (batch_x, batch_y) in enumerate(train_loader):
    batch_x, batch_y = batch_x.to(device), batch_y.to(device)
    
    outputs = model(batch_x)
    loss = criterion(outputs, batch_y)
    loss = loss / accumulation_steps   # ⭐ 损失除以累积步数
    loss.backward()                    # 梯度会累加（不清零）

    if (i + 1) % accumulation_steps == 0:
        optimizer.step()               # ⭐ 每 4 步才更新一次
        optimizer.zero_grad()          # 更新后清零

# 效果等价于 batch_size × accumulation_steps
# 你 notebook 里的 gradient_accumulation_steps=4 就是这个原理
```

---

## 9. 最终测试

```python
# 加载最佳模型
model.load_state_dict(torch.load("best_model.pth"))
model.eval()

test_correct = 0
test_total = 0

with torch.no_grad():
    for batch_x, batch_y in test_loader:
        batch_x, batch_y = batch_x.to(device), batch_y.to(device)

        outputs = model(batch_x)
        _, predicted = outputs.max(1)
        test_total += batch_y.size(0)
        test_correct += predicted.eq(batch_y).sum().item()

test_acc = test_correct / test_total
print(f"最终测试准确率: {test_acc:.4f}")
```

---

## 练习

```
1. 手写一个包含 train + val 的完整循环，训练一个分类模型
2. 实现早停（Early Stopping），观察它在第几个 epoch 停下来
3. 分别用 Adam 和 SGD 训练同一个模型，对比 loss 曲线
4. 实现梯度累积（accumulation_steps=4），确认效果等同于大 batch
5. 故意设一个很大的 lr（如 1.0），观察 loss 爆炸
6. 加 gradient clipping，看能不能拯救大 lr 的训练
```

---

## 本阶段小结

```
学到了什么：
  ✅ 完整的 train + val + test 循环
  ✅ 损失函数和优化器的选择
  ✅ 学习率调度器的使用
  ✅ 过拟合判断和解决（Dropout、早停、weight decay）
  ✅ 梯度裁剪和梯度累积

和 notebook 的关系：
  SFTTrainer 内部做的事 = 你这个阶段学的所有内容
    trainer.train() 
    → 就是上面的 for epoch 循环
    → 包含 forward + backward + step + zero_grad
    → 包含 gradient_accumulation_steps
    → 包含 lr_scheduler
    → 包含 logging

  现在你完全能理解 SFTTrainer 的每个参数了。

下一阶段预告：
  现实中不需要从零训练。下一阶段学加载别人训练好的模型，
  冻结大部分参数，只微调一小部分 → 迁移学习。
```
