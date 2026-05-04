# 12.5 搜索质量与相关性工程

> **轨道**：B core
>
> **目标**：从“会写 Query DSL”提升到“能治理搜索质量”：召回、排序、评估、实验和发布。

搜索相关性不是把 BM25 的 `k1`、`b` 或几个字段 `boost` 调到“看起来更顺眼”。资深搜索工程师要先定义业务场景和用户意图，再设计召回、排序、评估、实验和发布闭环。一个改动如果不能说明提升了哪些 query、伤害了哪些 query、是否影响延迟和成本、能不能灰度和 rollback，就不能算相关性工程。

面试里要把搜索质量讲成一条工程链路：

```text
用户意图
-> Analyzer / Synonym / mapping
-> Query Rewrite
-> 召回策略
-> 初排评分
-> rescore / rerank
-> 离线评估
-> online A/B
-> 灰度发布和回滚
```

## 搜索质量不是一个分数

搜索质量要拆成离线相关性指标、线上用户行为指标、业务指标和系统约束。只看一个分数会误导决策：CTR 上升可能来自标题党，conversion 下降可能说明用户点了但买不了；NDCG 提升可能只覆盖 head query，tail query 零结果率却变高。

常用指标要分层理解：

| 指标 | 含义 | 典型用途 | 主要风险 |
| --- | --- | --- | --- |
| `precision` | 返回结果里相关结果的比例 | 控制误召回、垃圾结果、低质内容 | precision 高可能只是返回太少，伤害 recall |
| `recall` | 应该被找到的相关结果里实际被找到的比例 | 解决漏召、零结果、同义词和长尾 query | recall 高可能带来噪声，压低排序质量 |
| `NDCG` | 结合人工等级和位置折扣的排序质量 | 评估 TopK 顺序是否合理，适合对比 ranker | 依赖标注集质量，不能直接代表业务收益 |
| `CTR` | 曝光后点击率 | 快速观察线上吸引力和用户选择 | 容易被位置、图片、标题、价格、补贴影响 |
| `CVR` / `conversion` | 点击或搜索后的转化 | 商品搜索、交易搜索的核心结果指标 | 转化受库存、价格、履约、促销、支付链路影响 |
| GMV / revenue | 搜索带来的交易规模 | 商品搜索排序和运营策略 | 可能牺牲相关性、公平性和长期体验 |
| 零结果率 | query 没有返回结果的比例 | 发现 analyzer、Synonym、拼写、类目词问题 | 零结果低不代表结果准，可能是过度扩召 |
| 用户改搜率 | 用户短时间内重写 query 的比例 | 识别意图理解失败和结果不满意 | 需要区分自然探索和失败改搜 |
| 延迟与成本 | P95/P99、CPU、heap、QPS 成本 | 判断策略能否生产化 | 相关性提升如果成本翻倍，可能不能发布 |

离线评估要有 manual judgment sets（人工标注集），不能只靠一次 bad case 讨论。一个实用评估集至少包含：

- query 分层：head、torso、tail、零结果、高转化、高投诉、强品牌、强类目、拼写错误、地域/时间敏感 query。
- 文档分层：热门商品/内容、冷门但正确结果、下架/过期/低质结果、同名品牌、相似型号、近义词和歧义词。
- 标注等级：例如 0=无关，1=弱相关，2=相关，3=高度相关；商品搜索还要标注可买性、库存、价格带和类目一致性。
- TopK 约束：分别看 Top1、Top3、Top10、Top20，因为用户体验主要被前几屏决定。
- 回归集：把线上事故、投诉 query、人工 bad case 固化，任何相关性发布都要跑回归。

资深回答要强调：离线 `precision`、`recall`、`NDCG` 是解释和筛选方案的工具，线上 `CTR`、`conversion`、GMV、改搜率和留存才证明业务影响。两者不能互相替代。

## Analyzer 与 Synonym 治理

Analyzer 决定“用户词和文档词能不能见面”。相关性问题很多不是排序问题，而是分词、归一化、字段建模和 Synonym 治理问题。中文搜索尤其要关注误切、过切和漏召：

- 误切：`苹果手机壳` 被切成不符合业务意图的组合，导致品牌、品类或配件关系混乱。
- 过切：短词被切得太碎，`小米13` 变成普通词组合，召回大量不相关商品。
- 漏召：`羽绒服`、`鸭绒外套`、`冬季外套` 没有建立业务可接受的词关系。
- 混淆：品牌、型号、类目、属性词混在同一个 text 字段里，排序时无法区分权重。

Analyzer 设计要从字段和意图开始：

- 标题字段：通常保留中文分词、精确词、拼音或前缀子字段，用于召回和输入联想，但不同子字段权重要分开。
- 品牌字段：更适合 keyword、归一化后的 brand id 或受控词表，不应完全依赖全文分词。
- 类目字段：用 category id、路径和叶子类目做过滤或强特征，避免只靠标题词猜类目。
- 型号字段：要保留大小写、数字、连字符、空格和别名规则，`iPhone 15 Pro Max`、`iphone15pm`、`15 promax` 不能只按自然语言处理。
- 内容正文：需要考虑分词粒度、停用词、长文本相关性、字段长度归一化和高亮成本。
- 日志字段：多数检索是 keyword、structured fields 和时间范围过滤，不能把所有字段都当 text。

index-time synonym 和 query-time synonym 的取舍：

| 方案 | 优点 | 风险 | 适合场景 |
| --- | --- | --- | --- |
| index-time synonym | 查询简单，召回稳定，运行时成本低 | 词表变更通常需要 reindex；错误扩展会污染索引，回滚成本高 | 稳定、少变、领域共识强的同义词 |
| query-time synonym | 词表可更快发布，能按场景、类目、用户意图控制 | 查询变复杂，可能放大召回和延迟；规则冲突更容易在线上暴露 | 高频迭代、运营词、类目相关同义词、实验策略 |

Synonym 最大风险是“看似召回，实际误召回”。例如把 `apple` 扩成 `苹果` 在数码类目可能合理，在水果、生鲜、音乐内容或日志字段里可能完全错误。同义词不能只按词面维护，要绑定业务域、类目、语言、地区和 query 意图。

发布流程要工程化：

1. 词表变更先进入评审：新增、删除、单向/双向、适用类目、示例 query、预期收益和风险 query。
2. 离线跑评估集：看 `recall` 是否提升，`precision` 和 `NDCG` 是否被误召回伤害。
3. shadow query：用生产 query 回放新 analyzer 或新 Synonym，不影响用户，只记录召回差异、TopK 差异、延迟和错误。
4. 小流量灰度：先对低风险流量或指定 query bucket 开启，观察零结果率、CTR、conversion、改搜率、P95/P99。
5. 可回滚：query-time 规则要能按版本关闭；index-time 规则要保留旧索引 alias 或双索引切换路径。

拼音、前缀、纠错和停用词也要谨慎：

- 拼音召回适合输入联想和中文品牌，但全量搜索里容易把短拼音打爆，必须限制字段、权重和 query 类型。
- 前缀、edge n-gram、search_as_you_type 可以改善输入中间态，但会增加索引体积和误召回，需要和完整词匹配区分权重。
- 纠错不能盲目替换原 query。安全做法是保留原词召回，同时追加纠错候选，且只在置信度足够时提升。
- 停用词在通用语料中有用，但在商品、型号、法律、医学、日志场景里可能删除关键 token。

## Query Rewrite

Query Rewrite 是把用户输入转成可执行搜索意图的过程。它不是简单字符串替换，而是在保护相关性、性能和安全边界的前提下组织查询。

常见 rewrite 层次：

1. 用户词归一化：大小写、全半角、繁简、标点、空白、单位、货币、特殊符号、品牌别名、型号格式。
2. 意图识别：识别类目、品牌、型号、属性、价格、地域、时间、新旧程度、问题类型和日志字段。
3. 同义词扩展：按领域和类目控制扩展方向，避免把交易词、内容词、日志词混用。
4. typo tolerance：拼写纠错、编辑距离、键盘邻近、拼音错误、数字/字母漏写；要限制在可解释范围内。
5. 查询结构生成：把 must、should、filter、minimum_should_match、短语匹配、精确匹配和弱召回组织成模板。
6. 危险模式拦截：禁用无边界 wildcard、regexp、过宽时间范围、深分页、大 size、高成本 sort、script query 和无租户过滤。

一个商品搜索 query 可以被 rewrite 成：

```text
raw query: "iphone15 pm 256 黑"

normalized:
- brand: Apple
- model: iPhone 15 Pro Max
- storage: 256GB
- color: black
- category intent: mobile phone

retrieval:
- filter: category_id = phone, status = online, tenant_id = current tenant
- must/should: title/model exact match, title analyzed match, alias synonym match
- business constraints: in_stock, deliverable_region
- ranking features: text score, brand authority, sales, conversion, price competitiveness, freshness
```

Query Rewrite 的核心风险是规则互相覆盖。比如品牌识别把 `荣耀` 识别为品牌后，内容搜索里“王者荣耀攻略”又可能是游戏实体；日志搜索里 `error code 404` 不能被当成自然语言纠错。工程上要把 rewrite 结果记录到日志里，至少包括原 query、归一化结果、识别出的实体、触发规则、召回模板版本和实验版本，方便 bad case 追溯。

面试里可以这样说：Query Rewrite 是相关性的第一道治理层。它决定召回候选是否合理，也决定高成本查询是否被挡住；它的发布要走离线评估、shadow query 和 A/B，不应该由运营规则直接全量上线。

## Relevance Toolbelt

ES 相关性工具箱要按阶段使用：先用 filter 缩小候选，再用全文查询召回，再用字段权重和特征排序，最后对 TopK 做 `rescore` 或外部 rerank。不要把所有逻辑塞进一个巨大 bool query。

### `multi_match` 类型选择

`multi_match` 适合一个用户 query 匹配多个字段，但类型选择会影响召回和得分解释：

- `best_fields`：适合多个字段语义相近但只希望最佳字段主导，例如 title、subtitle；底层常可理解为每个字段竞争，最强字段得分主导。
- `most_fields`：适合多个分析方式共同贡献，例如 title 的标准分词、英文 stem、拼音或 shingles 子字段；风险是字段越多分越高，需要控制权重。
- `cross_fields`：适合人名、品牌+型号、结构化短字段，多个字段共同表达一个意图；要注意 analyzer 一致性和字段语义一致性。
- `phrase` / `phrase_prefix`：适合强顺序意图、输入联想和短语精确性，但可能降低 recall 或增加成本。
- `bool_prefix`：常用于 search-as-you-type 类体验，适合输入未完成时的候选召回。

字段权重不能凭感觉写死。可靠做法是用评估集对 title、brand、category、attribute、body、tag 等字段分别调权，看 TopK 的 `NDCG`、bad case 和延迟变化。

### `dis_max` 和 tie breaker

`dis_max` 适合“多个字段都能命中，但最好的那个字段最重要”的场景。`tie_breaker` 允许其他字段提供少量加分，避免只看单一字段。

典型用途：

- title 命中应明显强于 description 命中。
- brand exact 命中应强于品牌词只出现在正文。
- 型号 exact 命中应强于模糊 token 命中。

风险是 tie breaker 过高会让“很多弱字段都命中”的文档超过“一个核心字段强命中”的文档。面试中可以说：`dis_max` 不是为了无脑加分，而是为了在字段竞争和多字段佐证之间取平衡。

### boost

`boost` 是最容易被滥用的工具。它适合表达明确的业务或字段优先级，例如品牌 exact、标题短语、类目一致、库存可售、地域可达，但不适合掩盖召回错误。

使用 boost 的原则：

- 先修 recall 和误召回，再调 boost；候选集错了，排序调不回来。
- boost 要能解释：哪个字段、哪个规则、哪个业务特征、预期影响哪些 query。
- boost 要有范围：不要让业务特征完全压过文本相关性，除非这是明确的运营策略。
- boost 要可实验：不同 query 类别可能需要不同权重，不能只看几个 head query。

### `rank_feature`

`rank_feature` 适合把静态或半静态数值信号加入相关性，例如 pagerank、商品质量分、内容权威度、商家信誉、历史转化率、热度。它比脚本打分更适合常见正向特征，但前提是特征定义稳定、取值分布可控。

注意事项：

- 特征要有业务含义，不能把所有数值字段都塞进 ranking。
- 要做归一化或分桶，否则超大值会压倒文本相关性。
- 要监控数据新鲜度，过期热度会让结果变成历史偏见。
- 要区分 query independent feature 和 query dependent feature；后者通常需要外部特征服务或 rerank。

### `function_score`

`function_score` 用于在文本相关性基础上叠加函数、权重、衰减、随机或字段值因子。常见场景：

- 商品搜索：库存、销量、毛利、价格竞争力、商家等级、地域履约、活动状态。
- 内容搜索：发布时间衰减、作者权威、互动质量、内容安全等级。
- 本地生活：距离衰减、营业状态、评分、可预约时间。

风险是 `function_score` 很容易把“相关”变成“商业排序”。资深工程师要明确 score 合成策略：

- `score_mode` 和 `boost_mode` 如何组合文本分与业务分。
- 每个特征是否有上限、下限、缺失值处理和异常值处理。
- 哪些规则是硬过滤，哪些规则只是软加分。
- 是否会伤害长尾、新品、冷启动或公平性。

### `rescore`

`rescore` 适合在每个 shard 的 Top window 上做第二阶段重排，例如用短语匹配、复杂字段组合或更贵的 scoring query 精排前几百个候选。它的价值是把昂贵逻辑限制在较小候选集里，降低全量查询成本。

使用 `rescore` 时要关注：

- `window_size` 太小会漏掉本该上来的候选，太大会增加延迟。
- rescore 只处理候选窗口，不能修复前一阶段 recall 不足。
- 多 shard 场景下要理解 rescore 和最终 reduce 的顺序影响。
- 上线前要同时看 `NDCG`、P95/P99、CPU 和 search thread pool。

### rerank 与 ES rescore 的边界

ES `rescore` 是搜索请求内部的二阶段重排，适合短语、字段权重、轻量特征和仍能在 ES 内表达的逻辑。外部 rerank 通常用于更复杂的模型，例如 learning to rank、cross-encoder、LLM reranker、query-doc 深度特征、实时用户特征或多路召回融合。

边界判断：

| 方案 | 适合 | 不适合 |
| --- | --- | --- |
| ES `rescore` | TopK 内轻量精排、短语匹配、字段组合、延迟敏感场景 | 需要复杂模型、实时个性化特征、跨服务特征的排序 |
| 外部 rerank | 商品个性化、语义精排、混合召回融合、复杂 LTR | 候选过多、延迟预算极小、特征不可观测或不可回滚 |

一个稳健 pipeline 通常是：

```text
filter
-> lexical recall: multi_match / dis_max / phrase / synonyms
-> optional semantic recall
-> business feature scoring: rank_feature / function_score
-> rescore TopK
-> optional external rerank
-> logging for evaluation and A/B attribution
```

## Product Search、Content Search、Log Search 差异

不同搜索场景的“相关”含义不同，不能用同一套指标和排序逻辑。

| 维度 | Product Search | Content Search | Log Search |
| --- | --- | --- | --- |
| 用户目标 | 找到可购买、可比较、可信的商品 | 找到满足信息需求的文章、帖子、文档或答案 | 找到故障证据、时间线和精确日志 |
| 核心指标 | `recall`、`precision`、`NDCG`、`CTR`、`conversion`、GMV、加购率、零结果率 | `NDCG`、停留时长、满意点击、收藏、分享、改搜率、低质内容率 | 查询成功率、延迟、过滤准确性、时间范围命中、可解释性、成本 |
| Analyzer 重点 | 品牌、类目、型号、属性、同义词、拼音、纠错 | 标题、正文、标签、实体、语义、语言和内容质量 | keyword、message、service、trace id、status、host、timestamp |
| Synonym 风险 | 误扩展会带来错误商品和低转化 | 误扩展会带来语义漂移和低质内容 | 同义词通常弱，错误 rewrite 可能破坏精确排障 |
| 排序特征 | 文本相关性 + 销量 + 库存 + 价格 + 履约 + 商家质量 + 个性化 | 文本/语义相关性 + 新鲜度 + 权威度 + 互动质量 + 安全 | 时间倒序、严重级别、服务、trace、精确字段过滤 |
| 发布风险 | GMV、库存、履约、商家公平性 | 内容生态、低质内容、标题党、时效性 | 故障定位失败、查询变慢、审计不准确 |

商品搜索重业务排序和转化，但必须保护文本相关性。用户搜“iPhone 15 原装充电器”，不能因为某个高毛利充电器销量高就排到明显不相关商品前面。

内容搜索重语义和相关性，更容易引入向量召回、实体识别和 rerank，但要防止标题党、重复内容、过期内容和低质量内容被行为指标放大。

日志搜索重过滤、时间范围和可解释性。排障场景里用户通常知道服务、时间、trace id、错误码或关键词，系统应优先保证精确过滤、稳定延迟、字段可解释和低成本，不应过度做自然语言扩展。

## A/B Test 与发布

相关性发布要把“离线有效”和“线上有效”分开。离线评估能降低上线风险，但不能证明业务收益；线上 A/B 能证明用户行为变化，但需要足够样本、稳定实验和清晰回滚条件。

发布链路：

1. 定义问题：是漏召、误召回、排序不稳、零结果、CTR 下滑、conversion 下滑、投诉 query，还是延迟成本问题。
2. 建离线评估集：从 query log、点击、转化、人工 bad case、客服投诉、运营词表和高价值 query 抽样。
3. 人工标注：用统一规范标注相关性等级，必要时多人标注并处理分歧；保留 query、doc、类目、品牌、库存和上下文。
4. 离线指标：看 `precision`、`recall`、`NDCG@K`、零结果率、TopK 覆盖、bad case 回归和延迟估算。
5. shadow query：生产 query 同时跑旧策略和新策略，只记录差异，不影响用户。
6. 小流量 A/B Test：按用户、session、query bucket 或租户稳定分流，避免同一用户来回跳实验。
7. 指标观察：同时看相关性、业务、系统和风险指标，不只看 CTR。
8. 灰度扩大：从 1% 到 5% 到 10% 到 50% 再全量，每一步有停留时间和退出条件。
9. rollback：保留旧策略、旧词表、旧索引 alias、旧模型版本和配置开关；触发条件明确后自动或人工回滚。

需要观察的指标：

- 相关性：`NDCG` 回归集、bad case 数量、零结果率、TopK 差异、改搜率。
- 用户行为：`CTR`、长点击、短点击、跳出、收藏、加购、二次搜索。
- 业务：`conversion`、GMV、订单数、客单价、履约失败、售后。
- 系统：P95/P99、timeout、rejected、CPU、heap、query cache、search thread pool、下游 rerank 服务延迟。
- 风险：投诉率、低质内容曝光、下架商品曝光、权限/地域/库存错误、实验样本偏斜。

回滚条件要提前写清楚，例如：

- P95 或 P99 超过基线 20% 并持续 15 分钟。
- timeout、search rejected 或 rerank 服务错误率超过阈值。
- 零结果率、改搜率或投诉 query 数显著上升。
- `conversion`、GMV 或关键类目指标显著下降。
- 发现权限、库存、下架、合规或日志审计错误。

资深工程师还要能说明归因。一次 A/B 里同时改 Analyzer、Synonym、Query Rewrite、boost 和 rerank，很难判断收益来自哪里。更好的做法是分层实验：先做召回安全性，再做排序特征，再做 rerank；每层都记录版本和命中规则。

## 面试回答模板

### Q：搜索结果不准，你怎么优化？

我会先把“不准”拆开，而不是直接说调 BM25 或加 boost。

1. 先定义“不准”：是 `recall` 不够、`precision` 低、排序不对、误召回、零结果、用户改搜、`CTR` 下降，还是 `conversion` 和业务指标下降。不同问题对应不同修复层。
2. 收集证据：拿 query log、曝光、点击、加购、转化、改搜、零结果、投诉、人工标注和 bad case；把 query 分成 head、tail、品牌、类目、型号、长句、错别字和高价值 query。
3. 定位层次：判断问题来自 Analyzer、Synonym、mapping、Query Rewrite、召回模板、字段 boost、`function_score`、`rescore`、业务特征、库存/权限过滤，还是外部 rerank。
4. 离线和线上分开：先用 manual judgment sets 评估 `precision`、`recall`、`NDCG@K` 和 bad case 回归，再用 shadow query 看召回差异和延迟，最后上小流量 A/B Test 看 `CTR`、`conversion`、GMV、改搜率、零结果率和系统成本。
5. 发布要可灰度、可观测、可回滚：规则、词表、索引 alias、模型和排序配置都要有版本；一旦延迟、误召回、零结果、业务指标或合规指标触发阈值，就按预案 rollback。

如果是商品搜索，我还会补一句：商品搜索不是只追文本相关性，还要考虑可售、库存、价格、履约、商家质量和转化，但这些业务特征不能把明显不相关的商品推上来。相关性工程的目标是让用户意图、候选召回、排序特征和业务目标在可评估、可发布、可回滚的框架里统一起来。

### Q：同义词上线后 CTR 上升但转化下降，怎么判断？

我不会直接认为同义词有效。`CTR` 上升说明结果可能更吸引点击，但 `conversion` 下降说明点击后的满足度或商品可买性可能变差。

排查顺序：

- 看实验分桶是否稳定，排除活动、价格、库存、流量来源和类目结构变化。
- 对比新旧策略 TopK，抽样人工标注，确认是否出现误召回或类目漂移。
- 拆 query 类型：品牌词、类目词、型号词、泛需求词、错别字和长尾 query 是否表现不同。
- 检查 Synonym 规则是否双向扩展过度，是否跨类目扩展，是否把上位词和下位词当成完全等价。
- 看商品特征：点击高但无库存、价格不合适、履约不可达或低质量商家是否被推高。
- 如果误召回明确，先回滚或缩小规则适用范围；如果只是排序问题，再调整 boost、`function_score`、`rescore` 或 rerank 特征。

面试表达可以是：“CTR 和 conversion 冲突时，我会把它当成相关性和商业质量的冲突，而不是简单继续放量。先用人工标注和 TopK diff 找误召回，再按 query 类别和类目定位规则风险，最后用可灰度的词表版本或排序版本修复。”

### Q：为什么不能把相关性优化理解为 BM25 调参？

BM25 只是文本相关性的一部分。真实搜索质量还取决于 Analyzer、Synonym、Query Rewrite、mapping、字段权重、召回策略、业务特征、用户意图、库存权限、内容质量、rerank、离线评估和线上 A/B。

我会这样回答：

```text
先保证候选集合理：analyzer、synonym、rewrite、filter、召回模板。
再保证排序有依据：multi_match、dis_max、boost、rank_feature、function_score、rescore/rerank。
然后用指标闭环：precision、recall、NDCG、CTR、conversion、零结果率、改搜率、延迟成本。
最后用发布治理兜底：shadow query、小流量 A/B、观测、rollback。
```

所以资深搜索工程不是“调一个参数”，而是围绕领域意图建立可度量、可解释、可迭代、可回滚的相关性系统。
