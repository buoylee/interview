# 12.7 Hybrid Search 与 Rerank

> **轨道**：B core
>
> **目标**：能解释现代搜索系统为什么常用 BM25 + vector + rerank，而不是只靠单一检索方式。

Hybrid Search 不是“把向量搜索接到 ES 上”这么简单，而是把 lexical retrieval、semantic retrieval、粗排融合、业务约束和精排模型放进一条可观测、可回滚、可控成本的链路。资深候选人要讲清楚两点：第一，向量检索补的是 BM25 的语义召回短板，不是替代 BM25；第二，rerank 只能在小候选集上做更贵的判断，不能修复前面完全漏掉的候选。

面试里不要把 vector search 包装成银弹。商品搜索、日志检索、文档检索、客服知识库的 query 结构差异很大：有的强依赖品牌、型号、ID、错误码和数字约束，有的强依赖语义改写、同义表达和长文本理解。Hybrid 的价值是让不同召回器承担自己擅长的部分，再用 fusion 和 rerank 把候选排序成用户能接受的 TopK。

## 三阶段搜索架构

一个生产级 hybrid pipeline 通常先按阶段拆开，而不是把所有逻辑塞进一个巨大 query：

```text
candidate generation
-> score fusion / coarse ranking
-> rerank
```

三阶段的职责边界：

| 阶段 | 主要输入 | 主要输出 | 资深关注点 |
| --- | --- | --- | --- |
| candidate generation | query rewrite、tenant/status/category/time filter、BM25 query、embedding query | 多路候选 docID 和各自的原始分数、rank、召回来源 | recall 是否足够，候选是否被硬过滤保护，召回成本是否可控 |
| score fusion / coarse ranking | BM25 TopN、kNN TopN、业务轻量特征 | 去重后的候选列表和粗排顺序 | score normalization、fusion 稳定性、候选窗口大小、fallback |
| rerank | 粗排 TopK、query-doc 特征、业务规则、模型特征 | 最终 TopK 或分页窗口 | latency budget、模型成本、稳定性、可解释性、回滚 |

候选生成阶段要先做 guardrail：租户、权限、状态、时间范围、可售状态、内容安全等硬约束不能留给 rerank 才处理。否则向量召回可能带来“语义相似但不可见、不可买、无权限”的候选，后面排序再强也只是浪费延迟。

一个实用的候选规模可以这样估算：BM25 取 200 到 1000，vector kNN 取 100 到 500，融合后保留 200 到 800，再把 Top 50 到 200 送入 rerank。真实数值必须用离线 recall@K、NDCG@K、线上 P95/P99 latency 和成本共同决定，不能凭经验固定。

延迟预算要按阶段拆开，例如：

| 阶段 | 常见预算思路 | 超时策略 |
| --- | --- | --- |
| query rewrite / embedding | head query 可以缓存 embedding，tail query 设置模型超时 | embedding 失败则只走 BM25 |
| BM25 retrieval | 依赖倒排和 filter 收缩候选，通常是低成本主召回 | 慢查询触发 query guardrail 或降低扩召 |
| Vector retrieval | `dense_vector` + kNN/HNSW 需要内存、CPU 和候选窗口 | 超时则跳过 vector 分支 |
| score fusion | 去重、normalization、RRF 或加权合成 | 失败则返回 BM25 粗排 |
| rerank | 只处理小候选集，模型要 batch 和 deadline | 超时则返回 fusion 粗排 |

observability 要覆盖每一段：query 类型、召回模板版本、embedding 模型版本、BM25 candidate 数、Vector candidate 数、重叠率、fusion 后候选数、rerank 输入数、各阶段 latency、fallback 原因、cache 命中率、TopK 变化、线上点击和转化。没有这些日志，hybrid 出 bad case 时很难判断是召回漏了、融合错了，还是 rerank 把正确结果压下去了。

## BM25 Retrieval

BM25 Retrieval 是 lexical retrieval，核心优势是精确词面匹配、倒排执行效率和可解释性。它特别适合这些 query：

- 品牌、型号、SKU、订单号、trace id、错误码、IP、域名、包名、类名。
- 用户明确输入的关键词，例如“iPhone 15 Pro Max 256 黑色”、“NullPointerException at PaymentService”。
- 有强字段语义的搜索，例如 title、brand、category、tags、log_message。

BM25 的强项：

- 精确关键词强。用户输入的 token 和文档 token 能直接在 Posting List 里相遇，品牌、型号、ID、数字、错误码都容易解释。
- 可解释性强。可以通过 analyzer、matched field、term frequency、IDF、field length、boost、`explain` 或 profile 去追踪为什么某个文档得分高。
- 工程成本低。倒排检索是 ES/Lucene 的主路径，配合高选择性 filter、Doc Values 和 TopK collector，通常比模型检索更容易压延迟和成本。

BM25 的短板：

- 对语义改写和同义表达弱。“降噪耳机”和“通勤隔音蓝牙耳机”、“报销流程”和“怎么申请费用 reimbursement”可能词面重叠很少。
- 对 query rewrite 依赖很强。Analyzer、Synonym、拼写纠错、字段建模和 boost 没做好时，BM25 会把“召回问题”暴露成“排序问题”。
- 原始 `_score` 不能随意跨 query、跨召回器比较。BM25 score 受 query term、字段长度、IDF、boost 和匹配字段影响，不是概率，也不是天然归一化后的相关性。

面试中可以把 BM25 讲成 hybrid 的稳定底座：它负责保护 exact intent 和可解释性，尤其在 B 线搜索工程场景里，日志检索、商品型号、法务文档编号、企业知识库标题命中都不能交给纯语义模型兜底。

## Vector Retrieval

Vector Retrieval 是 semantic retrieval，核心思想是把 query 和文档编码成向量，通过向量相似度找语义接近的候选。ES 中常见建模方式是为文档保存 `dense_vector` 字段，用 kNN 查询做近邻检索；底层常见近似检索直觉是 HNSW 这类图索引。

HNSW 的面试直觉可以这样讲：

```text
文档 embedding
-> dense_vector 字段
-> 建立近邻图
-> 查询向量从图上逐步走向更相似的邻居
-> 返回近似 TopK
```

它不是精确扫描所有向量，而是在近邻图上做 approximate nearest neighbor search。图连边质量、构建参数、量化方式、`num_candidates`、segment 数、内存状态都会影响 recall、latency 和成本。常见参数直觉：

- `dims`：向量维度必须和 embedding 模型输出一致，换模型通常意味着新字段或重建索引。
- `similarity`：选择 cosine、dot product、l2 等相似度时要和模型训练方式匹配。
- `index_options`：HNSW 或量化 HNSW 用来换取查询性能和内存效率，但会引入构建成本和召回损失权衡。
- `k`：最终希望向量分支返回的近邻数量。
- `num_candidates`：近似搜索探索的候选窗口，调大通常提高 recall，但会增加 latency 和 CPU。

Vector 的优势：

- 语义召回强。用户说法和文档说法不一致时，embedding 可以把相近语义拉到一起。
- 对长文本、问答、知识库、跨语言或弱关键词场景有价值。
- 能补足 BM25 依赖词面重叠的弱点，尤其适合 tail query 和自然语言问题。

Vector 的风险：

- 对精确词、型号、ID、数字可能不稳定。`iphone 15` 和 `iphone 15 pro max` 语义接近，但商品搜索里可能是不同意图；`error 500` 和 `error 502` 语义相似，但日志排障里不能混。
- 成本和延迟更高。embedding 生成、向量索引内存、HNSW 构建、segment merge、kNN 查询、模型升级和多版本索引都会增加平台成本。
- 可解释性弱。向量分数只能说明 embedding 空间相似，不能像 BM25 一样解释具体命中了哪个词、哪个字段。
- 模型漂移会改变召回集合。embedding 模型、分词、语料分布或向量归一化方式变了，TopK 可能整体变化，必须有离线评估和灰度。

因此向量检索在生产里更像一个召回分支，而不是唯一排序依据。它要被硬过滤保护、被候选窗口限制、被 observability 记录，并且随时能 fallback 到 BM25。

## Hybrid Retrieval

Hybrid Retrieval 的核心是让 BM25 和 vector 互补：BM25 抓住精确词和结构化意图，vector 抓住语义相似和弱词面重叠。典型流程是并行召回、去重、融合、粗排：

```text
BM25 TopN
+ Vector kNN TopN
+ filters / business lightweight features
-> deduplicate by doc_id
-> score normalization / score fusion or reciprocal rank fusion
-> coarse TopK
```

候选生成要先回答三个问题：

1. 哪些 query 必须走 BM25 主导：品牌型号、ID、订单号、日志错误码、强短语、强过滤。
2. 哪些 query 需要 vector 扩召：自然语言问题、同义表达、长尾 query、低词面重叠 query。
3. 每个分支取多少 candidate：BM25 TopN、kNN `k`、`num_candidates`、融合后的 `rank_window_size` 和 rerank TopK 都要用评估数据调。

score normalization/fusion 是难点，因为 BM25 score、向量相似度和业务特征不是同一量纲。常见做法有三类：

| 方法 | 做法 | 优点 | 风险 |
| --- | --- | --- | --- |
| 规则优先 | exact match、brand match、category match 先保护，再让语义结果补位 | 简单、可解释、适合强业务约束 | 规则过多会压死语义召回，维护成本高 |
| score normalization + weighted fusion | 对 BM25、vector score 做 min-max、z-score、rank-based normalization 后加权 | 能表达不同分支权重，便于实验 | 分数分布随 query 变化，normalization 不稳会导致排序抖动 |
| reciprocal rank fusion | 不比较原始分数，只按各召回器名次累加 `1 / (rank_constant + rank)` | 稳健、容易解释，适合多路召回 | 无法表达强分数差距，权重和窗口仍要调 |

RRF 的直觉是：一个文档如果在多个召回器里排名都靠前，就应该更靠前；如果只在一个召回器里靠后，它的贡献较小。公式可以写成：

```text
rrf_score(doc) = sum over retrievers 1 / (rank_constant + rank_of_doc)
```

Elasticsearch 新版本提供过基于 retriever 的 RRF 组合方式，可以把 standard lexical retriever 和 kNN retriever 放进同一个 RRF 配置里，并通过 `rank_constant`、`rank_window_size` 控制融合行为。面试时不需要背完整 DSL，但要能说清楚：RRF 回避了 BM25 和向量分数不可比的问题，把 fusion 转成 rank 融合问题。

候选窗口会同时影响 recall、latency 和 cost：

- 窗口太小：vector 找到的语义好结果可能还没进入 fusion，rerank 没机会纠正。
- 窗口太大：kNN、去重、特征读取、rerank 模型调用都会变慢，P95/P99 更容易超预算。
- 多 shard 下每个 shard 的候选窗口和协调节点 reduce 都会放大成本。
- 个性化、权限、库存、地域等动态过滤越多，cache 命中越差，候选窗口越需要保守。

cache 不能只说“加缓存”。实用做法是分层：

- query rewrite、实体识别、拼写纠错和 embedding 生成可以对 head query 做短 TTL cache。
- 稳定 filter 可能受益于底层 bitset 或请求缓存，但高基数租户、个性化、滑动时间窗和权限条件通常复用率低。
- fusion 后的 TopK 可以对匿名、无个性化、强 head query 缓存，但必须把租户、权限、语言、地区、实验版本、模型版本纳入 cache key。
- rerank 特征可以缓存静态特征，例如商品质量分、内容权威度；实时库存、价格、用户特征要谨慎缓存。

fallback 设计要在上线前定义好：

- embedding 服务失败或超时：只走 BM25，并记录 fallback reason。
- vector index 延迟、segment 状态异常或 kNN 超时：跳过 vector 分支，保留 lexical 结果。
- fusion 配置异常：返回 BM25 粗排或上一个稳定 fusion 版本。
- rerank 模型失败、特征服务超时或超过 deadline：返回 fusion coarse ranking。
- query 被识别为强 exact intent：可以降低 vector 权重，必要时关闭 vector 分支。

evaluation 要同时看召回、排序和系统指标：

- 离线：recall@K、NDCG@10、MRR、TopK overlap、精确词 query bucket、语义 query bucket、tail query bucket、零结果 query bucket。
- bad case：记录 BM25-only、vector-only、hybrid、rerank 后的 TopK 对比，标注“召回漏了、fusion 错了、rerank 错了、业务规则错了”。
- 线上：CTR、CVR、GMV、改搜率、零结果率、退出率、P95/P99 latency、CPU、heap、向量内存、模型调用成本。
- 发布：shadow query 回放、离线评估、灰度 A/B、guardrail 指标、可按 query bucket 回滚。

## Rerank Stage

Rerank Stage 只处理候选集，不处理全量文档。它的职责是在 BM25、vector 和 fusion 已经给出可控候选后，用更贵的信号重新排序 TopK。典型输入是 50 到 200 个候选，而不是全索引百万级文档。

常见 rerank 方法：

| 方法 | 适合场景 | 主要风险 |
| --- | --- | --- |
| 业务规则 rerank | 库存、地域、权限、内容安全、强品牌保护、运营降权 | 规则膨胀后难解释，可能压过相关性 |
| ES `rescore` | Top window 内短语匹配、轻量字段组合、仍能用 ES query 表达的二阶段排序 | window 太小修不回来，window 太大影响 latency |
| Learning to Rank | 商品搜索、内容搜索、招聘搜索等有标注和行为数据的排序 | 特征质量、训练偏差、线上特征一致性 |
| Cross-encoder / reranker model | query-doc 语义匹配、知识库问答、长文本相关性 | GPU/CPU 成本高，batch、超时和稳定性要求高 |
| LLM reranker | 少量高价值候选、复杂语义判断、需要上下文推理的场景 | latency 和成本高，可重复性和可解释性弱，不适合大流量全量路径 |

rerank 的关键工程点：

- 候选必须来自前一阶段。rerank 不能修复 candidate generation 完全漏掉的文档。
- 输入窗口要稳定。Top 20 输出不代表只给模型 20 个候选，通常要给 50 到 200 个候选让它有纠错空间。
- 特征要版本化。query rewrite 版本、embedding 模型版本、fusion 版本、rerank 模型版本和业务规则版本都要记录。
- 模型要有 deadline。比如整体搜索 P95 目标是 300 ms，rerank 只能占其中一部分；超时要返回 coarse ranking。
- 批处理和并发要受控。逐文档调用模型会把 latency 打爆，常见做法是 query 内 batch、跨请求微批或轻重模型分层。
- 输出要可解释到工程层面。至少能看到 rerank 前后名次变化、主要特征、模型分数、规则命中和降级原因。

资深回答里要明确 ES `rescore` 和外部 rerank 的边界：`rescore` 适合仍能在 ES 内表达的轻量二阶段排序；外部 rerank 适合复杂模型、实时特征、跨服务特征和深度语义匹配。两者都不能替代前面的召回质量。

## Failure Modes

Hybrid search 的事故往往不是单点 bug，而是召回、fusion、rerank、模型和流量分布共同变化后的系统问题。

必须能识别这些 failure modes：

- vector recall misses exact terms。向量把语义相近但型号、数字、错误码不同的文档召上来，真正 exact match 反而被挤出候选。
- BM25 misses semantic matches。用户自然语言表达和文档词面不重合，BM25-only 出现零结果或弱相关结果。
- rerank latency too high。候选窗口过大、模型过重、特征服务慢、没有 batch 或 deadline，导致 P95/P99 超预算。
- score fusion unstable。BM25 score、vector score、业务分布随 query 变化，normalization 后排序抖动；某个分支偶然高分压过主意图。
- embedding drift。模型升级、语料变化、分词变化、向量归一化变化导致向量召回集合整体漂移。
- query distribution changes。流量从 head query 变成 tail query，或促销、热点、事故期间 query 类型变化，原来的权重和缓存策略失效。

其他常见问题：

- `num_candidates` 太小导致 HNSW 近似召回不足，离线看 Top10 还行，线上 tail query 漏召严重。
- filter 和 kNN 组合后候选过少，尤其是多租户、权限、地域、库存等强约束叠加时。
- RRF 的 `rank_window_size` 太小，某一路召回器的好结果在窗口外，无法参与 reciprocal rank fusion。
- 业务规则过强，把文本相关性和语义相关性都压到后面，用户看到的是“可卖但不相关”的结果。
- cache key 缺少实验版本、模型版本、权限或地区，导致跨用户或跨实验污染。
- 线上只看 CTR，不看 conversion、改搜率和投诉，可能把标题党或低质内容推高。

对应的治理动作：

- exact intent query 要保护 BM25、phrase、keyword、brand/model/id 字段，必要时对 vector 分支降权。
- semantic intent query 要允许 vector 扩召，并在评估集中单独看语义 query bucket。
- fusion 要先从 rank-based 方法或稳定的规则开始，再引入复杂 score normalization。
- rerank 必须设置输入窗口、batch、timeout、fallback 和模型版本灰度。
- embedding 和 rerank 模型升级必须双写或 shadow，对比召回差异、TopK 差异、NDCG、latency 和成本。

## 面试回答模板

### Q：为什么不直接用向量搜索替代 BM25？

可以按这条主线回答：

1. BM25 对精确词、品牌、型号、ID、日志关键词强。商品型号、订单号、错误码这类 intent 需要词面和字段级解释，不能只靠语义相似。
2. 向量对语义相似强，但精确约束和可解释性弱。它能补“说法不同但意思相近”的召回，但对数字、版本、型号、权限和业务硬约束不天然可靠。
3. hybrid 用两者互补。BM25 保护 exact intent 和低成本主召回，vector 补语义召回，再通过 score fusion、normalization 或 reciprocal rank fusion 合并候选。
4. rerank 在较小候选集上做更贵的排序。它可以用业务规则、LTR、cross-encoder 或 LLM/reranker 处理复杂相关性，但不能对全量文档执行，也不能修复前面完全漏召的文档。
5. 设计要平衡 recall、latency、cost 和 explainability。上线时要有候选窗口、缓存、fallback、observability、离线 evaluation 和线上 A/B，而不是把向量搜索当成 BM25 的替代品。

### Q：如何设计一个 BM25 + Vector + Rerank 的商品搜索？

可以这样回答：

1. 先做 query rewrite，识别品牌、型号、类目、属性、价格、地域和强 exact intent；租户、权限、上架、库存、地域可达作为硬 filter。
2. BM25 分支查 title、brand、model、category、attribute，保护 exact、phrase、keyword 子字段；Vector 分支用商品标题、属性和描述 embedding 做 kNN 语义召回。
3. 两路各取一批 candidate，按 doc_id 去重。对强型号 query 提高 BM25 权重，对自然语言 query 提高 vector 权重。
4. fusion 优先考虑 RRF 或 rank-based fusion，避免直接比较 BM25 raw score 和向量相似度；如果做 weighted fusion，必须说明 normalization 和按 query bucket 调权。
5. 粗排 Top 100 左右进入 rerank，模型或规则使用文本相关性、类目一致、库存、价格、销量、转化率、商家质量和个性化特征。
6. 生产化要设置 latency budget：embedding、kNN、feature fetch、rerank 都有 timeout；任何分支失败都能 fallback 到 BM25 或 fusion 粗排。
7. 评估用 offline NDCG/recall、bad case bucket、线上 CTR/CVR/改搜率和 P95/P99 latency；发布走 shadow、灰度和可回滚配置。

### Q：Hybrid Search 出 bad case 时怎么排查？

排查顺序不要直接调权：

1. 看 candidate generation：正确文档是否出现在 BM25 TopN 或 Vector TopN。没有出现就是召回问题，rerank 调不回来。
2. 看 fusion：正确文档进入候选后是否被 score normalization、RRF 窗口、业务轻量特征或去重逻辑压下去。
3. 看 rerank：比较 rerank 前后名次、模型分数、规则命中、特征缺失和超时降级。
4. 看 query bucket：这是 exact intent、semantic intent、tail query、拼写错误、跨语言，还是热点流量变化。
5. 看系统指标：阶段 latency、fallback、cache、embedding 版本、rerank 版本、feature service 错误率和 shard 级慢点。
