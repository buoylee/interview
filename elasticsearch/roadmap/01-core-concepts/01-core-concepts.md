# 阶段 1：核心概念（0.5 周）

> **目标**：建立 ES 的全局心智模型。学完本阶段后，你应该能画出"一个搜索请求从发出到返回结果"的完整路径草图，并理解每一层的职责。
>
> **前置依赖**：无
>
> **为后续阶段铺路**：本阶段建立的心智模型是所有后续学习的骨架——阶段 2（Mapping）是给骨架填充"数据如何组织"，阶段 3（分词）是"文本如何进入倒排索引"，阶段 4（Query）是"如何查询倒排索引"，阶段 6（存储原理）是"骨架内部的细节实现"。

---

## 1.1 ES 是什么——一句话定位

**Elasticsearch 是基于 Lucene 的分布式搜索和分析引擎。**

这一句话里有三个关键词，每个都值得展开：

### 基于 Lucene

Lucene 是 Java 编写的全文搜索引擎**库**（注意是库，不是独立的服务）。它是目前最成熟、性能最好的搜索引擎核心。

但 Lucene 有四个致命局限：

| 局限 | 说明 |
|------|------|
| **只能 Java 使用** | 必须以 jar 包形式嵌入 Java 项目 |
| **API 极其复杂** | 创建索引、搜索的代码非常繁琐，需要深入理解检索原理 |
| **不支持分布式** | 单机存储，索引数据无法跨节点同步 |
| **运维困难** | 没有独立的管理界面，索引和应用共享服务器资源 |

**ES 做的事情**：在 Lucene 之上包了一层，解决上面所有问题。

```
ES 对 Lucene 的封装：

┌─────────────────────────────────────────────┐
│              Elasticsearch                   │
│  ┌───────────────────────────────────────┐  │
│  │   REST API（任何语言都能调用）          │  │
│  ├───────────────────────────────────────┤  │
│  │   分布式层（集群、分片、副本、路由）     │  │
│  ├───────────────────────────────────────┤  │
│  │   索引管理（Mapping、Settings、Alias） │  │
│  ├───────────────────────────────────────┤  │
│  │   Lucene（真正干活的搜索引擎核心）      │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

> **面试怎么答**："ES 和 Lucene 是什么关系？"
>
> Lucene 是全文搜索引擎库，提供倒排索引、分词、打分等核心能力，但只是一个 Java 库，不支持分布式、API 复杂。ES 在 Lucene 之上封装了 REST API、分布式集群管理、索引管理等能力，把 Lucene 从一个库变成了一个开箱即用的分布式搜索服务。

### 分布式

ES 天生是集群架构。即使你只启动一个节点，它也是一个"只有一个节点的集群"。数据可以分散到多个节点，查询时自动聚合所有节点的结果。这是 Lucene 做不到的。

### 搜索和分析引擎

ES 不仅能搜索（全文检索、过滤、排序），还能分析（聚合统计、指标计算）。这两种能力决定了 ES 的两大应用场景：

| 场景 | 搜索能力 | 分析能力 |
|------|---------|---------|
| 电商商品搜索 | 关键词搜索、过滤、排序 | 销量统计、价格分布 |
| 日志分析平台 | 日志关键词搜索 | 错误趋势、QPS 统计 |
| 站内搜索 | 文章/帖子搜索 | 热词统计、用户行为分析 |

---

## 1.2 核心概念——六个名词建立全局认知

ES 的核心概念可以用一张图说清：

```
                        Cluster（集群）
                 ┌──────────────────────────┐
                 │                          │
              Node A                     Node B                    Node C
           ┌──────────┐             ┌──────────┐             ┌──────────┐
           │ Shard P0  │             │ Shard P1  │             │ Shard P2  │
           │ Shard R1  │             │ Shard R2  │             │ Shard R0  │
           └──────────┘             └──────────┘             └──────────┘
                 │                       │                        │
                 └───────────────────────┴────────────────────────┘
                                         │
                              Index: "products"
                           (3 Primary + 3 Replica)
                                         │
                         ┌───────────────────────────────┐
                         │  Document 1: { "name": "..." } │
                         │  Document 2: { "name": "..." } │
                         │  Document 3: { "name": "..." } │
                         └───────────────────────────────┘
```

### Index（索引）

ES 中数据组织的最高层级。一个 Index 是一类数据的集合。

```
类比（帮助理解，但不完全等价）：
MySQL Database/Table  ←→  ES Index
```

**ES 7.x+ 重要变化**：取消了 Type 的概念。以前可以在一个 Index 下创建多个 Type（类似一个数据库下多张表），7.x 之后一个 Index 只有一个固定的 `_doc` 类型。

所以现在的 API 格式是 `/index_name/_doc/id`，而不是以前的 `/index_name/type_name/id`。

### Document（文档）

ES 中的最小数据单元，以 JSON 格式存储。类比 MySQL 中的一行记录。

```json
// 一个文档的例子
{
  "_index": "products",
  "_id": "1",
  "_source": {
    "name": "iPhone 15",
    "price": 5999,
    "brand": "Apple",
    "description": "Apple 最新款智能手机"
  }
}
```

其中：
- `_index`：属于哪个索引
- `_id`：文档唯一标识（可以自动生成，也可以手动指定）
- `_source`：文档的原始 JSON 内容

### Field（字段）

文档中的每个 key-value 对。类比 MySQL 中的列（Column）。

**关键区别**：MySQL 的列类型固定且统一，ES 的字段类型由 **Mapping** 定义，不同类型决定了完全不同的索引和查询行为（这是阶段 2 的核心内容）。

### Shard（分片）

一个 Index 的数据可以被切分成多个 **Shard**，分散存储在不同的 Node 上。每个 Shard 本质上就是一个完整的 **Lucene 索引**。

分片的目的：
- **水平扩展**：数据量太大时，一台机器存不下，分到多台
- **并行处理**：查询时多个 Shard 并行检索，再合并结果

分片分两种：
- **Primary Shard（主分片）**：数据写入的目标，每个文档只属于一个 Primary Shard
- **Replica Shard（副本分片）**：Primary 的完整拷贝，提供容错和读负载均衡

> **记住一个关键限制**（阶段 7 会解释为什么）：Primary Shard 的数量在索引创建后**不可修改**。Replica 的数量可以随时调整。

### Node（节点）

一个 ES 实例就是一个 Node。一台物理机可以运行多个 Node（但生产环境通常一台一个）。

### Cluster（集群）

拥有相同 `cluster.name` 的一组 Node 组成一个 Cluster。集群自动协调数据分布、故障转移、请求路由。

### 六个概念的关系总结

```
Cluster 包含多个 Node
  └→ Node 上分布着多个 Shard
       └→ Shard 属于某个 Index（Primary 或 Replica）
            └→ Index 包含多个 Document
                 └→ Document 由多个 Field 组成
```

---

## 1.3 倒排索引——ES 的灵魂

> 倒排索引是 ES（准确说是 Lucene）的核心数据结构。**理解倒排索引就理解了 ES 一半的行为**——为什么 match 查询能搜到、为什么 term 查询搜不到、为什么搜索这么快、为什么更新其实是"删除+新增"。

### 为什么全文搜索不能用 B+ 树？

先理解问题。假设我们有三篇文章：

| doc_id | content |
|--------|---------|
| 1 | "Elasticsearch is a search engine" |
| 2 | "Lucene is a search library" |
| 3 | "Elasticsearch is based on Lucene" |

**需求**：搜索包含 "search" 的文章。

**如果用 MySQL（B+ 树）**：
```sql
SELECT * FROM articles WHERE content LIKE '%search%';
```
`LIKE '%search%'` 的 `%` 前缀导致 B+ 树索引**完全失效**，只能**全表扫描**逐行比对。数据量大时（百万、千万级）极慢。

**根本原因**：B+ 树是按字段值的整体来排序和查找的。它能快速找到 `content = "xxx"` 的行，但无法快速找到 `content 包含 "xxx"` 的行——因为这需要"打开"每一行的内容去看里面有没有这个词。

### 倒排索引的思路——"反着来"

既然正着查（从文档找词）很慢，那就**反着存**：提前把每个词出现在哪些文档中记录好。

**正排索引**（B+ 树的思路）：

```
doc_id → content
1      → "Elasticsearch is a search engine"
2      → "Lucene is a search library"
3      → "Elasticsearch is based on Lucene"
```

从文档找词 → 需要扫描所有文档。

**倒排索引**（ES 的思路）：

先对每篇文章做**分词**（Tokenize），然后建立"词 → 文档列表"的映射：

```
Term（词项）      → Posting List（倒排列表）
─────────────────────────────────────────
a                → [1, 2]
based            → [3]
elasticsearch    → [1, 3]
engine           → [1]
is               → [1, 2, 3]
library          → [2]
lucene           → [2, 3]
on               → [3]
search           → [1, 2]
```

现在搜索 "search"：直接查表，O(1) 时间拿到结果 → `[doc 1, doc 2]`。

### 倒排索引的完整结构

上面的例子做了简化。完整的倒排索引由三部分组成：

```
Term Index      →    Term Dictionary     →    Posting List
（内存，快速定位）     （磁盘，有序词表）        （磁盘，文档列表）

 [FST 前缀树]         Term      指针
                      ─────────────           ┌──────────────────┐
                      a        ──────────────→│ doc_ids: [1, 2]  │
                      based    ──────────────→│ doc_ids: [3]     │
                      elastic… ──────────────→│ doc_ids: [1, 3]  │
                      engine   ──────────────→│ doc_ids: [1]     │
                      ...                     └──────────────────┘
```

| 组件 | 存储位置 | 作用 |
|------|---------|------|
| **Term Index** | 内存 | 前缀树结构（FST），快速定位 Term Dictionary 中的位置 |
| **Term Dictionary** | 磁盘 | 所有 Term 的有序列表，每个 Term 指向其 Posting List |
| **Posting List** | 磁盘 | 每个 Term 对应的文档 ID 列表（还可能包含词频、位置等信息） |

> **底层细节留到阶段 6**：FST 的数据结构、Posting List 的压缩编码（FOR/Roaring Bitmap）等，在学完 Mapping、分词、查询之后再深入，那时你会理解"为什么需要这些优化"。

### 倒排索引 vs B+ 树 对比

| 维度 | 倒排索引 | B+ 树 |
|------|---------|-------|
| 核心思路 | 词 → 文档列表 | 字段值 → 行位置 |
| 擅长 | 全文搜索（"content 包含 xxx"） | 精确查找和范围查找（"id = 5", "age > 18"） |
| 不擅长 | 事务、频繁更新 | 全文搜索（LIKE '%xxx%'） |
| 更新代价 | 高（Segment 不可变，更新=删除+新增） | 低（原地更新） |
| 典型应用 | Elasticsearch、Solr | MySQL、PostgreSQL |

> **面试怎么答**："倒排索引和 B+ 树的区别？为什么搜索用倒排不用 B+ 树？"
>
> B+ 树按字段值整体排序，擅长精确查找和范围查询，但 LIKE '%keyword%' 这种包含搜索会导致索引失效，只能全表扫描。倒排索引反过来，提前把每个词出现在哪些文档中记录好，搜索时直接查词表，O(1) 定位到文档列表，所以全文搜索非常快。但倒排索引的代价是更新成本高，因为 Segment 不可变，更新实际上是标记删除旧文档再写入新文档。

### 从倒排索引理解 ES 的一切行为

建立这个核心认知后，后续阶段的很多概念就能自然推导出来：

| 你将在后续学到的概念 | 与倒排索引的关系 |
|-------------------|---------------|
| **Mapping**（阶段 2） | 决定一个字段**是否建立倒排索引**、用什么方式建立 |
| **text vs keyword**（阶段 2） | text 会分词后建倒排，keyword 不分词整体建倒排 |
| **Analyzer 分词器**（阶段 3） | 决定文本**如何拆成 Term** 写入倒排索引 |
| **match 查询**（阶段 4） | 搜索词也经过分词器，拆成 Term，去倒排索引中查找匹配 |
| **term 查询**（阶段 4） | 搜索词**不分词**，直接去倒排索引中精确匹配 |
| **Segment 不可变**（阶段 6） | 倒排索引一旦写入 Segment 就不能修改，更新=标记删除+新增 |
| **近实时搜索**（阶段 6） | 写入倒排索引后需要 refresh 才能被搜到（默认 1s） |

---

## 1.4 CRUD 回顾

> 你已经掌握基本操作，这里重点理清**每个操作的语义差别**和**底层隐含的行为**。

### 创建索引

```
PUT /products
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1
  }
}
```

- `number_of_shards`：主分片数，创建后**不可修改**
- `number_of_replicas`：副本数，可随时修改
- 不指定 Mapping 时，ES 会根据写入的第一个文档自动推断（Dynamic Mapping）——这往往不是你想要的，**阶段 2 会讲为什么应该预先设计 Mapping**

### 写入文档

```
# 方式1：指定 ID（幂等）
PUT /products/_doc/1
{
  "name": "iPhone 15",
  "price": 5999
}

# 方式2：不指定 ID（ES 自动生成，非幂等）
POST /products/_doc
{
  "name": "MacBook Pro",
  "price": 12999
}
```

**PUT vs POST 的核心区别：**

| 维度 | PUT | POST |
|------|-----|------|
| ID | **必须**指定 | 可不指定（ES 自动生成） |
| 幂等性 | 幂等（相同请求多次执行结果一样） | 不幂等（每次生成新文档） |
| 如果 ID 已存在 | **整个文档替换**（全量覆盖） | 同 PUT |

### 更新文档

```
# 部分更新（只更新指定字段）
POST /products/_update/1
{
  "doc": {
    "price": 5499
  }
}
```

**底层实际操作**（阶段 6 会详细解释）：
1. 读取旧文档
2. 在内存中合并变更
3. **标记旧文档为删除**
4. **写入新文档**

所以 ES 的"更新"本质上是"删除+新增"。这是因为 Lucene 的 Segment 是不可变的。

### 删除

```
# 删除文档
DELETE /products/_doc/1

# 删除索引（危险！删除整个索引及所有数据）
DELETE /products
```

文档删除也不是立即物理删除，而是在 `.del` 文件中**标记**为已删除。真正的物理删除发生在后台的 **Segment Merge**（合并）时。

### 批量操作（_bulk）

```
POST /_bulk
{"index": {"_index": "products", "_id": "1"}}
{"name": "iPhone 15", "price": 5999}
{"index": {"_index": "products", "_id": "2"}}
{"name": "MacBook Pro", "price": 12999}
{"delete": {"_index": "products", "_id": "3"}}
```

- 格式：每两行一组（操作行 + 数据行），delete 只需操作行
- **性能关键**：batch size 建议 5-15MB，太大太小都影响性能
- _bulk 中单条操作失败不影响其他操作

### 批量获取（_mget）

```
GET /products/_mget
{
  "ids": ["1", "2", "3"]
}
```

### 并发控制——乐观锁

ES 使用 `_seq_no` + `_primary_term` 实现乐观锁（ES 7.x+，替代了旧版的 `_version`）。

```
# 步骤1：先读取文档，拿到 _seq_no 和 _primary_term
GET /products/_doc/1
# 响应中包含："_seq_no": 10, "_primary_term": 1

# 步骤2：更新时带上这两个值
PUT /products/_doc/1?if_seq_no=10&if_primary_term=1
{
  "name": "iPhone 15",
  "price": 5499
}
```

如果在你读取和更新之间，有人已经修改了这个文档（`_seq_no` 已变），则更新会失败（返回 409 Conflict），需要重新读取再重试。

- **`_seq_no`**：每次文档变更递增
- **`_primary_term`**：每次 Primary Shard 重新分配时递增（类比 ZooKeeper 的 epoch）

---

## 1.5 全局心智模型——把所有概念串起来

学完以上内容后，你应该能理解下面这张"一次搜索请求的完整路径"：

```
用户搜索 "智能手机"
        │
        ▼
   ① REST API 接收请求
        │
        ▼
   ② 请求到达某个 Node（Coordinating Node）
        │
        ▼
   ③ Coordinating Node 将请求广播到 Index 的所有 Shard
      （products 索引有 3 个 Primary Shard，分布在不同 Node 上）
        │
        ▼
   ④ 每个 Shard 内部（本质是一个 Lucene 索引）：
      - 对 "智能手机" 做分词 → ["智能", "手机"]       ← 阶段 3 会详细讲
      - 去倒排索引中查找包含这些 Term 的文档          ← 本阶段刚学的
      - 对匹配文档计算相关性分数                      ← 阶段 4 会详细讲
      - 返回 Top N 的 doc_id + score 给 Coordinating Node
        │
        ▼
   ⑤ Coordinating Node 合并所有 Shard 的结果
      - 全局排序、分页
      - 去对应 Shard 取回实际文档内容
        │
        ▼
   ⑥ 返回最终结果给用户
```

**本阶段你理解了第 ①②③⑤⑥ 步（API、节点、分片、汇总）和第 ④ 步中倒排索引查找的部分。**

后续阶段要补齐的：
- 阶段 2（Mapping）：字段如何决定④中的索引方式
- 阶段 3（分词）：④中"智能手机"如何被拆分成 Term
- 阶段 4（Query DSL）：④中不同查询类型的匹配规则和打分算法
- 阶段 6（存储原理）：④中 Shard 内部的 Segment/refresh/translog 机制
- 阶段 7（集群）：②③⑤ 中节点如何协调、分片如何路由

---

## 面试高频题与参考答案

### Q1：ES 和 Lucene 是什么关系？

**答**：Lucene 是 Apache 开源的全文搜索引擎**库**，用 Java 编写，提供倒排索引、分词、相关性打分等核心搜索能力。但它只是一个 jar 包级别的库，不支持分布式，API 复杂，且只能在 Java 中使用。

Elasticsearch 在 Lucene 之上做了封装，提供了：REST API（任何语言都能调用）、分布式集群管理（数据分片、副本、故障转移）、索引管理（Mapping、Settings、Alias）。简单说，Lucene 负责单机上的搜索引擎核心能力，ES 负责把它变成一个分布式可用的搜索服务。每一个 ES 的 Shard 本质上就是一个独立的 Lucene 索引。

### Q2：什么是倒排索引？和 B+ 树有什么区别？

**答**：倒排索引是一种"词 → 文档列表"的索引结构。写入文档时先分词，把每个词出现在哪些文档中记录下来。搜索时直接查词表定位文档，全文搜索效率极高。

B+ 树是按字段值的整体来排序组织的索引，擅长精确查找（`id = 5`）和范围查询（`age > 18`），但对"字段内容包含某个词"的搜索（`LIKE '%keyword%'`）无能为力，只能全表扫描。

所以全文搜索场景用倒排索引（ES），事务型精确查询用 B+ 树（MySQL）。两者不是替代关系，而是互补——生产中通常 MySQL 做主库保证事务和一致性，ES 做搜索副本提供全文检索能力。

### Q3：为什么全文搜索用 ES 而不用 MySQL？

**答**：三个原因：

1. **索引结构**：MySQL 的 B+ 树索引对 `LIKE '%keyword%'` 查询无法使用索引，只能全表扫描；ES 的倒排索引天生为全文搜索设计，可以直接从词定位到文档。
2. **分词能力**：ES 支持丰富的分词器（内置 + IK 等第三方），能把文本拆成有意义的词进行索引；MySQL 的全文索引能力相对有限（尤其是中文支持）。
3. **分布式**：ES 天生支持数据分片和副本，可以水平扩展到数十亿文档级别；MySQL 单表数据量过大后性能急剧下降。

但 ES 也有不适合的场景：不支持事务、不保证强一致性、更新代价高。所以 ES 通常不作为主数据库，而是作为搜索/分析的只读副本。

---

## 动手实践

### 练习 1：搭建环境

```bash
# 创建 docker-compose.yml，内容如下：
# （或者直接用命令行启动两个容器）

docker network create elastic

docker run -d --name es --net elastic \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
  elasticsearch:7.17.10

docker run -d --name kibana --net elastic \
  -p 5601:5601 \
  kibana:7.17.10
```

启动后访问：
- ES：http://localhost:9200（应该看到 JSON 信息）
- Kibana：http://localhost:5601 → 左侧菜单 → Dev Tools

### 练习 2：CRUD 全流程

在 Kibana Dev Tools 中依次执行：

```
# 1. 创建索引
PUT /my_test
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0
  }
}

# 2. 写入文档（指定ID）
PUT /my_test/_doc/1
{
  "title": "Elasticsearch 入门",
  "content": "ES 是基于 Lucene 的分布式搜索引擎",
  "tags": ["search", "distributed"],
  "created_at": "2024-01-01"
}

# 3. 写入文档（不指定ID）
POST /my_test/_doc
{
  "title": "Lucene 原理",
  "content": "Lucene 是一个全文搜索引擎库",
  "tags": ["search", "lucene"],
  "created_at": "2024-01-02"
}

# 4. 查看文档
GET /my_test/_doc/1

# 5. 搜索（全量）
GET /my_test/_search

# 6. 部分更新
POST /my_test/_update/1
{
  "doc": {
    "tags": ["search", "distributed", "elasticsearch"]
  }
}

# 7. 验证更新结果
GET /my_test/_doc/1

# 8. 批量操作
POST /_bulk
{"index": {"_index": "my_test", "_id": "3"}}
{"title": "分布式系统", "content": "分布式系统是由多个节点组成", "tags": ["distributed"], "created_at": "2024-01-03"}
{"index": {"_index": "my_test", "_id": "4"}}
{"title": "搜索引擎原理", "content": "搜索引擎的核心是倒排索引", "tags": ["search"], "created_at": "2024-01-04"}

# 9. 批量获取
GET /my_test/_mget
{
  "ids": ["1", "3", "4"]
}

# 10. 删除文档
DELETE /my_test/_doc/4

# 11. 验证删除
GET /my_test/_doc/4

# 12. 查看索引的 mapping（观察 ES 自动推断的字段类型）
GET /my_test/_mapping

# 13. 删除索引
DELETE /my_test
```

### 练习 3：验证你的理解

完成上面的操作后，尝试回答：

1. 执行完第 12 步后，看 `_mapping` 的结果——`title` 字段被 ES 推断成了什么类型？有没有 `.keyword` 子字段？（这为阶段 2 Mapping 的学习埋下伏笔）

2. 执行第 6 步（部分更新）后，`_seq_no` 的值相比第 2 步有没有变化？（理解乐观锁版本递增）

3. 执行第 11 步后，返回结果中 `found` 的值是什么？（理解删除行为）

---

## 本阶段总结

学完本阶段，你应该掌握了以下心智模型：

```
ES = Lucene（搜索核心） + 分布式 + REST API

数据组织：Cluster → Node → Index → Shard → Document → Field

搜索核心：倒排索引（Term → Posting List）
         正排：文档 → 词（全表扫描，慢）
         倒排：词 → 文档（直接查表，快）

CRUD：写入其实是"写入倒排索引"
      更新其实是"标记删除旧文档 + 写入新文档"
      删除其实是"标记删除，等 merge 时物理清理"
```

**下一阶段**：阶段 2 Mapping 与数据建模——你会学到 `title` 字段为什么同时有 `text` 和 `keyword` 两种类型，以及这如何决定了查询行为。
