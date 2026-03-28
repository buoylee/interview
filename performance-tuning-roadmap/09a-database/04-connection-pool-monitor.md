# 连接池监控

## 为什么需要连接池

数据库连接的创建成本极高：TCP 三次握手 + TLS 协商 + 认证 + 分配内存。一个 MySQL 连接的建立大约需要 3-10ms，在高并发场景下每秒创建几百个连接，光连接建立就消耗掉大量时间和资源。**连接池的核心作用是复用连接、控制并发、保护数据库**。连接池配错了，要么应用线程全部 hang 住等连接，要么把数据库压垮。

---

## 一、数据库连接池原理

### 连接生命周期

```
应用线程                    连接池                         数据库
   |                        |                              |
   |-- getConnection() ---->|                              |
   |                        |-- 池中有空闲连接? -->          |
   |                        |   是: 直接返回               |
   |<-- 返回连接 -----------|                              |
   |                        |   否: 池未满?                |
   |                        |     是: 创建新连接 -------->  |
   |                        |     <-- TCP+认证完成 ------   |
   |<-- 返回连接 -----------|                              |
   |                        |   否（池已满）: 等待释放      |
   |                        |     超时 → 抛异常            |
   |                        |                              |
   |-- 使用连接执行 SQL ---------------------------------->  |
   |<-- 返回结果 ------------------------------------------  |
   |                        |                              |
   |-- close()/归还 ------>  |                              |
   |                        |-- 连接有效? 放回池中          |
   |                        |-- 连接失效? 丢弃并创建新的    |
```

### 核心参数概念

| 参数 | 含义 | 类比 |
|------|------|------|
| minimumIdle | 最小空闲连接数 | 停车场最少保留的空车位 |
| maximumPoolSize | 最大连接数 | 停车场总车位 |
| connectionTimeout | 获取连接超时 | 排队等车位的最长时间 |
| idleTimeout | 空闲连接存活时间 | 空车位超时收回 |
| maxLifetime | 连接最大存活时间 | 车位使用年限 |
| validationTimeout | 连接有效性检查超时 | 检查车位是否能用的时间 |

---

## 二、HikariCP 参数调优

HikariCP 是目前 Java 生态中性能最好的连接池，Spring Boot 2.x+ 默认使用。

### 核心参数详解

```yaml
# application.yml
spring:
  datasource:
    hikari:
      # ===== 连接数 =====
      minimum-idle: 10              # 最小空闲连接（建议与 maximumPoolSize 相同）
      maximum-pool-size: 20         # 最大连接数

      # ===== 超时 =====
      connection-timeout: 3000      # 获取连接超时（ms），默认 30s 太长
      idle-timeout: 600000          # 空闲连接超时（ms），10 分钟
      max-lifetime: 1800000         # 连接最大存活时间（ms），30 分钟
      validation-timeout: 3000      # 连接有效性检查超时（ms）

      # ===== 连接检查 =====
      connection-test-query: SELECT 1   # MySQL 用 SELECT 1，PG 用 SELECT 1
      # 如果 JDBC4+ 驱动（推荐），不需要设置 test query，用 isValid() 更高效

      # ===== 泄漏检测 =====
      leak-detection-threshold: 30000   # 连接泄漏检测阈值（ms），30 秒

      # ===== 连接池名称 =====
      pool-name: PerfShop-HikariPool
```

### maximumPoolSize 计算公式

HikariCP 作者推荐的公式：

```
connections = ((core_count * 2) + effective_spindle_count)

例如：
- 4 核 CPU + 1 块 SSD：connections = (4 * 2) + 1 = 9
- 8 核 CPU + 1 块 SSD：connections = (8 * 2) + 1 = 17
```

**实际建议**：
- 不要设太大！大多数应用 10-20 就够了
- 如果应用有多个实例（例如 4 个 Pod），总连接数 = 单实例连接数 × 实例数
- 数据库端 `max_connections` 要大于所有应用实例的总连接数

```sql
-- MySQL：查看最大连接数
SHOW VARIABLES LIKE 'max_connections';
-- 默认 151，生产环境通常设 500-1000

-- 当前连接数
SHOW GLOBAL STATUS LIKE 'Threads_connected';

-- 历史最大连接数
SHOW GLOBAL STATUS LIKE 'Max_used_connections';
```

### minimumIdle 建议

HikariCP 作者**明确建议** `minimumIdle = maximumPoolSize`（即固定大小连接池）：

```yaml
# 推荐：固定大小连接池
spring:
  datasource:
    hikari:
      minimum-idle: 20
      maximum-pool-size: 20
```

原因：
1. 动态调整连接数有额外开销（创建/销毁连接）
2. 突发流量时创建连接需要时间，可能来不及
3. 固定连接池行为更可预测

### maxLifetime 设置

```yaml
# maxLifetime 必须小于数据库的 wait_timeout
# MySQL 默认 wait_timeout = 28800（8 小时）
# HikariCP 建议 maxLifetime = wait_timeout - 30s（至少减 30 秒）

spring:
  datasource:
    hikari:
      max-lifetime: 1770000     # 29.5 分钟（如果 MySQL wait_timeout=1800）
```

**为什么不能设太长**：数据库或中间的防火墙/LB 可能会静默关闭空闲连接。应用拿到一个已经被服务端关闭的连接，执行 SQL 会报错。

---

## 三、pgbouncer（PostgreSQL 连接池）

PostgreSQL 的连接模型是 "一个连接一个进程"（fork 模式），每个连接消耗 5-10MB 内存。**当连接数超过几百个时，PG 性能会急剧下降**。pgbouncer 是 PG 生态中最常用的连接池代理。

### 安装与配置

```bash
# 安装
apt-get install pgbouncer    # Debian/Ubuntu
yum install pgbouncer        # CentOS/RHEL

# 配置文件 /etc/pgbouncer/pgbouncer.ini
```

```ini
[databases]
perfshop = host=127.0.0.1 port=5432 dbname=perfshop

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt

# 连接池模式
pool_mode = transaction          # session / transaction / statement

# 连接数限制
max_client_conn = 1000           # 客户端最大连接数
default_pool_size = 25           # 每个用户+数据库组合的连接数
min_pool_size = 5                # 最小连接数
reserve_pool_size = 5            # 预留池大小（应对突发）
reserve_pool_timeout = 3         # 使用预留池前等待的秒数

# 超时设置
server_idle_timeout = 600        # 服务端空闲连接超时（秒）
client_idle_timeout = 0          # 客户端空闲超时（0=不限制）
query_timeout = 0                # 查询超时（0=不限制）
query_wait_timeout = 120         # 等待可用连接的超时（秒）

# 日志
log_connections = 1
log_disconnections = 1
log_pooler_errors = 1
stats_period = 60                # 统计输出间隔（秒）
```

### pool_mode 选择

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| session | 连接绑定到客户端会话 | 兼容性最好，但复用率最低 |
| transaction | 事务结束后连接归还池 | **推荐**，复用率高 |
| statement | 每条语句后归还 | 复用率最高，但不支持多语句事务 |

**注意**：`transaction` 模式下，以下功能不能使用：
- SET 命令（会影响下一个使用该连接的客户端）
- PREPARE / DEALLOCATE（预备语句绑定到连接）
- LISTEN / NOTIFY
- LOAD 语句
- WITH HOLD 游标

### pgbouncer 管理命令

```bash
# 连接到 pgbouncer 管理接口
psql -h 127.0.0.1 -p 6432 -U pgbouncer pgbouncer

# 查看连接池状态
SHOW POOLS;
# database | user | cl_active | cl_waiting | sv_active | sv_idle | sv_used | sv_tested | sv_login | maxwait
# perfshop | app  | 15        | 0          | 15        | 10      | 0       | 0         | 0        | 0

# 查看连接统计
SHOW STATS;

# 查看当前客户端连接
SHOW CLIENTS;

# 查看服务端连接
SHOW SERVERS;

# 重新加载配置
RELOAD;
```

### pgbouncer 关键指标

| 指标 | 含义 | 告警阈值 |
|------|------|---------|
| cl_active | 活跃客户端连接 | 接近 max_client_conn |
| cl_waiting | 等待中的客户端 | > 0 持续时间 > 5s |
| sv_active | 活跃服务端连接 | 接近 default_pool_size |
| sv_idle | 空闲服务端连接 | 持续为 0 表示连接不够 |
| maxwait | 最长等待时间（秒） | > 1s |
| avg_query | 平均查询时间（微秒） | 突增需关注 |

---

## 四、连接泄漏排查

### 什么是连接泄漏

获取连接后没有归还（忘了 close），连接池中的可用连接逐渐减少，最终所有线程都在等待获取连接。

### HikariCP 泄漏检测

```yaml
spring:
  datasource:
    hikari:
      leak-detection-threshold: 30000   # 30 秒
      # 如果一个连接被借出超过 30 秒还没归还，打印警告日志（含堆栈）
```

泄漏检测日志示例：

```
WARN  HikariPool-1 - Connection leak detection triggered for
  com.mysql.cj.jdbc.ConnectionImpl@3a7b5e1a on thread http-nio-8080-exec-5,
  stack trace follows
java.lang.Exception: Apparent connection leak detected
  at com.zaxxer.hikari.HikariDataSource.getConnection(HikariDataSource.java:128)
  at com.perfshop.service.OrderService.processOrder(OrderService.java:45)
  at com.perfshop.controller.OrderController.create(OrderController.java:30)
  ...
```

### 常见泄漏代码模式

```java
// ❌ 错误：异常时连接不会归还
public void badCode() {
    Connection conn = dataSource.getConnection();
    Statement stmt = conn.createStatement();
    ResultSet rs = stmt.executeQuery("SELECT * FROM products");
    // 如果这里抛异常，conn 永远不会 close
    process(rs);
    conn.close();
}

// ✅ 正确：try-with-resources 自动关闭
public void goodCode() {
    try (Connection conn = dataSource.getConnection();
         Statement stmt = conn.createStatement();
         ResultSet rs = stmt.executeQuery("SELECT * FROM products")) {
        process(rs);
    }  // 自动 close，即使发生异常
}

// ❌ 错误：Spring 中手动获取连接但没归还
@Service
public class BadService {
    @Autowired
    DataSource dataSource;

    public void doWork() {
        Connection conn = DataSourceUtils.getConnection(dataSource);
        // 做了一些操作...
        // 忘了调 DataSourceUtils.releaseConnection(conn, dataSource);
    }
}

// ✅ 正确：使用 JdbcTemplate 或 @Transactional
@Service
public class GoodService {
    @Autowired
    JdbcTemplate jdbcTemplate;

    public List<Product> findProducts() {
        return jdbcTemplate.query("SELECT * FROM products", rowMapper);
    }
}
```

### 排查连接泄漏的步骤

```bash
# 1. 看连接池指标：活跃连接数持续增长不回落
# 2. 看数据库端连接数
mysql -e "SHOW PROCESSLIST;" | grep -c "Sleep"
# Sleep 状态的连接越来越多

# 3. 开启泄漏检测看堆栈
# 4. 检查代码中的 getConnection() 调用
grep -rn "getConnection\|DataSourceUtils.getConnection" src/main/java/
# 确保都有对应的 close
```

---

## 五、慢连接检测

### 获取连接耗时监控

```java
// HikariCP 自带 JMX 指标
// 通过 Spring Boot Actuator 暴露

// application.yml
spring:
  datasource:
    hikari:
      register-mbeans: true    # 注册 JMX MBeans

management:
  endpoints:
    web:
      exposure:
        include: health,metrics,prometheus
```

```bash
# 通过 Actuator 查看连接池指标
curl http://localhost:8080/actuator/metrics/hikaricp.connections.acquire
# {
#   "name": "hikaricp.connections.acquire",
#   "measurements": [
#     { "statistic": "COUNT", "value": 15234 },
#     { "statistic": "TOTAL_TIME", "value": 12.345 },
#     { "statistic": "MAX", "value": 0.892 }
#   ]
# }
```

### 连接获取超时排查

```
# 典型错误日志
SQLTransientConnectionException: PerfShop-HikariPool -
  Connection is not available, request timed out after 3000ms.

# 排查思路：
# 1. 连接池满了吗？→ 看 maximumPoolSize 和 active connections
# 2. 有连接泄漏吗？→ 看 leak detection 日志
# 3. 查询太慢占住了连接？→ 看慢查询日志
# 4. 数据库端连接数满了吗？→ SHOW VARIABLES LIKE 'max_connections'
# 5. 网络问题？→ ping 数据库、检查 DNS 解析时间
```

---

## 六、监控指标

### HikariCP 核心指标

| 指标 | Micrometer 名称 | 含义 | 告警阈值 |
|------|-----------------|------|---------|
| 活跃连接 | `hikaricp.connections.active` | 正在使用的连接 | > 80% maximumPoolSize |
| 空闲连接 | `hikaricp.connections.idle` | 空闲可用连接 | < 2 |
| 等待线程 | `hikaricp.connections.pending` | 等待获取连接的线程数 | > 0 持续 > 5s |
| 总连接 | `hikaricp.connections` | 连接池中总连接数 | 偏离 maximumPoolSize |
| 获取时间 | `hikaricp.connections.acquire` | 获取连接耗时 | p99 > 100ms |
| 使用时间 | `hikaricp.connections.usage` | 连接使用时长 | p99 > 10s |
| 创建时间 | `hikaricp.connections.creation` | 创建新连接耗时 | > 1s |
| 超时次数 | `hikaricp.connections.timeout` | 获取连接超时次数 | > 0 |

### 数据库端监控

```sql
-- MySQL 连接状态
SHOW GLOBAL STATUS LIKE 'Threads%';
-- Threads_connected: 当前连接数
-- Threads_running: 正在执行查询的线程数
-- Threads_created: 已创建的线程总数
-- Threads_cached: 缓存的线程数

-- 连接使用率 = Threads_connected / max_connections
-- 正常 < 80%

-- 终止连接数（连接被异常断开的次数）
SHOW GLOBAL STATUS LIKE 'Aborted%';
-- Aborted_clients: 客户端异常断开（超时、被杀等）
-- Aborted_connects: 连接尝试失败（认证失败、达到限制等）
```

```sql
-- PostgreSQL 连接状态
SELECT
    count(*) AS total_connections,
    count(*) FILTER (WHERE state = 'active') AS active,
    count(*) FILTER (WHERE state = 'idle') AS idle,
    count(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_transaction,
    count(*) FILTER (WHERE wait_event_type = 'Lock') AS waiting_for_lock
FROM pg_stat_activity
WHERE backend_type = 'client backend';

-- 连接使用率
SELECT
    numbackends AS current_connections,
    (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max_connections,
    round(100.0 * numbackends / (SELECT setting::int FROM pg_settings WHERE name = 'max_connections'), 1) AS usage_pct
FROM pg_stat_database
WHERE datname = current_database();
```

---

## 七、Prometheus + Grafana 连接池监控

### Prometheus 指标采集

```yaml
# Spring Boot Actuator + Micrometer 自动暴露指标
# application.yml
management:
  metrics:
    export:
      prometheus:
        enabled: true
    tags:
      application: perfshop
  endpoint:
    prometheus:
      enabled: true
```

```bash
# 验证指标输出
curl http://localhost:8080/actuator/prometheus | grep hikaricp

# 输出示例：
# hikaricp_connections_active{pool="PerfShop-HikariPool",} 5.0
# hikaricp_connections_idle{pool="PerfShop-HikariPool",} 15.0
# hikaricp_connections{pool="PerfShop-HikariPool",} 20.0
# hikaricp_connections_pending{pool="PerfShop-HikariPool",} 0.0
# hikaricp_connections_timeout_total{pool="PerfShop-HikariPool",} 0.0
# hikaricp_connections_acquire_seconds_max{pool="PerfShop-HikariPool",} 0.001234
# hikaricp_connections_usage_seconds_max{pool="PerfShop-HikariPool",} 0.05678
```

### Prometheus 配置

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'perfshop'
    metrics_path: '/actuator/prometheus'
    scrape_interval: 15s
    static_configs:
      - targets: ['perfshop-app:8080']
```

### Grafana Dashboard 关键面板

```
面板 1：连接池使用率
  Query: hikaricp_connections_active / hikaricp_connections * 100
  告警：> 80% 持续 5 分钟

面板 2：等待线程数
  Query: hikaricp_connections_pending
  告警：> 0 持续 30 秒

面板 3：获取连接耗时（p99）
  Query: histogram_quantile(0.99, rate(hikaricp_connections_acquire_seconds_bucket[5m]))
  告警：> 100ms

面板 4：连接超时次数
  Query: rate(hikaricp_connections_timeout_total[5m])
  告警：> 0

面板 5：连接使用时长（p99）
  Query: histogram_quantile(0.99, rate(hikaricp_connections_usage_seconds_bucket[5m]))
  告警：> 30s（可能有长事务或泄漏）

面板 6：数据库端连接数
  Query: mysql_global_status_threads_connected
  告警：> max_connections * 0.8
```

### Grafana 告警规则示例

```yaml
# alerting rules
groups:
  - name: connection_pool
    rules:
      - alert: ConnectionPoolExhausted
        expr: hikaricp_connections_active / hikaricp_connections > 0.9
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "连接池即将耗尽 ({{ $labels.pool }})"
          description: "活跃连接占比 {{ $value | humanizePercentage }}，持续超过 2 分钟"

      - alert: ConnectionAcquireSlow
        expr: histogram_quantile(0.99, rate(hikaricp_connections_acquire_seconds_bucket[5m])) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "获取连接耗时过长 ({{ $labels.pool }})"

      - alert: ConnectionLeakSuspected
        expr: hikaricp_connections_pending > 0 and hikaricp_connections_idle == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "疑似连接泄漏 ({{ $labels.pool }})"
          description: "有线程等待连接但无空闲连接"
```

---

## 八、连接池问题排查清单

| 步骤 | 检查项 | 命令/工具 |
|------|--------|----------|
| 1 | 应用报连接超时？ | 看日志中 `Connection is not available` |
| 2 | 连接池满了？ | 检查 `hikaricp_connections_active` |
| 3 | 有连接泄漏？ | 看 `leak-detection-threshold` 日志 |
| 4 | 慢查询占住连接？ | 查慢查询日志 |
| 5 | 长事务占住连接？ | `information_schema.innodb_trx` |
| 6 | 数据库连接数满？ | `SHOW VARIABLES LIKE 'max_connections'` |
| 7 | 网络到数据库通？ | `telnet db-host 3306` |
| 8 | maximumPoolSize 合理？ | 公式：`(CPU核数*2) + 磁盘数` |
| 9 | maxLifetime 合理？ | 必须小于数据库 `wait_timeout` |
| 10 | 监控覆盖了？ | Prometheus + Grafana 面板 |
