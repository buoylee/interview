# 场景 04 · 慢依赖:下游 Redis 变慢,把你的服务拖垮

> 🧪 `multipass shell linux-lab`。这是道场的**旗舰场景**:在一个**真 Redis** 上注入延迟,逼你分清「我自己忙」和「我在等别人」。
> 工具:`Toxiproxy`(注延迟)+ `strace` / `ss` / `lsof` / `redis-benchmark`(诊断)。心法接 [`07`](../../07-troubleshooting-playbook/)。

---

## 一、这模拟大厂的什么真实事故

「下游变慢拖垮上游」是线上最常见的故障形状之一,真实对应:

- 跨 AZ / 跨 region 调用,网络多了几十~几百 ms;
- 数据库 / 缓存慢查询,或下游服务 **GC stop-the-world** 长暂停;
- service mesh 的 **sidecar 配错 / 故障**,或 LB、防火墙在链路上加了延迟;
- 下游被限流后排队 → 你这边线程/连接全卡在等它 → **级联雪崩**。

关键反直觉:**你的服务慢,但你的 CPU 是闲的。** 新手一看慢就「加机器」,加了也没用——因为瓶颈不在你这。

---

## 二、布置现场(造一个真现场)

```bash
# 1) 起一个"下游真服务":本地 Redis(这个场景自带的 service under test)
sudo apt-get install -y redis-server redis-tools
sudo systemctl enable --now redis-server     # 监听 127.0.0.1:6379
redis-cli ping                                # 应回 PONG

# 2) 起 Toxiproxy:在"你的服务"和 Redis 之间架一个可注毒的代理
toxiproxy-server >/tmp/toxiproxy.log 2>&1 &   # API 在 :8474
sleep 1
toxiproxy-cli create -l 127.0.0.1:26379 -u 127.0.0.1:6379 redis
#   含义:客户端以后连 26379(代理),代理转发到 6379(真 Redis)

# 3) 先量正常基线(经过代理,但还没注毒)—— 记住这组数字!
redis-benchmark -h 127.0.0.1 -p 26379 -t get,set -n 20000 -q
#   p50/p99 应该都是亚毫秒级。没有基线就感觉不出异常。
```

现在**注入故障**(模拟下游变慢)。⚠️ 跑完这行就**别往下看「揭晓」**,先自己当事故来查:

```bash
# 给下行方向注入 200ms 延迟 + 50ms 抖动,命名 slowdep 方便回头移除
toxiproxy-cli toxic add -t latency -n slowdep -a latency=200 -a jitter=50 redis
```

**你看到的现象(假装这是监控告警):**
> 接口 p99 从 ~2ms 飙到 210ms+,吞吐塌方;但 `top` 看 CPU、内存都正常,机器不忙。用户在喊「系统好慢」。

---

## 三、你的任务:走完整事故工作流

别急着翻揭晓。按 [`07`](../../07-troubleshooting-playbook/) 的路径,自己走一遍:

1. **① 止血** —— 服务慢但没死,你会先做什么来止血?(提示:别急着加机器)
2. **② 定位** —— 套「第一分钟体检清单」:`uptime` / `top` 是 CPU 型?IO 型?都不是?那慢在哪?进程在**等**什么?
3. **③ 根因** —— 是 Redis 本身慢,还是「到 Redis 的链路」慢?怎么用一条命令**二分**证明?
4. **④ 验证** —— 你认为的根因,怎么通过「移除它 → 现象消失」来证实?

把你的结论和命令写进一份 [`postmortem`](../postmortem-template.md),再翻下面对答案。

---

<details>
<summary>四、揭晓 + 破案点(自己走完再点开)</summary>

### ① 止血(先别根因)
服务慢、没死。**先别加机器**(CPU 是闲的,加了没用)。止血手段是针对「慢依赖」的:给这个下游调用**加/调小超时**、加**熔断**、做**降级**(返回缓存/默认值)。但要先确认「是下游慢」才好对症——所以马上转定位。

### ② 定位(套 07 第一分钟清单)
```bash
uptime                         # load 不高
top -bn1 | head -8             # %us/%sy 低、id 高、wa 低,没有 D 进程
```
→ **不是 CPU 型,也不是 I/O 型。CPU 是闲的。** 这是最关键的一步:**慢 ≠ CPU 不够**。CPU 闲着还慢,说明在**等**。

那在等什么?看你的"服务"进程卡在哪个 syscall(这里用 `redis-cli` 当你的服务):
```bash
redis-cli -p 26379 get k >/dev/null &        # 模拟一次会卡的请求
APP=$!; sudo strace -p "$APP" -T -e trace=network 2>&1 | tail -5
#   会看到时间几乎全花在 recvfrom()/read() 一个 socket 上,单次 ~0.2s ← 在等下游响应,不是在算
```
这个 socket 连去哪?
```bash
ss -tanp | grep 26379          # 对端是 127.0.0.1:26379(代理 → Redis)
```
→ 锁定「下游 = 那条到 Redis 的链路」。

### ③ 根因(二分:是 Redis 慢,还是链路慢?)
直接压**下游本身**做二分——直连 vs 经代理:
```bash
redis-benchmark -p 6379  -t get -n 5000 -q     # 直连 Redis:快(亚毫秒)
redis-benchmark -p 26379 -t get -n 5000 -q     # 经代理:慢(~200ms)
```
→ **Redis 本体快,经代理就慢 → 慢在 app↔Redis 之间的网络/代理层,不是 Redis。**
链路上有什么?这里是 Toxiproxy;真实世界就是 sidecar / LB / 跨 AZ 网络 / 防火墙。**根因:代理/网络层引入了 ~200ms 延迟。**

### ④ 验证(移除 → 现象消失)
```bash
toxiproxy-cli toxic remove -n slowdep redis    # 拔掉"毒"
redis-benchmark -p 26379 -t get -n 5000 -q     # p99 回落到基线 → 根因证实
```

### 🎯 破案点
- CPU 闲 + 服务慢 = **在等**,不是在算。别被「慢就加机器」带跑。
- `strace`/`ss` 把「等」**定位到具体的 socket 和对端**。
- **直接压下游做二分**,一步分清「下游本体慢」还是「到下游的链路慢」——这是最值钱的一招。

</details>

<details>
<summary>五、这题面试怎么答(一句话)</summary>

> 「服务变慢我不会先加机器。先 `top` 确认 CPU 是不是真忙——慢依赖场景下 CPU 往往是闲的,闲就说明在**等**。再用 `strace`/`ss` 看进程卡在哪个 socket、对端是谁,然后**直接压那个下游做二分**:是它本身慢,还是到它的链路慢。确认是慢依赖,就先上**超时 + 熔断 + 降级**止血,再追根因(跨 AZ / sidecar / 下游 GC)。核心是分清『我忙』和『我在等别人』。」

</details>

---

## 六、收尾(清理现场)

```bash
toxiproxy-cli delete redis
kill %1 2>/dev/null            # 关 toxiproxy-server
# 如不再需要本地 Redis:sudo systemctl disable --now redis-server
```

## 七、对应的公开复盘(借来的经验)

这题的故障形状叫 **慢依赖 → 重试放大 → 级联 / 亚稳态失败(metastable failure)**。延伸阅读:

- 《Metastable Failures in Distributed Systems》(HotOS 2021)——讲的就是慢依赖 + 重试把系统推进雪崩。
- `danluu/post-mortems` 合集里的 timeout / cascading 类事故。
- 进阶续作:[`场景 05 连接池耗尽`](../README.md#六场景目录故障动物园)、`场景 10 级联失败`——慢依赖往上游传染的两步。

➡️ 回到 [道场总纲](../README.md)。
