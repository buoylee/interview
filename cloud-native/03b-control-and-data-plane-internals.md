# 第 3 章·内幕 B · 控制面与数据面怎么真正运转

> 🔬 这章是 k8s 的「神经系统内幕」,也是 **C+ 架构师深度**的集中体现:reconcile **不是傻轮询**、watch **不是轮询**、kube-proxy **不真代理流量**、控制面挂了**数据面还在跑**。每一节都配「失效模式 + 规模上限 + 取舍 + 回扣 L0」——这正是**架构师面试的天花板答法**:把 k8s 讲成分布式理论的一个实例。

---

## Part A · list-watch + informer:k8s 怎么不靠轮询感知变化 🔬

**问题**:几十个控制器都要知道「期望状态变了没」。如果各自**轮询 etcd**,etcd 瞬间被打爆。

**机制**:
```
list-watch:① List 全量(初始)→ ② Watch 增量(长连接,变化由 API Server 推送)
informer  :客户端本地缓存(Indexer)+ 事件分发 → 变化入 WorkQueue → 控制器消费 reconcile
```
- **informer** 让控制器**读本地缓存**(不每次打 API Server),**写经 WorkQueue 串行处理**(去重、限速、失败重入队)。
- **resourceVersion** 保证「断线重连不漏事件」(回扣 L0 顺序/一致性)。

> **架构师视角(规模上限)** 🔬:watch 是**有状态长连接**。对象数、watch 数一多 → **API Server 内存 + etcd 压力陡增**——这是大集群的**头号扩展瓶颈**。所以大集群要:控制 CRD/对象数量、用 label/field selector 缩小 watch 范围、分片控制器。

---

## Part B · etcd:真相源,也是控制面的瓶颈 🔬

etcd 存**整个集群状态**,底层是 **Raft**(回扣 L0 共识/quorum)。

> **架构师视角(规模与失效)** 🔬:
> - **每个写都要 Raft 多数派确认**(回扣 L0「写延迟 = quorum 往返」)→ etcd 是控制面**写吞吐的天花板**。
> - 对象太多 / 大对象 / event 风暴 / watch 太多 → **etcd 变慢 → API Server 变慢 → 整个控制面卡**。大集群实践:etcd 独享高速 SSD、把 **Events 拆到独立 etcd**、定期 **compaction/defrag**、限制单对象大小。
> - **etcd 失去多数派**(如机房分区少数派侧)→ 控制面**只读、不能写**(不能调度/发布/自愈)→ 这是 **CAP 选 C 牺牲 A**(回扣 L0):k8s 控制面是 CP 系统。

---

## Part C · 控制器的高可用:leader election 🔬

`kube-controller-manager` / `kube-scheduler` 通常多副本部署。但——**同一时刻只能一个在干活**,否则两个控制器同时 reconcile 会**互相打架**(一个建、一个删)。

> 靠 **leader election**:多副本竞争一个基于 **etcd Lease 的分布式锁**,抢到的当 leader 干活,其余待命;leader 续不上租约 → 重新选举。**这就是 L0 共识 + L1 分布式锁的直接应用。**

**一句话(架构师认知)**:**k8s 控制面自己就是一个分布式系统**——etcd 是 Raft、控制器靠 leader election、组件靠 watch 协调。**你学的 L0 理论,k8s 内部处处在用。**

---

## Part D · kube-proxy 数据包路径:Service 流量到底怎么走 🔬

**先破一个误解**:**kube-proxy 不在数据路径上「代理」流量**——它只**写内核转发规则**,真正转发是**内核**(netfilter)。

```
Pod 访问 ClusterIP 10.96.x.x
   │  内核 netfilter / iptables(或 IPVS)匹配 Service 规则
   ▼  DNAT:目标地址改写成某个后端 Pod IP(从健康 Endpoints 里选)
   ▼  经 CNI(veth → 网桥/路由)送到目标 Pod
目标 Pod
```

> **架构师视角(规模拐点 + 取舍)** 🔬:
>
> | 模式 | 数据结构 | 规模表现 |
> |---|---|---|
> | **iptables** | 规则链,**O(n) 线性匹配** | 几千 Service 就规则爆炸、转发慢、**规则更新也慢** |
> | **IPVS** | 内核 hash 表,**O(1)** | 为大规模设计,首选 |
> | **eBPF(Cilium)** | 内核态程序,**绕过 kube-proxy/iptables** | 最优,云原生新方向 |
>
> 取舍:**小集群 iptables 够用;Service 规模上来(上千)换 IPVS;追求极致 + 可观测换 eBPF/Cilium。** 这是个真实的架构决策点,不是「都一样」。

---

## Part E · 控制面 vs 数据面解耦:故障域(架构师必答)🔬

**问题**:API Server / etcd / scheduler **全挂了**,你已经在跑的业务 Pod 会怎样?

> **答案:照常跑。** 因为 Pod 由所在节点的 **kubelet 直接管**,kubelet 不依赖控制面「实时在线」。
>
> **但是**:不能调度新 Pod、Pod 挂了**不会自愈**、**不能发布/扩缩**、Service 端点不更新。

- **回扣 CAP**:这是 k8s 刻意的可用性设计——**控制面不可用时,优先保「存量服务继续跑」(数据面),牺牲「管理与自愈能力」(控制面)**。
- **架构师答法(金句)**:**「控制面是大脑,数据面是四肢。大脑短暂离线,四肢按惯性继续动,但失去新指令、失去自愈。」** 所以控制面要高可用(多副本 + etcd 奇数集群),但即便它挂,也不会瞬间业务全崩。

---

## 交叉引用

- **etcd = Raft / quorum / 写延迟 / CP** → L0 `00`/`03` + CAP
- **leader election = 共识 + 分布式锁** → L0 `00` + L1 `05`
- **kube-proxy = 服务端 LB 的内核实现** → L1 `05` + 第 5 章
- **watch 一致性 / resourceVersion** → L0 `02` 一致性
- **数据包路径 / IPVS / eBPF** → 第 5 章 + 第 9 章 debug

---

## 本章小结

- **list-watch + informer**:list 全量 + watch 增量(长连接推送),informer 本地缓存 + WorkQueue——**不靠轮询**;**watch 是大集群头号扩展瓶颈**。
- **etcd**:Raft 真相源,**每写要 quorum → 控制面写吞吐天花板**;对象/watch 多就拖垮;失多数派 → 控制面只读(**CP,CAP 选 C**)。
- **leader election**:控制器多副本只一个干活,靠 etcd Lease 分布式锁——**L0 共识的直接应用**。
- **kube-proxy 只写规则、内核转发**;**iptables O(n) → IPVS O(1) → eBPF**,是真实规模拐点和取舍。
- **控制面/数据面解耦**:控制面挂了存量 Pod 照跑、但失去调度/自愈/发布——CAP 设计,「大脑离线四肢按惯性」。
- 至此 k8s「怎么真正运转」打通,后面资源/网络/存储章都站在这个内幕之上。

---

## 章末问答(复习自检,答案要点都在前面正文)

1. 控制器怎么感知期望状态变化、又不打爆 etcd?(list-watch + informer)
2. 为什么说「watch 是大集群的头号扩展瓶颈」?大集群怎么缓解?
3. 为什么 etcd 是控制面的写吞吐天花板?(回扣 L0 quorum)
4. etcd 失去多数派时控制面会怎样?这对应 CAP 的什么选择?
5. 为什么 controller-manager 多副本却只有一个在干活?靠什么机制?(回扣 L0/L1)
6. kube-proxy 到底「代理」流量吗?Service 流量真正怎么转发?
7. iptables / IPVS / eBPF 三种模式的规模差异和取舍是什么?
8. 控制面全挂了,正在跑的业务 Pod 会怎样?为什么?用「大脑/四肢」讲清(回扣 CAP)。
9. **综合题**:「你们 k8s 集群规模涨到几千节点/上万 service,控制面开始变慢,你从哪些方面优化」——从 etcd、watch/informer、kube-proxy 模式几方面答(这是纯架构师题)。
```
