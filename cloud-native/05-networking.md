# 第 5 章 · Kubernetes 网络

> 🔬 k8s 网络是 debug **最常踩的坑**(Service 没流量、DNS 不通、跨 Pod 不通)。这章讲清四层:**Pod 网络(CNI)→ Service(稳定入口)→ Ingress(七层)→ DNS**,加 NetworkPolicy。它是第 9 章「网络 debug」的地基。
>
> 📦 数据包**到底怎么走**(veth → 网桥 → iptables/IPVS/eBPF 的包路径)+ 三种 kube-proxy 模式的规模取舍,内幕在 `03b`。

---

## Part A · k8s 网络模型:四条铁律 + CNI

k8s 规定的网络模型(实现交给插件):

1. **每个 Pod 一个独立 IP**。
2. **Pod 之间直接通,不经 NAT**(扁平网络)。
3. 节点和 Pod 也能互通。
4. Pod 看到的自己 IP = 别人看到它的 IP。

> 这套模型由 **CNI 插件**实现:**Flannel**(简单)、**Calico**(网络策略强)、**Cilium**(eBPF,云原生新主流)。面试知道「Pod 网络是 CNI 插件实现的、Cilium 用 eBPF」就够。

---

## Part B · Service:给一组临时 Pod 一个稳定入口 🔬

**问题**:Pod 是临时的、IP 会变(回扣第 3 章)。**Service** = 一个**稳定的虚拟 IP(ClusterIP)+ DNS 名**,用 **label selector** 选中一组 Pod,自动负载均衡过去。

```
Service(ClusterIP 10.96.x.x, 稳定)
   │ label selector: app=web
   ├──► Pod web-1 (IP 易变)
   ├──► Pod web-2
   └──► Pod web-3      ← kube-proxy 把发往 ClusterIP 的流量 DNAT 到某个 Pod
```

- **底层**:**kube-proxy** 在每个节点维护 **iptables / IPVS** 规则,实现这个虚拟 IP → 真实 Pod 的转发(回扣 L1 服务端负载均衡)。
- **三种类型** 🔬:

| 类型 | 作用 | 场景 |
|---|---|---|
| **ClusterIP**(默认) | 集群内部访问 | 服务间调用 |
| **NodePort** | 每个节点开一个端口对外 | 简单外部访问/测试 |
| **LoadBalancer** | 云厂商分配外部 LB | 生产对外服务 |

- **Endpoints / EndpointSlice**:Service 背后**实际健康的 Pod 列表**(健康检查没过的不在里面,回扣服务发现)。**Service 没流量?先看 Endpoints 是不是空的**(直通第 9 章)。

---

## Part C · Ingress:七层入口

每个对外 Service 都开一个 `LoadBalancer` 太贵。**Ingress = 一个统一的七层入口**,按 **host / path** 路由到不同 Service(回扣 L1 网关、南北向流量):

```
外部 ──► Ingress(api.foo.com/orders → orders-svc)
              (api.foo.com/users  → users-svc)
```

> **Ingress 本身只是规则,真正干活的是 Ingress Controller**(Nginx Ingress / Traefik / 云厂商)。没装 Controller,Ingress 不生效——这是常见坑。

---

## Part D · 集群 DNS + NetworkPolicy

- **集群 DNS(CoreDNS)** 🔬:每个 Service 自动有 DNS 名 `服务名.命名空间.svc.cluster.local`。Pod 靠**域名**而不是 IP 发现服务(回扣 L1 server-side discovery)。**DNS 不通是网络故障重灾区**(第 9 章)。
- **NetworkPolicy**:k8s **默认 Pod 之间全通**(零隔离!)。NetworkPolicy 做**白名单隔离**(只允许指定来源访问)——回扣 L7 最小权限/网络分区。注意:**NetworkPolicy 要 CNI 支持**(Calico/Cilium 支持,Flannel 不支持)。

---

## 交叉引用

- **kube-proxy 转发 = 服务端 LB** → L1 `05`
- **CoreDNS 域名发现** → L1 服务发现
- **NetworkPolicy 隔离** → L7 `10` 网络分区/最小权限
- **Service 没流量 / DNS 失败 / 跨 Pod 不通** → 第 9 章 debug playbook

---

## 本章小结

- **网络模型四铁律**(每 Pod 独立 IP、直连不 NAT),由 **CNI 插件**(Calico/Cilium/Flannel)实现。
- **Service** 用 label 选中一组 Pod,给**稳定 ClusterIP + DNS**;底层 **kube-proxy(iptables/IPVS)** 转发;三型 ClusterIP/NodePort/LoadBalancer;**没流量先看 Endpoints**。
- **Ingress** = 七层统一入口(host/path 路由),**靠 Ingress Controller 生效**。
- **CoreDNS** 让 Pod 靠域名发现 Service;**NetworkPolicy** 做白名单隔离(默认全通,要 CNI 支持)。
- 下一章:`06` 存储——PV/PVC/StorageClass/CSI + StatefulSet。

---

## 章末问答(复习自检,答案要点都在前面正文)

1. k8s 网络模型的核心要求是什么?谁来实现?
2. Pod IP 会变,Service 怎么提供稳定访问?底层靠什么转发?
3. ClusterIP、NodePort、LoadBalancer 各用在什么场景?
4. Service 没流量,你第一个会去看什么?(Endpoints)
5. Ingress 和 Service 的 LoadBalancer 比,好在哪?Ingress 不生效最常见的原因?
6. Pod 怎么靠域名发现 Service?DNS 名长什么样?
7. NetworkPolicy 解决什么(回扣 L7)?为什么有时配了不生效?
8. **综合题**:「你 curl 一个 Service 不通,怎么一步步排查」——从 Endpoints、kube-proxy、DNS、NetworkPolicy 几层查(为第 9 章铺垫)。
```
