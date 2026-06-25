# 04 — 滚动编排机制:把单实例放大到 fleet

> 核心问题:ch02/ch03 讲的是**一个**实例怎么优雅上、下线。但发布是**一整排**实例同时换。把"单实例上下线"放大到 fleet,就冒出新问题:**滚动过程中怎么保证总容量不塌、两版本并存不出事、出问题怎么快速退回?**
>
> 边界:发布**策略**(蓝绿 vs 金丝雀 vs 滚动该选哪个、feature flag、schema 迁移策略)是 [`system-design/09`](../../system-design/09-發布與變更管理.md) 的地盘,**本章不重写**。本章只讲让这些策略成立的**机制旋钮**:`maxSurge`/`maxUnavailable`/`minReadySeconds`/PDB,以及它们怎么把 ch02+ch03 串成一条不掉容量的流水线。

---

## A · 两个旋钮决定滚动时的容量曲线:`maxUnavailable` / `maxSurge` ⭐

滚动更新 = 一边创建新 Pod、一边删老 Pod。两个旋钮控制这个"边删边建"的幅度:

| 旋钮 | 含义 | 控制什么 |
|---|---|---|
| **maxUnavailable** | 滚动期间,允许**低于**期望副本数多少 | 容量**底线**(最多掉多少) |
| **maxSurge** | 滚动期间,允许**超出**期望副本数多少 | 资源**上限**(最多多起多少) |

例:`replicas=10, maxUnavailable=20%, maxSurge=20%`:

```
  滚动中任意时刻:
    可用副本 ≥ 10 - 2 = 8       ← maxUnavailable=20% 保证至少 8 个在服务
    总副本   ≤ 10 + 2 = 12      ← maxSurge=20% 最多同时存在 12 个
```

两种典型配法,取舍清楚:

- **`maxUnavailable=0, maxSurge>0`(要容量不塌)**:**先把新 Pod 起好、Ready 了,再撤老 Pod**(先涨后落)→ 全程不低于期望容量。代价:滚动期要多占 surge 那部分资源(得有富余配额/节点)。**生产默认推荐。**
- **`maxUnavailable>0, maxSurge=0`(要省资源)**:先撤老的腾出位置再起新的(先落后涨)→ 滚动期容量会**短暂下凹**。资源紧时用,但要确认下凹的容量扛得住当前流量。

> 面试点:**"滚动时会不会掉容量"完全由这两个旋钮决定。** `maxUnavailable=0 + maxSurge>0` 是"零容量损失"的配方,但要有资源余量;否则就得接受短暂下凹。

---

## B · 滚动的真正时序:ch02 和 ch03 在这里被串起来 ⭐

旋钮只是幅度,**真正保证不掉请求的是每一步的时序**。一步滚动(替换一个 Pod)实际是:

```
  ① 按 maxSurge 创建一个新 Pod
        │
        ▼
  ② 新 Pod 走完【优雅上线/ch02】:启动 → 预热 → readiness=true → 稳过 minReadySeconds
        │   ← 没走完这一步,滚动【不会】进行下一步
        ▼
  ③ 这才去删一个老 Pod,触发它的【优雅下线/ch03】:
        Terminating → 摘 endpoint(链路A) ∥ preStop sleep → SIGTERM → 排空 → 退
        │
        ▼
  ④ 重复,直到全部替换完
```

**关键认知:滚动 = 把 ch02(新 Pod 上线)和 ch03(老 Pod 下线)用"先 ready 后摘老"的时序串起来,逐个推进。** 任何一环没做好,放大 N 倍就是事故:

- 新 Pod 的 readiness 不准(没真热就 ready)→ 滚动以为新的好了、撤了老的 → 流量打到没热的新 Pod(危险①被放大)。
- 老 Pod 没配 preStop → 每撤一个都掉一小撮请求(危险②被放大 N 次)。
- `minReadySeconds=0` → 抖动的新 Pod(翻 ready 又崩)被当可用 → 滚动撤了老 Pod → **容量塌**。

> 所以 ch01(readiness 准不准)、ch02(新 Pod 真热没)、ch03(老 Pod 排干净没)**是滚动不掉请求的前置条件**。旋钮配得再漂亮,单实例那两步没做好也白搭。

---

## C · PodDisruptionBudget:fleet 级的"最少留几个活着" ⭐

PDB 是最容易和 maxUnavailable 混、也最容易和 preStop 混的概念。钉死两件事:

### C1 PDB 管的是"自愿中断",不是滚动更新本身

中断分两类:

| 类型 | 例子 | PDB 管吗 |
|---|---|---|
| **自愿中断**(voluntary) | `kubectl drain` 节点、集群升级、节点缩容、autoscaler 挪 Pod | ✅ PDB 在这里生效 |
| **非自愿中断**(involuntary) | 节点宕机、OOMKill、内核 panic、网络断 | ❌ PDB 管不了 |

PDB 配 `minAvailable: 8`(或 `maxUnavailable: 2`):当有人要**驱逐(eviction)**你的 Pod(比如 drain 节点),k8s 会**检查 PDB**——如果驱逐会让可用数跌破 PDB,**驱逐被阻塞/排队**,直到有足够 Pod 重新就绪。这保证"运维操作(升级/缩容)不会一次端掉太多副本"。

> **常见误区**:以为 Deployment 滚动更新受 PDB 约束。**不**——Deployment 自己的滚动用的是 `strategy.rollingUpdate.maxUnavailable`;**PDB 主要约束 eviction API(drain/autoscaler 等)**。两套机制,别混。(节点 drain 时,两者会叠加作用。)

### C2 PDB vs preStop:两个不同层次(必考)

| | 层次 | 回答 |
|---|---|---|
| **PDB** | **fleet 级准入** | "整排里,同一时刻最多能有几个不可用" |
| **preStop**(ch03) | **单 Pod 级排空** | "**这一个** Pod 走的时候,怎么不掉它手上的请求" |

> 一句话:**PDB 保证"不会一次拿走太多个",preStop 保证"被拿走的那个走得干净"。** 两个都要——PDB 防"批量端掉导致容量塌",preStop 防"单个粗暴退出导致掉请求"。面试官爱问"PDB 能替代优雅下线吗",答案是不能,它俩正交。

---

## D · 回滚:把"零停机"延伸到"出事也能秒退"

零停机不只是"发上去不掉请求",还包括"**发现不对能快速退回、且退回也不掉请求**":

- `kubectl rollout undo deploy/x`:回到上一个 ReplicaSet(k8s 留有 `revisionHistoryLimit` 份历史)。**回滚本身也是一次滚动**,同样走 A/B 的旋钮和时序——所以回滚也得益于 preStop/readiness。
- **金丝雀 + 自动回滚**(Argo Rollouts/Flagger):按指标(错误率/延迟)自动判断、不行就退,见 [`cloud-native-landscape/06`](../../cloud-native-landscape/06-delivery-gitops-progressive.md)。
- **前提是变更可回滚**:DB schema 不兼容就回不了(回滚了代码,schema 已经改了)。这就接到 ch04 不碰、但你必须知道的**兼容变更**——expand-contract,见 [`system-design/09`](../../system-design/09-發布與變更管理.md) 和 [`python-data/07`](../../python-data/07-migrations.md)。**"能不能零停机回滚"常常卡在数据层而不是 Pod 层。**

---

## E · 和 HPA / 配额的交互(架构师细节)

- **HPA 与滚动同时进行**:滚动期 HPA 还在按指标扩缩,新老 ReplicaSet 都可能被调整;`maxSurge` 的额外 Pod + HPA 扩容会**叠加占用资源**。
- **配额会卡住 surge**:`maxSurge` 要创建超出期望数的 Pod,如果 namespace `ResourceQuota` 或节点资源不够,**surge Pod 起不来 → 滚动卡住**。所以"`maxUnavailable=0` 零容量损失"的前提是**有富余配额**。
- **缩容期的优雅**:HPA 缩容也是删 Pod,同样触发 ch03 的优雅下线——别以为只有发布才需要 preStop,**缩容、节点 drain 一样需要**。

---

## F · VM / 非 k8s 对照

| k8s 机制 | VM / 传统发布对应物 |
|---|---|
| maxUnavailable / maxSurge | **分批滚动**:每批取出 K 台(批大小 = maxUnavailable 的类比),发完健康检查通过再放回 LB,再下一批 |
| 先 surge 后撤(零容量损失) | 蓝绿:新版整组起好、健康后 LB 权重一次性切过去,旧组留着备回滚 |
| 滚动时序(新 ready 才撤老) | 每批:**先从 LB 摘 → 部署 → 健康检查 → 放回 LB → 下一批** |
| PDB | 发布工具/编排脚本里的"最少保留 N 台在线"约束 |
| rollout undo | 保留上一版本制品 + 一键切回(蓝绿换权重最快) |

> 蓝绿在 VM 上特别香的原因:**切换 = LB 权重瞬切,回滚 = 权重切回**,几秒级、不掉请求(前提同样是新组已健康、schema 兼容)。代价是要双倍资源。滚动省资源但过程更长、更依赖单实例的优雅上下线做对。

---

## 踩坑框 ⚠️

> **`maxUnavailable>0` 但容量已紧** → 滚动期容量下凹,扛不住当前流量 → 滚动中就 5xx。要零损失用 `maxUnavailable=0 + maxSurge>0`(A)。

> **`maxSurge>0` 但配额/节点不够** → surge Pod 起不来,滚动卡死。先确认有富余资源(E)。

> **`minReadySeconds=0` + 新 Pod 抖动** → 翻 ready 又崩的被当可用,撤了老 Pod → 容量塌(B)。

> **以为 PDB 能保证优雅滚动** → PDB 管自愿中断的 eviction、不管 Deployment 自身滚动;且 PDB ≠ preStop(C)。

> **以为配了 PDB 就不用 preStop** → 两个层次:PDB 保"不一次拿太多",preStop 保"拿走的那个走得干净"。缺 preStop 照样掉请求(C2)。

> **能滚动发布但回滚卡住** → 多半是 schema 不兼容,代码回滚了数据回不去。变更要 expand-contract、向后兼容(D)。

> **只给发布配优雅、忘了缩容/drain** → HPA 缩容、节点 drain 同样删 Pod、同样需要 preStop(E)。

---

## 面试速记卡(只做复习自检)

**人人会的**
- 滚动更新是什么?→ 逐批用新版 Pod 替换老版,过程中服务不中断。

**资深分水岭** ⭐
- 滚动时怎么保证不掉容量?→ `maxUnavailable=0 + maxSurge>0`:先把新 Pod 起好 Ready 再撤老 Pod(先涨后落),代价是要资源余量。
- maxUnavailable 和 maxSurge 分别控制什么?→ 前者=容量底线(最多掉几个),后者=资源上限(最多多起几个)。
- 滚动一步的真实时序?→ 起新 Pod → 等它预热 ready + 稳过 minReadySeconds → 才删一个老 Pod(触发优雅下线)→ 循环。串起了 ch02 和 ch03。
- PDB 管什么?→ 自愿中断(drain/升级/缩容)时保证最少可用数,阻塞会违反预算的 eviction;不管节点宕机这类非自愿中断,也不等同于 Deployment 自身的滚动策略。

**架构师**
- PDB 能替代优雅下线(preStop)吗?→ 不能。PDB 是 fleet 级"不一次拿太多",preStop 是单 Pod 级"走得干净",两层正交,都要。
- 为什么"能发布却回滚不了"?→ 通常卡在数据层:schema 不兼容,代码可回滚但数据回不去。要 expand-contract 兼容变更。
- VM 上怎么零停机滚动?→ 分批:摘 LB→部署→健康检查→放回→下一批;或蓝绿权重瞬切(双倍资源、秒级回滚)。

---

## 小结 + 桥接

> **滚动编排 = 把 ch02+ch03 用"先 ready 后撤老"的时序串成流水线,再用旋钮控幅度**:`maxUnavailable`(容量底线)/`maxSurge`(资源上限)决定容量曲线,`minReadySeconds` 防抖动,**PDB 保 fleet 级"不一次拿太多"(≠ preStop 的单 Pod 排空)**;零停机还要能秒级回滚,而回滚常卡在数据兼容。

- 每一步里"新 Pod 怎么算真 ready" → [`ch02 优雅上线`](./02-graceful-startup.md) + [`ch01 健康信号`](./01-health-signals.md)
- 每一步里"老 Pod 怎么走得干净" → [`ch03 优雅下线`](./03-graceful-shutdown.md)
- 发布**策略**选型(蓝绿/金丝雀/滚动)、schema 迁移 → [`system-design/09`](../../system-design/09-發布與變更管理.md)
- 渐进交付 / 自动金丝雀 / GitOps → [`cloud-native-landscape/06`](../../cloud-native-landscape/06-delivery-gitops-progressive.md)
- 兼容变更 expand-contract → [`python-data/07`](../../python-data/07-migrations.md)

➡️ 下一章:[`ch05 连接生命周期`](./05-connection-lifecycle.md) — 为什么上面这一切做对了,长连接还是能让"摘流量"失效。
