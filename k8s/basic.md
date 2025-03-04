[toc]



## 概述





## 组件概述



### API Server

处理所有 K8s API 请求，作为集群的统一入口，存储数据到 etcd。
提供watch功能, 所有的informer或事件都是通過API Server 監聽





### **kubelet**

负责**本node创建/拉起 Pod**, 
kubelet 监听 API Server，发现有新 Pod 需要运行(**Replication Controller**创建或删除触发了事件, 被kubelet监听到)。
它调用容器运行时（containerd / CRI-O），**拉取镜像并启动容器**。

周期性**检查**(心跳之类) **本node** 运行的 **pod的状态**, 
也**检查** pod 是否**成功运行**,
並**同步狀態**給 **API Server -> etcd**.

### **Container Runtime（容器运行时，如 containerd / CRI-O）**

负责拉取镜像、创建容器，并管理其生命周期。



### **Scheduler**

只负责 Pod 调度(不会创建或删除 Pod), **监听 API Server**, 如有未綁定node的pod, 帮他选一个, 然后回报 API Server.



### **controller-manager**

负责**协调执行**多个不同的 Controller, 确保它们不会互相干扰，并合理分配资源.

通过**调用各种Controller** **监听 API Server，检查资源状态**,  在**逻辑层面创建资源**, 实际是kubelet或其他组件去做.





### **kube-proxy**

维护网络规则，确保集群内部和外部的网络通信（实现 Service 负载均衡）。

通过 监听 Endpoints 变更，更新 iptables 规则



### **coredns**

负责 Kubernetes 内部 DNS 解析，为 Service 提供域名解析功能。

监听 Service 变化，更新 DNS 解析

### **Metrics Server**

提供集群监控数据（CPU、内存），用于自动扩缩（HPA）。



### **Controller**

各种 Controller, 负责各自资源的状态监测(副本数), 
并控制(创建或删除.), **这里的控制, 理解为pod的定义**, 具体需要kubelet通过Container Runtime来创建.

