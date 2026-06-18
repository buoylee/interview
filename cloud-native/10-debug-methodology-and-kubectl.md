# 第 10 章 · Debug 方法论 + kubectl 武器库 + 面试卡

> 🔬 前两章是「具体故障」,这章给**通用方法论**(任何 k8s 故障都能套)+ **kubectl 武器库** + **面试速答卡**。这也是整个 `cloud-native/` track 的收束——把架构、内幕、资源、网络、debug 串成一张可上白板的图。

---

## A · 通用排查方法论:按「声明 → 运行」分层定位 🔬

k8s 故障的本质(回扣 `03b` reconcile):**现实没趋近期望,卡在某一层**。所以排查就是**从声明一路追到运行,看断在哪**:

```
① 声明层  get/describe 对象 → 期望状态对吗?Events 说什么?  ← describe 永远第一刀
② 调度层  Pod 调度上了吗?            → Pending?   → 第 8 章
③ 运行层  容器起来了吗?logs 说什么?  → CrashLoop? → 第 8 章
④ 网络层  能通吗?Endpoints / DNS      → 没流量?   → 第 9 章
⑤ 节点层  节点健康吗?                 → NotReady?  → 第 9 章
```

> **心法两条**:① **`describe` 看 Events 永远是第一刀**(k8s 主动告诉你卡在哪)。② **期望 vs 现实**——把每个故障想成「reconcile 断在第几层」,而不是孤立现象。这就是懂原理(03b)带来的 debug 直觉。

---

## B · kubectl 武器库(速查)🔬

| 用途 | 命令 |
|---|---|
| **看状态** | `get pod -o wide` / `get all` / `get pod -A` |
| **看详情(★)** | `describe pod/node/svc`(看 Events) |
| **看日志** | `logs -f` / `logs --previous`(崩溃前) |
| **看事件** | `get events --sort-by=.lastTimestamp` |
| **进容器** | `exec -it <pod> -- sh` / `debug`(临时调试容器) |
| **看资源** | `top pod` / `top node` |
| **看端点** | `get endpoints <svc>`(Service 不通必看) |
| **本地连** | `port-forward <pod> 8080:8080` |
| **集群** | `get nodes` / `cluster-info` |

> 黄金组合:**`describe` + `logs --previous` + `get events`** —— 八成故障靠这三个定位。

---

## C · k8s 故障速查表(贴墙用)

| 现象 | 最可能根因 | 第一刀 | 章节 |
|---|---|---|---|
| **Pending** | 资源/亲和/污点/PVC 不满足 | `describe pod` | 8·A |
| **ImagePullBackOff** | 镜像名/认证/网络 | `describe pod` | 8·B |
| **CrashLoopBackOff** | 应用崩 / OOM / 探针 | `logs --previous` | 8·C |
| **OOMKilled(137)** | 超 limit / 泄漏 / JVM | `describe` + `top` | 8·D |
| **Running 但没流量** | Endpoints 空(selector/readiness) | `get endpoints` | 9·A |
| **DNS 失败** | CoreDNS / conntrack | `exec nslookup` | 9·B |
| **节点 NotReady** | kubelet/runtime/磁盘/CNI | `describe node` | 9·C |
| **没满载却慢** | CPU limit → throttle | cgroup 指标 | 9·D |

---

## D · 面试速答卡(把整个 track 串起来)🔬

- **「Pod 一直 Pending 怎么查?」** → describe 看 FailedScheduling → 资源/亲和/污点/PVC(第 4/8 章)。
- **「CrashLoopBackOff 怎么查?」** → `logs --previous` + Exit Code → 应用崩/OOM(137)/探针(第 8 章)。
- **「Service 不通怎么查?」** → 第一刀 `get endpoints`,空的就是 selector/readiness;再按包路径查 kube-proxy/CNI(第 9 章 + 03b)。
- **「控制面挂了,业务 Pod 还在跑吗?」** → 在跑!数据面解耦,但不能调度/自愈/发布——**CAP 选 C**(`03b`,这题答得出就是架构师)。
- **「大集群控制面变慢怎么优化?」** → etcd(独立 SSD/拆 events)、watch/informer(缩 selector)、kube-proxy 换 IPVS/eBPF(`03b`)。
- **「容器为什么被 OOMKilled?Java 要注意什么?」** → 超 cgroup limit;JVM 要感知 cgroup、用 MaxRAMPercentage(第 8 章)。
- **「k8s 弃用 Docker 是什么意思?」** → 弃 Docker 运行时(dockershim),不弃 OCI 镜像(`03a`)。

---

## 本章小结 + 整个 track 收束

- **方法论**:按「声明→调度→运行→网络→节点」分层定位;**describe 看 Events 第一刀**;**期望 vs 现实(reconcile)** 是 debug 的思维模型。
- **武器库**:describe + logs --previous + events 黄金三件套 + endpoints/top/exec/debug。
- **速查表 + 面试卡**:把 Pending/CrashLoop/OOM/Service 不通/DNS/NotReady 全收口,根因都指回原理章。
- **整个 `cloud-native/` track 收束**:Docker 应用层 → k8s 架构与**原理内幕(C+)** → 资源/网络/存储/安全 → **debug 三章**;底层指进 `linux-handson/09`、性能指进 `perf/12`、处处回扣 `system-design` 的 L0–L7。
- **架构师天花板**:你现在能把 k8s 讲成「分布式理论(L0)的一个落地实例」,并在故障时**用原理推理而不是背命令**——这就是这个 track 的目标。

---

## 章末问答(复习自检)

1. k8s 故障排查的「分层定位」是哪五层?为什么 describe 永远第一刀?
2. 「期望 vs 现实」这个思维模型怎么帮你 debug(回扣 03b reconcile)?
3. 默写黄金三件套命令,各看什么。
4. 不看前文,默写故障速查表至少 6 行(现象→根因→第一刀)。
5. **终极综合题**:面试官给你「线上服务大面积超时」,从 Pod 状态、Endpoints、readiness、DNS、节点、限流、控制面,讲一条系统化的排查 + 推理路径(把整个 track 串起来)。
```
