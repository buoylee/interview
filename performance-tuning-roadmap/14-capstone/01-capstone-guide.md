# 贯穿项目演练指南

## 为什么需要完整的演练项目

学了十几个阶段的理论和工具，最终能不能在生产环境中快速定位和解决问题，取决于你有没有把这些知识串联起来做过真实的端到端练习。PerfShop 就是为此设计的——一个包含 Java、Go、Python 三语言服务的微服务电商系统，内置了可以按需激活的各类性能问题。本指南将带你完成从环境准备到问题注入、排查、修复、验证的全流程。

---

## 一、PerfShop 架构回顾

### 1.1 整体架构

```
                    ┌─────────────┐
                    │   Nginx     │
                    │  (Gateway)  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
      ┌───────▼──────┐ ┌──▼──────────┐ ┌▼─────────────┐
      │ Java Service │ │ Go Service  │ │Python Service │
      │ (Order/Pay)  │ │ (Product/   │ │ (Recommend/   │
      │  Spring Boot │ │  Inventory) │ │  Analytics)   │
      └───────┬──────┘ └──┬──────────┘ └┬─────────────┘
              │            │             │
      ┌───────▼────────────▼─────────────▼──┐
      │          MySQL / Redis / Kafka       │
      └─────────────────────────────────────┘
```

### 1.2 核心服务职责

| 服务 | 语言 | 端口 | 职责 |
|------|------|------|------|
| order-service | Java (Spring Boot) | 8080 | 订单创建、支付处理 |
| product-service | Go (Gin) | 8081 | 商品查询、库存管理 |
| recommend-service | Python (FastAPI) | 8082 | 推荐算法、数据分析 |
| MySQL | - | 3306 | 订单/商品持久化 |
| Redis | - | 6379 | 缓存、Session、分布式锁 |
| Kafka | - | 9092 | 异步消息（订单事件） |

### 1.3 监控栈

| 组件 | 端口 | 用途 |
|------|------|------|
| Prometheus | 9090 | 指标采集 |
| Grafana | 3000 | 仪表盘展示 |
| Jaeger | 16686 | 分布式链路追踪 |
| Alertmanager | 9093 | 告警管理 |
| cAdvisor | 8088 | 容器指标 |

---

## 二、演练环境准备

### 2.1 启动全部服务

```bash
# 克隆项目
git clone https://github.com/your-org/perfshop.git
cd perfshop

# 一键启动（包含监控栈）
docker-compose -f docker-compose.yml \
               -f docker-compose.monitoring.yml \
               up -d

# 确认所有容器正常
docker-compose ps
```

### 2.2 环境健康检查清单

在开始演练前，逐项确认：

```bash
#!/bin/bash
# health-check.sh — 演练前环境检查脚本

echo "=== 1. 服务健康检查 ==="
curl -s http://localhost:8080/actuator/health | jq .status
curl -s http://localhost:8081/health | jq .status
curl -s http://localhost:8082/health | jq .status

echo "=== 2. 数据库连接 ==="
mysql -h 127.0.0.1 -u perfshop -p'perfshop' -e "SELECT 1" perfshop_db

echo "=== 3. Redis 连接 ==="
redis-cli -h 127.0.0.1 ping

echo "=== 4. Kafka 连接 ==="
kafka-topics.sh --bootstrap-server localhost:9092 --list

echo "=== 5. 监控栈 ==="
curl -s http://localhost:9090/-/healthy && echo "Prometheus OK"
curl -s http://localhost:3000/api/health | jq .
curl -s http://localhost:16686/ > /dev/null && echo "Jaeger OK"

echo "=== 6. 基准数据 ==="
curl -s http://localhost:8081/api/products | jq '. | length'
echo "products in DB"
```

### 2.3 初始化测试数据

```bash
# 导入基准商品数据（1000 个商品）
curl -X POST http://localhost:8081/admin/seed?count=1000

# 创建测试用户
curl -X POST http://localhost:8080/admin/users/seed?count=100

# 验证数据
curl -s http://localhost:8081/api/products/count
# 应输出: {"count": 1000}
```

### 2.4 确认 Grafana 仪表盘可用

登录 Grafana（admin/admin），确认以下仪表盘已导入：

- **JVM Overview** — Java 服务的 Heap、GC、线程
- **Go Runtime** — Go 服务的 goroutine、GC、内存
- **Python Runtime** — Python 服务的请求延迟、内存
- **MySQL Overview** — 查询 QPS、慢查询、连接数
- **Redis Overview** — 命中率、内存、大 Key
- **Node Exporter** — 主机 CPU、内存、磁盘、网络

---

## 三、问题注入方法

PerfShop 提供两种注入方式：**API 动态注入**和**代码修改注入**。

### 3.1 API 动态注入（推荐用于演练）

```bash
# 注入 GC 压力（Java 服务）
curl -X POST http://localhost:8080/chaos/gc-pressure \
  -d '{"allocSizeMB": 50, "intervalMs": 100, "durationSec": 300}'

# 注入慢查询（禁用查询缓存 + 触发全表扫描）
curl -X POST http://localhost:8080/chaos/slow-query \
  -d '{"dropIndex": "idx_order_user_id", "durationSec": 300}'

# 注入内存泄漏（Java 服务）
curl -X POST http://localhost:8080/chaos/memory-leak \
  -d '{"leakRateMBPerMin": 10, "durationSec": 600}'

# 注入 goroutine 泄漏（Go 服务）
curl -X POST http://localhost:8081/chaos/goroutine-leak \
  -d '{"leakRatePerSec": 5, "durationSec": 300}'

# 注入连接池耗尽（Java 服务）
curl -X POST http://localhost:8080/chaos/connection-exhaust \
  -d '{"holdConnSec": 30, "concurrency": 50}'

# 注入超时传播（Go → Java 调用链路变慢）
curl -X POST http://localhost:8081/chaos/slow-downstream \
  -d '{"targetService": "order-service", "delayMs": 3000, "durationSec": 300}'
```

### 3.2 代码修改注入

#### GC 问题注入（Java）

```java
// order-service/src/main/java/com/perfshop/chaos/GcPressure.java
@Component
public class GcPressure {
    private final List<byte[]> leakyList = new ArrayList<>();

    // 激活后，每 100ms 分配 50MB，触发频繁 Full GC
    @Scheduled(fixedRate = 100)
    public void allocateLargeObjects() {
        if (!chaosEnabled) return;
        byte[] chunk = new byte[50 * 1024 * 1024]; // 50MB
        leakyList.add(chunk);
        // 保留最近 20 个，模拟长生命周期对象晋升到老年代
        if (leakyList.size() > 20) {
            leakyList.remove(0);
        }
    }
}
```

#### 慢查询注入（MySQL）

```sql
-- 删除关键索引，让查询退化为全表扫描
ALTER TABLE orders DROP INDEX idx_order_user_id;
ALTER TABLE order_items DROP INDEX idx_item_order_id;

-- 注入大量数据让全表扫描更痛
INSERT INTO orders (user_id, status, total_amount, created_at)
SELECT FLOOR(RAND() * 10000),
       ELT(FLOOR(RAND() * 3) + 1, 'PENDING', 'PAID', 'SHIPPED'),
       RAND() * 1000,
       DATE_SUB(NOW(), INTERVAL FLOOR(RAND() * 365) DAY)
FROM information_schema.tables a, information_schema.tables b
LIMIT 500000;
```

#### Goroutine 泄漏注入（Go）

```go
// product-service/internal/chaos/goroutine_leak.go
func LeakGoroutines(ctx context.Context, rate int) {
    ticker := time.NewTicker(time.Second / time.Duration(rate))
    defer ticker.Stop()
    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            go func() {
                // 故意不关闭 resp.Body，goroutine 永远阻塞在 read 上
                resp, err := http.Get("http://order-service:8080/api/orders/1")
                if err != nil {
                    return
                }
                // 注意：没有 defer resp.Body.Close()
                // 这个 goroutine 会一直挂着
                buf := make([]byte, 1024)
                for {
                    _, err := resp.Body.Read(buf)
                    if err != nil {
                        break
                    }
                }
            }()
        }
    }
}
```

#### 连接池耗尽注入（Java）

```java
// 故意长时间持有数据库连接不释放
@Service
public class ConnectionExhaust {
    @Autowired
    private DataSource dataSource;

    public void exhaust(int holdSec, int concurrency) {
        ExecutorService pool = Executors.newFixedThreadPool(concurrency);
        for (int i = 0; i < concurrency; i++) {
            pool.submit(() -> {
                try {
                    Connection conn = dataSource.getConnection();
                    // 持有连接不释放
                    Thread.sleep(holdSec * 1000L);
                    conn.close();
                } catch (Exception e) {
                    log.error("connection exhaust error", e);
                }
            });
        }
    }
}
```

#### 超时传播注入

```go
// 在 Go 服务中注入对下游 Java 服务的调用延迟
func SlowDownstream(targetService string, delayMs int) gin.HandlerFunc {
    return func(c *gin.Context) {
        // 拦截对目标服务的调用，在发起前 sleep
        if strings.Contains(c.Request.URL.Path, "/api/orders") {
            time.Sleep(time.Duration(delayMs) * time.Millisecond)
        }
        c.Next()
    }
}
```

---

## 四、演练阶段清单

### 4.1 阶段一：GC 问题排查

| 步骤 | 操作 | 预期结果 |
|------|------|---------|
| 1 | 注入 GC 压力 | API 接口注入 |
| 2 | 发起持续负载 | `wrk -t4 -c50 -d120s http://localhost:8080/api/orders` |
| 3 | 观察 Grafana | JVM Heap 使用率飙升，Full GC 次数增加 |
| 4 | 查看 GC 日志 | `docker logs order-service 2>&1 \| grep "GC"` |
| 5 | 使用 Arthas 分析 | `dashboard`、`heapdump`、`jmap` |
| 6 | 定位大对象 | MAT 分析 heapdump，找到 leakyList |
| 7 | 修复 | 清除注入代码，调整 GC 参数 |
| 8 | 验证 | 再次负载测试，确认 Full GC 消失 |

### 4.2 阶段二：慢查询排查

| 步骤 | 操作 | 预期结果 |
|------|------|---------|
| 1 | 注入慢查询 | 删除索引 + 注入大量数据 |
| 2 | 发起查询负载 | `wrk -t4 -c20 -d60s http://localhost:8080/api/orders?userId=123` |
| 3 | 观察 Grafana | MySQL 慢查询数飙升，P99 延迟增加 |
| 4 | 查看慢查询日志 | `mysqldumpslow -s t /var/log/mysql/slow.log` |
| 5 | EXPLAIN 分析 | `EXPLAIN SELECT * FROM orders WHERE user_id = 123` |
| 6 | 确认全表扫描 | type=ALL，rows 数十万 |
| 7 | 修复 | 添加索引 |
| 8 | 验证 | EXPLAIN 确认 type=ref，延迟回到正常 |

### 4.3 阶段三：Goroutine 泄漏排查

| 步骤 | 操作 | 预期结果 |
|------|------|---------|
| 1 | 注入 goroutine 泄漏 | API 注入 |
| 2 | 发起负载 | `wrk -t4 -c20 -d120s http://localhost:8081/api/products` |
| 3 | 观察 Grafana | goroutine 数量持续线性增长 |
| 4 | pprof 抓取 | `go tool pprof http://localhost:8081/debug/pprof/goroutine` |
| 5 | 分析堆栈 | `top` 找到泄漏的 goroutine 创建位置 |
| 6 | 定位代码 | 找到未关闭 resp.Body 的代码 |
| 7 | 修复 | 添加 `defer resp.Body.Close()` |
| 8 | 验证 | goroutine 数量稳定，不再增长 |

### 4.4 阶段四：连接池耗尽排查

| 步骤 | 操作 | 预期结果 |
|------|------|---------|
| 1 | 注入连接池耗尽 | API 注入 |
| 2 | 发起正常请求 | 正常业务请求开始报错 |
| 3 | 观察 Grafana | HikariCP active connections 打满 |
| 4 | 查看应用日志 | `Connection is not available, request timed out after 30000ms` |
| 5 | 排查 MySQL | `SHOW PROCESSLIST` 看连接状态 |
| 6 | 定位代码 | 找到长时间持有连接的代码 |
| 7 | 修复 | 修复连接泄漏，调整连接池参数 |
| 8 | 验证 | 连接数恢复正常，请求不再报错 |

### 4.5 阶段五：超时传播排查

| 步骤 | 操作 | 预期结果 |
|------|------|---------|
| 1 | 注入下游延迟 | Go 服务调用 Java 服务延迟 3s |
| 2 | 发起端到端请求 | 下单接口延迟明显增加 |
| 3 | 观察 Jaeger | 链路中 order-service 调用耗时 3s+ |
| 4 | 观察 Grafana | 上游请求排队，goroutine/线程数增加 |
| 5 | 分析超时配置 | 检查各层超时设置是否合理 |
| 6 | 修复 | 添加合理的超时配置和断路器 |
| 7 | 验证 | 下游慢时快速失败，不拖垮上游 |

---

## 五、演练记录模板

每次演练使用以下模板记录过程，便于复盘和评估。

```markdown
# 演练记录：[问题类型]

## 基本信息
- 日期：2026-03-28
- 演练者：
- 问题类型：[GC / 慢查询 / goroutine 泄漏 / 连接池耗尽 / 超时传播]
- 注入方式：[API / 代码修改]

## 1. 发现阶段（Recording Discovery）
- 首次发现异常的时间点：
- 首次发现异常的方式（告警 / Grafana / 用户反馈）：
- 异常现象描述：

## 2. 定位阶段（Triage & Diagnosis）
- 使用了哪些工具：
- 查看了哪些指标/日志：
- 初始假设：
- 验证假设的步骤：
- 最终定位到的根因：

## 3. 修复阶段（Remediation）
- 临时止血方案（如有）：
- 根本修复方案：
- 修复后的验证方法：

## 4. 复盘
- 从发现到定位耗时：___分钟
- 从定位到修复耗时：___分钟
- 排查过程中的弯路：
- 可以改进的地方：
- 学到的新知识：

## 5. 自评
- 工具熟练度（1-5）：
- 定位效率（1-5）：
- 分析深度（1-5）：
- 整体评分（1-5）：
```

---

## 六、演练评估标准

### 6.1 分级评分

| 等级 | 标准 | 描述 |
|------|------|------|
| **L1 - 初学** | 能在提示下完成排查 | 需要查文档才能使用工具，定位时间 > 30 分钟 |
| **L2 - 熟练** | 能独立完成排查 | 工具使用熟练，定位时间 15-30 分钟 |
| **L3 - 精通** | 快速定位 + 深度分析 | 定位时间 < 15 分钟，能说清原理 |
| **L4 - 专家** | 能提前预防 + 设计方案 | 能设计监控告警预防此类问题 |

### 6.2 各维度评估项

```
┌─────────────────────────────────────────────────────┐
│  评估维度           │ L1  │ L2  │ L3  │ L4          │
├─────────────────────┼─────┼─────┼─────┼─────────────┤
│  工具使用能力       │     │     │     │             │
│  指标解读能力       │     │     │     │             │
│  日志分析能力       │     │     │     │             │
│  根因分析深度       │     │     │     │             │
│  修复方案合理性     │     │     │     │             │
│  排查效率           │     │     │     │             │
│  文档记录质量       │     │     │     │             │
│  知识迁移能力       │     │     │     │             │
└─────────────────────────────────────────────────────┘
```

### 6.3 通过标准

完成 Phase 14 演练的最低标准：

- [ ] 至少完成 5 个场景中的 4 个
- [ ] 每个场景在 30 分钟内独立完成定位
- [ ] 每个场景有完整的演练记录
- [ ] 能说清每个场景的根因原理（不只是"修好了"）
- [ ] 所有场景综合评分 >= L2

---

## 七、常见问题排查清单

### 7.1 演练环境问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 容器启动失败 | 端口冲突 | `lsof -i :8080` 检查端口占用 |
| MySQL 连不上 | 容器未就绪 | 等待 30s 或 `docker-compose logs mysql` |
| Grafana 无数据 | Prometheus 未 scrape | 检查 `prometheus.yml` targets |
| Jaeger 无链路 | 服务未上报 trace | 检查 OTEL agent 配置 |
| 注入 API 404 | chaos 模块未启用 | 启动时加 `CHAOS_ENABLED=true` 环境变量 |

### 7.2 工具快速参考

```bash
# === Java 排查工具 ===
# Arthas 连接容器中的 Java 进程
docker exec -it order-service java -jar /opt/arthas/arthas-boot.jar

# JVM 内存快照
docker exec order-service jmap -dump:format=b,file=/tmp/heap.hprof 1
docker cp order-service:/tmp/heap.hprof .

# GC 日志实时查看
docker logs -f order-service 2>&1 | grep -E "GC|Pause"

# === Go 排查工具 ===
# pprof CPU 分析（30s）
go tool pprof http://localhost:8081/debug/pprof/profile?seconds=30

# goroutine 堆栈
curl http://localhost:8081/debug/pprof/goroutine?debug=2

# 内存分析
go tool pprof http://localhost:8081/debug/pprof/heap

# === MySQL 排查 ===
# 当前执行的查询
mysql -e "SHOW FULL PROCESSLIST"

# 慢查询 top 10
mysqldumpslow -s t -t 10 /var/log/mysql/slow.log

# 索引使用情况
mysql -e "EXPLAIN SELECT * FROM orders WHERE user_id = 123"

# === Redis 排查 ===
# 大 Key 扫描
redis-cli --bigkeys

# 内存分析
redis-cli memory doctor

# 慢操作日志
redis-cli slowlog get 20

# === 通用 ===
# 容器资源使用
docker stats --no-stream

# 网络连接状态
ss -tnp | grep -E "8080|8081|8082"
```

---

## 八、演练顺序建议

建议按照以下顺序进行演练，从单一组件问题逐步过渡到跨服务问题：

```
演练路径（推荐顺序）：

Day 1: MySQL 慢查询
  ↓   （最直观，工具最成熟）
Day 2: Java GC 问题
  ↓   （需要理解 JVM 内存模型）
Day 3: Go goroutine 泄漏
  ↓   （需要理解 Go 并发模型）
Day 4: 连接池耗尽
  ↓   （跨 Java + MySQL 的问题）
Day 5: 超时传播
  ↓   （跨多个服务的分布式问题）
Day 6: 综合场景（同时注入 2-3 个问题）
  ↓   （模拟真实生产环境的复杂度）
Day 7: 复盘 + 自测
```

每天练习 2-3 小时，一周内可以完成全部演练。完成后通过 `03-self-assessment.md` 中的自测题验证掌握程度。
