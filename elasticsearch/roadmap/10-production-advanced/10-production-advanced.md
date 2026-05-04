# 阶段 10：生产运维与高级特性（1 周）

> **目标**：掌握 ES 在生产环境中的运维能力和高级搜索特性。学完本阶段后，你应该能配置 ILM 管理索引生命周期、做快照备份恢复、实现搜索自动补全（Completion Suggester）、使用向量搜索做语义搜索，以及搭建完整的 ELK 日志架构。
>
> **本阶段定位**：阶段 1-9 构建了从"会用"到"能落地"的完整知识体系。本阶段是**锦上添花**——补充生产运维和高级搜索特性，让你的 ES 知识更加完整。
>
> **阅读建议**：本阶段内容较广，每个子节相对独立。可以根据面试需求或项目需求选择性深入。

---

## 10.1 索引生命周期管理（ILM）

### 为什么需要 ILM？

日志、监控指标等时间序列数据有一个特点：**越新的数据越有价值，越旧的数据越不需要高性能**。

```
不用 ILM 的问题：
  所有日志都在高性能 SSD 上 → 存储成本爆炸
  手动删除过期索引 → 容易遗忘，磁盘被撑满

用 ILM 的方案：
  Hot（最近 7 天）  → SSD，高性能，频繁读写
  Warm（8-30 天）   → HDD，只读，偶尔查
  Cold（31-90 天）  → 大容量 HDD，极少查
  Delete（>90 天）  → 自动删除
```

### Hot-Warm-Cold-Delete 架构

```
  写入              查询频率递减
   │                ──────────→
   ▼
┌──────┐  7天后  ┌──────┐  30天后  ┌──────┐  90天后  ┌──────────┐
│ Hot  │ ──────→ │ Warm │ ──────→ │ Cold │ ──────→ │ Delete   │
│(SSD) │         │(HDD) │         │(大HDD)│         │(自动删除) │
│读+写 │         │只读   │         │极少查 │         │          │
└──────┘         └──────┘         └──────┘         └──────────┘
```

### 配置 ILM Policy

```json
// 1. 创建 ILM 策略
PUT /_ilm/policy/logs_policy
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_primary_shard_size": "50gb",    // 单分片超 50GB 触发滚动
            "max_age": "7d"                      // 或超过 7 天
          },
          "set_priority": { "priority": 100 }    // 高优先级恢复
        }
      },
      "warm": {
        "min_age": "7d",
        "actions": {
          "shrink": { "number_of_shards": 1 },   // 收缩分片数
          "forcemerge": { "max_num_segments": 1 },// 合并 Segment
          "allocate": {
            "require": { "data": "warm" }         // 迁移到 warm 节点
          },
          "set_priority": { "priority": 50 }
        }
      },
      "cold": {
        "min_age": "30d",
        "actions": {
          "allocate": {
            "require": { "data": "cold" }
          },
          "set_priority": { "priority": 0 }
        }
      },
      "delete": {
        "min_age": "90d",
        "actions": {
          "delete": {}                            // 自动删除
        }
      }
    }
  }
}
```

### Data Stream（ES 7.9+）

Data Stream 是 ES 对时间序列数据的原生支持——自动管理背后的滚动索引。

```json
// 2. 创建 Index Template 绑定 ILM 策略
PUT /_index_template/logs_template
{
  "index_patterns": ["logs-*"],
  "data_stream": {},
  "template": {
    "settings": {
      "index.lifecycle.name": "logs_policy",
      "number_of_shards": 1,
      "number_of_replicas": 1
    },
    "mappings": {
      "properties": {
        "@timestamp": { "type": "date" },
        "message": { "type": "text" },
        "level": { "type": "keyword" },
        "service": { "type": "keyword" }
      }
    }
  }
}

// 3. 写入数据（自动创建 Data Stream）
POST /logs-app/_doc
{
  "@timestamp": "2024-03-15T10:30:00Z",
  "message": "User login successful",
  "level": "INFO",
  "service": "auth-service"
}

// 4. 查看 Data Stream 状态
GET /_data_stream/logs-app
```

---

## 10.2 快照与恢复

### 快照仓库配置

```json
// 注册一个文件系统仓库
PUT /_snapshot/my_backup
{
  "type": "fs",
  "settings": {
    "location": "/mount/backups/es"    // 需要在 elasticsearch.yml 中配置 path.repo
  }
}

// 或使用 S3
PUT /_snapshot/s3_backup
{
  "type": "s3",
  "settings": {
    "bucket": "my-es-backups",
    "region": "us-east-1"
  }
}
```

### 快照操作

```
# 创建全量快照（首次）
PUT /_snapshot/my_backup/snapshot_1?wait_for_completion=true
{
  "indices": "products,logs-*",                  // 指定索引（留空=全部）
  "ignore_unavailable": true
}

# 创建增量快照（后续——只备份变更的 Segment）
PUT /_snapshot/my_backup/snapshot_2?wait_for_completion=true

# 查看快照状态
GET /_snapshot/my_backup/snapshot_1

# 恢复快照
POST /_snapshot/my_backup/snapshot_1/_restore
{
  "indices": "products",                         // 恢复指定索引
  "rename_pattern": "(.+)",                      // 重命名
  "rename_replacement": "restored_$1"            // 恢复为 restored_products
}

# 删除快照
DELETE /_snapshot/my_backup/snapshot_1
```

### SLM（Snapshot Lifecycle Management）

```json
// 自动化快照——每天凌晨 1 点自动备份
PUT /_slm/policy/daily_backup
{
  "schedule": "0 0 1 * * ?",
  "name": "<daily-snap-{now/d}>",
  "repository": "my_backup",
  "config": {
    "indices": ["*"],
    "ignore_unavailable": true
  },
  "retention": {
    "expire_after": "30d",                       // 30 天后自动清理旧快照
    "min_count": 5,
    "max_count": 50
  }
}
```

---

## 10.3 安全

ES 8.x 默认开启安全（开箱即用的 TLS 加密 + 用户认证）。

### 核心安全配置

```yaml
# elasticsearch.yml（ES 8.x 默认已开启）
xpack.security.enabled: true
xpack.security.transport.ssl.enabled: true        # 节点间通信加密
xpack.security.http.ssl.enabled: true             # HTTP 接口加密
```

### 内置用户和角色

```
# 重置内置用户密码
bin/elasticsearch-reset-password -u elastic

# 创建自定义角色
POST /_security/role/read_only_products
{
  "cluster": [],
  "indices": [
    {
      "names": ["products"],
      "privileges": ["read"]          // 只读权限
    }
  ]
}

# 创建用户
POST /_security/user/search_user
{
  "password": "secure_password",
  "roles": ["read_only_products"]
}
```

### API Key

```
# 创建 API Key（适合应用程序使用）
POST /_security/api_key
{
  "name": "search-service-key",
  "role_descriptors": {
    "search_role": {
      "cluster": [],
      "index": [
        { "names": ["products"], "privileges": ["read"] }
      ]
    }
  },
  "expiration": "30d"
}
```

---

## 10.4 高级搜索特性

### Completion Suggester——搜索自动补全

搜索框输入时实时给出补全建议。基于 FST（Finite State Transducer），**全部数据加载到内存**，前缀查找极快。

```json
// 1. Mapping 中定义 completion 类型
PUT /suggest_test
{
  "mappings": {
    "properties": {
      "name": { "type": "text" },
      "suggest": {
        "type": "completion",                  // completion 类型
        "analyzer": "simple"
      }
    }
  }
}

// 2. 写入数据（带补全建议）
PUT /suggest_test/_doc/1
{
  "name": "华为 Mate 60 Pro",
  "suggest": {
    "input": ["华为 Mate 60 Pro", "华为手机", "Mate 60"],  // 多个补全候选
    "weight": 10                                            // 权重（影响排序）
  }
}

PUT /suggest_test/_doc/2
{
  "name": "华为 MatePad Pro",
  "suggest": {
    "input": ["华为 MatePad Pro", "华为平板", "MatePad"],
    "weight": 5
  }
}

// 3. 搜索建议
POST /suggest_test/_search
{
  "suggest": {
    "product_suggest": {
      "prefix": "华为 Ma",                     // 用户输入的前缀
      "completion": {
        "field": "suggest",
        "size": 5,
        "skip_duplicates": true
      }
    }
  }
}

// 返回：华为 Mate 60 Pro, 华为 MatePad Pro（按 weight 排序）
```

> **面试怎么答**："搜索框自动补全怎么实现？"
>
> 使用 Completion Suggester。Mapping 中定义 completion 类型的字段，写入时指定补全候选词和权重。底层基于 FST 数据结构，全部加载到内存中，前缀查找时间复杂度 O(len(prefix))，响应时间通常在 1-5 毫秒，非常适合搜索框联想。相比 match_phrase_prefix（需要到倒排索引中查找），Completion Suggester 性能好一个数量级。

### Context Suggester——带上下文的补全

```json
// 根据品类上下文给出不同的补全建议
"suggest": {
  "type": "completion",
  "contexts": [
    { "name": "category", "type": "category" }
  ]
}
```

### Geo 查询——地理位置搜索

```json
// 1. Mapping
"location": { "type": "geo_point" }

// 2. 写入
PUT /shops/_doc/1
{ "name": "星巴克回龙观店", "location": { "lat": 40.07, "lon": 116.33 } }

// 3. 距离查询——找附近 5km 内的店
GET /shops/_search
{
  "query": {
    "geo_distance": {
      "distance": "5km",
      "location": { "lat": 40.08, "lon": 116.34 }
    }
  },
  "sort": [
    {
      "_geo_distance": {
        "location": { "lat": 40.08, "lon": 116.34 },
        "order": "asc",
        "unit": "km"
      }
    }
  ]
}
```

### Field Collapsing——字段折叠

类似 SQL 的 `GROUP BY + 取每组 Top 1`——在搜索结果中按某个字段去重。

```json
// 搜索手机，每个品牌只显示一个最相关的结果
GET /products/_search
{
  "query": { "match": { "name": "手机" } },
  "collapse": {
    "field": "brand",
    "inner_hits": {
      "name": "all_products",
      "size": 3,                              // 展开后显示每个品牌 Top 3
      "sort": [{ "price": "asc" }]
    }
  }
}
```

### Runtime Fields——查询时动态字段

不需要 Reindex 就能在查询时动态计算字段。

```json
GET /products/_search
{
  "runtime_mappings": {
    "price_with_tax": {
      "type": "double",
      "script": "emit(doc['price'].value * 1.13)"    // 价格 × 1.13 税率
    }
  },
  "query": {
    "range": { "price_with_tax": { "gte": 5000 } }   // 可以在查询中使用
  },
  "fields": ["name", "price", "price_with_tax"]       // 可以返回
}
```

适用场景：临时性计算字段、数据探索、避免 Reindex。但性能比预计算字段差（每次查询都要计算）。

### Percolator——反向搜索

普通搜索是"用查询找文档"。Percolator 是"用文档找查询"——当新文档匹配预先注册的某个查询时触发通知。

```json
// 1. 注册查询（"当有华为旗舰手机上架时通知我"）
PUT /alerts/_doc/1
{
  "query": {
    "bool": {
      "must": [
        { "match": { "name": "华为" } },
        { "term": { "tags": "旗舰" } }
      ]
    }
  }
}

// 2. 新文档到达时，检查匹配哪些预注册的查询
GET /alerts/_search
{
  "query": {
    "percolate": {
      "field": "query",
      "document": {
        "name": "华为 Mate 70 Pro",
        "tags": ["5G", "旗舰"]
      }
    }
  }
}
// 返回：匹配了 alert id=1 → 触发通知
```

适用场景：价格监控告警、关键词订阅、规则引擎。

---

## 10.5 数据处理

### Ingest Pipeline——写入前数据预处理

在文档写入索引**之前**，在 Ingest Node 上执行一系列处理器（Processor）对文档进行转换。

```json
// 1. 定义 Pipeline
PUT /_ingest/pipeline/log_pipeline
{
  "description": "日志预处理",
  "processors": [
    {
      "grok": {                                    // 用正则解析非结构化日志
        "field": "message",
        "patterns": ["%{IP:client_ip} - %{WORD:method} %{URIPATHPARAM:request}"]
      }
    },
    {
      "date": {                                    // 解析日期字段
        "field": "timestamp_str",
        "formats": ["yyyy-MM-dd HH:mm:ss"],
        "target_field": "@timestamp"
      }
    },
    {
      "geoip": {                                   // IP 转地理位置
        "field": "client_ip"
      }
    },
    {
      "remove": {                                  // 删除临时字段
        "field": "timestamp_str"
      }
    }
  ]
}

// 2. 写入时指定 Pipeline
PUT /logs/_doc/1?pipeline=log_pipeline
{
  "message": "192.168.1.1 - GET /api/products",
  "timestamp_str": "2024-03-15 10:30:00"
}
```

### 常用 Processor

| Processor | 作用 |
|-----------|------|
| `grok` | 用正则模式解析非结构化文本 |
| `date` | 解析日期字符串 |
| `geoip` | IP → 地理位置/经纬度 |
| `user_agent` | 解析 User-Agent → 浏览器/OS |
| `set` | 设置字段值 |
| `remove` | 删除字段 |
| `rename` | 重命名字段 |
| `lowercase` / `uppercase` | 大小写转换 |
| `script` | Painless 脚本自定义处理 |
| `enrich` | 关联外部数据（查找表） |

---

## 10.6 ELK/EFK 生态

### 典型日志架构

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌──────┐    ┌────────┐
│ App 1   │→   │         │    │         │    │      │    │        │
│ App 2   │→   │Filebeat │ →  │  Kafka  │ →  │Logstash│ → │   ES   │ → Kibana
│ App 3   │→   │(采集)    │    │(缓冲)   │    │(转换) │    │(存储)  │   (可视化)
└─────────┘    └─────────┘    └─────────┘    └──────┘    └────────┘
```

### 为什么中间加 Kafka？

```
不加 Kafka：
  Filebeat → Logstash → ES
  问题：突发流量（如大促/故障导致日志暴涨）直接打到 Logstash/ES → 写入压力过大 → 数据丢失

加 Kafka：
  Filebeat → Kafka → Logstash → ES
  好处：
  1. 削峰填谷：突发流量先堆积在 Kafka，Logstash 按自己的速度消费
  2. 解耦：Filebeat 和 Logstash/ES 相互不影响
  3. 持久化：Kafka 消息持久化，ES 宕机恢复后可以重新消费
  4. 多消费者：同一份日志可以同时给 ES（搜索）+ 实时告警 + 大数据平台
```

### Beats 家族

| Beat | 用途 |
|------|------|
| **Filebeat** | 采集日志文件（最常用） |
| **Metricbeat** | 采集系统/服务指标（CPU、内存、磁盘） |
| **Packetbeat** | 网络数据包分析 |
| **Heartbeat** | 服务可用性监控（ping/HTTP check） |
| **Auditbeat** | 审计事件（文件变更、用户登录） |

### Filebeat 配置示例

```yaml
# filebeat.yml
filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - /var/log/app/*.log
    multiline:
      pattern: '^\d{4}-\d{2}-\d{2}'
      negate: true
      match: after

output.kafka:
  hosts: ["kafka:9092"]
  topic: "app-logs"
```

---

## 10.7 ES 8.x 新特性——向量搜索

### KNN 向量搜索

ES 8.x 原生支持 dense_vector 字段和 KNN（K-Nearest Neighbors）查询，可以做**语义搜索**。

```json
// 1. Mapping——定义向量字段
PUT /semantic_search
{
  "mappings": {
    "properties": {
      "title": { "type": "text" },
      "title_vector": {
        "type": "dense_vector",
        "dims": 768,                             // 向量维度（如 BERT 768 维）
        "index": true,                           // 建立 HNSW 索引
        "similarity": "cosine"                   // 余弦相似度
      }
    }
  }
}

// 2. 写入（向量由外部模型生成）
PUT /semantic_search/_doc/1
{
  "title": "如何学习 Elasticsearch",
  "title_vector": [0.12, -0.34, 0.56, ...]       // 768 维向量
}

// 3. KNN 查询——用向量找最近邻
GET /semantic_search/_search
{
  "knn": {
    "field": "title_vector",
    "query_vector": [0.11, -0.33, 0.55, ...],    // 查询向量
    "k": 10,                                      // 返回最近的 10 个
    "num_candidates": 100                          // HNSW 搜索的候选数
  }
}
```

### 混合搜索（Hybrid Search）

结合传统 BM25 文本搜索 + 向量语义搜索：

```json
GET /semantic_search/_search
{
  "query": {
    "match": { "title": "ES 学习" }               // BM25 关键词搜索
  },
  "knn": {
    "field": "title_vector",
    "query_vector": [0.11, -0.33, 0.55, ...],     // 语义搜索
    "k": 10,
    "num_candidates": 100
  }
}
// ES 会自动融合 BM25 分数和 KNN 分数
```

> **面试怎么答**："ES 支持向量搜索吗？怎么做语义搜索？"
>
> ES 8.x 原生支持向量搜索。使用 dense_vector 字段类型存储文档向量（由外部 Embedding 模型如 BERT 生成），底层使用 HNSW（Hierarchical Navigable Small World）图索引做近似最近邻搜索。查询时传入查询文本的向量，ES 返回向量空间中最近的 K 个文档。还支持混合搜索——同时做 BM25 关键词搜索和 KNN 向量搜索，自动融合两种分数，兼顾关键词精确匹配和语义理解。

---

## 面试高频题与参考答案

### Q1：日志数据怎么管理生命周期？Hot-Warm-Cold 怎么配？

**答**：使用 ILM（Index Lifecycle Management）配置 Hot-Warm-Cold-Delete 四个阶段。Hot 阶段在 SSD 节点上处理写入和频繁查询，设置 rollover 条件（如单分片超 50GB 或超 7 天）自动滚动。Warm 阶段迁移到 HDD 节点，索引设为只读并做 force merge 和 shrink。Cold 阶段迁移到大容量节点，极少查询。Delete 阶段超过保留期自动删除。

配合 Data Stream 和 Index Template 使用：Template 绑定 ILM 策略，Data Stream 自动管理滚动索引，写入时只需指定 Data Stream 名称。

### Q2：搜索框自动补全怎么实现？

**答**：（见 10.4 Completion Suggester 节面试回答）

### Q3：如何用 ES 做日志系统？架构是什么？中间为什么加 Kafka？

**答**：典型架构是 Filebeat → Kafka → Logstash → ES → Kibana。Filebeat 部署在应用服务器上采集日志文件，发送到 Kafka。Logstash 从 Kafka 消费日志，做解析转换（grok 正则解析、date 日期解析、geoip 地理位置解析），写入 ES。Kibana 做可视化和告警。

加 Kafka 有三个原因：第一，削峰填谷——突发流量先堆积在 Kafka 不会打爆 ES；第二，解耦——Filebeat 和 ES 相互不影响，ES 宕机时日志不丢失；第三，支持多消费者——同一份日志可以同时给 ES 搜索、实时告警系统、大数据平台分别消费。

### Q4：ES 支持向量搜索吗？怎么做语义搜索？

**答**：（见 10.7 节面试回答）

### Q5：你们生产环境的 ES 集群是怎么部署的？

**答**：（结合阶段 7 和本阶段回答）

典型部署：3 个专用 Master 节点（8G 内存，管理集群状态）+ N 个 Data 节点（32-64G 内存，SSD 磁盘，分 Hot/Warm/Cold 层）+ 2 个 Coordinating 节点（接收请求，汇总结果）。安全层面配置 TLS 加密和用户认证。运维层面配置 ILM 管理索引生命周期、SLM 自动化快照备份、慢查询日志和监控告警。日志数据按天分索引配合 Data Stream，搜索数据用固定索引配合 Alias。

---

## 动手实践

### 练习 1：ILM + Data Stream

```
# 1. 创建 ILM 策略
PUT /_ilm/policy/practice_ilm
{
  "policy": {
    "phases": {
      "hot": {
        "actions": {
          "rollover": { "max_primary_shard_size": "1gb", "max_age": "1d" }
        }
      },
      "delete": {
        "min_age": "7d",
        "actions": { "delete": {} }
      }
    }
  }
}

# 2. 创建 Index Template
PUT /_index_template/practice_template
{
  "index_patterns": ["practice-logs-*"],
  "data_stream": {},
  "template": {
    "settings": {
      "index.lifecycle.name": "practice_ilm",
      "number_of_shards": 1,
      "number_of_replicas": 0
    },
    "mappings": {
      "properties": {
        "@timestamp": { "type": "date" },
        "message": { "type": "text" },
        "level": { "type": "keyword" }
      }
    }
  }
}

# 3. 写入数据
POST /practice-logs-app/_doc
{
  "@timestamp": "2024-03-15T10:30:00Z",
  "message": "Application started",
  "level": "INFO"
}

# 4. 查看 Data Stream 和 ILM 状态
GET /_data_stream/practice-logs-app
GET /practice-logs-app/_ilm/explain

# 5. 清理
DELETE /_data_stream/practice-logs-app
DELETE /_index_template/practice_template
DELETE /_ilm/policy/practice_ilm
```

### 练习 2：Completion Suggester

```
# 1. 创建索引
PUT /suggest_practice
{
  "mappings": {
    "properties": {
      "name": { "type": "text" },
      "suggest": { "type": "completion" }
    }
  }
}

# 2. 写入数据
POST /_bulk
{"index": {"_index": "suggest_practice"}}
{"name": "华为 Mate 60 Pro", "suggest": {"input": ["华为 Mate 60", "华为手机", "Mate 60 Pro"], "weight": 10}}
{"index": {"_index": "suggest_practice"}}
{"name": "华为 MatePad Pro", "suggest": {"input": ["华为 MatePad", "华为平板"], "weight": 5}}
{"index": {"_index": "suggest_practice"}}
{"name": "iPhone 15 Pro", "suggest": {"input": ["iPhone 15", "苹果手机", "iPhone"], "weight": 8}}
{"index": {"_index": "suggest_practice"}}
{"name": "小米 14 Ultra", "suggest": {"input": ["小米 14", "小米手机"], "weight": 6}}

# 3. 测试自动补全
POST /suggest_practice/_search
{
  "suggest": {
    "my_suggest": {
      "prefix": "华为",
      "completion": { "field": "suggest", "size": 5 }
    }
  }
}

POST /suggest_practice/_search
{
  "suggest": {
    "my_suggest": {
      "prefix": "iPh",
      "completion": { "field": "suggest", "size": 5 }
    }
  }
}

# 4. 清理
DELETE /suggest_practice
```

### 练习 3：Ingest Pipeline

```
# 1. 创建 Pipeline
PUT /_ingest/pipeline/practice_pipeline
{
  "processors": [
    {
      "set": {
        "field": "ingested_at",
        "value": "{{_ingest.timestamp}}"
      }
    },
    {
      "lowercase": {
        "field": "level"
      }
    },
    {
      "set": {
        "if": "ctx.level == 'error'",
        "field": "priority",
        "value": "high"
      }
    },
    {
      "set": {
        "if": "ctx.level != 'error'",
        "field": "priority",
        "value": "normal"
      }
    }
  ]
}

# 2. 用 Pipeline 写入数据
PUT /pipeline_test/_doc/1?pipeline=practice_pipeline
{
  "message": "Something went wrong",
  "level": "ERROR"
}

PUT /pipeline_test/_doc/2?pipeline=practice_pipeline
{
  "message": "User logged in",
  "level": "INFO"
}

# 3. 查看结果——level 变小写，自动添加了 ingested_at 和 priority
GET /pipeline_test/_doc/1
GET /pipeline_test/_doc/2

# 4. 清理
DELETE /pipeline_test
DELETE /_ingest/pipeline/practice_pipeline
```

---

## 本阶段总结

```
生产运维能力：
  ILM：Hot → Warm → Cold → Delete 自动管理索引生命周期
  快照：SLM 自动化备份 + 增量快照 + 恢复
  安全：TLS + 认证 + 角色权限 + API Key

高级搜索特性：
  Completion Suggester → 搜索自动补全（FST，毫秒级）
  Geo 查询 → 附近搜索 + 距离排序
  Field Collapsing → 按字段去重（品牌去重）
  Percolator → 反向搜索（文档匹配查询 → 告警）
  Runtime Fields → 查询时动态计算字段

数据处理：
  Ingest Pipeline → 写入前预处理（grok/date/geoip）

ELK 生态：
  Filebeat(采集) → Kafka(缓冲) → Logstash(转换) → ES(存储) → Kibana(可视化)
  Kafka 的作用：削峰、解耦、持久化、多消费者

向量搜索（ES 8.x）：
  dense_vector + HNSW 索引 + KNN 查询
  混合搜索：BM25 + KNN 自动融合
```

---

## 全 10 阶段完结总结 🎉

```
"会用"层（阶段 1-5）：
  1. 核心概念（倒排索引、集群架构基础）
  2. Mapping（字段类型、索引设计模式）
  3. 分词（Analyzer、IK、search_analyzer）
  4. Query DSL（match/term/bool、BM25、深度分页、高亮）
  5. 聚合（Bucket/Metric/Pipeline、近似聚合）

"懂原理"层（阶段 6-8）：
  6. 存储原理（FST、Segment、refresh/flush/translog/merge、NRT）
  7. 集群架构（节点角色、分片路由、选主、脑裂、故障恢复）
  8. 性能调优（写入/查询优化、JVM、OS、容量规划）

"能落地"层（阶段 9-10）：
  9. 数据同步（CDC/MQ/Logstash、一致性保障）
  10. 生产运维（ILM、快照、安全、Suggester、向量搜索、ELK）

→ 进入阶段 11：面试串联（将所有知识以面试视角重新组织）
```

## 资深扩展

如果你要从“知道生产特性”升级到“能负责生产治理”，继续看阶段 12 的 [生产拓扑与 Data Tiers](../12-senior-es-and-search-engineering/02-production-topology-and-data-tiers.md) 和 [故障恢复、RPO/RTO 与 SLO](../12-senior-es-and-search-engineering/03-failure-recovery-and-slo.md)。
