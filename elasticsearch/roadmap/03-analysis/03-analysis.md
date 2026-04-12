# 阶段 3：分词与文本分析（0.5 周）

> **目标**：完全掌握 ES 分词体系。学完本阶段后，你应该能说清 Analyzer 的三层架构、IK 分词器的选型策略、索引时分词与搜索时分词的区别，以及如何自定义分词器解决实际业务问题（同义词、拼音搜索、自动补全）。
>
> **前置依赖**：阶段 2（Mapping——理解 text 类型会触发分词、keyword 不分词）
>
> **为后续阶段铺路**：分词是连接 Mapping（阶段 2）和 Query DSL（阶段 4）的桥梁。match 查询会对搜索词做分词，term 查询不会——如果你不知道 text 字段被怎么分词的，就无法预测查询结果。学完本阶段后，阶段 4 的所有查询行为都能从「字段类型 + 分词方式」推导出来。
>
> **学习节奏提示**：你已有 IK 分词基础，本阶段不需要从零开始。重点补齐**Analyzer 三层架构**、**search_analyzer**、**自定义 Analyzer** 这三个核心概念，0.5 周足够。

---

## 3.1 分词在 ES 中的位置——分词是什么时候发生的？

阶段 2 结尾留了三个问题：分词器内部怎么工作？IK 的 smart 和 max_word 有什么区别？为什么写入和搜索可以用不同的分词器？这一阶段逐一解答。

首先建立一个全局认知——**分词在 ES 中发生在两个时刻**：

```
写入文档时（Indexing）：
  文档字段值 → Analyzer 分词 → 得到多个 Term → 写入倒排索引

搜索时（Querying）：
  搜索关键词 → Analyzer 分词 → 得到多个 Term → 去倒排索引中匹配

⚠️ 关键理解：写入和搜索用的 Analyzer 可以不同！
```

### 用一个例子串联 Mapping → 分词 → 查询

假设 Mapping 这样定义：

```json
"title": {
  "type": "text",
  "analyzer": "standard"
}
```

**写入时**：文档 `{ "title": "Elasticsearch Is Awesome" }` 经过 standard analyzer：
- `Elasticsearch` → `elasticsearch`（转小写）
- `Is` → `is`（转小写）
- `Awesome` → `awesome`（转小写）

倒排索引中存入三个 Term：`elasticsearch`、`is`、`awesome`

**搜索时**：`match: "Elasticsearch"` 经过相同的 standard analyzer：
- `Elasticsearch` → `elasticsearch`（转小写）

去倒排索引查 `elasticsearch` → ✅ 命中！

**如果用 term 查询呢？** `term: "Elasticsearch"` **不分词**，直接拿 `"Elasticsearch"` 去查——倒排索引里只有 `elasticsearch`（小写）→ ❌ 不命中！

> **这就是阶段 2 讲的 "term 查 text 字段搜不到" 的完整解释**——现在你从分词角度理解了为什么。

### 哪些查询会触发分词？

| 查询类型 | 是否对搜索词分词 | 说明 |
|---------|---------------|------|
| `match` | ✅ 会 | 全文搜索的标准查询 |
| `match_phrase` | ✅ 会 | 分词后还要求顺序和位置匹配 |
| `multi_match` | ✅ 会 | 多字段 match |
| `query_string` | ✅ 会 | 支持 AND/OR 语法的全文查询 |
| `term` | ❌ 不会 | 精确匹配，直接用原始值查倒排索引 |
| `terms` | ❌ 不会 | 多值精确匹配 |
| `range` | ❌ 不会 | 范围查询 |
| `prefix` | ❌ 不会 | 前缀匹配 |
| `wildcard` | ❌ 不会 | 通配符匹配 |

> **一句话记忆**：凡是 `match` 系列的查询都会分词，凡是 `term` 系列的查询都不分词。这直接决定了你该用什么查询查什么类型的字段。

---

## 3.2 Analyzer 三层架构——分词器的拆解

一个 Analyzer 并不是一个不可分割的整体，而是由**三个组件**按顺序组成的流水线：

```
原始文本
  │
  ▼
① Character Filter（字符过滤器）——预处理原始文本
  │  去 HTML 标签、字符替换等
  ▼
② Tokenizer（分词器）——核心：把文本切分成 Token（词元）
  │  按空格切？按 Unicode 切？按中文语义切？
  ▼
③ Token Filter（词元过滤器）——对切好的 Token 做后处理
  │  转小写、去停用词、加同义词、词干提取等
  ▼
最终的 Term 列表 → 写入倒排索引
```

### ① Character Filter（字符过滤器）

在分词之前对原始文本做字符级处理。一个 Analyzer 可以配置 **0 个或多个** Character Filter。

| Character Filter | 作用 | 典型场景 |
|-----------------|------|---------|
| `html_strip` | 去除 HTML 标签，保留纯文本 | 爬虫抓取的网页内容 |
| `mapping` | 字符映射替换（如 `&` → `and`，`①` → `1`） | 特殊字符标准化 |
| `pattern_replace` | 正则替换 | 清理格式化文本 |

**示例**：html_strip 的效果

```
输入：  "<p>Hello <b>World</b></p>"
输出：  "Hello World"
```

### ② Tokenizer（分词器）

核心组件——决定文本**如何被切分**成一个个 Token。一个 Analyzer **有且只有一个** Tokenizer。

| Tokenizer | 切分规则 | 适用场景 |
|-----------|---------|---------|
| `standard` | 按 Unicode 文本分割规则切分（对英文按单词，对中文按单字！） | 默认分词，英文效果好，中文不理想 |
| `whitespace` | 纯按空格切分 | 已经预处理好的文本 |
| `keyword` | 不切分，整个文本作为一个 Token | 需要 Analyzer 的其他组件但不想分词 |
| `pattern` | 按正则表达式切分 | 有规律的分隔符文本（如 CSV） |
| `letter` | 按非字母字符切分 | 简单英文场景 |
| `ik_smart` | 中文最粗粒度智能切分 | 中文搜索时分词 |
| `ik_max_word` | 中文最细粒度切分，穷尽所有组合 | 中文索引时分词 |

**standard 对中文的问题**：

```
standard 分词 "中华人民共和国"：
→ ["中", "华", "人", "民", "共", "和", "国"]   // 每个汉字一个 Token！

ik_smart 分词 "中华人民共和国"：
→ ["中华人民共和国"]                            // 作为一个整体

ik_max_word 分词 "中华人民共和国"：
→ ["中华人民共和国", "中华人民", "中华", "华人",
   "人民共和国", "人民", "共和国", "共和", "国"]  // 穷尽所有可能的组合
```

这就是为什么中文场景**必须使用 IK 等第三方分词器**——standard 把每个汉字单独切开，基本丧失了语义搜索能力。

### ③ Token Filter（词元过滤器）

对 Tokenizer 切好的 Token 做进一步处理。一个 Analyzer 可以配置 **0 个或多个** Token Filter，按顺序依次执行。

| Token Filter | 作用 | 示例 |
|-------------|------|------|
| `lowercase` | 转小写 | `Hello` → `hello` |
| `stop` | 去停用词（the/a/is/的/了/呢） | `"this is a test"` → `"test"` |
| `synonym` | 同义词扩展 | `"北大"` → `"北大"`, `"北京大学"` |
| `stemmer` | 词干提取（英文） | `running` → `run` |
| `edge_ngram` | 从头部开始截取 N-gram | `"hello"` → `"h"`, `"he"`, `"hel"`, `"hell"`, `"hello"` |
| `asciifolding` | 去除变音符号 | `café` → `cafe` |
| `unique` | 去重 | 去掉重复的 Token |

### 内置 Analyzer 的三层拆解

了解了三层架构后，内置分词器就可以「拆开看」了：

| Analyzer | Character Filter | Tokenizer | Token Filter |
|----------|-----------------|-----------|-------------|
| `standard` | - | standard | lowercase |
| `simple` | - | letter | lowercase |
| `whitespace` | - | whitespace | - |
| `keyword` | - | keyword | - |
| `stop` | - | standard | lowercase + stop |

所以当你说一个字段用了 `standard` analyzer 时，实际上是：standard tokenizer（按 Unicode 切分）→ lowercase filter（转小写）。这就是为什么 `"Hello World"` 被索引为 `["hello", "world"]`。

> **面试怎么答**："Analyzer 的三层架构是什么？"
>
> Analyzer 由三个组件按顺序组成：Character Filter → Tokenizer → Token Filter。Character Filter 在分词前对原始文本做预处理（如去 HTML 标签、字符替换）；Tokenizer 是核心，决定文本如何被切分成 Token（如 standard 按 Unicode 切分，IK 按中文语义切分）；Token Filter 对切分后的 Token 做后处理（如转小写、去停用词、加同义词）。一个 Analyzer 可以有 0~N 个 Character Filter、必须有且只有 1 个 Tokenizer、可以有 0~N 个 Token Filter。

---

## 3.3 IK 分词器深入——中文搜索的核心

你已经知道 IK 有 `ik_smart` 和 `ik_max_word` 两种模式。这一节深入理解它们的本质区别和生产选型策略。

### ik_smart vs ik_max_word 的本质

两者使用**同一份词典**，区别在于**切分策略**：

```
原始文本：  "中华人民共和国国歌"

ik_smart（最粗粒度）：
  → ["中华人民共和国", "国歌"]
  策略：尽量切出最长的词，不产生重叠

ik_max_word（最细粒度）：
  → ["中华人民共和国", "中华人民", "中华", "华人", "人民共和国",
     "人民", "共和国", "共和", "国歌"]
  策略：穷尽所有可能的词组合，允许重叠
```

**直觉理解**：
- `ik_smart` = "人脑阅读时看到的切分方式"——我们读"中华人民共和国"不会把它拆成"中华"+"人民"
- `ik_max_word` = "搜索引擎需要的切分方式"——搜"中华"或"人民"时都应该能搜到这篇文档

### 生产选型策略

```
               索引时（写入）              搜索时（查询）
  ┌─────────────────────────┐    ┌─────────────────────────┐
  │  用 ik_max_word          │    │  用 ik_smart            │
  │  最细粒度切分            │    │  最粗粒度切分            │
  │  尽可能多的 Term 进入     │    │  精确的 Term 去匹配      │
  │  倒排索引 → 增加召回率    │    │  倒排索引 → 提高精准度    │
  └─────────────────────────┘    └─────────────────────────┘
```

**为什么这样组合最优？**

假设文档包含 "中华人民共和国"：
- 索引时用 `ik_max_word`：倒排索引中有 `中华人民共和国`、`中华`、`人民`、`共和国` 等多个 Term
- 搜索 "中华"：用 `ik_smart` 分词得到 `中华` → 去倒排索引匹配 → ✅ 命中
- 搜索 "人民共和国"：用 `ik_smart` 分词得到 `人民共和国` → 去倒排索引匹配 → ✅ 命中

如果反过来（索引用 smart，搜索用 max_word）：
- 索引时只存了 `中华人民共和国` 一个 Term
- 搜索 "中华"：`ik_max_word` 分词得到 `中华` → 倒排索引里没有单独的 `中华` → ❌ 搜不到！

**在 Mapping 中配置**：

```json
"title": {
  "type": "text",
  "analyzer": "ik_max_word",        // 索引时：最细粒度
  "search_analyzer": "ik_smart"     // 搜索时：最粗粒度
}
```

> 这就是阶段 2 中 Q4 面试题提到的"阶段 3 后补充"的配置。现在你理解了为什么要这样配了。

### 自定义词典

IK 分词器依赖词典来识别词语。遇到业务专有名词（如产品名、品牌名）时，需要扩展词典。

**方式 1：本地词典**

```
# IK 配置文件路径（相对于 ES 的 plugins 目录）：
# plugins/ik/config/IKAnalyzer.cfg.xml

<?xml version="1.0" encoding="UTF-8"?>
<properties>
  <comment>IK Analyzer 扩展配置</comment>
  <entry key="ext_dict">my_custom.dic</entry>        <!-- 自定义扩展词典 -->
  <entry key="ext_stopwords">my_stopwords.dic</entry> <!-- 自定义停用词 -->
</properties>
```

```
# my_custom.dic（每行一个词，UTF-8 编码）
华为 Mate 60
麒麟芯片
鸿蒙系统
奥特曼
ChatGPT
```

添加后需要**重启 ES 节点**才能生效。

**方式 2：远程热更新词典**

```xml
<entry key="remote_ext_dict">http://your-server/dict/custom.dic</entry>
<entry key="remote_ext_stopwords">http://your-server/dict/stopwords.dic</entry>
```

- ES 定期（默认 60s）轮询远程 URL
- 通过 HTTP 响应头的 `Last-Modified` 或 `ETag` 判断是否有更新
- 有更新时自动加载，**不需要重启 ES**
- 生产环境推荐使用远程热更新，方便运维

**词典优先级**：自定义词典 > IK 内置主词典。如果你的自定义词 "奥特曼" 在 IK 主词典中不存在，加入自定义词典后就能被正确识别为一个完整的词。

> **面试怎么答**："ik_smart 和 ik_max_word 的区别？生产中怎么选？"
>
> ik_smart 做最粗粒度切分，"中华人民共和国"只切成一个词；ik_max_word 穷尽所有可能的词组合。生产中的标准做法是索引时用 ik_max_word 尽可能多地把 Term 写入倒排索引提高召回率，搜索时用 ik_smart 用最精确的切分去匹配提高精准度。在 Mapping 中通过 analyzer 和 search_analyzer 分别指定。

---

## 3.4 索引时分词 vs 搜索时分词——search_analyzer

这是本阶段最重要的概念之一。阶段 2 中有多处提到"阶段 3 后补充"——这里就是补充的地方。

### 两个时刻，两个 Analyzer

```
Mapping 中的配置：

"title": {
  "type": "text",
  "analyzer": "ik_max_word",       ← 索引时（写入文档时）用这个
  "search_analyzer": "ik_smart"    ← 搜索时（match 查询时）用这个
}

如果不指定 search_analyzer → 默认和 analyzer 相同
```

### 为什么要用不同的 Analyzer？

| 场景 | 索引时用 ik_max_word | 搜索时用 ik_smart |
|------|-------------------|-----------------|
| 文档: "中华人民共和国" | Terms: [中华人民共和国, 中华人民, 中华, 华人, 人民共和国, 人民, 共和国, 共和, 国] | - |
| 搜索: "中华" | - | Terms: [中华] → ✅ 匹配到 "中华" |
| 搜索: "人民" | - | Terms: [人民] → ✅ 匹配到 "人民" |
| 搜索: "中华人民共和国" | - | Terms: [中华人民共和国] → ✅ 匹配到 "中华人民共和国" |

**每一个搜索词都能匹配到**，因为索引端已经穷尽了所有 Term 组合。

如果两端都用 `ik_max_word`：
- 搜索 "中华人民共和国" → 分词成 9 个 Term → 这 9 个 Term 都去匹配 → 结果太多太杂，精准度下降
- 而且每一个 Term 都会参与打分，导致相关性分数不准确

**一句话总结**：索引端求"全"（召回率），搜索端求"准"（精准度）。

### Analyzer 解析优先级

当 ES 执行 match 查询时，搜索端的 Analyzer 按以下优先级确定：

```
1. 查询中显式指定的 analyzer（最高优先）
   GET /products/_search
   { "query": { "match": { "title": { "query": "手机", "analyzer": "ik_smart" } } } }

2. Mapping 中字段的 search_analyzer

3. Mapping 中字段的 analyzer

4. 索引 settings 中的 analysis.analyzer.default_search

5. 索引 settings 中的 analysis.analyzer.default

6. standard analyzer（兜底）
```

生产中通常在 Mapping 层面配好 `analyzer` + `search_analyzer`，不需要每次查询都指定。

---

## 3.5 自定义 Analyzer——组装你自己的分词器

除了使用内置和第三方 Analyzer，你还可以在索引的 `settings` 中自由组合三层组件，创建自定义 Analyzer。

### 基本语法

```json
PUT /my_index
{
  "settings": {
    "analysis": {
      "char_filter": {
        "my_char_filter": { ... }          // 自定义 Character Filter
      },
      "tokenizer": {
        "my_tokenizer": { ... }            // 自定义 Tokenizer
      },
      "filter": {
        "my_token_filter": { ... }         // 自定义 Token Filter
      },
      "analyzer": {
        "my_analyzer": {                   // 组装自定义 Analyzer
          "type": "custom",
          "char_filter": ["my_char_filter"],
          "tokenizer": "my_tokenizer",
          "filter": ["lowercase", "my_token_filter"]
        }
      }
    }
  }
}
```

### 实战场景 1：HTML 内容搜索

爬虫抓取的内容带有 HTML 标签，搜索时需要忽略标签：

```json
PUT /web_pages
{
  "settings": {
    "analysis": {
      "analyzer": {
        "html_content_analyzer": {
          "type": "custom",
          "char_filter": ["html_strip"],       // 先去 HTML 标签
          "tokenizer": "ik_max_word",          // 再用 IK 分词
          "filter": ["lowercase"]              // 最后转小写
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "content": {
        "type": "text",
        "analyzer": "html_content_analyzer"
      }
    }
  }
}
```

效果：

```
输入：  "<p>华为发布了<b>Mate 60 Pro</b>手机</p>"
→ html_strip:   "华为发布了Mate 60 Pro手机"
→ ik_max_word:  ["华为", "发布", "了", "mate", "60", "pro", "手机"]
→ lowercase:    ["华为", "发布", "了", "mate", "60", "pro", "手机"]
```

### 实战场景 2：边缘 N-gram 自动补全

搜索框"输入即搜索"（search-as-you-type）效果：用户只输入 "ipho" 就应该匹配到 "iPhone"。

```json
PUT /products_autocomplete
{
  "settings": {
    "analysis": {
      "tokenizer": {
        "edge_ngram_tokenizer": {
          "type": "edge_ngram",
          "min_gram": 1,                    // 最短 1 个字符
          "max_gram": 15,                   // 最长 15 个字符
          "token_chars": ["letter", "digit"]  // 按字母和数字切
        }
      },
      "analyzer": {
        "autocomplete_index": {
          "type": "custom",
          "tokenizer": "edge_ngram_tokenizer",
          "filter": ["lowercase"]
        },
        "autocomplete_search": {
          "type": "custom",
          "tokenizer": "standard",           // 搜索时不做 N-gram，用标准分词
          "filter": ["lowercase"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "name": {
        "type": "text",
        "analyzer": "autocomplete_index",       // 索引时：切成 N-gram
        "search_analyzer": "autocomplete_search" // 搜索时：不做 N-gram
      }
    }
  }
}
```

效果：

```
索引 "iPhone"：
→ edge_ngram: ["i", "ip", "iph", "ipho", "iphon", "iphone"]
→ 这些 Term 全部进入倒排索引

搜索 "ipho"：
→ standard + lowercase: ["ipho"]
→ 匹配倒排索引中的 "ipho" → ✅ 命中！

搜索 "ip"：
→ standard + lowercase: ["ip"]
→ 匹配倒排索引中的 "ip" → ✅ 命中！
```

> 这就是阶段 2 中 Multi-fields 进阶示例里 `edge_ngram_analyzer` 的完整实现。

### 实战场景 3：拼音搜索（需要 pinyin 插件）

```json
PUT /products_pinyin
{
  "settings": {
    "analysis": {
      "analyzer": {
        "pinyin_analyzer": {
          "type": "custom",
          "tokenizer": "ik_max_word",
          "filter": ["pinyin_filter", "lowercase"]
        }
      },
      "filter": {
        "pinyin_filter": {
          "type": "pinyin",
          "keep_full_pinyin": true,            // "华为" → "huawei"
          "keep_first_letter": true,           // "华为" → "hw"
          "keep_original": true,               // 保留原始中文
          "limit_first_letter_length": 16,
          "remove_duplicated_term": true
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "name": {
        "type": "text",
        "analyzer": "pinyin_analyzer"
      }
    }
  }
}
```

效果：索引 "华为手机" 后，搜索 `"huawei"`、`"hw"`、`"华为"` 都能匹配。

> **注意**：pinyin 插件需要单独安装（`./bin/elasticsearch-plugin install analysis-pinyin`），不是 ES 自带的。

---

## 3.6 同义词与停用词

### 同义词（Synonym）

同义词是搜索体验优化的利器——搜 "北大" 也能搜到 "北京大学"，搜 "手机" 也能搜到 "移动电话"。

**方式 1：内联配置**

```json
PUT /my_index
{
  "settings": {
    "analysis": {
      "filter": {
        "my_synonym_filter": {
          "type": "synonym",
          "synonyms": [
            "北大,北京大学",
            "手机,移动电话,mobile phone",
            "ES,Elasticsearch"
          ]
        }
      },
      "analyzer": {
        "synonym_analyzer": {
          "type": "custom",
          "tokenizer": "ik_smart",
          "filter": ["my_synonym_filter"]
        }
      }
    }
  }
}
```

**方式 2：文件配置（推荐）**

```json
"my_synonym_filter": {
  "type": "synonym",
  "synonyms_path": "analysis/synonyms.txt"    // 相对于 ES 的 config 目录
}
```

```
# synonyms.txt（每行一组同义词，逗号分隔）
北大,北京大学
手机,移动电话,mobile phone
ES,Elasticsearch
```

**方式 3：synonym_graph（ES 5.4+，推荐用于搜索时）**

```json
"my_synonym_filter": {
  "type": "synonym_graph",       // 比 synonym 更准确地处理多词同义词
  "synonyms_path": "analysis/synonyms.txt"
}
```

### 同义词放在索引时还是搜索时？

| 选项 | 优点 | 缺点 |
|------|------|------|
| **索引时** | 查询时不需要额外扩展，性能好 | 修改同义词需要 Reindex 所有数据 |
| **搜索时** | 修改同义词立即生效，无需 Reindex | 每次搜索都要做同义词扩展，查询稍慢 |

**生产建议**：**同义词放在搜索时（search_analyzer）更灵活**。因为同义词词库会随业务频繁变化（新增品牌名、流行词等），放在索引时每次改动都要 Reindex 成本太高。

```json
"title": {
  "type": "text",
  "analyzer": "ik_max_word",                // 索引时：不做同义词扩展
  "search_analyzer": "ik_smart_with_synonym" // 搜索时：做同义词扩展
}
```

### 停用词（Stop Words）

停用词是对搜索没有价值的高频词，过滤掉可以减少索引大小和噪音。

```
英文停用词：the, a, an, is, are, was, were, this, that, of, in, for, to, and ...
中文停用词：的, 了, 呢, 吗, 是, 在, 有, 和, 与, 或 ...
```

```json
"my_stop_filter": {
  "type": "stop",
  "stopwords_path": "analysis/stopwords.txt"
}
```

> **谨慎使用停用词**：有些看似是停用词的词在特定场景有意义。比如搜索 "to be or not to be"，如果去掉停用词就变成空查询了。一般中文场景的停用词问题比英文少。

> **面试怎么答**："如何实现搜索'北京大学'也能搜到'北大'？"
>
> 使用同义词（Synonym）Token Filter。在 ES 的 analysis 配置中定义一个同义词过滤器，配置同义词映射 "北大,北京大学"。推荐在搜索时做同义词扩展（配置在 search_analyzer 中），这样修改同义词词库后立即生效，不需要 Reindex。具体实现是创建一个 custom analyzer，tokenizer 用 ik_smart，filter 加上 synonym_graph，然后在 Mapping 中将这个 analyzer 指定为字段的 search_analyzer。

---

## 3.7 Normalizer——keyword 字段的"轻量分词"

Analyzer 是给 `text` 字段用的。但有时候 `keyword` 字段也需要做一些标准化处理——比如大小写不敏感的精确匹配。这时候用 **Normalizer**。

### Normalizer 与 Analyzer 的区别

| 维度 | Analyzer | Normalizer |
|------|----------|-----------|
| 适用字段 | text | keyword |
| 是否分词 | ✅ 是（Tokenizer 把文本切成多个 Token） | ❌ 否（整个值作为一个 Token） |
| 包含组件 | Character Filter + Tokenizer + Token Filter | Character Filter + Token Filter（没有 Tokenizer！） |
| 输出 | 多个 Term | 一个 Term（标准化后的整体值） |

```
Analyzer 处理 "Hello World"：
→ Tokenizer 切分 → ["hello", "world"]（两个 Term）

Normalizer 处理 "Hello World"：
→ 没有 Tokenizer → "hello world"（一个 Term，只做了小写转换）
```

### 典型场景：大小写不敏感的精确匹配

```json
PUT /users
{
  "settings": {
    "analysis": {
      "normalizer": {
        "lowercase_normalizer": {
          "type": "custom",
          "filter": ["lowercase"]         // 只做小写转换
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "email": {
        "type": "keyword",
        "normalizer": "lowercase_normalizer"
      }
    }
  }
}
```

效果：

```
写入：{ "email": "User@Example.COM" }
→ Normalizer 处理后，倒排索引中存的是 "user@example.com"

查询：term: "user@example.com"  → ✅ 命中
查询：term: "User@Example.COM"  → ✅ 也能命中（查询词也会经过 Normalizer）
```

**没有 Normalizer 时**：keyword 字段大小写敏感，`"User@Example.COM"` 和 `"user@example.com"` 是两个不同的 Term，必须完全一致才能匹配。

### 其他 Normalizer 用途

- 去除前后空格（配合 `trim` filter）
- 变音符号标准化（`asciifolding`：`café` → `cafe`）
- 在 keyword 上做自定义字符映射

---

## 3.8 _analyze API——分词调试利器

`_analyze` API 是学习和调试分词的**最重要工具**。它让你直接看到一段文本被某个 Analyzer 分词后的结果。

### 基本用法

```
# 用内置 Analyzer 测试
POST /_analyze
{
  "analyzer": "standard",
  "text": "Elasticsearch is awesome"
}

# 返回结果：
{
  "tokens": [
    { "token": "elasticsearch", "start_offset": 0, "end_offset": 13, "position": 0 },
    { "token": "is",            "start_offset": 14, "end_offset": 16, "position": 1 },
    { "token": "awesome",       "start_offset": 17, "end_offset": 24, "position": 2 }
  ]
}
```

### 对比不同 Analyzer

```
# standard 分词中文
POST /_analyze
{
  "analyzer": "standard",
  "text": "中华人民共和国国歌"
}
# → ["中", "华", "人", "民", "共", "和", "国", "国", "歌"] （逐字切分，无语义）

# ik_smart 分词中文
POST /_analyze
{
  "analyzer": "ik_smart",
  "text": "中华人民共和国国歌"
}
# → ["中华人民共和国", "国歌"]

# ik_max_word 分词中文
POST /_analyze
{
  "analyzer": "ik_max_word",
  "text": "中华人民共和国国歌"
}
# → ["中华人民共和国", "中华人民", "中华", "华人", "人民共和国", "人民", "共和国", "共和", "国歌"]
```

### 测试自定义 Analyzer

```
# 临时组合三层组件测试（不需要创建索引）
POST /_analyze
{
  "char_filter": ["html_strip"],
  "tokenizer": "ik_smart",
  "filter": ["lowercase"],
  "text": "<p>华为发布了Mate 60 Pro</p>"
}
# → ["华为", "发布", "了", "mate", "60", "pro"]
```

### 测试指定字段的 Analyzer

```
# 测试某个索引中某个字段实际使用的 Analyzer
POST /shop_products/_analyze
{
  "field": "name",
  "text": "华为 Mate 60 Pro 手机"
}
```

这个用法在调试时非常有用——当你不确定某个字段实际用了什么 Analyzer 时，直接用 `field` 参数测试。

### _analyze 的调试流程

当搜索结果不符合预期时，用 `_analyze` 来排查是最高效的方式：

```
搜索 "华为手机" 在 name 字段上没有返回预期的文档？

排查步骤：
1. 用 _analyze 看 name 字段在索引时怎么分词的：
   POST /products/_analyze { "field": "name", "text": "华为 Mate 60 Pro 手机" }
   → 看倒排索引里有哪些 Term

2. 用 _analyze 看搜索词怎么分词的（用 search_analyzer）：
   POST /_analyze { "analyzer": "ik_smart", "text": "华为手机" }
   → 看搜索端产生了哪些 Term

3. 对比两边的 Term 是否有交集
   → 有交集就能匹配，没有就匹配不到
```

---

## 面试高频题与参考答案

### Q1：Analyzer 的三层架构是什么？

**答**：Analyzer 由三个组件按顺序组成流水线：

第一层是 Character Filter（字符过滤器），在分词前对原始文本做预处理，比如 html_strip 去除 HTML 标签、mapping 做字符替换。一个 Analyzer 可以有 0 到多个 Character Filter。

第二层是 Tokenizer（分词器），核心组件，决定文本如何切分成 Token。比如 standard 按 Unicode 规则切分，whitespace 按空格切分，ik_smart/ik_max_word 按中文语义切分。一个 Analyzer 必须且只能有一个 Tokenizer。

第三层是 Token Filter（词元过滤器），对 Tokenizer 切出的 Token 做后处理。比如 lowercase 转小写、stop 去停用词、synonym 加同义词。一个 Analyzer 可以有 0 到多个 Token Filter。

比如 standard analyzer 就是 standard tokenizer + lowercase filter 的组合，所以 "Hello World" 会被处理为 ["hello", "world"]。

### Q2：ik_smart 和 ik_max_word 的区别？生产中怎么选？

**答**：两者使用同一份词典，区别在于切分策略。ik_smart 做最粗粒度切分，"中华人民共和国"只切成一个词；ik_max_word 穷尽所有可能的词组合，切成"中华人民共和国""中华""人民""共和国"等多个词。

生产中的标准做法是**索引时用 ik_max_word，搜索时用 ik_smart**。索引端用最细粒度切分让尽可能多的 Term 进入倒排索引，提高召回率；搜索端用最粗粒度切分，用最精确的 Term 去匹配，提高精准度。在 Mapping 中通过 `analyzer: "ik_max_word"` 和 `search_analyzer: "ik_smart"` 分别配置。

### Q3：如何实现搜索"北京大学"也能搜到"北大"？

**答**：使用同义词（Synonym）功能。具体做法是创建一个自定义 Analyzer，在 Token Filter 中加入 synonym 或 synonym_graph 组件，配置同义词映射 `"北大,北京大学"`。

建议在**搜索时做同义词扩展**——把这个自定义 Analyzer 配置为字段的 `search_analyzer`，而不是索引时的 `analyzer`。这样修改同义词词库后立即生效，不需要 Reindex 全量数据。同义词词库可以用文件配置（`synonyms_path`），便于维护和更新。

### Q4：索引时分词和搜索时分词可以不同吗？为什么？

**答**：可以，通过 Mapping 中的 `analyzer`（索引时）和 `search_analyzer`（搜索时）分别指定。如果不指定 search_analyzer，默认与 analyzer 相同。

之所以要用不同的分词器，是因为索引端和搜索端的目标不同。索引端追求召回率，用 ik_max_word 最细粒度切分，让更多 Term 进入倒排索引；搜索端追求精准度，用 ik_smart 最粗粒度切分，用最准确的 Term 去匹配。这个组合能平衡召回率和精准度。

另一个典型场景是同义词——索引时不做同义词扩展，搜索时做同义词扩展，这样修改同义词后不需要 Reindex。

### Q5：如何给 ES 添加自定义词典？支持热更新吗？

**答**：IK 分词器支持两种方式的自定义词典。

第一种是本地词典文件：在 IK 插件的 config 目录下创建 .dic 文件（每行一个词，UTF-8 编码），然后在 IKAnalyzer.cfg.xml 中配置 `ext_dict` 指向这个文件。缺点是需要**重启 ES 节点**才能生效。

第二种是远程热更新：在 IKAnalyzer.cfg.xml 中配置 `remote_ext_dict` 指向一个 HTTP URL，IK 会定期轮询（默认 60 秒），通过 HTTP 响应头的 Last-Modified 或 ETag 判断是否有更新，有更新时自动加载，不需要重启 ES。生产环境推荐使用远程热更新方式。

---

## 动手实践

### 练习 1：_analyze API 对比分词结果

```
# 1. 对比 standard / ik_smart / ik_max_word 对同一段中文的分词效果

POST /_analyze
{
  "analyzer": "standard",
  "text": "华为发布了最新的Mate 60 Pro智能手机"
}

POST /_analyze
{
  "analyzer": "ik_smart",
  "text": "华为发布了最新的Mate 60 Pro智能手机"
}

POST /_analyze
{
  "analyzer": "ik_max_word",
  "text": "华为发布了最新的Mate 60 Pro智能手机"
}

# 观察：
# - standard 会把每个汉字单独切开，对中文基本不可用
# - ik_smart 切出有意义的词，数量最少
# - ik_max_word 切出所有可能的词组合，数量最多

# 2. 对比英文分词
POST /_analyze
{
  "analyzer": "standard",
  "text": "The Quick Brown Fox jumps over the Lazy Dog"
}

POST /_analyze
{
  "analyzer": "whitespace",
  "text": "The Quick Brown Fox jumps over the Lazy Dog"
}

# 观察：
# - standard 转了小写，whitespace 没有
# - standard 和 whitespace 都按空格切了词

# 3. 临时组合三层组件测试（不需要创建索引）
POST /_analyze
{
  "char_filter": ["html_strip"],
  "tokenizer": "ik_smart",
  "filter": ["lowercase"],
  "text": "<div>华为<b>Mate 60</b>手机</div>"
}
# 观察 HTML 标签是否被正确去除
```

### 练习 2：自定义 Analyzer + 同义词 + search_analyzer

```
# 1. 创建索引——包含自定义 Analyzer 和同义词
PUT /search_test
{
  "settings": {
    "analysis": {
      "filter": {
        "my_synonym_filter": {
          "type": "synonym",
          "synonyms": [
            "北大,北京大学",
            "手机,移动电话",
            "ES,Elasticsearch"
          ]
        }
      },
      "analyzer": {
        "ik_index_analyzer": {
          "type": "custom",
          "tokenizer": "ik_max_word"
        },
        "ik_search_with_synonym": {
          "type": "custom",
          "tokenizer": "ik_smart",
          "filter": ["my_synonym_filter"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "analyzer": "ik_index_analyzer",
        "search_analyzer": "ik_search_with_synonym"
      }
    }
  }
}

# 2. 写入测试数据
POST /_bulk
{"index": {"_index": "search_test", "_id": "1"}}
{"title": "北京大学2024年招生简章"}
{"index": {"_index": "search_test", "_id": "2"}}
{"title": "清华大学计算机系介绍"}
{"index": {"_index": "search_test", "_id": "3"}}
{"title": "Elasticsearch 入门教程"}
{"index": {"_index": "search_test", "_id": "4"}}
{"title": "华为最新智能手机发布"}

# 3. 测试同义词效果
# 搜 "北大" 能否搜到 "北京大学"？
GET /search_test/_search
{
  "query": { "match": { "title": "北大" } }
}
# 预期：应该能搜到 doc 1（北京大学）

# 搜 "移动电话" 能否搜到 "手机"？
GET /search_test/_search
{
  "query": { "match": { "title": "移动电话" } }
}
# 预期：应该能搜到 doc 4（手机）

# 搜 "ES" 能否搜到 "Elasticsearch"？
GET /search_test/_search
{
  "query": { "match": { "title": "ES" } }
}
# 预期：应该能搜到 doc 3（Elasticsearch）

# 4. 用 _analyze 验证同义词扩展
POST /search_test/_analyze
{
  "analyzer": "ik_search_with_synonym",
  "text": "北大"
}
# 预期：看到 "北大" 和 "北京大学" 两个 Term

# 5. 清理
DELETE /search_test
```

### 练习 3：对比 analyzer 和 search_analyzer 的差异

```
# 1. 创建索引——索引时和搜索时用不同的 Analyzer
PUT /analyzer_diff_test
{
  "settings": {
    "analysis": {
      "analyzer": {
        "index_analyzer": {
          "type": "custom",
          "tokenizer": "ik_max_word"
        },
        "search_analyzer_smart": {
          "type": "custom",
          "tokenizer": "ik_smart"
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "content": {
        "type": "text",
        "analyzer": "index_analyzer",
        "search_analyzer": "search_analyzer_smart"
      }
    }
  }
}

# 2. 写入文档
PUT /analyzer_diff_test/_doc/1
{
  "content": "中华人民共和国成立于1949年"
}

# 3. 看索引时分了哪些 Term
POST /analyzer_diff_test/_analyze
{
  "field": "content",
  "text": "中华人民共和国成立于1949年"
}
# 注意看：ik_max_word 会切出很多 Term（中华人民共和国、中华人民、中华、人民...）

# 4. 看搜索时分了哪些 Term
POST /_analyze
{
  "analyzer": "ik_smart",
  "text": "中华"
}
# 注意看：ik_smart 只切出 "中华" 一个 Term

# 5. 测试搜索——"中华" 能搜到吗？
GET /analyzer_diff_test/_search
{
  "query": { "match": { "content": "中华" } }
}
# ✅ 能搜到！因为索引时 ik_max_word 把 "中华" 也作为一个 Term 存入了倒排索引

# 6. 测试搜索——"人民" 能搜到吗？
GET /analyzer_diff_test/_search
{
  "query": { "match": { "content": "人民" } }
}
# ✅ 也能搜到！同理

# 7. 清理
DELETE /analyzer_diff_test
```

---

## 本阶段总结

学完本阶段，你应该掌握了以下心智模型：

```
分词 = 文本进入/查询倒排索引的桥梁

Analyzer 三层架构：
  Character Filter → Tokenizer → Token Filter
  （字符预处理）      （核心切分）   （Token 后处理）

分词发生在两个时刻：
  写入时：文档字段值 → analyzer → Terms → 写入倒排索引
  搜索时：搜索关键词 → search_analyzer → Terms → 匹配倒排索引

中文搜索标准配置：
  索引时：ik_max_word（最细粒度，增加召回率）
  搜索时：ik_smart（最粗粒度，提高精准度）

Normalizer（给 keyword 用的轻量处理）：
  不分词，只做字符标准化（如 lowercase）
  keyword 大小写不敏感匹配的唯一正解

调试分词的万能工具：_analyze API
  搜索结果不符预期？→ 先用 _analyze 看两端的 Term 有没有交集
```

**关键因果链——现在你已经完整掌握了前三阶段的串联逻辑**：

```
阶段 2 Mapping 决定字段类型
  → text 类型触发 Analyzer
    → 阶段 3 Analyzer 决定分什么词
      → 分出的 Term 写入倒排索引
        → 阶段 4 Query DSL 决定如何匹配这些 Term
```

**下一阶段**：阶段 4 Query DSL 深入——你已经知道了 text 字段怎么分词、keyword 字段不分词，现在可以真正理解 match 查询为什么能搜到、term 查询为什么搜不到、bool 查询的 must/filter/should 有什么区别、BM25 打分是怎么算的了。阶段 4 是 ES 使用层面最核心、内容最丰富的一个阶段。
