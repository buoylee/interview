# 全链路性能工程实战

## 为什么需要全链路实战

单个工具会用不等于能解决问题。生产环境中的性能问题往往是多因素交织的——一个慢查询可能引发连接池耗尽，连接池耗尽可能导致请求堆积，请求堆积可能触发超时传播。本文档设计了 5 个端到端的问题场景，每个场景完整覆盖 **注入 → 发现 → 排查 → 根因 → 修复 → 验证** 的全流程，训练你从现象到本质的系统化排查能力。

---

## 一、场景 1：Java GC 问题 — 大对象分配导致频繁 Full GC

### 1.1 问题背景

PerfShop 的订单服务在一次需求迭代中，为了实现"批量导出订单"功能，开发者一次性将数据库查询结果全部加载到内存中再序列化为 Excel。当用户导出大量订单时，产生了大量的大对象分配，导致频繁触发 Full GC，整个服务的响应时间急剧恶化。

### 1.2 问题注入

```java
// order-service/src/main/java/com/perfshop/service/OrderExportService.java
@Service
public class OrderExportService {

    @Autowired
    private OrderRepository orderRepository;

    /**
     * 问题代码：一次性加载所有订单到内存
     * 假设 userId 有 50 万条订单
     */
    public byte[] exportOrders(Long userId) {
        // 一次性加载全部数据 → 大对象直接进入老年代
        List<Order> allOrders = orderRepository.findAllByUserId(userId);

        // 将每个 Order 转换为包含详情的 DTO，内存翻倍
        List<OrderExportDTO> dtos = allOrders.stream()
            .map(order -> {
                OrderExportDTO dto = new OrderExportDTO();
                dto.setOrderId(order.getId());
                dto.setItems(orderItemRepository.findByOrderId(order.getId()));
                // 序列化为 JSON 字符串再存入 DTO（又一份拷贝）
                dto.setItemsJson(objectMapper.writeValueAsString(dto.getItems()));
                return dto;
            })
            .collect(Collectors.toList());

        // 生成 Excel 文件（又一份内存占用）
        return excelGenerator.generate(dtos);
    }
}
```

触发注入：

```bash
# 先注入大量订单数据
curl -X POST http://localhost:8080/admin/seed-orders \
  -d '{"userId": 1001, "count": 500000}'

# 发起导出请求（触发大对象分配）
curl http://localhost:8080/api/orders/export?userId=1001 -o /dev/null &

# 同时发起正常业务负载
wrk -t4 -c50 -d120s http://localhost:8080/api/orders/recent
```

### 1.3 发现线索 — Grafana 上的异常

在 **JVM Overview** 仪表盘上观察到：

| 指标 | 正常值 | 异常值 | 说明 |
|------|--------|--------|------|
| Heap Used | 200-400MB | 1.5GB+ | 老年代被大对象占满 |
| Full GC Count | 0-1/hour | 10+/min | 频繁 Full GC |
| GC Pause Time | < 50ms | 2-5s | STW 暂停严重 |
| P99 Latency | 50ms | 8000ms+ | 所有接口都受影响 |
| Thread Count | 50 | 200+ | 请求被 GC 暂停阻塞后堆积 |

### 1.4 排查步骤

```bash
# Step 1: 确认 GC 情况
docker exec order-service jstat -gcutil 1 1000
# 观察 O（Old Gen）使用率持续高位，FGC 次数快速增长

# Step 2: 查看 GC 日志详情
docker logs order-service 2>&1 | grep -A2 "Full GC"
# [Full GC (Allocation Failure) 1536M->1480M(2048M), 3.245 secs]
# 注意：回收前后内存变化很小 → 说明大部分对象是活的

# Step 3: Arthas 实时诊断
docker exec -it order-service java -jar /opt/arthas/arthas-boot.jar
# Arthas 内执行：
dashboard
# 观察 MEMORY 部分，Old Gen 接近上限

# Step 4: 抓取堆转储
docker exec order-service \
  jmap -dump:live,format=b,file=/tmp/heap.hprof 1
docker cp order-service:/tmp/heap.hprof ./heap-gc-issue.hprof

# Step 5: MAT 分析
# 用 Eclipse MAT 打开 heap-gc-issue.hprof
# Leak Suspects Report → 发现 OrderExportDTO 的 List 占据 1.2GB
# Dominator Tree → ArrayList → OrderExportDTO[] → 50万个对象
```

### 1.5 根因分析

```
根因链条：
1. findAllByUserId() 一次性查询 50 万条记录
2. 每条记录又查一次 items（N+1 问题）
3. items 序列化为 JSON 字符串（冗余拷贝）
4. 最后生成 Excel（第三次内存放大）
5. 总内存占用 ≈ 原始数据 × 3-4 倍
6. 超过 JVM 堆大小 → 触发 Full GC → STW → 所有请求阻塞
```

### 1.6 修复方案

```java
// 修复版本：流式处理 + 分批查询
@Service
public class OrderExportService {

    public void exportOrders(Long userId, OutputStream outputStream) {
        // 使用 SXSSFWorkbook 进行流式 Excel 生成（内存中只保留 100 行）
        try (SXSSFWorkbook workbook = new SXSSFWorkbook(100)) {
            Sheet sheet = workbook.createSheet("Orders");

            // 分批查询，每次 1000 条
            int page = 0;
            int pageSize = 1000;
            int rowIndex = 0;

            while (true) {
                // 分页查询 + JOIN 消除 N+1 问题
                Page<OrderWithItems> batch = orderRepository
                    .findByUserIdWithItems(userId, PageRequest.of(page, pageSize));

                for (OrderWithItems order : batch.getContent()) {
                    Row row = sheet.createRow(rowIndex++);
                    fillRow(row, order); // 不再序列化为 JSON
                }

                if (!batch.hasNext()) break;
                page++;
            }

            // 直接写入输出流，不在内存中生成完整文件
            workbook.write(outputStream);
        }
    }
}
```

### 1.7 验证方法

```bash
# 修复后重新测试
curl http://localhost:8080/api/orders/export?userId=1001 -o /dev/null &
wrk -t4 -c50 -d120s http://localhost:8080/api/orders/recent

# 观察 Grafana：
# - Heap Used 保持在正常范围
# - Full GC 次数 = 0
# - P99 Latency 回到 50ms 以下
```

---

## 二、场景 2：MySQL 慢查询 — 缺失索引 + 全表扫描

### 2.1 问题背景

PerfShop 上线了一个"按日期范围查询用户订单"的功能。开发时用小数据集测试正常，但生产环境中 orders 表有 500 万条数据，由于 WHERE 条件中的 `created_at` 和 `user_id` 缺少合适的联合索引，每次查询变成了全表扫描。

### 2.2 问题注入

```sql
-- 1. 确保没有合适的联合索引
ALTER TABLE orders DROP INDEX IF EXISTS idx_order_user_date;
-- 仅保留 user_id 的单列索引（不够用）
-- 场景需要按 user_id + created_at 范围查询

-- 2. 注入大量数据
DELIMITER //
CREATE PROCEDURE seed_orders()
BEGIN
    DECLARE i INT DEFAULT 0;
    WHILE i < 5000000 DO
        INSERT INTO orders (user_id, status, total_amount, created_at)
        VALUES (
            FLOOR(RAND() * 100000),
            ELT(FLOOR(RAND() * 4) + 1, 'PENDING', 'PAID', 'SHIPPED', 'COMPLETED'),
            ROUND(RAND() * 5000, 2),
            DATE_SUB(NOW(), INTERVAL FLOOR(RAND() * 730) DAY)
        );
        SET i = i + 1;
    END WHILE;
END //
DELIMITER ;
CALL seed_orders();
```

触发问题的查询：

```sql
-- 这个查询在 500 万行表上没有合适索引，会全表扫描
SELECT * FROM orders
WHERE user_id = 12345
  AND created_at BETWEEN '2025-01-01' AND '2025-12-31'
ORDER BY created_at DESC
LIMIT 20;
```

### 2.3 发现线索 — Grafana 上的异常

**MySQL Overview** 仪表盘：

| 指标 | 正常值 | 异常值 | 说明 |
|------|--------|--------|------|
| Slow Queries/s | 0 | 15+ | 大量慢查询 |
| Query Duration P99 | 5ms | 3000ms+ | 查询延迟飙升 |
| Handler_read_rnd_next | 低 | 数百万/s | 全表扫描标志 |
| Threads_running | 5 | 30+ | 查询阻塞，线程堆积 |
| InnoDB Buffer Pool Hit | 99% | 70% | 全表扫描冲刷 buffer pool |

### 2.4 排查步骤

```bash
# Step 1: 查看慢查询日志
mysqldumpslow -s t -t 5 /var/log/mysql/slow.log
# Count: 847  Time=3.24s  Lock=0.00s  Rows=20.0
# SELECT * FROM orders WHERE user_id = N AND created_at BETWEEN 'S' AND 'S'

# Step 2: EXPLAIN 分析
mysql -e "EXPLAIN SELECT * FROM orders
WHERE user_id = 12345
AND created_at BETWEEN '2025-01-01' AND '2025-12-31'
ORDER BY created_at DESC LIMIT 20\G"
# type: ALL              ← 全表扫描
# possible_keys: idx_order_user_id
# key: NULL              ← 没有使用索引！
# rows: 4987235          ← 扫描了近 500 万行
# Extra: Using where; Using filesort  ← 还需要排序

# Step 3: 分析表结构和现有索引
mysql -e "SHOW INDEX FROM orders"
# 只有 PRIMARY 和 idx_order_user_id（user_id 单列索引）

# Step 4: 用 EXPLAIN ANALYZE 看实际执行计划（MySQL 8.0.18+）
mysql -e "EXPLAIN ANALYZE SELECT * FROM orders
WHERE user_id = 12345
AND created_at BETWEEN '2025-01-01' AND '2025-12-31'
ORDER BY created_at DESC LIMIT 20\G"
# → Table scan on orders  (cost=512345 rows=4987235)
#     (actual time=0.05..3241.33 rows=4987235 loops=1)
```

### 2.5 根因分析

```
根因链条：
1. WHERE 条件包含 user_id = X AND created_at BETWEEN ...
2. 现有索引 idx_order_user_id 只覆盖 user_id
3. MySQL 优化器评估：即使用 user_id 索引找到该用户的订单，
   还要回表读 created_at 做过滤，且 ORDER BY created_at 还要 filesort
4. 优化器判断全表扫描可能更快（错误判断或确实更快因为回表代价大）
5. 全表扫描 500 万行 → 耗时 3s+
6. 大量并发查询同时全表扫描 → buffer pool 被冲刷 → 其他查询也变慢
```

### 2.6 修复方案

```sql
-- 方案 1：创建覆盖查询的联合索引（推荐）
ALTER TABLE orders ADD INDEX idx_user_date (user_id, created_at);
-- 索引顺序重要：先等值条件 user_id，再范围条件 created_at
-- 这样可以通过索引直接定位 + 范围扫描，无需 filesort

-- 验证 EXPLAIN
EXPLAIN SELECT * FROM orders
WHERE user_id = 12345
  AND created_at BETWEEN '2025-01-01' AND '2025-12-31'
ORDER BY created_at DESC LIMIT 20;
-- type: range           ← 范围扫描
-- key: idx_user_date    ← 使用了联合索引
-- rows: 47              ← 只扫描 47 行
-- Extra: Using index condition; Backward index scan

-- 方案 2（进一步优化）：覆盖索引避免回表
ALTER TABLE orders ADD INDEX idx_user_date_cover
  (user_id, created_at, status, total_amount);
-- 如果 SELECT 的列都在索引中，连回表都免了
```

### 2.7 验证方法

```bash
# 修复前后对比
# 修复前：
mysql -e "SELECT * FROM orders WHERE user_id=12345
  AND created_at BETWEEN '2025-01-01' AND '2025-12-31'
  ORDER BY created_at DESC LIMIT 20" --profiling
# Query_time: 3.241s

# 加索引后：
mysql -e "ALTER TABLE orders ADD INDEX idx_user_date (user_id, created_at)"
mysql -e "SELECT * FROM orders WHERE user_id=12345
  AND created_at BETWEEN '2025-01-01' AND '2025-12-31'
  ORDER BY created_at DESC LIMIT 20" --profiling
# Query_time: 0.003s (提升 1000x)

# 负载测试验证
wrk -t4 -c50 -d60s "http://localhost:8080/api/orders?userId=12345&from=2025-01-01&to=2025-12-31"
# P99 应从 3000ms 降到 < 50ms
```

---

## 三、场景 3：Go Goroutine 泄漏 — HTTP Client 未关闭 Body

### 3.1 问题背景

PerfShop 的商品服务（Go）在获取商品价格时需要调用一个价格计算微服务。开发者在某些错误处理分支中忘记关闭 HTTP Response Body，导致 goroutine 和 TCP 连接持续泄漏，最终服务内存耗尽。

### 3.2 问题注入

```go
// product-service/internal/service/price.go
func (s *PriceService) GetPrice(ctx context.Context, productID int64) (float64, error) {
    url := fmt.Sprintf("http://price-calculator:8083/api/price/%d", productID)

    req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
    if err != nil {
        return 0, fmt.Errorf("create request: %w", err)
    }

    resp, err := s.client.Do(req)
    if err != nil {
        return 0, fmt.Errorf("do request: %w", err)
    }

    // BUG: 只在正常路径关闭 Body，错误路径漏了
    if resp.StatusCode != http.StatusOK {
        // 这里直接 return 了，没有关闭 resp.Body！
        return 0, fmt.Errorf("unexpected status: %d", resp.StatusCode)
    }

    defer resp.Body.Close()

    var result PriceResponse
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return 0, fmt.Errorf("decode response: %w", err)
    }

    return result.Price, nil
}
```

模拟触发条件：

```bash
# 让价格服务返回 500 错误（50% 概率）
curl -X POST http://localhost:8083/chaos/error-rate -d '{"rate": 0.5}'

# 持续发起商品查询（会触发价格服务调用）
wrk -t4 -c20 -d300s http://localhost:8081/api/products/1/detail
```

### 3.3 发现线索 — Grafana 上的异常

**Go Runtime** 仪表盘：

| 指标 | 正常值 | 异常值 | 说明 |
|------|--------|--------|------|
| Goroutines | 50-100 | 5000+ 且持续增长 | goroutine 泄漏 |
| Memory (RSS) | 50MB | 500MB+ 且持续增长 | 随 goroutine 泄漏增长 |
| Open FDs | 30 | 500+ | TCP 连接未释放 |
| HTTP Client Active | 10 | 500+ | Transport 中的连接泄漏 |

关键信号：**goroutine 数量呈线性增长，不会回落**。

### 3.4 排查步骤

```bash
# Step 1: 确认 goroutine 增长
watch -n 5 'curl -s http://localhost:8081/debug/pprof/goroutine?debug=0 | head -1'
# goroutine profile: total 5234  ← 持续增长

# Step 2: 下载 goroutine profile
curl -s http://localhost:8081/debug/pprof/goroutine?debug=2 > goroutine-dump.txt

# Step 3: 分析 goroutine 堆栈（找最多的相同堆栈）
grep -c "^goroutine" goroutine-dump.txt
# 5234

# 统计堆栈分类
go tool pprof -top http://localhost:8081/debug/pprof/goroutine
# Showing top nodes:
#       4891  93.45%  net/http.(*persistConn).readLoop
#       4891  93.45%  net/http.(*persistConn).writeLoop
# ← 大量 goroutine 卡在 HTTP Transport 的 readLoop/writeLoop

# Step 4: 查看完整堆栈，定位创建源头
go tool pprof -peek readLoop http://localhost:8081/debug/pprof/goroutine
# 找到调用链：
# PriceService.GetPrice → http.Client.Do → Transport.roundTrip
# → persistConn.readLoop (blocked)

# Step 5: 查看连接数确认
ss -tnp | grep 8083 | wc -l
# 4891  ← 每个泄漏的 goroutine 对应一个 TCP 连接
```

### 3.5 根因分析

```
根因链条：
1. GetPrice() 在 resp.StatusCode != 200 时直接 return error
2. 没有关闭 resp.Body → HTTP Transport 认为连接还在使用
3. Transport 的 readLoop goroutine 持续等待读取 Body
4. writeLoop goroutine 持续等待可能的写入
5. 每次未关闭的请求泄漏 2 个 goroutine + 1 个 TCP 连接
6. 50% 错误率 × 20 QPS = 每秒泄漏 10 个请求 = 20 个 goroutine
7. 5 分钟后 = 6000 个泄漏的 goroutine → 内存持续增长
```

### 3.6 修复方案

```go
// 修复版本：确保所有路径都关闭 Body
func (s *PriceService) GetPrice(ctx context.Context, productID int64) (float64, error) {
    url := fmt.Sprintf("http://price-calculator:8083/api/price/%d", productID)

    req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
    if err != nil {
        return 0, fmt.Errorf("create request: %w", err)
    }

    resp, err := s.client.Do(req)
    if err != nil {
        return 0, fmt.Errorf("do request: %w", err)
    }
    // 关键修复：在拿到 resp 后立即 defer Close，确保所有路径都关闭
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusOK {
        // 即使不读 Body，也要 drain 后关闭，让连接可复用
        io.Copy(io.Discard, resp.Body)
        return 0, fmt.Errorf("unexpected status: %d", resp.StatusCode)
    }

    var result PriceResponse
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return 0, fmt.Errorf("decode response: %w", err)
    }

    return result.Price, nil
}
```

### 3.7 验证方法

```bash
# 修复后重启服务，再次注入错误率
curl -X POST http://localhost:8083/chaos/error-rate -d '{"rate": 0.5}'
wrk -t4 -c20 -d300s http://localhost:8081/api/products/1/detail

# 观察 goroutine 数量
watch -n 5 'curl -s http://localhost:8081/debug/pprof/goroutine?debug=0 | head -1'
# goroutine profile: total 85  ← 稳定，不再增长

# 观察内存
watch -n 5 'curl -s http://localhost:8081/debug/pprof/heap?debug=0 | head -5'
# 内存使用稳定
```

---

## 四、场景 4：Redis 大 Key — 商品详情存为大 JSON

### 4.1 问题背景

PerfShop 的商品服务为了加速商品详情页加载，将完整的商品信息（包含所有 SKU、评论、图片 URL 列表）序列化为一个大 JSON 存入 Redis。当热门商品有上千个 SKU 和上万条评论时，单个 Key 的 Value 达到 5-10MB。这导致 Redis 出现周期性的延迟毛刺。

### 4.2 问题注入

```go
// product-service/internal/cache/product_cache.go
func (c *ProductCache) SetProductDetail(ctx context.Context, product *Product) error {
    // 问题：把所有关联数据打成一个大 JSON
    detail := ProductDetail{
        Product:  *product,
        SKUs:     product.SKUs,         // 可能有 1000+ 个 SKU
        Reviews:  product.Reviews,      // 可能有 10000+ 条评论
        Images:   product.ImageURLs,    // 50+ 张图片 URL
        Similar:  product.SimilarItems, // 关联商品
    }

    data, _ := json.Marshal(detail)
    // 单个 Key 的 Value 可能达到 5-10MB
    return c.rdb.Set(ctx, fmt.Sprintf("product:%d", product.ID), data, 24*time.Hour).Err()
}
```

注入数据：

```bash
# 创建包含大量 SKU 和评论的商品
curl -X POST http://localhost:8081/admin/create-heavy-product \
  -d '{"skuCount": 1000, "reviewCount": 10000, "imageCount": 50}'
# 返回 product_id: 9999

# 预热缓存（写入大 Key）
curl http://localhost:8081/api/products/9999/detail

# 检查 Key 大小
redis-cli memory usage "product:9999"
# (integer) 8372456  ← 约 8MB
```

### 4.3 发现线索 — Grafana 上的异常

**Redis Overview** 仪表盘：

| 指标 | 正常值 | 异常值 | 说明 |
|------|--------|--------|------|
| Latency P99 | < 1ms | 50-200ms（毛刺） | 大 Key 读写阻塞 |
| Network Input | 5MB/s | 50MB/s（突发） | 读取大 Value 占满带宽 |
| Memory Fragmentation | 1.0-1.1 | 1.5+ | 大对象导致内存碎片 |
| Slowlog Count | 0 | 10+/min | DEL/GET 大 Key 出现在慢日志 |
| Clients Blocked | 0 | 5+ | 被大 Key 操作阻塞 |

### 4.4 排查步骤

```bash
# Step 1: 查看 Redis 慢日志
redis-cli slowlog get 20
# 1) 1) (integer) 1
#    2) (integer) 1711612800
#    3) (integer) 183456    ← 183ms
#    4) 1) "GET"
#       2) "product:9999"

# Step 2: 扫描大 Key
redis-cli --bigkeys
# [00.00%] Biggest string found so far 'product:9999' with 8372456 bytes
# -------- summary -------
# Biggest string found 'product:9999' has 8372456 bytes  ← 8MB!

# Step 3: 用 memory usage 逐个检查可疑 Key
redis-cli memory usage "product:9999"
# (integer) 8372456

redis-cli memory usage "product:1"
# (integer) 2048  ← 正常大小

# Step 4: 分析 Key 的 TTL 和访问频率
redis-cli object freq "product:9999"
redis-cli ttl "product:9999"

# Step 5: 确认对 Redis 整体的影响
redis-cli info memory
# used_memory_human: 1.2G
# mem_fragmentation_ratio: 1.58  ← 碎片率偏高

redis-cli info stats | grep -E "keyspace|ops"
# instantaneous_ops_per_sec: 2500
```

### 4.5 根因分析

```
根因链条：
1. 商品详情缓存包含了所有关联数据（SKU、评论、图片）
2. 热门商品的单个 Key 达到 5-10MB
3. Redis 是单线程，读取/写入 8MB 的 Key 会阻塞其他命令数十毫秒
4. 当多个客户端同时读取大 Key → 网络带宽被占满
5. 大 Key 过期或被删除时（DEL 是 O(1) 但释放内存耗时），整个 Redis 被阻塞
6. 内存碎片率增加，Redis 内存利用效率下降
```

### 4.6 修复方案

```go
// 修复版本：拆分大 Key，按数据类型分开存储
func (c *ProductCache) SetProductDetail(ctx context.Context, product *Product) error {
    pipe := c.rdb.Pipeline()
    key := fmt.Sprintf("product:%d", product.ID)
    ttl := 24 * time.Hour

    // 基础信息单独存（通常 < 1KB）
    baseData, _ := json.Marshal(product.Base)
    pipe.Set(ctx, key+":base", baseData, ttl)

    // SKU 列表用 Hash 存储（每个 SKU 一个 field）
    for _, sku := range product.SKUs {
        skuData, _ := json.Marshal(sku)
        pipe.HSet(ctx, key+":skus", strconv.FormatInt(sku.ID, 10), skuData)
    }
    pipe.Expire(ctx, key+":skus", ttl)

    // 评论分页存储，每页 20 条
    pageSize := 20
    for i := 0; i < len(product.Reviews); i += pageSize {
        end := i + pageSize
        if end > len(product.Reviews) {
            end = len(product.Reviews)
        }
        page := i / pageSize
        pageData, _ := json.Marshal(product.Reviews[i:end])
        pipe.Set(ctx, fmt.Sprintf("%s:reviews:%d", key, page), pageData, ttl)
    }
    pipe.Set(ctx, key+":reviews:total", len(product.Reviews), ttl)

    // 图片 URL 用 List 存储
    for _, url := range product.ImageURLs {
        pipe.RPush(ctx, key+":images", url)
    }
    pipe.Expire(ctx, key+":images", ttl)

    _, err := pipe.Exec(ctx)
    return err
}

// 读取时按需加载
func (c *ProductCache) GetProductBase(ctx context.Context, id int64) (*ProductBase, error) {
    data, err := c.rdb.Get(ctx, fmt.Sprintf("product:%d:base", id)).Bytes()
    if err != nil {
        return nil, err
    }
    var base ProductBase
    json.Unmarshal(data, &base)
    return &base, nil
}

// 评论分页加载
func (c *ProductCache) GetProductReviews(ctx context.Context, id int64, page int) ([]Review, error) {
    data, err := c.rdb.Get(ctx, fmt.Sprintf("product:%d:reviews:%d", id, page)).Bytes()
    if err != nil {
        return nil, err
    }
    var reviews []Review
    json.Unmarshal(data, &reviews)
    return reviews, nil
}
```

删除旧的大 Key 时也要注意：

```bash
# 不要直接 DEL 大 Key（会阻塞 Redis）
# 使用 UNLINK（异步删除，Redis 4.0+）
redis-cli UNLINK "product:9999"

# 或手动分批删除（兼容老版本 Redis）
# 如果是 Hash 类型：HSCAN + HDEL 分批
# 如果是 String 类型：直接 UNLINK 或 DEL
```

### 4.7 验证方法

```bash
# 修复后重新写入缓存
curl http://localhost:8081/api/products/9999/detail

# 检查拆分后的 Key 大小
redis-cli memory usage "product:9999:base"
# (integer) 856    ← < 1KB

redis-cli memory usage "product:9999:skus"
# (integer) 24680  ← 每个 field 很小

# 慢日志应该清零
redis-cli slowlog reset
# 等待 1 分钟后
redis-cli slowlog get 5
# (empty array)

# Redis 延迟恢复正常
redis-cli --latency -i 1
# avg: 0.12ms  ← 正常
```

---

## 五、场景 5：超时传播 — 下游服务响应慢，上游超时设置不合理

### 5.1 问题背景

PerfShop 的下单流程：`Nginx → Go (Product) → Java (Order) → MySQL`。Java 订单服务因为某次部署引入了一个 N+1 查询问题，响应时间从 50ms 增加到 5s。但 Go 服务对 Java 服务的调用超时设置为 30s（太长），导致 Go 服务的 goroutine 全部堆积在等待 Java 响应上，最终 Go 服务自身也无法响应。

### 5.2 问题注入

```go
// product-service/internal/client/order_client.go
// 问题代码：超时设置不合理
func NewOrderClient() *OrderClient {
    return &OrderClient{
        httpClient: &http.Client{
            Timeout: 30 * time.Second, // 太长了！
        },
        baseURL: "http://order-service:8080",
    }
}

func (c *OrderClient) CreateOrder(ctx context.Context, req CreateOrderReq) (*Order, error) {
    // 没有使用 ctx 的 deadline，而是用 httpClient 自己的超时
    data, _ := json.Marshal(req)
    resp, err := c.httpClient.Post(
        c.baseURL+"/api/orders",
        "application/json",
        bytes.NewReader(data),
    )
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    var order Order
    json.NewDecoder(resp.Body).Decode(&order)
    return &order, nil
}
```

同时在 Java 端注入延迟：

```bash
# Java 服务注入 5s 延迟
curl -X POST http://localhost:8080/chaos/slow-response \
  -d '{"delayMs": 5000, "path": "/api/orders", "durationSec": 300}'

# 发起下单负载
wrk -t4 -c100 -d120s -s post_order.lua http://localhost:8081/api/checkout
```

### 5.3 发现线索 — Grafana + Jaeger

**多个仪表盘联合观察：**

| 仪表盘 | 指标 | 异常表现 |
|--------|------|---------|
| Go Runtime | Goroutines | 从 50 飙升到 3000+ |
| Go Runtime | HTTP Active Requests | 全部卡在 order-service 调用 |
| JVM Overview | Request Duration | P99 = 5000ms |
| Nginx | 5xx Count | Go 服务无响应，Nginx 报 502 |
| Jaeger | Trace Duration | 下单链路 5s+，瓶颈在 Order 阶段 |

**Jaeger 链路图关键信息：**

```
checkout (Go)               ─── 5.02s ────────────────────────│
  ├─ validate-stock (Go)    ── 2ms ─│
  ├─ create-order (Java)    ─────────── 5.00s ────────────────│  ← 瓶颈
  │    ├─ query-user         ── 0.5ms ─│
  │    ├─ query-products     ──── 4.95s ────────────────────│  ← N+1 问题
  │    └─ insert-order       ── 3ms ─│
  └─ (response)             ── 0.5ms ─│
```

### 5.4 排查步骤

```bash
# Step 1: 确认 Go 服务的 goroutine 状态
curl -s http://localhost:8081/debug/pprof/goroutine?debug=1 | head -20
# goroutine profile: total 3042
# 2891 @ 0x... 0x... → net/http.(*Client).Do → OrderClient.CreateOrder
# ← 大量 goroutine 阻塞在调用 order-service

# Step 2: 确认 Java 服务确实慢了
curl -w "%{time_total}s\n" -o /dev/null -s http://localhost:8080/api/orders/1
# 5.023s  ← 确认 Java 服务响应慢

# Step 3: Jaeger 中追踪一条慢链路
# 在 Jaeger UI 搜索 service=product-service, minDuration=3s
# 查看 span 细节，发现 create-order span 耗时 5s
# 进入 order-service 的子 span，发现 query-products 有 N+1 问题

# Step 4: 确认 Go 服务的超时配置
grep -r "Timeout" product-service/internal/client/
# Timeout: 30 * time.Second  ← 太长了

# Step 5: 确认 Nginx 的超时配置
grep "proxy_timeout\|proxy_read_timeout" nginx/nginx.conf
# proxy_read_timeout 10s;  ← Nginx 10s 超时，比 Go 的 30s 短
# 所以 Nginx 先超时返回 502，但 Go 还在傻等 Java
```

### 5.5 根因分析

```
根因链条（自底向上）：
1. Java 服务引入 N+1 查询，响应从 50ms 变为 5s
2. Go 服务超时设置 30s，远大于正常响应时间，不能快速失败
3. Go 服务 goroutine 全部堆积在等待 Java 响应
4. Nginx 超时 10s < Go 超时 30s → Nginx 先超时返回 502
5. 但 Go 的 goroutine 还在等（又等了 20s 才超时）
6. 每秒新请求进来 + 旧请求还没超时 = goroutine 快速堆积
7. Go 服务内存耗尽 / FD 耗尽 → 完全无法服务

关键问题：
- 超时不是层层递减的（Nginx 10s > Go 30s，方向反了）
- Go 没有传播 context deadline
- 没有断路器保护
```

### 5.6 修复方案

```go
// 修复版本：合理超时 + context 传播 + 断路器
func NewOrderClient() *OrderClient {
    return &OrderClient{
        httpClient: &http.Client{
            // 兜底超时，不应该生效（context deadline 应先触发）
            Timeout: 5 * time.Second,
            Transport: &http.Transport{
                MaxIdleConns:        100,
                MaxIdleConnsPerHost: 20,
                IdleConnTimeout:    90 * time.Second,
            },
        },
        baseURL: "http://order-service:8080",
        // 断路器：5 次错误后熔断 10s
        breaker: gobreaker.NewCircuitBreaker(gobreaker.Settings{
            Name:        "order-service",
            MaxRequests: 5,
            Interval:    10 * time.Second,
            Timeout:     10 * time.Second,
            ReadyToTrip: func(counts gobreaker.Counts) bool {
                failureRatio := float64(counts.TotalFailures) / float64(counts.Requests)
                return counts.Requests >= 5 && failureRatio >= 0.5
            },
        }),
    }
}

func (c *OrderClient) CreateOrder(ctx context.Context, req CreateOrderReq) (*Order, error) {
    result, err := c.breaker.Execute(func() (interface{}, error) {
        data, _ := json.Marshal(req)
        // 使用 ctx 创建 request，传播 deadline
        httpReq, err := http.NewRequestWithContext(ctx, "POST",
            c.baseURL+"/api/orders", bytes.NewReader(data))
        if err != nil {
            return nil, err
        }
        httpReq.Header.Set("Content-Type", "application/json")

        resp, err := c.httpClient.Do(httpReq)
        if err != nil {
            return nil, err
        }
        defer resp.Body.Close()

        if resp.StatusCode >= 500 {
            io.Copy(io.Discard, resp.Body)
            return nil, fmt.Errorf("order service error: %d", resp.StatusCode)
        }

        var order Order
        if err := json.NewDecoder(resp.Body).Decode(&order); err != nil {
            return nil, err
        }
        return &order, nil
    })
    if err != nil {
        return nil, err
    }
    return result.(*Order), nil
}
```

同时修复超时层级配置：

```nginx
# nginx.conf — 超时层层递减
upstream go_service {
    server product-service:8081;
}

server {
    location /api/checkout {
        proxy_pass http://go_service;
        proxy_read_timeout 8s;   # Nginx 8s（最外层，最长）
        proxy_connect_timeout 2s;
    }
}
```

```go
// Go 服务入口中间件：设置请求级超时
func TimeoutMiddleware() gin.HandlerFunc {
    return func(c *gin.Context) {
        ctx, cancel := context.WithTimeout(c.Request.Context(), 6*time.Second) // Go 6s
        defer cancel()
        c.Request = c.Request.WithContext(ctx)
        c.Next()
    }
}
// 调用 Java 服务的 httpClient.Timeout = 5s（最内层，最短）
```

### 5.7 验证方法

```bash
# 修复后再次注入 Java 延迟
curl -X POST http://localhost:8080/chaos/slow-response \
  -d '{"delayMs": 5000, "path": "/api/orders", "durationSec": 60}'

# 发起负载
wrk -t4 -c100 -d60s -s post_order.lua http://localhost:8081/api/checkout

# 预期行为：
# 1. 前 5 个请求超时（5s 后返回错误）
# 2. 断路器打开，后续请求立即返回错误（< 1ms）
# 3. Go 服务 goroutine 数量稳定（不堆积）
# 4. 10s 后断路器半开，尝试 1 个请求
# 5. 如果 Java 还是慢，断路器继续打开

# Grafana 确认：
# - Go goroutines 保持稳定（50-100）
# - 错误率高但响应快（快速失败）
# - 没有 502 错误（Nginx 超时前 Go 已返回错误）
```

---

## 六、综合评分标准

### 6.1 单场景评分（每个场景 20 分，共 100 分）

| 评分项 | 分值 | 评分标准 |
|--------|------|---------|
| 发现异常 | 3 分 | 能从监控/告警中识别异常（3），需要提示（1），未识别（0） |
| 工具使用 | 3 分 | 使用正确工具高效定位（3），工具对但不熟练（2），错误工具（0） |
| 根因分析 | 5 分 | 完整准确的根因链条（5），核心根因正确（3），表面原因（1） |
| 修复方案 | 5 分 | 生产级修复方案（5），可用但不完美（3），临时方案（1） |
| 验证方法 | 2 分 | 量化验证+回归测试（2），只做基本验证（1） |
| 排查效率 | 2 分 | < 15min（2），15-30min（1），> 30min（0） |

### 6.2 综合等级评定

| 总分 | 等级 | 评价 |
|------|------|------|
| 90-100 | S | 性能工程专家，可独立负责生产问题 |
| 75-89 | A | 高级工程师水平，能处理大部分问题 |
| 60-74 | B | 中级工程师水平，需要一定指导 |
| 45-59 | C | 初级水平，需要系统学习 |
| < 45 | D | 基础不足，建议从前置阶段重新学习 |

### 6.3 加分项

- 在排查中发现了注入问题之外的真实性能隐患：+5 分
- 提出了预防此类问题的监控告警方案：+3 分
- 修复方案考虑了灰度发布和回滚：+2 分
- 排查记录清晰完整，可作为团队知识库：+2 分
