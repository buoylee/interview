# 阶段 5：聚合深入（1 周）

> **目标**：系统掌握 ES 的聚合分析能力。学完本阶段后，你应该能用 Bucket + Metric + Pipeline 聚合组合实现各种统计分析需求，理解近似聚合的原理和精度取舍，并能用 Composite 聚合解决大数据量的聚合分页问题。
>
> **前置依赖**：阶段 2（Mapping——Doc Values 决定是否可聚合）+ 阶段 4（Query DSL——聚合通常和 query 配合使用）
>
> **为后续阶段铺路**：聚合是 ES "会用"层的最后一块拼图。阶段 6（存储原理）会从底层解释 Doc Values 的列式存储结构，帮你理解聚合的性能瓶颈；阶段 8（性能调优）中的聚合优化也基于本阶段的知识。
>
> **聚合 = ES 的数据分析能力**。如果说 Query DSL 回答的是"找到哪些文档"，那聚合回答的就是"这些文档的统计特征是什么"——有多少条、平均价格多少、按品牌怎么分布、销量的百分位是多少。

---

## 5.1 聚合的前置知识——Doc Values

在开始学聚合之前，必须理解一个底层概念——**为什么聚合和排序不走倒排索引？**

### 倒排索引不适合聚合

倒排索引的结构是 `Term → Document List`。当你做聚合（如"按品牌统计商品数量"）时，需要的是反过来的操作——**遍历每个文档，拿到它的品牌值**。

```
倒排索引（Term → Doc）：
  "Apple"  → [doc1, doc5, doc10]
  "华为"   → [doc2, doc4, doc6]
  "小米"   → [doc3, doc7]

聚合需要（Doc → Value）：
  doc1 → "Apple"
  doc2 → "华为"
  doc3 → "小米"
  doc4 → "华为"
  ...

用倒排索引做聚合 = 反向遍历整个倒排索引 → 非常低效
```

### Doc Values——为聚合而生的列式存储

**Doc Values** 是 ES 在写入时自动构建的**列式存储结构**（类似 Parquet、ORC），存在磁盘上。

```
Doc Values（列式存储，Doc → Value）：

doc_id  | brand    | price  | created_at
--------|----------|--------|------------
0       | "Apple"  | 9999   | 1710892800
1       | "华为"   | 6999   | 1710806400
2       | "小米"   | 5999   | 1706745600
3       | "华为"   | 4999   | 1704844800
...

聚合"按品牌统计"：直接扫描 brand 列 → 非常快
排序"按价格排"：直接扫描 price 列 → 非常快
```

### 哪些字段有 Doc Values？

| 字段类型 | 是否自动启用 Doc Values | 能否聚合/排序 |
|---------|----------------------|-------------|
| `keyword` | ✅ 自动启用 | ✅ |
| `long` / `integer` / `float` 等数值 | ✅ 自动启用 | ✅ |
| `date` | ✅ 自动启用 | ✅ |
| `boolean` | ✅ 自动启用 | ✅ |
| `geo_point` | ✅ 自动启用 | ✅ |
| **`text`** | **❌ 没有 Doc Values** | **❌ 不能直接聚合** |

### text 字段想聚合怎么办？

**方案 1（推荐）：用 keyword 子字段**

```
# text 字段不能聚合
GET /products/_search
{ "aggs": { "brands": { "terms": { "field": "name" } } } }
# ❌ 报错或返回无意义的结果

# 用 keyword 子字段聚合
GET /products/_search
{ "aggs": { "brands": { "terms": { "field": "name.keyword" } } } }
# ✅ 正确
```

**方案 2（不推荐）：开启 Fielddata**

```json
PUT /products/_mapping
{
  "properties": {
    "name": {
      "type": "text",
      "fielddata": true    // 在内存中构建 Doc Values
    }
  }
}
```

Fielddata 的问题：
- 在**内存中**构建（不像 Doc Values 在磁盘上）→ 巨大的内存消耗
- text 字段开启后聚合的是**分词后的 Term**，不是原始值（"华为 Mate 60" 变成 "华为"、"mate"、"60" 三个桶）
- 很容易导致 OOM

> **一句话结论**：**永远用 `.keyword` 子字段做字符串聚合，不要开 Fielddata**。

> **面试怎么答**："doc_values 是什么？为什么聚合和排序离不开它？"
>
> Doc Values 是 ES 在写入时自动为 keyword、数值、日期等字段构建的列式存储结构，存在磁盘上。它的结构是 doc_id → field_value，可以按文档顺序快速遍历某个字段的所有值，非常适合聚合和排序。倒排索引是 term → doc_list，做聚合需要反向遍历，效率很低。text 字段没有 Doc Values，所以不能直接聚合排序，生产中用 .keyword 子字段来实现。

---

## 5.2 三大聚合类型

ES 的聚合分为三大类，可以类比 SQL：

```
Bucket 聚合 ≈ GROUP BY     → 分桶（把文档分成不同的组）
Metric 聚合 ≈ SUM/AVG/MAX  → 统计（对每个桶内的文档计算指标）
Pipeline 聚合 ≈ 窗口函数    → 对聚合结果再做运算（环比、累计、移动平均）
```

### Bucket 聚合——分桶

Bucket 聚合把文档按条件分到不同的"桶"里。每个桶包含一组文档，可以在桶内嵌套 Metric 聚合做进一步统计。

#### terms 聚合——按字段值分桶

```
# 按品牌分桶，统计每个品牌的商品数量
GET /products/_search
{
  "size": 0,                    // 不需要返回文档，只要聚合结果
  "aggs": {
    "brand_distribution": {
      "terms": {
        "field": "brand",       // 必须是 keyword 或数值类型
        "size": 10,             // 返回 Top 10 个桶
        "order": { "_count": "desc" }  // 按文档数量降序（默认）
      }
    }
  }
}

# 返回结果：
{
  "aggregations": {
    "brand_distribution": {
      "buckets": [
        { "key": "华为", "doc_count": 3 },
        { "key": "Apple", "doc_count": 3 },
        { "key": "小米", "doc_count": 2 },
        { "key": "三星", "doc_count": 1 },
        { "key": "OPPO", "doc_count": 1 }
      ]
    }
  }
}
```

#### date_histogram——按时间区间分桶

```
# 按月统计商品上架数量
GET /products/_search
{
  "size": 0,
  "aggs": {
    "monthly_count": {
      "date_histogram": {
        "field": "created_at",
        "calendar_interval": "month",     // 按月分桶
        "format": "yyyy-MM",
        "min_doc_count": 0                // 即使某月没有数据也显示（doc_count=0）
      }
    }
  }
}
```

`calendar_interval` vs `fixed_interval`：
- `calendar_interval`：按日历（`month`、`quarter`、`year`）——每个桶长度可变（1 月 31 天，2 月 28 天）
- `fixed_interval`：按固定时长（`30d`、`1h`、`5m`）——每个桶完全等长

#### histogram——按数值区间分桶

```
# 按价格区间分桶（每 2000 元一个桶）
GET /products/_search
{
  "size": 0,
  "aggs": {
    "price_ranges": {
      "histogram": {
        "field": "price",
        "interval": 2000,
        "min_doc_count": 1
      }
    }
  }
}
```

#### range——自定义范围分桶

```
# 自定义价格区间（低/中/高端）
GET /products/_search
{
  "size": 0,
  "aggs": {
    "price_tiers": {
      "range": {
        "field": "price",
        "ranges": [
          { "key": "低端", "to": 3000 },
          { "key": "中端", "from": 3000, "to": 7000 },
          { "key": "高端", "from": 7000 }
        ]
      }
    }
  }
}
```

#### filters——按多个查询条件分桶

```
# 按自定义条件分桶
GET /products/_search
{
  "size": 0,
  "aggs": {
    "categories": {
      "filters": {
        "filters": {
          "华为手机": { "bool": { "must": [{ "term": { "brand": "华为" } }, { "term": { "category": "手机" } }] } },
          "苹果产品": { "term": { "brand": "Apple" } },
          "其他": { "match_all": {} }
        }
      }
    }
  }
}
```

### Metric 聚合——统计指标

Metric 聚合对一组文档计算统计值。通常嵌套在 Bucket 聚合内，对每个桶计算指标。

#### 基础统计

```
# avg / sum / min / max
"aggs": {
  "avg_price": { "avg": { "field": "price" } },
  "total_sales": { "sum": { "field": "sales_count" } },
  "min_price": { "min": { "field": "price" } },
  "max_price": { "max": { "field": "price" } }
}

# stats——一次返回 count + min + max + avg + sum
"aggs": {
  "price_stats": { "stats": { "field": "price" } }
}

# extended_stats——额外返回方差、标准差等
"aggs": {
  "price_extended": { "extended_stats": { "field": "price" } }
}
```

#### cardinality——去重计数

```
# 统计有多少个不同的品牌（类似 SQL 的 COUNT(DISTINCT brand)）
"aggs": {
  "unique_brands": {
    "cardinality": {
      "field": "brand",
      "precision_threshold": 100    // 精度阈值（下一节详讲）
    }
  }
}
```

#### percentiles——百分位数

```
# 统计价格的 P50、P90、P99
"aggs": {
  "price_percentiles": {
    "percentiles": {
      "field": "price",
      "percents": [50, 90, 95, 99]
    }
  }
}
# 结果示例：P50=5999, P90=9999, P95=12000, P99=14999
```

#### top_hits——桶内取原始文档

```
# 每个品牌的最畅销商品（Top 1）
"aggs": {
  "by_brand": {
    "terms": { "field": "brand" },
    "aggs": {
      "top_product": {
        "top_hits": {
          "size": 1,
          "sort": [{ "sales_count": "desc" }],
          "_source": ["name", "price", "sales_count"]
        }
      }
    }
  }
}
```

类似 SQL 的 `GROUP BY brand ORDER BY sales_count DESC LIMIT 1`。

#### value_count——文档计数

```
"aggs": {
  "total_products": { "value_count": { "field": "brand" } }
}
```

### Pipeline 聚合——对聚合结果再运算

Pipeline 聚合不直接操作文档，而是**对其他聚合的结果做二次运算**。

#### derivative——求导（变化率/环比）

```
# 按月统计销量，然后求月环比变化量
GET /products/_search
{
  "size": 0,
  "aggs": {
    "monthly": {
      "date_histogram": {
        "field": "created_at",
        "calendar_interval": "month"
      },
      "aggs": {
        "monthly_sales": { "sum": { "field": "sales_count" } },
        "sales_change": {
          "derivative": {
            "buckets_path": "monthly_sales"    // 引用兄弟聚合
          }
        }
      }
    }
  }
}
# 结果：每个月的总销量 + 相比上月的变化量
```

#### cumulative_sum——累计求和

```
"aggs": {
  "monthly": {
    "date_histogram": { "field": "created_at", "calendar_interval": "month" },
    "aggs": {
      "monthly_sales": { "sum": { "field": "sales_count" } },
      "running_total": {
        "cumulative_sum": { "buckets_path": "monthly_sales" }
      }
    }
  }
}
# 结果：1月销量, 1+2月累计, 1+2+3月累计...
```

#### bucket_sort——对桶排序

```
# 按品牌统计平均价格，然后按平均价格降序排列
"aggs": {
  "by_brand": {
    "terms": { "field": "brand", "size": 20 },
    "aggs": {
      "avg_price": { "avg": { "field": "price" } },
      "sort_by_price": {
        "bucket_sort": {
          "sort": [{ "avg_price": { "order": "desc" } }],
          "size": 5                               // 只取 Top 5
        }
      }
    }
  }
}
```

#### bucket_selector——按条件过滤桶

```
# 只保留平均价格 > 5000 的品牌
"aggs": {
  "by_brand": {
    "terms": { "field": "brand", "size": 20 },
    "aggs": {
      "avg_price": { "avg": { "field": "price" } },
      "price_filter": {
        "bucket_selector": {
          "buckets_path": { "avgPrice": "avg_price" },
          "script": "params.avgPrice > 5000"
        }
      }
    }
  }
}
```

### 三大聚合类型对比

```
               聚合全景图
 ┌──────────────────────────────────────┐
 │          查询结果文档集               │
 │                                      │
 │  ┌──────────── Bucket ────────────┐  │
 │  │ terms / date_histogram / range │  │  ← 分桶（GROUP BY）
 │  │                                │  │
 │  │  ┌──────── Metric ───────┐     │  │
 │  │  │ avg / sum / max       │     │  │  ← 桶内统计
 │  │  │ cardinality           │     │  │
 │  │  │ percentiles           │     │  │
 │  │  │ top_hits              │     │  │
 │  │  └───────────────────────┘     │  │
 │  └────────────────────────────────┘  │
 │                                      │
 │  ┌──────── Pipeline ────────────┐    │
 │  │ derivative / cumulative_sum  │    │  ← 对聚合结果再运算
 │  │ bucket_sort / bucket_selector│    │
 │  └──────────────────────────────┘    │
 └──────────────────────────────────────┘
```

---

## 5.3 嵌套聚合——多层分桶 + 统计

聚合的强大之处在于可以**无限嵌套**：Bucket 内嵌 Bucket，Bucket 内嵌 Metric，形成多维度分析。

### 典型嵌套：品牌 → 品类 → 平均价格

```
GET /products/_search
{
  "size": 0,
  "aggs": {
    "by_brand": {                              // 第 1 层：按品牌分桶
      "terms": { "field": "brand" },
      "aggs": {
        "by_category": {                       // 第 2 层：每个品牌内按品类分桶
          "terms": { "field": "category" },
          "aggs": {
            "avg_price": {                     // 第 3 层：每个品类内求平均价格
              "avg": { "field": "price" }
            }
          }
        }
      }
    }
  }
}
```

结果类似：

```
华为
  ├── 手机: avg_price=6999
  ├── 平板: avg_price=4999
  └── 耳机: avg_price=1499
Apple
  ├── 手机: avg_price=9999
  ├── 笔记本: avg_price=14999
  └── 平板: avg_price=4999
```

### 嵌套层数的性能影响

嵌套层数越多，桶的数量**指数级增长**。假设第 1 层 10 个桶，第 2 层 5 个桶，第 3 层 3 个桶 → 总共 10 × 5 × 3 = 150 个桶。每个桶都要做统计计算。

**经验原则**：嵌套不超过 3-4 层。如果需要更多维度分析，考虑使用 Composite 聚合（5.5 节）或在应用层拆分为多次查询。

### aggs 与 query 配合——先过滤再聚合

```
GET /products/_search
{
  "size": 0,
  "query": {                                    // ① 先用 query 过滤
    "bool": {
      "filter": [
        { "term": { "status": "active" } },
        { "range": { "price": { "gte": 3000 } } }
      ]
    }
  },
  "aggs": {                                     // ② 在过滤后的结果集上聚合
    "by_brand": {
      "terms": { "field": "brand" }
    }
  }
}
```

聚合默认在 query 匹配的文档集上执行。如果想**忽略 query 过滤，在全量数据上聚合**，用 `global` 聚合：

```
"aggs": {
  "all_brands": {
    "global": {},                               // 忽略 query，在全量数据上
    "aggs": {
      "by_brand": { "terms": { "field": "brand" } }
    }
  },
  "filtered_brands": {
    "terms": { "field": "brand" }               // 在 query 过滤后的数据上
  }
}
```

---

## 5.4 近似聚合——精确 vs 性能的取舍

### cardinality——近似去重计数

cardinality 聚合用 **HyperLogLog++（HLL++）** 算法估算字段的唯一值数量。

```
"aggs": {
  "unique_users": {
    "cardinality": {
      "field": "user_id",
      "precision_threshold": 3000     // 精度阈值
    }
  }
}
```

**为什么是"近似"？**

精确去重需要在内存中维护一个所有唯一值的集合。对于上亿条数据、几千万个唯一值，内存根本装不下。HLL++ 算法只需要**固定的极小内存**（几 KB）就能估算基数，代价是有一定误差。

**precision_threshold 参数：**

| precision_threshold | 内存消耗 | 精度 |
|-------------------|---------|------|
| 100 | ~1.6 KB | 唯一值 ≤ 100 时精确，>100 时误差 1-6% |
| 3000（默认） | ~48 KB | 唯一值 ≤ 3000 时精确，>3000 时误差 1-6% |
| 40000（最大） | ~640 KB | 唯一值 ≤ 40000 时精确，>40000 时误差 1-6% |

**precision_threshold 越大越精确，但内存消耗越大**。对于 UV 统计这种量级大的场景，3000 的默认值通常够用（误差 1-6% 在业务上可以接受）。

> **面试怎么答**："怎么对上亿数据做去重统计？"
>
> 使用 cardinality 聚合，底层是 HyperLogLog++ 算法。HLL++ 只需要极小的固定内存（几十 KB）就能估算几千万级别的唯一值数量，精度通过 precision_threshold 参数控制。唯一值在阈值以内时精确，超过时误差约为 1-6%。这是百亿级数据去重的唯一可行方案——精确去重需要把所有唯一值载入内存，不现实。

### percentiles——近似百分位数

percentiles 聚合用 **T-Digest** 算法估算百分位数。

```
"aggs": {
  "latency_percentiles": {
    "percentiles": {
      "field": "response_time",
      "percents": [50, 90, 95, 99, 99.9]
    }
  }
}
# 结果：P50=120ms, P90=350ms, P95=500ms, P99=1200ms, P99.9=3000ms
```

**T-Digest 的巧妙之处**：极端百分位（P1、P99、P99.9）的精度反而更高——因为 T-Digest 在分布的尾部保留了更多的数据点。这恰好符合实际需求：我们通常最关心 P99（最差的 1% 请求的延迟）。

**典型应用场景**：接口延迟分析、SLA 监控（"P99 延迟 < 500ms"）。

### percentile_ranks——反向百分位

```
# "延迟 < 200ms 的请求占比是多少？"
"aggs": {
  "fast_requests": {
    "percentile_ranks": {
      "field": "response_time",
      "values": [200, 500, 1000]
    }
  }
}
# 结果：<200ms 占 65%, <500ms 占 92%, <1000ms 占 98%
```

---

## 5.5 大数据量聚合方案

### terms 聚合不精确的问题

**这是面试高频考点。** 当数据分布在多个 shard 上时，terms 聚合的结果可能不精确。

```
问题场景：统计全网 Top 5 品牌

Shard 0 的 Top 5：          Shard 1 的 Top 5：
  华为: 500                   Apple: 600
  Apple: 450                  华为: 400
  小米: 300                   三星: 350
  三星: 200                   OPPO: 300
  OPPO: 150                   小米: 250

协调节点合并两个 Shard 的 Top 5：
  Apple: 450+600 = 1050
  华为: 500+400 = 900
  小米: 300+250 = 550
  三星: 200+350 = 550
  OPPO: 150+300 = 450

⚠️ 问题：Shard 0 的 Top 5 里没有 vivo（排第 6），
但 vivo 在 Shard 1 排第 6 有 240 条。
真实的全局 vivo 数量可能是 160+240=400，超过了 OPPO 的 450 吗？
不确定——因为 Shard 0 根本没返回 vivo 的数据！
```

**根本原因**：每个 shard 只返回自己的 Top N，协调节点在合并时可能遗漏全局排名靠前但在某个 shard 上不在 Top N 的值。

### 解决方案

**方案 1：shard_size 参数**

让每个 shard 多返回一些桶，减少遗漏概率：

```
"aggs": {
  "brands": {
    "terms": {
      "field": "brand",
      "size": 10,
      "shard_size": 30      // 每个 shard 返回 Top 30，协调节点合并后取 Top 10
    }
  }
}
```

默认 `shard_size = size × 1.5 + 10`。增大 shard_size 可以提高精度，但消耗更多内存和网络带宽。

**方案 2：单 shard 或 routing**

如果数据通过 routing 确保同一维度的数据落在同一 shard 上（比如按品牌 routing），terms 聚合就是精确的。

**方案 3：show_term_doc_count_error**

```
"aggs": {
  "brands": {
    "terms": {
      "field": "brand",
      "size": 10,
      "show_term_doc_count_error": true    // 显示每个桶的误差范围
    }
  }
}
```

返回结果中会包含 `doc_count_error_upper_bound`（最大可能的误差）和每个桶的 `doc_count_error`，帮你判断结果的可靠性。

### Composite Aggregation——聚合结果分页

当你需要对高基数字段（如几十万个用户 ID）做 terms 聚合时，`size=100000` 会消耗大量内存。Composite 聚合提供了**分页能力**：

```
# 第一页
GET /products/_search
{
  "size": 0,
  "aggs": {
    "all_brands": {
      "composite": {
        "size": 100,                    // 每页 100 个桶
        "sources": [
          { "brand": { "terms": { "field": "brand" } } },
          { "category": { "terms": { "field": "category" } } }
        ]
      }
    }
  }
}

# 返回结果包含 after_key
# 第二页——用 after_key 翻页
GET /products/_search
{
  "size": 0,
  "aggs": {
    "all_brands": {
      "composite": {
        "size": 100,
        "sources": [
          { "brand": { "terms": { "field": "brand" } } },
          { "category": { "terms": { "field": "category" } } }
        ],
        "after": { "brand": "小米", "category": "手机" }    // 上一页的 after_key
      }
    }
  }
}
```

Composite 的优势：
- 不需要一次性把所有桶加载到内存——分页获取
- 支持多维度组合（同时按品牌+品类分桶）
- 遍历所有桶（不限于 Top N）

### Sampler Aggregation——采样聚合

对高基数或大数据量场景，先采样一部分文档再聚合，减少计算量：

```
"aggs": {
  "sample": {
    "sampler": {
      "shard_size": 1000         // 每个 shard 只取 Top 1000 条相关文档
    },
    "aggs": {
      "top_tags": { "terms": { "field": "tags" } }
    }
  }
}
```

适合"探索性分析"——不需要完全精确，只要看个趋势。

---

## 面试高频题与参考答案

### Q1：terms 聚合结果为什么不精确？怎么解决？

**答**：当数据分布在多个 shard 上时，terms 聚合的每个 shard 只返回自己的 Top N 到协调节点，协调节点合并时可能遗漏某些全局排名靠前但在某个 shard 上不在 Top N 的值。

解决方案有三个层次：第一，增大 shard_size 参数（默认 size×1.5+10），让每个 shard 多返回一些桶减少遗漏概率，这是最简单的；第二，通过 routing 确保同一维度的数据落在同一个 shard 上，这样单 shard 上的 terms 聚合是精确的；第三，使用单 shard 索引（适合数据量不大的场景）。还可以设置 `show_term_doc_count_error: true` 来评估误差范围。

### Q2：怎么对上亿数据做去重统计？HyperLogLog 原理？

**答**：使用 cardinality 聚合，底层是 HyperLogLog++ 算法。精确去重需要在内存中维护所有唯一值的集合，对于上亿条数据不现实。HLL++ 通过对值做哈希后统计二进制表示中前导零的数量来估算基数，只需要几十 KB 的固定内存就能估算几千万级别的唯一值数量。

精度通过 precision_threshold 参数控制：唯一值数量在阈值以内时精确，超过后误差约 1-6%。默认值 3000 对大多数场景够用。如果业务能接受小范围误差（如 UV 统计），cardinality 是唯一可行的方案。

### Q3：doc_values 是什么？为什么聚合和排序离不开它？

**答**：Doc Values 是 ES 在写入时自动为 keyword、数值、日期等字段构建的列式存储结构。倒排索引的方向是 Term → Document List，适合搜索；聚合和排序需要的是反方向——Document → Field Value，需要按文档遍历字段值。Doc Values 正是这个方向的存储，以列式结构存在磁盘上，非常适合高效遍历和统计。

keyword、数值、日期、布尔等类型自动启用 Doc Values。text 字段没有 Doc Values，要聚合要么用 .keyword 子字段（推荐），要么开启 Fielddata（不推荐——内存构建且聚合的是分词后的 Term，不是原始值，容易 OOM）。

### Q4：text 字段能做聚合吗？为什么不推荐？

**答**：技术上可以，通过开启 Fielddata 参数让 text 字段在内存中构建 Doc Values。但强烈不推荐，原因有二：

第一，内存消耗巨大。Fielddata 在堆内存中构建，高基数的 text 字段会消耗大量内存，很容易导致 OOM。而普通的 Doc Values 存储在磁盘上，通过 OS Page Cache 按需加载，内存压力小得多。

第二，聚合结果没有意义。text 字段被分词了，"华为 Mate 60" 分成 "华为"、"mate"、"60" 三个 Term，聚合会生成三个桶而不是一个。正确做法是用 .keyword 子字段做聚合，得到的才是完整的原始值。

### Q5：聚合时内存不够怎么办？

**答**：几个方向：

第一，减少桶数量——降低 terms 聚合的 size、减少嵌套层数、用 Composite 聚合分页获取。第二，用近似聚合——cardinality 替代精确去重、percentiles 替代精确百分位。第三，用 Sampler 聚合——只对采样数据做聚合。第四，使用 filter 在聚合前缩小数据范围。第五，检查是否有 text 字段开启了 Fielddata——如果有，改用 .keyword 子字段并关闭 Fielddata。最后，调整 `indices.fielddata.cache.size` 限制 Fielddata 缓存大小，防止 OOM。

---

## 动手实践

### 练习 1：多层嵌套聚合 + bucket_sort

```
# 使用阶段 4 的测试数据，或重新创建：
PUT /agg_practice
{
  "settings": { "number_of_shards": 1, "number_of_replicas": 0 },
  "mappings": {
    "properties": {
      "name": { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
      "brand": { "type": "keyword" },
      "category": { "type": "keyword" },
      "price": { "type": "float" },
      "sales_count": { "type": "integer" },
      "tags": { "type": "keyword" },
      "status": { "type": "keyword" },
      "created_at": { "type": "date" }
    }
  }
}

POST /_bulk
{"index": {"_index": "agg_practice", "_id": "1"}}
{"name": "华为 Mate 60 Pro", "brand": "华为", "category": "手机", "price": 6999, "sales_count": 50000, "tags": ["5G", "旗舰"], "status": "active", "created_at": "2024-03-15"}
{"index": {"_index": "agg_practice", "_id": "2"}}
{"name": "iPhone 15 Pro Max", "brand": "Apple", "category": "手机", "price": 9999, "sales_count": 80000, "tags": ["5G", "旗舰"], "status": "active", "created_at": "2024-03-20"}
{"index": {"_index": "agg_practice", "_id": "3"}}
{"name": "小米 14 Ultra", "brand": "小米", "category": "手机", "price": 5999, "sales_count": 30000, "tags": ["5G", "影像"], "status": "active", "created_at": "2024-02-01"}
{"index": {"_index": "agg_practice", "_id": "4"}}
{"name": "华为 MatePad Pro", "brand": "华为", "category": "平板", "price": 4999, "sales_count": 15000, "tags": ["办公"], "status": "active", "created_at": "2024-01-10"}
{"index": {"_index": "agg_practice", "_id": "5"}}
{"name": "MacBook Pro 14", "brand": "Apple", "category": "笔记本", "price": 14999, "sales_count": 25000, "tags": ["专业"], "status": "active", "created_at": "2024-01-05"}
{"index": {"_index": "agg_practice", "_id": "6"}}
{"name": "华为 FreeBuds Pro 3", "brand": "华为", "category": "耳机", "price": 1499, "sales_count": 40000, "tags": ["降噪"], "status": "active", "created_at": "2024-04-01"}
{"index": {"_index": "agg_practice", "_id": "7"}}
{"name": "Redmi Note 13", "brand": "小米", "category": "手机", "price": 1299, "sales_count": 100000, "tags": ["5G", "性价比"], "status": "active", "created_at": "2024-03-01"}
{"index": {"_index": "agg_practice", "_id": "8"}}
{"name": "三星 Galaxy S24 Ultra", "brand": "三星", "category": "手机", "price": 9699, "sales_count": 20000, "tags": ["5G", "AI"], "status": "inactive", "created_at": "2024-02-15"}
{"index": {"_index": "agg_practice", "_id": "9"}}
{"name": "OPPO Find X7", "brand": "OPPO", "category": "手机", "price": 4999, "sales_count": 18000, "tags": ["5G", "影像"], "status": "active", "created_at": "2024-01-20"}
{"index": {"_index": "agg_practice", "_id": "10"}}
{"name": "iPad Air", "brand": "Apple", "category": "平板", "price": 4999, "sales_count": 35000, "tags": ["轻薄"], "status": "active", "created_at": "2024-03-25"}

# 1. 按品牌分桶 → 每个品牌的平均价格 → 按平均价格降序排
GET /agg_practice/_search
{
  "size": 0,
  "aggs": {
    "by_brand": {
      "terms": { "field": "brand", "size": 10 },
      "aggs": {
        "avg_price": { "avg": { "field": "price" } },
        "sort_by_price": {
          "bucket_sort": {
            "sort": [{ "avg_price": { "order": "desc" } }]
          }
        }
      }
    }
  }
}

# 2. 两层嵌套：品牌 → 品类 → 平均价格
GET /agg_practice/_search
{
  "size": 0,
  "aggs": {
    "by_brand": {
      "terms": { "field": "brand" },
      "aggs": {
        "by_category": {
          "terms": { "field": "category" },
          "aggs": {
            "avg_price": { "avg": { "field": "price" } },
            "total_sales": { "sum": { "field": "sales_count" } }
          }
        }
      }
    }
  }
}

# 3. 配合 query 过滤——只聚合 active 状态的手机
GET /agg_practice/_search
{
  "size": 0,
  "query": {
    "bool": {
      "filter": [
        { "term": { "status": "active" } },
        { "term": { "category": "手机" } }
      ]
    }
  },
  "aggs": {
    "by_brand": {
      "terms": { "field": "brand" },
      "aggs": {
        "avg_price": { "avg": { "field": "price" } },
        "top_product": {
          "top_hits": {
            "size": 1,
            "sort": [{ "sales_count": "desc" }],
            "_source": ["name", "sales_count"]
          }
        }
      }
    }
  }
}
```

### 练习 2：date_histogram + Pipeline 求环比

```
# 按月统计上架数量 + 环比变化
GET /agg_practice/_search
{
  "size": 0,
  "aggs": {
    "monthly": {
      "date_histogram": {
        "field": "created_at",
        "calendar_interval": "month",
        "format": "yyyy-MM",
        "min_doc_count": 0
      },
      "aggs": {
        "monthly_count": { "value_count": { "field": "brand" } },
        "total_sales": { "sum": { "field": "sales_count" } },
        "count_change": {
          "derivative": { "buckets_path": "monthly_count" }
        },
        "running_sales": {
          "cumulative_sum": { "buckets_path": "total_sales" }
        }
      }
    }
  }
}
# 观察：每月上架数 + 环比变化 + 累计销量
```

### 练习 3：cardinality + 价格分布

```
# 1. 去重统计品牌数量
GET /agg_practice/_search
{
  "size": 0,
  "aggs": {
    "unique_brands": {
      "cardinality": {
        "field": "brand",
        "precision_threshold": 100
      }
    }
  }
}

# 2. 价格区间分布
GET /agg_practice/_search
{
  "size": 0,
  "aggs": {
    "price_ranges": {
      "range": {
        "field": "price",
        "ranges": [
          { "key": "低端(0-3000)", "to": 3000 },
          { "key": "中端(3000-7000)", "from": 3000, "to": 7000 },
          { "key": "高端(7000+)", "from": 7000 }
        ]
      },
      "aggs": {
        "avg_sales": { "avg": { "field": "sales_count" } }
      }
    }
  }
}

# 3. 价格百分位数
GET /agg_practice/_search
{
  "size": 0,
  "aggs": {
    "price_percentiles": {
      "percentiles": {
        "field": "price",
        "percents": [25, 50, 75, 90, 99]
      }
    }
  }
}

# 4. 清理
DELETE /agg_practice
```

---

## 本阶段总结

学完本阶段，你应该掌握了以下心智模型：

```
聚合的基础：Doc Values
  keyword / 数值 / 日期 → 自动有 Doc Values → 可聚合排序
  text → 没有 Doc Values → 用 .keyword 子字段聚合
  永远不要开 Fielddata

三大聚合类型：
  Bucket（分桶）：terms / date_histogram / histogram / range / filters / composite
  Metric（统计）：avg / sum / min / max / stats / cardinality / percentiles / top_hits
  Pipeline（再运算）：derivative / cumulative_sum / bucket_sort / bucket_selector

嵌套聚合：
  Bucket 内嵌 Bucket + Metric → 多维度分析
  配合 query.filter 先过滤再聚合
  嵌套不超过 3-4 层

近似聚合：
  cardinality（HLL++）→ 大数据去重，误差 1-6%
  percentiles（T-Digest）→ 百分位数，极端值精度更高

大数据量聚合：
  terms 不精确 → 增大 shard_size 或用 routing
  高基数分页 → Composite Aggregation
  探索性分析 → Sampler Aggregation
```

**至此，ES "会用"层五个阶段全部完成！**

```
阶段 1  核心概念（倒排索引、文档、集群）
阶段 2  Mapping（字段类型、索引设计模式）
阶段 3  分词（Analyzer 架构、IK、search_analyzer）
阶段 4  Query DSL（match/term/bool、BM25、深度分页、高亮）
阶段 5  聚合（Bucket/Metric/Pipeline、近似聚合、Composite）
  ↓
  你现在可以独立完成 ES 的所有日常使用操作了
  ↓
  接下来进入"懂原理"层——理解 WHY，而不只是 HOW
```

**下一阶段**：阶段 6 存储原理与读写链路——你已经学会了所有"怎么用"，现在来理解"为什么这样设计"。为什么搜索是近实时的？为什么更新实际上是删除+新增？refresh、flush、translog、Segment merge 这些底层机制，将在阶段 6 全部串联起来。带着使用经验看原理，理解会深得多。
