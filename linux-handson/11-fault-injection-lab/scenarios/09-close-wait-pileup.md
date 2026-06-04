# 场景 09 · CLOSE_WAIT 堆积:对端关了,你没关

> 🧪 `multipass shell linux-lab`。`CLOSE_WAIT` 堆积是**应用 bug**(没调 close),最终拖垮 fd。务必和 `TIME_WAIT`(正常现象)分清。原理接 [`06 网络`](../../06-networking/) 的 TCP 状态机。
> 工具:`ss -tan state ...` / `ss -tanp` / `lsof`。

---

## 一、这模拟大厂的什么真实事故
- 对端(client / 下游)主动关闭连接,你的程序**没调 `close()`** → 连接卡在 `CLOSE_WAIT`;
- 越积越多 → 占满 fd → [场景 03 fd 耗尽](./03-fd-exhaustion.md) → 不能 accept 新连接。
- 常见于:HTTP 响应体没读完/没关、连接池回收逻辑漏了、异常路径没 close。

## 二、布置现场
```bash
# server:接受连接但永不 close —— 制造 CLOSE_WAIT
cat > /tmp/badserver.py <<'EOF'
import socket
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", 9999)); s.listen(128)
held = []
print("bad server on :9999")
while True:
    c, _ = s.accept(); held.append(c)   # 收下连接,但故意永不 close()
EOF
python3 /tmp/badserver.py &
SRV=$!; sleep 1

# client:连上就立刻关(对端主动关闭)
python3 -c "
import socket
for i in range(30):
    socket.create_connection(('127.0.0.1', 9999)).close()
"
```
⚠️ 现象:
> server 端积压了一堆 `CLOSE_WAIT`,且永远不消失。

## 三、你的任务(事故工作流)
1. **① 量级**:有多少 `CLOSE_WAIT`?是哪个进程的?
2. **② 区分**:这和 `TIME_WAIT` 有什么本质区别?哪个是 bug?
3. **③ 根因 & 解法**:为什么会卡在 `CLOSE_WAIT`?怎么修?

<details>
<summary>四、揭晓 + 破案点</summary>

### ① 数 + 定位进程
```bash
ss -tan state close-wait | wc -l                      # CLOSE_WAIT 数量
ss -tanp state close-wait '( sport = :9999 )'         # 是哪个进程持有的
```

### ② CLOSE_WAIT vs TIME_WAIT(必考)
| 状态 | 出现在 | 含义 | 正常吗 |
|------|--------|------|--------|
| `CLOSE_WAIT` | **被动关闭方**(对端先关) | 收到 FIN,但**你还没调 `close()`** | ❌ 堆积 = 应用 bug |
| `TIME_WAIT` | **主动关闭方**(你先关) | 已关,等 2MSL 防旧包串扰 | ✅ 正常,短连接多就多 |

口诀:**CLOSE_WAIT 怪你的代码(没关),TIME_WAIT 是协议要求(主动关方等一会)。**

### ③ 根因 & 解法
- 根因:对端发了 FIN,你的应用没把这条连接 `close()`(漏了 close / 异常路径没关 / 没读完响应体)。
- 解法:**代码确保 close**(`with` / `defer Close()` / try-finally / 连接池正确回收);给读写设超时,避免连接被永久持有。
- `TIME_WAIT` 过多则是另一回事:多为短连接太多,用长连接 / 连接池缓解(别乱开 `tcp_tw_recycle`,有坑)。

### 🎯 破案点
- `ss -tan state close-wait` 一行数清,`-p` 直接给出**漏 close 的进程**。
- 把 `CLOSE_WAIT`(你的 bug)和 `TIME_WAIT`(正常)分开——面试最爱在这设坑。
- CLOSE_WAIT 堆积的下游后果是 **fd 耗尽**,两个场景连着考。

</details>

<details>
<summary>五、面试怎么答</summary>

> 「`CLOSE_WAIT` 堆积是 bug:对端已发 FIN,我方应用没调 `close()`。`ss -tanp state close-wait` 数量 + 定位进程,根因是代码漏了 close(异常路径、没读完响应体、连接池回收漏)。注意别和 `TIME_WAIT` 混——后者在**主动关闭方**、是 2MSL 正常等待,短连接多就多。CLOSE_WAIT 不治会演变成 fd 耗尽。」

</details>

## 六、收尾
```bash
kill $SRV 2>/dev/null; rm -f /tmp/badserver.py
```

## 七、公开复盘
连接泄漏 / CLOSE_WAIT 堆积导致服务「假死、不能接新请求」是经典线上事故。TCP 状态机原理见 [`06 网络`](../../06-networking/);下游后果见 [场景 03 fd 耗尽](./03-fd-exhaustion.md)。

➡️ 回到 [道场总纲](../README.md)。
