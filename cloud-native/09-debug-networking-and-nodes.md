# 第 9 章 · Debug Playbook(二):网络与节点

> 🔬 第二类高频故障:**Service 没流量、连不上、DNS 失败、节点 NotReady**。这些根因全在第 5 章和 `03b` 的原理里——**懂数据包怎么走,才会查;不懂只能瞎试**。这就是 C+ 的回报:原理是 debug 的地基。

---

## A · Service 连不上 / 没流量 🔬 → 回扣第 5 章 + 03b 包路径

**按数据路径从「源」到「目标」一层层查**(这正是 `03b` 的 kube-proxy 包路径反过来用):

```
① kubectl get endpoints <svc>
      │
      ├─ 空的!──► selector 没选中 Pod,或 Pod 没 Ready
      │           → 检查 Service.selector 和 Pod label 是否一致
      │           → 检查 readiness 探针(回扣第 8 章 E!没 Ready 就不在 Endpoints)
      │
      └─ 有 endpoints,还是不通
            │
            ② 进一个 Pod curl 目标 Pod IP 直连 ──► 不通?= 目标应用/CNI 问题
            ③ curl ClusterIP ──► 不通?= kube-proxy 规则问题(03b iptables/IPVS)
            │     → 看 kube-proxy Pod 健康吗、模式是什么
            ④ 跨节点不通 ──► CNI 网络插件问题(第 5 章)
```

> **一句话(面试金句)**:**「Service 不通,我第一刀永远是 `kubectl get endpoints`——空的就是 selector 或 readiness 问题,这占 90%。」** 这把第 5 章(Endpoints)、第 8 章(readiness)、03b(kube-proxy)全串起来了。

---

## B · DNS 解析失败 🔬 → 回扣第 5 章 CoreDNS

**现象**:服务名解析不了,或**间歇性**失败。

**排查**:
```bash
kubectl exec -it <pod> -- nslookup <svc>       # Pod 里能解析吗
kubectl get pod -n kube-system | grep coredns  # CoreDNS 健康吗
kubectl exec <pod> -- cat /etc/resolv.conf      # DNS 配置对吗
```

| 现象 | 根因 | 修复 |
|---|---|---|
| 全解析不了 | CoreDNS 挂了/没起 | 修 CoreDNS |
| 慢/间歇失败 | 经典 **conntrack + UDP DNS 5s 超时**问题 | NodeLocal DNSCache、或用 TCP、扩 CoreDNS |
| 解析到错的 | search 域 / ndots 配置 | 调 dnsConfig |

---

## C · 节点 NotReady 🔬 → 回扣 03a 运行时 + 03b 自愈

**现象**:`kubectl get nodes` 显示 `NotReady` → 上面的 Pod 会被标记、最终**驱逐重调度**(03b 的自愈)。**第一刀**:`kubectl describe node <node>` 看 **Conditions** + kubelet 状态。

| Condition / 线索 | 根因 | 修复 |
|---|---|---|
| kubelet 连不上 API Server | 节点 agent / 网络问题 | 查 kubelet 服务、节点网络 |
| 容器运行时不健康 | containerd 挂了(回扣 03a) | 重启/修 runtime |
| **DiskPressure** | 磁盘满(镜像/日志堆积) | 清理、加盘、配镜像 GC |
| MemoryPressure / PIDPressure | 资源耗尽 | 查谁占用、加资源 |
| CNI 没就绪 | 网络插件没起 | 修 CNI |

> 回扣 `03b`:**节点挂了,控制面会把它的 Pod 重调度到健康节点(自愈)**——但前提是控制面在线、且有别的节点放得下。

---

## D · 性能问题 → 指进 perf/12

Pod/节点的 **CPU 限流(throttle)、内存、IO 瓶颈**,有专门的深档:**`performance-tuning-roadmap/12-container`**(cgroup 资源、容器监控、k8s 性能)。这里只给入口——容器性能不是这个 track 重写的范围。

> 注意一个高频坑(回扣第 4 章):**CPU `limit` 设太低 → 容器被 cgroup 限流(throttle)→ 表现为「没满载却很慢」**,`kubectl top` 看不出,要看 cgroup throttle 指标。

---

## 本章小结

- **Service 不通**:第一刀 `get endpoints`——**空的 = selector/readiness 问题(90%)**;有 endpoints 再按包路径查 Pod 直连→ClusterIP(kube-proxy)→跨节点(CNI)。
- **DNS**:`exec nslookup` + 查 CoreDNS;**间歇失败警惕 conntrack/UDP 5s 超时**,用 NodeLocal DNSCache。
- **节点 NotReady**:`describe node` 看 Conditions——kubelet/runtime(03a)/磁盘/CNI;节点挂了控制面重调度 Pod(03b 自愈)。
- **性能** → 指进 `perf/12`;注意 **CPU limit 太低→throttle→「没满载却慢」**。
- 下一章:`10` 通用 debug 方法论 + kubectl 武器库 + 面试卡。

---

## 章末问答(复习自检)

1. Service 不通,你的第一刀是什么命令?Endpoints 为空说明什么?
2. 完整画出「Service 没流量」从 Endpoints 到 CNI 的排查路径(回扣 03b 包路径)。
3. DNS 间歇性失败,经典根因是什么?怎么缓解?
4. 节点 NotReady,你看哪个命令的什么字段?列三个常见根因。
5. 「CPU 没满载但应用很慢」可能是什么?(回扣 limit/throttle)
6. **综合题**:「线上一个服务突然大量超时,kubectl 看 Pod 都 Running」——你会从 Endpoints、readiness、DNS、节点、限流哪几条线查?
```
