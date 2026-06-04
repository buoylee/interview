# 场景 08 · No space left:磁盘写满 / inode 耗尽 / 删了不释放

> 🧪 `multipass shell linux-lab`。`No space left on device` 不只是「磁盘满了」——还可能是 **inode 耗尽**(空间没满也报错),或**删了文件但进程还持有**(空间不释放)。原理接 [`05 I/O 与文件`](../../05-io-and-files/)、[`02 文件系统`](../../02-filesystem-and-permissions/)。
> 工具:`df -h` / `df -i` / `du` / `lsof +L1`。

---

## 一、这模拟大厂的什么真实事故
- 日志没轮转,把分区写满;
- 临时文件 / 上传文件堆积;
- 海量小文件(缓存碎片、邮件、session)→ **inode 先于空间耗尽**;
- 删了大日志但进程还开着它 → `df` 显示满、`du` 却找不到 → 空间「凭空消失」。

## 二、布置现场(三个小实验)

**A:空间写满**
```bash
df -h /tmp
fallocate -l 1G /tmp/fill         # 占 1G(按你 VM 剩余空间调)
df -h /tmp                         # Use% 逼近 100%
```

**B:inode 耗尽(空间没满也报错)**
```bash
sudo mkdir -p /mnt/small
sudo mount -t tmpfs -o size=20m,nr_inodes=100 tmpfs /mnt/small   # 故意只给 100 个 inode
cd /mnt/small
for i in $(seq 1 200); do touch f$i 2>/dev/null; done            # 很快报 No space left
df -h /mnt/small                   # 空间几乎没用!
df -i /mnt/small                   # 但 IUse% = 100% ← 真凶
cd ~
```

**C:删了但被持有,空间不释放**
```bash
python3 -c "
import os,time
f=open('/tmp/ghost','wb'); f.write(b'x'*200_000_000)   # 写个 200MB
os.remove('/tmp/ghost')                                  # 删掉,但 f 还开着
time.sleep(300)" &
GH=$!
df -h /tmp                          # 空间还被占着
du -sh /tmp/ghost 2>/dev/null       # 找不到这文件了!
```

## 三、你的任务(事故工作流)
1. **A**:空间满,怎么快速找到「谁占的」?
2. **B**:`df -h` 说没满,为什么还 `No space left`?
3. **C**:`df` 满但 `du` 找不到那么多东西,空间去哪了?

<details>
<summary>四、揭晓 + 破案点</summary>

### A:找占空间的大目录
```bash
du -xh /tmp --max-depth=1 | sort -rh | head     # 按大小排,揪出大目录/大文件
```

### B:inode 耗尽
```bash
df -i /mnt/small        # IUse% 100% = inode 用光(海量小文件)。空间再多也开不了新文件。
```
→ **`No space left` 先 `df -h` 看空间、再 `df -i` 看 inode**。两者任一满都会报这个错。

### C:删了但被持有
```bash
sudo lsof +L1 | grep -i deleted     # NLINK=0 但仍被进程打开的文件 → 空间没释放
#   找到那个进程,重启/结束它(或让它 close fd),空间才回来
kill $GH; df -h /tmp                 # 进程退出 → 空间立刻释放
```

### 🎯 破案点
- `No space left` 有**两个**原因:空间满(`df -h`)或 inode 满(`df -i`)——别只看前者。
- `df`(内核记账)和 `du`(遍历文件)对不上 → 八成是**已删除但被持有**的文件,用 `lsof +L1`。
- 海量小文件先吃光 inode;清理或换文件系统布局。

</details>

<details>
<summary>五、面试怎么答</summary>

> 「`No space left on device`:先 `df -h` 看空间、`df -i` 看 inode——空间没满也可能 inode 满(海量小文件)。空间满就 `du -xh | sort -rh` 找大目录。如果 `df` 显示满但 `du` 找不到东西,是『删了但进程还开着』,`lsof +L1` 找到那个进程重启它,空间才释放。根治是日志轮转(logrotate)+ 清理策略。」

</details>

## 六、收尾
```bash
rm -f /tmp/fill
sudo umount /mnt/small 2>/dev/null; sudo rmdir /mnt/small 2>/dev/null
kill $GH 2>/dev/null
```

## 七、公开复盘
「磁盘写满导致服务雪崩」「删了日志空间不回来」是运维高频事故。配 `logrotate`、监控分区 Use% 和 IUse% 是标准预防。原理见 [`02 文件系统`](../../02-filesystem-and-permissions/)(inode)与 [`05 I/O`](../../05-io-and-files/)。

➡️ 回到 [道场总纲](../README.md)。
