# 01 — 健康信号:liveness / readiness / startup 三探针

> 核心问题:整个 track 的不变式是「流量只打到 ready 且不在退场的实例」。可**谁来判定"ready"、谁来判定"该摘流量"?** 就是探针。三探针是上下半场共同的裁判——ch02 优雅上线靠它判定"热了没",ch03 优雅下线靠它判定"该摘了没"。先把裁判讲清,后面两章才站得住。

> 一句话先钉死分工:**liveness 管"要不要重启",readiness 管"给不给流量",startup 管"慢启动期间先别让前两个乱来"。** 三个探针、三件事,别混成"健康检查"一锅。

---

## A · 三探针语义 + 失败→动作(背下这张表)

| 探针 | 它问什么 | 失败了 kubelet 干什么 | 该查什么 |
|---|---|---|---|
| **liveness** | 进程还活着、没卡死吗? | **重启容器**(按 restartPolicy) | 只查**自身**(能不能响应),**绝不查外部依赖** |
| **readiness** | 现在能接流量吗? | **从 Endpoints 摘掉**(Service 不再路由),**不重启** | 可查关键依赖,但要权衡(见 E) |
| **startup** | 启动完成了吗?(慢启动专用) | 没成功前**门控** liveness/readiness(不让它们跑);超过预算才判失败→重启 | 查"初始化是否完成"(端口起没起、预热完没完) |

关键区别一句话:

> **liveness 失败 = "你坏了,重启你";readiness 失败 = "你没坏,但先别接活";startup 失败 = "你启动太久了,放弃等了"。**

最容易混的是 **liveness vs readiness**:都"探健康",但**动作天差地别**——一个重启(破坏性),一个摘流量(可逆)。把依赖检查放错探针,是本章头号事故源(见 E)。

---

## B · 谁在消费这三个信号 ⭐(这决定了 ch03 的竞态)

三个探针**都由 kubelet 在节点本地执行**,但结果的"消费者"不同,传播路径也不同:

```
  kubelet(节点本地,定时探三个探针)
     │
     ├─ liveness 失败 ──▶ kubelet 本地直接重启容器           ← 本地、立即
     ├─ startup  失败 ──▶ kubelet 本地直接重启容器           ← 本地、立即
     │
     └─ readiness 结果 ──▶ 更新 Pod 的 Ready condition
                              │
                              ▼  (走控制面,异步)
                       Endpoints/EndpointSlice controller watch 到 Ready 变化
                              │
                              ▼
                       kube-proxy(每个节点改 iptables/ipvs)
                       Ingress controller(改 upstream)
                       云 LB / CoreDNS …… 各自更新
                              │
                              ▼
                       流量才真正不再(或开始)打到这个 Pod
```

**这张图是 ch03 那个竞态的根**:liveness/startup 的动作是 kubelet **本地立即**的;而 readiness 要"摘流量",得**经过控制面多跳异步传播**(Pod Ready → EndpointSlice → kube-proxy/LB),有 lag。所以:

> **readiness 是 app 唯一能拨动"流量开关"的手柄,但这只手柄是"软"的——你拨了不等于流量立刻停,中间隔着一条最终一致的传播链。** ch03 的 preStop 就是为了覆盖这条链的 lag。

VM 世界同构:readiness 对应"注册中心里这个实例的健康状态 / LB 主动健康检查的结果",拨动后也要等调用方刷新本地服务列表,一样有 lag。

---

## C · startup 探针:为什么需要第三个

很多人只配 liveness + readiness,直到被一个慢启动应用坑了才懂 startup 的价值。

问题场景:一个 JVM / 大模型加载 / 要建一堆连接的服务,**启动要 60s**。你给 liveness 配了 `periodSeconds=10, failureThreshold=3`(30s 内探 3 次失败就重启)。结果:

> 进程还在正常启动(第 40s),liveness 已经探了 3 次都失败 → kubelet **重启**它 → 重启后又是慢启动 → 又被 liveness 干掉 → **永远起不来的重启循环**。

老办法是把 liveness 的 `initialDelaySeconds` 调很大(比如 90s),但这有副作用:**真·卡死也要等 90s 才被发现重启**。startup 探针解决这个两难:

- startup 没成功前,**liveness/readiness 完全不跑**(被门控),所以慢启动期间不会被误杀;
- startup 的 `failureThreshold × periodSeconds` = **允许的最长启动时间**(比如 `failureThreshold=30, periodSeconds=5` → 给 150s 启动);
- 一旦 startup 成功,liveness/readiness 接管,且 liveness 可以配得很灵敏(短周期),真卡死能快速发现。

> 一句话:**startup 把"慢启动的宽容"和"运行期的灵敏"解耦**——启动期给足耐心,启动完立刻严格。

---

## D · readiness 是不变式的执行者(承上启下)

回到 track 的不变式。readiness 几乎是它在 app 层的唯一执行手柄,**两个半场都靠它**:

- **入场(ch02)**:实例预热没完,readiness 就该返 **not ready**,把流量挡在"热"之前。"进程起来"不等于"readiness=true",中间隔着预热——这是 ch02 的主题。
- **退场(ch03)**:实例要下线,主动让 readiness 返 **not ready**,加速从 Endpoints 摘除。

所以 readiness 探针的实现质量,直接决定上下两个半场成不成立。**它不是"健康检查"那么简单,它是你对"我能不能服务"这个判断的代码化。** liveness 反而简单(只回 200 证明没死),readiness 才是要动脑子的那个。

---

## E · 经典坑 ⚠️(都来自"探针选错/配错")

> **liveness 探了外部依赖(DB/Redis/下游)** → 这是头号大坑。DB 抖一下 → 所有副本的 liveness 一起失败 → kubelet 把**整个 fleet 全重启** → 重启风暴,把本来只是抖动的小事变成全面宕机。**铁律:liveness 只查自身,绝不查依赖。** 依赖检查放 readiness。

> **readiness 探共享依赖的两难(架构师题)** → readiness 查共享 DB 看似对,但若该 DB 抖动,**所有副本同时 not ready → 流量无处可去 → 全站 503**。两种取舍:(a) readiness 只查"我自己能不能干活"、对下游错误用熔断/降级/快速失败处理,别让一个共享依赖打趴整排;(b) 真要查依赖,配合较高的 failureThreshold + 熔断,别一抖就全摘。**核心:readiness 失败是"全副本同步"的,容易把局部问题放大成全局。**

> **readiness 抖动 → 流量摆动** → 探针 timeout 设太短 / 依赖偶发慢,导致 readiness 在 true/false 间跳 → Pod 反复进出 Endpoints → 流量忽冷忽热、连接频繁重建。调 `timeoutSeconds`、`failureThreshold`、`successThreshold` 给它迟滞。

> **慢启动只调大 liveness initialDelay** → 副作用是运行期真卡死也要等那么久才发现。用 **startup 探针**解耦(C)。

> **探针端点做了重活** → `readiness` 里 `SELECT count(*)` 整张表 / 探针打到业务慢路径 → 探针本身成了负载。探针要轻(`SELECT 1` 级别)。

> **三个探针配同一个 endpoint** → liveness 和 readiness 指向同一个"查了依赖"的 `/health` → 依赖一挂,既摘流量又重启,最坏组合。分开:`/health/live`(只回 200)和 `/health/ready`(查依赖)。

---

## F · VM / 非 k8s 对照:同样三件事,换裁判

没有 kubelet,这三件事谁来做?

| k8s 探针 | VM / 注册中心世界对应物 |
|---|---|
| **liveness**(失败→重启) | 进程守护:`systemd` `Restart=on-failure` + watchdog(`WatchdogSec`,见 [`linux-handson/08`](../../linux-handson/08-systemd-and-services/README.md));supervisor |
| **readiness**(失败→摘流量) | **LB 健康检查**:主动(LB 定时打 `/health`)或被动(连续 N 次真实请求失败→摘);**注册中心健康状态**(Nacos/Consul 的 health check、Eureka 心跳) |
| **startup**(门控慢启动) | LB/注册中心的 `initialDelay` / 延迟注册(等启动完再注册,见 [ch02](./02-graceful-startup.md)) |
| readiness 传播 lag | 调用方/网关的**本地服务列表缓存**刷新延迟(Ribbon 等客户端负载均衡) |

主动 vs 被动健康检查的区别值得记:**主动**=LB 定时探一个探活端点(发现快、但要 LB 支持,nginx OSS 不支持主动);**被动**=LB 看真实流量的成败,连续失败才摘(零额外开销、但要"牺牲"几个真实请求才发现,且开源 nginx 就是这种)。详见 [`gateway/03`](../../gateway/03-routing-and-load-balancing.md)。

---

## 面试速记卡(只做复习自检)

**人人会的**
- liveness vs readiness?→ liveness 失败重启容器(只查自身),readiness 失败摘流量不重启(可查依赖)。

**资深分水岭** ⭐
- 为什么 liveness 不能查 DB?→ DB 抖动会让所有副本 liveness 一起失败 → 整个 fleet 被重启 → 重启风暴,小事变宕机。
- readiness 查共享依赖有什么风险?→ 依赖一抖所有副本同时 not ready → 流量无处去 → 全站 503;局部问题被放大成全局。取舍:只查自身 + 熔断降级,或高阈值 + 迟滞。
- 谁消费 readiness,和 liveness 有何不同?→ liveness/startup 是 kubelet 本地立即动作(重启);readiness 走控制面异步传播(Pod Ready→EndpointSlice→kube-proxy/LB)才摘流量,有 lag——这正是 ch03 竞态的根。
- startup 探针解决什么?→ 慢启动应用被 liveness 在启动期误杀的重启循环;它门控前两者,`failureThreshold×periodSeconds`=允许的最长启动时间,启动完才让 liveness 灵敏接管。

**架构师**
- readiness 失败是"同步全副本"的,如何防止把局部问题放大成全局?→ 别让单个共享依赖 gate 全部 readiness;用熔断/降级/负载脱落在 app 内处理下游故障,readiness 主要反映"自身能否服务"。
- VM 上没有 kubelet,这三件事谁做?→ liveness=systemd Restart/watchdog;readiness=LB 主/被动健康检查 + 注册中心健康状态;startup=延迟注册/initialDelay。

---

## 小结 + 桥接

> **三探针 = 不变式的裁判**:liveness 判"重启"(只查自身,查依赖会引发重启风暴)、readiness 判"给不给流量"(走控制面异步传播,是 ch03 竞态的根、也是 ch02 入场门控的手柄)、startup 判"慢启动期间先按住前两个"。

- readiness 怎么在**入场**时挡住没热的实例 → [`ch02 优雅上线`](./02-graceful-startup.md)
- readiness 摘流量的**传播 lag**怎么在退场时制造竞态、怎么用 preStop 治 → [`ch03 优雅下线`](./03-graceful-shutdown.md)
- probe 配置/调试实操 → [`cloud-native/08`](../../cloud-native/08-debug-pod-not-starting.md)
- LB 健康检查(主动/被动) → [`gateway/03`](../../gateway/03-routing-and-load-balancing.md)
