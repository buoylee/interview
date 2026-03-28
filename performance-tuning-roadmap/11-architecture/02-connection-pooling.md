# 连接池调优

数据库连接的创建开销极大：TCP 三次握手、TLS 协商、身份认证、会话初始化，一次建连可能耗费 20-100ms。连接池通过预创建和复用连接来消除这个开销。然而连接池配置不当（过大浪费资源引发锁竞争、过小成为瓶颈导致请求排队）同样会严重影响性能。本文覆盖主流连接池的深度配置与调优方法论。

---

## 一、连接池核心原理

### 1.1 工作流程

```
应用线程请求连接
    ↓
连接池中有空闲连接？──→ 是 → 分配连接给线程
    ↓ 否
当前连接数 < maxPoolSize？──→ 是 → 创建新连接
    ↓ 否
等待（最多 connectionTimeout 时长）
    ↓ 超时
抛出异常（连接池耗尽）
```

### 1.2 连接池大小公式

**经验公式**：

```
pool_size = CPU核数 * (1 + 等待时间/计算时间)
```

- **CPU 密集型**（等待时间 ≈ 0）：pool_size ≈ CPU 核数
- **IO 密集型**（等待时间 >> 计算时间）：pool_size 可以更大

**PostgreSQL 官方建议**：

```
connections = ((core_count * 2) + effective_spindle_count)
```

例如 4 核 CPU + 1 块 SSD：`(4 * 2) + 1 = 9`

**关键原则**：连接池不是越大越好。过大的连接池会导致：
- 数据库端上下文切换开销增大
- 锁竞争加剧
- 内存占用增加
- 实测表明：50 个连接的吞吐量可能低于 10 个连接

---

## 二、HikariCP 深度配置

HikariCP 是 Spring Boot 默认连接池，以高性能著称。

### 2.1 核心参数

```yaml
spring:
  datasource:
    hikari:
      # === 池大小 ===
      maximum-pool-size: 10          # 最大连接数（公式计算 + 压测验证）
      minimum-idle: 10               # 最小空闲连接（建议等于 max，固定池大小）

      # === 超时设置 ===
      connection-timeout: 3000       # 获取连接最大等待时间（ms），默认 30s 太长
      idle-timeout: 600000           # 空闲连接最大存活时间（ms），10分钟
      max-lifetime: 1800000          # 连接最大存活时间（ms），30分钟
                                     # 必须比 DB 的 wait_timeout 短几秒
      validation-timeout: 3000       # 连接有效性检测超时（ms）

      # === 泄漏检测 ===
      leak-detection-threshold: 30000  # 连接泄漏检测阈值（ms），开发环境设 5000

      # === 连接测试 ===
      connection-test-query: SELECT 1  # MySQL 5.x 用这个
      # MySQL 8.x + JDBC 4.x 可省略，HikariCP 自动用 isValid()
```

### 2.2 参数详解

**maximum-pool-size**：

```java
// 不要盲目设大！先用公式估算，再压测验证
// 4 核服务器，IO 密集型业务
// pool_size = 4 * (1 + 10ms_IO / 2ms_CPU) = 4 * 6 = 24
// 实际从 10 开始压测，逐步增加直到吞吐量不再提升

// 错误做法（常见于生产事故）：
maximum-pool-size: 200  // 数据库被打死
// 正确做法：
maximum-pool-size: 10   // 从小开始
```

**minimum-idle vs maximum-pool-size**：

```yaml
# 推荐：设为相同值（固定池大小）
# 原因：避免连接创建/销毁的抖动
minimum-idle: 10
maximum-pool-size: 10

# 不推荐：动态池（除非流量波动非常大）
minimum-idle: 2
maximum-pool-size: 20
```

**max-lifetime**：

```bash
# 查看 MySQL 的 wait_timeout
mysql> SHOW VARIABLES LIKE 'wait_timeout';
# 通常为 28800 (8小时)

# HikariCP 的 max-lifetime 必须比它短
# 建议设为 MySQL wait_timeout 的一半或更短
max-lifetime: 1800000  # 30 分钟
```

### 2.3 HikariCP 监控

```java
@Configuration
public class HikariMetricsConfig {

    @Bean
    public HikariDataSource dataSource(DataSourceProperties properties) {
        HikariDataSource ds = properties.initializeDataSourceBuilder()
            .type(HikariDataSource.class).build();

        // 注册 Prometheus 指标
        ds.setMetricRegistry(new PrometheusMetricsTrackerFactory());

        return ds;
    }
}

// 关键指标
// hikaricp_connections_active    - 活跃连接数
// hikaricp_connections_idle      - 空闲连接数
// hikaricp_connections_pending   - 等待获取连接的线程数（> 0 说明池太小）
// hikaricp_connections_timeout   - 获取连接超时次数（> 0 立即告警）
```

---

## 三、OkHttp 连接池

### 3.1 配置

```java
OkHttpClient client = new OkHttpClient.Builder()
    .connectionPool(new ConnectionPool(
        20,                         // maxIdleConnections: 最大空闲连接数
        5, TimeUnit.MINUTES         // keepAliveDuration: 空闲连接存活时间
    ))
    .connectTimeout(3, TimeUnit.SECONDS)
    .readTimeout(10, TimeUnit.SECONDS)
    .writeTimeout(10, TimeUnit.SECONDS)
    .retryOnConnectionFailure(true)
    .build();

// 关键：OkHttpClient 应该是单例，全局共享
// 错误做法：每次请求创建 new OkHttpClient()
```

### 3.2 调优要点

```java
// 1. 全局单例
@Bean
public OkHttpClient okHttpClient() {
    return new OkHttpClient.Builder()
        .connectionPool(new ConnectionPool(50, 5, TimeUnit.MINUTES))
        .dispatcher(new Dispatcher(executorService)) // 自定义线程池
        .build();
}

// 2. 针对不同后端服务用不同配置
OkHttpClient fastServiceClient = baseClient.newBuilder()
    .readTimeout(3, TimeUnit.SECONDS) // 快服务用短超时
    .build(); // 共享连接池

OkHttpClient slowServiceClient = baseClient.newBuilder()
    .readTimeout(30, TimeUnit.SECONDS) // 慢服务用长超时
    .build(); // 共享连接池
```

---

## 四、Redis 连接池：Jedis vs Lettuce

### 4.1 对比

| 特性 | Jedis | Lettuce |
|------|-------|---------|
| IO 模型 | 阻塞 IO | 基于 Netty 的非阻塞 IO |
| 线程安全 | 连接非线程安全，需要连接池 | 连接线程安全，可共享 |
| 连接池 | 必须使用 JedisPool | 可选（多数场景不需要） |
| 性能 | 适中 | 高（多路复用） |
| Spring Boot 默认 | 2.x 之前 | 2.x 之后 |
| 适用场景 | 简单场景 | 高并发/响应式 |

### 4.2 Jedis 连接池配置

```java
JedisPoolConfig poolConfig = new JedisPoolConfig();
poolConfig.setMaxTotal(50);          // 最大连接数
poolConfig.setMaxIdle(20);           // 最大空闲连接
poolConfig.setMinIdle(5);            // 最小空闲连接
poolConfig.setMaxWaitMillis(3000);   // 获取连接最大等待时间
poolConfig.setTestOnBorrow(true);    // 获取连接时检测有效性
poolConfig.setTestWhileIdle(true);   // 空闲时检测
poolConfig.setTimeBetweenEvictionRunsMillis(30000); // 检测间隔

JedisPool pool = new JedisPool(poolConfig, "redis-host", 6379, 3000, "password");

// 使用（必须归还连接！）
try (Jedis jedis = pool.getResource()) {
    jedis.set("key", "value");
}
```

### 4.3 Lettuce 配置

```yaml
spring:
  redis:
    host: redis-host
    port: 6379
    lettuce:
      pool:
        enabled: true                # 非必须，Lettuce 单连接也够用
        max-active: 20               # 最大活跃连接
        max-idle: 10                 # 最大空闲
        min-idle: 5                  # 最小空闲
        max-wait: 3000ms             # 最大等待时间
      shutdown-timeout: 5000ms
```

```java
// Lettuce 高级配置：连接池 + 读写分离
@Bean
public LettuceConnectionFactory lettuceConnectionFactory() {
    LettuceClientConfiguration clientConfig = LettuceClientConfiguration.builder()
        .readFrom(ReadFrom.REPLICA_PREFERRED)  // 读优先走从库
        .commandTimeout(Duration.ofSeconds(3))
        .build();

    RedisStandaloneConfiguration serverConfig = new RedisStandaloneConfiguration();
    serverConfig.setHostName("redis-host");
    serverConfig.setPort(6379);

    return new LettuceConnectionFactory(serverConfig, clientConfig);
}
```

---

## 五、连接池大小实战计算

### 5.1 数据库连接池

```
场景：4 核 CPU 服务器，每个请求：
  - CPU 计算 2ms
  - 数据库 IO 等待 18ms（1 次查询 + 1 次更新）

pool_size = 4 * (1 + 18/2) = 40

考虑到有 3 个服务实例，数据库 max_connections = 200：
每个实例分配 = 200 / 3 ≈ 60（留余量给管理连接）
实际设置 = min(40, 60) = 40
```

### 5.2 HTTP 连接池

```
场景：调用下游服务
  - 平均 RT 50ms
  - 峰值 QPS 2000/s
  - 最大并发 = QPS * RT = 2000 * 0.05 = 100

建议 maxTotal = 100 ~ 150（留 50% 余量）
```

### 5.3 验证方法

```bash
# 压测期间监控连接池指标
# 如果 pending > 0（有线程在等连接），说明池太小
# 如果 idle > max/2（大量空闲），说明池太大

# MySQL 端查看连接数
mysql> SHOW STATUS LIKE 'Threads_connected';
mysql> SHOW PROCESSLIST;
```

---

## 六、连接泄漏排查

### 6.1 常见泄漏原因

```java
// 原因 1：忘记关闭连接
Connection conn = dataSource.getConnection();
Statement stmt = conn.createStatement();
ResultSet rs = stmt.executeQuery("SELECT ...");
// 没有 finally 关闭！异常时连接泄漏

// 正确做法：try-with-resources
try (Connection conn = dataSource.getConnection();
     PreparedStatement stmt = conn.prepareStatement(sql);
     ResultSet rs = stmt.executeQuery()) {
    // 处理结果
}

// 原因 2：事务未提交/回滚
@Transactional
public void process() {
    // 抛出非 RuntimeException 时事务不回滚
    // 连接不会归还到池中
    throw new IOException("fail"); // 不会触发回滚！
}

// 正确做法：
@Transactional(rollbackFor = Exception.class)
public void process() throws Exception {
    // ...
}

// 原因 3：长事务占用连接
@Transactional
public void exportReport() {
    List<Data> data = repository.findAll(); // 大查询
    generateExcel(data);                     // 耗时操作
    sendEmail(report);                       // 外部调用
    // 整个方法执行期间一直占用一个连接！
}
```

### 6.2 泄漏检测工具

```yaml
# HikariCP 泄漏检测
spring:
  datasource:
    hikari:
      leak-detection-threshold: 5000  # 5秒未归还就打印堆栈
```

泄漏日志输出：

```
WARN  HikariPool - Connection leak detection triggered for conn0,
      stack trace follows
java.lang.Exception: Apparent connection leak detected
    at com.example.UserService.getUser(UserService.java:42)
    at com.example.UserController.query(UserController.java:25)
```

### 6.3 排查清单

```bash
# 1. 检查活跃连接数是否持续增长
watch -n 1 "mysql -e \"SHOW STATUS LIKE 'Threads_connected'\""

# 2. 查看长时间运行的连接
mysql -e "SELECT * FROM information_schema.processlist WHERE TIME > 60"

# 3. 检查应用端连接池指标
curl http://localhost:8080/actuator/metrics/hikaricp.connections.active
curl http://localhost:8080/actuator/metrics/hikaricp.connections.pending
```

---

## 七、Go 的 sql.DB 连接池

```go
import (
    "database/sql"
    _ "github.com/go-sql-driver/mysql"
    "time"
)

func initDB() *sql.DB {
    db, err := sql.Open("mysql", "user:pass@tcp(host:3306)/dbname")
    if err != nil {
        log.Fatal(err)
    }

    // 连接池配置
    db.SetMaxOpenConns(25)                  // 最大打开连接数
    db.SetMaxIdleConns(25)                  // 最大空闲连接数（建议等于 MaxOpen）
    db.SetConnMaxLifetime(30 * time.Minute) // 连接最大存活时间
    db.SetConnMaxIdleTime(10 * time.Minute) // 空闲连接最大存活时间（Go 1.15+）

    // 验证连接
    if err := db.Ping(); err != nil {
        log.Fatal(err)
    }

    return db
}

// 监控
func monitorDB(db *sql.DB) {
    ticker := time.NewTicker(30 * time.Second)
    for range ticker.C {
        stats := db.Stats()
        log.Printf(
            "OpenConns=%d InUse=%d Idle=%d WaitCount=%d WaitDuration=%v",
            stats.OpenConnections,
            stats.InUse,
            stats.Idle,
            stats.WaitCount,       // 等待连接的总次数
            stats.WaitDuration,    // 等待连接的总时长
        )
    }
}
```

**Go 连接池的坑**：

```go
// 坑 1：忘记关闭 Rows
rows, err := db.Query("SELECT ...")
// 必须关闭！否则连接不归还
defer rows.Close()
for rows.Next() { ... }

// 坑 2：QueryRow 不需要关闭，但 Scan 必须调用
var name string
err := db.QueryRow("SELECT name WHERE id = ?", 1).Scan(&name)
// 如果不调用 Scan，连接也会正常归还，但 err 会丢失

// 坑 3：事务中的连接
tx, _ := db.Begin()
// tx 占用一个连接直到 Commit 或 Rollback
defer tx.Rollback() // 确保异常时释放
```

---

## 八、Python SQLAlchemy 连接池

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    "mysql+pymysql://user:pass@host:3306/dbname",

    # 连接池配置
    pool_size=10,              # 核心连接数
    max_overflow=20,           # 允许超出 pool_size 的临时连接数
                               # 总最大连接 = pool_size + max_overflow = 30
    pool_timeout=3,            # 获取连接超时（秒）
    pool_recycle=1800,         # 连接回收时间（秒），防止 MySQL wait_timeout
    pool_pre_ping=True,        # 使用前 ping 检测连接有效性

    poolclass=QueuePool,       # 默认连接池实现

    echo_pool="debug",        # 开发环境：打印连接池日志
)

# 异步连接池（asyncio 场景）
from sqlalchemy.ext.asyncio import create_async_engine

async_engine = create_async_engine(
    "mysql+aiomysql://user:pass@host:3306/dbname",
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
)
```

### 监控

```python
from sqlalchemy import event

# 连接获取耗时监控
@event.listens_for(engine, "checkout")
def checkout_listener(dbapi_conn, connection_rec, connection_proxy):
    connection_rec.info["checkout_time"] = time.time()

@event.listens_for(engine, "checkin")
def checkin_listener(dbapi_conn, connection_rec):
    checkout_time = connection_rec.info.get("checkout_time")
    if checkout_time:
        duration = time.time() - checkout_time
        if duration > 5:  # 连接持有超过 5 秒
            logger.warning(f"连接持有时间过长: {duration:.2f}s")

# 获取连接池状态
pool = engine.pool
print(f"Pool size: {pool.size()}")
print(f"Checked out: {pool.checkedout()}")
print(f"Overflow: {pool.overflow()}")
```

---

## 九、连接池调优速查表

| 参数 | HikariCP | Go sql.DB | SQLAlchemy | 建议值 |
|------|----------|-----------|------------|--------|
| 最大连接数 | maximumPoolSize | MaxOpenConns | pool_size + max_overflow | CPU*(1+W/C) |
| 最小空闲 | minimumIdle | MaxIdleConns | pool_size | = 最大连接数 |
| 获取超时 | connectionTimeout | 无（阻塞） | pool_timeout | 3-5 秒 |
| 空闲超时 | idleTimeout | ConnMaxIdleTime | 无 | 10 分钟 |
| 最大存活 | maxLifetime | ConnMaxLifetime | pool_recycle | < DB wait_timeout |
| 泄漏检测 | leakDetectionThreshold | 无 | 自定义 event | 开发 5s/生产 30s |
| 有效性检测 | connectionTestQuery | Ping() | pool_pre_ping | 开启 |

### 排查流程

```
连接池相关问题排查：
    ↓
1. 获取连接超时？
   → 检查 active 连接数是否达到 max
   → 是：增大池或优化 SQL 减少连接持有时间
   → 否：检查 DB 是否可达
    ↓
2. 连接数持续增长不下降？
   → 开启 leakDetectionThreshold
   → 检查是否有未关闭的连接/未结束的事务
    ↓
3. 连接被数据库断开？
   → 检查 maxLifetime < DB wait_timeout
   → 开启 pool_pre_ping / testOnBorrow
    ↓
4. 性能未提升反而下降？
   → 池太大导致 DB 端锁竞争
   → 从小池开始压测，找到最佳值
```
