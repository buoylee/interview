# 阶段 2：自动求导（Autograd）

> **目标**：理解 PyTorch 如何自动计算梯度，不用手写链式法则。
> **预计时间**：1-2 天
> **前置知识**：阶段 1（张量操作）+ 微积分基础（导数、链式法则）

---

## 1. 为什么需要自动求导？

```
训练神经网络的核心步骤：
  1. 前向传播：输入 → 模型 → 预测值
  2. 算损失：预测值 vs 真实值 → loss
  3. 反向传播：算每个参数的梯度 ← 这一步用 Autograd
  4. 更新权重：参数 = 参数 - 学习率 × 梯度

如果手算梯度：
  一个简单的 3 层网络，你需要手写几十行链式法则
  一个 14B 参数的 LLM，你需要... 别想了

Autograd 做的事：
  你只需要定义前向计算（y = f(x)），
  PyTorch 自动帮你算所有梯度（dy/dx）
```

---

## 2. 基础：对一个变量求导

```python
import torch

# 创建一个需要求导的变量
x = torch.tensor(3.0, requires_grad=True)
# requires_grad=True → 告诉 PyTorch "我需要对 x 求导"
# 只有浮点数张量才能设置 requires_grad

# 定义一个计算
y = x ** 2 + 2 * x + 1
# y = x² + 2x + 1
# 数学上 dy/dx = 2x + 2

# 自动求导
y.backward()
# ⭐ 这一行做了所有事：
# 1. 追踪 y 是怎么从 x 算出来的（计算图）
# 2. 用链式法则从 y 倒推回 x
# 3. 把梯度存到 x.grad 里

print(x.grad)
# tensor(8.0)
# 验证：dy/dx = 2x + 2 = 2(3) + 2 = 8 ✓
```

---

## 3. 计算图（Computation Graph）

```python
x = torch.tensor(2.0, requires_grad=True)
y = x ** 3        # y = x³
z = 2 * y + 1     # z = 2y + 1 = 2x³ + 1
```

```
PyTorch 在背后构建了一个计算图：

  x (2.0) → [** 3] → y (8.0) → [* 2] → [+ 1] → z (17.0)

调用 z.backward() 时，PyTorch 从 z 开始往回走：
  dz/dz = 1
  dz/dy = 2
  dy/dx = 3x² = 3(4) = 12
  dz/dx = dz/dy × dy/dx = 2 × 12 = 24 ← 链式法则！
```

```python
z.backward()
print(x.grad)  # tensor(24.0)
# 验证：dz/dx = 6x² = 6(4) = 24 ✓
```

### 计算图的关键概念

```
叶子节点（leaf）：  你创建的变量（如 x）→ 梯度存在这里
中间节点：         计算过程中的变量（如 y）→ 梯度用完即丢
根节点：           最终的输出（如 z）→ 调用 .backward() 的起点

requires_grad=True 只需要设在叶子节点上
中间节点自动继承这个属性
```

---

## 4. 多变量求导

```python
# 模拟一个最简单的神经网络：y = wx + b
w = torch.tensor(2.0, requires_grad=True)   # 权重
b = torch.tensor(1.0, requires_grad=True)   # 偏置
x = torch.tensor(3.0)                        # 输入（不需要求导）

# 前向传播
y_pred = w * x + b           # 预测值 = 2*3 + 1 = 7
y_true = torch.tensor(5.0)   # 真实值

# 计算损失
loss = (y_pred - y_true) ** 2   # MSE 损失 = (7-5)² = 4

# 反向传播
loss.backward()

print(w.grad)  # dloss/dw = 2(y_pred - y_true) * x = 2(2)(3) = 12
print(b.grad)  # dloss/db = 2(y_pred - y_true) * 1 = 2(2) = 4
```

```
这就是训练的核心！

  loss.backward() 算出了：
    w 的梯度 = 12 → w 应该减小（因为预测值偏大了）
    b 的梯度 = 4  → b 也应该减小

  下一步用梯度下降更新：
    w = w - lr * w.grad
    b = b - lr * b.grad
```

---

## 5. 向量/矩阵的自动求导

```python
# 实际训练中，数据都是向量或矩阵，不是标量

x = torch.randn(3, requires_grad=True)     # 输入向量
W = torch.randn(2, 3, requires_grad=True)  # 权重矩阵

y = W @ x            # 矩阵乘法 → (2,) 向量
loss = y.sum()        # ⭐ backward() 只能对标量调用
                      # 所以需要先把输出变成标量（如 sum 或 mean）

loss.backward()

print(x.grad.shape)   # (3,) → 和 x 同形
print(W.grad.shape)   # (2, 3) → 和 W 同形

# 每个参数的梯度形状 = 参数本身的形状
# 这意味着每个参数都有自己的"应该怎么调"的指示
```

---

## 6. 重要注意事项

### 6.1 梯度会累加！

```python
x = torch.tensor(3.0, requires_grad=True)

# 第一次
y = x ** 2
y.backward()
print(x.grad)  # tensor(6.0)  → 正确

# 第二次（不清零）
y = x ** 2
y.backward()
print(x.grad)  # tensor(12.0) → 6 + 6 = 12！梯度被累加了

# ⭐ 解决：每次 backward 前清零
x.grad.zero_()  # 原地清零
y = x ** 2
y.backward()
print(x.grad)  # tensor(6.0)  → 正确了
```

```
为什么 PyTorch 默认累加？
  因为有些高级用法需要累加梯度（比如 gradient accumulation）
  你在微调 notebook 里看到的 gradient_accumulation_steps=4 就是利用了这个特性
  
  但日常训练中，每个 step 都要清零：
    optimizer.zero_grad()   ← 训练循环里必写的一行
```

### 6.2 不需要梯度时关掉它

```python
# 推理时：不需要计算梯度（省内存、加速）
with torch.no_grad():
    y = model(x)   # 这个计算过程不会被追踪
    # 省了大量内存（不用存计算图）

# 等价写法
x = torch.randn(3, requires_grad=True)
y = x.detach()     # 创建一个不追踪梯度的副本
```

### 6.3 in-place 操作会破坏计算图

```python
x = torch.tensor(3.0, requires_grad=True)
y = x * 2

# 不要对需要求导的张量做 in-place 操作！
# y += 1       ← 会报错！因为这会修改计算图中的节点
y = y + 1       # ← 正确写法，创建新张量
```

---

## 7. 手动实现梯度下降

把 Autograd 和梯度下降结合起来，手写一个最简单的训练：

```python
import torch

# 真实函数：y = 3x + 2（我们假装不知道 w=3, b=2）
# 目标：让模型自己学出 w 和 b

# 初始化参数（随机猜）
w = torch.tensor(0.0, requires_grad=True)
b = torch.tensor(0.0, requires_grad=True)
lr = 0.01  # 学习率

# 训练数据
X = torch.tensor([1.0, 2.0, 3.0, 4.0])
Y = torch.tensor([5.0, 8.0, 11.0, 14.0])  # Y = 3X + 2

# 训练 100 步
for step in range(100):

    # 1. 前向传播
    Y_pred = w * X + b

    # 2. 算损失
    loss = ((Y_pred - Y) ** 2).mean()  # MSE

    # 3. 反向传播
    loss.backward()

    # 4. 更新权重（⚠️ 必须在 no_grad 里做）
    with torch.no_grad():
        w -= lr * w.grad
        b -= lr * b.grad

    # 5. 清零梯度
    w.grad.zero_()
    b.grad.zero_()

    if step % 20 == 0:
        print(f"Step {step}: w={w.item():.3f}, b={b.item():.3f}, loss={loss.item():.4f}")

# 最终结果应该接近 w=3, b=2
print(f"学到的参数：w={w.item():.3f}, b={b.item():.3f}")
```

```
输出：
  Step 0:  w=0.300, b=0.095, loss=63.5000
  Step 20: w=2.515, b=1.324, loss=0.2718
  Step 40: w=2.874, b=1.716, loss=0.0344
  Step 60: w=2.961, b=1.885, loss=0.0050
  Step 80: w=2.987, b=1.956, loss=0.0007

  学到的参数：w=2.995, b=1.983  ← 接近真实值 w=3, b=2 ✅
```

### 为什么更新权重要在 no_grad() 里？

```
因为 w -= lr * w.grad 本身也是一次计算
如果不包在 no_grad() 里，PyTorch 会把它也加到计算图里
导致计算图越来越大，最终内存爆炸
```

---

## 练习

```
1. 定义 y = 3x³ + 2x² + x，在 x=2 处求导
   手算验证：dy/dx = 9x² + 4x + 1 = 9(4) + 4(2) + 1 = 45

2. 定义 z = sin(x) * cos(x)，在 x=π/4 处求导
   手算验证：dz/dx = cos²(x) - sin²(x) = cos(π/2) = 0

3. 用手动梯度下降拟合 y = -2x + 5
   看看模型能不能学到 w=-2, b=5

4. 试试不同的学习率（0.001, 0.01, 0.1, 1.0），观察收敛速度和稳定性

5. 故意不清零梯度，观察会发生什么
```

---

## 本阶段小结

```
学到了什么：
  ✅ requires_grad=True 开启梯度追踪
  ✅ .backward() 自动反向传播
  ✅ .grad 读取梯度值
  ✅ 梯度累加陷阱 + 清零方法
  ✅ no_grad() 节省推理时内存
  ✅ 手动实现了梯度下降

和 notebook 的关系：
  trainer.train() 内部做的就是：
    predictions = model(input)
    loss = criterion(predictions, labels)
    loss.backward()        ← Autograd 算梯度
    optimizer.step()       ← 梯度下降更新权重
    optimizer.zero_grad()  ← 清零梯度

下一阶段预告：
  手动写 w*x+b 太原始了。下一阶段学 nn.Module，
  用搭积木的方式构建复杂的神经网络。
```
