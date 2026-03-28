# SLI / SLO / SLA 体系

SLI、SLO、SLA 是 SRE 的核心概念，它们将"系统可靠性"从主观感受变成了可量化、可追踪、可决策的工程实践。没有这套体系，团队就只能在"追求 100% 可用"和"快速迭代"之间来回拉扯，永远找不到平衡点。Google SRE 实践反复证明：**可靠性是一个特性，而非绝对目标**——关键在于定义"多可靠才够"。

---

## 一、核心概念与区别

| 概念 | 全称 | 本质 | 制定者 | 面向对象 |
|------|------|------|--------|----------|
| **SLI** | Service Level Indicator | 度量指标 | 工程团队 | 内部 |
| **SLO** | Service Level Objective | 目标值 | 工程团队 + 产品 | 内部 |
| **SLA** | Service Level Agreement | 商业合同 | 商务/法务 | 外部客户 |

三者的关系：

```
SLI（指标） → SLO（目标） → SLA（承诺）

例如：
SLI = 请求成功率 = 成功请求数 / 总请求数
SLO = 请求成功率 ≥ 99.9%（每 30 天滚动窗口）
SLA = 若月可用性 < 99.9%，赔偿客户当月 10% 费用
```

**关键区别：**

- SLO 是内部目标，比 SLA 更严格（留有余量）
- SLA 是法律合同，违反有赔偿条款
- 没有 SLI 就没有 SLO，没有 SLO 的 SLA 就是空头支票

---

## 二、SLI 选择

### 2.1 四大 SLI 类型

| SLI 类型 | 适用场景 | 典型指标 |
|----------|----------|----------|
| **可用性（Availability）** | 所有服务 | 成功请求数 / 总请求数 |
| **延迟（Latency）** | 用户交互型服务 | P50、P95、P99 响应时间 |
| **正确性（Correctness）** | 数据处理、计算服务 | 正确处理数 / 总处理数 |
| **吞吐量（Throughput）** | 数据管道、批处理 | 单位时间处理量 |

### 2.2 SLI 选择原则

```
1. 选择用户可感知的指标
   ✅ "下单接口 P99 延迟"（用户直接体验）
   ❌ "CPU 使用率"（用户不关心）

2. 越靠近用户越好
   ✅ 在负载均衡器层采集（反映用户真实体验）
   ❌ 在应用内部采集（可能遗漏网络、LB 等环节）

3. 不超过 3-5 个 SLI
   贪多嚼不烂，重点指标才能驱动行动

4. 区分关键路径与非关键路径
   下单、支付 → 高 SLO
   商品评论、推荐 → 较低 SLO
```

### 2.3 按服务类型选择 SLI

| 服务类型 | 推荐 SLI |
|----------|----------|
| API 网关 / Web 服务 | 可用性 + 延迟 |
| 数据库 / 存储 | 可用性 + 延迟 + 正确性 |
| 消息队列 | 可用性 + 吞吐量 + 延迟（端到端） |
| 批处理管道 | 正确性 + 吞吐量 + 新鲜度 |
| CDN / 静态资源 | 可用性 + 延迟 |

---

## 三、如何度量 SLI

### 3.1 基于 Prometheus 的 SLI 查询

**可用性 SLI：**

```promql
# 过去 30 天的请求成功率
sum(increase(http_requests_total{
  service="order-service",
  status!~"5.."
}[30d]))
/
sum(increase(http_requests_total{
  service="order-service"
}[30d]))
```

**延迟 SLI（基于 Histogram）：**

```promql
# P99 延迟
histogram_quantile(0.99,
  sum by (le) (
    rate(http_request_duration_seconds_bucket{
      service="order-service"
    }[5m])
  )
)

# 延迟 SLI：请求在 500ms 内完成的比例
sum(increase(http_request_duration_seconds_bucket{
  service="order-service",
  le="0.5"
}[30d]))
/
sum(increase(http_request_duration_seconds_count{
  service="order-service"
}[30d]))
```

**正确性 SLI：**

```promql
# 订单处理正确率
sum(increase(order_process_total{result="correct"}[30d]))
/
sum(increase(order_process_total[30d]))
```

### 3.2 SLI 采集点选择

```
                用户
                 │
          ┌──────▼──────┐
          │   CDN / LB   │  ◄── 最佳采集点（最接近用户）
          └──────┬──────┘
          ┌──────▼──────┐
          │  API Gateway │  ◄── 次选采集点
          └──────┬──────┘
          ┌──────▼──────┐
          │  应用服务    │  ◄── 可用，但可能遗漏网络问题
          └──────┬──────┘
          ┌──────▼──────┐
          │  数据库      │  ◄── 只反映存储层
          └─────────────┘
```

### 3.3 基于日志的 SLI（备选方案）

```bash
# 从 Nginx 访问日志计算可用性
# 适用于尚未接入 Prometheus 的场景
cat access.log | awk '{print $9}' | sort | uniq -c | sort -rn
# 输出类似：
# 98523 200
#   872 304
#   234 502
#    45 503

# 可用性 = (98523 + 872) / (98523 + 872 + 234 + 45) = 99.72%
```

---

## 四、SLO 设定方法

### 4.1 基于历史数据设定

```
步骤：
1. 收集过去 30-90 天的 SLI 数据
2. 计算实际表现（如过去 90 天可用性 = 99.95%）
3. SLO 设在略低于实际表现的位置
   实际 99.95% → SLO 设为 99.9%
4. 预留一定的 Error Budget 空间给迭代
```

**Prometheus Recording Rule 示例：**

```yaml
groups:
  - name: slo_recording
    interval: 1m
    rules:
      # 可用性 SLI（5分钟窗口）
      - record: sli:availability:rate5m
        expr: |
          sum(rate(http_requests_total{
            service="order-service", status!~"5.."}[5m]))
          /
          sum(rate(http_requests_total{
            service="order-service"}[5m]))

      # 30 天滚动可用性
      - record: sli:availability:ratio_30d
        expr: |
          sum(increase(http_requests_total{
            service="order-service", status!~"5.."}[30d]))
          /
          sum(increase(http_requests_total{
            service="order-service"}[30d]))

      # Error Budget 剩余比例
      - record: slo:error_budget:remaining
        expr: |
          1 - (
            (1 - sli:availability:ratio_30d)
            /
            (1 - 0.999)
          )
```

### 4.2 基于用户体验设定

```
核心问题：用户在什么情况下会明显感到不满？

研究参考：
- 页面加载 > 3s：53% 移动用户会离开（Google 研究）
- 错误率 > 1%：用户开始投诉
- 支付超时 > 10s：放弃率显著上升

方法：
1. 分析用户行为数据（转化率 vs 延迟/错误率）
2. 找到"体验拐点"
3. SLO 设在拐点之上
```

### 4.3 SLO 的窗口选择

| 窗口类型 | 说明 | 适用场景 |
|----------|------|----------|
| **30 天滚动** | 持续计算最近 30 天 | 大多数服务（推荐） |
| **日历月** | 每月 1 日重置 | 与 SLA 账期对齐 |
| **季度** | 90 天窗口 | 低流量服务 |

---

## 五、Error Budget（错误预算）

### 5.1 核心概念

```
Error Budget = 1 - SLO

如果 SLO = 99.9%
那么 Error Budget = 0.1%

30 天内允许的错误时间：
30 天 × 24 小时 × 60 分钟 × 0.1% = 43.2 分钟

30 天内若有 100 万次请求：
允许失败的请求 = 100 万 × 0.1% = 1000 次
```

### 5.2 不同 SLO 对应的 Error Budget

| SLO | Error Budget / 30天 | 允许的停机时间 | 适用场景 |
|-----|---------------------|---------------|----------|
| 99% | 1% | 7.2 小时 | 内部工具 |
| 99.5% | 0.5% | 3.6 小时 | 非核心服务 |
| 99.9% | 0.1% | 43.2 分钟 | 核心 API |
| 99.95% | 0.05% | 21.6 分钟 | 支付、认证 |
| 99.99% | 0.01% | 4.3 分钟 | 基础设施 |

### 5.3 Error Budget 消耗告警

```yaml
# 当 Error Budget 消耗过快时告警
groups:
  - name: error_budget_alerts
    rules:
      # 快速消耗：1 小时内消耗了 2% 的月度 Budget
      - alert: ErrorBudgetFastBurn
        expr: slo:error_budget:remaining < 0.98 and slo:error_budget:remaining > 0.90
        for: 5m
        labels:
          severity: P1
        annotations:
          summary: "order-service Error Budget 快速消耗中，剩余 {{ $value | humanizePercentage }}"

      # 预算即将耗尽
      - alert: ErrorBudgetLow
        expr: slo:error_budget:remaining < 0.20
        for: 10m
        labels:
          severity: P0
        annotations:
          summary: "order-service Error Budget 剩余不足 20%，暂停非关键变更"
```

---

## 六、Error Budget Policy

Error Budget Policy 定义了当预算消耗到不同水平时，团队应该采取的行动。**没有 Policy 的 Error Budget 只是一个数字**。

### 6.1 标准 Policy 模板

| Budget 剩余 | 状态 | 行动 |
|-------------|------|------|
| **> 50%** | 健康 | 正常迭代，鼓励创新 |
| **20% - 50%** | 警告 | 加强变更评审，减少高风险发布 |
| **5% - 20%** | 危险 | 冻结非关键变更，集中精力提升可靠性 |
| **< 5%** | 耗尽 | 全面冻结发布，所有工程师投入可靠性工作 |

### 6.2 预算耗尽时的具体行动

```
当 Error Budget 耗尽（< 5%）时：

1. 发布冻结
   - 停止所有新功能发布
   - 仅允许可靠性修复和安全补丁
   - 需 SRE 负责人审批才能例外发布

2. 强制复盘
   - 回顾近期所有导致 Budget 消耗的事件
   - 识别系统性问题（而非个别事件）

3. 可靠性冲刺
   - 团队进入"可靠性冲刺"模式
   - 优先处理技术债务、自动化、监控完善
   - 持续至 Budget 恢复到 20% 以上

4. 升级汇报
   - 向管理层汇报 Budget 状态
   - 说明对发布节奏的影响
   - 请求必要资源支持
```

### 6.3 团队共识与签署

```markdown
## Error Budget Policy Agreement

服务名称：PerfShop Order Service
SLO：99.9% 可用性（30 天滚动窗口）
Policy 生效日期：2026-01-01

签署人：
- 产品负责人：___________（同意 Budget 耗尽时冻结发布）
- 工程负责人：___________（负责可靠性改进执行）
- SRE 负责人：___________（负责 Budget 监控与决策）

评审频率：每季度回顾一次 SLO 和 Policy 是否合理
```

---

## 七、SLA 与商业承诺

### 7.1 SLA 的构成要素

```
一份 SLA 通常包含：

1. 服务范围定义
   "本 SLA 覆盖 PerfShop API 的以下端点..."

2. 可用性承诺
   "月度可用性不低于 99.9%"

3. 排除条款
   - 计划内维护窗口
   - 客户端原因导致的错误
   - 不可抗力（自然灾害、政策变更等）

4. 度量方式
   "可用性 = (总分钟数 - 不可用分钟数) / 总分钟数 × 100%"

5. 赔偿方案
   | 月可用性 | 赔偿比例 |
   |---------|---------|
   | 99.0% - 99.9% | 月费 10% |
   | 95.0% - 99.0% | 月费 25% |
   | < 95.0% | 月费 50% |

6. 申报流程
   "客户需在事件发生后 30 天内提交赔偿申请"
```

### 7.2 SLO 与 SLA 的安全距离

```
原则：SLO 永远比 SLA 更严格

SLA 承诺 99.9% → SLO 设为 99.95%

为什么？
- 当 SLO 被打破时，团队有时间修复
- 不至于每次 SLO 违反都触发商业赔偿
- 给团队预留了"安全缓冲区"

       ┌──────────────────────────────────────────┐
       │         SLO (99.95%)                     │ ← 内部告警
       │    ┌──────────────────────────────────┐   │
       │    │      SLA (99.9%)                 │   │ ← 赔偿红线
       │    │                                  │   │
       │    └──────────────────────────────────┘   │
       └──────────────────────────────────────────┘
```

---

## 八、实际案例：为 PerfShop 设计 SLI/SLO

### 8.1 服务拆分与 SLI 定义

```yaml
# PerfShop SLI/SLO 定义文件
services:
  order-service:
    tier: T0  # 核心服务
    slis:
      - name: availability
        description: "下单接口成功率"
        query: |
          sum(rate(http_requests_total{service="order-service",
            endpoint="/api/orders", status!~"5.."}[5m]))
          / sum(rate(http_requests_total{service="order-service",
            endpoint="/api/orders"}[5m]))
        slo: 0.999  # 99.9%
        window: 30d

      - name: latency
        description: "下单接口 P99 延迟低于 500ms 的请求比例"
        query: |
          sum(rate(http_request_duration_seconds_bucket{service="order-service",
            endpoint="/api/orders", le="0.5"}[5m]))
          / sum(rate(http_request_duration_seconds_count{service="order-service",
            endpoint="/api/orders"}[5m]))
        slo: 0.99  # 99%
        window: 30d

  product-service:
    tier: T1  # 重要服务
    slis:
      - name: availability
        description: "商品列表接口成功率"
        query: |
          sum(rate(http_requests_total{service="product-service",
            status!~"5.."}[5m]))
          / sum(rate(http_requests_total{service="product-service"}[5m]))
        slo: 0.999
        window: 30d

      - name: latency
        description: "商品列表 P99 延迟低于 200ms"
        query: |
          sum(rate(http_request_duration_seconds_bucket{service="product-service",
            le="0.2"}[5m]))
          / sum(rate(http_request_duration_seconds_count{
            service="product-service"}[5m]))
        slo: 0.995
        window: 30d

  recommendation-service:
    tier: T2  # 非核心服务
    slis:
      - name: availability
        description: "推荐接口成功率"
        slo: 0.995  # 99.5%
        window: 30d
```

### 8.2 Grafana Dashboard 设计

```
┌─────────────────────────────────────────────────────────────┐
│ PerfShop SLO Dashboard                                      │
├─────────────────┬─────────────────┬─────────────────────────┤
│ 当前可用性       │ Error Budget     │ Budget 消耗趋势         │
│   99.94%        │   剩余 62%       │   📈 [趋势图]           │
│ SLO: 99.9% ✅   │   剩余 18.7 天   │                         │
├─────────────────┴─────────────────┴─────────────────────────┤
│ SLI 趋势（过去 30 天）                                       │
│ [可用性折线图] [延迟折线图] [错误率折线图]                    │
├─────────────────────────────────────────────────────────────┤
│ Budget 消耗事件                                              │
│ ┌──────────┬──────────┬──────────────┬─────────────────┐    │
│ │ 时间      │ 持续时长  │ 消耗 Budget   │ 原因            │    │
│ │ 3/15 14:00│ 12 分钟  │ 8.3%         │ DB 连接池满      │    │
│ │ 3/22 09:30│ 5 分钟   │ 3.5%         │ 发布回滚         │    │
│ └──────────┴──────────┴──────────────┴─────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 8.3 SLO 运营节奏

```
每日：
  - 自动检查 Error Budget 剩余量
  - Budget 消耗 > 5% 的事件自动创建 Ticket

每周：
  - SLO 周报（自动生成）
  - 回顾本周 Budget 消耗事件
  - 讨论是否需要调整发布计划

每月：
  - SLO 月度 Review
  - 对比各服务 SLO 达成情况
  - 讨论 SLO 是否需要调整

每季度：
  - SLO 与 Error Budget Policy 全面评审
  - 结合业务变化调整服务分级
  - 更新 SLA 条款（如需要）
```

---

## 九、常见问题与检查清单

### 9.1 SLO 设定常见误区

| 误区 | 正确做法 |
|------|----------|
| 追求 100% 可用 | 100% 是错误目标，成本无限高且限制迭代 |
| SLO 过于宽松（如 95%） | 用户早已不满，SLO 形同虚设 |
| 所有服务同一 SLO | 按服务重要性分级设定 |
| 只看平均值 | 用分位数（P99）和比例，平均值会掩盖长尾 |
| SLO 设了不看 | 必须有配套的 Error Budget Policy 和运营流程 |
| 频繁修改 SLO | 季度评审调整，避免来回漂移 |

### 9.2 落地检查清单

```
□ 识别了关键用户旅程（Critical User Journeys）
□ 为每个关键旅程选择了 SLI（不超过 3-5 个）
□ SLI 在尽可能靠近用户的位置采集
□ 基于历史数据和用户体验设定了 SLO
□ 配置了 Prometheus Recording Rules 持续计算 SLI
□ 搭建了 SLO Dashboard（Grafana）
□ 配置了 Error Budget 消耗告警（快速消耗 + 即将耗尽）
□ 制定了 Error Budget Policy 并获得产品/管理层签署
□ 建立了 SLO 运营节奏（周报 + 月度 Review）
□ SLO 比 SLA 至少严格 0.05%
□ 团队对 SLO 有共识（不是 SRE 自己玩的数字）
```
