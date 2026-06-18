# 09 · small-to-big 动手 lab（两种实现 + 量化）

## 这个 lab 证明什么

两件事，都用数字说话：

1. **small-to-big > 朴素固定切块** —— 拿到「小块的检索准」+「大块的上下文全」。
2. **LlamaIndex 的 `AutoMergingRetriever` ≈ 30 行裸 Python** —— 同一个策略，框架不是魔法，可移植到你自己的栈。

配套理论：[高级检索策略：当 hybrid+rerank 还不够](../../ml-to-llm-roadmap/01-rag-retrieval-systems/03b-advanced-retrieval-strategies.md)。这个 lab 就是把那篇里的 small-to-big 跑出来。

## 核心思想（一句话）

> 用**小块**做检索（embedding 准、命中精确），命中后把它所在的**大块（整节）**还给 LLM（上下文全）。检索粒度和喂给模型的粒度，本来就不必是同一个。

## 怎么跑

```bash
# 方式一：纯本地冒烟，零依赖（只验证管线 + 看完整度/字数对比）
LAB_EMBEDDER=lexical python3 run.py

# 方式二：真实语义（推荐，能看出 small vs big 的召回差异）
pip install -r requirements.txt
python3 run.py          # 默认 bge；首次会下载 bge-small-zh 模型(~100MB)，之后离线可跑

# 改 top-k
LAB_K=3 python3 run.py
```

全程**零 API key**：embedding 用本地 `bge-small-zh`，量化只用 Recall/MRR（不需要 LLM）。

## 实际输出（`LAB_EMBEDDER=lexical` 冒烟，本机实跑）

```
配置                          Recall@5     MRR      完整%       平均ctx字数
baseline_small                  100%    0.98       0%           174
baseline_big                    100%    1.00     100%           504
small_to_big (portable)         100%    1.00      96%           402
```

怎么读：

- **baseline_small**：检得准（Recall/MRR 高），但**完整% = 0**——只还了答案那一段，整节的上下文丢了。
- **baseline_big**：**完整% = 100**，但 **ctx 字数 504**——噪声和成本都上去了。
- **small_to_big**：Recall 同 small，**完整% 96**（≈big），**字数 402**（比 big 省）——两头都要到。
- portable 这行就是裸 Python 实现；装好依赖后会多出 `small_to_big (LlamaIndex)` 一行，与它**接近**——这就是「框架不是魔法」。

> ⚠️ lexical 模式是**词法匹配冒烟**：语料小、关键词好命中，所以四个配置的 Recall 都顶到 100%，看不出召回差异。**真正的 small vs big 召回差距要在 `bge` 语义模式下才显现**——大块把多个话题揉在一起，section 向量被「稀释」，针对某个细节的 query 反而排不上去；小块的向量更聚焦，召回更稳。完整%/字数的对比两种模式都成立。

## 代码结构

| 文件 | 作用 |
|---|---|
| `corpus.py` | 虚构知识库（doc→section→段落两层结构） |
| `golden_set.py` | 24 条 query + 答案落在哪节哪段 |
| `chunking.py` | 切小块(段落)/大块(整节)，记父子关系 |
| `embedder.py` | 可插拔 embedder：`bge`(语义) / `lexical`(纯标准库) |
| `retrievers.py` | **裸 Python** 三个检索器（baseline_small / baseline_big / portable_small_to_big） |
| `llamaindex_way.py` | **LlamaIndex** 的 `AutoMergingRetriever` 等价实现 |
| `run.py` | 跑全部配置、算指标、打表 |

## 两种实现，同一个策略

**裸 Python（`retrievers.py`）** —— 在小块上检索，数同一父节命中了几个子块，够 `merge_min` 个就「上卷」整节，否则只还小块：

```python
hits_per_parent = 数候选池里每个父节命中了几个子块
for c in 按相关度排好的小块:
    if hits_per_parent[parent_of[c]] >= merge_min:
        上卷 → 还整节(去重)
    else:
        还这一小块
```

**LlamaIndex（`llamaindex_way.py`）** —— 一样的思路，换成框架封装好的件：

```python
parser = HierarchicalNodeParser.from_defaults(chunk_sizes=[256, 128, 64])  # 大/中/小三层
retriever = AutoMergingRetriever(base_retriever, storage_context)          # 命中够多自动上卷
```

两者跑出来的 Recall / 完整% 接近 —— **策略可移植，不必为了它迁框架**。

## 把它搬进你的栈（LangGraph）

你的 agentic RAG MVP 是 LangGraph 骨架，不用换。要这个能力时，两条路：

- **借组件**：把 `AutoMergingRetriever`（或 LangChain 的 `ParentDocumentRetriever`）当一个 retriever，包进 LangGraph 的检索节点。
- **裸实现**：`retrievers.py` 那 30 行直接抄进你的节点，配你现在的向量库（命中小块 → 回查 `parent_id` → 还父块）。

参见 [§8 三层分工](../../ml-to-llm-roadmap/03-nlp-embedding-retrieval/03-retrieval-theory.md#8-工程实现这条流水线谁帮你做了)：重活在向量库和模型，框架只是胶水。

## 动手延伸

- 改 `retrievers.py` 的 `merge_min`（1 = 永远上卷，等于 LangChain `ParentDocumentRetriever`；调大 = 更保守），看完整%/字数怎么变。
- 在 `bge` 模式下对比 small vs big 的 Recall@3，亲眼看大块的「语义稀释」。
- 给 `golden_set.py` 加几条**跨段**的 query（答案需要同节好几段），看 small-to-big 的完整%优势更明显。
- 进阶：加一路 sub-question（复合问题先拆再检），对照 03b 笔记。

## 回到主线

- 策略全景与「何时用哪个」：[03b 高级检索策略](../../ml-to-llm-roadmap/01-rag-retrieval-systems/03b-advanced-retrieval-strategies.md)
- 加了策略怎么证明真有用：[RAG 评估、幻觉与生产排查](../../ml-to-llm-roadmap/01-rag-retrieval-systems/04-rag-evaluation-debugging.md)
