# ML to LLM Roadmap Systematic Learning Redesign

## 背景

第一批 `04-transformer-foundations` 样板已经把路线从旧的学科顺序改成了 AI Engineer 面试导向，但实际阅读反馈暴露出一个更根本的问题：

系统学习材料和面试复习材料的边界仍然不够清晰。某些主线文档为了快速连接面试高频点，开始压缩概念解释。例如 `05-decoder-only-and-generation.md` 直接给出 Encoder-only、Encoder-Decoder、Decoder-only 的对照表，但没有先解释原始 Transformer 为什么有 Encoder 和 Decoder、三种架构是怎样从原始结构演化或裁剪出来的。

这会让学习者产生“好像内容都提到了，但我心里没底”的感觉。问题不是缺少更多速记，而是第一次学习时缺少连续、可依赖的概念链。

## 目标

重新定义 `ml-to-llm-roadmap` 的文档产品顺序：

1. 先完成系统学习版文档，让学习者可以顺着主线读懂。
2. 再基于系统学习版提炼面试阅读路径。
3. 最后生成面试速记、30 秒答案、追问和易混点。

系统学习文档的验收标准不是“覆盖了多少概念”，而是“学习者是否知道每个概念为什么出现、解决什么问题、和前后知识如何连接”。

## 非目标

- 不把主线文档写成面试题库。
- 不为了短期面试效率牺牲第一次学习的流畅性。
- 不要求每个主题都写成完整教材，但必须解释当前主题必需的前置心智模型。
- 不在系统学习主线中堆砌百科式旁支；旁支进入 `foundations/` 或后续拓展阅读。

## 核心决策

采用四层文档体系，并明确依赖方向：

```text
Systematic Learning -> Interview Paths -> Review Notes
                 |
                 v
            Foundations
```

含义：

- `Systematic Learning` 是第一次学习入口，必须自洽。
- `Foundations` 是补课入口，只在主线出现前置缺口时跳转。
- `Interview Paths` 是学完后按面试优先级重排阅读顺序。
- `Review Notes` 是最后的记忆压缩，不承担第一次讲懂知识的责任。

## 文档层级

### 1. Systematic Learning

位置沿用主线目录，例如：

```text
ai/ml-to-llm-roadmap/
  01-rag-retrieval/
  02-agent-tool-use/
  03-generation-control/
  04-transformer-foundations/
  ...
```

职责：

- 第一次讲懂一个主题。
- 按依赖顺序引入概念。
- 每个新概念都说明“为什么需要它”。
- 每篇文档只解决一个明确学习问题。

### 2. Foundations

位置：

```text
ai/ml-to-llm-roadmap/foundations/
```

职责：

- 补主线所需的前置知识。
- 不承担默认学习入口。
- 每个 foundation 文件必须明确“它解锁哪些主线章节”。

### 3. Interview Paths

建议新增：

```text
ai/ml-to-llm-roadmap/interview-paths/
```

职责：

- 面试前按时间和岗位目标组织阅读顺序。
- 告诉学习者哪些系统章节必须看、哪些可以快速扫、哪些只做复习。
- 不重复讲概念，只链接系统学习文档和 review notes。

### 4. Review Notes

位置：

```text
ai/ml-to-llm-roadmap/09-review-notes/
```

职责：

- 30 秒答案。
- 2 分钟展开。
- 高频追问。
- 易混点对照。
- 项目经验连接。

限制：

- 不作为第一次学习入口。
- 不引入系统主线没有解释过的新核心概念。
- 每条速记必须能反向链接到系统学习材料。

## 系统学习文档标准

每篇系统学习文档必须包含以下结构。

### 1. 这一篇解决什么问题

开头必须回答：

- 为什么现在要学这个？
- 如果不懂它，后面哪个主题会卡住？
- 它和 RAG、Agent、生成、推理成本、评估或系统设计有什么关系？

### 2. 学前检查

列出必需前置知识，并链接到 foundation。

要求：

- 只列真正必要的前置知识。
- 不使用“你应该已经懂”这种空泛表述。
- 每个前置知识都给出补课链接或一句最小解释。

### 3. 概念为什么出现

新概念不能直接给定义，必须先给问题。

例如讲 Decoder-only 前，不能只说“Decoder-only 是只保留 Decoder 的架构”，而要先解释：

- 原始 Transformer 为什么分 Encoder 和 Decoder。
- Encoder 负责把输入读懂。
- Decoder 负责在生成时看已生成内容，并读取 Encoder 的结果。
- 后来不同任务需要不同裁剪方式，于是出现 Encoder-only、Encoder-Decoder、Decoder-only。

### 4. 最小心智模型

每个核心概念至少说明：

- 输入是什么。
- 输出是什么。
- 中间做了什么。
- 它依赖前一篇的哪个概念。

### 5. 最小例子

用一个小例子帮助落地，优先使用 LLM 应用场景。

示例：

- prompt token 如何变成 embedding。
- 一个 token 如何通过 attention 读取其他 token。
- Decoder-only 如何基于已有上下文预测下一个 token。
- RAG 里 embedding 模型为什么更像 Encoder-only 用法。

### 6. 和应用/面试的连接

系统学习文档可以提面试，但不能变成面试笔记。

写法：

- “这会影响什么工程现象”
- “面试通常会怎么问”
- “完整速记见 review note”

### 7. 常见误区

每篇至少列 2 到 4 个容易混淆点。

例如：

- Decoder-only 不是“没有 attention”，而是使用带 causal mask 的 self-attention。
- Encoder-only 不是完全不用生成，而是不是天然自回归生成。
- KV Cache 加速 decode，不消除长 prompt 的 prefill 成本。

### 8. 自测和下一步

自测必须验证理解，而不是背定义。

下一步必须明确：

- 继续读哪篇主线。
- 如果卡住，回哪篇 foundation。
- 如果准备面试，去哪个 review note。

## Transformer 样板重做设计

第一条要重做的是 `04-transformer-foundations`。当前样板可以保留作为素材，但要调整为真正的系统学习链路。

建议拆分为：

```text
04-transformer-foundations/
  README.md
  01-why-ai-engineers-need-transformer.md
  02-token-to-vector.md
  03-why-attention-needs-context.md
  04-self-attention-qkv.md
  05-transformer-block.md
  06-original-transformer-encoder-decoder.md
  07-transformer-architecture-variants.md
  08-decoder-only-generation.md
  09-kv-cache-context-cost.md
```

### 新增关键桥梁

#### 06 Original Transformer: Encoder and Decoder

目标：

- 解释原始 Transformer 的 Encoder / Decoder 分工。
- 解释 source sequence 和 target sequence。
- 解释 Decoder 为什么既需要 masked self-attention，又需要 cross-attention。
- 为后面的三种架构范式建立心智模型。

#### 07 Architecture Variants

目标：

- 从原始 Encoder-Decoder 结构出发解释三种裁剪：
  - Encoder-only：保留理解侧。
  - Encoder-Decoder：保留输入到输出转换链路。
  - Decoder-only：保留自回归生成侧。
- 解释 BERT、T5、GPT 分别适合什么任务。
- 连接到 RAG embedding/rerank、翻译/摘要、对话/工具调用。

#### 08 Decoder-only Generation

目标：

- 在读者已经理解 Decoder 的前提下讲自回归生成。
- 解释 next-token prediction、causal mask、logits、解码策略。
- 不再承担解释 Encoder-only / Encoder-Decoder 的主要责任。

#### 09 KV Cache and Context Cost

目标：

- 单独讲 KV Cache、prefill、decode、上下文长度、延迟和显存。
- 避免在 Decoder-only 章节里一次塞太多推理优化内容。

## 面试材料生成规则

只有当系统学习章节完成后，才写对应 review note。

Review note 来源规则：

- 30 秒答案来自系统学习章节的核心结论。
- 2 分钟展开来自系统学习章节的机制解释。
- 追问来自系统学习章节的误区和工程连接。
- 项目连接来自系统学习章节中的应用场景。
- 每个 review note 必须链接回对应系统学习章节。

如果某个 review note 需要解释一个系统主线没有讲过的概念，说明系统主线缺课，应先补系统文档。

## 验收标准

一条主线合格需要满足：

- 从头读到尾，不连续出现 3 个未解释的新概念。
- 每篇只解决一个主要学习问题。
- 新概念出现前有动机，出现后有最小心智模型。
- 表格只用于总结，不能替代解释。
- Foundation 链接能解决真实卡点。
- Review notes 看起来像复习，而不是第一次学习。
- 学习者读完主线后，能说清自己懂了什么、不懂什么、该去哪补。

## 对当前已完成样板的处理

当前已合并的 Transformer 样板不废弃，但视为第一版素材，不视为最终系统学习版。

需要调整：

- `05-decoder-only-and-generation.md` 中的 Encoder-only / Encoder-Decoder 补丁要拆出来，变成独立系统章节。
- `README.md` 学习路径要更新为更细的 9 篇结构。
- `03-self-attention-qkv.md` 可改名或前置新增 `03-why-attention-needs-context.md`，避免直接进入公式。
- `09-review-notes/03-transformer-core-cheatsheet.md` 暂时保留，但后续要根据新系统主线重新校准。

## 实施顺序

第一阶段只重做 Transformer 系统学习链路：

1. 更新 `04-transformer-foundations/README.md`。
2. 新增或拆分 Attention 动机章节。
3. 新增原始 Transformer Encoder/Decoder 章节。
4. 新增三种架构范式章节。
5. 拆分 Decoder-only 与 KV Cache/成本章节。
6. 重新校准 Transformer review note。

第二阶段再做面试路径：

1. 新增 `interview-paths/ai-engineer-transformer.md`。
2. 明确 2 周冲刺和系统学习两条路径。
3. 把 review note 作为复习入口，而不是学习入口。

第三阶段再迁移 RAG/Agent 等应用模块。

## 成功信号

这次重做成功时，学习者读到 Decoder-only 时应该已经知道：

- Transformer 最初为什么有 Encoder 和 Decoder。
- Encoder、Decoder、cross-attention、causal mask 分别解决什么问题。
- BERT、T5、GPT 为什么不是孤立名词，而是三种架构选择。
- Decoder-only 为什么适合通用生成、对话和工具调用。
- RAG 里的 embedding/rerank 为什么经常更接近 Encoder-only 用法。

只有达到这个状态，再写面试路径和面试笔记才不会让学习者心里没底。
