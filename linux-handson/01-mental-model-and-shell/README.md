# 01 · Linux 世界观 + shell 工作原理

> 🧪 **环境**:VM shell(`multipass shell linux-lab`)
> 这一章不教「命令大全」,而是教**命令背后发生了什么**。打通这层,后面所有排查都有了地基。

---

## 一、开篇盲点

你现在大概是这样用 Linux 的:把终端当成一个「输命令的黑框」,记住一堆命令组合,记不住就搜。问题是——

- 为什么 `cmd > f 2>&1` 和 `cmd 2>&1 > f` 结果完全不同?(后者其实不会把错误写进文件)
- 为什么程序的报错日志「丢了」,明明我重定向了输出?
- 为什么 `cd` 不能写成一个独立的 `/usr/bin/cd` 程序?
- 为什么 SSH 一断,后台跑的进程就死了?

这些都不是「命令记不熟」,而是**不知道命令在跟内核做什么交互**。这一章把三件事讲透:**内核与用户态的边界、一切皆文件、shell 执行命令的全过程**。讲完上面四个问题你都能秒答。

---

## 二、正文 · 原理

### 2.1 两层世界:用户态 vs 内核态

Linux 把世界分成两层,中间只有一道门:

```
┌─────────────────────────────────────────────┐
│              用户态 (User Space)              │
│   你的进程:bash / java / python / nginx ...   │
│   只能碰自己的内存,不能直接碰硬件             │
└───────────────────────┬─────────────────────┘
                        │  系统调用 (syscall)  ← 唯一的门
                        │  read/write/open/fork/execve...
┌───────────────────────┴─────────────────────┐
│              内核态 (Kernel Space)            │
│   管理 CPU、内存、磁盘、网卡;调度进程         │
│   代表进程去碰硬件                            │
└─────────────────────────────────────────────┘
```

**关键认知**:进程**不能**直接读磁盘、发网络包、创建进程。它只能发起**系统调用(syscall)**,请内核代劳。一个进程一生干的所有「实事」,本质都是一连串 syscall。

> 类比:进程是餐厅顾客,内核是厨房,syscall 是点单。顾客不能自己冲进厨房炒菜,只能下单,厨房做好端出来。

这就是为什么排查时 `strace`(跟踪 syscall)这么有用——它直接告诉你进程在向内核要什么、卡在哪个请求上。

### 2.2 一切皆文件

Linux 的核心抽象:**几乎所有东西都通过「文件」这套统一接口操作**——你用同一组 syscall(`open`/`read`/`write`/`close`)去读写它们:

| 你以为是… | 其实是个「文件」 | 例子 |
|-----------|------------------|------|
| 普通文件 | 普通文件 | `/etc/hosts` |
| 目录 | 一种特殊文件 | `/home` |
| 硬盘、终端 | 设备文件 | `/dev/sda`、`/dev/tty` |
| 进程间管道 | 管道文件 | `cmd1 \| cmd2` 里那根「\|」 |
| 网络连接 | socket | 一条 TCP 连接 |
| 内核状态 | 伪文件 | `/proc/meminfo`、`/proc/$$/fd` |

进程操作这些「文件」时,内核给每个打开的文件发一个小整数当句柄——**文件描述符(file descriptor, fd)**。后面排查「连接数爆」「fd 耗尽」,本质都是这个 fd 数量的问题(详见 `05`)。

### 2.3 每个进程自带三个 fd:0 / 1 / 2

进程一启动,内核默认给它三个 fd:

| fd | 名字 | 默认指向 | 干什么 |
|----|------|----------|--------|
| `0` | stdin(标准输入) | 终端键盘 | 读输入 |
| `1` | stdout(标准输出) | 终端屏幕 | 写正常输出 |
| `2` | stderr(标准错误) | 终端屏幕 | 写错误/日志 |

`1` 和 `2` 默认都指向屏幕,所以平时看起来混在一起。但它们是**两条独立的管子**——这是理解重定向的关键。

### 2.4 命令的一生:fork + exec

你在 shell 敲一条 `ls -l`,shell 内部经历这几步:

```
1. 读入并解析命令行          → "ls" + 参数 "-l"
2. 判断:是内建命令吗?
     是(如 cd) → shell 自己执行,结束
     否(如 ls) → 继续
3. 在 PATH 里找 "ls"          → /usr/bin/ls
4. fork()                     → 复制出一个子进程(shell 的克隆)
5. 子进程 execve("/usr/bin/ls") → 把自己"换脑"成 ls 程序
6. 父 shell wait()            → 等子进程结束,回收它
7. 子进程结束,shell 显示新提示符
```

两个关键 syscall:
- **`fork()`**:把当前进程复制一份(父子俩除了 PID 几乎一样,包括那三个 fd)。
- **`execve()`**:让进程「换脑」——保留进程壳子(PID、fd 不变),但把要执行的程序代码整个换成新程序。

> **为什么 `cd` 必须是内建命令?** 因为 `cd` 要改变**当前 shell 自己**的工作目录。如果 `cd` 是个外部程序,它会跑在 fork 出来的**子进程**里,子进程改了自己的目录然后退出,父 shell 的目录纹丝不动。所以 `cd`、`export`、`umask` 这类「要改变 shell 自身状态」的命令,必须由 shell 亲自执行,不能 fork 出去。

### 2.5 重定向与管道的本质:都是在摆弄 fd

理解了「fd」和「fork+exec」,重定向和管道就一通百通了。

**重定向**:在 `execve` 之前,把某个 fd 改指向别处。

```bash
ls -l > out.txt
```

实际发生:fork 出子进程后、exec 之前,shell 把子进程的 **fd 1** 从「屏幕」改指向「out.txt 这个文件」。然后 `ls` 照常往 fd 1 写,内容就进了文件。`ls` 自己完全不知道输出去了哪——它只认 fd 1。

**管道**:用内核的 `pipe()` 造一根管道,把**前一个进程的 fd 1** 接到**后一个进程的 fd 0**。

```bash
ps aux | grep java
```

`ps` 往 fd 1 写 → 管道 → `grep` 从 fd 0 读。**注意:管道两端是两个独立进程**(`ps` 和 `grep` 各是一个进程),内核负责在它们之间传数据。

### 2.6 经典坑:`2>&1` 为什么必须放在 `>file` 后面

这是面试高频、也是日志丢失的真凶。先记住一句话:

> **`2>&1` 的意思是「把 fd 2 指向 fd 1 当前所指的地方」——是「复制当下的指向」,不是「绑定 fd 1 以后的变化」。**

对比两种写法,从左到右处理:

```bash
# 写法 A(正确):错误也进文件
cmd > out.txt 2>&1
#   ① > out.txt   : fd1 → 文件
#   ② 2>&1        : fd2 → fd1 现在指向的(文件)
#   结果:fd1、fd2 都 → 文件 ✅

# 写法 B(错误):错误仍然打屏幕
cmd 2>&1 > out.txt
#   ① 2>&1        : fd2 → fd1 现在指向的(屏幕!)
#   ② > out.txt   : fd1 → 文件(但 fd2 已经定格在屏幕了)
#   结果:fd1 → 文件,fd2 → 屏幕 ❌ 错误日志没进文件
```

写法 B 是「报错日志神秘丢失」的典型原因。记忆点:**先定 fd1 的去向,再让 fd2 跟上**。

---

## 三、怎么看(命令 + 真实输出怎么读)

### 区分内建命令 vs 外部命令:`type`

```console
$ type cd
cd is a shell builtin            ← 内建,shell 亲自执行

$ type ls
ls is aliased to `ls --color=auto'   ← 还是个别名

$ type -a python3
python3 is /usr/bin/python3      ← 外部程序,在 PATH 里
```

> `type` 比 `which` 更准:`which` 只查 PATH 里的外部程序,看不出内建命令和别名。

### 看 PATH:命令从哪找

```console
$ echo $PATH
/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# shell 从左到右在这些目录里找你敲的命令,找到第一个就用
```

### 看进程自己的 fd:`/proc/<pid>/fd`

`$$` 是当前 shell 的 PID。直接看 shell 的三个标准 fd 指向哪:

```console
$ ls -l /proc/$$/fd
lrwx------ 1 ubuntu ubuntu 64 ... 0 -> /dev/pts/0     ← stdin  → 终端
lrwx------ 1 ubuntu ubuntu 64 ... 1 -> /dev/pts/0     ← stdout → 终端
lrwx------ 1 ubuntu ubuntu 64 ... 2 -> /dev/pts/0     ← stderr → 终端
```

三个都指向 `/dev/pts/0`(你的伪终端)。这就是「fd 0/1/2 默认指向终端」的实锤。

### 用 strace 看「换脑」过程

```console
$ strace -f -e trace=execve,openat,dup2 -- bash -c 'echo hi > /tmp/x' 2>&1 | head
execve("/usr/bin/bash", ["bash", "-c", "echo hi > /tmp/x"], ...) = 0   ← bash 被 exec
openat(AT_FDCWD, "/tmp/x", O_WRONLY|O_CREAT|O_TRUNC, 0666) = 3          ← 打开文件,拿到 fd 3
dup2(3, 1)                                                = 1           ← 把 fd1 复制成 fd3 的指向!这就是 > 的真身
```

看到了吗——重定向 `> /tmp/x` 在内核层面就是 `openat` 拿到 fd 3,再 `dup2(3, 1)` 把 fd 1 改指向它。**理论和系统调用对上了。**

---

## 四、动手实验(沙箱)

> 🧪 全部在 `multipass shell linux-lab` 里跑。

**实验 1:看自己的三个 fd**
```bash
ls -l /proc/$$/fd          # 0/1/2 都 → /dev/pts/N
exec 3> /tmp/myfd          # 手动开一个 fd 3 指向文件
ls -l /proc/$$/fd          # 现在多了 3 -> /tmp/myfd
echo "hello via fd3" >&3   # 往 fd3 写
cat /tmp/myfd              # 看到 hello via fd3
exec 3>&-                  # 关掉 fd3
```

**实验 2:亲手验证 `2>&1` 顺序(本章重点)**
```bash
# 造一个既有正常输出、又有错误输出的命令
ls /etc/hostname /no/such/path > A.txt 2>&1   # 写法 A
ls /etc/hostname /no/such/path 2>&1 > B.txt   # 写法 B

echo "== A.txt(正确:错误也在里面)=="; cat A.txt
echo "== B.txt(错误没进来,错误打了屏幕)=="; cat B.txt
```
观察:`A.txt` 同时含 `/etc/hostname` 和 `No such file` 报错;`B.txt` 只有正常那行,报错跑到了你的屏幕。

**实验 3:管道两端是两个进程**
```bash
sleep 300 | cat &          # 起一个管道,丢后台
ps -o pid,ppid,stat,cmd --ppid $$    # 看到 sleep 和 cat 是两个独立进程
kill %1                    # 收掉
```

**实验 4:`cd` 为什么不能是外部程序**
```bash
type cd                    # shell builtin
# 模拟"外部 cd 跑在子进程"会怎样:
(cd /tmp; pwd)             # 子 shell 里 cd 到 /tmp
pwd                        # 回到外层,目录没变 —— 印证 2.4 的解释
```

---

## 五、生产踩坑框 ⚠️

> **「我明明重定向了日志,报错却没记下来」**
> 八成是写成了 `app 2>&1 > app.log`(顺序错)或只写了 `app > app.log`(没带 `2>&1`,stderr 漏了)。正确:`app > app.log 2>&1`。

> **后台跑服务的标准写法**:`nohup ./app > app.log 2>&1 &`
> `nohup` 让进程忽略挂断信号(SSH 断开不被杀,详见 `03` 会话/控制终端),`> ... 2>&1` 把正常和错误都收进日志,`&` 丢后台。这一行四个知识点都在本课。

> **`cmd | while read line; do ...; done` 里改的变量,循环外读不到**
> 因为管道右侧在**子 shell** 里跑(独立进程,见 2.5),变量改在子进程里,父 shell 看不到。解法见 `10` 章(用 `< <(cmd)` 进程替换)。

---

## 六、本章面试速记

- **「一切皆文件」具体指什么?** 普通文件、目录、设备、管道、socket、`/proc` 伪文件,都用同一套 `open/read/write/close` syscall 操作,内核用文件描述符(fd)做句柄。
- **`cmd > f 2>&1` 和 `cmd 2>&1 > f` 区别?** 重定向从左到右处理,`2>&1` 是「复制 fd1 当下的指向」。前者 fd1 先指文件,fd2 再跟上→都进文件;后者 fd2 先复制了屏幕,再改 fd1→错误仍打屏幕。
- **`cd` 为什么是内建命令?** 它要改 shell 自身的工作目录;若是外部程序会跑在 fork 出的子进程里,子进程改完就退出,父 shell 目录不变。
- **管道 `a | b` 两端是几个进程?** 两个,内核用 `pipe()` 把 a 的 fd1 接到 b 的 fd0。

---

## 七、小结 + 延伸

**一句话记忆点**:
> 进程只会做一件事——发系统调用求内核办事;它眼里没有「文件/屏幕/网络」,只有一堆 **fd**。命令的执行 = `fork` 复制 + `execve` 换脑;重定向和管道 = 在 exec 前摆弄 fd 的指向。

**四语言桥接**:你写代码时也在做同样的事,只是被封装了——

| 概念 | Java | Go | Python | Node/JS |
|------|------|-----|--------|---------|
| 重定向子进程输出 | `ProcessBuilder.redirectOutput()` | `exec.Cmd.Stdout = f` | `subprocess.run(..., stdout=f)` | `spawn(cmd, {stdio:[...]})` |
| 继承父进程 fd | `.inheritIO()` | `cmd.Stdout = os.Stdout` | `stdout=None`(默认继承) | `stdio:'inherit'` |

你在这些语言里设的 `stdout`/`stdio`,底层就是本章的 `dup2(fd, 1)`。

**延伸指针**:
- `fork`/`execve`/进程状态/信号/会话 → 下一章 [`03 进程模型`](../03-process-model/)(本章的 fork+exec 在那里展开)
- fd、打开文件表、fd 耗尽 → [`05 I/O 与文件`](../05-io-and-files/)
- 想看 syscall 级性能剖析(strace/perf 深入) → `performance-tuning-roadmap/02-linux-tools/05-tracing-profiling.md`

➡️ 下一章:[`02 · 文件系统 + 权限`](../02-filesystem-and-permissions/)
