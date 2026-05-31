# 05 · I/O 与文件 ⭐核心

> 🧪 **环境**:VM shell(`multipass shell linux-lab`),部分实验需 `sudo`
> 进程要的第三种资源:I/O。本章接上 `04` 的 page cache(脏页刷盘在这里展开),并讲透两个高频线上事故:**「Too many open files」** 和 **「删了大文件磁盘空间没释放」**。

---

## 一、开篇盲点

- `write()` 返回成功,数据就落盘了?**没有**——它通常只到了 page cache,断电就丢。
- 报错 **`Too many open files`**,到底是「文件」还是「连接」开太多?(其实 socket 也是 fd)
- 一个大日志文件 `rm` 了,`df` 显示磁盘空间却没释放,为什么?
- `iostat` 的 `%util` 到 100% 就一定是磁盘到瓶颈了吗?(对 SSD/NVMe 不一定)

根子都在:不理解 **fd 的本质、缓冲 I/O 与刷盘、文件删除的真相、磁盘指标怎么读**。

---

## 二、正文 · 原理

### 2.1 打开一个文件,内核维护三张表

回顾 `01`:进程用 fd(小整数)操作一切。fd 背后是三层结构:

```
进程 A 的 fd 表          系统级打开文件表(file table)        inode 表(磁盘上的文件实体)
┌────────────┐         ┌─────────────────────────┐         ┌──────────────────┐
│ 0 → ───────┼────────►│ 偏移=120, 标志=O_RDONLY ─┼────────►│ inode(权限/大小/  │
│ 1 → ───────┼───┐     ├─────────────────────────┤    ┌───►│ 数据块指针...)     │
│ 3 → ───────┼─┐ └────►│ 偏移=0, 标志=O_WRONLY   ─┼────┘    └──────────────────┘
└────────────┘ │       └─────────────────────────┘
进程 B 的 fd 表 │       (每次 open 一个表项,记录读写位置 offset)
┌────────────┐ │
│ 3 → ───────┼─┘   ← B 的 fd3 和 A 的 fd3 可指向同一个打开项(fork/dup 共享 offset)
└────────────┘
```

- **fd 表**:每个进程私有,fd 号是它的索引。
- **打开文件表**:每次 `open` 产生一个表项,**记录读写偏移 offset 和打开标志**。`fork`/`dup` 会共享同一表项(所以父子进程写同一 fd 会接着对方的位置写)。
- **inode**:文件在磁盘上的真身(元数据 + 数据块指针)。多个打开项可指向同一 inode。

### 2.2 fd 是一种有限资源(高频事故源)

每个进程能打开的 fd 有上限:`RLIMIT_NOFILE`(`ulimit -n`)。系统全局还有 `fs.file-max`。

> **关键认知**:**socket 也是 fd,管道也是 fd**。所以「连接数」和「打开文件数」共用这个配额。

fd 耗尽 → 任何 `open`/`accept`/`socket` 都返回 `EMFILE`,表现为:
- `Too many open files`
- 服务无法接受新连接(`accept` 失败)、打不开新文件、建不了新连接。

**最常见根因**:连接/文件**没 close**(连接池泄漏、忘记 `close()`、`defer` 漏写)。fd 数只增不减就是泄漏信号。

### 2.3 缓冲 I/O vs 直接 I/O vs fsync(接 04 page cache)

```
write(fd, ...) ──► page cache 的"脏页" ──(内核异步,或 fsync 主动)──► 磁盘
       ↑ 立刻返回"成功"             ↑ 真正落盘在这一步才发生
```

- **缓冲 I/O(默认)**:`write` 把数据写进 page cache 的脏页就返回——**快,但没落盘**,断电/宕机会丢这段「在 cache 里还没刷的」数据。
- **`fsync(fd)` / `fdatasync`**:强制把该文件的脏页刷到磁盘,返回才保证持久化。代价大(等磁盘)。
- **直接 I/O(`O_DIRECT`)**:绕过 page cache 直接读写设备。数据库常用——因为它自己管缓存(buffer pool),不想被 OS cache 再缓存一层(双缓冲)。

### 2.4 脏页回写:数据什么时候真落盘

不主动 `fsync` 时,脏页由内核后台回写线程刷盘,触发条件大致是:
- 脏页占比超过 `vm.dirty_ratio` / `vm.dirty_background_ratio`;
- 脏页超过 `vm.dirty_expire_centisecs` 的时限。

这中间就是**掉电丢数据的窗口**。所以「要不要 `fsync`」是性能与持久化的经典权衡(见 §5 数据库)。

### 2.5 文件删除的真相:`rm` 删的不是数据

`rm` 实际调用 `unlink`,它做的是:**把目录项删掉,inode 的硬链接计数减 1**。文件数据真正被释放,需要同时满足:

> **硬链接计数 == 0,且没有任何进程还打开着它(没有 fd 引用)。**

这就解释了「**删了大日志,`df` 空间却没降**」:某进程(如 nginx、你的 app)还开着这个被删的文件的 fd,链接数虽然变 0,但 fd 还在引用,内核就不释放数据块。直到该进程关闭 fd 或退出,空间才回来。用 `lsof +L1` 能揪出这种「已删除但仍被持有」的文件。

### 2.6 磁盘 I/O 指标:`iostat -x` 怎么读

```console
$ iostat -x 1
Device  r/s   w/s  rkB/s  wkB/s  r_await w_await aqu-sz  %util
vda    12.0 340.0  480.0 28000.0    0.50   18.30   6.20   98.7
```

| 字段 | 含义 | 怎么判断 |
|------|------|----------|
| `r/s` `w/s` | 每秒读/写次数(IOPS) | 业务量 |
| `rkB/s` `wkB/s` | 每秒读/写吞吐 | 带宽 |
| `r_await` `w_await` | 单次 I/O 平均耗时(ms,含排队) | **飙升 = 慢**,最该看 |
| `aqu-sz` | 平均队列深度 | 持续 >1 说明在排队 |
| `%util` | 设备繁忙时间占比 | 见下方陷阱 |

> **`%util` 陷阱**:对单队列机械盘,接近 100% ≈ 饱和;但对 **SSD/NVMe 等能并行处理多个请求的设备,`%util` 100% 不代表饱和**(它还能同时处理更多)。判断 SSD 是否瓶颈要看 **`await` 是否变大、`aqu-sz` 是否堆积**,而不是只看 util。

### 2.7 两种「磁盘满」

- **空间满**:`df -h` 看,Use% 100% / Avail 0。
- **inode 满**:`df -i` 看,IUse% 100%。海量小文件会先耗尽 inode——这时 `df -h` 还有空间,却报「No space left on device」,很迷惑。

---

## 三、怎么看(命令 + 真实输出怎么读)

### fd 上限与某进程开了多少 fd

```console
$ ulimit -n                      # 当前 shell 的软限制(进程能继承)
1024
$ cat /proc/<pid>/limits | grep 'open files'
Max open files    1024    1048576   files       # 软限 / 硬限
$ ls /proc/<pid>/fd | wc -l      # 该进程实际打开了多少 fd
873                              # 接近 1024 就快爆了
```

### 谁打开了什么 / 揪「已删除仍占用」:`lsof`

```console
$ lsof -p <pid>                  # 某进程打开的所有文件(含 socket)
$ lsof /var/log/app.log          # 谁开着这个文件
$ lsof +L1                       # 链接数<1(已删除但被持有)的文件 —— 释放不掉空间的元凶
COMMAND  PID  USER  FD ... NLINK  NAME
nginx   1234  root  5w  ...    0  /var/log/app.log (deleted)
```

### 空间 vs inode:`df`

```console
$ df -h /var      # 看空间
$ df -i /var      # 看 inode(海量小文件场景必看)
```

### 每进程 I/O:`pidstat -d`

```console
$ pidstat -d 1
   PID   kB_rd/s   kB_wr/s  Command
  4242      0.00  28000.00  java        # 揪出在狂写盘的进程
```

---

## 四、动手实验(沙箱)

> 🧪 全部在 `multipass shell linux-lab` 里跑。

**实验 1:看 fd 上限与进程 fd 数**
```bash
ulimit -n
ls /proc/$$/fd          # 当前 shell 开的 fd
cat /proc/$$/limits | grep 'open files'
```

**实验 2:亲手触发 `Too many open files`**
```bash
bash -c '
  ulimit -Sn 64                      # 临时把软限制调小(仅此子进程)
  for i in $(seq 10 300); do
    eval "exec $i<>/tmp/openfile" 2>/dev/null \
      || { echo "开到 fd=$i 时失败:Too many open files"; break; }
  done
'
rm -f /tmp/openfile
```

**实验 3:删了文件但空间不释放(经典事故复现)**
```bash
dd if=/dev/zero of=/tmp/held.log bs=1M count=500   # 造 500M 文件
tail -f /tmp/held.log >/dev/null & HOLDER=$!        # 一个进程持有它
df -h /tmp | tail -1                                # 记下已用空间
rm /tmp/held.log                                    # 删除
echo "== rm 后 =="; df -h /tmp | tail -1            # 空间没降!
lsof +L1 2>/dev/null | grep held                    # 看到 (deleted) 仍被持有
kill $HOLDER; sleep 1                                # 释放持有者
echo "== 释放后 =="; df -h /tmp | tail -1           # 空间回来了
```
> 生产里正确处理:用 `: > /var/log/app.log` 或 `truncate -s 0` 清空(不删 inode),或配 logrotate(见 `08`)。

**实验 4:`fsync` 的代价**
```bash
echo "== 缓冲写(不强制落盘)=="; dd if=/dev/zero of=/tmp/t1 bs=4k count=20000
echo "== 每次写都落盘(oflag=dsync)=="; dd if=/dev/zero of=/tmp/t2 bs=4k count=20000 oflag=dsync
rm -f /tmp/t1 /tmp/t2
```
对比两次 dd 报告的速度——`dsync`(相当于每次 fsync)慢一个数量级,这就是数据库保证持久化的代价。

**实验 5:`iostat` 看 I/O 指标飙升**
```bash
stress-ng --hdd 2 --timeout 20s &
iostat -x 1 6           # 观察 w/s、w_await、aqu-sz、%util 飙升
wait
```

---

## 五、生产踩坑框 ⚠️

> **`Too many open files` 排查三步**:① `ulimit -n` / `/proc/<pid>/limits` 看限制;② `ls /proc/<pid>/fd | wc -l` 看实际开了多少、`lsof -p <pid>` 看开的是啥(常是没关的 socket → 连接池泄漏);③ 治标调大限制(systemd 服务用 `LimitNOFILE=`,见 `08`),治本修代码漏 `close`。

> **删日志不降空间**:`rm` 大日志后 `df` 不变,因为进程还开着 fd。别 `rm`,用 `truncate -s 0 file` 或 `: > file` 原地清空;滚动日志用 logrotate 的 `copytruncate`。`lsof +L1` 是定位神器。

> **数据库为什么写入「慢」**:持久化要 `fsync`,机械盘受限于每秒 fsync 次数(几百次);用 SSD、或带电池/超级电容的 RAID 卡(掉电保护下可安全合并写)能大幅提升。`O_DIRECT` + 自管缓存避免双缓冲。

> **「No space left」但 `df -h` 还有空间**:多半是 **inode 耗尽**(海量小文件),`df -i` 一看便知。

---

## 六、本章面试速记

- **文件描述符是什么?fd 耗尽什么表现、怎么查?** fd 是进程操作文件/socket/管道的句柄;耗尽报 `Too many open files`、无法新建连接/打开文件;查 `ulimit -n` + `ls /proc/<pid>/fd | wc -l` + `lsof`。
- **`write()` 返回成功数据就安全了吗?** 不,默认只进 page cache 的脏页,断电会丢;要 `fsync`/`fdatasync` 才保证落盘。
- **`rm` 删了大文件,磁盘空间没释放为什么?怎么办?** 还有进程持有它的 fd,链接数 0 但未释放;`lsof +L1` 找,关闭持有进程或用 `truncate`/`: >` 清空。
- **`iostat %util` 100% 一定是瓶颈吗?** 对单队列 HDD 接近饱和;对 SSD/NVMe 不一定,要看 `await` 和 `aqu-sz`。
- **缓冲 I/O vs 直接 I/O vs fsync?** 缓冲走 page cache 快不保证落盘;O_DIRECT 绕过 cache(DB 自管缓存);fsync 强制刷脏页落盘。

---

## 七、小结 + 桥接 + 延伸

**一句话记忆点**:
> fd 背后是「fd 表→打开文件表(存 offset)→inode」三层;fd 是有限资源(socket 也算),泄漏就 `Too many open files`;`write` 只到 page cache,`fsync` 才落盘;`rm` 删的是链接,被进程持有就不释放空间;看磁盘瓶颈别只盯 `%util`,要看 `await`。

**四语言桥接**:

| 场景 | Java | Go | Python | Node/JS |
|------|------|-----|--------|---------|
| 强制落盘 | `FileChannel.force()` / `fd.sync()` | `File.Sync()` | `os.fsync(fd)` | `fs.fsyncSync(fd)` |
| I/O 多路复用(一个线程管海量 fd) | Netty(epoll) | **netpoller**(epoll) | **asyncio**(epoll/selectors) | libuv(epoll) |
| fd/连接泄漏 | 没 close 的 Stream/Connection | 漏 `defer Close()` | 没 `with`/没 close | 没 `.end()`/句柄泄漏 |

→ 「阻塞 read 时进程进入 `S`/`D`,epoll 让单线程不阻塞地管上万 fd」正是你已学的并发模型的 OS 基础:[`python-concurrency/04-asyncio-core`](../../python-concurrency/04-asyncio-core/)、[`golang/concurrency`](../../golang/concurrency/)(netpoller)。

**延伸指针**:
- 磁盘 I/O 与文件系统机制(块层、调度器、文件系统对比)→ `performance-tuning-roadmap/00-os-fundamentals/03-disk-io-filesystem.md`
- 磁盘工具深入(iostat/iotop/blktrace)→ `performance-tuning-roadmap/02-linux-tools/03-disk-tools.md`
- I/O 性能调优 → `performance-tuning-roadmap/08-network-io/05-io-performance.md`

➡️ 下一章:[`06 · 网络模型`](../06-networking/)(进程要的第四种资源:网络;socket 也是 fd,TCP 状态机与连接排查)
