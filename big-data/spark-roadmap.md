# Apache Spark 学习路线

> 学习顺序:**Spark → Flink → ClickHouse**(本篇第 1 站)
> 目标:掌握批处理核心 + 流处理基础,能应对离线数仓和 ML 场景的系统设计题
> 预计时间:3-4 周

---

## 一、心智模型(先建立直觉)

### Spark 是什么
**一句话**:Spark 是**分布式计算引擎**——把大数据切成小块,分发到多台机器上并行计算,再把结果汇总。

### 和其他东西的关系
```
        数据源(HDFS/S3/Kafka/MySQL)
                   ↓
            [ Spark 计算引擎 ] ← 你在学的东西
                   ↓
        结果(Hive/Iceberg/MySQL/报表)
```

### 核心抽象:三层演进
Spark 的 API 经历了三代,**必须搞清楚它们的关系**:

```
RDD(底层)→ DataFrame(结构化)→ Dataset(强类型)
   ↑              ↑                    ↑
 手动控制    SQL 风格最常用        Scala/Java 强类型
```

**2026 年实践**:90% 代码写 DataFrame/SQL,只在优化时碰 RDD。

---

## 二、分阶段学习路线

### 阶段 1:环境 + Hello World(2-3 天)

**目标**:在本地跑通第一个 Spark 程序,理解基本流程

- [ ] **环境搭建**
  - 本地安装 Spark(推荐 `brew install apache-spark` 或 Docker)
  - 配置 PySpark / Spark Shell
  - 理解 `spark-submit` 命令结构

- [ ] **WordCount**(必跑经典 Demo)
  - 用 RDD 写一次
  - 用 DataFrame 写一次
  - 用 SQL 写一次
  - 对比三种写法的差异

- [ ] **关键概念初识**
  - Driver / Executor / Cluster Manager 是什么
  - 什么是 Job / Stage / Task
  - 画出 Spark 任务执行流程图

**产出**:能用 3 种 API 完成 WordCount,能画出 Spark 架构图

---

### 阶段 2:RDD 核心(3-4 天)

**目标**:理解 Spark 的底层抽象,搞懂"为什么 Spark 快"

- [ ] **RDD 是什么**
  - 弹性分布式数据集:不可变、分区、可恢复
  - 为什么叫"弹性"(Resilient):依赖链 + 血缘(Lineage)

- [ ] **两类算子**
  - **Transformation**(懒执行):`map`、`filter`、`flatMap`、`groupByKey`、`reduceByKey`
  - **Action**(触发执行):`collect`、`count`、`take`、`saveAsTextFile`
  - **记住**:Transformation 只是画图,Action 才真的跑

- [ ] **宽依赖 vs 窄依赖**(⭐ 面试必考)
  - 窄依赖:一对一,不触发 Shuffle(`map`、`filter`)
  - 宽依赖:多对多,触发 Shuffle(`groupByKey`、`join`)
  - **Shuffle 是性能瓶颈**

- [ ] **持久化**
  - `cache()` / `persist()`:什么时候需要
  - 存储级别:`MEMORY_ONLY` / `MEMORY_AND_DISK` / `DISK_ONLY`

**产出**:能解释"为什么 `reduceByKey` 比 `groupByKey` 快"

---

### 阶段 3:DataFrame + Spark SQL(5-7 天,重点)

**目标**:掌握 2026 年工作中 90% 用的 API

- [ ] **DataFrame 基础**
  - 从 CSV/JSON/Parquet 读入数据
  - `select` / `filter` / `groupBy` / `agg` / `join`
  - `withColumn` 添加/修改列
  - 写出到 Parquet / Iceberg / JDBC

- [ ] **Spark SQL**
  - 注册临时表:`createOrReplaceTempView`
  - 直接写 SQL 查询
  - UDF(自定义函数)

- [ ] **Catalyst 优化器**(⭐ 面试加分项)
  - 逻辑计划 → 优化后逻辑计划 → 物理计划 → 执行
  - 用 `explain()` 查看执行计划
  - 谓词下推、列裁剪、常量折叠

- [ ] **Tungsten 执行引擎**
  - 堆外内存管理
  - 代码生成(Whole-Stage Codegen)
  - 为什么 DataFrame 比 RDD 快

**产出**:能读懂 `df.explain()` 的输出,能手动优化一个慢查询

---

### 阶段 4:Structured Streaming(4-5 天)

**目标**:用 Spark 处理流数据,理解微批模型

- [ ] **核心思想**
  - "把流当成无界表" —— 每次微批追加新行
  - 和 Flink 真流处理的本质区别

- [ ] **基础操作**
  - 从 Kafka 读取流
  - 窗口聚合:`Tumbling` / `Sliding` / `Session`
  - Watermark 处理延迟数据
  - 输出模式:`Append` / `Update` / `Complete`

- [ ] **容错**
  - Checkpoint 机制
  - 端到端 Exactly-Once 如何实现

- [ ] **对比 Spark Streaming(老)**
  - DStream 已过时,只需了解概念
  - Structured Streaming 是正道

**产出**:跑通 Kafka → Spark Streaming → 控制台的 Demo

---

### 阶段 5:性能调优(4-5 天,面试核心)

**目标**:能回答"一个 Spark 任务很慢,你怎么排查?"

- [ ] **Spark UI 看什么**
  - Stage 视图:找最慢的 Stage
  - Task 视图:看是否有数据倾斜(某个 Task 明显慢)
  - Storage 视图:看缓存使用情况
  - SQL 视图:看执行计划

- [ ] **常见优化手段**
  - **数据倾斜**:加盐、两阶段聚合、广播小表
  - **Shuffle 优化**:`reduceByKey` 代替 `groupByKey`、调整 `spark.sql.shuffle.partitions`
  - **广播 Join**:`broadcast()` 小表
  - **AQE(Adaptive Query Execution)**:自适应查询优化,默认开
  - **分区调整**:`repartition` / `coalesce`

- [ ] **资源配置**
  - `executor-memory` / `executor-cores` / `num-executors` 怎么定
  - 并行度调优

**产出**:准备 5 个常见慢查询 Case 的优化思路

---

### 阶段 6:生态整合(3-4 天)

**目标**:了解 Spark 在真实架构中怎么用

- [ ] **Spark + Iceberg / Delta Lake**
  - 湖仓一体:Spark 读写 Iceberg 表
  - Time Travel、Schema 演进

- [ ] **Spark on Kubernetes**
  - 现代部署方式,取代 YARN

- [ ] **Spark + MLlib**(按需)
  - 特征工程 + 模型训练
  - 主要用 `ml` 包,不用老的 `mllib`

- [ ] **Databricks(商业化最成功的 Spark 发行版)**
  - 了解 Databricks Runtime、Photon、Unity Catalog

**产出**:画出"Spark + Iceberg + S3"的湖仓架构图

---

## 三、实战项目建议

**项目 1:离线日志分析**
- 数据源:Nginx 日志(自己造或公开数据集)
- 任务:按小时/天统计 PV/UV、Top 10 URL、异常状态码
- 技术栈:Spark SQL + Parquet

**项目 2:批流一体**
- 离线:Spark 批处理历史数据 → Iceberg
- 实时:Structured Streaming 消费 Kafka → 同一张 Iceberg 表
- 体会"Lambda 架构 → Kappa 架构"的演进

**项目 3:ML 流水线**(可选)
- 用 Spark ML 做用户流失预测
- 从特征工程到模型训练完整走一遍

---

## 四、高频面试题清单

### 基础
1. Spark 和 MapReduce 的区别?为什么 Spark 快?
2. RDD、DataFrame、Dataset 的区别?
3. 宽依赖和窄依赖?什么是 Shuffle?
4. Spark 任务执行流程(Driver/Executor/Stage/Task)?
5. `cache` 和 `persist` 区别?存储级别有哪些?

### 进阶
6. Catalyst 优化器做了什么?
7. Tungsten 是什么?堆外内存的意义?
8. `reduceByKey` vs `groupByKey`?
9. AQE 是什么?解决了什么问题?
10. Structured Streaming 和 Flink 的本质区别?

### 调优
11. 数据倾斜怎么解决?
12. 一个 Spark 任务 OOM 怎么排查?
13. 为什么要用广播 Join?什么时候不能用?
14. `spark.sql.shuffle.partitions` 默认值是多少?怎么调?

### 场景题
15. 10 亿条订单数据,统计每个用户的总消费额,怎么写最快?
16. Spark 读 Kafka,怎么保证 Exactly-Once?
17. 离线数仓每天跑批 4 小时,怎么优化到 1 小时?

---

## 五、学习资源

### 官方文档(必读)
- https://spark.apache.org/docs/latest/ (看最新版)
- 重点章节:Spark SQL Programming Guide、Structured Streaming Programming Guide

### 书籍
- 《Spark: The Definitive Guide》(英文,最权威)
- 《Learning Spark, 2nd Edition》(英文,入门友好)

### 实战
- Databricks Community Edition(免费云端 Spark 环境)
- Kaggle 公开数据集

---

## 六、检查点(每阶段结束自测)

- [ ] 能画出 Spark 完整架构图
- [ ] 能用 3 种 API(RDD/DataFrame/SQL)写 WordCount
- [ ] 能解释宽窄依赖和 Shuffle
- [ ] 能读懂 `explain()` 输出
- [ ] 能跑通 Kafka → Structured Streaming Demo
- [ ] 能排查并解决一个数据倾斜问题
- [ ] 能回答 10 个以上面试题

---

**学完本篇 → 进入 [Flink 路线](./flink-roadmap.md)**
