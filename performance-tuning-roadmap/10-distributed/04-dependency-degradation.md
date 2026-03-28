# 依赖分析与降级

## 为什么依赖治理决定系统的抗风险能力

一个微服务系统通常有几十甚至上百个服务间依赖。**你的系统的可用性，取决于依赖链中最脆弱的那一环**。如果不清楚哪些是强依赖、哪些是弱依赖，就无法设计有效的降级方案——要么全挂，要么过度降级。依赖治理不是架构师画完图就完事了，它是需要持续维护、定期演练的运维基本功。

---

## 一、依赖图分析与可视化

### 手动梳理依赖关系

对于中小规模系统，最直接的方式是基于代码和配置手动梳理：

```yaml
# 依赖关系文档示例：order-service 的依赖声明
service: order-service
dependencies:
  - name: user-service
    type: sync-rpc
    criticality: strong          # 强依赖：没有用户信息无法下单
    protocol: gRPC
    timeout: 1s
    retry: 1

  - name: inventory-service
    type: sync-rpc
    criticality: strong          # 强依赖：必须检查库存
    protocol: gRPC
    timeout: 2s
    retry: 2

  - name: coupon-service
    type: sync-rpc
    criticality: weak            # 弱依赖：优惠券校验失败可跳过
    protocol: HTTP
    timeout: 500ms
    retry: 0
    fallback: skip_coupon

  - name: recommendation-service
    type: sync-rpc
    criticality: weak            # 弱依赖：推荐失败不影响下单
    protocol: HTTP
    timeout: 300ms
    retry: 0
    fallback: empty_list

  - name: mysql
    type: database
    criticality: strong
    connection_pool: 20

  - name: redis
    type: cache
    criticality: weak            # 缓存不可用时回退到数据库
    fallback: query_db

  - name: kafka
    type: async-mq
    criticality: eventual        # 最终一致，短暂不可用可接受
    topic: order-events
```

### 从 Trace 自动生成 ServiceMap

大规模系统中手动梳理不现实，可以利用 Trace 数据自动生成依赖图：

```
Jaeger ServiceMap：
  Jaeger UI → System Architecture → DAG view
  → 自动展示服务间调用关系和调用量

Grafana Tempo + Service Graph：
  数据源选 Tempo → Service Graph 面板
  → 展示服务拓扑、延迟、错误率

自定义分析脚本：
```

```python
# 从 Jaeger API 提取依赖关系
import httpx
from collections import defaultdict
from datetime import datetime, timedelta

def extract_dependencies(jaeger_url: str, lookback_hours: int = 24) -> dict:
    """从 Jaeger 提取服务依赖关系"""
    end_time = int(datetime.now().timestamp() * 1_000_000)  # 微秒
    start_time = int((datetime.now() - timedelta(hours=lookback_hours)).timestamp() * 1_000_000)

    resp = httpx.get(
        f"{jaeger_url}/api/dependencies",
        params={"endTs": end_time, "lookback": lookback_hours * 3600 * 1000},
    )
    deps = resp.json()["data"]

    # 构建依赖图
    graph = defaultdict(list)
    for dep in deps:
        graph[dep["parent"]].append({
            "child": dep["child"],
            "call_count": dep["callCount"],
        })

    return dict(graph)

def find_critical_path(graph: dict, root: str, target: str) -> list:
    """BFS 找到从 root 到 target 的路径"""
    from collections import deque
    queue = deque([(root, [root])])
    visited = {root}

    while queue:
        node, path = queue.popleft()
        if node == target:
            return path
        for dep in graph.get(node, []):
            child = dep["child"]
            if child not in visited:
                visited.add(child)
                queue.append((child, path + [child]))
    return []

# 使用
deps = extract_dependencies("http://jaeger:16686")
for service, children in deps.items():
    print(f"{service} → {[c['child'] for c in children]}")
```

### 依赖可视化工具

| 工具 | 数据来源 | 特点 |
|------|---------|------|
| Jaeger Service Graph | Trace 数据 | 自动生成，实时更新 |
| Kiali（Istio） | Service Mesh | 与流量指标结合 |
| Backstage | 人工维护 | 包含 owner、文档链接 |
| 自建 Graphviz | 配置文件 | 灵活但需维护 |

---

## 二、关键路径识别

### 什么是关键路径

**关键路径**：决定请求总耗时的依赖调用链。关键路径上的任何服务变慢或故障，都会直接影响用户体验。

```
下单请求的调用图（包含并行调用）：

start → 鉴权(20ms) → ┬→ 库存检查(50ms) → ┬→ 创建订单(30ms) → 发消息(10ms) → end
                       └→ 优惠券校验(15ms) ┘

关键路径：start → 鉴权 → 库存检查 → 创建订单 → 发消息
总耗时 = 20 + 50 + 30 + 10 = 110ms

优惠券校验(15ms) 不在关键路径上（与库存检查并行，且耗时更短）
```

### 识别方法

```python
# 从 Trace 数据识别关键路径
def find_critical_path_from_trace(spans: list[dict]) -> list[dict]:
    """
    输入：一个 Trace 的所有 Span
    输出：关键路径上的 Span 列表
    """
    # 按 start_time 排序
    spans_by_id = {s["spanID"]: s for s in spans}

    # 找根 Span
    root = next(s for s in spans if not s.get("parentSpanID"))

    # DFS 找最长路径
    def dfs(span_id):
        span = spans_by_id[span_id]
        children = [s for s in spans if s.get("parentSpanID") == span_id]

        if not children:
            return [span], span["duration"]

        best_path, best_duration = [], 0
        for child in children:
            path, duration = dfs(child["spanID"])
            if duration > best_duration:
                best_path, best_duration = path, duration

        return [span] + best_path, span["duration"]

    path, total = dfs(root["spanID"])
    return path
```

### 关键路径上的依赖要特别关注

| 关注维度 | 非关键路径依赖 | 关键路径依赖 |
|---------|--------------|-------------|
| SLA 要求 | 可以较宽松 | 必须满足上游 SLA |
| 超时设置 | 可以较短（快速失败） | 需要留足裕量 |
| 断路器 | 建议有 | 必须有 |
| 降级方案 | 简单 fallback | 需要精心设计 |
| 监控告警 | P1 级别 | P0 级别 |
| 容量规划 | 跟随上游 | 需要额外 buffer |

---

## 三、强依赖 vs 弱依赖分类

### 分类标准

```
强依赖（Strong Dependency）：
  依赖不可用时，当前功能完全无法提供
  例：下单时的库存服务、支付服务

弱依赖（Weak Dependency）：
  依赖不可用时，当前功能可以降级提供
  例：下单时的推荐服务、优惠券服务

异步依赖（Eventual Dependency）：
  通过消息队列异步调用，短暂不可用不影响主流程
  例：下单后的通知服务、积分服务
```

### 分类决策树

```
这个依赖不可用时：
  ├─ 主流程能否继续？
  │   ├─ 不能 → 强依赖
  │   │   └─ 是否有替代方案？
  │   │       ├─ 有 → 强依赖（有 fallback）
  │   │       └─ 无 → 强依赖（不可降级）
  │   └─ 能 → 弱依赖
  │       └─ 用户能否感知？
  │           ├─ 能感知（如推荐位空了） → 弱依赖（需 fallback）
  │           └─ 不感知（如埋点丢了） → 弱依赖（静默失败）
```

### 实际系统的依赖分类

```
电商下单流程的依赖分类：

┌──────────────┬────────┬──────────────────────────┐
│ 依赖服务      │ 分类   │ 不可用时的策略             │
├──────────────┼────────┼──────────────────────────┤
│ 用户服务      │ 强依赖 │ 返回错误，无法下单          │
│ 库存服务      │ 强依赖 │ 返回错误，无法下单          │
│ 价格服务      │ 强依赖 │ 使用缓存价格（限时有效）    │
│ 支付服务      │ 强依赖 │ 异步支付（创建待支付订单）   │
│ 优惠券服务    │ 弱依赖 │ 跳过优惠，原价下单          │
│ 推荐服务      │ 弱依赖 │ 不展示推荐                  │
│ 风控服务      │ 弱依赖 │ 放行（记录后异步审核）      │
│ 通知服务      │ 异步   │ 消息积压，恢复后补发        │
│ 积分服务      │ 异步   │ 消息积压，恢复后补发        │
│ 数据分析      │ 异步   │ 数据延迟，不影响用户        │
└──────────────┴────────┴──────────────────────────┘
```

---

## 四、降级策略详解

### 策略 1：Fallback（返回默认值 / 缓存值）

```java
// Resilience4j Fallback 示例
@CircuitBreaker(name = "priceService", fallbackMethod = "priceFallback")
public ProductPrice getPrice(String productId) {
    return priceServiceClient.getPrice(productId);
}

// Fallback 方法签名必须与原方法一致，最后加 Throwable 参数
public ProductPrice priceFallback(String productId, Throwable t) {
    log.warn("Price service unavailable, using cache. productId={}", productId, t);

    // 策略 1：从本地缓存获取
    ProductPrice cached = localCache.get("price:" + productId);
    if (cached != null && !cached.isExpired(Duration.ofHours(1))) {
        cached.setFromCache(true);  // 标记来源，让前端展示提示
        return cached;
    }

    // 策略 2：返回默认价格（如原价）
    ProductPrice defaultPrice = productRepository.getBasePrice(productId);
    defaultPrice.setFromCache(true);
    defaultPrice.setDiscount(0);  // 无法计算折扣
    return defaultPrice;
}
```

```go
// Go Fallback 实现
func (s *PriceService) GetPrice(ctx context.Context, productID string) (*Price, error) {
    price, err := s.priceClient.GetPrice(ctx, productID)
    if err != nil {
        log.Warn("price service unavailable, using fallback",
            zap.String("product_id", productID), zap.Error(err))

        // 从缓存获取
        if cached, ok := s.cache.Get(productID); ok {
            cached.FromCache = true
            return cached, nil
        }

        // 从数据库获取基础价格
        basePrice, dbErr := s.repo.GetBasePrice(ctx, productID)
        if dbErr != nil {
            return nil, fmt.Errorf("all price sources failed: %w", dbErr)
        }
        basePrice.FromCache = true
        return basePrice, nil
    }

    // 成功时更新缓存
    s.cache.Set(productID, price, 1*time.Hour)
    return price, nil
}
```

### 策略 2：功能开关（Feature Flag）

```java
// Feature Flag 控制降级
@Component
public class FeatureFlagService {
    private final NacosConfigService configService;  // 或其他配置中心
    private volatile Map<String, Boolean> flags = new ConcurrentHashMap<>();

    @PostConstruct
    public void init() {
        // 监听配置变更，实时生效
        configService.addListener("feature-flags.json", event -> {
            flags = parseFlags(event.getContent());
            log.info("Feature flags updated: {}", flags);
        });
    }

    public boolean isEnabled(String feature) {
        return flags.getOrDefault(feature, true);  // 默认开启
    }
}

// 使用
@PostMapping("/orders")
public Order createOrder(CreateOrderRequest request) {
    Order order = new Order(request);

    // 强依赖：库存检查（不可跳过）
    inventoryService.reserve(order);

    // 弱依赖：优惠券 — 受 Feature Flag 控制
    if (featureFlags.isEnabled("coupon_validation")) {
        try {
            couponService.validate(order);
        } catch (Exception e) {
            log.warn("Coupon validation failed, skipping", e);
            order.setCouponSkipped(true);
        }
    }

    // 弱依赖：风控 — 受 Feature Flag 控制
    if (featureFlags.isEnabled("risk_check")) {
        try {
            riskService.check(order);
        } catch (Exception e) {
            log.warn("Risk check failed, will check async", e);
            asyncRiskQueue.add(order.getId());
        }
    }

    return orderRepository.save(order);
}
```

```json
// feature-flags.json（存在配置中心）
{
    "coupon_validation": true,
    "risk_check": true,
    "recommendation": true,
    "user_behavior_tracking": true,
    "real_time_inventory": true
}

// 降级时修改为：
{
    "coupon_validation": false,
    "risk_check": false,
    "recommendation": false,
    "user_behavior_tracking": false,
    "real_time_inventory": false
}
```

### 策略 3：柔性可用

```
正常模式：
  搜索结果 = 个性化推荐 + 实时库存 + 实时价格 + 优惠信息 + 评分

降级模式 1（推荐服务不可用）：
  搜索结果 = 热门排序 + 实时库存 + 实时价格 + 优惠信息 + 评分

降级模式 2（库存服务也不可用）：
  搜索结果 = 热门排序 + 缓存库存(标注可能不准) + 实时价格 + 评分

降级模式 3（价格服务也不可用）：
  搜索结果 = 热门排序 + 缓存库存 + 缓存价格 + 评分

降级模式 4（极端模式）：
  搜索结果 = 静态缓存页面 + "部分信息可能未更新" 提示
```

```go
// 柔性可用的实现模式
type SearchResult struct {
    Products       []Product
    DegradedFields []string  // 记录哪些字段是降级的
}

func (s *SearchService) Search(ctx context.Context, query string) (*SearchResult, error) {
    result := &SearchResult{}

    // 1. 核心搜索（强依赖）
    products, err := s.esClient.Search(ctx, query)
    if err != nil {
        return nil, fmt.Errorf("search engine unavailable: %w", err)
    }
    result.Products = products

    // 2. 个性化排序（弱依赖）
    if ranked, err := s.recommendClient.Rank(ctx, products); err == nil {
        result.Products = ranked
    } else {
        result.DegradedFields = append(result.DegradedFields, "personalization")
        // 退回到默认排序
    }

    // 3. 实时库存（弱依赖）
    if err := s.enrichInventory(ctx, result.Products); err != nil {
        result.DegradedFields = append(result.DegradedFields, "inventory")
        s.enrichInventoryFromCache(result.Products)  // 用缓存兜底
    }

    // 4. 实时价格（弱依赖）
    if err := s.enrichPrice(ctx, result.Products); err != nil {
        result.DegradedFields = append(result.DegradedFields, "price")
        s.enrichPriceFromCache(result.Products)  // 用缓存兜底
    }

    return result, nil
}
```

---

## 五、降级预案设计（Playbook）

### 预案模板

```yaml
# degradation-playbook.yaml
playbook:
  name: "库存服务降级预案"
  service: inventory-service
  owner: 交易团队
  last_drill: 2025-12-15    # 上次演练时间
  next_drill: 2026-03-15    # 下次演练时间

  triggers:
    - condition: "inventory-service 错误率 > 50% 持续 2 分钟"
      alert_channel: "#oncall-trade"
      auto_action: false    # 是否自动执行

  steps:
    - step: 1
      action: "确认故障范围"
      commands:
        - "检查 inventory-service 的 Pod 状态: kubectl get pods -l app=inventory"
        - "检查错误日志: kubectl logs -l app=inventory --tail=100"
        - "检查依赖的 MySQL 状态"
      duration: "2 分钟"

    - step: 2
      action: "开启降级开关"
      commands:
        - "curl -X PUT config-center/feature-flags/real_time_inventory -d 'false'"
      effect: "库存检查改为查询 Redis 缓存，不再调用 inventory-service"
      risk: "缓存库存可能不准确，可能超卖"
      duration: "1 分钟"

    - step: 3
      action: "通知相关方"
      notify:
        - "#oncall-trade: 库存服务已降级"
        - "产品经理: 页面库存可能不准确"
        - "客服团队: 可能有用户反馈超卖"

    - step: 4
      action: "监控降级效果"
      check:
        - "下单成功率是否恢复"
        - "缓存命中率是否正常"
        - "是否有超卖发生"

  recovery:
    - step: 1
      action: "确认服务恢复"
      check:
        - "inventory-service 错误率 < 1% 持续 5 分钟"
        - "P99 延迟回到正常水平"

    - step: 2
      action: "同步缓存与数据库库存"
      commands:
        - "执行库存同步任务: curl -X POST inventory-service/sync"

    - step: 3
      action: "关闭降级开关"
      commands:
        - "curl -X PUT config-center/feature-flags/real_time_inventory -d 'true'"

    - step: 4
      action: "复盘"
      check:
        - "确认无超卖"
        - "写故障报告"
```

### 降级演练

```bash
# 混沌工程：模拟依赖故障
# 使用 ChaosBlade 注入故障

# 模拟 inventory-service 延迟
blade create dubbo delay \
  --service com.example.InventoryService \
  --time 3000 \
  --offset 500

# 模拟 inventory-service 异常
blade create dubbo throwCustomException \
  --service com.example.InventoryService \
  --exception java.lang.RuntimeException

# 模拟网络丢包
blade create network loss \
  --percent 50 \
  --interface eth0 \
  --destination-ip 10.0.1.50

# 验证降级是否生效
# 1. 下单是否仍然成功
# 2. 是否触发了 fallback
# 3. 断路器是否打开
# 4. 监控是否有告警
```

---

## 六、依赖治理最佳实践

### 依赖治理原则

| 原则 | 说明 | 实践 |
|------|------|------|
| 依赖最小化 | 能不依赖就不依赖 | 定期 review 依赖是否必要 |
| 弱依赖异步化 | 弱依赖尽量用消息队列 | 通知、积分等走 MQ |
| 强依赖有 fallback | 即使是强依赖也要有兜底 | 缓存、默认值、人工介入 |
| 依赖可观测 | 每个依赖调用都有监控 | 成功率、延迟、超时率 |
| 定期演练 | 验证降级预案有效 | 每月一次故障注入演练 |
| 依赖有 owner | 每个依赖明确负责人 | 故障时知道找谁 |

### 依赖健康看板

```yaml
# Grafana Dashboard 设计
panels:
  - title: "依赖健康总览"
    type: table
    columns:
      - 依赖服务
      - 当前状态（Green/Yellow/Red）
      - 成功率（最近 5 分钟）
      - P99 延迟
      - 断路器状态
      - 降级状态

  - title: "各依赖成功率趋势"
    type: timeseries
    queries:
      - expr: |
          rate(rpc_client_requests_total{status="success"}[5m])
          /
          rate(rpc_client_requests_total[5m])
        legend: "{{ dependency }}"

  - title: "断路器状态"
    type: stat
    queries:
      - expr: circuit_breaker_state
        thresholds:
          - value: 0    # Closed
            color: green
          - value: 1    # Half-Open
            color: yellow
          - value: 2    # Open
            color: red
```

---

## 七、排查清单

### 依赖故障排查

| 检查项 | 方法 | 判断标准 |
|-------|------|---------|
| 哪个依赖出问题了 | ServiceMap + 错误率监控 | 错误率突增的服务 |
| 该依赖是强还是弱 | 查依赖分类文档 | 决定是否需要紧急修复 |
| 降级开关是否生效 | 检查 Feature Flag | 开关打开后成功率恢复 |
| Fallback 逻辑是否正常 | 检查 fallback 日志 | 有 fallback 触发记录 |
| 断路器是否在工作 | 检查断路器指标 | 高失败率时应 Open |
| 故障是否在蔓延 | 检查上游服务的健康 | 上游不应被拖垮 |
| 降级预案是否可执行 | 按 Playbook 操作 | 每一步都有明确指令 |
| 恢复后数据是否一致 | 检查缓存与数据库 | 降级期间的数据需要同步 |
