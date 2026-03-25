# 机器学习 → 大模型 完整学习路线（面试导向）

> **定位**：你已有 AI 应用开发经验（RAG、Agent、LangChain），本路线补齐底层理论，从数学基础一路打通到大模型前沿，并桥接你的实战经验。

---

## 🗺️ 全景路线图

```
阶段0       阶段1        阶段2          阶段3              阶段4            阶段5             阶段6        阶段7           阶段8
数学基础 → ML基础 → 深度学习基础 → NLP+Embedding → Transformer → 预训练语言模型 → 大模型LLM → 理论-应用桥接 → 面试串联
 (1周)     (2周)      (2周)        +检索理论(1.5周)  +非Transformer    (1周)          (3周)       (1周)         (持续)
                                                     (1.5周)
```

**总预计时间**：13-15 周（每天 1-2 小时）

---

## 阶段 0：数学基础速通（1 周）

> 不需要精通，理解直觉即可。遇到不懂的公式回来查。

### 0.1 线性代数（Day 1-2）
- 向量、矩阵乘法的几何直觉
- 转置、逆矩阵、特征值 & 特征向量（PCA 基础）
- SVD 奇异值分解（降维、推荐系统、LoRA 底层原理）
- 🔑 Embedding 就是向量，Attention 就是矩阵乘法

### 0.2 概率与统计（Day 3-4）
- 条件概率、贝叶斯定理
- 常见分布：正态、伯努利、多项式
- MLE vs MAP、期望、方差
- 🔑 语言模型本质是概率模型 P(下一个词|前面的词)

### 0.3 微积分（Day 5）
- 导数、偏导数、链式法则
- 梯度的几何意义 → 反向传播 = 链式法则

### 0.4 信息论（Day 6-7）
| 概念 | 面试关联 |
|------|---------|
| 信息熵 | 不确定性度量 |
| 交叉熵 | 分类损失函数、语言模型训练目标 |
| KL 散度 | RLHF 中约束模型不偏离太远、知识蒸馏中 soft label |
| 互信息 | 特征选择、对比学习理论 |

### 📖 资源
- 3Blue1Brown《线性代数的本质》《微积分的本质》

---

## 阶段 1：机器学习基础（2 周）

### 1.1 核心框架（Day 1-3）
| 概念 | 一句话理解 | 面试考点 |
|------|-----------|---------|
| 监督/无监督/半监督/自监督 | 有标签/没标签/部分/自造标签 | **自监督是大模型预训练核心！** |
| 训练/验证/测试集 | 学习/模拟考/高考 | 怎么分？为什么分？ |
| 过拟合 vs 欠拟合 | 死记硬背 vs 没学会 | 判断 & 解决 |
| 偏差-方差权衡 | 准不准 vs 稳不稳 | 和过拟合关系 |
| 损失函数 | 衡量"错了多少" | MSE、交叉熵 |
| 梯度下降 | 闭眼下山 | SGD/Mini-batch/Adam |
| 特征工程 | 数据→特征 | DL 时代自动化了 |

### 1.2 经典算法（Day 4-7）
| 算法 | 核心思想 | 面试深度 |
|------|---------|---------|
| 线性回归 | 找最合适的线 | 损失+梯度下降第一例 |
| 逻辑回归 | 线性+sigmoid→分类 | sigmoid 如何变概率 |
| 决策树 | 20 个问题猜东西 | 信息增益/基尼系数 |
| 随机森林 | 多棵树投票(Bagging) | 集成学习 |
| XGBoost/LightGBM | 迭代纠错(Boosting) | Bagging vs Boosting |
| SVM | 最宽分隔带 | 核函数直觉 |
| K-Means | 自动分组 | 无监督代表 |
| PCA | 降维 | 特征值分解应用 |
| t-SNE/UMAP | 高维可视化 | Embedding 可视化 |

### 1.3 模型评估 & 调优（Day 8-10）
- **分类**：Accuracy、Precision、Recall、F1、AUC-ROC（Precision vs Recall 取舍）
- **回归**：MSE、MAE、R²
- **正则化**：L1(稀疏)、L2(平滑)、ElasticNet
- **交叉验证**：K-Fold
- **超参调优**：Grid/Random Search、Bayesian Optimization

### 📖 资源
- StatQuest、吴恩达 ML Coursera、《百面机器学习》

---

## 阶段 2：深度学习基础（2 周）

### 2.1 神经网络基础（Day 1-4）
| 概念 | 面试关注 |
|------|---------|
| 神经元(输入×权重+偏置→激活) | 和逻辑回归关系 |
| MLP | 万能近似定理 |
| 激活函数(ReLU/GELU/SiLU/Swish) | ReLU 好在哪？sigmoid 问题？GELU 为什么在 Transformer 中用？ |
| 反向传播 | 链式法则直觉 |
| 梯度消失/爆炸 | 解决方案 |
| BN vs LN | Transformer 用 LN 的原因 |
| Dropout | 正则化 |
| 权重初始化(Xavier/He) | 为什么不能全零？ |

### 2.2 优化器 & 训练技巧（Day 5-6）
- **优化器**：SGD → Momentum → RMSProp → Adam → AdamW
- **学习率**：Warmup、Cosine Decay、Linear Decay
- **混合精度**：FP32→FP16/BF16（省显存加速）
- 梯度累积、梯度裁剪

### 2.3 迁移学习 & 灾难性遗忘（Day 7）⭐ 新增
| 概念 | 为什么重要 |
|------|-----------|
| 迁移学习 (Transfer Learning) | 预训练+微调的理论基础。为什么 ImageNet 预训练能迁移到医疗图像？为什么 GPT 预训练能迁移到各种任务？ |
| 灾难性遗忘 (Catastrophic Forgetting) | 微调时模型"忘掉"预训练知识。解释了为什么需要 LoRA/冻结参数/正则化/EWC |
| Domain Adaptation | 源域→目标域的分布差异怎么处理 |

### 2.4 CNN（Day 8-9）
- 卷积核、池化、特征图
- 经典演进：LeNet→AlexNet→VGG→ResNet
- **Residual Connection** → Transformer 也用

### 2.5 RNN → LSTM → Attention（Day 10-12）⭐ 关键过渡
| 概念 | 为什么重要 |
|------|-----------|
| RNN | NLP 第一代方案 |
| LSTM(遗忘门/输入门/输出门) | 解决长期依赖 |
| GRU | LSTM 简化版 |
| Seq2Seq(编码器-解码器) | **Transformer 前身** |
| Attention | **Transformer 核心** |
| Beam Search | 解码策略基础 |

### 2.6 其他架构（Day 13-14）
- **Autoencoder / VAE**：编码-解码重建（生成模型基础）
- **GAN**：生成对抗（了解思想）
- **对比学习 (Contrastive Learning)**：SimCLR、MoCo → **CLIP 的理论基础**

### 📖 资源
- 3Blue1Brown《神经网络》、李宏毅 (B站)、d2l.ai

---

## 阶段 3：NLP + Embedding & 检索理论（1.5 周）

### 3.1 文本表示演进（Day 1-2）
```
One-Hot → BoW/TF-IDF → Word2Vec/GloVe → ELMo → BERT/GPT
  稀疏       统计         静态向量       上下文    预训练
```

| 概念 | 面试关注 |
|------|---------|
| Tokenization | BPE / WordPiece / SentencePiece / Unigram 四种方法及区别 |
| 词表大小权衡 | 太小→OOV，太大→稀疏+慢 |
| Word2Vec | CBOW vs Skip-gram，负采样 |
| 静态 vs 上下文表示 | "bank" 在不同句子含义不同 |

### 3.2 Embedding 深度理论（Day 3-4）⭐ 新增（桥接 RAG）
| 概念 | 为什么必须知道 |
|------|--------------|
| 句子级 Embedding | 从词向量 → 句子向量：Sentence-BERT (SBERT) 架构 |
| 对比学习训练 | InfoNCE Loss、正负样本构造 → Embedding 模型怎么训的 |
| 相似度度量 | 余弦相似度 vs 点积 vs 欧式距离 → **面试追问：为什么 RAG 用余弦？** |
| Embedding 维度 | 768/1024/1536 的权衡，维度越高越好吗？ |
| Embedding 微调 | 对比学习 + 硬负样本挖掘 → 领域适配 |
| 主流模型 | text-embedding-ada-002 / BGE / E5 / GTE 的差异 |

### 3.3 检索理论（Day 5-6）⭐ 新增（桥接 RAG）
| 概念 | 面试关联 |
|------|---------|
| BM25 (稀疏检索) | TF-IDF 的改进版，为什么关键词匹配仍重要 |
| Dense Retrieval (稠密检索) | 语义检索，用 Embedding 向量 |
| ANN 近似最近邻算法 | **HNSW** (分层导航小世界图)、IVF、PQ → 向量数据库核心 |
| Bi-Encoder vs Cross-Encoder | 检索用 Bi (快)、重排用 Cross (准) → **Reranking 原理** |
| Hybrid Search (混合检索) | 稀疏+稠密融合，RRF 排序 |
| HyDE | 先让 LLM 生成假设文档再检索 |

### 3.4 语言模型 & 解码（Day 7-8）
| 概念 | 理解 |
|------|------|
| 自回归 (AR) | 从左到右预测（GPT）|
| 自编码 (AE) | 完形填空（BERT）|
| Perplexity | 语言模型评估指标 |
| Greedy → Beam → Top-k → Top-p → Temperature | 解码策略演进 |

### 3.5 受控生成 & 结构化输出（Day 9-10）⭐ 新增
| 概念 | 为什么重要 |
|------|-----------|
| Constrained Decoding | 在解码时限制 token 选择范围 → JSON Mode 底层原理 |
| Grammar-guided Generation | 用 CFG/正则约束输出格式 |
| Function Calling 训练机制 | 模型怎么学会输出函数调用？SFT 数据格式是什么样？ |
| Logit Processor | Temperature、Top-p、重复惩罚的统一框架 |
| Structured Output | 从 prompt 约束 → 解码约束 → 微调约束的演进 |

---

## 阶段 4：Transformer + 非 Transformer 架构（1.5 周）

### 4.1 Transformer 核心（Day 1-3）

```
Attention(Q, K, V) = softmax(QK^T / √d_k) V
```

| 核心组件 | 面试必问 |
|---------|---------|
| Self-Attention | Q/K/V 来源？√d_k 为什么？ |
| Multi-Head Attention (MHA) | 为什么多头？ |
| 位置编码 | 正弦余弦 / 学习式 / RoPE / ALiBi |
| FFN (SwiGLU) | d→4d→d，现代 LLM 用 SwiGLU 替代 ReLU |
| Pre-Norm vs Post-Norm | 现代 LLM 都用 Pre-Norm |
| Residual Connection | 梯度直通 |
| Mask | Padding Mask vs Causal Mask |

### 4.2 三种架构范式（Day 4）
| 类型 | 代表 | 训练方式 | 适合任务 |
|------|------|---------|---------|
| Encoder-only | BERT | MLM | 理解：分类、NER |
| Decoder-only | GPT | CLM | 生成 → **大模型主流** |
| Encoder-Decoder | T5 | 多种 | 翻译、摘要 |

### 4.3 Attention 变体（Day 5-6）⭐
| 变体 | 核心思想 | 代表模型 |
|------|---------|---------|
| MHA | 每头独立 Q/K/V | 原始 Transformer |
| MQA | 共享 K/V | PaLM |
| GQA | 分组共享 | LLaMA 2/3 |
| MLA | 低秩压缩 KV | DeepSeek-V2/V3 |
| Flash Attention | IO-aware 精确计算 | 所有现代 LLM |
| Sliding Window | 局部窗口 | Mistral |
| Sparse Attention | Longformer/BigBird 模式 | 长文本模型 |

### 4.4 非 Transformer 架构（Day 7-10）⭐ 新增
> 面试区分度问题："Transformer 有什么问题？有替代方案吗？"

| 架构 | 核心思想 | 面试关注 |
|------|---------|---------|
| **Mamba / SSM** | 状态空间模型，线性复杂度，选择性扫描 | Transformer 的 O(n²) 问题 → SSM 的 O(n) 方案 |
| **Mamba-2** | 结构化 SSM 与 Attention 的统一 | 为什么 SSM 能替代 Attention？ |
| **RWKV** | RNN 复兴，线性 Attention 变体 | 和传统 RNN 的区别？ |
| **Jamba** | Mamba + Transformer 混合架构 | 混合架构为什么可能是最优解？ |
| **RetNet** | 保留网络，推理时 O(1) 复杂度 | 训练并行性 vs 推理效率 |
| **xLSTM** | LSTM 现代化改进 | 经典架构复兴的尝试 |

**关键对比**：
```
              训练并行性   推理复杂度   长序列能力
Transformer     ✅ 好       O(n²)      受限于窗口
Mamba/SSM       ✅ 好       O(n)→O(1)  理论无限
RWKV            ✅ 好       O(1)       理论无限
```

### 📖 资源
- Illustrated Transformer、3Blue1Brown Transformer 视频
- Mamba 论文、Albert Gu 的 SSM 系列讲座

---

## 阶段 5：预训练语言模型时代（1 周）

### 5.1 BERT 家族（Day 1-3）
| 模型 | 改进 |
|------|------|
| BERT | MLM + NSP，双向编码 |
| RoBERTa | 去 NSP，更多数据，动态 mask |
| ALBERT | 参数共享+因式分解 |
| DeBERTa | 解耦注意力（内容+位置分离）|
| DistilBERT | 知识蒸馏压缩 |

### 5.2 GPT 演进（Day 4-5）
| 模型 | 关键突破 |
|------|---------|
| GPT-1 | 预训练+微调范式 |
| GPT-2 | Zero-shot 能力 |
| GPT-3 | In-Context Learning，175B |

### 5.3 里程碑 & 范式转换（Day 6-7）
- T5：统一 text-to-text
- CLIP：图文对齐（多模态基础）
- Pre-train→Fine-tune vs Pre-train→Prompt 范式转换
- 自监督学习：MLM、CLM、Denoising

---

## 阶段 6：大模型 LLM 核心知识（3 周）

### 6.1 训练三阶段（Day 1-4）⭐ 面试高频
```
预训练 (PT) → 监督微调 (SFT) → 对齐 (Alignment)
  "学知识"      "学听话"          "学做人"
```

| 阶段 | 数据 | 面试关注 |
|------|------|---------|
| 预训练 | TB 级无标注 | 数据清洗、去重、配比 |
| SFT | 指令-回复对 | 质量>数量(LIMA) |
| RLHF | 人类偏好排序 | Reward Model → PPO |
| DPO | 偏好对直接优化 | 跳过 Reward Model |
| GRPO | Group Relative Policy | DeepSeek 使用 |

### 6.2 对齐技术演进（Day 5-6）⭐ 扩展
| 方法 | 核心思想 | 时间线 |
|------|---------|--------|
| RLHF (PPO) | 训 Reward Model → PPO 优化 | 2022（经典）|
| DPO | 直接从偏好对优化，无需 RM | 2023 |
| KTO | 只需要 👍/👎 标签，不需要配对 | 2024 |
| ORPO | 统一 SFT + 偏好优化 | 2024 |
| SimPO | 简化 DPO，无需参考模型 | 2024 |
| GRPO | 组内相对排序 | 2024(DeepSeek) |
| Constitutional AI | 让 AI 自我监督和修正 | Anthropic |

### 6.3 RL 基础（Day 7，RLHF 前置）
- 策略、奖励、价值函数
- PPO：限制每步更新幅度
- KL 散度约束：防止偏离参考模型

### 6.4 Scaling Law（Day 8）
- Kaplan Law → Chinchilla Law（修正）
- **涌现能力**：为什么大到某点突然"开窍"？
- Test-time Compute Scaling：推理时多花算力

### 6.5 分布式训练（Day 9-10）⭐ 工程必考
| 技术 | 核心思想 |
|------|---------|
| 数据并行 (DP) | 同模型不同数据 |
| 张量并行 (TP) | 矩阵拆分到多 GPU |
| 流水线并行 (PP) | 不同层放不同 GPU |
| ZeRO (DeepSpeed) | 优化器状态分片 |
| FSDP (PyTorch) | 全分片数据并行 |
| 混合精度 | FP16/BF16 + FP32 主权重 |
| 梯度检查点 | 时间换显存 |

### 6.6 推理优化（Day 11-12）
| 技术 | 核心思想 |
|------|---------|
| KV-Cache | 缓存已算 K/V |
| 量化 (GPTQ/AWQ/GGUF) | FP32→INT8/INT4 |
| 推测解码 | 小模型猜大模型验 |
| Flash Attention | 优化内存访问 |
| PagedAttention | 虚拟内存管理 KV |
| Continuous Batching | 动态批处理 |
| vLLM / TGI / TRT-LLM | 推理引擎 |

### 6.7 知识蒸馏深入（Day 13）⭐ 扩展
| 概念 | 要点 |
|------|------|
| Hard Label vs Soft Label | 为什么 soft label 包含更多信息（类间关系）？ |
| Temperature 在蒸馏中 | 高 T 使分布更"软"，暴露更多知识 |
| Feature Distillation | 不只学输出，还学中间层特征 |
| 在线蒸馏 vs 离线蒸馏 | 师生同时训练 vs 先训师再训生 |

### 6.8 微调技术（Day 14-15）
| 技术 | 核心思想 |
|------|---------|
| 全参数微调 | 成本高效果好 |
| LoRA | 冻结原参 + 低秩矩阵 |
| QLoRA | 量化 + LoRA |
| Adapter | 层间小模块 |
| Prefix/P-Tuning v2 | 可学习前缀 |

### 6.9 MoE 混合专家（Day 16）⭐ 热点
- 稀疏激活：每 token 只走部分专家
- Router/Gate 机制、负载均衡
- 代表：GPT-4、Mixtral、DeepSeek-V2/V3

### 6.10 推理模型（Day 17）⭐ 最前沿
- o1/o3：思维链 + test-time compute
- DeepSeek-R1：开源推理模型
- 长思考 vs 快思考

### 6.11 多模态（Day 18）
- Vision Encoder + LLM (LLaVA)、CLIP 图文对齐
- GPT-4V/4o、Gemini、语音 Whisper

### 6.12 LLM for Code（Day 19）⭐ 新增
| 概念 | 为什么和你相关 |
|------|--------------|
| Code LLM 训练数据 | 代码+注释+文档的配比 |
| Fill-in-the-Middle (FIM) | 代码补全的训练技巧 |
| 代表模型 | CodeLLaMA / DeepSeek-Coder / StarCoder |
| 和通用 LLM 的区别 | 长上下文、结构化思维、测试生成 |

### 6.13 AI Safety（Day 20）⭐ 新增
| 概念 | 面试关注 |
|------|---------|
| Prompt Injection | Direct vs Indirect，攻击分类 |
| Jailbreak 系统化分类 | 角色扮演、编码绕过、Universal Suffix |
| 防御方案 | Input filtering / Output filtering / Guardrails / Constitutional AI |
| Red Teaming | 系统性安全测试方法 |

### 6.14 模型合并（Day 21）⭐ 新增
| 方法 | 思想 | 价值 |
|------|------|------|
| Model Merging | 多个微调模型合并为一个 | 不用重新训练 |
| DARE | 随机丢弃+放缩 delta 权重 | 稀疏合并 |
| TIES | 修剪+解决符号冲突 | 更稳定 |
| SLERP | 球面线性插值 | 两模型平滑混合 |

### 6.15 LLM 评估（贯穿）
| Benchmark | 能力 |
|-----------|------|
| MMLU | 多任务知识 |
| HumanEval | 代码 |
| GSM8K | 数学推理 |
| TruthfulQA | 真实性 |
| MT-Bench | 多轮对话 |
| Arena Elo | 人类偏好 |

### 6.16 数据工程 & 课程学习（贯穿）⭐ 扩展
- 预训练数据：CommonCrawl 清洗、去重、有害过滤、配比
- SFT 数据：Self-Instruct、Evol-Instruct
- 合成数据：用强模型生成训练数据的理论边界
- **课程学习 (Curriculum Learning)**：训练数据排序影响质量（先易后难）

### 6.17 长上下文技术
- RoPE 位置插值 / NTK-aware 扩展
- Sliding Window / Ring Attention / 上下文压缩

### 6.18 关键模型族总览
| 模型族 | 关键特点 |
|--------|---------|
| GPT (OpenAI) | 商业标杆，o1 推理 |
| LLaMA (Meta) | 开源标杆 |
| DeepSeek | MoE+MLA，R1 推理 |
| Qwen (阿里) | 国产开源最活跃 |
| Claude (Anthropic) | Constitutional AI |
| Gemini (Google) | 原生多模态 |
| Mistral/Mixtral | 小模型+MoE |

### 6.19 幻觉（Hallucination）
- 内在 vs 外在幻觉
- 缓解：RAG、自一致性检查、Grounding、RLHF

### 6.20 扩展方向（🔒 可选，暂不展开）
| 方向 | 简介 | 什么时候需要 |
|------|------|------------|
| **Diffusion Model（扩散模型）** | Stable Diffusion / DALL-E 的原理，去噪生成过程 | 面试图像生成、多模态深入方向 |
| **联邦学习 (Federated Learning)** | 数据不出本地的分布式训练，隐私保护 | 金融、医疗等对数据隐私严格的行业 |
| **图神经网络 (GNN)** | 图结构数据上的深度学习，消息传递机制 | GraphRAG 底层原理、知识图谱 + LLM |

---

## 阶段 7：理论-应用桥接（1 周）⭐ 新增阶段

> 把底层 ML/DL 理论和你的 RAG/Agent 实战经验打通

### 7.1 RAG 的 ML 理论基础
```
你的应用经验           底层理论
─────────────        ──────────
向量检索             → Embedding 对比学习 + ANN(HNSW)
Reranking            → Cross-Encoder vs Bi-Encoder
Chunking 策略        → 信息论：信息密度与冗余
Hybrid Search        → 稀疏(BM25) + 稠密检索融合
Query Expansion      → HyDE、Query Rewriting
评估指标             → Recall@K、MRR、NDCG
```

### 7.2 Agent 的 ML 理论基础
```
你的应用经验           底层理论
─────────────        ──────────
Function Calling     → SFT 数据格式 + Constrained Decoding
ReAct 模式           → CoT + 工具调用交替
多 Agent 协作        → 通信协议 + 角色 SFT
Agent 记忆           → KV-Cache + 外部存储检索
Planning             → Tree-of-Thought + Monte Carlo
```

### 7.3 Prompt Engineering 的 ML 理论基础
```
你的应用经验           底层理论
─────────────        ──────────
Few-shot 有效         → In-Context Learning 理论（隐式梯度下降？）
CoT 有效              → 推理 = 中间 token 提供计算步骤
System Prompt         → 条件概率 P(output | system + user)
Temperature 调节      → softmax 温度参数对分布的影响
```

---

## 阶段 8：面试串联（持续）

### 8.1 知识全景图

```
数学基础 (线代、概率、信息论)
  └── ML基础 (损失、梯度、正则化)
       └── 深度学习 (NN→CNN→RNN→Attention→迁移学习)
            └── NLP (Tokenization→Embedding→检索理论)
                 └── Transformer + 非Transformer(Mamba/SSM)
                      └── 预训练模型 (BERT→GPT→T5→CLIP)
                           └── 大模型 LLM
                                ├── 训练：PT→SFT→RLHF/DPO/GRPO
                                ├── 架构：MoE / GQA / MLA / Flash
                                ├── 部署：量化 / KV-Cache / vLLM
                                ├── 微调：LoRA / QLoRA
                                ├── 推理模型：o1 / DeepSeek-R1
                                ├── 多模态：GPT-4V / CLIP
                                ├── 安全：Red Teaming / 对齐
                                ├── 非Transformer：Mamba / RWKV
                                └── 应用桥接（你的经验）
                                     ├── RAG：Embedding+检索+重排
                                     ├── Agent：ReAct+Tool Use
                                     └── LangChain/LangGraph
```

### 8.2 面试高频 Top 25

| # | 问题 | 阶段 |
|---|------|------|
| 1 | Transformer Self-Attention 机制 | 4 |
| 2 | BERT vs GPT 区别 | 4-5 |
| 3 | 预训练→SFT→RLHF 三阶段 | 6 |
| 4 | LoRA 原理与优势 | 6 |
| 5 | MoE 混合专家 | 6 |
| 6 | KV-Cache 加速原理 | 6 |
| 7 | 量化方法比较 | 6 |
| 8 | Scaling Law | 6 |
| 9 | RAG 流程 & Embedding 原理 | 3+7 |
| 10 | 过拟合及解决 | 1 |
| 11 | 梯度下降 & 反向传播 | 0-2 |
| 12 | 位置编码(RoPE) | 4 |
| 13 | GQA/MQA vs MHA | 4 |
| 14 | 解码策略 Top-k/Top-p/Temp | 3 |
| 15 | Chain-of-Thought | 6 |
| 16 | 分布式训练 DP/TP/PP | 6 |
| 17 | 幻觉及缓解 | 6 |
| 18 | Flash Attention | 4 |
| 19 | DPO vs RLHF | 6 |
| 20 | Agent ReAct 模式 | 7 |
| 21 | **Mamba/SSM vs Transformer** | 4 |
| 22 | **向量检索算法(HNSW)** | 3 |
| 23 | **Function Calling 怎么训** | 3+7 |
| 24 | **灾难性遗忘 & 解决** | 2 |
| 25 | **模型合并方法** | 6 |

### 8.3 学习策略
1. **费曼学习法**：每学完一个概念用自己的话讲一遍
2. **面试驱动**：先看题，带着问题学
3. **不死磕数学**：理解直觉 > 推导公式
4. **画图**：Transformer、训练流程、Attention 都画出来
5. **结合经验**：每学一个概念就想想对应 RAG/Agent 的什么

---

## 📋 推荐资源

| 资源 | 覆盖阶段 | 推荐度 |
|------|---------|--------|
| 李宏毅机器学习 (B站) | 0-6 全覆盖 | ⭐⭐⭐⭐⭐ |
| 3Blue1Brown | 0,2,4 | ⭐⭐⭐⭐⭐ |
| StatQuest | 0-1 | ⭐⭐⭐⭐⭐ |
| 吴恩达系列 | 1-2 | ⭐⭐⭐⭐ |
| 《百面机器学习》 | 1-2 面试 | ⭐⭐⭐⭐⭐ |
| d2l.ai | 2-4 | ⭐⭐⭐⭐ |
| Illustrated Transformer | 4 | ⭐⭐⭐⭐⭐ |
| Lilian Weng Blog | 5-6 | ⭐⭐⭐⭐⭐ |
| Mamba 论文 & 讲解 | 4 | ⭐⭐⭐⭐ |

> **你的核心竞争力**：底层理论 + 实际应用经验的结合。阶段 7（桥接层）是你区别于纯理论/纯应用候选人的关键。
