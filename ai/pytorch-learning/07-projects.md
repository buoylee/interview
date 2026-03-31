# 阶段 7：实战项目

> **目标**：用前 6 个阶段的知识完成 3 个递进项目，从入门到衔接 fine-tuning。
> **预计时间**：3-5 天
> **前置知识**：阶段 1-6

---

## 项目 1：MNIST 手写数字识别

### 目标

```
用最经典的数据集跑通完整流程：
  数据加载 → 搭模型 → 训练 → 验证 → 测试
  准确率 > 97%
```

### 完整代码

```python
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
import torchvision
import torchvision.transforms as transforms

# ===== 1. 设备 =====
device = (
    "cuda" if torch.cuda.is_available()
    else "mps" if torch.backends.mps.is_available()
    else "cpu"
)
print(f"Using: {device}")

# ===== 2. 数据 =====
transform = transforms.Compose([
    transforms.ToTensor(),                # 图片 → [0,1] 张量
    transforms.Normalize((0.1307,), (0.3081,))  # MNIST 的均值和标准差
])

full_train = torchvision.datasets.MNIST('./data', train=True, download=True, transform=transform)
test_dataset = torchvision.datasets.MNIST('./data', train=False, download=True, transform=transform)

# 划分 train / val
train_size = int(0.9 * len(full_train))
val_size = len(full_train) - train_size
train_dataset, val_dataset = random_split(full_train, [train_size, val_size])

train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=64, shuffle=False)
test_loader = DataLoader(test_dataset, batch_size=64, shuffle=False)

print(f"Train: {len(train_dataset)}, Val: {len(val_dataset)}, Test: {len(test_dataset)}")

# ===== 3. 模型 =====
class MNISTModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.flatten = nn.Flatten()            # 28×28 → 784
        self.fc1 = nn.Linear(784, 256)
        self.fc2 = nn.Linear(256, 128)
        self.fc3 = nn.Linear(128, 10)          # 10 个数字类别
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.2)

    def forward(self, x):
        x = self.flatten(x)                    # (batch, 1, 28, 28) → (batch, 784)
        x = self.dropout(self.relu(self.fc1(x)))
        x = self.dropout(self.relu(self.fc2(x)))
        x = self.fc3(x)                        # 不加激活（CrossEntropyLoss 自带 Softmax）
        return x

model = MNISTModel().to(device)

# 打印参数量
total = sum(p.numel() for p in model.parameters())
print(f"Total parameters: {total:,}")  # ~235K

# ===== 4. 训练配置 =====
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=0.001)

# ===== 5. 训练循环 =====
num_epochs = 10
best_val_acc = 0
train_losses, val_losses = [], []

for epoch in range(num_epochs):

    # --- 训练 ---
    model.train()
    epoch_loss = 0
    correct, total = 0, 0

    for images, labels in train_loader:
        images, labels = images.to(device), labels.to(device)

        outputs = model(images)
        loss = criterion(outputs, labels)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        epoch_loss += loss.item()
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

    train_loss = epoch_loss / len(train_loader)
    train_acc = correct / total
    train_losses.append(train_loss)

    # --- 验证 ---
    model.eval()
    epoch_loss = 0
    correct, total = 0, 0

    with torch.no_grad():
        for images, labels in val_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)

            epoch_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()

    val_loss = epoch_loss / len(val_loader)
    val_acc = correct / total
    val_losses.append(val_loss)

    print(f"Epoch {epoch+1:2d}/{num_epochs}: "
          f"train_loss={train_loss:.4f} train_acc={train_acc:.4f} | "
          f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}")

    if val_acc > best_val_acc:
        best_val_acc = val_acc
        torch.save(model.state_dict(), "mnist_best.pth")

# ===== 6. 测试 =====
model.load_state_dict(torch.load("mnist_best.pth"))
model.eval()
correct, total = 0, 0

with torch.no_grad():
    for images, labels in test_loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

print(f"\n最终测试准确率: {correct/total:.4f}")  # 应该 > 0.97

# ===== 7. 画 loss 曲线 =====
try:
    import matplotlib.pyplot as plt
    plt.figure(figsize=(8, 4))
    plt.plot(train_losses, label='Train Loss')
    plt.plot(val_losses, label='Val Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.legend()
    plt.title('Training Progress')
    plt.savefig('loss_curve.png')
    plt.show()
    print("Loss 曲线已保存到 loss_curve.png")
except ImportError:
    print("安装 matplotlib 可以画 loss 曲线: pip install matplotlib")
```

### 预期输出

```
Epoch  1/10: train_loss=0.4500 train_acc=0.8700 | val_loss=0.1800 val_acc=0.9500
Epoch  2/10: train_loss=0.1500 train_acc=0.9550 | val_loss=0.1200 val_acc=0.9650
...
Epoch 10/10: train_loss=0.0500 train_acc=0.9850 | val_loss=0.0650 val_acc=0.9780

最终测试准确率: 0.9750+

如果你的结果：
  - 准确率 > 97% → 正常
  - 准确率 < 90% → 检查数据预处理或模型结构
  - loss 不降          → 检查学习率或 device 是否正确
```

### 这个项目用到了哪些阶段的知识

```
阶段 1：创建张量，.to(device)
阶段 2：loss.backward() 自动求导
阶段 3：nn.Module 搭建模型，nn.Linear, nn.ReLU, nn.Dropout
阶段 4：Dataset（MNIST），DataLoader，random_split
阶段 5：完整训练循环（train + val + test），保存最佳模型
```

### 做完后思考

```
1. 把 Dropout 从 0.2 改成 0.5，准确率变化了吗？（感受过拟合控制）
2. 把 Adam 换成 SGD，训练速度有什么不同？
3. 把学习率从 0.001 改成 0.1，会发生什么？（感受学习率的重要性）
```

---

## 项目 2：文本情感分类（BERT 迁移学习）

### 目标

```
用 Hugging Face 预训练的 BERT 做电影评论情感分类：
  输入："This movie is great!" → 输出：positive
  输入："Terrible waste of time" → 输出：negative
```

### 完整代码

```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from transformers import Trainer, TrainingArguments
from datasets import load_dataset
import torch
import numpy as np

# ===== 1. 加载数据 =====
dataset = load_dataset("imdb")
print(dataset)
# DatasetDict({
#     train: Dataset({features: ['text', 'label'], num_rows: 25000})
#     test:  Dataset({features: ['text', 'label'], num_rows: 25000})
# })

# 为了快速演示，只用一小部分数据
small_train = dataset["train"].shuffle(seed=42).select(range(2000))
small_test = dataset["test"].shuffle(seed=42).select(range(500))

# ===== 2. 加载模型和分词器 =====
model_name = "distilbert-base-uncased"   # 小型 BERT（更快）
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(
    model_name, num_labels=2
)

# ===== 3. 分词 =====
def tokenize_function(examples):
    return tokenizer(
        examples["text"],
        padding="max_length",
        truncation=True,
        max_length=256
    )

train_tokenized = small_train.map(tokenize_function, batched=True)
test_tokenized = small_test.map(tokenize_function, batched=True)

# ===== 4. 评估指标 =====
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    accuracy = (predictions == labels).mean()
    return {"accuracy": accuracy}

# ===== 5. 训练 =====
training_args = TrainingArguments(
    output_dir="./bert-imdb",
    num_train_epochs=3,
    per_device_train_batch_size=16,
    per_device_eval_batch_size=16,
    learning_rate=2e-5,          # 微调预训练模型用小学习率！
    weight_decay=0.01,
    eval_strategy="epoch",
    save_strategy="epoch",
    logging_steps=50,
    load_best_model_at_end=True,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_tokenized,
    eval_dataset=test_tokenized,
    compute_metrics=compute_metrics,
)

trainer.train()

# ===== 6. 评估 =====
results = trainer.evaluate()
print(f"最终准确率: {results['eval_accuracy']:.4f}")

# ===== 7. 使用 =====
from transformers import pipeline
classifier = pipeline("sentiment-analysis", model=model, tokenizer=tokenizer)
print(classifier("This movie is absolutely wonderful!"))
# [{'label': 'POSITIVE', 'score': 0.9998}]
```

### 预期输出

```
Epoch 1: eval_accuracy=0.8200
Epoch 2: eval_accuracy=0.8700
Epoch 3: eval_accuracy=0.8900+

如果你的结果：
  - 准确率 > 85% → 正常（2000条训练数据已经很少了）
  - 准确率 ~ 50%  → 模型没学到东西，检查 lr 或数据格式
```

### 做完后思考

```
1. 把 learning_rate 从 2e-5 改成 2e-3，会发生什么？
   （微调预训练模型时 lr 必须小，否则破坏已学到的知识）
2. 只用 100 条数据训练，准确率能到多少？（感受数据量的影响）
3. 冻结 BERT 所有参数只训练分类头，对比结果
```

---

## 项目 3：手写 LoRA 微调流程

### 目标

```
不用 SFTTrainer，自己写训练循环 + LoRA 微调 GPT-2
  → 完全理解你 fine-tuning notebook 里每一步在做什么
```

### 完整代码

```python
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model
from datasets import load_dataset

# ===== 1. 设备 =====
device = (
    "cuda" if torch.cuda.is_available()
    else "mps" if torch.backends.mps.is_available()
    else "cpu"
)

# ===== 2. 加载模型 =====
model_name = "gpt2"  # 124M 参数的小模型
tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(model_name)

# ===== 3. 添加 LoRA =====
lora_config = LoraConfig(
    r=8,
    lora_alpha=16,
    target_modules=["c_attn"],  # GPT-2 的注意力层
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()
# trainable params: X || all params: Y || trainable%: Z%

model = model.to(device)

# ===== 4. 准备数据 =====
dataset = load_dataset("tatsu-lab/alpaca", split="train[:500]")

def format_and_tokenize(example):
    text = f"### Instruction:\n{example['instruction']}\n\n### Response:\n{example['output']}{tokenizer.eos_token}"
    tokens = tokenizer(text, truncation=True, max_length=256, padding="max_length")
    tokens["labels"] = tokens["input_ids"].copy()
    return tokens

dataset = dataset.map(format_and_tokenize, remove_columns=dataset.column_names)
dataset.set_format("torch")

dataloader = DataLoader(dataset, batch_size=4, shuffle=True)

# ===== 5. 训练前推理（对比用）=====
print("\n===== 训练前 =====")
model.eval()
test_input = "### Instruction:\nWhat is the capital of France?\n\n### Response:\n"
inputs = tokenizer(test_input, return_tensors="pt").to(device)
with torch.no_grad():
    outputs = model.generate(**inputs, max_new_tokens=50, temperature=0.7)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))

# ===== 6. 手写训练循环 =====
optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4)
num_epochs = 3

print("\n===== 开始训练 =====")
for epoch in range(num_epochs):
    model.train()
    total_loss = 0

    for step, batch in enumerate(dataloader):
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["labels"].to(device)

        # 前向传播
        outputs = model(input_ids=input_ids,
                        attention_mask=attention_mask,
                        labels=labels)
        loss = outputs.loss

        # 反向传播
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()

        total_loss += loss.item()

        if step % 20 == 0:
            print(f"  Epoch {epoch+1} Step {step}: loss={loss.item():.4f}")

    avg_loss = total_loss / len(dataloader)
    print(f"Epoch {epoch+1}/{num_epochs}: avg_loss={avg_loss:.4f}")

# ===== 7. 训练后推理（对比！）=====
print("\n===== 训练后 =====")
model.eval()
inputs = tokenizer(test_input, return_tensors="pt").to(device)
with torch.no_grad():
    outputs = model.generate(**inputs, max_new_tokens=50, temperature=0.7)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))

# ===== 8. 保存 =====
model.save_pretrained("./gpt2-lora-adapter")
tokenizer.save_pretrained("./gpt2-lora-adapter")
print("\n模型已保存到 ./gpt2-lora-adapter")
```

### 预期输出

```
训练前：
  "### Response: What is the capital of France?\n\nThe capital of France is..."
  → 可能会生成无关内容或重复问题

Epoch 1: avg_loss=3.5000
Epoch 2: avg_loss=2.8000
Epoch 3: avg_loss=2.3000

训练后：
  "### Response: The capital of France is Paris."
  → 应该能生成更直接的回答（虽然只用了 500 条数据，效果有限）

如果你的结果：
  - loss 在 3 个 epoch 内持续下降 → 正常
  - 训练前后输出有差别 → 微调生效了
  - loss 不降 → 检查数据格式和 lr
```

### 这个项目和你 notebook 的完整对应

```
你 notebook 里的代码              这个项目里的代码
─────────────────────           ──────────────────
FastLanguageModel.from_pretrained  AutoModelForCausalLM.from_pretrained
FastLanguageModel.get_peft_model   get_peft_model(model, lora_config)
load_dataset(...)                  load_dataset("tatsu-lab/alpaca")
apply_chat_template                手动拼接 prompt
SFTTrainer + trainer.train()       手写 for 循环
model.save_pretrained              model.save_pretrained

区别：
  notebook 用了 Unsloth 加速 + SFTTrainer 封装
  这里用标准 PyTorch + peft，手写了每一步

掌握了这个项目，你就完全理解了 fine-tuning 的底层原理。
```

---

## 总结：3 个项目的递进关系

```
项目 1（MNIST）
  → 巩固 PyTorch 基础：张量 + 模型 + 训练循环
  → 所有代码从零手写

项目 2（BERT 情感分类）
  → 衔接迁移学习：加载预训练模型 + Trainer
  → 开始用 Hugging Face 生态

项目 3（GPT-2 LoRA 微调）
  → 衔接 fine-tuning：LoRA + 手写训练循环
  → 完全理解微调 notebook 的每一行代码
  
完成这 3 个项目后，你就能在面试中说：
  "我理解 fine-tuning 的底层原理，
   从 PyTorch 的自动求导到 LoRA 的实现，
   我都手写过完整的训练流程。"
```
