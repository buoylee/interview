# 阶段 4：数据处理（Dataset + DataLoader）

> **目标**：学会用 PyTorch 的数据管道高效地加载、预处理和分批喂数据。
> **预计时间**：1-2 天
> **前置知识**：阶段 1-3（张量 + 自动求导 + 神经网络）

---

## 1. 为什么需要 Dataset 和 DataLoader？

```
问题：
  训练数据可能有 100 万条
  不可能一次性全部塞进 GPU（内存爆炸）
  也不可能一条条喂（太慢）

解决：
  Dataset → 定义"数据在哪、怎么读一条"
  DataLoader → 自动分 batch、打乱顺序、多进程加载
```

---

## 2. 自定义 Dataset

```python
from torch.utils.data import Dataset

class MyDataset(Dataset):
    def __init__(self, texts, labels):
        """初始化：接收数据，可以在这里做预处理"""
        self.texts = texts
        self.labels = labels
        # 也可以在这里：
        # - 读取 CSV/JSON 文件
        # - 从数据库加载
        # - 做一些全局预处理

    def __len__(self):
        """返回数据集大小"""
        return len(self.texts)
        # DataLoader 需要知道总共有多少条数据

    def __getitem__(self, idx):
        """返回第 idx 条数据"""
        return self.texts[idx], self.labels[idx]
        # idx 是整数索引，DataLoader 会自动传入
        # 返回值可以是 tuple、dict、单个张量...
```

### 三个必须实现的方法

```
__init__   → 读数据 / 做预处理（只在创建对象时执行一次）
__len__    → 返回数据集大小（len(dataset) 时调用）
__getitem__ → 返回一条数据（dataset[0] 时调用）
```

### 实际例子：数字分类数据集

```python
import torch
from torch.utils.data import Dataset

class NumberDataset(Dataset):
    def __init__(self):
        # 100 条数据：输入是 3 维特征，标签是 0 或 1
        self.X = torch.randn(100, 3)
        self.y = torch.randint(0, 2, (100,))

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

# 使用
dataset = NumberDataset()
print(len(dataset))          # 100
print(dataset[0])            # (tensor([...]), tensor(0))
print(dataset[0][0].shape)   # torch.Size([3])
```

---

## 3. DataLoader：自动分 batch

```python
from torch.utils.data import DataLoader

dataset = NumberDataset()

dataloader = DataLoader(
    dataset,
    batch_size = 16,       # 每次取 16 条数据
    shuffle = True,        # 每个 epoch 随机打乱顺序
    num_workers = 0,       # 用多少个子进程加载数据
    drop_last = False,     # 最后不足一个 batch 的数据是否丢弃
)

# 遍历 DataLoader
for batch_x, batch_y in dataloader:
    print(batch_x.shape)   # torch.Size([16, 3]) → 16 条数据，3 个特征
    print(batch_y.shape)   # torch.Size([16]) → 16 个标签
    break  # 只看第一个 batch
```

### DataLoader 参数详解

```
batch_size = 16
  → 每次取 16 条数据组成一个 batch
  → 越大越好（梯度更稳定），但受显存限制
  → 常用值：16, 32, 64

shuffle = True
  → 每个 epoch 重新随机排列数据
  → 训练时必须 True（避免模型记住数据顺序）
  → 验证/测试时 False（结果要可复现）

num_workers = 0
  → Mac 上建议设 0（避免 MPS 兼容问题）
  → Linux/Colab 上可以设 2-4（加速数据加载）

drop_last = True
  → 100 条数据，batch_size=16，最后剩 4 条
  → True: 丢弃最后 4 条（6 个完整 batch）
  → False: 保留（最后一个 batch 只有 4 条）
  → 训练时通常 True，评估时 False
```

---

## 4. 数据划分：train / val / test

```python
from torch.utils.data import random_split

dataset = NumberDataset()  # 假设有 100 条数据

# 按 80:10:10 划分
train_size = int(0.8 * len(dataset))    # 80
val_size = int(0.1 * len(dataset))      # 10
test_size = len(dataset) - train_size - val_size  # 10

train_dataset, val_dataset, test_dataset = random_split(
    dataset,
    [train_size, val_size, test_size],
    generator=torch.Generator().manual_seed(42)  # 固定随机种子
)

print(f"Train: {len(train_dataset)}, Val: {len(val_dataset)}, Test: {len(test_dataset)}")
# Train: 80, Val: 10, Test: 10

# 分别创建 DataLoader
train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
val_loader   = DataLoader(val_dataset,   batch_size=16, shuffle=False)
test_loader  = DataLoader(test_dataset,  batch_size=16, shuffle=False)
```

### 为什么要划分三份？

```
Train（训练集）：模型学习用的数据
  → 把这个给模型看，让它学规律

Val（验证集）：训练过程中监控用的数据
  → 模型没见过，用来检查是否过拟合
  → 如果 train_loss ↓ 但 val_loss ↑ → 过拟合了

Test（测试集）：最终评估用的数据
  → 训练和调参完全结束后才用
  → 模拟真实世界中模型没见过的数据
```

---

## 5. 使用 PyTorch 内置数据集

```python
import torchvision
import torchvision.transforms as transforms

# MNIST 手写数字数据集（PyTorch 自带）
transform = transforms.Compose([
    transforms.ToTensor(),           # 图片 → 张量
    transforms.Normalize((0.5,), (0.5,))  # 归一化到 [-1, 1]
])

train_dataset = torchvision.datasets.MNIST(
    root='./data',         # 下载到哪里
    train=True,            # 训练集
    download=True,         # 自动下载
    transform=transform    # 预处理
)

test_dataset = torchvision.datasets.MNIST(
    root='./data',
    train=False,
    download=True,
    transform=transform
)

print(f"训练集: {len(train_dataset)} 条")  # 60000
print(f"测试集: {len(test_dataset)} 条")   # 10000

# 看一条数据
image, label = train_dataset[0]
print(f"图片形状: {image.shape}")  # torch.Size([1, 28, 28])
print(f"标签: {label}")            # 5（这张图是数字 5）

# 创建 DataLoader
train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
```

---

## 6. 使用 Hugging Face 数据集（了解即可，阶段 6 会用到）

> 这一节用到了 `tokenizer`，你现在可能还不熟悉。先看懂大意即可，阶段 6 会详细学。

```python
from datasets import load_dataset

# 加载 Hugging Face 上的数据集
hf_dataset = load_dataset("imdb", split="train")

print(hf_dataset[0])
# {'text': 'This movie was great...', 'label': 1}

# 转成 PyTorch 格式
hf_dataset.set_format("torch")

# 或者转成自定义 Dataset
class IMDBDataset(Dataset):
    def __init__(self, hf_data, tokenizer, max_len=128):
        self.data = hf_data
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        text = self.data[idx]["text"]
        label = self.data[idx]["label"]

        tokens = self.tokenizer(
            text,
            max_length=self.max_len,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )

        return {
            "input_ids": tokens["input_ids"].squeeze(),
            "attention_mask": tokens["attention_mask"].squeeze(),
            "label": torch.tensor(label)
        }
```

---

## 7. 数据预处理：transforms

> 图像预处理用 `transforms`，文本预处理用 `tokenizer`（阶段 6 详解）。

```python
import torchvision.transforms as transforms

# 图像预处理流水线
transform = transforms.Compose([
    transforms.Resize(256),             # 缩放到 256×256
    transforms.CenterCrop(224),         # 中心裁剪 224×224
    transforms.RandomHorizontalFlip(),  # 随机水平翻转（数据增强）
    transforms.ToTensor(),              # 转张量 [0,1]
    transforms.Normalize(               # 标准化
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    ),
])

# 为什么要 Normalize？
# 让每个特征的均值≈0，方差≈1
# 这样梯度下降更稳定，训练更快收敛
```

### 文本预处理（NLP）

```python
# NLP 的预处理由 tokenizer 完成（不用 transforms）

from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")

text = "Hello, how are you?"
tokens = tokenizer(text, padding="max_length", max_length=16, return_tensors="pt")

print(tokens["input_ids"])
# tensor([[ 101, 7592, 1010, 2129, 2024, 2017, 1029, 102, 0, 0, ...]])
#          [CLS]  hello  ,    how   are   you    ?   [SEP] [PAD]...

print(tokens["attention_mask"])
# tensor([[1, 1, 1, 1, 1, 1, 1, 1, 0, 0, ...]])
# 1 = 真实 token，0 = padding（模型会忽略 0 的位置）
```

---

## 8. collate_fn：自定义如何组 batch（了解即可）

> 日常训练中很少需要手写 collate_fn。Hugging Face Trainer 会自动处理。
> 这里了解概念即可，遇到变长数据时再回来看。

```python
# 当每条数据长度不同时，DataLoader 默认无法 stack 成 batch
# 需要自定义 collate_fn 来处理

def my_collate_fn(batch):
    """batch 是一个 list，每个元素是 __getitem__ 的返回值"""
    texts = [item["input_ids"] for item in batch]
    labels = [item["label"] for item in batch]

    # padding 到同一长度
    texts = torch.nn.utils.rnn.pad_sequence(texts, batch_first=True)
    labels = torch.stack(labels)

    return {"input_ids": texts, "labels": labels}

dataloader = DataLoader(
    dataset,
    batch_size=16,
    collate_fn=my_collate_fn   # 使用自定义的组 batch 方法
)
```

---

## 练习

```
1. 写一个自定义 Dataset，生成 200 条 (x, y=2x+1) 的数据
2. 用 random_split 划分成 train(160)/val(20)/test(20)
3. 用 DataLoader 遍历 train_loader，打印每个 batch 的形状
4. 加载 MNIST 数据集（PyTorch 自带），看一张图片的形状和标签
5. 尝试不同的 batch_size（1, 8, 64, 256），观察遍历速度差异
```

---

## 本阶段小结

```
学到了什么：
  ✅ Dataset 定义数据的读取方式（__getitem__）
  ✅ DataLoader 自动分 batch、打乱、多进程
  ✅ train/val/test 数据划分
  ✅ 内置数据集（MNIST）和外部数据集（Hugging Face）
  ✅ 数据预处理（transforms / tokenizer）

和 notebook 的关系：
  load_dataset("unsloth/OpenMathReasoning-mini")
    → Hugging Face 的 Dataset，底层转成 PyTorch 格式

  SFTTrainer(train_dataset=combined_dataset)
    → Trainer 内部自动创建 DataLoader
    → per_device_train_batch_size=2 就是 DataLoader 的 batch_size

下一阶段预告：
  模型有了，数据有了，下一阶段把它们组合起来 → 完整的训练循环。
  这是 PyTorch 最核心的部分。
```
