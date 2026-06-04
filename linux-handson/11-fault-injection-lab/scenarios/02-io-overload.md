# 场景 02 · I/O 过载:load 高但 CPU 闲,瓶颈在磁盘

> 🧪 `multipass shell linux-lab`。破除「load 高 = CPU 不够」的最大误解:load 高、CPU 却闲着,瓶颈在磁盘。原理接 [`05 I/O 与文件`](../../05-io-and-files/)。
> 工具:`uptime` / `top` / `vmstat` / `iostat -xz` / `pidstat -d`。

---

## 一、这模拟大厂的什么真实事故
- 慢盘 / 云盘被限流(IOPS 打满);
- 日志狂写、未加索引的全表扫、大批量导入;
- 备份 / 压缩任务和在线业务**抢 I/O**;
- NFS / 网络盘卡住,进程一片 `D` 状态。

## 二、布置现场
```bash
# 用 fio 造精确的随机写压力(比 stress-ng --hdd 更可控)
fio --name=load --rw=randwrite --bs=4k --size=256M --numjobs=2 \
    --iodepth=16 --time_based --runtime=60 --direct=1 --filename=/tmp/fiotest &
```
⚠️ 跑完别看揭晓。现象:
> `load` 和[场景 01](./01-cpu-saturation.md) 一样高,但这次 CPU 是闲的,系统却很卡。

## 三、你的任务(事故工作流)
1. **① 定位资源**:同样 load 高,这次是 CPU 型还是 I/O 型?怎么一眼区分?
2. **② 确认饱和**:磁盘真的忙到排队了吗?看哪几个指标?
3. **③ 锁进程**:谁在狂读写?
4. **④ 验证**:停掉负载后指标怎样?

<details>
<summary>四、揭晓 + 破案点</summary>

### ① I/O 型的标志
```bash
uptime                         # load 高
top -bn1 | head -8             # 但 %us 低、id 不低?看 %wa 高!且有 D 状态进程
```
**`%wa` 高 + `D`(不可中断睡眠,通常等 I/O)进程 = I/O 型**。CPU 其实闲着——这就是「不能只看 load 就喊加机器」的原因。

### ② 确认磁盘饱和
```bash
vmstat 1 3                     # b 列(阻塞/等 IO 的进程)>0、wa 高
iostat -xz 1 3                 # 看这几栏:
#   %util   设备繁忙百分比,接近 100% = 饱和
#   await   每次 I/O 平均耗时(ms),飙高 = 慢
#   aqu-sz  平均排队深度,>1 = 在排队
```

### ③ 锁进程
```bash
pidstat -d 1 3                 # 哪个进程 kB_rd/s、kB_wr/s 最高 → fio
# iotop 也行(更直观):sudo iotop -o
```

### ④ 验证
```bash
pkill fio                      # 停负载
iostat -xz 1 3                 # %util/await 回落
```

### 🎯 破案点
- **load 高先分 CPU 型 vs I/O 型**:看 `%wa` 和有没有 `D` 进程,这是和[场景 01](./01-cpu-saturation.md) 的分水岭。
- `iostat` 三件套:`%util`(忙不忙)+ `await`(快不快)+ `aqu-sz`(排不排队)。
- `D` 状态进程是 I/O 型的强信号(`ps -eo pid,stat,wchan,comm | grep ' D'` 看它卡在哪个内核函数)。

</details>

<details>
<summary>五、面试怎么答</summary>

> 「load 高不一定是 CPU。`top` 看 `%wa` 高、有 `D` 状态进程,就是 I/O 型——CPU 反而闲。`iostat -xz` 看 `%util`(饱和)、`await`(慢)、`aqu-sz`(排队)确认磁盘瓶颈,`pidstat -d` 锁定狂读写的进程。所以不能只看 load 就加机器,得先分清 CPU 型还是 I/O 型。」

</details>

## 六、四语言桥接(谁在发 I/O)
| 运行时 | 找 I/O 热点 |
|--------|------------|
| Java | async-profiler 的 wall-clock 模式 / 看阻塞在 socket、文件读写的线程 |
| Go | `pprof` block/mutex profile、trace |
| Python | `py-spy` 看卡在 read/write、慢查询 |
| 通用 | `strace -p <pid> -e trace=read,write -T` 看每次 I/O 耗时 |

## 七、收尾 + 公开复盘
```bash
pkill fio 2>/dev/null; rm -f /tmp/fiotest
```
「日志同步刷盘拖垮服务」「备份任务抢 IO 导致在线超时」是高频事故。原理深挖见 [`05 I/O 与文件`](../../05-io-and-files/)(缓冲/直接 I/O、fsync、iostat 指标)。

➡️ 回到 [道场总纲](../README.md)。
