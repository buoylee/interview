# 容量规划

容量规划是 SRE 最务实的工作之一：给系统准备足够的资源来承接业务增长和流量峰值，同时不浪费钱。做少了系统崩溃，做多了老板心疼。好的容量规划不是拍脑袋"加机器"，而是用数据和模型把资源需求量化出来，让每一分钱都花在刀刃上。

---

## 一、容量模型构建

### 1.1 容量模型的核心要素

```
容量模型 = 流量模型 × 单实例承载能力 × 安全系数

流量模型：
  - 日常峰值 QPS
  - 增长趋势（月环比、年同比）
  - 季节性波动（大促、节假日）

单实例承载能力：
  - 通过压测获得
  - 在满足 SLO 条件下的最大 QPS

安全系数：
  - 通常 1.3 ~ 2.0
  - 高可用冗余（N+1、N+2）
  - 爆发流量缓冲
```

### 1.2 容量计算公式

```
所需实例数 = (峰值QPS × 增长系数) / 单实例最大QPS × 安全系数

实际示例：
  峰值 QPS：5000
  年增长预期：50%（增长系数 = 1.5）
  单实例 QPS（压测结果，P99 < 200ms）：800
  安全系数：1.5（包含 N+1 冗余）

  所需实例数 = (5000 × 1.5) / 800 × 1.5
             = 7500 / 800 × 1.5
             = 9.375 × 1.5
             = 14.06
             ≈ 15 台
```

### 1.3 分层容量模型

```
┌──────────────────────────────────────────────┐
│ 接入层（Nginx / Gateway）                     │
│ 瓶颈：并发连接数、带宽                        │
│ 指标：connections、bandwidth                   │
├──────────────────────────────────────────────┤
│ 应用层（API 服务）                             │
│ 瓶颈：CPU、内存、线程/协程数                   │
│ 指标：QPS、P99 延迟、CPU 利用率                │
├──────────────────────────────────────────────┤
│ 缓存层（Redis / Memcached）                   │
│ 瓶颈：内存、连接数、命中率                     │
│ 指标：ops/sec、内存使用率、命中率              │
├──────────────────────────────────────────────┤
│ 数据层（MySQL / PostgreSQL）                  │
│ 瓶颈：连接数、IOPS、CPU                       │
│ 指标：QPS、慢查询数、连接使用率                │
├──────────────────────────────────────────────┤
│ 消息层（Kafka / RabbitMQ）                    │
│ 瓶颈：分区数、磁盘吞吐                        │
│ 指标：消息吞吐量、消费延迟                     │
└──────────────────────────────────────────────┘

每一层都需要独立评估容量，木桶效应——最短的那块板决定整体容量。
```

---

## 二、压测驱动的容量规划流程

### 2.1 标准流程

```
Step 1: 明确 SLO
  "order-service P99 延迟 < 500ms，错误率 < 0.1%"

Step 2: 搭建压测环境
  - 与生产环境配置一致（或已知差异可换算）
  - 数据量级与生产一致

Step 3: 基准压测
  - 单实例极限测试：持续加压直到 SLO 被打破
  - 记录打破点的 QPS 和资源使用情况

Step 4: 验证线性扩展
  - 2 实例 → 4 实例 → 8 实例
  - 验证是否线性扩展，找出扩展瓶颈

Step 5: 构建容量模型
  - 绘制 QPS-资源曲线
  - 建立扩缩容公式

Step 6: 全链路压测
  - 模拟真实流量比例（浏览:搜索:下单 = 100:20:3）
  - 验证整体容量与各层瓶颈
```

### 2.2 压测结果记录表

```markdown
| 测试场景 | 实例规格 | 实例数 | QPS | P50(ms) | P99(ms) | CPU% | Mem% | 错误率 | 是否满足SLO |
|----------|---------|--------|-----|---------|---------|------|------|--------|------------|
| 基准     | 4C8G    | 1      | 200 | 12      | 45      | 30%  | 40%  | 0%     | ✅          |
| 中等负载 | 4C8G    | 1      | 500 | 18      | 120     | 55%  | 45%  | 0%     | ✅          |
| 高负载   | 4C8G    | 1      | 800 | 35      | 380     | 78%  | 50%  | 0.02%  | ✅          |
| 极限     | 4C8G    | 1      | 1000| 85      | 650     | 92%  | 55%  | 0.5%   | ❌ P99超标  |
| 过载     | 4C8G    | 1      | 1200| 250     | 2100    | 99%  | 60%  | 3.2%   | ❌          |

结论：单实例安全容量 = 800 QPS（4C8G 规格）
```

### 2.3 扩展性验证

```bash
# wrk 脚本 - 逐步加压
for qps in 500 1000 2000 4000 8000; do
    echo "=== Testing at ${qps} QPS ==="
    wrk -t4 -c100 -d60s -R${qps} \
        --latency \
        http://order-service:8080/api/orders \
        2>&1 | tee "capacity_test_${qps}.txt"
    sleep 30  # 等系统恢复
done
```

---

## 三、成本优化

### 3.1 Right-sizing（资源合理配置）

```
常见问题：
  申请 8C16G，实际长期 CPU < 20%、内存 < 30%
  → 典型的过度配置（over-provisioning）

诊断方法：
  观察 7-30 天内的资源使用率分布
  重点看 P95 和 P99（不是平均值）
```

```promql
# Prometheus 查询：过去 7 天 CPU P95
quantile_over_time(0.95,
  container_cpu_usage_rate{
    namespace="production",
    container="order-service"
  }[7d]
)

# 过去 7 天内存使用率 P95
quantile_over_time(0.95,
  container_memory_working_set_bytes{
    namespace="production",
    container="order-service"
  }[7d]
)
/ on(pod)
kube_pod_container_resource_limits{resource="memory"}
```

**Right-sizing 决策矩阵：**

| CPU P95 | 内存 P95 | 建议 |
|---------|---------|------|
| < 30% | < 40% | 降配（缩小一档规格） |
| 30-60% | 40-70% | 合理（保持不变） |
| 60-80% | 70-85% | 关注（评估是否需要扩容） |
| > 80% | > 85% | 扩容（升配或加实例） |

### 3.2 云实例成本优化

```
成本优化三板斧：

1. 预留实例（Reserved Instance）
   适用：长期稳定运行的基础服务
   节省：30%-60%
   风险：提前锁定，灵活性降低

2. Spot / 竞价实例
   适用：无状态服务、批处理任务、压测环境
   节省：60%-90%
   风险：随时可能被回收（2 分钟通知）

3. Savings Plan
   适用：确定长期用量但规格可能变化
   节省：20%-40%
   风险：承诺用量
```

**混合部署策略：**

```yaml
# 应用部署成本优化示例
deployment:
  order-service:
    # 基准负载：预留实例（稳定保障）
    base_capacity:
      instance_type: reserved
      count: 10
      spec: c5.xlarge  # 4C8G

    # 日常波动：按需实例
    elastic_capacity:
      instance_type: on-demand
      min: 0
      max: 5
      scale_trigger: cpu > 60%

    # 大促峰值：Spot 实例（可被回收的无状态实例）
    burst_capacity:
      instance_type: spot
      max: 20
      fallback: on-demand  # Spot 不可用时回退
```

---

## 四、自动扩缩容策略

### 4.1 Kubernetes HPA 配置

**基于 CPU 的扩缩容（最基础）：**

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  minReplicas: 3
  maxReplicas: 30
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 65
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60   # 扩容等待 1 分钟确认
      policies:
        - type: Percent
          value: 100                    # 一次最多翻倍
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300   # 缩容等待 5 分钟确认
      policies:
        - type: Percent
          value: 10                     # 一次最多缩 10%
          periodSeconds: 120
```

**基于自定义指标（推荐）：**

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-service-hpa-custom
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  minReplicas: 3
  maxReplicas: 30
  metrics:
    # 基于 P99 延迟
    - type: Pods
      pods:
        metric:
          name: http_request_duration_p99
        target:
          type: AverageValue
          averageValue: "300m"   # 300ms
    # 基于队列深度
    - type: External
      external:
        metric:
          name: rabbitmq_queue_messages
          selector:
            matchLabels:
              queue: order-queue
        target:
          type: Value
          value: "1000"
```

### 4.2 扩缩容策略对比

| 策略 | 触发条件 | 优势 | 劣势 |
|------|---------|------|------|
| **CPU/内存** | 资源使用率阈值 | 简单、通用 | 滞后，不反映业务状态 |
| **自定义指标** | QPS、延迟、队列深度 | 贴近业务 | 需要额外监控组件 |
| **定时扩缩** | CronJob | 可预测流量场景 | 不适应突发 |
| **预测性扩缩** | 基于历史流量趋势 | 提前准备 | 需要稳定流量模式 |

### 4.3 预测性扩缩容（KEDA + Prometheus）

```yaml
# 使用 KEDA 的 Cron 触发器 + Prometheus 触发器组合
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: order-service-scaledobject
spec:
  scaleTargetRef:
    name: order-service
  minReplicaCount: 3
  maxReplicaCount: 50
  triggers:
    # 工作日晚高峰提前扩容
    - type: cron
      metadata:
        timezone: Asia/Shanghai
        start: "30 18 * * 1-5"   # 周一至周五 18:30
        end: "30 22 * * 1-5"     # 周一至周五 22:30
        desiredReplicas: "15"
    # 基于实时 QPS 动态扩容
    - type: prometheus
      metadata:
        serverAddress: http://prometheus:9090
        metricName: http_requests_per_second
        query: |
          sum(rate(http_requests_total{service="order-service"}[2m]))
        threshold: "500"
```

---

## 五、季节性与突发流量应对

### 5.1 大促容量预案

```
大促容量规划时间线：

T-30 天：容量评估
  □ 确认大促目标（预期 GMV、峰值流量倍数）
  □ 梳理核心链路（哪些服务参与）
  □ 基于去年数据 + 增长预期估算峰值

T-14 天：全链路压测
  □ 按预估峰值的 1.5 倍进行压测
  □ 逐层验证各组件容量
  □ 发现瓶颈并修复

T-7 天：资源准备
  □ 按压测结果扩容
  □ 预热缓存、连接池、JIT
  □ 数据库读写分离就位

T-1 天：最终检查
  □ 全链路健康检查
  □ 降级开关测试
  □ 值班人员 + 通讯渠道确认

T 日：大促执行
  □ 实时监控大屏
  □ 值班团队就位
  □ 降级预案随时待命

T+1 天：复盘
  □ 实际流量 vs 预估
  □ 资源使用率分析
  □ 经验教训沉淀
```

### 5.2 流量突发应对策略

```
预防性措施：
  1. 弹性伸缩兜底（HPA 配置合理的 maxReplicas）
  2. 限流保护（按用户 / IP / 接口限流）
  3. 缓存预热（大促前主动加载热点数据）
  4. 服务降级方案（非核心功能可关闭）

应急响应：
  1. 手动扩容（kubectl scale 或云控制台）
  2. 开启限流（Sentinel / Nginx limit_req）
  3. 启动降级（关闭推荐、评论等非核心）
  4. 静态化降级（核心页面出静态版本）
```

```bash
# 紧急扩容命令
kubectl scale deployment order-service --replicas=30 -n production

# 验证扩容状态
kubectl rollout status deployment/order-service -n production

# 紧急限流（Nginx 级别）
# 在 nginx.conf 中预留限流配置，通过 ConfigMap 开关控制
kubectl patch configmap nginx-config -n production \
  --type merge \
  -p '{"data":{"rate-limit-enabled":"true","rate-limit-rps":"1000"}}'
```

---

## 六、容量规划文档模板

```markdown
# [服务名称] 容量规划文档

## 1. 服务概述
- 服务名称：order-service
- 服务级别：T0（核心服务）
- 依赖服务：product-service, inventory-service, MySQL, Redis, Kafka

## 2. 流量模型
- 日常峰值 QPS：5,000
- 大促预估峰值 QPS：25,000（5x）
- 月增长率：8%
- 流量特征：工作日晚高峰 18:00-22:00

## 3. 单实例容量（压测数据）
| 指标 | 值 | 条件 |
|------|-----|------|
| 最大 QPS | 800 | P99 < 500ms, 错误率 < 0.1% |
| CPU 使用率 | 78% | 在 800 QPS 时 |
| 内存使用 | 4.2GB | 在 800 QPS 时 |
| 实例规格 | 4C8G | c5.xlarge |
| 压测日期 | 2026-03-15 | |

## 4. 容量规划
### 日常场景
  需求 QPS：5,000
  安全系数：1.5
  所需实例：5000 / 800 × 1.5 = 10 台

### 大促场景
  需求 QPS：25,000
  安全系数：1.3（有降级兜底）
  所需实例：25000 / 800 × 1.3 = 41 台

## 5. 成本估算
| 场景 | 实例数 | 月成本(按需) | 优化后成本 | 节省 |
|------|--------|-------------|-----------|------|
| 日常 | 10 | ¥15,000 | ¥9,000(预留) | 40% |
| 大促增量 | 31 | ¥46,500 | ¥9,300(Spot) | 80% |

## 6. 扩缩容策略
  HPA: CPU > 65% 扩容，< 30% 缩容
  日常范围：8-15 台
  大促范围：8-50 台

## 7. 依赖服务容量
| 依赖 | 当前规格 | 当前容量 | 大促是否需扩容 |
|------|---------|---------|---------------|
| MySQL 主库 | 8C32G | 3000 QPS | 需升配至 16C64G |
| Redis 集群 | 3 主 3 从 | 50K ops/s | 足够 |
| Kafka | 6 broker | 100K msg/s | 足够 |

## 8. 风险与预案
- 风险1：Spot 实例被回收 → 预案：自动回退到按需实例
- 风险2：数据库成为瓶颈 → 预案：读写分离 + 缓存降级
- 风险3：第三方支付限流 → 预案：排队机制 + 用户提示

## 9. 审批
- 编写人：_________
- 审批人：_________
- 日期：_________
```

---

## 七、常见容量规划误区

| 误区 | 问题 | 正确做法 |
|------|------|----------|
| **用平均值规划** | 平均 CPU 30% 但峰值 90%，按平均值规划会不够 | 用 P95/P99 规划 |
| **不做压测拍脑袋** | "感觉 10 台够了" → 上线崩了 | 必须压测获得单实例容量数据 |
| **只看应用层** | 应用层够了但数据库扛不住 | 全链路分层评估 |
| **忽略增长** | 按当前流量规划，3 个月后不够用 | 至少预留 6 个月增长空间 |
| **只扩不缩** | 大促后忘记缩容，白白浪费 | 自动扩缩容 + 大促后检查 |
| **安全系数过大** | 3 倍冗余太浪费 | 通常 1.3-1.5 即可，配合弹性 |
| **忽略冷启动** | 新实例启动需要预热（JIT、缓存） | 预热策略 + 扩容前置 |
| **线性外推** | 假设 10 实例能线性扩展到 100 | 验证扩展瓶颈（锁、数据库连接等） |

### 容量规划检查清单

```
□ 有明确的 SLO 作为容量是否充足的判断标准
□ 通过压测获得了每个关键服务的单实例容量
□ 全链路各层（接入/应用/缓存/数据库/消息）都做了容量评估
□ 容量模型包含了增长预期（至少 6 个月）
□ 配置了合理的 HPA（包含 scaleUp/scaleDown behavior）
□ 大促有专门的容量预案和扩容计划
□ 成本优化使用了混合实例策略
□ 有定期（月度/季度）容量评审机制
□ 容量规划文档存档且保持更新
□ 新服务上线前完成了容量评估
```
