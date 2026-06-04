# 抓「难复现」的故障:间歇 / 高负载才触发 / 日志刷太快

> 道场的**专题方法篇**。心法接 [`07 · 排查方法论`](../07-troubleshooting-playbook/);跑的靶子是 [`场景 05 连接池耗尽`](./scenarios/05-connection-pool-starvation.md) 那个会「假死」的服务。
> 🧪 `multipass shell linux-lab`,部分命令需 `sudo`。

---

## 〇、你的困惑(这篇就是答案)

> 「经典用法:进程假死 → `strace -p` 看到停在 `read(8,...)` 一直不返回 → `lsof` 查出是某个网络连接 → 对端不回包,链路清晰了。
> **可异常往往不好发现:① 日志刷太快,定位不到;② 不稳定复现;③ 请求高的时候才容易复现。这类怎么解决?」**

先把那套经典流程的**前提**讲破:`strace -p` 抓现场,只在**进程「稳定卡死」**时有效——它现在就卡着,你慢慢上去看就行。但「间歇 / 高负载才触发」的特征是**你上去时它已经好了、或你还没上去它已经过去了**。所以解法不是「更努力地抓现场」,而是换四个动作:

```
从「现场抓」  →  ① 实验室复现(把随机变必现)
              →  ② 看聚合指标(别追逐条日志)
              →  ③ 触发式抓取(它出事自己留证据,录像而非盯梢)
              →  ④ 看「每个线程在等什么」(分清等下游 vs 等锁/连接)
```

下面用一个**会假死的真服务**当靶子,把这四招逐个跑一遍。

---

## 一、起一个会「假死」的靶子(可反复刷)

用 [`scenarios/pool-app.py`](./scenarios/pool-app.py):一个带「看得见的连接池」的最小服务,只用 Python 标准库,免 pip。

```bash
# 1) 下游真服务 + 可注毒代理(同场景 04/05;已起则跳过)
sudo systemctl enable --now redis-server && redis-cli set k hello
toxiproxy-server >/tmp/toxiproxy.log 2>&1 &
sleep 1; toxiproxy-cli create -l 127.0.0.1:26379 -u 127.0.0.1:6379 redis 2>/dev/null || true

# 2) 起服务:连接池故意设小(4),借不到连接最多等 3 秒
POOL_SIZE=4 POOL_WAIT=3 python3 scenarios/pool-app.py &

# 3) 给下游注入「慢性病」:慢 200ms(模拟跨 AZ / 略慢的查询)
toxiproxy-cli toxic add -t latency -n slowdep -a latency=200 redis

# 4) 基线:低负载下它岁月静好
curl -s -o /dev/null -w 'code=%{http_code} time=%{time_total}s\n' http://127.0.0.1:8080/
curl -s http://127.0.0.1:8080/stats
#   code=200 time≈0.2s;stats: inflight 低、waiting=0、pool_timeout=0
```

一个并发打流量的小函数(zero-install,后面反复用):

```bash
hammer() {                                   # hammer <并发数>
  for i in $(seq 1 "${1:-50}"); do
    curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 http://127.0.0.1:8080/ &
  done; wait
}
```

---

## 二、痛点 ①「不稳定、请求高才复现」→ 在实验室把它变「必现」

**为什么间歇、且和负载相关?** 因为资源(连接池/线程池)是**有限**的,被负载点着:

```
一个连接每次被占用 ≈ 下游耗时 = 0.2s,池里 4 个
→ 这个池子每秒最多放行 4 / 0.2 = 20 个请求(20 QPS)
低负载(<20 QPS):连接还得过来,岁月静好;高负载(>20):还不过来 → 排队 → 雪崩
```

亲手看它从「好」到「假死」:

```bash
hammer 5  | sort | uniq -c            # 低并发:基本全 200
hammer 80 | sort | uniq -c            # 高并发:大量 503(借不到连接,快速失败)
top -bn1 | head -8                    # 关键:CPU 全程是闲的 —— 假死不是因为算不过来
```

**这就是答案的第一半:** 线上那个「不定时、高峰才复现」的故障,只要你能说出它**和负载相关**,就能在道场里用「**注慢性病(Toxiproxy)+ 加压(并发)**」把它逼成**必现**,然后从从容容地查——比在生产守株待兔高效一万倍。

> 真要造更真实的压力:`wrk` / `ab` / `k6` / `locust`(认识层),或用 `goreplay` 回放线上真实流量。系统教程见 [`performance-tuning-roadmap/03x-load-gen-quickstart`](../../performance-tuning-roadmap/03x-load-gen-quickstart/) 和 [`07-load-testing`](../../performance-tuning-roadmap/07-load-testing/)。

---

## 三、痛点 ②「日志刷太快,定位不到」→ 看聚合指标,别追逐条日志

肉眼追 raw log 是最低效的。三条出路:

**A. 看「健康度指标」,不看逐条日志。** 服务自己暴露的池子指标,一行说清根因:

```bash
# 一边 hammer 80,一边盯指标
watch -n1 'curl -s http://127.0.0.1:8080/stats'
#   inflight=4(顶格)waiting=70+(一堆在排队)pool_timeout=持续上涨
```

`inflight` 顶到池大小、`waiting` 高、`pool_timeout` 在涨——**不用翻一行日志就定位到「连接池耗尽」**。生产里这对应:HikariCP 的 `hikaricp_connections_active / pending`、线程池的 `active / queue size`、接口的 p99 与错误率。**先用这种指标定位,再去翻那个时间窗的日志。**

**B. 只抓慢的 / 失败的。** 别全量看。日志按 `code>=500` 或 `耗时>阈值` 过滤,信噪比立刻起来(生产即 tail-based sampling:只详细记慢请求)。

**C. 时间点对齐法。** 把「503 尖刺的时间点」和「负载尖峰 / 池子打满的时间点」叠在一起,吻合就锁定因果。这招的范本是 [`01-methodology/01-scientific-method`](../../performance-tuning-roadmap/01-methodology/01-scientific-method.md) 里「接口偶尔慢 = Full GC」那个案例:把慢请求时间戳和 GC 停顿时间戳对齐,一吻合就破案。

---

## 四、痛点 ③「真随机、线上抓不到」→ 触发式抓取(录像,别盯梢)

实验室能复现的,上面两招够了。但若是**生产里真·随机、连实验室都复现不出**的:**装一个「扳机」,让它在出事那一刻自己录像。** 思路——盯一个指标,越线就自动抓快照:

```bash
APP=$(pgrep -f pool-app.py | head -1)
while true; do
  pt=$(curl -s http://127.0.0.1:8080/stats | grep -o 'pool_timeout=[0-9]*' | cut -d= -f2)
  if [ "${pt:-0}" -gt 0 ]; then                       # 一旦开始有人借不到连接
    ts=$(date +%H%M%S)
    ps -L -p "$APP" -o tid,stat,wchan:28 > /tmp/snap_threads_$ts.txt   # 线程都卡在哪
    ss -tnp | grep 26379          > /tmp/snap_sock_$ts.txt             # 下游连接快照
    curl -s http://127.0.0.1:8080/stats > /tmp/snap_stats_$ts.txt      # 指标快照
    echo "captured @ $ts (pool_timeout=$pt)"
  fi
  sleep 1
done
```

(开着这个,再去另一个终端 `hammer 80`,回来就能看到 `/tmp/snap_*` 录下了案发现场。)

**生产里同理**——监控 p99 / 错误率 / 池子 pending,越线就自动 dump 现场:

| 运行时 | 出事自动抓什么 |
|--------|---------------|
| Java | `jstack`(线程栈)/ `jmap` 堆 dump |
| Go | `curl /debug/pprof/goroutine?debug=2`(goroutine 栈) |
| Python | `py-spy dump --pid <pid>`(免侵入采样栈) |
| 通用 | `ss -tanp`、`cat /proc/<pid>/task/*/stack`、`top -H` 快照 |

> **这才是间歇性故障的正确抓法:录像,而不是盯梢。** 你不可能 7×24 盯着;但一个 5 行的扳机脚本可以。

---

## 五、通用一招:看「每个线程在等什么」(它在等下游,还是在等锁?)

不管什么间歇故障,一个最值钱的动作是**看进程的每个线程分别卡在哪**。Linux 层用 `wchan`(线程在内核里睡在哪个函数上):

```bash
APP=$(pgrep -f pool-app.py | head -1)
# 一边 hammer 80,一边:
ps -L -p "$APP" -o tid,stat,wchan:28 | sort -k3 | uniq -c -f2
```

这个靶子会看到线程**分成两拨**(`wchan` 名随内核略有出入):

- **≈ 池大小那几个**:`wchan` 类似 `sk_wait_data` → 卡在**等下游 socket**(就是你最初问的 `read(8,...)` 不返回)。
- **其余一大批**:`wchan` 类似 `futex_*` → 卡在**等一把锁 / 等借连接**。

**破案关键(也是新手最容易漏的):** 真正多数的受害线程**根本没在做网络 IO**,而是在等一个「连接名额」。只盯着 `read` / `strace` 网络调用,会以为「就几个连接慢,不严重」,其实背后排着一长队。跨语言对应:Java `jstack` 看一片 `WAITING` 在 `getConnection`、Go pprof 看一堆 goroutine 阻塞在 `Pool.Get`——**一眼分清「我在等别人」和「我自己把自己堵死了」。**

---

## 六、把这套套到别的场景上

「复现 → 指标 → 触发抓取 → 看线程在等什么」这套**不止用于连接池**。任何「间歇 / 负载相关」的故障都套同一招:

| 故障 | 复现(注毒+加压) | 看什么指标 | 录像抓什么 |
|------|----------------|-----------|-----------|
| 连接池耗尽 | Toxiproxy 慢 + `hammer` | 池 active/pending | 线程栈 + `ss` |
| CPU 毛刺 / GC | `stress-ng` / 大对象 | p99 + GC 停顿 | `top -H` + 线程栈 |
| IO 抖动 | `fio` / `--hdd` | `iostat await/%util` | `iostat` + `D` 进程栈 |
| CLOSE_WAIT 堆积 | 不关连接 + `hammer` | `ss` CLOSE-WAIT 计数 | `ss -tanp` + `lsof` |

对应的注毒方式见 [道场各场景](./README.md#六场景目录故障动物园)。

---

## 收尾

```bash
kill "$(pgrep -f pool-app.py)" 2>/dev/null
toxiproxy-cli toxic remove -n slowdep redis 2>/dev/null; toxiproxy-cli delete redis 2>/dev/null
```

**一句话记忆点:**
> 经典 `strace` 是「点」上的现场急诊,只对稳定卡死有效;间歇 / 高负载 / 日志太快的故障,要靠「面」上的方法——**在实验室把随机逼成必现、用聚合指标代替翻日志、用触发脚本录像而非盯梢、用 `wchan`/线程栈看清每个线程在等什么。**

➡️ 心法总纲 [`07`](../07-troubleshooting-playbook/);本篇靶子的完整推演见 [`场景 05 连接池耗尽`](./scenarios/05-connection-pool-starvation.md);科学方法与时间点对齐见 [`01-methodology`](../../performance-tuning-roadmap/01-methodology/01-scientific-method.md)。回到 [道场总纲](./README.md)。
