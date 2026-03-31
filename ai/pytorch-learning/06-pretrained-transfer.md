# 阶段 6：预训练模型与迁移学习

> **目标**：学会加载别人训练好的模型，冻结 + 微调，衔接 fine-tuning 工作流。
> **预计时间**：2-3 天
> **前置知识**：阶段 1-5

---

## 1. 为什么不从零训练？

```
从零训练一个好模型需要：
  - 海量数据（GPT-4 用了几万亿 token）
  - 海量算力（上千块 A100 GPU）
  - 海量时间（几周到几个月）

迁移学习的思路：
  别人花了 1 亿美元训好了模型 → 你免费下载
  → 冻结大部分参数
  → 只训练一小部分（适配你的任务）
  → 用你自己的小数据集
  → 花几小时甚至几分钟搞定
```

---

## 2. 计算机视觉：torchvision 预训练模型

### 2.1 加载预训练模型

```python
import torch
import torch.nn as nn
import torchvision.models as models

# 加载在 ImageNet（128 万张图，1000 类）上训练好的 ResNet18
model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)

# 查看模型结构
print(model)
# 会打印出所有层：conv1, bn1, layer1, layer2, ..., fc

# 查看最后一层
print(model.fc)
# Linear(in_features=512, out_features=1000)
# 原来分 1000 类，你的任务可能只分 2 类
```

### 2.2 冻结 + 替换输出层

```python
# ===== 策略 1：只训练最后一层（最省资源）=====

# 冻结所有参数
for param in model.parameters():
    param.requires_grad = False

# 替换最后一层（这一层的参数是新的，需要训练）
num_classes = 2  # 你的任务有几个类
model.fc = nn.Linear(512, num_classes)
# 新创建的层默认 requires_grad=True

# 只优化最后一层的参数
optimizer = torch.optim.Adam(model.fc.parameters(), lr=0.001)

# 确认可训练参数量
trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
print(f"可训练: {trainable:,} / {total:,} ({trainable/total*100:.2f}%)")
# 约 1,026 / 11,177,538 (0.01%)
```

```python
# ===== 策略 2：微调最后几层（效果更好）=====

# 冻结所有参数
for param in model.parameters():
    param.requires_grad = False

# 解冻最后一个 block（layer4）
for param in model.layer4.parameters():
    param.requires_grad = True

# 替换输出层
model.fc = nn.Linear(512, num_classes)

# 优化解冻的参数（用不同的学习率）
optimizer = torch.optim.Adam([
    {"params": model.layer4.parameters(), "lr": 1e-4},   # 预训练层用小 lr
    {"params": model.fc.parameters(),     "lr": 1e-3},   # 新层用大 lr
])
```

### 2.3 完整训练示例

```python
import torchvision.transforms as transforms
from torch.utils.data import DataLoader

# 数据预处理（和 ImageNet 的预处理对齐）
transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])

# 设备
device = "mps" if torch.backends.mps.is_available() else "cpu"
model = model.to(device)
criterion = nn.CrossEntropyLoss()

# 训练循环（和阶段 5 学的一样）
for epoch in range(5):
    model.train()
    for images, labels in train_loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        loss = criterion(outputs, labels)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
    print(f"Epoch {epoch+1} done")
```

---

## 3. NLP：Hugging Face 预训练模型

### 3.1 加载 BERT 做文本分类

```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification

model_name = "bert-base-uncased"

# 加载分词器和模型
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(
    model_name,
    num_labels=2,       # 你的分类数
)

# 查看模型结构
print(model)
# BertModel（12 层 Transformer）+ classifier（Linear 分类头）
```

### 3.2 推理（不训练，直接用）

```python
# 输入文本
text = "This movie is absolutely fantastic!"
inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True)

# 推理
model.eval()
with torch.no_grad():
    outputs = model(**inputs)
    logits = outputs.logits
    prediction = torch.argmax(logits, dim=-1)
    print(f"预测类别: {prediction.item()}")  # 0 或 1
```

### 3.3 用 Trainer 微调

```python
from transformers import Trainer, TrainingArguments
from datasets import load_dataset

# 加载数据
dataset = load_dataset("imdb")

# 分词
def tokenize_function(examples):
    return tokenizer(examples["text"], padding="max_length",
                     truncation=True, max_length=256)

tokenized_dataset = dataset.map(tokenize_function, batched=True)

# 训练参数
training_args = TrainingArguments(
    output_dir="./results",
    num_train_epochs=3,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    learning_rate=2e-5,           # 微调用小学习率
    weight_decay=0.01,
    eval_strategy="epoch",
    save_strategy="epoch",
    logging_steps=100,
)

# 创建 Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset["train"],
    eval_dataset=tokenized_dataset["test"],
)

# 训练！
trainer.train()
```

### Trainer vs 手写循环

```
手写训练循环（阶段 5）:
  优点：完全控制每一步，理解底层原理
  缺点：代码量大，容易出 bug

Trainer（Hugging Face）:
  优点：几行代码搞定，自带 logging/保存/分布式
  缺点：黑盒，出 bug 难调试

实际工作：用 Trainer / SFTTrainer
面试/理解原理：会手写训练循环
```

---

## 4. 加载生成式模型（LLM）

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "gpt2"  # 小模型，适合学习

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)

# 生成文本
input_text = "The future of AI is"
inputs = tokenizer(input_text, return_tensors="pt")

model.eval()
with torch.no_grad():
    outputs = model.generate(
        **inputs,
        max_new_tokens=50,
        temperature=0.7,
        top_p=0.9,
    )

print(tokenizer.decode(outputs[0]))
# "The future of AI is bright. We are seeing..."
```

### 和你 notebook 的直接关系

```python
# notebook 里的代码：
from unsloth import FastLanguageModel
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen3-14B",
    load_in_4bit=True,
)

# 等价的标准 Hugging Face 写法：
from transformers import AutoModelForCausalLM, AutoTokenizer
model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3-14B",
    torch_dtype=torch.float16,
    device_map="auto",
)
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-14B")

# Unsloth 版本更快更省内存，但底层做的事是一样的
```

---

## 5. LoRA：参数高效微调

```python
from peft import LoraConfig, get_peft_model

# 配置 LoRA
lora_config = LoraConfig(
    r=16,                    # rank（低秩矩阵的秩）
    lora_alpha=32,           # 缩放系数
    target_modules=["q_proj", "v_proj"],  # 在哪些层加 LoRA
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",   # 生成式语言模型
)

# 给模型加上 LoRA
model = get_peft_model(model, lora_config)

# 查看可训练参数
model.print_trainable_parameters()
# trainable params: 4,718,592 || all params: 124,443,648 || trainable%: 3.79%
```

### LoRA 做了什么？

```
原始模型：
  Linear(768, 768) → 768×768 = 589,824 个参数（冻结）

加了 LoRA 后：
  原始 Linear（冻结）
    +
  LoRA_A: Linear(768, 16)  → 768×16 = 12,288 个参数（可训练）
  LoRA_B: Linear(16, 768)  → 16×768 = 12,288 个参数（可训练）

总共只训练 24,576 个参数 vs 原来的 589,824
比例：4.2%

和你 notebook 里的完全一样，只是 Unsloth 用了优化过的实现
```

---

## 6. 完整的 LoRA 微调流程（概览）

> 完整可运行的代码在 **阶段 7 项目 3** 中，这里只列关键步骤：

```python
# 1. 加载基座模型
model = AutoModelForCausalLM.from_pretrained("gpt2")
tokenizer = AutoTokenizer.from_pretrained("gpt2")

# 2. 添加 LoRA adapter
model = get_peft_model(model, lora_config)

# 3. 准备数据（格式化 + 分词）
dataset = load_dataset("tatsu-lab/alpaca", split="train[:1000]")

# 4. 训练（手写循环 或 用 Trainer）
trainer = Trainer(model=model, args=training_args, train_dataset=dataset)
trainer.train()

# 5. 保存 adapter（只有几十 MB，不是整个模型）
model.save_pretrained("./gpt2-lora-adapter")

# 6. 加载使用
from peft import PeftModel
base_model = AutoModelForCausalLM.from_pretrained("gpt2")
model = PeftModel.from_pretrained(base_model, "./gpt2-lora-adapter")
```

> ⭐ 项目 3 会用**手写训练循环**实现完整流程，并对比训练前后的效果。

---

## 练习

```
1. 用 torchvision 加载 ResNet18，替换最后一层为 2 分类，跑通前向传播
2. 冻结全部参数只训练最后一层，在任意小数据集上训练 5 个 epoch
3. 用 Hugging Face 加载 BERT，对一句话做情感分类推理
4. 用 Hugging Face 加载 GPT-2，生成一段文本
5. 给 GPT-2 加 LoRA，打印可训练参数占比
6. （进阶）完成完整的 LoRA 微调流程，从加载到训练到保存
```

---

## 本阶段小结

```
学到了什么：
  ✅ 迁移学习的思路：加载 → 冻结 → 替换/微调
  ✅ CV 场景：torchvision 预训练模型
  ✅ NLP 场景：Hugging Face Transformers
  ✅ LoRA 的标准实现（peft 库）
  ✅ Trainer vs 手写训练循环的对比
  ✅ 完整的 LoRA 微调流程

和 notebook 的完整对应：
  FastLanguageModel.from_pretrained   → 阶段 6.4（加载预训练模型）
  FastLanguageModel.get_peft_model    → 阶段 6.5（添加 LoRA）
  SFTTrainer + trainer.train()        → 阶段 5 + 6.6（训练循环）
  model.save_pretrained               → 阶段 6.6（保存 adapter）

  你现在能完全理解微调 notebook 的每一行代码了。

下一阶段预告：
  用前面所有知识完成 3 个递进实战项目，
  从 MNIST 到文本分类到手写 fine-tune 流程。
```
