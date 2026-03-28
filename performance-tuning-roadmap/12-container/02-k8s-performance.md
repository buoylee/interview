# K8s 性能调优

Kubernetes 对应用性能的影响远比大多数人以为的深。错误的 resource request 导致调度不均，不合理的 limit 引发 CPU 节流和 OOM，HPA 配置不当造成扩缩容振荡，探针设置不合理让健康的 Pod 被反复重启。Kubernetes 不会自动让你的应用跑得快——它只是提供了工具，用好用坏取决于你。

---

## 一、Resource Request vs Limit 设置策略

### 1.1 基本概念

```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: app
    resources:
      requests:         # 调度依据 + CPU shares 计算
        cpu: "500m"     # 0.5 核
        memory: "512Mi" # 512MB
      limits:           # 硬性上限
        cpu: "2000m"    # 2 核（超过会被节流）
        memory: "1Gi"   # 1GB（超过会被 OOM Kill）
```

### 1.2 Request 和 Limit 的本质

| 维度 | Request | Limit |
|------|---------|-------|
| 调度 | 节点必须有足够的可分配资源 | 不影响调度 |
| CPU | 转换为 `cpu.shares`（1 核 = 1024） | 转换为 `cpu.cfs_quota_us` |
| 内存 | 影响 OOM 评分和驱逐优先级 | 转换为 `memory.limit_in_bytes` |
| 超卖 | 允许（多个 Pod 的 request 总和可超过节点容量） | 不允许（单个容器不能超过其 limit） |

### 1.3 设置策略

```yaml
# 策略一：CPU 不设 limit（Google/社区推荐）
resources:
  requests:
    cpu: "500m"
    memory: "512Mi"
  limits:
    # 不设 cpu limit → 没有 CFS quota → 没有节流
    memory: "1Gi"    # 内存必须设 limit（否则可能吃掉整个节点的内存）

# 策略二：Limit = Request（Guaranteed QoS）
# 适用于延迟敏感型应用
resources:
  requests:
    cpu: "2"
    memory: "4Gi"
  limits:
    cpu: "2"
    memory: "4Gi"

# 策略三：Limit = 2~4 倍 Request（Burstable，最常见）
resources:
  requests:
    cpu: "500m"
    memory: "512Mi"
  limits:
    cpu: "2000m"
    memory: "1Gi"
```

### 1.4 常见错误

```yaml
# 错误一：request 设太低用来"省资源"
requests:
  cpu: "10m"       # 会被调度器认为几乎不用 CPU → 可能和大量 Pod 挤在同一节点
  memory: "32Mi"

# 错误二：limit 设太紧
limits:
  cpu: "100m"      # 0.1 核，启动都够呛
  memory: "128Mi"  # JVM 应用基本不可能

# 错误三：不设 request
# Pod 变成 BestEffort，节点压力大时第一个被驱逐
```

---

## 二、QoS 类别与驱逐优先级

### 2.1 三种 QoS 类别

```
┌─────────────────────────────────────────────────────────┐
│  Guaranteed    │ 所有容器的 request = limit              │
│  （最高优先级）  │ 最后被驱逐                               │
├─────────────────────────────────────────────────────────┤
│  Burstable     │ 至少一个容器设了 request 且 request ≠ limit │
│  （中等优先级）  │ 按内存使用率排序驱逐                       │
├─────────────────────────────────────────────────────────┤
│  BestEffort    │ 没有任何 request 和 limit                │
│  （最低优先级）  │ 第一个被驱逐                              │
└─────────────────────────────────────────────────────────┘
```

### 2.2 驱逐机制

```bash
# kubelet 的驱逐信号（默认配置）
--eviction-hard=memory.available<100Mi,nodefs.available<10%,imagefs.available<15%
--eviction-soft=memory.available<200Mi
--eviction-soft-grace-period=memory.available=1m30s

# 驱逐顺序：
# 1. BestEffort Pod（按内存使用量排序）
# 2. Burstable Pod（按内存使用率超出 request 的比例排序）
# 3. Guaranteed Pod（几乎不会被驱逐，除非系统级进程需要内存）
```

### 2.3 选择建议

| 场景 | 推荐 QoS | 原因 |
|------|---------|------|
| 核心交易系统 | Guaranteed | 不被驱逐，CPU 独占（配合 static CPU Manager） |
| 一般在线服务 | Burstable（CPU 不设 limit） | 灵活利用空闲 CPU，内存有保障 |
| 批处理任务 | Burstable 或 BestEffort | 可被驱逐影响小，充分利用闲置资源 |
| 开发测试环境 | BestEffort | 节省资源，环境不稳定可接受 |

---

## 三、HPA 配置与调优

### 3.1 基本配置

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-app-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app
  minReplicas: 3
  maxReplicas: 50
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70    # 目标 CPU 利用率 70%
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60    # 扩容冷却期
      policies:
      - type: Percent
        value: 50                        # 每次最多扩 50%
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300   # 缩容冷却期（5 分钟）
      policies:
      - type: Percent
        value: 10                        # 每次最多缩 10%
        periodSeconds: 120
```

### 3.2 HPA 调优要点

```
                     目标利用率太低（如 30%）           目标利用率太高（如 90%）
                   ┌────────────────────────┐     ┌────────────────────────┐
扩容               │ 频繁扩容，资源浪费         │     │ 扩容不及时，请求堆积      │
                   └────────────────────────┘     └────────────────────────┘

                     缩容窗口太短                     缩容窗口太长
                   ┌────────────────────────┐     ┌────────────────────────┐
缩容               │ 抖动：刚缩下去又扩回来      │     │ 浪费资源，闲置 Pod 太多   │
                   └────────────────────────┘     └────────────────────────┘
```

```bash
# HPA 的计算公式
desiredReplicas = ceil(currentReplicas × (currentMetricValue / targetMetricValue))

# 例：当前 4 个 Pod，CPU 利用率 85%，目标 70%
desiredReplicas = ceil(4 × (85 / 70)) = ceil(4.86) = 5

# 查看 HPA 状态
kubectl get hpa my-app-hpa -o yaml
kubectl describe hpa my-app-hpa
# 注意看 Conditions 中是否有 ScalingLimited、AbleToScale 等信息
```

### 3.3 自定义指标 HPA

```yaml
# 基于 Prometheus 自定义指标（需要 prometheus-adapter）
metrics:
- type: Pods
  pods:
    metric:
      name: http_requests_per_second
    target:
      type: AverageValue
      averageValue: "1000"    # 每个 Pod 平均 1000 RPS

- type: External
  external:
    metric:
      name: queue_messages_ready
      selector:
        matchLabels:
          queue: "orders"
    target:
      type: AverageValue
      averageValue: "30"      # 每个 Pod 平均处理 30 条队列消息
```

---

## 四、VPA 使用场景

### 4.1 VPA 是什么

VPA（Vertical Pod Autoscaler）自动调整 Pod 的 request 和 limit，而不是调整副本数。

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: my-app-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app
  updatePolicy:
    updateMode: "Auto"     # Off / Initial / Recreate / Auto
  resourcePolicy:
    containerPolicies:
    - containerName: app
      minAllowed:
        cpu: "100m"
        memory: "128Mi"
      maxAllowed:
        cpu: "4"
        memory: "8Gi"
      controlledResources: ["cpu", "memory"]
```

### 4.2 VPA 模式

| 模式 | 行为 | 适用场景 |
|------|------|---------|
| Off | 只产生推荐值，不自动修改 | 初次评估，观察推荐值是否合理 |
| Initial | 只在 Pod 创建时设置推荐值 | 新部署的应用 |
| Recreate | 通过重建 Pod 应用推荐值 | 可接受短暂中断的无状态应用 |
| Auto | 自动更新（当前实现也是重建） | 生产环境谨慎使用 |

### 4.3 VPA 与 HPA 的配合

```
# 原则：不要让 VPA 和 HPA 同时管理同一个指标
# 错误：VPA 管 CPU，HPA 也基于 CPU 扩缩容 → 冲突

# 正确组合：
# VPA 管理 CPU 和内存的 request/limit
# HPA 基于自定义指标（RPS、队列深度）扩缩副本数
```

---

## 五、调度策略

### 5.1 节点亲和性

```yaml
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: node-type
            operator: In
            values: ["high-memory"]
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 80
        preference:
          matchExpressions:
          - key: availability-zone
            operator: In
            values: ["az-1"]
```

### 5.2 Pod 反亲和性（高可用）

```yaml
spec:
  affinity:
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchExpressions:
          - key: app
            operator: In
            values: ["my-app"]
        topologyKey: "kubernetes.io/hostname"
        # 同一个应用的 Pod 不能在同一节点上 → 单节点故障不影响全部副本
```

### 5.3 拓扑分散约束

```yaml
spec:
  topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: DoNotSchedule
    labelSelector:
      matchLabels:
        app: my-app
    # Pod 在各可用区之间均匀分布，最大偏差为 1
```

---

## 六、Pod 资源画像

如何确定一个应用合理的 request 和 limit？不要猜，用数据说话。

### 6.1 数据采集方法

```bash
# 方法一：VPA 推荐值（updateMode: Off）
kubectl describe vpa my-app-vpa
# Recommendation:
#   Container Recommendations:
#     Container Name: app
#     Lower Bound:    Cpu: 100m,  Memory: 256Mi
#     Target:         Cpu: 350m,  Memory: 512Mi
#     Upper Bound:    Cpu: 800m,  Memory: 1Gi
#     Uncapped Target: Cpu: 350m, Memory: 512Mi

# 方法二：Prometheus 查询历史数据
# P95 CPU 使用量（过去 7 天）
quantile_over_time(0.95,
  rate(container_cpu_usage_seconds_total{
    container="app", pod=~"my-app-.*"
  }[5m])[7d:]
)

# P99 内存使用量（过去 7 天）
quantile_over_time(0.99,
  container_memory_working_set_bytes{
    container="app", pod=~"my-app-.*"
  }[7d:]
)
```

### 6.2 资源设置公式

```
CPU request  = P95 CPU 使用量 × 1.2（留 20% 余量）
CPU limit    = 不设 或 request × 3~5 倍
Memory request = P99 内存使用量 × 1.1
Memory limit   = request × 1.2~1.5（内存不适合留太大余量，防止 OOM 前不被驱逐）
```

---

## 七、资源配额与 LimitRange

### 7.1 ResourceQuota

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-alpha-quota
  namespace: team-alpha
spec:
  hard:
    requests.cpu: "20"
    requests.memory: "40Gi"
    limits.cpu: "40"
    limits.memory: "80Gi"
    pods: "100"
    persistentvolumeclaims: "20"
    services.loadbalancers: "2"
```

### 7.2 LimitRange

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: team-alpha
spec:
  limits:
  - type: Container
    default:          # 没设 limit 时的默认值
      cpu: "1"
      memory: "1Gi"
    defaultRequest:   # 没设 request 时的默认值
      cpu: "200m"
      memory: "256Mi"
    min:              # 最小值
      cpu: "50m"
      memory: "64Mi"
    max:              # 最大值
      cpu: "8"
      memory: "16Gi"
    maxLimitRequestRatio:  # limit/request 最大比例
      cpu: "5"
      memory: "3"
  - type: Pod
    max:
      cpu: "16"
      memory: "32Gi"
```

---

## 八、探针对性能的影响

### 8.1 三种探针

```yaml
spec:
  containers:
  - name: app
    # 启动探针：仅在启动阶段使用，成功后交给 liveness
    startupProbe:
      httpGet:
        path: /healthz
        port: 8080
      failureThreshold: 30    # 30 × 10s = 300s 启动时间
      periodSeconds: 10

    # 存活探针：失败则重启容器
    livenessProbe:
      httpGet:
        path: /healthz
        port: 8080
      initialDelaySeconds: 0   # startupProbe 接管启动等待
      periodSeconds: 15
      timeoutSeconds: 3
      failureThreshold: 3      # 连续 3 次失败才重启

    # 就绪探针：失败则从 Service 摘流量
    readinessProbe:
      httpGet:
        path: /ready
        port: 8080
      periodSeconds: 5
      timeoutSeconds: 3
      failureThreshold: 2
      successThreshold: 1
```

### 8.2 探针常见问题

| 问题 | 症状 | 解决 |
|------|------|------|
| liveness 太灵敏 | Pod 反复重启（CrashLoopBackOff） | 增大 failureThreshold 和 periodSeconds |
| liveness 检查依赖外部服务 | 数据库挂了 → Pod 全部重启 → 雪崩 | liveness 只检查进程自身健康 |
| 没有 startupProbe | 慢启动应用被 liveness 杀掉 | 加 startupProbe，给足启动时间 |
| readiness 太松 | 应用还没准备好就接流量 → 请求失败 | readiness 检查真实依赖（缓存预热、连接池就绪） |
| 探针频率太高 | 大量探针请求占用应用资源 | 降低频率，HTTP 探针用轻量端点 |
| 探针 timeout 太短 | GC 暂停导致探针超时 → 重启 | timeout 应大于最大 GC 暂停时间 |

### 8.3 探针设计原则

```
1. liveness 探针要"笨"
   - 只检查进程是否存活，不依赖外部服务
   - /healthz 只返回 200，不查数据库
   - failureThreshold 设大一点（3-5 次）

2. readiness 探针要"聪明"
   - 检查真正的服务可用性
   - /ready 应检查数据库连接池、缓存连通性、依赖服务
   - 失败只是摘流量，不重启

3. startupProbe 用于慢启动应用
   - JVM 应用可能需要 2-3 分钟启动
   - failureThreshold × periodSeconds > 最大启动时间
```

---

## 九、总结对照表

| 调优项 | 推荐做法 | 反模式 |
|-------|---------|--------|
| CPU request | 基于 P95 历史使用量 × 1.2 | 随便写 100m 或 1000m |
| CPU limit | 不设或 request 的 3-5 倍 | 设成和 request 相同（除非要 Guaranteed） |
| Memory limit | request 的 1.2-1.5 倍 | 不设 memory limit |
| HPA 目标利用率 | 60-80% | 太低浪费，太高来不及扩 |
| HPA 缩容窗口 | 300-600s | < 60s（容易抖动） |
| liveness 探针 | 只查进程自身 | 依赖外部服务 |
| readiness 探针 | 检查真实服务可用性 | 和 liveness 用同一个端点 |
| VPA 模式 | Off（只看推荐值） | Auto（生产环境不建议自动重建 Pod） |
| 调度策略 | Pod 反亲和 + 拓扑分散 | 全部调度到同一节点/可用区 |
