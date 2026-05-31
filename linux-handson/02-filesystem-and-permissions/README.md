# 02 · 文件系统 + 权限

> 🧪 **环境**:VM shell(`multipass shell linux-lab`)
> 接 `01` 的「一切皆文件」:既然一切皆文件,那这些文件**怎么组织(文件系统)、谁能动它(权限)**就是地基。这一章也把前面几章频繁出现的 `/proc` 说清楚。

---

## 一、开篇盲点

- 权限不够,你是不是 `chmod 777` 一把梭?它「解决」了问题,但你知道 `rwx` 对**文件**和**目录**分别是什么意思吗?(目录的 `x` 最反直觉)
- 软链接和硬链接,删了源文件谁还能用?
- `/proc`、`/sys` 里的「文件」是真文件吗?为什么 `cat` 它能看到内核状态、`echo` 进去能改内核参数?
- 为什么你是文件的 owner、对文件有读权限,却还是「进不去」它所在的目录?

这些都指向:不理解 **inode/链接、rwx 语义、伪文件系统**。

---

## 二、正文 · 原理

### 2.1 一棵树:FHS 与挂载

Linux 只有**一个根 `/`**,所有东西都挂在这棵树上(不像 Windows 的 C:/D:)。主要目录(FHS 规范):

| 目录 | 放什么 |
|------|--------|
| `/etc` | 配置文件(`/etc/passwd`、`/etc/hosts`、`/etc/resolv.conf`) |
| `/var` | 变化的数据:日志 `/var/log`、缓存、队列 |
| `/usr` | 程序与库(`/usr/bin`、`/usr/lib`) |
| `/tmp` | 临时文件(重启常清,sticky 见 2.6) |
| `/home` | 普通用户家目录 |
| `/dev` | 设备文件(`/dev/sda`、`/dev/null`) |
| `/proc` `/sys` | 内核的伪文件(见 2.8) |

不同磁盘/分区通过**挂载(mount)**接到树的某个目录上(挂载点)。`df -h` 看哪个目录由哪个设备提供。

### 2.2 inode 与目录:名字和实体是分开的

一个文件其实是两部分:
- **inode**:文件的「实体」,存元数据(权限、owner、大小、时间戳、数据块指针)——**但不存文件名**。
- **目录项**:目录本质是一张「**文件名 → inode 号**」的映射表。

所以「文件名」住在目录里,「文件内容和属性」住在 inode 里。这解释了 `05` 的删除真相:`rm` 删的是**目录里的名字**(unlink),inode 在「没人引用」时才释放。

```console
$ ls -li /etc/hostname
131073 -rw-r--r-- 1 root root 13 ... /etc/hostname
#  ↑ inode 号    ↑ 权限      ↑链接数
```

### 2.3 硬链接 vs 软链接

| | 硬链接 `ln a b` | 软链接(符号链接)`ln -s a b` |
|---|---|---|
| 本质 | 同一 inode 的另一个名字 | 一个特殊文件,内容是「目标路径」 |
| 删源文件后 | **还能用**(inode 引用未归零) | **悬空(dangling)**,指向不存在的路径 |
| 跨文件系统 | ❌ 不行(inode 号是单文件系统内的) | ✅ 可以 |
| 链接目录 | ❌ 一般不允许 | ✅ 可以 |
| 链接数(`ls -l` 第 2 列) | 增加 | 不影响目标的链接数 |

记忆:**硬链接是「同一个文件多个名字」,软链接是「一个写着路径的快捷方式」。**

### 2.4 权限模型 rwx(目录的 x 最易错)

`ls -l` 第一列逐位读:

```
-rwxr-xr--
│└┬┘└┬┘└┬┘
│ u   g  o      ← user(owner) / group / other 三组
│
└ 文件类型:- 普通  d 目录  l 软链接  c/b 设备  s socket  p 管道
```

`rwx` 对**文件**和**目录**含义不同——这是高频考点:

| 位 | 对文件 | 对目录 |
|----|--------|--------|
| `r` | 读内容 | 能 `ls` 列出里面的名字 |
| `w` | 改内容 | 能在里面**增删文件**(注意:删文件看的是目录的 w,不是文件本身的权限!) |
| `x` | 可执行 | **能进入/穿过该目录**(`cd`、访问里面的文件) |

> **最反直觉的点**:访问 `/a/b/file` 需要对路径上每一层目录都有 `x`。**目录没有 `x`,即使你对里面的文件有读权限,也访问不到**(进不去这一层)。`chmod 777 file` 经常没用,真正缺的是上层目录的 `x`。

八进制:`rwx`=7、`r-x`=5、`r--`=4,所以 `rwxr-xr--` = **754**。

### 2.5 owner/group、chmod/chown、umask

- **chmod** 改权限:符号式 `chmod u+x f`、`chmod go-w f`;八进制 `chmod 644 f`。
- **chown** 改属主:`chown user:group f`(改 owner 通常要 root)。
- **umask**:新建文件/目录的默认权限「掩码」。新文件权限 = 基准 & `~umask`。常见 `umask 022` → 新文件 `644`、新目录 `755`(目录要 x 才能进)。

### 2.6 特殊权限:suid / sgid / sticky

- **suid**(对可执行文件):运行时**以文件 owner 的身份**执行,而非调用者。经典例子 `passwd`——普通用户能改自己密码(写 `/etc/shadow`,本来只有 root 能写),就是因为 `passwd` 有 suid 跑成 root。`ls -l` 见 `-rwsr-xr-x` 的 `s`。
- **sgid**(对目录):目录里新建的文件**继承目录的组**(团队共享目录常用)。
- **sticky bit**(对目录):只有**文件 owner**能删自己的文件,别人删不了。`/tmp` 就有(`drwxrwxrwt` 末位 `t`),所以大家都能在 `/tmp` 写,但不能删别人的。

### 2.7 root 与 sudo

- **root**(uid 0):**无视权限检查**,能干一切。
- **sudo**:普通用户临时以 root(或他人)身份执行单条命令,由 `/etc/sudoers` 授权。比直接登录 root 更安全、可审计。

### 2.8 `/proc` 与 `/sys`:内核状态的「文件接口」

它们是**伪文件系统**——**不在磁盘上**,内容由内核实时生成。这就是「一切皆文件」最漂亮的体现:你用读写文件的方式,读写内核状态。前面各章用到的全在这:

| 路径 | 是什么 | 哪章用过 |
|------|--------|---------|
| `/proc/<pid>/fd` | 进程打开的 fd | `01`/`05` |
| `/proc/<pid>/status` `/limits` | 进程状态、资源限制 | `03`/`05` |
| `/proc/meminfo` | 内存信息 | `04` |
| `/proc/loadavg` | load average | `07` |
| `/proc/sys/...` | **可写**,改内核参数(= `sysctl`) | `04`/`06`/`08` |

`echo 3 > /proc/sys/vm/drop_caches`(`04` 清缓存)、`cat /proc/sys/net/ipv4/ip_local_port_range`(`06` 端口范围)——本质都是读写这些伪文件。

---

## 三、怎么看(命令 + 真实输出怎么读)

```console
$ ls -li file              # -i 显示 inode 号,-l 显示权限/owner/链接数
$ ls -ld /var/log          # -d 看目录本身的权限(不加 d 会列出里面内容)
$ stat /etc/hostname       # inode、权限(八进制+符号)、三个时间、链接数
$ id                       # 当前用户的 uid/gid/所属组
$ umask                    # 当前掩码(如 0022)
$ df -h                    # 各挂载点空间; lsblk 看块设备树
$ find / -perm -4000 -type f 2>/dev/null   # 全系统找 suid 程序(安全审计)
```

读 `ls -l` 一行:
```
drwxr-xr-x  2 ubuntu staff  4096 May 31 10:00 logs
│└─┬─┘└┬┘   │ └─┬──┘ └─┬─┘                    └ 名字
│ owner=rwx │  owner   group
└ d=目录    └ 链接数
→ owner(ubuntu) 可读写进;组(staff)和其他人可读可进、不可写
```

---

## 四、动手实验(沙箱)

> 🧪 在 `multipass shell linux-lab` 里跑。

**实验 1:读权限位 + 看目录本身**
```bash
ls -l /usr/bin/passwd      # 注意 owner 的 x 位是 s(suid)
ls -ld /tmp                # 末位是 t(sticky)
stat /etc/hostname
```

**实验 2:目录的 `x` 才是进门钥匙(最该做的实验)**
```bash
mkdir -p /tmp/d && echo secret > /tmp/d/f && chmod 644 /tmp/d/f
chmod 644 /tmp/d           # 去掉目录的 x(只剩 rw-)
cat /tmp/d/f               # ❌ Permission denied —— 文件可读,但进不去目录!
chmod 755 /tmp/d           # 加回 x
cat /tmp/d/f               # ✅ 现在读到 secret
rm -rf /tmp/d
```

**实验 3:硬链接 vs 软链接**
```bash
echo original > /tmp/src
ln /tmp/src /tmp/hard       # 硬链接
ln -s /tmp/src /tmp/soft    # 软链接
ls -li /tmp/src /tmp/hard /tmp/soft   # src 与 hard 同 inode、链接数=2;soft 不同
rm /tmp/src
echo "== 删源后 =="
cat /tmp/hard               # ✅ 还在(硬链接保住了 inode)
cat /tmp/soft               # ❌ No such file(软链接悬空)
rm -f /tmp/hard /tmp/soft
```

**实验 4:umask 怎么影响新文件权限**
```bash
umask                       # 看当前(通常 0022)
touch /tmp/a; ls -l /tmp/a  # 644
( umask 077; touch /tmp/b; ls -l /tmp/b )   # 600:只有自己能读写
rm -f /tmp/a /tmp/b
```

**实验 5:`/proc` 是活的**
```bash
cat /proc/loadavg           # 连续看两次,数值在变 —— 实时生成,不是磁盘文件
ls -l /proc/self/fd         # 当前进程的 fd(接 01)
grep MemAvailable /proc/meminfo   # 接 04
```

---

## 五、生产踩坑框 ⚠️

> **`chmod 777` 是坏味道**:它「能跑」是因为放开了所有人写权限,掩盖了真正的问题(应该改 owner/组或加目录 `x`),而且是安全风险——尤其 Web 可写目录被 777,等于让任何人改你的文件。正确做法:`chown` 到运行服务的用户,或精确给到 `750`/`640`。

> **部署后脚本「不能执行」**:`scp`/解压/git 检出后可执行位可能丢失 → `chmod +x deploy.sh`。CI 里也常见。

> **「明明有读权限却访问不了」**:十有八九是路径上某层目录缺 `x`。用 `namei -l /full/path/file` 逐层看每一级的权限。

> **suid 程序是提权攻击面**:定期 `find / -perm -4000` 审计,陌生的 suid 程序要警惕。

> **容器里的 root 不等于宿主机 root**:开启 user namespace 后,容器内 uid 0 映射到宿主机的非特权用户(接 `09`)。

---

## 六、本章面试速记

- **`rwx` 对文件和目录分别什么含义?** 文件:读/写内容、可执行;目录:`r`=列名字、`w`=增删文件、**`x`=能进入穿过**。访问深层文件需路径上每层目录都有 `x`。
- **硬链接 vs 软链接?** 硬链接是同 inode 的另一个名字,删源仍可用、不能跨文件系统/链目录;软链接是存路径的特殊文件,删源即悬空、可跨文件系统/链目录。
- **删一个文件看谁的权限?** 看**所在目录的 `w`**(和 sticky),不是文件本身的权限。
- **`chmod 777` 为什么不好?** 掩盖真正的属主/权限问题且有安全风险;应精确授权或改 owner。
- **suid / sgid / sticky 各干嘛?** suid=以文件属主身份运行(如 passwd);sgid 目录=新文件继承组;sticky 目录=只能删自己的文件(如 /tmp)。
- **`/proc` 是什么?** 伪文件系统,内核运行时状态的文件接口,不在磁盘上;读它看状态,写 `/proc/sys` 改内核参数。

---

## 七、小结 + 桥接 + 延伸

**一句话记忆点**:
> 文件名在目录(名字→inode),属性和内容在 inode;访问深层文件要路径每层目录都有 `x`;删文件看目录的 `w`;`/proc`、`/sys` 是内核状态的文件接口。别动不动 `chmod 777`。

**四语言/云原生桥接**(权限决定「服务以谁的身份、能不能读写」):

| 场景 | 落点 |
|------|------|
| 服务以哪个用户跑 | Dockerfile `USER appuser`、systemd `User=`(接 `08`)、K8s `securityContext.runAsUser` |
| 挂载卷的权限 | K8s `fsGroup`、容器 volume 的 owner/mode |
| 应用读写文件报错 | Java `AccessDeniedException`、Go `permission denied`、Python `PermissionError`、Node `EACCES` —— 先查文件 owner + 路径每层目录的 `x` |

**延伸指针**:
- 文件系统实现(ext4/xfs、块层、日志)→ `performance-tuning-roadmap/00-os-fundamentals/03-disk-io-filesystem.md`
- inode/链接/删除的 I/O 视角 → 本课 [`05`](../05-io-and-files/)
- `/proc/sys` 改内核参数的正式方式(`sysctl`)→ [`08`](../08-systemd-and-services/)

➡️ on-ramp(01→02)完成,前面是核心 [`03`–`07`](../03-process-model/)。接下来工程化:[`08 · systemd 与服务管理`](../08-systemd-and-services/)。
