# 阶段 2：Mapping 与数据建模（1 周）

> **目标**：掌握 ES 数据建模的完整能力。学完本阶段后，你应该能为任意业务场景设计出合理的 Mapping，知道每个字段类型的索引行为和查询含义，并能熟练使用 Index Template、Alias、Reindex 等索引管理工具。
>
> **前置依赖**：阶段 1（核心概念——倒排索引、文档、分片、CRUD）
>
> **为后续阶段铺路**：Mapping 是整个 ES 知识体系的地基。字段类型决定了阶段 3（分词）中文本如何被分析，决定了阶段 4（Query DSL）中不同查询的行为，也决定了阶段 5（聚合）中是否可以排序和统计。**Mapping 设计错了，后面所有操作都会出问题且无法修补（只能 Reindex）。**

---

## 2.1 为什么 Mapping 必须最先学——因果链

还记得阶段 1 结尾留的问题吗？你在练习 12 中查看了 `_mapping`，发现 ES 自动把 `title` 字段推断成了 **text 类型 + keyword 子字段**——但为什么是这样？text 和 keyword 有什么区别？为什么一个字段要同时有两种类型？这些问题的答案，就在本阶段。

在阶段 1 中，你已经知道了倒排索引的基本原理：文本被拆成 Term，建立 Term → 文档列表的映射。但有一个关键问题还没解答：**谁来决定一个字段要不要被拆成 Term？用什么方式拆？**

答案就是 **Mapping**。

```
Mapping 定义字段类型
    │
    ├── text 类型 → 触发分词（Analyzer） → 分词后的 Term 写入倒排索引 → 支持全文搜索（match）
    │                                                                  → 不能直接排序/聚合
    │
    ├── keyword 类型 → 不分词，整体作为一个 Term → 写入倒排索引 → 支持精确匹配（term）
    │                                           → 自动构建 Doc Values → 支持排序/聚合
    │
    ├── 数值/日期 类型 → 构建 BKD 树 → 支持范围查询
    │                  → 自动构建 Doc Values → 支持排序/聚合
    │
    └── nested 类型 → 每个嵌套对象独立建立倒排索引（隐藏文档）→ 支持精确关联查询
```

**一句话总结**：Mapping 是 ES 的「数据库 Schema」，它定义了每个字段的类型，而字段类型决定了这个字段的一切行为——如何索引、如何查询、能否排序、能否聚合。

> **和 MySQL 的关键区别**：MySQL 的 Schema 也定义字段类型，但所有类型都走 B+ 树索引，查询行为基本一致。ES 不同——text 和 keyword 虽然都存字符串，走的索引结构完全不同，查询行为也完全不同。这就是为什么 Mapping 必须在查询之前学。

### 为什么不能后补 Mapping？

**ES 的 Mapping 一旦创建就不可修改**（只能追加新字段，不能更改已有字段的类型）。

```
# 这是可以的：追加新字段
PUT /products/_mapping
{
  "properties": {
    "new_field": { "type": "keyword" }
  }
}

# 这是不行的：修改已有字段类型（会报错！）
PUT /products/_mapping
{
  "properties": {
    "name": { "type": "keyword" }   // 原来是 text，想改成 keyword → 报错
  }
}
```

如果需要修改字段类型，只能：
1. 创建一个新索引（使用正确的 Mapping）
2. 用 `_reindex` 把旧索引的数据迁移过去
3. 用 Alias 切换读写指向

这个代价非常大，所以**在写入第一条数据之前就设计好 Mapping** 是最佳实践。

> **面试怎么答**："ES 的 mapping 能修改吗？"
>
> ES 的 Mapping 创建后只能追加新字段，不能修改已有字段的类型。这是因为字段类型决定了底层的索引结构（倒排索引、BKD 树、Doc Values 等），修改类型意味着要重建所有已有数据的索引，ES 不支持原地重建。如果确实需要修改，只能创建新索引配置正确的 Mapping，然后用 `_reindex` API 迁移数据，最后用 Alias 切换。

---

## 2.2 核心字段类型——六种基础类型

ES 支持几十种字段类型，但日常使用集中在以下六种：

### 字符串类型：text 与 keyword

这是 ES 中**最重要**的类型区分，没有之一。同样是存储字符串，`text` 和 `keyword` 的底层索引行为截然不同。

| 维度 | text | keyword |
|------|------|---------|
| **是否分词** | ✅ 会经过 Analyzer 分词 | ❌ 不分词，整体作为一个 Term |
| **索引结构** | 倒排索引（分词后的多个 Term） | 倒排索引（整个值作为一个 Term） |
| **典型查询** | match（全文搜索） | term / terms（精确匹配） |
| **是否有 Doc Values** | ❌ 没有 | ✅ 有 |
| **能否排序/聚合** | ❌ 不能直接排序聚合（需开启 Fielddata，不推荐） | ✅ 可以 |
| **存储开销** | 较大（每个 Term 单独建索引） | 较小 |
| **max 限制** | 默认不限长度（但太长影响性能） | 默认 `ignore_above: 256`（超过部分不索引） |

> **Doc Values 是什么？** 倒排索引是「Term → 文档」的映射，解决的是「搜到哪些文档」的问题。但排序和聚合需要反过来——「文档 → 字段值」。Doc Values 是 ES 在写入时自动构建的**列式存储**（类似数据库的列存），把每个文档的字段值按列连续存放，专门服务排序和聚合。keyword、数值、日期类型默认自动开启 Doc Values；text 类型因为分词后一个字段对应多个 Term，没有唯一值可存，所以不构建 Doc Values。阶段 5（聚合）和阶段 6（存储原理）会深入讲 Doc Values 的底层实现。

**用一个例子感受差异：**

假设一个字段值是 `"Hello World"`：

- **text** 类型经过标准分词器后会拆成两个 Term：`hello` 和 `world`（注意转了小写）
  - 搜索 `match: "hello"` → ✅ 能匹配
  - 搜索 `term: "Hello World"` → ❌ 不能匹配（因为倒排索引里没有 "Hello World" 这个完整 Term，只有 "hello" 和 "world"）

- **keyword** 类型不分词，整体作为一个 Term：`Hello World`
  - 搜索 `term: "Hello World"` → ✅ 能匹配
  - 搜索 `term: "hello world"` → ❌ 不能匹配（大小写敏感）
  - 搜索 `match: "hello"` → ❌ 不能匹配

> **这是面试必考题的原点**。后面阶段 4 讲 Query DSL 时，match vs term 的行为差异全部来源于此。

### 数值类型

| 类型 | 说明 | 适用场景 |
|------|------|---------|
| `long` | 64 位整数 | 大多数整数场景 |
| `integer` | 32 位整数 | 值范围较小时 |
| `short` | 16 位整数 | 极小数值 |
| `byte` | 8 位整数 | 极小数值 |
| `double` | 64 位双精度浮点 | 需要精确小数 |
| `float` | 32 位单精度浮点 | 允许精度损失 |
| `half_float` | 16 位半精度浮点 | 精度要求极低 |
| `scaled_float` | 按缩放因子存为 long | 金额等场景（如 `scaling_factor: 100`，599.99 存为 59999） |

数值类型的索引结构是 **BKD 树**（Block K-Dimensional Tree），专为范围查询优化。同时自动启用 **Doc Values**，支持排序和聚合。

> **为什么数值不走倒排索引？** 倒排索引擅长精确匹配（Term → 文档列表），但范围查询（`price > 100 AND price < 500`）需要遍历所有符合的 Term 再取并集，效率低。BKD 树是一种多维空间索引，把数值按区间组织成树结构，范围查询时可以快速跳过不相关的区间，复杂度接近 O(log N)。简单类比：倒排索引像字典（按关键词精确翻页），BKD 树像图书馆的分类书架（按数值范围快速定位区间）。

**选型建议：**
- 优先用 `long` 和 `double`，够用就行，不要过度优化精度
- 金额场景用 `scaled_float`（避免浮点精度问题）
- **不要把数值类型的 ID 存为 `keyword`**——如果只是精确匹配不做范围查询，`keyword` 更省空间且查询更快

> **等等，数值 ID 应该用 keyword？** 是的，这是一个容易犯的直觉错误。如果一个字段（如 `user_id`、`order_id`）是数字，但你永远不会对它做 `>` `<` 范围查询，只做 `term` 精确匹配，那把它映射为 `keyword` 比 `long` 更好。原因是 `keyword` 走倒排索引的精确匹配，比 BKD 树的精确匹配更快。

### 日期类型（date）

```json
"created_at": {
  "type": "date",
  "format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd||epoch_millis"
}
```

关键知识点：
- 不管用什么格式写入，ES **内部都存储为 epoch_millis（毫秒时间戳）**
- `format` 可以指定多种格式，用 `||` 分隔，写入时自动匹配
- 常用格式：`strict_date_optional_time`（ISO 8601）、`yyyy-MM-dd`、`epoch_millis`
- 日期类型走 **BKD 树索引**，支持范围查询 + Doc Values，支持排序和聚合

### 布尔类型（boolean）

接受 `true` / `false` / `"true"` / `"false"` / `""` 。

### 二进制类型（binary）

Base64 编码的字符串。默认不索引、不搜索、不存 Doc Values。仅存储在 `_source` 中。

### 类型全景一览

```
ES 字段类型
├── 字符串
│   ├── text      → 分词，全文搜索
│   └── keyword   → 不分词，精确匹配/排序/聚合
├── 数值
│   ├── long / integer / short / byte
│   ├── double / float / half_float
│   └── scaled_float
├── 日期
│   └── date      → 内部存为 epoch_millis
├── 布尔
│   └── boolean
├── 二进制
│   └── binary    → Base64，不索引
├── 复杂类型
│   ├── object    → JSON 对象（扁平化存储）          ← 2.4 节详讲
│   ├── nested    → 保持对象数组关联性               ← 2.4 节详讲
│   ├── flattened → 整个 JSON 作为 keyword           ← 2.4 节详讲
│   └── join      → 父子文档关系                     ← 2.4 节详讲
├── 特殊类型
│   ├── geo_point / geo_shape → 地理位置             ← 2.6 节简述
│   ├── completion → 自动补全（FST 结构）            ← 2.6 节简述
│   ├── ip         → IPv4/IPv6                       ← 2.6 节简述
│   ├── dense_vector → 向量（KNN 搜索）             ← 2.6 节简述
│   └── *_range    → 范围类型                        ← 2.6 节简述
└── 元字段
    ├── _source   → 原始 JSON
    ├── _id       → 文档 ID
    └── _routing  → 路由值
```

---

## 2.3 text vs keyword 深入——最重要的选型决策

这一节专门讲清楚「什么时候用 text、什么时候用 keyword、什么时候两个都要」。这是 Mapping 设计中最常见的决策。

### 默认行为：Multi-fields（多字段映射）

当你不指定 Mapping、让 ES 自动推断时，字符串字段会被自动映射为同时拥有 text 和 keyword 两种子字段：

```json
// ES 自动推断的结果（你在阶段 1 练习 12 中应该看到过）
"name": {
  "type": "text",
  "fields": {
    "keyword": {
      "type": "keyword",
      "ignore_above": 256
    }
  }
}
```

这意味着：
- `name` → text 类型，会分词，用于 `match` 全文搜索
- `name.keyword` → keyword 类型，不分词，用于 `term` 精确匹配 / 排序 / 聚合

### 选型决策表

| 字段示例 | 推荐类型 | 理由 |
|---------|---------|------|
| **商品标题**、**文章标题** | text + keyword（Multi-fields） | 需要全文搜索，也需要按标题排序、聚合 |
| **文章正文**、**评论内容** | 只要 text | 只做全文搜索，不需要排序聚合（也不该对这么长的文本聚合） |
| **订单号**、**用户 ID** | 只要 keyword | 只做精确匹配，不需要分词搜索 |
| **状态码**（active/inactive） | 只要 keyword | 枚举值，精确匹配 + 聚合 |
| **邮箱、手机号** | 只要 keyword | 精确匹配，不需要对 `user@example.com` 进行分词搜索 |
| **商品名称** | text + keyword | 需要搜索"华为手机"能找到"华为 Mate 60 手机"，也需要按品名聚合 |
| **标签（tags）** | keyword（数组） | 每个标签做精确匹配和聚合，不需要分词 |
| **地址** | text + keyword | 可能需要搜索地址中的关键词，也可能按完整地址去重 |

### 常见误区

**误区 1：对 text 字段用 term 查询**

```
# ❌ 错误示范：用 term 查 text 字段
GET /products/_search
{
  "query": {
    "term": {
      "name": "iPhone 15"    // name 是 text 类型
    }
  }
}
// 结果：搜不到任何文档！
```

**为什么？** `name` 是 text 类型，写入时被标准分词器拆成了 `["iphone", "15"]`（小写）。`term` 查询不分词，直接拿 `"iPhone 15"` 去匹配——倒排索引里没有这个完整 Term，所以匹配失败。

**正确做法：**
```
# ✅ 全文搜索用 match 查 text 字段
GET /products/_search
{
  "query": {
    "match": {
      "name": "iPhone 15"
    }
  }
}

# ✅ 精确匹配用 term 查 keyword 字段
GET /products/_search
{
  "query": {
    "term": {
      "name.keyword": "iPhone 15"
    }
  }
}
```

**误区 2：对 text 字段做排序/聚合**

```
# ❌ 会报错或产生不可预期的结果
GET /products/_search
{
  "sort": [
    { "name": "asc" }    // name 是 text 类型，没有 Doc Values
  ]
}

# ✅ 用 keyword 子字段排序
GET /products/_search
{
  "sort": [
    { "name.keyword": "asc" }
  ]
}
```

> **面试怎么答**："text 和 keyword 的区别？什么时候用哪个？"
>
> text 会分词建立倒排索引，适合全文搜索（match 查询），但没有 Doc Values，不能直接排序和聚合。keyword 不分词，整个值作为一个 Term，适合精确匹配（term 查询）和排序/聚合。生产中对于商品名称这类「既要搜索又要聚合」的字段，用 Multi-fields 同时映射 text 和 keyword 两个子字段。对于 ID、状态码等枚举值只用 keyword，对于文章正文等只需搜索的字段只用 text。

---

## 2.4 复杂类型——Object、Nested、Flattened、Join

当文档中包含嵌套的 JSON 结构时，ES 提供了几种不同的处理方式。它们的差异巨大，选错会导致查询结果错误或性能严重问题。

### Object 类型（默认）

当你在文档中放一个 JSON 对象，ES 默认将其映射为 `object` 类型。

```json
// 文档
{
  "name": "T恤套装",
  "skus": [
    { "color": "红色", "size": "M" },
    { "color": "蓝色", "size": "L" }
  ]
}
```

**Object 的致命问题——扁平化存储：**

ES 内部会把上面的文档**扁平化**存储成：

```json
{
  "name": "T恤套装",
  "skus.color": ["红色", "蓝色"],
  "skus.size": ["M", "L"]
}
```

关联性丢失了！`红色` 和 `M` 的对应关系、`蓝色` 和 `L` 的对应关系都没了。

```
# ❌ 这个查询会错误地返回上面的文档！
# 明明没有 "红色 + L" 的 SKU，但 ES 认为文档同时包含"红色"和"L"
GET /products/_search
{
  "query": {
    "bool": {
      "must": [
        { "term": { "skus.color": "红色" } },
        { "term": { "skus.size": "L" } }
      ]
    }
  }
}
```

**Object 适用场景**：嵌套对象不是数组（只有一层），或者你不需要在嵌套对象内做交叉字段查询。

```json
// 这种场景用 Object 没问题——地址只有一个，不存在关联性问题
{
  "name": "张三",
  "address": {
    "city": "北京",
    "street": "朝阳路 123 号"
  }
}
```

### Nested 类型

Nested 专门解决 Object 数组的关联性丢失问题。

```json
// Mapping 中声明 nested
PUT /products
{
  "mappings": {
    "properties": {
      "name": { "type": "text" },
      "skus": {
        "type": "nested",
        "properties": {
          "color": { "type": "keyword" },
          "size": { "type": "keyword" }
        }
      }
    }
  }
}
```

**Nested 的内部实现：**

```
Nested 的本质：每个嵌套对象是一个隐藏的独立 Lucene 文档。

主文档 doc_0:       { "name": "T恤套装" }
隐藏文档 doc_0_0:   { "skus.color": "红色", "skus.size": "M" }
隐藏文档 doc_0_1:   { "skus.color": "蓝色", "skus.size": "L" }
```

每个嵌套对象单独建立倒排索引，所以查询时可以在**同一个对象内**做精确关联：

```
# ✅ 使用 nested query 正确查询——不会错误匹配
GET /products/_search
{
  "query": {
    "nested": {
      "path": "skus",
      "query": {
        "bool": {
          "must": [
            { "term": { "skus.color": "红色" } },
            { "term": { "skus.size": "L" } }
          ]
        }
      }
    }
  }
}
// 结果：不返回任何文档（因为没有"红色 + L"的 SKU）✅ 正确！
```

**Nested 的代价：**
- 每个嵌套对象是一个隐藏文档 → 如果一个文档有 100 个嵌套对象，底层实际是 101 个 Lucene 文档
- 更新主文档或任何嵌套对象时，**整个文档（包括所有嵌套对象）都要重新索引**
- 查询需要使用特殊的 `nested` 查询包装，比普通查询慢

### Flattened 类型（ES 7.3+）

整个 JSON 对象被当作一个大的 keyword 索引。

```json
PUT /logs
{
  "mappings": {
    "properties": {
      "metadata": {
        "type": "flattened"
      }
    }
  }
}

// 写入——metadata 可以是任意结构
PUT /logs/_doc/1
{
  "metadata": {
    "env": "production",
    "version": "2.1.0",
    "features": {
      "dark_mode": true
    }
  }
}
```

Flattened 的特点：
- 所有叶子节点的值都作为 keyword 处理
- 可以用 `term` 查询查任一叶子值：`"metadata.env": "production"` ✅
- **不支持范围查询、不支持全文搜索、不支持聚合**
- 优势：不会因为写入动态 JSON 导致 Mapping 爆炸（字段数过多）

**适用场景**：日志的 metadata、用户自定义属性等结构不固定的 JSON 字段。

### Join 类型（Parent-Child）

文档之间建立父子关系，父子文档是独立的 Lucene 文档，可以独立更新。

```json
PUT /qa
{
  "mappings": {
    "properties": {
      "qa_relation": {
        "type": "join",
        "relations": {
          "question": "answer"    // question 是父，answer 是子
        }
      }
    }
  }
}

// 写入父文档（问题）
PUT /qa/_doc/q1
{
  "title": "什么是 Elasticsearch？",
  "qa_relation": "question"
}

// 写入子文档（答案）——必须指定 routing 确保与父文档在同一 shard
PUT /qa/_doc/a1?routing=q1
{
  "body": "ES 是基于 Lucene 的分布式搜索引擎",
  "qa_relation": {
    "name": "answer",
    "parent": "q1"
  }
}
```

**Join 的关键约束和特点：**
- 父子文档**必须在同一个 Shard**（通过 routing 保证）
- 查询时需要使用 `has_child` 或 `has_parent` 查询
- 查询性能是所有关系类型中**最差的**（需要跨文档做 Join）
- 优势：子文档可以独立更新，不影响父文档的索引

---

## 2.5 Nested vs Object vs Join 选型——面试必考对比

```
                        你需要嵌套结构吗？
                              │
                      ┌───────┴───────┐
                      │               │
                    是的             不需要
                      │           → 用普通字段
                      │
              是数组还是单个对象？
                      │
              ┌───────┴───────┐
              │               │
           单个对象         对象数组
          → Object            │
                      需要精确关联查询吗？
                              │
                      ┌───────┴───────┐
                      │               │
                    不需要           需要
                  → Object            │
                              子文档需要独立频繁更新吗？
                                      │
                              ┌───────┴───────┐
                              │               │
                            不需要           需要
                          → Nested         → Join
```

### 三种方式完整对比

| 维度 | Object | Nested | Join (Parent-Child) |
|------|--------|--------|---------------------|
| **关联性** | ❌ 数组中各对象字段关联丢失 | ✅ 保持关联 | ✅ 保持关联 |
| **底层实现** | 扁平化为同一文档的字段 | 每个对象是隐藏的独立 Lucene 文档 | 父子是独立 Lucene 文档 |
| **查询方式** | 普通查询 | 必须用 `nested` 查询 | 必须用 `has_child`/`has_parent` 查询 |
| **查询性能** | 🟢 最快 | 🟡 中等 | 🔴 最慢（需要跨文档 Join） |
| **写入/更新代价** | 🟢 低 | 🔴 高（任何改动需重建整个文档及所有嵌套对象） | 🟢 低（子文档独立更新） |
| **适用场景** | 单对象嵌套，或不需要精确关联查询 | 对象数组，需要精确关联但更新频率不高 | 子文档数量大且需频繁独立更新 |
| **实际案例** | 用户的地址信息 | 商品的 SKU 列表 | 问答系统（1 个问题 N 个回答） |

### 实际场景举例

**电商商品 SKU：用 Nested**

一个商品有多个 SKU（颜色+尺码组合），需要精确查询"红色 M 码"。SKU 一般随商品一起更新，不需要独立更新。

**博客文章评论：用 Join 或 反范式**

一篇文章可能有上千条评论，评论频繁新增。如果用 Nested，每新增一条评论就要重建整篇文章的索引。这时有两种选择：
- 用 Join：文章是父文档，评论是子文档，新增评论只写一个新的子文档
- 反范式：文章和评论分成两个独立的索引，查询时分别查（更常用）

> **面试怎么答**："Nested 和 Object 的区别？举个实际例子？"
>
> Object 类型在存储对象数组时会把字段扁平化，丢失对象内部字段的关联性。比如商品有两个 SKU：{红色, M} 和 {蓝色, L}，用 Object 存储后查询"红色 + L"会错误命中，因为 ES 只知道这个文档同时包含红色和 L，不知道它们是否属于同一个 SKU。Nested 类型会把每个数组元素作为隐藏的独立 Lucene 文档存储，保持关联性，查询时用 nested query 可以精确匹配。代价是更新时整个文档和所有嵌套文档都需要重新索引，所以适合对象数量有限且更新频率不高的场景。

---

## 2.6 特殊类型——知道有什么、什么时候用

这些类型面试很少深入考查，但在特定业务场景中是必备的。了解其用途，遇到需求时知道往哪个方向查就行。

**什么时候你会遇到这些类型？**

| 业务需求 | 对应类型 |
|---------|----------|
| 外卖/打车/门店搜索——"找附近 3 公里的餐厅" | `geo_point` |
| 搜索框输入联想——用户打 "华" 就弹出 "华为手机" | `completion` |
| 日志分析——按 IP 段过滤攻击流量 | `ip` |
| 酒店预订——"找 5 月 1 日到 5 月 3 日有空房的酒店" | `date_range` |
| AI 语义搜索——搜 "苹果" 区分水果和手机品牌 | `dense_vector` |

### geo_point 与 geo_shape

```json
// geo_point：经纬度坐标
"location": {
  "type": "geo_point"
}

// 写入
{ "location": { "lat": 39.9042, "lon": 116.4074 } }
// 或
{ "location": "39.9042,116.4074" }
// 或
{ "location": [116.4074, 39.9042] }  // 注意：数组格式是 [lon, lat]
```

- 支持 `geo_distance`（附近 N 公里内）、`geo_bounding_box`（矩形范围内）等查询
- 支持按距离排序
- 门店搜索、外卖配送、LBS 应用的核心字段

`geo_shape` 可以存储多边形、线段等复杂地理形状，支持形状相交、包含等空间查询。

### completion 类型

```json
"suggest": {
  "type": "completion"
}
```

- 基于 **FST（Finite State Transducer）** 数据结构，全部加载到内存中
- 提供前缀搜索能力，专为搜索框的「输入即搜索」（search-as-you-type）设计
- 性能极快（内存查找），但消耗内存
- 阶段 10 会详细讲 Suggester 的完整能力

### ip 类型

支持 IPv4 和 IPv6，可以做 IP 范围查询和 CIDR 查询。

```json
"client_ip": { "type": "ip" }
// 查询：{ "term": { "client_ip": "192.168.1.1" } }
// 范围：{ "range": { "client_ip": { "gte": "192.168.0.0", "lte": "192.168.255.255" } } }
```

### 范围类型

`integer_range`、`float_range`、`long_range`、`double_range`、`date_range`、`ip_range`

```json
// 适用于时间段、价格区间等
"valid_period": {
  "type": "date_range"
}

// 写入
{ "valid_period": { "gte": "2024-01-01", "lte": "2024-12-31" } }
```

### dense_vector（ES 7.3+，ES 8.x 增强）

```json
"embedding": {
  "type": "dense_vector",
  "dims": 768     // 向量维度
}
```

- 用于存储文本/图片的向量表示
- ES 8.x 支持 KNN（K-Nearest Neighbors）搜索
- 是语义搜索、相似度推荐、AI 搜索的基础
- 阶段 10 会详细介绍向量搜索

---

## 2.7 Dynamic Mapping——ES 的自动类型推断

当你不预先定义 Mapping、直接写入文档时，ES 会根据 JSON 值自动推断字段类型。

### 推断规则

| JSON 值 | 推断的 ES 类型 |
|---------|--------------|
| `"hello world"` | text + keyword（Multi-fields） |
| `123` | long |
| `1.23` | float |
| `true` / `false` | boolean |
| `"2024-01-01"` | date（如果符合日期格式） |
| `{ "key": "value" }` | object |
| `[1, 2, 3]` | long（按第一个元素推断） |

### 推断出错的典型场景

```json
// 你期望 order_id 是 keyword（做精确匹配），但 ES 推断成了 text+keyword
{ "order_id": "ORD-2024-001" }   // 被推成 text+keyword，浪费了 text 索引空间

// 你期望 status 是 keyword，实际没问题（但如果第一条数据的 status 是数字呢？）
{ "status": 1 }   // 被推成 long，后面想存 "active" 就会报类型冲突

// 你期望 timestamp 是 date，但格式不在默认识别范围内
{ "timestamp": "01/15/2024" }   // 被推成 text+keyword，而不是 date

// 更隐蔽的问题：第一条文档没有某个字段，第二条有
// 第二条文档的类型推断可能和你预期不同
```

> **核心结论**：Dynamic Mapping 的自动推断在生产环境几乎必然会出问题。**认真设计 Mapping 是 ES 使用的第一步**。

### dynamic 参数——控制自动推断行为

`dynamic` 参数可以在索引级别或对象级别设置，控制遇到未定义字段时的行为：

| dynamic 值 | 遇到未定义字段时 | 适用场景 |
|------------|----------------|---------|
| `true`（默认） | 自动推断类型，添加到 Mapping | 开发测试环境 |
| `false` | 字段数据写入 _source 但**不索引**（不能搜索） | 需要存储但不需要搜索的动态字段 |
| `strict` | **直接报错拒绝写入** | **生产环境推荐**——严格控制 Mapping |
| `runtime`（ES 7.11+） | 作为 Runtime Field 动态添加，不建索引 | 偶尔需要查询但不想消耗索引空间的字段 |

```json
PUT /products
{
  "mappings": {
    "dynamic": "strict",     // 索引级别：严格模式
    "properties": {
      "name": { "type": "text" },
      "price": { "type": "float" },
      "metadata": {
        "type": "object",
        "dynamic": "true"    // metadata 内部允许动态字段
      }
    }
  }
}

// 写入包含未定义字段的文档
PUT /products/_doc/1
{
  "name": "iPhone 15",
  "price": 5999,
  "color": "黑色"            // ❌ 报错！color 未在 Mapping 中定义
}
```

> **生产最佳实践**：索引级别设 `dynamic: strict`，杜绝意外字段进入 Mapping。如果有确实需要存储动态数据的字段（如用户自定义属性），对那个特定的 object 字段设 `dynamic: true` 或用 `flattened` 类型。

### dynamic_templates——自定义推断规则

当你确实需要 Dynamic Mapping（比如日志场景，字段结构不确定），可以通过 `dynamic_templates` 自定义推断规则：

```json
PUT /logs
{
  "mappings": {
    "dynamic_templates": [
      {
        "strings_as_keyword": {
          "match_mapping_type": "string",
          "mapping": {
            "type": "keyword"          // 所有字符串都映射为 keyword，不做分词
          }
        }
      },
      {
        "long_as_integer": {
          "match_mapping_type": "long",
          "mapping": {
            "type": "integer"          // 所有整数用 integer 而非 long（省空间）
          }
        }
      },
      {
        "message_fields": {
          "match": "*_content",        // 字段名以 _content 结尾的
          "mapping": {
            "type": "text",            // 用 text，做全文搜索
            "analyzer": "standard"     // 这里用 standard 示意；阶段 3 学完分词后可替换为 ik_max_word
          }
        }
      }
    ]
  }
}
```

`dynamic_templates` 的匹配条件：
- `match_mapping_type`：按 JSON 值类型匹配
- `match` / `unmatch`：按字段名模式匹配（支持通配符）
- `path_match` / `path_unmatch`：按字段路径匹配（如 `user.address.*`）

---

## 2.8 Multi-fields——一个字段多种索引方式

Multi-fields 是 ES 非常实用的能力：**同一份数据，建立多种不同的索引方式，服务不同的查询需求**。

### 基本用法

你在 2.3 节已经见过最常见的 Multi-fields——text + keyword：

```json
"name": {
  "type": "text",           // 主字段：分词，用于全文搜索
  "fields": {
    "keyword": {
      "type": "keyword"     // 子字段：不分词，用于排序/聚合
    }
  }
}
```

### 进阶用法：一个字段三种索引

> 下面的示例使用了 `ik_max_word` 和 `edge_ngram_analyzer`，它们是自定义/第三方分词器。分词器的完整知识将在**阶段 3** 中系统学习。这里只需要理解 Multi-fields 的**结构设计思路**——同一字段可以用不同 Analyzer 建立多套索引，服务不同查询场景。

```json
"title": {
  "type": "text",
  "analyzer": "ik_max_word",           // 主字段：IK 最细粒度分词，用于搜索（阶段 3 详讲）
  "fields": {
    "keyword": {
      "type": "keyword"               // 子字段 1：不分词，用于排序/聚合
    },
    "autocomplete": {
      "type": "text",
      "analyzer": "edge_ngram_analyzer"  // 子字段 2：边缘 N-gram，用于自动补全（阶段 3 详讲）
    }
  }
}
```

这样一个 `title` 字段就支持了三种使用场景：
- `title` → 全文搜索（match 查询）
- `title.keyword` → 排序和聚合
- `title.autocomplete` → 搜索框自动补全

### Multi-fields 的存储代价

每个子字段会独立构建一套索引结构。所以 Multi-fields 不是免费的——子字段越多，写入越慢，存储越大。只为真正需要的查询场景添加子字段。

---

## 2.9 索引模板与别名——索引级别的管理工具

前面 2.2–2.8 节讲的是**字段级别**的设计（每个字段怎么映射）。这一节讲**索引级别**的管理工具，在生产环境中不可或缺。

### Index Template（索引模板）

当你按时间创建索引（如 `logs-2024.01.01`、`logs-2024.01.02`），每个索引都需要相同的 Mapping 和 Settings。手动给每个新索引配置 Mapping 不现实——这就是 Index Template 的用途。

```json
// 创建模板：所有匹配 logs-* 模式的新索引自动应用这个 Mapping
PUT /_index_template/logs_template
{
  "index_patterns": ["logs-*"],
  "priority": 100,
  "template": {
    "settings": {
      "number_of_shards": 3,
      "number_of_replicas": 1,
      "refresh_interval": "5s"
    },
    "mappings": {
      "dynamic": "strict",
      "properties": {
        "timestamp": { "type": "date" },
        "level": { "type": "keyword" },
        "message": { "type": "text" },
        "service": { "type": "keyword" }
      }
    }
  }
}
// 注意：这里 message 使用默认的 standard 分词器。
// 学完阶段 3（分词）后，可优化为 "analyzer": "ik_max_word", "search_analyzer": "ik_smart"

// 现在创建 logs-2024.01.01 索引时，不需要指定 mapping/settings——自动应用模板
PUT /logs-2024.01.01
```

**关键参数：**
- `index_patterns`：模式匹配，支持 `*` 通配符
- `priority`：多个模板匹配同一索引时，优先级高的生效
- `version`：模板版本号，方便管理

### Component Template（ES 7.8+）

可组合的模板模块。把 Mapping 和 Settings 拆成独立的组件，在 Index Template 中组合使用。

```json
// 组件模板 1：通用的基础 Settings
PUT /_component_template/base_settings
{
  "template": {
    "settings": {
      "number_of_shards": 3,
      "number_of_replicas": 1
    }
  }
}

// 组件模板 2：日志的 Mapping
PUT /_component_template/log_mappings
{
  "template": {
    "mappings": {
      "properties": {
        "timestamp": { "type": "date" },
        "level": { "type": "keyword" },
        "message": { "type": "text" }
      }
    }
  }
}

// Index Template 组合两个组件模板
PUT /_index_template/logs_template
{
  "index_patterns": ["logs-*"],
  "composed_of": ["base_settings", "log_mappings"]
}
```

好处：多个 Index Template 可以共享相同的组件模板，避免重复配置、便于统一修改。

### Index Alias（索引别名）

别名是指向一个或多个索引的「虚拟名称」。客户端通过别名访问，不直接操作真实索引名。

```
Index Alias 的本质：

  别名 "products"
       │
       ├──→ products-v1   （旧版本）
       └──→ products-v2   （新版本）  ← 当前指向

  客户端始终访问 "products"，切换版本只需修改别名指向。
```

```json
// 创建别名
POST /_aliases
{
  "actions": [
    { "add": { "index": "products-v1", "alias": "products" } }
  ]
}

// 零停机切换：原子操作——同时移除旧指向、添加新指向
POST /_aliases
{
  "actions": [
    { "remove": { "index": "products-v1", "alias": "products" } },
    { "add": { "index": "products-v2", "alias": "products" } }
  ]
}
```

**Alias 的三大用途：**

| 用途 | 说明 |
|------|------|
| **零停机索引切换** | Reindex 完成后，切换别名指向新索引，客户端无感知 |
| **读写分离** | `products-write` 指向活跃索引，`products-read` 指向优化后的索引 |
| **多索引聚合查询** | 一个 alias 指向多个索引（如 `logs` 指向所有 `logs-2024.*`），查询时自动跨索引搜索 |

**Alias 还支持 filter：**

```json
// 带过滤条件的 alias——查询 "products-active" 时自动只返回 status=active 的文档
POST /_aliases
{
  "actions": [
    {
      "add": {
        "index": "products-v1",
        "alias": "products-active",
        "filter": { "term": { "status": "active" } }
      }
    }
  ]
}
```

### Reindex（跨索引数据迁移）

**修改已有字段 Mapping 的唯一方式。** 完整流程：

```
步骤 1：创建新索引（正确的 Mapping）
步骤 2：Reindex 迁移数据
步骤 3：验证数据
步骤 4：切换 Alias
步骤 5：删除旧索引
```

```json
// 步骤 1：创建新索引
PUT /products-v2
{
  "mappings": {
    "properties": {
      "name": { "type": "text" },
      "status": { "type": "keyword" }       // 原来是 text，现在改为 keyword
    }
  }
}

// 步骤 2：Reindex
POST /_reindex
{
  "source": { "index": "products-v1" },
  "dest": { "index": "products-v2" }
}

// 步骤 3：验证数据量一致
GET /products-v1/_count
GET /products-v2/_count

// 步骤 4：切换 Alias（原子操作）
POST /_aliases
{
  "actions": [
    { "remove": { "index": "products-v1", "alias": "products" } },
    { "add": { "index": "products-v2", "alias": "products" } }
  ]
}

// 步骤 5：确认无误后删除旧索引
DELETE /products-v1
```

**Reindex 的注意事项：**
- 大数据量时非常耗时——可以用 `slices` 参数并行化（`"slices": 5`）
- 支持 `script` 在迁移过程中转换数据
- 支持远程 reindex（从另一个 ES 集群迁移数据）
- 迁移期间新写入的数据需要同步到新索引（可以通过双写或重跑增量）

### Rollover（自动滚动）

配合 Alias 实现时间序列索引的自动滚动创建：

```json
// 创建初始索引 + Alias
PUT /logs-000001
{
  "aliases": {
    "logs-write": { "is_write_index": true }
  }
}

// 设置 Rollover 条件：达到 50GB 或 30 天时自动创建新索引
POST /logs-write/_rollover
{
  "conditions": {
    "max_age": "30d",
    "max_size": "50gb",
    "max_docs": 100000000
  }
}
```

当条件满足时，ES 自动创建 `logs-000002`，并将 `logs-write` 别名指向新索引。阶段 10 会结合 ILM（索引生命周期管理）详细介绍完整的时间序列索引管理方案。

> **面试怎么答**："Index Alias 有什么用？"
>
> Index Alias 是索引的虚拟名称，客户端通过 Alias 访问而不直接操作真实索引。它有三个核心用途：第一，零停机索引切换——Reindex 修改 Mapping 后，通过原子操作切换 Alias 指向新索引，客户端无感知；第二，读写分离——写操作走 write alias 指向的活跃索引，读操作走 read alias 指向的优化后索引；第三，多索引聚合——一个 Alias 可以指向多个索引，实现跨索引透明搜索，比如日志按天分索引后用一个 Alias 覆盖所有历史日志。

---

## 2.10 索引设计模式——面试系统设计题的基础

前面学的是「怎么给字段选类型」，这一节是「怎么组织索引本身」。这是**索引架构层面**的设计决策，面试系统设计题几乎必考。

### 该用哪种模式？——决策流程

```
你的数据是什么类型？
        │
  ┌─────┴──────────────────────────────┐
  │                                    │
时间序列数据                         业务实体数据
（日志/指标/订单流水）              （商品/用户/文章）
  │                                    │
  ▼                                    │
模式 1：按时间分索引              是否多租户 SaaS？
（+ ILM + Rollover）                    │
                               ┌───────┴───────┐
                               │               │
                              不是             是
                               │               │
                               ▼               ▼
                        是否需要极致         模式 2：多租户
                        查询性能？            │
                               │       ┌──────┴──────┐
                         ┌─────┴─────┐ │             │
                         │           │ 租户少         租户多
                        不是        是  隔离要求高     数据均匀
                         │          │  → 每租户       → 大索引
                         ▼          ▼    一个索引      + routing
                    模式 3        模式 4
                    宽表反范式    读写分离
```

> **大多数场景**：业务实体数据用模式 3（宽表反范式）就够了——这是最常用的模式。模式 4（读写分离）是模式 3 的性能增强版。

### 模式 1：按时间分索引

**最常用的索引设计模式**，适用于日志、订单、消息等时间序列数据。

```
索引名称              内容                    状态
─────────────────────────────────────────────────────
logs-2024.01.01      1月1日的日志            Cold（只读，已优化）
logs-2024.01.02      1月2日的日志            Cold
...
logs-2024.03.15      3月15日的日志           Warm（只读，偶尔查询）
...
logs-2024.04.10      4月10日的日志           Hot（正在写入和频繁查询）
logs-2024.04.11      4月11日的日志           Hot（正在写入）

通过 Alias：
  "logs-write" → logs-2024.04.11           (写入入口)
  "logs-read"  → logs-2024.*               (查询入口，覆盖所有)
  "logs-recent" → logs-2024.04.*           (最近一个月)
```

**配套工具链：**
- **Index Template**：自动为新创建的 `logs-*` 索引应用 Mapping 和 Settings
- **Rollover**：满足条件自动创建下一个索引
- **ILM (Index Lifecycle Management)**：自动管理索引的 Hot → Warm → Cold → Delete 生命周期（阶段 10 详讲）
- **Alias**：客户端通过别名访问，不关心底层有多少个索引

**优势：**
- 旧数据可以独立压缩、force merge、迁移到低成本存储
- 删除旧数据只需删除整个索引，不需要逐条 delete（极快）
- 查询可以精确限定时间范围，避免扫描全量数据

### 模式 2：多租户索引设计

SaaS 系统中多个租户共用一套 ES 集群，有两种设计方案：

**方案 A：一个大索引 + 按租户路由**

```json
PUT /products
{
  "mappings": {
    "properties": {
      "tenant_id": { "type": "keyword" },
      "name": { "type": "text" },
      "price": { "type": "float" }
    }
  }
}

// 写入时指定 routing
PUT /products/_doc/1?routing=tenant_001
{
  "tenant_id": "tenant_001",
  "name": "iPhone 15",
  "price": 5999
}

// 查询时也指定 routing——只查一个 shard，性能好
GET /products/_search?routing=tenant_001
{
  "query": {
    "bool": {
      "filter": [
        { "term": { "tenant_id": "tenant_001" } }
      ]
    }
  }
}
```

| 优点 | 缺点 |
|------|------|
| 管理简单，只有一个索引 | 数据隔离弱（所有租户在同一索引） |
| 查询时用 routing 只扫一个 shard，性能好 | 大租户可能导致数据倾斜（某个 shard 过大） |
| 适合租户数量多（几千个）且数据量差异不大 | 无法为不同租户定制 Mapping |

**方案 B：每个租户一个索引**

```
tenant_001_products
tenant_002_products
tenant_003_products
...
```

| 优点 | 缺点 |
|------|------|
| 数据完全隔离 | 索引数过多时 Master 节点管理压力大 |
| 可以为不同租户定制 Mapping 和 Settings | 资源利用率低（很多小索引有大量空 shard） |
| 适合租户数量少（几十个）且隔离要求严格 | 跨租户查询不方便 |

**选型决策：**
- 租户 < 100 且隔离要求高 → 方案 B
- 租户 > 100 且数据量均匀 → 方案 A
- 折中方案：按租户分组，每组一个索引

### 模式 3：宽表反范式设计

**ES 不擅长 JOIN**——所以在写入时就把关联数据打平到一个文档中。

```
MySQL 范式设计（三张表）：
  orders: { order_id, user_id, product_id, amount }
  users:  { user_id, user_name, user_level }
  products: { product_id, product_name, brand }

ES 反范式设计（一个扁平文档）：
  {
    "order_id": "ORD001",
    "amount": 5999,
    "user_name": "张三",         ← 冗余了 users 表的数据
    "user_level": "VIP",         ← 冗余了 users 表的数据
    "product_name": "iPhone 15", ← 冗余了 products 表的数据
    "brand": "Apple"             ← 冗余了 products 表的数据
  }
```

**优势**：查询只需扫描一个索引，无需 JOIN，速度极快。

**代价**：
- 数据冗余——同一个用户名可能出现在上万个订单文档中
- 源数据更新时需要同步更新所有相关文档——用户改名要更新几万条订单
- **这就是为什么 ES 通常不做主数据库**，MySQL 是数据源，ES 只是搜索副本

> **核心理念**：ES 的数据模型是「为查询而设计」的。MySQL 追求存储不冗余（范式化），ES 追求查询够快（反范式）。

### 模式 4：读写分离索引

```
写入流程：
  业务数据 → 写入 "products-write"(alias) → products-v2（活跃索引）

读取流程：
  用户搜索 → 查询 "products-read"(alias)  → products-v1（已 force merge + 优化）

定期切换：
  1. 停止向 products-v2 写入（或切换 write alias）
  2. force merge products-v2 为单 Segment
  3. 将 read alias 切换到 products-v2
  4. 新写入切到 products-v3
```

适用场景：对查询性能要求极高的场景（如商品搜索主页）。force merge 后的索引只有一个 Segment，查询时不需要遍历多个 Segment，性能最优。

---

## 面试高频题与参考答案

### Q1：text 和 keyword 的区别？什么时候用哪个？

**答**：它们是 ES 中两种最核心的字符串类型，底层索引行为完全不同。

text 会经过 Analyzer 分词后建立倒排索引，适合全文搜索（match 查询），但没有 Doc Values，不能直接做排序和聚合。keyword 不分词，整个字段值作为一个 Term 存入倒排索引，适合精确匹配（term 查询），同时自动构建 Doc Values 支持排序和聚合。

选型原则：
- 只做精确匹配的字段（ID、状态码、枚举值）→ keyword
- 只做全文搜索的字段（文章正文、评论）→ text
- 既要搜索又要排序/聚合的字段（商品名、标题）→ Multi-fields，同时有 text 和 keyword 两个子字段

一个常见踩坑点是用 term 查询去查 text 字段——因为 text 被分词了，"Hello World" 在倒排索引中是 "hello" 和 "world" 两个 Term，用 term 查 "Hello World" 是匹配不到的。

### Q2：Nested 和 Object 的区别？举个实际例子？

**答**：Object 类型在存储对象数组时会把字段扁平化，丢失对象间的字段关联性。比如一个商品有两个 SKU：`{红色, M}` 和 `{蓝色, L}`，用 Object 存储后 ES 内部变成 `color: [红色, 蓝色], size: [M, L]`，查询"红色 + L"的组合会错误匹配，因为 ES 不知道红色和 M 才是一对。

Nested 类型在底层把每个数组元素存为一个隐藏的独立 Lucene 文档，保持了字段关联性。查询时用 nested query 可以在同一个对象内做精确匹配，"红色 + L"就不会命中了。

Nested 的代价是：每个嵌套对象是一个隐藏文档，一个文档有 100 个嵌套对象就是 101 个 Lucene 文档；更新时整个文档和所有嵌套对象都要重新索引。所以适合嵌套数量有限、更新频率不高的场景，比如商品的 SKU 列表。如果子文档量大且需要频繁独立更新（如文章的评论），应该考虑 Join 类型或者干脆拆成独立索引做反范式设计。

### Q3：ES 的 mapping 创建后能修改吗？如果需要修改怎么办？

**答**：ES 的 Mapping 创建后只能追加新字段，不能修改已有字段的类型或分词器。这是因为字段类型决定了底层索引结构（倒排索引、BKD 树、Doc Values），修改类型意味着所有已有数据的索引都需要重建，ES 不支持原地重建。

如果确实需要修改，标准做法是：
1. 创建新索引，配置正确的 Mapping
2. 用 `_reindex` API 把旧索引数据迁移到新索引
3. 验证数据完整性
4. 用 Alias 原子操作切换读写指向
5. 确认无误后删除旧索引

这个过程中需要注意迁移期间的新写入数据同步问题（可以通过双写或重跑增量解决），大数据量时可以用 `slices` 参数并行化 Reindex。这也是为什么我们总是建议在写入第一条数据之前就设计好 Mapping，避免后期修改的高成本。

### Q4：如何设计一个电商商品的索引 mapping？

**答**：以一个典型电商商品搜索场景为例：

```json
PUT /products
{
  "settings": {
    "number_of_shards": 5,
    "number_of_replicas": 1
  },
  "mappings": {
    "dynamic": "strict",
    "properties": {
      "product_id": { "type": "keyword" },
      "name": {
        "type": "text",
        "fields": {
          "keyword": { "type": "keyword" }
        }
      },
      "brand": { "type": "keyword" },
      "category": { "type": "keyword" },
      "price": { "type": "scaled_float", "scaling_factor": 100 },
      "sales_count": { "type": "integer" },
      "status": { "type": "keyword" },
      "description": {
        "type": "text"
      },
      "tags": { "type": "keyword" },
      "skus": {
        "type": "nested",
        "properties": {
          "sku_id": { "type": "keyword" },
          "color": { "type": "keyword" },
          "size": { "type": "keyword" },
          "stock": { "type": "integer" },
          "price": { "type": "scaled_float", "scaling_factor": 100 }
        }
      },
      "store_location": { "type": "geo_point" },
      "created_at": { "type": "date" },
      "updated_at": { "type": "date" }
    }
  }
}
```

设计要点：
- `product_id` 用 keyword 而非 long（只做精确匹配，不做范围查询）
- `name` 用 Multi-fields：text（全文搜索）+ keyword（排序聚合）
- `description` 只用 text（只搜索，不排序聚合），不需要 keyword 子字段
- `price` 用 scaled_float 避免浮点精度问题
- `skus` 用 nested 保持 SKU 内部字段关联性
- `store_location` 用 geo_point 支持附近门店搜索
- `dynamic: strict` 防止意外字段进入 Mapping
- 数据来源是 MySQL，ES 做搜索副本，通过 CDC 或 MQ 同步

> **分词器优化（阶段 3 后补充）**：上面的 `name` 和 `description` 使用了默认的 `standard` 分词器。学完阶段 3（分词）后，应该优化为：`"analyzer": "ik_max_word", "search_analyzer": "ik_smart"`——索引时用最细粒度分词增加召回率，搜索时用最粗粒度分词提高精准度。这是中文搜索的标准配置。

### Q5：Index Alias 有什么用？

**答**：Alias 是索引的虚拟名称，客户端通过 Alias 访问，不直接操作物理索引名。核心用途有三个：

第一是零停机索引切换。当需要修改 Mapping 时，创建新索引 → Reindex 数据 → 用 Alias 原子切换，客户端全程无感知。

第二是读写分离。用 `write-alias` 指向正在写入的活跃索引，`read-alias` 指向已经 force merge 优化过的索引，写入和查询互不影响。

第三是多索引透明聚合。日志按天分索引时，一个 Alias 可以指向所有 `logs-2024.*` 索引，查询时就像查一个大索引一样。Alias 还支持 filter，比如 `products-active` 这个 Alias 自动过滤 `status=active` 的文档。

### Q6：日志类数据的索引怎么设计？

**答**：日志数据的特点是只增不改、时间序列、数据量大、旧数据价值递减。索引设计采用「按时间分索引 + ILM + Alias」的模式：

1. **按天/周分索引**：`logs-2024.01.01`、`logs-2024.01.02`，通过 Index Template 自动为新索引应用 Mapping 和 Settings
2. **Alias**：`logs-write` 指向当前活跃索引（Rollover 自动切换），`logs-read` 指向所有历史索引
3. **ILM**：自动管理 Hot → Warm → Cold → Delete 生命周期——Hot 阶段在高性能 SSD 节点上处理写入和频繁查询，Warm 阶段数据只读、可迁移到普通磁盘，Cold 阶段做压缩、偶尔查询，超过保留期自动删除
4. **删除旧数据**：直接删除整个索引，比逐条 delete 快得多（DELETE /logs-2024.01.01 就行）

这种设计的核心好处是：新旧数据的运维完全独立——旧索引可以 force merge 压缩、迁移到低成本存储，新索引保持高性能写入。

---

## 动手实践

### 练习 1：创建电商商品索引 + Multi-fields + Nested

```
# 1. 创建索引（完整 Mapping）
PUT /shop_products
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0
  },
  "mappings": {
    "dynamic": "strict",
    "properties": {
      "product_id": { "type": "keyword" },
      "name": {
        "type": "text",
        "fields": {
          "keyword": { "type": "keyword" }
        }
      },
      "brand": { "type": "keyword" },
      "category": { "type": "keyword" },
      "price": { "type": "float" },
      "tags": { "type": "keyword" },
      "description": { "type": "text" },
      "skus": {
        "type": "nested",
        "properties": {
          "color": { "type": "keyword" },
          "size": { "type": "keyword" },
          "stock": { "type": "integer" }
        }
      },
      "store_location": { "type": "geo_point" },
      "status": { "type": "keyword" },
      "created_at": { "type": "date" }
    }
  }
}

# 2. 写入测试数据
POST /_bulk
{"index": {"_index": "shop_products", "_id": "1"}}
{"product_id": "P001", "name": "华为 Mate 60 Pro", "brand": "华为", "category": "手机", "price": 6999, "tags": ["5G", "旗舰", "鸿蒙"], "description": "华为最新旗舰手机，搭载麒麟芯片", "skus": [{"color": "黑色", "size": "256GB", "stock": 100}, {"color": "白色", "size": "512GB", "stock": 50}], "store_location": {"lat": 39.9042, "lon": 116.4074}, "status": "active", "created_at": "2024-01-15"}
{"index": {"_index": "shop_products", "_id": "2"}}
{"product_id": "P002", "name": "iPhone 15 Pro Max", "brand": "Apple", "category": "手机", "price": 9999, "tags": ["5G", "旗舰", "iOS"], "description": "Apple 最新旗舰手机，A17 Pro 芯片", "skus": [{"color": "黑色", "size": "256GB", "stock": 200}, {"color": "蓝色", "size": "1TB", "stock": 30}], "store_location": {"lat": 31.2304, "lon": 121.4737}, "status": "active", "created_at": "2024-01-20"}
{"index": {"_index": "shop_products", "_id": "3"}}
{"product_id": "P003", "name": "小米 14 Ultra", "brand": "小米", "category": "手机", "price": 5999, "tags": ["5G", "影像", "旗舰"], "description": "小米影像旗舰手机，徕卡联合设计", "skus": [{"color": "黑色", "size": "512GB", "stock": 150}, {"color": "白色", "size": "512GB", "stock": 80}], "store_location": {"lat": 22.5431, "lon": 114.0579}, "status": "active", "created_at": "2024-02-01"}

# 3. 验证 Mapping
GET /shop_products/_mapping

# 4. 验证 strict 模式——尝试写入未定义字段（应该报错）
PUT /shop_products/_doc/99
{
  "product_id": "P099",
  "name": "测试商品",
  "brand": "测试",
  "category": "测试",
  "price": 99,
  "unknown_field": "这个字段没有在 Mapping 中定义"
}
# 预期结果：抛出 strict_dynamic_mapping_exception 错误

# 5. 体验 Object 扁平化问题 vs Nested 精确查询
# ──────────────────────────────────────────────────
# 为了严格对比，我们额外创建一个 Object 版本的索引

# 5a. 创建 Object 版本（skus 是默认的 object 类型）
PUT /shop_products_object
{
  "settings": { "number_of_shards": 1, "number_of_replicas": 0 },
  "mappings": {
    "properties": {
      "product_id": { "type": "keyword" },
      "name": { "type": "text" },
      "skus": {
        "type": "object",
        "properties": {
          "color": { "type": "keyword" },
          "size": { "type": "keyword" }
        }
      }
    }
  }
}

# 5b. 向 Object 版本写入数据
PUT /shop_products_object/_doc/1
{
  "product_id": "P002", "name": "iPhone 15 Pro Max",
  "skus": [
    { "color": "黑色", "size": "256GB" },
    { "color": "蓝色", "size": "1TB" }
  ]
}

# 5c. 在 Object 版本上查 "黑色 + 1TB"（这个 SKU 组合不存在）
GET /shop_products_object/_search
{
  "query": {
    "bool": {
      "must": [
        { "term": { "skus.color": "黑色" } },
        { "term": { "skus.size": "1TB" } }
      ]
    }
  }
}
# ❌ 预期：返回了 iPhone 15！Object 扁平化丢失了关联性
# 解释：ES 内部存储变成了 skus.color=[黑色,蓝色], skus.size=[256GB,1TB]
#       文档同时包含"黑色"和"1TB"→ 错误命中

# 5d. 在 Nested 版本（shop_products）上做相同查询
GET /shop_products/_search
{
  "query": {
    "nested": {
      "path": "skus",
      "query": {
        "bool": {
          "must": [
            { "term": { "skus.color": "黑色" } },
            { "term": { "skus.size": "1TB" } }
          ]
        }
      }
    }
  }
}
# ✅ 预期：不返回任何文档。Nested 保持了每个 SKU 内部的关联性

# 5e. 清理 Object 版本
DELETE /shop_products_object

# 6. 体验 text vs keyword 的差异
# match 查 text 字段（能搜到）
GET /shop_products/_search
{
  "query": {
    "match": { "name": "华为手机" }
  }
}

# term 查 keyword 字段（精确匹配）
GET /shop_products/_search
{
  "query": {
    "term": { "name.keyword": "华为 Mate 60 Pro" }
  }
}

# term 查 text 字段（通常搜不到——理解为什么）
GET /shop_products/_search
{
  "query": {
    "term": { "name": "华为 Mate 60 Pro" }
  }
}
```

### 练习 2：Index Template + 验证自动应用

```
# 1. 创建 Index Template
PUT /_index_template/shop_logs_template
{
  "index_patterns": ["shop-logs-*"],
  "priority": 100,
  "template": {
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 0
    },
    "mappings": {
      "properties": {
        "timestamp": { "type": "date" },
        "action": { "type": "keyword" },
        "user_id": { "type": "keyword" },
        "product_id": { "type": "keyword" },
        "message": { "type": "text" }
      }
    }
  }
}

# 2. 创建匹配模式的新索引（不指定 mapping——应自动应用模板）
PUT /shop-logs-2024.04.11

# 3. 验证索引的 mapping 是否正确应用
GET /shop-logs-2024.04.11/_mapping

# 4. 写入测试数据
PUT /shop-logs-2024.04.11/_doc/1
{
  "timestamp": "2024-04-11T10:00:00",
  "action": "view",
  "user_id": "U001",
  "product_id": "P001",
  "message": "用户查看了商品详情页"
}

# 5. 清理
DELETE /shop-logs-2024.04.11
DELETE /_index_template/shop_logs_template
```

### 练习 3：Alias + Reindex 实现零停机修改 Mapping

```
# 1. 创建 v1 索引 + 别名
PUT /products-v1
{
  "mappings": {
    "properties": {
      "name": { "type": "text" },
      "status": { "type": "text" }      // 故意设成 text（错误的选型）
    }
  }
}

POST /_aliases
{
  "actions": [
    { "add": { "index": "products-v1", "alias": "products" } }
  ]
}

# 2. 通过别名写入数据
PUT /products/_doc/1
{ "name": "iPhone 15", "status": "active" }

PUT /products/_doc/2
{ "name": "MacBook Pro", "status": "inactive" }

# 3. 通过别名查询验证
GET /products/_search

# 4. 发现问题：status 应该是 keyword 而不是 text
# 创建 v2 索引（正确的 Mapping）
PUT /products-v2
{
  "mappings": {
    "properties": {
      "name": { "type": "text" },
      "status": { "type": "keyword" }    // 修正为 keyword
    }
  }
}

# 5. Reindex 迁移数据
POST /_reindex
{
  "source": { "index": "products-v1" },
  "dest": { "index": "products-v2" }
}

# 6. 验证数据量一致
GET /products-v1/_count
GET /products-v2/_count

# 7. 原子切换别名
POST /_aliases
{
  "actions": [
    { "remove": { "index": "products-v1", "alias": "products" } },
    { "add": { "index": "products-v2", "alias": "products" } }
  ]
}

# 8. 验证：通过别名查询，数据应该正常
GET /products/_search

# 9. 验证：现在 term 查 status 可以精确匹配了
GET /products/_search
{
  "query": { "term": { "status": "active" } }
}

# 10. 确认无误，删除旧索引
DELETE /products-v1

# 11. 清理
DELETE /products-v2
```

---

## 本阶段总结

学完本阶段，你应该掌握了以下心智模型：

```
Mapping = ES 的 Schema，定义字段类型 → 决定一切索引和查询行为

字段类型决策：
  text     → 分词，全文搜索（match），不能排序/聚合
  keyword  → 不分词，精确匹配（term），可排序/聚合
  数值/日期 → BKD 树索引 + Doc Values，范围查询 + 排序/聚合
  
  不确定用哪个？大多数字符串字段用 Multi-fields（text + keyword 都要）

复杂类型选型：
  单个嵌套对象           → Object（默认）
  对象数组 + 需要关联查询 → Nested（代价：更新要重建整个文档）
  子文档频繁独立更新      → Join（代价：查询性能差）
  动态 JSON 只需精确匹配  → Flattened

索引管理四件套：
  Index Template → 新索引自动应用 Mapping/Settings
  Alias          → 零停机切换 / 读写分离 / 多索引聚合
  Reindex        → 修改 Mapping 的唯一方式
  Rollover       → 时间序列索引自动滚动

索引设计模式：
  按时间分索引  → 日志、订单（配合 ILM）
  多租户        → 大索引+routing 或 每租户一个索引
  宽表反范式    → 写入时打平关联数据，避免 JOIN
  读写分离      → write alias + read alias + force merge
```

**Mapping 不可修改**，这是 ES 数据建模的第一铁律。写入数据前必须设计好 Mapping，设 `dynamic: strict`。

**下一阶段**：阶段 3 分词与文本分析——你已经知道 text 类型会「分词」，但分词器内部是怎么工作的？IK 的 smart 和 max_word 到底有什么区别？为什么写入和搜索可以用不同的分词器？这些问题将在阶段 3 中获得完整解答。
