# 08 权限与安全原语

> **这章解决什么问题**
>
> 线上权限问题常被简化成「chmod 一下」「用 root 跑」。但 Linux 的权限模型不只是 rwx：还有 real/effective UID、setuid、capabilities、user namespace、seccomp、AppArmor/SELinux。理解这些原语，才能解释为什么容器里 root 不一定等于宿主 root，为什么绑定 80 端口需要特殊权限，为什么 `privileged: true` 风险很大。

**依赖**：

- fd、inode、目录权限 → [`linux/03-io-primitives`](../03-io-primitives/README.md)
- 进程、exec、signal → [`linux/02-execution-primitives`](../02-execution-primitives/README.md)
- namespace/cgroup/容器进程 → [`linux/07-container-cgroup-primitives`](../07-container-cgroup-primitives/README.md)

**三层怎么读：**

- **① 你视角** — 从 `Permission denied`、容器 root、Kubernetes securityContext 搭桥。
- **② 黑盒内部** — 看 UID/GID、capability、seccomp、LSM 分别卡在哪一层。
- **③ 砸实** — 用 `id`、`stat`、`/proc/self/status`、`/proc/self/attr/current` 看证据。

---

## 原语一：UID/GID 是内核做权限判断的身份

### ① 你视角

你登录系统时看到用户名，例如 `deploy`、`root`。但内核做权限判断时主要看数字身份：UID 和 GID。

### ② 黑盒内部

一个进程不只有一个 UID。常见有：

| 身份 | 含义 |
|---|---|
| real UID | 谁启动了这个进程 |
| effective UID | 当前做权限判断时用谁的权限 |
| saved UID | 支持进程临时降权/恢复权限 |
| fs UID | 文件系统权限判断使用的 UID，通常等于 effective UID |

GID 也有类似概念，并且进程可以有 supplementary groups。

权限判断大致是：

```text
process credential
  effective uid/gid/groups
    + file owner/group/mode
    + capabilities
    + LSM policy
  → allow / deny
```

`root` 特殊不是因为名字特殊，而是 UID 0 在传统 Unix 权限模型里拥有绕过大量检查的能力。现代 Linux 又把 root 权限拆成 capabilities，见后文。

### ③ 砸实

```bash
id
cat /proc/self/status | grep -E 'Uid|Gid|Groups'
```

看点：

- `Uid:` 通常按 `real effective saved fs` 顺序展示。
- `Gid:` 也是类似口径。
- 排查权限问题时，不要只看用户名，要看进程实际 effective UID/GID。

---

## 原语二：文件权限不是只有文件本身，目录也参与判断

### ① 你视角

你可能遇到过：文件本身是 `rw-r--r--`，但程序还是打不开；或者目录有写权限但不能删除某些文件。这说明权限检查不只看目标文件。

### ② 黑盒内部

Linux 文件权限由三组 rwx 组成：

```text
owner  group  others
 rwx    rwx    rwx
```

文件和目录的 `rwx` 语义不同：

| 位 | 普通文件 | 目录 |
|---|---|---|
| r | 读取文件内容 | 列出目录项名字 |
| w | 修改文件内容 | 在目录中创建/删除/重命名目录项 |
| x | 执行文件 | 进入/穿过目录，访问目录下路径 |

打开一个路径时，内核会沿路径逐级检查目录执行权限：

```text
/var/log/app/error.log
  need x on /
  need x on /var
  need x on /var/log
  need permission on error.log
```

所以 `Permission denied` 可能不是目标文件权限错，而是上级目录缺少 `x`。

### ③ 砸实

```bash
namei -l /var/log/app/error.log
stat -c '%A %a %U:%G %n' /var /var/log /var/log/app /var/log/app/error.log
```

看点：

- `namei -l` 逐级展示路径组件权限。
- 目录缺 `x` 时，即使知道文件名也无法访问路径。

---

## 原语三：umask、setuid、setgid、sticky bit 改变默认和特殊行为

### ① 你视角

你创建文件时明明没有显式指定权限，结果默认不是 `666` 或 `777`。某些命令普通用户执行却能做高权限操作，例如 `passwd` 修改密码。`/tmp` 任何人可写，但不能随便删别人的文件。这些都来自特殊权限机制。

### ② 黑盒内部

### umask

新文件默认权限不是直接等于程序请求值，而是：

```text
final_mode = requested_mode & ~umask
```

常见：

```text
file requested 666, umask 022 → 644
dir  requested 777, umask 022 → 755
```

### setuid / setgid

如果可执行文件设置了 setuid 位，进程执行它时 effective UID 会变成文件 owner。

```text
normal exec:
  effective uid = caller uid

setuid exec:
  effective uid = file owner uid
```

这也是 `passwd` 这类程序能以受控方式修改系统文件的原因。它不是把普通用户变成 root，而是在一个小程序里临时获得高权限，并由程序自己做输入校验。

### sticky bit

目录设置 sticky bit 后，目录可写不代表能删任何人的文件。典型例子是 `/tmp`：

```text
drwxrwxrwt /tmp
```

最后的 `t` 表示 sticky bit。只有文件 owner、目录 owner 或 root 能删除目录里的文件。

### ③ 砸实

```bash
umask
ls -l /usr/bin/passwd
ls -ld /tmp
```

看点：

- `passwd` 常见权限里有 `s`，表示 setuid。
- `/tmp` 常见权限最后是 `t`。

---

## 原语四：capabilities 把 root 权限拆成更小的能力

### ① 你视角

服务想监听 80 端口，传统做法是用 root 启动。但这太粗暴。更小的做法是只给它 `CAP_NET_BIND_SERVICE`。

Kubernetes/Docker 里也经常看到 `capAdd` / `capDrop`，这就是 Linux capabilities。

### ② 黑盒内部

传统模型里 UID 0 拥有大量特权。capabilities 把这些特权拆成多个独立能力。

常见 capability：

| capability | 能做什么 |
|---|---|
| `CAP_NET_BIND_SERVICE` | 绑定 1024 以下端口 |
| `CAP_NET_ADMIN` | 修改网络配置、路由、iptables 等 |
| `CAP_SYS_ADMIN` | 很多系统管理能力，范围极大，风险很高 |
| `CAP_SYS_PTRACE` | ptrace 其他进程，调试/观测相关 |
| `CAP_DAC_OVERRIDE` | 绕过传统文件权限检查 |

进程 capability 集合不止一个，常见有 permitted、effective、inheritable、bounding、ambient。日常排查最先看 effective 和 bounding：

```text
process credentials
  uid/gid
  capability sets
  seccomp mode
  LSM labels/profiles
```

### ③ 砸实

```bash
cat /proc/self/status | grep Cap
getcap /usr/bin/ping 2>/dev/null || true
```

看点：

- `/proc/self/status` 里的 `CapEff` 是当前生效 capability 位图。
- `getcap` 能查看文件 capability，但系统不一定默认安装。
- 生产容器建议默认 drop 掉不需要的 capabilities，尤其谨慎对待 `CAP_SYS_ADMIN`。

---

## 原语五：容器 root 要看 user namespace 和 capability

### ① 你视角

容器里 `id` 显示 `uid=0(root)`，这是否意味着它就是宿主机 root？答案取决于 user namespace、capability、挂载和 runtime 配置。

### ② 黑盒内部

容器 root 可能有两种典型情况：

| 情况 | 含义 |
|---|---|
| 没有 user namespace remap | 容器内 UID 0 可能对应宿主机 UID 0，风险更高 |
| 使用 user namespace | 容器内 UID 0 映射到宿主机非 0 UID，风险降低 |

user namespace 通过 UID/GID 映射表改变身份解释：

```text
container uid 0
  → host uid 100000
```

但这不是唯一边界。即使 user namespace 降低了 root 风险，如果容器还拥有危险 capability、挂载了宿主敏感目录、或者以 privileged 模式运行，仍然可能突破隔离边界。

```text
container privilege =
  uid mapping
  + capabilities
  + mounts
  + seccomp
  + LSM
  + device access
```

### ③ 砸实

```bash
id
cat /proc/self/uid_map
cat /proc/self/gid_map
cat /proc/self/status | grep Cap
```

看点：

- `uid_map` 如果是 `0 0 ...`，表示容器内 UID 0 映射到宿主 UID 0。
- 如果是 `0 100000 ...`，表示容器内 root 映射到宿主普通范围。
- 还要结合 `CapEff`、mount、seccomp、LSM 一起判断风险。

---

## 原语六：seccomp 限制的是能调用哪些 syscall

### ① 你视角

有些程序在容器里报：

```text
Operation not permitted
```

但文件权限看起来没问题，UID 也对。这时可能不是传统权限，而是 seccomp 阻止了某个 syscall。

### ② 黑盒内部

seccomp 是 syscall 过滤机制。它允许进程进入受限模式，内核在 syscall 入口处按规则判断：

```text
process calls syscall
  → seccomp filter
    allow / errno / kill / trap / trace
  → syscall implementation
```

容器 runtime 通常会给容器套一个默认 seccomp profile，禁止一些高风险 syscall，例如部分 namespace、keyring、raw IO、内核模块相关操作。

seccomp 和 capability 不同：

| 机制 | 卡在哪里 |
|---|---|
| capability | 某些特权操作的权限检查 |
| seccomp | syscall 是否允许进入内核实现 |
| LSM | 更细的安全策略/标签检查 |

### ③ 砸实

```bash
grep Seccomp /proc/self/status
```

常见值：

| 值 | 含义 |
|---|---|
| `0` | 未启用 |
| `1` | strict mode |
| `2` | filter mode，常见容器默认模式 |

更深入需要用 `strace` 看失败 syscall，或查看容器 runtime/Kubernetes 配置的 seccomp profile。

---

## 原语七：AppArmor/SELinux 属于 LSM 策略层

### ① 你视角

有时 root 也会被拒绝访问某些文件或操作。因为 Linux 权限不是只看 UID/capability，还可能经过 LSM 安全模块检查。

### ② 黑盒内部

LSM（Linux Security Modules）是在内核关键操作路径上挂安全检查的框架。常见实现：

| LSM | 常见系统 | 核心概念 |
|---|---|---|
| AppArmor | Ubuntu/Debian 常见 | profile 路径/程序策略 |
| SELinux | RHEL/CentOS/Fedora 常见 | label/type/domain 策略 |

一个操作可能要连续过多道门：

```text
open("/secret")
  → DAC: UID/GID/rwx
  → capability checks
  → LSM hook: AppArmor/SELinux policy
  → allow / deny
```

所以 root 不是万能解释。root 可以绕过很多 DAC 检查，但不一定绕过 LSM 策略。

### ③ 砸实

```bash
cat /proc/self/attr/current 2>/dev/null || true
```

看点：

- AppArmor 环境可能显示当前 profile。
- SELinux 环境通常有安全上下文。
- 具体排查需要结合系统审计日志，例如 `audit.log` 或 `dmesg`。

---

## 本章速查

| 问题 | 先看哪里 |
|---|---|
| `Permission denied` | `id`、`namei -l`、`stat`、effective UID/GID |
| 目录能写但不能删别人文件 | sticky bit |
| 普通用户为什么能执行高权限操作 | setuid/setgid 或 file capability |
| 服务要绑定 80 端口 | `CAP_NET_BIND_SERVICE` |
| 容器 root 是否危险 | user namespace 映射 + capabilities + mounts + privileged |
| 容器里 syscall 被拒 | seccomp profile |
| root 也被拒绝 | AppArmor/SELinux 等 LSM |

**最小心智模型**：

```text
permission decision =
  process credential(uid/gid/groups)
  + file mode/owner
  + capabilities
  + namespace mapping
  + seccomp syscall filter
  + LSM policy
```

下一章：[`09 时间与定时器原语`](../09-time-timer-primitives/README.md)
