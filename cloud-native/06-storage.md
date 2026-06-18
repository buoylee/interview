# 第 6 章 · Kubernetes 存储

> 🔬 容器是**临时的、重启即丢数据**(回扣 `03a`:容器=可写层在 Pod 上)。那数据库这种**有状态**应用怎么在 k8s 上跑?这章讲 **Volume → PV/PVC/StorageClass/CSI** 的解耦 + **StatefulSet**,并带**架构师视角**:有状态应用到底该不该上 k8s。

---

## Part A · 容器的临时性 → Volume

- 容器写的东西在**可写层**,Pod 删了就没了。要持久 → **Volume**。
- **emptyDir**:随 Pod 生死(Pod 删了就没),用于临时/缓存/容器间共享。
- **持久卷**:生命周期**独立于 Pod**,Pod 重建数据还在。

---

## Part B · PV / PVC / StorageClass / CSI 的解耦 🔬

```
应用 ──写──► PVC「我要 10Gi, RWO」 ──绑定──► PV(一块实际存储)
                  ▲                              │
            应用只关心 PVC                  底层是 NFS / 云盘 / Ceph,应用不管
                                          StorageClass:PVC 来了【自动创建】PV(动态供应)
```

- **PV(PersistentVolume)**:一块实际存储(管理员建,或动态建)。
- **PVC(PersistentVolumeClaim)**:应用的申请(要多大、什么访问模式)。**应用只写 PVC,不关心底层**——和 L2「存储选型」一样的接口抽象思想。
- **StorageClass**:**动态供应**,PVC 一来按 class 指定的后端自动建 PV。
- **CSI(Container Storage Interface)**:存储插件标准——和 **CRI(运行时)/ CNI(网络)** 同一个套路:**k8s 定接口,各家存储接进来**。
- **访问模式** 🔬:**RWO**(单节点读写,块存储一般只支持这个)/ ROX(多节点只读)/ **RWX**(多节点读写,要文件存储如 NFS/CephFS 才支持)。架构师要知道「块存储给不了 RWX」。

---

## Part C · StatefulSet:有状态应用 🔬

`Deployment` 的 Pod **无身份**:名字随机、IP 会变、要么无存储要么共享——这对无状态服务正好,但**数据库不行**。数据库需要:

| 需求 | StatefulSet 怎么给 |
|---|---|
| **稳定网络标识** | Pod 名固定:`mysql-0`、`mysql-1`(不是随机后缀) |
| **稳定独享存储** | 每个副本**绑自己的 PVC**(mysql-0 永远用 data-mysql-0) |
| **有序启停** | 按序号启动/缩容(0→1→2),主从拓扑需要 |

> 用于 MySQL/Redis/Kafka/ZooKeeper 这类**有状态集群**。

---

## Part D · 架构师视角:有状态该不该上 k8s 🔬

> StatefulSet 给了「稳定身份 + 稳定存储 + 有序」这些**原语**,但它**不懂**「数据库主从怎么切、怎么备份、怎么扩容」这些**运维知识**。

- **路线一:Operator**(回扣 `03b` reconcile + 第 7 章)——把数据库运维知识写成控制器,k8s 自动管(如 MySQL Operator)。**「有状态上 k8s」的关键拼图。**
- **路线二:不上 k8s**——数据库对 IO/网络延迟敏感、故障域大、k8s 弹性优势在有状态上打折。很多团队选择 **「无状态服务上 k8s、数据库用托管服务或物理机」**。
- **架构师一句话**:**无状态天然适合 k8s;有状态要么用成熟 Operator,要么用托管,别拿 StatefulSet 裸扛一个生产数据库。**

---

## 交叉引用

- **CSI 和 CRI/CNI 同套路(k8s 定接口)** → `03a`/第 5 章
- **存储接口抽象 = L2 选型思想** → L2 `06`
- **Operator 管有状态** → `03b` reconcile + 第 7 章
- **有状态故障转移/一致性** → L0 + `financial-consistency/`

---

## 本章小结

- 容器临时 → **Volume**;emptyDir 随 Pod 生死,**持久卷独立于 Pod**。
- **PV/PVC/StorageClass/CSI 解耦**:应用只写 PVC,底层存储随便换;CSI 和 CRI/CNI 一样是「k8s 定接口」;**块存储一般只 RWO,RWX 要文件存储**。
- **StatefulSet** 给有状态应用稳定身份 + 独享存储 + 有序启停(mysql-0/1/2)。
- **架构师取舍**:无状态适合 k8s;有状态要么 Operator、要么托管,别用 StatefulSet 裸扛生产库。
- 下一章:`07` 配置与安全(ConfigMap/Secret、RBAC、Operator/CRD)。

---

## 章末问答(复习自检,答案要点都在前面正文)

1. 为什么容器需要 Volume?emptyDir 和持久卷的区别?
2. PV、PVC、StorageClass 各是什么?「应用只写 PVC」体现了什么思想(回扣 L2)?
3. CSI 和 CRI/CNI 是同一个套路吗?这个套路是什么?
4. RWO 和 RWX 的区别?为什么块存储一般给不了 RWX?
5. StatefulSet 比 Deployment 多给了有状态应用哪三样东西?
6. 为什么说「StatefulSet 给了原语但不懂运维」?这缺口靠什么补?
7. **综合题**:「你们要在 k8s 上跑 MySQL,你怎么权衡、怎么设计」——从 StatefulSet/Operator/托管、存储 RWO、故障转移几方面答。
```
