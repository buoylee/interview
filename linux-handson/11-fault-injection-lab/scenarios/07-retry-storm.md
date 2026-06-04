# 场景 07 · 重试风暴 / 惊群:好心的重试把下游打死

> 🧪 `multipass shell linux-lab`。下游抖一下,客户端一起重试 → 流量翻几倍 → 把下游彻底打死 → 更多重试……自我强化的雪崩。
> 工具:`tc-netem`(造抖动)/ `ss -ti` / `nstat`(看重传)。理论接 [`06 网络`](../../06-networking/)。

---

## 一、这模拟大厂的什么真实事故
- **重试放大**:下游 RT 抖动或偶发失败 → 所有客户端**同时**重试 → 请求量 ×N → 下游过载 → 失败更多 → 重试更多(正反馈雪崩)。
- **缓存击穿/惊群**:一个热 key 同时过期,成千请求**同时**穿透到 DB。
- **惊群效应**:一个事件唤醒所有等待者,但只有一个能处理,其余白忙。

## 二、布置现场
```bash
# 1) 给本机网络注入 30% 丢包 + 抖动(模拟下游不稳)
sudo tc qdisc add dev lo root netem loss 30% delay 50ms 20ms

# 2) 对比"无脑重试" vs "退避+抖动"——看请求被放大多少
cat > /tmp/retry.py <<'EOF'
import socket, time, random, sys
def call():                       # 一次"请求":连本地 9 号端口(大概率失败/慢)
    s = socket.socket(); s.settimeout(0.3)
    try:
        s.connect(("127.0.0.1", 6379)); s.sendall(b"PING\r\n"); s.recv(16); return True
    except Exception: return False
    finally: s.close()
mode = sys.argv[1] if len(sys.argv) > 1 else "naive"
attempts = 0
for _ in range(50):               # 50 个逻辑请求
    for i in range(5):            # 最多重试 5 次
        attempts += 1
        if call(): break
        if mode == "backoff":
            time.sleep((0.05 * 2**i) + random.random()*0.05)   # 指数退避 + 抖动
print(f"{mode}: 50 个请求实际打出 {attempts} 次调用")
EOF
sudo apt-get install -y redis-server >/dev/null 2>&1; sudo systemctl start redis-server
python3 /tmp/retry.py naive
python3 /tmp/retry.py backoff
```
⚠️ 现象:
> `naive` 模式把 50 个请求放大成一两百次调用,而且**同时**砸下去;丢包越高放大越狠——这就是把下游打死的那股力。

## 三、你的任务(事故工作流)
1. **① 看放大**:同样 50 个请求,naive vs backoff 实际打出多少次?
2. **② 看底层**:网络在重传吗?怎么量?
3. **③ 根因**:为什么"加重试"反而让事情更糟?
4. **④ 解法**:止血和根治分别是什么?

<details>
<summary>四、揭晓 + 破案点</summary>

### ② 看 TCP 重传
```bash
nstat -az | grep -i retrans          # TcpRetransSegs 等,丢包导致内核层重传
ss -ti | grep -A1 6379               # 单连接的 retrans 计数、rtt
```

### ③ 根因
重试本身没错,错在**没退避、没抖动、没上限、没熔断**:
- 没退避 → 失败立刻重试,瞬间翻倍;
- 没抖动 → 所有客户端**对齐**在同一时刻重试(惊群);
- 没熔断 → 下游已经挂了还在猛打,永远恢复不了。
**正反馈**:过载→失败→重试→更过载。这是把抖动放大成雪崩的机制。

### ④ 解法
- **止血**:对下游**熔断**(快速失败,停止重试)、**限流**、甚至临时**降级**。
- **根治**:
  - 重试加**指数退避 + 随机抖动(jitter)**,设**重试上限**;
  - 缓存击穿:热 key **过期时间加随机**、用 **singleflight / 请求合并**(同一 key 只放一个请求穿透);
  - 区分**可重试**(超时、503)与**不可重试**(400、鉴权失败)错误,后者别重试。

### 🎯 破案点
- 「加重试提高成功率」是双刃剑:**没退避+抖动+上限+熔断的重试 = 放大器**。
- 抖动(jitter)是反惊群的关键——让重试时间**错开**。
- 雪崩的特征是**正反馈**:触发器(抖动)消失后,系统可能仍卡在坏状态([场景 10](./10-cascading-failure.md))。

</details>

<details>
<summary>五、面试怎么答</summary>

> 「重试风暴:下游抖动 → 客户端同时重试 → 流量翻倍把下游打死 → 更多重试,正反馈雪崩。`nstat`/`ss -ti` 能看到 TCP 重传飙升。根因是重试没退避、没抖动、没上限、没熔断。解法:重试一定要**指数退避 + 随机抖动 + 上限**,配**熔断 + 限流**;缓存击穿再加**热 key 过期抖动 + singleflight**。」

</details>

## 六、四语言桥接(正确的重试)
| 运行时 | 退避+熔断 |
|--------|----------|
| Java | resilience4j / Hystrix(熔断、限流、重试带 jitter) |
| Go | `backoff` 库 + `singleflight`、context 超时 |
| Python | `tenacity`(`wait_exponential_jitter`) |
| Node | `p-retry` + 熔断中间件 |

## 七、收尾 + 公开复盘
```bash
sudo tc qdisc del dev lo root        # 一定记得删掉 netem,否则本机网络一直丢包!
rm -f /tmp/retry.py
```
重试放大是「亚稳态失败(metastable failure)」的典型起因,见《Metastable Failures in Distributed Systems》(HotOS 2021)。往上一步就是[场景 10 级联失败](./10-cascading-failure.md)。

➡️ 回到 [道场总纲](../README.md)。
