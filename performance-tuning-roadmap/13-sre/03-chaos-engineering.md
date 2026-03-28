# 混沌工程

你的系统在凌晨 3 点流量突增时能撑住吗？某个下游服务挂了会连锁崩溃吗？Redis 突然断开连接应用能优雅降级吗？如果你回答不出来，说明你还在靠运气运维。混沌工程就是在可控环境下**主动注入故障**，让你在事故发生前发现系统的脆弱点，而不是被用户和老板教做人。

---

## 一、混沌工程原理

### 1.1 核心概念

```
混沌工程 ≠ 随便搞破坏
混沌工程 = 通过受控实验验证系统韧性的工程实践

核心流程：
1. 定义稳态假设（Steady State Hypothesis）
   "在正常流量下，订单成功率应 > 99.9%，P99 延迟 < 500ms"

2. 假设稳态在实验组和对照组中均成立

3. 引入真实世界中可能发生的故障变量
   "注入 200ms 网络延迟"、"杀掉 1 个 Pod"

4. 寻找稳态假设被推翻的证据
   "注入延迟后 P99 飙到 5s → 发现超时配置不合理"

5. 得出结论，推动改进
```

### 1.2 混沌工程五大原则

```
1. 围绕稳态行为建立假设
   不是"看看系统会不会挂"
   而是"验证系统在故障下是否维持稳态"

2. 用真实世界的事件做变量
   网络分区、磁盘满、进程崩溃、时钟偏移
   不是臆想的故障，而是历史上真正发生过的

3. 在生产环境运行实验
   测试环境的结果参考价值有限
   目标是在生产环境跑（从小范围开始）

4. 自动化实验以持续运行
   不是一次性活动，而是持续验证
   纳入 CI/CD pipeline

5. 最小化爆炸半径
   从非核心服务开始
   限制影响范围
   有自动终止机制
```

### 1.3 混沌工程与传统测试的区别

| 维度 | 传统测试 | 混沌工程 |
|------|---------|---------|
| **目的** | 验证功能正确性 | 验证系统韧性 |
| **方法** | 已知输入 → 预期输出 | 注入故障 → 观察行为 |
| **环境** | 测试环境 | 生产或类生产环境 |
| **关注点** | 代码层面 bug | 系统级弱点 |
| **频率** | 每次提交 | 持续/定期 |
| **结果** | Pass / Fail | 发现未知弱点 |
| **思维** | "证明它能工作" | "找出它在哪里会失败" |

---

## 二、Netflix 混沌工程成熟度模型

Netflix 定义了一个混沌工程成熟度模型，用于评估团队的混沌工程实践水平：

### 2.1 成熟度阶段

| 阶段 | 级别 | 特征 | 典型实践 |
|------|------|------|----------|
| **Level 0** | 无 | 没有混沌实验 | 只靠祈祷 |
| **Level 1** | 初级 | 手动、临时性实验 | 手动杀进程看看会怎样 |
| **Level 2** | 基础 | 有计划的实验，非生产环境 | 在 Staging 跑定期实验 |
| **Level 3** | 进阶 | 生产环境实验，有安全控制 | 生产小范围注入故障 |
| **Level 4** | 高级 | 自动化、持续运行 | 集成到 CI/CD，每天自动跑 |
| **Level 5** | 卓越 | 全面覆盖，驱动架构决策 | 混沌实验结果影响设计 |

### 2.2 成熟度自评

```
评估你的团队：

□ 是否有明确的稳态定义（SLI/SLO）？
□ 是否有可观测性基础（监控、日志、追踪）？
□ 是否做过至少一次手动故障注入？
□ 是否有混沌实验文档和审批流程？
□ 是否在生产环境跑过混沌实验？
□ 是否有自动化混沌实验？
□ 是否有 Game Day 定期活动？
□ 混沌实验结果是否驱动了架构改进？

0-2 个 ✅ → Level 0-1（起步阶段）
3-4 个 ✅ → Level 2（基础阶段）
5-6 个 ✅ → Level 3（进阶阶段）
7-8 个 ✅ → Level 4-5（高级/卓越）
```

---

## 三、工具对比

### 3.1 主流工具

| 工具 | 类型 | 平台 | 语言 | 许可 | 适用场景 |
|------|------|------|------|------|----------|
| **ChaosBlade** | CLI + Server | K8s/物理机/Docker | Go | Apache 2.0 | 阿里系，中文文档好 |
| **Chaos Mesh** | K8s Operator | K8s 原生 | Go | Apache 2.0 | 云原生场景首选 |
| **LitmusChaos** | K8s Operator | K8s 原生 | Go | Apache 2.0 | CNCF 项目，生态完善 |
| **Gremlin** | SaaS 平台 | 多平台 | - | 商业 | 企业级，开箱即用 |

### 3.2 Chaos Mesh 快速上手

```bash
# 安装 Chaos Mesh（Helm 方式）
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm install chaos-mesh chaos-mesh/chaos-mesh \
  --namespace chaos-testing \
  --create-namespace \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/containerd/containerd.sock
```

**Pod 故障注入：**

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: pod-kill-order-service
  namespace: chaos-testing
spec:
  action: pod-kill
  mode: one              # 随机杀一个
  selector:
    namespaces:
      - production
    labelSelectors:
      app: order-service
  scheduler:
    cron: "@every 2h"     # 每 2 小时执行一次
  duration: "30s"
```

**网络延迟注入：**

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: network-delay-to-db
  namespace: chaos-testing
spec:
  action: delay
  mode: all
  selector:
    namespaces:
      - production
    labelSelectors:
      app: order-service
  delay:
    latency: "200ms"
    jitter: "50ms"
    correlation: "75"
  direction: to
  target:
    selector:
      namespaces:
        - production
      labelSelectors:
        app: mysql
    mode: all
  duration: "5m"
```

### 3.3 ChaosBlade 快速上手

```bash
# 安装
wget https://github.com/chaosblade-io/chaosblade/releases/download/v1.7.3/chaosblade-linux-amd64.tar.gz
tar xvf chaosblade-linux-amd64.tar.gz
cd chaosblade-1.7.3

# CPU 满载实验
./blade create cpu fullload --cpu-percent 80 --timeout 60

# 网络延迟
./blade create network delay --time 200 --interface eth0

# 磁盘填满
./blade create disk fill --size 1024 --path /data --timeout 120

# 杀进程
./blade create process kill --process java

# 销毁实验
./blade destroy <experiment-uid>
```

---

## 四、实验类型详解

### 4.1 常见实验类型

```
基础设施层：
  ├── CPU 满载（验证限流、降级是否生效）
  ├── 内存耗尽（验证 OOM Killer 行为）
  ├── 磁盘填满（验证日志轮转、磁盘告警）
  ├── 时钟偏移（验证分布式一致性）
  └── 进程崩溃（验证自动重启机制）

网络层：
  ├── 网络延迟（验证超时配置）
  ├── 网络丢包（验证重试机制）
  ├── 网络分区（验证脑裂处理）
  ├── DNS 故障（验证缓存和降级）
  └── 带宽限制（验证性能降级表现）

应用层：
  ├── Pod 杀死（验证副本数和自动恢复）
  ├── 容器 OOMKilled（验证内存限制）
  ├── 依赖服务不可用（验证熔断器）
  ├── 慢调用注入（验证超时配置）
  └── 异常注入（验证异常处理链路）

数据层：
  ├── 数据库主从切换（验证连接重建）
  ├── 缓存击穿（验证缓存降级方案）
  ├── 消息队列堆积（验证背压机制）
  └── 存储 IO 延迟（验证超时与重试）
```

### 4.2 实验设计模板

```yaml
# 混沌实验设计文档
experiment:
  name: "订单服务下游延迟容忍度验证"
  id: CE-2026-042
  date: "2026-03-28"
  owner: "SRE 团队 - 张三"

  # 1. 稳态假设
  steady_state:
    description: "在正常流量下"
    metrics:
      - name: "订单成功率"
        expected: ">= 99.9%"
        query: "sum(rate(order_success_total[5m])) / sum(rate(order_total[5m]))"
      - name: "P99 延迟"
        expected: "< 500ms"
        query: "histogram_quantile(0.99, sum by(le)(rate(order_duration_bucket[5m])))"

  # 2. 实验方法
  method:
    type: "network-delay"
    target: "order-service → inventory-service 的调用"
    parameters:
      latency: "500ms"
      jitter: "100ms"
      duration: "10 minutes"

  # 3. 预期结果
  expected_outcome: |
    order-service 应在 inventory-service 延迟时：
    1. 触发超时（超时设置 1s）
    2. 熔断器打开后走降级逻辑
    3. 订单成功率维持 > 99.5%（通过缓存库存降级）

  # 4. 终止条件
  abort_conditions:
    - "订单成功率 < 95%"
    - "P99 延迟 > 5s 持续 2 分钟"
    - "影响到非实验范围的服务"

  # 5. 回滚方案
  rollback: |
    1. 删除 NetworkChaos CR：kubectl delete networkchaos network-delay-to-inventory
    2. 验证指标恢复
    3. 如有持续影响，重启 order-service pods

  # 6. 审批
  approved_by: "李四（SRE Lead）"
  approval_date: "2026-03-27"
```

---

## 五、安全边界与爆炸半径控制

### 5.1 爆炸半径控制原则

```
1. 渐进式扩大
   开发环境 → 测试环境 → 预发布 → 生产灰度 → 生产全量

2. 比例控制
   生产环境：先影响 1 个 Pod → 10% 流量 → 全量

3. 时间限制
   所有实验必须设置 duration
   超时自动回滚

4. 自动终止
   当关键指标触发终止条件时，立即停止实验

5. 避开高风险时段
   不在大促期间、不在业务高峰期
   首选工作日白天（人员在线可快速响应）
```

### 5.2 安全控制清单

```yaml
# Chaos Mesh 安全配置
apiVersion: chaos-mesh.org/v1alpha1
kind: Workflow
metadata:
  name: safe-chaos-experiment
spec:
  entry: serial-experiment
  templates:
    - name: serial-experiment
      templateType: Serial
      children:
        - check-steady-state     # 先验证稳态正常
        - inject-fault           # 注入故障
        - observe-impact         # 观察影响
        - verify-recovery        # 验证恢复

    - name: check-steady-state
      templateType: Task
      task:
        # 确认实验前系统处于健康状态
        container:
          image: curlimages/curl
          command:
            - /bin/sh
            - -c
            - |
              # 检查服务健康
              STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://order-service:8080/health)
              if [ "$STATUS" != "200" ]; then
                echo "Service unhealthy, aborting experiment"
                exit 1
              fi
```

### 5.3 生产环境实验的安全准则

| 准则 | 说明 |
|------|------|
| **必须有审批** | 生产实验需 SRE Lead 或以上审批 |
| **必须有 On-call** | 实验期间必须有人值守 |
| **必须有回滚** | 每个实验必须有明确的回滚步骤 |
| **必须有终止条件** | 自动化终止，不能只靠人判断 |
| **必须有通知** | 实验开始/结束通知相关团队 |
| **不能影响数据** | 不做会导致数据不一致的实验 |
| **先小后大** | 1 个 Pod → 比例 → 全量 |

---

## 六、Game Day（游戏日）

### 6.1 什么是 Game Day

```
Game Day = 有组织的、跨团队的故障演练活动

不是随便搞：
  ❌ 偷偷杀几个 Pod 看看会怎样
  ❌ 只有 SRE 参与的单方面操作

是正式活动：
  ✅ 提前规划、有脚本、有目标
  ✅ 开发 + 运维 + 产品共同参与
  ✅ 有裁判观察和记录
  ✅ 事后有复盘和改进
```

### 6.2 Game Day 组织流程

```
阶段一：准备（提前 2 周）
  □ 确定演练目标（验证什么能力？）
  □ 设计故障场景（2-4 个场景）
  □ 准备注入工具和脚本
  □ 通知参与团队（开发、SRE、产品、客服）
  □ 确认观测工具就绪（Dashboard、告警、日志）
  □ 安排裁判/观察员

阶段二：执行（当天）
  时间      活动
  09:00    开场说明（目标、规则、安全边界）
  09:30    场景 1：单节点故障（Pod 被杀）
  10:00    复盘场景 1
  10:30    场景 2：网络延迟注入
  11:00    复盘场景 2
  11:30    场景 3：依赖服务不可用
  12:00    午间总结
  14:00    场景 4：级联故障（多个组件同时异常）
  14:30    复盘场景 4
  15:00    总结会议

阶段三：复盘（1 周内）
  □ 汇总所有发现
  □ 分类：已知问题 vs 新发现
  □ 创建改进 Ticket（有优先级和 Owner）
  □ 发送 Game Day 报告
  □ 下次 Game Day 计划
```

### 6.3 Game Day 报告模板

```markdown
# Game Day 报告

日期：2026-03-28
参与团队：SRE、订单团队、支付团队、平台团队
总时长：5 小时

## 场景与发现

### 场景 1：杀死 1/3 的 order-service Pod
- 预期：自动恢复，用户无感
- 实际：恢复时间 45s，期间有少量 5xx
- 发现：Pod readiness probe 配置过于宽松，新 Pod 还未就绪就接收流量
- 改进项：调整 readiness probe 的 initialDelaySeconds 和检查逻辑
- 严重度：中
- Owner：张三
- Deadline：2026-04-11

### 场景 2：inventory-service 延迟 2s
- 预期：熔断后走缓存降级，订单成功率 > 99%
- 实际：没有熔断！全部请求等到超时（10s），成功率降到 60%
- 发现：熔断器配置了但超时时间设置不合理（10s 太长）
- 改进项：1) 超时调整为 1s 2) 验证熔断器配置生效
- 严重度：高
- Owner：李四
- Deadline：2026-04-04

## 统计
- 总发现数：7
- 高严重度：2
- 中严重度：3
- 低严重度：2
- 改进项已创建 Ticket：7/7
```

---

## 七、从简单开始：第一个混沌实验

### 7.1 适合第一次的实验

```
推荐从最安全、最有价值的实验开始：

实验：在非生产环境杀死一个应用 Pod

为什么适合第一次：
  - 风险极低（Kubernetes 会自动重建 Pod）
  - 操作简单（一条命令）
  - 能验证基本的高可用能力
  - 结果直观易懂
```

### 7.2 动手操作

```bash
# 准备：确认当前状态
kubectl get pods -l app=order-service -n staging
# NAME                             READY   STATUS    RESTARTS   AGE
# order-service-7d8f9c6b5d-abc12   1/1     Running   0          2d
# order-service-7d8f9c6b5d-def34   1/1     Running   0          2d
# order-service-7d8f9c6b5d-ghi56   1/1     Running   0          2d

# 记录稳态指标
# - 当前 QPS：正常
# - 当前错误率：0%
# - 当前 P99 延迟：45ms

# 执行实验：杀死一个 Pod
kubectl delete pod order-service-7d8f9c6b5d-abc12 -n staging

# 立即观察
watch kubectl get pods -l app=order-service -n staging
# 观察新 Pod 启动时间和就绪时间

# 同时观察监控
# - 错误率是否上升？
# - 延迟是否增加？
# - 用户是否有感知？

# 记录结果
echo "Pod 删除时间: $(date)"
echo "新 Pod 就绪时间: 观察 kubectl 输出"
echo "恢复期间错误数: 查看 Grafana"
```

### 7.3 实验后的分析

```
观察到什么？           可能的改进
─────────────────────────────────────────────────
新 Pod 启动很慢(>60s)  优化启动时间、调整 JVM 预热
启动期间有错误         检查 readiness probe 配置
客户端看到连接重置     检查负载均衡的连接排空配置
完全无影响             很好！可以尝试更激进的实验
恢复后流量不均衡       检查负载均衡策略
```

---

## 八、混沌实验清单（按难度递进）

### 8.1 分阶段实验路线

| 阶段 | 实验 | 验证目标 | 环境 |
|------|------|---------|------|
| **入门** | 杀 Pod | 自动恢复、无感切换 | Staging |
| **入门** | 重启节点 | Pod 漂移、重新调度 | Staging |
| **基础** | 网络延迟 100ms | 超时配置合理性 | Staging |
| **基础** | 网络丢包 5% | 重试机制有效性 | Staging |
| **进阶** | 依赖服务挂掉 | 熔断、降级 | Staging→Prod |
| **进阶** | CPU 注入 90% | 限流、自动扩容 | Staging→Prod |
| **进阶** | 磁盘 IO 延迟 | 日志/数据写入降级 | Staging |
| **高级** | 多故障叠加 | 级联故障处理 | Staging |
| **高级** | AZ 级故障模拟 | 跨可用区容灾 | Prod(灰度) |
| **高级** | 数据库主从切换 | 连接自动重建 | Staging→Prod |

### 8.2 实验检查清单

```
实验前：
  □ 稳态假设已定义（用具体的指标和阈值）
  □ 实验方案已文档化
  □ 实验已获得审批
  □ 监控 Dashboard 已准备
  □ 终止条件已设置
  □ 回滚方案已准备
  □ On-call 人员已通知
  □ 不在业务高峰期

实验中：
  □ 持续观察关键指标
  □ 记录实验开始时间
  □ 触发终止条件时立即停止
  □ 记录异常行为和发现

实验后：
  □ 验证系统恢复到稳态
  □ 记录实验结果
  □ 分析发现的问题
  □ 创建改进项 Ticket
  □ 更新实验知识库
  □ 分享经验到团队
```
