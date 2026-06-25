# 05 · 隔离/cgroup → 多租户与隔离设计

> **本章镜头**：看到 cgroup / namespace / limit-request / steal time，立刻反射出多租户隔离的设计决策 —— 不重教机制，只教"事前挡住"的反射。
>
> **前置建议**：不清楚 cgroup v1/v2 层级、`cpu.cfs_quota_us`、`memory.limit_in_bytes` 这些字段本身的含义？先去 [`../../linux-handson/09-containers-from-linux/`](../../linux-handson/09-containers-from-linux/) 打机制地基，再回来做决策反射。
>
> **和其他章的关系**：本章聚焦"隔离"这一维度；CPU 并发模型的深度在 [01](../01-cpu-and-scheduling/)，内存预算在 [02](../02-memory-and-paging/)，完整的容量公式在 `concurrency-capacity`。

---

## 一、盲点

对大多数资深工程师来说，cgroup 是一个**事后工具**：被 throttle 了就调大 limit，OOMKill 了就调大 memory limit，邻居吵了就找 SRE 迁机器。这不是错，但这是**反应式**——问题已经在生产爆了，才开始动。

架构师的差别在**事前**：
- 还没部署，就知道哪些服务应该独占核、哪些可以混部；
- 还没定 limit/request，就能用峰值稳态数字推出合理区间，而不是拍一个 `100m / 500m` 的默认值；
- 还没上线，就设计好故障传播边界，让一个租户的 CPU 爆炸不传到核心链路；
- 还没选云实例，就评估了平台超卖策略（steal time），关键服务是否需要专属机型或绑核。

**一句点破**：资源上只会"事后解释"是资深；在设计期把隔离边界和资源预算写进架构文档，才是架构师。这层差距不在 OS 知识多少，而在**什么时间点用**这些知识。

---

## 二、原语 → 决策映射表

> 三列读法：左列是 OS 内核给出的原语；中列是资深工程师在事后解释时的典型答法；右列是架构师在设计期就应该反射出来的决策。**本课训练的是右列的条件反射。**

| OS 原语 | 资深·能答（反应式） | 架构师·能设计（预判式） |
|---|---|---|
| namespaces + cgroups = 容器 | "容器只是受限进程，共享宿主内核" | 设计期就定 limit/request、QoS 分级（Guaranteed / Burstable / BestEffort）；关键服务用 Guaranteed 类，绝不落入 BestEffort；namespace 不等于隔离，共享内核意味着内核漏洞影响所有容器 |
| CFS throttling（CPU 限速） | "服务被 throttle，p99 抖了，调大 limit" | 关键服务只设 request 不设 limit（或 limit = 2×request），允许突发；批处理才设严格 limit 保护邻居；设 `cpu_throttled_seconds` 告警，throttle > 5% 即触发 |
| noisy neighbor（邻居噪音） | "邻居吵，CPU/内存争抢，我的服务慢了" | 架构期就做 bulkhead 隔板：关键链路独立节点池（taint/toleration）；噪音不只是 CPU，磁盘 IO / 内存 page eviction 也是传播路径；按 SLA 等级分 node group，评估最坏邻居场景 |
| steal time（%st，被偷的 CPU） | "宿主超卖，st 高，性能抖动，找云厂商" | 关键服务选专属宿主 / bare-metal / CPU 绑核（cpuset cgroup）；设计故障传播边界：st 抖动时触发降级而非雪崩；评估云实例超卖策略（共享型 vs 独占型）再选机型；st 纳入 SLO 监控 |
| memory.limit + OOMKill | "容器被 OOMKill，加内存 limit" | limit = P99 峰值 + 20% 余量；request = P50 稳态均值；Java / Node / Python 运行时需加 cgroup 感知启动参数，否则 JVM 看宿主总内存设 heap → 触发 limit → OOMKill；内存不可压缩，OOMKill 是硬终止 |
| cgroup v2 统一层级 | "cgroup v2 和 v1 有区别，v2 层级不一样" | 新集群默认 v2（Linux 5.8+、k8s 1.25+）；v2 的 memory.pressure / cpu.pressure（PSI）是比 throttle 更早的预警信号，接进告警系统；HPA / VPA 策略需确认 metrics-server 读 cgroup v2 |

---

## 三、定量锚点

**反射式设定 request / limit 的三步：**

1. **request = 稳态 P50 用量**（看 7 天 CPU/内存 均值，取 P50）—— 这是调度器做 bin-packing 的依据，太低会导致节点被过度填充，太高浪费资源。
2. **limit = 峰值 P99 + 20% 余量**—— 峰值不等于 spike 最高点，看 P99 而不是 P100，避免偶发 spike 把 limit 定得过高掩盖问题。
3. **内存不可压缩** —— memory limit 被触发 = OOMKill，没有温和降级；CPU limit 被触发 = throttle，有 p99 抖动但不崩。对内存宁可给余量，对 CPU 关键服务宁可不设上限（或设宽）。

**一例**：一个 Java 微服务，稳态 0.2 CPU / 400 MiB，峰值 0.8 CPU / 700 MiB。

```
request: cpu=200m  memory=512Mi
limit:   cpu=1000m memory=900Mi   # 内存留 ~30% 余量；CPU limit 宽设允许突发
```

JVM 堆需配 `-XX:MaxRAMPercentage=75`（cgroup 感知模式），否则 JVM 看宿主 16 GiB 设堆 → 超出 limit → OOMKill。**Go 默认不感知 cgroup**：`GOMAXPROCS` 读宿主核数（容器限 2 核仍开宿主核数个 P，过度上下文切换），需 `automaxprocs` 或手设；内存要显式 `GOMEMLIMIT`（Go 1.19+）。Rust 无托管运行时，但分配器同样不会自动按 cgroup 限内存。

**QoS 三档快速参考**：

| k8s QoS 类 | 触发条件 | 节点内存压力时 kubelet 行为 |
|---|---|---|
| Guaranteed | request = limit（CPU + 内存都等） | 最后被驱逐；关键服务必须用 |
| Burstable | request < limit，或只设一项 | 中等优先级驱逐 |
| BestEffort | 都不设 | 最先被驱逐；只用于纯离线批处理 |

> 完整容量推导（稳态 vs 峰值、request 聚合、节点 bin-packing）指向深矿：[`../../concurrency-capacity/06-isolation/`](../../concurrency-capacity/06-isolation/)

---

## 四、决策清单 & 反模式

### 设计多租户 / 容器化部署时，该问这些问题

- **服务等级划分**：哪些服务是关键链路（需要 Guaranteed QoS）？哪些是可降级的批处理（BestEffort 可接受）？SLA 差异有多大？
- **隔离边界**：关键服务和批处理是否混部在同一节点池？混部的最坏邻居场景（全部突发、OOMKill 引发节点 pressure）是否评估过？
- **资源预算来源**：request / limit 是从真实监控数据推算出的，还是拍的默认值 `100m / 500m`？有没有人做过 profiling 确认稳态和峰值？
- **内存特殊性**：服务是否有 GC / 大对象 / 突发 allocation？OOMKill 发生时服务中断多长时间？是否需要 PodDisruptionBudget 限制同时驱逐数量？
- **运行时 cgroup 感知**：JVM / Node.js / Python（带 PyPy）是否正确配置了 cgroup 内存上限感知？没配的话 limit 触发就是 OOMKill。
- **宿主超卖**：平台是否超卖 CPU（云共享型实例默认超卖）？关键服务节点是否开了 steal-time（`%st`）监控？是否评估过换专属实例的 cost/SLA 权衡？
- **故障传播边界**：一个 namespace / 节点池的资源耗尽，是否会通过共享队列 / 共享数据库连接池传播到核心链路？有无熔断 / 限流隔离？

### 反模式

| 反模式 | 后果 | 正确做法 |
|---|---|---|
| 只设 limit，不设 request | 调度器无法做 bin-packing；关键服务被调度到已满节点，throttle / OOMKill | request = 稳态用量，让调度器有数字可用 |
| 关键服务和批处理混部，不做节点隔离 | 批处理突发 → 噪音邻居 → 关键链路 p99 抖动；批处理 OOMKill 触发节点内存压力 → 关键服务也被驱逐 | 分 node group / node selector / taint-toleration 隔离 |
| 忽略 CFS throttling，只看 CPU 使用率低 | CPU 使用率 20% 但 throttle 40%（突发被限速）→ p99 高，开发以为是代码慢 | 监控 `container_cpu_cfs_throttled_seconds_total`，关键服务 throttle > 5% 就扩或去掉 limit |
| JVM / Node.js 不做 cgroup 感知配置 | JVM 读宿主总内存设堆 → limit 触发 OOMKill；Node.js 无 `--max-old-space-size` → 同样问题 | Java 11+：`-XX:+UseContainerSupport`（默认开）+ `-XX:MaxRAMPercentage`；Node.js：显式传 `--max-old-space-size` |
| 多租户共享数据库 / 消息队列，不做 bulkhead | 一个租户写入爆增 → 连接池耗尽 / 队列积压 → 所有租户受损 | 按租户等级做连接池隔离；关键链路单独队列；熔断降级隔离传播 |

---

## 五、指针

### 下指（机制层）

- **容器隔离机制怎么运作**（namespace 六种类型 / cgroup v1 vs v2 / overlay fs 实验 / 从 unshare 手建容器）：[`../../linux-handson/09-containers-from-linux/`](../../linux-handson/09-containers-from-linux/)

### 横指（深决策层）

- **隔离 / bulkhead / 多租户容量设计完整推导**（连接池 per-tenant 配额、服务级熔断、隔离成本 vs 复用成本权衡）：[`../../concurrency-capacity/06-isolation/`](../../concurrency-capacity/06-isolation/)
- **cgroup 资源配置实战**（k8s request/limit/QoS 完整策略、VPA 自动扩、ResourceQuota namespace 配额、LimitRange 默认值）：[`../../performance-tuning-roadmap/12-container/01-cgroup-resource.md`](../../performance-tuning-roadmap/12-container/01-cgroup-resource.md)
- **容器化性能调优**（throttle 排查流程 / HPA 扩容延迟 / 节点超卖 steal-time 实测 / PSI 告警配置）：[`../../performance-tuning-roadmap/12-container/02-k8s-performance.md`](../../performance-tuning-roadmap/12-container/02-k8s-performance.md)
- **故障传播边界 / 可用性设计**（RPO/RTO 定义 / 多租户容灾 / 降级策略在隔离链路中的位置）：[`../../system-design/08-可用性與容災-RPO-RTO.md`](../../system-design/08-可用性與容災-RPO-RTO.md)

### 本章在 track 中的位置

```
os-for-architects/05（本章）
        ↓ 机制
linux-handson/09-containers-from-linux      ← 手建容器实验
        ↓ 横向深挖
concurrency-capacity/06-isolation           ← 完整 bulkhead 推导
performance-tuning-roadmap/12-container/    ← 调优实战
system-design/08                            ← 可用性 / 容灾边界
```

---

## 六、面试转化

> 面试考官问隔离类题目时，判断"能答"和"能设计"的分水岭：**能答**停在机制（"设了 limit"）；**能设计**说出预判逻辑、定量依据、故障传播边界三件事。

### 题 1：怎么避免 noisy neighbor？

**能答（资深）**：
> "noisy neighbor 是同一宿主上的容器争夺 CPU / 内存 / 磁盘 IO，导致我的服务性能抖动。可以设 cgroup limit 限制邻居，或者把关键服务迁到专属节点。"

**能设计（架构师）**：
> "在设计期就按 SLA 等级分节点池 —— 关键链路服务打 taint，只有能容忍该 taint 的 pod 才能调度进来，物理上杜绝批处理混入。节点池内再做 QoS 分级：关键服务全部 Guaranteed（request = limit），批处理允许 Burstable 或 BestEffort。
>
> 光 CPU 隔离不够：共享数据库 / 消息队列也是传播路径。批处理写入激增会耗尽连接池，影响所有服务。所以核心链路的数据库连接池要独立，或设每租户连接上限。
>
> 监控侧：打开 `container_cpu_cfs_throttled_seconds_total` 和 PSI（cgroup v2 memory.pressure），throttle > 5% 或 memory pressure 持续 > 30% 就触发告警，比 CPU 使用率低而 p99 高时才发现要早很多。"

---

### 题 2：limit / request 怎么设？容器为什么被 OOMKill？

> 追加追问："有没有遇过 CPU 使用率不高但 p99 很高的情况？"答案就是 CFS throttling。

**能答（资深）**：
> "limit 是上限，超了被 throttle（CPU）或 OOMKill（内存）；request 是调度保证。被 OOMKill 是因为内存超过 limit。"

**能设计（架构师）**：
> "先从监控拿数字：request = 7 天 P50 稳态用量，limit = P99 峰值 + 20% 余量。关键服务的 CPU limit 可以设得宽（2× request），甚至不设，避免 throttle 影响 p99；批处理才设严格 limit 保护邻居。
>
> OOMKill 常见根因有三：① limit 设得比实际峰值小；② JVM / Node.js 没开 cgroup 感知，用宿主总内存算 heap，超出 limit；③ 内存泄漏 / 大对象没释放。前两条在部署配置阶段就能堵。
>
> 内存和 CPU 要分开对待：CPU 限速（throttle）是温和的，服务慢但不崩；内存 OOMKill 是硬终止，影响请求成功率。所以内存 limit 宁可给余量、宁可 VPA 自动扩，也不要设太紧。
>
> Guaranteed QoS（request = limit）能防止在节点内存压力时被 kubelet 驱逐，关键服务必须用这种模式。"

---

### 题 3：你们系统怎么做多租户隔离？

**能答（资深）**：
> "用 k8s namespace 隔离，给每个租户分配 ResourceQuota，限制 CPU / 内存总量。"

**能设计（架构师）**：
> "namespace + ResourceQuota 只是入口第一层，真正的隔离需要多层：
>
> 第一层：计算隔离 —— 按租户 SLA 分节点池（taint/toleration），关键租户 Guaranteed QoS；
> 第二层：数据面隔离 —— 共享 DB 按租户做连接池上限（`connection_pool_size / tenant`），避免一个租户写入爆增耗尽连接池；
> 第三层：故障传播隔离 —— 关键租户的请求路径上做熔断（circuit breaker），一个租户的下游慢不影响其他租户；
> 第四层：可观测性 —— 每个租户单独看 throttle / OOMKill / p99，SLA 违约在 tenant 粒度告警，不只看服务整体均值。
>
> 做到前两层是资深水平，后两层是架构水平。"

---

## 小结

| 原语 | 反射到的架构决策 |
|---|---|
| namespaces + cgroups | 容器不是虚拟机；隔离边界是 QoS 分级 + 节点池，不是只加 limit |
| CFS throttle | CPU 使用率低 + p99 高 = throttle 信号；关键服务宽设或不设 CPU limit |
| noisy neighbor | 物理隔离节点池（taint）+ 共享资源（DB/MQ）也要隔离；bulkhead 不止计算层 |
| steal time（st） | 平台超卖 → 关键服务选专属实例 / 绑核；st 纳入监控告警 |
| memory limit + OOMKill | 内存不可压缩；JVM/Node 必须做 cgroup 感知配置；Guaranteed QoS 防驱逐 |

读完的标准：**给你一个"容器 OOMKill 了"或"p99 抖了"的场景，你能在两分钟内说出是哪条 OS 原语触发、在设计期哪个决策能提前挡住，并给出具体数字依据。**

---

## 附录：常用监控指标速查

| 指标 | 工具/来源 | 触发告警的阈值参考 |
|---|---|---|
| `container_cpu_cfs_throttled_seconds_total` | Prometheus + kube-state-metrics | 关键服务 throttle 比 > 5% |
| `container_oom_events_total` | Prometheus | 任意 OOMKill > 0 立即告警 |
| `node_cpu_seconds_total{mode="steal"}` | node-exporter | steal > 5% 持续 5min |
| `memory.pressure`（PSI，cgroup v2） | cgroupv2 / node-exporter | some avg10 > 30% |
| `container_memory_working_set_bytes` | cadvisor | 接近 limit 的 80% 发 warning |
| `kube_pod_container_status_restarts_total` | kube-state-metrics | 关键服务重启次数 > 3/小时 告警 |

> 这些指标不在本课展开如何配置 —— 用法指向 [`../../performance-tuning-roadmap/12-container/02-k8s-performance.md`](../../performance-tuning-roadmap/12-container/02-k8s-performance.md)。
>
> OOMKill 后容器会重启（CrashLoopBackOff），`kube_pod_container_status_restarts_total` 是比看 Events 更稳定的告警来源。
