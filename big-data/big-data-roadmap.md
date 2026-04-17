# 大数据学习路线(2026)

> 面向:有后端基础、为求职/面试准备的工程师
> 目标:掌握主流大数据生态,能在系统设计题中合理选型
> 原则:**排除中国团队主导的开源项目**,聚焦国际主流

---

## 一、核心心智模型

大数据系统可以抽象成 **5 个环节**,每个环节选一个代表框架即可覆盖 90% 场景:

```
[ 采集/传输 ]  →  [ 计算 ]  →  [ 存储 ]  →  [ 查询 ]  →  [ 调度 ]
    Kafka         Flink/Spark    Iceberg     ClickHouse    Airflow
                                              DuckDB
```

记住这张图,面试系统设计基本够用。

---

## 二、学习优先级(按求职价值排序)

### P0 - 必学(面试高频)

| 框架 | 定位 | 学习重点 |
|---|---|---|
| **Apache Kafka** | 消息队列 / 流数据管道 | 分区、消费组、Exactly-Once、Kafka Streams |
| **Apache Flink** | 实时流计算引擎 | 窗口、状态管理、Checkpoint、Flink SQL |
| **Apache Spark** | 批/流计算引擎 | Spark SQL、Structured Streaming、Catalyst |
| **ClickHouse** | 实时 OLAP 数据库 | MergeTree、物化视图、向量化执行 |

### P1 - 重要(湖仓方向)

| 框架 | 定位 | 学习重点 |
|---|---|---|
| **Apache Iceberg** | 数据湖表格式 | Schema 演进、Time Travel、隐藏分区 |
| **Trino (PrestoSQL)** | 联邦查询引擎 | 跨数据源 Join、Connector 机制 |
| **DuckDB** | 嵌入式 OLAP | 和 Pandas/Python 集成、单机分析 |

### P2 - 配套(项目落地必备)

| 框架 | 定位 | 学习重点 |
|---|---|---|
| **Apache Airflow** | 任务调度 | DAG、Operator、XCom、调度策略 |
| **Apache Parquet** | 列式存储格式 | 了解原理即可,不需深入 |

### P3 - AI 相关(结合 LLM 方向强推荐)

| 框架 | 定位 | 学习重点 |
|---|---|---|
| **Milvus** | 向量数据库 | 索引类型(HNSW/IVF)、向量检索原理 |
| **Qdrant / Weaviate** | 向量数据库替代选型 | 对比 Milvus 的优劣 |
| **LanceDB** | AI 原生数据湖 | 嵌入式向量存储新范式 |

---

## 三、不建议优先学(已过时或衰退)

| 框架 | 原因 |
|---|---|
| Hadoop MapReduce | 被 Spark 完全取代,只需了解概念 |
| Hive | 被 Spark SQL / Trino / Iceberg 取代 |
| HBase | 小众化,被云数据库取代 |
| Apache Storm | 被 Flink 完全取代 |
| Apache Hudi | 被 Iceberg 压过(生态、云厂商支持) |
| Delta Lake | 强绑定 Databricks,开源生态不如 Iceberg |

---

## 四、典型架构(要能背下来)

### 1. 实时数仓架构

```
业务系统 → Kafka → Flink(实时清洗/聚合) → ClickHouse → BI 看板
                      ↓
                  实时告警 / 风控
```

### 2. 湖仓一体架构

```
多源数据 → Kafka / CDC → Spark/Flink → Iceberg(S3/HDFS)
                                          ↓
                                   Trino / Spark SQL 查询
```

### 3. AI / RAG 架构

```
文档/知识库 → Embedding 模型 → Milvus/Qdrant
                                   ↓
                         LLM 应用 ← 向量检索
```

---

## 五、关键对比(面试常问)

### Flink vs Spark Streaming
- **Flink**:真·流处理,毫秒级延迟,状态管理强
- **Spark Streaming**:微批处理,秒级延迟,批流统一 API
- **选型**:延迟敏感选 Flink,已有 Spark 栈选 Spark

### ClickHouse vs Flink
- **不是竞品**。Flink 算"流动中的数据",ClickHouse 查"存下来的数据"
- 常见组合:Flink 实时计算 → 写入 ClickHouse → 供查询

### ClickHouse vs DuckDB
- **ClickHouse**:分布式集群,海量数据
- **DuckDB**:单机嵌入式,"OLAP 版 SQLite"
- **选型**:TB 级以上用 ClickHouse,单机分析用 DuckDB

### Iceberg vs Hudi vs Delta Lake
- **Iceberg**:2026 赢家,云厂商/Snowflake/BigQuery 全支持
- **Hudi**:Uber 开源,更新场景强,但生态被 Iceberg 压过
- **Delta Lake**:Databricks 主导,开源但生态绑定强

---

## 六、学习节奏建议

### 第 1 阶段:建立全局观(1 周)
- [ ] 理清 5 个环节各自在干什么
- [ ] 能画出实时数仓架构图并解释
- [ ] 搞懂 Flink 和 ClickHouse 的区别

### 第 2 阶段:核心框架(每个 2-3 周)
- [ ] Kafka:概念 + 本地搭建 + 编写 Producer/Consumer
- [ ] Flink:Flink SQL + 一个实时聚合 Demo
- [ ] ClickHouse:建表 + 物化视图 + 性能调优

### 第 3 阶段:湖仓(2-3 周)
- [ ] Iceberg:读写一次完整的表,理解元数据分层
- [ ] Trino:跨数据源查询 Demo

### 第 4 阶段:AI 方向(1-2 周)
- [ ] Milvus:跑通一个 RAG Demo
- [ ] 对比 Qdrant / Weaviate

### 第 5 阶段:调度(1 周)
- [ ] Airflow:写一个 ETL DAG

---

## 七、面试话术模板

### 问:你了解哪些大数据技术?
> 我按**数据流向**理解大数据栈:
> - **采集层**:Kafka 做消息队列
> - **计算层**:Flink 做实时、Spark 做批处理
> - **存储层**:Iceberg 做数据湖、ClickHouse 做 OLAP
> - **查询层**:Trino 做联邦查询
> - **调度层**:Airflow 编排
> 结合 AI 场景还会用到 Milvus 等向量数据库。

### 问:Flink 和 ClickHouse 的区别?
> Flink 是**流计算引擎**,处理流动中的数据,解决"算得快";
> ClickHouse 是**分析数据库**,查询已存储的数据,解决"查得快"。
> 它们不是竞品,典型架构是 **Kafka → Flink → ClickHouse**。

### 问:为什么用 Iceberg 不用 Hive?
> Hive 基于目录管理元数据,Schema 演进、ACID 事务、小文件都是老问题;
> Iceberg 用**元数据分层**(snapshot/manifest)解决了这些,并且原生支持
> Time Travel 和隐藏分区,云厂商生态也更好。

---

## 八、子路线(已展开)

按推荐学习顺序:

1. **[Spark 学习路线](./spark-roadmap.md)** - 批处理入门,3-4 周
2. **[Flink 学习路线](./flink-roadmap.md)** - 真·流处理,3-4 周
3. **[ClickHouse 学习路线](./clickhouse-roadmap.md)** - OLAP 查询层,2-3 周

**为什么这个顺序**:
- Spark 生态广、资料多、入门平缓,先建立分布式计算的基本感觉
- Flink 概念抽象(State/Watermark/Checkpoint),学完 Spark 再学轻松很多
- ClickHouse 作为"查询终点",和前两者天然接上,正好串起整条实时数仓链路

## 九、TODO / 后续讨论

- [ ] Kafka 独立路线(实时数仓的血管)
- [ ] Iceberg 路线(湖仓一体方向)
- [ ] Airflow 路线(调度必备)
- [ ] Milvus / 向量数据库路线(和 LLM 方向结合)
- [ ] 端到端实战项目:Kafka + Flink + ClickHouse 实时数仓 Demo

---

**最后更新**:2026-04-17
**当前进度**:路线制定完成,待逐一深入
