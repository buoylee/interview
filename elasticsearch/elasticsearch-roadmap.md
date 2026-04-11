# Elasticsearch 系统学习路线（面试 + 工作实战）

> **定位**：你已有 ES 基础操作经验（CRUD、DSL 查询、分词、集群概念），本路线补齐深层原理、生产运维、性能调优和高频面试题，从核心概念一路打通到系统设计。

---

## 设计原则

本路线遵循三个原则：

1. **先"会用"再"懂原理"** —— 先掌握 Mapping、分词、查询、聚合这些"操作层"能力，再深入 Lucene 内部原理和集群机制。带着使用经验看原理，才知道"为什么需要这个优化"。
2. **前置依赖严格排序** —— 每个阶段的知识只依赖前面阶段已学内容。Mapping 是分词的前提，分词是查询的前提，查询是打分和聚合的前提。不允许"先学查询，回头再补 Mapping"。
3. **逐层加深而非一次到底** —— 同一个主题（如写入链路）在不同阶段以不同深度出现：阶段 1 只知"写入经过 primary → replica"，阶段 6 才深入到 translog/segment/refresh 的内部机制。
4. **每个阶段必须动手** —— 每个阶段末尾都有"动手实践"指引。学 ES 不动手等于没学——看过的原理会忘，跑过的查询会记住。建议本地 Docker 搭建 ES + Kibana 环境，全程在 Dev Tools 中练习。

---

## 全景路线图

```
阶段1          阶段2           阶段3           阶段4           阶段5
核心概念      → Mapping       → 分词与        → Query DSL    → 聚合
(概览层)        与数据建模      文本分析         深入            深入
(0.5周)        (1周)          (0.5周)         (1.5周)         (1周)

      ↓ 以上是"会用"层 ──── 以下是"懂原理"层 ↓

阶段6          阶段7           阶段8           阶段9           阶段10         阶段11
存储原理      → 集群架构      → 性能调优      → 数据同步      → 生产运维      → 面试串联
与读写链路      与高可用                         与架构集成        与高级特性
(1.5周)        (1周)          (1周)           (1周)            (1周)          (持续)
```

**总预计时间**：9.5-10.5 周（每天 1-2 小时）
**目标版本**：以 **ES 7.x** 为主线（目前生产环境最广泛），ES 8.x 差异在阶段 10 专门标注。

### 知识依赖关系

```
阶段1 核心概念 ─┬─→ 阶段2 Mapping ──→ 阶段3 分词 ──→ 阶段4 Query DSL ──→ 阶段5 聚合
               │      (数据建模)       │                 (含高亮)          │
               │         │             │                  │                │
               │         │ 字段类型决定  │ 分词方式决定       │ 查询与聚合      │
               │         │ 如何分词      │ 查询行为          │ 依赖 DocValues  │
               │         └─────────────┘──────────────────┘────────────────┘
               │
               └─→ 阶段6 存储原理 ──→ 阶段7 集群 ──→ 阶段8 性能调优 ──→ 阶段9 数据同步 ──→ 阶段10 生产运维
                     │                    │                │              与架构集成         与高级特性
                     │  Segment/translog   │  分片策略影响    │                │
                     │  解释了 NRT 和写入   │  性能上限        │  调优需要理解    │  理解 ES 在
                     └────────────────────┘────────────────┘  原理 + 集群     │  系统中的角色
                                                                              ↓
                                                                         阶段11 面试串联
                                                                       （贯穿所有阶段）
```

---

## 详细内容导航

| 阶段 | 文件夹 | 核心内容 | 前置依赖 |
|------|--------|---------|---------|
| **1** | [核心概念](./roadmap/01-core-concepts/) | ES 是什么 / 与 Lucene 的关系 / 倒排索引直觉 / 基本架构概览 / CRUD 回顾 | 无 |
| **2** | [Mapping 与数据建模](./roadmap/02-mapping/) | 字段类型 / text vs keyword / Nested vs Join / Multi-fields / 模板别名 / **索引设计模式** | 阶段1 |
| **3** | [分词与文本分析](./roadmap/03-analysis/) | Analyzer 三层架构 / IK 深入 / 自定义分词 / 同义词 / search_analyzer / Normalizer | 阶段2 |
| **4** | [Query DSL 深入](./roadmap/04-query-dsl/) | 全文 vs 精确 / Bool 组合 / BM25 / Function Score / 深度分页 / filter vs query / **高亮** | 阶段2 + 阶段3 |
| **5** | [聚合深入](./roadmap/05-aggregations/) | Bucket / Metric / Pipeline / 嵌套聚合 / 近似聚合 / Composite / Doc Values 与 Fielddata | 阶段4 |
| **6** | [存储原理与读写链路](./roadmap/06-storage-internals/) | Lucene 底层(FST/FOR/Bitmap) / Segment 生命周期 / refresh/flush/translog/merge / NRT / 写入读取全链路 | 阶段1-5 |
| **7** | [集群架构与高可用](./roadmap/07-cluster/) | 节点角色 / 分片路由 / 选主 / 脑裂 / 一致性模型 / 故障恢复 / 分片分配与再平衡 | 阶段6 |
| **8** | [性能调优](./roadmap/08-performance-tuning/) | 写入优化 / 查询优化 / JVM 与 GC / OS 调优 / 监控诊断 / 容量规划 | 阶段6 + 阶段7 |
| **9** | [数据同步与架构集成](./roadmap/09-data-sync/) | **MySQL↔ES 同步** / 双写 vs MQ vs CDC / Canal/Debezium / 一致性保障 / ES 在系统中的定位 | 阶段7 + 阶段8 |
| **10** | [生产运维与高级特性](./roadmap/10-production/) | ILM / 快照恢复 / 滚动升级 / 安全 / ELK 架构 / Suggester / Geo / 向量搜索 / ES 8.x | 阶段8 + 阶段9 |
| **11** | [面试串联](./roadmap/11-interview/) | Top 30 高频题 / 系统设计题 / ES vs 其他存储 / 项目叙述 / **常见反模式** | 全部 |

---

## 速通路线（只有 2 周时间）

> 按知识依赖链压缩，每天的学习不会出现"用到了还没学的概念"的情况。

### 第 1 周：从使用到原理

| 天数 | 内容 | 为什么这个顺序 |
|------|------|--------------|
| Day 1 | 核心概念回顾 + Mapping 字段类型 + text vs keyword + 索引设计模式 | **地基**：后面所有查询和分词行为都取决于字段如何映射 |
| Day 2 | 分词器三层架构 + IK + search_analyzer | **桥梁**：理解了映射和分词，才能预测查询行为 |
| Day 3 | Query DSL 全量 + filter vs query + BM25 打分 + 高亮 | **核心技能**：现在你知道 term 查 keyword 为什么要完全匹配了 |
| Day 4 | 聚合（bucket/metric/pipeline + 近似聚合）+ Doc Values | **数据分析**：搜索之后最常用的能力 |
| Day 5 | Nested vs Join + Index Template + Alias + Reindex | **数据建模**：生产环境必须会的设计决策 |
| Day 6 | 存储原理：Segment + refresh/flush/translog/merge + NRT | **内功**：现在你用过 ES 了，理解"为什么近实时"有直觉了 |
| Day 7 | 写入读取全链路 + 集群架构 + 分片 + 选主 + 脑裂 | **分布式**：写入读取链路串联 Segment 和集群 |

### 第 2 周：调优 + 数据同步 + 面试

| 天数 | 内容 | 为什么这个顺序 |
|------|------|--------------|
| Day 8 | 写入优化 + 查询优化 | **调优需要原理基础**，Day 6-7 刚学完 |
| Day 9 | JVM/GC 调优 + 慢查询诊断 + 容量规划 | 调优第二层 |
| Day 10 | MySQL↔ES 数据同步方案 + ELK 日志架构 | **面试高频**：几乎必问"数据怎么同步" |
| Day 11 | ILM + Scroll/Search After + Suggester + 向量搜索 | 生产特性 |
| Day 12-13 | Top 30 面试题 + 系统设计题 + 常见反模式 | 面试冲刺 |
| Day 14 | 项目叙述 + 查漏补缺 | 收尾 |

### 速通时可跳过

```
可跳过（时间充足再看）：
  - 多语言分词细节（除非面试国际化产品）
  - X-Pack 安全配置细节（了解概念即可）
  - Percolator、Geo 细节（除非业务涉及）
  - Lucene 底层数据结构细节（FST/FOR/Bitmap，面试很少考到这个深度）
  - ELK 全栈操作细节（Logstash/Kibana 了解架构即可）
```

---

下面是各阶段的详细大纲：

## 阶段 1：核心概念（0.5 周）

> 快速建立全局认知。你已有基础，本阶段目标是**统一心智模型**，为后续学习建立框架。

### 1.1 ES 是什么

- 定位：分布式搜索和分析引擎
- 与 Lucene 的关系：ES = Lucene 的分布式封装 + REST API + 集群管理
- Lucene 的能力与局限（不支持集群、API 复杂、只能 Java 使用）
- ES 如何解决这些问题

### 1.2 核心概念速览

- Index / Document / Field —— 类比但不等于 Database / Table / Column
- Shard / Replica —— 分片与副本的基本概念（细节留到阶段 7）
- Node / Cluster —— 节点与集群（细节留到阶段 7）
- 概念之间的关系图

### 1.3 倒排索引——建立直觉

- 正排索引 vs 倒排索引：为什么全文搜索需要"反着来"
- 倒排索引的基本结构：Term → Document List
- 简单的例子走一遍：文档写入 → 分词 → 建立倒排 → 检索匹配
- 底层数据结构细节（FST/FOR/Bitmap）**留到阶段 6**

### 1.4 CRUD 回顾（快速过）

- POST/PUT/GET/DELETE 的语义差别
- _bulk 批量操作
- _mget 批量获取
- 版本控制：_seq_no + _primary_term

### 面试高频题（本阶段级别）
- ES 和 Lucene 是什么关系？
- 什么是倒排索引？和 B+ 树有什么区别？
- 为什么全文搜索用 ES 而不用 MySQL？

### 动手实践
- Docker 启动一个单节点 ES + Kibana（`docker-compose`），后续所有练习基于此环境
- 在 Kibana Dev Tools 中完成 CRUD 全流程：创建索引、写入文档、查询、更新、删除、_bulk 批量操作

---

## 阶段 2：Mapping 与数据建模（1 周）

> **Mapping 是一切的基础**。字段类型决定了如何分词、如何查询、如何聚合。不先学 Mapping，后面的分词和查询都是"知其然不知其所以然"。本阶段同时覆盖索引级别的设计模式。

### 2.1 为什么 Mapping 要最先学

理解这个因果链：
```
字段类型(Mapping) → 决定是否分词(Analysis) → 决定查询行为(Query)
                 → 决定是否有 DocValues → 决定能否聚合/排序(Aggregation)
```

### 2.2 核心字段类型

- **text**：会分词，建倒排索引，用于全文搜索，**不能**直接排序/聚合
- **keyword**：不分词，整体建索引，用于过滤/排序/聚合，大小写敏感
- **数值型**：long / integer / double / float —— 自动建 BKD 树索引
- **日期型**：date，内部存为 epoch_millis
- **布尔型**：boolean
- **binary**：Base64 编码的二进制

### 2.3 text vs keyword 深入

- 同一个字符串字段，默认会同时生成 text 和 keyword 两个子字段（Multi-fields）
- `name` 用于 match 搜索，`name.keyword` 用于 term 过滤/排序/聚合
- 什么时候只用 keyword：状态码、枚举值、ID
- 什么时候只用 text：文章正文、评论内容
- 什么时候两者都要：商品名称、人名

### 2.4 复杂类型

- **object**：JSON 对象，字段会被扁平化（array of objects 会丢失关联性）
- **nested**：保持对象数组中各对象的字段关联性（内部每个对象是隐藏的独立文档）
- **flattened**：整个 JSON 对象作为一个 keyword 索引（节省映射但查询能力有限）
- **join**（Parent-Child）：文档间的父子关系（同一个 shard 内）

### 2.5 Nested vs Object vs Join 选型

| 维度 | Object | Nested | Join (Parent-Child) |
|------|--------|--------|---------------------|
| 关联性保持 | 丢失 | 保持 | 保持 |
| 查询性能 | 最快 | 中等 | 最慢 |
| 更新代价 | 低 | 高（整个文档重建索引） | 低（子文档独立更新） |
| 适用场景 | 简单嵌套 | 嵌套数组需要精确匹配 | 子文档频繁独立更新 |

### 2.6 特殊类型

- **geo_point / geo_shape**：地理位置
- **completion**：自动补全（基于 FST）
- **ip**：IPv4/IPv6
- **date_range / integer_range**：范围类型
- **dense_vector**：向量字段（ES 8.x KNN 搜索）

### 2.7 Dynamic Mapping

- ES 自动推断类型的规则（字符串 → text+keyword，数字 → long/float，等）
- dynamic 参数：true（自动添加字段） / false（忽略未知字段） / strict（拒绝未知字段） / runtime
- dynamic_templates：自定义推断规则

### 2.8 Multi-fields

- 同一字段建立多种索引方式
- 典型：`title`（text, 用于搜索）+ `title.keyword`（keyword, 用于排序/聚合）+ `title.autocomplete`（用 edge_ngram 分词, 用于自动补全）

### 2.9 索引模板与别名

- **Index Template**：自动为匹配模式的新索引应用 mapping 和 settings
- **Component Template**（ES 7.8+）：可组合的模板模块
- **Index Alias**：索引的别名，用于零停机切换、读写分离
- **Rollover**：配合 alias 实现时间序列索引自动滚动
- **Reindex**：跨索引迁移数据（修改 mapping 的唯一方式）

### 2.10 索引设计模式

> 阶段 2.1-2.9 是**字段级别**的设计，这一节是**索引级别**的设计。面试系统设计题几乎必考。

- **按时间分索引**：`logs-2024.01.01`、`orders-2024-w03`
  - 配合 Index Template 自动创建 + ILM 自动管理生命周期
  - 查询时用 alias 或通配符 `logs-2024.*` 覆盖多个索引
- **多租户索引设计**：
  - 方案 A：一个大索引 + routing 按租户分片 —— 管理简单，数据隔离弱
  - 方案 B：每个租户一个索引 —— 隔离性好，但索引数过多时 master 压力大
  - 选型依据：租户数量、数据量差异、隔离要求
- **宽表反范式设计**：
  - ES 不擅长 JOIN → 写入时提前把关联数据打平到一个文档
  - 例：订单文档包含用户名、商品名，而非存 user_id + product_id
  - 代价：数据冗余、更新需要同步多处
- **读写分离索引**：
  - 写入用 alias `products-write` → 指向当前活跃索引
  - 查询用 alias `products-read` → 指向已优化的索引（force merged）

### 面试高频题
- text 和 keyword 的区别？什么时候用哪个？
- Nested 和 Object 的区别？举个实际例子？
- ES 的 mapping 创建后能修改吗？如果需要修改怎么办？
- 如何设计一个电商商品的索引 mapping？
- Index Alias 有什么用？
- 日志类数据的索引怎么设计？（按时间分索引 + ILM）

### 动手实践
- 在本地 ES 上创建一个电商商品索引，包含 text+keyword 多字段、nested 类型的 SKU 数组、geo_point 门店坐标
- 创建 Index Template，验证新建索引自动应用 mapping
- 用 Alias + Reindex 模拟零停机修改 mapping

---

## 阶段 3：分词与文本分析（0.5 周）

> **为什么分词在 Query DSL 之前？** 因为 match 查询会对搜索词做分词，term 查询不会。如果你不知道一个 text 字段被怎么分词的，你就无法预测查询结果。分词是连接 Mapping 和 Query 的桥梁。
>
> 你已了解 IK 基础，本阶段重点是补齐 Analyzer 架构和 search_analyzer 这两个核心概念，不需要花太长时间。

### 3.1 分词在 ES 中的位置

```
写入时：文档字段值 → Analyzer → 分词后的 terms → 写入倒排索引
查询时：搜索关键词 → Analyzer → 分词后的 terms → 去倒排索引匹配

关键理解：写入和查询用的 Analyzer 可以不同！
```

### 3.2 Analyzer 三层架构

- **Character Filter**：分词前的预处理
  - html_strip：去除 HTML 标签
  - mapping：字符替换（如 & → and）
  - pattern_replace：正则替换
- **Tokenizer**：分词核心
  - standard：按 Unicode 分词
  - whitespace：按空格分词
  - keyword：不分词，整体作为一个 token
  - pattern：按正则分词
  - 第三方：ik_smart / ik_max_word
- **Token Filter**：分词后处理
  - lowercase：转小写
  - stop：去停用词
  - synonym：同义词
  - stemmer：词干提取（英文）
  - edge_ngram：前缀分词（自动补全场景）

### 3.3 IK 分词器深入

- ik_smart vs ik_max_word 的本质区别
  - ik_smart：最粗粒度切分，"中华人民共和国" → "中华人民共和国"
  - ik_max_word：最细粒度，"中华人民共和国" → "中华人民共和国"、"中华人民"、"中华"、"人民共和国"、"人民"、"共和国"、"共和"、"国"
- 选择策略：**索引时用 ik_max_word（增加召回率），搜索时用 ik_smart（提高精准度）**
- 自定义词典
  - 本地词典：IKAnalyzer.cfg.xml + 自定义 .dic 文件
  - 远程热更新词典：配置远程词典 URL，ES 定期拉取
- 词典优先级与冲突处理

### 3.4 索引时分词 vs 搜索时分词

- `analyzer`：索引时使用的分词器
- `search_analyzer`：搜索时使用的分词器（未指定时默认与 analyzer 相同）
- **为什么要不同？** 索引时用 ik_max_word 让更多 term 进入倒排索引；搜索时用 ik_smart 让搜索更精确
- 在 Mapping 中指定：
  ```json
  "title": {
    "type": "text",
    "analyzer": "ik_max_word",
    "search_analyzer": "ik_smart"
  }
  ```

### 3.5 自定义 Analyzer

- 在 index settings 中组合 char_filter + tokenizer + filter
- 典型自定义场景：
  - 拼音分词（pinyin 插件）
  - 边缘 n-gram 自动补全
  - HTML 内容搜索（先 strip HTML 再分词）

### 3.6 同义词与停用词

- synonym token filter：同义词配置文件 + 热更新
- stop token filter：英文停用词 + 中文停用词
- 同义词应该在索引时还是搜索时生效？（通常搜索时更灵活）

### 3.7 Normalizer

- 用于 keyword 字段的文本标准化（如 lowercase）
- 与 Analyzer 的区别：Normalizer 不分词，只做字符级转换
- 应用场景：对 keyword 做大小写不敏感的精确匹配

### 3.8 _analyze API

- 调试分词结果的利器
- 测试内置分词器 / 自定义分词器 / 指定字段的分词器

### 面试高频题
- Analyzer 的三层架构是什么？
- ik_smart 和 ik_max_word 的区别？生产中怎么选？
- 如何实现搜索"北京大学"也能搜到"北大"？（同义词）
- 索引时分词和搜索时分词可以不同吗？为什么？
- 如何给 ES 添加自定义词典？支持热更新吗？

### 动手实践
- 用 _analyze API 对比 standard / ik_smart / ik_max_word 对同一段中文的分词结果
- 创建一个自定义 Analyzer（html_strip + ik_max_word + synonym），绑定到索引字段上测试
- 对同一个字段设置不同的 analyzer 和 search_analyzer，观察搜索行为差异

---

## 阶段 4：Query DSL 深入（1.5 周）

> 现在你已理解 Mapping（字段如何索引）和 Analysis（文本如何分词），可以真正理解每种查询的行为了。

### 4.1 理解查询行为的关键——从 Mapping 和分词出发

**先建立这个理解框架，后面所有查询都用它来推导：**

| 查询类型 | 查询词是否分词 | 字段类型 | 行为 |
|---------|-------------|---------|------|
| term | 不分词 | keyword | 精确匹配，常用 |
| term | 不分词 | text | 查询词必须匹配分词后的某个 token |
| match | 分词 | keyword | 分词后的每个 token 都必须完全等于 keyword 值（基本没用） |
| match | 分词 | text | 分词后的 token 去倒排索引匹配（最常用的全文搜索） |

### 4.2 全文检索查询

- **match**：分词后 OR/AND 匹配（operator 参数）
- **multi_match**：多字段 match + best_fields / most_fields / cross_fields 策略
- **match_phrase**：分词但保持顺序和位置（position）
- **match_phrase_prefix**：match_phrase + 最后一个词前缀匹配
- **match_bool_prefix**：前缀搜索的优化版本（ES 7.2+）
- **query_string / simple_query_string**：支持 AND/OR/NOT 语法

### 4.3 精确匹配查询

- **term / terms**：不分词的精确匹配
- **range**：范围查询（gte/lte/gt/lt），支持日期数学表达式
- **exists**：字段是否存在
- **ids**：按文档 ID 查
- **prefix**：前缀匹配（只对 keyword 有意义，性能差）
- **wildcard**：通配符（? 单字符，* 多字符，性能差）
- **regexp**：正则匹配（性能差）
- **fuzzy**：模糊匹配（允许编辑距离内的拼写错误）

### 4.4 复合查询

- **bool**：组合多个条件
  - must：AND + 参与打分
  - filter：AND + **不打分 + 可缓存**（性能更好）
  - should：OR + 参与打分
  - must_not：NOT + 不打分
  - minimum_should_match：should 条件的最小匹配数
- **dis_max**：取多个查询中分数最高的（best fields 策略）
- **tie_breaker**：让 dis_max 中分数低的查询也部分参与打分
- **constant_score**：包装查询，固定分数（不计算相关性）
- **boosting**：positive 查询提升分数，negative 查询降低分数
- **function_score**：自定义打分函数（下一节详述）

### 4.5 相关性打分深入

- **BM25 算法**（ES 5.x+ 默认，替代了 TF-IDF）
  - 词频（TF）：term 在文档中出现的次数——**有上限饱和度**（vs TF-IDF 线性增长）
  - 逆文档频率（IDF）：term 在所有文档中出现的稀有度
  - 字段长度归一化：字段越短，相关度越高
  - 参数 k1（控制 TF 饱和速度，默认 1.2）和 b（控制字段长度影响程度，默认 0.75）
- **Function Score Query**：自定义打分
  - script_score：Painless 脚本计算分数
  - weight：固定权重
  - field_value_factor：用字段值影响分数（如用 popularity 字段加权）
  - decay functions（linear/exp/gauss）：距离衰减（如时间越近分越高、地理越近分越高）
  - score_mode / boost_mode：多个函数如何组合
- **Rescore Query**：在 Top-N 结果上二次精排
- **explain API**：调试打分过程，理解为什么某个文档排在前面

### 4.6 搜索执行流程

- **Query Phase**：coordinating node 广播请求 → 每个 shard 返回 from+size 的 doc_id + score → 协调节点合并排序
- **Fetch Phase**：协调节点向相关 shard 取回实际文档内容
- **深度分页问题**：from=10000, size=10 → 每个 shard 返回 10010 条 → 5 个 shard 就是 50050 条在内存排序
- **三种解决方案**：
  - **scroll**：游标遍历，适合一次性导出全量数据，不适合实时搜索
  - **search_after**：无状态分页，需配合排序字段，适合实时深度分页
  - **PIT (Point in Time)**：ES 7.10+，配合 search_after 保证一致性视图

### 4.7 高亮（Highlight）

> 高亮是搜索结果展示的基本能力，几乎每个搜索 UI 都会用，不是"高级特性"。

- **基本用法**：highlight 字段 + pre_tags/post_tags 自定义标签
- **三种高亮类型**：
  - plain（默认）：基于 Lucene 标准高亮，适合大部分场景
  - posting（需字段设置 index_options=offsets）：不需要重新分词，性能更好，磁盘消耗更少
  - fvh（Fast Vector Highlighter，需 term_vector=with_positions_offsets）：大字段（>1MB）性能最好
- **fragment_size**：高亮片段长度（默认 100 字符）
- **number_of_fragments**：返回几个高亮片段
- **多字段高亮**：require_field_match=false 可以高亮不在查询中的字段

### 4.8 查询上下文与优化

- **query context vs filter context**
  - query：计算相关性分数，不缓存
  - filter：不计算分数，结果自动缓存到 node query cache
  - **原则：不需要打分的条件一律放 filter**
- **routing 查询**：指定 routing 值，只查指定 shard
- **preference**：_local（本地优先）/ _prefer_nodes / custom value（避免 bouncing results）
- **profile API**：查看查询在每个 shard 的各阶段耗时

### 面试高频题
- match 和 term 的区别？各自什么场景用？
- filter 和 must 的区别？filter 为什么更快？
- BM25 和 TF-IDF 的区别？BM25 好在哪？
- ES 深度分页怎么解决？scroll 和 search_after 的区别？
- dis_max 和 most_fields 的区别？什么时候用哪个？
- 如何给搜索结果加上自定义排序逻辑（如热度权重、时间衰减）？

### 动手实践
- 构造测试数据（100+ 文档），练习 match/term/bool/match_phrase/fuzzy 各种查询
- 用 explain API 调试一个查询的打分过程，理解 BM25 各项分数
- 用 function_score 实现"热度加权"排序：基础分 + field_value_factor(popularity)
- 测试深度分页：from=10000 观察性能，然后用 search_after 重写
- 用 profile API 对比 query context 和 filter context 的执行性能差异

---

## 阶段 5：聚合深入（1 周）

> 聚合依赖 Mapping（Doc Values）和查询（通常先 query 再 agg），所以放在阶段 4 之后。

### 5.1 聚合的前置知识——Doc Values

- 聚合和排序不走倒排索引，而走 **Doc Values**（列式存储，磁盘上的有序结构）
- keyword / numeric / date / boolean / geo 自动启用 Doc Values
- text 字段**没有** Doc Values → 要聚合必须开启 **Fielddata**（内存中构建，慎用）
- 所以生产中用 `name.keyword` 做聚合，而不是 `name`（text）

### 5.2 三大聚合类型

- **Bucket 聚合**（分桶 = GROUP BY）
  - terms：按字段值分桶
  - date_histogram / histogram：按时间/数值区间分桶
  - range：自定义范围分桶
  - filters：按多个查询条件分桶
  - composite：可分页的组合分桶（替代 terms size 过大的问题）
- **Metric 聚合**（统计 = SUM/AVG/MAX）
  - avg / sum / min / max / stats / extended_stats
  - cardinality：去重计数（HyperLogLog++，近似值）
  - percentiles：百分位数（T-Digest，近似值）
  - top_hits：每个桶内返回原始文档（类似 GROUP BY 后取 Top N）
- **Pipeline 聚合**（对聚合结果再聚合）
  - derivative：求导（变化率）
  - cumulative_sum：累计求和
  - moving_avg：移动平均
  - bucket_sort：对桶排序
  - bucket_selector：对桶过滤

### 5.3 嵌套聚合

- 多层 bucket 嵌套 + metric（如：按颜色分桶 → 每个桶内按品牌分桶 → 每个桶求平均价格）
- 嵌套层数对性能的影响
- aggs 与 query 配合：先 query 过滤再聚合

### 5.4 近似聚合

- **cardinality**：HyperLogLog++ 算法
  - precision_threshold 参数：低于此值时精确，超过时误差约 1-6%
  - 适用场景：UV 统计、去重计数
- **percentiles**：T-Digest 算法
  - 极端百分位（P99、P999）精确度更高
  - 适用场景：接口延迟分析
- **精确 vs 近似的取舍**：百亿级数据精确去重不现实，近似是唯一方案

### 5.5 大数据量聚合方案

- **terms 聚合不精确的原因**：每个 shard 独立计算 Top N，协调节点合并时可能遗漏
  - 解决：shard_size 参数（默认 size * 1.5 + 10）
  - 彻底解决：只用单 shard，或用 routing 保证数据在同一 shard
- **Composite Aggregation**：聚合结果分页，替代 terms size=100000 的内存风险
- **Sampler Aggregation**：对高基数字段采样后再聚合
- **Global Aggregation**：忽略 query 过滤，在全量数据上聚合

### 面试高频题
- terms 聚合结果为什么不精确？怎么解决？
- 怎么对上亿数据做去重统计？HyperLogLog 原理？
- doc_values 是什么？为什么聚合和排序离不开它？
- text 字段能做聚合吗？为什么不推荐？
- 聚合时内存不够怎么办？

### 动手实践
- 用电商数据实现：按品牌分桶 → 每个品牌的平均价格 → 按平均价格排序（bucket + metric + bucket_sort）
- 用 date_histogram 按月统计订单数，再用 pipeline 求环比增长率（derivative）
- 用 cardinality 统计 UV，对比不同 precision_threshold 下的精度和性能

---

## 阶段 6：存储原理与读写链路（1.5 周）

> **现在进入"懂原理"层**。你已经学会了 ES 的所有使用方式（Mapping/分词/查询/聚合），现在来理解底层为什么这样设计。带着使用经验看原理，理解会深得多。

### 6.1 Lucene 底层数据结构

- **倒排索引完整结构**：
  - Term Index（FST - Finite State Transducer）：内存中的前缀树，快速定位 Term Dictionary 位置
  - Term Dictionary：磁盘上的有序 Term 列表
  - Posting List：每个 Term 对应的文档 ID 列表
- **Posting List 编码优化**：
  - Frame of Reference (FOR)：增量编码 + 位压缩，减小存储空间
  - Roaring Bitmaps：filter 缓存中用于高效求交集/并集
- **Doc Values**：列式存储（类似 Parquet），用于排序和聚合
  - 为什么不用倒排索引做排序？（倒排是 term → doc，排序需要 doc → value）
- **Stored Fields vs _source**：
  - _source 存完整 JSON，stored field 存单个字段
  - 为什么 ES 默认用 _source 而非 stored fields

### 6.2 Segment 生命周期

- **Segment 不可变性** —— ES 存储设计的核心
  - 优势：无锁并发读、OS Cache 友好、便于压缩
  - 代价：更新 = 标记删除旧文档 + 写入新文档 + 等 merge 清理
- **完整写入链路**：
  ```
  文档写入 → Index Buffer (内存)
           → [refresh, 默认1s] → 新 Segment (OS Cache, 可搜索)
           → [flush, 默认30min] → Segment 持久化到磁盘
           → [merge, 后台持续] → 小 Segment 合并为大 Segment + 物理删除标记文档
  ```
- **refresh**：Index Buffer 中的数据写成新 Segment 到 OS Cache，此时文档变为可搜索
  - 这就是"近实时搜索"的根源：写入后最多 1s 才能搜到
  - refresh_interval 调大可提升写入性能
- **flush**：将 OS Cache 中的 Segment 持久化到磁盘 + 清空 translog
  - 默认 30 分钟或 translog 达到 512MB
- **translog**：Write-Ahead Log，保证 refresh 和 flush 之间的数据不丢
  - 默认每次写入操作后 fsync translog 到磁盘
  - 可设为 async（每 5s fsync）提升性能但增加丢数据风险
- **merge**：后台合并小 Segment 为大 Segment
  - Tiered Merge Policy：默认策略
  - force merge：只读索引可手动合并为单 Segment
  - 删除文档在 merge 时才真正物理删除（.del 标记 → merge 跳过）

### 6.3 写入全链路

```
Client → Coordinating Node → 路由(hash(_routing) % primary_shards) → Primary Shard
Primary Shard: 写 Index Buffer + 写 Translog → 返回成功
              → [异步] 转发到所有 in-sync Replica Shards
              → 所有 Replica 确认后 → 返回 Client 成功
```

- Wait for Active Shards：等待多少个分片副本确认写入
  - 默认 1（只需 primary 确认）
  - 可设为 all（等所有副本确认）或具体数字

### 6.4 读取全链路

- **Query Then Fetch 两阶段**（详见阶段 4.6，此处从分片视角重新理解）
  - 每个 Shard 内部：遍历所有 Segment，每个 Segment 独立检索，合并结果
  - 这就是为什么 Segment 太多会影响查询性能（每个都要查一遍）
- **DFS Query Then Fetch**：先收集全局的 term 频率，再查询（更准确的打分，更慢）

### 6.5 近实时搜索（NRT）总结

现在你可以完整理解这条链路了：
```
文档写入 → Index Buffer(内存, 不可搜) → [refresh 1s] → Segment(OS Cache, 可搜索)
所以: 写入后最多 1s 不可搜 = "近实时"
```

### 面试高频题
- 为什么 ES 是近实时的？refresh 机制是什么？
- ES 的写入数据丢失怎么办？translog 的作用？
- 删除文档是立即删除吗？对性能有什么影响？
- Segment 不可变有什么好处？有什么代价？
- 倒排索引中的 FST 是什么？为什么用它？
- force merge 什么时候用？有什么风险？

### 动手实践
- 调整 refresh_interval（1s → 30s → -1），批量写入数据观察写入性能和搜索延迟的变化
- 用 `_cat/segments` 观察 Segment 数量变化，手动触发 `_forcemerge` 观察合并结果
- 写入数据后关闭 ES 模拟宕机，重启后观察 translog 回放日志

---

## 阶段 7：集群架构与高可用（1 周）

> 有了阶段 6 的存储原理基础（Segment/Translog/Shard内部），现在可以理解集群层面如何协调多个 Shard。

### 7.1 节点角色详解

- **Master-eligible**：可参与选主，管理集群状态（索引创建删除、分片分配）
- **Data**：存储数据，执行 CRUD / 搜索 / 聚合（CPU/内存/IO 密集）
- **Coordinating**（默认所有节点都是）：接收请求，路由转发，汇总结果
- **Ingest**：执行 ingest pipeline 预处理
- **ML**：机器学习任务
- 生产集群推荐：**3 个专用 Master + N 个 Data + M 个 Coordinating**
- 专用 Master 为什么要**奇数个**（3/5/7）？—— 法定人数 = N/2 + 1

### 7.2 分片（Shard）机制

- 路由算法：`shard_num = hash(_routing) % number_of_primary_shards`
  - 这就是为什么 **primary shard 数量创建后不可变**（改了路由就乱了）
  - 自定义 _routing 可以让相关数据落在同一个 shard（查询性能提升）
- 分片数量规划：
  - 单个 shard 推荐 10-50GB
  - 分片过多：每个 shard 都有 Lucene 开销（文件句柄、内存、Segment），master 管理压力大
  - 分片过少：单 shard 过大，无法水平扩展，恢复慢
  - 经验公式：`分片数 ≈ 数据量 / 单 shard 目标大小`

### 7.3 节点发现与选主

- **ES 7.x+ 新选主机制**（取代 Zen Discovery）
  - Voting Configuration：自动管理参与投票的节点集合
  - 不再需要手动配置 minimum_master_nodes
- **选主流程**：Master-eligible 节点 → 互相发现 → 投票 → 获得多数票当选
- **集群状态（Cluster State）**：索引 mapping、分片分配等元数据
  - Master 维护并同步到所有节点
  - 频繁变更集群状态会成为性能瓶颈

### 7.4 脑裂（Split Brain）

- 什么是脑裂：网络分区导致两个子集各选出一个 Master
- ES 7.x+ 如何防止：Voting Configuration 自动维护法定人数
- ES 6.x-：需手动配置 `discovery.zen.minimum_master_nodes = master_eligible_nodes / 2 + 1`

### 7.5 写入一致性模型

- **Wait for Active Shards**（替代旧版 consistency: quorum/one/all）
  - 默认 1：只等 primary shard 确认
  - 设为 "all"：等所有 in-sync 副本确认
- **in-sync copies**：与 primary 保持同步的副本集合
  - 副本写入失败 → 从 in-sync set 移除 → primary 继续服务
  - 副本恢复后通过 peer recovery 追赶数据

### 7.6 分片分配与再平衡

- **Shard Allocation Awareness**：机架感知分配（避免主副本在同一机架）
- **Allocation Filtering**：控制分片分配到哪些节点（如按节点标签）
- **Cluster Reroute API**：手动移动分片
- **再平衡触发条件**：节点加入/离开、新建索引、分片不均衡

### 7.7 故障恢复

- **节点宕机后会发生什么？**
  1. Master 检测到节点离线
  2. 该节点上的 primary shard 由对应 replica promote 为新 primary
  3. 在其他节点上创建新的 replica
  4. Peer Recovery：新 replica 通过 translog + segment copy 追赶数据
- **集群 Red/Yellow/Green 状态**：
  - Green：所有 primary 和 replica 都正常
  - Yellow：所有 primary 正常，部分 replica 不可用
  - Red：部分 primary 不可用（数据可能丢失）

### 面试高频题
- ES 如何保证数据不丢失？
- 分片数设置多少合适？设置太多或太少有什么问题？
- primary shard 数量为什么创建后不可改？
- ES 如何避免脑裂？
- 一个节点宕机后会发生什么？恢复流程是怎样的？
- 集群状态 Red/Yellow/Green 分别代表什么？

### 动手实践
- 用 Docker Compose 搭建 3 节点集群，用 `_cat/nodes` / `_cat/health` / `_cat/shards` 观察集群状态
- 创建 3 分片 1 副本的索引，观察分片在节点间的分布
- 手动停掉一个节点，观察集群从 Green → Yellow → 重新分配副本 → 恢复 Green 的过程

---

## 阶段 8：性能调优（1 周）

> 调优需要同时理解存储原理（阶段 6）和集群架构（阶段 7），所以放在最后。面试和工作都会考查。

### 8.1 写入优化

- **批量写入**：_bulk 最佳 batch size（5-15MB），逐步测试找最优值
- **refresh_interval 调大**：大批量导入时设为 30s 或 -1（导入完再恢复）
- **translog 异步刷盘**：`index.translog.durability: async`（提升写入速度，牺牲少量持久性）
- **副本数临时设为 0**：大批量导入时去掉副本开销，导入完恢复
- **index sorting**：预排序加速查询，但写入稍慢
- **线程池调优**：write 线程池大小与队列

### 8.2 查询优化

- **filter 优先于 query**：不需要打分的条件一律用 filter（利用缓存）
- **routing 查询**：指定 routing 只查一个 shard（适用于多租户场景）
- **避免深度分页**：用 search_after 替代 from+size
- **避免 wildcard 前缀匹配**：`*keyword` 会全索引扫描
- **_source filtering**：只返回需要的字段
- **force merge 只读索引**：合并为单 Segment，减少查询时的 Segment 遍历
- **Index Sorting + Early Termination**：预排序后查询可提前终止
- **避免 script 排序/聚合**：Painless 脚本比原生慢 10-100 倍

### 8.3 JVM 与 GC 调优

- **堆内存两条红线**：
  - 不超过物理内存 **50%**：剩余留给 Lucene 依赖的 OS Page Cache
  - 不超过 **~31GB**（准确值取决于 JVM，通常约 30.5GB）：超过则 CompressedOops 失效，指针从 4 字节变 8 字节
- **G1GC**（ES 默认）：调优要点
  - InitiatingHeapOccupancyPercent
  - 关注 GC 停顿时间和频率
- **Fielddata 导致 OOM**：text 字段做聚合会加载 Fielddata 到内存
  - 限制：`indices.fielddata.cache.size`
  - 根本解决：用 keyword 子字段做聚合

### 8.4 OS 层调优

- **文件描述符**：`ulimit -n 65535+`（ES 打开大量 Segment 文件）
- **虚拟内存**：`vm.max_map_count = 262144`（Lucene 使用 mmap）
- **禁用 swap**：`swappiness = 1` 或 `bootstrap.memory_lock = true`
- **磁盘**：SSD 优于 HDD（随机读写性能差距巨大）

### 8.5 监控与诊断

- **_cat APIs**：`_cat/nodes?v` / `_cat/health?v` / `_cat/indices?v` / `_cat/shards?v` / `_cat/thread_pool?v`
- **_cluster/stats** / **_nodes/stats**：详细集群和节点统计
- **慢查询日志**：
  - `index.search.slowlog.threshold.query.warn: 10s`
  - `index.indexing.slowlog.threshold.index.warn: 10s`
- **Hot Threads API**：`_nodes/hot_threads`，定位 CPU 瓶颈
- **profile API**：查询执行计划，定位慢在哪个阶段

### 8.6 容量规划

- **数据量 → 分片数 → 节点数**：
  1. 预估数据量（含增长）
  2. 单 shard 10-50GB → 算出分片数
  3. 单节点承载 N 个 shard → 算出节点数
- **预留空间**：merge 需要额外 ~50% 磁盘空间
- **读写比**：写多读少 → 少副本；读多写少 → 多副本

### 面试高频题
- ES 写入慢怎么优化？说出 5 种方法
- ES 查询慢怎么排查和优化？
- ES 堆内存为什么不能超过 32GB？
- 如何做 ES 的容量规划？

### 动手实践
- 写入 10 万条测试数据，对比不同 refresh_interval / batch size / replica 配置下的写入吞吐量
- 用 profile API 分析一个复杂查询的各阶段耗时，找到瓶颈
- 开启慢查询日志，构造一个会触发慢查询的请求，观察日志输出

---

## 阶段 9：数据同步与架构集成（1 周）

> **面试几乎必问**："你们的数据怎么从 MySQL 同步到 ES 的？怎么保证一致性？" ES 在真实系统中几乎不会单独存在，一定有主数据库 → ES 的数据同步链路。这是连接 ES 知识和系统架构能力的关键阶段。

### 9.1 ES 在系统架构中的定位

- ES 不是主数据库——不支持事务、不保证强一致性
- 典型架构：MySQL（真实数据源） + ES（搜索/分析副本） + Redis（缓存）
- 数据流向：业务写 MySQL → 同步机制 → ES 索引 → 用户搜索
- **核心挑战**：如何保证 MySQL 和 ES 的数据一致性

### 9.2 同步方案对比

| 方案 | 原理 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|---------|
| **同步双写** | 业务代码同时写 MySQL 和 ES | 实现简单 | 事务一致性无法保证、代码耦合 | 小型项目、低一致性要求 |
| **异步双写（MQ）** | 写 MySQL 后发 MQ → 消费者写 ES | 解耦、异步、可重试 | 有延迟、MQ 可靠性 | 中等规模、可接受秒级延迟 |
| **CDC（Binlog 监听）** | Canal/Debezium 监听 MySQL binlog → 写 ES | 对业务代码零侵入、数据一致性好 | 架构复杂、binlog 解析有延迟 | **大型生产环境首选** |
| **Logstash JDBC** | Logstash 定时轮询 MySQL 增量数据 | 配置简单 | 延迟高（分钟级）、依赖更新时间字段 | 数据实时性要求不高 |
| **ETL 全量** | 定时全量导入 | 数据最终一致 | 耗时久、对源库有压力 | 冷数据、初始化导入 |

### 9.3 Canal/Debezium CDC 方案详解

- **Canal 架构**：Canal Server（伪装 MySQL Slave）→ 解析 Binlog → Canal Client/MQ → ES Writer
- **Debezium 架构**：MySQL → Debezium Connector → Kafka → ES Sink Connector
- 常见问题：
  - DDL 变更如何处理
  - binlog 位点管理与故障恢复
  - 延迟监控

### 9.4 异步双写（MQ 方案）详解

- 写入流程：业务写 MySQL（事务内） → 发 MQ 消息 → 消费者写 ES
- 保障一致性：
  - 本地消息表 / 事务消息（RocketMQ）
  - 消费者幂等性：用文档 _id 保证重复消费不产生副作用
  - 消费失败重试 + 死信队列
- 延迟与积压处理

### 9.5 数据一致性保障

- **最终一致性**：绝大部分场景的目标（而非强一致性）
- 全量校对机制：定时对比 MySQL 和 ES 数据量/关键字段
- 补偿机制：发现不一致后触发增量修复
- 监控告警：同步延迟、消息积压、ES 写入失败率

### 9.6 ES 客户端使用

- Java High-Level REST Client / Elasticsearch Java Client（ES 8.x+）
- Python elasticsearch-py
- Spring Data Elasticsearch
- 连接池管理、超时设置、重试策略

### 面试高频题
- 你们的数据怎么从 MySQL 同步到 ES 的？
- 同步双写有什么问题？怎么解决？
- Canal/Debezium 和 MQ 双写的区别？各自优缺点？
- 如何保证 MySQL 和 ES 的数据一致性？
- ES 写入失败怎么办？如何保证消费幂等？
- 全量同步和增量同步怎么配合？

### 动手实践
- 搭建一个 MySQL → Canal → ES 的同步链路（Docker Compose 可以一键搭建）
- 或用 Logstash JDBC Input 实现定时增量同步，观察 tracking_column 的工作方式
- 模拟同步中断场景（如 ES 宕机），验证重试和恢复机制

---

## 阶段 10：生产运维与高级特性（1 周）

> 涵盖生产环境运维和高级搜索特性。

### 10.1 索引生命周期管理（ILM）

- **Hot-Warm-Cold-Frozen-Delete 五阶段架构**
  - Hot：高性能节点，处理写入和频繁查询
  - Warm：中等性能，只读数据，历史查询
  - Cold：低成本存储，偶尔查询
  - Frozen：几乎不查询，最低成本
  - Delete：超过保留期自动删除
- **ILM Policy 配置**
- **Data Stream**：时间序列数据的原生支持（ES 7.9+）
- **Data Tier**：将节点标记为 hot/warm/cold/frozen

### 10.2 快照与恢复

- 快照仓库配置（filesystem / S3 / HDFS）
- 全量快照 vs 增量快照
- 单索引恢复 vs 全集群恢复
- SLM（Snapshot Lifecycle Management）自动化

### 10.3 滚动升级与版本迁移

- Rolling Upgrade 步骤
- 跨大版本升级路径（5.x → 6.x → 7.x → 8.x）
- 升级前兼容性检查工具

### 10.4 安全

- X-Pack Security：认证 + 授权 + TLS
- 内置用户与角色
- API Key 管理
- ES 8.x 默认开启安全（开箱即用 TLS + 认证）

### 10.5 高级搜索特性

- **Suggesters**：Term / Phrase / Completion（自动补全）/ Context Suggester
- **Geo 查询**：geo_distance / geo_bounding_box / 距离排序
- **Field Collapsing**：字段折叠（类似 GROUP BY 后取 Top 1）
- **Percolator**：反向搜索（"当新文档匹配这个查询时通知我"）
- **Search Template**：参数化查询模板
- **Runtime Fields**：查询时动态计算字段（无需 reindex）
- **Highlighting 高级配置**：boundary_scanner、自定义 pre/post_tags（基础已在阶段 4 覆盖）

### 10.6 数据处理

- **Ingest Pipeline**：写入前数据预处理（解析、转换、富化）
- **Enrich Processor**：写入时关联外部数据
- **Painless 脚本语言**：script query / script field / script aggregation

### 10.7 ELK/EFK 生态

- **Logstash**：数据采集与转换管道（input → filter → output）
- **Kibana**：可视化与管理界面
- **Beats 家族**：Filebeat / Metricbeat / Packetbeat / Heartbeat
- **典型日志架构**：Filebeat → Kafka → Logstash → ES → Kibana
- 为什么中间加 Kafka？（削峰填谷、解耦、防止 ES 被打爆）

### 10.8 ES 8.x 新特性

- KNN 向量搜索（dense_vector + knn query）
- 与 AI/ML 的结合：语义搜索、学习排序（LTR）
- 默认安全开启
- API 兼容层

### 面试高频题
- 你们生产环境的 ES 集群是怎么部署的？
- 日志数据怎么管理生命周期？Hot-Warm-Cold 怎么配？
- 搜索框自动补全怎么实现？Completion Suggester 原理？
- 如何用 ES 做日志系统？架构是什么？中间为什么加 Kafka？
- ES 支持向量搜索吗？怎么做语义搜索？

---

## 阶段 11：面试串联（持续）

> 将所有知识融会贯通，以面试视角重新组织。

### 11.1 Top 30 高频面试题

按维度分类：
- **基础概念**（5题）：倒排索引、近实时、Segment、text vs keyword、ES vs Lucene
- **查询**（5题）：match vs term、filter vs query、BM25、深度分页、function_score
- **写入**（4题）：写入流程、refresh/flush/translog、数据一致性、并发控制
- **集群**（5题）：选主、脑裂、分片策略、路由算法、故障恢复
- **性能**（5题）：写入优化、查询优化、JVM 32GB、容量规划、慢查询诊断
- **数据建模**（3题）：mapping 设计、nested vs join、index template
- **数据同步**（3题）：MySQL→ES 同步方案、一致性保障、CDC vs MQ
- **生产**（3题）：ILM、日志架构、监控告警

### 11.2 系统设计题

- **设计一个电商商品搜索系统**
  - 考查：mapping 设计、分词策略、多条件过滤+排序、搜索建议、**MySQL→ES 数据同步**、高亮
- **设计一个日志收集和分析平台**
  - 考查：ELK 架构、ILM、Hot-Warm-Cold、容量规划、告警
- **设计一个实时监控告警系统**
  - 考查：时间序列数据建模、聚合、Percolator/Watcher、数据保留策略
- **设计一个全文搜索引擎（百万级文档）**
  - 考查：分词、相关性打分、高亮、自动补全、性能优化

### 11.3 ES vs 其他存储

| 对比 | ES 适合 | 对方适合 |
|------|---------|---------|
| ES vs MySQL | 全文搜索、复杂条件过滤、聚合分析 | 事务、关系型数据、强一致性 |
| ES vs MongoDB | 搜索和分析 | 灵活 Schema、高写入吞吐 |
| ES vs Solr | 实时索引、分布式天然支持 | 稳定的纯搜索场景（社区萎缩） |
| ES vs ClickHouse | 全文搜索+聚合 | 超大规模 OLAP 分析（比 ES 快 10x） |

### 11.4 常见反模式（踩坑总结）

> 面试中描述"你踩过什么坑"比只会正面回答更有经验感。

| 反模式 | 后果 | 正确做法 |
|--------|------|---------|
| 把 ES 当主数据库 | 数据丢失、无事务 | MySQL 为主，ES 为搜索副本 |
| mapping 没设计就开始写数据 | Dynamic Mapping 推断出错、后期无法修改 | 先设计 mapping，设 dynamic: strict |
| 对 text 字段做聚合/排序 | 触发 Fielddata 加载，OOM | 用 `.keyword` 子字段 |
| 前缀用 wildcard `*keyword` | 全索引扫描，极慢 | 用 edge_ngram 或 prefix query |
| refresh_interval 设为 0 | 每次写入都 refresh，吞吐量极低 | 默认 1s 或按需调大；批量导入时设 -1 |
| 单索引 shard 设太多 | 空 shard 浪费资源，master 管理压力大 | 单 shard 10-50GB，按需设置 |
| nested 嵌套层数太深 | 性能断崖式下降 | 尽量用 object，必须 nested 时控制数量 |
| 不设 `max_result_window` 就深度分页 | from+size 内存爆炸 | 用 search_after / PIT |
| 忽略 ES 集群 Yellow 状态 | 副本不健康，节点宕机后丢数据 | 定期检查，确保所有 replica 分配 |
| 同步双写不处理失败 | MySQL 和 ES 数据不一致 | 用 MQ 异步+重试，或 CDC 方案 |

### 11.5 项目经验叙述

- STAR 方法组织项目经验
- 常见追问及应答策略
- 如何描述你在 ES 上做的性能优化
- 如何描述你设计的 MySQL→ES 数据同步方案

---

## 你已有知识对照表

> 根据你已有的笔记（已备份到 legacy/ 目录），标注当前掌握程度。

| 知识点 | 你的掌握 | 需要补齐 | 对应阶段 |
|--------|---------|---------|---------|
| ES 概念与 Lucene 关系 | 已了解 | 快速回顾即可 | 1 |
| 基础 CRUD | 已掌握 | - | 1 |
| Mapping 基础 | 了解静态/动态映射 | **补齐 Nested/Join/Multi-fields/Template/Alias** | **2** |
| text vs keyword | 了解基本区别 | 补齐选型策略和 Multi-fields | 2 |
| 索引设计模式 | **未覆盖** | **按时间分索引、多租户、宽表反范式** | **2** |
| 分词器（IK/standard） | 了解基本概念 | **补齐 search_analyzer、自定义 Analyzer、同义词** | **3** |
| DSL 查询 | 已掌握 match/term/bool/phrase/fuzzy | 补齐 function_score、rescore、profile、高亮 | 4 |
| 打分算法 | 了解 TF-IDF | **补齐 BM25、function_score 自定义打分** | **4** |
| 深度分页 | 未覆盖 | **scroll / search_after / PIT** | **4** |
| 聚合 | 了解 bucket/metric | **补齐 pipeline、近似聚合、composite、Doc Values** | **5** |
| 写入原理 | 了解 refresh/flush/translog | 补齐 Segment 详细生命周期、translog 持久化策略 | 6 |
| 读取原理 | 了解 Query Then Fetch | 补齐 DFS Query Then Fetch | 6 |
| 倒排索引底层 | 了解概念 | 补齐 FST/FOR/Roaring Bitmap | 6 |
| 集群架构 | 了解节点类型和分片 | 补齐分片路由算法、故障恢复、shard allocation | 7 |
| 选主与脑裂 | 了解基本概念 | 补齐 ES 7.x Voting Configuration | 7 |
| 性能调优 | **未覆盖** | **需要系统学习** | **8** |
| MySQL↔ES 数据同步 | **未覆盖** | **需要系统学习（面试必问）** | **9** |
| 生产运维 | **未覆盖** | **需要系统学习** | **10** |
| ILM/快照/安全 | **未覆盖** | **需要系统学习** | **10** |
| Suggester/Geo/向量搜索 | **未覆盖** | **需要系统学习** | **10** |
| 面试系统设计 | **未覆盖** | **需要系统学习** | **11** |

---

## 推荐学习资源

### 查阅型（遇到问题查）
- **官方文档**（最权威）：Elasticsearch 7.x Reference —— API 用法和参数以此为准
- **Elastic 官方博客**：深入原理的技术文章，尤其 "Under the Hood" 系列

### 学习型（系统学习跟）
- **极客时间《Elasticsearch 核心技术与实战》**（阮一鸣）—— 中文最系统的视频课程
- **《Elasticsearch 权威指南》**（中文版，基于 ES 2.x 但原理部分依然有价值）
- **《Elasticsearch 实战》**（Radu Gheorghe）—— 偏实战的英文书

### 实践环境搭建

```bash
# 最快速的本地环境：单节点 ES 7.x + Kibana
docker network create elastic
docker run -d --name es --net elastic -p 9200:9200 -e "discovery.type=single-node" -e "ES_JAVA_OPTS=-Xms512m -Xmx512m" elasticsearch:7.17.10
docker run -d --name kibana --net elastic -p 5601:5601 kibana:7.17.10

# 3 节点集群（阶段 7 需要）：建议用 docker-compose
# 参考官方文档的 docker-compose.yml 配置
```

所有动手实践都在 Kibana Dev Tools (http://localhost:5601/app/dev_tools) 中完成。
