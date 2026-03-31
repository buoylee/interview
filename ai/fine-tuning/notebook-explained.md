# Qwen3-14B 推理+对话微调 Notebook 逐行解读

> 本文档是对 `Qwen3_(14B)_Reasoning_Conversational.ipynb` 的完整解读。
> 每一行代码都有中文注释，适合初学者理解整个微调流程。

---

## 全局概览

```
这个 notebook 做了什么？
  用 QLoRA 方法微调 Qwen3-14B 模型，让它同时具备：
  1. 数学推理能力（能解数学题并展示思考过程）
  2. 日常对话能力（能正常聊天）

整体流程：
  安装库 → 加载模型 → 添加 LoRA → 准备数据 → 训练 → 测试 → 保存
```

---

## 阶段 1：安装依赖库

```python
%%capture
# %%capture = 隐藏安装过程的输出（不想看一堆安装日志）

import os, re
# os: 操作系统相关功能（这里用来读环境变量）
# re: 正则表达式（这里用来提取 PyTorch 版本号）

if "COLAB_" not in "".join(os.environ.keys()):
    # 检查是不是在 Google Colab 环境
    # 如果不是 Colab（比如在本地），用这种方式安装
    !pip install unsloth
else:
    # 如果是 Colab 环境，用优化过的安装方式
    import torch
    v = re.match(r'[\d]{1,}\.[\d]{1,}', str(torch.__version__)).group(0)
    # 提取 PyTorch 版本号，比如 "2.10" 或 "2.9"

    xformers = 'xformers==' + {
        '2.10': '0.0.34',
        '2.9': '0.0.33.post1',
        '2.8': '0.0.32.post2'
    }.get(v, "0.0.34")
    # 根据 PyTorch 版本选择对应的 xformers 版本
    # xformers = 一个加速 Attention 计算的库

    !pip install sentencepiece protobuf "datasets==4.3.0" "huggingface_hub>=0.34.0" hf_transfer
    # sentencepiece: 分词器（把文字切成 token）
    # protobuf: 数据序列化格式
    # datasets: Hugging Face 的数据集加载库
    # huggingface_hub: 从 Hugging Face 下载模型
    # hf_transfer: 加速下载

    !pip install --no-deps unsloth_zoo bitsandbytes accelerate {xformers} peft trl triton unsloth
    # --no-deps: 不安装这些库的依赖（避免版本冲突）
    # unsloth_zoo: Unsloth 的核心组件
    # bitsandbytes: ⭐ 做 4-bit/8-bit 量化的库（QLoRA 的关键）
    # accelerate: Hugging Face 的训练加速库
    # peft: ⭐ Parameter-Efficient Fine-Tuning，LoRA 的实现库
    # trl: ⭐ Transformer Reinforcement Learning，提供 SFTTrainer
    # triton: GPU 编程库（加速计算）
    # unsloth: 核心库，加速训练

!pip install transformers==4.56.2
# transformers: ⭐ Hugging Face 最核心的库，加载和使用各种模型
# 锁定版本号确保兼容性

!pip install --no-deps trl==0.22.2
# 锁定 trl 版本，确保 SFTTrainer 能正常工作
```

### 这些库的关系图

```
transformers ← 加载模型（Qwen3、Llama 等）
     ↓
peft ← 在模型上添加 LoRA adapter
     ↓
bitsandbytes ← 对模型做 4-bit 量化（Q in QLoRA）
     ↓
trl (SFTTrainer) ← 封装训练循环（不用自己写训练代码）
     ↓
unsloth ← 加速以上所有操作（2倍速度，70%内存节省）
```

---

## 阶段 2：加载模型

```python
from unsloth import FastLanguageModel
# FastLanguageModel: Unsloth 提供的加速版模型加载器
# 比直接用 transformers 加载更快、更省内存

import torch
# PyTorch: 深度学习框架，所有计算都在它上面跑

fourbit_models = [
    "unsloth/Qwen3-1.7B-unsloth-bnb-4bit",
    "unsloth/Qwen3-4B-unsloth-bnb-4bit",
    "unsloth/Qwen3-8B-unsloth-bnb-4bit",
    "unsloth/Qwen3-14B-unsloth-bnb-4bit",
    "unsloth/Qwen3-32B-unsloth-bnb-4bit",
    "unsloth/gemma-3-12b-it-unsloth-bnb-4bit",
    "unsloth/Phi-4",
    "unsloth/Llama-3.1-8B",
    "unsloth/Llama-3.2-3B",
    "unsloth/orpheus-3b-0.1-ft-unsloth-bnb-4bit",
]
# 这只是一个可选模型列表，展示 Unsloth 支持哪些模型
# 你可以把下面 model_name 换成列表里的任何一个

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/Qwen3-14B",
    # ⭐ 选择 Qwen3-14B 作为基座模型
    # "unsloth/" 前缀表示用 Unsloth 优化过的版本

    max_seq_length = 2048,
    # 最大序列长度 = 一次能处理多少个 token
    # 2048 ≈ 约 1500-2000 个中文字
    # 越大越耗内存，按需设置

    load_in_4bit = True,
    # ⭐⭐⭐ QLoRA 的 "Q" 就在这里！
    # True = 把模型权重从 FP16（每个参数 2 字节）压缩到 4-bit（0.5 字节）
    # 14B 参数：FP16 需要 ~28GB，4-bit 只需要 ~8GB
    # 这就是为什么 T4（16GB）能装得下 14B 模型

    load_in_8bit = False,
    # 8-bit 量化：比 4-bit 更准确，但用 2 倍内存
    # 这里关闭，用 4-bit 就够了

    full_finetuning = False,
    # False = 用 LoRA（只训练一小部分参数）
    # True = 全参数微调（需要巨大显存）

    # token = "YOUR_HF_TOKEN",
    # 如果模型需要授权（如 Llama 需要同意协议），填你的 HF token
    # Qwen3 不需要，所以注释掉了
)
```

### 返回值解释

```
model = 加载好的模型对象
  - 这时候模型的权重已经是 4-bit 量化的了
  - 模型被冻结（frozen），不能直接训练
  - 需要下一步添加 LoRA adapter 才能训练

tokenizer = 分词器
  - 把文字转成数字（token IDs）：  "你好" → [23421, 8823]
  - 把数字转回文字：              [23421, 8823] → "你好"
  - 每个模型有自己的分词器，不能混用
```

---

## 阶段 3：添加 LoRA Adapter

```python
model = FastLanguageModel.get_peft_model(
    model,
    # 传入上一步加载的（已冻结的）模型

    r = 32,
    # ⭐ LoRA rank（秩）
    # 你在线性代数里学过：LoRA 用两个小矩阵 A(d×r) 和 B(r×d) 近似权重变化
    # r 越大 → 表达力越强，但参数越多
    # 常用值：8, 16, 32, 64
    # 这里用 32，是个不错的平衡点

    target_modules = [
        "q_proj",     # Query 投影（Attention 中的 Q）
        "k_proj",     # Key 投影（Attention 中的 K）
        "v_proj",     # Value 投影（Attention 中的 V）
        "o_proj",     # Output 投影（Attention 输出）
        "gate_proj",  # FFN 门控层
        "up_proj",    # FFN 上投影层
        "down_proj",  # FFN 下投影层
    ],
    # ⭐ 在哪些层添加 LoRA
    # 前 4 个是 Attention（注意力）层 → Transformer 的核心
    # 后 3 个是 FFN（前馈网络）层
    # 几乎覆盖了 Transformer block 的所有可训练部分

    lora_alpha = 32,
    # 缩放系数，控制 LoRA 的影响力度
    # 通常设为和 r 相同，或 r 的 2 倍
    # 实际缩放 = lora_alpha / r = 32/32 = 1

    lora_dropout = 0,
    # Dropout 比率（随机丢弃部分连接防止过拟合）
    # 0 = 不丢弃（Unsloth 对 0 做了优化，更快）

    bias = "none",
    # 是否训练 bias 参数
    # "none" = 不训练（更快，通常够用）

    use_gradient_checkpointing = "unsloth",
    # ⭐ 梯度检查点：用时间换显存
    # 正常训练需要保存所有中间结果来算梯度 → 很耗显存
    # 开启后只保存部分，需要时重新计算 → 省显存但稍慢
    # "unsloth" 是 Unsloth 优化过的版本，省 30% 显存

    random_state = 3407,
    # 随机种子：确保每次运行结果可复现
    # 3407 是 Unsloth 作者的幸运数字（没有特殊含义）

    use_rslora = False,
    # rsLoRA = Rank Stabilized LoRA
    # 一种改进版 LoRA，大 rank 时更稳定
    # 这里不用

    loftq_config = None,
    # LoftQ = 另一种初始化方法
    # 这里不用
)
```

### LoRA 参数量计算

```
以 Qwen3-14B 为例，每个目标层：
  原始权重 W: (d × d)，比如 5120 × 5120 = 26.2M 参数（冻结）
  LoRA A:    (d × r) = 5120 × 32 = 163,840 参数（可训练）
  LoRA B:    (r × d) = 32 × 5120 = 163,840 参数（可训练）
  
  每层 LoRA: 约 328K 参数 vs 原始 26.2M（约 1.2%）

所有目标层加起来：
  128,450,560 可训练参数 / 14,896,757,760 总参数 = 0.86%
  ← 你在训练输出里看到的那个数字！
```

---

## 阶段 4：数据准备

### 4.1 加载数据集

```python
from datasets import load_dataset
# Hugging Face 的数据集加载库，一行代码从网上下载数据

reasoning_dataset = load_dataset(
    "unsloth/OpenMathReasoning-mini",
    split = "cot"
)
# ⭐ 数据集 1：数学推理数据
# 来源：NVIDIA 的 OpenMathReasoning 数据集（精简版）
# "cot" = Chain of Thought（思维链），包含详细解题步骤
# 每条数据 = { "problem": "数学题", "generated_solution": "详细解题过程" }
# 示例：
#   problem: "Solve (x + 2)^2 = 0"
#   solution: "Let me think step by step... (x+2)^2 = 0 means x+2 = 0, so x = -2"

non_reasoning_dataset = load_dataset(
    "mlabonne/FineTome-100k",
    split = "train"
)
# ⭐ 数据集 2：通用对话数据
# 来自 Maxime Labonne 整理的 10 万条高质量对话
# ShareGPT 格式 = 真实用户和 AI 的对话记录
# 涵盖各种话题：编程、写作、科学、日常问答等
```

### 4.2 转换数据格式

```python
def generate_conversation(examples):
    # 这个函数把数学推理数据转成对话格式

    problems  = examples["problem"]
    # 取出所有数学题

    solutions = examples["generated_solution"]
    # 取出所有解答

    conversations = []
    for problem, solution in zip(problems, solutions):
        # 一一配对

        conversations.append([
            {"role" : "user",      "content" : problem},
            # 用户提出数学题

            {"role" : "assistant", "content" : solution},
            # 助手给出解答（带思考过程）
        ])
    return { "conversations": conversations, }
    # 返回标准对话格式
```

```
为什么要转格式？

  原始格式：{ "problem": "...", "generated_solution": "..." }
                ↓ 转换
  对话格式：[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

  因为模型训练需要统一的对话格式（和 ChatGPT 一样的 messages 格式）
```

```python
reasoning_conversations = tokenizer.apply_chat_template(
    list(reasoning_dataset.map(generate_conversation, batched=True)["conversations"]),
    tokenize = False,
    # tokenize=False → 不转成数字，保持文字形式
)
# ⭐ apply_chat_template = 把对话套进模型专用的模板

# Qwen3 的模板长这样：
# <|im_start|>user
# Solve (x + 2)^2 = 0.<|im_end|>
# <|im_start|>assistant
# Let me think...<|im_end|>
#
# 不同模型模板不同，这就是为什么要用 tokenizer 自带的模板
```

### 4.3 处理通用对话数据

```python
from unsloth.chat_templates import standardize_sharegpt
# standardize_sharegpt = 统一 ShareGPT 数据的格式
# ShareGPT 数据格式不太标准，需要清洗

dataset = standardize_sharegpt(non_reasoning_dataset)
# 标准化：统一角色名（"human"→"user"），删除异常数据等

non_reasoning_conversations = tokenizer.apply_chat_template(
    list(dataset["conversations"]),
    tokenize = False,
)
# 同样套上 Qwen3 的对话模板
```

### 4.4 混合两个数据集

```python
chat_percentage = 0.25
# ⭐ 混合比例：25% 通用对话 + 75% 数学推理

# 为什么不是 50/50？
# 因为这个 notebook 的目标是让模型擅长推理
# 但又不想让它完全失去聊天能力
# 75/25 是一个经验值
```

```python
import pandas as pd
non_reasoning_subset = pd.Series(non_reasoning_conversations)
non_reasoning_subset = non_reasoning_subset.sample(
    int(len(reasoning_conversations) * (chat_percentage / (1 - chat_percentage))),
    # 计算需要多少条对话数据
    # 如果推理数据有 10000 条，chat_percentage=0.25
    # 那对话数据 = 10000 × (0.25/0.75) ≈ 3333 条
    # 合起来：10000 推理 + 3333 对话 ≈ 75% : 25%

    random_state = 2407,
    # 随机种子（确保每次采样结果一样）
)
```

```python
data = pd.concat([
    pd.Series(reasoning_conversations),
    pd.Series(non_reasoning_subset)
])
# 把两个数据集合并成一个

data.name = "text"
# 列名设为 "text"，SFTTrainer 会用这个列名

from datasets import Dataset
combined_dataset = Dataset.from_pandas(pd.DataFrame(data))
# 转成 Hugging Face Dataset 格式（SFTTrainer 需要这个格式）

combined_dataset = combined_dataset.shuffle(seed=3407)
# ⭐ 打乱顺序！
# 不打乱的话模型先看完所有推理数据再看对话数据
# 打乱后推理和对话数据交替出现，训练更稳定
```

---

## 阶段 5：训练

```python
from trl import SFTTrainer, SFTConfig
# SFTTrainer = Supervised Fine-Tuning Trainer（有监督微调训练器）
# 封装了整个训练循环，不用自己手写训练代码

trainer = SFTTrainer(
    model = model,
    # 传入添加了 LoRA adapter 的模型

    tokenizer = tokenizer,
    # 传入分词器

    train_dataset = combined_dataset,
    # 传入混合好的训练数据

    eval_dataset = None,
    # 验证集 = None（这个 demo 不做验证）
    # 正式训练应该设置验证集来监控过拟合

    args = SFTConfig(
        dataset_text_field = "text",
        # 告诉 trainer 数据在 "text" 这一列

        per_device_train_batch_size = 2,
        # ⭐ 每次从数据集取 2 条喂给 GPU
        # 为什么不取更多？因为显存有限
        # 越大越好（训练更稳定），但受显存限制

        gradient_accumulation_steps = 4,
        # ⭐ 梯度累积 4 步
        # 意思是：算 4 次梯度，累加起来，再更新一次权重
        # 等效 batch_size = 2 × 4 = 8
        # 为什么这么做？
        #   想要 batch_size=8 的效果，但显存只够放 2 条数据
        #   所以分 4 次算，效果近似

        warmup_steps = 5,
        # ⭐ 学习率预热：前 5 步从 0 慢慢升到设定的学习率
        # 为什么？刚开始模型参数是随机的（LoRA 部分）
        # 一上来就用大学习率容易训练不稳定
        # 慢慢热身更安全

        # num_train_epochs = 1,
        # epoch = 把所有数据看一遍
        # 注释掉了，改用 max_steps 控制

        max_steps = 30,
        # ⭐ 只训练 30 步（演示用）
        # 正式训练应该设几百到上千步
        # 或者用 num_train_epochs = 1-3（看完数据 1-3 遍）

        learning_rate = 2e-4,
        # ⭐ 学习率 = 0.0002
        # 控制每次更新权重的幅度
        # 太大（如 0.01）→ 训练不稳定，loss 跳来跳去
        # 太小（如 0.00001）→ 学得太慢
        # 2e-4 是 LoRA 微调的常用值
        # 如果训练很长（几千步），建议降到 2e-5

        logging_steps = 1,
        # 每 1 步打印一次 loss
        # 你看到的 "Step 1: loss=0.5538" 就是这个控制的

        optim = "adamw_8bit",
        # ⭐ 优化器 = AdamW（8-bit 版本）
        # AdamW 是最常用的优化器，比普通 SGD 更智能
        # 8-bit 版本更省内存（优化器也要占显存！）
        # 优化器的工作：根据梯度决定每个参数调整多少

        weight_decay = 0.001,
        # 权重衰减 = 一种正则化方法
        # 每次更新时让权重稍微缩小一点
        # 防止权重过大导致过拟合
        # 0.001 是很小的约束

        lr_scheduler_type = "linear",
        # 学习率调度器 = 线性衰减
        # 训练过程中学习率从 2e-4 线性降到 0
        # 为什么？前期大步走（学得快），后期小步走（精调）

        seed = 3407,
        # 随机种子

        report_to = "none",
        # 不上报训练日志到 WandB 等平台
        # 正式训练可以改成 "wandb" 来可视化训练过程

        padding_free = False,
        # 是否开启无填充训练（更省显存）
        # 需要 > 17GB 显存才建议开
    ),
)
```

### 显示当前显存使用

```python
gpu_stats = torch.cuda.get_device_properties(0)
# 获取 GPU 信息

start_gpu_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
# 当前已经占用了多少 GB 显存

max_memory = round(gpu_stats.total_memory / 1024 / 1024 / 1024, 3)
# GPU 总共有多少 GB 显存

print(f"GPU = {gpu_stats.name}. Max memory = {max_memory} GB.")
print(f"{start_gpu_memory} GB of memory reserved.")
# 输出类似：GPU = Tesla T4. Max memory = 15.843 GB.
#           8.5 GB of memory reserved.
```

### 开始训练！

```python
trainer_stats = trainer.train()
# ⭐⭐⭐ 这一行代码包含了所有你学过的数学：
#
# 每一步做了什么：
# 1. 取一批数据（batch_size=2）
# 2. 数据经过 tokenizer 变成数字
# 3. 数字经过模型前向传播，得到每个位置的预测
# 4. 用交叉熵计算 loss（预测和真实答案差多远）← 信息论
# 5. 反向传播计算梯度（链式法则，从后往前）    ← 微积分
# 6. 优化器根据梯度更新 LoRA 的参数            ← 梯度下降
# 7. 重复以上步骤 30 次（max_steps=30）
#
# 你会看到：
# Step 1/30: loss = 0.553
# Step 2/30: loss = 0.539   ← loss 在下降，模型在学习
# ...
# Step 30/30: loss = 0.392
```

### 训练统计

```python
used_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
# 训练后峰值显存

used_memory_for_lora = round(used_memory - start_gpu_memory, 3)
# 训练本身用了多少显存

print(f"{trainer_stats.metrics['train_runtime']} seconds used for training.")
# 训练用了多少秒

print(f"Peak reserved memory = {used_memory} GB.")
# 峰值显存使用
# T4 上大概 14-15 GB（快撑满了）

print(f"Peak reserved memory for training = {used_memory_for_lora} GB.")
# 纯训练用了多少显存（不算模型本身）
```

---

## 阶段 6：推理测试

### 6.1 不思考模式（直接回答）

```python
messages = [
    {"role" : "user", "content" : "Solve (x + 2)^2 = 0."}
]
# 构造一个用户消息

text = tokenizer.apply_chat_template(
    messages,
    tokenize = False,
    # 不转数字，保持文字

    add_generation_prompt = True,
    # ⭐ 在末尾添加 assistant 的开头标记
    # 告诉模型"该你回答了"

    enable_thinking = False,
    # ⭐ 关闭思考模式
    # Qwen3 的特色：可以选择是否展示思考过程
    # False = 直接给答案，快但可能不够准
)

from transformers import TextStreamer
# TextStreamer = 实时流式输出（一个字一个字蹦出来）

_ = model.generate(
    **tokenizer(text, return_tensors="pt").to("cuda"),
    # tokenizer(text) = 把文字转成数字
    # return_tensors="pt" = 返回 PyTorch 张量
    # .to("cuda") = 放到 GPU 上计算

    max_new_tokens = 256,
    # 最多生成 256 个 token

    temperature = 0.7,
    # ⭐ 温度 = 控制随机性
    # 0 = 完全确定（总是选概率最高的词）
    # 1 = 很随机（可能选概率低的词）
    # 0.7 = 略有随机性，比较自然

    top_p = 0.8,
    # ⭐ Nucleus Sampling
    # 只从累积概率前 80% 的词里选
    # 过滤掉概率极低的词

    top_k = 20,
    # ⭐ 只从概率最高的前 20 个词里选
    # 和 top_p 一起使用，双重过滤

    streamer = TextStreamer(tokenizer, skip_prompt=True),
    # 流式输出，跳过输入（只显示模型的回答）
)
```

### 6.2 思考模式（展示推理过程）

```python
# 和上面几乎一样，只有两个参数不同：

enable_thinking = True,
# ⭐ 开启思考模式
# 模型会先在 <think>...</think> 标签里展示思考过程
# 然后再给出最终答案
# 类似 OpenAI 的 o1 模型

max_new_tokens = 1024,
# 思考模式输出更长，所以给更多空间

temperature = 0.6,
# 推理时温度略低，更"认真"

top_p = 0.95,
# 采样范围更宽（推理需要更多可能性）
```

```
输出示例（思考模式）：

<think>
The equation is (x + 2)^2 = 0.
For a square to equal zero, the thing being squared must be zero.
So x + 2 = 0, which gives x = -2.
Let me verify: (-2 + 2)^2 = 0^2 = 0. ✓
</think>

The solution is x = -2.
```

---

## 阶段 7：保存模型

### 7.1 保存 LoRA adapter

```python
model.save_pretrained("qwen_lora")
# 保存 LoRA adapter 到本地目录 "qwen_lora/"
# ⭐ 只保存了 LoRA 的参数（几十 MB），不是整个模型（几十 GB）
# 使用时需要：加载原始 Qwen3-14B + 加载这个 adapter

tokenizer.save_pretrained("qwen_lora")
# 保存 tokenizer 配置

# model.push_to_hub("your_name/qwen_lora", token="YOUR_HF_TOKEN")
# 上传到 Hugging Face Hub（注释掉了，需要的话手动开启）
```

### 7.2 加载已保存的 adapter

```python
if False:  # 改成 True 才会执行
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name = "qwen_lora",
        # 从本地目录加载，它会自动找到原始模型 + adapter

        max_seq_length = 2048,
        load_in_4bit = True,
    )
# 这段代码展示如何重新加载微调后的模型
```

### 7.3 导出为其他格式

```python
# 导出为 FP16（完整精度，文件大但最准确）
if False:
    model.save_pretrained_merged(
        "qwen_finetune_16bit",
        tokenizer,
        save_method = "merged_16bit",
        # ⭐ "merged" = 把 LoRA adapter 合并进原始模型
        # 合并后就是一个完整的模型，不需要单独加载 adapter
    )

# 导出为 GGUF（本地 llama.cpp / Ollama 格式）
if False:
    model.save_pretrained_gguf(
        "qwen_finetune",
        tokenizer,
        quantization_method = "q4_k_m"
        # ⭐ GGUF 量化方法：
        # "q8_0" = 8-bit 量化，质量高，文件大
        # "q4_k_m" = 4-bit 混合量化，质量和大小平衡（推荐）
        # "q5_k_m" = 5-bit 混合量化
    )
    # 导出后的 .gguf 文件可以直接用 Ollama 运行：
    # ollama create my-model -f Modelfile
    # ollama run my-model
```

---

## 训练输出解读

你跑出来的结果：

```
Trainable parameters = 128,450,560 of 14,896,757,760 (0.86% trained)
│                      │                              │
│                      │                              └── 只训练了不到 1%
│                      └── 模型总共有 148 亿参数
└── 其中只有 1.28 亿是可训练的（LoRA）

Total batch size (2 x 4 x 1) = 8
│                 │   │   │
│                 │   │   └── 1 块 GPU
│                 │   └── 梯度累积 4 步
│                 └── 每次喂 2 条数据
└── 等效每次看 8 条数据

Step  Loss     解读
1     0.5538   起点，模型初始预测能力
2     0.5392   ↓ 开始学习
3     0.5153   ↓ 继续改善
4     0.6812   ↑ 偶尔波动（正常，可能遇到较难的数据）
...
8     0.3944   ↓ 明显改善
11    0.3847   ↓ 趋于稳定
16    0.4253   ↑ 小幅波动

整体趋势：从 ~0.55 降到 ~0.40，模型在学习 ✅
```

---

## 完整流程回顾：这个 notebook 对应了哪些数学概念

| Notebook 步骤 | 对应的数学/ML 概念 | 你在哪里学的 |
|---|---|---|
| `load_in_4bit=True` | 量化（数值精度压缩） | 06-llm-core |
| `r=32, target_modules=[...]` | LoRA 低秩分解 | 01-线性代数（SVD） |
| `apply_chat_template` | Tokenization | 03-NLP |
| `SFTTrainer` + `trainer.train()` | 梯度下降 + 反向传播 | 03-微积分 |
| `loss = 0.5538` | 交叉熵损失 | 04-信息论 |
| `learning_rate = 2e-4` | 学习率（梯度下降步长） | 03-微积分 |
| `gradient_accumulation_steps = 4` | 批量训练优化 | 01-ML 基础 |
| `temperature = 0.7` | Softmax 温度缩放 | 02-概率论 |
| `top_p, top_k` | 采样策略 | 05-预训练模型 |
