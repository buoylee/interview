# 第 3 章·内幕 A · 容器运行时链:从 kubelet 到 runc

> 🔬 「Pod 跑起来」时 kubelet 到底做了什么?容器最终是**怎么被 Linux 创建出来**的?这章把 **kubelet → CRI → containerd → shim → runc → OCI → namespace/cgroup** 这条链打通,接上 `linux-handson/09`(容器=被特殊安排的进程)。**架构师视角**:为什么有人说「k8s 弃用了 Docker」、运行时怎么选型、运行时层的故障与安全边界。

---

## Part A · 一张图:从 kubelet 到内核

```
kubelet ──CRI(gRPC)──► containerd ──► containerd-shim ──► runc ──► clone()/unshare()
 「我要这个Pod」  标准接口  容器运行时    每容器一个守护进程   OCI运行时   + namespaces + cgroups
                                                                   = 一个被隔离的普通进程(linux/09)
```

- **CRI(Container Runtime Interface)**:kubelet 和运行时之间的 **gRPC 标准接口**。kubelet **不直接懂** Docker/containerd,只说 CRI——这是解耦,谁实现 CRI 都能换上。
- **containerd**:CRI 实现,管镜像拉取、容器生命周期。
- **shim**:让容器进程的父进程**独立于 containerd**——containerd 重启,容器不跟着挂。
- **runc**:OCI 运行时,真正调 `clone()/unshare()` 建 namespace、写 cgroup(回扣 `linux-handson/09` 的底层)。

> 一句话:**kubelet 只下命令(CRI),一层层翻译到最后,runc 用 Linux 原语把容器「拼」出来。** 容器的底层(namespace/cgroup/overlayfs)在 `linux-handson/09`,这章是它和 k8s 之间的「中间链」。

---

## Part B · Pod 里的「pause 容器」🔬

一个 Pod 多容器**共享网络/IPC namespace**,是怎么做到的?

> 靠一个不起眼的 **pause 容器**:它**第一个起**,建好 network/IPC namespace 并 hold 住;Pod 里其他容器**加入(join)它的 namespace**。pause 几乎不占资源,是 Pod 的「namespace 锚 + 生命周期锚」。

这解释了两个「为什么」:**为什么 Pod 是最小单位**(共享 namespace 的容器组)、**为什么同 Pod 容器共享一个 IP**(共用 pause 的 network namespace)。

---

## Part C · 架构师视角:dockershim 移除与运行时选型 🔬

**「k8s 弃用 Docker」的真相**(高频误解,讲清显功底):
- 早期 kubelet 内置 **dockershim** 去适配 Docker daemon。k8s **1.24 移除 dockershim** → 直接用 CRI 运行时(containerd/CRI-O)。
- **弃的是「Docker 作为运行时」,不是「Docker 镜像」。** 镜像是 **OCI 标准**,照样能跑。你 `docker build` 的镜像在 containerd 上一样用。

**运行时选型(架构师取舍)**:

| 运行时 | 定位 | 何时选 |
|---|---|---|
| **containerd** | 主流、轻量 | 默认 |
| **CRI-O** | 为 k8s 而生、更精简 | OpenShift 系 |
| **gVisor / Kata** | 安全沙箱(用户态内核 / 轻量 VM) | **多租户、不可信代码**,牺牲性能换强隔离 |

> 取舍一句话:**普通业务 containerd;要把「共享内核」这个风险堵上(跑不可信代码、强多租户)才上 gVisor/Kata**——用性能换 VM 级隔离。

---

## Part D · 运行时层的故障与安全(接 debug + L7)🔬

- **故障**(直通 debug):镜像拉取失败(ImagePullBackOff,第 8 章)、runtime 不健康 → **节点 NotReady**(第 9 章)、磁盘满 → 容器创建失败。
- **安全边界**(回扣 L7 + `linux-handson/09`):**容器共享宿主机内核**——这是和 VM 的根本区别,也是**容器逃逸**的根源。一个内核漏洞可能让容器突破隔离。防御:非 root、只读根文件系统、seccomp/AppArmor 限系统调用、强隔离上 gVisor/Kata。
- **架构师认知**:**容器是「隔离」不是「安全边界」**。真要安全边界(跑别人的代码),要么沙箱运行时,要么干脆上 VM。

---

## 交叉引用

- **namespace/cgroup/overlayfs 底层** → `linux-handson/09`
- **镜像 OCI 标准 / 构建** → 第 1 章 `01`
- **ImagePullBackOff / 节点 NotReady** → debug 第 8、9 章
- **容器隔离 ≠ 安全边界** → L7 `system-design/10`
- **CRI 是 kubelet↔运行时的解耦** → 呼应第 3 章控制面解耦思想

---

## 本章小结

- **运行时链**:kubelet →(CRI gRPC)→ containerd →(shim)→ runc →(clone/namespaces/cgroups)→ 被隔离的进程;**kubelet 只说 CRI,不绑定具体运行时**。
- **pause 容器**先建好 namespace,Pod 内其他容器 join 它——这是「Pod 共享网络/IP、是最小单位」的实现。
- **「k8s 弃 Docker」= 弃 Docker 运行时(dockershim 1.24 移除),不弃 OCI 镜像**;运行时默认 containerd,强隔离上 gVisor/Kata。
- **容器共享内核 → 是隔离不是安全边界**;逃逸风险靠非 root/seccomp/沙箱运行时防。
- 下一篇内幕 B:控制面与数据面**怎么真正运转**(informer/watch、etcd 瓶颈、leader election、kube-proxy 包路径)。

---

## 章末问答(复习自检,答案要点都在前面正文)

1. 画出从 kubelet 到内核创建容器的完整链条,每一层干什么。
2. CRI 解耦了什么?为什么 kubelet「不直接懂 containerd」是好事?
3. pause 容器是干嘛的?它怎么解释「Pod 内容器共享 IP」?
4. 「k8s 弃用 Docker」准确的说法是什么?你的 docker build 镜像还能跑吗?
5. containerd 和 gVisor/Kata 的本质区别?什么场景才该上沙箱运行时?
6. 为什么说「容器是隔离不是安全边界」?根本原因是什么(回扣 linux/09)?
7. **综合题**:「你们要在 k8s 上跑用户提交的不可信代码,安全上你怎么设计」——从沙箱运行时、非 root、seccomp、NetworkPolicy、甚至独立集群几层答。
```
