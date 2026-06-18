# 容器与云原生 · 地图(Docker + Kubernetes + Debug)

> 面试导向 · 资深后端视角 · **doc-style**(概念全景 + **debug 排查手册** + 面试卡)
>
> 这是 `system-design/` 主线的 **L9「部署基础设施」**,内容大、自成体系,所以独立成一个 track。目标:把「容器化技术全景 + k8s/docker debug 最佳实践」补齐——尤其是 **debug**,这是面试和落地都最缺、最值钱的一块。

---

## 这个 track 的定位:补 k8s 主体 + debug,底层和性能「指进既有」

你的容器材料不是空白,是「底层有、性能有、**主体和 debug 没有**」。所以本 track **不重写底层**,只补缺口:

| 已有(指进,不重写) | 在哪 |
|---|---|
| 容器**底层原理**(namespace / cgroup / overlayfs /「容器只是进程」/ PID1 信号) | `linux-handson/09-containers-from-linux`(已写好,而且是 hands-on) |
| 容器 / k8s **性能** | `performance-tuning-roadmap/12-container` |

| 本 track 补(真缺口) |
|---|
| **Docker 应用层**:Dockerfile / 多阶段 / 镜像优化 / 编排 |
| **Kubernetes 系统知识**:架构 / 核心对象 / 调度 / 网络 / 存储 / 安全 |
| **k8s/docker debug 最佳实践**:一张张故障排查决策树(重头戏) |

---

## 章节地图

> 文件名用英文。✅=已写　⏳=待写

| 章 | 文件 | 内容 |
|---|---|---|
| **Docker 应用层** | | |
| 01 ✅ | `01-images-and-dockerfile.md` | 镜像分层、Dockerfile 最佳实践、多阶段构建、镜像瘦身与安全 |
| 02 ✅ | `02-compose-to-k8s.md` | docker-compose、为什么单机编排不够、k8s 解决什么 |
| **Kubernetes 主体** | | |
| 03 ✅ | `03-k8s-architecture-and-objects.md` | 控制面/数据面、Pod/Deployment/Service/Ingress、声明式 + reconcile |
| **原理内幕(C+,架构师深度)★** | | |
| 03a ✅ | `03a-container-runtime-internals.md` | kubelet→CRI→containerd→runc→OCI、pause、dockershim、沙箱运行时 🔬 |
| 03b ✅ | `03b-control-and-data-plane-internals.md` | informer/watch、etcd 瓶颈、leader election、kube-proxy 包路径、控制/数据面故障域 🔬 |
| **k8s 资源·网络·存储·安全** | | |
| 04 ✅ | `04-scheduling-and-resources.md` | scheduler、requests/limits、QoS、OOMKilled、亲和/污点、HPA |
| 05 ✅ | `05-networking.md` | Pod 网络/CNI、Service 三型、kube-proxy、Ingress、DNS、NetworkPolicy |
| 06 ✅ | `06-storage.md` | Volume/PV/PVC/StorageClass/CSI、StatefulSet、有状态该不该上 k8s |
| 07 ✅ | `07-config-and-security.md` | ConfigMap/Secret、RBAC、ServiceAccount、Operator/CRD |
| **Debug 最佳实践 ★** | | |
| 08 ✅ | `08-debug-pod-not-starting.md` | CrashLoopBackOff / ImagePullBackOff / Pending / OOMKilled / 探针失败 |
| 09 ✅ | `09-debug-networking-and-nodes.md` | Service 没流量 / DNS 失败 / 节点 NotReady / 性能(指进 perf/12) |
| 10 ✅ | `10-debug-methodology-and-kubectl.md` | 通用排查心法 + 命令速查 + 面试卡 |

**track 完成 ✅** —— 11 章(含 03a/03b 原理内幕,C+ 架构师深度);底层指进 `linux-handson/09`、性能指进 `perf/12`、处处回扣 `system-design` L0–L7。

---

## debug playbook 怎么用(格式说明)

debug 章不是知识罗列,是**可照着走的排查决策树**。每个故障一张:

> **现象** → **第一刀**(先敲哪个命令看什么)→ **分支判断**(看到 X 是这个根因、看到 Y 是那个)→ **每个分支:根因 + 修复** → **怎么预防**

例:`CrashLoopBackOff` → `kubectl describe pod` 看 Events + `kubectl logs --previous` → 分支:OOMKilled?探针失败?启动即崩?→ 各自根因与修复 → 预防(探针配置/资源 requests)。

---

## 一句话总纲(背起来)

> **容器 = 一个被 namespace 隔离、被 cgroup 限制的普通进程**(底层在 `linux-handson/09`);
> **Docker** 把它和镜像分层(overlayfs)封装成「可复现的交付单元」;
> **Kubernetes** 用**声明式 + 控制器 reconcile**,把「一堆容器」编排成「自愈、可扩缩、可发布」的集群;
> 而真正的功夫,是 Pod 起不来、网络不通、节点挂了的时候,你**有没有一套排查决策树**——这就是这个 track 的重点。
