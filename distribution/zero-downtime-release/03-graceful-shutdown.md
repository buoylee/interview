# 03 — 优雅下线:SIGTERM → 排空 → SIGKILL,与那个掉请求的竞态

> 核心问题:app 层的优雅关明明写对了(收 SIGTERM、停 accept、排空在途、关池),**为什么滚动发布时还是间歇掉请求 / 502 / connection reset?**
> 答案不在 app 里,在 app **外面**:流量层(Endpoints/LB)知不知道"这实例要走了"和进程收没收到 SIGTERM,是**两条不同步的链路**。本章把 `kubectl delete` 到进程退出**逐拍**拆开,讲清那个竞态和修它的招牌机制 `preStop`。

> 前置:单进程内部怎么优雅关,见 [`fastapi-ops/01`](../../fastapi-ops/01-foundation/README.md)(uvicorn `Server.shutdown` 关 socket→排空→lifespan)和 [`golang/service-design`](../../golang/service-design/)(`srv.Shutdown`)。本章默认你已会这套**单点**排空,只讲**分布式**那段。

---

## A · 先把时间线摆出来:删一个 Pod,并发发生两件事

面试里最能分高下的一句话:**"Pod 终止时,'摘流量'和'发 SIGTERM'是两条并行链路,不保证谁先谁后。"** 把这张图刻进脑子:

```
   你执行 kubectl delete pod  /  滚动更新要替换它  /  节点 drain
                    │
                    ▼
         API Server 把 Pod 标记为 Terminating(deletionTimestamp)
                    │
        ┌───────────┴────────────────────────────────────┐
        │                                                 │
   【链路 A:摘流量】                                  【链路 B:杀进程】
   Endpoints/EndpointSlice controller                  kubelet 看到 Terminating
   把这个 Pod 的 IP 从 Endpoints 移除                    │
        │                                               ├─▶ 先跑 preStop hook(若配了)
   kube-proxy / Ingress / 云LB / CoreDNS                │      ……跑完才……
   各自 watch 到变化,更新自己的转发表                    ├─▶ 给容器 PID 1 发 SIGTERM
        │  ← 多跳、异步、最终一致,有 lag                 │
   新连接不再被路由到这个 Pod                            └─▶ 等 terminationGracePeriodSeconds
                                                              到点还没退 → SIGKILL 硬杀
```

关键认知:

- **链路 A(摘流量)是"最终一致"的多跳广播。** Endpoints 变了,要等 kube-proxy 在每个节点改 iptables/ipvs、Ingress controller 改 upstream、云 LB 改 target、DNS TTL 过期……每一跳都有延迟,整体几百毫秒到几秒不等。
- **链路 B(杀进程)是"本地、立即"的。** kubelet 在 Pod 所在节点直接动手,preStop 一跑完就发 SIGTERM。
- **两条链路没有互相等待。** 默认情况下,**链路 B 往往跑得比链路 A 快**——SIGTERM 都发到进程了,某个节点的 kube-proxy / 某个客户端的 DNS 缓存还指着这个正在关的 Pod。

---

## B · 竞态核心 ⭐:为什么"app 优雅关写对了"还掉请求

> **面试分水岭。讲清这题,面试官就知道你真在生产滚过、而不是背了个 `srv.Shutdown`。**

把 A 的两条链路叠在一根时间轴上,掉请求的窗口就暴露了:

```
  t0  Pod → Terminating
  t0  kubelet 发 SIGTERM ──▶ 你的 app 开始优雅关:关监听 socket、不再 accept 新连接
  t0+ε  ……但此刻 kube-proxy/Ingress/云LB 还没更新,仍在往这个 Pod IP 转发新连接……
        ▼
  新连接打到一个"已经关了监听 socket"的进程 → 内核回 RST → 客户端看到 connection refused / 502
        ▲
  t0+Δ  链路 A 终于传播完,流量不再来 —— 但 [t0, t0+Δ] 这段窗口的请求已经掉了
```

**根因一句话:你的 app 太"听话"了——SIGTERM 一到就老实关 socket,但这时候它在流量层"还在岗"。** 关早了,就在摘流量完成前制造了一个"拒绝新连接"的黑洞。

这就解释了开篇的悖论:**app 层排空逻辑完全正确,问题出在"什么时候开始排空"和"流量层什么时候摘干净"对不齐。** 单点优雅 ≠ 分布式优雅。

> 注意区分两种掉法:
> - **拒新连接**:进程关 socket 后,新连接吃 RST(上面这种,最常见)。
> - **掐在途**:进程没排空就被 SIGKILL,已建立的请求被截断。这种是 grace 时间没算够(见 D),或信号没传到(容器 PID 1 陷阱,见 [`fastapi-ops/01` B′2](../../fastapi-ops/01-foundation/README.md))。

---

## C · 修复:`preStop` + readiness-first,以及为什么缺一不可 ⭐

招牌解法两件套,**仓库别处都没讲过,这是本章的核心交付**:

### C1 第一招:`preStop` sleep —— 把 SIGTERM 推迟到摘流量之后

回看 A 图:kubelet 在发 SIGTERM **之前**会先跑 `preStop` hook,**跑完才发 SIGTERM**。所以只要让 preStop "睡一会儿",就等于**人为延后 SIGTERM**,给链路 A(摘流量)留出传播时间:

```yaml
lifecycle:
  preStop:
    exec:
      command: ["sleep", "15"]    # 睡过 endpoint 传播窗口,再让 SIGTERM 真正触发优雅关
```

时间轴就变成:

```
  t0   Pod → Terminating;链路 A 开始摘流量(异步传播)
  t0   kubelet 开始跑 preStop: sleep 15 ──▶ 进程此刻【还在正常服务】,socket 没关
  t0+Δ 链路 A 摘干净,新流量不再来(Δ 通常 1~5s)
  t0+15 preStop 睡醒 ──▶ kubelet 这才发 SIGTERM ──▶ app 现在才开始关 socket、排空在途
                          此刻已经没有新连接进来,关 socket 不再制造黑洞 ✅
```

**精髓:让进程在"流量层还没摘干净"的那段窗口里继续正常服务,而不是急着关。** sleep 几秒(经验值 5~20s,取决于你的 LB 传播有多慢)覆盖掉传播 lag,竞态就消失了。

> 没有 `sleep` 命令的镜像(distroless/scratch),用别的方式延时:`preStop: httpGet` 打一个自家"开始下线"端点、或镜像里塞个静态 `sleep` 二进制、或在 app 里收到 SIGTERM 后**先自己 sleep 再开始关**(等价效果,但不如 preStop 干净,因为 SIGTERM 已经到了)。

### C2 第二招:readiness 提前转 fail —— 主动加速摘流量

光靠 preStop "被动等"还不够优雅:你可以**主动**让这个实例更快从 Endpoints 摘掉。做法是在收到下线信号时,**让 readiness 探针开始返回失败**:

```python
# FastAPI 示意:进程级开关,收到 SIGTERM 就翻
import signal
_shutting_down = False

@app.get("/health/ready")
async def ready():
    if _shutting_down:
        return Response(status_code=503)      # 主动告诉 k8s:别再给我导流量了
    await app.state.pool.execute("SELECT 1")
    return {"status": "ready"}

def _on_term(*_):
    global _shutting_down
    _shutting_down = True
signal.signal(signal.SIGTERM, _on_term)        # 实际生产更可能用 preStop 触发,见下方"配方"
```

readiness 一失败 → Endpoints controller 更快把它摘掉 → 链路 A 提速。

### C3 为什么单靠 readiness-fail 不够,必须配 preStop

这是最容易答错的追问。**readiness 转 fail 只是"加速"摘流量,它没消除竞态**:

- readiness 失败本身也要**经过链路 A 那套异步传播**(probe 周期 + Endpoints 更新 + kube-proxy/LB 同步),不是瞬间生效;
- 而 SIGTERM 仍然在链路 B 上**可能先到**。

所以正确姿势是 **preStop 兜底等待(保证下界)+ readiness-fail 加速(优化上界)**:preStop 的 sleep 保证"无论传播多慢,进程都还在服务";readiness-fail 让传播尽量快结束。**两个一起上,才既不掉请求、又不傻等满 sleep。**

### C4 标准配方(背下来)

```yaml
spec:
  terminationGracePeriodSeconds: 45        # 总预算,要 > preStop + 排空 + 关池(见 D)
  containers:
  - name: app
    readinessProbe:
      httpGet: { path: /health/ready, port: 8000 }
      periodSeconds: 2
      failureThreshold: 2
    lifecycle:
      preStop:
        exec:
          command: ["sh", "-c", "sleep 15"]    # 等链路A摘干净,再让 SIGTERM 触发优雅关
```

配套 app 行为:收到 SIGTERM → 停 accept、排空在途、关池(这套见 [`fastapi-ops/01`](../../fastapi-ops/01-foundation/README.md))。
可选增强:preStop 里先 `curl localhost:.../admin/start-draining` 把 readiness 翻 fail,再 sleep——主动加速 + 被动兜底一步到位。

> 一句话收口:**preStop 解决"关早了"(危险②的拒新连接),grace 时间解决"关晚了被硬杀"(危险②的掐在途)。两个旋钮治两种掉法,别混。**

---

## D · 时间预算:`terminationGracePeriodSeconds` 到底要多大

`terminationGracePeriodSeconds`(默认 **30s**)是 kubelet 从"开始终止"到"SIGKILL 硬杀"的**总宽限**。注意它**包含 preStop 的时间**(preStop 和 grace 倒计时是**同时**开始的,不是 preStop 跑完再开始算)。所以预算公式:

```
terminationGracePeriodSeconds  ≥  preStop_sleep  +  最长在途请求耗时  +  关连接池/flush 余量
       45s(例)               ≥     15s          +        25s         +        几秒
```

踩坑:

- **grace 给小了**:preStop sleep 15s + 一个跑 20s 的慢请求,grace=30 → 还剩 15s 不够排空 → **SIGKILL 掐断在途**。把 grace 调到能覆盖最长请求。
- **app 的排空超时要 < grace**:`srv.Shutdown(ctx)` 的 ctx 超时、uvicorn 的 graceful timeout,都要设得**比 grace 小**,否则 k8s 先 SIGKILL,你的优雅关白写。(对照 [`golang/service-design` 的卡片](../../golang/service-design/99-interview-cards/q-graceful-shutdown.md):Shutdown 超时 < terminationGracePeriodSeconds。)
- **别无脑调大 grace**:grace 太大 → 滚动发布变慢、节点 drain/缩容卡很久。按"最长合理请求 + preStop"算,不是越大越安全。

docker 世界等价物:`docker stop` 默认 `--time 10`(10s 宽限)→ SIGTERM → 不退则 SIGKILL。同一个机制,数字不同。systemd 世界等价物:`TimeoutStopSec`(见 [`linux-handson/08`](../../linux-handson/08-systemd-and-services/README.md))。

---

## E · app 层排空在这一层做什么(简述 + 回链)

preStop 睡醒、SIGTERM 真正到达后,进程内部那套**单点优雅关**才开演,它要干三件事:

1. **停止接新活**:关监听 socket(uvicorn `Server.shutdown` 里 `server.close()`;Go `srv.Shutdown` 停 accept)。
2. **排空在途**:等已经在处理的请求跑完(受排空超时约束)。
3. **释放资源**:关连接池、flush 日志/指标、退后台协程。

机制细节(信号怎么传到 PID 1、`should_exit` 标志、lifespan 下半)本章不重复——Python 见 [`fastapi-ops/01` A8/B′2](../../fastapi-ops/01-foundation/README.md),Go 见 [`golang/stdlib/01`](../../golang/stdlib/01-net-http/README.md)。**本章的贡献是:让这套单点排空在"对的时刻"(流量摘干净后)才开始。**

---

## F · LB 连接排空(deregistration delay):云上那条链路 A

上面讲的链路 A 在 k8s 内部是 Endpoints→kube-proxy。但流量入口往往是**云 LB**(ALB/NLB、SLB),它有自己的一套"摘后端"机制,叫 **connection draining / deregistration delay**:

- 你(或 k8s 通过 cloud-controller)把一个 target 标记为"要摘除" → 云 LB **停止给它分发新连接**,但**已建立的连接继续服务**,直到它们自然结束或超时(deregistration delay,常默认 300s)。
- 这正是云 LB 版的"优雅摘除":不粗暴掐连接,给在途留时间。

要点:

- **deregistration delay 要 ≥ 你的 preStop + 排空时间**,否则 LB 还在排空、Pod 已经被 SIGKILL,一样掉。
- 开源 **nginx OSS 只有被动健康检查**(连续失败 N 次才摘),没有主动 draining;要主动摘除/连接排空,靠 nginx Plus、或上游用 Ingress controller(它 watch Endpoints)、或 reload(见 [`gateway/08`](../../gateway/08-gateway-as-distributed-system.md) 的 nginx reload:新 worker 接新连接、旧 worker 排空在途)。

---

## G · 长连接:为什么"摘流量"对它常常无效(点到,详见 ch05)

链路 A 摘的是**新连接的分发**。但 HTTP **keep-alive** / HTTP/2 多路复用 / WebSocket / gRPC stream / SSE 都是**长连接**——连接早就建好了,LB"不再分发新连接"对**已经建立的这条**毫无作用,客户端会继续在老连接上发请求,直到这条连接关闭。

所以长连接的优雅下线要**额外**做"主动通知对端断开并重连":HTTP/1.1 回 `Connection: close`、HTTP/2 & gRPC 发 **GOAWAY**、WS/SSE 主动 close + 客户端 backoff 重连。这块是 [`ch05 连接生命周期`](./05-connection-lifecycle.md) 的主题,这里只点出"它是优雅下线里最容易漏的一块"。

---

## H · 异步排空:没有"请求"的那些在途活儿

优雅下线不只是 HTTP 在途。这些**没有 HTTP 连接**的在途工作同样要排空,否则掉数据:

| 在途工作 | 优雅下线要做什么 | 不做的后果 |
|---|---|---|
| **MQ 消费者**(Kafka/RabbitMQ/Pulsar) | 停止拉新消息 → 处理完手头这批 → **提交位点 / ack** → 再退 | 没提交位点就退 → 重复消费;没处理完就退 → 看似消费了实则丢 |
| **后台 job / worker**(Celery 等) | 停止领新任务 → 当前任务做完或安全检查点 → 退;或把任务 requeue | 任务执行一半被杀 → 半成品 / 需要幂等补偿 |
| **长请求 / 流式响应**(大文件、SSE、导出) | 要么排空等它完成,要么提前 readiness-fail 让新的别来 + 给足 grace | 被 SIGKILL 截断 → 客户端拿到半截 |
| **定时任务**(in-process cron) | 收到信号后不再触发新一轮 | 关机瞬间又起一轮、跑一半被杀 |

机制和 HTTP 排空同构:**先"关进水口"(停拉/停领/停触发)→ 再"放干存量"(处理完手头)→ 最后退。** 关键是别把"关进水口"和"放干存量"搞反顺序。MQ 消费者尤其要记得**提交位点**这一步——它是消息语义不丢不重的命门。

> 这也是为什么 grace 预算(D)对消费者类服务要算得更宽:一批消息处理 + 位点提交可能比一个 HTTP 请求久。

---

## I · VM / 裸机 / 非 k8s:同一套不变式,换一套零件

你说的"實機"场景(没有 k8s,VM + 注册中心 + LB),不变式不变,只是链路 A/B 换了实现:

| k8s 这一层 | VM / 注册中心世界对应物 |
|---|---|
| 链路 A:Endpoints 摘除 | **服务注册中心主动摘除**:`shutdown hook` 调 Nacos/Eureka/Consul/Dubbo 接口,把本实例下线(Spring Cloud `@PreDestroy` / `ContextClosedEvent`) |
| readiness-fail 加速 | 注册中心心跳停 + 主动 deregister;LB 健康检查转 fail |
| preStop sleep | hook 里 **deregister 后 sleep 几秒**,等其它实例/网关刷新本地服务列表(Ribbon/客户端负载均衡有本地缓存,不是即时) |
| SIGKILL 兜底 | `systemd` `TimeoutStopSec` → 不退则 SIGKILL(见 [`linux-handson/08`](../../linux-handson/08-systemd-and-services/README.md)) |
| LB target draining | 硬件/软件 LB 的连接排空 + 健康检查摘除 |

**VM 世界最大的坑和 k8s 一模一样:客户端/网关的服务列表是本地缓存的(最终一致),deregister 后不 sleep 就关,一样有调用方还在打你。** 所以"deregister → sleep 等传播 → 再关"这个配方,k8s 用 preStop 实现,VM 用 shutdown hook 里的 sleep 实现,**本质同一招**。

> 历史细节(面试会问):Spring Cloud 早年默认**不**优雅下线(直接 deregister 就关,调用方靠重试兜),后来 `spring-boot-starter` 加了 `server.shutdown=graceful` + `spring.lifecycle.timeout-per-shutdown-phase`,Dubbo 有 `dubbo.service.shutdown.wait`。机制都是这套"先摘、等传播、再排空"。

---

## Part C · 踩坑框 ⚠️

> **app 优雅关写对了还掉请求** → 90% 是没配 `preStop`:SIGTERM 比摘流量先到,关 socket 制造了拒连黑洞。配 `preStop: sleep N` 等链路 A 传播完(B/C)。

> **只配了 readiness-fail、没配 preStop** → readiness 失败本身也要异步传播,SIGTERM 仍可能先到,竞态没消除。两个一起上(C3)。

> **`terminationGracePeriodSeconds` 没覆盖最长请求** → preStop sleep 吃掉一截 grace,剩下不够排空 → 在途被 SIGKILL 掐断。grace ≥ preStop + 最长请求 + 余量(D)。

> **app 排空超时 ≥ grace** → k8s 先 SIGKILL,优雅关白写。Shutdown 超时要 < grace(D)。

> **容器 CMD 用 shell form** → PID 1 是 `sh` 不转发 SIGTERM,进程根本收不到信号,等满 grace 被硬杀。用 exec form / `--init`(见 [`fastapi-ops/01` B′2](../../fastapi-ops/01-foundation/README.md))。

> **长连接没单独处理** → keep-alive/WS/gRPC 对"摘流量"免疫,客户端继续打老连接。要主动 `Connection: close` / GOAWAY(G,ch05)。

> **MQ 消费者直接退** → 没提交位点 = 重复消费;没处理完 = 丢消息。先停拉、处理完、提交位点、再退(H)。

> **云 LB deregistration delay 太短** → LB 还在排空 Pod 已被杀。delay ≥ preStop + 排空(F)。

> **VM 下 deregister 后立刻关** → 调用方本地服务列表还没刷新,继续打你。hook 里 deregister 后 sleep(I)。

---

## Part D · 面试速记卡(只做复习自检)

**人人会的(不加分)**

- 优雅下线是什么?→ 收 SIGTERM 后停止接新请求、排空在途、关资源再退,而不是被硬杀。
- 怎么触发?→ k8s 删 Pod / 滚动替换 / `docker stop` / systemd stop 发 SIGTERM,宽限期内不退才 SIGKILL。

**资深分水岭** ⭐

- app 优雅关写对了为什么还掉请求?→ "摘流量"(Endpoints/LB 异步传播)和"发 SIGTERM"(kubelet 本地立即)是两条不同步链路,SIGTERM 常先到,进程关 socket 时流量还在来 → 拒连。
- 怎么修?→ `preStop: sleep N` 把 SIGTERM 推迟到摘流量传播完之后再触发优雅关;readiness 提前转 fail 加速摘除。
- 单靠 readiness-fail 行不行?→ 不行,readiness 失败也要异步传播、SIGTERM 仍可能先到;preStop 兜底等待 + readiness 加速,两个一起才行。
- preStop 和 grace 分别治什么?→ preStop 治"关早了"(拒新连接);grace 时间治"关晚了被硬杀"(掐在途)。
- `terminationGracePeriodSeconds` 怎么定?→ ≥ preStop sleep + 最长在途请求 + 关池余量;app 排空超时要比它小。
- 云 LB 那条链路?→ deregistration delay / connection draining:停分发新连接、已建立的排空,delay 要 ≥ preStop+排空。
- 长连接怎么办?→ keep-alive/WS/gRPC 对摘流量免疫,要主动 `Connection: close`/GOAWAY 让对端重连(ch05)。
- MQ 消费者优雅下线?→ 停拉新消息 → 处理完手头 → 提交位点/ack → 退,顺序别反。

**架构师**

- 没有 k8s(VM+注册中心)怎么优雅下线?→ shutdown hook 主动 deregister(Nacos/Eureka/Consul/Dubbo)+ sleep 等调用方本地服务列表刷新 + systemd TimeoutStopSec 兜底,和 k8s preStop 同一招。
- preStop 和 PodDisruptionBudget 是一回事吗?→ 不是,两个层次:PDB 是 **fleet 级准入**(drain 时保证最小存活数),preStop 是**单 Pod 级排空**(这一个怎么不掉请求)。见 [ch04](./04-rollout-orchestration.md)。
- 怎么验证优雅下线真的不掉请求?→ 压测下滚动重启,统计 5xx/connection-reset 是否归零(见 [lab](./lab/))。

---

## Part E · 小结 + 桥接

**一句话记忆点**

> 分布式优雅下线掉请求,根因是**"摘流量"和"发 SIGTERM"两条链路不同步**(前者异步传播、后者本地立即,后者常先到)。
> 修复 = **preStop sleep**(推迟 SIGTERM 到摘流量传播完)+ **readiness-fail**(加速摘除)+ **足够的 grace**(覆盖 preStop + 最长在途排空)。
> 同一招换零件就是 VM 版:**deregister → sleep 等传播 → 排空 → 退**。

**桥接指针**

- 单进程内部排空机制(信号→标志→关 socket→lifespan) → [`fastapi-ops/01`](../../fastapi-ops/01-foundation/README.md) / [`golang/stdlib/01`](../../golang/stdlib/01-net-http/README.md)
- 谁定义"ready/leaving"(readiness 探针语义) → [`ch01 健康信号`](./01-health-signals.md)
- 把这套放大到整个 fleet 的滚动(maxSurge/PDB/时序) → [`ch04 滚动编排`](./04-rollout-orchestration.md)
- 长连接为什么对摘流量免疫、怎么优雅断 → [`ch05 连接生命周期`](./05-connection-lifecycle.md)
- systemd 信号 / TimeoutStopSec → [`linux-handson/08`](../../linux-handson/08-systemd-and-services/README.md)

➡️ 动手:[`lab/`](./lab/) — docker-compose 本机复现"丢请求 → 加优雅排空 → 不丢了"。
