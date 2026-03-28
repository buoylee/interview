# 容器监控体系

没有监控的 Kubernetes 集群就是在裸奔。容器环境比传统部署多了一层抽象——Pod 会漂移、容器会重启、节点会驱逐。如果你还在用 SSH 登录服务器看日志的方式排查问题，那在 K8s 环境下基本行不通。你需要一套完整的可观测体系：指标采集、日志聚合、告警通知，缺一不可。

---

## 一、cAdvisor 原理与指标

### 1.1 cAdvisor 是什么

cAdvisor（Container Advisor）是 Google 开源的容器资源监控工具，直接内嵌在 kubelet 中，无需单独部署。

```
工作原理：
┌─────────────────────────────────────────────┐
│  kubelet                                     │
│  ├── cAdvisor（内嵌）                         │
│  │   ├── 读取 /sys/fs/cgroup/* 获取资源用量    │
│  │   ├── 读取 /proc/<pid>/* 获取进程信息       │
│  │   ├── 通过 containerd/CRI 获取容器元数据    │
│  │   └── 暴露 /metrics/cadvisor 端点          │
│  └── 暴露 /metrics 端点（kubelet 自身指标）     │
└─────────────────────────────────────────────┘
```

### 1.2 核心指标

```bash
# cAdvisor 暴露的关键指标（Prometheus 格式）

# CPU 指标
container_cpu_usage_seconds_total          # CPU 累计使用时间（秒）
container_cpu_user_seconds_total           # 用户态 CPU 时间
container_cpu_system_seconds_total         # 内核态 CPU 时间
container_cpu_cfs_periods_total            # CFS 调度周期总数
container_cpu_cfs_throttled_periods_total  # 被节流的周期数
container_cpu_cfs_throttled_seconds_total  # 被节流的总时间

# 内存指标
container_memory_usage_bytes               # 内存使用量（含 page cache）
container_memory_working_set_bytes         # 工作集内存（K8s 用这个判 OOM）
container_memory_rss                       # RSS 内存
container_memory_cache                     # page cache
container_memory_swap                      # swap 使用量

# 网络指标
container_network_receive_bytes_total      # 接收字节数
container_network_transmit_bytes_total     # 发送字节数
container_network_receive_errors_total     # 接收错误数
container_network_transmit_errors_total    # 发送错误数
container_network_receive_packets_dropped_total  # 接收丢包数

# 磁盘 IO 指标
container_fs_reads_bytes_total             # 读取字节数
container_fs_writes_bytes_total            # 写入字节数
container_fs_usage_bytes                   # 文件系统使用量
container_fs_limit_bytes                   # 文件系统总容量
```

### 1.3 注意事项

```
# container_memory_usage_bytes vs container_memory_working_set_bytes
#
# usage_bytes = RSS + cache（包含可回收的 page cache）
# working_set_bytes = RSS + 活跃 cache（K8s OOM 判断依据）
#
# 监控告警应该基于 working_set_bytes，而不是 usage_bytes
# 否则你会收到大量假告警——应用只是读了很多文件（page cache 增大）
```

---

## 二、kube-state-metrics vs metrics-server

### 2.1 对比

| 维度 | metrics-server | kube-state-metrics |
|------|---------------|-------------------|
| 数据来源 | kubelet 的 summary API | Kubernetes API Server |
| 指标类型 | 实时资源用量（CPU/内存） | 对象状态（Deployment 副本数、Pod 状态等） |
| 用途 | HPA/VPA 的数据源，`kubectl top` | Prometheus 监控，告警 |
| 存储 | 仅保留最新值（内存中） | 无存储，作为 Prometheus exporter |
| 部署要求 | 集群必须有（HPA 依赖） | 可选，但强烈推荐 |

### 2.2 metrics-server

```bash
# 部署 metrics-server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# 验证
kubectl top nodes
# NAME        CPU(cores)   CPU%   MEMORY(bytes)   MEMORY%
# node-1      1847m        23%    14328Mi         44%
# node-2      2103m        26%    16284Mi         51%

kubectl top pods -n production
# NAME                      CPU(cores)   MEMORY(bytes)
# my-app-7b9c5d4f6-x2k4j   324m         512Mi
# my-app-7b9c5d4f6-m8n3p   298m         487Mi
```

### 2.3 kube-state-metrics

```bash
# 部署
kubectl apply -f https://github.com/kubernetes/kube-state-metrics/releases/latest/download/kube-state-metrics.yaml

# 关键指标
kube_pod_status_phase                          # Pod 状态（Pending/Running/Failed）
kube_pod_container_status_restarts_total        # 容器重启次数
kube_pod_container_status_terminated_reason     # 终止原因（OOMKilled/Error）
kube_deployment_spec_replicas                   # 期望副本数
kube_deployment_status_replicas_available       # 可用副本数
kube_node_status_condition                      # 节点状态
kube_pod_container_resource_requests            # 资源 request
kube_pod_container_resource_limits              # 资源 limit
kube_horizontalpodautoscaler_status_current_replicas  # HPA 当前副本数
```

---

## 三、node-exporter 在 K8s 中的部署

node-exporter 采集宿主机级别的指标（CPU、内存、磁盘、网络），补充 cAdvisor 不覆盖的节点层面信息。

### 3.1 DaemonSet 部署

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-exporter
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: node-exporter
  template:
    metadata:
      labels:
        app: node-exporter
    spec:
      hostPID: true
      hostNetwork: true
      containers:
      - name: node-exporter
        image: prom/node-exporter:v1.7.0
        args:
        - "--path.rootfs=/host"
        - "--path.procfs=/host/proc"
        - "--path.sysfs=/host/sys"
        - "--collector.filesystem.mount-points-exclude=^/(dev|proc|sys|var/lib/docker/.+)($|/)"
        ports:
        - containerPort: 9100
          hostPort: 9100
        volumeMounts:
        - name: rootfs
          mountPath: /host
          readOnly: true
          mountPropagation: HostToContainer
      volumes:
      - name: rootfs
        hostPath:
          path: /
      tolerations:
      - operator: Exists    # 在所有节点上运行，包括 master
```

### 3.2 关键指标

```bash
# CPU
node_cpu_seconds_total                    # 各 CPU 各模式的累计时间
node_load1 / node_load5 / node_load15    # 系统负载

# 内存
node_memory_MemTotal_bytes               # 总内存
node_memory_MemAvailable_bytes           # 可用内存
node_memory_Buffers_bytes + node_memory_Cached_bytes  # 缓存

# 磁盘
node_disk_io_time_seconds_total          # 磁盘 IO 时间
node_disk_read_bytes_total               # 读字节数
node_disk_written_bytes_total            # 写字节数
node_filesystem_avail_bytes              # 文件系统可用空间

# 网络
node_network_receive_bytes_total         # 网卡接收字节
node_network_transmit_bytes_total        # 网卡发送字节
node_network_receive_errs_total          # 接收错误
node_netstat_Tcp_CurrEstab               # 当前 TCP 连接数
```

---

## 四、Kubernetes 监控架构全景

### 4.1 kube-prometheus-stack

kube-prometheus-stack（原 prometheus-operator）是 K8s 监控的事实标准，一键部署完整的监控栈：

```
┌─────────────────────────────────────────────────────────────────────┐
│                    kube-prometheus-stack                              │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │  Prometheus   │  │   Grafana    │  │ AlertManager │               │
│  │  Operator     │  │              │  │              │               │
│  └──────┬───────┘  └──────────────┘  └──────────────┘               │
│         │ 自动管理                                                    │
│  ┌──────▼───────┐                                                    │
│  │  Prometheus   │◄──── ServiceMonitor / PodMonitor（自动发现目标）    │
│  │  Server       │                                                    │
│  └──────┬───────┘                                                    │
│         │ 抓取                                                        │
│  ┌──────▼──────────────────────────────────────────────┐             │
│  │  数据源                                              │             │
│  │  ├── kubelet/cAdvisor  → 容器级 CPU/内存/网络/IO     │             │
│  │  ├── kube-state-metrics → K8s 对象状态               │             │
│  │  ├── node-exporter      → 节点级 CPU/内存/磁盘/网络   │             │
│  │  ├── kube-apiserver     → API Server 请求延迟/错误    │             │
│  │  ├── kube-scheduler     → 调度延迟/失败               │             │
│  │  ├── etcd               → etcd 延迟/大小              │             │
│  │  └── 应用自身 /metrics   → 业务指标                   │             │
│  └─────────────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Helm 安装

```bash
# 添加 Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# 安装（含 Prometheus、Grafana、AlertManager、node-exporter、kube-state-metrics）
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.retention=30d \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=100Gi \
  --set grafana.adminPassword=your-secure-password \
  --set alertmanager.alertmanagerSpec.storage.volumeClaimTemplate.spec.resources.requests.storage=10Gi

# 验证
kubectl get pods -n monitoring
# NAME                                                     READY   STATUS    AGE
# alertmanager-kube-prometheus-stack-alertmanager-0         2/2     Running   2m
# kube-prometheus-stack-grafana-7b9c5d4f6-x2k4j            3/3     Running   2m
# kube-prometheus-stack-kube-state-metrics-6f8b9c7d-m8n3p  1/1     Running   2m
# kube-prometheus-stack-operator-5c4d6e7f-k9l2m             1/1     Running   2m
# prometheus-kube-prometheus-stack-prometheus-0             2/2     Running   2m
# node-exporter-xxxxx                                      1/1     Running   2m
```

### 4.3 ServiceMonitor 自定义抓取

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: my-app-monitor
  namespace: monitoring
  labels:
    release: kube-prometheus-stack    # 必须匹配 Prometheus Operator 的 label selector
spec:
  namespaceSelector:
    matchNames:
    - production
  selector:
    matchLabels:
      app: my-app
  endpoints:
  - port: metrics          # Service 中定义的端口名
    interval: 15s
    path: /metrics
    scrapeTimeout: 10s
```

---

## 五、关键监控指标

### 5.1 Pod 级指标

```promql
# CPU 使用率（相对于 request）
sum(rate(container_cpu_usage_seconds_total{container!="", pod=~"my-app-.*"}[5m])) by (pod)
/
sum(kube_pod_container_resource_requests{resource="cpu", pod=~"my-app-.*"}) by (pod)

# 内存使用率（相对于 limit）
sum(container_memory_working_set_bytes{container!="", pod=~"my-app-.*"}) by (pod)
/
sum(kube_pod_container_resource_limits{resource="memory", pod=~"my-app-.*"}) by (pod)

# CPU 节流率
sum(rate(container_cpu_cfs_throttled_periods_total{container!="", pod=~"my-app-.*"}[5m])) by (pod)
/
sum(rate(container_cpu_cfs_periods_total{container!="", pod=~"my-app-.*"}[5m])) by (pod)

# 网络吞吐量
sum(rate(container_network_receive_bytes_total{pod=~"my-app-.*"}[5m])) by (pod) * 8  # bps

# 容器重启次数
kube_pod_container_status_restarts_total{pod=~"my-app-.*"}
```

### 5.2 Node 级指标

```promql
# 节点 CPU 使用率
1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) by (instance)

# 节点内存使用率
1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)

# 节点磁盘使用率
1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})

# 节点网络带宽
rate(node_network_receive_bytes_total{device="eth0"}[5m]) * 8  # bps

# 节点 Pod 数量（是否接近上限）
kubelet_running_pods / kube_node_status_allocatable{resource="pods"}
```

---

## 六、Grafana Dashboard 推荐

### 6.1 推荐 Dashboard ID

| Dashboard | Grafana ID | 说明 |
|-----------|-----------|------|
| Kubernetes / Views / Global | 15757 | 集群全局概览 |
| Kubernetes / Views / Namespaces | 15758 | 命名空间级资源使用 |
| Kubernetes / Views / Nodes | 15759 | 节点级详情 |
| Kubernetes / Views / Pods | 15760 | Pod 级详情 |
| Node Exporter Full | 1860 | 节点硬件指标详情 |
| Kubernetes Cluster Monitoring | 3119 | 经典集群监控 |
| CoreDNS | 15762 | DNS 解析性能 |

### 6.2 导入方式与自定义建议

```bash
# Grafana UI：左侧菜单 → Dashboards → Import → 输入 ID → Load
# 或通过 Helm values 中 grafana.dashboards 预装

# 自定义 Dashboard 面板建议：
# 集群概览：总 CPU/内存使用率、节点状态、Pod 状态分布、Top 10 CPU/内存 Pod
# Pod 详情：CPU/内存使用量 vs Request vs Limit、CPU 节流率、网络收发、重启次数
```

---

## 七、日志采集方案

### 7.1 方案对比

| 维度 | DaemonSet（Fluentd/Fluent Bit） | Sidecar |
|------|-------------------------------|---------|
| 资源开销 | 每节点一个 Pod | 每应用一个容器 |
| 配置灵活性 | 统一配置，无法按应用定制 | 每个应用可独立配置 |
| 日志来源 | 读取节点 `/var/log/containers/` | 直接读取应用日志文件或 stdout |
| 适用场景 | 大部分场景 | 多租户、日志格式差异大 |
| 性能影响 | 低（共享） | 高（每个 Pod 多一个容器） |

### 7.2 DaemonSet Fluent Bit 核心配置

```yaml
# DaemonSet 部署要点：
# - 挂载 /var/log 和 /var/log/containers（hostPath）
# - 资源限制：requests cpu 100m / memory 128Mi，limits memory 512Mi
# - 通过 ConfigMap 挂载 fluent-bit.conf

# fluent-bit.conf 核心段落
[INPUT]
    Name              tail
    Path              /var/log/containers/*.log
    Parser            cri
    Tag               kube.*
    Mem_Buf_Limit     50MB         # 防止内存暴涨
    Skip_Long_Lines   On

[FILTER]
    Name                kubernetes
    Match               kube.*
    Kube_URL            https://kubernetes.default.svc:443
    Merge_Log           On          # 合并 JSON 日志字段
    K8S-Logging.Parser  On

[OUTPUT]
    Name            es             # 或 loki、s3
    Match           *
    Host            elasticsearch.logging.svc
    Port            9200
    Logstash_Format On
```

### 7.3 Fluent Bit vs Fluentd

| 维度 | Fluent Bit | Fluentd |
|------|-----------|---------|
| 语言 | C | Ruby + C |
| 内存占用 | ~15MB | ~60MB |
| 插件数量 | 较少但覆盖主流 | 700+ 插件 |
| 定位 | 日志采集器（DaemonSet） | 日志聚合器（集中处理） |
| 推荐架构 | Fluent Bit 采集 → Fluentd 聚合 → ES/S3 | 或单独使用 Fluent Bit 直连 |

---

## 八、告警规则设计

### 8.1 关键告警规则

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: container-alerts
  namespace: monitoring
  labels:
    release: kube-prometheus-stack
spec:
  groups:
  - name: container.rules
    rules:
    # Pod OOMKilled
    - alert: PodOOMKilled
      expr: |
        kube_pod_container_status_terminated_reason{reason="OOMKilled"} > 0
      for: 0m
      labels:
        severity: warning
      annotations:
        summary: "Pod {{ $labels.pod }} OOMKilled"
        description: "容器 {{ $labels.container }} 在 {{ $labels.namespace }} 中被 OOM 杀掉"

    # CrashLoopBackOff
    - alert: PodCrashLooping
      expr: |
        rate(kube_pod_container_status_restarts_total[15m]) * 60 * 15 > 3
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "Pod {{ $labels.pod }} 持续崩溃重启"
        description: "{{ $labels.namespace }}/{{ $labels.pod }} 在 15 分钟内重启 {{ $value }} 次"

    # CPU 节流严重
    - alert: ContainerCPUThrottlingHigh
      expr: |
        sum(increase(container_cpu_cfs_throttled_periods_total{container!=""}[5m])) by (container, pod, namespace)
        /
        sum(increase(container_cpu_cfs_periods_total{container!=""}[5m])) by (container, pod, namespace)
        > 0.25
      for: 15m
      labels:
        severity: warning
      annotations:
        summary: "容器 {{ $labels.container }} CPU 节流率 {{ $value | humanizePercentage }}"
        description: "{{ $labels.namespace }}/{{ $labels.pod }} 的 {{ $labels.container }} CPU 节流率超过 25%"

    # 内存使用接近 limit
    - alert: ContainerMemoryNearLimit
      expr: |
        container_memory_working_set_bytes{container!=""}
        /
        kube_pod_container_resource_limits{resource="memory"}
        > 0.9
      for: 10m
      labels:
        severity: warning
      annotations:
        summary: "容器内存使用率超过 90%"
        description: "{{ $labels.namespace }}/{{ $labels.pod }} 内存使用已达 limit 的 {{ $value | humanizePercentage }}"

    # Pod 长时间 Pending
    - alert: PodPendingTooLong
      expr: |
        kube_pod_status_phase{phase="Pending"} == 1
      for: 15m
      labels:
        severity: warning
      annotations:
        summary: "Pod {{ $labels.pod }} 持续 Pending"
        description: "{{ $labels.namespace }}/{{ $labels.pod }} 已 Pending 超过 15 分钟，检查资源是否不足"

    # 节点磁盘空间不足
    - alert: NodeDiskSpaceLow
      expr: |
        (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) < 0.1
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "节点 {{ $labels.instance }} 磁盘空间低于 10%"

    # Deployment 副本数不足
    - alert: DeploymentReplicasMismatch
      expr: |
        kube_deployment_spec_replicas != kube_deployment_status_replicas_available
      for: 10m
      labels:
        severity: warning
      annotations:
        summary: "Deployment {{ $labels.deployment }} 可用副本数不足"
        description: "期望 {{ $value }} 个副本但实际可用数不匹配，持续 10 分钟"
```

### 8.2 告警分级策略

| 级别 | 触发条件 | 通知方式 | 响应时间 |
|------|---------|---------|---------|
| Critical | OOM、CrashLoop、节点 NotReady | 电话 + IM | < 5 分钟 |
| Warning | CPU 节流 > 25%、内存 > 90%、Pending > 15min | IM 群消息 | < 30 分钟 |
| Info | 资源使用率上升趋势、HPA 扩缩容事件 | 邮件 / Dashboard | 下一个工作日 |

---

## 九、监控体系排查清单

```
□ 基础设施检查
  ├─ metrics-server 正常运行（kubectl top 有输出）
  ├─ kube-state-metrics 数据正常（kube_pod_* 指标可查询）
  ├─ node-exporter DaemonSet 在所有节点运行
  └─ cAdvisor 指标可通过 kubelet 采集

□ Prometheus 检查
  ├─ Prometheus targets 页面所有目标 UP
  ├─ ServiceMonitor 配置 label 与 Prometheus Operator 匹配
  ├─ 存储空间充足（retention 周期内数据完整）
  └─ 抓取间隔合理（15-30s 之间）

□ 告警检查
  ├─ AlertManager 配置正确（路由、接收器）
  ├─ 关键告警（OOM、CrashLoop、节点故障）有电话通知
  ├─ 告警不能太多导致告警疲劳
  └─ 定期检查告警静默规则，避免遗漏

□ 日志检查
  ├─ Fluent Bit DaemonSet 在所有节点运行
  ├─ 日志索引正常写入（检查 ES/Loki 索引）
  ├─ 日志保留策略设置合理（不要撑爆存储）
  └─ 关键应用日志可在 Grafana/Kibana 中查询到
```
