# 事故响应

事故响应能力决定了一个团队从"业余"到"专业"的距离。同样是 P0 故障，有的团队 5 分钟内定位并缓解，有的团队 2 小时还在群里互相问"谁来看一下"。区别不在个人能力，而在于**有没有一套成熟的响应流程、明确的角色分工、和可执行的 Playbook**。事故响应不是英雄主义，是工程实践。

---

## 一、事故分级定义

### 1.1 P0-P3 分级标准

| 级别 | 定义 | 用户影响 | 示例 | 响应时间 | 通知范围 |
|------|------|---------|------|---------|---------|
| **P0** | 全站/核心功能完全不可用 | 全部或大部分用户 | 全站 5xx > 50%、支付完全失败、数据库宕机 | 5 分钟 | 全员 + 管理层 |
| **P1** | 核心功能严重降级 | 部分用户明显受影响 | 下单成功率 < 90%、延迟 > 10s、部分区域不可用 | 15 分钟 | 相关团队 + TL |
| **P2** | 非核心功能异常或部分降级 | 少数用户受影响 | 搜索结果异常、推荐失效、某个非核心 API 报错 | 1 小时 | 相关团队 |
| **P3** | 轻微问题或隐患 | 用户基本无感 | 日志报错增多、某个非核心指标异常、性能轻微下降 | 4 小时 | On-call 工程师 |

### 1.2 自动分级规则

```yaml
# 基于告警自动判断事故级别
incident_classification:
  P0:
    conditions:
      - "全站可用性 < 50%"
      - "核心服务（下单/支付）完全不可用"
      - "数据丢失或数据不一致"
    auto_actions:
      - notify: ["all-hands", "management"]
      - create_bridge: true          # 自动拉起 War Room
      - page: ["primary-oncall", "secondary-oncall", "team-lead"]

  P1:
    conditions:
      - "核心服务可用性 < 95%"
      - "核心服务 P99 延迟 > 5s"
      - "影响超过 10% 用户"
    auto_actions:
      - notify: ["team-channel"]
      - page: ["primary-oncall"]

  P2:
    conditions:
      - "非核心服务错误率 > 10%"
      - "核心服务可用性 95%-99%"
    auto_actions:
      - notify: ["team-channel"]

  P3:
    conditions:
      - "非核心指标异常但未影响用户"
      - "资源使用率预警"
    auto_actions:
      - create_ticket: true
```

---

## 二、事故响应流程

### 2.1 完整响应流程

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  发现     │ →  │  响应     │ →  │  缓解     │ →  │  恢复     │ →  │  复盘     │
│ Detect   │    │ Respond  │    │ Mitigate │    │ Recover  │    │ Review   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
  监控告警        确认问题         止血处理         彻底修复         总结改进
  用户报告        拉起团队         降级/回滚        验证恢复         防止再发
  巡检发现        建立沟通         限流/扩容        监控观察
```

### 2.2 各阶段详细动作

**阶段一：发现（Detect）**

```
触发来源：
  1. 监控告警（PagerDuty / 自建告警）
  2. 用户投诉（客服渠道）
  3. 内部发现（巡检、日志异常）
  4. 外部报告（社交媒体、合作伙伴）

关键动作：
  □ 确认告警是否真实（排除误报）
  □ 初步判断影响范围
  □ 确定事故级别（P0-P3）
  □ 通知 On-call 工程师

目标时间：< 5 分钟（从故障发生到被发现）
```

**阶段二：响应（Respond）**

```
关键动作：
  □ On-call 工程师确认（ACK 告警）
  □ 建立沟通渠道（Slack 频道 / 电话会议）
  □ 指定 Incident Commander（IC）
  □ IC 召集必要人员
  □ 开始初步诊断
  □ 发出第一条状态更新

P0 事故响应升级：
  5 分钟内  → On-call 工程师响应
  15 分钟内 → 如未缓解，升级至 Team Lead
  30 分钟内 → 如未缓解，升级至 Engineering Manager
  60 分钟内 → 如未缓解，升级至 VP Engineering
```

**阶段三：缓解（Mitigate）**

```
目标：尽快止血，恢复用户可用，不要求根因修复

常用缓解手段（按优先级）：
  1. 回滚最近变更（最常见的故障原因是变更）
     kubectl rollout undo deployment/order-service -n production

  2. 流量切换（切走故障实例/区域）
     修改 DNS 权重、调整 LB 配置

  3. 扩容（解决容量不足）
     kubectl scale deployment/order-service --replicas=20

  4. 限流（防止雪崩）
     开启 Sentinel/Nginx 限流

  5. 降级（关闭非核心功能保核心）
     开启降级开关，跳过推荐/评论等非核心调用

  6. 重启（万能的临时方案）
     kubectl rollout restart deployment/order-service

核心原则：
  先止血再排查，不要在生产火烧时慢慢 Debug
```

**阶段四：恢复（Recover）**

```
关键动作：
  □ 确认根因
  □ 实施永久修复（或安排修复计划）
  □ 验证修复效果（指标恢复正常）
  □ 监控观察期（至少 30 分钟无异常）
  □ 确认事故关闭
  □ 解散响应团队
  □ 安排事故复盘

注意：
  - 缓解 ≠ 恢复，回滚可以止血但不是最终方案
  - 恢复后保持观察，防止问题复发
  - 记录时间线，为复盘做准备
```

---

## 三、Incident Commander（指挥官）模式

### 3.1 角色定义

```
Incident Commander（IC / 事故指挥官）
  职责：
    - 统筹整个事故响应过程
    - 分配任务给不同角色
    - 做出决策（回滚？扩容？降级？）
    - 控制沟通节奏
    - 决定何时升级

  不做的事：
    ❌ 亲自 Debug（IC 不是最强的排查者）
    ❌ 深入代码排查
    ❌ 只关注某一个方向

  核心能力：
    - 保持冷静和全局视角
    - 快速决策能力
    - 良好的沟通协调能力
```

### 3.2 事故响应角色矩阵

| 角色 | 英文 | 职责 | 人数 |
|------|------|------|------|
| **事故指挥官** | Incident Commander (IC) | 统筹指挥、决策、升级 | 1 |
| **技术负责人** | Tech Lead (TL) | 技术方向判断、排查协调 | 1 |
| **排查工程师** | Investigators | 具体排查、定位根因 | 1-3 |
| **沟通协调** | Communications Lead | 状态更新、内外部沟通 | 1 |
| **记录员** | Scribe | 记录时间线、关键决策 | 1 |

### 3.3 IC 的决策框架

```
IC 在事故中需要反复问的问题：

每 10 分钟循环：
  1. 当前影响范围是什么？（扩大/缩小/不变）
  2. 我们的假设是什么？（根因方向）
  3. 正在做什么？（谁在做什么）
  4. 需要额外资源吗？（人、权限、信息）
  5. 需要升级吗？（时间超预期、影响扩大）
  6. 下一次状态更新在什么时候？

决策优先级：
  1. 用户影响是否在扩大？ → 优先止血
  2. 是否有最近的变更？ → 优先回滚
  3. 是否有明确的根因？ → 针对性修复
  4. 以上都不确定？ → 多路并查 + 降级保护
```

---

## 四、沟通模板

### 4.1 内部通知模板

```markdown
## 🔴 P0 事故通知

**时间**: 2026-03-28 14:30 CST
**影响**: 订单服务不可用，用户无法下单
**影响范围**: 全站所有用户
**当前状态**: 正在排查中

**事故指挥官**: 张三
**沟通渠道**: #incident-20260328 (Slack)
**War Room**: https://meet.google.com/xxx-yyy-zzz

**时间线**:
- 14:25 - 监控告警：order-service 5xx 率 > 50%
- 14:28 - On-call 确认，升级为 P0
- 14:30 - IC 就位，拉起 War Room

**下一次更新**: 14:45 或有重大进展时
```

### 4.2 状态更新模板

```markdown
## 事故更新 #3

**时间**: 2026-03-28 15:15 CST
**状态**: 缓解中

**进展**:
- 根因已定位：14:20 的配置变更导致数据库连接池配置错误
- 已回滚配置变更
- 订单成功率正在恢复（当前 95%，正常值 99.9%）
- 预计 5 分钟内完全恢复

**影响统计（截至当前）**:
- 持续时间：50 分钟
- 受影响订单数：约 2,300 笔
- 已恢复订单：补偿方案制定中

**下一步**:
- 持续监控至指标完全恢复
- 制定用户补偿方案
- 安排事故复盘（计划下周一）

**下一次更新**: 15:30 或事故关闭时
```

### 4.3 外部用户公告模板

```markdown
## 服务异常通知

**发布时间**: 2026-03-28 14:40 CST

我们注意到部分用户在使用下单功能时遇到异常。
我们的技术团队已经在全力排查和处理中。

**受影响服务**: 订单提交
**当前状态**: 处理中
**预计恢复时间**: 我们将尽快提供更新

对于给您带来的不便，我们深表歉意。

---

## 服务恢复通知

**发布时间**: 2026-03-28 15:25 CST

之前影响下单功能的问题已经解决，所有服务已恢复正常。
对于受影响的订单，我们将在 24 小时内进行补偿处理。

如果您仍遇到问题，请联系客服。
再次为给您带来的不便表示歉意。
```

---

## 五、降级预案（Playbook）

### 5.1 Playbook 设计原则

```
一份好的 Playbook：
  ✅ 具体到每一步命令（不是"检查日志"而是"运行 kubectl logs xxx"）
  ✅ 不需要深入理解系统也能执行（凌晨 3 点新人也能跟着做）
  ✅ 有判断分支（如果 A 则做 X，如果 B 则做 Y）
  ✅ 有升级条件（什么时候应该叫人帮忙）
  ✅ 定期演练和更新

一份差的 Playbook：
  ❌ "检查是否有异常"（太模糊）
  ❌ "联系张三"（张三离职了怎么办）
  ❌ 三年没更新，和现实严重脱节
  ❌ 只有 PDF 存在某个角落里没人知道
```

### 5.2 Playbook 模板

```markdown
# Playbook: 订单服务高错误率

## 触发条件
order-service 5xx 错误率 > 5% 持续 3 分钟

## 影响
用户下单失败

## 排查步骤

### Step 1: 确认故障范围
```bash
# 查看 order-service Pod 状态
kubectl get pods -l app=order-service -n production

# 查看最近的错误日志
kubectl logs -l app=order-service -n production --since=5m | grep -i error | tail -20

# 查看错误率趋势
# Grafana Dashboard: https://grafana.internal/d/order-service
```

### Step 2: 判断故障类型
- 如果 Pod 处于 CrashLoopBackOff → 转 Step 3A
- 如果 Pod 都是 Running 但有错误 → 转 Step 3B
- 如果 Pod 数量少于预期 → 转 Step 3C

### Step 3A: Pod 崩溃
```bash
# 查看崩溃原因
kubectl describe pod <pod-name> -n production
kubectl logs <pod-name> -n production --previous

# 检查最近是否有发布
kubectl rollout history deployment/order-service -n production

# 如果是最近发布导致，回滚
kubectl rollout undo deployment/order-service -n production
```

### Step 3B: 应用级错误
```bash
# 检查依赖服务健康状态
curl -s http://inventory-service:8080/health
curl -s http://payment-service:8080/health

# 检查数据库连接
kubectl exec -it <pod-name> -n production -- \
  curl -s localhost:8080/actuator/health

# 如果是下游依赖问题，开启降级
kubectl patch configmap order-service-config -n production \
  --type merge \
  -p '{"data":{"INVENTORY_FALLBACK_ENABLED":"true"}}'
```

### Step 3C: Pod 数量不足
```bash
# 检查 Node 资源
kubectl top nodes
kubectl describe nodes | grep -A5 "Allocated resources"

# 手动扩容
kubectl scale deployment/order-service --replicas=15 -n production
```

### Step 4: 升级条件
- 15 分钟内未缓解 → 通知 Team Lead
- 30 分钟内未缓解 → 升级为 P0，拉起 War Room
```

---

## 六、On-call 轮转最佳实践

### 6.1 On-call 排班设计

```
基本原则：
  - 轮转周期：1 周（不要太长，避免疲劳）
  - 角色：Primary + Secondary（主备制）
  - 覆盖时间：7×24（Primary）或按时段分工
  - 交接：每次轮转要有交接记录

排班示例：
  Week 1: Primary=张三, Secondary=李四
  Week 2: Primary=李四, Secondary=王五
  Week 3: Primary=王五, Secondary=赵六
  Week 4: Primary=赵六, Secondary=张三

交接内容：
  □ 当前正在进行的事故或风险项
  □ 近期变更计划（可能影响稳定性的）
  □ 已知但未解决的告警
  □ 需要关注的特殊时期（大促、活动）
```

### 6.2 On-call 负担控制

```
健康的 On-call：
  ✅ 每周被呼叫次数 < 2 次
  ✅ 每次事件处理 < 1 小时
  ✅ 非工作时间被叫起的概率 < 每周 1 次
  ✅ On-call 后有补休机制

不健康的 On-call：
  ❌ 每天都被告警轰炸
  ❌ 大量误报导致告警疲劳
  ❌ On-call 期间无法正常工作
  ❌ 总是同一个人处理（英雄文化）

改善措施：
  1. 消灭噪声告警（告警治理）
  2. 改进系统稳定性（减少真实事故）
  3. 完善 Playbook（降低处理时间）
  4. 自动化恢复（减少人工干预）
  5. 扩大 On-call 池（更多人参与分担）
```

### 6.3 On-call 新人培养

```
On-call Onboarding 计划（4 周）：

Week 1：影子期（Shadow）
  - 跟随有经验的 On-call 工程师
  - 观察告警处理流程
  - 熟悉监控 Dashboard 和工具

Week 2：辅助期（Assisted）
  - 作为 Secondary On-call
  - 在指导下处理简单告警
  - 独立完成 Playbook 演练

Week 3：主导期（Lead with backup）
  - 作为 Primary On-call
  - 有经验工程师作为 Secondary 兜底
  - 独立处理日常告警

Week 4：独立期（Independent）
  - 正式独立 On-call
  - 事后 Review 处理过程
  - 反馈 Playbook 改进建议
```

---

## 七、事故响应工具链

### 7.1 工具链全景

```
告警触发          事故管理          沟通协作          状态页面
┌──────────┐   ┌────────────┐   ┌───────────┐   ┌──────────┐
│Prometheus│   │ PagerDuty  │   │  Slack     │   │Statuspage│
│Grafana   │──→│ OpsGenie   │──→│  Teams     │──→│ Cachet   │
│Datadog   │   │ 自建系统    │   │  飞书/钉钉 │   │ 自建     │
└──────────┘   └────────────┘   └───────────┘   └──────────┘
                     │
                     ▼
              ┌────────────┐
              │ 自动化响应   │
              │ Rundeck    │
              │ 自建Bot     │
              └────────────┘
```

### 7.2 PagerDuty / OpsGenie 配置要点

```yaml
# PagerDuty 服务配置示例
service:
  name: "PerfShop Order Service"
  escalation_policy:
    - level: 1
      targets: ["primary-oncall"]
      timeout: 5m           # 5分钟无响应升级
    - level: 2
      targets: ["secondary-oncall", "team-lead"]
      timeout: 15m
    - level: 3
      targets: ["engineering-manager"]
      timeout: 30m

  integrations:
    - type: prometheus_alertmanager
      endpoint: "https://events.pagerduty.com/integration/xxx/enqueue"

  # 告警去重与聚合
  alert_grouping:
    type: intelligent       # 自动聚合相关告警
    timeout: 5m

  # 维护窗口
  maintenance_windows:
    - name: "每周二部署窗口"
      schedule: "TUE 02:00-04:00 Asia/Shanghai"
```

### 7.3 Slack Bot 自动化

```python
# 事故响应 Slack Bot 核心功能
# 实际生产中建议使用成熟框架如 Bolt for Python

INCIDENT_COMMANDS = {
    "/incident create": "创建新事故",
    "/incident update": "更新事故状态",
    "/incident resolve": "解决事故",
    "/incident timeline": "查看事故时间线",
}

# 创建事故时自动执行：
def create_incident(severity, title, description):
    """
    自动化流程：
    1. 创建专属 Slack 频道：#inc-20260328-order-service-down
    2. 邀请 On-call 人员和相关团队
    3. 发送事故通知到 #incidents 频道
    4. 创建 PagerDuty 事故
    5. 置顶事故信息和 Playbook 链接
    6. 启动事故时间线记录
    """
    channel = create_channel(f"inc-{date}-{slugify(title)}")
    invite_oncall(channel)
    post_notification(channel, severity, title, description)
    pin_playbook(channel, get_playbook(title))
    start_timeline(channel)
```

---

## 八、事故响应检查清单

### 8.1 事故响应成熟度评估

| 维度 | 初级 | 中级 | 高级 |
|------|------|------|------|
| **发现** | 用户投诉后才知道 | 监控告警主动发现 | 预测性告警，故障前感知 |
| **响应** | 群里喊谁有空看看 | 有 On-call 制度 | IC 模式，角色明确 |
| **缓解** | 只会重启 | 有 Playbook | 自动化缓解 |
| **沟通** | 微信群讨论 | 有固定沟通渠道 | 自动化通知 + 状态页 |
| **复盘** | 不做 | 做但不跟进 | 无责复盘 + 改进项跟踪 |

### 8.2 P0 事故响应速查卡

```
收到 P0 告警后的前 15 分钟：

0-2 分钟：
  □ ACK 告警（在 PagerDuty/OpsGenie 点确认）
  □ 打开监控 Dashboard 确认问题
  □ 判断影响范围

2-5 分钟：
  □ 在 Slack #incidents 发出事故通知
  □ 创建事故频道 #inc-YYYYMMDD-简述
  □ 指定 IC（通常由发现者先兼任）

5-10 分钟：
  □ 检查最近变更（最近 1 小时内是否有发布）
  □ 如有最近发布 → 立即准备回滚
  □ 如无最近发布 → 检查依赖服务和基础设施

10-15 分钟：
  □ 如果已定位 → 执行缓解措施
  □ 如果未定位 → 发出第一次状态更新，说明正在排查
  □ 如需更多人 → 通知 Secondary On-call 和相关团队
  □ 考虑是否需要升级

持续：
  □ 每 15 分钟发一次状态更新
  □ 记录所有关键操作和发现（Scribe）
  □ IC 保持全局视角，不深入某个方向
```
