# 零停机发布与实例生命周期(机制层)

> 一句话定位:这是坐在 [`system-design/09 发布与变更管理`](../../system-design/09-發布與變更管理.md)(**策略层**:蓝绿/金丝雀/滚动该选哪个)**之上的机制层**——只回答一件事:**这些发布策略,底层到底靠什么机制做到「不掉一个请求」?**
>
> 受众:资深 / 架构师面试 + 工作。读完你能从 `kubectl delete` 那一刻**逐拍**讲到进程退出,讲清中间每一个会掉请求的竞态,以及修它的招牌机制。

---

## 开篇 · 一个小问题,牵出一整个系统

很多人对「优雅停机」的理解停在单机那层:**收到 SIGTERM → 停止接新请求 → 排空在途 → 关池退出**。这套在 [`fastapi-ops/01`](../../fastapi-ops/01-foundation/README.md) 已经讲透了——单个进程内部怎么优雅关。

但真到生产,你会发现一个诡异现象:**app 层的优雅关明明写对了,滚动发布时还是间歇性掉请求 / 502 / connection reset。** 为什么?

因为「单实例怎么优雅关」只是整个故事的一小块。真实的生产是**一个 fleet(一堆实例)在负载均衡后面**,发布 = 这堆实例**一边下线旧的、一边上线新的**,流量在中间被路由器/LB 不停地重新分发。掉请求往往不是 app 关错了,而是:

- 流量层(Endpoints / LB)还没来得及知道"这个实例要走了",就把请求送了过来;
- 或者反过来,新实例进程起来了但**还没热**,就被塞了流量;
- 或者老连接是 **keep-alive 长连接**,"摘流量"对它根本无效。

**这些都不是 app 层的问题,是实例生命周期 + fleet 编排 + 连接层的问题。** 这个 track 就是把这一整层讲成系统。

---

## 核心不变式:整个 track 只为守住这一条

> **流量只能打到「已就绪(ready)AND 不在退场(leaving)」的实例。**

记住这一条,后面所有机制都是它的推论。这条不变式在**实例一生中的两个时刻**最容易被破坏:

```
            ┌──────────────────── 一个实例的一生 ────────────────────┐
  创建 ─▶ 启动 ─▶ [危险①: 还没热就接流量] ─▶ ready ─▶ 服务中 ─▶ [危险②: 还在服务就被拿走] ─▶ drain ─▶ 终止
                  └─ 优雅上线(ch02)防危险①         └─ 优雅下线(ch03)防危险② ─┘

  ↑ 健康信号(ch01)是裁判:它决定「什么时候算 ready、什么时候算 leaving」,上下两半都靠它
  ↑ 滚动编排(ch04)把这条时间线 ×N 个实例并行起来
  ↑ 连接生命周期(ch05)解释:为什么"摘流量"对已建立的长连接无效
```

- **危险①(入场)**:进程起来 ≠ 能服务(连接池冷、缓存空、JIT 没热)。没拦住就把流量塞给一个没准备好的实例 → 慢、错、甚至雪崩。
- **危险②(退场)**:实例还在处理在途请求,就被 LB 继续导流 / 被进程硬杀 → 掉请求。

整个发布过程,就是**无数个实例反复经历这两个危险时刻**,而你要保证全程不变式不破。

---

## 六支柱地图

| # | 支柱(机制层) | 它回答的面试题 | 在哪 |
|---|---|---|---|
| 1 | **健康信号** liveness / readiness / startup 三探针 | "探针有几种,失败分别会怎样?谁在消费 readiness?" | [ch01](./01-health-signals.md) |
| 2 | **优雅上线** readiness gating + 预热 + slow-start | "新实例怎么保证'热了'才接流量?没热就上会怎样?" | [ch02](./02-graceful-startup.md) |
| 3 | **优雅下线** SIGTERM→排空→SIGKILL + **preStop** + 传播竞态 | "Pod 删除到进程退出经历了什么?为什么还掉请求?" | [ch03](./03-graceful-shutdown.md) ⭐ |
| 4 | **滚动编排** maxSurge / maxUnavailable / PDB / minReadySeconds | "零停机发布怎么编排?滚动时怎么保证不掉容量?" | [ch04](./04-rollout-orchestration.md) |
| 5 | **连接生命周期** keep-alive / 长连接 drain / GOAWAY | "LB 摘了为什么旧连接还在打?WebSocket/gRPC 怎么优雅断?" | [ch05](./05-connection-lifecycle.md) |
| 6 | **兼容变更** expand-contract / 向后兼容 / deploy≠release | "滚动期两版本并存,schema 怎么改不出事?" | 已有家 → [system-design/09](../../system-design/09-發布與變更管理.md)、[python-data/07](../../python-data/07-migrations.md) |

> 支柱 6(数据/契约)在仓库里已经有系统覆盖,本 track **只回链不重写**(守"指进深矿不重写")。

---

## 这个 track 和别处的边界(避免你来回找)

| 你想找 | 去哪 |
|---|---|
| 蓝绿/金丝雀/滚动**该选哪个**(策略与取舍) | [`system-design/09`](../../system-design/09-發布與變更管理.md) — 策略层,本 track 的上游 |
| 单进程内部**怎么优雅关**(Python/uvicorn 细节) | [`fastapi-ops/01`](../../fastapi-ops/01-foundation/README.md) |
| Go `http.Server.Shutdown` 排空语义 | [`golang/stdlib/01`](../../golang/stdlib/01-net-http/README.md)、[`golang/service-design`](../../golang/service-design/) |
| systemd `TimeoutStopSec` / 信号机制 | [`linux-handson/08`](../../linux-handson/08-systemd-and-services/README.md) |
| k8s 对象模型 / probe 调试基础 | [`cloud-native/`](../../cloud-native/) |
| 渐进交付 / GitOps / canary 机制 | [`cloud-native-landscape/06`](../../cloud-native-landscape/06-delivery-gitops-progressive.md) |
| service mesh(Envoy)流量治理 | [`cloud-native-landscape/04`](../../cloud-native-landscape/04-service-mesh-sidecar-to-ambient.md) |
| 数据迁移 expand-contract | [`python-data/07`](../../python-data/07-migrations.md) |

**本 track 做的是中间那层**:把上面这些「策略」和「单点细节」串成一条**会掉请求 / 不掉请求**的因果链。

---

## 怎么读

- **顺读**:ch01(裁判)→ ch02(入场)→ ch03(退场)→ ch04(放大到 fleet)→ ch05(连接层收口)。
- **面试急救**:直接 ch03 + ch01,够答 80% 的题;再看 ch04 的 maxSurge/PDB 应对架构师追问。
- **动手**:ch03 配一个 [`lab/`](./lab/)(docker-compose,本机可跑)——亲眼看到"丢请求 → 加优雅排空 → 不丢了"。k8s 真集群的 preStop 竞态在 lab 里有可选 kind 附录。

---

## 章节

1. [健康信号:liveness / readiness / startup 三探针](./01-health-signals.md)
2. [优雅上线:readiness gating + 预热 + slow-start](./02-graceful-startup.md)
3. [优雅下线:SIGTERM → 排空 → SIGKILL,与那个掉请求的竞态](./03-graceful-shutdown.md) ⭐ + [lab](./lab/)
4. [滚动编排机制:把单实例放大到 fleet](./04-rollout-orchestration.md)
5. [连接生命周期:为什么"摘流量"常常没用](./05-connection-lifecycle.md)
