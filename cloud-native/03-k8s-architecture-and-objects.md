# 第 3 章 · Kubernetes 架构与核心对象

> 🔬 k8s 面试**必问的地基**:控制面有哪些组件、一个 Pod 从 `kubectl apply` 到跑起来经历了什么、Pod/Deployment/Service 是什么关系。把这些 + 「**声明式 + 控制器 reconcile**」这个灵魂讲清,你就真懂 k8s 在干嘛,而不是只会 `kubectl apply`。
>
> 📦 本章是**架构骨架**;更深的**运行内幕**(C+ 架构师深度)拆在两篇:容器运行时链 → `03a`;informer/watch、etcd 瓶颈、leader election、kube-proxy 包路径、控制/数据面故障域 → `03b`。

---

## Part A · 架构:控制面 + 工作节点(吸收 `k8s/basic.md`)

```
┌─────────────── 控制面 Control Plane(大脑)───────────────┐
│  API Server   ← 唯一入口,所有操作经它,读写 etcd          │
│  etcd         ← 集群状态的【唯一真相源】(CP,底层 Raft)   │
│  Scheduler    ← 决定 Pod 该放哪个节点                      │
│  Controller Manager ← 跑各种控制器(reconcile 循环)        │
└───────────────────────────────────────────────────────────┘
        │ (API Server 下发 / 节点上报)
┌───────────────── 工作节点 Node(干活)─────────────────────┐
│  kubelet          ← 节点 agent,管本节点 Pod 生命周期       │
│  Container Runtime← containerd / CRI-O,真正跑容器          │
│  kube-proxy       ← 维护 Service 的网络转发规则            │
└───────────────────────────────────────────────────────────┘
```

> 两个关键点 🔬:① **etcd 是唯一真相源**(回扣 L0:etcd 是 CP、用 Raft 选主,所以集群「大脑」强一致、不脑裂)。② **API Server 是唯一入口**——一切组件不直接互相调,都通过 watch API Server/etcd 协作(解耦)。

---

## Part B · 一个 Pod 的诞生(reconcile 全流程)🔬

```
kubectl apply -f deploy.yaml
      │
      ▼
① API Server:校验 → 写入 etcd(期望:要 3 个 Pod)
② Deployment Controller:看到 Deployment → 建 ReplicaSet
③ ReplicaSet Controller:看到要 3 个、现实 0 个 → 创建 3 个 Pod(未调度)
④ Scheduler:看到未调度 Pod → 选节点 → 把「Pod→节点」写回 etcd
⑤ 目标节点 kubelet:watch 到「我这有个 Pod」→ 调 runtime 拉镜像、起容器
⑥ kubelet 持续上报 Pod 状态 → etcd
```

> **每个组件都在做同一件事:watch「期望状态」,让「现实」趋近它。** 这个「比对期望 vs 现实 → 消除差异」的循环,就是 **reconcile**——k8s 的灵魂(Part D)。

---

## Part C · 核心对象 🔬

| 对象 | 一句话 | 关键 |
|---|---|---|
| **Pod** | 最小调度单位,1+ 个共享网络/存储的容器 | **临时的**:会被重建,**IP 会变**(所以需要 Service) |
| **ReplicaSet** | 保证 N 个 Pod 副本 | 一般不直接用,被 Deployment 管 |
| **Deployment** | 管 ReplicaSet,提供**滚动发布/回滚** | ← 你日常打交道的;回扣 L6 |
| **Service** | 给一组 Pod 一个**稳定虚拟 IP + DNS 名** | 解决「Pod IP 易变」,回扣 L1 服务发现 |
| **Ingress** | 七层入口,把外部 HTTP 路由到 Service | 回扣 L1 网关 / 南北向 |
| **ConfigMap / Secret** | 配置 / 密钥,注入容器 | 回扣 L1 配置中心 / L7 |
| **Namespace** | 逻辑隔离(团队/环境) | 配额、权限边界 |
| **StatefulSet / DaemonSet / Job** | 有状态 / 每节点一个 / 一次性任务 | 第 6 章细讲 StatefulSet |

**关系链(白板必画)**:
```
Deployment ──管──► ReplicaSet ──管──► Pod (×N)
                                       ▲
Service ──(用 label 选中)─────────────┘   ← 给这组 Pod 稳定入口
Ingress ──路由──► Service                  ← 外部 HTTP 进来
```

---

## Part D · 声明式 + 控制器模式(灵魂)🔬

```
你写 YAML:「我要 3 个副本」(期望状态,desired state)
        │
        ▼
控制器 reconcile loop(无限循环):
   读期望(etcd) ── 比对 ──► 读现实(实际几个 Pod)
        ▲                          │
        └────── 有差异?调整 ◄──────┘
          (少了就建、多了就删、挂了就重建)
```

- **声明式**:你描述「**想要什么**」,不写「**怎么一步步做**」。
- **控制器 reconcile**:持续比对期望 vs 现实,自动消除差异——这就是 **k8s「自愈」「弹性」的本质**:你删一个 Pod,控制器发现少了,立刻补一个。
- **Operator / CRD**(第 7 章预告):把「reconcile 模式」开放给你——自定义资源(CRD)+ 自定义控制器,让 k8s 帮你管理任意有状态应用(如数据库 Operator)。

> 面试金句:**「k8s 不是『执行你的命令』,是『不断让世界变成你声明的样子』。」**

---

## 交叉引用

- **etcd = CP / Raft** → L0 `00`/`03`
- **Pod IP 易变 → Service 稳定入口** → L1 服务发现 `05`
- **Deployment 滚动发布/回滚** → L6 `09`
- **Pending(调度不上)/ 探针 / OOM** → 第 4 章 + debug 第 8 章

---

## 本章小结

- **控制面**:API Server(唯一入口)、**etcd(唯一真相源,CP/Raft)**、Scheduler(选节点)、Controller Manager(reconcile);**工作节点**:kubelet、容器运行时、kube-proxy。
- **Pod 诞生**:apply→etcd→各控制器建 RS/Pod→Scheduler 选节点→kubelet 起容器,全程靠 watch + reconcile。
- **核心对象**:Pod(临时、IP 会变)→ ReplicaSet → Deployment(发布/回滚);Service(稳定入口)、Ingress(七层)、ConfigMap/Secret、Namespace。
- **灵魂 = 声明式 + 控制器 reconcile**:描述期望状态,系统持续趋近——自愈的本质;Operator/CRD 是它的延伸。
- 下一章:`04` 调度与资源(requests/limits、QoS、OOMKilled、HPA)。

---

## 章末问答(复习自检,答案要点都在前面正文)

1. 控制面四大组件各干什么?为什么说 etcd 是「唯一真相源」(回扣 L0 它为什么是 CP)?
2. 描述一个 Pod 从 `kubectl apply` 到容器跑起来的全过程。
3. 为什么 Pod 需要 Service?(Pod 的什么特性决定的)
4. Deployment、ReplicaSet、Pod 三者什么关系?画出来。
5. 什么是「声明式 + reconcile」?它如何实现「自愈」?
6. Operator/CRD 把什么能力开放给了用户?
7. **综合题**:「你 `kubectl delete pod` 删了一个 Pod,它为什么又自己回来了」——用控制器 reconcile 解释。
```
