# 最小端到端 Demo:实时订单分析

> **目标**:30 分钟内跑通 **Kafka → Flink → ClickHouse** 完整实时数据管道
> **场景**:电商实时大屏——每分钟 GMV、热销 Top10 商品
> **前置**:只需装 Docker(不用装 Java/Scala/Python 全家桶)

---

## 一、架构图(你即将搭建的东西)

```
  [ 数据生成器 ]                  ← Python 脚本,模拟订单
        ↓ 写入
  [ Kafka ]                       ← 消息队列,缓冲数据
        ↓ 消费
  [ Flink SQL ]                   ← 实时聚合(每分钟窗口)
        ↓ 写入
  [ ClickHouse ]                  ← 存聚合结果
        ↓ 查询
  [ 你的终端 / 可选 Grafana ]     ← 看实时大屏
```

### 每个组件在干嘛

| 组件 | 职责 | 不用它行不行 |
|---|---|---|
| Kafka | 缓冲数据,解耦生产和消费 | 不行(生产和消费速度不匹配就崩) |
| Flink | 每分钟窗口聚合,计算 GMV | 不行(ClickHouse 不擅长流式计算) |
| ClickHouse | 存聚合结果,供查询 | 不行(Flink 不做持久化存储) |

---

## 二、环境准备

### 目录结构(一会儿你会创建这些文件)

```
~/flink-demo/
├── docker-compose.yml          # 一键启动所有服务
├── producer.py                 # 订单数据生成器
├── flink-sql.sql               # Flink SQL 任务
└── clickhouse-init.sql         # ClickHouse 建表
```

### 一行命令创建目录
```bash
mkdir -p ~/flink-demo && cd ~/flink-demo
```

---

## 三、Step 1:启动基础设施(5 分钟)

### 创建 `docker-compose.yml`

```yaml
version: '3.8'

services:
  # Kafka(使用 KRaft 模式,不需要 ZooKeeper)
  kafka:
    image: bitnami/kafka:3.6
    container_name: kafka
    ports:
      - "9092:9092"
    environment:
      - KAFKA_CFG_NODE_ID=0
      - KAFKA_CFG_PROCESS_ROLES=controller,broker
      - KAFKA_CFG_CONTROLLER_QUORUM_VOTERS=0@kafka:9093
      - KAFKA_CFG_LISTENERS=PLAINTEXT://:9092,CONTROLLER://:9093
      - KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092
      - KAFKA_CFG_CONTROLLER_LISTENER_NAMES=CONTROLLER
      - KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT

  # Flink JobManager
  jobmanager:
    image: flink:1.18-scala_2.12
    container_name: jobmanager
    ports:
      - "8081:8081"
    command: jobmanager
    environment:
      - |
        FLINK_PROPERTIES=
        jobmanager.rpc.address: jobmanager

  # Flink TaskManager
  taskmanager:
    image: flink:1.18-scala_2.12
    container_name: taskmanager
    depends_on:
      - jobmanager
    command: taskmanager
    scale: 1
    environment:
      - |
        FLINK_PROPERTIES=
        jobmanager.rpc.address: jobmanager
        taskmanager.numberOfTaskSlots: 2

  # ClickHouse
  clickhouse:
    image: clickhouse/clickhouse-server:24.3
    container_name: clickhouse
    ports:
      - "8123:8123"   # HTTP
      - "9000:9000"   # Native
    ulimits:
      nofile:
        soft: 262144
        hard: 262144
```

### 启动
```bash
docker compose up -d
```

### 验证(等 30 秒后)
- Flink Web UI:http://localhost:8081
- ClickHouse:`docker exec -it clickhouse clickhouse-client`,输入 `SELECT 1` 应返回 1

---

## 四、Step 2:在 Kafka 建 Topic(1 分钟)

```bash
docker exec -it kafka kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --create --topic orders \
  --partitions 3 --replication-factor 1
```

---

## 五、Step 3:在 ClickHouse 建表(2 分钟)

### 进入 ClickHouse
```bash
docker exec -it clickhouse clickhouse-client
```

### 建表(直接粘贴到 client 里)
```sql
CREATE DATABASE IF NOT EXISTS demo;

-- 每分钟 GMV 聚合结果表
CREATE TABLE demo.gmv_per_minute (
    window_start DateTime,
    total_gmv    Decimal(18, 2),
    order_count  UInt64
) ENGINE = MergeTree()
ORDER BY window_start;

-- 每分钟热销 Top 商品聚合表
CREATE TABLE demo.hot_products_per_minute (
    window_start DateTime,
    product_id   UInt32,
    sales_count  UInt64,
    sales_amount Decimal(18, 2)
) ENGINE = MergeTree()
ORDER BY (window_start, product_id);
```

输入 `exit` 退出。

---

## 六、Step 4:启动数据生成器(2 分钟)

### 创建 `producer.py`

```python
import json
import random
import time
from datetime import datetime
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

PRODUCTS = [
    (1001, "iPhone", 6999),
    (1002, "MacBook", 12999),
    (1003, "AirPods", 1299),
    (1004, "iPad", 3999),
    (1005, "Watch", 2999),
]

print("开始生产订单... Ctrl+C 停止")
while True:
    product = random.choice(PRODUCTS)
    order = {
        "order_id": f"ORDER_{int(time.time() * 1000)}_{random.randint(1000, 9999)}",
        "user_id": random.randint(1, 1000),
        "product_id": product[0],
        "product_name": product[1],
        "price": product[2],
        "quantity": random.randint(1, 3),
        "order_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    producer.send('orders', order)
    print(f"发送订单: {order['order_id']} - {order['product_name']} x {order['quantity']}")
    time.sleep(0.2)  # 每秒 5 条
```

### 运行
```bash
pip install kafka-python
python producer.py
```

**保持这个终端运行**,它会持续发订单。

---

## 七、Step 5:运行 Flink SQL 任务(10 分钟,核心)

### 进入 Flink SQL Client
```bash
docker exec -it jobmanager ./bin/sql-client.sh
```

> ⚠️ 首次进入需要下载 Connector。如果提示 jar 缺失,先执行本节末尾的"补充:下载 Connector"。

### 粘贴以下 SQL(逐段执行)

**1)创建 Kafka Source 表**
```sql
SET 'execution.checkpointing.interval' = '10s';

CREATE TABLE orders_kafka (
    order_id      STRING,
    user_id       BIGINT,
    product_id    INT,
    product_name  STRING,
    price         DECIMAL(10, 2),
    quantity      INT,
    order_time    TIMESTAMP(3),
    WATERMARK FOR order_time AS order_time - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'orders',
    'properties.bootstrap.servers' = 'kafka:9092',
    'properties.group.id' = 'flink-demo',
    'scan.startup.mode' = 'latest-offset',
    'format' = 'json'
);
```

**2)创建 ClickHouse Sink 表 - GMV**
```sql
CREATE TABLE gmv_ck (
    window_start  TIMESTAMP(3),
    total_gmv     DECIMAL(18, 2),
    order_count   BIGINT
) WITH (
    'connector' = 'clickhouse',
    'url' = 'jdbc:clickhouse://clickhouse:8123/demo',
    'table-name' = 'gmv_per_minute',
    'sink.batch-size' = '100',
    'sink.flush-interval' = '1000'
);
```

**3)创建 ClickHouse Sink 表 - Top 商品**
```sql
CREATE TABLE hot_products_ck (
    window_start  TIMESTAMP(3),
    product_id    INT,
    sales_count   BIGINT,
    sales_amount  DECIMAL(18, 2)
) WITH (
    'connector' = 'clickhouse',
    'url' = 'jdbc:clickhouse://clickhouse:8123/demo',
    'table-name' = 'hot_products_per_minute',
    'sink.batch-size' = '100',
    'sink.flush-interval' = '1000'
);
```

**4)启动聚合任务 - 每分钟 GMV**
```sql
INSERT INTO gmv_ck
SELECT
    window_start,
    SUM(price * quantity) AS total_gmv,
    COUNT(*) AS order_count
FROM TABLE(
    TUMBLE(TABLE orders_kafka, DESCRIPTOR(order_time), INTERVAL '1' MINUTE)
)
GROUP BY window_start, window_end;
```

**5)启动聚合任务 - 每分钟热销商品**(另一个 INSERT,会创建新 Job)
```sql
INSERT INTO hot_products_ck
SELECT
    window_start,
    product_id,
    COUNT(*) AS sales_count,
    SUM(price * quantity) AS sales_amount
FROM TABLE(
    TUMBLE(TABLE orders_kafka, DESCRIPTOR(order_time), INTERVAL '1' MINUTE)
)
GROUP BY window_start, window_end, product_id;
```

### 验证
打开 http://localhost:8081,应该能看到 2 个 RUNNING 状态的 Job。

---

### 补充:下载 Connector(如果上面报缺 Jar)

Flink 默认不带 Kafka 和 ClickHouse Connector,手动下载:

```bash
# 进入 JobManager 容器
docker exec -it jobmanager bash

cd /opt/flink/lib

# Kafka Connector
wget https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.1.0-1.18/flink-sql-connector-kafka-3.1.0-1.18.jar

# ClickHouse Connector(社区版)
wget https://github.com/itinycheng/flink-connector-clickhouse/releases/download/v1.16.0-release/flink-connector-clickhouse-1.16.0-SNAPSHOT.jar

# ClickHouse JDBC 驱动
wget https://repo1.maven.org/maven2/com/clickhouse/clickhouse-jdbc/0.6.0/clickhouse-jdbc-0.6.0-all.jar

exit

# TaskManager 也要放一份
docker exec -it taskmanager bash -c "cp /opt/flink/lib/*kafka* /opt/flink/lib/*clickhouse* /tmp/"

# 重启 Flink
docker compose restart jobmanager taskmanager
```

---

## 八、Step 6:查看结果(激动人心!)

### 等 1-2 分钟(让窗口触发),然后查 ClickHouse

```bash
docker exec -it clickhouse clickhouse-client --database demo
```

```sql
-- 看每分钟 GMV
SELECT * FROM gmv_per_minute ORDER BY window_start DESC LIMIT 10;

-- 结果类似:
-- ┌────window_start────┬─total_gmv─┬─order_count─┐
-- │ 2026-04-17 10:05:00 │  245678.00 │         287 │
-- │ 2026-04-17 10:04:00 │  198432.00 │         251 │
-- └────────────────────┴───────────┴─────────────┘
```

```sql
-- 看热销 Top 5
SELECT
    window_start,
    product_id,
    sales_count,
    sales_amount
FROM hot_products_per_minute
WHERE window_start >= now() - INTERVAL 5 MINUTE
ORDER BY window_start DESC, sales_count DESC
LIMIT 10;
```

### 持续刷新看变化
```sql
-- ClickHouse 支持每秒刷新(Ctrl+C 退出)
WATCH (
    SELECT window_start, total_gmv, order_count
    FROM gmv_per_minute
    ORDER BY window_start DESC
    LIMIT 5
);
```

---

## 九、理解你刚才做了什么

### 关键点 1:Kafka 是缓冲
- Producer 每秒 5 条,Flink 消费速度完全可以不同步
- 即使 Flink 挂了,数据也在 Kafka 里等着

### 关键点 2:Flink 的 Window
- `TUMBLE(..., INTERVAL '1' MINUTE)`:每分钟一个不重叠的窗口
- **Watermark** 处理乱序:`order_time - INTERVAL '5' SECOND` 允许 5 秒延迟
- 窗口结束 + Watermark 越过 → 触发计算 → 写入 ClickHouse

### 关键点 3:ClickHouse 只存结果
- Flink 已经算好了,ClickHouse 只需要存聚合数据
- 查询量小,速度快

### 关键点 4:为什么不只用 ClickHouse
- 直接把 Kafka 数据灌 ClickHouse 也能聚合,但:
  - 每个查询都要扫原始数据,消耗大
  - 无法做复杂流处理(CEP、维表 Join)
  - 不能处理乱序数据

---

## 十、扩展玩法

### 玩法 1:加 Redis 缓存
- Flink 结果同时写 Redis(Key = `gmv:{minute}`)
- API 查询先 Redis,再 ClickHouse
- 模拟真实大屏的缓存层

### 玩法 2:加 Grafana
```yaml
# 在 docker-compose.yml 加
grafana:
  image: grafana/grafana:latest
  ports: ["3000:3000"]
```
接入 ClickHouse 数据源,做实时大屏。

### 玩法 3:换场景
- 日志分析:生产 Nginx 日志,统计每分钟 PV/UV
- IoT:生产设备数据,统计异常
- 风控:CEP 检测 5 分钟内多次失败登录

### 玩法 4:故意搞破坏
- 停掉 TaskManager:`docker stop taskmanager`
- 启动:`docker start taskmanager`
- 观察 Flink 从 Checkpoint 恢复,数据没丢也没重

---

## 十一、清理

```bash
cd ~/flink-demo
docker compose down -v   # -v 删除数据卷
```

---

## 十二、学完这个 Demo 你应该能

- [ ] 独立解释每个组件的职责
- [ ] 画出数据从产生到展示的完整流程
- [ ] 理解 Flink Window + Watermark 的配合
- [ ] 理解"为什么需要 Kafka 做缓冲"
- [ ] 理解"为什么 Flink 和 ClickHouse 不是竞品"
- [ ] 在面试中自信地说:"我搭过一套实时数仓"

---

## 十三、常见问题排查

| 问题 | 原因 | 解决 |
|---|---|---|
| Flink Web UI 打不开 | 容器没起来 | `docker logs jobmanager` 看日志 |
| Producer 连不上 Kafka | Kafka 没准备好 | 等 30 秒后再试 |
| SQL Client 报缺 jar | Connector 没下载 | 看本文"补充:下载 Connector" |
| ClickHouse 查不到数据 | 窗口还没触发 | 等够 1 分钟 + 5 秒 Watermark |
| Flink Job 显示 FAILED | 通常是 Sink 连接问题 | 检查 ClickHouse 容器是否运行 |

---

**这个 Demo 就是实时数仓的"最小骨架"**。真实生产只是把每一环做大、做稳:Kafka 多分区、Flink 多 TaskManager、ClickHouse 多分片多副本。**核心概念和这个 Demo 完全一致。**
