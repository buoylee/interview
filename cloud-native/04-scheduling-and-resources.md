# 第 4 章 · 调度与资源:requests/limits、QoS、OOMKilled、HPA

> 🔬 「你 Pod 为什么被 OOMKilled」「requests 和 limits 区别」「Pod 一直 Pending 怎么回事」「怎么自动扩缩容」——这章是 k8s 的资源管理,也**直接喂给 debug**(OOMKilled、Pending 的根因都在这)。底层 cgroup 怎么限制资源,复习 `linux-handson/09`。

---

## Part A · requests vs limits(最高频)🔬

每个容器可以声明两个数:

```yaml
resources:
  requests: { cpu: "250m", memory: "256Mi" }   # 我【至少需要】这么多
  limits:   { cpu: "500m", memory: "512Mi" }   # 我【最多用】这么多
```

| | **requests** | **limits** |
|---|---|---|
| 作用 | **调度依据** | **运行时上限** |
| 谁用它 | Scheduler:按 requests 找「放得下」的节点 | kubelet/cgroup:超了就处理 |
| 超了会怎样 | — | **CPU → 限流(throttle)**;**内存 → OOMKilled** 🔬 |

> 关键区分(面试必考):**requests 决定「调度到哪」,limits 决定「运行时被不被杀/限」。** 内存是**不可压缩**资源,超 limit 直接杀(OOMKilled);CPU 是可压缩的,超了只是被限速。底层就是 `linux-handson/09` 的 cgroup。

---

## Part B · QoS 三级:节点没内存时先杀谁 🔬

k8s 按 requests/limits 的关系把 Pod 分三档,**节点内存压力时按档次驱逐**:

| QoS | 条件 | 驱逐顺序 |
|---|---|---|
| **Guaranteed** | requests == limits(都设且相等) | 最后被杀(最稳) |
| **Burstable** | requests < limits(设了但不等) | 中间 |
| **BestEffort** | 啥都没设 | **最先被杀** |

> 实践:核心服务设成 **Guaranteed**(requests=limits)保稳;别让重要服务裸奔成 BestEffort。

---

## Part C · 调度:Scheduler 怎么选节点 + Pending 的根因 🔬

Scheduler 两步:**① 过滤(filter)**——哪些节点放得下(资源够、满足亲和/污点);**② 打分(score)**——从能放的里选最优。

影响调度的手段:
- **nodeSelector / 亲和(affinity)**:让 Pod 倾向/避开某些节点(如 GPU 节点、同可用区)。
- **反亲和(anti-affinity)**:让副本分散到不同节点/机架(回扣 L4 消除单点)。
- **污点与容忍(taint / toleration)**:节点「打污点」拒绝 Pod,除非 Pod「容忍」它(如 master 节点默认拒业务 Pod)。

> **Pod 一直 `Pending` 的常见根因**(直通 debug 第 8 章):没有节点同时满足 **requests(资源不够)/ 亲和 / 污点 / PVC 未绑定**。`kubectl describe pod` 看 Events 一眼就知道是哪个。

---

## Part D · 自动扩缩:HPA / VPA / Cluster Autoscaler 🔬

| | 扩什么 | 怎么做 |
|---|---|---|
| **HPA**(水平) | **Pod 数量** | 按 CPU/内存/自定义指标自动加减副本(回扣 observability 指标 + L3 扩展) |
| **VPA**(垂直) | 单 Pod 的 requests/limits | 自动调大/调小资源 |
| **Cluster Autoscaler** | **节点数量** | 节点不够(Pod 一直 Pending)→ 自动加机器;闲了删机器 |

> 典型组合:**HPA 加 Pod**,Pod 多到节点放不下 → **Cluster Autoscaler 加节点**,两级弹性。HPA 依赖 Metrics Server 提供指标。

---

## 交叉引用

- **cgroup 限制资源的底层** → `linux-handson/09`
- **Pending / OOMKilled 排查** → debug 第 8 章
- **反亲和消除单点** → L4 `08` 可用性
- **HPA 按指标扩缩** → `observability/`(指标来源)+ L3 `01` 扩展
- **容器/k8s 性能调优** → `perf/12-container`

---

## 本章小结

- **requests = 调度依据(至少要多少),limits = 运行时上限**;**内存超 limit → OOMKilled(不可压缩),CPU 超 → 限流(可压缩)**。
- **QoS**:Guaranteed(=,最稳)> Burstable(<)> BestEffort(没设,最先被驱逐);核心服务设成 Guaranteed。
- **调度**:过滤 + 打分;nodeSelector/亲和/反亲和/污点容忍控制落点;**Pending 多是资源/亲和/污点/PVC 不满足**。
- **弹性**:HPA(加 Pod)/ VPA(调资源)/ Cluster Autoscaler(加节点),常 HPA + CA 两级配合。
- 下一章:`05` 网络——Pod 网络/CNI、Service 三型、kube-proxy、Ingress、DNS。

---

## 章末问答(复习自检,答案要点都在前面正文)

1. requests 和 limits 各自的作用是什么?谁影响调度、谁影响运行时?
2. 内存超 limit 和 CPU 超 limit,结果有什么不同?为什么?(可压缩 vs 不可压缩)
3. QoS 三级怎么划分?节点内存不够时先驱逐哪个?核心服务该设成哪个?
4. Pod 一直 Pending,你会先看什么?常见根因有哪些?
5. 污点(taint)和容忍(toleration)是干嘛的?反亲和有什么用(回扣可用性)?
6. HPA、VPA、Cluster Autoscaler 各扩什么?怎么配合?
7. **综合题**:「你的 Pod 频繁 OOMKilled,怎么排查和解决」——从 limits、实际用量、QoS、是否内存泄漏几方面答(为第 8 章 debug 铺垫)。
```
