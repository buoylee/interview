# 场景 01 · CPU 饱和:谁在烧 CPU,烧的是哪段代码

> 🧪 `multipass shell linux-lab`。最基础也最常考:CPU 打满了,从「机器」一路定位到「哪一行代码」。原理接 [`03 进程模型`](../../03-process-model/)。
> 工具:`uptime` / `top` / `mpstat` / `pidstat` / `top -H` →(语言层)`jstack` / `py-spy` / `pprof`。

---

## 一、这模拟大厂的什么真实事故
- 死循环 / `while(true)` 没退出;
- 正则**灾难性回溯**(一个烂正则把一核打满——Cloudflare 2019-07-02 全球故障就是这么来的);
- 频繁 **Full GC**(CPU 高其实是 GC 的结果,不是业务);
- 算法退化(O(n²)、未走索引的全表扫、热点序列化)。

## 二、布置现场
```bash
stress-ng --cpu 2 --timeout 60s &     # 2 个 worker 死算,模拟 CPU 密集
```
⚠️ 跑完别看揭晓。现象:
> `load` 飙升,接口 RT 变长;但内存、磁盘、网络都正常。

## 三、你的任务(事故工作流)
1. **① 定位资源**:`load` 高,是 CPU 型还是 I/O 型?(接 [07](../../07-troubleshooting-playbook/) §2.4)
2. **② 锁进程**:哪个进程在吃 CPU?
3. **③ 锁线程 → 代码**:具体是哪个**线程**?对应哪段代码?
4. **④ 看分布**:是单核打满(单线程瓶颈)还是多核都满?

<details>
<summary>四、揭晓 + 破案点</summary>

### ① 是不是 CPU 型
```bash
uptime                         # load 高
top -bn1 | head -8             # %us(用户态)高、id 低、wa 低 → CPU 型(不是等 IO)
```
`%us` 高 = 真在算;若是 `%sy` 高 = 系统调用/上下文切换多;若 `%wa` 高 = 其实在等 IO(那是[场景 02](./02-io-overload.md))。

### ② 锁进程
```bash
pidstat -u 1 3                 # 哪个进程 %CPU 最高 → stress-ng
```

### ③ 锁线程 → 代码
```bash
top -H -bn1 -p $(pgrep -d, stress-ng) | head    # -H 看线程,拿到吃 CPU 的 TID
```
对真实 **Java** 服务,这一步接语言层:
```bash
printf '%x\n' <TID>            # 线程 TID 转十六进制
jstack <pid> | grep -A20 nid=0x<上面的十六进制>   # 在线程 dump 里按 nid 找到栈 → 哪段代码在烧
```

### ④ 单核还是多核
```bash
mpstat -P ALL 1 3              # 只有一个核 100%、其它闲 → 单线程瓶颈(加核没用,要并行化)
```

### 🎯 破案点
- 先用 `%us / %sy / %wa` 分清「真算 / 系统态 / 其实在等 IO」,别一上来抓火焰图。
- **`top -H` 拿线程 TID → 十六进制 → jstack 的 `nid`** 是 Java 定位代码的标准接力。
- 单核打满 ≠ 加机器能解,看 `mpstat -P ALL`。

</details>

<details>
<summary>五、面试怎么答</summary>

> 「CPU 100%:`uptime`/`top` 先确认是 CPU 型(`%us` 高、`%wa` 低)→ `pidstat` 锁进程 → `top -H` 锁线程 TID → Java 把 TID 转十六进制按 `nid` 在 `jstack` 里找栈,定位到代码。`mpstat -P ALL` 看是单核打满(单线程瓶颈)还是多核都满。常见根因:死循环、烂正则回溯、频繁 Full GC。」

</details>

## 六、四语言桥接(从线程到代码)
| 运行时 | 找热点 | 与 OS 层衔接 |
|--------|--------|--------------|
| Java | `jstack` / async-profiler | `top -H` 的 TID → 十六进制 = `nid` |
| Go | `pprof`(CPU profile) | OS 看进程,pprof 看 goroutine/函数 |
| Python | `py-spy dump --pid` / `py-spy top` | 免侵入采样,直接看卡在哪 |
| Node | `--prof` / `clinic` / `0x` | 火焰图定位事件循环阻塞 |

## 七、收尾 + 公开复盘
```bash
pkill stress-ng 2>/dev/null
```
**Cloudflare 2019-07-02** 全球宕机:一条新部署的 WAF 正则触发灾难性回溯,把所有核打满——「一个正则拖垮全网」的经典案例,值得读它的公开复盘。原理深挖见 [`03 进程模型`](../../03-process-model/)。

➡️ 回到 [道场总纲](../README.md)。
