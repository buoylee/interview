# ML 动手训练 Labs · 设计 spec

> **日期**:2026-06-17
> **定位**:为面试补齐「能跑、能训出模型的 runnable 产物」,填上 ML/DL 层只有 prose、没有作品的缺口。面试优先,顺带学会,robotics 兴趣单独分轨。

## 1. 背景与问题

`ai/ml-to-llm-roadmap/` 的理论覆盖已很完整,但「动手训练」这一层几乎只有文档:`pytorch-learning/` 是 markdown 章节,`rag-lab/` 是 markdown,真正能跑的只有 `agent-loop-lab/`(uv+pytest 工程)和 `fine-tuning/` 的 QLoRA notebook。

用户原始诉求:没做过经典 ML「训一个模型」的实验(识别数字 0-9、识别日常物品、意图识别、TTS、房价预测、训 LLM),想知道科班是否该做、哪些对面试加分。

**结论**:用户面的是 **AI Engineer / LLM 应用工程师**(在基础模型之上做 RAG/Agent/微调/推理),不是 ML Research/MLE(训模型的岗)。对这个目标岗,经典实验大多是「课程做过」级别、不差异化;真正要补的是三个信任缺口:

1. 你只会调 API,还是真能训出东西?
2. 你是真懂 Transformer,还是背名词?
3. 你知不知道什么时候*不该*用 LLM?

因此不是 6 个全做,而是按「缺口覆盖 + 面试可讲」挑选,并把 robotics 相关的低面试 ROI 项分到单独一轨。

## 2. 目标与非目标

**目标**

- 每个 lab 都能在用户的 **Apple M4 / 16GB / MPS(无 CUDA、无云 GPU)** 上几分钟内跑完。
- 每个 lab 产出一句「能在白板上讲」的面试故事,并连回 roadmap 对应笔记。
- 产出(loss 曲线、生成样本、指标表)commit 进 repo,使「作品」在 GitHub 浏览时即可见。
- 离线、确定性(固定 seed、内建/bundle 小数据集),不依赖线上服务。

**非目标**

- 不复刻一个科班四年的完整 lab 清单。
- 不从零训练 TTS / 大模型(16GB 不现实)。
- 不追求 SOTA 精度;追求方法论清晰 + 可复现。
- 本 spec 不一次实现全部 lab;实现按 lab 增量进行(见 §7)。

## 3. 现实约束(已实测)

| 项 | 值 |
|---|---|
| 芯片 / 架构 | Apple M4 / arm64 |
| 内存 | 16 GB |
| 加速 | MPS(无 CUDA、无 nvidia-smi) |
| Python / 工具 | 3.11.8 / uv 0.7.13 / torch 未装 |

含义:tabular、MNIST、意图分类、tiny-GPT、迁移学习全部可跑;**从零训 TTS 不可行 → TTS 改为「接开源 TTS」并归入 robotics 轨**。

## 4. 两轨结构

### Track A — 面试核心(现在做)

| Lab | 白板故事 | 连回笔记 | 算力 |
|---|---|---|---|
| **A1 · tiny-GPT 从零**(char 级,~10M 参数) | 「我手写了 multi-head self-attention,在 Mac 上训出一个会生成文字的 decoder-only 模型,还能调 temperature/top-k 看输出变化」 | 04-transformer-foundations(本体)、03-generation-control、06-llm-core 训练管线 | tiny config 几分钟(MPS) |
| **A2 · 意图识别 / 文本分类** | 「我做过 embedding+轻分类器 vs 微调 DistilBERT 两条路,知道路由/护栏这种场景*不该*动不动调 GPT-4,有延迟和成本的实测数字」 | 02-agent-tool-use(router/guardrail)、03-nlp-embedding、05-pretrained(BERT) | embedding+LR 秒级;DistilBERT 微调 分钟级 |
| **A3 · 房价预测(tabular 回归)** | 「我能从 baseline 出发讲清 train/val/test、过拟合、正则、RMSE vs MAE 怎么选、数据泄漏这个坑」 | 01-ml-basics、03-evaluation-tuning | sklearn 秒级 |

> **MNIST** 不单独当 keystone,作为 A1 之前的「PyTorch 训练循环热身鞍」,一个小节带过,让 `pytorch-learning/05-training-loop` 变真。

### Track B — Robotics / Embodied AI(写,但明确标「非当前面试」、单独放)

| Lab | 定位 | 为何分开 |
|---|---|---|
| **B1 · 图像/物体识别(迁移学习 ResNet)** | 机器人**感知**入门 | 对 LLM 岗是支线,但是 embodied AI 的眼睛 |
| **B2 · 语音回路:STT(Whisper)+ 接开源 TTS** | 机器人**人机语音**接口(整合,非训练) | 训 TTS 不现实;符合「纯开源逃生票」偏好 |
| **B3 · 路标文档:RL / 模仿学习 / VLA** | 指出 embodied AI 真正的训练范式,说明 A1+B1 是其前置 | 现在建是坑,只画地图显示这座桥 |

## 5. 目录与格式

### 落点:新建 `ai/ml-labs/`(与 `rag-lab/`、`agent-loop-lab/` 平级)

```
ai/ml-labs/
  README.md                  # 两轨地图 + 「面试故事」索引 + 怎么跑
  pyproject.toml             # 一个共享 uv 工程,dependency groups 按需装:
                             #   core=torch / nlp=transformers,datasets
                             #   vision=torchvision / audio=whisper,(开源 TTS client)
  .gitignore                 # 忽略 .venv、模型权重(*.pt/*.ckpt)、数据缓存
  interview/
    a3-house-price/
    a2-intent-classification/
    a1-tiny-gpt/
  robotics/
    README.md                # 顶部「⚠️ 非当前面试 · Embodied AI 长线」横幅
    b1-image-perception/
    b2-voice-loop/
    b3-rl-imitation-vla-roadmap.md
```

> 一个共享 `.venv` + uv groups,而非每个 lab 各自一个 venv(省磁盘,顺带练 uv groups)。

### 每个 lab 的固定骨架

```
<lab>/
  README.md      # ① 一句话这是什么 + 答哪道面试题
                 # ② 白板故事(正文教学,底层写进正文)
                 # ③ 怎么跑(uv run ...)
                 # ④ 把产出直接贴出来(曲线/样本/指标)
                 # ⑤ 结尾 3-5 条「面试追问」,只做复习自检,不承载新知识
  *.py           # 脚本优先:能跑、gittable、像 agent-loop-lab
  data/          # bundle 进 repo 的小数据集(离线确定性)
  outputs/       # ✅ commit:loss 曲线 png + samples.txt + metrics.md
                 # ❌ gitignore:模型权重
  notebook.ipynb # 可选,仅 A1 / MNIST 这种「看 loss 曲线跳」有助学习时配
```

### 三条关键设计决定

1. **脚本优先,不是只有 notebook**:`.py` 当作品更硬;只有「看曲线有助学习」的 lab 额外配 notebook。
2. **产出 commit 进 repo**:面试官在 GitHub 浏览即见 loss 曲线、生成样本、指标表 —— 与「prose lab」拉开差距。权重不入库,只入小产出。
3. **数据离线 + 确定性**:优先内建/bundle 小数据集(A3 用 sklearn 内建 california housing;A1 bundle 一小段公版文字),固定 seed,可重跑。

## 6. 各 Lab 内容要点

### A3 · 房价预测(先做,验证脚手架)
- 数据:sklearn 内建 california housing(零下载)。
- 主线是**方法论**不是模型:baseline → train/val/test split → 特征工程 → 过拟合演示 → 正则(Ridge/Lasso)→ 指标选择(RMSE vs MAE,为何)→ 误差分析。
- 必含一个**数据泄漏**陷阱演示(经典面试坑)。
- 产出:metrics.md(各阶段对比)、误差分析图。

### A2 · 意图识别 / 文本分类
- 两条路显式对比:
  - (a) 便宜路:sentence-embedding + logistic regression(生产 router 模式,CPU 秒级)。
  - (b) 微调路:DistilBERT 加分类头微调(MPS 分钟级)。
- 数据:bundle 一个小意图数据集(如 CLINC/SNIPS 子集或自建小 CSV)。
- 产出:两条路的 accuracy + **延迟/成本对比表**(支撑「何时不用 LLM」的故事)。
- 加分:可与 `agent-loop-lab` 联动,把分类器当 router 插进去(spec 内记为可选延伸,不强制)。

### A1 · tiny-GPT 从零(皇冠,最后收尾)
- 从零实现 decoder-only transformer:attention / multi-head / block / 位置编码(参考 nanoGPT / makemore 血统;可借助已装的 `andrej-karpathy-skills` guidelines)。
- char 级,小语料(Shakespeare 或用户自选/中文小语料,bundle 进 repo)。
- tiny config(约 n_layer 4-6 / n_head 4-6 / n_embd 256-384 / block_size 128-256),MPS 几分钟出基本连贯文本,固定 seed。
- `sample.py` 暴露 temperature / top-k,让 03-generation-control 的解码参数变成亲手可调。
- 产出:loss 曲线 png + 不同采样参数下的 samples.txt。
- 前置热身:MNIST 小节(PyTorch 训练循环 hello world)。

### B1 · 图像/物体识别(robotics 轨)
- 迁移学习版优先:冻结预训练 ResNet backbone + 换头微调(对应 LLM 微调心智模型)。
- 数据:CIFAR-10(torchvision 一次性下载)或小子集。
- 强调:这是机器人感知入门。

### B2 · 语音回路(robotics 轨)
- 整合非训练:Whisper(STT)+ 开源 TTS(纯开源,符合偏好)拼一个语音输入→输出回路。
- 文档说明为何不从零训 TTS(算力)+ 开源 TTS landscape。

### B3 · RL/模仿学习/VLA 路标(robotics 轨)
- 仅 markdown 路标文档:说明 embodied AI 真正训练范式(RL、imitation learning、Vision-Language-Action 模型),指出 A1(transformer)+ B1(感知/迁移)是其前置。不建代码。

## 7. 增量交付

- 本 spec = 整张两轨地图。
- spec 落定 → writing-plans 出实现计划 → **一个 lab 一个 lab 建**。
- 默认顺序:**A3 → A2 → A1**(便宜到贵、复用同一脚手架、收尾在皇冠),再 **B1 → B2**,B3 随时补。可选「先上 A1」。
- 每个 lab 完成的判定:能 `uv run` 跑通 + 产出已 commit + README 五段齐全。

## 8. roadmap 集成

- `ai/ml-to-llm-roadmap.md` 增加指向 `ai/ml-labs/` 的「动手实验」入口。
- 每个 lab 的 README 反向链接其对应的 roadmap 模块(见 §4 表「连回笔记」列)。
- `ai/README.md` 顶层目录登记 `ml-labs/`。
