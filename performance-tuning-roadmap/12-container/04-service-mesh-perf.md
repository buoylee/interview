# Service Mesh 性能

Service Mesh 是一把双刃剑。它带来了零侵入的 mTLS、流量管理、可观测性，但代价是每个请求多经过两次代理（出站 sidecar → 入站 sidecar），延迟增加、CPU 和内存开销增大。在决定是否使用 Service Mesh 之前，你必须量化它的性能影响，搞清楚它在什么场景下值得，什么场景下是过度设计。

---

## 一、Service Mesh 架构

### 1.1 数据面 vs 控制面

```
                          控制面（Control Plane）
                    ┌─────────────────────────────┐
                    │  Istiod                      │
                    │  ├── Pilot（配置下发）         │
                    │  ├── Citadel（证书管理）       │
                    │  └── Galley（配置验证）        │
                    └──────────┬──────────────────┘
                               │ xDS（配置推送）
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
   │  Pod A        │    │  Pod B        │    │  Pod C        │
   │ ┌──────────┐  │    │ ┌──────────┐  │    │ ┌──────────┐  │
   │ │  App     │  │    │ │  App     │  │    │ │  App     │  │
   │ └────┬─────┘  │    │ └────┬─────┘  │    │ └────┬─────┘  │
   │      │iptables│    │      │iptables│    │      │iptables│
   │ ┌────▼─────┐  │    │ ┌────▼─────┐  │    │ ┌────▼─────┐  │
   │ │  Envoy   │  │    │ │  Envoy   │  │    │ │  Envoy   │  │
   │ │ (sidecar)│  │    │ │ (sidecar)│  │    │ │ (sidecar)│  │
   │ └──────────┘  │    │ └──────────┘  │    │ └──────────┘  │
   └──────────────┘    └──────────────┘    └──────────────┘
        数据面（Data Plane）
```

### 1.2 请求路径

```
App A 发起请求 → iptables 拦截
    → App A 的 Envoy（outbound）
        → mTLS 加密
            → 网络传输
                → App B 的 Envoy（inbound）
                    → mTLS 解密
                        → App B 接收请求

# 一次服务间调用经过：2 次 Envoy 代理 + 1 次 mTLS 加解密
# 这就是 Service Mesh 的性能开销来源
```

---

## 二、Sidecar 代理开销量化

### 2.1 延迟开销

实际基准测试数据（来自 Istio 官方和社区测试）：

| 场景 | 无 Mesh | 有 Istio Sidecar | 延迟增加 |
|------|---------|-----------------|---------|
| P50 延迟 | 1.2ms | 3.1ms | +1.9ms |
| P90 延迟 | 3.5ms | 6.8ms | +3.3ms |
| P99 延迟 | 8.2ms | 15.6ms | +7.4ms |
| P99.9 延迟 | 15ms | 32ms | +17ms |

```
关键认知：
- Sidecar 增加的延迟是固定开销，约 2-5ms（P50）
- 对于本身延迟 100ms+ 的服务，2-5ms 开销可以接受（约 2-5%）
- 对于本身延迟 5ms 以下的高频内部调用，开销占比可达 50-100%
- 调用链越深，累积延迟越大：10 跳 × 3ms = 30ms 额外延迟
```

### 2.2 CPU 开销

```bash
# 每个 Sidecar Envoy 的 CPU 开销
# 空闲状态：~10-15m CPU
# 1000 RPS：~100-150m CPU
# 5000 RPS：~400-600m CPU

# 实际测量方法
kubectl top pods -n production --containers | grep istio-proxy
# NAME                      CONTAINER       CPU(cores)   MEMORY(bytes)
# my-app-7b9c5d4-x2k4j     istio-proxy     87m          62Mi
# my-app-7b9c5d4-x2k4j     app             324m         512Mi

# istio-proxy 占应用 CPU 的 ~27%，这是正常的
```

### 2.3 内存开销

```bash
# 每个 Sidecar Envoy 的内存开销
# 基础内存：~40-60MB
# 配置量大时（多路由规则、多服务）：~100-150MB
# 极端情况（万级服务发现）：~300MB+

# 集群总开销计算
# 1000 个 Pod × 每个 Sidecar 80MB = 80GB 内存
# 1000 个 Pod × 每个 Sidecar 100m CPU = 100 核 CPU
# 这是一笔不小的开销
```

### 2.4 网络开销

```
# 每次请求增加的网络路径：
# 无 Mesh：App A → 网络 → App B
# 有 Mesh：App A → lo(iptables) → Envoy → 网络 → Envoy → lo(iptables) → App B

# iptables 规则开销：
# Istio 默认通过 iptables REDIRECT 拦截流量
# 每个 Pod 约 50+ 条 iptables 规则
# 大规模集群中 iptables 规则可能影响连接建立速度

# 查看 Istio 注入的 iptables 规则
kubectl exec -it my-pod -c istio-proxy -- iptables -t nat -L -n
```

---

## 三、Istio/Envoy 性能调优

### 3.1 Envoy concurrency 调整

```yaml
# Envoy worker 线程数，默认等于 CPU 核数（容器感知的）
# 对于低流量服务，2 个 worker 足够
apiVersion: networking.istio.io/v1
kind: ProxyConfig
metadata:
  name: my-proxy-config
  namespace: production
spec:
  concurrency: 2    # 减少 worker 线程数 → 降低 CPU 和内存开销

# 或通过 Pod annotation 设置
metadata:
  annotations:
    proxy.istio.io/config: |
      concurrency: 2
```

### 3.2 Sidecar 资源限制

```yaml
# 全局配置（istio-operator 或 Helm values）
meshConfig:
  defaultConfig:
    concurrency: 2

# Sidecar 资源配置
sidecarInjectorWebhook:
  resources:
    requests:
      cpu: 50m
      memory: 64Mi
    limits:
      cpu: 500m
      memory: 256Mi

# 按 namespace 配置（高流量服务给更多资源）
apiVersion: networking.istio.io/v1
kind: Sidecar
metadata:
  name: high-traffic-sidecar
  namespace: high-traffic
spec:
  egress:
  - hosts:
    - "./*"                    # 只发现本 namespace 的服务
    - "istio-system/*"
  # 减少服务发现范围 → 减少 Envoy 配置量 → 降低内存
```

### 3.3 Access Log 调优

```yaml
# Access log 是 Envoy 的重大性能开销之一
# 生产环境建议关闭或采样

# 关闭 access log
meshConfig:
  accessLogFile: ""           # 空字符串表示关闭
  accessLogEncoding: JSON     # 如果开启，用 JSON 格式便于采集

# 按服务配置 access log
apiVersion: telemetry.istio.io/v1
kind: Telemetry
metadata:
  name: disable-accesslog
  namespace: high-traffic
spec:
  accessLogging:
  - disabled: true            # 高流量服务关闭 access log

# 或使用采样
  accessLogging:
  - providers:
    - name: envoy
    filter:
      expression: "response.code >= 400"    # 只记录错误请求
```

### 3.4 Protocol Detection

```yaml
# Istio 默认自动检测协议，这会增加延迟
# 显式声明协议可以跳过检测

apiVersion: v1
kind: Service
metadata:
  name: my-app
spec:
  ports:
  - name: http-web          # 以 http- 开头 → Istio 识别为 HTTP
    port: 8080
    targetPort: 8080
  - name: grpc-api           # 以 grpc- 开头 → Istio 识别为 gRPC
    port: 9090
    targetPort: 9090
  - name: tcp-db             # 以 tcp- 开头 → Istio 识别为 TCP
    port: 3306
    targetPort: 3306
```

### 3.5 连接池调优

```yaml
apiVersion: networking.istio.io/v1
kind: DestinationRule
metadata:
  name: my-app-dr
spec:
  host: my-app
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 1000         # 最大 TCP 连接数
        connectTimeout: 5s
        tcpKeepalive:
          time: 7200s
          interval: 75s
      http:
        h2UpgradePolicy: UPGRADE    # HTTP/1.1 升级到 HTTP/2
        maxRequestsPerConnection: 0  # 0 表示无限制（连接复用）
        maxRetries: 3
        idleTimeout: 300s
    outlierDetection:
      consecutive5xxErrors: 5
      interval: 30s
      baseEjectionTime: 30s
      maxEjectionPercent: 50
```

---

## 四、mTLS 性能影响

### 4.1 mTLS 开销

```
mTLS 握手开销：
- 首次连接：TLS 握手增加 ~1-3ms（取决于密钥交换算法）
- 后续请求：连接复用后无额外握手开销
- 证书验证：~0.1-0.5ms

# 实际影响
# 对于长连接（gRPC、HTTP/2 连接池）：几乎无影响
# 对于短连接（每次请求新建 TCP 连接）：影响显著
# 结论：确保使用连接池和连接复用
```

### 4.2 mTLS 模式

```yaml
# 严格模式：所有流量必须 mTLS
apiVersion: security.istio.io/v1
kind: PeerAuthentication
metadata:
  name: default
  namespace: production
spec:
  mtls:
    mode: STRICT

# 宽容模式：同时接受 mTLS 和明文（迁移阶段使用）
spec:
  mtls:
    mode: PERMISSIVE

# 特定端口禁用 mTLS（如健康检查端口）
spec:
  mtls:
    mode: STRICT
  portLevelMtls:
    8080:
      mode: DISABLE    # 健康检查不走 mTLS
```

### 4.3 证书轮转

```bash
# Istio 默认证书有效期 24 小时，自动轮转
# 证书轮转本身开销很小，但要注意：
# - 大规模集群中同时轮转可能给 Istiod 带来压力
# - Istiod 的证书签发能力是有限的

# 查看证书信息
istioctl proxy-config secret <pod-name> -o json | jq '.dynamicActiveSecrets[0].secret.tlsCertificate.certificateChain'

# 监控证书轮转
istio_agent_cert_expiry_seconds    # 证书过期时间
istio_agent_cert_rotation_count    # 证书轮转次数
```

---

## 五、链路追踪集成

### 5.1 Envoy 自动注入 Trace Header

```
Envoy 自动处理分布式追踪 Header：
- 如果请求带了 trace header → Envoy 传播
- 如果请求没有 trace header → Envoy 生成新的
- 支持的 header 格式：

| Header 类型 | Header 名称 |
|------------|-------------|
| B3（Zipkin） | x-b3-traceid, x-b3-spanid, x-b3-parentspanid, x-b3-sampled |
| W3C Trace Context | traceparent, tracestate |
| Jaeger | uber-trace-id |
| Datadog | x-datadog-trace-id, x-datadog-parent-id |
```

### 5.2 应用要做的事

```
# 关键点：应用必须传播 trace header！
# Envoy 只能在入站和出站之间关联 trace，但无法穿透应用代码

# 应用需要做的：
# 1. 从入站请求中读取 trace header
# 2. 在调用下游服务时把 trace header 传递过去

# 不需要应用集成 tracing SDK 就能获得基本的链路拓扑
# 但如果想要应用内部的 span（如数据库查询耗时），需要集成 SDK
```

### 5.3 采样率配置

```yaml
# 全局采样率
meshConfig:
  defaultConfig:
    tracing:
      sampling: 1.0          # 1% 采样（生产环境推荐）
      # sampling: 100.0      # 100% 采样（测试环境）

# Tracing provider 配置
meshConfig:
  defaultConfig:
    tracing:
      zipkin:
        address: jaeger-collector.observability:9411
  enableTracing: true

# 高采样率的性能影响
# 100% 采样：CPU 增加 ~5-10%，网络流量增加
# 1% 采样：CPU 增加 < 1%，几乎无感知
# 推荐：生产 0.1-1%，测试 100%
```

---

## 六、何时不用 Service Mesh

### 6.1 开销 vs 收益决策矩阵

```
                        收益高                    收益低
                 ┌─────────────────────┬─────────────────────┐
  开销可接受     │  ✅ 推荐使用          │  ⚠️ 按需评估         │
  （延迟 > 50ms） │  多团队微服务         │  单团队少量服务       │
                 │  合规要求 mTLS        │  已有 SDK 方案       │
                 ├─────────────────────┼─────────────────────┤
  开销不可接受   │  ⚠️ 考虑 Ambient Mesh │  ❌ 不推荐           │
  （延迟 < 5ms） │  核心交易链路         │  单体应用            │
                 │  高频内部调用         │  batch 作业          │
                 └─────────────────────┴─────────────────────┘
```

### 6.2 不适合 Service Mesh 的场景

| 场景 | 原因 |
|------|------|
| 超低延迟调用（< 5ms） | Sidecar 开销占比太大 |
| 极高吞吐量（> 50K RPS 每 Pod） | Envoy CPU 成为瓶颈 |
| 简单架构（< 5 个服务） | 运维复杂度不值得 |
| 批处理/离线任务 | 不需要流量管理和 mTLS |
| 团队缺乏 K8s 运维经验 | Mesh 故障排查门槛高 |
| 资源紧张的边缘环境 | 每个 Pod 多 50-100MB 内存 |

### 6.3 替代方案

```
如果只需要部分 Mesh 能力：
- 只要 mTLS → 用 SPIFFE/cert-manager + 应用集成
- 只要可观测 → 用 OpenTelemetry SDK
- 只要流量管理 → 用 Ingress Controller（Nginx/Traefik）+ 应用端重试
- 只要限流 → 用 API Gateway 或应用端中间件
```

---

## 七、Ambient Mesh（无 Sidecar 模式）

### 7.1 架构

```
传统 Sidecar 模式：每个 Pod 一个 Envoy

Ambient Mesh 模式：
┌──────────────────────────────────────────────┐
│  节点级 ztunnel（零信任隧道）                   │
│  ├── 处理 L4（mTLS、TCP 路由）                 │
│  └── 每个节点一个 DaemonSet                    │
└──────────────────────────────────────────────┘
              │
              ▼ 需要 L7 功能时
┌──────────────────────────────────────────────┐
│  waypoint proxy（共享 L7 代理）                │
│  ├── 处理 L7（HTTP 路由、重试、限流）           │
│  └── 每个 namespace/service 按需部署            │
└──────────────────────────────────────────────┘
```

### 7.2 性能优势

| 维度 | Sidecar 模式 | Ambient Mesh |
|------|-------------|-------------|
| 内存开销 | 每 Pod ~60-100MB | ztunnel 每节点 ~20-30MB，按需的 waypoint |
| CPU 开销 | 每 Pod ~50-150m | ztunnel 共享，节点级别 |
| L4 延迟 | ~2-3ms（经过 Envoy） | ~0.5-1ms（ztunnel 更轻量） |
| L7 延迟 | ~3-5ms | ~3-5ms（需要 waypoint 时与 sidecar 相当） |
| 资源浪费 | 低流量 Pod 的 sidecar 空转 | ztunnel 共享，无空转 |
| 升级影响 | 需重启所有 Pod | ztunnel 滚动更新，不影响应用 |

### 7.3 使用

```bash
# 安装 Istio Ambient 模式
istioctl install --set profile=ambient

# 将 namespace 加入 Ambient Mesh（不需要重启 Pod！）
kubectl label namespace production istio.io/dataplane-mode=ambient

# 按需创建 waypoint proxy（只在需要 L7 功能时）
istioctl x waypoint apply --namespace production --name my-waypoint

# 将服务关联到 waypoint
kubectl label service my-app istio.io/use-waypoint=my-waypoint
```

---

## 八、Service Mesh 性能测试方法

### 8.1 基准测试方案

```bash
# 工具：使用 fortio（Istio 官方推荐的负载测试工具）
# 或 wrk2、hey、vegeta

# 步骤一：无 Mesh 基准
kubectl create namespace no-mesh
kubectl apply -f app.yaml -n no-mesh
fortio load -c 64 -qps 0 -t 60s -json no-mesh.json http://app.no-mesh:8080/api

# 步骤二：有 Mesh 基准
kubectl create namespace with-mesh
kubectl label namespace with-mesh istio-injection=enabled
kubectl apply -f app.yaml -n with-mesh
fortio load -c 64 -qps 0 -t 60s -json with-mesh.json http://app.with-mesh:8080/api

# 步骤三：对比
fortio report -json no-mesh.json with-mesh.json
```

### 8.2 测试矩阵

```
需要覆盖的维度：

| 维度 | 变量 |
|------|------|
| 并发连接数 | 1, 16, 64, 256, 1024 |
| 请求大小 | 1KB, 10KB, 100KB, 1MB |
| 协议 | HTTP/1.1, HTTP/2, gRPC |
| mTLS | 开启 vs 关闭 |
| Access Log | 开启 vs 关闭 |
| Envoy concurrency | 1, 2, 4 |
```

### 8.3 关键测量指标

```bash
# 必须测量的指标
# 1. 延迟分布（P50/P90/P99/P99.9）— 不能只看平均值
# 2. 最大吞吐量（RPS）— 在延迟不超标的前提下
# 3. Envoy CPU 和内存使用量
# 4. 应用 CPU 和内存变化（是否被 Envoy 挤占）
# 5. 连接建立速率（TLS 握手对新连接的影响）

# Prometheus 查询 Envoy 指标
# Envoy 请求延迟
histogram_quantile(0.99,
  sum(rate(istio_request_duration_milliseconds_bucket{reporter="destination"}[5m]))
  by (le, destination_service_name)
)

# Envoy 请求速率
sum(rate(istio_requests_total{reporter="destination"}[5m]))
by (destination_service_name)

# Envoy 错误率
sum(rate(istio_requests_total{reporter="destination", response_code=~"5.*"}[5m]))
/
sum(rate(istio_requests_total{reporter="destination"}[5m]))
```

---

## 九、总结与决策清单

### Service Mesh 引入决策清单

```
□ 评估是否需要 Service Mesh
  ├─ 服务数量是否 > 10 且有跨团队调用？
  ├─ 是否有合规要求（mTLS、审计日志）？
  ├─ 是否需要金丝雀发布、流量镜像等高级流量管理？
  └─ 团队是否有足够的 K8s 运维能力？

□ 性能影响评估
  ├─ 在测试环境完成基准测试（有 Mesh vs 无 Mesh）
  ├─ 评估延迟增加是否在可接受范围
  ├─ 计算整个集群的额外 CPU/内存开销
  └─ 评估调用链深度 × 单跳延迟是否可接受

□ 调优配置
  ├─ 显式声明 Service port 协议（跳过协议检测）
  ├─ 生产环境 access log 关闭或采样
  ├─ 降低 tracing 采样率至 0.1-1%
  ├─ 使用 Sidecar CRD 限制服务发现范围
  └─ 低流量服务降低 Envoy concurrency

□ 考虑 Ambient Mesh
  ├─ 如果主要需求是 mTLS → Ambient 的 ztunnel 足够
  ├─ 只在需要 L7 功能的服务上部署 waypoint
  └─ 资源紧张的集群优先考虑 Ambient
```

### 性能影响速查表

| 配置项 | 默认值 | 调优后 | 性能影响 |
|-------|--------|--------|---------|
| Access log | 开启 | 关闭/采样 | CPU 降低 5-10% |
| Tracing 采样率 | 1% | 0.1% | CPU 降低 1-3% |
| Envoy concurrency | auto（=CPU 核数） | 2 | 内存降低 30-50% |
| 服务发现范围 | 全集群 | 本 namespace | 内存降低 30-60% |
| 协议声明 | 自动检测 | 显式声明 | P99 延迟降低 1-2ms |
| HTTP/2 升级 | 关闭 | 开启 | 连接数减少，延迟降低 |
| mTLS | PERMISSIVE | STRICT | 安全性提升，性能几乎无差 |
