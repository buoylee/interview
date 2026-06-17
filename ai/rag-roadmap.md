# RAG 资深主线:从零到能上线、能排查、能讲清

> 这是一份**总纲**,不是又一篇新教程。它把仓库里散落在四处的 RAG 材料(原理、LangChain 实现、调试 Lab、生产 MVP)串成**一条能从头读到尾的河**:每走一段,你会知道「这一步为什么存在、脑子里该装什么、去哪篇深读、动手做什么、资深的差距在哪、做到什么算过关」。
>
> 读法:**先把这页从头到尾顺读一遍**(约 20 分钟),建立全景;再沿着九个阶段,每到一阶段才跳进对应的深读材料。读完整条线并做完 Capstone,你应该能在面试里讲清 RAG 的每一层,也能在真实系统里把「答案不对」定位到具体环节。

---

## 先看清地形:你手上其实有四簇 RAG 材料

很多人(包括过去的你)觉得"对 RAG 了解不够",真相往往不是材料少,而是材料**散落、重叠、各有入口、没有主线**。先把地形看清:

| 簇 | 位置 | 它负责什么 | 形态 |
|---|---|---|---|
| **① 原理簇** | [`ml-to-llm-roadmap/01-rag-retrieval-systems/`](ml-to-llm-roadmap/01-rag-retrieval-systems/) | 为什么、边界、判断力(**框架无关**) | 纯心智模型,零代码 |
| **② 实现簇** | [`langchain/08-rag-with-langchain.md`](langchain/08-rag-with-langchain.md) | 用 LangChain 组件把链路拼出来 | 可跑的代码片段 |
| **③ Lab 簇** | [`rag-lab/`](rag-lab/)(9 篇) | 拆黑盒 + 自建 mini RAG + 调参 + 调试 + 文件 Agent | 实验设计 + 失败用例 |
| **④ Capstone** | [`langchain/mvp-agentic-rag/`](langchain/mvp-agentic-rag/) | 生产形态可运行工程(CRAG/hybrid/pgvector/eval/obs) | `docker compose up` 一键跑 |

**它们的关系是分工,不是重复**:

```
① 原理   想清楚 RAG 是什么、该怎么判断          (脑子)
② 实现   同一套链路用 LangChain 怎么写出来        (手)
③ Lab    亲手把每个黑盒拆开、弄坏、定位          (眼睛 + 手)
④ MVP    把上面全部收敛成一个能上线的工程         (作品)
```

> **本主线的角色** = 这四簇的**脊柱**。它不重写任何一篇的内容,只负责把你**按正确顺序**带过去,并在每一步**点名两套教程都没讲的深水区**,作为你冲资深的自学锚点。

---

## 九个阶段速览(系统性一览)

| 阶段 | 一句话 | 主读 | 过关标准 |
|---|---|---|---|
| **1 想清楚** | RAG 的问题边界:何时用、何时根本不该用 | ① | 能说清 RAG vs 长上下文/微调/搜索/工具的分工 |
| **2 建库** | 文件 → 可召回片段(解析/chunk/metadata/embedding/index) | ①③② | 能打印每个 chunk,并解释切分对召回的影响 |
| **3 召回排序** | 让"最能回答"的证据靠前(sparse/dense/hybrid/RRF/rerank) | ①③② | 能解释为什么单一向量召回不够,且能跑 hybrid |
| **4 组装** | 把证据变成模型真看得懂的上下文(去重/压缩/排序/引用) | ①③ | 能解释 context assembly 为什么影响幻觉 |
| **5 调参** | 用 golden set + 指标 + 成本,**科学**定 chunk/top_k | ③ | 能用一张图选出 chunk_size/overlap,而不是拍脑袋 |
| **6 评估排查** | 把"答案不好"拆成可定位的失败类型 | ①③ | 能区分检索失败 vs 生成失败,并说出 trace 字段 |
| **7 托管 vs 自建 / Agentic** | file_search 边界、检索即 tool、CRAG 自纠正 | ③②④ | 能说清哪些交给托管、哪些必须自建 |
| **8 Capstone** | 把 MVP 真跑出数字 → 故意弄坏 → 排查定位 | ④③ | 有真实延迟/成本/faithfulness 数字 + 一次定位记录 |
| **9 收尾** | 资深自检清单 + 面试高频题映射 | 全 | 能把任意一道 RAG 面试题落回上面某一阶段 |

下面是每一阶段的展开。一段接一段读,它会像一条河把你带到终点。

---

## 阶段 1 · 想清楚:RAG 的问题边界

在碰任何代码之前,先在脑子里把一件事钉死:**RAG 不是让模型"更聪明",而是在回答前把可验证的外部证据放进上下文,并让回答受证据约束。** 知识会变、知识私有、回答要有依据——这三件事单靠训练记忆或长 prompt 都解决不好,RAG 才出现。

更值钱的是**边界判断**:RAG 解决"外部知识接入与 grounding",长上下文解决"单次输入容量",微调解决"行为/格式/领域表达",搜索解决"找到文档",Agent 解决"多步行动"。这五者会配合,但不能互相顶替——把这套边界讲利索,是中高级面试的高频送分题。

**主读** → ① [`01-rag-problem-boundary.md`](ml-to-llm-roadmap/01-rag-retrieval-systems/01-rag-problem-boundary.md)。
**动手做** → 暂时不写代码,只做一件事:拿一个你熟的业务(订单、工单、合同),写出"为什么它该用 RAG 而不是微调"的三句话。
**资深缺口(自学锚点)** → ㉠ 长上下文**什么时候真的赢了 RAG**(成本/延迟/"大海捞针"准确率的实际拐点,不是口号);㉡ RAG + 微调**混合**怎么分工(事实走检索、风格走微调);㉢ RAG 与 agentic tool-retrieval 的边界——固定检索 vs 让 LLM 自己决定要不要检索。
**过关标准** → 面试官问"这个需求该 RAG 还是微调还是长上下文",你能不背诵地分情况答清,并主动说出"这两者其实能配合"。

> 想清楚了"为什么",下一步才是"知识怎么进库"——这是 RAG 质量的上限所在。

---

## 阶段 2 · 建库:从文件到可召回片段

RAG 的第一步不是生成,是**把文件变成可检索的知识单元**。原始 PDF / 网页 / Notion 不能直接高质量进 prompt,要经过:解析 → 清洗 → chunk → 打 metadata → embedding → 建 index。这条离线链路的质量,基本决定了整个系统的天花板——**召回不到的证据,后面再强的模型也救不回来。**

这里最该建立的两个直觉:其一,**chunk 的核心矛盾是"语义完整 vs 噪声"**——太短会丢条件/例外/指代对象,太长会把多主题混在一起、稀释匹配、挤占 prompt;overlap 是为了别在切口处切断语义,但过大会制造重复。其二,**metadata 不是可有可无**——部门/日期/产品/权限的过滤,解决的是"语义相似但不该返回"这类向量永远分不开的问题。

**主读** → ① [`02-indexing-embedding-retrieval.md`](ml-to-llm-roadmap/01-rag-retrieval-systems/02-indexing-embedding-retrieval.md)(原理)→ ③ [`02-mini-rag-from-scratch.md`](rag-lab/02-mini-rag-from-scratch.md)(亲手从零搭,看清 chunk/id/score)→ ② [`08-rag-with-langchain.md`](langchain/08-rag-with-langchain.md) §二~五(用 LangChain 组件落地)。
**动手做** → 用 ③ 的 mini RAG 设计,加载一篇真文档,**打印出每一个 chunk 和它的来源**——亲眼看到"一段政策被切成了什么样"。
**资深缺口** → ㉠ **高级解析**:表格/代码/版式感知切分(为什么 PDF 表格直接 `RecursiveCharacterTextSplitter` 会废,layout-aware 解析在做什么);㉡ **embedding 选型与微调**:维度/语种/领域怎么挑(MTEB 怎么看)、什么时候值得在自己语料上微调 embedding;㉢ **向量库内部与运维**:HNSW 的 `M`/`ef` 与 IVF-PQ 的 `nlist`/`nprobe` 在权衡什么、加了 metadata 过滤后召回为什么会"性能塌陷"、增量更新与 reindex 怎么做。**(已展开 → [向量库内部:一个 chunk 怎么存、怎么被搜出来](ml-to-llm-roadmap/01-rag-retrieval-systems/02b-vector-store-internals.md))**
**过关标准** → 你能解释"这个回答错了,是不是 chunk 切坏了",并能动手换 chunk 策略重切重建。

> 库建好了,候选能召回了——但**第一次召回的 top-k 通常不够好**。下一阶段专治这个。

---

## 阶段 3 · 召回与排序:让最能回答的证据靠前

第一阶段检索只负责"找一批可能相关的候选",里面常混着重复的、过期的、只匹配了关键词但不回答问题的、语义相关但缺关键条件的片段。直接把 top-k 全塞进 prompt,模型会被噪声带偏甚至引错证据。所以要补两件事:**hybrid search**(关键词 + 向量信号互补)和 **rerank**(用更贵更准的 cross-encoder 在少量候选里重判"可回答性")。

要建立的直觉:**sparse(BM25)和 dense(向量)抓的是不同信号**——BM25 擅长 `SOC2`、`SKU-123`、`P0` 这种精确术语/编号,向量擅长同义改写;**RRF** 按排名融合两路,不依赖分数尺度;**reranker 不是"更贵的 retriever"**——retriever 面向大库要快,reranker 面向少量候选可以慢而精,把 query 和 chunk 一起读,因此更懂条件、否定和"到底答没答"。

**主读** → ① [`03-hybrid-search-rerank-context.md`](ml-to-llm-roadmap/01-rag-retrieval-systems/03-hybrid-search-rerank-context.md)(原理)→ ③ [`03-hybrid-rerank-debugging.md`](rag-lab/03-hybrid-rerank-debugging.md)(从能跑到能排查)→ ② [`08-rag-with-langchain.md`](langchain/08-rag-with-langchain.md) §七(`EnsembleRetriever` / `MultiQueryRetriever` / 压缩 / 父文档)。
**动手做** → 在你的 mini RAG 上加一路 BM25,用 RRF 融合,对同一个 query 对比"纯向量 vs hybrid"的命中差异——亲眼看到 BM25 救回了哪个被向量漏掉的精确术语。
**资深缺口** → ㉠ **查询理解**:HyDE、query decomposition、step-back prompting、multi-hop——当用户问法和文档写法差很远时怎么办;㉡ **reranker 选型**:`bge-reranker-v2`、Cohere Rerank、ColBERT late-interaction 各自的代价与收益;㉢ **过滤与召回的交互**:pre-filter vs post-filter 对召回率和延迟的影响。
**过关标准** → 你能解释"为什么单靠向量召回在企业文档里不稳",并能跑出一个 hybrid+rerank 的检索器。

> 证据排好了,但模型最终看到的,还取决于你**怎么把它们拼进 prompt**。

---

## 阶段 4 · 组装:把证据变成模型真看得懂的上下文

`context assembly` 是**独立的设计步骤**,不是"取 rerank 的 top-k 拼起来"。即使检索全命中,如果证据太多、顺序乱、引用丢了,模型照样幻觉。它至少要处理四件事:**去重**(近重复、同段多版本)、**压缩**(留下回答所需的句子,压掉背景)、**排序**(把主证据放在模型容易用到的位置)、**来源追踪**(保留标题/时间/段落/权限,才能引用)。

一个必须记住的现象是 **lost-in-the-middle**:长上下文里**中间位置**的信息最容易被模型忽略。所以上下文越长,越要管顺序——主证据放前面或贴近问题,补充证据合并摘要,冲突证据显式标注。

**主读** → ① [`03-hybrid-search-rerank-context.md`](ml-to-llm-roadmap/01-rag-retrieval-systems/03-hybrid-search-rerank-context.md) 后半(context assembly 原理)→ ③ [`05-chatgpt-like-file-agent.md`](rag-lab/05-chatgpt-like-file-agent.md)(注入策略:metadata-only / summary / full / chunks / map-reduce)。
**动手做** → 在你的 RAG 上**打印最终 prompt**,数一数塞了几条证据、顺序如何;再故意把主证据挪到中间,看回答会不会变差。
**资深缺口** → ㉠ **context budget 管理**:token 预算超了怎么有规则地裁剪;㉡ **untrusted content 隔离**:文档里藏 prompt injection 怎么防(文件内容标 untrusted、绝不进 system prompt);㉢ **注入策略矩阵**:小文件全文、大文件 map-reduce、精确问答只给相关 chunks——什么时候用哪种。
**过关标准** → 你能说清"检索命中了为什么还会幻觉",并能指出 lost-in-the-middle 的缓解手段。

> 到这里,一条**能跑**的 RAG 已经成型。但"能跑"和"调到好"之间,隔着一套科学方法——这就是实战量化的第一块。

---

## 阶段 5 · 调参:用数据科学地定 chunk 与 top_k

前面你已经会"切 chunk",但 `chunk_size=500 / overlap=50` 是哪来的?如果答案是"教程抄的",那还没到资深。资深的做法是:**建一个 golden set(代表性问题 + 期望证据),用 retrieval 指标 + answer 指标 + 成本,把不同参数跑成一张可比较的表**,然后**选点**,而不是拍脑袋。

这是你**第一次把"实战"变成"数字"**:同一份语料,扫 `chunk_size × overlap × top_k` 的网格,看 recall@k 和 faithfulness 怎么变、延迟和成本怎么涨,在准确率和成本之间画条线选个点。

**主读** → ③ [`08-chunking-tuning-playbook.md`](rag-lab/08-chunking-tuning-playbook.md)(chunk 调参手册,本阶段的核心)。
**动手做** → 给你那篇文档造一个 5~10 题的小 golden set,跑 3 种 `chunk_size`(如 256/512/1024),把 recall@k 和成本填进一张表,**写下你选了哪个、为什么**。
**资深缺口** → ㉠ 把网格搜索**自动化**(脚本扫参数,而不是手动改);㉡ 把"准确率↑ / 延迟↑ / 成本↑"**画在同一张图**上选拐点,而不是只看单指标。
**过关标准** → 面试官问"chunk_size 怎么定",你不背区间,而是答"我用 golden set 扫一遍,在 recall 和成本之间选点",并能说出你实测的结论。

> 会调参之后,真正的工程能力是:当系统答错时,你能**定位是哪一段错了**。这是把 RAG 当系统、而非脚本来对待的分水岭。

---

## 阶段 6 · 评估与排查:把"答案不好"拆成可定位的失败类型

RAG 即使不报错也会答错,而且**错在不同环节、修法完全不同**。资深的关键能力是:把"答案不好"拆成可定位、可回归、可修复的**失败类型**——`no-hit`(根本没召回)、`wrong-hit`(召回了错证据)、`partial-hit`(只召回一半、丢了例外)、`stale`(命中过期文档)、`unsupported`(答案没被上下文支持)、`citation-mismatch`(引用对不上主张)、`context-overload`(证据太杂被忽略)。

配套的两层心智:**评估要分开看"证据找对没"和"答案忠实没"**。retrieval 层看 recall@k / precision@k / MRR / NDCG;answer 层看 correctness / faithfulness / citation accuracy / answer relevancy。**correctness ≠ faithfulness**——答案可能符合真实世界但没被当前上下文支持,也可能忠实复述了过期文档却与最新事实不符。修复时按链路定位:`no-hit` 多半改 ingestion/chunk/metadata/retriever,`wrong/partial-hit` 改 hybrid/rerank,`unsupported/citation-mismatch` 改 prompt/组装/grounding 检查。

**主读** → ① [`04-rag-evaluation-debugging.md`](ml-to-llm-roadmap/01-rag-retrieval-systems/04-rag-evaluation-debugging.md)(评估与失败分类的原理)→ ③ [`06-rag-file-agent-test-cases.md`](rag-lab/06-rag-file-agent-test-cases.md)(可回归的失败用例集)。
**动手做** → 给你的 RAG **故意制造一次 `partial-hit`**(删掉 golden set 里某条关键证据),跑一条完整 trace:`question → retrieved → reranked → final context → answer → 判定 → 失败类型`,确认你能指到"错在检索漏了边界"。
**资深缺口** → ㉠ **自建 LLM-as-judge**:写 rubric、防 judge 偏差,以及 RAGAS 的 faithfulness/context-precision 内部怎么算;㉡ **生产监控**:线上抽样 trace、按失败类型统计、检测文档漂移与 prompt 回归;㉢ 把失败类型做成 **regression set + dashboard**,防止改一处崩一处。
**过关标准** → 给你一个错误回答 + trace,你能在一分钟内说出"这是 retrieval 失败还是生成失败、属于哪一类、该改哪一层"。

> 现在你已经掌握自建 RAG 的全链路。但现实里还有一条岔路:很多能力(file_search、托管 RAG)厂商已经替你做了——什么时候用它、什么时候必须自己来?

---

## 阶段 7 · 托管 vs 自建 / Agentic RAG

OpenAI `file_search`、LlamaIndex 这类托管/封装方案能处理索引、检索、部分排序和 citation,但它们**不负责你的产品状态**:session/project/library 的 scope、active files、资源解析、权限过滤、业务 metadata、trace/eval。所以资深的结论是:**托管后端可以当 `RetrievalProvider`,但 Resource Registry、Resolver、Context Policy 和 Trace 必须由你自己的 runtime 掌握**——接口保持统一,避免被锁死。

另一条进阶线是 **Agentic RAG**:把"检索"从固定一步变成**交给 LLM 决定的 tool**(参见 ② 中 Retriever vs Tool 的对比——RAG 是"我替 LLM 提前查好",Tool 是"LLM 自己说要查我才查")。再往上是 **CRAG / self-RAG** 这类自纠正模式:检索质量不行就改写查询、换源、再检一轮。

**主读** → ③ [`04-file-search-vs-self-managed-rag.md`](rag-lab/04-file-search-vs-self-managed-rag.md) + [`07-implementation-roadmap.md`](rag-lab/07-implementation-roadmap.md)(自建文件 Agent 的分阶段实现)→ ② [`08-rag-with-langchain.md`](langchain/08-rag-with-langchain.md)(Retriever vs Tool 那节)→ ④ MVP 的 `kb_rag` 子图(CRAG 落地)。
**动手做** → 画一张"能力边界表":左边 `file_search` 托管了什么,右边你的 runtime 必须自管什么。
**资深缺口** → ㉠ 何时该 **agentic**(让 LLM 决定检索)、何时固定流程更稳更省;㉡ CRAG/self-RAG 的自纠正循环怎么设计、怎么防止无限重试;㉢ 托管方案的**锁定成本**与迁移路径。
**过关标准** → 面试官问"为什么不直接用 file_search 就好",你能答清它托管了哪几步、哪几步永远得你自己做。

> 所有零件你都见过了。最后一步,也是把你和"只会讲 RAG 的人"区分开的一步:把它**真跑起来,弄坏,再修好**。

---

## 阶段 8 · Capstone:把 MVP 跑出数字 → 故意弄坏 → 排查定位

这是整条线的临门一脚,也是**你之前一直缺的那块实战**。仓库里的 [`mvp-agentic-rag`](langchain/mvp-agentic-rag/) 已经是生产形态(hybrid+RRF+rerank、pgvector、CRAG 自纠正、HITL、可观测、可 eval、`docker compose up` 一键跑),**但它从没用真 key 跑过——`eval/reports` 还是空的。** 读一百遍 RAG,不如把这个跑出一组真实数字。

三步走,缺一不可:**①跑出基线**——配好 key,`make ingest && make serve && make eval`,拿到真实的 p50/p95 延迟、每查询 token 成本、faithfulness/context-precision 分数;**②故意弄坏**——按阶段 6 的失败类型注入故障(切坏 chunk 造 `partial-hit`、关掉 rerank 造 `wrong-hit`、塞过期文档造 `stale`);**③排查定位**——从 trace/Langfuse 里把每次失败定位到具体环节,记录下来。

**主读 / 动手** → ④ [`mvp-agentic-rag/README.md`](langchain/mvp-agentic-rag/README.md) 的 Quickstart 跑通;失败用例直接复用 ③ [`06-rag-file-agent-test-cases.md`](rag-lab/06-rag-file-agent-test-cases.md)。
**资深缺口** → ㉠ 让数字**可信**:固定 regression set、多次取均值、区分冷热缓存;㉡ 把"延迟 / 成本 / 质量"做成一页可对外讲的结论;㉢ 写一段"我把它弄坏又修好"的故障复盘——这正是面试里最有说服力的部分。
**过关标准** → 你手里有**一组自己跑出来的真实数字** + **至少一次"从现象定位到环节"的完整记录**。到这一步,你对 RAG 的了解才真正从"读过"变成"做过"。

> 跑完 Capstone,回头做最后一件事:用一份清单确认自己真的到位了。

---

## 阶段 9 · 收尾:资深自检 + 面试题映射

### 资深自检清单(能不假思索地答出来,才算过关)

- [ ] 这个需求该用 RAG / 长上下文 / 微调 / 搜索 / Agent?为什么?它们怎么配合?(阶段 1)
- [ ] chunk 太大太小分别坏在哪?metadata filter 解决什么向量分不开的问题?(阶段 2)
- [ ] 为什么单靠向量召回不稳?BM25/dense/RRF/rerank 各补什么?(阶段 3)
- [ ] 检索都命中了为什么还会幻觉?lost-in-the-middle 怎么缓解?(阶段 4)
- [ ] chunk_size 怎么定?——能答"用 golden set 扫一遍选点",并拿出实测结论。(阶段 5)
- [ ] 一个错误回答,怎么判断是检索失败还是生成失败、属于哪一类、改哪一层?(阶段 6)
- [ ] file_search 托管了什么、你必须自建什么?什么时候上 agentic/CRAG?(阶段 7)
- [ ] 你的 RAG 系统的延迟/成本/faithfulness 是多少?——能报真实数字。(阶段 8)

### 面试高频题 → 阶段映射(任何题都能落回某一段)

| 高频题 | 落在阶段 |
|---|---|
| RAG 和微调/长上下文怎么选 | 1 |
| chunk_size / overlap 怎么设 | 2 + 5 |
| 为什么要 hybrid search / rerank | 3 |
| 检索命中了为什么还幻觉 | 4 |
| RAG 怎么评估 / 怎么排查答错 | 6 |
| Retriever 和 Tool 有什么区别 | 7 |
| 讲一个你做过的 RAG 项目 | 8(用你的真实数字 + 故障复盘讲) |

---

> **掌握这条主线后,你应该能**:把 RAG 从"接个向量库"升级成一套**可解释、可评估、可排查、能上线**的工程;面试里任何一道 RAG 题都能落回某一阶段不慌不背;手里有一个自己跑出过数字、弄坏过又修好的真实系统当作品。这,就是 RAG 的资深线。
