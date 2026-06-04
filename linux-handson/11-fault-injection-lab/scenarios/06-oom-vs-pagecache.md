# 场景 06 · 内存涨了 ≠ 泄漏:page cache vs 真 OOM

> 🧪 `multipass shell linux-lab`。最常见的内存误判:看到 `used` 高就喊"内存泄漏要重启"。先分清**可回收的 page cache** 和**真的吃内存**。原理接 [`04 内存模型`](../../04-memory-model/)。
> 工具:`free` / `dmesg` / `ps --sort=-rss` / `/proc/<pid>/smaps`。

---

## 一、这模拟大厂的什么真实事故
- 把 **page cache**(读写文件留下的缓存,可随时回收)误判成内存泄漏,白白重启;
- 容器里 JVM 堆 `-Xmx` 配得比 cgroup `memory.max` 还大 → 被 cgroup **OOMKilled**(退出码 137);
- 进程真泄漏 / 配置过大 → 触发内核 **OOM killer**,按 `oom_score` 杀进程(常杀到"无辜"的大进程)。

## 二、布置现场

**A 部分:page cache 假象(used 高,但没事)**
```bash
free -h                                        # 记基线:盯住 available 这一列
dd if=/dev/zero of=/tmp/big bs=1M count=1024   # 造个 1G 文件
cat /tmp/big > /dev/null                        # 读它一遍 → page cache 涨
free -h                                         # buff/cache 涨、used 看着高,但 available 几乎没掉
```

**B 部分:真 OOM**
```bash
dmesg -T | tail -3                              # 基线
stress-ng --vm 1 --vm-bytes 95% --timeout 30s   # 真吃内存(前台跑,看它被杀)
dmesg -T | grep -i "killed process" | tail      # 内核 OOM killer 的记录
```

## 三、你的任务(事故工作流)
1. **判断**:A 部分里 `used` 涨了,这是泄漏吗?用哪一列判断?
2. **定位**:B 部分里谁被杀了?为什么是它?
3. **区分**:同样"内存涨",怎么分清 page cache / 真进程 RSS 涨 / OOM?

<details>
<summary>四、揭晓 + 破案点</summary>

### A:page cache 不是泄漏
`used` 涨是因为内核拿空闲内存做了文件缓存——**它可随时回收**。判断内存够不够看 **`available`**(真正还能给进程用的),不是 `used`。证明它可回收(需 root,谨慎):
```bash
sync && echo 1 | sudo tee /proc/sys/vm/drop_caches   # 主动丢缓存
free -h                                              # buff/cache 立刻掉,available 回来
```
→ 能被一键释放的,就不是泄漏。

### B:真 OOM,看 dmesg
```bash
dmesg -T | grep -i "out of memory"        # "Out of memory: Killed process <pid> (stress-ng)"
```
内核内存不够时按 `oom_score`(越大越先杀,跟 RSS 大小相关)挑进程杀。容器里更常见的是 **cgroup OOM**(进程超了 `memory.max`,退出码 137 / `OOMKilled`)。

### 三类"内存涨"怎么分
| 现象 | 怎么看 | 是不是问题 |
|------|--------|-----------|
| page cache 涨 | `free` 的 `available` 没掉、`buff/cache` 高 | 否,正常 |
| 进程 RSS 持续涨 | `ps aux --sort=-rss \| head`、`pidstat -r 1` | 是,可能泄漏/配置大 |
| 进程被杀 | `dmesg \| grep -i oom`、退出码 137 | 是,OOM killer / cgroup limit |

### 🎯 破案点
- **看 `available`,不是 `used`**;buff/cache 可回收。
- 真排查内存用 **RSS**(物理占用),不是 VSZ(地址空间,虚高)。
- 容器内存问题八成是 **cgroup limit 配小 / JVM 堆配大**,不是机器没内存。

</details>

<details>
<summary>五、面试怎么答</summary>

> 「内存涨先别喊泄漏:`free` 看 **available** 而不是 used——buff/cache 是可回收的 page cache。真涨就 `ps --sort=-rss` 看是哪个进程、RSS 是否持续增长;被杀就 `dmesg` 看 OOM killer 杀了谁、为什么(oom_score)。容器里最常见是 cgroup `memory.max` 配小或 JVM `-Xmx` 配大被 OOMKilled(退出码 137)。」

</details>

## 六、四语言桥接(内存上限怎么配)
| 运行时 | 关键 |
|--------|------|
| Java | `-Xmx` 要 < 容器 `memory.max`;另有堆外 / Metaspace / 线程栈 |
| Go | `GOMEMLIMIT` 给软上限,配合 cgroup |
| Python | 对象/缓存驻留;`fork` 子进程放大占用 |
| Node | `--max-old-space-size` |

## 七、收尾 + 公开复盘
```bash
rm -f /tmp/big
```
"page cache 当泄漏重启"、"容器 OOMKilled 找不到原因"都是高频事故。原理深挖见 [`04 内存模型`](../../04-memory-model/)(RSS vs VSZ、OOM killer、swap)。

➡️ 回到 [道场总纲](../README.md)。
