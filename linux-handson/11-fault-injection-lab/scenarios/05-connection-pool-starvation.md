# 场景 05 · 连接池耗尽:慢依赖往上游传染的第一步

> 🧪 接 [`场景 04 慢依赖`](./04-slow-dependency.md)。同样是「下游慢 200ms」,这次看它怎么通过**有限的连接池**把"下游慢"放大成"上游全卡"——级联失败的起点。
> 工具:`ss` / 应用线程栈。

---

## 一、这模拟大厂的什么真实事故
- 下游(DB / 缓存 / RPC)变慢 + 你的连接池或线程池大小有限 → 慢调用把池占满 → 新请求排队等连接 → 上游线程、内存被拖垮 → 雪崩。
- 这是**最常见的级联失败模式**,也是 Hystrix / resilience4j 这类熔断库存在的理由。

## 二、布置现场(复用 04 的慢 Redis)
```bash
# 若 04 的环境还在,直接注毒;否则先按 04「布置现场」起 Redis + Toxiproxy
toxiproxy-cli toxic add -t latency -n slowdep -a latency=200 -a jitter=20 redis 2>/dev/null || true

cat > /tmp/pool_client.py <<'EOF'
# 模拟"固定大小连接池"打慢下游:5 条连接,50 个并发请求
import socket, threading, time, queue
POOL = 5
pool = queue.Queue()
for _ in range(POOL):
    pool.put(socket.create_connection(("127.0.0.1", 26379)))  # 经 Toxiproxy
def worker(i):
    t0 = time.time()
    s = pool.get()                      # 池满时阻塞在这里"等连接"
    waited = (time.time() - t0) * 1000
    s.sendall(b"PING\r\n"); s.recv(64)  # Redis 回 +PONG
    pool.put(s)
    print(f"req{i:02d}: 等池 {waited:5.0f}ms")
ts = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
[t.start() for t in ts]; [t.join() for t in ts]
EOF
python3 /tmp/pool_client.py
```
现象:
> 下游"只"慢 200ms,但后面的请求"等池"时间一路涨到一两秒——上游看到的延迟被**放大**了。50 个请求挤 5 条连接,排队成灾。

## 三、你的任务(事故工作流)
1. **① 止血**:怎么阻止"下游慢"继续往上游传染?(提示:不是无脑调大池)
2. **② 定位**:到下游的连接数是多少?为什么应用"看起来卡住"但连接数不高?
3. **③ 根因**:瓶颈到底在下游,还是在池?
4. **④ 验证**:去掉延迟后排队是否消失?

<details>
<summary>四、揭晓 + 破案点</summary>

### ② 定位
```bash
ss -tanp | grep 26379                 # 到下游的 ESTABLISHED 连接 ≈ 5(顶在池上限)
ss -tanp | grep 26379 | wc -l
```
连接数不高(就 5 条),但应用一堆线程**卡在"等连接"**——Java 看 `jstack` 会是一片 `WAITING` 在连接池的 `getConnection`;Go 是 goroutine 阻塞在 `Pool.Get`。**关键:卡的不是 CPU、不是带宽,是"拿不到连接"。**

更进一步,在 Linux 层直接看「每个线程在等什么」——会发现线程**分成两拨**(`wchan` 名随内核略有出入):
```bash
APP=$(pgrep -f pool_client.py | head -1)        # 脚本跑得快,放循环里连敲几次抓现场
ps -L -p "$APP" -o tid,stat,wchan:24 2>/dev/null | sort -k3
```
- **≈ 池大小那几个**:`wchan` 类似 `sk_wait_data` → 卡在**等下游 socket**(经典的 `read` 不返回)。
- **其余一大批**:`wchan` 类似 `futex_*` → 卡在**等"借一个连接"**。

> 破案关键:多数受害线程**根本没在做网络 IO**,而是在等一个「连接名额」——只盯 `read` 会漏掉它们。生产里这对应一个监控指标:连接池 `active`(顶格)+ `pending`(高),如 HikariCP 的 `hikaricp_connections_active / pending`。**先看这个指标,比翻日志快得多。**
> 这类「间歇 / 高负载才复现 / 日志刷太快」的故障到底怎么抓(指标 + 触发式抓取 + 实验室复现),专门一篇:[`../catching-intermittent-faults.md`](../catching-intermittent-faults.md)。

### ③ 根因
下游每次占用一条连接 200ms,池只有 5 条 → 池的吞吐上限 = 5 / 0.2s = **25 req/s**。请求速率一超过它,就排队、越积越久。**根因是"慢依赖 × 有限池",不是池本身太小。**

### ① 止血(关键反直觉)
- **不是无脑调大池**——调大只是把雪崩推迟,还可能压垮下游。
- 正确止血:给下游调用上**超时**(让占着连接的慢调用尽快释放)、**熔断**(快速失败而不是排队)、**降级**(返回缓存/默认值)。
- 超时是这里最重要的一招:没有超时,一条卡死的调用会**永久**占住一条连接。

### ④ 验证
```bash
toxiproxy-cli toxic remove -n slowdep redis
python3 /tmp/pool_client.py            # "等池"时间回落到 ~0
```

### 🎯 破案点
- "应用卡住"但**连接数不高 + CPU 闲** = 卡在等池,不是带宽/算力。
- 池吞吐 = 池大小 / 单次耗时;慢依赖直接砍掉池吞吐。
- 解药是**超时 + 熔断 + 降级**让慢调用快速释放,不是调大池。

</details>

<details>
<summary>五、面试怎么答</summary>

> 「连接池耗尽:`ss` 看到到下游的连接顶在池上限,应用线程全 BLOCKED 在拿连接,但 CPU 是闲的。根因是慢依赖把池占满(池吞吐 = 池大小 / 单次耗时)。解法不是无脑调大池——那只是拖延还可能压垮下游——而是给下游调用上**超时 + 熔断 + 降级**,让慢调用快速释放连接、快速失败,阻止它往上游传染。」

</details>

## 六、收尾 + 续作
```bash
rm -f /tmp/pool_client.py
# 清 Redis / Toxiproxy 环境见 04 的「收尾」
```
再往上一步,慢依赖 + 重试会把多个服务一起拖下水 → `场景 10 级联失败(亚稳态)`(🚧)。理论读物:《Metastable Failures in Distributed Systems》(HotOS 2021)。

➡️ 回到 [道场总纲](../README.md)。
