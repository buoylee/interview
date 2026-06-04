# 场景 03 · fd 耗尽:Too many open files

> 🧪 `multipass shell linux-lab`。app-dev 最常踩的坑之一:进程打开 fd 不关,撞上限后**再也开不了文件 / 收不了新连接**。
> 工具:`lsof` / `/proc/<pid>/fd` / `ulimit` / `/proc/<pid>/limits`。原理接 [`05 I/O 与文件`](../../05-io-and-files/)。

---

## 一、这模拟大厂的什么真实事故
- HTTP client 每次新建连接不复用(没连接池)→ socket fd 越积越多;
- DB / Redis 连接用完不归还(忘了 close / 连接池配置错);
- 打开文件、日志句柄不关;维护大量长连接但忘了清理死连接。
- 现象通常**突然**:服务跑了几小时后开始大量报错、不能 accept 新请求。

## 二、布置现场
```bash
ulimit -n                       # 当前 shell/进程的 fd 软上限,通常 1024

cat > /tmp/leak.py <<'EOF'
# 一直开文件却不关,模拟 fd 泄漏
import time
held = []
while True:
    held.append(open("/etc/hostname"))
    time.sleep(0.002)
EOF
python3 /tmp/leak.py &           # 跑起来,很快撞上限
LEAK=$!
```
⚠️ 跑完别看揭晓。现象:
> 进程很快抛 `OSError: [Errno 24] Too many open files`,之后任何「开文件 / 建连接」都失败。

## 三、你的任务(事故工作流)
1. **① 止血**:怎么让服务先恢复?(提示:上限是哪来的?)
2. **② 定位**:这个进程开了多少 fd?上限是多少?
3. **③ 根因**:开的 fd 大多是**哪一类**(文件?socket?pipe?)→ 指向泄漏点。
4. **④ 验证**:修复后 fd 数应该怎样?

<details>
<summary>四、揭晓 + 破案点</summary>

### ② 定位
```bash
ls /proc/$LEAK/fd | wc -l                    # 这个进程开了多少 fd(最快)
lsof -p $LEAK | wc -l                         # 同样,信息更全
cat /proc/$LEAK/limits | grep "open files"    # 该进程的软/硬上限(比 ulimit 准)
cat /proc/sys/fs/file-nr                      # 全系统:已分配 fd / 上限
```

### ③ 根因(按 fd 类型分组找泄漏源)
```bash
lsof -p $LEAK | awk '{print $5}' | sort | uniq -c | sort -rn | head
#   TYPE 列:REG=普通文件 / IPv4=socket / FIFO=pipe …… 哪类暴涨就是哪类在泄漏
```
这里是一堆 `REG` 指向 `/etc/hostname` → 文件句柄没关。真实里最常见的是一堆 `IPv4`(socket)→ 连接没复用/没归还。

### ① 止血
- 临时调高上限:`ulimit -n 65535`(当前 shell);服务用 systemd 的 `LimitNOFILE=65535`,重启服务先恢复。
- 但调高只是续命,**根因是代码确保关闭**。

### ④ 验证
修复(确保 close)后,`ls /proc/<pid>/fd | wc -l` 应**稳定不涨**。

### 🎯 破案点
- `/proc/<pid>/limits` 比 `ulimit` 准(看的是目标进程,不是你的 shell)。
- **按 fd 类型分组**(`lsof` 的 TYPE 列)直接告诉你泄漏的是文件还是连接。
- 调 `ulimit` 是止血不是根治;真凶是没 close。

</details>

<details>
<summary>五、面试怎么答</summary>

> 「`Too many open files`:先 `ls /proc/pid/fd | wc -l` 数 fd、`cat /proc/pid/limits` 看上限,再用 `lsof -p` 按 TYPE 分组找泄漏类型(常是没归还的 socket/连接)。止血调 `ulimit` / systemd `LimitNOFILE`,根因是代码保证关闭——用语言的资源管理惯用法,别靠手动 close。」

</details>

## 六、四语言桥接(fd 怎么保证关)
| 运行时 | 惯用法 |
|--------|--------|
| Java | try-with-resources(`try (var in = ...)`),HttpClient 复用连接池 |
| Go | `defer f.Close()`、`defer resp.Body.Close()`(忘了它是经典 leak) |
| Python | `with open(...) as f:`、用 `requests.Session` / 连接池 |
| Node | 及时 `stream.close()`、复用 `http.Agent`、连接池 |

## 七、收尾 + 公开复盘
```bash
kill $LEAK; rm -f /tmp/leak.py
```
fd / 连接泄漏是经典生产事故,`danluu/post-mortems` 里多见。原理深挖见 [`05 I/O 与文件`](../../05-io-and-files/) 的「fd 耗尽」一节。

➡️ 回到 [道场总纲](../README.md)。
