# 日志基础设施

## 概述

结构化日志产生之后，需要一套基础设施完成采集、传输、存储、查询的完整链路。本节覆盖两套主流方案（ELK 和 Loki），日志采集器选型，以及生产级的架构设计。

---

## ELK Stack 架构

ELK 是 Elasticsearch + Logstash + Kibana 的组合，是最成熟的日志平台方案。

```
应用日志文件
    │
    ▼
┌──────────┐     ┌───────────┐     ┌───────────────┐     ┌──────────┐
│ Filebeat │────▶│ Logstash  │────▶│ Elasticsearch │────▶│ Kibana   │
│ (采集)    │     │ (解析转换) │     │ (存储索引)     │     │ (查询展示) │
└──────────┘     └───────────┘     └───────────────┘     └──────────┘
```

### 各组件职责

**Elasticsearch**：分布式搜索引擎，负责日志的存储和全文索引。
- 每条日志是一个 JSON 文档
- 基于倒排索引实现快速全文搜索
- 支持聚合分析（按时间、按字段统计）
- 资源消耗大：内存（JVM heap）、磁盘（索引膨胀比约 1:1.5）

**Logstash**：数据处理管道，负责解析、转换、过滤。
- Input：从 Beats、Kafka、文件等读取数据
- Filter：grok 解析非结构化日志、mutate 字段改名、date 时间解析
- Output：写入 Elasticsearch、Kafka 等

```ruby
# logstash.conf 示例
input {
  beats { port => 5044 }
}
filter {
  json { source => "message" }    # 已经是 JSON 格式则直接解析
  date {
    match => ["timestamp", "ISO8601"]
    target => "@timestamp"
  }
  mutate {
    remove_field => ["agent", "ecs", "host"]  # 去掉 Filebeat 附加的冗余字段
  }
}
output {
  elasticsearch {
    hosts => ["http://es-node1:9200"]
    index => "app-logs-%{+YYYY.MM.dd}"       # 按天创建索引
  }
}
```

**Kibana**：可视化查询界面。
- Discover：日志搜索和浏览
- Dashboard：自定义仪表盘
- Lens：拖拽式图表构建

**Filebeat**：轻量级日志采集器（后面详细对比）。

---

## Loki + Grafana：轻量级替代方案

Grafana Loki 的设计哲学与 Elasticsearch 截然不同：**只索引标签，不索引日志内容**。

```
应用日志
    │
    ▼
┌──────────────┐     ┌──────────┐     ┌─────────┐
│ Promtail     │────▶│  Loki    │────▶│ Grafana │
│ (采集+标签)   │     │ (存储)    │     │ (查询)   │
└──────────────┘     └──────────┘     └─────────┘
```

### 标签 vs 全文索引

| 维度 | Elasticsearch | Loki |
|------|--------------|------|
| 索引策略 | 全文倒排索引 | 仅索引标签（label） |
| 存储成本 | 高（索引膨胀 ~1.5x） | 低（压缩存储原始日志） |
| 查询速度 | 任意字段快速查询 | 标签过滤快，内容搜索需扫描 |
| 运维复杂度 | 高（JVM 调优、分片管理） | 低（单二进制，对象存储） |
| 适用场景 | 大规模、复杂查询需求 | 中小规模、标签驱动查询 |

**Loki 的标签设计原则：**

```yaml
# Promtail 配置示例
scrape_configs:
  - job_name: kubernetes-pods
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod
      - source_labels: [__meta_kubernetes_container_name]
        target_label: container
```

**关键原则：标签的基数（cardinality）要低。** 不要把 userId、traceId 这种高基数字段作为标签，否则 Loki 会产生大量小的 chunk，性能急剧下降。正确做法是把它们留在日志正文中，用 LogQL 的 `|=`、`|~` 做文本过滤。

---

## 日志采集器对比

| 特性 | Filebeat | Fluentd | Vector |
|------|----------|---------|--------|
| 语言 | Go | Ruby + C | Rust |
| 内存占用 | ~30MB | ~100MB | ~20MB |
| 吞吐量 | 高 | 中 | 极高 |
| 配置方式 | YAML | XML-like | TOML/YAML |
| 生态集成 | Elastic 生态最佳 | Kubernetes 标准 | 新兴，全能型 |
| 数据处理 | 简单（processors） | 丰富（filter 插件） | 丰富（transforms） |
| 背压处理 | 自动减速 | 缓冲 + 重试 | 自适应并发 |

**选型建议：**
- 用 ELK → Filebeat 是天然搭配
- 用 Kubernetes → Fluentd/Fluent Bit 是 CNCF 标准
- 追求性能和灵活性 → Vector 是最优选择，一个组件替代 Filebeat + Logstash

### Vector 配置示例

```toml
# vector.toml
[sources.app_logs]
type = "file"
include = ["/var/log/app/*.log"]

[transforms.parse_json]
type = "remap"
inputs = ["app_logs"]
source = '''
. = parse_json!(.message)
.environment = "production"
'''

[sinks.loki]
type = "loki"
inputs = ["parse_json"]
endpoint = "http://loki:3100"
labels.service = "{{ service }}"
labels.level = "{{ level }}"

[sinks.elasticsearch]
type = "elasticsearch"
inputs = ["parse_json"]
endpoints = ["http://es:9200"]
bulk.index = "app-logs-%Y-%m-%d"
```

---

## 日志查询技巧

### Kibana KQL（Kibana Query Language）

```
# 基本字段查询
level: "ERROR" and service: "order-service"

# 范围查询
duration_ms >= 1000

# 通配符
message: *timeout*

# 组合查询
level: "ERROR" and service: "order-service" and not message: "expected error"

# 时间范围（通过 UI 时间选择器更方便）
@timestamp >= "2024-03-15T00:00:00" and @timestamp < "2024-03-16T00:00:00"

# 存在性查询
error.stacktrace: *    # 有 stacktrace 字段的记录
```

### LogQL（Loki 查询语言）

```
# 标签选择器（必须有，这是 Loki 性能的关键）
{service="order-service", level="ERROR"}

# 文本过滤
{service="order-service"} |= "timeout"          # 包含 timeout
{service="order-service"} != "health check"      # 排除 health check
{service="order-service"} |~ "user_id=(123|456)" # 正则匹配

# JSON 解析 + 字段过滤
{service="order-service"} | json | duration_ms > 1000

# 聚合（统计每分钟错误数）
count_over_time({service="order-service", level="ERROR"}[1m])

# 按 service 统计错误率
sum by (service) (
  count_over_time({level="ERROR"}[5m])
)
```

---

## 日志存储与保留策略

### 热温冷（Hot-Warm-Cold）架构

这是 Elasticsearch 生产部署的标准模式：

```
                    写入
                     │
                     ▼
              ┌─────────────┐
    Hot 节点   │  SSD 存储    │  最近 1-3 天的数据
    (高性能)   │  高 CPU/内存  │  承担写入 + 实时查询
              └──────┬──────┘
                     │ ILM 自动迁移
                     ▼
              ┌─────────────┐
    Warm 节点  │  HDD 存储   │  3-30 天的数据
    (中等)     │  中等配置    │  只读查询
              └──────┬──────┘
                     │ ILM 自动迁移
                     ▼
              ┌─────────────┐
    Cold 节点  │  对象存储    │  30-90 天的数据
    (低成本)   │  最小配置    │  偶尔查询
              └──────┬──────┘
                     │ ILM 自动删除
                     ▼
                   Delete        90 天后自动删除
```

### Elasticsearch ILM（Index Lifecycle Management）配置

```json
PUT _ilm/policy/app-logs-policy
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_size": "50gb",
            "max_age": "1d"
          },
          "set_priority": { "priority": 100 }
        }
      },
      "warm": {
        "min_age": "3d",
        "actions": {
          "shrink": { "number_of_shards": 1 },
          "forcemerge": { "max_num_segments": 1 },
          "set_priority": { "priority": 50 }
        }
      },
      "cold": {
        "min_age": "30d",
        "actions": {
          "set_priority": { "priority": 0 }
        }
      },
      "delete": {
        "min_age": "90d",
        "actions": { "delete": {} }
      }
    }
  }
}
```

### Loki 保留策略

```yaml
# loki-config.yaml
limits_config:
  retention_period: 720h       # 30 天
  max_query_length: 721h

compactor:
  working_directory: /loki/compactor
  retention_enabled: true
  retention_delete_delay: 2h
  delete_request_store: filesystem
```

---

## 日志采集架构设计

### 小规模（日志量 < 1GB/天）

```
应用 → Filebeat → Elasticsearch → Kibana
```

直连，简单可靠。

### 中规模（日志量 1-50 GB/天）

```
应用 → Filebeat → Kafka → Logstash → Elasticsearch → Kibana
```

加入 Kafka 作为缓冲层：
- 解耦采集和消费，Elasticsearch 故障不影响应用
- Kafka 提供削峰能力，突发日志量不会压垮 ES
- 可以多消费者：同时写 ES 和 Loki，或做实时分析

### 大规模（日志量 > 50 GB/天）

```
应用 → Vector(agent) → Kafka → Vector(aggregator) → Elasticsearch/Loki
                                       │
                                       ├──▶ S3（原始日志归档）
                                       └──▶ ClickHouse（分析查询）
```

- Vector agent 在每个节点做初步过滤和采样
- Kafka 集群做缓冲
- Vector aggregator 做路由、转换、多目标输出
- 日志同时落 ES（近实时查询）和 S3（长期归档）

---

## 小结

```
日志基础设施选型思路
├── 日志量小 + 查询需求复杂 → ELK 直连
├── 日志量中 + 需要缓冲 → ELK + Kafka
├── 日志量大 + 成本敏感 → Loki + 对象存储
├── 日志量大 + 查询复杂 → ELK Hot-Warm-Cold + ILM
└── 采集器：Filebeat(ELK) / Fluent Bit(K8s) / Vector(全能)
```

日志基础设施的核心挑战不是"能不能存"，而是"能不能在需要时快速找到那条关键日志"。下一节我们进入可观测性的第二支柱 —— Metrics 理论。
