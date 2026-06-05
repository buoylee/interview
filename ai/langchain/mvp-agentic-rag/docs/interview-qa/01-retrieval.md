# 面试 Q&A — 检索子系统

> 本篇聚焦本项目的检索实现(hybrid+RRF+rerank,Postgres 单库双用)。不重写概念,只讲「在本项目里怎么做、怎么答」,并指向仓库已有文档。

---

## Q1: 为什么选 hybrid search(向量+全文),而不是纯向量检索?

**答案要点**

- 向量检索擅长语义相似,对同义词、措辞变换鲁棒;但对精确关键词(产品名、错误码、版本号)准确度低。
- BM25/tsvector 全文检索在精确词匹配上表现稳定,但完全不理解语义。
- 两路互补:hybrid 同时发出两路 query,分别拿回 dense top-K 和 sparse top-K,再 RRF 融合——比任意单路 recall 更高。
- 本项目用 Postgres 的 `pgvector` 做 dense,`tsvector` + `to_tsquery` 做 sparse,一张表搞定,不需要维护 Elasticsearch 第二套存储。

**深挖追问**

- "如果让你改成只用向量呢?" — 可以,但精确词命中率会下降;若知识库里有大量数字/代码/专有名词,用户投诉率会明显上升。
- "为什么用 Postgres 而不是 Elastic + Pinecone?" — 见 ARCHITECTURE.md §四「决策表」:单库降运维复杂度、pgvector HNSW 性能生产可用、checkpoint 也在同一个库。

**常见误区**

- 误认为 hybrid 一定要两套数据库。本项目用 Postgres 一库双列(`embedding vector`, `content tsvector`),无需 Elastic。
- 误认为 hybrid = 简单拼接结果。拼接会引入重复 chunk,必须经 fusion(RRF)去重并重新排序。

**仓库概念文档**

- `ai/rag-lab/03-hybrid-rerank-debugging.md` → hybrid 检索 debug 方法
- `ai/ml-to-llm-roadmap/01-rag-retrieval-systems/03-hybrid-search-rerank-context.md` → hybrid + RRF + rerank 系统方法论

---

## Q2: RRF 是怎么融合两路检索的?为什么不调权重?

**答案要点**

- RRF 公式:`score(d) = Σ 1 / (k + rank_i(d) + 1)`,k=60(本项目默认)。
- 每一路排名里,同一个 chunk 按其在该路的 rank 贡献 `1/(60+rank+1)` 分;多路得分相加后降序。
- **不调权重的原因**:权重需要 labeled 数据才能科学调整;没有标注集时调权重是过拟合风险极高的超参数;RRF 靠排名位置而非绝对分数合并,在无标注场景下经实验证明鲁棒性强。
- 具体实现:`retrieval/fusion.py` — `reciprocal_rank_fusion(rankings, k=60)`,函数只有 8 行,无任何外部依赖。

**深挖追问**

- "k=60 是怎么来的?" — 论文实验值,实践中 k 在 [30, 120] 变化对最终结果影响不大。如果想调,需要 recall@K 标注集来评估。
- "有没有比 RRF 更好的 fusion?" — 有:学习型 fusion(LambdaMART 等)在有标注集时效果更好;RRF 是无监督 baseline,足够好且零成本。

**常见误区**

- 误认为 rank 从 1 开始。本项目实现 `enumerate(ranking)` 从 0 开始,公式变为 `1/(k+rank+1)`,等价于论文的 `1/(k+rank)`(rank 从 1 起),无影响。
- 误认为要对向量分和 BM25 分做归一化后加权。归一化后加权是另一种 fusion 策略(linear combination),需要权重超参,不是 RRF。

**仓库概念文档**

- `ai/rag-lab/03-hybrid-rerank-debugging.md` → 融合策略与调试

---

## Q3: rerank 解决什么问题?为什么放在 RRF 之后?

**答案要点**

- hybrid+RRF 是 **recall 阶段**:目标是不漏,返回 top-20 或 top-50。向量/BM25 分都是粗粒度近似。
- rerank 是 **precision 阶段**:用 cross-encoder 对 `(query, chunk)` 逐对打细分,把真正相关的 chunk 排到前面。cross-encoder 比双塔向量精度高但速度慢,不能全库扫——必须先 recall 压缩候选集。
- 本项目 `retrieval/rerank.py`:对 top-N 候选调用 reranker(可配置 Cohere API 或本地 cross-encoder)。
- 最终送给 LLM 的只有 rerank 后 top-K(K<N),直接影响 faithfulness。

**深挖追问**

- "cross-encoder 比双塔向量为什么精度高?" — cross-encoder 把 query 和 doc 拼在一起做完整的 attention 交互;双塔模型分别 encode,丢失了 query-doc 细粒度交叉信息。
- "如果 reranker 很慢怎么办?" — 缩小 recall 候选集(从 top-50 降到 top-20 再 rerank),或换更小 cross-encoder 模型,或本地离线推理。

**常见误区**

- 误认为 rerank 就是"再搜一次"。rerank 是对已有候选集重新打分排序,不发新的检索 query。
- 误认为 rerank 能补全未被 recall 到的 chunk。recall 漏掉的 chunk rerank 也找不回来——问题要在 recall 阶段解决(调 top-N、改 hybrid 策略)。

**仓库概念文档**

- `ai/ml-to-llm-roadmap/01-rag-retrieval-systems/03-hybrid-search-rerank-context.md` → rerank pipeline 方法论

---

## Q4: chunk_size 和 overlap 怎么调?有什么实验方法?

**答案要点**

- `chunk_size` 太小:chunk 缺乏上下文,语义碎片化,向量表示质量差。
- `chunk_size` 太大:一个 chunk 混入多个主题,检索时噪声大,送给 LLM 的 context 稀释。
- `overlap` 作用:防止一个句子被切断到两个 chunk 的边界导致语义断裂;建议 10-20% 的 chunk_size。
- 调参实验方法:固定 query set → 改 chunk_size → 跑 `context_recall`(ragas 指标,见 04-eval.md)→ 选 recall 最高且 context 长度可控的参数组合。
- 本项目实现:`ingest/splitter.py`,通过 `CHUNK_SIZE` / `CHUNK_OVERLAP` 环境变量控制,默认 512/50。

**深挖追问**

- "如果文档是代码文件,chunk 策略是否不同?" — 是。代码应按语法边界(函数/类)切割,不按固定字符数;可用 `RecursiveCharacterTextSplitter` 的 language 参数。
- "多层 chunk 策略(parent-child)解决什么?" — 用小 chunk 检索(精准召回)、返回大 chunk 给 LLM(完整上下文);本项目 MVP 未实现,是「下一步」。

**常见误区**

- 误认为 overlap 越大越好。overlap 过大导致大量重复存储,检索到同一内容多次,RRF/rerank 浪费计算。
- 误认为只要调大 chunk_size 就能解决语义不完整问题。LLM context window 有限,chunk 过大会把 top-K 直接撑满。

**仓库概念文档**

- `ai/rag-lab/08-chunking-tuning-playbook.md` → chunk 调参实战 playbook

---

## Q5: 中文全文检索为什么需要 pg_jieba?现在是什么状态?

**答案要点**

- PostgreSQL 的 `tsvector` 默认用空格分词。中文没有空格,`to_tsvector('simple', '向量检索')` 会把整个词组当一个 token,导致无法匹配子词(如"检索")。
- `pg_jieba` 是 Postgres 的结巴分词扩展,接入后 `to_tsvector('jieba', '向量检索')` → `['向量', '检索']` 两个 token,全文检索才真正可用。
- **本项目现状**:使用 `simple` 分词器(ASCII 友好,中文基本不可用)。中文知识库若要生产可用,需要在 Postgres 镜像中编译安装 pg_jieba,并修改 `core/db.py` 的 `to_tsvector` 配置。
- 这是已知边界(MVP),列在 PROJECT-NARRATIVE.md §下一步会做什么。

**深挖追问**

- "不用 pg_jieba,有没有其他方案?" — 有:① 在 ingest 阶段用 Python jieba 分词后存储 token 列表;② 只依赖向量检索做语义匹配,放弃稀疏路;③ 换 Elasticsearch + ik analyzer。
- "pg_jieba 安装麻烦吗?" — 需要和 Postgres 版本匹配编译或用预编译 Docker 镜像,生产可用但有运维成本。

**常见误区**

- 误认为英文 simple 分词器在中文下"凑合能用"。能存储,但查询几乎全部失效,等于 hybrid search 退化为纯向量。
- 误认为 pg_jieba 是唯一方案。Python 端分词后存 `tsvector` 也可以,在 ingest 阶段就已经拆好了。

**仓库概念文档**

- `ai/rag-lab/03-hybrid-rerank-debugging.md` → 检索 debug,含分词问题排查
- `ai/rag-lab/08-chunking-tuning-playbook.md` → 文本处理与分词策略
