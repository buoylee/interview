# 场景 10 · 级联失败(亚稳态):为什么"恢复"比"触发"难

> 🧪 `multipass shell linux-lab`。**capstone**:把[慢依赖(04)](./04-slow-dependency.md)、[连接池耗尽(05)](./05-connection-pool-starvation.md)、[重试风暴(07)](./07-retry-storm.md) 串起来,理解**亚稳态失败(metastable failure)**——触发器消失了,系统却还卡在坏状态。
> 工具:综合(`ss` / `top` / Toxiproxy / netem)。理论:《Metastable Failures in Distributed Systems》(HotOS 2021)。

---

## 一、这模拟大厂的什么真实事故
一次典型雪崩的链条:
```
下游抖一下(触发器)
   → 调用变慢(慢依赖,04)
   → 慢调用占满连接池/线程池(05)
   → 请求排队、超时
   → 客户端一起重试(重试风暴,07)
   → 流量翻倍,下游更慢
   → 回到第 2 步,正反馈 ↻
```
最可怕的是:**就算最初的抖动早就过去了,系统也回不来**——因为重试积压本身成了新的过载源。这就是「亚稳态」:系统稳定地卡在一个坏的平衡点。

## 二、亚稳态的三要素(看懂这个就懂了一半)
| 要素 | 在上面链条里是什么 |
|------|--------------------|
| **触发器(trigger)** | 一次性的扰动:下游抖动 / 发布 / 流量尖峰 |
| **放大器(amplification)** | 把扰动放大的机制:无退避重试、连接池排队、超时堆积 |
| **正反馈维持(sustaining loop)** | 让坏状态自我维持:积压的重试 → 持续过载 → 更多积压 |

> 触发器只点一次火;**真正烧不灭的是放大器 + 正反馈**。所以「把触发器去掉」往往不够,必须**打断正反馈**。

## 三、布置现场(观察"去掉触发器也回不来")
```bash
# 复用 04/05 的慢 Redis + Toxiproxy(若没起,先按 04 布置)
toxiproxy-cli toxic add -t latency -n slowdep -a latency=300 -a jitter=50 redis 2>/dev/null || true

# 用 07 的无脑重试客户端,并发猛打(放大器 + 正反馈)
for i in $(seq 1 5); do python3 /tmp/retry.py naive & done
sleep 5

# 现在"修好"下游——去掉触发器
toxiproxy-cli toxic remove -n slowdep redis

# 观察:积压的重试/连接是否让系统仍然卡一阵子才恢复
ss -tan state close-wait state established | grep -c 26379
```
⚠️ 现象:
> 去掉延迟后,系统**不会立刻**恢复——积压的连接和重试还要消化一阵。规模再大些(真实生产),它可能**永远回不来**,直到你主动止血。

## 四、怎么打断正反馈(恢复手段)
去掉触发器不够,必须打断「放大 + 维持」:

- **限流 / 减载(load shedding)**:主动丢掉一部分请求,把负载压到系统能消化的水平——这是亚稳态恢复的关键手段。
- **熔断**:对挂掉的下游快速失败,停止重试积压。
- **清积压**:必要时重启 / 清队列,把系统踢出坏平衡点。
- **退避 + 抖动 + 上限**:从源头不让重试放大(根治,见 [07](./07-retry-storm.md))。

> 设计层面:**容量要留余量**(别让正常态就接近临界),关键调用都要**超时 + 熔断 + 退避抖动**,并做**减载**预案。

<details>
<summary>五、面试怎么答</summary>

> 「级联/亚稳态失败:一个触发器(下游抖动/发布)经放大器(无退避重试、连接池排队)和正反馈(积压重试→持续过载)演变成雪崩。它的可怕在于**去掉触发器也回不来**,因为积压本身成了新过载源。恢复不能只靠『修好下游』,要**减载(load shedding)+ 熔断 + 清积压**打断正反馈;预防靠**留容量余量 + 超时/熔断/退避抖动**。」

</details>

## 六、收尾
```bash
pkill -f retry.py 2>/dev/null
toxiproxy-cli delete redis 2>/dev/null
# 其余清理见 04 的「收尾」
```

## 七、公开复盘
- 《Metastable Failures in Distributed Systems》(HotOS 2021)—— 这个场景的理论原文,强烈推荐。
- 很多大规模 outage 的复盘本质都是这条链(慢依赖 + 重试放大 + 容量无余量)。读 `danluu/post-mortems` 里 cascading / overload 类,对照本场景的三要素拆解。

这是动物园的收口:[04](./04-slow-dependency.md) → [05](./05-connection-pool-starvation.md) → [07](./07-retry-storm.md) → **10**,慢依赖如何一步步变成雪崩。

➡️ 回到 [道场总纲](../README.md)。
