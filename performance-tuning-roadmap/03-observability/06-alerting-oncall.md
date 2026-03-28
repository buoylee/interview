# 告警与 On-call

## 告警设计原则：告警症状而非原因

这是告警设计中最重要的原则，来自 Google SRE 实践：

**Alert on symptoms, not causes.**

```
症状（Symptom）：用户可感知的影响
    "API 响应时间 P99 > 2s"
    "错误率 > 5%"
    "下单成功率 < 95%"

原因（Cause）：系统内部的技术状态
    "CPU 使用率 > 80%"
    "MySQL 连接数 > 100"
    "JVM Old Gen > 70%"
```

**为什么不应该告警原因？**

1. CPU 80% 不一定有问题 —— 如果延迟正常、错误率为零，那 CPU 跑满说明你在充分利用资源
2. 原因类告警噪声大 —— 每次发布可能短暂 CPU 飙升，触发告警但没有实际影响
3. 你无法穷举所有原因 —— 总有你想不到的原因导致问题，但症状一定能感知到

**正确做法：**
- P0/P1 告警只告症状（用户感知的）
- 原因类指标作为 P2/P3 预警或 Dashboard 观察项
- 排查时从症状出发，用 Dashboard 下钻到原因

---

## 告警分级

| 级别 | 含义 | 示例 | 响应时间 | 通知方式 |
|------|------|------|---------|---------|
| **P0** | 服务完全不可用 | 全站 5xx > 50%、核心功能 100% 失败 | 5 分钟内响应 | 电话 + 短信 + IM |
| **P1** | 严重降级 | P99 延迟 > 5s、错误率 > 10%、部分用户受影响 | 15 分钟内响应 | 短信 + IM |
| **P2** | 部分影响 | 某个非核心接口错误率升高、从库同步延迟 | 1 小时内处理 | IM 群通知 |
| **P3** | 预警/趋势 | 磁盘使用率 > 80%、证书即将过期 | 工作时间处理 | IM 群通知 |

**具体告警规则示例：**

```yaml
# P0: 服务不可用
- alert: ServiceDown
  expr: up{job="order-service"} == 0
  for: 2m
  labels:
    severity: P0
  annotations:
    summary: "order-service 实例 {{ $labels.instance }} 不可达"
    runbook: "https://wiki.internal/runbooks/service-down"

# P1: 高错误率
- alert: HighErrorRate
  expr: |
    sum(rate(http_requests_total{service="order-service", status=~"5.."}[5m]))
    /
    sum(rate(http_requests_total{service="order-service"}[5m])) > 0.05
  for: 3m
  labels:
    severity: P1
  annotations:
    summary: "order-service 错误率 {{ $value | humanizePercentage }}"

# P1: 高延迟
- alert: HighLatency
  expr: |
    histogram_quantile(0.99,
      sum by (le) (rate(http_request_duration_seconds_bucket{service="order-service"}[5m]))
    ) > 2
  for: 5m
  labels:
    severity: P1
  annotations:
    summary: "order-service P99 延迟 {{ $value }}s，超过 2s 阈值"

# P2: 连接池接近饱和
- alert: DBPoolNearSaturation
  expr: |
    hikaricp_connections_active / hikaricp_connections_max > 0.8
  for: 10m
  labels:
    severity: P2
  annotations:
    summary: "数据库连接池使用率 {{ $value | humanizePercentage }}"

# P3: 磁盘预警
- alert: DiskSpaceWarning
  expr: |
    (node_filesystem_avail_bytes / node_filesystem_size_bytes) < 0.2
  for: 30m
  labels:
    severity: P3
  annotations:
    summary: "磁盘剩余空间 {{ $value | humanizePercentage }}"
```

**`for` 持续时间的设计：**
- `for: 0m`：一触发就告警，适合 P0 级别的"服务完全挂了"
- `for: 3-5m`：避免短暂波动误报，适合 P1 级别
- `for: 10-30m`：趋势类预警，确认是持续趋势而非瞬时
- 一般不超过 15 分钟，否则告警延迟太高

---

## Alertmanager 配置

Prometheus 负责产生告警，Alertmanager 负责路由、去重、分组、抑制和通知。

```yaml
# alertmanager.yml

global:
  resolve_timeout: 5m

route:
  receiver: 'default-webhook'
  group_by: ['alertname', 'service']   # 相同 alertname+service 的告警合并
  group_wait: 30s                       # 新分组等待 30s 聚合后再发
  group_interval: 5m                    # 同一分组新告警的发送间隔
  repeat_interval: 4h                   # 未恢复的告警重复通知间隔
  routes:
    # P0 走电话
    - match:
        severity: P0
      receiver: 'pagerduty-critical'
      group_wait: 10s                   # P0 等待时间要短
      repeat_interval: 15m             # P0 每 15 分钟重复通知

    # P1 走即时通讯 + 短信
    - match:
        severity: P1
      receiver: 'slack-oncall'
      repeat_interval: 1h

    # P2/P3 走群通知
    - match_re:
        severity: P[23]
      receiver: 'slack-alerts'
      repeat_interval: 4h

receivers:
  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: '<pagerduty-key>'
        severity: critical

  - name: 'slack-oncall'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/xxx'
        channel: '#oncall'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'

  - name: 'slack-alerts'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/xxx'
        channel: '#alerts'

  - name: 'default-webhook'
    webhook_configs:
      - url: 'http://alert-handler:8080/webhook'
```

### 抑制规则（Inhibition）

当 P0 告警触发时，抑制同一服务的 P1/P2 告警，避免同一问题的连锁告警刷屏：

```yaml
inhibit_rules:
  - source_match:
      severity: P0
    target_match_re:
      severity: P[12]
    equal: ['service']   # 仅当 service 标签相同时抑制
```

### 静默规则（Silence）

在计划维护或已知问题期间临时关闭告警。通过 Alertmanager UI 或 API 创建：

```bash
# amtool 创建静默
amtool silence add \
  alertname="HighErrorRate" \
  service="order-service" \
  --comment="planned deployment" \
  --duration=30m
```

---

## 告警疲劳

**告警疲劳比没有告警更危险。** 当团队每天收到几十上百条告警时，人们开始忽略所有告警 —— 包括真正需要关注的那些。

### 告警疲劳的常见原因

1. **阈值太敏感**：CPU > 70% 就告警，但 70% 是正常状态
2. **告警原因而非症状**：GC 暂停 > 100ms，但对用户延迟没有影响
3. **缺少 `for` 持续时间**：瞬时波动频繁触发
4. **告警没有恢复自动关闭**：需要手动 ACK 或关闭
5. **没有定期清理**：废弃服务的告警还在响

### 告警收敛策略

```
告警收敛措施
├── 合理设置阈值（基于历史数据，而非拍脑袋）
├── 必须有 for 持续时间（避免抖动）
├── 利用 group_by 合并同类告警
├── 利用 inhibit_rules 抑制连锁告警
├── 定期回顾（每月 review，删除无效告警）
│   └── 如果一个告警过去 3 个月从未需要人工介入，删掉它
├── 告警必须 actionable（每个告警都有对应的 Runbook）
│   └── 如果你收到告警但不知道该做什么，这个告警就不应该存在
└── 黄金指标原则：先告核心指标，再补充次要指标
```

---

## On-call 轮转

### 值班制度设计

```
┌─────────────────────────────────────────────────┐
│ Primary On-call：第一响应人                       │
│ └── 收到 P0/P1 告警后 5-15 分钟内响应            │
│                                                   │
│ Secondary On-call：备份响应人                     │
│ └── Primary 无响应时自动升级（15 分钟后）         │
│                                                   │
│ 轮转周期：1 周                                    │
│ 交接时间：工作日上午（非周五下午）                │
│ 交接内容：当前活跃的问题、进行中的变更            │
└─────────────────────────────────────────────────┘
```

### 升级流程

```
T+0min   告警触发 → 通知 Primary On-call
T+5min   Primary 未 ACK → 电话 Primary
T+15min  Primary 仍未响应 → 升级到 Secondary
T+30min  问题未缓解 → 升级到 Tech Lead
T+60min  P0 仍未恢复 → 升级到 Engineering Manager
```

### On-call 质量保障

- **每次 On-call 事件必须有 Post-mortem（事后回顾）**
- 统计指标：MTTR（平均恢复时间）、On-call 被叫次数/周、误报率
- 如果某人 On-call 一周被叫超过 3 次，说明告警需要优化或系统可靠性需要提升
- On-call 工作量算入正常工作负载，不是额外义务

---

## Runbook 编写

每一条 P0/P1 告警都必须有对应的 Runbook（操作手册）。

### Runbook 模板

```markdown
# Runbook: HighErrorRate (order-service)

## 告警含义
order-service 的 5xx 错误率超过 5%，持续 3 分钟以上。

## 影响范围
用户无法正常下单。

## 排查步骤

### 1. 确认影响范围
- 打开 Grafana Dashboard: [链接]
- 检查：是全部接口还是某个接口？是全部实例还是某个实例？

### 2. 查看错误日志
- Kibana 查询: `service: "order-service" AND level: "ERROR" AND @timestamp > now-15m`
- 关注异常类型和堆栈

### 3. 常见原因 & 处理

| 原因 | 判断依据 | 处理方式 |
|------|---------|---------|
| 数据库连接超时 | 日志中有 ConnectionTimeout | 检查 DB 状态，必要时重启连接池 |
| 下游服务不可达 | 日志中有 ConnectException | 检查下游服务状态 |
| OOM | 日志中有 OutOfMemoryError | 重启 Pod，排查内存泄漏 |
| 发布导致 | 与最近发布时间吻合 | 回滚到上一版本 |

### 4. 缓解措施
- 重启：`kubectl rollout restart deployment/order-service`
- 回滚：`kubectl rollout undo deployment/order-service`
- 限流：在网关层对错误接口临时限流

### 5. 后续
- 创建事故报告 Issue
- 安排 Post-mortem 会议
```

### Runbook 关键要素

1. **每一步都是具体的命令或链接**，而非模糊描述
2. **假设读者是凌晨 3 点被叫醒的人**，大脑不清醒时也能照着做
3. **包含"常见原因"列表**，覆盖历史上出现过的所有情况
4. **包含缓解措施**（先止血再排查）
5. **定期更新**：每次事故后更新 Runbook

---

## 小结

```
告警与 On-call 体系
├── 核心原则：告警症状不告原因
├── 分级：P0(不可用) / P1(降级) / P2(部分) / P3(预警)
├── Alertmanager：路由 + 分组 + 抑制 + 静默
├── 告警疲劳：定期清理、必须 actionable、合理阈值
├── On-call：Primary/Secondary 轮转、升级流程
└── Runbook：每条 P0/P1 告警必须有可操作的手册
```

至此，可观测性体系的三大支柱（Logs、Metrics、Traces）加上告警与 On-call 已经完整覆盖。接下来我们进入压测快速上手，学习如何生成负载来验证系统的性能基线。
