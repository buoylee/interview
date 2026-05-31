# 09 · 容器底层(Linux 视角)

> 🧪 **环境**:VM shell,本章要用 Docker,先在 VM 里装(`00-lab` 说好留到这章):
> ```bash
> sudo apt-get update && sudo apt-get install -y docker.io
> sudo systemctl enable --now docker     # 接 08:用 systemd 起 docker
> sudo usermod -aG docker $USER           # 之后免 sudo(需重新登录生效)
> ```
> 你天天用 Docker/K8s,但容器到底是什么?这一章用前面 8 章的知识把它拆开——你会发现**容器没有任何新东西,全是 namespace + cgroup + overlayfs 的组合**。

---

## 一、开篇盲点

- 容器是「轻量虚拟机」吗?(**不是**,它没有自己的内核)
- 为什么容器里 `ps` 只看到自己几个进程、`free` 却看到宿主机的大内存(接 `04`)?
- 容器里 PID 1 是你的 app——这有什么坑(接 `03` 的信号和僵尸)?
- 镜像为什么能分层共享、容器删了改动就没了?

---

## 二、正文 · 原理

### 2.1 一句话:容器就是一个「被特殊安排的普通进程」

> **容器 = 被 namespace 隔离(看不到别人)+ 被 cgroup 限制(用不超额)+ 用 overlayfs 分层文件系统 的一个普通 Linux 进程。**

它**和宿主机共享同一个内核**(没有 Guest OS),所以启动快、开销小。这正是它和虚拟机的根本区别:

| | 容器 | 虚拟机 |
|---|------|--------|
| 内核 | 共享宿主机内核 | 各有独立内核 |
| 隔离 | namespace(进程级) | Hypervisor(硬件级) |
| 开销 | 几乎等于跑个进程 | 一整套 OS |
| 启动 | 毫秒级 | 秒~分钟级 |

> 这也解释了 `00-lab` 为什么主环境用 VM:容器共享内核,改 `sysctl`、跑 systemd、造真 OOM 都受限;VM 才有完整内核。

### 2.2 namespace:隔离「它能看到什么」

namespace 让进程**只看到属于自己的那部分系统资源**:

| namespace | 隔离什么 | 效果 |
|-----------|----------|------|
| **pid** | 进程号 | 容器里 PID 从 1 开始,看不到宿主机进程 |
| **net** | 网络栈 | 独立网卡/IP/端口/路由(接 `06`) |
| **mnt** | 挂载点 | 看到的根文件系统是镜像,不是宿主机的(接 `02`) |
| **uts** | 主机名 | 容器有自己的 hostname |
| **ipc** | 进程间通信 | 独立的共享内存/信号量 |
| **user** | uid/gid 映射 | 容器内 uid 0 可映射到宿主机非特权用户(接 `02`) |

关键:**这是单向的**。容器只看到自己;但**宿主机能看到容器里所有进程的真实 PID**(因为它们本就是宿主机的进程)。这点对排查极重要(见 2.6)。

### 2.3 cgroup:限制「它能用多少」(接 04 / 08)

namespace 管「看到什么」,cgroup 管「能用多少」。CPU、内存、PID 数、I/O 都能限。

- 容器 `--memory 512m` → 写进该容器 cgroup 的 `memory.max`。进程用超 → **cgroup OOM**(`OOMKilled`,exit 137),即使宿主机内存还很多(回顾 `04` 的头号坑)。
- **systemd 和容器用的是同一套 cgroup 机制**(接 `08`):一个 service、一个容器,各是一个 cgroup 子树。

### 2.4 overlayfs:镜像分层 + 写时复制

镜像是**只读层的叠加**;启动容器时,在最上面加一个**可写层**:

```
       ┌─────────────────────┐
容器写 │  可写层 (upperdir)   │ ← 容器运行时的改动都写这里
       ├─────────────────────┤
       │  镜像层 N (只读)     │ ┐
       │  ...                │ ├ 多个容器共享同一份只读镜像层
       │  镜像层 1 (只读)     │ ┘
       └─────────────────────┘  合并视图 = 容器看到的根文件系统
```

改一个来自只读层的文件时,先**复制到可写层再改(copy-up,写时复制)**。推论:
- 镜像层只读且可共享 → 多个容器省空间、秒级启动。
- **可写层是临时的**:容器删了,改动就没了 → 数据要用 **volume** 持久化。

### 2.5 「容器只是进程」的几个要命推论

**① `free`/`top` 看到宿主机(接 04)**:传统工具读 `/proc/meminfo`,那是宿主机的;容器的真实限制在 cgroup。要看 `cat /sys/fs/cgroup/memory.max`。运行时(JVM/Node/Go)也得感知 cgroup 才不会把堆设过大(回顾 `04`)。

**② 容器 PID 1 = 你的 app,两个坑(接 03)**:
- **信号陷阱**:内核对 PID 1 特殊对待——**没有注册 handler 的信号默认被忽略**。所以 app 当 PID 1 又没处理 `SIGTERM`,`docker stop`/K8s 删 Pod 发的 SIGTERM 会被忽略,**白等宽限期后被 SIGKILL 强杀**,优雅关闭失效。
- **僵尸堆积**:PID 1 还要负责收养并 `wait` 孤儿进程(接 `03`)。你的 app 通常不干这事 → 子进程僵尸堆积。
- **解法**:用 `tini`/`dumb-init` 当 PID 1(`docker run --init`),它正确转发信号 + 回收僵尸。

**③ 容器 root 默认就是宿主机 root**:不开 user namespace 时,容器内 uid 0 = 宿主机 uid 0,逃逸即提权。生产要:跑非 root(`USER`)、开 user ns、drop capabilities、只读根文件系统。

### 2.6 排查容器:前面 03–07 的技能照样用

因为容器就是宿主机进程,**在宿主机上**用真实 PID 排查它,`ps`/`strace`/`lsof` 全部穿透:

```bash
PID=$(docker inspect -f '{{.State.Pid}}' <容器>)   # 拿容器主进程的宿主机真实 PID
sudo strace -p $PID          # 直接 strace 容器进程(接 07)
sudo lsof -p $PID            # 看它的 fd(接 05/06)
sudo nsenter -t $PID -n ss -lntp   # 进它的 net namespace 看监听端口(接 06)
```

> `nsenter` 钻进容器的某个 namespace 执行命令——容器里没装的工具(如 `ss`),用宿主机的工具进它的 namespace 看,排查神器。

---

## 三、怎么看(命令 + 真实输出怎么读)

```console
$ docker stats --no-stream        # 各容器的 cgroup 资源(CPU/内存/IO/net)
$ docker top <容器>               # 容器内进程(容器视角 PID)
$ docker inspect -f '{{.State.Pid}}' <容器>   # 主进程的宿主机真实 PID

# 在宿主机上,把容器进程当普通进程看:
$ ps -ef | grep <进程名>          # 看到真实 PID(和容器内 PID 不同 → pid ns)
$ sudo ls -l /proc/<PID>/ns/      # 它的各个 namespace
$ cat /proc/<PID>/cgroup          # 它属于哪个 cgroup
$ lsns                            # 列出系统所有 namespace
```

---

## 四、动手实验(沙箱)

> 🧪 在 VM 里跑(已装 docker)。命令前的 `sudo` 在加入 docker 组并重新登录后可省。

**实验 1:容器只是进程(pid namespace)**
```bash
sudo docker run -d --name web nginx
sudo docker top web                          # 容器视角:nginx PID 是 1、若干 worker
PID=$(sudo docker inspect -f '{{.State.Pid}}' web)
echo "宿主机真实 PID = $PID"
ps -o pid,comm -p $PID                        # 宿主机视角:同一进程,完全不同的 PID
sudo ls -l /proc/$PID/ns/ | awk '{print $9,$10,$11}'   # 看它的 namespaces
```

**实验 2:容器里 `free` 骗你,cgroup 才是真的(接 04)**
```bash
sudo docker run --rm -m 64m alpine sh -c '
  echo "== cgroup 内存上限(真实限制)=="; cat /sys/fs/cgroup/memory.max
  echo "== free 看到的(其实是宿主机)=="; free -m | head -2
'
# memory.max ≈ 67108864 (64M),但 free 显示的是宿主机内存 —— 这就是 04 的坑
```

**实验 3:PID 1 的信号陷阱(优雅关闭失效)**
```bash
# app 直接当 PID 1、没处理 SIGTERM:docker stop 会等满 10s 才强杀
sudo docker run -d --name t2 alpine sh -c 'while true; do sleep 1; done'
echo "== 不加 --init,SIGTERM 被 PID1 忽略 =="; time sudo docker stop t2     # 约 10s
sudo docker rm t2 >/dev/null

# 加 --init:tini 当 PID1,转发信号给子进程,秒停
sudo docker run -d --init --name t3 alpine sh -c 'while true; do sleep 1; done'
echo "== 加 --init,信号被正确转发 =="; time sudo docker stop t3            # 很快
sudo docker rm t3 >/dev/null
```

**实验 4:用宿主机工具钻进容器 net namespace(接 06)**
```bash
PID=$(sudo docker inspect -f '{{.State.Pid}}' web)
sudo nsenter -t $PID -n ss -lntp             # 容器里没 ss 也能看它监听的端口
sudo docker rm -f web >/dev/null
```

---

## 五、生产踩坑框 ⚠️

> **优雅关闭失效(超高频)**:app 当 PID 1 又没注册 SIGTERM handler → `docker stop`/K8s 删 Pod 时 SIGTERM 被忽略,白等 `terminationGracePeriodSeconds` 后被 SIGKILL,丢请求。修法:`--init`(tini)、或确保 app 正确处理 SIGTERM(接 `03`)。

> **容器里看资源别信 `free`/`top`**:读的是宿主机(接 `04`)。看真实限制用 `/sys/fs/cgroup/memory.max`;运行时设内存要用感知 cgroup 的参数(JVM `MaxRAMPercentage`、Node `--max-old-space-size`、Go `GOMEMLIMIT`)。

> **僵尸堆积**:PID 1 不回收子进程(接 `03`),用 `--init`。

> **数据丢失**:可写层是临时的,容器重建即丢;持久化数据必须挂 volume。

> **安全**:别用 root 跑容器、别随意 `--privileged`;非 root `USER`、drop capabilities、只读根文件系统。

---

## 六、本章面试速记

- **容器和虚拟机的区别?** 容器共享宿主机内核、靠 namespace+cgroup 做进程级隔离,轻量秒启;VM 各有内核、硬件级隔离,重。
- **容器的底层基石?** namespace(隔离看到什么)+ cgroup(限制用多少)+ overlayfs(镜像分层、写时复制)。
- **为什么容器里 `free` 看到宿主机内存?** 传统工具读宿主机 `/proc`;真实限制在 cgroup `memory.max`。
- **容器 PID 1 有什么坑?** 信号陷阱(没 handler 的信号被忽略 → SIGTERM 失效)+ 不回收僵尸;用 `tini`/`--init`。
- **怎么在宿主机排查容器进程?** `docker inspect` 拿真实 PID,`strace`/`lsof` 直接用,`nsenter` 进它的 namespace。
- **容器里的 root 是宿主机 root 吗?** 不开 user namespace 时是,有提权风险。

---

## 七、小结 + 桥接 + 延伸

**一句话记忆点**:
> 容器是「namespace 隔离 + cgroup 限制 + overlayfs 分层」的普通进程,和宿主机共享内核;所以前面所有排查技能照用、`free` 看宿主机要看 cgroup、PID 1 要用 tini 处理信号和僵尸。

**桥接:K8s ≈ 给容器加了编排的「分布式 systemd」**

| K8s 概念 | 其实就是 | 本课对应 |
|----------|----------|----------|
| `resources.limits` | cgroup 限制 | `04` / `08` |
| `OOMKilled` (137) | cgroup memory OOM | `04` |
| `securityContext.runAsUser` / capabilities | user namespace / caps | `02` |
| `terminationGracePeriodSeconds` | SIGTERM → 等待 → SIGKILL | `03` / `08` |
| liveness/readiness probe | 健康检查(systemd 无,理念类似) | `08` |

→ 各语言在容器里都要**感知 cgroup 设内存**(接 `04`),都要**处理 SIGTERM 优雅关闭**(接 `03`)——这是容器化部署的两条铁律。

**延伸指针**:
- 容器环境的性能与资源细节 → `performance-tuning-roadmap/12-container/`
- cgroup/namespace 机制深入 → `performance-tuning-roadmap/00-os-fundamentals/05-process-thread-coroutine.md`

➡️ 最后一章:[`10 · Shell 脚本 + 文本三件套`](../10-shell-scripting/)(把前面学的排查命令组合成可复用脚本)
