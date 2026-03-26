# 7.6 模型微调实操指南

> **一句话定位**：从零跑通一次 LoRA 微调的完整实操手册——工具选择、数据准备、超参数、显存估算、训练监控、常见坑。理论部分见 [06/06-fine-tuning-distillation.md](../06-llm-core/06-fine-tuning-distillation.md)。

---

## 1. 工具链选择 ⭐

```
                 上手难度   灵活性   速度    适合场景
Unsloth           ★☆☆☆☆    中等    2x快    快速实验、个人项目 ⭐ 推荐入门
LLaMA-Factory     ★★☆☆☆    高      快      中文场景、多种方法切换
Axolotl           ★★★☆☆    高      快      YAML 配置驱动、团队协作
HF PEFT + TRL     ★★★★☆    最高    基准    深度定制、理解底层
torchtune         ★★★☆☆    高      快      PyTorch 原生方案
```

### 推荐路线

```
第一次微调 → Unsloth（10 行代码跑通）
需要更多控制 → LLaMA-Factory（Web UI + CLI）
生产级需求 → HF PEFT + TRL（完全可控）
```

### 各工具核心代码对比

**Unsloth（最简）：**
```python
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen2.5-7B",
    max_seq_length=2048,
    load_in_4bit=True,          # QLoRA
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16,                        # LoRA rank
    lora_alpha=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
)

# 用 HF Trainer 正常训练即可
```

**LLaMA-Factory（YAML 配置）：**
```yaml
# examples/train_lora/qwen2_lora_sft.yaml
model_name_or_path: Qwen/Qwen2.5-7B
stage: sft
finetuning_type: lora
lora_rank: 16
lora_alpha: 16
lora_target: all
dataset: my_dataset
template: qwen
output_dir: outputs/qwen2-lora
per_device_train_batch_size: 4
gradient_accumulation_steps: 4
num_train_epochs: 3
learning_rate: 2e-4
bf16: true
```

**HF PEFT + TRL（完全控制）：**
```python
from peft import LoraConfig
from trl import SFTTrainer

peft_config = LoraConfig(
    r=16, lora_alpha=16, lora_dropout=0.05,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    task_type="CAUSAL_LM",
)

trainer = SFTTrainer(
    model=model,
    train_dataset=dataset,
    peft_config=peft_config,
    args=training_args,
)
trainer.train()
```

## 2. Chat Template（对话模板）⭐⭐ 最容易踩的坑

```
不同模型有不同的对话格式，用错模板 = 白训！

模型不知道"哪部分是指令，哪部分是回答"
→ 学到错误的模式 → loss 下降但输出垃圾
```

### 常见模板格式

**ChatML（Qwen、Yi 等）：**
```
<|im_start|>system
你是一个有用的助手。<|im_end|>
<|im_start|>user
今天天气怎么样？<|im_end|>
<|im_start|>assistant
今天天气晴朗，气温 25 度。<|im_end|>
```

**LLaMA 3 格式：**
```
<|begin_of_text|><|start_header_id|>system<|end_header_id|>

你是一个有用的助手。<|eot_id|><|start_header_id|>user<|end_header_id|>

今天天气怎么样？<|eot_id|><|start_header_id|>assistant<|end_header_id|>

今天天气晴朗，气温 25 度。<|eot_id|>
```

**Mistral/Mixtral 格式：**
```
[INST] 今天天气怎么样？ [/INST] 今天天气晴朗，气温 25 度。</s>
```

### 怎么确保模板正确？

```python
# 方法 1：用 tokenizer 内置的 apply_chat_template
messages = [
    {"role": "system", "content": "你是一个有用的助手。"},
    {"role": "user", "content": "今天天气怎么样？"},
    {"role": "assistant", "content": "今天天气晴朗。"},
]
text = tokenizer.apply_chat_template(messages, tokenize=False)
print(text)  # 检查格式是否正确！

# 方法 2：用 LLaMA-Factory / Unsloth 自带的 template 参数
# 只需指定 template: qwen / llama3 / mistral 即可
```

**黄金法则：微调前，先打印 3-5 条格式化后的训练数据，肉眼检查格式是否正确。**

## 3. 数据准备 ⭐⭐

### 3.1 数据格式

```
标准格式（Alpaca style）：
[
  {
    "instruction": "将以下句子翻译成英文",
    "input": "今天是个好天气",
    "output": "Today is a nice day"
  }
]

对话格式（ShareGPT style）：推荐！
[
  {
    "conversations": [
      {"role": "system", "content": "你是翻译助手"},
      {"role": "user", "content": "翻译：今天是个好天气"},
      {"role": "assistant", "content": "Today is a nice day"},
      {"role": "user", "content": "再翻译：我喜欢编程"},
      {"role": "assistant", "content": "I love programming"}
    ]
  }
]

→ 多轮对话用 ShareGPT 格式，单轮用 Alpaca 格式
→ LLaMA-Factory 两种都支持
```

### 3.2 数据量参考

```
任务类型            推荐数据量        说明
简单格式适配        100-500 条        教模型用特定格式回答
领域知识注入        1K-10K 条         垂直领域问答
风格/人设塑造       500-2K 条         改变回答风格
复杂推理能力        10K-50K 条        需要高质量 CoT 数据
通用对话            50K-100K+ 条      提升综合能力

关键原则：
  ✅ 质量 >> 数量（LIMA 论文：1000 条高质量数据就够好）
  ✅ 多样性 > 重复（覆盖多种场景比同类数据堆量重要）
  ❌ 不要用低质量数据凑数（垃圾进垃圾出）
```

### 3.3 数据清洗 Checklist

```
□ 去重（完全重复 + 语义近似）
□ 去除过短/过长的样本（<10 字或 >2048 tokens）
□ 检查 input-output 是否对应（有些数据答非所问）
□ 去除有害/偏见内容
□ 检查语言一致性（不要中英混杂数据混在一起）
□ 确保答案质量（随机抽查 50 条人工检查）
□ token 长度分布统计（避免大量样本被截断）
```

## 4. 超参数选择 ⭐⭐

### 4.1 LoRA 超参数

```
参数              推荐值            说明
r (rank)         16               简单任务 8，复杂任务 32-64
lora_alpha       16 (= rank)      alpha/r = scaling factor，通常设为 1
lora_dropout     0.05             正则化，数据少时可以设 0.1
target_modules   "all" 或见下      哪些层加 LoRA

target_modules 选择：
  最少：["q_proj", "v_proj"]                      → 最省显存
  推荐：["q_proj", "k_proj", "v_proj", "o_proj"]  → 注意力层全加
  最多：上面 + ["gate_proj", "up_proj", "down_proj"] → FFN 也加，效果最好
  → LLaMA-Factory 中 lora_target: all 会自动选择所有线性层
```

### 4.2 训练超参数

```
参数                    推荐值              说明
learning_rate          1e-4 ~ 5e-4        QLoRA 通常 2e-4
                                           全参数微调用 1e-5 ~ 5e-5
num_epochs             2-3                 数据少可以 3-5，数据多 1-2
                                           过多 → 过拟合
batch_size             4-8                 显存不够就减小
gradient_accumulation  4-8                 等效 batch = bs × accum
                                           等效 batch 推荐 32-64
warmup_ratio           0.03-0.1           前 3-10% 步数线性升温
lr_scheduler           cosine              余弦退火，最后降到接近 0
weight_decay            0.01               轻度正则化
max_seq_length         1024-2048           根据数据实际长度设置
bf16                   true                A100/H100/4090 用 bf16
                                           V100/T4 用 fp16
```

### 4.3 不知道怎么选？用这组默认值

```yaml
# "黄金起步配置"，适用于大多数 7B 模型 QLoRA 微调
lora_rank: 16
lora_alpha: 16
lora_dropout: 0.05
lora_target: all
learning_rate: 2e-4
num_train_epochs: 3
per_device_train_batch_size: 4
gradient_accumulation_steps: 8   # 等效 batch_size = 32
warmup_ratio: 0.05
lr_scheduler_type: cosine
max_seq_length: 2048
bf16: true
```

## 5. 显存估算 ⭐

### 5.1 各模型显存需求

```
模型大小    全参数(FP16)    LoRA(FP16)    QLoRA(4bit)
1.5B        ~6 GB          ~4 GB         ~3 GB
7B          ~28 GB         ~18 GB        ~8 GB
13B         ~52 GB         ~34 GB        ~14 GB
32B         ~128 GB        ~80 GB        ~24 GB
70B         ~280 GB        ~160 GB       ~42 GB

注：以上为训练时显存（含优化器状态和梯度）
    推理时约为上述的 1/3-1/2
```

### 5.2 常见 GPU 适配

```
GPU               显存      能跑什么
RTX 3090/4090    24 GB     7B QLoRA ✅ | 13B QLoRA 勉强
A100-40G         40 GB     13B QLoRA ✅ | 7B LoRA FP16 ✅
A100-80G         80 GB     70B QLoRA ✅ | 13B 全参数 ✅
H100-80G         80 GB     同 A100-80G，速度更快
2× A100-80G      160 GB    70B LoRA FP16 ✅
Apple M2/M3      16-64 GB  7B QLoRA(MLX) ✅ 但慢
```

### 5.3 显存不够怎么办？

```
从低成本到高成本的方案：

1. 减小 batch_size + 增大 gradient_accumulation
   batch 4→1, accum 8→32 → 等效 batch 不变，显存减半

2. 减小 max_seq_length
   2048→1024 → 显存显著减少

3. 用 QLoRA 代替 LoRA
   FP16→4bit → 显存减少约 60%

4. 开启 gradient checkpointing
   用计算换显存 → 显存减少 30-50%，速度慢 20-30%

5. 减小 LoRA rank
   r=64→r=8 → LoRA 参数减少 8x

6. 用更小的模型
   13B→7B → 显存减半

7. 多卡并行 (DeepSpeed ZeRO)
   显存线性分摊到多张 GPU
```

## 6. 训练监控 ⭐

### 6.1 Loss 曲线怎么看

```
正常曲线：
  train_loss: 快速下降 → 平缓 → 基本不动
  eval_loss:  跟随下降 → 平缓 → 基本不动 (略高于 train)

过拟合信号 ⚠️：
  train_loss: 持续下降
  eval_loss:  先降后升 ← 这就是过拟合！
  → 减少 epoch / 增加数据 / 增大 dropout / 早停

欠拟合信号 ⚠️：
  train_loss: 下降很慢，最终值很高
  → 增大 lr / 增大 rank / 增加 epoch / 检查数据格式

Loss 突然飙升 ⚠️：
  → lr 太大 / 数据中有异常样本 / 精度溢出
  → 减小 lr 或检查数据

Loss 不下降 ⚠️：
  → 检查 Chat Template 是否正确（最常见原因！）
  → 检查 labels 是否正确（只有 assistant 的部分参与 loss 计算）
  → lr 太小
```

### 6.2 用什么工具监控

```
1. WandB (Weights & Biases) → 推荐
   HF Trainer 原生支持，加一行代码：
   report_to: wandb

2. TensorBoard
   HF Trainer 默认支持

3. LLaMA-Factory Web UI
   内置训练曲线可视化

关注指标：
  - train/loss → 训练损失
  - eval/loss → 验证损失
  - train/learning_rate → 学习率变化
  - train/grad_norm → 梯度范数（太大说明不稳定）
```

## 7. 训练后评估

### 7.1 快速验证

```
微调完成后，先做"冒烟测试"：

1. 手动对话测试
   准备 10-20 个代表性问题，人工检查回答质量
   包含训练数据内的问题 + 训练数据外的问题

2. 对比测试
   同一组问题，对比微调前后的回答
   → 微调后是否真的变好了？
   → 有没有灾难性遗忘（原来会的现在不会了）？

3. 边界测试
   故意问训练领域外的问题
   → 模型是否还能正常回答通用问题？
   → 是否出现"只会回答特定格式"的问题？
```

### 7.2 量化评估

```
任务类型          评估方法
分类/抽取        准确率、F1（有标准答案）
问答             人工评分 + LLM-as-Judge
对话             多轮对话连贯性、角色一致性
生成             BLEU/ROUGE（参考）+ 人工评分
综合             选几个 benchmark 跑分对比
```

## 8. 常见坑 & 排查 ⭐⭐

### 8.1 Loss 下降但输出变差

```
原因 1: Chat Template 错误
  模型学到了错误的格式 → loss 按错误模式下降
  排查: 打印格式化后的训练数据，检查模板

原因 2: Labels 设置错误
  system/user 的部分也参与了 loss 计算
  → 模型学会了"复读"用户的输入
  排查: 检查 labels 中非 assistant 部分是否为 -100

原因 3: 数据质量差
  答案本身有错误 / 答非所问
  排查: 随机抽查 50 条训练数据
```

### 8.2 灾难性遗忘

```
症状: 微调后领域任务变好，但通用能力变差

预防：
  1. 用 LoRA 而非全参数微调（冻结大部分参数）
  2. 混入通用数据（训练数据中保留 10-20% 通用对话）
  3. 减少训练轮次（别过度训练）
  4. 降低学习率

检测：
  准备一组通用测试题，微调前后对比
```

### 8.3 其他常见问题

```
问题：输出重复（"你好你好你好..."）
  → repetition_penalty 设为 1.1-1.2
  → 检查训练数据中是否有重复模式

问题：输出截断（回答不完整）
  → max_new_tokens 设大一些
  → 检查训练数据是否被 max_seq_length 截断

问题：输出混合语言（中英混杂）
  → 训练数据语言要统一
  → system prompt 中指定语言

问题：微调后拒绝回答变多
  → 可能基座模型的安全对齐太强
  → 需要更多正面示例数据

问题：多轮对话能力变差
  → 训练数据中要包含多轮对话样本
  → 不要全是单轮 QA
```

## 9. 从零到跑通的 Checklist

```
□ Step 1: 选模型
  推荐入门：Qwen2.5-7B / LLaMA-3.1-8B / Mistral-7B

□ Step 2: 准备数据
  至少 100-500 条高质量数据
  用 ShareGPT 格式
  人工检查 50 条确认质量

□ Step 3: 选工具
  第一次用 Unsloth 或 LLaMA-Factory

□ Step 4: 检查 Chat Template
  打印 3-5 条格式化数据，确认格式正确！

□ Step 5: 用默认超参数开始训练
  用第 4 节的"黄金起步配置"

□ Step 6: 监控训练
  观察 loss 曲线，确认正常下降

□ Step 7: 评估
  手动对话测试 + 对比测试 + 边界测试

□ Step 8: 迭代
  效果不好 → 先查数据质量，再调超参数
```

---

> ⬅️ [上一节：Compound AI Systems](./05-compound-ai-systems.md) | [返回概览](./README.md) | ➡️ [下一阶段：面试串联](../08-interview-synthesis/)
