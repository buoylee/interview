# 阶段 4：Query DSL 深入（1.5 周）

> **目标**：系统掌握 ES 的全部查询能力。学完本阶段后，你应该能针对任意搜索需求选择正确的查询类型、理解 BM25 打分机制、使用 function_score 实现自定义排序、解决深度分页问题，并能用 explain 和 profile API 调试查询。
>
> **前置依赖**：阶段 2（Mapping——字段类型决定查询行为）+ 阶段 3（分词——决定 match 查询的分词方式）
>
> **为后续阶段铺路**：Query DSL 是 ES 使用层面的核心。阶段 5（聚合）的 aggs 通常和 query 配合使用（先过滤再聚合）；阶段 8（性能调优）中的查询优化直接基于本阶段的 filter/query context 和深度分页知识。
>
> **本阶段为什么排在分词之后？** 因为每种查询的行为都可以从「字段类型 + 分词方式」推导出来。现在你已经掌握了 Mapping 和分词，可以**真正理解**每种查询为什么这样工作，而不是死记结论。

---

## 4.1 理解查询行为的关键——从 Mapping 和分词出发

在深入每种查询之前，先建立一个**统一的推导框架**。后面所有查询的行为，都可以用这个框架推导出来：

```
查询行为 = 查询词是否分词 × 字段类型（text/keyword）
```

| 查询类型 | 查询词是否分词 | 字段类型 | 实际行为 |
|---------|-------------|---------|---------|
| `term` | ❌ 不分词 | keyword | ✅ 精确匹配（最常用的 term 用法） |
| `term` | ❌ 不分词 | text | ⚠️ 查询词必须完全等于 text 分词后的某个 Token 才能匹配（容易踩坑） |
| `match` | ✅ 分词 | text | ✅ 分词后的 Token 去倒排索引匹配（最常用的全文搜索） |
| `match` | ✅ 分词 | keyword | ⚠️ keyword 不分词，搜索词又被分词了，很难匹配上（基本没用） |

**用这个框架推导一个例子：**

文档 `{ "brand": "Apple", "name": "iPhone 15 Pro Max" }`

- `brand` 是 keyword → 存入倒排索引的 Term 是 `Apple`（原样）
- `name` 是 text (standard) → 存入的 Term 是 `[iphone, 15, pro, max]`（分词+小写）

```
term 查 brand: "Apple"     → 不分词，直接查 "Apple" → ✅ 命中
term 查 brand: "apple"     → 不分词，直接查 "apple" → ❌ 不命中（大小写敏感）
term 查 name: "iPhone 15"  → 不分词，直接查 "iPhone 15" → ❌ 倒排索引里没有这个完整 Term
match 查 name: "iphone 15" → 分词得到 ["iphone","15"] → 两个都在倒排索引里 → ✅ 命中
match 查 name: "iPhone"    → 分词得到 ["iphone"] → 在倒排索引里 → ✅ 命中
```

> **核心原则**：**术语查精确，匹配查全文**（term 配 keyword，match 配 text）。记住这个原则，90% 的查询选型不会出错。

---

## 4.2 全文检索查询——match 家族

全文查询都会对搜索词做分词（使用字段的 search_analyzer）。它们的区别在于分词后**如何匹配**。

### match——最基础的全文搜索

```
GET /products/_search
{
  "query": {
    "match": {
      "name": "华为手机"
    }
  }
}
```

**match 的内部流程：**

```
搜索词 "华为手机"
  → search_analyzer (ik_smart) 分词 → ["华为", "手机"]
  → 默认用 OR 连接：文档包含 "华为" 或 "手机" 就匹配
  → 匹配到的文档按 BM25 打分排序
```

**operator 参数**：控制多个 Term 之间的逻辑关系

```
# 默认 OR：包含任一 Term 即匹配（召回率高，精准度低）
{ "match": { "name": { "query": "华为手机", "operator": "or" } } }

# AND：必须包含所有 Term（精准度高，召回率低）
{ "match": { "name": { "query": "华为手机", "operator": "and" } } }

# minimum_should_match：至少匹配 N 个 Term（折中）
{ "match": { "name": { "query": "华为 5G 旗舰 手机", "minimum_should_match": "75%" } } }
# 4 个 Term × 75% = 至少匹配 3 个
```

### multi_match——多字段全文搜索

在多个字段上同时做 match，并提供多种策略来组合各字段的分数。

```
GET /products/_search
{
  "query": {
    "multi_match": {
      "query": "华为手机",
      "fields": ["name^3", "description"],     // name 权重 ×3
      "type": "best_fields"
    }
  }
}
```

**四种策略对比：**

| type | 策略 | 适用场景 |
|------|------|---------|
| `best_fields`（默认） | 取分数最高的那个字段的分数 | 一个字段能完整匹配查询词（如商品名） |
| `most_fields` | 所有匹配字段的分数相加 | 同一内容分布在多个字段（如 title + subtitle） |
| `cross_fields` | 将多个字段当作一个大字段来匹配 | 姓名分成 first_name + last_name |
| `phrase` | 每个字段上做 match_phrase | 需要精确短语匹配的多字段搜索 |

**best_fields vs most_fields 直觉理解：**

```
文档 A：name="华为手机",   description="最新旗舰"
文档 B：name="华为",       description="5G 手机"

搜索 "华为手机"：

best_fields：
  A 的 name 字段完整匹配 → 高分 ✅（A 排前面）
  B 的 name 和 description 各匹配一部分 → 取 name 的分 → 分不高

most_fields：
  A 的 name 高分 + description 无匹配 → 总分一般
  B 的 name 有分 + description 有分 → 两个加起来可能更高 ⚠️（B 可能排前面）
```

通常搜索场景用 `best_fields` 更合理——一个字段完整匹配应该比分散在多个字段更相关。

### match_phrase——短语匹配

分词后不仅要求每个 Term 都匹配，还要求**顺序和位置**一致。

```
GET /products/_search
{
  "query": {
    "match_phrase": {
      "name": "华为 Mate"
    }
  }
}
```

```
"华为 Mate" 分词 → ["华为", "mate"]（位置0, 位置1）

文档 "华为 Mate 60 Pro" → "华为"在位置0，"mate"在位置1 → ✅ 顺序和位置匹配
文档 "Mate 手机 华为版"  → "mate"在位置0，"华为"在位置2 → ❌ 顺序不对
```

**slop 参数**：允许 Term 之间有多少个位置的间隔

```
{ "match_phrase": { "name": { "query": "华为 Pro", "slop": 2 } } }
# "华为 Mate 60 Pro" → "华为"和"Pro"之间间隔 2 个位置 → ✅ 在 slop=2 范围内
```

### match_phrase_prefix——搜索框联想

match_phrase + 最后一个词做前缀匹配。适合搜索框的输入联想。

```
{ "match_phrase_prefix": { "name": "华为 Ma" } }
# "华为" 精确匹配 + "Ma" 前缀匹配 → 能匹配 "华为 Mate 60"、"华为 MacBook"
```

> 注意：match_phrase_prefix 性能不佳，生产中推荐使用 Completion Suggester（阶段 10）或 edge_ngram（阶段 3 已学）。

### query_string / simple_query_string

支持用户直接输入搜索语法：

```
# query_string：支持完整的 Lucene 语法（AND/OR/NOT/通配符/分组）
{ "query_string": { "query": "(华为 OR 小米) AND 手机 AND NOT 平板" } }

# simple_query_string：安全版本，语法错误不会报错（会当普通文本搜索）
{ "simple_query_string": { "query": "华为 + 手机 -平板", "fields": ["name"] } }
```

| 语法 | query_string | simple_query_string |
|------|-------------|-------------------|
| AND | `AND` 或 `&&` | `+` |
| OR | `OR` 或 `\|\|` | 空格（默认） |
| NOT | `NOT` 或 `!` | `-` |
| 分组 | `()` | 不支持 |
| 语法错误 | 报错 | 容错处理 |

**生产建议**：面向用户的搜索框用 `simple_query_string`（避免用户输入导致查询报错），内部接口可以用 `query_string`。

---

## 4.3 精确匹配查询——term 家族

精确查询**不对搜索词做分词**，直接拿原始值去匹配倒排索引。

### term / terms

```
# 单值精确匹配
{ "term": { "status": "active" } }

# 多值精确匹配（OR 关系）
{ "terms": { "brand": ["华为", "Apple", "小米"] } }
```

> **再次强调**：term 不分词，所以要对 keyword 字段使用，不要对 text 字段使用（除非你非常清楚 text 分词后的 Term 是什么）。

### range——范围查询

```
# 数值范围
{ "range": { "price": { "gte": 3000, "lte": 8000 } } }

# 日期范围
{ "range": { "created_at": { "gte": "2024-01-01", "lt": "2024-04-01" } } }

# 日期数学表达式
{ "range": { "created_at": { "gte": "now-30d/d", "lt": "now/d" } } }
```

日期数学表达式说明：
- `now`：当前时间
- `now-30d`：30 天前
- `now-30d/d`：30 天前，取整到天的开始（00:00:00）
- `now/M`：当前月份的开始

### exists——字段是否存在

```
{ "exists": { "field": "description" } }
```

注意：值为 `null` 或空数组 `[]` 的字段被视为不存在。空字符串 `""` 是存在的。

### prefix / wildcard / regexp——模式匹配

```
# 前缀匹配
{ "prefix": { "name.keyword": "iPhone" } }

# 通配符（? 单字符，* 多字符）
{ "wildcard": { "name.keyword": "iPh*" } }

# 正则
{ "regexp": { "name.keyword": "iPhone [0-9]+" } }
```

> **⚠️ 性能警告**：prefix、wildcard（尤其是前缀 `*`）、regexp 都可能导致**全索引扫描**，生产中应尽量避免。如果需要前缀搜索，用 edge_ngram（阶段 3 已学）性能好得多。

### fuzzy——模糊匹配

允许一定的编辑距离（Levenshtein Distance），容忍拼写错误。

```
{ "fuzzy": { "name": { "value": "iphome", "fuzziness": 1 } } }
# "iphome" 和 "iphone" 编辑距离为 1（m→n）→ ✅ 能匹配
```

`fuzziness` 参数：
- `0`：不允许错误
- `1`：允许 1 个字符的编辑（增/删/改/换位）
- `2`：允许 2 个字符
- `AUTO`（推荐）：根据搜索词长度自动决定（1-2 字符→0，3-5 字符→1，>5 字符→2）

---

## 4.4 复合查询——组合与控制

### bool 查询——最核心的组合查询

bool 查询是 ES 中**使用频率最高**的查询结构。几乎所有生产中的查询都是 bool 的组合。

```
GET /products/_search
{
  "query": {
    "bool": {
      "must": [
        { "match": { "name": "华为手机" } }            // AND + 参与打分
      ],
      "filter": [
        { "term": { "status": "active" } },             // AND + 不打分 + 可缓存
        { "range": { "price": { "gte": 3000, "lte": 8000 } } }
      ],
      "should": [
        { "term": { "tags": "5G" } },                   // OR + 参与打分（加分项）
        { "term": { "tags": "旗舰" } }
      ],
      "must_not": [
        { "term": { "brand": "Apple" } }                // NOT + 不打分
      ],
      "minimum_should_match": 1                          // should 至少匹配 1 个
    }
  }
}
```

**四种子句的完整对比：**

| 子句 | 逻辑 | 是否打分 | 是否缓存 | 用途 |
|------|------|---------|---------|------|
| `must` | AND | ✅ 打分 | ❌ | 需要影响排序的条件（如关键词搜索） |
| `filter` | AND | ❌ 不打分 | ✅ 自动缓存 | 不需要影响排序的条件（如状态过滤、价格区间） |
| `should` | OR | ✅ 打分 | ❌ | 加分项（匹配了分数更高，不匹配也不过滤） |
| `must_not` | NOT | ❌ 不打分 | ✅ 自动缓存 | 排除条件 |

**should 的行为细节：**
- 当 bool 查询中**有 must 或 filter** 时，should 是可选的（加分项，不匹配也行）
- 当 bool 查询中**只有 should**（没有 must 和 filter）时，should 至少要匹配一个
- `minimum_should_match` 可以显式控制 should 的最小匹配数

### filter vs must——为什么 filter 更快？

这是一个**面试必考**的知识点。

```
两种写法，逻辑上等价——都要求 status=active：

# 写法 1：用 must（打分）
{ "bool": { "must": [ { "term": { "status": "active" } } ] } }

# 写法 2：用 filter（不打分）
{ "bool": { "filter": [ { "term": { "status": "active" } } ] } }
```

**filter 更快的两个原因：**

```
原因 1：跳过打分计算
  must：  找到匹配文档 → 计算 BM25 分数 → 排序
  filter：找到匹配文档 → 直接返回（省掉打分计算，CPU 消耗更低）

原因 2：结果自动缓存到 Node Query Cache
  filter：{ "term": { "status": "active" } } 的结果是一个 Bitset（标记哪些文档匹配）
          → ES 自动把这个 Bitset 缓存在内存中
          → 下次相同的 filter 直接从缓存取，跳过索引访问

  must：  不缓存（因为打分可能随数据变化，缓存不安全）
```

> **生产原则**：**不需要影响排序的条件，一律放 filter 而非 must**。状态过滤、时间范围、品类筛选、权限控制——这些都不需要打分，全部放 filter。只有关键词搜索这种需要相关性排序的才放 must。

### dis_max——最佳字段策略

取多个查询中**分数最高**的作为最终分数。

```
GET /products/_search
{
  "query": {
    "dis_max": {
      "queries": [
        { "match": { "name": "华为手机" } },
        { "match": { "description": "华为手机" } }
      ],
      "tie_breaker": 0.3
    }
  }
}
```

**dis_max 的打分**：`最终分数 = max(各查询分数) + tie_breaker × sum(其他查询分数)`

- `tie_breaker = 0`：只取最高分（纯 best fields）
- `tie_breaker = 1`：等同于分数相加（most fields）
- `tie_breaker = 0.3`（常用）：主要看最高分，其他字段有匹配给一点加分

> 实际上 `multi_match` 的 `best_fields` 策略底层就是 dis_max，`most_fields` 就是 dis_max + tie_breaker=1。

### constant_score——固定分数

包装一个查询，忽略其打分，赋予固定分数。

```
{ "constant_score": { "filter": { "term": { "status": "active" } }, "boost": 1.0 } }
```

所有匹配文档的分数都是 1.0，不计算 BM25。适合只关心匹配/不匹配、不关心相关性排序的场景。

### boosting——正面提升 + 负面降低

```
{
  "boosting": {
    "positive": { "match": { "name": "手机" } },        // 正面查询（必须匹配）
    "negative": { "term": { "brand": "杂牌" } },        // 负面查询（匹配了降分）
    "negative_boost": 0.5                                // 负面匹配的文档分数 ×0.5
  }
}
```

与 must_not 的区别：must_not 是完全排除，boosting 的 negative 只是降低排名，不排除。

---

## 4.5 相关性打分深入——BM25 与自定义打分

### BM25 算法

ES 5.x 起默认使用 BM25（替代了 TF-IDF），它是当前信息检索领域最广泛使用的打分算法。

**BM25 的三个核心因子：**

```
BM25(q, d) = Σ [ IDF(t) × (TF(t,d) × (k1 + 1)) / (TF(t,d) + k1 × (1 - b + b × |d|/avgdl)) ]

其中每个搜索 Term t 的得分由三部分决定：
```

| 因子 | 含义 | 直觉理解 |
|------|------|---------|
| **TF（词频）** | Term 在文档中出现的次数 | 出现越多越相关，但**有饱和度上限**（区别于 TF-IDF 的线性增长） |
| **IDF（逆文档频率）** | Term 在所有文档中的稀有程度 | 越稀有的词越有区分度。"的"出现在每篇文档中 → IDF 低；"Elasticsearch"只出现在少数文档 → IDF 高 |
| **字段长度归一化** | 字段越短，匹配的权重越高 | 标题中出现"手机"比详细描述中出现"手机"更相关 |

**BM25 vs TF-IDF 的关键区别：**

```
TF 的饱和度：

TF-IDF：      分数
              │         /
              │        /        ← TF-IDF: TF 线性增长，同一个词出现 100 次的文档
              │       /            得分是出现 1 次的 100 倍（不合理！）
              │      /
              │     /
              │    /
              │   /
              │──/──────────────→ 词频(TF)

BM25：        分数
              │       ___________
              │      /            ← BM25: TF 有饱和度，出现到一定次数后分数增长趋缓
              │     /                k1 控制饱和速度（k1=1.2 默认）
              │    /
              │   /
              │  /
              │ /
              │/────────────────→ 词频(TF)
```

**BM25 的两个可调参数：**

| 参数 | 默认值 | 作用 |
|------|-------|------|
| `k1` | 1.2 | 控制 TF 饱和速度。k1 越大，TF 对分数的影响越大；k1=0 时 TF 完全不影响 |
| `b` | 0.75 | 控制字段长度归一化的影响程度。b=1 完全归一化；b=0 不考虑字段长度 |

```json
// 在 Mapping 中自定义 BM25 参数（通常不需要调，默认值对大多数场景够用）
"name": {
  "type": "text",
  "similarity": {
    "type": "BM25",
    "k1": 1.2,
    "b": 0.75
  }
}
```

### explain API——调试打分

当你不理解「为什么这个文档排在前面/后面」时，用 explain API 查看打分详情：

```
GET /products/_explain/1
{
  "query": {
    "match": { "name": "华为手机" }
  }
}
```

返回结果会展示每一步的分数计算过程——IDF 多少、TF 多少、字段长度归一化多少、最终分数怎么来的。这在调优相关性排序时非常有用。

### Function Score Query——自定义打分

BM25 只考虑文本相关性。但实际搜索场景通常还需要考虑**业务因素**——热度、销量、时间新鲜度、地理距离等。Function Score 让你在 BM25 基础分上叠加自定义打分逻辑。

```
GET /products/_search
{
  "query": {
    "function_score": {
      "query": { "match": { "name": "手机" } },          // 基础查询（BM25 打分）
      "functions": [
        {
          "field_value_factor": {                          // 函数 1：用字段值影响分数
            "field": "sales_count",                        // 销量越高分越高
            "modifier": "log1p",                           // 用 log(1 + sales_count) 防止极端值
            "factor": 0.5
          }
        },
        {
          "gauss": {                                       // 函数 2：时间衰减
            "created_at": {
              "origin": "now",                             // 基准点：当前时间
              "scale": "30d",                              // 衰减范围：30 天
              "decay": 0.5                                 // 30 天前的文档分数衰减到 0.5
            }
          }
        },
        {
          "weight": 2,                                     // 函数 3：固定权重加分
          "filter": { "term": { "is_promoted": true } }   // 仅对推广商品生效
        }
      ],
      "score_mode": "sum",           // 多个函数的分数如何组合：sum/multiply/avg/max/min
      "boost_mode": "multiply"       // 函数组合分与原始 BM25 分如何结合：multiply/sum/replace/avg/max/min
    }
  }
}
```

**Function Score 的函数类型：**

| 函数 | 用途 | 示例 |
|------|------|------|
| `field_value_factor` | 用字段值影响分数 | 销量越高分越高 |
| `script_score` | Painless 脚本计算分数 | 完全自定义的打分逻辑 |
| `weight` | 固定权重（可配合 filter 给某类文档加分） | 推广商品 ×2 |
| `random_score` | 随机分（seed 保证同一用户看到相同结果） | 「猜你喜欢」随机推荐 |
| `linear` / `exp` / `gauss` | 距离衰减函数 | 时间越近分越高、地理越近分越高 |

**三种衰减函数的区别：**

```
分数
  │  gauss
  │  ╲
  │   ╲___
  │        ╲___________     ← gauss: 平滑的高斯曲线衰减
  │
  │  exp
  │  ╲
  │   ╲
  │    ╲___
  │        ╲_____________   ← exp: 指数衰减，远距离快速趋近 0
  │
  │  linear
  │  ╲
  │    ╲
  │      ╲
  │        ╲
  │          ╲              ← linear: 线性衰减，到 scale 后分数为 0
  │────────────╲──────────→ 距离
  0           scale
```

- `gauss`（最常用）：远距离仍有少量分数
- `exp`：远距离快速归零
- `linear`：超过 scale 就是 0 分

### Rescore Query——二次精排

先用简单查询（BM25）从全量数据中找出 Top N，然后在这 Top N 上用复杂的打分逻辑**二次排序**。

```
GET /products/_search
{
  "query": {
    "match": { "name": "手机" }
  },
  "rescore": {
    "window_size": 100,                           // 只对 Top 100 做重排
    "query": {
      "rescore_query": {
        "function_score": {
          "script_score": {
            "script": "_score * doc['sales_count'].value"
          }
        }
      },
      "query_weight": 0.7,                        // 原始分权重
      "rescore_query_weight": 0.3                  // 重排分权重
    }
  }
}
```

好处：复杂打分只在 Top N 上执行，比在全量数据上 function_score 快得多。

---

## 4.6 搜索执行流程——理解分布式查询

### Query Then Fetch 两阶段

```
客户端发送搜索请求
        │
        ▼
  Coordinating Node（协调节点）
        │
  ══════════════════════════════════
  │ Phase 1: Query Phase            │
  │                                 │
  │ 协调节点广播请求到所有相关 Shard   │
  │ ┌──────┐ ┌──────┐ ┌──────┐     │
  │ │Shard0│ │Shard1│ │Shard2│     │
  │ └──────┘ └──────┘ └──────┘     │
  │ 每个 Shard 在本地执行查询        │
  │ 返回 from+size 条的 doc_id+score│
  │                                 │
  │ 协调节点收集所有 Shard 结果       │
  │ 全局排序 → 取出 from+size 条     │
  ══════════════════════════════════
        │
  ══════════════════════════════════
  │ Phase 2: Fetch Phase            │
  │                                 │
  │ 协调节点根据 doc_id              │
  │ 向对应 Shard 取回文档内容        │
  │ （_source / highlight 等）       │
  ══════════════════════════════════
        │
        ▼
  返回最终结果给客户端
```

**关键理解**：
- Query Phase 只传 doc_id + score（很轻量），不传文档内容
- Fetch Phase 才取文档内容（只取最终需要的那几条）
- 这个两阶段设计减少了网络传输量

### 深度分页问题

```
请求：from=10000, size=10

实际会发生什么？

协调节点 → Shard 0: "给我你本地排名前 10010 条的 doc_id+score"
        → Shard 1: "给我你本地排名前 10010 条的 doc_id+score"
        → Shard 2: "给我你本地排名前 10010 条的 doc_id+score"

协调节点收到 3 × 10010 = 30030 条结果
→ 在内存中全局排序
→ 取第 10001~10010 条返回

问题：5 个 Shard 就是 50050 条在内存中排序！
     from 越大，内存消耗越大，直到 OOM
```

ES 默认限制 `from + size ≤ 10000`（`max_result_window` 参数）。

### 三种解决方案

**方案 1：Scroll（游标遍历）**

```
# 步骤 1：创建 scroll 上下文（设置快照保持时间）
POST /products/_search?scroll=1m
{
  "size": 100,
  "query": { "match_all": {} }
}
# 返回 scroll_id + 第一批数据

# 步骤 2：用 scroll_id 获取下一批
POST /_search/scroll
{
  "scroll": "1m",
  "scroll_id": "DXF1ZXJ5QW5kRmV0Y2gBA..."
}

# 步骤 3：清理 scroll 上下文
DELETE /_search/scroll
{
  "scroll_id": "DXF1ZXJ5QW5kRmV0Y2gBA..."
}
```

| 优点 | 缺点 |
|------|------|
| 可以遍历全量数据 | 创建了一个"快照"，有资源开销 |
| 不受 max_result_window 限制 | 不适合实时搜索（快照是固定时间点的） |
| | 无法实现跳页（只能一页一页往下翻） |

**适用场景**：一次性导出全量数据、数据迁移、后台批处理。

**方案 2：search_after（无状态深度分页）**

```
# 第一页：正常搜索，必须有排序字段
GET /products/_search
{
  "size": 10,
  "sort": [
    { "created_at": "desc" },
    { "_id": "asc" }               // 加 _id 保证排序唯一性
  ],
  "query": { "match": { "name": "手机" } }
}

# 假设最后一条文档的 sort 值是 [1704067200000, "abc123"]

# 第二页：用上一页最后一条的 sort 值
GET /products/_search
{
  "size": 10,
  "sort": [
    { "created_at": "desc" },
    { "_id": "asc" }
  ],
  "search_after": [1704067200000, "abc123"],    // ← 上一页最后一条的 sort 值
  "query": { "match": { "name": "手机" } }
}
```

| 优点 | 缺点 |
|------|------|
| 无状态，不消耗额外资源 | 无法跳页（只能下一页） |
| 适合实时搜索 | 必须有排序字段 |
| 不受 max_result_window 限制 | 排序字段需要保证唯一（否则可能漏数据） |

**适用场景**：用户翻页（下一页/上一页）、无限滚动（加载更多）。

**方案 3：PIT + search_after（ES 7.10+）**

PIT（Point in Time）提供一个一致性快照视图，配合 search_after 使用。

```
# 步骤 1：创建 PIT
POST /products/_pit?keep_alive=1m
# 返回 pit_id

# 步骤 2：用 PIT + search_after 分页
GET /_search
{
  "size": 10,
  "sort": [{ "created_at": "desc" }, { "_id": "asc" }],
  "pit": {
    "id": "pit_id_here",
    "keep_alive": "1m"
  },
  "search_after": [1704067200000, "abc123"]
}

# 步骤 3：清理 PIT
DELETE /_pit
{
  "id": "pit_id_here"
}
```

PIT 保证了分页过程中数据视图的一致性——即使其他请求在添加/删除数据，你看到的结果集是固定的。

**三种方案总结：**

| 方案 | 跳页 | 实时性 | 资源消耗 | 一致性 | 适用场景 |
|------|------|-------|---------|--------|---------|
| `from+size` | ✅ | ✅ | 深页高 | ❌ | 浅分页（前几页） |
| `scroll` | ❌ | ❌ 快照 | 中等 | ✅ | 全量导出 |
| `search_after` | ❌ | ✅ | 低 | ❌ | 实时深度分页 |
| `PIT + search_after` | ❌ | ✅ | 中等 | ✅ | 实时深度分页 + 一致视图 |

> **面试怎么答**："ES 深度分页怎么解决？"
>
> ES 默认的 from+size 分页在 from 很大时会导致协调节点内存暴涨（每个 shard 返回 from+size 条，协调节点汇总排序），所以 ES 限制 from+size ≤ 10000。解决深度分页有三种方案：scroll 创建数据快照游标遍历，适合全量导出但不适合实时搜索；search_after 无状态分页，用上一页最后一条的排序值定位下一页，适合实时深度分页但不能跳页；PIT + search_after 在 search_after 基础上提供一致性视图，是 ES 7.10+ 推荐的方案。

---

## 4.7 高亮（Highlight）——搜索结果展示

高亮是搜索 UI 的基本能力——在搜索结果中将匹配的关键词用 `<em>` 标签包裹，前端展示为红色/加粗。

### 基本用法

```
GET /products/_search
{
  "query": {
    "match": { "name": "华为手机" }
  },
  "highlight": {
    "fields": {
      "name": {}
    }
  }
}

# 返回结果：
{
  "hits": [{
    "_source": { "name": "华为 Mate 60 Pro 智能手机" },
    "highlight": {
      "name": ["<em>华为</em> Mate 60 Pro 智能<em>手机</em>"]
    }
  }]
}
```

### 自定义高亮标签

```
"highlight": {
  "pre_tags": ["<span class='highlight'>"],
  "post_tags": ["</span>"],
  "fields": {
    "name": {},
    "description": {
      "fragment_size": 150,           // 高亮片段长度（默认 100 字符）
      "number_of_fragments": 3        // 返回几个高亮片段（默认 5）
    }
  }
}
```

### 三种高亮类型

| 类型 | 特点 | Mapping 要求 | 性能 | 适用场景 |
|------|------|------------|------|---------|
| `plain`（默认） | 基于 Lucene Highlighter，搜索时重新分词 | 无特殊要求 | 一般 | 大部分场景 |
| `postings` | 利用索引中已存的位置信息，不需重新分词 | `index_options: "offsets"` | 更好 | 大量文档的高亮 |
| `fvh` | Fast Vector Highlighter，利用 term_vector | `term_vector: "with_positions_offsets"` | 最好（大字段） | 字段 >1MB |

```json
// 使用 postings 高亮（需要在 Mapping 中设置）
"title": {
  "type": "text",
  "index_options": "offsets"          // 存储位置偏移信息
}
```

### 多字段高亮

```
"highlight": {
  "require_field_match": false,       // 允许高亮不在查询中的字段
  "fields": {
    "name": {},
    "description": {}
  }
}
```

默认情况下只有查询中出现的字段才会高亮。设 `require_field_match: false` 后，即使查询只搜了 `name`，`description` 中的匹配词也会被高亮。

---

## 4.8 查询上下文与优化

### query context vs filter context

前面在 bool 查询中已经讲了 must vs filter 的区别。这里从更宏观的视角总结：

```
ES 的每个查询子句都运行在两种上下文之一：

Query Context（查询上下文）：
  - "这个文档有多匹配？" → 计算相关性分数
  - 用在：bool.must, bool.should, match, multi_match 等
  - 不缓存结果

Filter Context（过滤上下文）：
  - "这个文档匹配不匹配？" → 只要 yes/no，不打分
  - 用在：bool.filter, bool.must_not, constant_score.filter 等
  - 结果自动缓存到 Node Query Cache
```

**性能优化原则**：

| 条件类型 | 放在哪里 | 为什么 |
|---------|---------|--------|
| 关键词搜索 | `must` 或 `should` | 需要相关性排序 |
| 状态过滤（active/inactive） | `filter` | 不需要影响排序，可缓存 |
| 时间范围（最近 30 天） | `filter` | 不需要影响排序，可缓存 |
| 价格区间 | `filter` | 不需要影响排序，可缓存 |
| 品类筛选 | `filter` | 不需要影响排序，可缓存 |
| 排除条件 | `must_not` | 不打分 + 可缓存 |

### routing 查询

指定 routing 值，查询只在指定的 shard 上执行，跳过其他 shard。

```
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

多租户场景写入数据时用相同的 routing 值，查询时也指定 routing → 整个查询只在一个 shard 上执行，大幅提升查询速度。

### preference 参数

控制查询优先在哪些 shard 副本上执行。

```
GET /products/_search?preference=_local             // 本地节点的 shard 优先
GET /products/_search?preference=_prefer_nodes:node1 // 指定节点优先
GET /products/_search?preference=my_custom_id        // 相同的 preference 值始终路由到相同 shard 副本
```

**解决 bouncing results 问题**：默认情况下 ES 轮询不同的 shard 副本，不同副本的打分可能微妙不同（因为 TF/IDF 的统计值可能略有差异），导致用户刷新页面后排序变化。设置 `preference` 为固定值（如用户 session ID）可以避免。

### profile API——查询性能诊断

```
GET /products/_search
{
  "profile": true,
  "query": {
    "bool": {
      "must": [{ "match": { "name": "华为手机" } }],
      "filter": [{ "term": { "status": "active" } }]
    }
  }
}
```

返回结果中包含每个 shard 上每个查询组件的耗时详情（纳秒级）。用来定位「查询为什么慢」——是全文搜索慢？过滤慢？排序慢？

---

## 面试高频题与参考答案

### Q1：match 和 term 的区别？各自什么场景用？

**答**：核心区别在于是否对搜索词做分词。match 会用字段的 search_analyzer 对搜索词分词，然后用分词后的 Term 去匹配倒排索引，适合全文搜索场景（如商品名搜索、文章内容搜索），通常和 text 类型字段配合使用。

term 不对搜索词做分词，直接拿原始值去匹配倒排索引，适合精确匹配场景（如状态码过滤、ID 查找、标签匹配），通常和 keyword 类型字段配合使用。

一个常见踩坑点是用 term 查 text 字段——因为 text 字段在索引时被分词了（且通常转了小写），用 term 查原始值大概率匹配不上。正确做法是对 text 字段用 match 查询，对 keyword 字段用 term 查询。

### Q2：filter 和 must 的区别？filter 为什么更快？

**答**：逻辑上都是 AND 条件，但 filter 不计算相关性分数，must 计算。filter 更快有两个原因：

第一，跳过了打分计算。BM25 的分数计算涉及 TF、IDF、字段长度归一化等多步运算，filter 直接跳过，CPU 消耗更低。

第二，filter 的结果会被自动缓存到 Node Query Cache。ES 会把 filter 条件的匹配结果存为一个 Bitset 缓存在内存中，相同的 filter 下次直接从缓存取，跳过整个索引访问。must 的结果因为涉及打分，分数可能随数据变化，所以不缓存。

生产中的原则是：不需要影响排序的条件一律放 filter（状态过滤、时间范围、价格区间、品类筛选），只有关键词搜索这种需要相关性排序的才放 must。

### Q3：BM25 和 TF-IDF 的区别？BM25 好在哪？

**答**：两者都考虑词频（TF）和逆文档频率（IDF），但 BM25 有两个关键改进：

第一，TF 有饱和度上限。TF-IDF 中 TF 是线性增长的，一个词出现 100 次的文档得分是出现 1 次的 100 倍，这通常不合理。BM25 通过参数 k1 控制 TF 的饱和速度，出现到一定次数后分数增长趋缓，更符合直觉。

第二，字段长度归一化更灵活。BM25 通过参数 b 控制字段长度对分数的影响程度。短字段（如标题）中出现搜索词的权重高于长字段（如文章正文），b=0 可以完全关闭长度归一化。

ES 从 5.x 开始默认使用 BM25 替代 TF-IDF。在绝大部分场景下，BM25 的默认参数（k1=1.2, b=0.75）无需调整即可获得很好的排序效果。

### Q4：ES 深度分页怎么解决？scroll 和 search_after 的区别？

**答**：ES 的 from+size 分页在 from 很大时有性能问题——每个 shard 需要返回 from+size 条结果到协调节点做全局排序，from=10000 时 5 个 shard 就是 50050 条在内存排序。所以 ES 默认限制 from+size ≤ 10000。

scroll 适合全量数据导出：它创建一个搜索上下文快照，通过 scroll_id 游标逐页获取。优点是可以遍历全量数据，缺点是快照有资源消耗、不适合实时搜索、不能跳页。

search_after 适合实时深度分页：用上一页最后一条文档的排序值作为下一页的起点，无状态，不消耗额外资源。缺点是不能跳页（只能翻下一页），且必须有排序字段。

ES 7.10+ 推荐 PIT + search_after 组合：PIT 提供一致性视图，避免分页过程中数据变化导致的结果遗漏或重复。

### Q5：dis_max 和 most_fields 的区别？什么时候用哪个？

**答**：两者都是多字段搜索策略。dis_max（best_fields 的底层实现）取所有字段中**分数最高**的作为最终分数，适合"一个字段能完整匹配查询词"的场景（如商品名搜索，标题完整包含关键词更相关）。

most_fields 把所有匹配字段的分数相加，适合"同一内容分布在多个字段"的场景（如 title + subtitle + description 都描述同一个东西，越多字段匹配越相关）。

实际上 multi_match 的 `type: "best_fields"` 底层就是 dis_max，tie_breaker 参数可以让其他字段也部分参与打分（0~1 之间，0 是纯 best fields，1 等同于 most_fields）。一般搜索场景用 best_fields + tie_breaker=0.3 效果最好。

### Q6：如何给搜索结果加上自定义排序逻辑？

**答**：使用 function_score 查询。function_score 允许在 BM25 基础分上叠加自定义打分函数，常用的有：

field_value_factor 用字段值影响分数（如销量越高分越高，通常配合 log1p 防止极端值）；decay function（gauss/exp/linear）做距离衰减（如时间越近分越高、地理位置越近分越高）；weight 配合 filter 给特定类型文档加分（如推广商品 ×2）；script_score 用 Painless 脚本写完全自定义的打分逻辑。

多个函数通过 score_mode 组合（sum/multiply/avg），函数组合分再通过 boost_mode 与原始 BM25 分结合（multiply/sum/replace）。

如果打分逻辑复杂且对性能敏感，可以用 rescore query 只对 Top N 结果做二次精排，避免在全量数据上执行复杂打分。

---

## 动手实践

### 练习 1：构造测试数据 + 各种查询

```
# 1. 创建索引
PUT /query_practice
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0
  },
  "mappings": {
    "properties": {
      "name": {
        "type": "text",
        "fields": { "keyword": { "type": "keyword" } }
      },
      "brand": { "type": "keyword" },
      "category": { "type": "keyword" },
      "price": { "type": "float" },
      "sales_count": { "type": "integer" },
      "tags": { "type": "keyword" },
      "description": { "type": "text" },
      "status": { "type": "keyword" },
      "is_promoted": { "type": "boolean" },
      "created_at": { "type": "date" }
    }
  }
}

# 2. 批量写入测试数据（10+ 条）
POST /_bulk
{"index": {"_index": "query_practice", "_id": "1"}}
{"name": "华为 Mate 60 Pro", "brand": "华为", "category": "手机", "price": 6999, "sales_count": 50000, "tags": ["5G", "旗舰", "鸿蒙"], "description": "华为最新旗舰手机，搭载麒麟芯片，支持卫星通话", "status": "active", "is_promoted": true, "created_at": "2024-03-15"}
{"index": {"_index": "query_practice", "_id": "2"}}
{"name": "iPhone 15 Pro Max", "brand": "Apple", "category": "手机", "price": 9999, "sales_count": 80000, "tags": ["5G", "旗舰", "iOS"], "description": "Apple 最新旗舰手机，A17 Pro 芯片，钛金属边框", "status": "active", "is_promoted": false, "created_at": "2024-03-20"}
{"index": {"_index": "query_practice", "_id": "3"}}
{"name": "小米 14 Ultra", "brand": "小米", "category": "手机", "price": 5999, "sales_count": 30000, "tags": ["5G", "影像", "旗舰"], "description": "小米影像旗舰手机，徕卡联合设计镜头", "status": "active", "is_promoted": false, "created_at": "2024-02-01"}
{"index": {"_index": "query_practice", "_id": "4"}}
{"name": "华为 MatePad Pro", "brand": "华为", "category": "平板", "price": 4999, "sales_count": 15000, "tags": ["办公", "鸿蒙"], "description": "华为高端平板电脑，支持手写笔和键盘", "status": "active", "is_promoted": true, "created_at": "2024-01-10"}
{"index": {"_index": "query_practice", "_id": "5"}}
{"name": "MacBook Pro 14英寸", "brand": "Apple", "category": "笔记本", "price": 14999, "sales_count": 25000, "tags": ["M3芯片", "专业"], "description": "Apple 专业级笔记本电脑，M3 Pro 芯片", "status": "active", "is_promoted": false, "created_at": "2024-01-05"}
{"index": {"_index": "query_practice", "_id": "6"}}
{"name": "华为 FreeBuds Pro 3", "brand": "华为", "category": "耳机", "price": 1499, "sales_count": 40000, "tags": ["降噪", "无线"], "description": "华为旗舰降噪耳机，支持空间音频", "status": "active", "is_promoted": false, "created_at": "2024-04-01"}
{"index": {"_index": "query_practice", "_id": "7"}}
{"name": "Redmi Note 13", "brand": "小米", "category": "手机", "price": 1299, "sales_count": 100000, "tags": ["5G", "性价比"], "description": "小米入门级 5G 手机，超大电池", "status": "active", "is_promoted": true, "created_at": "2024-03-01"}
{"index": {"_index": "query_practice", "_id": "8"}}
{"name": "三星 Galaxy S24 Ultra", "brand": "三星", "category": "手机", "price": 9699, "sales_count": 20000, "tags": ["5G", "旗舰", "AI"], "description": "三星旗舰手机，Galaxy AI 智能功能", "status": "inactive", "is_promoted": false, "created_at": "2024-02-15"}
{"index": {"_index": "query_practice", "_id": "9"}}
{"name": "OPPO Find X7", "brand": "OPPO", "category": "手机", "price": 4999, "sales_count": 18000, "tags": ["5G", "影像"], "description": "OPPO 影像旗舰，哈苏联合调校", "status": "active", "is_promoted": false, "created_at": "2024-01-20"}
{"index": {"_index": "query_practice", "_id": "10"}}
{"name": "iPad Air", "brand": "Apple", "category": "平板", "price": 4999, "sales_count": 35000, "tags": ["M2芯片", "轻薄"], "description": "Apple 轻薄平板，M2 芯片", "status": "active", "is_promoted": false, "created_at": "2024-03-25"}

# 3. match vs term 对比
# match 搜 text 字段（正确）
GET /query_practice/_search
{ "query": { "match": { "name": "华为手机" } } }

# term 搜 keyword 字段（正确）
GET /query_practice/_search
{ "query": { "term": { "brand": "华为" } } }

# term 搜 text 字段（踩坑——观察结果）
GET /query_practice/_search
{ "query": { "term": { "name": "华为 Mate 60 Pro" } } }

# 4. bool 查询练习——典型的电商筛选
GET /query_practice/_search
{
  "query": {
    "bool": {
      "must": [
        { "match": { "name": "手机" } }
      ],
      "filter": [
        { "term": { "status": "active" } },
        { "range": { "price": { "gte": 3000, "lte": 8000 } } },
        { "terms": { "brand": ["华为", "小米"] } }
      ],
      "should": [
        { "term": { "tags": "5G" } },
        { "term": { "tags": "旗舰" } }
      ],
      "must_not": [
        { "term": { "category": "平板" } }
      ]
    }
  }
}

# 5. match_phrase 精确短语匹配
GET /query_practice/_search
{ "query": { "match_phrase": { "name": "华为 Mate" } } }

# 6. fuzzy 模糊匹配（容忍拼写错误）
GET /query_practice/_search
{ "query": { "fuzzy": { "brand": { "value": "Appel", "fuzziness": 2 } } } }
```

### 练习 2：explain API 调试打分 + function_score 热度加权

```
# 1. 用 explain API 看一个文档的打分详情
GET /query_practice/_explain/1
{
  "query": { "match": { "name": "华为手机" } }
}
# 仔细看返回结果中的 BM25 各项分数：TF、IDF、字段长度归一化

# 2. function_score 实现"热度加权"
GET /query_practice/_search
{
  "query": {
    "function_score": {
      "query": { "match": { "name": "手机" } },
      "functions": [
        {
          "field_value_factor": {
            "field": "sales_count",
            "modifier": "log1p",
            "factor": 0.5
          }
        }
      ],
      "boost_mode": "sum"
    }
  }
}
# 对比不加 function_score 时的排序——销量高的文档应该排名上升

# 3. 推广商品加权
GET /query_practice/_search
{
  "query": {
    "function_score": {
      "query": { "match": { "description": "手机" } },
      "functions": [
        {
          "weight": 5,
          "filter": { "term": { "is_promoted": true } }
        }
      ],
      "boost_mode": "multiply"
    }
  }
}
# 观察推广商品（is_promoted=true）是否排名靠前
```

### 练习 3：深度分页 + profile API

```
# 1. 测试深度分页的性能影响（from=9990 接近上限）
GET /query_practice/_search
{
  "from": 0,
  "size": 5,
  "query": { "match_all": {} }
}

# 2. 用 search_after 实现翻页
# 第一页
GET /query_practice/_search
{
  "size": 3,
  "sort": [
    { "sales_count": "desc" },
    { "_id": "asc" }
  ],
  "query": { "match_all": {} }
}
# 记下最后一条的 sort 值，如 [30000, "3"]

# 第二页（用上一页最后一条的 sort 值）
GET /query_practice/_search
{
  "size": 3,
  "sort": [
    { "sales_count": "desc" },
    { "_id": "asc" }
  ],
  "search_after": [30000, "3"],
  "query": { "match_all": {} }
}

# 3. profile API 对比 query vs filter 性能
GET /query_practice/_search
{
  "profile": true,
  "query": {
    "bool": {
      "must": [
        { "match": { "name": "手机" } },
        { "term": { "status": "active" } }      // status 放在 must 里（打分）
      ]
    }
  }
}

GET /query_practice/_search
{
  "profile": true,
  "query": {
    "bool": {
      "must": [
        { "match": { "name": "手机" } }
      ],
      "filter": [
        { "term": { "status": "active" } }      // status 放在 filter 里（不打分）
      ]
    }
  }
}
# 对比两次 profile 结果中 status 查询的耗时差异

# 4. 高亮练习
GET /query_practice/_search
{
  "query": {
    "match": { "description": "旗舰手机" }
  },
  "highlight": {
    "pre_tags": ["<em>"],
    "post_tags": ["</em>"],
    "fields": {
      "description": {
        "fragment_size": 100,
        "number_of_fragments": 2
      }
    }
  }
}

# 5. 清理
DELETE /query_practice
```

---

## 本阶段总结

学完本阶段，你应该掌握了以下心智模型：

```
查询选型的统一推导框架：
  查询行为 = 查询词是否分词 × 字段类型
  term 不分词 → 配 keyword → 精确匹配
  match 分词  → 配 text    → 全文搜索

查询类型全景：
  全文查询：match / multi_match / match_phrase / query_string
  精确查询：term / range / exists / prefix / fuzzy
  复合查询：bool (must/filter/should/must_not) / dis_max / function_score

BM25 打分三因子：
  TF（词频，有饱和度）× IDF（逆文档频率）× 字段长度归一化

性能优化核心原则：
  不需要打分的条件 → filter（不打分 + 可缓存）
  需要相关性排序的 → must

深度分页三方案：
  全量导出 → scroll
  实时翻页 → search_after
  实时翻页+一致性 → PIT + search_after

调试工具：
  打分不对 → explain API
  查询慢   → profile API
  分词不对 → _analyze API（阶段 3）
```

**前四阶段的因果链现在完整了**：

```
阶段 2 Mapping    → 定义字段类型（text/keyword/数值/...）
阶段 3 Analysis   → 决定 text 怎么分词
阶段 4 Query DSL  → 根据字段类型 + 分词方式，选择正确的查询 + 理解打分机制
                   → 这就是 ES "会用" 层面的完整能力
```

**下一阶段**：阶段 5 聚合深入——搜索找到文档后，如何对结果做统计分析？按品牌分桶计数、求平均价格、算销量百分位……聚合依赖 Doc Values（阶段 2 讲过），通常配合 query 先过滤再聚合（本阶段学的 bool + filter），所以放在阶段 4 之后。
