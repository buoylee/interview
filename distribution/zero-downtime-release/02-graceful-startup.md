# 02 — 优雅上线:readiness gating + 预热 + slow-start

> 核心问题:ch03 讲"实例走的时候别掉请求",这一章讲对称的另一半——**实例来的时候,别在它"还没热"的时候就把流量塞给它。** 这是不变式里的危险①。
>
> 一句话点破:**`进程起来` ≠ `能服务`。** 中间隔着一段"冷"——连接池空、缓存空、JIT 没热、下游连接没建。在这段冷期间接流量 = 慢、错、甚至把自己和下游一起拖垮。优雅上线 = 用机制把流量挡在"热"之前。

> 这一章在仓库里几乎是空白(grep `优雅上线`/`graceful startup`/`minReadySeconds` 零命中),但面试官只要问完优雅下线,**下一句大概率就是"那新实例怎么保证热了才接流量"**。

---

## A · 为什么新实例是"冷"的

进程刚起来,这些东西都还没就位:

| 冷在哪 | 第一批请求会怎样 |
|---|---|
| **连接池空**(DB/Redis/下游 HTTP 池 size=0 或最小) | 每个请求现场建连接(TCP+TLS 握手),慢;并发一来,池来不及扩,排队 |
| **本地缓存空**(进程内缓存、字典、模型) | 全部 miss → 全打到后端 → 后端被这台新实例的回源流量打一波 |
| **JIT / 解释器没热**(JVM C1/C2、PyPy、V8) | 热点代码还在解释执行,前几千次请求慢几倍(JVM 尤其明显) |
| **下游长连接没预建**(gRPC channel、连接池预热) | 首次调用要建链路 |
| **依赖还没就绪**(DB 迁移没跑完、配置没拉到) | 直接报错 |

> 单台冷一点点不致命;**致命的是"一批新实例同时冷 + 立刻接全量流量"**(扩容、滚动、重启风暴),那会放大成雪崩(见 C)。

---

## B · 五件机制:把流量挡在"热"之前 ⭐

### B1 readiness gating —— 最核心的一招

回顾 [ch01](./01-health-signals.md):readiness=false 时,流量不会来。优雅上线的根本手法就是:

> **预热没做完,readiness 就一直返 not ready;预热完成,才翻成 ready。** 把"预热"这件事塞进 readiness 变 true 之前。

```python
# 示意:启动时预热,预热完才允许 readiness 通过
_warm = False

@asynccontextmanager
async def lifespan(app):
    await app.state.pool.connect(min_size=10)   # 预建连接池
    await warmup_caches()                        # 预载热点缓存
    await prime_downstream()                     # 预建下游连接 / 触发 JIT
    global _warm; _warm = True                   # ← 热了,现在才放行
    yield

@app.get("/health/ready")
async def ready():
    if not _warm:
        return Response(status_code=503)         # 没热,别给我流量
    return {"status": "ready"}
```

**这是 ch03 readiness-first 的镜像**:退场时 readiness 翻 false 摘流量;入场时 readiness 拖到热了才翻 true 放流量。同一个手柄,两个方向。

### B2 startup 探针 —— 给慢启动足够耐心(回链 ch01)

预热本身可能很久(JVM 30s+、加载模型几分钟)。用 **startup 探针**门控,别让 liveness 在预热期把它误杀(机制见 [ch01 C](./01-health-signals.md))。`failureThreshold × periodSeconds` 给足预热预算。

### B3 LB slow-start —— 流量爬坡,而不是一上来就均摊全量

即使 readiness=true,也别让新实例**瞬间**接 `1/N` 的全量流量(N 台时每台的份额)。**slow-start** 让 LB 给新就绪的后端**逐渐**加权:

- nginx Plus `slow_start=30s`、Envoy slow start mode、Dubbo `warmup` 参数(按启动后时长线性升权)。
- 效果:新实例前 30s 只接一点点流量,边接边把池/缓存/JIT 真正热透,再逐步加到满。
- **注意**:这是对"readiness 是个布尔、热是连续的"这一矛盾的补丁——readiness 只能说"我可以开始接了",但"完全热"还要一点时间,slow-start 填这段。

### B4 minReadySeconds —— 刚 ready 别马上被当成"稳了"

`minReadySeconds`:一个 Pod **Ready 后还要稳定存活这么多秒**,才被滚动更新算作"可用"(available)。作用:

- 防"翻 ready 又立刻崩"的抖动 Pod 被当成好的,导致滚动把老 Pod 提前撤了 → 容量塌方。
- 给监控/告警一个观察窗口。
- 它直接影响 ch04 的滚动节奏:**新 Pod 要 Ready 且稳过 minReadySeconds,滚动才肯撤老 Pod**(见 [ch04](./04-rollout-orchestration.md))。

### B5 主动预热手段(readiness 翻 true 之前做)

- **预建连接池**:启动时把 DB/Redis/下游 HTTP 池的 `min_size` 建起来,别等第一个请求。
- **缓存预载**:把热点 key / 字典 / 配置 / 模型在启动时加载好。
- **合成预热请求**:启动时自己给自己打一批典型请求,触发 JIT 编译、走热代码路径(JVM 服务常见)。
- **依赖就绪等待**:init container / `wait-for-it` 等 DB、迁移完成再起 app。

---

## C · 冷启动雪崩 ⭐(架构师高频)

把"新实例冷"和"分布式放大"叠加,就是这个经典事故:

```
  流量高峰 → HPA 触发扩容 → 一次性拉起 5 个新 Pod(全冷)
     → 它们刚 ready 就各自被均摊 1/N 全量流量
     → 冷实例处理慢(池空、缓存 miss、JIT 没热)→ 响应变慢 / 超时
     → 上游重试 → 把冷实例打得更狠 → 它们 OOM / 被 liveness 误判重启
     → 容量不增反减 → 雪崩
```

成因链:**冷 + 立刻全量 + 重试放大**。对应的解药正好是 B 那几招:

- **slow-start**:新实例流量爬坡,不一上来全量(治"立刻全量")。
- **预热 + readiness gating**:热了才接(治"冷")。
- **下游限流/熔断 + 重试预算**:别让重试把冷实例打死(治"重试放大",见 [`system-design/01`](../../system-design/01-韌性-依賴掛了怎麼不崩.md))。
- **扩容别太激进 / 预扩容**:高峰前提前扩(warm pool),别等打满了才临时拉冷实例。

> 面试点:**"扩容了反而更慢/更挂"几乎都是冷启动雪崩。** 能把"冷 + 全量 + 重试"这条放大链说清,就到位了。

---

## D · VM / 非 k8s 对照

| k8s 机制 | VM / 注册中心世界对应物 |
|---|---|
| readiness gating(热了才 ready) | **延迟注册**:预热完成才向 Nacos/Eureka/Consul 注册(Spring Cloud:`ApplicationReadyEvent` 后 + 预热钩子完成才 register) |
| LB slow-start | 注册中心 / LB **权重渐进**:Dubbo provider `warmup`(默认 10min 内线性升权)、Nacos 权重、LB 初始低权重 |
| startup 探针门控 | 注册前的初始化等待 / 健康状态先报 starting |
| minReadySeconds | 灰度观察窗口 + 健康稳定才纳入 LB |

> Dubbo 的 `warmup` 是 B3 slow-start 的最直白实现:**provider 启动后的前 N 分钟,consumer 端按"已启动时长 / warmup"比例给它降权**,新节点自然只接一小部分流量,热透了才满载。机制和 k8s slow-start 一模一样。

---

## 踩坑框 ⚠️

> **进程起来就翻 readiness=true** → 没预热就接流量,首批请求慢/错;并发一来池来不及扩。预热完再翻 ready(B1)。

> **readiness=true 后立刻接全量** → 冷实例被瞬时全量打慢/打挂。用 slow-start 让流量爬坡(B3)。

> **高峰临时扩容反而更挂** → 冷启动雪崩(C):冷 + 全量 + 重试放大。slow-start + 预热 + 下游限流 + 预扩容。

> **预热很久被 liveness 误杀** → 用 startup 探针门控(B2/ch01),别只调大 liveness initialDelay。

> **minReadySeconds=0 + 抖动 Pod** → 翻 ready 又崩的 Pod 被当可用,滚动撤了老 Pod → 容量塌。给 minReadySeconds 一个观察窗(B4)。

> **VM 下预热没完就注册** → 调用方立刻把流量打到冷实例。延迟注册 + 权重渐进(D)。

---

## 面试速记卡(只做复习自检)

**人人会的**
- 怎么保证新实例不接到没准备好的流量?→ readiness 探针,没就绪返 503,流量不来。

**资深分水岭** ⭐
- "进程起来"为什么不等于"能接流量"?→ 连接池空、缓存空、JIT 没热、下游连接没预建、依赖没就绪;冷期间接流量会慢/错。
- 怎么做优雅上线?→ 预热(预建池/预载缓存/合成请求触发 JIT)放在 readiness 翻 true 之前;startup 探针给足预热时间;LB slow-start 让流量爬坡;minReadySeconds 防抖动。
- 什么是冷启动雪崩?→ 一批冷实例刚 ready 就接全量 → 慢 → 上游重试放大 → 冷实例被打挂 → 容量不增反减。解:slow-start + 预热 + 下游限流/熔断 + 预扩容。
- slow-start 和 readiness 什么关系?→ readiness 是布尔("可以开始接了"),但"完全热"是连续的;slow-start 填 readiness=true 之后到真正热透的那段,让流量逐步加。

**架构师**
- minReadySeconds 在滚动里起什么作用?→ 新 Pod 要 Ready 且稳过 minReadySeconds 才算 available,滚动才撤老 Pod;防抖动 Pod 导致容量塌(接 ch04)。
- VM 上怎么优雅上线?→ 延迟注册(预热完才进注册中心)+ 权重渐进(Dubbo warmup / LB 初始低权重)。

---

## 小结 + 桥接

> **优雅上线 = 把流量挡在"热"之前**:readiness gating(热了才 ready)+ startup 探针(给足预热时间)+ slow-start(流量爬坡)+ minReadySeconds(防抖动)+ 主动预热(预建池/预载缓存/触发 JIT)。最大的事故是**冷启动雪崩**(冷+全量+重试放大)。

- 它依赖的 readiness 探针语义 → [`ch01 健康信号`](./01-health-signals.md)
- 它的对称另一半(退场) → [`ch03 优雅下线`](./03-graceful-shutdown.md)
- minReadySeconds 怎么决定滚动节奏 → [`ch04 滚动编排`](./04-rollout-orchestration.md)
- 冷实例被重试打挂背后的韧性机制(熔断/限流/重试预算) → [`system-design/01`](../../system-design/01-韌性-依賴掛了怎麼不崩.md)
- 应用启动时的 lifespan 预热写法(Python) → [`fastapi-ops/01` A8](../../fastapi-ops/01-foundation/README.md)
