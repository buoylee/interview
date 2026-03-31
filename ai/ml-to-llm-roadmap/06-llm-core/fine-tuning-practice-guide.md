# QLoRA 微调实操指南

> **目标**：从零开始，动手完成一次模型微调，理解完整流程。

---

## 前置问题：为什么要微调？

### Prompt vs 微调 vs RAG 的区别

```
Prompt  = 告诉模型"这次怎么做" → 灵活但不稳定，每次都要写长 prompt
微调    = 教模型"以后都这么做" → 稳定可控，但需要数据和训练时间
RAG     = 给模型"一本参考书"   → 注入新知识，不改变模型本身
```

### 什么场景需要微调？

| 场景 | 例子 | 为什么不用 Prompt |
|------|------|-----------------|
| 固定输出风格 | 客服机器人用简短礼貌的格式回答 | prompt 做到 80% 稳定，微调做到 99% |
| 固定输出格式 | 每次都输出正确的 JSON | prompt 偶尔格式错，微调几乎不会错 |
| 专业领域对话 | 医疗问诊/法律咨询助手 | 需要持续稳定的专业风格 |
| 小模型替代大模型 | 用微调后的 7B 替代 GPT-4 API 省钱 | prompt 无法让小模型达到大模型水平 |

### 什么场景不需要微调？

```
需要新知识（公司内部文档、最新新闻） → 用 RAG
临时问一个问题                     → 直接 prompt
想试各种风格                       → 先试 system prompt
训练数据少于 50 条                  → 效果不好，先攒数据
```

### 微调能达到什么效果？

```
微调前（原始 7B 模型）：
  你："用 JSON 格式输出用户信息"
  模型：有时输出 JSON，有时输出自然语言，格式不稳定

微调后（同一个 7B 模型 + 500 条数据训练）：
  你："用 JSON 格式输出用户信息"
  模型：100% 稳定输出 {"name": "张三", "age": 25, ...}
```

> **一句话**：微调的核心价值 = 让模型的行为变得**稳定可控**。不是让它变聪明，而是让它听话。

---

## 整体流程概览

```
Step 1: 确定微调目标（你想让模型学会什么？）
Step 2: 准备训练数据（指令-回答对）
Step 3: 选择基座模型（Qwen / Llama）
Step 4: 配置环境（Colab 或本地）
Step 5: 运行训练（QLoRA 微调）
Step 6: 测试效果（和微调前对比）
Step 7: 导出模型（可选，本地跑）
```

---

## Step 1: 确定微调目标

微调不是万能的，先搞清楚你要做什么：

| 适合微调 | 不适合微调 |
|---------|-----------|
| 改变回答风格（更简洁/更专业） | 注入新知识（用 RAG 更合适） |
| 学会特定格式（JSON 输出等） | 临时问答（直接 prompt 就行） |
| 角色扮演（客服/教师/医生） | 数据太少（< 100 条效果差） |

**第一次练习建议**：做一个简单的任务，比如"让模型用文言文回答问题"或"让模型扮演一个特定角色"。

---

## Step 2: 准备训练数据

### 数据格式

每条数据是一个 JSON 对象，包含对话：

```jsonl
{"messages": [{"role": "system", "content": "你是一个用文言文回答问题的古代学者"}, {"role": "user", "content": "今天天气怎么样？"}, {"role": "assistant", "content": "今日天朗气清，惠风和畅，实乃出行之佳期也。"}]}
{"messages": [{"role": "system", "content": "你是一个用文言文回答问题的古代学者"}, {"role": "user", "content": "推荐一部电影"}, {"role": "assistant", "content": "余闻有《肖申克之救赎》者，讲述囚徒困于牢笼而志不屈，终得自由。此片寓意深远，观之令人振奋，诚为佳作。"}]}
```

### 数据量建议

```
第一次练习：50-200 条（够了，先跑通流程）
正式微调：500-2000 条（效果更好）
```

### 数据怎么来？

```
方法 1（练习1推荐）：直接用现成数据集，不用自己准备 ← 最快上手
方法 2：用 GPT/Claude 帮你生成      ← 练习2可以试
方法 3：自己手写                     ← 最可控，适合特定领域
```

#### 现成数据集推荐（一行代码加载）

```python
from datasets import load_dataset

# 中文指令数据（推荐第一次用）
dataset = load_dataset("silk-road/alpaca-data-gpt4-chinese")

# 英文指令数据
dataset = load_dataset("tatsu-lab/alpaca")

# Unsloth 官方 Notebook 里也自带示例数据集，打开就能直接跑
```

> 💡 **练习 1 不需要自己准备数据**，用现成的或 Unsloth 自带的就行。

创建一个 `data/` 目录，放入：

```
data/
  ├── train.jsonl   ← 训练数据（80%）
  ├── valid.jsonl   ← 验证数据（10%）
  └── test.jsonl    ← 测试数据（10%）
```

---

## Step 3: 选择基座模型

| 模型 | 大小 | 适用环境 | 推荐度 |
|------|------|---------|-------|
| Qwen2.5-7B-Instruct | 7B | Colab T4 (QLoRA) | ⭐⭐⭐ 推荐 |
| Llama-3.1-8B-Instruct | 8B | Colab T4 (QLoRA) | ⭐⭐⭐ |
| Qwen2.5-1.5B-Instruct | 1.5B | MacBook 本地 (MLX) | ⭐⭐ |
| SmolLM2-1.7B | 1.7B | MacBook 本地 (MLX) | ⭐⭐ |

**第一次建议**：Colab + Qwen2.5-7B-Instruct，中文效果最好。

---

## Step 4 & 5: 实际训练

### 方案 A: Google Colab + Unsloth（⭐ 推荐新手）

#### 4A. 环境准备

```
1. 打开 https://colab.research.google.com
2. 登录 Google 账号
3. 菜单 Runtime → Change runtime type → 选 T4 GPU → Save
```

#### 5A. 使用 Unsloth 官方 Notebook

```
1. 打开 https://github.com/unslothai/unsloth
2. 找到 README 里的 "Notebooks" 部分
3. 点击对应模型的 "Open in Colab" 按钮（选 Qwen2.5 或 Llama 3.1）
4. 按顺序运行每个 cell
```

或者手动写（核心代码，约 30 行）：

```python
# Cell 1: 安装
!pip install unsloth
!pip install --no-deps trl peft accelerate bitsandbytes

# Cell 2: 加载模型（4-bit 量化 = QLoRA）
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit",  # 4bit 量化版
    max_seq_length = 2048,
    load_in_4bit = True,
)

# Cell 3: 添加 LoRA adapter
model = FastLanguageModel.get_peft_model(
    model,
    r = 16,                # LoRA rank（16 是个好的起点）
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj"],
    lora_alpha = 16,
    lora_dropout = 0,
    use_gradient_checkpointing = "unsloth",
)

# Cell 4: 准备数据
# 把你的 jsonl 数据上传到 Colab，或者用 datasets 库加载
from datasets import load_dataset
dataset = load_dataset("json", data_files="train.jsonl", split="train")

# Cell 5: 配置训练
from trl import SFTTrainer
from transformers import TrainingArguments

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    args = TrainingArguments(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        warmup_steps = 5,
        max_steps = 100,          # 先跑 100 步试试，正式训练改大
        learning_rate = 2e-4,
        output_dir = "outputs",
        logging_steps = 10,       # 每 10 步打印一次 loss
    ),
)

# Cell 6: 开始训练！
trainer.train()

# Cell 7: 测试效果
FastLanguageModel.for_inference(model)
inputs = tokenizer("今天天气怎么样？", return_tensors="pt").to("cuda")
outputs = model.generate(**inputs, max_new_tokens=128)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))

# Cell 8: 保存 adapter（可选）
model.save_pretrained("my-lora-adapter")
tokenizer.save_pretrained("my-lora-adapter")
```

#### 训练过程中你会看到

```
Step 10/100: loss = 2.34   ← 损失在降，模型在学
Step 20/100: loss = 1.87
Step 50/100: loss = 1.12
Step 100/100: loss = 0.68  ← 损失越来越小 = 模型越来越好
```

---

### 方案 B: 本地 MacBook M4 + MLX

#### 4B. 环境准备

```bash
# 安装 MLX
pip install mlx-lm

# 创建数据目录
mkdir -p data
```

#### 5B. 准备数据

```bash
# data/train.jsonl（每行一个 JSON）
{"messages": [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "汝好，吾乃古之学者，有何赐教？"}]}
```

#### 5B. 运行训练

```bash
# 微调（用 4-bit 量化的 1.5B 模型）
python -m mlx_lm.lora \
  --model mlx-community/Qwen2.5-1.5B-Instruct-4bit \
  --data ./data \
  --train \
  --batch-size 2 \
  --num-layers 16 \
  --learning-rate 1e-4 \
  --iters 200

# 大约 10-20 分钟完成
```

#### 5B. 测试效果

```bash
# 用 adapter 跑推理
python -m mlx_lm.generate \
  --model mlx-community/Qwen2.5-1.5B-Instruct-4bit \
  --adapter-path adapters \
  --prompt "今天天气怎么样？"
```

#### 5B. 合并模型（可选）

```bash
# 把 adapter 合并进基座模型，变成一个完整模型
python -m mlx_lm.fuse \
  --model mlx-community/Qwen2.5-1.5B-Instruct-4bit \
  --adapter-path adapters \
  --save-path my-finetuned-model
```

---

## Step 6: 测试效果

微调完成后，对比微调前后的效果：

```
测试问题："推荐一本书"

微调前（原始模型）的回答：
  "我推荐《百年孤独》，这是一本拉美文学经典..."

微调后（文言文风格）的回答：
  "余荐《百年孤独》一书，此书乃拉美文学之瑰宝..."

如果风格变了 → 微调成功！
如果没变化 → 检查数据质量或增加训练步数
```

---

## Step 7: 导出模型（可选）

如果想在本地用 Ollama 运行微调后的模型：

```bash
# 在 Colab 里导出为 GGUF 格式（Unsloth 支持）
model.save_pretrained_gguf("my-model", tokenizer, quantization_method="q4_k_m")

# 下载到本地后，用 Ollama 运行
ollama create my-model -f Modelfile
ollama run my-model
```

---

## 常见问题

| 问题 | 解决方法 |
|------|---------|
| Colab 报 OOM (内存不足) | 减小 batch_size 或 max_seq_length |
| Loss 不下降 | 检查数据格式是否正确 |
| 效果不明显 | 增加数据量或训练步数 |
| 本地 MLX 太慢 | 用更小的模型（1.5B）或减少 iters |

---

## 关键参数速查

| 参数 | 含义 | 推荐值 |
|------|------|--------|
| r (rank) | LoRA 秩，越大表达力越强 | 16（入门用这个） |
| learning_rate | 学习率，太大不稳定太小学不动 | 2e-4 |
| max_steps | 训练多少步 | 100（试跑）/ 500+（正式） |
| batch_size | 每次喂多少条数据 | 2（显存小就用 1） |
| lora_alpha | 缩放系数，通常等于 r | 16 |

---

> 📌 **第一次实操目标**：跑通流程 > 效果好坏。先确保从头到尾能跑完，再去优化数据和参数。
